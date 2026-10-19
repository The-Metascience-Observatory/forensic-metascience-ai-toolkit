import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import type { Readable } from "node:stream";
import { pythonBin, pythonEnv, repoRoot } from "./python.ts";
import { indexPath } from "./settings.ts";

type Pending = { resolve: (value: any) => void; reject: (error: Error) => void; timer: ReturnType<typeof setTimeout> };
type Inflight = { task: Promise<any>; waiters: number; cancel: (reason: Error) => void };
type Runtime = { child: ChildProcessWithoutNullStreams | null; pending: Map<number, Pending>; seq: number; inflight?: Map<string, Inflight> };
// Survives Next dev module reloads, preventing duplicate workers and sync loops.
const host = globalThis as typeof globalThis & { metascienceWorkbench?: Runtime; metascienceImages?: Runtime };
const shared: Runtime = host.metascienceWorkbench ||= { child: null, pending: new Map(), seq: 0 };
const images: Runtime = host.metascienceImages ||= { child: null, pending: new Map(), seq: 0 };
const MAX_LINE = 80 * 1024 * 1024;

/** Split a stream into newline-framed lines.
 *
 * The stream is DECODED by the stream itself (`setEncoding`), whose decoder
 * carries a multibyte UTF-8 character split across two 64 KiB chunks over to
 * the next one; decoding each chunk separately turned that character into
 * U+FFFD and the JSON still parsed. Only the new chunk is searched for the
 * newline, so a large response costs O(n) rather than a rescan per chunk. */
export function frameLines(stream: Readable, onLine: (line: string) => void, onOverflow: () => void) {
  stream.setEncoding("utf8");
  let parts: string[] = [], length = 0;
  stream.on("data", (chunk: string) => {
    let start = 0, end;
    while ((end = chunk.indexOf("\n", start)) >= 0) {
      const tail = chunk.slice(start, end);
      const line = parts.length ? parts.join("") + tail : tail;
      parts = []; length = 0; start = end + 1;
      onLine(line);
    }
    if (start < chunk.length) {
      parts.push(chunk.slice(start)); length += chunk.length - start;
      if (length > MAX_LINE) { parts = []; length = 0; onOverflow(); }
    }
  });
}

function start(runtime: Runtime) {
  if (runtime.child && !runtime.child.killed) return runtime.child;
  const child = spawn(pythonBin(), ["-m", "metascience_agent.workbench.service", ...(runtime === images ? ["--images-local"] : ["--index", indexPath()])], {
    cwd: repoRoot(), stdio: ["pipe", "pipe", "pipe"],
    env: pythonEnv(),
  });
  runtime.child = child;
  let stderr = "";
  child.stderr.on("data", b => { stderr = (stderr + b.toString()).slice(-2000); });
  const fail = (error: Error) => {
    if (runtime.child !== child) return;
    runtime.child = null;
    rejectPending(runtime, error);
  };
  child.on("error", fail);
  child.stdin.on("error", fail);
  child.on("close", code => fail(new Error(`Workbench service stopped (${code}). ${stderr}`)));
  frameLines(child.stdout, line => {
    try {
      const message = JSON.parse(line), p = runtime.pending.get(message.id);
      if (!p) return;
      if (process.env.METASCIENCE_WORKBENCH_TIMING) console.info(`workbench ${message.id}: ${message.milliseconds}ms`);
      runtime.pending.delete(message.id); clearTimeout(p.timer);
      if (message.error) p.reject(new Error(message.error)); else p.resolve({value:message.result,timings:message.timings || {}});
    } catch { fail(new Error("Invalid workbench response")); child.kill(); }
  }, () => { child.kill(); fail(new Error("Workbench response exceeded 80 MiB")); });
  process.once("exit", () => child.kill());
  return child;
}

function rejectPending(runtime: Runtime, error: Error) {
  for (const p of runtime.pending.values()) { clearTimeout(p.timer); p.reject(error); }
  runtime.pending.clear();
}

