import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, test } from "vitest";

import { gmailUrl, mailtoUrl, pubpeerSearchUrl, ticked } from "../lib/draftLinks.ts";
import {
  jobArgv, jobFile, listDrafts, paperXmlAddresses, readJob, saveDraft, startJob,
} from "../lib/paperDrafts.ts";

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "paper-drafts-"));
afterAll(() => fs.rmSync(tmp, { recursive: true, force: true }));
const paper = (name = "10.1--x") => {
  const p = fs.mkdtempSync(path.join(tmp, "p-"));
  const dir = path.join(p, name);
  fs.mkdirSync(path.join(dir, "drafts"), { recursive: true });
  return dir;
};
const writeJson = (file, data) => fs.writeFileSync(file, JSON.stringify(data));
const OPTS = {
  kind: "email", authors: ["a@uni.edu", "not an address", "b@x.org,c@y.org"], who: "Dan\nElton",
  repoUrl: "https://github.com/Org/Repo-1", repoVisibility: "PRIVATE", contactsDir: "/srv/proj",
  exclude: ["f_1", "bad id;rm"],
};

test("the job argv keeps only well-formed addresses, ids and a GitHub URL", () => {
  const argv = jobArgv("/srv/proj/10.1--x", OPTS);
  const opt = (k) => argv[argv.indexOf(k) + 1];
  assert.deepEqual(argv.slice(0, 3), ["-m", "forensic_metascience_ai_toolkit.drafts", "/srv/proj/10.1--x"]);
  assert.equal(opt("--authors"), "a@uni.edu", "a comma would split one entry into two addresses");
  assert.equal(opt("--who"), "Dan Elton");
  assert.equal(opt("--exclude"), "f_1");
  assert.equal(opt("--repo-url"), "https://github.com/Org/Repo-1");
  assert.equal(jobArgv("/p", { ...OPTS, repoUrl: "https://evil.example/x" }).includes("https://evil.example/x"), false);
});

test("starting a job writes 'starting' first, launches it, and refuses a second", async () => {
  const dir = paper();
  const launched = [];
  const job = await startJob(dir, OPTS, (argv, log) => { launched.push({ argv, log }); return 4242; });
  assert.equal(job.state, "starting");
  assert.deepEqual(job.steps.map((s) => s.name), ["authors", "contacts", "draft"]);
  assert.equal(launched.length, 1);
  assert.equal(launched[0].log, path.join(dir, "drafts", "job-email.log"));
  assert.equal((await readJob(dir, "email")).state, "starting");
  await assert.rejects(startJob(dir, OPTS, () => 1), /already being drafted/);
  // The other kind is independent.
  const pp = await startJob(dir, { ...OPTS, kind: "pubpeer" }, () => 1);
  assert.deepEqual(pp.steps.map((s) => s.name), ["authors", "draft"]);
});

test("a job that cannot launch is recorded as failed", async () => {
  const dir = paper();
  const job = await startJob(dir, OPTS, () => { throw new Error("ENOENT python"); });
  assert.equal(job.state, "error");
  assert.match((await readJob(dir, "email")).error, /could not start: ENOENT python/);
});

test("a running job whose process is gone, or one that never started, reads as failed", async () => {
  const dir = paper();
  writeJson(jobFile(dir, "email"), { state: "running", pid: 99, steps: [] });
  assert.equal((await readJob(dir, "email", Date.now(), () => true)).state, "running");
  const dead = await readJob(dir, "email", Date.now(), () => false);
  assert.equal(dead.state, "error");
  assert.match(dead.error, /stopped before it finished/);
  writeJson(jobFile(dir, "email"), { state: "starting", started_at: new Date(Date.now() - 120_000).toISOString(), steps: [] });
  assert.match((await readJob(dir, "email")).error, /did not start/);
  assert.equal(await readJob(paper(), "pubpeer"), null);
});

