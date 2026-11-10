// Access control: the route table × anonymous / unknown / reviewer / admin ×
// local / hosted, per-project assignment, and which names are projects at
// all (lib/projectSources.ts). The real directory lookup runs against a
// scratch settings file; the workbench service is a recorder.
import { afterAll, beforeAll, test, vi } from "vitest";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const calls = [];
let catalogRoots = [];
vi.mock("../lib/workbench.ts", () => ({
  workbench: async (method, params) => {
    calls.push({ method, params });
    if (method === "roots") return { roots: catalogRoots };
    return { ok: true };
  },
}));

const HEADER = "x-ms-reviewer-email";
const WHO = { anonymous: null, reviewer: "rev@example.org", unknown: "stranger@example.org", admin: "dan@example.org" };
const before = { ...process.env };
let scratch, file;

beforeAll(() => {
  scratch = fs.mkdtempSync(path.join(os.tmpdir(), "workbench-guard-"));
  file = path.join(scratch, "settings.json");
  process.env.METASCIENCE_SETTINGS_FILE = file;
});
afterAll(() => {
  for (const k of Object.keys(process.env)) if (!(k in before)) delete process.env[k];
  Object.assign(process.env, before);
  fs.rmSync(scratch, { recursive: true, force: true });
});

const writeSettings = (extra = {}) => fs.writeFileSync(file, JSON.stringify({ papers_root: scratch, reviewers: [
  { email: "dan@example.org", name: "Dan Elton", role: "admin" },
  { email: "rev@example.org", name: "Second Reviewer", role: "reviewer", projects: ["alpha"] }], ...extra }));
const hosted = (on) => {
  if (on) { process.env.METASCIENCE_ACCESS_TEAM = "unit-test-team"; process.env.METASCIENCE_ACCESS_AUD = "a".repeat(64); }
  else { delete process.env.METASCIENCE_ACCESS_TEAM; delete process.env.METASCIENCE_ACCESS_AUD; }
};

