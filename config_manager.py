import os
import json
import shutil
from datetime import datetime
from PyQt6.QtCore import QSettings, QStandardPaths

class ConfigManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    @staticmethod
    def get_default_config_path():
        appdata = os.getenv('APPDATA')
        if not appdata:
            # Fallback for non-windows or weird environments
            appdata = os.path.expanduser("~/.config")
        
        app_dir = os.path.join(appdata, 'PrecureManager')
        return os.path.join(app_dir, 'config.json')
    
    def __init__(self):
        if self._initialized:
            return
            
        # We use QSettings ONLY to store the path to the actual JSON config file in the Registry
        self.registry = QSettings("MyCompany", "PrecureMediaManager")
        default_path = self.get_default_config_path()
        self.config_path = self.registry.value("config_json_path", default_path)
        self.config_dir = os.path.dirname(self.config_path)
        self.cache_path = os.path.join(self.config_dir, "cache.json")
        self.offline_db_dir = os.path.join(self.config_dir, "offline_dbs")
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        self.settings = {
            "base_dir_path": r"E:\_Internal",
            "global_db_path": "_global.db",
            "ui": {
                "geometry": None,
                "maximized": True,
                "sidebar_visible": True,
                "console_visible": True,
                "auto_resize": True,
                "show_construction_logs": False,
                "theme": "Fusion",
                "column_configs": {} # table_name -> {col_name -> {"width": int, "locked": bool}}
            },
            "telegram": {
                "api_id": "",
                "api_hash": "",
                "chat_id": None,
                "chat_name": ""
            },
            "api": {
                "enabled": False,
                "port": 9090
            },
            "firebase": {
                "db_url": "",
                "db_ref_journals": "",
                "credentials_path": ""
            }
        }
        self.load()
        self._initialized = True

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge loaded settings into default ones to handle new keys
                    self._deep_update(self.settings, loaded)
            except Exception as e:
                print(f"Error loading config: {e}")

    def _deep_update(self, base, update):
        for k, v in update.items():
            if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                self._deep_update(base[k], v)
            else:
                base[k] = v

    def save(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.settings
        for k in keys:
            if isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def get_column_config(self, table_name, col_name):
        configs = self.get("ui.column_configs", {})
        table_config = configs.get(table_name, {})
        return table_config.get(col_name, {"width": 100, "locked": False})

    def set_column_config(self, table_name, col_name, width=None, locked=None, save=True):
        configs = self.get("ui.column_configs", {})
        if table_name not in configs:
            configs[table_name] = {}
        
        if col_name not in configs[table_name]:
            configs[table_name][col_name] = {"width": 100, "locked": False}
        
        if width is not None:
            configs[table_name][col_name]["width"] = width
        if locked is not None:
            configs[table_name][col_name]["locked"] = locked
            
        self.set("ui.column_configs", configs, save=save)

    def set(self, key, value, save=True):
        keys = key.split('.')
        val = self.settings
        for k in keys[:-1]:
            if k not in val:
                val[k] = {}
            val = val[k]
        val[keys[-1]] = value
        if save:
            self.save()

    def get_cache(self, key, default=None):
        if not os.path.exists(self.cache_path):
            return default
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                cache = json.load(f)
                return cache.get(key, default)
        except:
            return default

    def set_cache(self, key, value):
        cache = {}
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    cache = json.load(f)
            except:
                pass

        cache[key] = value
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=4)
        except Exception as e:
            print(f"Error saving cache: {e}")

    def clear_cache(self, key=None):
        if key is None:
            if os.path.exists(self.cache_path):
                try: os.remove(self.cache_path)
                except: pass
        else:
            if os.path.exists(self.cache_path):
                try:
                    with open(self.cache_path, 'r', encoding='utf-8') as f:
                        cache = json.load(f)
                    if key in cache:
                        del cache[key]
                        with open(self.cache_path, 'w', encoding='utf-8') as f:
                            json.dump(cache, f, indent=4)
                except:
                    pass

    def move_config_file(self, new_path):
        if new_path == self.config_path:
            return True
        
        old_dir = os.path.dirname(self.config_path)
        new_dir = os.path.dirname(new_path)

        try:
            # Ensure target directory exists
            os.makedirs(new_dir, exist_ok=True)
            
            # Move config file
            if os.path.exists(self.config_path):
                shutil.move(self.config_path, new_path)
            else:
                self.config_path = new_path
                self.save()
            
            # Move cache file if exists
            old_cache = os.path.join(old_dir, "cache.json")
            if os.path.exists(old_cache):
                shutil.move(old_cache, os.path.join(new_dir, "cache.json"))

            # Move telegram session files if they exist
            # Telethon creates session_name.session
            for f in os.listdir(old_dir):
                if f.startswith("session_telegram") and f.endswith(".session"):
                    shutil.move(os.path.join(old_dir, f), os.path.join(new_dir, f))

            # Move offline dbs if they exist
            old_offline_dir = os.path.join(old_dir, "offline_dbs")
            if os.path.exists(old_offline_dir):
                shutil.move(old_offline_dir, os.path.join(new_dir, "offline_dbs"))

            # Move journals if they exist
            old_journals_dir = os.path.join(old_dir, "journals")
            if os.path.exists(old_journals_dir):
                shutil.move(old_journals_dir, os.path.join(new_dir, "journals"))

            # Move whitelist if exists
            old_whitelist = os.path.join(old_dir, "whitelist.json")
            if os.path.exists(old_whitelist):
                shutil.move(old_whitelist, os.path.join(new_dir, "whitelist.json"))

            # Move firebase credentials if they exist and are inside the config dir
            old_creds = self.get("firebase.credentials_path")
            if old_creds and old_creds.startswith(old_dir):
                new_creds = old_creds.replace(old_dir, new_dir)
                os.makedirs(os.path.dirname(new_creds), exist_ok=True)
                shutil.move(old_creds, new_creds)
                self.set("firebase.credentials_path", new_creds, save=False)

            # Update paths in memory
            self.config_path = new_path
            self.config_dir = new_dir
            self.cache_path = os.path.join(new_dir, "cache.json")
            self.offline_db_dir = os.path.join(new_dir, "offline_dbs")

            # Update registry
            self.registry.setValue("config_json_path", new_path)
            return True
        except Exception as e:
            print(f"Error moving config and auxiliary files: {e}")
            return False

    @staticmethod
    def validate_base_dir(path):
        if not os.path.exists(path):
            return False, "La ruta no existe."
        
        current_year = datetime.now().year
        missing = []
        for year in range(2004, current_year + 1):
            year_path = os.path.join(path, str(year))
            if not os.path.isdir(year_path):
                missing.append(str(year))
        
        if missing:
            return False, f"Faltan carpetas de años: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}"
        
        return True, ""

    @staticmethod
    def validate_db_path(path):
        if os.path.exists(path) and os.path.isfile(path):
            return True, ""
        # If it doesn't exist, it might be created later, but we should probably warn
        return False, "Archivo de base de datos no encontrado."
