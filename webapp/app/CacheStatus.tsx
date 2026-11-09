"use client";
import type { Judgments } from "@/lib/types/review";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import useSWR, { type SWRConfiguration, type State, unstable_serialize, useSWRConfig } from "swr";
import { getJson, postJson } from "@/lib/getJson";
import { ReviewSyncTracker, reviewSyncInterval, type ReviewSyncReading, type ReviewSyncState } from "@/lib/reviewSync";
export type SyncState = ReviewSyncState & {import_error?: unknown};

const UNAVAILABLE = "Local service unavailable";
const STATUS_TIMEOUT_MS = 10000;
// SWR's own retry backs off exponentially; the service contract is a flat
// five seconds until the local service answers again.
const retryLater: NonNullable<SWRConfiguration<ReviewSyncReading, Error>["onErrorRetry"]> =
  (_error, _key, _config, revalidate, { retryCount }) => {
    setTimeout(() => void revalidate({ retryCount }), reviewSyncInterval(undefined, true));
  };

/** The local service's review-sync status, polled at 30 s, or 5 s while
 *  decisions are pending or the service is unreachable. A `workbench-review`
 *  event (a saved decision) reads at once; when the pending writes it
 *  announced have drained, `workbench-review-synced` tells the item and queue
 *  views to refetch their judgments. Focus refreshes immediately; on shared
 *  pages it first asks the service to pull changed records. An image page
 *  reads only local image status and never writes to shared storage. */
export function useReviewSync(imagePage: boolean, project: string): SyncState {
  const [tracker] = useState(() => new ReviewSyncTracker());
  const url = `/api/workbench?method=${imagePage ? "image_status" : "status"}${imagePage ? `&project=${encodeURIComponent(project)}` : ""}`;
  const key = ["review-sync", url];
  // SWR evaluates a `refreshInterval` callback only when it arms the next
  // timer, so a reading that turns up pending writes would still wait out
  // the idle 30 s. Passing the cadence as a value derived from the latest
  // reading re-arms the timer the moment the cadence changes.
  const { cache } = useSWRConfig();
  const latest = cache.get(unstable_serialize(key)) as State<ReviewSyncReading> | undefined;
  const { data, error, mutate } = useSWR<ReviewSyncReading, Error>(
    key,
    async () => {
      const generation = tracker.saves;
      const state = await getJson<SyncState>(url, AbortSignal.timeout(STATUS_TIMEOUT_MS));
      return { state, generation };
    },
    {
      refreshInterval: reviewSyncInterval(latest?.data),
      refreshWhenHidden: false,
      // Focus is handled below: a shared page synchronizes before it reads.
      revalidateOnFocus: false,
      onErrorRetry: retryLater,
      onSuccess: (reading) => {
        if (tracker.observe(reading)) window.dispatchEvent(new Event("workbench-review-synced"));
      },
    },
  );
  useEffect(() => {
    const saved = () => { tracker.saved(); void mutate(); };
    const focus = () => {
      if (imagePage) { void mutate(); return; }
      postJson("/api/workbench", { method: "sync" }).catch(() => undefined).then(() => void mutate());
    };
    window.addEventListener("focus", focus);
    window.addEventListener("workbench-review", saved);
    return () => { window.removeEventListener("focus", focus); window.removeEventListener("workbench-review", saved); };
  }, [imagePage, mutate, tracker]);
  return error ? { error: UNAVAILABLE } : (data?.state ?? {});
}

export function CacheStatus(){
 const pathname=usePathname();
 const imagePage=pathname.includes("/images");
 const project=imagePage ? decodeURIComponent(pathname.split("/")[2] || "") : "";
 const state=useReviewSync(imagePage,project);
 return <span role="status" style={{fontSize:11}} title={state.error || (state.import_error ? `Local import needs attention: ${JSON.stringify(state.import_error)}` : undefined) || state.pending_errors?.join('; ') || state.file_monitor_error || (state.warmup_error ? `Landing-page summary could not be prepared: ${state.warmup_error}` : undefined) || state.synced_at || (imagePage ? 'Local image review; no network synchronization' : 'Initial synchronization in progress')}>
 {imagePage ? (state.error ? 'Local review needs attention' : state.ready ? 'Saved on this computer' : 'Loading local image records…') : state.error || state.pending_errors?.length?'Offline / sync needs attention':state.ready?'Shared records cached':'Synchronizing shared records…'}
 {imagePage && !!state.import_error && ' · import needs attention'}
 {state.synced_at && ` · synced ${new Date(state.synced_at).toLocaleTimeString()}`}
 {state.file_monitor_error && ' · local files checked periodically'}
 {state.warmup_error && ' · project summary computed on demand'}
 {!!state.pending_writes && ` · ${state.pending_writes} decision(s) pending sync`}{' '}<a href="/files">Local files</a></span>;
}
export function ReviewJudgments({reviews}:{reviews?: Judgments}){
 if(!reviews?.reviewers?.length)return null;
 return <div style={{fontSize:12}}>{reviews.conflict&&<strong>Reviewers disagree — all judgments retained.</strong>}
 {reviews.reviewers.map(r=><p key={r.reviewer}>{r.reviewer}: {r.decision} · {r.at}{r.pending?' · pending sync':''}{r.note?` — ${r.note}`:''}</p>)}
 <details><summary>Decision history ({reviews.history?.length || 0})</summary>{reviews.history?.map(r=><p key={r.event_id}>{r.at} · {r.reviewer} · {r.decision} · {r.note}</p>)}</details></div>;
}
