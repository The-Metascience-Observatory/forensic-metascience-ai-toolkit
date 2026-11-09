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
 */
import { NextResponse, type NextRequest } from "next/server";

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

function refused(req: NextRequest, error: string): NextResponse {
  if (req.nextUrl.pathname.startsWith("/api/")) {
    return NextResponse.json({ error }, { status: 401, headers: { "cache-control": "no-store" } });
  }
  return new NextResponse(SIGN_IN_PAGE, {
    status: 401, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-store" },
  });
}

export async function proxy(req: NextRequest): Promise<NextResponse> {
  const headers = new Headers(req.headers);
  headers.delete(REVIEWER_EMAIL_HEADER);
  const cfg = hostedConfig();
  if (!cfg) return NextResponse.next({ request: { headers } });
  try {
    const { email } = await verifyAccessToken(accessToken(req.headers), cfg, keysFor(cfg));
    headers.set(REVIEWER_EMAIL_HEADER, email);
    return NextResponse.next({ request: { headers } });
  } catch (e) {
    return refused(req, e instanceof AccessTokenError ? e.message : "Could not verify the Cloudflare Access token");
  }
}
