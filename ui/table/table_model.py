from PyQt6.QtSql import QSqlTableModel, QSqlRelationalTableModel, QSqlRelation, QSqlQuery
from PyQt6.QtCore import Qt

def create_table_model(db_conn_name, table_name, parent=None):
    from PyQt6.QtSql import QSqlDatabase
    db = QSqlDatabase.database(db_conn_name)
    if table_name == "T_Resources" and db_conn_name == "year_db":
        model = QSqlRelationalTableModel(parent, db)
        model.setTable(table_name)
        model.setRelation(1, QSqlRelation("T_Type_Resources", "idx", "type_resource"))
        model.setRelation(2, QSqlRelation("T_Seasons", "precure_season_name", "precure_season_name"))
    else:
        model = QSqlTableModel(parent, db)
        model.setTable(table_name)
    model.setEditStrategy(QSqlTableModel.EditStrategy.OnManualSubmit)
    model.select()
    return model

class FilterManager:
    def __init__(self, model, table_name):
        self.model = model
        self.table_name = table_name
        self.active_filters = {}

    def apply_filter(self, col_index, selected_values):
        self.active_filters[col_index] = selected_values
        parts = []
        for col, values in self.active_filters.items():
            field = self.model.record().fieldName(col)
            escaped, has_null = [], False
            for v in values:
                if v is None: has_null = True
                else: escaped.append(f"'{str(v).replace('\'', '\'\'')}'")
            if not escaped and not has_null: parts.append("1=0")
            else:
                conds = []
                if escaped: conds.append(f'"{field}" IN ({", ".join(escaped)})')
                if has_null: conds.append(f'"{field}" IS NULL OR "{field}" = ""')
                parts.append(f"({' OR '.join(conds)})")
        self.model.setFilter(" AND ".join(parts))
        self.model.select()
