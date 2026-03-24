from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTableView,
                             QApplication, QDialogButtonBox, QMessageBox, QHeaderView)
from PyQt6.QtGui import QIcon, QStandardItemModel, QStandardItem, QKeySequence
from PyQt6.QtCore import Qt, QEvent
from datetime import datetime
import os
from config_manager import ConfigManager
from .common_delegates import (SpinoffDelegate, SeasonDelegate, TypeResourceDelegate,
                               TitleMaterialDelegate, CatalogDelegate)

class ReportMaterialsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.table_name = "ReportMaterials"
        self.config = ConfigManager()
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.setWindowTitle("Reportar Materiales Vistos")
        self.resize(1100, 600)
        self.layout = QVBoxLayout(self)

        self.model = QStandardItemModel(20, 8)
        self.model.setHorizontalHeaderLabels([
            "datetime_range_utc_06", "is_spinoff", "season", "type_resource",
            "title_material", "type_repeat", "type_listen", "model_writer"
        ])

        self.view = QTableView()
        self.view.setModel(self.model)
        from data_table import ColumnHeaderView
        self.header = ColumnHeaderView(Qt.Orientation.Horizontal, self.view)
        self.view.setHorizontalHeader(self.header)

        self.view.setItemDelegateForColumn(1, SpinoffDelegate(self))
        self.view.setItemDelegateForColumn(2, SeasonDelegate(self))
        self.view.setItemDelegateForColumn(3, TypeResourceDelegate(self))
        self.view.setItemDelegateForColumn(4, TitleMaterialDelegate(self))
        self.view.setItemDelegateForColumn(5, CatalogDelegate("repeat", self))
        self.view.setItemDelegateForColumn(6, CatalogDelegate("listen", self))
        self.view.setItemDelegateForColumn(7, CatalogDelegate("write", self))

        self.layout.addWidget(QLabel("Pega los datetimes en la primera columna. Las temporadas y materiales se filtrarán según tu selección."))
        self.layout.addWidget(self.view)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Agregar")
        self.buttons.accepted.connect(self.process_addition)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

        self.apply_column_configs()
        self.view.installEventFilter(self)

    def apply_column_configs(self):
        self.header._is_applying_config = True
        for i in range(self.model.columnCount()):
            col_name = self.model.headerData(i, Qt.Orientation.Horizontal)
            col_config = self.config.get_column_config(self.table_name, col_name)
            width = col_config.get("width")
            locked = col_config.get("locked", False)
            if locked:
                self.header.setSectionResizeMode(i, QHeaderView.ResizeMode.Fixed)
                self.header.resizeSection(i, width)
            else:
                self.header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
                if width: self.header.resizeSection(i, width)
        self.header._is_applying_config = False

    def eventFilter(self, source, event):
        if event.type() == QEvent.Type.KeyPress and event.matches(QKeySequence.StandardKey.Paste):
            self.handle_paste()
            return True
        return super().eventFilter(source, event)

    def handle_paste(self):
        index = self.view.currentIndex()
        if not index.isValid() or index.column() != 0: return
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text: return
        lines = text.splitlines()
        current_row = max(0, index.row())
        for i, line in enumerate(lines):
            row_to_fill = current_row + i
            if row_to_fill >= self.model.rowCount():
                self.model.appendRow([QStandardItem("") for _ in range(8)])
            self.model.setData(self.model.index(row_to_fill, 0), line.strip())

    def process_addition(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        from db_operations import DBOperations
        materials_list = []
        for r in range(self.model.rowCount()):
            dt = self.model.data(self.model.index(r, 0))
            season = self.model.data(self.model.index(r, 2))
            title = self.model.data(self.model.index(r, 4))
            if not dt or not season or not title: continue
            try:
                parts = str(dt).strip().split(' ')
                if len(parts) < 2: raise ValueError()
                datetime.strptime(parts[0], "%Y-%m-%d")
            except: continue
            materials_list.append({
                'dt': dt, 'season': season, 'title': title,
                'type_repeat': self.model.data(self.model.index(r, 5)),
                'type_listen': self.model.data(self.model.index(r, 6)),
                'model_writer': self.model.data(self.model.index(r, 7))
            })
        if not materials_list:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Advertencia", "No hay registros válidos para agregar.")
            return
        ops = DBOperations()
        success_count = ops.process_materials_report(materials_list)
        QApplication.restoreOverrideCursor()
        QMessageBox.information(self, "Éxito", f"Se agregaron {success_count} registros correctamente.")
        self.accept()
