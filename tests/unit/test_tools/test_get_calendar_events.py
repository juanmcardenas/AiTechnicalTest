import json
import pytest
from unittest.mock import AsyncMock
from app.application.services.tools.get_calendar_events import make_get_calendar_events_tool


@pytest.fixture
def mock_calendar():
    svc = AsyncMock()
    svc.get_available_slots.return_value = [
        {"start": "2026-04-20T10:00:00+00:00", "end": "2026-04-20T11:00:00+00:00"},
        {"start": "2026-04-20T14:00:00+00:00", "end": "2026-04-20T15:00:00+00:00"},
    ]
    return svc


async def test_get_calendar_events_returns_slots(mock_calendar):
    tool = make_get_calendar_events_tool(mock_calendar)
    result = await tool.ainvoke({"days_ahead": 7})
    slots = json.loads(result)
    assert len(slots) == 2
    assert "start" in slots[0]
    mock_calendar.get_available_slots.assert_called_once_with(days_ahead=7)
