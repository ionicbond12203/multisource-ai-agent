import type { SalesDatabaseInfo } from "./types";

export async function fetchSalesDatabase(baseUrl: string, signal?: AbortSignal): Promise<SalesDatabaseInfo> {
  const response = await fetch(`${baseUrl}/sales/tables`, { signal });
  if (!response.ok) {
    throw new Error(`Could not load the tables (${response.status}).`);
  }
  return (await response.json()) as SalesDatabaseInfo;
}
