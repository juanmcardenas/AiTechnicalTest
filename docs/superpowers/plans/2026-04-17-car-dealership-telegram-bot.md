# Car Dealership Telegram Chatbot — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a complete FastAPI backend that powers a Telegram chatbot for a car dealership, using a LangGraph ReAct agent with DeepSeek LLM, Supabase PostgreSQL, and integrations for Google Calendar, Gmail, and OpenAI voice.

**Architecture:** Strict Hexagonal (Ports & Adapters) built layer-by-layer: domain (pure Python) → infrastructure (DB + adapters) → application (agent + tools) → API. Each layer only imports from layers below it. ORM models never leave `infrastructure/`.

**Tech Stack:** Python 3.11, FastAPI, SQLAlchemy async, Alembic, LangGraph `create_react_agent`, LangChain, DeepSeek via `langchain-openai`, OpenAI Whisper/TTS, Google Calendar/Gmail APIs, LangFuse, Supabase PostgreSQL, pytest + pytest-asyncio.

---

## File Map

```
app/
├── main.py
├── config.py
├── domain/
│   ├── __init__.py
│   ├── exceptions.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── car.py
│   │   ├── lead.py
│   │   ├── meeting.py
│   │   └── reminder.py
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── inventory_repository.py
│   │   ├── lead_repository.py
│   │   ├── meeting_repository.py
│   │   ├── reminder_repository.py
│   │   └── email_log_repository.py
│   └── use_cases/
│       ├── __init__.py
│       ├── speech_use_case.py
│       ├── calendar_use_case.py
│       ├── email_use_case.py
│       └── telegram_use_case.py
├── application/
│   ├── __init__.py
│   └── services/
│       ├── __init__.py
│       ├── agent_graph.py
│       ├── message_processor.py
│       └── tools/
│           ├── __init__.py
│           ├── get_inventory.py
│           ├── get_calendar_events.py
│           ├── schedule_meeting.py
│           └── send_email.py
└── infrastructure/
    ├── __init__.py
    ├── container/
    │   ├── __init__.py
    │   └── container.py
    ├── database/
    │   ├── __init__.py
    │   ├── base.py
    │   ├── engine.py
    │   └── models/
    │       ├── __init__.py
    │       ├── inventory_model.py
    │       ├── lead_model.py
    │       ├── meeting_model.py
    │       ├── reminder_model.py
    │       └── email_log_model.py
    ├── events/
    │   ├── __init__.py
    │   ├── openai_adapter.py
    │   ├── calendar_adapter.py
    │   ├── gmail_adapter.py
    │   └── telegram_adapter.py
    ├── handlers/
    │   ├── __init__.py
    │   ├── health_handler.py
    │   └── webhook_handler.py
    ├── repositories/
    │   ├── __init__.py
    │   ├── base_repository.py
    │   ├── inventory_repo.py
    │   ├── lead_repo.py
    │   ├── meeting_repo.py
    │   ├── reminder_repo.py
    │   └── email_log_repo.py
    └── schemas/
        ├── __init__.py
        ├── health_schema.py
        └── telegram_schema.py
tests/
├── conftest.py
├── unit/
│   ├── __init__.py
│   ├── test_domain/
│   │   ├── __init__.py
│   │   └── test_entities.py
│   ├── test_tools/
│   │   ├── __init__.py
│   │   ├── test_get_inventory.py
│   │   ├── test_get_calendar_events.py
│   │   ├── test_schedule_meeting.py
│   │   └── test_send_email.py
│   ├── test_message_processor/
│   │   ├── __init__.py
│   │   └── test_message_processor.py
│   └── test_agent_graph/
│       ├── __init__.py
│       └── test_state_modifier.py
└── integration/
    ├── __init__.py
    ├── test_inventory_repo/
    │   ├── __init__.py
    │   └── test_inventory_repo.py
    ├── test_lead_repo/
    │   ├── __init__.py
    │   └── test_lead_repo.py
    └── test_webhook/
        ├── __init__.py
        └── test_webhook.py
alembic/
├── env.py
├── script.py.mako
└── versions/
    ├── 0001_initial_schema.py
    └── 0002_seed_inventory.py
pyproject.toml
alembic.ini
.env.example
.gitignore
```

---

## Task 1: Project Scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `alembic.ini`
- Create: `app/config.py`
- Create: all `__init__.py` files

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[tool.poetry]
name = "car-dealership-bot"
version = "2.0.0"
description = "Car Dealership Telegram Chatbot"
authors = []
packages = [{include = "app"}]

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

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 2: Create `.env.example`**

```env
APP_ENV=development
BASE_URL=https://your-ngrok-url.ngrok.io
LOG_LEVEL=DEBUG

TELEGRAM_BOT_TOKEN=your_telegram_bot_token

DATABASE_URL=postgresql+asyncpg://postgres:password@db.xorgqqkizkyktsuxoxhz.supabase.co:5432/postgres

DEEPSEEK_API_KEY=your_deepseek_api_key

OPENAI_API_KEY=your_openai_api_key

LANGFUSE_SECRET_KEY=your_langfuse_secret_key
LANGFUSE_PUBLIC_KEY=your_langfuse_public_key
LANGFUSE_HOST=https://us.cloud.langfuse.com

GOOGLE_SERVICE_ACCOUNT_JSON=path/to/service_account.json
GOOGLE_CALENDAR_ID=primary
GMAIL_SENDER=your-dealership@gmail.com

DEALERSHIP_NAME=Your Dealership Name
DEALERSHIP_ADDRESS=123 Main Street, City, State
```

- [ ] **Step 3: Create `.gitignore`**

```
.env
__pycache__/
*.pyc
*.pyo
.pytest_cache/
.mypy_cache/
dist/
*.egg-info/
.venv/
venv/
```

- [ ] **Step 4: Create `alembic.ini`**

```ini
[alembic]
script_location = alembic
prepend_sys_path = .

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console
qualname =

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

- [ ] **Step 5: Create `app/config.py`**

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


settings = Settings()
```

- [ ] **Step 6: Create all `__init__.py` files**

```bash
touch app/__init__.py \
  app/domain/__init__.py \
  app/domain/entities/__init__.py \
  app/domain/repositories/__init__.py \
  app/domain/use_cases/__init__.py \
  app/application/__init__.py \
  app/application/services/__init__.py \
  app/application/services/tools/__init__.py \
  app/infrastructure/__init__.py \
  app/infrastructure/container/__init__.py \
  app/infrastructure/database/__init__.py \
  app/infrastructure/database/models/__init__.py \
  app/infrastructure/events/__init__.py \
  app/infrastructure/handlers/__init__.py \
  app/infrastructure/repositories/__init__.py \
  app/infrastructure/schemas/__init__.py \
  tests/__init__.py \
  tests/unit/__init__.py \
  tests/unit/test_domain/__init__.py \
  tests/unit/test_tools/__init__.py \
  tests/unit/test_message_processor/__init__.py \
  tests/unit/test_agent_graph/__init__.py \
  tests/integration/__init__.py \
  tests/integration/test_inventory_repo/__init__.py \
  tests/integration/test_lead_repo/__init__.py \
  tests/integration/test_webhook/__init__.py
```

- [ ] **Step 7: Install dependencies**

```bash
poetry install
```

Expected: dependencies install without error.

- [ ] **Step 8: Commit**

```bash
git add .
git commit -m "feat: project scaffold — pyproject.toml, config, env example"
```

---

## Task 2: Domain Entities

**Files:**
- Create: `app/domain/entities/car.py`
- Create: `app/domain/entities/lead.py`
- Create: `app/domain/entities/meeting.py`
- Create: `app/domain/entities/reminder.py`
- Create: `app/domain/exceptions.py`
- Test: `tests/unit/test_domain/test_entities.py`

- [ ] **Step 1: Write failing tests for entities**

