"""Model adapter abstract base class."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator


@dataclass
class ToolCallRequest:
    id: str
    name: str
    args: dict


@dataclass
class ModelResponse:
    content: str
    tool_calls: list[ToolCallRequest] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0


class ModelAdapter(ABC):
    @abstractmethod
    def stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        images: list[dict] | None = None,
    ) -> Generator[str, None, ModelResponse]:
        """Yield text chunks for SSE. Return ModelResponse when exhausted.

        The generator protocol: iterate to get text deltas, and when
        StopIteration is raised, its .value is the final ModelResponse.

        images: list of {"filename", "type": "image", "media_type", "base64"} dicts.
        """
        ...
