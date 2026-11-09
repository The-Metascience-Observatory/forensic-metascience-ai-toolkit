/** Keep in lockstep with `paper_metadata.first_author` (pinned there). */
export function displayFirstAuthor(name: string | null | undefined): string {
  if (!name) return "";
  const s = name.trim();
  if (!s) return "";
  if (s.includes(";")) return s.split(";")[0].trim();
  const parts = s.split(",").map((p) => p.trim()).filter(Boolean);
  if (parts.length >= 3) return parts[0];
  if (parts.length === 2 && parts[1].split(/\s+/).length >= 2) return parts[0];
  return s;
}

/** Keep in lockstep with `paper_metadata.citation_bits` (pinned there). */
export function citationParts(p: {
  journal?: string | null;
  volume?: string | null;
  issue?: string | null;
  year?: string | number | null;
}): { journal: string; loc: string; year: string } {
  const journal = (p.journal || "").trim();
  const volume = String(p.volume ?? "").trim();
  const issue = String(p.issue ?? "").trim();
  const year = p.year == null || p.year === "" ? "" : String(p.year);
  const loc = volume && issue ? `${volume}(${issue})`
    : volume || (issue ? `(${issue})` : "");
  return { journal, loc, year };
}

export function citationLine(p: {
  journal?: string | null;
  volume?: string | null;
  issue?: string | null;
  year?: string | number | null;
}): string {
  const { journal, loc, year } = citationParts(p);
  return [journal, loc, year ? `(${year})` : ""].filter(Boolean).join(" ");
}

/** A bare `10.x/y`, or null when the input is not a DOI we can use.
 *  Accepts a full doi.org URL and strips it. Shared so every surface that
 *  builds a link from a DOI agrees on what counts as one. */
