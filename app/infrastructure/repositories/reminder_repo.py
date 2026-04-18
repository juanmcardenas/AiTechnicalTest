import uuid
from datetime import datetime
from sqlalchemy import select
from app.domain.entities.reminder import Reminder
from app.domain.repositories.reminder_repository import IReminderRepository
from app.infrastructure.database.models.reminder_model import ReminderORM
from app.infrastructure.repositories.base_repository import BaseRepository


class ReminderRepository(BaseRepository, IReminderRepository):
    async def create(self, reminder: Reminder) -> Reminder:
        row = ReminderORM(
            id=uuid.UUID(reminder.id) if reminder.id else uuid.uuid4(),
            lead_id=uuid.UUID(reminder.lead_id),
            remind_at=reminder.remind_at,
            message=reminder.message,
            sent=reminder.sent,
        )
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._to_domain(row)

    async def get_pending(self, before: datetime) -> list[Reminder]:
        stmt = select(ReminderORM).where(
            ReminderORM.sent == False,  # noqa: E712
            ReminderORM.remind_at <= before,
        )
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._to_domain(r) for r in rows]

    async def mark_sent(self, reminder_id: str) -> None:
        stmt = select(ReminderORM).where(ReminderORM.id == uuid.UUID(reminder_id))
        row = (await self.session.execute(stmt)).scalar_one()
        row.sent = True
        row.sent_at = datetime.utcnow()
        await self.session.commit()

    def _to_domain(self, r: ReminderORM) -> Reminder:
        return Reminder(
            id=str(r.id), lead_id=str(r.lead_id),
            remind_at=r.remind_at, message=r.message,
            sent=r.sent, sent_at=r.sent_at, created_at=r.created_at,
        )
