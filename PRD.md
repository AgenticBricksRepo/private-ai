# Private AI Gateway — Product Requirements Document

*Version 1.2 · March 2026*

---

## 1. Purpose

A private, white-labelled AI gateway that organisations deploy under their own brand. Users chat with AI models through a familiar interface. Administrators configure agents, connect document libraries, and wire up tools. The underlying models are swappable. The platform never writes data anywhere on its own — all mutations happen through explicitly registered tools.

This is not a general-purpose AI platform. It is a focused, maintainable product with a clear build order and hard scope boundaries.

---

## 2. Guiding Principles

**Simplicity over cleverness.** Code should be readable by a mid-level developer without explanation. If a pattern requires a comment to explain why it exists, reconsider the pattern. This does not mean avoiding abstraction — it means abstraction earns its place.

**Errors are information, but not all errors are equal.** Distinguish between two categories:

- *Unexpected failures* — bugs, misconfiguration, unhandled states. These propagate. Do not catch them to hide them. The full trace surfaces in logs immediately.
- *Expected operational failures* — tool timeouts, transient network errors, idempotent read retries. These get explicit, local handling with a clear contract. A tool that times out is not a bug; it needs a defined response.

The only place errors are translated into user-facing language is at the HTTP boundary, and only after the full trace is logged.

**No magic.** No magic numbers. No magic strings. No implicit defaults buried in code. All configuration is explicit, named, and lives in `constants.py` or environment config. If a value matters, it has a name that explains what it is.

**Test behaviour, not lines.** Every critical path has a test that asserts on meaningful outcomes. Coverage is a signal, not a target. A test that hits a line without asserting anything useful is worse than no test — it creates false confidence. The CI pipeline enforces coverage on critical paths (orchestrator, model router, tool executor, hooks, all API routes). It does not mandate a blanket percentage.

**Model agnosticism from day one.** The orchestrator never calls a model API directly. It calls the model router. Swapping models is a config change, not a code change.

**Write-back only through tools.** The platform core is read-only. Any mutation of external state happens through a registered tool. This is enforced architecturally, not by convention.

**Retrieval simplicity is a deliberate constraint, not a universal truth.** The document index approach (no RAG, no vector DB) works well for structured enterprise document corpora with modern context windows. It has limits: heterogeneous unstructured corpora, passage-level retrieval needs, and very large collections will eventually require more. These are known boundaries. When a client hits them, the retrieval layer is evolved — not the entire product.

---

## 3. Concepts

### 3.1 Session

The runtime context for a human-driven conversation. A session is created when a user starts a chat and destroyed when they close it or it times out.

A session holds:
- The active agent (optional — user can chat without an agent)
- Ad hoc files attached by the user for this session only
- Folders explicitly included by the user for this session
- Tools and connectors active for this session
- The conversation history (stored as a separate `messages` table — see section 5.1)
- Token usage

Sessions are ephemeral. Attached files do not persist beyond the session. Included folders remain available but are not modified.

Every completed session is recorded to object storage as a JSON archive. Retention is configured per tenant via a storage lifecycle policy. See section 5.4.

### 3.2 Agent

A markdown file. An agent defines a persona, a system prompt, and default configuration. It is a pre-built session template.

An agent has two modes:

**Interactive** — the agent seeds a session. The user drives the conversation. The agent's config is the starting point; the user can attach additional files or include additional folders on top.

**Headless** — the agent runs autonomously, triggered by a schedule, a webhook, or an event. There is no human in the loop. Output is routed to a tool (e.g. post to Slack, write to a webhook). See section 4.6 for headless execution details.

Agent file format:

```markdown
---
name: Support Digest
description: Summarises yesterday's support tickets and posts to Slack
mode: headless
trigger:
  type: schedule
  cron: "0 8 * * 1-5"
tools: [get_tickets, post_to_slack]
connectors: [zendesk]
folders: [support-kb]
requires_confirmation: false
---

You are a support operations assistant.
Every morning, use get_tickets to pull yesterday's open tickets.
Group them by category and priority.
Write a concise digest and post it to #support-digest using post_to_slack.
Be brief. Use bullet points. Do not fabricate data.
```

### 3.3 Orchestrator

The core engine. The orchestrator takes a session context, builds a model payload, streams the response, handles tool call requests from the model, executes those tool calls, feeds results back to the model, and loops until the model signals completion or a budget limit is reached.

The orchestrator is responsible for:
- Context assembly (system prompt + history + docs + tool definitions)
- Streaming the model response
- Detecting and executing tool calls
- Feeding tool results back to the model
- Enforcing token budget and tool call limits
- Supporting cancellation (user closes tab, headless run is aborted)
- Running hooks at defined points

