import uuid
from sqlalchemy import select
from app.domain.entities.meeting import Meeting
from app.domain.repositories.meeting_repository import IMeetingRepository
from app.infrastructure.database.models.meeting_model import MeetingORM
from app.infrastructure.repositories.base_repository import BaseRepository


class MeetingRepository(BaseRepository, IMeetingRepository):
    async def create(self, meeting: Meeting) -> Meeting:
        row = MeetingORM(
            id=uuid.UUID(meeting.id) if meeting.id else uuid.uuid4(),
            lead_id=uuid.UUID(meeting.lead_id),
            car_id=uuid.UUID(meeting.car_id),
            google_event_id=meeting.google_event_id,
            google_meet_link=meeting.google_meet_link,
            scheduled_at=meeting.scheduled_at,
            duration_minutes=meeting.duration_minutes,
            location=meeting.location,
            status=meeting.status,
            notes=meeting.notes,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._to_domain(row)

    async def get_by_lead(self, lead_id: str) -> list[Meeting]:
        stmt = select(MeetingORM).where(MeetingORM.lead_id == uuid.UUID(lead_id))
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._to_domain(r) for r in rows]

    def _to_domain(self, r: MeetingORM) -> Meeting:
        return Meeting(
            id=str(r.id), lead_id=str(r.lead_id), car_id=str(r.car_id),
            google_event_id=r.google_event_id, google_meet_link=r.google_meet_link,
            scheduled_at=r.scheduled_at, duration_minutes=r.duration_minutes,
            location=r.location, status=r.status, notes=r.notes,
            created_at=r.created_at, updated_at=r.updated_at,
        )
