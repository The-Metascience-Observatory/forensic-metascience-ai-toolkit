"""`analyze --doi [--run-full-on-everything]`: fetch a paper with fetchpdf,
then review the folder.

fetchpdf is replaced by a fake that writes what the real one writes
(`{stem}.xml`/`.pdf`, `{stem}_supplementary_info_N_*`, the manifest,
`{stem}_data_artifacts/<deposit>/`) and reports through `json_out` -- no
network. What matters here: the folder name, reuse, the per-channel statuses
(a fetch result is never a fact about the paper), the stop before spend when
no article arrived, and that fetched datasets are actually READ.
"""
import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from metascience_agent import agent, cli, fetch_paper, raw_track, supplements

DOI = "10.1234/Journal.ABC-5"
DIRNAME = "10.1234--journal.abc-5"

_JATS = """<?xml version="1.0"?>
<article><front><article-meta><title-group><article-title>A trial
</article-title></title-group></article-meta></front><body><sec><title>Methods
</title><p>{body}</p></sec></body></article>"""


class FakeFetchpdf:
    """Writes the layout `fetchpdf.batch_fetch_pdfs` writes for one DOI."""

    __version__ = "0.0-fake"

    def __init__(self, *, xml=True, pdf=False, supplements=0, datasets=(),
                 si_status=None, raises=None, stem=DIRNAME):
        self.xml, self.pdf, self.n_si = xml, pdf, supplements
        self.datasets, self.si_status, self.raises = datasets, si_status, raises
        self.stem, self.calls = stem, []

    def batch_fetch_pdfs(self, dois, output_dir, **kw):
        self.calls.append({"dois": dois, "output_dir": output_dir, **kw})
        if self.raises:
            raise self.raises
        out = Path(output_dir)
        if self.xml:
            (out / f"{self.stem}.xml").write_text(
                _JATS.format(body="Participants were randomised. " * 40))
        if self.pdf:
            (out / f"{self.stem}.pdf").write_bytes(b"%PDF-1.4 fake")
        status = self.si_status
        if kw.get("pull_supplementary"):
            for i in range(1, self.n_si + 1):
                (out / f"{self.stem}_supplementary_info_{i}_table.csv").write_text(
                    "a,b\n1,2\n")
            (out / f"{self.stem}_supplementary_info.json").write_text("{}")
            status = status or ("ok" if self.n_si else "none_found")
        if kw.get("download_data_artifacts"):
            for rel, text in self.datasets:
                p = out / f"{self.stem}_data_artifacts" / rel
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(text)
        record = {"identifier": dois[0], "success": self.xml or self.pdf,
                  "status": "downloaded" if (self.xml or self.pdf) else "failed"}
        if kw.get("pull_supplementary"):
            record["supplementary"] = {"status": status, "missing_declared":
                                       ["S2.xlsx"] if status == "incomplete" else []}
        kw["json_out"].write(record)
        return [(dois[0], record["success"], None)]


@pytest.fixture
def fake(monkeypatch):
    holder = {}

    def install(**kw):
        holder["fp"] = FakeFetchpdf(**kw)
        monkeypatch.setattr(fetch_paper, "_load_fetchpdf", lambda: holder["fp"])
        return holder["fp"]
    return install


class TestDoi:
    @pytest.mark.parametrize("raw", [DOI, f"https://doi.org/{DOI}",
                                     f"doi:{DOI}", f"  {DOI} "])
    def test_prefixes_and_whitespace_are_stripped(self, raw):
        assert fetch_paper.normalize_doi(raw) == DOI

    @pytest.mark.parametrize("raw", ["", "not-a-doi", "10.12/", "11.1234/x"])
    def test_a_non_doi_is_refused(self, raw):
        with pytest.raises(fetch_paper.FetchError):
            fetch_paper.normalize_doi(raw)

    def test_the_folder_is_the_existing_doi_dirname_convention(self, tmp_path):
        assert fetch_paper.paper_dir_for(DOI, tmp_path) == tmp_path / DIRNAME


