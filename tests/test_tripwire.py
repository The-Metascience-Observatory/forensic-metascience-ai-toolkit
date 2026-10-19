"""The tripwire must fire on synthetic breakage and stay silent on health.

The archive replay done 2026-08-18 gave the first half: over every archived run
on disk, the report-stage conditions fired on 0 of 47 measurable runs. That is
the number that decides whether a tripwire is safe to arm on a $12 job -- one
that kills healthy runs gets disabled within a week, and is then worse than
nothing.

BUT 0/47 LEAVES THE OTHER DIRECTION UNMEASURED, and saying so is the point of
this file. A condition that has never fired has an unknown true-positive rate:
the replay proves these do not fire on healthy runs, and cannot prove they fire
on broken ones, because no archived run is broken in these particular ways.
Shipping on the strength of 0/47 alone would be verifying a smoke alarm by
noting that it has never gone off.

So every condition here is exercised BOTH ways against a directory built to be
broken in exactly the way that condition names.
"""
import json

import pytest

from metascience_agent import tripwire
from metascience_agent.tripwire import (
    Trip, TripwireError, check_preflight, check_report, enforce, summarise,
)


def _trip(cid, paper_dir):
    got = [t for t in check_preflight(paper_dir) if t.id == cid]
    assert len(got) == 1, f"expected one {cid} trip, got {len(got)}"
    return got[0]


class TestXmlPresentButNoText:
    """Positive evidence: the publisher's own marked-up full text is on disk."""

    def test_it_fires_when_the_xml_yields_nothing(self, tmp_path):
        d = tmp_path / "paper"; d.mkdir()
        # Well-formed XML with no extractable body -- the shape of a namespace
        # or schema mismatch, which is how this loss actually happens.
        (d / "article.xml").write_text("<article></article>", encoding="utf-8")
        t = _trip("xml_present_but_no_text", d)
        assert t.fired is True
        assert "article.xml" in t.expected
        assert t.message

    def test_it_is_silent_when_the_text_arrives(self, tmp_path):
        d = tmp_path / "paper"; d.mkdir()
        (d / "article.xml").write_text("<article></article>", encoding="utf-8")
        (d / "body.md").write_text("The mean was 4.2 (SD 0.9).", encoding="utf-8")
        assert _trip("xml_present_but_no_text", d).fired is False

    def test_no_xml_is_not_a_trip(self, tmp_path):
        """Absence of the thing is not evidence of loss. The whole design rule."""
        d = tmp_path / "paper"; d.mkdir()
        t = _trip("xml_present_but_no_text", d)
        assert t.fired is False and "no publisher XML" in t.expected


class TestStage2CarriedNothing:
    def test_it_fires_when_the_report_carries_none(self):
        t = check_report([{"id": "1"}, {"id": "2"}], {"findings": []})[0]
        assert t.fired is True
        assert "2 sweep finding" in t.expected

    def test_it_is_silent_when_the_report_carries_some(self):
        t = check_report([{"id": "1"}], {"findings": [{"title": "x"}]})[0]
        assert t.fired is False

    def test_no_sweep_findings_is_not_a_trip(self):
        """A clean paper produces no findings and must not be killed for it."""
        assert check_report([], {"findings": []})[0].fired is False

    def test_a_missing_report_is_NOT_MEASURED_rather_than_fired(self):
        """The exact mistake the first replay made: two archived runs had a
        working stage 2 and no report.json because they predate the schema.
        Scoring that as a trip invented a 4% false-positive rate."""
        t = check_report([{"id": "1"}], None)[0]
        assert t.fired is False
        assert t.not_measured is True


class TestNotMeasuredIsNeverAPass:
    def test_the_summary_counts_it_separately(self):
        trips = [Trip("a", False), Trip("b", False, not_measured=True)]
        s = summarise(trips)
        assert s["tripped"] is False
        assert s["n_not_measured"] == 1
        assert "not measurable" in s["note"]

    def test_it_is_visible_in_the_note_rather_than_silent(self):
        s = summarise([Trip("b", False, not_measured=True)])
        assert "1 not measurable" in s["note"]


