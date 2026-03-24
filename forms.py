from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QSpinBox, 
                             QCheckBox, QDialogButtonBox, QMessageBox, QComboBox,
                             QVBoxLayout, QHBoxLayout, QRadioButton, QButtonGroup,
                             QLabel, QWidget, QTableView, QStyledItemDelegate,
                             QApplication, QFileDialog, QGroupBox, QPushButton,
                             QHeaderView, QTreeView, QScrollArea, QProgressBar,
                             QInputDialog, QListWidget, QListWidgetItem, QGridLayout)
from PyQt6.QtSql import QSqlRelationalTableModel, QSqlRelation, QSqlTableModel, QSqlQuery, QSqlDatabase
from PyQt6.QtCore import Qt, QEvent, QUrl
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QKeySequence, QIcon, QDesktopServices
from datetime import datetime
import os
from config_manager import ConfigManager
from telegram_manager import TelegramManager

class ChatSelectionDialog(QDialog):
    def __init__(self, chats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Chat")
        self.resize(400, 500)
        self.layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for chat in chats:
            item = QListWidgetItem(chat['name'])
            item.setData(Qt.ItemDataRole.UserRole, chat)
            self.list_widget.addItem(item)

        self.layout.addWidget(self.list_widget)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_selected_chat(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None

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
        index = self.view.currentIndex()
        if not index.isValid() or index.column() != 0:
            return

        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return

        lines = text.splitlines()
        current_row = index.row()
        if current_row < 0:
            current_row = 0

        for i, line in enumerate(lines):
            row_to_fill = current_row + i
            if row_to_fill >= self.model.rowCount():
                self.model.appendRow([QStandardItem("") for _ in range(8)])
            
            self.model.setData(self.model.index(row_to_fill, 0), line.strip())

    def process_addition(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        from db_operations import DBOperations
        
        materials_list = []
        for r in range(self.model.rowCount()):
            dt = self.model.data(self.model.index(r, 0))
            season = self.model.data(self.model.index(r, 2))
            title = self.model.data(self.model.index(r, 4))
            
            if not dt or not season or not title:
                continue

            # Datetime validation
            try:
                # Expected format: "2023-01-01 03:07:00-03:32:00"
                # We validate the first part which is a standard datetime
                parts = str(dt).strip().split(' ')
                if len(parts) < 2: raise ValueError()
                datetime.strptime(parts[0], "%Y-%m-%d")
            except:
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

        QApplication.restoreOverrideCursor()
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
        # Normalization: handle both int/bool and "Sí"/"No" string values
        if isinstance(val, str):
            int_val = 1 if val == "Sí" else 0
        else:
            int_val = int(val or 0)

        idx = editor.findData(int_val)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor, model, index):
        old_val = model.data(index, Qt.ItemDataRole.EditRole)
        new_val = editor.currentText() # Stores as string "Sí"/"No" for standard staging model consistency
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
    _db_cache = {}

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
            
            db_year = self._get_cached_db(year)
            if db_year and db_year.isOpen():
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
            
        return editor

    def _get_cached_db(self, year):
        conn_name = f"cached_title_db_{year}"
        if conn_name in self._db_cache:
            db = self._db_cache[conn_name]
            if db.isOpen():
                return db

        from db_manager import get_yearly_db_path
        db_path = get_yearly_db_path(year)
        if not os.path.exists(db_path):
            return None

        db = QSqlDatabase.addDatabase("QSQLITE", conn_name)
        db.setDatabaseName(db_path)
        if db.open():
            self._db_cache[conn_name] = db
            return db
        return None

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
    def __init__(self, parent=None, tg_manager=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.tg_manager = tg_manager
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
        
        # Telegram Settings Group
        tg_group = QGroupBox("Telegram")
        tg_layout = QFormLayout()

        self.api_id_edit = QLineEdit(str(self.config.get("telegram.api_id", "")))
        tg_layout.addRow("API ID:", self.api_id_edit)

        self.api_hash_edit = QLineEdit(self.config.get("telegram.api_hash", ""))
        tg_layout.addRow("API Hash:", self.api_hash_edit)

        help_label = QLabel('<a href="https://my.telegram.org/">¿Dónde consigo esto?</a>')
        help_label.setOpenExternalLinks(True)
        tg_layout.addRow("", help_label)

        self.tg_status_label = QLabel("No conectado")
        self.btn_tg_connect = QPushButton("Conectar")
        self.btn_tg_connect.clicked.connect(self.on_tg_main_btn_clicked)
        self._tg_connected = False

        tg_conn_layout = QHBoxLayout()
        tg_conn_layout.addWidget(self.tg_status_label)
        tg_conn_layout.addStretch()
        tg_conn_layout.addWidget(self.btn_tg_connect)
        tg_layout.addRow("Estado:", tg_conn_layout)

        self.chat_name_label = QLabel(self.config.get("telegram.chat_name", "Ninguno seleccionado"))
        self.btn_select_chat = QPushButton("Elegir Grupo/Canal")
        self.btn_select_chat.clicked.connect(self.on_select_chat_clicked)

        tg_chat_layout = QHBoxLayout()
        tg_chat_layout.addWidget(self.chat_name_label)
        tg_chat_layout.addStretch()
        tg_chat_layout.addWidget(self.btn_select_chat)
        tg_layout.addRow("Chat Destino:", tg_chat_layout)

        tg_group.setLayout(tg_layout)
        self.layout.addWidget(tg_group)

        # Column Management Button
        self.btn_manage_columns = QPushButton("Administrar Anchos de Columnas")
        self.btn_manage_columns.clicked.connect(self.manage_columns)
        self.layout.addWidget(self.btn_manage_columns)
        
        # Buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.validate_and_save)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def _init_tg_manager(self):
        if self.tg_manager:
            try:
                self.tg_manager.connection_status.disconnect(self.update_tg_status)
            except: pass
            try:
                self.tg_manager.auth_required.disconnect(self.handle_tg_auth)
            except: pass
            try:
                self.tg_manager.chats_loaded.disconnect(self.show_chat_selection)
            except: pass

            self.tg_manager.connection_status.connect(self.update_tg_status)
            self.tg_manager.auth_required.connect(self.handle_tg_auth)
            self.tg_manager.chats_loaded.connect(self.show_chat_selection)

    def on_tg_main_btn_clicked(self):
        self._init_tg_manager()
        if self._tg_connected:
            self.tg_manager.disconnect()
        else:
            # Save current API credentials first
            self.config.set("telegram.api_id", self.api_id_edit.text(), save=False)
            self.config.set("telegram.api_hash", self.api_hash_edit.text(), save=True)
            self.tg_manager.connect()

    def update_tg_status(self, message, connected):
        self.tg_status_label.setText(message)
        self._tg_connected = connected
        self.btn_tg_connect.setText("Desconectar" if connected else "Conectar")

    def handle_tg_auth(self, type):
        if not self.tg_manager: return
        self._init_tg_manager()
        if type == "phone":
            phone, ok = QInputDialog.getText(self, "Telegram Auth", "Introduce tu número de teléfono (+...):")
            if ok: self.tg_manager.submit_phone(phone)
        elif type == "code":
            code, ok = QInputDialog.getText(self, "Telegram Auth", "Introduce el código de verificación:")
            if ok: self.tg_manager.submit_code(code)
        elif type == "password":
            pw, ok = QInputDialog.getText(self, "Telegram Auth", "Introduce tu contraseña 2FA:", QLineEdit.EchoMode.Password)
            if ok: self.tg_manager.submit_password(pw)

    def on_select_chat_clicked(self):
        if not self.tg_manager:
            QMessageBox.critical(self, "Error", "Telegram Manager no disponible.")
            return
        self._init_tg_manager()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.tg_manager.fetch_chats()

    def show_chat_selection(self, chats):
        QApplication.restoreOverrideCursor()
        dialog = ChatSelectionDialog(chats, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            chat = dialog.get_selected_chat()
            if chat:
                self.config.set("telegram.chat_id", chat['id'], save=False)
                self.config.set("telegram.chat_name", chat['name'], save=True)
                self.chat_name_label.setText(chat['name'])

    def closeEvent(self, event):
        if self.tg_manager:
            try:
                self.tg_manager.connection_status.disconnect(self.update_tg_status)
                self.tg_manager.auth_required.disconnect(self.handle_tg_auth)
                self.tg_manager.chats_loaded.disconnect(self.show_chat_selection)
            except: pass
        super().closeEvent(event)

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
        self.config.set("ui.theme", self.theme_combo.currentText(), save=False)

        self.config.set("telegram.api_id", self.api_id_edit.text(), save=False)
        self.config.set("telegram.api_hash", self.api_hash_edit.text(), save=True) # Last one saves
        
        self.accept()

class DuplicateActionDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(r"img\icon.ico"))
        self.setWindowTitle("Conflicto de Duplicado")
        self.setMinimumWidth(400)
        self.layout = QVBoxLayout(self)

        self.layout.addWidget(QLabel(f"El recurso '{title}' ya existe en la base de datos."))
        self.layout.addWidget(QLabel("¿Qué acción deseas tomar?"))

        self.radio_omit = QRadioButton("Omitir (No hacer nada)")
        self.radio_update_paths = QRadioButton("Actualizar Rutas (Solo actualiza las rutas relativas)")
        self.radio_replace = QRadioButton("Reemplazar (Actualiza todos los metadatos: duración, fecha, etc.)")

        self.radio_omit.setChecked(True)

        self.bg = QButtonGroup(self)
        self.bg.addButton(self.radio_omit, 0)
        self.bg.addButton(self.radio_update_paths, 1)
        self.bg.addButton(self.radio_replace, 2)

        self.layout.addWidget(self.radio_omit)
        self.layout.addWidget(self.radio_update_paths)
        self.layout.addWidget(self.radio_replace)

        self.apply_all_cb = QCheckBox("Aplicar esta acción a todos los demás duplicados")
        self.layout.addWidget(self.apply_all_cb)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        self.buttons.accepted.connect(self.accept)
        self.layout.addWidget(self.buttons)

    def get_choice(self):
        return self.bg.checkedId(), self.apply_all_cb.isChecked()

class TelegramDownloadDialog(QDialog):
    def __init__(self, parent=None, tg_manager=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.tg_manager = tg_manager

        if self.tg_manager:
            # Avoid duplicate connections
            try:
                self.tg_manager.videos_loaded.disconnect(self.populate_videos)
            except: pass
            try:
                self.tg_manager.download_progress.disconnect(self.update_progress)
            except: pass
            try:
                self.tg_manager.download_finished.disconnect(self.on_download_finished)
            except: pass

        self.setWindowIcon(QIcon(r"img\icon.ico"))
        self.setWindowTitle("Descargar nuevo contenido desde Telegram")
        self.resize(800, 700)
        self.layout = QVBoxLayout(self)

        # 1. Video Selection Area
        self.layout.addWidget(QLabel("Últimos videos del canal/grupo:"))
        self.video_list_widget = QWidget()
        self.video_list_layout = QVBoxLayout(self.video_list_widget)
        self.video_scroll = QScrollArea()
        self.video_scroll.setWidgetResizable(True)
        self.video_scroll.setWidget(self.video_list_widget)
        self.layout.addWidget(self.video_scroll)

        # 2. Destination Selection Area
        dest_group = QGroupBox("Destino de descarga")
        dest_layout = QGridLayout()

        dest_layout.addWidget(QLabel("Año:"), 0, 0)
        self.year_combo = QComboBox()
        current_year = datetime.now().year
        for y in range(2004, current_year + 1):
            self.year_combo.addItem(str(y))
        self.year_combo.setCurrentText(str(current_year))
        self.year_combo.currentTextChanged.connect(self.update_master_subfolders)
        dest_layout.addWidget(self.year_combo, 0, 1)

        dest_layout.addWidget(QLabel("Carpeta Master:"), 1, 0)
        self.master_combo = QComboBox()
        self.master_combo.currentTextChanged.connect(self.update_first_file_label)
        dest_layout.addWidget(self.master_combo, 1, 1)

        dest_layout.addWidget(QLabel("Primer archivo actual:"), 2, 0)
        self.first_file_label = QLabel("N/A")
        self.first_file_label.setStyleSheet("font-weight: bold; color: #4282da;")
        dest_layout.addWidget(self.first_file_label, 2, 1)

        dest_group.setLayout(dest_layout)
        self.layout.addWidget(dest_group)

        # 3. Renaming Area
        self.layout.addWidget(QLabel("Opciones de renombrado:"))
        self.rename_widget = QWidget()
        self.rename_layout = QVBoxLayout(self.rename_widget)
        self.rename_scroll = QScrollArea()
        self.rename_scroll.setWidgetResizable(True)
        self.rename_scroll.setWidget(self.rename_widget)
        self.layout.addWidget(self.rename_scroll)

        # 4. Progress and Buttons
        self.progress_bar = QProgressBar()
        self.layout.addWidget(self.progress_bar)
        self.status_label = QLabel("Listo")
        self.layout.addWidget(self.status_label)

        btn_layout = QHBoxLayout()
        self.btn_download = QPushButton("Descargar")
        self.btn_download.clicked.connect(self.start_downloads)
        self.btn_close = QPushButton("Cerrar")
        self.btn_close.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_download)
        btn_layout.addWidget(self.btn_close)
        self.layout.addLayout(btn_layout)

        # Internal state
        self.video_items = [] # List of (checkbox, message_dict, rename_checkbox, rename_input)
        self._apply_to_all_choice = None # (choice, rename_pattern)

        # Connect TG signals
        if self.tg_manager:
            self.tg_manager.videos_loaded.connect(self.populate_videos)
            self.tg_manager.download_progress.connect(self.update_progress)
            self.tg_manager.download_finished.connect(self.on_download_finished)

        # Initial data
        self.update_master_subfolders()
        self.fetch_latest_videos()

    def fetch_latest_videos(self):
        chat_id = self.config.get("telegram.chat_id")
        if chat_id and self.tg_manager:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            self.tg_manager.fetch_videos(chat_id, limit=5)
        elif not chat_id:
            QMessageBox.warning(self, "Telegram", "No se ha seleccionado un chat de destino en Configuración.")

    def populate_videos(self, videos):
        QApplication.restoreOverrideCursor()
        # Clear current
        while self.video_list_layout.count():
            item = self.video_list_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        while self.rename_layout.count():
            item = self.rename_layout.takeAt(0)
            if item.widget(): item.widget().deleteLater()

        self.video_items = []

        for v in videos:
            # Video item with checkbox
            v_widget = QWidget()
            v_layout = QHBoxLayout(v_widget)
            cb = QCheckBox(f"{v['file_name']} ({v['date']})")
            v_layout.addWidget(cb)
            self.video_list_layout.addWidget(v_widget)

            # Rename item
            r_widget = QWidget()
            r_layout = QHBoxLayout(r_widget)
            msg_label = QLabel(v['text'][:50] + "..." if len(v['text']) > 50 else v['text'] or v['file_name'])
            msg_label.setToolTip(v['text'])
            r_layout.addWidget(msg_label, 1)

            ren_cb = QCheckBox("Renombrar:")
            r_layout.addWidget(ren_cb)
            ren_input = QLineEdit()
            ren_input.setPlaceholderText("Nuevo nombre de archivo...")
            ren_input.setEnabled(False)
            ren_cb.toggled.connect(ren_input.setEnabled)
            r_layout.addWidget(ren_input, 2)

            self.rename_layout.addWidget(r_widget)

            self.video_items.append({
                'cb': cb,
                'video': v,
                'ren_cb': ren_cb,
                'ren_input': ren_input
            })

    def update_master_subfolders(self):
        year = self.year_combo.currentText()
        base_path = self.config.get("base_dir_path")
        year_path = os.path.join(base_path, year)

        self.master_combo.clear()
        if os.path.exists(year_path):
            try:
                # Find folder with "___"
                master_parent = None
                for item in os.listdir(year_path):
                    if "___" in item and os.path.isdir(os.path.join(year_path, item)):
                        master_parent = os.path.join(year_path, item)
                        break

                if master_parent:
                    subfolders = [d for d in os.listdir(master_parent) if os.path.isdir(os.path.join(master_parent, d))]
                    self.master_combo.addItems(sorted(subfolders))
            except Exception as e:
                print(f"Error scanning master subfolders: {e}")

    def update_first_file_label(self):
        year = self.year_combo.currentText()
        base_path = self.config.get("base_dir_path")
        year_path = os.path.join(base_path, year)
        master_parent = None
        if os.path.exists(year_path):
            try:
                for item in os.listdir(year_path):
                    if "___" in item and os.path.isdir(os.path.join(year_path, item)):
                        master_parent = os.path.join(year_path, item)
                        break
            except Exception as e:
                print(f"Error scanning year path: {e}")

        subfolder = self.master_combo.currentText()
        if master_parent and subfolder:
            full_path = os.path.join(master_parent, subfolder)
            if os.path.exists(full_path):
                try:
                    files = [f for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f))]
                    if files:
                        files.sort(key=lambda f: os.path.getmtime(os.path.join(full_path, f)))
                        self.first_file_label.setText(files[0])
                    else:
                        self.first_file_label.setText("Vacia")
                except Exception as e:
                    print(f"Error scanning subfolder: {e}")
                    self.first_file_label.setText("Error")
            else:
                self.first_file_label.setText("No existe")
        else:
            self.first_file_label.setText("N/A")

    def start_downloads(self):
        self.to_download = [item for item in self.video_items if item['cb'].isChecked()]
        if not self.to_download:
            QMessageBox.warning(self, "Descarga", "No hay videos seleccionados.")
            return

        self._apply_to_all_choice = None
        self.btn_download.setEnabled(False)
        self.download_next()

    def download_next(self):
        if not self.to_download:
            self.status_label.setText("Todas las descargas finalizadas.")
            self.btn_download.setEnabled(True)
            return

        self.current_item = self.to_download.pop(0)
        video = self.current_item['video']

        # Determine destination
        year = self.year_combo.currentText()
        base_path = self.config.get("base_dir_path")
        year_path = os.path.join(base_path, year)
        master_parent = None
        if os.path.exists(year_path):
            for item in os.listdir(year_path):
                if "___" in item and os.path.isdir(os.path.join(year_path, item)):
                    master_parent = os.path.join(year_path, item)
                    break

        if not master_parent:
            QMessageBox.critical(self, "Error", f"No se encontró carpeta maestra para el año {year}")
            self.btn_download.setEnabled(True)
            return

        dest_folder = os.path.join(master_parent, self.master_combo.currentText())
        if not os.path.exists(dest_folder):
            try:
                os.makedirs(dest_folder)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"No se pudo crear carpeta de destino: {e}")
                self.btn_download.setEnabled(True)
                return

        filename = video['file_name']
        if self.current_item['ren_cb'].isChecked() and self.current_item['ren_input'].text():
            ext = os.path.splitext(filename)[1]
            filename = self.current_item['ren_input'].text()
            if not filename.endswith(ext):
                filename += ext

        dest_path = os.path.join(dest_folder, filename)

        # Conflict Handling
        if os.path.exists(dest_path):
            choice = self._apply_to_all_choice
            if choice is None:
                msg = f"El archivo '{filename}' ya existe.\n¿Qué deseas hacer?"
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("Archivo existente")
                msg_box.setText(msg)
                msg_box.setWindowIcon(QIcon(r"img\icon.ico"))

                over_btn = msg_box.addButton("Sobrescribir", QMessageBox.ButtonRole.ActionRole)
                skip_btn = msg_box.addButton("Omitir", QMessageBox.ButtonRole.ActionRole)
                ren_btn = msg_box.addButton("Mantener ambos (renombrar)", QMessageBox.ButtonRole.ActionRole)
                cancel_btn = msg_box.addButton("Cancelar todo", QMessageBox.ButtonRole.RejectRole)

                apply_all_cb = QCheckBox("Aplicar a todo")
                msg_box.setCheckBox(apply_all_cb)

                msg_box.exec()

                if msg_box.clickedButton() == cancel_btn:
                    self.to_download = []
                    self.btn_download.setEnabled(True)
                    return
                elif msg_box.clickedButton() == over_btn:
                    choice = "overwrite"
                elif msg_box.clickedButton() == skip_btn:
                    choice = "skip"
                elif msg_box.clickedButton() == ren_btn:
                    choice = "rename"

                if apply_all_cb.isChecked():
                    self._apply_to_all_choice = choice

            if choice == "skip":
                self.download_next()
                return
            elif choice == "rename":
                base, ext = os.path.splitext(filename)
                counter = 1
                while os.path.exists(os.path.join(dest_folder, f"{base}_{counter}{ext}")):
                    counter += 1
                dest_path = os.path.join(dest_folder, f"{base}_{counter}{ext}")

        chat_id = self.config.get("telegram.chat_id")
        if self.tg_manager:
            self.tg_manager.download_video(chat_id, video['id'], dest_path)
        else:
            QMessageBox.critical(self, "Error", "Telegram Manager no disponible.")
            self.btn_download.setEnabled(True)

    def update_progress(self, value, status):
        self.progress_bar.setValue(int(value * 100))
        self.status_label.setText(status)

    def on_download_finished(self, success, message):
        if not self.isVisible():
            return
        if success:
            self.download_next()
        else:
            QMessageBox.critical(self, "Error de descarga", f"Error al descargar: {message}")
            self.btn_download.setEnabled(True)

    def closeEvent(self, event):
        try:
            self.tg_manager.videos_loaded.disconnect(self.populate_videos)
            self.tg_manager.download_progress.disconnect(self.update_progress)
            self.tg_manager.download_finished.disconnect(self.on_download_finished)
        except: pass
        super().closeEvent(event)

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
