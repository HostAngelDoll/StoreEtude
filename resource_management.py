import os
import re
import subprocess
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal, QCoreApplication
from PyQt6.QtSql import QSqlDatabase, QSqlQuery
from db_manager import BASE_DIR_PATH, get_yearly_db_path

class ResourceScanner(QObject):
    progress_changed = pyqtSignal(int, int, str)
    log_message = pyqtSignal(str, bool, str)
    finished = pyqtSignal()
    warning_emitted = pyqtSignal(str, str) # title, message

    def __init__(self):
        super().__init__()
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def get_file_duration(self, file_path):
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
            result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8').strip()
            seconds = float(result)
            return f"{int(seconds // 3600):02d}:{int((seconds % 3600) // 60):02d}:{int(seconds % 60):02d}"
        except:
            return None

    def clean_name(self, name):
        return re.sub(r'\d{4}-\d{2}-\d{2}', '', name)

    def is_valid_file(self, filename, allowed_exts=None):
        if filename.startswith('.') or filename.lower() in ['thumbs.db', 'desktop.ini']:
            return False
        return filename.lower().endswith(allowed_exts) if allowed_exts else True

    def scan_and_link_resources(self, years, overwrite=True):
        if not os.path.exists(BASE_DIR_PATH):
            return

        db_global = QSqlDatabase.database("global_db")
        type_ids = {}
        q = QSqlQuery(db_global)
        q.exec("SELECT idx, type_resource FROM T_Type_Resources")
        while q.next():
            type_ids[q.value(1)] = q.value(0)

        for i, year in enumerate(years):
            if self._cancel_requested:
                self.log_message.emit("Escaneo cancelado.", True, "resources")
                break

            self.progress_changed.emit(i, len(years), f"Procesando año {year}...")
            self.log_message.emit(f"Escaneando recursos para el año {year}...", False, "resources")

            seasons_info = []
            sq = QSqlQuery(db_global)
            sq.prepare("SELECT precure_season_name, is_spinoff, episode_total, path_master FROM T_Seasons WHERE year = ?")
            sq.addBindValue(year)
            if sq.exec():
                while sq.next():
                    seasons_info.append({
                        'name': sq.value(0),
                        'is_spinoff': bool(sq.value(1)),
                        'ep_total': sq.value(2) or 0,
                        'path_master': sq.value(3)
                    })

            if not seasons_info:
                continue

            master_path = os.path.join(BASE_DIR_PATH, str(year), seasons_info[0]['path_master'] or "")
            if not os.path.exists(master_path):
                continue

            db_year_conn = f"scan_db_{year}"
            db_year_path = get_yearly_db_path(year)
            db_year = QSqlDatabase.addDatabase("QSQLITE", db_year_conn)
            db_year.setDatabaseName(db_year_path)
            if not db_year.open():
                continue

            try:
                self.log_message.emit(f"--- Fase 1: Episodios de Temporada ({year}) ---", False, "resources")
                for s in [si for si in seasons_info if not si['is_spinoff']]:
                    if self._cancel_requested: break
                    self.process_season_episodes(db_year, master_path, type_ids, s, overwrite, False)
                
                self.log_message.emit(f"--- Fase 2: Episodios Spinoff ({year}) ---", False, "resources")
                for s in [si for si in seasons_info if si['is_spinoff']]:
                    if self._cancel_requested: break
                    self.process_season_episodes(db_year, master_path, type_ids, s, overwrite, True)
                
                self.log_message.emit(f"--- Fase 3: Películas y Especiales ({year}) ---", False, "resources")
                for s in seasons_info:
                    if self._cancel_requested: break
                    self.process_movies(db_year, master_path, type_ids, s, overwrite)
                
                self.log_message.emit(f"--- Fase 4: Soundtracks y Letras ({year}) ---", False, "resources")
                if not self._cancel_requested:
                    self.process_soundtracks(db_year, master_path, type_ids, overwrite)
            except Exception as e:
                self.log_message.emit(f"Error año {year}: {e}", True, "resources")
            finally:
                db_year.close()
                QSqlDatabase.removeDatabase(db_year_conn)

        self.progress_changed.emit(len(years), len(years), "Escaneo completado.")
        self.finished.emit()

    def process_season_episodes(self, db, master_path, type_ids, season_info, overwrite, is_spinoff=False):
        season_name = season_info['name']
        ep_total = season_info['ep_total']

        candidates = []
        keyword = "spinoff" if is_spinoff else "_episodes"
        for item in os.listdir(master_path):
            p = os.path.join(master_path, item)
            if os.path.isdir(p) and keyword in item.lower():
                candidates.append(p)

        def select_best(cands):
            if not cands: return None
            if len(cands) == 1: return cands[0]
            for c in cands:
                if c.lower().endswith(".s"):
                    return c
            return sorted(cands)[0]

        target_folder = select_best(candidates)
        if target_folder:
            self.log_message.emit(f"Temporada: {season_name} -> Carpeta: {os.path.basename(target_folder)}", False, "resources")
            files = [f for f in os.listdir(target_folder) if self.is_valid_file(f, ('.mp4', '.mkv'))]

            now = datetime.now()
            is_active_season = False
            try:
                db_year_val = int(re.search(r'\d+', os.path.dirname(os.path.dirname(master_path))).group())
                if (now.year == db_year_val and now.month >= 2) or (now.year == db_year_val + 1 and now.month == 1):
                    is_active_season = True
            except:
                pass

            if len(files) != ep_total and ep_total > 0 and not is_active_season:
                self.warning_emitted.emit("Advertencia", f"Temporada {season_name}: Se encontraron {len(files)} archivos, se esperaban {ep_total}.")

            self.link_season_files(db, target_folder, files, type_ids, overwrite, season_name)
        else:
            self.log_message.emit(f"No se encontró carpeta para {keyword} en {season_name}.", True, "resources")

    def link_season_files(self, db, folder_path, files, type_ids, overwrite, season_name):
        ep_type_id = type_ids.get("Episodio")
        ep_sp_type_id = type_ids.get("Ep Sp")

        query = QSqlQuery(db)
        sql = "SELECT title_material, ep_num, ep_sp_num, type_material FROM T_Resources WHERE precure_season_name = ? AND type_material IN (?, ?)"
        if not overwrite:
            sql += " AND (relative_path_of_file IS NULL OR relative_path_of_file = '')"

        query.prepare(sql)
        query.addBindValue(season_name)
        query.addBindValue(ep_type_id)
        query.addBindValue(ep_sp_type_id)
        if not query.exec():
            return

        updates = []
        used_files = set()
        folder_name = os.path.basename(folder_path)

        while query.next():
            title = query.value(0)
            ep_num = query.value(1)
            ep_sp_num = query.value(2)
            t_mat = query.value(3)

            target_num = ep_num if t_mat == ep_type_id else ep_sp_num
            if target_num is None:
                continue

            for f in files:
                if f in used_files:
                    continue
                if re.search(rf'(?<!\d)0*{target_num}(?!\d)', self.clean_name(f)):
                    updates.append((f, title))
                    used_files.add(f)
                    break

        for filename, title in updates:
            if self._cancel_requested: break
            self.log_message.emit(f"Vinculando: {filename} -> {title}", False, "resources")
            full_path = os.path.join(folder_path, filename)
            duration = self.get_file_duration(full_path)
            dt_str = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M:%S')

            upd = QSqlQuery(db)
            upd.prepare("UPDATE T_Resources SET relative_path_of_file = ?, duration_file = ?, datetime_download = ? WHERE title_material = ?")
            upd.addBindValue(f"{folder_name}/{filename}")
            upd.addBindValue(duration)
            upd.addBindValue(dt_str)
            upd.addBindValue(title)
            upd.exec()

    def process_movies(self, db, master_path, type_ids, season_info, overwrite):
        season_name = season_info['name']
        movie_types = ["Pelicula Temp", "All Stars", "Cortometraje", "Espetaculo"]
        movie_type_ids = [type_ids.get(t) for t in movie_types if type_ids.get(t)]
        if not movie_type_ids:
            return

        movie_folders = []
        keywords = ["e_movie", "all stars", "cortometraje", "espetaculo"]
        for item in os.listdir(master_path):
            if os.path.isdir(p := os.path.join(master_path, item)) and any(kw in item.lower() for kw in keywords):
                movie_folders.append(item)

        movie_folders.sort()
        if not movie_folders:
            return

        query = QSqlQuery(db)
        sql = f"SELECT title_material FROM T_Resources WHERE type_material IN ({','.join(['?']*len(movie_type_ids))}) AND precure_season_name = ?"
        if not overwrite:
            sql += " AND (relative_path_of_file IS NULL OR relative_path_of_file = '')"
        sql += " ORDER BY released_utc_09 ASC"

        query.prepare(sql)
        for tid in movie_type_ids:
            query.addBindValue(tid)
        query.addBindValue(season_name)
        if not query.exec():
            return

        records = []
        while query.next():
            records.append(query.value(0))

        if not records:
            return

        self.log_message.emit(f"Vinculando {len(records)} películas/especiales para {season_name}...", False, "resources")
        for i in range(min(len(records), len(movie_folders))):
            if self._cancel_requested: break
            title = records[i]
            folder_name = movie_folders[i]
            folder_path = os.path.join(master_path, folder_name)
            files = [f for f in os.listdir(folder_path) if self.is_valid_file(f, ('.mp4', '.mkv'))]

            if files:
                filename = files[0]
                full_path = os.path.join(folder_path, filename)
                duration = self.get_file_duration(full_path)
                dt_str = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M:%S')

                upd = QSqlQuery(db)
                upd.prepare("UPDATE T_Resources SET relative_path_of_file = ?, duration_file = ?, datetime_download = ? WHERE title_material = ?")
                upd.addBindValue(f"{folder_name}/{filename}")
                upd.addBindValue(duration)
                upd.addBindValue(dt_str)
                upd.addBindValue(title)
                upd.exec()

    def process_soundtracks(self, db, master_path, type_ids, overwrite):
        sd_types = ["Soundtrack", "Soundtrack Sp"]
        sd_type_ids = [type_ids.get(t) for t in sd_types if type_ids.get(t)]
        if not sd_type_ids:
            return

        sd_folder_name = None
        ly_folder_name = None
        for item in os.listdir(master_path):
            if os.path.isdir(os.path.join(master_path, item)):
                if "soundtrack" in item.lower():
                    sd_folder_name = item
                elif "lyrics" in item.lower():
                    ly_folder_name = item

        if not sd_folder_name:
            self.log_message.emit("Carpeta de soundtracks no encontrada.", True, "resources")
            return

        sd_folder = os.path.join(master_path, sd_folder_name)
        ly_folder = os.path.join(master_path, ly_folder_name) if ly_folder_name else None

        query = QSqlQuery(db)
        sql = f"SELECT title_material FROM T_Resources WHERE type_material IN ({','.join(['?']*len(sd_type_ids))})"
        if not overwrite:
            sql += " AND (relative_path_of_soundtracks IS NULL OR relative_path_of_soundtracks = '')"

        query.prepare(sql)
        for tid in sd_type_ids:
            query.addBindValue(tid)
        if not query.exec():
            return

        while query.next():
            if self._cancel_requested: break
            title = str(query.value(0)).strip()
            found_sd = None
            for f in os.listdir(sd_folder):
                if not self.is_valid_file(f):
                    continue
                base, ext = os.path.splitext(f)
                if base.strip() == title and ext.lower() in ['.mp3', '.mp4', '.m4a']:
                    found_sd = f
                    break

            found_ly = None
            if ly_folder and os.path.exists(ly_folder):
                for f in os.listdir(ly_folder):
                    if not self.is_valid_file(f):
                        continue
                    base, ext = os.path.splitext(f)
                    if base.strip() == title:
                        found_ly = f
                        break

            if found_sd:
                self.log_message.emit(f"Vinculando soundtrack: {found_sd}", False, "resources")
                full_path = os.path.join(sd_folder, found_sd)
                duration = self.get_file_duration(full_path)
                dt_str = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M:%S')

                upd = QSqlQuery(db)
                upd.prepare("UPDATE T_Resources SET relative_path_of_soundtracks = ?, relative_path_of_lyrics = ?, relative_path_of_file = NULL, duration_file = ?, datetime_download = ? WHERE title_material = ?")
                upd.addBindValue(f"{sd_folder_name}/{found_sd}")
                upd.addBindValue(f"{ly_folder_name}/{found_ly}" if found_ly else None)
                upd.addBindValue(duration)
                upd.addBindValue(dt_str)
                upd.addBindValue(title)
                upd.exec()
            elif overwrite:
                upd = QSqlQuery(db)
                upd.prepare("UPDATE T_Resources SET relative_path_of_file = NULL WHERE title_material = ?")
                upd.addBindValue(title)
                upd.exec()
