"""E2E tests for round 2 fixes — branding, theme persistence, chat history, audit log."""

import time

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

LIVE_SERVER = "http://localhost:5001"


def login(page):
    page.goto(f"{LIVE_SERVER}/login")
    page.locator("[data-testid='login-email']").fill("dev@localhost")
    page.locator("[data-testid='login-submit']").click()
    page.wait_for_url(f"{LIVE_SERVER}/chat")


def test_branding_update(page):
    """Admin can change the app name and it persists across pages."""
    login(page)
    page.goto(f"{LIVE_SERVER}/admin")

    # Change the app name
    name_input = page.locator("input[name='name']")
    name_input.clear()
    name_input.fill("Acme AI")
    page.locator("button:text('Save Branding')").click()
    time.sleep(1)

    # Navigate to chat — header should show new name
    page.goto(f"{LIVE_SERVER}/chat")
    expect(page.locator(".navbar")).to_contain_text("Acme AI")

    # Reset to original
    page.goto(f"{LIVE_SERVER}/admin")
    name_input = page.locator("input[name='name']")
    name_input.clear()
    name_input.fill("Development")
    page.locator("button:text('Save Branding')").click()
    time.sleep(1)


def test_theme_persists_across_pages(page):
    """Theme change in admin persists when navigating to other pages."""
    login(page)
    page.goto(f"{LIVE_SERVER}/admin")

    # Change theme to "cyberpunk"
    page.locator("#theme-select").select_option("cyberpunk")
    time.sleep(1)

    # Navigate to chat
    page.goto(f"{LIVE_SERVER}/chat")
    theme = page.locator("html").get_attribute("data-theme")
    assert theme == "cyberpunk", f"Expected 'cyberpunk', got '{theme}'"

    # Navigate to admin agents
    page.goto(f"{LIVE_SERVER}/admin/agents")
    theme = page.locator("html").get_attribute("data-theme")
    assert theme == "cyberpunk", f"Expected 'cyberpunk', got '{theme}'"

    # Reset to dark
    page.goto(f"{LIVE_SERVER}/admin")
    page.locator("#theme-select").select_option("dark")
    time.sleep(1)


def test_chat_history_loads(page):
    """Clicking a session in chat history loads it without error."""
    login(page)

    # Send a message to create a session
    page.locator("[data-testid='chat-input']").fill("Hello, test message for history")
    page.locator("[data-testid='send-button']").click()
    page.locator("[data-testid='send-button']").wait_for(state="visible", timeout=30000)
    time.sleep(2)

    # Navigate to fresh /chat — should show session in sidebar
    page.goto(f"{LIVE_SERVER}/chat")
    time.sleep(1)

    # Click the first session in the sidebar
    session_links = page.locator("a[href^='/chat/']")
    if session_links.count() > 0:
        session_links.first.click()
        time.sleep(1)
        # Should NOT be a 500 error — page should load with messages
        assert "500" not in page.content()
        assert "Internal Server Error" not in page.content()
        # Should still show the chat interface
        expect(page.locator("[data-testid='chat-input']")).to_be_visible()


def test_audit_log_detail_expand(page):
    """Audit log rows expand to show full payload detail."""
    login(page)
    page.goto(f"{LIVE_SERVER}/admin/audit")

    # Should have rows
    rows = page.locator("table tbody tr:not(.hidden)")
    expect(rows.first).to_be_visible()

    # Click the first data row to expand detail
    rows.first.click()
    time.sleep(0.5)

    # Detail row should now be visible with payload
    detail = page.locator("pre").first
    expect(detail).to_be_visible()


def test_audit_log_filter_by_event_type(page):
    """Audit log can be filtered by event type."""
    login(page)
    page.goto(f"{LIVE_SERVER}/admin/audit")

    # The event type dropdown should have options
    select = page.locator("select[name='event_type']")
    options = select.locator("option")
    assert options.count() > 1, "Should have event type filter options"

    # Select a specific event type and filter
    select.select_option(index=1)  # First non-empty option
    page.locator("button:text('Filter')").click()
    time.sleep(0.5)

    # URL should have event_type param
    assert "event_type=" in page.url


def test_audit_log_search(page):
    """Audit log can be searched by payload text."""
    login(page)
    page.goto(f"{LIVE_SERVER}/admin/audit")

    search_input = page.locator("input[name='search']")
    search_input.fill("theme")
    page.locator("button:text('Filter')").click()
    time.sleep(0.5)

    assert "search=theme" in page.url
