"""Persisted anchors (docs/specs/anchors.md): the annotator's contract.

The load-bearing case is the TYPOGRAPHY-MANGLED known-positive: a quote
copied from XML (curly quotes, the fi ligature, a soft hyphen, an en-dash)
must still get PDF boxes via the tier-2 word-alignment bridge — and the test
proves the tier is what did it by disabling it and watching the anchor
degrade. A guard that cannot fail is indistinguishable from a broken one
(LESSONS #4).
"""

import copy
import json

import pytest

fitz = pytest.importorskip("fitz")

from metascience_agent import anchors

PAGE1 = (
    "Methods\n"
    "The quick brown fox jumps over the lazy dog repeatedly.\n"
    "We measured efficacy in the field over twenty-five trials with care."
)
PAGE2 = "Table 2. Mean 3.53 (SD 0.71), n = 30, p = 0.049 in the second arm."

# The page-1 sentence with XML-copy typography: the fi ligature in "field",
# a soft hyphen inside "measured", an en-dash in "twenty-five". search_for
# on the raw string misses all of these; the folded tokens are identical.
MANGLED = "We mea­sured efficacy in the ﬁeld over twenty–five trials with care."


@pytest.fixture(scope="module")
def paper(tmp_path_factory):
    d = tmp_path_factory.mktemp("anchors_paper")
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in PAGE1.split("\n"):
        page.insert_text((72, y), line)
        y += 18
    page2 = doc.new_page()
    page2.insert_text((72, 72), PAGE2)
    pdf = d / f"{d.name}.pdf"
    doc.save(pdf)
    doc.close()
    return d


def _finding(fid, quote=None, **extra):
    f = {"finding_id": fid, "location": "somewhere", "technique": "grim_check"}
    if quote is not None:
        f["quote"] = quote
    f.update(extra)
    return f


def _run(paper, finding):
    anchors.annotate_findings(paper, [finding])
    return finding


def _pdf_anchor(finding):
    recs = [a for a in finding["anchors"] if a["surface"] == "pdf"]
    assert recs, f"no pdf anchor on {finding['finding_id']}"
    return recs[0]


class TestExactQuote:
    def test_boxes_media_box_and_summary(self, paper):
        f = _run(paper, _finding(
            "f_aaaa000000000001",
            quote="The quick brown fox jumps over the lazy dog repeatedly."))
        a = _pdf_anchor(f)
        assert a["confidence"] == "exact"
        assert a["method"] == "quote_verbatim"
        assert a["status"] == "anchored"
        assert a["page"] == 1
        assert a["boxes"] and all(b["x1"] > b["x0"] for b in a["boxes"])
        assert a["region"]["page"] == 1
        assert a["media_box"]["w"] > 0 and a["media_box"]["h"] > 0
        assert a["anchor_id"] == "f_aaaa000000000001:a:pdf"
        assert a["passage_key"] == "f_aaaa000000000001:a"
        assert f["anchor_summary"]["pdf"] == "anchored"
        assert f["anchor_summary"]["page"] == 1
        assert f["anchor_summary"]["primary_anchor_id"] == a["anchor_id"]


class TestTypographyMangledKnownPositive:
    def test_word_alignment_recovers_boxes(self, paper):
        f = _run(paper, _finding("f_aaaa000000000002", quote=MANGLED))
        a = _pdf_anchor(f)
        assert a["method"] == "quote_word_align", (
            "the XML-copy typography case must be carried by tier 2")
        assert a["confidence"] == "exact"
        assert a["page"] == 1
        assert a["boxes"]

    def test_the_tier_is_load_bearing(self, paper, monkeypatch):
        """Disable tier 2 and the same quote must DEGRADE — proving the
        passing test above cannot pass vacuously."""
        monkeypatch.setattr(anchors, "_aligned_spans",
                            lambda ctx, page, tokens: [])
        f = _run(paper, _finding("f_aaaa000000000003", quote=MANGLED))
        a = _pdf_anchor(f)
        assert a["method"] != "quote_word_align"
        assert not a["boxes"]
        assert a["status"] in ("page_only", "unanchored")


