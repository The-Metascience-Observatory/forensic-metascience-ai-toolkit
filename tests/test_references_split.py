"""The bibliography is severed once, by name, and never enumerated as results.

GREG, 2026-08-16: "extract the references separately. That way this kind of
mistake won't happen."
"""
import json
import pathlib

import pytest

from metascience_agent import completeness as C
from metascience_agent import references as R

CACHES = sorted(pathlib.Path("tests/fixtures/papers/high_value_pdfs_to_run_on").glob(
    "**/.extraction_cache/*.tables.json"))


class TestTheBoundaryIsFoundTwoWays:
    """A heading is not the only signal, and assuming it was is what the first
    cut got wrong: it split every paper that prints `## References` and missed
    all five PNAS papers, which print no heading and number their entries."""

    def test_a_markdown_heading_is_found(self):
        text = ("Body with results. " * 200) + "\n## References\n\nSmith J (1998). A paper.\n"
        s = R.split(text)
        assert s["how"] == "heading"
        assert "## References" in s["references"]
        assert "Body with results." in s["body"]

    def test_a_numbered_list_with_no_heading_is_found(self):
        entries = "\n".join(
            f"{i}. Author{i} AB (19{80 + i}) A title here. Journal {i}:1-10."
            for i in range(1, 12))
        text = ("Body with results. " * 300) + "\n" + entries + "\n"
        s = R.split(text)
        assert s["how"] == "numbered_run"
        assert s["n_entries"] >= 10
        assert s["references"].lstrip().startswith("1. Author1")

    def test_a_lowercase_surname_particle_does_not_move_the_boundary(self):
        """`5. te Nijenhuis J, van Vianen AEM` -- a real entry in PNAS
        0801268105. Requiring a capital dropped it, punched a hole in the
        numbering, and moved the detected start five entries down, leaving part
        of the bibliography in the body."""
        entries = [f"{i}. Author{i} AB (19{80 + i}) A title. Journal {i}:1-10."
                   for i in range(1, 12)]
        entries[4] = "5. te Nijenhuis J, van Vianen AEM (2007) Score gains. Intelligence 35:283-300."
        text = ("Body with results. " * 300) + "\n" + "\n".join(entries) + "\n"
        s = R.split(text)
        assert s["references"].lstrip().startswith("1. Author1"), (
            f"boundary landed at: {s['references'][:60]!r}")

    def test_one_dropped_entry_does_not_move_the_boundary(self):
        """Extraction loses an entry now and then. An exact +1 rule turns that
        into a boundary in the wrong place."""
        entries = [f"{i}. Author{i} AB (19{80 + i}) A title. Journal {i}:1-10."
                   for i in range(1, 12) if i != 4]
        text = ("Body with results. " * 300) + "\n" + "\n".join(entries) + "\n"
        assert R.split(text)["references"].lstrip().startswith("1. Author1")


class TestItRefusesRatherThanGuesses:
    """Cutting where there is no bibliography deletes real results, and nobody
    ever hears about a Results section that silently left the body."""

    def test_no_bibliography_means_the_whole_text_is_body(self):
        text = "Body with results and no reference list at all. " * 50
        s = R.split(text)
        assert s["how"] == "not_found"
        assert s["body"] == text and s["references"] == ""

    def test_a_table_of_contents_does_not_truncate_the_paper(self):
        text = "Contents\n\nReferences\n\n" + ("Body with results. " * 300)
        assert R.split(text)["body"] == text

    def test_a_sentence_mentioning_references_is_not_a_heading(self):
        text = ("Filler. " * 200) + "\nWe compared our references to theirs.\n" + ("More. " * 200)
        assert R.split(text)["how"] == "not_found"

    def test_a_short_numbered_list_is_not_a_bibliography(self):
        """Three numbered items in a Methods section are a procedure."""
        text = ("Body. " * 300) + "\n1. Ames A (1999) x.\n2. Bell B (2000) y.\n"
        assert R.split(text)["how"] == "not_found"

    def test_empty_text_is_handled(self):
        s = R.split("")
        assert s["how"] == "empty" and s["body"] == "" and s["boundary"] is None


@pytest.mark.skipif(not CACHES, reason="corpus not present")
class TestOnTheRealCorpus:
    def test_every_article_has_its_bibliography_severed(self):
        """Every cached ARTICLE must have its reference list found -- this is the
        regression that would silently return.

        Supplements are excluded because most carry no reference list at all, so
        `not_found` is the correct answer for them and asserting otherwise would
        pin a false expectation.
        """
        undetected = []
        for p in CACHES:
            if "_supplementary_info_" in p.name:
                continue
            t = (json.loads(p.read_text()).get("text") or "")
            if R.split(t)["how"] == "not_found":
                undetected.append(p.parent.parent.name)
        assert not undetected, f"no bibliography boundary found in: {undetected}"

    def test_the_known_miss_is_recorded_rather_than_papered_over(self):
        """ONE cached document defeats the detector and it should be named.

        `10.1001--jamanetworkopen.2023.51752` supplement 1 is a 289k-char study
        protocol whose reference list runs to entry 252 in AMA style, but the PDF
        carries interleaved line numbers, so entries are not at line starts
        (`...1989. 97 247. Schmidt, P. ...`) and several sit inside a markdown
        table. No line-anchored pattern reaches them.

        Extending the detector to cover it would mean dropping the line anchor,
        which is the constraint keeping it from firing on ordinary numbered
        prose. The guards in `_is_result` -- DOI context, impossible fractions --
        are what protect this document instead. Recorded so the limit is known
        rather than discovered again.
        """
        hits = [p for p in CACHES if "51752_supplementary_info_1" in p.name]
        if not hits:
            pytest.skip("that supplement is not in this checkout")
        t = json.loads(hits[0].read_text()).get("text") or ""
        assert R.split(t)["how"] == "not_found", (
            "the detector now handles line-numbered protocols -- good. Update "
            "this test and say what changed."
        )

    def test_the_body_never_ends_inside_the_reference_list(self):
        """The PNAS bug: the boundary landed at entry 6, so entries 1-5 stayed
        in the body. Assert the body's tail is not a numbered citation."""
        import re
        bad = []
        for p in CACHES:
            t = (json.loads(p.read_text()).get("text") or "")
            s = R.split(t)
            if s["how"] != "numbered_run":
                continue
            if re.search(r"^\s*\d{1,3}\.\s+\S+.*\(\d{4}\)", s["body"][-400:], re.MULTILINE):
                bad.append(p.parent.parent.name)
        assert not bad, f"body ends inside the bibliography for: {bad}"

    def test_no_doi_is_enumerated_as_a_sample_fraction(self):
        for p in CACHES:
            t = (json.loads(p.read_text()).get("text") or "")
            for it in C._body_items(t):
                raw = it["raw"]
                if "/" in raw:
                    a, _, b = raw.partition("/")
                    if a.strip().isdigit() and b.strip().isdigit():
                        assert int(a) <= int(b), (
                            f"{p.parent.parent.name}: enumerated {raw!r} as a fraction")


