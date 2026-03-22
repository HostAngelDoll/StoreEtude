import os
import openpyxl
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from PyQt6.QtSql import QSqlDatabase, QSqlQuery
from db_manager import BASE_DIR_PATH, get_yearly_db_path

class DataMigrator(QObject):
    progress_changed = pyqtSignal(int, int, str)  # current, total, label
    log_message = pyqtSignal(str, bool, str)      # message, is_error, target
    finished = pyqtSignal(int)
    error_occurred = pyqtSignal(str)
    request_confirmation = pyqtSignal(int, str) # year, message. To be handled by UI.

    def __init__(self):
        super().__init__()
        self._cancel_requested = False
        self._confirmation_result = None

    def cancel(self):
        self._cancel_requested = True

    def set_confirmation_result(self, result: bool):
        self._confirmation_result = result

    def migrate_resources(self):
        if not os.path.exists(BASE_DIR_PATH):
            self.error_occurred.emit(f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return

        years = list(range(2004, datetime.now().year + 1))
        total_migrated = 0
        type_res_map = {}
        seasons_map = {}

        db_global = QSqlDatabase.database("global_db")
        q = QSqlQuery(db_global)
        q.exec("SELECT idx, type_resource FROM T_Type_Resources")
        while q.next():
            type_res_map[q.value(1)] = q.value(0)

        q.exec("SELECT precure_season_name FROM T_Seasons")
        while q.next():
            seasons_map[q.value(0)] = q.value(0)

        for i, year in enumerate(years):
            if self._cancel_requested:
                self.log_message.emit("Migración cancelada por el usuario.", True, "resources")
                break

            self.progress_changed.emit(i, len(years), f"Procesando año {year}...")
            self.log_message.emit(f"Iniciando migración de recursos para el año {year}...", False, "resources")

            px = year - 2003
            px_str = f"{px:02d}"
            excel_path = os.path.join(BASE_DIR_PATH, str(year), f"{px_str}. identity_propeties", f"{px_str}. le_etude.overwrite.xlsx")

            if not os.path.exists(excel_path):
                continue

            try:
                wb = openpyxl.load_workbook(excel_path, data_only=True)
                if "material_list" not in wb.sheetnames:
                    continue

                sheet = wb["material_list"]
                db_year_conn_name = f"migration_db_{year}"
                db_year_path = get_yearly_db_path(year)

                db_year = QSqlDatabase.addDatabase("QSQLITE", db_year_conn_name)
                db_year.setDatabaseName(db_year_path)
                if not db_year.open(): continue

                existing_titles = set()
                q_titles = QSqlQuery(db_year)
                q_titles.exec("SELECT title_material FROM T_Resources")
                while q_titles.next():
                    existing_titles.add(q_titles.value(0))

                query = QSqlQuery(db_year)
                for row_idx in range(4, sheet.max_row + 1):
                    if self._cancel_requested: break

                    title_material = sheet.cell(row=row_idx, column=9).value
                    if not title_material: continue

                    base_title = str(title_material)
                    final_title = base_title
                    counter = 2
                    while final_title in existing_titles:
                        final_title = f"{base_title} ({counter})"
                        counter += 1

                    existing_titles.add(final_title)
                    type_mat_id = type_res_map.get(sheet.cell(row=row_idx, column=5).value)
                    season_name_fk = seasons_map.get(sheet.cell(row=row_idx, column=6).value)

                    query.prepare("""
                        INSERT INTO T_Resources (
                            title_material, type_material, precure_season_name, ep_num, ep_sp_num,
                            released_utc_09, released_soundtrack_utc_09, released_spinoff_utc_09,
                            duration_file, datetime_download, relative_path_of_file,
                            relative_path_of_soundtracks, relative_path_of_lyrics
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """)
                    query.addBindValue(final_title)
                    query.addBindValue(type_mat_id)
                    query.addBindValue(season_name_fk)
                    query.addBindValue(sheet.cell(row=row_idx, column=7).value)
                    query.addBindValue(sheet.cell(row=row_idx, column=8).value)
                    query.addBindValue(str(sheet.cell(row=row_idx, column=10).value or ""))
                    query.addBindValue(str(sheet.cell(row=row_idx, column=11).value or ""))
                    query.addBindValue(str(sheet.cell(row=row_idx, column=12).value or ""))
                    query.addBindValue(str(sheet.cell(row=row_idx, column=13).value or ""))
                    query.addBindValue(str(sheet.cell(row=row_idx, column=14).value or ""))
                    query.addBindValue(str(sheet.cell(row=row_idx, column=15).value or ""))
                    query.addBindValue(None); query.addBindValue(None)

                    if query.exec():
                        total_migrated += 1
                        self.log_message.emit(f"Migrado recurso: {final_title}", False, "resources")
                    else:
                        self.log_message.emit(f"Error al migrar recurso {final_title}: {query.lastError().text()}", True, "resources")

                db_year.close()
                QSqlDatabase.removeDatabase(db_year_conn_name)
            except Exception as e:
                self.log_message.emit(f"Error procesando {excel_path}: {e}", True, "resources")

        self.progress_changed.emit(len(years), len(years), "Finalizado.")
        self.finished.emit(total_migrated)

    def migrate_registry(self):
        from db_manager import calculate_lapsed, get_opener_model_info
        if not os.path.exists(BASE_DIR_PATH):
            self.error_occurred.emit(f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return

        years = list(range(2004, datetime.now().year + 1))
        total_migrated = 0
        for i, year in enumerate(years):
            if self._cancel_requested: break

            self.progress_changed.emit(i, len(years), f"Procesando año {year}...")
            self.log_message.emit(f"Iniciando migración de registros para el año {year}...", False, "registry")

            px = year - 2003
            px_str = f"{px:02d}"
            excel_path = os.path.join(BASE_DIR_PATH, str(year), f"{px_str}. identity_propeties", f"{px_str}. le_etude.overwrite.xlsx")
            if not os.path.exists(excel_path): continue

            try:
                wb = openpyxl.load_workbook(excel_path, data_only=True)
                if "overwrite_registry" not in wb.sheetnames: continue
                sheet = wb["overwrite_registry"]

                db_year_conn_name = f"registry_mig_{year}"
                db_year_path = get_yearly_db_path(year)
                db_year = QSqlDatabase.addDatabase("QSQLITE", db_year_conn_name)
                db_year.setDatabaseName(db_year_path)
                if not db_year.open(): continue

                # Check if table has data
                q_check = QSqlQuery(db_year)
                q_check.exec("SELECT COUNT(*) FROM T_Registry")
                has_data = q_check.next() and q_check.value(0) > 0

                if has_data:
                    self._confirmation_result = None
                    self.request_confirmation.emit(year, f"La tabla T_Registry del año {year} contiene datos. ¿Desea borrarlos y migrar?")

                    import time
                    from PyQt6.QtCore import QCoreApplication
                    while self._confirmation_result is None:
                        QCoreApplication.processEvents()
                        time.sleep(0.01)
                        if self._cancel_requested: break

                    if not self._confirmation_result:
                        db_year.close()
                        QSqlDatabase.removeDatabase(db_year_conn_name)
                        continue

                QSqlQuery(db_year).exec("DELETE FROM T_Registry")

                query = QSqlQuery(db_year)
                for row_idx in range(4, sheet.max_row + 1):
                    if self._cancel_requested: break
                    title_material = sheet.cell(row=row_idx, column=11).value
                    if not title_material: continue

                    dt_range = sheet.cell(row=row_idx, column=12).value
                    type_repeat = sheet.cell(row=row_idx, column=13).value
                    type_listen = sheet.cell(row=row_idx, column=14).value
                    model_writer = sheet.cell(row=row_idx, column=15).value

                    lapsed = calculate_lapsed(dt_range)
                    op_model, op_name = get_opener_model_info(dt_range, model_writer)

                    query.prepare("""
                        INSERT INTO T_Registry (
                            title_material, datetime_range_utc_06, type_repeat,
                            type_listen, model_writer, lapsed_calculated,
                            opener_model, name_of_opener_model
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """)
                    query.addBindValue(title_material)
                    query.addBindValue(str(dt_range or ""))
                    query.addBindValue(str(type_repeat or ""))
                    query.addBindValue(str(type_listen or ""))
                    query.addBindValue(str(model_writer or ""))
                    query.addBindValue(lapsed)
                    query.addBindValue(op_model)
                    query.addBindValue(op_name)

                    if query.exec():
                        total_migrated += 1
                        self.log_message.emit(f"Migrado registro: {title_material} ({dt_range})", False, "registry")
                    else:
                        self.log_message.emit(f"Error al migrar registro {title_material}: {query.lastError().text()}", True, "registry")

                db_year.close()
                QSqlDatabase.removeDatabase(db_year_conn_name)
            except Exception as e:
                self.log_message.emit(f"Error registry {year}: {e}", True, "registry")

        self.progress_changed.emit(len(years), len(years), "Finalizado.")
        self.finished.emit(total_migrated)
