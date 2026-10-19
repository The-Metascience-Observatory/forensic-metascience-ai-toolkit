"""Deterministic check dispatch: one call per table instead of one per cell.

WHY
---
Measured on two archived runs:

  cerebrolysin  34 turns, 20 tool calls (11 of them sandbox breaches, now denied)
  apple cider   66 turns, 58 tool calls -- of which 51 are the SAME check
                repeated per cell (23 recalc_within_subjects_t, 10 grim_percentage)

Each tool call is a turn, and each turn re-sends ~16,768 tokens of fixed prefix.
The tools are cheap; the turns are the cost. And `stage1_sweep.md` requires a
narration line before AND after each call, so the audit discipline roughly
doubles turn count -- batching pays twice.

THE OBSERVATION THIS RESTS ON
-----------------------------
Once a cell is TYPED (`celltypes` gives it a `kind`) and its variable is
DECLARED (`anatomy` gives family, bounds, bound_source), which checks apply is
DETERMINED, not a judgement. A `mean_sd` cell on an integer variable with stated
bounds implies GRIM, GRIMMER and SPRITE. There is nothing to decide.

So the model's job shrinks to what only it can do -- read the paper, declare
what the variables ARE, and interpret results -- and stops including the
mechanical selection. That also directly serves "limit the model's ability to
perform unaided calculation": it never chooses a tool per number, so it never
has the opportunity to skip one and compute it itself.

WHAT THIS IS NOT
----------------
It is a ROUTER, not a new implementation. Every check goes through
`registry.BY_NAME[tool].call(args)`, so the applicability guards, the `exact`
gate and the withheld parameters are inherited rather than reimplemented. The
dispatcher never rewrites, rounds or re-severities a tool result.

THE PIECES WERE ALREADY WRITTEN AND HAD NO CONSUMER
---------------------------------------------------
`ParsedCell.forensic_kwargs()`, `Variable.forensic_kwargs()` and
`FAMILY_TO_TOOLS` are all tested and were referenced by zero production paths.
The typed-cell-to-arguments bridge existed; nothing called it.
"""

from __future__ import annotations

import re

from typing import Any

from .composite import split_sections
from .tools.celltypes import parse_cells
from .tools.severity import SEVERITY_LEVELS


def _specs():
    """Look up the registry lazily.

    `registry` imports `check_table` from this module at import time, so a
    module-level `from . import registry` here is a cycle. It happened to work
    only because every real entry point imports `registry` first; importing
    `forensic_metascience_ai_toolkit.dispatch` on its own raised ImportError.
    """
    from . import registry as _registry
    return _registry.BY_NAME

def _reproduction(tool: str, args: dict) -> str | None:
    """The `metascience tool run` command replaying this call, or None."""
    from . import registry as _registry
    return _registry.reproduction_command(tool, args)[0]


#: (cell kind, canonical data_type) -> tools that fire.
#:
#: Absence is meaningful and is recorded in `not_run` with a reason, so coverage
#: stops depending on how diligent the model felt. The refusals here are the
#: same ones the tools would make on their own -- dispatching them anyway would
#: work, but it would spend a call to be told no.
DISPATCH: dict[tuple[str, str], tuple[str, ...]] = {
    # mean (SD) -- the granularity family, but ONLY on integer-valued data
    ("mean_sd", "integer"): ("grim_check", "grimmer_check", "sprite_reconstruct"),
    ("mean_sd", "likert"): ("grim_check", "grimmer_check", "sprite_reconstruct"),
    ("mean_sd", "count"): ("grim_check", "grimmer_check", "sprite_reconstruct"),
    ("mean_sd", "binary"): ("debit_check",),
    ("mean_sd", "proportion"): (),
    # This row is the systolic-BP and age-48.90 false accusation, refused by
    # rule rather than by the model remembering.
    ("mean_sd", "continuous"): ("check_sd_or_se",),
    ("mean_sd", "unknown"): (),
    ("mean_sd", "nominal"): (),
    # mean (SE) -- never convert SE to SD here; that is a derivation, not a read
    ("mean_se", "integer"): ("check_sd_or_se",),
    ("mean_se", "likert"): ("check_sd_or_se",),
    ("mean_se", "count"): ("check_sd_or_se",),
    ("mean_se", "continuous"): ("check_sd_or_se",),
    ("mean_se", "unknown"): ("check_sd_or_se",),
    ("mean_se", "binary"): ("check_sd_or_se",),
    ("mean_se", "proportion"): ("check_sd_or_se",),
    # A mean (SE) of a nominal category is not a quantity. Empty BY DECISION,
    # which the closure test below distinguishes from absent.
    ("mean_se", "nominal"): (),
    # n (%) -- percentages are bounded [0,100] whatever the variable is.
    #
    # `check_count_percent` RUNS ALONGSIDE GRIM ON EVERY ROW, and it is the
    # stronger of the two wherever the count is printed. GRIM asks whether a
    # percentage is attainable for SOME integer numerator; the count check asks
    # whether it matches THE numerator the paper printed.
    #
    # MEASURED, and the reason this row changed: a cell reading `142 (73.0)` at
    # n = 200 passes `grim_percentage` as `consistent`, because 73.0 is
    # reachable at k = 146 -- while 100 x 142 / 200 = 71.0. `parse_cells`
    # returned `count: 142` the whole time and `_build_args` dropped it, because
    # `grim_percentage`'s schema has no `count`. A FALSE CLEAR: not a missing
    # check that refuses loudly, but a check answering a nearby question and
    # reporting success.
    ("n_percent", "binary"): ("grim_percentage", "check_count_percent"),
    ("n_percent", "proportion"): ("grim_percentage", "check_count_percent"),
    ("n_percent", "nominal"): ("grim_percentage", "check_count_percent"),
    ("n_percent", "integer"): ("grim_percentage", "check_count_percent"),
    ("n_percent", "likert"): ("grim_percentage", "check_count_percent"),
    ("n_percent", "count"): ("grim_percentage", "check_count_percent"),
    ("n_percent", "continuous"): ("grim_percentage", "check_count_percent"),
    ("n_percent", "unknown"): ("grim_percentage", "check_count_percent"),
    # count/denominator (%) -- `12/30 (40.0)`, where the paper PRINTS its own
    # denominator. Routed exactly like `n_percent` because a percentage is
    # bounded [0,100] whatever the variable is, but on strictly better evidence:
    # `n_percent` has to infer the n from a column header, a row above, or a
    # reconstructed section total, and each of those can manufacture an
    # impossibility. Here the paper states it.
    #
    # THIS KIND WAS TYPED AND THEN NEVER DISPATCHED. celltypes has emitted
    # `count_denominator_percent` since f009ee3; DISPATCHABLE_KINDS never
    # gained it and DISPATCH never gained a row, so every such cell fell to
    # "no check defined" -- the best-evidenced percentage cell in the corpus
    # was the one cell form nothing checked.
    ("count_denominator_percent", "binary"): ("grim_percentage", "check_count_percent"),
    ("count_denominator_percent", "proportion"): ("grim_percentage", "check_count_percent"),
    ("count_denominator_percent", "nominal"): ("grim_percentage", "check_count_percent"),
    ("count_denominator_percent", "integer"): ("grim_percentage", "check_count_percent"),
    ("count_denominator_percent", "likert"): ("grim_percentage", "check_count_percent"),
    ("count_denominator_percent", "count"): ("grim_percentage", "check_count_percent"),
    ("count_denominator_percent", "continuous"): ("grim_percentage", "check_count_percent"),
    ("count_denominator_percent", "unknown"): ("grim_percentage", "check_count_percent"),
    # estimate (CI) -- the highest-yield cell type on a clinical corpus.
    #
    # THE FOUR ROWS BELOW WERE MISSING, and their absence produced the worst
    # possible incentive: DECLARING MORE INFORMATION TURNED THE CHECK OFF. An
    # `estimate_ci` cell with no variable bound fell to ("estimate_ci",
    # "unknown") and ran; the same cell bound to a declared likert_item
    # variable matched no key and was refused as "no check defined". MEASURED:
    # 39 real cells refused for exactly this on
    # eval/ground_truth/papers/10.3389--fpsyg.2019.02949, 19% of all observed
    # in-table refusals.
    #
    # `check_estimate_ci` is interval arithmetic -- does the point estimate sit
    # where its own confidence interval says it should -- and that question does
    # not depend on the family. It caps at `suspicious`, so no row here can
    # produce an accusation by itself.
    ("estimate_ci", "continuous"): ("check_estimate_ci",),
    ("estimate_ci", "binary"): ("check_estimate_ci",),
    ("estimate_ci", "proportion"): ("check_estimate_ci",),
    ("estimate_ci", "unknown"): ("check_estimate_ci",),
    ("estimate_ci", "integer"): ("check_estimate_ci",),
    ("estimate_ci", "likert"): ("check_estimate_ci",),
    ("estimate_ci", "count"): ("check_estimate_ci",),
    # An odds ratio with a CI on a nominal outcome is ordinary and checkable.
    ("estimate_ci", "nominal"): ("check_estimate_ci",),
}

#: The canonical `data_type` values: the image of `Variable.forensic_kwargs`'
#: family map, plus the undeclared case.
#:
#: Pinned so that the completeness test below fails when anatomy grows a family
#: whose data_type nobody routed. THE HOLE ABOVE EXISTED BECAUSE NOBODY EVER
#: ENUMERATED THIS KEY SPACE -- a missing key is indistinguishable from a
#: deliberate refusal, so four oversights sat next to eight decisions and read
#: identically.
CANONICAL_DATA_TYPES = frozenset({
    "binary", "count", "likert", "proportion",
    "continuous", "integer", "nominal", "unknown",
})

#: Cell kinds that reach DISPATCH: every `celltypes.CELL_KINDS` value that
#: `NEVER_DISPATCH` does not turn away first.
DISPATCHABLE_KINDS = frozenset({"mean_sd", "mean_se", "n_percent", "estimate_ci",
                                "count_denominator_percent"})

#: Cell kinds whose percentage is a count's share of the sample.
_SHARE_KINDS = frozenset({"n_percent", "count_denominator_percent"})

