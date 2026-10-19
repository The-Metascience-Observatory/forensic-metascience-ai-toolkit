"""The viewer's note about a missing census must be true of the run it is on.

HISTORY, because the fact under this file has now moved twice.

The note originally read: "The census ... was added after this review ran ...
Re-running the paper at current HEAD produces the audited count." For a v2 run
that was FALSE -- `census` was called only from `agent.py` -- so a reader was
told the gap was the run's age and fixable when it was neither. A second
branch was added saying "re-running would not produce one", correct for a v2
run at that time.

v1.23.0 INVERTED IT AGAIN: the census was ported to the parallel path and
attaches to the v2 document. So "re-running would not produce one" is now
false for any current run, and the branch may fire ONLY for a v2 run that
genuinely carries no census -- an archived one from before the port. The flag
is computed from both the schema version AND the census's presence for exactly
that reason.

2026-10-19: the `census_is_a_legacy_capability` flag and its "re-running
would not produce one" branch were deleted with the serial-pipeline readers,
leaving only the "added after this review ran" note, which is true of every
run that lacks a census (all predate v1.23.0).

The through-line is the same each time: the page must not explain an absence
with a reason that has stopped being true.
"""

from __future__ import annotations

import inspect
import pathlib

import pytest

from forensic_metascience_ai_toolkit import bundle


class TestTheCapabilityClaim:
    def test_census_is_called_on_the_parallel_path(self):
        """Inverted in v1.23.0. The census used to be legacy-only; it is the
        independent denominator and now runs on the live path."""
        src = pathlib.Path(bundle.__file__).parent / "parallel.py"
        text = src.read_text(encoding="utf-8")
        assert "_checkable_coverage" in text, (
            "the parallel writer no longer computes the census; if that is "
            "deliberate, the viewer's 'legacy capability' note must come back")
        assert "coverage_summary" in text

    def test_census_is_called_on_the_legacy_path(self):
        src = pathlib.Path(bundle.__file__).parent / "agent.py"
        assert "_census." in src.read_text(encoding="utf-8")


class TestTheNoteDistinguishesTheTwoCases:
    @pytest.fixture(scope="class")
    def src(self):
        return inspect.getsource(bundle)

    def test_a_v1_run_keeps_the_original_wording(self, src):
        """An old v1 run really did predate the census commit, and for it the
        original sentence is true."""
        import re
        flat = re.sub(r"\s+", " ", src)
        assert ("Re-running the paper at current HEAD produces the audited "
                "count") in flat

