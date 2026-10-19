"use client";

import { useMemo, useState } from "react";
import { DELETE_STARTED } from "@/lib/projectDelete";

const columns = [
  { key: "n_papers", label: "Papers" },
  { key: "n_pdf", label: "With PDF" },
  { key: "n_xml", label: "With XML" },
  { key: "n_image_run", label: "Image track" },
  { key: "n_text_run", label: "Text track" },
  { key: "n_human_reviewed", label: "Human reviewed" },
  { key: "n_image_reviewed", label: "Image reviews" },
  { key: "n_image_unviewed", label: "Image viewed / unviewed" },
] as const;

type SortKey = typeof columns[number]["key"];
type ProjectSummary = Record<SortKey, number> & {
  name: string;
  n_not_fetched: number;
  n_image_discarded?: number;
  n_image_refused?: number;
  n_in_progress: number;
  n_submitted_pubpeer?: number;
  n_image_reviewed_papers?: number;
  n_image_reviewed_other_runs?: number;
  n_image_viewed?: number;
  done?: boolean;
  done_at?: string | null;
  /** Has image results but is not in the shared catalog yet. */
  image_only?: boolean;
};

type DeletePlan = {
  project: string;
  folders: { path: string; files: number; bytes: number; measured: boolean;
             also_removes: string[]; inside_project: string[] }[];
  refused: { path: string; reason: string }[];
  missing: string[];
  kept_mapped_papers: number;
  also_removes: string[];
  partly_affects: string[];
  can_delete: boolean;
};

