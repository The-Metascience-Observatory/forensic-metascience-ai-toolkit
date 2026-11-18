import "server-only";

import { execFile } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import fs from "node:fs";
import fsp from "node:fs/promises";
import path from "node:path";

import { contained } from "./paths.ts";

/** A paper's reproduction repository: the git repo an agent built inside the
 *  paper folder and pushed, privately, to the reproductions organisation.
 *
 *  Everything that runs `git` or `gh` goes through a `Run` passed in, with an
 *  argv array and no shell, so tests pin the commands without running them
 *  (the pattern of `lib/reveal.ts`). */
export const ORG = "Metascience-Observatory-Reproductions";
export const README = "README.md";
export const TRIAGE_NOTE = "rng_triage.md";
export const VISIBILITY_LOG = "REPO_VISIBILITY.tsv";
const MAX_README_BYTES = 400_000;

export type Run = (argv: string[], opts?: { cwd?: string; timeoutMs?: number }) => Promise<string>;

/** Runs one command and returns its stdout. A failure carries the command's
 *  own stderr, which is what says why a push or a visibility change failed. */
export const runCommand: Run = (argv, opts = {}) =>
  new Promise((resolve, reject) => {
    execFile(argv[0], argv.slice(1), {
      cwd: opts.cwd, timeout: opts.timeoutMs ?? 30_000, maxBuffer: 4 * 1024 * 1024, windowsHide: true,
      env: { ...process.env, GIT_TERMINAL_PROMPT: "0", GH_PROMPT_DISABLED: "1" },
    }, (error, stdout, stderr) => {
      if (error) reject(new Error(`${argv.slice(0, 3).join(" ")}: ${String(stderr || error.message).trim().slice(0, 1500)}`));
      else resolve(String(stdout));
    });
  });

export type Visibility = "PRIVATE" | "PUBLIC" | "INTERNAL" | "unknown";

export interface RepoState {
  name: string;
  /** `https://github.com/<owner>/<name>`, or `""` with no remote. */
  url: string;
  hasRemote: boolean;
  /** The remote is a repository of the reproductions organisation. */
  inOrg: boolean;
  readmeDirty: boolean;
  /** Changed or untracked paths other than the README. */
  otherDirty: string[];
  /** Commits not yet on the remote; `null` when the branch tracks nothing. */
  ahead: number | null;
}

/** `{owner, name}` of a GitHub remote URL (https or ssh), else `null`. */
export function githubSlug(remote: string): { owner: string; name: string } | null {
  const m = /github\.com[:/]([^/\s]+)\/([^/\s]+?)(?:\.git)?\/?\s*$/.exec(remote.trim());
  return m ? { owner: m[1], name: m[2] } : null;
}

/** The one subfolder of the paper folder that is a git repository (the rule
 *  `check_repo.py` uses), or `null`. A symlinked folder is never followed. */
export async function findRepo(paperAbs: string): Promise<string | null> {
  const entries = await fsp.readdir(paperAbs, { withFileTypes: true });
  const repos: string[] = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || entry.name.startsWith(".")) continue;
    if (fs.existsSync(path.join(paperAbs, entry.name, ".git"))) repos.push(entry.name);
  }
  if (repos.length > 1) throw new Error(`This paper folder holds ${repos.length} git repositories; one is expected: ${repos.sort().join(", ")}`);
  if (!repos.length) return null;
  const abs = await fsp.realpath(path.join(paperAbs, repos[0]));
  if (!contained(await fsp.realpath(paperAbs), abs)) throw new Error("The repository is outside the paper folder");
  return abs;
}

/** The paths `git status --porcelain` lists (a rename gives its new path). */
export function dirtyPaths(porcelain: string): string[] {
  return porcelain.split("\n").filter((line) => line.length > 3)
    .map((line) => line.slice(3).split(" -> ").pop()!.replace(/^"|"$/g, ""));
}

export async function repoState(repoAbs: string, run: Run = runCommand): Promise<RepoState> {
  const git = (...args: string[]) => run(["git", "-C", repoAbs, ...args]);
  const dirty = dirtyPaths(await git("status", "--porcelain"));
  const remote = (await git("remote", "get-url", "origin").catch(() => "")).trim();
  const slug = githubSlug(remote);
  const ahead = await git("rev-list", "--count", "@{u}..HEAD").then((s) => Number(s.trim()), () => null);
  return {
    name: path.basename(repoAbs),
    url: slug ? `https://github.com/${slug.owner}/${slug.name}` : "",
    hasRemote: !!remote,
    inOrg: !!slug && slug.owner === ORG && slug.name === path.basename(repoAbs),
    readmeDirty: dirty.includes(README),
    otherDirty: dirty.filter((p) => p !== README),
    ahead: ahead === null || Number.isNaN(ahead) ? null : ahead,
  };
}

const seen = new Map<string, { at: number; value: Visibility }>();
const VISIBILITY_TTL_MS = 60_000;

/** The repository's visibility on GitHub, remembered for a minute. `unknown`
 *  when `gh` cannot say (offline, not signed in, no such repository). */
export async function visibility(name: string, run: Run = runCommand, fresh = false): Promise<Visibility> {
  const hit = seen.get(name);
  if (!fresh && hit && Date.now() - hit.at < VISIBILITY_TTL_MS) return hit.value;
  const value = await run(["gh", "repo", "view", `${ORG}/${name}`, "--json", "visibility", "-q", ".visibility"], { timeoutMs: 20_000 })
    .then((s) => (["PRIVATE", "PUBLIC", "INTERNAL"].includes(s.trim()) ? s.trim() as Visibility : "unknown"), () => "unknown" as const);
  if (value !== "unknown") seen.set(name, { at: Date.now(), value });
  return value;
}

