"use client";
import { useState } from "react";
import type { Item } from "@/app/images/lib";
import type { ImagePdfBox } from "@/lib/imagePdfBoxes";
import { readReviewer } from "@/app/ReviewerChip";

/** Record a duplication the detector did NOT flag: box A and box B drawn on
 *  the paper's pages, a manipulation type and a note. Saved as an immutable
 *  local event and exported as ground truth (`image-reviews-export
 *  --missed-out`), so the detector's recall can be measured on it. */
export type MissedRegion = { paper_dir: string; document: string; page: number; bbox_pt: [number, number, number, number];
  panel_uid?: string | null; figure?: string | null };
export type MissedDraft = { step: "A" | "B" | "details"; regions: MissedRegion[]; manipulation: string; note: string };

export const MANIPULATIONS: [string, string][] = [
  ["whole_panel_reuse", "Whole-panel reuse"], ["partial_overlap", "Partial overlap"],
  ["rotation_flip", "Rotation / flip"], ["splice", "Splice"], ["clone", "Clone (within one panel)"], ["other", "Other"],
];
const COLOR = "#e8590c";

function overlap(a: number[], b: number[]) {
  const ix = Math.max(0, Math.min(a[2], b[2]) - Math.max(a[0], b[0])), iy = Math.max(0, Math.min(a[3], b[3]) - Math.max(a[1], b[1]));
  const small = Math.min((a[2] - a[0]) * (a[3] - a[1]), (b[2] - b[0]) * (b[3] - b[1]));
  return small > 0 ? ix * iy / small : 0;
}

/** The item's own panel under a drawn box, when one is placed there. */
export function regionFor(item: Item, paperDir: string, document: string, page: number, bbox: [number, number, number, number]): MissedRegion {
  let best: { uid: string; figure: string | null; score: number } | null = null;
  for (const panel of item.panels) {
    if (panel.paper_dir !== paperDir) continue;
    for (const pl of panel.placements) {
      if (pl.page !== page || !pl.bbox || pl.bbox.length !== 4 || (pl.document_path && pl.document_path !== document)) continue;
      const score = overlap(pl.bbox, bbox);
      if (score >= 0.5 && (!best || score > best.score)) best = { uid: panel.uid, figure: pl.figure_label || panel.figure_label, score };
    }
  }
  return { paper_dir: paperDir, document, page, bbox_pt: bbox, panel_uid: best?.uid ?? null, figure: best?.figure ?? null };
}

export function missedBoxes(draft: MissedDraft | null, paperDir: string | undefined, document: string | undefined): ImagePdfBox[] {
  if (!draft) return [];
  return draft.regions.flatMap((r, i) => r.paper_dir === paperDir && r.document === document ? [{
    page: r.page, tid: `missed:${"AB"[i]}`, paperDir: r.paper_dir, documentPath: r.document, color: COLOR,
    regionLabel: `missed ${"AB"[i]}`,
    points: [[r.bbox_pt[0], r.bbox_pt[1]], [r.bbox_pt[2], r.bbox_pt[1]], [r.bbox_pt[2], r.bbox_pt[3]], [r.bbox_pt[0], r.bbox_pt[3]]],
  } as ImagePdfBox] : []);
}

export function MissedDuplicationPanel({ project, item, draft, setDraft, canDraw }: {
  project: string; item: Item; draft: MissedDraft | null; setDraft: (d: MissedDraft | null) => void; canDraw: boolean;
}) {
  const [status, setStatus] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  if (!draft) return (
    <p style={{ margin: "6px 0" }}>
      <button type="button" disabled={!canDraw} onClick={() => { setStatus(null); setDraft({ step: "A", regions: [], manipulation: "partial_overlap", note: "" }); }}
              title={canDraw ? "Draw two boxes on the paper for a duplication the detector did not flag" : "Needs the paper's PDF in the pane"}>
        Record a missed duplication…
      </button>
      {status && <span className="muted" role="status"> {status}</span>}
    </p>
  );
  async function save() {
    const reviewer = readReviewer().trim();
    if (!reviewer) { setStatus("Set your name in the header first."); return; }
    setSaving(true); setStatus(null);
    try {
      const response = await fetch("/api/images/missed", { method: "POST", headers: { "content-type": "application/json" },
        body: JSON.stringify({ project, reviewer, manipulation: draft!.manipulation, note: draft!.note, regions: draft!.regions,
          run: item.run_id, item: item.id, event_id: "mx_" + globalThis.crypto.randomUUID().replace(/-/g, "") }) });
      const body = await response.json();
      if (!response.ok || body.error) throw new Error(body.error || response.statusText);
      setDraft(null); setStatus("Missed duplication recorded.");
    } catch (error) { setStatus(`Not saved: ${error instanceof Error ? error.message : String(error)}`); }
    finally { setSaving(false); }
  }
  const describe = (r: MissedRegion, i: number) =>
    `${"AB"[i]}: p. ${r.page}${r.figure ? ` · ${r.figure}` : ""}${r.panel_uid ? "" : " · no known panel under it"}`;
  return (
    <fieldset style={{ margin: "6px 0", padding: 6 }}>
      <legend>Missed duplication</legend>
      {draft.regions.map((r, i) => <div key={i} className="muted">{describe(r, i)}</div>)}
      {draft.step !== "details" ? (
        <p role="status" style={{ margin: "4px 0" }}>
          Drag on the PDF to draw box <b>{draft.step}</b>{draft.step === "B" ? " (switch side A/B above to reach another figure)" : ""}.
          {!canDraw && " The PDF is not shown for this side."}
        </p>
      ) : (
        <>
          <label>Manipulation{" "}
            <select value={draft.manipulation} onChange={e => setDraft({ ...draft, manipulation: e.target.value })}>
              {MANIPULATIONS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>
          <textarea value={draft.note} onChange={e => setDraft({ ...draft, note: e.target.value })} placeholder="note (what is duplicated, and why it is not the detector's)"
                    style={{ width: "100%", minHeight: 40, fontSize: 12 }} />
          <button type="button" disabled={saving} onClick={save}>{saving ? "saving…" : "Save"}</button>{" "}
        </>
      )}
      {draft.regions.length > 0 && <button type="button" onClick={() => setDraft({ ...draft, step: draft.regions.length === 2 ? "B" : "A", regions: draft.regions.slice(0, -1) })}>Redraw last box</button>}{" "}
      <button type="button" onClick={() => setDraft(null)}>Cancel</button>
      {status && <p role="alert">{status}</p>}
    </fieldset>
  );
}
