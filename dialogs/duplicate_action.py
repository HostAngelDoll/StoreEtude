from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QRadioButton, QButtonGroup,
                             QCheckBox, QDialogButtonBox)
from PyQt6.QtGui import QIcon
import os

class DuplicateActionDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
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
