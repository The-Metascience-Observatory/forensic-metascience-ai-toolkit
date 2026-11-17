"use client";

import { useEffect, useState } from "react";
import { DELETE_STARTED } from "@/lib/projectDelete";

/** What `project_delete_plan` returns for one project (only the fields read here). */
type Plan = {
  project: string;
  folders: { path: string; files: number; bytes: number; measured: boolean; registered_as?: string | null }[];
  /** Registered folders that are symlinks: each is removed after its target. */
  links?: string[];
  refused: { path: string; reason: string }[];
  also_removes: string[];
  can_delete: boolean;
};

async function post(body: Record<string, unknown>) {
  const res = await fetch("/api/projects", {
    method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body),
  });
  const out = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(out.error || res.statusText);
  return out;
}

export function bytes(n: number) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
}

/** The projects to start deleting: those whose plan allows it, minus any a
 *  selected parent's delete already removes (it lives inside that folder). */
export function toDelete(plans: Plan[]): string[] {
  const ok = plans.filter((p) => p.can_delete);
  const covered = new Set(ok.flatMap((p) => p.also_removes));
  return ok.map((p) => p.project).filter((n) => !covered.has(n));
}

/** "Delete selected": one confirmation listing every selected project's
 *  folders, then one background delete per project (the bar at the bottom
 *  follows them). Projects whose plan is refused are listed and skipped. */
export function BulkDelete({ names, onClose }: { names: string[]; onClose: (started: boolean) => void }) {
  const [plans, setPlans] = useState<Plan[] | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let live = true;
    Promise.all(names.map((project) =>
      post({ project, action: "delete_plan" })
        .then((p) => ({ plan: p as Plan }))
        .catch((e) => ({ error: `${project}: ${e instanceof Error ? e.message : String(e)}` })),
    )).then((out) => {
      if (!live) return;
      setPlans(out.flatMap((o) => ("plan" in o ? [o.plan] : [])));
      setErrors(out.flatMap((o) => ("error" in o ? [o.error] : [])));
    });
    return () => { live = false; };
  }, [names]);

  const go = plans ? toDelete(plans) : [];
  const files = (plans || []).filter((p) => go.includes(p.project))
    .reduce((a, p) => a + p.folders.reduce((b, f) => b + f.files, 0), 0);
  const size = (plans || []).filter((p) => go.includes(p.project))
    .reduce((a, p) => a + p.folders.reduce((b, f) => b + f.bytes, 0), 0);

  async function confirm() {
    setBusy(true);
    const failed: string[] = [];
    for (const project of go) {
      try { await post({ project, action: "delete", confirm: true }); }
      catch (e) { failed.push(`${project}: ${e instanceof Error ? e.message : String(e)}`); }
      window.dispatchEvent(new Event(DELETE_STARTED));
    }
    setBusy(false);
    if (failed.length) setErrors(failed);
    else onClose(true);
  }

  return (
    <div role="dialog" aria-label={`Delete ${names.length} projects`} className="delete-plan">
      <h2 style={{ fontSize: 16, margin: "0 0 8px" }}>Delete {names.length} selected projects?</h2>
      <p className="muted" style={{ margin: "0 0 8px" }}>
        Permanently removes these folders from this computer, including downloaded papers,
        supplements and analysis outputs, and hides the projects here. Shared database records
        and other reviewers’ copies are not changed.
      </p>
      {!plans && <p>Measuring the folders…</p>}
      {plans && (
        <ul style={{ margin: "0 0 8px", paddingLeft: 18 }}>
          {plans.map((p) => (
            <li key={p.project}>
              <span className="mono">{p.project}</span>
              {!p.can_delete && <span style={{ color: "var(--sev-impossible)" }}> — refused, skipped
                {p.refused.length > 0 && `: ${p.refused.map((r) => `${r.path} (${r.reason})`).join("; ")}`}</span>}
              {p.can_delete && !go.includes(p.project) && <span className="muted"> — inside another selected project, removed with it</span>}
              {p.can_delete && p.folders.length === 0 && <span className="muted"> — no local folder; only hidden here</span>}
              {p.folders.length > 0 && (
                <ul style={{ paddingLeft: 18 }}>
                  {p.folders.map((f) => (
                    <li key={f.path}>
                      <span className="mono">{f.path}</span>{" "}
                      <span className="muted">— {f.measured ? "" : "at least "}{f.files.toLocaleString()} files, {bytes(f.bytes)}</span>
                      {f.registered_as && (p.links || []).includes(f.registered_as) && (
                        <div className="muted" data-symlink>
                          registered through the symlink <span className="mono">{f.registered_as}</span>, which is removed too
                        </div>
                      )}
                    </li>
                  ))}
                  {(p.links || []).filter((l) => !p.folders.some((f) => f.registered_as === l)).map((l) => (
                    <li key={l} className="muted" data-symlink>
                      symlink <span className="mono">{l}</span>, removed too
                    </li>
                  ))}
                </ul>
              )}
              {p.also_removes.length > 0 && (
                <div><strong>Also removes:</strong> <span className="mono">{p.also_removes.join(", ")}</span></div>
              )}
            </li>
          ))}
        </ul>
      )}
      {errors.map((e) => <p key={e} style={{ color: "var(--sev-impossible)", margin: "0 0 4px" }}>{e}</p>)}
      {plans && go.length > 0 && (
        <p style={{ margin: "8px 0" }}>
          <strong>Delete {go.length} project{go.length === 1 ? "" : "s"} permanently?</strong>{" "}
          <span className="muted">{files.toLocaleString()} files, {bytes(size)} in all.</span>
        </p>
      )}
      <span style={{ display: "inline-flex", gap: 8 }}>
        {plans && go.length > 0 && (
          <button type="button" className="danger" disabled={busy} autoFocus onClick={confirm}>
            {busy ? "Starting…" : `Yes, delete ${go.length}`}
          </button>
        )}
        <button type="button" disabled={busy} onClick={() => onClose(false)}>
          {plans && go.length > 0 ? "No" : "Close"}
        </button>
      </span>
    </div>
  );
}
