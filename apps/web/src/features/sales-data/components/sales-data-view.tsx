"use client";

import { ArrowRight, Info } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { BackendStatusBanner, useBackendStatus } from "@/features/workspace";
import { cn } from "@/lib/utils";
import { fetchSalesDatabase, fetchTableRows } from "../api";
import { useRemote } from "../hooks/use-remote";
import type { RowsQuery, SalesColumn, SalesTable } from "../types";
import { DataGrid } from "./data-grid";

const PAGE_SIZES = [25, 50, 100] as const;

/**
 * A table browser for the sample sales database, in the style of a database
 * GUI: tabs to pick a table, then every row a page at a time, sortable by any
 * column. Read-only; no AI calls involved.
 */
export function SalesDataView({ apiUrl }: { apiUrl: string | undefined }) {
  const backendStatus = useBackendStatus(apiUrl);
  const database = useRemote(apiUrl ? "tables" : null, (signal) => fetchSalesDatabase(apiUrl!, signal));

  const [selected, setSelected] = useState<string | null>(null);
  const [query, setQuery] = useState<RowsQuery>({ offset: 0, limit: 50, sort: null, order: "asc" });

  const tables = database.data?.tables ?? [];
  const table = tables.find((t) => t.name === selected) ?? tables[0];

  const rows = useRemote(table && apiUrl ? JSON.stringify([table.name, query]) : null, (signal) =>
    fetchTableRows(apiUrl!, table!.name, query, signal),
  );
  // Rows of the table on screen only; while another table loads, the old rows are not shown under new headers.
  const page = rows.data?.table === table?.name ? rows.data : undefined;

  function selectTable(name: string) {
    setSelected(name);
    setQuery((q) => ({ ...q, offset: 0, sort: null, order: "asc" }));
  }

  function sortBy(column: string) {
    // Each click cycles: ascending → descending → back to the default (primary key) order.
    setQuery((q) => {
      if (q.sort !== column) return { ...q, offset: 0, sort: column, order: "asc" };
      if (q.order === "asc") return { ...q, offset: 0, order: "desc" };
      return { ...q, offset: 0, sort: null, order: "asc" };
    });
  }

  if (!apiUrl) {
    return (
      <main className="flex-1 px-6 py-8">
        <h1 className="font-display text-xl font-semibold tracking-tight">SQL database</h1>
        <p className="mt-2 text-ink-muted">
          This page reads the sales database from the backend. Set <code>NEXT_PUBLIC_API_URL</code> to see it.
        </p>
      </main>
    );
  }

  return (
    <>
      <BackendStatusBanner status={backendStatus} />
      <main className="flex min-h-0 flex-1 flex-col">
        <div className="flex flex-wrap items-end gap-x-6 gap-y-2 px-6 pt-5 pb-3">
          <div>
            <h1 className="font-display text-xl font-semibold tracking-tight">SQL database</h1>
            <p className="text-[13px] text-ink-muted">
              {database.data
                ? `Sejuk Beverages (fictional) · ${database.data.period} · read-only`
                : "Sample sales data the SQL agent queries"}
            </p>
          </div>
          <Link
            href="/"
            className="ml-auto flex items-center gap-1.5 rounded-lg border border-line-strong px-3 py-1.5 text-[13px] font-medium text-ink hover:bg-subtle"
          >
            Ask a question about this data
            <ArrowRight aria-hidden="true" className="size-3.5" />
          </Link>
        </div>

        {database.error && <ErrorBar message={database.error} onRetry={database.retry} />}
        {!database.data && !database.error && <p className="px-6 py-4 text-ink-muted">Loading tables…</p>}

        {table && (
          <>
            <TableTabs tables={tables} current={table.name} onSelect={selectTable} />
            <TableToolbar table={table} />

            <div className="mx-6 min-h-[320px] flex-1 overflow-auto rounded-xl border border-line bg-surface">
              {page ? (
                <DataGrid
                  columns={table.columns}
                  rows={page.rows}
                  firstRowNumber={page.offset + 1}
                  sort={query.sort}
                  order={query.order}
                  onSort={sortBy}
                  stale={rows.loading}
                />
              ) : rows.error ? null : (
                <p className="p-4 text-ink-muted">Loading rows…</p>
              )}
            </div>
            {rows.error && <ErrorBar message={rows.error} onRetry={rows.retry} />}

            <Pagination
              total={table.rowCount}
              offset={query.offset}
              limit={query.limit}
              onChange={(offset, limit) => setQuery((q) => ({ ...q, offset, limit }))}
              sortLabel={query.sort ? `${query.sort} ${query.order === "asc" ? "↑" : "↓"}` : null}
            />
          </>
        )}
      </main>
    </>
  );
}

