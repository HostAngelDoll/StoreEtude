from .base_repository import BaseRepository

class ResourcesRepository(BaseRepository):
    def insert_resource(self, data):
        sql = """
            INSERT INTO T_Resources (
                title_material, type_material, precure_season_name, ep_num, ep_sp_num,
                released_utc_09, released_soundtrack_utc_09, released_spinoff_utc_09,
                duration_file, datetime_download, relative_path_of_file,
                relative_path_of_soundtracks, relative_path_of_lyrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_query(sql, data)

    def insert_new_soundtrack(self, title, type_id, season_name, duration, dt_str, sd_path, ly_path):
        sql = """
            INSERT INTO T_Resources (
                title_material, type_material, precure_season_name,
                duration_file, datetime_download,
                relative_path_of_soundtracks, relative_path_of_lyrics
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        return self.execute_query(sql, [title, type_id, season_name, duration, dt_str, sd_path, ly_path])

    def update_resource_file_info(self, title, relative_path, duration, datetime_download):
        sql = """
            UPDATE T_Resources
            SET relative_path_of_file = ?, duration_file = ?, datetime_download = ?
            WHERE title_material = ?
        """
        return self.execute_query(sql, [relative_path, duration, datetime_download, title])

    def update_resource_soundtrack_info(self, title, sd_path, ly_path, duration=None, dt_str=None, type_id=None, season_name=None):
        if type_id and season_name:
             # Full upgrade from existing non-soundtrack resource
             sql = """
                UPDATE T_Resources SET
                    type_material = ?, precure_season_name = ?,
                    duration_file = ?, datetime_download = ?,
                    relative_path_of_soundtracks = ?, relative_path_of_lyrics = ?,
                    relative_path_of_file = NULL
                WHERE title_material = ?
            """
             return self.execute_query(sql, [type_id, season_name, duration, dt_str, sd_path, ly_path, title])
        else:
            # Simple link
            sql = """
                UPDATE T_Resources
                SET relative_path_of_soundtracks = ?, relative_path_of_lyrics = ?
                WHERE title_material = ?
            """
            return self.execute_query(sql, [sd_path, ly_path, title])

    def get_resources_by_season_and_type(self, season_name, type_ids, overwrite=True):
        sql = f"SELECT title_material, ep_num, ep_sp_num, type_material FROM T_Resources WHERE precure_season_name = ? AND type_material IN ({','.join(['?']*len(type_ids))})"
        if not overwrite:
            sql += " AND (relative_path_of_file IS NULL OR relative_path_of_file = '')"

        query = self.execute_query(sql, [season_name, *type_ids])
        results = []
        if query:
            while query.next():
                results.append((query.value(0), query.value(1), query.value(2), query.value(3)))
        return results

    def get_movies_for_linking(self, type_ids, season_name, overwrite=True):
        sql = f"SELECT title_material FROM T_Resources WHERE type_material IN ({','.join(['?']*len(type_ids))}) AND precure_season_name = ?"
        if not overwrite:
            sql += " AND (relative_path_of_file IS NULL OR relative_path_of_file = '')"
        sql += " ORDER BY released_utc_09 ASC"

        query = self.execute_query(sql, [*type_ids, season_name])
        results = []
        if query:
            while query.next():
                results.append(query.value(0))
        return results

    def get_all_titles(self):
        query = self.execute_query("SELECT title_material FROM T_Resources")
        titles = set()
        if query:
            while query.next():
                titles.add(query.value(0))
        return titles

    def check_resource_exists(self, title):
        query = self.execute_query("SELECT COUNT(*) FROM T_Resources WHERE title_material = ?", [title])
        if query and query.next():
            return query.value(0) > 0
        return False
