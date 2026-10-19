import { spawn } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { loadSettings } from "./settings.ts";

/** The interpreter the `metascience` console script points at.
 *
 * CLAUDE.md's rule: the right interpreter is MACHINE-SPECIFIC (a venv on one
 * machine, a conda install on another) and `head -1 $(which metascience)`
 * names it. The bridge used to try only the env var and one venv path, and
 * on a conda machine fell through to the SYSTEM python3 -- which imports the
 * package (PYTHONPATH is set) but takes ~4 s to do it against ~0.4 s, so
 * every page paid ten times the bridge cost and nothing said why. */
let shebangCache: string | null | undefined;
const PYTHON_BASENAME = /^python[0-9.]*$/;
/** The interpreter a script's shebang names, or -- for a `#!/bin/sh` shim
 *  that `exec`s another script (this machine's `~/.local/bin/metascience`
 *  does exactly that, into the conda one) -- the shebang ONE hop down.
 *  A non-python shebang is never an answer: the first version of this
 *  accepted `/bin/sh` and every bridge call ran `sh -m metascience_agent.cli`. */
function pythonOfScript(script: string, hops: number): string | null {
  let head: string[];
  try {
    head = fs.readFileSync(script, "utf-8").split("\n").slice(0, 40);
  } catch {
    return null;
  }
  const m = /^#!\s*(\S+)/.exec(head[0] || "");
  if (!m) return null;
  if (PYTHON_BASENAME.test(path.basename(m[1]))) {
    return fs.existsSync(m[1]) ? m[1] : null;
  }
  if (hops <= 0) return null;
  for (const line of head.slice(1)) {
    const ex = /^\s*exec\s+(\S+)/.exec(line);
    if (ex && fs.existsSync(ex[1])) return pythonOfScript(ex[1], hops - 1);
  }
  return null;
}
function consoleScriptPython(): string | null {
  if (shebangCache !== undefined) return shebangCache;
  shebangCache = null;
  const dirs = (process.env.PATH || "").split(path.delimiter).filter(Boolean);
  for (const d of dirs) {
    const script = path.join(d, "metascience");
    try {
      if (!fs.existsSync(script)) continue;
    } catch {
      continue;
    }
    const py = pythonOfScript(script, 1);
    if (py) { shebangCache = py; break; }
  }
  return shebangCache;
}

function candidates(): string[] {
  const env = (process.env.METASCIENCE_PYTHON || "").trim();
  const home = os.homedir();
  const venv = path.join(home, ".venvs", "metascience-agent");
  return [
    env,
    loadSettings().python_bin || "",
    consoleScriptPython() || "",
    path.join(venv, "bin", "python"),
    path.join(venv, "Scripts", "python.exe"),
  ].filter(Boolean);
}

export function pythonBin(): string {
  for (const c of candidates()) {
    try {
      if (fs.existsSync(c)) return c;
    } catch {
      /* skip */
    }
  }
  return process.platform === "win32" ? "python" : "python3";
}

export function repoRoot(): string {
  return path.resolve(process.cwd(), "..");
}

/** The toolkit's own source roots come from THIS checkout, whatever an
 * editable install points at. The image package is a separate repository
 * (since 1.77.0) checked out BESIDE the toolkit, so its root is the sibling
 * `../metascience-observatory-image-analysis`; where that is absent (a
 * worktree, a machine without the package) Python skips the entry and the
 * installed package, if any, is used. */
export function pythonEnv(): NodeJS.ProcessEnv {
  const repo = repoRoot();
  return {
    ...process.env,
    PYTHONPATH: [
      path.join(repo, "src"),
      path.join(repo, "copy_paste_detector", "src"),
      path.join(repo, "..", "metascience-observatory-image-analysis", "src"),
      process.env.PYTHONPATH,
    ].filter(Boolean).join(path.delimiter),
    PYTHONUNBUFFERED: "1",
  };
}

type Options = { timeoutMs?: number; stdin?: string; dedupe?: boolean };
const pending = new Map<string, Promise<unknown>>();
const waiters: (() => void)[] = [];
let active = 0;
const MAX_CHILDREN = 2;

export function pyJson(args: string[], opts?: string | Options): Promise<unknown> {
  return runJson(["-m", "metascience_agent.cli", ...args], opts);
}

/** Leaf modules avoid importing the full CLI on hot paths. */
export function pyModuleJson(mod: string, args: string[], opts?: string | Options): Promise<unknown> {
  return runJson(["-m", mod, ...args], opts);
}

async function slot<T>(job: () => Promise<T>): Promise<T> {
  if (active >= MAX_CHILDREN) await new Promise<void>((resolve) => waiters.push(resolve));
  else active++;
  try { return await job(); }
  finally {
    const next = waiters.shift();
    if (next) next(); else active--;
  }
}

function runJson(argv: string[], input?: string | Options): Promise<unknown> {
  const opts = typeof input === "object" && input !== null ? input : { stdin: input };
  const repo = repoRoot();
  const key = JSON.stringify([pythonBin(), repo, argv, opts]);
  if (opts.dedupe && pending.has(key)) return pending.get(key)!;
  const job = slot(() => new Promise<unknown>((resolve, reject) => {
    const child = spawn(pythonBin(), argv, {
      cwd: repo, stdio: ["pipe", "pipe", "pipe"],
      env: pythonEnv(),
    });
    const stdout: Buffer[] = [], stderr: Buffer[] = [];
    let bytes = 0, failure: Error | null = null;
    const stop = (message: string) => { failure = new Error(message); child.kill("SIGKILL"); };
    const timer = setTimeout(() => stop("python request timed out"), opts.timeoutMs ?? 120_000);
    const collect = (into: Buffer[]) => (b: Buffer) => {
      bytes += b.length;
      if (bytes > 80 * 1024 * 1024) stop("python output exceeded 80 MiB");
      else into.push(b);
    };
    child.stdout.on("data", collect(stdout)); child.stderr.on("data", collect(stderr));
    child.on("error", (e) => { clearTimeout(timer); reject(e); });
    child.stdin.on("error", (e: NodeJS.ErrnoException) => {
      if (e.code !== "EPIPE") { failure = e; child.kill("SIGKILL"); }
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      if (failure) { reject(failure); return; }
      const out = Buffer.concat(stdout).toString("utf8").trim();
      if (code !== 0) {
        reject(new Error((Buffer.concat(stderr).toString("utf8") || out || `exit ${code}`).slice(0, 4000)));
        return;
      }
      try {
        if (!out) throw new Error("python produced no JSON");
        // Parse complete pretty JSON before trying the CLI's final JSON line.
        try { resolve(JSON.parse(out)); }
        catch {
          const lines = out.split("\n").filter((l) => /^[\[{]/.test(l.trim()));
          resolve(JSON.parse(lines[lines.length - 1] || out));
        }
      } catch (e) { reject(e); }
    });
    child.stdin.end(opts.stdin);
  }));
  if (opts.dedupe) {
    pending.set(key, job);
    void job.finally(() => pending.delete(key)).catch(() => {});
  }
  return job;
}
