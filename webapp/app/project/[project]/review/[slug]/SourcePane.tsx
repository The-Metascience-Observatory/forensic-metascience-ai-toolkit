"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { KeyboardEvent as ReactKeyboardEvent, PointerEvent } from "react";

import { HtmlArticlePane } from "./HtmlArticlePane";
import { PdfPane } from "./PdfPane";
import { PdfZoomControls } from "./PdfZoomControls";
import { SpreadsheetPane } from "./SpreadsheetPane";
import { jumpable, xmlCells } from "@/lib/targets";
import {
  extraPdfArtefact, parseStoredZoom, sheetArtefact,
  unanchoredReason, zoomIn, zoomOut, ZOOM_FIT, ZOOM_KEY,
  type Surface, type UnanchoredReason,
} from "@/lib/sourceView";

function mediaUrl(project: string, dir: string, rel: string) {
  return `/api/media?project=${encodeURIComponent(project)}`
    + `&dir=${encodeURIComponent(dir)}&f=${encodeURIComponent(rel)}`;
}

const EXHIBIT_KEY = "metascience.exhibit";
const EXHIBIT_DEFAULT = 82;
const EXHIBIT_MIN = 40;
const EXHIBIT_MAX = 92;

function clampExhibit(pct: number): number {
  return Math.min(EXHIBIT_MAX, Math.max(EXHIBIT_MIN, pct));
}

function readExhibitPct(): number {
  if (typeof window === "undefined") return EXHIBIT_DEFAULT;
  const n = Number(window.localStorage.getItem(EXHIBIT_KEY));
  if (Number.isFinite(n) && n >= EXHIBIT_MIN && n <= EXHIBIT_MAX) return n;
  return EXHIBIT_DEFAULT;
}

