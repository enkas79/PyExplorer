"""
Modulo Principale: PyExplorer - Pro.

Gestore file SFTP avanzato per Raspberry Pi e server Linux.
Architettura: MVC (Model-View-Controller) con PyQt6.
Caratteristiche: Multi-lingua, Auto-Update, Gestione asincrona dei task.

Autore: Enrico Martini
Versione: 1.0.5
"""

import os
import json
import stat
import tempfile
import platform
import subprocess
import posixpath
import socket
import traceback
import sys
import requests
from typing import Dict, List, Optional, Tuple, Any, Union

import paramiko
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QListWidget, QWidget, QMessageBox, QFileDialog, QLabel,
    QFrame, QMenu, QListWidgetItem, QDialog, QTextBrowser, QDialogButtonBox,
    QProgressDialog
)
from PyQt6.QtGui import QAction, QIcon, QFont, QDesktopServices
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QObject, QUrl

# --- CONFIGURAZIONE ---
GITHUB_REPO: str = "enkas79/PyExplorer"  # Da aggiornare con il repo corretto
AUTHOR: str = "Enrico Martini"
VERSION: str = "1.0.5"
CONFIG_FILE: str = "connessioni_raspberry.json"


# ==========================================
# MODELLO (LOGICA DI BUSINESS)
# ==========================================

class SftpManager:
    """Classe Model per la gestione delle operazioni SFTP."""

    def __init__(self) -> None:
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.sftp_client: Optional[paramiko.SFTPClient] = None
        self.current_remote_path: str = "/"

    def connect(self, host: str, user: str, psw: str) -> bool:
        """Stabilisce una connessione SSH/SFTP sicura."""
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(hostname=host, username=user, password=psw, timeout=10)
            self.sftp_client = self.ssh_client.open_sftp()
            self.current_remote_path = self.sftp_client.normalize('.')
            return True
        except Exception as e:
            raise ConnectionError(f"Errore di connessione: {str(e)}")

    def disconnect(self) -> None:
        """Chiude le connessioni attive."""
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()

    def list_dir(self, path: str) -> List[paramiko.SFTPAttributes]:
        """Elenca i file nella directory remota specificata."""
        if not self.sftp_client:
            raise RuntimeError("Client SFTP non connesso.")
        return self.sftp_client.listdir_attr(path)

    def upload(self, local: str, remote: str) -> None:
        """Carica un file sul server."""
        if self.sftp_client:
            self.sftp_client.put(local, remote)

    def download(self, remote: str, local: str) -> None:
        """Scarica un file dal server."""
        if self.sftp_client:
            self.sftp_client.get(remote, local)

    def delete(self, path: str, is_dir: bool = False) -> None:
        """Elimina un file o una directory."""
        if not self.sftp_client:
            return
        if is_dir:
            self.sftp_client.rmdir(path)
        else:
            self.sftp_client.remove(path)


# ==========================================
# CONTROLLER (TASK ASINCRONI)
# ==========================================

class UpdateWorker(QThread):
    """Worker per il controllo degli aggiornamenti via GitHub API."""
    finished = pyqtSignal(bool, str, str)
    error = pyqtSignal(str)

    def run(self) -> None:
        """Esegue il controllo asincrono della versione."""
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_ver = data.get('tag_name', '').replace('v', '')
                download_url = ""
                for asset in data.get('assets', []):
                    if asset['name'].endswith('.exe') or asset['name'].endswith('.deb'):
                        download_url = asset['browser_download_url']
                        break
                self.finished.emit(latest_ver > VERSION, latest_ver, download_url)
        except Exception as e:
            self.error.emit(str(e))


# ==========================================
# VISTA (INTERFACCIA GRAFICA)
# ==========================================

class GuideDialog(QDialog):
    """Finestra di documentazione per l'utente."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guida all'uso - PyExplorer")
        self.setMinimumSize(600, 400)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setHtml(f"""
            <h1>PyExplorer Pro - Manuale Utente</h1>
            <p>Benvenuto in PyExplorer, lo strumento professionale per la gestione dei tuoi file remoti.</p>
            <ul>
                <li><b>Connessione:</b> Inserisci IP, Username e Password del tuo Raspberry o server.</li>
                <li><b>Navigazione:</b> Fai doppio click su una cartella per entrare. Usa '..' per tornare indietro.</li>
                <li><b>Download:</b> Fai doppio click su un file per scaricarlo e aprirlo localmente.</li>
                <li><b>Azioni:</b> Usa il tasto destro su file o cartelle per eliminare gli elementi.</li>
                <li><b>Aggiornamenti:</b> Il programma controlla automaticamente nuove versioni all'avvio.</li>
            </ul>
        """)
        layout.addWidget(browser)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


class InfoDialog(QDialog):
    """Finestra delle informazioni sul software."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Informazioni")
        self.setFixedSize(300, 180)
        layout = QVBoxLayout(self)
        info = QLabel(f"<h2>PyExplorer Pro</h2>"
                      f"<p><b>Autore:</b> {AUTHOR}<br>"
                      f"<b>Versione:</b> {VERSION}<br>"
                      f"<b>Stato:</b> Prodotto Verificato</p>")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(info)
        btn = QPushButton("Chiudi")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)


