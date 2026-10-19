"use client";

import { useState } from "react";

export function RootForm({ initial }: { initial: string }) {
  const [root, setRoot] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function saveAndScan() {
    setBusy(true); setErr(null);
    try {
      const res = await fetch("/api/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ papers_root: root, scan: true }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error || res.statusText);
      window.location.reload();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
      <label className="muted" style={{ fontSize: 12 }}>Papers root</label>
      <input value={root} onChange={(e) => setRoot(e.target.value)}
             className="mono" style={{ width: 520, fontSize: 12 }} />
      <button className="primary" disabled={busy || !root.trim()}
              onClick={saveAndScan}>
        {busy ? "Scanning…" : "Set root and scan"}
      </button>
      {err && <span style={{ color: "var(--sev-impossible)" }}>{err}</span>}
    </div>
  );
}
