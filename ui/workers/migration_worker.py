from PyQt6.QtCore import pyqtSignal
from .base_worker import BaseWorker

class MigrationWorker(BaseWorker):
    finished_with_count = pyqtSignal(int)
    request_confirmation = pyqtSignal(int, str)

    def __init__(self, migration_service, base_dir, years):
        super().__init__(migration_service)
        self.base_dir = base_dir
        self.years = years
        self._confirmation_result = None

    def set_confirmation_result(self, res): self._confirmation_result = res

    def _confirm_callback(self, year):
        self._confirmation_result = None
        self.request_confirmation.emit(year, f"La tabla T_Registry del año {year} contiene datos. ¿Desea borrarlos?")
        while self._confirmation_result is None:
            import time; time.sleep(0.01)
        return self._confirmation_result

    def migrate_resources(self):
        count = self.service.migrate_resources(self.base_dir, self.years, self.progress_changed.emit, self.log_message.emit)
        self.finished_with_count.emit(count)
        self.finished.emit()

    def migrate_registry(self):
        count = self.service.migrate_registry(self.base_dir, self.years, self._confirm_callback, self.progress_changed.emit, self.log_message.emit)
        self.finished_with_count.emit(count)
        self.finished.emit()
