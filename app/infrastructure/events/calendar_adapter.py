import json
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google.oauth2 import service_account
from app.config import settings
from app.domain.exceptions import CalendarUnavailableError
from app.domain.use_cases.calendar_use_case import ICalendarService

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarAdapter(ICalendarService):
    def __init__(self) -> None:
        sa_info = settings.google_service_account_json
        if sa_info.endswith(".json"):
            with open(sa_info) as f:
                sa_dict = json.load(f)
        else:
            sa_dict = json.loads(sa_info)
        creds = service_account.Credentials.from_service_account_info(sa_dict, scopes=SCOPES)
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._calendar_id = settings.google_calendar_id

    async def get_available_slots(self, days_ahead: int = 14) -> list[dict]:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        body = {
            "timeMin": now.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": self._calendar_id}],
        }
        try:
            result = self._service.freebusy().query(body=body).execute()
            busy = result["calendars"][self._calendar_id]["busy"]
        except Exception as e:
            raise CalendarUnavailableError(str(e)) from e

        busy_ranges = [(b["start"], b["end"]) for b in busy]
        slots = []
        cursor = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        while cursor < end and len(slots) < 20:
            if cursor.weekday() < 5 and 9 <= cursor.hour < 18:
                slot_end = cursor + timedelta(hours=1)
                overlap = any(
                    cursor.isoformat() < be and slot_end.isoformat() > bs
                    for bs, be in busy_ranges
                )
                if not overlap:
                    slots.append({
                        "start": cursor.isoformat(),
                        "end": slot_end.isoformat(),
                    })
            cursor += timedelta(hours=1)
        return slots

    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None,
        description: str,
    ) -> str:
        full_description = description
        if attendee_email:
            full_description = f"{description}\n\nCustomer email: {attendee_email}"
        event = {
            "summary": title,
            "description": full_description,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }
        try:
            created = self._service.events().insert(
                calendarId=self._calendar_id, body=event
            ).execute()
            return created["id"]
        except Exception as e:
            raise CalendarUnavailableError(str(e)) from e
