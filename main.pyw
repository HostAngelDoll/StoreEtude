import sys
import os
import re
import sqlite3
import csv
import subprocess
import ctypes
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QTabWidget, QLabel, QHBoxLayout, QTreeView,
                             QDockWidget, QDialog, QMessageBox, QMenuBar, QMenu,
                             QProgressDialog)
from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QStandardItemModel, QStandardItem, QAction, QIcon
from PyQt6.QtSql import QSqlDatabase, QSqlQuery
import openpyxl

from db_manager import init_databases, GLOBAL_DB_PATH, get_yearly_db_path, BASE_DIR_PATH
from forms import DatabaseForm, YearRangeDialog, ReportMaterialsDialog
from data_table import DataTableTab

class PrecureManagerApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Precure Media Manager - Core System")
        self.setWindowIcon(QIcon("img\icon.ico"))
        self.settings = QSettings("MyCompany", "PrecureMediaManager")

        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.setGeometry(100, 100, 1200, 800)

        self.init_db_connections()
        self.init_actions()
        # Pre-load only non-UI dependent settings
        self.show_construction_logs.setChecked(self.settings.value("show_construction_logs", False, type=bool))

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        self.main_layout = QHBoxLayout(central_widget)

        self.init_sidebar()

        self.tabs = QTabWidget()
        self.main_layout.addWidget(self.tabs, 4)

        # Tabs initialization
        self.registry_tab = DataTableTab("year_db", "T_Registry")
        self.resources_tab = DataTableTab("year_db", "T_Resources")

        self.global_tab_container = QWidget()
        global_layout = QVBoxLayout(self.global_tab_container)
        self.global_subtabs = QTabWidget()

        self.catalog_tab = DataTableTab("global_db", "T_Type_Catalog_Reg")
        self.opener_tab = DataTableTab("global_db", "T_Opener_Models")
        self.type_res_tab = DataTableTab("global_db", "T_Type_Resources")
        self.seasons_tab = DataTableTab("global_db", "T_Seasons")

        self.global_subtabs.addTab(self.catalog_tab, "Catálogo")
        self.global_subtabs.addTab(self.opener_tab, "Modelos Opener")
        self.global_subtabs.addTab(self.type_res_tab, "Tipos Recursos")
        self.global_subtabs.addTab(self.seasons_tab, "Temporadas")
        global_layout.addWidget(self.global_subtabs)

        self.tabs.addTab(self.registry_tab, "Registros")
        self.tabs.addTab(self.resources_tab, "Recursos")
        self.tabs.addTab(self.global_tab_container, "Global")

        self.init_menu_bar()
        self.load_settings()

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

    def save_settings(self):
        self.settings.setValue("geometry", self.saveGeometry())
        self.settings.setValue("sidebar_visible", self.toggle_sidebar.isChecked())
        self.settings.setValue("console_visible", self.toggle_console.isChecked())
        self.settings.setValue("auto_resize", self.auto_resize_action.isChecked())
        self.settings.setValue("show_construction_logs", self.show_construction_logs.isChecked())

    def load_settings(self):
        sidebar_visible = self.settings.value("sidebar_visible", True, type=bool)
        self.toggle_sidebar.setChecked(sidebar_visible)
        self.dock.setVisible(sidebar_visible)

        console_visible = self.settings.value("console_visible", True, type=bool)
        self.toggle_console.setChecked(console_visible)
        self.toggle_sql_consoles()

        auto_resize = self.settings.value("auto_resize", True, type=bool)
        self.auto_resize_action.setChecked(auto_resize)
        self.set_auto_resize_columns(auto_resize)

        show_const_logs = self.settings.value("show_construction_logs", False, type=bool)
        self.show_construction_logs.setChecked(show_const_logs)

    def set_auto_resize_columns(self, enabled):
        for tab in [self.registry_tab, self.resources_tab, self.catalog_tab,
                    self.opener_tab, self.type_res_tab, self.seasons_tab]:
            tab.set_auto_resize(enabled)

    def init_actions(self):
        # Archivo
        self.save_action = QAction("Guardar", self)
        self.save_action.setShortcut("Ctrl+S")
        self.save_action.triggered.connect(self.save_current_tab)

        self.export_action = QAction("Exportar tabla a CSV", self)
        self.export_action.triggered.connect(self.export_active_tab_to_csv)

        self.import_action = QAction("Importar tabla desde CSV", self)
        self.import_action.triggered.connect(self.import_active_tab_from_csv)

        self.exit_action = QAction("Salir", self)
        self.exit_action.triggered.connect(self.close)

        # Edición
        self.add_row_action = QAction("Añadir fila", self)
        self.add_row_action.triggered.connect(self.on_add_row_requested)

        self.scan_masters_action = QAction("Escanear carpetas maestras", self)
        self.scan_masters_action.triggered.connect(self.scan_master_folders)

        self.migrate_resources_action = QAction("Migrar Recursos de años", self)
        self.migrate_resources_action.triggered.connect(self.migrate_resources_from_excel)

        self.migrate_registry_action = QAction("Migrar Registros de años", self)
        self.migrate_registry_action.triggered.connect(self.migrate_registry_from_excel)

        self.regen_index_action = QAction("Regenerar la columna index de registros", self)
        self.regen_index_action.triggered.connect(self.regenerate_registry_index)

        self.recalc_lapses_action = QAction("Recalcular Lapsos de rangos de registros", self)
        self.recalc_lapses_action.triggered.connect(self.recalculate_registry_lapses)

        self.recalc_models_action = QAction("Recalcular modelos detectados de registros", self)
        self.recalc_models_action.triggered.connect(self.recalculate_registry_models)

        self.update_links_action = QAction("Actualizar vinculación de archivos", self)
        self.update_links_action.triggered.connect(self.on_update_links_requested)

        # Herramientas
        self.scan_link_action = QAction("Escanear y vincular archivos", self)
        self.scan_link_action.triggered.connect(self.on_scan_link_requested)

        self.report_materials_action = QAction("Reportar Materiales Vistos", self)
        self.report_materials_action.triggered.connect(self.on_report_materials_requested)

        # Vista
        self.toggle_sidebar = QAction("Años", self, checkable=True)
        self.toggle_sidebar.setChecked(True)
        self.toggle_sidebar.triggered.connect(self.on_toggle_sidebar)

        self.toggle_console = QAction("Consola SQL", self, checkable=True)
        self.toggle_console.setChecked(True)
        self.toggle_console.triggered.connect(self.toggle_sql_consoles)

        self.show_construction_logs = QAction("Mostrar logs de construcción de tablas", self, checkable=True)
        self.show_construction_logs.setChecked(False)
        self.show_construction_logs.triggered.connect(self.save_settings)

        self.auto_resize_action = QAction("Auto-ajustar ancho de columnas", self, checkable=True)
        self.auto_resize_action.setChecked(True)
        self.auto_resize_action.triggered.connect(self.set_auto_resize_columns)

        # Ayuda
        self.about_action = QAction("Acerca de", self)
        self.about_action.triggered.connect(lambda: QMessageBox.information(self, "Ayuda", "Precure Media Manager v1.0"))

    def on_toggle_sidebar(self):
        if hasattr(self, 'dock'):
            self.dock.setVisible(self.toggle_sidebar.isChecked())
        self.save_settings()

    def init_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("Archivo")
        file_menu.addAction(self.save_action)
        file_menu.addAction(self.export_action)
        file_menu.addAction(self.import_action)
        file_menu.addAction(self.exit_action)

        edit_menu = menubar.addMenu("Edición")
        edit_menu.addAction(self.add_row_action)
        edit_menu.addAction(self.scan_masters_action)
        edit_menu.addAction(self.migrate_resources_action)
        edit_menu.addAction(self.migrate_registry_action)
        edit_menu.addAction(self.regen_index_action)
        edit_menu.addAction(self.recalc_lapses_action)
        edit_menu.addAction(self.recalc_models_action)
        edit_menu.addAction(self.update_links_action)

        tools_menu = menubar.addMenu("Herramientas")
        tools_menu.addAction(self.scan_link_action)
        tools_menu.addAction(self.report_materials_action)

        view_menu = menubar.addMenu("Vista")
        panels_submenu = view_menu.addMenu("Mostrar Paneles")
        panels_submenu.addAction(self.toggle_sidebar)
        panels_submenu.addAction(self.toggle_console)

        log_types_menu = view_menu.addMenu("Mostrar tipos de logs")
        log_types_menu.addAction(self.show_construction_logs)

        view_menu.addAction(self.auto_resize_action)

        help_menu = menubar.addMenu("Ayuda")
        help_menu.addAction(self.about_action)

    def save_current_tab(self):
        current_tab = self.get_active_data_tab()
        if current_tab:
            # Force commit of active editor
            if current_tab.view.currentIndex().isValid():
                current_tab.view.setEnabled(False)
                current_tab.view.setEnabled(True)
                current_tab.view.setFocus()

            if current_tab.model.submitAll():
                QMessageBox.information(self, "Guardar", "Cambios guardados correctamente.")
            else:
                QMessageBox.critical(self, "Error", f"No se pudo guardar: {current_tab.model.lastError().text()}")

    def export_active_tab_to_csv(self):
        current_tab = self.get_active_data_tab()
        if current_tab:
            current_tab.export_to_csv()

    def import_active_tab_from_csv(self):
        current_tab = self.get_active_data_tab()
        if current_tab:
            current_tab.import_from_csv()

    def get_active_data_tab(self):
        current_widget = self.tabs.currentWidget()
        if current_widget == self.global_tab_container:
            current_tab = self.global_subtabs.currentWidget()
        else:
            current_tab = current_widget

        if isinstance(current_tab, DataTableTab):
            return current_tab
        return None

    def on_add_row_requested(self):
        current_tab = self.get_active_data_tab()
        if current_tab:
            current_tab.add_record()

    def migrate_resources_from_excel(self):
        if not os.path.exists(BASE_DIR_PATH):
            QMessageBox.critical(self, "Error", f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return

        years = list(range(2004, datetime.now().year + 1))
        progress = QProgressDialog("Migrando recursos...", "Cancelar", 0, len(years), self)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

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
            progress.setValue(i)
            progress.setLabelText(f"Procesando año {year}...")
            self.log(f"Iniciando migración de recursos para el año {year}...", target="resources")
            QApplication.processEvents()

            if progress.wasCanceled():
                self.log("Migración cancelada por el usuario.", is_error=True)
                break

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
                        self.log(f"Migrado recurso: {final_title}", target="resources")
                    else:
                        self.log(f"Error al migrar recurso {final_title}: {query.lastError().text()}", is_error=True, target="resources")
                    QApplication.processEvents()

                db_year.close()
                QSqlDatabase.removeDatabase(db_year_conn_name)
            except Exception as e:
                print(f"Error processing {excel_path}: {e}")

        progress.setValue(len(years))
        self.resources_tab.model.select()
        if not progress.wasCanceled():
            QMessageBox.information(self, "Migración", f"Se migraron {total_migrated} recursos en total.")

    def migrate_registry_from_excel(self):
        if not os.path.exists(BASE_DIR_PATH):
            QMessageBox.critical(self, "Error", f"Ruta base {BASE_DIR_PATH} no encontrada.")
            return

        years = list(range(2004, datetime.now().year + 1))
        progress = QProgressDialog("Migrando registros...", "Cancelar", 0, len(years), self)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        total_migrated = 0
        for i, year in enumerate(years):
            progress.setValue(i)
            progress.setLabelText(f"Procesando año {year}...")
            self.log(f"Iniciando migración de registros para el año {year}...", target="registry")
            QApplication.processEvents()

            if progress.wasCanceled(): break

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
                    reply = QMessageBox.question(self, "Advertencia",
                        f"La tabla T_Registry del año {year} contiene datos. ¿Desea borrarlos y migrar? Se recomienda hacer un respaldo manual antes.",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if reply == QMessageBox.StandardButton.No:
                        db_year.close()
                        QSqlDatabase.removeDatabase(db_year_conn_name)
                        continue

                QSqlQuery(db_year).exec("DELETE FROM T_Registry")

                query = QSqlQuery(db_year)
                for row_idx in range(4, sheet.max_row + 1):
                    title_material = sheet.cell(row=row_idx, column=11).value
                    if not title_material: continue

                    dt_range = sheet.cell(row=row_idx, column=12).value
                    type_repeat = sheet.cell(row=row_idx, column=13).value
                    type_listen = sheet.cell(row=row_idx, column=14).value
                    model_writer = sheet.cell(row=row_idx, column=15).value

                    lapsed = self.calculate_lapsed(dt_range)
                    op_model, op_name = self.get_opener_model_info(dt_range, model_writer)

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
                        self.log(f"Migrado registro: {title_material} ({dt_range})", target="registry")
                    else:
                        self.log(f"Error al migrar registro {title_material}: {query.lastError().text()}", is_error=True, target="registry")
                    QApplication.processEvents()

                db_year.close()
                QSqlDatabase.removeDatabase(db_year_conn_name)
            except Exception as e:
                print(f"Error registry {year}: {e}")

        progress.setValue(len(years))
        self.registry_tab.model.select()
        QMessageBox.information(self, "Migración", f"Se migraron {total_migrated} registros en total.")

    def regenerate_registry_index(self):
        current_year = self.get_current_year()
        dialog = YearRangeDialog(current_year, self)
        dialog.setWindowTitle("Regenerar columna index")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        years = dialog.get_years(current_year)
        progress = QProgressDialog("Regenerando índices...", "Cancelar", 0, len(years), self)
        progress.setWindowTitle("Procesando años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        total_processed = 0
        for i, year in enumerate(years):
            progress.setValue(i)
            progress.setLabelText(f"Procesando año {year}...")
            self.log(f"Regenerando índice de registros para el año {year}...", target="registry")
            QApplication.processEvents()
            if progress.wasCanceled(): break

            db_path = get_yearly_db_path(year)
            if not os.path.exists(db_path): continue

            conn_name = f"regen_idx_{year}"
            db = QSqlDatabase.addDatabase("QSQLITE", conn_name)
            db.setDatabaseName(db_path)
            if not db.open():
                self.log(f"No se pudo abrir la DB del año {year}", is_error=True, target="registry")
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
                    self.log(f"No se encontraron columnas en T_Registry para el año {year}", is_error=True, target="registry")
                    db.close()
                    QSqlDatabase.removeDatabase(conn_name)
                    continue

                q.exec("SELECT sql FROM sqlite_master WHERE type='table' AND name='T_Registry'")
                if not q.next():
                    self.log(f"No se encontró el esquema de T_Registry para el año {year}", is_error=True, target="registry")
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
                self.log(f"Índice regenerado para el año {year}", target="registry")
            except Exception as e:
                db.rollback()
                self.log(f"Error en año {year}: {str(e)}", is_error=True, target="registry")
            finally:
                db.close()
                QSqlDatabase.removeDatabase(conn_name)

        progress.setValue(len(years))
        self.registry_tab.model.select()
        QMessageBox.information(self, "Regenerar Índice", f"Se procesaron {total_processed} años correctamente.")

    def recalculate_registry_lapses(self):
        db = QSqlDatabase.database("year_db")
        q = QSqlQuery(db)
        q.exec("SELECT idx, datetime_range_utc_06 FROM T_Registry")
        updates = []
        while q.next():
            idx = q.value(0)
            dt = q.value(1)
            lapsed = self.calculate_lapsed(dt)
            updates.append((lapsed, idx))

        for lapsed, idx in updates:
            upd = QSqlQuery(db)
            upd.prepare("UPDATE T_Registry SET lapsed_calculated = ? WHERE idx = ?")
            upd.addBindValue(lapsed); upd.addBindValue(idx)
            upd.exec()

        self.registry_tab.model.select()
        QMessageBox.information(self, "Lapsos", "Lapsos recalculados.")

    def recalculate_registry_models(self):
        db = QSqlDatabase.database("year_db")
        q = QSqlQuery(db)
        q.exec("SELECT idx, datetime_range_utc_06, model_writer FROM T_Registry")
        updates = []
        while q.next():
            idx = q.value(0)
            dt = q.value(1)
            mw = q.value(2)
            op_model, op_name = self.get_opener_model_info(dt, mw)
            updates.append((op_model, op_name, idx))

        for op_m, op_n, idx in updates:
            upd = QSqlQuery(db)
            upd.prepare("UPDATE T_Registry SET opener_model = ?, name_of_opener_model = ? WHERE idx = ?")
            upd.addBindValue(op_m); upd.addBindValue(op_n); upd.addBindValue(idx)
            upd.exec()

        self.registry_tab.model.select()
        QMessageBox.information(self, "Modelos", "Modelos recalculados.")

    def on_update_links_requested(self):
        year = self.get_current_year()
        self.scan_and_link_resources([year], overwrite=False)
        QMessageBox.information(self, "Vinculación", f"Proceso de actualización para el año {year} completado.")

    def on_scan_link_requested(self):
        current_year = self.get_current_year()
        dialog = YearRangeDialog(current_year, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            years = dialog.get_years(current_year)
            self.scan_and_link_resources(years, overwrite=True)
            QMessageBox.information(self, "Escaneo", "Proceso de escaneo y vinculación completado.")

    def on_report_materials_requested(self):
        dialog = ReportMaterialsDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            # Refresh registry if it's the active tab
            self.registry_tab.model.select()

    def scan_master_folders(self):
        if not os.path.exists(BASE_DIR_PATH):
            QMessageBox.critical(self, "Error", f"Ruta base {BASE_DIR_PATH} no encontrada.")
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

        self.seasons_tab.model.select()
        QMessageBox.information(self, "Escaneo", f"Se actualizaron {updated_count} filas en Temporadas.")

    def toggle_sql_consoles(self):
        is_visible = self.toggle_console.isChecked()
        self.registry_tab.set_console_visible(is_visible)
        self.resources_tab.set_console_visible(is_visible)
        self.catalog_tab.set_console_visible(is_visible)
        self.opener_tab.set_console_visible(is_visible)
        self.type_res_tab.set_console_visible(is_visible)
        self.seasons_tab.set_console_visible(is_visible)

    def init_db_connections(self):
        if not QSqlDatabase.contains("global_db"):
            db = QSqlDatabase.addDatabase("QSQLITE", "global_db")
            db.setDatabaseName(GLOBAL_DB_PATH)
            db.open()

        if not QSqlDatabase.contains("year_db"):
            db = QSqlDatabase.addDatabase("QSQLITE", "year_db")
            db.setDatabaseName(get_yearly_db_path(2004))
            if db.open():
                QSqlQuery(db).exec(f"ATTACH DATABASE '{GLOBAL_DB_PATH}' AS global_db")

    def init_sidebar(self):
        self.dock = QDockWidget("Años", self)
        self.dock.setFeatures(QDockWidget.DockWidgetFeature.DockWidgetMovable)
        self.year_tree = QTreeView()
        self.year_tree.setHeaderHidden(True)
        self.year_model = QStandardItemModel()
        root_node = self.year_model.invisibleRootItem()
        for year in range(2004, datetime.now().year + 1):
            item = QStandardItem(str(year))
            item.setEditable(False)
            root_node.appendRow(item)
        self.year_tree.setModel(self.year_model)
        self.year_tree.clicked.connect(self.on_year_selected)
        self.dock.setWidget(self.year_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self.dock)

    def on_year_selected(self, index):
        year = index.data()
        db_path = get_yearly_db_path(year)
        db = QSqlDatabase.database("year_db")
        db.close()
        db.setDatabaseName(db_path)
        if db.open():
            QSqlQuery(db).exec(f"ATTACH DATABASE '{GLOBAL_DB_PATH}' AS global_db")
            self.resources_tab.update_database("year_db")
            self.registry_tab.update_database("year_db")
        else:
            QMessageBox.critical(self, "Error", f"No se pudo abrir la base de datos del año {year}.")

    def get_current_year(self):
        index = self.year_tree.currentIndex()
        return int(index.data()) if index.isValid() else 2004

    def get_file_duration(self, file_path):
        try:
            cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', file_path]
            result = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode('utf-8').strip()
            seconds = float(result)
            return f"{int(seconds // 3600):02d}:{int((seconds % 3600) // 60):02d}:{int(seconds % 60):02d}"
        except:
            return None

    def scan_and_link_resources(self, years, overwrite=True):
        if not os.path.exists(BASE_DIR_PATH): return
        db_global = QSqlDatabase.database("global_db")
        type_ids = {}
        q = QSqlQuery(db_global)
        q.exec("SELECT idx, type_resource FROM T_Type_Resources")
        while q.next():
            type_ids[q.value(1)] = q.value(0)

        progress = QProgressDialog("Escaneando y vinculando recursos...", "Cancelar", 0, len(years), self)
        progress.setWindowTitle("Trabajando con años")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        for i, year in enumerate(years):
            progress.setValue(i)
            progress.setLabelText(f"Procesando año {year}...")
            self.log(f"Escaneando recursos para el año {year}...")
            QApplication.processEvents()
            if progress.wasCanceled():
                self.log("Escaneo cancelado.", is_error=True)
                break

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
                self.log(f"--- Fase 1: Episodios de Temporada ({year}) ---")
                for s in [si for si in seasons_info if not si['is_spinoff']]:
                    self.process_season_episodes(db_year, master_path, type_ids, s, overwrite, False)
                self.log(f"--- Fase 2: Episodios Spinoff ({year}) ---")
                for s in [si for si in seasons_info if si['is_spinoff']]:
                    self.process_season_episodes(db_year, master_path, type_ids, s, overwrite, True)
                self.log(f"--- Fase 3: Películas y Especiales ({year}) ---")
                for s in seasons_info:
                    self.process_movies(db_year, master_path, type_ids, s, overwrite)
                self.log(f"--- Fase 4: Soundtracks y Letras ({year}) ---")
                self.process_soundtracks(db_year, master_path, type_ids, overwrite)
            except Exception as e:
                print(f"Error year {year}: {e}")
            finally:
                db_year.close()
                QSqlDatabase.removeDatabase(db_year_conn)

        progress.setValue(len(years)); self.resources_tab.model.select()

    def clean_name(self, name): return re.sub(r'\d{4}-\d{2}-\d{2}', '', name)

    def is_valid_file(self, filename, allowed_exts=None):
        if filename.startswith('.') or filename.lower() in ['thumbs.db', 'desktop.ini']: return False
        return filename.lower().endswith(allowed_exts) if allowed_exts else True

    def process_season_episodes(self, db, master_path, type_ids, season_info, overwrite, is_spinoff=False):
        season_name = season_info['name']
        ep_total = season_info['ep_total']
        ep_type_id = type_ids.get("Episodio")
        ep_sp_type_id = type_ids.get("Ep Sp")

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
            self.log(f"Temporada: {season_name} -> Carpeta: {os.path.basename(target_folder)}")
            files = [f for f in os.listdir(target_folder) if self.is_valid_file(f, ('.mp4', '.mkv'))]

            now = datetime.now()
            is_active_season = False
            try:
                db_year = int(re.search(r'\d+', os.path.dirname(os.path.dirname(master_path))).group())
                if (now.year == db_year and now.month >= 2) or (now.year == db_year + 1 and now.month == 1):
                    is_active_season = True
            except:
                pass

            if len(files) != ep_total and ep_total > 0 and not is_active_season:
                QMessageBox.warning(self, "Advertencia", f"Temporada {season_name}: Se encontraron {len(files)} archivos, se esperaban {ep_total}.")

            self.link_season_files(db, target_folder, files, type_ids, overwrite, season_name)
        else:
            self.log(f"No se encontró carpeta para {keyword} en {season_name}.", is_error=True)

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
            QApplication.processEvents()
            self.log(f"Vinculando: {filename} -> {title}")
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

        self.log(f"Vinculando {len(records)} películas/especiales para {season_name}...")
        for i in range(min(len(records), len(movie_folders))):
            QApplication.processEvents()
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
            self.log("Carpeta de soundtracks no encontrada.", is_error=True)
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
            QApplication.processEvents()
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
                self.log(f"Vinculando soundtrack: {found_sd}")
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

    def calculate_lapsed(self, datetime_range):
        from db_manager import calculate_lapsed
        return calculate_lapsed(datetime_range)

    def get_opener_model_info(self, dt_range, model_writer):
        from db_manager import get_opener_model_info
        return get_opener_model_info(dt_range, model_writer)

    def log(self, message, is_error=False, target="resources"):
        if target == "resources" and hasattr(self, 'resources_tab'):
            self.resources_tab.log(message, is_error)
        elif target == "registry" and hasattr(self, 'registry_tab'):
            self.registry_tab.log(message, is_error)
        elif hasattr(self, 'resources_tab'):
            self.resources_tab.log(message, is_error)

if __name__ == "__main__":
    if os.name == 'nt':
        myappid = 'storeetude.precuremanager.desktopcenter.1'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

    init_databases()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setWindowIcon(QIcon("img\icon.ico"))

    window = PrecureManagerApp()
    window.show()
    sys.exit(app.exec())
