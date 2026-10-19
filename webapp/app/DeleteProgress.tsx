"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";

import { DELETE_STARTED, tqdmLine, type DeleteJob } from "@/lib/projectDelete";

const DISMISSED = "metascience.deleteJobs.dismissed";
const readDismissed = (): string[] => {
  try { return JSON.parse(localStorage.getItem(DISMISSED) || "[]"); } catch { return []; }
};

/** Project deletions run in the workbench service; this bar follows them on
 * every page, so the reviewer can keep working while a corpus is removed. */
export function DeleteProgress() {
  const [jobs, setJobs] = useState<DeleteJob[]>([]);
  const [dismissed, setDismissed] = useState<string[]>([]);
  const [now, setNow] = useState(() => Date.now() / 1000);
  const [err, setErr] = useState<string | null>(null);
  const active = useRef<Set<string>>(new Set());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const router = useRouter(), pathname = usePathname();
  const path = useRef(pathname); path.current = pathname;

  const poll = useCallback(async () => {
    if (timer.current) clearTimeout(timer.current);
    let next: DeleteJob[] = [];
    try {
      const res = await fetch("/api/projects", { cache: "no-store" });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || res.statusText);
      next = body.jobs || [];
      setErr(null);
    } catch (e) {
      // Keep the last known progress; say the reading failed rather than dropping the bar.
      setErr(e instanceof Error ? e.message : String(e));
      if (active.current.size) timer.current = setTimeout(poll, 3000);
      return;
    }
    const running = new Set(next.filter(j => j.state === "counting" || j.state === "deleting").map(j => j.id));
    const finished = [...active.current].some(id => !running.has(id));
    active.current = running;
    setJobs(next); setNow(Date.now() / 1000);
    // The landing page lists projects; refresh it once a deletion lands.
    if (finished && path.current === "/") router.refresh();
    if (running.size) timer.current = setTimeout(poll, 1000);
  }, [router]);

  useEffect(() => {
    setDismissed(readDismissed());
    void poll();
    const start = () => void poll();
    window.addEventListener(DELETE_STARTED, start);
    return () => { window.removeEventListener(DELETE_STARTED, start); if (timer.current) clearTimeout(timer.current); };
  }, [poll]);

  const dismiss = (id: string) => {
    const next = [...dismissed, id].slice(-50);
    setDismissed(next);
    try { localStorage.setItem(DISMISSED, JSON.stringify(next)); } catch { /* per-viewer only */ }
  };
  const shown = jobs.filter(j => !dismissed.includes(j.id));
  if (!shown.length) return null;
  return (
    <div className="delete-progress" role="status" aria-live="polite">
      {shown.map(j => (
        <div key={j.id} className="delete-progress-row">
          <span className="mono delete-progress-name" title={j.project}>
            {j.state === "done" ? "✓ Deleted" : j.state === "failed" ? "✗ Delete failed:" : "Deleting"} {j.project}
          </span>
          <span className="mono delete-progress-bar">
            {j.state === "failed" ? j.error : tqdmLine(j, now)}
            {j.state === "done" && j.also_removes.length > 0 && ` · also ${j.also_removes.length} nested project(s)`}
          </span>
          {(j.state === "done" || j.state === "failed") && (
            <button type="button" className="delete-progress-close" aria-label="Dismiss"
                    onClick={() => dismiss(j.id)}>×</button>
          )}
        </div>
      ))}
      {err && <div className="delete-progress-row" style={{ color: "var(--sev-impossible)" }}>
        Progress unavailable: {err}</div>}
    </div>
  );
}
