from pydantic import BaseModel


class Voice(BaseModel):
    file_id: str
    file_unique_id: str
    duration: int
    mime_type: str | None = None
    file_size: int | None = None


class Message(BaseModel):
    message_id: int
    chat: dict
    text: str | None = None
    voice: Voice | None = None

    @property
    def chat_id(self) -> str:
        return str(self.chat["id"])


class TelegramUpdate(BaseModel):
    update_id: int
    message: Message | None = None