export function SourcePane({ project, slug, dir, article, issue, locator, extras,
  surface, canSwitch, onSurface, focusTargetId }: {
  project: string;
  slug: string;
  dir: string;
  article: any;
  issue: any;
  locator: any;
  extras?: any;
  /** Already resolved by Reviewer: the toggle preference, or an explicit jump. */
  surface: Surface;
  /** Both a PDF and an XML exist, so there is a real choice to offer. */
  canSwitch: boolean;
  onSurface: (s: Surface) => void;
  focusTargetId?: string | null;
}) {
  const mode = article?.mode || "none";
  const doiUrl = article?.doi_url as string | null;
  const warning = article?.warning as string | null;
  const sheetArt = sheetArtefact(issue);
  const pdfArt = extraPdfArtefact(issue, article);

  const xmlQuotes = useMemo(() => (
    (locator?.targets || [])
      .filter((t: any) => t.kind === "xml_text" && jumpable(t) && t.quote)
      .map((t: any) => ({ id: t.id, quote: t.quote as string }))
  ), [locator]);

  const cells = useMemo(() => xmlCells(locator?.targets), [locator]);

  /** The table a jumpable XML target names, if it names one. */
  const xmlTableNum = useMemo(() => {
    const t = (locator?.targets || []).find(
      (x: any) => x.kind === "xml_text" && jumpable(x) && x.table_num != null,
    );
    return t ? (t.table_num as number) : null;
  }, [locator]);

  const reason: UnanchoredReason = unanchoredReason(
    surface, issue, locator?.targets, xmlQuotes.length > 0 || cells.length > 0,
  );

  const pdfUrl = (surface === "pdf" && pdfArt?.found && pdfArt.relpath)
    ? mediaUrl(project, dir, pdfArt.relpath)
    : (surface === "pdf" && article?.pdf_relpath)
      ? mediaUrl(project, dir, article.pdf_relpath)
      : null;

  const hasMedia = !!(extras && (extras.video || extras.exhibit));
  const exhibitUrl = extras?.exhibit
    ? mediaUrl(project, dir, extras.exhibit) : null;
  const videoUrl = extras?.video
    ? mediaUrl(project, dir, extras.video) : null;

  const [zoom, setZoom] = useState(ZOOM_FIT);
  const [revealError, setRevealError] = useState<string | null>(null);
  const [revealing, setRevealing] = useState(false);
  useEffect(() => { setRevealError(null); }, [project, dir]);
  useEffect(() => {
    setZoom(parseStoredZoom(window.localStorage.getItem(ZOOM_KEY)));
  }, []);
  const applyZoom = useCallback((z: number) => {
    setZoom(z);
    window.localStorage.setItem(ZOOM_KEY, String(z));
  }, []);
  // Re-fit is a GESTURE, not a reaction to layout. Watching the pane's width
  // and re-rendering on it flashed on every paper (see PdfPane's `refitNonce`).
  // It also has to force a render on its own: clicking "fit" when the zoom is
  // already 1 changes no state, so without this the button would do nothing
  // after a resize -- the one moment it is wanted.
  const [refitNonce, setRefitNonce] = useState(0);
  const refit = useCallback(() => {
    applyZoom(ZOOM_FIT);
    setRefitNonce((i) => i + 1);
  }, [applyZoom]);

  const colRef = useRef<HTMLDivElement>(null);
  const exhibitPctRef = useRef(EXHIBIT_DEFAULT);
  const [exhibitPct, setExhibitPct] = useState(EXHIBIT_DEFAULT);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    const n = readExhibitPct();
    exhibitPctRef.current = n;
    setExhibitPct(n);
  }, []);

  const applyExhibit = useCallback((pct: number) => {
    const next = clampExhibit(pct);
    exhibitPctRef.current = next;
    setExhibitPct(next);
  }, []);

  const onGutterPointerDown = useCallback((e: PointerEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(true);
    e.currentTarget.setPointerCapture(e.pointerId);
  }, []);

  const onGutterPointerMove = useCallback((e: PointerEvent<HTMLDivElement>) => {
    if (e.buttons === 0 || !colRef.current) return;
    const rect = colRef.current.getBoundingClientRect();
    if (rect.height <= 0) return;
    applyExhibit(((e.clientY - rect.top) / rect.height) * 100);
  }, [applyExhibit]);

  const onGutterPointerUp = useCallback(() => {
    setDragging(false);
    window.localStorage.setItem(EXHIBIT_KEY, String(exhibitPctRef.current));
  }, []);

  const onGutterKeyDown = useCallback((e: ReactKeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowUp" || e.key === "ArrowDown") {
      e.preventDefault();
      e.stopPropagation();
      applyExhibit(exhibitPctRef.current + (e.key === "ArrowDown" ? 2 : -2));
      window.localStorage.setItem(EXHIBIT_KEY, String(exhibitPctRef.current));
    }
  }, [applyExhibit]);

  return (
    <div
      className={`source-col${dragging ? " dragging" : ""}`}
      ref={colRef}
    >
      {revealError && <p role="alert" style={{color: "var(--sev-highly)", margin: 10}}>{revealError}</p>}
      {warning && surface !== "sheet" && (
        <div className="banner" style={{ margin: 10 }}>
          {warning}{" "}
          {/* The download-link sentence belongs to "PDF not available, using
              XML"; beside "paper files unavailable" it read as though the
              paper had no PDF, when the folder was simply unregistered. */}
          {mode === "xml" && (doiUrl ? (
            <a href={doiUrl} target="_blank" rel="noreferrer">{doiUrl}</a>
          ) : (
            <span className="muted">no DOI on disk to build a download link from</span>
          ))}
        </div>
      )}
      {hasMedia && (
        <div
          className="exhibit-strip"
          style={pdfUrl || surface === "xml" || surface === "sheet"
            ? { flex: `0 0 ${exhibitPct}%` }
            : { flex: "1 1 auto" }}
        >
          {exhibitUrl && (
            <a
              href={exhibitUrl}
              target="_blank"
              rel="noreferrer"
              className="exhibit-open"
              title="Open full size in a new tab"
            >
              Open full size
            </a>
          )}
          {videoUrl && (
            <video
              src={videoUrl}
              controls
              className="exhibit-media"
            />
          )}
          {exhibitUrl && (
            <a
              href={exhibitUrl}
              target="_blank"
              rel="noreferrer"
              className="exhibit-link"
              title="Open full size in a new tab"
            >
              <img
                src={exhibitUrl}
                alt="Duplication exhibit"
                className="exhibit-media"
              />
            </a>
          )}
        </div>
      )}
      {hasMedia && (pdfUrl || surface === "xml" || surface === "sheet") && (
        <div
          className={`split-gutter split-gutter-row${dragging ? " dragging" : ""}`}
          role="separator"
          aria-orientation="horizontal"
          aria-label="Resize exhibit and source panes"
          aria-valuemin={EXHIBIT_MIN}
          aria-valuemax={EXHIBIT_MAX}
          aria-valuenow={Math.round(exhibitPct)}
          tabIndex={0}
          onPointerDown={onGutterPointerDown}
          onPointerMove={onGutterPointerMove}
          onPointerUp={onGutterPointerUp}
          onPointerCancel={onGutterPointerUp}
          onKeyDown={onGutterKeyDown}
        />
      )}
      <div style={{ flex: 1, minHeight: 0, position: "relative" }}>
        {surface === "pdf" && (
          <PdfZoomControls
            zoom={zoom}
            onZoomOut={() => applyZoom(zoomOut(zoom))}
            onZoomIn={() => applyZoom(zoomIn(zoom))}
            onFit={refit}
            style={{ right: canSwitch ? 108 : 12 }}
          >
            <button
              type="button"
              onClick={() => { window.location.href = `${pdfUrl}&download=1`; }}
              title="Download this PDF"
              aria-label="Download this PDF"
            >
              ⤓
            </button>
            <button
              type="button"
              disabled={revealing}
              onClick={async () => {
                const rel = (pdfArt?.found && pdfArt.relpath) || article?.pdf_relpath;
                setRevealing(true); setRevealError(null);
                try {
                  const response = await fetch("/api/reveal", {
                    method: "POST", headers: { "content-type": "application/json" },
                    body: JSON.stringify({ project, dir, f: rel || undefined }),
                  });
                  const result = await response.json();
                  if (!response.ok || result.error) throw new Error(result.error || response.statusText);
                } catch (error) { setRevealError(String(error)); }
                finally { setRevealing(false); }
              }}
              title="Show this paper's folder in the file browser"
              aria-label="Show this paper's folder in the file browser"
            >
              ⌂
            </button>
          </PdfZoomControls>
        )}
        {canSwitch && (
          <div className="source-view-toggle" role="group"
               aria-label="Document rendering">
            <button
              className={surface === "xml" ? "primary" : undefined}
              aria-pressed={surface === "xml"}
              title="Publisher XML — reflowing text, real table markup"
              onClick={() => onSurface("xml")}
            >
              XML
            </button>
            <button
              className={surface === "pdf" ? "primary" : undefined}
              aria-pressed={surface === "pdf"}
              title="The PDF as published — the document of record"
              onClick={() => onSurface("pdf")}
            >
              PDF
            </button>
          </div>
        )}
        {surface === "xml" && reason && (
          <div className="banner" style={{ margin: "10px 92px 10px 10px" }}>
            {reason.code === "image_finding" && (
              <>This finding is about a figure panel. The XML carries the
              article&rsquo;s text, not its images, so there is nothing to
              highlight here — the panel is in the PDF.</>
            )}
            {reason.code === "supplement" && (
              <>This quote comes from{" "}
              <span className="mono">{reason.file}</span>, not the article text,
              so it is not in the XML.</>
            )}
            {reason.code === "section_only" && (
              <>Located to <b>{reason.section}</b> only — the exact quote was
              not matched in the XML, so nothing is marked. Scrolled to the
              section.</>
            )}
            {reason.code === "pdf_only" && (
              <>This finding is anchored to the PDF only — we could not match
              its quote in the XML, so nothing is highlighted here.</>
            )}
            {reason.code === "unlocated" && (
              <>No location was found for this finding on any surface. We will
              not invent one.</>
            )}
            {(reason.code === "pdf_only" || reason.code === "image_finding") && canSwitch && (
              <>{" "}
                <button onClick={() => onSurface("pdf")}>Show in PDF</button>
              </>
            )}
          </div>
        )}
        {surface === "sheet" && sheetArt && sheetArt.found && (
          <SpreadsheetPane
            key={`${sheetArt.relpath || sheetArt.basename}:${sheetArt.sheet || ""}`}
            project={project}
            slug={slug}
            dir={dir}
            artefact={sheetArt}
            label={issue ? `F${issue.priority}` : ""}
          />
        )}
        {surface === "sheet" && sheetArt && !sheetArt.found && (
          <p className="muted" style={{ padding: 16 }}>
            This finding names <span className="mono">{sheetArt.basename}</span>
            {" "}but that file is not in this paper directory
            {sheetArt.missing_reason ? ` (${sheetArt.missing_reason})` : ""}.
          </p>
        )}
        {surface === "pdf" && pdfUrl && (
          <PdfPane
            url={pdfUrl}
            locator={locator}
            label={issue ? `F${issue.priority}` : ""}
            severity={issue?.severity}
            focusTargetId={focusTargetId}
            zoom={zoom}
            refitNonce={refitNonce}
          />
        )}
        {surface === "xml" && article.html && (
          <HtmlArticlePane
            html={article.html}
            className="xml-article"
            sectionIndex={locator?.section_index}
            tableNum={xmlTableNum}
            quotes={xmlQuotes}
            cells={cells}
            focusTargetId={focusTargetId}
            severity={issue?.severity}
          />
        )}
        {surface === "none" && mode === "html" && article.html && (
          <HtmlArticlePane html={article.html} className="xml-article" />
        )}
        {surface === "none" && mode === "text" && article.html && (
          <HtmlArticlePane html={article.html} />
        )}
        {surface === "none" && !warning && (
          <p className="muted" style={{ padding: 16 }}>
            Nothing to show for this paper.
          </p>
        )}
      </div>
    </div>
  );
}
