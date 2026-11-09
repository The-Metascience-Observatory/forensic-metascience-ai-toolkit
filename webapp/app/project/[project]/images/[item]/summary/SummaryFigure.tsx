"use client";

import { createPortal } from "react-dom";
import { useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import type { Item } from "@/app/images/lib";
import { pubpeerLink } from "@/lib/citation";
import { NEON, type CropEditor } from "./CropEditor";
import { AddToWebsite } from "./AddToWebsiteForm";
import { AuthorEmails } from "../AuthorEmails";

/** One PubPeer link per paper of the finding (its page when recorded, else
 *  a DOI search), labelled A/B on a cross-paper item. Same rule as the page. */
function pubpeerLinks(item: Item): { label: string; href: string; title: string }[] {
  const papers = item.papers || [item.paper];
  const dirs = [...new Set(item.panels.map(p => p.paper_dir).filter(Boolean))];
  return dirs.flatMap((dir, i) => {
    const paper = papers.find(p => p?.dir === dir);
    const link = pubpeerLink(paper?.doi || (dir.includes("--") ? dir.replace("--", "/") : null), paper?.pubpeer_url, paper?.title);
    if (!link) return [];
    return [{ href: link.href, label: dirs.length > 1 ? `PubPeer ${"AB"[i] || i + 1}` : "PubPeer",
      title: `${link.label}: ${paper?.title || dir}` }];
  });
}

/** The summary figure dialog: toolbar, match-box controls, the resize
 *  panel, the "add to website" form and the editor canvas, in a portal.
 *  Mounted only while the figure is shown; the state lives in
 *  `SummaryFigureButton` and the crop editor. */
export function SummaryFigure({ project, item, editor, meta, error, busy, website, setWebsite, resizing, setResizing,
  close, generate, download, copy, cropAndDownload, exportBlob, openResize, changeBoxSize, boxPercent, canExpand }: {
  project: string; item: Item; editor: CropEditor;
  meta: { name: string; note: string | null }; error: string | null; busy: boolean;
  website: boolean; setWebsite: Dispatch<SetStateAction<boolean>>;
  resizing: boolean; setResizing: (resizing: boolean) => void;
  close: () => void; generate: (force?: boolean) => Promise<boolean>;
  download: (suffix?: string) => Promise<void>; copy: () => Promise<void>; cropAndDownload: () => Promise<void>;
  exportBlob: () => Promise<Blob>; openResize: () => void;
  changeBoxSize: (percent: number) => void; boxPercent: number | undefined; canExpand: boolean;
}) {
  const { floating, setFloating, setSelection, setHistory, brand, setBrand, copied, boxColor, setBoxColor, canvasRef,
    settle, usable, erase, crop, undo, onPointerDown, onPointerMove, onPointerUp, sel, edited, scaleTo, pct, hint } = editor;
  // The toolbar wraps on a narrow window; the image gets the height it leaves.
  const toolbarRef = useRef<HTMLDivElement>(null);
  const [toolbarH, setToolbarH] = useState(40);

  useEffect(() => {
    const el = toolbarRef.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setToolbarH(el.getBoundingClientRect().height));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return createPortal(
  <div role="dialog" aria-modal="true" aria-label="Summary figure" onClick={close}
       style={{ position: "fixed", inset: 0, zIndex: 50, background: "rgba(0,0,0,.6)",
                display: "flex", alignItems: "center", justifyContent: "center", padding: 24 }}>
    <div onClick={e => e.stopPropagation()}
         style={{ background: "var(--panel)", border: "1px solid var(--line)", borderRadius: 6, padding: 12,
                  maxWidth: "100%", maxHeight: "100%", overflow: "auto", display: "flex", flexDirection: "row", gap: 12 }}>
      {/* The addresses a PubPeer post notifies, beside the figure it will
          carry: read as soon as the dialog opens, each with a copy button. */}
      <aside aria-label="Author e-mails"
             style={{ flex: "0 0 240px", width: 240, overflow: "auto", fontSize: 12, alignSelf: "stretch",
                      borderRight: "1px solid var(--line)", paddingRight: 10 }}>
        <b>Author e-mails</b>
        <p className="muted" style={{ fontSize: 11, margin: "4px 0 0" }}>
          From the paper&apos;s PDF, or its XML when there is no PDF; for PubPeer&apos;s notify field.
        </p>
        <AuthorEmails project={project} item={item} autoStart />
      </aside>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, minWidth: 0 }}>
      <div ref={toolbarRef} style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <b>Summary figure{edited ? " (edited)" : ""}</b>
        <span className="muted">{hint}</span>
        {meta.note && <span className="muted">{meta.note}</span>}
        {error && <span role="alert" style={{ color: "var(--sev-impossible)" }}>{error}</span>}
        <span style={{ flex: 1 }} />
        <span style={{ display: "inline-flex", gap: 3, alignItems: "center" }} title="Draw a box: pick a colour, then drag on the image">
          <button type="button" onClick={() => setBoxColor(null)} aria-pressed={!boxColor}
                  style={{ fontWeight: boxColor ? undefined : "bold" }}>select</button>
          {NEON.map(([name, hex]) => (
            <button key={hex} type="button" onClick={() => { setBoxColor(hex); setSelection(null); }}
                    aria-label={`draw ${name} box`} aria-pressed={boxColor === hex} title={`draw a ${name} box`}
                    style={{ width: 22, height: 22, padding: 0, background: hex, border: boxColor === hex ? "3px solid #111" : "1px solid #555",
                             borderRadius: 4, cursor: "pointer" }} />
          ))}
        </span>
        <button type="button" onClick={openResize} disabled={!floating && !usable(sel)}
                title="Scale the selected picture by a percentage, proportions locked">resize</button>
        {floating && <button type="button" onClick={() => { settle(); setResizing(false); }} title="Put the piece down here (Enter)">place</button>}
        <button type="button" onClick={() => { if (usable(sel)) erase(sel); }} disabled={!usable(sel)}
                title="Blank the selection to white (Delete)">blank</button>
        <button type="button" onClick={() => { if (usable(sel)) crop(sel); }} disabled={!usable(sel)}
                title="Crop to the selection">crop</button>
        <button type="button" onClick={cropAndDownload} disabled={!usable(sel)}
                title="Crop to the selection, keep the crop here, and download it">crop &amp; download</button>
        <button type="button" onClick={undo} disabled={!edited} title="Undo the last edit (Ctrl+Z)">undo</button>
        <button type="button" disabled={!edited} title="Back to the image as generated, discarding every edit"
                onClick={() => { setFloating(null); setSelection(null); setResizing(false); setHistory(h => h.slice(0, 1)); }}>reset</button>
        <button type="button" disabled={busy} title="Render the figure again from the PDF (discards edits)"
                onClick={() => void generate(true)}>regenerate</button>
        <label title="Credit line in the bottom-right corner" style={{ display: "flex", gap: 4, alignItems: "center" }}>
          <input type="checkbox" checked={brand} onChange={e => setBrand(e.target.checked)} /> logo
        </label>
        <button type="button" onClick={() => download()}>download PNG</button>
        <button type="button" onClick={copy}>{copied ? "copied" : "copy"}</button>
        {pubpeerLinks(item).map(l => (
          <a key={l.href} href={l.href} target="_blank" rel="noopener noreferrer" title={l.title}>{l.label} ↗</a>
        ))}
        <button type="button" onClick={() => setWebsite(w => !w)} aria-expanded={website}
                title="Put this figure and its PubPeer comment on the Observatory website's image-findings page">add to website</button>
        <button type="button" onClick={close}>close</button>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <b>Match boxes</b>
        <button type="button" onClick={() => changeBoxSize(boxPercent === 0 ? 100 : (boxPercent ?? 100) + 25)} disabled={!canExpand || (boxPercent ?? 100) >= 1000}>expand boxes +25%</button>
        <button type="button" onClick={() => changeBoxSize((boxPercent ?? 100) - 25)} disabled={!canExpand || boxPercent === 100 || boxPercent === 0}>shrink boxes −25%</button>
        <button type="button" onClick={() => changeBoxSize(0)} disabled={!canExpand || boxPercent === 0}
                title="Remove the match boxes from the figure (original boxes brings them back)">remove boxes</button>
        <span>{boxPercent === 0 ? "boxes removed" : boxPercent !== undefined ? `${boxPercent}%` : "custom edits"}</span>
        <button type="button" onClick={() => changeBoxSize(100)} disabled={!canExpand || boxPercent === 100}>original boxes</button>
        <span className="muted">{boxPercent === undefined || floating
          ? "Reset image edits to adjust the match boxes."
          : "Adjust outlines before cropping. Larger boxes are a visual guide; check their extent against the images."}</span>
      </div>
      {resizing && floating && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", border: "1px solid var(--line)", borderRadius: 6, padding: 8 }}>
          <b>Resize</b>
          <span className="muted">the selected picture, proportions locked; then place it</span>
          <button type="button" onClick={() => scaleTo(pct - 10)}>−10%</button>
          <input type="number" min={5} max={1000} step={5} value={pct} style={{ width: 70 }}
                 onChange={e => { const v = Number(e.target.value); if (Number.isFinite(v) && v > 0) scaleTo(v); }} />
          <span>%</span>
          <button type="button" onClick={() => scaleTo(pct + 10)}>+10%</button>
          <button type="button" onClick={() => scaleTo(50)}>½</button>
          <button type="button" onClick={() => scaleTo(200)}>2×</button>
          <button type="button" onClick={() => scaleTo(100)}>100%</button>
          <span style={{ flex: 1 }} />
          <button type="button" onClick={() => { settle(); setResizing(false); }}>place</button>
          <button type="button" onClick={() => { setFloating(null); setResizing(false); }}>cancel</button>
        </div>
      )}
      {website && <AddToWebsite project={project} item={item} exportBlob={exportBlob} onClose={() => setWebsite(false)} />}
      </div>
      <div style={{ alignSelf: "center", minHeight: 0, lineHeight: 0, overflow: "hidden", touchAction: "none" }}>
        <canvas ref={canvasRef} role="img" aria-label="Summary figure: the source figure(s) with duplication boxes"
                onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={onPointerUp}
                style={{ display: "block", maxWidth: "100%", maxHeight: `calc(100vh - ${Math.ceil(toolbarH) + 84}px)`, width: "auto", height: "auto",
                         userSelect: "none" }} />
      </div>
      </div>
    </div>
  </div>, document.body
  );
}
