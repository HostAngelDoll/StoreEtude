import os
import uvicorn
import time
from fastapi import FastAPI, HTTPException, Query, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from PyQt6.QtCore import QThread, pyqtSignal
from datetime import datetime

from core.config_manager import ConfigManager
from core.whitelist_manager import WhitelistManager
from journals_manager.journal_logic import JournalManager
from core.db_manager_utils import get_base_dir_path

class APIServerThread(QThread):
    log_message = pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()
        self.config = ConfigManager()
        self.whitelist_manager = WhitelistManager()
        self.journal_manager = JournalManager()
        self.app = FastAPI(title="StoreEtude API")
        self._setup_logging()
        self._setup_routes()
        self.running = False
        self.server = None

    def _is_allowed(self):
        enabled = self.config.get("security.whitelist_enabled", False)
        if not enabled:
            return True
        # Note: whitelist_manager.check_connection_status() currently checks
        # the network state of the machine running StoreEtude, NOT the client IP.
        # This is preserved as per existing logic, but made accessible via FastAPI.
        return self.whitelist_manager.check_connection_status() == "accepted"

    def _is_drive_connected(self):
        base_dir = self.config.get("base_dir_path")
        return os.path.exists(base_dir)

    def _check_allowed_dependency(self, request: Request):
        if not self._is_allowed():
            raise HTTPException(status_code=403, detail="Unauthorized network")

    def _check_drive_dependency(self):
        if not self._is_drive_connected():
            raise HTTPException(status_code=503, detail="External drive disconnected. Resource exposure unavailable.")

    def _setup_logging(self):
        @self.app.middleware("http")
        async def log_requests(request: Request, call_next):
            # Block EVERYTHING if network not allowed
            if not self._is_allowed():
                method = request.method
                path = request.url.path
                log_msg = f"[{method}] {path} -> 403 (Acceso denegado: Red no confiable)"
                self.log_message.emit(log_msg, True)
                return JSONResponse(status_code=403, content={"detail": "Unauthorized network"})

            start_time = time.time()
            response = await call_next(request)

            # Format: [GET] /downloads?path=/xxx -> 200
            method = request.method
            path = request.url.path
            query = request.url.query
            status_code = response.status_code

            full_path = f"{path}?{query}" if query else path
            log_msg = f"[{method}] {full_path} -> {status_code}"

            # Emit log via signal. status >= 400 is considered error for coloring
            self.log_message.emit(log_msg, status_code >= 400)

            return response

    def _setup_routes(self):
        @self.app.get("/ping")
        async def ping():
            return {
                "name": "StoreEtude",
                "version": "1.0"
            }

        @self.app.get("/health")
        async def health():
            is_connected = self._is_drive_connected()
            return {
                "status": "ok" if is_connected else "error",
                "storage": "available" if is_connected else "unavailable"
            }

        @self.app.get("/journals_sync")
        @self.app.get("/jorunals_sync")  # Support the typo version too
        async def journals_sync(_=Depends(self._check_allowed_dependency)):
            try:
                journals = self.journal_manager.list_journals()

                total_version_sum = 0
                last_update = ""
                max_dt = None

                for j in journals:
                    # 'vertion' is misspelled in the original logic, keeping it for compatibility
                    try:
                        v = int(j.get("vertion", "0"))
                        total_version_sum += v
                    except:
                        pass

                    upd = j.get("updated_at", "")
                    if upd:
                        try:
                            dt = datetime.fromisoformat(upd)
                            if max_dt is None or dt > max_dt:
                                max_dt = dt
                                last_update = upd
                        except:
                            pass

                # The 'version' should change if any journal is added, removed or updated.
                # We use a combination of the sum of versions, the count, and the latest timestamp.
                global_version = total_version_sum + len(journals)
                if max_dt:
                    global_version += int(max_dt.timestamp())

                return {
                    "version": global_version,
                    "last_update": last_update,
                    "journals": journals
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

        @self.app.get("/journal/{journal_id}")
        async def get_journal(journal_id: str, _=Depends(self._check_allowed_dependency)):
            journal = self.journal_manager.get_journal(journal_id)
            if not journal:
                raise HTTPException(status_code=404, detail="Journal not found")
            return journal

        @self.app.put("/journal/{journal_id}")
        async def update_journal(journal_id: str, request: Request, _=Depends(self._check_allowed_dependency)):
            try:
                data = await request.json()
                material_updates = data.get("materiales")
                if material_updates is None:
                    raise HTTPException(status_code=400, detail="Missing 'materiales' in request body")

                if not isinstance(material_updates, list):
                    raise HTTPException(status_code=400, detail="'materiales' must be a list")

                success = self.journal_manager.update_journal_progress(journal_id, material_updates)
                if not success:
                    # Could be not found or other error
                    if not self.journal_manager.get_journal(journal_id):
                        raise HTTPException(status_code=404, detail="Journal not found")
                    raise HTTPException(status_code=500, detail="Failed to update journal")

                return {"status": "success"}
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid JSON or request: {str(e)}")

        @self.app.get("/downloads")
        async def download_file(
            path: str = Query(..., description="Virtual path of the file"),
            _=Depends(self._check_allowed_dependency),
            __=Depends(self._check_drive_dependency)
        ):
            base_dir = os.path.normpath(get_base_dir_path())

            # Normalize and validate path
            # Remove leading slash and backslashes for consistency
            clean_path = path.lstrip("/\\").replace("\\", "/")
            full_path = os.path.normpath(os.path.join(base_dir, clean_path))

            # Security check: ensure full_path is within base_dir
            try:
                if os.path.commonpath([full_path, base_dir]) != base_dir:
                    raise HTTPException(status_code=400, detail="Invalid path traversal attempt")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid path")

            if not os.path.isfile(full_path):
                raise HTTPException(status_code=404, detail="File not found")

            return FileResponse(full_path)

        @self.app.get("/downloads/list")
        @self.app.get("/download/list") # Support both as requested in different parts of prompt
        async def list_downloads(
            path: str = Query(..., alias="path", description="Virtual path of the directory"),
            _=Depends(self._check_allowed_dependency),
            __=Depends(self._check_drive_dependency)
        ):
            base_dir = os.path.normpath(get_base_dir_path())

            clean_path = path.lstrip("/\\").replace("\\", "/")
            full_dir = os.path.normpath(os.path.join(base_dir, clean_path))

            # Security check
            try:
                if os.path.commonpath([full_dir, base_dir]) != base_dir:
                    raise HTTPException(status_code=400, detail="Invalid path traversal attempt")
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid path")

            if not os.path.isdir(full_dir):
                raise HTTPException(status_code=404, detail="Directory not found")

            allowed_exts = {'.mp4', '.mkv', '.avi', '.webm', '.txt', '.md'}

            files = []
            try:
                for entry in os.scandir(full_dir):
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in allowed_exts:
                            files.append({
                                "name": entry.name,
                                "size": entry.stat().st_size
                            })

                return {
                    "path": path,
                    "files": files
                }
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))

    def run(self):
        self.config.load()

        # Security check before starting
        if not self._is_allowed():
            self.log_message.emit("No se puede iniciar el servidor: Red actual no está en la lista blanca.", True)
            self.running = False
            return

        port = self.config.get("api.port", 9090)
        self.running = True

        # We need a low-level way to run uvicorn that we can stop
        config = uvicorn.Config(app=self.app, host="0.0.0.0", port=port, log_level="info")
        self.server = uvicorn.Server(config)

        try:
            self.log_message.emit(f"Servidor API iniciado en http://0.0.0.0:{port}", False)
            self.server.run()
        except Exception as e:
            self.log_message.emit(f"Error en Servidor API: {e}", True)
        finally:
            self.running = False
            self.log_message.emit("Servidor API detenido.", False)

    def stop(self):
        if self.server:
            self.server.should_exit = True
