import os
import json
import uuid
from datetime import datetime
from core.config_manager import ConfigManager

class JournalManager:
    def __init__(self):
        self.config = ConfigManager()
        self.journals_dir = os.path.join(self.config.config_dir, "journals")
        os.makedirs(self.journals_dir, exist_ok=True)

    def get_journals_dir(self):
        return self.journals_dir

    def list_journals(self):
        journals = []
        if not os.path.exists(self.journals_dir):
            return journals

        for filename in os.listdir(self.journals_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.journals_dir, filename)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        data['_filename'] = filename
                        journals.append(data)
                except Exception as e:
                    print(f"Error loading journal {filename}: {e}")
        return journals

    def get_journal(self, journal_id):
        filename = f"{journal_id}.json"
        path = os.path.join(self.journals_dir, filename)
        if not os.path.exists(path):
            return None
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data['_filename'] = filename
                return data
        except Exception as e:
            print(f"Error loading journal {filename}: {e}")
            return None

    def _calculate_material_paths(self, material):
        title = material.get('title_material', '')
        season = material.get('season', '')
        type_res = material.get('type_resource', '')

        results = {
            "path": "",
            "lyric_path": "",
            "summon_path": ""
        }

        if not season:
            return results

        import sqlite3
        from core.db_manager_utils import get_global_db_path, get_yearly_db_path, get_offline_db_path

        global_db = get_global_db_path()
        if not os.path.exists(global_db):
            global_db = get_offline_db_path(global_db)

        if not os.path.exists(global_db):
            return results

        try:
            conn_g = sqlite3.connect(global_db)
            cursor_g = conn_g.cursor()
            cursor_g.execute("SELECT year, path_master FROM T_Seasons WHERE precure_season_name = ?", (season,))
            row_s = cursor_g.fetchone()
            conn_g.close()

            if not row_s:
                return results

            year, master_folder = row_s

            yearly_db = get_yearly_db_path(year)
            if not os.path.exists(yearly_db):
                yearly_db = get_offline_db_path(yearly_db)

            if not os.path.exists(yearly_db):
                return results

            conn_y = sqlite3.connect(yearly_db)
            cursor_y = conn_y.cursor()

            # Mapping based on typical storage in T_Resources
            col = ""
            if type_res in ["Soundtrack", "Soundtrack Sp"]:
                col = "relative_path_of_soundtracks"
            elif type_res in ["Letra", "Lyrics"]:
                col = "relative_path_of_lyrics"
            else:
                # Default mapping for episodes, movies, trailers, spinoffs, etc.
                col = "relative_path_of_file"

            # 1. Path calculation
            if title != "[User selection]" and title and col:
                cursor_y.execute(f"SELECT {col} FROM T_Resources WHERE title_material = ?", (title,))
                row_r = cursor_y.fetchone()
                if row_r and row_r[0]:
                    rel_path = row_r[0].replace("\\", "/").strip()
                    full_path = f"/{year}/{master_folder}/{rel_path}"
                    while "//" in full_path: full_path = full_path.replace("//", "/")
                    results["path"] = full_path

            # 2. Lyric path calculation
            if type_res in ["Soundtrack", "Soundtrack Sp"] and title != "[User selection]" and title:
                cursor_y.execute("SELECT relative_path_of_lyrics FROM T_Resources WHERE title_material = ?", (title,))
                row_l = cursor_y.fetchone()
                if row_l and row_l[0]:
                    rel_lyric = row_l[0].replace("\\", "/").strip()
                    full_lyric = f"/{year}/{master_folder}/{rel_lyric}"
                    while "//" in full_lyric: full_lyric = full_lyric.replace("//", "/")
                    results["lyric_path"] = full_lyric

            # 3. Summon path calculation
            summon_rel = ""
            if results["path"]:
                # From existing path
                summon_rel = "/".join(results["path"].split("/")[:-1]) + "/"
            elif col:
                # From first file (cache or DB)
                cache_key = f"first_file_{year}_{season}_{type_res}"
                first_file_rel = self.config.get_cache(cache_key)

                if not first_file_rel:
                    # In yearly db, we need to join with global db types or guess the integer ID
                    # Since global_db is already opened once above (but closed),
                    # let's just get the type_id from T_Type_Resources (global) first.
                    conn_g_tmp = sqlite3.connect(global_db)
                    cursor_g_tmp = conn_g_tmp.cursor()
                    cursor_g_tmp.execute("SELECT idx FROM T_Type_Resources WHERE type_resource = ?", (type_res,))
                    row_t = cursor_g_tmp.fetchone()
                    conn_g_tmp.close()

                    if row_t:
                        type_id = row_t[0]
                        cursor_y.execute(f"SELECT {col} FROM T_Resources WHERE precure_season_name = ? AND type_material = ? AND {col} IS NOT NULL AND {col} != '' ORDER BY title_material ASC LIMIT 1", (season, type_id))
                        row_f = cursor_y.fetchone()
                        if row_f:
                            first_file_rel = row_f[0]
                            self.config.set_cache(cache_key, first_file_rel)

                if first_file_rel:
                    first_file_rel = first_file_rel.replace("\\", "/").strip()
                    full_first = f"/{year}/{master_folder}/{first_file_rel}"
                    summon_rel = "/".join(full_first.split("/")[:-1]) + "/"

            if summon_rel:
                while "//" in summon_rel: summon_rel = summon_rel.replace("//", "/")
                results["summon_path"] = summon_rel

            conn_y.close()
            return results

        except Exception as e:
            print(f"Error calculating paths: {e}")
            return results

    def save_journal(self, data):
        # data should have 'nombre', 'fecha_esperada', 'estado', 'materiales'
        # Enrich materials with paths
        for material in data.get('materiales', []):
            paths = self._calculate_material_paths(material)
            material.update(paths)

        journal_id = data.get('id')
        if not journal_id:
            journal_id = str(uuid.uuid4())
            data['id'] = journal_id
            data['created_at'] = datetime.now().isoformat()
            data['vertion'] = "1"
        else:
            # Increment version
            try:
                v = int(data.get('vertion', "1"))
                data['vertion'] = str(v + 1)
            except:
                data['vertion'] = "1"

        data['updated_at'] = datetime.now().isoformat()

        filename = f"{journal_id}.json"
        path = os.path.join(self.journals_dir, filename)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

        return journal_id

    def delete_journal(self, journal_id):
        filename = f"{journal_id}.json"
        path = os.path.join(self.journals_dir, filename)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def get_journal_by_name(self, name):
        for j in self.list_journals():
            if j.get('nombre') == name:
                return j
        return None

    def toggle_state(self, journal_id):
        filename = f"{journal_id}.json"
        path = os.path.join(self.journals_dir, filename)
        if not os.path.exists(path):
            return False

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if data.get('estado') == "borrador":
            data['estado'] = "guardado"
        else:
            data['estado'] = "borrador"

        # Update paths as well to ensure they are present for NextPlayer
        for material in data.get('materiales', []):
            paths = self._calculate_material_paths(material)
            material.update(paths)

        # Increment version for state change too? Requirement says "por cada modificacion"
        try:
            v = int(data.get('vertion', "1"))
            data['vertion'] = str(v + 1)
        except:
            data['vertion'] = "1"

        data['updated_at'] = datetime.now().isoformat()

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return True

    def categorize_journals(self):
        journals = self.list_journals()
        # Sort by fecha_esperada
        journals.sort(key=lambda x: x.get('fecha_esperada', ""))

        borradores = []
        pendientes = []
        vencidos = []

        today = datetime.now().date()

        for j in journals:
            estado = j.get('estado')
            fecha_str = j.get('fecha_esperada', "")
            try:
                fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except:
                fecha = None

            if estado == "borrador":
                borradores.append(j)
            elif estado == "guardado":
                if fecha and fecha < today:
                    vencidos.append(j)
                else:
                    pendientes.append(j)
            else:
                # Default to borradores if state is unknown?
                borradores.append(j)

        return borradores, pendientes, vencidos
