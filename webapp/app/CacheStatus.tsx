"use client";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { watchReviewSync, type ReviewSyncState } from "@/lib/reviewSync";
export type SyncState = ReviewSyncState & {import_error?: unknown};
export function CacheStatus(){
 const pathname=usePathname();
 const imagePage=pathname.includes("/images");
 const project=imagePage ? decodeURIComponent(pathname.split("/")[2] || "") : "";
 const [state,setState]=useState<SyncState>({});
 useEffect(()=>{
 const controller = new AbortController();
 const watcher = watchReviewSync({
  read: async()=>{
   const response=await fetch(`/api/workbench?method=${imagePage ? 'image_status' : 'status'}${imagePage ? `&project=${encodeURIComponent(project)}` : ''}`,{signal:AbortSignal.any([controller.signal,AbortSignal.timeout(10000)])});
   if(!response.ok)throw new Error('Local service unavailable');
   return response.json();
  },
  update:setState,
  completed:()=>window.dispatchEvent(new Event("workbench-review-synced")),
  visible:()=>!document.hidden,
 });
 const saved=()=>watcher.saved();
 const focus=()=>{if(imagePage){watcher.refresh();return;}void fetch('/api/workbench',{method:'POST',signal:controller.signal,headers:{'content-type':'application/json'},body:JSON.stringify({method:'sync'})}).then(()=>watcher.refresh()).catch(()=>watcher.refresh());};
 window.addEventListener('focus',focus);window.addEventListener('workbench-review',saved);
 return()=>{watcher.stop();controller.abort();window.removeEventListener('focus',focus);window.removeEventListener('workbench-review',saved);};
 },[imagePage,project]);
 return <span role="status" style={{fontSize:11}} title={state.error || (state.import_error ? `Local import needs attention: ${JSON.stringify(state.import_error)}` : undefined) || state.pending_errors?.join('; ') || state.file_monitor_error || (state.warmup_error ? `Landing-page summary could not be prepared: ${state.warmup_error}` : undefined) || state.synced_at || (imagePage ? 'Local image review; no network synchronization' : 'Initial synchronization in progress')}>
 {imagePage ? (state.error ? 'Local review needs attention' : state.ready ? 'Saved on this computer' : 'Loading local image records…') : state.error || state.pending_errors?.length?'Offline / sync needs attention':state.ready?'Shared records cached':'Synchronizing shared records…'}
 {imagePage && !!state.import_error && ' · import needs attention'}
 {state.synced_at && ` · synced ${new Date(state.synced_at).toLocaleTimeString()}`}
 {state.file_monitor_error && ' · local files checked periodically'}
 {state.warmup_error && ' · project summary computed on demand'}
 {!!state.pending_writes && ` · ${state.pending_writes} decision(s) pending sync`}{' '}<a href="/files">Local files</a></span>;
}
export function ReviewJudgments({reviews}:{reviews?:{conflict?:boolean;reviewers?:any[];history?:any[]}}){
 if(!reviews?.reviewers?.length)return null;
 return <div style={{fontSize:12}}>{reviews.conflict&&<strong>Reviewers disagree — all judgments retained.</strong>}
 {reviews.reviewers.map(r=><p key={r.reviewer}>{r.reviewer}: {r.decision} · {r.at}{r.pending?' · pending sync':''}{r.note?` — ${r.note}`:''}</p>)}
 <details><summary>Decision history ({reviews.history?.length || 0})</summary>{reviews.history?.map(r=><p key={r.event_id}>{r.at} · {r.reviewer} · {r.decision} · {r.note}</p>)}</details></div>;
}
