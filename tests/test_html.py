"""
Tests for fetched-publisher-HTML ingestion (`extraction/html.py`).

Two load-bearing properties, tested directly rather than implied:

1. The table-structure guards `extraction/jats.py` already earned (a merged
   cell repeated into its continuations fabricates duplicate (mean, SD) pairs;
   a shifted column label hands GRIM a triple the paper never reported) carry
   over unchanged, because this module reuses `_expand`/`_cells_from_grid`/
   `_flatten_header` directly rather than re-deriving them.
2. The property XML extraction never needed: a fetched "full text" HTML file
   can be a landing page, cookie gate, or JS-rendered shell rather than the
   article, and must be refused (structured error), not silently swept.

Structure-focused tests bypass the landing-page guard (monkeypatched to
"passes") so they test table parsing, not validation, in isolation. The guard
itself is tested separately, with real content long enough to clear
`validate_t2`'s own byte-count floors on its own merits — see
`fetchpdf/tests/test_landing_page_detection.py` for the guard's own regression
tests against real decoy pages; these just confirm the wiring here reaches it.
"""

import pytest

from forensic_metascience_ai_toolkit.extraction.html import (
    extract_html_text_with_tables,
    find_html,
)


def _write(tmp_path, body, name="paper.fulltext.html"):
    path = tmp_path / name
    path.write_text(
        f"<!DOCTYPE html><html><head><title>T</title></head>"
        f"<body>{body}</body></html>",
        encoding="utf-8",
    )
    return path


def _table(tmp_path, inner, extra_body=""):
    return _write(
        tmp_path,
        f"<article>{extra_body}<table id='t1'><caption>Table 1. Cap.</caption>"
        f"{inner}</table></article>",
    )


def _only_table(tmp_path, inner, extra_body="", monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.setattr(
            "forensic_metascience_ai_toolkit.extraction.html._validate_not_a_landing_page",
            lambda path, content, **kw: None,
        )
    result = extract_html_text_with_tables(_table(tmp_path, inner, extra_body))
    assert not result.get("error"), result.get("error")
    assert result["n_tables"] == 1
    return result["tables"][0]


# ---------------------------------------------------------------------------
# Span expansion — the fabricated-duplication guard, reused from jats.py
# ---------------------------------------------------------------------------

def test_body_colspan_places_the_value_exactly_once(tmp_path, monkeypatch):
    table = _only_table(
        tmp_path,
        "<thead><tr><th>Group</th><th>A</th><th>B</th><th>C</th><th>D</th></tr></thead>"
        "<tbody><tr><td>Pooled</td><td colspan='4'>3.7 (0.30)</td></tr></tbody>",
        monkeypatch=monkeypatch,
    )
    flat = [c["raw"] for c in table["cells"]]
    assert flat.count("3.7 (0.30)") == 1
    row = table["rows"][0]
    assert row == ["Pooled", "3.7 (0.30)", "", "", ""]


def test_multirow_header_becomes_composite_labels(tmp_path, monkeypatch):
    table = _only_table(
        tmp_path,
        "<thead>"
        "<tr><th rowspan='2'>Var</th><th colspan='2'>Weighted %</th></tr>"
        "<tr><th>Non</th><th>Vet</th></tr>"
        "</thead>"
        "<tbody><tr><td>Age</td><td>50.1</td><td>61.2</td></tr></tbody>",
        monkeypatch=monkeypatch,
    )
    assert table["headers"] == ["Var", "Weighted % | Non", "Weighted % | Vet"]
    raws = {(c["row_label"], c["col_label"]): c["raw"] for c in table["cells"]}
    assert raws[("Age", "Weighted % | Non")] == "50.1"
    assert raws[("Age", "Weighted % | Vet")] == "61.2"


def test_ragged_flag_is_only_set_for_rows_short_in_the_source(tmp_path, monkeypatch):
    table = _only_table(
        tmp_path,
        "<thead><tr><th>h</th><th>i</th><th>j</th></tr></thead>"
        "<tbody>"
        "<tr><td>lbl</td><td colspan='2'>1.1</td></tr>"  # blanks, but not short
        "<tr><td>x</td><td>2.2</td></tr>"                 # genuinely short: 1 numeric cell only
        "</tbody>",
        monkeypatch=monkeypatch,
    )
    # A single numeric cell in a short row is benign (rule: >=2 numerics needed).
    assert table["alignment_uncertain"] is False


def test_ragged_row_with_two_numerics_is_flagged(tmp_path, monkeypatch):
    table = _only_table(
        tmp_path,
        "<thead><tr><th>h</th><th>i</th><th>j</th></tr></thead>"
        "<tbody>"
        "<tr><td>lbl</td><td>1.1</td><td>2.2</td></tr>"
        "<tr><td>3.3</td><td>4.4</td></tr>"  # short AND >=2 numeric cells
        "</tbody>",
        monkeypatch=monkeypatch,
    )
    assert table["alignment_uncertain"] is True
    assert any("ragged row" in w for w in table["warnings"])


def test_table_with_no_rows_reports_image_only(tmp_path, monkeypatch):
    """A <table> tag with no populated rows -- most likely never rendered by
    the page's own JavaScript. Same treatment jats.py gives a picture-only
    table: no cells, and say so rather than pretending it was checked."""
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.extraction.html._validate_not_a_landing_page",
        lambda path, content, **kw: None,
    )
    path = _write(
        tmp_path,
        "<article><table id='t9'><caption>Table 9.</caption></table></article>",
    )
    result = extract_html_text_with_tables(path)
    table = result["tables"][0]
    assert table["image_only"] is True
    assert table["data"] == [] and table["cells"] == []


