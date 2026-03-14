import os
import re
import csv
import sqlite3
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QTableView, 
                             QHeaderView, QPushButton, QLabel, QPlainTextEdit,
                             QSplitter, QMessageBox, QFileDialog, QInputDialog,
                             QApplication, QAbstractItemView, QMenu, QProgressDialog,
                             QStyle, QStyleOptionButton, QStyleOptionHeader)
from PyQt6.QtCore import Qt, QRect, QPoint
from PyQt6.QtGui import QTextCharFormat, QColor, QTextCursor, QPainter, QPalette
from datetime import datetime
from PyQt6.QtSql import (QSqlTableModel, QSqlRelationalTableModel, QSqlRelation, 
                         QSqlRelationalDelegate, QSqlQuery, QSqlDatabase)

from forms import DatabaseForm
from filter_widget import FilterMenu

class ColumnHeaderView(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionsClickable(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.filter_rects = {}

    def sectionSizeFromContents(self, logicalIndex):
        size = super().sectionSizeFromContents(logicalIndex)
        size.setWidth(size.width() + 20) # Space for filter button
        return size

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        
        # Draw background only
        opt = QStyleOptionHeader()
        opt.rect = rect
        opt.section = logicalIndex
        opt.state = QStyle.StateFlag.State_Enabled
        self.style().drawControl(QStyle.ControlElement.CE_HeaderSection, opt, painter, self)
        
        # Draw text in restricted area
        text = self.model().headerData(logicalIndex, self.orientation(), Qt.ItemDataRole.DisplayRole)
        margin = 4
        btn_size = 14
        text_rect = QRect(rect.left() + margin, rect.top(), rect.width() - btn_size - margin * 3, rect.height())
        self.style().drawItemText(painter, text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.palette(), True, str(text))
        
        # Draw filter button
        btn_rect = QRect(rect.right() - btn_size - margin, rect.center().y() - btn_size//2, btn_size, btn_size)
        self.filter_rects[logicalIndex] = btn_rect
        
        # Determine button colors based on light/dark mode (heuristic)
        is_dark = self.palette().window().color().lightness() < 128
        bg_color = QColor(255, 255, 255, 60) if is_dark else QColor(0, 0, 0, 40)
        text_color = Qt.GlobalColor.white if is_dark else Qt.GlobalColor.black

        painter.setBrush(bg_color)
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawRoundedRect(btn_rect, 2, 2)
        
        painter.setPen(text_color)
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, "▼")
        
        painter.restore()

    def mousePressEvent(self, event):
        logical_index = self.logicalIndexAt(event.pos())
        if logical_index in self.filter_rects and self.filter_rects[logical_index].contains(event.pos()):
            # Filter button clicked
            table_tab = self.parent().parent().parent()
            table_tab.show_filter_menu(logical_index, self.mapToGlobal(event.pos()))
            return
        super().mousePressEvent(event)

    def show_context_menu(self, pos):
        logical_index = self.logicalIndexAt(pos)
        if logical_index < 0:
            return
        
        menu = QMenu(self)
        add_left = menu.addAction("Agregar columna (izquierda)")
        add_right = menu.addAction("Agregar columna (derecha)")
        rename_col = menu.addAction("Renombrar columna")
        delete_col = menu.addAction("Eliminar columna")
        menu.addSeparator()
        copy_col_name = menu.addAction("Copiar nombre de esta columna")
        copy_col_data = menu.addAction("Copiar datos de esta columna")
        
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
        elif action == copy_col_name:
            table_tab.copy_column_name(logical_index)
        elif action == copy_col_data:
            table_tab.copy_column_data(logical_index)

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
        
        self.active_filters = {} # col_index -> list of values
        self.current_sort = (None, None) # (col_index, order)

    def show_filter_menu(self, col_index, pos):
        is_relational = isinstance(self.model, QSqlRelationalTableModel)
        relation = self.model.relation(col_index) if is_relational else QSqlRelation()
        
        all_values = []
        db = self.model.database()
        query = QSqlQuery(db)
        
        # Get the underlying field name from the DB schema to avoid model aliases/display names
        actual_field_name = db.record(self.table_name).fieldName(col_index)
        
        success = False
        if relation.isValid() and actual_field_name:
            rel_table = relation.tableName()
            rel_index = relation.indexColumn()
            rel_display = relation.displayColumn()
            
            sql = f"""
                SELECT DISTINCT r."{rel_display}" 
                FROM "{self.table_name}" t
                LEFT JOIN "{rel_table}" r ON t."{actual_field_name}" = r."{rel_index}"
            """
            if query.exec(sql):
                while query.next():
                    all_values.append(query.value(0))
                success = True
        elif actual_field_name:
            sql = f'SELECT DISTINCT "{actual_field_name}" FROM "{self.table_name}"'
            if query.exec(sql):
                while query.next():
                    all_values.append(query.value(0))
                success = True
        
        # Fallback to model data if query failed or returned no values
        if not success or not all_values:
            unique_vals = set()
            for r in range(self.model.rowCount()):
                unique_vals.add(self.model.data(self.model.index(r, col_index)))
            all_values = list(unique_vals)
            
        current_selection = self.active_filters.get(col_index)
        
        self.filter_menu = FilterMenu(all_values, current_selection, self)
        self.filter_menu.filter_requested.connect(lambda selected: self.apply_filter(col_index, selected))
        self.filter_menu.sort_requested.connect(lambda order: self.apply_sort(col_index, order))
        self.filter_menu.show_at(pos)

    def apply_filter(self, col_index, selected_values):
        self.active_filters[col_index] = selected_values
        
        filter_parts = []
        for col, values in self.active_filters.items():
            field_name = self.model.record().fieldName(col)
            # Escape single quotes and handle NULLs
            escaped_vals = []
            has_null = False
            for v in values:
                if v is None: 
                    has_null = True
                else:
                    escaped_vals.append(f"'{str(v).replace('\'', '\'\'')}'")
            
            if not escaped_vals and not has_null:
                filter_parts.append("1=0") # No values selected
            else:
                conditions = []
                if escaped_vals:
                    conditions.append(f'"{field_name}" IN ({", ".join(escaped_vals)})')
                if has_null:
                    conditions.append(f'"{field_name}" IS NULL OR "{field_name}" = ""')
                filter_parts.append(f"({' OR '.join(conditions)})")
        
        filter_str = " AND ".join(filter_parts)
        self.model.setFilter(filter_str)
        self.model.select()

    def apply_sort(self, col_index, order):
        self.model.sort(col_index, order)
        self.model.select()

    def export_to_csv(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Exportar tabla a CSV", f"{self.table_name}.csv", "CSV Files (*.csv)")
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                
                # Headers
                headers = []
                for i in range(self.model.columnCount()):
                    headers.append(self.model.headerData(i, Qt.Orientation.Horizontal))
                writer.writerow(headers)
                
                # Data
                for r in range(self.model.rowCount()):
                    row_data = []
                    for c in range(self.model.columnCount()):
                        row_data.append(self.model.data(self.model.index(r, c)))
                    writer.writerow(row_data)
                    
            QMessageBox.information(self, "Exportación", "Tabla exportada con éxito.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo exportar: {e}")

    def import_from_csv(self):
        msg = ("Asegúrate de que el CSV tenga el mismo número de columnas, "
               "los mismos nombres y tipos de datos que la tabla actual.\n\n"
               "Toda la información actual de la tabla será reemplazada.\n"
               "¿Deseas continuar?")
        if QMessageBox.warning(self, "Importar CSV", msg, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes:
            return
            
        file_path, _ = QFileDialog.getOpenFileName(self, "Importar tabla desde CSV", "", "CSV Files (*.csv)")
        if not file_path:
            return
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                headers = next(reader)
                
                # Validate headers
                model_headers = [self.model.headerData(i, Qt.Orientation.Horizontal) for i in range(self.model.columnCount())]
                if headers != model_headers:
                    QMessageBox.critical(self, "Error", f"Las columnas no coinciden.\nCSV: {headers}\nTabla: {model_headers}")
                    return
                
                # Clear table efficiently
                db = QSqlDatabase.database(self.db_conn_name)
                query = QSqlQuery(db)
                if not query.exec(f"DELETE FROM {self.table_name}"):
                    QMessageBox.critical(self, "Error", f"No se pudo limpiar la tabla: {query.lastError().text()}")
                    return
                
                # Insert data
                for row_data in reader:
                    record = self.model.record()
                    for i, val in enumerate(row_data):
                        record.setValue(i, val)
                    self.model.insertRecord(-1, record)
                
                if self.model.submitAll():
                    self.model.select()
                    QMessageBox.information(self, "Importación", "Datos importados con éxito.")
                else:
                    QMessageBox.critical(self, "Error", f"Error al guardar los datos: {self.model.lastError().text()}")
                    self.model.select()
                    
        except Exception as e:
            QMessageBox.critical(self, "Error", f"No se pudo importar: {e}")

    def copy_column_data(self, index):
        data_list = []
        for r in range(self.model.rowCount()):
            val = self.model.data(self.model.index(r, index))
            data_list.append(str(val) if val is not None else "")
        
        clipboard = QApplication.clipboard()
        clipboard.setText("\n".join(data_list))
        self.log(f"Datos de columna '{self.model.headerData(index, Qt.Orientation.Horizontal)}' copiados al portapapeles.")

    def copy_column_name(self, index):
        col_name = self.model.headerData(index, Qt.Orientation.Horizontal)
        clipboard = QApplication.clipboard()
        clipboard.setText(col_name)
        self.log(f"Nombre de columna '{col_name}' copiado al portapapeles.")

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
        
        self.model.submitAll()
        self.update_sql_file_add_column(col_name)
        
        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)
        sql = f'ALTER TABLE "{self.table_name}" ADD COLUMN "{col_name}" TEXT'
        
        current_cols_count = self.model.record().count()
        if query.exec(sql):
            self.log(f"Columna '{col_name}' añadida en base de datos actual.")
            if self.db_conn_name == "year_db":
                self.propagate_schema_change(sql, f"Columna '{col_name}' añadida")
            
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
        self.update_sql_file_rename_column(old_name, new_name)
        
        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)
        sql = f'ALTER TABLE "{self.table_name}" RENAME COLUMN "{old_name}" TO "{new_name}"'
        
        if query.exec(sql):
            self.log(f"Columna '{old_name}' renombrada a '{new_name}' en base de datos actual.")
            if self.db_conn_name == "year_db":
                # For rename, we need custom logic to check existence, but we can pass the SQL
                self.propagate_schema_change(sql, f"Columna renombrada a '{new_name}'")
                
            self.model.setTable(self.table_name)
            self.model.select()
        else:
            self.log(f"Error renombrando columna: {query.lastError().text()}", is_error=True)

    def delete_column(self, index):
        col_name = self.model.record().fieldName(index)
        if QMessageBox.question(self, "Confirmar", f"¿Seguro que quieres eliminar la columna '{col_name}'?") != QMessageBox.StandardButton.Yes:
            return
        
        self.model.submitAll()
        
        # Mandatory Backup Logic if column has data
        from db_manager import get_yearly_db_path
        
        has_data = False
        db_paths_to_check = []
        if self.db_conn_name == "year_db":
            for y in range(2004, datetime.now().year + 1):
                p = get_yearly_db_path(y)
                if os.path.exists(p):
                    db_paths_to_check.append((y, p))
        else:
            db_paths_to_check.append((None, QSqlDatabase.database(self.db_conn_name).databaseName()))

        # Check for data
        for _, p in db_paths_to_check:
            if self.column_has_data(p, self.table_name, col_name):
                has_data = True
                break
        
        if has_data:
            ret = QMessageBox.warning(self, "Columna con Datos", 
                f"La columna '{col_name}' contiene datos. Se realizará una exportación a CSV de seguridad antes de borrar.\n¿Deseas continuar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if ret == QMessageBox.StandardButton.No:
                return
            
            # Perform export
            backup_dir = "backups"
            if not os.path.exists(backup_dir):
                os.makedirs(backup_dir)
            
            progress = QProgressDialog("Exportando backups...", "Cancelar", 0, len(db_paths_to_check), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()
            
            for i, (year, p) in enumerate(db_paths_to_check):
                progress.setValue(i)
                label = f"Backup año {year}..." if year else "Backup base de datos..."
                progress.setLabelText(label)
                QApplication.processEvents()
                if progress.wasCanceled(): break
                
                suffix = f"_{year}" if year else ""
                csv_path = os.path.join(backup_dir, f"{self.table_name}{suffix}_pre_delete_{col_name}.csv")
                self.export_table_to_csv_static(p, self.table_name, csv_path)
            
            progress.setValue(len(db_paths_to_check))
            QMessageBox.information(self, "Backup Completado", f"Se han guardado copias de seguridad en la carpeta '{backup_dir}'.")

        # Proceed with deletion
        self.update_sql_file_drop_column(col_name)
        
        db = QSqlDatabase.database(self.db_conn_name)
        query = QSqlQuery(db)
        sql = f'ALTER TABLE "{self.table_name}" DROP COLUMN "{col_name}"'
        
        if query.exec(sql):
            self.log(f"Columna '{col_name}' eliminada en base de datos actual.")
            if self.db_conn_name == "year_db":
                self.propagate_schema_change(sql, f"Columna '{col_name}' eliminada")
                
            self.model.setTable(self.table_name)
            self.model.select()
        else:
            self.log(f"Error eliminando columna: {query.lastError().text()}", is_error=True)

    def column_has_data(self, db_path, table_name, col_name):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(f"PRAGMA table_info({table_name})")
            cols = [row[1] for row in cursor.fetchall()]
            if col_name not in cols:
                conn.close()
                return False
                
            cursor = conn.execute(f'SELECT 1 FROM "{table_name}" WHERE "{col_name}" IS NOT NULL AND "{col_name}" != "" LIMIT 1')
            row = cursor.fetchone()
            conn.close()
            return row is not None
        except:
            return False

    def export_table_to_csv_static(self, db_path, table_name, csv_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.execute(f'SELECT * FROM "{table_name}"')
            columns = [description[0] for description in cursor.description]
            
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(cursor.fetchall())
            conn.close()
        except Exception as e:
            self.log(f"Error exportando CSV {csv_path}: {e}", is_error=True)

    def propagate_schema_change(self, sql_command, success_msg_prefix):
        from db_manager import init_yearly_dbs, get_yearly_db_path
        
        # Ensure all databases exist
        init_yearly_dbs()
        
        current_db_path = os.path.abspath(QSqlDatabase.database(self.db_conn_name).databaseName())
        years = list(range(2004, datetime.now().year + 1))
        
        progress = QProgressDialog("Propagando cambios de esquema...", "Cancelar", 0, len(years), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()
        
        for i, year in enumerate(years):
            progress.setValue(i)
            progress.setLabelText(f"Procesando año {year}...")
            QApplication.processEvents()
            
            if progress.wasCanceled():
                self.log("Propagación cancelada por el usuario.", is_error=True)
                break
                
            db_path = os.path.abspath(get_yearly_db_path(year))
            if db_path == current_db_path:
                continue
                
            if os.path.exists(db_path):
                try:
                    conn = sqlite3.connect(db_path)
                    # Check if table exists
                    cursor = conn.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.table_name}'")
                    if cursor.fetchone():
                        # Additional safety for renames: check if column exists
                        if "RENAME COLUMN" in sql_command.upper():
                            # Command format: ALTER TABLE "table" RENAME COLUMN "old" TO "new"
                            parts = sql_command.split('"')
                            if len(parts) >= 6:
                                old_col = parts[3]
                                new_col = parts[5]
                                info = conn.execute(f"PRAGMA table_info({self.table_name})").fetchall()
                                cols = [r[1] for r in info]
                                # If old column doesn't exist or new one already exists, skip
                                if old_col not in cols or new_col in cols:
                                    conn.close()
                                    continue
                        
                        conn.execute(sql_command)
                        conn.commit()
                        self.log(f"{success_msg_prefix} en base de datos del año {year}.")
                    conn.close()
                except Exception as e:
                    self.log(f"Error en año {year}: {e}", is_error=True)
        
        progress.setValue(len(years))

    def update_database(self, db_conn_name):
        self.active_filters = {}
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
        self.model.setFilter("")
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
