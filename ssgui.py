
import sys
import time
import paramiko
import threading
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLineEdit,
    QPushButton, QTextEdit, QLabel, QFormLayout, QMessageBox,
    QDialog, QHBoxLayout, QListWidget, QListWidgetItem, QComboBox, QButtonGroup, QStyle,
    QMainWindow, QTabWidget
)
from PyQt5.QtCore import Qt, QEvent, pyqtSignal, QObject, QTimer
from PyQt5.QtGui import QFont, QTextCursor, QIcon, QPixmap
import re
import json
import os
import bcrypt
from cryptography.fernet import Fernet
import tempfile
import shutil
from PyQt5.QtGui import QDrag
import qtawesome as qta
import requests

# Création automatique du fichier servers.json vide s'il n'existe pas
if not os.path.exists("servers.json"):
    with open("servers.json", "w", encoding="utf-8") as f:
        json.dump([], f)

def download_temp_icon(url, filename):
    temp_dir = tempfile.gettempdir()
    temp_path = os.path.join(temp_dir, filename)
    r = requests.get(url)
    with open(temp_path, "wb") as f:
        f.write(r.content)
    return temp_path

# Téléchargement systématique à chaque lancement
icon_png_path = download_temp_icon("https://ssgui.netlify.app/icon.png", "icon.png")
cross_icon_path = download_temp_icon("https://ssgui.netlify.app/cross.png", "cross.png")

def resource_path(filename):
    temp_dir = tempfile.gettempdir()
    return os.path.join(temp_dir, filename)

class Worker(QObject):
    output_ready = pyqtSignal(str)