#: `n = 59`, `N=120`, `n = 1,204` -- as printed in a column header or row label.
#: `=` AS THE PDF ACTUALLY ENCODED IT. Older Springer PDFs render `=` as `¼`
#: -- a Type-1 font-encoding artifact, not an OCR guess -- so `n = 68` reaches
#: us as `n ¼ 68`. MEASURED over the 305-paper cerebrolysin corpus: 16 papers
#: (5.2%) contain `n ¼ <digit>`, 107 occurrences.
#:
#: The cost is total where it bites. On 10.1007--s00702-004-0248-2 the column
#: header reads `Placebo (n ¼ 68)`, so the denominator printed directly above
#: the cells could not be read and ALL 24 of that paper's checkable percentage
#: groups were refused for want of it.
#:
#: REPAIRED IN CONTEXT, NEVER GLOBALLY. `¼` means one quarter elsewhere, so it
#: is not a character this codebase may rewrite on sight -- `celltypes.
#: _UNICODE_REPAIRS` is deliberately not the place for it. Between an `n` and a
#: digit it can mean nothing else.
_EQ = r"[=\u00bc]"

#: THE COMMA GROUP IS `+`, NOT `*`, AND THE DIFFERENCE IS A FALSE ACCUSATION.
#: With `*` the first alternative matches THREE digits with the comma group
#: empty and succeeds; `finditer` has nothing after the group to force
#: backtracking, so an unseparated 4+ digit sample size is silently TRUNCATED:
#: `N=2749` read as 274, `N = 10432` as 104, `n = 1293` as 129.
#:
#: That wrong premise reaches `values._stated_n` -> `check_stated_denominators`
#: at column level, where `explaining_denominator` searches only DOWNWARD from
#: the stated n -- so a percentage computed over 2,749 can never be reproduced
#: from any denominator <= 274, and every ordinary count in the column is
#: recorded `suspicious`. Measured on a four-row honest table whose arithmetic
#: is exact against N = 2749: THREE false `suspicious` before, `consistent` on
#: all four after.
#:
#: Requiring the comma makes the alternation unambiguous: the comma form must
#: contain a comma, so a bare run of digits can only take the `\d+` branch.
#: Regression cases: N=2749, N = 1165, N = 10432, n = 1293, n = 1,204,
#: n = 1,234,567, n ¼ 68, fullwidth `(N=2749）`.
#:
#: The sibling copies of this alternation in `celltypes` and `cellformat` are
#: SAFE and were checked rather than assumed -- every use there is inside a
#: `re.fullmatch` with a trailing anchor, so backtracking rescues them. This is
#: the only unanchored `finditer` use, which is the argument for one facet
#: grammar instead of four hand-copied regexes.
_N_IN_LABEL = re.compile(rf"\b[Nn]\s*{_EQ}\s*(\d{{1,3}}(?:,\d{{3}})+|\d+)")


#: How a stacked column header joins its levels, OUTERMOST FIRST.
#: `extraction.jats._composite_labels` writes it; everything that reads a level
#: out of a label reads it through here. Written by hand at one end and read by
#: hand at the other is how three separate defects arrived today.
HEADER_LEVEL_SEP = " | "


def header_ns(label: Any) -> list[dict]:
    """Every sample size a header states, INNERMOST LEVEL FIRST.

    A stacked column header states its size twice, at two scopes:

        "PP Population, n = 318 | Cerebrolysin , n = 117"

    318 covers the pair of columns grouped under it. 117 is what THIS column's
    numbers were divided by. Levels are joined outermost-first, so anything
    taking the first regex match takes the grouping -- which is also the LARGER
    number, and this module's own `_refusal_reason` warns that a check "accuses
    when n is too large". It was recommending the most dangerous candidate it
    had.

    Innermost first, each labelled with its scope, so a caller can prefer the
    column's own figure and still see what the grouping said.
    """
    out: list[dict] = []
    parts = str(label or "").split(HEADER_LEVEL_SEP)
    for i in range(len(parts) - 1, -1, -1):
        for m in _N_IN_LABEL.finditer(parts[i]):
            out.append({"n": int(m.group(1).replace(",", "")),
                        "level": "column" if i == len(parts) - 1 else "group"})
    return out


def _n_in_labels(raw_cell: dict) -> list[tuple[str, int]]:
    """Group sizes printed in this cell's own labels.

    MEASURED on the archived ledgers: every one of the 71 missing-`n` refusals
    was for an n that WAS available, and in the worst case it was inside the
    refused call's own arguments -- `col_label: "Cerebrolysin (n = 59)"`, with
    the dispatcher refusing for want of the number it had just been handed. The
    same figure appears 25 more times in that paper's body text.
    """
    found = []
    for key in ("col_label", "row_label"):
        text = raw_cell.get(key)
        if not isinstance(text, str):
            continue
        # INNERMOST FIRST. `_refusal_reason` reads `found[0]` and tells the
        # reader which n to pass; on a stacked header that used to be the
        # grouping total rather than the column's own size.
        for hit in header_ns(text):
            found.append((key, hit["n"]))
    return found


def _refusal_reason(spec, n, raw_cell: dict) -> str:
    """Name what is missing, and where the reader could get it.

    A refusal that names its own discharge turns a silent loss into a one-turn
    fix. It deliberately does NOT auto-supply the n: a header n is the ENROLLED
    count, not necessarily the count behind a particular row (missing data,
    per-protocol subsets), and GRIM run with too large an n accuses. Naming the
    candidate is help; using it unasked is the false accusation this module
    exists to prevent.
    """
    wants_n = any(p.name == "n" and p.required for p in spec.params)
    if not (wants_n and n is None):
        return "required inputs not present in this cell"
    candidates = _n_in_labels(raw_cell)
    if not candidates:
        return (f"{spec.name} needs n and this cell carries none; supply n for this row "
                f"(the participants paragraph or the table footnote usually states it)")
    where, value = candidates[0]
    # NAME THE OTHERS TOO. A stacked header offers more than one n, and the
    # reader deciding which to pass should see that rather than be handed one
    # figure as though it were the only candidate.
    others = sorted({v for _w, v in candidates} - {value})
    also = (f" Its labels also print {', '.join('n = ' + str(v) for v in others)}"
            f", which cover wider groupings." if others else "")
    return (f"{spec.name} needs n and this cell carries none, but its {where} prints "
            f"'n = {value}'. Pass n={value} explicitly to run this check -- it is not "
            f"used automatically, because an enrolled n is not always the n behind a "
            f"given row, and this check accuses when n is too large.{also}")


#: Why a (kind, data_type) pair runs nothing. Recorded verbatim in `not_run`.
WHY_NOT: dict[tuple[str, str], str] = {
    ("mean_sd", "continuous"):
        "granularity checks assume integer observations; a continuous mean is not "
        "constrained to multiples of 1/n (this is the systolic-BP false accusation)",
    ("mean_sd", "proportion"):
        "a proportion's mean/SD is not an integer sample; use the n (%) cells instead",
    ("mean_sd", "unknown"):
        "variable not typed. Running on defaults is the single most common route to "
        "a false accusation, so nothing runs until the family is declared",
    ("mean_sd", "nominal"):
        "a mean of an unordered category is a typing problem, not an anomaly",
    ("mean_se", "nominal"):
        "a mean and standard error of an unordered category is not a quantity; as with "
        "mean (SD) on the same family, the cell is mistyped rather than anomalous",
}

#: Cell kinds that never dispatch anything, whatever the variable.
NEVER_DISPATCH: dict[str, str] = {
    "ambiguous": "cell meaning is ambiguous; running any tool on a value whose meaning "
                 "is unknown is how false accusations are made",
    "non_numeric": "not a numeric cell",
    "reference_category": "the level other levels are compared AGAINST; its 1 is "
                          "true by construction, has no interval, and no check can "
                          "confirm or refute a definition. Recorded so a reader "
                          "tracing an odds ratio sees what it is relative to",
    "censored": "a bound, not a point value: `p < 0.001` is not `p = 0.001`, and "
                "handing a checker the bound as though it were the number gives it "
                "a precision the paper never claimed. The value is RECORDED with "
                "its operator so a reader sees the bound; no tool consumes it",
    "numeric": "a bare number carries no dispersion or denominator to check",
    "count": "a bare count contributes to table-level checks only",
    "median_iqr": "median summaries carry no mean/SD granularity",
    "median_range": "median summaries carry no mean/SD granularity; the range may still "
                    "supply STATED bounds for this variable's mean (SD) cells",
}


#: Families whose granularity checks are NOT safely dispatchable yet.
#:
#: A multi-item composite's mean moves in steps of 1/(items*n), not 1/n --
#: PHQ-9 at 9 items and n=42 has granularity 0.00265, not 0.0238. `grim_test`
#: has no `items` parameter, so dispatching a composite to it uses the wrong
#: denominator and returns `impossible` on a perfectly ordinary value. Verified:
#: mean 12.30, n=42, 9 items comes back `impossible`.
#:
#: Refusing is the correct behaviour until `items` is plumbed through. Running
#: a check whose denominator we know to be wrong is precisely the false
#: accusation this toolkit exists to avoid, and batching it would have turned
#: one such error into one per composite row.
COMPOSITE_FAMILIES = frozenset({"likert_composite"})

#: Checks that need a BOUNDED scale and silently invent one if not given.
#:
#: `sprite_reconstruct` and `grimmer_test` both default to scale_min=1,
#: scale_max=7 -- a Likert scale, applied to whatever they are handed. Measured
#: on a real paper: "Number of coalition members", mean 35.78, SD 33.74, n=64,
#: declared `count` with NO stated bounds. SPRITE assumed [1, 7], computed that
#: the implied total of 2290 exceeds its imagined maximum of 448, and returned
#: `impossible`. GRIMMER failed the same way, its candidate sums confined to the
#: invented range. The paper was fine; 2290/64 = 35.78125 rounds to 35.78.
#:
#: `grim_check` got the same cell right, returning `suspicious`, because it caps
#: severity when `bound_source` is assumed. These two have no such cap.
#:
#: Counts are unbounded above. Refusing is the only correct answer when the
#: bound is unknown, and it is the same rule the rest of the system follows:
#: an unverified precondition yields `indeterminate`, never a verdict.
_NEEDS_STATED_BOUNDS = frozenset({"sprite_reconstruct", "grimmer_check"})

#: Families with no natural upper bound, where a default scale is always wrong.
_UNBOUNDED_FAMILIES = frozenset({"count", "continuous", "time_to_event", "ratio"})

UNBOUNDED_REASON = (
    "this check needs a STATED scale maximum and the paper does not give one. It "
    "would otherwise fall back to a default 1-7 Likert scale, which for an "
    "unbounded variable manufactures an impossibility out of an ordinary value "
    "(measured: a mean of 35.78 members at n=64 reported `impossible` against an "
    "invented maximum of 7)."
)

NOT_ENABLED_REASON = (
    "tool not enabled in this pipeline: the run was configured with a toolset "
    "that excludes this check, so the cell was not checked by it (not a pass)."
)


