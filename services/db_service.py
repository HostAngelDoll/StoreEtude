from core.db_operations import DBOperations as LegacyDBOperations

class DBService:
    def __init__(self):
        self._ops = LegacyDBOperations()

    def get_operations_worker(self):
        return self._ops

    def scan_master_folders(self):
        self._ops.scan_master_folders()

    def recalculate_lapses(self, db_path):
        self._ops.recalculate_registry_lapses(db_path)

    def recalculate_models(self, db_path):
        self._ops.recalculate_registry_models(db_path)

    def regenerate_index(self, years):
        self._ops.regenerate_registry_index(years)

    def cancel(self):
        self._ops.cancel()
