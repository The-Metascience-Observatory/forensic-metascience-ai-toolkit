"""A provisional clamp was applied and nothing recorded that it happened.

`clamp_provisionals` OVERWRITES `provisional_severity` with the evidence-channel
cap and records the before/after only in its returned summary --
and `parallel.py:401` calls it and DISCARDS that return value. So the row lost
its own history: nothing anywhere said a ceiling had been applied, or what the
model originally claimed.

`adjudicate._clamp` already works the other way, writing `severity_from` onto
the finding, and the spec's rule is that "a clamp is visible, never silent".
This is that rule one stage earlier. Marking the ROW rather than plumbing a
summary through two call sites means a caller cannot drop it again.
"""

from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit import findings_v2 as fv2


def _row(slug, prov, computed_by="agent_code", technique="internal_contradiction"):
    # `agent_code` so the row clamps through a CHANNEL cap (AGENT_CODE_CAP=4);
    # v1.14.0 removed the evidence-class ceiling this fixture once relied on.
    return {"slug": slug, "producer": "tool_expert", "outcome": "problem",
            "provisional_severity": prov, "technique": technique,
            "computed_by": computed_by, "title": "t" * 10,
            "description": "d" * 30, "location": "Table 2"}


class TestAClampMarksTheRow:
    def test_a_clamped_row_records_what_it_claimed(self):
        rows = [_row("a", 7)]
        fv2.clamp_provisionals(rows)
        assert rows[0]["provisional_severity"] < 7
        assert rows[0]["provisional_severity_from"] == 7

    def test_an_unclamped_row_is_not_marked(self):
        """Absence must mean "no ceiling applied", so it cannot be written
        unconditionally."""
        rows = [_row("b", 2, computed_by="registry_tool", technique="grim_check")]
        fv2.clamp_provisionals(rows)
        assert "provisional_severity_from" not in rows[0]

    def test_the_mark_survives_the_caller_discarding_the_summary(self):
        """`parallel.py:401` ignores the return value; that must not lose the
        record."""
        rows = [_row("a", 7)]
        fv2.clamp_provisionals(rows)          # return value deliberately dropped
        assert rows[0].get("provisional_severity_from") == 7

    def test_the_summary_still_agrees_with_the_rows(self):
        rows = [_row("a", 7), _row("b", 2, "registry_tool", "grim_check")]
        summary = fv2.clamp_provisionals(rows)
        marked = [r for r in rows if "provisional_severity_from" in r]
        assert summary["n_clamped"] == len(marked) == 1


class TestTheModelCannotWriteItsOwnClampHistory:
    @pytest.mark.parametrize("producer", ["tool_expert", "science_error"])
    def test_the_producer_schema_excludes_it(self, producer):
        """A producer that could write this could assert it had been capped
        from a level it never claimed, or that it had not been capped at all --
        the same reason `severity` is pipeline-set."""
        from forensic_metascience_ai_toolkit.core import prompts
        props = prompts.producer_findings_schema(producer)[
            "properties"]["findings"]["items"]["properties"]
        assert "provisional_severity_from" not in props

    def test_the_v2_schema_declares_it(self):
        """`additionalProperties` is False on finding rows, so a field the
        pipeline writes must be declared or the document fails validation."""
        import json
        import pathlib
        schema = json.loads(
            (pathlib.Path(__file__).resolve().parents[1] / "src"
             / "forensic_metascience_ai_toolkit" / "schema"
             / "findings.v2.schema.json").read_text(encoding="utf-8"))
        props = schema["properties"]["findings"]["items"]["properties"]
        assert "provisional_severity_from" in props
        assert "PIPELINE-SET" in props["provisional_severity_from"]["description"]
