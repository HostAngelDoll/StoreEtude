import os
import sqlite3
import re
import time
from datetime import datetime
from PyQt6.QtSql import QSqlQuery, QSqlDatabase
from config_manager import ConfigManager

_config = ConfigManager()

GLOBAL_DB_PATH = _config.get("global_db_path", "_global.db")
BASE_DIR_PATH = _config.get("base_dir_path", r"E:\_Internal")
SQL_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sql")

def refresh_config_paths():
    global GLOBAL_DB_PATH, BASE_DIR_PATH
    _config.load()
    GLOBAL_DB_PATH = _config.get("global_db_path", "_global.db")
    BASE_DIR_PATH = _config.get("base_dir_path", r"E:\_Internal")

def is_on_external_drive(path):
    # Check if path starts with E:\
    # Using case-insensitive check to be safe
    return path.lower().startswith("e:\\")

def get_offline_db_path(original_path):
    config = ConfigManager()
    offline_dir = config.offline_db_dir
    os.makedirs(offline_dir, exist_ok=True)

    if original_path == GLOBAL_DB_PATH:
        return os.path.join(offline_dir, "offline_global.db")

    # For yearly dbs, original_path looks like:
    # E:\_Internal\2004\01. identity_propeties\le_etude_base.db
    # We want a flat name like offline_2004.db
    match = re.search(r'\\(\d{4})\\', original_path)
    if match:
        year = match.group(1)
        return os.path.join(offline_dir, f"offline_{year}.db")

    # Fallback to a sanitized filename
    filename = os.path.basename(original_path)
    return os.path.join(offline_dir, f"offline_{filename}")

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def get_yearly_db_path(year):
    px = int(year) - 2003
    px_str = f"{px:02d}"
    year_dir = os.path.join(BASE_DIR_PATH, str(year), f"{px_str}. identity_propeties")
    return os.path.join(year_dir, "le_etude_base.db")

def run_sql_file(conn, filename):
    filepath = os.path.join(SQL_DIR, filename)
    if not os.path.exists(filepath):
        print(f"SQL file not found: {filepath}")
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
    conn.executescript(sql)

def init_global_db(reset=False):
    if reset and os.path.exists(GLOBAL_DB_PATH):
        os.remove(GLOBAL_DB_PATH)
        
    conn = get_db_connection(GLOBAL_DB_PATH)
    run_sql_file(conn, "global.sql")
    conn.commit()
    conn.close()

def init_yearly_dbs(reset=False):
    # Only if E:\ exists or the BASE_DIR_PATH exists
    drive = os.path.splitdrive(BASE_DIR_PATH)[0]
    if drive and not os.path.exists(drive + "\\"):
         # Skip if drive doesn't exist
         return
    
    if not os.path.exists(BASE_DIR_PATH):
        try:
            os.makedirs(BASE_DIR_PATH)
        except Exception as e:
            print(f"Error creating base dir: {e}")
            return

    for year in range(2004, 2027):
        db_path = get_yearly_db_path(year)
        year_dir = os.path.dirname(db_path)
        
        if reset and os.path.exists(db_path):
            os.remove(db_path)

        if not os.path.exists(year_dir):
            try:
                os.makedirs(year_dir)
            except Exception as e:
                print(f"Could not create directory {year_dir}: {e}")
                continue
        
        conn = get_db_connection(db_path)
        run_sql_file(conn, "yearly.sql")
        conn.commit()
        conn.close()

def calculate_lapsed(datetime_range):
    try:
        # Format: "2023-01-01 03:07:00-03:32:00"
        parts = str(datetime_range).strip().split(' ')
        if len(parts) < 2: return "00:00:00"

        times = parts[1].split('-')
        if len(times) < 2: return "00:00:00"

        fmt = '%H:%M:%S'
        start_t = datetime.strptime(times[0], fmt)
        end_t = datetime.strptime(times[1], fmt)

        delta = end_t - start_t
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            total_seconds += 86400 # Handle midnight crossing

        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except Exception:
        return "00:00:00"

def get_opener_model_info(dt_range, model_writer):
    if not dt_range or not model_writer:
        return None, None

    try:
        # Extract date "YYYY-MM-DD"
        date_str = str(dt_range).strip().split(' ')[0]
        if not re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            return None, None

        db_global = QSqlDatabase.database("global_db")
        if not db_global.isOpen():
            return None, None
            
        q = QSqlQuery(db_global)

        writer_type = str(model_writer).lower()
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

        q.prepare(f"""
            SELECT model_name, {col_subname}
            FROM T_Opener_Models
            WHERE ? >= {col_start} AND ? <= {col_end}
        """)
        q.addBindValue(date_str)
        q.addBindValue(date_str)

        if q.exec() and q.next():
            return q.value(0), q.value(1)
    except Exception as e:
        print(f"Error in get_opener_model_info: {e}")

    return None, None

def get_opener_model_info_sqlite(dt_range, model_writer):
    if not dt_range or not model_writer:
        return None, None

    try:
        # Extract date "YYYY-MM-DD"
        date_str = str(dt_range).strip().split(' ')[0]
        if not re.match(r'\d{4}-\d{2}-\d{2}', date_str):
            return None, None

        conn = sqlite3.connect(GLOBAL_DB_PATH)
        cursor = conn.cursor()

        writer_type = str(model_writer).lower()
        if "overwrite" in writer_type:
            col_start = "start_validity_overwrite"
            col_end = "end_validity_overwrite"
            col_subname = "model_name_overwrite"
        elif "locally" in writer_type:
            col_start = "start_validity_locally"
            col_end = "end_validity_locally"
            col_subname = "model_name_locally"
        else:
            conn.close()
            return None, None

        cursor.execute(f"""
            SELECT model_name, {col_subname}
            FROM T_Opener_Models
            WHERE ? >= {col_start} AND ? <= {col_end}
        """, (date_str, date_str))

        row = cursor.fetchone()
        conn.close()
        if row:
            return row[0], row[1]
    except Exception as e:
        print(f"Error in get_opener_model_info_sqlite: {e}")

    return None, None

def init_databases(reset=False):
    init_global_db(reset)
    init_yearly_dbs(reset)

if __name__ == "__main__":
    init_databases(reset=True)
