import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.infrastructure.repositories.lead_repo import LeadRepository
from app.infrastructure.repositories.session_repo import SessionRepository


@pytest.fixture
async def lead(db_session):
    lead_repo = LeadRepository(db_session)
    chat_id = f"test_session_{uuid.uuid4().hex[:8]}"
    return await lead_repo.get_or_create(chat_id)


async def test_create_inserts_session(db_session, lead):
    repo = SessionRepository(db_session)
    s = await repo.create(lead.id)
    assert s.id
    assert s.lead_id == lead.id
    assert s.started_at is not None
    assert s.last_message_at is not None


async def test_get_active_returns_recent_session(db_session, lead):
    repo = SessionRepository(db_session)
    created = await repo.create(lead.id)
    now = datetime.now(timezone.utc)
    active = await repo.get_active_for_lead(lead.id, now)
    assert active is not None
    assert active.id == created.id


async def test_get_active_returns_none_when_past_idle_window(db_session, lead):
    repo = SessionRepository(db_session)
    await repo.create(lead.id)
    future = datetime.now(timezone.utc) + timedelta(minutes=6)
    active = await repo.get_active_for_lead(lead.id, future)
    assert active is None


async def test_touch_updates_last_message_at(db_session, lead):
    repo = SessionRepository(db_session)
    s = await repo.create(lead.id)
    bumped = datetime.now(timezone.utc) + timedelta(minutes=2)
    await repo.touch(s.id, bumped)
    reloaded = await repo.get_active_for_lead(lead.id, bumped)
    assert reloaded is not None
    assert reloaded.last_message_at >= s.last_message_at
