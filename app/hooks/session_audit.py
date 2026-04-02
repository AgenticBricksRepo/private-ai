"""SessionAudit hook — writes session_started and session_ended to audit_log."""

import logging

logger = logging.getLogger(__name__)


class SessionAudit:
    def __init__(self, db_pool):
        self.db_pool = db_pool

    def run(self, ctx=None, **kwargs):
        if not ctx:
            return
        # Determine event type based on whether session has ended
        event_type = "session_ended" if ctx.output_tokens_total > 0 else "session_started"
        try:
            with self.db_pool.connection() as conn:
                from app.db.audit import write_audit_log
                write_audit_log(
                    conn,
                    tenant_id=ctx.tenant_id,
                    event_type=event_type,
                    payload={
                        "model_id": ctx.model_id,
                        "agent_id": ctx.agent_id,
                        "input_tokens": ctx.input_tokens_total,
                        "output_tokens": ctx.output_tokens_total,
                    },
                    session_id=ctx.session_id,
                    user_id=ctx.user_id,
                )
                conn.commit()
        except Exception:
            logger.exception("SessionAudit: failed to write")