/** Stop the service so the next call respawns it with current settings.
 *
 * Requests still waiting on the old process are rejected NOW, by name. The
 * child's own close handler cannot do it -- it ignores a child that is no
 * longer current -- so they used to wait out the 60 s timer and then report
 * "timed out", which reads as a slow service rather than a restart. */
export function restartWorkbench() {
  const runtime = shared;
  const child = runtime.child;
  runtime.child = null;
  rejectPending(runtime, new Error("Workbench restarted; the request was abandoned and can be retried"));
  runtime.inflight?.clear();
  if (child && !child.killed) child.kill();
  return { restarted: Boolean(child) };
}

export type WorkbenchOptions = { signal?: AbortSignal | null };
const READS = new Set(["status","image_status","image_review_counts","item","item_core","item_details","image_navigation","feed","feed_facets","runs","artifact","thumbnail","source"]);

/** One waiter's view of a (possibly shared) request. The request is
 *  cancelled in the service only when its LAST waiter goes away. */
function waitFor<T>(entry: Inflight, signal?: AbortSignal | null): Promise<T> {
  entry.waiters++;
  if (!signal) return entry.task;
  if (signal.aborted) { if (--entry.waiters === 0) entry.cancel(new Error("Workbench request cancelled")); return Promise.reject(new Error("Workbench request cancelled")); }
  return new Promise<T>((resolve, reject) => {
    const abort = () => {
      reject(new Error("Workbench request cancelled"));
      if (--entry.waiters === 0) entry.cancel(new Error("Workbench request cancelled"));
    };
    signal.addEventListener("abort", abort, { once: true });
    entry.task.then(resolve, reject).finally(() => signal.removeEventListener("abort", abort));
  });
}

export function workbenchTimed<T = any>(method: string, params: Record<string, unknown> = {}, options: WorkbenchOptions = {}): Promise<{value:T;timings:Record<string,number>}> {
  const localImages = process.env.METASCIENCE_IMAGE_STORAGE !== "shared" &&
    (params.component === "image_forensics" || ["image_status", "image_review_counts", "image_viewed", "item_core", "item_details", "image_navigation", "image_carried"].includes(method));
  const runtime = localImages ? images : shared;
  const requestKey = JSON.stringify([method, params]);
  const inflight = runtime.inflight ||= new Map();
  const reusable = READS.has(method);
  const existing = reusable ? inflight.get(requestKey) : undefined;
  if (existing) return waitFor(existing, options.signal);
  const child = start(runtime), id = ++runtime.seq;
  let entry!: Inflight;
  const task = new Promise<{value:T;timings:Record<string,number>}>((resolve, reject) => {
    // A request nobody waits for any more is withdrawn from the service, which
    // skips it if no worker has started it yet. Fast j/k browsing used to queue
    // every abandoned item behind the two detail workers.
    const withdraw = (error: Error) => {
      const pending = runtime.pending.get(id);
      if (!pending) return;
      runtime.pending.delete(id); clearTimeout(pending.timer);
      if (runtime.child === child) { try { child.stdin.write(JSON.stringify({ id: null, method: "cancel", params: { id } }) + "\n"); } catch { /* the close handler names the failure */ } }
      pending.reject(error);
    };
    const timer = setTimeout(() => withdraw(new Error("Workbench request timed out")), localImages && ["item_core","image_status","image_navigation"].includes(method) ? 10000 : 60000);
    runtime.pending.set(id, { resolve, reject, timer });
    entry = { task: null as any, waiters: 0, cancel: withdraw };
    child.stdin.write(JSON.stringify({ id, method, params }) + "\n");
  });
  entry.task = task;
  if (reusable) {
    inflight.set(requestKey, entry);
    void task.finally(() => { if (inflight.get(requestKey) === entry) inflight.delete(requestKey); }).catch(() => {});
  }
  return waitFor(entry, options.signal);
}

export async function workbench<T = any>(method: string, params: Record<string, unknown> = {}, options: WorkbenchOptions = {}): Promise<T> {
  return (await workbenchTimed<T>(method, params, options)).value;
}
export function serverTiming(timings: Record<string,number>) {
  return Object.entries(timings).map(([key,value])=>`${key};dur=${value.toFixed(2)}`).join(", ");
}
