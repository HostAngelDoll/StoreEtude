import json
import os
import time
import urllib.request
from core.api_server import APIServerThread
from journals_manager.journal_logic import JournalManager
from core.config_manager import ConfigManager
from PyQt6.QtCore import QCoreApplication
import sys

# Mocking enough to run the server in a script
app = QCoreApplication(sys.argv)

jm = JournalManager()
conf = ConfigManager()

# Create a dummy journal
jid = "test-journal-123"
jdata = {
    "id": jid,
    "nombre": "Test Journal",
    "fecha_esperada": "2024-01-01",
    "estado": "guardado",
    "vertion": "1",
    "materiales": [
        {
            "title_material": "Ep 1",
            "datetime_range_utc_06": ""
        },
        {
            "title_material": "Ep 2",
            "datetime_range_utc_06": ""
        }
    ]
}

# Save it manually
jpath = os.path.join(jm.journals_dir, f"{jid}.json")
with open(jpath, 'w', encoding='utf-8') as f:
    json.dump(jdata, f)

print(f"Created test journal at {jpath}")

# Start server in thread
server_thread = APIServerThread()
# Disable whitelist for test
conf.set("security.whitelist_enabled", False)
conf.set("api.port", 9999)

server_thread.start()
time.sleep(3) # Wait for server to start

try:
    # Test PUT
    url = f"http://127.0.0.1:9999/journal/{jid}"
    payload = {
        "materiales": [
            {"datetime_range_utc_06": "2024-01-01T10:00:00"},
            {"datetime_range_utc_06": "2024-01-01T11:00:00"}
        ]
    }

    print(f"Sending PUT to {url}...")
    req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), method='PUT')
    req.add_header('Content-Type', 'application/json')

    with urllib.request.urlopen(req) as response:
        res_body = json.loads(response.read().decode())
        print(f"Response: {response.status} {res_body}")

        if response.status == 200:
            # Verify file content
            with open(jpath, 'r', encoding='utf-8') as f:
                updated_data = json.load(f)
                print(f"Updated materials: {updated_data['materiales']}")
                print(f"Updated at: {updated_data['updated_at']}")
                print(f"Version: {updated_data['vertion']}")

                assert updated_data['materiales'][0]['datetime_range_utc_06'] == "2024-01-01T10:00:00"
                assert updated_data['vertion'] == "1"
                print("Verification SUCCESS")
        else:
            print("Verification FAILED")

except Exception as e:
    print(f"An error occurred: {e}")

finally:
    server_thread.stop()
    server_thread.wait()
    if os.path.exists(jpath):
        os.remove(jpath)
