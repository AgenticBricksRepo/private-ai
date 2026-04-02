"""User queries."""


def get_user_by_id(conn, user_id):
    row = conn.execute(
        "SELECT id, tenant_id, email, role, created_at FROM users WHERE id = %s",
        (str(user_id),),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def get_user_by_email(conn, tenant_id, email):
    row = conn.execute(
        "SELECT id, tenant_id, email, role, created_at FROM users "
        "WHERE tenant_id = %s AND email = %s",
        (str(tenant_id), email),
    ).fetchone()
    if not row:
        return None
    return _row_to_dict(row)


def create_user(conn, tenant_id, email, role="member"):
    row = conn.execute(
        "INSERT INTO users (tenant_id, email, role) VALUES (%s, %s, %s) "
        "RETURNING id, tenant_id, email, role, created_at",
        (str(tenant_id), email, role),
    ).fetchone()
    return _row_to_dict(row)


def upsert_user(conn, tenant_id, email, role="member"):
    """Insert user or return existing one."""
    existing = get_user_by_email(conn, tenant_id, email)
    if existing:
        return existing
    return create_user(conn, tenant_id, email, role)


def list_users(conn, tenant_id):
    rows = conn.execute(
        "SELECT id, tenant_id, email, role, created_at FROM users "
        "WHERE tenant_id = %s ORDER BY created_at",
        (str(tenant_id),),
    ).fetchall()
    return [_row_to_dict(r) for r in rows]


def update_user_role(conn, user_id, role):
    conn.execute(
        "UPDATE users SET role = %s WHERE id = %s",
        (role, str(user_id)),
    )


def _row_to_dict(row):
    return {
        "id": row[0],
        "tenant_id": row[1],
        "email": row[2],
        "role": row[3],
        "created_at": row[4],
    }
