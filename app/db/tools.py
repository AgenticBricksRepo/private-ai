"""Tool queries."""

import json


def create_tool(conn, tenant_id, name, description, endpoint, method, auth_type,
                input_schema, timeout_ms, auth_secret_path=None,
                side_effects=None, requires_confirmation=False):
    row = conn.execute(
        "INSERT INTO tools (tenant_id, name, description, endpoint, method, auth_type, "
        "auth_secret_path, input_schema, side_effects, requires_confirmation, timeout_ms) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s) "
        "RETURNING id, tenant_id, name, description, endpoint, method, auth_type, "
        "auth_secret_path, input_schema, side_effects, requires_confirmation, timeout_ms, created_at",
        (str(tenant_id), name, description, endpoint, method, auth_type,
         auth_secret_path, json.dumps(input_schema), side_effects,
         requires_confirmation, timeout_ms),
    ).fetchone()
    return _row_to_dict(row)


def get_tool(conn, tool_id):
    row = conn.execute(
        "SELECT id, tenant_id, name, description, endpoint, method, auth_type, "
        "auth_secret_path, input_schema, side_effects, requires_confirmation, timeout_ms, created_at "
        "FROM tools WHERE id = %s",
        (str(tool_id),),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_tool_by_name(conn, tenant_id, name):
    row = conn.execute(
        "SELECT id, tenant_id, name, description, endpoint, method, auth_type, "
        "auth_secret_path, input_schema, side_effects, requires_confirmation, timeout_ms, created_at "
        "FROM tools WHERE tenant_id = %s AND name = %s",
        (str(tenant_id), name),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_tools(conn, tenant_id):
    rows = conn.execute(
        "SELECT id, tenant_id, name, description, endpoint, method, auth_type, "
        "auth_secret_path, input_schema, side_effects, requires_confirmation, timeout_ms, created_at "
        "FROM tools WHERE tenant_id = %s ORDER BY name",
        (str(tenant_id),),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def delete_tool(conn, tool_id):
    conn.execute("DELETE FROM tools WHERE id = %s", (str(tool_id),))


def _row_to_dict(row):
    return {
        "id": row[0], "tenant_id": row[1], "name": row[2], "description": row[3],
        "endpoint": row[4], "method": row[5], "auth_type": row[6],
        "auth_secret_path": row[7], "input_schema": row[8], "side_effects": row[9],
        "requires_confirmation": row[10], "timeout_ms": row[11], "created_at": row[12],
    }
