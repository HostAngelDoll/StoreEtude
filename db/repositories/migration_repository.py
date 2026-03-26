from .base_repository import BaseRepository

class MigrationRepository(BaseRepository):
    def get_table_schema(self, table_name):
        query = self.execute_query(f"SELECT sql FROM sqlite_master WHERE type='table' AND name='{table_name}'")
        if query and query.next():
            return query.value(0)
        return None

    def get_columns_info(self, table_name):
        query = self.execute_query(f"PRAGMA table_info({table_name})")
        columns = []
        if query:
            while query.next():
                columns.append({
                    'name': query.value(1),
                    'type': query.value(2),
                    'notnull': bool(query.value(3)),
                    'pk': bool(query.value(5))
                })
        return columns

    def drop_table(self, table_name):
        return self.execute_query(f"DROP TABLE IF EXISTS {table_name}")

    def rename_table(self, old_name, new_name):
        return self.execute_query(f"ALTER TABLE {old_name} RENAME TO {new_name}")

    def reset_sequence(self, table_name):
        return self.execute_query(f"DELETE FROM sqlite_sequence WHERE name='{table_name}'")

    def create_table_from_sql(self, sql):
        return self.execute_query(sql)

    def copy_data_between_tables(self, from_table, to_table, columns, order_by=None):
        cols_str = ", ".join(columns)
        sql = f"INSERT INTO {to_table} ({cols_str}) SELECT {cols_str} FROM {from_table}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        return self.execute_query(sql)
