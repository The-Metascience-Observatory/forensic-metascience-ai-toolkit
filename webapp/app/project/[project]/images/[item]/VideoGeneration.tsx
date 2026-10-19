"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Item } from "@/app/images/lib";

export type VideoJob = {
  status: "idle" | "queued" | "running" | "ready" | "failed";
  can_generate: boolean;
  reason?: string | null;
  error?: string | null;
  video?: string | null;
  thumbnail?: string | null;
  revision?: string;
};

export function useVideoGeneration(project: string, item: Item | null | undefined, enabled = true) {
  const key = JSON.stringify([project, item?.run_id, item?.id, item?.record_revision]);
  // Job/media revisions change independently of the scientific finding.
  const embedded = JSON.stringify(item?.video_generation ?? null);
  const latest = useRef(key);
  latest.current = key;
  const latestEmbedded = useRef(embedded);
  latestEmbedded.current = embedded;
  const [state, setState] = useState<{ key: string; embedded: string; job: VideoJob | null; error?: string; recovering?: boolean }>({ key: "", embedded: "", job: null });
  const [submitting, setSubmitting] = useState<string | null>(null);
  const request = useCallback(async (generate = false, signal?: AbortSignal) => {
    if (!item) return;
    const startedWith = latestEmbedded.current;
    const args = { component:"image_forensics", project, run: item.run_id, item: item.id };
    const response = await fetch(generate ? "/api/workbench" : `/api/workbench?${new URLSearchParams({ method: "video_status", ...args })}`, generate ? {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ method: "video_generate", ...args }),
    } : { signal });
    const value = await response.json();
    if (!response.ok) {
      const error = new Error(String(value.error || "Video request failed").replace(/^(Error:\s*)+/, ""));
      Object.assign(error, { uncertain: response.status >= 500 || /timed? out|timeout/i.test(error.message) });
      throw error;
    }
    if (latest.current === key && latestEmbedded.current === startedWith)
      setState({ key, embedded: startedWith, job: value });
  }, [key, project, item?.run_id, item?.id]);
  const currentState = state.key === key && state.embedded === embedded;
  const job = currentState ? state.job : item?.video_generation ?? null;
  const pending = job?.status === "queued" || job?.status === "running";
  useEffect(() => {
    if (!enabled || !item || item.video_generation) return;
    const controller = new AbortController();
    request(false, controller.signal).catch(error => {
      if (!controller.signal.aborted && latest.current === key) setState({ key, embedded, job: null, error: error instanceof Error ? error.message : String(error), recovering: true });
    });
    return () => controller.abort();
  }, [key, embedded, request, enabled]);
  useEffect(() => {
    if (!enabled || (!pending && !(currentState && state.recovering))) return;
    const controller = new AbortController();
    let inFlight = false;
    const poll = () => {
      if (document.visibilityState === "hidden" || inFlight) return;
      inFlight = true;
      request(false, controller.signal).catch(error => {
        if (!controller.signal.aborted && latest.current === key && latestEmbedded.current === embedded)
          setState({ key, embedded, job, error: error instanceof Error ? error.message : String(error), recovering: true });
      }).finally(() => { inFlight = false; });
    };
    const timer = window.setInterval(poll, 2000);
    document.addEventListener("visibilitychange", poll);
    return () => { controller.abort(); window.clearInterval(timer); document.removeEventListener("visibilitychange", poll); };
  }, [pending, currentState, state.recovering, key, embedded, request, enabled]);
  const generate = async () => {
    if (submitting === key || pending || (currentState && state.recovering)) return;
    const startedWith = latestEmbedded.current;
    setSubmitting(key);
    try { await request(true); }
    catch (error) {
      if (latest.current === key && latestEmbedded.current === startedWith) {
        const message = error instanceof Error ? error.message : String(error);
        const uncertain = error instanceof TypeError || (error as { uncertain?: boolean }).uncertain;
        if (uncertain) {
          // A lost response does not cancel the durable job. Reconcile with GET only.
          setState(old => ({ key, embedded: latestEmbedded.current, job: old.key === key ? old.job : null, error: message, recovering: true }));
        } else setState({ key, embedded: latestEmbedded.current, job: job ? { ...job, status: "failed", error: message } : null, error: message });
      }
    } finally { setSubmitting(old => old === key ? null : old); }
  };
  const refresh = () => {
    const startedWith = latestEmbedded.current;
    return request(false).catch(error => {
      if (latest.current === key && latestEmbedded.current === startedWith)
        setState({ key, embedded: startedWith, job, error: error instanceof Error ? error.message : String(error), recovering: true });
    });
  };
  const thumbnailUrl = job?.thumbnail && item ? `/api/media?${new URLSearchParams({component:"image_forensics",project, dir: item.paper.dir, f: job.thumbnail, download: "1"})}` : null;
  return { job, thumbnailUrl, recovering: currentState && !!state.recovering, error: currentState ? state.error : undefined, generating: submitting === key, generate, refresh };
}

export function VideoGeneration({ state }: { state: ReturnType<typeof useVideoGeneration> }) {
  const { job, thumbnailUrl, generating, generate, error, refresh, recovering } = state;
  const pending = job?.status === "queued" || job?.status === "running";
  return <span style={{ display: "inline-flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
    {job?.status === "ready" && job.video ? <span className="muted">Saved on this computer</span> :
      <button type="button" onClick={recovering || (!job && error) ? refresh : generate} disabled={generating || pending || (!job?.can_generate && !(error && !job))}
        title={job?.reason || "Generate and save a video of this recorded match on this computer"}>
        {recovering || (!job && error) ? "Retry video status" : generating ? "Queuing…" : job?.status === "queued" ? "Queued…" : job?.status === "running" ? "Generating…" : job?.status === "failed" ? "Retry video" : "Generate video"}
      </button>}
    {thumbnailUrl && <a href={thumbnailUrl} download className="btn">Download thumbnail</a>}
    <span role="status" aria-live="polite" className="muted">
      {recovering ? "Connection interrupted; checking video status…" : job?.error || error || (!job?.can_generate ? job?.reason : "")}
    </span>
  </span>;
}

/** Mounted only when the reviewer opens video tools. */
export function VideoTools({project,item,onVideo}:{project:string;item:Item;onVideo:(video:string|null)=>void}) {
  const state=useVideoGeneration(project,item);
  useEffect(()=>{onVideo(state.job?.video || item.video || null);},[state.job?.video,item.video,onVideo]);
  return <VideoGeneration state={state}/>;
}
