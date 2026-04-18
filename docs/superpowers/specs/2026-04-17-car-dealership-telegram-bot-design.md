# Car Dealership Telegram Chatbot — Design Spec

**Date:** 2026-04-17  
**Version:** 1.0  
**Stack:** Python · FastAPI · SQLAlchemy · Alembic · LangChain · LangGraph · DeepSeek · OpenAI · LangFuse · Google Calendar · Gmail  
**Architecture:** Hexagonal (Ports & Adapters)

---

## 1. Architecture

The system uses strict Hexagonal Architecture in three layers with explicit import rules:

```
domain/          ← pure Python, zero third-party imports
application/     ← imports domain only (LangGraph, LangChain tools)
infrastructure/  ← imports domain + application (FastAPI, SQLAlchemy, adapters)
```

**Layer import rules:**

| Layer | May import from |
|-------|-----------------|
| `domain` | Nothing outside `domain` |
| `application` | `domain` only |
| `infrastructure` | `domain` + `application` |

ORM models are never imported by `domain` or `application`. The mapping between ORM rows and domain entities happens exclusively inside `infrastructure/repositories/`.

---

## 2. Project Structure

```
app/
├── main.py                              # FastAPI app factory + lifespan
├── config.py                            # Pydantic Settings from .env
├── domain/
│   ├── entities/
│   │   ├── car.py
│   │   ├── lead.py
│   │   ├── meeting.py
│   │   └── reminder.py
│   ├── repositories/                    # Port ABCs for data persistence
│   │   ├── inventory_repository.py
│   │   ├── lead_repository.py
│   │   ├── meeting_repository.py
│   │   ├── reminder_repository.py
│   │   └── email_log_repository.py
│   ├── use_cases/                       # Port ABCs for external services
│   │   ├── speech_use_case.py
│   │   ├── calendar_use_case.py
│   │   ├── email_use_case.py
│   │   └── telegram_use_case.py
│   └── exceptions.py
├── application/
│   ├── services/
│   │   ├── message_processor.py
│   │   ├── agent_graph.py
│   │   └── tools/
│   │       ├── get_inventory.py
│   │       ├── get_calendar_events.py
│   │       ├── schedule_meeting.py
│   │       └── send_email.py
│   └── validators/
│       └── message_validator.py
├── infrastructure/
│   ├── handlers/
│   │   ├── webhook_handler.py
│   │   └── health_handler.py
│   ├── database/
│   │   ├── engine.py
│   │   ├── base.py
│   │   └── models/
│   │       ├── inventory_model.py
│   │       ├── lead_model.py
│   │       ├── meeting_model.py
│   │       ├── reminder_model.py
│   │       └── email_log_model.py
│   ├── repositories/
│   │   ├── base_repository.py
│   │   ├── inventory_repo.py
│   │   ├── lead_repo.py
│   │   ├── meeting_repo.py
│   │   ├── reminder_repo.py
│   │   └── email_log_repo.py
│   ├── events/
│   │   ├── openai_adapter.py
│   │   ├── calendar_adapter.py
│   │   ├── gmail_adapter.py
│   │   └── telegram_adapter.py
│   ├── schemas/
│   │   ├── telegram_schema.py
│   │   └── health_schema.py
│   └── container/
│       └── container.py
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_domain/
    │   ├── test_tools/
    │   ├── test_message_processor/
    │   └── test_agent_graph/
    └── integration/
        ├── test_inventory_repo/
        ├── test_lead_repo/
        ├── test_meeting_repo/
        ├── test_reminder_repo/
        └── test_webhook/
alembic/
├── env.py
├── script.py.mako
└── versions/
    ├── 0001_initial_schema.py
    └── 0002_seed_inventory.py
pyproject.toml
.env                 # gitignored
.env.example
alembic.ini
```

---

## 3. Domain Layer

### 3.1 Entities

All entities are pure `@dataclass` objects with no third-party imports.

**`Car`** — vehicle record with: `id`, `brand`, `model`, `year`, `color`, `price`, `km`, `fuel_type`, `transmission`, `condition` (new/used/certified), `vin`, `description`, `image_url`, `available`, `created_at`.

**`Lead`** — customer identified by `telegram_chat_id`: `id`, `name`, `phone`, `email`, `status` (`LeadStatus` enum), `preferred_language`, `last_contacted_at`, `created_at`, `updated_at`.

**`Meeting`** — links lead + car to Google Calendar: `id`, `lead_id`, `car_id`, `google_event_id`, `google_meet_link`, `scheduled_at`, `duration_minutes` (default 60), `location`, `status`, `notes`, `created_at`, `updated_at`.

**`Reminder`** — follow-up message: `id`, `lead_id`, `remind_at`, `message`, `sent`, `sent_at`, `created_at`.

### 3.2 Enums

```python
class LeadStatus(str, Enum):
    NEW = "new"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CONVERTED = "converted"
```

### 3.3 Repository Ports

Async ABCs in `domain/repositories/`:

