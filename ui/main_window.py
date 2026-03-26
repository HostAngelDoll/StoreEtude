from PyQt6.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QTabWidget, QHBoxLayout, QTreeView, QDockWidget, QMessageBox)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QIcon
from datetime import datetime
import os

from ui.warning_bar import OfflineWarningBar
from ui.table.table_view import DataTableTab
from core.app_state import AppMode

class MainWindow(QMainWindow):
    def __init__(self, controller):
        super().__init__()
        self.controller = controller
        self.setWindowTitle("Precure Media Manager - Core System")
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.setGeometry(100, 100, 1200, 800)
        self._init_ui()
        self._init_menu()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        self.outer_layout = QVBoxLayout(central)
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
        self.year_tree = QTreeView()
        self.year_tree.setHeaderHidden(True)
        self.year_model = QStandardItemModel()
        root = self.year_model.invisibleRootItem()
        for year in range(2004, datetime.now().year + 1):
            item = QStandardItem(str(year)); item.setEditable(False)
            root.appendRow(item)
        self.year_tree.setModel(self.year_model)
        self.year_tree.clicked.connect(self.on_year_selected)
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
        self.global_tabs = [DataTableTab("global_db", t) for t in ["T_Type_Catalog_Reg", "T_Opener_Models", "T_Type_Resources", "T_Seasons", "T_Domains_base"]]
        for tab, name in zip(self.global_tabs, ["Catálogo", "Modelos Opener", "Tipos Recursos", "Temporadas", "Dominios Base"]):
            self.global_subtabs.addTab(tab, name)
        global_layout.addWidget(self.global_subtabs)
        self.tabs.addTab(self.registry_tab, "Registros")
        self.tabs.addTab(self.resources_tab, "Recursos")
        self.tabs.addTab(self.global_tab_container, "Global")
        self.all_tabs = [self.registry_tab, self.resources_tab] + self.global_tabs

    def _init_menu(self):
        from ui.actions import ActionsManager
        self.actions = ActionsManager(self)
        self.actions.setup_menu(self.menuBar())

    def on_year_selected(self, index):
        if index.isValid(): self.controller.open_year_db(int(index.data()))

    def update_offline_mode(self, offline):
        self.warning_bar.setVisible(offline)

    def closeEvent(self, event):
        self.controller.shutdown()
        super().closeEvent(event)
