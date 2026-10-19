"""Did the payload arrive? The third leg of the def-use analysis.

GREG, 2026-08-15: "can you check whether all of the tests we have in place are
actually linking up properly to the models, such that all relevant information
is passed on appropriately?"

`handoff.audit` already asks whether a stage's output is PRODUCED and CONSUMED.
This asks the question underneath both: when the model reached for something,
did it get it?

MEASURED over all 2,706 archived tool calls: 46 returned nothing usable and 29
were never recovered. One `extract_supplement` overflowed at 3,241,286
characters. `result_truncated` had been computed into the ledger for months and
read by no renderer -- so a supplement could go unread and the report would not
say so, while the coverage denominator went on counting items the model could
not have seen.

BOTH OF THIS FUNCTION'S OWN EARLY BUGS RAN TOWARD OVERSTATING OUR FAILURE, which
is why the recovery tests below are as detailed as the loss tests. An instrument
that cries wolf about its own side gets switched off exactly as fast as one that
stays silent.
"""
from forensic_metascience_ai_toolkit.handoff import delivery_audit

OVERFLOW = ("Error: result (3,241,286 characters across 139,991 lines) exceeds "
            "maximum allowed tokens. Output has been saved to /tmp/x")


def _call(seq, tool, result, **inp):
    return {"seq": seq, "tool": f"mcp__forensic_metascience__{tool}",
            "input": inp, "result": result}


class TestARefusalIsNotAFailure:
    """A tool that declines to judge has delivered its answer. Counting those
    would bury the real thing under routine noise -- and the refusals are a
    designed feature of this system, not an error."""

    def test_a_declining_tool_is_not_undelivered(self):
        d = delivery_audit([_call(1, "check_estimate_ci", '{"severity": "indeterminate", '
                                  '"explanation": "CI bounds arrive reversed"}')])
        assert d["ok"] is True and d["n_undelivered"] == 0

    def test_an_error_FIELD_is_not_an_error_RESULT(self):
        d = delivery_audit([_call(1, "grim_check", '{"error": false, "consistent": true}')])
        assert d["n_undelivered"] == 0


class TestOverflowIsCaught:
    def test_an_overflowed_extraction_is_undelivered(self):
        d = delivery_audit([_call(1, "extract_supplement", OVERFLOW, path="/p/s001.docx")])
        assert d["n_undelivered"] == 1 and d["n_extraction"] == 1
        assert d["lost"][0]["kind"] == "overflow"

    def test_the_note_names_the_consequence_for_coverage(self):
        d = delivery_audit([_call(1, "extract_supplement", OVERFLOW, path="/p/s001.docx")])
        assert "could not have seen" in d["note"]
        assert "OUR pipe" in d["note"]


class TestRecoveryIsRecognised:
    """The commonest recovery is switching tool SHAPE, not paging the same call.
    The first cut looked only for first_page/last_page/max_chars and scored
    Romano's five successful per-table fetches as no recovery at all."""

    PATH = "/p/EAT-58-1072-s001.docx"

    def test_a_later_successful_call_on_the_same_path_counts_as_recovery(self):
        d = delivery_audit([
            _call(1, "extract_supplement", OVERFLOW, path=self.PATH),
            _call(2, "get_supplement_table", '{"label": "Table 2", "cells": []}', path=self.PATH),
        ])
        assert d["n_undelivered"] == 1, "the loss still happened and is still recorded"
        assert d["n_unrecovered"] == 0, "and it was recovered by a narrower call"

    def test_a_paged_retry_also_counts(self):
        d = delivery_audit([
            _call(1, "extract_pdf", OVERFLOW, pdf_path="/p/a.pdf"),
            _call(2, "extract_pdf", '{"text": "page 4"}', pdf_path="/p/a.pdf", first_page=4),
        ])
        assert d["n_unrecovered"] == 0

    def test_an_overflow_with_no_later_success_is_unrecovered(self):
        d = delivery_audit([_call(1, "extract_supplement", OVERFLOW, path=self.PATH)])
        assert d["n_unrecovered"] == 1

    def test_a_success_on_a_DIFFERENT_path_does_not_excuse_it(self):
        d = delivery_audit([
            _call(1, "extract_supplement", OVERFLOW, path=self.PATH),
            _call(2, "extract_supplement", '{"text": "fine"}', path="/p/other.docx"),
        ])
        assert d["n_unrecovered"] == 1


