"use client";

import type { useRouter } from "next/navigation";
import { updateFeed, useItem } from "@/app/images/useFeed";
import { advanceTarget, decidedKey, DecisionOutbox, newEventId, type Ref } from "@/lib/decisionQueue";
import { useCallback, useEffect, useRef, useState } from "react";

import { readReviewer } from "@/app/ReviewerChip";
import {
  DEFAULT_FILTER, type Filter, type Item,
  itemHref, readFilter,
} from "@/app/images/lib";

// v4: the default now includes unscreened candidates; a saved v3 default hid them.
const FILTER_KEY = "metascience.images.filter.v4";
// One outbox per tab: decisions keep sending (and failures stay visible)
// while the reviewer has already moved on to the next item.
const outbox = new DecisionOutbox();
// The previous item's upcoming undecided list, for a decision made before
// this item's own navigation has loaded.
let upcomingHint: { from: Ref; upcoming: Ref[] } | null = null;

export type Neighbor={id:string;run_id:string};
export type Navigation={key:string;prev:Neighbor|null;next:Neighbor|null;next_undecided:Neighbor|null;upcoming?:Neighbor[];position:number|null;total:number};
// A decision recorded on an earlier run of this item, offered only when the
// service PROVES the evidence is the same (panel pixels and crops); one
// click records it again here, with its provenance. Never applied silently.
export type CarryOffer={run:string;decision:string;reviewer:string;at?:string;event_id:string};
export type Decide = (decision: string, resolve?: boolean, extra?: Record<string, unknown>, carryFrom?: string) => void;
export type ItemData = ReturnType<typeof useItemData>;

/** The item in the URL, its queue position, the carried-decision offer and
 *  the decision outbox: everything the item page shows that comes from the
 *  service rather than from the reviewer's gestures. */
