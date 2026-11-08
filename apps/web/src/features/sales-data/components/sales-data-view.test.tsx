import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SalesDatabaseInfo, TableRows } from "../types";
import { SalesDataView } from "./sales-data-view";

const DATABASE: SalesDatabaseInfo = {
  company: "Sejuk Beverages Sdn Bhd, a fictional Malaysian drinks distributor",
  period: "1 January to 30 September 2026",
  tables: [
    {
      name: "orders",
      description: "One row per customer order.",
      rowCount: 120,
      primaryKey: ["id"],
      columns: [
        { name: "id", type: "integer", description: "" },
        { name: "status", type: "text", description: "'delivered' | 'cancelled' | 'returned'" },
      ],
    },
    {
      name: "deliveries",
      description: "One row per order.",
      rowCount: 3,
      primaryKey: ["order_id"],
      columns: [
        { name: "order_id", type: "integer", description: "orders.id" },
        { name: "delivered_at", type: "timestamp", description: "NULL for cancelled orders" },
      ],
    },
  ],
};

/** Fake backend: serves the table list and pages of generated rows, and records each rows request. */
function fakeBackend({ failRows = false } = {}) {
  const rowRequests: URL[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((input: string) => {
      const url = new URL(input);
      if (url.pathname === "/health") return Promise.resolve(new Response("{}"));
      if (url.pathname === "/sales/tables") return Promise.resolve(Response.json(DATABASE));
      rowRequests.push(url);
      if (failRows)
        return Promise.resolve(Response.json({ detail: "Database unavailable." }, { status: 503 }));
      const table = url.pathname.split("/")[3];
      const offset = Number(url.searchParams.get("offset"));
      const limit = Number(url.searchParams.get("limit"));
      const body: TableRows = {
        table,
        columns: table === "orders" ? ["id", "status"] : ["order_id", "delivered_at"],
        rows:
          table === "orders"
            ? Array.from({ length: Math.min(limit, 120 - offset) }, (_, i) => [
                1000 + offset + i,
                "delivered",
              ])
            : [[1, null]],
        total: table === "orders" ? 120 : 3,
        offset,
        limit,
        order: (url.searchParams.get("order") as "asc" | "desc") ?? "asc",
        sort: url.searchParams.get("sort") ?? undefined,
      };
      return Promise.resolve(Response.json(body));
    }),
  );
  return rowRequests;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SalesDataView", () => {
  it("shows the first table's rows in a grid with tabs for every table", async () => {
    fakeBackend();
    render(<SalesDataView apiUrl="https://api.test" />);

    expect(await screen.findByText("1049")).toBeInTheDocument(); // last row of page 1 (50 rows)
    const tabs = screen.getByRole("tablist", { name: "Tables" });
    expect(within(tabs).getByRole("tab", { name: /orders/ })).toHaveAttribute("aria-selected", "true");
    expect(within(tabs).getByRole("tab", { name: /deliveries/ })).toBeInTheDocument();
    expect(screen.getByText("Rows 1–50 of 120")).toBeInTheDocument();
    expect(screen.getByText("Page 1 of 3")).toBeInTheDocument();
  });

  it("pages through every row", async () => {
    const requests = fakeBackend();
    render(<SalesDataView apiUrl="https://api.test" />);
    await screen.findByText("1049");

    await userEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("1099")).toBeInTheDocument();
    expect(requests.at(-1)?.searchParams.get("offset")).toBe("50");

    await userEvent.click(screen.getByRole("button", { name: "Last" }));
    expect(await screen.findByText("Rows 101–120 of 120")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("sorts by a column: ascending, descending, then back to default", async () => {
    const requests = fakeBackend();
    render(<SalesDataView apiUrl="https://api.test" />);
    await screen.findByText("1049");
    const header = () => screen.getByRole("columnheader", { name: /status/ });

    await userEvent.click(within(header()).getByRole("button"));
    await waitFor(() => expect(requests.at(-1)?.searchParams.get("sort")).toBe("status"));
    expect(requests.at(-1)?.searchParams.get("order")).toBe("asc");
    await waitFor(() => expect(header()).toHaveAttribute("aria-sort", "ascending"));

    await userEvent.click(within(header()).getByRole("button"));
    await waitFor(() => expect(requests.at(-1)?.searchParams.get("order")).toBe("desc"));

    await userEvent.click(within(header()).getByRole("button"));
    await waitFor(() => expect(requests.at(-1)?.searchParams.has("sort")).toBe(false));
  });

  it("switches tables and shows NULL values", async () => {
    fakeBackend();
    render(<SalesDataView apiUrl="https://api.test" />);
    await screen.findByText("1049");

    await userEvent.click(screen.getByRole("tab", { name: /deliveries/ }));
    expect(await screen.findByText("NULL")).toBeInTheDocument();
    expect(screen.getByText("Rows 1–3 of 3")).toBeInTheDocument();
  });

  it("shows column meanings on request", async () => {
    fakeBackend();
    render(<SalesDataView apiUrl="https://api.test" />);
    await screen.findByText("1049");
    await userEvent.click(screen.getByRole("button", { name: "Column info" }));
    expect(screen.getByText("'delivered' | 'cancelled' | 'returned'")).toBeInTheDocument();
  });

  it("explains errors and offers a retry", async () => {
    fakeBackend({ failRows: true });
    render(<SalesDataView apiUrl="https://api.test" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Database unavailable.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("explains that a backend is needed without one", () => {
    render(<SalesDataView apiUrl={undefined} />);
    expect(screen.getByText(/reads the sales database from the backend/)).toBeInTheDocument();
  });
});