class TestItIsConsumed:
    def test_the_run_records_it(self):
        import pathlib
        src = (lambda r: (r / "src/forensic_metascience_ai_toolkit/agent.py").read_text(encoding="utf-8")
                   + (r / "src/forensic_metascience_ai_toolkit/parallel.py").read_text(encoding="utf-8")
                   )(pathlib.Path(__file__).resolve().parents[1])
        # The live pipeline writes it in `parallel._write_delivery_and_source_coverage`.
        assert 'meta["delivery"] = delivery_audit(' in src

    def test_the_viewer_renders_it(self):
        import pathlib
        v = (pathlib.Path(__file__).resolve().parents[1]
             / "src/forensic_metascience_ai_toolkit/bundle.py").read_text(encoding="utf-8")
        assert "rm.delivery" in v, \
            "computed, attached, and rendered by nothing is this repo's signature defect"
        assert "Information that did not arrive" in v


class TestOnTheRealArchive:
    def test_the_measured_figures_still_hold(self):
        import json
        import pathlib

        import pytest
        root = pathlib.Path(__file__).resolve().parents[1]
        lost = unrec = calls = 0
        for p in root.glob("**/toolcalls.stage*.json"):
            if "scratchpad" in str(p):
                continue
            try:
                led = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            d = delivery_audit(led)
            calls += d["n_calls"]; lost += d["n_undelivered"]; unrec += d["n_unrecovered"]
        if calls < 500:
            pytest.skip("archive not in this checkout")
        # Recomputed rather than asserted exactly: the archive grows with every
        # run. What is pinned is that the instrument still FINDS the problem and
        # still distinguishes recovered from not.
        assert lost > 20, f"only {lost} undelivered payloads found in {calls} calls"
        assert 0 < unrec < lost, (unrec, lost)


def _cold_caches(paper_dir) -> list[str]:
    """Which of this paper's SUPPLEMENT PDFs `audit` cannot read cheaply.

    THE PRECONDITION THESE TESTS ACQUIRED ON 2026-08-16, when
    `extraction/pdf.py` became docling-only and cache-only. `audit` walks the
    paper through `prepass.paper_tables(include_supplements=True)`, which reads
    each supplement with `extract_text_with_tables`. That function no longer
    falls back to pdfplumber, so a cache stored before schema 4 -- no per-page
    text -- comes back `unreadable: True, num_pages: 0`, and
    `supplements_read.extract_supplement_full` correctly routes an unreadable
    PDF into the OCR seam: every page rendered at 300 dpi and transcribed.

    THE SUPPLEMENTS AND NOT THE ARTICLE, deliberately. The first cut of this
    gate asked every declared PDF and was wrong in the direction that hurts
    most: it skipped tests that could have run. The article is read either from
    the publisher XML or through `docling_tables.extract_pdf_tables`, which
    serves a cache of ANY schema and never OCRs -- MEASURED on this paper,
    whose article cache is still schema 2 while `audit` completes in 36 s. Only
    `extract_supplement_full` reaches the OCR seam, and only for the files
    `supplements.present_files` enumerates, so those are the files to ask about.
    A guard wider than the defect is a guard that stops guarding.

    MEASURED 2026-08-17 on this paper, one machine, one corpus, HEAD against
    the working tree: `paper_tables(include_supplements=True)` took 30.3 s with
    the pdfplumber fallback in place and 406.8 s without it -- 13.4x, all of it
    the 11-page supplement being rendered and OCR'd from scratch, on every
    call. Reading that supplement directly reports `unreadable=False, pages=11,
    tables=8` before and `unreadable=True, num_pages=0` after. Nothing about
    the file changed; OUR cache is stale. `audit` walks it three times over
    (`paper_tables`, then `build_manifest` twice, which walks it again), so one
    audit is ~20 minutes and the class below makes five of them.

    So the honest precondition is not "is the paper here" but "can it be read
    without the layout model", and the skip names the command that fixes it.
    `analyze` now runs that command itself (`ensure_paper_extracted`), which is
    why this is a checkout-freshness gate and not a permanent exclusion.
    """
    from forensic_metascience_ai_toolkit import supplements
    from forensic_metascience_ai_toolkit.extraction import docling_tables as dl

    cold: list[str] = []
    for name in (supplements.present_files(paper_dir) or []):
        if not str(name).lower().endswith(".pdf"):
            continue
        usable, why = dl.cache_status(paper_dir / name)
        if not usable:
            cold.append(f"{name}: {why}")
    return cold


