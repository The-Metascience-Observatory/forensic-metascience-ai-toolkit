import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Dispatch, SetStateAction } from "react";
import useSWR, { mutate as mutateGlobal, type State, unstable_serialize, useSWRConfig } from "swr";

import { readReviewer } from "../../../../ReviewerChip";
import { errorMessage, getJson, postJson } from "@/lib/getJson";
import { GROUP_KEY, readGrouped } from "@/lib/findingGroups";
import type { Article, Issue, ReviewState } from "@/lib/types/review";

// `Reviewer` renders the read's paper, source, headline and nav blocks and the
// paper-level review fields (PubPeer url, note) as it did when this hook held
// them as `any`; it still receives them that way. The hook's own reads and
// the splice are typed below (`PaperRead`, `Issue`).
/* eslint-disable @typescript-eslint/no-explicit-any */
type Loose = Record<string, any>;
type PageData = any;
type PageIssue = any;
/* eslint-enable @typescript-eslint/no-explicit-any */
type Review = ReviewState & { paper: Loose };
type Locator = { issue_id: string; [key: string]: unknown };
type Locators = { locators?: Locator[] };
type PaperIssues = Loose & {
  issues: Issue[]; review?: Review; focus_index?: number; latest_run?: string; pagination: Loose;
};
/** `/api/paper` as the service returns it. The hook reads the fields named
 *  here; `Reviewer` reads the rest (nav, source, headline, …) as before. */
type PaperRead = Loose & {
  paper: Loose & { dir: string }; issues: PaperIssues; locators?: Locators; article?: Article;
};
type SourceRead = { article?: Article; locators?: Locators; error?: string };
type DetailRead = { issue?: Issue; locators?: Locators; error?: string };
type PaperKey = ["paper", string, string, string | null, string | null, number, boolean, string | null];
type SourceKey = ["source", string, string, string, string];
type DetailKey = ["issue_detail", string, string, string | null];

const REFRESH_MS = 30000;
const NO_ISSUES: Issue[] = [];

function paperUrl([, project, slug, dir, run, offset, grouped, finding]: PaperKey) {
  return `/api/paper?offset=${offset}&group=${grouped ? 1 : 0}&project=${encodeURIComponent(project)}&slug=${encodeURIComponent(slug)}${dir ? `&dir=${encodeURIComponent(dir)}` : ""}${run ? `&run=${encodeURIComponent(run)}` : ""}${finding ? `&finding=${encodeURIComponent(finding)}` : ""}`;
}
const fetchPaper = (key: PaperKey) => getJson<PaperRead>(paperUrl(key));
const fetchSource = ([, project, slug, dir, run]: SourceKey) =>
  getJson<SourceRead>(`/api/workbench?${new URLSearchParams({ method: "source", project, slug, dir, run })}`);
const fetchDetail = ([, project, finding, run]: DetailKey) =>
  getJson<DetailRead>(`/api/workbench?${new URLSearchParams({ method: "issue_detail", project, finding, ...(run ? { run } : {}) })}`);
const detailKeyOf = (project: string, row: Issue): DetailKey | null =>
  row.detail_key == null || row.detail_loaded ? null : ["issue_detail", project, String(row.detail_key), row.run ?? null];

/** The paper page's data: the `/api/paper` read (paged, grouped, scoped to a
 *  run and opened on a named finding), its `/api/workbench` source follow-up,
 *  the per-finding detail, the viewed ping and the `/api/review` writes.
 *  `Reviewer` keeps the layout and the jump/view state.
 *
 *  Each read is an SWR key; the page is derived from them, so a refresh
 *  (30 s, focus, `workbench-review-synced`) never discards a loaded detail. */
