from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.repositories.lead_repository import ILeadRepository
from app.domain.use_cases.speech_use_case import ISpeechService
from app.domain.use_cases.telegram_use_case import ITelegramService
from app.infrastructure.schemas.telegram_schema import TelegramUpdate

FALLBACK_MESSAGE = (
    "I'm having a little trouble right now. "
    "Please try again in a moment or contact us directly."
)


class MessageProcessingService:
    def __init__(
        self,
        lead_repo: ILeadRepository,
        speech_service: ISpeechService,
        telegram_service: ITelegramService,
        agent_graph,
        langfuse_handler,
        db_session: AsyncSession,
    ) -> None:
        self.lead_repo = lead_repo
        self.speech_service = speech_service
        self.telegram_service = telegram_service
        self.agent_graph = agent_graph
        self.langfuse_handler = langfuse_handler
        self.db_session = db_session

    async def receive_message(self, update: TelegramUpdate) -> None:
        if not update.message:
            return

        message = update.message
        chat_id = message.chat_id
        is_voice = message.voice is not None

        try:
            lead = await self.lead_repo.get_or_create(chat_id)

            if is_voice:
                audio_bytes = await self.telegram_service.download_voice(message.voice.file_id)
                user_text = await self.speech_service.transcribe(audio_bytes, "ogg")
            else:
                user_text = message.text or ""

            if not user_text.strip():
                return

            config = {
                "configurable": {"thread_id": str(lead.id)},
                "callbacks": [self.langfuse_handler],
            }
            result = await self.agent_graph.ainvoke(
                {"messages": [HumanMessage(content=user_text)]},
                config=config,
            )
            response_text = result["messages"][-1].content

            if is_voice:
                audio_response = await self.speech_service.synthesize(response_text)
                await self.telegram_service.send_voice(chat_id, audio_response)
            else:
                await self.telegram_service.send_text(chat_id, response_text)

            lead.last_contacted_at = datetime.now(timezone.utc)
            await self.lead_repo.update(lead)

        except Exception:
            await self.telegram_service.send_text(chat_id, FALLBACK_MESSAGE)
