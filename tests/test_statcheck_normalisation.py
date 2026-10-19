"""Four extraction artefacts that make a printed statistic invisible to statcheck.

statcheck answers "no statistics found in text", which a reader takes as a fact
about the paper. Every case below is a MEASURED instance where it was a fact
about our text channel instead -- the same defect class as the HTML-entity and
capital-`P` repairs that were already in `python_statcheck_text`, found in a
9-paper grok-4.6 psychology batch on 2026-08-22.

The two new ones:

* docling renders `<` as `\\` in some PDFs. On 10.1007--s10803-013-1829-4
  (Springer) there are 15 `p \\ .001` and ZERO `p <`, so every `p < .001` in
  the paper was unreadable; repairing them takes statcheck from 26 to 37
  statistics on that one paper.
* runs of whitespace defeat the regex outright. On
  10.1037--0022-3514.71.2.230 (Bargh, Chen & Burrows 1996, an old scan whose
  text layer keeps inter-word padding) the whole-text channel found 0 of 4.
"""
import pytest

from metascience_agent.tools.r_wrappers import (
    normalise_for_statcheck,
    python_statcheck_text,
)


class TestNormalisation:
    @pytest.mark.parametrize("raw,want", [
        # docling's backslash for `<`
        (r"t (30) = -2.62, p \ .001", "t (30) = -2.62, p < .001"),
        (r"F(2, 54) = 51.81, p \ .001", "F(2, 54) = 51.81, p < .001"),
        # HTML entities
        ("F(2, 33) = 5.76, p &lt; .05", "F(2, 33) = 5.76, p < .05"),
        # capital P
        ("r(51) = -0.167, P = 0.232", "r(51) = -0.167, p = 0.232"),
        # runs of horizontal whitespace
        ("F(2,  33)  =  5.76, p  =  .008", "F(2, 33) = 5.76, p = .008"),
    ])
    def test_each_artefact_is_repaired(self, raw, want):
        assert normalise_for_statcheck(raw) == want

    @pytest.mark.parametrize("raw", [
        r"C:\path\to\file",            # a path, not a comparator
        r"see \ref{tab:1} and p 4",     # a backslash with no p-value after it
        "the P wave amplitude",         # an ordinary capital P
        "panel P shows the trend",      # a panel label
    ])
    def test_scoping_leaves_unrelated_text_untouched(self, raw):
        """Both the backslash rule and the capital-P rule are scoped to a
        p-value CONTEXT -- a comparator and a number. Widening either would
        rewrite paths, LaTeX and panel labels."""
        assert normalise_for_statcheck(raw) == raw

    def test_newlines_survive(self):
        """statcheck's own line handling depends on them; only horizontal
        whitespace is collapsed."""
        assert normalise_for_statcheck("a  b\n\nc  d") == "a b\n\nc d"

    def test_none_and_empty_do_not_raise(self):
        assert normalise_for_statcheck("") == ""
        assert normalise_for_statcheck(None) == ""


class TestStatcheckSeesTheRepairedText:
    """The repair is worthless if it does not change what statcheck extracts.
    A normaliser with no consumer is the failure mode this repo keeps hitting."""

    @pytest.mark.parametrize("text", [
        "main effect, F(2,  33)  =  5.76, p  =  .008.",
        r"attitudes rose, t (30) = -2.62, p \ .001, d = .47.",
        "F(2, 33) = 5.76, p &lt; .05",
        "r(51) = -0.167, P = 0.232",
    ])
    def test_one_statistic_is_recovered_from_each_artefact(self, text):
        out = python_statcheck_text(text)
        assert out.get("stats_found") == 1, out

    def test_the_unrepaired_form_is_what_used_to_fail(self):
        """Pinning the defect itself, so a regression is legible: statcheck's
        own regex allows ONE optional space between tokens."""
        from statcheck.st import statcheck as _upstream
        df, _ = _upstream("main effect, F(2,  33)  =  5.76, p  =  .008.")
        assert df is None or len(df) == 0, \
            "upstream now handles padded whitespace; the repair may be redundant"


class TestOneToolOneAnswer:
    """`python_statcheck(pdf_path)` and `python_statcheck_text(text)` were two
    implementations wearing one name. The PDF route had NONE of the repairs
    above and NONE of the rounding-interval filter, so on
    10.1007--s10803-013-1829-4 it reported `errors_found: 25` where the text
    route reports 1 -- 24 of them p-values correct at their own printed
    precision. A model handed 25 and a model handed 1 are reading two different
    papers."""

    _TEXT = ("A one-way ANOVA revealed a significant main effect, "
             "F(2,  33)  =  5.76, p  =  .008. Attitudes rose, "
             r"t (30) = -2.62, p \ .001, d = .47.")

    def _patched(self, monkeypatch, tmp_path, text):
        pdf = tmp_path / "paper.pdf"
        pdf.write_bytes(b"%PDF-1.4 not really a pdf")
        from metascience_agent.extraction import pdf as _pdf
        monkeypatch.setattr(_pdf, "extract_text_with_tables",
                            lambda *a, **k: {"text": text, "tables": []})
        return pdf

    def test_the_pdf_route_inherits_the_repairs(self, monkeypatch, tmp_path):
        from metascience_agent.tools.r_wrappers import python_statcheck
        pdf = self._patched(monkeypatch, tmp_path, self._TEXT)
        out = python_statcheck(str(pdf))
        assert out["pdf_reader"] == "docling"
        assert out["stats_found"] == 2, \
            "padded whitespace and docling's backslash must both be repaired"

    def test_the_two_routes_agree_on_the_same_document(self, monkeypatch,
                                                       tmp_path):
        from metascience_agent.tools.r_wrappers import (
            python_statcheck, python_statcheck_text)
        pdf = self._patched(monkeypatch, tmp_path, self._TEXT)
        a = python_statcheck(str(pdf))
        b = python_statcheck_text(self._TEXT)
        for k in ("stats_found", "errors_found", "errors_flagged_upstream",
                  "errors_explained_by_rounding", "decision_errors"):
            assert a[k] == b[k], f"{k}: pdf route {a[k]} vs text route {b[k]}"

    def test_the_pdf_route_reports_the_rounding_split(self, monkeypatch,
                                                      tmp_path):
        """The old PDF route had no `errors_explained_by_rounding` key at all,
        so a caller could not tell a rounding artefact from a real one."""
        from metascience_agent.tools.r_wrappers import python_statcheck
        pdf = self._patched(monkeypatch, tmp_path,
                            "the effect held, F(2, 33) = 5.76, p = .008.")
        out = python_statcheck(str(pdf))
        assert out["errors_flagged_upstream"] == 1, "computed p is .00715"
        assert out["errors_explained_by_rounding"] == 0, ".008 is not .007"
        assert out["errors_found"] == 1
        assert out["decision_errors"] == 0, "both sides of .05; no decision flips"

    def test_a_pdf_our_extractor_cannot_read_falls_back(self, monkeypatch,
                                                        tmp_path):
        from metascience_agent.tools.r_wrappers import python_statcheck
        pdf = self._patched(monkeypatch, tmp_path, "")
        monkeypatch.setattr(
            "metascience_agent.tools.r_wrappers._statcheck_pdf_via_vendored_reader",
            lambda p: {"success": True, "stats_found": 7,
                       "pdf_reader": "statcheck_pdfminer"})
        out = python_statcheck(str(pdf))
        assert out["pdf_reader"] == "statcheck_pdfminer"
        assert out["stats_found"] == 7
