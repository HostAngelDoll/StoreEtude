import sys
import os
import re
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QTabWidget, QLabel, QPushButton, QHBoxLayout,
                             QTreeView, QHeaderView, QDockWidget, QTableView,
                             QAbstractItemView, QDialog, QFormLayout, QLineEdit,
                             QSpinBox, QCheckBox, QDialogButtonBox, QMessageBox,
                             QComboBox, QPlainTextEdit, QMenuBar, QMenu, QInputDialog,
                             QSplitter)
from PyQt6.QtCore import Qt, QStringListModel
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction, QCursor, QTextCharFormat, QColor
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel, QSqlRecord, QSqlQuery

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
            if field_name.lower() == "idx" and row < 0:
                continue

            label = field_name.replace("_", " ").title()

            if "is_" in field_name.lower():
                widget = QCheckBox()
                if row >= 0:
                    widget.setChecked(bool(self.record.value(i)))
            elif "total_" in field_name.lower() or "_num" in field_name.lower() or "episode_" in field_name.lower():
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

class ColumnHeaderView(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionsClickable(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)

    def show_context_menu(self, pos):
        logical_index = self.logicalIndexAt(pos)
        if logical_index < 0:
            return

        menu = QMenu(self)
        add_left = menu.addAction("Agregar columna (izquierda)")
        add_right = menu.addAction("Agregar columna (derecha)")
        rename_col = menu.addAction("Renombrar columna")
        delete_col = menu.addAction("Eliminar columna")

        action = menu.exec(self.mapToGlobal(pos))
        if not action:
            return

        table_tab = self.parent().parent() # QTableView -> DataTableTab
        if action == add_left:
            table_tab.add_column(logical_index)
        elif action == add_right:
            table_tab.add_column(logical_index + 1)
        elif action == rename_col:
            table_tab.rename_column(logical_index)
        elif action == delete_col:
            table_tab.delete_column(logical_index)

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

        # Custom Header
        header = ColumnHeaderView(Qt.Orientation.Horizontal, self.view)
        self.view.setHorizontalHeader(header)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # CRUD Buttons
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

        # Main Splitter for Table and Console
        self.main_splitter = QSplitter(Qt.Orientation.Vertical)
        self.main_splitter.addWidget(self.view)

        # SQL Console Area
        self.console_area = QWidget()
        self.console_layout = QVBoxLayout(self.console_area)
        self.console_layout.setContentsMargins(0, 5, 0, 0)

        # Splitter for SQL Command and Log
        self.sql_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left side: Command
        self.cmd_container = QWidget()
        cmd_layout = QVBoxLayout(self.cmd_container)
        cmd_layout.setContentsMargins(0,0,0,0)
        cmd_layout.addWidget(QLabel("SQL Commands:"))
        self.sql_console = QPlainTextEdit()
        cmd_layout.addWidget(self.sql_console)

        # Right side: Log
        self.log_container = QWidget()
        log_layout = QVBoxLayout(self.log_container)
        log_layout.setContentsMargins(0,0,0,0)
        log_layout.addWidget(QLabel("SQL Log:"))
        self.log_viewer = QPlainTextEdit()
        self.log_viewer.setReadOnly(True)
        # Dark theme for log viewer
        self.log_viewer.setStyleSheet("background-color: black; color: white; font-family: Consolas, monospace;")
        log_layout.addWidget(self.log_viewer)

        self.sql_splitter.addWidget(self.cmd_container)
        self.sql_splitter.addWidget(self.log_container)

        self.btn_run_sql = QPushButton("Ejecutar SQL")
        self.btn_run_sql.clicked.connect(self.run_sql_script)

        self.console_layout.addWidget(self.sql_splitter)
        self.console_layout.addWidget(self.btn_run_sql)

        self.main_splitter.addWidget(self.console_area)
        self.main_splitter.setStretchFactor(0, 3)
        self.main_splitter.setStretchFactor(1, 1)

        self.layout.addWidget(self.main_splitter)
        self.layout.addLayout(self.btn_layout)

    def log(self, message, is_error=False):
        self.log_viewer.moveCursor(Qt.MoveOperation.End)
        fmt = QTextCharFormat()
        if is_error:
            fmt.setForeground(QColor("red"))
            prefix = "[ERROR] "
        else:
            fmt.setForeground(QColor("white"))
            prefix = "[INFO] "

        self.log_viewer.setCurrentCharFormat(fmt)
        self.log_viewer.insertPlainText(f"{prefix}{message}\n")
        self.log_viewer.moveCursor(Qt.MoveOperation.End)

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

    def run_sql_script(self):
        script = self.sql_console.toPlainText().strip()
        if not script:
            return

        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)
        if query.exec(script):
            self.log(f"Ejecutado con éxito.")

            # Detect CREATE TABLE or DROP TABLE
            create_match = re.search(r"CREATE\s+TABLE\s+(\w+)", script, re.IGNORECASE)
            drop_match = re.search(r"DROP\s+TABLE\s+(\w+)", script, re.IGNORECASE)

            if create_match:
                new_table = create_match.group(1)
                self.table_name = new_table
                self.model.setTable(new_table)
                self.log(f"Vista vinculada a nueva tabla: {new_table}")
            elif drop_match:
                dropped_table = drop_match.group(1)
                if dropped_table.lower() == self.table_name.lower():
                    self.model.clear()
                    self.log(f"Tabla activa '{dropped_table}' eliminada. Vista limpiada.")

            self.model.select()
            self.sql_console.clear()
        else:
            err_msg = query.lastError().text()
            self.log(f"Error: {err_msg}", is_error=True)

    def add_column(self, position):
        col_name, ok = QInputDialog.getText(self, "Nueva Columna", "Nombre de la columna:")
        if not ok or not col_name:
            return

        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)

        current_cols_count = self.model.record().count()
        if query.exec(f"ALTER TABLE \"{self.table_name}\" ADD COLUMN \"{col_name}\" TEXT"):
            self.log(f"Columna '{col_name}' añadida.")
            self.model.select()
            if position < current_cols_count:
                QMessageBox.information(self, "Columna Añadida",
                    "Nota: SQLite solo permite añadir columnas al final. La columna se ha añadido al final de la tabla.")
        else:
            self.log(f"Error añadiendo columna: {query.lastError().text()}", is_error=True)

    def rename_column(self, index):
        old_name = self.model.record().fieldName(index)
        new_name, ok = QInputDialog.getText(self, "Renombrar Columna", f"Nuevo nombre para '{old_name}':", text=old_name)
        if not ok or not new_name or new_name == old_name:
            return

        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)

        self.model.submitAll()

        sql = f'ALTER TABLE "{self.table_name}" RENAME COLUMN "{old_name}" TO "{new_name}"'
        if query.exec(sql):
            self.log(f"Columna '{old_name}' renombrada a '{new_name}'.")
            self.model.setTable(self.table_name)
            self.model.select()
        else:
            self.log(f"Error renombrando columna: {query.lastError().text()}", is_error=True)

    def delete_column(self, index):
        col_name = self.model.record().fieldName(index)
        if QMessageBox.question(self, "Confirmar", f"¿Seguro que quieres eliminar la columna '{col_name}'?") != QMessageBox.StandardButton.Yes:
            return

        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)
        if query.exec(f'ALTER TABLE "{self.table_name}" DROP COLUMN "{col_name}"'):
            self.log(f"Columna '{col_name}' eliminada.")
            self.model.setTable(self.table_name)
            self.model.select()
        else:
            self.log(f"Error eliminando columna: {query.lastError().text()}", is_error=True)


    def update_database(self, db_conn_name):
        self.db_conn_name = db_conn_name
        self.model = QSqlTableModel(self, QSqlDatabase.database(db_conn_name))
        self.model.setTable(self.table_name)
        self.model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.model.select()
        self.view.setModel(self.model)

    def set_console_visible(self, visible):
        self.console_area.setVisible(visible)

class PrecureManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Precure Media Manager - Core System")
        self.setGeometry(100, 100, 1200, 800)

        self.init_db_connections()
        
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

        self.global_subtabs.addTab(self.catalog_tab, "Catálogo")
        self.global_subtabs.addTab(self.opener_tab, "Modelos Opener")
        self.global_subtabs.addTab(self.type_res_tab, "Tipos Recursos")
        self.global_subtabs.addTab(self.seasons_tab, "Temporadas")
        global_layout.addWidget(self.global_subtabs)

        self.tabs.addTab(self.registry_tab, "Registros")
        self.tabs.addTab(self.resources_tab, "Recursos")
        self.tabs.addTab(self.global_tab_container, "Global")

        self.init_menu_bar()

    def init_menu_bar(self):
        menubar = self.menuBar()

        # Archivo
        file_menu = menubar.addMenu("Archivo")
        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Vista
        view_menu = menubar.addMenu("Vista")
        panels_submenu = view_menu.addMenu("Mostrar Paneles")

        toggle_sidebar = QAction("Años", self, checkable=True)
        toggle_sidebar.setChecked(True)
        toggle_sidebar.triggered.connect(lambda: self.dock.setVisible(toggle_sidebar.isChecked()))
        panels_submenu.addAction(toggle_sidebar)

        toggle_console = QAction("Consola SQL", self, checkable=True)
        toggle_console.setChecked(True)
        toggle_console.triggered.connect(self.toggle_sql_consoles)
        panels_submenu.addAction(toggle_console)

        # Ayuda
        help_menu = menubar.addMenu("Ayuda")
        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(lambda: QMessageBox.information(self, "Ayuda", "Precure Media Manager v1.0\nSistema de gestión de recursos."))
        help_menu.addAction(about_action)

    def toggle_sql_consoles(self):
        is_visible = self.sender().isChecked()
        self.registry_tab.set_console_visible(is_visible)
        self.resources_tab.set_console_visible(is_visible)
        self.catalog_tab.set_console_visible(is_visible)
        self.opener_tab.set_console_visible(is_visible)
        self.type_res_tab.set_console_visible(is_visible)
        self.seasons_tab.set_console_visible(is_visible)

    def init_db_connections(self):
        if not QSqlDatabase.contains("global_db"):
            db = QSqlDatabase.addDatabase("QSQLITE", "global_db")
            db.setDatabaseName(GLOBAL_DB_PATH)
            db.open()

        if not QSqlDatabase.contains("year_db"):
            db = QSqlDatabase.addDatabase("QSQLITE", "year_db")
            db.setDatabaseName(get_yearly_db_path(2004))
            db.open()

    def init_sidebar(self):
        self.dock = QDockWidget("Años", self)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)

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

        self.dock.setWidget(self.year_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)

    def on_year_selected(self, index):
        year = index.data()
        db_path = get_yearly_db_path(year)

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
