"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function RefreshCountsButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    setBusy(true);
    setErr(null);
    try {
      const res = await fetch("/api/workbench", { method: "POST", headers:{"content-type":"application/json"}, body:JSON.stringify({method:"sync"}) });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error || res.statusText);
      router.refresh();
      setBusy(false);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  }

  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
      <button type="button" onClick={refresh} disabled={busy}
              title="Synchronize changed shared findings, reviews and runs">
        {busy ? "Refreshing…" : "Sync records"}
      </button>
      {err && (
        <span style={{ color: "var(--sev-impossible)", fontSize: 12 }}>{err}</span>
      )}
    </span>
  );
}
