import os
from datetime import datetime
from PyQt6.QtWidgets import QApplication, QMessageBox, QProgressDialog, QDialog
from PyQt6.QtCore import Qt, QByteArray, QThread, QTimer, QObject
from PyQt6.QtGui import QPalette, QColor

from core.db_manager_utils import (get_base_dir_path, get_global_db_path, get_yearly_db_path,
                                  get_offline_db_path, is_on_external_drive)
from core.config_manager import ConfigManager
from core.db_connection_manager import DBConnectionManager
from core.drive_monitor import DriveMonitor
from core.app_state import AppState, AppMode
from core.api_server import APIServerThread
from core.firebase_manager import FirebaseManager
from core.telegram_manager import TelegramManager
from core.sync_manager import SyncManager
from core.db_operations import DBOperations
from core.resource_management import ResourceScanner
from data_migration import DataMigrator

from dialogs import (YearRangeDialog, ReportMaterialsDialog,
                     TelegramDownloadDialog, DuplicateActionDialog, SettingsDialog)
from journals_manager.journal_gui import JournalAdminDialog

class MainController(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.win = main_window
        self.config = ConfigManager()
        self.state = AppState()
        self.db_manager = DBConnectionManager()
        self.tg_manager = TelegramManager()
        self.sync_manager = SyncManager()
        self.api_server_thread = APIServerThread()
        self.fb_manager = FirebaseManager()

        self.last_device_change = 0

        self._setup_connections()
        self._init_drive_monitor()

        # Defer DB init until after UI is fully ready
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

        # Initial Drive check
        self.handle_drive_status_change(self.drive_monitor.is_available)

    def delayed_init(self):
        self.apply_theme(self.config.get("ui.theme", "Fusion"))
        self.init_db_connections()
        self.load_settings()
        self.restore_window_geometry_safe()

        if self.state.mode == AppMode.ONLINE:
            self.run_startup_sync()

        self.sync_firebase_journals()
        self.update_api_server_status()

    def init_db_connections(self):
        g_path = get_global_db_path()
        is_ro = False
        if self.state.mode == AppMode.OFFLINE and is_on_external_drive(g_path):
            g_path = get_offline_db_path(g_path)
            is_ro = True

        self.db_manager.open_connection("global_db", g_path, readonly=is_ro)

        for tab in self.win.global_tabs:
            tab.update_database("global_db")

        self.open_year_db(self.win.get_current_year())

    def open_year_db(self, year):
        if not year: return False

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

        self.win.resources_tab.update_database("year_db")
        self.win.registry_tab.update_database("year_db")
        return True

    def on_year_selected(self, year):
        self.open_year_db(year)

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

            progress = QProgressDialog("Cambiando modo de base de datos...", "Cancelar", 0, 0, self.win)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            QApplication.processEvents()

            self.db_manager.close_all(self.win.all_tabs)

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
        tasks = []
        global_db_path = get_global_db_path()
        if is_on_external_drive(global_db_path):
            tasks.append((global_db_path, get_offline_db_path(global_db_path), "Sincronizando Global DB..."))

        for year in range(2004, datetime.now().year + 1):
            y_path = get_yearly_db_path(year)
            if os.path.exists(y_path):
                tasks.append((y_path, get_offline_db_path(y_path), f"Sincronizando año {year}..."))

        if not tasks:
            if callback: callback()
            return

        self.sync_progress = QProgressDialog("Sincronizando bases de datos...", "Cancelar", 0, 100, self.win)
        self.sync_progress.setWindowModality(Qt.WindowModality.WindowModal)

        def on_finished(success, msg):
            try:
                self.sync_manager.task_progress.disconnect()
                self.sync_manager.sync_finished.disconnect()
            except Exception: pass
            self.sync_progress.close()
            if not success:
                QMessageBox.warning(self.win, "Sincronización", f"Problema al sincronizar: {msg}")
            if callback: callback()

        def update_sync_progress(cur, tot, lbl):
            self.sync_progress.setLabelText(lbl)
            self.sync_progress.setValue(int(cur/tot*100 if tot > 0 else 100))

        self.sync_manager.task_progress.connect(update_sync_progress)
        self.sync_manager.sync_finished.connect(on_finished)
        self.sync_manager.perform_sync(tasks)

    def on_report_materials_requested(self):
        self.sync_firebase_journals()
        dialog = ReportMaterialsDialog(self.win)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.win.registry_tab.model.select()

    def on_tg_download_requested(self):
        dialog = TelegramDownloadDialog(self.win, self.tg_manager)
        dialog.exec()

    def on_manage_journals_requested(self):
        self.sync_firebase_journals()
        dialog = JournalAdminDialog(self.win)
        dialog.exec()

    def on_settings_requested(self):
        old_global_path = self.config.get("global_db_path")
        dialog = SettingsDialog(self.win, self.tg_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            new_global_path = self.config.get("global_db_path")

            if new_global_path != old_global_path:
                self.db_manager.close_all(self.win.all_tabs)
                if not self.config.move_global_db_file(new_global_path):
                    QMessageBox.warning(self.win, "Error", "No se pudo mover la base de datos global. Se intentará reconectar de todas formas.")

            self.config.load()
            from core.db_manager_utils import refresh_config_paths
            refresh_config_paths()
            self.apply_theme(self.config.get("ui.theme"))
            self.load_settings()
            if hasattr(self.tg_manager, 'reset_client'):
                self.tg_manager.reset_client()
            self.init_db_connections()

    def scan_master_folders(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self.win, "Escaneo", "No se puede escanear en modo solo lectura.")
            return
        ops = DBOperations()
        ops.scan_master_folders()
        self.win.seasons_tab.model.select()
        QMessageBox.information(self.win, "Escaneo", "Escaneo de carpetas maestras finalizado.")

    def on_update_links_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self.win, "Vinculación", "No se puede vincular en modo solo lectura.")
            return
        year = self.win.get_current_year()
        self.scan_and_link_resources_ui([year], overwrite=False)
        QMessageBox.information(self.win, "Vinculación", f"Proceso de actualización para el año {year} completado.")

    def on_scan_link_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self.win, "Escaneo", "No se puede escanear en modo solo lectura.")
            return
        current_year = self.win.get_current_year()
        dialog = YearRangeDialog(current_year, self.win)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            years = dialog.get_years(current_year)
            self.scan_and_link_resources_ui(years, overwrite=True)
            QMessageBox.information(self.win, "Escaneo", "Proceso de escaneo y vinculación completado.")

    def on_scan_new_sd_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self.win, "Búsqueda", "No se puede buscar en modo solo lectura.")
            return
        current_year = self.win.get_current_year()
        dialog = YearRangeDialog(current_year, self.win)
        dialog.setWindowTitle("Buscar nuevas soundtracks")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            years = dialog.get_years(current_year)
            self.scan_new_soundtracks_ui(years)
            QMessageBox.information(self.win, "Búsqueda", "Proceso de búsqueda de soundtracks finalizado.")

    def scan_and_link_resources_ui(self, years, overwrite=True):
        progress = QProgressDialog("Escaneando y vinculando recursos...", "Cancelar", 0, len(years), self.win)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        self.scan_thread = QThread()
        self.scanner = ResourceScanner()
        self.scanner.moveToThread(self.scan_thread)

        def update_progress(cur, tot, lbl):
            progress.setMaximum(tot)
            progress.setValue(cur)
            progress.setLabelText(lbl)

        def on_finished():
            self.scan_thread.quit()
            self.win.resources_tab.model.select()
            progress.close()

        self.scanner.progress_changed.connect(update_progress)
        self.scanner.log_message.connect(self.win.log)
        self.scanner.warning_emitted.connect(lambda t, m: QMessageBox.warning(self.win, t, m))
        self.scanner.finished.connect(on_finished)

        progress.canceled.connect(self.scanner.cancel)
        self.scan_thread.started.connect(lambda: self.scanner.scan_and_link_resources(years, overwrite))

        self.scan_thread.start()
        progress.show()

    def scan_new_soundtracks_ui(self, years):
        progress = QProgressDialog("Buscando nuevas soundtracks...", "Cancelar", 0, len(years), self.win)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        self.sd_scan_thread = QThread()
        self.sd_scanner = ResourceScanner()
        self.sd_scanner.moveToThread(self.sd_scan_thread)

        def update_progress(cur, tot, lbl):
            progress.setMaximum(tot)
            progress.setValue(cur)
            progress.setLabelText(lbl)

        def handle_duplicate(title):
            diag = DuplicateActionDialog(title, self.win)
            diag.exec()
            self.sd_scanner.set_duplicate_choice(*diag.get_choice())

        def on_finished():
            self.sd_scan_thread.quit()
            self.win.resources_tab.model.select()
            progress.close()

        self.sd_scanner.progress_changed.connect(update_progress)
        self.sd_scanner.log_message.connect(self.win.log)
        self.sd_scanner.request_duplicate_action.connect(handle_duplicate, Qt.ConnectionType.BlockingQueuedConnection)
        self.sd_scanner.finished.connect(on_finished)

        progress.canceled.connect(self.sd_scanner.cancel)
        self.sd_scan_thread.started.connect(lambda: self.sd_scanner.scan_new_soundtracks_lyrics(years))

        self.sd_scan_thread.start()
        progress.show()

    def migrate_resources_from_excel(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self.win, "Migración", "No se puede migrar en modo solo lectura.")
            return

        progress = QProgressDialog("Migrando recursos...", "Cancelar", 0, 100, self.win)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        self.migrator_thread = QThread()
        self.migrator = DataMigrator()
        self.migrator.moveToThread(self.migrator_thread)

        def update_progress(cur, tot, lbl):
            progress.setMaximum(tot)
            progress.setValue(cur)
            progress.setLabelText(lbl)

        def on_finished(count):
            self.migrator_thread.quit()
            self.win.resources_tab.model.select()
            if not progress.wasCanceled():
                QMessageBox.information(self.win, "Migración", f"Proceso finalizado. Se migraron {count} recursos.")
            progress.close()

        self.migrator.progress_changed.connect(update_progress)
        self.migrator.log_message.connect(self.win.log)
        self.migrator.finished.connect(on_finished)

        progress.canceled.connect(self.migrator.cancel)
        self.migrator_thread.started.connect(self.migrator.migrate_resources)

        self.migrator_thread.start()
        progress.show()

    def migrate_registry_from_excel(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self.win, "Migración", "No se puede migrar en modo solo lectura.")
            return

        progress = QProgressDialog("Migrando registros...", "Cancelar", 0, 100, self.win)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        self.reg_mig_thread = QThread()
        self.reg_migrator = DataMigrator()
        self.reg_migrator.moveToThread(self.reg_mig_thread)

        def update_progress(cur, tot, lbl):
            progress.setMaximum(tot)
            progress.setValue(cur)
            progress.setLabelText(lbl)

        def on_finished(count):
            self.reg_mig_thread.quit()
            self.win.registry_tab.model.select()
            if not progress.wasCanceled():
                QMessageBox.information(self.win, "Migración", f"Proceso finalizado. Se migraron {count} registros.")
            progress.close()

        def handle_confirmation(year, message):
            reply = QMessageBox.question(self.win, "Advertencia",
                message + " Se recomienda hacer un respaldo manual antes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            self.reg_migrator.set_confirmation_result(reply == QMessageBox.StandardButton.Yes)

        self.reg_migrator.progress_changed.connect(update_progress)
        self.reg_migrator.log_message.connect(self.win.log)
        self.reg_migrator.finished.connect(on_finished)
        self.reg_migrator.request_confirmation.connect(handle_confirmation, Qt.ConnectionType.BlockingQueuedConnection)

        progress.canceled.connect(self.reg_migrator.cancel)
        self.reg_mig_thread.started.connect(self.reg_migrator.migrate_registry)

        self.reg_mig_thread.start()
        progress.show()

    def regenerate_registry_index(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self.win, "Regenerar Índice", "No se puede regenerar en modo solo lectura.")
            return
        current_year = self.win.get_current_year()
        dialog = YearRangeDialog(current_year, self.win)
        dialog.setWindowTitle("Regenerar columna index")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        years = dialog.get_years(current_year)
        progress = QProgressDialog("Regenerando índices...", "Cancelar", 0, len(years), self.win)
        progress.setWindowTitle("Procesando años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        self.ops_thread = QThread()
        self.ops = DBOperations()
        self.ops.moveToThread(self.ops_thread)

        def update_progress_ops(cur, tot, lbl):
            progress.setMaximum(tot)
            progress.setValue(cur)
            progress.setLabelText(lbl)

        def on_finished(msg):
            self.ops_thread.quit()
            self.win.registry_tab.model.select()
            if not progress.wasCanceled():
                QMessageBox.information(self.win, "Regenerar Índice", msg)
            progress.close()

        self.ops.progress_changed.connect(update_progress_ops)
        self.ops.log_message.connect(self.win.log)
        self.ops.finished.connect(on_finished)

        progress.canceled.connect(self.ops.cancel)
        self.ops_thread.started.connect(lambda: self.ops.regenerate_registry_index(years))

        self.ops_thread.start()
        progress.show()

    def recalculate_registry_lapses(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self.win, "Lapsos", "No se puede recalcular en modo solo lectura.")
            return
        ops = DBOperations()
        ops.recalculate_registry_lapses("year_db")
        self.win.registry_tab.model.select()
        QMessageBox.information(self.win, "Lapsos", "Lapsos recalculados.")

    def recalculate_registry_models(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self.win, "Modelos", "No se puede recalcular en modo solo lectura.")
            return
        ops = DBOperations()
        ops.recalculate_registry_models("year_db")
        self.win.registry_tab.model.select()
        QMessageBox.information(self.win, "Modelos", "Modelos recalculados.")

    def sync_firebase_journals(self):
        if not self.config.get("firebase.db_url"):
            return

        progress = QProgressDialog("Sincronizando jornadas con Firebase...", "Cancelar", 0, 100, self.win)
        progress.setWindowTitle("Firebase Sync")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        def update_fb_progress(cur, tot, lbl):
            progress.setMaximum(tot)
            progress.setValue(cur)
            progress.setLabelText(lbl)
            QApplication.processEvents()

        success, msg = self.fb_manager.download_journals(progress_callback=update_fb_progress)
        progress.close()

        if not success:
            self.win.log(f"Firebase Sync Error: {msg}", is_error=True)
        else:
            self.win.log(msg)

    def update_api_server_status(self):
        enabled = self.config.get("api.enabled", False)
        if enabled:
            if not self.api_server_thread.isRunning():
                self.api_server_thread.start()
        else:
            if self.api_server_thread.isRunning():
                pass

    def apply_theme(self, theme_name):
        if theme_name == "Dark":
            QApplication.instance().setStyle("Fusion")
            palette = QPalette()
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Window, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.WindowText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Base, QColor(25, 25, 25))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.AlternateBase, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ToolTipBase, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ToolTipText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Text, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Button, QColor(53, 53, 53))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.ButtonText, Qt.GlobalColor.white)
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.BrightText, Qt.GlobalColor.red)
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Link, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.Highlight, QColor(42, 130, 218))
            palette.setColor(QPalette.ColorGroup.All, QPalette.ColorRole.HighlightedText, Qt.GlobalColor.black)
            QApplication.instance().setPalette(palette)
        else:
            QApplication.instance().setStyle(theme_name)
            if QApplication.instance().style():
                QApplication.instance().setPalette(QApplication.instance().style().standardPalette())

    def restore_window_geometry_safe(self):
        is_max = self.config.get("ui.maximized", True)
        if is_max:
            self.win.setGeometry(100, 100, 1200, 800)
            self.win.showMaximized()
            return

        geometry = self.config.get("ui.geometry")
        if geometry:
            try:
                ba = QByteArray.fromBase64(geometry.encode())
                if not ba.isEmpty() and ba.size() >= 20:
                    self.win.restoreGeometry(ba)
            except Exception as e:
                print(f"Error al restaurar geometría: {e}")

    def load_settings(self):
        sidebar_visible = self.config.get("ui.sidebar_visible", True)
        self.win.dock.setVisible(sidebar_visible)
        self.win.actions.toggle_sidebar.setChecked(sidebar_visible)

        console_visible = self.config.get("ui.console_visible", True)
        self.win.actions.toggle_console.setChecked(console_visible)
        self.win.toggle_sql_consoles(console_visible)

        auto_resize = self.config.get("ui.auto_resize", True)
        self.win.actions.auto_resize_action.setChecked(auto_resize)
        self.win.set_auto_resize_columns(auto_resize)

        show_const_logs = self.config.get("ui.show_construction_logs", False)
        self.win.actions.show_construction_logs.setChecked(show_const_logs)

    def save_settings(self):
        if not self.win.isMinimized():
            geo = self.win.saveGeometry()
            if geo and not geo.isEmpty():
                self.config.set("ui.geometry", geo.toBase64().data().decode())
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
        self.save_settings()
        if hasattr(self, 'tg_manager'):
            self.tg_manager.shutdown()
