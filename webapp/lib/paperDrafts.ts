import "server-only";

import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";

import { xmlEmails } from "./emails.ts";

/** A paper's email and PubPeer-comment drafts: `drafts.py` makes them as a
 *  background job (the model calls take minutes, longer than a request
 *  through the tunnel may last); this side starts the job, reads its
 *  progress and the drafts it wrote, and saves a reviewer's edits.
 *  Nothing here sends or posts anything. */
export const DRAFTS_DIR = "drafts";
export const KINDS = ["email", "pubpeer"] as const;
export type DraftKind = (typeof KINDS)[number];
export const isKind = (k: unknown): k is DraftKind => KINDS.includes(k as DraftKind);

/** A job that has not written its first progress in this long never started. */
const START_GRACE_MS = 90_000;
const NAME = /^(email|pubpeer)-\d{8}-\d{6}\.json$/;

export interface JobStep { name: string; status: "pending" | "running" | "done" | "warning" | "error"; detail: string }
export interface DraftJob {
  kind: DraftKind;
  state: "starting" | "running" | "done" | "error";
  pid?: number | null;
  started_at?: string;
  finished_at?: string;
  steps: JobStep[];
  result?: string;
  error?: string;
}

export interface Contact {
  name: string; role: string; email: string; source_url: string;
  verified: boolean; check: string; selected: boolean;
}
export interface AuthorAddress { email: string; selected: boolean; corresponding?: boolean; added?: boolean }
export interface Draft {
  name: string;
  kind: DraftKind;
  created_at: string;
  who: string;
  model: string;
  paper: { title?: string; doi?: string; journal?: string; handling_editor?: string };
  to: Contact[];
  cc: AuthorAddress[];
  subject: string;
  body: string;
  repo_url: string;
  repo_visibility: string;
  contacts_note: string;
  /** Marked by the reviewer once they sent the email or posted the comment. */
  sent: { at: string; by: string } | null;
  edited?: { at: string; by: string };
}

export const jobFile = (paperAbs: string, kind: DraftKind) => path.join(paperAbs, DRAFTS_DIR, `job-${kind}.json`);

const pidAlive = (pid: unknown): boolean => {
  if (typeof pid !== "number" || pid <= 0) return false;
  try { process.kill(pid, 0); return true; } catch (e) { return (e as NodeJS.ErrnoException).code === "EPERM"; }
};

async function readJson<T>(file: string): Promise<T | null> {
  try { return JSON.parse(await fsp.readFile(file, "utf8")) as T; } catch { return null; }
}

async function writeJson(file: string, data: unknown): Promise<void> {
  await fsp.mkdir(path.dirname(file), { recursive: true });
  const tmp = `${file}.${randomBytes(6).toString("hex")}.tmp`;
  await fsp.writeFile(tmp, JSON.stringify(data, null, 2) + "\n", "utf8");
  try { await fsp.rename(tmp, file); } catch (e) { await fsp.rm(tmp, { force: true }); throw e; }
}

/** The job's progress, with a job whose process is gone reported as failed. */
export async function readJob(paperAbs: string, kind: DraftKind, now = Date.now(), alive = pidAlive): Promise<DraftJob | null> {
  const job = await readJson<DraftJob>(jobFile(paperAbs, kind));
  if (!job || typeof job !== "object") return null;
  if (job.state === "running" && !alive(job.pid)) {
    return { ...job, state: "error", error: job.error || "The drafting job stopped before it finished" };
  }
  if (job.state === "starting" && now - Date.parse(job.started_at || "") > START_GRACE_MS) {
    return { ...job, state: "error", error: "The drafting job did not start" };
  }
  return { ...job, kind };
}

export const busy = (job: DraftJob | null) => job?.state === "starting" || job?.state === "running";

/** Every draft in the paper folder, newest first. */
export async function listDrafts(paperAbs: string): Promise<Draft[]> {
  const names = await fsp.readdir(path.join(paperAbs, DRAFTS_DIR)).catch(() => [] as string[]);
  const out: Draft[] = [];
  for (const name of names.filter((n) => NAME.test(n)).sort().reverse()) {
    const d = await readJson<Omit<Draft, "name">>(path.join(paperAbs, DRAFTS_DIR, name));
    if (d && typeof d === "object") out.push({ ...d, name, kind: name.startsWith("email") ? "email" : "pubpeer" } as Draft);
  }
  return out;
}

/** The author addresses in the paper's publisher XML, if it has one. */
export async function paperXmlAddresses(paperAbs: string): Promise<string[]> {
  const own = path.join(paperAbs, `${path.basename(paperAbs)}.xml`);
  const file = fs.existsSync(own) ? own
    : (await fsp.readdir(paperAbs).catch(() => [] as string[])).filter((n) => n.endsWith(".xml")).sort()
      .map((n) => path.join(paperAbs, n))[0];
  if (!file) return [];
  return xmlEmails(await fsp.readFile(file, "utf8"));
}

export interface JobOptions {
  kind: DraftKind;
  authors: string[];
  who: string;
  repoUrl: string;
  repoVisibility: string;
  contactsDir: string;
  exclude: string[];
}

