"""Tool admin page routes (HTML)."""

from flask import Blueprint, g, render_template

from app.auth.decorators import admin_required

tools_bp = Blueprint("tools", __name__)


@tools_bp.route("/admin/tools")
@admin_required
def index():
    from app.db.tools import list_tools
    conn = g.db_conn
    tools = list_tools(conn, g.current_tenant["id"])
    return render_template("admin/tools.html", tools=tools)


@tools_bp.route("/admin/tools/new")
@admin_required
def new():
    return render_template("admin/tool_form.html")
