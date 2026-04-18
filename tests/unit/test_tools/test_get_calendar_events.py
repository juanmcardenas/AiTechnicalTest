import json
from unittest.mock import AsyncMock

import pytest

from app.application.services.tools.get_calendar_events import make_get_calendar_events_tool


@pytest.fixture
def mock_calendar():
    svc = AsyncMock()
    svc.get_available_slots.return_value = [
        {"start": "2026-07-15T14:00:00+00:00", "end": "2026-07-15T15:00:00+00:00"},
        {"start": "2026-01-15T14:00:00+00:00", "end": "2026-01-15T15:00:00+00:00"},
    ]
    return svc


async def test_slots_include_display_field_with_tz(mock_calendar):
    tool = make_get_calendar_events_tool(mock_calendar)
    result = await tool.ainvoke({"days_ahead": 7})
    slots = json.loads(result)
    assert len(slots) == 2
    for s in slots:
        assert "display" in s
        assert "EDT" in s["display"] or "EST" in s["display"]
    mock_calendar.get_available_slots.assert_called_once_with(days_ahead=7)
