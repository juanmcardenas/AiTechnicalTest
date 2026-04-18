# Sessions, Lead Identification & Default Timezone — Design Spec

**Date:** 2026-04-18
**Version:** 1.0
**Depends on:** the v1 backend spec at `docs/superpowers/specs/2026-04-17-car-dealership-telegram-bot-design.md`

## Goals

1. Add a first-class **Session** concept. Each inbound Telegram message belongs to a session; a gap of more than 5 minutes between messages starts a new session. Session id drives LangGraph conversation memory so every new session begins with a clean slate.
2. On every new session, the bot greets the customer and asks for **name, email, or phone**. The customer can still browse inventory without identifying themselves, but `schedule_meeting` and `send_email` are gated until at least one identifier is captured on the lead. Every new session always re-asks and overwrites prior values.
3. Interpret times the customer mentions without an explicit timezone as **`America/New_York`** (Eastern). Always display times back with the timezone name so there is no ambiguity.

Lead duplication at the DB level is already prevented by the `UNIQUE` constraint on `leads.telegram_chat_id`. No changes to the lead schema — the identification flow simply populates the existing `name`, `email`, `phone` columns.

---

## 1. Data Model

### 1.1 New `sessions` table (Alembic migration `0003_sessions.py`)

```sql
CREATE TABLE sessions (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id          UUID        NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_message_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_sessions_lead_last ON sessions(lead_id, last_message_at DESC);
```

### 1.2 New domain entity `app/domain/entities/session.py`

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

### 1.3 New domain port `app/domain/repositories/session_repository.py`

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

### 1.4 ORM + repository

- `app/infrastructure/database/models/session_model.py` — `SessionORM` with `DateTime(timezone=True)` on every timestamp column.
- `app/infrastructure/repositories/session_repo.py` — `SessionRepository` extends `BaseRepository` and implements `ISessionRepository`, mapping rows to `Session` via `_to_domain`.
- Alembic autogeneration is not relied on; migration `0003_sessions.py` is hand-written.

### 1.5 No schema change to `leads`

`leads.name`, `leads.email`, `leads.phone` already exist. The identification tool overwrites them.

---

## 2. Session Resolution in `MessageProcessingService.receive_message`

```
1.  Resolve lead via lead_repo.get_or_create(telegram_chat_id)     [unchanged]
2.  now = now_fn()                                                  [new: injectable clock]
3.  session = session_repo.get_active_for_lead(lead.id, now)
    if session is None:
        session = await session_repo.create(lead.id)
        is_new_session = True
    else:
        is_new_session = False
    await session_repo.touch(session.id, now)                       [advance activity
                                                                     regardless of later
                                                                     success/failure]
4.  If voice → download + transcribe                                [unchanged]
5.  Build tools (with lead_repo, session_repo, etc.)
6.  Build agent_graph using checkpointer
7.  config = {
        "configurable": {
            "thread_id": str(session.id),        ← session.id, NOT lead.id
            "lead_id":   str(lead.id),           ← new, read by tools
        },
        "callbacks": [langfuse_handler],
    }
    Build dynamic system prompt from base SYSTEM_PROMPT +
    build_session_context(lead, is_new_session)
    Inject into state_modifier before agent.ainvoke
8.  agent.ainvoke(..., config=config)                               [unchanged]
9.  TTS / send_text                                                 [unchanged]
10. lead.last_contacted_at = now; lead_repo.update(lead)            [unchanged]
```

### 2.1 Injectable clock

`MessageProcessingService` gains a constructor parameter `now_fn: Callable[[], datetime]` defaulting to `lambda: datetime.now(timezone.utc)`. All time-reading inside the service goes through `self.now_fn()`. Tests pass fixed or advancing clocks.

### 2.2 Concurrency

Two near-simultaneous inbound messages from the same lead could both observe no active session and both INSERT. This is accepted. The second session silently becomes the active one; the first is an orphan with no further messages. No unique constraint is added.

---

## 3. Identification Tool & Tool-Level Gating

### 3.1 New tool `app/application/services/tools/update_lead_identity.py`

```python
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
            "success": True, "name": lead.name,
            "email": lead.email, "phone": lead.phone,
        })

    return update_lead_identity
```

### 3.2 Gating on `schedule_meeting` and `send_email`

Both tools start with:

```python
lead_id = (config or {}).get("configurable", {}).get("lead_id")
if not lead_id:
    return json.dumps({"error": "Lead context missing"})
lead = await lead_repo.get_by_id(lead_id)
if lead is None or not (lead.name or lead.email or lead.phone):
    return json.dumps({
        "error": "Lead not identified. Ask the customer for their name, "
                 "email, or phone first and call update_lead_identity before retrying."
    })
```

`schedule_meeting` already has `lead_repo`. `send_email` gains a `lead_repo` dependency.

`get_inventory` and `get_calendar_events` stay ungated.

### 3.3 Configurable for tools

Tools now read **`lead_id`** from `config["configurable"]["lead_id"]`. The existing `thread_id` becomes `session.id` and is no longer used by tools for identity lookup.

### 3.4 System prompt — dynamic per-invocation block

Static `SYSTEM_PROMPT` is unchanged. `state_modifier` now receives a `session_ctx` string and prepends it to the static system prompt each invocation.

```python
def build_session_context(lead: Lead, is_new_session: bool) -> str:
    identity_bits = []
    if lead.name:  identity_bits.append(f"name={lead.name}")
    if lead.email: identity_bits.append(f"email={lead.email}")
    if lead.phone: identity_bits.append(f"phone={lead.phone}")
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
```

`_build_state_modifier` accepts a `session_ctx: str` parameter and prepends it to `SYSTEM_PROMPT`. The processor builds `session_ctx` after session + lead are known and passes it when constructing the agent for that request.