def test_table_content_is_never_inlined_into_text(tmp_path, monkeypatch):
    """Only a placeholder reaches `text` -- pouring table data into prose loses
    column alignment, the exact failure this reuses jats.py's reasoning to avoid."""
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.extraction.html._validate_not_a_landing_page",
        lambda path, content, **kw: None,
    )
    path = _write(
        tmp_path,
        "<article><p>Real prose paragraph.</p>"
        "<table id='t1'><caption>Table 1.</caption>"
        "<tbody><tr><td>3.7</td><td>0.30</td></tr></tbody></table></article>",
    )
    result = extract_html_text_with_tables(path)
    assert "Real prose paragraph." in result["text"]
    assert "3.7" not in result["text"]
    assert "Table 1" in result["text"]  # the placeholder reference, not the data


# ---------------------------------------------------------------------------
# find_html — narrow substring exclusion, matching find_xml's convention
# ---------------------------------------------------------------------------

def test_find_html_prefers_dirname_stem(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.extraction.html._validate_not_a_landing_page",
        lambda path, content, **kw: None,
    )
    (tmp_path / "other.html").write_text("<html></html>", encoding="utf-8")
    preferred = tmp_path / f"{tmp_path.name}.fulltext.html"
    preferred.write_text("<html></html>", encoding="utf-8")
    assert find_html(tmp_path) == preferred


def test_find_html_excludes_supplementary_stems(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.extraction.html._validate_not_a_landing_page",
        lambda path, content, **kw: None,
    )
    (tmp_path / "paper_supplementary_info_1.html").write_text("<html></html>", encoding="utf-8")
    real = tmp_path / "paper.fulltext.html"
    real.write_text("<html></html>", encoding="utf-8")
    assert find_html(tmp_path) == real


def test_find_html_returns_none_when_absent(tmp_path):
    assert find_html(tmp_path) is None


def test_find_html_returns_none_when_content_fails_validation(tmp_path):
    """The bug this guards against: `find_html` only checking existence would
    silently defeat the whole XML->HTML->body.md+PDF fallback design, since
    callers treat whatever it returns as usable without re-checking."""
    path = tmp_path / f"{tmp_path.name}.fulltext.html"
    filler = "<p>Jump to Content. Dismiss this warning.</p>" * 150
    path.write_text(f"<html><body>{filler}</body></html>", encoding="utf-8")
    assert find_html(tmp_path) is None


# ---------------------------------------------------------------------------
# The landing-page/decoy guard — wiring, not the guard's own logic
# ---------------------------------------------------------------------------

