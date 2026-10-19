"""PMC figure renders for papers with no PDF: the fetch (offline, with an
injected HTTP getter), the `pmc_render` harvest channel, and the track's
fallback to it. Every test names the substitution it forbids.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

fitz = pytest.importorskip("fitz")
cv2 = pytest.importorskip("cv2")

from metascience_observatory_image_analysis.image_forensics import panels as PN  # noqa: E402
from metascience_observatory_image_analysis.image_forensics import pmc_figures as PF  # noqa: E402
from metascience_observatory_image_analysis.image_forensics.image_analysis import analyze_paper_images  # noqa: E402
from metascience_observatory_image_analysis.image_forensics.image_track import run_track  # noqa: E402

SRC = Path(__file__).resolve().parent.parent / "src" / "forensic_metascience_ai_toolkit"

JATS = """<?xml version="1.0"?>
<pmc-articleset><article xmlns:xlink="http://www.w3.org/1999/xlink">
<body><sec>
<fig id="F1" position="float"><label>Fig. 1</label>
  <caption><title>Confocal images of treated cells.</title></caption>
  <graphic xlink:href="nihms1f1.jpg"/></fig>
<fig id="F2"><label>Figure 2.</label>
  <caption><p>Confocal images of control cells.</p></caption>
  <graphic xlink:href="nihms1f2"/></fig>
