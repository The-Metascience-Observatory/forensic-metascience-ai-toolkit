"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { getJson, postJson } from "@/lib/getJson";

type Folder = { path: string; available: boolean; via?: "root" | "folder"; source?: string };
type Sources = { roots: string[]; folders: { name: string; path: string }[]; database: string[] };
type ProjectRow = {
  name: string;
  n_papers: number;
  done: boolean;
  folders: Folder[];
  database: boolean;
  members: string[];
};
type Unsourced = { name: string; n_papers: number; folders: Folder[] };
type Payload = {
  configured: boolean;
  sources: Sources;
  projects: ProjectRow[];
  unsourced: Unsourced[];
  missingRoots: string[];
  suggested: string[];
};
type User = { email: string; name: string; role: "admin" | "reviewer"; projects: string[] };

const basename = (p: string) =>
  p
    .replace(/[\\/]+$/, "")
    .split(/[\\/]/)
    .pop() || "";
const msg = (e: unknown) => (e instanceof Error ? e.message : String(e));

/** Which folders are projects, and who reviews each. A watched folder makes
 *  every subfolder a project (new ones appear by themselves); a single folder
 *  can be added by hand; a name with findings in the database but no folder
 *  here can be adopted. Everything else the catalog knows stays out of the
 *  app. Nothing on this page deletes files or database rows. */
