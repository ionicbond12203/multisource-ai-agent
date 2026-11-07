import { CircleAlert, FileText, Loader2, X } from "lucide-react";
import type { KnowledgeFile } from "../types";
import { cn } from "@/lib/utils";

const STAGE_LABELS = {
  parsing: "Reading text",
  chunking: "Splitting into chunks",
  embedding: "Embedding",
  indexing: "Indexing",
} as const;

interface KnowledgeFileRowProps {
  file: KnowledgeFile;
  onToggle: (fileId: string) => void;
  onRemove: (fileId: string) => void;
  onRunOcr: (fileId: string) => void;
}

export function KnowledgeFileRow({ file, onToggle, onRemove, onRunOcr }: KnowledgeFileRowProps) {
  const { status } = file;
  const failed = status.kind === "failed";
  const progress = getProgress(file);

  return (
    <li
      className={cn(
        "flex items-center gap-2.5 rounded-lg border bg-surface px-2.5 py-2",
        failed ? "border-danger-line" : "border-line",
      )}
    >
      {failed ? (
        <CircleAlert aria-hidden="true" className="size-[18px] shrink-0 text-danger" strokeWidth={1.6} />
      ) : status.kind === "ready" ? (
        <FileText aria-hidden="true" className="size-[18px] shrink-0 text-ink-muted" strokeWidth={1.6} />
      ) : (
        <Loader2
          aria-hidden="true"
          className="size-[18px] shrink-0 animate-spin text-accent"
          strokeWidth={1.6}
        />
      )}

      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium" title={file.name}>
          {file.name}
        </p>
        <p className={cn("text-xs", statusColor(file))}>{statusText(file)}</p>
        {progress !== null && (
          <div
            role="progressbar"
            aria-label={`${file.name} progress`}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={Math.round(progress * 100)}
            className="mt-1 h-[3px] overflow-hidden rounded-full bg-line"
          >
            <div className="h-full bg-accent transition-[width]" style={{ width: `${progress * 100}%` }} />
          </div>
        )}
      </div>

      {status.kind === "ready" && (
        <input
          type="checkbox"
          checked={file.enabled}
          onChange={() => onToggle(file.id)}
          aria-label={`Use ${file.name} in answers`}
          className="size-4 shrink-0 cursor-pointer accent-accent"
        />
      )}
      {failed && status.recovery === "ocr" && (
        <button
          type="button"
          onClick={() => onRunOcr(file.id)}
          className="shrink-0 cursor-pointer rounded-md px-1.5 py-1 text-xs font-medium text-accent hover:bg-accent-soft"
        >
          Run OCR
        </button>
      )}
      {failed && status.recovery !== "ocr" && (
        <button
          type="button"
          onClick={() => onRemove(file.id)}
          aria-label={`Remove ${file.name}`}
          className="shrink-0 cursor-pointer rounded-md p-1 text-ink-muted hover:bg-muted"
        >
          <X aria-hidden="true" className="size-4" />
        </button>
      )}
    </li>
  );
}

function statusText({ status }: KnowledgeFile): string {
  switch (status.kind) {
    case "uploading":
      return `Uploading · ${Math.round(status.progress * 100)}%`;
    case "processing":
      return status.progress === undefined
        ? `${STAGE_LABELS[status.stage]}…`
        : `${STAGE_LABELS[status.stage]} · ${Math.round(status.progress * 100)}%`;
    case "ready":
      return `Ready · ${status.pages} pages`;
    case "failed":
      return status.reason;
  }
}

function statusColor({ status }: KnowledgeFile): string {
  if (status.kind === "ready") return "text-success";
  if (status.kind === "failed") return "text-danger";
  return "text-ink-muted";
}

/** 0–1 while uploading or when the backend reports stage progress; null otherwise. */
function getProgress({ status }: KnowledgeFile): number | null {
  if (status.kind === "uploading") return status.progress;
  if (status.kind === "processing" && status.progress !== undefined) return status.progress;
  return null;
}
