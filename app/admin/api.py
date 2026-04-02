"""Admin API routes (JSON)."""

import json

from flask import Blueprint, g, request

from app.auth.decorators import admin_required
from app.db.audit import write_audit_log

admin_api_bp = Blueprint("admin_api", __name__)


@admin_api_bp.route("/api/admin/recordings/<session_id>")
@admin_required
def get_recording(session_id):
    from app.db.sessions import get_session
    from app import extensions

    conn = g.db_conn
    session_row = get_session(conn, session_id)
    if not session_row or str(session_row["tenant_id"]) != str(g.current_tenant["id"]):
        return json.dumps({"error": "Session not found"}), 404

    if not session_row.get("recording_url"):
        return json.dumps({"error": "No recording available"}), 404

    url = extensions.s3_client.presigned_url(session_row["recording_url"])
    return json.dumps({"url": url}), 200


@admin_api_bp.route("/api/admin/theme", methods=["POST"])
@admin_required
def set_theme():
    data = request.get_json(silent=True) or {}
    if not data:
        data = {k: v for k, v in request.form.items()}
    theme_name = data.get("theme", "dark")

    conn = g.db_conn
    conn.execute(
        "UPDATE tenants SET theme = %s::jsonb WHERE id = %s",
        (json.dumps({"name": theme_name}), str(g.current_tenant["id"])),
    )

    write_audit_log(conn, g.current_tenant["id"], "theme_changed",
                    {"theme": theme_name}, user_id=g.current_user["id"])

    return json.dumps({"status": "ok", "theme": theme_name}), 200


@admin_api_bp.route("/api/admin/branding", methods=["POST"])
@admin_required
def update_branding():
    data = request.get_json(silent=True) or {}
    if not data:
        data = {k: v for k, v in request.form.items()}

    conn = g.db_conn
    name = data.get("name", "").strip()
    logo_url = data.get("logo_url", "").strip() or None

    if not name:
        return json.dumps({"error": "Name is required"}), 400

    conn.execute(
        "UPDATE tenants SET name = %s, logo_url = %s WHERE id = %s",
        (name, logo_url, str(g.current_tenant["id"])),
    )

    write_audit_log(conn, g.current_tenant["id"], "branding_updated",
                    {"name": name, "logo_url": logo_url}, user_id=g.current_user["id"])

    return json.dumps({"status": "ok"}), 200
