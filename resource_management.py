import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal, QCoreApplication
from core.db_manager_utils import BASE_DIR_PATH, get_yearly_db_path, GLOBAL_DB_PATH

class ResourceScanner(QObject):
    progress_changed = pyqtSignal(int, int, str)
    log_message = pyqtSignal(str, bool, str)
    finished = pyqtSignal()
    warning_emitted = pyqtSignal(str, str) # title, message
    request_duplicate_action = pyqtSignal(str) # title_material. Handled by UI.

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

        conn_global = sqlite3.connect(GLOBAL_DB_PATH)
        cursor_global = conn_global.cursor()

        type_ids = {}
        cursor_global.execute("SELECT idx, type_resource FROM T_Type_Resources")
        for row in cursor_global.fetchall():
            type_ids[row[1]] = row[0]

        for i, year in enumerate(years):
            if self._cancel_requested:
                self.log_message.emit("Escaneo cancelado.", True, "resources")
                break

            self.progress_changed.emit(i, len(years), f"Procesando año {year}...")
            self.log_message.emit(f"Escaneando recursos para el año {year}...", False, "resources")

            seasons_info = []
            cursor_global.execute("SELECT precure_season_name, is_spinoff, episode_total, path_master FROM T_Seasons WHERE year = ?", (year,))
            for row in cursor_global.fetchall():
                seasons_info.append({
                    'name': row[0],
                    'is_spinoff': bool(row[1]),
                    'ep_total': row[2] or 0,
                    'path_master': row[3]
                })

            if not seasons_info: continue

            master_path = os.path.join(BASE_DIR_PATH, str(year), seasons_info[0]['path_master'] or "")
            if not os.path.exists(master_path): continue

            db_year_path = get_yearly_db_path(year)
            conn_year = sqlite3.connect(db_year_path)

            try:
                self.log_message.emit(f"--- Fase 1: Episodios de Temporada ({year}) ---", False, "resources")
                for s in [si for si in seasons_info if not si['is_spinoff']]:
                    if self._cancel_requested: break
                    self.process_season_episodes(conn_year, master_path, type_ids, s, overwrite, False)
                
                self.log_message.emit(f"--- Fase 2: Episodios Spinoff ({year}) ---", False, "resources")
                for s in [si for si in seasons_info if si['is_spinoff']]:
                    if self._cancel_requested: break
                    self.process_season_episodes(conn_year, master_path, type_ids, s, overwrite, True)
                
                self.log_message.emit(f"--- Fase 3: Películas y Especiales ({year}) ---", False, "resources")
                for s in seasons_info:
                    if self._cancel_requested: break
                    self.process_movies(conn_year, master_path, type_ids, s, overwrite)
                
                self.log_message.emit(f"--- Fase 4: Soundtracks y Letras ({year}) ---", False, "resources")
                if not self._cancel_requested:
                    self.process_soundtracks(conn_year, master_path, type_ids, overwrite)

                conn_year.commit()
            except Exception as e:
                self.log_message.emit(f"Error año {year}: {e}", True, "resources")
            finally:
                conn_year.close()

        conn_global.close()
        self.progress_changed.emit(len(years), len(years), "Escaneo completado.")
        self.finished.emit()

    def process_season_episodes(self, conn, master_path, type_ids, season_info, overwrite, is_spinoff=False):
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

            self.link_season_files(conn, target_folder, files, type_ids, overwrite, season_name)
        else:
            self.log_message.emit(f"No se encontró carpeta para {keyword} en {season_name}.", True, "resources")

    def link_season_files(self, conn, folder_path, files, type_ids, overwrite, season_name):
        ep_type_id = type_ids.get("Episodio")
        ep_sp_type_id = type_ids.get("Ep Sp")

        cursor = conn.cursor()
        sql = "SELECT title_material, ep_num, ep_sp_num, type_material FROM T_Resources WHERE precure_season_name = ? AND type_material IN (?, ?)"
        if not overwrite:
            sql += " AND (relative_path_of_file IS NULL OR relative_path_of_file = '')"

        cursor.execute(sql, (season_name, ep_type_id, ep_sp_type_id))
        rows = cursor.fetchall()

        updates = []
        used_files = set()
        folder_name = os.path.basename(folder_path)

        for row in rows:
            title = row[0]
            ep_num = row[1]
            ep_sp_num = row[2]
            t_mat = row[3]

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

            cursor.execute("UPDATE T_Resources SET relative_path_of_file = ?, duration_file = ?, datetime_download = ? WHERE title_material = ?",
                           (f"{folder_name}/{filename}", duration, dt_str, title))

    def process_movies(self, conn, master_path, type_ids, season_info, overwrite):
        season_name = season_info['name']
        movie_types = ["Pelicula Temp", "All Stars", "Cortometraje", "Espetaculo"]
        movie_type_ids = [type_ids.get(t) for t in movie_types if type_ids.get(t)]
        if not movie_type_ids: return

        movie_folders = []
        keywords = ["e_movie", "all stars", "cortometraje", "espetaculo"]
        for item in os.listdir(master_path):
            if os.path.isdir(p := os.path.join(master_path, item)) and any(kw in item.lower() for kw in keywords):
                movie_folders.append(item)
        movie_folders.sort()
        if not movie_folders: return

        cursor = conn.cursor()
        sql = f"SELECT title_material FROM T_Resources WHERE type_material IN ({','.join(['?']*len(movie_type_ids))}) AND precure_season_name = ?"
        if not overwrite:
            sql += " AND (relative_path_of_file IS NULL OR relative_path_of_file = '')"
        sql += " ORDER BY released_utc_09 ASC"

        cursor.execute(sql, (*movie_type_ids, season_name))
        records = [row[0] for row in cursor.fetchall()]
        if not records: return

        self.log_message.emit(f"Vinculando {len(records)} películas/especiales for {season_name}...", False, "resources")
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

                cursor.execute("UPDATE T_Resources SET relative_path_of_file = ?, duration_file = ?, datetime_download = ? WHERE title_material = ?",
                               (f"{folder_name}/{filename}", duration, dt_str, title))

    def scan_new_soundtracks_lyrics(self, years):
        if not os.path.exists(BASE_DIR_PATH): return

        conn_global = sqlite3.connect(GLOBAL_DB_PATH)
        cursor_global = conn_global.cursor()

        type_ids = {}
        cursor_global.execute("SELECT idx, type_resource FROM T_Type_Resources")
        for row in cursor_global.fetchall(): type_ids[row[1]] = row[0]

        sd_type_id = type_ids.get("Soundtrack")
        self._duplicate_choice = None
        self._apply_all_duplicate = False
        self._last_action = 0

        for i, year in enumerate(years):
            if self._cancel_requested: break
            self.progress_changed.emit(i, len(years), f"Procesando año {year}...")
            self.log_message.emit(f"Buscando nuevas soundtracks para el año {year}...", False, "resources")

            cursor_global.execute("SELECT precure_season_name, path_master FROM T_Seasons WHERE year = ? AND is_spinoff = 0", (year,))
            row = cursor_global.fetchone()
            if not row: continue
            season_name, path_master = row

            master_path = os.path.join(BASE_DIR_PATH, str(year), path_master or "")
            if not os.path.exists(master_path): continue

            sd_folder_name = ly_folder_name = None
            for item in os.listdir(master_path):
                if os.path.isdir(os.path.join(master_path, item)):
                    if "soundtrack" in item.lower(): sd_folder_name = item
                    elif "lyrics" in item.lower(): ly_folder_name = item
            if not sd_folder_name or not ly_folder_name: continue

            sd_folder = os.path.join(master_path, sd_folder_name)
            ly_folder = os.path.join(master_path, ly_folder_name)

            db_year_path = get_yearly_db_path(year)
            conn_year = sqlite3.connect(db_year_path)
            cursor_year = conn_year.cursor()

            try:
                sd_files = {os.path.splitext(f)[0]: f for f in os.listdir(sd_folder) if self.is_valid_file(f, ('.mp3', '.mp4', '.m4a'))}
                ly_files = {os.path.splitext(f)[0]: f for f in os.listdir(ly_folder) if self.is_valid_file(f)}
                common_names = set(sd_files.keys()) & set(ly_files.keys())

                for title in sorted(common_names):
                    if self._cancel_requested: break
                    cursor_year.execute("SELECT COUNT(*) FROM T_Resources WHERE title_material = ?", (title,))
                    exists = cursor_year.fetchone()[0] > 0
                    action = 0
                    if exists:
                        if self._apply_all_duplicate: action = self._last_action
                        else:
                            self._duplicate_choice = None
                            self.request_duplicate_action.emit(title)
                            while self._duplicate_choice is None:
                                time.sleep(0.01)
                                if self._cancel_requested: break
                            if self._duplicate_choice is None: break
                            action, self._apply_all_duplicate = self._duplicate_choice
                            self._last_action = action
                        if action == 0: continue

                    filename_sd = sd_files[title]; filename_ly = ly_files[title]
                    full_path_sd = os.path.join(sd_folder, filename_sd)
                    duration = self.get_file_duration(full_path_sd)
                    dt_str = datetime.fromtimestamp(os.path.getmtime(full_path_sd)).strftime('%Y-%m-%d %H:%M:%S')

                    if not exists:
                        cursor_year.execute("""
                            INSERT INTO T_Resources (
                                title_material, type_material, precure_season_name,
                                duration_file, datetime_download,
                                relative_path_of_soundtracks, relative_path_of_lyrics
                            ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (title, sd_type_id, season_name, duration, dt_str, f"{sd_folder_name}/{filename_sd}", f"{ly_folder_name}/{filename_ly}"))
                    else:
                        if action == 1:
                            cursor_year.execute("UPDATE T_Resources SET relative_path_of_soundtracks = ?, relative_path_of_lyrics = ? WHERE title_material = ?",
                                                (f"{sd_folder_name}/{filename_sd}", f"{ly_folder_name}/{filename_ly}", title))
                        elif action == 2:
                            cursor_year.execute("""
                                UPDATE T_Resources SET
                                    type_material = ?, precure_season_name = ?,
                                    duration_file = ?, datetime_download = ?,
                                    relative_path_of_soundtracks = ?, relative_path_of_lyrics = ?,
                                    relative_path_of_file = NULL
                                WHERE title_material = ?
                            """, (sd_type_id, season_name, duration, dt_str, f"{sd_folder_name}/{filename_sd}", f"{ly_folder_name}/{filename_ly}", title))

                conn_year.commit()
            except Exception as e:
                self.log_message.emit(f"Error año {year}: {e}", True, "resources")
            finally:
                conn_year.close()

        conn_global.close()
        self.progress_changed.emit(len(years), len(years), "Búsqueda completada.")
        self.finished.emit()

    def set_duplicate_choice(self, choice, apply_all):
        self._duplicate_choice = (choice, apply_all)

    def process_soundtracks(self, conn, master_path, type_ids, overwrite):
        sd_types = ["Soundtrack", "Soundtrack Sp"]
        sd_type_ids = [type_ids.get(t) for t in sd_types if type_ids.get(t)]
        if not sd_type_ids: return

        sd_folder_name = ly_folder_name = None
        for item in os.listdir(master_path):
            if os.path.isdir(os.path.join(master_path, item)):
                if "soundtrack" in item.lower(): sd_folder_name = item
                elif "lyrics" in item.lower(): ly_folder_name = item
        if not sd_folder_name: return

        sd_folder = os.path.join(master_path, sd_folder_name)
        ly_folder = os.path.join(master_path, ly_folder_name) if ly_folder_name else None

        cursor = conn.cursor()
        sql = f"SELECT title_material FROM T_Resources WHERE type_material IN ({','.join(['?']*len(sd_type_ids))})"
        if not overwrite:
            sql += " AND (relative_path_of_soundtracks IS NULL OR relative_path_of_soundtracks = '')"

        cursor.execute(sql, sd_type_ids)
        titles = [row[0] for row in cursor.fetchall()]

        for title in titles:
            if self._cancel_requested: break
            title = str(title).strip()
            found_sd = None
            for f in os.listdir(sd_folder):
                if not self.is_valid_file(f): continue
                base, ext = os.path.splitext(f)
                if base.strip() == title and ext.lower() in ['.mp3', '.mp4', '.m4a']:
                    found_sd = f; break

            found_ly = None
            if ly_folder and os.path.exists(ly_folder):
                for f in os.listdir(ly_folder):
                    if not self.is_valid_file(f): continue
                    base, ext = os.path.splitext(f)
                    if base.strip() == title: found_ly = f; break

            if found_sd:
                full_path = os.path.join(sd_folder, found_sd)
                duration = self.get_file_duration(full_path)
                dt_str = datetime.fromtimestamp(os.path.getmtime(full_path)).strftime('%Y-%m-%d %H:%M:%S')
                cursor.execute("UPDATE T_Resources SET relative_path_of_soundtracks = ?, relative_path_of_lyrics = ?, relative_path_of_file = NULL, duration_file = ?, datetime_download = ? WHERE title_material = ?",
                               (f"{sd_folder_name}/{found_sd}", f"{ly_folder_name}/{found_ly}" if found_ly else None, duration, dt_str, title))
            elif overwrite:
                cursor.execute("UPDATE T_Resources SET relative_path_of_file = NULL WHERE title_material = ?", (title,))
