from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMessageBox
from core.app_state import AppMode

class ActionsManager:
    def __init__(self, main_win):
        self.win = main_win
        self.init_actions()

    def init_actions(self):
        # Archivo
        self.save_action = QAction("Guardar", self.win)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.win.save_requested.emit)

        self.export_action = QAction("Exportar tabla a CSV", self.win)
        self.export_action.triggered.connect(self.win.export_requested.emit)

        self.import_action = QAction("Importar tabla desde CSV", self.win)
        self.import_action.triggered.connect(self.win.import_requested.emit)

        self.config_action = QAction("Configuración", self.win)
        self.config_action.triggered.connect(self.win.settings_requested.emit)

        self.exit_action = QAction("Salir", self.win)
        self.exit_action.triggered.connect(self.win.close)

        # Edición
        self.add_row_action = QAction("Añadir fila", self.win)
        self.add_row_action.triggered.connect(self.win.add_row_requested.emit)

        self.scan_masters_action = QAction("Escanear carpetas maestras", self.win)
        self.scan_masters_action.triggered.connect(self.win.scan_master_folders_requested.emit)

        self.migrate_resources_action = QAction("Migrar Recursos de años", self.win)
        self.migrate_resources_action.triggered.connect(self.win.migrate_resources_requested.emit)

        self.migrate_registry_action = QAction("Migrar Registros de años", self.win)
        self.migrate_registry_action.triggered.connect(self.win.migrate_registry_requested.emit)

        self.regen_index_action = QAction("Regenerar la columna index de registros", self.win)
        self.regen_index_action.triggered.connect(self.win.regenerate_index_requested.emit)

        self.recalc_lapses_action = QAction("Recalcular Lapsos de rangos de registros", self.win)
        self.recalc_lapses_action.triggered.connect(self.win.recalculate_lapses_requested.emit)

        self.recalc_models_action = QAction("Recalcular modelos detectados de registros", self.win)
        self.recalc_models_action.triggered.connect(self.win.recalculate_models_requested.emit)

        self.update_links_action = QAction("Actualizar vinculación de archivos", self.win)
        self.update_links_action.triggered.connect(self.win.update_links_requested.emit)

        # Herramientas
        self.scan_link_action = QAction("Escanear y vincular archivos", self.win)
        self.scan_link_action.triggered.connect(self.win.scan_link_requested.emit)

        self.scan_new_sd_action = QAction("Búsqueda de nuevas soundtracks con lyrics", self.win)
        self.scan_new_sd_action.triggered.connect(self.win.scan_new_sd_requested.emit)

        self.report_materials_action = QAction("Reportar Materiales Vistos", self.win)
        self.report_materials_action.triggered.connect(self.win.report_materials_requested.emit)

        self.tg_download_action = QAction("Descargar nuevo contenido desde telegram", self.win)
        self.tg_download_action.triggered.connect(self.win.tg_download_requested.emit)

        self.manage_journals_action = QAction("Administrar Jornadas", self.win)
        self.manage_journals_action.triggered.connect(self.win.manage_journals_requested.emit)

        # Vista
        self.toggle_sidebar = QAction("Años", self.win, checkable=True)
        self.toggle_sidebar.setChecked(True)
        self.toggle_sidebar.triggered.connect(lambda checked: self.win.dock.setVisible(checked))

        self.toggle_console = QAction("Consola SQL", self.win, checkable=True)
        self.toggle_console.setChecked(True)
        self.toggle_console.triggered.connect(self.win.console_toggled.emit)

        self.show_construction_logs = QAction("Mostrar logs de construcción de tablas", self.win, checkable=True)
        self.show_construction_logs.setChecked(False)
        self.show_construction_logs.triggered.connect(self.win.save_requested.emit)

        self.auto_resize_action = QAction("Auto-ajustar ancho de columnas", self.win, checkable=True)
        self.auto_resize_action.setChecked(True)
        self.auto_resize_action.triggered.connect(self.win.auto_resize_toggled.emit)

        self.resize_to_contents_action = QAction("Ajustar anchos al contenido", self.win)
        self.resize_to_contents_action.triggered.connect(self.win.resize_requested.emit)

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

        self.edit_menu = menubar.addMenu("Edición")
        self.edit_menu.addAction(self.add_row_action)
        self.edit_menu.addAction(self.scan_masters_action)
        self.edit_menu.addAction(self.migrate_resources_action)
        self.edit_menu.addAction(self.migrate_registry_action)
        self.edit_menu.addAction(self.regen_index_action)
        self.edit_menu.addAction(self.recalc_lapses_action)
        self.edit_menu.addAction(self.recalc_models_action)
        self.edit_menu.addAction(self.update_links_action)

        self.tools_menu = menubar.addMenu("Herramientas")
        self.tools_menu.addAction(self.scan_link_action)
        self.tools_menu.addAction(self.scan_new_sd_action)
        self.tools_menu.addAction(self.report_materials_action)
        self.tools_menu.addAction(self.tg_download_action)
        self.tools_menu.addSeparator()
        self.tools_menu.addAction(self.manage_journals_action)

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
