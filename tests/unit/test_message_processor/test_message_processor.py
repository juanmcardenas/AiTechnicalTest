import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
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


class _FakeSessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *a):
        return None


@pytest.fixture
def lead_repo_mock(sample_lead):
    repo = AsyncMock()
    repo.get_or_create.return_value = sample_lead
    repo.update.return_value = sample_lead
    return repo


@pytest.fixture
def agent_graph_mock():
    agent = AsyncMock()
    agent.ainvoke.return_value = {
        "messages": [HumanMessage(content="Show me red cars"), AIMessage(content="Here are red cars")]
    }
    return agent


@pytest.fixture
def processor(lead_repo_mock, agent_graph_mock):
    session_factory = lambda: _FakeSessionCtx(AsyncMock())

    speech_service = AsyncMock()
    speech_service.transcribe.return_value = "Show me red cars"
    speech_service.synthesize.return_value = b"audio_bytes"

    telegram_service = AsyncMock()
    calendar_service = AsyncMock()

    proc = MessageProcessingService(
        session_factory=session_factory,
        speech_service=speech_service,
        telegram_service=telegram_service,
        calendar_service=calendar_service,
        checkpointer=MagicMock(),
        langfuse_handler=MagicMock(),
    )
    proc._lead_repo_mock = lead_repo_mock
    proc._agent_mock = agent_graph_mock
    return proc


@pytest.fixture
def patched_processor(processor):
    """Patch LeadRepository and build_agent_graph so receive_message uses our mocks."""
    with patch("app.application.services.message_processor.LeadRepository", return_value=processor._lead_repo_mock), \
         patch("app.application.services.message_processor.InventoryRepository"), \
         patch("app.application.services.message_processor.MeetingRepository"), \
         patch("app.application.services.message_processor.EmailLogRepository"), \
         patch("app.application.services.message_processor.GmailAdapter"), \
         patch("app.application.services.message_processor.build_agent_graph", return_value=processor._agent_mock):
        yield processor


async def test_text_message_sends_text_reply(patched_processor, text_update):
    await patched_processor.receive_message(text_update)
    patched_processor.telegram_service.send_text.assert_called_once_with("12345", "Here are red cars")
    patched_processor.telegram_service.send_voice.assert_not_called()


async def test_voice_message_transcribes_and_replies_with_voice(patched_processor, voice_update):
    patched_processor.telegram_service.download_voice = AsyncMock(return_value=b"ogg_bytes")
    patched_processor.speech_service.transcribe = AsyncMock(return_value="Show me red cars")
    await patched_processor.receive_message(voice_update)
    patched_processor.speech_service.transcribe.assert_called_once_with(b"ogg_bytes", "ogg")
    patched_processor.telegram_service.send_voice.assert_called_once()


async def test_updates_lead_last_contacted(patched_processor, text_update):
    await patched_processor.receive_message(text_update)
    patched_processor._lead_repo_mock.update.assert_called_once()
    updated_lead = patched_processor._lead_repo_mock.update.call_args[0][0]
    assert updated_lead.last_contacted_at is not None
