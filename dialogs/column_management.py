from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QLabel, QTreeView, QDialogButtonBox,
                             QPushButton, QMessageBox)
from PyQt6.QtGui import QIcon, QStandardItemModel, QStandardItem
from PyQt6.QtCore import Qt
import os
from config_manager import ConfigManager

class ColumnManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.config = ConfigManager()
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.setWindowTitle("Gestión de Anchos de Columnas")
        self.resize(600, 400)
        self.layout = QVBoxLayout(self)

        self.tree = QTreeView()
        self.tree.setHeaderHidden(False)
        self.model = QStandardItemModel()
        self.model.setHorizontalHeaderLabels(["Elemento", "Ancho (px)", "Bloqueado"])

        self.load_data()
        self.tree.setModel(self.model)
        self.tree.expandAll()
        self.layout.addWidget(self.tree)

        self.btn_clear = QPushButton("Limpiar Todo")
        self.btn_clear.clicked.connect(self.clear_all)
        self.layout.addWidget(self.btn_clear)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.save_data)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def load_data(self):
        configs = self.config.get("ui.column_configs", {})
        root = self.model.invisibleRootItem()

        for table_name, columns in configs.items():
            table_item = QStandardItem(table_name)
            table_item.setEditable(False)

            for col_name, config in columns.items():
                col_item = QStandardItem(col_name)
                col_item.setEditable(False)

                width_item = QStandardItem(str(config.get("width", 100)))

                lock_item = QStandardItem()
                lock_item.setCheckable(True)
                lock_item.setCheckState(Qt.CheckState.Checked if config.get("locked", False) else Qt.CheckState.Unchecked)
                lock_item.setEditable(False)

                table_item.appendRow([col_item, width_item, lock_item])

            root.appendRow(table_item)

    def save_data(self):
        new_configs = {}
        root = self.model.invisibleRootItem()

        for i in range(root.rowCount()):
            table_item = root.child(i)
            table_name = table_item.text()
            new_configs[table_name] = {}

            for j in range(table_item.rowCount()):
                col_name = table_item.child(j, 0).text()
                try:
                    width = int(table_item.child(j, 1).text())
                except:
                    width = 100
                locked = table_item.child(j, 2).checkState() == Qt.CheckState.Checked

                new_configs[table_name][col_name] = {"width": width, "locked": locked}

        self.config.set("ui.column_configs", new_configs)
        self.accept()

    def clear_all(self):
        if QMessageBox.question(self, "Confirmar", "¿Seguro que quieres borrar todas las configuraciones de columnas?") == QMessageBox.StandardButton.Yes:
            self.model.clear()
            self.model.setHorizontalHeaderLabels(["Elemento", "Ancho (px)", "Bloqueado"])
            self.config.set("ui.column_configs", {})
            self.accept()
