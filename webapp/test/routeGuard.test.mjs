// The hosted-mode gating table: every listed route × anonymous / reviewer /
// admin × local / hosted, with the real directory lookup behind it.
import { test } from "vitest";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const HEADER = "x-ms-reviewer-email";
const WHO = { anonymous: null, reviewer: "rev@example.org", unknown: "stranger@example.org", admin: "dan@example.org" };

test("routeGuard matrix", async () => {
  const before = { ...process.env };
  const scratch = fs.mkdtempSync(path.join(os.tmpdir(), "workbench-guard-"));
  try {
    const file = path.join(scratch, "settings.json");
    process.env.METASCIENCE_SETTINGS_FILE = file;
    fs.writeFileSync(file, JSON.stringify({ papers_root: scratch, reviewers: [
      { email: "dan@example.org", name: "Dan Elton", role: "admin" },
      { email: "rev@example.org", name: "Second Reviewer", role: "reviewer" }] }));
    const { ADMIN_WORKBENCH_METHODS, RULES, guard, policyFor } = await import("../lib/routeGuard.ts");

    const request = (who, rule) => new Request(`http://127.0.0.1:3101${rule.path}${rule.search || ""}`,
      { method: rule.method, headers: who ? { [HEADER]: who } : {} });
    const status = (who, rule, extra) => guard(request(who, rule), extra)?.status ?? 200;

    const open = [
      { path: "/api/review", method: "POST" }, { path: "/api/images", method: "POST" },
      { path: "/api/images/bulk", method: "POST" }, { path: "/api/images/missed", method: "POST" },
      { path: "/api/images/viewed", method: "POST" }, { path: "/api/viewed", method: "POST" },
      { path: "/api/paper", method: "GET" }, { path: "/api/media", method: "GET" },
      { path: "/api/settings", method: "GET" }, { path: "/api/images", method: "GET" },
      { path: "/api/workbench", method: "GET" }, { path: "/api/reveal", method: "GET" },
      { path: "/api/projects", method: "GET" },
    ];
    const admin = RULES.filter((r) => r.admin), forbidden = RULES.filter((r) => r.forbidden);
    assert.ok(admin.length >= 9 && forbidden.length === 1 && forbidden[0].path === "/api/reveal");
    for (const expected of ["/api/projects", "/api/settings", "/api/index", "/api/metadata", "/api/images/reference",
                            "/api/stats", "/api/draft", "/api/images/website", "/api/images/sync"]) {
      assert.ok(admin.some((r) => r.path === expected && r.method === "POST"), `${expected} POST is admin-only`);
    }
    assert.deepEqual([...ADMIN_WORKBENCH_METHODS].sort(), ["map_paper", "register_file", "register_root", "sync"]);

    // Local mode: no roles, nothing refused, whoever the header names.
    delete process.env.METASCIENCE_ACCESS_TEAM; delete process.env.METASCIENCE_ACCESS_AUD;
    for (const rule of [...RULES, ...open]) for (const who of Object.values(WHO)) {
      assert.equal(status(who, rule), 200, `local ${rule.method} ${rule.path} as ${who}`);
    }
    for (const m of ["register_root", "sync", "review"]) {
      assert.equal(status(null, { path: "/api/workbench", method: "POST" }, { workbenchMethod: m }), 200, `local workbench ${m}`);
    }

    // Hosted mode.
    process.env.METASCIENCE_ACCESS_TEAM = "unit-test-team"; process.env.METASCIENCE_ACCESS_AUD = "a".repeat(64);
    for (const rule of [...RULES, ...open]) {
      assert.equal(status(WHO.anonymous, rule), 401, `hosted ${rule.method} ${rule.path} anonymous`);
      assert.equal(status(WHO.admin, rule), rule.forbidden ? 403 : 200, `hosted ${rule.method} ${rule.path} admin`);
      for (const who of [WHO.reviewer, WHO.unknown]) {
        assert.equal(status(who, rule), rule.admin || rule.forbidden ? 403 : 200, `hosted ${rule.method} ${rule.path} as ${who}`);
      }
    }
    const wb = { path: "/api/workbench", method: "POST" };
    for (const m of ["register_root", "map_paper", "register_file", "sync"]) {
      assert.equal(status(WHO.reviewer, wb, { workbenchMethod: m }), 403, `workbench ${m} reviewer`);
      assert.equal(status(WHO.admin, wb, { workbenchMethod: m }), 200, `workbench ${m} admin`);
      assert.equal(status(WHO.anonymous, wb, { workbenchMethod: m }), 401, `workbench ${m} anonymous`);
    }
    for (const m of ["review", "video_generate"]) {
      assert.equal(status(WHO.reviewer, wb, { workbenchMethod: m }), 200, `workbench ${m} reviewer`);
    }
    assert.equal(status(WHO.reviewer, wb), 200, "workbench POST before the method is known: identity only");

    // The table is keyed by exact path and method: a trailing slash or a
    // different method does not widen it, and the refusal bodies are JSON.
    assert.deepEqual(policyFor(new Request("http://x/api/reveal/", { method: "POST" })), { admin: false, forbidden: true });
    assert.deepEqual(policyFor(new Request("http://x/api/reveal", { method: "GET" })), { admin: false, forbidden: false });
    assert.deepEqual(policyFor(new Request("http://x/api/settings?x=1", { method: "POST" })), { admin: true, forbidden: false });
    const refused = guard(request(WHO.reviewer, { path: "/api/settings", method: "POST" }));
    assert.deepEqual(await refused.json(), { error: "Admin only" });
    const anon = guard(request(null, { path: "/api/paper", method: "GET" }));
    assert.deepEqual(await anon.json(), { error: "Sign in through Cloudflare Access" });
    const gone = guard(request(WHO.admin, { path: "/api/reveal", method: "POST" }));
    assert.deepEqual(await gone.json(), { error: "Not available in hosted mode" });
  } finally {
    for (const k of Object.keys(process.env)) if (!(k in before)) delete process.env[k];
    Object.assign(process.env, before);
    fs.rmSync(scratch, { recursive: true, force: true });
  }
});
