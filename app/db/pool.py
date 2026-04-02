"""psycopg v3 connection pool."""

from psycopg_pool import ConnectionPool


def create_pool(database_url: str, min_size: int = 2, max_size: int = 10) -> ConnectionPool:
    """Create a connection pool from the DATABASE_URL."""
    return ConnectionPool(
        conninfo=database_url,
        min_size=min_size,
        max_size=max_size,
        kwargs={"autocommit": False},
    )
