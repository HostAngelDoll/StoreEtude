from PyQt6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QPushButton, QLabel, QProgressBar
from PyQt6.QtCore import Qt

class TelegramDownloadDialog(QDialog):
    def __init__(self, parent, telegram_worker):
        super().__init__(parent)
        self.telegram_worker = telegram_worker
        self.setWindowTitle("Descargar de Telegram")
        self.resize(600, 400)
        self.init_ui()
        self.setup_signals()

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.status_label = QLabel("Estado: Desconectado")
        layout.addWidget(self.status_label)

        self.chat_list = QListWidget()
        layout.addWidget(QLabel("Selecciona un chat:"))
        layout.addWidget(self.chat_list)

        self.video_list = QListWidget()
        layout.addWidget(QLabel("Selecciona videos:"))
        layout.addWidget(self.video_list)

        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        self.btn_download = QPushButton("Descargar Seleccionados")
        self.btn_download.clicked.connect(self.on_download_clicked)
        layout.addWidget(self.btn_download)

        self.btn_load_chats = QPushButton("Cargar Chats")
        self.btn_load_chats.clicked.connect(self.telegram_worker.fetch_chats)
        layout.addWidget(self.btn_load_chats)

    def setup_signals(self):
        self.telegram_worker.connection_status.connect(self.on_connection_status)
        self.telegram_worker.chats_loaded.connect(self.on_chats_loaded)
        self.telegram_worker.videos_loaded.connect(self.on_videos_loaded)
        self.telegram_worker.download_progress.connect(self.on_download_progress)
        self.telegram_worker.download_finished.connect(self.on_download_finished)

    def on_connection_status(self, status, connected):
        self.status_label.setText(f"Estado: {status}")
        self.btn_download.setEnabled(connected)

    def on_chats_loaded(self, chats):
        self.chat_list.clear()
        for c in chats: self.chat_list.addItem(f"{c['name']} (ID: {c['id']})")

    def on_videos_loaded(self, videos):
        self.video_list.clear()
        for v in videos: self.video_list.addItem(f"{v['file_name']} - {v['text']}")

    def on_download_progress(self, percent, text):
        self.progress_bar.setValue(int(percent * 100))
        self.status_label.setText(text)

    def on_download_finished(self, success, msg):
        self.status_label.setText("Descarga finalizada" if success else f"Error: {msg}")

    def on_download_clicked(self):
        # Implementation of selected video downloads via telegram_worker
        pass