def _drop_unbounded(tools: tuple, variable: dict | None) -> tuple[tuple, set]:
    """Remove bounded-scale checks when the variable's bounds were not stated."""
    var = variable or {}
    family = str(var.get("family") or "").lower()
    has_upper = var.get("upper_bound") is not None
    if has_upper or family not in _UNBOUNDED_FAMILIES:
        return tools, set()
    refused = {t for t in tools if t in _NEEDS_STATED_BOUNDS}
    return tuple(t for t in tools if t not in refused), refused


COMPOSITE_REASON = (
    "multi-item composite whose scoring is undeclared. If the score is a MEAN of "
    "items its granularity is 1/(items*n) and grim_test has no `items` parameter, "
    "so checking at 1/n would manufacture an impossibility; if it is a SUM the "
    "granularity is 1/n and the check is valid. Declare `derivation` as "
    "'mean_of_items' or 'sum_of_items' to resolve this -- the field is already in "
    "the schema and the prompt asks for it."
)

COMPOSITE_MEAN_REASON = (
    "composite scored as a MEAN of items: granularity is 1/(items*n), not 1/n, and "
    "grim_test has no `items` parameter. Checking at 1/n would manufacture an "
    "impossibility. Refused until `items` is plumbed through."
)

#: A composite scored as a SUM needs no new machinery at all.
#:
#: Each subject's total is an INTEGER -- a PHQ-9 total is 0-27 per person -- so
#: the group mean moves in steps of 1/n exactly like any other integer variable,
#: and ordinary GRIM is correct. The blanket refusal was written from the
#: item-MEAN model and suppressed this case with it.
#:
#: MEASURED: mean 12.27 at n=42 on a PHQ-9 TOTAL has ZERO integer solutions at
#: 1/42 and three at 1/378. `impossible` is the right answer and we were not
#: giving it. The repo's own `test_the_underlying_false_positive_is_real` uses
#: this same sum-score example to justify a refusal whose stated rationale is the
#: item-mean model -- two opposite cases, conflated, because the field that
#: distinguishes them was being dropped on load.
#: Canonical home is `anatomy`, which needs them for `forensic_kwargs` and
#: cannot import this module. Re-exported so every reference keeps working and
#: the two copies cannot drift apart.
from .anatomy import MEAN_SCORED, SUM_SCORED  # noqa: E402


def _as_variable(variable: dict):
    """Build an anatomy Variable from a partial declaration.

    `id` and `name` are required by the dataclass but carry no forensic meaning,
    and a caller declaring `{"id": "v1", "family": "continuous"}` is giving us
    everything that matters. Without defaults the constructor raised, the caller
    fell into the except branch, and a correctly-typed continuous variable was
    reported as "variable not typed" -- a refusal blamed on the user for our
    own TypeError.
    """
    from .anatomy import PIPELINE_ONLY_FIELDS, Variable

    # PIPELINE_ONLY_FIELDS is stripped here as well as in `anatomy._pick`,
    # because this is the OTHER construction path -- and it is the only one
    # stage 2 has. A guard on one path is a guard the other path walks around.
    allowed = set(Variable.__dataclass_fields__) - PIPELINE_ONLY_FIELDS
    fields = {k: v for k, v in variable.items() if k in allowed}
    fields.setdefault("id", variable.get("id", "v"))
    fields.setdefault("name", variable.get("name", fields["id"]))
    var = Variable(**fields)
    # STRIP THE MODEL'S CLAIM, THEN WRITE OUR OWN. The order is the whole point:
    # whatever `provenance_verdict` the model supplied was discarded two lines
    # above, and this adjudicates the quote against the paper itself. A verdict
    # the model cannot forge, arrived at BEFORE the checks run.
    verdict = _verify_variable_quote(var.provenance_quote)
    if verdict:
        var.provenance_verdict = verdict
    return var


#: Built once per process from the paper the PIPELINE named (never the model --
#: see `agent.PAPER_DIR_ENV`). `False` means we tried and could not; `None`
#: means not tried yet. Conflating those is how a missing haystack becomes a
#: silent, permanent "assumed" that nobody can distinguish from a real verdict.
_HAYSTACK: dict | None | bool = None

#: `quotes.fold_haystack(_HAYSTACK)`, built beside it and cached for the same
#: reason: this runs once per DECLARED VARIABLE, and re-folding the paper on
#: every variable would charge a paid run for the same work repeatedly.
_FOLDED: dict | None = None


def _haystack() -> dict | None:
    """The paper's text, for adjudicating a variable's quote before dispatch.

    Read from `METASCIENCE_PAPER_DIR`, which the pipeline sets on the tool
    server's environment. The model has no way to write it -- the same property
    `PIPELINE_ONLY_FIELDS` gives the in-payload fields, here at the process
    boundary.
    """
    global _HAYSTACK, _FOLDED
    if _HAYSTACK is None:
        import os

        _HAYSTACK = False
        pdir = os.environ.get("METASCIENCE_PAPER_DIR")
        if pdir:
            try:
                from .quotes import build_haystack, fold_haystack

                _HAYSTACK = build_haystack(pdir) or False
                if _HAYSTACK:
                    _FOLDED = fold_haystack(_HAYSTACK)
            except Exception:  # noqa: BLE001
                _HAYSTACK = False
                _FOLDED = None
    return _HAYSTACK or None


def _verify_variable_quote(quote: str | None) -> str | None:
    """Is this variable's `provenance_quote` actually in the paper?

    THE GAP THIS CLOSES. `Variable.bounds_are_stated` and
    `Variable.discreteness_source` both refuse to license `impossible` without a
    pipeline-set `provenance_verdict` -- deliberately, so the model cannot
    certify its own quote (#87). But that verdict was written by
    `agent._annotate_quotes`, which runs AFTER the model's tool calls.

    MEASURED across every archived run: not one variable has ever reached
    `check_table` carrying a verdict. Both gates were therefore ABSOLUTE rather
    than evidential -- on the table path, which is where the volume is, a
    granularity or range failure could never reach `impossible` whatever the
    paper said. That is safe, but it is not what either gate was designed to do,
    and a gate that always says no is indistinguishable from a broken one.

    SILENT ON FAILURE BY DESIGN, and the direction matters. No haystack, no
    verdict, and the variable keeps `assumed` -- the capped reading. Stamping
    `absent` because we could not open the paper would convert OUR failure into
    a statement about the authors' quote, which is the house mistake this
    codebase keeps having to unlearn.
    """
    if not (quote or "").strip():
        return None
    hay = _haystack()
    if not hay:
        return None
    try:
        from .quotes import classify

        return classify(quote, hay, _FOLDED).get("quote_verified")
    except Exception:  # noqa: BLE001
        return None


def _is_composite(variable: dict | None) -> bool:
    """Does this composite still have to be refused, and why?

    Returns False for a composite the paper scores as a SUM: each subject's
    total is an integer, so 1/n is the correct granularity and ordinary GRIM
    applies. Only the item-MEAN case and the undeclared case are refused.

    DERIVATION IS CHECKED BEFORE FAMILY, and the order matters. This test gated
    on `family in COMPOSITE_FAMILIES` first, so a variable that correctly
    declared `derivation: mean_of_items` was IGNORED whenever its family sat
    outside that set -- and a five-item scale averaged to a continuous score is
    naturally declared `continuous`, not `likert_composite`. Verified 2026-08-28:
    with `derivation: mean_of_items` and `n_items: 5`, the refusal fires for
    family `likert_composite` and does not fire for `continuous`,
    `ordinal_category` or `unknown`.

    `derivation` is the field that settles the denominator -- a mean of k items
    has granularity 1/(k*n) whatever the family is called -- so it decides here.
    Family remains the fallback for the UNDECLARED case, which is the other
    thing this refusal exists for.
    """
    if not variable:
        return False
    if str(variable.get("derivation") or "") in MEAN_SCORED:
        return True
    if variable.get("family") not in COMPOSITE_FAMILIES:
        return False
    return str(variable.get("derivation") or "") not in SUM_SCORED


def _composite_reason(variable: dict | None) -> str:
    deriv = str((variable or {}).get("derivation") or "")
    return COMPOSITE_MEAN_REASON if deriv in MEAN_SCORED else COMPOSITE_REASON


def _canonical_type(variable: dict | None) -> str:
    """The variable's canonical data_type, or `unknown` when undeclared."""
    if not variable:
        return "unknown"

    try:
        kwargs = _as_variable(variable).forensic_kwargs()
    except Exception:
        return "unknown"
    return kwargs.get("data_type", "unknown")


#: Declaring a row costs one short dict; NOT declaring it is the single largest
#: coverage loss in the system. MEASURED on a real paper: 79 checkable cells, 76
#: blocked for want of a declaration, 0 checked.
#:
#: Nothing is missing from the plumbing. `variables` and `bindings` arrive in the
#: SAME call, and the dispatcher already refuses correctly and says why. What it
#: never did was hand back the FORM -- so the cure for the commonest refusal in
#: the system lived only in a prompt instruction, and a rule the model has to
#: remember is a rule it will sometimes not. A refusal that carries its own cure
#: is the pattern `_refusal_reason` already applies to a missing `n`.
#: Offered as declarations. These are anatomy FAMILIES (what the model writes),
#: not the canonical data_types DISPATCH is keyed on -- the two are related by
#: `Variable.forensic_kwargs`, and asking for a data_type would be asking the
#: model to do our mapping for us.
_DECLARABLE_FAMILIES = ("binary", "count", "likert_item", "likert_composite",
                        "proportion", "continuous")


