"""The severity gates were absolute, not evidential, and nothing had noticed.

`Variable.bounds_are_stated` (#87) and `Variable.discreteness_source` both
refuse to license `impossible` without a pipeline-set `provenance_verdict`.
That is deliberate: it stops the model certifying its own quote. But the verdict
was written by `agent._annotate_quotes`, which runs AFTER the model's tool
calls.

MEASURED across every archived run: NOT ONE variable has ever reached
`check_table` carrying a verdict. So on the table path -- which is where
essentially all the volume is -- a granularity or range failure could never
reach `impossible`, whatever the paper actually said. Safe, but not what either
gate was designed to do, and a gate that always says no is indistinguishable
from a broken one.

The fix adjudicates each variable's quote against the paper BEFORE dispatch,
using a paper directory the PIPELINE names on the tool server's environment.
The model cannot write an environment variable, which is the same property
`PIPELINE_ONLY_FIELDS` gives the in-payload fields -- here at the process
boundary.
"""
import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit import dispatch as D
from forensic_metascience_ai_toolkit.agent import PAPER_DIR_ENV, _build_mcp_config

PAPER = pathlib.Path(__file__).resolve().parents[1] / (
    "tests/fixtures/papers/cerebrolysin_run_2026-08-09/10.1007--s11064-023-03861-8")

#: A phrase that really is in that paper, checked by reading it.
IN_THE_PAPER = "Values are Mean"


@pytest.fixture(autouse=True)
def _clear_haystack_cache():
    """The haystack is cached per process; a test that changed the env without
    clearing it would silently read the previous test's paper."""
    D._HAYSTACK = None
    yield
    D._HAYSTACK = None


def _variable(**kw):
    base = {"id": "v1", "name": "Score", "family": "count",
            "discreteness": "discrete", "confidence": "high",
            # THE FORGERY, present in every case below: the model asserting the
            # verdict it is not allowed to assert.
            "provenance_verdict": "verbatim"}
    return {**base, **kw}


class TestTheChannelIsPipelineOnly:
    def test_the_paper_directory_reaches_the_SERVER_not_the_model(self):
        cfg = json.loads(_build_mcp_config("/some/paper/dir"))
        env = cfg["mcpServers"][next(iter(cfg["mcpServers"]))]["env"]
        assert env[PAPER_DIR_ENV] == "/some/paper/dir"

    def test_no_paper_directory_means_no_variable_at_all(self):
        """Absent, not empty. An empty value would read as 'we looked and found
        nothing' to anything downstream that tests truthiness of the key."""
        cfg = json.loads(_build_mcp_config())
        env = cfg["mcpServers"][next(iter(cfg["mcpServers"]))]["env"]
        assert PAPER_DIR_ENV not in env

    def test_pythonpath_is_still_set(self):
        cfg = json.loads(_build_mcp_config("/x"))
        env = cfg["mcpServers"][next(iter(cfg["mcpServers"]))]["env"]
        assert env["PYTHONPATH"]


class TestTheModelCannotCertifyItself:
    """The forged `provenance_verdict` must never survive, with or without a
    paper to check against."""

    def test_the_forgery_is_stripped_when_there_is_no_paper(self, monkeypatch):
        monkeypatch.delenv(PAPER_DIR_ENV, raising=False)
        v = D._as_variable(_variable(provenance_quote="anything at all"))
        assert v.provenance_verdict is None
        assert v.discreteness_source() == "assumed"
        assert v.forensic_kwargs()["discreteness_source"] == "assumed"

    def test_the_forgery_is_replaced_by_OUR_verdict_when_there_is(self, monkeypatch):
        if not PAPER.exists():
            pytest.skip("archived paper not present in this checkout")
        monkeypatch.setenv(PAPER_DIR_ENV, str(PAPER))
        v = D._as_variable(_variable(provenance_quote="nothing like this appears"))
        # Whatever it says, it is not the model's word for it.
        assert v.provenance_verdict != "verbatim"


