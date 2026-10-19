"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { findQuoteSpans } from "@/lib/haystack";
import { SEV_FILL } from "@/lib/severity";
import type { XmlImageBox } from "@/lib/imageXmlBoxes";
import { mountXmlImageOverlays } from "@/lib/xmlImageOverlays";
import { FindBar, useFindShortcut } from "./FindBar";

function clearMarks(root: HTMLElement, cls: string) {
  root.querySelectorAll(`mark.${cls}`).forEach((m) => {
    const text = document.createTextNode(m.textContent || "");
    m.replaceWith(text);
  });
  root.normalize();
}

/** Elements whose text does not run on into the next one's. */
const BLOCKISH = "td,th,tr,li,p,div,caption,figcaption,blockquote,pre,dd,dt,"
  + "h1,h2,h3,h4,h5,h6,section";

function highlight(
  root: HTMLElement, query: string, cls: string, tid?: string,
): HTMLElement[] {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const nodes: Text[] = [];
  // The haystack is the concatenation of these pieces, so two cells of a table
  // row would run together as `GroupF (1.29) = 37.3` while the quote folds to
  // `group f (1.29) = 37.3` -- and a table-row quote could never match. Feed a
  // one-space piece in at every block boundary and drop any span that lands on
  // one. The same bug ran two adjacent paragraphs together.
  const pieces: { data: string }[] = [];
  const pieceNode: number[] = [];
  let prevBlock: Element | null = null;
  let first = true;
  while (walker.nextNode()) {
    const n = walker.currentNode as Text;
    if (!n.data) continue;
    if (n.parentElement?.closest("mark, svg")) continue;
    const block = n.parentElement?.closest(BLOCKISH) ?? null;
    if (!first && block !== prevBlock) {
      pieces.push({ data: " " });
      pieceNode.push(-1);
    }
    pieces.push({ data: n.data });
    pieceNode.push(nodes.length);
    nodes.push(n);
    prevBlock = block;
    first = false;
  }
  const matches = findQuoteSpans(pieces, query);
  const marks: HTMLElement[] = [];
  // Wrap back to front: surroundContents splits the text node, which keeps
  // every earlier (node, offset) span valid against the original nodes.
  for (let m = matches.length - 1; m >= 0; m--) {
    for (let s = matches[m].length - 1; s >= 0; s--) {
      const span = matches[m][s];
      const ni = pieceNode[span.node];
      if (ni < 0) continue;              // the synthetic block separator
      const range = document.createRange();
      range.setStart(nodes[ni], span.start);
      range.setEnd(nodes[ni], span.end);
      const mark = document.createElement("mark");
      mark.className = cls;
      if (tid) mark.dataset.targetId = tid;
      try {
        range.surroundContents(mark);
      } catch {
        continue;
      }
      marks.push(mark);
    }
  }
  return marks.reverse(); // document order, as before
}

/** Unmark every table cell a previous finding marked. */
function clearCells(root: HTMLElement) {
  root.querySelectorAll<HTMLElement>("td.xml-cell-hit").forEach((td) => {
    td.classList.remove("xml-cell-hit");
    delete td.dataset.targetId;
    td.style.background = "";
    td.style.outline = "";
  });
}

