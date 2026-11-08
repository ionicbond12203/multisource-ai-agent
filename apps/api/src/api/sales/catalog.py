"""
What the sales database contains, for people rather than the model: each
table's description, columns, row count and first rows.

Read through the same SalesDatabase (read-only, guarded) as the SQL agent,
and cached after the first request because the sample data never changes.
"""

import threading

from api.sales.database import SalesDatabase
from api.sales.guard import check_sql
from api.sales.schema import COMPANY, PERIOD, TABLES
from api.schemas import SalesColumn, SalesDatabaseInfo, SalesTable

PREVIEW_ROWS = 20


class SalesCatalog:
    def __init__(self, sales_db: SalesDatabase, preview_rows: int = PREVIEW_ROWS) -> None:
        self.sales_db = sales_db
        self.preview_rows = preview_rows
        self._cached: SalesDatabaseInfo | None = None
        self._lock = threading.Lock()

    def describe(self) -> SalesDatabaseInfo:
        with self._lock:
            if self._cached is None:
                self._cached = self._build()
            return self._cached

    def _build(self) -> SalesDatabaseInfo:
        counts_sql = "select " + ", ".join(f"(select count(*) from {t.name}) as {t.name}" for t in TABLES)
        [counts] = self.sales_db.run(check_sql(counts_sql, max_rows=1)).rows

        tables = []
        for table, row_count in zip(TABLES, counts, strict=True):
            preview = self.sales_db.run(
                check_sql(f"select * from {table.name} order by 1", max_rows=self.preview_rows)
            )
            tables.append(
                SalesTable(
                    name=table.name,
                    description=table.description,
                    row_count=int(row_count),
                    columns=[
                        SalesColumn(name=c.name, type=c.type, description=c.description)
                        for c in table.columns
                    ],
                    preview_rows=[list(row) for row in preview.rows],
                )
            )
        return SalesDatabaseInfo(company=COMPANY, period=PERIOD, tables=tables)
