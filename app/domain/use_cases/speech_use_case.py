from abc import ABC, abstractmethod


class ISpeechService(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, file_format: str = "ogg") -> str: ...

    @abstractmethod
    async def synthesize(self, text: str) -> bytes: ...
