/** Decision button layouts for the review page, one per vocabulary.
 *
 * The vocabularies themselves are generated from `review_io.py` into
 * `constants.gen.ts`; this file only arranges them into columns with
 * labels. `test/decisions.mjs` pins that every layout's keys equal its
 * generated list, so a decision added in Python cannot silently lack a
 * button, and a button cannot offer a decision the service would refuse.
 *
 * Keyed by the STORED producer (`DECISIONS_BY_PRODUCER`), never a display
 * name: a separately distributed detector (rng_track today; spectra and
 * copy-paste tracks later) declares its vocabulary in Python and gets its
 * layout here. A producer without a layout of its own falls back by kind.
 */
import {
  DECISIONS_BY_PRODUCER, IMAGE_DECISIONS, NUMERIC_DECISIONS, RNG_DECISIONS,
} from "./constants.gen.ts";

export type DecisionColumns = readonly (readonly (readonly [string, string])[])[];

export const NUMERIC_COLS: DecisionColumns = [
  [
    ["correct_minor", "Correct — minor issue"],
    ["correct_significant", "Correct — significant issue"],
  ],
  [
    ["false_positive", "False positive"],
  ],
];

export const IMAGE_COLS: DecisionColumns = [
  [
    ["true_issue", "True issue"],
    ["unsure", "Unsure"],
  ],
  [
    ["false_positive", "False positive"],
    ["false_positive_same_condition", "FP — same condition"],
    ["false_positive_other", "FP — other"],
    ["false_positive_chart", "FP — chart / label"],
    ["false_positive_overlay", "FP — channel overlay"],
    ["false_positive_supplement", "FP — own supplement"],
    ["false_positive_magnification", "FP — magnification"],
    ["false_positive_scale_bar", "False positive: scale bar"],
    ["false_positive_channels", "False positive: different channels"],
    ["false_positive_logo", "False positive: logo"],
  ],
];

/** Seeded-RNG detector (`rng_track`): the match is either the paper's own
 *  data presented as measured, or one of three benign explanations. */
export const RNG_COLS: DecisionColumns = [
  [
    ["true_issue", "True issue — seeded output presented as data"],
    ["unsure", "Unsure"],
  ],
  [
    ["disclosed_simulation", "Disclosed / legitimate simulation"],
    ["random_algorithm", "Legitimate random algorithm (assignment, bootstrap)"],
    ["artefact", "Parse artefact / false positive"],
  ],
];

export const COLS_BY_PRODUCER: Record<string, DecisionColumns> = {
  rng_track: RNG_COLS,
};

export function columnKeys(cols: DecisionColumns): string[] {
  return cols.flatMap((col) => col.map(([key]) => key));
}

/** The layout one issue row offers: its producer's own when declared, else
 *  image or numeric by kind -- the same rule as `decisionsFor` in
 *  `constants.gen.ts` / `review_io.decisions_for`. */
export function decisionColumnsFor(
  iss: { kind?: string | null; producer?: string | null },
): DecisionColumns {
  const own = iss.producer ? COLS_BY_PRODUCER[iss.producer] : undefined;
  if (own) return own;
  return iss.kind === "image" ? IMAGE_COLS : NUMERIC_COLS;
}

/** Every generated vocabulary with the layout that serves it. */
export type Vocabulary = { name: string; decisions: readonly string[]; cols: DecisionColumns };

export function vocabularies(): Vocabulary[] {
  const out: Vocabulary[] = [
    { name: "numeric", decisions: NUMERIC_DECISIONS, cols: NUMERIC_COLS },
    { name: "image", decisions: IMAGE_DECISIONS, cols: IMAGE_COLS },
    { name: "rng_track", decisions: RNG_DECISIONS, cols: RNG_COLS },
  ];
  for (const producer of Object.keys(DECISIONS_BY_PRODUCER)) {
    if (!out.some((v) => v.name === producer)) {
      out.push({ name: producer, decisions: DECISIONS_BY_PRODUCER[producer],
                 cols: COLS_BY_PRODUCER[producer] ?? [] });
    }
  }
  return out;
}
