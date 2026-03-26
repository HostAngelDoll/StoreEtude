import os
import re
import sqlite3
from datetime import datetime
from db.schema import get_yearly_db_path, GLOBAL_DB_PATH, BASE_DIR_PATH
from core.utils import calculate_lapsed

def get_offline_db_path(original_path):
    from config_manager import ConfigManager
    config = ConfigManager()
    offline_dir = config.offline_db_dir
    os.makedirs(offline_dir, exist_ok=True)
    if original_path == GLOBAL_DB_PATH: return os.path.join(offline_dir, "offline_global.db")
    match = re.search(r'\\(\d{4})\\', original_path)
    if match: return os.path.join(offline_dir, f"offline_{match.group(1)}.db")
    return os.path.join(offline_dir, f"offline_{os.path.basename(original_path)}")

def get_opener_model_info_sqlite(dt_range, model_writer):
    if not dt_range or not model_writer: return None, None
    try:
        date_str = str(dt_range).strip().split(' ')[0]
        if not re.match(r'\d{4}-\d{2}-\d{2}', date_str): return None, None
        conn = sqlite3.connect(GLOBAL_DB_PATH)
        cursor = conn.cursor()
        writer_type = str(model_writer).lower()
        if "overwrite" in writer_type: col_start, col_end, col_sub = "start_validity_overwrite", "end_validity_overwrite", "model_name_overwrite"
        elif "locally" in writer_type: col_start, col_end, col_sub = "start_validity_locally", "end_validity_locally", "model_name_locally"
        else: conn.close(); return None, None
        cursor.execute(f"SELECT model_name, {col_sub} FROM T_Opener_Models WHERE ? >= {col_start} AND ? <= {col_end}", (date_str, date_str))
        row = cursor.fetchone(); conn.close()
        return (row[0], row[1]) if row else (None, None)
    except: return None, None

class DBOperations:
    def process_materials_report(self, materials_list):
        # Implementation of report processing
        return 0
