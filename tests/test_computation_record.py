"""No number reaches a reader without a record of where it came from.

Greg, 2026-08-13: "It should be impossible for an agent to perform computations
and it not be recorded for the sake of the output. That's black box nonsense I
want to avoid."

`technique: "manual"` could not support that rule, because it was three
unrelated things at once. MEASURED 2026-08-13 over 626 archived findings,
DEDUPLICATED by (id, location, claim, computed) -- each run is stored twice, in
`forensic_review_*` and again inside its bundle, and an undeduplicated count
inflates every figure. 159 are `manual`: 103 computed a number unaided, 36
recorded a note rather than a number, 20 recorded no computation at all. So 56
(35.2%) named findings with NO ARITHMETIC -- a data-availability statement, a
figure legend naming the wrong protein, an asterisk against the wrong p --
which the schema capped at `suspicious` on the grounds that unaided arithmetic
is unsafe.
"""

import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit import computation as C

SCHEMA = (pathlib.Path(__file__).resolve().parents[1]
          / "src/forensic_metascience_ai_toolkit/schema/findings.v2.schema.json")


class TestTheThreeCasesAreDistinguished:
    def test_a_registered_tool_is_classified_as_such(self):
        assert C.classify({"technique": "grim_check"}) == "tool"


class TestANumberMustBeAccountable:
    """THE DECIDABLE QUESTION IS WHERE THE FIGURE CAME FROM, and nothing else.

    A first cut asked "is a method recorded?" and answered it by counting
    letters beside the figure. MEASURED 2026-08-13 over the 18 archived findings
    presenting a figure that is NOT in their paper -- the exact population it
    existed to catch -- it passed 18 and failed 0, because `computed` is a dict
    and its keys are words. `{'fisher_odds_ratio_from_recalc': 1.56}` and
    `{'difference': 10576}` scored the same, and only the first names its
    derivation. That guard is gone; these tests pin what replaced it.
    """

    PAPER = "Mean weight was 4.21 kg (SD 0.9) across 40 animals."

    def test_a_figure_that_is_in_the_paper_is_a_transcription(self):
        v = C.verify({"technique": "no_tool_exists", "computed": {"x": 4.21}},
                     haystack=self.PAPER)
        assert v["transcribed"] is True
        assert v["codes"] == ["number_transcribed"]
        # RESCUED, not condemned: it is a quotation missing a locator.
        assert v["auditable"] is True

    def test_a_figure_that_is_not_in_the_paper_is_named_as_the_agents_own(self):
        v = C.verify({"technique": "no_tool_exists", "computed": {"ratio": 7.77}},
                     haystack=self.PAPER)
        assert v["codes"] == ["number_derived"]
        assert "7.77" in " ".join(v["problems"]), \
            "a ledger that does not name the figure cannot be checked against"

    def test_an_unreadable_paper_is_our_gap_and_says_so(self):
        v = C.verify({"technique": "no_tool_exists", "computed": {"x": 4.21}})
        assert v["auditable"] is False
        assert v["codes"] == ["number_uncheckable_no_paper"]
        assert "OUR gap" in " ".join(v["problems"])

    def test_a_tool_result_needs_no_extra_justification(self):
        v = C.verify({"technique": "grim_check", "computed": {"consistent": False}})
        assert v["auditable"] is True and v["kind"] == "tool"

    def test_naming_no_technique_at_all_is_a_failure(self):
        v = C.verify({"computed": {"x": 1}})
        assert v["auditable"] is False
        assert "names no technique" in " ".join(v["problems"])


class TestNotComputationalMayNotCarryArithmetic:
    """The claim and the content have to agree: declaring there is no
    arithmetic and then presenting some means one of the two is wrong."""

    def test_a_number_under_not_computational_is_caught(self):
        v = C.verify({"technique": "not_computational",
                      "computed": {"implied_n": 20}})
        assert v["auditable"] is False
        assert "presents 1 number" in " ".join(v["problems"])

    def test_a_genuine_non_computational_finding_passes(self):
        v = C.verify({"technique": "not_computational",
                      "computed": "the data-availability statement withholds "
                                  "the data it promises"})
        assert v["auditable"] is True