<fig id="F3"><label>Fig. 3</label><caption><p>Blot.</p></caption></fig>
</sec></body></article></pmc-articleset>
"""

PAGE = """<html><body>
<img src="https://cdn.ncbi.nlm.nih.gov/pmc/blobs/1234/999/aa11/nihms1f1.jpg">
<a href="https://cdn.ncbi.nlm.nih.gov/pmc/blobs/1234/999/bb22/nihms1f2.jpg">f2</a>
</body></html>"""



IMAGE_SRC = __import__("pathlib").Path(__import__("metascience_observatory_image_analysis").__file__).parent
def _texture(seed: int, w: int = 300, h: int = 220) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return cv2.GaussianBlur(rng.integers(0, 256, (h, w), dtype=np.uint8), (0, 0), 1.2)


def _jpg(gray: np.ndarray) -> bytes:
    ok, buf = cv2.imencode(".jpg", gray, [cv2.IMWRITE_JPEG_QUALITY, 92])
    assert ok
    return buf.tobytes()


def _getter(images: dict[str, bytes], page_status: int = 200):
    calls: list[str] = []

    def get(url: str):
        calls.append(url)
        if url.startswith(PF.PMC_PAGE.format(pmcid="PMC999")):
            return page_status, PAGE.encode(), "text/html"
        for base, data in images.items():
            if url.endswith(base):
                return 200, data, "image/jpeg"
        return 404, b"", "text/html"
    return get, calls


@pytest.fixture
def paper(tmp_path):
    d = tmp_path / "10.1--nopdf"
    d.mkdir()
    (d / "10.1--nopdf.xml").write_text(JATS)
    (d / "10.1--nopdf.provenance.json").write_text(json.dumps(
        {"identifiers_resolved": {"doi": "10.1/nopdf", "pmcid": "PMC999"}}))
    (d / "metadata.json").write_text("{}")
    return d


class TestTheFetch:
    def test_jats_figures_normalise_labels_and_skip_figs_without_a_graphic(self):
        figs = PF.jats_figures(JATS)
        assert [f["figure_label"] for f in figs] == ["Figure 1", "Figure 2"]
        assert figs[0]["caption"].startswith("Confocal images of treated")
        assert figs[1]["href"] == "nihms1f2"

    def test_page_urls_match_by_basename_with_or_without_extension(self):
        urls = PF.figure_urls_from_page(PAGE, ["nihms1f1.jpg", "nihms1f2", "nope.jpg"])
        assert urls["nihms1f1.jpg"].endswith("/aa11/nihms1f1.jpg")
        assert urls["nihms1f2"].endswith("/bb22/nihms1f2.jpg")
        assert "nope.jpg" not in urls

    def test_fetch_writes_files_and_a_manifest_politely(self, paper):
        same = _jpg(_texture(1))
        get, calls = _getter({"nihms1f1.jpg": same, "nihms1f2.jpg": same})
        slept: list[float] = []
        m = PF.fetch_figures(paper, delay_s=0.7, get=get, sleep=slept.append)
        assert m["pmcid"] == "PMC999" and m["n_ok"] == 2 and m["n_failed"] == 0
        assert m["refusal"] is None
        assert (paper / "pmc_figures" / "nihms1f1.jpg").read_bytes() == same
        assert (paper / "pmc_figures" / "nihms1f2.jpg").exists()
        assert (paper / "pmc_figures" / "manifest.json").exists()
        # one page + two images, a delay after each, serial
        assert len(calls) == 3 and len(slept) == 3 and all(s == 0.7 for s in slept)
        # idempotent: a second call requests nothing
        m2 = PF.fetch_figures(paper, get=get, sleep=slept.append)
        assert m2.get("reused") is True and len(calls) == 3

    def test_refusals_are_named_and_written(self, paper, tmp_path):
        get, _ = _getter({}, page_status=403)
        m = PF.fetch_figures(paper, get=get, sleep=lambda s: None)
        assert m["refusal"]["kind"] == "page_unreachable:403"
        assert PF.read_manifest(paper)["refusal"]["kind"] == "page_unreachable:403"
        nop = tmp_path / "10.1--nopmcid"
        nop.mkdir()
        (nop / "metadata.json").write_text("{}")
        assert PF.fetch_figures(nop, get=get, sleep=lambda s: None)["refusal"]["kind"] == "no_pmcid"

    def test_a_page_with_no_figure_links_is_retried_then_named(self, paper):
        """MEASURED live 2026-09-02: PMC served a 200 page listing no figure
        links for two papers, then listed every figure minutes later."""
        pages = iter([b"<html>no links yet</html>", PAGE.encode()])
        img = _jpg(_texture(1))

        def get(url):
            if url.startswith(PF.PMC_PAGE.format(pmcid="PMC999")):
                return 200, next(pages), "text/html"
            return (200, img, "image/jpeg") if url.endswith(".jpg") else (404, b"", "")
        slept: list[float] = []
        m = PF.fetch_figures(paper, delay_s=1.0, get=get, sleep=slept.append)
        assert m["page_retried"] is True and m["page_blob_links"] == 2
        assert m["n_ok"] == 2
        assert max(slept) >= 5.0, "the retry must wait longer than the normal delay"
        # twice empty -> a refusal that is NOT "figure missing"
        (paper / "pmc_figures" / "manifest.json").unlink()
        m = PF.fetch_figures(paper, get=lambda u: (200, b"<html></html>", "text/html"),
                             sleep=lambda s: None)
        assert m["refusal"]["kind"] == "page_without_figure_links"
        assert m["figures"] == []

    def test_a_manifest_that_fetched_nothing_is_retried_not_reused(self, paper):
        get, calls = _getter({}, page_status=503)
        m = PF.fetch_figures(paper, get=get, sleep=lambda s: None)
        assert m["refusal"]["kind"] == "page_unreachable:503"
        get2, calls2 = _getter({"nihms1f1.jpg": _jpg(_texture(1)),
                                "nihms1f2.jpg": _jpg(_texture(2))})
        m2 = PF.fetch_figures(paper, get=get2, sleep=lambda s: None)
        assert not m2.get("reused") and m2["n_ok"] == 2 and calls2

    def test_a_figure_missing_from_the_page_is_named_per_figure(self, paper):
        get, _ = _getter({"nihms1f1.jpg": _jpg(_texture(1))})
        m = PF.fetch_figures(paper, get=get, sleep=lambda s: None)
        by = {f["href"]: f["status"] for f in m["figures"]}
        assert by["nihms1f1.jpg"] == "ok"
        assert by["nihms1f2"] == "download_failed:404"
        assert m["n_ok"] == 1 and m["n_failed"] == 1


class TestTheChannel:
    def test_pmc_render_is_not_original_bytes(self):
        assert PN.PMC_RENDER not in PN.ORIGINAL_BYTES

    def _fetched(self, paper, a: bytes, b: bytes):
        get, _ = _getter({"nihms1f1.jpg": a, "nihms1f2.jpg": b})
        PF.fetch_figures(paper, get=get, sleep=lambda s: None)

    def test_harvest_reads_renders_with_figure_labels(self, paper):
        self._fetched(paper, _jpg(_texture(1)), _jpg(_texture(2)))
        h = PN.harvest_pmc_figures(paper)
        assert h["success"] and h["n_panels"] == 2 and h["n_eligible"] == 2
        labels = {p["placements"][0]["figure_label"] for p in h["panels"]}
        assert labels == {"Figure 1", "Figure 2"}
        assert all(p["acquisition"] == PN.PMC_RENDER for p in h["panels"])
        assert all(p["placements"][0]["page"] is None for p in h["panels"])

    def test_no_manifest_is_a_refusal_not_an_empty_harvest(self, tmp_path):
        d = tmp_path / "10.1--x"
        d.mkdir()
        h = PN.harvest_pmc_figures(d)
        assert h["success"] is False and h["unreadable"] is True
        assert "never fetched" in h["error"]

    def test_the_same_render_under_two_figures_fires_perceptually_only(self, paper):
        same = _jpg(_texture(3))
        self._fetched(paper, same, same)
        res = analyze_paper_images(None, paper_dir=paper, out_dir=paper / "panels")
        assert res["success"], res.get("error")
        kinds = {g["kind"] for g in res["duplicate_groups"]
                 if g.get("duplication_evidence") is not False}
        assert "near_duplicate_phash" in kinds or "transformed_match" in kinds
        assert "identical_stream" not in kinds, (
            "byte identity between two PMC renders testifies about PMC, not the authors")
        assert res["pdf"] is None
        assert [d["role"] for d in res["documents"]] == ["pmc_render"]
        assert res["n_panels"] == 2

    def test_identified_main_pdf_is_gold_standard_over_pmc_renders(self, paper):
        same = _jpg(_texture(31))
        self._fetched(paper, same, same)
        pdf = paper / f"{paper.name}.pdf"
        with fitz.open() as doc:
            page = doc.new_page()
            page.insert_image(fitz.Rect(60, 60, 360, 280), stream=same)
            doc.save(pdf)
        res = analyze_paper_images(pdf, paper_dir=paper, out_dir=paper / "panels")
        assert res["success"], res.get("error")
        assert not [g for g in res["duplicate_groups"]
                    if g.get("duplication_evidence") is not False]
        ignored = [e for e in res["excluded"]
                   if e.get("reason") == "alternate_source_ignored"]
        assert len(ignored) == 2
        assert all("gold-standard" in e["detail"] for e in ignored)

    def test_run_track_examines_a_pdf_less_paper_and_refuses_without_renders(self, paper):
        out = run_track(paper, emit_v2=True)
        assert out["status"]["ran"] is False
        assert out["status"]["refusal_subtype"] == "no_pdf"
        assert "image-fetch-pmc-figures" in out["status"]["detail"]
        same = _jpg(_texture(4))
        self._fetched(paper, same, same)
        out = run_track(paper, emit_v2=True)
        assert out["status"]["ran"] is True, out["status"]
        assert "PMC FIGURE RENDERS ONLY" in out["status"]["detail"]
        assert out["findings_rows"], "the duplicated render produced no row"
        v2 = out["findings_rows_v2"]
        assert v2 and v2[0]["anchors"] == []
        assert "PMC figure renders" in v2[0]["anchor_problem"]
        assert v2[0]["inputs"]["spans_figures"] is True

    def test_never_spends_and_never_runs_from_the_sweep(self):
        src = (IMAGE_SRC / "image_forensics" / "pmc_figures.py").read_text()
        for bad in ("llm_backend", "resolve_backend", "subprocess"):
            assert bad not in src
        sweep = (IMAGE_SRC / "image_forensics" / "sweep.py").read_text()
        assert "pmc_figures" not in sweep.replace("pmc_figures/manifest", "")


# ---------------------------------------------------------------------------
# 2026-09-06: figures as images for EVERY paper (Greg), starting with PMC.
# Measured on the working corpus before these: six papers refused `no_pmcid`
# while carrying one in a source record or in the JATS itself; five PNAS papers
# had the PMC page on disk with every blob link in it and no JATS; and PMC
# served a 200 page without its figure section twice in a row.
# ---------------------------------------------------------------------------

_LONG = " ".join(["Results were consistent across the sample and the analyses that follow."] * 30)
LOCAL_PAGE = f"""<html><body><article>
<h1>A paper with its page on disk</h1><p>{_LONG}</p>
<figure class="fig xbox font-sm" id="fig01"><h4>Fig. 1.</h4>
<img class="graphic zoom-in" src="https://cdn.ncbi.nlm.nih.gov/pmc/blobs/e2a2/3306667/69b76a4faf99/pnas.1118373109fig01.jpg">
<figcaption><p>Training improves <i>recall</i> at 24 h.</p></figcaption></figure>
<figure class="fig xbox font-sm" id="fig02"><h4>Fig. 2.</h4>
<img class="graphic zoom-in" src="https://cdn.ncbi.nlm.nih.gov/pmc/blobs/e2a2/3306667/6a043a442a23/pnas.1118373109fig02.jpg">
<figcaption><p>Dose response.</p></figcaption></figure>
<p>{_LONG}</p></article></body></html>"""


class TestPmcidSources:
    def test_the_source_upgrade_record_names_the_pmcid(self, tmp_path):
        d = tmp_path / "10.1073--pnas.x"; d.mkdir()
        (d / "10.1073--pnas.x.fulltext.source.json").write_text(json.dumps({"pmcid": "PMC3306667", "url": "x"}))
        assert PF.pmcid_of(d) == "PMC3306667"

    def test_the_jats_names_its_own_pmcid(self, tmp_path):
        d = tmp_path / "10.1--j"; d.mkdir()
        (d / "10.1--j.xml").write_text('<article><front><article-meta>'
                                       '<article-id pub-id-type="pmcid">PMC12138863</article-id>'
                                       '</article-meta></front></article>')
        assert PF.pmcid_of(d) == "PMC12138863"

    def test_nothing_anywhere_is_still_none(self, tmp_path):
        d = tmp_path / "10.1--none"; d.mkdir()
        (d / "metadata.json").write_text("{}")
        assert PF.pmcid_of(d) is None


class TestTheLocalPage:
    def test_figures_come_from_the_page_on_disk_without_a_page_request(self, tmp_path):
        d = tmp_path / "10.1073--pnas.1118373109"; d.mkdir()
        # A complete article fixture clears both the built-in gate and the
        # optional fetchpdf validator (5000 characters and populated tables).
        page = LOCAL_PAGE.replace("</article>", "<p>" + "article prose. " * 500
                                  + "</p><table><tr><td>12.3</td></tr></table></article>")
        (d / "10.1073--pnas.1118373109.fulltext.html").write_text(page)
        (d / "10.1073--pnas.1118373109.fulltext.source.json").write_text(json.dumps({"pmcid": "PMC3306667"}))
        (d / "10.1073--pnas.1118373109.pdf").write_bytes(b"%PDF-1.4 stub")
        calls: list[str] = []

        def get(url):
            calls.append(url)
            if "/blobs/" in url:
                return 200, _jpg(_texture(int(url[-6:-4]) if url[-6:-4].isdigit() else 1)), "image/jpeg"
            return 500, b"", "text/html"
        m = PF.fetch_figures(d, get=get, sleep=lambda s: None)
        assert m["refusal"] is None, m
        assert m["source"] == "local_html_page" and m["figures_from"] == "local_html_page"
        assert m["n_ok"] == 2 and not any(PF.PMC_PAGE.format(pmcid="PMC3306667") in u for u in calls), (
            "the page was on disk; PMC was asked only for the two images")
        labels = sorted(f["figure_label"] for f in m["figures"])
        assert labels == ["Figure 1", "Figure 2"]
        assert m["figures"][0]["caption"].startswith("Training improves recall")
        assert (d / PF.SUBDIR / "pnas.1118373109fig01.jpg").exists()

    def test_html_figures_reads_id_label_caption_and_blob(self):
        figs = PF.html_figures(LOCAL_PAGE)
        assert [(f["id"], f["figure_label"], f["href"]) for f in figs] == [
            ("fig01", "Figure 1", "pnas.1118373109fig01.jpg"), ("fig02", "Figure 2", "pnas.1118373109fig02.jpg")]


class TestRetries:
    def test_an_empty_page_is_retried_with_backoff_then_read(self, paper):
        images = {"nihms1f1.jpg": _jpg(_texture(1)), "nihms1f2.jpg": _jpg(_texture(2))}
        served: list[int] = []
        pauses: list[float] = []

        def get(url):
            if url.startswith(PF.PMC_PAGE.format(pmcid="PMC999")):
                served.append(1)
                if len(served) < 3:
                    return 200, b"<html><body>PMC page without its figure section</body></html>", "text/html"
                return 200, PAGE.encode(), "text/html"
            for base, data in images.items():
                if url.endswith(base):
                    return 200, data, "image/jpeg"
            return 404, b"", "text/html"
        m = PF.fetch_figures(paper, get=get, sleep=pauses.append)
        assert m["refusal"] is None and m["n_ok"] == 2
        assert m["page_attempts"] == 3 and m["page_retried"] is True
        assert PF.PAGE_RETRY_PAUSES_S[0] in pauses and PF.PAGE_RETRY_PAUSES_S[1] in pauses, "backed off, not hammered"

    def test_a_page_empty_every_time_is_named_after_all_attempts(self, paper):
        def get(url):
            if url.startswith(PF.PMC_PAGE.format(pmcid="PMC999")):
                return 200, b"<html><body>nothing</body></html>", "text/html"
            return 404, b"", "text/html"
        m = PF.fetch_figures(paper, get=get, sleep=lambda s: None)
        assert m["refusal"]["kind"] == "page_without_figure_links"
        assert m["page_attempts"] == 1 + len(PF.PAGE_RETRY_PAUSES_S)


class TestAllPapers:
    def test_all_papers_includes_one_that_has_a_pdf(self, tmp_path, monkeypatch):
        corpus = tmp_path / "corpus"; corpus.mkdir()
        d = corpus / "10.1--haspdf"; d.mkdir()
        (d / "10.1--haspdf.pdf").write_bytes(b"%PDF-1.4 stub")
        (d / "metadata.json").write_text("{}")
        monkeypatch.setattr("forensic_metascience_ai_toolkit.webapp_index.iter_paper_dirs", lambda c: [d])
        logs: list[str] = []
        s_default = PF.run_fetch(corpus, get=lambda u: (404, b"", ""), sleep=lambda s: None, log=logs.append)
        s_all = PF.run_fetch(corpus, get=lambda u: (404, b"", ""), sleep=lambda s: None, log=logs.append,
                             all_papers=True)
        assert s_default["attempted"] == 0 and s_all["attempted"] == 1


class TestSupplementaryLabelsAreFigureS:
    """MEASURED 2026-09-14 on `10.1016--j.jalz.2018.02.017`: `Supplementary
    Fig. 1` normalised to `Figure 1` and collided with the main text's Figure
    1 (six figures, three labels). The canonical form is `Figure S<n>`, the
    spelling `publisher_figures.figure_label` already emitted."""

    def test_the_supplementary_family(self):
        assert PF.normalise_label("Supplementary Fig. 1") == "Figure S1"
        assert PF.normalise_label("Supplemental Figure 2A") == "Figure S2A"
        assert PF.normalise_label("Supporting Figure 3") == "Figure S3"
        assert PF.normalise_label("Supplementary Figure S3") == "Figure S3"

    def test_other_prefixes_and_plain_labels_are_untouched(self):
        assert PF.normalise_label("Extended Data Fig. 2") == "Figure 2"
        assert PF.normalise_label("Fig. 3") == "Figure 3"
        assert PF.normalise_label("Figure S1") == "Figure S1"

    def test_a_jats_supplementary_fig_label(self):
        xml = ("<article><body><fig id='S1'><label>Supplementary Figure 1</label>"
               "<graphic href='s1.jpg'/></fig></body></article>")
        assert [f["figure_label"] for f in PF.jats_figures(xml)] == ["Figure S1"]
