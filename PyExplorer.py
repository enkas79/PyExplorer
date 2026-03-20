"""
PyExplorer - Pro
Gestore file SFTP per Raspberry Pi con interfaccia in PyQt6.
Rispetta i principi OOP, PEP 8, Type Hints e Separazione delle Responsabilità.
"""

import os
import json
import stat
import tempfile
import platform
import subprocess
import posixpath
import socket
from typing import Dict, List, Optional, Tuple, Any

import paramiko
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QListWidget, QWidget, QMessageBox,
                             QFileDialog, QLabel, QFrame, QMenu, QListWidgetItem)
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt, QPoint

# Costanti
CONFIG_FILE = "connessioni_raspberry.json"
VERSION = "1.0.4"
AUTHOR = "Enrico Martini"


class ConfigManager:
    """
    Classe responsabile della gestione dei dati di configurazione locali (salvataggio e caricamento connessioni).
    """

    def __init__(self, config_path: str = CONFIG_FILE) -> None:
        """
        Inizializza il manager della configurazione.

        Args:
            config_path (str): Il percorso del file di configurazione JSON.
        """
        self.config_path: str = config_path

    def load_connections(self) -> Dict[str, Dict[str, str]]:
        """
        Carica le connessioni salvate dal file JSON.

        Returns:
            Dict[str, Dict[str, str]]: Dizionario contenente i profili salvati.
        """
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                print(f"Errore nel caricamento del file di configurazione: {e}")
                return {}
        return {}

    def save_connections(self, connections: Dict[str, Dict[str, str]]) -> bool:
        """
        Salva le connessioni nel file JSON locale.

        Args:
            connections (Dict[str, Dict[str, str]]): I profili da salvare.

        Returns:
            bool: True se il salvataggio ha successo, False altrimenti.
        """
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(connections, f, indent=4)
            return True
        except OSError as e:
            print(f"Errore nel salvataggio della configurazione: {e}")
            return False


class SFTPManager:
    """
    Classe responsabile della logica di business e di rete (connessione SSH/SFTP e operazioni sui file).
    """

    def __init__(self) -> None:
        self.ssh_client: Optional[paramiko.SSHClient] = None
        self.sftp_client: Optional[paramiko.SFTPClient] = None
        self.current_remote_path: str = "/home"

    def connect(self, host: str, user: str, password: str) -> Tuple[bool, str]:
        """
        Stabilisce una connessione SSH/SFTP con l'host remoto.

        Args:
            host (str): Indirizzo IP o hostname.
            user (str): Nome utente SSH.
            password (str): Password SSH.

        Returns:
            Tuple[bool, str]: (Successo, Messaggio di errore se applicabile)
        """
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(host, username=user, password=password, timeout=10)
            self.sftp_client = self.ssh_client.open_sftp()
            return True, ""
        except paramiko.AuthenticationException:
            return False, "Autenticazione fallita. Controlla utente e password."
        except (paramiko.SSHException, socket.error) as e:
            return False, f"Errore di connessione: {str(e)}"

    def disconnect(self) -> None:
        """Chiude le connessioni SFTP e SSH attive."""
        if self.sftp_client:
            self.sftp_client.close()
        if self.ssh_client:
            self.ssh_client.close()

    def is_directory(self, remote_path: str) -> bool:
        """Controlla se il percorso remoto specificato è una directory."""
        if not self.sftp_client:
            return False
        try:
            file_stat = self.sftp_client.stat(remote_path)
            return stat.S_ISDIR(file_stat.st_mode)
        except IOError:
            return False

    def list_directory(self) -> List[paramiko.sftp_attr.SFTPAttributes]:
        """Restituisce il contenuto della directory remota corrente."""
        if not self.sftp_client:
            return []
        try:
            items = self.sftp_client.listdir_attr(self.current_remote_path)
            # Ordina: prima le cartelle, poi i file, in ordine alfabetico
            items.sort(key=lambda x: (not stat.S_ISDIR(x.st_mode), x.filename.lower()))
            return items
        except IOError as e:
            print(f"Errore nella lettura della directory: {e}")
            return []

    def go_up(self) -> None:
        """Naviga alla directory padre."""
        if self.current_remote_path != "/":
            self.current_remote_path = posixpath.dirname(self.current_remote_path) or "/"

    def download_file(self, remote_path: str, local_path: str) -> bool:
        """Scarica un file dal server remoto al disco locale."""
        if not self.sftp_client:
            return False
        try:
            self.sftp_client.get(remote_path, local_path)
            return True
        except IOError as e:
            print(f"Errore nel download: {e}")
            return False

    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """Carica un file dal disco locale al server remoto."""
        if not self.sftp_client:
            return False
        try:
            self.sftp_client.put(local_path, remote_path)
            return True
        except IOError as e:
            print(f"Errore nell'upload: {e}")
            return False

    def delete_item(self, remote_path: str, is_dir: bool) -> bool:
        """Elimina un file o una directory vuota dal server remoto."""
        if not self.sftp_client:
            return False
        try:
            if is_dir:
                self.sftp_client.rmdir(remote_path)
            else:
                self.sftp_client.remove(remote_path)
            return True
        except IOError as e:
            print(f"Errore durante l'eliminazione: {e}")
            return False