- `IInventoryRepository`: `get_cars(filters)`, `get_car_by_id(car_id)`
- `ILeadRepository`: `get_or_create(telegram_chat_id)`, `update(lead)`
- `IMeetingRepository`: `create(meeting)`, `get_by_lead(lead_id)`
- `IReminderRepository`: `create(reminder)`, `get_pending(before)`, `mark_sent(reminder_id)`
- `IEmailLogRepository`: `log(lead_id, car_id, recipient, subject, template, success, error)`

### 3.4 Service Ports

Async ABCs in `domain/use_cases/`:

- `ISpeechService`: `transcribe(audio_bytes, file_format)`, `synthesize(text)`
- `ICalendarService`: `get_available_slots(days_ahead)`, `create_event(title, start, end, attendee_email, description)`
- `IEmailService`: `send_car_specs(recipient_email, car)`
- `ITelegramService`: `send_text(chat_id, text)`, `send_voice(chat_id, audio_bytes)`, `download_voice(file_id)`

### 3.5 Exceptions

`domain/exceptions.py` defines domain-specific errors: `LeadNotFoundError`, `CarNotFoundError`, `CalendarUnavailableError`, `EmailSendError`. Infrastructure adapters raise these; the application layer catches them.

---

## 4. Infrastructure Layer

### 4.1 Database

- **Engine** (`infrastructure/database/engine.py`): async SQLAlchemy engine → Supabase PostgreSQL, `async_sessionmaker`, `get_checkpointer()` initializes `AsyncPostgresSaver` for LangGraph state.
- **ORM models**: mirror DB schema with `Mapped[T]` / `mapped_column` annotations. Never imported outside `infrastructure/`.
- **Repository pattern**: `BaseRepository` holds `AsyncSession`. Each concrete repo inherits `BaseRepository` + its domain port ABC. All DB rows are mapped to domain entities via `_to_domain()` before leaving the repository.

### 4.2 External Adapters

| Adapter | Port | Notes |
|---------|------|-------|
| `OpenAIAdapter` | `ISpeechService` | Whisper STT (`whisper-1`), TTS (`tts-1`, `alloy`) |
| `CalendarAdapter` | `ICalendarService` | Google Calendar FreeBusy + event creation via service account |
| `GmailAdapter` | `IEmailService` | HTML email with car specs; logs every attempt via `IEmailLogRepository` |
| `TelegramAdapter` | `ITelegramService` | Bot API `sendMessage`, `sendVoice`, `getFile`; sets webhook on startup |

### 4.3 LangFuse

No custom adapter class. A single `CallbackHandler` instance created at startup and passed via `config["callbacks"]` on every `ainvoke`. Auto-traces all LangGraph nodes, LLM calls, and tool invocations.

### 4.4 DI Container

`infrastructure/container/container.py` instantiates all adapters and repos, wires them into `MessageProcessingService`. FastAPI routers use `Depends()` to pull the service.

---

## 5. Application Layer

### 5.1 MessageProcessingService

Single entry point for all Telegram updates:

1. `get_or_create` lead by `telegram_chat_id`
2. If voice → download OGG → `ISpeechService.transcribe()` → text
3. `agent_graph.ainvoke({"messages": [HumanMessage(text)]}, config)` with `thread_id=lead.id`
4. Extract final `AIMessage.content`
5. If original voice → TTS → `send_voice`; else `send_text`
6. Update `lead.last_contacted_at` + write to `conversation_history` (fire-and-forget)

### 5.2 LangGraph Agent

- Built with `create_react_agent` (model node ↔ tools node loop)
- LLM: `ChatOpenAI` → DeepSeek (`deepseek-chat`, `base_url=https://api.deepseek.com/v1`, `temperature=0.3`, `max_retries=3`)
- Checkpointer: `AsyncPostgresSaver` — full conversation history persisted per `lead.id` in Supabase
- `state_modifier`: prepends system prompt + `trim_messages` (max 6 000 tokens, strategy `"last"`)
- LangFuse `CallbackHandler` in `config["callbacks"]` on every `ainvoke`

### 5.3 System Prompt

Enforces dealership identity, language mirroring, and strict scope guard: off-topic questions receive a canned reply with no tools invoked.

### 5.4 Tools

Factory closure pattern — `make_<tool>(deps)` returns a `@tool`-decorated async function:

| Tool | When called | Behaviour |
|------|-------------|-----------|
| `get_inventory` | Customer asks about vehicles | `IInventoryRepository.get_cars(filters)` → JSON array (max 10) |
| `get_calendar_events` | Before proposing times | `ICalendarService.get_available_slots()` → free 1-hour windows |
| `schedule_meeting` | Customer confirms slot | `ICalendarService.create_event()` + `IMeetingRepository.create()` + sets lead `converted` |
| `send_email` | Customer wants specs by email | `IEmailService.send_car_specs()` + `IEmailLogRepository.log()` |

---

## 6. API Layer

### 6.1 Endpoints

- `POST /webhook/telegram` — validates `TelegramUpdate`, adds `processor.receive_message(update)` to `BackgroundTasks`, returns `{"ok": True}` immediately
- `GET /health` — checks DB (`SELECT 1`), DeepSeek reachability, LangFuse status; returns per-dependency status JSON

