"use client";
import {useState,useEffect} from "react";
export type RunOption = {
  id: string; label: string; n_items?: number; states?: Record<string, number>;
  provenance?: unknown; configuration?: unknown; requested_components?: string[]; status?: string;
  execution_id?: string | null; component?: string;
  /** Number of per-paper records folded into this execution. */
  n_runs?: number;
  /** A run made by a non-default pipeline: "tools only · provisional". */
  pipeline?: { name?: string | null; complete_review?: boolean; label: string } | null;
};
/** The option text: the run's own label, then its pipeline when that is not
 *  the default complete review. A partial run's rows are unadjudicated, and a
 *  picker that named it only by version and date read as a complete review. */
export function runOptionLabel(option: RunOption): string {
  return option.label + (option.pipeline?.label ? ` · ${option.pipeline.label}` : "")
    + (option.n_items != null ? ` · ${option.n_items} saved items` : "");
}
/** What the "latest" selection actually resolved to, from the server. The
 *  selector prints the newest run's OWN date and how many sweeps the per-paper
 *  view mixes, because the header's `built_at` is when the projection was
 *  rebuilt, not when the results were produced -- a stale run rebuilt this
 *  morning reads as fresh. (2026-09-14: two newer sweeps sat on disk unsynced
 *  and the viewer showed the previous one as current, with nothing on screen
 *  saying so.) */
export type LatestInfo = {
  newest_run_at?: string | null;
  /** Distinct detector stamps (code fingerprint + flags) among the runs shown.
   *  1 means one coherent run; 2+ means the per-paper view is mixing runs made
   *  under different code or flags, which is the stale-data signal. */
  configurations_in_view?: number;
  papers_in_view?: number;
  newest_run?: { run_uid: string; execution_uid?: string | null } | null;
  configuration?: Record<string, unknown>;
};
function day(t?: string | null): string { return t ? String(t).slice(0, 16).replace("T", " ") : "date unknown"; }
export function RunSelector({ value, options, onChange, project, component, latest = true, latestInfo }: {
  value: string; options: RunOption[]; onChange: (selection: string) => void; latest?: boolean; project?:string; component?:string;
  latestInfo?: LatestInfo;
}) {
  const [extra,setExtra]=useState<RunOption[]>([]),[offset,setOffset]=useState(0),[done,setDone]=useState(false),[error,setError]=useState("");
  useEffect(()=>{setExtra([]);setOffset(0);setDone(false);},[project,component]);
  async function more(){
    const params=new URLSearchParams({project:project!,offset:String(offset),...(component?{component}:{})});
    try {const r=await fetch(`/api/runs?${params}`),b=await r.json();if(!r.ok)throw new Error(b.error);
      setExtra(prev=>[...prev,...b.runs]);setOffset(b.pagination.next_offset || 0);setDone(b.pagination.next_offset===null);setError("");
    }catch(e){setError(String(e));}
  }
  const all=[...new Map([...options,...extra].map(o=>[o.id,o])).values()];
  const configs=latestInfo?.configurations_in_view ?? 0;
  const cfg=latestInfo?.configuration || {};
  const detector=typeof cfg.panel_detector==="string" ? cfg.panel_detector : undefined;
  const cfgText=[detector, cfg.rendered_regions ? "rendered regions" : undefined].filter(Boolean).join(", ");
  // The default selection says what it IS: the newest run's date, its detector
  // configuration, and whether every paper shown carries that one stamp. A
  // resumed sweep legitimately spans many execution ids on identical flags,
  // which is why "latest per paper" stays the default rather than a single
  // execution -- but it must never again be possible to read this label and
  // not know how fresh the data is, or that two configurations are mixed.
  const latestLabel = latestInfo?.newest_run_at
    ? `Latest run — newest ${day(latestInfo.newest_run_at)}${cfgText ? ` · ${cfgText}` : ""}`
      + (configs > 1 ? ` · MIXES ${configs} configurations` : configs === 1 ? " · one configuration" : "")
    : "Latest per paper";
  return <div style={{ display: "inline-block", fontSize: 12 }}>
    <label>Version / run{" "}<select aria-label="Version / run" value={value} onChange={e => onChange(e.target.value)} style={{ maxWidth: 650 }}>
      {latest && <option value="latest">{latestLabel}</option>}
      {value !== "latest" && !all.some(o => o.id === value) && <option value={value}>{value} · selected historical run</option>}
      {all.map(option => <option key={option.id} value={option.id}>{runOptionLabel(option)}</option>)}
    </select></label>
    {project && !done && <button onClick={more}>Load older runs</button>}{error && <span role="alert">{error}</span>}
  </div>;
}