class PyExplorerApp(QMainWindow):
    """
    Classe principale dell'Interfaccia Grafica PyQt6.
    Gestisce la UI e coordina ConfigManager e SFTPManager.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("PyExplorer - Pro")
        self.setGeometry(100, 100, 1150, 650)
        self.setWindowIcon(QIcon("icon.png"))

        # Inizializzazione dei moduli logici (Separazione delle Responsabilità)
        self.config_manager = ConfigManager()
        self.sftp_manager = SFTPManager()
        self.saved_connections: Dict[str, Dict[str, str]] = self.config_manager.load_connections()

        self.current_lang: str = "it"
        self._init_translations()

        self.init_ui()
        self.create_menu_bar()
        self.retranslate_ui()

    def _init_translations(self) -> None:
        """Inizializza il dizionario delle traduzioni."""
        self.texts: Dict[str, Dict[str, str]] = {
            "it": {
                "nome": "Nome:", "host": "Host:", "user": "Utente:", "pass": "Pass:",
                "salva": "💾 Salva", "connetti": "⚡ Connetti", "dispositivi": "<b>Dispositivi:</b>",
                "elimina_disp": "🗑️ Elimina", "su": "⬅ Su", "esci": "🚪 Esci",
                "info": "Info", "lingua": "Lingua", "aiuto": "Aiuto",
                "percorso": "Percorso:", "pronto": "Pronto.", "connesso": "Connesso.",
                "apri": "👁️ Apri file", "scarica": "⬇️ Scarica", "elimina_file": "❌ Elimina",
                "carica": "⬆️ Carica file qui", "aggiorna": "🔄 Aggiorna",
                "err_conn": "Connessione fallita", "conf_del": "Eliminare definitivamente?",
                "err_del": "Impossibile eliminare l'elemento."
            },
            "en": {
                "nome": "Name:", "host": "Host:", "user": "User:", "pass": "Pass:",
                "salva": "💾 Save", "connetti": "⚡ Connect", "dispositivi": "<b>Devices:</b>",
                "elimina_disp": "🗑️ Delete", "su": "⬅ Up", "esci": "🚪 Exit",
                "info": "Info", "lingua": "Language", "aiuto": "Help",
                "percorso": "Path:", "pronto": "Ready.", "connesso": "Connected.",
                "apri": "👁️ Open file", "scarica": "⬇️ Download", "elimina_file": "❌ Delete",
                "carica": "⬆️ Upload file here", "aggiorna": "🔄 Refresh",
                "err_conn": "Connection failed", "conf_del": "Delete permanently?",
                "err_del": "Unable to delete item."
            }
        }

    def init_ui(self) -> None:
        """Inizializza l'interfaccia grafica e i suoi widget."""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout_principale = QVBoxLayout(central_widget)

        # --- Toolbar Superiore ---
        toolbar_layout = QHBoxLayout()
        self.label_nome = QLabel()
        self.alias_input = QLineEdit()
        self.label_host = QLabel("Host:")
        self.host_input = QLineEdit()
        self.host_input.setPlaceholderText("IP")
        self.label_user = QLabel()
        self.user_input = QLineEdit()
        self.label_pass = QLabel()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.EchoMode.Password)

        self.btn_save = QPushButton()
        self.btn_save.clicked.connect(self.save_connection)
        self.btn_connect = QPushButton()
        self.btn_connect.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")
        self.btn_connect.clicked.connect(self.connect_to_server)

        toolbar_layout.addWidget(self.label_nome)
        toolbar_layout.addWidget(self.alias_input)
        toolbar_layout.addWidget(self.label_host)
        toolbar_layout.addWidget(self.host_input)
        toolbar_layout.addWidget(self.label_user)
        toolbar_layout.addWidget(self.user_input)
        toolbar_layout.addWidget(self.label_pass)
        toolbar_layout.addWidget(self.pass_input)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_connect)
        layout_principale.addLayout(toolbar_layout)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout_principale.addWidget(line)

        # --- Corpo Centrale ---
        content_layout = QHBoxLayout()

        # Sidebar
        sidebar_layout = QVBoxLayout()
        self.label_devices = QLabel()
        sidebar_layout.addWidget(self.label_devices)
        self.devices_list = QListWidget()
        self.devices_list.setFixedWidth(180)
        self.devices_list.itemClicked.connect(self.load_selected_device)
        self.refresh_device_list()
        sidebar_layout.addWidget(self.devices_list)

        self.btn_delete_disp = QPushButton()
        self.btn_delete_disp.setStyleSheet("color: #C62828;")
        self.btn_delete_disp.clicked.connect(self.delete_connection)
        sidebar_layout.addWidget(self.btn_delete_disp)
        content_layout.addLayout(sidebar_layout)

        # Explorer
        explorer_layout = QVBoxLayout()
        nav_layout = QHBoxLayout()
        self.btn_back = QPushButton()
        self.btn_back.clicked.connect(self.go_to_parent_dir)
        self.path_label = QLabel()
        nav_layout.addWidget(self.btn_back)
        nav_layout.addWidget(self.path_label)
        nav_layout.addStretch()
        explorer_layout.addLayout(nav_layout)

        self.file_list = QListWidget()
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        self.file_list.itemDoubleClicked.connect(self.handle_item_double_click)
        explorer_layout.addWidget(self.file_list)

        content_layout.addLayout(explorer_layout)
        layout_principale.addLayout(content_layout)

        # --- Bottom Row ---
        bottom_row = QHBoxLayout()
        self.status_bar = QLabel()
        bottom_row.addWidget(self.status_bar)
        bottom_row.addStretch()
        self.btn_exit = QPushButton()
        self.btn_exit.clicked.connect(self.close)
        self.btn_exit.setStyleSheet("background-color: #C62828; color: white; font-weight: bold;")
        bottom_row.addWidget(self.btn_exit)
        layout_principale.addLayout(bottom_row)

    def create_menu_bar(self) -> None:
        """Crea la barra dei menu."""
        menubar = self.menuBar()
        self.menu_lingua = menubar.addMenu("Lingua")
        langs = [("Italiano", "it"), ("English", "en")]
        for name, code in langs:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, c=code: self.change_language(c))
            self.menu_lingua.addAction(action)

        self.menu_aiuto = menubar.addMenu("Aiuto")
        self.info_action = QAction("Info", self)
        self.info_action.triggered.connect(self.show_info)
        self.menu_aiuto.addAction(self.info_action)

    def change_language(self, code: str) -> None:
        """Cambia la lingua dell'interfaccia."""
        if code in self.texts:
            self.current_lang = code
            self.retranslate_ui()

    def retranslate_ui(self) -> None:
        """Aggiorna i testi dell'interfaccia nella lingua corrente."""
        t = self.texts[self.current_lang]
        self.label_nome.setText(t["nome"])
        self.label_user.setText(t["user"])
        self.label_pass.setText(t["pass"])
        self.btn_save.setText(t["salva"])
        self.btn_connect.setText(t["connetti"])
        self.label_devices.setText(t["dispositivi"])
        self.btn_delete_disp.setText(t["elimina_disp"])
        self.btn_back.setText(t["su"])
        self.btn_exit.setText(t["esci"])
        self.status_bar.setText(t["pronto"])
        self.path_label.setText(f"{t['percorso']} {self.sftp_manager.current_remote_path}")
        self.menu_lingua.setTitle(t["lingua"])
        self.menu_aiuto.setTitle(t["aiuto"])
        self.info_action.setText(t["info"])

    def show_info(self) -> None:
        """Mostra il menu Info con i dettagli dell'autore e della versione."""
        msg = f"Autore: {AUTHOR}\nVersione: {VERSION}"
        QMessageBox.information(self, "Info PyExplorer", msg)

    # --- Gestione Connessioni ---

    def save_connection(self) -> None:
        """Salva i dati di connessione correnti tramite il ConfigManager."""
        alias = self.alias_input.text().strip()
        if not alias:
            return

        self.saved_connections[alias] = {
            "host": self.host_input.text(),
            "user": self.user_input.text(),
            "password": self.pass_input.text(),
            "alias": alias
        }
        self.config_manager.save_connections(self.saved_connections)
        self.refresh_device_list()

    def refresh_device_list(self) -> None:
        """Aggiorna la lista dei dispositivi salvati nella UI."""
        self.devices_list.clear()
        for alias in self.saved_connections.keys():
            self.devices_list.addItem(alias)

    def load_selected_device(self, item: QListWidgetItem) -> None:
        """Carica i parametri di connessione del dispositivo selezionato."""
        data = self.saved_connections.get(item.text(), {})
        self.alias_input.setText(data.get("alias", ""))
        self.host_input.setText(data.get("host", ""))
        self.user_input.setText(data.get("user", ""))
        self.pass_input.setText(data.get("password", ""))

    def delete_connection(self) -> None:
        """Elimina il profilo di connessione selezionato."""
        item = self.devices_list.currentItem()
        if item:
            alias = item.text()
            if alias in self.saved_connections:
                del self.saved_connections[alias]
                self.config_manager.save_connections(self.saved_connections)
                self.refresh_device_list()

    # --- Operazioni SFTP ---

    def connect_to_server(self) -> None:
        """Avvia la connessione sfruttando SFTPManager e aggiorna la UI."""
        host = self.host_input.text().strip()
        user = self.user_input.text().strip()
        password = self.pass_input.text()

        if not host or not user:
            return

        success, error_msg = self.sftp_manager.connect(host, user, password)
        if success:
            self.refresh_file_list()
            self.status_bar.setText(self.texts[self.current_lang]["connesso"])
        else:
            QMessageBox.critical(self, "Error", f"{self.texts[self.current_lang]['err_conn']}\n{error_msg}")

    def refresh_file_list(self) -> None:
        """Aggiorna la visualizzazione dei file nella directory remota corrente."""
        self.file_list.clear()
        items = self.sftp_manager.list_directory()

        for attr in items:
            prefix = "📁 " if stat.S_ISDIR(attr.st_mode) else "📄 "
            self.file_list.addItem(prefix + attr.filename)

        t = self.texts[self.current_lang]
        self.path_label.setText(f"{t['percorso']} {self.sftp_manager.current_remote_path}")

    def go_to_parent_dir(self) -> None:
        """Sale di un livello nella gerarchia delle directory remote."""
        self.sftp_manager.go_up()
        self.refresh_file_list()

    def handle_item_double_click(self, item: QListWidgetItem) -> None:
        """Gestisce il doppio clic su un elemento della lista file."""
        filename = item.text().replace("📁 ", "").replace("📄 ", "")
        remote_path = posixpath.join(self.sftp_manager.current_remote_path, filename)

        if self.sftp_manager.is_directory(remote_path):
            self.sftp_manager.current_remote_path = remote_path
            self.refresh_file_list()
        else:
            self.open_remote_file(remote_path, filename)

    def open_remote_file(self, remote_path: str, filename: str) -> None:
        """Scarica un file in una cartella temporanea e lo apre con l'app di sistema."""
        temp_dir = tempfile.gettempdir()
        local_path = os.path.join(temp_dir, filename)

        if self.sftp_manager.download_file(remote_path, local_path):
            try:
                if platform.system() == "Windows":
                    os.startfile(local_path)
                else:
                    cmd = "open" if platform.system() == "Darwin" else "xdg-open"
                    subprocess.call((cmd, local_path))
            except OSError as e:
                print(f"Errore nell'apertura del file locale: {e}")

    def show_context_menu(self, pos: QPoint) -> None:
        """Mostra il menu contestuale al clic destro sulla lista file."""
        item = self.file_list.itemAt(pos)
        t = self.texts[self.current_lang]
        menu = QMenu()

        if item:
            act_open = menu.addAction(t["apri"])
            act_down = menu.addAction(t["scarica"])
            act_del = menu.addAction(t["elimina_file"])
            action = menu.exec(self.file_list.mapToGlobal(pos))

            if action == act_open:
                self.handle_item_double_click(item)
            elif action == act_down:
                filename = item.text().replace("📁 ", "").replace("📄 ", "")
                remote_path = posixpath.join(self.sftp_manager.current_remote_path, filename)
                self.start_download(remote_path, filename)
            elif action == act_del:
                self.delete_remote_item(item)
        else:
            act_up = menu.addAction(t["carica"])
            act_ref = menu.addAction(t["aggiorna"])
            action = menu.exec(self.file_list.mapToGlobal(pos))

            if action == act_up:
                self.start_upload()
            elif action == act_ref:
                self.refresh_file_list()

    def start_download(self, remote_path: str, default_filename: str) -> None:
        """Gestisce il processo di download con finestra di dialogo."""
        local_path, _ = QFileDialog.getSaveFileName(self, "Save File", default_filename)
        if local_path:
            self.sftp_manager.download_file(remote_path, local_path)

    def start_upload(self) -> None:
        """Gestisce il processo di upload con finestra di dialogo."""
        local_path, _ = QFileDialog.getOpenFileName(self, "Select File to Upload")
        if local_path:
            filename = os.path.basename(local_path)
            remote_path = posixpath.join(self.sftp_manager.current_remote_path, filename)
            if self.sftp_manager.upload_file(local_path, remote_path):
                self.refresh_file_list()

    def delete_remote_item(self, item: QListWidgetItem) -> None:
        """Chiede conferma ed elimina un file o una directory remota."""
        t = self.texts[self.current_lang]
        filename = item.text().replace("📁 ", "").replace("📄 ", "")
        remote_path = posixpath.join(self.sftp_manager.current_remote_path, filename)
        is_dir = "📁" in item.text()

        reply = QMessageBox.question(self, "PyExplorer", f"{t['conf_del']} ({filename})")
        if reply == QMessageBox.StandardButton.Yes:
            success = self.sftp_manager.delete_item(remote_path, is_dir)
            if success:
                self.refresh_file_list()
            else:
                QMessageBox.warning(self, "Error", t.get("err_del", "Error"))

    def closeEvent(self, event: Any) -> None:
        """Intercetta la chiusura dell'applicazione per disconnettere i client in sicurezza."""
        self.sftp_manager.disconnect()
        super().closeEvent(event)


if __name__ == "__main__":
    app = QApplication([])
    window = PyExplorerApp()
    window.show()
    app.exec()
