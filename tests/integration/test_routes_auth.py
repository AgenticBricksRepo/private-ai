"""Auth route integration tests."""

import pytest

pytestmark = pytest.mark.integration


def test_login_page_renders(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert b"Private AI" in resp.data


def test_login_redirects_to_chat(client):
    resp = client.post("/login", data={"email": "dev@localhost"}, follow_redirects=False)
    assert resp.status_code == 302
    assert "/chat" in resp.headers["Location"]


def test_unauthenticated_redirect_to_login(client):
    resp = client.get("/chat", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_admin_requires_auth(client):
    resp = client.get("/admin", follow_redirects=False)
    assert resp.status_code == 302
    assert "/login" in resp.headers["Location"]


def test_logout_clears_session(auth_client):
    resp = auth_client.get("/logout", follow_redirects=False)
    assert resp.status_code == 302
    # After logout, /chat should redirect to login
    resp2 = auth_client.get("/chat", follow_redirects=False)
    assert resp2.status_code == 302
    assert "/login" in resp2.headers["Location"]
