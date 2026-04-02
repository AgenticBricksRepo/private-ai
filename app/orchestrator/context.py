"""Context building and compaction for the orchestrator."""

import logging

from app.orchestrator.models import SessionContext

logger = logging.getLogger(__name__)


def build_context(session_data, agent_data=None, messages=None,
                  tools=None, attached_files=None) -> SessionContext:
    """Build a SessionContext from DB data."""
    ctx = SessionContext(
        session_id=str(session_data["id"]),
        tenant_id=str(session_data["tenant_id"]),
        user_id=str(session_data["user_id"]),
        agent_id=str(session_data["agent_id"]) if session_data.get("agent_id") else None,
        model_id=session_data["model_id"],
        tools=tools or [],
        attached_files=attached_files or [],
    )

    # System prompt
    system_prompt = "You are a helpful assistant."
    if agent_data and agent_data.get("prompt_md"):
        system_prompt = agent_data["prompt_md"]
    ctx.append_message("system", system_prompt)

    # Inject attached files into context
    if attached_files:
        text_files = [f for f in attached_files if f.get("type") == "text"]
        image_files = [f for f in attached_files if f.get("type") == "image"]

        # Text files: inject as system context
        if text_files:
            file_context = "\n\n--- Attached Files ---\n"
            for f in text_files:
                file_context += f"\n### {f['filename']}\n{f['content']}\n"
            ctx.append_message("system", file_context)

        # Images: store on context for the model adapters to handle
        if image_files:
            ctx.attached_files = image_files

    # Replay existing conversation history
    if messages:
        for m in messages:
            ctx.append_message(m["role"], m["content"],
                             tool_call_id=m.get("tool_call", {}).get("tool_call_id") if m.get("tool_call") else None)

    return ctx


def compact_context(ctx: SessionContext) -> SessionContext:
    """Reduce context size by summarizing older messages.

    Keeps the system prompt and last N messages, drops the middle.
    """
    from app.constants import MAX_CONTEXT_TOKENS

    if ctx.token_count < MAX_CONTEXT_TOKENS:
        return ctx

    # Keep system messages and last 10 messages
    system_msgs = [m for m in ctx.messages if m["role"] == "system"]
    recent_msgs = [m for m in ctx.messages if m["role"] != "system"][-10:]

    # Build a summary of dropped messages
    dropped = [m for m in ctx.messages if m["role"] != "system"][:-10]
    if dropped:
        summary = f"[Earlier conversation with {len(dropped)} messages was summarized to save context space.]"
        system_msgs.append({"role": "system", "content": summary})

    ctx.messages = system_msgs + recent_msgs
    ctx._update_token_count()

    logger.info("Context compacted: dropped %d messages, new token count: %d",
                len(dropped), ctx.token_count)
    return ctx
