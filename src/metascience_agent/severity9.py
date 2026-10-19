"""
The ONE source of truth for the 1-9 severity ladder
(`docs/specs/findings_v2.md` section 7). Two axes: the tool-layer 5-enum in
`tools/severity.py` is an EPISTEMIC verdict about a number and stays in every
ToolSpec, guard and test; this ladder is a CORRECTION-OUTCOME ranking
(`docs/errorlevels.md` is its narrative appendix -- rationale and worked
cases for people, read by no code).
 Neither is derivable from the other, so a finding
carries both.

Deliberately imports NOTHING from `tools/severity.py` -- the vocabularies
touch only through the string keys of `FIVE_TO_NINE`/`OUTCOME_FROM_FIVE`;
importing the enum would invite "convenience" conversions in tool code.

Consumers: prompt assembly (`rubric_markdown()`); the pipeline annotator and
`adjudicate.apply()` (evidence-channel cap constants + `clamp_provisional()`;
no literal severities anywhere else, and NO absolute ceiling -- every role may
write any rung 1-9); the Part C codegen (`as_json()` ->
`webapp/lib/constants.gen.ts` and `docs/severity_ladder.json`, both written by
`metascience gen-webapp-constants`).

The record carries BOTH audiences' fields rather than splitting into two
documents: prompts read `finding_rubric` + `boundaries`, the public ladder page
reads `label`/`correction_outcome`/`web_summary`/`colors`. A second hand-written
copy for the website would be the `tool_reference.md` failure -- prose
maintained for an audience of nobody.
"""

from __future__ import annotations

from typing import NamedTuple

# Bump when the LADDER changes meaning (a slug, a cap, a rung's rubric): two
# reviews across such a boundary are not comparable, same as the MINOR rule
# in CHANGELOG.md. This is the ladder's own version, not the finding-id
# hasher's (that constant lives with the hasher).
LADDER_VERSION = "3"


class Level(NamedTuple):
    """One rung.

    `finding_rubric` answers RUBRIC_QUESTION for a single finding, with the
    worked cases left to `docs/errorlevels.md`. `boundaries` are the
    escalate/de-escalate tests against the ADJACENT rungs -- the ladder's
    misclassifications all live at seams, and prose alone gave a classifier
    nothing to test. `web_summary` is one table cell for the public ladder
    page; it is deliberately NOT the rubric, which is too long for a cell.
    """

    slug: str
    label: str
    correction_outcome: str
    finding_rubric: str
    boundaries: tuple[str, ...]
    web_summary: str