export const sha256 = (text: string): string => createHash("sha256").update(text, "utf8").digest("hex");

/** The README's text and hash; `null` when the repo has none. A symlink is
 *  refused: the file read and written must be the one in the repository. */
export async function readReadme(repoAbs: string): Promise<{ text: string; sha256: string } | null> {
  const file = path.join(repoAbs, README);
  const stat = await fsp.lstat(file).catch(() => null);
  if (!stat) return null;
  if (!stat.isFile()) throw new Error("README.md is not a regular file");
  const text = await fsp.readFile(file, "utf8");
  return { text, sha256: sha256(text) };
}

/** Replace the README, but only the version the editor started from: a save
 *  over someone else's newer text is refused. Writes nothing else and runs
 *  no git command. */
export async function saveReadme(repoAbs: string, content: string, baseSha256: string): Promise<{ sha256: string }> {
  if (typeof content !== "string" || !content.trim()) throw new Error("The README is empty");
  if (Buffer.byteLength(content, "utf8") > MAX_README_BYTES) throw new Error("The README is too large");
  const current = await readReadme(repoAbs);
  if (!current) throw new Error("This repository has no README.md");
  if (current.sha256 !== baseSha256) throw new Error("The README changed on disk since you opened it. Reload it, then make your edit again.");
  const text = content.replace(/\r\n?/g, "\n");
  const tmp = path.join(repoAbs, `.README.md.${randomBytes(6).toString("hex")}.tmp`);
  await fsp.writeFile(tmp, text, "utf8");
  try { await fsp.rename(tmp, path.join(repoAbs, README)); }
  catch (e) { await fsp.rm(tmp, { force: true }); throw e; }
  return { sha256: sha256(text) };
}

const oneLine = (s: string, max = 80) => String(s || "").replace(/[\r\n\t]+/g, " ").trim().slice(0, max);

export const commitMessage = (who: string): string =>
  `README: edited in the review workbench${oneLine(who) ? ` by ${oneLine(who)}` : ""}`;

/** Commit the README (and only the README) and push the branch. */
export async function commitAndPush(repoAbs: string, who: string, run: Run = runCommand): Promise<{ committed: boolean; pushed: boolean }> {
  const state = await repoState(repoAbs, run);
  if (!state.hasRemote) throw new Error("This repository has no GitHub remote yet; the repo driver creates it");
  if (!state.inOrg) throw new Error(`The remote is not ${ORG}/${state.name}; nothing was pushed`);
  if (state.otherDirty.length) {
    throw new Error(`Other files have uncommitted changes (${state.otherDirty.slice(0, 5).join(", ")}). Only the README is committed from here, so commit or discard those first.`);
  }
  if (!state.readmeDirty && !state.ahead) throw new Error("Nothing to commit or push");
  const git = (...args: string[]) => run(["git", "-C", repoAbs, ...args], { timeoutMs: 90_000 });
  if (state.readmeDirty) {
    await git("add", "--", README);
    await git("commit", "-m", commitMessage(who), "--", README);
  }
  await git("push", "origin", "HEAD");
  return { committed: state.readmeDirty, pushed: true };
}

export const makePublicArgv = (name: string): string[] =>
  ["gh", "repo", "edit", `${ORG}/${name}`, "--visibility", "public", "--accept-visibility-change-consequences"];

export const visibilityLogLine = (r: { paper: string; url: string; who: string }, now: Date = new Date()): string =>
  [now.toISOString(), oneLine(r.paper, 200), r.url, "public", oneLine(r.who)].join("\t") + "\n";

/** Make the GitHub repository public. Refused unless the caller typed the
 *  repository's name, the tree is clean and every commit is on GitHub: what
 *  becomes public must be what the reviewer has just been reading. */
export async function makePublic(
  repoAbs: string, confirmName: string, who: string, logDir: string | null, run: Run = runCommand,
): Promise<{ visibility: Visibility; url: string }> {
  const state = await repoState(repoAbs, run);
  if (String(confirmName || "").trim() !== state.name) throw new Error("The name typed does not match the repository's name");
  if (!state.hasRemote || !state.inOrg) throw new Error(`The remote is not ${ORG}/${state.name}; nothing was changed`);
  if (state.readmeDirty || state.otherDirty.length) throw new Error("There are uncommitted changes. Commit and push them first.");
  if (state.ahead === null) throw new Error("The branch does not track a branch on GitHub; push it first");
  if (state.ahead > 0) throw new Error(`${state.ahead} commit(s) are not on GitHub yet. Push them first.`);
  await run(makePublicArgv(state.name), { timeoutMs: 60_000 });
  const now = await visibility(state.name, run, true);
  if (now !== "PUBLIC") throw new Error(`GitHub reports the repository as ${now} after the change`);
  if (logDir) {
    await fsp.appendFile(path.join(logDir, VISIBILITY_LOG),
      visibilityLogLine({ paper: path.basename(path.dirname(repoAbs)), url: state.url, who }), "utf8");
  }
  return { visibility: now, url: state.url };
}

/** The first EMBARGO.json at or above a folder (a corpus under a selection
 *  embargo carries one at its root), else `null`. */
export function embargoMarker(dir: string): string | null {
  for (let d = path.resolve(dir); ; d = path.dirname(d)) {
    const marker = path.join(d, "EMBARGO.json");
    if (fs.existsSync(marker)) return marker;
    if (path.dirname(d) === d) return null;
  }
}
