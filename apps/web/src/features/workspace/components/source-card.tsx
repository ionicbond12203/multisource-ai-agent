import type { Source } from "../types";
import { cn } from "@/lib/utils";
import { DocumentPreview } from "./document-preview";

interface SourceCardProps {
  source: Source;
  selected: boolean;
  onSelect: (index: number) => void;
}

/** One cited source. The selected card expands to show the highlighted passages. */
export function SourceCard({ source, selected, onSelect }: SourceCardProps) {
  const citedCount = source.passages.filter((passage) => passage.cited).length;
  const isSql = source.kind === "sql";

  return (
    <div
      className={cn(
        "overflow-hidden rounded-xl border bg-surface",
        selected ? "border-[1.5px] border-accent" : "border-line",
      )}
    >
      <button
        type="button"
        aria-expanded={selected}
        onClick={() => onSelect(source.index)}
        className={cn(
          "flex w-full cursor-pointer items-center gap-2.5 px-3 py-2.5 text-left",
          selected ? "bg-accent-tint" : "hover:bg-subtle",
        )}
      >
        <span
          className={cn(
            "flex h-[18px] min-w-[18px] items-center justify-center rounded-[5px] px-1.5 text-[11px] font-semibold",
            selected ? "bg-accent text-white" : "bg-accent-soft text-accent-strong",
          )}
        >
          {source.index}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-[13px] font-medium">{source.fileName}</span>
          <span className="block text-xs text-ink-muted">{source.location}</span>
        </span>
        {isSql ? (
          <span className="font-mono text-xs text-ink-muted">SQL</span>
        ) : (
          <span className="font-mono text-xs text-ink-muted" title="Relevance score">
            {source.score.toFixed(2)}
          </span>
        )}
      </button>

      {selected && (
        <>
          <DocumentPreview source={source} />
          <p className="px-3 py-2 text-xs text-ink-muted">
            {isSql
              ? "The answer is based on this query result"
              : `Highlighted: ${citedCount} ${citedCount === 1 ? "passage" : "passages"} used in the answer`}
          </p>
        </>
      )}
    </div>
  );
}
