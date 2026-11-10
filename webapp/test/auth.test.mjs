// Hosted mode: the proxy's Cloudflare Access verification, the identity
// header it forwards, the reviewer directory, and the hosted-only origin
// rule. Tokens are minted here with a throwaway RS256 key and the JWKS fetch
// is stubbed, so nothing reaches Cloudflare.
import { test } from "vitest";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { SignJWT, exportJWK, generateKeyPair } from "jose";
import { NextRequest } from "next/server";

const TEAM = "unit-test-team", AUD = "a".repeat(64), ISSUER = `https://${TEAM}.cloudflareaccess.com`;
const CERTS = `${ISSUER}/cdn-cgi/access/certs`;
const HEADER = "x-ms-reviewer-email";

function snapshotEnv() {
  const before = { ...process.env };
  return () => {
    for (const k of Object.keys(process.env)) if (!(k in before)) delete process.env[k];
    Object.assign(process.env, before);
  };
}

async function keyring() {
  const { privateKey, publicKey } = await generateKeyPair("RS256", { extractable: true });
  const jwk = { ...(await exportJWK(publicKey)), kid: "k1", use: "sig", alg: "RS256" };
  const mint = (claims, { expired = false, issuer = ISSUER, aud = AUD, kid = "k1" } = {}) => {
    let jwt = new SignJWT(claims).setProtectedHeader({ alg: "RS256", kid }).setIssuer(issuer).setAudience(aud)
      .setIssuedAt(expired ? Math.floor(Date.now() / 1000) - 7200 : undefined);
    jwt = expired ? jwt.setExpirationTime(Math.floor(Date.now() / 1000) - 3600) : jwt.setExpirationTime("1h");
    return jwt.sign(privateKey);
  };
  return { jwk, mint };
}

/** The headers `NextResponse.next({request:{headers}})` forwards to handlers. */
function forwarded(res) {
  const names = (res.headers.get("x-middleware-override-headers") || "").split(",").map((s) => s.trim()).filter(Boolean);
  return Object.fromEntries(names.map((n) => [n, res.headers.get(`x-middleware-request-${n}`)]));
}

test("proxy: Cloudflare Access token verification", async () => {
  const restore = snapshotEnv();
  const realFetch = globalThis.fetch;
  try {
    process.env.METASCIENCE_ACCESS_TEAM = TEAM;
    process.env.METASCIENCE_ACCESS_AUD = AUD;
    const { jwk, mint } = await keyring();
    const fetched = [];
    globalThis.fetch = async (url) => {
      fetched.push(String(url));
      assert.equal(String(url), CERTS, "JWKS comes from the team's certs endpoint");
      return new Response(JSON.stringify({ keys: [jwk] }), { headers: { "content-type": "application/json" } });
    };
    const { proxy } = await import("../proxy.ts");
    const req = (url, headers = {}) => new NextRequest(`http://127.0.0.1:3101${url}`, { headers });

    // No token: JSON 401 on the API, a sign-in page elsewhere, nothing forwarded.
    const api = await proxy(req("/api/paper?project=x"));
    assert.equal(api.status, 401);
    assert.match(api.headers.get("content-type"), /json/);
    assert.deepEqual(await api.json(), { error: "Missing Cloudflare Access token" });
    const page = await proxy(req("/project/x"));
    assert.equal(page.status, 401);
    assert.match(page.headers.get("content-type"), /text\/html/);
    assert.match(await page.text(), /Sign in through Cloudflare Access/);
    assert.equal(fetched.length, 0, "no JWKS fetch without a token");

    // A valid token: the verified email reaches the handler, lower-cased.
    const good = await mint({ email: "Reviewer@Example.org" });
    const ok = await proxy(req("/api/paper", { "cf-access-jwt-assertion": good, [HEADER]: "spoofed@example.org" }));
    assert.equal(ok.status, 200);
    assert.equal(forwarded(ok)[HEADER], "reviewer@example.org");
    assert.equal(fetched.length, 1);

    // The cookie is accepted too; the JWKS is cached.
    const viaCookie = await proxy(req("/", { cookie: `theme=dark; CF_Authorization=${good}` }));
    assert.equal(viaCookie.status, 200);
    assert.equal(forwarded(viaCookie)[HEADER], "reviewer@example.org");
    assert.equal(fetched.length, 1);

    // Expired, wrong audience, wrong issuer, unknown key, no email: all 401.
    const bad = {
      expired: await mint({ email: "r@example.org" }, { expired: true }),
      audience: await mint({ email: "r@example.org" }, { aud: "b".repeat(64) }),
      issuer: await mint({ email: "r@example.org" }, { issuer: "https://other.cloudflareaccess.com" }),
      noEmail: await mint({ common_name: "service-token" }),
      garbage: "not.a.jwt",
    };
    for (const [why, token] of Object.entries(bad)) {
      const res = await proxy(req("/api/review", { "cf-access-jwt-assertion": token, [HEADER]: "spoofed@example.org" }));
      assert.equal(res.status, 401, why);
      assert.equal(res.headers.get("x-middleware-override-headers"), null, `${why}: nothing forwarded`);
    }
    const unknownKey = await (async () => {
      const other = await keyring();
      return other.mint({ email: "r@example.org" });
    })();
    assert.equal((await proxy(req("/api/review", { "cf-access-jwt-assertion": unknownKey }))).status, 401, "unknown key");

    // Every API route is behind the proxy's matcher.
    const { config } = await import("../proxy.ts");
    const matcher = new RegExp(`^${config.matcher[0].replace(/:[a-z]+\*?/g, "").replace(/\((?!\?)/g, "(?:")}$`);
    for (const route of routes()) {
      assert.ok(matcher.test(`/api/${route}`), `/api/${route} matched`);
      const res = await proxy(req(`/api/${route}`));
      assert.equal(res.status, 401, `/api/${route} without a token`);
    }
    for (const open of ["/_next/static/chunks/main.js", "/favicon.ico"]) assert.ok(!matcher.test(open), `${open} not matched`);
    for (const gated of ["/", "/project/x/review/y", "/api/media?project=x", "/pdf.worker.min.mjs"]) assert.ok(matcher.test(gated), `${gated} matched`);
  } finally {
    globalThis.fetch = realFetch;
    restore();
  }
});