class TestFetch:
    def test_article_only_by_default(self, fake, tmp_path):
        fp = fake(xml=True, pdf=True)
        r = fetch_paper.fetch_for_analysis(DOI, tmp_path)
        call = fp.calls[0]
        assert call["output_dir"] == str(tmp_path / DIRNAME)
        assert call["get_xml_or_html"] and not call["pull_supplementary"]
        assert not call["download_data_artifacts"]
        assert r.channels["xml"]["status"] == "obtained"
        assert r.channels["pdf"]["status"] == "obtained"
        assert r.channels["supplements"]["status"] == "not_requested"
        assert r.channels["datasets"]["status"] == "not_requested"
        assert r.has_article and not r.reused

    def test_everything_asks_for_supplements_and_unpacked_data(self, fake, tmp_path):
        fp = fake(supplements=2, datasets=[("zenodo_1/data.csv", "x\n1\n")])
        r = fetch_paper.fetch_for_analysis(DOI, tmp_path, everything=True,
                                           max_supplementary_mb=1, max_data_mb=2)
        call = fp.calls[0]
        assert call["pull_supplementary"] and call["download_data_artifacts"]
        assert call["unpack_data_artifacts"]
        assert call["max_supplementary_bytes"] == 1024 * 1024
        assert call["max_data_artifact_bytes"] == 2 * 1024 * 1024
        assert len(r.channels["supplements"]["paths"]) == 2
        assert r.channels["datasets"]["paths"] == [
            f"{DIRNAME}_data_artifacts/zenodo_1/data.csv"]
        rec = json.loads((tmp_path / DIRNAME / "fetch.json").read_text())
        assert rec["doi"] == DOI and rec["everything"] is True
        assert rec["fetcher"] == {"name": "fetchpdf", "version": "0.0-fake"}

    def test_three_outcomes_stay_distinct(self, fake, tmp_path):
        """Found nothing, could not fetch, and did not ask are different
        facts, and none of them is a fact about the paper."""
        fake(supplements=0)
        none = fetch_paper.fetch_for_analysis(DOI, tmp_path / "a", everything=True)
        assert none.channels["supplements"]["status"] == "none_listed"
        assert none.channels["datasets"]["status"] == "not_obtained"
        assert any("not proof the paper has none" in s for s in none.limitations())

        fake(xml=False, raises=RuntimeError("network down"))
        err = fetch_paper.fetch_for_analysis(DOI, tmp_path / "b", everything=True)
        assert {err.channels[c]["status"] for c in
                ("xml", "pdf", "supplements", "datasets")} == {"error"}
        assert "network down" in err.record["error"]
        assert not err.has_article

        fake(supplements=1, si_status="incomplete")
        part = fetch_paper.fetch_for_analysis(DOI, tmp_path / "c", everything=True)
        assert part.channels["supplements"]["fetch_status"] == "incomplete"
        assert any("S2.xlsx" in s for s in part.limitations())

    def test_pdf_only_says_the_text_came_from_the_pdf(self, fake, tmp_path):
        fake(xml=False, pdf=True)
        r = fetch_paper.fetch_for_analysis(DOI, tmp_path)
        assert any("read from the PDF" in s for s in r.limitations())

    def test_an_existing_folder_is_reused_without_the_network(self, fake, tmp_path):
        fp = fake()
        fetch_paper.fetch_for_analysis(DOI, tmp_path)
        again = fetch_paper.fetch_for_analysis(DOI, tmp_path)
        assert again.reused and len(fp.calls) == 1
        assert again.channels["xml"]["status"] == "obtained"

    def test_everything_after_an_article_only_fetch_does_fetch(self, fake, tmp_path):
        fp = fake(supplements=1)
        fetch_paper.fetch_for_analysis(DOI, tmp_path)
        r = fetch_paper.fetch_for_analysis(DOI, tmp_path, everything=True)
        assert len(fp.calls) == 2 and not r.reused
        assert r.channels["supplements"]["status"] == "obtained"

    def test_refetch_runs_fetchpdf_again(self, fake, tmp_path):
        fp = fake(supplements=1)
        fetch_paper.fetch_for_analysis(DOI, tmp_path, everything=True)
        fetch_paper.fetch_for_analysis(DOI, tmp_path, everything=True, refetch=True)
        assert len(fp.calls) == 2
        assert fp.calls[1]["refresh_supplementary"] and fp.calls[1]["upgrade_existing"]

    def test_a_fetchpdf_stem_unlike_the_folder_still_resolves(self, fake, tmp_path):
        """fetchpdf encodes some DOIs differently (`:` -> `~`); the finders'
        first-non-supplementary fallback still picks the article."""
        fake(xml=True, pdf=True, supplements=1, stem="10.1234--journal.abc~2d~5")
        r = fetch_paper.fetch_for_analysis(DOI, tmp_path, everything=True)
        src = agent._resolve_paper_sources(str(r.paper_dir))
        assert src.xml.name == "10.1234--journal.abc~2d~5.xml"
        assert src.main_pdf.name == "10.1234--journal.abc~2d~5.pdf"
        assert all("supplementary_info" in p.name for p in src.si_readable)

    def test_missing_fetchpdf_is_named(self, monkeypatch, tmp_path):
        import builtins
        real = builtins.__import__

        def no_fetchpdf(name, *a, **k):
            if name == "fetchpdf":
                raise ImportError("No module named 'fetchpdf'")
            return real(name, *a, **k)
        monkeypatch.setattr(builtins, "__import__", no_fetchpdf)
        with pytest.raises(fetch_paper.FetchError, match="fetchpdf is not importable"):
            fetch_paper.fetch_for_analysis(DOI, tmp_path)


