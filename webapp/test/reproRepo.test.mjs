import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterAll, test } from "vitest";

import {
  ORG, commitAndPush, commitMessage, dirtyPaths, findRepo, githubSlug, makePublic, makePublicArgv,
  readReadme, repoState, saveReadme, sha256, visibilityLogLine,
} from "../lib/reproRepo.ts";

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "repro-repo-"));
afterAll(() => fs.rmSync(tmp, { recursive: true, force: true }));
const git = (cwd, ...args) => execFileSync("git", ["-C", cwd, "-c", "user.name=T", "-c", "user.email=t@example.org", ...args], { encoding: "utf8" });

/** A paper folder with a repo that tracks a local bare "GitHub". */
function paperWithRepo(name = "Journal-2024-PMC1-10.1--x-words") {
  const paper = fs.mkdtempSync(path.join(tmp, "paper-"));
  const repo = path.join(paper, name), bare = path.join(paper, ".remote.git");
  fs.mkdirSync(repo);
  execFileSync("git", ["init", "-q", "--bare", "-b", "main", bare]);
  execFileSync("git", ["init", "-q", "-b", "main", repo]);
  git(repo, "config", "user.name", "T"); git(repo, "config", "user.email", "t@example.org");
  fs.writeFileSync(path.join(repo, "README.md"), "# Title\n\n**Summary**\n\n- one\n");
  fs.writeFileSync(path.join(repo, "replay.py"), "print(1)\n");
  git(repo, "add", "."); git(repo, "commit", "-q", "-m", "first");
  git(repo, "remote", "add", "origin", bare); git(repo, "push", "-q", "-u", "origin", "main");
  return { paper, repo, bare, name };
}

/** The real git, with the remote reported as the org's GitHub repository and
 *  `gh` answered by `gh(argv)`; every argv is recorded. */
