from PyQt6.QtCore import QObject, pyqtSignal

class BaseWorker(QObject):
    progress_changed = pyqtSignal(int, int, str)
    log_message = pyqtSignal(str, bool, str)
    finished = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def __init__(self, service):
        super().__init__()
        self.service = service

    def cancel(self): self.service.cancel()
