import pytest
import uuid
from app.domain.entities.lead import LeadStatus
from app.infrastructure.repositories.lead_repo import LeadRepository


async def test_get_or_create_creates_new_lead(db_session):
    repo = LeadRepository(db_session)
    chat_id = f"test_{uuid.uuid4().hex[:8]}"
    lead = await repo.get_or_create(chat_id)
    assert lead.telegram_chat_id == chat_id
    assert lead.status == LeadStatus.NEW


async def test_get_or_create_idempotent(db_session):
    repo = LeadRepository(db_session)
    chat_id = f"test_{uuid.uuid4().hex[:8]}"
    lead1 = await repo.get_or_create(chat_id)
    lead2 = await repo.get_or_create(chat_id)
    assert lead1.id == lead2.id


async def test_update_lead_status(db_session):
    repo = LeadRepository(db_session)
    chat_id = f"test_{uuid.uuid4().hex[:8]}"
    lead = await repo.get_or_create(chat_id)
    lead.status = LeadStatus.INTERESTED
    updated = await repo.update(lead)
    assert updated.status == LeadStatus.INTERESTED


async def test_get_by_id_returns_lead(db_session):
    repo = LeadRepository(db_session)
    chat_id = f"test_{uuid.uuid4().hex[:8]}"
    lead = await repo.get_or_create(chat_id)
    found = await repo.get_by_id(lead.id)
    assert found is not None
    assert found.id == lead.id
