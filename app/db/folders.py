"""Folder and document queries."""

import json


def create_folder(conn, tenant_id, name, slug, tier):
    row = conn.execute(
        "INSERT INTO folders (tenant_id, name, slug, tier) VALUES (%s, %s, %s, %s) "
        "RETURNING id, tenant_id, name, slug, tier, index_url, doc_count, created_at",
        (str(tenant_id), name, slug, tier),
    ).fetchone()
    return _folder_to_dict(row)


def get_folder(conn, folder_id):
    row = conn.execute(
        "SELECT id, tenant_id, name, slug, tier, index_url, doc_count, created_at "
        "FROM folders WHERE id = %s",
        (str(folder_id),),
    ).fetchone()
    if not row:
        return None
    return _folder_to_dict(row)


def list_folders(conn, tenant_id):
    rows = conn.execute(
        "SELECT id, tenant_id, name, slug, tier, index_url, doc_count, created_at "
        "FROM folders WHERE tenant_id = %s ORDER BY name",
        (str(tenant_id),),
    ).fetchall()
    return [_folder_to_dict(r) for r in rows]


def update_folder_index(conn, folder_id, index_url, doc_count):
    conn.execute(
        "UPDATE folders SET index_url = %s, doc_count = %s WHERE id = %s",
        (index_url, doc_count, str(folder_id)),
    )


def delete_folder(conn, folder_id):
    conn.execute("DELETE FROM documents WHERE folder_id = %s", (str(folder_id),))
    conn.execute("DELETE FROM folders WHERE id = %s", (str(folder_id),))


def add_document(conn, folder_id, filename, storage_url, summary=None, metadata=None):
    row = conn.execute(
        "INSERT INTO documents (folder_id, filename, storage_url, summary, metadata) "
        "VALUES (%s, %s, %s, %s, %s::jsonb) "
        "RETURNING id, folder_id, filename, storage_url, summary, metadata, uploaded_at",
        (str(folder_id), filename, storage_url, summary, json.dumps(metadata or {})),
    ).fetchone()
    return _doc_to_dict(row)


def list_documents(conn, folder_id):
    rows = conn.execute(
        "SELECT id, folder_id, filename, storage_url, summary, metadata, uploaded_at "
        "FROM documents WHERE folder_id = %s ORDER BY uploaded_at",
        (str(folder_id),),
    ).fetchall()
    return [_doc_to_dict(r) for r in rows]


def _folder_to_dict(row):
    return {
        "id": row[0], "tenant_id": row[1], "name": row[2], "slug": row[3],
        "tier": row[4], "index_url": row[5], "doc_count": row[6], "created_at": row[7],
    }


def _doc_to_dict(row):
    return {
        "id": row[0], "folder_id": row[1], "filename": row[2],
        "storage_url": row[3], "summary": row[4], "metadata": row[5],
        "uploaded_at": row[6],
    }