def test_decoy_page_returns_structured_error_not_a_crash(tmp_path):
    """Long enough to clear validate_t2's own byte floors on its own merits,
    so this fails for the reason it claims to, not because it is short."""
    filler = "<p>Jump to Content. Dismiss this warning.</p>" * 150
    path = _write(tmp_path, f"<article>{filler}<table><tr><td>x</td></tr></table></article>")
    result = extract_html_text_with_tables(path)
    assert result.get("error"), "a real decoy signature should have been rejected"
    assert result["tables"] == []
    assert result["n_tables"] == 0


def test_decoy_error_shape_matches_supplements_read_convention():
    """Same {error, unreadable_format, tables: [], ...} shape
    extraction.supplements_read already uses for an unreadable format, so
    existing prompt-level 'record in unchecked' routing needs no new case."""
    from forensic_metascience_ai_toolkit.extraction.html import _validation_error
    from pathlib import Path

    result = _validation_error(Path("x.html"), "paywall/bot-challenge signature: 'test'")
    assert result["error"]
    assert result["unreadable_format"] == ".html"
    assert result["tables"] == []
    assert result["text"] == ""
    assert result["n_tables"] == 0


def test_missing_fetchpdf_degrades_to_not_validated_not_a_crash(tmp_path, monkeypatch):
    """fetchpdf is a sibling-repo dependency; a broken/missing install must
    degrade to "not checked" rather than take extraction down."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "fetchpdf.retrieval.validate" or name.startswith("fetchpdf"):
            raise ImportError("simulated missing fetchpdf")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    path = _write(
        tmp_path,
        "<article>" + "<p>Real body text of the article. " * 200 + "</p>"
        "<table><tr><td>3.7</td></tr></table></article>",
    )
    result = extract_html_text_with_tables(path)
    assert not result.get("error"), result.get("error")
    assert result["n_tables"] == 1


class TestTheDefenceWorksWithoutItsOptionalDependency:
    """The landing-page defence was entirely delegated to `fetchpdf`.

    `fetchpdf` is declared in pyproject as a local file:// path inside one
    developer's home directory, so it cannot install anywhere else. On every
    other machine the import failed and `_validate_not_a_landing_page` returned
    None -- "not validated" -- so the defence was silently INERT for everyone
    who is not its author. Two of this file's own tests were failing on `main`
    for exactly that reason.

    That is worse than having no defence, because the feature is documented as
    present. And unlike other optional checks, whose absence merely costs
    coverage, this one costs a FALSE ACCUSATION: a stub read as full text makes
    every statistic the paper really reported into a 'not reported' finding
    against its authors.
    """

    def test_the_blatant_decoy_is_caught_with_no_dependency(self):
        from forensic_metascience_ai_toolkit.extraction.html import _looks_like_boilerplate
        page = "Jump to Content. Dismiss this warning.\n" * 150
        assert _looks_like_boilerplate(page)

    def test_a_real_article_is_not_refused(self):
        """Over-refusing here means a paper cannot be reviewed at all, so the
        fallback must fire only on the blatant case."""
        from forensic_metascience_ai_toolkit.extraction.html import _looks_like_boilerplate
        body = ("Participants completed the task under three conditions. "
                "Reaction times were recorded to the nearest millisecond. "
                "We analysed the data with a mixed-effects model. " * 40)
        assert _looks_like_boilerplate(body) is None

    def test_an_article_merely_MENTIONING_cookies_is_not_a_decoy(self):
        """Presence is not dominance. A paper about web tracking says 'cookie'
        often and is still a paper."""
        from forensic_metascience_ai_toolkit.extraction.html import _looks_like_boilerplate
        body = ("This study examined how users respond when asked to enable "
                "cookies during checkout. Please enable cookies was shown to "
                "half the sample. " * 30)
        assert _looks_like_boilerplate(body) is None

    def test_too_short_to_judge_is_not_refused(self):
        """The byte floors already handle short pages; guessing here would add
        a refusal on no evidence."""
        from forensic_metascience_ai_toolkit.extraction.html import _looks_like_boilerplate
        assert _looks_like_boilerplate("Jump to Content.") is None
