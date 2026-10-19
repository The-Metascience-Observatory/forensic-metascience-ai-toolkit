"""`values.csv`: the account's values in long form, and nothing else.

The account is already normalised -- every value IS a row at a coordinate -- so
the long form is a PROJECTION of it. The property that makes it worth having is
also the one that makes it safe: one row per value, exactly, and every cell a
field the account carries or a rendering of one. A file that dropped rows would
be a coverage claim nobody made; one that added them would be an invention.
"""

from __future__ import annotations

import csv
import io

import pytest

from metascience_agent.scaffold import export

ACCOUNT = {
    "structure": {"version": 2},
    "code": {"code_commit": "da685a4003fc", "sha256": "5d9f7da81593f86b"},
    "values": [
        {"id": "val:t1:r1:c1:0:mean", "statistic": "mean", "printed": "3.83", "numeric": 3.83,
         "units": None, "variable_id": "var:comm", "level_id": None, "source": "table",
         "quote_verified": "cell", "coordinate_source": "caption_join",
         "coordinate": {"study_id": "study:1", "group_id": "grp:a", "phase_id": None},
         "location": {"kind": "table_cell", "table_id": "table:1", "row": 1, "col": 1}},
        {"id": "val:p1", "statistic": "percentage", "printed": "60", "numeric": 60.0,
         "units": "%", "variable_id": None, "level_id": None, "source": "prose",
         "quote_verified": "verbatim", "coordinate_source": None,
         "coordinate": {"study_id": None, "group_id": None, "phase_id": None},
         "location": {"kind": "results", "offset": 1234, "end": 1250}},
        {"id": "val:param:x", "statistic": "setting", "printed": "two or more", "numeric": None,
         "units": None, "variable_id": None, "level_id": None, "source": "methods_parameter",
         "quote_verified": "verbatim",
         "coordinate": {"study_id": None, "group_id": None, "phase_id": None},
         "location": {"kind": "methods", "offset": None, "procedure_id": "proc:survey"}},
    ],
}


@pytest.fixture()
def parsed():
    return list(csv.DictReader(io.StringIO(export.values_csv(ACCOUNT))))


class TestOneRowPerValue:

    def test_the_row_count_is_exactly_the_number_of_values(self, parsed):
        assert len(parsed) == len(ACCOUNT["values"])

    def test_an_empty_account_writes_a_header_and_no_rows(self):
        text = export.values_csv({"values": []})
        assert text.strip() == ",".join(export.COLUMNS)
        assert list(csv.DictReader(io.StringIO(text))) == []

    def test_the_columns_are_fixed_and_ordered(self, parsed):
        assert list(parsed[0]) == list(export.COLUMNS)

    def test_every_value_id_appears_once(self, parsed):
        assert [r["value_id"] for r in parsed] == [v["id"] for v in ACCOUNT["values"]]


class TestItAddsNoInformation:

    def test_every_cell_traces_to_the_account(self, parsed):
        r = parsed[0]
        v = ACCOUNT["values"][0]
        assert r["statistic"] == v["statistic"] and r["printed"] == v["printed"]
        assert r["value"] == "3.83" and r["variable_id"] == "var:comm"
        assert r["study_id"] == "study:1" and r["group_id"] == "grp:a"
        assert r["coordinate_source"] == "caption_join"
        assert r["quote_verified"] == "cell"

    def test_an_absent_field_is_an_empty_cell_and_never_the_word_none(self):
        text = export.values_csv(ACCOUNT)
        assert "None" not in text
        rows = list(csv.DictReader(io.StringIO(text)))
        assert rows[1]["group_id"] == "" and rows[1]["coordinate_source"] == ""
        assert rows[2]["value"] == ""

    def test_the_location_takes_the_form_its_own_kind_takes(self, parsed):
        assert parsed[0]["location"] == "table:1 r1 c1"
        assert parsed[1]["location"] == "results@1234"
        assert parsed[2]["location"] == "methods:proc:survey"

    def test_each_row_names_the_vocabulary_and_the_code_it_was_written_by(self, parsed):
        for r in parsed:
            assert r["structure_version"] == "2"
            assert r["code_commit"] == "da685a4003fc"

    def test_an_account_with_no_structure_leaves_the_version_empty(self):
        rows = list(csv.DictReader(io.StringIO(export.values_csv(
            {"values": ACCOUNT["values"][:1]}))))
        assert rows[0]["structure_version"] == "" and rows[0]["code_commit"] == ""


class TestItIsWritten:

    def test_the_entry_point_writes_it_beside_the_account(self):
        import inspect
        from metascience_agent.scaffold import __main__ as m
        src = inspect.getsource(m.main)
        assert '(out / "values.csv").write_text(_export.values_csv(account)' in src
