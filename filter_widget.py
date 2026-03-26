from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLineEdit, QListWidget, QListWidgetItem, QCheckBox,
                             QFrame, QLabel)
from PyQt6.QtCore import Qt, pyqtSignal, QEvent

class FilterMenu(QFrame):
    filter_requested = pyqtSignal(list) # List of selected values
    sort_requested = pyqtSignal(Qt.SortOrder)

    def __init__(self, values, selected_values=None, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setWindowFlags(Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)

        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(5, 5, 5, 5)
        self.setStyleSheet("""
            QFrame {
                background-color: #333333;
                color: white;
                border: 1px solid #555;
                border-radius: 4px;
            }
            QPushButton {
                text-align: left;
                padding: 5px;
                border: none;
                background: transparent;
                color: white;
            }
            QPushButton:hover {
                background-color: #444444;
            }
            QLineEdit {
                background-color: #222;
                color: white;
                border: 1px solid #555;
                padding: 2px;
            }
            QListWidget {
                background-color: #222;
                color: white;
                border: 1px solid #555;
            }
            QListWidget::item:hover {
                background-color: #444;
            }
            QCheckBox {
                color: white;
            }
        """)

        # Sort options
        self.btn_sort_asc = QPushButton("↑ Ordenar de A a Z")
        self.btn_sort_asc.clicked.connect(lambda: self.on_sort(Qt.SortOrder.AscendingOrder))
        self.btn_sort_desc = QPushButton("↓ Ordenar de Z a A")
        self.btn_sort_desc.clicked.connect(lambda: self.on_sort(Qt.SortOrder.DescendingOrder))

        self.layout.addWidget(self.btn_sort_asc)
        self.layout.addWidget(self.btn_sort_desc)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        self.layout.addWidget(line)

        # Search box
        self.search_box = QLineEdit()
        self.search_box.setPlaceholderText("Buscar...")
        self.search_box.textChanged.connect(self.filter_list)
        self.layout.addWidget(self.search_box)

        # List with checkboxes
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(200)
        self.layout.addWidget(self.list_widget)

        self.all_checkbox = QCheckBox("(Seleccionar todo)")
        self.all_checkbox.setChecked(True)
        self.all_checkbox.stateChanged.connect(self.toggle_all)
        self.layout.addWidget(self.all_checkbox)

        self.items = []
        self.values = values
        self.populate_list(values, selected_values)

        # Footer buttons
        btn_layout = QHBoxLayout()
        self.btn_ok = QPushButton("Aceptar")
        self.btn_ok.setStyleSheet("background-color: #0078d4; color: white; font-weight: bold; border-radius: 2px; text-align: center;")
        self.btn_ok.clicked.connect(self.apply_filter)
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setStyleSheet("background-color: #555; color: white; border-radius: 2px; text-align: center;")
        self.btn_cancel.clicked.connect(self.close)
        btn_layout.addWidget(self.btn_ok)
        btn_layout.addWidget(self.btn_cancel)
        self.layout.addLayout(btn_layout)

        if not values:
            self.set_disabled(True)

    def set_disabled(self, disabled):
        self.btn_sort_asc.setDisabled(disabled)
        self.btn_sort_desc.setDisabled(disabled)
        self.search_box.setDisabled(disabled)
        self.list_widget.setDisabled(disabled)
        self.all_checkbox.setDisabled(disabled)
        self.btn_ok.setDisabled(disabled)

    def populate_list(self, values, selected_values=None):
        self.list_widget.clear()
        self.items = []
        unique_vals = sorted(list(set(values)), key=lambda x: (x is not None, str(x)))
        for val in unique_vals:
            item = QListWidgetItem(self.list_widget)
            cb = QCheckBox(str(val) if val is not None else "(Vacío)")
            if selected_values is None:
                cb.setChecked(True)
            else:
                cb.setChecked(val in selected_values)
            self.list_widget.setItemWidget(item, cb)
            self.items.append((val, cb))

    def toggle_all(self, state):
        for _, cb in self.items:
            cb.setChecked(state == Qt.CheckState.Checked.value)

    def filter_list(self, text):
        for val, cb in self.items:
            item = self.list_widget.item(self.items.index((val, cb)))
            item.setHidden(text.lower() not in str(val).lower())

    def on_sort(self, order):
        self.sort_requested.emit(order)
        self.close()

    def apply_filter(self):
        selected = [val for val, cb in self.items if cb.isChecked()]
        self.filter_requested.emit(selected)
        self.close()

    def show_at(self, pos):
        self.show() # Show first to get correct size

        # Adjust position to stay on screen
        screen = self.screen().availableGeometry()
        size = self.sizeHint()

        x = pos.x()
        y = pos.y()

        if x + size.width() > screen.right():
            x = screen.right() - size.width()

        if y + size.height() > screen.bottom():
            y = screen.bottom() - size.height()

        if x < screen.left():
            x = screen.left()
        if y < screen.top():
            y = screen.top()

        self.move(x, y)
        self.search_box.setFocus()
