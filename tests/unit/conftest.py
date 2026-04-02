"""Unit test fixtures — mocks, no I/O."""

import pytest
from unittest.mock import MagicMock

from app.model_router.base import ModelResponse, ToolCallRequest
from app.orchestrator.models import HookResult


@pytest.fixture
def mock_model_router():
    router = MagicMock()

    def simple_response(model_id, messages, tools=None, images=None):
        def gen():
            yield "Hello "
            yield "world!"
            return ModelResponse(content="Hello world!", tool_calls=[], input_tokens=10, output_tokens=5)
        return gen()

    router.stream.side_effect = simple_response
    router.get_default_model.return_value = "claude-sonnet-4-6"
    router.list_models.return_value = ["claude-sonnet-4-6"]
    return router


@pytest.fixture
def mock_tool_executor():
    return MagicMock()


@pytest.fixture
def mock_hook_runner():
    runner = MagicMock()
    runner.run.return_value = HookResult(proceed=True)
    return runner
