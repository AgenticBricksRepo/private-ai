"""Admin route integration tests."""

import pytest

pytestmark = pytest.mark.integration


def test_usage_page(auth_client):
    resp = auth_client.get("/admin/usage")
    assert resp.status_code == 200
    assert b"Usage" in resp.data


def test_audit_page(auth_client):
    resp = auth_client.get("/admin/audit")
    assert resp.status_code == 200
    assert b"Audit Log" in resp.data


def test_tools_page(auth_client):
    resp = auth_client.get("/admin/tools")
    assert resp.status_code == 200
    assert b"Tools" in resp.data


def test_folders_page(auth_client):
    resp = auth_client.get("/admin/folders")
    assert resp.status_code == 200
    assert b"Folders" in resp.data
