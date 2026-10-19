"""A verdict that only holds at a df the paper never printed is not a verdict.

FROM THE ROMANO VARIABILITY STUDY, 2026-08-11. Two runs of one paper at
byte-identical prompt and schema handed `check_regression_batch` the SAME 68
Table-2 coefficients. Replayed from the archived ledger:

    df supplied      verdict          inconsistent rows
    (none)           indeterminate    0 of 0 evaluated
    10               SUSPICIOUS       5
    30               consistent       0
    100              consistent       0
    100000           consistent       0

Run B declined to supply a df and wrote up "the single largest verification gap
in the paper" -- a `suspicious` finding. Run C supplied `df=100000`, a number
appearing nowhere in the paper, got 68 of 68 consistent, and filed the whole
question under `not_checked`.

BOTH DIRECTIONS ARE THE FAILURE. A false accusation against an honest paper is
the worst output this toolkit can produce, and a false all-clear is second. Here
one model-chosen argument produced one of each on identical numbers, and neither
was attributable to the authors.

THE RULE. A df the paper printed is evidence and is never second-guessed. A df
the review supplied is an assumption, so the batch is re-run across
`DF_PROBES`; if the verdict is the same at every probe it is a property of the
numbers and stands, and if it changes the answer is `indeterminate` -- not "the
paper is fine", not "these disagree", but "this cannot be settled without a df
the paper did not print".

ABSENT `df_source` MEANS ASSUMED. That is the fail-safe direction and it is also
the historical truth: no archived call has ever set the field, and the one run
that supplied a df invented it.
"""
import json
from pathlib import Path

import pytest

from metascience_agent.tools.regression import (DF_PROBES, DF_REPORTED,
                                                check_regression_batch)

REPO = Path(__file__).resolve().parents[1]
LEDGER = REPO / ("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/"
                 "forensic_review_clamped/toolcalls.stage1.json")


def _rows(df=None, source=None, n=3, p_relation=None):
    """Coefficients whose verdict is df-dependent by construction: t = 2.33,
    which clears p < .05 two-tailed at df 30 but not at df 10."""
    out = []
    for i in range(n):
        r = {"b": 0.70, "se": 0.30, "reported_p": 0.04, "label": f"r{i}",
             "decimals_b": 2, "decimals_se": 2, "decimals_p": 3}
        if df is not None:
            r["df"] = df
        if source is not None:
            r["df_source"] = source
        if p_relation is not None:
            r["p_relation"] = p_relation
        out.append(r)
    return out


class TestAReportedDfIsEvidence:
    def test_it_is_never_second_guessed(self):
        out = check_regression_batch(_rows(df=100000, source=DF_REPORTED))
        assert out["df_provenance"] == "reported"
        assert "df_sensitivity" not in out, (
            "a df the paper printed is a fact about the paper; probing it would "
            "second-guess the authors rather than ourselves")

    def test_its_verdict_stands(self):
        """Whatever the printed df gives is the paper's verdict, unsoftened.

        At df 100000 the achievable p is [.017, .023]. Printed as a bound,
        "p < .040" is true. Printed EXACT, ".040" sits above all of it -- an
        under-claim since 1.86.0 (this asserted `consistent` before, when the
        under-claim direction was never checked) -- and a reported df does not
        get probed into `indeterminate`."""
        assert check_regression_batch(
            _rows(df=100000, source=DF_REPORTED, p_relation="<")
        )["severity"] == "consistent"
        out = check_regression_batch(_rows(df=100000, source=DF_REPORTED))
        assert out["severity"] == "suspicious"


