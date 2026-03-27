from PyQt6.QtWidgets import QDialog
from dialogs import TelegramDownloadDialog
from services.telegram.telegram_service import TelegramService

class TelegramController:
    def __init__(self, main_window, telegram_service: TelegramService):
        self.win = main_window
        self.service = telegram_service

    def show_download_dialog(self):
        dialog = TelegramDownloadDialog(self.win, self.service.get_manager())
        dialog.exec()

    def reset_client(self):
        self.service.reset_client()

    def shutdown(self):
        self.service.shutdown()