class TestDatasetsAreRead:
    """Downloaded and never opened is the failure this closes."""

    def _paper(self, tmp_path):
        d = tmp_path / DIRNAME
        dep = d / f"{DIRNAME}_data_artifacts" / "osf_abc"
        (dep / "sub").mkdir(parents=True)
        (dep / "trial.csv").write_text("a\n1\n")
        (dep / "sub" / "wide.xlsx").write_bytes(b"")
        (dep / "codebook.pdf").write_bytes(b"%PDF-1.4")
        (dep / "archive.zip").write_bytes(b"PK")
        (dep / "analysis.do").write_text("reg y x")
        (dep / "fig.tif").write_bytes(b"II*")
        (dep / ".hidden.csv").write_text("a\n")
        (d / "review_output").mkdir()
        (d / "review_output" / "stray.csv").write_text("a\n")
        return d

    def test_the_one_scan(self, tmp_path):
        d = self._paper(tmp_path)
        files, left_out = supplements.data_artifact_files(d)
        names = sorted(p.name for p in files)
        assert names == ["archive.zip", "codebook.pdf", "trial.csv", "wide.xlsx"]
        assert left_out == 0

    def test_the_cap_is_counted_not_silent(self, tmp_path, monkeypatch):
        d = self._paper(tmp_path)
        monkeypatch.setattr(supplements, "MAX_DATA_ARTIFACT_FILES", 2)
        files, left_out = supplements.data_artifact_files(d)
        assert len(files) == 2 and left_out == 2

    def test_raw_data_module_reads_them(self, tmp_path):
        d = self._paper(tmp_path)
        rels = [str(p.relative_to(d)) for p in raw_track.structured_files(d)]
        assert rels == [f"{DIRNAME}_data_artifacts/osf_abc/sub/wide.xlsx",
                        f"{DIRNAME}_data_artifacts/osf_abc/trial.csv"]

    def test_the_analysts_are_given_them(self, tmp_path):
        d = self._paper(tmp_path)
        src = agent._resolve_paper_sources(str(d))
        assert [p.name for p in src.si_pdfs] == ["codebook.pdf"]
        assert sorted(p.name for p in src.si_readable) == ["trial.csv", "wide.xlsx"]
        assert [p.name for p in src.si_unreadable] == ["archive.zip"]
        assert ("codebook.pdf" in
                {p.name for p, _ in agent._pdfs_to_extract(str(d))})


