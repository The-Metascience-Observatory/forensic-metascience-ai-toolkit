"use client";

import { useEffect, useMemo, useState } from "react";

import { legacyToNine, sev9Label } from "@/lib/constants.gen";

/** Generate/edit PubPeer-comment and letter-to-editor drafts from the
 * STORED findings. Nothing here posts anywhere — the human copies the text
 * out. Mirrors drafts.py's contract via /api/draft. */
export function DraftsModal({ project, dir, issues, review, onClose }: {
  project: string;
  dir: string;
  issues: any[];
  review: any;
  onClose: () => void;
}) {
  const [kind, setKind] = useState<"pubpeer" | "letter">("pubpeer");
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [savedPath, setSavedPath] = useState<string | null>(null);
  const [existing, setExisting] = useState<string[]>([]);
  const [copied, setCopied] = useState(false);

  const candidates = useMemo(
    () => issues.filter((i) => i.kind === "numeric" && i.id
      && i.adjudication_action !== "discarded"),
    [issues],
  );

  // Pre-check: severity >= 5 on the ladder (legacy runs via the canonical
  // map) and not already labelled a false positive by a reviewer.
  useEffect(() => {
    const init: Record<string, boolean> = {};
    for (const iss of candidates) {
      const nine = typeof iss.severity_9 === "number"
        ? iss.severity_9 : legacyToNine(iss.severity);
      const decision = review?.issues?.[iss.id]?.decision || "";
      init[iss.id] = typeof nine === "number" && nine >= 5
        && !decision.startsWith("false_positive");
    }
    setChecked(init);
  }, [candidates, review]);

  useEffect(() => {
    fetch(`/api/draft?project=${encodeURIComponent(project)}&dir=${encodeURIComponent(dir)}`)
      .then((r) => r.json())
      .then((b) => setExisting(b.drafts || []))
      .catch(() => { /* listing is best-effort */ });
  }, [project, dir]);

  const ids = Object.keys(checked).filter((k) => checked[k]);

  async function generate() {
    setBusy(true); setErr(null); setSavedPath(null);
    try {
      const res = await fetch("/api/draft", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project, dir, kind, finding_ids: ids }),
      });
      const rec = await res.json();
      if (!res.ok) throw new Error(rec.error || "draft failed");
      setBody(rec.body || "");
      setSavedPath(rec.path || null);
      const list = await fetch(
        `/api/draft?project=${encodeURIComponent(project)}&dir=${encodeURIComponent(dir)}`,
      ).then((r) => r.json()).catch(() => null);
      if (list?.drafts) setExisting(list.drafts);
    } catch (e: any) {
      setErr(String(e.message || e));
    } finally {
      setBusy(false);
    }
  }

  async function open(name: string) {
    setErr(null);
    const rec = await fetch(
      `/api/draft?project=${encodeURIComponent(project)}&dir=${encodeURIComponent(dir)}&f=${encodeURIComponent(name)}`,
    ).then((r) => r.json()).catch((e) => ({ error: String(e) }));
    if (rec.error) { setErr(rec.error); return; }
    setBody(rec.body || "");
    setSavedPath(name);
  }

  async function copy() {
    try {
      await navigator.clipboard.writeText(body);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    } catch { /* clipboard may be unavailable */ }
  }

  return (
    <div role="dialog" aria-modal="true" aria-label="Drafts"
         style={{
           position: "fixed", inset: 0, zIndex: 50,
           background: "color-mix(in srgb, var(--ink, #000) 40%, transparent)",
           display: "flex", alignItems: "center", justifyContent: "center",
         }}
         onClick={onClose}>
      <div style={{
        background: "var(--panel)", border: "1px solid var(--line)",
        borderRadius: 6, width: "min(860px, 94vw)", maxHeight: "88vh",
        display: "flex", flexDirection: "column", padding: 16, gap: 10,
      }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <strong style={{ flex: 1 }}>Drafts — generated from stored findings, never posted</strong>
          <label style={{ fontSize: 12 }}>
            <input type="radio" checked={kind === "pubpeer"}
                   onChange={() => setKind("pubpeer")} /> PubPeer comment
          </label>
          <label style={{ fontSize: 12 }}>
            <input type="radio" checked={kind === "letter"}
                   onChange={() => setKind("letter")} /> Letter to editor
          </label>
          <button onClick={onClose}>Close</button>
        </div>

        <div style={{ display: "flex", gap: 12, minHeight: 0, flex: 1 }}>
          <div style={{ width: 300, overflowY: "auto", flexShrink: 0,
                        borderRight: "1px solid var(--line)", paddingRight: 10 }}>
            <p className="muted" style={{ fontSize: 11, margin: "0 0 6px" }}>
              Findings to include (S≥5 pre-checked; reviewer false positives
              excluded):
            </p>
            {candidates.map((iss) => {
              const nine = typeof iss.severity_9 === "number"
                ? iss.severity_9 : legacyToNine(iss.severity);
              return (
                <label key={iss.id}
                       style={{ display: "block", fontSize: 12, margin: "4px 0" }}>
                  <input type="checkbox" checked={!!checked[iss.id]}
                         onChange={(e) => setChecked(
                           { ...checked, [iss.id]: e.target.checked })} />
                  {" "}
                  {typeof nine === "number" ? `${sev9Label(nine).split(" ")[0]} ` : ""}
                  {iss.title}
                </label>
              );
            })}
            {existing.length > 0 && (
              <div style={{ marginTop: 12 }}>
                <p className="muted" style={{ fontSize: 11, margin: "0 0 4px" }}>
                  Saved drafts:
                </p>
                {existing.map((name) => (
                  <button key={name} type="button" onClick={() => open(name)}
                          style={{ display: "block", fontSize: 11,
                                   margin: "2px 0", maxWidth: "100%",
                                   overflow: "hidden", textOverflow: "ellipsis" }}>
                    {name}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div style={{ flex: 1, display: "flex", flexDirection: "column",
                        gap: 8, minWidth: 0 }}>
            <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
              <button className="primary" disabled={busy || ids.length === 0}
                      onClick={generate}>
                {busy ? "Generating… (can take minutes)" : `Generate ${kind === "pubpeer" ? "comment" : "letter"} from ${ids.length} finding(s)`}
              </button>
              <button disabled={!body} onClick={copy}>
                {copied ? "Copied" : "Copy text"}
              </button>
              {savedPath && (
                <span className="muted" style={{ fontSize: 11 }}>
                  saved: {String(savedPath).split("/").pop()}
                </span>
              )}
            </div>
            {err && (
              <p style={{ color: "var(--sev-impossible)", fontSize: 12, margin: 0 }}>
                {err}
              </p>
            )}
            <textarea value={body} onChange={(e) => setBody(e.target.value)}
                      placeholder="Generated draft appears here. Edit freely — copying out is the only way it leaves this machine."
                      style={{ flex: 1, minHeight: 260, fontSize: 12,
                               fontFamily: "inherit", resize: "none" }} />
          </div>
        </div>
      </div>
    </div>
  );
}
