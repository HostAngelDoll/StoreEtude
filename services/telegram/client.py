import os
from telethon import TelegramClient

class TelegramClientManager:
    def __init__(self, api_id, api_hash, session_name):
        self.api_id = api_id
        self.api_hash = api_hash
        self.session_name = session_name
        self.client = None

    async def get_client(self):
        if self.client is None:
            if not self.api_id or not self.api_hash:
                return None
            try:
                api_id_int = int(self.api_id)
            except:
                return None
            self.client = TelegramClient(self.session_name, api_id_int, self.api_hash)
        return self.client

    async def connect(self):
        client = await self.get_client()
        if not client: return False
        if not client.is_connected():
            await client.connect()
        return True

    async def is_authorized(self):
        client = await self.get_client()
        if not client or not client.is_connected():
            return False
        return await client.is_user_authorized()

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def get_me(self):
        client = await self.get_client()
        if client:
            return await client.get_me()
        return None
