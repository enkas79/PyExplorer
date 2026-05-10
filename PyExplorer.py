"""
Modulo Principale: PyExplorer - Pro.
Gestore file SFTP avanzato per Raspberry Pi e server Linux basato su PyQt6.

Autore: Enrico Martini
Versione: 1.5.0
"""

import os
import json
import stat
import tempfile
import posixpath
import sys
import requests
import datetime
import platform
from typing import Optional, Any

import paramiko
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QPushButton,
    QLineEdit, QListWidget, QWidget, QMessageBox, QFileDialog, QLabel,
    QFrame, QMenu, QListWidgetItem, QDialog, QTextBrowser, QDialogButtonBox,
    QInputDialog, QPlainTextEdit, QSplitter
)
from PyQt6.QtGui import QAction, QFont, QDesktopServices, QIcon
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QUrl

import utils

# --- CONFIGURAZIONE ---
GITHUB_REPO: str = "enkas79/PyExplorer"
AUTHOR: str = "Enrico Martini"
VERSION: str = "1.5.3"
CONFIG_FILE: str = "connessioni_raspberry.json"

# ==========================================
# LOGICA DI BUSINESS (MODEL)
# ==========================================

class SftpManager:
    """Gestore delle operazioni SFTP."""
    def __init__(self) -> None:
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.sftp_client: Optional[paramiko.SFTPClient] = None
        self.current_remote_path: str = "/"

    def connect(self, host: str, user: str, psw: str) -> bool:
        self.ssh_client = paramiko.SSHClient()
        self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        self.ssh_client.connect(hostname=host, username=user, password=psw, timeout=10)
        self.sftp_client = self.ssh_client.open_sftp()
        self.current_remote_path = self.sftp_client.normalize('.')
        return True

    def disconnect(self) -> None:
        if self.sftp_client: self.sftp_client.close()
        if self.ssh_client: self.ssh_client.close()

    def list_dir(self, path: str) -> list[paramiko.SFTPAttributes]:
        if not self.sftp_client: raise ConnectionError("Client non connesso.")
        return self.sftp_client.listdir_attr(path)

    def get_info(self, path: str) -> paramiko.SFTPAttributes:
        return self.sftp_client.stat(path)

    def upload(self, local: str, remote: str) -> None:
        self.sftp_client.put(local, remote)

    def download(self, remote: str, local: str) -> None:
        self.sftp_client.get(remote, local)

    def download_batch(self, names: list[str], remote_dir: str, target_dir: str) -> None:
        for n in names:
            self.download(posixpath.join(remote_dir, n), os.path.join(target_dir, n))

    def read_text_file(self, path: str) -> str:
        with self.sftp_client.open(path, 'r') as f:
            return f.read().decode('utf-8', errors='replace')

    def write_text_file(self, path: str, content: str) -> None:
        with self.sftp_client.open(path, 'w') as f:
            f.write(content.encode('utf-8'))

    def delete(self, path: str, is_dir: bool = False) -> None:
        self.sftp_client.rmdir(path) if is_dir else self.sftp_client.remove(path)

    def rename(self, old: str, new: str) -> None:
        self.sftp_client.rename(old, new)

    def mkdir(self, path: str) -> None:
        self.sftp_client.mkdir(path)


class ProfileManager:
    """Gestore persistenza profili di connessione con migrazione automatica."""

    @staticmethod
    def load() -> dict:
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    data = json.load(f)

                    # Verifica retrocompatibilità: vecchio formato v1.4.0
                    # Se "host" è presente come stringa nel root, è il vecchio file.
                    if "host" in data and isinstance(data["host"], str):
                        # Crea un profilo di default e migra i dati
                        migrated_data = {"Profilo Migrato": data}
                        # Salva immediatamente nel nuovo formato
                        ProfileManager.save(migrated_data)
                        return migrated_data

                    return data
            except Exception:
                return {}
        return {}

    @staticmethod
    def save(profiles: dict) -> None:
        with open(CONFIG_FILE, "w") as f:
            json.dump(profiles, f, indent=4)


# ==========================================
# COMPONENTI UI
# ==========================================

class EditorDialog(QDialog):
    def __init__(self, filename: str, content: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Editor Remoto: {filename}")
        self.setMinimumSize(850, 600)
        layout = QVBoxLayout(self)
        self.editor = QPlainTextEdit()
        self.editor.setPlainText(content)
        self.editor.setFont(QFont("Consolas" if platform.system() == "Windows" else "Monospace", 11))
        layout.addWidget(self.editor)
        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept); btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_content(self) -> str: return self.editor.toPlainText()


