import os
import json
import uuid
from datetime import datetime
from core.config_manager import ConfigManager

class JournalManager:
    def __init__(self):
        self.config = ConfigManager()
        self.journals_dir = os.path.join(self.config.config_dir, "journals")
        os.makedirs(self.journals_dir, exist_ok=True)

    def get_journals_dir(self):
        return self.journals_dir

    def list_journals(self):
        journals = []
        if not os.path.exists(self.journals_dir):
            return journals

        for filename in os.listdir(self.journals_dir):
            if filename.endswith(".json"):
                path = os.path.join(self.journals_dir, filename)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        data['_filename'] = filename
                        journals.append(data)
                except Exception as e:
                    print(f"Error loading journal {filename}: {e}")
        return journals

    def save_journal(self, data):
        # data should have 'nombre', 'fecha_esperada', 'estado', 'materiales'
        journal_id = data.get('id')
        if not journal_id:
            journal_id = str(uuid.uuid4())
            data['id'] = journal_id
            data['created_at'] = datetime.now().isoformat()
            data['vertion'] = "1"
        else:
            # Increment version
            try:
                v = int(data.get('vertion', "1"))
                data['vertion'] = str(v + 1)
            except:
                data['vertion'] = "1"

        data['updated_at'] = datetime.now().isoformat()

        filename = f"{journal_id}.json"
        path = os.path.join(self.journals_dir, filename)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)

        return journal_id

    def delete_journal(self, journal_id):
        filename = f"{journal_id}.json"
        path = os.path.join(self.journals_dir, filename)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def get_journal_by_name(self, name):
        for j in self.list_journals():
            if j.get('nombre') == name:
                return j
        return None

    def toggle_state(self, journal_id):
        filename = f"{journal_id}.json"
        path = os.path.join(self.journals_dir, filename)
        if not os.path.exists(path):
            return False

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        if data.get('estado') == "borrador":
            data['estado'] = "guardado"
        else:
            data['estado'] = "borrador"

        # Increment version for state change too? Requirement says "por cada modificacion"
        try:
            v = int(data.get('vertion', "1"))
            data['vertion'] = str(v + 1)
        except:
            data['vertion'] = "1"

        data['updated_at'] = datetime.now().isoformat()

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        return True

    def categorize_journals(self):
        journals = self.list_journals()
        # Sort by fecha_esperada
        journals.sort(key=lambda x: x.get('fecha_esperada', ""))

        borradores = []
        pendientes = []
        vencidos = []

        today = datetime.now().date()

        for j in journals:
            estado = j.get('estado')
            fecha_str = j.get('fecha_esperada', "")
            try:
                fecha = datetime.strptime(fecha_str, "%Y-%m-%d").date()
            except:
                fecha = None

            if estado == "borrador":
                borradores.append(j)
            elif estado == "guardado":
                if fecha and fecha < today:
                    vencidos.append(j)
                else:
                    pendientes.append(j)
            else:
                # Default to borradores if state is unknown?
                borradores.append(j)

        return borradores, pendientes, vencidos