def _declaration_template(blocked: dict[str, list[dict]]) -> list[dict]:
    """For each row blocked only for want of a declaration, the form to fill.

    `would_unlock` is not written out. Each candidate family is SIMULATED
    through the real `_resolve_ambiguous` and `DISPATCH`, so what the form
    promises is exactly what the dispatcher would do. Hand-writing it would be a
    second copy of the routing table, and this module exists because one copy is
    already hard enough to keep true.

    A family that unlocks nothing for the cells actually on that row is omitted:
    offering it would invite a declaration that buys the reader nothing.
    """
    out: list[dict] = []
    for row, cells in sorted(blocked.items()):
        unlocks: dict[str, set[str]] = {}
        resolves_to: dict[str, set[str]] = {}
        for family in _DECLARABLE_FAMILIES:
            probe = {"id": "_probe", "name": row, "family": family,
                     "scale_min": 0, "scale_max": 100, "bounds_are_stated": True}
            dtype = _canonical_type(probe)
            for cell in cells:
                resolved = _resolve_ambiguous(dict(cell), probe)
                kind = resolved.get("kind")
                if kind in NEVER_DISPATCH or not kind:
                    continue
                tools = DISPATCH.get((kind, dtype))
                if tools:
                    unlocks.setdefault(family, set()).update(tools)
                    resolves_to.setdefault(family, set()).add(kind)
        if not unlocks:
            continue
        out.append({
            "row_label": row,
            "n_cells": len(cells),
            "declare": {
                "id": "<a short id you choose, e.g. 'age'>",
                "name": row,
                "family": f"<one of: {', '.join(sorted(unlocks))}>",
                "scale_min": "<lowest possible value, or null if unbounded>",
                "scale_max": "<highest possible value, or null if unbounded>",
                "bounds_are_stated": "<true ONLY if the PAPER states the range>",
                "derivation": "<omit unless composite; then 'sum' or 'mean'>",
            },
            "bind": {row: "<the id you chose above>"},
            "would_unlock": {
                f: {"reads_the_cells_as": sorted(resolves_to.get(f, ())),
                    "runs": sorted(t)}
                for f, t in sorted(unlocks.items())
            },
            # THE FORM MUST NOT REWARD OVER-DECLARING. `would_unlock` lists more
            # tools for some families than others, and a reader optimising for
            # coverage would pick the longest list. On an n(%) row like
            # "31 (51.7)", declaring `count` makes the resolver read it as
            # mean = 31, SD = 51.7 and run GRIM on a mean that does not exist --
            # a fabricated input producing a fabricated accusation, which is the
            # worst output this toolkit can produce. The list is what WOULD
            # happen, not a menu of options ranked by desirability.
            "caution": (
                "Declare what the paper says this variable IS, never whichever "
                "family unlocks the most checks. A wrong family changes how the "
                "cell is READ -- an n(%) row declared as a count is re-read as "
                "mean(SD) -- and every check then runs on values the paper never "
                "reported. Leaving it undeclared costs coverage; declaring it "
                "wrongly manufactures accusations."
            ),
        })
    return out


def _variable_kwargs(variable: dict | None, share: bool = False) -> dict:
    if not variable:
        return {"data_type": "unknown", "bound_source": "assumed"}

    try:
        return _as_variable(variable).forensic_kwargs(share=share)
    except Exception:
        return {"data_type": "unknown", "bound_source": "assumed"}


#: A declared variable resolves what a row label could not.
#:
#: `celltypes` marks `48.90 (14.46)` ambiguous when the label is bare ("Age"),
#: which is right in isolation -- it could be mean(SD), n(%) or estimate(CI).
#: But once the model has DECLARED that Age is a continuous variable, the
#: reading is determined. This is what makes declaring variables worth doing:
#: it recovers cells that pure syntax has to refuse.
#:
#: It is not a licence to guess. Resolution happens only from an EXPLICIT
#: declaration, never from a default, and an undeclared variable leaves the
#: cell ambiguous and unchecked.
_FAMILY_RESOLVES_TO = {
    "continuous": "mean_sd", "count": "mean_sd", "likert_item": "mean_sd",
    "likert_composite": "mean_sd", "time_to_event": "mean_sd",
    "binary": "n_percent", "nominal_category": "n_percent", "proportion": "n_percent",
}


def _resolve_ambiguous(cell: dict, variable: dict | None) -> dict:
    """Re-read an ambiguous cell using the declared family, or leave it alone.

    THIS IS THE PATH THAT UNCAPS SEVERITY. An `ambiguous` cell is refused by
    every check; resolving it here is what lets the exact-arithmetic tools run,
    and a declared variable is what lets them reach `impossible`. So the
    numbers this function extracts had better be the numbers the paper printed.
    Twice they were not:

      * `1,234 (56.7)` under a declared CONTINUOUS variable resolved to
        mean=1.0, sd=234.0. The old pattern could not span a digit-group comma,
        so `re.findall` cut `1,234` into `1` and `234` and the `.replace(",","")`
        afterwards had nothing left to fix. Two fabricated numbers, handed to
        GRIM/GRIMMER/SPRITE with the severity cap already lifted.
      * `48.9 (7.1)` under a declared BINARY variable resolved to count=48, by
        truncating a mean into a count. A count is a whole thing; 48.9 of them
        is not a count that was misread, it is a count that never existed.

    Both are now refusals: the cell stays `ambiguous`, which every check
    declines rather than judges.
    """
    if cell.get("kind") != "ambiguous" or not variable:
        return cell
    target = _FAMILY_RESOLVES_TO.get(variable.get("family"))
    if not target:
        return cell
    candidates = cell.get("candidates") or []
    if target not in candidates:
        return cell
    import re

    from .tools.celltypes import _NUM

    # The SAME pattern `celltypes` parses with. Two number patterns in one
    # pipeline is two chances to disagree about what a cell contains, and the
    # disagreement is silent.
    nums = [float(x.replace(",", "")) for x in
            re.findall(_NUM, str(cell.get("raw", ""))) if x.strip()]
    if len(nums) < 2:
        return cell
    resolved = dict(cell)
    resolved["kind"] = target
    resolved["resolved_by"] = f"declared family={variable.get('family')}"
    if target == "mean_sd":
        resolved["value"], resolved["sd"] = nums[0], nums[1]
    else:
        # A count must BE a count, and a percentage must be a percentage. A
        # declaration says what the variable is, not what the cell says; where
        # the two disagree, the declaration is the thing more likely to be
        # wrong, and refusing costs one check while resolving costs a false
        # accusation.
        if not float(nums[0]).is_integer() or not (0.0 <= nums[1] <= 100.0):
            return cell
        resolved["value"], resolved["count"], resolved["percent"] = nums[0], int(nums[0]), nums[1]
    return resolved


#: How many rows must agree on the SAME unstated denominator before the
#: disagreement is read as the section's denominator rather than as errors.
#: Two is enough: one row implying n=340 against a header n=352 is a coincidence
#: worth a shrug, and two rows implying the SAME 340 is a fact about the table.
_SHARED_DENOM_MIN_ROWS = 2

#: How far below the header n a LONE row's implied denominator may sit and still
#: read as item non-response rather than an error. 5% of a 352-patient column is
#: about 18 patients; the two real cases sit 7 and 8 below. Beyond this the gap
#: is too large to be non-response on a single item and the row stays accusable.
_LONE_DENOM_MAX_GAP = 0.05


def _clamp_shared_denominator(results: list[dict]) -> None:
    """Rows that agree on ONE unstated denominator are reporting, not erring.

    MEASURED, and this is why it exists. A harness-fired sweep over 87 corpus
    papers produced 21 accusatory flags from 556 checks; 8 of them were
    `check_count_percent` on ONE table of an honest PLoS ONE paper, and every
    one recomputes like this:

         90/352 = 25.57%   printed 26.5%   -> implies n = 340
        127/352 = 36.08%   printed 37.3%   -> implies n = 340
        123/352 = 34.94%   printed 36.2%   -> implies n = 340
        256/598 = 42.81%   printed 45.5%   -> implies n = 563
        209/598 = 34.95%   printed 37.1%   -> implies n = 563
         98/598 = 16.39%   printed 17.4%   -> implies n = 563

    THE CONSISTENCY IS THE WHOLE SIGNAL. Three rows landing on exactly 340 and
    three on exactly 563 is a paper computing its percentages over respondents
    who answered THAT item -- routine in survey work, where the header n is the
    sample and the denominator is the sample minus missing. Errors do not agree
    with each other; a denominator does.

    So the flags are not deleted -- a reader still sees that the printed
    percentage disagrees with the header n, which is a real and useful fact --
    but they are capped at `indeterminate` and told what the implied denominator
    is. The paper is not accused of arithmetic it did not get wrong; we are
    told which number we were missing.

    Mutates `results` in place, which is how the surrounding code works.
    """
    from collections import defaultdict

    by_denom: dict[tuple, list[dict]] = defaultdict(list)
    for r in results:
        if r.get("tool") != "check_count_percent":
            continue
        if r.get("severity") not in ("suspicious", "highly_suspicious", "impossible"):
            continue
        args = r.get("inputs") or {}
        count, pct, n = args.get("count"), args.get("percentage"), args.get("n")
        if not count or not pct or not n:
            continue
        implied = round(100.0 * count / pct)
        if implied and implied != n:
            by_denom[(n, implied)].append(r)

    # HOW MANY ROWS OF THIS COLUMN ARE LEFT UNEXPLAINED. A group of two or more
    # explains itself -- those rows agree on a denominator. What matters for a
    # singleton is whether the REST of its column is accounted for.
    #
    # MEASURED on PLoS ONE 0128753 Table 1, column n=352: thirteen flagged rows,
    # twelve of them in agreeing groups (350, 349, 340 and 351 each appearing
    # two or more times) and exactly one -- 345 -- alone. A column otherwise
    # fully explained by shared denominators, with one straggler seven below the
    # header, is another item's non-response. A column with SEVERAL unexplained
    # disagreements is error-shaped, and every one of them stays accusable.
    unexplained: dict[Any, int] = {}
    for (header_n, _implied), group in by_denom.items():
        if len(group) < _SHARED_DENOM_MIN_ROWS:
            unexplained[header_n] = unexplained.get(header_n, 0) + len(group)

    for (header_n, implied), group in by_denom.items():
        if len(group) < _SHARED_DENOM_MIN_ROWS:
            if unexplained.get(header_n, 0) != 1:
                continue
            # A LONE ROW HAS NO ONE TO AGREE WITH, and the agreement is the
            # whole signal above. But the shape is still recognisable, and a
            # row that is alone in a column is alone by accident -- it is the
            # only cell of its column we could type, not the only cell the
            # paper printed.
            #
            # MEASURED 2026-08-20 on PLoS ONE 0128753 Table 1:
            #     10 (2.9%)   header n = 352   implies 345   (7 below)
            #    587 (99.5%)  header n = 598   implies 590   (8 below)
            # Both are item non-response -- the header n is the sample, the
            # denominator is the sample minus those who did not answer that
            # item. From ONE row that is indistinguishable from a one-digit
            # slip in the percentage, and no arithmetic can separate them.
            #
            # BOUNDED TWO WAYS, because this softens a guard rather than adding
            # one. Only DOWNWARD: a denominator above the sample is not missing
            # data, it is an error, and stays accusable. And only NEAR: a gap
            # beyond `_LONE_DENOM_MAX_GAP` of the header is too large to be
            # non-response on an item and keeps its severity.
            #
            # The trade is deliberate. Softened, a real slip still reaches the
            # reader as `indeterminate` WITH its implied denominator named;
            # unsoftened, an honest paper is accused. Greg's call, 2026-08-20.
            if not (0 < header_n - implied <= _LONE_DENOM_MAX_GAP * header_n):
                continue
            r = group[0]
            r["severity"] = "indeterminate"
            r["clamped_by"] = "lone_row_near_denominator"
            r["clamp_reason"] = (
                f"this row implies n={implied}, {header_n - implied} below the "
                f"header's n={header_n} -- the shape of item non-response, where "
                "the header is the sample and the denominator is the sample "
                "minus those who did not answer this item. It is the ONLY row "
                "of this column we could type, so there is no second row to "
                "confirm the denominator, and from one row this is "
                "indistinguishable from a slip in the printed percentage. "
                "Reported, not alleged: confirm what n=" f"{implied} refers to "
                "before treating it as a finding.")
            continue
        for r in group:
            r["severity"] = "indeterminate"
            r["clamped_by"] = "shared_section_denominator"
            r["clamp_reason"] = (
                f"{len(group)} rows of this table imply the SAME denominator "
                f"n={implied} rather than the header's n={header_n}. Rows that "
                "agree on one unstated denominator are reporting over a "
                "subgroup -- respondents to that item, a complete-case subset -- "
                "not making the same arithmetic error repeatedly. The "
                "disagreement with the header is reported; no error is alleged. "
                f"Confirm what n={implied} refers to before treating any of "
                "these as a finding."
            )

    _propagate_denominator_clamp(results)


