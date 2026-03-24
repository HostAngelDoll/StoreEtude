import os
from PyQt6.QtCore import QObject, QTimer, pyqtSignal

class DriveMonitor(QObject):
    drive_status_changed = pyqtSignal(bool) # is_available

    def __init__(self, drive_letter, interval_ms=3000):
        super().__init__()
        self.drive_path = drive_letter + ":\\"
        self.is_available = self._check()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._poll)
        self.timer.start(interval_ms)

    def _check(self):
        try:
            return os.path.isdir(self.drive_path)
        except Exception as e:
            print(f"DriveMonitor error: {e}")
            return False

    def _poll(self):
        current = self._check()
        if current != self.is_available:
            self.is_available = current
            self.drive_status_changed.emit(self.is_available)
