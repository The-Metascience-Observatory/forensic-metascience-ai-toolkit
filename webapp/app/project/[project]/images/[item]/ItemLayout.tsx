"use client";

import dynamic from "next/dynamic";

import Link from "next/link";
import { RunSelector } from "@/app/RunSelector";
import type { useRouter } from "next/navigation";
import { useState, type Dispatch, type SetStateAction } from "react";

import { pubpeerLink } from "@/lib/citation";
import { useSplitPane } from "@/app/useSplitPane";
const PdfPane=dynamic(()=>import("@/app/components/pdf/PdfPane").then(m=>m.PdfPane),{ssr:false,loading:()=> <p>Loading paper…</p>});
import { PdfZoomControls } from "@/app/project/[project]/review/[slug]/PdfZoomControls";
import { Comparator } from "./Comparator";
const VideoTools=dynamic(()=>import("./VideoGeneration").then(m=>m.VideoTools),{loading:()=> <span>Loading video tools…</span>});
const ImageDetails=dynamic(()=>import("./ImageDetails").then(m=>m.ImageDetails),{loading:()=> <p>Loading details…</p>});
const XmlPaperPane=dynamic(()=>import("./XmlPaperPane").then(m=>m.XmlPaperPane),{ssr:false,loading:()=> <p>Loading paper…</p>});
import { canReadXml } from "@/lib/xmlFigures";
import { NativeImagePane } from "./NativeImagePane";
import { nativeSides, summaryGroups } from "@/lib/summaryGroups";
import type { ImageSize } from "@/lib/imageXmlBoxes";
// The 760-line figure editor loads on the first click, not with every item.
const SummaryFigureButton=dynamic(()=>import("./summary").then(m=>m.SummaryFigureButton),{loading:()=> <span>Loading the figure editor…</span>});
function SummaryFigureLauncher({ project, item, boxes, sizes }: { project: string; item: Item; boxes: ImagePdfBox[]; sizes: (ImageSize | null)[] }) {
  const [start, setStart] = useState<"generate" | "website" | null>(null);
  if (start) return <SummaryFigureButton project={project} item={item} boxes={boxes} sizes={sizes} autoStart={start} />;
  const pdf = summaryGroups(item, boxes);
  const none = !pdf.length && !nativeSides(item, pdf).length;
  return (<>
    <button type="button" disabled={none} onClick={() => setStart("generate")}
            title={none ? "No PDF placement or figure image for this finding"
              : pdf.length ? "Render the whole figure(s) from the PDF with the duplication boxes drawn on"
              : "Render the whole figure image(s) with the duplication boxes drawn on"}>generate summary figure</button>
    <button type="button" disabled={none} onClick={() => setStart("website")}
            title="Generate the summary figure and put it, with its PubPeer comment, on the Observatory website's image-findings page">add to website</button>
  </>);
}
import { AuthorEmails } from "./AuthorEmails";
import { MissedDuplicationPanel, missedBoxes, regionFor, type MissedDraft } from "./MissedDuplication";
import { PaperReference, PaperReferences } from "./PaperReferences";
import type { ImagePdfBox } from "@/lib/imagePdfBoxes";
import { describeTransform, type placementOrientation } from "@/lib/affine";
import { zoomIn, zoomOut } from "@/lib/sourceView";
import {
  buildPaneLocator, DECISIONS, type Item,
  itemHref, mediaUrl, paneDocument, queueHref,
} from "@/app/images/lib";
import type { ItemData } from "./useItemData";

const LEFT_KEY = "metascience.images.split.left.v2";
const TOP_KEY = "metascience.images.split.top";
function paperOf(it: Item, dir: string) {
  return it.papers.find((p) => p.dir === dir) || it.paper;
}

/** The pair's measurements re-expressed as printed (`ImageItem`'s `printed` memo). */
export type Printed = {
  reads: ReturnType<typeof placementOrientation>[];
  ms: Record<string, unknown>;
  notes: (string | null)[];
  raw: string | null;
};