export function HtmlArticlePane({ html, className, sectionIndex, tableNum,
  quotes, cells, focusTargetId, severity, figureAnchor, figureImage, jumpNonce, imageBoxes }: {
  html: string;
  figureAnchor?: string;
  /** Within that figure, the rendition (media path) to land on, when it holds several. */
  figureImage?: string;
  jumpNonce?: string;
  imageBoxes?: XmlImageBox[];
  className?: string;
  sectionIndex?: number | null;
  /** A table-scoped anchor: `xml_html` gives every grid an `id="table-{n}"`. */
  tableNum?: number | null;
  quotes?: { id: string; quote: string }[];
  /** Table cells to mark, addressed as `xml_html` prints them:
   *  `figure[data-table-num] td[data-row][data-col]`. A number, not a passage. */
  cells?: { id: string; tableNum: number; row: number; col: number }[];
  focusTargetId?: string | null;
  severity?: string;
}) {
  const article = useRef<HTMLDivElement>(null);
  // Next's renderer assigns innerHTML again when this prop object changes,
  // even if the text is unchanged. Preserve the DOM augmented by figure
  // overlays and search marks through navigation and parent rerenders.
  const articleHtml = useMemo(() => ({ __html: html }), [html]);
  const findInput = useRef<HTMLInputElement>(null);
  const marksRef = useRef<HTMLElement[]>([]);
  const atRef = useRef(0);
  const findOpenRef = useRef(false);
  const queryRef = useRef("");
  const [findOpen, setFindOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [matchAt, setMatchAt] = useState(0);
  const [matchN, setMatchN] = useState(0);

  useEffect(() => {
    if (article.current && imageBoxes?.length) return mountXmlImageOverlays(article.current, imageBoxes);
  }, [html, imageBoxes]);

  const paintCurrent = useCallback(() => {
    const marks = marksRef.current;
    marks.forEach((m, i) => {
      m.classList.toggle("html-hit-current", i === atRef.current);
    });
    marks[atRef.current]?.scrollIntoView({ block: "center", inline: "nearest" });
  }, []);

  const runSearch = useCallback((q: string) => {
    const el = article.current;
    if (!el) return;
    clearMarks(el, "html-hit");
    const trimmed = q.trim();
    const marks = trimmed ? highlight(el, trimmed, "html-hit") : [];
    marksRef.current = marks;
    atRef.current = 0;
    setMatchN(marks.length);
    setMatchAt(0);
    paintCurrent();
  }, [paintCurrent]);

  const stepMatch = useCallback((delta: number) => {
    const marks = marksRef.current;
    if (!marks.length) return;
    const next = (atRef.current + delta + marks.length) % marks.length;
    atRef.current = next;
    setMatchAt(next);
    paintCurrent();
  }, [paintCurrent]);

  const openFind = useCallback(() => {
    findOpenRef.current = true;
    setFindOpen(true);
    queueMicrotask(() => {
      findInput.current?.focus();
      findInput.current?.select();
    });
  }, []);

  const closeFind = useCallback(() => {
    findOpenRef.current = false;
    setFindOpen(false);
    queryRef.current = "";
    setQuery("");
    marksRef.current = [];
    atRef.current = 0;
    setMatchN(0);
    setMatchAt(0);
    if (article.current) clearMarks(article.current, "html-hit");
  }, []);

  const isOpen = useCallback(() => findOpenRef.current, []);
  useFindShortcut(openFind, closeFind, stepMatch, isOpen);

  useEffect(() => {
    marksRef.current = [];
    const el = article.current;
    if (!el) return;
    clearMarks(el, "xml-hit");
    clearCells(el);
    const fill = SEV_FILL[severity || ""] || "rgba(224,176,74,0.35)";
    let focused: HTMLElement | null = null;
    let firstCell: HTMLElement | null = null;
    for (const c of cells || []) {
      const td = el.querySelector<HTMLElement>(
        `figure[data-table-num="${c.tableNum}"] td[data-row="${c.row}"][data-col="${c.col}"]`);
      if (!td) continue;
      td.classList.add("xml-cell-hit");
      td.dataset.targetId = c.id;
      td.style.background = fill;
      td.style.outline = c.id === focusTargetId
        ? "3px solid rgba(31,111,191,1)" : "2px solid rgba(61,143,209,0.9)";
      if (c.id === focusTargetId && !focused) focused = td;
      if (!firstCell) firstCell = td;
    }
    for (const q of quotes || []) {
      const needle = (q.quote || "").trim();
      if (needle.length < 8) continue;
      let hits = highlight(el, needle, "xml-hit", q.id);
      if (!hits.length) {
        const probe = needle.split(/\s+/).slice(0, 8).join(" ");
        if (probe && probe !== needle) hits = highlight(el, probe, "xml-hit", q.id);
      }
      for (const m of hits) {
        m.style.background = fill;
        m.style.outline = q.id === focusTargetId
          ? "3px solid rgba(31,111,191,1)" : "2px solid rgba(61,143,209,0.9)";
        if (q.id === focusTargetId && !focused) focused = m;
      }
    }
    if (findOpenRef.current && queryRef.current.trim()) {
      runSearch(queryRef.current);
      return;
    }
    if (focused) {
      focused.scrollIntoView({ block: "center" });
      return;
    }
    const firstHit = (el.querySelector("mark.xml-hit") as HTMLElement | null) || firstCell;
    if (firstHit) {
      firstHit.scrollIntoView({ block: "center" });
      return;
    }
    // A table anchor names its grid, so land on the grid even when no mark
    // could be drawn. Its section is often called "Floats" and is useless.
    if (tableNum != null) {
      const grid = el.querySelector(`#table-${tableNum}`) as HTMLElement | null;
      if (grid) {
        grid.scrollIntoView({ block: "start" });
        return;
      }
    }
    if (sectionIndex == null) return;
    el.querySelector(`#sec-${sectionIndex}`)?.scrollIntoView({ block: "start" });
  }, [html, sectionIndex, tableNum, quotes, cells, focusTargetId, severity, runSearch]);

  useEffect(() => {
    const el = article.current;
    if (!el) return;
    const failed = (event: Event) => {
      const image = event.target;
      if (!(image instanceof HTMLImageElement)) return;
      const message = document.createElement('p');
      message.className = 'muted';
      message.textContent = `${image.alt || 'Figure'}: image unavailable or could not be decoded.`;
      image.replaceWith(message);
    };
    el.addEventListener('error', failed, true);
    return () => el.removeEventListener('error', failed, true);
  }, [html]);

  useEffect(() => {
    const el = article.current;
    if (!el || figureAnchor === undefined) return;
    const jump = () => {
      if (!figureAnchor) { el.scrollTop = 0; return; }
      const figure = [...el.querySelectorAll<HTMLElement>('figure[id]')].find(f => f.id === figureAnchor);
      // A figure printing two renditions (PMC beside the publisher's) stacks
      // them; land on the one this panel was measured on, not the first.
      const image = figureImage ? [...(figure?.querySelectorAll<HTMLImageElement>('img') || [])]
        .find(i => new URL(i.src, document.baseURI).searchParams.get('f') === figureImage) : undefined;
      const target = image && image !== figure?.querySelector('img') ? image : figure;
      if (target) el.scrollTop += target.getBoundingClientRect().top - el.getBoundingClientRect().top;
    };
    jump();
    // Lazy images above the selected figure can change its offset. Correct the
    // initial jump until the reader starts navigating for themselves.
    let active = true;
    const stop = () => { active = false; };
    const loaded = () => { if (active) jump(); };
    el.addEventListener('load', loaded, true);
    el.addEventListener('wheel', stop, { passive: true });
    el.addEventListener('touchstart', stop, { passive: true });
    el.addEventListener('pointerdown', stop);
    window.addEventListener('keydown', stop);
    return () => {
      el.removeEventListener('load', loaded, true);
      el.removeEventListener('wheel', stop);
      el.removeEventListener('touchstart', stop);
      el.removeEventListener('pointerdown', stop);
      window.removeEventListener('keydown', stop);
    };
  }, [html, figureAnchor, figureImage, jumpNonce]);

  return (
    <div className="pdf-pane">
      {findOpen && (
        <FindBar
          query={query}
          matchAt={matchAt}
          matchN={matchN}
          placeholder="Find in article"
          inputRef={findInput}
          onQuery={(q) => { queryRef.current = q; setQuery(q); runSearch(q); }}
          onPrev={() => stepMatch(-1)}
          onNext={() => stepMatch(1)}
          onClose={closeFind}
        />
      )}
      <div
        ref={article}
        className={className}
        style={{ overflow: "auto", height: "100%", flex: 1, minHeight: 0 }}
        dangerouslySetInnerHTML={articleHtml}
      />
    </div>
  );
}
