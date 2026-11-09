/** Which document the right-hand pane shows for a panel, and the media
 *  reference rules it depends on. Pure; shared by the image boxes and the
 *  summary figure in lib/ and by the item page. */
import type { Panel, PaneDocument, PaperHead } from "./types/images";

/** Browser media references are archive identifiers or paper-relative paths,
 * never producer workspace paths. Keep the server containment checks as well. */
export function isPdfReference(path: string | null | undefined): path is string {
  if (!path) return false;
  const normalized = path.replaceAll("\\", "/");
  if (normalized.startsWith("/") || /^[a-z][a-z0-9+.-]*:/i.test(normalized)
      || normalized.split("/").some(part => part === ".." || part === ".")) return false;
  if (normalized.startsWith("__runs/")) return /^__runs\/[^/]+\/[^/]+$/.test(normalized);
  return normalized.toLowerCase().endsWith(".pdf");
}

export function nativePaneSentence(path: string | null): string {
  return `No PDF location: this panel comes from ${path || "an unresolved document"}; shown on its native image.`;
}

/** Which document the right-hand pane shows for a panel.
 *
 *  The paper's main PDF is substituted ONLY when the panel's own document
 *  is the main article (or its role is unknown) and the recorded path is
 *  not itself a PDF. A publisher render, a DOCX supplement member or an
 *  SI image has no page in that PDF: substituting it painted the main
 *  article beside a panel that was never printed there, so those render
 *  on their native image instead. */
export function paneDocument(panel: Panel | undefined, paper: PaperHead | undefined): PaneDocument {
  const doc = panel?.document;
  const path = doc?.path ?? null;
  const role = doc?.role ?? "unknown";
  if (panel?.paper_dir && paper?.dir && panel.paper_dir !== paper.dir) {
    return { kind: "none", reason: "The selected source belongs to a different paper." };
  }
  // A sealed paper head is the canonical main document for this exact run.
  // Historical cross-panel metadata may still name an expired workspace PDF.
  if (role === "main" && isPdfReference(paper?.pdf) && paper.pdf.startsWith("__runs/")
      && !path?.startsWith("__runs/")) {
    return { kind: "pdf", path: paper.pdf, substituted: true };
  }
  if (isPdfReference(path)) return { kind: "pdf", path, substituted: false };
  if (role === "main" || role === "unknown") {
    if (isPdfReference(paper?.pdf)) return { kind: "pdf", path: paper!.pdf!, substituted: true };
    if (panel?.parent_image || panel?.image) {
      return { kind: "native", path, reason: `No PDF location: no PDF on disk for ${paper?.dir || "this paper"}` };
    }
    return { kind: "none", reason: `No PDF on disk for ${paper?.dir || "this paper"}.` };
  }
  return { kind: "native", path, reason: nativePaneSentence(path) };
}
