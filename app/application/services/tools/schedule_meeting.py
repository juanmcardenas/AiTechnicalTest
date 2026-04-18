import json
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
from app.domain.entities.lead import LeadStatus
from app.domain.entities.meeting import Meeting
from app.domain.repositories.lead_repository import ILeadRepository
from app.domain.repositories.meeting_repository import IMeetingRepository
from app.domain.use_cases.calendar_use_case import ICalendarService


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
        scheduled_at must be an ISO8601 datetime string. Sets lead status to converted."""
        lead_id = (config or {}).get("configurable", {}).get("thread_id")
        if not lead_id:
            return json.dumps({"error": "Lead context missing; cannot schedule."})

        start = datetime.fromisoformat(scheduled_at)
        end = start + timedelta(hours=1)

        event_id = await calendar_service.create_event(
            title="Car Inspection",
            start=start,
            end=end,
            attendee_email=attendee_email,
            description=f"Car inspection for car {car_id}. Notes: {notes or 'None'}",
        )

        meeting = Meeting(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            car_id=car_id,
            google_event_id=event_id,
            google_meet_link=None,
            scheduled_at=start,
            duration_minutes=60,
            location="Dealership showroom",
            status="scheduled",
            notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        saved_meeting = await meeting_repo.create(meeting)

        lead = await lead_repo.get_by_id(lead_id)
        if lead:
            lead.status = LeadStatus.CONVERTED
            await lead_repo.update(lead)

        return json.dumps(asdict(saved_meeting), default=str)

    return schedule_meeting
