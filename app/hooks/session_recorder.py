"""SessionRecorder hook — async write session recording to S3 on SESSION_END."""

import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class SessionRecorder:
    def __init__(self, s3_client):
        self.s3 = s3_client

    def run(self, ctx=None, **kwargs):
        if not ctx:
            return

        try:
            now = datetime.now(timezone.utc)
            recording = {
                "session_id": ctx.session_id,
                "tenant_id": ctx.tenant_id,
                "user_id": ctx.user_id,
                "agent_id": ctx.agent_id,
                "model_id": ctx.model_id,
                "started_at": now.isoformat(),
                "ended_at": now.isoformat(),
                "messages": [
                    {"role": m["role"], "content": m["content"]}
                    for m in ctx.messages if m["role"] != "system"
                ],
                "tool_calls": ctx.tool_calls_log,
                "token_usage": {
                    "input": ctx.input_tokens_total,
                    "output": ctx.output_tokens_total,
                },
            }

            key = (
                f"tenants/{ctx.tenant_id}/recordings/"
                f"{now.year}/{now.month:02d}/{now.day:02d}/"
                f"{ctx.session_id}.json"
            )

            self.s3.upload(key, json.dumps(recording, default=str))
            logger.info("Session recording saved: %s", key)
        except Exception:
            logger.exception("SessionRecorder: failed to save recording")
