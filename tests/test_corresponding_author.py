"""Who to write to, and how far to trust the address.

Greg asked for the corresponding author on the Questions page. The field and the
display row already existed; the EXTRACTION was missing the commonest pattern in
this corpus, so the page rendered "No corresponding author was extracted, so
these have nowhere to go without looking one up" while the answer sat in the
file.

MEASURED on `10.1007--s11064-023-03861-8`: the XML carries ZERO `<corresp>`
elements and ZERO `<email>` elements -- the two things the old extractor looked
for. What it carries instead is an `<author-notes>` footnote reading
"Corresponding author." with the contrib xref-ing it, and two addresses printed
in running text.

THE STAKE, which is why the provenance labels matter as much as the values: this
address is shown to someone about to send an email concerning a possible error
in a colleague's paper. Sending that to the wrong person is a small harm of
exactly the kind this toolkit exists to avoid, so an inferred address must never
be presented like a structured one.
"""
import pathlib
import xml.etree.ElementTree as ET

import pytest

from forensic_metascience_ai_toolkit.extraction import jats

XML = pathlib.Path(__file__).resolve().parents[1] / (
    "tests/fixtures/papers/cerebrolysin_run_2026-08-09/10.1007--s11064-023-03861-8/"
    "10.1007--s11064-023-03861-8.xml")

PMC_STYLE = """<article><front><article-meta>
  <contrib-group>
    <contrib contrib-type="author"><name><surname>Sharma</surname>
      <given-names>Hari Shanker</given-names></name>
      <xref ref-type="author-notes" rid="_fncrsp93pmc__">*</xref></contrib>
    <contrib contrib-type="author"><name><surname>Feng</surname>
      <given-names>Lianyuan</given-names></name></contrib>
  </contrib-group>
  <author-notes><fn id="_fncrsp93pmc__"><label>*</label>
    <p>Corresponding author.</p></fn></author-notes>
</article-meta></front></article>"""

STRUCTURED = """<article><front><article-meta>
  <contrib-group>
    <contrib contrib-type="author" corresp="yes"><name><surname>Rossi</surname>
      <given-names>Ada</given-names></name>
      <address><email>ada.rossi@example.edu</email></address></contrib>
  </contrib-group>
</article-meta></front></article>"""


class TestTheAuthorNotesFootnotePattern:
    def test_the_corresponding_author_is_recovered_from_the_xref(self):
        md = jats.article_metadata(ET.fromstring(PMC_STYLE))
        assert md["corresponding_author"] == "Hari Shanker Sharma"

    def test_it_says_the_name_was_INFERRED_not_declared(self):
        """A footnote match is our reading of prose; `corresp="yes"` is the
        publisher's structured claim. The page must be able to tell them apart
        before it puts an address in front of someone."""
        md = jats.article_metadata(ET.fromstring(PMC_STYLE))
        assert md["corresponding_author_source"] == "author_notes_footnote"

    def test_the_structured_attribute_still_wins_and_is_labelled(self):
        md = jats.article_metadata(ET.fromstring(STRUCTURED))
        assert md["corresponding_author"] == "Ada Rossi"
        assert md["corresponding_email"] == "ada.rossi@example.edu"
        assert md["corresponding_author_source"] == "structured"

    def test_the_wrong_author_is_not_picked(self):
        """Only the contrib that xrefs the footnote. Matching any author would
        put a colleague's name on our email."""
        md = jats.article_metadata(ET.fromstring(PMC_STYLE))
        assert md["corresponding_author"] != "Lianyuan Feng"

    def test_a_footnote_that_is_not_about_correspondence_is_ignored(self):
        xml = PMC_STYLE.replace("Corresponding author.", "Contributed equally.")
        md = jats.article_metadata(ET.fromstring(xml))
        assert md["corresponding_author"] == ""
        assert md["corresponding_author_source"] == ""

    def test_no_authors_at_all_is_not_a_crash(self):
        md = jats.article_metadata(ET.fromstring(
            "<article><front><article-meta/></front></article>"))
        assert md["corresponding_author"] == ""


class TestTheEmailPrintedInRunningText:
    """Last resort, and it must announce itself as one."""

    def test_an_address_matching_the_surname_is_reported_as_matched(self):
        e, conf = jats.corresponding_email_from_text(
            "Correspondence to Sharma@surgsci.uu.se, Uppsala.", "Hari Shanker Sharma")
        assert e == "Sharma@surgsci.uu.se"
        assert conf == "surname_match"

    def test_an_address_that_matches_nothing_is_flagged_unverified(self):
        """Offered, but never as though it were confirmed. The reader is about
        to email a stranger about a suspected error."""
        e, conf = jats.corresponding_email_from_text(
            "Enquiries: journal-office@publisher.com", "Hari Shanker Sharma")
        assert e == "journal-office@publisher.com"
        assert conf == "unverified"

    def test_the_matching_address_is_preferred_over_an_earlier_one(self):
        e, conf = jats.corresponding_email_from_text(
            "office@publisher.com and also Sharma@surgsci.uu.se", "H S Sharma")
        assert e == "Sharma@surgsci.uu.se" and conf == "surname_match"

    def test_no_email_returns_empty_rather_than_a_guess(self):
        assert jats.corresponding_email_from_text("no addresses here", "X") == ("", "")
        assert jats.corresponding_email_from_text(None, None) == ("", "")

    def test_it_never_invents_a_NAME_from_an_address(self):
        """The function returns only an address. Deriving "Sharma" from
        `Sharma@surgsci.uu.se` and presenting it as the corresponding author
        would be inventing a person from a string."""
        assert isinstance(jats.corresponding_email_from_text("a@b.co"), tuple)
        assert len(jats.corresponding_email_from_text("a@b.co")) == 2


class TestAgainstTheRealPaper:
    """The artefact that motivated the change."""

    def _md(self):
        if not XML.exists():
            pytest.skip("archived XML not present in this checkout")
        return ET.fromstring(XML.read_text(errors="ignore"))

    def test_the_old_extractor_had_nothing_to_find(self):
        """Both branches that existed key on markup this file does not contain,
        which is why the page said the address was unrecoverable."""
        raw = XML.read_text(errors="ignore") if XML.exists() else pytest.skip("no XML")
        assert "<corresp" not in raw
        assert "<email" not in raw

    def test_the_answer_was_recoverable_all_along(self):
        md = jats.article_metadata(self._md())
        assert md["corresponding_author"] == "Hari Shanker Sharma"
        assert md["corresponding_author_source"] == "author_notes_footnote"

    def test_and_so_was_the_address(self):
        raw = XML.read_text(errors="ignore") if XML.exists() else pytest.skip("no XML")
        e, conf = jats.corresponding_email_from_text(raw, "Hari Shanker Sharma")
        assert e == "Sharma@surgsci.uu.se"
        assert conf == "surname_match"
