/**
 * Shapes of the sales database endpoints. Mirror SalesDatabaseInfo and
 * TableRows in apps/api/src/api/schemas.py.
 */

export type CellValue = string | number | boolean | null;

export interface SalesColumn {
  name: string;
  /** SQL type, e.g. "integer", "numeric(10, 2)", "timestamp". */
  type: string;
  description: string;
}

export interface SalesTable {
  name: string;
  description: string;
  rowCount: number;
  primaryKey: string[];
  columns: SalesColumn[];
}

/** GET /sales/tables */
export interface SalesDatabaseInfo {
  company: string;
  period: string;
  tables: SalesTable[];
}

export type SortOrder = "asc" | "desc";

export interface RowsQuery {
  offset: number;
  limit: number;
  sort: string | null;
  order: SortOrder;
}

/** GET /sales/tables/{name}/rows: one page of rows. */
export interface TableRows {
  table: string;
  columns: string[];
  /** Values in column order. Dates and times are ISO strings. */
  rows: CellValue[][];
  total: number;
  offset: number;
  limit: number;
  sort?: string;
  order: SortOrder;
}
