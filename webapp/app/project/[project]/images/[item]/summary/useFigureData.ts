/** The data a summary figure fetches beyond its media: each paper's XML
 *  figure list (`/api/workbench`) and full reference (`/api/images/reference`).
 *  Plain async functions, awaited by `generate` and `compose`. */
import type { Item } from "@/app/images/lib";
import type { XmlFigure } from "@/lib/xmlFigures";
import { referenceRuns, type ReferenceMeta, type Run } from "@/lib/citation";

/** Each paper's XML figure list, from the same `source` read the XML paper
 *  pane makes: it names the native image file each figure was rendered from. */
export async function fetchFigures(project: string, item: Item, dirs: string[]): Promise<Record<string, XmlFigure[]>> {
  return Object.fromEntries(await Promise.all(dirs.map(async dir => {
    const query = new URLSearchParams({ method: "source", project, dir, run: item.run_id, component: "image_forensics" });
    const response = await fetch(`/api/workbench?${query}`);
    const source = await response.json().catch(() => ({}));
    if (!response.ok || source.error) throw new Error(`The figure list for ${dir} could not be loaded: ${source.error || response.statusText}`);
    return [dir, (source.article?.figures || []) as XmlFigure[]];
  })));
}

/** The papers' full references, fetched (and cached beside each paper) by
 *  the workbench. A paper the APIs cannot describe falls back to what the
 *  item already carries; it is never labelled by its DOI. */
export async function fetchReferences(project: string, item: Item, dirs: string[]): Promise<Record<string, Run[]>> {
  const fallback = (dir: string) => {
    const paper = (item.papers || [item.paper]).find(p => p?.dir === dir) as ReferenceMeta | undefined;
    return referenceRuns(paper);
  };
  let fetched: Record<string, { metadata?: ReferenceMeta }> = {};
  try {
    const response = await fetch("/api/images/reference", { method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ project, dirs }) });
    if (response.ok) fetched = (await response.json()).references || {};
  } catch { /* fall back below */ }
  return Object.fromEntries(dirs.map(d => {
    const runs = referenceRuns(fetched[d]?.metadata);
    return [d, runs.length ? runs : fallback(d)];
  }));
}
