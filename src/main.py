"""
Modulo Principale: PyExplorer - Pro.
Gestore file SFTP avanzato per Raspberry Pi e server Linux basato su PyQt6.

Autore: Enrico Martini
Versione: letta dinamicamente da version.txt
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
    QInputDialog, QPlainTextEdit, QSplitter, QProgressDialog, QStyle,
    QToolButton, QScrollArea, QSizePolicy
)
from PyQt6.QtGui import QAction, QFont, QDesktopServices, QIcon
from PyQt6.QtCore import Qt, QPoint, QThread, pyqtSignal, QUrl, QSize

import utils

# --- CONFIGURAZIONE ---
GITHUB_REPO: str = "enkas79/PyExplorer"
AUTHOR: str = "Enrico Martini"
CONFIG_FILE: str = "connessioni_raspberry.json"
ROLE_IS_DIR: int = Qt.ItemDataRole.UserRole + 1


def _base_dir() -> str:
    """Cartella base dell'applicazione: bundle PyInstaller oppure root del progetto (src/..)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


VERSION_FILE: str = os.path.join(_base_dir(), "version.txt")


def _read_version() -> str:
    """Legge dinamicamente la versione corrente da version.txt."""
    try:
        with open(VERSION_FILE, "r") as f:
            return f.read().strip()
    except Exception:
        return "0.0.0"


VERSION: str = _read_version()

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

    def upload(self, local: str, remote: str, callback=None) -> None:
        self.sftp_client.put(local, remote, callback=callback)

    def download(self, remote: str, local: str, callback=None) -> None:
        self.sftp_client.get(remote, local, callback=callback)

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


def _version_tuple(v: str) -> tuple[int, ...]:
    """Converte 'x.y.z' in tupla di interi per un confronto semver corretto."""
    parts = []
    for p in v.strip().split('.'):
        digits = ''.join(c for c in p if c.isdigit())
        parts.append(int(digits) if digits else 0)
    return tuple(parts)


