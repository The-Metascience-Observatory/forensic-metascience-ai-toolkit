"""LaTeX-flavoured extractor output, normalised so the floor can read it.

MEASURED on 10.1007--s00702-004-0248-2: our floor reads 40 statistics from the
text layer, 39 from Mistral, and 2 from Mathpix -- whose extraction was
excellent and whose notation we simply could not see. Across the 22 damaged
papers the normalisation takes Mathpix from 277 statistics to 1,266."""

from metascience_agent.latex_text import to_unicode, looks_like_latex


class TestItIsSafeToApplyGlobally:
    """`glyphs.proven_repairs` refuses to map a raw control byte without
    per-document proof, because a font glyph index means whatever that font
    says -- `\\x06` is `±` in three corpus papers and a DECIMAL POINT in a
    fourth. A LaTeX command name is a STANDARD: `\\pm` means `±` in every
    document ever written. Same class as decoding `&lt;`."""

    def test_the_operator_that_matters(self):
        assert to_unicode(r"$65 \pm 1.17$").strip() == "65 ±   1.17"

    def test_comparison_operators(self):
        assert "≤" in to_unicode(r"$p \leq 0.05$")
        assert "≥" in to_unicode(r"$n \geq 30$")

    def test_greek_used_as_units_and_names(self):
        assert "µ" in to_unicode(r"$12 \mu \mathrm{g}$")
        assert "β" in to_unicode(r"$\beta = 0.31$")


class TestLengthIsPreserved:
    """Every repair in this codebase is length-preserving so that an offset into
    the normalised text is an offset into the original, and `raw` can still be
    sliced from the source a reader would recognise."""

    CASES = [r"$65 \pm 1.17$", r"$\mathrm{N}=68$", r"$p \leq 0.05$",
             r"$12.3 \pm 1.4 \mu \mathrm{g}$", r"$\alpha$ and $\beta$",
             r"20\% of $n = 30$"]

    def test_every_case_keeps_its_width(self):
        for s in self.CASES:
            assert len(to_unicode(s)) == len(s), s

    def test_plain_text_is_returned_untouched(self):
        t = "mean age was 65 ± 1.17 years"
        assert to_unicode(t) == t


class TestItKnowsWhenNotToRun:
    def test_a_dollar_sign_in_a_cost_table_is_not_mathematics(self):
        assert not looks_like_latex("the trial cost $2.4 million in total")

    def test_real_latex_is_detected(self):
        assert looks_like_latex(r"$a \pm b$ and $c \pm d$ and $e \pm f$")


class TestTheFloorCanNowReadIt:
    def test_a_mathpix_style_mean_and_sd_is_enumerated(self):
        from metascience_agent import completeness as C
        text = (r"Values are mean $\pm$ SD. Age was $65 \pm 1.17$ years and "
                r"weight $70.2 \pm 3.4$ kg, with $p \leq 0.05$ throughout.")
        kinds = [i["kind"] for i in C._body_items(text)]
        assert "mean_pm_prose" in kinds

    def test_an_unrecognised_command_is_dropped_not_guessed(self):
        """It cannot be a number, and leaving the backslash in would only give
        the floor a token it will never match."""
        out = to_unicode(r"$x \someunknownmacro y$")
        assert "\\" not in out and "someunknownmacro" not in out
