from core.telegram_manager import TelegramManager

class TelegramService:
    def __init__(self):
        self._manager = TelegramManager()

    def get_manager(self):
        return self._manager

    def shutdown(self):
        self._manager.shutdown()

    def reset_client(self):
        if hasattr(self._manager, 'reset_client'):
            self._manager.reset_client()

    def fetch_videos(self, chat_id, limit=5):
        """
        Solicita al manager que busque videos en el chat especificado.
        """
        self._manager.fetch_videos(chat_id, limit)
