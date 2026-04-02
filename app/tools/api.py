"""Tool API routes (JSON)."""

import json

from flask import Blueprint, g, redirect, request

from app.auth.decorators import admin_required
from app.db.audit import write_audit_log

tools_api_bp = Blueprint("tools_api", __name__)


def _htmx_or_json(data, status=200):
    if request.headers.get("HX-Request"):
        resp = redirect("/admin/tools")
        resp.headers["HX-Redirect"] = "/admin/tools"
        return resp
    return json.dumps(data, default=str), status


@tools_api_bp.route("/api/tools", methods=["POST"])
@admin_required
def create_tool():
    from app.db.tools import create_tool
    data = request.get_json(silent=True) or {}
    if not data:
        data = {k: v for k, v in request.form.items()}
        if "input_schema" in data and isinstance(data["input_schema"], str):
            data["input_schema"] = json.loads(data["input_schema"])
        if "timeout_ms" in data and isinstance(data["timeout_ms"], str):
            data["timeout_ms"] = int(data["timeout_ms"])
        if "requires_confirmation" in data:
            data["requires_confirmation"] = data["requires_confirmation"] == "true"

    required = ["name", "description", "endpoint", "method", "auth_type", "input_schema", "timeout_ms"]
    missing = [f for f in required if f not in data]
    if missing:
        return json.dumps({"error": f"Missing fields: {missing}"}), 400

    tool = create_tool(g.db_conn, tenant_id=g.current_tenant["id"], **data)
    write_audit_log(g.db_conn, g.current_tenant["id"], "tool_created",
                    {"tool_id": str(tool["id"]), "name": data["name"]},
                    user_id=g.current_user["id"])
    return _htmx_or_json(tool, 201)


@tools_api_bp.route("/api/tools/<tool_id>", methods=["DELETE"])
@admin_required
def delete_tool(tool_id):
    from app.db.tools import delete_tool, get_tool

    tool = get_tool(g.db_conn, tool_id)
    if not tool or str(tool["tenant_id"]) != str(g.current_tenant["id"]):
        return json.dumps({"error": "Tool not found"}), 404

    delete_tool(g.db_conn, tool_id)
    write_audit_log(g.db_conn, g.current_tenant["id"], "tool_deleted",
                    {"tool_id": tool_id, "name": tool["name"]},
                    user_id=g.current_user["id"])
    return _htmx_or_json({"status": "deleted"})