---

## 4. Default Timezone

### 4.1 Config

`app/config.py` gains `default_timezone: str = "America/New_York"`. `.env.example` adds `DEFAULT_TIMEZONE=America/New_York`. Runs on stdlib `zoneinfo` (Python 3.11+); no new dependency.

### 4.2 Utility module `app/application/services/timezone_utils.py`

```python
from datetime import datetime
from zoneinfo import ZoneInfo
from app.config import settings


def default_tz() -> ZoneInfo:
    return ZoneInfo(settings.default_timezone)


def parse_local_datetime(s: str) -> datetime:
    """Parse ISO8601; if naive, attach default_tz()."""
    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=default_tz())
    return dt


def format_for_user(dt: datetime) -> str:
    local = dt.astimezone(default_tz())
    return local.strftime("%A, %B %-d, %Y at %-I:%M %p %Z")
```

### 4.3 Tool changes

- `schedule_meeting`:
  - Replace `datetime.fromisoformat(scheduled_at)` with `parse_local_datetime(scheduled_at)`.
  - The returned JSON gets a new field `scheduled_at_display = format_for_user(start)`.
- `get_calendar_events`:
  - For each slot, add a `display` key: `format_for_user(datetime.fromisoformat(slot["start"]))`.
- `update_lead_identity`: no timezone work.

### 4.4 System prompt addition

One bullet added to the TOOL USAGE section:

> Times the customer mentions without an explicit timezone are assumed to be America/New_York (Eastern). Always include the timezone name when showing times back to the customer.

---

## 5. Wiring & DI

### 5.1 Container (`app/infrastructure/container/container.py`)

No change — the container still just constructs the processor with stateless dependencies. Session repo and tools are built inside `receive_message` per request, alongside the existing repos.

### 5.2 `MessageProcessingService` constructor

Add the following parameters:

```python
def __init__(
    self,
    session_factory,
    speech_service: ISpeechService,
    telegram_service: ITelegramService,
    calendar_service: ICalendarService,
    checkpointer,
    langfuse_handler,
    now_fn: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
):
```

Inside `receive_message`, after opening the session:

```python
session_repo = SessionRepository(session)
...
tools = [
    make_get_inventory_tool(inventory_repo),
    make_get_calendar_events_tool(self.calendar_service),
    make_schedule_meeting_tool(meeting_repo, lead_repo, self.calendar_service),
    make_send_email_tool(inventory_repo, gmail_adapter, email_log_repo, lead_repo),
    make_update_lead_identity_tool(lead_repo),
]
```

(`make_send_email_tool` gains `lead_repo` for the gating check.)

### 5.3 Agent graph

`build_agent_graph` accepts an optional `session_ctx: str = ""` and passes it to `_build_state_modifier`. The state modifier prepends `session_ctx + "\n" + SYSTEM_PROMPT` as the single SystemMessage.

---

## 6. Testing Strategy

### 6.1 New unit tests

- `tests/unit/test_domain/test_session.py` — `Session.is_active` at the 5-minute boundary (inclusive on or just under).
- `tests/unit/test_tools/test_update_lead_identity.py` — saves name/email/phone; returns error when all three are None; returns error when `lead_id` config missing.
- `tests/unit/test_tools/test_schedule_meeting.py` — add cases for identified vs unidentified lead.
- `tests/unit/test_tools/test_send_email.py` — same two cases.
- `tests/unit/test_tools/test_get_calendar_events.py` — slots include a `display` field containing a `%Z` timezone abbreviation.
- `tests/unit/test_timezone_utils/test_timezone_utils.py` — naive string gains Eastern tz; aware string is preserved; `format_for_user` round-trips UTC instants to Eastern strings with "EDT" or "EST".
- `tests/unit/test_message_processor/test_message_processor.py` — add: new lead creates session; message inside 5 min reuses session; message outside 5 min creates new session. Uses an injected `now_fn` mock that advances time.

### 6.2 New integration tests

- `tests/integration/test_session_repo/test_session_repo.py` — against real Supabase:
  - `create(lead_id)` inserts and returns the session.
  - `get_active_for_lead` returns the most recent session when `last_message_at` is within 5 min, and `None` once past that boundary.
  - `touch` advances `last_message_at`.

No change needed to existing webhook integration tests beyond swapping to the new processor constructor.

### 6.3 Fixture additions

New `tests/unit/conftest.py` helper `identified_lead(...)` to build a `Lead` with `name="Alice"` pre-set, shared across tool tests that expect gating to pass.

### 6.4 Expected totals after this work

Roughly 28 unit + 10 integration ≈ 38 tests, up from 18 + 9 = 27.

---

## 7. Migration Rollout

1. Apply `alembic upgrade head` — creates `sessions` table + index.
2. Deploy new app code. Existing leads keep working; the first incoming message for each lead opens a fresh session.
3. Existing `langgraph_checkpoints` rows become orphaned (keyed on old `lead.id`). They remain in the DB harmlessly. A one-off cleanup script can drop them if desired.

No data backfill is needed. No breaking changes to `leads`, `meetings`, `reminders`, or `email_sent_logs` schemas.

---

## 8. Out of Scope

- Regex-based identity extraction as a safety net (rejected in favour of tool-only per decision).
- Carrying a summary of past sessions into new sessions (decision: clean memory reset).
- Merging multiple `telegram_chat_id`s that belong to the same human.
- Per-customer timezone detection from chat content.
- Session expiry / cleanup jobs (sessions are append-only).

---

## 9. Env Changes

```
DEFAULT_TIMEZONE=America/New_York
```

Single new env var. `.env.example` updated; existing `.env` files must add it or accept the default.
