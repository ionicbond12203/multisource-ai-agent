import type { Metadata } from "next";
import { AppHeader } from "@/components/app-header";
import { SalesDataView } from "@/features/sales-data";
import { isUsingMockApi } from "@/features/workspace";
import { apiUrl } from "@/lib/api-url";

export const metadata: Metadata = {
  title: "SQL database",
  description: "Tables, columns and sample rows of the sales database the SQL agent queries.",
};

export default function SqlDatabasePage() {
  return (
    <>
      <AppHeader activeHref="/sql-database" apiMode={isUsingMockApi ? "mock" : "live"} />
      <SalesDataView apiUrl={apiUrl} />
    </>
  );
}
