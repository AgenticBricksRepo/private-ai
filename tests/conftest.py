"""Root test fixtures."""

import json
import os
import uuid

import psycopg
import pytest

# Set test environment before importing app
os.environ.update({
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL", "postgresql://private_ai:private_ai@localhost:5432/private_ai"),
    "S3_BUCKET": "private-ai",
    "S3_ENDPOINT_URL": "http://localhost:9000",
    "AWS_REGION": "us-east-1",
    "AWS_ACCESS_KEY_ID": "minioadmin",
    "AWS_SECRET_ACCESS_KEY": "minioadmin",
    "SECRET_KEY": "test-secret-key",
    "AUTH_MODE": "dev",
    "ANTHROPIC_API_KEY": "test-key",
    "OPENAI_API_KEY": "test-key",
})


@pytest.fixture(scope="session")
def app():
    from app import create_app
    app = create_app(testing=True)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_conn():
    """Direct DB connection for test setup/assertions."""
    url = os.environ.get("DATABASE_URL", "postgresql://private_ai:private_ai@localhost:5432/private_ai")
    conn = psycopg.connect(url)
    yield conn
    conn.rollback()
    conn.close()


@pytest.fixture
def test_tenant(db_conn):
    """Get or create the dev tenant."""
    row = db_conn.execute("SELECT id, name, slug, theme FROM tenants WHERE slug = 'dev'").fetchone()
    if row:
        return {"id": row[0], "name": row[1], "slug": row[2], "theme": row[3]}
    row = db_conn.execute(
        "INSERT INTO tenants (name, slug, theme) VALUES (%s, %s, %s::jsonb) RETURNING id, name, slug, theme",
        ("Test Corp", "dev", json.dumps({"name": "dark"})),
    ).fetchone()
    db_conn.commit()
    return {"id": row[0], "name": row[1], "slug": row[2], "theme": row[3]}


@pytest.fixture
def test_user(db_conn, test_tenant):
    """Get or create the dev admin user."""
    row = db_conn.execute(
        "SELECT id, tenant_id, email, role FROM users WHERE tenant_id = %s AND email = 'dev@localhost'",
        (str(test_tenant["id"]),),
    ).fetchone()
    if row:
        return {"id": row[0], "tenant_id": row[1], "email": row[2], "role": row[3]}
    row = db_conn.execute(
        "INSERT INTO users (tenant_id, email, role) VALUES (%s, %s, %s) RETURNING id, tenant_id, email, role",
        (str(test_tenant["id"]), "dev@localhost", "admin"),
    ).fetchone()
    db_conn.commit()
    return {"id": row[0], "tenant_id": row[1], "email": row[2], "role": row[3]}


@pytest.fixture
def auth_client(client, test_user, test_tenant):
    """Flask test client with an authenticated session."""
    with client.session_transaction() as sess:
        sess["user_id"] = str(test_user["id"])
        sess["tenant_id"] = str(test_tenant["id"])
    return client
