import os
import re
import sqlite3
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from db_manager import BASE_DIR_PATH, get_yearly_db_path, GLOBAL_DB_PATH, get_opener_model_info_sqlite
from core.utils import calculate_lapsed

class DBOperations(QObject):
    progress_changed = pyqtSignal(int, int, str)
    log_message = pyqtSignal(str, bool, str)
    finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancel_requested = False

    def cancel(self): self._cancel_requested = True

    def scan_master_folders(self):
        if not os.path.exists(BASE_DIR_PATH):
            self.error_occurred.emit(f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return
        try:
            conn = sqlite3.connect(GLOBAL_DB_PATH)
            cursor = conn.cursor()
            updated_count = 0
            for year in range(2004, datetime.now().year + 1):
                year_path = os.path.join(BASE_DIR_PATH, str(year))
                if os.path.exists(year_path):
                    found_folder = None
                    try:
                        for item in os.listdir(year_path):
                            if "___" in item and os.path.isdir(os.path.join(year_path, item)):
                                found_folder = item; break
                    except: continue
                    if found_folder:
                        cursor.execute("UPDATE T_Seasons SET path_master = ? WHERE year = ?", (found_folder, year))
                        if cursor.rowcount > 0: updated_count += 1
            conn.commit(); conn.close()
            self.finished.emit(f"Se actualizaron {updated_count} filas en Temporadas.")
        except Exception as e: self.error_occurred.emit(f"Error scanning master folders: {e}")

    def process_materials_report(self, materials_list):
        try:
            conn_global = sqlite3.connect(GLOBAL_DB_PATH)
            cursor_global = conn_global.cursor()
            records_to_add = []
            for mat in materials_list:
                dt, season, title = mat['dt'], mat['season'], mat['title']
                type_repeat, type_listen, model_writer = mat['type_repeat'], mat['type_listen'], mat['model_writer']
                cursor_global.execute("SELECT year FROM T_Seasons WHERE precure_season_name = ?", (season,))
                row = cursor_global.fetchone()
                year = row[0] if row else None
                if not year: continue
                lapsed = calculate_lapsed(dt)
                op_model, op_name = get_opener_model_info_sqlite(dt, model_writer)
                records_to_add.append({'year': year, 'data': (title, dt, type_repeat, type_listen, model_writer, lapsed, op_model, op_name)})
            conn_global.close()
            if not records_to_add: return 0
            by_year = {}
            for rec in records_to_add: by_year.setdefault(rec['year'], []).append(rec['data'])
            success_count = 0
            for year, rows in by_year.items():
                db_path = get_yearly_db_path(year)
                if not os.path.exists(db_path): continue
                conn_year = sqlite3.connect(db_path)
                cursor_year = conn_year.cursor()
                cursor_year.execute("BEGIN TRANSACTION")
                cursor_year.executemany("INSERT INTO T_Registry (title_material, datetime_range_utc_06, type_repeat, type_listen, model_writer, lapsed_calculated, opener_model, name_of_opener_model) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", rows)
                success_count += cursor_year.rowcount
                conn_year.commit(); conn_year.close()
            return success_count
        except: return 0
