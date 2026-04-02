"""Audit log queries. Append-only."""

import json


def write_audit_log(conn, tenant_id, event_type, payload,
                    session_id=None, agent_id=None, user_id=None):
    conn.execute(
        "INSERT INTO audit_log (tenant_id, session_id, agent_id, user_id, event_type, payload) "
        "VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
        (str(tenant_id), str(session_id) if session_id else None,
         str(agent_id) if agent_id else None, str(user_id) if user_id else None,
         event_type, json.dumps(payload)),
    )


def list_audit_logs(conn, tenant_id, event_type=None, search=None, limit=100, offset=0):
    conditions = ["a.tenant_id = %s"]
    params = [str(tenant_id)]

    if event_type:
        conditions.append("a.event_type = %s")
        params.append(event_type)
    if search:
        conditions.append("a.payload::text ILIKE %s")
        params.append(f"%{search}%")

    where = " AND ".join(conditions)
    params.extend([limit, offset])

    rows = conn.execute(
        f"SELECT a.id, a.tenant_id, a.session_id, a.agent_id, a.user_id, a.event_type, "
        f"a.payload, a.ts, u.email as user_email "
        f"FROM audit_log a LEFT JOIN users u ON a.user_id = u.id "
        f"WHERE {where} ORDER BY a.ts DESC LIMIT %s OFFSET %s",
        params,
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_audit_logs(conn, tenant_id, event_type=None, search=None):
    conditions = ["tenant_id = %s"]
    params = [str(tenant_id)]

    if event_type:
        conditions.append("event_type = %s")
        params.append(event_type)
    if search:
        conditions.append("payload::text ILIKE %s")
        params.append(f"%{search}%")

    where = " AND ".join(conditions)
    row = conn.execute(
        f"SELECT COUNT(*) FROM audit_log WHERE {where}", params,
    ).fetchone()
    return row[0]


def list_event_types(conn, tenant_id):
    rows = conn.execute(
        "SELECT DISTINCT event_type FROM audit_log WHERE tenant_id = %s ORDER BY event_type",
        (str(tenant_id),),
    ).fetchall()
    return [r[0] for r in rows]


def _row_to_dict(row):
    return {
        "id": row[0], "tenant_id": row[1], "session_id": row[2],
        "agent_id": row[3], "user_id": row[4], "event_type": row[5],
        "payload": row[6], "ts": row[7],
        "user_email": row[8] if len(row) > 8 else None,
    }
