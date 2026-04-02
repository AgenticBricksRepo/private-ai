"""Tenant queries. Direct SQL, no ORM."""


def get_tenant_by_id(conn, tenant_id):
    row = conn.execute(
        "SELECT id, name, slug, logo_url, theme, sso_config, recording_retention_days, created_at "
        "FROM tenants WHERE id = %s",
        (str(tenant_id),),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_tenant_by_slug(conn, slug):
    row = conn.execute(
        "SELECT id, name, slug, logo_url, theme, sso_config, recording_retention_days, created_at "
        "FROM tenants WHERE slug = %s",
        (slug,),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def create_tenant(conn, name, slug, theme=None, logo_url=None):
    import json
    theme_json = json.dumps(theme or {})
    row = conn.execute(
        "INSERT INTO tenants (name, slug, logo_url, theme) VALUES (%s, %s, %s, %s::jsonb) "
        "RETURNING id, name, slug, logo_url, theme, sso_config, recording_retention_days, created_at",
        (name, slug, logo_url, theme_json),
    ).fetchone()
    return _row_to_dict(row)


def _row_to_dict(row):
    return {
        "id": row[0],
        "name": row[1],
        "slug": row[2],
        "logo_url": row[3],
        "theme": row[4],
        "sso_config": row[5],
        "recording_retention_days": row[6],
        "created_at": row[7],
    }