class TestDegradation:
    def test_absent_quote_is_unanchored_never_page_1(self, paper):
        f = _run(paper, _finding(
            "f_aaaa000000000004",
            quote="the emperor penguin colony collapsed catastrophically "
                  "overnight during the austral winter storm"))
        a = _pdf_anchor(f)
        assert a["status"] == "unanchored"
        assert a["confidence"] == "none"
        assert a["method"] == "unlocated"
        assert a["page"] is None
        assert a["boxes"] == []

    def test_numeric_tokens_give_a_page_and_no_box(self, paper):
        f = _run(paper, _finding(
            "f_aaaa000000000005",
            quote="the mean was 3.53 with a dispersion of 0.71 across 30 "
                  "subjects yielding 0.049 overall"))
        a = _pdf_anchor(f)
        assert a["confidence"] == "page"
        assert a["method"] == "numeric_tokens"
        assert a["page"] == 2
        assert a["boxes"] == []
        assert a["status"] == "page_only"


class TestImagePlacements:
    def test_one_pdf_bbox_anchor_per_page_distinct_passage_keys(self, paper):
        f = _run(paper, _finding(
            "f_aaaa000000000006",
            placements=[{"page": 1, "bbox": [10, 10, 100, 100]},
                        {"page": 2, "bbox": [20, 20, 80, 90]}]))
        bbox_recs = [a for a in f["anchors"] if a["kind"] == "pdf_bbox"]
        assert [a["passage_id"] for a in bbox_recs] == ["pg1", "pg2"]
        assert len({a["passage_key"] for a in bbox_recs}) == 2
        for a in bbox_recs:
            assert a["confidence"] == "bbox"
            assert a["status"] == "anchored"
            assert a["region"]
        # dict-by-uid placements are the other on-disk shape (spec section 5)
        g = _run(paper, _finding(
            "f_aaaa000000000007",
            placements={"xref9": [{"page": 2, "bbox": [5, 5, 50, 50]}]}))
        recs = [a for a in g["anchors"] if a["kind"] == "pdf_bbox"]
        assert [a["page"] for a in recs] == [2]


class TestIdempotence:
    def test_second_run_is_a_byte_level_noop(self, paper):
        f = _finding("f_aaaa000000000008",
                     quote="The quick brown fox jumps over the lazy dog "
                           "repeatedly.")
        anchors.annotate_findings(paper, [f])
        first = json.dumps(f, sort_keys=True)
        anchors.annotate_findings(paper, [f])
        assert json.dumps(f, sort_keys=True) == first

    def test_force_reannotates(self, paper):
        f = _finding("f_aaaa000000000009",
                     quote="The quick brown fox jumps over the lazy dog "
                           "repeatedly.")
        anchors.annotate_findings(paper, [f])
        before = copy.deepcopy(f["anchors"])
        anchors.annotate_findings(paper, [f], force=True)
        assert [a["anchor_id"] for a in f["anchors"]] == \
            [a["anchor_id"] for a in before]


class TestNeverRaises:
    def test_context_failure_names_the_error(self, paper, monkeypatch):
        def boom(paper_dir, doc=None):
            raise RuntimeError("pymupdf unavailable on this machine")
        monkeypatch.setattr(anchors, "_paper_ctx", boom)
        f = _finding("f_aaaa00000000000a", quote="any quote at all here now")
        out = anchors.annotate_findings(paper, [f])  # must not raise
        assert out is not None
        assert f.get("anchor_summary") is not None

    def test_doc_open_failure_writes_named_unanchored_records(self, paper,
                                                              monkeypatch):
        real = anchors._paper_ctx

        def no_doc(paper_dir, doc=None):
            ctx = real(paper_dir, doc=doc)
            if ctx.get("own_doc") and ctx.get("doc") is not None:
                ctx["doc"].close()
            ctx["doc"] = None
            ctx["own_doc"] = False
            ctx["pdf_error"] = "pymupdf_unavailable"
            return ctx

        monkeypatch.setattr(anchors, "_paper_ctx", no_doc)
        f = _run(paper, _finding("f_aaaa00000000000b",
                                 quote="any quote at all here now"))
        a = _pdf_anchor(f)
        assert a["status"] == "unanchored"
        assert a["page"] is None
        assert "pymupdf" in (a["anchor_provenance"].get("error") or "")

    def test_non_dict_findings_are_skipped(self, paper):
        anchors.annotate_findings(paper, [None, "junk", 7])  # must not raise
