"""When we could not read the paper itself, we must not claim its contents.

`build_haystack` guards each source independently, so a scanned PDF-only paper
whose body/XML/PDF text all fail to extract -- but which ships a machine-readable
supplement -- yields a haystack of the supplement ALONE. The old `annotate`
guarded only the TOTALLY empty haystack, so every finding was then stamped
against the supplement: a quote whose numbers happen to be in the supplement got
`stitched` ("searching the PDF for it will find nothing" -- about a PDF we never
opened), and the rest got `unverified` ("not located"). Both are definitive
claims about text we never read -- the house failure pattern.
"""

import forensic_metascience_ai_toolkit.quotes as quotes
from forensic_metascience_ai_toolkit.quotes import annotate, normalise


class TestOnlyASupplementLoaded:
    def _only_supplement(self, monkeypatch, text):
        monkeypatch.setattr(
            quotes, "build_haystack",
            lambda _dir: {"a supplement": normalise(text)})

    def test_a_negative_verdict_is_withheld_not_asserted(self, monkeypatch):
        # The quote's numbers are NOT in the supplement. The old code stamped
        # this `unverified` ("we searched the paper and did not find it"); the
        # truth is we never read the paper, so no stamp may be made.
        self._only_supplement(monkeypatch, "Supplementary Table S1: age 40, 41, 42")
        findings = [{"id": "x", "quote": "the mean score was 4.52 (SD 1.2)"}]
        annotate(findings, "/nonexistent")
        assert "quote_verified" not in findings[0], findings[0]

    def test_a_stitched_verdict_is_withheld_when_paper_unread(self, monkeypatch):
        # Numbers ARE in the supplement, so the old code returned `stitched` with
        # "searching the PDF for it will find nothing" -- a claim about a PDF we
        # never opened. Withhold it.
        self._only_supplement(monkeypatch, "Supplement: values 4.52 and 1.2 appear here")
        findings = [{"id": "x", "quote": "the mean score was 4.52 (SD 1.2) in the arm"}]
        annotate(findings, "/nonexistent")
        assert "quote_verified" not in findings[0], findings[0]

    def test_a_quote_actually_in_the_supplement_still_gets_a_positive_stamp(self, monkeypatch):
        # A verbatim hit in the supplement is honest to report -- it says where
        # we DID find it. Positive locations are kept.
        self._only_supplement(monkeypatch, "the supplement reports a mean score of 4.52 (sd 1.2) in the arm")
        findings = [{"id": "x", "quote": "a mean score of 4.52 (SD 1.2) in the arm"}]
        annotate(findings, "/nonexistent")
        assert findings[0].get("quote_verified") == "verbatim"
        assert findings[0].get("quote_source") == "a supplement"


class TestPrimarySourcePresentIsUnchanged:
    def test_paper_text_present_still_stamps_negatives(self, monkeypatch):
        # When the paper body WAS read, a genuinely unlocatable quote is still
        # `unverified` -- the honest verdict is intact.
        monkeypatch.setattr(
            quotes, "build_haystack",
            lambda _dir: {"the paper's text": normalise("We recruited 100 people.")})
        findings = [{"id": "x", "quote": "compensated with 40 dollars"}]
        annotate(findings, "/nonexistent")
        assert findings[0].get("quote_verified") == "unverified"

    def test_empty_haystack_still_withholds(self, monkeypatch):
        monkeypatch.setattr(quotes, "build_haystack", lambda _dir: {})
        findings = [{"id": "x", "quote": "anything"}]
        annotate(findings, "/nonexistent")
        assert "quote_verified" not in findings[0]
