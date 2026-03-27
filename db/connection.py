import os
import gc
from PyQt6.QtSql import QSqlDatabase, QSqlQuery
from PyQt6.QtWidgets import QApplication

class DBConnectionManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(DBConnectionManager, cls).__new__(cls)
            cls._instance.connections = {}
        return cls._instance

    def get_connection(self, name):
        return QSqlDatabase.database(name)

    def open_connection(self, name, path, readonly=False):
        db = QSqlDatabase.database(name, open=False)
        if not db.isValid():
            db = QSqlDatabase.addDatabase("QSQLITE", name)

        if db.isOpen():
            db.close()

        if readonly:
            # Use URI mode for RO
            db.setDatabaseName(f"file:{path}?mode=ro")
            db.setConnectOptions("QSQLITE_OPEN_URI")
        else:
            db.setDatabaseName(path)
            db.setConnectOptions("")

        if not db.open():
            raise RuntimeError(f"Could not open database {name} at {path}: {db.lastError().text()}")

        return db

    def close_all(self, tabs):
        # 1. Unlink models from views
        for tab in tabs:
            if hasattr(tab, 'view') and hasattr(tab, 'model') and tab.model:
                tab.view.setModel(None)
                tab.model.deleteLater()
                tab.model = None

        # 2. Process events to ensure deleteLater is executed
        QApplication.processEvents()
        gc.collect()

        # 3. Close and remove connections
        for name in list(QSqlDatabase.connectionNames()):
            db = QSqlDatabase.database(name, open=False)
            if db.isOpen():
                db.close()
            del db
            QSqlDatabase.removeDatabase(name)

        QApplication.processEvents()

    def safe_detach(self, conn_name, schema_name):
        db = QSqlDatabase.database(conn_name)
        if not db.isOpen():
            return

        query = QSqlQuery(db)
        if query.exec("PRAGMA database_list"):
            while query.next():
                if query.value(1) == schema_name:
                    QSqlQuery(db).exec(f"DETACH DATABASE {schema_name}")
                    break

    def safe_attach(self, conn_name, path, schema_name):
        db = QSqlDatabase.database(conn_name)
        if not db.isOpen():
            return False

        self.safe_detach(conn_name, schema_name)

        safe_path = path.replace("'", "''")
        query = QSqlQuery(db)
        if not query.exec(f"ATTACH DATABASE '{safe_path}' AS {schema_name}"):
            print(f"ATTACH failed: {query.lastError().text()}")
            return False
        return True
