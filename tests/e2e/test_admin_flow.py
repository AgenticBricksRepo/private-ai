"""E2E admin flow tests with Playwright."""

import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e


def login(page, live_server):
    page.goto(f"{live_server}/login")
    page.locator("[data-testid='login-email']").fill("dev@localhost")
    page.locator("[data-testid='login-submit']").click()
    page.wait_for_url(f"{live_server}/chat")


def test_admin_pages_load(page, live_server):
    """All admin pages load without errors."""
    login(page, live_server)

    for path, heading in [
        ("/admin", "Dashboard"),
        ("/admin/users", "Users"),
        ("/admin/agents", "Agents"),
        ("/admin/tools", "Tools"),
        ("/admin/folders", "Folders"),
        ("/admin/usage", "Usage"),
        ("/admin/audit", "Audit Log"),
    ]:
        page.goto(f"{live_server}{path}")
        expect(page.locator("h1")).to_contain_text(heading)
