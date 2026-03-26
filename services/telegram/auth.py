from telethon.errors import SessionPasswordNeededError

class TelegramAuthService:
    def __init__(self, client_manager):
        self.client_manager = client_manager
        self.phone_code_hash = None
        self.current_phone = None

    async def send_code(self, phone):
        client = await self.client_manager.get_client()
        if not client: return False
        result = await client.send_code_request(phone)
        self.phone_code_hash = result.phone_code_hash
        self.current_phone = phone
        return True

    async def sign_in(self, code):
        client = await self.client_manager.get_client()
        if not client: return "error"
        try:
            await client.sign_in(
                phone=self.current_phone,
                code=code,
                phone_code_hash=self.phone_code_hash
            )
            return "ok"
        except SessionPasswordNeededError:
            return "password_required"
        except:
            return "error"

    async def sign_in_password(self, password):
        client = await self.client_manager.get_client()
        if not client: return False
        try:
            await client.sign_in(password=password)
            return True
        except:
            return False
