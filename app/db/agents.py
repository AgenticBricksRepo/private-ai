"""Agent queries."""

import json


def create_agent(conn, tenant_id, name, slug, prompt_md, mode="interactive",
                 description=None, trigger_config=None, tool_ids=None,
                 connector_ids=None, folder_ids=None):
    row = conn.execute(
        "INSERT INTO agents (tenant_id, name, slug, description, prompt_md, mode, "
        "trigger_config, tool_ids, connector_ids, folder_ids) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s) "
        "RETURNING id, tenant_id, name, slug, description, prompt_md, mode, "
        "trigger_config, tool_ids, connector_ids, folder_ids, created_at",
        (str(tenant_id), name, slug, description, prompt_md, mode,
         json.dumps(trigger_config) if trigger_config else None,
         tool_ids or [], connector_ids or [], folder_ids or []),
    ).fetchone()
    return _row_to_dict(row)


def get_agent(conn, agent_id):
    row = conn.execute(
        "SELECT id, tenant_id, name, slug, description, prompt_md, mode, "
        "trigger_config, tool_ids, connector_ids, folder_ids, created_at "
        "FROM agents WHERE id = %s",
        (str(agent_id),),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def list_agents(conn, tenant_id):
    rows = conn.execute(
        "SELECT id, tenant_id, name, slug, description, prompt_md, mode, "
        "trigger_config, tool_ids, connector_ids, folder_ids, created_at "
        "FROM agents WHERE tenant_id = %s ORDER BY name",
        (str(tenant_id),),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_agent(conn, agent_id, **kwargs):
    allowed = {"name", "slug", "description", "prompt_md", "mode",
               "trigger_config", "tool_ids", "connector_ids", "folder_ids"}
    fields = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
    if not fields:
        return
    if "trigger_config" in fields:
        fields["trigger_config"] = json.dumps(fields["trigger_config"])
    set_clause = ", ".join(f"{k} = %s" for k in fields)
    values = list(fields.values()) + [str(agent_id)]
    conn.execute(f"UPDATE agents SET {set_clause} WHERE id = %s", values)


def delete_agent(conn, agent_id):
    conn.execute("DELETE FROM agents WHERE id = %s", (str(agent_id),))


def _row_to_dict(row):
    return {
        "id": row[0], "tenant_id": row[1], "name": row[2], "slug": row[3],
        "description": row[4], "prompt_md": row[5], "mode": row[6],
        "trigger_config": row[7], "tool_ids": row[8], "connector_ids": row[9],
        "folder_ids": row[10], "created_at": row[11],
    }
