"""A fullwidth parenthesis is a parenthesis.

Measured 2026-09-03 across 21 supplement .docx files in three corpora: U+FF08
and U+FF09 occur 83 times each, in 81 cells of one file -- the mefatinib
protocol supplement, which writes its phase II adverse-event table as
`88.89%（32）`. Nothing else fullwidth occurs anywhere; the DIGITS are ordinary
ASCII, so a repair aimed at them would fix nothing.

WHAT THIS BUYS, STATED HONESTLY: parity, not coverage. `88.89%(32)` does not
parse in EITHER encoding -- the parser handles `32 (88.89%)` but not the
reversed order -- so repairing the parenthesis does not by itself recover the
table. It removes the encoding as a variable, which is what makes the remaining
gap legible as a parser gap rather than a Unicode one.

AND THE REVERSED FORM IS NOT WORTH BUILDING -- measured 2026-09-03 so nobody
re-investigates. `percent% (count)` occurs in **80 cells, all of them in this
one supplement**. The form the parser already reads, `count (percent%)`, occurs
**1,939 times across at least five supplements**. So the gap is one paper's
house style at 4% of the volume of the convention everyone else uses, and
closing it would make precisely the cells whose denominator we would then have
to guess -- the documented route from a coverage win to a false accusation
(25e2f9f, reverted once for exactly this).
"""
from metascience_agent.tools import celltypes


class TestFullwidthParens:
    def test_the_repair_is_registered(self):
        assert celltypes._UNICODE_REPAIRS.get("（") == "("
        assert celltypes._UNICODE_REPAIRS.get("）") == ")"

    def test_the_regex_is_built_from_the_table(self):
        # Guards the build step rather than restating the dict.
        assert celltypes._UNICODE_RE.search("88.89%（32）")

    def test_both_spellings_reach_the_same_parse(self):
        wide = celltypes.parse_cell("88.89%（32）")
        plain = celltypes.parse_cell("88.89%(32)")
        assert (wide.kind, wide.value, wide.percent, wide.count) == \
               (plain.kind, plain.value, plain.percent, plain.count)
        assert wide.unicode_repairs == 2, "the repair must actually fire"

    def test_the_repair_reaches_a_form_that_does_parse(self):
        # The parenthesis repair is load-bearing for the form the parser DOES
        # understand: a fullwidth `32（88.89%）` must type exactly as its ASCII
        # twin, which is the whole point.
        wide = celltypes.parse_cell("32（88.89%）")
        plain = celltypes.parse_cell("32(88.89%)")
        assert wide.kind == plain.kind == "n_percent"
        assert (wide.count, wide.percent) == (32, 88.89)

    def test_ascii_parens_are_untouched(self):
        assert not celltypes._UNICODE_RE.search("12.3 (4.5)")
