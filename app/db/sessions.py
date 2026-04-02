"""Session queries."""


def create_session(conn, tenant_id, user_id, model_id, agent_id=None):
    row = conn.execute(
        "INSERT INTO sessions (tenant_id, user_id, agent_id, model_id, status) "
        "VALUES (%s, %s, %s, %s, 'active') "
        "RETURNING id, tenant_id, user_id, agent_id, model_id, status, recording_url, started_at, ended_at",
        (str(tenant_id), str(user_id), str(agent_id) if agent_id else None, model_id),
    ).fetchone()
    return _row_to_dict(row)


def get_session(conn, session_id):
    row = conn.execute(
        "SELECT id, tenant_id, user_id, agent_id, model_id, status, recording_url, started_at, ended_at "
        "FROM sessions WHERE id = %s",
        (str(session_id),),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def end_session(conn, session_id, status="completed", recording_url=None):
    conn.execute(
        "UPDATE sessions SET status = %s, recording_url = %s, ended_at = now() WHERE id = %s",
        (status, recording_url, str(session_id)),
    )


def list_sessions(conn, tenant_id, user_id=None, limit=50):
    base = (
        "SELECT s.id, s.tenant_id, s.user_id, s.agent_id, s.model_id, "
        "s.status, s.recording_url, s.started_at, s.ended_at, u.email as user_email "
        "FROM sessions s JOIN users u ON s.user_id = u.id "
    )
    if user_id:
        rows = conn.execute(
            base + "WHERE s.tenant_id = %s AND s.user_id = %s ORDER BY s.started_at DESC LIMIT %s",
            (str(tenant_id), str(user_id), limit),
        ).fetchall()
    else:
        rows = conn.execute(
            base + "WHERE s.tenant_id = %s ORDER BY s.started_at DESC LIMIT %s",
            (str(tenant_id), limit),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row):
    d = {
        "id": row[0],
        "tenant_id": row[1],
        "user_id": row[2],
        "agent_id": row[3],
        "model_id": row[4],
        "status": row[5],
        "recording_url": row[6],
        "started_at": row[7],
        "ended_at": row[8],
    }
    if len(row) > 9:
        d["user_email"] = row[9]
    return d
