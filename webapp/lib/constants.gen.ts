// GENERATED FILE -- do not edit.
// Regenerate with: metascience gen-webapp-constants
// Sources of truth: severity9.py (ladder, legacy map), review_io.py
// (decision vocabulary), webapp_index.py (channel states), names.py
// (display names of stored producer/stage/channel identifiers).
// tests/test_webapp_constants.py regenerates and byte-compares.

export const SEVERITY9 = {
  "caps": {
    "accusatory_min": 3,
    "agent_code": 4,
    "fast_screen": 4,
    "model_knowledge": 3,
    "model_reading": 3,
    "quarantine": 3
  },
  "five_to_nine": {
    "highly_suspicious": 4,
    "impossible": 5,
    "suspicious": 3
  },
  "ladder_version": "3",
  "levels": [
    {
      "boundaries": [
        "Up to 2 if: a stated value or claim is actually wrong, not merely how it is displayed."
      ],
      "colors": {
        "dark": "#94a3b8",
        "light": "#64748b"
      },
      "correction_outcome": "no formal correction",
      "finding_rubric": "A cosmetic slip that is self-evidently a slip: a typo, a formatting glitch, a malformed reference. No reader could carry away a wrong fact, because the error is visibly an error. Confirmed and alone, the journal would do nothing formal: the record needs no amending.",
      "label": "Trivial error",
      "n": 1,
      "slug": "trivial",
      "web_summary": "Cosmetic slip; nothing to amend."
    },
    {
      "boundaries": [
        "Down to 1 if: nothing stated is wrong -- only how it is displayed.",
        "Up to 3 if: any reported result changes once it is corrected."
      ],
      "colors": {
        "dark": "#cbd5e1",
        "light": "#475569"
      },
      "correction_outcome": "erratum if needed",
      "finding_rubric": "A stated fact is wrong, but nothing depends on it: a wrong unit obvious from context, a mislabeled figure panel the caption disambiguates, a reference-numbering slip, a value that feeds no calculation. Levels 1-2 are one reporting band -- use 2 when unsure. Confirmed and alone, the journal would at most publish a brief erratum; the core findings stand unchanged.",
      "label": "Minor error",
      "n": 2,
      "slug": "minor",
      "web_summary": "A wrong fact that nothing depends on."
    },
    {
      "boundaries": [
        "Down to 2 if: no reported number or figure changes.",
        "Up to 4 if: correcting it requires re-running or re-deriving something, not just restating it."
      ],
      "colors": {
        "dark": "#fbbf24",
        "light": "#d97706"
      },
      "correction_outcome": "localized correction/clarification",
      "finding_rubric": "A reporting or assembly error that changes one reported result: a miscalculated supplementary value, a misreported subset of the sample, an assembly-mistake duplicate panel that does not misrepresent the experiment. The underlying work is sound -- correcting it means fixing the report, not redoing the analysis. Confirmed and alone, the journal would issue a localized correction; the paper's main claims still hold.",
      "label": "Notable error",
      "n": 3,
      "slug": "notable",
      "web_summary": "A reporting error that changes one result."
    },
    {
      "boundaries": [
        "Down to 3 if: the error is in the reporting, not in the method -- nothing needs re-running.",
        "Up to 5 if: a claim in the abstract changes once the section is fixed."
      ],
      "colors": {
        "dark": "#fb923c",
        "light": "#ea580c"
      },
      "correction_outcome": "public correction (corrigendum)",
      "finding_rubric": "The work itself is flawed in one part: a calibration error behind one figure, a data-processing mistake in one analysis, an omitted method detail that blocks reproduction. That section must be redone or re-derived, not merely relabeled, yet the paper's overall interpretation survives the fix. Confirmed and alone, the journal would require a public corrigendum for the affected portion.",
      "label": "Localized methodological flaw or omission",
      "n": 4,
      "slug": "local_flaw",
      "web_summary": "One part of the work is flawed and must be redone."
    },
    {
      "boundaries": [
        "Down to 4 if: every abstract-level claim survives the fix.",
        "Up to 6 if: you cannot bound which results are affected."
      ],
      "colors": {
        "dark": "#f97316",
        "light": "#c2410c"
      },
      "correction_outcome": "corrigendum or partial retraction",
      "finding_rubric": "A named claim of the paper does not survive: a miscalculation that changes an important quantitative result, a compromised dataset, a statistical error behind one main conclusion. You can still say WHICH claim falls and which stand. Confirmed and alone, the journal would publish a major corrigendum with revised conclusions, or retract the affected portion while the rest stands.",
      "label": "Major error affecting conclusions",
      "n": 5,
      "slug": "conclusions_affected",
      "web_summary": "A main claim of the paper does not survive."
    },
    {
      "boundaries": [
        "Down to 5 if: the damage is bounded and the surviving results are still identifiable.",
        "Up to 7 if: the question is settled and nothing is salvageable."
      ],
      "colors": {
        "dark": "#f87171",
        "light": "#dc2626"
      },
      "correction_outcome": "expression of concern; retraction candidate",
      "finding_rubric": "Problems pervasive enough that you cannot say which results survive: errors across many analyses, a fundamental design flaw biasing the study, a contaminated or misidentified key reagent or cell line. This rung records UNBOUNDED SCOPE, not a journal's procedural state -- whether an investigation has opened is not something this pipeline can know. Confirmed and alone, the journal would issue an expression of concern and investigate.",
      "label": "Severe error -- results unreliable",
      "n": 6,
      "slug": "unreliable",
      "web_summary": "Too much is wrong to say what survives."
    },
    {
      "boundaries": [
        "Down to 6 if: the outcome is still open -- some part may be salvageable.",
        "Up to 8 if: there is positive evidence of intent."
      ],
      "colors": {
        "dark": "#ef4444",
        "light": "#b91c1c"
      },
      "correction_outcome": "retraction (honest error)",
      "finding_rubric": "An honest mistake that is determinedly fatal: the wrong cell line or strain, a coding or calculation error that erases the key result, data misread so the primary conclusion is wrong. Nothing can be isolated or repaired. Confirmed and alone, the journal would retract the paper as an honest error.",
      "label": "Fatal error invalidating main findings",
      "n": 7,
      "slug": "fatal_error",
      "web_summary": "An honest mistake that destroys the central finding."
    },
    {
      "boundaries": [
        "Down to 7 if: the result is merely implausible, with no affirmative evidence of intent.",
        "Up to 9 if: the fraud spans multiple papers, or caused direct harm to patients, policy or the public."
      ],
      "colors": {
        "dark": "#f472b6",
        "light": "#9d174d"
      },
      "correction_outcome": "retraction (misconduct)",
      "finding_rubric": "A breach of research integrity rather than a mistake, possibly confined in scope: plagiarism, deliberate data manipulation or falsification in part of the work, research conducted without ethical approval. This rung requires POSITIVE evidence of manipulation, never mere improbability. Confirmed and alone, the journal would retract, and the notice would name the misconduct category.",
      "label": "Serious misconduct",
      "n": 8,
      "slug": "misconduct",
      "web_summary": "Deliberate manipulation, evidenced, possibly confined."
    },
    {
      "boundaries": [
        "Down to 8 if: the breach is confined to a single paper -- however many of its figures -- and caused no external harm."
      ],
      "colors": {
        "dark": "#c084fc",
        "light": "#581c87"
      },
      "correction_outcome": "retraction, sanctions",
      "finding_rubric": "Willful, systematic fraud broad in scope or with direct consequences for public welfare or policy: fabricated datasets or images across figures or papers, a manipulated clinical trial, deception that misled a field. Confirmed, the journal would retract with condemnation and institutions would pursue sanctions.",
      "label": "Malicious or extreme misconduct",
      "n": 9,
      "slug": "extreme_misconduct",
      "web_summary": "Systematic fraud, or fraud that harmed the public."
    }
  ],
  "outcome_from_five": {
    "consistent": "pass",
    "highly_suspicious": "problem",
    "impossible": "problem",
    "indeterminate": "undecided",
    "suspicious": "problem"
  }
} as const;

