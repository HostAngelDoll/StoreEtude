from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
                             QApplication, QDialogButtonBox, QMessageBox, QHeaderView)
from PyQt6.QtGui import QIcon, QStandardItemModel, QStandardItem, QKeySequence
from PyQt6.QtCore import Qt, QEvent
from PyQt6.QtSql import QSqlQuery, QSqlDatabase
from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox
from datetime import datetime
import os
from config_manager import ConfigManager

class SpinoffDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItem("No", 0)
        editor.addItem("Sí", 1)
        return editor

    def setEditorData(self, editor, index):
        val = index.data(Qt.ItemDataRole.EditRole)
        if isinstance(val, str):
            int_val = 1 if val == "Sí" else 0
        else:
            int_val = int(val or 0)
        idx = editor.findData(int_val)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor, model, index):
        old_val = model.data(index, Qt.ItemDataRole.EditRole)
        new_val = editor.currentText()
        model.setData(index, new_val, Qt.ItemDataRole.EditRole)
        if old_val != new_val:
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
            if db.isOpen(): return db
        from db_manager import get_yearly_db_path
        db_path = get_yearly_db_path(year)
        if not os.path.exists(db_path): return None
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

class ReportMaterialsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.table_name = "ReportMaterials"
        self.config = ConfigManager()
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
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
        self.buttons.accepted.connect(self.process_addition)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        self.apply_column_configs()
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
                if width: self.header.resizeSection(i, width)
        self.header._is_applying_config = False

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress and event.matches(QKeySequence.StandardKey.Paste):
            self.handle_paste()
            return True
        return super().eventFilter(source, event)

    def handle_paste(self):
        index = self.view.currentIndex()
        if not index.isValid() or index.column() != 0: return
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text: return
        lines = text.splitlines()
        current_row = max(0, index.row())
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
            if not dt or not season or not title: continue
            try:
                parts = str(dt).strip().split(' ')
                if len(parts) < 2: raise ValueError()
                datetime.strptime(parts[0], "%Y-%m-%d")
            except: continue
            materials_list.append({
                'dt': dt, 'season': season, 'title': title,
                'type_repeat': self.model.data(self.model.index(r, 5)),
                'type_listen': self.model.data(self.model.index(r, 6)),
                'model_writer': self.model.data(self.model.index(r, 7))
            })
        if not materials_list:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Advertencia", "No hay registros válidos para agregar.")
            return
        ops = DBOperations()
        success_count = ops.process_materials_report(materials_list)
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "Éxito", f"Se agregaron {success_count} registros correctamente.")
        self.accept()
