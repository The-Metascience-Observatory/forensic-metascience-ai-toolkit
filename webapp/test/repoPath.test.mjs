import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import vm from "node:vm";
import ts from "typescript";
import { test } from "vitest";

// GET /api/repo sends the paper folder's path on the server to an admin (and
// in local mode, where `requireAdmin` lets everyone through), never to a
// hosted reviewer.
test("the paper folder's path is in the answer for admins only", async () => {
  const source = readFileSync(new URL("../app/api/repo/route.ts", import.meta.url), "utf8");
  const code = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  let admin = true;
  const endpoint = {};
  vm.runInNewContext(code, { exports: endpoint, URL, Response, require: (name) => ({
    "@/lib/auth": { requireAdmin: () => (admin ? null : Response.json({ error: "Admin only" }, { status: 403 })) },
    "@/lib/err": { jsonError: (e) => Response.json({ error: String(e) }, { status: 400 }) },
    "@/lib/routeGuard": { guard: async () => null },
    "@/lib/repoInfo": {
      paperRepo: async () => ({ paperAbs: "/srv/papers/proj/10.1--x", repoAbs: null }),
      repoInfo: async () => ({ repo: null, readme: null, sha256: null, summary_md: "", triage_md: "", embargoed: false }),
    },
  }[name]) });
  const get = async () => (await endpoint.GET(new Request("http://localhost:3100/api/repo?project=proj&dir=10.1--x"))).json();
  assert.equal((await get()).paper_path, "/srv/papers/proj/10.1--x");
  admin = false;
  const reviewer = await get();
  assert.equal("paper_path" in reviewer, false);
  assert.equal(reviewer.triage_md, "", "the rest of the answer still arrives");
});