#: Checks that read the SAME cell's percentage against the SAME denominator, and
#: therefore inherit the same explanation when that denominator turns out to be
#: a subgroup. `check_count_percent` is the one that can DETECT the shared
#: denominator, because it is the only one given the count; the others are the
#: ones that most need the answer.
_DENOMINATOR_SIBLINGS = ("grim_percentage",)


def _cell_key(result: dict):
    cell = result.get("cell") or {}
    return (cell.get("row_label"), cell.get("row"), cell.get("ordinal"),
            cell.get("raw"))


def _propagate_denominator_clamp(results: list[dict]) -> None:
    """Give the sibling checks on a clamped cell the same explanation.

    THE ASYMMETRY THIS FIXES, and it ran the wrong way round. The clamp above
    covers `check_count_percent`, which ALREADY caps itself at `suspicious`
    because "a different percentage base is an ordinary reporting convention,
    not a defect" (count_percent.CEILING). `grim_percentage` is routed to the
    SAME cell with the SAME n, has no such ceiling, and was not clamped -- so
    the check that cannot accuse was protected and the check that can was not.

    MEASURED on the honest table the clamp's own docstring is built from
    (PLoS ONE 0128753 Table 1: header n=352, percentages over the 340 who
    answered that item), with the variable declared `binary` so GRIM applies:

        grim_percentage      26.5 -> impossible      clamped_by=None
        check_count_percent  26.5 -> indeterminate   clamped_by=shared_section_denominator

    Three rows, three `impossible` verdicts, and the TABLE severity was
    `impossible` -- against a paper the repository already documents as honest.

    GRIM cannot detect this itself: it is never given the count, so it cannot
    compute an implied denominator. It can only inherit one. That is why this is
    propagation from the sibling rather than a second detector -- a second
    detector would need the count GRIM does not receive, and would drift.

    Only ever DOWNWARD to `indeterminate`, and only onto a cell whose sibling
    was clamped, so this cannot make anything more accusatory than it was.
    """
    # ONLY THE SHARED-DENOMINATOR CLAMP PROPAGATES, and the distinction is the
    # evidence each rests on.
    #
    # `shared_section_denominator` rests on AGREEMENT: several rows landing on
    # exactly the same unstated denominator, which errors do not do. That is
    # positive evidence about the cell, and any check reading that cell against
    # that denominator inherits it.
    #
    # `lone_row_near_denominator` rests on NOTHING but charity. Its own comment
    # says a single row is "indistinguishable from a one-digit slip in the
    # percentage, and no arithmetic can separate them" -- it is a deliberate
    # benefit of the doubt, granted to a check that caps at `suspicious`.
    # Extending it to a check that can say `impossible` spends that charity
    # twice over.
    #
    # MEASURED, and the suite caught this before I shipped it: `101 (71.5%)` at
    # n=142 implies 141, one below the header, so the lone-row clamp fires --
    # and propagating it suppressed a GENUINE impossibility that
    # `test_a_genuine_impossibility_is_still_caught` exists to hold.
    clamped = {_cell_key(r): r for r in results
               if r.get("clamped_by") == "shared_section_denominator"
               and r.get("tool") == "check_count_percent"}
    if not clamped:
        return
    for r in results:
        if r.get("tool") not in _DENOMINATOR_SIBLINGS:
            continue
        if r.get("severity") not in ("suspicious", "highly_suspicious", "impossible"):
            continue
        source = clamped.get(_cell_key(r))
        if source is None:
            continue
        r["severity"] = "indeterminate"
        r["clamped_by"] = source.get("clamped_by")
        r["clamp_reason"] = (
            f"inherited from `check_count_percent` on this same cell, which "
            f"could compute the implied denominator because it is given the "
            f"count. {source.get('clamp_reason')}")


#: Cell kinds whose routed checks all ask a question ABOUT THE BOUND VARIABLE,
#: and which are therefore meaningless on a model output. `estimate_ci` is
#: deliberately ABSENT: an odds ratio with its interval IS a model output, and
#: the checks routed for it are the ones that belong there.
_DESCRIPTIVE_KINDS = frozenset({"mean_sd", "mean_se", "n_percent"})


def _reports_model_output(col_label):
    """Shared with `prepass.reports_model_output` -- one definition, imported.

    The single-definition rule exists because this codebase has found the same
    constant hand-copied eleven times with the copies disagreeing. A second
    pattern list here would drift from the sweep's within a week.
    """
    from .prepass import reports_model_output
    return reports_model_output(col_label=col_label)


