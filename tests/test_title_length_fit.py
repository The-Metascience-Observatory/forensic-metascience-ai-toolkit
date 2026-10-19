"""A long finding title is accepted from the producer and cut by the pipeline.

MEASURED 2026-10-18 over the 116 archived stages of the statcheck p-value
benchmark (Claude Sonnet + grok 4.6, full and tools_only pipelines): 40 stages
had a StructuredOutput submission rejected, and 44 of the 52 rejections were
titles over 90 characters and nothing else -- 119 titles, median 96, longest
126. Seven at once on 10.1001--jamanetworkopen.2020.33457. Each rejection costs
a paid resubmission turn, and that loop is where the CLI's stream was cut in
the 1.85.1 lost-findings bug.

The stored contract is unchanged (title <= 90 in findings.v2.schema.json); the
producer-facing schemas accept up to PRODUCER_TITLE_MAX, and the harness cuts
the row back at a word boundary, keeping the full title in `notes`.
"""
from __future__ import annotations

import copy
import json

import jsonschema
import pytest

from metascience_agent import adjudicate, parallel
from metascience_agent import findings_v2 as fv2
from metascience_agent.core import prompts

#: A real rejected title shape from the benchmark (94 characters).
LONG = ("Table 2: reported t(58) = 2.10, p = .002 recomputes to p = 0.0401, "
        "a decision-relevant mismatch")


class TestFitTitle:
    def test_a_title_that_fits_is_untouched(self):
        title = "Table 2: BDI-II mean 23.47 is impossible for n=28"
        assert fv2.fit_title(title) == (title, None)

    def test_exactly_the_limit_is_untouched(self):
        title = "x" * fv2.TITLE_MAX
        assert fv2.fit_title(title) == (title, None)

    def test_a_long_title_is_cut_at_a_word(self):
        assert len(LONG) > fv2.TITLE_MAX
        short, full = fv2.fit_title(LONG)
        assert full == LONG
        assert len(short) <= fv2.TITLE_MAX
        assert short.endswith("…")
        assert LONG.startswith(short[:-1]), "the cut is a prefix, nothing rewritten"
        assert LONG[len(short) - 1] == " ", "cut at a word boundary"

    def test_a_number_is_never_split(self):
        """A hard cut turns p = 0.0401 into p = 0.04, a value nobody printed."""
        title = ("Results paragraph 3: the reported interaction F(2, 114) = 3.21 "
                 "gives p = 0.0438172 not p < .01")
        short, _ = fv2.fit_title(title)
        tokens = title.split()
        kept = short[:-1].split()
        assert kept == tokens[:len(kept)], short

    def test_a_single_unbroken_token_still_fits(self):
        short, full = fv2.fit_title("y" * 130)
        assert len(short) == fv2.TITLE_MAX and full == "y" * 130

    def test_whitespace_only_overrun_is_collapsed_not_cut(self):
        title = "Table 3:" + " " * 100 + "SD 0.4 impossible"
        short, full = fv2.fit_title(title)
        assert full is None and short == "Table 3: SD 0.4 impossible"


class TestFitRowTitle:
    def test_the_full_title_is_kept_in_notes(self):
        row = {"title": LONG, "notes": "The authors may have used a one-sided test."}
        assert fv2.fit_row_title(row, "tool_expert") is True
        assert len(row["title"]) <= fv2.TITLE_MAX
        assert row["notes"].startswith("The authors may have used a one-sided test.")
        assert LONG in row["notes"], "the producer's words are kept, never dropped"
        assert "tool_expert" in row["notes"]

    def test_a_fitting_row_is_not_touched(self):
        row = {"title": "Table 1: n sums to 61, not 60"}
        before = copy.deepcopy(row)
        assert fv2.fit_row_title(row, "tool_expert") is False
        assert row == before


class TestTheSchemasAgree:
    def test_the_stored_bound_is_TITLE_MAX(self):
        full = prompts.findings_schema_v2()
        title = full["properties"]["findings"]["items"]["properties"]["title"]
        assert title["maxLength"] == fv2.TITLE_MAX

    @pytest.mark.parametrize("producer", ["tool_expert", "science_error"])
    def test_a_producer_may_submit_up_to_PRODUCER_TITLE_MAX(self, producer):
        sub = prompts.producer_findings_schema(producer)
        title = sub["properties"]["findings"]["items"]["properties"]["title"]
        assert title["maxLength"] == fv2.PRODUCER_TITLE_MAX
        assert str(fv2.TITLE_MAX) in title["description"], (
            "the model is still told the target")
        assert max(126, len(LONG)) <= fv2.PRODUCER_TITLE_MAX, (
            "the longest measured rejection would now pass")

    def test_the_full_schema_was_not_loosened_by_the_subset(self):
        prompts.producer_findings_schema("tool_expert")
        full = prompts.findings_schema_v2()
        title = full["properties"]["findings"]["items"]["properties"]["title"]
        assert title["maxLength"] == fv2.TITLE_MAX, "deepcopy, not aliasing"

    def test_the_adjudicator_rewrite_bound(self):
        verdict = prompts.adjudication_schema()["properties"]["verdicts"]["items"]
        assert verdict["properties"]["title"]["maxLength"] == fv2.PRODUCER_TITLE_MAX


def _producer_row(title: str) -> dict:
    return {"slug": "t2-p", "technique": "recalc_stat_to_p", "title": title,
            "description": "The printed p does not match the recomputed p for "
                           "the reported t and df.",
            "location": "Table 2", "outcome": "problem",
            "provisional_severity": 3,
            "anchors": [{"kind": "quote", "quote": "t(58) = 2.10, p = .002"}]}


def test_a_producer_row_is_stored_within_the_bound():
    """End to end through the stamping path every producer row takes."""
    rows = parallel._rows_from_producer(
        {"findings": [_producer_row(LONG)]}, "tool_expert", [], "paper")
    assert len(rows) == 1
    assert len(rows[0]["title"]) <= fv2.TITLE_MAX
    assert LONG in rows[0]["notes"]
    item = copy.deepcopy(prompts.findings_schema_v2()["properties"]["findings"]["items"])
    jsonschema.validate(rows[0]["title"], item["properties"]["title"])


def test_a_long_adjudicator_rewrite_is_applied_and_cut():
    """It used to be silently IGNORED above 90 (the bounds check), so the
    adjudicator's correction of a title was lost without a word."""
    f = {"finding_id": "f1", "producer": "tool_expert", "title": "short title here",
         "description": "x" * 30, "outcome": "problem", "provisional_severity": 3,
         "technique": "recalc_stat_to_p"}
    new_title = LONG + " in the primary outcome"
    adj = {"verdicts": [{"finding_id": "f1", "action": "kept", "severity": 3,
                         "rationale": "Recomputed; it stands.",
                         "title": new_title}]}
    rows, _summary = adjudicate.apply([f], adj)
    row = rows[0]
    assert len(row["title"]) <= fv2.TITLE_MAX
    assert new_title in row.get("notes", "")
    assert row["adjudication"]["title_was"] == "short title here"
