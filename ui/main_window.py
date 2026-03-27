import os
from datetime import datetime
from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout,
                             QTabWidget, QHBoxLayout, QTreeView,
                             QDockWidget)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon

from data_table import DataTableTab
from ui.warning_bar import OfflineWarningBar

class MainWindow(QMainWindow):
    # Signals for Controller
    year_selected = pyqtSignal(int)
    report_materials_requested = pyqtSignal()
    tg_download_requested = pyqtSignal()
    manage_journals_requested = pyqtSignal()
    scan_master_folders_requested = pyqtSignal()
    update_links_requested = pyqtSignal()
    scan_link_requested = pyqtSignal()
    scan_new_sd_requested = pyqtSignal()
    migrate_resources_requested = pyqtSignal()
    migrate_registry_requested = pyqtSignal()
    regenerate_index_requested = pyqtSignal()
    recalculate_lapses_requested = pyqtSignal()
    recalculate_models_requested = pyqtSignal()
    auto_resize_toggled = pyqtSignal(bool)
    console_toggled = pyqtSignal(bool)
    settings_requested = pyqtSignal()
    save_requested = pyqtSignal()
    export_requested = pyqtSignal()
    import_requested = pyqtSignal()
    add_row_requested = pyqtSignal()
    resize_requested = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Precure Media Manager - Core System")
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.setGeometry(100, 100, 1200, 800)

        self._is_offline = False # Cache for menu state updates

        self._init_ui()
        self._init_menu()

    def _init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.outer_layout = QVBoxLayout(central_widget)
        self.outer_layout.setContentsMargins(0, 0, 0, 0)
        self.outer_layout.setSpacing(0)

        self.warning_bar = OfflineWarningBar()
        self.warning_bar.setVisible(False)
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
        self.year_tree.clicked.connect(self._on_year_clicked)

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

        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.global_subtabs.currentChanged.connect(self.on_tab_changed)

    def _init_menu(self):
        from ui.actions import ActionsManager
        self.actions = ActionsManager(self)
        self.actions.setup_menu(self.menuBar())
        self.update_menu_states()

    def _on_year_clicked(self, index):
        if index.isValid():
            self.year_selected.emit(int(index.data()))

    def get_current_year(self):
        index = self.year_tree.currentIndex()
        return int(index.data()) if index.isValid() else 2004

    def on_tab_changed(self, index):
        self.update_menu_states()

    def set_offline_mode(self, offline):
        self._is_offline = offline
        self.warning_bar.setVisible(offline)
        self.update_menu_states()

    def update_menu_states(self):
        if not hasattr(self, 'actions'): return

        current_tab = self.tabs.currentWidget()

        # Tools menu - restricted in offline but Journals allowed
        if self._is_offline:
            for action in self.actions.tools_menu.actions():
                if action == self.actions.manage_journals_action:
                    action.setEnabled(True)
                else:
                    action.setEnabled(False)
        else:
            for action in self.actions.tools_menu.actions():
                action.setEnabled(True)

        # Edit menu - restricted in offline
        if self._is_offline:
            self.actions.edit_menu.setEnabled(True)
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

    def log(self, message, is_error=False, target="resources"):
        if target == "resources" and hasattr(self, 'resources_tab'):
            self.resources_tab.log(message, is_error)
        elif target == "registry" and hasattr(self, 'registry_tab'):
            self.registry_tab.log(message, is_error)
        elif hasattr(self, 'resources_tab'):
            self.resources_tab.log(message, is_error)

    def set_auto_resize_columns(self, enabled):
        for tab in self.all_tabs:
            tab.set_auto_resize(enabled)

    def toggle_sql_consoles(self, visible):
        for tab in self.all_tabs:
            tab.set_console_visible(visible)

    def get_active_tab_widget(self):
        current_widget = self.tabs.currentWidget()
        if current_widget == self.global_tab_container:
            return self.global_subtabs.currentWidget()
        return current_widget

    def closeEvent(self, event):
        self.closed.emit()
        super().closeEvent(event)
