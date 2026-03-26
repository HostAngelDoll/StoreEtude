from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QTabWidget, QWidget, QFormLayout, QLineEdit, QPushButton, QCheckBox, QComboBox, QHBoxLayout)
from PyQt6.QtCore import Qt

class SettingsDialog(QDialog):
    def __init__(self, parent, config_controller, network_controller):
        super().__init__(parent)
        self.config_ctrl = config_controller
        self.network_ctrl = network_controller
        self.setWindowTitle("Configuración")
        self.resize(600, 450)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self.tabs.addTab(self.init_paths_tab(), "Rutas")
        self.tabs.addTab(self.init_ui_tab(), "Interfaz")
        self.tabs.addTab(self.init_telegram_tab(), "Telegram")
        self.tabs.addTab(self.init_security_tab(), "Seguridad")

        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar")
        self.btn_cancel = QPushButton("Cancelar")
        btn_layout.addStretch(); btn_layout.addWidget(self.btn_save); btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_save.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def init_paths_tab(self):
        widget = QWidget(); lay = QFormLayout(widget)
        self.base_dir_edit = QLineEdit(self.config_ctrl.get_settings().base_dir_path)
        self.global_db_edit = QLineEdit(self.config_ctrl.get_settings().global_db_path)
        lay.addRow("Ruta Base:", self.base_dir_edit); lay.addRow("Base Global:", self.global_db_edit)
        return widget

    def init_ui_tab(self):
        widget = QWidget(); lay = QFormLayout(widget)
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Fusion", "Windows", "Dark"])
        self.theme_combo.setCurrentText(self.config_ctrl.get_settings().ui.theme)
        self.auto_resize_check = QCheckBox("Auto-redimensionar columnas")
        self.auto_resize_check.setChecked(self.config_ctrl.get_settings().ui.auto_resize)
        lay.addRow("Tema:", self.theme_combo); lay.addRow(self.auto_resize_check)
        return widget

    def init_telegram_tab(self):
        widget = QWidget(); lay = QFormLayout(widget)
        tg = self.config_ctrl.get_settings().telegram
        self.api_id_edit = QLineEdit(tg.api_id); self.api_hash_edit = QLineEdit(tg.api_hash)
        lay.addRow("API ID:", self.api_id_edit); lay.addRow("API Hash:", self.api_hash_edit)
        return widget

    def init_security_tab(self):
        widget = QWidget(); lay = QVBoxLayout(widget)
        self.whitelist_btn = QPushButton("Gestionar Lista Blanca de Redes")
        self.whitelist_btn.clicked.connect(self.on_whitelist_clicked)
        lay.addWidget(self.whitelist_btn)
        return widget

    def on_whitelist_clicked(self):
        # Implementation of WhitelistDialog using network_controller
        pass

    def accept(self):
        # Collect values and update config through config_controller
        settings = self.config_ctrl.get_settings()
        settings.base_dir_path = self.base_dir_edit.text()
        settings.global_db_path = self.global_db_edit.text()
        settings.ui.theme = self.theme_combo.currentText()
        settings.ui.auto_resize = self.auto_resize_check.isChecked()
        settings.telegram.api_id = self.api_id_edit.text()
        settings.telegram.api_hash = self.api_hash_edit.text()
        self.config_ctrl.save_settings()
        super().accept()
