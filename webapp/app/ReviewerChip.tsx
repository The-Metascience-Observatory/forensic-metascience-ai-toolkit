"use client";

import { useEffect, useState } from "react";

const KEY = "metascience.reviewer";

export function readReviewer(): string {
  if (typeof window === "undefined") return "";
  return window.localStorage.getItem(KEY) || "";
}

export function ReviewerChip() {
  const [name, setName] = useState("");
  const [open, setOpen] = useState(false);
  const [known, setKnown] = useState<string[]>(["Dan Elton"]);

  useEffect(() => {
    const saved = readReviewer();
    setName(saved);
    if (!saved) setOpen(true);
    fetch("/api/settings")
      .then((r) => r.json())
      .then((s) => {
        if (Array.isArray(s.known_reviewers)) setKnown(s.known_reviewers);
      })
      .catch(() => undefined);
  }, []);

  function save(next: string) {
    const v = next.trim();
    setName(v);
    if (v) window.localStorage.setItem(KEY, v);
    else window.localStorage.removeItem(KEY);
    setOpen(false);
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
