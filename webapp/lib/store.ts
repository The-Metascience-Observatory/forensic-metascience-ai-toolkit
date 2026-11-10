import "server-only";

import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";

import { pyJson } from "./python";
import { workbench } from "./workbench";
import { badProject, badRel, posixRel, sameRel } from "./paths";
import { indexPath, loadSettings } from "./settings";
import type { Corpus, Index, Paper, ProjectRow } from "./types/catalog";

export type { Corpus, Index, Paper, ProjectRow };

let _cache: { path: string; mtimeMs: number; size: number; index: Index } | null = null;

export class IndexMissing extends Error {}

export function loadIndex(): Index {
  const p = indexPath();
  let st: fs.Stats;
  try {
    st = fs.statSync(p);
  } catch {
    throw new IndexMissing(
      `No index at ${p}. Scan from the workbench, or:\n\n` +
      `    metascience webapp-index --projects-root <papers-root> -o webapp/data/index.json`
    );
  }
  if (_cache && _cache.path === p && _cache.mtimeMs === st.mtimeMs && _cache.size === st.size) return _cache.index;
  const index = JSON.parse(fs.readFileSync(p, "utf-8")) as Index;
  if (!index.projects) {
    throw new Error(
      "This index is the old per-corpus shape. Rescan with --projects-root."
    );
  }
  _cache = { path: p, mtimeMs: st.mtimeMs, size: st.size, index };
  return index;
}

export function findProject(name: string): ProjectRow | null {
  return loadIndex().projects.find((p) => p.name === name) ?? null;
}

export function findPaper(
  project: string, slug: string, dir?: string | null,
): Paper | null {
  const proj = findProject(project);
  if (!proj) return null;
  const cands = proj.corpus.papers.filter((p) => p.paper_id === slug);
  if (!cands.length) return null;
  if (dir) {
    const hit = cands.find((p) => sameRel(p.dir, dir));
    if (hit) return hit;
  }
  // A DOI slug can name two directories (top-level fetch vs done/). Prefer
  // the copy that actually has a review — that is the one with the xlsx.
  const withRun = cands.filter((p) => (p.n_runs || 0) > 0);
  const pool = withRun.length ? withRun : cands;
  return [...pool].sort((a, b) => (b.n_findings || 0) - (a.n_findings || 0))[0];
}

async function performScan(): Promise<Index> {
  const settings = loadSettings();
  const out = indexPath();
  fs.mkdirSync(path.dirname(out), { recursive: true });
  await pyJson([
    "webapp-index",
    "--projects-root", settings.papers_root,
    "-o", out,
    "--stdout",
  ], { dedupe: true, timeoutMs: 600_000 });
  await workbench("import_index", { path: out });
  await workbench("import_index", { path: out, component: "image_forensics" });
  _cache = null;
  return loadIndex();
}

let scanning: Promise<Index> | null = null;
export function scanNow(): Promise<Index> {
  if (!scanning) scanning = performScan().finally(() => { scanning = null; });
  return scanning;
}


// Media and reveal paths are resolved and contained by the Python service
// (`artifact` / `reveal_target` in workbench/service.py): realpath, inside
// the registered root, hash-checked. The TypeScript `resolveInProject` that
// once did this had no callers left and was deleted (2026-11-09), so nothing
// here reads as a boundary that is not one. `paperAbsDir` below asks the
// service for a paper folder, for the few routes that read one directly.

export async function paperAbsDir(project: string, dir: string): Promise<string> {
  if (badProject(project)) {
    throw new Error("bad project");
  }
  const paperDir = posixRel(dir);
  if (badRel(paperDir)) {
    throw new Error("bad paper directory");
  }
  // The catalog resolves the folder from the project's registered roots
  // (`catalog.paper_path`: explicit mapping, else <root>/<dir>, contained,
  // no symlinks) -- the same answer the review pages get -- rather than
  // assuming the project is a folder under the papers root.
  const target = await workbench<{ directory: string }>("reveal_target", { project, dir: paperDir });
  return fsp.realpath(target.directory);
}

/** The project's folders on this machine (its registered catalog roots). */
export async function projectFolders(project: string): Promise<string[]> {
  if (badProject(project)) throw new Error("bad project");
  const { roots } = await workbench<{ roots: { project: string; path: string; available?: boolean }[] }>("roots");
  return (roots || []).filter((r) => r.project === project && r.available !== false).map((r) => r.path);
}

/** The folder holding the project's corpus-level files (`corpus_stats.json`):
 *  the first registered folder that has one, else the first folder. */
export async function projectRoot(project: string): Promise<string | null> {
  const folders = await projectFolders(project);
  for (const f of folders) if (fs.existsSync(path.join(f, "corpus_stats.json"))) return f;
  return folders[0] ?? null;
}
