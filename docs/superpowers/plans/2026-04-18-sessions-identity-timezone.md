# Sessions, Identity Gating & Default Timezone — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-class `Session` concept (new DB table, 5-min idle window), gate `schedule_meeting` and `send_email` behind a new `update_lead_identity` tool, interpret bare user times as `America/New_York`, and inject per-request session context into the agent's system prompt.

**Architecture:** Hexagonal layering preserved. Domain gains `Session` entity + port; infrastructure gains a new ORM/repo/migration. Application gains `timezone_utils`, `update_lead_identity` tool, and a refactored `MessageProcessingService` that resolves sessions, injects a dynamic session-context string, and uses an injectable clock. Tool-level gating defends identity-sensitive operations.

**Tech Stack:** Python 3.11, uv, SQLAlchemy async, Alembic, LangGraph `create_react_agent`, LangChain, pydantic-settings, stdlib `zoneinfo`, pytest.

---

## File Map

### Create

```
app/domain/entities/session.py
app/domain/repositories/session_repository.py
app/infrastructure/database/models/session_model.py
app/infrastructure/repositories/session_repo.py
app/application/services/timezone_utils.py
app/application/services/tools/update_lead_identity.py
alembic/versions/0003_sessions.py
tests/unit/test_domain/test_session.py
tests/unit/test_timezone_utils/__init__.py
tests/unit/test_timezone_utils/test_timezone_utils.py
tests/unit/test_tools/test_update_lead_identity.py
tests/integration/test_session_repo/__init__.py
tests/integration/test_session_repo/test_session_repo.py
```

### Modify

```
app/config.py                                              # add default_timezone
.env.example                                               # add DEFAULT_TIMEZONE
app/application/services/agent_graph.py                    # session_ctx + build_agent_graph signature
app/application/services/message_processor.py              # session resolution + now_fn + session_ctx + lead_id in config
app/application/services/tools/schedule_meeting.py         # gating, timezone_utils, attendee gating
app/application/services/tools/send_email.py               # add lead_repo, gating
app/application/services/tools/get_calendar_events.py      # add display field
tests/unit/test_tools/test_schedule_meeting.py             # update signatures + gating tests
tests/unit/test_tools/test_send_email.py                   # update signatures + gating tests
tests/unit/test_tools/test_get_calendar_events.py          # display field assertion
tests/unit/test_agent_graph/test_state_modifier.py         # session_ctx tests
tests/unit/test_message_processor/test_message_processor.py  # session resolution + now_fn tests
```

---

## Task 1: Config — add DEFAULT_TIMEZONE

**Files:**
- Modify: `app/config.py`
- Modify: `.env.example`

- [ ] **Step 1: Update `app/config.py`**

Add the new setting. Full file contents:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_env: str = "development"
    base_url: str = "http://localhost:8000"
    log_level: str = "DEBUG"

    telegram_bot_token: str
    database_url: str
    deepseek_api_key: str
    openai_api_key: str

    langfuse_secret_key: str
    langfuse_public_key: str
    langfuse_host: str = "https://us.cloud.langfuse.com"

    google_service_account_json: str
    google_calendar_id: str = "primary"
    gmail_sender: str

    dealership_name: str = "Our Dealership"
    dealership_address: str = "123 Main Street"

    default_timezone: str = "America/New_York"


settings = Settings()
```

- [ ] **Step 2: Append to `.env.example`**

Add at the bottom of the file (keep existing lines):

```
DEFAULT_TIMEZONE=America/New_York
```

- [ ] **Step 3: Verify config imports cleanly**

```bash
uv run python -c "from app.config import settings; print(settings.default_timezone)"
```

Expected: `America/New_York`

- [ ] **Step 4: Commit**

```bash
git add app/config.py .env.example
git commit -m "feat: add DEFAULT_TIMEZONE setting (America/New_York default)"
```

---

## Task 2: Timezone Utility Module

**Files:**
- Create: `app/application/services/timezone_utils.py`
- Create: `tests/unit/test_timezone_utils/__init__.py`
- Create: `tests/unit/test_timezone_utils/test_timezone_utils.py`

- [ ] **Step 1: Create `tests/unit/test_timezone_utils/__init__.py` (empty file)**

```bash
touch tests/unit/test_timezone_utils/__init__.py
```

- [ ] **Step 2: Write failing tests at `tests/unit/test_timezone_utils/test_timezone_utils.py`**

```python
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.application.services.timezone_utils import (
    default_tz,
    format_for_user,
    parse_local_datetime,
)


def test_default_tz_is_america_new_york():
    tz = default_tz()
    assert isinstance(tz, ZoneInfo)
    assert str(tz) == "America/New_York"


def test_parse_local_datetime_attaches_default_tz_to_naive():
    dt = parse_local_datetime("2026-07-15T14:00:00")
    assert dt.tzinfo is not None
    assert dt.utcoffset() == datetime(2026, 7, 15, 14, 0, tzinfo=ZoneInfo("America/New_York")).utcoffset()


def test_parse_local_datetime_preserves_explicit_offset():
    dt = parse_local_datetime("2026-07-15T14:00:00+00:00")
    assert dt.utcoffset().total_seconds() == 0


def test_format_for_user_renders_eastern_with_tz_name():
    utc_instant = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
    text = format_for_user(utc_instant)
    assert "2026" in text
    assert "EDT" in text or "EST" in text


def test_format_for_user_winter_shows_est():
    utc_instant = datetime(2026, 1, 15, 18, 0, tzinfo=timezone.utc)
    text = format_for_user(utc_instant)
    assert "EST" in text
```

- [ ] **Step 3: Run tests — confirm ModuleNotFoundError**

```bash
uv run pytest tests/unit/test_timezone_utils/ -v
```

Expected: fails with `ModuleNotFoundError: No module named 'app.application.services.timezone_utils'`.

- [ ] **Step 4: Create `app/application/services/timezone_utils.py`**

```python
from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings


def default_tz() -> ZoneInfo:
    return ZoneInfo(settings.default_timezone)


