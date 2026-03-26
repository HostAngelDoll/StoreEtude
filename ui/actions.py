from PyQt6.QtGui import QAction
from PyQt6.QtWidgets import QMenu, QApplication, QDialog, QMessageBox
from PyQt6.QtCore import Qt

class ActionsManager:
    def __init__(self, main_win):
        self.win = main_win
        self.init_actions()

    def init_actions(self):
        # Archivo
        self.save_action = QAction("Guardar", self.win)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.win.controller.save_settings)

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
        self.scan_masters_action.triggered.connect(lambda: self.win.controller.run_operation("scan_masters"))

        self.migrate_resources_action = QAction("Migrar Recursos de años", self.win)
        self.migrate_resources_action.triggered.connect(lambda: self.win.controller.run_operation("migrate_resources"))

        self.migrate_registry_action = QAction("Migrar Registros de años", self.win)
        self.migrate_registry_action.triggered.connect(lambda: self.win.controller.run_operation("migrate_registry"))

        self.regen_index_action = QAction("Regenerar la columna index de registros", self.win)
        self.regen_index_action.triggered.connect(lambda: self.win.controller.run_operation("regen_index"))

        self.recalc_lapses_action = QAction("Recalcular Lapsos de rangos de registros", self.win)
        self.recalc_lapses_action.triggered.connect(lambda: self.win.controller.run_operation("recalc_lapses"))

        self.recalc_models_action = QAction("Recalcular modelos detectados de registros", self.win)
        self.recalc_models_action.triggered.connect(lambda: self.win.controller.run_operation("recalc_models"))

        self.update_links_action = QAction("Actualizar vinculación de archivos", self.win)
        self.update_links_action.triggered.connect(lambda: self.win.controller.run_operation("update_links"))

        # Herramientas
        self.scan_link_action = QAction("Escanear y vincular archivos", self.win)
        self.scan_link_action.triggered.connect(lambda: self.win.controller.run_operation("scan_link"))

        self.scan_new_sd_action = QAction("Búsqueda de nuevas soundtracks con lyrics", self.win)
        self.scan_new_sd_action.triggered.connect(lambda: self.win.controller.run_operation("scan_new_sd"))

        self.report_materials_action = QAction("Reportar Materiales Vistos", self.win)
        self.report_materials_action.triggered.connect(lambda: self.win.controller.run_dialog("report_materials"))

        self.tg_download_action = QAction("Descargar nuevo contenido desde telegram", self.win)
        self.tg_download_action.triggered.connect(lambda: self.win.controller.run_dialog("tg_download"))

        self.manage_journals_action = QAction("Administrar Jornadas", self.win)
        self.manage_journals_action.triggered.connect(lambda: self.win.controller.run_dialog("manage_journals"))

        # Vista
        self.toggle_sidebar = QAction("Años", self.win, checkable=True)
        self.toggle_sidebar.setChecked(True)
        self.toggle_sidebar.triggered.connect(lambda checked: self.win.dock.setVisible(checked))

        self.toggle_console = QAction("Consola SQL", self.win, checkable=True)
        self.toggle_console.setChecked(True)
        self.toggle_console.triggered.connect(self.win.toggle_sql_consoles)

        self.show_construction_logs = QAction("Mostrar logs de construcción de tablas", self.win, checkable=True)
        self.show_construction_logs.setChecked(False)

        self.auto_resize_action = QAction("Auto-ajustar ancho de columnas", self.win, checkable=True)
        self.auto_resize_action.setChecked(True)
        self.auto_resize_action.triggered.connect(lambda checked: self.win.set_auto_resize_columns(checked))

        self.resize_to_contents_action = QAction("Ajustar anchos al contenido", self.win)
        self.resize_to_contents_action.triggered.connect(self.on_resize_requested)

        # Ayuda
        self.about_action = QAction("Acerca de", self.win)
        self.about_action.triggered.connect(lambda: QMessageBox.information(self.win, "Ayuda", "Precure Media Manager v1.1 - Refactorizado"))

    def setup_menu(self, menubar):
        file_menu = menubar.addMenu("Archivo")
        file_menu.addAction(self.save_action); file_menu.addAction(self.export_action); file_menu.addAction(self.import_action)
        file_menu.addSeparator(); file_menu.addAction(self.config_action)
        file_menu.addSeparator(); file_menu.addAction(self.exit_action)

        self.edit_menu = menubar.addMenu("Edición")
        self.edit_menu.addAction(self.add_row_action); self.edit_menu.addAction(self.scan_masters_action)
        self.edit_menu.addAction(self.migrate_resources_action); self.edit_menu.addAction(self.migrate_registry_action)
        self.edit_menu.addAction(self.regen_index_action); self.edit_menu.addAction(self.recalc_lapses_action)
        self.edit_menu.addAction(self.recalc_models_action); self.edit_menu.addAction(self.update_links_action)

        self.tools_menu = menubar.addMenu("Herramientas")
        self.tools_menu.addAction(self.scan_link_action); self.tools_menu.addAction(self.scan_new_sd_action)
        self.tools_menu.addAction(self.report_materials_action); self.tools_menu.addAction(self.tg_download_action)
        self.tools_menu.addSeparator(); self.tools_menu.addAction(self.manage_journals_action)

        view_menu = menubar.addMenu("Vista")
        panels = view_menu.addMenu("Mostrar Paneles")
        panels.addAction(self.toggle_sidebar); panels.addAction(self.toggle_console)
        view_menu.addMenu("Mostrar tipos de logs").addAction(self.show_construction_logs)
        view_menu.addAction(self.auto_resize_action); view_menu.addSeparator(); view_menu.addAction(self.resize_to_contents_action)
        menubar.addMenu("Ayuda").addAction(self.about_action)

    def get_active_tab(self):
        curr = self.win.tabs.currentWidget()
        return self.win.global_subtabs.currentWidget() if curr == self.win.global_tab_container else curr

    def export_active_tab(self):
        tab = self.get_active_tab()
        if hasattr(tab, 'export_to_csv'): tab.export_to_csv()

    def import_active_tab(self):
        tab = self.get_active_tab()
        if hasattr(tab, 'import_from_csv'): tab.import_from_csv()

    def on_settings_requested(self):
        from dialogs.settings_dialog import SettingsDialog
        if SettingsDialog(self.win, self.win.controller.config_ctrl, self.win.controller.network_ctrl).exec() == QDialog.DialogCode.Accepted:
            self.win.controller.delayed_init()

    def on_add_row_requested(self):
        tab = self.get_active_tab()
        if hasattr(tab, 'add_record'): tab.add_record()

    def on_resize_requested(self):
        tab = self.get_active_tab()
        if hasattr(tab, 'resize_to_contents'): tab.resize_to_contents()
