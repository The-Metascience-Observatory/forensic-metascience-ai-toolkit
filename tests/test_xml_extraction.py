

class TestATopLevelHeadingIsNotLostWithItsProse:
    """REPORTED BY GREG FROM THE VIEWER, 2026-08-11. The Romano PDF reads

        Method
        Participants and Procedures
        Institutional review board approval was obtained...

    and the extracted text began at `## Participants and Procedures` with no
    `Method` anywhere above it.

    THE MECHANISM. JATS puts a top-level section's prose inside its CHILD
    `<sec>` elements, so `_paragraphs()` on the container returns nothing, and
    `add()` ended `if texts or tables:` -- dropping the container entirely,
    heading and all, while its children survived as `##` headings with no
    parent.

    MEASURED over 71 XML papers: 293 of 1,209 distinct section titles (24%)
    never reached the extracted text, and they were systematically the ones
    that matter -- Methods, Results, Discussion, Materials and Methods,
    Conclusions. After the fix, 163 (13%), and the remainder is a different
    mechanism (structured-abstract sub-sections, footnotes).

    WHY IT MATTERS more than a cosmetic heading: a model that cannot see where
    Methods starts cannot tell a number reported in Methods from the same
    number reported in Results, and that distinction carries much of the
    internal-consistency reasoning.
    """
    import xml.etree.ElementTree as _ET

    JATS = """<article><body>
      <sec><title>Method</title>
        <sec><title>Participants</title><p>Board approval was obtained.</p></sec>
        <sec><title>Measures</title><p>We measured affect.</p></sec>
      </sec>
      <sec><title>Results</title><p>We found things.</p></sec>
      <sec><title>Empty</title></sec>
    </body></article>"""

    def _titles(self):
        import xml.etree.ElementTree as ET
        from metascience_agent.extraction.jats import _Counter, _sections
        root = ET.fromstring(self.JATS)
        return [s["title"] for s in _sections(root, _Counter())]

    def test_the_container_heading_survives(self):
        assert "Method" in self._titles(), (
            "a section whose prose lives in its children is still the paper's "
            "structure")

    def test_it_comes_before_its_children(self):
        t = self._titles()
        assert t.index("Method") < t.index("Participants")

    def test_the_children_are_still_there(self):
        t = self._titles()
        assert "Participants" in t and "Measures" in t

    def test_a_section_with_no_children_and_no_text_is_still_dropped(self):
        """The fix must not start emitting headings over nothing."""
        assert "Empty" not in self._titles()

    def test_the_real_paper_that_reported_it(self):
        import xml.etree.ElementTree as ET
        from pathlib import Path
        from metascience_agent.extraction.jats import _Counter, _sections
        p = (Path(__file__).resolve().parents[1]
             / "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/10.1002--eat.24415.xml")
        if not p.exists():
            import pytest
            pytest.skip("Romano XML not in this checkout")
        titles = [s["title"] for s in _sections(ET.parse(p).getroot(), _Counter())]
        for expected in ("Method", "Results", "Discussion", "Measures"):
            assert expected in titles, f"`{expected}` lost again"


