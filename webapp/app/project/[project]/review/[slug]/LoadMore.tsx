"use client";

import { useEffect, useRef } from "react";

/** The end of the findings list: asks for the next 100 when it comes within
 *  a screen of view (infinite scroll), with a button as a fallback. Renders
 *  nothing once the list is complete. */
export function LoadMore({ hasMore, loading, onMore }: {
  hasMore: boolean; loading: boolean; onMore: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el || !hasMore || loading || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver((entries) => {
      if (entries.some((e) => e.isIntersecting)) onMore();
    }, { rootMargin: "600px 0px" });
    io.observe(el);
    return () => io.disconnect();
  }, [hasMore, loading, onMore]);
  if (!hasMore) return null;
  return (
    <div ref={ref} data-findings-more className="muted" style={{ padding: "8px 0", fontSize: 12 }}>
      <button type="button" disabled={loading} onClick={onMore}>
        {loading ? "Loading…" : "Load more findings"}
      </button>
    </div>
  );
}