class TestTheLegacyLabelIsReportedAsUnauditable:
    def test_manual_cannot_be_audited_either_way(self):
        v = C.verify({"technique": "manual", "computed": {"x": 1}})
        assert v["auditable"] is False
        assert "does not say whether" in " ".join(v["problems"])

    def test_the_archive_is_entirely_legacy(self):
        """Every archived finding predates the split, which the audit should
        say plainly rather than scoring them as if the vocabulary applied."""
        root = pathlib.Path(__file__).resolve().parents[1]
        # DEDUPLICATED, on the same key as the docstring's measurement. Every
        # run is stored twice -- once under `forensic_review_*` and again inside
        # its bundle -- and an undeduplicated scan here would measure a
        # different population from the one the docstring describes, which is
        # the "name the population" failure this module is full of comments
        # about.
        seen: dict = {}
        for f in root.glob("**/findings.json"):
            if "scratchpad" in str(f):
                continue
            try:
                items = json.loads(f.read_text(encoding="utf-8")).get("findings") or []
            except Exception:
                continue
            for x in items:
                if isinstance(x, dict):
                    seen.setdefault((str(x.get("id")), str(x.get("location")),
                                     str(x.get("claim"))[:120],
                                     str(x.get("computed"))[:120]), x)
        findings = list(seen.values())
        if len(findings) < 100:
            pytest.skip("archive not in this checkout")
        a = C.audit(findings)
        assert a["by_kind"].get("tool", 0) > 400
        assert a["by_kind"].get("manual", 0) > 100
        # AND THE AUDIT SAYS WHOSE FAILURE IT IS. Run without a paper, every
        # figure is unverifiable BY US, and the note must not report that as a
        # property of the findings.
        assert a["paper_readable"] is False
        assert "COULD NOT BE READ" in a["note"]


class TestTheNoteCountsEachFailureSEPARATELY:
    """One total described in one sentence was a false statement about our own
    work. The first three runs this audit met reported "N present a number the
    artefact cannot account for" when all N were legacy labels and none was an
    unaccounted number -- LESSONS.md #2, in code written to enforce #1."""

    def test_a_legacy_label_is_not_reported_as_an_unaccounted_number(self):
        a = C.audit([{"technique": "manual",
                      "computed": "recomputed from the SI: 5.7111 gives 0.0575"}],
                    haystack="the SI prints 5.7111 and 0.0575")
        # Both figures ARE in the paper, so the only complaint about this
        # finding is our own vocabulary -- and the note must not upgrade that
        # into a claim that the agent produced a number from nowhere.
        assert a["by_code"] == {"legacy_label": 1, "number_transcribed": 1}
        assert a["n_derived"] == 0
        assert "legacy" in a["note"]
        assert "NOT in the paper" not in a["note"]

    def test_every_code_it_counts_it_also_explains(self):
        a = C.audit([{"technique": "manual", "computed": {"x": 9.99}},
                     {"computed": {"y": 1}},
                     {"technique": "not_computational", "computed": {"z": 2}}],
                    haystack="nothing matches here")
        for code in a["by_code"]:
            assert code in a["code_meanings"], f"`{code}` counted, never defined"


class TestAPartialHaystackSaysSo:
    """A figure quoted from the PROSE, when only table cells could be read, is
    not found -- and lands in the column headed "the agent produced this". That
    is our extraction failing, recorded as a property of the review. The first
    cut of `_number_haystack` swallowed the exception silently; `lint-inert`
    caught it as the 29th proven-inert finding."""

    def test_no_readable_source_returns_nothing_and_says_why(self):
        from forensic_metascience_ai_toolkit.agent import _number_haystack
        text, why = _number_haystack("/nonexistent/paper/dir", None)
        assert text is None and why, "a silent None reads as a clean paper"

    def test_cells_without_prose_carry_the_caveat(self):
        from forensic_metascience_ai_toolkit.agent import _number_haystack
        text, why = _number_haystack("/nonexistent/paper/dir",
                                     {"items": [{"raw": "12.3"}, {"raw": "4"}]})
        assert "12.3" in text
        assert "OUR gap" in why and "PROSE" in why

class TestItIsConsumed:
    def test_the_prompt_teaches_all_three(self):
        from forensic_metascience_ai_toolkit.core.prompts import tool_expert_body
        md = tool_expert_body()   # the prompt as assembled, guidance included
        for v in ("not_computational", "no_tool_exists", "tool_existed_unused"):
            assert v in md
        assert "MUST BE ACCOUNTABLE" in md


class TestLocateDoesNotMatchInsideALargerNumber:
    """FOUND BY A STRESS TEST, 2026-08-13, not by review.

    `locate` used plain containment, so `12` counted as found in a paper that
    only ever prints `3124` -- and the error ran in the DANGEROUS direction: a
    figure the agent produced was rescued as a quotation of a number the paper
    never printed, and shown to the reader as such.

    `quotes._contains_bounded` had already solved this after "n = 42" verified
    verbatim against "the final sample was n = 428". The fix existed; I reached
    for `in` instead of the module that had been bitten. Correcting it moved the
    measured transcription rate from 93.2% to 86.7%.
    """

    def test_a_number_does_not_match_inside_a_longer_one(self):
        assert C.locate("12", "n = 3124") is False
        assert C.locate("42", "the final sample was n = 428") is False

    def test_a_decimal_does_not_match_a_fractional_tail(self):
        assert C.locate(".86", "the value was 40.86") is False

    def test_the_sign_is_not_dropped(self):
        assert C.locate("-1.5", "the value was 1.5") is False

    def test_a_real_match_still_matches(self):
        assert C.locate("12", "n = 12 participants") is True
        assert C.locate("0.99", "r = .99") is True, "printed forms still count"

    def test_no_haystack_is_not_a_match(self):
        assert C.locate("1.5", None) is False
        assert C.locate("", "anything") is False


