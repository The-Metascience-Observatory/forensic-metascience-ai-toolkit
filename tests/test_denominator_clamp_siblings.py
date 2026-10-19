"""The denominator clamp protected the check that cannot accuse, and not the
check that can.

`_clamp_shared_denominator` exists because a survey paper computing percentages
over the respondents to an item -- routine practice -- disagrees with its own
header n and looks like arithmetic error. It clamped `check_count_percent`,
which ALREADY caps itself at `suspicious` because "a different percentage base
is an ordinary reporting convention, not a defect". `grim_percentage` is routed
to the SAME cell with the SAME n, has no ceiling, and was not clamped.
"""

from __future__ import annotations

import pytest

from metascience_agent.dispatch import check_table

VARIABLE = {"id": "v1", "name": "Reported full compliance",
            "measurement_level": "nominal", "discreteness": "discrete",
            "family": "binary", "lower_bound": 0, "upper_bound": 1,
            "derivation": "measured", "confidence": "high",
            "provenance_quote": "q", "provenance_verdict": "verbatim"}

HEADER_N = 352
ANSWERED = 340          # the item's real denominator


def _cell(count: int, pct: float):
    return {"raw": f"{count} ({pct})", "row_label": VARIABLE["name"],
            "col_label": "n (%)", "n": HEADER_N}


def _run(cells):
    return check_table(cells=cells, variables=[VARIABLE],
                       bindings={VARIABLE["name"]: "v1"})


def _sev(out, tool):
    return [r.get("severity") for r in out["results"] if r.get("tool") == tool]


HONEST = [_cell(c, round(100 * c / ANSWERED, 1)) for c in (90, 127, 123)]


class TestTheHonestTableIsNotAccused:
    """PLoS ONE 0128753 Table 1, the table the clamp's own docstring is built
    from: header n = 352, percentages taken over the 340 who answered."""

    def test_grim_percentage_is_no_longer_impossible(self):
        out = _run(HONEST)
        assert _sev(out, "grim_percentage") == ["indeterminate"] * 3

    def test_the_table_severity_is_not_an_accusation(self):
        assert _run(HONEST)["severity"] == "indeterminate"

    def test_it_inherits_the_explanation_rather_than_going_silent(self):
        """A clamped row must still tell the reader what denominator it
        implies -- the disagreement with the header is a real and useful fact."""
        out = _run(HONEST)
        grim = [r for r in out["results"] if r.get("tool") == "grim_percentage"]
        for r in grim:
            assert r["clamped_by"] == "shared_section_denominator"
            assert "340" in r["clamp_reason"]
            assert "check_count_percent" in r["clamp_reason"]

    def test_the_sibling_was_already_protected(self):
        """The asymmetry, pinned: this is what grim_percentage was missing."""
        out = _run(HONEST)
        assert _sev(out, "check_count_percent") == ["indeterminate"] * 3


class TestARealErrorStillReachesTheReader:
    """The counter-test. A clamp that buys safety by disabling the check is
    worse than the defect it fixes."""

    def test_a_genuine_slip_among_correct_rows_is_still_impossible(self):
        rows = [_cell(c, round(100 * c / HEADER_N, 1)) for c in (90, 127)]
        rows.append(_cell(123, 61.2))       # 123/352 = 34.9%, printed 61.2
        out = _run(rows)
        assert "impossible" in _sev(out, "grim_percentage")
        assert out["severity"] == "impossible"

    def test_a_lone_row_far_from_the_header_is_still_impossible(self):
        """Only NEAR misses are non-response; a denominator of 147 against a
        header of 352 is not missing data."""
        out = _run([_cell(90, 61.2)])
        assert _sev(out, "grim_percentage") == ["impossible"]

    def test_the_clamp_never_raises_a_severity(self):
        """Propagation is downward-only by construction."""
        from metascience_agent.dispatch import _propagate_denominator_clamp
        results = [
            {"tool": "check_count_percent", "severity": "indeterminate",
             "clamped_by": "shared_section_denominator", "clamp_reason": "r",
             "cell": {"row_label": "x", "row": 1, "ordinal": 0, "raw": "90 (26.5)"}},
            {"tool": "grim_percentage", "severity": "consistent",
             "cell": {"row_label": "x", "row": 1, "ordinal": 0, "raw": "90 (26.5)"}},
        ]
        _propagate_denominator_clamp(results)
        assert results[1]["severity"] == "consistent"

    def test_an_unclamped_sibling_is_untouched(self):
        from metascience_agent.dispatch import _propagate_denominator_clamp
        results = [
            {"tool": "check_count_percent", "severity": "suspicious",
             "cell": {"row_label": "x", "row": 1, "ordinal": 0, "raw": "1 (2)"}},
            {"tool": "grim_percentage", "severity": "impossible",
             "cell": {"row_label": "x", "row": 1, "ordinal": 0, "raw": "1 (2)"}},
        ]
        _propagate_denominator_clamp(results)
        assert results[1]["severity"] == "impossible"

    def test_a_different_cell_does_not_inherit(self):
        """Cell identity is what licenses the inheritance."""
        from metascience_agent.dispatch import _propagate_denominator_clamp
        results = [
            {"tool": "check_count_percent", "severity": "indeterminate",
             "clamped_by": "shared_section_denominator", "clamp_reason": "r",
             "cell": {"row_label": "a", "row": 1, "ordinal": 0, "raw": "90 (26.5)"}},
            {"tool": "grim_percentage", "severity": "impossible",
             "cell": {"row_label": "b", "row": 2, "ordinal": 0, "raw": "5 (9.9)"}},
        ]
        _propagate_denominator_clamp(results)
        assert results[1]["severity"] == "impossible"


class TestOnlyTheEvidencedClampPropagates:
    """The two clamps rest on different evidence and must not travel together.

    `shared_section_denominator` rests on AGREEMENT -- several rows landing on
    exactly one unstated denominator, which errors do not do.
    `lone_row_near_denominator` rests on nothing but charity: its own comment
    says one row is "indistinguishable from a one-digit slip in the percentage,
    and no arithmetic can separate them". That charity was granted to a check
    capped at `suspicious`; spending it again on a check that can say
    `impossible` suppresses real findings.

    The suite caught this before it shipped -- propagating both clamps broke
    `test_printed_precision::test_a_genuine_impossibility_is_still_caught`.
    """

    def test_a_lone_row_clamp_does_not_propagate(self):
        from metascience_agent.dispatch import _propagate_denominator_clamp
        cell = {"row_label": "x", "row": 1, "ordinal": 0, "raw": "101 (71.5%)"}
        results = [
            {"tool": "check_count_percent", "severity": "indeterminate",
             "clamped_by": "lone_row_near_denominator", "clamp_reason": "r",
             "cell": cell},
            {"tool": "grim_percentage", "severity": "impossible", "cell": cell},
        ]
        _propagate_denominator_clamp(results)
        assert results[1]["severity"] == "impossible"

    def test_the_genuine_impossibility_that_caught_it(self):
        """`101 (71.5%)` at n = 142: 71.5% is unreachable, and the implied
        denominator 141 is one below the header, which fires the lone-row
        clamp. GRIM must still say so."""
        out = check_table(
            cells=[{"raw": "101 (71.5%)", "row_label": "Male, n (%)", "n": 142}],
            variables=[{"id": "v1", "name": "Male", "family": "binary"}],
            bindings={"Male, n (%)": "v1"}, provenance="printed_table")
        assert out["severity"] == "impossible"