function runner(name, gh = () => "PRIVATE\n") {
  const calls = [];
  const run = async (argv, opts = {}) => {
    calls.push(argv);
    if (argv[0] === "gh") return gh(argv);
    if (argv.slice(3).join(" ") === "remote get-url origin") return `https://github.com/${ORG}/${name}.git\n`;
    return execFileSync(argv[0], argv.slice(1), { cwd: opts.cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  };
  return { run, calls };
}

test("pure pieces: slug, dirty paths, commit message, argv, log line", () => {
  assert.deepEqual(githubSlug("https://github.com/Org/Some-Repo.git\n"), { owner: "Org", name: "Some-Repo" });
  assert.deepEqual(githubSlug("git@github.com:Org/a.b-c"), { owner: "Org", name: "a.b-c" });
  assert.equal(githubSlug("/srv/git/x.git"), null);
  assert.deepEqual(dirtyPaths(" M README.md\n?? new file.txt\nR  a.py -> b.py\n"), ["README.md", "new file.txt", "b.py"]);
  assert.equal(commitMessage("Dan\nElton"), "README: edited in the review workbench by Dan Elton");
  assert.equal(commitMessage(""), "README: edited in the review workbench");
  assert.deepEqual(makePublicArgv("r"), ["gh", "repo", "edit", `${ORG}/r`, "--visibility", "public", "--accept-visibility-change-consequences"]);
  assert.equal(visibilityLogLine({ paper: "10.1--x", url: "https://github.com/o/r", who: "Dan" }, new Date(0)),
    "1970-01-01T00:00:00.000Z\t10.1--x\thttps://github.com/o/r\tpublic\tDan\n");
});

test("findRepo: none, one, two, and a symlinked folder is not followed", async () => {
  const { paper, repo } = paperWithRepo();
  assert.equal(await findRepo(paper), fs.realpathSync(repo));
  const empty = fs.mkdtempSync(path.join(tmp, "empty-"));
  fs.mkdirSync(path.join(empty, "forensic_review_rng"));
  assert.equal(await findRepo(empty), null);
  // A link to a repo elsewhere is not this paper's repo.
  fs.symlinkSync(repo, path.join(empty, "linked"));
  assert.equal(await findRepo(empty), null);
  fs.mkdirSync(path.join(paper, "second", ".git"), { recursive: true });
  await assert.rejects(findRepo(paper), /holds 2 git repositories/);
});

test("saveReadme writes only the version the editor started from", async () => {
  const { repo } = paperWithRepo();
  const before = await readReadme(repo);
  assert.equal(before.sha256, sha256(before.text));
  const saved = await saveReadme(repo, "# Title\r\n\r\nedited\r\n", before.sha256);
  assert.equal(fs.readFileSync(path.join(repo, "README.md"), "utf8"), "# Title\n\nedited\n");
  assert.equal(saved.sha256, sha256("# Title\n\nedited\n"));
  await assert.rejects(saveReadme(repo, "stale edit", before.sha256), /changed on disk/);
  await assert.rejects(saveReadme(repo, "   ", saved.sha256), /empty/);
  assert.deepEqual(fs.readdirSync(repo).filter((n) => n.endsWith(".tmp")), [], "no temp file left behind");
  // Saving runs no git command: the edit is uncommitted.
  assert.match(git(repo, "status", "--porcelain"), /^ M README\.md/);
  // A README that is a symlink is refused.
  fs.rmSync(path.join(repo, "README.md")); fs.symlinkSync("/etc/hostname", path.join(repo, "README.md"));
  await assert.rejects(readReadme(repo), /not a regular file/);
});

test("commitAndPush commits the README alone and the remote receives it", async () => {
  const { repo, bare, name } = paperWithRepo();
  const { run } = runner(name);
  await assert.rejects(commitAndPush(repo, "Dan", run), /Nothing to commit or push/);
  fs.writeFileSync(path.join(repo, "README.md"), "# Title\n\nedited\n");
  let state = await repoState(repo, run);
  assert.deepEqual([state.readmeDirty, state.otherDirty, state.ahead, state.inOrg], [true, [], 0, true]);
  assert.deepEqual(await commitAndPush(repo, "Dan Elton", run), { committed: true, pushed: true });
  assert.equal(git(bare, "log", "-1", "--format=%s").trim(), "README: edited in the review workbench by Dan Elton");
  assert.equal(git(bare, "show", "main:README.md"), "# Title\n\nedited\n");
  state = await repoState(repo, run);
  assert.deepEqual([state.readmeDirty, state.ahead], [false, 0]);

  // Another dirty file is never swept into the commit: refused, nothing changed.
  fs.writeFileSync(path.join(repo, "README.md"), "# Title\n\nagain\n");
  fs.writeFileSync(path.join(repo, "replay.py"), "print(2)\n");
  const head = git(repo, "rev-parse", "HEAD");
  await assert.rejects(commitAndPush(repo, "Dan", run), /Other files have uncommitted changes \(replay\.py\)/);
  assert.equal(git(repo, "rev-parse", "HEAD"), head);

  // A remote that is not the org's repository of this name is never pushed to.
  const real = async (argv, opts = {}) => execFileSync(argv[0], argv.slice(1), { cwd: opts.cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] });
  git(repo, "checkout", "-q", "--", "replay.py");
  await assert.rejects(commitAndPush(repo, "Dan", real), /The remote is not Metascience-Observatory-Reproductions/);
  assert.equal(git(repo, "rev-parse", "HEAD"), head);
});

test("makePublic: typed name, clean tree and pushed commits, then one gh edit and a log line", async () => {
  const { paper, repo, name } = paperWithRepo();
  let vis = "PRIVATE";
  const { run, calls } = runner(name, (argv) => { if (argv[2] === "edit") { vis = "PUBLIC"; return ""; } return vis + "\n"; });
  const edits = () => calls.filter((c) => c[0] === "gh" && c[2] === "edit");

  await assert.rejects(makePublic(repo, "something-else", "Dan", paper, run), /does not match/);
  fs.writeFileSync(path.join(repo, "README.md"), "# Title\n\nedited\n");
  await assert.rejects(makePublic(repo, name, "Dan", paper, run), /uncommitted changes/);
  git(repo, "commit", "-q", "-am", "edit");
  await assert.rejects(makePublic(repo, name, "Dan", paper, run), /1 commit\(s\) are not on GitHub yet/);
  assert.deepEqual(edits(), [], "nothing was changed on GitHub by a refused request");
  assert.equal(fs.existsSync(path.join(paper, "REPO_VISIBILITY.tsv")), false);

  git(repo, "push", "-q");
  assert.deepEqual(await makePublic(repo, ` ${name} `, "Dan Elton", paper, run),
    { visibility: "PUBLIC", url: `https://github.com/${ORG}/${name}` });
  assert.deepEqual(edits(), [makePublicArgv(name)]);
  const line = fs.readFileSync(path.join(paper, "REPO_VISIBILITY.tsv"), "utf8").trim().split("\t");
  assert.deepEqual(line.slice(1), [path.basename(paper), `https://github.com/${ORG}/${name}`, "public", "Dan Elton"]);
});

test("makePublic reports a change GitHub did not make, and logs nothing", async () => {
  const { paper, repo, name } = paperWithRepo("Other-2024-PMC2-10.1--y-words");
  const { run } = runner(name, (argv) => (argv[2] === "edit" ? "" : "PRIVATE\n"));
  await assert.rejects(makePublic(repo, name, "Dan", paper, run), /reports the repository as PRIVATE after the change/);
  assert.equal(fs.existsSync(path.join(paper, "REPO_VISIBILITY.tsv")), false);
});
