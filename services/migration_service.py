from data_migration import DataMigrator as LegacyDataMigrator

class MigrationService:
    def __init__(self):
        self._migrator = LegacyDataMigrator()

    def get_migrator(self):
        return self._migrator

    def migrate_resources(self):
        self._migrator.migrate_resources()

    def migrate_registry(self):
        self._migrator.migrate_registry()

    def cancel(self):
        self._migrator.cancel()

    def set_confirmation_result(self, result):
        self._migrator.set_confirmation_result(result)
