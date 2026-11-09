"use client";

import { useState } from "react";
import type { Item } from "@/app/images/lib";
import { isoDate, normalisePubpeerUrl } from "@/lib/websiteFinding";

type WebsiteResult = { id: string; website: string; files: string[]; page: string; embargoOverridden?: string };

/** "Add to website": the PubPeer link and comment for this finding, sent
 *  with the current summary figure to the Observatory website checkout. */
export function AddToWebsite({ project, item, exportBlob, onClose }: {
  project: string; item: Item; exportBlob: () => Promise<Blob>; onClose: () => void;
}) {
  const dirs = [...new Set(item.panels.map(p => p.paper_dir).filter(Boolean))];
  const [dir, setDir] = useState(dirs[0] || "");
  const [url, setUrl] = useState("");
  const [summary, setSummary] = useState("");
  const [date, setDate] = useState(isoDate());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<WebsiteResult | null>(null);
  // Set when the server refuses because the corpus is under a selection embargo;
  // the override is then offered, for this one finding, as "submit anyway".
  const [embargo, setEmbargo] = useState<string | null>(null);
  const urlOk = !!normalisePubpeerUrl(url);
  const labels = [...new Set(item.panels.map(p => p.figure_label).filter(Boolean))].join(" and ");

  async function submit(override = false) {
    setBusy(true); setError(null);
    try {
      const form = new FormData();
      form.set("project", project); form.set("dir", dir);
      form.set("pubpeerUrl", url); form.set("summary", summary); form.set("submitted", date);
      form.set("alt", `Annotated ${labels || "figure"} with the matching regions outlined.`);
      form.set("image", await exportBlob(), "summary.png");
      if (override) form.set("embargoOverride", "submit-anyway");
      const response = await fetch("/api/images/website", { method: "POST", body: form });
      const body = await response.json().catch(() => ({}));
      if (response.status === 403 && body.code === "embargo") { setEmbargo(String(body.marker || "")); return; }
      if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
      setDone(body as WebsiteResult);
    } catch (e) { setError(String(e instanceof Error ? e.message : e)); }
    finally { setBusy(false); }
  }

  const box = { border: "1px solid var(--line)", borderRadius: 6, padding: 10, display: "flex", flexDirection: "column" as const, gap: 6 };
  if (done) return (
    <div style={box}>
      <span>Added to the website as <b>{done.id}</b>: wrote {done.files.map(f => <code key={f} style={{ marginRight: 6 }}>{f}</code>)}
        in <code>{done.website}</code>. Nothing is public until the website is committed and deployed.</span>
      {done.embargoOverridden && <span role="status">The selection embargo was overridden for this finding; recorded in <code>EMBARGO_OVERRIDES.jsonl</code> beside <code>{done.embargoOverridden}</code>.</span>}
      <span className="muted">It will appear at <code>{done.page}</code>.</span>
      <div><button type="button" onClick={onClose}>ok</button></div>
    </div>
  );
  return (
    <div style={box}>
      <b>Add to website</b>
      <span className="muted">The figure as shown now (with any crop and edits, and the logo if ticked) goes to the image-findings page with this comment.</span>
      {dirs.length > 1 && (
        <label style={{ display: "flex", gap: 6, alignItems: "center" }}>paper the comment is on
          <select value={dir} onChange={e => setDir(e.target.value)}>
            {dirs.map((d, i) => <option key={d} value={d}>{"AB"[i] || i + 1} · {d}</option>)}
          </select>
        </label>
      )}
      <label style={{ display: "flex", gap: 6, alignItems: "center" }}>PubPeer URL
        <input type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://pubpeer.com/publications/…"
               style={{ flex: 1, minWidth: 260 }} />
      </label>
      {url && !urlOk && <span style={{ color: "var(--sev-impossible)" }}>Not a PubPeer publication link.</span>}
      <label style={{ display: "flex", flexDirection: "column", gap: 4 }}>Comment text
        <textarea value={summary} onChange={e => setSummary(e.target.value)} rows={4}
                  placeholder="The comment as posted on PubPeer" style={{ width: "100%", lineHeight: 1.4 }} />
      </label>
      <label style={{ display: "flex", gap: 6, alignItems: "center" }}>submitted
        <input type="date" value={date} onChange={e => setDate(e.target.value)} />
      </label>
      {error && <span role="alert" style={{ color: "var(--sev-impossible)" }}>{error}</span>}
      {embargo !== null && (
        <div role="alert" style={{ border: "2px solid var(--sev-impossible)", borderRadius: 6, padding: 8, display: "flex", flexDirection: "column", gap: 6 }}>
          <b>This corpus is under a selection embargo.</b>
          <span><code>{embargo}</code> marks it as selected for a possible False Claims Act action, where publishing our own
            findings can spoil the claim. Override only if you have decided to publish this finding. It applies to this
            one finding, the marker is left in place, and the override is written to <code>EMBARGO_OVERRIDES.jsonl</code> beside it.</span>
          <div>
            <button type="button" onClick={() => submit(true)}
                    disabled={busy || !urlOk || !summary.trim() || !dir || !date}>
              {busy ? "adding…" : "submit anyway"}</button>
          </div>
        </div>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <button type="button" onClick={() => submit(false)} disabled={busy || !urlOk || !summary.trim() || !dir || !date}>
          {busy ? "adding…" : "add to website"}</button>
        <button type="button" onClick={onClose} disabled={busy}>cancel</button>
      </div>
    </div>
  );
}
