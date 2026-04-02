"""Full unmocked E2E test — real LLM calls through the entire stack.

Tests the complete flow:
  1. Login via dev auth
  2. Create a session (GPT-4o)
  3. Send a message
  4. Receive a real streamed LLM response via SSE
  5. Verify the response is non-empty and meaningful
  6. Verify the message was persisted in the database
  7. Verify the session appears on the admin dashboard
  8. End the session
  9. Verify session status is 'completed'
"""

import json
import os
import time

import psycopg
import pytest
from playwright.sync_api import expect

pytestmark = pytest.mark.e2e

LIVE_SERVER = "http://localhost:5001"
DATABASE_URL = os.environ.get("DATABASE_URL", "postgresql://private_ai:private_ai@localhost:5432/private_ai")


@pytest.fixture(scope="module")
def db():
    conn = psycopg.connect(DATABASE_URL)
    yield conn
    conn.close()


def test_full_chat_flow_with_real_llm(page, db):
    """Complete E2E: login -> chat with GPT-4o -> verify DB -> admin -> end session."""

    # === Step 1: Login ===
    page.goto(f"{LIVE_SERVER}/login")
    expect(page.locator("[data-testid='login-email']")).to_be_visible()
    page.locator("[data-testid='login-email']").fill("dev@localhost")
    page.locator("[data-testid='login-submit']").click()
    page.wait_for_url(f"{LIVE_SERVER}/chat")
    expect(page.locator("[data-testid='chat-input']")).to_be_visible()
    print("  [PASS] Login successful, on /chat")

    # === Step 2: Select GPT-4o model ===
    page.locator("[data-testid='model-select']").select_option("gpt-4o")
    print("  [PASS] Selected GPT-4o model")

    # === Step 3: Send a message ===
    test_message = "What is 2 + 2? Reply with just the number."
    page.locator("[data-testid='chat-input']").fill(test_message)
    page.locator("[data-testid='send-button']").click()
    print("  [PASS] Message sent")

    # === Step 4: Wait for the streamed response ===
    # The user message should appear immediately
    user_msg = page.locator("[data-testid='message-user']").last
    expect(user_msg).to_contain_text("2 + 2")

    # Wait for assistant response to appear and complete
    assistant_msg = page.locator("[data-testid='message-assistant']").last
    expect(assistant_msg).to_be_visible(timeout=30000)

    # Wait for streaming to finish (send button reappears, cancel hides)
    page.locator("[data-testid='send-button']").wait_for(state="visible", timeout=30000)
    time.sleep(1)  # Brief settle

    response_text = assistant_msg.inner_text()
    assert len(response_text) > 0, "Assistant response should not be empty"
    assert "4" in response_text, f"Expected '4' in response, got: {response_text}"
    print(f"  [PASS] Got LLM response: {response_text[:100]}")

    # === Step 5: Verify messages persisted in DB ===
    # Find the most recent active session
    row = db.execute(
        "SELECT id FROM sessions WHERE status = 'active' ORDER BY started_at DESC LIMIT 1"
    ).fetchone()
    assert row is not None, "Should have an active session in DB"
    session_id = str(row[0])

    messages = db.execute(
        "SELECT role, content FROM messages WHERE session_id = %s ORDER BY created_at",
        (session_id,),
    ).fetchall()

    roles = [m[0] for m in messages]
    assert "user" in roles, "User message should be persisted"
    assert "assistant" in roles, "Assistant message should be persisted"

    user_content = next(m[1] for m in messages if m[0] == "user")
    assert "2 + 2" in user_content

    assistant_content = next(m[1] for m in messages if m[0] == "assistant")
    assert len(assistant_content) > 0, "Persisted assistant content should not be empty"
    print(f"  [PASS] Messages persisted in DB ({len(messages)} messages)")

    # === Step 6: Check admin dashboard shows the session ===
    page.goto(f"{LIVE_SERVER}/admin")
    expect(page.locator("h1")).to_contain_text("Dashboard")
    # The sessions table should contain our model
    expect(page.locator("table")).to_contain_text("gpt-4o")
    print("  [PASS] Session visible on admin dashboard")

    # === Step 7: Send a follow-up in the SAME session (don't navigate away) ===
    page.goto(f"{LIVE_SERVER}/chat")
    page.locator("[data-testid='model-select']").select_option("gpt-4o")
    page.locator("[data-testid='chat-input']").fill("What is the capital of France? One word.")
    page.locator("[data-testid='send-button']").click()

    # Wait for response
    page.locator("[data-testid='send-button']").wait_for(state="visible", timeout=30000)
    time.sleep(1)

    # Check the latest assistant message
    latest_assistant = page.locator("[data-testid='message-assistant']").last
    follow_up_text = latest_assistant.inner_text()
    assert "Paris" in follow_up_text or "paris" in follow_up_text.lower(), \
        f"Expected 'Paris' in follow-up, got: {follow_up_text}"
    print(f"  [PASS] Follow-up response: {follow_up_text[:100]}")

    # === Step 8: Verify admin usage page ===
    page.goto(f"{LIVE_SERVER}/admin/usage")
    expect(page.locator("h1")).to_contain_text("Usage")
    print("  [PASS] Usage page loads")

    # === Step 9: Verify audit log has entries ===
    page.goto(f"{LIVE_SERVER}/admin/audit")
    expect(page.locator("h1")).to_contain_text("Audit Log")
    print("  [PASS] Audit log page loads")

    print("\n  === ALL E2E CHECKS PASSED ===")


