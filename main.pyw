import sys
import os
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QTabWidget, QLabel, QPushButton, QHBoxLayout,
                             QTreeView, QHeaderView, QDockWidget, QTableView,
                             QAbstractItemView, QDialog, QFormLayout, QLineEdit,
                             QSpinBox, QCheckBox, QDialogButtonBox, QMessageBox,
                             QComboBox)
from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import QStandardItemModel, QStandardItem
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel, QSqlRecord

from db_manager import init_databases, GLOBAL_DB_PATH, get_yearly_db_path

class DatabaseForm(QDialog):
    def __init__(self, model, row=-1, parent=None):
        super().__init__(parent)
        self.model = model
        self.row = row
        self.record = model.record(row) if row >= 0 else model.record()
        self.setWindowTitle("Añadir Registro" if row < 0 else "Editar Registro")
        self.setMinimumWidth(400)

        self.layout = QFormLayout(self)
        self.widgets = {}

        for i in range(self.record.count()):
            field_name = self.record.fieldName(i)
            # Skip auto-increment columns if adding new
            if field_name.lower() == "idx" and row < 0:
                continue

            label = field_name.replace("_", " ").title()

            # Basic widget type detection
            if "is_" in field_name.lower():
                widget = QCheckBox()
                if row >= 0:
                    widget.setChecked(bool(self.record.value(i)))
            elif "total_" in field_name.lower() or "_num" in field_name.lower():
                widget = QSpinBox()
                widget.setRange(0, 9999)
                if row >= 0:
                    widget.setValue(int(self.record.value(i) or 0))
            else:
                widget = QLineEdit()
                if row >= 0:
                    widget.setText(str(self.record.value(i) or ""))

            self.layout.addRow(label, widget)
            self.widgets[field_name] = widget

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addRow(self.buttons)

    def accept(self):
        for i in range(self.record.count()):
            field_name = self.record.fieldName(i)
            if field_name in self.widgets:
                widget = self.widgets[field_name]
                if isinstance(widget, QCheckBox):
                    self.record.setValue(i, 1 if widget.isChecked() else 0)
                elif isinstance(widget, QSpinBox):
                    self.record.setValue(i, widget.value())
                else:
                    self.record.setValue(i, widget.text())

        if self.row >= 0:
            if self.model.setRecord(self.row, self.record):
                if self.model.submitAll():
                    super().accept()
                else:
                    QMessageBox.critical(self, "Error", f"No se pudo guardar en la base de datos: {self.model.lastError().text()}")
            else:
                QMessageBox.critical(self, "Error", "No se pudo actualizar el registro en el modelo.")
        else:
            if self.model.insertRecord(-1, self.record):
                if self.model.submitAll():
                    super().accept()
                else:
                    QMessageBox.critical(self, "Error", f"No se pudo guardar en la base de datos: {self.model.lastError().text()}")
            else:
                QMessageBox.critical(self, "Error", "No se pudo añadir el registro al modelo.")

        self.model.select()

class DataTableTab(QWidget):
    def __init__(self, db_conn_name, table_name, parent=None):
        super().__init__(parent)
        self.db_conn_name = db_conn_name
        self.table_name = table_name
        self.layout = QVBoxLayout(self)

        self.model = QSqlTableModel(self, QSqlDatabase.database(db_conn_name))
        self.model.setTable(table_name)
        self.model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.model.select()

        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        self.btn_layout = QHBoxLayout()
        self.btn_add = QPushButton("Añadir")
        self.btn_edit = QPushButton("Editar")
        self.btn_delete = QPushButton("Borrar")

        self.btn_add.clicked.connect(self.add_record)
        self.btn_edit.clicked.connect(self.edit_record)
        self.btn_delete.clicked.connect(self.delete_record)

        self.btn_layout.addWidget(self.btn_add)
        self.btn_layout.addWidget(self.btn_edit)
        self.btn_layout.addWidget(self.btn_delete)

        self.layout.addWidget(self.view)
        self.layout.addLayout(self.btn_layout)

    def add_record(self):
        form = DatabaseForm(self.model, parent=self)
        form.exec()

    def edit_record(self):
        index = self.view.currentIndex()
        if index.isValid():
            form = DatabaseForm(self.model, index.row(), parent=self)
            form.exec()
        else:
            QMessageBox.warning(self, "Selección", "Por favor selecciona una fila.")

    def delete_record(self):
        index = self.view.currentIndex()
        if index.isValid():
            if QMessageBox.question(self, "Confirmar", "¿Seguro que quieres borrar este registro?") == QMessageBox.StandardButton.Yes:
                self.model.removeRow(index.row())
                self.model.submitAll()
                self.model.select()
        else:
            QMessageBox.warning(self, "Selección", "Por favor selecciona una fila.")

    def update_database(self, db_conn_name):
        self.db_conn_name = db_conn_name
        self.model = QSqlTableModel(self, QSqlDatabase.database(db_conn_name))
        self.model.setTable(self.table_name)
        self.model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.model.select()
        self.view.setModel(self.model)

class PrecureManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Precure Media Manager - Core System")
        self.setGeometry(100, 100, 1100, 700)

        self.init_db_connections()
        
        # Main Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)
        
        # Tabs
        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs, 3) # Left side with more weight
        
        # Yearly Tabs
        self.resources_tab = DataTableTab("year_db", "T_Resources")
        self.registry_tab = DataTableTab("year_db", "T_Registry")
        
        # Global Tabs
        self.seasons_tab = DataTableTab("global_db", "T_Seasons")
        self.catalog_tab = DataTableTab("global_db", "T_Type_Catalog_Reg")
        self.opener_tab = DataTableTab("global_db", "T_Opener_Models")
        self.type_res_tab = DataTableTab("global_db", "T_Type_Resources")
        
        self.tabs.addTab(self.resources_tab, "Recursos")
        self.tabs.addTab(self.registry_tab, "Registros")
        self.tabs.addTab(self.seasons_tab, "Temporadas")
        self.tabs.addTab(self.catalog_tab, "Catálogo")
        self.tabs.addTab(self.opener_tab, "Modelos Opener")
        self.tabs.addTab(self.type_res_tab, "Tipos Recursos")

        # Sidebar (Right)
        self.init_sidebar()

    def init_db_connections(self):
        # Global DB
        if not QSqlDatabase.contains("global_db"):
            db = QSqlDatabase.addDatabase("QSQLITE", "global_db")
            db.setDatabaseName(GLOBAL_DB_PATH)
            if not db.open():
                print("Could not open global database")

        # Yearly DB (placeholder for now)
        if not QSqlDatabase.contains("year_db"):
            db = QSqlDatabase.addDatabase("QSQLITE", "year_db")
            # Default to 2004
            db.setDatabaseName(get_yearly_db_path(2004))
            db.open()

    def init_sidebar(self):
        dock = QDockWidget("Años", self)
        dock.setAllowedAreas(Qt.DockWidgetArea.RightDockWidgetArea)
        
        self.year_tree = QTreeView()
        self.year_tree.setHeaderHidden(True)
        self.year_model = QStandardItemModel()
        root_node = self.year_model.invisibleRootItem()
        
        for year in range(2004, 2027):
            item = QStandardItem(str(year))
            item.setEditable(False)
            root_node.appendRow(item)

        self.year_tree.setModel(self.year_model)
        self.year_tree.clicked.connect(self.on_year_selected)
        
        dock.setWidget(self.year_tree)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

    def on_year_selected(self, index):
        year = index.data()
        db_path = get_yearly_db_path(year)

        # Re-open year_db with new path
        db = QSqlDatabase.database("year_db")
        db.close()
        db.setDatabaseName(db_path)
        if db.open():
            self.resources_tab.update_database("year_db")
            self.registry_tab.update_database("year_db")
        else:
            QMessageBox.critical(self, "Error", f"No se pudo abrir la base de datos del año {year}.\n¿Está el disco E: conectado?")

if __name__ == "__main__":
    init_databases()
    app = QApplication(sys.argv)
    app.setStyle("Fusion") 
    window = PrecureManagerApp()
    window.show()
    sys.exit(app.exec())
