"""Admin dashboard routes (HTML)."""

from flask import Blueprint, g, render_template

from app.auth.decorators import admin_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/admin")
@admin_required
def dashboard():
    from app.db.usage import get_usage_summary
    from app.db.sessions import list_sessions

    conn = g.db_conn
    usage = get_usage_summary(conn, g.current_tenant["id"])
    sessions = list_sessions(conn, g.current_tenant["id"], limit=10)
    return render_template("admin/dashboard.html", usage=usage, sessions=sessions)


@admin_bp.route("/admin/users")
@admin_required
def users():
    from app.db.users import list_users
    conn = g.db_conn
    users_list = list_users(conn, g.current_tenant["id"])
    return render_template("admin/users.html", users=users_list)


@admin_bp.route("/admin/usage")
@admin_required
def usage():
    from app.db.usage import get_usage_summary, get_usage_by_user
    conn = g.db_conn
    by_model = get_usage_summary(conn, g.current_tenant["id"])
    by_user = get_usage_by_user(conn, g.current_tenant["id"])
    return render_template("admin/usage.html", by_model=by_model, by_user=by_user)


@admin_bp.route("/admin/audit")
@admin_required
def audit():
    from flask import request
    from app.db.audit import list_audit_logs, count_audit_logs, list_event_types

    conn = g.db_conn
    tenant_id = g.current_tenant["id"]

    event_type = request.args.get("event_type", "")
    search = request.args.get("search", "")
    page = max(1, int(request.args.get("page", 1)))
    per_page = 25

    total = count_audit_logs(conn, tenant_id, event_type=event_type or None, search=search or None)
    logs = list_audit_logs(conn, tenant_id,
                           event_type=event_type or None,
                           search=search or None,
                           limit=per_page,
                           offset=(page - 1) * per_page)
    event_types = list_event_types(conn, tenant_id)
    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template("admin/audit.html",
                           logs=logs, event_types=event_types,
                           current_event_type=event_type, current_search=search,
                           page=page, total_pages=total_pages, total=total)
