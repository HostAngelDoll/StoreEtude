import asyncio
import threading
from PyQt6.QtCore import QThread, pyqtSignal, QObject
from services.telegram.client import TelegramClientManager
from services.telegram.auth import TelegramAuthService
from services.telegram.media_service import TelegramMediaService

class TelegramLoopThread(QThread):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = None
        self._ready = threading.Event()

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._ready.set()
        try: self.loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(self.loop)
                for task in pending: task.cancel()
                if pending: self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except: pass
            finally:
                try: self.loop.close()
                except: pass

    def wait_until_ready(self, timeout=3.0):
        return self._ready.wait(timeout)

    def submit(self, coro):
        if not self.loop or not self.loop.is_running():
            raise RuntimeError("Telegram event loop is not active.")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop_loop(self):
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

class TelegramWorker(QObject):
    connection_status = pyqtSignal(str, bool)
    auth_required = pyqtSignal(str)
    chats_loaded = pyqtSignal(list)
    videos_loaded = pyqtSignal(list)
    download_progress = pyqtSignal(float, str)
    download_finished = pyqtSignal(bool, str)

    def __init__(self, api_id, api_hash, session_path):
        super().__init__()
        self.client_manager = TelegramClientManager(api_id, api_hash, session_path)
        self.auth_service = TelegramAuthService(self.client_manager)
        self.media_service = TelegramMediaService(self.client_manager)

        self.loop_thread = TelegramLoopThread()
        self.loop_thread.start()
        self.loop_thread.wait_until_ready()

    def _submit(self, coro):
        return self.loop_thread.submit(coro)

    def connect(self):
        self._submit(self._connect_async())

    async def _connect_async(self):
        try:
            if await self.client_manager.connect():
                if not await self.client_manager.is_authorized():
                    self.connection_status.emit("Requiere autenticación", False)
                    self.auth_required.emit("phone")
                    return

                me = await self.client_manager.get_me()
                name = ((me.first_name or "") + (" " + me.last_name if me.last_name else "")).strip()
                self.connection_status.emit(f"Conectado como {name or 'usuario'}", True)
            else:
                self.connection_status.emit("Faltan API ID / API Hash", False)
        except Exception as e:
            self.connection_status.emit(f"Error al conectar: {e}", False)

    def submit_phone(self, phone):
        self._submit(self._submit_phone_async(phone))

    async def _submit_phone_async(self, phone):
        if await self.auth_service.send_code(phone):
            self.auth_required.emit("code")
        else:
            self.connection_status.emit("Error al enviar código", False)

    def submit_code(self, code):
        self._submit(self._submit_code_async(code))

    async def _submit_code_async(self, code):
        res = await self.auth_service.sign_in(code)
        if res == "ok": await self._connect_async()
        elif res == "password_required": self.auth_required.emit("password")
        else: self.connection_status.emit("Error al validar código", False)

    def submit_password(self, password):
        self._submit(self._submit_password_async(password))

    async def _submit_password_async(self, password):
        if await self.auth_service.sign_in_password(password):
            await self._connect_async()
        else:
            self.connection_status.emit("Error al validar contraseña", False)

    def fetch_chats(self):
        self._submit(self._fetch_chats_async())

    async def _fetch_chats_async(self):
        chats = await self.media_service.fetch_chats()
        self.chats_loaded.emit(chats)

    def fetch_videos(self, chat_id, limit=5):
        self._submit(self._fetch_videos_async(chat_id, limit))

    async def _fetch_videos_async(self, chat_id, limit):
        videos = await self.media_service.fetch_videos(chat_id, limit)
        self.videos_loaded.emit(videos)

    def download_video(self, chat_id, message_id, dest_path):
        self._submit(self._download_video_async(chat_id, message_id, dest_path))

    async def _download_video_async(self, chat_id, message_id, dest_path):
        def progress(current, total):
            percent = (current / total) if total else 0.0
            mb_curr = current / (1024 * 1024)
            mb_total = total / (1024 * 1024) if total else 0.0
            self.download_progress.emit(percent, f"Descargando... {mb_curr:.1f} MB / {mb_total:.1f} MB")

        success, res = await self.media_service.download_video(chat_id, message_id, dest_path, progress)
        self.download_finished.emit(success, res)

    def disconnect(self):
        self._submit(self.client_manager.disconnect())

    def shutdown(self):
        self.disconnect()
        self.loop_thread.stop_loop()
        self.loop_thread.wait(2000)
