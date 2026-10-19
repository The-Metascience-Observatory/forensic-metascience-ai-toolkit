"""A spreadsheet's first row is often its CAPTION, not its header.

MEASURED 2026-08-22 on `10.1038--s41537-025-00576-3`'s supplementary .xlsx,
which contributes 2,983 groups to the register -- the largest single supplement
in the corpus. Every sheet is laid out:

    row 0   'eTable 1. Proportion of ...'   (rest of the row empty)
    row 1   'ICD-10 code' | 'Diagnosis' | 'Cases (n)' | 'Prevalence (%)'
    row 2   'I10'         | 'Primary hypertension' | '1306' | '46.15'

`_finish` takes one header row, so the CAPTION becomes the column labels: three
of four columns end up `(unlabelled column N)` and the real header is read as
data. Measured consequence: 2,983 of 2,983 values (100%) sit under a column
with no name.

WHAT THAT COSTS is not just tidiness. Those sheets pair `Cases (n)` with
`Prevalence (%)`, which is a count/percent relationship `check_count_percent`
exists to verify -- and it cannot fire on a column it cannot name.

WHY THIS NEEDS ITS OWN RULE. The .docx fix proved header depth from OOXML span
markup. openpyxl reports NO merged ranges on these sheets (`merged=[]`), so
there is nothing to prove depth with. The signature that IS present is
structural: a first row holding exactly one value in a sheet several columns
wide, followed by a row that reads as LABELS rather than measurements.

`jats._reads_as_measurements` already draws that second distinction and is
reused rather than re-spelled.

FAILS CLOSED. If the row below the candidate caption reads as measurements, the
caption is not promoted -- a header that eats a data row is the worse error,
because a measurement that leaves the body stops existing for every check.
"""
import pytest

from forensic_metascience_ai_toolkit.extraction import supplements_read as S


class TestACaptionRowIsNotAHeader:
    def _grid(self):
        return [
            ["eTable 1. Proportion of comorbidities", "", "", ""],
            ["ICD-10 code", "Diagnosis", "Cases (n)", "Prevalence (%)"],
            ["I10", "Primary hypertension", "1306", "46.15"],
            ["I25", "Chronic ischemic heart disease", "490", "17.31"],
        ]

    def test_the_real_header_becomes_the_labels(self):
        t = S._finish([r[:] for r in self._grid()], 1, "ST1", "", "x", "xlsx")
        assert t["headers"][2] == "Cases (n)"
        assert t["headers"][3] == "Prevalence (%)"

    def test_no_column_is_left_unnamed(self):
        t = S._finish([r[:] for r in self._grid()], 1, "ST1", "", "x", "xlsx")
        unnamed = [h for h in t["headers"] if "unlabelled column" in str(h)]
        assert not unnamed, f"still unnamed: {unnamed}"

    def test_the_caption_is_kept_as_the_caption(self):
        t = S._finish([r[:] for r in self._grid()], 1, "ST1", "", "x", "xlsx")
        assert "eTable 1" in str(t.get("caption"))

    def test_the_data_rows_are_not_eaten(self):
        t = S._finish([r[:] for r in self._grid()], 1, "ST1", "", "x", "xlsx")
        assert t["n_rows"] == 2, "both measurement rows must survive"

    def test_a_real_one_row_header_is_left_alone(self):
        """No caption: row 0 is already the header and must not be skipped."""
        grid = [["ICD-10 code", "Diagnosis", "Cases (n)"],
                ["I10", "Primary hypertension", "1306"]]
        t = S._finish([r[:] for r in grid], 1, "ST1", "", "x", "xlsx")
        assert t["headers"][0] == "ICD-10 code" and t["n_rows"] == 1

    def test_it_fails_closed_when_the_next_row_is_measurements(self):
        """A lone label above numbers is NOT a caption -- promoting it would
        delete a row of data."""
        grid = [["Total", "", ""],
                ["12.3", "4.5", "6.7"],
                ["13.1", "4.9", "7.0"]]
        t = S._finish([r[:] for r in grid], 1, "ST1", "", "x", "xlsx")
        assert t["n_rows"] == 2, "a measurement row must never be eaten"
