"use client";

import { useEffect, useState } from "react";
import type { Item } from "@/app/images/lib";

type Exported = { doi: string; id: string };

// One read per page load: the list changes only when someone adds a finding.
let cached: Promise<Exported[]> | null = null;
function loadExported(): Promise<Exported[]> {
  cached ??= fetch("/api/images/website")
    .then(r => (r.ok ? r.json() : { exported: [] }))
    .then(b => (Array.isArray(b?.exported) ? b.exported as Exported[] : []))
    .catch(() => { cached = null; return []; });
  return cached;
}
/** Test hook: forget the cached list. */
export function resetExportedCache() { cached = null; }

/** Each paper of the finding with its DOI: the recorded one, else the paper
 *  folder name, which is the DOI with the slash written `--`. */
export function itemDois(item: Item): string[] {
  const papers = item.papers || [item.paper];
  const dirs = [...new Set(item.panels.map(p => p.paper_dir).filter(Boolean))];
  if (!dirs.length && item.paper?.dir) dirs.push(item.paper.dir);
  return dirs.flatMap(dir => {
    const paper = papers.find(p => p?.dir === dir);
    const doi = paper?.doi || (dir.includes("--") ? dir.replace("--", "/") : "");
    return doi ? [doi.toLowerCase()] : [];
  });
}

/** "EXPORTED" in the item's top bar when a paper of this finding is already
 *  on the website's image-findings page (matched by DOI, the key the
 *  website's findings.json is unique on). */
export function ExportedBadge({ item }: { item: Item }) {
  const [exported, setExported] = useState<Exported[]>([]);
  useEffect(() => { let live = true; loadExported().then(e => { if (live) setExported(e); }); return () => { live = false; }; }, []);
  const dois = itemDois(item);
  const hits = exported.filter(e => dois.includes(e.doi));
  if (!hits.length) return null;
  return (
    <span data-exported-badge title={`On the website's image-findings page as ${hits.map(h => h.id).join(", ")}`}
          style={{ background: "#1a7f37", color: "#fff", fontWeight: 700, fontSize: 11, letterSpacing: 0.5,
                   padding: "2px 8px", borderRadius: 10, flexShrink: 0 }}>
      EXPORTED
    </span>
  );
}
