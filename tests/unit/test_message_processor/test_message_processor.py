from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.application.services.message_processor import MessageProcessingService
from app.domain.entities.lead import Lead, LeadStatus
from app.domain.entities.session import Session
from app.infrastructure.schemas.telegram_schema import Message, TelegramUpdate


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
        message=Message(message_id=1, chat={"id": 12345}, text="Show me red cars"),
    )


@pytest.fixture
def voice_update():
    return TelegramUpdate(
        update_id=2,
        message=Message(
            message_id=2, chat={"id": 12345},
            voice={"file_id": "file123", "file_unique_id": "uq123", "duration": 3},
        ),
    )


class _FakeSessionCtx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *a):
        return None


@pytest.fixture
def lead_repo_mock(sample_lead):
    repo = AsyncMock()
    repo.get_or_create.return_value = sample_lead
    repo.update.return_value = sample_lead
    return repo


@pytest.fixture
def session_repo_mock():
    repo = AsyncMock()
    repo.get_active_for_lead.return_value = None
    repo.create.return_value = Session(
        id="sess-1", lead_id="lead-1",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_message_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    repo.touch = AsyncMock()
    return repo


@pytest.fixture
def agent_graph_mock():
    agent = AsyncMock()
    agent.ainvoke.return_value = {
        "messages": [HumanMessage(content="Show me red cars"), AIMessage(content="Here are red cars")]
    }
    return agent


@pytest.fixture
def fixed_now():
    return datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def processor(lead_repo_mock, session_repo_mock, agent_graph_mock, fixed_now):
    proc = MessageProcessingService(
        session_factory=lambda: _FakeSessionCtx(AsyncMock()),
        speech_service=AsyncMock(),
        telegram_service=AsyncMock(),
        calendar_service=AsyncMock(),
        checkpointer=MagicMock(),
        langfuse_handler=MagicMock(),
        now_fn=lambda: fixed_now,
    )
    proc.speech_service.transcribe.return_value = "Show me red cars"
    proc.speech_service.synthesize.return_value = b"audio_bytes"
    proc._lead_repo_mock = lead_repo_mock
    proc._session_repo_mock = session_repo_mock
    proc._agent_mock = agent_graph_mock
    return proc


@pytest.fixture
def patched_processor(processor):
    with patch("app.application.services.message_processor.LeadRepository", return_value=processor._lead_repo_mock), \
         patch("app.application.services.message_processor.SessionRepository", return_value=processor._session_repo_mock), \
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


async def test_updates_lead_last_contacted(patched_processor, text_update, fixed_now):
    await patched_processor.receive_message(text_update)
    patched_processor._lead_repo_mock.update.assert_called_once()
    updated_lead = patched_processor._lead_repo_mock.update.call_args[0][0]
    assert updated_lead.last_contacted_at == fixed_now


async def test_creates_new_session_when_none_active(patched_processor, text_update):
    await patched_processor.receive_message(text_update)
    patched_processor._session_repo_mock.get_active_for_lead.assert_called_once()
    patched_processor._session_repo_mock.create.assert_called_once_with("lead-1")
    patched_processor._session_repo_mock.touch.assert_called_once()


async def test_reuses_active_session(patched_processor, text_update, fixed_now):
    existing = Session(
        id="existing-1", lead_id="lead-1",
        started_at=fixed_now - timedelta(minutes=2),
        last_message_at=fixed_now - timedelta(minutes=2),
        created_at=fixed_now - timedelta(minutes=2),
    )
    patched_processor._session_repo_mock.get_active_for_lead.return_value = existing
    await patched_processor.receive_message(text_update)
    patched_processor._session_repo_mock.create.assert_not_called()
    patched_processor._session_repo_mock.touch.assert_called_once()
    touch_args = patched_processor._session_repo_mock.touch.call_args[0]
    assert touch_args[0] == "existing-1"


async def test_thread_id_is_session_id(patched_processor, text_update):
    await patched_processor.receive_message(text_update)
    agent_invoke_config = patched_processor._agent_mock.ainvoke.call_args.kwargs["config"]
    assert agent_invoke_config["configurable"]["thread_id"] == "sess-1"
    assert agent_invoke_config["configurable"]["lead_id"] == "lead-1"
