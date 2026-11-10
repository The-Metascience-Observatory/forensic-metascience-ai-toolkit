"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { getJson, postJson } from "@/lib/getJson";

type Role = "admin" | "reviewer";
type User = { email: string; name: string; role: Role; projects: string[] };
type Payload = { users: User[]; projects: string[]; me: string | null };

const blank = (): User => ({ email: "", name: "", role: "reviewer", projects: [] });

/** The user directory: who may use the hosted app, as what, on which
 *  projects. Cloudflare Access must ALSO admit each email (two gates, by
 *  design); the banner after a save says so for every newly added person. */
export default function UsersPage() {
  const [data, setData] = useState<Payload | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [saved, setSaved] = useState<string[] | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getJson<Payload>("/api/admin/users")
      .then((d) => {
        setData(d);
        setUsers(d.users);
      })
      .catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, []);

  const original = useMemo(() => new Map((data?.users || []).map((u) => [u.email, u])), [data]);
  const dirty = JSON.stringify(users) !== JSON.stringify(data?.users || []);

  const update = (i: number, patch: Partial<User>) =>
    setUsers((us) => us.map((u, j) => (j === i ? { ...u, ...patch } : u)));

  async function save() {
    setBusy(true);
    setErr(null);
    setSaved(null);
    try {
      const cleaned = users
        .filter((u) => u.email.trim())
        .map((u) => ({ ...u, email: u.email.trim().toLowerCase(), name: u.name.trim() }));
      const out = await postJson<{ users: User[] }>("/api/admin/users", { users: cleaned });
      const added = out.users.filter((u) => !original.has(u.email)).map((u) => u.email);
      setData((d) => (d ? { ...d, users: out.users } : d));
      setUsers(out.users);
      setSaved(added);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
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

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <h1 style={{ fontSize: 20, margin: "0 0 6px" }}>Users</h1>
      <p className="muted" style={{ maxWidth: 760, marginTop: 0 }}>
        Admins see every project and the admin pages. Reviewers see only the projects ticked for
        them, and can record decisions, mark papers complete and record PubPeer posts there.
        Decisions are recorded under the display name, so renaming someone who has already reviewed
        splits their history. Projects come from <Link href="/admin/projects">Projects</Link>.
      </p>

      <table className="grid">
        <thead>
          <tr>
            <th>Email (Cloudflare Access)</th>
            <th>Display name</th>
            <th>Role</th>
            <th>Projects</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {users.map((u, i) => {
            const before = original.get(u.email);
            const renamed = before && before.name !== u.name;
            const self = data.me && u.email === data.me;
            return (
              <tr key={i}>
                <td>
                  {before ? (
                    <span className="mono">{u.email}</span>
                  ) : (
                    <input
                      type="email"
                      value={u.email}
                      placeholder="name@example.org"
                      aria-label="Email"
                      onChange={(e) => update(i, { email: e.target.value })}
                      style={{ width: 230 }}
                    />
                  )}
                  {self && <span className="muted"> (you)</span>}
                </td>
                <td>
                  <input
                    value={u.name}
                    aria-label="Display name"
                    placeholder="Full name"
                    onChange={(e) => update(i, { name: e.target.value })}
                    style={{ width: 170 }}
                  />
                  {renamed && (
                    <div style={{ fontSize: 11, color: "var(--sev-highly)" }}>
                      Was “{before.name}”; past decisions stay under that name.
                    </div>
                  )}
                </td>
                <td>
                  <select
                    value={u.role}
                    aria-label="Role"
                    disabled={!!self}
                    onChange={(e) => update(i, { role: e.target.value as Role })}
                  >
                    <option value="reviewer">Reviewer</option>
                    <option value="admin">Admin</option>
                  </select>
                </td>
                <td>
                  {u.role === "admin" ? (
                    <span className="muted">All projects</span>
                  ) : (
                    <ProjectPicker
                      all={data.projects}
                      value={u.projects}
                      onChange={(projects) => update(i, { projects })}
                    />
                  )}
                </td>
                <td>
                  {!self && (
                    <button
                      type="button"
                      className="danger"
                      onClick={() => setUsers((us) => us.filter((_, j) => j !== i))}
                    >
                      Remove
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      <div style={{ display: "flex", gap: 8, marginTop: 12, alignItems: "center" }}>
        <button type="button" onClick={() => setUsers((us) => [...us, blank()])}>
          Add user
        </button>
        <button type="button" className="primary" disabled={!dirty || busy} onClick={save}>
          {busy ? "Saving…" : "Save changes"}
        </button>
        {dirty && !busy && (
          <button type="button" onClick={() => setUsers(data.users)}>
            Discard
          </button>
        )}
      </div>
      {err && <p style={{ color: "var(--sev-impossible)" }}>{err}</p>}
      {saved && (
        <div className="banner" style={{ marginTop: 12 }}>
          Saved.
          {saved.length > 0 && (
            <>
              {" "}
              Now also admit {saved.join(", ")} in Cloudflare Access: Zero Trust → Access →
              Applications → this app → its policy → add the email to the Include rule. Until then
              Access will not let them in.
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ProjectPicker({
  all,
  value,
  onChange,
}: {
  all: string[];
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const [filter, setFilter] = useState("");
  const missing = value.filter((p) => !all.includes(p));
  const shown = all.filter((p) => !filter || p.toLowerCase().includes(filter.toLowerCase()));
  const toggle = (p: string) =>
    onChange(value.includes(p) ? value.filter((x) => x !== p) : [...value, p].sort());
  return (
    <details>
      <summary style={{ cursor: "pointer" }}>
        {value.length ? value.join(", ") : <span className="muted">None: sees nothing yet</span>}
      </summary>
      <div
        style={{
          border: "1px solid var(--line)",
          padding: 6,
          marginTop: 4,
          maxHeight: 260,
          overflow: "auto",
          minWidth: 280,
        }}
      >
        <input
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="Filter projects"
          style={{ width: "100%", marginBottom: 4 }}
        />
        {shown.map((p) => (
          <label key={p} style={{ display: "block", fontSize: 12 }}>
            <input type="checkbox" checked={value.includes(p)} onChange={() => toggle(p)} /> {p}
          </label>
        ))}
        {missing.map((p) => (
          <label
            key={p}
            style={{ display: "block", fontSize: 12 }}
            title="Assigned, but not a project any more (no source lists it)"
          >
            <input type="checkbox" checked onChange={() => toggle(p)} /> <s>{p}</s>{" "}
            <span className="muted">(not a project)</span>
          </label>
        ))}
      </div>
    </details>
  );
}
