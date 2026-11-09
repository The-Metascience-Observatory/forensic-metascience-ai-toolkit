import { hostedMode } from "./accessToken.ts";

/** Local clients may omit Origin; browser mutations must be same-origin.
 *
 * Next reports `req.url` as `localhost` whatever name the browser used, and
 * scripts/serve.mjs prints (and binds) 127.0.0.1, so a page opened from that
 * link had every save refused (measured 2026-11-07, Next 14 and 16 alike).
 * The loopback names are therefore one origin when scheme and port match. The
 * Host header is deliberately NOT trusted: under DNS rebinding an attacker's
 * name resolves to 127.0.0.1 and sends a matching Host and Origin.
 *
 * Hosted mode (lib/accessToken.ts): behind the Cloudflare Tunnel the browser
 * sends `Origin: https://<public host>` while `req.url` is `http://<host>`,
 * so the operator names the public origin in METASCIENCE_PUBLIC_ORIGIN and
 * it counts as same-origin, and `x-forwarded-proto` stands in for the
 * scheme of `req.url`. Neither applies in local mode. */
const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

export function publicOrigin(env: NodeJS.ProcessEnv = process.env): string | null {
  if (!hostedMode(env)) return null;
  const raw = (env.METASCIENCE_PUBLIC_ORIGIN || "").trim();
  if (!raw) return null;
  try { return new URL(raw).origin; } catch { return null; }
}

function sameOrigin(origin: string, url: URL, forwardedProto: string | null): boolean {
  if (origin === url.origin) return true;
  let o: URL;
  try { o = new URL(origin); } catch { return false; }
  if (LOOPBACK.has(o.hostname) && LOOPBACK.has(url.hostname)
      && o.protocol === url.protocol && o.port === url.port) return true;
  const trusted = publicOrigin();
  if (!trusted) return false;
  if (o.origin === trusted) return true;
  // The tunnel terminates TLS: the request reaches Node as http://<host>.
  if (forwardedProto && o.hostname === url.hostname && o.port === url.port
      && o.protocol === `${forwardedProto.split(",")[0].trim()}:`) return true;
  return false;
}

export function rejectCrossOrigin(req: Request): Response | null {
  const origin = req.headers.get("origin");
  const forwarded = publicOrigin() ? req.headers.get("x-forwarded-proto") : null;
  if ((origin && !sameOrigin(origin, new URL(req.url), forwarded)) || req.headers.get("sec-fetch-site") === "cross-site") {
    return Response.json({ error: "Cross-origin request refused" }, { status: 403 });
  }
  return null;
}
