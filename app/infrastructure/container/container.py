from functools import lru_cache
from fastapi import Request
from langfuse.callback import CallbackHandler
from app.config import settings
from app.infrastructure.database.engine import AsyncSessionFactory
from app.infrastructure.events.openai_adapter import OpenAIAdapter
from app.infrastructure.events.telegram_adapter import TelegramAdapter
from app.infrastructure.events.calendar_adapter import CalendarAdapter
from app.application.services.message_processor import MessageProcessingService


@lru_cache
def get_langfuse_handler() -> CallbackHandler:
    return CallbackHandler(
        secret_key=settings.langfuse_secret_key,
        public_key=settings.langfuse_public_key,
        host=settings.langfuse_host,
    )


@lru_cache
def get_telegram_adapter() -> TelegramAdapter:
    return TelegramAdapter()


@lru_cache
def get_openai_adapter() -> OpenAIAdapter:
    return OpenAIAdapter()


@lru_cache
def get_calendar_adapter() -> CalendarAdapter:
    return CalendarAdapter()


async def get_message_processor(request: Request) -> MessageProcessingService:
    return MessageProcessingService(
        session_factory=AsyncSessionFactory,
        speech_service=get_openai_adapter(),
        telegram_service=get_telegram_adapter(),
        calendar_service=get_calendar_adapter(),
        checkpointer=request.app.state.checkpointer,
        langfuse_handler=get_langfuse_handler(),
    )