class TestCli:
    runner = CliRunner()

    def test_path_and_doi_together_are_refused(self, tmp_path):
        r = self.runner.invoke(cli.app, ["analyze", str(tmp_path), "--doi", DOI,
                                         "--backend", "claude"])
        assert r.exit_code == 2 and "exactly one" in r.output

    def test_neither_is_refused(self):
        r = self.runner.invoke(cli.app, ["analyze", "--backend", "claude"])
        assert r.exit_code == 2

    def test_the_flag_needs_doi(self, tmp_path):
        r = self.runner.invoke(cli.app, ["analyze", str(tmp_path),
                                         "--run-full-on-everything",
                                         "--backend", "claude"])
        assert r.exit_code == 2 and "need --doi" in r.output

    def test_a_bad_flag_costs_no_download(self, fake, tmp_path):
        fp = fake()
        r = self.runner.invoke(cli.app, ["analyze", "--doi", DOI,
                                         "--fetch-dir", str(tmp_path)])
        assert r.exit_code == 2 and "--backend is required" in r.output
        assert fp.calls == []

    def test_no_article_stops_before_any_spend(self, fake, tmp_path, monkeypatch):
        fake(xml=False, pdf=False)

        def must_not_run(*a, **k):
            raise AssertionError("reached the paper after a failed fetch")
        monkeypatch.setattr(agent, "ensure_paper_extracted", must_not_run)
        monkeypatch.setattr(agent, "analyze_paper", must_not_run)
        r = self.runner.invoke(cli.app, ["analyze", "--doi", DOI,
                                         "--run-full-on-everything",
                                         "--fetch-dir", str(tmp_path),
                                         "--backend", "claude"])
        assert r.exit_code == 2, r.output
        assert "No copy of the article was obtained" in r.output

    def test_the_flag_runs_the_complete_review_on_everything(self, fake, tmp_path):
        fp = fake(xml=False, pdf=False)
        r = self.runner.invoke(cli.app, ["analyze", "--doi", DOI,
                                         "--run-full-on-everything",
                                         "--fetch-dir", str(tmp_path),
                                         "--backend", "claude"])
        assert "pipeline 'full_raw_data'" in r.output
        for module in ("tools_agent", "scientific_proofreading_agent",
                       "image_analysis", "text_forensics", "raw_data",
                       "adjudicator"):
            assert module in r.output, module
        call = fp.calls[0]
        assert call["pull_supplementary"] and call["download_data_artifacts"]

    @pytest.mark.parametrize("narrower", ["raw_data_only", "full", "image_detect"])
    def test_a_narrower_pipeline_is_refused_before_any_fetch(self, fake, tmp_path,
                                                            narrower):
        fp = fake()
        r = self.runner.invoke(cli.app, ["analyze", "--doi", DOI,
                                         "--run-full-on-everything",
                                         "--pipeline", narrower,
                                         "--fetch-dir", str(tmp_path),
                                         "--backend", "claude"])
        assert r.exit_code == 2 and "be combined with" in " ".join(r.output.split())
        assert fp.calls == []

    def test_run_forwards_the_fetch_options(self, fake, tmp_path):
        """`run` passes unknown options through, so the ones that take a value
        must be declared or the value lands in PAPER_PATH."""
        fp = fake(xml=False, pdf=False)
        r = self.runner.invoke(cli.app, ["run", "raw_data_only", "--doi", DOI,
                                         "--fetch-dir", str(tmp_path),
                                         "--max-data-mb", "3"])
        assert r.exit_code == 2, r.output
        assert fp.calls and fp.calls[0]["output_dir"] == str(tmp_path / DIRNAME)
        assert fp.calls[0]["max_data_artifact_bytes"] == 3 * 1024 * 1024

    def test_fetched_data_reach_the_detector_and_run_meta(self, fake, tmp_path):
        """No model: fetch everything, then the raw-data module alone over the
        folder. The deposit CSV must be read and the fetch must reach
        run_meta. (The paid modules of the full review are covered by their
        own tests; this pins the hand-off from the fetch.)"""
        from tests.test_raw_data_module import _csv_with_copied_rows

        fake(xml=True, supplements=0,
             datasets=[("zenodo_9/table.csv", _csv_with_copied_rows())])
        res = fetch_paper.fetch_for_analysis(DOI, tmp_path, everything=True)
        r = self.runner.invoke(cli.app, ["run", "raw_data_only", str(res.paper_dir),
                                         "--no-pdf", "--no-bundle"])
        assert r.exit_code == 0, r.output
        metas = list(res.paper_dir.rglob("run_meta.json"))
        assert len(metas) == 1
        meta = json.loads(metas[0].read_text())
        assert meta["fetch"]["channels"]["datasets"]["status"] == "obtained"
        assert "fetchpdf_record" not in meta["fetch"]
        assert meta["stages"]["raw_data"]["detail"].startswith("1 file(s)")
        doc = (metas[0].parent / "findings.v2.json").read_text()
        assert f"{DIRNAME}_data_artifacts/zenodo_9/table.csv" in doc
