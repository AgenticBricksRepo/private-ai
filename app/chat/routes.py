"""Chat page routes (HTML)."""

from flask import Blueprint, g, render_template

from app.auth.decorators import login_required

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat")
@login_required
def index():
    from app.db.sessions import list_sessions
    from app.db.agents import list_agents
    from app import extensions

    conn = g.db_conn
    sessions = list_sessions(conn, g.current_tenant["id"], g.current_user["id"])
    agents = list_agents(conn, g.current_tenant["id"])
    models = extensions.model_router.list_models()
    default_model = extensions.model_router.get_default_model()

    return render_template(
        "chat.html",
        sessions=sessions,
        agents=agents,
        models=models,
        default_model=default_model,
    )


@chat_bp.route("/chat/<session_id>")
@login_required
def resume(session_id):
    from app.db.sessions import get_session, list_sessions
    from app.db.messages import get_messages
    from app.db.agents import list_agents
    from app import extensions

    conn = g.db_conn
    chat_session = get_session(conn, session_id)
    if not chat_session or str(chat_session["tenant_id"]) != str(g.current_tenant["id"]):
        return "Session not found", 404

    messages = get_messages(conn, session_id)
    sessions = list_sessions(conn, g.current_tenant["id"], g.current_user["id"])
    agents = list_agents(conn, g.current_tenant["id"])
    models = extensions.model_router.list_models()

    return render_template(
        "chat.html",
        sessions=sessions,
        agents=agents,
        models=models,
        default_model=chat_session["model_id"],
        current_session=chat_session,
        messages=messages,
    )
