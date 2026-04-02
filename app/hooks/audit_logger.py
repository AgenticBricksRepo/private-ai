"""AuditLogger hook — async write to audit_log on POST_TOOL."""

import logging

logger = logging.getLogger(__name__)


class AuditLogger:
    def __init__(self, db_pool):
        self.db_pool = db_pool

    def run(self, ctx=None, tool_call=None, tool_result=None, **kwargs):
        if not ctx or not tool_call:
            return

        try:
            with self.db_pool.connection() as conn:
                from app.db.audit import write_audit_log
                write_audit_log(
                    conn,
                    tenant_id=ctx.tenant_id,
                    event_type="tool_call",
                    payload={
                        "tool_name": tool_call.name,
                        "tool_args": tool_call.args,
                        "is_error": tool_result.is_error if tool_result else None,
                    },
                    session_id=ctx.session_id,
                    user_id=ctx.user_id,
                    agent_id=ctx.agent_id,
                )
                conn.commit()
        except Exception:
            logger.exception("AuditLogger: failed to write audit log")
