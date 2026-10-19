"""The register enumerates; the regex floor keeps it honest.

GREG, 2026-08-15: "implement the register then, with the regex set as the floor".

The design tension this module exists to resolve: THE FINDER SHOULD BE THE MODEL
-- it is the only reader that recognises `(M = 2.26, SD = 1.32)`, `M = 4.44
(1.57)`, `β = 0.24` and `AOR 0.55 (0.32-0.94)`, four conventions the regex set
has no pattern for -- but THE DENOMINATOR MUST BE INDEPENDENT OF THE FINDER, or
coverage is `(what it checked) / (what it decided was checkable)` and improves
as the enumeration degrades.
"""
from metascience_agent import register as R

TEXT = ("Participants rated losing control while eating (M = 2.26, SD = 1.32) and "
        "difficulties resisting eating (M = 2.79, SD = 1.42). Negative affect "
        "predicted dysregulation, t(28) = -3.33, p = .004, at the within-person "
        "(b = 0.24) level.")


def _row(**over):
    row = {"source": "prose", "kind": "mean_sd", "values": {"M": 2.26, "SD": 1.32},
           "quote": "losing control while eating (M = 2.26, SD = 1.32)",
           "location": "Measures", "checkable": {"tools": ["grim_check"]}}
    row.update(over)
    return row


class TestTheFloorIsCheckedValueByValue:
    """A register with the same NUMBER of rows as the regex found, listing
    different statistics, has missed things. Comparing totals scores that as
    agreement, which is why the floor matches spans rather than counts."""

    FLOOR = [{"raw": "t(28) = -3.33", "kind": "nhst", "offset": 120},
             {"raw": "p = .004", "kind": "p_value", "offset": 135}]

    def test_a_register_that_omits_a_located_statistic_fails_the_floor(self):
        out = R.validate([_row()], text=TEXT, floor_items=self.FLOOR)
        assert out["floor"]["ok"] is False
        assert out["floor"]["n_unmatched"] == 2
        assert "did not list them" in out["floor"]["note"]

    def test_matching_row_counts_do_not_excuse_a_different_set(self):
        """Two rows against two floor items, and still a failure."""
        out = R.validate([_row(), _row(values={"M": 2.79, "SD": 1.42},
                                       quote="difficulties resisting eating (M = 2.79, SD = 1.42)")],
                         text=TEXT, floor_items=self.FLOOR)
        assert len(out["rows"]) == len(self.FLOOR)
        assert out["floor"]["ok"] is False, "count parity is not coverage"

    def test_a_register_that_accounts_for_the_floor_passes(self):
        rows = [_row(), _row(kind="test_statistic", values={"t": -3.33, "df": 28, "p": 0.004},
                             quote="t(28) = -3.33, p = .004",
                             checkable={"tools": ["recalc_stat_to_p"]})]
        out = R.validate(rows, text=TEXT, floor_items=self.FLOOR)
        assert out["floor"]["ok"] is True

    def test_the_floor_does_not_apply_to_table_rows(self):
        """Table statistics have their own cell census. Holding the register to
        a BODY-TEXT regex for them manufactures a shortfall from a category
        mismatch."""
        out = R.validate([_row(source="table")], text=TEXT, floor_items=[])
        assert out["floor"]["ok"] is True


class TestNothingIsSilentlyDropped:
    def test_an_unverified_row_is_marked_and_still_counted(self):
        """A register that discards its own bad rows is one whose denominator
        improves every time the model makes a mistake."""
        bad = _row(quote="a sentence that is not in this paper at all")
        out = R.validate([bad], text=TEXT, floor_items=[])
        assert out["n_unique"] == 1
        assert out["rows"][0]["verification"]["quote_located"] is False
        assert "not found in the paper" in " ".join(out["rows"][0]["verification"]["problems"])

    def test_a_value_missing_from_its_own_quote_is_a_transcription_error(self):
        out = R.validate([_row(values={"M": 9.99, "SD": 1.32})], text=TEXT, floor_items=[])
        v = out["rows"][0]["verification"]
        assert v["quote_located"] is True and v["values_in_quote"] is False
        assert "9.99" in " ".join(v["problems"])

    def test_duplicates_are_marked_not_merged(self):
        out = R.validate([_row(), _row()], text=TEXT, floor_items=[])
        assert out["n_rows"] == 2 and out["n_unique"] == 1 and out["n_duplicates"] == 1


