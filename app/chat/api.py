"""Chat API routes (JSON + SSE)."""

import json
import logging
import threading

from flask import Blueprint, Response, g, request, stream_with_context

from app.auth.decorators import login_required

logger = logging.getLogger(__name__)
chat_api_bp = Blueprint("chat_api", __name__)

# Track active sessions for cancellation
_active_sessions: dict[str, dict] = {}
# Track attached files per session (in-memory; moves to Redis for horizontal scaling)
_session_files: dict[str, list[dict]] = {}
_lock = threading.Lock()


@chat_api_bp.route("/api/sessions", methods=["POST"])
@login_required
def create_session():
    from app.db.sessions import create_session
    from app import extensions

    data = request.get_json(force=True)
    model_id = data.get("model_id", extensions.model_router.get_default_model())
    agent_id = data.get("agent_id")

    conn = g.db_conn
    session_row = create_session(
        conn,
        tenant_id=g.current_tenant["id"],
        user_id=g.current_user["id"],
        model_id=model_id,
        agent_id=agent_id,
    )

    return json.dumps(session_row, default=str), 201, {"Content-Type": "application/json"}


@chat_api_bp.route("/api/sessions/<session_id>/chat", methods=["POST"])
@login_required
def chat(session_id):
    from app.db.sessions import get_session
    from app.db.messages import add_message, get_messages
    from app.db.agents import get_agent
    from app.orchestrator.engine import run
    from app.orchestrator.context import build_context
    from app import extensions

    conn = g.db_conn
    session_row = get_session(conn, session_id)
    if not session_row or str(session_row["tenant_id"]) != str(g.current_tenant["id"]):
        return json.dumps({"error": "Session not found"}), 404

    data = request.get_json(force=True)
    user_message = data.get("content", "").strip()
    if not user_message:
        return json.dumps({"error": "Empty message"}), 400

    # Store user message
    add_message(conn, session_id, "user", user_message)
    conn.commit()

    # Build context
    messages = get_messages(conn, session_id)
    agent_data = None
    if session_row.get("agent_id"):
        agent_data = get_agent(conn, session_row["agent_id"])

    attached_files = _session_files.get(session_id, [])
    ctx = build_context(session_row, agent_data=agent_data, messages=messages,
                        attached_files=attached_files)

    # Track for cancellation
    with _lock:
        _active_sessions[session_id] = {"ctx": ctx}

    def generate():
        try:
            accumulated = ""
            for chunk in run(ctx, extensions.model_router, extensions.tool_executor, extensions.hook_runner):
                yield chunk
                # Track accumulated text for message storage
                try:
                    parsed = json.loads(chunk.replace("data: ", "").strip())
                    if parsed.get("type") == "text":
                        accumulated += parsed.get("content", "")
                except (json.JSONDecodeError, ValueError):
                    pass

            # Store assistant response
            if accumulated:
                with extensions.db_pool.connection() as store_conn:
                    add_message(store_conn, session_id, "assistant", accumulated)
                    store_conn.commit()
        except Exception as e:
            logger.exception("Chat stream error")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            with _lock:
                _active_sessions.pop(session_id, None)

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@chat_api_bp.route("/api/sessions/<session_id>/cancel", methods=["POST"])
@login_required
def cancel(session_id):
    with _lock:
        active = _active_sessions.get(session_id)
        if active:
            active["ctx"].cancelled = True
    return json.dumps({"status": "cancelled"}), 200


@chat_api_bp.route("/api/sessions/<session_id>", methods=["DELETE"])
@login_required
def end_session(session_id):
    from app.db.sessions import end_session, get_session

    conn = g.db_conn
    session_row = get_session(conn, session_id)
    if not session_row or str(session_row["tenant_id"]) != str(g.current_tenant["id"]):
        return json.dumps({"error": "Session not found"}), 404

    end_session(conn, session_id, status="completed")
    _session_files.pop(session_id, None)
    return json.dumps({"status": "completed"}), 200


@chat_api_bp.route("/api/sessions/<session_id>/files", methods=["POST"])
@login_required
def attach_file(session_id):
    """Attach an ad-hoc file to a session (Tier 1: injected into context)."""
    from app.db.sessions import get_session

    conn = g.db_conn
    session_row = get_session(conn, session_id)
    if not session_row or str(session_row["tenant_id"]) != str(g.current_tenant["id"]):
        return json.dumps({"error": "Session not found"}), 404

    if "file" not in request.files:
        return json.dumps({"error": "No file provided"}), 400

    file = request.files["file"]
    raw = file.read()
    import base64, os
    ext = os.path.splitext(file.filename or "")[1].lower()

    IMAGE_EXTENSIONS = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                        ".gif": "image/gif", ".webp": "image/webp"}
    TEXT_EXTENSIONS = {".txt", ".md", ".csv", ".json", ".xml", ".html", ".py", ".js",
                       ".ts", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".log", ".sql",
                       ".sh", ".bash", ".css", ".java", ".go", ".rs", ".rb", ".php"}

    if ext in IMAGE_EXTENSIONS:
        # Images: cap at 5MB, store as base64 for vision API
        if len(raw) > 5_000_000:
            return json.dumps({"error": f"Image too large ({len(raw):,} bytes). Maximum is 5MB."}), 400
        media_type = IMAGE_EXTENSIONS[ext]
        b64 = base64.b64encode(raw).decode("ascii")
        file_entry = {
            "filename": file.filename,
            "type": "image",
            "media_type": media_type,
            "base64": b64,
        }
    elif ext in TEXT_EXTENSIONS:
        # Text: cap at 100KB
        if len(raw) > 100_000:
            return json.dumps({"error": f"File too large ({len(raw):,} bytes). Maximum is 100KB."}), 400
        file_entry = {
            "filename": file.filename,
            "type": "text",
            "content": raw.decode("utf-8", errors="replace"),
        }
    else:
        return json.dumps({"error": f"Unsupported file type: {ext or 'unknown'}"}), 400

    # Store in S3
    from app import extensions
    import uuid
    doc_id = str(uuid.uuid4())
    key = f"tenants/{g.current_tenant['id']}/sessions/{session_id}/files/{doc_id}"
    extensions.s3_client.upload(key, raw)

    # Track for context injection
    if session_id not in _session_files:
        _session_files[session_id] = []
    _session_files[session_id].append(file_entry)

    return json.dumps({
        "id": doc_id,
        "filename": file.filename,
        "storage_url": key,
    }), 201
