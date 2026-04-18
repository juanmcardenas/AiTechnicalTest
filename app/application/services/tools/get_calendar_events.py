import json
from langchain_core.tools import tool
from app.domain.use_cases.calendar_use_case import ICalendarService


def make_get_calendar_events_tool(calendar_service: ICalendarService):
    @tool
    async def get_calendar_events(days_ahead: int = 14) -> str:
        """Get available 1-hour appointment slots during business hours (9 AM–6 PM)
        over the next N days. Always call before proposing times to the customer."""
        slots = await calendar_service.get_available_slots(days_ahead=days_ahead)
        return json.dumps(slots)

    return get_calendar_events
