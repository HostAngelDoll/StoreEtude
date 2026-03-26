from enum import Enum

class AppMode(Enum):
    ONLINE = "online"
    OFFLINE = "offline"

class AppState:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppState, cls).__new__(cls)
            cls._instance.mode = AppMode.ONLINE
            cls._instance.reconnecting = False
        return cls._instance