class TestUnsectionedBodyProseIsNotDropped:
    """MEASURED 2026-08-22, `10.15585--mmwr.mm6923e2`.

    34 KB of publisher XML yielded 6,891 characters of text. That report's
    entire Methods and Results -- eleven `<p>` children of `<body>`, about
    7 KB -- sit outside any `<sec>`, and only the Discussion onward is
    sectioned. `walk()` recognised sections and containers and nothing else,
    so the prose was never read; the tool agent recovered it from PDF page
    images instead, and that paper's ledger is the smallest in its batch
    (32 calls against 64-118 for its siblings).
    """

    _MMWR_SHAPED = """<?xml version="1.0"?>
    <article xmlns:xlink="http://www.w3.org/1999/xlink">
      <front><journal-meta><issn>1545-861X</issn></journal-meta>
        <article-meta><title-group><article-title>T</article-title>
        </title-group></article-meta></front>
      <body>
        <p>Thirty-nine percent reported intentionally engaging in at least one
           high-risk practice.</p>
        <p>The median age of respondents was 46 years.</p>
        <sec><title>Discussion</title>
          <p>Approximately one third reported engaging in high-risk
             practices.</p></sec>
      </body>
    </article>"""

    def _text(self, tmp_path, xml: str) -> str:
        from metascience_agent.extraction.jats import extract_xml_text
        f = tmp_path / "a.xml"
        f.write_text(xml, encoding="utf-8")
        return extract_xml_text(f)

    def test_body_paragraphs_outside_every_section_reach_the_text(self, tmp_path):
        text = self._text(tmp_path, self._MMWR_SHAPED)
        assert "Thirty-nine percent" in text
        assert "median age of respondents was 46" in text
        # And the sectioned prose still arrives, exactly once.
        assert text.count("Approximately one third") == 1

    def test_the_heading_does_not_invent_a_section_name(self, tmp_path):
        """"Methods" or "Results" here would be a fabricated `location`."""
        text = self._text(tmp_path, self._MMWR_SHAPED)
        assert "no section heading in the XML" in text
        assert "## Methods" not in text and "## Results" not in text

    def test_sectioned_prose_is_never_emitted_twice(self, tmp_path):
        """The walk must not re-collect what `add()` already read off a sec."""
        xml = """<?xml version="1.0"?>
        <article><front><journal-meta><issn>1</issn></journal-meta></front>
          <body><sec><title>Methods</title>
            <p>A distinctive sentence that appears once in the source.</p>
          </sec></body></article>"""
        text = self._text(tmp_path, xml)
        assert text.count("A distinctive sentence") == 1

    def test_document_order_survives_interleaving(self, tmp_path):
        xml = """<?xml version="1.0"?>
        <article><front><journal-meta><issn>1</issn></journal-meta></front>
          <body>
            <p>FIRST loose paragraph.</p>
            <sec><title>Middle</title><p>MIDDLE sectioned paragraph.</p></sec>
            <p>LAST loose paragraph.</p>
          </body></article>"""
        text = self._text(tmp_path, xml)
        assert text.index("FIRST") < text.index("MIDDLE") < text.index("LAST")


class TestElsevierFullTextIsPublisherMarkupWithAnAbstract:
    """MEASURED 2026-08-22, `10.1016--j.jpsychires.2018.04.010`.

    `paper_text_with_source` returned `xml_derived` and text beginning at
    `## Introduction`. Two consequences: Elsevier full text was stripped of an
    authority it had earned (its root is emitted by no converter), and both of
    that paper's abstract-vs-Results findings shipped
    `quote_verified: "unverified"` because the sentences they quote were not
    in the text we had loaded.
    """

    _ELSEVIER = """<?xml version="1.0"?>
    <full-text-retrieval-response
        xmlns="http://www.elsevier.com/xml/svapi/article/dtd"
        xmlns:ce="http://www.elsevier.com/xml/common/dtd"
        xmlns:dc="http://purl.org/dc/elements/1.1/">
      <coredata><dc:title>T</dc:title></coredata>
      <originalText><doc><serial-item>
        <ce:abstract>
          <ce:abstract-sec>
            <ce:section-title>Results</ce:section-title>
            <ce:simple-para>Mean hippocampal and thalamic volumes were
              significantly reduced in acAN participants.</ce:simple-para>
          </ce:abstract-sec>
        </ce:abstract>
        <ce:sections><ce:section>
          <ce:section-title>Introduction</ce:section-title>
          <ce:para>Anorexia nervosa is a complex disorder.</ce:para>
        </ce:section></ce:sections>
      </serial-item></doc></originalText>
    </full-text-retrieval-response>"""

    def test_the_structured_abstract_reaches_the_text(self, tmp_path):
        from metascience_agent.extraction.jats import extract_xml_text
        f = tmp_path / "a.xml"
        f.write_text(self._ELSEVIER, encoding="utf-8")
        text = extract_xml_text(f)
        assert "thalamic volumes were" in text, (
            "ce:abstract-sec is Elsevier's name for a structured abstract's "
            "section; missing it drops the whole abstract, not a heading")
        assert "Anorexia nervosa is a complex disorder" in text

    def test_the_elsevier_api_root_is_publisher_not_derived(self, tmp_path):
        from metascience_agent.extraction.jats import xml_provenance
        f = tmp_path / "a.xml"
        f.write_text(self._ELSEVIER, encoding="utf-8")
        assert xml_provenance(f) == "publisher"

    def test_a_grobid_tei_is_still_derived(self, tmp_path):
        """The privilege stays narrow: a converter's output earns none of it."""
        from metascience_agent.extraction.jats import xml_provenance
        f = tmp_path / "b.xml"
        f.write_text(
            '<?xml version="1.0"?><TEI xmlns="http://www.tei-c.org/ns/1.0">'
            '<teiHeader><encodingDesc><appInfo><application ident="GROBID"/>'
            "</appInfo></encodingDesc></teiHeader></TEI>", encoding="utf-8")
        assert xml_provenance(f) == "derived"
