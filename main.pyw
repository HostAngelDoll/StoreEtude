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
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction, QCursor, QTextCharFormat, QColor, QTextCursor
from PyQt6.QtSql import QSqlDatabase, QSqlTableModel, QSqlRecord, QSqlQuery

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

        self.model = QSqlTableModel(self, QSqlDatabase.database(db_conn_name))
        self.model.setTable(table_name)
        self.model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
        self.model.select()

        self.view = QTableView()
        self.view.setModel(self.model)
        self.view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)

        # Custom Header
        self.header = ColumnHeaderView(Qt.Orientation.Horizontal, self.view)
        self.view.setHorizontalHeader(self.header)
        self.header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

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

    def set_auto_resize_columns(self, enabled):
        if enabled:
            self.header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        else:
            self.header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            # Default width based on header text if interactive
            self.view.resizeColumnsToContents()

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

        # Edición
        edit_menu = menubar.addMenu("Edición")
        add_row_action = QAction("Añadir fila", self)
        add_row_action.triggered.connect(self.on_add_row_requested)
        edit_menu.addAction(add_row_action)

        scan_masters_action = QAction("Escanear carpetas maestras", self)
        scan_masters_action.triggered.connect(self.scan_master_folders)
        edit_menu.addAction(scan_masters_action)

        migrate_excel_action = QAction("Migrar Recursos de años", self)
        migrate_excel_action.triggered.connect(self.migrate_resources_from_excel)
        edit_menu.addAction(migrate_excel_action)

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

        auto_resize_action = QAction("Auto-ajustar ancho de columnas", self, checkable=True)
        auto_resize_action.setChecked(True)
        auto_resize_action.triggered.connect(self.toggle_auto_resize_columns)
        view_menu.addAction(auto_resize_action)

        # Ayuda
        help_menu = menubar.addMenu("Ayuda")
        about_action = QAction("Acerca de", self)
        about_action.triggered.connect(lambda: QMessageBox.information(self, "Ayuda", "Precure Media Manager v1.0"))
        help_menu.addAction(about_action)

    def toggle_auto_resize_columns(self):
        enabled = self.sender().isChecked()
        for tab in [self.registry_tab, self.resources_tab, self.catalog_tab,
                    self.opener_tab, self.type_res_tab, self.seasons_tab]:
            tab.set_auto_resize_columns(enabled)

    def on_add_row_requested(self):
        current_widget = self.tabs.currentWidget()
        if current_widget == self.global_tab_container:
            current_tab = self.global_subtabs.currentWidget()
        else:
            current_tab = current_widget

        if isinstance(current_tab, DataTableTab):
            current_tab.add_record()

    def scan_master_folders(self):
        if not os.path.exists(BASE_DIR_PATH):
            QMessageBox.critical(self, "Error", f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return

        db = QSqlDatabase.database("global_db")
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
                except:
                    continue

                if found_folder:
                    q = QSqlQuery(db)
                    q.prepare("UPDATE T_Seasons SET path_master = ? WHERE year = ?")
                    q.addBindValue(found_folder)
                    q.addBindValue(year)
                    if q.exec():
                        updated_count += 1

        self.seasons_tab.model.select()
        QMessageBox.information(self, "Escaneo", f"Se actualizaron {updated_count} filas en Temporadas.")

    def migrate_resources_from_excel(self):
        if not os.path.exists(BASE_DIR_PATH):
            QMessageBox.critical(self, "Error", f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return

        total_migrated = 0

        for year in range(2004, 2027):
            px = year - 2003
            px_str = f"{px:02d}"
            excel_path = os.path.join(BASE_DIR_PATH, str(year), f"{px_str}. identity_propeties", f"{px_str}. le_etude.overwrite.xlsx")

            if not os.path.exists(excel_path):
                continue

            db_path = get_yearly_db_path(year)
            conn_name = f"migration_{year}"
            db = QSqlDatabase.addDatabase("QSQLITE", conn_name)
            db.setDatabaseName(db_path)

            if not db.open():
                print(f"No se pudo abrir DB para migración {year}")
                continue

            try:
                wb = openpyxl.load_workbook(excel_path, data_only=True)
                if "material_list" not in wb.sheetnames:
                    continue

                sheet = wb["material_list"]
                # Columns mapping (starting from index 1, so E is 5, N is 14, O is 15)
                # Excel:
                # E (5): Type Material [FK]
                # F (6): Season Name [FK]
                # G (7): Ep Num
                # H (8): Ep Sp Num
                # I (9): ID Code Material [A] (Empty for now)
                # J (10): Title Material
                # K (11): Released (UTC+09)
                # L (12): Released Soundtrack
                # M (13): Released Spinoff
                # N (14): Duration File
                # O (15): DateTime Download

                rows_migrated = 0
                for row_idx in range(4, sheet.max_row + 1):
                    # Basic empty row check: if Title (J) and Type (E) are empty
                    if not sheet.cell(row=row_idx, column=10).value and not sheet.cell(row=row_idx, column=5).value:
                        continue

                    query = QSqlQuery(db)
                    query.prepare("""
                        INSERT INTO T_Resources (
                            type_material, precure_season_name, ep_num, ep_sp_num,
                            id_code_material, title_material, released_utc_09,
                            released_soundtrack_utc_09, released_spinoff_utc_09,
                            duration_file, datetime_download
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """)

                    query.addBindValue(sheet.cell(row=row_idx, column=5).value) # Type
                    query.addBindValue(sheet.cell(row=row_idx, column=6).value) # Season
                    query.addBindValue(sheet.cell(row=row_idx, column=7).value) # Ep Num
                    query.addBindValue(sheet.cell(row=row_idx, column=8).value) # Ep Sp Num
                    query.addBindValue(None) # ID Code Material (Empty [A])
                    query.addBindValue(sheet.cell(row=row_idx, column=10).value) # Title
                    query.addBindValue(str(sheet.cell(row=row_idx, column=11).value or "")) # Released
                    query.addBindValue(str(sheet.cell(row=row_idx, column=12).value or ""))
                    query.addBindValue(str(sheet.cell(row=row_idx, column=13).value or ""))
                    query.addBindValue(str(sheet.cell(row=row_idx, column=14).value or "")) # Duration
                    query.addBindValue(str(sheet.cell(row=row_idx, column=15).value or "")) # Download

                    if query.exec():
                        rows_migrated += 1

                total_migrated += rows_migrated
                print(f"Migrados {rows_migrated} recursos para el año {year}")

            except Exception as e:
                print(f"Error migrando año {year}: {e}")
            finally:
                db.close()
                QSqlDatabase.removeDatabase(conn_name)

        # Refresh currently visible models
        self.resources_tab.model.select()
        QMessageBox.information(self, "Migración", f"Migración completada. Total recursos migrados: {total_migrated}")

    def toggle_sql_consoles(self):
        is_visible = self.sender().isChecked()
        for tab in [self.registry_tab, self.resources_tab, self.catalog_tab,
                    self.opener_tab, self.type_res_tab, self.seasons_tab]:
            tab.set_console_visible(is_visible)

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