test("routeGuard matrix: roles and route rules", async () => {
  writeSettings();
  const { ADMIN_WORKBENCH_METHODS, ADMIN_WORKBENCH_READS, RULES, guard, policyFor } = await import("../lib/routeGuard.ts");
  const request = (who, rule) => new Request(`http://127.0.0.1:3101${rule.path}`,
    { method: rule.method, headers: who ? { [HEADER]: who } : {} });
  const status = async (who, rule, need) => (await guard(request(who, rule), need))?.status ?? 200;

  const open = [
    { path: "/api/review", method: "POST" }, { path: "/api/images", method: "POST" },
    { path: "/api/images/bulk", method: "POST" }, { path: "/api/images/missed", method: "POST" },
    { path: "/api/images/viewed", method: "POST" }, { path: "/api/viewed", method: "POST" },
    { path: "/api/paper", method: "GET" }, { path: "/api/media", method: "GET" },
    { path: "/api/settings", method: "GET" }, { path: "/api/images", method: "GET" },
    { path: "/api/workbench", method: "GET" }, { path: "/api/reveal", method: "GET" },
  ];
  const rules = RULES.map((r) => (r.prefix ? { ...r, path: `${r.path}users` } : r));
  const admin = rules.filter((r) => r.admin), forbidden = rules.filter((r) => r.forbidden);
  assert.ok(forbidden.length === 1 && forbidden[0].path === "/api/reveal");
  for (const expected of ["/api/projects", "/api/settings", "/api/index", "/api/metadata", "/api/images/reference",
                          "/api/stats", "/api/draft", "/api/images/website", "/api/images/sync"]) {
    assert.ok(admin.some((r) => r.path === expected && r.method === "POST"), `${expected} POST is admin-only`);
  }
  for (const expected of ["/api/projects", "/api/admin/users"]) {
    assert.ok(admin.some((r) => r.path === expected && r.method === "GET"), `${expected} GET is admin-only`);
  }
  assert.deepEqual([...ADMIN_WORKBENCH_METHODS].sort(), ["map_paper", "register_file", "register_root", "sync"]);
  assert.deepEqual([...ADMIN_WORKBENCH_READS].sort(), ["projects", "roots"]);

  // Local mode: no roles, nothing refused, whoever the header names.
  hosted(false);
  for (const rule of [...rules, ...open]) for (const who of Object.values(WHO)) {
    assert.equal(await status(who, rule), 200, `local ${rule.method} ${rule.path} as ${who}`);
  }

  // Hosted mode.
  hosted(true);
  for (const rule of [...rules, ...open]) {
    assert.equal(await status(WHO.anonymous, rule), 401, `hosted ${rule.method} ${rule.path} anonymous`);
    assert.equal(await status(WHO.unknown, rule), 403, `hosted ${rule.method} ${rule.path} unknown email`);
    assert.equal(await status(WHO.admin, rule), rule.forbidden ? 403 : 200, `hosted ${rule.method} ${rule.path} admin`);
    assert.equal(await status(WHO.reviewer, rule), rule.admin || rule.forbidden ? 403 : 200, `hosted ${rule.method} ${rule.path} reviewer`);
  }
  const wbPost = { path: "/api/workbench", method: "POST" }, wbGet = { path: "/api/workbench", method: "GET" };
  for (const m of ADMIN_WORKBENCH_METHODS) {
    assert.equal(await status(WHO.reviewer, wbPost, { workbenchMethod: m }), 403, `workbench ${m} reviewer`);
    assert.equal(await status(WHO.admin, wbPost, { workbenchMethod: m }), 200, `workbench ${m} admin`);
  }
  for (const m of ["projects", "roots"]) assert.equal(await status(WHO.reviewer, wbGet, { workbenchMethod: m }), 403, `read ${m} reviewer`);
  assert.equal(await status(WHO.reviewer, wbGet, { workbenchMethod: "status" }), 200, "status is open");
  assert.equal(await status(WHO.reviewer, wbPost, { workbenchMethod: "review", project: "alpha" }), 200);

  // Per-project: assigned only; a scoped route with no project is a
  // reviewer's 400 and an admin's pass.
  const paper = { path: "/api/paper", method: "GET" };
  assert.equal(await status(WHO.reviewer, paper, { project: "alpha" }), 200);
  assert.equal(await status(WHO.reviewer, paper, { project: "beta" }), 403);
  assert.equal(await status(WHO.reviewer, paper, { project: undefined }), 400);
  assert.equal(await status(WHO.reviewer, paper, { project: "" }), 400);
  assert.equal(await status(WHO.admin, paper, { project: "beta" }), 200);
  assert.equal(await status(WHO.admin, paper, { project: "" }), 200);
  assert.equal(await status(WHO.unknown, paper, { project: "alpha" }), 403);
  assert.deepEqual(await (await guard(request(WHO.reviewer, paper), { project: "beta" })).json(),
    { error: "You do not have access to this project" });

  // Exact path and method; HEAD reads as GET; refusal bodies are JSON.
  assert.deepEqual(policyFor(new Request("http://x/api/reveal/", { method: "POST" })), { admin: false, forbidden: true });
  assert.deepEqual(policyFor(new Request("http://x/api/reveal", { method: "GET" })), { admin: false, forbidden: false });
  assert.deepEqual(policyFor(new Request("http://x/api/settings?x=1", { method: "POST" })), { admin: true, forbidden: false });
  assert.deepEqual(policyFor(new Request("http://x/api/projects", { method: "HEAD" })), { admin: true, forbidden: false });
  assert.deepEqual(policyFor(new Request("http://x/api/administrator", { method: "GET" })), { admin: false, forbidden: false }, "prefix is a path segment");
  assert.deepEqual(await (await guard(request(WHO.reviewer, { path: "/api/settings", method: "POST" }))).json(), { error: "Admin only" });
  assert.deepEqual(await (await guard(request(null, paper))).json(), { error: "Sign in through Cloudflare Access" });
  assert.match((await (await guard(request(WHO.unknown, paper))).json()).error, /not set up/);
  assert.deepEqual(await (await guard(request(WHO.admin, { path: "/api/reveal", method: "POST" }))).json(), { error: "Not available in hosted mode" });
});

