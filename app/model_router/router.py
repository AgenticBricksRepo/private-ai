"""Model router — dispatches to the correct adapter based on model_id."""

import logging

from app.constants import SupportedModel
from app.model_router.base import ModelAdapter

logger = logging.getLogger(__name__)


class ModelRouter:
    def __init__(self, config):
        self.adapters: dict[str, ModelAdapter] = {}

        if config.get("ANTHROPIC_API_KEY"):
            from app.model_router.claude_adapter import ClaudeAdapter
            self.adapters[SupportedModel.CLAUDE_SONNET] = ClaudeAdapter(
                api_key=config["ANTHROPIC_API_KEY"],
                model=SupportedModel.CLAUDE_SONNET,
            )

        if config.get("OPENAI_API_KEY"):
            from app.model_router.openai_adapter import OpenAIAdapter
            self.adapters[SupportedModel.GPT_4O] = OpenAIAdapter(
                api_key=config["OPENAI_API_KEY"],
                model=SupportedModel.GPT_4O,
            )

        if not self.adapters:
            raise ValueError("No model adapters configured — provide at least one API key")

        self.default_model = next(iter(self.adapters))
        logger.info("Model router initialized with adapters: %s", list(self.adapters.keys()))

    def stream(self, model_id, messages, tools=None, images=None):
        """Stream a model response. Returns a generator yielding text chunks.

        The generator's return value (via StopIteration.value) is a ModelResponse.
        """
        adapter = self.adapters.get(model_id)
        if not adapter:
            raise ValueError(f"Unsupported model: {model_id}. Available: {list(self.adapters.keys())}")
        return adapter.stream(messages, tools, images=images)

    def get_default_model(self):
        return self.default_model

    def list_models(self):
        return list(self.adapters.keys())
