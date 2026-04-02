"""Agent admin page routes (HTML)."""

from flask import Blueprint, g, render_template

from app.auth.decorators import admin_required

agents_bp = Blueprint("agents", __name__)


@agents_bp.route("/admin/agents")
@admin_required
def index():
    from app.db.agents import list_agents
    conn = g.db_conn
    agents = list_agents(conn, g.current_tenant["id"])
    return render_template("admin/agents.html", agents=agents)


@agents_bp.route("/admin/agents/new")
@admin_required
def new():
    return render_template("admin/agent_form.html", agent=None)


@agents_bp.route("/admin/agents/<agent_id>/edit")
@admin_required
def edit(agent_id):
    from app.db.agents import get_agent
    conn = g.db_conn
    agent = get_agent(conn, agent_id)
    if not agent or str(agent["tenant_id"]) != str(g.current_tenant["id"]):
        return "Agent not found", 404
    return render_template("admin/agent_form.html", agent=agent)
