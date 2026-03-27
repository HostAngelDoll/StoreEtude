import os
import json
import firebase_admin
from firebase_admin import credentials, db
from core.config_manager import ConfigManager
from journals_manager.journal_logic import JournalManager

class FirebaseManager:
    def __init__(self):
        self.config = ConfigManager()
        self.journal_manager = JournalManager()
        self._app = None

    def _initialize_app(self):
        if self._app:
            return True

        creds_path = self.config.get("firebase.credentials_path")
        db_url = self.config.get("firebase.db_url")

        if not creds_path or not os.path.exists(creds_path) or not db_url:
            return False

        try:
            cred = credentials.Certificate(creds_path)
            self._app = firebase_admin.initialize_app(cred, {
                'databaseURL': db_url
            })
            return True
        except Exception as e:
            print(f"Error initializing Firebase: {e}")
            return False

    def validate_credentials(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Basic check for service account json
                required = ["type", "project_id", "private_key", "client_email"]
                return all(k in data for k in required)
        except:
            return False

    def download_journals(self, progress_callback=None):
        if not self._initialize_app():
            return False, "No se pudo inicializar Firebase. Verifique las credenciales y la URL."

        ref_path = self.config.get("firebase.db_ref_journals")
        if not ref_path:
            return False, "Referencia de base de datos para jornadas no configurada."

        try:
            ref = db.reference(ref_path)
            journals_data = ref.get()

            if not journals_data:
                return True, "No se encontraron jornadas en Firebase."

            # Firebase returns dict or list depending on keys
            if isinstance(journals_data, dict):
                items = list(journals_data.values())
            elif isinstance(journals_data, list):
                items = [i for i in journals_data if i is not None]
            else:
                return False, "Formato de datos de Firebase inesperado."

            total = len(items)
            count = 0
            for i, journal in enumerate(items):
                if progress_callback:
                    progress_callback(i, total, f"Descargando: {journal.get('nombre', 'Sin nombre')}")

                # Save locally
                self.journal_manager.save_journal(journal)
                count += 1

            return True, f"Se descargaron {count} jornadas correctamente."
        except Exception as e:
            return False, f"Error al descargar jornadas: {e}"

    def shutdown(self):
        if self._app:
            firebase_admin.delete_app(self._app)
            self._app = None
