"""Orchestrator data models."""

from dataclasses import dataclass, field
from enum import StrEnum


@dataclass
class ToolResult:
    tool_call_id: str
    content: str
    is_error: bool = False

    @classmethod
    def success(cls, tool_call_id: str, data) -> "ToolResult":
        import json
        content = json.dumps(data) if not isinstance(data, str) else data
        return cls(tool_call_id=tool_call_id, content=content, is_error=False)

    @classmethod
    def error(cls, tool_call_id: str, status_code: int, message: str) -> "ToolResult":
        return cls(tool_call_id=tool_call_id, content=f"Error {status_code}: {message}", is_error=True)

    @classmethod
    def halted(cls, tool_call_id: str, reason: str) -> "ToolResult":
        return cls(tool_call_id=tool_call_id, content=f"Halted: {reason}", is_error=True)


class HookPoint(StrEnum):
    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    SESSION_START = "session_start"
    SESSION_END = "session_end"


@dataclass
class HookResult:
    proceed: bool = True
    reason: str | None = None


@dataclass
class SessionContext:
    """Runtime context for an orchestrator run."""
    session_id: str
    tenant_id: str
    user_id: str
    agent_id: str | None
    model_id: str
    messages: list[dict] = field(default_factory=list)
    tools: list[dict] = field(default_factory=list)
    attached_files: list[dict] = field(default_factory=list)
    token_count: int = 0
    cancelled: bool = False
    input_tokens_total: int = 0
    output_tokens_total: int = 0
    tool_calls_log: list[dict] = field(default_factory=list)

    def append_message(self, role, content, tool_call_id=None):
        msg = {"role": role, "content": content}
        if tool_call_id:
            msg["tool_call_id"] = tool_call_id
        self.messages.append(msg)
        self._update_token_count()

    def append_tool_result(self, tool_call_id, result: ToolResult):
        self.messages.append({
            "role": "tool",
            "content": result.content,
            "tool_call_id": tool_call_id,
        })
        self._update_token_count()

    def _update_token_count(self):
        """Simple word-based token estimation."""
        from app.constants import TOKENS_PER_WORD
        total_words = sum(len(m.get("content", "").split()) for m in self.messages)
        self.token_count = int(total_words * TOKENS_PER_WORD)
