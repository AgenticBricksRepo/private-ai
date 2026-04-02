"""Agent API routes (JSON)."""

import json
import re

from flask import Blueprint, g, redirect, request

from app.auth.decorators import admin_required
from app.db.audit import write_audit_log

agents_api_bp = Blueprint("agents_api", __name__)


def _htmx_or_json(data, status=200):
    """Return HX-Redirect for HTMX requests, JSON otherwise."""
    if request.headers.get("HX-Request"):
        resp = redirect("/admin/agents")
        resp.headers["HX-Redirect"] = "/admin/agents"
        return resp
    return json.dumps(data, default=str), status


@agents_api_bp.route("/api/agents", methods=["POST"])
@admin_required
def create_agent():
    from app.db.agents import create_agent
    data = request.get_json(silent=True) or {}
    # Support both JSON and form data
    if not data:
        data = {k: v for k, v in request.form.items()}

    name = data.get("name", "").strip()
    if not name:
        return json.dumps({"error": "Name is required"}), 400

    slug = data.get("slug") or re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    agent = create_agent(
        g.db_conn,
        tenant_id=g.current_tenant["id"],
        name=name,
        slug=slug,
        prompt_md=data.get("prompt_md", "You are a helpful assistant."),
        mode=data.get("mode", "interactive"),
        description=data.get("description"),
    )
    write_audit_log(g.db_conn, g.current_tenant["id"], "agent_created",
                    {"agent_id": str(agent["id"]), "name": name},
                    user_id=g.current_user["id"])
    return _htmx_or_json(agent, 201)


@agents_api_bp.route("/api/agents/<agent_id>", methods=["PUT"])
@admin_required
def update_agent(agent_id):
    from app.db.agents import update_agent, get_agent
    data = request.get_json(silent=True) or {}
    if not data:
        data = {k: v for k, v in request.form.items()}

    agent = get_agent(g.db_conn, agent_id)
    if not agent or str(agent["tenant_id"]) != str(g.current_tenant["id"]):
        return json.dumps({"error": "Agent not found"}), 404

    update_agent(g.db_conn, agent_id, **data)
    write_audit_log(g.db_conn, g.current_tenant["id"], "agent_updated",
                    {"agent_id": agent_id, "changes": list(data.keys())},
                    user_id=g.current_user["id"])
    return _htmx_or_json({"status": "updated"})


@agents_api_bp.route("/api/agents/<agent_id>", methods=["DELETE"])
@admin_required
def delete_agent(agent_id):
    from app.db.agents import delete_agent, get_agent

    agent = get_agent(g.db_conn, agent_id)
    if not agent or str(agent["tenant_id"]) != str(g.current_tenant["id"]):
        return json.dumps({"error": "Agent not found"}), 404

    delete_agent(g.db_conn, agent_id)
    write_audit_log(g.db_conn, g.current_tenant["id"], "agent_deleted",
                    {"agent_id": agent_id, "name": agent["name"]},
                    user_id=g.current_user["id"])
    return _htmx_or_json({"status": "deleted"})
