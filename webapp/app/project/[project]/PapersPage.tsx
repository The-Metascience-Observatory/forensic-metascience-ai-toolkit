"use client";
import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { ProjectTable } from "./ProjectTable";
import type { Paper } from "@/lib/types/catalog";
import type { SortState } from "@/lib/projectTableSort";

/** Rows per request (the service caps a page at 100). */
export const PAGE = 50;
/** Infinite scroll stops here; past it, search or sort to narrow. */
export const MAX_ROWS = 1000;

type PapersReply = { papers: Paper[]; pagination: { total: number } };

/** The project's papers: the first 50 load at once and more load in 50s as
 *  the reader nears the bottom, up to 1,000. The 30-second refresh (and
 *  focus) re-reads every loaded row in one go, so rows never mix two
 *  revisions of the list. A new search or sort starts again from the top. */
export function PapersPage({ project }: { project: string }) {
  const [papers, setPapers] = useState<Paper[]>([]),
    [total, setTotal] = useState(0),
    [q, setQ] = useState(""),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(false);
  const [sort, setSort] = useState<SortState | null>({ key: "findings", dir: "desc" });
  const rows = useRef<Paper[]>([]);
  rows.current = papers;
  // A generation per (project, search, sort): replies from an older one are
  // dropped, and only a request of the CURRENT generation blocks another.
  const generation = useRef(0);
  const busy = useRef(0);
  const sentinel = useRef<HTMLDivElement>(null);

  const fetchPage = useCallback(
    async (offset: number, signal?: AbortSignal) => {
      const params = new URLSearchParams({
        method: "papers", project, offset: String(offset), limit: String(PAGE), q,
        sort: sort?.key || "findings", direction: sort?.dir || "desc",
      });
      const r = await fetch(`/api/workbench?${params}`, { signal });
      const b = await r.json();
      if (!r.ok) throw new Error(b.error);
      return b as PapersReply;
    },
    [project, q, sort],
  );

  useEffect(() => {
    const controller = new AbortController();
    const mine = ++generation.current;
    setPapers([]); setTotal(0); setError("");
    const refresh = async () => {
      if (document.hidden || busy.current === mine) return;
      busy.current = mine;
      try {
        const n = Math.max(PAGE, rows.current.length);
        const offsets = Array.from({ length: Math.ceil(n / PAGE) }, (_, i) => i * PAGE);
        const pages = await Promise.all(offsets.map((o) => fetchPage(o, controller.signal)));
        if (generation.current !== mine) return;
        setPapers(pages.flatMap((p) => p.papers).slice(0, MAX_ROWS));
        setTotal(pages[pages.length - 1].pagination.total);
        setError("");
      } catch (e) {
        if ((e as Error).name !== "AbortError") setError(String(e));
      } finally {
        if (busy.current === mine) busy.current = 0;
      }
    };
    refresh();
    const timer = setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    return () => {
      controller.abort();
      clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, [fetchPage]);

  const limit = Math.min(total, MAX_ROWS);
  const hasMore = papers.length > 0 && papers.length < limit;

  const loadMore = useCallback(async () => {
    const mine = generation.current;
    const offset = rows.current.length;
    if (busy.current === mine || offset === 0 || offset >= limit) return;
    busy.current = mine;
    setLoading(true);
    try {
      const page = await fetchPage(offset);
      if (generation.current !== mine) return;
      // Append only onto the rows this page continues; a refresh that landed
      // in between already replaced them.
      setPapers((cur) => (cur.length === offset ? [...cur, ...page.papers].slice(0, MAX_ROWS) : cur));
      setTotal(page.pagination.total);
      setError("");
    } catch (e) {
      if (generation.current === mine) setError(String(e));
    } finally {
      if (busy.current === mine) busy.current = 0;
      setLoading(false);
    }
  }, [fetchPage, limit]);

  // Re-observed after every batch: a batch too short to push the sentinel
  // out of view must still trigger the next one.
  useEffect(() => {
    const el = sentinel.current;
    if (!el || !hasMore || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) loadMore();
    }, { rootMargin: "800px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [hasMore, loadMore, papers.length]);

  return (
    <div className="page">
      <Link href="/">← projects</Link>
      <h1>{project}</h1>
      <p>
        <a href={`/project/${encodeURIComponent(project)}/images`}>Image findings</a>
        {" · "}
        <a href={`/project/${encodeURIComponent(project)}/copypaste`}>Copy/paste findings</a>
        {" · "}
        <a href={`/project/${encodeURIComponent(project)}/detector/rng_track`}>RNG findings</a>
        {" · "}
        <a href={`/project/${encodeURIComponent(project)}/stats`}>Statistics</a>
      </p>
      <label>
        Search{" "}
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="title, DOI, or folder (10.1007--s004010050748)"
          aria-label="Search papers by title, DOI, or folder name"
          style={{ minWidth: 280 }}
        />
      </label>{" "}
      <span data-papers-count>{papers.length} of {total}</span>
      {error && <p role="alert">{error}</p>}
      <ProjectTable project={project} papers={papers} onSortChange={setSort} />
      <div ref={sentinel} style={{ padding: "12px 0" }} className="muted">
        {hasMore && (
          <button type="button" disabled={loading} onClick={loadMore}>
            {loading ? "Loading…" : `Load ${Math.min(PAGE, limit - papers.length)} more`}
          </button>
        )}
        {!hasMore && total > MAX_ROWS && papers.length >= MAX_ROWS && (
          <span data-papers-cap>
            Showing the first {MAX_ROWS.toLocaleString()} of {total.toLocaleString()} papers. Search or sort to
            find others.
          </span>
        )}
      </div>
    </div>
  );
}
