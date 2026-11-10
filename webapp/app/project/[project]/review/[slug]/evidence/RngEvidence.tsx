"use client";

import type { Issue } from "@/lib/types/review";
import { hitCellIndex, inputFacts, maxDelta, valuePairs, valuesArePrinted,
         type RngInputs, type TableGrid } from "@/lib/rngEvidence";
import { CopyButton } from "../CopyButton";

type Block = Record<string, unknown>;

/** The matched-block columns the detector records (`computed.blocks`). */
const BLOCK_COLS: [string, string][] = [
  ["offset", "stream pos."], ["n", "n"], ["kind", "match"], ["axis", "axis"],
  ["family", "family"], ["loc", "loc"], ["scale", "scale"],
  ["rel_resid", "rel. resid"], ["excess_bits", "bits"],
];

function fmt(v: unknown): string {
  if (typeof v === "number") {
    if (Number.isInteger(v)) return String(v);
    const a = Math.abs(v);
    return a !== 0 && (a < 1e-3 || a >= 1e6) ? v.toExponential(2)
      : String(Number(v.toPrecision(6)));
  }
  return v == null ? "" : String(v);
}

function FactList({ facts }: { facts: [string, string][] }) {
  return (
    <dl style={{ display: "grid", gridTemplateColumns: "max-content 1fr",
                 gap: "2px 10px", margin: 0 }}>
      {facts.map(([k, v]) => (
        <div key={k} style={{ display: "contents" }}>
          <dt className="muted">{k}</dt>
          <dd className="mono" style={{ margin: 0 }}>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function TableGridView({ grid }: { grid: TableGrid }) {
  const idx = hitCellIndex(grid);
  if (!grid.cells) {
    return (
      <p className="muted" style={{ fontSize: 11 }}>
        Table grid not stored{grid.truncated ? " (too large to file)" : ""}.
      </p>
    );
  }
  const headerRows = grid.header_rows ?? 0;
  return (
    <details open>
      <summary>
        {grid.label || "Table"}{grid.caption ? `: ${grid.caption}` : ""} — matched cells shaded
        {grid.unplaced ? `, ${grid.unplaced} value(s) not placed` : ""}
      </summary>
      <div style={{ overflow: "auto", maxHeight: 320 }}>
        <table className="grid rng-grid">
          <tbody>
            {grid.cells.map((row, r) => (
              <tr key={r}>
                {row.map((c, ci) => {
                  const hit = idx.get(`${r},${ci}`);
                  const style = hit !== undefined
                    ? { background: "var(--focus)", fontWeight: 600 } : undefined;
                  return r < headerRows
                    ? <th key={ci} data-hit={hit} style={style}>{c ?? ""}</th>
                    : <td key={ci} data-hit={hit} style={style}>{c ?? ""}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {grid.foot && <p className="muted" style={{ fontSize: 11 }}>{grid.foot}</p>}
    </details>
  );
}

/** Evidence panel for a seeded-RNG match (`rng_track`): the detector's
 *  measured inputs, the observed values beside the generator's, every
 *  matched block, the table grid when the match is in a table, and the
 *  replay snippet. Renders nothing until the row's detail has loaded. */
export function RngEvidence({ issue }: { issue: Issue }) {
  const inputs = (issue.inputs ?? null) as RngInputs | null;
  const reported = issue.reported ?? {};
  const computed = issue.computed ?? {};
  const facts = inputFacts(inputs);
  // The generator stays in view; the match statistics (seed, position,
  // counts, tier, bits, table/column) fold under "Details", closed.
  const headline = facts.filter(([k]) => k === "generator");
  const detail = facts.filter(([k]) => k !== "generator");
  const units = typeof reported.units === "string" ? reported.units : undefined;
  const printed = valuesArePrinted(inputs, units);
  const pairs = valuePairs(reported.observed_first_values as unknown[] | undefined,
                           computed.generated_first_values as unknown[] | undefined, { printed });
  const blocks: Block[] = Array.isArray(computed.blocks) ? computed.blocks : [];
  const grid = (computed.table_grid ?? null) as TableGrid | null;
  const replay = typeof computed.replay === "string" ? computed.replay : "";
  if (!facts.length && !pairs.length && !blocks.length && !replay && !grid) return null;
  const off = pairs.filter((p) => p.off).length;
  const worst = maxDelta(pairs);
  const agreement = printed
    ? (off ? `${off} beyond printed precision` : "all within printed precision")
    : (worst === null ? "" : `max |Δ| ${fmt(worst)} (measured coordinates; the fit residual is the criterion)`);
  return (
    <section data-evidence="rng_track" onClick={(e) => e.stopPropagation()}
             style={{ marginTop: 8, fontSize: 12 }}>
      {headline.length > 0 && <FactList facts={headline} />}
      {detail.length > 0 && (
        <details data-rng-details>
          <summary>Details</summary>
          <FactList facts={detail} />
        </details>
      )}
      {pairs.length > 0 && (
        <details open>
          <summary>
            Observed vs generated: {pairs.length} shown
            {inputs?.n_values ? ` of ${inputs.n_values}` : ""}
            {units ? ` (${units})` : ""}
            {agreement ? `, ${agreement}` : ""}
          </summary>
          <table className="grid rng-values">
            <thead><tr><th>#</th><th>observed</th><th>generated</th><th>Δ</th></tr></thead>
            <tbody>
              {pairs.map((p) => (
                <tr key={p.i} data-off={p.off || undefined}
                    style={p.off ? { color: "var(--sev-suspicious, #b45309)" } : undefined}>
                  <td>{p.i + 1}</td>
                  <td className="mono">{fmt(p.observed)}</td>
                  <td className="mono">{fmt(p.generated)}</td>
                  <td className="mono">{fmt(p.delta)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      {blocks.length > 0 && (
        <details>
          <summary>
            Matched blocks: {blocks.length} listed
            {typeof computed.n_blocks_not_listed === "number" && computed.n_blocks_not_listed > 0
              ? `, ${computed.n_blocks_not_listed} more not listed` : ""}
          </summary>
          <div style={{ overflow: "auto", maxHeight: 240 }}>
            <table className="grid">
              <thead><tr>{BLOCK_COLS.map(([k, l]) => <th key={k}>{l}</th>)}</tr></thead>
              <tbody>
                {blocks.map((b, i) => (
                  <tr key={i}>{BLOCK_COLS.map(([k]) => <td key={k} className="mono">{fmt(b[k])}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </details>
      )}
      {grid && <TableGridView grid={grid} />}
      {replay && (
        <details>
          <summary>Replay snippet</summary>
          <pre className="mono" style={{ fontSize: 11, maxHeight: 240, overflow: "auto",
                                         padding: 6, border: "1px solid var(--line)",
                                         borderRadius: 4, margin: "4px 0 0" }}>{replay}</pre>
          <CopyButton text={replay} label="Copy replay" title="Copy the reproduction snippet" />
        </details>
      )}
      {/* `issue.notes` (the exporter's provenance and triage paragraph) is
          not shown: it repeats the replay and the table above. */}
    </section>
  );
}
