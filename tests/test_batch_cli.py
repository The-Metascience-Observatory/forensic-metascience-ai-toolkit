"""`metascience batch` must be one command over a whole directory, and safe to interrupt.

Dan's requirement, verbatim: "running the system on the 100 papers in series
should be as simple as a single command line command"; "it's meant to be fully
automated". Before this, batching lived in `forensic_metascience_ai_toolkit/batch.py` with
`--limit 3` and `--concurrency 3` -- a script, not a command, defaulting to
three papers in parallel.

Nothing here spends money: every test uses --dry-run or an empty corpus.
"""
import json

from typer.testing import CliRunner

from forensic_metascience_ai_toolkit.cli import app

runner = CliRunner()


def _corpus(tmp_path, n, with_report=(), same_text=False):
    """A corpus of `n` papers, each with DISTINCT body text by default.

    Every paper used to get the literal string "# body", which made the whole
    corpus a set of duplicates. That was invisible until the batch plan learned
    to warn about directories sharing one text -- a real corpus does not look
    like this, so the fixture would have fired a warning meant for a genuine
    defect in every unrelated test. `same_text=True` asks for the degenerate
    case on purpose.
    """
    root = tmp_path / "corpus"
    root.mkdir()
    for i in range(n):
        d = root / f"10.1234--paper{i:03d}"
        d.mkdir()
        (d / "body.md").write_text(
            "# body" if same_text else f"# body of paper {i}")
        (d / f"10.1234--paper{i:03d}.pdf").write_bytes(b"%PDF-1.4")
        if i in with_report:
            (d / "forensic_review").mkdir()
            (d / "forensic_review" / "report.md").write_text("x")
    return root


class TestDryRun:
    def test_reports_the_plan_without_spending(self, tmp_path):
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 5)), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "papers found" in r.output
        assert "nothing spent" in r.output.lower()

    def test_defaults_to_ten_workers(self, tmp_path):
        """CHANGED 2026-08-23, at Dan's request, and it reverses a decision.

        The default was 1, on the argument that "a shared token budget, not
        wall-clock, is the binding constraint" -- true of a 421-paper corpus
        under one Claude quota, where parallelism only spends the same budget
        sooner. It is false of the case this default now serves: a ten-paper
        benchmark corpus, where serial execution costs ten paper-times (~5.5
        hours at the measured 33 min/paper) for no saving at all.

        The old reason has not stopped being true for large corpora. Pass
        `-j 1` there. The risk this default carries is that ten workers hit a
        session limit together, and with `--backend grok` there is no usage
        probe to notice.
        """
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 3)), "--dry-run", "--backend", "claude"])
        assert "10" in next(l for l in r.output.splitlines() if "workers" in l)

    def test_defaults_to_the_whole_directory(self, tmp_path):
        """The old script defaulted to --limit 3, which silently analysed 3%."""
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 12)), "--dry-run", "--backend", "claude"])
        assert "12" in r.output

    def test_gives_a_cost_estimate_before_committing(self, tmp_path):
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 10)), "--dry-run", "--backend", "claude"])
        assert "estimated total" in r.output.lower()


class TestResumability:
    def test_already_analysed_papers_are_skipped(self, tmp_path):
        """An interrupted run must restart with the SAME command, paying once."""
        root = _corpus(tmp_path, 6, with_report=(0, 1, 2))
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0
        # Assert on content, not on table layout: column widths shift whenever a
        # row is added, and a test that breaks on formatting teaches people to
        # ignore it.
        import re
        row = next(l for l in r.output.splitlines() if "already analysed" in l)
        assert re.search(r"\b3\b", row), f"expected 3 skipped, got: {row!r}"
        assert "SKIP  10.1234--paper000" in r.output
        assert "paper003" in r.output          # pending

    def test_fully_analysed_corpus_does_nothing(self, tmp_path):
        root = _corpus(tmp_path, 3, with_report=(0, 1, 2))
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0
        assert "Nothing to do" in r.output

    def test_redo_overrides_the_skip(self, tmp_path):
        root = _corpus(tmp_path, 3, with_report=(0, 1, 2))
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "--redo"])
        assert "Nothing to do" not in r.output


