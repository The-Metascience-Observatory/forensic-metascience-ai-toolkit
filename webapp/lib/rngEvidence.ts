/** Pure helpers for the seeded-RNG evidence panel (`rng_track` rows).
 *
 * The detector files the first observed values beside the generator's
 * values (`reported.observed_first_values`, `computed.generated_first_values`),
 * its measured inputs (generator, seed, stream position, tier, excess
 * bits) and a replay snippet. This module turns those into what a reviewer
 * compares; the component only lays it out. No React here, so the rules
 * run under `node --experimental-strip-types` in `test/rngEvidence.mjs`.
 */

export type RngInputs = {
  generator?: string | null;
  seed?: number | null;
  stream_position?: number | null;
  n_values?: number | null;
  n_blocks?: number | null;
  match_kind?: string | null;
  tier?: number | null;
  excess_bits?: number | null;
  log10_chance?: number | null;
  page?: number | null;
  file?: string | null;
  table?: string | null;
  column?: string | null;
  pmcid?: string | null;
  [key: string]: unknown;
};

export type ValuePair = {
  i: number;
  observed: number;
  generated: number;
  delta: number;
  /** |delta| exceeds half the printed precision: not an exact reproduction. */
  off: boolean;
};

/** Decimal places a printed value carries (`0.2447` -> 4; `12` -> 0).
 *  Exponent notation is read through `toString`, so 1e-7 -> 7. */
export function decimals(v: number): number {
  if (!Number.isFinite(v)) return 0;
  const s = String(v);
  const m = /e-(\d+)$/i.exec(s);
  if (m) {
    const mant = s.slice(0, s.indexOf("e")).split(".")[1]?.length ?? 0;
    return Number(m[1]) + mant;
  }
  const frac = s.split(".")[1];
  return frac ? frac.length : 0;
}

/** The finest step the observed values were printed at: 10^-(max decimals). */
export function printedPrecision(values: readonly number[]): number {
  let d = 0;
  for (const v of values) if (Number.isFinite(v)) d = Math.max(d, decimals(v));
  // `Number("1e-4")` is exact where `Math.pow(10, -4)` is 0.00009999999999999999.
  return Number(`1e-${d}`);
}

/** Observed/generated pairs over the common prefix.
 *
 *  `printed` (a table or spreadsheet value, which the paper printed to a
 *  known number of decimals): a pair is `off` when the difference exceeds
 *  half the printed step, since an exact reproduction must round to the
 *  printed digits. Not printed (a coordinate read off a figure, in data
 *  units): the values are measurements with the renderer's own error, there
 *  is no printed step to hold them to, and the detector's fit residual is
 *  the match criterion; nothing is flagged and the panel reports max |Δ|. */
export function valuePairs(
  observed: readonly unknown[] | null | undefined,
  generated: readonly unknown[] | null | undefined,
  { printed = true }: { printed?: boolean } = {},
): ValuePair[] {
  const obs = (observed ?? []).map(Number);
  const gen = (generated ?? []).map(Number);
  const n = Math.min(obs.length, gen.length);
  const tol = printed ? printedPrecision(obs.filter(Number.isFinite)) / 2 + 1e-12 : Infinity;
  const out: ValuePair[] = [];
  for (let i = 0; i < n; i++) {
    const delta = obs[i] - gen[i];
    out.push({ i, observed: obs[i], generated: gen[i], delta,
               off: !Number.isFinite(delta) || Math.abs(delta) > tol });
  }
  return out;
}

/** Were the observed values printed by the paper (a table or sheet), or
 *  measured off a figure? The exporter says so in `reported.units` ("data
 *  units" for coordinates) and names the table for table hits. */
export function valuesArePrinted(inputs: RngInputs | null | undefined,
                                 units: string | null | undefined): boolean {
  if (inputs?.table) return true;
  return !/data units|coordinate|pixel/i.test(units || "");
}

/** The largest |Δ| of the pairs, or null. */
export function maxDelta(pairs: readonly ValuePair[]): number | null {
  let m: number | null = null;
  for (const p of pairs) if (Number.isFinite(p.delta)) m = Math.max(m ?? 0, Math.abs(p.delta));
  return m;
}

/** `numpy_legacy:normal:even` -> "NumPy legacy (np.random.seed) · normal · even". */
export function generatorLabel(generator: string | null | undefined): string {
  if (!generator) return "";
  const [family, ...rest] = generator.split(":");
  const names: Record<string, string> = {
    numpy_legacy: "NumPy legacy (np.random.seed / RandomState)",
    numpy_pcg64: "NumPy default_rng (PCG64)",
    numpy_mt19937: "NumPy Generator(MT19937)",
    python_random: "Python random",
    r_mt: "R set.seed (Mersenne-Twister)",
    matlab: "MATLAB rng",
    stata: "Stata set seed",
  };
  return [names[family] ?? family, ...rest].join(" · ");
}

/** The header facts, in display order, skipping what the row did not record. */
export function inputFacts(inputs: RngInputs | null | undefined): [string, string][] {
  if (!inputs) return [];
  const facts: [string, string][] = [];
  const put = (label: string, v: unknown, fmt?: (x: number) => string) => {
    if (v === null || v === undefined || v === "") return;
    facts.push([label, typeof v === "number" && fmt ? fmt(v) : String(v)]);
  };
  put("generator", generatorLabel(inputs.generator));
  put("seed", inputs.seed);
  put("stream position", inputs.stream_position);
  put("values matched", inputs.n_values);
  put("blocks", inputs.n_blocks);
  put("match", inputs.match_kind);
  put("tier", inputs.tier);
  put("excess bits", inputs.excess_bits, (x) => x.toFixed(1));
  put("log10 chance matches", inputs.log10_chance, (x) => x.toFixed(1));
  put("table", inputs.table);
  put("column", inputs.column);
  put("page", inputs.page);
  return facts;
}

/** A table grid filed by the Europe PMC export: cells plus the (row, col)
 *  addresses each matched block landed on. 0-based grid coordinates. */
export type TableGrid = {
  label?: string | null;
  caption?: string | null;
  foot?: string | null;
  header_rows?: number | null;
  cells: (string | null)[][] | null;
  hit_cells?: Record<string, ([number, number] | null)[]> | null;
  truncated?: boolean;
  unplaced?: number;
};

/** Which block (if any) each cell belongs to, keyed "r,c" -> block index. */
export function hitCellIndex(grid: TableGrid | null | undefined): Map<string, number> {
  const out = new Map<string, number>();
  const hits = grid?.hit_cells;
  if (!hits) return out;
  for (const [block, cells] of Object.entries(hits)) {
    const b = Number(block);
    for (const rc of cells ?? []) {
      if (rc && rc.length === 2) out.set(`${rc[0]},${rc[1]}`, b);
    }
  }
  return out;
}