class TestTheAuditCarriesAllThreeLegs:
    """`handoff-audit` is now the whole def-use question in one command.

    rows          -- is each stage's output PRODUCED and CONSUMED
    reachability  -- can the model call every registered tool at all
    delivery      -- did what it asked for actually ARRIVE

    Static, static, and post-hoc respectively, which is why `delivery` reports
    NOT MEASURED on a pre-flight instead of clean.

    These run on a REAL paper and a REAL archived run, which is the point of
    them and also the reason they now carry a precondition: since extraction
    went docling-only, `audit` can only read this paper cheaply if its cache is
    fresh. `_cold_caches` explains what happens when it is not, with the
    measurement.
    """

    PAPER = "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1001--jamanetworkopen.2023.37679"
    RUN = PAPER + "/forensic_review_2026-08-13"

    def _audit(self, run=None):
        import pathlib

        import pytest
        from forensic_metascience_ai_toolkit.handoff import audit
        root = pathlib.Path(__file__).resolve().parents[1]
        paper = root / self.PAPER
        if not paper.is_dir():
            pytest.skip("paper not in this checkout")
        # SKIPPED, NOT ASSERTED AWAY. Running `audit` against a cold cache does
        # not fail these tests, it OCRs eleven pages per call and answers
        # minutes later -- so the skip is the difference between an honest
        # "not measured here" and a suite that looks hung. See `_cold_caches`.
        cold = _cold_caches(paper)
        if cold:
            pytest.skip(
                "these supplements have no schema-4 docling cache, so `audit` "
                "would OCR them page by page instead of reading them ("
                + "; ".join(cold) + "). Run `metascience extract-tables "
                f"--force {self.PAPER}`.")
        return audit(paper, (root / run) if run else None)

    def test_a_preflight_reports_delivery_as_not_measured_not_clean(self):
        d = self._audit()["delivery"]
        assert d["ok"] is None and "not measured" in d["note"]

    def test_a_run_gets_a_real_delivery_verdict(self):
        d = self._audit(self.RUN)["delivery"]
        assert d["ok"] in (True, False) and d["n_calls"] > 0

    def test_both_exits_attach_the_legs(self):
        """The first cut attached them only to the early return taken when no
        run is given, so a pre-flight got the new checks and a full audit
        silently did not -- the exact defect this module exists to detect."""
        for run in (None, self.RUN):
            a = self._audit(run)
            assert "reachability" in a and "delivery" in a, run

    def test_a_declared_cli_only_tool_is_not_reported_as_stranded(self):
        """Counting our own decision as a defect is the same error as missing
        one: an audit that reads our choices back to us gets ignored."""
        from forensic_metascience_ai_toolkit.registry import CLI_ONLY
        r = self._audit()["reachability"]
        assert r["ok"] is True and r["stranded"] == []
        assert set(r["cli_only"]) == set(CLI_ONLY)

    def test_ready_requires_all_three(self):
        from forensic_metascience_ai_toolkit.handoff import _finish
        base = {"ready": True, "reachability": {"ok": True}}
        assert _finish(dict(base), None)["ready"] is True
        stranded = {"ready": True, "reachability": {"ok": False}}
        assert _finish(dict(stranded), None)["ready"] is False
