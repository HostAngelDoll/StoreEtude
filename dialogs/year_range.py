from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QRadioButton,
                             QButtonGroup, QLabel, QSpinBox, QWidget, QDialogButtonBox)
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from datetime import datetime
import os

class YearRangeDialog(QDialog):
    def __init__(self, current_year, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
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