class TestTheBibliographyIsTheLastListNotTheLongest:
    """`_numbered_run_start` took the LONGEST ascending run of numbered
    entries. A systematic review's Results carries a numbered list of included
    trials, each citing a year, and it can easily be longer than a short
    bibliography -- so the cut landed on the Results, and the Discussion, the
    pooled estimate and the whole remainder of the paper were returned as
    `references` and never enumerated as reported statistics. `how` said
    `numbered_run` either way, so nothing downstream could tell.
    """

    @staticmethod
    def _review_with_a_numbered_results_list():
        return ("Introduction. " + "Background prose. " * 300 +
                "Results. We summarise the included trials:\n" +
                "".join(f"{i}. Author{i} J (201{i%10}) reported a mean "
                        f"difference of 1.{i} (95% CI 0.1-2.2).\n"
                        for i in range(1, 9)) +
                "\nDiscussion: the pooled estimate was 0.42 (SE 0.11). " +
                "More discussion prose. " * 250 + "\n" +
                "".join(f"{i}. Ref{i} A (200{i}) J Something 200{i};1(1):1-9.\n"
                        for i in range(1, 6)))

    def test_a_numbered_list_in_results_is_not_the_bibliography(self):
        from metascience_agent.references import split
        r = split(self._review_with_a_numbered_results_list())
        assert "Discussion: the pooled estimate" in r["body"]
        assert "reported a mean difference of 1.4" in r["body"]
        assert "Ref1 A (2001)" in r["references"]

    def test_one_bibliography_split_by_dropped_entries_is_still_one(self):
        """Taking the LAST run alone is worse than taking the longest, and
        measurably so: on three cerebrolysin papers it moved the boundary to
        entry 37, entry 18 and entry 11 OF THE BIBLIOGRAPHY, because extraction
        drops the occasional entry and splits one list into several runs. Half
        of a real bibliography was reclassified as body. Runs close together
        are one list -- the three real within-bibliography gaps in that corpus
        are 192, 752 and 1,155 characters."""
        from metascience_agent.references import split
        body = "Introduction. " + "Body prose here. " * 400 + "\n"
        first = "".join(f"{i}. Ref{i} A (200{i%9}) J Something 200{i%9};1(1):1-9.\n"
                        for i in range(1, 11))
        # An entry the pattern cannot match, which ends the run.
        interruption = "te Nijenhuis J, van der Flier H. Score gains. 2013.\n"
        second = "".join(f"{i}. Ref{i} B (201{i%9}) J Other 201{i%9};2(2):2-8.\n"
                         for i in range(12, 22))
        r = split(body + first + interruption + second)
        assert "Ref1 A (2001)" in r["references"], (
            "the boundary landed inside the bibliography")

    def test_the_gap_threshold_is_documented_as_measured(self):
        from metascience_agent import references
        assert references._SAME_LIST_GAP >= 1155, (
            "must exceed the largest observed within-bibliography gap")


class TestABulletedBibliography:
    """docling emits some reference lists as a markdown bullet list --
    `- 55 . Niu, Z. et al.` -- with a dash before the number and a space before
    the point. The anchored pattern saw neither, so the boundary was never found
    and the whole bibliography was enumerated as the paper's own statistics.
    15 of 211 Zotero-corpus papers use this shape."""

    def test_the_bulleted_form_is_recognised(self):
        from metascience_agent.references import split
        body = "Introduction. " + "Body prose here. " * 400 + "\n"
        refs = "".join(
            f"- {i} . Author{i}, A. B. Title of the work. Journal 20{i:02d};1(1):1-9.\n"
            for i in range(1, 12))
        r = split(body + refs)
        assert r["how"] == "numbered_run"
        assert "Author1," in r["references"]
        assert "Body prose here" in r["body"]

    def test_the_plain_form_still_works(self):
        from metascience_agent.references import split
        body = "Introduction. " + "Body prose here. " * 400 + "\n"
        refs = "".join(f"{i}. Author{i} A (200{i%9}) J Something 200{i%9};1(1):1-9.\n"
                       for i in range(1, 12))
        assert split(body + refs)["how"] == "numbered_run"
