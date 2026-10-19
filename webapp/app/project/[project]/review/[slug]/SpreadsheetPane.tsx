"use client";

import { useEffect, useMemo, useState } from "react";

export function SpreadsheetPane({ project, slug, dir, artefact, label }: {
  project: string;
  slug: string;
  dir: string;
  artefact: any;
  label: string;
}) {
  const [grid, setGrid] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  const identity = `${project}:${dir}:${artefact.relpath || artefact.basename}:${artefact.sheet || ""}`;
  const [selection, setSelection] = useState({ identity, sheet: artefact.sheet || "" });
  const sheet = selection.identity === identity ? selection.sheet : artefact.sheet || "";
  const setSheet = (value: string) => setSelection({ identity, sheet: value });

  const highlights = useMemo(
    () => JSON.stringify(artefact.cells || []),
    [artefact.cells],
  );

  useEffect(() => {
    const q = new URLSearchParams({
      project, slug, dir, f: artefact.relpath || artefact.basename,
    });
    if (sheet) q.set("sheet", sheet);
    if (highlights && highlights !== "[]") q.set("highlights", highlights);
    const controller = new AbortController();
    let cancel = false;
    setGrid(null); setErr(null);
    fetch(`/api/sheet?${q}`, { signal: controller.signal })
      .then(async (r) => {
        const body = await r.json();
        if (!r.ok) throw new Error(body.error || r.statusText);
        return body;
      })
      .then((body) => {
        if (cancel) return;
        setGrid(body);

      })
      .catch((e) => { if (!cancel) setErr(String(e.message || e)); });
    return () => { cancel = true; controller.abort(); };
  }, [project, slug, dir, artefact.relpath, artefact.basename, sheet, highlights]);

  const mark = useMemo(() => {
    const s = new Set<string>();
    for (const h of grid?.highlights || []) s.add(`${h.r}:${h.c}`);
    return s;
  }, [grid]);

  const download = (rel: string) =>
    `/api/media?project=${encodeURIComponent(project)}`
    + `&dir=${encodeURIComponent(dir)}&f=${encodeURIComponent(rel)}`
    + `&download=1`;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{
        display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap",
        padding: "6px 10px", borderBottom: "1px solid var(--line)",
        background: "var(--panel)", fontSize: 12,
      }}>
        <strong className="mono" title={artefact.basename}
                style={{ overflow: "hidden", textOverflow: "ellipsis",
                         whiteSpace: "nowrap", maxWidth: "46%" }}>
          {artefact.basename}
        </strong>
        {label && <span className="pill">{label}</span>}
        <span className="muted">
          {artefact.sheet ? `sheet ${artefact.sheet}` : ""}
          {artefact.confidence === "file" ? " · file located; cells not recorded" : ""}
        </span>
        <span style={{ marginLeft: "auto", display: "flex", gap: 8 }}>
          {artefact.relpath && (
            <a href={download(artefact.relpath)}
               download={artefact.basename || true}>download</a>
          )}
          {artefact.highlight_relpath && (
            <a href={download(artefact.highlight_relpath)}
               download={artefact.highlight_relpath.split("/").pop() || true}>
              highlighted xlsx
            </a>
          )}
        </span>
      </div>
      {grid?.sheets?.length > 1 && (
        <div style={{ display: "flex", gap: 4, padding: "4px 10px",
                      borderBottom: "1px solid var(--line)", overflowX: "auto" }}>
          {grid.sheets.map((name: string) => (
            <button key={name} onClick={() => setSheet(name)}
                    style={{
                      fontSize: 11,
                      background: name === grid.sheet ? "var(--accent)" : "transparent",
                      color: name === grid.sheet ? "var(--on-accent)" : "inherit",
                    }}>{name}</button>
          ))}
        </div>
      )}
      {err && <p style={{ color: "var(--sev-impossible)", padding: 12 }}>{err}</p>}
      {grid?.error && <p style={{ color: "var(--sev-impossible)", padding: 12 }}>{grid.error}</p>}
      {grid?.preview_note && <p className="muted" style={{padding: "4px 10px", fontSize: 11}}>{grid.preview_note}</p>}
      {grid?.truncated && !grid?.preview_note && (
        <p className="muted" style={{ padding: "4px 10px", fontSize: 11 }}>
          Showing the first {grid.n_rows} rows.
        </p>
      )}
      {grid?.rows && (
        <div style={{ overflow: "auto", flex: 1, minHeight: 0 }}>
          <table className="sheet">
            {grid.column_labels && <thead><tr><th>Row</th>{grid.column_labels.map((c: string) => <th key={c}>{c}</th>)}</tr></thead>}
            <tbody>
              {grid.rows.map((row: string[], r: number) => (
                <tr key={r} ref={r === (grid.highlights?.[0]?.r ?? -1)
                  ? (el) => { el?.scrollIntoView({ block: "center" }); } : undefined}>
                  <td className="rowhead">{grid.row_numbers?.[r] ?? r + 1}</td>
                  {row.map((cell: string, c: number) => (
                    <td key={c} className={mark.has(`${r}:${c}`) ? "hit" : undefined}>
                      {cell}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
