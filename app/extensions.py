"""Singleton extensions initialized once during create_app()."""

from psycopg_pool import ConnectionPool

# These are set by init_extensions() in __init__.py
db_pool: ConnectionPool | None = None
s3_client = None
model_router = None
hook_runner = None
tool_executor = None
