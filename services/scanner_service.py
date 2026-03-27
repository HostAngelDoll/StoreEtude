from core.resource_management import ResourceScanner as LegacyResourceScanner

class ScannerService:
    def __init__(self):
        # We wrap the legacy scanner for now, as it's already a QObject that can be moved to a thread
        self._scanner = LegacyResourceScanner()

    def get_scanner(self):
        return self._scanner

    def scan_and_link(self, years, overwrite=True):
        self._scanner.scan_and_link_resources(years, overwrite)

    def scan_new_soundtracks(self, years):
        self._scanner.scan_new_soundtracks_lyrics(years)

    def cancel(self):
        self._scanner.cancel()

    def set_duplicate_choice(self, action, apply_to_all=False):
        self._scanner.set_duplicate_choice(action, apply_to_all)
