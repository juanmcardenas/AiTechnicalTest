from abc import ABC, abstractmethod


class ITelegramService(ABC):
    @abstractmethod
    async def send_text(self, chat_id: str, text: str) -> None: ...

    @abstractmethod
    async def send_voice(self, chat_id: str, audio_bytes: bytes) -> None: ...

    @abstractmethod
    async def download_voice(self, file_id: str) -> bytes: ...

    @abstractmethod
    async def set_webhook(self, url: str) -> None: ...
