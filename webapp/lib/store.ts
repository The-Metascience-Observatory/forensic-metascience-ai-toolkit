import "server-only";

import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";

import { pyJson } from "./python";
import { workbench } from "./workbench";
import { badProject, badRel, contained, posixRel, sameRel } from "./paths";
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

function realOrSelf(p: string): string {
  try { return fs.realpathSync(p); } catch { return path.resolve(p); }
}

/**
 * Resolve a file inside a project. THE SECURITY BOUNDARY.
 *
 * `dir` is corpus-relative (`done/10.x`, `grok_run/10.x`, or `10.x`).
 * `rel` is paper-relative. Backslashes are accepted and folded to `/`.
 * Symlinks that escape the papers root are refused.
 */
export async function resolveInProject(
  project: string, dir: string, rel: string
): Promise<string> {
  const settings = loadSettings();
  const papersRoot = realOrSelf(settings.papers_root);
  if (badProject(project)) {
    throw new Error("bad project");
  }
  const paperDir = posixRel(dir);
  const fileRel = posixRel(rel);
  if (badRel(fileRel)) {
    throw new Error("path must be relative to the paper directory");
  }
  if (badRel(paperDir)) {
    throw new Error("bad paper directory");
  }
  const projectRoot = path.join(papersRoot, project);
  const realProject = await fsp.realpath(projectRoot);
  if (realProject !== papersRoot && !contained(papersRoot, realProject)) {
    throw new Error("project escapes the papers root");
  }
  const target = path.resolve(realProject, paperDir, fileRel);
  let realTarget: string;
  try {
    realTarget = await fsp.realpath(target);
  } catch {
    throw new Error("no such file");
  }
  if (!contained(realProject, realTarget)) {
    throw new Error("path escapes the project");
  }
  const st = await fsp.stat(realTarget);
  if (!st.isFile()) throw new Error("not a file");
  return realTarget;
}

export async function paperAbsDir(project: string, dir: string): Promise<string> {
  const settings = loadSettings();
  const papersRoot = realOrSelf(settings.papers_root);
  if (badProject(project)) {
    throw new Error("bad project");
  }
  const paperDir = posixRel(dir);
  if (badRel(paperDir)) {
    throw new Error("bad paper directory");
  }
  const projectRoot = await fsp.realpath(path.join(papersRoot, project));
  if (projectRoot !== papersRoot && !contained(papersRoot, projectRoot)) {
    throw new Error("project escapes the papers root");
  }
  const abs = path.resolve(projectRoot, paperDir);
  const real = await fsp.realpath(abs);
  if (!contained(projectRoot, real)) {
    throw new Error("paper escapes the project");
  }
  return real;
}
