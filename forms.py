from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QSpinBox, 
                             QCheckBox, QDialogButtonBox, QMessageBox, QComboBox,
                             QVBoxLayout, QHBoxLayout, QRadioButton, QButtonGroup,
                             QLabel, QWidget, QTableView, QStyledItemDelegate,
                             QApplication, QFileDialog, QGroupBox, QPushButton,
                             QHeaderView, QTreeView)
from PyQt6.QtSql import QSqlRelationalTableModel, QSqlRelation, QSqlTableModel, QSqlQuery, QSqlDatabase
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QIcon
from datetime import datetime
import os
from config_manager import ConfigManager

class DatabaseForm(QDialog):
    def __init__(self, model, row=-1, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(r"img\icon.ico"))
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
            
            # Special case for T_Registry which no longer uses QSqlRelationalTableModel
            if not relation.isValid() and model.tableName() == "T_Registry":
                if field_name == "title_material":
                    relation = QSqlRelation("T_Resources", "title_material", "title_material")
                elif field_name == "type_repeat":
                    relation = QSqlRelation("T_Type_Catalog_Reg", "type", "type")
                elif field_name == "type_listen":
                    relation = QSqlRelation("T_Type_Catalog_Reg", "type", "type")
                elif field_name == "model_writer":
                    relation = QSqlRelation("T_Type_Catalog_Reg", "type", "type")

            if relation.isValid():
                widget = QComboBox()
                if is_relational and model.relation(i).isValid():
                    rel_model = model.relationModel(i)
                else:
                    # Manually create and filter the relation model
                    rel_model = QSqlTableModel(self, model.database())
                    rel_model.setTable(relation.tableName())
                    if model.tableName() == "T_Registry":
                        if field_name == "type_repeat": rel_model.setFilter("category = 'repeat'")
                        elif field_name == "type_listen": rel_model.setFilter("category = 'listen'")
                        elif field_name == "model_writer": rel_model.setFilter("category = 'write'")
                
                # Ensure the relational model is populated
                rel_model.select()
                while rel_model.canFetchMore():
                    rel_model.fetchMore()
                
                # Add a blank entry to the combo box by using a proxy or manual addition
                # Since we want to use the model, we can add the item manually and handle indices
                widget.addItem("", None) # Blank item at index 0
                for rel_row in range(rel_model.rowCount()):
                    display_val = rel_model.data(rel_model.index(rel_row, rel_model.fieldIndex(relation.displayColumn())))
                    key_val = rel_model.data(rel_model.index(rel_row, rel_model.fieldIndex(relation.indexColumn())))
                    widget.addItem(str(display_val), key_val)
                
                if row >= 0:
                    current_val = self.record.value(i)
                    idx = widget.findData(current_val)
                    if idx >= 0:
                        widget.setCurrentIndex(idx)
                    else:
                        widget.setCurrentIndex(0)
                else:
                    widget.setCurrentIndex(0)
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
                    key_val = widget.currentData()
                    self.record.setValue(i, key_val if key_val != "" else None)
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

class YearRangeDialog(QDialog):
    def __init__(self, current_year, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(r"img\icon.ico"))
        self.setWindowTitle("Escanear y vincular archivos")
        self.setMinimumWidth(300)
        self.layout = QVBoxLayout(self)
        
        current_system_year = datetime.now().year
        
        self.radio_current = QRadioButton(f"Solo el año actual ({current_year})")
        self.radio_range = QRadioButton("Rango de años")
        self.radio_range.setChecked(True)
        
        self.bg = QButtonGroup(self)
        self.bg.addButton(self.radio_current)
        self.bg.addButton(self.radio_range)
        
        self.layout.addWidget(self.radio_current)
        self.layout.addWidget(self.radio_range)
        
        range_layout = QHBoxLayout()
        self.start_year = QSpinBox()
        self.start_year.setRange(2004, current_system_year)
        self.start_year.setValue(2004)
        self.end_year = QSpinBox()
        self.end_year.setRange(2004, current_system_year)
        self.end_year.setValue(int(current_year))
        
        range_layout.addWidget(QLabel("Desde:"))
        range_layout.addWidget(self.start_year)
        range_layout.addWidget(QLabel("Hasta:"))
        range_layout.addWidget(self.end_year)
        
        self.range_widget = QWidget()
        self.range_widget.setLayout(range_layout)
        self.layout.addWidget(self.range_widget)
        
        self.radio_current.toggled.connect(lambda checked: self.range_widget.setDisabled(checked))

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_years(self, current_year):
        if self.radio_current.isChecked():
            return [int(current_year)]
        else:
            return list(range(self.start_year.value(), self.end_year.value() + 1))

class ReportMaterialsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.table_name = "ReportMaterials" # Virtual table name for config
        self.config = ConfigManager()
        self.setWindowIcon(QIcon(r"img\icon.ico"))
        self.setWindowTitle("Reportar Materiales Vistos")
        self.resize(1100, 600)
        self.layout = QVBoxLayout(self)

        self.model = QStandardItemModel(20, 8)
        self.model.setHorizontalHeaderLabels([
            "datetime_range_utc_06", "is_spinoff", "season", "type_resource",
            "title_material", "type_repeat", "type_listen", "model_writer"
        ])

        self.view = QTableView()
        self.view.setModel(self.model)
        
        from data_table import ColumnHeaderView
        self.header = ColumnHeaderView(Qt.Orientation.Horizontal, self.view)
        self.view.setHorizontalHeader(self.header)
        
        # Delegates
        self.view.setItemDelegateForColumn(1, SpinoffDelegate(self))
        self.view.setItemDelegateForColumn(2, SeasonDelegate(self))
        self.view.setItemDelegateForColumn(3, TypeResourceDelegate(self))
        self.view.setItemDelegateForColumn(4, TitleMaterialDelegate(self))
        self.view.setItemDelegateForColumn(5, CatalogDelegate("repeat", self))
        self.view.setItemDelegateForColumn(6, CatalogDelegate("listen", self))
        self.view.setItemDelegateForColumn(7, CatalogDelegate("write", self))

        self.layout.addWidget(QLabel("Pega los datetimes en la primera columna. Las temporadas y materiales se filtrarán según tu selección."))
        self.layout.addWidget(self.view)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Agregar")
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        
        self.buttons.accepted.connect(self.process_addition)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        # Apply saved column configs
        self.apply_column_configs()

        # Install event filter for pasting
        self.view.installEventFilter(self)

    def apply_column_configs(self):
        self.header._is_applying_config = True
        
        for i in range(self.model.columnCount()):
            col_name = self.model.headerData(i, Qt.Orientation.Horizontal)
            col_config = self.config.get_column_config(self.table_name, col_name)
            
            width = col_config.get("width")
            locked = col_config.get("locked", False)
            
            if locked:
                self.header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.header.resizeSection(i, width)
            else:
                self.header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                if width:
                    self.header.resizeSection(i, width)
        
        self.header._is_applying_config = False

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress and event.matches(QKeySequence.StandardKey.Paste):
            self.handle_paste()
            return True
        return super().eventFilter(source, event)

    def handle_paste(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return

        lines = text.splitlines()
        current_row = self.view.currentIndex().row()
        if current_row < 0:
            current_row = self.model.rowCount()

        for i, line in enumerate(lines):
            row_to_fill = current_row + i
            if row_to_fill >= self.model.rowCount():
                self.model.appendRow([QStandardItem("") for _ in range(8)])
            
            self.model.setData(self.model.index(row_to_fill, 0), line.strip())

    def process_addition(self):
        from db_operations import DBOperations
        
        materials_list = []
        for r in range(self.model.rowCount()):
            dt = self.model.data(self.model.index(r, 0))
            season = self.model.data(self.model.index(r, 2))
            title = self.model.data(self.model.index(r, 4))
            
            if not dt or not season or not title:
                continue
                
            materials_list.append({
                'dt': dt,
                'season': season,
                'title': title,
                'type_repeat': self.model.data(self.model.index(r, 5)),
                'type_listen': self.model.data(self.model.index(r, 6)),
                'model_writer': self.model.data(self.model.index(r, 7))
            })

        if not materials_list:
            QMessageBox.warning(self, "Advertencia", "No hay registros válidos para agregar (asegúrate de llenar datetime, season y material).")
            return

        ops = DBOperations()
        success_count = ops.process_materials_report(materials_list)

        QMessageBox.information(self, "Éxito", f"Se agregaron {success_count} registros correctamente.")
        self.accept()

class SpinoffDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItem("No", 0)
        editor.addItem("Sí", 1)
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.ItemDataRole.EditRole)
        idx = editor.findData(1 if val == "Sí" else 0)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor, model, index):
        old_val = model.data(index, Qt.ItemDataRole.EditRole)
        new_val = editor.currentText()
        model.setData(index, new_val, Qt.ItemDataRole.EditRole)
        if old_val != new_val:
            # Clear season, type_resource and title_material if is_spinoff changed
            model.setData(model.index(index.row(), 2), "", Qt.ItemDataRole.EditRole)
            model.setData(model.index(index.row(), 3), "", Qt.ItemDataRole.EditRole)
            model.setData(model.index(index.row(), 4), "", Qt.ItemDataRole.EditRole)

class SeasonDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItem("", None)
        is_spinoff_str = index.model().data(index.model().index(index.row(), 1))
        is_spinoff = 1 if is_spinoff_str == "Sí" else 0
        
        db = QSqlDatabase.database("global_db")
        q = QSqlQuery(db)
        q.prepare("SELECT precure_season_name FROM T_Seasons WHERE is_spinoff = ? ORDER BY year ASC")
        q.addBindValue(is_spinoff)
        if q.exec():
            while q.next():
                editor.addItem(q.value(0))
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.ItemDataRole.EditRole)
        idx = editor.findText(str(val))
        if idx >= 0: editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        old_val = model.data(index, Qt.ItemDataRole.EditRole)
        new_val = editor.currentText()
        model.setData(index, new_val, Qt.ItemDataRole.EditRole)
        if old_val != new_val:
            # Clear title_material if season changed
            model.setData(model.index(index.row(), 4), "", Qt.ItemDataRole.EditRole)

class TypeResourceDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItem("", None)
        db = QSqlDatabase.database("global_db")
        q = QSqlQuery(db)
        q.exec("SELECT type_resource FROM T_Type_Resources ORDER BY type_resource ASC")
        while q.next():
            editor.addItem(q.value(0))
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.ItemDataRole.EditRole)
        idx = editor.findText(str(val))
        if idx >= 0: editor.setCurrentIndex(idx)
        else: editor.setCurrentIndex(0)

    def setModelData(self, editor, model, index):
        old_val = model.data(index, Qt.ItemDataRole.EditRole)
        new_val = editor.currentText()
        model.setData(index, new_val, Qt.ItemDataRole.EditRole)
        if old_val != new_val:
            # Clear title_material if type_resource changed
            model.setData(model.index(index.row(), 4), "", Qt.ItemDataRole.EditRole)

class TitleMaterialDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItem("", None)
        season = index.model().data(index.model().index(index.row(), 2))
        type_res = index.model().data(index.model().index(index.row(), 3))
        if not season:
            return editor
            
        db_global = QSqlDatabase.database("global_db")
        q = QSqlQuery(db_global)
        q.prepare("SELECT year FROM T_Seasons WHERE precure_season_name = ?")
        q.addBindValue(season)
        if q.exec() and q.next():
            year = q.value(0)
            from db_manager import get_yearly_db_path
            db_path = get_yearly_db_path(year)
            
            conn_name = f"tmp_title_db_{year}"
            db_year = QSqlDatabase.addDatabase("QSQLITE", conn_name)
            db_year.setDatabaseName(db_path)
            if db_year.open():
                qy = QSqlQuery(db_year)

                sql = "SELECT title_material FROM T_Resources WHERE precure_season_name = ?"
                type_idx = None
                if type_res:
                    q_idx = QSqlQuery(db_global)
                    q_idx.prepare("SELECT idx FROM T_Type_Resources WHERE type_resource = ?")
                    q_idx.addBindValue(type_res)
                    if q_idx.exec() and q_idx.next():
                        type_idx = q_idx.value(0)
                        sql += " AND type_material = ?"

                sql += " ORDER BY title_material ASC"

                qy.prepare(sql)
                qy.addBindValue(season)
                if type_idx is not None:
                    qy.addBindValue(type_idx)

                if qy.exec():
                    while qy.next():
                        editor.addItem(qy.value(0))
                db_year.close()
            QSqlDatabase.removeDatabase(conn_name)
            
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.ItemDataRole.EditRole)
        idx = editor.findText(str(val))
        if idx >= 0: editor.setCurrentIndex(idx)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

