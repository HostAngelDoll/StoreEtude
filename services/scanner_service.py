import os
import re
import subprocess
from datetime import datetime

class ScannerService:
    def __init__(self, catalog_repo, resources_repo):
        self.catalog_repo = catalog_repo
        self.resources_repo = resources_repo
        self._cancel_requested = False

    def cancel(self): self._cancel_requested = True

    def get_file_duration(self, file_path):
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
            result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8').strip()
            seconds = float(result)
            return f"{int(seconds // 3600):02d}:{int((seconds % 3600) // 60):02d}:{int(seconds % 60):02d}"
        except: return None

    def clean_name(self, name): return re.sub(r'\d{4}-\d{2}-\d{2}', '', name)

    def is_valid_file(self, filename, allowed_exts=None):
        if filename.startswith('.') or filename.lower() in ['thumbs.db', 'desktop.ini']: return False
        return filename.lower().endswith(allowed_exts) if allowed_exts else True

    def scan_and_link_resources(self, base_dir, years, overwrite=True, progress_callback=None, log_callback=None, warning_callback=None):
        type_ids = self.catalog_repo.get_all_resource_types()

        for i, year in enumerate(years):
            if self._cancel_requested:
                if log_callback: log_callback("Escaneo cancelado.", True, "resources")
                break

            if progress_callback: progress_callback(i, len(years), f"Procesando año {year}...")
            if log_callback: log_callback(f"Escaneando recursos para el año {year}...", False, "resources")

            seasons_info = self.catalog_repo.get_seasons_by_year(year)
            if not seasons_info: continue

            master_path = os.path.join(base_dir, str(year), seasons_info[0]['path_master'] or "")
            if not os.path.exists(master_path): continue

            try:
                if log_callback: log_callback(f"--- Fase 1: Episodios de Temporada ({year}) ---", False, "resources")
                for s in [si for si in seasons_info if not si['is_spinoff']]:
                    if self._cancel_requested: break
                    self.process_season_episodes(master_path, type_ids, s, overwrite, False, log_callback, warning_callback)

                if log_callback: log_callback(f"--- Fase 2: Episodios Spinoff ({year}) ---", False, "resources")
                for s in [si for si in seasons_info if si['is_spinoff']]:
                    if self._cancel_requested: break
                    self.process_season_episodes(master_path, type_ids, s, overwrite, True, log_callback, warning_callback)

                if log_callback: log_callback(f"--- Fase 3: Películas y Especiales ({year}) ---", False, "resources")
                for s in seasons_info:
                    if self._cancel_requested: break
                    self.process_movies(master_path, type_ids, s, overwrite, log_callback)

                if log_callback: log_callback(f"--- Fase 4: Soundtracks y Letras ({year}) ---", False, "resources")
                if not self._cancel_requested:
                    self.process_soundtracks(master_path, type_ids, overwrite, log_callback)
            except Exception as e:
                if log_callback: log_callback(f"Error año {year}: {e}", True, "resources")
        return True

    def process_season_episodes(self, master_path, type_ids, season_info, overwrite, is_spinoff, log_callback, warning_callback):
        season_name = season_info['name']
        ep_total = season_info['ep_total']

        keyword = "spinoff" if is_spinoff else "_episodes"
        candidates = [os.path.join(master_path, item) for item in os.listdir(master_path) if os.path.isdir(os.path.join(master_path, item)) and keyword in item.lower()]

        def select_best(cands):
            if not cands: return None
            if len(cands) == 1: return cands[0]
            for c in cands:
                if c.lower().endswith(".s"): return c
            return sorted(cands)[0]

        target_folder = select_best(candidates)
        if target_folder:
            if log_callback: log_callback(f"Temporada: {season_name} -> Carpeta: {os.path.basename(target_folder)}", False, "resources")
            files = [f for f in os.listdir(target_folder) if self.is_valid_file(f, ('.mp4', '.mkv'))]

            now = datetime.now()
            is_active_season = False
            try:
                db_year_val = int(re.search(r'\d+', os.path.dirname(os.path.dirname(master_path))).group())
                if (now.year == db_year_val and now.month >= 2) or (now.year == db_year_val + 1 and now.month == 1):
                    is_active_season = True
            except: pass

            if len(files) != ep_total and ep_total > 0 and not is_active_season:
                if warning_callback: warning_callback("Advertencia", f"Temporada {season_name}: Se encontraron {len(files)} archivos, se esperaban {ep_total}.")

            self.link_season_files(target_folder, files, type_ids, overwrite, season_name, log_callback)
        else:
            if log_callback: log_callback(f"No se encontró carpeta para {keyword} en {season_name}.", True, "resources")

    def link_season_files(self, folder_path, files, type_ids, overwrite, season_name, log_callback):
        ep_type_id = type_ids.get("Episodio")
        ep_sp_type_id = type_ids.get("Ep Sp")

        rows = self.resources_repo.get_resources_by_season_and_type(season_name, [ep_type_id, ep_sp_type_id], overwrite)
        used_files = set()
        folder_name = os.path.basename(folder_path)

        for title, ep_num, ep_sp_num, t_mat in rows:
            target_num = ep_num if t_mat == ep_type_id else ep_sp_num
            if target_num is None: continue
            for f in files:
                if f in used_files: continue
                if re.search(rf'(?<!\d)0*{target_num}(?!\d)', self.clean_name(f)):
                    if log_callback: log_callback(f"Vinculando: {f} -> {title}", False, "resources")
                    full_p = os.path.join(folder_path, f)
                    duration = self.get_file_duration(full_p)
                    dt_str = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime('%Y-%m-%d %H:%M:%S')
                    self.resources_repo.update_resource_file_info(title, f"{folder_name}/{f}", duration, dt_str)
                    used_files.add(f)
                    break

    def process_movies(self, master_path, type_ids, season_info, overwrite, log_callback):
        season_name = season_info['name']
        movie_types = ["Pelicula Temp", "All Stars", "Cortometraje", "Espetaculo"]
        movie_type_ids = [type_ids.get(t) for t in movie_types if type_ids.get(t)]
        if not movie_type_ids: return

        movie_folders = [item for item in os.listdir(master_path) if os.path.isdir(os.path.join(master_path, item)) and any(kw in item.lower() for kw in ["e_movie", "all stars", "cortometraje", "espetaculo"])]
        movie_folders.sort()
        if not movie_folders: return

        records = self.resources_repo.get_movies_for_linking(movie_type_ids, season_name, overwrite)
        if not records: return

        if log_callback: log_callback(f"Vinculando {len(records)} películas/especiales for {season_name}...", False, "resources")
        for i in range(min(len(records), len(movie_folders))):
            if self._cancel_requested: break
            title, folder_name = records[i], movie_folders[i]
            folder_path = os.path.join(master_path, folder_name)
            files = [f for f in os.listdir(folder_path) if self.is_valid_file(f, ('.mp4', '.mkv'))]
            if files:
                f = files[0]
                full_p = os.path.join(folder_path, f)
                duration = self.get_file_duration(full_p)
                dt_str = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime('%Y-%m-%d %H:%M:%S')
                self.resources_repo.update_resource_file_info(title, f"{folder_name}/{f}", duration, dt_str)

    def process_soundtracks(self, master_path, type_ids, overwrite, log_callback):
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

        titles = [r[0] for r in self.resources_repo.get_resources_by_season_and_type(None, sd_type_ids, overwrite)] # Modified to get all

        for title in titles:
            if self._cancel_requested: break
            title = str(title).strip()
            found_sd = next((f for f in os.listdir(sd_folder) if self.is_valid_file(f) and os.path.splitext(f)[0].strip() == title and os.path.splitext(f)[1].lower() in ['.mp3', '.mp4', '.m4a']), None)
            found_ly = next((f for f in os.listdir(ly_folder) if self.is_valid_file(f) and os.path.splitext(f)[0].strip() == title), None) if ly_folder else None

            if found_sd:
                full_p = os.path.join(sd_folder, found_sd)
                duration = self.get_file_duration(full_p)
                dt_str = datetime.fromtimestamp(os.path.getmtime(full_p)).strftime('%Y-%m-%d %H:%M:%S')
                self.resources_repo.update_resource_soundtrack_info(title, f"{sd_folder_name}/{found_sd}", f"{ly_folder_name}/{found_ly}" if found_ly else None, duration, dt_str)
            elif overwrite:
                self.resources_repo.update_resource_file_info(title, None, None, None) # Clear file path
