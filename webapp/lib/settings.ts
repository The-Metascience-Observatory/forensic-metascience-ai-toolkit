import "server-only";

import fs from "node:fs";
import path from "node:path";
import os from "node:os";

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

export type Role = "reviewer" | "admin";
/** One entry of the hosted-mode reviewer directory: the Cloudflare Access
 *  email, the display name the Python service records as `reviewer`, and
 *  the role `lib/routeGuard.ts` gates on. Local mode ignores it. */
export interface Reviewer { email: string; name: string; role: Role }
export const DEFAULT_DIRECTORY: Reviewer[] = [{ email: "delton17@gmail.com", name: "Dan Elton", role: "admin" }];

export function asDirectory(v: unknown): Reviewer[] {
  if (!Array.isArray(v)) return [];
  const out: Reviewer[] = [];
  for (const x of v) {
    if (!x || typeof x !== "object") continue;
    const r = x as Record<string, unknown>;
    const email = typeof r.email === "string" ? r.email.trim().toLowerCase() : "";
    if (!email || out.some((o) => o.email === email)) continue;
    const name = typeof r.name === "string" && r.name.trim() ? r.name.trim() : email;
    out.push({ email, name, role: r.role === "admin" ? "admin" : "reviewer" });
  }
  return out;
}

const DATA_DIR = path.join(process.cwd(), "data");
/** Machine configuration must never live in the Dropbox checkout. */
export function settingsPath(): string {
  if (process.env.METASCIENCE_SETTINGS_FILE) return path.resolve(process.env.METASCIENCE_SETTINGS_FILE);
  const base = process.platform === "darwin"
    ? path.join(os.homedir(), "Library", "Application Support")
    : process.platform === "win32"
      ? process.env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local")
      : process.env.XDG_CONFIG_HOME || path.join(os.homedir(), ".config");
  return path.join(base, "metascience", "webapp", "settings.json");
}

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
  const directory = "reviewers" in onDisk ? asDirectory(onDisk.reviewers) : DEFAULT_DIRECTORY;
  return {
    python_bin: onDisk.python_bin,
    papers_root: hostPath(envRoot || onDisk.papers_root || DEFAULT_PAPERS_ROOT),
    known_reviewers: [...new Set([...DEFAULT_REVIEWERS, ...directory.map((r) => r.name), ...reviewers])],
    reviewers: directory,
  };
}

function asStringList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
}

/** `reviewers` omitted keeps the directory on disk (or the default). */
export function saveSettings(next: Omit<Settings, "reviewers"> & { reviewers?: Reviewer[] }): Settings {
  const file = settingsPath();
  const current = readLocalSettings();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const directory = Array.isArray(next.reviewers) ? asDirectory(next.reviewers)
    : "reviewers" in current ? asDirectory(current.reviewers) : DEFAULT_DIRECTORY;
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
  fs.writeFileSync(file, JSON.stringify(merged, null, 2) + "\n", { mode: 0o600 });
  return merged;
}
