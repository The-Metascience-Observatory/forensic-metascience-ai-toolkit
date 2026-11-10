import "server-only";

import { REVIEWER_EMAIL_HEADER, hostedMode } from "./accessToken.ts";
import { identityFor, mayOpenProject, readDirectory, type Identity, type Role } from "./directory.ts";

export { hostedMode, identityFor, mayOpenProject };
export type { Identity, Role };

type HasHeaders = { headers: { get(name: string): string | null } };

/** The email `proxy.ts` verified from the Cloudflare Access token, or `null`
 *  (local mode, or a request that did not pass the proxy: the header is set
 *  only there, after verification, and a client-supplied copy is stripped). */
export function signedInEmail(req: HasHeaders): string | null {
  if (!hostedMode()) return null;
  const email = req.headers.get(REVIEWER_EMAIL_HEADER);
  return email && email.trim() ? email.trim().toLowerCase() : null;
}

/** Who is making this request: the directory entry for the signed-in email.
 *  `null` in local mode (no identity exists there), without a verified email,
 *  and for an email the directory does not list -- Access admitted them, but
 *  nobody has set them up, so they may do nothing (deny by default). */
export function identity(req: HasHeaders): Identity | null {
  const email = signedInEmail(req);
  return email ? identityFor(email, readDirectory()) : null;
}

/** Admin-only step: `null` to proceed. Local mode has no roles, so it always
 *  proceeds there. */
export function requireAdmin(req: Request): Response | null {
  if (!hostedMode()) return null;
  if (!signedInEmail(req)) return Response.json({ error: "Sign in through Cloudflare Access" }, { status: 401 });
  const who = identity(req);
  if (!who) return Response.json({ error: NOT_SET_UP }, { status: 403 });
  if (who.role !== "admin") return Response.json({ error: "Admin only" }, { status: 403 });
  return null;
}

export const NOT_SET_UP = "Your account is not set up yet. Ask the admin to add you on the Users page.";

/** The body a write handler passes on. In hosted mode the named field is
 *  the signed-in reviewer's display name whatever the client sent; in local
 *  mode the body is returned as it came. */
export function withReviewer<T extends Record<string, unknown>>(req: Request, body: T, field = "reviewer"): T {
  const who = identity(req);
  if (!who) return body;
  return { ...body, [field]: who.name };
}
