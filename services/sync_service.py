import os
from datetime import datetime
from core.db_manager_utils import get_global_db_path, get_yearly_db_path, get_offline_db_path, is_on_external_drive
from core.config_manager import ConfigManager
from core.firebase_manager import FirebaseManager
from core.sync_manager import SyncManager

class SyncService:
    def __init__(self, config: ConfigManager, fb_manager: FirebaseManager = None, sync_manager: SyncManager = None):
        self.config = config
        self.fb_manager = fb_manager or FirebaseManager()
        self.sync_manager = sync_manager or SyncManager()

    def get_startup_sync_tasks(self):
        tasks = []
        global_db_path = get_global_db_path()
        if is_on_external_drive(global_db_path):
            tasks.append((global_db_path, get_offline_db_path(global_db_path), "Sincronizando Global DB..."))

        for year in range(2004, datetime.now().year + 1):
            y_path = get_yearly_db_path(year)
            if os.path.exists(y_path):
                tasks.append((y_path, get_offline_db_path(y_path), f"Sincronizando año {year}..."))
        return tasks

    def perform_sync(self, tasks, progress_callback, finished_callback):
        self.sync_manager.task_progress.connect(progress_callback)
        self.sync_manager.sync_finished.connect(finished_callback)
        self.sync_manager.perform_sync(tasks)

    def disconnect_sync_signals(self):
        try:
            self.sync_manager.task_progress.disconnect()
            self.sync_manager.sync_finished.disconnect()
        except Exception:
            pass

    def sync_firebase_journals(self, progress_callback=None):
        if not self.config.get("firebase.db_url"):
            return False, "Firebase URL not configured"

        return self.fb_manager.download_journals(progress_callback=progress_callback)
