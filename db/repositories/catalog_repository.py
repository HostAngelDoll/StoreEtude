from .base_repository import BaseRepository

class CatalogRepository(BaseRepository):
    def get_all_resource_types(self):
        query = self.execute_query("SELECT idx, type_resource FROM T_Type_Resources")
        types = {}
        if query:
            while query.next():
                types[query.value(1)] = query.value(0)
        return types

    def get_seasons_by_year(self, year):
        query = self.execute_query(
            "SELECT precure_season_name, is_spinoff, episode_total, path_master FROM T_Seasons WHERE year = ?",
            [year]
        )
        seasons = []
        if query:
            while query.next():
                seasons.append({
                    'name': query.value(0),
                    'is_spinoff': bool(query.value(1)),
                    'ep_total': query.value(2) or 0,
                    'path_master': query.value(3)
                })
        return seasons

    def get_all_season_names(self):
        query = self.execute_query("SELECT precure_season_name FROM T_Seasons")
        names = {}
        if query:
            while query.next():
                names[query.value(0)] = query.value(0)
        return names

    def get_year_by_season_name(self, season_name):
        query = self.execute_query("SELECT year FROM T_Seasons WHERE precure_season_name = ?", [season_name])
        if query and query.next():
            return query.value(0)
        return None

    def update_season_path_master(self, year, path_master):
        return self.execute_query(
            "UPDATE T_Seasons SET path_master = ? WHERE year = ?",
            [path_master, year]
        )

    def get_opener_model_info(self, date_str, writer_type):
        writer_type = str(writer_type).lower()
        if "overwrite" in writer_type:
            col_start = "start_validity_overwrite"
            col_end = "end_validity_overwrite"
            col_subname = "model_name_overwrite"
        elif "locally" in writer_type:
            col_start = "start_validity_locally"
            col_end = "end_validity_locally"
            col_subname = "model_name_locally"
        else:
            return None, None

        sql = f"""
            SELECT model_name, {col_subname}
            FROM T_Opener_Models
            WHERE ? >= {col_start} AND ? <= {col_end}
        """
        query = self.execute_query(sql, [date_str, date_str])
        if query and query.next():
            return query.value(0), query.value(1)
        return None, None
