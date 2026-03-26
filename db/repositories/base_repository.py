from PyQt6.QtSql import QSqlQuery, QSqlDatabase

class BaseRepository:
    def __init__(self, db_conn_name):
        self.db_conn_name = db_conn_name

    def get_db(self):
        return QSqlDatabase.database(self.db_conn_name)

    def execute_query(self, sql, params=None):
        db = self.get_db()
        if not db.isOpen():
            return None

        query = QSqlQuery(db)
        if params:
            query.prepare(sql)
            for param in params:
                query.addBindValue(param)
            success = query.exec()
        else:
            success = query.exec(sql)

        if success:
            return query
        else:
            print(f"Query failed: {query.lastError().text()}")
            return None