const ADDRESS = /^[^\s@,]+@[^\s@,]+\.[A-Za-z]{2,}$/;
const ID = /^[\w.:-]{1,80}$/;

/** The argv after the Python binary. Addresses and finding ids are checked
 *  here: the list is passed comma-separated. */
export function jobArgv(paperAbs: string, o: JobOptions): string[] {
  return [
    "-m", "forensic_metascience_ai_toolkit.drafts", paperAbs,
    "--kind", o.kind,
    "--authors", o.authors.filter((a) => ADDRESS.test(a)).join(","),
    "--who", o.who.replace(/[\r\n]+/g, " ").slice(0, 80),
    "--repo-url", /^https:\/\/github\.com\/[\w.-]+\/[\w.-]+$/.test(o.repoUrl) ? o.repoUrl : "",
    "--repo-visibility", /^[A-Z]+$/.test(o.repoVisibility) ? o.repoVisibility : "",
    "--contacts-dir", o.contactsDir,
    "--exclude", o.exclude.filter((x) => ID.test(x)).join(","),
  ];
}

export type Spawner = (argv: string[], logFile: string) => number | undefined;

/** Start a drafting job in the background. Refused while one of the same
 *  kind is under way for this paper. */
export async function startJob(paperAbs: string, o: JobOptions, launch: Spawner): Promise<DraftJob> {
  const current = await readJob(paperAbs, o.kind);
  if (busy(current)) throw new Error(o.kind === "email" ? "An email is already being drafted for this paper" : "A PubPeer comment is already being drafted for this paper");
  const steps = (o.kind === "email" ? ["authors", "contacts", "draft"] : ["authors", "draft"])
    .map((name) => ({ name, status: "pending" as const, detail: "" }));
  // Written before the process exists, so a poll never reads the last job's
  // result as this one's; the job then writes its own progress over it.
  const job: DraftJob = { kind: o.kind, state: "starting", pid: null, started_at: new Date().toISOString(), steps };
  await writeJson(jobFile(paperAbs, o.kind), job);
  try {
    launch(jobArgv(paperAbs, o), path.join(paperAbs, DRAFTS_DIR, `job-${o.kind}.log`));
  } catch (e) {
    const failed = { ...job, state: "error" as const, error: `The drafting job could not start: ${e instanceof Error ? e.message : e}` };
    await writeJson(jobFile(paperAbs, o.kind), failed);
    return failed;
  }
  return job;
}

/** Runs the job detached from this server, its output to a log file. */
export function detachedPython(python: string, cwd: string, env: NodeJS.ProcessEnv): Spawner {
  return (argv, logFile) => {
    const fd = fs.openSync(logFile, "a");
    try {
      const child = spawn(python, argv, { cwd, env, detached: true, stdio: ["ignore", fd, fd], windowsHide: true });
      child.on("error", () => { /* reported by the job file never leaving "starting" */ });
      child.unref();
      return child.pid;
    } finally { fs.closeSync(fd); }
  };
}

export interface DraftEdit {
  to?: { email: string; selected: boolean }[];
  cc?: { email: string; selected: boolean }[];
  subject?: string;
  body?: string;
  /** true marks the draft sent or posted; false clears the mark. */
  sent?: boolean;
}

/** Save a reviewer's edits to one draft. Only the recipients' ticks, added
 *  addresses, subject, body and the sent mark change. */
export async function saveDraft(paperAbs: string, name: string, edit: DraftEdit, who: string): Promise<Draft> {
  if (!NAME.test(name)) throw new Error("No such draft");
  const file = path.join(paperAbs, DRAFTS_DIR, name);
  const d = await readJson<Draft>(file);
  if (!d) throw new Error("No such draft");
  const by = who || "unknown";
  const at = new Date().toISOString();
  const ticks = (rows: { email: string; selected: boolean }[] | undefined) =>
    new Map((rows || []).filter((r) => typeof r?.email === "string").map((r) => [r.email.trim().toLowerCase(), !!r.selected]));
  if (edit.to) {
    const t = ticks(edit.to);
    d.to = d.to.map((c) => ({ ...c, selected: t.get(c.email) ?? c.selected }));
  }
  if (edit.cc) {
    const t = ticks(edit.cc);
    const known = new Set(d.cc.map((c) => c.email));
    d.cc = d.cc.map((c) => ({ ...c, selected: t.get(c.email) ?? c.selected }));
    for (const [email, selected] of t) {
      if (known.has(email)) continue;
      if (!ADDRESS.test(email)) throw new Error(`Not an email address: ${email.slice(0, 80)}`);
      d.cc.push({ email, selected, added: true });
    }
  }
  if (typeof edit.subject === "string") d.subject = edit.subject.slice(0, 500);
  if (typeof edit.body === "string") {
    if (edit.body.length > 50_000) throw new Error("The draft is too long");
    d.body = edit.body;
  }
  if (edit.to || edit.cc || typeof edit.subject === "string" || typeof edit.body === "string") d.edited = { at, by };
  if (edit.sent === true) d.sent = { at, by };
  if (edit.sent === false) d.sent = null;
  const { name: _omit, ...stored } = d as Draft & { name?: string };
  void _omit;
  await writeJson(file, stored);
  return { ...d, name };
}