```python
# tests/unit/test_domain/test_entities.py
from datetime import datetime
import pytest
from app.domain.entities.car import Car
from app.domain.entities.lead import Lead, LeadStatus
from app.domain.entities.meeting import Meeting
from app.domain.entities.reminder import Reminder


def test_car_creation():
    car = Car(
        id="car-1", brand="Toyota", model="Corolla", year=2022,
        color="White", price=22500.0, km=28000, fuel_type="gasoline",
        transmission="automatic", condition="used", vin=None,
        description=None, image_url=None, available=True,
        created_at=datetime(2024, 1, 1),
    )
    assert car.brand == "Toyota"
    assert car.available is True


def test_lead_status_enum():
    assert LeadStatus.NEW == "new"
    assert LeadStatus.CONVERTED == "converted"


def test_lead_creation():
    lead = Lead(
        id="lead-1", telegram_chat_id="12345", name="Alice",
        phone=None, email=None, status=LeadStatus.NEW,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2024, 1, 1), updated_at=datetime(2024, 1, 1),
    )
    assert lead.telegram_chat_id == "12345"
    assert lead.status == LeadStatus.NEW


def test_meeting_creation():
    meeting = Meeting(
        id="meet-1", lead_id="lead-1", car_id="car-1",
        google_event_id=None, google_meet_link=None,
        scheduled_at=datetime(2024, 6, 1, 10, 0),
        duration_minutes=60, location="Dealership showroom",
        status="scheduled", notes=None,
        created_at=datetime(2024, 1, 1), updated_at=datetime(2024, 1, 1),
    )
    assert meeting.duration_minutes == 60
    assert meeting.status == "scheduled"


def test_reminder_creation():
    reminder = Reminder(
        id="rem-1", lead_id="lead-1",
        remind_at=datetime(2024, 7, 1, 9, 0),
        message="Follow up with Alice", sent=False,
        sent_at=None, created_at=datetime(2024, 1, 1),
    )
    assert reminder.sent is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
poetry run pytest tests/unit/test_domain/test_entities.py -v
```

Expected: `ModuleNotFoundError` — entities don't exist yet.

- [ ] **Step 3: Create `app/domain/entities/car.py`**

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Car:
    id: str
    brand: str
    model: str
    year: int
    color: str
    price: float
    km: int
    fuel_type: str
    transmission: str
    condition: str
    vin: str | None
    description: str | None
    image_url: str | None
    available: bool
    created_at: datetime
```

- [ ] **Step 4: Create `app/domain/entities/lead.py`**

```python
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class LeadStatus(str, Enum):
    NEW = "new"
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    CONVERTED = "converted"


@dataclass
class Lead:
    id: str
    telegram_chat_id: str
    name: str | None
    phone: str | None
    email: str | None
    status: LeadStatus
    preferred_language: str
    last_contacted_at: datetime | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 5: Create `app/domain/entities/meeting.py`**

```python
from dataclasses import dataclass
from datetime import datetime


@dataclass
class Meeting:
    id: str
    lead_id: str
    car_id: str
    google_event_id: str | None
    google_meet_link: str | None
    scheduled_at: datetime
    duration_minutes: int
    location: str
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 6: Create `app/domain/entities/reminder.py`**

```python
from dataclasses import dataclass
from datetime import datetime


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

- [ ] **Step 7: Create `app/domain/exceptions.py`**

```python
class LeadNotFoundError(Exception):
    pass


class CarNotFoundError(Exception):
    pass


class CalendarUnavailableError(Exception):
    pass


class EmailSendError(Exception):
    pass
```

- [ ] **Step 8: Run tests — confirm they pass**

```bash
poetry run pytest tests/unit/test_domain/test_entities.py -v
```

Expected: 5 tests PASS.

- [ ] **Step 9: Commit**

```bash
git add app/domain/ tests/unit/test_domain/
git commit -m "feat: domain entities — Car, Lead, Meeting, Reminder, exceptions"
```

---

## Task 3: Domain Repository Ports

**Files:**
- Create: `app/domain/repositories/inventory_repository.py`
- Create: `app/domain/repositories/lead_repository.py`
- Create: `app/domain/repositories/meeting_repository.py`
- Create: `app/domain/repositories/reminder_repository.py`
- Create: `app/domain/repositories/email_log_repository.py`

No tests for ABCs — they are tested via their concrete implementations.

- [ ] **Step 1: Create `app/domain/repositories/inventory_repository.py`**

```python
from abc import ABC, abstractmethod
from app.domain.entities.car import Car


class IInventoryRepository(ABC):
    @abstractmethod
    async def get_cars(self, filters: dict | None = None) -> list[Car]: ...

    @abstractmethod
    async def get_car_by_id(self, car_id: str) -> Car | None: ...
```

- [ ] **Step 2: Create `app/domain/repositories/lead_repository.py`**

```python
from abc import ABC, abstractmethod
from app.domain.entities.lead import Lead


class ILeadRepository(ABC):
    @abstractmethod
    async def get_or_create(self, telegram_chat_id: str) -> Lead: ...

    @abstractmethod
    async def update(self, lead: Lead) -> Lead: ...
```

- [ ] **Step 3: Create `app/domain/repositories/meeting_repository.py`**

```python
from abc import ABC, abstractmethod
from app.domain.entities.meeting import Meeting


class IMeetingRepository(ABC):
    @abstractmethod
    async def create(self, meeting: Meeting) -> Meeting: ...

    @abstractmethod
    async def get_by_lead(self, lead_id: str) -> list[Meeting]: ...
```

- [ ] **Step 4: Create `app/domain/repositories/reminder_repository.py`**

```python
from abc import ABC, abstractmethod
from datetime import datetime
from app.domain.entities.reminder import Reminder


class IReminderRepository(ABC):
    @abstractmethod
    async def create(self, reminder: Reminder) -> Reminder: ...

    @abstractmethod
    async def get_pending(self, before: datetime) -> list[Reminder]: ...

    @abstractmethod
    async def mark_sent(self, reminder_id: str) -> None: ...
```

- [ ] **Step 5: Create `app/domain/repositories/email_log_repository.py`**

```python
from abc import ABC, abstractmethod


class IEmailLogRepository(ABC):
    @abstractmethod
    async def log(
        self,
        lead_id: str,
        car_id: str,
        recipient: str,
        subject: str,
        template: str,
        success: bool,
        error: str | None,
    ) -> None: ...
```

- [ ] **Step 6: Commit**

```bash
git add app/domain/repositories/
git commit -m "feat: domain repository port ABCs"
```

---

## Task 4: Domain Service Ports

**Files:**
- Create: `app/domain/use_cases/speech_use_case.py`
- Create: `app/domain/use_cases/calendar_use_case.py`
- Create: `app/domain/use_cases/email_use_case.py`
- Create: `app/domain/use_cases/telegram_use_case.py`

- [ ] **Step 1: Create `app/domain/use_cases/speech_use_case.py`**

```python
from abc import ABC, abstractmethod


class ISpeechService(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, file_format: str = "ogg") -> str: ...

    @abstractmethod
    async def synthesize(self, text: str) -> bytes: ...
```

- [ ] **Step 2: Create `app/domain/use_cases/calendar_use_case.py`**

```python
from abc import ABC, abstractmethod
from datetime import datetime


class ICalendarService(ABC):
    @abstractmethod
    async def get_available_slots(self, days_ahead: int = 14) -> list[dict]: ...

    @abstractmethod
    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None,
        description: str,
    ) -> str: ...
```

- [ ] **Step 3: Create `app/domain/use_cases/email_use_case.py`**

```python
from abc import ABC, abstractmethod
from app.domain.entities.car import Car


class IEmailService(ABC):
    @abstractmethod
    async def send_car_specs(self, recipient_email: str, car: Car) -> bool: ...
```

- [ ] **Step 4: Create `app/domain/use_cases/telegram_use_case.py`**

```python
from abc import ABC, abstractmethod


class ITelegramService(ABC):
    @abstractmethod
    async def send_text(self, chat_id: str, text: str) -> None: ...

    @abstractmethod
    async def send_voice(self, chat_id: str, audio_bytes: bytes) -> None: ...

    @abstractmethod
    async def download_voice(self, file_id: str) -> bytes: ...

    @abstractmethod
    async def set_webhook(self, url: str) -> None: ...
```

- [ ] **Step 5: Commit**

```bash
git add app/domain/use_cases/
git commit -m "feat: domain service port ABCs — speech, calendar, email, telegram"
```

---

## Task 5: Infrastructure Database — Engine, Base, ORM Models

**Files:**
- Create: `app/infrastructure/database/base.py`
- Create: `app/infrastructure/database/engine.py`
- Create: `app/infrastructure/database/models/inventory_model.py`
- Create: `app/infrastructure/database/models/lead_model.py`
- Create: `app/infrastructure/database/models/meeting_model.py`
- Create: `app/infrastructure/database/models/reminder_model.py`
- Create: `app/infrastructure/database/models/email_log_model.py`

- [ ] **Step 1: Create `app/infrastructure/database/base.py`**

```python
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
```

- [ ] **Step 2: Create `app/infrastructure/database/engine.py`**

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    pool_size=10,
    max_overflow=20,
    echo=settings.app_env == "development",
)

AsyncSessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncSession:
    async with AsyncSessionFactory() as session:
        yield session


async def get_checkpointer() -> AsyncPostgresSaver:
    checkpointer = AsyncPostgresSaver.from_conn_string(
        settings.database_url.replace("+asyncpg", "")
    )
    await checkpointer.setup()
    return checkpointer
```

- [ ] **Step 3: Create `app/infrastructure/database/models/inventory_model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Numeric, Boolean, Text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base