def parse_local_datetime(s: str) -> datetime:
    """Parse an ISO8601 datetime string. If naive, attach the default timezone."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz())
    return dt


def format_for_user(dt: datetime) -> str:
    """Format a timezone-aware datetime in the default timezone, including tz abbreviation."""
    local = dt.astimezone(default_tz())
    return local.strftime("%A, %B %-d, %Y at %-I:%M %p %Z")
```

- [ ] **Step 5: Run tests — confirm 5/5 pass**

```bash
uv run pytest tests/unit/test_timezone_utils/ -v
```

Expected: 5 tests PASS.

- [ ] **Step 6: Commit**

```bash
git add app/application/services/timezone_utils.py tests/unit/test_timezone_utils/
git commit -m "feat: timezone utils — default_tz, parse_local_datetime, format_for_user"
```

---

## Task 3: Domain Session Entity + Port

**Files:**
- Create: `app/domain/entities/session.py`
- Create: `app/domain/repositories/session_repository.py`
- Create: `tests/unit/test_domain/test_session.py`

- [ ] **Step 1: Write failing test at `tests/unit/test_domain/test_session.py`**

```python
from datetime import datetime, timedelta, timezone

from app.domain.entities.session import SESSION_IDLE_MINUTES, Session


def test_session_is_active_true_within_window():
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(minutes=SESSION_IDLE_MINUTES - 1)
    s = Session(
        id="s1", lead_id="l1",
        started_at=last, last_message_at=last, created_at=last,
    )
    assert s.is_active(now) is True


def test_session_is_active_true_at_boundary():
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(minutes=SESSION_IDLE_MINUTES)
    s = Session(
        id="s1", lead_id="l1",
        started_at=last, last_message_at=last, created_at=last,
    )
    assert s.is_active(now) is True


def test_session_is_active_false_past_boundary():
    now = datetime(2026, 4, 18, 12, 0, tzinfo=timezone.utc)
    last = now - timedelta(minutes=SESSION_IDLE_MINUTES + 1)
    s = Session(
        id="s1", lead_id="l1",
        started_at=last, last_message_at=last, created_at=last,
    )
    assert s.is_active(now) is False


def test_session_idle_minutes_is_five():
    assert SESSION_IDLE_MINUTES == 5
```

- [ ] **Step 2: Run test to confirm failure**

```bash
uv run pytest tests/unit/test_domain/test_session.py -v
```

Expected: `ModuleNotFoundError: No module named 'app.domain.entities.session'`.

- [ ] **Step 3: Create `app/domain/entities/session.py`**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta

SESSION_IDLE_MINUTES = 5


@dataclass
class Session:
    id: str
    lead_id: str
    started_at: datetime
    last_message_at: datetime
    created_at: datetime

    def is_active(self, now: datetime) -> bool:
        return now - self.last_message_at <= timedelta(minutes=SESSION_IDLE_MINUTES)
```

- [ ] **Step 4: Create `app/domain/repositories/session_repository.py`**

```python
from abc import ABC, abstractmethod
from datetime import datetime
from app.domain.entities.session import Session


class ISessionRepository(ABC):
    @abstractmethod
    async def get_active_for_lead(self, lead_id: str, now: datetime) -> Session | None: ...

    @abstractmethod
    async def create(self, lead_id: str) -> Session: ...

    @abstractmethod
    async def touch(self, session_id: str, ts: datetime) -> None: ...
```

- [ ] **Step 5: Run tests — confirm 4/4 pass and no third-party imports in domain/**

```bash
uv run pytest tests/unit/test_domain/test_session.py -v
```

Expected: 4 tests PASS.

```bash
grep -rE "^(import|from)" app/domain/ | grep -vE "abc|dataclasses|datetime|enum|app\.domain"
```

Expected: no output (domain stays pure Python).

- [ ] **Step 6: Commit**

```bash
git add app/domain/entities/session.py app/domain/repositories/session_repository.py tests/unit/test_domain/test_session.py
git commit -m "feat: domain Session entity + ISessionRepository port"
```

---

## Task 4: Session ORM Model

**Files:**
- Create: `app/infrastructure/database/models/session_model.py`

- [ ] **Step 1: Create `app/infrastructure/database/models/session_model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.infrastructure.database.base import Base


class SessionORM(Base):
    __tablename__ = "sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lead_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("leads.id", ondelete="CASCADE"), nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
```

- [ ] **Step 2: Verify import**

```bash
uv run python -c "from app.infrastructure.database.models.session_model import SessionORM; print(SessionORM.__tablename__)"
```

Expected: `sessions`

- [ ] **Step 3: Commit**

```bash
git add app/infrastructure/database/models/session_model.py
git commit -m "feat: SessionORM model with tz-aware columns"
```

---

## Task 5: Alembic Migration — `sessions` Table

**Files:**
- Create: `alembic/versions/0003_sessions.py`
- Modify: `alembic/env.py` (register new model import)

- [ ] **Step 1: Register SessionORM in `alembic/env.py`**

Open `alembic/env.py` and add this line to the block of `import app.infrastructure.database.models.*_model` lines (preserve existing order, append at the end of that block):

```python
import app.infrastructure.database.models.session_model  # noqa: F401
```

- [ ] **Step 2: Create `alembic/versions/0003_sessions.py`**

```python
"""sessions table

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("last_message_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_sessions_lead_last", "sessions", ["lead_id", sa.text("last_message_at DESC")])


def downgrade() -> None:
    op.drop_index("idx_sessions_lead_last", table_name="sessions")
    op.drop_table("sessions")
