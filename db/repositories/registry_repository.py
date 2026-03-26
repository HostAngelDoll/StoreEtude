from .base_repository import BaseRepository

class RegistryRepository(BaseRepository):
    def insert_registry(self, data):
        sql = """
            INSERT INTO T_Registry (
                title_material, datetime_range_utc_06, type_repeat,
                type_listen, model_writer, lapsed_calculated,
                opener_model, name_of_opener_model
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_query(sql, data)

    def insert_many_registries(self, registries):
        # We perform individual inserts through execute_query for simplicity
        # but in a production environment we'd use a bulk method.
        success_count = 0
        for r in registries:
            if self.insert_registry(r):
                success_count += 1
        return success_count

    def clear_registries(self):
        return self.execute_query("DELETE FROM T_Registry")

    def count_registries(self):
        query = self.execute_query("SELECT COUNT(*) FROM T_Registry")
        if query and query.next():
            return query.value(0)
        return 0

    def get_all_registries(self):
        return self.execute_query("SELECT idx, datetime_range_utc_06, model_writer FROM T_Registry")

    def update_registry_calculations(self, idx, lapsed, opener_model, name_of_opener_model):
        sql = """
            UPDATE T_Registry
            SET lapsed_calculated = ?, opener_model = ?, name_of_opener_model = ?
            WHERE idx = ?
        """
        return self.execute_query(sql, [lapsed, opener_model, name_of_opener_model, idx])