class UpdateWorker(QThread):
    finished = pyqtSignal(bool, str, str)
    def run(self) -> None:
        try:
            r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", timeout=5)
            if r.status_code == 200:
                data = r.json()
                v = data.get('tag_name', '').replace('v', '')
                url = next((a['browser_download_url'] for a in data.get('assets', []) if '.exe' in a['name'] or '.deb' in a['name']), "")
                self.finished.emit(v > VERSION, v, url)
        except: pass


# ==========================================
# MAIN WINDOW
# ==========================================

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.sftp_manager = SftpManager()
        self.profiles = ProfileManager.load()
        self.full_list_cache: list[QListWidgetItem] = []
        self._init_ui()
        self._refresh_profile_list()
        self._check_for_updates(silent=True)

    def _init_ui(self) -> None:
        self.setWindowTitle(f"PyExplorer Pro v{VERSION}")
        self.setMinimumSize(1100, 800)
        self.setStyleSheet("""
            QMainWindow { background-color: #f0f2f5; }
            QFrame#Sidebar { background-color: #2c3e50; border-right: 1px solid #bdc3c7; }
            QListWidget#ProfileList { background: transparent; border: none; color: white; font-size: 13px; }
            QLineEdit { padding: 6px; border: 1px solid #ccc; border-radius: 4px; }
            QPushButton#Primary { background-color: #27ae60; color: white; font-weight: bold; border-radius: 4px; padding: 8px; }
            QPushButton#Secondary { background-color: #2980b9; color: white; border-radius: 4px; padding: 5px; }
            QLabel#Title { color: #ecf0f1; font-weight: bold; padding: 10px; font-size: 14px; }
        """)

        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0); main_layout.setSpacing(0)

        # Sidebar
        sidebar = QFrame(); sidebar.setObjectName("Sidebar"); sidebar.setFixedWidth(240)
        side_layout = QVBoxLayout(sidebar)
        lbl_p = QLabel("DISPOSITIVI SALVATI"); lbl_p.setObjectName("Title")
        side_layout.addWidget(lbl_p)
        self.profile_list = QListWidget(); self.profile_list.setObjectName("ProfileList")
        self.profile_list.itemClicked.connect(self._load_selected_profile)
        side_layout.addWidget(self.profile_list)
        btn_new = QPushButton("+ Nuovo Profilo"); btn_new.clicked.connect(self._clear_conn_fields)
        side_layout.addWidget(btn_new)
        main_layout.addWidget(sidebar)

        # Work Area
        work_area = QWidget()
        work_layout = QVBoxLayout(work_area)

        # Conn Panel
        conn_group = QFrame(); conn_group.setFrameShape(QFrame.Shape.StyledPanel)
        cl = QHBoxLayout(conn_group)
        self.txt_alias = QLineEdit(); self.txt_alias.setPlaceholderText("Alias (es. Pi4)")
        self.txt_host = QLineEdit(); self.txt_host.setPlaceholderText("Host/IP")
        self.txt_user = QLineEdit(); self.txt_user.setPlaceholderText("User")
        self.txt_pass = QLineEdit(); self.txt_pass.setPlaceholderText("Pass"); self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.btn_save = QPushButton("Salva"); self.btn_save.clicked.connect(self._save_profile)
        self.btn_conn = QPushButton("Connetti"); self.btn_conn.setObjectName("Primary"); self.btn_conn.clicked.connect(self._toggle_connection)

        for w in [self.txt_alias, self.txt_host, self.txt_user, self.txt_pass, self.btn_save, self.btn_conn]: cl.addWidget(w)
        work_layout.addWidget(conn_group)

        # Browser
        nav_l = QHBoxLayout()
        self.txt_path = QLineEdit("/"); self.txt_path.returnPressed.connect(self._jump_to_path)
        self.txt_search = QLineEdit(); self.txt_search.setPlaceholderText("Cerca...")
        self.txt_search.textChanged.connect(self._filter_list)
        nav_l.addWidget(QLabel("Percorso:")); nav_l.addWidget(self.txt_path, 4); nav_l.addWidget(self.txt_search, 1)
        work_layout.addLayout(nav_l)

        self.file_list = QListWidget(); self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._show_context_menu)
        work_layout.addWidget(self.file_list)

        # Actions
        act_l = QHBoxLayout()
        self.btn_up = QPushButton("Carica File"); self.btn_up.setEnabled(False); self.btn_up.clicked.connect(self._upload_file)
        self.btn_mk = QPushButton("Nuova Cartella"); self.btn_mk.setEnabled(False); self.btn_mk.clicked.connect(self._create_directory)
        btn_exit = QPushButton("Esci"); btn_exit.setStyleSheet("background: #c0392b; color: white;"); btn_exit.clicked.connect(self.close)
        act_l.addWidget(self.btn_up); act_l.addWidget(self.btn_mk); act_l.addStretch(); act_l.addWidget(btn_exit)
        work_layout.addLayout(act_l)

        main_layout.addWidget(work_area)
        self._create_menu_bar()

    def _create_menu_bar(self) -> None:
        """Crea la barra dei menu principale dell'applicazione."""
        m = self.menuBar().addMenu("Opzioni")

        # Azione: Update
        a_upd = QAction("Controlla Aggiornamenti", self)
        a_upd.triggered.connect(lambda: self._check_for_updates(False))
        m.addAction(a_upd)

        # Azione: Guida
        a_guida = QAction("Guida", self)
        a_guida.triggered.connect(
            lambda: QMessageBox.information(
                self,
                "Guida",
                "Usa la sidebar per i profili.\nDoppio click per navigare."
            )
        )
        m.addAction(a_guida)

    def _refresh_profile_list(self) -> None:
        self.profile_list.clear()
        for alias in self.profiles.keys(): self.profile_list.addItem(alias)

    def _load_selected_profile(self, item: QListWidgetItem) -> None:
        p = self.profiles.get(item.text(), {})
        self.txt_alias.setText(item.text()); self.txt_host.setText(p.get("host", ""))
        self.txt_user.setText(p.get("user", "")); self.txt_pass.setText(p.get("pass", ""))

    def _save_profile(self) -> None:
        alias = self.txt_alias.text().strip()
        if not alias: return
        self.profiles[alias] = {"host": self.txt_host.text(), "user": self.txt_user.text(), "pass": self.txt_pass.text()}
        ProfileManager.save(self.profiles); self._refresh_profile_list()

    def _clear_conn_fields(self) -> None:
        for w in [self.txt_alias, self.txt_host, self.txt_user, self.txt_pass]: w.clear()

    def _toggle_connection(self) -> None:
        if self.btn_conn.text() == "Connetti":
            try:
                if self.sftp_manager.connect(self.txt_host.text(), self.txt_user.text(), self.txt_pass.text()):
                    self.btn_conn.setText("Disconnetti"); self.btn_conn.setStyleSheet("background: #e67e22; color: white;")
                    self.btn_up.setEnabled(True); self.btn_mk.setEnabled(True); self.refresh_list()
            except Exception as e: QMessageBox.critical(self, "Errore", str(e))
        else:
            self.sftp_manager.disconnect(); self.btn_conn.setText("Connetti")
            self.btn_conn.setStyleSheet("background: #27ae60; color: white;")
            self.btn_up.setEnabled(False); self.btn_mk.setEnabled(False); self.file_list.clear()

    def refresh_list(self) -> None:
        try:
            self.file_list.clear(); self.full_list_cache = []
            path = self.sftp_manager.current_remote_path
            self.txt_path.setText(path)
            if path != "/":
                item = QListWidgetItem("📁 .."); item.setData(Qt.ItemDataRole.UserRole, "..")
                self.file_list.addItem(item)
            items = self.sftp_manager.list_dir(path)
            items.sort(key=lambda x: (not stat.S_ISDIR(x.st_mode), x.filename.lower()))
            for i in items:
                prefix = "📁 " if stat.S_ISDIR(i.st_mode) else "📄 "
                li = QListWidgetItem(f"{prefix}{i.filename} [{utils.format_permissions(i.st_mode)}]")
                li.setData(Qt.ItemDataRole.UserRole, i.filename)
                self.file_list.addItem(li); self.full_list_cache.append(li)
        except Exception as e: QMessageBox.warning(self, "Errore", str(e))

    def _filter_list(self, text: str) -> None:
        q = text.lower()
        self.file_list.clear()
        for i in self.full_list_cache:
            if q in i.data(Qt.ItemDataRole.UserRole).lower(): self.file_list.addItem(QListWidgetItem(i))

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if "📁" in item.text():
            self.sftp_manager.current_remote_path = posixpath.dirname(self.sftp_manager.current_remote_path) if name == ".." else posixpath.join(self.sftp_manager.current_remote_path, name)
            self.refresh_list()
        else:
            self._download_and_open(name)

    def _download_and_open(self, name: str) -> None:
        local = os.path.join(tempfile.gettempdir(), name)
        self.sftp_manager.download(posixpath.join(self.sftp_manager.current_remote_path, name), local)
        utils.open_local_path(local)

    def _show_context_menu(self, pos: QPoint) -> None:
        sel = [i for i in self.file_list.selectedItems() if i.data(Qt.ItemDataRole.UserRole) != ".."]
        if not sel: return
        menu = QMenu()
        if len(sel) == 1:
            name = sel[0].data(Qt.ItemDataRole.UserRole)
            if "📄" in sel[0].text():
                menu.addAction("Edita (Remoto)", lambda: self._edit_remote(name))
            menu.addAction("Rinomina", lambda: self._rename_item(name))
        menu.addAction(f"Scarica ({len(sel)})", self._download_selected)
        menu.addAction(f"Elimina ({len(sel)})", self._delete_selected)
        menu.exec(self.file_list.mapToGlobal(pos))

    def _edit_remote(self, name: str) -> None:
        p = posixpath.join(self.sftp_manager.current_remote_path, name)
        d = EditorDialog(name, self.sftp_manager.read_text_file(p), self)
        if d.exec() == QDialog.DialogCode.Accepted:
            self.sftp_manager.write_text_file(p, d.get_content())
            QMessageBox.information(self, "Ok", "Salvato.")

    def _upload_file(self) -> None:
        fs, _ = QFileDialog.getOpenFileNames(self, "Carica")
        for f in fs: self.sftp_manager.upload(f, posixpath.join(self.sftp_manager.current_remote_path, os.path.basename(f)))
        self.refresh_list()

    def _create_directory(self) -> None:
        n, ok = QInputDialog.getText(self, "Nuova Cartella", "Nome:")
        if ok and n: self.sftp_manager.mkdir(posixpath.join(self.sftp_manager.current_remote_path, n)); self.refresh_list()

    def _delete_selected(self) -> None:
        items = [i for i in self.file_list.selectedItems() if i.data(Qt.ItemDataRole.UserRole) != ".."]
        if items and QMessageBox.question(self, "Conferma", f"Eliminare {len(items)} elementi?") == QMessageBox.StandardButton.Yes:
            try:
                for i in items:
                    target_path = posixpath.join(self.sftp_manager.current_remote_path, i.data(Qt.ItemDataRole.UserRole))
                    is_directory = "📁" in i.text()
                    self.sftp_manager.delete(target_path, is_directory)
                self.refresh_list()
            except Exception as e:
                # Cattura l'errore e avvisa l'utente senza far crashare il software
                msg = (f"Impossibile completare l'eliminazione.\n"
                       f"Dettagli errore: {e}\n\n"
                       f"Nota: tramite SFTP non è possibile eliminare cartelle che contengono file "
                       f"oppure potresti non avere i permessi di scrittura in questo percorso.")
                QMessageBox.critical(self, "Errore di Eliminazione", msg)

    def _download_selected(self) -> None:
        names = [i.data(Qt.ItemDataRole.UserRole) for i in self.file_list.selectedItems() if i.data(Qt.ItemDataRole.UserRole) != ".."]
        t = QFileDialog.getExistingDirectory(self, "Salva in...")
        if t: self.sftp_manager.download_batch(names, self.sftp_manager.current_remote_path, t); QMessageBox.information(self, "Ok", "Fatto.")

    def _jump_to_path(self) -> None:
        self.sftp_manager.current_remote_path = self.txt_path.text(); self.refresh_list()

    def _rename_item(self, old: str) -> None:
        n, ok = QInputDialog.getText(self, "Rinomina", "Nuovo nome:", text=old)
        if ok and n: self.sftp_manager.rename(posixpath.join(self.sftp_manager.current_remote_path, old), posixpath.join(self.sftp_manager.current_remote_path, n)); self.refresh_list()

    def _check_for_updates(self, silent: bool) -> None:
        self.w = UpdateWorker(); self.w.finished.connect(lambda a,v,u: self._on_upd(a,v,u,silent)); self.w.start()

    def _on_upd(self, av: bool, v: str, u: str, s: bool) -> None:
        if av and QMessageBox.question(self, "Update", f"v{v} disponibile. Scaricare?") == QMessageBox.StandardButton.Yes: QDesktopServices.openUrl(QUrl(u))
        elif not s: QMessageBox.information(self, "Update", "Sei all'ultima versione.")

    def closeEvent(self, e) -> None:
        self.sftp_manager.disconnect(); e.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion")
    w = MainWindow(); w.show(); sys.exit(app.exec())