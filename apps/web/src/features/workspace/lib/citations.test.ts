import { describe, expect, it } from "vitest";
import { extractCitationIndexes, linkifyCitations, parseCitationHref } from "./citations";

describe("linkifyCitations", () => {
  it("turns [n] markers into #cite-n links", () => {
    expect(linkifyCitations("Keep it cold [1] and log it [12].")).toBe(
      "Keep it cold [1](#cite-1) and log it [12](#cite-12).",
    );
  });

  it("leaves ordinary markdown links alone", () => {
    expect(linkifyCitations("See [docs](https://example.com) [2]")).toBe(
      "See [docs](https://example.com) [2](#cite-2)",
    );
  });

  it("ignores bracketed text that is not a number", () => {
    expect(linkifyCitations("Use [QA-07] form")).toBe("Use [QA-07] form");
  });
});

describe("parseCitationHref", () => {
  it("reads the citation number", () => {
    expect(parseCitationHref("#cite-3")).toBe(3);
  });

  it("returns null for other links", () => {
    expect(parseCitationHref("https://example.com")).toBeNull();
    expect(parseCitationHref(undefined)).toBeNull();
    expect(parseCitationHref("#cite-abc")).toBeNull();
  });
});

describe("extractCitationIndexes", () => {
  it("lists each citation once, in order of appearance", () => {
    expect(extractCitationIndexes("a [2] b [1] c [2]")).toEqual([2, 1]);
  });
});
