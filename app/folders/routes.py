"""Folder admin page routes (HTML)."""

from flask import Blueprint, g, render_template

from app.auth.decorators import admin_required

folders_bp = Blueprint("folders", __name__)


@folders_bp.route("/admin/folders")
@admin_required
def index():
    from app.db.folders import list_folders
    conn = g.db_conn
    folders = list_folders(conn, g.current_tenant["id"])
    return render_template("admin/folders.html", folders=folders)


@folders_bp.route("/admin/folders/new")
@admin_required
def new():
    return render_template("admin/folder_form.html")
