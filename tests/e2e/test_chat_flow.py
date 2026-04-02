"""E2E chat flow tests with Playwright."""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def test_login_and_see_chat(page, live_server):
    """User logs in and sees the chat interface."""
    page.goto(f"{live_server}/login")
    expect(page.locator("[data-testid='login-email']")).to_be_visible()

    page.locator("[data-testid='login-email']").fill("dev@localhost")
    page.locator("[data-testid='login-submit']").click()

    page.wait_for_url(f"{live_server}/chat")
    expect(page.locator("[data-testid='chat-input']")).to_be_visible()
    expect(page.locator("[data-testid='send-button']")).to_be_visible()


def test_unauthenticated_redirects_to_login(page, live_server):
    """Unauthenticated user redirected to /login."""
    page.goto(f"{live_server}/chat")
    page.wait_for_url(f"{live_server}/login")


def test_admin_accessible_after_login(page, live_server):
    """Admin can access dashboard after login."""
    page.goto(f"{live_server}/login")
    page.locator("[data-testid='login-email']").fill("dev@localhost")
    page.locator("[data-testid='login-submit']").click()
    page.wait_for_url(f"{live_server}/chat")

    page.goto(f"{live_server}/admin")
    expect(page.locator("h1")).to_contain_text("Dashboard")