export function normalizeDoi(doi: string | null | undefined): string | null {
  let d = (doi || "").trim();
  if (!d) return null;
  d = d.replace(/^https?:\/\/(dx\.)?doi\.org\//i, "");
  return d.toLowerCase().startsWith("10.") ? d : null;
}

/** `doi.org/10.x/y` → https://doi.org/10.x/y. Null when we have no DOI. */
export function doiLink(doi: string | null | undefined): { href: string; label: string } | null {
  const d = normalizeDoi(doi);
  if (!d) return null;
  return { href: `https://doi.org/${d}`, label: `doi.org/${d}` };
}

/** PubPeer's DOI SEARCH for this paper. Null when we have no DOI.
 *
 *  A SEARCH, not a thread link, and the distinction is the point. A thread
 *  URL on a paper record is a fact -- somebody posted about this paper. This
 *  is a lookup: it answers "has anyone posted?", and an empty result page is
 *  not evidence the paper is clean, only that this search found nothing. The
 *  label says "search" so the link cannot be read as the former.
 *
 *  `encodeURIComponent` is what turns the DOI's slash into `%2F`; PubPeer's
 *  search does not match a raw slash reliably. */
export function pubpeerSearchLink(
  doi: string | null | undefined,
): { href: string; label: string } | null {
  const d = normalizeDoi(doi);
  if (!d) return null;
  return {
    href: `https://pubpeer.com/search?q=${encodeURIComponent(d)}`,
    label: "PubPeer search",
  };
}

/** A recorded publication URL takes precedence over the DOI search fallback. */
export function pubpeerLink(
  doi: string | null | undefined,
  publicationUrl?: string | null,
  title?: string | null,
) {
  if (publicationUrl && /^https:\/\/pubpeer\.com\/publications\/[a-z0-9]+\/?$/i.test(publicationUrl)) {
    return { href: publicationUrl, label: "PubPeer page" };
  }
  const bySearch = pubpeerSearchLink(doi);
  if (bySearch) return bySearch;
  // A paper with no DOI (some journals issue none) can still be looked up by
  // its title. Weaker than a DOI match, so the label says so.
  const t = (title || "").trim();
  if (!t) return null;
  return { href: `https://pubpeer.com/search?q=${encodeURIComponent(t)}`, label: "PubPeer title search" };
}

// ---- reference line for the summary figure (moved from summaryFigure.ts) ----

export type ReferenceMeta = {
  authors_list?: { given?: string | null; family?: string | null; full?: string | null }[] | null;
  authors?: string | null; title?: string | null; journal?: string | null;
  volume?: string | number | null; issue?: string | number | null; pages?: string | null;
  year?: string | number | null;
};

const MAX_AUTHORS = 20;
const initials = (given: string) => given.split(/\s+/).filter(Boolean)
  .map(t => t.split("-").map(p => p.replace(/\.$/, "")).filter(Boolean).map(p => `${p[0].toUpperCase()}.`).join("-"))
  .join(" ");
const trimStop = (s: string) => s.trim().replace(/[.\s]+$/, "");

/** A run of reference text; the journal name is the italic one. */
export type Run = { text: string; italic?: boolean };

/** One reference line: `Chetty, C., Dontula, R., & Lakka, S. S. (2011).
 * Title. *Journal*, 417(2), 874-879.` No DOI -- the figure is for readers,
 * and the DOI is on every other surface. Missing pieces are omitted, never
 * printed as "None"; returns [] when there is nothing but a DOI to say. */
export function referenceRuns(meta: ReferenceMeta | null | undefined): Run[] {
  if (!meta) return [];
  let names = (meta.authors_list || []).map(a => {
    const family = (a.family || "").trim(), given = (a.given || "").trim();
    return family ? (given ? `${family}, ${initials(given)}` : family) : (a.full || "").trim();
  }).filter(Boolean);
  if (!names.length && meta.authors) {
    names = meta.authors.split(";").map(n => n.trim()).filter(Boolean).map(n => {
      const parts = n.split(/\s+/);
      return parts.length > 1 ? `${parts[parts.length - 1]}, ${initials(parts.slice(0, -1).join(" "))}` : n;
    });
  }
  const authors = names.length > MAX_AUTHORS
    ? `${names.slice(0, MAX_AUTHORS - 1).join(", ")}, ... ${names[names.length - 1]}`
    : names.length > 1 ? `${names.slice(0, -1).join(", ")}, & ${names[names.length - 1]}` : names[0] || "";
  const year = meta.year == null || meta.year === "" ? "" : String(meta.year);
  const title = trimStop(meta.title || "");
  const journal = trimStop(meta.journal || "");
  const volume = String(meta.volume ?? "").trim(), issue = String(meta.issue ?? "").trim();
  const rest = [volume ? `${volume}${issue ? `(${issue})` : ""}` : issue ? `(${issue})` : "",
    (meta.pages || "").trim().replace(/-/g, "–")].filter(Boolean).join(", ");
  if (!title && !journal && !rest) return [];
  const lead = [authors && `${trimStop(authors)}.`, year && `(${year}).`, title && `${title}.`].filter(Boolean).join(" ");
  const runs: Run[] = [];
  if (lead) runs.push({ text: journal || rest ? `${lead} ` : lead });
  if (journal) runs.push({ text: journal, italic: true });
  if (journal || rest) runs.push({ text: `${journal && rest ? ", " : ""}${rest}.` });
  return runs;
}

export function formatReference(meta: ReferenceMeta | null | undefined): string {
  return referenceRuns(meta).map(r => r.text).join("");
}

/** Greedy word wrap of styled runs against a width measure (canvas
 * `measureText` in the page, a character count in tests). A word may change
 * style midway ("*Cancer*,"); a single overlong word keeps its line. Each
 * line comes back as runs with adjacent same-style pieces merged. */
export function wrapRuns(runs: Run[], width: number, measure: (s: string, italic: boolean) => number): Run[][] {
  const words: Run[][] = [];
  let word: Run[] = [];
  for (const run of runs) for (const piece of run.text.split(/(\s+)/)) {
    if (!piece) continue;
    if (/^\s+$/.test(piece)) { if (word.length) words.push(word); word = []; }
    else word.push({ text: piece, italic: !!run.italic });
  }
  if (word.length) words.push(word);
  const push = (line: Run[], piece: Run) => {
    const last = line[line.length - 1];
    if (last && !!last.italic === !!piece.italic) last.text += piece.text; else line.push({ ...piece });
  };
  const size = (line: Run[]) => line.reduce((s, r) => s + measure(r.text, !!r.italic), 0);
  const lines: Run[][] = [];
  let line: Run[] = [];
  for (const w of words) {
    const next = line.map(r => ({ ...r }));
    if (next.length) push(next, { text: " ", italic: !!next[next.length - 1].italic && !!w[0].italic });
    w.forEach(r => push(next, r));
    if (line.length && size(next) > width) {
      lines.push(line); line = [];
      w.forEach(r => push(line, r));
    } else line = next;
  }
  if (line.length) lines.push(line);
  return lines;
}

export function wrapText(text: string, width: number, measure: (s: string) => number): string[] {
  return wrapRuns([{ text }], width, s => measure(s)).map(l => l.map(r => r.text).join(""));
}
