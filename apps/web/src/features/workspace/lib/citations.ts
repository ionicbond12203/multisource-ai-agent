/**
 * Citation markers in answer text look like "[1]" or "[12]".
 *
 * Before the markdown is rendered, each marker is turned into a link to
 * "#cite-N". The markdown renderer then swaps those links for <CitationChip>.
 * Existing markdown links such as "[docs](https://…)" are left untouched.
 */
const CITATION_MARKER = /\[(\d{1,3})\](?!\()/g;
export const CITATION_HREF_PREFIX = "#cite-";

export function linkifyCitations(markdown: string): string {
  return markdown.replace(CITATION_MARKER, (_match, n: string) => `[${n}](${CITATION_HREF_PREFIX}${n})`);
}

/** Returns the citation number for a "#cite-N" href, or null for ordinary links. */
export function parseCitationHref(href: string | undefined): number | null {
  if (!href?.startsWith(CITATION_HREF_PREFIX)) return null;
  const value = Number(href.slice(CITATION_HREF_PREFIX.length));
  return Number.isInteger(value) && value > 0 ? value : null;
}

/** Citation numbers in order of first appearance, without duplicates. */
export function extractCitationIndexes(markdown: string): number[] {
  const seen = new Set<number>();
  for (const match of markdown.matchAll(CITATION_MARKER)) {
    seen.add(Number(match[1]));
  }
  return [...seen];
}