test("proxy: local mode strips the identity header and lets everything through", async () => {
  const restore = snapshotEnv();
  try {
    delete process.env.METASCIENCE_ACCESS_TEAM;
    delete process.env.METASCIENCE_ACCESS_AUD;
    const { proxy } = await import("../proxy.ts");
    const res = await proxy(new NextRequest("http://127.0.0.1:3100/api/review", { headers: { [HEADER]: "spoofed@example.org", "x-keep": "1" } }));
    assert.equal(res.status, 200);
    const fwd = forwarded(res);
    assert.equal(fwd[HEADER], undefined, "client header removed");
    assert.equal(fwd["x-keep"], "1");
  } finally { restore(); }
});

test("identity: reviewer directory and roles", async () => {
  const restore = snapshotEnv();
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "workbench-auth-"));
  try {
    const file = path.join(scratch, "settings.json");
    process.env.METASCIENCE_SETTINGS_FILE = file;
    fs.writeFileSync(file, JSON.stringify({ papers_root: scratch, known_reviewers: ["Typed Name"],
      reviewers: [{ email: "Dan@Example.org", name: "Dan Elton", role: "admin" }, { email: "rev@example.org", name: "Second Reviewer", role: "reviewer" }] }));
    const { identity, identityFor, requireAdmin, withReviewer } = await import("../lib/auth.ts");
    const { loadSettings, saveSettings, defaultDirectory } = await import("../lib/settings.ts");
    const req = (email) => new Request("http://127.0.0.1:3101/api/review", { headers: email ? { [HEADER]: email } : {} });

    // Local mode: no identity, everyone proceeds, bodies pass through.
    assert.equal(identity(req("dan@example.org")), null);
    assert.equal(requireAdmin(req(null)), null);
    assert.deepEqual(withReviewer(req("dan@example.org"), { reviewer: "Typed" }), { reviewer: "Typed" });
    assert.deepEqual(loadSettings().known_reviewers, ["Dan Elton", "Second Reviewer", "Typed Name"]);

    process.env.METASCIENCE_ACCESS_TEAM = TEAM;
    process.env.METASCIENCE_ACCESS_AUD = AUD;
    assert.deepEqual(identity(req("DAN@example.org")), { email: "dan@example.org", name: "Dan Elton", role: "admin" });
    assert.deepEqual(identity(req("rev@example.org")), { email: "rev@example.org", name: "Second Reviewer", role: "reviewer" });
    assert.deepEqual(identity(req("new@example.org")), { email: "new@example.org", name: "new@example.org", role: "reviewer" }, "unknown email is a reviewer shown by address");
    assert.equal(identity(req(null)), null, "no header: no identity, even in hosted mode");
    assert.equal(requireAdmin(req("dan@example.org")), null);
    assert.equal(requireAdmin(req("rev@example.org"))?.status, 403);
    assert.equal(requireAdmin(req(null))?.status, 401);
    assert.deepEqual(withReviewer(req("rev@example.org"), { reviewer: "Mallory", decision: "x" }), { reviewer: "Second Reviewer", decision: "x" });
    assert.deepEqual(withReviewer(req("rev@example.org"), { viewer: "Mallory" }, "viewer"), { viewer: "Second Reviewer" });

    // Directory absent on disk: seeded from the environment's admin (never
    // from a name in the source), and a save persists it; with no admin
    // named, nobody is an admin.
    fs.writeFileSync(file, JSON.stringify({ papers_root: scratch }));
    process.env.METASCIENCE_ADMIN_EMAIL = "Admin@Example.org";
    process.env.METASCIENCE_ADMIN_NAME = "Site Admin";
    const seeded = [{ email: "admin@example.org", name: "Site Admin", role: "admin" }];
    assert.deepEqual(defaultDirectory(), seeded);
    assert.deepEqual(loadSettings().reviewers, seeded);
    assert.deepEqual(identityFor("admin@example.org", loadSettings().reviewers), seeded[0]);
    saveSettings({ papers_root: scratch, known_reviewers: ["Typed Name"] });
    assert.deepEqual(JSON.parse(fs.readFileSync(file, "utf8")).reviewers, seeded);
    delete process.env.METASCIENCE_ADMIN_EMAIL; delete process.env.METASCIENCE_ADMIN_NAME;
    fs.writeFileSync(file, JSON.stringify({ papers_root: scratch }));
    assert.deepEqual(loadSettings().reviewers, []);
    assert.deepEqual(identityFor("anyone@example.org", loadSettings().reviewers).role, "reviewer");
    // Malformed entries are dropped, roles other than admin are reviewer.
    saveSettings({ papers_root: scratch, known_reviewers: [], reviewers: [{ email: "x@example.org", role: "root" }, { name: "no email" }, "junk"] });
    assert.deepEqual(loadSettings().reviewers, [{ email: "x@example.org", name: "x@example.org", role: "reviewer" }]);
  } finally {
    restore();
    fs.rmSync(scratch, { recursive: true, force: true });
  }
});

