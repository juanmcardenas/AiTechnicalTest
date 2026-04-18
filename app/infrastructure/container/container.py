from functools import lru_cache
from fastapi import Request
from langfuse.callback import CallbackHandler
from app.config import settings
from app.infrastructure.database.engine import AsyncSessionFactory
from app.infrastructure.events.openai_adapter import OpenAIAdapter
from app.infrastructure.events.telegram_adapter import TelegramAdapter
from app.infrastructure.events.calendar_adapter import CalendarAdapter
from app.infrastructure.events.gmail_adapter import GmailAdapter
from app.infrastructure.repositories.inventory_repo import InventoryRepository
from app.infrastructure.repositories.lead_repo import LeadRepository
from app.infrastructure.repositories.meeting_repo import MeetingRepository
from app.infrastructure.repositories.email_log_repo import EmailLogRepository
from app.application.services.tools.get_inventory import make_get_inventory_tool
from app.application.services.tools.get_calendar_events import make_get_calendar_events_tool
from app.application.services.tools.schedule_meeting import make_schedule_meeting_tool
from app.application.services.tools.send_email import make_send_email_tool
from app.application.services.agent_graph import build_agent_graph
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
    session = AsyncSessionFactory()
    inventory_repo = InventoryRepository(session)
    lead_repo = LeadRepository(session)
    meeting_repo = MeetingRepository(session)
    email_log_repo = EmailLogRepository(session)

    gmail_adapter = GmailAdapter(email_log_repo)
    calendar_adapter = get_calendar_adapter()
    speech_service = get_openai_adapter()
    telegram_service = get_telegram_adapter()

    tools = [
        make_get_inventory_tool(inventory_repo),
        make_get_calendar_events_tool(calendar_adapter),
        make_schedule_meeting_tool(meeting_repo, lead_repo, calendar_adapter),
        make_send_email_tool(inventory_repo, gmail_adapter, email_log_repo),
    ]

    checkpointer = request.app.state.checkpointer
    agent = build_agent_graph(checkpointer=checkpointer, tools=tools)

    return MessageProcessingService(
        lead_repo=lead_repo,
        speech_service=speech_service,
        telegram_service=telegram_service,
        agent_graph=agent,
        langfuse_handler=get_langfuse_handler(),
        db_session=session,
    )
