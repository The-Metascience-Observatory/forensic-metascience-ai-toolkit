"use client";

import { RunSelector } from "@/app/RunSelector";
import {useSearchParams,useRouter} from "next/navigation";
import { ReviewJudgments } from "@/app/CacheStatus";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent, ReactNode } from "react";

import { citationParts, displayFirstAuthor, doiLink, pubpeerSearchLink }
  from "../../../../Citation";
import { readReviewer } from "../../../../ReviewerChip";
import { caughtUpHref, reviewHref, type NavRef } from "@/lib/nav";
import { primaryJumpTarget, surfaceOf, type Target } from "@/lib/targets";
import { GROUP_KEY, readGrouped, stepEntry } from "@/lib/findingGroups";
import {
  availableViews, canToggle, defaultView, extraPdfArtefact, parseStoredView,
  sheetArtefact, VIEW_KEY, type Surface,
} from "@/lib/sourceView";
import { DraftsModal } from "./DraftsModal";
import { IssueList } from "./IssueList";
import { SourcePane } from "./SourcePane";

const SPLIT_KEY = "metascience.split";
const SPLIT_MIN = 20;
const SPLIT_MAX = 80;

function readSplit(): number {
  if (typeof window === "undefined") return 50;
  const n = Number(window.localStorage.getItem(SPLIT_KEY));
  if (Number.isFinite(n) && n >= SPLIT_MIN && n <= SPLIT_MAX) return n;
  return 50;
}

function clampSplit(pct: number): number {
  return Math.min(SPLIT_MAX, Math.max(SPLIT_MIN, pct));
}

