import "server-only";

import fs from "node:fs";
import path from "node:path";

import { asDirectory, defaultDirectory, settingsPath, type Reviewer } from "./directory.ts";
import { windowsAbsToWsl, wslAbsToWindows } from "./rel.ts";

/**
 * A papers root Greg types as `C:\Users\...` while the webapp runs in WSL
 * must become `/mnt/c/Users/...` before Node or Python look at it. The
 * inverse is for a Windows-native Node given a leftover WSL path.
 */
export function hostPath(p: string): string {
  const s = String(p || "").trim();
  if (!s) return s;
  if (process.platform === "win32") {
    return wslAbsToWindows(s) || s;
  }
  const wsl = windowsAbsToWsl(s);
  if (!wsl) return s;
  const mount = `/mnt/${s[0].toLowerCase()}`;
  try {
    if (fs.existsSync(mount)) return wsl;
  } catch {
    /* keep the original */
  }
  return s;
}

export const DEFAULT_PAPERS_ROOT =
  path.resolve(process.cwd(), "..", "..", "agent_for_forensic_metascience_papers");

export const DEFAULT_REVIEWERS = ["Dan Elton"];

export type { Reviewer, Role } from "./directory.ts";
export { asDirectory, defaultDirectory, settingsPath } from "./directory.ts";

/** Where projects come from (Dan, 2026-11-10). Every immediate subfolder of a
 *  watched `root` is a project named after it (and any catalog project
 *  registered at a folder inside that root); each `folders` entry is one
 *  folder added as a project by name; each `database` name is a project with
 *  findings in the database and no folder on this machine. Anything else the
 *  catalog knows (`pytest-600`, a scratch `corpus`) is not a project for the
 *  app. Absent: every catalog project is listed, as before. */
export interface ProjectSources {
  roots: string[];
  folders: { name: string; path: string }[];
  database: string[];
}

export function asProjectSources(v: unknown): ProjectSources | undefined {
  if (!v || typeof v !== "object") return undefined;
  const r = v as Record<string, unknown>;
  const strings = (x: unknown) => Array.isArray(x)
    ? [...new Set(x.filter((y): y is string => typeof y === "string").map((y) => y.trim()).filter(Boolean))] : [];
  const folders: { name: string; path: string }[] = [];
  if (Array.isArray(r.folders)) {
    for (const f of r.folders) {
      if (!f || typeof f !== "object") continue;
      const { name, path: p } = f as Record<string, unknown>;
      if (typeof name !== "string" || !name.trim() || typeof p !== "string" || !p.trim()) continue;
      if (folders.some((o) => o.name === name.trim() && o.path === p.trim())) continue;
      folders.push({ name: name.trim(), path: p.trim() });
    }
  }
  return { roots: strings(r.roots), folders, database: strings(r.database) };
}

const DATA_DIR = path.join(process.cwd(), "data");
function readLocalSettings(): Partial<Settings> {
  const file = settingsPath();
  try {
    return JSON.parse(fs.readFileSync(file, "utf-8"));
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e;
  }
  // One-time migration only. Later Dropbox changes cannot reset this machine.
  let legacy: Partial<Settings> = {};
  try { legacy = JSON.parse(fs.readFileSync(path.join(DATA_DIR, "settings.json"), "utf-8")); }
  catch { /* first run */ }
  let root = DEFAULT_PAPERS_ROOT;
  try {
    if (legacy.papers_root && fs.statSync(hostPath(legacy.papers_root)).isDirectory()) {
      root = hostPath(legacy.papers_root);
    }
  } catch { /* another machine's root is not a local default */ }
  const migrated = { ...legacy, papers_root: root };
  fs.mkdirSync(path.dirname(file), { recursive: true });
  try { fs.writeFileSync(file, JSON.stringify(migrated, null, 2) + "\n", { flag: "wx", mode: 0o600 }); }
  catch (e) { if ((e as NodeJS.ErrnoException).code !== "EEXIST") throw e; }
  return JSON.parse(fs.readFileSync(file, "utf-8"));
}

export interface Settings {
  python_bin?: string;
  papers_root: string;
  /** Every display name: the directory's names plus the free-text ones. */
  known_reviewers: string[];
  reviewers: Reviewer[];
  project_sources?: ProjectSources;
}

export function indexPath(): string {
  const env = process.env.METASCIENCE_INDEX;
  if (env && env.trim()) return path.resolve(env.trim());
  return path.join(DATA_DIR, "index.json");
}

export function loadSettings(): Settings {
  const envRoot = (process.env.METASCIENCE_PAPERS_ROOT || "").trim();
  const onDisk = readLocalSettings();
  const reviewers = Array.isArray(onDisk.known_reviewers)
    ? onDisk.known_reviewers.filter((x): x is string => typeof x === "string")
    : [];
  // Seeded, not written: a settings file without a directory behaves as if
  // it held the default one until the next save persists it.
  const directory = "reviewers" in onDisk ? asDirectory(onDisk.reviewers) : defaultDirectory();
  return {
    python_bin: onDisk.python_bin,
    papers_root: hostPath(envRoot || onDisk.papers_root || DEFAULT_PAPERS_ROOT),
    known_reviewers: [...new Set([...DEFAULT_REVIEWERS, ...directory.map((r) => r.name), ...reviewers])],
    reviewers: directory,
    project_sources: asProjectSources(onDisk.project_sources),
  };
}

function asStringList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
}

/** `reviewers` omitted keeps the directory on disk (or the default); keys
 *  this function does not manage (`project_sources`, legacy ones) are kept. */
export function saveSettings(next: Omit<Settings, "reviewers" | "project_sources"> & { reviewers?: Reviewer[] }): Settings {
  const current = readLocalSettings();
  const directory = Array.isArray(next.reviewers) ? asDirectory(next.reviewers)
    : "reviewers" in current ? asDirectory(current.reviewers) : defaultDirectory();
  const merged: Settings = {
    python_bin: next.python_bin ?? current.python_bin,
    papers_root: path.resolve(hostPath(next.papers_root)),
    known_reviewers: [...new Set([
      ...DEFAULT_REVIEWERS,
      ...directory.map((r) => r.name),
      ...asStringList(next.known_reviewers),
    ])],
    reviewers: directory,
  };
  writeSettingsFile({ ...current, ...merged });
  return { ...merged, project_sources: asProjectSources(current.project_sources) };
}

function writeSettingsFile(obj: object) {
  const file = settingsPath();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  // Written whole to a sibling and renamed: the proxy reads this file on every
  // request and must never see half of it.
  const tmp = `${file}.${process.pid}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(obj, null, 2) + "\n", { mode: 0o600 });
  fs.renameSync(tmp, file);
}

/** Replace the user directory (the Users page). */
export function saveDirectory(reviewers: Reviewer[]): Reviewer[] {
  const current = readLocalSettings();
  const directory = asDirectory(reviewers);
  const names = asStringList(current.known_reviewers);
  writeSettingsFile({ ...current, reviewers: directory,
    known_reviewers: [...new Set([...names, ...directory.map((r) => r.name)])] });
  return directory;
}

/** Replace the project sources (the Projects page). */
export function saveProjectSources(sources: ProjectSources): ProjectSources {
  const current = readLocalSettings();
  const clean = asProjectSources(sources) ?? { roots: [], folders: [], database: [] };
  writeSettingsFile({ ...current, project_sources: clean });
  return clean;
}