```

- [ ] **Step 3: Run migration against Supabase**

```bash
uv run alembic upgrade head
```

Expected last line: `Running upgrade 0002 -> 0003, sessions table` (no error).

- [ ] **Step 4: Verify table exists**

```bash
uv run python -c "
import asyncio
from sqlalchemy import text
from app.infrastructure.database.engine import AsyncSessionFactory
async def main():
    async with AsyncSessionFactory() as s:
        r = await s.execute(text(\"SELECT column_name FROM information_schema.columns WHERE table_name='sessions' ORDER BY ordinal_position\"))
        print([row[0] for row in r.fetchall()])
asyncio.run(main())
"
```

Expected: `['id', 'lead_id', 'started_at', 'last_message_at', 'created_at']`

- [ ] **Step 5: Commit**

```bash
git add alembic/env.py alembic/versions/0003_sessions.py
git commit -m "feat: alembic migration 0003 — sessions table"
```

---

## Task 6: Session Repository + Integration Tests

**Files:**
- Create: `app/infrastructure/repositories/session_repo.py`
- Create: `tests/integration/test_session_repo/__init__.py`
- Create: `tests/integration/test_session_repo/test_session_repo.py`

- [ ] **Step 1: Create `app/infrastructure/repositories/session_repo.py`**

```python
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
```

- [ ] **Step 2: Create `tests/integration/test_session_repo/__init__.py` (empty file)**

```bash
touch tests/integration/test_session_repo/__init__.py
```

- [ ] **Step 3: Write integration tests at `tests/integration/test_session_repo/test_session_repo.py`**

```python
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
```

- [ ] **Step 4: Run integration tests against Supabase**

```bash
uv run pytest tests/integration/test_session_repo/ -v
```

Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/repositories/session_repo.py tests/integration/test_session_repo/
git commit -m "feat: SessionRepository + integration tests against Supabase"
```

---

## Task 7: `update_lead_identity` Tool

**Files:**
- Create: `app/application/services/tools/update_lead_identity.py`
- Create: `tests/unit/test_tools/test_update_lead_identity.py`

- [ ] **Step 1: Write failing tests at `tests/unit/test_tools/test_update_lead_identity.py`**

```python
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.application.services.tools.update_lead_identity import make_update_lead_identity_tool
from app.domain.entities.lead import Lead, LeadStatus


@pytest.fixture
def existing_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name=None, phone=None, email=None,
        status=LeadStatus.NEW, preferred_language="en",
        last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


@pytest.fixture
def mock_lead_repo(existing_lead):
    repo = AsyncMock()
    repo.get_by_id.return_value = existing_lead
    repo.update.side_effect = lambda lead: lead
    return repo


async def test_saves_name_email_phone(mock_lead_repo):
    tool = make_update_lead_identity_tool(mock_lead_repo)
    result = await tool.ainvoke(
        {"name": "Alice", "email": "a@x.com", "phone": "+1555"},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert data["success"] is True
    assert data["name"] == "Alice"
    assert data["email"] == "a@x.com"
    assert data["phone"] == "+1555"
    mock_lead_repo.update.assert_called_once()


async def test_requires_at_least_one_field(mock_lead_repo):
    tool = make_update_lead_identity_tool(mock_lead_repo)
    result = await tool.ainvoke(
        {},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert "error" in data
    mock_lead_repo.update.assert_not_called()


async def test_requires_lead_id_in_config(mock_lead_repo):
    tool = make_update_lead_identity_tool(mock_lead_repo)
    result = await tool.ainvoke({"name": "Alice"}, config={"configurable": {}})
    data = json.loads(result)
    assert "error" in data
    mock_lead_repo.update.assert_not_called()
```

- [ ] **Step 2: Run tests — confirm ModuleNotFoundError**

```bash
uv run pytest tests/unit/test_tools/test_update_lead_identity.py -v
```

Expected: fails with `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/application/services/tools/update_lead_identity.py`**

```python
import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.domain.repositories.lead_repository import ILeadRepository


def make_update_lead_identity_tool(lead_repo: ILeadRepository):
    @tool
    async def update_lead_identity(
        name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        config: RunnableConfig = None,
    ) -> str:
        """Save the customer's contact info to their lead record.
        Call this whenever the customer shares their name, email, or phone number.
        At least one of name/email/phone must be provided."""
        lead_id = (config or {}).get("configurable", {}).get("lead_id")
        if not lead_id:
            return json.dumps({"error": "Lead context missing"})
        if not (name or email or phone):
            return json.dumps({"error": "Provide at least one of name, email, phone"})
        lead = await lead_repo.get_by_id(lead_id)
        if lead is None:
            return json.dumps({"error": f"Lead {lead_id} not found"})
        if name is not None:
            lead.name = name
        if email is not None:
            lead.email = email
        if phone is not None:
            lead.phone = phone
        await lead_repo.update(lead)
        return json.dumps({
            "success": True,
            "name": lead.name,
            "email": lead.email,
            "phone": lead.phone,
        })

    return update_lead_identity
```

- [ ] **Step 4: Run tests — confirm 3/3 pass**

```bash
uv run pytest tests/unit/test_tools/test_update_lead_identity.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/application/services/tools/update_lead_identity.py tests/unit/test_tools/test_update_lead_identity.py
git commit -m "feat: update_lead_identity tool — saves name/email/phone"
```

---

## Task 8: Gating + Timezone for `schedule_meeting`

**Files:**
- Modify: `app/application/services/tools/schedule_meeting.py`
- Modify: `tests/unit/test_tools/test_schedule_meeting.py`

- [ ] **Step 1: Replace `app/application/services/tools/schedule_meeting.py` with:**

```python
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
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
    def _fmt(dt: datetime) -> str:
        return dt.astimezone(tz=None).strftime("%Y%m%dT%H%M%SZ") if dt.utcoffset() else dt.strftime("%Y%m%dT%H%M%SZ")

    # Use UTC for the URL so Google Calendar renders correctly regardless of viewer tz
    from datetime import timezone as _tz
    def _utc(dt: datetime) -> str:
        return dt.astimezone(_tz.utc).strftime("%Y%m%dT%H%M%SZ")

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

        start = parse_local_datetime(scheduled_at)
        end = start + timedelta(hours=1)
        location = "Dealership showroom"
        description = f"Car inspection for car {car_id}. Notes: {notes or 'None'}"

        event_id = await calendar_service.create_event(
            title="Car Inspection",
            start=start,
            end=end,
            attendee_email=attendee_email,
            description=description,
        )

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
        saved_meeting = await meeting_repo.create(meeting)

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
```

- [ ] **Step 2: Replace `tests/unit/test_tools/test_schedule_meeting.py` with:**

```python
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.application.services.tools.schedule_meeting import make_schedule_meeting_tool
from app.domain.entities.lead import Lead, LeadStatus
from app.domain.entities.meeting import Meeting


@pytest.fixture
def identified_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name="Alice",
        phone=None, email="alice@example.com", status=LeadStatus.INTERESTED,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


@pytest.fixture
def unidentified_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name=None, phone=None, email=None,
        status=LeadStatus.NEW, preferred_language="en",
        last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


@pytest.fixture
def mock_meeting_repo():
    repo = AsyncMock()
    repo.create.return_value = Meeting(
        id="meet-1", lead_id="11111111-1111-1111-1111-111111111111",
        car_id="22222222-2222-2222-2222-222222222222",
        google_event_id="gcal-1", google_meet_link=None,
        scheduled_at=datetime(2026, 4, 20, 10, 0),
        duration_minutes=60, location="Dealership showroom",
        status="scheduled", notes=None,
        created_at=datetime(2026, 4, 17), updated_at=datetime(2026, 4, 17),
    )
    return repo


def _lead_repo(lead):
    repo = AsyncMock()
    repo.get_by_id.return_value = lead
    repo.update.return_value = lead
    return repo


@pytest.fixture
def mock_calendar():
    svc = AsyncMock()
    svc.create_event.return_value = "gcal-1"
    return svc


async def test_schedule_meeting_succeeds_for_identified_lead(
    mock_meeting_repo, identified_lead, mock_calendar
):
    lead_repo = _lead_repo(identified_lead)
    tool = make_schedule_meeting_tool(mock_meeting_repo, lead_repo, mock_calendar)
    result = await tool.ainvoke(
        {
            "car_id": "22222222-2222-2222-2222-222222222222",
            "scheduled_at": "2026-04-20T10:00:00",
            "attendee_email": "alice@example.com",
        },
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert data["status"] == "scheduled"
    assert "scheduled_at_display" in data
    assert "add_to_calendar_url" in data
    mock_calendar.create_event.assert_called_once()
    mock_meeting_repo.create.assert_called_once()
    lead_repo.update.assert_called_once()


async def test_schedule_meeting_returns_error_for_unidentified_lead(
    mock_meeting_repo, unidentified_lead, mock_calendar
):
    lead_repo = _lead_repo(unidentified_lead)
    tool = make_schedule_meeting_tool(mock_meeting_repo, lead_repo, mock_calendar)
    result = await tool.ainvoke(
        {
            "car_id": "22222222-2222-2222-2222-222222222222",
            "scheduled_at": "2026-04-20T10:00:00",
        },
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert "error" in data
    assert "not identified" in data["error"].lower()
    mock_meeting_repo.create.assert_not_called()
    mock_calendar.create_event.assert_not_called()


async def test_schedule_meeting_without_lead_id_returns_error(
    mock_meeting_repo, identified_lead, mock_calendar
):
    lead_repo = _lead_repo(identified_lead)
    tool = make_schedule_meeting_tool(mock_meeting_repo, lead_repo, mock_calendar)
    result = await tool.ainvoke({
        "car_id": "22222222-2222-2222-2222-222222222222",
        "scheduled_at": "2026-04-20T10:00:00",
    })
    data = json.loads(result)
    assert "error" in data
    mock_meeting_repo.create.assert_not_called()
```

- [ ] **Step 3: Run tests — confirm 3/3 pass**

```bash
uv run pytest tests/unit/test_tools/test_schedule_meeting.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add app/application/services/tools/schedule_meeting.py tests/unit/test_tools/test_schedule_meeting.py
git commit -m "feat: schedule_meeting gated on identified lead + timezone-aware parsing"
```

---

## Task 9: Gating for `send_email`

**Files:**
- Modify: `app/application/services/tools/send_email.py`
- Modify: `tests/unit/test_tools/test_send_email.py`

- [ ] **Step 1: Replace `app/application/services/tools/send_email.py` with:**

```python
import json

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from app.domain.repositories.email_log_repository import IEmailLogRepository
from app.domain.repositories.inventory_repository import IInventoryRepository
from app.domain.repositories.lead_repository import ILeadRepository
from app.domain.use_cases.email_use_case import IEmailService


def make_send_email_tool(
    inventory_repo: IInventoryRepository,
    email_service: IEmailService,
    email_log_repo: IEmailLogRepository,
    lead_repo: ILeadRepository,
):
    @tool
    async def send_email(
        car_id: str,
        recipient_email: str,
        config: RunnableConfig = None,
    ) -> str:
        """Send a car specification HTML email via Gmail. Logs the result to email_sent_logs.
        Requires the lead to be identified (name, email, or phone on file)."""
        lead_id = (config or {}).get("configurable", {}).get("lead_id")
        if not lead_id:
            return json.dumps({"error": "Lead context missing"})
        lead = await lead_repo.get_by_id(lead_id)
        if lead is None or not (lead.name or lead.email or lead.phone):
            return json.dumps({
                "error": (
                    "Lead not identified. Ask the customer for their name, email, "
                    "or phone first and call update_lead_identity before retrying."
                )
            })

        car = await inventory_repo.get_car_by_id(car_id)
        if not car:
            return json.dumps({"error": f"Car {car_id} not found"})
        try:
            await email_service.send_car_specs(recipient_email, car)
            return json.dumps({"success": True, "message": f"Email sent to {recipient_email}"})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    return send_email
```

- [ ] **Step 2: Replace `tests/unit/test_tools/test_send_email.py` with:**

```python
import json
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.application.services.tools.send_email import make_send_email_tool
from app.domain.entities.car import Car
from app.domain.entities.lead import Lead, LeadStatus


@pytest.fixture
def sample_car():
    return Car(
        id="car-1", brand="Tesla", model="Model 3", year=2023,
        color="Black", price=48500.0, km=0, fuel_type="electric",
        transmission="automatic", condition="new", vin=None,
        description=None, image_url=None, available=True,
        created_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def identified_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name="Alice", phone=None,
        email="alice@example.com", status=LeadStatus.NEW,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


@pytest.fixture
def unidentified_lead():
    return Lead(
        id="11111111-1111-1111-1111-111111111111",
        telegram_chat_id="12345", name=None, phone=None, email=None,
        status=LeadStatus.NEW, preferred_language="en",
        last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )


def _inventory(car):
    repo = AsyncMock()
    repo.get_car_by_id.return_value = car
    return repo


def _lead_repo(lead):
    repo = AsyncMock()
    repo.get_by_id.return_value = lead
    return repo


@pytest.fixture
def mock_email_service():
    svc = AsyncMock()
    svc.send_car_specs.return_value = True
    return svc


@pytest.fixture
def mock_email_log_repo():
    return AsyncMock()


async def test_send_email_succeeds_for_identified_lead(
    sample_car, identified_lead, mock_email_service, mock_email_log_repo
):
    tool = make_send_email_tool(
        _inventory(sample_car), mock_email_service, mock_email_log_repo, _lead_repo(identified_lead),
    )
    result = await tool.ainvoke(
        {"car_id": "car-1", "recipient_email": "buyer@example.com"},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    assert "success" in result.lower()
    mock_email_service.send_car_specs.assert_called_once()


async def test_send_email_blocked_for_unidentified_lead(
    sample_car, unidentified_lead, mock_email_service, mock_email_log_repo
):
    tool = make_send_email_tool(
        _inventory(sample_car), mock_email_service, mock_email_log_repo, _lead_repo(unidentified_lead),
    )
    result = await tool.ainvoke(
        {"car_id": "car-1", "recipient_email": "buyer@example.com"},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    data = json.loads(result)
    assert "error" in data
    assert "not identified" in data["error"].lower()
    mock_email_service.send_car_specs.assert_not_called()


async def test_send_email_car_not_found(
    identified_lead, mock_email_service, mock_email_log_repo
):
    no_car = AsyncMock()
    no_car.get_car_by_id.return_value = None
    tool = make_send_email_tool(
        no_car, mock_email_service, mock_email_log_repo, _lead_repo(identified_lead),
    )
    result = await tool.ainvoke(
        {"car_id": "nonexistent", "recipient_email": "buyer@example.com"},
        config={"configurable": {"lead_id": "11111111-1111-1111-1111-111111111111"}},
    )
    assert "not found" in result.lower()
    mock_email_service.send_car_specs.assert_not_called()
```

- [ ] **Step 3: Run tests — confirm 3/3 pass**

```bash
uv run pytest tests/unit/test_tools/test_send_email.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add app/application/services/tools/send_email.py tests/unit/test_tools/test_send_email.py
git commit -m "feat: send_email gated on identified lead; takes lead_repo dependency"
```

---

## Task 10: `get_calendar_events` — Display in Eastern

**Files:**
- Modify: `app/application/services/tools/get_calendar_events.py`
- Modify: `tests/unit/test_tools/test_get_calendar_events.py`

- [ ] **Step 1: Replace `app/application/services/tools/get_calendar_events.py` with:**

```python
import json
from datetime import datetime

from langchain_core.tools import tool

from app.application.services.timezone_utils import format_for_user
from app.domain.use_cases.calendar_use_case import ICalendarService


def make_get_calendar_events_tool(calendar_service: ICalendarService):
    @tool
    async def get_calendar_events(days_ahead: int = 14) -> str:
        """Get available 1-hour appointment slots during business hours (9 AM–6 PM)
        over the next N days. Always call before proposing times to the customer.
        Each slot includes a `display` field formatted in the dealership's timezone
        (America/New_York) which is safe to show the customer directly."""
        slots = await calendar_service.get_available_slots(days_ahead=days_ahead)
        enriched = []
        for s in slots:
            start = datetime.fromisoformat(s["start"])
            enriched.append({**s, "display": format_for_user(start)})
        return json.dumps(enriched)

    return get_calendar_events
```

- [ ] **Step 2: Replace `tests/unit/test_tools/test_get_calendar_events.py` with:**

```python
import json
from unittest.mock import AsyncMock

import pytest

from app.application.services.tools.get_calendar_events import make_get_calendar_events_tool


@pytest.fixture
def mock_calendar():
    svc = AsyncMock()
    svc.get_available_slots.return_value = [
        {"start": "2026-07-15T14:00:00+00:00", "end": "2026-07-15T15:00:00+00:00"},
        {"start": "2026-01-15T14:00:00+00:00", "end": "2026-01-15T15:00:00+00:00"},
    ]
    return svc


async def test_slots_include_display_field_with_tz(mock_calendar):
    tool = make_get_calendar_events_tool(mock_calendar)
    result = await tool.ainvoke({"days_ahead": 7})
    slots = json.loads(result)
    assert len(slots) == 2
    for s in slots:
        assert "display" in s
        assert "EDT" in s["display"] or "EST" in s["display"]
    mock_calendar.get_available_slots.assert_called_once_with(days_ahead=7)
```

- [ ] **Step 3: Run tests — confirm pass**

```bash
uv run pytest tests/unit/test_tools/test_get_calendar_events.py -v
```

Expected: 1 test PASS.

- [ ] **Step 4: Commit**

```bash
git add app/application/services/tools/get_calendar_events.py tests/unit/test_tools/test_get_calendar_events.py
git commit -m "feat: get_calendar_events adds Eastern-time display field per slot"
```

---

## Task 11: Agent Graph — `session_ctx` Parameter

**Files:**
- Modify: `app/application/services/agent_graph.py`
- Modify: `tests/unit/test_agent_graph/test_state_modifier.py`

- [ ] **Step 1: Replace `app/application/services/agent_graph.py` with:**

```python
from datetime import date

from langchain_core.messages import SystemMessage, trim_messages
from langchain_core.messages.utils import count_tokens_approximately
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.prebuilt import create_react_agent

from app.config import settings

SYSTEM_PROMPT = f"""You are an AI assistant for {settings.dealership_name}, a car dealership.
Help customers find vehicles, schedule visits, and receive car information by email.
Be friendly, professional, and concise. Always reply in the customer's language.

SCOPE RESTRICTION: Only answer questions about cars, inventory, pricing, scheduling,
test drives, or email specs. For anything else respond ONLY with:
"I can only help with questions about our car inventory, scheduling visits, and
sending vehicle information. Is there anything car-related I can help you with today?"

TOOL USAGE:
- Pick the tool that matches the customer's ACTUAL intent. Asking to "schedule a visit"
  or "book an appointment" means call get_calendar_events then schedule_meeting — NOT send_email.
  Asking to "send specs" or "email me details" means call send_email — NOT schedule_meeting.
- If a tool returns an error or a JSON object with "error" or "success": false, tell the
  customer plainly what failed. NEVER fabricate a successful result when a tool failed.
- Before scheduling, always call get_calendar_events first to find real available slots.
- After schedule_meeting succeeds, the tool returns an `add_to_calendar_url`. ALWAYS
  include this link in your reply so the customer can add the event to their own calendar.
- Times the customer mentions without an explicit timezone are assumed to be
  America/New_York (Eastern). Always include the timezone name when showing times back
  to the customer.

Current date: {date.today().isoformat()}
Dealership address: {settings.dealership_address}
"""


def _build_state_modifier(llm, session_ctx: str = ""):
    system_text = (session_ctx + "\n\n" + SYSTEM_PROMPT) if session_ctx else SYSTEM_PROMPT

    def state_modifier(state: dict) -> list:
        trimmed = trim_messages(
            state["messages"],
            max_tokens=6000,
            strategy="last",
            token_counter=count_tokens_approximately,
            include_system=True,
            allow_partial=False,
        )
        return [SystemMessage(content=system_text)] + trimmed
    return state_modifier


def build_agent_graph(
    checkpointer: AsyncPostgresSaver,
    tools: list,
    session_ctx: str = "",
):
    llm = ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key=settings.deepseek_api_key,
        temperature=0.3,
        max_retries=3,
    )
    return create_react_agent(
        model=llm,
        tools=tools,
        checkpointer=checkpointer,
        state_modifier=_build_state_modifier(llm, session_ctx),
    )
```

- [ ] **Step 2: Replace `tests/unit/test_agent_graph/test_state_modifier.py` with:**

```python
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage, SystemMessage

from app.application.services.agent_graph import SYSTEM_PROMPT, _build_state_modifier


def test_state_modifier_prepends_static_system_prompt_when_no_session_ctx():
    mock_llm = MagicMock()
    modifier = _build_state_modifier(mock_llm, session_ctx="")
    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [HumanMessage(content="Hello")]
        messages = modifier({"messages": [HumanMessage(content="Hello")]})
    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == SYSTEM_PROMPT


def test_state_modifier_prepends_session_ctx_before_system_prompt():
    mock_llm = MagicMock()
    ctx = "SESSION CONTEXT:\n- test block"
    modifier = _build_state_modifier(mock_llm, session_ctx=ctx)
    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [HumanMessage(content="Hello")]
        messages = modifier({"messages": [HumanMessage(content="Hello")]})
    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content.startswith(ctx)
    assert SYSTEM_PROMPT in messages[0].content


def test_state_modifier_includes_trimmed_messages():
    mock_llm = MagicMock()
    modifier = _build_state_modifier(mock_llm)
    human_msg = HumanMessage(content="Hello")
    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [human_msg]
        messages = modifier({"messages": [human_msg]})
    assert human_msg in messages
```

- [ ] **Step 3: Run tests — confirm 3/3 pass**

```bash
uv run pytest tests/unit/test_agent_graph/ -v
```

Expected: 3 tests PASS.

- [ ] **Step 4: Commit**

```bash
git add app/application/services/agent_graph.py tests/unit/test_agent_graph/test_state_modifier.py
git commit -m "feat: agent_graph accepts session_ctx prepended to system prompt"
```

---

## Task 12: MessageProcessingService — Sessions, `now_fn`, `session_ctx`

**Files:**
- Modify: `app/application/services/message_processor.py`
- Modify: `app/infrastructure/container/container.py`
- Modify: `tests/unit/test_message_processor/test_message_processor.py`

- [ ] **Step 1: Replace `app/application/services/message_processor.py` with:**

```python
import logging
import traceback
from datetime import datetime, timezone
from typing import Callable

from langchain_core.messages import HumanMessage

from app.application.services.agent_graph import build_agent_graph
from app.application.services.tools.get_calendar_events import make_get_calendar_events_tool
from app.application.services.tools.get_inventory import make_get_inventory_tool
from app.application.services.tools.schedule_meeting import make_schedule_meeting_tool
from app.application.services.tools.send_email import make_send_email_tool
from app.application.services.tools.update_lead_identity import make_update_lead_identity_tool
from app.domain.entities.lead import Lead
from app.domain.use_cases.calendar_use_case import ICalendarService
from app.domain.use_cases.speech_use_case import ISpeechService
from app.domain.use_cases.telegram_use_case import ITelegramService
from app.infrastructure.events.gmail_adapter import GmailAdapter
from app.infrastructure.repositories.email_log_repo import EmailLogRepository
from app.infrastructure.repositories.inventory_repo import InventoryRepository
from app.infrastructure.repositories.lead_repo import LeadRepository
from app.infrastructure.repositories.meeting_repo import MeetingRepository
from app.infrastructure.repositories.session_repo import SessionRepository
from app.infrastructure.schemas.telegram_schema import TelegramUpdate

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE = (
    "I'm having a little trouble right now. "
    "Please try again in a moment or contact us directly."
)


def _build_session_context(lead: Lead, is_new_session: bool) -> str:
    identity_bits = []
    if lead.name:
        identity_bits.append(f"name={lead.name}")
    if lead.email:
        identity_bits.append(f"email={lead.email}")
    if lead.phone:
        identity_bits.append(f"phone={lead.phone}")
    identity = ", ".join(identity_bits) if identity_bits else "(unknown)"
    state = "NEW" if is_new_session else "ongoing"
    return (
        "SESSION CONTEXT:\n"
        f"- This is a {state} session. Current customer identity: {identity}.\n"
        "- If the session is NEW and identity is (unknown), greet warmly and ask "
        "for name, email, or phone to personalise the conversation.\n"
        "- When the customer shares any contact info, call update_lead_identity "
        "immediately to save it.\n"
        "- For scheduling and emails, identity is required. If unidentified, ask "
        "for contact info before calling those tools.\n"
    )


class MessageProcessingService:
    def __init__(
        self,
        session_factory,
        speech_service: ISpeechService,
        telegram_service: ITelegramService,
        calendar_service: ICalendarService,
        checkpointer,
        langfuse_handler,
        now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ) -> None:
        self.session_factory = session_factory
        self.speech_service = speech_service
        self.telegram_service = telegram_service
        self.calendar_service = calendar_service
        self.checkpointer = checkpointer
        self.langfuse_handler = langfuse_handler
        self.now_fn = now_fn

    async def receive_message(self, update: TelegramUpdate) -> None:
        if not update.message:
            return

        message = update.message
        chat_id = message.chat_id
        is_voice = message.voice is not None

        try:
            async with self.session_factory() as db:
                lead_repo = LeadRepository(db)
                inventory_repo = InventoryRepository(db)
                meeting_repo = MeetingRepository(db)
                email_log_repo = EmailLogRepository(db)
                session_repo = SessionRepository(db)
                gmail_adapter = GmailAdapter(email_log_repo)

                lead = await lead_repo.get_or_create(chat_id)

                now = self.now_fn()
                session = await session_repo.get_active_for_lead(lead.id, now)
                if session is None:
                    session = await session_repo.create(lead.id)
                    is_new_session = True
                else:
                    is_new_session = False
                await session_repo.touch(session.id, now)

                if is_voice:
                    audio_bytes = await self.telegram_service.download_voice(message.voice.file_id)
                    user_text = await self.speech_service.transcribe(audio_bytes, "ogg")
                else:
                    user_text = message.text or ""

                if not user_text.strip():
                    return

                tools = [
                    make_get_inventory_tool(inventory_repo),
                    make_get_calendar_events_tool(self.calendar_service),
                    make_schedule_meeting_tool(meeting_repo, lead_repo, self.calendar_service),
                    make_send_email_tool(inventory_repo, gmail_adapter, email_log_repo, lead_repo),
                    make_update_lead_identity_tool(lead_repo),
                ]
                session_ctx = _build_session_context(lead, is_new_session)
                agent = build_agent_graph(
                    checkpointer=self.checkpointer, tools=tools, session_ctx=session_ctx,
                )

                config = {
                    "configurable": {
                        "thread_id": str(session.id),
                        "lead_id": str(lead.id),
                    },
                    "callbacks": [self.langfuse_handler],
                }
                result = await agent.ainvoke(
                    {"messages": [HumanMessage(content=user_text)]},
                    config=config,
                )
                response_text = result["messages"][-1].content

                if is_voice:
                    audio_response = await self.speech_service.synthesize(response_text)
                    await self.telegram_service.send_voice(chat_id, audio_response)
                else:
                    await self.telegram_service.send_text(chat_id, response_text)

                lead.last_contacted_at = now
                await lead_repo.update(lead)

        except Exception as e:
            logger.exception("receive_message failed: %s", e)
            traceback.print_exc()
            await self.telegram_service.send_text(chat_id, FALLBACK_MESSAGE)
```

- [ ] **Step 2: Update `app/infrastructure/container/container.py` `get_message_processor` function**

Replace the body of `get_message_processor` (only this function, keep the rest of the file):

```python
async def get_message_processor(request: Request) -> MessageProcessingService:
    return MessageProcessingService(
        session_factory=AsyncSessionFactory,
        speech_service=get_openai_adapter(),
        telegram_service=get_telegram_adapter(),
        calendar_service=get_calendar_adapter(),
        checkpointer=request.app.state.checkpointer,
        langfuse_handler=get_langfuse_handler(),
    )
```

(unchanged from current; just confirm it still matches. No new args needed — `now_fn` takes its default.)

- [ ] **Step 3: Replace `tests/unit/test_message_processor/test_message_processor.py` with:**

```python
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from app.application.services.message_processor import MessageProcessingService
from app.domain.entities.lead import Lead, LeadStatus
from app.domain.entities.session import Session
from app.infrastructure.schemas.telegram_schema import Message, TelegramUpdate


@pytest.fixture
def sample_lead():
    return Lead(
        id="lead-1", telegram_chat_id="12345", name="Alice",
        phone=None, email=None, status=LeadStatus.NEW,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2026, 1, 1), updated_at=datetime(2026, 1, 1),
    )


@pytest.fixture
def text_update():
    return TelegramUpdate(
        update_id=1,
        message=Message(message_id=1, chat={"id": 12345}, text="Show me red cars"),
    )


@pytest.fixture
def voice_update():
    return TelegramUpdate(
        update_id=2,
        message=Message(
            message_id=2, chat={"id": 12345},
            voice={"file_id": "file123", "file_unique_id": "uq123", "duration": 3},
        ),
    )


class _FakeSessionCtx:
    def __init__(self, db):
        self._db = db

    async def __aenter__(self):
        return self._db

    async def __aexit__(self, *a):
        return None


@pytest.fixture
def lead_repo_mock(sample_lead):
    repo = AsyncMock()
    repo.get_or_create.return_value = sample_lead
    repo.update.return_value = sample_lead
    return repo


@pytest.fixture
def session_repo_mock():
    repo = AsyncMock()
    repo.get_active_for_lead.return_value = None
    repo.create.return_value = Session(
        id="sess-1", lead_id="lead-1",
        started_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        last_message_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    repo.touch = AsyncMock()
    return repo


@pytest.fixture
def agent_graph_mock():
    agent = AsyncMock()
    agent.ainvoke.return_value = {
        "messages": [HumanMessage(content="Show me red cars"), AIMessage(content="Here are red cars")]
    }
    return agent


@pytest.fixture
def fixed_now():
    return datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)


@pytest.fixture
def processor(lead_repo_mock, session_repo_mock, agent_graph_mock, fixed_now):
    proc = MessageProcessingService(
        session_factory=lambda: _FakeSessionCtx(AsyncMock()),
        speech_service=AsyncMock(),
        telegram_service=AsyncMock(),
        calendar_service=AsyncMock(),
        checkpointer=MagicMock(),
        langfuse_handler=MagicMock(),
        now_fn=lambda: fixed_now,
    )
    proc.speech_service.transcribe.return_value = "Show me red cars"
    proc.speech_service.synthesize.return_value = b"audio_bytes"
    proc._lead_repo_mock = lead_repo_mock
    proc._session_repo_mock = session_repo_mock
    proc._agent_mock = agent_graph_mock
    return proc


@pytest.fixture
def patched_processor(processor):
    with patch("app.application.services.message_processor.LeadRepository", return_value=processor._lead_repo_mock), \
         patch("app.application.services.message_processor.SessionRepository", return_value=processor._session_repo_mock), \
         patch("app.application.services.message_processor.InventoryRepository"), \
         patch("app.application.services.message_processor.MeetingRepository"), \
         patch("app.application.services.message_processor.EmailLogRepository"), \
         patch("app.application.services.message_processor.GmailAdapter"), \
         patch("app.application.services.message_processor.build_agent_graph", return_value=processor._agent_mock):
        yield processor


async def test_text_message_sends_text_reply(patched_processor, text_update):
    await patched_processor.receive_message(text_update)
    patched_processor.telegram_service.send_text.assert_called_once_with("12345", "Here are red cars")
    patched_processor.telegram_service.send_voice.assert_not_called()


async def test_voice_message_transcribes_and_replies_with_voice(patched_processor, voice_update):
    patched_processor.telegram_service.download_voice = AsyncMock(return_value=b"ogg_bytes")
    patched_processor.speech_service.transcribe = AsyncMock(return_value="Show me red cars")
    await patched_processor.receive_message(voice_update)
    patched_processor.speech_service.transcribe.assert_called_once_with(b"ogg_bytes", "ogg")
    patched_processor.telegram_service.send_voice.assert_called_once()


async def test_updates_lead_last_contacted(patched_processor, text_update, fixed_now):
    await patched_processor.receive_message(text_update)
    patched_processor._lead_repo_mock.update.assert_called_once()
    updated_lead = patched_processor._lead_repo_mock.update.call_args[0][0]
    assert updated_lead.last_contacted_at == fixed_now


async def test_creates_new_session_when_none_active(patched_processor, text_update):
    await patched_processor.receive_message(text_update)
    patched_processor._session_repo_mock.get_active_for_lead.assert_called_once()
    patched_processor._session_repo_mock.create.assert_called_once_with("lead-1")
    patched_processor._session_repo_mock.touch.assert_called_once()


async def test_reuses_active_session(patched_processor, text_update, fixed_now):
    existing = Session(
        id="existing-1", lead_id="lead-1",
        started_at=fixed_now - timedelta(minutes=2),
        last_message_at=fixed_now - timedelta(minutes=2),
        created_at=fixed_now - timedelta(minutes=2),
    )
    patched_processor._session_repo_mock.get_active_for_lead.return_value = existing
    await patched_processor.receive_message(text_update)
    patched_processor._session_repo_mock.create.assert_not_called()
    patched_processor._session_repo_mock.touch.assert_called_once()
    touch_args = patched_processor._session_repo_mock.touch.call_args[0]
    assert touch_args[0] == "existing-1"


async def test_thread_id_is_session_id(patched_processor, text_update):
    await patched_processor.receive_message(text_update)
    agent_invoke_config = patched_processor._agent_mock.ainvoke.call_args.kwargs["config"]
    assert agent_invoke_config["configurable"]["thread_id"] == "sess-1"
    assert agent_invoke_config["configurable"]["lead_id"] == "lead-1"
```

- [ ] **Step 4: Run message processor tests — confirm 6/6 pass**

```bash
uv run pytest tests/unit/test_message_processor/ -v
```

Expected: 6 tests PASS.

- [ ] **Step 5: Run the full unit suite**

```bash
uv run pytest tests/unit/ -v 2>&1 | tail -15
```

Expected: approximately 25 tests PASS (domain, timezone_utils, tools, agent_graph, processor).

- [ ] **Step 6: Commit**

```bash
git add app/application/services/message_processor.py app/infrastructure/container/container.py tests/unit/test_message_processor/test_message_processor.py
git commit -m "feat: MessageProcessingService — session resolution, now_fn, session_ctx"
```

---

## Task 13: Final Validation

- [ ] **Step 1: Full test run (unit + integration)**

```bash
uv run pytest -v 2>&1 | tail -15
```

Expected: all tests pass (approx. 25 unit + 13 integration = 38 total).

- [ ] **Step 2: Restart the running server (if applicable)**

If a server is already running from a prior task, kill it first, then start fresh so new code is loaded:

```bash
pkill -f "uvicorn app.main:app" 2>/dev/null
sleep 2
uv run uvicorn app.main:app --port 8000 > /tmp/uvicorn_sessions.log 2>&1 &
sleep 6
grep "startup complete" /tmp/uvicorn_sessions.log
```

Expected: `INFO:     Application startup complete.`

- [ ] **Step 3: Verify /health still returns all green**

```bash
curl -sS http://localhost:8000/health | python3 -m json.tool
```

Expected: `status: ok` with `database: ok`.

- [ ] **Step 4: Manual sanity check via Telegram (optional, leave to user)**

Have the user send a fresh message to the bot and confirm:
- New session → bot greets and asks for name/email/phone
- After identity shared → `schedule_meeting` / `send_email` become usable
- Bot shows times like "Monday, April 20, 2026 at 10:00 AM EDT"

- [ ] **Step 5: Final commit (if any residual changes)**

```bash
git status
```

If clean, no commit needed. If not, commit whatever's left with a descriptive message.

---

## Self-Review

### Spec Coverage

| Spec Requirement | Task |
|---|---|
| `sessions` table migration | Task 5 |
| `Session` domain entity + `SESSION_IDLE_MINUTES=5` | Task 3 |
| `ISessionRepository` port | Task 3 |
| `SessionORM` model | Task 4 |
| `SessionRepository` concrete + integration tests | Task 6 |
| Session resolution in `receive_message` | Task 12 |
| `thread_id = session.id` | Task 12 |
| `lead_id` in configurable | Task 12 |
| Injectable `now_fn` clock | Task 12 |
| `touch` called even on later failure (happens before agent/tool calls) | Task 12 |
| `update_lead_identity` tool | Task 7 |
| Gating on `schedule_meeting` | Task 8 |
| Gating on `send_email` (+ new `lead_repo` arg) | Task 9 |
| `timezone_utils` module | Task 2 |
| `DEFAULT_TIMEZONE` env | Task 1 |
| `schedule_meeting` uses `parse_local_datetime` + `scheduled_at_display` | Task 8 |
| `get_calendar_events` adds `display` field | Task 10 |
| System prompt TOOL USAGE bullet for timezone | Task 11 |
| Dynamic `session_ctx` prepended to SYSTEM_PROMPT | Task 11 + 12 |
| New unit tests covering all of the above | Tasks 2, 3, 7, 8, 9, 10, 11, 12 |
| New integration tests for `session_repo` | Task 6 |

All spec requirements have a corresponding task.

### Placeholder Scan

No "TBD", "TODO", "add validation", or "similar to Task N" references. All code blocks are complete and self-contained.

### Type / Signature Consistency

- `make_send_email_tool(inventory_repo, email_service, email_log_repo, lead_repo)` — 4 args, matches Task 9 tool definition and Task 12 wiring.
- `make_schedule_meeting_tool(meeting_repo, lead_repo, calendar_service)` — 3 args, unchanged from current code, matches Task 8 and Task 12.
- `build_agent_graph(checkpointer, tools, session_ctx="")` — Task 11 defines, Task 12 calls.
- `_build_state_modifier(llm, session_ctx: str = "")` — Task 11.
- `MessageProcessingService.__init__` parameters match container call in Task 12 step 2.
- `ISessionRepository` methods `get_active_for_lead`, `create`, `touch` — consistent across Tasks 3, 6, 12.
- `Session.is_active(now)` uses `<=` (not `<`) so the 5-minute boundary is inclusive — matches Task 3 test `test_session_is_active_true_at_boundary`.

All internally consistent.
