import type { Source } from "../types";

/**
 * Preview of a source's passages: paper-like text for documents, with the
 * cited passages highlighted, or the SQL query and its result for the sales
 * database.
 * When the backend can return page images or PDF coordinates, replace the
 * document body with a PDF viewer (e.g. react-pdf) and keep this component's props.
 */
export function DocumentPreview({ source }: { source: Source }) {
  if (source.kind === "sql") return <SqlPreview source={source} />;

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

/** The first passage is the SQL that ran, the second its result as a plain-text table. */
function SqlPreview({ source }: { source: Source }) {
  const [query, result] = source.passages;
  return (
    <div className="flex flex-col gap-3 bg-muted p-4">
      {query && <CodeBlock label="Read-only query" text={query.text} />}
      {result && <CodeBlock label="Result" text={result.text} />}
    </div>
  );
}

function CodeBlock({ label, text }: { label: string; text: string }) {
  return (
    <figure className="m-0">
      <figcaption className="mb-1.5 text-[11px] text-ink-faint">{label}</figcaption>
      <pre className="overflow-x-auto rounded bg-surface px-3.5 py-3 font-mono text-[11px] leading-[1.6] whitespace-pre text-ink shadow-sm">
        {text}
      </pre>
    </figure>
  );
}
