import os
import sqlite3

GLOBAL_DB_PATH = "_global.db"
BASE_DIR_PATH = r"E:\_Internal"  # Configurable

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_global_db():
    conn = get_db_connection(GLOBAL_DB_PATH)
    cursor = conn.cursor()

    # T_Type_Catalog_Reg
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS T_Type_Catalog_Reg (
        type TEXT,
        category TEXT,
        description TEXT
    )
    """)

    # T_Opener_Models
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS T_Opener_Models (
        model_name TEXT PRIMARY KEY,
        start_validity_overwrite TEXT,
        end_validity_overwrite TEXT,
        start_validity_locally TEXT,
        end_validity_locally TEXT,
        model_name_overwrite TEXT,
        model_name_locally TEXT,
        components TEXT,
        description TEXT
    )
    """)

    # T_Type_Resources
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS T_Type_Resources (
        idx INTEGER PRIMARY KEY AUTOINCREMENT,
        type_resource TEXT
    )
    """)

    # T_Seasons
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS T_Seasons (
        year INTEGER,
        prefix_by_year TEXT,
        is_spinoff INTEGER, -- Boolean 0/1
        precure_season_name TEXT PRIMARY KEY,
        japanese_name TEXT,
        romaji_name TEXT,
        total_episode INTEGER,
        theme_description TEXT,
        release_date TEXT,
        path_master TEXT
    )
    """)

    conn.commit()
    conn.close()

def init_yearly_dbs():
    # Only if E:\ exists or the BASE_DIR_PATH exists
    if not os.path.exists(os.path.splitdrive(BASE_DIR_PATH)[0] + "\\") and not os.path.exists(BASE_DIR_PATH):
        print(f"Base path {BASE_DIR_PATH} not found. Skipping yearly databases.")
        return

    for year in range(2004, 2027):
        px = year - 2003
        px_str = f"{px:02d}"

        # Path: E:\_Internal\[year]\[px]. identity_propeties\le_etude_base.db
        year_dir = os.path.join(BASE_DIR_PATH, str(year), f"{px_str}. identity_propeties")
        db_path = os.path.join(year_dir, "le_etude_base.db")

        if not os.path.exists(year_dir):
            try:
                os.makedirs(year_dir)
            except Exception as e:
                print(f"Could not create directory {year_dir}: {e}")
                continue

        conn = get_db_connection(db_path)
        cursor = conn.cursor()

        # T_Resources
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS T_Resources (
            idx INTEGER PRIMARY KEY AUTOINCREMENT,
            type_material INTEGER,
            precure_season_name TEXT,
            ep_num INTEGER,
            ep_sp_num INTEGER,
            id_code_material TEXT UNIQUE,
            title_material TEXT,
            released_utc_09 TEXT,
            released_soundtrack_utc_09 TEXT,
            released_spinoff_utc_09 TEXT,
            duration_file TEXT,
            datetime_download TEXT,
            relative_path_of_file TEXT,
            relative_path_of_lyrics TEXT
        )
        """)

        # T_Registry
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS T_Registry (
            idx INTEGER PRIMARY KEY AUTOINCREMENT,
            id_code_material TEXT,
            datetime_range_utc_06 TEXT,
            type_repeat TEXT,
            type_listen TEXT,
            model_writer TEXT,
            lapsed_calculated TEXT,
            opener_model TEXT,
            name_of_opener_model TEXT,
            FOREIGN KEY (id_code_material) REFERENCES T_Resources(id_code_material)
        )
        """)

        conn.commit()
        conn.close()

def init_databases():
    init_global_db()
    init_yearly_dbs()

if __name__ == "__main__":
    init_databases()