def check_table(
    cells: list[dict],
    variables: list[dict] | None = None,
    bindings: dict[str, str] | None = None,
    provenance: str = "printed_table",
) -> dict:
    """Type a table's cells and run every applicable check, in one call.

    Args:
        cells: `{raw, row_label, col_label, n}` per cell.
        variables: anatomy `Variable` dicts -- the same objects declared in Pass 0.
        bindings: row_label -> variable id.
        provenance: where these values came from. `measured_raster` or
            `measured_vector` stamps `uncertainty` on every exact param, and the
            registry's existing gate then refuses the granularity checks.

    Returns per-check results, a machine-generated `not_run` list, and a
    severity summary. Consistent results are collapsed into a count and an index
    rather than repeated in full -- re-inflating the context is the cost this
    exists to avoid.
    """
    by_id = {v.get("id"): v for v in (variables or [])}
    bindings = bindings or {}
    typed = parse_cells(cells)
    # THE DECLARATIONS BECOME ADDRESSABLE. `check_table` is the only surface the
    # model can hand variables to, so this is the one place a later per-cell
    # call can learn that `v3` means "BDI-II total, 0-63, sum of 21 items".
    # Without it `variable_id` on a direct grim_check names nothing.
    #
    # ORDERING LIMIT, stated rather than hidden: a per-cell call can only
    # reference a variable that some earlier `check_table` call declared. A run
    # that never submits a table leaves the store empty and every per-cell call
    # unreconciled -- exactly as it was before, which is the safe direction.
    declaration_note: str | None = None
    try:
        from . import declared as _declared
        _declared.add_variables(variables)
    except Exception as exc:  # noqa: BLE001 -- never fail a table over this
        # RECORDED, not discarded. If the declarations do not register, every
        # later per-cell call naming one of them comes back `not_declared` --
        # and without this note that reads as the model naming a variable it
        # never declared, rather than as our bookkeeping having dropped it.
        declaration_note = (
            f"variable declarations were not registered ({type(exc).__name__}: "
            f"{exc}), so a later per-cell check naming one of them cannot be "
            "reconciled against the paper")

    derived_n, sections, disputed_n = _section_denominators(cells)

    results: list[dict] = []
    consistent_index: list[dict] = []
    not_run: list[dict] = []
    blocked_on_declaration: dict[str, list[dict]] = {}
    tools_run: set[str] = set()
    # The pipeline's toolset, from the server environment (None: every check).
    from .pipeline_config import enabled_tools_from_env
    enabled = enabled_tools_from_env()
    #: Checks that ACTUALLY used a reconstructed denominator, not derivations
    #: that were merely available. A table where every cell states its own n
    #: derives plenty and uses none, and reporting the former would credit this
    #: with work it did not do.
    used_derived: set[str] = set()
    # One set, imported rather than re-spelled. This tuple was a literal copy of
    # `registry.MEASURED_PROVENANCE`, so adding the OCR channel there would have
    # left the TABLE path -- the path a scanned supplement actually travels --
    # judging transcribed cells while the per-cell path refused them.
    from .registry import UNVERIFIED_PROVENANCE
    measured = provenance in UNVERIFIED_PROVENANCE

    # POSITION IN THE ROW, counted over every cell. This is the join key the
    # value register needs: `check_table` is handed cells without a table name,
    # so it cannot build a value id, but it CAN say which cell of which row a
    # verdict belongs to. Counted over every cell, including the ones no check
    # runs on, so it means the same thing on both sides of the join.
    #
    # THE ROW NUMBER TRAVELS WITH IT. This comment used to claim
    # `(row_label, ordinal)` is unique within a table. It is not: clinical
    # tables repeat labels -- "Male" under two arms, "Age" at baseline and at
    # endpoint -- and joining without the row number attached one row's
    # `suspicious` verdict to another row's honest values.
    # HOW MANY CELLS CANNOT BE JOINED BACK. `get_table` emits `row` on every
    # cell; the documented contract listed only {raw, row_label, col_label}, so
    # the model faithfully dropped it and EVERY verdict came back carrying
    # `row: None`. Measured 2026-08-20 over nine registers: `n_checks_attached`
    # zero on all of them, 0 of 459 submitted cells carrying a row. The checks
    # ran and the answers had nowhere to go, and nothing said so.
    _n_rowless = sum(1 for c in cells
                     if isinstance(c, dict) and c.get("row") is None)

    _ordinals: dict[Any, int] = {}
    for i, (cell, raw_cell) in enumerate(zip(typed["cells"], cells)):
        row = cell.get("row_label") or raw_cell.get("row_label") or ""
        _row_key = raw_cell.get("row", cell.get("row"))
        _ordinals[_row_key] = _ordinals.get(_row_key, -1) + 1
        _ordinal = _ordinals[_row_key]
        var = by_id.get(bindings.get(row))
        cell = _resolve_ambiguous(cell, var)
        kind = cell["kind"]
        dtype = _canonical_type(var)

        # A COEFFICIENT IS NOT A MEAN, AND THE CELL CANNOT TELL YOU WHICH.
        # `8.57 (3.03)` is a mean beside its SD or a regression coefficient
        # beside its standard error, and the two are typographically identical;
        # only the column band says. Every descriptive check dispatched here
        # asks a question ABOUT THE BOUND VARIABLE -- GRIM asks whether a mean
        # is attainable from n integer observations of it -- so running one on
        # a model output asks that question of a number that is not a
        # measurement of anything.
        #
        # MEASURED on real cells from 10.1002--ajcp.70049 Table 4, bound to the
        # 1-5 variable their row labels correctly name: `grim_check`,
        # `grimmer_check` and `sprite_reconstruct` all RUN, and `-0.05 (0.98)`
        # returns `suspicious` -- GRIM reading a regression coefficient of
        # -0.05 as a mean of a 1-5 scale. The paper is honest and the row is
        # bound correctly; the premise is wrong.
        #
        # Refused BEFORE tool selection, and recorded in `not_run` like every
        # other refusal, so the loss is visible rather than silent. This only
        # ever REMOVES checks (invariant 1), so a false positive costs coverage
        # and cannot cost correctness.
        _model_output = _reports_model_output(
            raw_cell.get("col_label") or cell.get("col_label"))
        if _model_output and kind in _DESCRIPTIVE_KINDS:
            not_run.append({
                "cell": row, "row": _row_key, "kind": kind, "tools": [],
                "reason": (
                    f"this column holds a model output, not a descriptive "
                    f"statistic ({_model_output}). A regression coefficient "
                    f"beside its standard error is typographically identical "
                    f"to a mean beside its SD, and the checks routed for "
                    f"{kind} all ask a question about the bound variable that "
                    f"a model output cannot answer.")})
            continue

        if kind in NEVER_DISPATCH:
            not_run.append({"cell": row, "row": _row_key, "kind": kind, "tools": [],
                            "reason": NEVER_DISPATCH[kind]})
            # `ambiguous` is the DECLARATION-FIXABLE refusal, and measurement
            # says it is the commonest one: a bare "Age" row printing
            # "48.90 (14.46)" could be mean(SD), n(%) or estimate(CI), and
            # `_resolve_ambiguous` settles it the moment a family is declared.
            # Recorded only when undeclared -- a declared row that is still
            # ambiguous is a different problem and no form will fix it.
            if kind == "ambiguous" and var is None:
                blocked_on_declaration.setdefault(row, []).append(dict(cell))
            continue

        if kind == "mean_sd" and _is_composite(var):
            not_run.append({"cell": row, "row": _row_key, "kind": kind, "data_type": dtype,
                            "tools": ["grim_check", "grimmer_check", "sprite_reconstruct"],
                            "reason": _composite_reason(var)})
            continue

        tools = DISPATCH.get((kind, dtype))
        if tools:
            tools, refused = _drop_unbounded(tools, var)
            if refused:
                not_run.append({"cell": row, "row": _row_key, "kind": kind, "data_type": dtype,
                                "tools": sorted(refused), "reason": UNBOUNDED_REASON})
        if not tools:
            not_run.append({
                # `row` beside `cell`: a table can repeat a row LABEL -- "Male"
                # under two arms -- so the label alone stamps one row's refusal
                # onto another row's values. See `values.attach_not_run`.
                "cell": row, "row": _row_key, "kind": kind,
                "data_type": dtype, "tools": [],
                "reason": WHY_NOT.get((kind, dtype),
                                      f"no check defined for a {kind} cell on {dtype} data"),
            })
            # Undeclared is the fixable case, and the commonest one. Record the
            # row so the refusal can return the form rather than only the
            # complaint. `dtype == "unknown"` means no variable was bound to
            # this row; every other dtype is a declared row for which this kind
            # genuinely has no check, and no declaration would change that.
            if dtype == "unknown":
                blocked_on_declaration.setdefault(row, []).append(dict(cell))
            continue

        # THE n (%) OF A CATEGORY IS A PROPORTION: `share` reads a category
        # family's percentage as the share of the sample it is (see
        # `Variable.forensic_kwargs`), so grim_percentage tests it.
        base = dict(_variable_kwargs(var, share=kind in _SHARE_KINDS))
        # WHAT THE DECLARED VARIABLE CONTRIBUTED, captured before the cell's
        # values are layered on. The two are dropped by `_build_args` for
        # entirely different reasons and must not be counted together: a tool
        # not consuming `percent` is by DESIGN, one tool per shape; a tool
        # unable to name `items` or `derivation` is a FACT WE HAD AND LOST.
        _var_supplied = set(base)
        base.update({k: v for k, v in cell.items()
                     if k in ("value", "sd", "se", "percent", "count", "low", "high")})
        # LAST, never first. A stated `n` -- on the cell or on the declared
        # variable -- always wins, so this is purely additive: it can turn a
        # refusal into a check, and can never change the inputs of a check that
        # already ran. Measured on 10.1038/s41537-025-00576-3 Table 2, the
        # refusal it addresses was 244 of 389 cells, all reading
        # "grim_percentage needs n and this cell carries none".
        # THE CELL'S OWN PRINTED DENOMINATOR WINS. `12/30 (40.0)` states its n;
        # everything else here infers one, and an inferred n is how a
        # granularity check manufactures an impossibility out of a correctly
        # reported number. Ordered first for that reason, not for convenience.
        n_in_cell = cell.get("denominator")
        n = n_in_cell or raw_cell.get("n") or (var or {}).get("n")
        n_derived = n is None and i in derived_n
        if n_derived:
            n = derived_n[i]["n"]
        # A DISPUTED DENOMINATOR IS NOT A DENOMINATOR. If this cell's column
        # had two n's that disagree, neither may be used -- composite's own
        # words -- and a supplied one is exactly the source under dispute. The
        # cell's OWN printed denominator still wins, because `12/30 (40.0)`
        # states its n rather than inheriting a header's.
        n_disputed = n is not None and not n_in_cell and i in disputed_n
        if n_disputed:
            n = None

        for tool_name in tools:
            if enabled is not None and tool_name not in enabled:
                # A PIPELINE TOOLSET, not a gap in the toolkit: the run was
                # configured without this check. Recorded like every other
                # refusal so the cell reads "not checked", never "passed".
                not_run.append({"cell": row, "row": _row_key, "kind": kind,
                                "tools": [tool_name],
                                "reason": NOT_ENABLED_REASON})
                continue
            spec = _specs().get(tool_name)
            if spec is None:
                # NAMED IN DISPATCH, ABSENT FROM THE REGISTRY. Silently skipping
                # left a cell with an applicable tool, no verdict and no
                # refusal -- which reads downstream as a value nothing needed to
                # check. It is OUR gap, and it says so.
                not_run.append({
                    "cell": row, "row": _row_key, "kind": kind,
                    "tools": [tool_name],
                    "reason": (f"{tool_name} is routed for this cell but is not "
                               "in the tool registry, so nothing ran. This is a "
                               "gap in the toolkit, not a fact about the paper."),
                })
                continue
            _dropped: set[str] = set()
            args = _build_args(spec, cell, base, n, dropped=_dropped)
            if args is not None and bindings.get(row):
                # The table path already sourced these arguments FROM the
                # declared variable, so reconciliation here agrees by
                # construction -- the point is the result carrying the same
                # `variable` block the model path gets, so the viewer has one
                # shape to render rather than two.
                args["variable_id"] = bindings.get(row)
            if args is None:
                not_run.append({"cell": row, "row": _row_key, "kind": kind, "tools": [tool_name],
                                "reason": _refusal_reason(spec, n, raw_cell)})
                continue
            if measured:
                # One place, reusing the registry gate rather than duplicating it.
                args["uncertainty"] = {p: None for p in spec.exact_params()}
            out = spec.call(args)
            tools_run.add(tool_name)
            record = {
                # WHAT THE TOOL'S SCHEMA COULD NOT NAME. Empty on almost every
                # call; when it is not, it is the difference between a refusal
                # and a verdict. See `_build_args`.
                **({"dropped_args": sorted(_dropped & _var_supplied)}
                   if (_dropped & _var_supplied) else {}),
                "check_id": f"r{i}.{tool_name}",
                "tool": tool_name,
                "cell": {"row_label": row, "raw": cell.get("raw"), "kind": kind,
                         # See `_ordinals` above: the value register joins on
                         # this, not on the raw text, because two columns of a
                         # row can print the same number.
                         "row": _row_key, "ordinal": _ordinal},
                "variable_id": bindings.get(row),
                "inputs": {k: v for k, v in args.items() if k != "uncertainty"},
                "severity": out.get("severity"),
                "result": out,
                "reproduction": _reproduction(
                    tool_name, {k: v for k, v in args.items() if k != "uncertainty"}),
            }
            if n_derived:
                _stamp_derived_n(record, derived_n[i])
                used_derived.add(record["check_id"])
            elif n_in_cell is not None and n == n_in_cell:
                # The strongest provenance there is, and distinguished from
                # `supplied` because it carries no caveat: `_stamp_supplied_n`
                # has to warn that an enrolled total may not be the n ANALYSED,
                # and a printed `12/30` is the analysed denominator by
                # construction.
                record["n_provenance"] = {
                    "derived": False,
                    "n": n,
                    "how": "printed_in_the_cell",
                    "note": ("The paper printed this denominator in the cell "
                             "itself, as `count/denominator`. Nothing here was "
                             "inferred, carried down from another row, or "
                             "reconstructed."),
                }
            else:
                # EVERY check says where its denominator came from, not only the
                # reconstructed ones. See `_stamp_supplied_n`.
                _stamp_supplied_n(record, n, raw_cell)
            if record["severity"] == "consistent":
                # THE CELL TRAVELS WITH THE PASS, not only with the finding.
                # Without it a value the checks CLEARED and a value nothing ran
                # on are spelled identically downstream -- an absence read as
                # knowledge, in the index whose whole job is to say what came
                # back clean. Kept to the join key and nothing more, so the
                # index stays the cheap summary it was built to be.
                consistent_index.append({
                    "check_id": record["check_id"], "tool": tool_name,
                    "cell": {"row_label": row, "row": _row_key,
                             "ordinal": _ordinal},
                })
            else:
                results.append(record)

    # THE SPLIT `n (%)` COLUMN, which the per-cell path cannot see.
    #
    # `check_count_percent` is routed for every cell typed `n_percent` -- but
    # that type means ONE cell reading `142 (73.0)`. Where a journal prints the
    # count and the percentage in ADJACENT COLUMNS there is no such cell, the
    # routing never fires, and the strongest check available on those rows
    # simply does not run. Archived refusals name the gap exactly: "the counts
    # and percentages sit in separate columns, so the typed parser reads them
    # as independent". See `count_percent_pairs` for why the pairing is by
    # shared header prefix and never positional.
    for pair in count_percent_pairs(cells):
        if enabled is not None and "check_count_percent" not in enabled:
            not_run.append({"cell": pair["row_label"], "kind": "split_n_percent",
                            "tools": ["check_count_percent"],
                            "reason": NOT_ENABLED_REASON})
            continue
        try:
            count = int(str(pair["count_cell"].get("raw")).replace(",", "").strip())
            pct_raw = str(pair["percent_cell"].get("raw")).replace("%", "").strip()
            pct = float(pct_raw)
        except (TypeError, ValueError):
            continue
        decimals = len(pct_raw.split(".", 1)[1]) if "." in pct_raw else 0
        from . import registry as _reg
        spec = _reg.BY_NAME.get("check_count_percent")
        if spec is None:
            break
        args = {"count": count, "percentage": pct, "n": pair["n"],
                "decimals": decimals}
        out = spec.call(dict(args))
        tools_run.add("check_count_percent")
        record = {
            "check_id": f"cp:{pair['row_label']}:{pair['group']}",
            "tool": "check_count_percent",
            "cell": {"row_label": pair["row_label"],
                     "raw": f"{count} / {pct}%", "kind": "split_n_percent"},
            "variable_id": bindings.get(pair["row_label"]),
            "inputs": args,
            "severity": out.get("severity"),
            "result": out,
            "reproduction": _reproduction("check_count_percent", args),
            # The denominator came from the group's OWN header, which is the
            # only place it may come from -- see `count_percent_pairs`.
            "n_provenance": {
                "derived": False, "n": pair["n"], "how": "printed_in_a_label",
                "note": f"read from the column header {pair['group']!r}",
            },
        }
        if record["severity"] == "consistent":
            consistent_index.append({"check_id": record["check_id"],
                                     "tool": "check_count_percent"})
        else:
            results.append(record)

    _clamp_shared_denominator(results)

    summary: dict[str, int] = {}
    for r in results:
        summary[r["severity"]] = summary.get(r["severity"], 0) + 1
    summary["consistent"] = len(consistent_index)

    order = ["impossible", "highly_suspicious", "suspicious", "indeterminate", "consistent"]
    n_checks_run = len(results) + len(consistent_index)
    # ZERO checks run is NOT a clean bill of health.
    #
    # The fallback used to be "consistent", so a table on which every cell was
    # refused reported an all-clear the tool had never earned. Verified:
    # check_table(cells=[{'raw':'n/a'}, {'raw':'--'}, {'raw':'NR'}], variables=[])
    # returned severity 'consistent' with n_checks_run 0, n_not_run 3,
    # tools_run []. `stage1_sweep.md:213` mandates ONE check_table call per
    # table, so that single verdict is the whole record of the table -- "we
    # refused everything" was being published as "we checked and it is clean".
    #
    # The entire guard architecture exists so refusals stay explicit, and
    # `indeterminate` is the answer every other unverified precondition gives.
    worst = next((s for s in order if summary.get(s)),
                 "consistent" if n_checks_run else "indeterminate")

    return {
        "severity": worst,
        "parse": {k: typed[k] for k in ("n_cells", "coverage", "kind_counts", "warnings")},
        "n_checks_run": n_checks_run,
        "n_not_run": len(not_run),
        "results": results,
        "consistent_index": consistent_index,
        "not_run": not_run,
        "declaration_template": _declaration_template(blocked_on_declaration),
        # PUBLISHED even when nothing was derived. The sections are how the
        # table was read: a reader who disagrees with a denominator needs to
        # see which rows it was summed from, and a reader whose table yielded
        # none needs the stated reason rather than silence.
        "sections": sections,
        # HOW MANY CELLS CANNOT BE JOINED BACK, and it is a count rather than a
        # silence. `get_table` supplies `row` on every cell; the documented
        # contract used to list only {raw, row_label, col_label}, so the model
        # dropped it and EVERY verdict came back with `row: None`. Measured
        # 2026-08-20 over nine registers: `n_checks_attached` zero on all of
        # them, 0 of 459 submitted cells carrying a row. The checks ran and the
        # answers had nowhere to go, and nothing said so.
        "n_cells_without_row": _n_rowless,
        "n_denominators_derived": len(used_derived),
        "summary_by_severity": summary,
        "tools_run": sorted(tools_run),
        # Present ONLY when the declarations failed to register. See the note
        # where it is set: without it, every later per-cell check naming one of
        # these variables comes back `not_declared`, which reads as the model's
        # mistake rather than ours.
        **({"declaration_note": declaration_note} if declaration_note else {}),
        "provenance": provenance,
        "methodology": (
            "Deterministic dispatch: typed cell kind x declared variable family -> the "
            "checks that apply. Every check runs through the registry, so applicability "
            "guards, the exact-value gate and withheld parameters are inherited, not "
            "reimplemented. `not_run` is machine-generated per (cell, check), so coverage "
            "does not depend on anything being remembered. Consistent results are counted "
            "and indexed rather than repeated in full. "
            f"{n_checks_run} checks run, {len(not_run)} refused. "
            + (f"{len(used_derived)} of those checks used a denominator RECONSTRUCTED "
               "from their own section rather than one the table prints -- accepted "
               "only where the section's counts reproduce every percentage it prints, "
               "applied only to the cells that were summed to make it, and capped at "
               f"`{_DERIVED_N_CEILING}`. See `n_provenance` on each. " if used_derived else "")
            +
            "Report the DENOMINATOR with any finding: 3 suspicious out of 140 checks and 3 "
            "out of 4 are different papers."
        ),
    }


