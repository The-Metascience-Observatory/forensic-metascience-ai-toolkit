"""`_repro_entries` labels a v2 row by its `finding_id`, and walks only the live document.

Until 2026-09-05 it yielded `str(f.get("id", i))` -- the row's INDEX on every
v2 row, which carries `finding_id` -- so `reproducibility.problems` read
`finding[0]: ...` instead of naming the row. And it walked
`result["report_obj"]`, the serial pipeline's editorial report, which no
writer has produced since v1.27.0. Both reads sat in `agent.py`, which
`tests/test_v1_residue_ratchet.py` excluded by name; they were the only
structure-level and one of the two field-level residue reads left in that
file, and the ratchet had never counted them.

Fixtures are shaped on live rows (`finding_id`, `provisional_severity`, no
`id`) and the last class refuses to let them drift back to v1.
"""
from __future__ import annotations

import copy

import pytest

from metascience_agent import agent as A


def _entries(result):
    """The function's home moves in the split; resolve it wherever it is."""
    try:
        from metascience_agent import annotators
        return annotators._repro_entries(result)
    except ImportError:
        return A._repro_entries(result)


def _annotate(result, **kw):
    try:
        from metascience_agent import annotators
        return annotators.annotate_reproductions(result, **kw)
    except ImportError:
        return A._annotate_reproductions(result, **kw)


# Shaped on litvak05 `f_0fd8774546f184a7`: a kept model-reading accusation.
PRODUCER_ROW = {
    "slug": "statcheck_t_p_mismatch", "finding_id": "f_0fd8774546f184a7",
    "producer": "tool_expert", "technique": "statcheck", "outcome": "problem",
    "provisional_severity": 3, "severity_is_provisional": True,
    "computed_by": "model_reading", "location": "Results, paragraph 2",
    "title": "t", "description": "d", "quote": "q",
}
V1_ROW = {"id": "s1", "technique": "grim_check", "severity": "suspicious",
          "location": "Table 1"}


class TestReproEntriesLabelTheRow:
    def test_a_v2_row_is_labelled_by_finding_id(self):
        r = {"findings": {"findings": [dict(PRODUCER_ROW, reproduction="metascience grim 1 2")]}}
        assert [label for label, _ in _entries(r)] == ["f_0fd8774546f184a7"]

    def test_an_archived_v1_row_is_labelled_by_id_and_a_bare_row_by_index(self):
        r = {"findings": {"findings": [dict(V1_ROW), {"reproduction": "x"}]}}
        assert [label for label, _ in _entries(r)] == ["s1", "1"]

    def test_the_headline_is_still_walked(self):
        r = {"findings": {"headline": {"reproduction": "x"}, "findings": []}}
        assert [label for label, _ in _entries(r)] == ["headline"]

    def test_report_obj_is_not_walked(self):
        """No writer has produced `report_obj` since v1.27.0; a result that
        somehow carries one is not the live shape and must not be annotated
        as if it were."""
        r = {"findings": {"findings": [dict(PRODUCER_ROW)]},
             "report_obj": {"headline": {"reproduction": "x"}, "findings": [dict(V1_ROW)]}}
        assert [label for label, _ in _entries(r)] == ["f_0fd8774546f184a7"]
        untouched = copy.deepcopy(r)
        untouched["run_meta"] = {}
        _annotate(untouched, execute=False)
        assert "reproduction_valid" not in untouched["report_obj"]["headline"]

    def test_the_problem_message_names_the_row(self):
        """The label's one reader: `reproducibility.problems`."""
        r = {"findings": {"findings": [dict(PRODUCER_ROW, reproduction="not a command")]},
             "run_meta": {}}
        summary = _annotate(r, execute=False)
        problems = " ".join(summary.get("problems") or [])
        assert "f_0fd8774546f184a7" in problems, summary
        assert "finding[0]" not in problems

    def test_the_defect_shape_is_the_index(self):
        """Known positive: the pre-fix expression on the live fixture."""
        f, i = dict(PRODUCER_ROW), 0
        assert str(f.get("id", i)) == "0"


class TestTheFixturesAreLiveShaped:
    def test_the_v2_fixture_carries_no_v1_id(self):
        assert "id" not in PRODUCER_ROW and "finding_id" in PRODUCER_ROW

    def test_the_producer_fixture_has_no_severity_key(self):
        assert "severity" not in PRODUCER_ROW and "provisional_severity" in PRODUCER_ROW

    def test_the_source_no_longer_reads_report_obj(self):
        import inspect
        try:
            from metascience_agent import annotators as home
        except ImportError:
            home = A
        src = inspect.getsource(home._repro_entries)
        body = src.split('"""')[-1]          # after the docstring
        assert "report_obj" not in body
        assert 'get("id"' not in body
