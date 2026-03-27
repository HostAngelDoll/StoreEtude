from PyQt6.QtWidgets import QStyledItemDelegate, QComboBox
from PyQt6.QtCore import Qt
from PyQt6.QtSql import QSqlTableModel

class ComboDelegate(QStyledItemDelegate):
    def __init__(self, table_name, model_column, filter_str=None, parent=None):
        super().__init__(parent)
        self.table_name = table_name
        self.model_column = model_column
        self.filter_str = filter_str

    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)

        # Get DB from model
        model = index.model()
        db = model.database()

        # Create a temporary model for the combo
        rel_model = QSqlTableModel(editor, db)
        rel_model.setTable(self.table_name)
        if self.filter_str:
            rel_model.setFilter(self.filter_str)
        rel_model.select()
        while rel_model.canFetchMore():
            rel_model.fetchMore()

        editor.addItem("", None) # Index 0
        col_idx = rel_model.fieldIndex(self.model_column)
        for r in range(rel_model.rowCount()):
            val = rel_model.data(rel_model.index(r, col_idx))
            editor.addItem(str(val), val)

        return editor

    def setEditorData(self, editor, index):
        value = index.data(Qt.ItemDataRole.EditRole)
        idx = editor.findData(value)
        if idx >= 0:
            editor.setCurrentIndex(idx)
        else:
            editor.setCurrentIndex(0)

    def setModelData(self, editor, model, index):
        val = editor.currentData()
        model.setData(index, val if val != "" else None, Qt.ItemDataRole.EditRole)