class TestALocatedNumberMayBeACoincidence:
    """`number_transcribed` withdraws the demand "Show the derivation": the
    finding is flipped to auditable and filed under `ledger`, on the strength
    of its digits appearing somewhere in the paper. `12`, `0.05`, `95` and `2`
    are printed in essentially every paper -- as a figure number, a table cell,
    an alpha, a CI level -- so finding one is not evidence that the finding
    QUOTED it. The rescue is all-or-nothing over a finding's numbers, so a
    single small number was rescued unconditionally.
    """

    HAY = ("We removed 12 items before analysis. Alpha was 0.05 and we report "
           "95% intervals. The adjusted mean was 40.86 in the treatment arm.")

    def _verify(self, computed):
        from forensic_metascience_ai_toolkit.computation import verify
        return verify({"technique": "no_tool_exists", "computed": computed},
                      self.HAY)

    def test_a_small_number_does_not_buy_a_transcription_rescue(self):
        """{"difference": 12} -- the agent subtracted 40 - 28 unaided -- is not
        a quotation just because the paper says "12 items"."""
        v = self._verify({"difference": 12})
        assert v["transcribed"] is False
        assert "number_transcribed_uninformative" in v["codes"]

    def test_alpha_and_ci_levels_do_not_either(self):
        v = self._verify({"alpha": 0.05, "ci": 95})
        assert v["transcribed"] is False

    def test_an_informative_figure_still_earns_the_rescue(self):
        v = self._verify({"adjusted_mean": 40.86})
        assert v["transcribed"] is True
        assert "number_transcribed" in v["codes"]

    def test_one_informative_figure_is_enough(self):
        """The gate asks whether ANY figure carries information, not all."""
        v = self._verify({"adjusted_mean": 40.86, "n_removed": 12})
        assert v["transcribed"] is True

    def test_an_unlocated_figure_still_demands_the_derivation(self):
        v = self._verify({"adjusted_mean": 77.31})
        assert v["transcribed"] is False
        assert "number_derived" in v["codes"]

    def test_significant_digits(self):
        from forensic_metascience_ai_toolkit.computation import _significant_digits as sd
        assert sd("12") == 2
        assert sd("0.05") == 1
        assert sd("40.86") == 4
        assert sd("0.421") == 3
        assert sd("100") == 1        # trailing integer zeros are ambiguous

class TestARangeSeparatorIsNotAMinusSign:
    """`_NUMBER` was `-?\\d+(?:\\.\\d+)?`, so the separator in
    `rows 1-8, 9-16, 17-24` was read as a sign and -8, -16 and -24 were reported
    as figures the finding presented.

    Those appear in no paper, so they land in `unlocated` and the finding is
    stamped `number_derived`: "appear nowhere in the paper ... so the agent
    produced them. Show the derivation." A verbatim transcription accused of
    unaudited arithmetic, over a hyphen.

    21 such spurious negatives sit in the nine archived papers. None reached
    that stamp, because those findings are `kind == "tool"` and skip the branch.
    Latent, fixed before it fired.
    """

    def test_a_row_range_is_two_numbers(self):
        from forensic_metascience_ai_toolkit.computation import _numbers_in
        assert _numbers_in("rows 1-8, 9-16") == ["1", "8", "9", "16"]

    def test_a_scale_range_is_two_numbers(self):
        from forensic_metascience_ai_toolkit.computation import _numbers_in
        assert _numbers_in("integer responses on a 1-7 scale") == ["1", "7"]

    def test_a_genuine_negative_survives(self):
        from forensic_metascience_ai_toolkit.computation import _numbers_in
        assert _numbers_in({"difference": -0.85}) == ["-0.85"]
        assert _numbers_in("change of -1.5") == ["-1.5"]

    def test_a_decimal_range_does_not_become_a_negative(self):
        from forensic_metascience_ai_toolkit.computation import _numbers_in
        assert _numbers_in("2.5-1.234") == ["2.5", "1.234"]

    def test_a_figure_spelled_inside_a_key_is_still_a_figure(self):
        """NOT `numerals.NUMERAL`, deliberately. That pattern refuses a digit
        glued to a word, which is right for prose and wrong here: a computed
        block is a stringified dict whose KEYS carry figures, and this guard
        asks whether a figure the agent presented came out of the paper.
        Switching to the shared tokenizer would have dropped 346 such figures
        across 116 of the 225 archived blocks -- making the guard ask a smaller
        question, which is the wrong direction for a guard."""
        from forensic_metascience_ai_toolkit.computation import _numbers_in
        got = _numbers_in({"unique_viable_n_for_61pct_within_n_max_19": 18})
        assert got == ["61", "19", "18"]