class TestFullTextGate:
    """A directory is not a paper. Check there is something to READ before pricing it.

    `pick_papers` takes every subdirectory of the corpus, so a directory holding
    only extracted figures, only a previous forensic_review/, or nothing at all,
    was counted as runnable and priced into the estimate. The sweep then runs
    with no source, finds nothing, and an empty findings.json reads exactly like
    a clean paper.

    Measured 2026-08-07 on eval/ground_truth/papers/: 8 of 78 directories have no
    XML, no body.md and no main PDF. With --ok-if-supplementary-missing all 78 were listed
    as runnable, so those 8 would have been paid for (~$40 at the measured
    $5/paper) to sweep nothing.
    """

    @staticmethod
    def _mixed(tmp_path):
        """3 real papers + 2 directories with no readable source."""
        root = tmp_path / "corpus"
        root.mkdir()
        for i in range(3):
            d = root / f"10.1234--real{i:03d}"
            d.mkdir()
            (d / "body.md").write_text("# body")
        # Nothing to read: figures only, and completely empty.
        (root / "10.1234--figs-only" / "figures").mkdir(parents=True)
        ((root / "10.1234--figs-only" / "figures") / "fig1.png").write_bytes(b"\x89PNG")
        (root / "10.1234--empty").mkdir()
        return root

    def test_papers_with_no_readable_source_are_not_counted_as_runnable(self, tmp_path):
        r = runner.invoke(app, ["batch", str(self._mixed(tmp_path)), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "no full text" in r.output, "the skip must be visible, not silent"
        assert "SKIP  10.1234--figs-only" in r.output
        assert "SKIP  10.1234--empty" in r.output
        assert "real000" in r.output

    def test_ok_if_supplementary_missing_does_not_wave_them_through(self, tmp_path):
        """--ok-if-supplementary-missing trades partial coverage for a run. There is
        nothing to trade when there is no text at all, so it must not apply here.
        """
        r = runner.invoke(
            app, ["batch", str(self._mixed(tmp_path)), "--dry-run", "--backend", "claude", "--ok-if-supplementary-missing"]
        )
        assert r.exit_code == 0, r.output
        assert "SKIP  10.1234--figs-only" in r.output
        assert "SKIP  10.1234--empty" in r.output
        row = next(l for l in r.output.splitlines() if "to run" in l)
        assert "3" in row, f"expected 3 runnable, got: {row!r}"

    def test_a_missing_supplement_is_included_with_a_warning(self, tmp_path):
        """2026-10-18: a paper citing supplementary material that is not here
        runs (with a warning and a report limitation); it used to be skipped."""
        root = tmp_path / "corpus"
        root.mkdir()
        d = root / "10.1234--cites-si"
        d.mkdir()
        (d / "body.md").write_text("Baseline data are in eTable 3 of Supplement 1.")
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "SKIP  10.1234--cites-si" not in r.output
        assert "WARNING" in r.output and "10.1234--cites-si" in r.output
        assert "INCLUDED, warned" in r.output
        row = next(line for line in r.output.splitlines() if "to run" in line)
        assert "1" in row, r.output

    def test_harvest_from_pdf_body_is_readable(self, tmp_path):
        """A harvest body is text. Skipping it as a scan was the nina_mazar miss."""
        root = tmp_path / "corpus"
        root.mkdir()
        d = root / "10.1002--bdm.1794"
        d.mkdir()
        (d / "10.1002--bdm.1794.pdf").write_bytes(b"%PDF-1.4")
        (d / "10.1002--bdm.1794_from_pdf_body.md").write_text(
            "See Supplementary Table 1. n = 40, p = .03.")
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude",
                                "--ok-if-supplementary-missing"])
        assert r.exit_code == 0, r.output
        assert "scanned or corrupt" not in r.output
        assert "SKIP  10.1002--bdm.1794" not in r.output
        row = next(l for l in r.output.splitlines() if "to run" in l)
        assert "1" in row, r.output

    def test_the_runner_is_handed_pending_not_the_corpus(self):
        """The plan table used to skip no-full-text papers, then run_batch
        called pick_papers on the corpus again. Measured 2026-08-20: grok_test
        said to run 3, then 'Analyzing 6 papers', and the landing-page-only
        directory failed with FileNotFoundError as if it were an analysis
        fault.
        """
        import inspect
        from forensic_metascience_ai_toolkit import cli as cli_mod
        src = inspect.getsource(cli_mod.batch_cmd)
        assert "papers=pending" in src, (
            "run_batch must receive the gated pending list; re-picking "
            "from the corpus re-queues every skip the table just announced"
        )

    def test_skipped_directories_are_not_analysed(self, tmp_path, monkeypatch):
        """Live path, not dry-run: analyze_paper must not see the empty dirs."""
        import sys
        from pathlib import Path as _P
        from forensic_metascience_ai_toolkit import batch as batch_analyze

        seen: list[str] = []

        async def fake_analyze(path, **kwargs):
            seen.append(_P(path).name)
            # The shape `analyze_paper` actually returns since v1.27.0: the
            # deliverable is the findings-v2 document, and the report is
            # rendered from it at write time.
            return {
                "mode": "parallel",
                "report": "# ok",
                "findings_v2": {"schema_version": "2.0", "paper_id": "p",
                                "findings": []},
                "is_error": False,
                "verdict": "ok",
                "total_cost_usd": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_wall_seconds": 1.0,
                "run_meta": {"stages": {}},
            }

        async def no_guard(*a, **k):
            return None

        monkeypatch.setattr(batch_analyze, "analyze_paper", fake_analyze)
        monkeypatch.setattr(batch_analyze, "write_parallel_outputs",
                            lambda *a, **k: None)
        monkeypatch.setattr(batch_analyze, "usage_guard", no_guard)

        r = runner.invoke(app, ["batch", str(self._mixed(tmp_path)),
                                "--workers", "1", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "Analyzing 3 papers" in r.output
        assert "figs-only" not in seen
        assert "empty" not in seen
        assert seen == ["10.1234--real000", "10.1234--real001",
                        "10.1234--real002"]


class TestGuardsAgainstMistakes:
    def test_missing_directory_exits_nonzero(self, tmp_path):
        r = runner.invoke(app, ["batch", str(tmp_path / "nope"), "--dry-run", "--backend", "claude"])
        assert r.exit_code != 0

    def test_empty_directory_exits_nonzero(self, tmp_path):
        empty = tmp_path / "empty"
        empty.mkdir()
        r = runner.invoke(app, ["batch", str(empty), "--dry-run", "--backend", "claude"])
        assert r.exit_code != 0


class TestUsageReporting:
    """Greg owed Dan a token/USD report. This is it."""

    def test_reports_tokens_and_api_equivalent_cost(self, tmp_path):
        root = _corpus(tmp_path, 2)
        (root / "batch_costs.jsonl").write_text(
            json.dumps({"paper": "a", "total_cost_usd": 4.97,
                        "input_tokens": 120000, "output_tokens": 8000,
                        "total_wall_seconds": 300.0}) + "\n"
            + json.dumps({"paper": "b", "total_cost_usd": 5.03,
                          "input_tokens": 130000, "output_tokens": 9000,
                          "total_wall_seconds": 320.0}) + "\n"
        )
        r = runner.invoke(app, ["usage", str(root)])
        assert r.exit_code == 0, r.output
        out = r.output.replace(",", "").replace(" ", "")
        assert "267000" in out, "total tokens not reported"
        assert "10.00" in out, "total cost not reported"
        assert "5.00" in out, "mean per paper not reported"
        # 120k+130k in, 8k+9k out, two papers.
        assert "125000" in out, "average tokens in per paper"
        assert "8500" in out, "average tokens out per paper"
        assert "average tokens in per paper" in r.output
        assert "average tokens out per paper" in r.output
        # 300s + 320s = 10m 20s total, 5m 10s per paper. Used to print
        # "0.2 h", which hides minutes and seconds and has no per-paper row.
        assert "10m 20s" in r.output, r.output
        assert "5m 10s" in r.output, r.output
        assert "average runtime per paper" in r.output

    def test_tokens_in_per_paper_includes_cache(self, tmp_path):
        """`input_tokens` alone is ~0 on a cached sweep; the live line sums
        cache-read/creation into "in", and the summary must not disagree."""
        root = _corpus(tmp_path, 1)
        (root / "batch_costs.jsonl").write_text(
            json.dumps({"paper": "a", "total_cost_usd": 1.0,
                        "input_tokens": 20,
                        "cache_creation_input_tokens": 1000,
                        "cache_read_input_tokens": 8980,
                        "output_tokens": 50,
                        "total_wall_seconds": 60.0}) + "\n")
        r = runner.invoke(app, ["usage", str(root)])
        assert r.exit_code == 0, r.output
        out = r.output.replace(",", "").replace(" ", "")
        assert "10000" in out, "tokens in must include cache: 20+1000+8980"
        assert "50" in out

    def test_says_api_equivalent_not_billed(self, tmp_path):
        """Runs go through a subscription; a bare '$' reads as money spent."""
        root = _corpus(tmp_path, 1)
        (root / "batch_costs.jsonl").write_text(
            json.dumps({"paper": "a", "total_cost_usd": 1.0,
                        "input_tokens": 10, "output_tokens": 1}) + "\n")
        r = runner.invoke(app, ["usage", str(root)])
        assert "API-equivalent" in r.output

    def test_missing_costs_file_exits_nonzero(self, tmp_path):
        r = runner.invoke(app, ["usage", str(_corpus(tmp_path, 1))])
        assert r.exit_code != 0


class TestDuplicateTextWarning:
    """Two directories holding the same text cannot both be their own paper.

    MEASURED on `cerebrolysin_papers/` (309 directories, Dan's working corpus):
    19 hold publisher furniture instead of an article, and 14 of those are
    byte-identical to another directory. Eight different DOIs, spanning
    International Clinical Psychopharmacology, Journal of Hypertension,
    Behavioural Pharmacology, Neuroreport and Anesthesia & Analgesia, all hold
    the same 6,777-character Lippincott author-permission page. Five more all
    hold the same 30,542-character Bentham Science media kit, which is an
    advertising brochure.

    None of them is caught by the full-text gate or the supplement gate,
    because they are full of readable text -- it simply is not the paper's. A
    sweep of an advertisement finds no statistics, completes for less than a
    real paper costs, and reports no problems found.

    Warned, not skipped: at most one of each group is wrong and nothing here
    can tell which, so dropping both would discard a possibly-good paper to fix
    a corpus defect that belongs to whoever assembled it.
    """

    def test_identical_bodies_are_reported(self, tmp_path):
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 4, same_text=True)),
                                "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "same text in >1 directory" in r.output

    def test_the_directories_are_named(self, tmp_path):
        """A count alone is not actionable -- the operator has to go and look."""
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 3, same_text=True)),
                                "--dry-run", "--backend", "claude"])
        assert "10.1234--paper000" in r.output
        assert "10.1234--paper001" in r.output

    def test_a_normal_corpus_is_not_warned_about(self, tmp_path):
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 5)), "--dry-run", "--backend", "claude"])
        assert "same text in >1 directory" not in r.output

    def test_they_are_still_run(self, tmp_path):
        """Included, not skipped. The count in `to run` must not drop."""
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 4, same_text=True)),
                                "--dry-run", "--backend", "claude"])
        assert "INCLUDED" in r.output

    # -- The docling-cache fallback. A corpus fetched PDF-only carries no
    # body.md at all, and the markdown-only screen silently gave it no
    # duplicate check whatsoever -- the same furniture-fetch defect, invisible
    # on exactly the corpora the retired body.md workflow no longer feeds.

    @staticmethod
    def _pdf_only(tmp_path, texts):
        """One PDF-only paper per text, each with a planted extraction cache."""
        from forensic_metascience_ai_toolkit.extraction import docling_tables as dl
        root = tmp_path / "corpus"
        root.mkdir()
        for i, text in enumerate(texts):
            d = root / f"10.1234--pdfonly{i}"
            d.mkdir()
            pdf = d / f"10.1234--pdfonly{i}.pdf"
            pdf.write_bytes(b"%PDF-1.4 " + str(i).encode())   # distinct bytes
            cache = dl._cache_path(pdf)
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_text(json.dumps({
                "text": text, "tables": [], "error": None, "n_tables": 0,
                "n_text_chars": len(text),
                "pages": [{"page_num": 1, "text": text}], "num_pages": 1,
                "source_format": "pdf", "extractor": "docling",
                "cache_schema": 4,
            }), encoding="utf-8")
        return root

    def test_a_pdf_only_corpus_dedups_from_the_extraction_cache(self, tmp_path):
        kit = "This journal's media kit. We enrolled n = 40, p = .03."
        r = runner.invoke(app, ["batch", str(self._pdf_only(tmp_path, [kit, kit])),
                                "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "same text in >1 directory" in r.output
        assert "10.1234--pdfonly0" in r.output
        assert "10.1234--pdfonly1" in r.output

    def test_distinct_cache_texts_are_not_warned_about(self, tmp_path):
        r = runner.invoke(app, ["batch", str(self._pdf_only(
            tmp_path, ["Paper A. n = 40, p = .03.", "Paper B. n = 41, p = .04."])),
            "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "same text in >1 directory" not in r.output

    def test_markdown_stays_preferred_over_the_cache(self, tmp_path):
        """Markdown is the cheaper read and keeps deciding when present: two
        papers with DISTINCT bodies must not be paired by identical caches."""
        root = self._pdf_only(tmp_path, ["identical cache", "identical cache"])
        for i in range(2):
            (root / f"10.1234--pdfonly{i}" / "body.md").write_text(
                f"# distinct body of paper {i}")
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "same text in >1 directory" not in r.output


class TestSupplementIntegrityInThePlan:
    """The batch plan READS BACK fetchpdf's integrity manifests.

    A real corpus held 30 git-lfs pointer stubs where its supplementary
    spreadsheets should have been, each 130 bytes standing in for tens of KB,
    every pointer's oid matching the sha256 the manifest recorded -- proof the
    bytes were fetched intact and something afterward replaced them. Nothing
    noticed, because the metadata was only ever written. A hollow supplement
    reads downstream as "this paper published no data", which this toolkit
    treats as a finding against the authors.

    Best-effort in every direction: damage informs the plan and never skips a
    paper; an unimportable auditor is a NAMED absence with the standalone
    command; an audit crash never blocks the batch.
    """

    @staticmethod
    def _with_stub(tmp_path):
        __import__("pytest").importorskip("fetchpdf.retrieval.verify")
        root = _corpus(tmp_path, 2)
        d = root / "10.1234--paper000"
        supp = d / "10.1234--paper000_supplementary_info_1_tables.xlsx"
        supp.write_bytes(
            b"version https://git-lfs.github.com/spec/v1\n"
            b"oid sha256:" + b"0" * 64 + b"\nsize 9362\n")
        (d / "10.1234--paper000_supplementary_info.json").write_text(json.dumps(
            {"files": [{"filename": supp.name, "bytes": 9362,
                        "sha256": "0" * 64}]}))
        return root

    def test_an_lfs_stub_is_surfaced_with_its_paper_and_verdict(self, tmp_path):
        r = runner.invoke(app, ["batch", str(self._with_stub(tmp_path)),
                                "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "damaged" in r.output
        # fetchpdf's own verdict vocabulary, per paper -- a bare count is not
        # actionable, and a renamed verdict could disagree with fetchpdf-verify.
        line = next(l for l in r.output.splitlines() if "lfs_pointer" in l)
        assert "paper000" in line

    def test_damage_informs_but_never_skips(self, tmp_path):
        r = runner.invoke(app, ["batch", str(self._with_stub(tmp_path)),
                                "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "SKIP  10.1234--paper000" not in r.output
        assert "INCLUDED" in next(
            l for l in r.output.splitlines() if "damaged" in l)
        assert "2" in next(l for l in r.output.splitlines() if "to run" in l)

    def test_an_intact_supplement_reads_as_intact(self, tmp_path):
        import hashlib
        __import__("pytest").importorskip("fetchpdf.retrieval.verify")
        root = _corpus(tmp_path, 1)
        d = root / "10.1234--paper000"
        payload = b"col1,col2\n1,2\n"
        supp = d / "10.1234--paper000_supplementary_info_1_data.csv"
        supp.write_bytes(payload)
        (d / "10.1234--paper000_supplementary_info.json").write_text(json.dumps(
            {"files": [{"filename": supp.name, "bytes": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest()}]}))
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "1 file(s) intact" in r.output
        assert "damaged" not in r.output

    def test_no_manifests_is_not_a_clean_bill(self, tmp_path):
        """'Nothing was verifiable' and 'everything verified' are different
        facts; a corpus fetched without manifests must get the first."""
        __import__("pytest").importorskip("fetchpdf.retrieval.verify")
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 2)), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "no manifests to verify" in r.output
        assert "intact" not in r.output

    def test_unimportable_auditor_is_a_named_absence(self, tmp_path, monkeypatch):
        """The standalone command is printed -- never silence. sys.modules[x] =
        None makes `from x import ...` raise ImportError, whether or not the
        real package is installed here."""
        import sys
        monkeypatch.setitem(sys.modules, "fetchpdf.retrieval.verify", None)
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 2)), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "UNCHECKED" in r.output
        assert "fetchpdf-verify" in r.output, "the standalone command must be named"

    def test_an_audit_crash_does_not_block_the_batch(self, tmp_path, monkeypatch):
        pytest = __import__("pytest")
        v = pytest.importorskip("fetchpdf.retrieval.verify")

        def boom(root, verify_hashes=True):
            raise RuntimeError("disk went away")

        monkeypatch.setattr(v, "audit_tree", boom)
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 2)), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "UNCHECKED" in r.output
        assert "fetchpdf-verify" in r.output


class TestUnreadableIsNotOverridable:
    """`--ok-if-supplementary-missing` was waving through papers with no text at all.

    `gate` refuses two different things: a paper whose supplement is missing,
    and a paper whose text could not be read (`missing: None` -- the question
    was never answered). Both landed in one bucket, so the flag that trades
    partial coverage for a run also bought a run on a document nobody read.

    The comment on the full-text gate says it runs "FIRST and unconditionally"
    for exactly this reason, but it tests whether a FILE EXISTS -- and a
    scanned paper has a perfectly good PDF with no text in it, so it sailed
    through. `--ok-if-supplementary-missing` then included it and the sweep would have
    been paid for.
    """

    @staticmethod
    def _with_scan(tmp_path):
        root = tmp_path / "corpus"
        root.mkdir()
        for i in range(2):
            d = root / f"10.1234--real{i}"
            d.mkdir()
            (d / "body.md").write_text(
                f"# Methods\nWe enrolled n = {40 + i} participants, p = .0{i + 1}.")
        # A scan: pages that open cleanly and hold nothing but a stamp.
        fitz = __import__("pytest").importorskip("fitz")
        d = root / "10.1234--scan"
        d.mkdir()
        doc = fitz.open()
        for _ in range(8):
            page = doc.new_page()
            page.insert_text((40, 30), "Downloaded from example.org by guest "
                                       "on 12 March 2021", fontsize=6)
        doc.save(str(d / "10.1234--scan.pdf"))
        doc.close()
        return root

    def test_an_unextracted_pdf_is_not_called_a_scan(self, tmp_path):
        """Cache miss used to print 'scanned or corrupt'. Measured 2026-08-20
        on nina_mazar/grok_test: 5 readable PDFs skipped under that label."""
        r = runner.invoke(app, ["batch", str(self._with_scan(tmp_path)), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        assert "scanned or corrupt" not in r.output
        assert "not extracted" in r.output
        row = next(l for l in r.output.splitlines() if "to run" in l)
        assert "3" in row, f"unextracted PDF must stay in to-run, got: {row!r}"

    def test_ok_if_supplementary_missing_does_not_buy_a_run_on_a_true_scan(
            self, tmp_path):
        root = self._with_scan(tmp_path)
        self._plant_empty_cache(root / "10.1234--scan" / "10.1234--scan.pdf")
        r = runner.invoke(app, ["batch", str(root),
                                "--dry-run", "--backend", "claude", "--ok-if-supplementary-missing"])
        assert "no readable text" in r.output
        row = next(l for l in r.output.splitlines() if "to run" in l)
        assert "2" in row, f"the scan was waved through: {row!r}"
        assert "SKIP  10.1234--scan" in r.output

    def test_an_extracted_empty_pdf_is_filed_as_scanned(self, tmp_path):
        """Two different refusals need two different words. After the cache
        is filled and still empty, 'scanned or corrupt' is the honest label."""
        root = self._with_scan(tmp_path)
        self._plant_empty_cache(root / "10.1234--scan" / "10.1234--scan.pdf")
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        assert "scanned or" in r.output
        assert "SKIP  10.1234--scan" in r.output

    @staticmethod
    def _plant_empty_cache(pdf):
        import json
        from forensic_metascience_ai_toolkit.extraction import docling_tables as dl
        cache = dl._cache_path(pdf)
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({
            "text": "", "tables": [], "error": None, "n_tables": 0,
            "n_text_chars": 0,
            "pages": [{"page_num": 1, "text": ""}], "num_pages": 1,
            "source_format": "pdf", "extractor": "docling", "cache_schema": 4,
        }), encoding="utf-8")


class TestSupplementFlagIsNotAnUnreadabilityOverride:
    """`--supplement <file>` bypassed the unreadability refusal too.

    `_supplement_gate` short-circuited the whole audit whenever a file was
    passed: it overwrote `missing = False` and returned `proceed: True`
    without ever consulting the text. But the two questions are different. The
    attachment answers "do we hold the supplement"; it says nothing about
    whether we can read the article it belongs to, and it cannot make a scan
    that was never OCR'd readable.
    """

    @staticmethod
    def _scan_dir(tmp_path):
        fitz = __import__("pytest").importorskip("fitz")
        d = tmp_path / "scan"
        d.mkdir()
        doc = fitz.open()
        for _ in range(8):
            doc.new_page().insert_text(
                (40, 30), "Downloaded from example.org by guest", fontsize=6)
        doc.save(str(d / "p.pdf"))
        doc.close()
        return d

    def test_a_supplied_file_does_not_make_a_scan_readable(self, tmp_path):
        from forensic_metascience_ai_toolkit.cli import _supplement_gate
        si = tmp_path / "si.docx"
        si.write_bytes(b"PK\x03\x04")
        g = _supplement_gate(self._scan_dir(tmp_path), [si], allow_incomplete=False)
        assert g["proceed"] is False
        assert g["audit"].get("text_available") is False

    def test_a_readable_paper_still_accepts_the_supplied_file(self, tmp_path):
        from forensic_metascience_ai_toolkit.cli import _supplement_gate
        d = tmp_path / "real"
        d.mkdir()
        (d / "body.md").write_text(
            "See Supplementary Table S1. We enrolled n = 40, p = .03.")
        si = tmp_path / "si.docx"
        si.write_bytes(b"PK\x03\x04")
        g = _supplement_gate(d, [si], allow_incomplete=False)
        assert g["proceed"] is True
        assert g["audit"]["missing"] is False


class TestWorkers:
    """`--workers N` runs N papers at once, one paper per worker.

    The behaviour predates the flag: `--concurrency/-j` already drove
    `asyncio.Semaphore(n)` in batch_analyze, and `process_paper` holds that
    semaphore for a WHOLE paper, so the worker count and the in-flight paper
    count were always the same number. What was missing was the name people
    reach for. `--workers` is therefore an ALIAS onto the same parameter, not a
    second setting -- two settings would let `--workers 4 --concurrency 2` be
    accepted and then silently resolved by whichever the code read first.

    Nothing here spends money: every test is --dry-run.
    """

    def test_workers_flag_is_accepted(self, tmp_path):
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 4)), "--dry-run", "--backend", "claude",
                                "--workers", "3"])
        assert r.exit_code == 0, r.output
        assert "3" in next(l for l in r.output.splitlines() if "workers" in l)

    def test_workers_and_concurrency_are_one_parameter(self, tmp_path):
        """Both spellings must produce an identical plan, or they have drifted."""
        root = _corpus(tmp_path, 4)
        a = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "--workers", "4"])
        b = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "--concurrency", "4"])
        c = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "-j", "4"])
        assert a.exit_code == b.exit_code == c.exit_code == 0
        assert a.output == b.output == c.output

    def test_adding_the_alias_did_not_change_the_default(self, tmp_path):
        """The alias and the default are separate decisions. The default moved
        to 10 on 2026-08-23 (see TestDryRun.test_defaults_to_ten_workers); what
        this pins is that `--workers` remains an ALIAS and did not introduce a
        second setting with its own default."""
        root = _corpus(tmp_path, 3)          # built once: the helper is not idempotent
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        assert "10" in next(l for l in r.output.splitlines() if "workers" in l)
        explicit = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "-j", "10"])
        assert explicit.output == r.output

    def test_parallel_plan_does_not_claim_to_be_serial(self, tmp_path):
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 3)), "--dry-run", "--backend", "claude",
                                "--workers", "2"])
        assert "serial" not in r.output

    def test_underlying_script_takes_the_same_alias(self, tmp_path):
        """`metascience batch` and forensic_metascience_ai_toolkit/batch.py must not disagree
        about what the flag is called -- the CLI delegates straight to it."""
        import sys
        from pathlib import Path
        from forensic_metascience_ai_toolkit import batch as batch_analyze
        parser = batch_analyze.build_parser()
        assert parser.parse_args(["c", "--workers", "5"]).concurrency == 5
        assert parser.parse_args(["c", "--concurrency", "5"]).concurrency == 5