# The correction outcome is the LABEL, not the TEST. Rungs 2/3/4 used to be
# discriminated by journal notice names (erratum / correction / corrigendum),
# which are publisher-dependent -- Nature publishes "Author Correction" where
# Science publishes "Erratum" -- so a classifier was being asked to decide on
# an unstable category. Every `boundaries` entry keys on the PAPER instead:
# does a reported result change, must something be re-run, does an
# abstract-level claim fall, can the damage still be bounded.
LEVELS: dict[int, Level] = {
    1: Level(
        slug="trivial",
        label="Trivial error",
        correction_outcome="no formal correction",
        finding_rubric=(
            "A cosmetic slip that is self-evidently a slip: a typo, a "
            "formatting glitch, a malformed reference. No reader could carry "
            "away a wrong fact, because the error is visibly an error. "
            "Confirmed and alone, the journal would do nothing formal: the "
            "record needs no amending."
        ),
        boundaries=(
            "Up to 2 if: a stated value or claim is actually wrong, not "
            "merely how it is displayed.",
        ),
        web_summary="Cosmetic slip; nothing to amend.",
    ),
    2: Level(
        slug="minor",
        label="Minor error",
        correction_outcome="erratum if needed",
        finding_rubric=(
            "A stated fact is wrong, but nothing depends on it: a wrong unit "
            "obvious from context, a mislabeled figure panel the caption "
            "disambiguates, a reference-numbering slip, a value that feeds no "
            "calculation. Levels 1-2 are one reporting band -- use 2 when "
            "unsure. Confirmed and alone, the journal would at most publish a "
            "brief erratum; the core findings stand unchanged."
        ),
        boundaries=(
            "Down to 1 if: nothing stated is wrong -- only how it is "
            "displayed.",
            "Up to 3 if: any reported result changes once it is corrected.",
        ),
        web_summary="A wrong fact that nothing depends on.",
    ),
    3: Level(
        slug="notable",
        label="Notable error",
        correction_outcome="localized correction/clarification",
        finding_rubric=(
            "A reporting or assembly error that changes one reported result: "
            "a miscalculated supplementary value, a misreported subset of the "
            "sample, an assembly-mistake duplicate panel that does not "
            "misrepresent the experiment. The underlying work is sound -- "
            "correcting it means fixing the report, not redoing the analysis. "
            "Confirmed and alone, the journal would issue a localized "
            "correction; the paper's main claims still hold."
        ),
        boundaries=(
            "Down to 2 if: no reported number or figure changes.",
            "Up to 4 if: correcting it requires re-running or re-deriving "
            "something, not just restating it.",
        ),
        web_summary="A reporting error that changes one result.",
    ),
    4: Level(
        slug="local_flaw",
        label="Localized methodological flaw or omission",
        correction_outcome="public correction (corrigendum)",
        finding_rubric=(
            "The work itself is flawed in one part: a calibration error "
            "behind one figure, a data-processing mistake in one analysis, an "
            "omitted method detail that blocks reproduction. That section "
            "must be redone or re-derived, not merely relabeled, yet the "
            "paper's overall interpretation survives the fix. Confirmed and "
            "alone, the journal would require a public corrigendum for the "
            "affected portion."
        ),
        boundaries=(
            "Down to 3 if: the error is in the reporting, not in the method "
            "-- nothing needs re-running.",
            "Up to 5 if: a claim in the abstract changes once the section is "
            "fixed.",
        ),
        web_summary="One part of the work is flawed and must be redone.",
    ),
    5: Level(
        slug="conclusions_affected",
        label="Major error affecting conclusions",
        correction_outcome="corrigendum or partial retraction",
        finding_rubric=(
            "A named claim of the paper does not survive: a miscalculation "
            "that changes an important quantitative result, a compromised "
            "dataset, a statistical error behind one main conclusion. You can "
            "still say WHICH claim falls and which stand. Confirmed and "
            "alone, the journal would publish a major corrigendum with "
            "revised conclusions, or retract the affected portion while the "
            "rest stands."
        ),
        boundaries=(
            "Down to 4 if: every abstract-level claim survives the fix.",
            "Up to 6 if: you cannot bound which results are affected.",
        ),
        web_summary="A main claim of the paper does not survive.",
    ),
    6: Level(
        slug="unreliable",
        label="Severe error -- results unreliable",
        correction_outcome="expression of concern; retraction candidate",
        finding_rubric=(
            "Problems pervasive enough that you cannot say which results "
            "survive: errors across many analyses, a fundamental design flaw "
            "biasing the study, a contaminated or misidentified key reagent "
            "or cell line. This rung records UNBOUNDED SCOPE, not a journal's "
            "procedural state -- whether an investigation has opened is not "
            "something this pipeline can know. Confirmed and alone, the "
            "journal would issue an expression of concern and investigate."
        ),
        boundaries=(
            "Down to 5 if: the damage is bounded and the surviving results "
            "are still identifiable.",
            "Up to 7 if: the question is settled and nothing is salvageable.",
        ),
        web_summary="Too much is wrong to say what survives.",
    ),
    7: Level(
        slug="fatal_error",
        label="Fatal error invalidating main findings",
        correction_outcome="retraction (honest error)",
        finding_rubric=(
            "An honest mistake that is determinedly fatal: the wrong cell "
            "line or strain, a coding or calculation error that erases the "
            "key result, data misread so the primary conclusion is wrong. "
            "Nothing can be isolated or repaired. Confirmed and alone, the "
            "journal would retract the paper as an honest error."
        ),
        boundaries=(
            "Down to 6 if: the outcome is still open -- some part may be "
            "salvageable.",
            "Up to 8 if: there is positive evidence of intent.",
        ),
        web_summary="An honest mistake that destroys the central finding.",
    ),
    8: Level(
        slug="misconduct",
        label="Serious misconduct",
        correction_outcome="retraction (misconduct)",
        finding_rubric=(
            "A breach of research integrity rather than a mistake, possibly "
            "confined in scope: plagiarism, deliberate data manipulation or "
            "falsification in part of the work, research conducted without "
            "ethical approval. This rung requires POSITIVE evidence of "
            "manipulation, never mere improbability. Confirmed and alone, the "
            "journal would retract, and the notice would name the misconduct "
            "category."
        ),
        boundaries=(
            "Down to 7 if: the result is merely implausible, with no "
            "affirmative evidence of intent.",
            "Up to 9 if: the fraud spans multiple papers, or caused direct "
            "harm to patients, policy or the public.",
        ),
        web_summary="Deliberate manipulation, evidenced, possibly confined.",
    ),
    9: Level(
        slug="extreme_misconduct",
        label="Malicious or extreme misconduct",
        correction_outcome="retraction, sanctions",
        finding_rubric=(
            "Willful, systematic fraud broad in scope or with direct "
            "consequences for public welfare or policy: fabricated datasets "
            "or images across figures or papers, a manipulated clinical "
            "trial, deception that misled a field. Confirmed, the journal "
            "would retract with condemnation and institutions would pursue "
            "sanctions."
        ),
        boundaries=(
            "Down to 8 if: the breach is confined to a single paper -- "
            "however many of its figures -- and caused no external harm.",
        ),
        web_summary="Systematic fraud, or fraud that harmed the public.",
    ),
}

