from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QSpinBox,
                             QCheckBox, QDialogButtonBox, QMessageBox, QComboBox)
from PyQt6.QtSql import QSqlRelationalTableModel, QSqlRelation, QSqlTableModel, QSqlDatabase
from PyQt6.QtGui import QIcon
import os

class DatabaseForm(QDialog):
    def __init__(self, model, row=-1, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.model = model
        self.row = row
        self.record = model.record(row) if row >= 0 else model.record()
        self.setWindowTitle("Añadir Registro" if row < 0 else "Editar Registro")
        self.setMinimumWidth(400)

        self.layout = QFormLayout(self)
        self.widgets = {}
        self._relation_models = [] # Prevent GC

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
                db = QSqlDatabase.database(model.database().connectionName())

                if is_relational and model.relation(i).isValid():
                    rel_model = model.relationModel(i)
                    if rel_model and rel_model.rowCount() == 0:
                        rel_model.select()
                else:
                    # Manually create and filter the relation model
                    rel_model = QSqlTableModel(self, db)
                    rel_model.setTable(relation.tableName())
                    if model.tableName() == "T_Registry":
                        if field_name == "type_repeat": rel_model.setFilter("category = 'repeat'")
                        elif field_name == "type_listen": rel_model.setFilter("category = 'listen'")
                        elif field_name == "model_writer": rel_model.setFilter("category = 'write'")
                    rel_model.select()
                    self._relation_models.append(rel_model)

                widget.addItem("", None)
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
                    try:
                        widget.setValue(int(self.record.value(i)))
                    except (TypeError, ValueError):
                        widget.setValue(0)
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
            if not self.record.isGenerated(i):
                continue

            if field_name in self.widgets:
                widget = self.widgets[field_name]
                if isinstance(widget, QCheckBox):
                    self.record.setValue(i, 1 if widget.isChecked() else 0)
                elif isinstance(widget, QSpinBox):
                    self.record.setValue(i, widget.value())
                elif isinstance(widget, QComboBox):
                    key_val = widget.currentData()
                    self.record.setValue(i, key_val)
                else:
                    self.record.setValue(i, widget.text())

        db = self.model.database()
        db.transaction()

        success = False
        if self.row >= 0:
            if self.model.setRecord(self.row, self.record):
                success = self.model.submitAll()
        else:
            if self.model.insertRecord(-1, self.record):
                success = self.model.submitAll()

        if success:
            db.commit()
            super().accept()
        else:
            db.rollback()
            QMessageBox.critical(self, "Error", f"No se pudo guardar: {self.model.lastError().text()}")
