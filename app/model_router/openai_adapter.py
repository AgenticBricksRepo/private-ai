"""OpenAI GPT adapter using the openai Python SDK."""

import json
import logging

import openai

from app.model_router.base import ModelAdapter, ModelResponse, ToolCallRequest

logger = logging.getLogger(__name__)


class OpenAIAdapter(ModelAdapter):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model

    def stream(self, messages, tools=None, images=None):
        # Convert messages to OpenAI format
        api_messages = []
        for m in messages:
            if m["role"] == "tool":
                api_messages.append({
                    "role": "tool",
                    "tool_call_id": m.get("tool_call_id", ""),
                    "content": m["content"],
                })
            else:
                api_messages.append({"role": m["role"], "content": m["content"]})

        # Attach images to the last user message as multimodal content
        if images and api_messages:
            last_user_idx = None
            for i in range(len(api_messages) - 1, -1, -1):
                if api_messages[i]["role"] == "user":
                    last_user_idx = i
                    break
            if last_user_idx is not None:
                text_content = api_messages[last_user_idx]["content"]
                content_parts = []
                for img in images:
                    content_parts.append({
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{img['media_type']};base64,{img['base64']}",
                        },
                    })
                content_parts.append({"type": "text", "text": text_content})
                api_messages[last_user_idx]["content"] = content_parts

        # Convert tools to OpenAI function calling format
        api_tools = None
        if tools:
            api_tools = []
            for t in tools:
                api_tools.append({
                    "type": "function",
                    "function": {
                        "name": t["name"],
                        "description": t.get("description", ""),
                        "parameters": t.get("input_schema", {"type": "object"}),
                    },
                })

        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if api_tools:
            kwargs["tools"] = api_tools

        response_stream = self.client.chat.completions.create(**kwargs)

        accumulated_content = ""
        accumulated_tool_calls: dict[int, dict] = {}
        usage = None

        for chunk in response_stream:
            if chunk.usage:
                usage = chunk.usage

            if not chunk.choices:
                continue

            delta = chunk.choices[0].delta

            if delta and delta.content:
                accumulated_content += delta.content
                yield delta.content

            if delta and delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in accumulated_tool_calls:
                        accumulated_tool_calls[idx] = {
                            "id": tc.id or "",
                            "name": tc.function.name if tc.function and tc.function.name else "",
                            "args_str": "",
                        }
                    if tc.id:
                        accumulated_tool_calls[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        accumulated_tool_calls[idx]["name"] = tc.function.name
                    if tc.function and tc.function.arguments:
                        accumulated_tool_calls[idx]["args_str"] += tc.function.arguments

        tool_calls = []
        for tc_data in accumulated_tool_calls.values():
            try:
                args = json.loads(tc_data["args_str"]) if tc_data["args_str"] else {}
            except json.JSONDecodeError:
                args = {}
            tool_calls.append(
                ToolCallRequest(id=tc_data["id"], name=tc_data["name"], args=args)
            )

        return ModelResponse(
            content=accumulated_content,
            tool_calls=tool_calls,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )
