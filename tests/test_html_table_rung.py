"""The table walker must read HTML, because the text ladder already does.

MEASURED 2026-09-05: `grep -c -i html src/metascience_agent/prepass.py` returned
0. `paper_tables` checked for XML and, finding none, went straight to the PDF --
so a paper whose best source is HTML had NO tables at all, while
`jats._derive_paper_text` served that same paper's HTML text. Text and tables
named different documents.

On `10.1073--pnas.1211286109` (Moss-Racusin) that cost Table 1's entire
means-and-SDs block, 34 numerals. Recovered here: 36 cells, with the stacked
header `Female target student | Female faculty | Mean` preserved from real
colspan markup, which a PDF reading of the same table does not carry.
"""


import sys

import pytest

from metascience_agent.prepass import _article_html_tables, paper_tables

TABLE = """
<html><body>
<p>%s</p>
<table>
  <thead>
    <tr><th rowspan="2">Measure</th><th colspan="2">Female faculty</th></tr>
    <tr><th>Mean</th><th>SD</th></tr>
  </thead>
  <tbody>
    <tr><td>Competence</td><td>4.01</td><td>0.92</td></tr>
    <tr><td>Hireability</td><td>3.33</td><td>1.07</td></tr>
  </tbody>
</table>
</body></html>
""" % ("filler prose. " * 200)


def _paper(tmp_path, html=TABLE, name="10.1073--pnas.1211286109"):
    d = tmp_path / name
    d.mkdir()
    (d / f"{name}.fulltext.html").write_text(html, encoding="utf-8")
    return d


def test_an_html_paper_yields_its_tables(tmp_path):
    out = _article_html_tables(_paper(tmp_path), [])
    assert out is not None and len(out) == 1
    assert len(out[0]["cells"]) > 0


def test_the_stacked_header_survives(tmp_path):
    """Real colspan/rowspan is the whole reason HTML beats a PDF reading."""
    out = _article_html_tables(_paper(tmp_path), [])
    labels = {c.get("col_label") for c in out[0]["cells"] if c.get("col_label")}
    assert any("Female faculty" in str(l) and "Mean" in str(l) for l in labels)


def test_the_role_axis_is_not_the_format_axis(tmp_path):
    """`html._build_table` sets source="html" (the FORMAT). The walker's
    `source` means article-vs-supplement (the ROLE). Conflating them would make
    a supplement table report as the article's."""
    out = _article_html_tables(_paper(tmp_path), [])
    assert out[0]["source"] == "article"
    assert out[0]["extractor"] == "html"


def test_no_usable_html_returns_None_not_empty(tmp_path):
    """None and [] are different answers: None means fall through to the PDF,
    [] means the HTML IS the paper and has no tables. Returning [] for a paper
    with no HTML would stop the PDF ever being read."""
    d = tmp_path / "10.9999--nothing"
    d.mkdir()
    assert _article_html_tables(d, []) is None


def test_a_decoy_page_supplies_no_tables(tmp_path):
    """The decoy gate applies here too -- a challenge page cannot supply tables
    any more than it can supply text."""
    decoy = ("<html><body><p>Client Challenge JavaScript is disabled in your "
             "browser. Please enable JavaScript to proceed.</p></body></html>")
    assert _article_html_tables(_paper(tmp_path, decoy), []) is None


def test_paper_tables_prefers_html_over_the_pdf(tmp_path):
    """Order must mirror the TEXT ladder (xml > html > pdf), or a finding could
    quote a table the served text does not contain."""
    d = _paper(tmp_path)
    (d / f"{d.name}.pdf").write_bytes(b"%PDF-1.4 stub")
    out = paper_tables(d)
    assert out and all(t.get("extractor") == "html" for t in out)