async function projectAction(body: Record<string, unknown>) {
  const res = await fetch("/api/projects", { method: "POST",
    headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  const out = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(out.error || res.statusText);
  return out;
}

function bytes(n: number) {
  const units = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  while (n >= 1024 && i < units.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(i ? 1 : 0)} ${units[i]}`;
}

export type ImageReviewCount = {
  n_items: number; n_papers: number; n_items_other_runs: number;
  // Absent when the project's latest queue could not be counted.
  n_latest_items?: number; n_viewed?: number;
};

export function ProjectsTable({ projects }: { projects: ProjectSummary[] }) {
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [plan, setPlan] = useState<DeletePlan | null>(null);
  // Done moves the row at once; the save runs behind it and is undone if it fails.
  const [doneOverride, setDoneOverride] = useState<Record<string, boolean>>({});
  const isDone = (p: ProjectSummary) => doneOverride[p.name] ?? Boolean(p.done);
  const active = projects.filter(p => !isDone(p)), done = projects.filter(isDone);

  async function toggleDone(p: ProjectSummary) {
    const next = !isDone(p);
    setErr(null);
    setDoneOverride(o => ({ ...o, [p.name]: next }));
    try {
      await projectAction({ project: p.name, action: next ? "done" : "undone" });
    } catch (e) {
      setDoneOverride(o => ({ ...o, [p.name]: !next }));
      setErr(`${p.name}: could not save — ${e instanceof Error ? e.message : String(e)}`);
    }
  }

  async function run(project: string, body: Record<string, unknown>, after?: (out: any) => void) {
    setBusy(project); setErr(null);
    try {
      const out = await projectAction({ project, ...body });
      if (after) after(out); else window.location.reload();
    } catch (e) {
      setErr(`${project}: ${e instanceof Error ? e.message : String(e)}`);
    } finally { setBusy(null); }
  }
  const actions = (p: ProjectSummary) => (
    <span style={{ display: "inline-flex", gap: 6 }}>
      <button type="button"
              title={isDone(p) ? "Move back to the active projects" : "Mark this project done on this machine"}
              onClick={() => toggleDone(p)}>
        {isDone(p) ? "Reopen" : "Done"}
      </button>
      <button type="button" disabled={busy !== null} className="danger"
              title="Delete this project's folder(s) on this machine"
              onClick={() => run(p.name, { action: "delete_plan" }, out => setPlan(out))}>
        {busy === p.name && !plan ? "…" : "Delete…"}
      </button>
    </span>
  );

  return (
    <>
      {err && <p style={{ color: "var(--sev-impossible)", marginTop: 12 }}>{err}</p>}
      {plan && (
        <div role="dialog" aria-label={`Delete ${plan.project}`} className="delete-plan">
          <h2 style={{ fontSize: 16, margin: "0 0 8px" }}>
            Delete <span className="mono">{plan.project}</span>?
          </h2>
          <p className="muted" style={{ margin: "0 0 8px" }}>
            Permanently removes these folders from this computer, including downloaded
            papers, supplements and analysis outputs, and hides the project here. Shared
            database records and other reviewers’ copies are not changed.
          </p>
          {plan.folders.length === 0 && (
            <p>No local folder is registered for this project; it will only be hidden here.</p>
          )}
          <ul style={{ margin: "0 0 8px", paddingLeft: 18 }}>
            {plan.folders.map(f => (
              <li key={f.path}>
                <span className="mono">{f.path}</span>{" "}
                <span className="muted">
                  — {f.measured ? "" : "at least "}{f.files.toLocaleString()} files, {bytes(f.bytes)}
                  {f.inside_project.length > 0 && ` · inside project ${f.inside_project.join(", ")}`}
                </span>
              </li>
            ))}
          </ul>
          {plan.missing.length > 0 && (
            <p className="muted">Already absent: {plan.missing.join(", ")}</p>
          )}
          {plan.also_removes.length > 0 && (
            <p><strong>Also removes {plan.also_removes.length} project(s) stored inside it:</strong>{" "}
              <span className="mono">{plan.also_removes.join(", ")}</span></p>
          )}
          {plan.partly_affects.length > 0 && (
            <p>Also removes folders registered to (these projects stay listed): <span className="mono">{plan.partly_affects.join(", ")}</span></p>
          )}
          {plan.kept_mapped_papers > 0 && (
            <p className="muted">{plan.kept_mapped_papers} explicitly mapped paper folder(s) outside
              these folders are kept.</p>
          )}
          {plan.refused.length > 0 && (
            <p style={{ color: "var(--sev-impossible)" }}>
              Refused: {plan.refused.map(r => `${r.path} (${r.reason})`).join("; ")}
            </p>
          )}
          {plan.can_delete && <p style={{ margin: "8px 0" }}><strong>Delete permanently?</strong></p>}
          <span style={{ display: "inline-flex", gap: 8 }}>
            {plan.can_delete && (
              <button type="button" className="danger" disabled={busy !== null} autoFocus
                      onClick={() => run(plan.project, { action: "delete", confirm: true }, () => {
                        setPlan(null);
                        window.dispatchEvent(new Event(DELETE_STARTED));
                      })}>
                {busy === plan.project ? "Starting…" : "Yes, delete"}
              </button>
            )}
            <button type="button" disabled={busy !== null} onClick={() => setPlan(null)}>
              {plan.can_delete ? "No" : "Close"}
            </button>
          </span>
        </div>
      )}
      <Table projects={active} actions={actions} />
      {done.length > 0 && (
        <section style={{ marginTop: 24 }}>
          <h2 style={{ fontSize: 16, margin: 0 }}>Done <span className="muted">({done.length})</span></h2>
          <Table projects={done} actions={actions} />
        </section>
      )}
    </>
  );
}

function Table({ projects, actions }: {
  projects: ProjectSummary[]; actions: (p: ProjectSummary) => React.ReactNode;
}) {
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" } | null>(null);
  const rows = useMemo(() => {
    if (!sort) return projects;
    return [...projects].sort((a, b) => {
      const left = a[sort.key], right = b[sort.key];
      // Unavailable counts stay last in either direction; they are not zero.
      if (!Number.isFinite(left)) return Number.isFinite(right) ? 1 : 0;
      if (!Number.isFinite(right)) return -1;
      return sort.dir === "desc" ? right - left : left - right;
    });
  }, [projects, sort]);

  return (
      <table className="grid" style={{ marginTop: 18 }}>
        <thead>
          <tr>
            <th>Project</th>
            {columns.map(({ key, label }) => (
              <th key={key} style={{ textAlign: "right" }}
                  aria-sort={sort?.key === key ? (sort.dir === "desc" ? "descending" : "ascending") : "none"}>
                <button type="button" className="sort-th" title={`Sort by ${label}`}
                        onClick={() => setSort(current => ({
                          key,
                          dir: current?.key === key && current.dir === "desc" ? "asc" : "desc",
                        }))}>
                  {label}{sort?.key === key ? (sort.dir === "desc" ? " ▾" : " ▴") : " ↕"}
                </button>
              </th>
            ))}
            <th />
          </tr>
        </thead>
        <tbody>
          {rows.map((p) => (
            <tr key={p.name}>
              <td>
                <a href={`/project/${encodeURIComponent(p.name)}`}
                   className="mono">{p.name}</a>
                {p.image_only && (
                  <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}
                        title="Image results are imported, but the shared catalog has not scanned this folder yet; paper counts appear once it does.">
                    image results only
                  </span>
                )}
                {p.n_not_fetched > 0 && (
                  <span className="muted" style={{ marginLeft: 8, fontSize: 11 }}
                        title="Landing page, no PDF — our gap, not the paper's">
                    {p.n_not_fetched} never fetched
                  </span>
                )}
              </td>
              <td style={{ textAlign: "right" }}>{p.n_papers}</td>
              <td style={{ textAlign: "right" }}>{p.n_pdf}</td>
              <td style={{ textAlign: "right" }}>{p.n_xml}</td>
              <td style={{ textAlign: "right" }}
                  title={(p.n_image_discarded || p.n_image_refused)
                    ? `${p.n_image_run} retained`
                      + (p.n_image_discarded
                        ? ` · ${p.n_image_discarded} ran, result discarded` : "")
                      + (p.n_image_refused
                        ? ` · ${p.n_image_refused} refused` : "")
                    : "retained results only"}>
                {p.n_image_run}
                {(p.n_image_discarded ?? 0) > 0 && (
                  <span className="muted"> · {p.n_image_discarded} discarded</span>
                )}
              </td>
              <td style={{ textAlign: "right" }}>{p.n_text_run}</td>
              <td style={{ textAlign: "right" }}
                  title={p.n_in_progress
                    ? `${p.n_in_progress} in progress (not counted as reviewed)`
                    : "complete only"}>
                {p.n_human_reviewed}
                {p.n_in_progress > 0 && (
                  <span className="muted"> +{p.n_in_progress}</span>
                )}
                {(p.n_submitted_pubpeer ?? 0) > 0 && (
                  <span className="muted"> · {p.n_submitted_pubpeer} PubPeer</span>
                )}
              </td>
              <td style={{ textAlign: "right" }}
                  title={Number.isFinite(p.n_image_reviewed)
                    ? `${p.n_image_reviewed} image finding(s) with a human decision, `
                      + `in ${p.n_image_reviewed_papers} paper(s)`
                      + (p.n_image_reviewed_other_runs
                        ? ` · ${p.n_image_reviewed_other_runs} more on earlier runs` : "")
                    : "Local image-review database unavailable"}>
                {Number.isFinite(p.n_image_reviewed) ? p.n_image_reviewed : "—"}
                {(p.n_image_reviewed_papers ?? 0) > 0 && (
                  <span className="muted"> · {p.n_image_reviewed_papers} papers</span>
                )}
              </td>
              <td style={{ textAlign: "right" }}
                  title={Number.isFinite(p.n_image_unviewed)
                    ? `${p.n_image_viewed} of ${p.n_image_viewed! + p.n_image_unviewed} image finding(s) `
                      + "in the latest runs opened by anyone; "
                      + `${p.n_image_unviewed} never opened. Opening is not a decision. `
                      + "Views are recorded from 2026-09-26 on."
                    : "No image queue for this project, or its count is unavailable"}>
                {Number.isFinite(p.n_image_unviewed)
                  ? <>{p.n_image_viewed} <span className="muted">/ {p.n_image_unviewed} unviewed</span></>
                  : "—"}
              </td>
              <td style={{ whiteSpace: "nowrap" }}>{actions(p)}</td>
            </tr>
          ))}
        </tbody>
      </table>
  );
}
