import uuid
from datetime import datetime
from sqlalchemy import select

from app.domain.entities.session import Session
from app.domain.repositories.session_repository import ISessionRepository
from app.infrastructure.database.models.session_model import SessionORM
from app.infrastructure.repositories.base_repository import BaseRepository


class SessionRepository(BaseRepository, ISessionRepository):
    async def get_active_for_lead(self, lead_id: str, now: datetime) -> Session | None:
        stmt = (
            select(SessionORM)
            .where(SessionORM.lead_id == uuid.UUID(lead_id))
            .order_by(SessionORM.last_message_at.desc())
            .limit(1)
        )
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return None
        session_obj = self._to_domain(row)
        return session_obj if session_obj.is_active(now) else None

    async def create(self, lead_id: str) -> Session:
        row = SessionORM(id=uuid.uuid4(), lead_id=uuid.UUID(lead_id))
        self.session.add(row)
        await self.session.commit()
        await self.session.refresh(row)
        return self._to_domain(row)

    async def touch(self, session_id: str, ts: datetime) -> None:
        stmt = select(SessionORM).where(SessionORM.id == uuid.UUID(session_id))
        row = (await self.session.execute(stmt)).scalar_one()
        row.last_message_at = ts
        await self.session.commit()

    def _to_domain(self, r: SessionORM) -> Session:
        return Session(
            id=str(r.id),
            lead_id=str(r.lead_id),
            started_at=r.started_at,
            last_message_at=r.last_message_at,
            created_at=r.created_at,
        )
