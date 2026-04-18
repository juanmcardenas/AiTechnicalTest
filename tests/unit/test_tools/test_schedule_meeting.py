import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from app.domain.entities.lead import Lead, LeadStatus
from app.domain.entities.meeting import Meeting
from app.application.services.tools.schedule_meeting import make_schedule_meeting_tool


@pytest.fixture
def mock_meeting_repo():
    repo = AsyncMock()
    repo.create.return_value = Meeting(
        id="meet-1", lead_id="11111111-1111-1111-1111-111111111111",
        car_id="22222222-2222-2222-2222-222222222222",
        google_event_id="gcal-event-1", google_meet_link=None,
        scheduled_at=datetime(2026, 4, 20, 10, 0),
        duration_minutes=60, location="Dealership showroom",
        status="scheduled", notes=None,
        created_at=datetime(2026, 4, 17), updated_at=datetime(2026, 4, 17),
    )
    return repo


@pytest.fixture
def mock_lead_repo():
    repo = AsyncMock()
    lead = Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name="Alice",
        phone=None, email="alice@example.com", status=LeadStatus.INTERESTED,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )
    repo.get_by_id.return_value = lead
    repo.update.return_value = lead
    return repo


@pytest.fixture
def mock_calendar():
    svc = AsyncMock()
    svc.create_event.return_value = "gcal-event-1"
    return svc


async def test_schedule_meeting_creates_event_and_meeting(
    mock_meeting_repo, mock_lead_repo, mock_calendar
):
    tool = make_schedule_meeting_tool(mock_meeting_repo, mock_lead_repo, mock_calendar)
    result = await tool.ainvoke(
        {
            "car_id": "22222222-2222-2222-2222-222222222222",
            "scheduled_at": "2026-04-20T10:00:00",
            "attendee_email": "alice@example.com",
        },
        config={"configurable": {"thread_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert data["status"] == "scheduled"
    mock_calendar.create_event.assert_called_once()
    mock_meeting_repo.create.assert_called_once()
    mock_lead_repo.update.assert_called_once()


async def test_schedule_meeting_without_lead_context_returns_error(
    mock_meeting_repo, mock_lead_repo, mock_calendar
):
    tool = make_schedule_meeting_tool(mock_meeting_repo, mock_lead_repo, mock_calendar)
    result = await tool.ainvoke({
        "car_id": "22222222-2222-2222-2222-222222222222",
        "scheduled_at": "2026-04-20T10:00:00",
    })
    data = json.loads(result)
    assert "error" in data
    mock_meeting_repo.create.assert_not_called()
