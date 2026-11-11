import "server-only";

import { NOT_SET_UP, hostedMode, identity, mayOpenProject, signedInEmail } from "./auth.ts";
import { sourceView } from "./projectSources.ts";

/** Access control for every API route, in one place.
 *
 * Every handler calls `await guard(req, {project})` (after
 * `rejectCrossOrigin` for a write), naming the project it is about to touch:
 * the query's for a read, the parsed body's for a write. A test fails if a
 * route handler does not call it.
 *
 * Hosted mode (`proxy.ts` set the verified email):
 *   - no verified email → 401; an email the directory does not list → 403;
 *   - a route marked `forbidden` → 403 for everyone; `admin` → 403 unless the
 *     directory says admin;
 *   - a project the reviewer is not assigned → 403; a project-scoped route
 *     with no project named → 400 for a reviewer (an admin may list across).
 * Both modes: a project that is not one of the configured sources
 * (`lib/projectSources.ts`) → 404, so `pytest-600` and friends are not
 * reachable by URL either.
 *
 * `/api/workbench` dispatches on a `method`, so the route passes it.
 */
export interface Rule {
  path: string;
  method: "GET" | "POST";
  /** Every path under this prefix (`path` must end in `/`). */
  prefix?: true;
  admin?: true;
  /** Refused for everyone in hosted mode. */
  forbidden?: true;
  why: string;
}

/** Workbench writes that change this machine's catalog. */
export const ADMIN_WORKBENCH_METHODS: ReadonlySet<string> = new Set(["register_root", "map_paper", "register_file", "sync"]);
/** Workbench reads across every project or about the server's folders.
 *  (`status`, the sync line in the header, is open to everyone signed in; the
 *  route removes its error details for a reviewer.) */
export const ADMIN_WORKBENCH_READS: ReadonlySet<string> = new Set(["projects", "roots"]);
/** Workbench reads that are about no single project. */
export const UNSCOPED_WORKBENCH_READS: ReadonlySet<string> = new Set([...ADMIN_WORKBENCH_READS, "status"]);

export const RULES: readonly Rule[] = [
  { path: "/api/projects", method: "POST", admin: true, why: "deletes project folders on the server" },
  { path: "/api/projects", method: "GET", admin: true, why: "every project's deletion jobs" },
  { path: "/api/settings", method: "POST", admin: true, why: "changes the papers root and scans the server's disk" },
  { path: "/api/index", method: "POST", admin: true, why: "rescans the server's disk" },
  { path: "/api/metadata", method: "POST", admin: true, why: "writes metadata beside papers" },
  { path: "/api/images/reference", method: "POST", admin: true, why: "writes metadata beside papers" },
  { path: "/api/stats", method: "POST", admin: true, why: "runs the CLI over a corpus" },
  { path: "/api/draft", method: "POST", admin: true, why: "paid model call" },
  { path: "/api/images/website", method: "POST", admin: true, why: "writes the website checkout" },
  { path: "/api/images/sync", method: "POST", admin: true, why: "pulls shared records" },
  { path: "/api/admin/", method: "GET", prefix: true, admin: true, why: "users and project sources" },
  { path: "/api/admin/", method: "POST", prefix: true, admin: true, why: "users and project sources" },
  { path: "/api/reveal", method: "POST", forbidden: true, why: "opens a file manager on the server" },
];

/** Every route a signed-in reviewer may call (each is still scoped to the
 *  projects they are assigned, by `guard`). A handler that is in neither this
 *  list nor `RULES` is admin-only: a route added later is closed to reviewers
 *  until someone decides it here, and a test fails until it is listed. */
export const REVIEWER_ROUTES: ReadonlySet<string> = new Set([
  "GET /api/me", "GET /api/settings",
  "GET /api/workbench", "POST /api/workbench",
  "GET /api/findings", "GET /api/paper", "GET /api/runs", "GET /api/stats", "GET /api/draft",
  "GET /api/media", "GET /api/sheet",
  "POST /api/review", "POST /api/viewed",
  "GET /api/images", "POST /api/images",
  "GET /api/images/bulk", "POST /api/images/bulk",
  "GET /api/images/missed", "POST /api/images/missed",
  "GET /api/images/summary", "GET /api/images/text-regions", "POST /api/images/viewed",
]);

export interface Policy { admin: boolean; forbidden: boolean }

export function policyFor(req: Request, extra: { workbenchMethod?: string } = {}): Policy {
  const url = new URL(req.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const method = req.method.toUpperCase() === "HEAD" ? "GET" : req.method.toUpperCase();
  const policy: Policy = { admin: !REVIEWER_ROUTES.has(`${method} ${path}`), forbidden: false };
  for (const rule of RULES) {
    if (rule.method !== method) continue;
    if (rule.prefix ? !(path + "/").startsWith(rule.path) : rule.path !== path) continue;
    if (rule.admin) policy.admin = true;
    if (rule.forbidden) policy.forbidden = true;
  }
  if (path === "/api/workbench" && extra.workbenchMethod) {
    const admin = method === "POST" ? ADMIN_WORKBENCH_METHODS : ADMIN_WORKBENCH_READS;
    if (admin.has(extra.workbenchMethod)) policy.admin = true;
  }
  return policy;
}

export interface Need {
  /** The workbench method, for `/api/workbench`. */
  workbenchMethod?: string;
  /** The project this request touches. Present (even empty) means the route
   *  is project-scoped: a reviewer must name one they are assigned. */
  project?: unknown;
}

const json = (status: number, error: string) => Response.json({ error }, { status, headers: { "cache-control": "no-store" } });

/** `null` to proceed, else the refusal to return. */
export async function guard(req: Request, need: Need = {}): Promise<Response | null> {
  const policy = policyFor(req, need);
  const scoped = "project" in need;
  const project = typeof need.project === "string" ? need.project : "";
  if (hostedMode()) {
    if (!signedInEmail(req)) return json(401, "Sign in through Cloudflare Access");
    const who = identity(req);
    if (!who) return json(403, NOT_SET_UP);
    if (policy.forbidden) return json(403, "Not available in hosted mode");
    if (policy.admin && who.role !== "admin") return json(403, "Admin only");
    if (scoped && !project && who.role !== "admin") return json(400, "project required");
    if (project && !mayOpenProject(who, project)) return json(403, "You do not have access to this project");
  }
  if (project) {
    let view;
    try { view = await sourceView(); }
    catch { return json(503, "The project list could not be read; try again shortly"); }
    if (view && !view.projects.has(project)) return json(404, "Unknown project");
  }
  return null;
}
