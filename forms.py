from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QSpinBox, 
                             QCheckBox, QDialogButtonBox, QMessageBox, QComboBox,
                             QVBoxLayout, QHBoxLayout, QRadioButton, QButtonGroup,
                             QLabel, QWidget)
from PyQt6.QtSql import QSqlRelationalTableModel, QSqlRelation
from PyQt6.QtCore import Qt
from datetime import datetime

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
                widget.setModel(rel_model)
                widget.setModelColumn(rel_model.fieldIndex(relation.displayColumn()))
                
                if row >= 0:
                    # Find the index of the current value in the relational model
                    current_val = self.record.value(i)
                    for rel_row in range(rel_model.rowCount()):
                        if rel_model.data(rel_model.index(rel_row, rel_model.fieldIndex(relation.indexColumn()))) == current_val:
                            widget.setCurrentIndex(rel_row)
                            break
                else:
                    widget.setCurrentIndex(-1)
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
                    rel_model = widget.model()
                    current_rel_row = widget.currentIndex()
                    if current_rel_row >= 0:
                        # We need to know which column is the indexColumn.
                        # In our case it's usually the same as displayColumn or we can infer it.
                        # Since we used QSqlRelation to set it up:
                        if isinstance(self.model, QSqlRelationalTableModel) and self.model.relation(i).isValid():
                            relation = self.model.relation(i)
                            index_col = relation.indexColumn()
                        else:
                            # Manual relation logic
                            if self.model.tableName() == "T_Registry":
                                index_col = "title_material" if field_name == "title_material" else "type"
                            else:
                                index_col = rel_model.record().fieldName(0) # Fallback

                        key_val = rel_model.data(rel_model.index(current_rel_row, rel_model.fieldIndex(index_col)))
                        self.record.setValue(i, key_val)
                    else:
                        self.record.setValue(i, None)
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
