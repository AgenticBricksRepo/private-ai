"""Dev auth bypass — simple email login for local development."""

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for, g

dev_auth_bp = Blueprint("auth", __name__)


@dev_auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not email:
            return render_template("login.html", error="Email is required"), 400

        from app.db.tenants import get_tenant_by_slug
        from app.db.users import upsert_user

        conn = g.db_conn

        # Get or create dev tenant
        tenant = get_tenant_by_slug(conn, "dev")
        if not tenant:
            from app.db.tenants import create_tenant
            tenant = create_tenant(conn, "Development", "dev", theme={"name": "dark"})

        # Upsert user — auto-admin in dev mode
        user = upsert_user(conn, tenant["id"], email, role="admin")

        session["user_id"] = str(user["id"])
        session["tenant_id"] = str(tenant["id"])
        session.permanent = True

        return redirect(url_for("chat.index"))

    return render_template("login.html")


@dev_auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@dev_auth_bp.route("/")
def root():
    if session.get("user_id"):
        return redirect(url_for("chat.index"))
    return redirect(url_for("auth.login"))
