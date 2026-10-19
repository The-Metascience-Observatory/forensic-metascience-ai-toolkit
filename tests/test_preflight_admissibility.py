"""The pre-flight must refuse what the runner refuses.

MEASURED 2026-08-13 on Kross 2013 (10.1371--journal.pone.0069841):
`metascience handoff-audit` printed "All 5 hand-offs carry data and have a
consumer that reads them" and `metascience inputs` reported "1 article, 0
supplementary" without complaint. `metascience analyze` then exited 2 -- the
article's own Supporting Information section lists Text S1-S6 and none was
present.

The pre-flight exists so an operator does not pay for a run that cannot succeed.
It was checking the DATA hand-offs and never the ADMISSIBILITY gates, so it said
GO on a paper the runner refuses. A pre-flight that passes what the runner
rejects is worse than no pre-flight, because it is trusted.

THREE-VALUED, DELIBERATELY. `supplements.audit` returns `missing` as True /
False / None, where None means the paper could not be read and the question was
never answered. Collapsing None into a pass would reinstate absence-as-evidence
one level up -- the defect this whole module exists to catch.
"""
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.handoff import audit

LINK = "cited supplements are present"


def _row(paper_dir):
    rows = [r for r in audit(paper_dir)["rows"] if r["link"] == LINK]
    assert len(rows) == 1, f"expected exactly one {LINK!r} row, got {len(rows)}"
    return rows[0]


@pytest.fixture
def paper(tmp_path):
    d = tmp_path / "paper"
    d.mkdir()
    return d


class TestACitedButAbsentSupplementIsRefused:
    def test_the_row_fails(self, paper):
        (paper / "body.md").write_text(
            "Results are given in Table S1 and Text S2 of the Supporting "
            "Information.", encoding="utf-8")
        row = _row(paper)
        assert row["ok"] is False

    def test_the_note_says_the_run_will_warn(self, paper):
        """An operator reads this INSTEAD of paying, so it has to say what will
        happen: since 2026-10-18 the run proceeds with a recorded limitation."""
        (paper / "body.md").write_text(
            "See Table S1 in the Supporting Information.", encoding="utf-8")
        note = " ".join(str(_row(paper)["note"]).split())
        assert "WILL WARN" in note
        assert "--supplement" in note

    def test_the_whole_audit_reports_not_ready(self, paper):
        (paper / "body.md").write_text("See Table S1.", encoding="utf-8")
        assert audit(paper)["ready"] is False


class TestAPaperWithNoSupplementaryCitationPasses:
    def test_ok_when_nothing_is_cited(self, paper):
        (paper / "body.md").write_text(
            "Everything is reported in Table 1 of this article.",
            encoding="utf-8")
        row = _row(paper)
        assert row["ok"] is True
        assert "cites no supplementary material" in str(row["note"])


class TestUnreadableIsNotAPass:
    def test_no_text_gives_none_rather_than_true(self, paper):
        """An empty directory answers nothing. `None` is the honest verdict and
        it must not be rendered as a green row."""
        row = _row(paper)
        assert row["ok"] is None
        assert "NOT MEASURED" in str(row["note"])

    def test_none_is_distinguishable_from_false(self, paper):
        """`ok is None` and `ok is False` must not compare equal to a renderer
        that branches on truthiness -- both are falsy, and only one is a defect
        in the paper directory."""
        unknown = _row(paper)
        (paper / "body.md").write_text("See Table S1.", encoding="utf-8")
        refused = _row(paper)
        assert unknown["ok"] is None and refused["ok"] is False
        assert unknown["note"] != refused["note"]
