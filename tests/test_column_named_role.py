"""A column headed `p` names the role its cells carry.

MEASURED 2026-08-20 over the eleven-paper run: 468 values reached the register
with role `unknown` while sitting under a column header that says `p` or
`P value`. A p-value is the most checkable thing a table prints -- it is what
`statcheck` exists for -- and an untyped one dispatches to nothing.

The marker was in the COLUMN HEADER and the cell parser reads only the cell:
the same seam that hid the stacked header, one layer up.

THE BOUND IS THE GUARD. A p-value lies in [0, 1]. A number outside it under a
`p` heading is evidence the column is MISALIGNED, not evidence of an impossible
p-value, so it stays `unknown` and no check may dispatch on it. Typing it
would manufacture exactly the accusation this repository exists to avoid.
"""
import pytest

from forensic_metascience_ai_toolkit import values as V


class TestAColumnHeaderCanNameTheRole:
    @pytest.mark.parametrize("label", [
        "p", "P", "p value", "P value", "P-value", "p-val", "adj. p",
        "Within-Person | p", "Model 2 | P Value",
    ])
    def test_a_p_column_is_recognised(self, label):
        assert V.role_from_column(label, 0.02) == "p"

    @pytest.mark.parametrize("label", [
        "n", "Mean (SD)", "AOR (95% CI)", "Proportion (%)", "beta",
        "Population", "Sample p articipants", "",
    ])
    def test_other_columns_are_not_claimed(self, label):
        assert V.role_from_column(label, 0.02) is None

    @pytest.mark.parametrize("bad", [1.5, -0.2, 42.0, 3.42])
    def test_an_out_of_bounds_value_stays_unknown(self, bad):
        assert V.role_from_column("P value", bad) is None, (
            "out of [0,1] means the column is misaligned, not that the "
            "paper printed an impossible p-value")

    @pytest.mark.parametrize("ok", [0.0, 1.0, 0.049, 0.9999])
    def test_the_bounds_are_inclusive(self, ok):
        assert V.role_from_column("P value", ok) == "p"

    def test_a_missing_value_claims_nothing(self):
        assert V.role_from_column("P value", None) is None


class TestAFootnoteMarkerIsNotPartOfTheName:
    """MEASURED 2026-08-20: 202 further p-values sat untyped under headings
    like `P valuec`, `P valued` and `MHT p-value`. The `c`/`d`/`e` are
    FOOTNOTE MARKERS welded to the label by the extractor, and `MHT` is a
    qualifier (multiple-hypothesis-testing); an adjusted p is still a p.

    `celltypes._TRAILING_MARKER` deliberately refuses to strip a welded ASCII
    letter after a NUMBER, because `12.3a` could be annum and guessing is what
    that module exists not to do. That ambiguity does not exist after the word
    `value`: no unit attaches there. So the allowance belongs in the HEADER
    matcher and must not be pushed down into the numeric one.
    """

    @pytest.mark.parametrize("label", [
        "P valuec", "P valued", "P valuee", "p valuea",
        "P valueᶜ", "P value*", "P value†",
        "MHT p-value", "MHT P valued", "Adjusted p value",
    ])
    def test_the_marker_does_not_hide_the_column(self, label):
        assert V.role_from_column(label, 0.03) == "p"

    @pytest.mark.parametrize("label", [
        "Population", "Sample participants", "Placebo", "Parity",
        "Proportion (%)", "Predictor", "Percent", "People",
    ])
    def test_a_word_beginning_with_p_is_still_not_a_p_column(self, label):
        assert V.role_from_column(label, 0.03) is None

    def test_a_qualifier_alone_does_not_make_a_p_column(self):
        # A prefix is allowed only ahead of an explicit `p value`, never
        # ahead of a bare `p`: `Sample p` would otherwise be claimed.
        assert V.role_from_column("Sample p", 0.03) is None

    def test_the_bound_still_guards_the_marked_form(self):
        assert V.role_from_column("P valuec", 7.4) is None


class TestTheRawDataClaimStaysMeasured:
    """A measured claim in a docstring can be FALSIFIED by a fix elsewhere.

    `is_deposited_raw_data` asserted that the corpus held "NOT ONE formatted
    supplementary statistics table", and concluded from that absence that no
    classifier could be validated. The claim was true when written and false
    three commits later: repairing the .docx header depth revealed 37 such
    tables that had been surfacing with unlabelled columns.

    Nothing failed when it rotted, because a docstring asserts to humans only.
    This pins it: if the numbers leave, the claim has become an assertion.
    """

    def test_the_falsified_claim_is_not_restated(self):
        import inspect
        src = inspect.getsource(V.is_deposited_raw_data)
        assert "no negative example" not in src.lower(), (
            "the corpus has 37 of them; the old conclusion must not return")

    def test_the_correction_carries_its_measurement(self):
        import inspect
        src = inspect.getsource(V.is_deposited_raw_data)
        for token in ("2,421", "4,944", "37 tables", "FALSIFIED"):
            assert token in src, f"the re-measurement must keep {token!r}"

    def test_the_asymmetry_is_recorded(self):
        """WHY the behaviour was left alone is the load-bearing part: the
        current error flatters coverage, the opposite one accuses a paper."""
        import inspect
        src = inspect.getsource(V.is_deposited_raw_data)
        assert "POSITIVE PROOF" in src and "FLATTERS" in src

    def test_the_behaviour_really_is_unchanged(self):
        assert V.is_deposited_raw_data({"anchor": {"table": "supp:x.docx :: Table 4"}})
        assert not V.is_deposited_raw_data({"anchor": {"table": "TABLE 1"}})


class TestATruncatedHeaderIsStillAPColumn:
    """`p-v` is `p-value` with the end cut off by the extractor.

    MEASURED 2026-08-22, after the repeated-header fix made a stacked
    supplement's inner level visible: 168 values sit under a column labelled
    `p-v`. Docling truncates header text, and the column is a p-value column in
    every one of them.

    THE ALLOWANCE IS A PREFIX OF ONE KNOWN WORD, not arbitrary text after `p`.
    `p-v`, `p-va`, `p-val`, `p-valu` are truncations of `value`; `p-w` is not
    anything and must not match. That keeps the rule as tight as the one it
    extends while covering what the extractor actually does.

    The [0,1] bound is unchanged and still decides: a number outside it under a
    truncated heading stays `unknown`, because a misaligned column is a likelier
    explanation than a paper printing an impossible p-value.
    """

    @pytest.mark.parametrize("label", ["p-v", "p-va", "p-val", "p-valu",
                                       "p value", "P-V", "MHT p-v"])
    def test_a_truncated_p_value_column_is_recognised(self, label):
        assert V.role_from_column(label, 0.03) == "p"

    @pytest.mark.parametrize("label", ["p-w", "p-x", "pop", "p-t", "prev"])
    def test_it_does_not_match_arbitrary_text_after_p(self, label):
        assert V.role_from_column(label, 0.03) is None

    def test_the_bound_still_guards_the_truncated_form(self):
        assert V.role_from_column("p-v", 4.2) is None
