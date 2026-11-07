import type { Source } from "../types";
import { cn } from "@/lib/utils";

interface CitationChipProps {
  index: number;
  /** Undefined when the answer cites a number that has no matching source. */
  source?: Source;
  active?: boolean;
  onSelect?: (index: number) => void;
  className?: string;
}

/** Small numbered button inside an answer. Selecting it shows the source in the evidence panel. */
export function CitationChip({ index, source, active = false, onSelect, className }: CitationChipProps) {
  const label = source ? `Source ${index}: ${source.fileName}, ${source.location}` : `Source ${index}`;

  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={active}
      title={source ? `${source.fileName} · ${source.location}` : undefined}
      onClick={() => onSelect?.(index)}
      className={cn(
        "mx-0.5 inline-flex h-[18px] min-w-[18px] cursor-pointer items-center justify-center rounded-[5px] px-1.5 align-[2px] font-sans text-[11px] leading-none font-semibold transition-colors",
        active
          ? "bg-accent text-white"
          : "bg-accent-soft text-accent-strong hover:bg-accent hover:text-white",
        className,
      )}
    >
      {index}
    </button>
  );
}
