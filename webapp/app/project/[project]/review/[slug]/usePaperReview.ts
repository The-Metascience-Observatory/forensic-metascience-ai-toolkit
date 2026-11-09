import { useCallback, useEffect, useRef, useState } from "react";

import { readReviewer } from "../../../../ReviewerChip";
import { GROUP_KEY, readGrouped } from "@/lib/findingGroups";

/** The paper page's data: the `/api/paper` read (paged, grouped, scoped to a
 *  run and opened on a named finding), its `/api/workbench` source follow-up,
 *  the per-finding detail, the viewed ping and the `/api/review` writes.
 *  `Reviewer` keeps the layout and the jump/view state. */
export function usePaperReview({ project, slug, dir, run, focusFinding }: {
  project: string; slug: string; dir?: string | null;
  /** `?run=` and `?finding=` from the URL, read by the caller. */
  run: string | null; focusFinding: string | null;
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
  const [review, setReview] = useState<any>(null);
  // The `?finding=` focus is consumed once the page holding it is on screen,
  // so paging and j/k afterwards are the reader's own.
  const focusConsumed = useRef(false);
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

  useEffect(() => {
    if (grouped === null) return;
    let cancel = false;
    setData(null); setErr(null); setAt(0);
    fetch(`/api/paper?offset=${offset}&group=${grouped ? 1 : 0}&project=${encodeURIComponent(project)}&slug=${encodeURIComponent(slug)}${dir ? `&dir=${encodeURIComponent(dir)}` : ""}${run ? `&run=${encodeURIComponent(run)}` : ""}${focusFinding && !focusConsumed.current ? `&finding=${encodeURIComponent(focusFinding)}` : ""}`)
      .then(async (r) => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.error || r.statusText);
        return body;
      })
      .then((body) => {
        if (cancel) return;
        setData(body);
        setReview(body.issues?.review || { issues: {}, paper: {} });
        const fi = body.issues?.focus_index;
        if (typeof fi === "number") {
          const po = body.issues?.pagination?.offset;
          if (typeof po === "number" && po !== offset) setOffset(po);
          else focusConsumed.current = true;
          setAt(fi);
        }
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

  return { data, err, issues, review, at, setAt, offset, setOffset, grouped, onGrouped, detailError, save };
}
