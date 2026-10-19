"""A blinding layer that cannot be bypassed, proven against the real corpus.

The guard-that-cannot-fire pattern has been found four times in this codebase in
a week, and a blinding layer is the easiest possible instance of it: it is
trivially testable in isolation and trivially bypassed in production, because
the sweep prompt tells the model to `Read body.md` and `Read` passes through no
code here. So most of what follows tests the ARCHITECTURE -- that the unblinded
bytes are unreachable -- rather than the scrubber's regexes.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from metascience_agent.blinding import (
    ALLOWED_SUFFIXES,
    BlindedPaper,
    audit_ledger,
    materialize,
    materialize_corpus,
    opaque_id,
    scrub_text,
    verify,
)
from metascience_agent.evaluation.corpus_run import paper_slug, resolve_paper_dir
from metascience_agent.evaluation.harness import repo_root
from metascience_agent.registry import SPECS
from metascience_agent.paper_ids import doi_dirname

CANARY = "ZZQCANARYZZQ"

# The EPMC property block, verbatim in shape. `is-retracted` carries `no` here --
# a control -- and the two flags beside it separate the classes perfectly while
# containing no retraction vocabulary at all.
CUSTOM_META = (
    "<custom-meta-group>"
    "<custom-meta><meta-name>is-retracted</meta-name><meta-value>no</meta-value></custom-meta>"
    "<custom-meta><meta-name>display-pdf</meta-name><meta-value>yes</meta-value></custom-meta>"
    "<custom-meta><meta-name>pmc-prop-has-pdf</meta-name><meta-value>yes</meta-value>"
    "</custom-meta></custom-meta-group>"
)


def build_canary(tmp_path: Path) -> Path:
    """A paper directory carrying the label on every channel found in the corpus."""
    src = tmp_path / "10.1234--retracted-thing"
    (src / "forensic_review_specificity").mkdir(parents=True)
    (src / "figures").mkdir()

    (src / "body.md").write_text(
        "RETRACTED ARTICLE\n\n"
        f"We measured {CANARY} in 40 rats (M = 4.61, SD = 1.02).\n"
        "This article has been retracted. See the notice for details.\n"
        "Patients were withdrawn from the drug after the retraction of the scapula.\n"
    )
    (src / "abstract.md").write_text("RETRACTED: An abstract.\n")
    (src / "paper.xml").write_text(
        '<?xml version="1.0"?><article article-type="retraction">'
        "<front><article-meta>"
        "<title-group><article-title>RETRACTED ARTICLE: A Study of Things"
        "</article-title></title-group>"
        '<related-article related-article-type="retraction-forward" '
        'xlink:href="10.1/notice"/>'
        f"{CUSTOM_META}"
        "</article-meta></front>"
        f"<body><p>The mean was 4.61 and {CANARY} was observed.</p>"
        "<p>See also Findings of Research Misconduct, Fed. Regist.</p></body>"
        "<back><notes><p>This article has been retracted.</p></notes></back></article>"
    )
    # Prior run output: our own verdict, inside the corpus, in allowlisted markdown.
    (src / "forensic_review_specificity" / "report.md").write_text(
        "verdict: untrustworthy. The article is published as RETRACTED; "
        "the second author is a known case.\n"
    )
    (src / "provenance.json").write_text(json.dumps({"is_retracted_crossref": True}))
    (src / "figures" / "page_001.png").write_bytes(b"\x89PNG\r\n\x1a\n fake pixels")
    (src / "paper.pdf").write_bytes(b"%PDF-1.4 fake")
    (src / "RETRACTION_notice.txt").write_text("a notice")
    return src


class TestTheCanaryComesOutClean:
    @pytest.fixture
    def blinded(self, tmp_path) -> BlindedPaper:
        return materialize(build_canary(tmp_path), tmp_path / "out")

    def test_no_blocking_marker_survives_anywhere(self, blinded):
        assert blinded.residual == [], blinded.residual

    def test_the_real_content_survives(self, blinded):
        """Blinding that destroys the numbers would pass every test above."""
        body = (blinded.blinded_dir / "body.md").read_text()
        assert CANARY in body and "4.61" in body and "SD = 1.02" in body

    def test_pdf_png_and_json_are_never_copied(self, blinded):
        copied = " ".join(blinded.files_copied)
        assert ".pdf" not in copied and ".png" not in copied and ".json" not in copied

    def test_prior_run_output_is_not_copied(self, blinded):
        """Our own earlier verdict, sitting in the corpus, in allowlisted markdown."""
        assert not any("forensic_review" in f for f in blinded.files_copied)
        assert any("forensic_review" in s for s in blinded.files_skipped)

    def test_a_filename_carrying_the_label_is_renamed(self, blinded):
        assert not any("RETRACTION" in f.upper() for f in blinded.files_copied)

    def test_the_source_is_never_mutated(self, tmp_path):
        src = build_canary(tmp_path)
        before = (src / "body.md").read_text()
        materialize(src, tmp_path / "out")
        assert (src / "body.md").read_text() == before

    def test_the_opaque_id_does_not_contain_the_source(self, blinded):
        assert "retracted" not in blinded.paper_id.lower()
        assert "1234" not in blinded.paper_id


class TestTheSubtleMetadataChannel:
    """The channel a "retract" scrubber leaves behind.

    `display-pdf` and `pmc-prop-has-pdf` separate fraud from control perfectly
    across the corpus -- retracted papers get their PDFs suppressed -- and
    neither string contains any retraction vocabulary. Removing the whole
    custom-meta block is the only thing that closes it.
    """

    def test_the_whole_block_goes_even_with_no_retraction_word_in_it(self):
        xml = ("<article><front>"
               "<custom-meta-group><custom-meta><meta-name>display-pdf</meta-name>"
               "<meta-value>no</meta-value></custom-meta>"
               "<custom-meta><meta-name>pmc-prop-has-pdf</meta-name>"
               "<meta-value>no</meta-value></custom-meta></custom-meta-group>"
               "</front><body><p>Mean 3.2</p></body></article>")
        cleaned, _ = scrub_text(xml)
        assert "display-pdf" not in cleaned
        assert "pmc-prop-has-pdf" not in cleaned
        assert "Mean 3.2" in cleaned

    def test_an_ori_notice_citation_carries_no_retraction_word_and_still_goes(self):
        cleaned, _ = scrub_text("See Findings of Research Misconduct, 80 Fed. Regist.")
        assert "Misconduct" not in cleaned


class TestTheAuditIsNotVacuous:
    def test_a_planted_marker_is_caught(self, tmp_path):
        d = tmp_path / "blinded"
        d.mkdir()
        (d / "body.md").write_text("This article has been retracted.")
        blocking, _ = verify(d)
        assert blocking

    def test_a_clean_file_with_a_dirty_name_is_not_blind(self, tmp_path):
        d = tmp_path / "blinded"
        d.mkdir()
        (d / "retracted_article.md").write_text("nothing to see")
        blocking, _ = verify(d)
        assert any("PATH" in b for b in blocking)

    def test_ordinary_prose_is_reviewed_not_blocked(self, tmp_path):
        """Measured false-positive traps from the real corpus.

        A control says "stipulations are hard to retract", another describes
        "retraction of the scapula", and seven describe patients withdrawn from a
        drug. Blocking on the stem would exclude honest papers for using a word
        -- and because 27 of the 29 papers a stem-blocker excluded were controls,
        the exclusion itself would have leaked the label.
        """
        d = tmp_path / "blinded"
        d.mkdir()
        (d / "body.md").write_text(
            "Stipulations are hard to retract. We measured retraction of the "
            "scapula. Four patients were withdrawn from the drug."
        )
        blocking, review = verify(d)
        assert blocking == []
        assert review

    def test_unreviewed_is_not_clean(self, tmp_path):
        bp = BlindedPaper(source=Path("s"), blinded_dir=Path("d"), paper_id="p",
                          needs_review=["something"])
        assert not bp.clean and not bp.excluded


class TestNothingCanRouteAroundIt:
    def test_every_byte_source_param_is_known_to_this_test(self):
        """The assertion that catches the tool added six months from now.

        Blinding works by making unblinded bytes unreachable by name, so the set
        of parameters that NAME a byte source is the surface it has to cover. A
        new tool with a novel path parameter fails here and has to be considered
        deliberately rather than silently inheriting the guarantee.
        """
        found = {(s.name, p.name) for s in SPECS for p in s.params
                 if p.name.endswith("_path") or p.name in {"path", "out_dir"}}
        assert found == {
            ("extract_figures", "pdf_path"), ("extract_figures", "out_dir"),
            ("detect_raw_duplication", "path"), ("extract_pdf", "pdf_path"),
            ("extract_xml", "xml_path"), ("get_table", "xml_path"),
            ("extract_html", "html_path"), ("extract_supplement", "path"),
            # Reads the same supplement bytes as `extract_supplement`, one
            # sheet at a time, and is governed by the same blinding rule: a
            # blinded run materialises no file it may not read.
            ("get_supplement_table", "path"),
            ("statcheck", "pdf_path"),
            # CLI-only (stages=frozenset()): the model cannot call it at all,
            # and even outside blinding it is covered by the same fact as
            # statcheck -- a blinded run materialises no PDF (".pdf" is not
            # in ALLOWED_SUFFIXES), so there is nothing for the harvest to
            # open. out_dir only WRITES panel PNGs derived from that
            # (nonexistent) input.
            ("analyze_paper_images", "pdf_path"),
            ("analyze_paper_images", "out_dir"),
        }, sorted(found)

    def test_the_tools_that_read_pdfs_have_no_pdf_to_read(self):
        """`statcheck(pdf_path)` extracts with its OWN reader, bypassing
        `extraction/`, and page renders carry the watermark as pixels. Both are
        closed by the same fact: blinded mode materializes no PDF."""
        assert ".pdf" not in ALLOWED_SUFFIXES
        assert ".html" not in ALLOWED_SUFFIXES

    def test_the_ledger_audit_catches_a_read_outside_the_root(self, tmp_path):
        root = tmp_path / "blinded"
        (root / "paper_x").mkdir(parents=True)
        ledger = [
            {"name": "Read", "arguments": {"file_path": str(root / "paper_x" / "body.md")}},
            {"name": "Read", "arguments": {"file_path": str(tmp_path / "manifest.csv")}},
        ]
        escapes = audit_ledger(ledger, root)
        assert len(escapes) == 1
        assert "manifest.csv" in escapes[0]

    def test_the_id_map_may_not_live_beside_the_papers(self, tmp_path):
        src = build_canary(tmp_path)
        with pytest.raises(ValueError, match="the model can Read it"):
            materialize_corpus([src], tmp_path / "out", tmp_path / "out" / "map.json")

    def test_the_id_map_is_written_when_it_is_somewhere_safe(self, tmp_path):
        src = build_canary(tmp_path)
        m = tmp_path / "analyst" / "map.json"
        papers = materialize_corpus([src], tmp_path / "out", m)
        assert json.loads(m.read_text()) == {papers[0].paper_id: str(src)}


class TestTheRealCorpus:
    """The measurement that matters: does it hold on the actual files?"""

    @pytest.fixture(scope="class")
    def results(self, tmp_path_factory):
        root = repo_root() / "eval" / "ground_truth"
        out = tmp_path_factory.mktemp("blinded")
        rows = list(csv.DictReader(open(root / "manifest.csv", encoding="utf-8")))
        got = []
        for r in rows:
            d = resolve_paper_dir(root / "papers", r["doi"])
            if d is not None:
                got.append((r["label"], materialize(d, out)))
        return got

    def test_the_corpus_is_present(self, results):
        assert len(results) == 78

    def test_no_paper_is_excluded_by_a_blocking_marker(self, results):
        bad = [(lab, bp.source.name, bp.residual[:2]) for lab, bp in results if bp.excluded]
        assert bad == [], bad

    def test_exclusion_does_not_itself_leak_the_label(self, results):
        """Whatever the blinder rejects must not correlate with the answer.

        Before the custom-meta fix this failed loudly: a stem-based audit blocked
        27 of 48 controls and 2 of 30 frauds, so "was it excluded?" was a better
        classifier than anything the tools compute.
        """
        held = {"fraud": 0, "control": 0}
        for lab, bp in results:
            if not bp.clean:
                held[lab] += 1
        n = {"fraud": 30, "control": 48}
        rate = {k: held[k] / n[k] for k in held}
        assert abs(rate["fraud"] - rate["control"]) < 0.15, (held, rate)

    def test_the_fifteen_fraud_xmls_lose_their_markers(self, results):
        rows = {paper_slug(r["doi"]): r
                for r in csv.DictReader(
                    open(repo_root() / "eval" / "ground_truth" / "manifest.csv",
                         encoding="utf-8"))}
        n = 0
        for lab, bp in results:
            if lab != "fraud" or rows[bp.source.name]["has_fulltext_xml"] != "yes":
                continue
            n += 1
            assert bp.residual == [], (bp.source.name, bp.residual[:3])
        assert n == 15

    def test_no_file_is_gutted_by_an_over_matching_rule(self, results):
        """The guard for the bug that produced three empty papers.

        A line-anchored rule met single-line JATS and deleted whole documents.
        Downstream that reads as "this paper has no content" -- our failure in
        the grammar of a claim about the paper.
        """
        anomalies = [(bp.source.name, bp.anomalies) for _, bp in results if bp.anomalies]
        assert anomalies == [], anomalies

    def test_papers_that_do_have_text_keep_it(self, results):
        sizes = [self._chars(bp) for _, bp in results if bp.files_copied]
        assert len([s for s in sizes if s > 2000]) >= 60
        assert max(sizes) > 50_000

    def test_blinded_emptiness_predicts_the_label_perfectly(self, results):
        """Measured, and it is the strongest confound in the corpus.

        Blinding cannot touch a PDF: the two PLOS frauds carry a red RETRACTED
        stamp as vector art on every page, invisible to text extraction and
        instantly legible to a vision model. So blinded mode ships no PDF, and
        every paper whose only artefact was a PDF arrives with nothing.

        The result is that 15 of 30 fraud papers have no analysable content and
        0 of 48 controls do. "Did this paper arrive empty?" is a perfect
        classifier that reads no statistics at all. This test pins the number so
        it cannot drift silently; it is not a pass, it is a documented defect of
        the corpus, and PREREGISTRATION.md has to carry it.
        """
        empty = {"fraud": 0, "control": 0}
        for lab, bp in results:
            if self._chars(bp) < 2000:
                empty[lab] += 1
        assert empty == {"fraud": 15, "control": 0}, empty

    @staticmethod
    def _chars(bp) -> int:
        return sum(len((bp.blinded_dir / f).read_text(errors="replace"))
                   for f in bp.files_copied)


def test_opaque_id_is_stable_and_not_reversible():
    a, b = opaque_id("10.1/xyz"), opaque_id("10.1/xyz")
    assert a == b and a != opaque_id("10.1/abc")
    assert a.startswith("paper_") and len(a) == len("paper_") + 12


class TestIdentityBlindingNotJustMarkerBlinding:
    """Marker-blinding is not identity-blinding, and conflating them voids the
    measurement the blinding exists to protect.

    Found by a hostile-reviewer pass, 2026-08-10. After a `materialize` that
    reported ZERO surviving retraction markers, 10.1038/srep12770 still carried
    its DOI twice, "Steenbergen" 5 times, "Colzato" 6 times and the affiliation
    city 6 times -- and shipped the DOI as its own FILENAME, which the model is
    told to Read. Across all 78 corpus papers the committed pipeline failed its
    own identity audit on 63 of 63 non-empty papers, 183 hits, every one a DOI
    token in the path.
    """

    SRC = "eval/ground_truth/papers/10.1038--srep12770"

    def _chain(self, tmp_path):
        from pathlib import Path
        from metascience_agent import blinding
        src = Path(self.SRC)
        bp = blinding.materialize(src, tmp_path)
        ids = blinding.derive_identifiers(src)
        blinding.scrub_identity(bp.blinded_dir, ids)
        return bp, ids

    def test_the_filename_no_longer_carries_the_doi(self, tmp_path):
        from metascience_agent import blinding
        from pathlib import Path
        bp = blinding.materialize(Path(self.SRC), tmp_path)
        names = [p.name for p in bp.blinded_dir.rglob("*") if p.is_file()]
        assert names, "nothing copied"
        for n in names:
            assert "srep12770" not in n and "10.1038" not in n, n
            assert n.startswith(bp.paper_id) or Path(n).stem in {"body", "abstract"}

    def test_identity_is_gone_by_an_audit_that_derives_its_own_targets(self, tmp_path):
        from metascience_agent import blinding
        bp, ids = self._chain(tmp_path)
        assert len(ids) > 20, "identifiers must come from the document, not a manifest"
        assert blinding.identity_residue(bp.blinded_dir, ids) == []
        text = "".join(p.read_text(errors="replace")
                       for p in bp.blinded_dir.rglob("*") if p.is_file())
        for leak in ("Steenbergen", "Colzato", "srep12770", "Leiden"):
            assert leak.lower() not in text.lower(), leak

    def test_pub_history_goes_with_its_retraction_timestamp(self, tmp_path):
        """`history` never matched `<pub-history>`, so the blinding deleted the
        retraction's WORDS and shipped its DATE. The release-to-last-change gap
        alone separated the classes at AUC 0.785 (p = 0.038)."""
        from metascience_agent import blinding
        bp, _ = self._chain(tmp_path)
        text = "".join(p.read_text(errors="replace")
                       for p in bp.blinded_dir.rglob("*") if p.is_file())
        for tag in ("<pub-history", "pmc-last-change", "pmc-release",
                    "<issue-id", "<article-version"):
            assert tag not in text, tag

    def test_the_paper_itself_survives(self, tmp_path):
        """Blinding must not redact the evidence. An earlier version replaced
        'GABA' 103 times because the word appears in the title."""
        from metascience_agent import blinding
        bp, _ = self._chain(tmp_path)
        text = "".join(p.read_text(errors="replace")
                       for p in bp.blinded_dir.rglob("*") if p.is_file())
        assert text.count("GABA") > 50
        assert len(text) > 20_000


class TestRecognitionDetectorActuallyFires:
    """`recognition_hits` is the stated answer to the one risk input-blinding
    cannot remove -- a model recognising a famous paper from its content. Its
    retraction-vocabulary tier was DEAD: `BLOCKING_TERMS` are regex patterns and
    were tested as literal substrings, so 8 of 10 could never match English.
    Measured before the fix, the sentence below returned []."""

    IDS = {"author": "Laura Steenbergen", "doi": "10.1038/srep12770"}

    def test_it_catches_a_model_stating_the_status(self):
        from metascience_agent.blinding import recognition_hits
        hits = recognition_hits(
            "I recall that this article has been retracted following an ORI "
            "investigation.", self.IDS)
        assert hits, "the tier that voids a run for stated recognition must fire"

    def test_it_catches_a_paraphrase_and_a_named_author(self):
        from metascience_agent.blinding import recognition_hits
        assert recognition_hits("This is the withdrawn GABA study.", self.IDS)
        assert recognition_hits("Consistent with Steenbergen's design.", self.IDS)

    def test_ordinary_forensic_prose_is_not_flagged(self):
        """A detector that fires on normal output would be turned off."""
        from metascience_agent.blinding import recognition_hits
        assert recognition_hits(
            "Table 2 reports a mean of 4.2, GRIM-inconsistent at n = 30 for one "
            "decimal place.", self.IDS) == []


class TestTheManifestResolvesOnACaseSensitiveFILESYSTEM:
    """FOUND BY RUNNING THE SUITE IN A PRISTINE CHECKOUT ON EXT4, 2026-08-13.

    `TestTheRealCorpus` asserted `len(results) == 78` and got 76 there while
    passing on `/mnt/c`. Two manifest rows carry the DOI as the publisher
    prints it -- `10.2147/TCRM.S15812`, `10.2147/TCRM.S43811` -- and every
    directory on disk is lowercase, because the fetcher that made them
    lowercases. A Windows filesystem folds the case and hides it; ext4 does
    not, so on any Linux collaborator's machine `evaluation/corpus_run` filed
    two present papers as `papers_missing_on_disk` and evaluated 76.

    THIS TEST COMPARES STRINGS, NOT FILESYSTEM EXISTENCE, so it fails on the
    case-insensitive filesystem too. A check that asks the filesystem whether a
    path exists cannot detect a bug whose entire nature is that the filesystem
    answers too generously.
    """

    def test_every_manifest_doi_maps_onto_a_directory_that_is_actually_there(self):
        import csv as _csv
        root = repo_root() / "eval" / "ground_truth"
        on_disk = {p.name for p in (root / "papers").iterdir() if p.is_dir()}
        with open(root / "manifest.csv", encoding="utf-8") as fh:
            wanted = {doi_dirname(r["doi"]) for r in _csv.DictReader(fh)}
        assert not (wanted - on_disk), (
            "manifest rows with no directory of that exact name: "
            f"{sorted(wanted - on_disk)}")

    def test_the_mapping_is_the_one_the_fetcher_used(self):
        """Uppercase in, lowercase out -- DOIs are case-insensitive by
        specification, and the producer of the directories lowercases."""
        assert doi_dirname("10.2147/TCRM.S15812") == "10.2147--tcrm.s15812"
        assert doi_dirname(" 10.1038/S41537-025-00576-3 ") == "10.1038--s41537-025-00576-3"

    def test_nobody_spells_the_mapping_themselves(self):
        """Five hand-rolled copies is how two of them came to disagree."""
        root = repo_root()
        # SPLIT so the detector does not match its own source line. The first
        # cut flagged itself -- this repository's habit of building a tool that
        # reproduces the defect it is hunting (LESSONS #7).
        needle = 'replace("/", ' + '"--")'
        offenders = []
        for p in list((root / "src").rglob("*.py")) + list((root / "eval").rglob("*.py")) \
                + list((root / "tests").rglob("*.py")):
            if p.name == "paper_ids.py":
                continue
            for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
                if needle in line and "doi" in line.lower():
                    offenders.append(f"{p.relative_to(root)}: {line.strip()}")
        assert not offenders, offenders
