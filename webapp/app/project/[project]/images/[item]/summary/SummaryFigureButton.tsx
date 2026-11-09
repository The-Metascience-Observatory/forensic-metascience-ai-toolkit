"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Item } from "@/app/images/lib";
import type { ImagePdfBox } from "@/lib/imagePdfBoxes";
import type { ImageSize } from "@/lib/imageXmlBoxes";
import { nativeSides, nativeSummaryGroups, summaryGroups, type SummaryGroup } from "@/lib/summaryGroups";
import type { RenderedFigure } from "./RenderedFigure";
import { annotateFigure, flatten, placePiece } from "./CanvasDraw";
import { compose } from "./ComposeFigure";
import { fetchFigures } from "./useFigureData";
import { saveBlob, toBlob } from "./ExportPng";
import { useCropEditor } from "./CropEditor";
import { SummaryFigure } from "./SummaryFigure";

export function SummaryFigureButton({ project, item, boxes, sizes, autoStart }: { project: string; item: Item; boxes: ImagePdfBox[];
  /** The panels' decoded sizes: the measured frame when the item does not record one. */
  sizes?: (ImageSize | null)[];
  /** The click that loaded this (lazily imported) module, replayed once. */
  autoStart?: "generate" | "website" }) {
  const [busy, setBusy] = useState(false);
  const [meta, setMeta] = useState<{ name: string; note: string | null } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [website, setWebsite] = useState(false);
  const [resizing, setResizing] = useState(false);

  const generated = useRef<RenderedFigure | null>(null);
  const boxScales = useRef(new WeakMap<HTMLCanvasElement, number>());
  // The dialog can be closed and reopened: the figure and its edits stay
  // until the item changes or a new one is generated.
  const [shown, setShown] = useState(false);
  const editor = useCropEditor(shown && !!meta);
  const { open, content, history, floating, setFloating, selection, setSelection, brand, setCopied, boxColor, setBoxColor,
    setHistory, settle, selected, usable, lift, erase, crop, undo, push } = editor;

  const discard = useCallback(() => {
    generated.current = null;
    setShown(false); setMeta(null); setHistory([]); setFloating(null); setSelection(null);
    setCopied(false); setWebsite(false); setResizing(false);
  }, [setHistory, setFloating, setSelection, setCopied]);
  useEffect(() => { discard(); setError(null); }, [item.id, item.run_id, discard]);
  /** Hide the dialog, keeping the edits; a lifted piece is placed where it is. */
  const close = useCallback(() => {
    if (floating) { const { canvas } = placePiece(floating); setHistory(h => [...h, canvas]); setFloating(null); }
    setSelection(null); setWebsite(false); setResizing(false); setShown(false);
  }, [floating, setHistory, setFloating, setSelection]);

  async function exportBlob(): Promise<Blob> {
    const current = settle();
    if (!current) throw new Error("nothing to export");
    const flat = flatten(current, brand);
    try { return await toBlob(flat); } finally { flat.width = 0; flat.height = 0; }
  }
  async function download(suffix = "") {
    if (!meta) return;
    try { saveBlob(await exportBlob(), `${meta.name}${suffix}.png`); }
    catch (e) { setError(`Download failed: ${String(e)}`); }
  }
  async function copy() {
    try { await navigator.clipboard.write([new ClipboardItem({ "image/png": exportBlob() })]); setCopied(true); }
    catch (e) { setError(`Copy failed: ${String(e)}`); }
  }
  async function cropAndDownload() {
    const sel = selected();
    if (!usable(sel) || !meta) return;
    const out = crop(sel);
    if (!out) return;
    try { const flat = flatten(out, brand); saveBlob(await toBlob(flat), `${meta.name}_crop.png`); flat.width = 0; }
    catch (e) { setError(`Crop failed: ${String(e)}`); }
  }

  // While open, the page's shortcuts (Esc = back to queue, j/k = navigate)
  // must not act behind the dialog. Esc puts back a lifted region, then
  // clears a selection, then closes; Enter places; Delete blanks; Ctrl+Z undoes.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.tagName === "INPUT" || t.tagName === "TEXTAREA" || t.tagName === "SELECT" || t.isContentEditable)) {
        e.stopPropagation(); // typing stays in the form, away from the page's shortcuts
        if (e.key === "Escape") setWebsite(false);
        return;
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); undo(); return; }
      if (e.ctrlKey || e.metaKey) return;
      e.preventDefault();
      if (e.key === "Escape") {
        if (boxColor) setBoxColor(null); else if (floating) setFloating(null); else if (selection) setSelection(null); else close();
      }
      else if (e.key === "Enter" && floating) settle();
      else if (e.key === "Delete" || e.key === "Backspace") { const s = selected(); if (usable(s)) erase(s); }
    };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  });

  const pdfGroups = summaryGroups(item, boxes);
  const pending = nativeSides(item, pdfGroups);
  const available = pdfGroups.length > 0 || pending.length > 0;

  async function generate(force = false): Promise<boolean> {
    if (!force && content && meta) { setShown(true); return true; } // reopen, edits kept
    setBusy(true); setError(null); setCopied(false);
    try {
      if (!available) throw new Error("No PDF placement or figure image for either panel -- nothing to screenshot.");
      const dirs = [...new Set(pending.map(s => item.panels[s].paper_dir))];
      const native = pending.length ? nativeSummaryGroups(item, pending, await fetchFigures(project, item, dirs), sizes) : [];
      if (pending.length && !native.length && !pdfGroups.length)
        throw new Error("This paper has no PDF, and neither panel could be linked to one of its figure images.");
      const groups: SummaryGroup[] = [...pdfGroups, ...native].sort((a, b) => a.sides[0] - b.sides[0]);
      const figure = await compose(project, item, groups);
      const { unreferenced } = figure;
      const missing = groups.filter(g => !g.boxes.length).length;
      const unlinked = pending.filter(s => !native.some(g => g.sides.includes(s))).map(s => "AB"[s]);
      const notes = [missing ? `${missing} of ${groups.length} figure(s) have no exact placement, so no box is drawn there.` : "",
        unlinked.length ? `Panel ${unlinked.join(" and ")} has no PDF and could not be linked to a figure image, so it is not shown.` : "",
        unreferenced ? `No reference could be found for ${unreferenced} paper(s).` : ""].filter(Boolean);
      discard();
      generated.current = figure;
      const canvas = annotateFigure(figure, 100);
      boxScales.current.set(canvas, 100);
      setHistory([canvas]);
      setMeta({ name: `summary_figure_${item.id.replace(/[^\w.-]+/g, "_")}`, note: notes.join(" ") || null });
      setShown(true);
      return true;
    } catch (e) { setError(String(e instanceof Error ? e.message : e)); return false; }
    finally { setBusy(false); }
  }

  const boxPercent = content ? boxScales.current.get(content) : undefined;
  const canExpand = boxPercent !== undefined && !floating && !!generated.current?.boxes.some(b => !b.dashed);
  const changeBoxSize = (percent: number) => {
    if (!canExpand || !generated.current) return;
    const next = percent <= 0 ? 0 : Math.max(100, Math.min(1000, percent));
    const canvas = annotateFigure(generated.current, next);
    boxScales.current.set(canvas, next);
    push(canvas); setSelection(null);
  };
  const openResize = () => {
    if (!floating) { const s = selected(); if (!usable(s)) return; lift(s); }
    setResizing(true);
  };

  const started = useRef(false);
  useEffect(() => {
    if (!autoStart || started.current) return;
    started.current = true;
    void generate().then(ok => { if (ok && autoStart === "website") setWebsite(true); });
  // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on the mount the click caused
  }, []);

  return (
    <>
      <button type="button" onClick={() => generate()} disabled={busy || !available}
              title={!available ? "No PDF placement or figure image for this finding"
                : content ? "Reopen the summary figure with its edits"
                : pdfGroups.length ? "Render the whole figure(s) from the PDF with the duplication boxes drawn on"
                : "Render the whole figure image(s) with the duplication boxes drawn on"}>
        {busy ? "generating…" : content ? `open summary figure${history.length > 1 ? " (edited)" : ""}` : "generate summary figure"}
      </button>
      <button type="button" onClick={async () => { if (await generate()) setWebsite(true); }} disabled={busy || !available}
              title="Generate the summary figure and put it, with its PubPeer comment, on the Observatory website's image-findings page">
        add to website
      </button>
      {error && !open && <span role="alert" style={{ color: "var(--sev-impossible)" }}>{error}</span>}
      {open && meta && (
        <SummaryFigure project={project} item={item} editor={editor} meta={meta} error={error} busy={busy}
                       website={website} setWebsite={setWebsite} resizing={resizing} setResizing={setResizing}
                       close={close} generate={generate} download={download} copy={copy} cropAndDownload={cropAndDownload}
                       exportBlob={exportBlob} openResize={openResize} changeBoxSize={changeBoxSize}
                       boxPercent={boxPercent} canExpand={canExpand} />
      )}
    </>
  );
}
