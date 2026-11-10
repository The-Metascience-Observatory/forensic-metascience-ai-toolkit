import "server-only";

import fs from "node:fs";
import path from "node:path";

import { SCAFFOLDING_DIRS } from "./constants.gen.ts";
import { loadSettings, type ProjectSources } from "./settings.ts";
import { workbench } from "./workbench.ts";

/** Which projects exist, as the admin configured them (`ProjectSources` in
 *  `lib/settings.ts`). A project is a NAME (the catalog's corpus name, which
 *  keys records, reviews and image tables); the sources decide which names
 *  the app lists and serves, and link each to its folder(s) on this machine.
 *
 *  Resolution, in order:
 *   - each watched root's immediate subfolders, minus scaffolding (dot and
 *     underscore folders, `SCAFFOLDING_DIRS`), each a project named after the
 *     folder; a new subfolder appears on the next read with no restart;
 *   - every catalog root registered at a folder INSIDE a watched root (the
 *     `<author>__pubpeer_checked_*` session corpora, nested and differently
 *     named); a root at the watched folder itself is a collection registered
 *     by mistake and does not count;
 *   - each added folder, under its chosen name;
 *   - each adopted database-only name.
 *  A (name, folder) pair the catalog does not know yet is registered with
 *  the service (`register_root`), so the review pages find its files.
 *
 *  Absent sources: `null`, and every catalog project is listed (local
 *  checkouts that never configured this behave as before). */

export interface SourcedFolder {
  path: string;
  available: boolean;
  /** `root`: found under a watched root (`source` names it); `folder`: added by hand. */
  via: "root" | "folder";
  source: string;
}

export interface SourcedProject {
  name: string;
  folders: SourcedFolder[];
  /** Adopted as a database-only project. */
  database: boolean;
}

export interface SourceView {
  sources: ProjectSources;
  projects: Map<string, SourcedProject>;
  /** Watched roots that are not readable directories on this machine. */
  missingRoots: string[];
}

const SCAFFOLDING: ReadonlySet<string> = new Set(SCAFFOLDING_DIRS);

export function isProjectFolderName(name: string): boolean {
  return !!name && !name.startsWith(".") && !name.startsWith("_") && !SCAFFOLDING.has(name);
}

/** Strictly inside `base` (the base itself does not count). */
export function insideRoot(p: string, base: string): boolean {
  const rel = path.relative(base, p);
  return !!rel && !rel.startsWith("..") && !path.isAbsolute(rel);
}

export function isDirectory(p: string): boolean {
  try {
    return fs.lstatSync(p).isDirectory();
  } catch {
    return false;
  }
}

type CatalogRoot = { project: string; path: string; available?: boolean };

/** Pure resolution, given the catalog's roots and a directory lister: what
 *  `sourceView` computes, testable without a service or a disk. */
export function resolveSources(
  sources: ProjectSources,
  roots: CatalogRoot[],
  list: (dir: string) => string[] | null,
  isDir: (p: string) => boolean = isDirectory,
): {
  projects: Map<string, SourcedProject>;
  missingRoots: string[];
  toRegister: { project: string; path: string }[];
} {
  const projects = new Map<string, SourcedProject>();
  const missingRoots: string[] = [];
  const known = new Set(roots.map((r) => `${r.project}\0${path.resolve(r.path)}`));
  const resolved = roots.filter((r) => r.available !== false).map((r) => path.resolve(r.path));
  const toRegister: { project: string; path: string }[] = [];
  const entry = (name: string) => {
    let p = projects.get(name);
    if (!p) {
      p = { name, folders: [], database: false };
      projects.set(name, p);
    }
    return p;
  };
  const addFolder = (name: string, folder: SourcedFolder) => {
    const p = entry(name);
    if (!p.folders.some((f) => f.path === folder.path)) p.folders.push(folder);
    if (folder.available && !known.has(`${name}\0${folder.path}`)) {
      known.add(`${name}\0${folder.path}`);
      toRegister.push({ project: name, path: folder.path });
    }
  };
  for (const raw of sources.roots) {
    const base = path.resolve(raw);
    const names = list(base);
    if (names === null) {
      missingRoots.push(base);
      continue;
    }
    for (const name of names) {
      if (!isProjectFolderName(name)) continue;
      const folder = path.join(base, name);
      // A folder OF projects (`fca_leads_2026-10/lead_a_tsc`): it holds
      // registered projects and is not one itself, so its projects are
      // listed (below) and it is not.
      const holder = resolved.some((r) => insideRoot(r, folder)) && !resolved.includes(folder);
      if (!holder && isDir(folder))
        addFolder(name, { path: folder, available: true, via: "root", source: base });
    }
    for (const r of roots) {
      const p = path.resolve(r.path);
      // Under a scaffolding folder (`_rw_image_veins_*`, `done/`) is not a
      // project either: the same rule as the subfolders above, applied to the
      // first level below the watched root.
      const first = path.relative(base, p).split(path.sep)[0];
      if (r.available !== false && insideRoot(p, base) && isProjectFolderName(first) && isDir(p)) {
        addFolder(r.project, { path: p, available: true, via: "root", source: base });
      }
    }
  }
  for (const f of sources.folders) {
    const p = path.resolve(f.path);
    addFolder(f.name, { path: p, available: isDir(p), via: "folder", source: p });
  }
  for (const name of sources.database) entry(name).database = true;
  return { projects, missingRoots, toRegister };
}

function listDir(dir: string): string[] | null {
  try {
    return fs
      .readdirSync(dir, { withFileTypes: true })
      .filter((d) => d.isDirectory()) // a symlink is not followed, as the catalog refuses them
      .map((d) => d.name);
  } catch {
    return null;
  }
}

const TTL_MS = 5000;
let cached: { at: number; value: Promise<SourceView | null> } | null = null;

/** The resolved view, cached for a few seconds (every guarded request asks). */
export function sourceView(): Promise<SourceView | null> {
  const now = Date.now();
  if (cached && now - cached.at < TTL_MS) return cached.value;
  const value = compute();
  cached = { at: now, value };
  value.catch(() => {
    if (cached?.value === value) cached = null;
  });
  return value;
}

/** Forget the cached view: the sources were just edited. */
export function invalidateSources(): void {
  cached = null;
}

async function compute(): Promise<SourceView | null> {
  const sources = loadSettings().project_sources;
  if (!sources) return null;
  const { roots } = await workbench<{ roots: CatalogRoot[] }>("roots");
  const { projects, missingRoots, toRegister } = resolveSources(sources, roots || [], listDir);
  for (const r of toRegister) {
    // Best effort: an unregistered folder still lists; its papers appear
    // once the service knows the root.
    await workbench("register_root", r).catch(() => undefined);
  }
  return { sources, projects, missingRoots };
}

/** Whether a project name exists for the app. `true` when no sources are
 *  configured (every catalog name is listed then). */
export async function isSourcedProject(name: string): Promise<boolean> {
  const view = await sourceView();
  return view === null || view.projects.has(name);
}
