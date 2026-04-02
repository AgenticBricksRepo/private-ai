"""Hook runner — dispatches hooks at defined orchestrator points."""

import logging
from concurrent.futures import ThreadPoolExecutor

from app.orchestrator.models import HookPoint, HookResult

logger = logging.getLogger(__name__)


class HookRunner:
    def __init__(self):
        self._hooks: dict[HookPoint, list] = {hp: [] for hp in HookPoint}
        self._executor = ThreadPoolExecutor(max_workers=4)

    def register(self, point: HookPoint, hook, is_gate=False):
        """Register a hook. Gate hooks run synchronously and can block execution."""
        self._hooks[point].append((hook, is_gate))

    def run(self, point: HookPoint, **kwargs) -> HookResult:
        """Run all hooks for a given point.

        Gate hooks run synchronously and can return proceed=False.
        I/O hooks run asynchronously via thread pool.
        """
        result = HookResult(proceed=True)

        for hook, is_gate in self._hooks[point]:
            if is_gate:
                try:
                    result = hook.run(**kwargs)
                    if not result.proceed:
                        return result
                except Exception:
                    logger.exception("Gate hook failed (non-fatal)")
            else:
                self._executor.submit(self._safe_run, hook, **kwargs)

        return result

    def _safe_run(self, hook, **kwargs):
        try:
            hook.run(**kwargs)
        except Exception:
            logger.exception("Async hook failed (non-fatal)")

    def shutdown(self):
        self._executor.shutdown(wait=False)
