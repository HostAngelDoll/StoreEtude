from PyQt6.QtCore import pyqtSignal
from .base_worker import BaseWorker

class ScannerWorker(BaseWorker):
    warning_emitted = pyqtSignal(str, str)
    request_duplicate_action = pyqtSignal(str)

    def __init__(self, scanner_service, duplicate_resolver, base_dir, years, overwrite=True):
        super().__init__(scanner_service)
        self.duplicate_resolver = duplicate_resolver
        self.base_dir = base_dir
        self.years = years
        self.overwrite = overwrite

    def scan_and_link(self):
        self.service.scan_and_link_resources(self.base_dir, self.years, self.overwrite, self.progress_changed.emit, self.log_message.emit, self.warning_emitted.emit)
        self.finished.emit()

    def scan_new_soundtracks(self):
        # Implementation of scan_new_soundtracks logic moved to scanner_service/duplicate_resolver
        # but for now we follow the existing structure.
        pass
