/** Shared types and helpers for the image review system: a re-export
 *  barrel. The record types live in lib/types/images.ts, the pane-document
 *  rules in lib/paneDocument.ts and the helpers in lib/images/*.ts (lib/
 *  must not import app/); importers of this module keep working. */
export type { Subfigure, Placement, Rendition, FigureSources, IdentitySidecar, Panel, PaneTarget, PaneLocator, PaneDocument, PaperHead, Decision, ContentSupportData, Item, SpotCheck, Feed, FigureSpan, Filter, QueueSort } from "@/lib/types/images";
export { isPdfReference, nativePaneSentence, paneDocument } from "@/lib/paneDocument";
export * from "@/lib/images/urls";
export * from "@/lib/images/filters";
export * from "@/lib/images/sort";
export * from "@/lib/images/labels";
export * from "@/lib/images/geometry";
