from PyQt6.QtWidgets import QWidget, QHBoxLayout, QLabel, QStyle
from PyQt6.QtCore import Qt

class OfflineWarningBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(30)

        # Use a background widget to ensure color occupies full width without margins
        self.bg_widget = QWidget(self)
        self.bg_widget.setObjectName("warning_bg")
        self.bg_widget.setStyleSheet("""
            QWidget#warning_bg {
                background-color: #FFF29D;
                border-bottom: 1px solid #D4C46B;
            }
        """)

        self.main_layout = QHBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.addWidget(self.bg_widget)

        self.content_layout = QHBoxLayout(self.bg_widget)
        self.content_layout.setContentsMargins(10, 0, 10, 0)

        self.warning_icon = QLabel()
        self.warning_icon.setPixmap(self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning).pixmap(16, 16))

        self.label = QLabel("El disco 'E:/' no está disponible. Los datos respaldados están en modo de solo lectura. La exposición de materiales API no está operativa.")
        self.label.setStyleSheet("font-weight: bold; color: black;")

        self.content_layout.addWidget(self.warning_icon)
        self.content_layout.addWidget(self.label)
        self.content_layout.addStretch()

        self.setVisible(False)
