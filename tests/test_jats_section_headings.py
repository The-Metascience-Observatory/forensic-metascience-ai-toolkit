"""A top-level heading must not be lost with the prose it does not own.

REPORTED BY GREG FROM THE VIEWER, 2026-08-11. The Romano PDF reads

    Method
    Participants and Procedures
    Institutional review board approval was obtained...

and the extracted text began at `## Participants and Procedures`, with no
`Method` anywhere above it.

THE MECHANISM. JATS puts a top-level section's prose inside its CHILD `<sec>`
elements, so `_paragraphs()` on the container returns nothing of its own, and
`_sections`' `add()` ended `if texts or tables:` -- which dropped the container
entirely, heading and all, while its children survived as `##` headings with no
parent above them.

MEASURED over the 71 XML papers in this checkout: 293 of 1,209 distinct section
titles (24%) never reached the extracted text, and they were systematically the
ones that matter -- Methods, Results, Discussion, Materials and Methods,
Conclusions. After the fix: 163 (13%). The remainder is a DIFFERENT mechanism
(structured-abstract sub-sections, whose text is captured but flattened into one
`Abstract` blob, plus genuinely contentless Footnotes sections) and is tracked
separately.

WHY IT MATTERS more than a cosmetic heading: a model that cannot see where the
Methods section starts cannot tell a number reported in Methods from the same
number reported in Results, and that distinction carries much of the
internal-consistency reasoning this toolkit does.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from metascience_agent.extraction.jats import _Counter, _sections

REPO = Path(__file__).resolve().parents[1]

JATS = """<article><body>
  <sec><title>Method</title>
    <sec><title>Participants</title><p>Board approval was obtained.</p></sec>
    <sec><title>Measures</title><p>We measured affect.</p></sec>
  </sec>
  <sec><title>Results</title><p>We found things.</p></sec>
  <sec><title>Empty</title></sec>
</body></article>"""


def _titles(xml: str) -> list[str]:
    return [s["title"] for s in _sections(ET.fromstring(xml), _Counter())]


class TestTheContainerHeadingSurvives:
    def test_it_is_present(self):
        assert "Method" in _titles(JATS), (
            "a section whose prose lives in its children is still the paper's "
            "structure, and dropping it leaves the children parentless")

    def test_it_comes_before_its_children(self):
        t = _titles(JATS)
        assert t.index("Method") < t.index("Participants")

    def test_the_children_are_still_there(self):
        t = _titles(JATS)
        assert "Participants" in t and "Measures" in t

    def test_the_container_carries_no_invented_prose(self):
        """Emitting the heading must not duplicate the children's text under
        the parent -- that would double every Methods paragraph and inflate
        every character-offset the click-to-source sync depends on."""
        secs = _sections(ET.fromstring(JATS), _Counter())
        method = next(s for s in secs if s["title"] == "Method")
        assert method["texts"] == []


class TestItDoesNotStartEmittingHeadingsOverNothing:
    def test_a_leaf_section_with_no_text_is_still_dropped(self):
        assert "Empty" not in _titles(JATS)

    def test_a_container_with_only_empty_children_still_yields_its_heading(self):
        """Borderline and deliberate: the heading is real structure even when
        every child turns out to be empty. The alternative -- inspecting
        descendants for text before deciding -- would drop a heading whose
        children hold only tables."""
        xml = ("<article><body><sec><title>Method</title>"
               "<sec><title>Sub</title></sec></sec></body></article>")
        assert "Method" in _titles(xml)


class TestTheRealPaperThatReportedIt:
    def test_romano_keeps_its_structural_headings(self):
        p = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/10.1002--eat.24415.xml"
        if not p.exists():
            pytest.skip("Romano XML not in this checkout")
        titles = [s["title"] for s in _sections(ET.parse(p).getroot(), _Counter())]
        for expected in ("Method", "Results", "Discussion", "Measures"):
            assert expected in titles, f"`{expected}` lost again"

    def test_method_precedes_participants_and_procedures(self):
        """The exact ordering in the screenshot Greg sent."""
        p = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415/10.1002--eat.24415.xml"
        if not p.exists():
            pytest.skip("Romano XML not in this checkout")
        titles = [s["title"] for s in _sections(ET.parse(p).getroot(), _Counter())]
        assert titles.index("Method") < titles.index("Participants and Procedures")


class TestTheCorpusRatchet:
    """MEASURED 2026-08-11: 163 of 1,209 titles are still lost, to a different
    mechanism. Pinned so the number can only improve."""

    MAX_LOST_SHARE = 0.14

    def test_section_title_loss_has_not_got_worse(self):
        import glob
        from metascience_agent.extraction.jats import _local, _section_title

        tot = kept = 0
        for x in glob.glob(str(REPO / "**/*.xml"), recursive=True):
            if "scratchpad" in x or "cerebrolysin" in x:
                continue
            try:
                root = ET.parse(x).getroot()
                have = {s["title"] for s in _sections(root, _Counter())}
            except Exception:  # noqa: BLE001
                continue
            names: list[str] = []

            def walk(el):
                for ch in el:
                    if _local(ch.tag) in ("sec", "section"):
                        try:
                            t = _section_title(ch, _Counter())
                            if t:
                                names.append(t)
                        except Exception:  # noqa: BLE001
                            pass
                        walk(ch)
                    else:
                        walk(ch)
            walk(root)
            if not names:
                continue
            tot += len(set(names))
            kept += len(set(names) & have)
        if not tot:
            pytest.skip("no XML papers in this checkout")
        lost = (tot - kept) / tot
        assert lost <= self.MAX_LOST_SHARE, (
            f"{tot - kept} of {tot} section titles ({lost:.0%}) are lost in "
            f"extraction, above the pinned {self.MAX_LOST_SHARE:.0%}. Headings "
            "are how the model knows which section a number was reported in.")