export function useItemData({ project, selection, itemId, router, note }: {
  project: string; selection: string; itemId: string; router: ReturnType<typeof useRouter>;
  /** The note textarea's text, saved with the next decision. */
  note: string;
}) {
  const filterKey = `${FILTER_KEY}.${project}.${selection}`;
  const [filter, setFilter] = useState<Filter>(DEFAULT_FILTER);
  const detail=useItem(project,selection,"image_forensics",itemId,undefined,"item_core");
  // The previous item stays on screen while the next one loads, so the PDF
  // pane (and its parsed document) is not torn down between items of one
  // paper. Nothing may be DECIDED on it: `current` is the item in the URL.
  const lastShown=useRef<Item|null>(null);
  if(detail.item)lastShown.current=detail.item;
  const current=detail.item;
  const stale=!current && detail.loading && !!lastShown.current;
  const [, renderOutbox]=useState(0);
  useEffect(()=>outbox.subscribe(()=>renderOutbox(n=>n+1)),[]);
  useEffect(() => {
    if (detail.item?.requested_item_id === itemId && detail.item.id !== itemId)
      router.replace(itemHref(project, detail.item.id, selection));
  }, [detail.item, itemId, project, selection, router]);
  // Record a view once per item and run when its detail has loaded. Viewing
  // is tracked apart from decisions; a failed ping is never shown as an error.
  const viewedRef=useRef<string|null>(null);
  useEffect(() => {
    const it=detail.item;
    if (!it || it.id !== itemId && it.requested_item_id !== itemId) return;
    const key=`${project}\u0000${it.run_id}\u0000${it.id}`;
    if (viewedRef.current===key) return;
    viewedRef.current=key;
    fetch("/api/images/viewed",{method:"POST",headers:{"content-type":"application/json"},
      body:JSON.stringify({project,run:it.run_id,owner:it.run_id,item:it.id,viewer:readReviewer()})}).catch(()=>undefined);
  }, [detail.item, itemId, project]);
  const [navigation,setNavigation]=useState<Navigation>();
  const [navError,setNavError]=useState<string|null>(null);
  const savingRef = useRef(false);
  const [err, setErr] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [revealing, setRevealing] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setFilter(readFilter(filterKey));

  }, [project, filterKey]);

  const item=current || (stale ? lastShown.current : null);
  const [carry,setCarry]=useState<{key:string;offers:CarryOffer[];unproven:number}|null>(null);
  const carryKey=current&&!current.decision&&!current.review_conflict?JSON.stringify([project,current.run_id,current.id]):"";
  useEffect(()=>{
    if(!carryKey)return;
    const controller=new AbortController();
    const [,run,id]=JSON.parse(carryKey);
    fetch(`/api/workbench?${new URLSearchParams({method:"image_carried",project,run,item:id,component:"image_forensics"})}`,{signal:controller.signal})
      .then(r=>r.json()).then(v=>{if(!v.error)setCarry({key:carryKey,offers:v.offers||[],unproven:(v.not_provable||[]).length});}).catch(()=>undefined);
    return()=>controller.abort();
  },[carryKey,project]);
  const carryOffers=carry?.key===carryKey?carry:null;
  const navigationKey=JSON.stringify([project,selection,itemId,filter,current?.record_revision]);
  useEffect(()=>{
    const item=current;
    if(!item)return;
    const controller=new AbortController();
    let disposed=false;
    const timer=setTimeout(()=>{setNavError("Navigation timed out. Refresh to retry.");controller.abort();},10000);
    const params=new URLSearchParams({method:"image_navigation",project,run:selection,item:itemId,owner:item.run_id,
      ...Object.fromEntries(Object.entries(filter).map(([k,v])=>[k,Array.isArray(v)?JSON.stringify(v):String(v)]))});
    fetch(`/api/workbench?${params}`,{signal:controller.signal}).then(async r=>{
      const value=await r.json();if(!r.ok)throw new Error(value.error);
      if(disposed)return;
      setNavigation({key:navigationKey,...value});setNavError(null);
    }).catch(e=>{if(!controller.signal.aborted)setNavError(String(e));}).finally(()=>clearTimeout(timer));
    return()=>{disposed=true;clearTimeout(timer);controller.abort();};
  },[navigationKey]);
  const nav=navigation?.key===navigationKey?navigation:null;
  const prev=nav?.prev || null, next=nav?.next || null, nextUndecided=nav?.next_undecided || null;
  useEffect(() => { if (item?.decision && !item.decision.pending) setNotice(null); }, [item?.decision]);

  const go = useCallback((it: Neighbor | null) => { if (it) router.push(itemHref(project, it.id, selection)); }, [project, router, selection]);

  const activeKey = useRef(""); activeKey.current = `${project}:${selection}:${itemId}`;
  useEffect(() => { setErr(null); setNotice(null); setSaving(false); setRevealing(false); savingRef.current = false; }, [project, selection, itemId]);
  // A decision key pressed before this item's neighbours were known: saved
  // at once, and the advance happens when navigation arrives -- never a
  // silent save that leaves the reviewer where they were.
  const pendingAdvance = useRef<string | null>(null);
  const advance = useCallback((from: Ref) => {
    const target = advanceTarget(from, nav, upcomingHint, outbox.decided);
    if (target === undefined) { pendingAdvance.current = decidedKey(from); setNotice("Saved; moving to the next undecided item when the queue position loads…"); return; }
    pendingAdvance.current = null;
    if (target === null) { setNotice("Saved. No undecided item follows in this queue."); return; }
    const after = (nav?.upcoming || upcomingHint?.upcoming || []).filter(r => decidedKey(r) !== decidedKey(target));
    upcomingHint = { from: target, upcoming: after };
    router.push(itemHref(project, target.id, selection));
  }, [nav, project, router, selection]);
  useEffect(() => {
    if (current && nav && pendingAdvance.current === decidedKey(current)) advance(current);
  }, [nav, current, advance]);
  const decide: Decide = useCallback((decision: string, resolve = false, extra?: Record<string, unknown>, carryFrom?: string) => {
    if (!current) { if (stale) setNotice("Still loading this item; the decision was not recorded."); return; }
    const item = current;
    const reviewer = readReviewer();
    if (!reviewer) { setErr("set your name in the header before recording a decision"); return; }
    const body = { project, run: item.run_id, item: item.id, decision, reviewer, note, event_id: newEventId(), ...(resolve ? { resolve: true } : {}), ...(extra ? { extra } : {}), ...(carryFrom ? { carry_from: carryFrom } : {}) };
    // Sent in the background; the reviewer moves on now. A failure is kept
    // in the outbox and shown on whatever item is open, with a link back.
    outbox.submit(body).then(saved => {
      updateFeed(project, (f) => f ? { ...f, items: f.items.map((i) => i.id === item.id && i.run_id === item.run_id ? { ...i, decision: saved } : i) } : f, selection);
    }).catch(() => undefined);
    if (resolve) { setNotice("Resolution recorded."); return; }
    advance({ id: item.id, run_id: item.run_id });
  }, [current, stale, note, project, selection, advance]);

  return {
    detail, item, current, stale, filter,
    nav, navError, prev, next, nextUndecided, go,
    carryOffers, outbox, decide,
    err, setErr, notice, setNotice, saving, revealing, setRevealing, activeKey,
  };
}