class TestCheckabilityIsAColumnNeverAFilter:
    """A statistic no tool can check is a row carrying a reason. That is the
    whole difference between a denominator and a self-report."""

    def test_no_tools_and_no_reason_is_a_problem(self):
        out = R.validate([_row(checkable={"tools": []})], text=TEXT, floor_items=[])
        assert any("gives no reason" in p for p in out["rows"][0]["problems"])

    def test_no_tools_WITH_a_reason_is_a_legitimate_row(self):
        out = R.validate([_row(checkable={"tools": [], "reason":
                                          "a standardised coefficient with no SE or n"})],
                         text=TEXT, floor_items=[])
        assert out["rows"][0]["problems"] == []
        assert out["n_unique"] == 1 and out["n_checkable"] == 0, \
            "it counts in the denominator and not in the numerator -- that is the point"


class TestAbsenceIsNotEmptiness:
    def test_no_register_is_distinguishable_from_an_empty_one(self):
        absent = R.validate(None, text=TEXT, floor_items=[])
        empty = R.validate([], text=TEXT, floor_items=[])
        assert absent["absent"] is True and empty["absent"] is False
        assert "no statistics register was emitted" in absent["note"]

    def test_no_paper_text_makes_verification_OUR_gap(self):
        out = R.validate([_row()], text=None, floor_items=[])
        assert "our gap" in " ".join(out["rows"][0]["verification"]["problems"]).lower()


class TestItSaysWhatItCannotMeasure:
    def test_the_count_is_labelled_as_what_the_agent_located(self):
        out = R.validate([_row()], text=TEXT, floor_items=[])
        assert "LOCATED" in out["note"] and "recall is unmeasured" in out["note"]

    def test_provenance_is_carried_not_assumed(self):
        """A register built from pdfplumber text, or from quarantined text,
        holds values that may be wrong in ways no arithmetic detects."""
        out = R.validate([_row()], text=TEXT, floor_items=[],
                         provenance={"n_pdfplumber": 1, "all_high_fidelity": False})
        assert out["provenance"]["all_high_fidelity"] is False


class TestItIsConsumed:
    def test_the_run_attaches_the_register_to_the_report(self):
        import pathlib
        src = (lambda r: (r / "src/metascience_agent/agent.py").read_text(encoding="utf-8")
                   + (r / "src/metascience_agent/parallel.py").read_text(encoding="utf-8")
                   )(pathlib.Path(__file__).resolve().parents[1])
        # The live pipeline builds it in `parallel._build_coverage_summary`
        # and files it under `coverage_summary`.
        assert '"statistics_register"' in src and 'coverage_summary' in src

    def test_the_schema_offers_it_and_does_not_require_it(self):
        import json
        import pathlib
        s = json.loads((pathlib.Path(__file__).resolve().parents[1]
                        / "src/metascience_agent/schema/findings.v2.schema.json"
                        ).read_text(encoding="utf-8"))
        assert "statistics_register" in s["properties"]
        assert "statistics_register" not in s.get("required", []), \
            "requiring it would stop every archived run from parsing"

    def test_the_prompt_teaches_enumerate_before_judging(self):
        import pathlib
        from metascience_agent.core.prompts import tool_expert_body
        md = tool_expert_body()   # the prompt as assembled, guidance included
        assert "statistics_register" in md
        assert "ENUMERATE BEFORE YOU JUDGE" in md
