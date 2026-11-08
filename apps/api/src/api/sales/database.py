"""
Runs checked SQL against the sales database.

`DuckDbSalesDatabase` is the offline version: an embedded database file,
opened read-only after the sample data is written. The Postgres version is in
`api.postgres.sales_database`.
"""

import csv
import logging
import tempfile
import threading
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Protocol

import duckdb
import sqlglot

from api.sales.data import generate
from api.sales.schema import CREATE_TABLES, SCHEMA, TABLE_ORDER

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class QueryResult:
    columns: list[str]
    rows: list[tuple[object, ...]]
    elapsed_ms: int


class QueryFailed(Exception):
    """The database rejected or failed the query. The message is shown to the model and in the trace."""


class SalesDatabase(Protocol):
    def run(self, sql: str) -> QueryResult:
        """Runs SQL already approved by `check_sql`. Raises QueryFailed."""
        ...


class DuckDbSalesDatabase:
    def __init__(self, timeout_s: float = 5.0) -> None:
        self.timeout_s = timeout_s
        # Read-only: even a query that slipped past the checks cannot change anything.
        self._connection = duckdb.connect(str(_database_file()), read_only=True)
        self._connection.execute(f"set search_path = '{SCHEMA}'")
        self._lock = threading.Lock()  # a DuckDB connection is not safe to share between threads

    def run(self, sql: str) -> QueryResult:
        duck_sql = sqlglot.transpile(sql, read="postgres", write="duckdb")[0]
        started = time.perf_counter()
        with self._lock:
            # DuckDB has no statement timeout, so interrupt long queries from a timer.
            timer = threading.Timer(self.timeout_s, self._connection.interrupt)
            timer.start()
            try:
                cursor = self._connection.execute(duck_sql)
                columns = [column[0] for column in cursor.description or []]
                rows = cursor.fetchall()
            except duckdb.InterruptException as error:
                raise QueryFailed(f"The query took longer than {self.timeout_s:g} seconds.") from error
            except duckdb.Error as error:
                raise QueryFailed(_first_line(error)) from error
            finally:
                timer.cancel()
        return QueryResult(columns, [to_plain_row(row) for row in rows], _elapsed_ms(started))


_build_lock = threading.Lock()
_build_directory: tempfile.TemporaryDirectory[str] | None = None


def _database_file() -> Path:
    """
    Builds the sample database once per process and returns its path.
    The data is deterministic, so every instance can share the same file.
    """
    global _build_directory
    with _build_lock:
        if _build_directory is None:
            directory = tempfile.TemporaryDirectory(prefix="sales-db-")
            _create(Path(directory.name))
            _build_directory = directory  # kept alive (and deleted) with the process
        return Path(_build_directory.name) / "sales.duckdb"


def _create(directory: Path) -> None:
    data = generate()
    with duckdb.connect(str(directory / "sales.duckdb")) as connection:
        connection.execute(CREATE_TABLES)
        for table in TABLE_ORDER:
            # Bulk-loading a CSV is far faster than inserting rows one by one.
            csv_path = directory / f"{table}.csv"
            with csv_path.open("w", newline="", encoding="utf-8") as handle:
                csv.writer(handle).writerows(
                    ["" if value is None else value for value in row] for row in data[table]
                )
            connection.execute(
                f"copy {SCHEMA}.{table} from '{csv_path.as_posix()}' (header false, nullstr '')"
            )
            csv_path.unlink()


def to_plain_row(row: Sequence[object]) -> tuple[object, ...]:
    """Turns Decimal and date values into JSON-friendly ones."""
    return tuple(_plain(value) for value in row)


def _plain(value: object) -> object:
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, datetime):
        return value.isoformat(sep=" ", timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()
    return value


def _elapsed_ms(started: float) -> int:
    return round((time.perf_counter() - started) * 1000)


def _first_line(error: Exception) -> str:
    return str(error).strip().splitlines()[0][:300]