class TestEveryTripCarriesItsPositiveEvidence:
    """A trip with no `expected` is a trip firing on an absence, which this
    module forbids -- that is the line between a tripwire and a coverage gate."""

    def test_a_fired_trip_names_what_should_have_arrived(self, tmp_path):
        d = tmp_path / "paper"; d.mkdir()
        (d / "article.xml").write_text("<article></article>", encoding="utf-8")
        for t in check_preflight(d) + check_report([{"id": "1"}], {"findings": []}):
            if t.fired:
                assert t.expected, f"{t.id} fired with no stated evidence"
                assert t.got, f"{t.id} fired without saying what arrived"


class TestTheModes:
    FIRED = [Trip("x", True, expected="a supplement", got="zero cells")]

    def test_off_records_and_does_not_raise(self):
        s = enforce(self.FIRED, mode="off")
        assert s["tripped"] is True and s["n_fired"] == 1

    def test_warn_records_and_does_not_raise(self):
        assert enforce(self.FIRED, mode="warn")["tripped"] is True

    def test_kill_raises_with_the_evidence_in_the_message(self):
        with pytest.raises(TripwireError) as e:
            enforce(self.FIRED, mode="kill")
        msg = str(e.value)
        assert "a supplement" in msg and "zero cells" in msg
        assert "handoff-audit" in msg, "a dead run must say how to diagnose it"

    def test_kill_does_not_raise_when_nothing_fired(self):
        assert enforce([Trip("x", False)], mode="kill")["tripped"] is False

    def test_the_summary_survives_a_kill_decision(self):
        """A tripped run must be diagnosable, so `fired` is populated in every
        mode rather than only in the one that lets the run continue."""
        assert enforce(self.FIRED, mode="off")["fired"][0]["id"] == "x"


class TestTheArchiveRemainsQuiet:
    """The false-positive half, kept executable rather than only recorded."""

    #: Two depths, resolved from the REPO ROOT and not the working directory:
    #: dated run dirs sit at `<corpus>/<paper>/forensic_review*`, and since the
    #: corpus consolidation every fixture paper lives under `tests/fixtures/papers/`. The
    #: single fixed-depth `Path(".").glob("*/*/...")` this replaced matched 0
    #: of 22 archived runs after the move and the replay below skipped green
    #: -- a guard that had stopped guarding (LESSONS.md, entry 4).
    _REVIEW_GLOBS = ("*/*/forensic_review*/findings.json",
                     "tests/fixtures/papers/*/*/forensic_review*/findings.json")

    @classmethod
    def _archived_runs(cls):
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        found = []
        for pattern in cls._REVIEW_GLOBS:
            found.extend(p for p in root.glob(pattern)
                         if "scratchpad" not in p.parts)
        return sorted(set(found))

    def test_the_replay_can_see_the_archive(self):
        """The known positive for the test below: in a checkout that carries
        `tests/fixtures/papers/`, the globs must find runs. A replay that finds nothing
        and skips is indistinguishable from one that found nothing wrong."""
        from pathlib import Path
        if not (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "papers").is_dir():
            pytest.skip("no tests/fixtures/papers/ corpus in this checkout")
        assert self._archived_runs(), (
            "tests/fixtures/papers/ is present but no forensic_review*/findings.json was "
            "found -- the archive globs no longer match the corpus layout")

    def test_no_archived_run_would_have_been_killed(self):
        runs = self._archived_runs()
        measurable = killed = 0
        for fj in runs:
            rep = fj.parent / "report.json"
            if not rep.is_file():
                continue          # pre-schema: not measurable, not a pass
            try:
                f = json.loads(fj.read_text(encoding="utf-8"))
                r = json.loads(rep.read_text(encoding="utf-8"))
            except Exception:
                continue
            sweep = f if isinstance(f, list) else (f.get("findings") or [])
            measurable += 1
            if check_report(sweep, r)[0].fired:
                killed += 1
        if not measurable:
            pytest.skip("no archived runs present")
        assert killed == 0, (
            f"{killed} of {measurable} archived runs would have been killed; "
            "a tripwire that fires on healthy runs gets disabled and is then "
            "worse than nothing")


