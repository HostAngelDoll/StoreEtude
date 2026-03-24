import sys
import os
import re
import sqlite3
import csv
import subprocess
import ctypes
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QTabWidget, QLabel, QHBoxLayout, QTreeView,
                             QDockWidget, QDialog, QMessageBox, QMenuBar, QMenu,
                             QProgressDialog)
from PyQt6.QtCore import Qt, QSettings, QByteArray
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction, QIcon
from PyQt6.QtSql import QSqlDatabase, QSqlQuery
import openpyxl

from db_manager import init_databases, GLOBAL_DB_PATH, get_yearly_db_path, BASE_DIR_PATH, refresh_config_paths
from forms import DatabaseForm, YearRangeDialog, ReportMaterialsDialog, SettingsDialog, TelegramDownloadDialog
from config_manager import ConfigManager
from data_table import DataTableTab

# Domain Logic Imports
from data_migration import DataMigrator
from resource_management import ResourceScanner
from db_operations import DBOperations
from telegram_manager import TelegramManager

class PrecureManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Precure Media Manager - Core System")
        self.setWindowIcon(QIcon(r"img\icon.ico"))
        self.config = ConfigManager()
        self.tg_manager = TelegramManager()

        geometry = self.config.get("ui.geometry")
        if geometry:
            try:
                self.restoreGeometry(QByteArray.fromBase64(geometry.encode()))
            except:
                self.setGeometry(100, 100, 1200, 800)
        else:
            self.setGeometry(100, 100, 1200, 800)

        self.apply_theme(self.config.get("ui.theme", "Fusion"))
        self.init_actions()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)

        self.init_sidebar()

        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs, 4)

        # Tabs initialization
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

        self.global_subtabs.addTab(self.catalog_tab, "Catálogo")
        self.global_subtabs.addTab(self.opener_tab, "Modelos Opener")
        self.global_subtabs.addTab(self.type_res_tab, "Tipos Recursos")
        self.global_subtabs.addTab(self.seasons_tab, "Temporadas")
        self.global_subtabs.addTab(self.domains_tab, "Dominios Base")
        global_layout.addWidget(self.global_subtabs)

        self.tabs.addTab(self.registry_tab, "Registros")
        self.tabs.addTab(self.resources_tab, "Recursos")
        self.tabs.addTab(self.global_tab_container, "Global")

        self.init_menu_bar()
        # init_db_connections depends on year_tree (via get_current_year),
        # so it must be called AFTER init_sidebar() and BEFORE load_settings()
        # which might rely on DB connections being active for model selection.
        self.init_db_connections()

        # Ensure all tabs are properly initialized with the correct database connection
        self.registry_tab.update_database("year_db")
        self.resources_tab.update_database("year_db")
        self.catalog_tab.update_database("global_db")
        self.opener_tab.update_database("global_db")
        self.type_res_tab.update_database("global_db")
        self.seasons_tab.update_database("global_db")
        self.domains_tab.update_database("global_db")

        self.load_settings()

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

    def closeEvent(self, event):
        self.save_settings()
        if hasattr(self, 'tg_manager'):
            self.tg_manager.shutdown()
        super().closeEvent(event)

    def save_settings(self):
        self.config.set("ui.geometry", self.saveGeometry().toBase64().data().decode())
        self.config.set("ui.sidebar_visible", self.toggle_sidebar.isChecked())
        self.config.set("ui.console_visible", self.toggle_console.isChecked())
        self.config.set("ui.auto_resize", self.auto_resize_action.isChecked())
        self.config.set("ui.show_construction_logs", self.show_construction_logs.isChecked())

    def load_settings(self):
        sidebar_visible = self.config.get("ui.sidebar_visible", True)
        self.toggle_sidebar.setChecked(sidebar_visible)
        self.dock.setVisible(sidebar_visible)

        console_visible = self.config.get("ui.console_visible", True)
        self.toggle_console.setChecked(console_visible)
        self.toggle_sql_consoles()

        auto_resize = self.config.get("ui.auto_resize", True)
        self.auto_resize_action.setChecked(auto_resize)
        self.set_auto_resize_columns(auto_resize)

        show_const_logs = self.config.get("ui.show_construction_logs", False)
        self.show_construction_logs.setChecked(show_const_logs)

    def set_auto_resize_columns(self, enabled):
        for tab in [self.registry_tab, self.resources_tab, self.catalog_tab,
                    self.opener_tab, self.type_res_tab, self.seasons_tab, self.domains_tab]:
            tab.set_auto_resize(enabled)

    def init_actions(self):
        # Archivo
        self.save_action = QAction("Guardar", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_current_tab)

        self.export_action = QAction("Exportar tabla a CSV", self)
        self.export_action.triggered.connect(self.export_active_tab_to_csv)

        self.import_action = QAction("Importar tabla desde CSV", self)
        self.import_action.triggered.connect(self.import_active_tab_from_csv)

        self.config_action = QAction("Configuración", self)
        self.config_action.triggered.connect(self.on_settings_requested)

        self.exit_action = QAction("Salir", self)
        self.exit_action.triggered.connect(self.close)

        # Edición
        self.add_row_action = QAction("Añadir fila", self)
        self.add_row_action.triggered.connect(self.on_add_row_requested)

        self.scan_masters_action = QAction("Escanear carpetas maestras", self)
        self.scan_masters_action.triggered.connect(self.scan_master_folders)

        self.migrate_resources_action = QAction("Migrar Recursos de años", self)
        self.migrate_resources_action.triggered.connect(self.migrate_resources_from_excel)

        self.migrate_registry_action = QAction("Migrar Registros de años", self)
        self.migrate_registry_action.triggered.connect(self.migrate_registry_from_excel)

        self.regen_index_action = QAction("Regenerar la columna index de registros", self)
        self.regen_index_action.triggered.connect(self.regenerate_registry_index)

        self.recalc_lapses_action = QAction("Recalcular Lapsos de rangos de registros", self)
        self.recalc_lapses_action.triggered.connect(self.recalculate_registry_lapses)

        self.recalc_models_action = QAction("Recalcular modelos detectados de registros", self)
        self.recalc_models_action.triggered.connect(self.recalculate_registry_models)

        self.update_links_action = QAction("Actualizar vinculación de archivos", self)
        self.update_links_action.triggered.connect(self.on_update_links_requested)

        # Herramientas
        self.scan_link_action = QAction("Escanear y vincular archivos", self)
        self.scan_link_action.triggered.connect(self.on_scan_link_requested)

        self.scan_new_sd_action = QAction("Búsqueda de nuevas soundtracks con lyrics", self)
        self.scan_new_sd_action.triggered.connect(self.on_scan_new_sd_requested)

        self.report_materials_action = QAction("Reportar Materiales Vistos", self)
        self.report_materials_action.triggered.connect(self.on_report_materials_requested)

        self.tg_download_action = QAction("Descargar nuevo contenido desde telegram", self)
        self.tg_download_action.triggered.connect(self.on_tg_download_requested)

        # Vista
        self.toggle_sidebar = QAction("Años", self, checkable=True)
        self.toggle_sidebar.setChecked(True)
        self.toggle_sidebar.triggered.connect(self.on_toggle_sidebar)

        self.toggle_console = QAction("Consola SQL", self, checkable=True)
        self.toggle_console.setChecked(True)
        self.toggle_console.triggered.connect(self.toggle_sql_consoles)

        self.show_construction_logs = QAction("Mostrar logs de construcción de tablas", self, checkable=True)
        self.show_construction_logs.setChecked(False)
        self.show_construction_logs.triggered.connect(self.save_settings)

        self.auto_resize_action = QAction("Auto-ajustar ancho de columnas", self, checkable=True)
        self.auto_resize_action.setChecked(True)
        self.auto_resize_action.triggered.connect(self.set_auto_resize_columns)

        self.resize_to_contents_action = QAction("Ajustar anchos al contenido", self)
        self.resize_to_contents_action.triggered.connect(self.on_resize_to_contents_requested)

        self.lock_all_columns_action = QAction("Bloquear todos los anchos desbloqueados", self)
        self.lock_all_columns_action.triggered.connect(self.on_lock_all_columns_requested)

        self.unlock_all_columns_action = QAction("Desbloquear todos los anchos bloqueados", self)
        self.unlock_all_columns_action.triggered.connect(self.on_unlock_all_columns_requested)

        # Ayuda
        self.about_action = QAction("Acerca de", self)
        self.about_action.triggered.connect(lambda: QMessageBox.information(self, "Ayuda", "Precure Media Manager v1.0"))

    def on_toggle_sidebar(self):
        if hasattr(self, 'dock'):
            self.dock.setVisible(self.toggle_sidebar.isChecked())
        self.save_settings()

    def init_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Archivo")
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.export_action)
        file_menu.addAction(self.import_action)
        file_menu.addSeparator()
        file_menu.addAction(self.config_action)
        file_menu.addSeparator()
        file_menu.addAction(self.exit_action)

        edit_menu = menubar.addMenu("Edición")
        edit_menu.addAction(self.add_row_action)
        edit_menu.addAction(self.scan_masters_action)
        edit_menu.addAction(self.migrate_resources_action)
        edit_menu.addAction(self.migrate_registry_action)
        edit_menu.addAction(self.regen_index_action)
        edit_menu.addAction(self.recalc_lapses_action)
        edit_menu.addAction(self.recalc_models_action)
        edit_menu.addAction(self.update_links_action)

        tools_menu = menubar.addMenu("Herramientas")
        tools_menu.addAction(self.scan_link_action)
        tools_menu.addAction(self.scan_new_sd_action)
        tools_menu.addAction(self.report_materials_action)
        tools_menu.addAction(self.tg_download_action)

        view_menu = menubar.addMenu("Vista")
        panels_submenu = view_menu.addMenu("Mostrar Paneles")
        panels_submenu.addAction(self.toggle_sidebar)
        panels_submenu.addAction(self.toggle_console)

        log_types_menu = view_menu.addMenu("Mostrar tipos de logs")
        log_types_menu.addAction(self.show_construction_logs)

        view_menu.addAction(self.auto_resize_action)
        view_menu.addSeparator()
        view_menu.addAction(self.resize_to_contents_action)
        view_menu.addAction(self.lock_all_columns_action)
        view_menu.addAction(self.unlock_all_columns_action)

        help_menu = menubar.addMenu("Ayuda")
        help_menu.addAction(self.about_action)

    def save_current_tab(self):
        current_tab = self.get_active_data_tab()
        if current_tab:
            # Force commit of active editor
            if current_tab.view.currentIndex().isValid():
                current_tab.view.setEnabled(False)
                current_tab.view.setEnabled(True)
                current_tab.view.setFocus()

            if current_tab.model.submitAll():
                QMessageBox.information(self, "Guardar", "Cambios guardados correctamente.")
            else:
                QMessageBox.critical(self, "Error", f"No se pudo guardar: {current_tab.model.lastError().text()}")

    def export_active_tab_to_csv(self):
        current_tab = self.get_active_data_tab()
        if current_tab:
            current_tab.export_to_csv()

    def import_active_tab_from_csv(self):
        current_tab = self.get_active_data_tab()
        if current_tab:
            current_tab.import_from_csv()

    def get_active_data_tab(self):
        current_widget = self.tabs.currentWidget()
        if current_widget == self.global_tab_container:
            current_tab = self.global_subtabs.currentWidget()
        else:
            current_tab = current_widget

        if isinstance(current_tab, DataTableTab):
            return current_tab
        return None

    def on_add_row_requested(self):
        current_tab = self.get_active_data_tab()
        if current_tab:
            current_tab.add_record()

    def migrate_resources_from_excel(self):
        migrator = DataMigrator()
        progress = QProgressDialog("Migrando recursos...", "Cancelar", 0, 100, self)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        migrator.progress_changed.connect(lambda cur, tot, lbl: (progress.setMaximum(tot), progress.setValue(cur), progress.setLabelText(lbl)))
        migrator.log_message.connect(self.log)
        progress.canceled.connect(migrator.cancel)

        migrator.migrate_resources()

        self.resources_tab.model.select()
        if not progress.wasCanceled():
            QMessageBox.information(self, "Migración", "Proceso de migración de recursos finalizado.")

    def migrate_registry_from_excel(self):
        migrator = DataMigrator()
        progress = QProgressDialog("Migrando registros...", "Cancelar", 0, 100, self)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        migrator.progress_changed.connect(lambda cur, tot, lbl: (progress.setMaximum(tot), progress.setValue(cur), progress.setLabelText(lbl)))
        migrator.log_message.connect(self.log)
        progress.canceled.connect(migrator.cancel)

        def handle_confirmation(year, message):
            reply = QMessageBox.question(self, "Advertencia",
                message + " Se recomienda hacer un respaldo manual antes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            migrator.set_confirmation_result(reply == QMessageBox.StandardButton.Yes)

        migrator.request_confirmation.connect(handle_confirmation)

        migrator.migrate_registry()

        self.registry_tab.model.select()
        if not progress.wasCanceled():
            QMessageBox.information(self, "Migración", "Proceso de migración de registros finalizado.")

    def regenerate_registry_index(self):
        current_year = self.get_current_year()
        dialog = YearRangeDialog(current_year, self)
        dialog.setWindowTitle("Regenerar columna index")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        years = dialog.get_years(current_year)
        ops = DBOperations()
        progress = QProgressDialog("Regenerando índices...", "Cancelar", 0, len(years), self)
        progress.setWindowTitle("Procesando años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        ops.progress_changed.connect(lambda cur, tot, lbl: (progress.setMaximum(tot), progress.setValue(cur), progress.setLabelText(lbl)))
        ops.log_message.connect(self.log)
        progress.canceled.connect(ops.cancel)

        ops.regenerate_registry_index(years)

        self.registry_tab.model.select()
        if not progress.wasCanceled():
            QMessageBox.information(self, "Regenerar Índice", "Proceso finalizado.")

    def recalculate_registry_lapses(self):
        ops = DBOperations()
        ops.recalculate_registry_lapses("year_db")
        self.registry_tab.model.select()
        QMessageBox.information(self, "Lapsos", "Lapsos recalculados.")

    def recalculate_registry_models(self):
        ops = DBOperations()
        ops.recalculate_registry_models("year_db")
        self.registry_tab.model.select()
        QMessageBox.information(self, "Modelos", "Modelos recalculados.")

    def on_update_links_requested(self):
        year = self.get_current_year()
        self.scan_and_link_resources_ui([year], overwrite=False)
        QMessageBox.information(self, "Vinculación", f"Proceso de actualización para el año {year} completado.")

    def on_scan_link_requested(self):
        current_year = self.get_current_year()
        dialog = YearRangeDialog(current_year, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            years = dialog.get_years(current_year)
            self.scan_and_link_resources_ui(years, overwrite=True)
            QMessageBox.information(self, "Escaneo", "Proceso de escaneo y vinculación completado.")

    def on_scan_new_sd_requested(self):
        current_year = self.get_current_year()
        dialog = YearRangeDialog(current_year, self)
        dialog.setWindowTitle("Buscar nuevas soundtracks")
        if dialog.exec() == QDialog.DialogCode.Accepted:
            years = dialog.get_years(current_year)
            self.scan_new_soundtracks_ui(years)
            QMessageBox.information(self, "Búsqueda", "Proceso de búsqueda de soundtracks finalizado.")

    def scan_new_soundtracks_ui(self, years):
        from forms import DuplicateActionDialog
        scanner = ResourceScanner()
        progress = QProgressDialog("Buscando nuevas soundtracks...", "Cancelar", 0, len(years), self)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        scanner.progress_changed.connect(lambda cur, tot, lbl: (progress.setMaximum(tot), progress.setValue(cur), progress.setLabelText(lbl)))
        scanner.log_message.connect(self.log)
        progress.canceled.connect(scanner.cancel)

        def handle_duplicate(title):
            diag = DuplicateActionDialog(title, self)
            diag.exec()
            scanner.set_duplicate_choice(*diag.get_choice())

        scanner.request_duplicate_action.connect(handle_duplicate)

        scanner.scan_new_soundtracks_lyrics(years)
        self.resources_tab.model.select()

    def scan_and_link_resources_ui(self, years, overwrite=True):
        scanner = ResourceScanner()
        progress = QProgressDialog("Escaneando y vinculando recursos...", "Cancelar", 0, len(years), self)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        scanner.progress_changed.connect(lambda cur, tot, lbl: (progress.setMaximum(tot), progress.setValue(cur), progress.setLabelText(lbl)))
        scanner.log_message.connect(self.log)
        scanner.warning_emitted.connect(lambda t, m: QMessageBox.warning(self, t, m))
        progress.canceled.connect(scanner.cancel)

        scanner.scan_and_link_resources(years, overwrite)
        self.resources_tab.model.select()

    def on_report_materials_requested(self):
        dialog = ReportMaterialsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh registry if it's the active tab
            self.registry_tab.model.select()

    def on_tg_download_requested(self):
        dialog = TelegramDownloadDialog(self, self.tg_manager)
        dialog.exec()

    def scan_master_folders(self):
        ops = DBOperations()
        ops.scan_master_folders()
        self.seasons_tab.model.select()
        QMessageBox.information(self, "Escaneo", "Escaneo de carpetas maestras finalizado.")

    def toggle_sql_consoles(self):
        is_visible = self.toggle_console.isChecked()
        self.registry_tab.set_console_visible(is_visible)
        self.resources_tab.set_console_visible(is_visible)
        self.catalog_tab.set_console_visible(is_visible)
        self.opener_tab.set_console_visible(is_visible)
        self.type_res_tab.set_console_visible(is_visible)
        self.seasons_tab.set_console_visible(is_visible)
        self.domains_tab.set_console_visible(is_visible)

    def init_db_connections(self):
        from db_manager import GLOBAL_DB_PATH

        db_global = QSqlDatabase.database("global_db", open=False)
        if not db_global.isValid():
            db_global = QSqlDatabase.addDatabase("QSQLITE", "global_db")

        if db_global.databaseName() != GLOBAL_DB_PATH:
            db_global.close()
            db_global.setDatabaseName(GLOBAL_DB_PATH)

        if not db_global.isOpen():
            db_global.open()

        db_year = QSqlDatabase.database("year_db", open=False)
        if not db_year.isValid():
            db_year = QSqlDatabase.addDatabase("QSQLITE", "year_db")
            db_year.setDatabaseName(get_yearly_db_path(self.get_current_year()))

        if not db_year.isOpen():
            if db_year.open():
                QSqlQuery(db_year).exec(f"ATTACH DATABASE '{GLOBAL_DB_PATH}' AS global_db")

    def init_sidebar(self):
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
        self.dock.setWidget(self.year_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)

    def on_year_selected(self, index):
        year = index.data()
        db_path = get_yearly_db_path(year)
        db = QSqlDatabase.database("year_db")
        db.close()
        db.setDatabaseName(db_path)
        if db.open():
            from db_manager import GLOBAL_DB_PATH
            QSqlQuery(db).exec(f"ATTACH DATABASE '{GLOBAL_DB_PATH}' AS global_db")
            self.resources_tab.update_database("year_db")
            self.registry_tab.update_database("year_db")
        else:
            QMessageBox.critical(self, "Error", f"No se pudo abrir la base de datos del año {year}.")

    def get_current_year(self):
        if not hasattr(self, 'year_tree'):
            return 2004
        index = self.year_tree.currentIndex()
        return int(index.data()) if index.isValid() else 2004

    def on_resize_to_contents_requested(self):
        tab = self.get_active_data_tab()
        if tab:
            tab.resize_to_contents()

    def on_lock_all_columns_requested(self):
        tab = self.get_active_data_tab()
        if tab:
            tab.lock_all_columns()

    def on_unlock_all_columns_requested(self):
        tab = self.get_active_data_tab()
        if tab:
            tab.unlock_all_columns()

    def on_settings_requested(self):
        dialog = SettingsDialog(self, self.tg_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Re-apply settings
            self.config.load()
            refresh_config_paths()
            self.apply_theme(self.config.get("ui.theme"))
            self.load_settings()

            # Re-initialize Telegram manager to pick up moved session or new credentials
            if hasattr(self, 'tg_manager'):
                self.tg_manager.reset_client()

            # If the DB path changed, we might need to reconnect
            self.init_db_connections()
            # Reconstruct global tabs to use new connection/path
            self.catalog_tab.update_database("global_db")
            self.opener_tab.update_database("global_db")
            self.type_res_tab.update_database("global_db")
            self.seasons_tab.update_database("global_db")
            self.domains_tab.update_database("global_db")

            # Refresh year-based tabs
            self.on_year_selected(self.year_tree.currentIndex())

    def log(self, message, is_error=False, target="resources"):
        if target == "resources" and hasattr(self, 'resources_tab'):
            self.resources_tab.log(message, is_error)
        elif target == "registry" and hasattr(self, 'registry_tab'):
            self.registry_tab.log(message, is_error)
        elif hasattr(self, 'resources_tab'):
            self.resources_tab.log(message, is_error)

if __name__ == "__main__":
    if os.name == 'nt':
        myappid = 'storeetude.precuremanager.desktopcenter.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    init_databases()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon(r"img\icon.ico"))

    window = PrecureManagerApp()
    window.show()
    sys.exit(app.exec())
