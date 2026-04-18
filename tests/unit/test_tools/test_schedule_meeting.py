import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.application.services.tools.schedule_meeting import make_schedule_meeting_tool
from app.domain.entities.lead import Lead, LeadStatus
from app.domain.entities.meeting import Meeting


@pytest.fixture
def identified_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name="Alice",
        phone=None, email="alice@example.com", status=LeadStatus.INTERESTED,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


@pytest.fixture
def unidentified_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name=None, phone=None, email=None,
        status=LeadStatus.NEW, preferred_language="en",
        last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


@pytest.fixture
def mock_meeting_repo():
    repo = AsyncMock()
    repo.create.return_value = Meeting(
        id="meet-1", lead_id="11111111-1111-1111-1111-111111111111",
        car_id="22222222-2222-2222-2222-222222222222",
        google_event_id="gcal-1", google_meet_link=None,
        scheduled_at=datetime(2026, 4, 20, 10, 0),
        duration_minutes=60, location="Dealership showroom",
        status="scheduled", notes=None,
        created_at=datetime(2026, 4, 17), updated_at=datetime(2026, 4, 17),
    )
    return repo


def _lead_repo(lead):
    repo = AsyncMock()
    repo.get_by_id.return_value = lead
    repo.update.return_value = lead
    return repo


@pytest.fixture
def mock_calendar():
    svc = AsyncMock()
    svc.create_event.return_value = "gcal-1"
    return svc


async def test_schedule_meeting_succeeds_for_identified_lead(
    mock_meeting_repo, identified_lead, mock_calendar
):
    lead_repo = _lead_repo(identified_lead)
    tool = make_schedule_meeting_tool(mock_meeting_repo, lead_repo, mock_calendar)
    result = await tool.ainvoke(
        {
            "car_id": "22222222-2222-2222-2222-222222222222",
            "scheduled_at": "2026-04-20T10:00:00",
            "attendee_email": "alice@example.com",
        },
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert data["status"] == "scheduled"
    assert "scheduled_at_display" in data
    assert "add_to_calendar_url" in data
    mock_calendar.create_event.assert_called_once()
    mock_meeting_repo.create.assert_called_once()
    lead_repo.update.assert_called_once()


async def test_schedule_meeting_returns_error_for_unidentified_lead(
    mock_meeting_repo, unidentified_lead, mock_calendar
):
    lead_repo = _lead_repo(unidentified_lead)
    tool = make_schedule_meeting_tool(mock_meeting_repo, lead_repo, mock_calendar)
    result = await tool.ainvoke(
        {
            "car_id": "22222222-2222-2222-2222-222222222222",
            "scheduled_at": "2026-04-20T10:00:00",
        },
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert "error" in data
    assert "not identified" in data["error"].lower()
    mock_meeting_repo.create.assert_not_called()
    mock_calendar.create_event.assert_not_called()


async def test_schedule_meeting_without_lead_id_returns_error(
    mock_meeting_repo, identified_lead, mock_calendar
):
    lead_repo = _lead_repo(identified_lead)
    tool = make_schedule_meeting_tool(mock_meeting_repo, lead_repo, mock_calendar)
    result = await tool.ainvoke({
        "car_id": "22222222-2222-2222-2222-222222222222",
        "scheduled_at": "2026-04-20T10:00:00",
    })
    data = json.loads(result)
    assert "error" in data
    mock_meeting_repo.create.assert_not_called()
