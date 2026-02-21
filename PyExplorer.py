import os
import json
import paramiko
import stat
import tempfile
import platform
import subprocess
import posixpath  # Gestione percorsi Raspberry su Windows
import requests  # Per controllo aggiornamenti su GitHub
import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QVBoxLayout, QHBoxLayout,
                             QPushButton, QLineEdit, QListWidget, QWidget, QMessageBox,
                             QFileDialog, QLabel, QFrame, QMenu)
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtCore import Qt, QPoint

# Metadati e Configurazione
VERSION = "1.0.2"  # Incrementata versione per la nuova feature
REPO_OWNER = "enkas79"
REPO_NAME = "PyExplorer"
CONFIG_FILE = "connessioni_raspberry.json"


class PyExplorer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"PyExplorer v{VERSION}")
        self.setGeometry(100, 100, 1150, 650)

        # Caricamento Icona
        if os.path.exists("icon.png"):
            self.setWindowIcon(QIcon("icon.png"))

        self.ssh_client = None
        self.sftp_client = None
        self.current_remote_path = "/home"

        # Dizionario Traduzioni
        self.current_lang = "it"
        self.texts = {
            "it": {
                "nome": "Nome:", "host": "Host:", "user": "Utente:", "pass": "Pass:",
                "salva": "💾 Salva", "connetti": "⚡ Connetti", "dispositivi": "<b>Dispositivi:</b>",
                "elimina_disp": "🗑️ Elimina", "su": "⬅ Su", "esci": "🚪 Esci",
                "info": "Info", "lingua": "Lingua", "aiuto": "Aiuto",
                "percorso": "Percorso:", "pronto": "Pronto.", "connesso": "Connesso.",
                "apri": "👁️ Apri/Modifica", "scarica": "⬇️ Scarica", "elimina_file": "❌ Elimina",
                "carica": "⬆️ Carica file qui", "aggiorna": "🔄 Aggiorna",
                "msg_info": "Autore: Enrico Martini\nVersione:",
                "err_conn": "Connessione fallita", "conf_del": "Eliminare definitivamente?",
                "edit_title": "Modifica File",
                "edit_msg": "Hai finito le modifiche? Salva nell'editor e clicca SI per aggiornare il Raspberry.",
                "up_ok": "✅ File aggiornato!", "no_mod": "Nessuna modifica rilevata."
            },
            "en": {
                "nome": "Name:", "host": "Host:", "user": "User:", "pass": "Pass:",
                "salva": "💾 Save", "connetti": "⚡ Connect", "dispositivi": "<b>Devices:</b>",
                "elimina_disp": "🗑️ Delete", "su": "⬅ Up", "esci": "🚪 Exit",
                "info": "Info", "lingua": "Language", "aiuto": "Help",
                "percorso": "Path:", "pronto": "Ready.", "connesso": "Connected.",
                "apri": "👁️ Open/Edit", "scarica": "⬇️ Download", "elimina_file": "❌ Delete",
                "carica": "⬆️ Upload file here", "aggiorna": "🔄 Refresh",
                "msg_info": "Author: Enrico Martini\nVersion:",
                "err_conn": "Connection failed", "conf_del": "Delete permanently?",
                "edit_title": "Edit File",
                "edit_msg": "Finished editing? Save in the editor and click YES to update the Raspberry.",
                "up_ok": "✅ File updated!", "no_mod": "No changes detected."
            }
            # Puoi aggiungere le altre lingue seguendo questo schema
        }

        self.saved_connections = self.load_connections()
        self.initUI()
        self.create_menu_bar()
        self.retranslate_ui()
        self.check_for_updates()

    # --- AGGIORNAMENTO DINAMICO INFO ---
    def show_info(self):
        t = self.texts[self.current_lang]
        full_info = f"{t['msg_info']} {VERSION}"
        QMessageBox.information(self, "PyExplorer", full_info)

    # --- GESTIONE AGGIORNAMENTI ---
    def check_for_updates(self):
        try:
            api_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases/latest"
            response = requests.get(api_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                latest_v = data["tag_name"].replace("v", "")
                if latest_v > VERSION:
                    if QMessageBox.question(self, "Update",
                                            f"Nuova versione v{latest_v} disponibile. Aggiornare?") == QMessageBox.StandardButton.Yes:
                        self.download_update(data["assets"])
        except:
            pass

    def download_update(self, assets):
        try:
            url = next((a["browser_download_url"] for a in assets if "PyExplorer.exe" in a["name"]), None)
            if not url: return
            r = requests.get(url)
            with open("PyExplorer_new.exe", "wb") as f:
                f.write(r.content)
            with open("update.bat", "w") as f:
                f.write(
                    f'@echo off\ntimeout /t 2\nmove /y "PyExplorer_new.exe" "{sys.argv[0]}"\nstart "" "{sys.argv[0]}"\ndel "update.bat"')
            subprocess.Popen(["update.bat"], shell=True)
            sys.exit()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    # --- LOGICA ARCHIVIAZIONE ---
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
        self.saved_connections[a] = {
            "host": self.host_input.text(), "user": self.user_input.text(),
            "password": self.pass_input.text(), "alias": a
        }
        with open(CONFIG_FILE, "w") as f: json.dump(self.saved_connections, f, indent=4)
        self.refresh_device_list()

    def delete_connection(self):
        i = self.devices_list.currentItem()
        if i and i.text() in self.saved_connections:
            del self.saved_connections[i.text()]
            with open(CONFIG_FILE, "w") as f: json.dump(self.saved_connections, f, indent=4)
            self.refresh_device_list()

    def refresh_device_list(self):
        self.devices_list.clear()
        for a in self.saved_connections.keys(): self.devices_list.addItem(a)

    def load_selected_device(self, item):
        d = self.saved_connections.get(item.text(), {})
        self.alias_input.setText(d.get("alias", ""))
        self.host_input.setText(d.get("host", ""))
        self.user_input.setText(d.get("user", ""))
        self.pass_input.setText(d.get("password", ""))

    # --- INTERFACCIA ---
    def initUI(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_l = QVBoxLayout(central)

        t_l = QHBoxLayout()
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
        self.btn_connect.clicked.connect(self.connect_to_raspberry)
        self.btn_connect.setStyleSheet("background-color: #2E7D32; color: white; font-weight: bold;")

        for w in [self.label_nome, self.alias_input, QLabel("Host:"), self.host_input,
                  self.label_user, self.user_input, self.label_pass, self.pass_input,
                  self.btn_save, self.btn_connect]: t_l.addWidget(w)
        main_l.addLayout(t_l)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        main_l.addWidget(line)

        c_l = QHBoxLayout()
        s_l = QVBoxLayout()
        self.label_devices = QLabel()
        s_l.addWidget(self.label_devices)
        self.devices_list = QListWidget()
        self.devices_list.setFixedWidth(180)
        self.devices_list.itemClicked.connect(self.load_selected_device)
        self.refresh_device_list()
        s_l.addWidget(self.devices_list)
        self.btn_delete_disp = QPushButton()
        self.btn_delete_disp.clicked.connect(self.delete_connection)
        self.btn_delete_disp.setStyleSheet("color: #C62828;")
        s_l.addWidget(self.btn_delete_disp)
        c_l.addLayout(s_l)

        e_l = QVBoxLayout()
        n_l = QHBoxLayout()
        self.btn_back = QPushButton()
        self.btn_back.clicked.connect(self.go_to_parent)
        self.path_label = QLabel()
        n_l.addWidget(self.btn_back)
        n_l.addWidget(self.path_label)
        n_l.addStretch()
        e_l.addLayout(n_l)
        self.file_list = QListWidget()
        self.file_list.itemDoubleClicked.connect(self.handle_item_click)
        self.file_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.file_list.customContextMenuRequested.connect(self.show_context_menu)
        e_l.addWidget(self.file_list)
        c_l.addLayout(e_l)
        main_l.addLayout(c_l)

        b_l = QHBoxLayout()
        self.status_bar = QLabel()
        b_l.addWidget(self.status_bar)
        b_l.addStretch()
        self.btn_exit = QPushButton()
        self.btn_exit.clicked.connect(self.close)
        self.btn_exit.setStyleSheet("background-color: #C62828; color: white;")
        b_l.addWidget(self.btn_exit)
        main_l.addLayout(b_l)

    def create_menu_bar(self):
        m = self.menuBar()
        self.menu_lingua = m.addMenu("Lingua")
        for n, c in [("Italiano", "it"), ("English", "en")]:
            a = QAction(n, self)
            a.triggered.connect(lambda ch, code=c: self.change_language(code))
            self.menu_lingua.addAction(a)
        self.menu_aiuto = m.addMenu("Aiuto")
        self.info_action = QAction("Info", self)
        self.info_action.triggered.connect(self.show_info)
        self.menu_aiuto.addAction(self.info_action)

    def change_language(self, c):
        self.current_lang = c
        self.retranslate_ui()

    def retranslate_ui(self):
        t = self.texts.get(self.current_lang, self.texts["en"])
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
        self.menu_lingua.setTitle(t["lingua"])
        self.menu_aiuto.setTitle(t["aiuto"])
        self.info_action.setText(t["info"])

    # --- SFTP LOGIC ---
    def connect_to_raspberry(self):
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.ssh_client.connect(self.host_input.text(), username=self.user_input.text(),
                                    password=self.pass_input.text())
            self.sftp_client = self.ssh_client.open_sftp()
            self.refresh_file_list()
            self.status_bar.setText(self.texts[self.current_lang]["connesso"])
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def refresh_file_list(self):
        self.file_list.clear()
        try:
            it = self.sftp_client.listdir_attr(self.current_remote_path)
            it.sort(key=lambda x: (not stat.S_ISDIR(x.st_mode), x.filename.lower()))
            for a in it: self.file_list.addItem(("📁 " if stat.S_ISDIR(a.st_mode) else "📄 ") + a.filename)
            self.path_label.setText(f"{self.texts[self.current_lang]['percorso']} {self.current_remote_path}")
        except:
            pass

    def handle_item_click(self, item):
        rn = item.text().replace("📁 ", "").replace("📄 ", "")
        rp = posixpath.join(self.current_remote_path, rn)
        try:
            if stat.S_ISDIR(self.sftp_client.stat(rp).st_mode):
                self.current_remote_path = rp
                self.refresh_file_list()
            else:
                self.open_remote_file(rp, rn)
        except:
            pass

    # --- NUOVA LOGICA DI MODIFICA E SALVATAGGIO ---
    def open_remote_file(self, rp, fn):
        """Scarica il file, lo apre per la modifica e lo salva se cambiato."""
        try:
            t = self.texts[self.current_lang]
            tp = os.path.join(tempfile.gettempdir(), fn)
            self.sftp_client.get(rp, tp)

            # Registriamo l'ora dell'ultima modifica locale
            time_before = os.path.getmtime(tp)

            # Apriamo il file con il programma predefinito del sistema
            if platform.system() == "Windows":
                os.startfile(tp)
            else:
                subprocess.call(("open" if platform.system() == "Darwin" else "xdg-open", tp))

            # Messaggio di attesa per l'utente
            msg = QMessageBox.question(self, t["edit_title"], t["edit_msg"],
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)

            if msg == QMessageBox.StandardButton.Yes:
                # Controlliamo se il file è stato effettivamente salvato dall'utente
                if os.path.getmtime(tp) > time_before:
                    self.sftp_client.put(tp, rp)
                    self.status_bar.setText(t["up_ok"])
                    self.refresh_file_list()
                else:
                    self.status_bar.setText(t["no_mod"])
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

    def show_context_menu(self, pos):
        item = self.file_list.itemAt(pos)
        t = self.texts[self.current_lang]
        menu = QMenu()
        if item:
            rn = item.text().replace("📁 ", "").replace("📄 ", "")
            rp = posixpath.join(self.current_remote_path, rn)
            menu.addAction(t["apri"]).triggered.connect(lambda: self.handle_item_click(item))
            menu.addAction(t["scarica"]).triggered.connect(lambda: self.start_download(rp, rn))
            menu.addAction(t["elimina_file"]).triggered.connect(lambda: self.delete_remote_item(item))
        else:
            menu.addAction(t["carica"]).triggered.connect(self.start_upload)
            menu.addAction(t["aggiorna"]).triggered.connect(self.refresh_file_list)
        menu.exec(self.file_list.mapToGlobal(pos))

    def go_to_parent(self):
        if self.current_remote_path == "/": return
        self.current_remote_path = posixpath.dirname(self.current_remote_path) or "/"
        self.refresh_file_list()

    def start_download(self, rp, fn):
        p, _ = QFileDialog.getSaveFileName(self, "Save", fn)
        if p: self.sftp_client.get(rp, p)

    def start_upload(self):
        lp, _ = QFileDialog.getOpenFileName(self, "Select")
        if lp:
            self.sftp_client.put(lp, posixpath.join(self.current_remote_path, os.path.basename(lp)))
            self.refresh_file_list()

    def delete_remote_item(self, item):
        rn = item.text().replace("📁 ", "").replace("📄 ", "")
        rp = posixpath.join(self.current_remote_path, rn)
        if QMessageBox.question(self, "Confirm", f"Delete {rn}?") == QMessageBox.StandardButton.Yes:
            try:
                if "📁" in item.text():
                    self.sftp_client.rmdir(rp)
                else:
                    self.sftp_client.remove(rp)
                self.refresh_file_list()
            except:
                pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PyExplorer()
    window.show()
    sys.exit(app.exec())
