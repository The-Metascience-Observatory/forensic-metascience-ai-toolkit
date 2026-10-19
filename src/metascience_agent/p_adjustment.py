"""Does the paper declare a correction that adjusts its printed p-values?

A Huynh-Feldt / Greenhouse-Geisser p printed beside the UNCORRECTED df, or a
Bonferroni / Holm / Tukey / Scheffe adjusted p printed beside its raw
statistic, is LARGER than the statistic implies -- which the p tools read as an
under-claim unless they are told the correction (`p_adjustment`).

MEASURED 2026-10-18 on the deterministic p-tool benchmark
(benchmarks/pvalue_tools): all 12 false flags on the 1,071 statistics
Wicherts, Bakker & Molenaar (2011) coded as correct were Huynh-Feldt p's, and
95 of the 96 statcheck flags Nuijten et al. (2017) found explained by a
declared correction were flagged. With the correction passed, both fall to
0 and 2.

Same shape as `survey_design.declares_complex_survey`: the paper's OWN clause
is returned, so the claim "this paper corrects its p's" is auditable against
the source rather than being an assertion about a regex, and the tools agent
decides per statistic which p's the correction covers.
"""

from __future__ import annotations

import re

from .scope import _clause_around

#: (kind, pattern). Sphericity corrections first: a paper declaring both is
#: told about both.
_MARKERS: tuple[tuple[str, str], ...] = (
    ("sphericity", r"greenhouse[\s\-–]*geisser"),
    ("sphericity", r"huynh[\s\-–]*feldt"),
    ("sphericity", r"sphericity[\s\-–]*(?:correct|adjust)\w*"),
    ("sphericity", r"(?:correct|adjust)\w*\s+for\s+(?:violations?\s+of\s+)?sphericity"),
    ("multiplicity", r"bonferroni"),
    ("multiplicity", r"holm(?:[\s\-–]*bonferroni)?\b"),
    ("multiplicity", r"\b[šs]id[aá]k"),
    ("multiplicity", r"tukey(?:'?s)?\s*(?:hsd|honest|post[\s\-]*hoc|test|correct)"),
    ("multiplicity", r"scheff[eé]"),
    ("multiplicity", r"benjamini[\s\-–]*hochberg|false\s+discovery\s+rate"),
    ("multiplicity", r"(?:correct|adjust)\w*\s+for\s+multiple\s+(?:comparisons|testing|tests)"),
    ("multiplicity", r"adjusted\s+p[\s\-]*values?"),
)
_RX = tuple((kind, re.compile(p, re.I)) for kind, p in _MARKERS)


def declares_p_adjustment(text: str | None) -> list[dict]:
    """Every KIND of correction the paper declares, first match per kind.

    Returns `[{"kind": "sphericity" | "multiplicity", "marker": ..., "quote": ...}]`,
    empty when none is declared.
    """
    if not text:
        return []
    found: dict[str, dict] = {}
    for kind, rx in _RX:
        if kind in found:
            continue
        m = rx.search(text)
        if m:
            found[kind] = {"kind": kind, "marker": m.group(0),
                           "quote": _clause_around(text, m.start(), m.end())}
    return list(found.values())


def p_adjustment_note(text: str | None) -> str:
    """The prompt block telling the analysts which correction the paper declares."""
    found = declares_p_adjustment(text)
    if not found:
        return ""
    lines = ["\n\n**THIS PAPER DECLARES A CORRECTION TO SOME OF ITS p-VALUES.** Its own words:"]
    for f in found:
        lines.append(f"> ({f['kind']}) {f['quote']}")
    lines.append(
        "\nA corrected p printed beside the UNCORRECTED statistic is larger than the "
        "statistic implies. That is EXPECTED, not a finding. For each statistic the "
        "correction covers (and only those -- read which tests it applies to), pass "
        "`p_adjustment=\"sphericity\"` or `\"multiplicity\"` to `recalc_stat_to_p`, "
        "`recalc_f_to_p`, `recalc_anova`, `recalc_independent_t`, `recalc_chi_squared` "
        "and `check_regression`. They then report that direction as indeterminate. A "
        "printed p SMALLER than the statistic allows is never explained by a "
        "correction and is still a finding.")
    return "\n".join(lines)
