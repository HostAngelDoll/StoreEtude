from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QStyle
from PyQt6.QtCore import Qt

class OfflineWarningBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 0, 10, 0)

        self.warning_icon = QLabel()
        self.warning_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(16, 16))

        self.label = QLabel("El disco 'E:/' no está disponible. Los datos respaldados están en modo de solo lectura.")
        self.label.setStyleSheet("font-weight: bold; color: black;")

        self.layout.addWidget(self.warning_icon)
        self.layout.addWidget(self.label)
        self.layout.addStretch()

        self.setStyleSheet("background-color: #FFF29D; border-bottom: 1px solid #D4C46B;")
        self.setVisible(False)
