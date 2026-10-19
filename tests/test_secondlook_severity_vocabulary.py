"""The second look must be able to see an accusation.

`secondlook` builds the worklist that tells the adjudicator which of OUR OWN
accusations rest on weak evidence. It gates on whether a finding accuses the
paper at all -- and it made that test against the v1 STRING severity
vocabulary, while the parallel pipeline's v2 rows carry the NUMERIC ladder.

    ACCUSATORY     ('suspicious', 'highly_suspicious', 'impossible')
    v2 severities  {2: 9, 4: 1, 1: 3, 3: 2, None: 19}
    overlap        set()

So the worklist counted zero on every parallel run, and the live adjudicator
docket of 2026-08-29 was handed, verbatim:

    "No finding accuses the paper, so there is nothing to re-check."

beside a tally of 34 findings, 21 of them outcome `problem`.

WHY THIS IS WORSE THAN A MISSING CAPABILITY. The module was present, imported,
and called. Every existence check passed. What froze was a VOCABULARY on one
side of a seam while the other side moved -- the same shape as `_N_IN_LABEL` in
four copies, `ACCUSATORY` in eleven with zero imports, the v1/v2 schema pair,
and `col` dying between the walker and the typer. An artifact-parity test would
have scored this module green.

THE FIX IS TO REUSE THE LADDER'S OWN CONSTANT, not to write a second mapping.
`severity9.ACCUSATORY_MIN` already states the rule in its comment: at or above
it a `problem` finding "is accusation-grade ... Levels 1-2 are record-keeping,
not accusations." A translation table here would be the twelfth copy.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from metascience_agent import secondlook as S
from metascience_agent.severity9 import ACCUSATORY_MIN

REPO = pathlib.Path(__file__).resolve().parent.parent
RUN = (REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1002--ajcp.70049"
       / "forensic_review_gatetest2_2026-08-29" / "findings.v2.json")


class TestBothVocabularies:
    def test_the_v1_strings_still_accuse(self):
        for s in S.ACCUSATORY:
            assert S.is_accusatory({"severity": s})
        for s in ("consistent", "indeterminate", ""):
            assert not S.is_accusatory({"severity": s})

    def test_the_v2_ladder_accuses_at_and_above_the_shared_constant(self):
        for lvl in range(ACCUSATORY_MIN, 9):
            assert S.is_accusatory({"severity": lvl, "outcome": "problem"}), lvl
        for lvl in range(0, ACCUSATORY_MIN):
            assert not S.is_accusatory({"severity": lvl, "outcome": "problem"}), lvl

    def test_a_level_alone_is_not_an_accusation(self):
        """A level is a claim about a finding that concluded something. A `pass`
        at level 4 accuses nobody, and counting it would send the adjudicator
        to re-check a clean result."""
        for outcome in ("pass", "undecided", "", None):
            assert not S.is_accusatory({"severity": 4, "outcome": outcome})

    def test_it_reads_the_ladder_rather_than_copying_it(self):
        """If someone hard-codes a threshold here, the two drift again -- which
        is exactly how this defect happened. Moving the ladder's own constant
        must move this behaviour with it."""
        import inspect
        src = inspect.getsource(S.is_accusatory)
        assert "ACCUSATORY_MIN" in src
        assert "severity9" in src


class TestTheLiveRun:
    @pytest.fixture(scope="class")
    def rows(self):
        if not RUN.is_file():
            pytest.skip("the reference run is not present in this checkout")
        return json.loads(RUN.read_text(encoding="utf-8"))["findings"]

    def test_the_old_test_saw_nothing(self, rows):
        """The defect, pinned as a fact about the data. If this stops being true
        the fixture changed and every number in this file is stale."""
        seen = {str(r.get("severity")) for r in rows}
        assert not (seen & set(S.ACCUSATORY)), seen

    def test_the_worklist_now_sees_the_accusations(self, rows):
        assert sum(1 for r in rows if S.is_accusatory(r)) == 3
        out = S.worklist(rows)
        assert out["n_accusatory"] == 3
        assert "nothing to re-check" not in (out.get("note") or "")

    def test_it_did_not_buy_coverage_by_calling_everything_an_accusation(self, rows):
        """The off-switch. 21 of these rows are outcome `problem`; if all 21
        counted, the worklist would send the adjudicator to re-check
        record-keeping entries, and the guard would be noise instead of a
        signal."""
        n = sum(1 for r in rows if S.is_accusatory(r))
        assert 0 < n < sum(1 for r in rows if r.get("outcome") == "problem")


class TestItReadsTheShapeTheCallSiteActuallyProduces:
    """The 2026-08-29 fix corrected the frozen v1 STRING vocabulary and kept the
    FIELD NAME, so the same false sentence survived the repair of its own
    symptom.

    `secondlook.worklist` is called at parallel.py:951. `adjudicate.apply`
    writes `severity` at adjudicate.py:274, called at parallel.py:1062 -- ONE
    HUNDRED AND ELEVEN LINES LATER. That ordering is deliberate: the docket
    exists to tell the ADJUDICATOR what to re-check, so it must be built before
    adjudication. Producer rows therefore carry `provisional_severity` and no
    `severity` at all, and reading only `severity` returned None for every row
    on every parallel run.

    THE EXISTING REGRESSION TEST PASSED THROUGHOUT, because it loads
    `findings.v2.json` -- the FINAL artifact, after `apply` has written
    `severity`. A fixture built on a shape the call site never produces cannot
    fail. That is why this class builds its rows the way `_rows_from_producer`
    does instead of loading an artifact.
    """

    PRODUCER_ROW = {
        "finding_id": "f_1", "producer": "tool_expert", "technique": "grim_check",
        "outcome": "problem", "provisional_severity": 5,
        "computed_by": "model_reading", "quote": "", "impossible": True,
    }

    def test_a_producer_row_is_recognised_as_an_accusation(self):
        from metascience_agent import secondlook
        assert secondlook.worklist([self.PRODUCER_ROW])["n_accusatory"] == 1

    def test_the_docket_does_not_say_nothing_accuses(self):
        from metascience_agent import secondlook
        note = secondlook.worklist([self.PRODUCER_ROW])["note"]
        assert "No finding accuses the paper" not in note

    def test_the_markers_actually_fire_on_a_producer_row(self):
        """The point of the docket is the markers, not the count."""
        from metascience_agent import secondlook
        out = secondlook.worklist([self.PRODUCER_ROW])
        assert out["n_flagged"] == 1
        assert "quote_not_located" in out["by_marker"]

    def test_a_row_the_adjudicator_discarded_is_not_resurrected(self):
        """ABSENT and None are different facts. No `severity` key means not yet
        adjudicated; `severity: None` means adjudicated and DISCARDED, and its
        provisional level is the claim just rejected."""
        from metascience_agent import secondlook
        discarded = dict(self.PRODUCER_ROW, severity=None)
        assert secondlook.worklist([discarded])["n_accusatory"] == 0

    def test_an_adjudicated_row_still_uses_its_final_severity(self):
        from metascience_agent import secondlook
        kept = dict(self.PRODUCER_ROW, severity=5)
        assert secondlook.worklist([kept])["n_accusatory"] == 1
        lowered = dict(self.PRODUCER_ROW, severity=1)
        assert secondlook.worklist([lowered])["n_accusatory"] == 0

    def test_a_pass_accuses_nobody_at_any_level(self):
        from metascience_agent import secondlook
        row = dict(self.PRODUCER_ROW, outcome="pass")
        assert secondlook.worklist([row])["n_accusatory"] == 0

    def test_the_producer_schema_really_has_no_severity_property(self):
        """The fact that makes all of the above load-bearing. If this ever
        changes, the fallback above is dead code and should go."""
        from metascience_agent.core import prompts
        schema = prompts.producer_findings_schema("tool_expert")
        props = schema["properties"]["findings"]["items"]["properties"]
        assert "severity" not in props
        assert "provisional_severity" in props


class TestQuoteNotLocatedIsTheComplementOfLocated:
    """`quotes.classify` emits FIVE verdicts -- verbatim, elided, stitched,
    unverified, absent -- and the marker listed three of the not-located ones,
    missing `stitched` and `absent`.

    MEASURED over this repo's v2 archive: of the 11 unlocated quotes, SEVEN are
    `stitched`. On the live ajcp run 12 of 34 findings carry `absent`,
    including 2 of the 3 accusatory rows -- and the docket's note therefore
    said all three "quote a passage located in the paper".
    """

    ROW = {"finding_id": "f", "producer": "tool_expert", "technique": "grim_check",
           "outcome": "problem", "provisional_severity": 5,
           "computed_by": "registry_tool", "quote": "x"}

    def _flagged(self, verdict):
        from metascience_agent import secondlook
        out = secondlook.worklist([dict(self.ROW, quote_verified=verdict)])
        return "quote_not_located" in (out["by_marker"] or {})

    @pytest.mark.parametrize("verdict", ["verbatim", "elided"])
    def test_a_located_quote_is_not_flagged(self, verdict):
        assert not self._flagged(verdict)

    @pytest.mark.parametrize("verdict", ["absent", "unverified", "", None])
    def test_a_quote_that_was_not_found_is_flagged(self, verdict):
        assert self._flagged(verdict)

    def test_absent_was_the_missing_one(self):
        """On the live ajcp run 12 of 34 findings carry `absent`, including 2
        of the 3 accusatory rows -- so the docket asserted that all three
        "quote a passage located in the paper"."""
        assert self._flagged("absent")

    def test_stitched_is_deliberately_not_flagged(self):
        """`stitched` means "not contiguous, but EVERY NUMBER IN IT IS IN THE
        PAPER". It is 46% of quotes in the module's own corpus, under-claims by
        design, and its hand-adjudicated siblings contained no fabrications.
        The evidence IS in the paper, so flagging it would fire this marker on
        nearly half of all accusations and drown the verdicts that mean
        something is genuinely missing. The RENDERER labels stitched
        separately, which is where that distinction belongs."""
        assert not self._flagged("stitched")


class TestTheCleanNoteClaimsOnlyWhatWasChecked:
    """`assumed_bound` reads `inputs.bound_source`, ABSENT on 165 of the 167
    findings in this repo's v2 archive. The marker is therefore structurally
    silent on 98.8% of rows -- and the clean note nonetheless asserted that
    every accusation "rests on stated bounds", a positive claim inferred from a
    field nobody had filled in.

    The real bounds gate is `prepass._bounds_are_stated`, which REFUSES the
    check rather than annotating it. This marker is coverage recovery, and its
    silence is not evidence.
    """

    CLEAN = {"finding_id": "f", "producer": "tool_expert",
             "technique": "grim_check", "outcome": "problem",
             "provisional_severity": 5, "computed_by": "registry_tool",
             "quote": "x", "quote_verified": "verbatim"}

    def _note(self, *rows):
        from metascience_agent import secondlook
        return secondlook.worklist(list(rows))["note"]

    def test_it_does_not_claim_stated_bounds_when_none_were_recorded(self):
        note = self._note(self.CLEAN)
        assert "rest on stated bounds" not in note
        assert "unverified" in note

    def test_it_says_how_many_are_unverified(self):
        note = self._note(self.CLEAN, dict(self.CLEAN, finding_id="g"))
        assert "2 of them state no bound provenance" in note

    def test_a_stated_bound_still_earns_the_claim(self):
        note = self._note(dict(self.CLEAN, inputs={"bound_source": "stated"}))
        assert "rest on stated bounds" in note

    def test_an_assumed_bound_is_flagged_rather_than_noted(self):
        from metascience_agent import secondlook
        out = secondlook.worklist(
            [dict(self.CLEAN, inputs={"bound_source": "assumed"})])
        assert "assumed_bound" in out["by_marker"]

    def test_no_accusation_still_says_so_plainly(self):
        note = self._note(dict(self.CLEAN, outcome="pass"))
        assert note.startswith("No finding accuses the paper")
