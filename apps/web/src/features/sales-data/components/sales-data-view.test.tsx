import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { SalesDatabaseInfo } from "../types";
import { SalesDataView } from "./sales-data-view";

const DATA: SalesDatabaseInfo = {
  company: "Sejuk Beverages Sdn Bhd, a fictional Malaysian drinks distributor",
  period: "1 January to 30 September 2026",
  tables: [
    {
      name: "warehouses",
      description: "Distribution centres that ship the orders.",
      rowCount: 4,
      columns: [
        { name: "id", type: "text", description: "'WH-SA' Shah Alam" },
        { name: "state", type: "text", description: "" },
      ],
      previewRows: [
        ["WH-SA", "Selangor"],
        ["WH-KT", "Pahang"],
      ],
    },
    {
      name: "deliveries",
      description: "One row per order.",
      rowCount: 1577,
      columns: [
        { name: "order_id", type: "integer", description: "orders.id" },
        { name: "delivered_at", type: "timestamp", description: "NULL for cancelled orders" },
      ],
      previewRows: [[1001, null]],
    },
  ],
};

function serve(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve(
        url.endsWith("/health") ? new Response("{}") : new Response(JSON.stringify(body), { status }),
      ),
    ),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("SalesDataView", () => {
  it("lists the tables and shows the first one's columns and rows", async () => {
    serve(DATA);
    render(<SalesDataView apiUrl="https://api.test" />);

    expect(await screen.findByRole("heading", { name: "warehouses" })).toBeInTheDocument();
    const tables = screen.getByRole("navigation", { name: "Tables" });
    expect(within(tables).getByText("1,577 rows")).toBeInTheDocument();
    expect(screen.getByText("'WH-SA' Shah Alam")).toBeInTheDocument();
    expect(screen.getByText("Pahang")).toBeInTheDocument();
    expect(screen.getByText("First 2 of 4 rows")).toBeInTheDocument();
  });

  it("switches tables and shows NULL values", async () => {
    serve(DATA);
    render(<SalesDataView apiUrl="https://api.test" />);
    await userEvent.click(await screen.findByRole("button", { name: /deliveries/ }));

    expect(screen.getByRole("heading", { name: "deliveries" })).toBeInTheDocument();
    expect(screen.getByText("NULL")).toBeInTheDocument();
  });

  it("offers a retry when loading fails", async () => {
    serve({ detail: "boom" }, 500);
    render(<SalesDataView apiUrl="https://api.test" />);
    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent("Could not load the tables (500)."),
    );
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("explains that a backend is needed without one", () => {
    render(<SalesDataView apiUrl={undefined} />);
    expect(screen.getByText(/reads the sales database from the backend/)).toBeInTheDocument();
  });
});
