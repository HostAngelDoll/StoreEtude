import os
import re
import csv
import sqlite3
from datetime import datetime
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableView,
                             QHeaderView, QPushButton, QLabel, QPlainTextEdit,
                             QSplitter, QMessageBox, QFileDialog, QInputDialog,
                             QApplication, QAbstractItemView, QMenu, QProgressDialog,
                             QMainWindow)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor
from PyQt6.QtSql import (QSqlTableModel, QSqlRelationalTableModel, QSqlRelation,
                         QSqlRelationalDelegate, QSqlQuery, QSqlDatabase)

from dialogs.database_form import DatabaseForm
from filter_widget import FilterMenu
from core.app_state import AppMode
from config_manager import ConfigManager
from .delegates.combo_delegate import ComboDelegate
from .column_manager import ColumnHeaderView
from .table_model import create_table_model, FilterManager

class DataTableTab(QWidget):
    def __init__(self, db_conn_name, table_name, parent=None):
        super().__init__(parent)
        self.db_conn_name = db_conn_name
        self.table_name = table_name
        self.layout = QVBoxLayout(self)
        self.view = QTableView()
        self.model = None
        self.init_ui_components()

    def init_ui_components(self):
        self.btn_layout = QHBoxLayout()
        self.btn_add, self.btn_edit, self.btn_delete = QPushButton("Añadir"), QPushButton("Editar"), QPushButton("Borrar")
        for b in [self.btn_add, self.btn_edit, self.btn_delete]: self.btn_layout.addWidget(b)
        self.btn_add.clicked.connect(self.add_record)
        self.btn_edit.clicked.connect(self.edit_record)
        self.btn_delete.clicked.connect(self.delete_record)

        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.addWidget(self.view)

        self.console_area = QWidget()
        self.console_layout = QVBoxLayout(self.console_area)
        self.sql_splitter = QSplitter(Qt.Orientation.Horizontal)

        self.cmd_container, self.log_container = QWidget(), QWidget()
        for c, l in [(self.cmd_container, "SQL Commands:"), (self.log_container, "SQL Log:")]:
            lay = QVBoxLayout(c); lay.addWidget(QLabel(l))
        self.sql_console, self.log_viewer = QPlainTextEdit(), QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        self.log_viewer.setStyleSheet("background-color: black; color: white; font-family: Consolas, monospace;")
        self.cmd_container.layout().addWidget(self.sql_console)
        self.log_container.layout().addWidget(self.log_viewer)

        self.sql_splitter.addWidget(self.cmd_container); self.sql_splitter.addWidget(self.log_container)
        self.btn_run_sql = QPushButton("Ejecutar SQL"); self.btn_run_sql.clicked.connect(self.run_sql_script)
        self.console_layout.addWidget(self.sql_splitter); self.console_layout.addWidget(self.btn_run_sql)

        self.main_splitter.addWidget(self.console_area)
        self.main_splitter.setStretchFactor(0, 3); self.main_splitter.setStretchFactor(1, 1)
        self.layout.addWidget(self.main_splitter); self.layout.addLayout(self.btn_layout)

    def update_database(self, db_conn_name):
        self.db_conn_name = db_conn_name
        db = QSqlDatabase.database(db_conn_name)
        if not db.isOpen(): return

        self.main_splitter.setUpdatesEnabled(False)
        if self.model: self.model.deleteLater()

        self.model = create_table_model(db_conn_name, self.table_name, self)
        self.filter_manager = FilterManager(self.model, self.table_name)

        new_view = QTableView()
        new_view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        new_view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        new_view.setModel(self.model)
        new_view.setHorizontalHeader(ColumnHeaderView(Qt.Orientation.Horizontal, new_view))

        if isinstance(self.model, QSqlRelationalTableModel):
            new_view.setItemDelegate(QSqlRelationalDelegate(new_view))
        if self.table_name == "T_Registry" and db_conn_name == "year_db":
            new_view.setItemDelegateForColumn(1, ComboDelegate("T_Resources", "title_material", parent=new_view))
            new_view.setItemDelegateForColumn(3, ComboDelegate("T_Type_Catalog_Reg", "type", "category='repeat'", parent=new_view))
            new_view.setItemDelegateForColumn(4, ComboDelegate("T_Type_Catalog_Reg", "type", "category='listen'", parent=new_view))
            new_view.setItemDelegateForColumn(5, ComboDelegate("T_Type_Catalog_Reg", "type", "category='write'", parent=new_view))

        self.main_splitter.replaceWidget(0, new_view)
        self.view = new_view
        self.apply_column_configs()
        self.main_splitter.setUpdatesEnabled(True)

    def show_filter_menu(self, col_index, pos):
        vals = set()
        for r in range(self.model.rowCount()): vals.add(self.model.data(self.model.index(r, col_index)))
        menu = FilterMenu(list(vals), self.filter_manager.active_filters.get(col_index), self)
        menu.filter_requested.connect(lambda sel: self.filter_manager.apply_filter(col_index, sel))
        menu.sort_requested.connect(lambda order: (self.model.sort(col_index, order), self.model.select()))
        menu.show_at(pos)

    def add_record(self): DatabaseForm(self.model, parent=self).exec()
    def edit_record(self):
        idx = self.view.currentIndex()
        if idx.isValid(): DatabaseForm(self.model, idx.row(), parent=self).exec()
        else: QMessageBox.warning(self, "Selección", "Por favor selecciona una fila.")
    def delete_record(self):
        idx = self.view.currentIndex()
        if idx.isValid() and QMessageBox.question(self, "Confirmar", "¿Seguro que quieres borrar este registro?") == QMessageBox.StandardButton.Yes:
            self.model.removeRow(idx.row()); self.model.submitAll(); self.model.select()

    def run_sql_script(self):
        script = self.sql_console.toPlainText().strip()
        if not script: return
        db = QSqlDatabase.database(self.db_conn_name)
        for stmt in re.split(r';(?=(?:[^\'"]*[\'"][^\'"]*[\'"])*[^\'"]*$)', script):
            if not stmt.strip(): continue
            q = QSqlQuery(db)
            if not q.exec(stmt.strip()): self.log(f"Error: {q.lastError().text()}", True)
        self.model.select()

    def log(self, msg, is_error=False):
        self.log_viewer.moveCursor(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("red") if is_error else QColor("white"))
        self.log_viewer.setCurrentCharFormat(fmt)
        self.log_viewer.insertPlainText(f"{'[ERROR] ' if is_error else '[INFO] '}{msg}\n")

    def apply_column_configs(self):
        header = self.view.horizontalHeader()
        if not isinstance(header, ColumnHeaderView): return
        header._is_applying_config = True
        config = ConfigManager()
        for i in range(self.model.columnCount()):
            c_cfg = config.get_column_config(self.table_name, self.model.headerData(i, Qt.Orientation.Horizontal))
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            if c_cfg.width: header.resizeSection(i, c_cfg.width)
        header._is_applying_config = False

    def set_console_visible(self, v): self.console_area.setVisible(v)
    def set_auto_resize(self, e): self.apply_column_configs()