class TestAlreadyAnalysedIsOneDefinition:
    """`--skip-existing` must see an `analyze` run, or it re-bills a paid paper.

    MEASURED, 2026-08-14: ten papers in `high_value_biomedical_.../` held
    complete reviews costing $70.33, and `metascience batch --dry-run` reported
    "already analysed (skipped): 0" -- because `analyze` writes
    `forensic_review_<model>_<date>/` (cli.py) while the check tested only the
    bare `forensic_review/`. `--skip-existing` is on by default and promises
    "nothing is paid for twice".

    Nothing here spends money: every test is --dry-run or a direct call.
    """

    def test_an_analyze_run_counts_as_analysed(self, tmp_path):
        root = _corpus(tmp_path, 3)
        d = root / "10.1234--paper000" / "forensic_review_sonnet_08_14_2026"
        d.mkdir()
        (d / "report.md").write_text("x")
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        assert r.exit_code == 0, r.output
        row = next(l for l in r.output.splitlines() if "already analysed" in l)
        assert "1" in row, f"expected 1 skipped, got: {row!r}"
        assert "SKIP  10.1234--paper000" in r.output

    def test_an_empty_review_directory_is_not_a_review(self, tmp_path):
        """A crashed run leaves the directory but no report. The two old call
        sites disagreed: one tested the directory, one the file."""
        root = _corpus(tmp_path, 3)
        (root / "10.1234--paper000" / "forensic_review").mkdir()
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        row = next(l for l in r.output.splitlines() if "already analysed" in l)
        assert re_search_int(row) == 0, f"empty dir must not count: {row!r}"

    def test_the_viewer_bundle_is_not_a_review(self, tmp_path):
        root = _corpus(tmp_path, 3)
        b = root / "10.1234--paper000" / "forensic_review_sonnet_08_14_2026_bundle"
        b.mkdir()
        (b / "report.md").write_text("x")
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude"])
        row = next(l for l in r.output.splitlines() if "already analysed" in l)
        assert re_search_int(row) == 0, f"bundle must not count: {row!r}"

    def test_helper_returns_the_newest_review(self, tmp_path):
        import os
        from forensic_metascience_ai_toolkit.agent import completed_review
        p = tmp_path / "paper"
        (p / "forensic_review_opus_08_11_2026").mkdir(parents=True)
        (p / "forensic_review_opus_08_11_2026" / "report.md").write_text("old")
        (p / "forensic_review_sonnet_08_14_2026").mkdir()
        (p / "forensic_review_sonnet_08_14_2026" / "report.md").write_text("new")
        os.utime(p / "forensic_review_opus_08_11_2026" / "report.md", (1, 1))
        assert completed_review(p).name == "forensic_review_sonnet_08_14_2026"

    def test_helper_on_a_paper_with_no_review(self, tmp_path):
        from forensic_metascience_ai_toolkit.agent import completed_review
        p = tmp_path / "paper"; p.mkdir()
        assert completed_review(p) is None
        assert completed_review(tmp_path / "does-not-exist") is None


