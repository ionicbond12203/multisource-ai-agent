"""
The sales database in Postgres (e.g. Supabase).

Queries run inside a transaction that is read-only, switched to the
`sales_reader` role (SELECT on the sales schema only) and limited by a
statement timeout. So even SQL that got past `check_sql` cannot change data,
read the document tables, or run forever.
"""

import logging
import time

import psycopg
from psycopg_pool import ConnectionPool

from api.sales.data import generate
from api.sales.database import QueryFailed, QueryResult, to_plain_row
from api.sales.schema import CREATE_TABLES, SCHEMA, TABLE_ORDER

logger = logging.getLogger(__name__)

READER_ROLE = "sales_reader"

_CREATE_READER = f"""
do $$
begin
    if not exists (select from pg_roles where rolname = '{READER_ROLE}') then
        create role {READER_ROLE} nologin;
    end if;
end
$$;
grant usage on schema {SCHEMA} to {READER_ROLE};
grant select on all tables in schema {SCHEMA} to {READER_ROLE};
-- Lets the API's own user switch to the reader role with SET ROLE.
grant {READER_ROLE} to current_user;
"""


class PostgresSalesDatabase:
    def __init__(self, pool: ConnectionPool, timeout_s: float = 5.0) -> None:
        self.pool = pool
        self.timeout_ms = int(timeout_s * 1000)
        self._set_up()

    def run(self, sql: str) -> QueryResult:
        started = time.perf_counter()
        try:
            with self.pool.connection() as connection, connection.transaction():
                connection.execute("set transaction read only")
                connection.execute(f"set local role {READER_ROLE}")
                connection.execute(f"set local statement_timeout = {self.timeout_ms}")
                connection.execute(f"set local search_path = {SCHEMA}")
                cursor = connection.execute(sql)
                columns = [column.name for column in cursor.description or []]
                rows = cursor.fetchall()
        except psycopg.errors.QueryCanceled as error:
            raise QueryFailed(f"The query took longer than {self.timeout_ms / 1000:g} seconds.") from error
        except psycopg.Error as error:
            message = error.diag.message_primary or str(error)
            raise QueryFailed(message.splitlines()[0][:300]) from error
        elapsed_ms = round((time.perf_counter() - started) * 1000)
        return QueryResult(columns, [to_plain_row(row) for row in rows], elapsed_ms)

    def _set_up(self) -> None:
        """Creates the tables and reader role, and loads the sample data once."""
        with self.pool.connection() as connection:
            connection.execute(CREATE_TABLES)
            connection.execute(_CREATE_READER)
            count = connection.execute(f"select count(*) from {SCHEMA}.orders").fetchone()
            if count and count[0] > 0:
                return
            data = generate()
            with connection.cursor() as cursor:
                for table in TABLE_ORDER:
                    rows = data[table]
                    placeholders = ", ".join("%s" for _ in rows[0])
                    cursor.executemany(f"insert into {SCHEMA}.{table} values ({placeholders})", rows)
            logger.info("Loaded the sample sales data (%d orders)", len(data["orders"]))
