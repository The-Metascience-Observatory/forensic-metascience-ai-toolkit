"""XML that a converter built from a PDF is not the marked-up truth.

Throughout this codebase XML means exactly that -- `prepass.paper_tables` says
"it is not an extraction at all, it is the marked-up truth". MEASURED over the
61 evaluation papers shipping publisher XML, glyph debris is ZERO in 61 of 61,
because there is no font layer to corrupt.

A JATS file SYNTHESISED from a PDF earns none of that. ScienceBeam and GROBID
parse with pdfalto, which reads the same text layer that yields `65 /C6 1.17`,
so a derived JATS carries identical corruption inside much better structure.
"""

import pathlib
import tempfile

from metascience_agent.extraction.jats import xml_provenance


def _write(text):
    d = pathlib.Path(tempfile.mkdtemp())
    p = d / "a.xml"
    p.write_text(text, encoding="utf-8")
    return p


class TestProvenanceIsRead:
    def test_publisher_jats_is_recognised(self):
        p = _write("<article><front><journal-meta><journal-id>X</journal-id>"
                   "</journal-meta></front></article>")
        assert xml_provenance(p) == "publisher"

    def test_grobid_tei_is_derived(self):
        p = _write('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader>'
                   '<encodingDesc><appInfo><application ident="GROBID"/>'
                   "</appInfo></encodingDesc></teiHeader></TEI>")
        assert xml_provenance(p) == "derived"

    def test_real_sciencebeam_output_is_not_publisher(self):
        """THE CASE THE FIRST VERSION GOT WRONG, and it is the one that matters.

        I wrote the original fixture myself, with a `sciencebeam` comment in it,
        and it passed. Real ScienceBeam JATS carries NO self-identifying stamp
        at all -- no GROBID string, no TEI namespace, no `pdfalto` -- and it
        DOES emit `<article-meta>`, which was in the publisher list. So the real
        output classified as `publisher`: the exact laundering this function
        exists to prevent, passed by a test I invented.

        This fixture is the shape real output has: article-level structure, and
        none of the journal or publisher identity a production system writes."""
        p = _write('<article xmlns:xlink="http://www.w3.org/1999/xlink" '
                   'article-type="research-article"><front><article-meta>'
                   "<title-group><article-title>A paper</article-title>"
                   "</title-group></article-meta></front></article>")
        assert xml_provenance(p) != "publisher"

    def test_a_stamped_converter_is_derived(self):
        p = _write('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/></TEI>')
        assert xml_provenance(p) == "derived"

    def test_publisher_identity_is_what_counts(self):
        """Article-level structure proves nothing -- reconstructing it is what a
        converter DOES. An ISSN, a publisher name and a DTD declaration are
        things a converter reading a PDF cannot invent."""
        assert xml_provenance(_write(
            "<article><front><article-meta><title-group/></article-meta>"
            "</front></article>")) != "publisher"
        assert xml_provenance(_write(
            "<article><front><journal-meta><issn>1234-5678</issn>"
            "<publisher><publisher-name>X</publisher-name></publisher>"
            "</journal-meta></front></article>")) == "publisher"


class TestItFailsTowardTheWeakerClaim:
    def test_unknown_origin_is_not_publisher(self):
        """Being unable to tell is not evidence of publisher markup."""
        assert xml_provenance(_write("<doc><p>hello 4.2</p></doc>")) == "unknown"

    def test_an_unreadable_file_is_unknown(self):
        assert xml_provenance("/nonexistent/nowhere.xml") == "unknown"

    def test_the_label_never_says_bare_xml(self):
        """`paper_text_with_source` must not return `"xml"` any more -- a caller
        keying off that string would give a derived file publisher privileges."""
        import metascience_agent.extraction.jats as jats
        src = pathlib.Path(jats.__file__).read_text()
        assert 'return text, "xml"' not in src
        assert "xml_publisher" in src and "xml_derived" in src