# ---------------------------------------------------------------------------
# BLOCK STRUCTURE, because two things downstream are built on it
#
# `_flatten_text` collapsed every run of whitespace to a single space, so the
# article arrived as ONE LINE. MEASURED on the PMC rendering of Stern 2014:
# `'## '` occurred 0 times, `sections.map_sections` found ONE section spanning
# the paper, and `scaffold.linear.chunks` produced ONE CHUNK -- the whole-text
# pass that linear reading exists to replace. 18 chunks on the PDF path became
# 1 on the HTML path, silently.
#
# After: 42 headings, 41 sections, 24 chunks, 0 ragged boundaries.
# ---------------------------------------------------------------------------

from metascience_agent.extraction.html import _article_root, extract_html_text_with_tables

STRUCTURED = """
<html><body>
  <nav>Skip to main content</nav>
  <section>Official websites use .gov. A .gov website belongs to an official
     government organization in the United States.</section>
  <article>
    <h1>A Paper Title</h1>
    <h2>Abstract</h2><p>%s</p>
    <h2>Materials and Methods</h2><p>%s</p>
    <h2>Results</h2><p>%s</p>
  </article>
</body></html>
""" % ("abstract prose. " * 40, "methods prose. " * 40, "results prose. " * 40)


def test_headings_become_markers_the_shared_mapper_reads(tmp_path):
    """`## ` is deliberately docling's shape -- a second section convention
    would be a second definition of what a section is."""
    p = tmp_path / "a.fulltext.html"
    p.write_text(STRUCTURED, encoding="utf-8")
    text = extract_html_text_with_tables(p, max_chars=10_000_000)["text"]
    assert text.count("## ") >= 4


def test_blocks_keep_their_boundaries(tmp_path):
    """`linear.chunks` splits an over-long section at a blank line. With none
    present a long section cannot be split at all."""
    p = tmp_path / "a.fulltext.html"
    p.write_text(STRUCTURED, encoding="utf-8")
    text = extract_html_text_with_tables(p, max_chars=10_000_000)["text"]
    assert "\n\n" in text


def test_the_mapper_finds_the_papers_own_sections(tmp_path):
    """`map_sections` names sections; `document._roles_for` is what assigns a
    ROLE to each. Asserting roles here would test the wrong function -- the
    first draft of this test did, and failed against correct code."""
    from metascience_agent.scaffold.document import _roles_for
    from metascience_agent.sections import map_sections
    p = tmp_path / "a.fulltext.html"
    p.write_text(STRUCTURED, encoding="utf-8")
    text = extract_html_text_with_tables(p, max_chars=10_000_000)["text"]
    secs = map_sections(text)
    assert {"abstract", "materials and methods", "results"} <= {
        str(s.get("name")).lower() for s in secs}
    assert {"abstract", "methods", "results"} <= {
        s.get("role") for s in _roles_for(secs)}


def test_page_chrome_stays_out_of_the_text(tmp_path):
    """`_CHROME_TAGS` strips nav/header/footer/aside; NCBI's federal banner is
    in none of them, so it entered both the served text and the numeral floor's
    denominator. Selecting the article root is the positive form of the rule."""
    p = tmp_path / "a.fulltext.html"
    p.write_text(STRUCTURED, encoding="utf-8")
    text = extract_html_text_with_tables(p, max_chars=10_000_000)["text"]
    assert ".gov" not in text
    assert "Skip to main content" not in text


def test_a_page_with_no_article_element_is_unchanged(tmp_path):
    """The root selection can NARROW what is read, never widen it."""
    from lxml import html as LH
    tree = LH.fromstring("<html><body><p>hello</p></body></html>")
    assert _article_root(tree) is tree


def test_a_displayed_equation_is_not_a_table(tmp_path):
    """PMC wraps `<disp-formula>` in a one-cell `<table class="disp-formula">`
    holding an image of the equation. MEASURED on PMC2747164: `n_tables: 1` for
    a paper whose only `<table>` is a formula. Harmless for checking -- a
    zero-cell table offers nothing to check -- and NOT harmless for counting,
    because table counts feed coverage claims."""
    p = tmp_path / "a.fulltext.html"
    p.write_text(
        '<html><body><article><p>%s</p>'
        '<table class="disp-formula p"><tr><td class="formula">'
        '<img src="eq.jpg"></td></tr></table></article></body></html>'
        % ("prose. " * 200), encoding="utf-8")
    assert extract_html_text_with_tables(p, max_chars=10_000_000)["n_tables"] == 0