class TestTheGateIsNowEvidential:
    """The point of the change: a real quote can license `impossible`, and an
    invented one still cannot."""

    def test_a_quote_that_IS_in_the_paper_licenses_the_top_of_the_ladder(
            self, monkeypatch):
        if not PAPER.exists():
            pytest.skip("archived paper not present in this checkout")
        monkeypatch.setenv(PAPER_DIR_ENV, str(PAPER))
        v = D._as_variable(_variable(provenance_quote=IN_THE_PAPER))
        assert v.provenance_verdict == "verbatim"
        assert v.discreteness_source() == "stated"

    def test_an_invented_quote_does_not(self, monkeypatch):
        if not PAPER.exists():
            pytest.skip("archived paper not present in this checkout")
        monkeypatch.setenv(PAPER_DIR_ENV, str(PAPER))
        v = D._as_variable(_variable(
            provenance_quote="participants rated their zorbliness on a 1-7 scale"))
        assert v.provenance_verdict in ("stitched", "unverified", "absent")
        assert v.discreteness_source() == "assumed"

    def test_the_bounds_gate_is_unblocked_by_the_same_change(self, monkeypatch):
        """Both gates demanded the same evidence and both were starved of it.
        Fixing one and not the other would have been arbitrary.

        WHAT THIS TEST PINS is that the DISPATCH path now reaches a verdict at
        all -- before the haystack change, no variable ever arrived at
        `check_table` carrying one, so both gates were absolute rather than
        evidential. It no longer asserts that `Values are Mean` licenses a 1-7
        scale, because since 2026-08-11 it does not and should not: a verified
        sentence has to be verified ABOUT THE BOUNDS, and that one names
        neither. See tests/test_bounds_provenance.py."""
        if not PAPER.exists():
            pytest.skip("archived paper not present in this checkout")
        monkeypatch.setenv(PAPER_DIR_ENV, str(PAPER))
        v = D._as_variable(_variable(
            provenance_quote=IN_THE_PAPER, lower_bound=1, upper_bound=7))
        assert v.provenance_verdict in ("verbatim", "elided"), (
            "the dispatch path must adjudicate the quote; that is the change "
            "this test exists for")
        assert v.bounds_are_stated() is False, (
            "`Values are Mean` says nothing about a 1-7 range")

    def test_a_quote_that_names_the_range_does_license_it(self, monkeypatch):
        """The other half: evidence about the bounds still unlocks them, so the
        gate is evidential rather than simply shut."""
        if not PAPER.exists():
            pytest.skip("archived paper not present in this checkout")
        monkeypatch.setenv(PAPER_DIR_ENV, str(PAPER))
        v = D._as_variable(_variable(
            provenance_quote=IN_THE_PAPER, lower_bound=None, upper_bound=None))
        assert v.bounds_are_stated() is True, (
            "a variable declaring no range has no bounds claim to evidence")


class TestFailureIsSilentAndCAPPED:
    """The direction of failure is the whole safety argument."""

    def test_an_unreadable_paper_leaves_the_variable_ASSUMED(self, monkeypatch, tmp_path):
        """Not `absent`. Stamping a verdict because we could not open the paper
        would convert OUR failure into a statement about the authors' quote --
        the house mistake this codebase keeps having to unlearn."""
        monkeypatch.setenv(PAPER_DIR_ENV, str(tmp_path))
        v = D._as_variable(_variable(provenance_quote="anything"))
        assert v.provenance_verdict is None
        assert v.discreteness_source() == "assumed"

    def test_a_nonexistent_directory_does_not_raise(self, monkeypatch):
        monkeypatch.setenv(PAPER_DIR_ENV, "/no/such/place/at/all")
        v = D._as_variable(_variable(provenance_quote="anything"))
        assert v.discreteness_source() == "assumed"

    def test_no_quote_means_no_verdict_rather_than_a_negative_one(self, monkeypatch):
        """A variable the model did not quote for is not a variable whose quote
        failed. Those are different facts."""
        if not PAPER.exists():
            pytest.skip("archived paper not present in this checkout")
        monkeypatch.setenv(PAPER_DIR_ENV, str(PAPER))
        for quote in (None, "", "   "):
            v = D._as_variable(_variable(provenance_quote=quote))
            assert v.provenance_verdict is None

    def test_the_haystack_is_built_once_per_process(self, monkeypatch):
        """275 KB of paper text, and `check_table` types every cell of every
        table. Rebuilding per variable would be a per-cell file read."""
        if not PAPER.exists():
            pytest.skip("archived paper not present in this checkout")
        monkeypatch.setenv(PAPER_DIR_ENV, str(PAPER))
        first = D._haystack()
        assert first
        monkeypatch.setenv(PAPER_DIR_ENV, "/no/such/place")
        assert D._haystack() is first, "cache was rebuilt after the env changed"
