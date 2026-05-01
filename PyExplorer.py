"""
Modulo Principale: PyExplorer - Pro.
Gestore file SFTP avanzato per Raspberry Pi e server Linux basato su PyQt6.

Autore: Enrico Martini
Versione: 1.2.1
"""

import os
import json
import stat
import tempfile
import posixpath
import sys
import requests
import datetime
from typing import List, Optional, Any

import paramiko
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QListWidget, QWidget, QMessageBox, QFileDialog, QLabel,
    QFrame, QMenu, QListWidgetItem, QDialog, QTextBrowser, QDialogButtonBox,
    QInputDialog
)
from PyQt6.QtGui import QAction, QFont, QDesktopServices
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QUrl

import utils

# --- CONFIGURAZIONE ---
GITHUB_REPO: str = "enkas79/PyExplorer"
AUTHOR: str = "Enrico Martini"
VERSION: str = "1.2.1"
CONFIG_FILE: str = "connessioni_raspberry.json"


# ==========================================
# LOGICA DI BUSINESS (MODEL)
# ==========================================

class SftpManager:
    """
    Gestore delle operazioni SFTP.
    Propaga le eccezioni al chiamante (UI) senza catturarle internamente.
    """

    def __init__(self) -> None:
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.sftp_client: Optional[paramiko.SFTPClient] = None
        self.current_remote_path: str = "/"

    def connect(self, host: str, user: str, psw: str) -> bool:
        """Stabilisce la connessione SSH/SFTP."""
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(hostname=host, username=user, password=psw, timeout=10)
        self.sftp_client = self.ssh_client.open_sftp()
        self.current_remote_path = self.sftp_client.normalize('.')
        return True

    def disconnect(self) -> None:
        """Chiude i client attivi."""
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()

    def list_dir(self, path: str) -> List[paramiko.SFTPAttributes]:
        """Elenca gli attributi dei file nel percorso specificato."""
        if not self.sftp_client:
            raise ConnectionError("Client SFTP non inizializzato.")
        return self.sftp_client.listdir_attr(path)

    def get_info(self, path: str) -> paramiko.SFTPAttributes:
        """Recupera i metadati di un file o cartella."""
        if not self.sftp_client:
            raise ConnectionError("Client SFTP non inizializzato.")
        return self.sftp_client.stat(path)

    def upload(self, local: str, remote: str) -> None:
        self.sftp_client.put(local, remote)

    def download(self, remote: str, local: str) -> None:
        self.sftp_client.get(remote, local)

    def delete(self, path: str, is_dir: bool = False) -> None:
        if is_dir:
            self.sftp_client.rmdir(path)
        else:
            self.sftp_client.remove(path)

    def rename(self, old_path: str, new_path: str) -> None:
        self.sftp_client.rename(old_path, new_path)

    def mkdir(self, path: str) -> None:
        self.sftp_client.mkdir(path)


# ==========================================
# GESTIONE AGGIORNAMENTI (CONTROLLER)
# ==========================================

class UpdateWorker(QThread):
    """Worker asincrono per il controllo versioni su GitHub."""
    finished = pyqtSignal(bool, str, str)
    error = pyqtSignal(str)

    def run(self) -> None:
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
        try:
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_ver = data.get('tag_name', '').replace('v', '')
                download_url = ""
                for asset in data.get('assets', []):
                    if any(asset['name'].endswith(ext) for ext in ['.exe', '.deb', '.zip']):
                        download_url = asset['browser_download_url']
                        break
                self.finished.emit(latest_ver > VERSION, latest_ver, download_url)
        except Exception as e:
            self.error.emit(str(e))


# ==========================================
# INTERFACCIA UTENTE (UI)
# ==========================================

