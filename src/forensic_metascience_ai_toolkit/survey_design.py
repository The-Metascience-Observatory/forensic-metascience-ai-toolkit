"""Does the paper say it analysed a COMPLEX SURVEY? And what that forbids.

WHY THIS EXISTS
---------------
MEASURED 2026-08-22, `10.1186--s12889-025-24026-y` (NHANES) on grok-4.6: SIX of
the twenty severity-bearing tool-expert findings in a ten-paper run -- two of
them at severity 3 -- were one error, and the paper's own Methods said so:

    "NHANES sampling weights (WTMEC2YR) were applied to account for complex
     survey design ... Analyses were performed using R v4.3.1 with the survey
     package to incorporate sampling weights."

The tool expert then recomputed that paper's p-values and confidence intervals
as though they came from a simple random sample, and filed every disagreement
as a defect. They are not defects. Solving for the survey degrees of freedom
that reproduce each printed p FROM ITS OWN PRINTED INTERVAL:

    row                p if z95    printed    df that reproduces it
    Table 2 Model 1     0.00034      0.003            7.8
    Table 2 Model 2     0.00001      0.001            6.9
    Table 2 Model 3     0.00000     <0.001            4.7   <- called CONSISTENT
    Table 5 matched     0.00322      0.008            8.8
    Abstract PSM        0.00770      0.009           38.6
    Excl dual users     0.00212      0.003           37.3

Every row lands on a plausible df, and the tell is the pass/fail pattern: on one
table the z-based check cleared Model 3 and accused Models 1-2, with no coherent
story. That is what a z test does when the truth is a t with small,
subpopulation-varying df. The BMI t-test needed a design effect of only 1.62,
and NHANES design effects of 1.5-3 are routine.

THE CHECK IS NOT BROKEN. IT IS ONE-SIDED.
-----------------------------------------
A complex design costs degrees of freedom; fewer df means fatter tails; so the
same interval half-width implies a LESS significant p. That is monotone in df,
and the normal-approximation answer is its infimum:

    df:        2       4       8      20     100    inf(z)
    p:    0.0158  0.0071  0.0029  0.0011  0.0004  0.00034   (Table 2 Model 1)

Hence, for a check that reads a p and its own interval off the SAME fit:

  * printed p ABOVE the z-implied p -> some finite df always explains it, so
    the observation carries no information about the paper;
  * printed p BELOW the z-implied p -> no df reaches that, so it stands.

All six rows above sit in the no-information direction. We were publishing the
uninformative side of a one-sided check.

WHY A PAPER-LEVEL FLAG CANNOT DO EVERYTHING
-------------------------------------------
The direction argument holds only where the interval and the p come from one
fit. It does NOT transfer to a check that recomputes from printed means or
back-derived counts, and the race row is the proof: printed p=0.003 against an
unweighted chi-square of 0.117 is the "anomalous" direction, and it is still a
false positive, because NHANES oversamples minorities and weighting moves the
racial composition itself, not merely the variance. There both the point
estimate and the variance are unrecoverable from the printed summary, so
neither direction carries information and the check must refuse outright.

Integer arithmetic on printed counts -- `check_count_percent`,
`check_summation*`, `check_flow_arithmetic`, the GRIM family -- is valid under
any design and is deliberately untouched. Whether one PARTICULAR percentage was
weighted is a per-cell fact that a paper-level flag cannot know, and suppressing
those checks corpus-wide would cost far more than it saved.
"""

from __future__ import annotations

import re

from .scope import _clause_around

#: Phrases that only appear when a paper is describing design-based inference.
#: Deliberately specific. "weight" alone is body weight in half this corpus, and
#: "stratified" alone is an ordinary subgroup analysis; neither is here.
#:
#: MEASURED 2026-08-22 over all 18 paper directories in
#: `biomedical_did_not_replicate` (two ten-paper biomedical runs plus eight
#: staged cancer-biology papers): fires on exactly the two survey papers --
#: `10.1186--s12889-025-24026-y` on four independent markers and
#: `10.15585--mmwr.mm6923e2` on one -- and on none of the other sixteen.
_MARKERS: tuple[str, ...] = (
    r"complex[\s-]+(?:survey|sampling)[\s-]+design",
    r"\bsurvey[- ]weight",
    r"\bsampling\s+weights?\b",
    # NHANES variable names. WTMEC2YR / WTINTPRP / WTMECPRP and relatives.
    r"\bWT(?:MEC|INT)\w*\b",
    r"\bSDMVPSU\b",
    r"\bSDMVSTRA\b",
    # The software says it out loud: R survey, Stata svy:, SAS PROC SURVEY*.
    r"\bsvy(?:glm|mean|design|set|by|ciprop|total|contrast)\w*",
    r"\bPROC\s+SURVEY\w+",
    r"\b(?:the|R)\s+survey\s+package\b",
    # Design-based variance estimators.
    r"\bprimary\s+sampling\s+units?\b",
    r"\bTaylor[- ]series\s+linear",
    r"\bjackknife\s+replicate\b",
    r"\bbalanced\s+repeated\s+replication\b",
    r"\bweighted\s+(?:response\s+)?"
    r"(?:frequenc|percentage|prevalence|proportion|estimate)",
)

