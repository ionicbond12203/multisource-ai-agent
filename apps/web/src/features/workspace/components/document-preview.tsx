import type { Source } from "../types";

/**
 * Paper-like preview of the retrieved passages, with the cited ones highlighted.
 * When the backend can return page images or PDF coordinates, replace the body
 * with a PDF viewer (e.g. react-pdf) and keep this component's props.
 */
export function DocumentPreview({ source }: { source: Source }) {
  return (
    <div className="bg-muted p-4">
      <article className="rounded bg-surface px-5 py-5 font-serif text-xs leading-[1.65] text-ink-body shadow-sm">
        {source.heading && <p className="mb-2.5 font-sans text-[11px] text-ink-faint">{source.heading}</p>}
        {source.passages.map((passage, i) =>
          passage.cited ? (
            <p key={i} className="mb-2 last:mb-0">
              <mark className="block rounded-[3px] bg-highlight px-1.5 py-1 text-ink shadow-[inset_2px_0_0_var(--color-highlight-edge)]">
                {passage.text}
              </mark>
            </p>
          ) : (
            <p key={i} className="mb-2 last:mb-0">
              {passage.text}
            </p>
          ),
        )}
      </article>
    </div>
  );
}