class TestAStageThatReportsItsOwnError:
    """Added after a REAL failure, 2026-08-18, hours after this module shipped.

    A Sonnet repeat on the Stapel paper lost its API connection mid-response:
    sweep finished cleanly with 14 findings, editorial recorded
    `is_error: True, error_subtype: "api_error"`, no report.json was written,
    and the run billed $5.18. `stage2_carried_nothing` returned NOT MEASURED on
    it -- correct for the case it was designed against, and useless here.

    The archive replay for THIS condition fires on 1 of 49 runs, `apple_cider`,
    where both stages hit `error_max_budget_usd`. That is a true positive. It
    also corrects the record: that run had earlier been written off as merely
    predating the report schema, when it had in fact been killed by its budget.
    """

    def test_it_fires_when_a_stage_reports_an_error(self):
        from metascience_agent.tripwire import check_run
        t = check_run({"stages": {
            "sweep": {"is_error": False},
            "editorial": {"is_error": True, "error_subtype": "api_error"},
        }})[0]
        assert t.fired is True
        assert "editorial" in t.got and "api_error" in t.got

    def test_it_is_silent_when_every_stage_completed(self):
        from metascience_agent.tripwire import check_run
        t = check_run({"stages": {"sweep": {"is_error": False},
                                  "editorial": {"is_error": False}}})[0]
        assert t.fired is False

    def test_a_budget_kill_fires_too(self):
        """The archived `apple_cider` case: not an API fault, still a loss."""
        from metascience_agent.tripwire import check_run
        t = check_run({"stages": {
            "sweep": {"is_error": True, "error_subtype": "error_max_budget_usd"},
            "editorial": {"is_error": True, "error_subtype": "error_max_budget_usd"}}})[0]
        assert t.fired is True
        assert "2 reported an error" in t.got

    def test_no_stages_is_not_measured_rather_than_clean(self):
        from metascience_agent.tripwire import check_run
        t = check_run({})[0]
        assert t.fired is False and t.not_measured is True


class TestASecondaryModelWritingContent:
    """Greg, 2026-08-18: "the Haiku model that is dispatched to perform a task
    might do a poor job and supply incorrect information to the pipeline."

    Investigated and not happening: haiku is billed on every run but appears in
    0 of 156 assistant messages, only in the final billing rollup, and its
    output never exceeded 32 tokens across 40 archived transcripts. See
    docs/HAIKU_IN_THE_LOOP.md.

    This check exists for the case the evidence could NOT rule out. What the CLI
    sends a secondary model happens inside the CLI. If one were used to
    SUMMARISE a long conversation, that summary would re-enter the main model's
    context, and a poor one would degrade the analysis. Every archived run fits
    in context; a longer paper is where it would show.

    Output tokens are the signature. Housekeeping writes a sentence.
    """

    def _meta(self, out_tokens, primary="claude-opus-5"):
        return {"stages": {"sweep": {
            "is_error": False, "primary_billed_model": primary,
            "model_usage": {primary: {"outputTokens": 120000},
                            "claude-haiku-4-5": {"outputTokens": out_tokens}}}}}

    def _trip(self, meta):
        from metascience_agent.tripwire import check_run
        return [t for t in check_run(meta)
                if t.id == "secondary_model_wrote_content"][0]

    def test_the_real_observed_case_does_not_fire(self):
        """26 output tokens is what actually happens. A check that fired here
        would be disabled within a week."""
        assert self._trip(self._meta(26)).fired is False

    def test_a_conversation_summary_fires(self):
        t = self._trip(self._meta(3000))
        assert t.fired is True
        assert "3000 output tokens" in t.got

    def test_the_primary_model_is_never_an_offender(self):
        """The commissioned model writing a lot is the point of the run."""
        assert self._trip(self._meta(26)).fired is False

    def test_a_run_predating_the_field_is_not_measured(self):
        """Older run_meta carries costUSD only. Absence of the field is not
        evidence that no secondary model wrote anything."""
        t = self._trip({"stages": {"s": {"model_usage": {"m": {"costUSD": 1.0}}}}})
        assert t.fired is False and t.not_measured is True

    def test_the_message_says_what_to_do(self):
        t = self._trip(self._meta(3000))
        assert "messages.stage" in t.message
