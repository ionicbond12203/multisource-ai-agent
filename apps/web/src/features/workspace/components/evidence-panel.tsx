"use client";

import { useId, type KeyboardEvent } from "react";
import type { AssistantMessage, EvidenceTab } from "../types";
import { cn } from "@/lib/utils";
import { AgentSteps } from "./agent-steps";
import { SourceCard } from "./source-card";

const TABS: Array<{ id: EvidenceTab; label: string }> = [
  { id: "sources", label: "Sources" },
  { id: "trace", label: "Trace" },
  { id: "chunks", label: "Retrieved chunks" },
];

interface EvidencePanelProps {
  /** The answer whose evidence is shown; null before the first answer. */
  message: AssistantMessage | null;
  activeSourceIndex: number | null;
  tab: EvidenceTab;
  onTabChange: (tab: EvidenceTab) => void;
  onSelectSource: (messageId: string, sourceIndex: number) => void;
}

export function EvidencePanel({
  message,
  activeSourceIndex,
  tab,
  onTabChange,
  onSelectSource,
}: EvidencePanelProps) {
  const baseId = useId();
  const tabId = (id: EvidenceTab) => `${baseId}-tab-${id}`;
  const panelId = (id: EvidenceTab) => `${baseId}-panel-${id}`;

  // Arrow keys move between tabs (WAI-ARIA tabs pattern).
  function handleKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    const current = TABS.findIndex((t) => t.id === tab);
    const next = (current + (event.key === "ArrowRight" ? 1 : TABS.length - 1)) % TABS.length;
    onTabChange(TABS[next].id);
    document.getElementById(tabId(TABS[next].id))?.focus();
  }

  return (
    <aside aria-label="Evidence" className="flex h-full flex-col border-line bg-surface xl:border-l">
      <div
        role="tablist"
        aria-label="Evidence views"
        onKeyDown={handleKeyDown}
        className="flex gap-1 border-b border-line px-4 pt-2.5"
      >
        {TABS.map((t) => {
          const selected = t.id === tab;
          return (
            <button
              key={t.id}
              id={tabId(t.id)}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={panelId(t.id)}
              tabIndex={selected ? 0 : -1}
              onClick={() => onTabChange(t.id)}
              className={cn(
                "-mb-px cursor-pointer border-b-2 px-2.5 py-2.5 text-sm",
                selected
                  ? "border-accent font-medium text-ink"
                  : "border-transparent text-ink-muted hover:text-ink",
              )}
            >
              {t.label}
              {t.id === "sources" && message && (
                <span className="ml-1 text-xs text-ink-faint">{message.sources.length}</span>
              )}
            </button>
          );
        })}
      </div>

      <div role="tabpanel" id={panelId(tab)} aria-labelledby={tabId(tab)} className="flex flex-col gap-3 p-4">
        {!message ? (
          <p className="text-sm text-ink-muted">Sources for each answer will appear here.</p>
        ) : tab === "sources" ? (
          message.sources.length > 0 ? (
            message.sources.map((source) => (
              <SourceCard
                key={source.index}
                source={source}
                selected={source.index === activeSourceIndex}
                onSelect={(index) => onSelectSource(message.id, index)}
              />
            ))
          ) : (
            <p className="text-sm text-ink-muted">This answer has no sources: nothing relevant was found.</p>
          )
        ) : tab === "trace" ? (
          <AgentSteps steps={message.run.steps} />
        ) : (
          <ChunkList message={message} />
        )}
      </div>
    </aside>
  );
}

/** Every retrieved passage, cited or not, so retrieval quality can be judged. */
function ChunkList({ message }: { message: AssistantMessage }) {
  const chunks = message.sources.flatMap((source) =>
    source.passages.map((passage, i) => ({ key: `${source.index}-${i}`, source, passage })),
  );
  if (chunks.length === 0) return <p className="text-sm text-ink-muted">No chunks were retrieved.</p>;

  return (
    <ul className="flex flex-col gap-2">
      {chunks.map(({ key, source, passage }) => (
        <li key={key} className="rounded-lg border border-line p-3 text-[13px]">
          <div className="mb-1 flex justify-between gap-2 text-xs text-ink-muted">
            <span className="truncate">
              [{source.index}] {source.fileName}
            </span>
            <span className={passage.cited ? "font-medium text-accent-strong" : undefined}>
              {passage.cited ? "Cited" : "Not used"}
            </span>
          </div>
          <p className="text-ink-body">{passage.text}</p>
        </li>
      ))}
    </ul>
  );
}
