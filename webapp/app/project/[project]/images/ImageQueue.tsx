"use client";

import Link from "next/link";
import { readReviewer } from "@/app/ReviewerChip";
import { RunSelector } from "@/app/RunSelector";
import { useSearchParams, useRouter } from "next/navigation";
import { FlipArrow } from "@/app/images/FlipArrow";
import { previewBoxes } from "@/lib/imagePreview";
import { boxCorners, matchDirection } from "@/lib/flipArrow";
import { HoverPreview } from "@/app/images/HoverPreview";
import { useInfiniteFeed } from "@/app/images/useInfiniteFeed";
import { useEffect, useRef, useState } from "react";

import {
  DEFAULT_FILTER, FIGURE_SPANS, type Filter, type Item, itemHref,
  mediaUrl, readFilter, verdictLabel, queueHref,
  paperColumn, cycleQueueSort, queueSortMark, queueAriaSort, QUEUE_SORTS, queueSortOf, queueSortFirst,
  MATCH_REGIONS, matchRegionLabel,
} from "@/app/images/lib";

// v4: the default now includes unscreened candidates; a saved v3 default hid them.
const FILTER_KEY = "metascience.images.filter.v4";

// Why a whole filter's worth of candidates is a false positive. Recorded on
// the event as `bulk_reason` beside the generic `false_positive` decision --
// the decision vocabulary stays as it is, and the reason is what makes the
// labels usable as a regression fixture instead of a count.
const BULK_REASONS = [
  ["chart_or_graph", "Charts, graphs or graphics"],
  ["channel_overlay", "Colour-channel overlay or merge"],
  ["caption_disclosed_zoom", "Overview/detail disclosed in the caption"],
  ["other", "Other (see note)"],
] as const;

const JUDGMENTS = [
  ["issue", "Issue"], ["unresolved", "Unresolved"], ["innocuous", "Innocuous"],
  ["automatic_clearance", "Automatically cleared — AI not needed"],
  ["missing", "No saved AI judgment"], ["legacy", "Legacy adjudication"],
] as const;

function thumb(project: string, it: Item): string | null {
  // Archived exhibits may still contain the old explanatory text bands.
  const panel = it.panels.find(p => p.image);
  const rel = panel?.image || it.exhibit;
  const dir = panel?.image ? panel.paper_dir : it.paper.dir;
  return rel ? mediaUrl(project, dir, rel) + "&variant=thumbnail" : null;
}

function QueueThumbnail({src, root, item}: {src: string; item: Item; root: React.RefObject<HTMLDivElement>}) {
  const image = useRef<HTMLImageElement>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const observer = new IntersectionObserver(entries => {
      if (entries.some(e => e.isIntersecting)) { setVisible(true); observer.disconnect(); }
    }, {root: root.current, rootMargin: `${root.current?.clientHeight || 800}px 0px`});
    if (image.current) observer.observe(image.current);
    return () => observer.disconnect();
  }, [root]);
  const side = item.panels.findIndex(p => p.image);
  const ms = item.measurements ?? {};
  const size = side === 0 ? ms.panel_px_a : side === 1 ? ms.panel_px_b : null;
  const clone = item.detector_kind === 'intra_panel_clone';
  const boxes = Array.isArray(size) && size.length === 2 ? previewBoxes(ms, side, size as [number,number], clone) : [];
  return <div style={{position:'relative',width:130,height:60}}><img ref={image} src={visible ? src : undefined} alt="" decoding="async" width={130} height={60}
    style={{width:130,height:60,display:"block",objectFit:"contain",background:"var(--media-bg)"}} />
    {visible && Array.isArray(size) && boxes.length > 0 && <svg viewBox={`0 0 ${size[0]} ${size[1]}`} aria-label="Matching regions"
      style={{position:'absolute',inset:0,width:'100%',height:'100%',pointerEvents:'none'}}>
      {boxes.map((box,i)=><g key={i}>
        <rect x={box[0]} y={box[1]} width={box[2]-box[0]} height={box[3]-box[1]} fill="none" stroke="#00FFDD" strokeWidth={2} vectorEffect="non-scaling-stroke" />
        <FlipArrow points={boxCorners(box)} direction={matchDirection(ms,clone ? i : side,clone)} color="#00FFDD" />
      </g>)}
    </svg>}
  </div>;
}

/** How much of a bulk save is KNOWN to have happened when it did not finish. */
class BulkOutcome extends Error {
  constructor(readonly kind: "refused" | "partial" | "unknown", message: string, readonly saved = 0) { super(message); }
}

