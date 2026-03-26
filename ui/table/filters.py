from filter_widget import FilterMenu

class TableFilter:
    def __init__(self, table_tab):
        self.table_tab = table_tab

    def show_menu(self, col_index, pos):
        vals = set()
        for r in range(self.table_tab.model.rowCount()):
            vals.add(self.table_tab.model.data(self.table_tab.model.index(r, col_index)))
        menu = FilterMenu(list(vals), self.table_tab.filter_manager.active_filters.get(col_index), self.table_tab)
        menu.filter_requested.connect(lambda sel: self.table_tab.filter_manager.apply_filter(col_index, sel))
        menu.sort_requested.connect(lambda order: (self.table_tab.model.sort(col_index, order), self.table_tab.model.select()))
        menu.show_at(pos)
