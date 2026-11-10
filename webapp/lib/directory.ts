/** The hosted-mode user directory: who may use the app, their role, and the
 *  projects a reviewer is assigned.
 *
 * No `server-only` import: `proxy.ts` loads this module (it refuses unknown
 * users and other people's projects before any page or route runs), and so
 * do the plain-script tests. It only reads the settings file; writes go
 * through `lib/settings.ts`.
 *
 * Two gates, by design (Dan, 2026-11-10): Cloudflare Access decides who may
 * reach the app at all; this directory decides what a signed-in person may
 * do. An email Access admitted but the directory does not list is refused
 * ("not set up yet"), never treated as a reviewer of everything.
 */
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

export type Role = "reviewer" | "admin";
export const ROLES: readonly Role[] = ["admin", "reviewer"];

/** One user: the Cloudflare Access email (the stable key), the display name
 *  the Python service records as `reviewer` (Postgres `users.legacy_name`,
 *  so renaming someone splits their history), the role, and for a reviewer
 *  the project names they may open. An admin's `projects` is ignored. */
export interface Reviewer {
  email: string;
  name: string;
  role: Role;
  projects: string[];
}

export type Identity = Reviewer;

/** Machine configuration must never live in the Dropbox checkout. */
export function settingsPath(env: NodeJS.ProcessEnv = process.env): string {
  if (env.METASCIENCE_SETTINGS_FILE) return path.resolve(env.METASCIENCE_SETTINGS_FILE);
  const base =
    process.platform === "darwin"
      ? path.join(os.homedir(), "Library", "Application Support")
      : process.platform === "win32"
        ? env.LOCALAPPDATA || path.join(os.homedir(), "AppData", "Local")
        : env.XDG_CONFIG_HOME || path.join(os.homedir(), ".config");
  return path.join(base, "metascience", "webapp", "settings.json");
}

/** The directory a settings file without one starts with: the operator
 *  named by `METASCIENCE_ADMIN_EMAIL` (display name `METASCIENCE_ADMIN_NAME`)
 *  as admin, else nobody, so a fresh hosted instance has no admin until its
 *  operator names one. Never a person's address in this public source. */
export function defaultDirectory(env: NodeJS.ProcessEnv = process.env): Reviewer[] {
  const email = (env.METASCIENCE_ADMIN_EMAIL || "").trim().toLowerCase();
  if (!email) return [];
  return [
    {
      email,
      name: (env.METASCIENCE_ADMIN_NAME || "").trim() || email,
      role: "admin",
      projects: [],
    },
  ];
}

function projectList(v: unknown): string[] {
  if (!Array.isArray(v)) return [];
  return [
    ...new Set(
      v
        .filter((x): x is string => typeof x === "string")
        .map((x) => x.trim())
        .filter(Boolean),
    ),
  ].sort();
}

/** Parse a stored directory, dropping malformed entries and duplicate emails. */
export function asDirectory(v: unknown): Reviewer[] {
  if (!Array.isArray(v)) return [];
  const out: Reviewer[] = [];
  for (const x of v) {
    if (!x || typeof x !== "object") continue;
    const r = x as Record<string, unknown>;
    const email = typeof r.email === "string" ? r.email.trim().toLowerCase() : "";
    if (!email || out.some((o) => o.email === email)) continue;
    const name = typeof r.name === "string" && r.name.trim() ? r.name.trim() : email;
    const role: Role = r.role === "admin" ? "admin" : "reviewer";
    out.push({ email, name, role, projects: role === "admin" ? [] : projectList(r.projects) });
  }
  return out;
}

/** The directory as stored, else the seeded default. Read on every call: a
 *  small file, and an edit on the Users page must apply to the next request. */
export function readDirectory(env: NodeJS.ProcessEnv = process.env): Reviewer[] {
  let raw: Record<string, unknown>;
  try {
    raw = JSON.parse(fs.readFileSync(settingsPath(env), "utf-8"));
  } catch {
    return defaultDirectory(env);
  }
  return raw && typeof raw === "object" && "reviewers" in raw
    ? asDirectory(raw.reviewers)
    : defaultDirectory(env);
}

/** The directory entry for an authenticated email, or `null` when the
 *  directory does not list it. */
export function identityFor(email: string, directory: Reviewer[]): Identity | null {
  const key = email.trim().toLowerCase();
  const entry = directory.find((r) => r.email === key);
  return entry ? { ...entry, projects: [...entry.projects] } : null;
}

/** Whether this person may open a project. Admins open every project; a
 *  reviewer only the ones assigned to them. (Whether the project exists at
 *  all is `lib/projectSources.ts`'s question.) */
export function mayOpenProject(who: Identity, project: string): boolean {
  return who.role === "admin" || who.projects.includes(project);
}

/** The project a page or API path names, if any: `/project/<name>/…`. */
export function projectInPath(pathname: string): string | null {
  const m = /^\/project\/([^/]+)/.exec(pathname);
  if (!m) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch {
    return m[1];
  }
}

/** Pages only an admin may open. API routes are gated by `lib/routeGuard.ts`. */
export function adminOnlyPage(pathname: string): boolean {
  return (
    pathname === "/files" ||
    pathname.startsWith("/files/") ||
    pathname === "/admin" ||
    pathname.startsWith("/admin/")
  );
}