# ---------------------------------------------------------------------------
# Maps between the tool-layer 5-enum (as STRINGS -- never import the enum)
# and this ladder. One value, stated once: the legacy webapp badge, the
# converter (Phase 5) and every "legacy_mapped" display derive from these.
# ---------------------------------------------------------------------------

FIVE_TO_NINE: dict[str, int] = {
    "suspicious": 3,
    "highly_suspicious": 4,
    "impossible": 5,
}

# Total over the 5-enum: the two non-accusatory values map to non-problem
# outcomes (and get null severity); the three accusatory values are problems.
OUTCOME_FROM_FIVE: dict[str, str] = {
    "consistent": "pass",
    "indeterminate": "undecided",
    "suspicious": "problem",
    "highly_suspicious": "problem",
    "impossible": "problem",
}

# ---------------------------------------------------------------------------
# Evidence-CHANNEL caps. Every clamp in the pipeline and in adjudicate.apply()
# imports these; a literal severity anywhere else is a defect (spec section
# 7). There is deliberately NO absolute ceiling and no cap keyed on a
# technique's evidence class (v1.14.0): the analysts and the adjudicator may
# rank any rung 1-9. What remains caps the CHANNEL a number arrived through --
# code the agent wrote, a screen, model memory, model arithmetic, a
# quarantined detector -- because that is where the measured false
# accusations came from.
# ---------------------------------------------------------------------------

# R4: agent-written analysis code is probabilistic-class evidence -- it can
# support a correction argument but never mint `impossible`.
AGENT_CODE_CAP = 4

# A screen is a funnel, not evidence (the Table-1 screening lesson); also a DB CHECK.
FAST_SCREEN_CAP = 4

# A memory-based factual claim with no recorded lookup. The plan said
# "capped" without a number; the value is resolved HERE, once.
MODEL_KNOWLEDGE_CAP = 3

# ARITHMETIC ASSERTED RATHER THAN PERFORMED. `model_reading` means the model
# read the numbers off the page and did the sum unaided: no tool call, no
# `inputs` to join one by, no `computed` block. It is a WEAKER channel than
# `agent_code` (4), which at least ran code that can be re-run.
#
# MEASURED 2026-08-22 on 10.1037--0022-3514.94.2.94.2.196. Two findings shipped
# at severity 4 in a `does_not_reconcile` verdict carrying
# `computed_by: model_reading`, `inputs: null`, `computed: null` and no
# tool_verdict -- and one of them is a false positive. `F(1, 142) = 14.06` was
# called "about twice the F from the means", but the paper states a
# "2 x 2 x (time) mixed-design ANOVA" in the same paragraph, so the error term
# is the model's and not the two postattack cells'. Reaching 14.06 needs
# MS_error 1.219; the within-subjects error term at r = 0.47 gives 1.234 -- an
# ordinary pre/post correlation reproduces the printed F exactly.
#
# `recalc_anova` ITSELF returned `suspicious` on those very numbers: the tool
# was right and the finding did not cite it. The codebase already treats
# `model_reading` as weak -- `findings_v2.derive_impossible` refuses it in the
# same breath as `agent_code` -- and only the severity table had never been
# told.
#
# GATED on the technique naming a registered tool (`technique_is_tool`). A
# `not_computational` or `internal_contradiction` warrant has no arithmetic to
# cite and reading the page IS its honest channel; capping those would demote
# three legitimate level-4 findings in the same two runs.
MODEL_READING_CAP = 3

# Quarantined detectors (unmeasured precision) stay `problem` but never rank
# above notable and never headline.
QUARANTINE_CAP = 3

# At/above this a `problem` finding is accusation-grade: it must carry a
# verified quote or a validated tool_verdict, it enters accusation-grade
# fire-rate stats, and draft tooling treats it as publishable criticism.
# Levels 1-2 are record-keeping, not accusations.
ACCUSATORY_MIN = 3

# Caps keyed on the evidence channel handed to clamp_provisional().
# `model_knowledge` is a `basis` value, not a `computed_by` member -- see
# clamp_provisional().
_COMPUTED_BY_CAPS: dict[str, int] = {
    "agent_code": AGENT_CODE_CAP,
    "model_knowledge": MODEL_KNOWLEDGE_CAP,
}

#: Applied ONLY when the technique names a registered tool, so it is kept apart
#: from the unconditional table above rather than guarded at the use site.
_TOOL_TECHNIQUE_COMPUTED_BY_CAPS: dict[str, int] = {
    "model_reading": MODEL_READING_CAP,
}

_PRODUCER_CAPS: dict[str, int] = {
    "fast_screen": FAST_SCREEN_CAP,
}


#: A finding filed under a registered tool, as computed by that tool, is
#: capped by what ITS OWN validated call returned. A check that came back
#: `consistent` cleared the value; one that came back `indeterminate`
#: refused to evaluate it. Either way the tool did not support an
#: accusation, and a finding above these rungs rests on the model's
#: interpretation (which comparison a significance mark denotes, which
#: test was run), not on the arithmetic it cites.
#:
#: MEASURED 2026-10-13 (36 eval runs): "the †/‡ marks on identical means
#: 78.1 vs 78.1 are impossible" was the Level-5 HEADLINE in 6 runs across
#: Claude and Grok with a validated `indeterminate` tool verdict, and the
#: judge called it a false positive each time. Replayed on all 767 kept
#: rows: 19 capped, every one of those headlines among them, and no gold
#: finding pushed below its expected range. `suspicious` is deliberately
#: NOT capped: a cap of 4 there would have lowered a real gold headline
#: (cerebrolysin's Table 3 combined row copying Table 2).
TOOL_VERDICT_CAPS: dict[str, int] = {"consistent": 2, "indeterminate": 3}


def tool_verdict_cap(*, technique_is_tool: bool, computed_by: str | None,
                     tool_verdict: str | None) -> int | None:
    """The `TOOL_VERDICT_CAPS` rung for a row, or None when it does not apply:
    only a registered-tool technique computed by that tool, with a verdict."""
    if technique_is_tool and computed_by == "registry_tool":
        return TOOL_VERDICT_CAPS.get(str(tool_verdict or ""))
    return None


def clamp_provisional(
    sev: int,
    *,
    quarantined: bool = False,
    computed_by: str | None = None,
    producer: str | None = None,
    technique_is_tool: bool = False,
    tool_verdict: str | None = None,
) -> int:
    """Clamp a producer's provisional severity under every applicable
    evidence-CHANNEL cap.

    ALL caps compose by MIN, so application order is irrelevant. There is no
    ceiling keyed on the technique's evidence class and no pipeline maximum: a
    finding whose channel carries no cap keeps whatever rung 1-9 it claimed.
    `computed_by` may also be the finding's `basis` ("model_knowledge"): a
    memory-based claim's evidence channel IS model memory, and the
    `computed_by` enum has no member for it.

    `technique_is_tool` says the technique names a REGISTERED TOOL, which is
    what makes `model_reading` cappable: a finding claiming `recalc_anova` and
    citing no call asserted arithmetic it never performed, while an
    `internal_contradiction` has no arithmetic to cite and reading the page is
    its honest channel. The CALLER decides --
    `findings_v2.clamp_provisionals` reads `registry.BY_NAME` -- because this
    module holds no registry dependency by design.
    """
    if isinstance(sev, bool) or not isinstance(sev, int):
        raise ValueError(
            f"provisional severity must be an int 1-9, got {sev!r}"
        )
    if not 1 <= sev <= 9:
        raise ValueError(
            f"provisional severity must be in 1..9, got {sev}"
        )

    caps: list[int] = []
    if computed_by is not None and computed_by in _COMPUTED_BY_CAPS:
        caps.append(_COMPUTED_BY_CAPS[computed_by])
    if (technique_is_tool and computed_by is not None
            and computed_by in _TOOL_TECHNIQUE_COMPUTED_BY_CAPS):
        caps.append(_TOOL_TECHNIQUE_COMPUTED_BY_CAPS[computed_by])
    if producer is not None and producer in _PRODUCER_CAPS:
        caps.append(_PRODUCER_CAPS[producer])
    if quarantined:
        caps.append(QUARANTINE_CAP)
    cap = tool_verdict_cap(technique_is_tool=technique_is_tool,
                           computed_by=computed_by, tool_verdict=tool_verdict)
    if cap is not None:
        caps.append(cap)
    return min(sev, *caps) if caps else sev


