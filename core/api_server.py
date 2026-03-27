import os
import json
import sqlite3
from flask import Flask, jsonify, send_file, request
from waitress import serve
from PyQt6.QtCore import QThread, pyqtSignal
from werkzeug.utils import secure_filename

from core.config_manager import ConfigManager
from core.whitelist_manager import WhitelistManager
from journals_manager.journal_logic import JournalManager
from core.db_manager_utils import get_yearly_db_path, get_base_dir_path, get_global_db_path

class APIServerThread(QThread):
    def __init__(self):
        super().__init__()
        self.app = Flask(__name__)
        self.config = ConfigManager()
        self.whitelist_manager = WhitelistManager()
        self.journal_manager = JournalManager()
        self._setup_routes()
        self.running = False

    def _is_allowed(self):
        enabled = self.config.get("security.whitelist_enabled", False)
        if not enabled:
            return True
        return self.whitelist_manager.check_connection_status() == "accepted"

    def _is_drive_connected(self):
        base_dir = self.config.get("base_dir_path")
        return os.path.exists(base_dir)

    def _setup_routes(self):
        @self.app.route('/files/<year>/<type_material>', methods=['GET'])
        def list_files(year, type_material):
            if not self._is_allowed():
                return jsonify({"error": "Unauthorized network"}), 403

            if not self._is_drive_connected():
                return jsonify({"error": "External drive disconnected. Resource exposure unavailable."}), 503

            db_path = get_yearly_db_path(year)
            if not os.path.exists(db_path):
                # Fallback to offline DB if exists
                from core.db_manager_utils import get_offline_db_path
                db_path = get_offline_db_path(db_path)
                if not os.path.exists(db_path):
                    return jsonify({"error": "Year not found"}), 404

            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                from core.db_manager_utils import get_offline_db_path
                g_path = get_global_db_path()
                if not os.path.exists(g_path):
                    g_path = get_offline_db_path(g_path)

                if os.path.exists(g_path):
                    cursor.execute(f"ATTACH DATABASE '{g_path}' AS global_db")
                else:
                    return jsonify({"error": "Global DB not found"}), 404

                query = """
                    SELECT r.relative_path_of_file, r.relative_path_of_soundtracks
                    FROM T_Resources r
                    JOIN global_db.T_Type_Resources t ON r.type_material = t.idx
                    WHERE t.type_resource = ?
                """
                cursor.execute(query, (type_material,))
                rows = cursor.fetchall()

                files = []
                base_dir = self.config.get("base_dir_path")
                for rel_file, rel_sd in rows:
                    if rel_file:
                        files.append(os.path.normpath(os.path.join(base_dir, str(year), rel_file)))
                    if rel_sd:
                        files.append(os.path.normpath(os.path.join(base_dir, str(year), rel_sd)))

                return jsonify(files)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
            finally:
                if 'conn' in locals():
                    conn.close()

        @self.app.route('/db/<year>', methods=['GET'])
        def get_db(year):
            if not self._is_allowed():
                return jsonify({"error": "Unauthorized network"}), 403

            db_path = get_yearly_db_path(year)
            if not os.path.exists(db_path):
                from core.db_manager_utils import get_offline_db_path
                db_path = get_offline_db_path(db_path)

            if os.path.exists(db_path):
                return send_file(db_path, as_attachment=True)
            return jsonify({"error": "Year DB not found"}), 404

        @self.app.route('/download/<year>/<type_material>/<filename>', methods=['GET'])
        def download_file(year, type_material, filename):
            if not self._is_allowed():
                return jsonify({"error": "Unauthorized network"}), 403

            if not self._is_drive_connected():
                return jsonify({"error": "External drive disconnected. Resource exposure unavailable."}), 503

            # Sanitization
            safe_name = secure_filename(filename)

            db_path = get_yearly_db_path(year)
            if not os.path.exists(db_path):
                from core.db_manager_utils import get_offline_db_path
                db_path = get_offline_db_path(db_path)
                if not os.path.exists(db_path):
                    return jsonify({"error": "Year not found"}), 404

            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                from core.db_manager_utils import get_offline_db_path
                g_path = get_global_db_path()
                if not os.path.exists(g_path):
                    g_path = get_offline_db_path(g_path)

                if os.path.exists(g_path):
                    cursor.execute(f"ATTACH DATABASE '{g_path}' AS global_db")
                else:
                    return jsonify({"error": "Global DB not found"}), 404

                # Find the relative path for this filename in this year/type
                # We check both relative_path_of_file and relative_path_of_soundtracks
                query = """
                    SELECT r.relative_path_of_file, r.relative_path_of_soundtracks
                    FROM T_Resources r
                    JOIN global_db.T_Type_Resources t ON r.type_material = t.idx
                    WHERE t.type_resource = ? AND (r.relative_path_of_file LIKE ? OR r.relative_path_of_soundtracks LIKE ?)
                """
                cursor.execute(query, (type_material, f"%{safe_name}", f"%{safe_name}"))
                row = cursor.fetchone()

                if not row:
                    return jsonify({"error": "File not found in registry"}), 404

                rel_path = None
                if row[0] and safe_name in row[0]: rel_path = row[0]
                elif row[1] and safe_name in row[1]: rel_path = row[1]

                if not rel_path:
                     return jsonify({"error": "File path mismatch"}), 404

                base_dir = self.config.get("base_dir_path")
                full_path = os.path.normpath(os.path.join(base_dir, str(year), rel_path))

                if os.path.exists(full_path):
                    return send_file(full_path, as_attachment=True)
                else:
                    return jsonify({"error": "Physical file not found", "path": full_path}), 404

            except Exception as e:
                return jsonify({"error": str(e)}), 500
            finally:
                if 'conn' in locals():
                    conn.close()

        @self.app.route('/journals', methods=['GET'])
        def list_journals():
            if not self._is_allowed():
                return jsonify({"error": "Unauthorized network"}), 403
            try:
                journals = self.journal_manager.list_journals()
                return jsonify(journals)
            except Exception as e:
                return jsonify({"error": str(e)}), 500

    def run(self):
        port = self.config.get("api.port", 9090)
        self.running = True
        try:
            serve(self.app, host='0.0.0.0', port=port)
        except Exception as e:
            print(f"API Server error: {e}")
        finally:
            self.running = False
