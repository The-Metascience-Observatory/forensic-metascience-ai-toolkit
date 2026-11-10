/** Next 16 proxy (the `middleware.ts` successor): runs before every page,
 *  API and media request.
 *
 *  Always: strip a client-supplied `x-ms-reviewer-email`, the header the
 *  handlers read the signed-in reviewer from. In hosted mode (see
 *  `lib/accessToken.ts`): verify the Cloudflare Access token on the request
 *  and forward the verified email in that header; refuse everything else
 *  with 401 -- JSON for `/api/*`, a sign-in page for the rest. Cloudflare
 *  Access normally stops unauthenticated visitors before the tunnel; this is
 *  what makes a misconfigured Access application fail closed.
 *
 *  Then the user directory (`lib/directory.ts`): an email it does not list
 *  is refused ("not set up yet"); a reviewer is refused any `/project/<p>`
 *  page or `?project=<p>` request for a project not assigned to them, and
 *  the admin pages. This covers server-rendered pages, which call the
 *  service directly; every API route also checks its body's project with
 *  `lib/routeGuard.ts`, which this cannot read.
 */
import { NextResponse, type NextRequest } from "next/server";

import { adminOnlyPage, identityFor, mayOpenProject, projectInPath, readDirectory } from "@/lib/directory";
import { AccessTokenError, REVIEWER_EMAIL_HEADER, accessKeys, accessToken, hostedConfig,
  verifyAccessToken, type HostedConfig } from "@/lib/accessToken";

export const config = {
  // Build assets are not reviewer data; everything else, including /api/media
  // and the public folder, needs a signed-in reviewer in hosted mode.
  matcher: ["/((?!_next/static|_next/image|favicon.ico).*)"],
};

let keys: { certs: string; getKey: ReturnType<typeof accessKeys> } | null = null;
function keysFor(cfg: HostedConfig) {
  if (!keys || keys.certs !== cfg.certs.href) keys = { certs: cfg.certs.href, getKey: accessKeys(cfg) };
  return keys.getKey;
}

const SIGN_IN_PAGE = `<!doctype html><meta charset="utf-8"><title>Sign in</title>
<style>body{font:15px/1.5 system-ui,sans-serif;max-width:36em;margin:4em auto;padding:0 1em;color:#222}</style>
<h1>Sign in through Cloudflare Access</h1>
<p>This review workbench is available to invited reviewers only. Open the address you were given in your browser and sign in with the email that was invited; this page means the request arrived without a valid Cloudflare Access token.</p>`;

const page = (title: string, body: string) => `<!doctype html><meta charset="utf-8"><title>${title}</title>
<style>body{font:15px/1.5 system-ui,sans-serif;max-width:36em;margin:4em auto;padding:0 1em;color:#222}</style>
<h1>${title}</h1><p>${body}</p><p><a href="/">Back to your projects</a></p>`;

const NOT_SET_UP_PAGE = page("Your account is not set up yet",
  "You signed in, but nobody has added this email to the review platform yet. Ask the admin to add you on the Users page; then reload.");
const NO_ACCESS_PAGE = page("No access",
  "This page belongs to a project, or an admin area, that your account has not been given.");

function refused(req: NextRequest, error: string, status = 401, html = SIGN_IN_PAGE): NextResponse {
  if (req.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error }, { status, headers: { "cache-control": "no-store" } });
  }
  return new NextResponse(html, {
    status, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
  });
}

export async function proxy(req: NextRequest): Promise<NextResponse> {
  const headers = new Headers(req.headers);
  headers.delete(REVIEWER_EMAIL_HEADER);
  const cfg = hostedConfig();
  if (!cfg) return NextResponse.next({ request: { headers } });
  let email: string;
  try {
    ({ email } = await verifyAccessToken(accessToken(req.headers), cfg, keysFor(cfg)));
  } catch (e) {
    return refused(req, e instanceof AccessTokenError ? e.message : "Could not verify the Cloudflare Access token");
  }
  const who = identityFor(email, readDirectory());
  if (!who) {
    return refused(req, "Your account is not set up yet. Ask the admin to add you on the Users page.", 403, NOT_SET_UP_PAGE);
  }
  if (who.role !== "admin") {
    const path = req.nextUrl.pathname;
    const named = [projectInPath(path), req.nextUrl.searchParams.get("project")].filter((p): p is string => !!p);
    if (adminOnlyPage(path) || named.some((p) => !mayOpenProject(who, p))) {
      return refused(req, "You do not have access to this project", 403, NO_ACCESS_PAGE);
    }
  }
  headers.set(REVIEWER_EMAIL_HEADER, who.email);
  return NextResponse.next({ request: { headers } });
}