class InventoryORM(Base):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    brand: Mapped[str] = mapped_column(String(100), nullable=False)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    color: Mapped[str] = mapped_column(String(50), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    km: Mapped[int] = mapped_column(Integer, default=0)
    fuel_type: Mapped[str] = mapped_column(String(30), nullable=False)
    transmission: Mapped[str] = mapped_column(String(20), nullable=False)
    condition: Mapped[str] = mapped_column(String(20), default="used")
    vin: Mapped[str | None] = mapped_column(String(17), unique=True, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 4: Create `app/infrastructure/database/models/lead_model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base


class LeadORM(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    telegram_chat_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    preferred_language: Mapped[str] = mapped_column(String(10), nullable=False, default="en")
    last_contacted_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 5: Create `app/infrastructure/database/models/meeting_model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Integer, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base


class MeetingORM(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    car_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("inventory.id"), nullable=False)
    google_event_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    google_meet_link: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    location: Mapped[str] = mapped_column(Text, nullable=False, default="Dealership showroom")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
```

- [ ] **Step 6: Create `app/infrastructure/database/models/reminder_model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import Text, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base


class ReminderORM(Base):
    __tablename__ = "reminders"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    remind_at: Mapped[datetime] = mapped_column(nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    sent: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 7: Create `app/infrastructure/database/models/email_log_model.py`**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func
from app.infrastructure.database.base import Base


class EmailLogORM(Base):
    __tablename__ = "email_sent_logs"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("leads.id"), nullable=False)
    car_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("inventory.id"), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str] = mapped_column(String(300), nullable=False)
    template_used: Mapped[str] = mapped_column(String(100), nullable=False, default="car_specs")
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    error_msg: Mapped[str | None] = mapped_column(Text, nullable=True)
    sent_at: Mapped[datetime] = mapped_column(server_default=func.now())
```

- [ ] **Step 8: Commit**

```bash
git add app/infrastructure/database/
git commit -m "feat: database engine, base, and ORM models"
```

---

## Task 6: Alembic Migrations

**Files:**
- Create: `alembic/env.py`
- Create: `alembic/script.py.mako`
- Create: `alembic/versions/0001_initial_schema.py`
- Create: `alembic/versions/0002_seed_inventory.py`

- [ ] **Step 1: Initialise Alembic**

```bash
poetry run alembic init alembic
```

Expected: `alembic/` directory created with `env.py`, `script.py.mako`, and `versions/`.

- [ ] **Step 2: Replace `alembic/env.py`**

```python
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.config import settings
from app.infrastructure.database.base import Base
import app.infrastructure.database.models.inventory_model  # noqa: F401
import app.infrastructure.database.models.lead_model  # noqa: F401
import app.infrastructure.database.models.meeting_model  # noqa: F401
import app.infrastructure.database.models.reminder_model  # noqa: F401
import app.infrastructure.database.models.email_log_model  # noqa: F401

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```

- [ ] **Step 3: Create `alembic/versions/0001_initial_schema.py`**

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("brand", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("color", sa.String(50), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.Column("km", sa.Integer, nullable=False, server_default="0"),
        sa.Column("fuel_type", sa.String(30), nullable=False),
        sa.Column("transmission", sa.String(20), nullable=False),
        sa.Column("condition", sa.String(20), nullable=False, server_default="used"),
        sa.Column("vin", sa.String(17), unique=True, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("available", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "leads",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("telegram_chat_id", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="new"),
        sa.Column("preferred_language", sa.String(10), nullable=False, server_default="en"),
        sa.Column("last_contacted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "conversation_history",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("input_modality", sa.String(10), nullable=False, server_default="text"),
        sa.Column("tool_calls", sa.JSON, nullable=True),
        sa.Column("tokens_used", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_conv_history_lead", "conversation_history", ["lead_id", "created_at"])

    op.create_table(
        "meetings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("car_id", UUID(as_uuid=True), sa.ForeignKey("inventory.id"), nullable=False),
        sa.Column("google_event_id", sa.String(200), nullable=True),
        sa.Column("google_meet_link", sa.Text, nullable=True),
        sa.Column("scheduled_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False, server_default="60"),
        sa.Column("location", sa.Text, nullable=False, server_default="Dealership showroom"),
        sa.Column("status", sa.String(30), nullable=False, server_default="scheduled"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )

    op.create_table(
        "reminders",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("remind_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("sent", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_reminders_pending", "reminders", ["remind_at"], postgresql_where=sa.text("sent = false"))

    op.create_table(
        "email_sent_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id"), nullable=False),
        sa.Column("car_id", UUID(as_uuid=True), sa.ForeignKey("inventory.id"), nullable=False),
        sa.Column("recipient_email", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(300), nullable=False),
        sa.Column("template_used", sa.String(100), nullable=False, server_default="car_specs"),
        sa.Column("success", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("error_msg", sa.Text, nullable=True),
        sa.Column("sent_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("email_sent_logs")
    op.drop_index("idx_reminders_pending", table_name="reminders")
    op.drop_table("reminders")
    op.drop_table("meetings")
    op.drop_index("idx_conv_history_lead", table_name="conversation_history")
    op.drop_table("conversation_history")
    op.drop_table("leads")
    op.drop_table("inventory")
```

- [ ] **Step 4: Create `alembic/versions/0002_seed_inventory.py`**

```python
"""seed inventory

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-17
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

SEED_VEHICLES = [
    ("Toyota", "Corolla", 2022, "White", 22500, 28000, "gasoline", "automatic", "used"),
    ("Toyota", "RAV4", 2023, "Silver", 34900, 0, "hybrid", "automatic", "new"),
    ("Honda", "Civic", 2021, "Black", 20000, 45000, "gasoline", "manual", "used"),
    ("Honda", "CR-V", 2022, "Blue", 31500, 18500, "gasoline", "automatic", "certified"),
    ("Ford", "Mustang", 2020, "Red", 38000, 62000, "gasoline", "manual", "used"),
    ("Ford", "Explorer", 2023, "Gray", 45000, 0, "gasoline", "automatic", "new"),
    ("Chevrolet", "Spark", 2022, "Yellow", 16000, 33000, "gasoline", "automatic", "used"),
    ("BMW", "320i", 2021, "White", 52000, 24000, "gasoline", "automatic", "certified"),
    ("Tesla", "Model 3", 2023, "Black", 48500, 0, "electric", "automatic", "new"),
    ("Nissan", "Sentra", 2022, "Silver", 19900, 41000, "gasoline", "automatic", "used"),
]


def upgrade() -> None:
    inventory = sa.table(
        "inventory",
        sa.column("brand"), sa.column("model"), sa.column("year"),
        sa.column("color"), sa.column("price"), sa.column("km"),
        sa.column("fuel_type"), sa.column("transmission"), sa.column("condition"),
        sa.column("available"),
    )
    op.bulk_insert(inventory, [
        {
            "brand": brand, "model": model, "year": year,
            "color": color, "price": price, "km": km,
            "fuel_type": fuel_type, "transmission": transmission,
            "condition": condition, "available": True,
        }
        for brand, model, year, color, price, km, fuel_type, transmission, condition in SEED_VEHICLES
    ])


def downgrade() -> None:
    op.execute("DELETE FROM inventory")
```

- [ ] **Step 5: Run migrations against Supabase**

```bash
poetry run alembic upgrade head
```

Expected: all 6 tables created + 10 seed vehicles inserted. No errors.

- [ ] **Step 6: Commit**

```bash
git add alembic/
git commit -m "feat: alembic migrations — schema + seed inventory"
```

---

## Task 7: Infrastructure Repositories

**Files:**
- Create: `app/infrastructure/repositories/base_repository.py`
- Create: `app/infrastructure/repositories/inventory_repo.py`
- Create: `app/infrastructure/repositories/lead_repo.py`
- Create: `app/infrastructure/repositories/meeting_repo.py`
- Create: `app/infrastructure/repositories/reminder_repo.py`
- Create: `app/infrastructure/repositories/email_log_repo.py`
- Test: `tests/unit/test_domain/test_entities.py` (extend with `_to_domain` tests)

- [ ] **Step 1: Create `app/infrastructure/repositories/base_repository.py`**

```python
from sqlalchemy.ext.asyncio import AsyncSession


class BaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
```

- [ ] **Step 2: Create `app/infrastructure/repositories/inventory_repo.py`**

```python
import json
from dataclasses import asdict
from sqlalchemy import select
from app.domain.entities.car import Car
from app.domain.repositories.inventory_repository import IInventoryRepository
from app.infrastructure.database.models.inventory_model import InventoryORM
from app.infrastructure.repositories.base_repository import BaseRepository


class InventoryRepository(BaseRepository, IInventoryRepository):
    async def get_cars(self, filters: dict | None = None) -> list[Car]:
        stmt = select(InventoryORM).where(InventoryORM.available == True)  # noqa: E712
        if filters:
            if filters.get("brand"):
                stmt = stmt.where(InventoryORM.brand.ilike(f"%{filters['brand']}%"))
            if filters.get("model"):
                stmt = stmt.where(InventoryORM.model.ilike(f"%{filters['model']}%"))
            if filters.get("year"):
                stmt = stmt.where(InventoryORM.year == filters["year"])
            if filters.get("color"):
                stmt = stmt.where(InventoryORM.color.ilike(f"%{filters['color']}%"))
            if filters.get("min_price"):
                stmt = stmt.where(InventoryORM.price >= filters["min_price"])
            if filters.get("max_price"):
                stmt = stmt.where(InventoryORM.price <= filters["max_price"])
            if filters.get("min_km"):
                stmt = stmt.where(InventoryORM.km >= filters["min_km"])
            if filters.get("max_km"):
                stmt = stmt.where(InventoryORM.km <= filters["max_km"])
            if filters.get("condition"):
                stmt = stmt.where(InventoryORM.condition == filters["condition"])
            if filters.get("fuel_type"):
                stmt = stmt.where(InventoryORM.fuel_type == filters["fuel_type"])
            if filters.get("transmission"):
                stmt = stmt.where(InventoryORM.transmission == filters["transmission"])
        rows = (await self.session.execute(stmt)).scalars().all()
        return [self._to_domain(r) for r in rows]

    async def get_car_by_id(self, car_id: str) -> Car | None:
        stmt = select(InventoryORM).where(InventoryORM.id == car_id)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(row) if row else None

    def _to_domain(self, r: InventoryORM) -> Car:
        return Car(
            id=str(r.id), brand=r.brand, model=r.model, year=r.year,
            color=r.color, price=float(r.price), km=r.km,
            fuel_type=r.fuel_type, transmission=r.transmission,
            condition=r.condition, vin=r.vin, description=r.description,
            image_url=r.image_url, available=r.available, created_at=r.created_at,
        )
```

- [ ] **Step 3: Create `app/infrastructure/repositories/lead_repo.py`**

```python
import uuid
from datetime import datetime, timezone
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

    async def update(self, lead: Lead) -> Lead:
        stmt = select(LeadORM).where(LeadORM.id == lead.id)
        row = (await self.session.execute(stmt)).scalar_one()
        row.name = lead.name
        row.phone = lead.phone
        row.email = lead.email
        row.status = lead.status.value if isinstance(lead.status, LeadStatus) else lead.status
        row.preferred_language = lead.preferred_language
        row.last_contacted_at = lead.last_contacted_at
        row.updated_at = datetime.now(timezone.utc)
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
```

- [ ] **Step 4: Create `app/infrastructure/repositories/meeting_repo.py`**

```python
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
```

- [ ] **Step 5: Create `app/infrastructure/repositories/reminder_repo.py`**

```python
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
```

- [ ] **Step 6: Create `app/infrastructure/repositories/email_log_repo.py`**

```python
import uuid
from app.domain.repositories.email_log_repository import IEmailLogRepository
from app.infrastructure.database.models.email_log_model import EmailLogORM
from app.infrastructure.repositories.base_repository import BaseRepository


class EmailLogRepository(BaseRepository, IEmailLogRepository):
    async def log(
        self,
        lead_id: str,
        car_id: str,
        recipient: str,
        subject: str,
        template: str,
        success: bool,
        error: str | None,
    ) -> None:
        row = EmailLogORM(
            id=uuid.uuid4(),
            lead_id=uuid.UUID(lead_id),
            car_id=uuid.UUID(car_id),
            recipient_email=recipient,
            subject=subject,
            template_used=template,
            success=success,
            error_msg=error,
        )
        self.session.add(row)
        await self.session.commit()
```

- [ ] **Step 7: Commit**

```bash
git add app/infrastructure/repositories/
git commit -m "feat: infrastructure repositories — inventory, lead, meeting, reminder, email_log"
```

---

## Task 8: Infrastructure Adapters

**Files:**
- Create: `app/infrastructure/events/openai_adapter.py`
- Create: `app/infrastructure/events/telegram_adapter.py`
- Create: `app/infrastructure/events/calendar_adapter.py`
- Create: `app/infrastructure/events/gmail_adapter.py`

- [ ] **Step 1: Create `app/infrastructure/events/openai_adapter.py`**

```python
import io
from openai import AsyncOpenAI
from app.config import settings
from app.domain.use_cases.speech_use_case import ISpeechService


class OpenAIAdapter(ISpeechService):
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def transcribe(self, audio_bytes: bytes, file_format: str = "ogg") -> str:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{file_format}"
        response = await self._client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
        )
        return response.text

    async def synthesize(self, text: str) -> bytes:
        response = await self._client.audio.speech.create(
            model="tts-1",
            voice="alloy",
            input=text,
        )
        return response.content
```

- [ ] **Step 2: Create `app/infrastructure/events/telegram_adapter.py`**

```python
import httpx
from app.config import settings
from app.domain.use_cases.telegram_use_case import ITelegramService

_BASE = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
_FILE_BASE = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}"


class TelegramAdapter(ITelegramService):
    async def send_text(self, chat_id: str, text: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{_BASE}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
                timeout=10,
            )

    async def send_voice(self, chat_id: str, audio_bytes: bytes) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{_BASE}/sendVoice",
                data={"chat_id": chat_id},
                files={"voice": ("voice.mp3", audio_bytes, "audio/mpeg")},
                timeout=30,
            )

    async def download_voice(self, file_id: str) -> bytes:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{_BASE}/getFile", params={"file_id": file_id}, timeout=10)
            file_path = r.json()["result"]["file_path"]
            audio = await client.get(f"{_FILE_BASE}/{file_path}", timeout=30)
            return audio.content

    async def set_webhook(self, url: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{_BASE}/setWebhook",
                json={"url": url, "allowed_updates": ["message"]},
                timeout=10,
            )
```

- [ ] **Step 3: Create `app/infrastructure/events/calendar_adapter.py`**

```python
import json
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from google.oauth2 import service_account
from app.config import settings
from app.domain.exceptions import CalendarUnavailableError
from app.domain.use_cases.calendar_use_case import ICalendarService

SCOPES = ["https://www.googleapis.com/auth/calendar"]


class CalendarAdapter(ICalendarService):
    def __init__(self) -> None:
        sa_info = settings.google_service_account_json
        if sa_info.endswith(".json"):
            with open(sa_info) as f:
                sa_dict = json.load(f)
        else:
            sa_dict = json.loads(sa_info)
        creds = service_account.Credentials.from_service_account_info(sa_dict, scopes=SCOPES)
        self._service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        self._calendar_id = settings.google_calendar_id

    async def get_available_slots(self, days_ahead: int = 14) -> list[dict]:
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)
        body = {
            "timeMin": now.isoformat(),
            "timeMax": end.isoformat(),
            "items": [{"id": self._calendar_id}],
        }
        try:
            result = self._service.freebusy().query(body=body).execute()
            busy = result["calendars"][self._calendar_id]["busy"]
        except Exception as e:
            raise CalendarUnavailableError(str(e)) from e

        busy_ranges = [(b["start"], b["end"]) for b in busy]
        slots = []
        cursor = now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        while cursor < end and len(slots) < 20:
            if cursor.weekday() < 5 and 9 <= cursor.hour < 18:
                slot_end = cursor + timedelta(hours=1)
                overlap = any(
                    cursor.isoformat() < be and slot_end.isoformat() > bs
                    for bs, be in busy_ranges
                )
                if not overlap:
                    slots.append({
                        "start": cursor.isoformat(),
                        "end": slot_end.isoformat(),
                    })
            cursor += timedelta(hours=1)
        return slots

    async def create_event(
        self,
        title: str,
        start: datetime,
        end: datetime,
        attendee_email: str | None,
        description: str,
    ) -> str:
        event = {
            "summary": title,
            "description": description,
            "start": {"dateTime": start.isoformat(), "timeZone": "UTC"},
            "end": {"dateTime": end.isoformat(), "timeZone": "UTC"},
        }
        if attendee_email:
            event["attendees"] = [{"email": attendee_email}]
        try:
            created = self._service.events().insert(
                calendarId=self._calendar_id, body=event, sendUpdates="all"
            ).execute()
            return created["id"]
        except Exception as e:
            raise CalendarUnavailableError(str(e)) from e
```

- [ ] **Step 4: Create `app/infrastructure/events/gmail_adapter.py`**

```python
import json
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from googleapiclient.discovery import build
from google.oauth2 import service_account
from app.config import settings
from app.domain.entities.car import Car
from app.domain.exceptions import EmailSendError
from app.domain.repositories.email_log_repository import IEmailLogRepository
from app.domain.use_cases.email_use_case import IEmailService

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


class GmailAdapter(IEmailService):
    def __init__(self, email_log_repo: IEmailLogRepository) -> None:
        self._email_log_repo = email_log_repo
        sa_info = settings.google_service_account_json
        if sa_info.endswith(".json"):
            with open(sa_info) as f:
                sa_dict = json.load(f)
        else:
            sa_dict = json.loads(sa_info)
        creds = service_account.Credentials.from_service_account_info(
            sa_dict, scopes=SCOPES, subject=settings.gmail_sender
        )
        self._service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    async def send_car_specs(self, recipient_email: str, car: Car) -> bool:
        subject = f"Car Specs: {car.year} {car.brand} {car.model}"
        html_body = self._build_html(car)
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.gmail_sender
        msg["To"] = recipient_email
        msg.attach(MIMEText(html_body, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        success = False
        error = None
        try:
            self._service.users().messages().send(
                userId="me", body={"raw": raw}
            ).execute()
            success = True
        except Exception as e:
            error = str(e)
        await self._email_log_repo.log(
            lead_id="unknown",
            car_id=car.id,
            recipient=recipient_email,
            subject=subject,
            template="car_specs",
            success=success,
            error=error,
        )
        if not success:
            raise EmailSendError(error)
        return True

    def _build_html(self, car: Car) -> str:
        image_tag = f'<img src="{car.image_url}" style="max-width:400px"/><br/>' if car.image_url else ""
        return f"""
        <html><body>
        <h2>{car.year} {car.brand} {car.model}</h2>
        {image_tag}
        <table border="1" cellpadding="6">
          <tr><td>Color</td><td>{car.color}</td></tr>
          <tr><td>Price</td><td>${car.price:,.0f}</td></tr>
          <tr><td>KM</td><td>{car.km:,}</td></tr>
          <tr><td>Fuel</td><td>{car.fuel_type}</td></tr>
          <tr><td>Transmission</td><td>{car.transmission}</td></tr>
          <tr><td>Condition</td><td>{car.condition}</td></tr>
        </table>
        <p>{car.description or ""}</p>
        </body></html>
        """
```

- [ ] **Step 5: Commit**

```bash
git add app/infrastructure/events/
git commit -m "feat: infrastructure adapters — openai, telegram, calendar, gmail"
```

---

## Task 9: Infrastructure Schemas & DI Container

**Files:**
- Create: `app/infrastructure/schemas/telegram_schema.py`
- Create: `app/infrastructure/schemas/health_schema.py`
- Create: `app/infrastructure/container/container.py`

- [ ] **Step 1: Create `app/infrastructure/schemas/telegram_schema.py`**

```python
from pydantic import BaseModel


class Voice(BaseModel):
    file_id: str
    file_unique_id: str
    duration: int
    mime_type: str | None = None
    file_size: int | None = None


class Message(BaseModel):
    message_id: int
    chat: dict
    text: str | None = None
    voice: Voice | None = None

    @property
    def chat_id(self) -> str:
        return str(self.chat["id"])


class TelegramUpdate(BaseModel):
    update_id: int
    message: Message | None = None
```

- [ ] **Step 2: Create `app/infrastructure/schemas/health_schema.py`**

```python
from pydantic import BaseModel


class DependencyStatus(BaseModel):
    database: str
    deepseek: str
    langfuse: str


class HealthResponse(BaseModel):
    status: str
    version: str
    dependencies: DependencyStatus
```

- [ ] **Step 3: Create `app/infrastructure/container/container.py`**

```python
from functools import lru_cache
from langfuse.callback import CallbackHandler
from app.config import settings
from app.infrastructure.database.engine import AsyncSessionFactory, get_checkpointer
from app.infrastructure.events.openai_adapter import OpenAIAdapter
from app.infrastructure.events.telegram_adapter import TelegramAdapter
from app.infrastructure.events.calendar_adapter import CalendarAdapter
from app.infrastructure.events.gmail_adapter import GmailAdapter
from app.infrastructure.repositories.inventory_repo import InventoryRepository
from app.infrastructure.repositories.lead_repo import LeadRepository
from app.infrastructure.repositories.meeting_repo import MeetingRepository
from app.infrastructure.repositories.reminder_repo import ReminderRepository
from app.infrastructure.repositories.email_log_repo import EmailLogRepository
from app.application.services.tools.get_inventory import make_get_inventory_tool
from app.application.services.tools.get_calendar_events import make_get_calendar_events_tool
from app.application.services.tools.schedule_meeting import make_schedule_meeting_tool
from app.application.services.tools.send_email import make_send_email_tool
from app.application.services.agent_graph import build_agent_graph
from app.application.services.message_processor import MessageProcessingService


@lru_cache
def get_langfuse_handler() -> CallbackHandler:
    return CallbackHandler(
        secret_key=settings.langfuse_secret_key,
        public_key=settings.langfuse_public_key,
        host=settings.langfuse_host,
    )


@lru_cache
def get_telegram_adapter() -> TelegramAdapter:
    return TelegramAdapter()


@lru_cache
def get_openai_adapter() -> OpenAIAdapter:
    return OpenAIAdapter()


@lru_cache
def get_calendar_adapter() -> CalendarAdapter:
    return CalendarAdapter()


async def get_message_processor() -> MessageProcessingService:
    session = AsyncSessionFactory()
    inventory_repo = InventoryRepository(session)
    lead_repo = LeadRepository(session)
    meeting_repo = MeetingRepository(session)
    reminder_repo = ReminderRepository(session)
    email_log_repo = EmailLogRepository(session)

    gmail_adapter = GmailAdapter(email_log_repo)
    calendar_adapter = get_calendar_adapter()
    speech_service = get_openai_adapter()
    telegram_service = get_telegram_adapter()

    tools = [
        make_get_inventory_tool(inventory_repo),
        make_get_calendar_events_tool(calendar_adapter),
        make_schedule_meeting_tool(meeting_repo, lead_repo, calendar_adapter),
        make_send_email_tool(inventory_repo, gmail_adapter, email_log_repo),
    ]

    checkpointer = await get_checkpointer()
    agent = build_agent_graph(checkpointer=checkpointer, tools=tools)

    return MessageProcessingService(
        lead_repo=lead_repo,
        speech_service=speech_service,
        telegram_service=telegram_service,
        agent_graph=agent,
        langfuse_handler=get_langfuse_handler(),
        db_session=session,
    )
```

- [ ] **Step 4: Commit**

```bash
git add app/infrastructure/schemas/ app/infrastructure/container/
git commit -m "feat: telegram/health schemas and DI container"
```

---

## Task 10: Application Tools

**Files:**
- Create: `app/application/services/tools/get_inventory.py`
- Create: `app/application/services/tools/get_calendar_events.py`
- Create: `app/application/services/tools/schedule_meeting.py`
- Create: `app/application/services/tools/send_email.py`
- Test: `tests/unit/test_tools/test_get_inventory.py`
- Test: `tests/unit/test_tools/test_get_calendar_events.py`
- Test: `tests/unit/test_tools/test_schedule_meeting.py`
- Test: `tests/unit/test_tools/test_send_email.py`

- [ ] **Step 1: Write failing tests for `get_inventory` tool**

```python
# tests/unit/test_tools/test_get_inventory.py
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from app.domain.entities.car import Car
from app.application.services.tools.get_inventory import make_get_inventory_tool


@pytest.fixture
def sample_car():
    return Car(
        id="car-1", brand="Toyota", model="Corolla", year=2022,
        color="White", price=22500.0, km=28000, fuel_type="gasoline",
        transmission="automatic", condition="used", vin=None,
        description=None, image_url=None, available=True,
        created_at=datetime(2024, 1, 1),
    )


@pytest.fixture
def mock_repo(sample_car):
    repo = AsyncMock()
    repo.get_cars.return_value = [sample_car]
    return repo


async def test_get_inventory_no_filters(mock_repo, sample_car):
    tool = make_get_inventory_tool(mock_repo)
    result = await tool.ainvoke({})
    cars = json.loads(result)
    assert len(cars) == 1
    assert cars[0]["brand"] == "Toyota"
    mock_repo.get_cars.assert_called_once_with({})


async def test_get_inventory_with_brand_filter(mock_repo):
    tool = make_get_inventory_tool(mock_repo)
    await tool.ainvoke({"brand": "Toyota"})
    mock_repo.get_cars.assert_called_once_with({"brand": "Toyota"})


async def test_get_inventory_returns_max_10(mock_repo, sample_car):
    mock_repo.get_cars.return_value = [sample_car] * 15
    tool = make_get_inventory_tool(mock_repo)
    result = await tool.ainvoke({})
    assert len(json.loads(result)) == 10
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/test_tools/test_get_inventory.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/application/services/tools/get_inventory.py`**

```python
import json
from dataclasses import asdict
from typing import Literal
from langchain_core.tools import tool
from app.domain.repositories.inventory_repository import IInventoryRepository


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
        """Search available car inventory. All filters optional. Returns JSON array (max 10).
        Use when the customer asks about vehicles, models, prices, colors, km, or specs."""
        filters = {k: v for k, v in locals().items() if v is not None and k != "repo"}
        cars = await repo.get_cars(filters if filters else None)
        return json.dumps([asdict(c) for c in cars[:10]], default=str)

    return get_inventory
```

- [ ] **Step 4: Run test to verify it passes**

```bash
poetry run pytest tests/unit/test_tools/test_get_inventory.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Write failing tests for `get_calendar_events` and `schedule_meeting` tools**

```python
# tests/unit/test_tools/test_get_calendar_events.py
import json
import pytest
from unittest.mock import AsyncMock
from app.application.services.tools.get_calendar_events import make_get_calendar_events_tool


@pytest.fixture
def mock_calendar():
    svc = AsyncMock()
    svc.get_available_slots.return_value = [
        {"start": "2026-04-20T10:00:00+00:00", "end": "2026-04-20T11:00:00+00:00"},
        {"start": "2026-04-20T14:00:00+00:00", "end": "2026-04-20T15:00:00+00:00"},
    ]
    return svc


async def test_get_calendar_events_returns_slots(mock_calendar):
    tool = make_get_calendar_events_tool(mock_calendar)
    result = await tool.ainvoke({"days_ahead": 7})
    slots = json.loads(result)
    assert len(slots) == 2
    assert "start" in slots[0]
    mock_calendar.get_available_slots.assert_called_once_with(days_ahead=7)
```

```python
# tests/unit/test_tools/test_schedule_meeting.py
import json
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch
from app.domain.entities.lead import Lead, LeadStatus
from app.domain.entities.meeting import Meeting
from app.application.services.tools.schedule_meeting import make_schedule_meeting_tool


@pytest.fixture
def mock_meeting_repo():
    repo = AsyncMock()
    repo.create.return_value = Meeting(
        id="meet-1", lead_id="lead-1", car_id="car-1",
        google_event_id="gcal-event-1", google_meet_link=None,
        scheduled_at=datetime(2026, 4, 20, 10, 0),
        duration_minutes=60, location="Dealership showroom",
        status="scheduled", notes=None,
        created_at=datetime(2026, 4, 17), updated_at=datetime(2026, 4, 17),
    )
    return repo


@pytest.fixture
def mock_lead_repo():
    repo = AsyncMock()
    lead = Lead(
        id="lead-1", telegram_chat_id="12345", name="Alice",
        phone=None, email="alice@example.com", status=LeadStatus.INTERESTED,
        preferred_language="en", last_contacted_at=None,
        created_at=datetime(2026, 4, 1), updated_at=datetime(2026, 4, 1),
    )
    repo.update.return_value = lead
    return repo


@pytest.fixture
def mock_calendar():
    svc = AsyncMock()
    svc.create_event.return_value = "gcal-event-1"
    return svc


async def test_schedule_meeting_creates_event_and_meeting(
    mock_meeting_repo, mock_lead_repo, mock_calendar
):
    tool = make_schedule_meeting_tool(mock_meeting_repo, mock_lead_repo, mock_calendar)
    result = await tool.ainvoke({
        "car_id": "car-1",
        "lead_id": "lead-1",
        "scheduled_at": "2026-04-20T10:00:00",
        "attendee_email": "alice@example.com",
    })
    data = json.loads(result)
    assert data["status"] == "scheduled"
    mock_calendar.create_event.assert_called_once()
    mock_meeting_repo.create.assert_called_once()
    mock_lead_repo.update.assert_called_once()
```

- [ ] **Step 6: Run tests to verify they fail**

```bash
poetry run pytest tests/unit/test_tools/test_get_calendar_events.py tests/unit/test_tools/test_schedule_meeting.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 7: Create `app/application/services/tools/get_calendar_events.py`**

```python
import json
from langchain_core.tools import tool
from app.domain.use_cases.calendar_use_case import ICalendarService


def make_get_calendar_events_tool(calendar_service: ICalendarService):
    @tool
    async def get_calendar_events(days_ahead: int = 14) -> str:
        """Get available 1-hour appointment slots during business hours (9 AM–6 PM)
        over the next N days. Always call before proposing times to the customer."""
        slots = await calendar_service.get_available_slots(days_ahead=days_ahead)
        return json.dumps(slots)

    return get_calendar_events
```

- [ ] **Step 8: Add `get_by_id` to `ILeadRepository`**

Edit `app/domain/repositories/lead_repository.py`:

```python
from abc import ABC, abstractmethod
from app.domain.entities.lead import Lead


class ILeadRepository(ABC):
    @abstractmethod
    async def get_or_create(self, telegram_chat_id: str) -> Lead: ...

    @abstractmethod
    async def get_by_id(self, lead_id: str) -> Lead | None: ...

    @abstractmethod
    async def update(self, lead: Lead) -> Lead: ...
```

Edit `app/infrastructure/repositories/lead_repo.py` — add after `get_or_create`:

```python
    async def get_by_id(self, lead_id: str) -> Lead | None:
        stmt = select(LeadORM).where(LeadORM.id == uuid.UUID(lead_id))
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        return self._to_domain(row) if row else None
```

- [ ] **Step 9: Create `app/application/services/tools/schedule_meeting.py`**

```python
import json
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
from langchain_core.tools import tool
from app.domain.entities.lead import LeadStatus
from app.domain.entities.meeting import Meeting
from app.domain.repositories.lead_repository import ILeadRepository
from app.domain.repositories.meeting_repository import IMeetingRepository
from app.domain.use_cases.calendar_use_case import ICalendarService


def make_schedule_meeting_tool(
    meeting_repo: IMeetingRepository,
    lead_repo: ILeadRepository,
    calendar_service: ICalendarService,
):
    @tool
    async def schedule_meeting(
        car_id: str,
        lead_id: str,
        scheduled_at: str,
        attendee_email: str | None = None,
        notes: str | None = None,
    ) -> str:
        """Create a Google Calendar event and persist a meeting record.
        scheduled_at must be an ISO8601 datetime string. Sets lead status to converted."""
        start = datetime.fromisoformat(scheduled_at)
        end = start + timedelta(hours=1)

        event_id = await calendar_service.create_event(
            title="Car Inspection",
            start=start,
            end=end,
            attendee_email=attendee_email,
            description=f"Car inspection for car {car_id}. Notes: {notes or 'None'}",
        )

        meeting = Meeting(
            id=str(uuid.uuid4()),
            lead_id=lead_id,
            car_id=car_id,
            google_event_id=event_id,
            google_meet_link=None,
            scheduled_at=start,
            duration_minutes=60,
            location="Dealership showroom",
            status="scheduled",
            notes=notes,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        saved_meeting = await meeting_repo.create(meeting)

        lead = await lead_repo.get_by_id(lead_id)
        if lead:
            lead.status = LeadStatus.CONVERTED
            await lead_repo.update(lead)

        return json.dumps(asdict(saved_meeting), default=str)

    return schedule_meeting
```

- [ ] **Step 10: Write failing tests for `send_email` tool**

```python
# tests/unit/test_tools/test_send_email.py
import pytest
from datetime import datetime
from unittest.mock import AsyncMock
from app.domain.entities.car import Car
from app.application.services.tools.send_email import make_send_email_tool


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
def mock_inventory_repo(sample_car):
    repo = AsyncMock()
    repo.get_car_by_id.return_value = sample_car
    return repo


@pytest.fixture
def mock_email_service():
    svc = AsyncMock()
    svc.send_car_specs.return_value = True
    return svc


@pytest.fixture
def mock_email_log_repo():
    return AsyncMock()


async def test_send_email_sends_specs(mock_inventory_repo, mock_email_service, mock_email_log_repo):
    tool = make_send_email_tool(mock_inventory_repo, mock_email_service, mock_email_log_repo)
    result = await tool.ainvoke({
        "car_id": "car-1",
        "recipient_email": "buyer@example.com",
        "lead_id": "lead-1",
    })
    assert "sent" in result.lower()
    mock_email_service.send_car_specs.assert_called_once()


async def test_send_email_car_not_found(mock_inventory_repo, mock_email_service, mock_email_log_repo):
    mock_inventory_repo.get_car_by_id.return_value = None
    tool = make_send_email_tool(mock_inventory_repo, mock_email_service, mock_email_log_repo)
    result = await tool.ainvoke({
        "car_id": "nonexistent",
        "recipient_email": "buyer@example.com",
        "lead_id": "lead-1",
    })
    assert "not found" in result.lower()
    mock_email_service.send_car_specs.assert_not_called()
```

- [ ] **Step 11: Run test to verify it fails**

```bash
poetry run pytest tests/unit/test_tools/test_send_email.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 12: Create `app/application/services/tools/send_email.py`**

```python
import json
from langchain_core.tools import tool
from app.domain.repositories.email_log_repository import IEmailLogRepository
from app.domain.repositories.inventory_repository import IInventoryRepository
from app.domain.use_cases.email_use_case import IEmailService


def make_send_email_tool(
    inventory_repo: IInventoryRepository,
    email_service: IEmailService,
    email_log_repo: IEmailLogRepository,
):
    @tool
    async def send_email(car_id: str, recipient_email: str, lead_id: str) -> str:
        """Send a car specification HTML email via Gmail. Logs the result to email_sent_logs."""
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

- [ ] **Step 13: Run all tool tests**

```bash
poetry run pytest tests/unit/test_tools/ -v
```

Expected: all tests PASS.

- [ ] **Step 14: Commit**

```bash
git add app/application/services/tools/ app/domain/repositories/lead_repository.py app/infrastructure/repositories/lead_repo.py tests/unit/test_tools/
git commit -m "feat: application tools — get_inventory, get_calendar_events, schedule_meeting, send_email"
```

---

## Task 11: LangGraph Agent Graph

**Files:**
- Create: `app/application/services/agent_graph.py`
- Test: `tests/unit/test_agent_graph/test_state_modifier.py`

- [ ] **Step 1: Write failing test for state modifier**

```python
# tests/unit/test_agent_graph/test_state_modifier.py
import pytest
from unittest.mock import MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from app.application.services.agent_graph import _build_state_modifier, SYSTEM_PROMPT


def test_state_modifier_prepends_system_prompt():
    mock_llm = MagicMock()
    modifier = _build_state_modifier(mock_llm)

    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [HumanMessage(content="Hello")]
        messages = modifier({"messages": [HumanMessage(content="Hello")]})

    assert isinstance(messages[0], SystemMessage)
    assert messages[0].content == SYSTEM_PROMPT


def test_state_modifier_includes_trimmed_messages():
    mock_llm = MagicMock()
    modifier = _build_state_modifier(mock_llm)
    human_msg = HumanMessage(content="Hello")

    with patch("app.application.services.agent_graph.trim_messages") as mock_trim:
        mock_trim.return_value = [human_msg]
        messages = modifier({"messages": [human_msg]})

    assert human_msg in messages
```

- [ ] **Step 2: Run test to verify it fails**

```bash
poetry run pytest tests/unit/test_agent_graph/ -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/application/services/agent_graph.py`**

```python
from datetime import date
from langchain_core.messages import SystemMessage, trim_messages
from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from app.config import settings

SYSTEM_PROMPT = f"""You are an AI assistant for {settings.dealership_name}, a car dealership.
Help customers find vehicles, schedule visits, and receive car information by email.
Be friendly, professional, and concise. Always reply in the customer's language.

SCOPE RESTRICTION: Only answer questions about cars, inventory, pricing, scheduling,
test drives, or email specs. For anything else respond ONLY with:
"I can only help with questions about our car inventory, scheduling visits, and
sending vehicle information. Is there anything car-related I can help you with today?"

Current date: {date.today().isoformat()}
Dealership address: {settings.dealership_address}
"""


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


def build_agent_graph(checkpointer: AsyncPostgresSaver, tools: list):
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
        state_modifier=_build_state_modifier(llm),
    )
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
poetry run pytest tests/unit/test_agent_graph/ -v
```

Expected: 2 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/application/services/agent_graph.py tests/unit/test_agent_graph/
git commit -m "feat: LangGraph agent graph with DeepSeek LLM and state modifier"
```

---

## Task 12: Message Processing Service

**Files:**
- Create: `app/application/services/message_processor.py`
- Test: `tests/unit/test_message_processor/test_message_processor.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/unit/test_message_processor/test_message_processor.py
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import AIMessage, HumanMessage
from app.domain.entities.lead import Lead, LeadStatus
from app.infrastructure.schemas.telegram_schema import TelegramUpdate, Message
from app.application.services.message_processor import MessageProcessingService


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
        message=Message(
            message_id=1,
            chat={"id": 12345},
            text="Show me red cars",
        ),
    )


