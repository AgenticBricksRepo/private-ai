"""Agent route integration tests."""

import json
import uuid

import pytest

pytestmark = pytest.mark.integration


def test_create_agent(auth_client):
    unique = uuid.uuid4().hex[:8]
    resp = auth_client.post("/api/agents",
                            data=json.dumps({
                                "name": f"Test Agent {unique}",
                                "slug": f"test-agent-{unique}",
                                "prompt_md": "You are a test agent.",
                                "mode": "interactive",
                            }),
                            content_type="application/json")
    assert resp.status_code == 201
    data = json.loads(resp.data)
    assert "Test Agent" in data["name"]
    assert data["mode"] == "interactive"


def test_delete_agent(auth_client):
    unique = uuid.uuid4().hex[:8]
    # Create first
    resp = auth_client.post("/api/agents",
                            data=json.dumps({
                                "name": f"To Delete {unique}",
                                "slug": f"to-delete-{unique}",
                                "prompt_md": "Delete me.",
                            }),
                            content_type="application/json")
    agent_id = json.loads(resp.data)["id"]

    # Delete
    resp = auth_client.delete(f"/api/agents/{agent_id}")
    assert resp.status_code == 200
