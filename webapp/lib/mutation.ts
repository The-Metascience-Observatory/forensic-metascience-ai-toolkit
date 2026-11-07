/** Local clients may omit Origin; browser mutations must be same-origin.
 *
 * Next reports `req.url` as `localhost` whatever name the browser used, and
 * scripts/serve.mjs prints (and binds) 127.0.0.1, so a page opened from that
 * link had every save refused (measured 2026-11-07, Next 14 and 16 alike).
 * The loopback names are therefore one origin when scheme and port match. The
 * Host header is deliberately NOT trusted: under DNS rebinding an attacker's
 * name resolves to 127.0.0.1 and sends a matching Host and Origin. */
const LOOPBACK = new Set(["localhost", "127.0.0.1", "[::1]"]);

function sameOrigin(origin: string, url: URL): boolean {
  if (origin === url.origin) return true;
  let o: URL;
  try { o = new URL(origin); } catch { return false; }
  return LOOPBACK.has(o.hostname) && LOOPBACK.has(url.hostname)
    && o.protocol === url.protocol && o.port === url.port;
}

export function rejectCrossOrigin(req: Request): Response | null {
  const origin = req.headers.get("origin");
  if ((origin && !sameOrigin(origin, new URL(req.url))) || req.headers.get("sec-fetch-site") === "cross-site") {
    return Response.json({ error: "Cross-origin request refused" }, { status: 403 });
  }
  return null;
}