export const FIVE_TO_NINE: Record<string, number> = {"highly_suspicious": 4, "impossible": 5, "suspicious": 3};

export const ACCUSATORY_MIN = 3;

export const NUMERIC_DECISIONS = ["correct_minor", "correct_significant", "false_positive"] as const;

export const IMAGE_DECISIONS = ["false_positive", "false_positive_other", "false_positive_same_condition", "false_positive_chart", "false_positive_overlay", "false_positive_supplement", "false_positive_magnification", "false_positive_scale_bar", "false_positive_channels", "false_positive_logo", "true_issue", "unsure"] as const;

export const CHANNEL_STATES = ["ran", "ran_result_discarded", "refused", "did_not_run", "unknown"] as const;

export const DISPLAY_NAMES: Record<string, string> = {
  "adjudication": "Adjudicator",
  "adjudicator": "Adjudicator",
  "harness": "Harness sweep (deterministic)",
  "image_analysis": "Image analysis",
  "image_forensics": "Image analysis",
  "image_track": "Image analysis",
  "legacy_sweep": "Serial-pipeline sweep (converted)",
  "raw_data": "Raw data (copy-paste detector)",
  "raw_data_track": "Raw data (copy-paste detector)",
  "science_agent": "Scientific proofreading agent",
  "science_error": "Scientific proofreading agent",
  "scientific_proofreading_agent": "Scientific proofreading agent",
  "text_forensics": "Text forensics (tortured phrases)",
  "text_track": "Text forensics (tortured phrases)",
  "tool_agent": "Tools agent",
  "tool_expert": "Tools agent",
  "tools_agent": "Tools agent",
  "tortured_phrases": "Text forensics (tortured phrases)"
};


export type Sev9Level = (typeof SEVERITY9)["levels"][number];

const byN = new Map<number, Sev9Level>(SEVERITY9.levels.map((l) => [l.n, l]));

/** Ladder label for a 1-9 level; "" when the value is not on the ladder. */
export function sev9Label(n: number | null | undefined): string {
  const l = typeof n === "number" ? byN.get(n) : undefined;
  return l ? `S${l.n} · ${l.label}` : "";
}

/** Color for a 1-9 level in the given theme. */
export function sev9Color(n: number | null | undefined,
                          theme: "light" | "dark" = "light"): string {
  const l = typeof n === "number" ? byN.get(n) : undefined;
  return l ? l.colors[theme] : "transparent";
}

/** Map a legacy 5-enum severity string onto the ladder; null when unmapped
 * (consistent/indeterminate carry no level -- absence, not zero). A mapped
 * value must always render with a "(legacy)" marker: a mapped S5 presented
 * as an assigned S5 is exactly the substitution this toolkit exists to
 * catch. */
export function legacyToNine(sev5: string | null | undefined): number | null {
  return sev5 != null && sev5 in FIVE_TO_NINE ? FIVE_TO_NINE[sev5] : null;
}

/** The name a person reads for a stored producer value, stage label or
 * channel key (`tool_expert` -> "Tools agent"); unknown ones pass through.
 * The stored values never change: they are hashed into finding ids. */
export function displayName(id: string | null | undefined): string {
  return id ? DISPLAY_NAMES[id] ?? id : "";
}
