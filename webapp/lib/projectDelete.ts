/** Tells the page-wide progress bar that a delete job just started. */
export const DELETE_STARTED = "metascience:project-delete-started";

export type DeleteJob = {
  id: string; project: string;
  state: "counting" | "deleting" | "done" | "failed";
  total: number; done: number; elapsed: number;
  deleting_since?: number; started_at: number; finished_at?: number;
  also_removes: string[]; error: string | null;
};

function clock(seconds: number) {
  if (!Number.isFinite(seconds) || seconds < 0) return "?";
  const s = Math.round(seconds), h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60;
  const mmss = `${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
  return h ? `${h}:${mmss}` : mmss;
}

/** One tqdm-style line: `45%|████▌     | 40,512/90,295 files [00:12<00:15, 3,300 files/s]`. */
export function tqdmLine(job: DeleteJob, nowSeconds: number, width = 24) {
  if (job.state === "counting") return `counting files… [${clock(job.elapsed)}]`;
  const total = Math.max(job.total, job.done), frac = total ? job.done / total : 1;
  const cells = frac * width, full = Math.floor(cells);
  const partial = full < width ? " ▏▎▍▌▋▊▉"[Math.floor((cells - full) * 8)] : "";
  const bar = ("█".repeat(full) + partial).padEnd(width, " ");
  const since = job.deleting_since ?? job.started_at;
  const spent = (job.finished_at ?? nowSeconds) - since;
  const rate = spent > 0 ? job.done / spent : 0;
  const eta = rate > 0 ? (total - job.done) / rate : NaN;
  return `${String(Math.floor(frac * 100)).padStart(3)}%|${bar}| ${job.done.toLocaleString()}/${total.toLocaleString()} files `
    + `[${clock(spent)}<${clock(eta)}, ${Math.round(rate).toLocaleString()} files/s]`;
}
