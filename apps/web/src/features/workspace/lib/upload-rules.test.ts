import { describe, expect, it } from "vitest";
import { validateUpload, type UploadRules } from "./upload-rules";

const rules: UploadRules = { maxFileSizeBytes: 1000, acceptedExtensions: [".pdf", ".md"] };

describe("validateUpload", () => {
  it("accepts a supported file within the size limit", () => {
    expect(validateUpload({ name: "Report.PDF", size: 500 }, rules)).toBeNull();
  });

  it("rejects unsupported extensions", () => {
    expect(validateUpload({ name: "photo.png", size: 10 }, rules)).toMatch(/Unsupported file type/);
  });

  it("rejects files over the size limit", () => {
    expect(validateUpload({ name: "big.md", size: 2000 }, rules)).toMatch(/larger than/);
  });
});
