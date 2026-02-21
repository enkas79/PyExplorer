import os
import json
import paramiko
import stat
import tempfile
import platform
import subprocess
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QListWidget, QWidget, QMessageBox,
                             QFileDialog, QLabel, QFrame, QMenu)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt, QPoint
from PyQt6.QtGui import QIcon

CONFIG_FILE = "connessioni_raspberry.json"


class PyExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowIcon(QIcon("icon.png"))
        self.setWindowTitle("PyExplorer")
        self.setGeometry(100, 100, 1150, 650)

        # --- SISTEMA DI TRADUZIONE ---
        self.current_lang = "it"
        self.texts = {
            "it": {
                "nome": "Nome:", "host": "Host:", "user": "Utente:", "pass": "Pass:",
                "salva": "💾 Salva", "connetti": "⚡ Connetti", "dispositivi": "<b>Dispositivi:</b>",
                "elimina_disp": "🗑️ Elimina", "su": "⬅ Su", "esci": "🚪 Esci",
                "info": "Info", "lingua": "Lingua", "aiuto": "Aiuto",
                "percorso": "Percorso:", "pronto": "Pronto.", "connesso": "Connesso.",
                "apri": "👁️ Apri file", "scarica": "⬇️ Scarica", "elimina_file": "❌ Elimina",
                "carica": "⬆️ Carica file qui", "aggiorna": "🔄 Aggiorna",
                "msg_info": "Autore: Enrico Martini\nVersione: 1.0",
                "err_conn": "Connessione fallita", "conf_del": "Eliminare definitivamente?"
            },
            "en": {
                "nome": "Name:", "host": "Host:", "user": "User:", "pass": "Pass:",
                "salva": "💾 Save", "connetti": "⚡ Connect", "dispositivi": "<b>Devices:</b>",
                "elimina_disp": "🗑️ Delete", "su": "⬅ Up", "esci": "🚪 Exit",
                "info": "Info", "lingua": "Language", "aiuto": "Help",
                "percorso": "Path:", "pronto": "Ready.", "connesso": "Connected.",
                "apri": "👁️ Open file", "scarica": "⬇️ Download", "elimina_file": "❌ Delete",
                "carica": "⬆️ Upload file here", "aggiorna": "🔄 Refresh",
                "msg_info": "Author: Enrico Martini\nVersion: 1.0",
                "err_conn": "Connection failed", "conf_del": "Delete permanently?"
            },
            "de": {
                "nome": "Name:", "host": "Host:", "user": "Nutzer:", "pass": "Pass:",
                "salva": "💾 Speichern", "connetti": "⚡ Verbinden", "dispositivi": "<b>Geräte:</b>",
                "elimina_disp": "🗑️ Löschen", "su": "⬅ Hoch", "esci": "🚪 Beenden",
                "info": "Info", "lingua": "Sprache", "aiuto": "Hilfe",
                "percorso": "Pfad:", "pronto": "Bereit.", "connesso": "Verbunden.",
                "apri": "👁️ Datei öffnen", "scarica": "⬇️ Herunterladen", "elimina_file": "❌ Löschen",
                "carica": "⬆️ Datei hier hochladen", "aggiorna": "🔄 Aktualisieren",
                "msg_info": "Autor: Enrico Martini\nVersion: 1.0",
                "err_conn": "Verbindung fehlgeschlagen", "conf_del": "Dauerhaft löschen?"
            },
            "es": {
                "nome": "Nombre:", "host": "Host:", "user": "Usuario:", "pass": "Pass:",
                "salva": "💾 Guardar", "connetti": "⚡ Conectar", "dispositivi": "<b>Dispositivos:</b>",
                "elimina_disp": "🗑️ Eliminar", "su": "⬅ Subir", "esci": "🚪 Salir",
                "info": "Info", "lingua": "Idioma", "aiuto": "Ayuda",
                "percorso": "Ruta:", "pronto": "Listo.", "connesso": "Conectado.",
                "apri": "👁️ Abrir archivo", "scarica": "⬇️ Descargar", "elimina_file": "❌ Eliminar",
                "carica": "⬆️ Subir archivo aquí", "aggiorna": "🔄 Actualizar",
                "msg_info": "Autor: Enrico Martini\nVersión: 1.0",
                "err_conn": "Conexión fallida", "conf_del": "¿Eliminar permanentemente?"
            }
        }

        self.ssh_client = None
        self.sftp_client = None
        self.current_remote_path = "/home"
        self.saved_connections = self.load_connections()

        self.initUI()
        self.create_menu_bar()
        self.retranslate_ui()  # Applica la lingua iniziale

    def create_menu_bar(self):
        menubar = self.menuBar()

        # Menu Lingua
        self.menu_lingua = menubar.addMenu("Lingua")
        langs = [("Italiano", "it"), ("English", "en"), ("Deutsch", "de"), ("Español", "es")]
        for name, code in langs:
            action = QAction(name, self)
            action.triggered.connect(lambda checked, c=code: self.change_language(c))
            self.menu_lingua.addAction(action)

        # Menu Aiuto
        self.menu_aiuto = menubar.addMenu("Aiuto")
        self.info_action = QAction("Info", self)
        self.info_action.triggered.connect(self.show_info)
        self.menu_aiuto.addAction(self.info_action)

    def change_language(self, code):
        self.current_lang = code
        self.retranslate_ui()

    def retranslate_ui(self):
        """Aggiorna tutti i testi dell'interfaccia basandosi sulla lingua scelta."""
        t = self.texts[self.current_lang]

        # Labels e Button
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
        self.path_label.setText(f"{t['percorso']} {self.current_remote_path}")

        # Menu
        self.menu_lingua.setTitle(t["lingua"])
        self.menu_aiuto.setTitle(t["aiuto"])
        self.info_action.setText(t["info"])

    def show_info(self):
        t = self.texts[self.current_lang]
        QMessageBox.information(self, "PyExplorer", t["msg_info"])

    def initUI(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout_principale = QVBoxLayout(central_widget)

        # BARRA SUPERIORE
        toolbar_layout = QHBoxLayout()
        self.label_nome = QLabel()
        self.alias_input = QLineEdit()
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
        self.btn_connect.clicked.connect(self.connect_to_raspberry)

        toolbar_layout.addWidget(self.label_nome)
        toolbar_layout.addWidget(self.alias_input)
        toolbar_layout.addWidget(QLabel("Host:"))
        toolbar_layout.addWidget(self.host_input)
        toolbar_layout.addWidget(self.label_user)
        toolbar_layout.addWidget(self.user_input)
        toolbar_layout.addWidget(self.label_pass)
        toolbar_layout.addWidget(self.pass_input)
        toolbar_layout.addWidget(self.btn_save)
        toolbar_layout.addWidget(self.btn_connect)
        layout_principale.addLayout(toolbar_layout)

        layout_principale.addWidget(self.get_line())

        # CORPO CENTRALE
        content_layout = QHBoxLayout()
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

        explorer_layout = QVBoxLayout()
        nav_layout = QHBoxLayout()
        self.btn_back = QPushButton()
        self.btn_back.clicked.connect(self.go_to_parent)
        self.path_label = QLabel()
        nav_layout.addWidget(self.btn_back)
        nav_layout.addWidget(self.path_label)
        nav_layout.addStretch()
        explorer_layout.addLayout(nav_layout)

        self.file_list = QListWidget()
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        self.file_list.itemDoubleClicked.connect(self.handle_item_click)
        explorer_layout.addWidget(self.file_list)
        content_layout.addLayout(explorer_layout)
        layout_principale.addLayout(content_layout)

        # BARRA INFERIORE
        bottom_row = QHBoxLayout()
        self.status_bar = QLabel()
        bottom_row.addWidget(self.status_bar)
        bottom_row.addStretch()
        self.btn_exit = QPushButton()
        self.btn_exit.clicked.connect(self.close)
        self.btn_exit.setStyleSheet("background-color: #C62828; color: white;")
        bottom_row.addWidget(self.btn_exit)
        layout_principale.addLayout(bottom_row)

    def get_line(self):
        line = QFrame();
        line.setFrameShape(QFrame.Shape.HLine);
        line.setFrameShadow(QFrame.Shadow.Sunken)
        return line

    def show_context_menu(self, pos: QPoint):
        item = self.file_list.itemAt(pos)
        t = self.texts[self.current_lang]
        menu = QMenu()
        if item:
            act_open = menu.addAction(t["apri"])
            act_down = menu.addAction(t["scarica"])
            act_del = menu.addAction(t["elimina_file"])
            action = menu.exec(self.file_list.mapToGlobal(pos))
            if action == act_open:
                self.handle_item_click(item)
            elif action == act_down:
                rn = item.text().replace("📁 ", "").replace("📄 ", "")
                self.start_download(os.path.join(self.current_remote_path, rn), rn)
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

    # --- LOGICHE (Semplificate per brevità, invariate rispetto a prima) ---
    def handle_item_click(self, item):
        rn = item.text().replace("📁 ", "").replace("📄 ", "")
        rp = os.path.join(self.current_remote_path, rn)
        try:
            if stat.S_ISDIR(self.sftp_client.stat(rp).st_mode):
                self.current_remote_path = rp
                self.refresh_file_list()
            else:
                self.open_remote_file(rp, rn)
        except:
            pass

    def open_remote_file(self, rp, fn):
        try:
            tp = os.path.join(tempfile.gettempdir(), fn)
            self.sftp_client.get(rp, tp)
            if platform.system() == "Windows":
                os.startfile(tp)
            else:
                subprocess.call(("open" if platform.system() == "Darwin" else "xdg-open", tp))
        except:
            pass

    def start_upload(self):
        lp, _ = QFileDialog.getOpenFileName(self, "Select File")
        if lp: self.sftp_client.put(lp, os.path.join(self.current_remote_path,
                                                     os.path.basename(lp))); self.refresh_file_list()

    def delete_remote_item(self, item):
        t = self.texts[self.current_lang]
        rn = item.text().replace("📁 ", "").replace("📄 ", "")
        if QMessageBox.question(self, "PyExplorer", f"{t['conf_del']} ({rn})") == QMessageBox.StandardButton.Yes:
            try:
                if "📁" in item.text():
                    self.sftp_client.rmdir(os.path.join(self.current_remote_path, rn))
                else:
                    self.sftp_client.remove(os.path.join(self.current_remote_path, rn))
                self.refresh_file_list()
            except:
                pass

    def load_connections(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_connection(self):
        a = self.alias_input.text().strip()
        if not a: return
        self.saved_connections[a] = {"host": self.host_input.text(), "user": self.user_input.text(),
                                     "password": self.pass_input.text(), "alias": a}
        with open(CONFIG_FILE, "w") as f: json.dump(self.saved_connections, f, indent=4)
        self.refresh_device_list()

    def refresh_device_list(self):
        self.devices_list.clear()
        for a in self.saved_connections.keys(): self.devices_list.addItem(a)

    def load_selected_device(self, item):
        d = self.saved_connections.get(item.text(), {})
        self.alias_input.setText(d.get("alias", ""));
        self.host_input.setText(d.get("host", ""))
        self.user_input.setText(d.get("user", ""));
        self.pass_input.setText(d.get("password", ""))

    def delete_connection(self):
        i = self.devices_list.currentItem()
        if i: del self.saved_connections[i.text()]; self.save_connection(); self.refresh_device_list()

    def connect_to_raspberry(self):
        try:
            self.ssh_client = paramiko.SSHClient();
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self.host_input.text(), username=self.user_input.text(),
                                    password=self.pass_input.text())
            self.sftp_client = self.ssh_client.open_sftp();
            self.refresh_file_list()
            self.status_bar.setText(self.texts[self.current_lang]["connesso"])
        except:
            QMessageBox.critical(self, "Error", self.texts[self.current_lang]["err_conn"])

    def refresh_file_list(self):
        self.file_list.clear()
        try:
            it = self.sftp_client.listdir_attr(self.current_remote_path)
            it.sort(key=lambda x: (not stat.S_ISDIR(x.st_mode), x.filename.lower()))
            for a in it: self.file_list.addItem(("📁 " if stat.S_ISDIR(a.st_mode) else "📄 ") + a.filename)
            self.path_label.setText(f"{self.texts[self.current_lang]['percorso']} {self.current_remote_path}")
        except:
            pass

    def go_to_parent(self):
        if self.current_remote_path == "/": return
        self.current_remote_path = os.path.dirname(self.current_remote_path) or "/"
        self.refresh_file_list()

    def start_download(self, rp, fn):
        p, _ = QFileDialog.getSaveFileName(self, "Save", fn)
        if p: self.sftp_client.get(rp, p)


if __name__ == "__main__":
    app = QApplication([])
    window = PyExplorer()
    window.show()
    app.exec()
