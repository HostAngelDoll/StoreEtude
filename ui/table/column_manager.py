from PyQt6.QtWidgets import QHeaderView, QMenu, QApplication, QMainWindow
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor, QPalette
from config_manager import ConfigManager
from core.app_state import AppMode

class ColumnHeaderView(QHeaderView):
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setSectionsClickable(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self.filter_rects = {}
        self.sectionResized.connect(self.on_section_resized)
        self._is_applying_config = False

    def on_section_resized(self, logicalIndex, oldSize, newSize):
        if self._is_applying_config: return
        tab = self.get_table_tab()
        if tab and tab.model:
            col_name = tab.model.headerData(logicalIndex, Qt.Orientation.Horizontal)
            ConfigManager().set_column_config(tab.table_name, col_name, width=newSize)

    def get_table_tab(self):
        p = self.parent()
        while p:
            if hasattr(p, 'table_name') and hasattr(p, 'model'): return p
            p = p.parent()
        return None

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()
        from PyQt6.QtWidgets import QStyle, QStyleOptionHeader
        opt = QStyleOptionHeader()
        opt.rect = rect
        opt.section = logicalIndex
        opt.state = QStyle.StateFlag.State_Enabled
        self.style().drawControl(QStyle.ControlElement.CE_HeaderSection, opt, painter, self)

        text = self.model().headerData(logicalIndex, self.orientation(), Qt.ItemDataRole.DisplayRole)
        margin, btn_size = 4, 14
        text_rect = QRect(rect.left() + margin, rect.top(), rect.width() - btn_size - margin * 3, rect.height())
        self.style().drawItemText(painter, text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.palette(), True, str(text))

        btn_rect = QRect(rect.right() - btn_size - margin, rect.center().y() - btn_size//2, btn_size, btn_size)
        self.filter_rects[logicalIndex] = btn_rect
        is_dark = self.palette().window().color().lightness() < 128
        bg_color, text_color = (QColor(255, 255, 255, 60) if is_dark else QColor(0, 0, 0, 40)), (Qt.GlobalColor.white if is_dark else Qt.GlobalColor.black)
        painter.setBrush(bg_color)
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawRoundedRect(btn_rect, 2, 2)
        painter.setPen(text_color)
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, "▼")
        painter.restore()

    def mousePressEvent(self, event):
        logical_index = self.logicalIndexAt(event.pos())
        if logical_index in self.filter_rects and self.filter_rects[logical_index].contains(event.pos()):
            self.get_table_tab().show_filter_menu(logical_index, self.mapToGlobal(event.pos()))
            return
        super().mousePressEvent(event)

    def show_context_menu(self, pos):
        logical_index = self.logicalIndexAt(pos)
        if logical_index < 0: return
        tab = self.get_table_tab()
        col_name = tab.model.headerData(logical_index, Qt.Orientation.Horizontal)
        config = ConfigManager()
        is_locked = config.get_column_config(tab.table_name, col_name).locked

        menu = QMenu(self)
        add_l, add_r = menu.addAction("Agregar columna (izquierda)"), menu.addAction("Agregar columna (derecha)")
        rename_col, delete_col = menu.addAction("Renombrar columna"), menu.addAction("Eliminar columna")
        menu.addSeparator()
        lock_action = menu.addAction("Desbloquear Ancho" if is_locked else "Bloquear Ancho")
        menu.addSeparator()
        copy_name, copy_data = menu.addAction("Copiar nombre de esta columna"), menu.addAction("Copiar datos de esta columna")

        main_win = next((w for w in QApplication.topLevelWidgets() if isinstance(w, QMainWindow)), None)
        is_offline = main_win and getattr(main_win, 'state', None) and main_win.state.mode == AppMode.OFFLINE
        is_year_tab = getattr(tab, 'db_conn_name', None) == "year_db"

        from .table_view import DataTableTab
        if not isinstance(tab, DataTableTab):
            for a in [add_l, add_r, rename_col, delete_col]: a.setVisible(False)
        if is_year_tab and is_offline:
            for a in [add_l, add_r, rename_col, delete_col]: a.setEnabled(False)

        action = menu.exec(self.mapToGlobal(pos))
        if action == lock_action:
            config.set_column_config(tab.table_name, col_name, locked=not is_locked)
            tab.apply_column_configs()
        elif action == add_l: tab.add_column(logical_index)
        elif action == add_r: tab.add_column(logical_index + 1)
        elif action == rename_col: tab.rename_column(logical_index)
        elif action == delete_col: tab.delete_column(logical_index)
        elif action == copy_name: tab.copy_column_name(logical_index)
        elif action == copy_data: tab.copy_column_data(logical_index)
