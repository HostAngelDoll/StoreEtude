import os
import json
import shutil
from datetime import datetime
from PyQt6.QtCore import QSettings
from core.app_settings import AppSettings, UIColumnConfig

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
            appdata = os.path.expanduser("~/.config")
        
        app_dir = os.path.join(appdata, 'PrecureManager')
        return os.path.join(app_dir, 'config.json')
    
    def __init__(self):
        if self._initialized:
            return
            
        self.registry = QSettings("MyCompany", "PrecureMediaManager")
        default_path = self.get_default_config_path()
        self.config_path = self.registry.value("config_json_path", default_path)
        self.config_dir = os.path.dirname(self.config_path)
        self.cache_path = os.path.join(self.config_dir, "cache.json")
        self.offline_db_dir = os.path.join(self.config_dir, "offline_dbs")
        
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        
        self.settings = AppSettings()
        self.load()
        self._initialized = True

    def load(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    loaded_data = json.load(f)
                    self.settings = AppSettings.from_dict(loaded_data)
            except Exception as e:
                print(f"Error loading config: {e}")

    def save(self):
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings.to_dict(), f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def get(self, key, default=None):
        keys = key.split('.')
        val = self.settings
        for k in keys:
            if hasattr(val, k):
                val = getattr(val, k)
            elif isinstance(val, dict) and k in val:
                val = val[k]
            else:
                return default
        return val

    def set(self, key, value, save=True):
        keys = key.split('.')
        target = self.settings
        for k in keys[:-1]:
            if hasattr(target, k):
                target = getattr(target, k)
            elif isinstance(target, dict):
                if k not in target:
                    target[k] = {}
                target = target[k]
            else:
                return # Should handle error better

        k_last = keys[-1]
        if hasattr(target, k_last):
            setattr(target, k_last, value)
        elif isinstance(target, dict):
            target[k_last] = value

        if save:
            self.save()

    def get_column_config(self, table_name, col_name):
        configs = self.settings.ui.column_configs
        table_config = configs.get(table_name, {})
        return table_config.get(col_name, UIColumnConfig())

    def set_column_config(self, table_name, col_name, width=None, locked=None, save=True):
        configs = self.settings.ui.column_configs
        if table_name not in configs:
            configs[table_name] = {}
        
        if col_name not in configs[table_name]:
            configs[table_name][col_name] = UIColumnConfig()
        
        if width is not None:
            configs[table_name][col_name].width = width
        if locked is not None:
            configs[table_name][col_name].locked = locked
            
        if save:
            self.save()

    # Auxiliary methods (cache, move, validate) stay mostly the same but point to self.settings
    def get_cache(self, key, default=None):
        if not os.path.exists(self.cache_path): return default
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                return json.load(f).get(key, default)
        except: return default

    def set_cache(self, key, value):
        cache = self.get_cache_all()
        cache[key] = value
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=4)
        except Exception as e: print(f"Error saving cache: {e}")

    def get_cache_all(self):
        if not os.path.exists(self.cache_path): return {}
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except: return {}

    def clear_cache(self, key=None):
        if key is None:
            if os.path.exists(self.cache_path):
                try: os.remove(self.cache_path)
                except: pass
        else:
            cache = self.get_cache_all()
            if key in cache:
                del cache[key]
                with open(self.cache_path, 'w', encoding='utf-8') as f:
                    json.dump(cache, f, indent=4)

    def move_config_file(self, new_path):
        if new_path == self.config_path: return True
        old_dir, new_dir = os.path.dirname(self.config_path), os.path.dirname(new_path)
        try:
            os.makedirs(new_dir, exist_ok=True)
            if os.path.exists(self.config_path): shutil.move(self.config_path, new_path)
            else: self.config_path = new_path; self.save()
            
            for f in ["cache.json", "whitelist.json"]:
                if os.path.exists(os.path.join(old_dir, f)):
                    shutil.move(os.path.join(old_dir, f), os.path.join(new_dir, f))
            
            for f in os.listdir(old_dir):
                if f.startswith("session_telegram") and f.endswith(".session"):
                    shutil.move(os.path.join(old_dir, f), os.path.join(new_dir, f))

            for d in ["offline_dbs", "journals"]:
                if os.path.exists(os.path.join(old_dir, d)):
                    shutil.move(os.path.join(old_dir, d), os.path.join(new_dir, d))

            old_creds = self.settings.firebase.credentials_path
            if old_creds and old_creds.startswith(old_dir):
                new_creds = old_creds.replace(old_dir, new_dir)
                os.makedirs(os.path.dirname(new_creds), exist_ok=True)
                shutil.move(old_creds, new_creds)
                self.settings.firebase.credentials_path = new_creds

            self.config_path, self.config_dir = new_path, new_dir
            self.cache_path = os.path.join(new_dir, "cache.json")
            self.offline_db_dir = os.path.join(new_dir, "offline_dbs")
            self.registry.setValue("config_json_path", new_path)
            return True
        except Exception as e:
            print(f"Error moving config: {e}")
            return False

    @staticmethod
    def validate_base_dir(path):
        if not os.path.exists(path): return False, "La ruta no existe."
        missing = [str(y) for y in range(2004, datetime.now().year + 1) if not os.path.isdir(os.path.join(path, str(y)))]
        if missing: return False, f"Faltan carpetas de años: {', '.join(missing[:5])}{'...' if len(missing) > 5 else ''}"
        return True, ""
