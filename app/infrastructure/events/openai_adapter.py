import io
from openai import AsyncOpenAI
from app.config import settings
from app.domain.use_cases.speech_use_case import ISpeechService


class OpenAIAdapter(ISpeechService):
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def transcribe(self, audio_bytes: bytes, file_format: str = "ogg") -> str:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{file_format}"
        response = await self._client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return response.text

    async def synthesize(self, text: str) -> bytes:
        response = await self._client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
        )
        return response.content
