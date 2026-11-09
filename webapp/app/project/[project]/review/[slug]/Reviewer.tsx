"use client";

import { RunSelector } from "@/app/RunSelector";
import {useSearchParams,useRouter} from "next/navigation";
import { ReviewJudgments } from "@/app/CacheStatus";
import { useSplitPane } from "@/app/useSplitPane";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { citationParts, displayFirstAuthor, doiLink, pubpeerSearchLink }
  from "@/lib/citation";
import { caughtUpHref, reviewHref, type NavRef } from "@/lib/nav";
import { primaryJumpTarget, surfaceOf, type Target } from "@/lib/targets";
import {
  availableViews, canToggle, defaultView, extraPdfArtefact, parseStoredView,
  sheetArtefact, VIEW_KEY, type Surface,
} from "@/lib/sourceView";
import { DraftsModal } from "./DraftsModal";
import { IssueList } from "./IssueList";
import { SourcePane } from "./SourcePane";
import { usePaperReview } from "./usePaperReview";
import { useReviewKeys } from "./useReviewKeys";

// The findings/source split is a standing preference (localStorage), unlike
// the image item's session-scoped panes; see `useSplitPane`.
const SPLIT_KEY = "metascience.split";

export function Reviewer({ project, slug, dir }: {
  project: string; slug: string; dir?: string | null;
}) {
  const [focusTargetId, setFocusTargetId] = useState<string | null>(null);
  const [forceSurface, setForceSurface] = useState<Surface | null>(null);
  /** The reviewer's sticky XML-vs-PDF choice; null until read from storage. */
  const [viewPref, setViewPref] = useState<Surface | null>(null);
  const searchParams = useSearchParams(), router = useRouter();
  const run = searchParams.get("run");
  // `?finding=<id>` (a queue link): the service serves the page holding it
  // and names its index; consumed once that page is on screen, so paging
  // and j/k afterwards are the reader's own.
  const focusFinding = searchParams.get("finding");
  const setRun = (value:string) => { const q=new URLSearchParams(searchParams.toString()); q.set("run",value); router.push(`?${q}`); };
  const [draftsOpen, setDraftsOpen] = useState(false);
  const split = useSplitPane({ storageKey: SPLIT_KEY, axis: "x", def: 50, min: 20, max: 80,
                               label: "Resize findings and source panes", storage: "local" });
  const { data, err, issues, review, at, setAt, offset, setOffset, grouped, onGrouped,
          detailError, save } = usePaperReview({ project, slug, dir, run, focusFinding });

  // A fresh page read (same keys as the paper fetch in `usePaperReview`)
  // starts with no jump and on the reviewer's own surface.
  useEffect(() => {
    setFocusTargetId(null); setForceSurface(null);
  }, [project, slug, dir, run, offset, grouped]);

  const locators = data?.locators?.locators;
  const locById = useMemo(() => {
    const m = new Map<string, any>();
    for (const loc of locators || []) {
      m.set(loc.issue_id, loc);
    }
    return m;
  }, [locators]);

  useEffect(() => {
    setViewPref(parseStoredView(window.localStorage.getItem(VIEW_KEY)));
  }, []);

  /** One finding at a time, groups or not: the header's ‹ finding › buttons. */
  const moveFinding = useCallback((delta: number) => {
    setAt((i) => Math.min(issues.length - 1, Math.max(0, i + delta)));
  }, [issues.length, setAt]);

  const jump = useCallback((t: Target) => {
    setFocusTargetId(t.id);
    setForceSurface(surfaceOf(t));
  }, []);

  /** Focus this issue's best target ON THE VIEW THE REVIEWER CHOSE.
   *
   * It used to call `primaryJumpTarget` with no preference, and
   * `coveringSurface` breaks ties to PDF — so every issue change silently
   * yanked the pane back to the PDF. The surface is now the reviewer's to
   * pick; moving to a new finding returns to it rather than overriding it.
   */
  const jumpPrimary = useCallback((issueId: string | undefined) => {
    const issue = issueId ? issues.find((i: any) => i.id === issueId) : null;
    const article = data?.article;
    const available = availableViews(
      article,
      !!sheetArtefact(issue)?.found,
      !!extraPdfArtefact(issue, article)?.found,
    );
    const pref = defaultView(available, viewPref);
    const t = primaryJumpTarget(
      issueId ? locById.get(issueId)?.targets : undefined,
      pref === "none" ? null : pref,
    );
    setFocusTargetId(t ? t.id : null);
    setForceSurface(null);
  }, [locById, issues, data, viewPref]);

  const currentId = issues[at]?.id as string | undefined;

  useEffect(() => {
    jumpPrimary(currentId);
  }, [currentId, jumpPrimary]);

  const goPaper = useCallback((next: NavRef | null | "caught-up") => {
    if (next === "caught-up") {
      window.location.href = caughtUpHref(project);
      return;
    }
    if (!next) return;
    const destination = new URL(reviewHref(project, next.slug, next.dir), window.location.origin);
    destination.searchParams.set("run", run === "latest" || !run ? "latest" : data?.issues?.source?.execution_id || run);
    window.location.href = destination.toString();
  }, [project, run, data?.issues?.source?.execution_id]);

  useReviewKeys({ issues, grouped, setAt, goPaper, data });

  if (err) {
    return <div className="page"><p style={{ color: "var(--sev-impossible)" }}>{err}</p></div>;
  }
  if (!data) {
    return <div className="page">Loading…</div>;
  }

  const paper = data.paper;
  const current = issues[at] ?? null;
  const loc = current ? locById.get(current.id) : null;
  const paperStatus = review?.paper?.status || "unreviewed";
  const available = availableViews(
    data.article,
    !!sheetArtefact(current)?.found,
    !!extraPdfArtefact(current, data.article)?.found,
  );
  const surface: Surface = forceSurface ?? defaultView(available, viewPref);
  const onSurface = (s: Surface) => {
    setViewPref(s);
    window.localStorage.setItem(VIEW_KEY, s);
    setForceSurface(null);
  };
  const reviewedLine = review?.paper?.reviewed_by
    ? `reviewed by ${review.paper.reviewed_by} on ${String(review.paper.reviewed_at || "").slice(0, 10)}`
    : paperStatus === "in_progress" ? "in progress" : "not yet reviewed";
  const first = displayFirstAuthor(paper.first_author || paper.authors);
  const cite = citationParts(paper);
  const byline: ReactNode[] = [];
  if (first) byline.push(first);
  if (cite.journal || cite.loc || cite.year) {
    byline.push(
      <span key="cite">
        {cite.journal ? <span className="journal-title">{cite.journal}</span> : null}
        {cite.loc ? `${cite.journal ? " " : ""}${cite.loc}` : ""}
        {cite.year ? `${cite.journal || cite.loc ? " " : ""}(${cite.year})` : ""}
      </span>,
    );
  }
  // The paper_id fallback: a directory name is the DOI with the slash written
  // `--`, which is the only DOI a paper without metadata has.
  const rawDoi = paper.doi
    || (typeof paper.paper_id === "string" && paper.paper_id.includes("--")
      ? paper.paper_id.replace("--", "/")
      : null);
  const doi = doiLink(rawDoi);
  if (doi) {
    byline.push(
      <a key="doi" href={doi.href} target="_blank" rel="noreferrer">{doi.label}</a>,
    );
  }
  const pubpeer = pubpeerSearchLink(rawDoi);
  if (pubpeer) {
    byline.push(
      <a key="pubpeer" href={pubpeer.href} target="_blank" rel="noreferrer"
         title="Search PubPeer for this DOI. An empty result is not evidence the paper is clean.">
        {pubpeer.label}
      </a>,
    );
  }
  if (reviewedLine) byline.push(reviewedLine);

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <header style={{
        display: "flex", alignItems: "center", gap: 10, padding: "6px 12px",
        borderBottom: "1px solid var(--line)", background: "var(--panel)",
        flexShrink: 0,
      }}>
        <a href={`/project/${encodeURIComponent(project)}`} style={{ fontSize: 12 }}>←</a>
        <button disabled={!data.nav?.prev} onClick={() => goPaper(data.nav.prev)}
                title="Previous paper with findings (←)">‹ paper</button>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 13, overflow: "hidden",
                        textOverflow: "ellipsis", whiteSpace: "nowrap" }}
               title={paper.title || paper.paper_id}>
            {paper.title || paper.paper_id}
          </div>
          <div className="muted" style={{ fontSize: 11, overflow: "hidden",
                                          textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
            {byline.map((bit, i) => (
              <span key={i}>{i > 0 ? " · " : ""}{bit}</span>
            ))}
          </div>
        </div>
        <div><button disabled={!offset} onClick={()=>setOffset(Math.max(0,offset-50))}>Previous 50</button> {data.issues?.pagination?.findings_total ?? data.issues?.pagination?.total ?? issues.length} findings{data.issues?.pagination?.grouped ? ` in ${data.issues.pagination.total} rows` : ""} <button disabled={data.issues?.pagination?.next_offset==null} onClick={()=>setOffset(data.issues.pagination.next_offset)}>Next 50</button></div>
        {detailError && <p role="alert">{detailError}</p>}
        <ReviewJudgments reviews={current?.reviews}/>
        {current?.component_item && <a href={current.producer==="copy_paste" ? `/project/${encodeURIComponent(project)}/copypaste?run=${encodeURIComponent(current.run)}&item=${encodeURIComponent(current.id)}&owner=${encodeURIComponent(current.run)}` : `/project/${encodeURIComponent(project)}/images/${encodeURIComponent(current.id)}?run=${encodeURIComponent(current.run)}`}>Open preserved evidence and adjudication</a>}
        {data.issues?.source?.detail && <p>{data.issues.source.detail}</p>}
        {data.issues?.source?.pipeline && !data.issues.source.pipeline.complete_review && (
          <p role="note" data-partial-run>
            {data.issues.source.partial_fallback
              ? "This paper has no complete review. Showing its newest partial run"
              : "Partial run"}{" "}
            ({data.issues.source.pipeline.label}): not adjudicated, so every severity is the analyst&apos;s own.
          </p>
        )}
        {data.issues?.source?.kind === "archive" && <details><summary>Recorded component execution</summary><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(data.issues.source,null,2)}</pre></details>}
        {Array.isArray(data.issues?.available_runs)
          && data.issues.available_runs.length > 0 && (
          <RunSelector value={run === "latest" || !run ? "latest" : data.issues.latest_run || run} options={data.issues.run_options || data.issues.available_runs.map((name:string)=>({id:name,label:name}))} onChange={setRun}/>

        )}
        <button onClick={() => moveFinding(-1)} disabled={at === 0}>‹ finding</button>
        <span className="muted" style={{ fontSize: 12 }}>
          {issues.length ? `${at + 1} / ${issues.length}` : "0"}
        </span>
        <button onClick={() => moveFinding(1)} disabled={at >= issues.length - 1}>
          finding ›
        </button>
        <button onClick={() => goPaper(data.nav?.next ?? "caught-up")}
                title={data.nav?.next
                  ? "Next paper with findings (→)"
                  : "No more papers with findings (→)"}
                className="primary">
          paper ›
        </button>
      </header>

      {draftsOpen && (
        <DraftsModal project={project} dir={paper.dir || dir || slug}
                     issues={issues} review={review}
                     onClose={() => setDraftsOpen(false)} />
      )}
      <div className={`split${split.dragging ? " dragging" : ""}`} ref={split.containerRef}>
        <section className="split-left" style={{ width: `${split.pct}%` }}>
          {data.issues?.source?.kind === "database" && (
            <p className="muted" style={{fontSize:12}}>
              Shared findings from this computer’s synchronized cache.
              Source availability is checked separately against local files.
            </p>
          )}
          {data.issues?.headline?.statement && (
            <p style={{
              fontSize: 13, margin: "0 0 10px", padding: "8px 10px",
              background: "var(--panel)", borderRadius: 4,
              borderLeft: "3px solid var(--accent)",
            }}>
              {data.issues.headline.statement}
            </p>
          )}
          <IssueList
            issues={issues}
            source={data.issues?.source ?? null}
            at={at}
            review={review}
            onFocus={(i) => {
              setAt(i);
              jumpPrimary(issues[i]?.id);
            }}
            onSave={save}
            locById={locById}
            onJump={jump}
            focusTargetId={focusTargetId}
            preferredSurface={surface === "none" ? null : surface}
            grouped={!!grouped}
            onGrouped={onGrouped}
          />
          <div style={{ marginTop: 16, paddingTop: 12,
                        borderTop: "1px solid var(--line)" }}>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 8,
                          alignItems: "center" }}>
              <button
                className="primary"
                disabled={paperStatus === "complete"}
                onClick={() => save({
                  paper: { status: "complete" },
                })}
              >
                Mark paper reviewed
              </button>
              <button
                onClick={() => goPaper(data.nav?.next ?? "caught-up")}
                title={data.nav?.next
                  ? "Next paper with findings (→)"
                  : "No more papers with findings (→)"}
              >
                Next paper →
              </button>
              <button onClick={() => setDraftsOpen(true)}
                      title="Draft a PubPeer comment or editor letter from the stored findings — never posted anywhere">
                Drafts…
              </button>
            </div>
            <label style={{ display: "block", marginTop: 10, fontSize: 13 }}>
              <input
                type="checkbox"
                checked={!!review?.paper?.submitted_to_pubpeer}
                onChange={(e) => save({
                  paper: { submitted_to_pubpeer: e.target.checked },
                })}
              />
              {" "}submitted to PubPeer
            </label>
            {review?.paper?.pubpeer_url && (
              <p style={{ fontSize: 12, margin: "6px 0 0" }}>
                <a href={review.paper.pubpeer_url} target="_blank" rel="noreferrer">
                  View on PubPeer
                </a>
              </p>
            )}
            {review?.paper?.pubpeer_note && (
              <p className="muted" style={{ fontSize: 12, margin: "4px 0 0" }}>
                {review.paper.pubpeer_note}
              </p>
            )}
            <p className="muted" style={{ fontSize: 11, marginTop: 6 }}>
              Completing is deliberate. Labelling one finding does not count
              the paper as reviewed. A PubPeer post is usually one comment
              for the paper, recorded here even when there is no finding
              on disk to tick.
            </p>
          </div>
        </section>
        <div {...split.separatorProps} />
        <section className="split-right">
          <SourcePane
            project={project}
            slug={slug}
            dir={paper.dir}
            article={data.article}
            issue={current}
            locator={loc}
            extras={current?.extras}
            surface={surface}
            canSwitch={canToggle(available) && surface !== "sheet"}
            onSurface={onSurface}
            focusTargetId={focusTargetId}
          />
        </section>
      </div>
    </div>
  );
}