test("project sources decide which names are projects", async () => {
  const papers = path.join(scratch, "papers"), elsewhere = path.join(scratch, "elsewhere", "g");
  for (const d of ["alpha", "beta", "_hidden", "_hidden/batch", "leads/lead_a", "fresh", ".git", "done", "alpha/analysis_sessions/x/corpus"]) fs.mkdirSync(path.join(papers, d), { recursive: true });
  fs.mkdirSync(elsewhere, { recursive: true });
  fs.writeFileSync(path.join(papers, "notes.html"), "");
  fs.symlinkSync(elsewhere, path.join(papers, "linked"));
  catalogRoots = [
    { project: "alpha__session", path: path.join(papers, "alpha/analysis_sessions/x/corpus"), available: true },
    { project: "alpha", path: path.join(papers, "alpha"), available: true },
    { project: "beta", path: path.join(papers, "beta"), available: true },
    { project: "collection", path: papers, available: true },
    { project: "_hidden", path: path.join(papers, "_hidden"), available: true },
    { project: "batch", path: path.join(papers, "_hidden/batch"), available: true },
    { project: "lead_a", path: path.join(papers, "leads/lead_a"), available: true },
    { project: "gone", path: path.join(papers, "gone"), available: false },
    { project: "pytest-600", path: path.join(scratch, "tmp-run"), available: false },
  ];
  writeSettings({ project_sources: { roots: [papers, path.join(scratch, "missing")],
    folders: [{ name: "gamma", path: elsewhere }], database: ["delta"] } });
  const { invalidateSources, sourceView, resolveSources } = await import("../lib/projectSources.ts");
  const { guard } = await import("../lib/routeGuard.ts");
  invalidateSources(); calls.length = 0;
  const view = await sourceView();
  assert.deepEqual([...view.projects.keys()].sort(), ["alpha", "alpha__session", "beta", "delta", "fresh", "gamma", "lead_a"],
    "a folder of projects (leads/) is not itself one; alpha holds a session corpus but is registered, so it stays");
  assert.deepEqual(view.missingRoots, [path.join(scratch, "missing")]);
  assert.equal(view.projects.get("delta").database, true);
  assert.equal(view.projects.get("gamma").folders[0].via, "folder");
  // New (name, folder) pairs are registered with the service; known ones are not.
  assert.deepEqual(calls.filter((c) => c.method === "register_root").map((c) => c.params.project).sort(), ["fresh", "gamma"], "a new subfolder is registered; known pairs are not");

  // Same name in two places is one project with two folders, never silently one.
  const twice = resolveSources({ roots: [papers], folders: [{ name: "alpha", path: elsewhere }], database: [] }, [], () => ["alpha"], () => true);
  assert.equal(twice.projects.get("alpha").folders.length, 2);

  hosted(true);
  const req = (who) => new Request("http://127.0.0.1:3101/api/paper", { headers: { [HEADER]: who } });
  assert.equal(await guard(req(WHO.admin), { project: "alpha" }), null);
  assert.equal((await guard(req(WHO.admin), { project: "pytest-600" }))?.status, 404, "an unsourced name is not reachable, even by an admin");
  assert.equal((await guard(req(WHO.admin), { project: "collection" }))?.status, 404, "a root AT the watched folder is not a project");
  assert.equal(await guard(req(WHO.reviewer), { project: "alpha" }), null);
  assert.equal((await guard(req(WHO.reviewer), { project: "delta" }))?.status, 403);
  hosted(false);
  assert.equal((await guard(req(WHO.admin), { project: "pytest-600" }))?.status, 404, "local mode too");
  assert.equal(await guard(req(WHO.admin), { project: "delta" }), null);
});

test("every API route handler calls the guard", () => {
  // `/api/me` answers identity questions itself and touches no project.
  const exempt = new Set(["app/api/me/route.ts"]);
  const routes = fs.globSync("app/api/**/route.ts");
  assert.ok(routes.length >= 25);
  for (const file of routes) {
    if (exempt.has(file)) continue;
    const src = fs.readFileSync(file, "utf8");
    const handlers = [...src.matchAll(/export async function (GET|POST|HEAD|PUT|DELETE|PATCH)\b/g)].map((m) => m[1]);
    assert.ok(handlers.length, `${file} exports a handler`);
    for (const h of handlers) {
      const start = src.indexOf(`export async function ${h}`);
      const next = src.slice(start + 1).search(/\nexport async function /);
      const body = next < 0 ? src.slice(start) : src.slice(start, start + 1 + next);
      // HEAD may delegate to the shared server function GET uses.
      const delegated = /return serve\(req/.test(body) && /await guard\(req/.test(src);
      assert.ok(/await guard\(/.test(body) || delegated, `${file} ${h} calls guard`);
    }
  }
});