export function Reviewer({ project, slug, dir }: {
  project: string; slug: string; dir?: string | null;
}) {
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const [at, setAt] = useState(0);
  const [offset,setOffset]=useState(0);
  // Group Findings: on by default, per reader (localStorage), applied by the
  // service before pagination. Read once on mount; null until then, so the
  // first fetch waits rather than fetching ungrouped and refetching.
  const [grouped,setGrouped]=useState<boolean|null>(null);
  useEffect(()=>{let v=true;try{v=readGrouped(window.localStorage.getItem(GROUP_KEY));}catch{/* storage unavailable */}setGrouped(v);},[]);
  const onGrouped=useCallback((on:boolean)=>{setGrouped(on);setOffset(0);try{window.localStorage.setItem(GROUP_KEY,on?"1":"0");}catch{/* ok */}},[]);
  const [detailError,setDetailError]=useState("");
  const [focusTargetId, setFocusTargetId] = useState<string | null>(null);
  const [forceSurface, setForceSurface] = useState<Surface | null>(null);
  /** The reviewer's sticky XML-vs-PDF choice; null until read from storage. */
  const [viewPref, setViewPref] = useState<Surface | null>(null);
  const [review, setReview] = useState<any>(null);
  const searchParams = useSearchParams(), router = useRouter();
  const run = searchParams.get("run");
  const setRun = (value:string) => { const q=new URLSearchParams(searchParams.toString()); q.set("run",value); router.push(`?${q}`); };
  const [draftsOpen, setDraftsOpen] = useState(false);
  const saveChain = useRef(Promise.resolve());
  const [leftPct, setLeftPct] = useState(50);
  const [dragging, setDragging] = useState(false);
  const leftPctRef = useRef(50);
  const splitRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const n = readSplit();
    leftPctRef.current = n;
    setLeftPct(n);
  }, []);

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

  const applySplit = useCallback((pct: number) => {
    const next = clampSplit(pct);
    leftPctRef.current = next;
    setLeftPct(next);
  }, []);

  const onGutterPointerDown = useCallback((e: PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  }, []);

  const onGutterPointerMove = useCallback((e: PointerEvent<HTMLDivElement>) => {
    if (e.buttons === 0 || !splitRef.current) return;
    const rect = splitRef.current.getBoundingClientRect();
    if (rect.width <= 0) return;
    applySplit(((e.clientX - rect.left) / rect.width) * 100);
  }, [applySplit]);

  const onGutterPointerUp = useCallback(() => {
    setDragging(false);
    window.localStorage.setItem(SPLIT_KEY, String(leftPctRef.current));
  }, []);

  const onGutterKeyDown = useCallback((e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      e.stopPropagation();
      applySplit(leftPctRef.current + (e.key === "ArrowRight" ? 2 : -2));
      window.localStorage.setItem(SPLIT_KEY, String(leftPctRef.current));
    }
  }, [applySplit]);

  useEffect(() => {
    if (grouped === null) return;
    let cancel = false;
    setData(null); setErr(null); setAt(0);
    setFocusTargetId(null); setForceSurface(null);
    fetch(`/api/paper?offset=${offset}&group=${grouped ? 1 : 0}&project=${encodeURIComponent(project)}&slug=${encodeURIComponent(slug)}${dir ? `&dir=${encodeURIComponent(dir)}` : ""}${run ? `&run=${encodeURIComponent(run)}` : ""}`)
      .then(async (r) => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.error || r.statusText);
        return body;
      })
      .then((body) => {
        if (cancel) return;
        setData(body);
        setReview(body.issues?.review || { issues: {}, paper: {} });
        const sourceParams=new URLSearchParams({method:"source",project,slug,dir:body.paper.dir,run:run || "latest"});
        fetch(`/api/workbench?${sourceParams}`).then(async r=>{const source=await r.json();if(!r.ok)throw new Error(source.error);
          if(!cancel)setData((prev:any)=>prev&&({...prev,article:source.article,locators:prev.locators?.locators?.length ? prev.locators : source.locators}));
        }).catch(e=>{if(!cancel)setData((prev:any)=>prev&&({...prev,article:{mode:"none",warning:String(e)}}));});
      })
      .catch((e) => { if (!cancel) setErr(String(e.message || e)); });
    return () => { cancel = true; };
  }, [project, slug, dir, run, offset, grouped]);

  useEffect(()=>{
    if(grouped===null)return;
    let active=true;
    const refresh=()=>{
      if(document.hidden)return;
      const params=new URLSearchParams({project,slug,dir:dir || "",run:run || "latest",offset:String(offset),group:grouped?"1":"0"});
      fetch(`/api/paper?${params}`).then(async r=>{if(!r.ok)return;const b=await r.json();if(!active)return;
        setReview(b.issues.review);
        setData((prev:any)=>prev&&({...prev,sync:b.sync,issues:{...b.issues,issues:b.issues.issues.map((i:any)=>{
          const old=prev.issues.issues.find((x:any)=>x.id===i.id&&x.run===i.run);
          return old?.detail_loaded?{...old,reviews:i.reviews}:i;
        })}}));
      }).catch(()=>{});
    };
    const timer=setInterval(refresh,30000);window.addEventListener("focus",refresh);window.addEventListener("workbench-review-synced",refresh);
    return()=>{active=false;clearInterval(timer);window.removeEventListener("focus",refresh);window.removeEventListener("workbench-review-synced",refresh);};
  },[project,slug,dir,run,offset,grouped]);

  const issues: any[] = data?.issues?.issues ?? [];
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

  // Grouped, the arrows step between ENTRIES (a group is one); its findings
  // are reached by opening it. Ungrouped, finding by finding as before.
  const move = useCallback((delta: number) => {
    setAt((i) => grouped ? stepEntry(issues, i, delta)
      : Math.min(issues.length - 1, Math.max(0, i + delta)));
  }, [issues, grouped]);
  /** One finding at a time, groups or not: the header's ‹ finding › buttons. */
  const moveFinding = useCallback((delta: number) => {
    setAt((i) => Math.min(issues.length - 1, Math.max(0, i + delta)));
  }, [issues.length]);

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
  const detailKey=issues[at]?.detail_key;
  const detailLoaded=issues[at]?.detail_loaded;
  // The finding's OWN run: the service loads that run's findings to find
  // this one. Without it the detail read "latest", which a partial run is
  // never part of, and every such finding failed "Finding not in this project".
  const detailRun=issues[at]?.run as string | undefined;
  useEffect(()=>{
    if(!detailKey || detailLoaded)return;
    let active=true;setDetailError("");
    fetch(`/api/workbench?${new URLSearchParams({method:"issue_detail",project,finding:String(detailKey),...(detailRun?{run:detailRun}:{})})}`)
      .then(async r=>{const b=await r.json();if(!r.ok)throw new Error(b.error);if(active&&b.issue)setData((prev:any)=>prev&&({...prev,
        // The detail replaces the summary row but not the LIST's facts about
        // it: its group and its place in the list come from the paper read.
        issues:{...prev.issues,issues:prev.issues.issues.map((i:any)=>i.detail_key===detailKey?{...b.issue,group:i.group,location_basis:i.location_basis,priority:b.issue.priority ?? i.priority}:i)},
        locators:{locators:[...(prev.locators?.locators || []).filter((l:any)=>l.issue_id!==b.issue.id),...(b.locators?.locators || [])]}}));})
      .catch(e=>{if(active)setDetailError(String(e));});
    return()=>{active=false;};
  },[detailKey,detailLoaded,detailRun,project]);

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

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement | null;
      if (el && /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName)) return;
      if (el?.closest?.(".split-gutter")) return;
      if (e.key === "ArrowDown") { e.preventDefault(); move(1); }
      if (e.key === "ArrowUp") { e.preventDefault(); move(-1); }
      if (e.key === "ArrowRight") {
        e.preventDefault();
        goPaper(data?.nav?.next ?? "caught-up");
      }
      if (e.key === "ArrowLeft") {
        e.preventDefault();
        goPaper(data?.nav?.prev ?? null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, goPaper, data]);

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
        ? (issues[at]?.run || data?.issues?.latest_run)
        : data?.issues?.latest_run;
      if (!owningRun) {
        alert("No run is on screen to attach this decision to.");
        return;
      }
      const res = await fetch("/api/review", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project, slug, dir: data?.paper?.dir || dir, reviewer,
          patch: { ...patch, run: owningRun },
        }),
      });
      const body = await res.json();
      if (!res.ok) {
        alert(body.error || "save failed");
        return;
      }
      setReview(body.review); window.dispatchEvent(new Event("workbench-review"));
    };
    saveChain.current = saveChain.current.then(run, run);
  }, [project, slug, dir, data?.paper?.dir, data?.issues?.latest_run, issues, at]);

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
      <div className={`split${dragging ? " dragging" : ""}`} ref={splitRef}>
        <section className="split-left" style={{ width: `${leftPct}%` }}>
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
        <div
          className={`split-gutter${dragging ? " dragging" : ""}`}
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize findings and source panes"
          aria-valuemin={SPLIT_MIN}
          aria-valuemax={SPLIT_MAX}
          aria-valuenow={Math.round(leftPct)}
          tabIndex={0}
          onPointerDown={onGutterPointerDown}
          onPointerMove={onGutterPointerMove}
          onPointerUp={onGutterPointerUp}
          onPointerCancel={onGutterPointerUp}
          onKeyDown={onGutterKeyDown}
        />
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
