# Backend Application Specification
## Car Dealership Telegram Chatbot

**Version:** 2.0.0
**Stack:** Python · FastAPI · SQLAlchemy · Alembic · LangChain · LangGraph · DeepSeek · OpenAI · LangFuse · Google Calendar · Gmail
**Architecture:** Hexagonal (Ports & Adapters)

---

## Table of Contents

1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Directory Structure](#3-directory-structure)
4. [Domain Layer](#4-domain-layer)
5. [Ports (Interfaces)](#5-ports-interfaces)
6. [Infrastructure Adapters](#6-infrastructure-adapters)
7. [Application Services & Agent](#7-application-services--agent)
8. [API Layer](#8-api-layer)
9. [Database Schema](#9-database-schema)
10. [Tools Specification](#10-tools-specification)
11. [Business Rule Workflow](#11-business-rule-workflow)
12. [Configuration & Environment Variables](#12-configuration--environment-variables)
13. [Error Handling & Logging](#13-error-handling--logging)
14. [Sequence Diagrams](#14-sequence-diagrams)
15. [Dependencies](#15-dependencies)

---

## 1. System Overview

This backend powers a Telegram chatbot for a car dealership. It accepts text and voice messages from customers and can:

- Answer dealership-related questions (scope-guarded — off-topic questions are rejected)
- Search vehicle inventory by brand, model, price, km, condition, fuel type, etc.
- Schedule in-person car inspection meetings via Google Calendar
- Capture follow-up reminders when a customer is not ready to buy
- Send car specification sheets by email via Gmail

**Key technology decisions:**

| Concern | Choice | Reason |
|---------|--------|--------|
| Agent orchestration | LangGraph `create_react_agent` | Production-ready ReAct loop with native tool-calling and checkpointing |
| Conversation memory | LangGraph `AsyncPostgresSaver` | Zero-code persistence; state stored per `thread_id` in PostgreSQL |
| LLM | DeepSeek via `langchain-openai` | OpenAI-compatible API, cost-effective, tool-calling support |
| STT / TTS | OpenAI Whisper + TTS | High-quality voice handling |
| Observability | LangFuse callback handler | Automatic tracing of every graph node, LLM call, and tool invocation |
| ORM / migrations | SQLAlchemy async + Alembic | Type-safe async queries; version-controlled schema changes |

---

## 2. Architecture

The application follows **Hexagonal Architecture** (Ports & Adapters) with three explicit layers:

```
┌─────────────────────────────────────────────────────────┐
│                INFRASTRUCTURE (driving)                  │
│         FastAPI handlers · Pydantic schemas              │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    APPLICATION                           │
│   MessageProcessingService · LangGraph Agent Graph      │
│   LangChain @tool definitions                           │
└──────┬───────────────────────────────────────┬──────────┘
       │                                       │
       ▼                                       ▼
┌─────────────────────┐         ┌──────────────────────────┐
│       DOMAIN         │         │  INFRASTRUCTURE (driven) │
│  Entities · Ports    │◄────────│  SQLAlchemy repos        │
│  (ABCs)             │         │  DeepSeek / OpenAI       │
└─────────────────────┘         │  Google Calendar / Gmail │
                                │  LangFuse · Telegram     │
                                │  LangGraph checkpointer  │
                                └──────────────────────────┘
```

**Layer rules:**

| Layer | Contains | May import from |
|-------|----------|-----------------|
| `domain` | Entities, port ABCs, exceptions | Nothing outside `domain` |
| `application` | LangGraph graph, `@tool` definitions, orchestration services | `domain` only |
| `infrastructure` | ORM models, repo adapters, API adapters, handlers, schemas, DI container | `domain` + `application` |

> ORM models are **never imported** by `domain` or `application`. The mapping between ORM rows and domain entities happens exclusively inside `infrastructure/repositories/`.

---

## 3. Directory Structure

```
app/
├── main.py                              # FastAPI app factory + lifespan (startup/shutdown)
├── config.py                            # Pydantic Settings — reads from .env
│
├── domain/
│   ├── entities/
│   │   ├── car.py                       # Car dataclass
│   │   ├── lead.py                      # Lead dataclass
│   │   ├── meeting.py                   # Meeting dataclass
│   │   └── reminder.py                  # Reminder dataclass
│   ├── repositories/                    # Port ABCs for data persistence
│   │   ├── inventory_repository.py      # IInventoryRepository
│   │   ├── lead_repository.py           # ILeadRepository
│   │   ├── meeting_repository.py        # IMeetingRepository
│   │   ├── reminder_repository.py       # IReminderRepository
│   │   └── email_log_repository.py      # IEmailLogRepository
│   ├── use_cases/                       # Port ABCs for external services
│   │   ├── speech_use_case.py           # ISpeechService (STT + TTS)
│   │   ├── calendar_use_case.py         # ICalendarService
│   │   ├── email_use_case.py            # IEmailService
│   │   └── telegram_use_case.py         # ITelegramService
│   └── exceptions.py
│
├── application/
│   ├── services/
│   │   ├── message_processor.py         # Entry point: voice/text pipeline + response dispatch
│   │   ├── agent_graph.py               # LangGraph graph (build_agent_graph factory)
│   │   └── tools/                       # LangChain @tool closures
│   │       ├── get_inventory.py
│   │       ├── get_calendar_events.py
│   │       ├── schedule_meeting.py
│   │       └── send_email.py
│   └── validators/
│       └── message_validator.py         # Validates incoming Telegram payloads
│
├── infrastructure/
│   ├── handlers/                        # FastAPI routers
│   │   ├── webhook_handler.py           # POST /webhook/telegram
│   │   └── health_handler.py            # GET /health
│   ├── database/
│   │   ├── engine.py                    # Async engine, sessionmaker, get_checkpointer()
│   │   ├── base.py                      # DeclarativeBase
│   │   └── models/                      # SQLAlchemy ORM models
│   │       ├── inventory_model.py
│   │       ├── lead_model.py
│   │       ├── meeting_model.py
│   │       ├── reminder_model.py
│   │       └── email_log_model.py
│   ├── repositories/                    # Implements domain repository ports
│   │   ├── base_repository.py
│   │   ├── inventory_repo.py
│   │   ├── lead_repo.py
│   │   ├── meeting_repo.py
│   │   ├── reminder_repo.py
│   │   └── email_log_repo.py
│   ├── events/                          # Implements domain use_case ports
│   │   ├── openai_adapter.py            # ISpeechService — Whisper STT + TTS
│   │   ├── calendar_adapter.py          # ICalendarService — Google Calendar
│   │   ├── gmail_adapter.py             # IEmailService — Gmail API
│   │   └── telegram_adapter.py          # ITelegramService — Bot API
│   ├── schemas/
│   │   ├── telegram_schema.py           # TelegramUpdate, Message, Voice
│   │   └── health_schema.py
│   └── container/
│       └── container.py                 # DI wiring: binds ports to adapters + builds agent graph
│
├── tests/
│   ├── unit/
│   └── integration/
│
└── alembic/
    ├── env.py
    ├── script.py.mako
    └── versions/
        └── 0001_initial_schema.py
```

> **Root-level:** `alembic.ini` · `pyproject.toml` · `.env` · `Dockerfile` · `docker-compose.yml`

---

## 4. Domain Layer

> The domain has **no imports** from `langchain`, `sqlalchemy`, `fastapi`, or any third-party library.

### 4.1 Entities

```python
# domain/entities/car.py
@dataclass
class Car:
    id: str
    brand: str
    model: str
    year: int
    color: str
    price: float
    km: int                 # odometer in kilometres
    fuel_type: str          # gasoline | diesel | electric | hybrid
    transmission: str       # automatic | manual
    condition: str          # new | used | certified
    vin: str | None
    description: str | None
    image_url: str | None
    available: bool
    created_at: datetime
```

```python
# domain/entities/lead.py
@dataclass
class Lead:
    id: str
    telegram_chat_id: str
    name: str | None
    phone: str | None
    email: str | None
    status: LeadStatus          # new | interested | not_interested | converted
    preferred_language: str     # "en" | "es" | etc.
    last_contacted_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

```python
# domain/entities/meeting.py
@dataclass
class Meeting:
    id: str
    lead_id: str
    car_id: str
    google_event_id: str | None
    google_meet_link: str | None
    scheduled_at: datetime
    duration_minutes: int       # default 60
    location: str
    status: str                 # scheduled | cancelled | completed
    notes: str | None
    created_at: datetime
    updated_at: datetime
```

```python
# domain/entities/reminder.py
@dataclass
class Reminder:
    id: str
    lead_id: str
    remind_at: datetime
    message: str
    sent: bool
    sent_at: datetime | None
    created_at: datetime
```

### 4.2 Enums

```python
class LeadStatus(str, Enum):
    NEW = "new"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CONVERTED = "converted"
```

> **Removed `MessageType` enum** — intent classification is now handled entirely inside the LangGraph agent via the system prompt and tool selection. There is no separate classification step.

---

## 5. Ports (Interfaces)

### 5.1 Repository Ports (`domain/repositories/`)

```python
class IInventoryRepository(ABC):
    @abstractmethod
    async def get_cars(self, filters: dict | None = None) -> list[Car]: ...
    @abstractmethod
    async def get_car_by_id(self, car_id: str) -> Car | None: ...

class ILeadRepository(ABC):
    @abstractmethod
    async def get_or_create(self, telegram_chat_id: str) -> Lead: ...
    @abstractmethod
    async def update(self, lead: Lead) -> Lead: ...

class IMeetingRepository(ABC):
    @abstractmethod
    async def create(self, meeting: Meeting) -> Meeting: ...
    @abstractmethod
    async def get_by_lead(self, lead_id: str) -> list[Meeting]: ...

class IReminderRepository(ABC):
    @abstractmethod
    async def create(self, reminder: Reminder) -> Reminder: ...
    @abstractmethod
    async def get_pending(self, before: datetime) -> list[Reminder]: ...
    @abstractmethod
    async def mark_sent(self, reminder_id: str) -> None: ...

class IEmailLogRepository(ABC):
    @abstractmethod
    async def log(self, lead_id: str, car_id: str, recipient: str,
                  subject: str, template: str, success: bool, error: str | None) -> None: ...
```

### 5.2 Service Ports (`domain/use_cases/`)

```python
class ISpeechService(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, file_format: str = "ogg") -> str: ...
    @abstractmethod
    async def synthesize(self, text: str) -> bytes: ...

class ICalendarService(ABC):
    @abstractmethod
    async def get_available_slots(self, days_ahead: int = 14) -> list[dict]: ...
    @abstractmethod
    async def create_event(self, title: str, start: datetime, end: datetime,
                           attendee_email: str | None, description: str) -> str: ...

class IEmailService(ABC):
    @abstractmethod
    async def send_car_specs(self, recipient_email: str, car: Car) -> bool: ...

class ITelegramService(ABC):
    @abstractmethod
    async def send_text(self, chat_id: str, text: str) -> None: ...
    @abstractmethod
    async def send_voice(self, chat_id: str, audio_bytes: bytes) -> None: ...
    @abstractmethod
    async def download_voice(self, file_id: str) -> bytes: ...
```

> **Removed `ILLMService` and `IObservabilityService` ports.** LangChain owns the LLM instance directly inside the agent graph; LangFuse is integrated via its `CallbackHandler` passed into `ainvoke` config — neither needs a domain abstraction.

---

## 6. Infrastructure Adapters

### 6.1 Database — SQLAlchemy + Alembic

**Connection:** `postgresql+asyncpg://postgres:<pwd>@db.xorgqqkizkyktsuxoxhz.supabase.co:5432/postgres`

#### Engine & Session (`infrastructure/database/engine.py`)

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

engine = create_async_engine(settings.DATABASE_URL, pool_size=10, max_overflow=20)
AsyncSessionFactory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session

async def get_checkpointer() -> AsyncPostgresSaver:
    checkpointer = AsyncPostgresSaver.from_conn_string(settings.DATABASE_URL)
    await checkpointer.setup()   # creates langgraph_checkpoints table if absent
    return checkpointer
```

#### ORM Models — example (`infrastructure/database/models/inventory_model.py`)

```python
class InventoryORM(Base):
    __tablename__ = "inventory"

    id:           Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand:        Mapped[str]       = mapped_column(String(100), nullable=False)
    model:        Mapped[str]       = mapped_column(String(100), nullable=False)
    year:         Mapped[int]       = mapped_column(Integer, nullable=False)
    color:        Mapped[str]       = mapped_column(String(50), nullable=False)
    price:        Mapped[float]     = mapped_column(Numeric(12, 2), nullable=False)
    km:           Mapped[int]       = mapped_column(Integer, default=0)
    fuel_type:    Mapped[str]       = mapped_column(String(30), nullable=False)
    transmission: Mapped[str]       = mapped_column(String(20), nullable=False)
    condition:    Mapped[str]       = mapped_column(String(20), default="used")
    vin:          Mapped[str | None]= mapped_column(String(17), unique=True, nullable=True)
    description:  Mapped[str | None]= mapped_column(Text, nullable=True)
    image_url:    Mapped[str | None]= mapped_column(Text, nullable=True)
    available:    Mapped[bool]      = mapped_column(Boolean, default=True)
    created_at:   Mapped[datetime]  = mapped_column(server_default=func.now())
```

#### Repository pattern — example (`infrastructure/repositories/inventory_repo.py`)

```python
class InventoryRepository(BaseRepository, IInventoryRepository):
    async def get_cars(self, filters: dict | None = None) -> list[Car]:
        stmt = select(InventoryORM).where(InventoryORM.available == True)
        if filters:
            if filters.get("brand"):
                stmt = stmt.where(InventoryORM.brand.ilike(f"%{filters['brand']}%"))
            if filters.get("max_km"):
                stmt = stmt.where(InventoryORM.km <= filters["max_km"])
            if filters.get("condition"):
                stmt = stmt.where(InventoryORM.condition == filters["condition"])
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._to_domain(r) for r in rows]

    def _to_domain(self, r: InventoryORM) -> Car:
        return Car(id=str(r.id), brand=r.brand, model=r.model, year=r.year,
                   color=r.color, price=float(r.price), km=r.km,
                   fuel_type=r.fuel_type, transmission=r.transmission,
                   condition=r.condition, vin=r.vin, description=r.description,
                   image_url=r.image_url, available=r.available, created_at=r.created_at)
```

#### Alembic

```bash
alembic revision --autogenerate -m "description"  # generate migration from model changes
alembic upgrade head                               # apply all pending migrations
alembic downgrade -1                               # roll back one step
```

```ini
# alembic.ini
[alembic]
script_location = alembic
sqlalchemy.url = %(DATABASE_URL)s
```

### 6.2 OpenAI Adapter (`infrastructure/events/openai_adapter.py`)

Implements `ISpeechService`:
- **STT:** `whisper-1` via `audio.transcriptions.create` — accepts OGG bytes, returns text
- **TTS:** `tts-1` voice `alloy` via `audio.speech.create` — returns MP3 bytes

### 6.3 Google Calendar Adapter (`infrastructure/events/calendar_adapter.py`)

Implements `ICalendarService`:
- OAuth2 service account credentials, scope `https://www.googleapis.com/auth/calendar`
- `get_available_slots`: uses FreeBusy API to find free 1-hour windows during business hours (9 AM – 6 PM) over the next N days
- `create_event`: creates a calendar event with optional attendee email invite

### 6.4 Gmail Adapter (`infrastructure/events/gmail_adapter.py`)

Implements `IEmailService`:
- OAuth2 service account credentials, scope `https://www.googleapis.com/auth/gmail.send`
- Sends HTML email with car name, specs table, image, and price
- Calls `IEmailLogRepository.log()` after every send attempt

### 6.5 Telegram Adapter (`infrastructure/events/telegram_adapter.py`)

Implements `ITelegramService`:
- `send_text` / `send_voice`: Bot API `sendMessage` / `sendVoice`
- `download_voice`: downloads OGG file by `file_id`
- Sets the webhook URL on application startup

### 6.6 LangFuse — Callback Handler

LangFuse integration uses **no custom adapter class**. A `CallbackHandler` instance is created once and passed into every `ainvoke` call via `config["callbacks"]`. This auto-traces all LangGraph nodes, LLM calls, and tool executions.

```python
from langfuse.callback import CallbackHandler

langfuse_handler = CallbackHandler(
    secret_key=settings.LANGFUSE_SECRET_KEY,
    public_key=settings.LANGFUSE_PUBLIC_KEY,
    host=settings.LANGFUSE_HOST,
)
```

---

## 7. Application Services & Agent

### 7.1 `MessageProcessingService` (`application/services/message_processor.py`)

Single entry point for all Telegram updates.

```
receive_message(update)
  1. Resolve or create Lead via ILeadRepository (by telegram_chat_id)
  2. If voice message → download_voice → ISpeechService.transcribe() → text
  3. agent_graph.ainvoke({"messages": [HumanMessage(text)]}, config)
  4. Extract final AIMessage text from result
  5. If original was voice → ISpeechService.synthesize() → ITelegramService.send_voice()
     Else → ITelegramService.send_text()
  6. Update lead.last_contacted_at
```

### 7.2 LangGraph Agent Graph (`application/services/agent_graph.py`)

Built with `create_react_agent` — a prebuilt LangGraph `StateGraph` with two nodes (**model** → **tools**) that loop until the model returns a response with no tool calls.

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI

def build_agent_graph(
    checkpointer: AsyncPostgresSaver,
    tools: list,           # injected @tool closures with bound dependencies
) -> CompiledGraph:

    llm = ChatOpenAI(
        model="deepseek-chat",
        base_url="https://api.deepseek.com/v1",
        api_key=settings.DEEPSEEK_API_KEY,
        temperature=0.3,
        max_retries=3,
    )

    return create_react_agent(
        model=llm,
        tools=tools,
        checkpointer=checkpointer,
        state_modifier=_build_state_modifier(llm),
    )
```

**Invocation** (inside `MessageProcessingService`):

```python
config = {
    "configurable": {"thread_id": str(lead.id)},
    "callbacks": [langfuse_handler],
}
result = await agent_graph.ainvoke(
    {"messages": [HumanMessage(content=user_text)]},
    config=config,
)
response_text = result["messages"][-1].content
```

### 7.3 Memory & Context Window

LangGraph's `AsyncPostgresSaver` checkpointer persists the full message list per `thread_id` between invocations. No manual history loading is needed — every `ainvoke` call automatically has access to the full conversation.

`trim_messages` is applied inside `state_modifier` to keep the token budget under 6 000 tokens:

```python
from langchain_core.messages import trim_messages, SystemMessage

def _build_state_modifier(llm):
    def state_modifier(state: dict) -> list:
        trimmed = trim_messages(
            state["messages"],
            max_tokens=6000,
            strategy="last",
            token_counter=llm,
            include_system=True,
            allow_partial=False,
        )
        return [SystemMessage(content=SYSTEM_PROMPT)] + trimmed
    return state_modifier
```

### 7.4 Tool Closures (`application/services/tools/`)

Tools use a **factory closure** pattern: a `make_<tool>()` function accepts injected dependencies and returns a `@tool`-decorated async function. This keeps tools testable and decoupled from infrastructure.

```python
# application/services/tools/get_inventory.py
from langchain_core.tools import tool

def make_get_inventory_tool(repo: IInventoryRepository):
    @tool
    async def get_inventory(
        brand: str | None = None,
        model: str | None = None,
        year: int | None = None,
        color: str | None = None,
        min_price: float | None = None,
        max_price: float | None = None,
        min_km: int | None = None,
        max_km: int | None = None,
        condition: Literal["new", "used", "certified"] | None = None,
        fuel_type: Literal["gasoline", "diesel", "electric", "hybrid"] | None = None,
        transmission: Literal["automatic", "manual"] | None = None,
    ) -> str:
        """Search the car inventory. Use when the customer asks about available
        vehicles, models, prices, colors, km, or specs. All filters are optional.
        Returns JSON array of matching cars (max 10)."""
        filters = {k: v for k, v in locals().items() if v is not None and k != "repo"}
        cars = await repo.get_cars(filters)
        return json.dumps([asdict(c) for c in cars[:10]], default=str)
    return get_inventory
```

Tools are instantiated in `infrastructure/container/container.py` with their concrete dependencies and passed to `build_agent_graph()`.

### 7.5 System Prompt

```
You are an AI assistant for {dealership_name}, a car dealership.
Help customers find vehicles, schedule visits, and receive car information by email.
Be friendly, professional, and concise. Always reply in the customer's language.

SCOPE RESTRICTION: Only answer questions about cars, inventory, pricing, scheduling,
test drives, or email specs. For anything else respond ONLY with:
"I can only help with questions about our car inventory, scheduling visits, and
sending vehicle information. Is there anything car-related I can help you with today?"

Current date: {current_date}
Customer: {lead_name}
```

---

## 8. API Layer

Route handlers in `infrastructure/handlers/` are thin: validate input → delegate to `MessageProcessingService` → return.

### 8.1 `POST /webhook/telegram`

```python
@router.post("/webhook/telegram")
async def telegram_webhook(
    update: TelegramUpdate,
    background_tasks: BackgroundTasks,
    processor: MessageProcessingService = Depends(),
):
    background_tasks.add_task(processor.receive_message, update)
    return {"ok": True}   # respond 200 immediately to Telegram
```

Supported update types: `message.text`, `message.voice` (OGG/Opus).

### 8.2 `GET /health`

```json
{
  "status": "ok",
  "version": "2.0.0",
  "dependencies": { "database": "ok", "deepseek": "ok", "langfuse": "ok" }
}
```

### 8.3 Startup

```python
# main.py — lifespan context manager (replaces deprecated @app.on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    await telegram_adapter.set_webhook(url=f"{settings.BASE_URL}/webhook/telegram")
    await checkpointer.setup()
    yield
    await engine.dispose()
```

---

## 9. Database Schema

**Supabase PostgreSQL:** `xorgqqkizkyktsuxoxhz.supabase.co`

> LangGraph also creates a `langgraph_checkpoints` table automatically via `checkpointer.setup()`. This table stores the full agent state per `thread_id` and is managed entirely by LangGraph — do not modify it manually.

### 9.1 `inventory`

```sql
CREATE TABLE inventory (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    brand         VARCHAR(100)   NOT NULL,
    model         VARCHAR(100)   NOT NULL,
    year          INTEGER        NOT NULL,
    color         VARCHAR(50)    NOT NULL,
    price         NUMERIC(12,2)  NOT NULL,
    km            INTEGER        NOT NULL DEFAULT 0,
    fuel_type     VARCHAR(30)    NOT NULL,  -- gasoline | diesel | electric | hybrid
    transmission  VARCHAR(20)    NOT NULL,  -- automatic | manual
    condition     VARCHAR(20)    NOT NULL DEFAULT 'used',  -- new | used | certified
    vin           VARCHAR(17)    UNIQUE,
    description   TEXT,
    image_url     TEXT,
    available     BOOLEAN        NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ    NOT NULL DEFAULT now()
);
```

**Seed data (10 vehicles):**

| Brand | Model | Year | Color | Price | Km | Fuel | Trans | Condition |
|-------|-------|------|-------|-------|----|------|-------|-----------|
| Toyota | Corolla | 2022 | White | 22,500 | 28,000 | Gasoline | Automatic | Used |
| Toyota | RAV4 | 2023 | Silver | 34,900 | 0 | Hybrid | Automatic | New |
| Honda | Civic | 2021 | Black | 20,000 | 45,000 | Gasoline | Manual | Used |
| Honda | CR-V | 2022 | Blue | 31,500 | 18,500 | Gasoline | Automatic | Certified |
| Ford | Mustang | 2020 | Red | 38,000 | 62,000 | Gasoline | Manual | Used |
| Ford | Explorer | 2023 | Gray | 45,000 | 0 | Gasoline | Automatic | New |
| Chevrolet | Spark | 2022 | Yellow | 16,000 | 33,000 | Gasoline | Automatic | Used |
| BMW | 320i | 2021 | White | 52,000 | 24,000 | Gasoline | Automatic | Certified |
| Tesla | Model 3 | 2023 | Black | 48,500 | 0 | Electric | Automatic | New |
| Nissan | Sentra | 2022 | Silver | 19,900 | 41,000 | Gasoline | Automatic | Used |

### 9.2 `leads`

```sql
CREATE TABLE leads (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    telegram_chat_id   VARCHAR(50)  NOT NULL UNIQUE,
    name               VARCHAR(200),
    phone              VARCHAR(30),
    email              VARCHAR(200),
    status             VARCHAR(30)  NOT NULL DEFAULT 'new',  -- new | interested | not_interested | converted
    preferred_language VARCHAR(10)  NOT NULL DEFAULT 'en',
    last_contacted_at  TIMESTAMPTZ,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

### 9.3 `conversation_history`

Used for **analytics and auditing only** — the live agent context is stored in `langgraph_checkpoints`.

```sql
CREATE TABLE conversation_history (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id        UUID         NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
    role           VARCHAR(20)  NOT NULL,   -- user | assistant | tool
    content        TEXT         NOT NULL,
    input_modality VARCHAR(10)  NOT NULL DEFAULT 'text',  -- text | voice
    tool_calls     JSONB,
    tokens_used    INTEGER,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX idx_conv_history_lead ON conversation_history(lead_id, created_at DESC);
```

### 9.4 `meetings`

```sql
CREATE TABLE meetings (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id          UUID         NOT NULL REFERENCES leads(id),
    car_id           UUID         NOT NULL REFERENCES inventory(id),
    google_event_id  VARCHAR(200),
    google_meet_link TEXT,
    scheduled_at     TIMESTAMPTZ  NOT NULL,
    duration_minutes INTEGER      NOT NULL DEFAULT 60,
    location         TEXT         NOT NULL DEFAULT 'Dealership showroom',
    status           VARCHAR(30)  NOT NULL DEFAULT 'scheduled',  -- scheduled | cancelled | completed
    notes            TEXT,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

### 9.5 `reminders`

```sql
CREATE TABLE reminders (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id     UUID        NOT NULL REFERENCES leads(id),
    remind_at   TIMESTAMPTZ NOT NULL,
    message     TEXT        NOT NULL,
    sent        BOOLEAN     NOT NULL DEFAULT FALSE,
    sent_at     TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_reminders_pending ON reminders(remind_at) WHERE sent = FALSE;
```

### 9.6 `email_sent_logs`

```sql
CREATE TABLE email_sent_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id         UUID         NOT NULL REFERENCES leads(id),
    car_id          UUID         NOT NULL REFERENCES inventory(id),
    recipient_email VARCHAR(200) NOT NULL,
    subject         VARCHAR(300) NOT NULL,
    template_used   VARCHAR(100) NOT NULL DEFAULT 'car_specs',
    success         BOOLEAN      NOT NULL DEFAULT TRUE,
    error_msg       TEXT,
    sent_at         TIMESTAMPTZ  NOT NULL DEFAULT now()
);
```

---

## 10. Tools Specification

All tools are `@tool`-decorated async functions in `application/services/tools/`. LangChain auto-generates the JSON schema from type hints and the docstring.

### 10.1 `get_inventory`

```python
@tool
async def get_inventory(
    brand: str | None = None, model: str | None = None, year: int | None = None,
    color: str | None = None, min_price: float | None = None, max_price: float | None = None,
    min_km: int | None = None, max_km: int | None = None,
    condition: Literal["new","used","certified"] | None = None,
    fuel_type: Literal["gasoline","diesel","electric","hybrid"] | None = None,
    transmission: Literal["automatic","manual"] | None = None,
) -> str:
    """Search available car inventory. All filters optional. Returns JSON array (max 10)."""
```

### 10.2 `get_calendar_events`

```python
@tool
async def get_calendar_events(days_ahead: int = 14) -> str:
    """Get available 1-hour appointment slots during business hours (9 AM–6 PM)
    over the next N days. Always call before proposing times to the customer."""
```

### 10.3 `schedule_meeting`

```python
@tool
async def schedule_meeting(
    car_id: str, lead_id: str, scheduled_at: str,
    attendee_email: str | None = None, notes: str | None = None,
) -> str:
    """Create a Google Calendar event and persist a meeting record.
    scheduled_at must be an ISO8601 datetime string."""
```

### 10.4 `send_email`

```python
@tool
async def send_email(car_id: str, recipient_email: str, lead_id: str) -> str:
    """Send a car specification HTML email via Gmail. Logs the result to email_sent_logs."""
```

---

## 11. Business Rule Workflow

### 11.1 Main Flow

```
Telegram Update received
        │
        ▼
Voice? → YES: download OGG → Whisper STT → text
        NO:  use message.text
        │
        ▼
Get or create Lead (by telegram_chat_id)
        │
        ▼
LangGraph agent.ainvoke(message, thread_id=lead.id)
        │
        ├── System prompt enforces scope → off-topic? → canned reply, no tools
        │
        ├── In-scope → agent selects tool(s) and loops until done
        │       ├── get_inventory   → present results, offer to schedule or email
        │       ├── get_calendar_events + schedule_meeting → confirm booking
        │       ├── send_email      → confirm send
        │       └── no tool needed  → answer from context (greet, recap, etc.)
        │
        └── Final AIMessage text extracted
                │
                ▼
        Voice input? → TTS → send_voice
        Text input?  → send_text
        │
        ▼
Update lead.last_contacted_at
Write turn to conversation_history (async, non-blocking)
```

### 11.2 Intent-Specific Behaviours

**General / greeting:** Agent responds with dealership capabilities. Sets lead `status = interested` on first contact.

**Inventory inquiry:** Calls `get_inventory` with extracted filters. Returns up to 5 cars with brand, model, year, km, price. Asks if the customer wants to schedule a visit or receive specs by email.

**Schedule meeting:** Calls `get_calendar_events`, presents 3 nearest slots, then calls `schedule_meeting` once the customer confirms. Sets lead `status = converted`.

**Not interested:** Asks when to follow up. Creates a `Reminder` record. Sets lead `status = not_interested`.

**Send email:** Asks for email address if missing, asks which car if not clear from context. Calls `send_email`.

**Out-of-scope:** Responds with the canned message. No tools invoked. Lead status unchanged.

### 11.3 Voice Policy

| Input | Output |
|-------|--------|
| Voice (OGG) | Voice (MP3, `alloy` voice) |
| Text | Text |

### 11.4 Memory

LangGraph `AsyncPostgresSaver` stores the full message history per `lead.id` (= `thread_id`). `trim_messages` caps the context at 6 000 tokens. No manual history management required.

---

## 12. Configuration & Environment Variables

```env
# Application
APP_ENV=production
BASE_URL=https://your-domain.com
LOG_LEVEL=INFO

# Telegram
TELEGRAM_BOT_TOKEN=<your_telegram_bot_token>

# Database
DATABASE_URL=postgresql+asyncpg://postgres:<password>@db.xorgqqkizkyktsuxoxhz.supabase.co:5432/postgres

# DeepSeek
DEEPSEEK_API_KEY=<your_deepseek_api_key>

# OpenAI (Whisper STT + TTS)
OPENAI_API_KEY=<your_openai_api_key>

# LangFuse
LANGFUSE_SECRET_KEY=<langfuse_secret_key>
LANGFUSE_PUBLIC_KEY=<langfuse_public_key>
LANGFUSE_HOST=https://us.cloud.langfuse.com

# Google
GOOGLE_SERVICE_ACCOUNT_JSON=<path_or_inline_json>
GOOGLE_CALENDAR_ID=primary
GMAIL_SENDER=your-dealership@gmail.com

# Dealership
DEALERSHIP_NAME=Your Dealership Name
DEALERSHIP_ADDRESS=123 Main Street, City, State
```

> ⚠️ Never commit API keys to source control. Use `.env` locally and a secrets manager (Doppler, AWS Secrets Manager) in production.

---

## 13. Error Handling & Logging

| Layer | Strategy |
|-------|----------|
| Webhook handler | Always return `200 OK`; process in `BackgroundTasks` |
| `MessageProcessingService` | Catch all exceptions; send fallback message to user |
| LangGraph tools | Return structured error string — agent decides whether to retry |
| External adapters | `max_retries=3` with exponential backoff (built into `ChatOpenAI`) |
| LLM unavailable | Caught at service layer; send canned fallback to user |

**Fallback message:** *"I'm having a little trouble right now. Please try again in a moment or contact us directly."*

**Logging:** Structured JSON via `python-json-logger`. `DEBUG` in dev, `INFO` in production. PII fields (phone, email) masked. All LLM traces go to LangFuse automatically via the callback handler.

---

## 14. Sequence Diagrams

### 14.1 Text → Inventory Search

```
Customer         Telegram       Backend (LangGraph)      DB
   │                │                 │                   │
   │── "Red Toyota?" ────────────────►│                   │
   │                │──── webhook ───►│                   │
   │                │                 │── agent.ainvoke() │
   │                │                 │   (model node)    │
   │                │                 │── tool: get_inventory
   │                │                 │──────────────────►│
   │                │                 │◄── [Corolla, RAV4]│
   │                │                 │   (model node)    │
   │◄── "Here are 2 red Toyotas..." ──│                   │
```

### 14.2 Voice → Schedule Meeting

```
Customer        Telegram    Backend               OpenAI      Google Cal
   │               │            │                   │              │
   │── [voice] ───────────────►│                   │              │
   │               │── DL OGG ►│                   │              │
   │               │            │── transcribe ────►│              │
   │               │            │◄── "I want to see it"           │
   │               │            │── agent.ainvoke()               │
   │               │            │── get_calendar_events ──────────►│
   │               │            │◄── available slots ─────────────│
   │               │            │── schedule_meeting ─────────────►│
   │               │            │◄── event created ───────────────│
   │               │            │── TTS ────────────►│             │
   │               │            │◄── audio ─────────│             │
   │◄── [voice: "Meeting booked"] ──│               │              │
```

---

## 15. Dependencies

```toml
[tool.poetry.dependencies]
python = "^3.11"

# Web
fastapi = "^0.111"
uvicorn = {extras = ["standard"], version = "^0.30"}
pydantic = "^2.7"
pydantic-settings = "^2.3"

# Database
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
asyncpg = "^0.29"
alembic = "^1.13"

# AI — LangChain + LangGraph
langchain = "^0.3"
langchain-openai = "^0.2"
langchain-core = "^0.3"
langgraph = "^0.2"
langgraph-checkpoint-postgres = "^0.1"
openai = "^1.30"                         # Whisper STT + TTS
langfuse = "^2.36"

# Google
google-api-python-client = "^2.130"
google-auth-httplib2 = "^0.2"
google-auth-oauthlib = "^1.2"

# Telegram
python-telegram-bot = "^21.3"

# Utilities
httpx = "^0.27"
python-json-logger = "^2.0"

[tool.poetry.dev-dependencies]
pytest = "^8.2"
pytest-asyncio = "^0.23"
pytest-mock = "^3.14"
```

---

*Specification v2.0 — CBTW Car Dealership Telegram Bot*