# The per-finding question, verbatim in every prompt that ranks severity.
RUBRIC_QUESTION = (
    "If this one finding were confirmed, and it were the only problem in "
    "the paper, what would the journal have to do about it?"
)

def rubric_markdown() -> str:
    """The ladder digest embedded into agent and adjudicator prompts,
    rendered from `LEVELS` so prompt text cannot drift from the data."""
    lines = [
        "## Severity ladder (1-9)",
        "",
        "Rank each `problem` finding by one question:",
        "",
        f"> {RUBRIC_QUESTION}",
        "",
    ]
    for n in sorted(LEVELS):
        level = LEVELS[n]
        lines.append(
            f"**Level {n} -- `{level.slug}` ({level.label}; "
            f"{level.correction_outcome}).** {level.finding_rubric}"
        )
        lines.append("")
        for test in level.boundaries:
            lines.append(f"- {test}")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Colors: the 9-step concern ramp (docs/specs/webapp_db.md section 8).
# Sequential: slate (1-2, record-keeping) -> amber/orange (3-5, correction
# territory) -> red (6-7, retraction territory) -> deep magenta-red /
# aubergine (8-9). The hue break at 8 is deliberate: misconduct is a KIND
# change, not a shade of worse -- a reader must not be able to mistake an 8
# for a slightly darker 7. `light` is the variant for light backgrounds,
# `dark` for dark backgrounds.
# ---------------------------------------------------------------------------

SEVERITY9_COLORS: dict[int, dict[str, str]] = {
    1: {"light": "#64748b", "dark": "#94a3b8"},  # slate
    2: {"light": "#475569", "dark": "#cbd5e1"},  # slate, firmer
    3: {"light": "#d97706", "dark": "#fbbf24"},  # amber
    4: {"light": "#ea580c", "dark": "#fb923c"},  # orange
    5: {"light": "#c2410c", "dark": "#f97316"},  # deep orange
    6: {"light": "#dc2626", "dark": "#f87171"},  # red
    7: {"light": "#b91c1c", "dark": "#ef4444"},  # deep red
    8: {"light": "#9d174d", "dark": "#f472b6"},  # hue break: magenta-red
    9: {"light": "#581c87", "dark": "#c084fc"},  # aubergine
}


def as_json() -> dict:
    """Export for the TS codegen (`gen-webapp-constants`): ladder + colors +
    maps + caps, so `webapp/lib/constants.gen.ts` is a projection of THIS
    module and a mutated ladder fails the byte-compare drift guard."""
    return {
        "ladder_version": LADDER_VERSION,
        "levels": [
            {
                "n": n,
                "slug": LEVELS[n].slug,
                "label": LEVELS[n].label,
                "correction_outcome": LEVELS[n].correction_outcome,
                "web_summary": LEVELS[n].web_summary,
                "finding_rubric": LEVELS[n].finding_rubric,
                "boundaries": list(LEVELS[n].boundaries),
                "colors": dict(SEVERITY9_COLORS[n]),
            }
            for n in sorted(LEVELS)
        ],
        "five_to_nine": dict(FIVE_TO_NINE),
        "outcome_from_five": dict(OUTCOME_FROM_FIVE),
        "caps": {
            "agent_code": AGENT_CODE_CAP,
            "fast_screen": FAST_SCREEN_CAP,
            "model_knowledge": MODEL_KNOWLEDGE_CAP,
            "model_reading": MODEL_READING_CAP,
            "quarantine": QUARANTINE_CAP,
            "accusatory_min": ACCUSATORY_MIN,
        },
    }
