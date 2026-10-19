"use client";
import {TextSupport} from "./TextSupport";
import {FindingRegionAudit} from "../text-regions/TextRegionAudit";
import { useState } from "react";
import { useItem } from "@/app/images/useFeed";
import { ReviewJudgments } from "@/app/CacheStatus";
import { ContentSupport } from "./ContentSupport";
import { evidenceLabel, fmt, renditionLines, verdictLabel, type Item } from "@/app/images/lib";
const MEASURE_LABELS: Record<string, string> = {
  matched_frac: "Match bounding-box area / candidate B area",
  matched_frac_a: "Match bounding-box area / candidate A area",
  coverage_frac: "Geometric overlap / candidate B area",
};
const MEASURE_KEYS = ["n_inliers", "inlier_ratio", "matched_frac", "matched_frac_a", "coverage_frac",
                      "rotation_deg", "scale", "flip", "grain_residual_r", "same_registration",
                      "offset", "area_px", "mean_ncc", "flat_fraction"];


export function ImageDetails({project,run,itemId}:{project:string;run:string;itemId:string}) {
  const detail=useItem(project,run,"image_forensics",itemId,undefined,"item_details");
  const [support,setSupport]=useState<Item["content_support"]>();
  const [checking,setChecking]=useState(false);
  const item=detail.item;
  if(!item)return <p role="status">{detail.error || "Loading details…"}</p>;
  const ms=item.measurements ?? {};
  async function diagnostics(){
    setChecking(true);
    try {
      const response=await fetch(`/api/workbench?${new URLSearchParams({method:"item_diagnostics",project,run,item:itemId,component:"image_forensics"})}`,{signal:AbortSignal.timeout(15000)});
      const value=await response.json();if(!response.ok)throw new Error(value.error);
      setSupport(value.content_support);
    }catch(error){setSupport({status:"unavailable",reason:String(error)});}
    finally{setChecking(false);}
  }
  return <section aria-label="Finding details">
    <ReviewJudgments reviews={item.reviews}/>
    <button onClick={diagnostics} disabled={checking}>{checking ? "Checking…" : "Load content diagnostics"}</button>
    {support && <ContentSupport data={support} project={project} dir={item.paper.dir}/>}
          <p><b>{item.publication_status === "published" ? "Published finding" : item.publication_status === "cleared" ? "Cleared detector candidate" : "Detector candidate"}</b>
            {item.screening && <> · Saved AI: {item.screening.decision} ({item.screening.confidence})</>}</p>
          {item.screening_status === "failed" && <p role="status">Screening failed — no validated scientific decision.</p>}
          {item.screening_status === "unresolved" && <p role="status">Unresolved — context incomplete or ambiguous.</p>}
          {item.scientific_disposition && <p>Validated scientific disposition: {item.scientific_disposition}</p>}
          {item.eligibility_detail && <p className="muted">{item.eligibility_detail}</p>}
          {item.screening?.explanation && <>
            <h3 style={h3}>{item.screening.validated ? "AI assessment" : "Unvalidated assessment"}</h3>
            <blockquote style={bq}>{item.screening.explanation}</blockquote>
            {item.screening.validated && item.screening.evidence_quote && <blockquote style={bq}>{item.screening.evidence_quote}</blockquote>}
          </>}
          {!!item.screening?.validation_errors?.length && <ul style={ul}>{item.screening.validation_errors.map((error, i) => <li key={i}>{error}</li>)}</ul>}
          <h3 style={h3}>Rank {item.rank.score}</h3>
          <ul style={ul}>{(item.rank.reasons || []).map((r) => <li key={r}>{r}</li>)}</ul>

          <h3 style={h3}>Captions</h3>
          {item.panels.map((p, i) => (
            <div key={p.uid + i} style={{ marginBottom: 6 }}>
              <div><b>{"AB"[i]}</b> · <span className="mono">{p.paper_dir}</span> · {p.figure_label || "no figure label"}
                {p.caption_source && <span className="muted"> · {p.caption_source}</span>}</div>
              {p.caption ? <blockquote style={bq}>{p.caption}</blockquote>
                         : <div className="muted">no caption found for this panel</div>}
              <div className="muted">
                {p.document ? p.document.role + ": " + p.document.path : "Source document unresolved"}
                {" · subfigure "}{p.subfigure?.raw || "unresolved"}
                {p.subfigure?.status ? " (" + p.subfigure.status + ")" : ""}
              </div>
              {(item.screening?.panel_readings || []).filter(r => r.uid === p.uid).map((r, n) =>
                <div key={n}>Visual reading: {r.subfigure_raw || "unresolved"} · {r.status}
                  {r.page ? " · p. " + r.page : ""}{r.context_text ? " · " + r.context_text : ""}</div>)}
              {p.placements.map((pl, n) => <div key={n} className="muted">
                p. {pl.page} · {pl.bbox_kind === "crop_exact" ? "exact crop location" :
                  pl.bbox_kind === "parent_approximate" ? "approximate parent location" :
                  pl.bbox ? "image location" : "page only"}
                {pl.identity_source ? " · from the identity sidecar" : ""}
                {pl.geometry_gap ? " · " + pl.geometry_gap : ""}
              </div>)}
              {p.identity_sidecar && p.identity_sidecar.status !== "usable" && (
                <div className="muted">identity sidecar {p.identity_sidecar.status}
                  {p.identity_sidecar.reason ? ": " + p.identity_sidecar.reason : ""}</div>
              )}
              {/* The figure source ledger: every rendition of this figure
                  with its pixel size and link verdict, text only. */}
              {p.figure_sources && (() => {
                const { note, lines } = renditionLines(p.figure_sources);
                return (
                  <div style={{ marginTop: 2 }}>
                    <div className="muted">Renditions{lines.length ? "" : ": none recorded"}</div>
                    {lines.map((line, n) => <div key={n} className="muted" style={{ paddingLeft: 8 }}>{line}</div>)}
                    {note && <div className="muted">{note}</div>}
                  </div>
                );
              })()}
              {p.caption_locator?.path && <div className="muted">Caption source: {p.caption_locator.path}
                {p.caption_locator.page ? " · p. " + p.caption_locator.page : ""}</div>}
              {[...(p.caption_warnings || []), ...(p.identity_gaps || [])].map((gap, n) =>
                <div key={n} className="muted">{gap}</div>)}
            </div>
          ))}

          {!!(item.legacy_decision_context || item.prior_decisions?.length) && <details><summary>Other historical decisions (context only)</summary><pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify({unassigned: item.legacy_decision_context, other_runs: item.prior_decisions},null,2)}</pre></details>}
          <h3 style={h3}>Detector</h3>
          <p className="muted">Run {item.run_id} · v{item.provenance?.version || "unknown"} · {item.run_status} · {item.publication_status} · evidence: {evidenceLabel(item.evidence_source)}</p>
          <p style={{ margin: "2px 0" }}><span className="mono">{item.detector_kind}</span>
            {item.spans_figures && " · spans figures"}</p>
          <p style={{ margin: "2px 0" }}>{item.sentence}</p>
          {item.direction?.basis && <p className="muted" style={{ margin: "2px 0" }}>{item.direction.basis}</p>}

          <h3 style={h3}>Original adjudication</h3>
          <p style={{ margin: "2px 0" }}><b>{verdictLabel(item)}</b></p>
          {item.adjudication?.explanation && <blockquote style={bq}>{item.adjudication.explanation}</blockquote>}
          {!item.adjudication && <p className="muted">not adjudicated</p>}

          <h3 style={h3}>Saved AI screening</h3><pre style={{whiteSpace:"pre-wrap"}}>{item.screening ? JSON.stringify(item.screening,null,2) : item.screening_attempts?.length ? JSON.stringify(item.screening_attempts,null,2) : "No screening judgment was recorded."}</pre>
          {ms.zoom_context && typeof ms.zoom_context === "object" ? <>
            <h3 style={h3}>Zoom/inset relationship</h3>
            <pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify(ms.zoom_context, null, 2)}</pre>
          </> : null}
          {ms.engine === "hybrid" ? <>
            <h3 style={h3}>Within-panel search</h3>
            <p>Regions A and B match; copying direction is unknown.</p>
            <pre style={{whiteSpace:"pre-wrap"}}>{JSON.stringify({engine: ms.engine, version: ms.engine_version,
              search: ms.search_coverage, annotations: ms.review_annotations,
              equivalent_observations: ms.equivalent_observations}, null, 2)}</pre>
          </> : null}
          <h3 style={h3}>Measurements</h3>
          <p className="muted">Bounding-box area and geometric overlap do not measure the percentage of duplicated experimental pixels.</p>
          <table style={{ fontSize: 11 }}>
            <tbody>
              {MEASURE_KEYS.filter((k) => k in ms).map((k) => (
                <tr key={k}><td className="mono" style={{ paddingRight: 8 }}>{MEASURE_LABELS[k] || k}</td><td>{fmt(ms[k])}</td></tr>
              ))}
            </tbody>
          </table>
          <FindingRegionAudit project={project} run={run} panels={item.panels}/>
          <TextSupport value={ms.text_support} item={item} project={project}/>
          {/* The unaligned control: the same two panels correlated WITHOUT the
              transform, beside the aligned r. Absent means never measured
              (an old manifest, a cross-paper item), never "failed". */}
          {Boolean(ms.control) && typeof ms.control === "object" && (() => {
            const c = ms.control as Record<string, unknown>;
            const keys = ["overlap_r", "control_r", "lift", "agree_frac", "region"];
            return (
              <>
                <h3 style={h3}>Unaligned control{item.exhibit_gate && <span className="muted mono" style={{ fontWeight: 400, marginLeft: 8, fontSize: 11 }}>{item.exhibit_gate}</span>}</h3>
                {c.note ? (
                  <p className="muted" style={{ margin: "2px 0" }}>not measured: {String(c.note)}</p>
                ) : (
                  <table style={{ fontSize: 11 }}>
                    <tbody>
                      {keys.filter((k) => k in c).map((k) => (
                        <tr key={k}><td className="mono" style={{ paddingRight: 8 }}>{k}</td>
                          <td>{typeof c[k] === "number" ? fmt(c[k]) : String(c[k])}</td></tr>
                      ))}
                    </tbody>
                  </table>
                )}
                {item.rank.lookalike && (
                  <p style={{ margin: "4px 0", color: "var(--sev-highly)" }}>
                    lookalike: aligning these panels buys no agreement they lack unaligned
                  </p>
                )}
              </>
            );
          })()}

          <h3 style={h3}>Keys</h3>
          <p className="muted" style={{ margin: 0 }}>
            1–9 decide (then next undecided) · j/k next/prev · n next undecided · a / shift+b jump the PDF to panel A / B ·
            s/b/o comparator mode, v the rendered video when there is one · space hold B · − / = zoom, 0 fit · Esc queue ·
            drag either divider to resize (arrow keys once it has focus); the
            sizes hold for the rest of this browser tab
          </p>
  </section>;
}
const h3: React.CSSProperties = { fontSize: 12, margin: "12px 0 4px", textTransform: "uppercase", letterSpacing: 0.4 };
const ul: React.CSSProperties = { margin: 0, paddingLeft: 18 };
const bq: React.CSSProperties = { margin: "4px 0", paddingLeft: 8, borderLeft: "3px solid var(--line)", whiteSpace: "pre-wrap" };
