"""SSO authentication via Authlib (OIDC). Skeleton for production use."""

from flask import Blueprint, current_app, redirect, session, url_for, g

sso_bp = Blueprint("auth", __name__)


@sso_bp.route("/login")
def login():
    # TODO: Implement Authlib OIDC redirect
    # oauth = current_app.extensions.get("oauth")
    # return oauth.provider.authorize_redirect(url_for("auth.callback", _external=True))
    return "SSO login not yet configured. Set AUTH_MODE=dev for local development.", 501


@sso_bp.route("/auth/callback")
def callback():
    # TODO: Implement Authlib OIDC callback
    return "SSO callback not yet configured.", 501


@sso_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@sso_bp.route("/")
def root():
    if session.get("user_id"):
        return redirect(url_for("chat.index"))
    return redirect(url_for("auth.login"))
