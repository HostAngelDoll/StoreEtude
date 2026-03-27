import os
import sqlite3
import json
import time
import hashlib
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from core.config_manager import ConfigManager

class BackupWorker(QThread):
    progress = pyqtSignal(int, int, str)  # current, total, label
    finished = pyqtSignal(bool, str)       # success, message

    def __init__(self, src_path, dst_path, label="Copiando base de datos..."):
        super().__init__()
        self.src_path = src_path
        self.dst_path = dst_path
        self.label = label

    def run(self):
        try:
            if not os.path.exists(self.src_path):
                self.finished.emit(False, f"Archivo origen no encontrado: {self.src_path}")
                return

            os.makedirs(os.path.dirname(self.dst_path), exist_ok=True)

            src_conn = sqlite3.connect(self.src_path)
            dst_conn = sqlite3.connect(self.dst_path)

            with dst_conn:
                src_conn.backup(dst_conn, pages=10, progress=self._progress_callback)

            src_conn.close()
            dst_conn.close()

            self.finished.emit(True, "Backup completado exitosamente.")
        except Exception as e:
            self.finished.emit(False, str(e))

    def _progress_callback(self, status, remaining, total):
        # status is not used by backup() but pages is
        # remaining and total are pages
        current = total - remaining
        self.progress.emit(current, total, self.label)

class SyncManager(QObject):
    sync_finished = pyqtSignal(bool, str)
    task_progress = pyqtSignal(int, int, str)

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.sync_cache_path = os.path.join(os.path.dirname(self.config.config_path), "sync_cache.json")
        self._load_sync_cache()

    def _load_sync_cache(self):
        if os.path.exists(self.sync_cache_path):
            try:
                with open(self.sync_cache_path, 'r', encoding='utf-8') as f:
                    self.sync_cache = json.load(f)
            except:
                self.sync_cache = {}
        else:
            self.sync_cache = {}

    def _save_sync_cache(self):
        try:
            with open(self.sync_cache_path, 'w', encoding='utf-8') as f:
                json.dump(self.sync_cache, f, indent=4)
        except Exception as e:
            print(f"Error saving sync cache: {e}")

    def get_file_metadata(self, filepath):
        if not os.path.exists(filepath):
            return None
        stats = os.stat(filepath)
        return {
            "mtime": stats.st_mtime,
            "size": stats.st_size
        }

    def needs_sync(self, src_path, dst_path):
        if not os.path.exists(dst_path):
            return True

        src_meta = self.get_file_metadata(src_path)
        if not src_meta:
            return False

        cached_meta = self.sync_cache.get(src_path)
        if not cached_meta:
            return True

        if src_meta["mtime"] != cached_meta["mtime"] or src_meta["size"] != cached_meta["size"]:
            return True

        return False

    def update_sync_metadata(self, src_path):
        meta = self.get_file_metadata(src_path)
        if meta:
            self.sync_cache[src_path] = meta
            self._save_sync_cache()

    def perform_sync(self, sync_tasks):
        """
        sync_tasks: list of (src, dst, label)
        """
        if not sync_tasks:
            self.sync_finished.emit(True, "No hay tareas de sincronización.")
            return

        self.remaining_tasks = sync_tasks
        self._process_next_task()

    def _process_next_task(self):
        if not self.remaining_tasks:
            self.sync_finished.emit(True, "Sincronización finalizada.")
            return

        src, dst, label = self.remaining_tasks.pop(0)

        if self.needs_sync(src, dst):
            self.worker = BackupWorker(src, dst, label)
            self.worker.progress.connect(self.task_progress.emit)
            self.worker.finished.connect(lambda success, msg: self._on_worker_finished(success, msg, src))
            self.worker.start()
        else:
            # Emit 100% for skipped tasks to keep progress bar moving
            self.task_progress.emit(100, 100, label)
            self._process_next_task()

    def _on_worker_finished(self, success, msg, src_path):
        if success:
            self.update_sync_metadata(src_path)
            self._process_next_task()
        else:
            self.sync_finished.emit(False, msg)
