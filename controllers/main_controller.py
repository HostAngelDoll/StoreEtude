import os
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QProgressDialog, QDialog
from PyQt6.QtCore import Qt, QThread, QTimer, QObject

from core.db_manager_utils import get_base_dir_path, get_yearly_db_path, refresh_config_paths
from core.config_manager import ConfigManager
from core.drive_monitor import DriveMonitor
from core.app_state import AppState, AppMode
from core.api_server import APIServerThread
from db.session_manager import DBSessionManager
from services.sync_service import SyncService
from services.scanner_service import ScannerService
from services.migration_service import MigrationService
from services.db_service import DBService
from services.telegram.telegram_service import TelegramService
from controllers.telegram_controller import TelegramController

from dialogs import (YearRangeDialog, ReportMaterialsDialog,
                     DuplicateActionDialog, SettingsDialog)
from journals_manager.journal_gui import JournalAdminDialog

class MainController(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.win = main_window
        self.config = ConfigManager()
        self.state = AppState()

        self.db_session = DBSessionManager(self.state, self.db_manager if hasattr(self, 'db_manager') else None)
        self.sync_service = SyncService(self.config)
        self.scanner_service = ScannerService()
        self.migration_service = MigrationService()
        self.db_service = DBService()
        self.telegram_service = TelegramService()
        self.tg_controller = TelegramController(self.win, self.telegram_service)

        self.api_server_thread = APIServerThread()
        self.last_device_change = 0

        self._setup_connections()
        self._init_drive_monitor()

        QTimer.singleShot(0, self.delayed_init)

    def _setup_connections(self):
        self.win.year_selected.connect(self.on_year_selected)
        self.win.report_materials_requested.connect(self.on_report_materials_requested)
        self.win.tg_download_requested.connect(self.on_tg_download_requested)
        self.win.manage_journals_requested.connect(self.on_manage_journals_requested)
        self.win.scan_master_folders_requested.connect(self.scan_master_folders)
        self.win.update_links_requested.connect(self.on_update_links_requested)
        self.win.scan_link_requested.connect(self.on_scan_link_requested)
        self.win.scan_new_sd_requested.connect(self.on_scan_new_sd_requested)
        self.win.migrate_resources_requested.connect(self.migrate_resources_from_excel)
        self.win.migrate_registry_requested.connect(self.migrate_registry_from_excel)
        self.win.regenerate_index_requested.connect(self.regenerate_registry_index)
        self.win.recalculate_lapses_requested.connect(self.recalculate_registry_lapses)
        self.win.recalculate_models_requested.connect(self.recalculate_registry_models)
        self.win.auto_resize_toggled.connect(self.win.set_auto_resize_columns)
        self.win.console_toggled.connect(self.win.toggle_sql_consoles)
        self.win.settings_requested.connect(self.on_settings_requested)
        self.win.save_requested.connect(self.save_settings)
        self.win.export_requested.connect(self.export_active_tab)
        self.win.import_requested.connect(self.import_active_tab)
        self.win.add_row_requested.connect(self.add_row_to_active_tab)
        self.win.resize_requested.connect(self.resize_active_tab)

    def _init_drive_monitor(self):
        drive_letter = os.path.splitdrive(get_base_dir_path())[0].replace(":", "")
        self.drive_monitor = DriveMonitor(drive_letter or "E")
        self.drive_monitor.drive_status_changed.connect(self.handle_drive_status_change)
        self.handle_drive_status_change(self.drive_monitor.is_available)

    def delayed_init(self):
        self.win.apply_theme(self.config.get("ui.theme", "Fusion"))
        self.init_db_connections()
        self.load_settings()
        self.win.restore_geometry_safe(self.config.get("ui.geometry"), self.config.get("ui.maximized", True))

        if self.state.mode == AppMode.ONLINE:
            self.run_startup_sync()

        self.sync_firebase_journals()
        self.update_api_server_status()

    def init_db_connections(self):
        conn_name = self.db_session.init_global_connection()
        for tab in self.win.global_tabs:
            tab.update_database(conn_name)
        self.on_year_selected(self.win.get_current_year())

    def on_year_selected(self, year):
        if self.db_session.open_year_db(year):
            self.win.resources_tab.update_database("year_db")
            self.win.registry_tab.update_database("year_db")

    def handle_drive_status_change(self, is_available):
        was_offline = self.state.mode == AppMode.OFFLINE
        if was_offline and is_available:
            self.sync_and_reconnect(offline=False)
        elif not was_offline and not is_available:
            self.sync_and_reconnect(offline=True)

    def sync_and_reconnect(self, offline):
        if self.state.reconnecting: return
        self.state.reconnecting = True
        try:
            self.state.mode = AppMode.OFFLINE if offline else AppMode.ONLINE
            self.win.set_offline_mode(offline)
            progress = self.win.create_progress_dialog("Cambiando modo de base de datos...", cancelable=False)
            progress.setRange(0, 0); progress.show()
            QApplication.processEvents()

            self.db_session.close_all(self.win.all_tabs)

            if not offline:
                self.run_startup_sync(callback=lambda: self.finish_reconnect(progress))
            else:
                self.finish_reconnect(progress)
        finally:
            self.state.reconnecting = False

    def finish_reconnect(self, progress_dialog):
        self.init_db_connections()
        progress_dialog.close()

    def run_startup_sync(self, callback=None):
        tasks = self.sync_service.get_startup_sync_tasks()
        if not tasks:
            if callback: callback()
            return

        self.sync_progress = self.win.create_progress_dialog("Sincronizando bases de datos...", title="Sincronización")

        def on_finished(success, msg):
            self.sync_service.disconnect_sync_signals()
            self.sync_progress.close()
            if not success:
                self.win.show_error(f"Problema al sincronizar: {msg}", "Sincronización")
            if callback: callback()

        def update_sync_progress(cur, tot, lbl):
            self.sync_progress.setLabelText(lbl)
            self.sync_progress.setValue(int(cur/tot*100 if tot > 0 else 100))

        self.sync_service.perform_sync(tasks, update_sync_progress, on_finished)

    def on_report_materials_requested(self):
        self.sync_firebase_journals()
        dialog = ReportMaterialsDialog(self.win)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.win.registry_tab.model.select()

    def on_tg_download_requested(self):
        self.tg_controller.show_download_dialog()

    def on_manage_journals_requested(self):
        self.sync_firebase_journals()
        dialog = JournalAdminDialog(self.win)
        dialog.exec()

    def on_settings_requested(self):
        old_global_path = self.config.get("global_db_path")
        dialog = SettingsDialog(self.win, self.telegram_service.get_manager())
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_global_path = self.config.get("global_db_path")
            if new_global_path != old_global_path:
                self.db_session.close_all(self.win.all_tabs)
                if not self.config.move_global_db_file(new_global_path):
                    self.win.show_error("No se pudo mover la base de datos global. Se intentará reconectar de todas formas.")

            self.config.load()
            refresh_config_paths()
            self.win.apply_theme(self.config.get("ui.theme"))
            self.load_settings()
            self.tg_controller.reset_client()
            self.init_db_connections()

    def scan_master_folders(self):
        if self.state.mode == AppMode.OFFLINE:
            self.win.show_error("No se puede escanear en modo solo lectura.", "Escaneo")
            return
        self.db_service.scan_master_folders()
        self.win.seasons_tab.model.select()
        self.win.show_info("Escaneo de carpetas maestras finalizado.", "Escaneo")

    def on_update_links_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            self.win.show_error("No se puede vincular en modo solo lectura.", "Vinculación")
            return
        year = self.win.get_current_year()
        self.scan_and_link_resources_ui([year], overwrite=False)

    def on_scan_link_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            self.win.show_error("No se puede escanear en modo solo lectura.", "Escaneo")
            return
        current_year = self.win.get_current_year()
        dialog = YearRangeDialog(current_year, self.win)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            years = dialog.get_years(current_year)
            self.scan_and_link_resources_ui(years, overwrite=True)

    def on_scan_new_sd_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            self.win.show_error("No se puede buscar en modo solo lectura.", "Búsqueda")
            return
        current_year = self.win.get_current_year()
        dialog = YearRangeDialog(current_year, self.win)
        dialog.setWindowTitle("Buscar nuevas soundtracks")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            years = dialog.get_years(current_year)
            self.scan_new_soundtracks_ui(years)

    def scan_and_link_resources_ui(self, years, overwrite=True):
        progress = self.win.create_progress_dialog("Escaneando y vinculando recursos...", title="Trabajando con años")
        progress.setMaximum(len(years))

        self.scan_thread = QThread()
        scanner = self.scanner_service.get_scanner()
        scanner.moveToThread(self.scan_thread)

        def update_progress(cur, tot, lbl):
            progress.setMaximum(tot); progress.setValue(cur); progress.setLabelText(lbl)

        def on_finished():
            self.scan_thread.quit(); self.win.resources_tab.model.select(); progress.close()
            self.win.show_info("Proceso completado.", "Escaneo")

        scanner.progress_changed.connect(update_progress)
        scanner.log_message.connect(self.win.log)
        scanner.warning_emitted.connect(self.win.show_error)
        scanner.finished.connect(on_finished)
        progress.canceled.connect(self.scanner_service.cancel)
        self.scan_thread.started.connect(lambda: self.scanner_service.scan_and_link(years, overwrite))
        self.scan_thread.start(); progress.show()

    def scan_new_soundtracks_ui(self, years):
        progress = self.win.create_progress_dialog("Buscando nuevas soundtracks...", title="Trabajando con años")
        progress.setMaximum(len(years))

        self.sd_scan_thread = QThread()
        scanner = self.scanner_service.get_scanner()
        scanner.moveToThread(self.sd_scan_thread)

        def update_progress(cur, tot, lbl):
            progress.setMaximum(tot); progress.setValue(cur); progress.setLabelText(lbl)

        def handle_duplicate(title):
            diag = DuplicateActionDialog(title, self.win); diag.exec()
            self.scanner_service.set_duplicate_choice(*diag.get_choice())

        def on_finished():
            self.sd_scan_thread.quit(); self.win.resources_tab.model.select(); progress.close()
            self.win.show_info("Proceso de búsqueda de soundtracks finalizado.", "Búsqueda")

        scanner.progress_changed.connect(update_progress)
        scanner.log_message.connect(self.win.log)
        scanner.request_duplicate_action.connect(handle_duplicate, Qt.ConnectionType.BlockingQueuedConnection)
        scanner.finished.connect(on_finished)
        progress.canceled.connect(self.scanner_service.cancel)
        self.sd_scan_thread.started.connect(lambda: self.scanner_service.scan_new_soundtracks(years))
        self.sd_scan_thread.start(); progress.show()

    def migrate_resources_from_excel(self):
        if self.state.mode == AppMode.OFFLINE:
            self.win.show_error("No se puede migrar en modo solo lectura.", "Migración")
            return
        progress = self.win.create_progress_dialog("Migrando recursos...", title="Trabajando con años")

        self.migrator_thread = QThread()
        migrator = self.migration_service.get_migrator()
        migrator.moveToThread(self.migrator_thread)

        def on_finished(count):
            self.migrator_thread.quit(); self.win.resources_tab.model.select()
            if not progress.wasCanceled(): self.win.show_info(f"Proceso finalizado. Se migraron {count} recursos.")
            progress.close()

        migrator.progress_changed.connect(lambda c, t, l: (progress.setMaximum(t), progress.setValue(c), progress.setLabelText(l)))
        migrator.log_message.connect(self.win.log)
        migrator.finished.connect(on_finished)
        progress.canceled.connect(self.migration_service.cancel)
        self.migrator_thread.started.connect(self.migration_service.migrate_resources)
        self.migrator_thread.start(); progress.show()

    def migrate_registry_from_excel(self):
        if self.state.mode == AppMode.OFFLINE:
            self.win.show_error("No se puede migrar en modo solo lectura.", "Migración")
            return
        progress = self.win.create_progress_dialog("Migrando registros...", title="Trabajando con años")

        self.reg_mig_thread = QThread()
        migrator = self.migration_service.get_migrator()
        migrator.moveToThread(self.reg_mig_thread)

        def on_finished(count):
            self.reg_mig_thread.quit(); self.win.registry_tab.model.select()
            if not progress.wasCanceled(): self.win.show_info(f"Proceso finalizado. Se migraron {count} registros.")
            progress.close()

        def handle_confirmation(year, message):
            res = self.win.ask_confirmation(message + " Se recomienda hacer un respaldo manual antes.", "Advertencia")
            self.migration_service.set_confirmation_result(res)

        migrator.progress_changed.connect(lambda c, t, l: (progress.setMaximum(t), progress.setValue(c), progress.setLabelText(l)))
        migrator.log_message.connect(self.win.log)
        migrator.finished.connect(on_finished)
        migrator.request_confirmation.connect(handle_confirmation, Qt.ConnectionType.BlockingQueuedConnection)
        progress.canceled.connect(self.migration_service.cancel)
        self.reg_mig_thread.started.connect(self.migration_service.migrate_registry)
        self.reg_mig_thread.start(); progress.show()

    def regenerate_registry_index(self):
        if self.state.mode == AppMode.OFFLINE:
            self.win.show_error("No se puede regenerar en modo solo lectura.", "Regenerar Índice")
            return
        current_year = self.win.get_current_year()
        dialog = YearRangeDialog(current_year, self.win)
        dialog.setWindowTitle("Regenerar columna index")
        if dialog.exec() != QDialog.DialogCode.Accepted: return

        years = dialog.get_years(current_year)
        progress = self.win.create_progress_dialog("Regenerando índices...", title="Procesando años")

        self.ops_thread = QThread()
        worker = self.db_service.get_operations_worker()
        worker.moveToThread(self.ops_thread)

        def on_finished(msg):
            self.ops_thread.quit(); self.win.registry_tab.model.select()
            if not progress.wasCanceled(): self.win.show_info(msg, "Regenerar Índice")
            progress.close()

        worker.progress_changed.connect(lambda c, t, l: (progress.setMaximum(t), progress.setValue(c), progress.setLabelText(l)))
        worker.log_message.connect(self.win.log)
        worker.finished.connect(on_finished)
        progress.canceled.connect(self.db_service.cancel)
        self.ops_thread.started.connect(lambda: self.db_service.regenerate_index(years))
        self.ops_thread.start(); progress.show()

    def recalculate_registry_lapses(self):
        if self.state.mode == AppMode.OFFLINE:
            self.win.show_error("No se puede recalcular en modo solo lectura.", "Lapsos")
            return
        self.db_service.recalculate_lapses("year_db")
        self.win.registry_tab.model.select(); self.win.show_info("Lapsos recalculados.", "Lapsos")

    def recalculate_registry_models(self):
        if self.state.mode == AppMode.OFFLINE:
            self.win.show_error("No se puede recalcular en modo solo lectura.", "Modelos")
            return
        self.db_service.recalculate_models("year_db")
        self.win.registry_tab.model.select(); self.win.show_info("Modelos recalculados.", "Modelos")

    def sync_firebase_journals(self):
        def update_fb_progress(cur, tot, lbl):
            progress.setMaximum(tot); progress.setValue(cur); progress.setLabelText(lbl)
            QApplication.processEvents()

        progress = self.win.create_progress_dialog("Sincronizando jornadas con Firebase...", title="Firebase Sync", cancelable=False)
        progress.show()
        success, msg = self.sync_service.sync_firebase_journals(progress_callback=update_fb_progress)
        progress.close()

        if not success: self.win.log(f"Firebase Sync Error: {msg}", is_error=True)
        else: self.win.log(msg)

    def update_api_server_status(self):
        if self.config.get("api.enabled", False):
            if not self.api_server_thread.isRunning(): self.api_server_thread.start()

    def load_settings(self):
        self.win.dock.setVisible(self.config.get("ui.sidebar_visible", True))
        self.win.actions.toggle_sidebar.setChecked(self.config.get("ui.sidebar_visible", True))
        self.win.actions.toggle_console.setChecked(self.config.get("ui.console_visible", True))
        self.win.toggle_sql_consoles(self.config.get("ui.console_visible", True))
        self.win.actions.auto_resize_action.setChecked(self.config.get("ui.auto_resize", True))
        self.win.set_auto_resize_columns(self.config.get("ui.auto_resize", True))
        self.win.actions.show_construction_logs.setChecked(self.config.get("ui.show_construction_logs", False))

    def save_settings(self):
        if not self.win.isMinimized():
            geo = self.win.get_geometry_base64()
            if geo: self.config.set("ui.geometry", geo)
            self.config.set("ui.maximized", self.win.isMaximized())

        self.config.set("ui.sidebar_visible", self.win.dock.isVisible())
        self.config.set("ui.console_visible", self.win.registry_tab.console_area.isVisible())
        self.config.save()

    def export_active_tab(self):
        tab = self.win.get_active_tab_widget()
        if hasattr(tab, 'export_to_csv'): tab.export_to_csv()

    def import_active_tab(self):
        if self.state.mode == AppMode.OFFLINE: return
        tab = self.win.get_active_tab_widget()
        if hasattr(tab, 'import_from_csv'): tab.import_from_csv()

    def add_row_to_active_tab(self):
        tab = self.win.get_active_tab_widget()
        if hasattr(tab, 'add_record'): tab.add_record()

    def resize_active_tab(self):
        tab = self.win.get_active_tab_widget()
        if hasattr(tab, 'resize_to_contents'): tab.resize_to_contents()

    def shutdown(self):
        self.save_settings(); self.tg_controller.shutdown()
