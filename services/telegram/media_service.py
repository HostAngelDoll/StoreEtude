class TelegramMediaService:
    def __init__(self, client_manager):
        self.client_manager = client_manager

    async def fetch_chats(self):
        client = await self.client_manager.get_client()
        if not client or not await client.is_user_authorized():
            return []

        dialogs = await client.get_dialogs()
        return [{"id": d.id, "name": d.name or "Sin nombre"} for d in dialogs]

    async def fetch_videos(self, chat_id, limit=5):
        client = await self.client_manager.get_client()
        if not client or not await client.is_user_authorized():
            return []

        videos = []
        async for msg in client.iter_messages(chat_id):
            if msg.video:
                videos.append({
                    "id": msg.id,
                    "date": msg.date.isoformat() if msg.date else "",
                    "text": msg.message or "",
                    "file_name": msg.file.name if msg.file and msg.file.name else "video.mp4",
                    "size": msg.file.size if msg.file else 0
                })
                if len(videos) >= limit: break
        return videos

    async def download_video(self, chat_id, message_id, dest_path, progress_callback=None):
        client = await self.client_manager.get_client()
        if not client or not await client.is_user_authorized():
            return False, "Not authorized"

        try:
            msg = await client.get_messages(chat_id, ids=message_id)
            await client.download_media(msg, file=dest_path, progress_callback=progress_callback)
            return True, dest_path
        except Exception as e:
            return False, str(e)
