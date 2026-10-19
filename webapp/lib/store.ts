import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";

import { pyJson } from "./python";
import { workbench } from "./workbench";
import { badProject, badRel, contained, posixRel, sameRel } from "./paths";
import { indexPath, loadSettings } from "./settings";

export interface ProjectRow {
  name: string;
  root: string;
  n_papers: number;
  n_pdf: number;
  n_xml: number;
  n_agent_run: number;
  n_image_run: number;
  n_image_discarded?: number;
  n_image_refused?: number;
  n_text_run: number;
  n_human_reviewed: number;
  n_viewed?: number;
  n_viewed_unknown?: number;
  n_in_progress: number;
  n_not_fetched: number;
  n_pubpeer?: number;
  n_pubpeer_image?: number;
  n_submitted_pubpeer?: number;
  corpus: Corpus;
}

export interface Index {
  schema_version: string;
  papers_root: string;
  projects: ProjectRow[];
  n_projects: number;
  n_papers: number;
  errors?: { path: string; error: string }[];
}

export interface Corpus {
  schema_version: string;
  root: string;
  papers: Paper[];
  errors: { path: string; error: string }[];
  totals: Record<string, unknown>;
}

export interface Paper {
  paper_id: string;
  dir: string;
  doi: string | null;
  title: string | null;
  authors: string | null;
  first_author: string | null;
  journal: string | null;
  volume: string | null;
  issue: string | null;
  year: string | number | null;
  identity_source?: string;
  channels: Record<string, { state: string; detail?: string }>;
  n_runs: number;
  runs: { name: string; status: string; verdict: string | null;
          n_findings: number;
          n_non_image_findings?: number | null;
          pipeline_version?: string | null;
          analysed_at?: string | null }[];
  latest_run: string | null;
  analysed_at?: string | null;
  analysed_at_source?: "recorded" | "file_mtime" | null;
  verdict: string | null;
  worst_severity_9?: number | null;
  n_findings: number | null;
  // Absent (not 0) on an index written before this field existed -- the table
  // shows a dash and says to rescan, rather than passing the total off as the
  // non-image count.
  n_non_image_findings?: number | null;
  /** Standing groups the image adjudicator left unexplained or never
   *  judged. `insufficient_evidence` survivors are counted SEPARATELY in
   *  n_image_undecided — still standing, but not what the LLM called
   *  suspicious, and folding them in is what made this column read 834
   *  where 344 was the truth (2026-09-08). */
  image_status?: string;
  n_image_findings?: number | null;
  n_image_undecided?: number | null;
  /** Release that produced the latest run (run_meta.json `version`). */
  pipeline_version?: string | null;
  /** Has anyone OPENED this paper's review page? Absent on an index written
   *  before view tracking — which is neither "no" nor "unknown", it is a
   *  question this index was never asked. `viewed: null` with
   *  `source: "unreadable"` IS unknown: the record exists and could not be
   *  read. */
  viewed?: {
    viewed: boolean | null;
    n_views: number | null;
    first_at: string | null;
    last_at: string | null;
    viewers: (string | null)[];
    source: "recorded" | "inferred_from_review" | "none" | "unreadable";
  };
  review: {
    reviewed: boolean;
    paper_status?: string;
    reviewed_by?: string | null;
    reviewed_at?: string | null;
    n_decisions: number;
    submitted_to_pubpeer?: boolean | null;
    pubpeer_url?: string | null;
    pubpeer_note?: string | null;
  };
  sources: {
    state: string;
    pdf: boolean;
    xml: boolean;
    body_md: boolean;
    landing_page_only: boolean;
    /** Page count of the largest PDF, measured only when an XML is also
     *  held; null/absent = unknown (no fitz), never a claim. */
    main_pdf_pages?: number | null;
    /** ≤2-page PDF beside a full-text XML: a publisher preview stub, not
     *  the paper — image checks were effectively figure-blind. */
    pdf_suspect_stub?: boolean;
  };
  evidence: { path: string | null; is_video?: boolean }[];
  pubpeer?: {
    has_entry: boolean;
    is_image_integrity: boolean;
    figures: string[];
    n_comments: number;
    url?: string | null;
  } | null;
}

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
