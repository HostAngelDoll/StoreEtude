from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox
from PyQt6.QtCore import Qt
from PyQt6.QtSql import QSqlQuery, QSqlDatabase
import os

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

    def __init__(self, parent=None, allow_user_selection=False):
        super().__init__(parent)
        self.allow_user_selection = allow_user_selection

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        editor.addItem("", None)
        if self.allow_user_selection:
            editor.addItem("[User selection]", "[User selection]")

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

        from db.schema import get_yearly_db_path
        from db_manager import get_offline_db_path
        db_path = get_yearly_db_path(year)
        if not os.path.exists(db_path):
            # TODO: Refactor get_offline_db_path
            db_path = get_offline_db_path(db_path)
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
