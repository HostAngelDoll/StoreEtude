import os
import re
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtSql import QSqlDatabase, QSqlQuery
from db_manager import BASE_DIR_PATH, get_yearly_db_path, calculate_lapsed, get_opener_model_info

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

            conn_name = f"regen_idx_{year}"
            db = QSqlDatabase.addDatabase("QSQLITE", conn_name)
            db.setDatabaseName(db_path)
            if not db.open():
                self.log_message.emit(f"No se pudo abrir la DB del año {year}", True, "registry")
                continue

            try:
                q = QSqlQuery(db)
                columns = []
                q.exec("PRAGMA table_info(T_Registry)")
                while q.next():
                    col_name = q.value(1)
                    if col_name.lower() != "idx":
                        columns.append(col_name)

                if not columns:
                    self.log_message.emit(f"No se encontraron columnas en T_Registry para el año {year}", True, "registry")
                    q = None
                    db.close()
                    QSqlDatabase.removeDatabase(conn_name)
                    continue

                q.exec("SELECT sql FROM sqlite_master WHERE type='table' AND name='T_Registry'")
                if not q.next():
                    self.log_message.emit(f"No se encontró el esquema de T_Registry para el año {year}", True, "registry")
                    q = None
                    db.close()
                    QSqlDatabase.removeDatabase(conn_name)
                    continue

                original_sql = q.value(0)
                temp_sql = re.sub(r'\bT_Registry\b', 'T_Registry_temp', original_sql)

                db.transaction()
                q.exec("DROP TABLE IF EXISTS T_Registry_temp")
                if not q.exec(temp_sql):
                    raise Exception(f"Error creando tabla temporal: {q.lastError().text()}")

                cols_str = ", ".join(columns)
                insert_sql = f"INSERT INTO T_Registry_temp ({cols_str}) SELECT {cols_str} FROM T_Registry ORDER BY datetime_range_utc_06 ASC"
                if not q.exec(insert_sql):
                    raise Exception(f"Error insertando datos: {q.lastError().text()}")

                q.exec("DROP TABLE T_Registry")
                q.exec("ALTER TABLE T_Registry_temp RENAME TO T_Registry")
                q.exec("DELETE FROM sqlite_sequence WHERE name='T_Registry'")

                db.commit()
                total_processed += 1
                self.log_message.emit(f"Índice regenerado para el año {year}", False, "registry")
            except Exception as e:
                db.rollback()
                self.log_message.emit(f"Error en año {year}: {str(e)}", True, "registry")
            finally:
                q = None
                db.close()
                db = None
                QSqlDatabase.removeDatabase(conn_name)

        self.progress_changed.emit(len(years), len(years), "Finalizado.")
        self.finished.emit(f"Se procesaron {total_processed} años correctamente.")

    def recalculate_registry_lapses(self, db_conn_name):
        db = QSqlDatabase.database(db_conn_name)
        q = QSqlQuery(db)
        q.exec("SELECT idx, datetime_range_utc_06 FROM T_Registry")
        updates = []
        while q.next():
            idx = q.value(0)
            dt = q.value(1)
            lapsed = calculate_lapsed(dt)
            updates.append((lapsed, idx))

        for lapsed, idx in updates:
            upd = QSqlQuery(db)
            upd.prepare("UPDATE T_Registry SET lapsed_calculated = ? WHERE idx = ?")
            upd.addBindValue(lapsed); upd.addBindValue(idx)
            upd.exec()
        
        self.finished.emit("Lapsos recalculados.")

    def recalculate_registry_models(self, db_conn_name):
        db = QSqlDatabase.database(db_conn_name)
        q = QSqlQuery(db)
        q.exec("SELECT idx, datetime_range_utc_06, model_writer FROM T_Registry")
        updates = []
        while q.next():
            idx = q.value(0)
            dt = q.value(1)
            mw = q.value(2)
            op_model, op_name = get_opener_model_info(dt, mw)
            updates.append((op_model, op_name, idx))

        for op_m, op_n, idx in updates:
            upd = QSqlQuery(db)
            upd.prepare("UPDATE T_Registry SET opener_model = ?, name_of_opener_model = ? WHERE idx = ?")
            upd.addBindValue(op_m); upd.addBindValue(op_n); upd.addBindValue(idx)
            upd.exec()

        self.finished.emit("Modelos recalculados.")

    def scan_master_folders(self):
        if not os.path.exists(BASE_DIR_PATH):
            self.error_occurred.emit(f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return

        db = QSqlDatabase.database("global_db")
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
                    q = QSqlQuery(db)
                    q.prepare("UPDATE T_Seasons SET path_master = ? WHERE year = ?")
                    q.addBindValue(found_folder); q.addBindValue(year)
                    if q.exec(): updated_count += 1

        self.finished.emit(f"Se actualizaron {updated_count} filas en Temporadas.")

    def process_materials_report(self, materials_list):
        records_to_add = []
        for mat in materials_list:
            dt = mat['dt']
            season = mat['season']
            title = mat['title']
            type_repeat = mat['type_repeat']
            type_listen = mat['type_listen']
            model_writer = mat['model_writer']
            
            # Find year for this season
            db_global = QSqlDatabase.database("global_db")
            q = QSqlQuery(db_global)
            q.prepare("SELECT year FROM T_Seasons WHERE precure_season_name = ?")
            q.addBindValue(season)
            year = None
            if q.exec() and q.next():
                year = q.value(0)
            
            if not year: continue

            lapsed = calculate_lapsed(dt)
            op_model, op_name = get_opener_model_info(dt, model_writer)
            
            records_to_add.append({
                'year': year,
                'data': (title, dt, type_repeat, type_listen, model_writer, lapsed, op_model, op_name)
            })

        if not records_to_add:
            return 0

        # Group by year
        by_year = {}
        for rec in records_to_add:
            by_year.setdefault(rec['year'], []).append(rec['data'])

        success_count = 0
        for year, rows in by_year.items():
            db_path = get_yearly_db_path(year)
            if not os.path.exists(db_path): continue
            
            conn_name = f"report_db_{year}"
            db = QSqlDatabase.addDatabase("QSQLITE", conn_name)
            db.setDatabaseName(db_path)
            if not db.open(): continue
                
            query = QSqlQuery(db)
            db.transaction()
            for row in rows:
                query.prepare("""
                    INSERT INTO T_Registry (
                        title_material, datetime_range_utc_06, type_repeat,
                        type_listen, model_writer, lapsed_calculated,
                        opener_model, name_of_opener_model
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """)
                for val in row:
                    query.addBindValue(val)
                
                if query.exec():
                    success_count += 1
            
            db.commit()
            query = None
            db.close()
            db = None
            QSqlDatabase.removeDatabase(conn_name)

        return success_count
