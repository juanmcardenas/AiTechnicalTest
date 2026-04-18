import json
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.application.services.timezone_utils import format_for_user, parse_local_datetime
from app.domain.entities.lead import LeadStatus
from app.domain.entities.meeting import Meeting
from app.domain.repositories.lead_repository import ILeadRepository
from app.domain.repositories.meeting_repository import IMeetingRepository
from app.domain.use_cases.calendar_use_case import ICalendarService


def _build_add_to_calendar_url(
    title: str,
    start: datetime,
    end: datetime,
    description: str,
    location: str,
    attendee_email: str | None,
) -> str:
    def _utc(dt: datetime) -> str:
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    params = {
        "action": "TEMPLATE",
        "text": title,
        "dates": f"{_utc(start)}/{_utc(end)}",
        "details": description,
        "location": location,
    }
    if attendee_email:
        params["add"] = attendee_email
    return "https://calendar.google.com/calendar/render?" + urlencode(params)


def make_schedule_meeting_tool(
    meeting_repo: IMeetingRepository,
    lead_repo: ILeadRepository,
    calendar_service: ICalendarService,
):
    @tool
    async def schedule_meeting(
        car_id: str,
        scheduled_at: str,
        attendee_email: str | None = None,
        notes: str | None = None,
        config: RunnableConfig = None,
    ) -> str:
        """Create a Google Calendar event and persist a meeting record.
        scheduled_at must be an ISO8601 datetime string. Bare times (no offset) are
        interpreted in the dealership's default timezone (America/New_York).
        Sets lead status to converted. Returns JSON with the meeting record plus
        `scheduled_at_display` (Eastern-time friendly) and `add_to_calendar_url`."""
        lead_id = (config or {}).get("configurable", {}).get("lead_id")
        if not lead_id:
            return json.dumps({"error": "Lead context missing; cannot schedule."})
        lead = await lead_repo.get_by_id(lead_id)
        if lead is None or not (lead.name or lead.email or lead.phone):
            return json.dumps({
                "error": (
                    "Lead not identified. Ask the customer for their name, email, "
                    "or phone first and call update_lead_identity before retrying."
                )
            })

        try:
            start = parse_local_datetime(scheduled_at)
        except Exception as e:
            return json.dumps({"success": False, "error": f"Invalid scheduled_at: {e}"})

        end = start + timedelta(hours=1)
        location = "Dealership showroom"
        description = f"Car inspection for car {car_id}. Notes: {notes or 'None'}"

        try:
            event_id = await calendar_service.create_event(
                title="Car Inspection",
                start=start,
                end=end,
                attendee_email=attendee_email,
                description=description,
            )
        except Exception as e:
            return json.dumps({"success": False, "error": f"Calendar error: {e}"})

        meeting = Meeting(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            car_id=car_id,
            google_event_id=event_id,
            google_meet_link=None,
            scheduled_at=start,
            duration_minutes=60,
            location=location,
            status="scheduled",
            notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        try:
            saved_meeting = await meeting_repo.create(meeting)
        except Exception as e:
            return json.dumps({"success": False, "error": f"Database error: {e}"})

        lead.status = LeadStatus.CONVERTED
        await lead_repo.update(lead)

        payload = asdict(saved_meeting)
        payload["scheduled_at_display"] = format_for_user(start)
        payload["add_to_calendar_url"] = _build_add_to_calendar_url(
            title="Car Inspection",
            start=start,
            end=end,
            description=description,
            location=location,
            attendee_email=attendee_email,
        )
        return json.dumps(payload, default=str)

    return schedule_meeting
