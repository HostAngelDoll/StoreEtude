from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QScrollArea, QWidget,
                             QGroupBox, QGridLayout, QComboBox, QProgressBar, QHBoxLayout,
                             QPushButton, QCheckBox, QLineEdit, QMessageBox, QApplication, QInputDialog)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from datetime import datetime
import os
from core.config_manager import ConfigManager

class TelegramDownloadDialog(QDialog):
    def __init__(self, parent=None, tg_manager=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.tg_manager = tg_manager

        if self.tg_manager:
            try:
                self.tg_manager.videos_loaded.disconnect(self.populate_videos)
            except Exception: pass
            try:
                self.tg_manager.download_progress.disconnect(self.update_progress)
            except Exception: pass
            try:
                self.tg_manager.download_finished.disconnect(self.on_download_finished)
            except Exception: pass

        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.setWindowTitle("Descargar nuevo contenido desde Telegram")
        self.resize(800, 700)
        self.layout = QVBoxLayout(self)

        self.layout.addWidget(QLabel("Últimos videos del canal/grupo:"))
        self.video_list_widget = QWidget()
        self.video_list_layout = QVBoxLayout(self.video_list_widget)
        self.video_scroll = QScrollArea()
        self.video_scroll.setWidgetResizable(True)
        self.video_scroll.setWidget(self.video_list_widget)
        self.layout.addWidget(self.video_scroll)

        dest_group = QGroupBox("Destino de descarga")
        dest_layout = QGridLayout()
        dest_layout.addWidget(QLabel("Año:"), 0, 0)
        self.year_combo = QComboBox()
        current_year = datetime.now().year
        for y in range(2004, current_year + 1):
            self.year_combo.addItem(str(y))
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.currentTextChanged.connect(self.update_master_subfolders)
        dest_layout.addWidget(self.year_combo, 0, 1)

        dest_layout.addWidget(QLabel("Carpeta Master:"), 1, 0)
        self.master_combo = QComboBox()
        self.master_combo.currentTextChanged.connect(self.update_first_file_label)
        dest_layout.addWidget(self.master_combo, 1, 1)

        dest_layout.addWidget(QLabel("Primer archivo actual:"), 2, 0)
        self.first_file_label = QLabel("N/A")
        self.first_file_label.setStyleSheet("font-weight: bold; color: #4282da;")
        dest_layout.addWidget(self.first_file_label, 2, 1)
        dest_group.setLayout(dest_layout)
        self.layout.addWidget(dest_group)

        self.layout.addWidget(QLabel("Opciones de renombrado:"))
        self.rename_widget = QWidget()
        self.rename_layout = QVBoxLayout(self.rename_widget)
        self.rename_scroll = QScrollArea()
        self.rename_scroll.setWidgetResizable(True)
        self.rename_scroll.setWidget(self.rename_widget)
        self.layout.addWidget(self.rename_scroll)

        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Listo")
        self.layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.btn_reload = QPushButton("Recargar")
        self.btn_reload.clicked.connect(self.fetch_latest_videos)
        btn_layout.addWidget(self.btn_reload)

        self.btn_download = QPushButton("Descargar")
        self.btn_download.clicked.connect(self.start_downloads)
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_close)
        self.layout.addLayout(btn_layout)

        self.video_items = []
        self._apply_to_all_choice = None

        if self.config.get_cache("first_files") is None:
            self.config.set_cache("first_files", {})

        if self.tg_manager:
            self.tg_manager.videos_loaded.connect(self.populate_videos)
            self.tg_manager.download_progress.connect(self.update_progress)
            self.tg_manager.download_finished.connect(self.on_download_finished)
            self.tg_manager.connection_status.connect(self.on_connection_status_changed)
            self.tg_manager.auth_required.connect(self.handle_tg_auth)

        self.update_master_subfolders()
        self.fetch_latest_videos()

    def fetch_latest_videos(self):
        chat_id = self.config.get("telegram.chat_id")
        if chat_id and self.tg_manager:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.tg_manager.fetch_videos(chat_id, limit=5)
        elif not chat_id:
            QMessageBox.warning(self, "Telegram", "No se ha seleccionado un chat de destino en Configuración.")

    def populate_videos(self, videos):
        QApplication.restoreOverrideCursor()
        while self.video_list_layout.count():
            item = self.video_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        while self.rename_layout.count():
            item = self.rename_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        self.video_items = []
        for v in videos:
            v_widget = QWidget()
            v_layout = QHBoxLayout(v_widget)
            cb = QCheckBox(f"{v['file_name']} ({v['date']})")
            v_layout.addWidget(cb)
            self.video_list_layout.addWidget(v_widget)

            r_widget = QWidget()
            r_layout = QHBoxLayout(r_widget)
            msg_label = QLabel(v['text'][:50] + "..." if len(v['text']) > 50 else v['text'] or v['file_name'])
            msg_label.setToolTip(v['text'])
            r_layout.addWidget(msg_label, 1)

            ren_cb = QCheckBox("Renombrar:")
            r_layout.addWidget(ren_cb)
            ren_input = QLineEdit()
            ren_input.setPlaceholderText("Nuevo nombre de archivo...")
            ren_input.setEnabled(False)
            ren_cb.toggled.connect(ren_input.setEnabled)
            r_layout.addWidget(ren_input, 2)

            self.rename_layout.addWidget(r_widget)
            r_widget.hide()
            cb.toggled.connect(r_widget.setVisible)

            self.video_items.append({
                'cb': cb, 'video': v, 'ren_cb': ren_cb,
                'ren_input': ren_input, 'rename_widget': r_widget
            })

    def update_master_subfolders(self):
        year = self.year_combo.currentText()
        base_path = self.config.get("base_dir_path")
        year_path = os.path.join(base_path, year)
        self.master_combo.clear()
        if os.path.exists(year_path):
            try:
                master_parent = None
                for item in os.listdir(year_path):
                    if "___" in item and os.path.isdir(os.path.join(year_path, item)):
                        master_parent = os.path.join(year_path, item)
                        break
                if master_parent:
                    subfolders = [d for d in os.listdir(master_parent) if os.path.isdir(os.path.join(master_parent, d))]
                    self.master_combo.addItems(sorted(subfolders))
            except Exception as e:
                print(f"Error scanning master subfolders: {e}")

    def update_first_file_label(self):
        year = self.year_combo.currentText()
        subfolder = self.master_combo.currentText()
        if not subfolder:
            self.first_file_label.setText("N/A")
            return
        cache_key = f"{year}_{subfolder}"
        cache = self.config.get_cache("first_files", {})
        if cache_key in cache:
            self.first_file_label.setText(cache[cache_key])
            return
        base_path = self.config.get("base_dir_path")
        year_path = os.path.join(base_path, year)
        master_parent = None
        if os.path.exists(year_path):
            try:
                for item in os.listdir(year_path):
                    if "___" in item and os.path.isdir(os.path.join(year_path, item)):
                        master_parent = os.path.join(year_path, item)
                        break
            except Exception: pass
        if master_parent and subfolder:
            full_path = os.path.join(master_parent, subfolder)
            if os.path.exists(full_path):
                try:
                    files = [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]
                    if files:
                        files.sort()
                        first_file = files[0]
                        self.first_file_label.setText(first_file)
                        cache[cache_key] = first_file
                        self.config.set_cache("first_files", cache)
                    else:
                        self.first_file_label.setText("Vacia")
                except Exception:
                    self.first_file_label.setText("Error")
            else:
                self.first_file_label.setText("No existe")
        else:
            self.first_file_label.setText("N/A")

    def start_downloads(self):
        self.to_download = [item for item in self.video_items if item['cb'].isChecked()]
        if not self.to_download:
            QMessageBox.warning(self, "Descarga", "No hay videos seleccionados.")
            return
        self._apply_to_all_choice = None
        self.btn_download.setEnabled(False)
        self.download_next()

    def download_next(self):
        if not self.to_download:
            self.status_label.setText("Todas las descargas finalizadas.")
            self.btn_download.setEnabled(True)
            return
        self.current_item = self.to_download.pop(0)
        video = self.current_item['video']
        year = self.year_combo.currentText()
        base_path = self.config.get("base_dir_path")
        year_path = os.path.join(base_path, year)
        master_parent = None
        if os.path.exists(year_path):
            for item in os.listdir(year_path):
                if "___" in item and os.path.isdir(os.path.join(year_path, item)):
                    master_parent = os.path.join(year_path, item)
                    break
        if not master_parent:
            QMessageBox.critical(self, "Error", f"No se encontró carpeta maestra para el año {year}")
            self.btn_download.setEnabled(True)
            return
        dest_folder = os.path.join(master_parent, self.master_combo.currentText())
        if not os.path.exists(dest_folder):
            try: os.makedirs(dest_folder)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo crear carpeta de destino: {e}")
                self.btn_download.setEnabled(True)
                return
        filename = video['file_name']
        if self.current_item['ren_cb'].isChecked() and self.current_item['ren_input'].text():
            ext = os.path.splitext(filename)[1]
            filename = self.current_item['ren_input'].text()
            if not filename.endswith(ext): filename += ext
        dest_path = os.path.join(dest_folder, filename)
        if os.path.exists(dest_path):
            choice = self._apply_to_all_choice
            if choice is None:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Archivo existente")
                msg_box.setText(f"El archivo '{filename}' ya existe.\n¿Qué deseas hacer?")
                msg_box.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
                over_btn = msg_box.addButton("Sobrescribir", QMessageBox.ButtonRole.ActionRole)
                skip_btn = msg_box.addButton("Omitir", QMessageBox.ButtonRole.ActionRole)
                ren_btn = msg_box.addButton("Mantener ambos (renombrar)", QMessageBox.ButtonRole.ActionRole)
                cancel_btn = msg_box.addButton("Cancelar todo", QMessageBox.ButtonRole.RejectRole)
                apply_all_cb = QCheckBox("Aplicar a todo")
                msg_box.setCheckBox(apply_all_cb)
                msg_box.exec()
                if msg_box.clickedButton() == cancel_btn:
                    self.to_download = []
                    self.btn_download.setEnabled(True)
                    return
                elif msg_box.clickedButton() == over_btn: choice = "overwrite"
                elif msg_box.clickedButton() == skip_btn: choice = "skip"
                elif msg_box.clickedButton() == ren_btn: choice = "rename"
                if apply_all_cb.isChecked(): self._apply_to_all_choice = choice
            if choice == "skip":
                self.download_next()
                return
            elif choice == "rename":
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(dest_folder, f"{base}_{counter}{ext}")): counter += 1
                dest_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")
        chat_id = self.config.get("telegram.chat_id")
        if self.tg_manager:
            self.tg_manager.download_video(chat_id, video['id'], dest_path)
        else:
            QMessageBox.critical(self, "Error", "Telegram Manager no disponible.")
            self.btn_download.setEnabled(True)

    def update_progress(self, value, status):
        self.progress_bar.setValue(int(value * 100))
        self.status_label.setText(status)

    def on_download_finished(self, success, message):
        if not self.isVisible(): return
        if success: self.download_next()
        else:
            QMessageBox.critical(self, "Error de descarga", f"Error al descargar: {message}")
            self.btn_download.setEnabled(True)

    def on_connection_status_changed(self, message, connected):
        self.status_label.setText(message)
        if connected and not self.video_items: self.fetch_latest_videos()

    def handle_tg_auth(self, type):
        if not self.isVisible(): return
        if type == "phone":
            phone, ok = QInputDialog.getText(self, "Telegram Auth", "Introduce tu número de teléfono (+...):")
            if ok: self.tg_manager.submit_phone(phone)
        elif type == "code":
            code, ok = QInputDialog.getText(self, "Telegram Auth", "Introduce el código de verificación:")
            if ok: self.tg_manager.submit_code(code)
        elif type == "password":
            pw, ok = QInputDialog.getText(self, "Telegram Auth", "Introduce tu contraseña 2FA:", QLineEdit.EchoMode.Password)
            if ok: self.tg_manager.submit_password(pw)

    def closeEvent(self, event):
        try:
            self.tg_manager.videos_loaded.disconnect(self.populate_videos)
            self.tg_manager.download_progress.disconnect(self.update_progress)
            self.tg_manager.download_finished.disconnect(self.on_download_finished)
            self.tg_manager.connection_status.disconnect(self.on_connection_status_changed)
            self.tg_manager.auth_required.disconnect(self.handle_tg_auth)
        except Exception: pass
        super().closeEvent(event)