def re_search_int(row):
    """First integer in a rich table row (column widths shift; content does not)."""
    import re
    m = re.search(r"\b(\d+)\b", row)
    return int(m.group(1)) if m else None


class TestCostEstimateIsModelAware:
    """An opus quote must not be priced from sonnet's number.

    Opus is the DEFAULT for `analyze` and `batch`, and was absent from MEASURED,
    so it fell through to the sonnet constant -- every opus estimate was ~2.3x
    low against the measured $11.52 (n=12, verified against `model_usage`).
    """

    def test_opus_is_no_longer_unmeasured(self, tmp_path):
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 4)), "--dry-run", "--backend", "claude",
                                "--model", "opus"])
        assert r.exit_code == 0, r.output
        assert "UNMEASURED" not in r.output
        assert "opus" in next(l for l in r.output.splitlines() if "estimate basis" in l)

    def test_opus_and_sonnet_estimates_differ(self, tmp_path):
        root = _corpus(tmp_path, 4)
        o = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "--model", "opus"])
        s = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "--model", "sonnet"])
        est = lambda out: next(l for l in out.splitlines() if "estimated total" in l)
        assert est(o.output) != est(s.output), "model must move the estimate"

    def test_an_unknown_model_still_says_so(self, tmp_path):
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 3)), "--dry-run", "--backend", "claude",
                                "--model", "haiku"])
        assert "UNMEASURED" in r.output

    def test_history_for_another_model_does_not_price_this_one(self, tmp_path):
        """The bug: history overwrote the per-model constant unconditionally."""
        root = _corpus(tmp_path, 4)
        (root / "batch_costs.jsonl").write_text(
            "\n".join(json.dumps({"paper": f"p{i}", "model": "sonnet",
                                  "total_cost_usd": 5.0}) for i in range(3)))
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "--model", "opus"])
        basis = next(l for l in r.output.splitlines() if "estimate basis" in l)
        assert "history" not in basis, f"sonnet history must not price opus: {basis!r}"
        assert "opus" in basis

    def test_history_for_this_model_is_used_and_names_its_sample(self, tmp_path):
        root = _corpus(tmp_path, 4)
        (root / "batch_costs.jsonl").write_text(
            "\n".join(json.dumps({"paper": f"p{i}", "model": "opus",
                                  "total_cost_usd": 9.0}) for i in range(3)))
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "--model", "opus"])
        basis = next(l for l in r.output.splitlines() if "estimate basis" in l)
        assert "history" in basis and "opus" in basis and "n=3" in basis

    def test_legacy_rows_without_a_model_are_not_guessed_at(self, tmp_path):
        """Both pre-existing batch_costs.jsonl files predate the model column."""
        root = _corpus(tmp_path, 4)
        (root / "batch_costs.jsonl").write_text(
            json.dumps({"paper": "p0", "total_cost_usd": 5.0}))
        r = runner.invoke(app, ["batch", str(root), "--dry-run", "--backend", "claude", "--model", "opus"])
        basis = next(l for l in r.output.splitlines() if "estimate basis" in l)
        assert "history" not in basis, f"unlabelled rows must not be claimed: {basis!r}"