#: The ceiling on any finding whose denominator we reconstructed rather than
#: read. `impossible` is the one verdict that admits no innocent explanation,
#: and this repo reserves it for bound-free exact arithmetic on values the
#: PAPER PRINTED. A section denominator is verified against the paper's own
#: percentages -- see `composite._derive_n` -- but it is still our inference,
#: and a wrong n is the shortest route to a false `impossible`
#: (`docs/GRIM_CONTEXT_DEPENDENCY.md`, mechanism 18). One rung down costs a
#: reader nothing: the finding is still shown, still reproducible, and now
#: says out loud which number it had to work out for itself.
_DERIVED_N_CEILING = "highly_suspicious"


#: `(n = 84)` inside a column header -- the denominator a per-arm table prints
#: where it belongs, and the reason this pairing is checkable at all.
_HEADER_N = re.compile(rf"\(\s*n\s*{_EQ}\s*(\d[\d,\s]*)\s*\)", re.I)

#: The two halves of a split `n (%)` column, as journals actually label them.
_COUNT_SUFFIXES = frozenset({"n", "no", "no.", "count", "freq", "frequency", "number"})
_PERCENT_SUFFIXES = frozenset({"%", "percent", "percentage", "pct"})


def _label_parts(label: str) -> tuple[str, str]:
    """Split `Control group (n = 30) | %` into its group prefix and its suffix.

    The separator is whatever the extractor used to join a spanning header to
    its sub-header. Without a separator the whole label is the suffix and the
    prefix is empty, which is what makes an unspanned table refuse below.
    """
    text = " ".join(str(label or "").split())
    for sep in ("|", "–", " - "):
        if sep in text:
            head, _, tail = text.rpartition(sep)
            return head.strip(), tail.strip().lower()
    return "", text.strip().lower()


def count_percent_pairs(cells: list[dict]) -> list[dict]:
    """Cells where a printed COUNT and a printed PERCENTAGE describe one group.

    WHY THIS EXISTS. `check_count_percent` is strictly stronger than GRIM
    wherever the count is printed -- GRIM asks whether a percentage is
    attainable for SOME numerator, this asks whether it matches THE numerator
    the paper printed -- and it is routed automatically for every cell typed
    `n_percent`. But that type means ONE cell reading `142 (73.0)`. Where a
    journal splits the pair across two columns, no such cell exists, the routing
    never fires, and archived refusals say so in as many words: "the counts and
    percentages sit in separate columns, so the typed parser reads them as
    independent". MEASURED across 125 archived table extractions: 372 paired
    cells, 264 of them with the denominator printed in the header.

    PAIRING IS BY SHARED GROUP PREFIX, NEVER BY POSITION, AND THAT IS THE WHOLE
    SAFETY ARGUMENT. My first attempt at this measurement took the cross-product
    of count columns against percentage columns and reported 1,656 "pairs" -- it
    was pairing arm A's count with arm B's percentage. Every one of those would
    have been a false accusation, manufactured entirely by us, against a table
    whose arithmetic is fine. So a pair is formed only when the two labels agree
    on everything to the left of the separator, and a table whose headers do not
    span is left alone rather than guessed at.

    The denominator comes from `(n = N)` in that SAME shared prefix, or from the
    cells' own agreeing `n`. It is never taken from another column's header, and
    never inferred.
    """
    by_row: dict[tuple, dict[str, list[dict]]] = {}
    for cell in cells or []:
        if not isinstance(cell, dict):
            continue
        prefix, suffix = _label_parts(cell.get("col_label"))
        if not prefix:
            continue
        key = (str(cell.get("row_label") or ""), prefix)
        if suffix in _COUNT_SUFFIXES:
            by_row.setdefault(key, {}).setdefault("count", []).append(cell)
        elif suffix in _PERCENT_SUFFIXES:
            by_row.setdefault(key, {}).setdefault("pct", []).append(cell)

    out: list[dict] = []
    for (row_label, prefix), halves in by_row.items():
        counts, pcts = halves.get("count") or [], halves.get("pct") or []
        # Exactly one of each. Two count columns under one prefix means the
        # prefix does not identify a group, and pairing on it would be the
        # positional guess this function exists to refuse.
        if len(counts) != 1 or len(pcts) != 1:
            continue
        c, p = counts[0], pcts[0]
        header = _HEADER_N.search(prefix)
        n = None
        if header:
            n = int(header.group(1).replace(",", "").replace(" ", ""))
        else:
            ns = {c.get("n"), p.get("n")} - {None}
            if len(ns) == 1:
                n = next(iter(ns))
        if not n:
            continue
        out.append({"row_label": row_label, "group": prefix, "n": n,
                    "count_cell": c, "percent_cell": p})
    return out


