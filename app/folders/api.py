"""Folder API routes (JSON)."""

import json
import re
import uuid

from flask import Blueprint, g, redirect, request

from app.auth.decorators import admin_required
from app.db.audit import write_audit_log

folders_api_bp = Blueprint("folders_api", __name__)


def _htmx_or_json(data, status=200):
    if request.headers.get("HX-Request"):
        resp = redirect("/admin/folders")
        resp.headers["HX-Redirect"] = "/admin/folders"
        return resp
    return json.dumps(data, default=str), status


@folders_api_bp.route("/api/folders", methods=["POST"])
@admin_required
def create_folder():
    from app.db.folders import create_folder
    data = request.get_json(silent=True) or {}
    if not data:
        data = {k: v for k, v in request.form.items()}
        if "tier" in data and isinstance(data["tier"], str):
            data["tier"] = int(data["tier"])

    name = data.get("name", "").strip()
    if not name:
        return json.dumps({"error": "Name is required"}), 400

    slug = data.get("slug") or re.sub(r"[^a-z0-9-]", "-", name.lower()).strip("-")
    tier = data.get("tier", 1)

    folder = create_folder(g.db_conn, g.current_tenant["id"], name, slug, tier)
    write_audit_log(g.db_conn, g.current_tenant["id"], "folder_created",
                    {"folder_id": str(folder["id"]), "name": name, "tier": tier},
                    user_id=g.current_user["id"])
    return _htmx_or_json(folder, 201)


@folders_api_bp.route("/api/folders/<folder_id>/upload", methods=["POST"])
@admin_required
def upload_document(folder_id):
    from app.db.folders import get_folder, add_document, update_folder_index, list_documents
    from app.storage.documents import upload_document as s3_upload, build_folder_index
    from app import extensions

    conn = g.db_conn
    folder = get_folder(conn, folder_id)
    if not folder or str(folder["tenant_id"]) != str(g.current_tenant["id"]):
        return json.dumps({"error": "Folder not found"}), 404

    if "file" not in request.files:
        return json.dumps({"error": "No file provided"}), 400

    file = request.files["file"]
    content = file.read()
    doc_id = str(uuid.uuid4())

    storage_url = s3_upload(
        extensions.s3_client,
        str(g.current_tenant["id"]),
        str(folder["id"]),
        doc_id,
        file.filename,
        content,
    )

    doc = add_document(conn, folder["id"], file.filename, storage_url)

    # Rebuild folder index
    docs = list_documents(conn, folder["id"])
    index_url = build_folder_index(
        extensions.s3_client,
        str(g.current_tenant["id"]),
        str(folder["id"]),
        docs,
    )
    update_folder_index(conn, folder["id"], index_url, len(docs))

    write_audit_log(conn, g.current_tenant["id"], "document_uploaded",
                    {"folder_id": folder_id, "filename": file.filename},
                    user_id=g.current_user["id"])

    if request.headers.get("HX-Request"):
        resp = redirect(f"/admin/folders")
        resp.headers["HX-Redirect"] = "/admin/folders"
        return resp
    return json.dumps(doc, default=str), 201


@folders_api_bp.route("/api/folders/<folder_id>/reindex", methods=["POST"])
@admin_required
def reindex_folder(folder_id):
    from app.db.folders import get_folder, list_documents, update_folder_index
    from app.storage.documents import build_folder_index
    from app import extensions

    conn = g.db_conn
    folder = get_folder(conn, folder_id)
    if not folder or str(folder["tenant_id"]) != str(g.current_tenant["id"]):
        return json.dumps({"error": "Folder not found"}), 404

    docs = list_documents(conn, folder["id"])
    index_url = build_folder_index(
        extensions.s3_client,
        str(g.current_tenant["id"]),
        str(folder["id"]),
        docs,
    )
    update_folder_index(conn, folder["id"], index_url, len(docs))

    return json.dumps({"status": "reindexed", "doc_count": len(docs), "index_url": index_url}), 200
