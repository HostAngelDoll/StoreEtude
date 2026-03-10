import os
import sqlite3

GLOBAL_DB_PATH = "_global.db"
BASE_DIR_PATH = r"E:\_Internal"  # Configurable
SQL_DIR = "sql"

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
        except:
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

def init_databases(reset=False):
    init_global_db(reset)
    init_yearly_dbs(reset)

if __name__ == "__main__":
    init_databases(reset=True)