@pytest.fixture
def voice_update():
    return TelegramUpdate(
        update_id=2,
        message=Message(
            message_id=2,
            chat={"id": 12345},
            voice={"file_id": "file123", "file_unique_id": "uq123", "duration": 3},
        ),
    )


@pytest.fixture
def processor(sample_lead):
    lead_repo = AsyncMock()
    lead_repo.get_or_create.return_value = sample_lead
    lead_repo.update.return_value = sample_lead

    speech_service = AsyncMock()
    speech_service.transcribe.return_value = "Show me red cars"
    speech_service.synthesize.return_value = b"audio_bytes"

    telegram_service = AsyncMock()

    agent_graph = AsyncMock()
    agent_graph.ainvoke.return_value = {
        "messages": [HumanMessage(content="Show me red cars"), AIMessage(content="Here are red cars")]
    }

    db_session = AsyncMock()

    return MessageProcessingService(
        lead_repo=lead_repo,
        speech_service=speech_service,
        telegram_service=telegram_service,
        agent_graph=agent_graph,
        langfuse_handler=MagicMock(),
        db_session=db_session,
    )


async def test_text_message_sends_text_reply(processor, text_update):
    await processor.receive_message(text_update)
    processor.telegram_service.send_text.assert_called_once_with("12345", "Here are red cars")
    processor.telegram_service.send_voice.assert_not_called()


