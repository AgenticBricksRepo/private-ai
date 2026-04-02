# Private AI Gateway

A private, white-labelled AI gateway that organisations deploy under their own brand. Users chat with AI models (Claude, GPT-4o) through a familiar interface with streaming responses, image understanding, and markdown rendering. Administrators configure agents, connect document libraries, wire up tools, and manage everything from a built-in admin dashboard.

## What It Does

- **Chat with LLMs** — streaming responses via SSE, multi-turn context, markdown rendering
- **Image understanding** — upload images and ask questions about them (Claude + GPT-4o vision)
- **Agents** — preconfigured personas with system prompts, selectable per session
- **Tools** — register external HTTP endpoints the model can call during conversation
- **Document folders** — upload documents, auto-indexed, injected into model context
- **Admin dashboard** — branding, themes, user management, usage analytics, audit log
- **White-labelling** — per-tenant branding, logo, and 16+ DaisyUI themes
- **Session recording** — every conversation archived to S3/MinIO as JSON
- **Audit log** — every action logged with filtering, search, and expandable detail

## Quick Start

### Prerequisites

- **Docker & Docker Compose** (for Postgres + MinIO)
- **Python 3.11+**
- At least one LLM API key: **Anthropic** and/or **OpenAI**

### Option A: Using uv (recommended, faster)

```bash
git clone https://github.com/AgenticBricksRepo/private-ai.git
cd private-ai

# Start infrastructure
docker compose up -d

# Create venv and install deps
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and/or OPENAI_API_KEY

# Set up database
alembic upgrade head
python scripts/seed_dev_data.py

# Run
flask run --port 5001
# Open http://localhost:5001 — log in as dev@localhost
```

### Option B: Using pip

```bash
git clone https://github.com/AgenticBricksRepo/private-ai.git
cd private-ai

# Start infrastructure
docker compose up -d

# Create venv and install deps
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Edit .env — add your ANTHROPIC_API_KEY and/or OPENAI_API_KEY

# Set up database
alembic upgrade head
python scripts/seed_dev_data.py

# Run
flask run --port 5001
# Open http://localhost:5001 — log in as dev@localhost
```

### What the seed creates

- A **dev tenant** with dark theme
- An **admin user** (`dev@localhost`)
- A **General Assistant** agent
- Two demo **tools** (echo via httpbin, weather via wttr.in)

## How It Works

```
User Browser                Flask App                    LLM API
    |                           |                           |
    |-- POST /api/chat -------->|                           |
    |                           |-- build context           |
    |                           |   (system prompt +        |
    |                           |    history + docs +       |
    |                           |    tool definitions)      |
    |                           |                           |
    |                           |-- stream request -------->|
    |<-- SSE text chunks -------|<-- stream response -------|
    |                           |                           |
    |                           |   if tool_call:           |
    |                           |-- call tool endpoint      |
    |                           |-- feed result back ------>|
    |<-- more SSE chunks -------|<-- continue response -----|
    |                           |                           |
    |                           |-- async hooks:            |
    |                           |   audit log, usage,       |
    |                           |   session recording       |
```

### Core Loop (Orchestrator)

The orchestrator is a Python generator that:
1. Builds context (system prompt + conversation history + attached files + tool definitions)
2. Streams the model response to the client via SSE
3. If the model requests tool calls, executes them and feeds results back
4. Loops until the model signals completion or a budget limit is reached
5. Fires async hooks (audit log, usage tracking, session recording to S3)

### Model Router

The model router abstracts LLM providers behind a common streaming interface. Currently supports:
- **Claude** (Anthropic) — via `anthropic` Python SDK
- **GPT-4o** (OpenAI) — via `openai` Python SDK

Adding a model is: write an adapter (~80 lines), register it in the router. The orchestrator doesn't change.

### No Build Step

The frontend uses CDN-loaded libraries only:
- **Tailwind CSS + DaisyUI** — styling and themes
- **HTMX** — all UI interactions (forms, partial updates, CRUD)
- **marked.js** — markdown rendering in chat
- **Vanilla JS** — one file (`chat-stream.js`) for SSE streaming

Zero npm, zero webpack, zero bundling.

## Running Tests

```bash
# Unit tests — no Docker needed, runs in ~1s
pytest -m unit

# Integration tests — needs Postgres + MinIO running
pytest -m integration

# E2E browser tests — needs app running on port 5001
pytest -m e2e

# E2E with visible browser (watch it run)
pytest -m e2e --headed --slowmo 200

# Real LLM E2E tests — needs valid API keys, makes real API calls
pytest tests/e2e/test_real_chat.py -m e2e --headed

# Everything
pytest
```

First-time Playwright setup:
```bash
playwright install chromium
```

## Project Structure

