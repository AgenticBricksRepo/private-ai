"""E2E tests for admin CRUD operations — agents, tools, folders, audit log."""

import time
import uuid

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

LIVE_SERVER = "http://localhost:5001"


def login(page):
    page.goto(f"{LIVE_SERVER}/login")
    page.locator("[data-testid='login-email']").fill("dev@localhost")
    page.locator("[data-testid='login-submit']").click()
    page.wait_for_url(f"{LIVE_SERVER}/chat")


def test_dashboard_shows_user_email(page):
    """Dashboard sessions table includes the user email column."""
    login(page)
    page.goto(f"{LIVE_SERVER}/admin")
    expect(page.locator("h1")).to_contain_text("Dashboard")
    expect(page.locator("table thead")).to_contain_text("User")


def test_tools_page_shows_demo_tools(page):
    """Tools page shows the seeded echo and weather tools."""
    login(page)
    page.goto(f"{LIVE_SERVER}/admin/tools")
    expect(page.locator("table")).to_contain_text("echo")
    expect(page.locator("table")).to_contain_text("weather")


def test_create_agent_via_dedicated_page(page):
    """Create an agent via the dedicated /admin/agents/new page."""
    login(page)
    unique = uuid.uuid4().hex[:6]

    # Navigate to create page
    page.goto(f"{LIVE_SERVER}/admin/agents/new")
    expect(page.locator("h1")).to_contain_text("Create Agent")

    # Fill the form
    page.locator("input[name='name']").fill(f"E2E Agent {unique}")
    page.locator("input[name='description']").fill("Created by E2E test")
    page.locator("textarea[name='prompt_md']").fill("You are a test agent.")

    # Submit
    page.locator("button:text('Create Agent')").click()
    time.sleep(1)

    # Should redirect back to agents list
    page.goto(f"{LIVE_SERVER}/admin/agents")
    expect(page.locator("table")).to_contain_text(f"E2E Agent {unique}")


def test_edit_agent_via_dedicated_page(page):
    """Edit an agent via the dedicated /admin/agents/<id>/edit page."""
    login(page)
    page.goto(f"{LIVE_SERVER}/admin/agents")

    # Click the first Edit link
    edit_link = page.locator("a:text('Edit')").first
    edit_link.click()

    # Should be on the edit form page
    expect(page.locator("h1")).to_contain_text("Edit Agent")
    expect(page.locator("input[name='name']")).not_to_be_empty()


def test_create_folder_via_dedicated_page(page):
    """Create a folder via the dedicated /admin/folders/new page."""
    login(page)
    unique = uuid.uuid4().hex[:6]

    page.goto(f"{LIVE_SERVER}/admin/folders/new")
    expect(page.locator("h1")).to_contain_text("Create Folder")

    page.locator("input[name='name']").fill(f"KB {unique}")
    page.locator("button:text('Create Folder')").click()
    time.sleep(1)

    page.goto(f"{LIVE_SERVER}/admin/folders")
    expect(page.locator("table")).to_contain_text(f"KB {unique}")


def test_create_tool_via_dedicated_page(page):
    """Register a tool via the dedicated /admin/tools/new page."""
    login(page)
    unique = uuid.uuid4().hex[:6]

    page.goto(f"{LIVE_SERVER}/admin/tools/new")
    expect(page.locator("h1")).to_contain_text("Register Tool")

    page.locator("input[name='name']").fill(f"test_tool_{unique}")
    page.locator("input[name='endpoint']").fill("https://httpbin.org/post")
    page.locator("input[name='description']").fill("A test tool")
    page.locator("button:text('Register Tool')").click()
    time.sleep(1)

    page.goto(f"{LIVE_SERVER}/admin/tools")
    expect(page.locator("table")).to_contain_text(f"test_tool_{unique}")


def test_audit_log_has_entries(page):
    """After CRUD operations, audit log should have entries."""
    login(page)
    page.goto(f"{LIVE_SERVER}/admin/audit")
    expect(page.locator("h1")).to_contain_text("Audit Log")
    rows = page.locator("table tbody tr")
    expect(rows.first).to_be_visible()