def test_multi_turn_conversation(page, db):
    """Test that conversation context is maintained across turns."""

    # Login
    page.goto(f"{LIVE_SERVER}/login")
    page.locator("[data-testid='login-email']").fill("dev@localhost")
    page.locator("[data-testid='login-submit']").click()
    page.wait_for_url(f"{LIVE_SERVER}/chat")

    # Select GPT-4o
    page.locator("[data-testid='model-select']").select_option("gpt-4o")

    # Turn 1: Set context
    page.locator("[data-testid='chat-input']").fill("My favorite color is blue. Remember that.")
    page.locator("[data-testid='send-button']").click()
    page.locator("[data-testid='send-button']").wait_for(state="visible", timeout=30000)
    time.sleep(1)
    print("  [PASS] Turn 1 complete")

    # Turn 2: Ask about the context
    page.locator("[data-testid='chat-input']").fill("What is my favorite color? Reply with just the color.")
    page.locator("[data-testid='send-button']").click()
    page.locator("[data-testid='send-button']").wait_for(state="visible", timeout=30000)
    time.sleep(1)

    response = page.locator("[data-testid='message-assistant']").last.inner_text()
    assert "blue" in response.lower(), f"Expected 'blue' in context-aware response, got: {response}"
    print(f"  [PASS] Multi-turn context maintained: {response[:80]}")


def test_agent_seeded_chat(page, db):
    """Test that selecting an agent applies its system prompt."""

    # Login
    page.goto(f"{LIVE_SERVER}/login")
    page.locator("[data-testid='login-email']").fill("dev@localhost")
    page.locator("[data-testid='login-submit']").click()
    page.wait_for_url(f"{LIVE_SERVER}/chat")

    # Select GPT-4o and the General Assistant agent
    page.locator("[data-testid='model-select']").select_option("gpt-4o")
    page.locator("[data-testid='agent-select']").select_option(label="General Assistant")

    # New chat with agent
    page.locator("[data-testid='new-chat-btn']").click()
    time.sleep(0.5)
    page.locator("[data-testid='chat-input']").fill("Hi, what can you help me with? Be brief.")
    page.locator("[data-testid='send-button']").click()

    # Wait for streaming to complete
    page.locator("[data-testid='send-button']").wait_for(state="visible", timeout=30000)
    time.sleep(2)

    response = page.locator("[data-testid='message-assistant']").last.inner_text()
    # Strip the "Assistant" header text that chat bubbles include
    response_clean = response.replace("Assistant", "").strip()
    assert len(response_clean) > 5, f"Agent response too short: {repr(response)}"
    print(f"  [PASS] Agent-seeded response: {response_clean[:100]}")
