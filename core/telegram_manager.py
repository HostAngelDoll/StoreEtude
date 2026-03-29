import os
import asyncio
import threading

from PyQt6.QtCore import QObject, pyqtSignal, QThread, QCoreApplication
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from core.config_manager import ConfigManager


class TelegramLoopThread(QThread):
    """
    Hilo dedicado para ejecutar un event loop de asyncio.
    No usa el event loop de Qt; solo hospeda asyncio.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.loop = None
        self._ready = threading.Event()

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self._ready.set()

        try:
            self.loop.run_forever()
        finally:
            try:
                pending = asyncio.all_tasks(self.loop)
                for task in pending:
                    task.cancel()

                if pending:
                    self.loop.run_until_complete(
                        asyncio.gather(*pending, return_exceptions=True)
                    )
            except Exception:
                pass
            finally:
                try:
                    self.loop.close()
                except Exception:
                    pass

    def wait_until_ready(self, timeout=3.0):
        return self._ready.wait(timeout)

    def submit(self, coro):
        if not self.loop or not self.loop.is_running():
            raise RuntimeError("El event loop de Telegram no está activo.")
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def stop_loop(self):
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)


class TelegramManager(QObject):
    connection_status = pyqtSignal(str, bool)
    auth_required = pyqtSignal(str)          # "phone", "code", "password"
    chats_loaded = pyqtSignal(list)
    videos_loaded = pyqtSignal(list)
    download_progress = pyqtSignal(float, str)
    download_finished = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        super().__init__(parent)

        app = QCoreApplication.instance()
        if app is not None and QThread.currentThread() != app.thread():
            raise RuntimeError("TelegramManager debe instanciarse en el hilo principal de Qt.")

        self.config = ConfigManager()
        self.client = None
        self._current_phone = None
        self._phone_code_hash = None
        self._is_connected = False
        self._is_connecting = False
        self._last_status = "No conectado"

        self.worker_thread = TelegramLoopThread()
        self.worker_thread.start()

        if not self.worker_thread.wait_until_ready(3.0):
            raise RuntimeError("No se pudo iniciar el hilo de Telegram a tiempo.")

        # Attempt automatic connection on startup if credentials exist
        self.connect()

    def _submit(self, coro):
        try:
            return self.worker_thread.submit(coro)
        except Exception as e:
            self.connection_status.emit(f"Error interno: {e}", False)
            return None

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
            self.client = TelegramClient(
                session_path, 
                api_id_int, 
                api_hash,
                connection_retries=5,
                retry_delay=2
            )
                
        return self.client

    def connect(self):
        if self._is_connecting: return
        self._is_connecting = True
        self._last_status = "Conectando..."
        self.connection_status.emit(self._last_status, False)
        self._submit(self._connect_async())

    async def _ensure_connection(self):
        client = await self._get_client()
        if not client:
            return None

        if not client.is_connected():
            await client.connect()

        if not await client.is_user_authorized():
            self._is_connected = False
            self._last_status = "Requiere autenticación"
            self.connection_status.emit(self._last_status, False)
            self.auth_required.emit("phone")
            return None

        return client

    async def _connect_async(self):
        client = await self._get_client()
        if not client:
            self._last_status = "Faltan API ID / API Hash"
            self.connection_status.emit(self._last_status, False)
            return

        try:
            if not client.is_connected():
                await client.connect()

            if not await client.is_user_authorized():
                self._is_connected = False
                self._last_status = "Requiere autenticación"
                self.connection_status.emit(self._last_status, False)
                self.auth_required.emit("phone")
                return

            me = await client.get_me()
            name = ((me.first_name or "") + (" " + me.last_name if me.last_name else "")).strip()
            self._is_connected = True
            self._is_connecting = False
            self._last_status = f"Conectado como {name or 'usuario'}"
            self.connection_status.emit(self._last_status, True)

        except Exception as e:
            self._is_connected = False
            self._is_connecting = False
            self._last_status = f"Error al conectar: {e}"
            self.connection_status.emit(self._last_status, False)

    def submit_phone(self, phone):
        self._submit(self._submit_phone_async(phone))

    async def _submit_phone_async(self, phone):
        client = await self._get_client()
        if not client:
            self.connection_status.emit("Cliente no disponible", False)
            return

        try:
            result = await client.send_code_request(phone)
            self._phone_code_hash = result.phone_code_hash
            self._current_phone = phone
            self.auth_required.emit("code")
        except Exception as e:
            self.connection_status.emit(f"Error al enviar código: {e}", False)

    def submit_code(self, code):
        self._submit(self._submit_code_async(code))

    async def _submit_code_async(self, code):
        client = await self._get_client()
        if not client:
            self.connection_status.emit("Cliente no disponible", False)
            return

        try:
            await client.sign_in(
                phone=self._current_phone,
                code=code,
                phone_code_hash=self._phone_code_hash
            )
            await self._connect_async()
        except SessionPasswordNeededError:
            self.auth_required.emit("password")
        except Exception as e:
            self.connection_status.emit(f"Error al validar código: {e}", False)

    def submit_password(self, password):
        self._submit(self._submit_password_async(password))

    async def _submit_password_async(self, password):
        client = await self._get_client()
        if not client:
            self.connection_status.emit("Cliente no disponible", False)
            return

        try:
            await client.sign_in(password=password)
            await self._connect_async()
        except Exception as e:
            self.connection_status.emit(f"Error al validar contraseña: {e}", False)

    def fetch_chats(self):
        self._submit(self._fetch_chats_async())

    async def _fetch_chats_async(self):
        client = await self._ensure_connection()
        if not client:
            self._is_connected = False
            self._last_status = "No conectado o no autorizado"
            self.connection_status.emit(self._last_status, False)
            return

        try:
            dialogs = await client.get_dialogs()
            chat_list = []

            for d in dialogs:
                chat_list.append({
                    "id": d.id,
                    "name": d.name or "Sin nombre"
                })

            self.chats_loaded.emit(chat_list)

        except Exception as e:
            self.connection_status.emit(f"Error al obtener chats: {e}", False)

    def fetch_videos(self, chat_id, limit=5):
        self._submit(self._fetch_videos_async(chat_id, limit))

    async def _fetch_videos_async(self, chat_id, limit):
        client = await self._ensure_connection()
        if not client:
            self._is_connected = False
            self._last_status = "No conectado o no autorizado"
            self.connection_status.emit(self._last_status, False)
            return

        videos = []
        try:
            async for msg in client.iter_messages(chat_id):
                if msg.video:
                    videos.append({
                        "id": msg.id,
                        "date": msg.date.isoformat() if msg.date else "",
                        "text": msg.message or "",
                        "file_name": msg.file.name if msg.file and msg.file.name else "video.mp4",
                        "size": msg.file.size if msg.file else 0
                    })

                    if len(videos) >= limit:
                        break

            self.videos_loaded.emit(videos)

        except Exception as e:
            self.connection_status.emit(f"Error al obtener videos: {e}", False)

    def download_video(self, chat_id, message_id, dest_path):
        self._submit(self._download_video_async(chat_id, message_id, dest_path))

    async def _download_video_async(self, chat_id, message_id, dest_path):
        client = await self._ensure_connection()
        if not client:
            self.download_finished.emit(False, "No conectado o no autorizado")
            return

        try:
            msg = await client.get_messages(chat_id, ids=message_id)

            def progress_callback(current, total):
                percent = (current / total) if total else 0.0
                mb_curr = current / (1024 * 1024)
                mb_total = total / (1024 * 1024) if total else 0.0
                self.download_progress.emit(
                    percent,
                    f"Descargando... {mb_curr:.1f} MB / {mb_total:.1f} MB"
                )

            await client.download_media(
                msg,
                file=dest_path,
                progress_callback=progress_callback,
            )
            self.download_finished.emit(True, dest_path)

        except Exception as e:
            self.download_finished.emit(False, str(e))

    def disconnect(self):
        if self.client:
            self._submit(self._disconnect_async())

    async def _disconnect_async(self):
        try:
            if self.client:
                await self.client.disconnect()
        finally:
            self.client = None
            self._is_connected = False
            self._last_status = "Desconectado"
            self.connection_status.emit(self._last_status, False)

    def is_connected(self):
        return self._is_connected

    def is_connecting(self):
        return self._is_connecting

    def get_last_status(self):
        return self._last_status

    def reset_client(self):
        self._submit(self._reset_client_async())

    async def _reset_client_async(self):
        try:
            if self.client:
                await self.client.disconnect()
        finally:
            self.client = None
            self._is_connected = False
            self._is_connecting = False
            self.connect()

    def shutdown(self):
        """
        Cierra el cliente y detiene el hilo.
        Llama esto al cerrar la aplicación.
        """
        if self.worker_thread and self.worker_thread.isRunning():
            fut = self._submit(self._shutdown_async())
            try:
                if fut is not None:
                    fut.result(timeout=5)
            except Exception:
                pass

            self.worker_thread.stop_loop()
            self.worker_thread.wait(5000)

    async def _shutdown_async(self):
        try:
            if self.client:
                await self.client.disconnect()
        finally:
            self.client = None
