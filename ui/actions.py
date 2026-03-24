from PyQt6.QtGui import QAction, QMessageBox
from PyQt6.QtWidgets import QMenu, QApplication, QProgressDialog, QDialog
from PyQt6.QtCore import Qt, QThread
import os

class ActionsManager:
    def __init__(self, main_win):
        self.win = main_win
        self.init_actions()

    def init_actions(self):
        # Archivo
        self.save_action = QAction("Guardar", self.win)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.win.save_settings) # Simplified for now

        self.export_action = QAction("Exportar tabla a CSV", self.win)
        self.export_action.triggered.connect(self.export_active_tab)

        self.import_action = QAction("Importar tabla desde CSV", self.win)
        self.import_action.triggered.connect(self.import_active_tab)

        self.config_action = QAction("Configuración", self.win)
        self.config_action.triggered.connect(self.on_settings_requested)

        self.exit_action = QAction("Salir", self.win)
        self.exit_action.triggered.connect(self.win.close)

        # Edición
        self.add_row_action = QAction("Añadir fila", self.win)
        self.add_row_action.triggered.connect(self.on_add_row_requested)

        self.scan_masters_action = QAction("Escanear carpetas maestras", self.win)
        self.scan_masters_action.triggered.connect(self.win.scan_master_folders)

        self.migrate_resources_action = QAction("Migrar Recursos de años", self.win)
        self.migrate_resources_action.triggered.connect(self.win.migrate_resources_from_excel)

        self.migrate_registry_action = QAction("Migrar Registros de años", self.win)
        self.migrate_registry_action.triggered.connect(self.win.migrate_registry_from_excel)

        self.regen_index_action = QAction("Regenerar la columna index de registros", self.win)
        self.regen_index_action.triggered.connect(self.win.regenerate_registry_index)

        self.recalc_lapses_action = QAction("Recalcular Lapsos de rangos de registros", self.win)
        self.recalc_lapses_action.triggered.connect(self.win.recalculate_registry_lapses)

        self.recalc_models_action = QAction("Recalcular modelos detectados de registros", self.win)
        self.recalc_models_action.triggered.connect(self.win.recalculate_registry_models)

        self.update_links_action = QAction("Actualizar vinculación de archivos", self.win)
        self.update_links_action.triggered.connect(self.win.on_update_links_requested)

        # Herramientas
        self.scan_link_action = QAction("Escanear y vincular archivos", self.win)
        self.scan_link_action.triggered.connect(self.win.on_scan_link_requested)

        self.scan_new_sd_action = QAction("Búsqueda de nuevas soundtracks con lyrics", self.win)
        self.scan_new_sd_action.triggered.connect(self.win.on_scan_new_sd_requested)

        self.report_materials_action = QAction("Reportar Materiales Vistos", self.win)
        self.report_materials_action.triggered.connect(self.win.on_report_materials_requested)

        self.tg_download_action = QAction("Descargar nuevo contenido desde telegram", self.win)
        self.tg_download_action.triggered.connect(self.win.on_tg_download_requested)

        # Vista
        self.toggle_sidebar = QAction("Años", self.win, checkable=True)
        self.toggle_sidebar.setChecked(True)
        self.toggle_sidebar.triggered.connect(lambda checked: self.win.dock.setVisible(checked))

        self.toggle_console = QAction("Consola SQL", self.win, checkable=True)
        self.toggle_console.setChecked(True)
        self.toggle_console.triggered.connect(self.win.toggle_sql_consoles)

        self.show_construction_logs = QAction("Mostrar logs de construcción de tablas", self.win, checkable=True)
        self.show_construction_logs.setChecked(False)
        self.show_construction_logs.triggered.connect(self.win.save_settings)

        self.auto_resize_action = QAction("Auto-ajustar ancho de columnas", self.win, checkable=True)
        self.auto_resize_action.setChecked(True)
        self.auto_resize_action.triggered.connect(lambda checked: self.win.set_auto_resize_columns(checked))

        self.resize_to_contents_action = QAction("Ajustar anchos al contenido", self.win)
        self.resize_to_contents_action.triggered.connect(self.on_resize_requested)

        # Ayuda
        self.about_action = QAction("Acerca de", self.win)
        self.about_action.triggered.connect(lambda: QMessageBox.information(self.win, "Ayuda", "Precure Media Manager v1.1"))

    def setup_menu(self, menubar):
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

        help_menu = menubar.addMenu("Ayuda")
        help_menu.addAction(self.about_action)

    def get_active_tab(self):
        # We need a reference back to the window's tabs
        current_widget = self.win.tabs.currentWidget()
        if current_widget == self.win.global_tab_container:
            return self.win.global_subtabs.currentWidget()
        return current_widget

    def export_active_tab(self):
        tab = self.get_active_tab()
        if hasattr(tab, 'export_to_csv'): tab.export_to_csv()

    def import_active_tab(self):
        if self.win.state.mode == AppMode.OFFLINE: return
        tab = self.get_active_tab()
        if hasattr(tab, 'import_from_csv'): tab.import_from_csv()

    def on_settings_requested(self):
        from dialogs.settings_dialog import SettingsDialog
        dialog = SettingsDialog(self.win, self.win.tg_manager)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.win.config.load()
            from db_manager import refresh_config_paths
            refresh_config_paths()
            self.win.apply_theme(self.win.config.get("ui.theme"))
            self.win.load_settings()
            if hasattr(self.win.tg_manager, 'reset_client'):
                self.win.tg_manager.reset_client()
            self.win.init_db_connections()

    def on_add_row_requested(self):
        tab = self.get_active_tab()
        if hasattr(tab, 'add_record'): tab.add_record()

    def on_resize_requested(self):
        tab = self.get_active_tab()
        if hasattr(tab, 'resize_to_contents'): tab.resize_to_contents()

from core.app_state import AppMode
