"use client";

import type { LatestInfo, RunOption } from "@/lib/types/runs";

export type { LatestInfo, RunOption };
import {useState,useEffect} from "react";
/** The option text: the run's own label, then its pipeline when that is not
 *  the default complete review. A partial run's rows are unadjudicated, and a
 *  picker that named it only by version and date read as a complete review. */
export function runOptionLabel(option: RunOption): string {
  return option.label + (option.pipeline?.label ? ` · ${option.pipeline.label}` : "")
    + (option.n_items != null ? ` · ${option.n_items} saved items` : "");
}
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
