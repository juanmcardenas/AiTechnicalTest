import uuid
from datetime import datetime
from sqlalchemy import select
from app.domain.entities.lead import Lead, LeadStatus
from app.domain.repositories.lead_repository import ILeadRepository
from app.infrastructure.database.models.lead_model import LeadORM
from app.infrastructure.repositories.base_repository import BaseRepository


class LeadRepository(BaseRepository, ILeadRepository):
    async def get_or_create(self, telegram_chat_id: str) -> Lead:
        stmt = select(LeadORM).where(LeadORM.telegram_chat_id == telegram_chat_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            row = LeadORM(
                id=uuid.uuid4(),
                telegram_chat_id=telegram_chat_id,
                status=LeadStatus.NEW.value,
                preferred_language="en",
            )
            self.session.add(row)
            await self.session.commit()
            await self.session.refresh(row)
        return self._to_domain(row)

    async def get_by_id(self, lead_id: str) -> Lead | None:
        stmt = select(LeadORM).where(LeadORM.id == uuid.UUID(lead_id))
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(row) if row else None

    async def update(self, lead: Lead) -> Lead:
        stmt = select(LeadORM).where(LeadORM.id == uuid.UUID(lead.id))
        row = (await self.session.execute(stmt)).scalar_one()
        row.name = lead.name
        row.phone = lead.phone
        row.email = lead.email
        row.status = lead.status.value if isinstance(lead.status, LeadStatus) else lead.status
        row.preferred_language = lead.preferred_language
        row.last_contacted_at = lead.last_contacted_at
        row.updated_at = datetime.now()
        await self.session.commit()
        await self.session.refresh(row)
        return self._to_domain(row)

    def _to_domain(self, r: LeadORM) -> Lead:
        return Lead(
            id=str(r.id), telegram_chat_id=r.telegram_chat_id,
            name=r.name, phone=r.phone, email=r.email,
            status=LeadStatus(r.status), preferred_language=r.preferred_language,
            last_contacted_at=r.last_contacted_at,
            created_at=r.created_at, updated_at=r.updated_at,
        )