export function usePaperReview({ project, slug, dir, run, focusFinding }: {
  project: string; slug: string; dir?: string | null;
  /** `?run=` and `?finding=` from the URL, read by the caller. */
  run: string | null; focusFinding: string | null;
}) {
  const { cache } = useSWRConfig();
  const [offset,setOffset]=useState(0);
  // Group Findings: on by default, per reader (localStorage), applied by the
  // service before pagination. Read once on mount; null until then, so the
  // first fetch waits rather than fetching ungrouped and refetching.
  const [grouped,setGrouped]=useState<boolean|null>(null);
  useEffect(()=>{let v=true;try{v=readGrouped(window.localStorage.getItem(GROUP_KEY));}catch{/* storage unavailable */}setGrouped(v);},[]);
  const onGrouped=useCallback((on:boolean)=>{setGrouped(on);setOffset(0);try{window.localStorage.setItem(GROUP_KEY,on?"1":"0");}catch{/* ok */}},[]);
  // The review as last returned by the service: the paper read, or a save.
  const [reviewState, setReviewState] = useState<Review | null>(null);
  // The `?finding=` focus is consumed once the page holding it is on screen,
  // so paging and j/k afterwards are the reader's own.
  const [consumedFinding, setConsumedFinding] = useState<string | null>(null);
  const finding = focusFinding && consumedFinding !== focusFinding ? focusFinding : null;
  const saveChain = useRef(Promise.resolve());

  // Record that a HUMAN opened this paper. CLIENT-SIDE ON PURPOSE: the stats
  // page links here with next/link, which prefetches on viewport entry and
  // renders the server component -- recording there would mark two hundred
  // papers viewed by scrolling a page. An effect does not run for a prefetch.
  //
  // Keyed on the paper, not on `run`: switching between two review directories
  // is not a second view. The ref survives StrictMode's double mount, and the
  // Python side ignores a repeat at the same instant even if it is defeated.
  // Fire and forget -- a view is not a decision, and a failed ping must never
  // be something the reviewer has to look at.
  const viewedRef = useRef<string | null>(null);
  useEffect(() => {
    const key = `${project}\u0000${slug}\u0000${dir || ""}`;
    if (viewedRef.current === key) return;
    viewedRef.current = key;
    fetch("/api/viewed", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ project, slug, dir: dir || undefined,
                             viewer: readReviewer() || null }),
      keepalive: true,
    }).catch(() => { /* nothing here is worth interrupting a review for */ });
  }, [project, slug, dir]);

  // The focused row belongs to a page read: a new page (or paper, run,
  // grouping) starts at its first row, until the read names a focus index.
  const pageStamp = JSON.stringify([project, slug, dir ?? null, run ?? null, offset, grouped]);
  const [atState, setAtState] = useState<{ stamp: string; index: number }>({ stamp: pageStamp, index: 0 });
  const at = atState.stamp === pageStamp ? atState.index : 0;
  const setAt: Dispatch<SetStateAction<number>> = useCallback((value) => setAtState((prev) => {
    const current = prev.stamp === pageStamp ? prev.index : 0;
    return { stamp: pageStamp, index: typeof value === "function" ? value(current) : value };
  }), [pageStamp]);

  const paperKey: PaperKey | null =
    grouped === null ? null : ["paper", project, slug, dir ?? null, run ?? null, offset, grouped, finding];
  const paper = useSWR<PaperRead, Error>(paperKey, fetchPaper, {
    refreshInterval: REFRESH_MS,
    revalidateOnFocus: true,
    refreshWhenHidden: false,
    onSuccess: (body) => {
      setReviewState(body.issues?.review || { issues: {}, paper: {} });
      const fi = body.issues?.focus_index;
      if (typeof fi !== "number") return;
      // The service served the page holding the finding. If that is not the
      // page asked for, adopt its offset and ask again WITH the finding, so
      // the two agree; once they do, the focus is consumed.
      const po = body.issues?.pagination?.offset;
      if (typeof po === "number" && po !== offset) setOffset(po);
      else if (finding) {
        // The same body answers the finding-less key, so dropping `finding`
        // from the key does not blank the page while it revalidates.
        void mutateGlobal(["paper", project, slug, dir ?? null, run ?? null, offset, grouped === true, null] satisfies PaperKey, body, { revalidate: false });
        setConsumedFinding(finding);
      }
      setAt(fi);
    },
  });
  const body = paper.data;
  useEffect(() => {
    const synced = () => void paper.mutate();
    window.addEventListener("workbench-review-synced", synced);
    return () => window.removeEventListener("workbench-review-synced", synced);
  }, [paper.mutate]);

  const sourceKey: SourceKey | null = body ? ["source", project, slug, body.paper.dir, run || "latest"] : null;
  const source = useSWR<SourceRead, Error>(sourceKey, fetchSource, { revalidateOnFocus: false });

  const rows: Issue[] = body?.issues?.issues ?? NO_ISSUES;
  // The finding's OWN run: the service loads that run's findings to find
  // this one. Without it the detail read "latest", which a partial run is
  // never part of, and every such finding failed "Finding not in this project".
  const detail = useSWR<DetailRead, Error>(rows[at] ? detailKeyOf(project, rows[at]) : null, fetchDetail, {
    revalidateOnFocus: false, revalidateIfStale: false, revalidateOnReconnect: false,
  });

  const data = useMemo(() => {
    if (!body) return null;
    // Every detail read so far, from the SWR cache (the focused row's is
    // `detail.data`; the dependency makes this recompute when it lands).
    const detailOf = (row: Issue): DetailRead | undefined => {
      const key = detailKeyOf(project, row);
      return key ? (cache.get(unstable_serialize(key)) as State<DetailRead> | undefined)?.data : undefined;
    };
    const read = rows.map((row) => [row, detailOf(row)?.issue ? detailOf(row) : undefined] as const);
    // The detail replaces the summary row but not the LIST's facts about it:
    // its group, its place in the list and its current judgments come from
    // the paper read.
    const issues: Issue[] = read.map(([row, d]) => d?.issue
      ? { ...d.issue, group: row.group, location_basis: row.location_basis, priority: d.issue.priority ?? row.priority,
          ...(row.reviews !== undefined ? { reviews: row.reviews } : {}) }
      : row);
    const base = body.locators?.locators?.length ? body.locators : source.data?.locators;
    let locators: Locator[] = base?.locators || [];
    for (const [, d] of read) {
      if (!d?.issue) continue;
      const id = d.issue.id;
      locators = [...locators.filter((l) => l.issue_id !== id), ...(d.locators?.locators || [])];
    }
    const article: Article | undefined = source.data?.article
      ?? (source.error ? { mode: "none", warning: errorMessage(source.error) } : body.article);
    const view: PaperRead = { ...body, article, locators: { locators }, issues: body.issues ? { ...body.issues, issues } : body.issues };
    return view;
  }, [body, rows, source.data, source.error, detail.data, cache, project]);
  const issues: Issue[] = data?.issues?.issues ?? NO_ISSUES;
  const review: Review | null = reviewState ?? (body ? body.issues?.review || { issues: {}, paper: {} } : null);
  // A failed refresh keeps the page; only a page that never loaded is an error.
  const err = paper.error && !body ? errorMessage(paper.error) : null;
  const detailError = detail.error ? errorMessage(detail.error) : "";

  const paperDir = body?.paper?.dir, latestRun = body?.issues?.latest_run;
  const save = useCallback((patch: Record<string, unknown>) => {
    const reviewer = readReviewer();
    if (!reviewer) {
      alert("Set your name in the header first. Decisions are stamped with it.");
      return;
    }
    const run = async () => {
      // Paper-level events (__paper__ complete / PubPeer) are read from the
      // comprehensive run on screen. A finding-level event stays on that
      // finding's own run. Never fall through to paper.latest_run or to
      // whichever finding happens to have focus.
      const owningRun = "issue_id" in patch
        ? (issues[at]?.run || latestRun)
        : latestRun;
      if (!owningRun) {
        alert("No run is on screen to attach this decision to.");
        return;
      }
      let saved: { review: Review };
      try {
        saved = await postJson<{ review: Review }>("/api/review", {
          project, slug, dir: paperDir || dir, reviewer,
          patch: { ...patch, run: owningRun },
        });
      } catch (e) {
        alert(errorMessage(e) || "save failed");
        return;
      }
      setReviewState(saved.review); window.dispatchEvent(new Event("workbench-review"));
    };
    saveChain.current = saveChain.current.then(run, run);
  }, [project, slug, dir, paperDir, latestRun, issues, at]);

  return { data: data as PageData, err, issues: issues as PageIssue[], review, at, setAt, offset, setOffset, grouped, onGrouped, detailError, save };
}