export default function ProjectsAdminPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [newRoot, setNewRoot] = useState("");
  const [newFolder, setNewFolder] = useState({ path: "", name: "" });
  const [filter, setFilter] = useState("");

  useEffect(() => {
    Promise.all([
      getJson<Payload>("/api/admin/projects"),
      getJson<{ users: User[] }>("/api/admin/users"),
    ]).then(
      ([p, u]) => {
        setData(p);
        setUsers(u.users);
      },
      (e) => setErr(msg(e)),
    );
  }, []);

  async function saveSources(next: Sources, done: string) {
    setBusy(true);
    setErr(null);
    setNote(null);
    try {
      const out = await postJson<Payload & { warning?: string }>("/api/admin/projects", {
        sources: next,
      });
      if (out.warning) setNote(`${done} The project list could not be refreshed: ${out.warning}`);
      else {
        setData(out);
        setNote(done);
      }
    } catch (e) {
      setErr(msg(e));
    } finally {
      setBusy(false);
    }
  }

  async function setMembers(project: string, emails: string[]) {
    setBusy(true);
    setErr(null);
    setNote(null);
    const next = users.map((u) =>
      u.role === "admin"
        ? u
        : {
            ...u,
            projects: emails.includes(u.email)
              ? [...new Set([...u.projects, project])].sort()
              : u.projects.filter((p) => p !== project),
          },
    );
    try {
      const out = await postJson<{ users: User[] }>("/api/admin/users", { users: next });
      setUsers(out.users);
      setData(
        (d) =>
          d && {
            ...d,
            projects: d.projects.map((p) =>
              p.name !== project
                ? p
                : {
                    ...p,
                    members: out.users
                      .filter((u) => u.role !== "admin" && u.projects.includes(project))
                      .map((u) => u.name),
                  },
            ),
          },
      );
      setNote(`Reviewers of ${project} saved.`);
    } catch (e) {
      setErr(msg(e));
    } finally {
      setBusy(false);
    }
  }

  if (!data)
    return (
      <div className="page">
        {err ? (
          <p style={{ color: "var(--sev-impossible)" }}>{err}</p>
        ) : (
          <p className="muted">Loading…</p>
        )}
      </div>
    );
  const src = data.sources;
  const reviewers = users.filter((u) => u.role !== "admin");
  const shown = data.projects.filter(
    (p) => !filter || p.name.toLowerCase().includes(filter.toLowerCase()),
  );

  return (
    <div className="page" style={{ maxWidth: 1200 }}>
      <h1 style={{ fontSize: 20, margin: "0 0 6px" }}>Projects</h1>
      <p className="muted" style={{ maxWidth: 820, marginTop: 0 }}>
        A <strong>watched folder</strong> makes each of its subfolders a project, named after the
        subfolder, and new subfolders appear by themselves. You can also add{" "}
        <strong>one folder</strong> as a project, or adopt a project that exists only in the{" "}
        <strong>database</strong>. Anything else in the catalog is left out of the app. Nothing here
        deletes files or database records. Assign reviewers below or on{" "}
        <Link href="/admin/users">Users</Link>.
      </p>

      {!data.configured && (
        <div className="banner">
          No sources are configured, so every name in the catalog is listed (test leftovers
          included).
          {data.suggested.length > 0 ? (
            <>
              {" "}
              Start by watching:
              <ul style={{ margin: "6px 0" }}>
                {data.suggested.map((r) => (
                  <li key={r} className="mono">
                    {r}
                  </li>
                ))}
              </ul>
              <button
                type="button"
                className="primary"
                disabled={busy}
                onClick={() =>
                  saveSources(
                    { roots: data.suggested, folders: [], database: [] },
                    "Now managing projects from the watched folders.",
                  )
                }
              >
                Watch these folders
              </button>
            </>
          ) : (
            " Add a watched folder below to start."
          )}
        </div>
      )}

      <section style={{ marginTop: 16 }}>
        <h2 style={{ fontSize: 15, margin: "0 0 6px" }}>Watched folders</h2>
        {src.roots.length === 0 && <p className="muted">None.</p>}
        {src.roots.map((r) => (
          <div key={r} style={{ display: "flex", gap: 8, alignItems: "center", margin: "3px 0" }}>
            <span className="mono">{r}</span>
            {data.missingRoots.includes(r) && (
              <span style={{ color: "var(--sev-impossible)", fontSize: 12 }}>
                not found on this machine
              </span>
            )}
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                saveSources(
                  { ...src, roots: src.roots.filter((x) => x !== r) },
                  `Stopped watching ${r}.`,
                )
              }
            >
              Stop watching
            </button>
          </div>
        ))}
        <form
          style={{ display: "flex", gap: 6, marginTop: 6 }}
          onSubmit={(e) => {
            e.preventDefault();
            if (newRoot.trim())
              void saveSources(
                { ...src, roots: [...src.roots, newRoot.trim()] },
                `Watching ${newRoot.trim()}.`,
              ).then(() => setNewRoot(""));
          }}
        >
          <input
            value={newRoot}
            onChange={(e) => setNewRoot(e.target.value)}
            placeholder="/path/to/a/folder/of/projects"
            aria-label="Folder to watch"
            style={{ width: 460 }}
            className="mono"
          />
          <button type="submit" disabled={busy || !newRoot.trim()}>
            Watch folder
          </button>
        </form>
      </section>

      <section style={{ marginTop: 16 }}>
        <h2 style={{ fontSize: 15, margin: "0 0 6px" }}>Single folders</h2>
        {src.folders.length === 0 && <p className="muted">None.</p>}
        {src.folders.map((f) => (
          <div
            key={`${f.name}\0${f.path}`}
            style={{ display: "flex", gap: 8, alignItems: "center", margin: "3px 0" }}
          >
            <strong>{f.name}</strong> <span className="mono">{f.path}</span>
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                saveSources(
                  { ...src, folders: src.folders.filter((x) => x !== f) },
                  `Removed ${f.name}.`,
                )
              }
            >
              Remove
            </button>
          </div>
        ))}
        <form
          style={{ display: "flex", gap: 6, marginTop: 6 }}
          onSubmit={(e) => {
            e.preventDefault();
            const path = newFolder.path.trim(),
              name = newFolder.name.trim() || basename(path);
            if (path && name)
              void saveSources(
                { ...src, folders: [...src.folders, { name, path }] },
                `Added ${name}.`,
              ).then(() => setNewFolder({ path: "", name: "" }));
          }}
        >
          <input
            value={newFolder.path}
            onChange={(e) => setNewFolder((f) => ({ ...f, path: e.target.value }))}
            placeholder="/path/to/one/project/folder"
            aria-label="Project folder"
            style={{ width: 380 }}
            className="mono"
          />
          <input
            value={newFolder.name}
            onChange={(e) => setNewFolder((f) => ({ ...f, name: e.target.value }))}
            placeholder={basename(newFolder.path) || "project name"}
            aria-label="Project name"
            style={{ width: 200 }}
          />
          <button type="submit" disabled={busy || !newFolder.path.trim()}>
            Add folder
          </button>
        </form>
        {src.database.length > 0 && (
          <p style={{ fontSize: 13 }}>
            Database-only:{" "}
            {src.database.map((n) => (
              <span key={n} style={{ marginRight: 10 }}>
                {n}{" "}
                <button
                  type="button"
                  disabled={busy}
                  style={{ fontSize: 11 }}
                  onClick={() =>
                    saveSources(
                      { ...src, database: src.database.filter((x) => x !== n) },
                      `Removed ${n}.`,
                    )
                  }
                >
                  ×
                </button>
              </span>
            ))}
          </p>
        )}
      </section>

      {note && (
        <p className="banner" style={{ marginTop: 12 }}>
          {note}
        </p>
      )}
      {err && <p style={{ color: "var(--sev-impossible)" }}>{err}</p>}

      <section style={{ marginTop: 18 }}>
        <h2 style={{ fontSize: 15, margin: "0 0 6px" }}>
          {data.configured
            ? `Projects (${data.projects.length})`
            : `Catalog projects (${data.projects.length})`}
        </h2>
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter"
          style={{ width: 240, marginBottom: 6 }}
        />
        <table className="grid">
          <thead>
            <tr>
              <th>Project</th>
              <th style={{ textAlign: "right" }}>Papers</th>
              <th>Folders</th>
              <th>Reviewers</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((p) => (
              <tr key={p.name}>
                <td>
                  <Link href={`/project/${encodeURIComponent(p.name)}`}>{p.name}</Link>
                  {p.done && <span className="muted"> · done</span>}
                </td>
                <td style={{ textAlign: "right" }}>{p.n_papers}</td>
                <td style={{ fontSize: 12 }}>
                  {p.database && p.folders.length === 0 && (
                    <span className="muted">database only</span>
                  )}
                  {p.folders.length > 1 && (
                    <div style={{ color: "var(--sev-highly)" }}>
                      {p.folders.length} folders share this name
                    </div>
                  )}
                  {p.folders.map((f) => (
                    <div
                      key={f.path}
                      className="mono"
                      style={{ opacity: f.available ? 1 : 0.5 }}
                      title={f.available ? f.path : "missing on this machine"}
                    >
                      {f.path}
                      {!f.available && " (missing)"}
                    </div>
                  ))}
                </td>
                <td>
                  <Members
                    // Remounts (resetting the ticks) when the saved reviewers change.
                    key={reviewers
                      .filter((u) => u.projects.includes(p.name))
                      .map((u) => u.email)
                      .join(",")}
                    project={p.name}
                    reviewers={reviewers}
                    busy={busy}
                    onSave={(emails) => setMembers(p.name, emails)}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      {data.configured && data.unsourced.length > 0 && (
        <section style={{ marginTop: 18 }}>
          <h2 style={{ fontSize: 15, margin: "0 0 6px" }}>
            Not in any source ({data.unsourced.length})
          </h2>
          <p className="muted" style={{ marginTop: 0, maxWidth: 760 }}>
            Names the catalog knows that no source covers: test corpora, scratch copies, folders
            that moved, results pushed from another machine. They are hidden from everyone. Add one
            if it should be a project.
          </p>
          <details>
            <summary style={{ cursor: "pointer" }}>Show them</summary>
            <table className="grid" style={{ marginTop: 6 }}>
              <thead>
                <tr>
                  <th>Name</th>
                  <th style={{ textAlign: "right" }}>Papers</th>
                  <th>Registered folders</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {data.unsourced.map((u) => {
                  const here = u.folders.find((f) => f.available);
                  return (
                    <tr key={u.name}>
                      <td>{u.name}</td>
                      <td style={{ textAlign: "right" }}>{u.n_papers}</td>
                      <td style={{ fontSize: 12 }}>
                        {u.folders.map((f) => (
                          <div
                            key={f.path}
                            className="mono"
                            style={{ opacity: f.available ? 1 : 0.5 }}
                          >
                            {f.path}
                            {!f.available && " (missing)"}
                          </div>
                        ))}
                      </td>
                      <td style={{ whiteSpace: "nowrap" }}>
                        {here && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() =>
                              saveSources(
                                {
                                  ...src,
                                  folders: [...src.folders, { name: u.name, path: here.path }],
                                },
                                `Added ${u.name}.`,
                              )
                            }
                          >
                            Add its folder
                          </button>
                        )}{" "}
                        {u.n_papers > 0 && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() =>
                              saveSources(
                                { ...src, database: [...src.database, u.name] },
                                `Added ${u.name} from the database.`,
                              )
                            }
                          >
                            Add from database
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </details>
        </section>
      )}
    </div>
  );
}

function Members({
  project,
  reviewers,
  busy,
  onSave,
}: {
  project: string;
  reviewers: User[];
  busy: boolean;
  onSave: (emails: string[]) => void;
}) {
  const current = reviewers.filter((u) => u.projects.includes(project)).map((u) => u.email);
  const [picked, setPicked] = useState<string[]>(current);
  const changed = picked.slice().sort().join(",") !== current.slice().sort().join(",");
  if (!reviewers.length)
    return (
      <span className="muted" style={{ fontSize: 12 }}>
        Admins only (no reviewers yet)
      </span>
    );
  return (
    <details>
      <summary style={{ cursor: "pointer", fontSize: 12 }}>
        {current.length ? (
          reviewers
            .filter((u) => current.includes(u.email))
            .map((u) => u.name)
            .join(", ")
        ) : (
          <span className="muted">Admins only</span>
        )}
      </summary>
      <div style={{ padding: 4 }}>
        {reviewers.map((u) => (
          <label key={u.email} style={{ display: "block", fontSize: 12 }}>
            <input
              type="checkbox"
              checked={picked.includes(u.email)}
              onChange={() =>
                setPicked((p) =>
                  p.includes(u.email) ? p.filter((x) => x !== u.email) : [...p, u.email],
                )
              }
            />{" "}
            {u.name} <span className="muted">{u.email}</span>
          </label>
        ))}
        <button
          type="button"
          className="primary"
          disabled={busy || !changed}
          onClick={() => onSave(picked)}
          style={{ marginTop: 4 }}
        >
          Save reviewers
        </button>
      </div>
    </details>
  );
}
