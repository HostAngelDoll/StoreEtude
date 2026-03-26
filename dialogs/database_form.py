from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QLineEdit, QPushButton, QHBoxLayout, QMessageBox, QSpinBox, QCheckBox, QComboBox)
from PyQt6.QtCore import Qt
from PyQt6.QtSql import QSqlRelationalDelegate

class DatabaseForm(QDialog):
    def __init__(self, model, row_index=None, parent=None):
        super().__init__(parent)
        self.model = model
        self.row_index = row_index
        self.setWindowTitle("Añadir Registro" if row_index is None else "Editar Registro")
        self.widgets = {}
        self.init_ui()
        if row_index is not None: self.load_data()

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        for i in range(self.model.columnCount()):
            field_name = self.model.record().fieldName(i)
            label_text = self.model.headerData(i, Qt.Orientation.Horizontal)

            # Simple heuristic for widget type based on column name or model info
            # In a real app we'd use meta-data, but here we can infer from common names
            if "is_" in field_name.lower():
                widget = QCheckBox()
                self.widgets[i] = widget
            elif "ep_num" in field_name.lower() or "total" in field_name.lower():
                widget = QSpinBox()
                widget.setRange(0, 9999)
                self.widgets[i] = widget
            elif self.model.relation(i).isValid():
                widget = QComboBox()
                rel_model = self.model.relationModel(i)
                widget.setModel(rel_model)
                widget.setModelColumn(rel_model.fieldIndex(self.model.relation(i).displayColumn()))
                self.widgets[i] = widget
            else:
                widget = QLineEdit()
                self.widgets[i] = widget

            form_layout.addRow(label_text, widget)

        layout.addLayout(form_layout)

        btn_layout = QHBoxLayout()
        self.btn_save, self.btn_cancel = QPushButton("Guardar"), QPushButton("Cancelar")
        btn_layout.addStretch(); btn_layout.addWidget(self.btn_save); btn_layout.addWidget(self.btn_cancel)
        layout.addLayout(btn_layout)

        self.btn_save.clicked.connect(self.on_save_clicked)
        self.btn_cancel.clicked.connect(self.reject)

    def load_data(self):
        for i, widget in self.widgets.items():
            val = self.model.data(self.model.index(self.row_index, i))
            if isinstance(widget, QCheckBox): widget.setChecked(bool(val))
            elif isinstance(widget, QSpinBox): widget.setValue(int(val) if val else 0)
            elif isinstance(widget, QComboBox):
                idx = widget.findText(str(val))
                if idx >= 0: widget.setCurrentIndex(idx)
            else: widget.setText(str(val) if val is not None else "")

    def on_save_clicked(self):
        if self.row_index is None: self.model.insertRow(self.model.rowCount())
        row = self.row_index if self.row_index is not None else self.model.rowCount() - 1
        for i, widget in self.widgets.items():
            if isinstance(widget, QCheckBox): val = 1 if widget.isChecked() else 0
            elif isinstance(widget, QSpinBox): val = widget.value()
            elif isinstance(widget, QComboBox):
                # For relational models, we need the actual ID (value column)
                rel = self.model.relation(i)
                rel_model = self.model.relationModel(i)
                val = rel_model.data(rel_model.index(widget.currentIndex(), rel_model.fieldIndex(rel.indexColumn())))
            else: val = widget.text() if widget.text() else None

            self.model.setData(self.model.index(row, i), val)

        if self.model.submitAll(): self.accept()
        else: QMessageBox.critical(self, "Error", f"No se pudo guardar: {self.model.lastError().text()}")
