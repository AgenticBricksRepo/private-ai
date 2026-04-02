"""Initial schema — all tables from PRD section 5.1.

Revision ID: 001
Revises: None
Create Date: 2026-03-31
"""
from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE tenants (
        id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        name                     TEXT NOT NULL,
        slug                     TEXT NOT NULL UNIQUE,
        logo_url                 TEXT,
        theme                    JSONB NOT NULL DEFAULT '{}',
        sso_config               JSONB NOT NULL DEFAULT '{}',
        recording_retention_days INTEGER,
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

    CREATE TABLE tools (
        id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        tenant_id             UUID NOT NULL REFERENCES tenants(id),
        name                  TEXT NOT NULL,
        description           TEXT NOT NULL,
        endpoint              TEXT NOT NULL,
        method                TEXT NOT NULL CHECK (method IN ('GET', 'POST', 'PUT', 'DELETE')),
        auth_type             TEXT NOT NULL CHECK (auth_type IN ('api_key', 'oauth', 'none')),
        auth_secret_path      TEXT,
        input_schema          JSONB NOT NULL,
        side_effects          TEXT,
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

    CREATE TABLE messages (
        id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        session_id  UUID NOT NULL REFERENCES sessions(id),
        role        TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'tool')),
        content     TEXT NOT NULL,
        tool_call   JSONB,
        created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
    );

    CREATE TABLE agent_runs (
        id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        agent_id          UUID NOT NULL REFERENCES agents(id),
        tenant_id         UUID NOT NULL REFERENCES tenants(id),
        status            TEXT NOT NULL CHECK (status IN ('pending', 'running', 'completed', 'failed')),
        trigger_type      TEXT NOT NULL CHECK (trigger_type IN ('schedule', 'webhook')),
        idempotency_key   TEXT,
        session_id        UUID REFERENCES sessions(id),
        error             TEXT,
        started_at        TIMESTAMPTZ,
        ended_at          TIMESTAMPTZ,
        created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
        UNIQUE (agent_id, idempotency_key)
    );

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

    -- Indexes for common queries
    CREATE INDEX idx_users_tenant ON users(tenant_id);
    CREATE INDEX idx_sessions_tenant ON sessions(tenant_id);
    CREATE INDEX idx_sessions_user ON sessions(user_id);
    CREATE INDEX idx_messages_session ON messages(session_id);
    CREATE INDEX idx_agents_tenant ON agents(tenant_id);
    CREATE INDEX idx_tools_tenant ON tools(tenant_id);
    CREATE INDEX idx_folders_tenant ON folders(tenant_id);
    CREATE INDEX idx_documents_folder ON documents(folder_id);
    CREATE INDEX idx_usage_events_tenant ON usage_events(tenant_id);
    CREATE INDEX idx_usage_events_ts ON usage_events(ts);
    CREATE INDEX idx_audit_log_tenant ON audit_log(tenant_id);
    CREATE INDEX idx_audit_log_ts ON audit_log(ts);
    CREATE INDEX idx_agent_runs_agent ON agent_runs(agent_id);
    """)


def downgrade():
    op.execute("""
    DROP TABLE IF EXISTS audit_log CASCADE;
    DROP TABLE IF EXISTS usage_events CASCADE;
    DROP TABLE IF EXISTS agent_runs CASCADE;
    DROP TABLE IF EXISTS messages CASCADE;
    DROP TABLE IF EXISTS sessions CASCADE;
    DROP TABLE IF EXISTS documents CASCADE;
    DROP TABLE IF EXISTS folders CASCADE;
    DROP TABLE IF EXISTS tools CASCADE;
    DROP TABLE IF EXISTS agents CASCADE;
    DROP TABLE IF EXISTS users CASCADE;
    DROP TABLE IF EXISTS tenants CASCADE;
    """)
