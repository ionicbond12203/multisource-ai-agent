import type { RowsQuery, SalesDatabaseInfo, TableRows } from "./types";

export async function fetchSalesDatabase(baseUrl: string, signal?: AbortSignal): Promise<SalesDatabaseInfo> {
  return getJson<SalesDatabaseInfo>(`${baseUrl}/sales/tables`, signal);
}

export async function fetchTableRows(
  baseUrl: string,
  table: string,
  query: RowsQuery,
  signal?: AbortSignal,
): Promise<TableRows> {
  const params = new URLSearchParams({
    offset: String(query.offset),
    limit: String(query.limit),
    order: query.order,
  });
  if (query.sort) params.set("sort", query.sort);
  return getJson<TableRows>(`${baseUrl}/sales/tables/${encodeURIComponent(table)}/rows?${params}`, signal);
}

async function getJson<T>(url: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(url, { signal });
  if (!response.ok) {
    let detail = `Request failed (${response.status}).`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      // Not JSON; keep the generic message.
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}
