"""Usage event queries. Append-only."""

import json


def record_usage(conn, tenant_id, session_id, user_id, model_id,
                 input_tokens, output_tokens, agent_id=None, tool_calls=None):
    conn.execute(
        "INSERT INTO usage_events (tenant_id, session_id, user_id, agent_id, model_id, "
        "input_tokens, output_tokens, tool_calls) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
        (str(tenant_id), str(session_id), str(user_id),
         str(agent_id) if agent_id else None, model_id,
         input_tokens, output_tokens, json.dumps(tool_calls or [])),
    )


def get_usage_summary(conn, tenant_id, days=30):
    """Get usage summary grouped by model for the last N days."""
    rows = conn.execute(
        "SELECT model_id, COUNT(*) as count, "
        "SUM(input_tokens) as total_input, SUM(output_tokens) as total_output "
        "FROM usage_events WHERE tenant_id = %s AND ts >= now() - interval '%s days' "
        "GROUP BY model_id ORDER BY total_input DESC",
        (str(tenant_id), days),
    ).fetchall()
    return [{"model_id": r[0], "count": r[1], "total_input": r[2], "total_output": r[3]}
            for r in rows]


def get_usage_by_user(conn, tenant_id, days=30):
    """Get usage grouped by user for the last N days."""
    rows = conn.execute(
        "SELECT u.email, COUNT(*) as count, "
        "SUM(ue.input_tokens) as total_input, SUM(ue.output_tokens) as total_output "
        "FROM usage_events ue JOIN users u ON ue.user_id = u.id "
        "WHERE ue.tenant_id = %s AND ue.ts >= now() - interval '%s days' "
        "GROUP BY u.email ORDER BY total_input DESC",
        (str(tenant_id), days),
    ).fetchall()
    return [{"email": r[0], "count": r[1], "total_input": r[2], "total_output": r[3]}
            for r in rows]
