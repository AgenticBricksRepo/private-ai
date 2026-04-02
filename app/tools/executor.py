"""Tool executor — validates, authenticates, calls, and classifies tool responses."""

import logging
import os

import httpx
import jsonschema

from app.constants import TOOL_EXPECTED_ERROR_CODES
from app.errors import SchemaValidationError, ToolNotFoundError
from app.orchestrator.models import ToolResult

logger = logging.getLogger(__name__)


class ToolExecutor:
    def __init__(self, db_pool):
        self.db_pool = db_pool

    def call(self, tool_call, tenant_id=None):
        """Execute a tool call. Returns ToolResult on expected failure, raises on unexpected."""
        with self.db_pool.connection() as conn:
            from app.db.tools import get_tool_by_name
            tool = get_tool_by_name(conn, tenant_id, tool_call.name) if tenant_id else None

        if not tool:
            raise ToolNotFoundError(f"Tool not found: {tool_call.name}")

        # Validate input against schema
        try:
            jsonschema.validate(instance=tool_call.args, schema=tool["input_schema"])
        except jsonschema.ValidationError as e:
            raise SchemaValidationError(f"Schema validation failed for {tool_call.name}: {e.message}")

        # Resolve auth credentials
        headers = {}
        if tool["auth_type"] == "api_key" and tool.get("auth_secret_path"):
            # In Phase 1, resolve from env vars instead of Secrets Manager
            api_key = os.environ.get(tool["auth_secret_path"], "")
            headers["Authorization"] = f"Bearer {api_key}"

        # Call the endpoint
        timeout_s = tool["timeout_ms"] / 1000
        try:
            response = httpx.request(
                method=tool["method"],
                url=tool["endpoint"],
                json=tool_call.args if tool["method"] in ("POST", "PUT") else None,
                params=tool_call.args if tool["method"] == "GET" else None,
                headers=headers,
                timeout=timeout_s,
            )
        except httpx.TimeoutException:
            return ToolResult.error(tool_call.id, 408, "Request timeout")
        except httpx.RequestError as e:
            return ToolResult.error(tool_call.id, 0, f"Connection error: {e}")

        if response.status_code in TOOL_EXPECTED_ERROR_CODES:
            return ToolResult.error(tool_call.id, response.status_code, response.text[:500])

        response.raise_for_status()  # Unexpected — propagates
        return ToolResult.success(tool_call.id, response.json())