class GuideDialog(QDialog):
    """Finestra di documentazione rapida."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Guida - PyExplorer")
        self.setMinimumSize(500, 350)
        layout = QVBoxLayout(self)
        browser = QTextBrowser()
        browser.setHtml(f"""
            <h2>PyExplorer Pro: Istruzioni</h2>
            <ul>
                <li><b>Navigazione:</b> Doppio click sulle cartelle. Digita il percorso e premi Invio per saltare.</li>
                <li><b>Ricerca:</b> Usa la barra 'Filtra' per cercare file nella vista corrente.</li>
                <li><b>Azioni:</b> Tasto destro sugli elementi per Rinomina, Elimina o Proprietà.</li>
                <li><b>Download:</b> Doppio click su un file per scaricarlo e aprirlo localmente.</li>
            </ul>
        """)
        layout.addWidget(browser)
        btn = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        btn.accepted.connect(self.accept)
        layout.addWidget(btn)


class InfoDialog(QDialog):
    """Finestra 'About' del software."""
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Informazioni")
        self.setFixedSize(300, 200)
        layout = QVBoxLayout(self)
        label = QLabel(f"<h3>PyExplorer Pro</h3>"
                       f"<p><b>Autore:</b> {AUTHOR}<br>"
                       f"<b>Versione:</b> {VERSION}<br>"
                       f"<b>Framework:</b> PyQt6</p>")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(label)
        btn = QPushButton("Chiudi")
        btn.clicked.connect(self.accept)
        layout.addWidget(btn)


class MainWindow(QMainWindow):
    """Finestra principale con gestione degli eventi (Confine UI)."""

    def __init__(self) -> None:
        super().__init__()
        self.sftp_manager = SftpManager()
        self.full_list_cache: List[QListWidgetItem] = []
        self._init_ui()
        self._load_config()
        self._check_for_updates(silent=True)

    def _init_ui(self) -> None:
        self.setWindowTitle(f"PyExplorer Pro v{VERSION} - {AUTHOR}")
        self.setMinimumSize(1000, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self._create_menu_bar()

        # Sezione Connessione
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

        for widget in [self.txt_host, self.txt_user, self.txt_pass, self.btn_connect]:
            conn_layout.addWidget(widget)
        main_layout.addWidget(conn_group)

        # Barra Navigazione e Ricerca
        nav_layout = QHBoxLayout()
        self.txt_path = QLineEdit("/")
        self.txt_path.returnPressed.connect(self._jump_to_path)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Filtra lista...")
        self.txt_search.textChanged.connect(self._filter_list)

        nav_layout.addWidget(QLabel("Percorso:"))
        nav_layout.addWidget(self.txt_path, stretch=3)
        nav_layout.addWidget(QLabel("Cerca:"))
        nav_layout.addWidget(self.txt_search, stretch=1)
        main_layout.addLayout(nav_layout)

        # Bottoni Azione
        btn_layout = QHBoxLayout()
        self.btn_mkdir = QPushButton("Nuova Cartella")
        self.btn_upload = QPushButton("Carica File")
        self.btn_mkdir.setEnabled(False)
        self.btn_upload.setEnabled(False)
        self.btn_mkdir.clicked.connect(self._create_directory)
        self.btn_upload.clicked.connect(self._upload_file)
        btn_layout.addWidget(self.btn_mkdir)
        btn_layout.addWidget(self.btn_upload)
        main_layout.addLayout(btn_layout)

        # File List
        self.file_list = QListWidget()
        self.file_list.setFont(QFont("Segoe UI", 10))
        self.file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._show_context_menu)
        main_layout.addWidget(self.file_list)

        # Footer
        footer = QHBoxLayout()
        btn_exit = QPushButton("Esci")
        btn_exit.setFixedWidth(120)
        btn_exit.setStyleSheet("background-color: #e74c3c; color: white;")
        btn_exit.clicked.connect(self.close)
        footer.addStretch()
        footer.addWidget(btn_exit)
        main_layout.addLayout(footer)

    def _create_menu_bar(self) -> None:
        menu = self.menuBar()
        help_menu = menu.addMenu("Aiuto")

        act_guide = QAction("Guida", self)
        act_guide.triggered.connect(lambda: GuideDialog(self).exec())
        help_menu.addAction(act_guide)

        act_info = QAction("Informazioni", self)
        act_info.triggered.connect(lambda: InfoDialog(self).exec())
        help_menu.addAction(act_info)

    def _toggle_connection(self) -> None:
        """Handler UI per la connessione (Confine Eccezioni)."""
        if self.btn_connect.text() == "Connetti":
            try:
                host = self.txt_host.text().strip()
                user = self.txt_user.text().strip()
                psw = self.txt_pass.text()

                if self.sftp_manager.connect(host, user, psw):
                    self.btn_connect.setText("Disconnetti")
                    self.btn_connect.setStyleSheet("background-color: #f39c12; color: white;")
                    self.btn_upload.setEnabled(True)
                    self.btn_mkdir.setEnabled(True)
                    self._save_config(host, user, psw)
                    self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Errore Connessione", f"Impossibile connettersi:\n{str(e)}")
        else:
            self.sftp_manager.disconnect()
            self.btn_connect.setText("Connetti")
            self.btn_connect.setStyleSheet("background-color: #2ecc71; color: white;")
            self.btn_upload.setEnabled(False)
            self.btn_mkdir.setEnabled(False)
            self.file_list.clear()

    def refresh_list(self) -> None:
        """Aggiorna la visualizzazione dei file remoti."""
        try:
            self.file_list.clear()
            self.full_list_cache = []
            path = self.sftp_manager.current_remote_path
            self.txt_path.setText(path)

            if path != "/":
                back = QListWidgetItem("📁 ..")
                back.setData(Qt.ItemDataRole.UserRole, "..")
                self.file_list.addItem(back)

            items = self.sftp_manager.list_dir(path)
            items.sort(key=lambda x: (not stat.S_ISDIR(x.st_mode), x.filename.lower()))

            for item in items:
                prefix = "📁 " if stat.S_ISDIR(item.st_mode) else "📄 "
                perms = utils.format_permissions(item.st_mode)
                label = f"{prefix}{item.filename}  [{perms}]"
                list_item = QListWidgetItem(label)
                list_item.setData(Qt.ItemDataRole.UserRole, item.filename)
                self.file_list.addItem(list_item)
                self.full_list_cache.append(list_item)

            self.txt_search.clear()
        except Exception as e:
            QMessageBox.warning(self, "Errore Navigazione", f"Errore lettura directory:\n{str(e)}")

    def _filter_list(self, text: str) -> None:
        """Filtra la lista in base alla cache locale."""
        query = text.lower()
        self.file_list.clear()

        if self.sftp_manager.current_remote_path != "/":
            back = QListWidgetItem("📁 ..")
            back.setData(Qt.ItemDataRole.UserRole, "..")
            self.file_list.addItem(back)

        for item in self.full_list_cache:
            if query in item.data(Qt.ItemDataRole.UserRole).lower():
                self.file_list.addItem(QListWidgetItem(item))

    def _show_context_menu(self, pos: QPoint) -> None:
        item = self.file_list.itemAt(pos)
        if not item or item.data(Qt.ItemDataRole.UserRole) == "..":
            return

        name = item.data(Qt.ItemDataRole.UserRole)
        is_dir = "📁" in item.text()
        menu = QMenu()

        act_prop = QAction("Proprietà", self)
        act_prop.triggered.connect(lambda: self._show_properties(name))
        menu.addAction(act_prop)

        menu.addSeparator()

        act_ren = QAction("Rinomina", self)
        act_ren.triggered.connect(lambda: self._rename_item(name))
        menu.addAction(act_ren)

        act_del = QAction("Elimina", self)
        act_del.triggered.connect(lambda: self._delete_item(name, is_dir))
        menu.addAction(act_del)

        menu.exec(self.file_list.mapToGlobal(pos))

    def _show_properties(self, name: str) -> None:
        try:
            p = posixpath.join(self.sftp_manager.current_remote_path, name)
            info = self.sftp_manager.get_info(p)
            mod_time = datetime.datetime.fromtimestamp(info.st_mtime).strftime('%Y-%m-%d %H:%M:%S')

            msg = (f"Nome: {name}\n"
                   f"Dimensione: {utils.format_size(info.st_size)}\n"
                   f"Ultima Modifica: {mod_time}\n"
                   f"Permessi: {utils.format_permissions(info.st_mode)}")
            QMessageBox.information(self, "Proprietà", msg)
        except Exception as e:
            QMessageBox.warning(self, "Errore", f"Impossibile leggere proprietà: {e}")

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if "📁" in item.text():
            if name == "..":
                self.sftp_manager.current_remote_path = posixpath.dirname(self.sftp_manager.current_remote_path)
            else:
                self.sftp_manager.current_remote_path = posixpath.join(self.sftp_manager.current_remote_path, name)
            self.refresh_list()
        else:
            self._download_and_open(name)

    def _download_and_open(self, name: str) -> None:
        try:
            remote = posixpath.join(self.sftp_manager.current_remote_path, name)
            local = os.path.join(tempfile.gettempdir(), name)
            self.sftp_manager.download(remote, local)
            utils.open_local_path(local)
        except Exception as e:
            QMessageBox.critical(self, "Errore File", f"Errore durante l'apertura:\n{str(e)}")

    def _jump_to_path(self) -> None:
        target = self.txt_path.text().strip()
        if target:
            try:
                self.sftp_manager.list_dir(target)
                self.sftp_manager.current_remote_path = target
                self.refresh_list()
            except Exception as e:
                QMessageBox.warning(self, "Errore Percorso", f"Percorso non valido:\n{str(e)}")
                self.txt_path.setText(self.sftp_manager.current_remote_path)

    def _create_directory(self) -> None:
        name, ok = QInputDialog.getText(self, "Nuova Cartella", "Nome:")
        if ok and name:
            try:
                self.sftp_manager.mkdir(posixpath.join(self.sftp_manager.current_remote_path, name))
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Errore", str(e))

    def _rename_item(self, old: str) -> None:
        new, ok = QInputDialog.getText(self, "Rinomina", "Nuovo nome:", text=old)
        if ok and new and new != old:
            try:
                old_p = posixpath.join(self.sftp_manager.current_remote_path, old)
                new_p = posixpath.join(self.sftp_manager.current_remote_path, new)
                self.sftp_manager.rename(old_p, new_p)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Errore", str(e))

    def _delete_item(self, name: str, is_dir: bool) -> None:
        if QMessageBox.question(self, "Conferma", f"Eliminare {name}?") == QMessageBox.StandardButton.Yes:
            try:
                p = posixpath.join(self.sftp_manager.current_remote_path, name)
                self.sftp_manager.delete(p, is_dir)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Errore", str(e))

    def _upload_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Seleziona File")
        if path:
            try:
                remote = posixpath.join(self.sftp_manager.current_remote_path, os.path.basename(path))
                self.sftp_manager.upload(path, remote)
                self.refresh_list()
            except Exception as e:
                QMessageBox.critical(self, "Errore Caricamento", str(e))

    def _save_config(self, host: str, user: str, psw: str) -> None:
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump({"host": host, "user": user, "pass": psw}, f)
        except Exception: pass

    def _load_config(self) -> None:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    c = json.load(f)
                    self.txt_host.setText(c.get("host", ""))
                    self.txt_user.setText(c.get("user", ""))
                    self.txt_pass.setText(c.get("pass", ""))
            except Exception: pass

    def _check_for_updates(self, silent: bool) -> None:
        self.worker = UpdateWorker()
        self.worker.finished.connect(lambda a, v, u: self._on_update_res(a, v, u, silent))
        self.worker.start()

    def _on_update_res(self, available: bool, ver: str, url: str, silent: bool) -> None:
        if available:
            if QMessageBox.question(self, "Aggiornamento", f"v{ver} disponibile. Scaricare?") == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl(url))
        elif not silent:
            QMessageBox.information(self, "Update", "Sei già all'ultima versione.")

    def closeEvent(self, event: Any) -> None:
        self.sftp_manager.disconnect()
        event.accept()


# ==========================================
# ENTRY POINT
# ==========================================

def main() -> None:
    """Inizializza e avvia l'applicazione."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()