class TestCostLedgerRecordsWhatItReports:
    def test_the_row_carries_model_and_wall_seconds(self, tmp_path):
        """`_print_batch_usage` sums `total_wall_seconds`; nothing wrote it, so
        the 'total runtime' row was always 0 and hidden by its own `if secs:`."""
        import sys
        from pathlib import Path as _P
        import inspect

        from forensic_metascience_ai_toolkit import batch as batch_analyze
        src = inspect.getsource(batch_analyze.process_paper)
        for field in ("\"model\"", "\"total_wall_seconds\"",
                      "\"cache_read_input_tokens\"", "\"primary_billed_model\""):
            assert field in src, f"cost ledger row is missing {field}"


class TestUsageGuardPreCheckForwardsBackend:
    def test_the_pre_check_passes_backend(self, tmp_path):
        """process_paper()'s explicit pre-call `usage_guard()` -- run BEFORE
        analyze_paper(), so a batch stays protected even if the internal hook
        inside _run_stage is ever refactored away -- must forward
        backend=args.backend.

        A bare `usage_guard()` resolves its backend the same way
        `resolve_backend(None)` always has: explicit arg, then
        METASCIENCE_LLM_CLI, then "claude". `--backend grok` is a CLI flag,
        not that env var, so an unforwarded call silently probed the
        OPERATOR's own Claude Code account instead of Grok's -- which has no
        usage probe at all (Backend.supports_usage_probe=False) and should
        have made this a no-op.

        MEASURED 2026-08-19: a `metascience batch ... --backend grok` run hit
        the operator's unrelated Claude weekly quota at 100%, and
        WeeklyLimitReached raised at this call site -- BEFORE the
        try/except below that would have handled it and logged a clean
        stop. The uncaught raise propagated through asyncio.gather() (which
        does not cancel sibling tasks on the first exception), while a
        second paper had already started a concurrent _run_text_track()
        task. asyncio.run()'s teardown then hung trying to unwind that
        orphaned task -- surfacing to the operator as a frozen batch that
        needed Ctrl-C, printing "Task was destroyed but it is pending!".
        """
        import inspect
        import sys
        from pathlib import Path as _P
        from forensic_metascience_ai_toolkit import batch as batch_analyze
        src = inspect.getsource(batch_analyze.process_paper)
        assert "usage_guard(backend=" in src, (
            "the pre-check usage_guard() call must forward backend= -- a "
            "bare usage_guard() always resolves to the Claude probe "
            "regardless of --backend grok"
        )


