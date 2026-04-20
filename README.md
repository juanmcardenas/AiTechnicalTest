# Car Dealership Telegram Chatbot

An AI-driven Telegram bot that handles a car dealership's front-desk interactions: answering inventory questions, scheduling customer visits on a shared Google Calendar, and emailing vehicle specifications. Built on FastAPI with a LangGraph ReAct agent over DeepSeek, persistent per-session memory in PostgreSQL, and LangFuse tracing for every turn.

---

## Table of Contents

1. [Features](#1-features)
2. [Capabilities](#2-capabilities)
3. [Architecture](#3-architecture)
4. [LangGraph Usage](#4-langgraph-usage)
5. [Business Rules](#5-business-rules)
6. [Running the Project](#6-running-the-project)
7. [Testing](#7-testing)
8. [Repository Layout](#8-repository-layout)

---

## 1. Features

| Feature | Summary |
|---|---|
| **Text + voice messaging** | Customers talk to the bot in Telegram. Voice notes are transcribed with OpenAI Whisper and replied to with TTS audio; text conversations stay text-only. |
| **Inventory search** | The agent calls `get_inventory` with any subset of 11 filters (brand, model, year, color, price range, km range, condition, fuel type, transmission) and returns up to 10 matching cars as JSON. |
| **Visit scheduling** | Uses Google Calendar FreeBusy to find real open 1-hour slots during business hours (9 AM – 6 PM, weekdays), then creates a Calendar event on a shared dealership calendar. Event includes the customer email in the description and the tool returns an `add_to_calendar_url` that the customer can click to add it to their own calendar. |
| **Email spec sheets** | Sends an HTML email with the vehicle's specs (color, price, km, fuel, transmission, condition, description) via Gmail SMTP. Every attempt — success or failure — is logged to `email_sent_logs`. |
| **Session-scoped memory** | A Session starts on first message and ends after 5 minutes of idle. Each new session begins with a fresh agent memory, so the bot greets the customer again and re-asks for identity if needed. |
| **Identity capture & gating** | On a new session with an unidentified lead, the bot greets and asks for name, email, or phone. The `update_lead_identity` tool writes whatever the customer shares to the lead record. `schedule_meeting` and `send_email` are gated until at least one identifier is on file. |
| **Default timezone** | Times the customer mentions without an explicit offset are interpreted as `America/New_York`. All times shown back to the customer include the timezone abbreviation (EDT/EST). |
| **Strict scope guard** | The system prompt instructs the agent to decline anything unrelated to inventory, scheduling, test drives, or specs — responding with a single canned message. |
| **Observability** | Every LangGraph node transition, LLM call, and tool invocation is traced in LangFuse automatically via a CallbackHandler attached to each `ainvoke`. |
| **Fallback on error** | The outer `receive_message` wraps the full pipeline; any uncaught exception is logged with a full traceback and the customer receives a short "I'm having a little trouble right now" message. |

---

## 2. Capabilities

| Customer intent | Tool(s) the agent invokes |
|---|---|
| "What cars do you have?" / "Show me used Toyotas under $25k" | `get_inventory` |
| "I want to book a visit for Monday 10am" | `get_calendar_events` → `schedule_meeting` |
| "Email me the specs for the Civic" | `send_email` |
| "My name is Juan, phone is +57..." (anywhere in the conversation) | `update_lead_identity` |
| Anything off-topic (weather, politics, jokes, etc.) | No tool; canned out-of-scope reply |

---

## 3. Architecture

### 3.1 Hexagonal layering

```
┌─────────────────────────────────────────────────────────┐
│                INFRASTRUCTURE (driving)                  │
│    FastAPI /webhook + /health · Pydantic schemas         │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    APPLICATION                           │
│  MessageProcessingService · LangGraph ReAct agent        │
│  5 LangChain @tool factory closures · timezone_utils     │
└──────┬───────────────────────────────────────┬──────────┘
       │                                       │
       ▼                                       ▼
┌─────────────────────┐         ┌──────────────────────────┐
│       DOMAIN         │         │  INFRASTRUCTURE (driven) │
│  Entities · Ports    │◄────────│  SQLAlchemy repos        │
│  (stdlib only)       │         │  OpenAI / Google / SMTP  │
└─────────────────────┘         │  LangFuse · Telegram     │
                                │  AsyncPostgresSaver       │
                                └──────────────────────────┘
```

**Layer rules:**

| Layer | May import from |
|-------|-----------------|
| `domain/` | Nothing outside `domain/` (Python stdlib only) |
| `application/` | `domain/` only |
| `infrastructure/` | `domain/` + `application/` |

ORM models never cross into `domain/` or `application/`. The mapping between ORM rows and domain entities happens exclusively inside `infrastructure/repositories/` via each repo's `_to_domain` helper.

### 3.2 Request lifecycle

```
Telegram                 FastAPI                MessageProcessingService              LangGraph agent                  External
   │                        │                             │                                    │                          │
   │── Update (webhook) ───►│                             │                                    │                          │
   │                        │── 200 OK ───────────────────┼───► queued in BackgroundTasks ────►│                          │
   │                        │                             │                                    │                          │
   │                        │           async with session_factory() as db:                    │                          │
   │                        │           get_or_create(lead)                                    │                          │
   │                        │           resolve/create Session (idle>5m → new)                 │                          │
   │                        │           touch Session.last_message_at                          │                          │
   │                        │           if voice: download_voice ─► transcribe ──►             │                          │
   │                        │                                                                  │                          │
   │                        │   build 5 tools + agent_graph(checkpointer, tools, session_ctx)  │                          │
   │                        │   agent.ainvoke({"messages":[HumanMessage]}, config={...}) ─────► model ◄──► tools ─────────►│
   │                        │                                                                  │                          │
   │                        │   response = result["messages"][-1].content                      │                          │
   │                        │   if voice: synthesize ─► send_voice     else: send_text         │                          │
   │                        │   lead.last_contacted_at = now ; lead_repo.update(lead)          │                          │
   │◄── reply ──────────────┤                                                                  │                          │
```

### 3.3 Persistence

| Table | Purpose |
|-------|---------|
| `inventory` | Vehicle catalogue (10 seed rows) |
| `leads` | One row per `telegram_chat_id` — `UNIQUE` constraint prevents duplicates |
| `sessions` | One row per conversation episode, `(lead_id, last_message_at DESC)` indexed |
| `meetings` | Scheduled visits, foreign-keyed to `leads` and `inventory`, holding the `google_event_id` |
| `reminders` | Scheduled follow-ups (table present; no user-facing use yet) |
| `email_sent_logs` | Every email-send attempt (success or failure, with `error_msg` when applicable) |
| `conversation_history` | Audit log (table present; optional) |
| `checkpoints`, `checkpoint_blobs`, `checkpoint_writes` | **Managed entirely by LangGraph**'s `AsyncPostgresSaver`. One serialized conversation state per `thread_id`. We never write to these tables directly. |

Migrations live under `alembic/versions/` and are applied with `uv run alembic upgrade head`.

---

## 4. LangGraph Usage

### 4.1 Why the prebuilt ReAct graph

The bot's flow is exactly ReAct: the LLM decides which tool (if any) to call, the tool runs, the result is appended to the message list, the LLM decides again, and so on until it produces a final answer. We use `langgraph.prebuilt.create_react_agent` — no custom `StateGraph` — because its compiled 2-node graph (`model` ↔ `tools`) matches this flow one-to-one.

```
          ┌───────────┐
          │   model   │ ← LLM call; may emit zero or more tool_calls
          └─────┬─────┘
                │ tool_calls present?
        ┌───────┴───────┐
        │               │
        ▼               ▼
  ┌───────────┐     ┌─────┐
  │   tools   │     │ END │ ← final AIMessage returned to MessageProcessingService
  └─────┬─────┘     └─────┘
        │ results appended to messages
        └──► loops back to "model"
```

### 4.2 Per-session memory via `AsyncPostgresSaver`

LangGraph's `AsyncPostgresSaver` (from `langgraph-checkpoint-postgres`) is attached as a `checkpointer` to the compiled graph. After every node transition, the full message list is serialized into the `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` tables, keyed on `thread_id` from the invocation config.

- **`thread_id = session.id`** — each Session gets its own conversation memory. A fresh Session means the agent starts from scratch, which is how we get a clean greeting after 5+ minutes of silence.
- The checkpointer lifecycle is wired via `AsyncExitStack` in FastAPI's lifespan (`app/main.py`); it connects once on startup and the underlying async connection is closed on shutdown.

### 4.3 Dynamic system prompt via `state_modifier`

`state_modifier` is a function that runs before every `model` node invocation and rewrites the message list the LLM will see. `_build_state_modifier` returns a closure that:

1. Prepends a per-request **SESSION CONTEXT** block (built from the lead's identity and whether the session is new) — this is how identity gating and the greeting behaviour surface to the agent.
2. Prepends the static `SYSTEM_PROMPT` (dealership name/address, scope restriction, tool-usage guidance, timezone policy).
3. Runs `trim_messages` with `count_tokens_approximately` (DeepSeek doesn't expose `get_num_tokens_from_messages`) to cap the window at 6 000 tokens.

Because the agent is rebuilt per request with a freshly-computed `session_ctx`, the context that reaches the LLM is always current without needing to write it back into the conversation history.

### 4.4 Tools — factory closures

Tools live under `app/application/services/tools/`. Each one is produced by a `make_<name>_tool(deps)` factory that returns a `@tool`-decorated async function:

| Tool | Factory | Injected deps |
|---|---|---|
| `get_inventory` | `make_get_inventory_tool(inventory_repo)` | `IInventoryRepository` |
| `get_calendar_events` | `make_get_calendar_events_tool(calendar_service)` | `ICalendarService` |
| `schedule_meeting` | `make_schedule_meeting_tool(meeting_repo, lead_repo, calendar_service)` | ports + service |
| `send_email` | `make_send_email_tool(inventory_repo, email_service, email_log_repo, lead_repo)` | ports + service |
| `update_lead_identity` | `make_update_lead_identity_tool(lead_repo)` | `ILeadRepository` |

**`lead_id` is injected through `RunnableConfig`, not LLM-supplied.** Every tool that needs the current lead reads `config["configurable"]["lead_id"]`. This prevents the agent from fabricating UUIDs, which used to cause foreign-key violations.

### 4.5 Observability

A single `langfuse.callback.CallbackHandler` is attached to every `ainvoke`:

```python
config = {
    "configurable": {"thread_id": str(session.id), "lead_id": str(lead.id)},
    "callbacks": [langfuse_handler],
}
```

This traces every node transition, model call, and tool invocation to the LangFuse dashboard with zero custom instrumentation.

---

## 5. Business Rules

All business rules are encoded in one of three places. Nothing is hidden in infrastructure.

### 5.1 The system prompt (`app/application/services/agent_graph.py`)

The static `SYSTEM_PROMPT` encodes:

- **Identity** — dealership name, address, current date (refreshed on each module load).
- **Scope restriction** — off-topic questions receive a single canned reply, no tool calls.
- **Tool usage** — tiebreakers when customer intent is ambiguous (scheduling vs. email), instructions to never fabricate success when a tool returned an error, instructions to always include `add_to_calendar_url` in the reply when `schedule_meeting` succeeded, timezone policy.

### 5.2 The dynamic session context (`app/application/services/message_processor.py::_build_session_context`)

Built per request and prepended to the system prompt:

- Whether this is a NEW or ongoing session.
- The current customer identity (name/email/phone, or `(unknown)` if none).
- On a NEW + unknown session, tells the agent to greet and ask for contact info.
- Reminds the agent to call `update_lead_identity` whenever the customer shares any details.
- States that identity is required for scheduling and email.

### 5.3 Tool-level gating (defense in depth)

Even if the prompt were ignored, the tools themselves enforce identity:

```python
lead = await lead_repo.get_by_id(lead_id)
if lead is None or not (lead.name or lead.email or lead.phone):
    return json.dumps({"error": "Lead not identified. Ask the customer..."})
```

`schedule_meeting` and `send_email` both do this check before any side effect. `get_inventory` and `get_calendar_events` stay ungated — browsing is free.

### 5.4 Timezone handling (`app/application/services/timezone_utils.py`)

- `parse_local_datetime(s)` attaches `America/New_York` to any naive ISO string, so "Monday at 2 PM" goes through as Eastern.
- `format_for_user(dt)` renders as `"Monday, April 20, 2026 at 2:00 PM EDT"` — always in Eastern, always with the tz abbreviation.
- `get_calendar_events` enriches every slot with a `display` field; `schedule_meeting` returns both the ISO `scheduled_at` and a friendly `scheduled_at_display`. The agent is instructed to use the display fields in user-facing replies.

### 5.5 Session boundary

`Session.is_active(now)` returns True when `now - last_message_at <= 5 minutes`. The constant lives in `app/domain/entities/session.py` (`SESSION_IDLE_MINUTES = 5`). On each incoming message:

1. `SessionRepository.get_active_for_lead(lead.id, now)` — returns the most recent session if active, else None.
2. If None → `create(lead.id)` → `is_new_session = True`.
3. `touch(session.id, now)` — advances `last_message_at` regardless of whether processing later succeeds (prevents zombie short sessions).

### 5.6 Error handling

| Layer | Strategy |
|---|---|
| Webhook handler | Always returns `200 OK`; processing happens in `BackgroundTasks`. |
| Tools | Return structured `{"success": false, "error": "..."}` JSON for every failure mode. The agent sees the error and tells the customer what specifically went wrong. |
| External adapters (Telegram, OpenAI, Calendar, Gmail) | Raise exceptions on HTTP errors or API failures — no silent swallowing. |
| `MessageProcessingService.receive_message` | Final catch-all — logs traceback, sends the generic "I'm having a little trouble" fallback to the customer. |

---

## 6. Running the Project

### 6.1 Prerequisites

- **Python 3.11** (via `uv` — see below)
- **`uv`** (Astral's package manager) — if you don't have it: `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Supabase Postgres** project (free tier works). Use the **Connection Pooling** URI (port `5432` or `6543`, host `aws-<n>-<region>.pooler.supabase.com`) — direct hosts (`db.<ref>.supabase.co`) are IPv6-only and won't work from most home ISPs.
- **DeepSeek API key** — https://platform.deepseek.com/
- **OpenAI API key** — https://platform.openai.com/ (Whisper STT + TTS only)
- **LangFuse project** — https://cloud.langfuse.com/ (secret + public keys)
- **Google Cloud service account** with the Calendar API enabled — https://console.cloud.google.com/ → Create a service account, download the JSON key, and share your dealership Google Calendar with the service account's email ("Make changes to events" permission).
- **Gmail account with 2FA enabled**, plus a 16-char **App Password** — https://myaccount.google.com/apppasswords
- **Telegram bot** from BotFather (https://t.me/BotFather) — note the bot token
- **ngrok** (or any HTTPS tunnel) for local Telegram webhooks — `curl -LsSf https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-darwin-amd64.zip` etc.

### 6.2 Install

```bash
git clone <this-repo>
cd AiTechnicalTest
uv python install 3.11
uv sync
```

### 6.3 Configure

Copy the template and fill in real values:

```bash
cp .env.example .env
```

Required keys:

| Variable | Example |
|---|---|
| `TELEGRAM_BOT_TOKEN` | `1234567890:ABCDE...` |
| `DATABASE_URL` | `postgresql+asyncpg://postgres.<ref>:<pw>@aws-0-us-east-1.pooler.supabase.com:5432/postgres` |
| `DEEPSEEK_API_KEY` | `sk-...` |
| `OPENAI_API_KEY` | `sk-...` |
| `LANGFUSE_SECRET_KEY` / `LANGFUSE_PUBLIC_KEY` | from the LangFuse dashboard |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | path to downloaded JSON, or inline JSON |
| `GOOGLE_CALENDAR_ID` | the shared calendar's ID (secondary calendar IDs end in `@group.calendar.google.com`) |
| `GMAIL_SENDER` | the Gmail account sending emails |
| `GMAIL_APP_PASSWORD` | 16-char App Password for that same account |
| `BASE_URL` | your public HTTPS URL (e.g. the ngrok tunnel URL) |
| `DEALERSHIP_NAME` / `DEALERSHIP_ADDRESS` | shown in the system prompt and event description |
| `DEFAULT_TIMEZONE` | defaults to `America/New_York` |

### 6.4 Migrate

```bash
uv run alembic upgrade head
```

This creates all tables (`inventory`, `leads`, `sessions`, `meetings`, `reminders`, `email_sent_logs`, `conversation_history`) and seeds 10 vehicles. The LangGraph `checkpoints` tables are created on server startup.

### 6.5 Run locally

Two terminals:

**Terminal A — tunnel:**

```bash
ngrok http 8000
# copy the https://*.ngrok-free.dev URL
```

**Terminal B — update `BASE_URL` in `.env` to that URL, then:**

```bash
uv run uvicorn app.main:app --port 8000
```

On startup the server registers the Telegram webhook at `{BASE_URL}/webhook/telegram` and initialises the LangGraph checkpointer. The tunnel must already be up at this point.

Verify:

```bash
curl -sS http://localhost:8000/health
# {"status":"ok","version":"2.0.0","dependencies":{"database":"ok","deepseek":"ok","langfuse":"ok"}}
```

Send any message to your Telegram bot; watch the server logs for the full flow.

---

## 7. Testing

```bash
uv run pytest               # unit + integration
uv run pytest tests/unit/   # unit only (fast, no network)
```

- **Unit tests** mock all I/O (repos, adapters, agent). They cover domain entities, tool behaviour (gating + happy paths + error paths), the `state_modifier`'s prompt construction, session resolution in the message processor, and the `timezone_utils` helpers.
- **Integration tests** hit the real Supabase database for the inventory, lead, and session repositories, and exercise the `/webhook/telegram` endpoint end-to-end via FastAPI's `TestClient` (with Telegram + Calendar + Gmail services mocked).

There is no local Postgres substitute — integration tests require a populated Supabase database accessible from the `DATABASE_URL` in `.env`.

---

## 8. Repository Layout

```
app/
├── main.py                              # FastAPI app factory + lifespan (checkpointer + webhook setup)
├── config.py                            # Pydantic Settings reading from .env
├── domain/                              # Pure Python — stdlib only
│   ├── entities/                        # Car, Lead/LeadStatus, Meeting, Reminder, Session
│   ├── repositories/                    # IInventoryRepository, ILeadRepository, etc. (ABCs)
│   ├── use_cases/                       # ISpeechService, ICalendarService, IEmailService, ITelegramService
│   └── exceptions.py
├── application/                         # Business logic — imports domain only
│   └── services/
│       ├── message_processor.py         # Per-message orchestration: session resolution, agent invocation
│       ├── agent_graph.py               # build_agent_graph, SYSTEM_PROMPT, state_modifier
│       ├── timezone_utils.py            # parse_local_datetime, format_for_user, default_tz
│       └── tools/                       # 5 factory-closure tools
├── infrastructure/                      # Adapters — imports domain + application
│   ├── handlers/                        # FastAPI routers
│   ├── database/                        # Engine, Base, ORM models, checkpointer context
│   ├── repositories/                    # Concrete repos implementing domain ports
│   ├── events/                          # OpenAI, Telegram, Calendar, Gmail adapters
│   ├── schemas/                         # Pydantic Telegram + health models
│   └── container/                       # DI wiring for FastAPI Depends
└── ...

tests/
├── conftest.py                          # shared fixtures (real DB session for integration)
├── unit/
│   ├── test_domain/                     # entity + Session tests
│   ├── test_tools/                      # per-tool, mocked deps
│   ├── test_agent_graph/                # state_modifier tests
│   ├── test_message_processor/          # session resolution + pipeline tests
│   └── test_timezone_utils/             # parsing + formatting
└── integration/
    ├── test_inventory_repo/             # real Supabase
    ├── test_lead_repo/                  # real Supabase
    ├── test_session_repo/               # real Supabase
    └── test_webhook/                    # TestClient + mocked externals

alembic/
└── versions/
    ├── 0001_initial_schema.py
    ├── 0002_seed_inventory.py
    └── 0003_sessions.py

docs/
└── superpowers/
    ├── specs/                           # Design docs for the two feature bundles
    └── plans/                           # Step-by-step implementation plans
```

---

*Backend v2.0 — Car Dealership Telegram Bot*
