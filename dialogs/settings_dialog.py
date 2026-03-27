from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QHBoxLayout,
                             QPushButton, QGroupBox, QCheckBox, QComboBox, QLabel,
                             QDialogButtonBox, QFileDialog, QMessageBox, QApplication, QInputDialog,
                             QTabWidget, QWidget)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
import os
from core.config_manager import ConfigManager
from .chat_selection import ChatSelectionDialog
from .column_management import ColumnManagementDialog
from .whitelist_dialog import WhitelistDialog
from core.whitelist_manager import WhitelistManager

class SettingsDialog(QDialog):
    def __init__(self, parent=None, tg_manager=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.tg_manager = tg_manager
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.setWindowTitle("Configuración")
        self.setMinimumWidth(500)

        self.layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.layout.addWidget(self.tabs)

        # --- Tab: Rutas ---
        rutas_tab = QWidget()
        rutas_layout = QVBoxLayout(rutas_tab)
        paths_group = QGroupBox("Configuración de Rutas")
        paths_form = QFormLayout()

        self.base_dir_edit = QLineEdit(self.config.get("base_dir_path"))
        self.btn_browse_base = QPushButton("...")
        self.btn_browse_base.clicked.connect(self.browse_base_dir)
        base_h_layout = QHBoxLayout()
        base_h_layout.addWidget(self.base_dir_edit)
        base_h_layout.addWidget(self.btn_browse_base)
        paths_form.addRow("Ruta Base Recursos:", base_h_layout)

        self.global_db_edit = QLineEdit(self.config.get("global_db_path"))
        self.btn_browse_db = QPushButton("...")
        self.btn_browse_db.clicked.connect(self.browse_global_db)
        db_h_layout = QHBoxLayout()
        db_h_layout.addWidget(self.global_db_edit)
        db_h_layout.addWidget(self.btn_browse_db)
        paths_form.addRow("Ruta DB Global:", db_h_layout)

        self.config_path_edit = QLineEdit(self.config.config_path)
        self.config_path_edit.setReadOnly(True)
        self.btn_move_config = QPushButton("Cambiar/Mover JSON")
        self.btn_move_config.setToolTip("Al cambiar la ruta, el archivo config.json, cache.json, sesiones de telegram y la carpeta de jornadas se moverán a la nueva ubicación.")
        self.btn_move_config.clicked.connect(self.move_config_json)
        config_h_layout = QHBoxLayout()
        config_h_layout.addWidget(self.config_path_edit)
        config_h_layout.addWidget(self.btn_move_config)
        paths_form.addRow("Ubicación de Ajustes:", config_h_layout)

        paths_group.setLayout(paths_form)
        rutas_layout.addWidget(paths_group)
        rutas_layout.addStretch()
        self.tabs.addTab(rutas_tab, "Rutas")

        # --- Tab: Interfaz ---
        ui_tab = QWidget()
        ui_layout_v = QVBoxLayout(ui_tab)
        ui_group = QGroupBox("Interfaz de Usuario")
        ui_form = QFormLayout()

        self.auto_resize_cb = QCheckBox()
        self.auto_resize_cb.setChecked(self.config.get("ui.auto_resize", True))
        ui_form.addRow("Auto-ajustar columnas:", self.auto_resize_cb)

        self.show_const_logs_cb = QCheckBox()
        self.show_const_logs_cb.setChecked(self.config.get("ui.show_construction_logs", False))
        ui_form.addRow("Mostrar logs de construcción:", self.show_const_logs_cb)

        self.show_sidebar_cb = QCheckBox()
        self.show_sidebar_cb.setChecked(self.config.get("ui.sidebar_visible", True))
        ui_form.addRow("Ver panel de años:", self.show_sidebar_cb)

        self.show_console_cb = QCheckBox()
        self.show_console_cb.setChecked(self.config.get("ui.console_visible", True))
        ui_form.addRow("Ver consola SQL:", self.show_console_cb)

        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Fusion", "Windows", "Dark"])
        self.theme_combo.setCurrentText(self.config.get("ui.theme", "Fusion"))
        ui_form.addRow("Tema:", self.theme_combo)

        ui_group.setLayout(ui_form)
        ui_layout_v.addWidget(ui_group)
        ui_layout_v.addStretch()
        self.tabs.addTab(ui_tab, "Interfaz")

        # --- Tab: Telegram ---
        tg_tab = QWidget()
        tg_layout_v = QVBoxLayout(tg_tab)
        tg_group = QGroupBox("Ajustes de Telegram")
        tg_form = QFormLayout()

        self.api_id_edit = QLineEdit(str(self.config.get("telegram.api_id", "")))
        tg_form.addRow("API ID:", self.api_id_edit)

        self.api_hash_edit = QLineEdit(self.config.get("telegram.api_hash", ""))
        tg_form.addRow("API Hash:", self.api_hash_edit)

        help_label = QLabel('<a href="https://my.telegram.org/">¿Dónde consigo esto?</a>')
        help_label.setOpenExternalLinks(True)
        tg_form.addRow("", help_label)

        self.tg_status_label = QLabel(self.tg_manager.get_last_status() if self.tg_manager else "No disponible")
        self._tg_connected = self.tg_manager.is_connected() if self.tg_manager else False
        self.btn_tg_connect = QPushButton("Desconectar" if self._tg_connected else "Conectar")
        self.btn_tg_connect.clicked.connect(self.on_tg_main_btn_clicked)

        tg_conn_layout = QHBoxLayout()
        tg_conn_layout.addWidget(self.tg_status_label)
        tg_conn_layout.addStretch()
        tg_conn_layout.addWidget(self.btn_tg_connect)
        tg_form.addRow("Estado:", tg_conn_layout)

        self.chat_name_label = QLabel(self.config.get("telegram.chat_name", "Ninguno seleccionado"))
        self.btn_select_chat = QPushButton("Elegir Grupo/Canal")
        self.btn_select_chat.clicked.connect(self.on_select_chat_clicked)

        tg_chat_layout = QHBoxLayout()
        tg_chat_layout.addWidget(self.chat_name_label)
        tg_chat_layout.addStretch()
        tg_chat_layout.addWidget(self.btn_select_chat)
        tg_form.addRow("Chat Destino:", tg_chat_layout)

        tg_group.setLayout(tg_form)
        tg_layout_v.addWidget(tg_group)
        tg_layout_v.addStretch()
        self.tabs.addTab(tg_tab, "Telegram")

        # --- Tab: Servidor API ---
        api_tab = QWidget()
        api_layout_v = QVBoxLayout(api_tab)
        api_group = QGroupBox("Exposición de Recursos")
        api_form = QFormLayout()

        self.api_enabled_cb = QCheckBox("Exponer materiales a la red local")
        self.api_enabled_cb.setChecked(self.config.get("api.enabled", False))
        api_form.addRow(self.api_enabled_cb)

        self.api_port_edit = QLineEdit(str(self.config.get("api.port", 9090)))
        api_form.addRow("Puerto API:", self.api_port_edit)

        api_group.setLayout(api_form)
        api_layout_v.addWidget(api_group)
        api_layout_v.addStretch()
        self.tabs.addTab(api_tab, "Servidor API")

        # --- Tab: Firebase ---
        fb_tab = QWidget()
        fb_layout_v = QVBoxLayout(fb_tab)
        fb_group = QGroupBox("Firebase Connector")
        fb_form = QFormLayout()

        self.fb_url_edit = QLineEdit(self.config.get("firebase.db_url", ""))
        self.fb_url_edit.textChanged.connect(self.update_fb_btns_state)
        fb_form.addRow("URL de Base de Datos:", self.fb_url_edit)

        self.fb_ref_edit = QLineEdit(self.config.get("firebase.db_ref_journals", ""))
        fb_form.addRow("Referencia Jornadas:", self.fb_ref_edit)

        self.fb_creds_label = QLabel()
        self.update_fb_creds_label(self.config.get("firebase.credentials_path", ""))

        self.btn_browse_fb_creds = QPushButton("Anexar Credenciales JSON")
        self.btn_browse_fb_creds.clicked.connect(self.browse_fb_creds)

        fb_creds_h_layout = QHBoxLayout()
        fb_creds_h_layout.addWidget(self.fb_creds_label)
        fb_creds_h_layout.addStretch()
        fb_creds_h_layout.addWidget(self.btn_browse_fb_creds)
        fb_form.addRow("Credenciales:", fb_creds_h_layout)

        fb_group.setLayout(fb_form)
        fb_layout_v.addWidget(fb_group)
        fb_layout_v.addStretch()
        self.tabs.addTab(fb_tab, "Firebase")

        # --- Tab: Seguridad ---
        sec_tab = QWidget()
        sec_layout_v = QVBoxLayout(sec_tab)
        net_group = QGroupBox("Seguridad de Red")
        net_form = QFormLayout()

        self.whitelist_enabled_cb = QCheckBox()
        self.whitelist_enabled_cb.setChecked(self.config.get("security.whitelist_enabled", False))
        net_form.addRow("Modo lista blanca de redes:", self.whitelist_enabled_cb)

        self.btn_manage_whitelist = QPushButton("Administrar lista blanca de redes")
        self.btn_manage_whitelist.clicked.connect(self.manage_whitelist)
        self.update_whitelist_tooltip()
        net_form.addRow(self.btn_manage_whitelist)

        net_group.setLayout(net_form)
        sec_layout_v.addWidget(net_group)
        sec_layout_v.addStretch()
        self.tabs.addTab(sec_tab, "Seguridad")

        # Advanced/Management Area
        mgmt_layout = QHBoxLayout()
        self.btn_manage_columns = QPushButton("Administrar Anchos de Columnas")
        self.btn_manage_columns.clicked.connect(self.manage_columns)
        mgmt_layout.addWidget(self.btn_manage_columns)

        self.btn_clear_cache = QPushButton("Limpiar Caché de Archivos")
        self.btn_clear_cache.clicked.connect(self.clear_file_cache)
        mgmt_layout.addWidget(self.btn_clear_cache)
        self.layout.addLayout(mgmt_layout)

        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_save)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        # Initial signal connection
        self._init_tg_manager()

    def _init_tg_manager(self):
        if self.tg_manager:
            try:
                self.tg_manager.connection_status.disconnect(self.update_tg_status)
            except Exception: pass
            try:
                self.tg_manager.auth_required.disconnect(self.handle_tg_auth)
            except Exception: pass
            try:
                self.tg_manager.chats_loaded.disconnect(self.show_chat_selection)
            except Exception: pass

            self.tg_manager.connection_status.connect(self.update_tg_status)
            self.tg_manager.auth_required.connect(self.handle_tg_auth)
            self.tg_manager.chats_loaded.connect(self.show_chat_selection)

    def on_tg_main_btn_clicked(self):
        self._init_tg_manager()
        if self._tg_connected:
            self.tg_manager.disconnect()
        elif not self.tg_manager.is_connecting():
            # Save current API credentials first
            self.config.set("telegram.api_id", self.api_id_edit.text(), save=False)
            self.config.set("telegram.api_hash", self.api_hash_edit.text(), save=True)
            # Ensure we start from a clean state if credentials changed
            self.tg_manager.disconnect()
            self.tg_manager.connect()

    def update_tg_status(self, message, connected):
        self.tg_status_label.setText(message)
        self._tg_connected = connected
        if self.tg_manager and self.tg_manager.is_connecting():
            self.btn_tg_connect.setText("Conectando...")
            self.btn_tg_connect.setEnabled(False)
        else:
            self.btn_tg_connect.setText("Desconectar" if connected else "Conectar")
            self.btn_tg_connect.setEnabled(True)

    def handle_tg_auth(self, type):
        if not self.tg_manager: return
        self._init_tg_manager()
        if type == "phone":
            phone, ok = QInputDialog.getText(self, "Telegram Auth", "Introduce tu número de teléfono (+...):")
            if ok: self.tg_manager.submit_phone(phone)
        elif type == "code":
            code, ok = QInputDialog.getText(self, "Telegram Auth", "Introduce el código de verificación:")
            if ok: self.tg_manager.submit_code(code)
        elif type == "password":
            pw, ok = QInputDialog.getText(self, "Telegram Auth", "Introduce tu contraseña 2FA:", QLineEdit.EchoMode.Password)
            if ok: self.tg_manager.submit_password(pw)

    def on_select_chat_clicked(self):
        if not self.tg_manager:
            QMessageBox.critical(self, "Error", "Telegram Manager no disponible.")
            return
        self._init_tg_manager()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.tg_manager.fetch_chats()

    def show_chat_selection(self, chats):
        QApplication.restoreOverrideCursor()
        dialog = ChatSelectionDialog(chats, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chat = dialog.get_selected_chat()
            if chat:
                self.config.set("telegram.chat_id", chat['id'], save=False)
                self.config.set("telegram.chat_name", chat['name'], save=True)
                self.chat_name_label.setText(chat['name'])

    def closeEvent(self, event):
        if self.tg_manager:
            try:
                self.tg_manager.connection_status.disconnect(self.update_tg_status)
                self.tg_manager.auth_required.disconnect(self.handle_tg_auth)
                self.tg_manager.chats_loaded.disconnect(self.show_chat_selection)
            except Exception: pass
        super().closeEvent(event)

    def browse_base_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Seleccionar Ruta Base", self.base_dir_edit.text())
        if dir_path:
            self.base_dir_edit.setText(dir_path)

    def browse_global_db(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar DB Global", self.global_db_edit.text(), "SQLite DB (*.db)")
        if file_path:
            self.global_db_edit.setText(file_path)

    def browse_fb_creds(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar Credenciales Firebase", "", "JSON (*.json)")
        if file_path:
            self.update_fb_creds_label(file_path)

    def update_fb_creds_label(self, path):
        if not path:
            self.fb_creds_label.setText('<span style="color: grey;">No seleccionado</span>')
            self._fb_creds_path = ""
            return

        from core.firebase_manager import FirebaseManager
        fm = FirebaseManager()
        if fm.validate_credentials(path):
            self.fb_creds_label.setText('<span style="color: green;">Válido</span>')
            self._fb_creds_path = path
        else:
            self.fb_creds_label.setText('<span style="color: red;">Inválido</span>')
            self._fb_creds_path = ""

    def update_fb_btns_state(self):
        url = self.fb_url_edit.text().strip()
        self.btn_browse_fb_creds.setEnabled(bool(url))

    def move_config_json(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Mover archivo de ajustes", self.config_path_edit.text(), "JSON (*.json)")
        if file_path:
            if self.config.move_config_file(file_path):
                self.config_path_edit.setText(file_path)
                QMessageBox.information(self, "Éxito", "Archivo de ajustes movido correctamente.")

    def manage_columns(self):
        dialog = ColumnManagementDialog(self)
        dialog.exec()

    def clear_file_cache(self):
        res = QMessageBox.question(self, "Limpiar Caché", "¿Deseas borrar el historial de primeros archivos detectados?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            self.config.clear_cache("first_files")
            QMessageBox.information(self, "Limpiar Caché", "Caché borrada correctamente.")

    def manage_whitelist(self):
        dialog = WhitelistDialog(self)
        dialog.exec()
        self.update_whitelist_tooltip()

    def update_whitelist_tooltip(self):
        wm = WhitelistManager()
        status = wm.check_connection_status()
        if status == "accepted":
            tooltip = "Conectado a una red aceptada."
        elif status == "unacceptable":
            tooltip = "Conectado a una red NO aceptada o fuera de control."
        elif status == "offline":
            tooltip = "No hay conexión a internet/red."
        elif status == "empty":
            tooltip = "No hay redes añadidas a la lista blanca todavía."
        else:
            tooltip = "Estado de red desconocido."
        self.btn_manage_whitelist.setToolTip(tooltip)

    def validate_and_save(self):
        base_path = self.base_dir_edit.text()
        db_path = self.global_db_edit.text()

        valid_base, msg_base = ConfigManager.validate_base_dir(base_path)
        if not valid_base:
            res = QMessageBox.warning(self, "Validación de Ruta Base", f"{msg_base}\n¿Deseas guardar de todas formas?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if res == QMessageBox.StandardButton.No:
                return

        valid_db, msg_db = ConfigManager.validate_db_path(db_path)
        if not valid_db:
            res = QMessageBox.warning(self, "Validación de DB Global", f"{msg_db}\n¿Deseas guardar de todas formas?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if res == QMessageBox.StandardButton.No:
                return

        self.config.set("base_dir_path", base_path, save=False)
        self.config.set("global_db_path", db_path, save=False)
        self.config.set("ui.auto_resize", self.auto_resize_cb.isChecked(), save=False)
        self.config.set("ui.show_construction_logs", self.show_const_logs_cb.isChecked(), save=False)
        self.config.set("ui.sidebar_visible", self.show_sidebar_cb.isChecked(), save=False)
        self.config.set("ui.console_visible", self.show_console_cb.isChecked(), save=False)
        self.config.set("ui.theme", self.theme_combo.currentText(), save=False)
        self.config.set("security.whitelist_enabled", self.whitelist_enabled_cb.isChecked(), save=False)

        # API
        self.config.set("api.enabled", self.api_enabled_cb.isChecked(), save=False)
        try:
            self.config.set("api.port", int(self.api_port_edit.text()), save=False)
        except: pass

        # Firebase
        self.config.set("firebase.db_url", self.fb_url_edit.text(), save=False)
        self.config.set("firebase.db_ref_journals", self.fb_ref_edit.text(), save=False)
        self.config.set("firebase.credentials_path", getattr(self, '_fb_creds_path', ""), save=False)

        self.config.set("telegram.api_id", self.api_id_edit.text(), save=False)
        self.config.set("telegram.api_hash", self.api_hash_edit.text(), save=True) # Last one saves

        # Update API server status in main window
        if self.parent() and hasattr(self.parent(), "update_api_server_status"):
            self.parent().update_api_server_status()

        self.accept()
