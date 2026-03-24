import sys
import os
import ctypes
import ctypes.wintypes
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QTabWidget, QHBoxLayout, QTreeView,
                             QDockWidget, QMessageBox, QProgressDialog, QStyle)
from PyQt6.QtCore import Qt, QByteArray, QThread, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon
from PyQt6.QtSql import QSqlDatabase

from db_manager import init_databases
from config_manager import ConfigManager
from data_table import DataTableTab

# Core Imports
from core.db_connection_manager import DBConnectionManager
from core.drive_monitor import DriveMonitor
from core.app_state import AppState, AppMode

# UI Imports
from ui.warning_bar import OfflineWarningBar

# Dialog Imports
from dialogs import (DatabaseForm, YearRangeDialog, ReportMaterialsDialog,
                     SettingsDialog, TelegramDownloadDialog, DuplicateActionDialog)

# Domain Logic Imports
from data_migration import DataMigrator
from resource_management import ResourceScanner
from db_operations import DBOperations
from telegram_manager import TelegramManager
from sync_manager import SyncManager

class PrecureManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Precure Media Manager - Core System")
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))

        self.config = ConfigManager()
        self.state = AppState()
        self.db_manager = DBConnectionManager()
        self.tg_manager = TelegramManager()
        self.sync_manager = SyncManager()

        self.last_device_change = 0

        # Base geometry
        self.setGeometry(100, 100, 1200, 800)
        self.apply_theme(self.config.get("ui.theme", "Fusion"))

        self._init_ui()
        self._init_menu()

        # Start Polling for Drive
        from db_manager import BASE_DIR_PATH
        drive_letter = os.path.splitdrive(BASE_DIR_PATH)[0].replace(":", "")
        self.drive_monitor = DriveMonitor(drive_letter or "E")
        self.drive_monitor.drive_status_changed.connect(self.handle_drive_status_change)

        # Initial Drive check
        self.handle_drive_status_change(self.drive_monitor.is_available)

        # Defer DB init until after UI is fully ready
        QTimer.singleShot(0, self.delayed_init)

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.outer_layout = QVBoxLayout(central_widget)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)

        self.warning_bar = OfflineWarningBar()
        self.outer_layout.addWidget(self.warning_bar)

        self.main_container = QWidget()
        self.main_layout = QHBoxLayout(self.main_container)
        self.outer_layout.addWidget(self.main_container)

        self._init_sidebar()
        self._init_tabs()

    def _init_sidebar(self):
        self.dock = QDockWidget("Años", self)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.year_tree = QTreeView()
        self.year_tree.setHeaderHidden(True)
        self.year_model = QStandardItemModel()
        root_node = self.year_model.invisibleRootItem()
        for year in range(2004, datetime.now().year + 1):
            item = QStandardItem(str(year))
            item.setEditable(False)
            root_node.appendRow(item)
        self.year_tree.setModel(self.year_model)
        self.year_tree.clicked.connect(self.on_year_selected)

        # Initial selection
        self.year_tree.setCurrentIndex(self.year_model.index(0, 0))

        self.dock.setWidget(self.year_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)

    def _init_tabs(self):
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs, 4)

        self.registry_tab = DataTableTab("year_db", "T_Registry")
        self.resources_tab = DataTableTab("year_db", "T_Resources")

        self.global_tab_container = QWidget()
        global_layout = QVBoxLayout(self.global_tab_container)
        self.global_subtabs = QTabWidget()

        self.catalog_tab = DataTableTab("global_db", "T_Type_Catalog_Reg")
        self.opener_tab = DataTableTab("global_db", "T_Opener_Models")
        self.type_res_tab = DataTableTab("global_db", "T_Type_Resources")
        self.seasons_tab = DataTableTab("global_db", "T_Seasons")
        self.domains_tab = DataTableTab("global_db", "T_Domains_base")

        self.global_tabs = [self.catalog_tab, self.opener_tab, self.type_res_tab, self.seasons_tab, self.domains_tab]
        self.year_tabs = [self.registry_tab, self.resources_tab]
        self.all_tabs = self.year_tabs + self.global_tabs

        self.global_subtabs.addTab(self.catalog_tab, "Catálogo")
        self.global_subtabs.addTab(self.opener_tab, "Modelos Opener")
        self.global_subtabs.addTab(self.type_res_tab, "Tipos Recursos")
        self.global_subtabs.addTab(self.seasons_tab, "Temporadas")
        self.global_subtabs.addTab(self.domains_tab, "Dominios Base")
        global_layout.addWidget(self.global_subtabs)

        self.tabs.addTab(self.registry_tab, "Registros")
        self.tabs.addTab(self.resources_tab, "Recursos")
        self.tabs.addTab(self.global_tab_container, "Global")

        self.tabs.currentChanged.connect(self.update_menu_states)
        self.global_subtabs.currentChanged.connect(self.update_menu_states)

    def _init_menu(self):
        from ui.actions import ActionsManager
        self.actions = ActionsManager(self)
        self.actions.setup_menu(self.menuBar())
        self.update_menu_states()

    def on_report_materials_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Reportar Materiales", "No se pueden reportar materiales en modo solo lectura.")
            return
        dialog = ReportMaterialsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.registry_tab.model.select()

    def on_tg_download_requested(self):
        dialog = TelegramDownloadDialog(self, self.tg_manager)
        dialog.exec()

    def scan_master_folders(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Escaneo", "No se puede escanear en modo solo lectura.")
            return
        ops = DBOperations()
        ops.scan_master_folders()
        self.seasons_tab.model.select()
        QMessageBox.information(self, "Escaneo", "Escaneo de carpetas maestras finalizado.")

    def on_update_links_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Vinculación", "No se puede vincular en modo solo lectura.")
            return
        year = self.get_current_year()
        self.scan_and_link_resources_ui([year], overwrite=False)
        QMessageBox.information(self, "Vinculación", f"Proceso de actualización para el año {year} completado.")

    def on_scan_link_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Escaneo", "No se puede escanear en modo solo lectura.")
            return
        current_year = self.get_current_year()
        dialog = YearRangeDialog(current_year, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            years = dialog.get_years(current_year)
            self.scan_and_link_resources_ui(years, overwrite=True)
            QMessageBox.information(self, "Escaneo", "Proceso de escaneo y vinculación completado.")

    def on_scan_new_sd_requested(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Búsqueda", "No se puede buscar en modo solo lectura.")
            return
        current_year = self.get_current_year()
        dialog = YearRangeDialog(current_year, self)
        dialog.setWindowTitle("Buscar nuevas soundtracks")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            years = dialog.get_years(current_year)
            self.scan_new_soundtracks_ui(years)
            QMessageBox.information(self, "Búsqueda", "Proceso de búsqueda de soundtracks finalizado.")

    def migrate_resources_from_excel(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Migración", "No se puede migrar en modo solo lectura.")
            return

        progress = QProgressDialog("Migrando recursos...", "Cancelar", 0, 100, self)
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
            self.resources_tab.model.select()
            if not progress.wasCanceled():
                QMessageBox.information(self, "Migración", f"Proceso finalizado. Se migraron {count} recursos.")
            progress.close()

        self.migrator.progress_changed.connect(update_progress)
        self.migrator.log_message.connect(self.log)
        self.migrator.finished.connect(on_finished)

        progress.canceled.connect(self.migrator.cancel)
        self.migrator_thread.started.connect(self.migrator.migrate_resources)

        self.migrator_thread.start()
        progress.show()

    def migrate_registry_from_excel(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Migración", "No se puede migrar en modo solo lectura.")
            return

        progress = QProgressDialog("Migrando registros...", "Cancelar", 0, 100, self)
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
            self.registry_tab.model.select()
            if not progress.wasCanceled():
                QMessageBox.information(self, "Migración", f"Proceso finalizado. Se migraron {count} registros.")
            progress.close()

        def handle_confirmation(year, message):
            reply = QMessageBox.question(self, "Advertencia",
                message + " Se recomienda hacer un respaldo manual antes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            self.reg_migrator.set_confirmation_result(reply == QMessageBox.StandardButton.Yes)

        self.reg_migrator.progress_changed.connect(update_progress)
        self.reg_migrator.log_message.connect(self.log)
        self.reg_migrator.finished.connect(on_finished)
        self.reg_migrator.request_confirmation.connect(handle_confirmation, Qt.ConnectionType.BlockingQueuedConnection)

        progress.canceled.connect(self.reg_migrator.cancel)
        self.reg_mig_thread.started.connect(self.reg_migrator.migrate_registry)

        self.reg_mig_thread.start()
        progress.show()

    def regenerate_registry_index(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Regenerar Índice", "No se puede regenerar en modo solo lectura.")
            return
        current_year = self.get_current_year()
        dialog = YearRangeDialog(current_year, self)
        dialog.setWindowTitle("Regenerar columna index")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        years = dialog.get_years(current_year)
        progress = QProgressDialog("Regenerando índices...", "Cancelar", 0, len(years), self)
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
            self.registry_tab.model.select()
            if not progress.wasCanceled():
                QMessageBox.information(self, "Regenerar Índice", msg)
            progress.close()

        self.ops.progress_changed.connect(update_progress_ops)
        self.ops.log_message.connect(self.log)
        self.ops.finished.connect(on_finished)

        progress.canceled.connect(self.ops.cancel)
        self.ops_thread.started.connect(lambda: self.ops.regenerate_registry_index(years))

        self.ops_thread.start()
        progress.show()

    def scan_new_soundtracks_lyrics(self, years):
        # Implementation moved to background thread below
        pass

    def scan_new_soundtracks_ui(self, years):
        from dialogs.duplicate_action import DuplicateActionDialog
        progress = QProgressDialog("Buscando nuevas soundtracks...", "Cancelar", 0, len(years), self)
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
            diag = DuplicateActionDialog(title, self)
            diag.exec()
            self.sd_scanner.set_duplicate_choice(*diag.get_choice())

        def on_finished():
            self.sd_scan_thread.quit()
            self.resources_tab.model.select()
            progress.close()

        self.sd_scanner.progress_changed.connect(update_progress)
        self.sd_scanner.log_message.connect(self.log)
        self.sd_scanner.request_duplicate_action.connect(handle_duplicate, Qt.ConnectionType.BlockingQueuedConnection)
        self.sd_scanner.finished.connect(on_finished)

        progress.canceled.connect(self.sd_scanner.cancel)
        self.sd_scan_thread.started.connect(lambda: self.sd_scanner.scan_new_soundtracks_lyrics(years))

        self.sd_scan_thread.start()
        progress.show()

    def scan_and_link_resources_ui(self, years, overwrite=True):
        progress = QProgressDialog("Escaneando y vinculando recursos...", "Cancelar", 0, len(years), self)
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
            self.resources_tab.model.select()
            progress.close()

        self.scanner.progress_changed.connect(update_progress)
        self.scanner.log_message.connect(self.log)
        self.scanner.warning_emitted.connect(lambda t, m: QMessageBox.warning(self, t, m))
        self.scanner.finished.connect(on_finished)

        progress.canceled.connect(self.scanner.cancel)
        self.scan_thread.started.connect(lambda: self.scanner.scan_and_link_resources(years, overwrite))

        self.scan_thread.start()
        progress.show()

    def recalculate_registry_lapses(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Lapsos", "No se puede recalcular en modo solo lectura.")
            return
        ops = DBOperations()
        ops.recalculate_registry_lapses("year_db")
        self.registry_tab.model.select()
        QMessageBox.information(self, "Lapsos", "Lapsos recalculados.")

    def recalculate_registry_models(self):
        if self.state.mode == AppMode.OFFLINE:
            QMessageBox.warning(self, "Modelos", "No se puede recalcular en modo solo lectura.")
            return
        ops = DBOperations()
        ops.recalculate_registry_models("year_db")
        self.registry_tab.model.select()
        QMessageBox.information(self, "Modelos", "Modelos recalculados.")

    def log(self, message, is_error=False, target="resources"):
        if target == "resources" and hasattr(self, 'resources_tab'):
            self.resources_tab.log(message, is_error)
        elif target == "registry" and hasattr(self, 'registry_tab'):
            self.registry_tab.log(message, is_error)
        elif hasattr(self, 'resources_tab'):
            self.resources_tab.log(message, is_error)

    def apply_theme(self, theme_name):
        if theme_name == "Dark":
            QApplication.instance().setStyle("Fusion")
            from PyQt6.QtGui import QPalette, QColor
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

    def delayed_init(self):
        self.init_db_connections()
        self.load_settings()
        self.restore_window_geometry_safe()

        if self.state.mode == AppMode.ONLINE:
            self.run_startup_sync()

    def restore_window_geometry_safe(self):
        is_max = self.config.get("ui.maximized", True)
        if is_max:
            self.setGeometry(100, 100, 1200, 800)
            self.showMaximized()
            return

        geometry = self.config.get("ui.geometry")
        if geometry:
            try:
                ba = QByteArray.fromBase64(geometry.encode())
                if not ba.isEmpty() and ba.size() >= 20:
                    self.restoreGeometry(ba)
            except Exception as e:
                print(f"Error al restaurar geometría: {e}")

    def save_settings(self):
        if not self.isMinimized():
            geo = self.saveGeometry()
            if geo and not geo.isEmpty():
                self.config.set("ui.geometry", geo.toBase64().data().decode())
            self.config.set("ui.maximized", self.isMaximized())

        self.config.set("ui.sidebar_visible", self.dock.isVisible())
        self.config.set("ui.console_visible", self.registry_tab.console_area.isVisible())
        self.config.save()

    def load_settings(self):
        sidebar_visible = self.config.get("ui.sidebar_visible", True)
        self.dock.setVisible(sidebar_visible)
        self.actions.toggle_sidebar.setChecked(sidebar_visible)

        console_visible = self.config.get("ui.console_visible", True)
        self.actions.toggle_console.setChecked(console_visible)
        self.toggle_sql_consoles(console_visible)

        auto_resize = self.config.get("ui.auto_resize", True)
        self.actions.auto_resize_action.setChecked(auto_resize)
        self.set_auto_resize_columns(auto_resize)

        show_const_logs = self.config.get("ui.show_construction_logs", False)
        self.actions.show_construction_logs.setChecked(show_const_logs)

    def init_db_connections(self):
        from db_manager import GLOBAL_DB_PATH, is_on_external_drive, get_offline_db_path

        g_path = GLOBAL_DB_PATH
        is_ro = False
        if self.state.mode == AppMode.OFFLINE and is_on_external_drive(g_path):
            g_path = get_offline_db_path(g_path)
            is_ro = True

        self.db_manager.open_connection("global_db", g_path, readonly=is_ro)

        for tab in self.global_tabs:
            tab.update_database("global_db")

        self.open_year_db(self.get_current_year())

    def open_year_db(self, year):
        if not year: return False
        from db_manager import get_yearly_db_path, get_offline_db_path, GLOBAL_DB_PATH, is_on_external_drive

        y_path = get_yearly_db_path(year)
        is_ro = False
        if self.state.mode == AppMode.OFFLINE:
            y_path = get_offline_db_path(y_path)
            is_ro = True

        self.db_manager.open_connection("year_db", y_path, readonly=is_ro)

        g_path = GLOBAL_DB_PATH
        if self.state.mode == AppMode.OFFLINE and is_on_external_drive(g_path):
            g_path = get_offline_db_path(g_path)

        self.db_manager.safe_attach("year_db", g_path, "global_db")

        self.resources_tab.update_database("year_db")
        self.registry_tab.update_database("year_db")
        return True

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
            self.warning_bar.setVisible(offline)

            progress = QProgressDialog("Cambiando modo de base de datos...", "Cancelar", 0, 0, self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            QApplication.processEvents()

            self.db_manager.close_all(self.all_tabs)

            if not offline:
                self.run_startup_sync(callback=lambda: self.finish_reconnect(progress))
            else:
                self.finish_reconnect(progress)
        finally:
            self.state.reconnecting = False

    def finish_reconnect(self, progress_dialog):
        self.init_db_connections()
        self.update_menu_states()
        progress_dialog.close()

    def run_startup_sync(self, callback=None):
        from db_manager import GLOBAL_DB_PATH, get_yearly_db_path, get_offline_db_path, is_on_external_drive

        tasks = []
        if is_on_external_drive(GLOBAL_DB_PATH):
            tasks.append((GLOBAL_DB_PATH, get_offline_db_path(GLOBAL_DB_PATH), "Sincronizando Global DB..."))

        for year in range(2004, datetime.now().year + 1):
            y_path = get_yearly_db_path(year)
            if os.path.exists(y_path):
                tasks.append((y_path, get_offline_db_path(y_path), f"Sincronizando año {year}..."))

        if not tasks:
            if callback: callback()
            return

        self.sync_progress = QProgressDialog("Sincronizando bases de datos...", "Cancelar", 0, 100, self)
        self.sync_progress.setWindowModality(Qt.WindowModality.WindowModal)

        def on_finished(success, msg):
            try:
                self.sync_manager.task_progress.disconnect()
                self.sync_manager.sync_finished.disconnect()
            except Exception: pass
            self.sync_progress.close()
            if not success:
                QMessageBox.warning(self, "Sincronización", f"Problema al sincronizar: {msg}")
            if callback: callback()

        def update_sync_progress(cur, tot, lbl):
            self.sync_progress.setLabelText(lbl)
            self.sync_progress.setValue(int(cur/tot*100 if tot > 0 else 100))

        self.sync_manager.task_progress.connect(update_sync_progress)
        self.sync_manager.sync_finished.connect(on_finished)
        self.sync_manager.perform_sync(tasks)

    def on_year_selected(self, index):
        if not index.isValid(): return
        self.open_year_db(int(index.data()))

    def get_current_year(self):
        index = self.year_tree.currentIndex()
        return int(index.data()) if index.isValid() else 2004

    def set_auto_resize_columns(self, enabled):
        for tab in self.all_tabs:
            tab.set_auto_resize(enabled)

    def toggle_sql_consoles(self, visible):
        for tab in self.all_tabs:
            tab.set_console_visible(visible)

    def update_menu_states(self):
        if not hasattr(self, 'actions'): return

        is_offline = self.state.mode == AppMode.OFFLINE
        current_tab = self.tabs.currentWidget()

        # Tools menu - always disabled in offline
        self.actions.tools_menu.setEnabled(not is_offline)

        # Edit menu - restricted in offline
        if is_offline:
            # Only "Añadir Fila" enabled if in Global tab
            self.actions.edit_menu.setEnabled(True) # Keep menu enabled to see actions

            is_global_active = (current_tab == self.global_tab_container)

            for action in self.actions.edit_menu.actions():
                if action == self.actions.add_row_action:
                    action.setEnabled(is_global_active)
                else:
                    action.setEnabled(False)
        else:
            self.actions.edit_menu.setEnabled(True)
            for action in self.actions.edit_menu.actions():
                action.setEnabled(True)

    def closeEvent(self, event):
        self.save_settings()
        if hasattr(self, 'tg_manager'):
            self.tg_manager.shutdown()
        super().closeEvent(event)

if __name__ == "__main__":
    if os.name == 'nt':
        myappid = 'storeetude.precuremanager.desktopcenter.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    init_databases()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = PrecureManagerApp()
    window.show()
    sys.exit(app.exec())
