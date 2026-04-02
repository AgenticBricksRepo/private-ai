"""UsageLogger hook — async write to usage_events on SESSION_END."""

import logging

logger = logging.getLogger(__name__)


class UsageLogger:
    def __init__(self, db_pool):
        self.db_pool = db_pool

    def run(self, ctx=None, **kwargs):
        if not ctx:
            return

        try:
            with self.db_pool.connection() as conn:
                from app.db.usage import record_usage
                record_usage(
                    conn,
                    tenant_id=ctx.tenant_id,
                    session_id=ctx.session_id,
                    user_id=ctx.user_id,
                    model_id=ctx.model_id,
                    input_tokens=ctx.input_tokens_total,
                    output_tokens=ctx.output_tokens_total,
                    agent_id=ctx.agent_id,
                    tool_calls=ctx.tool_calls_log,
                )
                conn.commit()
        except Exception:
            logger.exception("UsageLogger: failed to record usage")
