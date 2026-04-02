"""Hook system unit tests."""

import pytest
from unittest.mock import MagicMock

from app.hooks.registry import HookRunner
from app.orchestrator.models import HookPoint, HookResult

pytestmark = pytest.mark.unit


def test_async_hook_dispatched():
    runner = HookRunner()
    hook = MagicMock()
    hook.run.return_value = None
    runner.register(HookPoint.SESSION_END, hook)

    runner.run(HookPoint.SESSION_END, ctx=MagicMock())
    runner._executor.shutdown(wait=True)

    hook.run.assert_called_once()


def test_gate_hook_can_block():
    runner = HookRunner()
    gate = MagicMock()
    gate.run.return_value = HookResult(proceed=False, reason="Blocked")
    runner.register(HookPoint.PRE_TOOL, gate, is_gate=True)

    result = runner.run(HookPoint.PRE_TOOL, ctx=MagicMock())
    assert result.proceed is False
    assert result.reason == "Blocked"


def test_hook_failure_does_not_propagate():
    runner = HookRunner()
    bad_hook = MagicMock()
    bad_hook.run.side_effect = RuntimeError("Crash!")
    runner.register(HookPoint.SESSION_END, bad_hook)

    # Should not raise
    result = runner.run(HookPoint.SESSION_END, ctx=MagicMock())
    runner._executor.shutdown(wait=True)
    assert result.proceed is True


def test_multiple_hooks_all_dispatched():
    runner = HookRunner()
    hooks = [MagicMock() for _ in range(3)]
    for h in hooks:
        h.run.return_value = None
        runner.register(HookPoint.SESSION_END, h)

    runner.run(HookPoint.SESSION_END, ctx=MagicMock())
    runner._executor.shutdown(wait=True)

    for h in hooks:
        h.run.assert_called_once()