class UpdateWorker(QThread):
    finished = pyqtSignal(bool, str, str, str)  # aggiornamento_disponibile, versione, url, errore

    def run(self) -> None:
        try:
            r = requests.get(f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest", timeout=5)
            if r.status_code == 200:
                data = r.json()
                v = data.get('tag_name', '').replace('v', '')
                url = next((a['browser_download_url'] for a in data.get('assets', []) if '.exe' in a['name'] or '.deb' in a['name']), "")
                self.finished.emit(_version_tuple(v) > _version_tuple(VERSION), v, url, "")
            else:
                self.finished.emit(False, "", "", f"Risposta inattesa dal server (HTTP {r.status_code}).")
        except Exception as e:
            self.finished.emit(False, "", "", str(e))


class TaskWorker(QThread):
    """Esegue in background una funzione senza argomenti (I/O SFTP, rete, ecc.)."""
    succeeded = pyqtSignal(object)
    failed = pyqtSignal(str)

    def __init__(self, fn, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.succeeded.emit(self._fn())
        except Exception as e:
            self.failed.emit(str(e))


class TransferWorker(QThread):
    """Esegue in background un trasferimento file riportando l'avanzamento."""
    progress = pyqtSignal(str, int)
    succeeded = pyqtSignal()
    failed = pyqtSignal(str)

    def __init__(self, fn, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self._fn(lambda label, pct: self.progress.emit(label, pct))
            self.succeeded.emit()
        except Exception as e:
            self.failed.emit(str(e))


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
        icon_path = os.path.join(_base_dir(), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        style = self.style()
        self.setStyleSheet("""
            QMainWindow { background-color: #f5f6fa; }
            QFrame#Sidebar { background-color: #1f2a38; border-right: 1px solid #10151c; }
            QListWidget#ProfileList { background: transparent; border: none; color: #ecf0f1; font-size: 13px; outline: none; }
            QListWidget#ProfileList::item { padding: 8px 12px; border-radius: 6px; margin: 2px 8px; }
            QListWidget#ProfileList::item:hover { background-color: #2c3e50; }
            QListWidget#ProfileList::item:selected { background-color: #2980b9; color: white; }
            QLabel#Title { color: #ecf0f1; font-weight: 600; padding: 14px 12px 8px 12px; font-size: 12px; letter-spacing: 1px; }
            QFrame#ConnPanel { background: white; border: 1px solid #e1e4e8; border-radius: 8px; }
            QLineEdit { padding: 7px 10px; border: 1px solid #d0d5dd; border-radius: 6px; background: white; }
            QLineEdit:focus { border: 1px solid #2980b9; }
            QPushButton { padding: 7px 14px; border-radius: 6px; border: none; background-color: #dfe4ea; }
            QPushButton:hover { background-color: #ced6e0; }
            QPushButton:disabled { background-color: #eceff3; color: #a8b0bb; }
            QPushButton#Primary { background-color: #27ae60; color: white; font-weight: 600; }
            QPushButton#Primary:hover { background-color: #219150; }
            QPushButton#Secondary { background-color: #2980b9; color: white; }
            QPushButton#Secondary:hover { background-color: #2574a9; }
            QPushButton#Danger { background-color: #c0392b; color: white; }
            QPushButton#Danger:hover { background-color: #a93226; }
            QListWidget { background: white; border: 1px solid #e1e4e8; border-radius: 6px; padding: 4px; outline: none; }
            QListWidget::item { padding: 6px 8px; border-radius: 4px; }
            QListWidget::item:hover { background-color: #eef2f7; }
            QListWidget::item:selected { background-color: #d6e9f8; color: #1a1a1a; }
            QToolButton { border: none; padding: 5px; border-radius: 5px; }
            QToolButton:hover { background-color: #e1e8ee; }
            QToolButton:disabled { color: #c2c9d1; }
            QScrollArea#BreadcrumbArea { border: none; background: white; }
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
        work_layout.setContentsMargins(16, 16, 16, 16); work_layout.setSpacing(10)

        # Conn Panel
        conn_group = QFrame(); conn_group.setObjectName("ConnPanel"); conn_group.setFrameShape(QFrame.Shape.StyledPanel)
        cl = QHBoxLayout(conn_group)
        self.txt_alias = QLineEdit(); self.txt_alias.setPlaceholderText("Alias (es. Pi4)")
        self.txt_host = QLineEdit(); self.txt_host.setPlaceholderText("Host/IP")
        self.txt_user = QLineEdit(); self.txt_user.setPlaceholderText("User")
        self.txt_pass = QLineEdit(); self.txt_pass.setPlaceholderText("Pass"); self.txt_pass.setEchoMode(QLineEdit.EchoMode.Password)
        self.btn_save = QPushButton("Salva"); self.btn_save.clicked.connect(self._save_profile)
        self.btn_conn = QPushButton("Connetti")
        self.btn_conn.setObjectName("Primary")
        self.btn_conn.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DriveNetIcon))
        self.btn_conn.clicked.connect(self._toggle_connection)

        for w in [self.txt_alias, self.txt_host, self.txt_user, self.txt_pass, self.btn_save, self.btn_conn]: cl.addWidget(w)
        work_layout.addWidget(conn_group)

        # Navigazione: pulsante "Su", breadcrumb cliccabile, modifica manuale, ricerca
        nav_l = QHBoxLayout()
        self.btn_up_dir = QToolButton()
        self.btn_up_dir.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogToParent))
        self.btn_up_dir.setToolTip("Cartella superiore")
        self.btn_up_dir.setEnabled(False)
        self.btn_up_dir.clicked.connect(self._go_up)
        nav_l.addWidget(self.btn_up_dir)

        self.breadcrumb_bar = QWidget()
        self.breadcrumb_layout = QHBoxLayout(self.breadcrumb_bar)
        self.breadcrumb_layout.setContentsMargins(6, 0, 6, 0); self.breadcrumb_layout.setSpacing(2)
        breadcrumb_scroll = QScrollArea(); breadcrumb_scroll.setObjectName("BreadcrumbArea")
        breadcrumb_scroll.setWidget(self.breadcrumb_bar); breadcrumb_scroll.setWidgetResizable(True)
        breadcrumb_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        breadcrumb_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        breadcrumb_scroll.setFixedHeight(36)
        nav_l.addWidget(breadcrumb_scroll, 4)

        self.btn_edit_path = QToolButton()
        self.btn_edit_path.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView))
        self.btn_edit_path.setToolTip("Vai a un percorso specifico")
        self.btn_edit_path.clicked.connect(self._edit_path_manually)
        nav_l.addWidget(self.btn_edit_path)

        self.txt_search = QLineEdit(); self.txt_search.setPlaceholderText("Cerca...")
        self.txt_search.textChanged.connect(self._filter_list)
        nav_l.addWidget(self.txt_search, 1)
        work_layout.addLayout(nav_l)

        self.file_list = QListWidget(); self.file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.file_list.setIconSize(QSize(20, 20))
        self.file_list.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self._show_context_menu)
        work_layout.addWidget(self.file_list)

        # Actions
        act_l = QHBoxLayout()
        self.btn_up = QPushButton("Carica File")
        self.btn_up.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_ArrowUp))
        self.btn_up.setEnabled(False); self.btn_up.clicked.connect(self._upload_file)
        self.btn_mk = QPushButton("Nuova Cartella")
        self.btn_mk.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.btn_mk.setEnabled(False); self.btn_mk.clicked.connect(self._create_directory)
        btn_exit = QPushButton("Esci")
        btn_exit.setObjectName("Danger")
        btn_exit.setIcon(style.standardIcon(QStyle.StandardPixmap.SP_DialogCloseButton))
        btn_exit.clicked.connect(self.close)
        act_l.addWidget(self.btn_up); act_l.addWidget(self.btn_mk); act_l.addStretch(); act_l.addWidget(btn_exit)
        work_layout.addLayout(act_l)

        main_layout.addWidget(work_area)
        self._create_menu_bar()
        self._set_breadcrumb("/")

    def _create_menu_bar(self) -> None:
        """Crea la barra dei menu principale dell'applicazione."""
        m = self.menuBar().addMenu("Aiuto")

        # Azione: Informazioni
        a_about = QAction("Informazioni", self)
        a_about.triggered.connect(self._show_about)
        m.addAction(a_about)

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

    def _show_about(self) -> None:
        QMessageBox.about(
            self,
            "Informazioni su PyExplorer Pro",
            f"<b>PyExplorer Pro</b><br>Versione: {VERSION}<br>Autore: {AUTHOR}"
        )

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

    def _run_async(self, fn, on_success=None, on_error=None, busy_text: str = "Operazione in corso...") -> None:
        """Esegue fn() in un QThread mostrando un dialogo di attesa indeterminato."""
        dlg = QProgressDialog(busy_text, None, 0, 0, self)
        dlg.setWindowTitle("Attendere")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.show()

        worker = TaskWorker(fn)
        self._bg_worker = worker  # mantiene viva la referenza finché il thread gira

        def _ok(result):
            dlg.close()
            if on_success: on_success(result)

        def _err(msg: str):
            dlg.close()
            (on_error or (lambda m: QMessageBox.critical(self, "Errore", m)))(msg)

        worker.succeeded.connect(_ok)
        worker.failed.connect(_err)
        worker.start()

    def _run_transfer(self, task_fn, on_done=None, on_error=None) -> None:
        """Esegue un trasferimento file in un QThread con progress bar determinata."""
        dlg = QProgressDialog("Preparazione...", None, 0, 100, self)
        dlg.setWindowTitle("Trasferimento in corso")
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setCancelButton(None)
        dlg.setMinimumDuration(0)
        dlg.setValue(0)
        dlg.show()

        worker = TransferWorker(task_fn)
        self._bg_worker = worker

        def _progress(label: str, pct: int):
            dlg.setLabelText(label); dlg.setValue(max(0, min(100, pct)))

        def _ok():
            dlg.close()
            if on_done: on_done()

        def _err(msg: str):
            dlg.close()
            (on_error or (lambda m: QMessageBox.critical(self, "Errore", f"Trasferimento fallito.\n{m}")))(msg)

        worker.progress.connect(_progress)
        worker.succeeded.connect(_ok)
        worker.failed.connect(_err)
        worker.start()

    def _toggle_connection(self) -> None:
        if self.btn_conn.text() == "Connetti":
            host, user, psw = self.txt_host.text(), self.txt_user.text(), self.txt_pass.text()

            def _do_connect():
                return self.sftp_manager.connect(host, user, psw)

            def _on_connected(_result):
                self.btn_conn.setText("Disconnetti"); self.btn_conn.setStyleSheet("background-color: #e67e22; color: white; font-weight: 600;")
                self.btn_up.setEnabled(True); self.btn_mk.setEnabled(True); self.refresh_list()

            self._run_async(_do_connect, on_success=_on_connected, busy_text="Connessione in corso...")
        else:
            self.sftp_manager.disconnect(); self.btn_conn.setText("Connetti")
            self.btn_conn.setStyleSheet("")
            self.btn_up.setEnabled(False); self.btn_mk.setEnabled(False); self.file_list.clear()
            self.btn_up_dir.setEnabled(False); self._set_breadcrumb("/")

    def refresh_list(self) -> None:
        path = self.sftp_manager.current_remote_path
        style = self.style()

        def _fetch():
            items = self.sftp_manager.list_dir(path)
            items.sort(key=lambda x: (not stat.S_ISDIR(x.st_mode), x.filename.lower()))
            return [(i.filename, stat.S_ISDIR(i.st_mode), utils.format_permissions(i.st_mode)) for i in items]

        def _on_ok(rows):
            self.file_list.clear(); self.full_list_cache = []
            self._set_breadcrumb(path)
            self.btn_up_dir.setEnabled(path != "/")
            if path != "/":
                item = QListWidgetItem(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogToParent), "..")
                item.setData(Qt.ItemDataRole.UserRole, ".."); item.setData(ROLE_IS_DIR, True)
                self.file_list.addItem(item)
            dir_icon = style.standardIcon(QStyle.StandardPixmap.SP_DirIcon)
            file_icon = style.standardIcon(QStyle.StandardPixmap.SP_FileIcon)
            for filename, is_dir, perms in rows:
                li = QListWidgetItem(dir_icon if is_dir else file_icon, f"{filename}   [{perms}]")
                li.setData(Qt.ItemDataRole.UserRole, filename); li.setData(ROLE_IS_DIR, is_dir)
                self.file_list.addItem(li); self.full_list_cache.append(li)

        self._run_async(_fetch, on_success=_on_ok,
                         on_error=lambda m: QMessageBox.warning(self, "Errore", m),
                         busy_text="Caricamento cartella...")

    def _set_breadcrumb(self, path: str) -> None:
        """Ricostruisce la barra di navigazione a segmenti cliccabili (breadcrumb)."""
        while self.breadcrumb_layout.count():
            child = self.breadcrumb_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()

        parts = [p for p in path.split("/") if p]

        def _crumb(label: str, target: str, is_last: bool) -> QToolButton:
            btn = QToolButton(); btn.setText(label); btn.setAutoRaise(True)
            if is_last: btn.setStyleSheet("font-weight: 600; color: #1a1a1a;")
            btn.clicked.connect(lambda: self._navigate_to(target))
            return btn

        self.breadcrumb_layout.addWidget(_crumb("/", "/", len(parts) == 0))
        cumulative = ""
        for idx, part in enumerate(parts):
            cumulative += "/" + part
            self.breadcrumb_layout.addWidget(QLabel("›"))
            self.breadcrumb_layout.addWidget(_crumb(part, cumulative, idx == len(parts) - 1))
        self.breadcrumb_layout.addStretch()

    def _navigate_to(self, path: str) -> None:
        self.sftp_manager.current_remote_path = path
        self.refresh_list()

    def _go_up(self) -> None:
        path = self.sftp_manager.current_remote_path
        if path != "/":
            self._navigate_to(posixpath.dirname(path) or "/")

    def _edit_path_manually(self) -> None:
        n, ok = QInputDialog.getText(self, "Vai al percorso", "Percorso:", text=self.sftp_manager.current_remote_path)
        if ok and n:
            self._navigate_to(n)

    def _filter_list(self, text: str) -> None:
        q = text.lower()
        self.file_list.clear()
        for i in self.full_list_cache:
            if q in i.data(Qt.ItemDataRole.UserRole).lower(): self.file_list.addItem(QListWidgetItem(i))

    def _on_item_double_clicked(self, item: QListWidgetItem) -> None:
        name = item.data(Qt.ItemDataRole.UserRole)
        if item.data(ROLE_IS_DIR):
            target = posixpath.dirname(self.sftp_manager.current_remote_path) if name == ".." else posixpath.join(self.sftp_manager.current_remote_path, name)
            self._navigate_to(target or "/")
        else:
            self._download_and_open(name)

    def _download_and_open(self, name: str) -> None:
        local = os.path.join(tempfile.gettempdir(), name)
        remote = posixpath.join(self.sftp_manager.current_remote_path, name)

        def _task(emit):
            def cb(done: int, size: int):
                emit(f"Scaricamento {name}", int(done * 100 / size) if size else 0)
            self.sftp_manager.download(remote, local, callback=cb)

        self._run_transfer(_task, on_done=lambda: utils.open_local_path(local),
                            on_error=lambda m: QMessageBox.critical(self, "Errore", f"Impossibile aprire il file.\n{m}"))

    def _show_context_menu(self, pos: QPoint) -> None:
        sel = [i for i in self.file_list.selectedItems() if i.data(Qt.ItemDataRole.UserRole) != ".."]
        if not sel: return
        style = self.style()
        menu = QMenu()
        if len(sel) == 1:
            name = sel[0].data(Qt.ItemDataRole.UserRole)
            if not sel[0].data(ROLE_IS_DIR):
                a = menu.addAction(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogContentsView), "Edita (Remoto)")
                a.triggered.connect(lambda: self._edit_remote(name))
            a = menu.addAction(style.standardIcon(QStyle.StandardPixmap.SP_FileDialogDetailedView), "Rinomina")
            a.triggered.connect(lambda: self._rename_item(name))
        a = menu.addAction(style.standardIcon(QStyle.StandardPixmap.SP_ArrowDown), f"Scarica ({len(sel)})")
        a.triggered.connect(self._download_selected)
        a = menu.addAction(style.standardIcon(QStyle.StandardPixmap.SP_TrashIcon), f"Elimina ({len(sel)})")
        a.triggered.connect(self._delete_selected)
        menu.exec(self.file_list.mapToGlobal(pos))

    def _edit_remote(self, name: str) -> None:
        p = posixpath.join(self.sftp_manager.current_remote_path, name)

        def _open_editor(content: str):
            d = EditorDialog(name, content, self)
            if d.exec() == QDialog.DialogCode.Accepted:
                new_content = d.get_content()
                self._run_async(
                    lambda: self.sftp_manager.write_text_file(p, new_content),
                    on_success=lambda _: QMessageBox.information(self, "Ok", "Salvato."),
                    on_error=lambda m: QMessageBox.critical(self, "Errore", f"Impossibile salvare il file.\n{m}"),
                    busy_text="Salvataggio in corso...")

        self._run_async(
            lambda: self.sftp_manager.read_text_file(p), on_success=_open_editor,
            on_error=lambda m: QMessageBox.critical(self, "Errore", f"Impossibile leggere il file.\n{m}"),
            busy_text="Apertura file...")

    def _upload_file(self) -> None:
        fs, _ = QFileDialog.getOpenFileNames(self, "Carica")
        if not fs: return
        remote_dir = self.sftp_manager.current_remote_path

        def _task(emit):
            total = len(fs)
            for idx, f in enumerate(fs, start=1):
                name = os.path.basename(f)

                def cb(done: int, size: int, idx=idx, name=name):
                    emit(f"Caricamento {name} ({idx}/{total})", int(done * 100 / size) if size else 0)

                self.sftp_manager.upload(f, posixpath.join(remote_dir, name), callback=cb)

        self._run_transfer(_task, on_done=self.refresh_list,
                            on_error=lambda m: QMessageBox.critical(self, "Errore", f"Impossibile completare il caricamento.\n{m}"))

    def _create_directory(self) -> None:
        n, ok = QInputDialog.getText(self, "Nuova Cartella", "Nome:")
        if ok and n:
            path = posixpath.join(self.sftp_manager.current_remote_path, n)
            self._run_async(
                lambda: self.sftp_manager.mkdir(path), on_success=lambda _: self.refresh_list(),
                on_error=lambda m: QMessageBox.critical(self, "Errore", f"Impossibile creare la cartella.\n{m}"),
                busy_text="Creazione cartella...")

    def _delete_selected(self) -> None:
        items = [i for i in self.file_list.selectedItems() if i.data(Qt.ItemDataRole.UserRole) != ".."]
        if not items: return
        if QMessageBox.question(self, "Conferma", f"Eliminare {len(items)} elementi?") != QMessageBox.StandardButton.Yes:
            return
        targets = [(posixpath.join(self.sftp_manager.current_remote_path, i.data(Qt.ItemDataRole.UserRole)), bool(i.data(ROLE_IS_DIR))) for i in items]

        def _do_delete():
            for path, is_dir in targets:
                self.sftp_manager.delete(path, is_dir)

        def _on_error(msg: str):
            # Avvisa l'utente senza far crashare il software
            full_msg = (f"Impossibile completare l'eliminazione.\n"
                        f"Dettagli errore: {msg}\n\n"
                        f"Nota: tramite SFTP non è possibile eliminare cartelle che contengono file "
                        f"oppure potresti non avere i permessi di scrittura in questo percorso.")
            QMessageBox.critical(self, "Errore di Eliminazione", full_msg)

        self._run_async(_do_delete, on_success=lambda _: self.refresh_list(), on_error=_on_error,
                         busy_text="Eliminazione in corso...")

    def _download_selected(self) -> None:
        names = [i.data(Qt.ItemDataRole.UserRole) for i in self.file_list.selectedItems() if i.data(Qt.ItemDataRole.UserRole) != ".."]
        if not names: return
        t = QFileDialog.getExistingDirectory(self, "Salva in...")
        if not t: return
        remote_dir = self.sftp_manager.current_remote_path

        def _task(emit):
            total = len(names)
            for idx, n in enumerate(names, start=1):
                def cb(done: int, size: int, idx=idx, n=n):
                    emit(f"Scaricamento {n} ({idx}/{total})", int(done * 100 / size) if size else 0)
                self.sftp_manager.download(posixpath.join(remote_dir, n), os.path.join(t, n), callback=cb)

        self._run_transfer(_task, on_done=lambda: QMessageBox.information(self, "Ok", "Fatto."),
                            on_error=lambda m: QMessageBox.critical(self, "Errore", f"Impossibile completare lo scaricamento.\n{m}"))

    def _rename_item(self, old: str) -> None:
        n, ok = QInputDialog.getText(self, "Rinomina", "Nuovo nome:", text=old)
        if ok and n:
            old_p = posixpath.join(self.sftp_manager.current_remote_path, old)
            new_p = posixpath.join(self.sftp_manager.current_remote_path, n)
            self._run_async(
                lambda: self.sftp_manager.rename(old_p, new_p), on_success=lambda _: self.refresh_list(),
                on_error=lambda m: QMessageBox.critical(self, "Errore", f"Impossibile rinominare l'elemento.\n{m}"),
                busy_text="Rinomina in corso...")

    def _check_for_updates(self, silent: bool) -> None:
        self.w = UpdateWorker(); self.w.finished.connect(lambda a,v,u,err: self._on_upd(a,v,u,err,silent)); self.w.start()

    def _on_upd(self, av: bool, v: str, u: str, err: str, s: bool) -> None:
        """
        Gestisce la risposta del controllo aggiornamenti.
        Se viene trovato un update, reindirizza l'utente alla sezione download del sito.
        """
        if err:
            if not s:
                QMessageBox.warning(self, "Update", f"Impossibile verificare gli aggiornamenti.\n{err}")
            return
        if av and QMessageBox.question(self, "Update", f"v{v} disponibile. Scaricare?") == QMessageBox.StandardButton.Yes:
            # Definiamo l'URL del tuo sito web
            sito_download = "https://mindnetwork.vip/download"

            # Apriamo il browser dell'utente direttamente sul tuo portale
            QDesktopServices.openUrl(QUrl(sito_download))
        elif not s:
            QMessageBox.information(self, "Update", "Sei all'ultima versione.")

    def closeEvent(self, e) -> None:
        self.sftp_manager.disconnect(); e.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setStyle("Fusion")
    w = MainWindow(); w.show(); sys.exit(app.exec())
