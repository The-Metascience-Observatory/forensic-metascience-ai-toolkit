import { displayFirstAuthor } from "./citation.ts";
import type { Paper } from "./store";

const RUN_AT = /^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/;

export type SortKey =
  | "title"
  | "author"
  | "journal"
  | "year"
  | "folder"
  | "run"
  | "version"
  | "verdict"
  | "sev9"
  | "findings"
  | "image"
  | "viewed";

export type SortDir = "asc" | "desc";
export type SortState = { key: SortKey; dir: SortDir };

/** Text columns start A→Z; counts and dates start high→low.
 *
 * `viewed` starts ascending — "no" first — because this table is a work
 * queue, not an alphabet: the useful first click is the one that surfaces the
 * papers nobody has opened yet. Same reason `webapp_index.sort_papers` ranks
 * unreviewed ahead of reviewed. */
export function firstSortDir(key: SortKey): SortDir {
  return key === "title" || key === "author" || key === "journal"
      || key === "folder" || key === "viewed"
    ? "asc"
    : "desc";
}

export function cycleSort(prev: SortState | null, key: SortKey): SortState | null {
  if (prev?.key !== key) return { key, dir: firstSortDir(key) };
  const first = firstSortDir(key);
  if (prev.dir === first) {
    return { key, dir: first === "asc" ? "desc" : "asc" };
  }
  return null;
}

export function defaultSort(_papers?: Paper[]): SortState {
  return { key: "run", dir: "desc" };
}

export function paperRunAt(p: Paper): string | null {
  if (p.analysed_at) return p.analysed_at;
  const name = p.latest_run;
  const run = (p.runs || []).find((r) => r.name === name) || p.runs?.[0];
  return run?.analysed_at ?? null;
}

export function runMs(raw: string | null | undefined): number {
  if (!raw) return NaN;
  const m = RUN_AT.exec(raw.trim());
  if (!m) return NaN;
  return Date.UTC(Number(m[1]), Number(m[2]) - 1, Number(m[3]),
                  Number(m[4]), Number(m[5]));
}

export function compactRunAt(raw: string | null | undefined): string | null {
  if (!raw) return null;
  const m = RUN_AT.exec(raw.trim());
  if (!m) return raw;
  const y = Number(m[1]);
  const mo = Number(m[2]);
  const d = Number(m[3]);
  const hm = `${m[4]}:${m[5]}`;
  const thisY = new Date().getUTCFullYear();
  return y === thisY
    ? `${mo}/${d} ${hm}`
    : `${mo}/${d}/${String(y).slice(2)} ${hm}`;
}

function folderOf(p: Paper): string {
  return p.dir || p.paper_id;
}

