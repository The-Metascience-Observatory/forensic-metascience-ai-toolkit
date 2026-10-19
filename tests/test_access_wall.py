"""A publisher shop front must not outrank the article it is selling.

MEASURED 2026-08-22 on 10.1177--0093854811403123. The fetched `.fulltext.html`
is the SAGE landing page -- title, abstract, references, and "Purchase 24 hour
online access ... Article - $37.50 ... Add to cart ... Click the button below
for the full-text content". 13,838 characters, ZERO statcheck-eligible
statistics, no tables. The PDF beside it: 41,510 characters and 13 statistics.

`paper_text_with_source` ranks HTML above the PDF because real HTML preserves
table structure a text layer cannot. That reasoning is exactly backwards for a
purchase page, and everything reading `paper_text` on that paper -- the value
register, the text-forensics word count, the supplement gate -- was reading the
shop front. The tool agent only escaped it by calling `extract_pdf` itself.
"""
import pytest

from forensic_metascience_ai_toolkit.extraction.jats import (
    looks_like_access_wall,
    paper_text_with_source,
)

WALL = (
    "Evaluation of a Violence Risk Assessment Training Program Skip to main "
    "content Abstract Although a great deal of research has focused on ... "
    "Access options If you have access to journal content via a personal "
    "subscription, university, library, employer or society, select from the "
    "options below: Click the button below for the full-text content "
    "Alternatively, view purchase options below: Purchase access Purchase 24 "
    "hour online access to view and download content. Article - $37.50 Add to "
    "cart Checkout Start 2 week free trial"
)


class TestDetector:
    def test_the_measured_landing_page_is_recognised(self):
        walled, markers = looks_like_access_wall(WALL)
        assert walled is True
        assert len(markers) >= 2

    def test_one_marker_alone_is_not_enough(self):
        """Purchase chrome shows up in the sidebar of genuine full-text pages."""
        walled, _ = looks_like_access_wall(
            "Methods. Participants were 73 officers. Results ... Add to cart")
        assert walled is False

    def test_a_plain_article_is_not_a_wall(self):
        walled, markers = looks_like_access_wall(
            "Methods. Participants were 73 officers. Results. t(70) = 7.10, "
            "p < .001. Discussion.")
        assert walled is False
        assert markers == []

    def test_a_reference_list_does_not_defeat_it(self):
        """A section-word test was tried as the second condition and FAILED:
        'method' and 'discussion' both appear in the real landing page, inside
        its own reference-list titles. Pinning that this page still trips."""
        walled, _ = looks_like_access_wall(
            WALL + " References. Hart, S. D. (2008). Method and discussion "
                   "in violence risk assessment. Journal of Method 12, 1-20.")
        assert walled is True

    def test_empty_text_is_not_a_wall(self):
        assert looks_like_access_wall("") == (False, [])
        assert looks_like_access_wall(None) == (False, [])


