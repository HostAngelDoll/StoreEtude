from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QDateEdit,
                             QTableView, QPushButton, QTabWidget, QListWidget, QListWidgetItem,
                             QMessageBox, QDialogButtonBox, QWidget, QCheckBox, QAbstractItemView,
                             QApplication, QHeaderView)
from PyQt6.QtCore import Qt, QDate, QEvent
from PyQt6.QtGui import QIcon, QStandardItemModel, QStandardItem, QKeySequence
import os
from datetime import datetime
from config_manager import ConfigManager
from dialogs.common_delegates import (SpinoffDelegate, SeasonDelegate, TypeResourceDelegate,
                               TitleMaterialDelegate, CatalogDelegate)
from .journal_logic import JournalManager

class JournalForm(QDialog):
    def __init__(self, parent=None, journal_data=None):
        super().__init__(parent)
        self.table_name = "JournalMaterials"
        self.journal_data = journal_data or {}
        self.config = ConfigManager()
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.setWindowTitle("Añadir Jornada" if not journal_data else "Editar Jornada")
        self.resize(1100, 700)
        self.layout = QVBoxLayout(self)

        form_layout = QHBoxLayout()
        form_layout.addWidget(QLabel("Nombre de la jornada:"))
        self.name_edit = QLineEdit(self.journal_data.get('nombre', ''))
        form_layout.addWidget(self.name_edit)

        form_layout.addWidget(QLabel("Fecha esperada:"))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        date_str = self.journal_data.get('fecha_esperada', datetime.now().strftime("%Y-%m-%d"))
        self.date_edit.setDate(QDate.fromString(date_str, "yyyy-MM-dd"))
        form_layout.addWidget(self.date_edit)
        self.layout.addLayout(form_layout)

        self.model = QStandardItemModel(20, 8)
        self.model.setHorizontalHeaderLabels([
            "datetime_range_utc_06", "is_spinoff", "season", "type_resource",
            "title_material", "type_repeat", "type_listen", "model_writer"
        ])

        # Load existing materials if any
        materials = self.journal_data.get('materiales', [])
        for r, m in enumerate(materials):
            if r >= self.model.rowCount():
                self.model.appendRow([QStandardItem("") for _ in range(8)])
            self.model.setData(self.model.index(r, 0), m.get('datetime_range_utc_06', ''))
            is_spinoff = "Sí" if m.get('is_spinoff') == "Sí" or m.get('is_spinoff') == 1 else "No"
            self.model.setData(self.model.index(r, 1), is_spinoff)
            self.model.setData(self.model.index(r, 2), m.get('season', ''))
            self.model.setData(self.model.index(r, 3), m.get('type_resource', ''))
            self.model.setData(self.model.index(r, 4), m.get('title_material', ''))
            self.model.setData(self.model.index(r, 5), m.get('type_repeat', ''))
            self.model.setData(self.model.index(r, 6), m.get('type_listen', ''))
            self.model.setData(self.model.index(r, 7), m.get('model_writer', ''))

        self.view = QTableView()
        self.view.setModel(self.model)

        from ui.table.column_manager import ColumnHeaderView
        self.header = ColumnHeaderView(Qt.Orientation.Horizontal, self.view)
        self.view.setHorizontalHeader(self.header)

        self.view.setItemDelegateForColumn(1, SpinoffDelegate(self))
        self.view.setItemDelegateForColumn(2, SeasonDelegate(self))
        self.view.setItemDelegateForColumn(3, TypeResourceDelegate(self))
        self.view.setItemDelegateForColumn(4, TitleMaterialDelegate(self, allow_user_selection=True))
        self.view.setItemDelegateForColumn(5, CatalogDelegate("repeat", self))
        self.view.setItemDelegateForColumn(6, CatalogDelegate("listen", self))
        self.view.setItemDelegateForColumn(7, CatalogDelegate("write", self))

        self.layout.addWidget(QLabel("Materiales de la jornada:"))
        self.layout.addWidget(self.view)

        self.apply_column_configs()

        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_save = QPushButton("Guardar")
        self.btn_save.clicked.connect(lambda: self.process_save("guardado"))
        self.btn_borrador = QPushButton("Borrador")
        self.btn_borrador.clicked.connect(lambda: self.process_save("borrador"))
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_save)
        btn_layout.addWidget(self.btn_borrador)
        btn_layout.addWidget(self.btn_cancel)
        self.layout.addLayout(btn_layout)

        self.view.installEventFilter(self)

    def apply_column_configs(self):
        self.header._is_applying_config = True
        for i in range(self.model.columnCount()):
            col_name = self.model.headerData(i, Qt.Orientation.Horizontal)
            col_config = self.config.get_column_config(self.table_name, col_name)
            width = col_config.get("width")

            # Use Interactive to allow manual resizing as per user's bug report fix
            self.header.setSectionResizeMode(i, QHeaderView.ResizeMode.Interactive)
            if width:
                self.header.resizeSection(i, width)
        self.header.setStretchLastSection(True)
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

    def process_save(self, estado):
        nombre = self.name_edit.text().strip()
        if not nombre:
            QMessageBox.warning(self, "Error", "El nombre de la jornada es obligatorio.")
            return

        # Check for duplicates if it's a new journal or name changed
        mgr = JournalManager()
        existing = mgr.get_journal_by_name(nombre)
        if existing and existing.get('id') != self.journal_data.get('id'):
            res = QMessageBox.question(self, "Sobrescribir", f"Ya existe una jornada llamada '{nombre}'. ¿Deseas sobrescribirla?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if res == QMessageBox.StandardButton.No:
                return
            # If yes, we keep the ID of the existing one
            self.journal_data['id'] = existing['id']
            self.journal_data['created_at'] = existing.get('created_at')
            self.journal_data['vertion'] = existing.get('vertion', "1")

        self.journal_data['nombre'] = nombre
        self.journal_data['fecha_esperada'] = self.date_edit.date().toString("yyyy-MM-dd")
        self.journal_data['estado'] = estado

        materials_list = []
        for r in range(self.model.rowCount()):
            season = self.model.data(self.model.index(r, 2))
            title = self.model.data(self.model.index(r, 4))
            if not season or not title: continue

            materials_list.append({
                'datetime_range_utc_06': self.model.data(self.model.index(r, 0)) or "",
                'is_spinoff': self.model.data(self.model.index(r, 1)),
                'season': season,
                'type_resource': self.model.data(self.model.index(r, 3)) or "",
                'title_material': title,
                'type_repeat': self.model.data(self.model.index(r, 5)) or "",
                'type_listen': self.model.data(self.model.index(r, 6)) or "",
                'model_writer': self.model.data(self.model.index(r, 7)) or ""
            })

        self.journal_data['materiales'] = materials_list
        mgr.save_journal(self.journal_data)
        self.accept()

class JournalAdminDialog(QDialog):
    def __init__(self, parent=None, selection_mode=False):
        super().__init__(parent)
        self.selection_mode = selection_mode
        self.mgr = JournalManager()
        self.setWindowIcon(QIcon(os.path.join("img", "icon.ico")))
        self.setWindowTitle("Administrar Jornadas" if not selection_mode else "Seleccionar Jornadas para Importar")
        self.resize(800, 600)
        self.layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        self.tab_pendientes = QWidget()
        self.tab_borradores = QWidget()
        self.tab_vencidos = QWidget()

        self._init_tab_ui(self.tab_pendientes, "Pendientes")
        self._init_tab_ui(self.tab_borradores, "Borradores")
        self._init_tab_ui(self.tab_vencidos, "Vencidos")

        self.tabs.addTab(self.tab_pendientes, "Pendientes")
        self.tabs.addTab(self.tab_borradores, "Borradores")
        self.tabs.addTab(self.tab_vencidos, "Vencidos")

        self.layout.addWidget(self.tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        if not self.selection_mode:
            self.btn_add = QPushButton("Añadir")
            self.btn_add.clicked.connect(self.on_add)

            self.btn_toggle = QPushButton("Marcar como Borrador/Activo")
            self.btn_toggle.clicked.connect(self.on_toggle)
            self.btn_toggle.setEnabled(False)

            self.btn_edit = QPushButton("Editar")
            self.btn_edit.clicked.connect(self.on_edit)
            self.btn_edit.setEnabled(False)

            self.btn_delete = QPushButton("Eliminar")
            self.btn_delete.clicked.connect(self.on_delete)
            self.btn_delete.setEnabled(False)

            btn_layout.addWidget(self.btn_add)
            btn_layout.addWidget(self.btn_toggle)
            btn_layout.addWidget(self.btn_edit)
            btn_layout.addWidget(self.btn_delete)
        else:
            self.btn_import = QPushButton("Importar")
            self.btn_import.clicked.connect(self.accept)
            self.btn_import.setEnabled(False)

            self.btn_cancel = QPushButton("Cancelar")
            self.btn_cancel.clicked.connect(self.reject)

            btn_layout.addStretch()
            btn_layout.addWidget(self.btn_import)
            btn_layout.addWidget(self.btn_cancel)

        self.layout.addLayout(btn_layout)

        self.refresh_lists()
        self.tabs.currentChanged.connect(self.update_button_states)

    def _init_tab_ui(self, tab, name):
        layout = QVBoxLayout(tab)
        list_widget = QListWidget()
        list_widget.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        list_widget.itemSelectionChanged.connect(self.update_button_states)
        list_widget.itemChanged.connect(self.update_button_states)
        list_widget.itemDoubleClicked.connect(self.on_edit)
        layout.addWidget(list_widget)
        setattr(self, f"list_{name.lower()}", list_widget)

    def refresh_lists(self):
        borradores, pendientes, vencidos = self.mgr.categorize_journals()

        self._fill_list(self.list_borradores, borradores)
        self._fill_list(self.list_pendientes, pendientes)
        self._fill_list(self.list_vencidos, vencidos)
        self.update_button_states()

    def _fill_list(self, list_widget, journals):
        list_widget.clear()
        for j in journals:
            fecha_str = j.get('fecha_esperada', "")
            try:
                dt = datetime.strptime(fecha_str, "%Y-%m-%d")
                # Requirement: [Fecha "dddd, yyyy-mm-dd] - [Nombre]
                display_name = f"[Fecha {dt.strftime('%A, %Y-%m-%d')}] - {j.get('nombre')}"
            except:
                display_name = f"[Fecha {fecha_str}] - {j.get('nombre')}"

            item = QListWidgetItem(display_name)
            item.setData(Qt.ItemDataRole.UserRole, j)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            list_widget.addItem(item)

    def update_button_states(self):
        current_list = self._get_current_list()
        selected_items = current_list.selectedItems()

        if not self.selection_mode:
            checked_items = self._get_checked_items(current_list)
            any_checked = len(checked_items) > 0

            # Requirement 14: botón editar deshabilitado si no hay selección
            self.btn_edit.setEnabled(len(selected_items) == 1)

            # toggle and delete apply to CHECKED items as per requirement 3.i
            # "los checkboxes serviran para administrarlos al presionar el boton 'eliminar' o 'marcar como borrador/activo'"
            self.btn_toggle.setEnabled(any_checked)
            self.btn_delete.setEnabled(any_checked)
        else:
            # In selection mode, check all tabs for any checked items to enable 'Importar'
            any_checked = False
            for list_widget in [self.list_pendientes, self.list_borradores, self.list_vencidos]:
                if any(list_widget.item(i).checkState() == Qt.CheckState.Checked for i in range(list_widget.count())):
                    any_checked = True
                    break
            self.btn_import.setEnabled(any_checked)

    def _get_current_list(self):
        idx = self.tabs.currentIndex()
        if idx == 0: return self.list_pendientes
        if idx == 1: return self.list_borradores
        return self.list_vencidos

    def _get_checked_items(self, list_widget):
        checked = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                checked.append(item)
        return checked

    def on_add(self):
        form = JournalForm(self)
        if form.exec() == QDialog.DialogCode.Accepted:
            self.refresh_lists()

    def on_edit(self):
        current_list = self._get_current_list()
        selected = current_list.selectedItems()
        if not selected: return

        journal_data = selected[0].data(Qt.ItemDataRole.UserRole)
        form = JournalForm(self, journal_data)
        if form.exec() == QDialog.DialogCode.Accepted:
            self.refresh_lists()

    def on_toggle(self):
        current_list = self._get_current_list()
        checked = self._get_checked_items(current_list)
        if not checked: return

        for item in checked:
            data = item.data(Qt.ItemDataRole.UserRole)
            self.mgr.toggle_state(data['id'])

        self.refresh_lists()

    def get_selected_journals_data(self):
        selected_data = []
        for list_widget in [self.list_pendientes, self.list_borradores, self.list_vencidos]:
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item.checkState() == Qt.CheckState.Checked:
                    selected_data.append(item.data(Qt.ItemDataRole.UserRole))
        return selected_data

    def on_delete(self):
        current_list = self._get_current_list()
        checked = self._get_checked_items(current_list)
        if not checked: return

        res = QMessageBox.question(self, "Eliminar", f"¿Estás seguro de que deseas eliminar {len(checked)} jornadas? Esta acción es permanente.",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if res == QMessageBox.StandardButton.Yes:
            for item in checked:
                data = item.data(Qt.ItemDataRole.UserRole)
                self.mgr.delete_journal(data['id'])
            self.refresh_lists()
