"""Context builder unit tests."""

import pytest

from app.orchestrator.context import build_context, compact_context
from app.orchestrator.models import SessionContext

pytestmark = pytest.mark.unit


def make_session_data(**overrides):
    defaults = {
        "id": "sess-1", "tenant_id": "t-1", "user_id": "u-1",
        "agent_id": None, "model_id": "claude-sonnet-4-6",
    }
    defaults.update(overrides)
    return defaults


def test_basic_assembly():
    ctx = build_context(make_session_data())
    assert len(ctx.messages) >= 1
    assert ctx.messages[0]["role"] == "system"
    assert ctx.model_id == "claude-sonnet-4-6"


def test_agent_prompt_applied():
    agent_data = {"prompt_md": "You are a financial analyst."}
    ctx = build_context(make_session_data(), agent_data=agent_data)
    assert "financial analyst" in ctx.messages[0]["content"]


def test_message_history_replayed():
    messages = [
        {"role": "user", "content": "Hello", "tool_call": None},
        {"role": "assistant", "content": "Hi there!", "tool_call": None},
    ]
    ctx = build_context(make_session_data(), messages=messages)
    roles = [m["role"] for m in ctx.messages]
    assert "user" in roles
    assert "assistant" in roles


def test_attached_text_files_injected():
    files = [{"filename": "notes.txt", "type": "text", "content": "Important notes here."}]
    ctx = build_context(make_session_data(), attached_files=files)
    all_content = " ".join(m["content"] for m in ctx.messages if isinstance(m.get("content"), str))
    assert "notes.txt" in all_content
    assert "Important notes" in all_content


def test_attached_images_stored_on_context():
    files = [{"filename": "photo.png", "type": "image", "media_type": "image/png", "base64": "abc123"}]
    ctx = build_context(make_session_data(), attached_files=files)
    assert len(ctx.attached_files) == 1
    assert ctx.attached_files[0]["type"] == "image"


def test_compact_context_reduces_messages():
    ctx = SessionContext(
        session_id="s", tenant_id="t", user_id="u",
        agent_id=None, model_id="m",
    )
    ctx.append_message("system", "You are helpful.")
    for i in range(50):
        ctx.append_message("user", f"Message {i} " + "word " * 500)
        ctx.append_message("assistant", f"Response {i} " + "word " * 500)

    # Force high token count
    ctx.token_count = 200_000

    compacted = compact_context(ctx)
    assert len(compacted.messages) < 102  # Less than the original 1 system + 100 msgs
