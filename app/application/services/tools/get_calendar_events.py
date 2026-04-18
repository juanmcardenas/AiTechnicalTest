import json
from datetime import datetime

from langchain_core.tools import tool

from app.application.services.timezone_utils import format_for_user
from app.domain.use_cases.calendar_use_case import ICalendarService


def make_get_calendar_events_tool(calendar_service: ICalendarService):
    @tool
    async def get_calendar_events(days_ahead: int = 14) -> str:
        """Get available 1-hour appointment slots during business hours (9 AM–6 PM)
        over the next N days. Always call before proposing times to the customer.
        Each slot includes a `display` field formatted in the dealership's timezone
        (America/New_York) which is safe to show the customer directly."""
        slots = await calendar_service.get_available_slots(days_ahead=days_ahead)
        enriched = []
        for s in slots:
            start = datetime.fromisoformat(s["start"])
            enriched.append({**s, "display": format_for_user(start)})
        return json.dumps(enriched)

    return get_calendar_events