export function ImageQueue({ project, projectName }: {
  project: string; projectName: string;
}) {
  const router = useRouter();
  const selection = useSearchParams().get("run") || "latest";
  const filterKey = `${FILTER_KEY}.${project}.${selection}`;
  const [filter, setFilter] = useState<Filter>(DEFAULT_FILTER);
  const [filterLoaded,setFilterLoaded]=useState<string | null>(null);
  const {feed,error:feedError,loading,facetsLoading,loadMore,refresh:load}=useInfiniteFeed(project,selection,filter,filterLoaded===filterKey);
  const rows = feed?.items || [];
  const [cursor, setCursor] = useState(0);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const [bulkMessage, setBulkMessage] = useState("");
  const [bulkReason, setBulkReason] = useState<string>(BULK_REASONS[0][0]);
  const selectAll = useRef<HTMLInputElement>(null);
  const rowKey = (it: Item) => JSON.stringify([it.run_id, it.id]);
  const selectedRows = rows.filter(it => checked.has(rowKey(it)));
  const allChecked = rows.length > 0 && selectedRows.length === rows.length;
  useEffect(() => {
    if (selectAll.current) selectAll.current.indeterminate = selectedRows.length > 0 && !allChecked;
  }, [selectedRows.length, allChecked]);
  useEffect(() => { setChecked(new Set()); setBulkMessage(""); }, [filterKey, filter]);
  function toggleAll() {
    setChecked(allChecked ? new Set() : new Set(rows.map(rowKey)));
  }
  // ONE request for the whole selection. It used to be one request per row:
  // measured at ~630 ms each, so 1,944 selected rows took twenty minutes, and
  // each request re-refreshed the service projection and bumped the revision
  // the reviewer's own queue was paging through.
  //
  // The save is a background job, polled for progress. What a failure means
  // depends on what is KNOWN: a refusal the service answered before saving
  // ("saved 0") is nothing saved; a lost connection or an unknown job is an
  // unknown outcome, and the queue is reloaded to show what was saved.
  async function runBulk(payload: Record<string, unknown>, label: string) {
    const response = await fetch("/api/images/bulk", {
      method: "POST", headers: {"content-type": "application/json"}, body: JSON.stringify(payload),
    }).catch(error => { throw new BulkOutcome("unknown", String(error)); });
    const started = await response.json().catch(() => ({}));
    if (!response.ok || started.error || !started.job) throw new BulkOutcome(response.ok ? "unknown" : "refused", started.error || response.statusText);
    let misses = 0;
    for (;;) {
      await new Promise(resolve => setTimeout(resolve, 400));
      let job;
      try {
        const poll = await fetch(`/api/images/bulk?job=${encodeURIComponent(started.job.id)}`);
        const body = await poll.json();
        if (!poll.ok || body.error) throw new Error(body.error || poll.statusText);
        job = body.job; misses = 0;
      } catch (error) {
        if (++misses >= 5) throw new BulkOutcome("unknown", String(error));
        continue;
      }
      const p = job.progress || {};
      if (job.state === "running") {
        setBulkMessage(p.to_save != null ? `${label}: ${(p.processed || 0).toLocaleString()} of ${p.to_save.toLocaleString()} processed, ${(p.saved || 0).toLocaleString()} saved…` : `${label}: preparing…`);
        continue;
      }
      if (job.state === "done") return job.result;
      throw new BulkOutcome((p.saved || 0) > 0 ? "partial" : "refused", job.error, p.saved || 0);
    }
  }
  function outcomeMessage(error: unknown, unchanged: string) {
    if (error instanceof BulkOutcome) {
      if (error.kind === "refused") return `Nothing was saved${unchanged}. ${error.message}`;
      if (error.kind === "partial") return `${error.saved.toLocaleString()} decisions were saved before the job stopped; the reloaded queue shows which. ${error.message}`;
    }
    return `The outcome is unknown: some decisions may have been saved; the reloaded queue shows what was. ${error instanceof Error ? error.message : String(error)}`;
  }
  async function markFalsePositive() {
    if (savingRef.current || !selectedRows.length) return;
    const reviewer = readReviewer().trim();
    if (!reviewer) { setBulkMessage("Set your name in the header before recording a decision."); return; }
    savingRef.current = true; setSaving(true);
    const targets = [...selectedRows];
    setBulkMessage(`Saving ${targets.length.toLocaleString()}…`);
    try {
      const result = await runBulk({project, decision: "false_positive", reviewer,
          items: targets.map(it => ({run: it.run_id, id: it.id}))}, "Saving");
      const failed = new Set<string>((result.failed || []).map((f: {id: string; run?: string}) => f.run ? rowKey({run_id: f.run, id: f.id} as Item) : f.id));
      // Only the rows that failed stay selected, so a retry is the same click.
      setChecked(new Set(targets.filter(it => failed.has(rowKey(it)) || failed.has(it.id)).map(rowKey)));
      setBulkMessage(`${result.saved} of ${targets.length} saved locally as False positive; `
        + "database sync runs in the background."
        + (failed.size ? ` ${failed.size} failed and remain selected. ${result.failed[0].error}` : ""));
    } catch (error) {
      setBulkMessage(outcomeMessage(error, "; the selection is unchanged"));
    }
    savingRef.current = false; setSaving(false);
    window.dispatchEvent(new Event("workbench-review"));
    load();
  }
  async function markFilterFalsePositive() {
    if (savingRef.current) return;
    const reviewer = readReviewer().trim();
    if (!reviewer) { setBulkMessage("Set your name in the header before recording a decision."); return; }
    const total = feed?.pagination?.total;
    if (!total) { setBulkMessage("Nothing matches the current filter."); return; }
    const label = BULK_REASONS.find(([value]) => value === bulkReason)?.[1] || bulkReason;
    if (!window.confirm(`Mark all ${total.toLocaleString()} items matching the current filter `
        + `as False positive (${label})? Items that already carry a decision are left alone.`)) return;
    savingRef.current = true; setSaving(true);
    setBulkMessage(`Saving ${total.toLocaleString()} decisions…`);
    try {
      const r = await runBulk({project, run: selection, component: "image_forensics", ...filter,
          decision: "false_positive", reason: bulkReason, note: label,
          reviewer, expected_total: total}, "Saving");
      setBulkMessage(`${r.saved} of ${r.matched} saved as False positive (${label}).`
        + (r.skipped_already_decided ? ` ${r.skipped_already_decided} already had a decision and were left alone.` : "")
        + (r.failed?.length ? ` ${r.failed.length} failed: ${r.failed[0].error}` : "")
        + " Database sync runs in the background.");
      setChecked(new Set());
    } catch (error) { setBulkMessage(outcomeMessage(error, "")); }
    savingRef.current = false; setSaving(false);
    window.dispatchEvent(new Event("workbench-review"));
    load();
  }
  const scrollHost = useRef<HTMLDivElement>(null);
  const sentinel = useRef<HTMLDivElement>(null);
  const restored = useRef(false);
  const arrowTarget = useRef<number | null>(null);
  const nextOffset = feed?.pagination?.next_offset;
  const [hover, setHover] = useState<{ it: Item; x: number; y: number } | null>(null);
  const positionKey = `images.queue.${project}.${selection}`;
  const filterStamp = JSON.stringify(filter);
  useEffect(() => {
    restored.current=false; arrowTarget.current=null; setCursor(0); setHover(null);
    setFilter(readFilter(filterKey)); setFilterLoaded(filterKey);
    if (scrollHost.current) scrollHost.current.scrollTop=0;
  }, [filterKey]);
  useEffect(() => {
    if (!feed || restored.current) return;
    try {
      const saved = JSON.parse(sessionStorage.getItem(positionKey) || "null");
      if (saved?.filter === filterStamp) {
        if (saved.cursor >= rows.length && nextOffset != null) { loadMore(); return; }
        setCursor(Math.min(saved.cursor || 0, Math.max(0,rows.length-1)));
        if (scrollHost.current) scrollHost.current.scrollTop=saved.top || 0;
      }
    } catch { /* optional session preference */ }
    restored.current=true;
  }, [feed, rows.length, nextOffset, loadMore, positionKey, filterStamp]);
  useEffect(() => {
    if (!restored.current) return;
    try { sessionStorage.setItem(positionKey,JSON.stringify({top:scrollHost.current?.scrollTop || 0,cursor,filter:filterStamp})); }
    catch { /* optional session preference */ }
  }, [cursor, positionKey, filterStamp]);
  useEffect(() => {
    const observer=new IntersectionObserver(entries => {
      if (entries.some(entry=>entry.isIntersecting) && !loading && !feedError && nextOffset != null) loadMore();
    }, {root:scrollHost.current, rootMargin:"600px 0px"});
    if (sentinel.current) observer.observe(sentinel.current);
    return () => observer.disconnect();
  }, [loading, feedError, nextOffset, loadMore]);
  function selectRow(index: number) {
    setCursor(index);
    const row=scrollHost.current?.querySelector<HTMLElement>(`[data-row-index="${index}"]`);
    row?.focus({preventScroll:true});
    row?.scrollIntoView({block:"nearest"});
  }
  useEffect(() => {
    if (arrowTarget.current != null && arrowTarget.current < rows.length) {
      selectRow(arrowTarget.current); arrowTarget.current=null;
    }
    if (feed && cursor >= rows.length) setCursor(Math.max(0,rows.length-1));
  }, [rows.length, feed, cursor]);

  function setF(next: Partial<Filter>) {
    const f = { ...filter, ...next };
    setFilter(f); restored.current=true; arrowTarget.current=null; setHover(null);
    if (scrollHost.current) scrollHost.current.scrollTop=0;
    setCursor(0);
    try { window.localStorage.setItem(filterKey, JSON.stringify(f)); } catch { /* fine */ }
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.defaultPrevented) return;
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if ((e.target as HTMLElement | null)?.isContentEditable) return;
      if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        if (!rows.length) return;
        const index=cursor + (e.key === "ArrowDown" ? 1 : -1);
        if (index >= rows.length && nextOffset != null) { arrowTarget.current=index; loadMore(); }
        else selectRow(Math.max(0,Math.min(rows.length-1,index)));
      }
      else if (e.key === "Enter" && rows[cursor] && tag !== "BUTTON" && tag !== "A") {
        e.preventDefault();
        router.push(itemHref(project, rows[cursor].id, selection));
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [rows, cursor, project, router, selection, nextOffset, loadMore]);


  const counts = feed?.counts || {};
  const nDecided = counts.decided;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12, padding: "6px 12px",
                       borderBottom: "1px solid var(--line)", background: "var(--panel)", flexShrink: 0 }}>
        <Link prefetch={false} href={`/project/${encodeURIComponent(project)}`} style={{ fontSize: 12 }}>← {projectName}</Link>
        <div style={{ fontWeight: 600, fontSize: 13 }}>Image review</div>
        <div className="muted" style={{ fontSize: 11 }}>
          {feed ? (
            <>
              {counts.items ?? "…"} items · {counts.within ?? "…"} within-paper · {counts.cross ?? "…"} cross-paper ·{" "}
              {counts.unexplained ?? "…"} saved screened findings · {counts.unscreened ?? "…"} unscreened / unresolved ·{" "}
              {!!feed.screening_progress?.awaiting_review && <>{feed.screening_progress.awaiting_review} candidates awaiting AI review · </>}
              <b>{nDecided != null ? `${nDecided} decided` : facetsLoading ? "… decided" : "decided count unavailable"}</b> · {counts.papers ?? "…"} papers ·{" "}
              <b title="The newest run in this selection. The projection may have been rebuilt more recently; that is NOT the date of the results.">
                newest run {feed.latest_info?.newest_run_at ? String(feed.latest_info.newest_run_at).slice(0, 16).replace("T", " ") : "unknown"}
              </b>
              {(feed.latest_info?.configurations_in_view ?? 0) > 1 &&
                <b style={{ color: "var(--warn, #b45309)" }} title="Papers in this view were run under different detector code or flags. This is not one run.">
                  {" "}· MIXES {feed.latest_info!.configurations_in_view} configurations
                </b>}
              {" "}· built {feed.built_at}
            </>
          ) : loading ? "loading the feed…" : "loading…"}
        </div>
        <div style={{ flex: 1 }} />
        <Link prefetch={false} href={`/api/images?project=${encodeURIComponent(project)}&run=${encodeURIComponent(selection)}&format=csv`} style={{ fontSize: 12 }}
           title="Every item with its rank, verdict and decision, one row each">export CSV</Link>
        <button type="button" onClick={() => load(true)} disabled={loading} style={{ fontSize: 12 }}
                title="Synchronize shared records. No analysis or screening is run.">
          {loading ? "…" : "sync"}
        </button>
      </header>

      <fieldset disabled={saving} style={{ margin: 0, border: 0, display: "flex", gap: 10, padding: "6px 12px", alignItems: "center",
                    borderBottom: "1px solid var(--line)", fontSize: 12, flexShrink: 0, flexWrap: "wrap" }}>
        <RunSelector project={project} component="image_forensics" value={selection} options={feed?.runs || []} latestInfo={feed?.latest_info}
                     onChange={s => router.push(queueHref(project, s))} />
        <label>Result status{" "}
          <select value={filter.verdict} onChange={(e) => setF({ verdict: e.target.value as Filter["verdict"] })}>
            <option value="standing">Standing candidates</option>
            <option value="all">All saved results</option>
            <option value="unexplained">Published findings (saved judgment)</option>
            <option value="unscreened">Unscreened / unresolved</option>
            <option value="cleared">Cleared / rejected</option>
          </select>
        </label>
        <label title="Detector kind, or cross-paper items. Counts show how many items each choice would leave GIVEN the other filters, so they move as you narrow.">kind{" "}
          <select value={filter.kind} onChange={(e) => setF({ kind: e.target.value })}>
            <option value="all">{feed ? `all (${(feed.facet_totals?.kind ?? counts.items ?? 0).toLocaleString()})` : "all"}</option>
            <option value="cross">{feed ? `cross (${(feed.facet_totals?.kind_cross ?? counts.cross ?? 0).toLocaleString()})` : "cross"}</option>
            {(feed?.kinds || []).map(({ value, count }) =>
              <option key={value} value={value}>{value} ({count.toLocaleString()})</option>)}
          </select>
        </label>
        <label title="The panel typer's class for the item. 'mixed' = two classes in one item; 'untyped' = no panel in the item was typed (visible crops and whole panels are never typed by the current splitter). Counts show how many items each choice would leave GIVEN the other filters.">
          Image type{" "}
          <select value={filter.image_type || "all"} onChange={(e) => setF({ image_type: e.target.value })}>
            <option value="all">all</option>
            {(feed?.image_types || []).map(({ value, count }) =>
              <option key={value} value={value}>{value} ({count})</option>)}
          </select>
        </label>
        <label title="Whether the match is spread across two different figures of the paper. Taken from every placement's figure label, so one image printed in Figure 1 and Figure 2 counts; panel letters and '(cont.)' do not make a new figure, and Figure S1 is not Figure 1. 'figure unknown' means a panel has no figure label -- a missing label, not a match. Counts show how many items each choice would leave GIVEN the other filters.">
          Figures{" "}
          <select value={filter.figure_span || "all"} onChange={(e) => setF({ figure_span: e.target.value as Filter["figure_span"] })}>
            <option value="all">all</option>
            {FIGURE_SPANS.map(([value, label]) => {
              // A loaded feed omits a value nobody has: that is zero, not unmeasured.
              const count = feed?.figure_span_counts
                ? feed.figure_span_counts.find((c) => c.value === value)?.count ?? 0 : undefined;
              return <option key={value} value={value}>{label}{count === undefined ? "" : ` (${count.toLocaleString()})`}</option>;
            })}
          </select>
        </label>
        <label>Transformation
          <select value={filter.transformation || "all"} onChange={e => setF({transformation: e.target.value as Filter["transformation"]})}>
            {["all", "any", "translation", "rotation", "resizing", "reflection", "combined", "unknown"].map(value => <option key={value} value={value} title={value === "any" ? "Any rotation, resizing, reflection or combination: everything except direct duplications / crops (translation) and unmeasured matches" : undefined}>{value}</option>)}
          </select>
        </label>
        <label title="Incomplete means a saved stage was skipped, failed or capped. Unknown means no complete coverage claim was recorded.">Coverage
          <select value={filter.coverage || "all"} onChange={e => setF({coverage: e.target.value as Filter["coverage"]})}>
            {["all", "incomplete", "unknown"].map(value => <option key={value} value={value}>{value}</option>)}
          </select>
        </label>
        <label>Text-label context
          <select value={filter.text_context || "exclude"} onChange={e=>setF({text_context:e.target.value as Filter["text_context"]})}>
            <option value="exclude">Exclude from queue</option>
            <option value="include">Include</option>
            <option value="only">Context only</option>
          </select>
        </label>
        <label title="Whether each item's archived panel images can be served on THIS computer. Missing means no registered folder here holds the sealed run's objects (register the corpus folder on the Files page); it says nothing about the paper. Not checked yet: the service checks in the background.">
          evidence{" "}
          <select aria-label="Evidence on this computer" value={filter.evidence || "all"} onChange={(e) => setF({ evidence: e.target.value as Filter["evidence"] })}>
            {([["all", "all"], ["available", "available here"], ["missing", "missing here"], ["unknown", "not checked yet"]] as const).map(([value, label]) => {
              const count = feed?.evidence_counts ? feed.evidence_counts.find((c) => c.value === value)?.count ?? 0 : undefined;
              return <option key={value} value={value}>{label}{value === "all" || count === undefined ? "" : ` (${count.toLocaleString()})`}</option>;
            })}
          </select>
        </label>
        <label title="Spot-check the detector's own context demotions (rows it cleared as chart furniture, channel overlays, independent captures, chart templates). Shows a seeded sample per demotion kind; the same seed always gives the same sample. On each item, say whether the demotion was right or wrong.">
          <input type="checkbox" checked={!!filter.spot_check} onChange={(e) => setF({ spot_check: e.target.checked ? "1" : "" })} />
          {" "}spot-check demotions
          {filter.spot_check && <> · seed <input aria-label="Spot-check seed" value={filter.spot_check} size={4}
            onChange={(e) => setF({ spot_check: e.target.value.trim() || "1" })} /></>}
        </label>
        <label title="Queue order. Triage is the shared ranking rule: groups an adjudicator cleared, then groups whose unaligned control was measured and failed (lookalikes), sort after every other group; within that, the verdict tier, the rank score and the inlier count. Rank score is the bare score.">
          order{" "}
          <select aria-label="Queue order" value={queueSortOf(filter)}
                  onChange={(e) => { const sort = e.target.value as Filter["sort"] & string; setF({ sort, direction: queueSortFirst(queueSortOf({ sort })) }); }}>
            {QUEUE_SORTS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </select>
        </label>
        <label title="A LOOKALIKE is a group whose unaligned control was MEASURED and failed: the same two panels agree about as well unaligned as aligned, so the agreement is not specific to the recovered transform -- generic resemblance rather than shared pixels. Also set for a single channel matched to a merge containing it across two figures. It never changes the score, only the sort order. A group whose control was never measured is NOT a lookalike: absence of a measurement is not a failed measurement, and the control is only measured when exhibits are rendered. Counts show how many items each choice would leave GIVEN the other filters.">
          Lookalike{" "}
          <select value={filter.lookalike || "all"} onChange={(e) => setF({ lookalike: e.target.value as "all" | "yes" | "no" })}>
            <option value="all">all</option>
            {(feed?.lookalike_counts || []).map(({ value, count }) =>
              <option key={value} value={value}>{value} ({count.toLocaleString()})</option>)}
          </select>
        </label>
        <label title="Area of the bounding box around matched features, divided by each compared image's area. Partial in both requires a measured box in both images. These are candidate matches, not proof that every pixel inside the boxes is duplicated.">
          Matched region{" "}
          <select value={filter.match_region || "all"} onChange={e => setF({match_region: e.target.value as Filter["match_region"]})}>
            <option value="all">all</option>
            {MATCH_REGIONS.map(([value, label]) => <option key={value} value={value}>
              {label}{feed ? ` (${(feed.match_region_counts?.find(c => c.value === value)?.count ?? 0).toLocaleString()})` : ""}
            </option>)}
          </select>
        </label>
        {filter.match_region && filter.match_region !== "all" && filter.match_region !== "unknown" &&
          <label title="Partial means the matched box covers no more than this percentage of that image. Both images must meet the cutoff for Partial in both images.">
            Max. area per image{" "}
            <select value={filter.region_max_percent ?? 80} onChange={e => setF({region_max_percent: Number(e.target.value)})}>
              {[25, 50, 70, 80, 90, 95, 99].map(n => <option key={n} value={n}>{n}%</option>)}
            </select>
          </label>}
        <details style={{ position: "relative" }}>
          <summary style={{ cursor: "pointer", border: "1px solid var(--line)", borderRadius: 4, padding: "5px 8px" }}>
            Adjudicator output: {JUDGMENTS.filter(([value]) => filter.judgments?.includes(value)).map(([, label]) => label).join(", ") || "None"}
          </summary>
          <div style={{ position: "absolute", top: "100%", left: 0, zIndex: 30, minWidth: 240,
            padding: 10, background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 4,
            boxShadow: "0 4px 16px rgba(0,0,0,0.2)" }}>
            {JUDGMENTS.map(([value, label]) => (
              <label key={value} style={{ display: "flex", gap: 8, padding: "5px 0", alignItems: "center" }}>
                <input type="checkbox" checked={filter.judgments?.includes(value) || false}
                  onChange={(e) => setF({ verdict: "all", judgments: e.target.checked
                    ? [...(filter.judgments || []), value]
                    : (filter.judgments || []).filter(v => v !== value) })} />
                {label} ({feed?.judgment_counts ? (feed.judgment_counts[value] || 0).toLocaleString() : "…"})
              </label>
            ))}
            <div className="muted" style={{ fontSize: 11, marginTop: 6 }}>Counts cover the selected run before filters, across all confidence levels.</div>
          </div>
        </details>
        <label title="Matches the paper folder in the Paper column. A DOI with a slash also matches the -- folder name.">
          Paper folder{" "}
          <input className="mono" value={filter.q || ""}
            onChange={(e) => setF({ q: e.target.value })}
            placeholder="10.1007--s004010050748"
            aria-label="Search by paper folder name"
            style={{ minWidth: 220 }} />
        </label>
        <label><input type="checkbox" checked={filter.undecided}
                      onChange={(e) => setF({ undecided: e.target.checked })} /> undecided only</label>
        <button type="button" onClick={() => setF(DEFAULT_FILTER)}>Reset filters</button>
      </fieldset>

      <div style={{display:"flex",gap:12,alignItems:"center",padding:"6px 12px",flexShrink:0,fontSize:12}}>
        <button type="button" onClick={toggleAll} disabled={saving || !rows.length}>
          {allChecked ? "Deselect all" : "Select all"} loaded rows
        </button>
        <span>{selectedRows.length} selected · {rows.length} loaded{feed?.pagination ? ` of ${feed.pagination.total} matching` : ""}</span>
        <button type="button" onClick={markFalsePositive} disabled={saving || !selectedRows.length}>
          {saving ? "Saving…" : "Mark selection as False positive"}
        </button>
        <select value={bulkReason} onChange={(e) => setBulkReason(e.target.value)}
                aria-label="Reason for a filter-wide false positive" disabled={saving}>
          {BULK_REASONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <button type="button" onClick={markFilterFalsePositive}
                disabled={saving || !feed?.pagination?.total}>
          {saving ? "Saving…" : `Mark all ${(feed?.pagination?.total || 0).toLocaleString()} matching`}
        </button>
        <span role="status">{bulkMessage}</span>
      </div>
      {(feedError || feed?.refresh_error) && <p style={{ color: "var(--sev-highly)", padding: "8px 12px" }}>{feedError || feed?.refresh_error}</p>}

      {feed?.refresh_needed && <p className="muted" style={{ margin: 8 }}>Refreshing the image feed…</p>}
      {feed && rows.length === 0 && <p style={{padding:12}}>{feed.empty_reason}</p>}
      {filter.spot_check && feed?.spot_check && (
        <p className="muted" role="status" style={{ margin: "4px 12px", flexShrink: 0 }}>
          Spot-check sample (seed {feed.spot_check.seed}, up to {feed.spot_check.per_kind} per kind):{" "}
          {Object.entries(feed.spot_check.strata).map(([kind, s]) =>
            `${kind} ${s.right + s.wrong}/${s.sampled} checked of ${s.population.toLocaleString()} (${s.wrong} wrong)`).join(" · ") || "no automatic demotions in this selection"}
        </p>
      )}
      {(feed?.notes?.length || 0) > 0 && <details style={{margin:"4px 12px",flexShrink:0}}><summary>Availability details ({feed?.notes?.length})</summary><div style={{maxHeight:160,overflow:"auto"}}>{feed?.notes?.map((note,i)=><p className="muted" key={i}>{note}</p>)}</div></details>}
      <div ref={scrollHost} onScroll={(e) => {
        try { sessionStorage.setItem(`images.queue.${project}.${selection}`, JSON.stringify({ top: e.currentTarget.scrollTop, cursor, filter:filterStamp })); } catch { /* optional */ }
      }} style={{ overflow: "auto", flex: 1, minHeight: 0 }}>
        <table style={{ borderCollapse: "collapse", width: "100%", fontSize: 12 }}>
          <thead>
            <tr style={{ position: "sticky", top: 0, background: "var(--panel)" }}>
              <th style={th}><label style={{whiteSpace:"nowrap"}}>
                <input ref={selectAll} type="checkbox" aria-label="Select all loaded rows" checked={allChecked}
                  disabled={saving || !rows.length} onChange={toggleAll} /> #
              </label></th><th style={th}></th>
              <th style={th} aria-sort={queueAriaSort(filter, "score")}>
                <button type="button" className="sort-th" onClick={() => setF(cycleQueueSort(filter, "score"))}
                        title="Sort by rank score">score{queueSortMark(filter, "score")}</button>
              </th>
              <th style={th} aria-sort={queueAriaSort(filter, "paper")}>
                <button type="button" className="sort-th" onClick={() => setF(cycleQueueSort(filter, "paper"))}
                        title="Sort by paper folder. First click A to Z, second Z to A, third restores score.">
                  paper{queueSortMark(filter, "paper")}
                </button>
              </th>
              <th style={th} aria-sort={queueAriaSort(filter, "year")}>
                <button type="button" className="sort-th" onClick={() => setF(cycleQueueSort(filter, "year"))}
                        title="Sort by the paper's publication year. First click newest first, second oldest first, third restores score. Unknown years stay last.">
                  year{queueSortMark(filter, "year")}
                </button>
              </th>
              <th style={th}>figures</th><th style={th}>kind</th>
              <th style={th}>adjudicator</th>
              <th style={th} aria-sort={queueAriaSort(filter, "decision")}>
                <button type="button" className="sort-th" onClick={() => setF(cycleQueueSort(filter, "decision"))}
                        title="Sort by decision: true issue, unsure, conflicting, false positive, then each FP reason; undecided always last. Second click reverses, third restores score.">
                  decision{queueSortMark(filter, "decision")}
                </button>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((it, i) => {
              const t = thumb(project, it);
              const focused = i === cursor;
              return (
                <tr key={`${it.run_id}:${it.id}`} data-row-index={i} tabIndex={-1} aria-current={focused ? "true" : undefined}
                    onClick={() => { setCursor(i); }}
                    onDoubleClick={() => { router.push(itemHref(project, it.id, selection)); }}
                    style={{ borderBottom: "1px solid var(--line)", cursor: "pointer",
                             background: focused ? "var(--hover)" : undefined }}>
                  <td style={td}><label style={{whiteSpace:"nowrap"}} onDoubleClick={e => e.stopPropagation()}>
                    <input type="checkbox" aria-label={`Select row ${i + 1}`} checked={checked.has(rowKey(it))}
                      disabled={saving} onChange={e => {
                        const value = e.target.checked;
                        setChecked(previous => { const next = new Set(previous);
                          if (value) next.add(rowKey(it)); else next.delete(rowKey(it)); return next; });
                      }} /> {i + 1}
                  </label></td>
                  <td style={{ ...td, width: 140 }}
                      onMouseEnter={(e) => setHover({ it, x: e.clientX, y: e.clientY })}
                      onMouseLeave={() => setHover(null)}>
                    {t ? (
                      <Link prefetch={false} href={itemHref(project, it.id, selection)}>
                        <QueueThumbnail key={t} src={t} item={it} root={scrollHost} />
                      </Link>
                    ) : <span className="muted">no image</span>}
                  </td>
                  <td style={td} title={it.rank.reasons.join("\n")}>
                    <b>{it.rank.score}</b>
                    {it.rank.lookalike && (
                      <span title="measured against an unaligned control: aligning these panels buys no agreement they lack unaligned"
                            style={{ marginLeft: 6, fontSize: 10, padding: "0 5px", borderRadius: 8,
                                     border: "1px solid var(--sev-highly)", color: "var(--sev-highly)" }}>lookalike</span>
                    )}
                    <div className="muted" style={{ fontSize: 10, maxWidth: 220 }}>
                      {it.rank.reasons.map((r) => r.split(":")[0]).join(" · ")}
                    </div>
                  </td>
                  <td style={td}>
                    <Link prefetch={false} href={itemHref(project, it.id, selection)} className="mono" style={{ fontSize: 11 }}>
                      {paperColumn(it)}
                    </Link>
                    {it.evidence === "missing" && (
                      <span title="The archived panel images are not on this computer: no registered folder holds this run's objects. This is not a property of the paper."
                            style={{ marginLeft: 6, fontSize: 10, padding: "0 5px", borderRadius: 8, border: "1px solid var(--line)" }}>evidence not here</span>
                    )}
                    {it.paper.title && (
                      <div className="muted" style={{ fontSize: 10, maxWidth: 320,
                                                     overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                        {it.paper.title}
                      </div>
                    )}
                  </td>
                  <td style={{...td, whiteSpace: "nowrap"}}>{it.year ?? (it.paper.year ? String(it.paper.year).slice(0, 4) : <span className="muted">—</span>)}</td>
                  <td style={td}>{it.figure_labels.join(" / ") || <span className="muted">unlabelled</span>}
                    <div className="muted" style={{fontSize: 10}} title="Bounding boxes around matched features, as a percentage of each compared panel (not the whole parent figure). This does not prove that all enclosed pixels are duplicated.">
                      {matchRegionLabel(it)}
                    </div>
                  </td>
                  <td style={{...td, whiteSpace:"nowrap"}} className="mono">{it.detector_kind} <span className="muted" style={{fontSize:10, marginLeft:6}}>v{it.provenance?.version || "unknown"}</span></td>
                  <td style={td}>
                    {verdictLabel(it)}
                    {it.adjudication?.explanation && (
                      <div className="muted" style={{ fontSize: 10, maxWidth: 300,
                                                     overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}
                           title={it.adjudication.explanation}>
                        {it.adjudication.explanation}
                      </div>
                    )}
                  </td>
                  <td style={td}>
                    {it.decision ? (
                      <span title={`${it.decision.reviewer || ""} ${it.decision.at || ""}\n${it.decision.note || ""}`}>
                        {it.decision.decision === "false_positive" ? "False positive" : it.decision.decision}
                      </span>
                    ) : <span className="muted">—</span>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <div ref={sentinel} style={{minHeight:32,padding:8,textAlign:"center"}}>
          {loading && <span role="status" className="muted">{rows.length ? "Loading more…" : "Loading…"}</span>}
          {feedError && <button onClick={loadMore} disabled={loading}>Retry loading</button>}
        </div>
      </div>
      {hover && <HoverPreview key={`${hover.it.run_id}:${hover.it.id}`} project={project} it={hover.it} x={hover.x} y={hover.y} />}
    </div>
  );
}

const th: React.CSSProperties = { textAlign: "left", padding: "4px 8px", borderBottom: "1px solid var(--line)", fontWeight: 600 };
const td: React.CSSProperties = { padding: "4px 8px", verticalAlign: "top" };