def test_a_real_image_only_table_is_still_counted(tmp_path):
    """`image_only` exists to RECORD a data table the publisher shipped as a
    picture. Skipping on "has no text cells" would discard it; the rule keys on
    the publisher's own class marker instead."""
    p = tmp_path / "b.fulltext.html"
    p.write_text(
        '<html><body><article><p>%s</p>'
        '<table class="table"><tr><td><img src="t1.jpg"></td></tr></table>'
        '</article></body></html>' % ("prose. " * 200), encoding="utf-8")
    assert extract_html_text_with_tables(p, max_chars=10_000_000)["n_tables"] == 1


# ---------------------------------------------------------------------------
# THE BIBLIOGRAPHY IS NOT THE PAPER'S MEASUREMENTS
#
# The JATS reader has skipped `<ref-list>` from the section walk since before
# the HTML reader existed -- "it carries no checkable statistics and would swamp
# the stage-1 budget". The HTML reader had no such skip, so the SAME paper's
# bibliography was in the served text on one rung and not the other.
#
# MEASURED by hand-classifying 36 unclassified floor numerals drawn in salted
# hash order across the upgraded corpus: 15 (42%) are reference debris -- page
# ranges, volume/issue, DOIs, years. That is the largest single bucket, and it
# inflates `n_total`, the denominator of every "numbers we did not check" claim.
# ---------------------------------------------------------------------------

REFS = """
<html><body><article>
  <h2>Results</h2><p>%s</p>
  <section id="ref-list1" class="ref-list"><h2>References</h2>
    <ol><li>Smith J. Curr Dir Psychol Sci. 2011;20:246-250. doi:10.1037/0033-2909</li>
        <li>Jones A. J Abnorm Psychol. 1999;108:120-133.</li></ol>
  </section>
</article></body></html>
""" % ("results prose. " * 120)


def test_the_reference_list_leaves_the_statistics_text(tmp_path):
    p = tmp_path / "r.fulltext.html"
    p.write_text(REFS, encoding="utf-8")
    text = extract_html_text_with_tables(p, max_chars=10_000_000)["text"]
    assert "246-250" not in text
    assert "10.1037" not in text
    assert "results prose" in text


def test_the_skip_reuses_the_jats_definition(tmp_path):
    """A second copy of "what counts as the reference list" is the drift this
    project keeps finding. `jats._SKIP_SECTIONS` is the one definition."""
    from metascience_agent.extraction.jats import _SKIP_SECTIONS
    assert "ref-list" in _SKIP_SECTIONS


def test_in_text_author_year_citations_are_not_touched(tmp_path):
    """Stern's PMC page keeps 78 year tokens after the strip because Nature uses
    author-year citations IN THE BODY. Those are the paper's own prose; the
    floor classes them `citation_year` rather than leaving them unclassified,
    and removing them would delete text the paper printed."""
    p = tmp_path / "c.fulltext.html"
    p.write_text("<html><body><article><p>%s (Roth, 1988; Russo et al, 2005) more.</p>"
                 "</article></body></html>" % ("prose. " * 150), encoding="utf-8")
    text = extract_html_text_with_tables(p, max_chars=10_000_000)["text"]
    assert "Roth, 1988" in text


@pytest.fixture(autouse=True)
def _builtin_article_gate(monkeypatch):
    """These small fixtures exercise the built-in gate and HTML extraction.

    The optional fetchpdf validator requires full-length articles with populated
    tables. Installing it must not change these focused unit tests. Production
    validation stays enabled; tests/test_html.py covers actual article inputs.
    """
    monkeypatch.setitem(sys.modules, "fetchpdf.retrieval.validate", None)
