import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Source } from "../types";
import { SourceCard } from "./source-card";

const sqlSource: Source = {
  kind: "sql",
  index: 1,
  fileId: "sales-db",
  fileName: "Sales database",
  location: "SQL query · 2 rows",
  heading: "Query and result",
  score: 1,
  passages: [
    { text: "SELECT\n  state\nFROM warehouses\nLIMIT 200", cited: true },
    { text: "Result: 2 rows\nstate\nPahang\nJohor", cited: true },
  ],
};

describe("SourceCard", () => {
  it("shows a SQL source as the query and its result, keeping line breaks", () => {
    render(<SourceCard source={sqlSource} selected onSelect={() => {}} />);

    expect(screen.getByText("Read-only query")).toBeInTheDocument();
    const [query, result] = screen.getAllByText(/./, { selector: "pre" });
    expect(query.textContent).toBe("SELECT\n  state\nFROM warehouses\nLIMIT 200");
    expect(result.textContent).toContain("Pahang\nJohor");
    // A relevance score means nothing for a query result.
    expect(screen.queryByTitle("Relevance score")).not.toBeInTheDocument();
    expect(screen.getByText("The answer is based on this query result")).toBeInTheDocument();
  });

  it("shows a document source with its relevance score", () => {
    render(
      <SourceCard source={{ ...sqlSource, kind: undefined, score: 0.82 }} selected onSelect={() => {}} />,
    );
    expect(screen.getByTitle("Relevance score")).toHaveTextContent("0.82");
    expect(screen.queryByText("Read-only query")).not.toBeInTheDocument();
  });
});
