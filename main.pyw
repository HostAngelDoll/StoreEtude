import sys
import os
import re
import sqlite3
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QTabWidget, QLabel, QPushButton, QHBoxLayout,
                             QTreeView, QHeaderView, QDockWidget, QTableView,
                             QAbstractItemView, QDialog, QFormLayout, QLineEdit,
                             QSpinBox, QCheckBox, QDialogButtonBox, QMessageBox,
                             QComboBox, QPlainTextEdit, QMenuBar, QMenu, QInputDialog,
                             QSplitter, QProgressDialog)
from PyQt6.QtCore import Qt, QStringListModel, QSettings
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction, QCursor, QTextCharFormat, QColor, QTextCursor
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel, QSqlRecord, QSqlQuery, QSqlRelationalTableModel, QSqlRelation, QSqlRelationalDelegate
import openpyxl

from db_manager import init_databases, GLOBAL_DB_PATH, get_yearly_db_path, BASE_DIR_PATH

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

        is_relational = isinstance(model, QSqlRelationalTableModel)

        for i in range(self.record.count()):
            field_name = self.record.fieldName(i)
            if field_name.lower() == "idx" and row < 0:
                continue

            label = field_name.replace("_", " ").title()

            # Check if this field has a relation
            relation = model.relation(i) if is_relational else QSqlRelation()

            if relation.isValid():
                widget = QComboBox()
                rel_model = model.relationModel(i)
                # Ensure the relational model is populated
                rel_model.select()
                widget.setModel(rel_model)
                widget.setModelColumn(rel_model.fieldIndex(relation.displayColumn()))

                if row >= 0:
                    # Find the index of the current value in the relational model
                    current_val = self.record.value(i)
                    for rel_row in range(rel_model.rowCount()):
                        if rel_model.data(rel_model.index(rel_row, rel_model.fieldIndex(relation.indexColumn()))) == current_val:
                            widget.setCurrentIndex(rel_row)
                            break
            elif "is_" in field_name.lower():
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
        is_relational = isinstance(self.model, QSqlRelationalTableModel)
        for i in range(self.record.count()):
            field_name = self.record.fieldName(i)
            if field_name in self.widgets:
                widget = self.widgets[field_name]
                if isinstance(widget, QCheckBox):
                    self.record.setValue(i, 1 if widget.isChecked() else 0)
                elif isinstance(widget, QSpinBox):
                    self.record.setValue(i, widget.value())
                elif isinstance(widget, QComboBox):
                    relation = self.model.relation(i)
                    rel_model = self.model.relationModel(i)
                    current_rel_row = widget.currentIndex()
                    key_val = rel_model.data(rel_model.index(current_rel_row, rel_model.fieldIndex(relation.indexColumn())))
                    self.record.setValue(i, key_val)
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

        # Hierarchy: ColumnHeaderView -> QTableView -> QSplitter -> DataTableTab
        table_tab = self.parent().parent().parent()
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

        db = QSqlDatabase.database(db_conn_name)
        if table_name == "T_Resources" and db_conn_name == "year_db":
            self.model = QSqlRelationalTableModel(self, db)
            self.model.setTable(table_name)
            self.model.setRelation(1, QSqlRelation("T_Type_Resources", "idx", "type_resource"))
            self.model.setRelation(2, QSqlRelation("T_Seasons", "precure_season_name", "precure_season_name"))
        else:
            self.model = QSqlTableModel(self, db)
            self.model.setTable(table_name)

        self.model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.model.select()

        self.view = QTableView()
        self.view.setModel(self.model)
        if isinstance(self.model, QSqlRelationalTableModel):
            self.view.setItemDelegate(QSqlRelationalDelegate(self.view))
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.view.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed)

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
        self.log_viewer.moveCursor(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        if is_error:
            fmt.setForeground(QColor("red"))
            prefix = "[ERROR] "
        else:
            fmt.setForeground(QColor("white"))
            prefix = "[INFO] "

        self.log_viewer.setCurrentCharFormat(fmt)
        self.log_viewer.insertPlainText(f"{prefix}{message}\n")
        self.log_viewer.moveCursor(QTextCursor.MoveOperation.End)

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
        full_script = self.sql_console.toPlainText().strip()
        if not full_script:
            return

        db = QSqlDatabase.database(self.db_conn_name)
        # Split by semicolon but ignore inside quotes
        statements = re.split(r';(?=(?:[^\'"]*[\'"][^\'"]*[\'"])*[^\'"]*$)', full_script)

        success_count = 0
        error_occurred = False

        for statement in statements:
            stmt = statement.strip()
            if not stmt or stmt.upper() == "COMMIT":
                continue

            query = QSqlQuery(db)
            if query.exec(stmt):
                success_count += 1
                # Detect CREATE TABLE or DROP TABLE
                create_match = re.search(r"CREATE\s+TABLE\s+(\w+)", stmt, re.IGNORECASE)
                drop_match = re.search(r"DROP\s+TABLE\s+(\w+)", stmt, re.IGNORECASE)

                if create_match:
                    new_table = create_match.group(1)
                    self.table_name = new_table
                    self.model.setTable(new_table)
                    self.log(f"Vista vinculada a nueva tabla: {new_table}")
                elif drop_match:
                    dropped_table = drop_match.group(1)
                    if dropped_table.lower() == self.table_name.lower():
                        self.model.clear()
                        self.log(f"Tabla activa '{dropped_table}' eliminada.")
            else:
                err_msg = query.lastError().text()
                self.log(f"Error en sentencia: {stmt[:30]}... -> {err_msg}", is_error=True)
                error_occurred = True
                break

        if success_count > 0:
            self.log(f"Ejecutadas con éxito {success_count} sentencias.")
            self.model.select()
            if not error_occurred:
                self.sql_console.clear()

    def add_column(self, position):
        col_name, ok = QInputDialog.getText(self, "Nueva Columna", "Nombre de la columna:")
        if not ok or not col_name:
            return

        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)

        current_cols_count = self.model.record().count()
        if query.exec(f"ALTER TABLE \"{self.table_name}\" ADD COLUMN \"{col_name}\" TEXT"):
            self.log(f"Columna '{col_name}' añadida.")
            self.update_sql_file_add_column(col_name)
            self.model.select()
            if position < current_cols_count:
                QMessageBox.information(self, "Columna Añadida",
                    "Nota: SQLite solo permite añadir columnas al final.")
        else:
            self.log(f"Error añadiendo columna: {query.lastError().text()}", is_error=True)

    def rename_column(self, index):
        old_name = self.model.record().fieldName(index)
        new_name, ok = QInputDialog.getText(self, "Renombrar Columna", f"Nuevo nombre para '{old_name}':", text=old_name)
        if not ok or not new_name or new_name == old_name:
            return

        self.model.submitAll()

        # 1. Update SQL file first
        self.update_sql_file_rename_column(old_name, new_name)

        # 2. Apply to current connection
        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)
        sql = f'ALTER TABLE "{self.table_name}" RENAME COLUMN "{old_name}" TO "{new_name}"'

        if query.exec(sql):
            self.log(f"Columna '{old_name}' renombrada a '{new_name}' en base de datos actual.")

            # 3. Propagate if it's a yearly database
            if self.db_conn_name == "year_db":
                self.propagate_rename_column_to_all_years(old_name, new_name)

            self.model.setTable(self.table_name)
            self.model.select()
        else:
            self.log(f"Error renombrando columna: {query.lastError().text()}", is_error=True)

    def propagate_rename_column_to_all_years(self, old_name, new_name):
        from db_manager import init_yearly_dbs, get_yearly_db_path

        # Ensure all databases exist (will use updated yearly.sql if created now)
        init_yearly_dbs()

        current_db_path = os.path.abspath(QSqlDatabase.database(self.db_conn_name).databaseName())

        for year in range(2004, 2027):
            db_path = os.path.abspath(get_yearly_db_path(year))

            # Skip current if it's the same file
            if db_path == current_db_path:
                continue

            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    # Check if old column exists and new doesn't
                    cursor = conn.execute(f"PRAGMA table_info({self.table_name})")
                    cols = [row[1] for row in cursor.fetchall()]
                    if old_name in cols and new_name not in cols:
                        conn.execute(f'ALTER TABLE "{self.table_name}" RENAME COLUMN "{old_name}" TO "{new_name}"')
                        conn.commit()
                        self.log(f"Columna renombrada en base de datos del año {year}.")
                    conn.close()
                except Exception as e:
                    self.log(f"Error propagando cambio al año {year}: {e}", is_error=True)

    def delete_column(self, index):
        col_name = self.model.record().fieldName(index)
        if QMessageBox.question(self, "Confirmar", f"¿Seguro que quieres eliminar la columna '{col_name}'?") != QMessageBox.StandardButton.Yes:
            return

        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)
        if query.exec(f'ALTER TABLE "{self.table_name}" DROP COLUMN "{col_name}"'):
            self.log(f"Columna '{col_name}' eliminada.")
            self.update_sql_file_drop_column(col_name)
            self.model.setTable(self.table_name)
            self.model.select()
        else:
            self.log(f"Error eliminando columna: {query.lastError().text()}", is_error=True)

    def update_database(self, db_conn_name):
        self.db_conn_name = db_conn_name
        db = QSqlDatabase.database(db_conn_name)

        if self.table_name == "T_Resources" and db_conn_name == "year_db":
            self.model = QSqlRelationalTableModel(self, db)
            self.model.setTable(self.table_name)
            self.model.setRelation(1, QSqlRelation("T_Type_Resources", "idx", "type_resource"))
            self.model.setRelation(2, QSqlRelation("T_Seasons", "precure_season_name", "precure_season_name"))
        else:
            self.model = QSqlTableModel(self, db)
            self.model.setTable(self.table_name)

        self.model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.model.select()
        self.view.setModel(self.model)
        if isinstance(self.model, QSqlRelationalTableModel):
            self.view.setItemDelegate(QSqlRelationalDelegate(self.view))
        else:
            self.view.setItemDelegate(None)

    def set_console_visible(self, visible):
        self.console_area.setVisible(visible)

    def get_sql_filepath(self):
        filename = "global.sql" if self.db_conn_name == "global_db" else "yearly.sql"
        return os.path.join("sql", filename)

    def update_sql_file_add_column(self, col_name):
        path = self.get_sql_filepath()
        if not os.path.exists(path): return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Simple regex to find the CREATE TABLE block and add the column before );
        pattern = rf'(CREATE TABLE {self.table_name}\s*\([^;]*)\);'
        replacement = r'\1,    ' + col_name + ' TEXT\n);'
        new_content = re.sub(pattern, replacement, content, flags=re.IGNORECASE | re.DOTALL)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

    def update_sql_file_rename_column(self, old_name, new_name):
        path = self.get_sql_filepath()
        if not os.path.exists(path): return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Regex to find the table block and then replace the column name within it
        table_pattern = rf'(CREATE TABLE {self.table_name}\s*\()(.*?)(\);)'

        def replace_col(match):
            prefix = match.group(1)
            body = match.group(2)
            suffix = match.group(3)
            # Match word with optional quotes
            new_body = re.sub(rf'\b"{old_name}"\b|\b{old_name}\b', new_name, body)
            return prefix + new_body + suffix

        new_content = re.sub(table_pattern, replace_col, content, flags=re.IGNORECASE | re.DOTALL)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

    def update_sql_file_drop_column(self, col_name):
        path = self.get_sql_filepath()
        if not os.path.exists(path): return
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        table_pattern = rf'(CREATE TABLE {self.table_name}\s*\()(.*?)(\);)'

        def replace_col(match):
            prefix = match.group(1)
            body = match.group(2)
            suffix = match.group(3)
            # Remove line with column name and handle trailing/leading commas
            lines = body.split('\n')
            new_lines = []
            for line in lines:
                if not re.search(rf'\b"{col_name}"\b|\b{col_name}\b', line):
                    new_lines.append(line)

            # Re-clean commas
            body_text = '\n'.join(new_lines)
            body_text = re.sub(r',\s*\n\s*\)', '\n)', body_text) # remove comma before closing paren
            body_text = re.sub(r'\(\s*,', '(', body_text) # remove comma after opening paren

            return prefix + body_text + suffix

        new_content = re.sub(table_pattern, replace_col, content, flags=re.IGNORECASE | re.DOTALL)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_content)

    def set_auto_resize(self, enabled):
        header = self.view.horizontalHeader()
        if enabled:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            self.view.resizeColumnsToContents()

class PrecureManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Precure Media Manager - Core System")
        self.settings = QSettings("MyCompany", "PrecureMediaManager")

        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
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
        self.load_settings()

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("sidebar_visible", self.toggle_sidebar.isChecked())
        self.settings.setValue("console_visible", self.toggle_console.isChecked())
        self.settings.setValue("auto_resize", self.auto_resize_action.isChecked())

    def load_settings(self):
        sidebar_visible = self.settings.value("sidebar_visible", True, type=bool)
        self.toggle_sidebar.setChecked(sidebar_visible)
        self.dock.setVisible(sidebar_visible)

        console_visible = self.settings.value("console_visible", True, type=bool)
        self.toggle_console.setChecked(console_visible)
        self.toggle_sql_consoles()

        auto_resize = self.settings.value("auto_resize", True, type=bool)
        self.auto_resize_action.setChecked(auto_resize)
        self.set_auto_resize_columns(auto_resize)

    def set_auto_resize_columns(self, enabled):
        for tab in [self.registry_tab, self.resources_tab, self.catalog_tab,
                    self.opener_tab, self.type_res_tab, self.seasons_tab]:
            tab.set_auto_resize(enabled)

    def init_menu_bar(self):
        menubar = self.menuBar()

        # Archivo
        file_menu = menubar.addMenu("Archivo")

        save_action = QAction("Guardar", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self.save_current_tab)
        file_menu.addAction(save_action)

        exit_action = QAction("Salir", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Edición
        edit_menu = menubar.addMenu("Edición")
        add_row_action = QAction("Añadir fila", self)
        add_row_action.triggered.connect(self.on_add_row_requested)
        edit_menu.addAction(add_row_action)

        scan_masters_action = QAction("Escanear carpetas maestras", self)
        scan_masters_action.triggered.connect(self.scan_master_folders)
        edit_menu.addAction(scan_masters_action)

        migrate_resources_action = QAction("Migrar Recursos de años", self)
        migrate_resources_action.triggered.connect(self.migrate_resources_from_excel)
        edit_menu.addAction(migrate_resources_action)

        # Vista
        view_menu = menubar.addMenu("Vista")
        panels_submenu = view_menu.addMenu("Mostrar Paneles")

        self.toggle_sidebar = QAction("Años", self, checkable=True)
        self.toggle_sidebar.setChecked(True)
        self.toggle_sidebar.triggered.connect(lambda: self.dock.setVisible(self.toggle_sidebar.isChecked()))
        panels_submenu.addAction(self.toggle_sidebar)

        self.toggle_console = QAction("Consola SQL", self, checkable=True)
        self.toggle_console.setChecked(True)
        self.toggle_console.triggered.connect(self.toggle_sql_consoles)
        panels_submenu.addAction(self.toggle_console)

        self.auto_resize_action = QAction("Auto-ajustar ancho de columnas", self, checkable=True)
        self.auto_resize_action.setChecked(True)
        self.auto_resize_action.triggered.connect(self.set_auto_resize_columns)
        view_menu.addAction(self.auto_resize_action)

        # Ayuda
        help_menu = menubar.addMenu("Ayuda")
        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(lambda: QMessageBox.information(self, "Ayuda", "Precure Media Manager v1.0"))
        help_menu.addAction(about_action)

    def save_current_tab(self):
        current_widget = self.tabs.currentWidget()
        if current_widget == self.global_tab_container:
            current_tab = self.global_subtabs.currentWidget()
        else:
            current_tab = current_widget

        if isinstance(current_tab, DataTableTab):
            if current_tab.model.submitAll():
                QMessageBox.information(self, "Guardar", "Cambios guardados correctamente.")
            else:
                QMessageBox.critical(self, "Error", f"No se pudo guardar: {current_tab.model.lastError().text()}")

    def on_add_row_requested(self):
        # Get active tab (handle nested tabs too)
        current_widget = self.tabs.currentWidget()
        if current_widget == self.global_tab_container:
            current_tab = self.global_subtabs.currentWidget()
        else:
            current_tab = current_widget

        if isinstance(current_tab, DataTableTab):
            current_tab.add_record()

    def migrate_resources_from_excel(self):
        if not os.path.exists(BASE_DIR_PATH):
            QMessageBox.critical(self, "Error", f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return

        # Prepare progress dialog
        years = list(range(2004, 2027))
        progress = QProgressDialog("Migrando recursos...", "Cancelar", 0, len(years), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        total_migrated = 0

        # Load Global FK mappings
        type_res_map = {} # text -> id
        seasons_map = {} # text -> text (primary key is name)

        db_global = QSqlDatabase.database("global_db")
        q = QSqlQuery(db_global)
        q.exec("SELECT idx, type_resource FROM T_Type_Resources")
        while q.next():
            type_res_map[q.value(1)] = q.value(0)

        q.exec("SELECT precure_season_name FROM T_Seasons")
        while q.next():
            seasons_map[q.value(0)] = q.value(0)

        for i, year in enumerate(years):
            progress.setValue(i)
            progress.setLabelText(f"Procesando año {year}...")
            QApplication.processEvents()

            if progress.wasCanceled():
                break

            px = year - 2003
            px_str = f"{px:02d}"
            excel_path = os.path.join(BASE_DIR_PATH, str(year), f"{px_str}. identity_propeties", f"{px_str}. le_etude.overwrite.xlsx")

            if not os.path.exists(excel_path):
                continue

            try:
                wb = openpyxl.load_workbook(excel_path, data_only=True)
                if "material_list" not in wb.sheetnames:
                    continue

                sheet = wb["material_list"]

                db_year_conn_name = f"migration_db_{year}"
                db_year_path = get_yearly_db_path(year)

                db_year = QSqlDatabase.addDatabase("QSQLITE", db_year_conn_name)
                db_year.setDatabaseName(db_year_path)
                if not db_year.open():
                    print(f"Could not open yearly DB for {year}")
                    continue

                # Get existing titles to handle duplicates
                existing_titles = set()
                q_titles = QSqlQuery(db_year)
                q_titles.exec("SELECT title_material FROM T_Resources")
                while q_titles.next():
                    existing_titles.add(q_titles.value(0))

                query = QSqlQuery(db_year)

                # Start from row 4
                for row_idx in range(4, sheet.max_row + 1):
                    # Columns according to mapping:
                    # E: Type Material, F: Season Name, G: Ep Num, H: Ep Sp Num, I: Title Material,
                    # J: Released (UTC+09), K: Released Soundtrack, L: Released Spinoff, M: Duration File, N: DateTime Download
                    # O: Path of File

                    type_mat_text = sheet.cell(row=row_idx, column=5).value
                    season_name_text = sheet.cell(row=row_idx, column=6).value
                    ep_num = sheet.cell(row=row_idx, column=7).value
                    ep_sp_num = sheet.cell(row=row_idx, column=8).value
                    title_material = sheet.cell(row=row_idx, column=9).value
                    released_09 = sheet.cell(row=row_idx, column=10).value
                    released_sdtr = sheet.cell(row=row_idx, column=11).value
                    released_spin = sheet.cell(row=row_idx, column=12).value
                    duration = sheet.cell(row=row_idx, column=13).value
                    dt_download = sheet.cell(row=row_idx, column=14).value
                    path_file = sheet.cell(row=row_idx, column=15).value

                    # Check for empty rows (Title is mandatory)
                    if not title_material:
                        continue

                    # Handle duplicates
                    base_title = str(title_material)
                    final_title = base_title
                    counter = 2
                    while final_title in existing_titles:
                        final_title = f"{base_title} ({counter})"
                        counter += 1

                    existing_titles.add(final_title)

                    # FK Resolving
                    type_mat_id = type_res_map.get(type_mat_text)
                    season_name_fk = seasons_map.get(season_name_text)

                    query.prepare("""
                        INSERT INTO T_Resources (
                            title_material, type_material, precure_season_name, ep_num, ep_sp_num,
                            released_utc_09, released_soundtrack_utc_09, released_spinoff_utc_09,
                            duration_file, datetime_download, relative_path_of_file,
                            relative_path_of_soundtracks, relative_path_of_lyrics
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """)
                    query.addBindValue(final_title)
                    query.addBindValue(type_mat_id)
                    query.addBindValue(season_name_fk)
                    query.addBindValue(ep_num)
                    query.addBindValue(ep_sp_num)
                    query.addBindValue(str(released_09) if released_09 else None)
                    query.addBindValue(str(released_sdtr) if released_sdtr else None)
                    query.addBindValue(str(released_spin) if released_spin else None)
                    query.addBindValue(str(duration) if duration else None)
                    query.addBindValue(str(dt_download) if dt_download else None)
                    query.addBindValue(str(path_file) if path_file else None)
                    query.addBindValue(None) # Path of Soundtracks (Empty)
                    query.addBindValue(None) # Path of Lyrics (Empty)

                    if query.exec():
                        total_migrated += 1
                    else:
                        print(f"Error migrating row {row_idx} in year {year}: {query.lastError().text()}")

                db_year.close()
                QSqlDatabase.removeDatabase(db_year_conn_name)

            except Exception as e:
                print(f"Error processing {excel_path}: {e}")

        progress.setValue(len(years))
        self.resources_tab.model.select()
        if not progress.wasCanceled():
            QMessageBox.information(self, "Migración", f"Se migraron {total_migrated} recursos en total.")

    def scan_master_folders(self):
        if not os.path.exists(BASE_DIR_PATH):
            QMessageBox.critical(self, "Error", f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return

        db = QSqlDatabase.database("global_db")
        query = QSqlQuery(db)
        updated_count = 0

        for year in range(2004, 2027):
            year_path = os.path.join(BASE_DIR_PATH, str(year))
            if os.path.exists(year_path):
                found_folder = None
                try:
                    for item in os.listdir(year_path):
                        if "___" in item and os.path.isdir(os.path.join(year_path, item)):
                            found_folder = item
                            break
                except Exception as e:
                    print(f"Error escaneando {year_path}: {e}")
                    continue

                if found_folder:
                    # Update T_Seasons where year = year
                    q = QSqlQuery(db)
                    q.prepare("UPDATE T_Seasons SET path_master = ? WHERE year = ?")
                    q.addBindValue(found_folder)
                    q.addBindValue(year)
                    if q.exec():
                        updated_count += 1
                    else:
                        print(f"Error actualizando año {year}: {q.lastError().text()}")

        self.seasons_tab.model.select()
        QMessageBox.information(self, "Escaneo", f"Se actualizaron {updated_count} filas en Temporadas.")

    def toggle_sql_consoles(self):
        is_visible = self.toggle_console.isChecked()
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
            if db.open():
                # Attach global db on initial load
                query = QSqlQuery(db)
                query.exec(f"ATTACH DATABASE '{GLOBAL_DB_PATH}' AS global_db")

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
            # Attach global db
            query = QSqlQuery(db)
            query.exec(f"ATTACH DATABASE '{GLOBAL_DB_PATH}' AS global_db")

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