class CatalogDelegate(QStyledItemDelegate):
    def __init__(self, category, parent=None):
        super().__init__(parent)
        self.category = category

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItem("", None)
        db = QSqlDatabase.database("global_db")
        q = QSqlQuery(db)
        q.prepare("SELECT type FROM T_Type_Catalog_Reg WHERE category = ? ORDER BY type ASC")
        q.addBindValue(self.category)
        if q.exec():
            while q.next():
                editor.addItem(q.value(0))
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.ItemDataRole.EditRole)
        idx = editor.findText(str(val))
        if idx >= 0: editor.setCurrentIndex(idx)
        else: editor.setCurrentIndex(0)

    def setModelData(self, editor, model, index):
        model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.setWindowIcon(QIcon(r"img\icon.ico"))
        self.setWindowTitle("Configuración")
        self.setMinimumWidth(500)
        
        self.layout = QVBoxLayout(self)
        
        # Paths Group
        paths_group = QGroupBox("Rutas")
        paths_layout = QFormLayout()
        
        self.base_dir_edit = QLineEdit(self.config.get("base_dir_path"))
        self.btn_browse_base = QPushButton("...")
        self.btn_browse_base.clicked.connect(self.browse_base_dir)
        base_h_layout = QHBoxLayout()
        base_h_layout.addWidget(self.base_dir_edit)
        base_h_layout.addWidget(self.btn_browse_base)
        paths_layout.addRow("Ruta Base Recursos:", base_h_layout)
        
        self.global_db_edit = QLineEdit(self.config.get("global_db_path"))
        self.btn_browse_db = QPushButton("...")
        self.btn_browse_db.clicked.connect(self.browse_global_db)
        db_h_layout = QHBoxLayout()
        db_h_layout.addWidget(self.global_db_edit)
        db_h_layout.addWidget(self.btn_browse_db)
        paths_layout.addRow("Ruta DB Global:", db_h_layout)
        
        self.config_path_edit = QLineEdit(self.config.config_path)
        self.config_path_edit.setReadOnly(True)
        self.btn_move_config = QPushButton("Cambiar/Mover JSON")
        self.btn_move_config.clicked.connect(self.move_config_json)
        config_h_layout = QHBoxLayout()
        config_h_layout.addWidget(self.config_path_edit)
        config_h_layout.addWidget(self.btn_move_config)
        paths_layout.addRow("Ubicación de Ajustes:", config_h_layout)
        
        paths_group.setLayout(paths_layout)
        self.layout.addWidget(paths_group)
        
        # UI Settings Group
        ui_group = QGroupBox("Interfaz de Usuario")
        ui_layout = QFormLayout()
        
        self.auto_resize_cb = QCheckBox()
        self.auto_resize_cb.setChecked(self.config.get("ui.auto_resize", True))
        ui_layout.addRow("Auto-ajustar columnas:", self.auto_resize_cb)
        
        self.show_const_logs_cb = QCheckBox()
        self.show_const_logs_cb.setChecked(self.config.get("ui.show_construction_logs", False))
        ui_layout.addRow("Mostrar logs de construcción:", self.show_const_logs_cb)
        
        self.show_sidebar_cb = QCheckBox()
        self.show_sidebar_cb.setChecked(self.config.get("ui.sidebar_visible", True))
        ui_layout.addRow("Ver panel de años:", self.show_sidebar_cb)
        
        self.show_console_cb = QCheckBox()
        self.show_console_cb.setChecked(self.config.get("ui.console_visible", True))
        ui_layout.addRow("Ver consola SQL:", self.show_console_cb)
        
        self.theme_combo = QComboBox()
        self.theme_combo.addItems(["Fusion", "Windows", "Dark"])
        self.theme_combo.setCurrentText(self.config.get("ui.theme", "Fusion"))
        ui_layout.addRow("Tema:", self.theme_combo)
        
        ui_group.setLayout(ui_layout)
        self.layout.addWidget(ui_group)
        
        # Column Management Button
        self.btn_manage_columns = QPushButton("Administrar Anchos de Columnas")
        self.btn_manage_columns.clicked.connect(self.manage_columns)
        self.layout.addWidget(self.btn_manage_columns)
        
        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_save)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def browse_base_dir(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Seleccionar Ruta Base", self.base_dir_edit.text())
        if dir_path:
            self.base_dir_edit.setText(dir_path)

    def browse_global_db(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Seleccionar DB Global", self.global_db_edit.text(), "SQLite DB (*.db)")
        if file_path:
            self.global_db_edit.setText(file_path)

    def move_config_json(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Mover archivo de ajustes", self.config_path_edit.text(), "JSON (*.json)")
        if file_path:
            if self.config.move_config_file(file_path):
                self.config_path_edit.setText(file_path)
                QMessageBox.information(self, "Éxito", "Archivo de ajustes movido correctamente.")

    def manage_columns(self):
        dialog = ColumnManagementDialog(self)
        dialog.exec()

    def validate_and_save(self):
        base_path = self.base_dir_edit.text()
        db_path = self.global_db_edit.text()
        
        valid_base, msg_base = ConfigManager.validate_base_dir(base_path)
        if not valid_base:
            res = QMessageBox.warning(self, "Validación de Ruta Base", f"{msg_base}\n¿Deseas guardar de todas formas?", 
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if res == QMessageBox.StandardButton.No:
                return
        
        valid_db, msg_db = ConfigManager.validate_db_path(db_path)
        if not valid_db:
            res = QMessageBox.warning(self, "Validación de DB Global", f"{msg_db}\n¿Deseas guardar de todas formas?", 
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if res == QMessageBox.StandardButton.No:
                return

        self.config.set("base_dir_path", base_path, save=False)
        self.config.set("global_db_path", db_path, save=False)
        self.config.set("ui.auto_resize", self.auto_resize_cb.isChecked(), save=False)
        self.config.set("ui.show_construction_logs", self.show_const_logs_cb.isChecked(), save=False)
        self.config.set("ui.sidebar_visible", self.show_sidebar_cb.isChecked(), save=False)
        self.config.set("ui.console_visible", self.show_console_cb.isChecked(), save=False)
        self.config.set("ui.theme", self.theme_combo.currentText(), save=True) # Last one saves
        
        self.accept()

class ColumnManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.setWindowIcon(QIcon(r"img\icon.ico"))
        self.setWindowTitle("Gestión de Anchos de Columnas")
        self.resize(600, 400)
        self.layout = QVBoxLayout(self)
        
        self.tree = QTreeView()
        self.tree.setHeaderHidden(False)
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Elemento", "Ancho (px)", "Bloqueado"])
        
        self.load_data()
        self.tree.setModel(self.model)
        self.tree.expandAll()
        self.layout.addWidget(self.tree)
        
        self.btn_clear = QPushButton("Limpiar Todo")
        self.btn_clear.clicked.connect(self.clear_all)
        self.layout.addWidget(self.btn_clear)
        
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.save_data)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def load_data(self):
        configs = self.config.get("ui.column_configs", {})
        root = self.model.invisibleRootItem()
        
        for table_name, columns in configs.items():
            table_item = QStandardItem(table_name)
            table_item.setEditable(False)
            
            for col_name, config in columns.items():
                col_item = QStandardItem(col_name)
                col_item.setEditable(False)
                
                width_item = QStandardItem(str(config.get("width", 100)))
                
                lock_item = QStandardItem()
                lock_item.setCheckable(True)
                lock_item.setCheckState(Qt.CheckState.Checked if config.get("locked", False) else Qt.CheckState.Unchecked)
                lock_item.setEditable(False)
                
                table_item.appendRow([col_item, width_item, lock_item])
            
            root.appendRow(table_item)

    def save_data(self):
        new_configs = {}
        root = self.model.invisibleRootItem()
        
        for i in range(root.rowCount()):
            table_item = root.child(i)
            table_name = table_item.text()
            new_configs[table_name] = {}
            
            for j in range(table_item.rowCount()):
                col_name = table_item.child(j, 0).text()
                try:
                    width = int(table_item.child(j, 1).text())
                except:
                    width = 100
                locked = table_item.child(j, 2).checkState() == Qt.CheckState.Checked
                
                new_configs[table_name][col_name] = {"width": width, "locked": locked}
        
        self.config.set("ui.column_configs", new_configs)
        self.accept()

    def clear_all(self):
        if QMessageBox.question(self, "Confirmar", "¿Seguro que quieres borrar todas las configuraciones de columnas?") == QMessageBox.StandardButton.Yes:
            self.model.clear()
            self.model.setHorizontalHeaderLabels(["Elemento", "Ancho (px)", "Bloqueado"])
            self.config.set("ui.column_configs", {})
            self.accept()