### 6.2 Startup (lifespan)

1. `telegram_adapter.set_webhook(url=f"{BASE_URL}/webhook/telegram")`
2. `checkpointer.setup()` — creates `langgraph_checkpoints` table if absent
3. On shutdown: `engine.dispose()`

### 6.3 Running Locally

```bash
uvicorn app.main:app --reload --port 8000
```

Telegram requires a public HTTPS URL. Use `ngrok` (or similar) to tunnel and set `BASE_URL` in `.env` to the tunnel URL.

---

## 7. Database Schema & Migrations

### 7.1 Tables

| Table | Purpose |
|-------|---------|
| `inventory` | Vehicle catalogue |
| `leads` | Customer records |
| `conversation_history` | Audit log (analytics only — live context in `langgraph_checkpoints`) |
| `meetings` | Scheduled inspections linked to Google Calendar |
| `reminders` | Follow-up reminders for not-yet-ready customers |
| `email_sent_logs` | Log of every email send attempt |
| `langgraph_checkpoints` | Managed by LangGraph `checkpointer.setup()` — do not touch |

### 7.2 Alembic Migrations

- `0001_initial_schema.py` — creates all six application tables + indexes
- `0002_seed_inventory.py` — inserts 10 seed vehicles

```bash
alembic upgrade head    # apply all migrations
alembic downgrade -1    # roll back one step
```

---

## 8. Error Handling

| Layer | Strategy |
|-------|----------|
| Webhook handler | Always returns `200 OK`; processing happens in `BackgroundTasks` |
| `MessageProcessingService` | Catches all exceptions; sends fallback message to user |
| LangGraph tools | Return structured error string — agent decides whether to retry |
| External adapters | `max_retries=3` with exponential backoff (built into `ChatOpenAI`) |
| LLM unavailable | Caught at service layer; sends canned fallback to user |

**Fallback message:** *"I'm having a little trouble right now. Please try again in a moment or contact us directly."*

**Logging:** Structured JSON via `python-json-logger`. `DEBUG` in dev, `INFO` in production. PII fields (phone, email) masked. All LLM traces go to LangFuse via callback handler.

---

## 9. Testing Strategy

### 9.1 Unit Tests (`tests/unit/`)

No I/O. Fast. Fully isolated.

- `test_domain/` — entity construction, enum transitions, `_to_domain()` mapping
- `test_tools/` — each tool with fake repo/service implementations; verifies filter construction, JSON output, status updates
- `test_message_processor/` — mocks agent graph + all ports; verifies voice→STT→agent→TTS and text→agent→text paths
- `test_agent_graph/` — verifies `state_modifier` trims messages correctly and prepends system prompt

### 9.2 Integration Tests (`tests/integration/`)

Hit real Supabase. External APIs (Telegram, OpenAI, Calendar, Gmail) are mocked.

- `test_inventory_repo/` — `get_cars` with filter combinations, `get_car_by_id`
- `test_lead_repo/` — `get_or_create` idempotency, `update` persistence
- `test_meeting_repo/` + `test_reminder_repo/` — create + retrieve
- `test_webhook/` — FastAPI `TestClient` posts `TelegramUpdate`; real DB repos, mocked external adapters

### 9.3 Fixtures (`tests/conftest.py`)

- Async DB session connected to Supabase (with rollback per test)
- `pytest-asyncio` in `asyncio_mode = "auto"`
- Factory fixtures for `Car`, `Lead`, `Meeting` domain objects

---

## 10. Configuration

All values via `pydantic-settings` reading from `.env`:

```
APP_ENV, BASE_URL, LOG_LEVEL
TELEGRAM_BOT_TOKEN
DATABASE_URL
DEEPSEEK_API_KEY
OPENAI_API_KEY
LANGFUSE_SECRET_KEY, LANGFUSE_PUBLIC_KEY, LANGFUSE_HOST
GOOGLE_SERVICE_ACCOUNT_JSON, GOOGLE_CALENDAR_ID, GMAIL_SENDER
DEALERSHIP_NAME, DEALERSHIP_ADDRESS
```

`.env` is gitignored. `.env.example` with placeholder values is committed.

---

## 11. Dependencies (pyproject.toml)

```toml
[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.111"
uvicorn = {extras = ["standard"], version = "^0.30"}
pydantic = "^2.7"
pydantic-settings = "^2.3"
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
asyncpg = "^0.29"
alembic = "^1.13"
langchain = "^0.3"
langchain-openai = "^0.2"
langchain-core = "^0.3"
langgraph = "^0.2"
langgraph-checkpoint-postgres = "^0.1"
openai = "^1.30"
langfuse = "^2.36"
google-api-python-client = "^2.130"
google-auth-httplib2 = "^0.2"
google-auth-oauthlib = "^1.2"
python-telegram-bot = "^21.3"
httpx = "^0.27"
python-json-logger = "^2.0"

[tool.poetry.dev-dependencies]
pytest = "^8.2"
pytest-asyncio = "^0.23"
pytest-mock = "^3.14"
```
