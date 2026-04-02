"""Auth decorators — @login_required and @admin_required."""

from functools import wraps

from flask import abort, g, redirect, session, url_for


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get("user_id")
        tenant_id = session.get("tenant_id")
        if not user_id or not tenant_id:
            return redirect(url_for("auth.login"))

        # Load user and tenant into g
        from app.db.users import get_user_by_id
        from app.db.tenants import get_tenant_by_id

        conn = g.db_conn
        g.current_user = get_user_by_id(conn, user_id)
        g.current_tenant = get_tenant_by_id(conn, tenant_id)

        if not g.current_user or not g.current_tenant:
            session.clear()
            return redirect(url_for("auth.login"))

        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if g.current_user["role"] != "admin":
            abort(403)
        return f(*args, **kwargs)
    return decorated