```
app/
├── __init__.py              # Flask app factory (create_app)
├── config.py                # Environment validation (fails fast on missing vars)
├── constants.py             # All named constants — no magic values anywhere
├── errors.py                # Custom exceptions
├── extensions.py            # Singletons (DB pool, S3, model router, hooks)
├── auth/                    # Dev bypass login + SSO skeleton (Authlib OIDC)
├── chat/                    # Chat page + SSE streaming API + file attach
├── agents/                  # Agent CRUD + markdown file loader
├── tools/                   # Tool registration + HTTP executor
├── folders/                 # Document folders + Tier 1/2 indexing
├── admin/                   # Dashboard, users, usage, audit log, branding
├── orchestrator/            # Core engine: context → model → tool loop → hooks
│   ├── engine.py            # The run() generator — heart of the system
│   ├── context.py           # Context building and compaction
│   └── models.py            # Dataclasses (SessionContext, ToolResult, etc.)
├── model_router/            # LLM abstraction layer
│   ├── base.py              # ModelAdapter ABC
│   ├── claude_adapter.py    # Anthropic streaming + vision
│   ├── openai_adapter.py    # OpenAI streaming + vision
│   └── router.py            # Dispatch by model_id
├── hooks/                   # Async hooks (ThreadPoolExecutor, non-blocking)
│   ├── audit_logger.py      # Tool call audit → audit_log table
│   ├── usage_logger.py      # Token usage → usage_events table
│   ├── session_recorder.py  # Full session → S3 as JSON
│   └── session_audit.py     # Session start/end → audit_log
├── storage/                 # S3-compatible (works with MinIO locally)
└── db/                      # Direct SQL queries (psycopg v3, no ORM)

templates/                   # Jinja2 — one template per page
static/js/chat-stream.js    # The only JS file — SSE streaming + markdown
agents/                      # Agent .md files (frontmatter + prompt)
scripts/seed_dev_data.py     # Seeds tenant, user, agent, demo tools
tests/                       # pytest: unit / integration / e2e (Playwright)
```

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | — | PostgreSQL connection string |
| `S3_BUCKET` | Yes | — | S3/MinIO bucket name |
| `S3_ENDPOINT_URL` | Yes | — | `http://localhost:9000` for MinIO |
| `AWS_REGION` | Yes | — | AWS region |
| `AWS_ACCESS_KEY_ID` | Yes | — | S3/MinIO access key |
| `AWS_SECRET_ACCESS_KEY` | Yes | — | S3/MinIO secret key |
| `SECRET_KEY` | Yes | — | Flask session signing key |
| `ANTHROPIC_API_KEY` | One needed | — | Anthropic API key for Claude |
| `OPENAI_API_KEY` | One needed | — | OpenAI API key for GPT-4o |
| `AUTH_MODE` | No | `sso` | `dev` for local bypass, `sso` for production |
| `DEV_USER_EMAIL` | No | `dev@localhost` | Default email in dev mode |

## Admin Features

Access via the **Admin** dropdown in the nav bar (admin users only).

- **Dashboard** — session stats, token usage, branding (app name + logo), theme selector (16 themes)
- **Users** — list all users and roles
- **Agents** — create, edit, delete agents with system prompts
- **Tools** — register external HTTP endpoints with schema validation
- **Folders** — create document folders, upload files, auto-indexed
- **Usage** — token usage by model and by user
- **Audit Log** — every action logged, expandable detail, filtering by event type, payload search, pagination

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Framework | Flask | Simple, explicit. UI + API in one process. |
| Templates | Jinja2 | Ships with Flask. One template per page. |
| Styles | Tailwind + DaisyUI (CDN) | No build step. Theme switching via `data-theme`. |
| Interactivity | HTMX (CDN) | Zero JS for forms and CRUD. |
| Streaming | `fetch` + ReadableStream | One file, native browser API. |
| Markdown | marked.js (CDN) | Renders LLM responses with headings, code, lists, tables. |
| Language | Python 3.11+ | One language across the entire codebase. |
| Database | PostgreSQL via psycopg v3 | Direct SQL, no ORM. Readable and testable. |
| Migrations | Alembic | Version-controlled schema changes. |
| Storage | boto3 (S3/MinIO) | Documents, indexes, session recordings. |
| Auth | Authlib (OIDC/SAML) | Azure AD, Google Workspace, generic SAML. |
| Testing | pytest + Playwright | Unit, integration, and E2E browser tests. |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Required environment variables not set` | `cp .env.example .env` and fill in API keys |
| `Connection refused on port 5432` | `docker compose up -d` |
| `MinIO bucket not found` | `docker compose up minio-init` |
| `No model adapters configured` | Add `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` to `.env` |
| `Target database is not up to date` | `alembic upgrade head` |
| Port 5000 already in use (macOS) | Use `flask run --port 5001` — macOS AirPlay uses 5000 |
| `ModuleNotFoundError: pip` | `python -m ensurepip && pip install -e ".[dev]"` |

## License

Proprietary. All rights reserved.