function titleOf(p: Paper): string {
  // Harvested titles sometimes store <i>/<sub> as literal text; sort on the
  // words a reader sees, not under "<".
  return (p.title || folderOf(p))
    .replace(/<[^>]+>/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function authorOf(p: Paper): string {
  return displayFirstAuthor(p.first_author || p.authors);
}

function journalOf(p: Paper): string {
  return (p.journal || "").trim();
}

function yearNum(p: Paper): number {
  const y = p.year;
  if (y == null || y === "") return NaN;
  const n = typeof y === "number" ? y : Number(String(y).trim());
  return Number.isFinite(n) ? n : NaN;
}

/** The paper's worst assigned 1-9 rung, or null. */
export function sev9Of(p: { worst_severity_9?: number | null }): number | null {
  return typeof p.worst_severity_9 === "number" ? p.worst_severity_9 : null;
}

/** Higher = more serious. Legacy names rank with the current vocabulary. */
const VERDICT_WEIGHT: Record<string, number> = {
  does_not_reconcile: 3,
  untrustworthy: 3,
  unresolved: 2,
  questionable: 2,
  reconciles: 1,
  trustworthy: 1,
};

function rankOf(raw: string | null | undefined, weights: Record<string, number>): number {
  if (raw == null || raw === "") return NaN;
  const w = weights[String(raw).trim().toLowerCase()];
  return w == null ? NaN : w;
}

/** The count the table shows: findings the IMAGE track did not produce.
 *
 * `undefined` means the index predates the field, which is NOT zero and not
 * `n_findings` either -- on an image-only corpus those two differ by almost
 * everything (310 of 311 problem findings in masliah_papers came from the
 * image track). Absence is shown as absence and sorts last.
 */
export function nonImageFindings(p: Paper): number | null {
  const n = p.n_non_image_findings;
  return typeof n === "number" && Number.isFinite(n) ? n : null;
}

function findingsNum(p: Paper): number {
  const n = nonImageFindings(p);
  return n == null ? NaN : n;
}

/** Four states, and none of them may be spelled as another.
 *
 *  `seen`       somebody opened the review page, or a review decision proves
 *               the paper was open in front of them.
 *  `unseen`     nothing is on file. NOT "nobody has read this paper": view
 *               tracking is younger than the corpus, and a bundle or a PDF
 *               opened outside the workbench cannot report back.
 *  `unknown`    the record beside the paper could not be read.
 *  `unindexed`  this index predates the field and was never asked.
 */
export type ViewState =
  | { code: "seen"; source: "recorded" | "inferred_from_review";
      n: number; first_at: string | null; last_at: string | null;
      viewers: (string | null)[] }
  | { code: "unseen" }
  | { code: "unknown" }
  | { code: "unindexed" };

export function viewState(p: Paper): ViewState {
  const v = p.viewed;
  if (!v || typeof v !== "object") return { code: "unindexed" };
  if (v.source === "unreadable" || v.viewed == null) return { code: "unknown" };
  if (!v.viewed) return { code: "unseen" };
  return {
    code: "seen",
    source: v.source === "inferred_from_review" ? "inferred_from_review"
                                                : "recorded",
    n: typeof v.n_views === "number" ? v.n_views : 0,
    first_at: v.first_at ?? null,
    last_at: v.last_at ?? null,
    viewers: Array.isArray(v.viewers) ? v.viewers : [],
  };
}

function viewerName(n: string | null): string {
  // A viewer who never set a name is not called "anonymous" — nobody chose
  // that. Say what happened.
  return n && n.trim() ? n : "someone who had not set a name";
}

/** The cell. `yes*` marks a view we INFERRED rather than observed — the same
 *  asterisk this table already uses for a mapped legacy severity. */
export function viewedLabel(s: ViewState): string {
  switch (s.code) {
    case "seen": return s.source === "recorded" ? "yes" : "yes*";
    case "unseen": return "no";
    case "unknown": return "?";
    case "unindexed": return "—";
  }
}

/** The hover. Every branch says what it knows and refuses what it doesn't. */
export function viewedTitle(s: ViewState): string {
  switch (s.code) {
    case "seen": {
      if (s.source === "inferred_from_review") {
        const who = viewerName(s.viewers[0] ?? null);
        const when = s.last_at ? ` on ${s.last_at}` : "";
        return `No view is on file, but ${who} recorded a review decision`
          + `${when} — the paper was open in front of somebody. View tracking`
          + ` is younger than that decision.`;
      }
      const names = s.viewers.map(viewerName).join(", ");
      const first = s.first_at ? `first opened ${s.first_at}` : "opened";
      const last = s.last_at && s.last_at !== s.first_at
        ? `, last ${s.last_at}` : "";
      const opens = s.n === 1 ? "1 open" : `${s.n} opens`;
      return `${first}${last} · ${opens} · ${names}`;
    }
    case "unseen":
      return "No view is on file. Views have only been recorded since this"
        + " column shipped, and a bundle or PDF opened outside the workbench"
        + " cannot report back — this is \"nothing recorded\", not \"nobody has"
        + " read it\".";
    case "unknown":
      return "The view record beside this paper could not be read, so whether"
        + " anyone opened it is unknown.";
    case "unindexed":
      return "This index predates view tracking — reload the project page to"
        + " rescan.";
  }
}

function viewedNum(p: Paper): number {
  const s = viewState(p);
  if (s.code === "seen") return 1;
  if (s.code === "unseen") return 0;
  return NaN;   // unknown and unindexed sort last in both directions
}

export function pipelineVersionOf(p: Paper): string {
  const v = p.pipeline_version;
  return typeof v === "string" ? v.trim() : "";
}

/** Missing values sort last in both directions. */
function cmpMissing(aMiss: boolean, bMiss: boolean): number | null {
  if (aMiss && bMiss) return 0;
  if (aMiss) return 1;
  if (bMiss) return -1;
  return null;
}

function cmpNum(a: number, b: number, dir: SortDir): number {
  const miss = cmpMissing(!Number.isFinite(a), !Number.isFinite(b));
  if (miss !== null) return miss;
  return dir === "desc" ? b - a : a - b;
}

function cmpStr(a: string, b: string, dir: SortDir): number {
  const miss = cmpMissing(!a, !b);
  if (miss !== null) return miss;
  const c = a.localeCompare(b, undefined, { sensitivity: "base", numeric: true });
  return dir === "asc" ? c : -c;
}

export function sortPapers(papers: Paper[], sort: SortState | null): Paper[] {
  if (!sort) return papers;
  const signed = [...papers];
  signed.sort((a, b) => {
    switch (sort.key) {
      case "title":
        return cmpStr(titleOf(a), titleOf(b), sort.dir);
      case "author":
        return cmpStr(authorOf(a), authorOf(b), sort.dir);
      case "journal":
        return cmpStr(journalOf(a), journalOf(b), sort.dir);
      case "year":
        return cmpNum(yearNum(a), yearNum(b), sort.dir);
      case "folder":
        return cmpStr(folderOf(a), folderOf(b), sort.dir);
      case "run":
        return cmpNum(runMs(paperRunAt(a)), runMs(paperRunAt(b)), sort.dir);
      case "version":
        // localeCompare with numeric:true orders 0.9.0 < 1.0.0 < 1.10.0 --
        // segment-wise, which a plain string compare gets wrong at 1.10 vs 1.9.
        return cmpStr(pipelineVersionOf(a), pipelineVersionOf(b), sort.dir);
      case "verdict":
        return cmpNum(rankOf(a.verdict, VERDICT_WEIGHT),
                      rankOf(b.verdict, VERDICT_WEIGHT), sort.dir);
      case "sev9":
        return cmpNum(sev9Of(a) ?? Number.NaN, sev9Of(b) ?? Number.NaN, sort.dir);
      case "findings":
        return cmpNum(findingsNum(a), findingsNum(b), sort.dir);
      case "viewed":
        return cmpNum(viewedNum(a), viewedNum(b), sort.dir);
      case "image": {
        const miss = cmpMissing(a.n_image_findings == null, b.n_image_findings == null);
        if (miss !== null) return miss;
        return sort.dir === "desc"
          ? (b.n_image_findings as number) - (a.n_image_findings as number)
          : (a.n_image_findings as number) - (b.n_image_findings as number);
      }
    }
  });
  return signed;
}
