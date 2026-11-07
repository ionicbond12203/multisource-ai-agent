import { siteConfig } from "@/config/site";
import { formatBytes } from "@/lib/utils";

export interface UploadRules {
  maxFileSizeBytes: number;
  acceptedExtensions: readonly string[];
}

/** Returns a user-facing reason the file can't be uploaded, or null if it's fine. */
export function validateUpload(
  file: Pick<File, "name" | "size">,
  rules: UploadRules = siteConfig.upload,
): string | null {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!rules.acceptedExtensions.includes(extension)) {
    return `Unsupported file type. Use ${rules.acceptedExtensions.join(", ")}.`;
  }
  if (file.size > rules.maxFileSizeBytes) {
    return `File is larger than ${formatBytes(rules.maxFileSizeBytes)}.`;
  }
  return null;
}
