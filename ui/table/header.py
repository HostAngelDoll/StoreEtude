from PyQt6.QtWidgets import QHeaderView, QMenu, QApplication, QMainWindow, QStyle, QStyleOptionHeader
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QColor
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
        if self._is_applying_config:
            return

        table_tab = self.get_table_tab()
        if table_tab and table_tab.model:
            col_name = table_tab.model.headerData(logicalIndex, Qt.Orientation.Horizontal)
            from core.config_manager import ConfigManager
            config = ConfigManager()
            config.set_column_config(table_tab.table_name, col_name, width=newSize)

    def get_table_tab(self):
        p = self.parent()
        while p:
            if hasattr(p, 'table_name') and hasattr(p, 'model'):
                return p
            p = p.parent()
        return None

    def sectionSizeFromContents(self, logicalIndex):
        size = super().sectionSizeFromContents(logicalIndex)
        size.setWidth(size.width() + 20) # Space for filter button
        return size

    def sectionCountChanged(self, oldCount, newCount):
        self.filter_rects.clear()
        super().sectionCountChanged(oldCount, newCount)

    def paintSection(self, painter, rect, logicalIndex):
        painter.save()

        opt = QStyleOptionHeader()
        opt.rect = rect
        opt.section = logicalIndex
        opt.state = QStyle.StateFlag.State_Enabled
        self.style().drawControl(QStyle.ControlElement.CE_HeaderSection, opt, painter, self)

        text = self.model().headerData(logicalIndex, self.orientation(), Qt.ItemDataRole.DisplayRole)
        margin = 4
        btn_size = 14
        text_rect = QRect(rect.left() + margin, rect.top(), rect.width() - btn_size - margin * 3, rect.height())
        self.style().drawItemText(painter, text_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, self.palette(), True, str(text))

        btn_rect = QRect(rect.right() - btn_size - margin, rect.center().y() - btn_size//2, btn_size, btn_size)
        self.filter_rects[logicalIndex] = btn_rect

        is_dark = self.palette().window().color().lightness() < 128
        bg_color = QColor(255, 255, 255, 60) if is_dark else QColor(0, 0, 0, 40)
        text_color = Qt.GlobalColor.white if is_dark else Qt.GlobalColor.black

        painter.setBrush(bg_color)
        painter.setPen(Qt.GlobalColor.transparent)
        painter.drawRoundedRect(btn_rect, 2, 2)

        painter.setPen(text_color)
        painter.drawText(btn_rect, Qt.AlignmentFlag.AlignCenter, "▼")

        painter.restore()

    def mousePressEvent(self, event):
        logical_index = self.logicalIndexAt(event.pos())
        if logical_index in self.filter_rects and self.filter_rects[logical_index].contains(event.pos()):
            # Find the DataTableTab or whatever handles show_filter_menu
            table_tab = self.get_table_tab()
            if table_tab and hasattr(table_tab, 'show_filter_menu'):
                table_tab.show_filter_menu(logical_index, self.mapToGlobal(event.pos()))
                return
        super().mousePressEvent(event)

    def show_context_menu(self, pos):
        logical_index = self.logicalIndexAt(pos)
        if logical_index < 0:
            return

        table_tab = self.get_table_tab()
        col_name = table_tab.model.headerData(logical_index, Qt.Orientation.Horizontal)
        from core.config_manager import ConfigManager
        config = ConfigManager()
        col_config = config.get_column_config(table_tab.table_name, col_name)
        is_locked = col_config.get("locked", False)

        menu = QMenu(self)
        add_left = menu.addAction("Agregar columna (izquierda)")
        add_right = menu.addAction("Agregar columna (derecha)")
        rename_col = menu.addAction("Renombrar columna")
        delete_col = menu.addAction("Eliminar columna")
        menu.addSeparator()

        lock_action = menu.addAction("Desbloquear Ancho" if is_locked else "Bloquear Ancho")

        menu.addSeparator()
        copy_col_name = menu.addAction("Copiar nombre de esta columna")
        copy_col_data = menu.addAction("Copiar datos de esta columna")

        main_win = None
        for widget in QApplication.topLevelWidgets():
            if isinstance(widget, QMainWindow):
                main_win = widget
                break

        is_year_tab = getattr(table_tab, 'db_conn_name', None) == "year_db"
        is_offline = (main_win and getattr(main_win, 'state', None) and main_win.state.mode == AppMode.OFFLINE)

        # JournalForm and other non-DB forms should not allow schema changes
        # Use simple string check if DataTableTab is not importable due to circularity
        from ui.table.table_tab import DataTableTab
        is_db_tab = isinstance(table_tab, DataTableTab)
        if not is_db_tab:
            add_left.setVisible(False)
            add_right.setVisible(False)
            rename_col.setVisible(False)
            delete_col.setVisible(False)

        if is_year_tab and is_offline:
            add_left.setEnabled(False)
            add_right.setEnabled(False)
            rename_col.setEnabled(False)
            delete_col.setEnabled(False)

        action = menu.exec(self.mapToGlobal(pos))
        if not action:
            return

        if action == lock_action:
            config.set_column_config(table_tab.table_name, col_name, locked=not is_locked)
            table_tab.apply_column_configs()
            return

        if action == add_left:
            table_tab.add_column(logical_index)
        elif action == add_right:
            table_tab.add_column(logical_index + 1)
        elif action == rename_col:
            table_tab.rename_column(logical_index)
        elif action == delete_col:
            table_tab.delete_column(logical_index)
        elif action == copy_col_name:
            table_tab.copy_column_name(logical_index)
        elif action == copy_col_data:
            table_tab.copy_column_data(logical_index)