class TestAnAssumedDfIsProbed:
    def test_absent_provenance_is_treated_as_assumed(self):
        """The fail-safe direction, and the historical truth: no archived call
        has ever set the field, and the one run that supplied a df invented it."""
        out = check_regression_batch(_rows(df=100000))
        assert out["df_provenance"] == "assumed"
        assert "df_sensitivity" in out

    def test_the_word_assumed_is_also_accepted(self):
        out = check_regression_batch(_rows(df=100000, source="assumed"))
        assert out["df_provenance"] == "assumed"

    def test_every_probe_is_reported_so_a_reader_can_check(self):
        out = check_regression_batch(_rows(df=100000))
        probes = out["df_sensitivity"]["probes"]
        assert {int(k) for k in probes} == set(DF_PROBES)

    def test_a_stable_verdict_survives_the_probe(self):
        """A coefficient wildly inconsistent at every df is inconsistent, and
        saying so does not depend on the assumption."""
        rows = [{"b": 5.0, "se": 0.1, "reported_p": 0.90, "df": 100,
                 "decimals_b": 1, "decimals_se": 1, "decimals_p": 2}]
        out = check_regression_batch(rows)
        if out["df_sensitivity"]["stable"]:
            assert out["severity"] != "indeterminate"
            assert "does not rest on that assumption" in out["explanation"]

    def test_an_unstable_verdict_becomes_indeterminate(self):
        out = check_regression_batch(_rows(df=100000))
        if not out["df_sensitivity"]["stable"]:
            assert out["severity"] == "indeterminate"

    def test_the_downgrade_is_visible_and_says_why(self):
        out = check_regression_batch(_rows(df=100000))
        if out["df_sensitivity"]["stable"]:
            pytest.skip("fixture stopped being df-sensitive")
        src = out["severity_source"]
        assert src["clamped_by"] == "assumed_df_changes_the_verdict"
        assert "not\n" not in src["why"]
        assert "supplied by this review" in src["why"]
        assert "df 10" in src["why"] and "df 30" in src["why"]


class TestItChangesNothingItShouldNot:
    def test_no_df_at_all_behaves_exactly_as_before(self):
        """Without a df the rows were already indeterminate. There is no
        assumption to probe, and inventing one would be the defect."""
        out = check_regression_batch(_rows())
        assert out["severity"] == "indeterminate"
        assert "df_sensitivity" not in out

    def test_an_empty_batch_is_untouched(self):
        out = check_regression_batch([])
        assert out["severity"] == "indeterminate" and out["n_rows"] == 0

    def test_row_level_results_are_preserved(self):
        """The reader must still see what each coefficient did; the clamp is on
        the aggregate verdict, not on the evidence."""
        out = check_regression_batch(_rows(df=100000, n=3))
        assert len(out["results"]) == 3
        assert all("row" in r for r in out["results"])


class TestTheArchivedCallThatReportedIt:
    """Replayed from the ledger on disk -- the real 68 coefficients."""

    @pytest.fixture(scope="class")
    def rows(self):
        if not LEDGER.exists():
            pytest.skip("clamped Romano run not in this checkout")
        led = json.loads(LEDGER.read_text(encoding="utf-8"))
        calls = [c for c in led if c.get("tool_short") == "check_regression_batch"]
        if not calls:
            pytest.skip("no check_regression_batch call in that ledger")
        return calls[0]["input"]["rows"]

    def test_the_run_supplied_a_df_the_paper_never_printed(self, rows):
        assert {r.get("df") for r in rows} == {100000}
        assert not any(r.get("df_source") for r in rows)

    def test_it_no_longer_returns_a_clean_bill(self, rows):
        """This is the regression. The shipped run reported 68 of 68
        consistent and filed the question as settled."""
        out = check_regression_batch([dict(r) for r in rows])
        assert out["severity"] == "indeterminate"
        assert out["df_sensitivity"]["stable"] is False

    def test_the_probe_reproduces_the_measured_flip(self, rows):
        """Measured 2026-08-11: df 10 accused, df 30 and above cleared. Since
        1.86.0 df 30 and 100 accuse too: an exact `.048` against B/SE at df 30
        (two-tailed [.051, .059]) was rescued only by the ONE-tailed reading
        (~.027) under the bound-only test, and an exact p matches neither. The
        flip itself -- and so `indeterminate` -- is unchanged."""
        out = check_regression_batch([dict(r) for r in rows])
        probes = out["df_sensitivity"]["probes"]
        assert probes["10"] == "suspicious", "df 10 accused 5 of these rows"
        assert probes["100000"] == "consistent", "the large-df reading clears them"

    def test_the_explanation_names_the_assumption(self, rows):
        out = check_regression_batch([dict(r) for r in rows])
        assert "did not print" in out["explanation"]
        assert "Ask the authors" in out["explanation"]

    def test_a_reported_df_would_have_stood(self, rows):
        """Not a hypothetical: it is the difference between a number on the
        page and a number we chose, and it is the whole rule."""
        out = check_regression_batch([dict(r, df_source=DF_REPORTED) for r in rows])
        assert out["severity"] == "consistent"


class TestTheModelIsToldAboutTheField:
    """A schema field the prompt never mentions is a field the model never
    sets, and this one defaults to the cautious reading -- so without the
    instruction every reported df would be probed as though invented."""

    def test_the_registry_description_explains_df_source(self):
        from metascience_agent.registry import BY_NAME
        desc = BY_NAME["check_regression_batch"].description
        assert "df_source" in desc
        assert "reported" in desc and "assumed" in desc
