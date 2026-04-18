import httpx
from app.config import settings
from app.domain.use_cases.telegram_use_case import ITelegramService

_BASE = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
_FILE_BASE = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}"


class TelegramAdapter(ITelegramService):
    async def send_text(self, chat_id: str, text: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{_BASE}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )

    async def send_voice(self, chat_id: str, audio_bytes: bytes) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{_BASE}/sendVoice",
                data={"chat_id": chat_id},
                files={"voice": ("voice.mp3", audio_bytes, "audio/mpeg")},
                timeout=30,
            )

    async def download_voice(self, file_id: str) -> bytes:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{_BASE}/getFile", params={"file_id": file_id}, timeout=10)
            file_path = r.json()["result"]["file_path"]
            audio = await client.get(f"{_FILE_BASE}/{file_path}", timeout=30)
            return audio.content

    async def set_webhook(self, url: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{_BASE}/setWebhook",
                json={"url": url, "allowed_updates": ["message"]},
                timeout=10,
            )
