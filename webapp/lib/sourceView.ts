/** Which document the right-hand pane draws, and who gets to decide.
 *
 * Kept DOM-free on purpose: `test/smoke.mjs` imports these directly under
 * `node --experimental-strip-types`, the same reason `haystack.ts` is pure.
 *
 * The rule the whole module exists for: a paper that ships publisher XML and a
 * PDF opens in the XML. The XML is the publisher's own text, it reflows, and
 * its tables are real `<table>` markup rather than pixels. The PDF stays one
 * click away because it is the document of record for how the page LOOKED.
 */

import { jumpable } from "./targets.ts";

export type Surface = "pdf" | "xml" | "sheet" | "none";

/** localStorage key, namespaced like `metascience.theme` / `.split` / `.exhibit`. */
export const VIEW_KEY = "metascience.sourceView";

export const SHEET_KINDS = new Set(["xlsx", "xls", "csv", "tsv"]);

/** A stored preference we are willing to honour. Anything else is "unset". */
export function parseStoredView(raw: string | null | undefined): Surface | null {
  return raw === "pdf" || raw === "xml" ? raw : null;
}

export function sheetArtefact(issue: any): any {
  return (issue?.artefacts || []).find((a: any) => SHEET_KINDS.has(a.kind));
}

/** A PDF the FINDING names, as opposed to the paper's own main PDF. */
export function extraPdfArtefact(issue: any, article: any): any {
  return (issue?.artefacts || []).find(
    (a: any) => a.kind === "pdf" && a.relpath && a.relpath !== article?.pdf_relpath,
  );
}

/** Views this paper can actually render. Never offer one we cannot draw.
 *
 * `article.html` is NOT sufficient for "xml": it is also non-null for
 * `mode === "html"` (publisher HTML) and `mode === "text"` (extracted text).
 * Offering an XML toggle on those would name a format the paper does not have,
 * so the XML view is gated on `has_xml` as well.
 */
export function availableViews(
  article: any,
  sheetFound: boolean,
  extraPdfFound: boolean,
): Surface[] {
  const out: Surface[] = [];
  if (extraPdfFound || article?.pdf_relpath) out.push("pdf");
  if (article?.has_xml && article?.html) out.push("xml");
  if (sheetFound) out.push("sheet");
  return out;
}

/** The surface to draw, absent an explicit per-target jump.
 *
 * A sheet artefact keeps the priority it has always had: the finding names a
 * spreadsheet, so the spreadsheet is the evidence. Otherwise a stored choice
 * wins, and with nothing stored the XML wins over the PDF.
 */
export function defaultView(
  available: Surface[],
  stored: Surface | null,
): Surface {
  if (available.includes("sheet")) return "sheet";
  if (stored && available.includes(stored)) return stored;
  if (available.includes("xml")) return "xml";
  if (available.includes("pdf")) return "pdf";
  return "none";
}

/** Show the toggle only when there is a real choice to make. */
export function canToggle(available: Surface[]): boolean {
  return available.includes("pdf") && available.includes("xml");
}

/** Why the XML pane is showing no mark. Never let that read as "nothing here".
 *
 * Four different facts, kept apart on purpose. An image finding has no text to
 * anchor anywhere; a supplement quote is legitimately absent from the article;
 * a PDF-only anchor is our matcher falling short; a section hit is a real but
 * imprecise locate that may scroll and must NOT mark. Collapsing them into one
 * "not found" would state the wrong thing three times out of four.
 */
export type UnanchoredReason =
  | { code: "image_finding" }
  | { code: "supplement"; file: string }
  | { code: "section_only"; section: string }
  | { code: "pdf_only" }
  | { code: "unlocated" }
  | null;

export function unanchoredReason(
  surface: Surface,
  issue: any,
  targets: any[] | undefined,
  hasXmlQuote: boolean,
): UnanchoredReason {
  if (surface !== "xml") return null;
  if (hasXmlQuote) return null;

  const all = targets || [];
  if (all.some((t: any) => t.kind === "xml_cell" && jumpable(t))) return null;
  const xmlT = all.find((t: any) => t.kind === "xml_text");
  if (xmlT && xmlT.section) {
    return { code: "section_only", section: String(xmlT.section) };
  }
  if (issue?.kind === "image") return { code: "image_finding" };

  const sheet = sheetArtefact(issue);
  if (sheet) {
    return { code: "supplement", file: String(sheet.basename || sheet.relpath || "") };
  }
  const pdfJump = all.some(
    (t: any) => (t.kind === "pdf_text" || t.kind === "pdf_bbox" || t.kind === "pdf_cell")
      && jumpable(t),
  );
  if (pdfJump) return { code: "pdf_only" };
  return { code: "unlocated" };
}

// --- PDF zoom -----------------------------------------------------------
//
// 1 means "fit the pane width", which is what the PDF pane always did. The
// steps are the familiar viewer ladder rather than a continuous slider: a
// reviewer comparing a table digit against a claim wants to land on the same
// magnification twice, not somewhere near it.

export const ZOOM_KEY = "metascience.pdfZoom";
export const ZOOM_STEPS = [0.5, 0.75, 1, 1.25, 1.5, 2, 3] as const;
export const ZOOM_FIT = 1;

/** The step at or above `z`, clamped. Handles a stored value off the ladder. */
function stepIndex(z: number): number {
  const i = ZOOM_STEPS.findIndex((s) => s >= z - 1e-9);
  return i < 0 ? ZOOM_STEPS.length - 1 : i;
}

export function zoomIn(z: number): number {
  const i = stepIndex(z);
  // Off-ladder values step UP to the next rung, not past it.
  const next = ZOOM_STEPS[i] > z + 1e-9 ? i : i + 1;
  return ZOOM_STEPS[Math.min(next, ZOOM_STEPS.length - 1)];
}

export function zoomOut(z: number): number {
  const i = stepIndex(z);
  const prev = ZOOM_STEPS[i] < z - 1e-9 ? i : i - 1;
  return ZOOM_STEPS[Math.max(prev, 0)];
}

export function canZoomIn(z: number): boolean {
  return z < ZOOM_STEPS[ZOOM_STEPS.length - 1] - 1e-9;
}

export function canZoomOut(z: number): boolean {
  return z > ZOOM_STEPS[0] + 1e-9;
}

/** A stored zoom we are willing to honour; anything else means "fit". */
export function parseStoredZoom(raw: string | null | undefined): number {
  const n = Number(raw);
  if (!Number.isFinite(n)) return ZOOM_FIT;
  return ZOOM_STEPS.includes(n as typeof ZOOM_STEPS[number]) ? n : ZOOM_FIT;
}

export function zoomLabel(z: number): string {
  return `${Math.round(z * 100)}%`;
}
