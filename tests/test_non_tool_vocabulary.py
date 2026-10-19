"""One membership list for "no tool did this", not two that disagree.

`computation.classify` answers a load-bearing question: did a REGISTERED TOOL
produce this finding's numbers, or did the model? It answers `"tool"` for any
technique absent from `computation.NON_TOOL_TECHNIQUES` -- so that mapping's
membership decides who gets credited with the arithmetic.

THE DEFECT. `prompts.NON_TOOL_TECHNIQUES` is the spec ("the six fixed non-tool
technique values, spec section 1.2"); `computation` kept a hand-written four.
They disagreed on FOUR of seven members, and the consequence was a false
positive claim rather than a missing one: `internal_contradiction` and
`factual_claim` -- which the spec names as NON-tool -- were classified `"tool"`,
i.e. arithmetic a registered tool performed and the ledger can prove. Seven
live rows carried `internal_contradiction` on the run of 2026-08-29.

WHY IT SHIPPED IN THE SAME CHANGE AS THE SECONDLOOK FIX. It was inert only
because `secondlook` was itself inert -- its severity vocabulary had frozen
against the v1 strings, so nothing downstream read this answer. Repairing that
gate ARMED this one. A latent wrong answer sitting under a guard that has just
been switched on is not a separate problem; it is the same problem one step
later, and shipping the guard alone would have been a coverage win bought with
a correctness loss.

The fix is derivation, not synchronisation: membership comes from the spec,
this file supplies only the may-carry-a-number flags, and an unflagged spec
member defaults to True -- the safe direction, since that keeps a technique OUT
of the "a tool computed this" answer, which is the claim that has to be earned.
"""
from __future__ import annotations

from forensic_metascience_ai_toolkit.computation import (NON_TOOL_TECHNIQUES, classify,
                                           did_unaided_arithmetic)
from forensic_metascience_ai_toolkit.core.prompts import NON_TOOL_TECHNIQUES as SPEC


class TestTheTwoListsCannotDisagree:
    def test_every_spec_member_is_known_here(self):
        missing = sorted(set(SPEC) - set(NON_TOOL_TECHNIQUES))
        assert not missing, (
            f"the spec names {missing} as non-tool and `classify` would report "
            "them as arithmetic a registered tool performed")

    def test_membership_is_derived_rather_than_copied(self):
        """A second literal list is how this broke. If someone re-hardcodes the
        membership, the derivation disappears and drift becomes possible again."""
        import inspect
        from forensic_metascience_ai_toolkit import computation
        src = inspect.getsource(computation._non_tool_techniques)
        assert "from .core.prompts import NON_TOOL_TECHNIQUES" in src

    def test_the_legacy_label_survives_although_the_v2_spec_dropped_it(self):
        """`manual` is v1-only. Deriving membership from the v2 spec must not
        silently reclassify archived findings as tool-produced."""
        assert "manual" in NON_TOOL_TECHNIQUES


class TestWhatClassifyNowAnswers:
    def test_a_spec_non_tool_technique_is_not_called_a_tool(self):
        for t in SPEC:
            got = classify({"technique": t, "computed": {"x": 3}})
            assert got == t, (t, got)

    def test_a_real_tool_is_still_called_a_tool(self):
        """The off-switch: if everything answers with its own name, the
        distinction has been deleted rather than corrected."""
        for t in ("grim_check", "statcheck", "check_count_percent"):
            assert classify({"technique": t, "computed": {"x": 3}}) == "tool"

    def test_unaided_arithmetic_is_unchanged_for_the_two_it_reads(self):
        """`did_unaided_arithmetic` keys on exactly two members plus the
        contents-decided legacy label. Widening the membership must not move
        it -- that would be a severity change smuggled in as a vocabulary fix."""
        for t, want in (("no_tool_exists", True), ("tool_existed_unused", True),
                        ("not_computational", False),
                        ("internal_contradiction", False),
                        ("factual_claim", False), ("grim_check", False)):
            got = did_unaided_arithmetic({"technique": t, "computed": {"x": 3}})
            assert got is want, (t, got, want)

    def test_the_legacy_label_is_still_decided_by_its_contents(self):
        assert did_unaided_arithmetic({"technique": "manual", "computed": {"x": 3}})
        assert not did_unaided_arithmetic({"technique": "manual", "computed": {}})
