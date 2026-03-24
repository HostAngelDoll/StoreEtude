import os
import asyncio
import threading
from PyQt6.QtCore import QObject, pyqtSignal, QThread, QMetaObject, Qt
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from config_manager import ConfigManager

class TelegramManager(QObject):
    connection_status = pyqtSignal(str, bool)
    auth_required = pyqtSignal(str)  # "phone", "code", "password"
    chats_loaded = pyqtSignal(list)
    videos_loaded = pyqtSignal(list)
    download_progress = pyqtSignal(float, str)
    download_finished = pyqtSignal(bool, str)

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(TelegramManager, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        super().__init__()
        self.config = ConfigManager()
        self.client = None
        self.loop = asyncio.new_event_loop()

        # Using QThread for better integration with Qt event loop and signals
        self.worker_thread = TelegramWorkerThread(self.loop)
        self.worker_thread.start()

        self._auth_future = None
        self._initialized = True

    def _emit_safe(self, signal, *args):
        """Helper to emit signals from the background thread to the GUI thread safely."""
        QMetaObject.invokeMethod(
            self,
            lambda: signal.emit(*args),
            Qt.ConnectionType.QueuedConnection
        )

    def run_coro(self, coro):
        future = asyncio.run_coroutine_threadsafe(coro, self.loop)

        def handle_result(f):
            try:
                f.result()
            except Exception as e:
                print(f"TelegramManager Coroutine error: {e}")
                # Use _emit_safe if we want to report this to UI

        future.add_done_callback(handle_result)
        return future

    async def _get_client(self):
        api_id = self.config.get("telegram.api_id")
        api_hash = self.config.get("telegram.api_hash")

        if not api_id or not api_hash:
            return None

        try:
            api_id_int = int(api_id)
        except (ValueError, TypeError):
            return None

        session_path = os.path.join(os.path.dirname(self.config.config_path), "session_telegram")

        if self.client is None:
            self.client = TelegramClient(session_path, api_id_int, api_hash)
        return self.client

    def connect(self):
        self.run_coro(self._connect_async())

    async def _connect_async(self):
        client = await self._get_client()
        if not client:
            self.connection_status.emit("Faltan API ID/Hash", False)
            return

        try:
            if not client.is_connected():
                await client.connect()

            if not await client.is_user_authorized():
                # We use a simplified sign in flow to handle UI interaction
                self._emit_safe(self.auth_required, "phone")
                return

            me = await client.get_me()
            name = (me.first_name or "") + (" " + me.last_name if me.last_name else "")
            self._emit_safe(self.connection_status, f"Conectado como {name}", True)
        except Exception as e:
            self._emit_safe(self.connection_status, f"Error: {str(e)}", False)

    def submit_phone(self, phone):
        self.run_coro(self._submit_phone_async(phone))

    async def _submit_phone_async(self, phone):
        client = await self._get_client()
        try:
            self._phone_code_hash = (await client.send_code_request(phone)).phone_code_hash
            self._current_phone = phone
            self._emit_safe(self.auth_required, "code")
        except Exception as e:
            self._emit_safe(self.connection_status, f"Error (phone): {str(e)}", False)

    def submit_code(self, code):
        self.run_coro(self._submit_code_async(code))

    async def _submit_code_async(self, code):
        client = await self._get_client()
        try:
            await client.sign_in(self._current_phone, code, phone_code_hash=self._phone_code_hash)
            await self._connect_async()
        except SessionPasswordNeededError:
            self._emit_safe(self.auth_required, "password")
        except Exception as e:
            self._emit_safe(self.connection_status, f"Error (code): {str(e)}", False)

    def submit_password(self, password):
        self.run_coro(self._submit_password_async(password))

    async def _submit_password_async(self, password):
        client = await self._get_client()
        try:
            await client.sign_in(password=password)
            await self._connect_async()
        except Exception as e:
            self._emit_safe(self.connection_status, f"Error (pw): {str(e)}", False)

    def fetch_chats(self):
        self.run_coro(self._fetch_chats_async())

    async def _fetch_chats_async(self):
        client = await self._get_client()
        if not client or not await client.is_user_authorized():
            return

        try:
            dialogs = await client.get_dialogs()
            chat_list = []
            for d in dialogs:
                chat_list.append({
                    'id': d.id,
                    'name': d.name or "Sin nombre"
                })
            self._emit_safe(self.chats_loaded, chat_list)
        except Exception as e:
            print(f"Error fetching chats: {e}")
            self._emit_safe(self.connection_status, f"Error al obtener chats: {str(e)}", True)

    def fetch_videos(self, chat_id, limit=5):
        self.run_coro(self._fetch_videos_async(chat_id, limit))

    async def _fetch_videos_async(self, chat_id, limit):
        client = await self._get_client()
        if not client or not await client.is_user_authorized():
            return

        videos = []
        try:
            async for msg in client.iter_messages(chat_id):
                if msg.video:
                    videos.append({
                        'id': msg.id,
                        'date': msg.date.isoformat() if msg.date else "",
                        'text': msg.message or "",
                        'file_name': msg.file.name if msg.file else "video.mp4",
                        'size': msg.file.size if msg.file else 0
                    })
                    if len(videos) >= limit:
                        break
            self._emit_safe(self.videos_loaded, videos)
        except Exception as e:
            print(f"Error fetching videos: {e}")
            self._emit_safe(self.download_finished, False, f"Error al obtener videos: {str(e)}")

    def download_video(self, chat_id, message_id, dest_path):
        self.run_coro(self._download_video_async(chat_id, message_id, dest_path))

    async def _download_video_async(self, chat_id, message_id, dest_path):
        client = await self._get_client()
        if not client or not await client.is_user_authorized():
            self.download_finished.emit(False, "No autorizado")
            return

        try:
            msg = await client.get_messages(chat_id, ids=message_id)

            def progress_callback(current, total):
                perc = current / total if total else 0
                mb_curr = current / (1024 * 1024)
                mb_tot = total / (1024 * 1024)
                self._emit_safe(self.download_progress, perc, f"Descargando... {mb_curr:.1f}MB / {mb_tot:.1f}MB")

            await client.download_media(msg, file=dest_path, progress_callback=progress_callback)
            self._emit_safe(self.download_finished, True, dest_path)
        except Exception as e:
            self._emit_safe(self.download_finished, False, str(e))

    def disconnect(self):
        if self.client:
            self.run_coro(self.client.disconnect())
            self.client = None
            self._emit_safe(self.connection_status, "Desconectado", False)

    def shutdown(self):
        """Cleanly shutdown the loop and thread."""
        if self.client:
            asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)

        if self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

        if self.worker_thread.isRunning():
            self.worker_thread.quit()
            self.worker_thread.wait(1000)

class TelegramWorkerThread(QThread):
    def __init__(self, loop):
        super().__init__()
        self.loop = loop

    def run(self):
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_forever()
        except Exception as e:
            print(f"TelegramManager loop error: {e}")
