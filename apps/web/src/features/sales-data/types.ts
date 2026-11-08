/**
 * Shape of GET /sales/tables. Mirrors SalesDatabaseInfo in apps/api/src/api/schemas.py.
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
  columns: SalesColumn[];
  /** The first rows, values in column order. Dates and times are ISO strings. */
  previewRows: CellValue[][];
}

export interface SalesDatabaseInfo {
  company: string;
  period: string;
  tables: SalesTable[];
}
