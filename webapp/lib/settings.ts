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
  known_reviewers: string[];
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
  return {
    python_bin: onDisk.python_bin,
    papers_root: hostPath(envRoot || onDisk.papers_root || DEFAULT_PAPERS_ROOT),
    known_reviewers: [...new Set([...DEFAULT_REVIEWERS, ...reviewers])],
  };
}

function asStringList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return v.filter((x): x is string => typeof x === "string");
}

export function saveSettings(next: Settings): Settings {
  const file = settingsPath();
  const current = readLocalSettings();
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const merged: Settings = {
    python_bin: next.python_bin ?? current.python_bin,
    papers_root: path.resolve(hostPath(next.papers_root)),
    known_reviewers: [...new Set([
      ...DEFAULT_REVIEWERS,
      ...asStringList(next.known_reviewers),
    ])],
  };
  fs.writeFileSync(file, JSON.stringify(merged, null, 2) + "\n", { mode: 0o600 });
  return merged;
}
