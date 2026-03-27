import os
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from db.connection import DBConnectionManager
from core.db_manager_utils import (get_global_db_path, get_offline_db_path,
                                  get_yearly_db_path, is_on_external_drive)
from core.app_state import AppState, AppMode

class DBSessionManager(QObject):
    session_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.db_manager = DBConnectionManager()
        self.state = AppState()
        self.current_year = None

    def init_global_connection(self):
        g_path = get_global_db_path()
        is_ro = False
        if self.state.mode == AppMode.OFFLINE and is_on_external_drive(g_path):
            g_path = get_offline_db_path(g_path)
            is_ro = True

        self.db_manager.open_connection("global_db", g_path, readonly=is_ro)
        return "global_db"

    def open_year_db(self, year):
        if not year:
            return False

        self.current_year = year
        y_path = get_yearly_db_path(year)
        is_ro = False
        if self.state.mode == AppMode.OFFLINE:
            y_path = get_offline_db_path(y_path)
            is_ro = True

        self.db_manager.open_connection("year_db", y_path, readonly=is_ro)

        g_path = get_global_db_path()
        if self.state.mode == AppMode.OFFLINE and is_on_external_drive(g_path):
            g_path = get_offline_db_path(g_path)

        self.db_manager.safe_attach("year_db", g_path, "global_db")
        self.session_changed.emit()
        return True

    def close_all(self, tabs):
        self.db_manager.close_all(tabs)

    def get_connection(self, name):
        return self.db_manager.get_connection(name)
