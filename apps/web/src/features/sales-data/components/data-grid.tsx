import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { CellValue, SalesColumn, SortOrder } from "../types";

interface DataGridProps {
  columns: SalesColumn[];
  rows: CellValue[][];
  /** Row number of the first row, for the # column (1-based). */
  firstRowNumber: number;
  sort: string | null;
  order: SortOrder;
  onSort: (column: string) => void;
  /** Dims the rows while the next page loads. */
  stale?: boolean;
}

/** Spreadsheet-style table with a sticky header. Click a column header to sort by it. */
export function DataGrid({ columns, rows, firstRowNumber, sort, order, onSort, stale }: DataGridProps) {
  return (
    <table className={cn("w-full border-separate border-spacing-0 text-[13px]", stale && "opacity-50")}>
      <thead>
        <tr>
          <th
            scope="col"
            className="sticky top-0 z-10 w-12 border-r border-b border-line bg-subtle px-3 py-2 text-right text-xs font-normal text-ink-faint"
          >
            #
          </th>
          {columns.map((column) => {
            const active = sort === column.name;
            const SortIcon = !active ? ArrowUpDown : order === "asc" ? ArrowUp : ArrowDown;
            return (
              <th
                key={column.name}
                scope="col"
                aria-sort={active ? (order === "asc" ? "ascending" : "descending") : "none"}
                className="sticky top-0 z-10 border-r border-b border-line bg-subtle p-0 text-left font-normal last:border-r-0"
              >
                <button
                  type="button"
                  onClick={() => onSort(column.name)}
                  title={column.description || undefined}
                  className="group flex w-full cursor-pointer items-center gap-2 px-3 py-1.5 text-left hover:bg-muted"
                >
                  <span className="min-w-0">
                    <span className="block font-medium whitespace-nowrap text-ink">{column.name}</span>
                    <span className="block text-[11px] whitespace-nowrap text-ink-faint">{column.type}</span>
                  </span>
                  <SortIcon
                    aria-hidden="true"
                    className={cn(
                      "ml-auto size-3.5 shrink-0",
                      active ? "text-accent" : "text-ink-faint opacity-0 group-hover:opacity-100",
                    )}
                  />
                </button>
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, i) => (
          <tr key={i} className="hover:bg-subtle">
            <td className="border-r border-b border-line px-3 py-1.5 text-right text-xs text-ink-faint tabular-nums">
              {firstRowNumber + i}
            </td>
            {row.map((value, j) => (
              <td
                key={j}
                className={cn(
                  "border-r border-b border-line px-3 py-1.5 whitespace-nowrap last:border-r-0",
                  isNumeric(columns[j]?.type) && "text-right tabular-nums",
                )}
              >
                <Cell value={value} />
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function Cell({ value }: { value: CellValue }) {
  if (value === null) return <span className="text-ink-faint italic">NULL</span>;
  if (typeof value === "boolean") {
    return <span className={value ? "text-ink" : "text-ink-muted"}>{String(value)}</span>;
  }
  return <>{String(value)}</>;
}

function isNumeric(type: string | undefined): boolean {
  return !!type && /^(integer|numeric|bigint|smallint|real|double)/.test(type);
}
