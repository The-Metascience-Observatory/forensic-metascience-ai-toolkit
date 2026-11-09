import "server-only";

import { REVIEWER_EMAIL_HEADER, hostedMode } from "./accessToken.ts";
import { loadSettings, type Reviewer, type Role } from "./settings.ts";

export { hostedMode };
export type { Role };

export interface Identity {
  email: string;
  /** What the Python service records as `reviewer`; existing rows are keyed
   *  by this display name, so the directory keeps "Dan Elton" joined. */
  name: string;
  role: Role;
}

/** Look an authenticated email up in the reviewer directory. Unknown emails
 *  are still reviewers (Cloudflare Access already admitted them), shown by
 *  their address. */
export function identityFor(email: string, directory: Reviewer[]): Identity {
  const key = email.trim().toLowerCase();
  const entry = directory.find((r) => r.email.toLowerCase() === key);
  return { email: key, name: entry?.name || key, role: entry?.role === "admin" ? "admin" : "reviewer" };
}

/** Who is making this request. `null` in local mode (no identity exists
 *  there) and for a hosted request that did not pass the proxy, since the
 *  header is set only by `proxy.ts` after verifying the Access token and a
 *  client-supplied copy is stripped there. */
export function identity(req: Request): Identity | null {
  if (!hostedMode()) return null;
  const email = req.headers.get(REVIEWER_EMAIL_HEADER);
  if (!email || !email.trim()) return null;
  return identityFor(email, loadSettings().reviewers);
}

/** Admin-only step: `null` to proceed. Local mode has no roles, so it always
 *  proceeds there. */
export function requireAdmin(req: Request): Response | null {
  if (!hostedMode()) return null;
  const who = identity(req);
  if (!who) return Response.json({ error: "Sign in through Cloudflare Access" }, { status: 401 });
  if (who.role !== "admin") return Response.json({ error: "Admin only" }, { status: 403 });
  return null;
}

/** The body a write handler passes on. In hosted mode the named field is
 *  the signed-in reviewer's display name whatever the client sent; in local
 *  mode the body is returned as it came. */
export function withReviewer<T extends Record<string, unknown>>(req: Request, body: T, field = "reviewer"): T {
  const who = identity(req);
  if (!who) return body;
  return { ...body, [field]: who.name };
}
