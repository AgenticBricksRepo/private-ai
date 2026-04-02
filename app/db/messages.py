"""Message queries."""

import json


def add_message(conn, session_id, role, content, tool_call=None):
    tool_call_json = json.dumps(tool_call) if tool_call else None
    row = conn.execute(
        "INSERT INTO messages (session_id, role, content, tool_call) "
        "VALUES (%s, %s, %s, %s::jsonb) RETURNING id, session_id, role, content, tool_call, created_at",
        (str(session_id), role, content, tool_call_json),
    ).fetchone()
    return _row_to_dict(row)


def get_messages(conn, session_id):
    rows = conn.execute(
        "SELECT id, session_id, role, content, tool_call, created_at "
        "FROM messages WHERE session_id = %s ORDER BY created_at",
        (str(session_id),),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def _row_to_dict(row):
    return {
        "id": row[0],
        "session_id": row[1],
        "role": row[2],
        "content": row[3],
        "tool_call": row[4],
        "created_at": row[5],
    }