export type ItemLayoutProps = ItemData & {
  project: string; projectName: string; itemId: string; selection: string;
  router: ReturnType<typeof useRouter>;
  /** The item on screen: the one in the URL, or the previous one while it loads. */
  item: Item;
  detailsOpen: boolean; setDetailsOpen: Dispatch<SetStateAction<boolean>>;
  videoOpen: boolean; setVideoOpen: Dispatch<SetStateAction<boolean>>;
  selectedVideo: string | null; setSelectedVideo: Dispatch<SetStateAction<string | null>>;
  side: 0 | 1; jumpTo: (s: 0 | 1) => void; focusTid: string | null;
  zoom: number; applyZoom: (z: number) => void; refitPdf: () => void; pdfRefit: number;
  paperReady: boolean;
  missed: MissedDraft | null; setMissed: Dispatch<SetStateAction<MissedDraft | null>>;
  note: string; setNote: Dispatch<SetStateAction<string>>;
  panelErrors: string[];
  panelSizes: ([number, number] | null)[];
  printed: Printed;
  printedImages: (HTMLImageElement | HTMLCanvasElement | null)[];
  pdfMatches: ImagePdfBox[];
};

/** Header, then the notes column beside the evidence column, which holds
 *  the panel comparison above the paper pane: two session-sticky dividers
 *  (README "Pane sizes"). */
