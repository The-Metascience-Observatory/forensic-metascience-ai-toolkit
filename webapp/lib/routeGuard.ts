import "server-only";

import { hostedMode, identity } from "./auth.ts";

/** Role gating for hosted mode, in one place.
 *
 * Every API route calls `guard(req)` after `rejectCrossOrigin`. In local
 * mode it is a no-op (one person, their own machine). In hosted mode an
 * unidentified request is 401 (the proxy sets the identity header after
 * verifying the Access token), a route marked `forbidden` is 403 for
 * everyone, and a route marked `admin` is 403 unless the directory says
 * the signed-in reviewer is an admin. Everything not listed is open to any
 * signed-in reviewer.
 *
 * `/api/workbench` POST dispatches on a `method` in its body, so the route
 * passes that method once it has parsed the body.
 */
export interface Rule {
  path: string;
  method: "GET" | "POST";
  /** Only when every listed query parameter has this value. */
  query?: Record<string, string>;
  admin?: true;
  /** Refused for everyone in hosted mode. */
  forbidden?: true;
  why: string;
}

export const ADMIN_WORKBENCH_METHODS: ReadonlySet<string> = new Set(["register_root", "map_paper", "register_file", "sync"]);

export const RULES: readonly Rule[] = [
  { path: "/api/projects", method: "POST", admin: true, why: "deletes project folders on the server" },
  { path: "/api/settings", method: "POST", admin: true, why: "changes the papers root and scans the server's disk" },
  { path: "/api/index", method: "POST", admin: true, why: "rescans the server's disk" },
  { path: "/api/metadata", method: "POST", admin: true, why: "writes metadata beside papers" },
  { path: "/api/images/reference", method: "POST", admin: true, why: "writes metadata beside papers" },
  { path: "/api/stats", method: "POST", admin: true, why: "runs the CLI over a corpus" },
  { path: "/api/draft", method: "POST", admin: true, why: "paid model call" },
  { path: "/api/images/website", method: "POST", admin: true, why: "writes the website checkout" },
  { path: "/api/images/sync", method: "POST", admin: true, why: "pulls shared records" },
  { path: "/api/reveal", method: "POST", forbidden: true, why: "opens a file manager on the server" },
];

export interface Policy { admin: boolean; forbidden: boolean }

export function policyFor(req: Request, extra: { workbenchMethod?: string } = {}): Policy {
  const url = new URL(req.url);
  const path = url.pathname.replace(/\/+$/, "") || "/";
  const method = req.method.toUpperCase();
  const policy: Policy = { admin: false, forbidden: false };
  for (const rule of RULES) {
    if (rule.path !== path || rule.method !== method) continue;
    if (rule.query && Object.entries(rule.query).some(([k, v]) => url.searchParams.get(k) !== v)) continue;
    if (rule.admin) policy.admin = true;
    if (rule.forbidden) policy.forbidden = true;
  }
  if (path === "/api/workbench" && method === "POST" && extra.workbenchMethod
      && ADMIN_WORKBENCH_METHODS.has(extra.workbenchMethod)) policy.admin = true;
  return policy;
}

/** `null` to proceed, else the refusal to return. */
export function guard(req: Request, extra: { workbenchMethod?: string } = {}): Response | null {
  if (!hostedMode()) return null;
  const who = identity(req);
  if (!who) return Response.json({ error: "Sign in through Cloudflare Access" }, { status: 401 });
  const policy = policyFor(req, extra);
  if (policy.forbidden) return Response.json({ error: "Not available in hosted mode" }, { status: 403 });
  if (policy.admin && who.role !== "admin") return Response.json({ error: "Admin only" }, { status: 403 });
  return null;
}
