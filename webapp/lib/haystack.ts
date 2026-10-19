/**
 * Cross-node quote matching for HtmlArticlePane (docs/specs/anchors.md §10).
 * Pure on purpose: DOM-Text-shaped `{ data }` pieces in, per-piece spans out,
 * so smoke.mjs can test it without a DOM. The fold mirrors the view-relevant
 * subset of quotes.py `normalise` + `fold_rendering`; like them, it is the
 * identity on digits — no number can enter, leave, or change value under it.
 */

const OPERATORS: Record<string, string> = {
  "≤": "<=", "≥": ">=", "≠": "!=", "≈": "~", "×": "x",
};
const DASHES = "−–—‐‑";
/* A table cell boundary (quotes.py `_CELL_EDGE`). Both the model and our own
   extraction draw a row with pipes, seldom with the same set of columns, so a
   pipe is renderer noise exactly as a dash-space is. Folding it to a space is
   what lets `| Group | F (1.29) = 37.3 |` match the cells of that row. */
const CELL_EDGE = "|";
const QUOTE_MARKS = "‘’“”´`";
const WS = /\s/;

export type Folded = {
  folded: string;
  /** Per folded char: original [start, end) offsets in the raw string. */
  starts: number[];
  ends: number[];
};

/** Fold typography, keeping a folded-index → original-offset map. */
export function foldWithMap(raw: string): Folded {
  const out: string[] = [];
  const starts: number[] = [];
  const ends: number[] = [];
  let space = -1; // start offset of a pending whitespace run, -1 if none
  let i = 0;
  for (const cp of raw) {
    const s = i;
    const e = (i += cp.length);
    if (WS.test(cp) || cp === CELL_EDGE) {
      if (out.length && space < 0) space = s;
      continue;
    }
    const ch = cp === "­" ? "" // soft hyphen: typography, not content
      : OPERATORS[cp] ?? (DASHES.includes(cp) ? "-"
        : QUOTE_MARKS.includes(cp) ? "'"
          : cp.normalize("NFKC").toLowerCase());
    if (!ch) continue;
    // `\s*-\s*` → `-` (fold_rendering: hyphen spacing is renderer noise), so
    // a pending space is dropped around "-" and emitted as one " " otherwise.
    if (space >= 0 && ch !== "-" && out[out.length - 1] !== "-") {
      out.push(" ");
      starts.push(space);
      ends.push(space + 1);
    }
    space = -1;
    for (const c of ch) {
      out.push(c);
      starts.push(s);
      ends.push(e);
    }
  }
  return { folded: out.join(""), starts, ends };
}

export function fold(raw: string): string {
  return foldWithMap(raw).folded;
}

export type NodeSpan = { node: number; start: number; end: number };

/**
 * Every occurrence of `quote` in the concatenation of `pieces`, matched in
 * folded space so a quote spanning inline markup still hits. Each match is a
 * list of per-piece spans in ORIGINAL offsets, ready to become DOM Ranges.
 * Whitespace-only slivers are dropped, never marked. No match → [].
 */
export function findQuoteSpans(
  pieces: { data: string }[],
  quote: string,
): NodeSpan[][] {
  const offs: number[] = [];
  let hay = "";
  for (const p of pieces) {
    offs.push(hay.length);
    hay += p.data;
  }
  const needle = fold(quote);
  if (!needle) return [];
  const { folded, starts, ends } = foldWithMap(hay);
  const matches: NodeSpan[][] = [];
  let from = 0;
  while (from <= folded.length - needle.length) {
    const at = folded.indexOf(needle, from);
    if (at < 0) break;
    const o0 = starts[at];
    const o1 = ends[at + needle.length - 1];
    const spans: NodeSpan[] = [];
    for (let n = 0; n < pieces.length; n++) {
      const start = Math.max(o0, offs[n]) - offs[n];
      const end = Math.min(o1, offs[n] + pieces[n].data.length) - offs[n];
      if (end <= start) continue;
      if (!pieces[n].data.slice(start, end).trim()) continue;
      spans.push({ node: n, start, end });
    }
    if (spans.length) matches.push(spans);
    from = at + needle.length;
  }
  return matches;
}