export function ItemLayout({
  project, projectName, itemId, selection, router,
  item, stale, filter, nav, navError, prev, next, nextUndecided, go,
  carryOffers, outbox, decide,
  err, setErr, notice, setNotice, saving, revealing, setRevealing, activeKey,
  detailsOpen, setDetailsOpen, videoOpen, setVideoOpen, selectedVideo, setSelectedVideo,
  side, jumpTo, focusTid, zoom, applyZoom, refitPdf, pdfRefit, paperReady,
  missed, setMissed, note, setNote,
  panelErrors, panelSizes, printed, printedImages, pdfMatches,
}: ItemLayoutProps) {
  // Two dividers, both session-sticky, so a posture chosen on one finding
  // survives client navigation to the next finding.
  const cols = useSplitPane({ storageKey: LEFT_KEY, axis: "x", def: 16, min: 12, max: 70,
                              label: "Resize the notes and evidence panes" });
  const rows = useSplitPane({ storageKey: TOP_KEY, axis: "y", def: 46, min: 12, max: 85,
                              label: "Resize the panel comparison and PDF panes" });

  const pa = item.panels[0], pb = item.panels[1];
  const srcA = pa?.image ? mediaUrl(project, pa.paper_dir, pa.image) : null;
  const srcB = pb?.image ? mediaUrl(project, pb.paper_dir, pb.image) : null;
  const ms = printed.ms;
  const boxA = (ms.inlier_box_a as number[] | undefined) || null;
  const boxB = (ms.inlier_box_b as number[] | undefined) || null;
  const regions = (ms.regions as { role: string; bbox: number[] }[] | undefined) || null;
  const exhibit = item.exhibit ? mediaUrl(project, item.paper.dir, item.exhibit) : null;
  const videoRef = selectedVideo || item.video;
  const video = videoRef ? mediaUrl(project, item.paper.dir, videoRef)
    + (item.video_revision ? `&v=${encodeURIComponent(item.video_revision)}` : "") : null;
  const shownPanel = item.panels[side] || pa;
  const shownPaper = shownPanel ? paperOf(item, shownPanel.paper_dir) : item.paper;
  // The main PDF stands in ONLY for a main/unknown-role document; a
  // publisher render or SI member shows on its native image instead of
  // beside a page it was never printed on (`paneDocument`).
  const pane = paneDocument(shownPanel, shownPaper);
  const documentPath = pane.kind === "pdf" ? pane.path : undefined;
  const pdfUrl = pane.kind === "pdf" && shownPaper ? mediaUrl(project, shownPaper.dir, pane.path) : null;
  // Follows the SHOWN side: on a cross-paper item A and B are different
  // papers, so one link that tracks the visible panel is right where two
  // fixed links would make the reader work out which is which. The paper
  // directory is the DOI with the slash written `--`, and is the only DOI a
  // paper with no metadata record has.
  const pubpeer = pubpeerLink(
    shownPaper?.doi
    || (shownPaper?.dir?.includes("--") ? shownPaper.dir.replace("--", "/") : null),
    shownPaper?.pubpeer_url,
    shownPaper?.title,
  );
  const paneTargets = item.targets.filter((t) => t.paper_dir === shownPanel?.paper_dir
    && (!t.document_path || t.document_path === documentPath
      || shownPanel?.placements.some(p => p.document_path === t.document_path)));
  const matchBoxes = pdfMatches.filter(b =>
    b.paperDir === shownPanel?.paper_dir && b.documentPath === documentPath);
  // Carries `method`, so a page-only image placement reads "Figure on
  // p. N" in the pane rather than the numeric-token sentence.
  const locator = buildPaneLocator(paneTargets);
  // Recording a missed duplication: the PDF pane draws boxes A then B.
  const drawRegion = missed && missed.step !== "details" && pdfUrl && shownPaper && documentPath
    ? (r: { page: number; bbox: [number, number, number, number] }) => {
        const regions = [...missed.regions, regionFor(item, shownPaper.dir, documentPath, r.page, r.bbox)];
        setMissed({ ...missed, regions, step: regions.length >= 2 ? "details" : "B" });
      } : null;
  const focus = focusTid || paneTargets[0]?.id || null;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 12px",
                       borderBottom: "1px solid var(--line)", background: "var(--panel)", flexShrink: 0 }}>

      <RunSelector project={project} component="image_forensics" value={selection} options={[]} onChange={s=>router.push(itemHref(project, itemId, s))} />
        <Link href={queueHref(project, selection)} style={{ fontSize: 12 }}>← queue</Link>
        <div className="mono" style={{ fontSize: 12, minWidth: 0, overflow: "hidden", textOverflow: "ellipsis" }}>
          {item.id}
        </div>
        {pubpeer && (
          <a href={pubpeer.href} target="_blank" rel="noreferrer"
             title={pubpeer.label === "PubPeer page" ? "Open this paper's PubPeer discussion" : "Search PubPeer for this paper (by DOI, or by title when it has none)"}
             style={{ fontSize: 12, flexShrink: 0 }}>PubPeer →</a>
        )}
        <div style={{ flex: 1 }} />
        <a href={`/api/images/summary?project=${encodeURIComponent(project)}&run=${encodeURIComponent(item.run_id)}&item=${encodeURIComponent(item.id)}`}
           title="one PNG: both panels, boxes and labels baked in — ready for a PubPeer comment"
           style={{ fontSize: 12 }}>summary PNG</a>
        <span className="muted" style={{ fontSize: 11 }}>{projectName}</span>
        <button type="button" disabled={!prev} onClick={() => go(prev)} title="previous (k)">‹ prev</button>
        <div style={{ fontSize: 12 }}>{nav?.position ? `${nav.position} of ${nav.total}` : nav ? "Outside current filters" : ""}</div>
        <button type="button" disabled={!next} onClick={() => go(next)} title="next (j)">next ›</button>
        <button type="button" disabled={!nextUndecided} onClick={() => go(nextUndecided)} title="n">next undecided ›</button>
      </header>
      {(err || navError) && <p role="alert" style={{padding:"4px 12px"}}>{err || navError}</p>}
      {stale && <p className="muted" role="status" style={{ padding: "4px 12px", margin: 0 }}>Loading the next item… decisions wait until it is shown.</p>}
      {outbox.failures.map(f => (
        <p key={f.body.event_id} role="alert" style={{ padding: "4px 12px", margin: 0 }}>
          Decision “{f.body.decision}” on <Link href={itemHref(project, f.body.item, selection)}>{f.body.item}</Link> was NOT saved: {f.error}{" "}
          <button type="button" onClick={() => { void outbox.submit(f.body).catch(() => undefined); }}>Retry</button>
        </p>
      ))}
      {outbox.pending.size > 0 && <p className="muted" role="status" style={{ padding: "0 12px", margin: 0, fontSize: 11 }}>Saving {outbox.pending.size} decision{outbox.pending.size === 1 ? "" : "s"}…</p>}
      {notice && <p className="muted" role="status" style={{ padding: "4px 12px", margin: 0 }}>{notice}</p>}

      {/* Dan, 2026-09-08: explanation and feedback on the LEFT, the PDF and
          image evidence on the RIGHT, navigation at the right end of the
          header -- the same reading order as the paper page. */}
      <div className={`split${cols.dragging ? " dragging" : ""}`} ref={cols.containerRef}>
        <aside className="split-left" style={{ flex: `0 0 ${detailsOpen ? Math.max(30,cols.pct) : cols.pct}%`, fontSize: 12, minHeight: 0 }}>
          <div style={{ marginBottom: 6 }}>
            <button type="button" disabled={!next} onClick={() => go(next)} title="next (j)">next ›</button>
          </div>
          <PaperReferences item={item} />
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
            {DECISIONS.map(([key, k, label]) => {
              const on = item.decision?.decision === key;
              return (
                <button key={key} type="button" onClick={() => decide(key)} disabled={saving}
                        style={{ fontWeight: on ? 700 : 400, outline: on ? "2px solid var(--accent)" : undefined }}
                        title={`key ${k}`}>
                  <span className="muted">{k}</span> {label}
                </button>
              );
            })}
          </div>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} placeholder="note (saved with the next decision)"
                    style={{ width: "100%", minHeight: 44, fontSize: 12 }} />
          {item.decision && (
            <p className="muted" style={{ margin: "4px 0 8px" }}>
              decided <b>{item.decision.decision}</b> by {item.decision.reviewer} at {item.decision.at}
            </p>
          )}

          {carryOffers && carryOffers.offers.length > 0 && (
            <div role="group" aria-label="Decision on an earlier run" style={{ border: "1px solid var(--line)", padding: 6, margin: "6px 0" }}>
              {carryOffers.offers.slice(0, 1).map(o => (
                <p key={o.event_id} style={{ margin: 0 }}>
                  Decided <b>{o.decision}</b> by {o.reviewer} on run <span className="mono">{o.run}</span>{o.at ? ` (${String(o.at).slice(0, 10)})` : ""}.
                  Same evidence: the panels&apos; archived pixels and crop boxes match.{" "}
                  <button type="button" onClick={() => decide(o.decision, false, undefined, o.run)}>Confirm for this run</button>
                </p>
              ))}
            </div>
          )}
          {carryOffers && !carryOffers.offers.length && carryOffers.unproven > 0 && (
            <p className="muted" style={{ margin: "4px 0" }}>Decided on {carryOffers.unproven} earlier run(s) of this item id, but the evidence differs or cannot be proved the same; not carried over.</p>
          )}
          {filter.spot_check && (
            <div role="group" aria-label="Spot-check this demotion" style={{ border: "1px solid var(--line)", padding: 6, margin: "6px 0" }}>
              <p style={{ margin: "0 0 4px" }}>Spot check: the detector demoted this as <b>{item.detector_kind}</b>. Was it right?</p>
              {/* Right: it is context, i.e. a false positive. Wrong: it is
                  evidence the rule hid; recorded as unsure, to be decided. */}
              <button type="button" onClick={() => decide("false_positive", false, { demotion_check: { verdict: "right", kind: item.detector_kind, seed: filter.spot_check } })}>Demotion right</button>{" "}
              <button type="button" onClick={() => decide("unsure", false, { demotion_check: { verdict: "wrong", kind: item.detector_kind, seed: filter.spot_check } })}>Demotion wrong</button>
            </div>
          )}
          {item.review_conflict && (
            <div role="group" aria-label="Resolve conflicting reviews" style={{ border: "1px solid var(--line)", padding: 6, margin: "6px 0" }}>
              <p role="status" style={{ margin: "0 0 4px" }}>Conflicting reviews:{" "}
                {(item.reviews?.reviewers || []).map((r) => `${r.reviewer}: ${r.decision}`).join(" · ") || "two versions of one imported event"}
              </p>
              {/* A resolution is a new event that names what it settles; both
                  original reviews stay in the history and the export. */}
              <span className="muted">Resolve as: </span>
              {DECISIONS.slice(0, 3).map(([key, , label]) => (
                <button key={key} type="button" disabled={saving} onClick={() => decide(key, true)}>{label}</button>
              ))}
            </div>
          )}
          <p className="muted">{item.publication_status} · {item.screening_status}</p>
          {item.screening_status === "failed" && <p role="status">Screening failed — no validated decision.</p>}
          <AuthorEmails project={project} item={item} />
          <MissedDuplicationPanel project={project} item={item} draft={missed} setDraft={setMissed} canDraw={!!pdfUrl} />
          <button type="button" aria-expanded={detailsOpen} onClick={()=>setDetailsOpen(v=>!v)}>{detailsOpen ? "Hide details" : "Details"}</button>
          {item.kind !== "cross" && <PaperReference paper={shownPaper} />}
          {detailsOpen && <ImageDetails project={project} run={item.run_id} itemId={item.id}/>}
        </aside>

        <div {...cols.separatorProps} />

        <div className={`split-right${rows.dragging ? " dragging" : ""}`} ref={rows.containerRef}>
          {/* `0 1` not `0 0`: at the top of its range the basis plus the
              toolbar can exceed the column, and the pane that must give way
              is this one -- the PDF pane's basis is 0, so it has no shrink
              weight of its own. */}
          <div style={{ padding: 10, overflow: "auto", flex: `0 1 ${rows.pct}%`, minHeight: 0, boxSizing: "border-box" }}>
            {panelErrors.length>0 && (
              <p style={{ color: "var(--sev-impossible)", margin: "4px 0" }}>
                Panel images could not be served: {panelErrors.join("; ")}
              </p>
            )}
            {printed.notes.length > 0 && (
              <p className="muted" style={{ margin: "2px 0 4px", fontSize: 12 }}>
                Shown as printed: {printed.notes.join("; ")}.{printed.raw ? ` Detector's reading on the stored pixels: ${printed.raw}.` : ""}
              </p>
            )}
            <Comparator key={JSON.stringify([project, item.run_id, item.id])} imgA={printedImages[0] || null} imgB={printedImages[item.detector_kind === "intra_panel_clone" ? 0 : 1] || null} srcA={srcA} srcB={item.kind === "within" && item.detector_kind === "intra_panel_clone" ? null : srcB}
                        boxA={boxA as never} boxB={boxB as never} affine={ms.affine}
                        labelA={pa?.figure_label || ""}
                        labelB={pb?.figure_label || ""}
                        exhibit={exhibit} regions={regions as never}
                        measurements={ms} flip={ms.flip === true} transformNote={describeTransform(ms)}
                        video={videoOpen ? video : null}
                        videoActions={videoOpen ? <VideoTools project={project} item={item} onVideo={setSelectedVideo} /> : <button onClick={()=>setVideoOpen(true)}>Video…</button>}
                        fitNonce={cols.settled + rows.settled} />
          </div>
          <div {...rows.separatorProps} />
          <div style={{ display: "flex", gap: 8, alignItems: "center", padding: "4px 10px",
                        fontSize: 12, flexShrink: 0 }}>
            <span>Paper:</span>
            {item.panels.map((p, i) => (
              <button key={p.uid + i} type="button" onClick={() => jumpTo(i as 0 | 1)}
                      style={{ fontWeight: side === i ? 700 : 400 }}
                      title={i === 0 ? "a" : "B (shift+b)"}>
                {"AB"[i]} · {p.paper_dir} {p.figure_label || "(no label)"}
                {p.placements.length ? ` p. ${p.placements.map((x) => x.page).join(", ")}` : " · no page"}
              </button>
            ))}
            <SummaryFigureLauncher project={project} item={item} boxes={pdfMatches} sizes={panelSizes} />
            {shownPaper?.dir && (
              <span style={{ marginLeft: "auto", display: "inline-flex", gap: 10 }}>
                {pdfUrl && (
                  <a href={`${pdfUrl}&download=1`} download title="download this paper's PDF">download PDF</a>
                )}
                <button type="button" title="open the paper's folder in the file browser" disabled={revealing}
                        onClick={async () => {
                          const requestKey = activeKey.current;
                          setRevealing(true); setErr(null); setNotice(null);
                          try {
                            const response = await fetch("/api/reveal", {
                              method: "POST", headers: { "content-type": "application/json" },
                              body: JSON.stringify({ component:"image_forensics", project, dir: shownPaper.dir, f: shownPaper.pdf || undefined }),
                            });
                            const result = await response.json();
                            if (!response.ok || result.error) throw new Error(result.error || response.statusText);
                            if (activeKey.current === requestKey) setNotice(result.note || "Opened in the file browser.");
                          } catch (error) {
                            if (activeKey.current === requestKey) setErr(String(error));
                          } finally { if (activeKey.current === requestKey) setRevealing(false); }
                        }}>{revealing ? "opening…" : "show in folder"}</button>
                {pubpeer && (
                  <a href={pubpeer.href} target="_blank" rel="noreferrer"
                     title={pubpeer.label === "PubPeer page" ? "Open this paper's PubPeer discussion" : "Search PubPeer for this paper (by DOI, or by title when it has none)"}>
                    {pubpeer.label}
                  </a>
                )}
              </span>
            )}
          </div>
          <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
            {!paperReady ? <p>Loading paper…</p> : pdfUrl ? (
              <>
                <PdfZoomControls
                  zoom={zoom}
                  onZoomOut={() => applyZoom(zoomOut(zoom))}
                  onZoomIn={() => applyZoom(zoomIn(zoom))}
                  onFit={refitPdf}
                  style={{ right: 12 }}
                />
                <PdfPane url={pdfUrl} locator={locator} label={"AB"[side]} focusTargetId={focus}
                         zoom={zoom} refitNonce={cols.settled + pdfRefit}
                         imageBoxes={missed ? [...matchBoxes, ...missedBoxes(missed, shownPaper?.dir, documentPath)] : matchBoxes}
                         onDrawRegion={drawRegion} />
              </>
            ) : shownPanel && canReadXml(shownPanel) && !shownPaper?.pdf ? (
              <XmlPaperPane project={project} panel={shownPanel} run={item.run_id}
                item={item} sizes={panelSizes}
                component="image_forensics" revision={String(item.record_revision || '')}
                reason={pane.kind === 'native' || pane.kind === 'none' ? pane.reason : 'No PDF location.'} />
            ) : pane.kind === "native" && shownPanel ? (
              <NativeImagePane item={item} project={project} panel={shownPanel} documentPath={pane.path} reason={pane.reason} />
            ) : (
              <p className="muted" style={{ padding: 12 }}>{pane.kind === "none" ? pane.reason : `No PDF on disk for ${shownPaper?.dir}.`}</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
