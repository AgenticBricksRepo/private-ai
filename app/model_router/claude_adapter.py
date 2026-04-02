"""Anthropic Claude adapter using the anthropic Python SDK."""

import logging

import anthropic

from app.model_router.base import ModelAdapter, ModelResponse, ToolCallRequest

logger = logging.getLogger(__name__)


class ClaudeAdapter(ModelAdapter):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-6"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def stream(self, messages, tools=None, images=None):
        # Separate system message
        system_msg = None
        api_messages = []
        for m in messages:
            if m["role"] == "system":
                system_msg = m["content"]
            elif m["role"] == "tool":
                api_messages.append({
                    "role": "user",
                    "content": [{
                        "type": "tool_result",
                        "tool_use_id": m.get("tool_call_id", ""),
                        "content": m["content"],
                    }],
                })
            else:
                api_messages.append({"role": m["role"], "content": m["content"]})

        # Attach images to the last user message as multimodal content blocks
        if images and api_messages:
            last_user_idx = None
            for i in range(len(api_messages) - 1, -1, -1):
                if api_messages[i]["role"] == "user":
                    last_user_idx = i
                    break
            if last_user_idx is not None:
                text_content = api_messages[last_user_idx]["content"]
                content_blocks = []
                for img in images:
                    content_blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": img["media_type"],
                            "data": img["base64"],
                        },
                    })
                content_blocks.append({"type": "text", "text": text_content})
                api_messages[last_user_idx]["content"] = content_blocks

        # Convert tools to Anthropic format
        api_tools = []
        if tools:
            for t in tools:
                api_tools.append({
                    "name": t["name"],
                    "description": t.get("description", ""),
                    "input_schema": t.get("input_schema", {"type": "object"}),
                })

        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "max_tokens": 4096,
        }
        if system_msg:
            kwargs["system"] = system_msg
        if api_tools:
            kwargs["tools"] = api_tools

        accumulated_text = ""
        tool_calls = []

        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                if hasattr(event, "type"):
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            accumulated_text += event.delta.text
                            yield event.delta.text

            response = stream.get_final_message()

        for block in response.content:
            if block.type == "tool_use":
                tool_calls.append(
                    ToolCallRequest(id=block.id, name=block.name, args=block.input)
                )

        for block in response.content:
            if block.type == "text" and not accumulated_text:
                accumulated_text = block.text

        return ModelResponse(
            content=accumulated_text,
            tool_calls=tool_calls,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
        )
