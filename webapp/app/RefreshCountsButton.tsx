"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { errorMessage, postJson } from "@/lib/getJson";

export function RefreshCountsButton() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function refresh() {
    setBusy(true);
    setErr(null);
    try {
      await postJson("/api/workbench", { method: "sync" });
      router.refresh();
      setBusy(false);
    } catch (e: unknown) {
      setErr(errorMessage(e));
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
