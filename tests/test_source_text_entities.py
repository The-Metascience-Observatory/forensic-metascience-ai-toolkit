"""HTML entities from the extractor must not reach the reader.

MEASURED 2026-08-16 across all 16 cached docling extractions: 176 `&lt;`/`&gt;`
plus 201 `&amp;`. Essentially every threshold p-value in the corpus arrives
entity-encoded, because docling emits `P &lt; 0.05` where the paper printed
`P < 0.05`.

The cache is left alone deliberately -- it is a faithful record of what docling
produced, and rewriting it would destroy the only evidence of what the extractor
actually did. The decode belongs on the DISPLAY path, and there are two of them:

  report.md    `report_render._quote_line`, decoding since 2026-08-16
  viewer.html  `bundle.render_viewer`, decoding since 2026-08-17

The viewer needed its own fix rather than inheriting the markdown one, and the
reason is worth keeping: the viewer's JS runs quotes through `esc()` before
insertion, so an entity that survives to the payload is escaped a SECOND time
into `&amp;lt;` and rendered on screen as the literal text `&lt;`. Decode before
escape; never instead of it.

MEASURED in the archived artefacts when this was written: 59 entity-carrying
strings in the PNAS `findings.json`, in three keys -- `quote` 31,
`provenance_quote` 21, `source_quote` 4.
"""
import json
from pathlib import Path

import pytest

from metascience_agent.bundle import _SOURCE_TEXT_KEYS, _decode_source_text


class TestTheDecodeIsScopedToQuotedText:
    """The scoping is the design, not an optimisation."""

    def test_quoted_fields_are_decoded(self):
        payload = {"findings": [{"quote": "P &lt; 0.05",
                                 "source_quote": "F &gt; 1",
                                 "provenance_quote": "M &lt; 2"}]}
        f = _decode_source_text(payload)["findings"][0]
        assert f["quote"] == "P < 0.05"
        assert f["source_quote"] == "F > 1"
        assert f["provenance_quote"] == "M < 2"

    def test_model_prose_is_left_exactly_alone(self):
        """A blanket walk would rewrite text that never came from the paper.

        `&` is an ordinary character in explanatory prose -- an author list, a
        company name, a comparison the model wrote itself. Only the three keys
        carry the promise "this is what the paper printed", and only that
        promise is broken by an entity.
        """
        payload = {"explanation": "the AT&amp;T study &lt;-- see note",
                   "headline": {"summary": "R&amp;D spending"}}
        out = _decode_source_text(payload)
        assert out["explanation"] == "the AT&amp;T study &lt;-- see note"
        assert out["headline"]["summary"] == "R&amp;D spending"

    def test_it_recurses_through_lists_and_dicts(self):
        payload = {"a": [{"b": [{"quote": "n &gt; 30"}]}]}
        assert _decode_source_text(payload)["a"][0]["b"][0]["quote"] == "n > 30"

    def test_non_string_values_survive(self):
        """Severity ranks, counts and None all pass through this walk."""
        payload = {"quote": None, "n": 3, "flag": True, "vals": [1.5, None]}
        out = _decode_source_text(payload)
        assert out == payload

    def test_the_key_list_matches_what_was_measured(self):
        assert set(_SOURCE_TEXT_KEYS) == {
            "quote", "source_quote", "provenance_quote"}


class TestTheRenderedViewerCarriesNoEntities:
    def test_render_viewer_emits_decoded_quotes(self):
        """End to end, because the unit test above cannot catch the payload
        being decoded and then re-encoded by something downstream."""
        from metascience_agent.bundle import render_viewer
        html_out = render_viewer({
            "paper_id": "10.0000/test",
            "findings": [{"quote": "P &lt; 0.05", "severity": "indeterminate"}],
        })
        assert '"P < 0.05"' in html_out or "P < 0.05" in html_out
        # The escaped-once form is what `esc()` should produce at runtime from a
        # decoded payload. The DOUBLE-escaped form is the defect, and it must
        # not be sitting in the serialised data.
        assert "&amp;lt;" not in html_out


class TestTheMarkdownPathToo:
    def test_quote_line_decodes(self):
        from metascience_agent.report_render import _quote_line
        line = _quote_line("- ", "P &lt; 0.05", "the paper's text", "verbatim")
        assert "P < 0.05" in line
        assert "&lt;" not in line


class TestTheArchiveRecordsWhyThisExists:
    """Not a regression guard -- a record that the defect was real and shipped."""

    def test_the_pnas_findings_still_show_the_original_leak(self):
        f = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1073--pnas.0801268105/"
                 "forensic_review_2026-08-16/findings.json")
        if not f.is_file():
            pytest.skip("run artefacts not present")
        raw = f.read_text(encoding="utf-8")
        assert "&lt;" in raw, (
            "the archived artefact is the evidence this defect reached a "
            "delivered report; if it is gone, so is the reason for this module")
        # And the decode fixes it.
        assert "&lt;" not in json.dumps(_decode_source_text(json.loads(raw)))
