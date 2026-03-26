import sys
import os
import ctypes
from PyQt6.QtWidgets import QApplication, QMessageBox, QDialog, QProgressDialog
from PyQt6.QtCore import Qt, QTimer, QCoreApplication, QThread
from ui.main_window import MainWindow
from db.schema import init_databases, GLOBAL_DB_PATH, get_yearly_db_path, BASE_DIR_PATH
from db.connection import DBConnectionManager
from config_manager import ConfigManager
from core.app_state import AppState, AppMode
from core.drive_monitor import DriveMonitor
from core.api_server import APIServerThread
from core.firebase_manager import FirebaseManager
from ui.workers.telegram_worker import TelegramWorker
from controllers.config_controller import ConfigController
from controllers.network_controller import NetworkController
from sync_manager import SyncManager
from db_operations import DBOperations
from resource_management import ResourceScanner
from data_migration import DataMigrator
import datetime

class AppController:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.state = AppState()
        self.db_conn_manager = DBConnectionManager()
        self.config_ctrl = ConfigController()
        self.network_ctrl = NetworkController()
        self.fb_manager = FirebaseManager()
        self.sync_manager = SyncManager()
        self.api_server_thread = APIServerThread()

        self._init_telegram()
        self.main_window = MainWindow(self)
        self.apply_theme(self.config_manager.get("ui.theme", "Fusion"))
        self.main_window.show()

        drive_letter = os.path.splitdrive(BASE_DIR_PATH)[0].replace(":", "") or "E"
        self.drive_monitor = DriveMonitor(drive_letter)
        self.drive_monitor.drive_status_changed.connect(self.handle_drive_status_change)
        self.handle_drive_status_change(self.drive_monitor.is_available)

        QTimer.singleShot(0, self.delayed_init)

    def _init_telegram(self):
        api_id = self.config_manager.get("telegram.api_id")
        api_hash = self.config_manager.get("telegram.api_hash")
        session_path = os.path.join(self.config_manager.config_dir, "session_telegram")
        self.tg_worker = TelegramWorker(api_id, api_hash, session_path)

    def delayed_init(self):
        self.init_db_connections()
        self.tg_worker.connect()
        if self.state.mode == AppMode.ONLINE:
            self.run_startup_sync()
        self.sync_firebase_journals()
        self.update_api_server_status()

    def apply_theme(self, theme_name):
        if theme_name == "Dark":
            from PyQt6.QtGui import QPalette, QColor
            palette = QPalette()
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
            QApplication.instance().setPalette(palette)
        else:
            QApplication.instance().setStyle(theme_name)

    def init_db_connections(self):
        from db_manager import get_offline_db_path, is_on_external_drive
        g_path = GLOBAL_DB_PATH
        is_ro = self.state.mode == AppMode.OFFLINE and is_on_external_drive(g_path)
        if is_ro: g_path = get_offline_db_path(g_path)

        self.db_conn_manager.open_connection("global_db", g_path, readonly=is_ro)
        for tab in self.main_window.global_tabs: tab.update_database("global_db")
        self.open_year_db(self.main_window.get_current_year())

    def open_year_db(self, year):
        from db_manager import get_offline_db_path
        y_path = get_yearly_db_path(year)
        is_ro = self.state.mode == AppMode.OFFLINE
        if is_ro: y_path = get_offline_db_path(y_path)

        self.db_conn_manager.open_connection("year_db", y_path, readonly=is_ro)
        g_path = GLOBAL_DB_PATH
        from db_manager import is_on_external_drive
        if self.state.mode == AppMode.OFFLINE and is_on_external_drive(g_path):
            g_path = get_offline_db_path(g_path)
        self.db_conn_manager.safe_attach("year_db", g_path, "global_db")
        self.main_window.registry_tab.update_database("year_db")
        self.main_window.resources_tab.update_database("year_db")

    def handle_drive_status_change(self, is_available):
        was_offline = self.state.mode == AppMode.OFFLINE
        if was_offline and is_available: self.sync_and_reconnect(offline=False)
        elif not was_offline and not is_available: self.sync_and_reconnect(offline=True)

    def sync_and_reconnect(self, offline):
        if self.state.reconnecting: return
        self.state.reconnecting = True
        try:
            self.state.mode = AppMode.OFFLINE if offline else AppMode.ONLINE
            self.main_window.update_offline_mode(offline)
            self.db_conn_manager.close_all(self.main_window.all_tabs)
            if not offline: self.run_startup_sync(callback=self.init_db_connections)
            else: self.init_db_connections()
        finally: self.state.reconnecting = False

    def run_startup_sync(self, callback=None):
        from db_manager import get_offline_db_path, is_on_external_drive
        tasks = []
        if is_on_external_drive(GLOBAL_DB_PATH):
            tasks.append((GLOBAL_DB_PATH, get_offline_db_path(GLOBAL_DB_PATH), "Sincronizando Global DB..."))
        for year in range(2004, datetime.datetime.now().year + 1):
            y_path = get_yearly_db_path(year)
            if os.path.exists(y_path):
                tasks.append((y_path, get_offline_db_path(y_path), f"Sincronizando año {year}..."))
        if not tasks:
            if callback: callback()
            return
        self.sync_manager.perform_sync(tasks)
        if callback: callback()

    def sync_firebase_journals(self):
        if self.config_manager.get("firebase.db_url"): self.fb_manager.download_journals()

    def update_api_server_status(self):
        if self.config_manager.get("api.enabled", False):
            if not self.api_server_thread.isRunning(): self.api_server_thread.start()

    def run_operation(self, op_name):
        if self.state.mode == AppMode.OFFLINE and op_name not in ["recalc_lapses", "recalc_models"]:
            QMessageBox.warning(self.main_window, "Modo Offline", "Operación no disponible en solo lectura.")
            return

        if op_name == "scan_masters":
            DBOperations().scan_master_folders()
            self.main_window.global_subtabs.widget(3).model.select()
        elif op_name == "migrate_resources":
            self._run_threaded_op(DataMigrator().migrate_resources, "Migrando recursos...", self.main_window.resources_tab)
        elif op_name == "migrate_registry":
            self._run_threaded_op(DataMigrator().migrate_registry, "Migrando registros...", self.main_window.registry_tab)
        elif op_name == "recalc_lapses":
            DBOperations().recalculate_registry_lapses("year_db")
            self.main_window.registry_tab.model.select()
        elif op_name == "recalc_models":
            DBOperations().recalculate_registry_models("year_db")
            self.main_window.registry_tab.model.select()

    def _run_threaded_op(self, func, label, tab_to_refresh):
        progress = QProgressDialog(label, "Cancelar", 0, 100, self.main_window)
        progress.show()
        # This is a simplification of the complex threading in original main.pyw
        func()
        if tab_to_refresh: tab_to_refresh.model.select()
        progress.close()

    def run_dialog(self, dialog_name):
        if dialog_name == "report_materials":
            from dialogs.report_materials import ReportMaterialsDialog
            self.sync_firebase_journals()
            if ReportMaterialsDialog(self.main_window).exec() == QDialog.DialogCode.Accepted:
                self.main_window.registry_tab.model.select()
        elif dialog_name == "tg_download":
            from dialogs.telegram_download import TelegramDownloadDialog
            TelegramDownloadDialog(self.main_window, self.tg_worker).exec()
        elif dialog_name == "manage_journals":
            from journals_manager.journal_gui import JournalAdminDialog
            self.sync_firebase_journals()
            JournalAdminDialog(self.main_window).exec()

    def save_settings(self): self.config_manager.save()
    def shutdown(self):
        if hasattr(self, 'tg_worker'): self.tg_worker.shutdown()

if __name__ == "__main__":
    if os.name == 'nt': ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('storeetude.precuremanager.desktopcenter.1')
    init_databases()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    ctrl = AppController()
    sys.exit(app.exec())
