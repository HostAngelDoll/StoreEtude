from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QDialogButtonBox)
from PyQt6.QtCore import Qt

class ChatSelectionDialog(QDialog):
    def __init__(self, chats, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Seleccionar Chat")
        self.resize(400, 500)
        self.layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for chat in chats:
            item = QListWidgetItem(chat['name'])
            item.setData(Qt.ItemDataRole.UserRole, chat)
            self.list_widget.addItem(item)

        self.layout.addWidget(self.list_widget)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_selected_chat(self):
        item = self.list_widget.currentItem()
        return item.data(Qt.ItemDataRole.UserRole) if item else None
