/** Cloudflare Access token handling shared by `proxy.ts` and the server.
 *
 * No `server-only` import: the proxy bundle and the tests load this module
 * directly. Nothing here reads the reviewer directory; that is `lib/auth.ts`.
 *
 * Hosted mode is ON when both `METASCIENCE_ACCESS_TEAM` (the `<team>` of
 * `<team>.cloudflareaccess.com`) and `METASCIENCE_ACCESS_AUD` (the Access
 * application's Audience tag) are set. With either missing the app runs in
 * local mode, exactly as before: loopback bind, free-text reviewer name.
 */
import { createRemoteJWKSet, customFetch, jwtVerify, type JWTVerifyGetKey } from "jose";

/** Set by the proxy from the verified token; never trusted from a client. */
export const REVIEWER_EMAIL_HEADER = "x-ms-reviewer-email";
export const ACCESS_JWT_HEADER = "cf-access-jwt-assertion";
export const ACCESS_COOKIE = "CF_Authorization";

export interface HostedConfig {
  team: string;
  aud: string;
  issuer: string;
  certs: URL;
}

export function hostedConfig(env: NodeJS.ProcessEnv = process.env): HostedConfig | null {
  const team = (env.METASCIENCE_ACCESS_TEAM || "").trim();
  const aud = (env.METASCIENCE_ACCESS_AUD || "").trim();
  // One of the two set is a mistyped hosted deployment, not local mode:
  // answering as local mode would make every caller an admin behind the tunnel.
  if (Boolean(team) !== Boolean(aud)) throw new Error("Hosted mode needs both METASCIENCE_ACCESS_TEAM and METASCIENCE_ACCESS_AUD; only one is set");
  if (!team || !aud) return null;
  if (!/^[a-z0-9-]+$/i.test(team)) throw new Error(`METASCIENCE_ACCESS_TEAM is not a team name: ${team}`);
  const issuer = `https://${team}.cloudflareaccess.com`;
  return { team, aud, issuer, certs: new URL(`${issuer}/cdn-cgi/access/certs`) };
}

export function hostedMode(env: NodeJS.ProcessEnv = process.env): boolean {
  return hostedConfig(env) !== null;
}

/** The token Cloudflare attaches: the header on every proxied request, the
 *  cookie as a fallback for clients that only carry cookies. */
export function accessToken(headers: Headers): string | null {
  const header = headers.get(ACCESS_JWT_HEADER);
  if (header && header.trim()) return header.trim();
  const cookie = headers.get("cookie") || "";
  for (const part of cookie.split(";")) {
    const [k, ...rest] = part.trim().split("=");
    if (k === ACCESS_COOKIE && rest.length) return rest.join("=").trim();
  }
  return null;
}

export class AccessTokenError extends Error {
  // A plain field, not a parameter property: Node's type stripping (the
  // plain-script tests) erases types only.
  readonly reason: string;
  constructor(message: string, reason: string) {
    super(message);
    this.name = "AccessTokenError";
    this.reason = reason;
  }
}

/** The Access JWKS, fetched lazily and cached by jose. `fetchImpl` resolves
 *  `globalThis.fetch` at call time so a test can stub it before the first
 *  verification. */
export function accessKeys(cfg: HostedConfig,
                           fetchImpl: typeof fetch = (...args) => globalThis.fetch(...args)): JWTVerifyGetKey {
  return createRemoteJWKSet(cfg.certs, { [customFetch]: fetchImpl });
}

/** Verify a Cloudflare Access user token: RS256 signature against the team's
 *  JWKS, the application's audience, the team's issuer, and not expired. A
 *  valid token without an `email` claim (a service token) is refused: every
 *  write is keyed by a person. */
export async function verifyAccessToken(token: string | null, cfg: HostedConfig,
                                        getKey: JWTVerifyGetKey): Promise<{ email: string }> {
  if (!token) throw new AccessTokenError("Missing Cloudflare Access token", "missing");
  let payload;
  try {
    ({ payload } = await jwtVerify(token, getKey, {
      audience: cfg.aud, issuer: cfg.issuer, algorithms: ["RS256"],
    }));
  } catch (e) {
    const code = (e as { code?: string }).code || "invalid";
    throw new AccessTokenError(`Invalid Cloudflare Access token (${code})`, code);
  }
  const email = typeof payload.email === "string" ? payload.email.trim().toLowerCase() : "";
  if (!email) throw new AccessTokenError("Access token carries no email", "no_email");
  return { email };
}
