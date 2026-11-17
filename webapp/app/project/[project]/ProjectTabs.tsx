"use client";
import Link from "next/link";
import { useEffect, useState } from "react";

/** Non-image findings (the papers table) | Image findings. The image tab is
 *  greyed out and not a link when the project has no image results: the
 *  feed's total over every verdict is 0, or the service has none for it.
 *  The project page opens on Image findings when those are all it has; the
 *  Non-image tab links with `?view=findings` so choosing it always sticks. */
export function ProjectTabs({ project, active }: { project: string; active: "findings" | "images" }) {
  const [hasImages, setHasImages] = useState<boolean | null>(active === "images" ? true : null);
  useEffect(() => {
    if (active === "images") return;
    const controller = new AbortController();
    const params = new URLSearchParams({ project, verdict: "all", limit: "1", offset: "0", facets: "none" });
    fetch(`/api/images?${params}`, { signal: controller.signal })
      .then(async (r) => {
        const b = await r.json().catch(() => ({}));
        setHasImages(r.ok && (b?.feed?.pagination?.total ?? 0) > 0);
      })
      .catch((e) => { if ((e as Error).name !== "AbortError") setHasImages(false); });
    return () => controller.abort();
  }, [project, active]);

  const base = `/project/${encodeURIComponent(project)}`;
  const tab = (on: boolean): React.CSSProperties => ({
    padding: "6px 14px", borderBottom: on ? "2px solid var(--accent)" : "2px solid transparent",
    fontWeight: on ? 600 : 400, color: on ? "var(--fg)" : undefined, marginBottom: -1,
  });
  const imagesOff = hasImages !== true;
  return (
    <nav aria-label="Project views" data-project-tabs
         style={{ display: "flex", alignItems: "flex-end", borderBottom: "1px solid var(--line)", margin: "8px 0 12px" }}>
      <Link href={`${base}?view=findings`} aria-current={active === "findings" ? "page" : undefined} style={tab(active === "findings")}>
        Non-image findings
      </Link>
      {imagesOff ? (
        <span aria-disabled="true" data-tab-disabled
              title={hasImages === null ? "Checking for image findings…" : "This project has no image findings"}
              style={{ ...tab(false), color: "var(--muted)", opacity: 0.5, cursor: "not-allowed" }}>
          Image findings
        </span>
      ) : (
        <Link href={`${base}/images`} aria-current={active === "images" ? "page" : undefined} style={tab(active === "images")}>
          Image findings
        </Link>
      )}
      <span style={{ flex: 1 }} />
      <Link href={`${base}/stats`} style={{ padding: "6px 0", fontSize: 13 }}>Statistics</Link>
    </nav>
  );
}