function TableTabs({
  tables,
  current,
  onSelect,
}: {
  tables: SalesTable[];
  current: string;
  onSelect: (name: string) => void;
}) {
  return (
    <div role="tablist" aria-label="Tables" className="flex gap-1 overflow-x-auto border-b border-line px-6">
      {tables.map((t) => {
        const active = t.name === current;
        return (
          <button
            key={t.name}
            type="button"
            role="tab"
            aria-selected={active}
            onClick={() => onSelect(t.name)}
            className={cn(
              "-mb-px flex shrink-0 cursor-pointer items-center gap-2 border-b-2 px-3 py-2 text-[13px] whitespace-nowrap",
              active
                ? "border-accent font-medium text-ink"
                : "border-transparent text-ink-muted hover:text-ink",
            )}
          >
            {t.name}
            <span className="rounded-full bg-muted px-1.5 text-[11px] text-ink-muted tabular-nums">
              {t.rowCount.toLocaleString("en-US")}
            </span>
          </button>
        );
      })}
    </div>
  );
}

function TableToolbar({ table }: { table: SalesTable }) {
  const [showColumns, setShowColumns] = useState(false);
  return (
    <div className="px-6 py-3">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <p className="min-w-0 flex-1 text-[13px] text-ink-muted">{table.description}</p>
        <button
          type="button"
          aria-expanded={showColumns}
          onClick={() => setShowColumns((v) => !v)}
          className="flex cursor-pointer items-center gap-1.5 rounded-lg px-2 py-1 text-[13px] text-ink-muted hover:bg-muted hover:text-ink"
        >
          <Info aria-hidden="true" className="size-3.5" />
          {showColumns ? "Hide column info" : "Column info"}
        </button>
      </div>
      {showColumns && <ColumnInfo columns={table.columns} />}
    </div>
  );
}

function ColumnInfo({ columns }: { columns: SalesColumn[] }) {
  return (
    <dl className="mt-3 grid gap-x-6 gap-y-2 rounded-xl border border-line bg-surface p-4 text-[13px] sm:grid-cols-2 lg:grid-cols-3">
      {columns.map((column) => (
        <div key={column.name}>
          <dt>
            <span className="font-medium">{column.name}</span>{" "}
            <span className="text-xs text-ink-faint">{column.type}</span>
          </dt>
          <dd className="text-ink-muted">{column.description || "—"}</dd>
        </div>
      ))}
    </dl>
  );
}

function Pagination({
  total,
  offset,
  limit,
  onChange,
  sortLabel,
}: {
  total: number;
  offset: number;
  limit: number;
  onChange: (offset: number, limit: number) => void;
  sortLabel: string | null;
}) {
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + limit, total);
  const pageCount = Math.max(1, Math.ceil(total / limit));
  const page = Math.floor(offset / limit) + 1;
  const button =
    "cursor-pointer rounded-lg border border-line-strong px-3 py-1 text-[13px] hover:bg-subtle disabled:cursor-default disabled:opacity-40 disabled:hover:bg-transparent";

  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-6 py-3 text-[13px] text-ink-muted">
      <span className="tabular-nums">
        Rows {first.toLocaleString("en-US")}–{last.toLocaleString("en-US")} of {total.toLocaleString("en-US")}
        {sortLabel && <> · sorted by {sortLabel}</>}
      </span>
      <label className="flex items-center gap-1.5">
        Rows per page
        <select
          value={limit}
          onChange={(event) => onChange(0, Number(event.target.value))}
          className="cursor-pointer rounded-md border border-line-strong bg-surface px-1.5 py-0.5 text-ink"
        >
          {PAGE_SIZES.map((size) => (
            <option key={size} value={size}>
              {size}
            </option>
          ))}
        </select>
      </label>
      <div className="ml-auto flex items-center gap-2">
        <button type="button" className={button} disabled={page <= 1} onClick={() => onChange(0, limit)}>
          First
        </button>
        <button
          type="button"
          className={button}
          disabled={page <= 1}
          onClick={() => onChange(Math.max(0, offset - limit), limit)}
        >
          Previous
        </button>
        <span className="tabular-nums">
          Page {page} of {pageCount}
        </span>
        <button
          type="button"
          className={button}
          disabled={page >= pageCount}
          onClick={() => onChange(offset + limit, limit)}
        >
          Next
        </button>
        <button
          type="button"
          className={button}
          disabled={page >= pageCount}
          onClick={() => onChange((pageCount - 1) * limit, limit)}
        >
          Last
        </button>
      </div>
    </div>
  );
}

function ErrorBar({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div role="alert" className="mx-6 my-3 flex flex-wrap items-center gap-3 text-[13px] text-ink">
      <span>{message}</span>
      <button
        type="button"
        onClick={onRetry}
        className="cursor-pointer rounded-lg border border-line-strong px-3 py-1 font-medium hover:bg-subtle"
      >
        Try again
      </button>
    </div>
  );
}