The orchestrator has no knowledge of:
- Whether a tool is read-only or write-back (that is the tool's concern)
- Whether it is running interactively or headless (that is the session's concern)
- Which model is active (that is the router's concern)

### 3.4 Tool

An HTTP REST endpoint with a structured definition. The orchestrator reads the definition to decide when and how to call the tool. The model reads the description to understand what the tool does.

Tools are registered by administrators. Write-back capability lives entirely within the tool's implementation — the platform does not gate it.

Tools have explicit contracts around:
- Input schema validation (before the call is made)
- Authentication (api_key, OAuth — credentials from Secrets Manager, not the tool definition)
- Timeout (required, no default)
- Expected failure modes (the `side_effects` and `requires_confirmation` fields)

The platform validates tool input against the registered schema before calling the endpoint. A schema mismatch is a hard error, not a warning.

### 3.5 Connector

A tool with a managed implementation. Where a plain tool is just an endpoint the customer provides, a connector is a first-party integration (Google Drive, SharePoint, Slack, Zendesk) with a built-in OAuth flow, token refresh, pagination handling, and rate limit management. From the orchestrator's perspective, a connector is identical to a tool.

### 3.6 Folder

An indexed collection of documents stored in the platform. Folders are read-only. Users and agents can read from folders; nothing in the platform writes to them.

Folders use a two-tier approach. The tier is set explicitly at folder creation — it is not inferred automatically.

**Tier 1** — small corpus: documents are injected directly into the session context. No index needed. Appropriate when total content fits comfortably within the model's context window (`FOLDER_TIER1_MAX_TOKENS` in `constants.py`).

**Tier 2** — larger corpus: on upload, each document gets a 150-word summary and metadata written to a per-folder `index.json`. At query time, the orchestrator injects the index, the model selects relevant documents by ID, the orchestrator fetches those documents in full and appends them to context.

**Known limits of Tier 2:** Works well for structured corpora where document-level selection is sufficient (policy libraries, handbooks, knowledge bases). It will underperform for heterogeneous unstructured collections, questions that need passage-level retrieval, or corpora above a few hundred documents. Tier 3 (Postgres full-text search, Phase 3) extends the range. Beyond that, a retrieval layer is a separate architectural decision.

No vector database. No embeddings pipeline. No chunking.

---

## 4. Architecture

### 4.1 Components

```
┌──────────────────────────────────────────────┐
│                 Flask App                    │
│                                              │
│  Jinja2 templates · HTMX · DaisyUI themes   │
│  chat-stream.js (SSE, ~30 lines)             │
│  Per-tenant branding via data-theme attr     │
└─────────────────────┬────────────────────────┘
                      │ same process
┌─────────────────────▼────────────────────────┐
│              Orchestrator                    │
│  Context builder · Model router              │
│  Tool executor · Hook runner                 │
│  Budget enforcement · Cancellation           │
└──────────┬───────────────────┬───────────────┘
           │                   │
┌──────────▼──────┐   ┌────────▼──────────────┐
│  Model Router   │   │  Tool / Connector      │
│  Claude         │   │  HTTP endpoints        │
│  GPT-4o         │   │  schema-validated      │
│  Gemini …       │   │  timeout-enforced      │
└──────────┬──────┘   └────────────────────────┘
           │
┌──────────▼──────────────────────────────────┐
│                Data Layer                   │
│  Postgres · S3-compatible object storage    │
│  index.json per folder · session recordings │
│  Langfuse (self-hosted, async, LLM tracing) │
└─────────────────────────────────────────────┘
```

Flask serves both the UI and the API from one process. No separate frontend service.

### 4.2 Frontend Approach

**Templates:** Jinja2. One template per page. Shared components are Jinja2 macros in `templates/macros/`.

**Styles:** Tailwind CSS via CDN + DaisyUI via CDN. No build step. No custom CSS except one `<style>` block in `base.html` that writes DaisyUI CSS variables from the tenant's custom theme config (if set). No inline styles anywhere else.

**Interactivity:** HTMX via CDN for all UI interactions — form submissions, partial page updates, confirmations, admin table mutations. HTMX attributes in HTML templates, zero JS files for any of this.

**Streaming:** One JS file, `static/js/chat-stream.js`, ~30 lines. Uses the browser's native `EventSource` API to consume the SSE stream and append chunks to the chat window. This is the only hand-written JavaScript in the project.

**Theming:** DaisyUI themes. The tenant's `theme` config in the DB is a string (e.g. `"corporate"`) for built-in themes, or a JSON object for a custom theme. Applied via `data-theme` on the `<html>` tag. Switching themes is a DB config change — no code change, no redeploy.

```html
<!-- base.html -->
<html data-theme="{{ tenant.theme.name }}">

{% if tenant.theme.definition %}
<style>
  [data-theme="{{ tenant.theme.name }}"] {
    {% for key, value in tenant.theme.definition.items() %}
    --{{ key }}: {{ value }};
    {% endfor %}
  }
</style>
{% endif %}
```

### 4.3 Orchestrator Loop

```python
def run(session: Session) -> Generator[str, None, None]:
    context = build_context(session)
    tool_call_count = 0

    while True:
        if context.token_count >= MAX_CONTEXT_TOKENS:
            context = compact_context(context)

        response = model_router.stream(context)

        if not response.tool_calls:
            break

        if tool_call_count >= MAX_TOOL_CALLS_PER_SESSION:
            raise OrchestratorBudgetError(
                f"Tool call limit reached: {MAX_TOOL_CALLS_PER_SESSION}"
            )

        for tool_call in response.tool_calls:
            if session.cancelled:
                return

            hook_result = run_hook(HookPoint.PRE_TOOL, tool_call, session)
            if not hook_result.proceed:
                context.append_tool_result(tool_call.id, ToolResult.halted(hook_result.reason))
                continue

            result = tool_executor.call(tool_call)   # raises on unexpected failure
                                                      # returns ToolResult.error() on expected failure
            run_hook(HookPoint.POST_TOOL, tool_call, result, session)
            context.append_tool_result(tool_call.id, result)
            tool_call_count += 1

    run_hook(HookPoint.SESSION_END, session)
```

`MAX_CONTEXT_TOKENS` and `MAX_TOOL_CALLS_PER_SESSION` are defined in `constants.py`.

Unexpected failures (model API down, unhandled exception) propagate. Expected operational failures from tools (timeout, 4xx response) return a `ToolResult.error()` so the model can reason about them.

### 4.4 Tool Executor

The tool executor handles the mechanics of calling an HTTP endpoint. It is responsible for:

- Resolving auth credentials from Secrets Manager (not from the tool definition)
- Validating input against the tool's registered schema before the call
- Enforcing the registered `timeout_ms`
- Classifying the response: success, expected failure (timeout, 4xx), unexpected failure (5xx, network error)

```python
def call(self, tool_call: ToolCall) -> ToolResult:
    tool = self.registry.get(tool_call.name)         # raises ToolNotFoundError if missing
    validated = tool.schema.validate(tool_call.args) # raises SchemaValidationError if invalid
    credentials = self.secrets.get(tool.auth_config)

    response = http.post(
        tool.endpoint,
        json=validated,
        headers=credentials.to_headers(),
        timeout=tool.timeout_ms / 1000,              # no default — timeout_ms is required
    )

    if response.status_code in TOOL_EXPECTED_ERROR_CODES:
        return ToolResult.error(response.status_code, response.text)

    response.raise_for_status()   # unexpected — propagates
    return ToolResult.success(response.json())
```

`TOOL_EXPECTED_ERROR_CODES` is defined in `constants.py`. Retries are not automatic. If a tool is idempotent and retry-safe, the agent prompt should say so and the model will retry via the loop.

### 4.5 Hook System

Hooks are called at defined points in the orchestrator loop. They observe and optionally gate execution. They do not modify the context.

```python
class HookPoint(str, Enum):
    PRE_TOOL      = "pre_tool"
    POST_TOOL     = "post_tool"
    SESSION_START = "session_start"
    SESSION_END   = "session_end"

@dataclass
class HookResult:
    proceed: bool
    reason:  str | None = None
```

Hooks that do I/O (writing to Postgres, writing to S3, calling an alert endpoint) **dispatch asynchronously**. A hook that blocks the orchestrator is a design error. The orchestrator does not wait for hook completion — it fires and continues. Hook failures are logged but do not affect the session.

Built-in hooks:

- **AuditLogger** — async write to `audit_log` on `POST_TOOL`
- **UsageLogger** — async write to `usage_events` on `SESSION_END`
- **SessionRecorder** — async write to S3 on `SESSION_END`
- **ConfirmationGate** — `PRE_TOOL` only. If `requires_confirmation` is true and the session is headless, dispatches an async alert and returns `proceed=False`. Does not block waiting for a human response — that is a separate flow outside the orchestrator.

### 4.6 Headless Agent Execution

Headless agents do not run inside the Flask request worker. Triggering a headless run enqueues an ECS `run-task` call. The ECS task runs the orchestrator in isolation with its own process and resources, separate from live user traffic.

**Trigger types:**
- `schedule` — ECS scheduled task via EventBridge. Managed by IaC per agent.
- `webhook` — `POST /api/agents/<id>/run` enqueues an ECS run-task. Returns 202 immediately.

**Run state:** Each headless run creates a record in `agent_runs` (see schema). Status transitions: `pending → running → completed | failed`. ECS task start/stop events update this via a CloudWatch event rule.

**Failure handling:** If the ECS task crashes, the run record stays in `running` until a watchdog query (run on a schedule) marks stale runs as `failed` after `HEADLESS_RUN_TIMEOUT_SECONDS`.

**Deduplication:** Schedule-triggered runs include the scheduled timestamp as an idempotency key. A run with the same agent + scheduled timestamp cannot be created twice.

**Secrets scoping:** Headless agents have access only to the tools and connectors listed in their config. The ECS task role is scoped to those secrets paths specifically — not the full tenant secrets namespace.

---

## 5. Data Model

### 5.1 Postgres Schema

```sql
CREATE TABLE tenants (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name                     TEXT NOT NULL,
  slug                     TEXT NOT NULL UNIQUE,
  logo_url                 TEXT,
  theme                    JSONB NOT NULL DEFAULT '{}',
  sso_config               JSONB NOT NULL DEFAULT '{}',
  recording_retention_days INTEGER,   -- NULL = keep forever
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL REFERENCES tenants(id),
  email       TEXT NOT NULL,
  role        TEXT NOT NULL CHECK (role IN ('admin', 'member', 'viewer')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, email)
);

CREATE TABLE sessions (
  id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      UUID NOT NULL REFERENCES tenants(id),
  user_id        UUID NOT NULL REFERENCES users(id),
  agent_id       UUID REFERENCES agents(id),
  model_id       TEXT NOT NULL,
  status         TEXT NOT NULL CHECK (status IN ('active', 'completed', 'error')),
  recording_url  TEXT,
  started_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
  ended_at       TIMESTAMPTZ
);

-- Messages are a separate table, not JSONB on sessions.
-- This allows querying across conversation history and keeps
-- session rows lightweight. Known migration path if needed later.
CREATE TABLE messages (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id  UUID NOT NULL REFERENCES sessions(id),
  role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
  content     TEXT NOT NULL,
  tool_call   JSONB,          -- populated for role='tool'
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE agents (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id       UUID NOT NULL REFERENCES tenants(id),
  name            TEXT NOT NULL,
  slug            TEXT NOT NULL,
  description     TEXT,
  prompt_md       TEXT NOT NULL,
  mode            TEXT NOT NULL CHECK (mode IN ('interactive', 'headless')),
  trigger_config  JSONB,
  tool_ids        UUID[] NOT NULL DEFAULT '{}',
  connector_ids   UUID[] NOT NULL DEFAULT '{}',
  folder_ids      UUID[] NOT NULL DEFAULT '{}',
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);

-- Run history for headless agents
CREATE TABLE agent_runs (
  id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id          UUID NOT NULL REFERENCES agents(id),
  tenant_id         UUID NOT NULL REFERENCES tenants(id),
  status            TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
  trigger_type      TEXT NOT NULL CHECK (trigger_type IN ('schedule', 'webhook')),
  idempotency_key   TEXT,          -- schedule: agent_id + scheduled_at; webhook: caller-supplied
  session_id        UUID REFERENCES sessions(id),
  error             TEXT,
  started_at        TIMESTAMPTZ,
  ended_at          TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (agent_id, idempotency_key)
);

CREATE TABLE tools (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id             UUID NOT NULL REFERENCES tenants(id),
  name                  TEXT NOT NULL,
  description           TEXT NOT NULL,
  endpoint              TEXT NOT NULL,
  method                TEXT NOT NULL CHECK (method IN ('GET', 'POST', 'PUT', 'DELETE')),
  auth_type             TEXT NOT NULL CHECK (auth_type IN ('api_key', 'oauth', 'none')),
  auth_secret_path      TEXT,        -- path in Secrets Manager; not the credential itself
  input_schema          JSONB NOT NULL,
  side_effects          TEXT,        -- NULL means read-only
  requires_confirmation BOOLEAN NOT NULL DEFAULT false,
  timeout_ms            INTEGER NOT NULL,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, name)
);

CREATE TABLE folders (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL REFERENCES tenants(id),
  name        TEXT NOT NULL,
  slug        TEXT NOT NULL,
  tier        INTEGER NOT NULL CHECK (tier IN (1, 2)),
  index_url   TEXT,
  doc_count   INTEGER NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, slug)
);

CREATE TABLE documents (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  folder_id    UUID NOT NULL REFERENCES folders(id),
  filename     TEXT NOT NULL,
  storage_url  TEXT NOT NULL,
  summary      TEXT,
  metadata     JSONB NOT NULL DEFAULT '{}',
  uploaded_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Append-only. Never updated, never deleted.
CREATE TABLE usage_events (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     UUID NOT NULL REFERENCES tenants(id),
  session_id    UUID NOT NULL REFERENCES sessions(id),
  user_id       UUID NOT NULL REFERENCES users(id),
  agent_id      UUID REFERENCES agents(id),
  model_id      TEXT NOT NULL,
  input_tokens  INTEGER NOT NULL,
  output_tokens INTEGER NOT NULL,
  tool_calls    JSONB NOT NULL DEFAULT '[]',
  ts            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Append-only. Never updated, never deleted.
CREATE TABLE audit_log (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id   UUID NOT NULL REFERENCES tenants(id),
  session_id  UUID REFERENCES sessions(id),
  agent_id    UUID REFERENCES agents(id),
  user_id     UUID REFERENCES users(id),
  event_type  TEXT NOT NULL,
  payload     JSONB NOT NULL,
  ts          TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

### 5.2 Object Storage Layout

```
s3://{bucket}/
  tenants/{tenant_id}/
    folders/{folder_id}/
      index.json
      docs/{document_id}
    recordings/
      {year}/{month}/{day}/
        {session_id}.json
```

### 5.3 Session Recording Format

Written by the `SessionRecorder` hook at session end. The `recording_url` column in `sessions` points to this file.

```json
{
  "session_id": "...",
  "tenant_id":  "...",
  "user_id":    "...",
  "agent_id":   "...",
  "model_id":   "...",
  "started_at": "...",
  "ended_at":   "...",
  "messages":   [...],
  "tool_calls": [
    {
      "id":        "...",
      "tool_name": "...",
      "input":     {},
      "result":    {},
      "is_error":  false,
      "called_at": "..."
    }
  ],
  "token_usage": { "input": 0, "output": 0 }
}
```

### 5.4 Session Retention

`tenants.recording_retention_days` drives an S3 lifecycle rule created by the IaC for that tenant's recordings prefix. No custom deletion code. If the value is null, recordings are kept indefinitely.

```python
# constants.py
RECORDING_RETENTION_MIN_DAYS = 1
RECORDING_RETENTION_MAX_DAYS = 3650
```

---

## 6. Security and Compliance

### 6.1 Tenant Isolation

Each deployment is a separate AWS account or VPC. There is no shared compute, database, or storage between tenants. Network egress from one tenant cannot reach another tenant's resources.

### 6.2 Secrets

Tool credentials, SSO config, and API keys live in AWS Secrets Manager. They are never stored in the database, in environment variables, or in source code. The ECS task role has read access only to its own tenant's secrets path. Headless agent task roles are scoped further to only the secrets referenced by that agent's tools.

### 6.3 Encryption

All data at rest is encrypted (S3 SSE-S3, RDS encryption enabled). All data in transit uses TLS. Encryption keys are AWS-managed by default; bring-your-own-key (KMS CMK) is a configuration option in the IaC.

### 6.4 Admin Action Logging

All admin actions (user role changes, tool registration, agent creation/deletion, folder management, tenant config changes) are written to `audit_log` with the acting `user_id`. Admin actions are a distinct `event_type` from orchestrator events. This table is append-only and cannot be modified through the application.

### 6.5 Tool Egress Controls

Tool endpoints are registered with explicit URLs. The platform does not allow wildcard endpoints or dynamic URL construction from user input. An admin must register each endpoint explicitly. This limits the blast radius of a compromised or misbehaving agent.

### 6.6 PII Handling

Session recordings contain conversation content which may include PII. Tenants are responsible for their retention configuration. The platform provides the retention mechanism (S3 lifecycle rules) and makes the configuration visible in the admin UI. The platform does not scan or redact PII — that is out of scope.

### 6.7 Authentication

SSO via Authlib (OIDC/SAML). Sessions use signed, server-side tokens (not JWT stored in localStorage). Token expiry is configurable per tenant. No magic token values — expiry is explicit in `constants.py` as `SESSION_TOKEN_EXPIRY_SECONDS`.

---

## 7. Routes

All authenticated routes resolve the tenant from the session token. Admin routes additionally assert `role = 'admin'`.

### UI routes (return HTML)

```
GET  /                        Redirect to /chat or /login
GET  /login                   SSO login page
GET  /auth/callback           SSO callback
GET  /chat                    Main chat interface
GET  /chat/<session_id>       Resume a session
GET  /admin                   Admin dashboard
GET  /admin/users             User management
GET  /admin/agents            Agent list
GET  /admin/tools             Tool registration
GET  /admin/folders           Folder management
GET  /admin/usage             Usage and cost view
GET  /admin/audit             Audit log view
```

### API routes (return JSON or SSE)

```
POST   /api/sessions                      Create session
DELETE /api/sessions/<id>                 End session
POST   /api/sessions/<id>/chat            Send message — SSE stream
POST   /api/sessions/<id>/cancel          Cancel in-progress stream
POST   /api/sessions/<id>/files           Attach ad hoc file
POST   /api/sessions/<id>/folders         Include folder

POST   /api/agents                        Create agent
PUT    /api/agents/<id>                   Update agent
DELETE /api/agents/<id>                   Delete agent
POST   /api/agents/<id>/run               Trigger headless run — returns 202

POST   /api/tools                         Register tool
PUT    /api/tools/<id>                    Update tool
DELETE /api/tools/<id>                    Remove tool
POST   /api/tools/<id>/test               Run eval harness

POST   /api/folders                       Create folder
POST   /api/folders/<id>/upload           Upload document
POST   /api/folders/<id>/reindex          Rebuild index

GET    /api/admin/recordings/<session_id> Retrieve session recording URL
GET    /api/admin/runs/<run_id>           Headless agent run status
```

---

## 8. Deployment

### 8.1 Model

**Single-tenant per deployment.** Each client gets their own isolated deployment. No shared infrastructure between clients.

*Known operational ceiling:* At 15–20 clients, running `terraform apply` per client becomes a bottleneck. A provisioning API and control plane are the solution. That is a Phase 3 problem. The IaC is designed to make that migration straightforward — each deployment is already a self-contained module.

### 8.2 Services

```
Flask app    ECS Fargate   UI and API
Postgres     RDS           primary database
S3           AWS S3        documents, indexes, recordings
Langfuse     ECS Fargate   LLM tracing (async, not in request path)
Job runner   ECS tasks     headless agent runs (discrete tasks, not always-on)
```

### 8.3 Scaling

**Flask app:** Stateless. ECS auto-scaling on ALB request count. SSE connections are long-lived — scale on active connection count, not CPU alone.

**Postgres:** Vertical first. `db.t3.medium` for most clients. Read replica only when analytics queries compete with live traffic.

**S3:** Automatic.

**Langfuse:** Single task. Not in the user request path. Receives async writes from hooks.

**Job runner:** Each headless run is a discrete ECS task. No always-on process.

### 8.4 Infrastructure as Code

Terraform. One module per component. One root module per client.

```
/infra
  /modules
    /networking     VPC, subnets, security groups, ALB
    /ecs-service    Task definition, ECS service, auto-scaling
    /rds            Postgres instance, backups, parameter group
    /s3             Bucket, lifecycle rules, encryption, versioning
    /langfuse       Langfuse ECS service + dedicated RDS
    /iam            Task roles scoped per service, Secrets Manager policies
    /eventbridge    Scheduled rules for headless agent crons
  /deployments
    /acme-corp
    /state-university
  /shared
    /ecr            Container registries
```

Secrets live in AWS Secrets Manager. The ECS task role reads only its tenant's path. Headless agent task roles are scoped to the specific secret paths for that agent's tools.

```hcl
# deployments/acme-corp/main.tf
module "app" {
  source    = "../../modules/ecs-service"
  tenant_slug   = "acme-corp"
  image_uri     = var.image_uri
  cpu           = 512
  memory        = 1024
  min_tasks     = 1
  max_tasks     = 10
}

module "db" {
  source         = "../../modules/rds"
  tenant_slug    = "acme-corp"
  instance_class = "db.t3.medium"
}

module "storage" {
  source                   = "../../modules/s3"
  tenant_slug              = "acme-corp"
  recording_retention_days = 365
}
```

### 8.5 CI/CD

**App pipeline** — on every push to `main`:
1. `pytest --cov` — fail on any test failure or coverage regression on critical paths
2. Build Docker image
3. Push to ECR
4. Rolling deploy to ECS

**Infra pipeline** — on changes to `/infra`:
1. `terraform fmt` check
2. `terraform validate`
3. `terraform plan` — posted as PR comment
4. `terraform apply` on merge (manual approval for production)

---

## 9. Testing

### 9.1 Mandate

Tests cover behaviour on critical paths. The CI pipeline enforces coverage on: orchestrator module, model router, tool executor, all hooks, all API routes. Coverage on these is a hard gate. Coverage elsewhere is tracked but not gated — utility functions, config loading, and template rendering do not need line-for-line tests, they need to be exercised by integration tests.

Quality over quantity: a test that hits a line without asserting a meaningful outcome does not count. Code review checks for this.

### 9.2 Structure

```
/tests
  /unit
    test_orchestrator.py       loop, budget enforcement, cancellation, hooks
    test_model_router.py       adapter correctness per model
    test_context_builder.py    assembly, token budget, doc injection
    test_document_index.py     tier 1 injection, tier 2 index build and query
    test_tool_executor.py      schema validation, auth resolution, timeout,
                               expected vs unexpected failure classification
    test_hooks.py              each hook, async dispatch, hook failure isolation
    test_session_recorder.py   recording format, S3 path, retention config
  /integration
    test_routes_chat.py        full session lifecycle via HTTP
    test_routes_agents.py      interactive and headless trigger
    test_routes_folders.py     upload, index build, query
    test_routes_tools.py       register, schema validation, invoke, eval harness
    test_routes_auth.py        SSO flow, token expiry, RBAC enforcement
    test_routes_admin.py       usage, audit log, recordings, run history
  /eval
    test_tool_harness.py       model invokes correct tool for given prompt
    /agent_evals               expected tool call sequences per agent
```

### 9.3 Orchestrator Tests

- Single response, no tool calls — completes in one pass
- Response with one tool call — executed, result fed back, completes
- Sequential tool calls — loop runs N times correctly
- `requires_confirmation: true` in headless session — `proceed=False`, halted result appended
- Tool returns expected error (4xx) — `ToolResult.error()` appended, loop continues
- Tool raises unexpected exception — propagates out of orchestrator
- Model router raises — propagates
- Token budget exceeded — `compact_context` called, result within `MAX_CONTEXT_TOKENS`
- Tool call count exceeds `MAX_TOOL_CALLS_PER_SESSION` — `OrchestratorBudgetError` raised
- Session cancelled mid-loop — exits cleanly without processing further tool calls
- Hook failure — logged, does not affect session outcome

### 9.4 Eval Harness

```python
@dataclass
class ToolEval:
    tool:               ToolDefinition
    prompt:             str
    expected_tool_name: str
    expected_params:    dict | None = None
```

Runs in CI against `EVAL_MODEL` (defined in `constants.py`). Asserts correct tool called, parameters match schema, `expected_params` match if provided.

### 9.5 Error Handling in Tests

```python
# WRONG — error was silently swallowed
def test_tool_failure():
    mock_tool.side_effect = Exception("timeout")
    result = orchestrator.run(session)
    assert result.status == "completed"

# RIGHT — asserts on what the error became
def test_expected_tool_failure_appended_to_context():
    mock_executor.call.return_value = ToolResult.error(408, "Request timeout")
    result = orchestrator.run(session)
    tool_result = next(r for r in result.tool_results if r.tool_call_id == "call_1")
    assert tool_result.is_error is True
    assert "408" in tool_result.content

def test_unexpected_tool_failure_propagates():
    mock_executor.call.side_effect = RuntimeError("Segfault in tool adapter")
    with pytest.raises(RuntimeError, match="Segfault"):
        orchestrator.run(session)
```

---

## 10. Engineering Standards

### 10.1 Error Handling

Two categories, two treatments:

**Unexpected failures** — bugs, unhandled states, config errors. Let them propagate. Do not catch. The Flask error handler catches at the boundary, logs the full trace, and returns a structured HTTP error.

**Expected operational failures** — tool timeouts, transient network errors, 4xx responses from external APIs. Handle explicitly and locally. Return a typed result, not an exception. The caller knows what to do with it.

```python
# Expected failure — return a typed result
def call(self, tool_call: ToolCall) -> ToolResult:
    response = http.post(tool.endpoint, timeout=tool.timeout_ms / 1000, ...)
    if response.status_code in TOOL_EXPECTED_ERROR_CODES:
        return ToolResult.error(response.status_code, response.text)
    response.raise_for_status()   # unexpected — propagates
    return ToolResult.success(response.json())

# Unexpected failure — let it propagate
def fetch_document(doc_id: str) -> Document:
    return storage.get(doc_id)    # raises StorageError — caller propagates or Flask catches
```

```python
# Flask boundary — the one place we catch broadly
@app.errorhandler(Exception)
def handle_exception(e: Exception):
    app.logger.exception("Unhandled exception")
    return {"error": "An unexpected error occurred"}, 500
```

### 10.2 No Magic Values

```python
# constants.py
class SupportedModel(str, Enum):
    CLAUDE_SONNET = "claude-sonnet-4-6"
    GPT_4O        = "gpt-4o"
    GEMINI_PRO    = "gemini-1.5-pro"

FOLDER_TIER2_THRESHOLD        = 50       # docs
FOLDER_TIER1_MAX_TOKENS       = 180_000  # tokens
MAX_CONTEXT_TOKENS            = 190_000  # tokens
MAX_TOOL_CALLS_PER_SESSION    = 20
HEADLESS_RUN_TIMEOUT_SECONDS  = 3600
SESSION_TOKEN_EXPIRY_SECONDS  = 86_400
TOOL_EXPECTED_ERROR_CODES     = {400, 401, 403, 404, 408, 422, 429}
RECORDING_RETENTION_MIN_DAYS  = 1
RECORDING_RETENTION_MAX_DAYS  = 3650
EVAL_MODEL                    = SupportedModel.CLAUDE_SONNET
```

### 10.3 No Unnecessary Fallbacks

Validate all required environment variables at startup. The app does not start in a partially-configured state.

```python
# config.py — runs at import time
REQUIRED_ENV_VARS = [
    "DATABASE_URL",
    "S3_BUCKET",
    "AWS_REGION",
    "TOOL_TIMEOUT_MS",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "AUTH_CLIENT_ID",
    "AUTH_CLIENT_SECRET",
    "SECRET_KEY",
]

missing = [v for v in REQUIRED_ENV_VARS if v not in os.environ]
if missing:
    raise EnvironmentError(f"Required environment variables not set: {missing}")
```

### 10.4 Explicit Over Implicit

Behaviour is visible at the call site. No metaclass magic, no decorator-driven side effects that are not obvious from reading the function, no hidden framework wiring.

### 10.5 Simple Code

No premature generalisation. A new developer should be able to follow a request from HTTP entry point to model response by reading the code linearly. Abstractions earn their place when they are used in more than one place or when they isolate a genuinely complex boundary.

---

## 11. Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Web framework | Flask | Simple, explicit. UI and API in one process. |
| Templates | Jinja2 | Ships with Flask. One template per page. |
| Styles | Tailwind CSS + DaisyUI (CDN) | No build step. Theme switching via `data-theme`. |
| UI interactivity | HTMX (CDN) | Zero JS for all non-streaming interactions. |
| Streaming | Vanilla JS `EventSource` (~30 lines) | One file, native browser API. |
| Language | Python 3.12 | One language across the entire codebase. |
| Database | PostgreSQL via psycopg (v3) | Direct SQL, no ORM. Readable and testable. |
| Migrations | Alembic | Explicit, version-controlled schema changes. |
| Object storage | boto3 (S3-compatible) | Documents, indexes, session recordings. |
| LLM tracing | Langfuse (self-hosted, async) | Full trace per model call. Not in request path. |
| Auth | Authlib (OIDC / SAML) | Azure AD, Google Workspace, generic SAML. |
| Secrets | AWS Secrets Manager | No credentials in code, env vars, or DB. |
| Testing | pytest + pytest-flask | Standard, well-understood, good fixture model. |
| IaC | Terraform | One module per component, one root per client. |
| CI/CD | GitHub Actions | Test gate, Docker build, ECS deploy. |

---

## 12. Build Order

### Phase 1 — Closeable demo (4–6 weeks)

1. Flask app scaffold — startup env validation, error handlers, structured logging
2. Postgres schema + Alembic migrations (including `messages` table)
3. SSO login via Authlib
4. Per-tenant branding — DaisyUI theme from DB config
5. Orchestrator core loop — budget enforcement, cancellation support
6. Model router — Claude + GPT-4o adapters
7. Chat UI — Jinja2, HTMX, SSE stream, cancel button
8. Agents as `.md` files — interactive mode only
9. Ad hoc file attach — Tier 1 context injection
10. Session recording — `SessionRecorder` hook (async), S3 write, retention config
11. Admin dashboard — users, usage, cost by model
12. Full tests for all of the above

### Phase 2 — Depth (6–12 weeks)

13. Shared folders — Tier 2 index build and query
14. Tool registration — schema validation, Secrets Manager auth resolution
15. Connector framework — Google Drive first
16. RBAC — teams and per-agent audience
17. Eval harness for tools
18. Headless agents — ECS task dispatch, run state, deduplication, failure watchdog
19. Write-back tools + `ConfirmationGate` hook (async alert dispatch)

### Phase 3 — Enterprise (ongoing)

20. Additional connectors (SharePoint, Slack, Zendesk)
21. Tier 3 document handling (Postgres full-text search)
22. Audit log export
23. Agent run history and failure alerting UI
24. Multi-model eval comparisons
25. Recording playback in admin UI
26. Provisioning API + control plane (unlocks scaling past ~15 clients)

---

## 13. Out of Scope

Explicitly out of scope until a client pays for them:

- Vector database or RAG pipeline
- Self-hosted LLM inference
- Native mobile apps (the web app is mobile-responsive)
- Fine-tuning pipeline
- Multi-tenant shared infrastructure
- Real-time collaboration on sessions
- Agent-to-agent orchestration
- PII scanning or redaction

If any of these appear in a PR without a linked client requirement, the PR is rejected.

---

## 14. Known Debts and Open Questions

These are acknowledged trade-offs, not oversights.

| Item | Nature | Resolution path |
|---|---|---|
| Single-tenant IaC per client | Operational burden grows past ~15 clients | Phase 3: provisioning API |
| Retrieval limited to document-level selection | Underperforms on heterogeneous / large corpora | Phase 3: Tier 3 (FTS), then retrieval layer if needed |
| No PII scanning | Recordings may contain sensitive data | Tenant's responsibility via retention config; scanning is out of scope |
| Context compaction is basic | Summarisation quality affects long session coherence | Revisit if clients report quality issues on long sessions |
| Headless agent secrets scoping is per-agent | Fine-grained but requires IaC change per new agent tool | Acceptable for now; automate in Phase 3 |
