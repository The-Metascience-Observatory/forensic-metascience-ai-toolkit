import "server-only";

import path from "node:path";

import { asDirectory, type Reviewer } from "./directory.ts";
import { badProject } from "./paths.ts";
import { isDirectory, sourceView, type SourcedFolder } from "./projectSources.ts";
import { asProjectSources, loadSettings, type ProjectSources } from "./settings.ts";
import { workbench } from "./workbench.ts";

/** What the admin pages read and validate. Pure-ish helpers so the routes
 *  stay thin and the rules are testable. */

export interface CatalogProject {
  name: string;
  n_papers: number;
  done?: boolean;
}

export async function catalogProjects(): Promise<CatalogProject[]> {
  const index = await workbench<{ projects: CatalogProject[] }>("projects");
  return (index.projects || []).map((p) => ({
    name: p.name,
    n_papers: p.n_papers || 0,
    done: !!p.done,
  }));
}

export interface ProjectRow {
  name: string;
  n_papers: number;
  done: boolean;
  folders: SourcedFolder[];
  database: boolean;
  members: string[];
}

export interface UnsourcedRow {
  name: string;
  n_papers: number;
  folders: { path: string; available: boolean }[];
}

export interface ProjectsPayload {
  configured: boolean;
  sources: ProjectSources;
  projects: ProjectRow[];
  unsourced: UnsourcedRow[];
  missingRoots: string[];
  /** Watched roots to start with, when nothing is configured yet. */
  suggested: string[];
}

/** Folders holding several catalog projects' roots, plus the papers root:
 *  the likely watched roots on a machine that never configured any. */
export function suggestRoots(
  papersRoot: string,
  roots: { path: string; available?: boolean }[],
): string[] {
  const parents = new Map<string, number>();
  for (const r of roots) {
    if (r.available === false) continue;
    const parent = path.dirname(path.resolve(r.path));
    parents.set(parent, (parents.get(parent) || 0) + 1);
  }
  const out = new Set<string>();
  if (papersRoot && isDirectory(papersRoot)) out.add(path.resolve(papersRoot));
  for (const [p, n] of [...parents].sort((a, b) => b[1] - a[1]))
    if (n >= 3 && isDirectory(p)) out.add(p);
  return [...out];
}

export async function projectsPayload(): Promise<ProjectsPayload> {
  const settings = loadSettings();
  const [catalog, view, rootsReply] = await Promise.all([
    catalogProjects(),
    sourceView(),
    workbench<{ roots: { project: string; path: string; available?: boolean }[] }>("roots"),
  ]);
  const roots = rootsReply.roots || [];
  const byName = new Map(catalog.map((p) => [p.name, p]));
  const members = (name: string) =>
    settings.reviewers
      .filter((r) => r.role !== "admin" && r.projects.includes(name))
      .map((r) => r.name);
  const projects: ProjectRow[] = view
    ? [...view.projects.values()]
        .map((p) => ({
          name: p.name,
          n_papers: byName.get(p.name)?.n_papers ?? 0,
          done: !!byName.get(p.name)?.done,
          folders: p.folders,
          database: p.database,
          members: members(p.name),
        }))
        .sort((a, b) => a.name.localeCompare(b.name))
    : catalog.map((p) => ({
        name: p.name,
        n_papers: p.n_papers,
        done: !!p.done,
        folders: roots
          .filter((r) => r.project === p.name)
          .map((r) => ({
            path: r.path,
            available: r.available !== false,
            via: "folder" as const,
            source: r.path,
          })),
        database: false,
        members: members(p.name),
      }));
  const unsourced: UnsourcedRow[] = view
    ? catalog
        .filter((p) => !view.projects.has(p.name))
        .map((p) => ({
          name: p.name,
          n_papers: p.n_papers,
          folders: roots
            .filter((r) => r.project === p.name)
            .map((r) => ({ path: r.path, available: r.available !== false })),
        }))
        .sort((a, b) => b.n_papers - a.n_papers || a.name.localeCompare(b.name))
    : [];
  return {
    configured: !!view,
    sources: view?.sources ?? { roots: [], folders: [], database: [] },
    projects,
    unsourced,
    missingRoots: view?.missingRoots ?? [],
    suggested: view ? [] : suggestRoots(settings.papers_root, roots),
  };
}

/** Validate edited sources. Paths must be existing directories on this
 *  machine (resolved, not symlinks); names must be plain folder-like names. */
export function validateSources(raw: unknown): { sources: ProjectSources } | { error: string } {
  const sources = asProjectSources(raw);
  if (!sources) return { error: "sources must be an object with roots, folders and database" };
  const roots: string[] = [];
  for (const r of sources.roots) {
    const p = path.resolve(r);
    if (!isDirectory(p)) return { error: `Not a folder on this machine: ${r}` };
    if (p === path.parse(p).root) return { error: "A whole drive cannot be a watched root" };
    if (!roots.includes(p)) roots.push(p);
  }
  const folders: { name: string; path: string }[] = [];
  for (const f of sources.folders) {
    const p = path.resolve(f.path);
    if (!isDirectory(p)) return { error: `Not a folder on this machine: ${f.path}` };
    if (badProject(f.name)) return { error: `Not a usable project name: ${f.name}` };
    if (folders.some((o) => o.name === f.name && o.path === p)) continue;
    folders.push({ name: f.name, path: p });
  }
  for (const name of sources.database)
    if (badProject(name)) return { error: `Not a usable project name: ${name}` };
  return { sources: { roots, folders, database: sources.database } };
}

/** Validate an edited user list against who is saving it. */
export function validateUsers(
  raw: unknown,
  editor: string | null,
): { users: Reviewer[] } | { error: string } {
  if (!Array.isArray(raw)) return { error: "users must be a list" };
  for (const u of raw) {
    const email =
      u && typeof u === "object" ? String((u as Record<string, unknown>).email || "").trim() : "";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))
      return { error: `Not an email address: ${email || "(empty)"}` };
  }
  const users = asDirectory(raw);
  if (users.length !== raw.length) return { error: "Each email may appear only once" };
  if (!users.some((u) => u.role === "admin")) return { error: "At least one admin is required" };
  if (editor && users.find((u) => u.email === editor)?.role !== "admin") {
    return { error: "You cannot remove yourself or take away your own admin role" };
  }
  const names = new Map<string, string>();
  for (const u of users) {
    const k = u.name.toLowerCase();
    if (names.has(k))
      return {
        error: `Two users share the display name "${u.name}"; decisions are recorded under it`,
      };
    names.set(k, u.email);
  }
  return { users };
}