class TestForensicToolsNeverRanDump:
    def test_a_refuse_leaves_a_diagnostic_not_just_a_traceback(self, tmp_path):
        import sys
        from pathlib import Path as _P
        from forensic_metascience_ai_toolkit import batch as batch_analyze
        from forensic_metascience_ai_toolkit.llm_backend import ForensicToolsNeverRan

        paper = tmp_path / "10.1234--p"
        paper.mkdir()
        stage = {
            "messages": [
                {"type": "assistant", "message": {"content": [
                    {"type": "tool_use", "name": "Read", "id": "1",
                     "input": {}},
                ]}},
            ],
            "mcp_discovery": {"declared": True, "ok": True},
            "llm_backend": "grok",
            "input_tokens": 12,
            "output_tokens": 3,
            "wall_seconds": 19.0,
        }
        exc = ForensicToolsNeverRan("0 on-list calls", stage=stage)
        path = batch_analyze._dump_forensic_tools_never_ran(
            paper, "forensic_review", exc)
        assert path is not None and path.exists()
        data = json.loads(path.read_text())
        assert data["n_messages"] == 1
        assert data["llm_backend"] == "grok"
        assert data["ledger_tools"][0]["tool"] == "Read"
        assert data["ledger_tools"][0]["surface"] == "builtin_allowed"
        # A dump that only restates the exception is not a diagnostic.
        assert data["event_summary"][0]["tools"] == ["Read"]

    def test_the_dump_carries_the_empty_json_the_model_emitted(self, tmp_path):
        """Measured 2026-08-20: grok dumped findings:[] in 173 tokens and the
        diagnostic omitted result/structured_output, so the empty skeleton
        was only in ~/.grok/sessions after sandbox cleanup."""
        import sys
        from pathlib import Path as _P
        from forensic_metascience_ai_toolkit import batch as batch_analyze
        from forensic_metascience_ai_toolkit.llm_backend import ForensicToolsNeverRan

        paper = tmp_path / "10.18332--tid--209827"
        paper.mkdir()
        empty = {
            "schema_version": "1.0", "paper_id": "x",
            "findings": [],
            "coverage": {"stats_found": 0, "tools_run": []},
            "anatomy": {"studies": [], "variables": [], "tests": []},
        }
        stage = {
            "messages": [
                {"type": "system", "subtype": "init",
                 "tools": ["read_file", "search_tool", "use_tool"],
                 "mcp_servers": [{"name": "forensic_metascience"}]},
                {"type": "assistant", "message": {"content": [
                    {"type": "text", "text": json.dumps(empty)},
                ]}},
                {"type": "result", "result": json.dumps(empty),
                 "structured_output": empty, "stop_reason": "end_turn",
                 "num_turns": 1},
            ],
            "mcp_discovery": {"declared": True, "ok": True},
            "llm_backend": "grok",
            "result": json.dumps(empty),
            "structured_output": empty,
            "stop_reason": "end_turn",
            "num_turns": 1,
            "tool_calls": 0,
            "input_tokens": 30370,
            "output_tokens": 173,
            "wall_seconds": 37.0,
        }
        exc = ForensicToolsNeverRan("0 on-list calls", stage=stage)
        path = batch_analyze._dump_forensic_tools_never_ran(
            paper, "forensic_review", exc)
        data = json.loads(path.read_text())
        assert data["structured_output"]["findings"] == []
        assert data["result"]
        assert "findings" in data["result"]
        assert data["stop_reason"] == "end_turn"
        assert data["num_turns"] == 1
        assert data["init_tools"] == ["read_file", "search_tool", "use_tool"]
        assert "findings" in (data.get("assistant_text") or "")
        msgs = paper / "forensic_review" / "messages.stage1.json"
        assert msgs.is_file()
        assert json.loads(msgs.read_text())[0]["type"] == "system"

    def test_a_refuse_is_billed(self):
        import sys
        from pathlib import Path as _P
        from forensic_metascience_ai_toolkit import batch as batch_analyze
        from forensic_metascience_ai_toolkit.llm_backend import ForensicToolsNeverRan

        first = {"cost_usd": 0.01, "input_tokens": 100, "output_tokens": 173,
                 "wall_seconds": 37.0, "cache_creation_input_tokens": 0,
                 "cache_read_input_tokens": 0}
        second = {"cost_usd": 0.02, "input_tokens": 200, "output_tokens": 50,
                  "wall_seconds": 40.0, "cache_creation_input_tokens": 1,
                  "cache_read_input_tokens": 2}
        exc = ForensicToolsNeverRan(
            "0 on-list calls", stage=second, prior_stages=[first])
        row = batch_analyze._cost_fields_from_refuse(exc)
        assert row["total_cost_usd"] == 0.03
        assert row["input_tokens"] == 300
        assert row["n_attempts"] == 2

    def test_the_handled_refuse_does_not_print_a_traceback(self):
        import inspect
        import sys
        from pathlib import Path as _P
        from forensic_metascience_ai_toolkit import batch as batch_analyze
        src = inspect.getsource(batch_analyze.process_paper)
        # One print_exc, on the generic Exception path. The known refuse
        # used to dump a traceback that looked like a batch crash.
        assert src.count("traceback.print_exc()") == 1
        assert "except ForensicToolsNeverRan" in src
        handler = src.split("except ForensicToolsNeverRan")[1].split("except ")[0]
        assert "print_exc" not in handler


class TestBackendIsRequired:
    """There is no silent default to Claude Code: a run that calls a model
    must name its backend, and METASCIENCE_LLM_CLI does not stand in for it."""

    def test_batch_without_backend_is_refused(self, tmp_path, monkeypatch):
        monkeypatch.setenv("METASCIENCE_LLM_CLI", "claude")
        r = runner.invoke(app, ["batch", str(_corpus(tmp_path, 2)), "--dry-run"])
        assert r.exit_code == 2, r.output
        assert "--backend is required" in r.output

    def test_analyze_without_backend_is_refused(self, tmp_path):
        paper = tmp_path / "paper.md"
        paper.write_text("# A paper\n")
        r = runner.invoke(app, ["analyze", str(paper), "--no-usage-guard"])
        assert r.exit_code == 2, r.output
        assert "--backend is required" in r.output

    def test_a_pipeline_that_calls_no_model_needs_no_backend(self):
        from forensic_metascience_ai_toolkit import pipeline_config as pc
        assert not pc.load("image_detect").uses_llm
        assert not pc.load("raw_data_only").uses_llm
        for name in ("full", "tools_only", "proofreading_only", "image_only"):
            assert pc.load(name).uses_llm, name
