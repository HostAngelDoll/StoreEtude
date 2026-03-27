import os
import re
import sqlite3
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from core.db_manager_utils import (BASE_DIR_PATH, get_yearly_db_path, GLOBAL_DB_PATH,
                                     calculate_lapsed, get_opener_model_info_sqlite)

class DBOperations(QObject):
    progress_changed = pyqtSignal(int, int, str)
    log_message = pyqtSignal(str, bool, str)
    finished = pyqtSignal(str) # Message
    error_occurred = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def regenerate_registry_index(self, years):
        total_processed = 0
        for i, year in enumerate(years):
            if self._cancel_requested: break
            self.progress_changed.emit(i, len(years), f"Procesando año {year}...")
            self.log_message.emit(f"Regenerando índice de registros para el año {year}...", False, "registry")

            db_path = get_yearly_db_path(year)
            if not os.path.exists(db_path): continue

            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                columns = []
                cursor.execute("PRAGMA table_info(T_Registry)")
                for row in cursor.fetchall():
                    col_name = row[1]
                    if col_name.lower() != "idx":
                        columns.append(col_name)

                if not columns:
                    self.log_message.emit(f"No se encontraron columnas en T_Registry para el año {year}", True, "registry")
                    conn.close()
                    continue

                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='T_Registry'")
                row_sql = cursor.fetchone()
                if not row_sql:
                    self.log_message.emit(f"No se encontró el esquema de T_Registry para el año {year}", True, "registry")
                    conn.close()
                    continue

                original_sql = row_sql[0]
                temp_sql = re.sub(r'\bT_Registry\b', 'T_Registry_temp', original_sql)

                cursor.execute("BEGIN TRANSACTION")
                cursor.execute("DROP TABLE IF EXISTS T_Registry_temp")
                cursor.execute(temp_sql)

                cols_str = ", ".join(columns)
                insert_sql = f"INSERT INTO T_Registry_temp ({cols_str}) SELECT {cols_str} FROM T_Registry ORDER BY datetime_range_utc_06 ASC"
                cursor.execute(insert_sql)

                cursor.execute("DROP TABLE T_Registry")
                cursor.execute("ALTER TABLE T_Registry_temp RENAME TO T_Registry")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='T_Registry'")

                conn.commit()
                total_processed += 1
                self.log_message.emit(f"Índice regenerado para el año {year}", False, "registry")
                conn.close()
            except Exception as e:
                self.log_message.emit(f"Error en año {year}: {str(e)}", True, "registry")
                try: conn.rollback(); conn.close()
                except: pass

        self.progress_changed.emit(len(years), len(years), "Finalizado.")
        self.finished.emit(f"Se procesaron {total_processed} años correctamente.")

    def recalculate_registry_lapses(self, db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT idx, datetime_range_utc_06 FROM T_Registry")
            updates = []
            for row in cursor.fetchall():
                idx = row[0]
                dt = row[1]
                lapsed = calculate_lapsed(dt)
                updates.append((lapsed, idx))

            cursor.executemany("UPDATE T_Registry SET lapsed_calculated = ? WHERE idx = ?", updates)
            conn.commit()
            conn.close()
            self.finished.emit("Lapsos recalculados.")
        except Exception as e:
            self.error_occurred.emit(f"Error recalculating lapses: {e}")

    def recalculate_registry_models(self, db_path):
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT idx, datetime_range_utc_06, model_writer FROM T_Registry")
            updates = []
            for row in cursor.fetchall():
                idx = row[0]; dt = row[1]; mw = row[2]
                op_model, op_name = get_opener_model_info_sqlite(dt, mw)
                updates.append((op_model, op_name, idx))

            cursor.executemany("UPDATE T_Registry SET opener_model = ?, name_of_opener_model = ? WHERE idx = ?", updates)
            conn.commit()
            conn.close()
            self.finished.emit("Modelos recalculados.")
        except Exception as e:
            self.error_occurred.emit(f"Error recalculating models: {e}")

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
                        if cursor.rowcount > 0:
                            updated_count += 1

            conn.commit()
            conn.close()
            self.finished.emit(f"Se actualizaron {updated_count} filas en Temporadas.")
        except Exception as e:
            self.error_occurred.emit(f"Error scanning master folders: {e}")

    def process_materials_report(self, materials_list):
        try:
            conn_global = sqlite3.connect(GLOBAL_DB_PATH)
            cursor_global = conn_global.cursor()
            
            records_to_add = []
            for mat in materials_list:
                dt = mat['dt']; season = mat['season']; title = mat['title']
                type_repeat = mat['type_repeat']; type_listen = mat['type_listen']
                model_writer = mat['model_writer']

                cursor_global.execute("SELECT year FROM T_Seasons WHERE precure_season_name = ?", (season,))
                row = cursor_global.fetchone()
                year = row[0] if row else None
                if not year: continue

                lapsed = calculate_lapsed(dt)
                op_model, op_name = get_opener_model_info_sqlite(dt, model_writer)

                records_to_add.append({
                    'year': year,
                    'data': (title, dt, type_repeat, type_listen, model_writer, lapsed, op_model, op_name)
                })
            conn_global.close()

            if not records_to_add: return 0

            by_year = {}
            for rec in records_to_add:
                by_year.setdefault(rec['year'], []).append(rec['data'])

            success_count = 0
            for year, rows in by_year.items():
                db_path = get_yearly_db_path(year)
                if not os.path.exists(db_path): continue

                conn_year = sqlite3.connect(db_path)
                cursor_year = conn_year.cursor()
                cursor_year.execute("BEGIN TRANSACTION")
                
                cursor_year.executemany("""
                    INSERT INTO T_Registry (
                        title_material, datetime_range_utc_06, type_repeat,
                        type_listen, model_writer, lapsed_calculated,
                        opener_model, name_of_opener_model
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, rows)
                
                success_count += cursor_year.rowcount
                conn_year.commit()
                conn_year.close()

            return success_count
        except Exception as e:
            print(f"Error in process_materials_report: {e}")
            return 0
