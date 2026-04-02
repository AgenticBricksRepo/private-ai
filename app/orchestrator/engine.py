"""Orchestrator core loop — the engine that drives all chat."""

import json
import logging

from app.constants import MAX_CONTEXT_TOKENS, MAX_TOOL_CALLS_PER_SESSION
from app.errors import OrchestratorBudgetError
from app.orchestrator.context import compact_context
from app.orchestrator.models import HookPoint, SessionContext, ToolResult

logger = logging.getLogger(__name__)


def run(ctx: SessionContext, model_router, tool_executor, hook_runner):
    """Generator that yields SSE-formatted strings.

    The caller iterates this and streams each chunk to the client.
    """
    hook_runner.run(HookPoint.SESSION_START, ctx=ctx)
    tool_call_count = 0

    while True:
        # Budget check — compact if needed
        if ctx.token_count >= MAX_CONTEXT_TOKENS:
            ctx = compact_context(ctx)

        # Stream model response (pass attached images if any)
        images = [f for f in ctx.attached_files if f.get("type") == "image"]
        gen = model_router.stream(ctx.model_id, ctx.messages, ctx.tools, images=images)
        response = None
        accumulated_text = ""

        try:
            while True:
                chunk = next(gen)
                accumulated_text += chunk
                yield f"data: {json.dumps({'type': 'text', 'content': chunk})}\n\n"
        except StopIteration as e:
            response = e.value

        if response is None:
            logger.error("Model returned no response")
            yield f"data: {json.dumps({'type': 'error', 'message': 'Model returned no response'})}\n\n"
            break

        # Update token counts
        ctx.input_tokens_total += response.input_tokens
        ctx.output_tokens_total += response.output_tokens

        # Store assistant message
        if accumulated_text:
            ctx.append_message("assistant", accumulated_text)

        # No tool calls — we're done
        if not response.tool_calls:
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            break

        # Budget check for tool calls
        if tool_call_count + len(response.tool_calls) > MAX_TOOL_CALLS_PER_SESSION:
            error_msg = f"Tool call limit reached: {MAX_TOOL_CALLS_PER_SESSION}"
            yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
            raise OrchestratorBudgetError(error_msg)

        # Process tool calls
        for tc in response.tool_calls:
            if ctx.cancelled:
                yield f"data: {json.dumps({'type': 'cancelled'})}\n\n"
                hook_runner.run(HookPoint.SESSION_END, ctx=ctx)
                return

            # PRE_TOOL hook (gate)
            hook_result = hook_runner.run(HookPoint.PRE_TOOL, ctx=ctx, tool_call=tc)
            if not hook_result.proceed:
                result = ToolResult.halted(tc.id, hook_result.reason or "Blocked by hook")
                ctx.append_tool_result(tc.id, result)
                continue

            # Execute the tool
            yield f"data: {json.dumps({'type': 'tool_call', 'name': tc.name, 'args': tc.args})}\n\n"

            try:
                result = tool_executor.call(tc)
            except Exception as e:
                # Unexpected tool failure — propagate
                logger.exception("Unexpected tool failure: %s", tc.name)
                raise

            # POST_TOOL hook (async, non-blocking)
            hook_runner.run(HookPoint.POST_TOOL, ctx=ctx, tool_call=tc, tool_result=result)

            # Log the tool call
            ctx.tool_calls_log.append({
                "id": tc.id,
                "tool_name": tc.name,
                "input": tc.args,
                "result": result.content,
                "is_error": result.is_error,
            })

            ctx.append_tool_result(tc.id, result)
            tool_call_count += 1

    hook_runner.run(HookPoint.SESSION_END, ctx=ctx)
