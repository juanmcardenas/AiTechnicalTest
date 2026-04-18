import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from langchain_core.messages import AIMessage, HumanMessage
from app.domain.entities.lead import Lead, LeadStatus
from app.infrastructure.schemas.telegram_schema import TelegramUpdate, Message
from app.application.services.message_processor import MessageProcessingService


@pytest.fixture
def sample_lead():
    return Lead(
        id="lead-1", telegram_chat_id="12345", name="Alice",
        phone=None, email=None, status=LeadStatus.NEW,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
    )


@pytest.fixture
def text_update():
    return TelegramUpdate(
        update_id=1,
        message=Message(
            message_id=1,
            chat={"id": 12345},
            text="Show me red cars",
        ),
    )


@pytest.fixture
def voice_update():
    return TelegramUpdate(
        update_id=2,
        message=Message(
            message_id=2,
            chat={"id": 12345},
            voice={"file_id": "file123", "file_unique_id": "uq123", "duration": 3},
        ),
    )


@pytest.fixture
def processor(sample_lead):
    lead_repo = AsyncMock()
    lead_repo.get_or_create.return_value = sample_lead
    lead_repo.update.return_value = sample_lead

    speech_service = AsyncMock()
    speech_service.transcribe.return_value = "Show me red cars"
    speech_service.synthesize.return_value = b"audio_bytes"

    telegram_service = AsyncMock()

    agent_graph = AsyncMock()
    agent_graph.ainvoke.return_value = {
        "messages": [HumanMessage(content="Show me red cars"), AIMessage(content="Here are red cars")]
    }

    db_session = AsyncMock()

    return MessageProcessingService(
        lead_repo=lead_repo,
        speech_service=speech_service,
        telegram_service=telegram_service,
        agent_graph=agent_graph,
        langfuse_handler=MagicMock(),
        db_session=db_session,
    )


async def test_text_message_sends_text_reply(processor, text_update):
    await processor.receive_message(text_update)
    processor.telegram_service.send_text.assert_called_once_with("12345", "Here are red cars")
    processor.telegram_service.send_voice.assert_not_called()


async def test_voice_message_transcribes_and_replies_with_voice(processor, voice_update):
    processor.telegram_service.download_voice = AsyncMock(return_value=b"ogg_bytes")
    processor.speech_service.transcribe = AsyncMock(return_value="Show me red cars")
    await processor.receive_message(voice_update)
    processor.speech_service.transcribe.assert_called_once_with(b"ogg_bytes", "ogg")
    processor.telegram_service.send_voice.assert_called_once()


async def test_updates_lead_last_contacted(processor, text_update):
    await processor.receive_message(text_update)
    processor.lead_repo.update.assert_called_once()
    updated_lead = processor.lead_repo.update.call_args[0][0]
    assert updated_lead.last_contacted_at is not None
