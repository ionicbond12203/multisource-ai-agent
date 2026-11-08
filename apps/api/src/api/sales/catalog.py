"""
The sales database for people rather than the model: what each table holds,
and its rows, a page at a time, sorted by any column.

Everything is read through the same SalesDatabase (checked SQL, read-only
connection) as the SQL agent. Table and column names come only from the
whitelist in schema.py, never from the request as typed.
"""

import threading
from typing import Literal

from api.sales.database import SalesDatabase
from api.sales.guard import check_sql
from api.sales.schema import COMPANY, PERIOD, TABLES, Table, find_table
from api.schemas import SalesColumn, SalesDatabaseInfo, SalesTable, TableRows

MAX_PAGE_SIZE = 100
SortOrder = Literal["asc", "desc"]


class UnknownTable(LookupError):
    pass


class InvalidSort(ValueError):
    pass


class SalesCatalog:
    def __init__(self, sales_db: SalesDatabase) -> None:
        self.sales_db = sales_db
        self._cached: SalesDatabaseInfo | None = None
        self._lock = threading.Lock()

    def describe(self) -> SalesDatabaseInfo:
        """Tables, columns and row counts. Cached: the sample data never changes."""
        with self._lock:
            if self._cached is None:
                self._cached = self._describe()
            return self._cached

    def rows(
        self,
        table_name: str,
        offset: int = 0,
        limit: int = 50,
        sort: str | None = None,
        order: SortOrder = "asc",
    ) -> TableRows:
        table = find_table(table_name)
        if table is None:
            raise UnknownTable(table_name)
        if sort is not None and sort not in table.column_names():
            raise InvalidSort(f"Unknown column {sort!r}. Columns: {', '.join(table.column_names())}.")
        limit = max(1, min(limit, MAX_PAGE_SIZE))
        offset = max(0, offset)

        result = self.sales_db.run(check_sql(_page_sql(table, offset, limit, sort, order), max_rows=limit))
        total = next(t.row_count for t in self.describe().tables if t.name == table.name)
        return TableRows(
            table=table.name,
            columns=result.columns,
            rows=[list(row) for row in result.rows],
            total=total,
            offset=offset,
            limit=limit,
            sort=sort,
            order=order,
        )

    def _describe(self) -> SalesDatabaseInfo:
        counts_sql = "select " + ", ".join(f"(select count(*) from {t.name}) as {t.name}" for t in TABLES)
        [counts] = self.sales_db.run(check_sql(counts_sql, max_rows=1)).rows
        return SalesDatabaseInfo(
            company=COMPANY,
            period=PERIOD,
            tables=[
                SalesTable(
                    name=table.name,
                    description=table.description,
                    row_count=int(count),
                    primary_key=list(table.primary_key),
                    columns=[
                        SalesColumn(name=c.name, type=c.type, description=c.description)
                        for c in table.columns
                    ],
                )
                for table, count in zip(TABLES, counts, strict=True)
            ],
        )


def _page_sql(table: Table, offset: int, limit: int, sort: str | None, order: SortOrder) -> str:
    # Names here are from the whitelist only. The primary key breaks ties, so
    # rows never repeat or go missing between pages.
    ordering = [f"{sort} {order} nulls last"] if sort else []
    ordering += [column for column in table.primary_key if column != sort]
    return f"select * from {table.name} order by {', '.join(ordering)} limit {limit} offset {offset}"