class MainWindow(QMainWindow):
    """Interfaccia principale dell'applicazione SFTP."""

    def __init__(self) -> None:
        super().__init__()
        self.sftp_manager = SftpManager()
        self.current_lang = "it"
        self._init_ui()
        self._load_config()

        # Avvio controllo aggiornamenti silenzioso
        QThread.msleep(500)
        self._check_for_updates(silent=True)

    def _init_ui(self) -> None:
        """Inizializza gli elementi grafici."""
        self.setWindowTitle(f"PyExplorer Pro v{VERSION} - {AUTHOR}")
        self.setMinimumSize(900, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Menu Bar ---
        self._create_menu_bar()

        # --- Pannello di Connessione ---
        conn_group = QFrame()
        conn_group.setFrameShape(QFrame.Shape.StyledPanel)
        conn_layout = QHBoxLayout(conn_group)

        self.txt_host = QLineEdit()
        self.txt_host.setPlaceholderText("IP Host (es. 192.168.1.10)")
        self.txt_user = QLineEdit()
        self.txt_user.setPlaceholderText("Username")
        self.txt_pass = QLineEdit()
        self.txt_pass.setPlaceholderText("Password")
        self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)

        self.btn_connect = QPushButton("Connetti")
        self.btn_connect.setStyleSheet("background-color: #2ecc71; color: white; font-weight: bold;")
        self.btn_connect.clicked.connect(self._toggle_connection)

        conn_layout.addWidget(self.txt_host)
        conn_layout.addWidget(self.txt_user)
        conn_layout.addWidget(self.txt_pass)
        conn_layout.addWidget(self.btn_connect)
        main_layout.addWidget(conn_group)

        # --- Navigazione Percorso ---
        path_layout = QHBoxLayout()
        self.lbl_path = QLabel("Percorso: /")
        self.lbl_path.setStyleSheet("font-family: Consolas; font-weight: bold;")
        path_layout.addWidget(self.lbl_path)

        self.btn_upload = QPushButton("Carica File")
        self.btn_upload.setEnabled(False)
        self.btn_upload.clicked.connect(self._upload_file)
        path_layout.addWidget(self.btn_upload)
        main_layout.addLayout(path_layout)

        # --- Lista File ---
        self.file_list = QListWidget()
        self.file_list.setFont(QFont("Segoe UI", 10))
        self.file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._show_context_menu)
        main_layout.addWidget(self.file_list)

        # --- Footer con Pulsante Uscita ---
        footer_layout = QHBoxLayout()
        btn_exit = QPushButton("Esci dal Programma")
        btn_exit.setFixedWidth(200)
        btn_exit.setStyleSheet("background-color: #e74c3c; color: white; padding: 5px;")
        btn_exit.clicked.connect(self.close)
        footer_layout.addStretch()
        footer_layout.addWidget(btn_exit)
        main_layout.addLayout(footer_layout)

    def _create_menu_bar(self) -> None:
        """Crea la barra dei menu."""
        nav = self.menuBar()

        # Menu Aiuto
        help_menu = nav.addMenu("Aiuto")

        action_guide = QAction("Guida", self)
        action_guide.triggered.connect(lambda: GuideDialog(self).exec())
        help_menu.addAction(action_guide)

        action_update = QAction("Verifica Aggiornamenti", self)
        action_update.triggered.connect(lambda: self._check_for_updates(silent=False))
        help_menu.addAction(action_update)

        help_menu.addSeparator()

        action_info = QAction("Info", self)
        action_info.triggered.connect(lambda: InfoDialog(self).exec())
        help_menu.addAction(action_info)

    def _check_for_updates(self, silent: bool = True) -> None:
        """Avvia la verifica degli aggiornamenti."""
        self.update_thread = UpdateWorker()
        self.update_thread.finished.connect(lambda a, v, url: self._on_update_result(a, v, url, silent))
        self.update_thread.start()

    def _on_update_result(self, available: bool, version: str, url: str, silent: bool) -> None:
        if available:
            reply = QMessageBox.question(self, "Aggiornamento Disponibile",
                                       f"Versione v{version} disponibile. Scaricare?")
            if reply == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(url))
        elif not silent:
            QMessageBox.information(self, "Aggiornato", "Il software è già all'ultima versione.")

    def _toggle_connection(self) -> None:
        """Gestisce il login/logout."""
        if self.btn_connect.text() == "Connetti":
            host = self.txt_host.text().strip()
            user = self.txt_user.text().strip()
            psw = self.txt_pass.text()

            try:
                if self.sftp_manager.connect(host, user, psw):
                    self.btn_connect.setText("Disconnetti")
                    self.btn_connect.setStyleSheet("background-color: #f39c12; color: white;")
                    self.btn_upload.setEnabled(True)
                    self._save_config(host, user, psw)
                    self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Errore", str(e))
        else:
            self.sftp_manager.disconnect()
            self.btn_connect.setText("Connetti")
            self.btn_connect.setStyleSheet("background-color: #2ecc71; color: white;")
            self.btn_upload.setEnabled(False)
            self.file_list.clear()

    def refresh_list(self) -> None:
        """Aggiorna la visualizzazione dei file remoti."""
        try:
            self.file_list.clear()
            self.lbl_path.setText(f"Percorso: {self.sftp_manager.current_remote_path}")

            # Aggiunta elemento per tornare indietro
            if self.sftp_manager.current_remote_path != "/":
                self.file_list.addItem(QListWidgetItem("📁 .."))

            items = self.sftp_manager.list_dir(self.sftp_manager.current_remote_path)

            # Ordina: prima cartelle, poi file
            items.sort(key=lambda x: (not stat.S_ISDIR(x.st_mode), x.filename.lower()))

            for item in items:
                prefix = "📁 " if stat.S_ISDIR(item.st_mode) else "📄 "
                self.file_list.addItem(QListWidgetItem(f"{prefix}{item.filename}"))
        except Exception as e:
            QMessageBox.warning(self, "Errore Lista", f"Impossibile leggere i file: {e}")

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        """Gestisce il doppio click sugli elementi."""
        name = item.text()[3:]

        if "📁" in item.text():
            if name == "..":
                self.sftp_manager.current_remote_path = posixpath.dirname(self.sftp_manager.current_remote_path)
            else:
                self.sftp_manager.current_remote_path = posixpath.join(self.sftp_manager.current_remote_path, name)
            self.refresh_list()
        else:
            self._download_and_open(name)

    def _download_and_open(self, filename: str) -> None:
        """Scarica un file in locale e lo apre con l'app di sistema."""
        try:
            remote_path = posixpath.join(self.sftp_manager.current_remote_path, filename)
            local_path = os.path.join(tempfile.gettempdir(), filename)

            self.sftp_manager.download(remote_path, local_path)

            if platform.system() == "Windows":
                os.startfile(local_path)
            elif platform.system() == "Darwin":
                subprocess.call(["open", local_path])
            else:
                subprocess.call(["xdg-open", local_path])
        except Exception as e:
            QMessageBox.warning(self, "Errore Apertura", str(e))

    def _upload_file(self) -> None:
        """Seleziona e carica un file."""
        local_path, _ = QFileDialog.getOpenFileName(self, "Seleziona file da caricare")
        if local_path:
            try:
                name = os.path.basename(local_path)
                remote_path = posixpath.join(self.sftp_manager.current_remote_path, name)
                self.sftp_manager.upload(local_path, remote_path)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Errore Caricamento", str(e))

    def _show_context_menu(self, position: QPoint) -> None:
        """Menu contestuale per eliminazione."""
        item = self.file_list.itemAt(position)
        if not item or ".." in item.text():
            return

        menu = QMenu()
        action_del = QAction("Elimina", self)
        action_del.triggered.connect(lambda: self._delete_item(item))
        menu.addAction(action_del)
        menu.exec(self.file_list.mapToGlobal(position))

    def _delete_item(self, item: QListWidgetItem) -> None:
        name = item.text()[3:]
        is_dir = "📁" in item.text()
        path = posixpath.join(self.sftp_manager.current_remote_path, name)

        confirm = QMessageBox.question(self, "Conferma", f"Eliminare {name}?")
        if confirm == QMessageBox.StandardButton.Yes:
            try:
                self.sftp_manager.delete(path, is_dir)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Errore Eliminazione", str(e))

    def _save_config(self, host: str, user: str, psw: str) -> None:
        """Salva i dati di connessione crittografati o in JSON semplice."""
        config = {"host": host, "user": user, "pass": psw}
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)

    def _load_config(self) -> None:
        """Carica l'ultima connessione effettuata."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    config = json.load(f)
                    self.txt_host.setText(config.get("host", ""))
                    self.txt_user.setText(config.get("user", ""))
                    self.txt_pass.setText(config.get("pass", ""))
            except Exception: pass

    def closeEvent(self, event: Any) -> None:
        """Assicura la disconnessione alla chiusura."""
        self.sftp_manager.disconnect()
        event.accept()


# ==========================================
# AVVIO APPLICAZIONE
# ==========================================

def main() -> None:
    """Entry point del programma."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # Inizializza la finestra principale
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()