const DRAFT = {
  kind: "email", created_at: "2026-11-17T10:00:00Z", who: "Dan", model: "opus", paper: { doi: "10.1/x" },
  to: [{ name: "Ed", role: "editorial office", email: "ed@j.org", source_url: "https://j.org", verified: true, check: "", selected: true },
       { name: "Guess", role: "other", email: "g@j.org", source_url: "", verified: false, check: "", selected: false }],
  cc: [{ email: "a@uni.edu", selected: true, corresponding: true }],
  subject: "S", body: "B", repo_url: "", repo_visibility: "", contacts_note: "", sent: null,
};

test("drafts are listed newest first; stray files are ignored", async () => {
  const dir = paper();
  writeJson(path.join(dir, "drafts", "email-20261117-100000.json"), DRAFT);
  writeJson(path.join(dir, "drafts", "pubpeer-20261117-110000.json"), { ...DRAFT, kind: "pubpeer" });
  fs.writeFileSync(path.join(dir, "drafts", "letter-20250101-000000.md"), "old");
  writeJson(path.join(dir, "drafts", "job-email.json"), { state: "done" });
  const all = await listDrafts(dir);
  assert.deepEqual(all.map((d) => d.name), ["pubpeer-20261117-110000.json", "email-20261117-100000.json"]);
});

test("saving edits ticks, adds an address, and marks the draft sent", async () => {
  const dir = paper();
  const name = "email-20261117-100000.json";
  writeJson(path.join(dir, "drafts", name), DRAFT);
  const d = await saveDraft(dir, name, {
    to: [{ email: "ed@j.org", selected: false }, { email: "g@j.org", selected: true }],
    cc: [{ email: "a@uni.edu", selected: true }, { email: "New@Uni.edu", selected: true }],
    subject: "S2", body: "B2", sent: true,
  }, "Remy");
  assert.deepEqual(d.to.map((c) => c.selected), [false, true]);
  assert.deepEqual(d.cc.map((c) => c.email), ["a@uni.edu", "new@uni.edu"]);
  assert.equal(d.subject, "S2");
  assert.equal(d.sent.by, "Remy");
  assert.equal(d.edited.by, "Remy");
  const stored = JSON.parse(fs.readFileSync(path.join(dir, "drafts", name), "utf8"));
  assert.equal(stored.body, "B2");
  assert.equal("name" in stored, false);
  assert.equal(stored.to[0].verified, true, "fields the reviewer does not edit stay");
  assert.equal((await saveDraft(dir, name, { sent: false }, "Remy")).sent, null);
  await assert.rejects(saveDraft(dir, name, { cc: [{ email: "nope", selected: true }] }, "R"), /Not an email address/);
  await assert.rejects(saveDraft(dir, "../../etc/passwd", {}, "R"), /No such draft/);
  await assert.rejects(saveDraft(dir, "email-20991231-000000.json", {}, "R"), /No such draft/);
});

test("author addresses are read from the paper's own XML", async () => {
  const dir = paper("10.2--y");
  fs.writeFileSync(path.join(dir, "10.2--y.xml"), "<article><email>yan@uni.edu</email><email>Zhu@Uni.edu</email></article>");
  assert.deepEqual(await paperXmlAddresses(dir), ["yan@uni.edu", "zhu@uni.edu"]);
  assert.deepEqual(await paperXmlAddresses(paper()), []);
});

test("mail links carry the ticked recipients, subject and body", () => {
  const to = ticked([{ email: "ed@j.org", selected: true }, { email: "g@j.org", selected: false }]);
  assert.deepEqual(to, ["ed@j.org"]);
  const m = mailtoUrl(to, ["a@uni.edu", "b@uni.edu"], "Figure 5 & data", "Line 1\nLine 2");
  assert.equal(m, "mailto:ed%40j.org?cc=a%40uni.edu,b%40uni.edu&subject=Figure%205%20%26%20data&body=Line%201%0D%0ALine%202");
  const g = new URL(gmailUrl(to, ["a@uni.edu"], "S", "B"));
  assert.equal(g.searchParams.get("to"), "ed@j.org");
  assert.equal(g.searchParams.get("cc"), "a@uni.edu");
  assert.equal(g.searchParams.get("su"), "S");
  assert.equal(pubpeerSearchUrl("10.1002/acn3.51800"), "https://pubpeer.com/search?q=10.1002%2Facn3.51800");
});