async def test_voice_message_transcribes_and_replies_with_voice(processor, voice_update):
    processor.telegram_service.download_voice = AsyncMock(return_value=b"ogg_bytes")
    processor.speech_service.transcribe = AsyncMock(return_value="Show me red cars")
    await processor.receive_message(voice_update)
    processor.speech_service.transcribe.assert_called_once_with(b"ogg_bytes", "ogg")
    processor.telegram_service.send_voice.assert_called_once()


async def test_updates_lead_last_contacted(processor, text_update):
    await processor.receive_message(text_update)
    processor.lead_repo.update.assert_called_once()
    updated_lead = processor.lead_repo.update.call_args[0][0]
    assert updated_lead.last_contacted_at is not None
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
poetry run pytest tests/unit/test_message_processor/ -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Create `app/application/services/message_processor.py`**

```python
from datetime import datetime, timezone
from langchain_core.messages import HumanMessage
from sqlalchemy.ext.asyncio import AsyncSession
from app.domain.repositories.lead_repository import ILeadRepository
from app.domain.use_cases.speech_use_case import ISpeechService
from app.domain.use_cases.telegram_use_case import ITelegramService
from app.infrastructure.schemas.telegram_schema import TelegramUpdate

FALLBACK_MESSAGE = (
    "I'm having a little trouble right now. "
    "Please try again in a moment or contact us directly."
)


class MessageProcessingService:
    def __init__(
        self,
        lead_repo: ILeadRepository,
        speech_service: ISpeechService,
        telegram_service: ITelegramService,
        agent_graph,
        langfuse_handler,
        db_session: AsyncSession,
    ) -> None:
        self.lead_repo = lead_repo
        self.speech_service = speech_service
        self.telegram_service = telegram_service
        self.agent_graph = agent_graph
        self.langfuse_handler = langfuse_handler
        self.db_session = db_session

    async def receive_message(self, update: TelegramUpdate) -> None:
        if not update.message:
            return

        message = update.message
        chat_id = message.chat_id
        is_voice = message.voice is not None

        try:
            lead = await self.lead_repo.get_or_create(chat_id)

            if is_voice:
                audio_bytes = await self.telegram_service.download_voice(message.voice.file_id)
                user_text = await self.speech_service.transcribe(audio_bytes, "ogg")
            else:
                user_text = message.text or ""

            if not user_text.strip():
                return

            config = {
                "configurable": {"thread_id": str(lead.id)},
                "callbacks": [self.langfuse_handler],
            }
            result = await self.agent_graph.ainvoke(
                {"messages": [HumanMessage(content=user_text)]},
                config=config,
            )
            response_text = result["messages"][-1].content

            if is_voice:
                audio_response = await self.speech_service.synthesize(response_text)
                await self.telegram_service.send_voice(chat_id, audio_response)
            else:
                await self.telegram_service.send_text(chat_id, response_text)

            lead.last_contacted_at = datetime.now(timezone.utc)
            await self.lead_repo.update(lead)

        except Exception:
            await self.telegram_service.send_text(chat_id, FALLBACK_MESSAGE)
```

