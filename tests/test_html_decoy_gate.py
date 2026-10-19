"""The fetched HTML must be the article, or serve nothing.

MEASURED 2026-09-05 on the cerebrolysin corpus: 16 paper directories hold an
HTML file `find_html` accepts as the article, and on 13 of them
`_derive_paper_text` returned it -- 228 characters reading "Client Challenge.
JavaScript is disabled in your browser." served as the paper's full text.

`_looks_like_boilerplate` missed them by design: both its signatures require
DOMINANCE (a line repeated until it fills the page, or interstitial phrases
summing to a large share), and a challenge page says its one sentence once.

This toolkit reports absent data as a finding, so a paper read from an
interstitial manufactures accusations against its authors for our failed fetch.
"""


import sys

import pytest

from metascience_agent.extraction.html import (
    _ARTICLE_TEXT_FLOOR,
    article_text_too_short,
    manual_fetch_needed,
)

CHALLENGE = (
    "Client Challenge JavaScript is disabled in your browser. Please enable "
    "JavaScript to proceed. A required part of this site couldn't load. This "
    "may be due to a browser extension, network issues, or browser settings."
)


def _paper(tmp_path, html: str, name="10.1023--a~1016270626439"):
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.pdf").write_bytes(b"%PDF-1.4 stub")
    (d / f"{name}.landing.html").write_text(
        f"<html><body><p>{html}</p></body></html>", encoding="utf-8")
    return d


def test_a_challenge_page_is_too_short_to_be_an_article():
    assert article_text_too_short(CHALLENGE) is not None


def test_a_real_article_length_clears_the_floor():
    assert article_text_too_short("word " * 400) is None


def test_the_floor_sits_between_the_measured_populations():
    """Decoys measured at 194-228 chars, the shortest real paper at 2,810.
    The floor must sit clear of BOTH, or it is tuned to one sample."""
    assert 228 < _ARTICLE_TEXT_FLOOR < 2810


def test_the_reason_names_the_number_rather_than_asserting_a_verdict():
    reason = article_text_too_short(CHALLENGE)
    assert str(len(" ".join(CHALLENGE.split()))) in reason


def test_a_decoy_paper_is_reported_with_a_url_to_fetch_by_hand(tmp_path):
    """Greg's ruling: the fix for a bot challenge is a person, so the record
    must carry a URL. A record naming no URL is not actionable."""
    rec = manual_fetch_needed(_paper(tmp_path, CHALLENGE))
    assert rec is not None
    assert rec["url"] and rec["url"].startswith("https://doi.org/")
    assert rec["url_source"]


def test_the_tilde_is_restored_to_a_colon_in_the_derived_doi(tmp_path):
    """`paper_ids.doi_dirname` encodes only `/`; the `~` is the fetcher
    sanitising a colon. VERIFIED against doi.org: the restored form returns
    200 and the tilde form 404, so serving the tilde would hand the operator a
    URL that resolves nowhere -- worse than handing them none."""
    rec = manual_fetch_needed(_paper(tmp_path, CHALLENGE))
    assert "~" not in rec["url"]
    assert rec["url"].endswith("10.1023/a:1016270626439")


def test_a_real_article_is_not_reported(tmp_path):
    assert manual_fetch_needed(_paper(tmp_path, "word " * 400)) is None


@pytest.fixture(autouse=True)
def _builtin_article_gate(monkeypatch):
    """These small fixtures exercise the built-in gate and HTML extraction.

    The optional fetchpdf validator requires full-length articles with populated
    tables. Installing it must not change these focused unit tests. Production
    validation stays enabled; tests/test_html.py covers actual article inputs.
    """
    monkeypatch.setitem(sys.modules, "fetchpdf.retrieval.validate", None)


@pytest.mark.parametrize("accepted", [False, True])
def test_optional_validator_decision_is_respected(tmp_path, monkeypatch, accepted):
    from types import ModuleType, SimpleNamespace

    from metascience_agent.extraction.html import _validate_not_a_landing_page

    calls = []
    module = ModuleType("fetchpdf.retrieval.validate")

    def validate(content, **kwargs):
        calls.append((content, kwargs))
        return SimpleNamespace(ok=accepted, reason="validator refusal")

    module.validate_t2 = validate
    monkeypatch.setitem(sys.modules, module.__name__, module)
    path = tmp_path / "article.html"
    content = ("<html><body><p>" + "article prose. " * 500 + "</p></body></html>").encode()
    path.write_bytes(content)
    reason = _validate_not_a_landing_page(path, content)
    assert reason == (None if accepted else "validator refusal")
    assert len(calls) == 1 and calls[0][0] == content
