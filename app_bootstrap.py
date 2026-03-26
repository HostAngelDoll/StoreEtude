import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from ui.main_window import MainWindow
from db.schema import init_databases
from db.connection import DBConnectionManager
from config_manager import ConfigManager
from core.app_state import AppState, AppMode
from ui.workers.telegram_worker import TelegramWorker
from controllers.config_controller import ConfigController
from controllers.network_controller import NetworkController

class AppController:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.state = AppState()
        self.db_conn_manager = DBConnectionManager()
        self.config_ctrl = ConfigController()
        self.network_ctrl = NetworkController()

        # Init Telegram Worker
        api_id = self.config_manager.get("telegram.api_id")
        api_hash = self.config_manager.get("telegram.api_hash")
        session_path = os.path.join(self.config_manager.config_dir, "session_telegram")
        self.tg_worker = TelegramWorker(api_id, api_hash, session_path)

        self.main_window = MainWindow(self)
        self.main_window.show()

        QTimer.singleShot(0, self.delayed_init)

    def delayed_init(self):
        self.init_db_connections()
        self.tg_worker.connect()

    def init_db_connections(self):
        from db.schema import GLOBAL_DB_PATH
        self.db_conn_manager.open_connection("global_db", GLOBAL_DB_PATH)
        for tab in self.main_window.global_tabs:
            tab.update_database("global_db")
        self.open_year_db(2004)

    def open_year_db(self, year):
        from db.schema import get_yearly_db_path, GLOBAL_DB_PATH
        y_path = get_yearly_db_path(year)
        self.db_conn_manager.open_connection("year_db", y_path)
        self.db_conn_manager.safe_attach("year_db", GLOBAL_DB_PATH, "global_db")
        self.main_window.registry_tab.update_database("year_db")
        self.main_window.resources_tab.update_database("year_db")

    def shutdown(self):
        if hasattr(self, 'tg_worker'):
            self.tg_worker.shutdown()

if __name__ == "__main__":
    if os.name == 'nt':
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('storeetude.precuremanager.desktopcenter.1')

    init_databases()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    ctrl = AppController()
    sys.exit(app.exec())