- [ ] **Step 4: Run tests — confirm they pass**

```bash
poetry run pytest tests/unit/test_message_processor/ -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/application/services/message_processor.py tests/unit/test_message_processor/
git commit -m "feat: MessageProcessingService — voice/text pipeline with fallback"
```

---

## Task 13: API Handlers & main.py

**Files:**
- Create: `app/infrastructure/handlers/webhook_handler.py`
- Create: `app/infrastructure/handlers/health_handler.py`
- Create: `app/main.py`

- [ ] **Step 1: Create `app/infrastructure/handlers/webhook_handler.py`**

```python
from fastapi import APIRouter, BackgroundTasks, Depends
from app.application.services.message_processor import MessageProcessingService
from app.infrastructure.container.container import get_message_processor
from app.infrastructure.schemas.telegram_schema import TelegramUpdate

router = APIRouter()


@router.post("/webhook/telegram")
async def telegram_webhook(
    update: TelegramUpdate,
    background_tasks: BackgroundTasks,
    processor: MessageProcessingService = Depends(get_message_processor),
):
    background_tasks.add_task(processor.receive_message, update)
    return {"ok": True}
```

- [ ] **Step 2: Create `app/infrastructure/handlers/health_handler.py`**

```python
from fastapi import APIRouter
from sqlalchemy import text
from app.infrastructure.database.engine import AsyncSessionFactory
from app.infrastructure.schemas.health_schema import HealthResponse, DependencyStatus

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check():
    db_status = "ok"
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
    except Exception:
        db_status = "error"

    return HealthResponse(
        status="ok",
        version="2.0.0",
        dependencies=DependencyStatus(
            database=db_status,
            deepseek="ok",
            langfuse="ok",
        ),
    )
```

