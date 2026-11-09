"use client";

import Link from "next/link";
import { RunSelector } from "@/app/RunSelector";
import { useSearchParams, useRouter } from "next/navigation";
import { HoverPreview } from "@/app/images/HoverPreview";
import { useInfiniteFeed } from "@/app/images/useInfiniteFeed";
import { useCallback, useEffect, useRef, useState } from "react";
import { useQueueFilters } from "./useQueueFilters";
import { BULK_REASONS, useBulkReview } from "./useBulkReview";
import { useQueueKeyboard } from "./QueueKeyboard";
import { QueueThumbnailCell, type HoverTarget } from "./QueueThumbnail";

import {
  DEFAULT_FILTER, FIGURE_SPANS, type Filter, itemHref,
  verdictLabel, queueHref,
  paperColumn, cycleQueueSort, queueSortMark, queueAriaSort, QUEUE_SORTS, queueSortOf, queueSortFirst,
  MATCH_REGIONS, matchRegionLabel,
} from "@/app/images/lib";

const JUDGMENTS = [
  ["issue", "Issue"], ["unresolved", "Unresolved"], ["innocuous", "Innocuous"],
  ["automatic_clearance", "Automatically cleared — AI not needed"],
  ["missing", "No saved AI judgment"], ["legacy", "Legacy adjudication"],
] as const;

export function ImageQueue({ project, projectName }: {
  project: string; projectName: string;
}) {
  const router = useRouter();
  const selection = useSearchParams().get("run") || "latest";
  const [cursor, setCursor] = useState(0);
  const scrollHost = useRef<HTMLDivElement>(null);
  const sentinel = useRef<HTMLDivElement>(null);
  const restored = useRef(false);
  const arrowTarget = useRef<number | null>(null);
  const [hover, setHover] = useState<HoverTarget | null>(null);
  const resetNavigation = useCallback(() => {
    restored.current=false; arrowTarget.current=null; setCursor(0); setHover(null);
    if (scrollHost.current) scrollHost.current.scrollTop=0;
  }, []);
  const { filter, filterKey, filterLoaded, updateFilter } = useQueueFilters(project, selection, resetNavigation);
  const {feed,error:feedError,loading,facetsLoading,loadMore,refresh:load}=useInfiniteFeed(project,selection,filter,filterLoaded===filterKey);
  const rows = feed?.items || [];
  const { checked, setChecked, rowKey, selectedRows, allChecked, selectAll, toggleAll,
    saving, bulkMessage, bulkReason, setBulkReason, markFalsePositive, markFilterFalsePositive,
  } = useBulkReview({ project, selection, filter, filterKey, feed, rows, load });
  const nextOffset = feed?.pagination?.next_offset;
  const positionKey = `images.queue.${project}.${selection}`;
  const filterStamp = JSON.stringify(filter);
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
  useQueueKeyboard({ rows, cursor, setCursor, feed, nextOffset, loadMore, project, selection, router, scrollHostRef: scrollHost, arrowTargetRef: arrowTarget });

  function setF(next: Partial<Filter>) {
    updateFilter(next); restored.current=true; arrowTarget.current=null; setHover(null);
    if (scrollHost.current) scrollHost.current.scrollTop=0;
    setCursor(0);
  }

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
            {["all", "any_suspicious", "translation", "rotation", "resizing", "reflection", "combined", "unknown"].map(value => value === "any_suspicious"
              ? <option key={value} value={value} title="Rotation over 10 degrees (either direction), reflection, or a combination: not direct duplications / crops, not resizing alone, not unmeasured matches">any suspicious</option>
              : <option key={value} value={value}>{value}</option>)}
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
                  <QueueThumbnailCell project={project} selection={selection} it={it} root={scrollHost}
                                      style={{ ...td, width: 140 }} onHover={setHover} />
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