class ConnectionDialog(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SSGui")
        self.setFixedSize(600, 500)
        self.setStyleSheet("""
            QDialog {
                background: #101014;
                color: #e0e0e0;
                font-size: 15px;
                border-radius: 10px;
            }
            QLineEdit {
                background: #181a20;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 6px 8px;
                font-size: 15px;
            }
            QLineEdit:focus {
                border: 1.5px solid #4e8cff;
                background: #23272e;
            }
            QLabel {
                color: #b0b8c0;
                font-weight: bold;
            }
            QPushButton {
                background: #2d333b;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 6px;
                padding: 7px 18px;
                font-size: 15px;
            }
            QPushButton:hover {
                background: #3a4250;
                border: 1.5px solid #4e8cff;
            }
            QPushButton:pressed {
                background: #1a1d23;
            }
        """)
        self.servers_file = "servers.json"
        self.fernet_key_file = ".fernet.key"
        self.fernet = self.load_fernet()
        self.servers = self.load_servers()
        self.init_ui()

    def load_servers(self):
        if os.path.exists(self.servers_file):
            try:
                with open(self.servers_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def save_servers(self):
        try:
            with open(self.servers_file, 'w', encoding='utf-8') as f:
                json.dump(self.servers, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def load_fernet(self):
        if not os.path.exists(self.fernet_key_file):
            key = Fernet.generate_key()
            with open(self.fernet_key_file, 'wb') as f:
                f.write(key)
        else:
            with open(self.fernet_key_file, 'rb') as f:
                key = f.read()
        return Fernet(key)

    def init_ui(self):
        global_layout = QVBoxLayout()

        # Logo et titre SSGui en haut (horizontal et vraiment centré)
        logo_title_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_label.setPixmap(QPixmap(resource_path('icon.png')).scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignVCenter)
        title_label = QLabel("<b>SSGui</b>")
        title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        title_label.setStyleSheet("font-size: 28px; color: #8ab4f8; margin-left: 18px;")
        logo_title_layout.addWidget(logo_label)
        logo_title_layout.addWidget(title_label)
        logo_title_layout.setAlignment(Qt.AlignHCenter)
        logo_widget = QWidget()
        logo_widget.setLayout(logo_title_layout)
        logo_widget.setStyleSheet("background: #101014;")
        global_layout.addWidget(logo_widget, alignment=Qt.AlignHCenter)

        # Bouton SSH en haut (plus de modes)
        mode_layout = QHBoxLayout()
        self.mode = "SSH"
        ssh_btn = QPushButton("SSH")
        ssh_btn.setCheckable(True)
        ssh_btn.setChecked(True)
        ssh_btn.setEnabled(False)
        mode_layout.addWidget(ssh_btn)
        mode_layout.addStretch(1)
        global_layout.addLayout(mode_layout)

        main_layout = QHBoxLayout()

        # Liste verticale des serveurs à gauche
        self.server_list = QListWidget()
        self.server_list.setFixedWidth(210)
        self.server_list.addItem("+ Nouveau serveur")
        for s in self.servers:
            label = f"{s['user']}@{s['host']}:{s['port']}"
            self.server_list.addItem(label)
        self.server_list.currentRowChanged.connect(self.on_server_selected)
        self.server_list.setStyleSheet("""
            QListWidget {
                background: #23272e;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 8px;
                font-size: 15px;
            }
            QListWidget::item:selected {
                background: #3a4250;
                color: #8ab4f8;
            }
        """)
        main_layout.addWidget(self.server_list)

        # Formulaire à droite
        form_widget = QWidget()
        form_layout = QFormLayout()
        form_layout.setLabelAlignment(Qt.AlignRight)

        self.host_input = QLineEdit()
        self.user_input = QLineEdit()
        self.pass_input = QLineEdit()
        self.pass_input.setEchoMode(QLineEdit.Password)
        self.port_input = QLineEdit()
        self.port_input.setPlaceholderText("22")
        self.remember_pass = QPushButton("Retenir le mot de passe")
        self.remember_pass.setCheckable(True)
        self.remember_pass.setStyleSheet("QPushButton:checked { background: #4e8cff; color: #fff; }")

        form_layout.addRow("Hôte :", self.host_input)
        form_layout.addRow("Utilisateur :", self.user_input)
        form_layout.addRow("Mot de passe :", self.pass_input)
        form_layout.addRow("Port :", self.port_input)
        form_layout.addRow(self.remember_pass)

        btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connexion")
        self.cancel_btn = QPushButton("Annuler")
        self.connect_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self.connect_btn)
        btn_layout.addWidget(self.cancel_btn)
        form_layout.addRow(btn_layout)

        form_widget.setLayout(form_layout)
        main_layout.addWidget(form_widget)

        global_layout.addLayout(main_layout)
        self.setLayout(global_layout)
        self.server_list.setCurrentRow(0)

    def on_server_selected(self, idx):
        if idx > 0 and idx <= len(self.servers):
            s = self.servers[idx-1]
            self.host_input.setText(s['host'])
            self.user_input.setText(s['user'])
            self.port_input.setText(str(s['port']))
            # Déchiffrer le mot de passe si présent
            if 'password_fernet' in s:
                try:
                    decrypted = self.fernet.decrypt(s['password_fernet'].encode()).decode()
                    self.pass_input.setText(decrypted)
                    self.remember_pass.setChecked(True)
                except Exception:
                    self.pass_input.clear()
                    self.remember_pass.setChecked(False)
            else:
                self.pass_input.clear()
                self.remember_pass.setChecked(False)
        else:
            self.host_input.clear()
            self.user_input.clear()
            self.port_input.clear()
            self.pass_input.clear()
            self.remember_pass.setChecked(False)

    def set_mode(self, mode):
        self.mode = mode
        for m, btn in self.mode_btns.items():
            btn.setChecked(m == mode)

class SSHInteractiveClient(QWidget):
    def __init__(self, dialog=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("SSGui")
        self.setWindowIcon(QIcon(resource_path('icon.png')))
        self.retour = False  # Pour savoir si on a cliqué sur Retour
        self.setStyleSheet("""
            QWidget {
                font-family: 'Fira Mono', 'Consolas', 'Menlo', 'monospace';
                font-size: 14px;
                background-color: #181a20;
                color: #e0e0e0;
            }
            QLabel {
                color: #8ab4f8;
                font-size: 16px;
                font-weight: bold;
            }
            QTextEdit {
                background-color: #181a20;
                color: #e0e0e0;
                border: 1.5px solid #23272e;
                border-radius: 8px;
                padding: 8px;
                font-size: 15px;
                selection-background-color: #2d333b;
                selection-color: #f0f0f0;
            }
            QTextEdit:focus {
                border: 1.5px solid #4e8cff;
            }
        """)
        self.client = None
        self.shell = None
        self.connected = False
        self.worker = Worker()
        self.worker.output_ready.connect(self.append_output)
        self.terminal_buffer = ""
        self.cursor_visible = True
        self.cursor_char = '█'
        self.init_ui()
        if dialog is not None:
            self.connect_ssh(dialog)
        else:
            self.show_connection_dialog()

    def init_ui(self):
        layout = QVBoxLayout()
        # Logo et titre SSGui en haut (centré)
        logo_title_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_label.setPixmap(QPixmap(resource_path('icon.png')).scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_label.setAlignment(Qt.AlignVCenter)
        logo_label.setStyleSheet("background: transparent; border-radius: 12px; padding: 8px;")
        title_label = QLabel("<b>SSGui</b>")
        title_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        title_label.setStyleSheet("font-size: 22px; color: #8ab4f8; margin-left: 14px;")
        logo_title_layout.addWidget(logo_label)
        logo_title_layout.addWidget(title_label)
        logo_title_layout.setAlignment(Qt.AlignHCenter)
        logo_widget = QWidget()
        logo_widget.setLayout(logo_title_layout)
        logo_widget.setStyleSheet("background: #101014;")
        layout.addWidget(logo_widget, alignment=Qt.AlignHCenter)
        # Boutons Retour et Clear avec icônes qtawesome
        btn_layout = QHBoxLayout()
        self.back_btn = QPushButton(" Retour")
        self.back_btn.setFixedWidth(120)
        self.back_btn.setIcon(qta.icon('fa5s.angle-left', color='#8ab4f8'))
        self.back_btn.setStyleSheet("QPushButton { background: #23272e; color: #e0e0e0; border-radius: 6px; font-size: 14px; } QPushButton:hover { background: #3a4250; color: #8ab4f8; }")
        self.back_btn.clicked.connect(self.handle_back)
        btn_layout.addWidget(self.back_btn, alignment=Qt.AlignLeft)
        self.clear_btn = QPushButton(" Clear")
        self.clear_btn.setFixedWidth(120)
        self.clear_btn.setIcon(qta.icon('fa5s.trash', color='#ff3333'))
        self.clear_btn.setStyleSheet("QPushButton { background: #23272e; color: #e0e0e0; border-radius: 6px; font-size: 14px; } QPushButton:hover { background: #3a4250; color: #8ab4f8; }")
        self.clear_btn.clicked.connect(self.handle_clear)
        btn_layout.addWidget(self.clear_btn, alignment=Qt.AlignLeft)
        btn_layout.addStretch(1)
        layout.addLayout(btn_layout)
        self.terminal = QTextEdit()
        self.terminal.setReadOnly(True)
        self.terminal.setFont(QFont("Fira Mono", 11))
        self.terminal.setStyleSheet("QTextEdit { background-color: #1e1e1e; color: #e0e0e0; }")
        self.terminal.installEventFilter(self)
        self.terminal.setCursorWidth(2)
        layout.addWidget(self.terminal)
        self.setLayout(layout)
        self.cursor_timer = QTimer()
        self.cursor_timer.timeout.connect(self.toggle_cursor)
        self.cursor_timer.start(500)

    def show_connection_dialog(self):
        dialog = ConnectionDialog()
        if dialog.exec_() == QDialog.Accepted:
            self.connect_ssh(dialog)
        else:
            self.close()

    def connect_ssh(self, dialog):
        host = dialog.host_input.text().strip()
        user = dialog.user_input.text().strip()
        passwd = dialog.pass_input.text()
        port = dialog.port_input.text().strip()
        remember = dialog.remember_pass.isChecked()
        if not host or not user or not passwd:
            self.show_error("Tous les champs doivent être remplis (sauf port si 22).")
            return
        try:
            port = int(port) if port else 22
        except ValueError:
            self.show_error("Le port doit être un nombre.")
            return
        self.terminal.clear()
        self.terminal.append("[*] Connexion SSH en cours...")
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(host, port=port, username=user, password=passwd, timeout=10)
            self.shell = self.client.invoke_shell()
            self.connected = True
            self.terminal.append(f"[+] Connecté à {host}:{port}")
            threading.Thread(target=self.receive_output, daemon=True).start()
            self.save_server_entry(host, user, port, passwd, remember)
        except paramiko.AuthenticationException:
            self.terminal.append("[!] Authentification échouée.")
        except paramiko.SSHException as e:
            self.terminal.append(f"[!] Erreur SSH : {str(e)}")
        except Exception as e:
            self.terminal.append(f"[!] Connexion échouée : {str(e)}")

    def save_server_entry(self, host, user, port, passwd, remember):
        # Ajoute ou met à jour le serveur dans le JSON (pas de doublon)
        try:
            servers_file = "servers.json"
            if os.path.exists(servers_file):
                with open(servers_file, 'r', encoding='utf-8') as f:
                    servers = json.load(f)
            else:
                servers = []
            entry = {"host": host, "user": user, "port": port}
            if remember and passwd:
                # Chiffre le mot de passe
                dialog = self.findChild(ConnectionDialog)
                if dialog:
                    fernet = dialog.fernet
                else:
                    with open('.fernet.key', 'rb') as f:
                        fernet = Fernet(f.read())
                entry["password_fernet"] = fernet.encrypt(passwd.encode()).decode()
            # Supprime doublon
            servers = [s for s in servers if not (s['host'] == host and s['user'] == user and str(s['port']) == str(port))]
            servers.insert(0, entry)
            # Max 10 serveurs
            servers = servers[:10]
            with open(servers_file, 'w', encoding='utf-8') as f:
                json.dump(servers, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

    def receive_output(self):
        try:
            while self.connected and self.shell and not self.shell.closed:
                try:
                    data = self.shell.recv(4096).decode(errors='ignore')
                    if data:
                        self.worker.output_ready.emit(data)
                except Exception:
                    pass
                time.sleep(0.01)
        except Exception as e:
            self.worker.output_ready.emit(f"\n[!] Erreur réception : {str(e)}")

    def process_backspaces(self, text):
        result = []
        for c in text:
            if c == '\b' or ord(c) == 127:
                if result:
                    result.pop()
            else:
                result.append(c)
        return ''.join(result)

    def append_output(self, data):
        self.terminal_buffer += data
        clean_text = self.process_backspaces(self.terminal_buffer)
        if self.cursor_visible:
            display_text = clean_text + self.cursor_char
        else:
            display_text = clean_text
        self.terminal.setPlainText(display_text)
        self.terminal.moveCursor(QTextCursor.End)
        self.terminal.ensureCursorVisible()

    def toggle_cursor(self):
        # Ne jamais modifier le buffer ici, juste réafficher
        clean_text = self.process_backspaces(self.terminal_buffer)
        self.cursor_visible = not self.cursor_visible
        if self.cursor_visible:
            display_text = clean_text + self.cursor_char
        else:
            display_text = clean_text
        self.terminal.setPlainText(display_text)
        self.terminal.moveCursor(QTextCursor.End)
        self.terminal.ensureCursorVisible()

    def eventFilter(self, source, event):
        if event.type() == QEvent.KeyPress and source is self.terminal:
            if self.shell and self.connected:
                key = event.key()
                modifiers = event.modifiers()
                try:
                    if key in (Qt.Key_Return, Qt.Key_Enter):
                        self.shell.send(b'\r')
                    elif key == Qt.Key_Backspace:
                        self.shell.send(b'\x7f')
                    elif key == Qt.Key_Tab:
                        self.shell.send(b'\t')
                    elif modifiers == Qt.ControlModifier and key == Qt.Key_V:
                        clipboard = QApplication.clipboard()
                        if clipboard is not None:
                            text = clipboard.text()
                            if text:
                                self.shell.send(text.encode())
                    elif modifiers == Qt.ControlModifier and key == Qt.Key_C:
                        cursor = self.terminal.textCursor()
                        if cursor.hasSelection():
                            selected_text = cursor.selectedText()
                            clipboard = QApplication.clipboard()
                            if clipboard is not None:
                                clipboard.setText(selected_text)
                        else:
                            self.shell.send(b'\x03')  # SIGINT
                    elif 32 <= key <= 126:
                        self.shell.send(event.text().encode())
                    return True
                except Exception as e:
                    self.worker.output_ready.emit(f"\n[!] Erreur touche : {str(e)}")
            else:
                return True
        return super().eventFilter(source, event)

    def contextMenuEvent(self, event):
        if self.terminal.underMouse() and self.shell and self.connected:
            clipboard = QApplication.clipboard()
            if clipboard is not None:
                text = clipboard.text()
                if text:
                    try:
                        self.shell.send(text.encode())
                    except Exception as e:
                        self.worker.output_ready.emit(f"\n[!] Erreur coller clic droit : {str(e)}")
            event.accept()
        else:
            super().contextMenuEvent(event)

    def closeEvent(self, event):
        self.connected = False
        try:
            if self.client:
                self.client.close()
        except:
            pass
        event.accept()

    def show_error(self, message):
        QMessageBox.critical(self, "Erreur", message)

    def handle_back(self):
        self.connected = False
        try:
            if self.client:
                self.client.close()
        except:
            pass
        # Ferme juste l'onglet courant
        parent = self.parent()
        while parent and not isinstance(parent, QTabWidget):
            parent = parent.parent()
        if parent:
            idx = parent.indexOf(self)
            parent.removeTab(idx)

    def handle_clear(self):
        self.terminal_buffer = ""
        self.terminal.clear()
        if self.shell and self.connected:
            self.shell.send(b'\r')

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SSGui")
        self.setWindowIcon(QIcon(resource_path('icon.png')))
        self.setGeometry(100, 100, 900, 600)
        self.setStyleSheet("""
            QMainWindow, QWidget, QDialog {
                background: #101014;
                color: #e0e0e0;
            }
            QTabWidget::pane { border: none; background: #101014; }
            QTabBar::tab {
                background: #181a20;
                color: #e0e0e0;
                font-weight: normal;
                border-radius: 8px 8px 0 0;
                padding: 8px 24px;
                font-size: 15px;
                margin-right: 0px;
                border: 1.5px solid #23272e;
                border-bottom: none;
                border-left: 1.5px solid #23272e;
                min-width: 180px;
                max-width: 320px;
            }
            QTabBar::tab:first {
                border-left: none;
            }
            QTabBar::tab:selected {
                background: #101014;
                color: #fff;
                font-weight: bold;
                border-bottom: 2.5px solid #101014;
            }
            QTabBar::tab:!selected {
                background: #181a20;
                color: #e0e0e0;
                font-weight: normal;
            }
            QTabBar::tab:hover {
                background: #23272e;
                color: #fff;
                border-top: 2px solid #8ab4f8;
            }
            QTabBar::close-button {
                subcontrol-position: right;
                image: url("%s");
                min-width: 18px;
                min-height: 18px;
                border-radius: 9px;
                background: transparent;
            }
            QTabBar::close-button:hover {
                background: #ff3333;
            }
            QTabBar::close-button:pressed {
                background: #b71c1c;
            }
            QTabBar::tab:last { margin-right: 0; }
            QPushButton {
                background: #181a20;
                color: #e0e0e0;
                border: 1px solid #23272e;
                border-radius: 6px;
                font-size: 15px;
            }
            QPushButton:hover {
                background: #23272e;
                color: #8ab4f8;
            }
            QTextEdit {
                background-color: #101014;
                color: #e0e0e0;
                border: 1.5px solid #23272e;
                border-radius: 8px;
                padding: 8px;
                font-size: 15px;
                selection-background-color: #23272e;
                selection-color: #f0f0f0;
            }
        """ % resource_path('cross.png'))
        self.tabs = QTabWidget()
        self.tabs.setTabsClosable(True)
        self.tabs.setMovable(True)
        self.tabs.setDocumentMode(True)
        self.tabs.tabCloseRequested.connect(self.close_tab)
        self.tabs.currentChanged.connect(self.handle_tab_changed)
        self.setCentralWidget(self.tabs)
        self.add_plus_tab()
        self.tabs.setCurrentIndex(0)
        self.tabs.setElideMode(Qt.ElideNone)
        # Demande la première connexion immédiatement
        self.handle_tab_changed(0)
        # Si aucun onglet SSH n'a été ouvert, ferme la fenêtre
        if self.tabs.count() == 1:
            self.close()

    def add_plus_tab(self):
        # Onglet + à droite
        plus_widget = QWidget()
        idx = self.tabs.addTab(plus_widget, "+")
        self.tabs.setTabToolTip(idx, "Nouvelle connexion SSH")

    def handle_tab_changed(self, index):
        # Si on clique sur l'onglet +, ouvrir la connexion
        if index == self.tabs.count() - 1:
            dialog = ConnectionDialog()
            if dialog.exec_() == QDialog.Accepted:
                ssh_client = SSHInteractiveClient(dialog, parent=self)
                tab_title = f"{dialog.host_input.text()} - {dialog.user_input.text()}"
                idx = self.tabs.insertTab(self.tabs.count() - 1, ssh_client, tab_title)
                self.tabs.setCurrentIndex(idx)
            else:
                # Revenir à l'onglet précédent si annulation
                if self.tabs.count() > 1:
                    self.tabs.setCurrentIndex(0)

    def close_tab(self, index):
        if index == self.tabs.count() - 1:
            return  # Ne pas fermer l'onglet +
        widget = self.tabs.widget(index)
        if isinstance(widget, SSHInteractiveClient):
            widget.connected = False
            try:
                if widget.client:
                    widget.client.close()
            except:
                pass
        self.tabs.removeTab(index)
        # Si plus d'onglet SSH (seul le + reste), ferme la fenêtre principale
        if self.tabs.count() == 1:
            self.close()

# Nouveau main
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setWindowIcon(QIcon(resource_path('icon.png')))
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())