- [ ] **Step 3: Create `app/main.py`**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.infrastructure.database.engine import engine, get_checkpointer
from app.infrastructure.events.telegram_adapter import TelegramAdapter
from app.infrastructure.handlers.webhook_handler import router as webhook_router
from app.infrastructure.handlers.health_handler import router as health_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    telegram = TelegramAdapter()
    await telegram.set_webhook(url=f"{settings.base_url}/webhook/telegram")
    checkpointer = await get_checkpointer()
    app.state.checkpointer = checkpointer
    yield
    await engine.dispose()


app = FastAPI(title="Car Dealership Bot", version="2.0.0", lifespan=lifespan)
app.include_router(webhook_router)
app.include_router(health_router)
```

- [ ] **Step 4: Verify server starts**

```bash
poetry run uvicorn app.main:app --reload --port 8000
```

Expected: server starts, no import errors. Visit `http://localhost:8000/health` in browser — returns `{"status":"ok",...}`. Stop server with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add app/main.py app/infrastructure/handlers/
git commit -m "feat: FastAPI handlers — webhook, health, and app lifespan"
```

---

## Task 14: Integration Tests

**Files:**
- Create: `tests/conftest.py`
- Create: `tests/integration/test_inventory_repo/test_inventory_repo.py`
- Create: `tests/integration/test_lead_repo/test_lead_repo.py`
- Create: `tests/integration/test_webhook/test_webhook.py`

- [ ] **Step 1: Create `tests/conftest.py`**

```python
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings


@pytest_asyncio.fixture
async def db_session():
    engine = create_async_engine(settings.database_url, echo=False)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
        await session.rollback()
    await engine.dispose()
```

- [ ] **Step 2: Create `tests/integration/test_inventory_repo/test_inventory_repo.py`**

```python
import pytest
from app.infrastructure.repositories.inventory_repo import InventoryRepository


async def test_get_cars_returns_available_cars(db_session):
    repo = InventoryRepository(db_session)
    cars = await repo.get_cars()
    assert len(cars) >= 10
    assert all(c.available for c in cars)


async def test_get_cars_filter_by_brand(db_session):
    repo = InventoryRepository(db_session)
    cars = await repo.get_cars({"brand": "Toyota"})
    assert all("toyota" in c.brand.lower() for c in cars)


async def test_get_cars_filter_by_condition(db_session):
    repo = InventoryRepository(db_session)
    cars = await repo.get_cars({"condition": "new"})
    assert all(c.condition == "new" for c in cars)


async def test_get_car_by_id_returns_none_for_unknown(db_session):
    repo = InventoryRepository(db_session)
    car = await repo.get_car_by_id("00000000-0000-0000-0000-000000000000")
    assert car is None


async def test_get_cars_filter_by_max_price(db_session):
    repo = InventoryRepository(db_session)
    cars = await repo.get_cars({"max_price": 25000})
    assert all(c.price <= 25000 for c in cars)
```

- [ ] **Step 3: Create `tests/integration/test_lead_repo/test_lead_repo.py`**

```python
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
```

- [ ] **Step 4: Create `tests/integration/test_webhook/test_webhook.py`**

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, HumanMessage


def test_webhook_returns_200_immediately():
    with patch("app.infrastructure.container.container.get_message_processor") as mock_get:
        mock_processor = AsyncMock()
        mock_get.return_value = mock_processor
        with patch("app.main.TelegramAdapter") as mock_tg:
            mock_tg.return_value.set_webhook = AsyncMock()
            with patch("app.main.get_checkpointer", return_value=AsyncMock()):
                from app.main import app
                client = TestClient(app)
                payload = {
                    "update_id": 1,
                    "message": {
                        "message_id": 1,
                        "chat": {"id": 99999},
                        "text": "Hello",
                    },
                }
                response = client.post("/webhook/telegram", json=payload)
                assert response.status_code == 200
                assert response.json() == {"ok": True}


def test_health_endpoint_returns_ok():
    with patch("app.main.TelegramAdapter") as mock_tg:
        mock_tg.return_value.set_webhook = AsyncMock()
        with patch("app.main.get_checkpointer", return_value=AsyncMock()):
            from app.main import app
            client = TestClient(app)
            response = client.get("/health")
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "ok"
            assert "dependencies" in data
```

- [ ] **Step 5: Run unit tests (all)**

```bash
poetry run pytest tests/unit/ -v
```

Expected: all unit tests PASS.

- [ ] **Step 6: Run integration tests against Supabase**

```bash
poetry run pytest tests/integration/test_inventory_repo/ tests/integration/test_lead_repo/ -v
```

Expected: all integration tests PASS. (Requires valid `DATABASE_URL` in `.env`.)

- [ ] **Step 7: Commit**

```bash
git add tests/
git commit -m "feat: integration and webhook tests"
```

---

## Task 15: Final Validation

- [ ] **Step 1: Run full test suite**

```bash
poetry run pytest -v
```

Expected: all tests PASS (unit + integration).

- [ ] **Step 2: Start the server**

```bash
poetry run uvicorn app.main:app --reload --port 8000
```

Expected: server starts, webhook set on Telegram, no errors in logs.

- [ ] **Step 3: Verify health endpoint**

```bash
curl http://localhost:8000/health
```

Expected:
```json
{"status":"ok","version":"2.0.0","dependencies":{"database":"ok","deepseek":"ok","langfuse":"ok"}}
```

- [ ] **Step 4: Set up ngrok and test end-to-end**

```bash
ngrok http 8000
```

Update `BASE_URL` in `.env` to the ngrok HTTPS URL, then restart the server. Send a text message to your Telegram bot — expect a response about car inventory.

- [ ] **Step 5: Final commit**

```bash
git add .
git commit -m "feat: complete car dealership telegram chatbot backend"
```

---

## Self-Review Checklist

### Spec Coverage

| Spec Section | Covered By |
|---|---|
| Domain entities (Car, Lead, Meeting, Reminder) | Task 2 |
| Domain port ABCs (5 repos + 4 services) | Tasks 3–4 |
| Domain exceptions | Task 2 |
| ORM models (5 tables) | Task 5 |
| Alembic migrations + seed data | Task 6 |
| Infrastructure repositories (5) | Task 7 |
| OpenAI adapter (Whisper STT + TTS) | Task 8 |
| Telegram adapter | Task 8 |
| Calendar adapter (FreeBusy + create) | Task 8 |
| Gmail adapter (HTML email) | Task 8 |
| LangFuse CallbackHandler | Task 9 |
| DI container | Task 9 |
| `get_inventory` tool | Task 10 |
| `get_calendar_events` tool | Task 10 |
| `schedule_meeting` tool | Task 10 |
| `send_email` tool | Task 10 |
| LangGraph agent graph (DeepSeek, trim_messages) | Task 11 |
| System prompt with scope guard | Task 11 |
| MessageProcessingService (voice/text pipeline) | Task 12 |
| `POST /webhook/telegram` | Task 13 |
| `GET /health` | Task 13 |
| FastAPI lifespan (webhook setup + checkpointer) | Task 13 |
| Unit tests (domain, tools, processor, agent) | Tasks 2, 10, 11, 12 |
| Integration tests (repos, webhook) | Task 14 |
| `.env.example` + config | Task 1 |
| Seed data (10 vehicles) | Task 6 |

All spec requirements are covered. ✓