_RX = tuple(re.compile(m, re.I) for m in _MARKERS)

#: Checks that rebuild a test statistic from printed means, SDs or counts.
#: Under a complex design neither the point estimate nor the variance is
#: recoverable from those, so these refuse in BOTH directions.
REFUSED_UNDER_SURVEY = frozenset({
    "recalc_independent_t",
    "recalc_within_subjects_t",
    "recalc_anova",
    "recalc_chi_squared",
    "recalc_stat_to_p",
    "rivets_independent_t",
    "rivets_anova",
})

#: The two states a caller may declare. `simple_random` is the default
#: everywhere, so no existing call site changes meaning.
SIMPLE_RANDOM = "simple_random"
COMPLEX_SURVEY = "complex_survey"

#: Only the spellings a model plausibly emits. Trimming is safe in the one
#: direction that matters: an unrecognised string falls back to
#: `simple_random`, i.e. the guard stays OFF, which is what a typo should buy.
_ALIASES = {
    "": SIMPLE_RANDOM,
    "none": SIMPLE_RANDOM,
    "srs": SIMPLE_RANDOM,
    "simple_random": SIMPLE_RANDOM,
    "complex_survey": COMPLEX_SURVEY,
    "complex survey": COMPLEX_SURVEY,
    "survey": COMPLEX_SURVEY,
    "weighted": COMPLEX_SURVEY,
}


def canonical_sampling(sampling: str | None) -> str:
    """`simple_random` or `complex_survey`; anything unrecognised is the former.

    UNRECOGNISED FALLS BACK TO `simple_random` ON PURPOSE, and the asymmetry is
    the opposite of `canonical_data_type`'s. There, an unknown type must not buy
    a check, so it degrades toward refusal. Here, refusal is what a typo would
    buy -- and a guard that silently switches itself on for a string it did not
    recognise would delete real findings on ordinary papers. A paper IS a simple
    random sample until it says otherwise; the harness detector below is what
    says otherwise, not a free-text argument the model may misspell.
    """
    key = str(sampling or "").strip().lower()
    return _ALIASES.get(key, SIMPLE_RANDOM)


def declares_complex_survey(text: str | None) -> dict | None:
    """What the paper says about its sampling design, or None.

    Returns `{"marker": <matched text>, "quote": <the clause it sits in>}`.
    The quote is what a prompt or a refusal message shows the reader, so the
    claim is auditable against the paper's own sentence rather than being an
    assertion about a regex.

    FIRST MATCH ONLY, and no count. An earlier version also returned
    `n_markers`, on the argument that one marker and four are different
    evidence -- which is true, and nothing acted on it. A count of regex hits
    is not something a reader can check; the quote is. (The measurement that
    argument came from -- s12889 matching four markers, mmwr one -- came from
    the probe, not from this field, and is recorded in the comment above.)
    """
    if not text:
        return None
    for rx in _RX:
        m = rx.search(text)
        if m:
            return {"marker": m.group(0),
                    "quote": _clause_around(text, m.start(), m.end())}
    return None


def survey_refusal(tool_name: str, sampling: str | None) -> dict | None:
    """The structured refusal for a `REFUSED_UNDER_SURVEY` check, or None.

    ONE IMPLEMENTATION, CALLED FROM EACH TOOL, and the placement is deliberate.
    The registry's own gates are the model's path, but `cli.py` calls these
    functions DIRECTLY (`chi_squared.recalc_chi_squared(...)` at cli.py:2654) --
    so a gate that lived only in `ToolSpec.call` would leave every human
    reproduction string unguarded, which is the surface a reader uses to check
    an accusation. Same reason `grim_test` owns its `data_type` guard rather
    than delegating it upward.
    """
    if canonical_sampling(sampling) != COMPLEX_SURVEY:
        return None
    if tool_name not in REFUSED_UNDER_SURVEY:
        return None
    return {
        "severity": "indeterminate",
        "applicable": False,
        "consistent": False,
        "error": (
            f"{tool_name} rebuilds a test statistic from printed summary "
            "statistics, and this analysis is declared COMPLEX SURVEY "
            "(sampling='complex_survey')."
        ),
        "explanation": (
            "Not evaluated. This is a refusal, not a weak finding, and not a "
            "statement about the paper. Under a weighted, stratified, clustered "
            "design the published estimate and its standard error come from a "
            "design-based variance estimator on a t with the survey degrees of "
            "freedom, and neither is a function of the printed means, SDs or "
            "counts -- weighting moves the composition of the sample, not "
            "merely its variance. A disagreement here is therefore expected in "
            "BOTH directions and carries no information. Counting checks on "
            "printed integers (check_count_percent, check_summation, "
            "check_flow_arithmetic, the GRIM family) are valid under any design "
            "and still run."
        ),
        "sampling": COMPLEX_SURVEY,
        "methodology": "Sampling-design applicability gate (complex survey).",
    }