def _section_denominators(cells: list[dict]) -> tuple[dict[int, dict], list[dict]]:
    """Recover a denominator for cells that carry none, from their own section.

    A composite table -- several logical tables printed as one, separated by a
    banner row repeating the section name across every column -- hides its
    denominators in plain sight: within a section the categories are exhaustive,
    so the counts sum to n. `composite.split_sections` recovers that n and
    VERIFIES it against the paper's printed percentages before returning it.

    Returns `{cell index: {n, n_source, section, column}}` for cells the
    verification covered, the section list for the caller to publish, and
    `{cell index: why}` for cells whose column had TWO denominators that
    disagree -- those must not be checked against either. A table with no
    banners yields one section, which is the ordinary case and costs nothing.

    Never raises. A malformed table must not take the whole check down with it:
    the worst outcome of failing here is the refusal we already had.
    """
    try:
        sections = split_sections(cells)
    except Exception as exc:  # noqa: BLE001 -- see docstring
        # THREE VALUES ON EVERY PATH. This returned a 2-tuple while the success
        # path returned 3, so a malformed table unpacked into a ValueError --
        # turning "we could not split this table" into a crash, which is the
        # one thing this except block exists to prevent.
        return ({}, [{"label": None, "n": None,
                      "why_not": f"section split failed: {type(exc).__name__}: {exc}"}],
                {})

    pos = {id(c): i for i, c in enumerate(cells)}
    out: dict[int, dict] = {}
    disputed: dict[int, str] = {}
    published: list[dict] = []
    for s in sections:
        by_col = s.get("n_by_column") or {}
        published.append({
            "label": s.get("label"),
            "n_cells": len(s.get("cells") or []),
            "n_by_column": {k: v.get("n") for k, v in by_col.items()},
            "why_not": {k: v["why_not"] for k, v in by_col.items() if v.get("why_not")},
        })
        # ONLY the cells that were summed to make the denominator get it. A
        # `mean (SD)` row printed inside an otherwise categorical section
        # contributed no count, and its own n may be smaller for missing data
        # -- handing it the section total is the false `impossible` this whole
        # module is built to avoid. In practice that restricts the derived n to
        # `count (percent)` cells, which is exactly the refusal it addresses.
        for col, info in by_col.items():
            # A COLUMN WHOSE TWO DENOMINATORS DISAGREE POISONS BOTH. composite
            # says so in as many words -- "two sources for one denominator
            # disagree, so neither is used" -- but that only ever removed the
            # DERIVED n. The header n arrives separately, on `raw_cell["n"]`,
            # and was still used to check the very cells this rejected.
            #
            # MEASURED 2026-08-20: two false accusations on honest papers.
            # `Radiotherapy history | Yes`, count 10, percentage 2.9, checked
            # against the header's n = 352. 10/352 is 2.84%, so it fired -- but
            # the section's own counts sum to 345, any n from 339 to 350 prints
            # 2.9%, and the paper is right. The rows have a smaller denominator
            # than the column total because some histories are unknown.
            for c in info.get("disputed") or []:
                i = pos.get(id(c))
                if i is not None:
                    disputed[i] = info.get("why_not") or "denominators disagree"
            if not info.get("n"):
                continue
            for c in info.get("contributing") or []:
                i = pos.get(id(c))
                if i is not None:
                    out[i] = {"n": info["n"], "n_source": info.get("n_source"),
                              "section": s.get("label"), "column": col}
    return out, published, disputed


def _stamp_supplied_n(record: dict, n: Any, raw_cell: dict | None) -> None:
    """Record where an ordinary, NON-derived denominator came from.

    THE GAP: `_stamp_derived_n` below documents the reconstructed case at
    length and caps it -- and the ORDINARY case, which is the overwhelming
    majority, carried no provenance at all. `n` arrives as `raw_cell["n"]` or
    off the bound variable, put there by the model after reading a column
    header, and every check downstream treats it as simply true.

    That is the third premise of this family, after the scale bounds and the
    discreteness, and it is the one an earlier audit ranked ABOVE both: the
    analysed n for a single outcome is routinely smaller than the column's
    enrolled n, and GRIM at the wrong denominator manufactures an impossibility
    out of an honest table.

    NO CAP IS APPLIED HERE, deliberately. A cap needs something to key on, and
    the honest position is that we do not know whether this n is the analysed
    one -- see `grim.nearby_denominators` for the measurement showing that
    "it would fit at n +/- 1" cannot supply that evidence, since it is true of
    70-80% of genuine failures at these sample sizes. What we can do, and now
    do, is say plainly where the number came from so a reader knows which
    question to ask. Recording provenance we have is worth more than inventing
    a confidence we do not.
    """
    if n is None:
        return
    label_ns = [v for _lbl, v in _n_in_labels(raw_cell or {})]
    record["n_provenance"] = {
        "derived": False,
        "n": n,
        "how": "printed_in_a_label" if n in label_ns else "supplied",
        "in_cell_labels": label_ns or None,
        "note": (
            "This denominator was supplied with the cell, not reconstructed. It is "
            "typically the column's enrolled total; the n ANALYSED for a single "
            "outcome is often smaller after exclusions, and every granularity "
            "verdict here assumes the two are the same."
        ),
    }


def _stamp_derived_n(record: dict, info: dict) -> None:
    """Record that this check's `n` was reconstructed, and cap it accordingly."""
    record["n_provenance"] = {
        "derived": True, "n": info["n"], "how": info.get("n_source"),
        "section": info.get("section"), "column": info.get("column"),
        "note": (
            f"This check's denominator, n = {info['n']}, is NOT printed in the table. "
            f"It is the sum of the counts in section {info.get('section')!r}, column "
            f"{info.get('column')!r}, and it was accepted only because it reproduces "
            "every percentage that section prints. Verify it before acting on this "
            f"finding. Severity is capped at `{_DERIVED_N_CEILING}` for that reason."
        ),
    }
    order = list(SEVERITY_LEVELS)
    if order.index(record["severity"]) < order.index(_DERIVED_N_CEILING):
        record["severity_uncapped"] = record["severity"]
        record["severity"] = _DERIVED_N_CEILING


def _build_args(spec, cell: dict, base: dict, n: Any,
                dropped: set[str] | None = None) -> dict | None:
    """Assemble one tool's arguments, or None when the cell lacks its inputs.

    `dropped`, if given, is filled with the names of facts we HAD and the tool's
    schema cannot name. That set used to vanish.

    WHY IT IS RECORDED. The line below is an intersection with the tool's
    schema, and it was silent: no `not_run` entry, no warning, no residue. A
    fact the cell or the declared variable supplied simply ceased to exist
    between here and the tool. It is not a hypothetical loss -- a variable
    declaring `derivation: mean_of_items` has its `items` dropped here, because
    `grim_check`'s schema has no `items` parameter, and the tool then runs at a
    granularity of 1/n instead of 1/(items*n) and returns `impossible` on an
    honest scale score.

    IT ALSO MAKES THE REGISTER REFACTOR FALSIFIABLE, which is the larger reason.
    A richer register delivered to `dispatch` would change nothing here and NO
    TEST WOULD FAIL: the extra fields would be dropped by this line exactly as
    the current ones are. Counting the drop is what converts an invisible class
    of loss into a measurable one, and it must land before the refactor rather
    than after it.

    Names only, never values: a dropped `quote` or `rows` payload would bloat
    every record, and the name is what a reader needs to see the pattern.
    """
    want = set(spec.schema())

    # ONE FACT, TWO NAMES. `Variable.forensic_kwargs` emits `scale_min` and
    # `scale_max`; `check_sd_or_se`'s ToolSpec calls the same two numbers
    # `variable_range_min` and `variable_range_max`. The intersection below is
    # by NAME, so the declared variable's range was dropped at the schema
    # boundary and that tool received no bounds at all -- leaving it able to
    # return nothing but `indeterminate` through `check_table`, on all 8 of the
    # DISPATCH rows that route to it.
    #
    # THIS ONLY EVER ADDS A FACT THE CELL ALREADY DECLARED, under a name the
    # tool asked for, and the tool's own `bound_source` cap still governs what
    # it may conclude from it. Verified by replaying the 934-call archive: no
    # archived call becomes accusatory.
    for src, dst in (("scale_min", "variable_range_min"),
                     ("scale_max", "variable_range_max")):
        if dst in want and dst not in base and src in base:
            base = {**base, dst: base[src]}

    if dropped is not None:
        dropped.update(k for k in base if k not in want)
    args = {k: v for k, v in base.items() if k in want}

    # PRINTED precision, not the parsed float's. Omitting this let every check
    # fall back to its registry default: `101 (71%)` was tested as though "71"
    # had been printed to one decimal, and a correctly-reported cell came back
    # `impossible` through check_table's primary path.
    #
    # `decimals` means the precision of WHICHEVER VALUE THE TOOL CONSUMES, so
    # it is resolved from the tool's own parameter names rather than assumed to
    # be the cell's main value. Getting this wrong is silent: the check runs,
    # returns a verdict, and sized its rounding interval off an unrelated number.
    if "percentage" in want:
        decimals = cell.get("decimals_percent")
    elif "estimate" in want:
        # A comparison among an estimate and its two bounds is only known to
        # the coarsest of the three.
        decimals = cell.get("decimals_interval")
    elif "reported_value" in want:
        # check_sd_or_se consumes the DISPERSION, not the mean beside it.
        decimals = cell.get("decimals_sd")
    else:
        decimals = cell.get("decimals_value")

    mapping = {
        "mean": cell.get("value"), "sd": cell.get("sd"),
        "percentage": cell.get("percent"), "estimate": cell.get("value"),
        "ci_low": cell.get("low"), "ci_high": cell.get("high"),
        "reported_value": cell.get("se") if cell.get("se") is not None else cell.get("sd"),
        "n": n,
        # THE FIELD THAT WAS BEING DROPPED. `parse_cells` has always returned
        # it for an `n (%)` cell; nothing downstream asked for it, so the
        # numerator the paper printed never reached a check.
        "count": cell.get("count"),
        "decimals": decimals,
        # The same quantity as `decimals` under a different name; sprite and
        # debit call it that. Unmapped, it sent sprite to a fallback that
        # re-derives precision from the parsed float -- a mean printed "71"
        # read as 1 dp -- and left debit silently defaulting to 2.
        "decimals_mean": cell.get("decimals_value"),
        "decimals_sd": cell.get("decimals_sd"),
    }
    for key, val in mapping.items():
        if key in want and val is not None:
            args[key] = val

    missing = [p.name for p in spec.params
               if p.required and p.name not in args and p.name != "uncertainty"]
    return None if missing else args