test("origin check: public origin and forwarded scheme in hosted mode only", async () => {
  const restore = snapshotEnv();
  try {
    const { rejectCrossOrigin, publicOrigin } = await import("../lib/mutation.ts");
    const at = (url, headers) => rejectCrossOrigin(new Request(url, { method: "POST", headers }));
    delete process.env.METASCIENCE_ACCESS_TEAM; delete process.env.METASCIENCE_ACCESS_AUD;
    process.env.METASCIENCE_PUBLIC_ORIGIN = "https://review.example.org";
    assert.equal(publicOrigin(), null, "ignored in local mode");
    assert.equal(at("http://localhost:3101/api/review", { origin: "https://review.example.org" })?.status, 403);
    assert.equal(at("http://review.example.org/api/review", { origin: "https://review.example.org", "x-forwarded-proto": "https" })?.status, 403);
    assert.equal(at("http://localhost:3101/api/review", { origin: "http://127.0.0.1:3101" }), null, "loopback alias still accepted");

    process.env.METASCIENCE_ACCESS_TEAM = TEAM; process.env.METASCIENCE_ACCESS_AUD = AUD;
    assert.equal(publicOrigin(), "https://review.example.org");
    assert.equal(at("http://localhost:3101/api/review", { origin: "https://review.example.org" }), null, "public origin is same-origin");
    assert.equal(at("http://review.example.org/api/review", { origin: "https://review.example.org", "x-forwarded-proto": "https" }), null);
    assert.equal(at("http://localhost:3101/api/review", { origin: "https://evil.example.org" })?.status, 403);
    assert.equal(at("http://evil.example.org/api/review", { origin: "https://evil.example.org", "x-forwarded-proto": "https" })?.status, 403, "forwarded scheme never vouches for another host");
    assert.equal(at("http://localhost:3101/api/review", { origin: "https://review.example.org", "sec-fetch-site": "cross-site" })?.status, 403);
    assert.equal(at("http://localhost:3101/api/review", { origin: "http://127.0.0.1:3101" }), null);
    process.env.METASCIENCE_PUBLIC_ORIGIN = "not a url";
    assert.equal(publicOrigin(), null);
  } finally { restore(); }
});

test("start:hosted refuses to start with the hosted variables unset", async () => {
  const { requireHostedEnv, modeBanner, hostedMode } = await import("../scripts/serve.mjs");
  assert.throws(() => requireHostedEnv({}), /missing: METASCIENCE_ACCESS_TEAM, METASCIENCE_ACCESS_AUD, METASCIENCE_PUBLIC_ORIGIN/);
  assert.throws(() => requireHostedEnv({ METASCIENCE_ACCESS_TEAM: TEAM, METASCIENCE_ACCESS_AUD: AUD }), /missing: METASCIENCE_PUBLIC_ORIGIN/);
  assert.throws(() => requireHostedEnv({ METASCIENCE_ACCESS_TEAM: TEAM, METASCIENCE_ACCESS_AUD: AUD, METASCIENCE_PUBLIC_ORIGIN: "http://review.example.org" }), /https/);
  const full = { METASCIENCE_ACCESS_TEAM: TEAM, METASCIENCE_ACCESS_AUD: AUD, METASCIENCE_PUBLIC_ORIGIN: "https://review.example.org" };
  requireHostedEnv(full);
  assert.equal(hostedMode({}), false);
  assert.match(modeBanner({}), /^Mode: local/);
  assert.match(modeBanner(full), /^Mode: hosted .*review\.example\.org/);
});

function routes() {
  const dir = path.join(import.meta.dirname, "..", "app", "api");
  const out = [];
  const walk = (d, rel) => {
    for (const entry of fs.readdirSync(d, { withFileTypes: true })) {
      if (entry.isDirectory()) walk(path.join(d, entry.name), rel ? `${rel}/${entry.name}` : entry.name);
      else if (entry.name === "route.ts") out.push(rel);
    }
  };
  walk(dir, "");
  return out.sort();
}
