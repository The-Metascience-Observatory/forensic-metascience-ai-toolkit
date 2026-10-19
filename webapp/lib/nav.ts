import { sameRel } from "./rel.ts";

export type NavRef = { slug: string; dir: string };

export type PaperNav = {
  prev: NavRef | null;
  next: NavRef | null;
};

/** Image-duplicate groups or a numeric/editorial agent report with findings. */
export function paperHasFindings(p: {
  n_findings?: number | null;
  n_image_findings?: number | null;
}): boolean {
  return (p.n_findings || 0) > 0 || (p.n_image_findings || 0) > 0;
}

function asNavRef(p: { paper_id: string; dir: string }): NavRef {
  return { slug: p.paper_id, dir: p.dir };
}

/** Next/prev paper that has findings, in corpus order. Skips empties. */
export function findingsNeighbors(
  papers: { paper_id: string; dir: string;
            n_findings?: number | null;
            n_image_findings?: number | null }[],
  slug: string,
  dir?: string | null,
): PaperNav {
  if (!papers.length) return { prev: null, next: null };
  let i = dir ? papers.findIndex((p) => sameRel(p.dir, dir)) : -1;
  if (i < 0) i = papers.findIndex((p) => p.paper_id === slug);
  if (i < 0) return { prev: null, next: null };
  let prev: NavRef | null = null;
  for (let j = i - 1; j >= 0; j--) {
    if (paperHasFindings(papers[j])) { prev = asNavRef(papers[j]); break; }
  }
  let next: NavRef | null = null;
  for (let j = i + 1; j < papers.length; j++) {
    if (paperHasFindings(papers[j])) { next = asNavRef(papers[j]); break; }
  }
  return { prev, next };
}

export function lastFindingsIn(
  papers: { paper_id: string; dir: string;
            n_findings?: number | null;
            n_image_findings?: number | null }[],
): NavRef | null {
  for (let i = papers.length - 1; i >= 0; i--) {
    if (paperHasFindings(papers[i])) return asNavRef(papers[i]);
  }
  return null;
}

export function reviewHref(project: string, slug: string, dir?: string | null): string {
  const base = `/project/${encodeURIComponent(project)}/review/${encodeURIComponent(slug)}`;
  return dir ? `${base}?dir=${encodeURIComponent(dir)}` : base;
}

export function caughtUpHref(project: string): string {
  return `/project/${encodeURIComponent(project)}/caught-up`;
}
