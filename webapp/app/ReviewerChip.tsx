"use client";

import { useEffect, useState } from "react";

const KEY = "metascience.reviewer";

export function readReviewer(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(KEY) || "";
}

type Me = { mode: "local" | "hosted"; email: string | null; name: string | null; role: string };

export function ReviewerChip() {
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);
  const [hosted, setHosted] = useState(false);
  const [role, setRole] = useState("");
  const [known, setKnown] = useState<string[]>(["Dan Elton"]);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/me")
      .then((r) => (r.ok ? r.json() : null))
      .then((me: Me | null) => {
        if (cancelled) return;
        if (me?.mode === "hosted" && me.name) {
          // Signed in through Cloudflare Access: the server decides the name.
          // It is mirrored into localStorage so the pages that read
          // `readReviewer()` before posting keep working; the server ignores
          // the body's value in this mode anyway.
          setHosted(true);
          setName(me.name);
          setRole(me.role);
          setOpen(false);
          try { window.localStorage.setItem(KEY, me.name); } catch { /* private window */ }
          return;
        }
        const saved = readReviewer();
        setName(saved);
        if (!saved) setOpen(true);
        fetch("/api/settings")
          .then((r) => r.json())
          .then((s) => {
            if (!cancelled && Array.isArray(s.known_reviewers)) setKnown(s.known_reviewers);
          })
          .catch(() => undefined);
      })
      .catch(() => {
        if (cancelled) return;
        const saved = readReviewer();
        setName(saved);
        if (!saved) setOpen(true);
      });
    return () => { cancelled = true; };
  }, []);

  function save(next: string) {
    const v = next.trim();
    setName(v);
    if (v) window.localStorage.setItem(KEY, v);
    else window.localStorage.removeItem(KEY);
    setOpen(false);
  }

  if (hosted) {
    return (
      <span title="Signed in through Cloudflare Access" style={{ fontSize: 12 }}>
        {name ? `Reviewing as ${name}${role === "admin" ? " · admin" : ""}` : "Signing in…"}
      </span>
    );
  }
  if (!open) {
    return (
      <button onClick={() => setOpen(true)} title="Change reviewer identity"
              style={{ fontSize: 12 }}>
        {name ? `Reviewing as ${name}` : "Set your name"}
      </button>
    );
  }
  return (
    <span style={{ display: "flex", gap: 6, alignItems: "center", fontSize: 12 }}>
      <label className="muted">You are</label>
      <input list="reviewers" value={name}
             onChange={(e) => setName(e.target.value)}
             placeholder="Dan Elton"
             style={{ width: 180 }} />
      <datalist id="reviewers">
        {known.map((n) => <option key={n} value={n} />)}
      </datalist>
      <button className="primary" onClick={() => save(name)}>Save</button>
    </span>
  );
}
