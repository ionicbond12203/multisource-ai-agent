"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { BackendStatusBanner, useBackendStatus } from "@/features/workspace";
import { cn } from "@/lib/utils";
import { fetchSalesDatabase } from "../api";
import type { CellValue, SalesDatabaseInfo, SalesTable } from "../types";

type Load =
  { kind: "loading" } | { kind: "loaded"; data: SalesDatabaseInfo } | { kind: "failed"; message: string };

/**
 * Browse the sample sales database the SQL agent queries: every table, what
 * each column means, and the first rows. Read-only; no AI calls involved.
 */
export function SalesDataView({ apiUrl }: { apiUrl: string | undefined }) {
  const backendStatus = useBackendStatus(apiUrl);
  const [load, setLoad] = useState<Load>({ kind: "loading" });
  const [selected, setSelected] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => {
    setLoad({ kind: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!apiUrl) return;
    const controller = new AbortController();
    fetchSalesDatabase(apiUrl, controller.signal)
      .then((data) => setLoad({ kind: "loaded", data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setLoad({
          kind: "failed",
          message: error instanceof Error ? error.message : "Could not load the tables.",
        });
      });
    return () => controller.abort();
  }, [apiUrl, attempt]);

  if (!apiUrl) {
    return (
      <Shell>
        <p className="text-ink-muted">
          This page reads the sales database from the backend. Set <code>NEXT_PUBLIC_API_URL</code> to see it.
        </p>
      </Shell>
    );
  }

  const tables = load.kind === "loaded" ? load.data.tables : [];
  const current = tables.find((table) => table.name === selected) ?? tables[0];

  return (
    <>
      <BackendStatusBanner status={backendStatus} />
      <Shell>
        {load.kind === "loaded" && (
          <p className="max-w-3xl text-ink-muted">
            {load.data.company}, with orders from {load.data.period}. These are the tables the
            assistant&apos;s SQL agent can read, through a read-only connection. Ask a data question in the{" "}
            <Link href="/" className="text-accent underline underline-offset-2">
              Workspace
            </Link>{" "}
            and the answer shows the exact SQL it ran.
          </p>
        )}

        {load.kind === "loading" && <p className="text-ink-muted">Loading tables…</p>}

        {load.kind === "failed" && (
          <div role="alert" className="flex flex-wrap items-center gap-3 text-ink">
            <span>{load.message}</span>
            <button
              type="button"
              onClick={retry}
              className="cursor-pointer rounded-lg border border-line-strong px-3 py-1.5 text-[13px] font-medium hover:bg-subtle"
            >
              Try again
            </button>
          </div>
        )}

        {current && (
          <div className="mt-6 grid gap-6 md:grid-cols-[220px_minmax(0,1fr)]">
            <nav aria-label="Tables" className="flex flex-row flex-wrap gap-1 md:flex-col">
              {tables.map((table) => (
                <button
                  key={table.name}
                  type="button"
                  aria-current={table.name === current.name ? "true" : undefined}
                  onClick={() => setSelected(table.name)}
                  className={cn(
                    "flex cursor-pointer items-baseline justify-between gap-3 rounded-lg px-3 py-2 text-left",
                    table.name === current.name
                      ? "bg-muted font-medium text-ink"
                      : "text-ink-muted hover:bg-muted",
                  )}
                >
                  <span className="font-mono text-[13px]">{table.name}</span>
                  <span className="text-xs text-ink-faint">{formatCount(table.rowCount)}</span>
                </button>
              ))}
            </nav>
            <TableDetail table={current} />
          </div>
        )}
      </Shell>
    </>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
      <h1 className="mb-2 font-display text-2xl font-semibold tracking-tight">SQL database</h1>
      {children}
    </main>
  );
}

function TableDetail({ table }: { table: SalesTable }) {
  const shown = table.previewRows.length;
  return (
    <section aria-labelledby="table-title" className="min-w-0">
      <h2 id="table-title" className="font-mono text-lg font-semibold">
        {table.name}
      </h2>
      <p className="mt-1 text-ink-muted">{table.description}</p>

      <h3 className="mt-6 mb-2 text-xs font-semibold tracking-wider text-ink-muted uppercase">Columns</h3>
      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left text-[13px]">
          <thead className="bg-subtle text-xs text-ink-muted">
            <tr>
              <th className="px-3 py-2 font-medium">Column</th>
              <th className="px-3 py-2 font-medium">Type</th>
              <th className="px-3 py-2 font-medium">Meaning</th>
            </tr>
          </thead>
          <tbody>
            {table.columns.map((column) => (
              <tr key={column.name} className="border-t border-line align-top">
                <td className="px-3 py-2 font-mono whitespace-nowrap">{column.name}</td>
                <td className="px-3 py-2 font-mono whitespace-nowrap text-ink-muted">{column.type}</td>
                <td className="px-3 py-2 text-ink-muted">{column.description || "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="mt-6 mb-2 text-xs font-semibold tracking-wider text-ink-muted uppercase">
        First {shown} of {formatCount(table.rowCount)}
      </h3>
      <div className="overflow-x-auto rounded-xl border border-line bg-surface">
        <table className="w-full text-left font-mono text-xs">
          <thead className="bg-subtle text-ink-muted">
            <tr>
              {table.columns.map((column) => (
                <th key={column.name} scope="col" className="px-3 py-2 font-medium whitespace-nowrap">
                  {column.name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {table.previewRows.map((row, i) => (
              <tr key={i} className="border-t border-line">
                {row.map((value, j) => (
                  <td key={j} className="px-3 py-1.5 whitespace-nowrap">
                    <Cell value={value} />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function Cell({ value }: { value: CellValue }) {
  if (value === null) return <span className="text-ink-faint">NULL</span>;
  return <>{String(value)}</>;
}

function formatCount(count: number): string {
  return `${count.toLocaleString("en-US")} ${count === 1 ? "row" : "rows"}`;
}
