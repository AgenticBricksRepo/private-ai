"""Chat route integration tests."""

import json

import pytest

pytestmark = pytest.mark.integration


def test_chat_page_renders(auth_client):
    resp = auth_client.get("/chat")
    assert resp.status_code == 200
    assert b"Type a message" in resp.data


def test_create_session(auth_client):
    resp = auth_client.post("/api/sessions",
                            data=json.dumps({"model_id": "claude-sonnet-4-6"}),
                            content_type="application/json")
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert "id" in data
    assert data["status"] == "active"


def test_create_session_with_agent(auth_client, db_conn, test_tenant):
    # Get agent id
    row = db_conn.execute(
        "SELECT id FROM agents WHERE tenant_id = %s LIMIT 1",
        (str(test_tenant["id"]),),
    ).fetchone()
    if not row:
        pytest.skip("No agent in DB")
    agent_id = str(row[0])

    resp = auth_client.post("/api/sessions",
                            data=json.dumps({"model_id": "claude-sonnet-4-6", "agent_id": agent_id}),
                            content_type="application/json")
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert data["agent_id"] is not None


def test_end_session(auth_client):
    # Create session first
    resp = auth_client.post("/api/sessions",
                            data=json.dumps({"model_id": "claude-sonnet-4-6"}),
                            content_type="application/json")
    session_id = json.loads(resp.data)["id"]

    # End it
    resp = auth_client.delete(f"/api/sessions/{session_id}")
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["status"] == "completed"


def test_admin_dashboard_accessible(auth_client):
    resp = auth_client.get("/admin")
    assert resp.status_code == 200
    assert b"Dashboard" in resp.data


def test_admin_agents_page(auth_client):
    resp = auth_client.get("/admin/agents")
    assert resp.status_code == 200
    assert b"Agents" in resp.data


def test_admin_users_page(auth_client):
    resp = auth_client.get("/admin/users")
    assert resp.status_code == 200
    assert b"Users" in resp.data
