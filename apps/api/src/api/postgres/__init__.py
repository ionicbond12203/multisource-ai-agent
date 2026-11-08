"""
Postgres connection pool and schema setup.

Works with any Postgres that has the pgvector extension, including Supabase's
free plan. On Supabase, use the "Session pooler" connection string: it works
over IPv4, which most free hosts need.
"""

from importlib.resources import files

from pgvector.psycopg import register_vector
from psycopg import Connection
from psycopg_pool import ConnectionPool


def _configure(connection: Connection) -> None:
    register_vector(connection)


def create_pool(database_url: str) -> ConnectionPool:
    """Opens a small pool and makes sure the schema exists."""
    _apply_schema(database_url)
    return ConnectionPool(
        database_url,
        min_size=1,
        max_size=5,
        open=True,
        configure=_configure,
        # Supabase's pooler closes connections that sit idle. Without these, the
        # pool would hand out a dead connection and the request would fail with
        # "server closed the connection unexpectedly":
        # - check: test each connection before lending it, replacing broken ones
        # - max_idle / max_lifetime: retire connections before the server drops them
        check=ConnectionPool.check_connection,
        max_idle=120,
        max_lifetime=15 * 60,
        # Transaction poolers (e.g. Supabase port 6543) don't support prepared statements.
        kwargs={"prepare_threshold": None},
    )


def _apply_schema(database_url: str) -> None:
    sql = files("api.postgres").joinpath("schema.sql").read_text(encoding="utf-8")
    # The extension must exist before `register_vector` runs on pooled connections.
    with Connection.connect(database_url, autocommit=True, prepare_threshold=None) as connection:
        connection.execute(sql)
