import logging
import traceback
from datetime import datetime, timezone
from typing import Callable

from langchain_core.messages import HumanMessage

from app.application.services.agent_graph import build_agent_graph
from app.application.services.tools.get_calendar_events import make_get_calendar_events_tool
from app.application.services.tools.get_inventory import make_get_inventory_tool
from app.application.services.tools.schedule_meeting import make_schedule_meeting_tool
from app.application.services.tools.send_email import make_send_email_tool
from app.application.services.tools.update_lead_identity import make_update_lead_identity_tool
from app.domain.entities.lead import Lead
from app.domain.use_cases.calendar_use_case import ICalendarService
from app.domain.use_cases.speech_use_case import ISpeechService
from app.domain.use_cases.telegram_use_case import ITelegramService
from app.infrastructure.events.gmail_adapter import GmailAdapter
from app.infrastructure.repositories.email_log_repo import EmailLogRepository
from app.infrastructure.repositories.inventory_repo import InventoryRepository
from app.infrastructure.repositories.lead_repo import LeadRepository
from app.infrastructure.repositories.meeting_repo import MeetingRepository
from app.infrastructure.repositories.session_repo import SessionRepository
from app.infrastructure.schemas.telegram_schema import TelegramUpdate

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "I'm having a little trouble right now. "
    "Please try again in a moment or contact us directly."
)


def _build_session_context(lead: Lead, is_new_session: bool) -> str:
    identity_bits = []
    if lead.name:
        identity_bits.append(f"name={lead.name}")
    if lead.email:
        identity_bits.append(f"email={lead.email}")
    if lead.phone:
        identity_bits.append(f"phone={lead.phone}")
    identity = ", ".join(identity_bits) if identity_bits else "(unknown)"
    state = "NEW" if is_new_session else "ongoing"
    return (
        "SESSION CONTEXT:\n"
        f"- This is a {state} session. Current customer identity: {identity}.\n"
        "- If the session is NEW and identity is (unknown), greet warmly and ask "
        "for name, email, or phone to personalise the conversation.\n"
        "- When the customer shares any contact info, call update_lead_identity "
        "immediately to save it.\n"
        "- For scheduling and emails, identity is required. If unidentified, ask "
        "for contact info before calling those tools.\n"
    )


class MessageProcessingService:
    def __init__(
        self,
        session_factory,
        speech_service: ISpeechService,
        telegram_service: ITelegramService,
        calendar_service: ICalendarService,
        checkpointer,
        langfuse_handler,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.session_factory = session_factory
        self.speech_service = speech_service
        self.telegram_service = telegram_service
        self.calendar_service = calendar_service
        self.checkpointer = checkpointer
        self.langfuse_handler = langfuse_handler
        self.now_fn = now_fn

    async def receive_message(self, update: TelegramUpdate) -> None:
        if not update.message:
            return

        message = update.message
        chat_id = message.chat_id
        is_voice = message.voice is not None

        try:
            async with self.session_factory() as db:
                lead_repo = LeadRepository(db)
                inventory_repo = InventoryRepository(db)
                meeting_repo = MeetingRepository(db)
                email_log_repo = EmailLogRepository(db)
                session_repo = SessionRepository(db)
                gmail_adapter = GmailAdapter()

                lead = await lead_repo.get_or_create(chat_id)

                now = self.now_fn()
                session = await session_repo.get_active_for_lead(lead.id, now)
                if session is None:
                    session = await session_repo.create(lead.id)
                    is_new_session = True
                else:
                    is_new_session = False
                await session_repo.touch(session.id, now)

                if is_voice:
                    audio_bytes = await self.telegram_service.download_voice(message.voice.file_id)
                    user_text = await self.speech_service.transcribe(audio_bytes, "ogg")
                else:
                    user_text = message.text or ""

                if not user_text.strip():
                    return

                tools = [
                    make_get_inventory_tool(inventory_repo),
                    make_get_calendar_events_tool(self.calendar_service),
                    make_schedule_meeting_tool(meeting_repo, lead_repo, self.calendar_service),
                    make_send_email_tool(inventory_repo, gmail_adapter, email_log_repo, lead_repo),
                    make_update_lead_identity_tool(lead_repo),
                ]
                session_ctx = _build_session_context(lead, is_new_session)
                agent = build_agent_graph(
                    checkpointer=self.checkpointer, tools=tools, session_ctx=session_ctx,
                )

                config = {
                    "configurable": {
                        "thread_id": str(session.id),
                        "lead_id": str(lead.id),
                    },
                    "callbacks": [self.langfuse_handler],
                }
                result = await agent.ainvoke(
                    {"messages": [HumanMessage(content=user_text)]},
                    config=config,
                )
                response_text = result["messages"][-1].content

                if is_voice:
                    audio_response = await self.speech_service.synthesize(response_text)
                    await self.telegram_service.send_voice(chat_id, audio_response)
                else:
                    await self.telegram_service.send_text(chat_id, response_text)

                lead.last_contacted_at = now
                await lead_repo.update(lead)

        except Exception as e:
            logger.exception("receive_message failed: %s", e)
            traceback.print_exc()
            await self.telegram_service.send_text(chat_id, FALLBACK_MESSAGE)
