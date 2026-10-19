"""A file we could not load must not look like a file with nothing in it.

TASK #166. `handoff.py` has detected a token overflow since 2026-08-15 --
`overflow = "exceeds maximum allowed tokens" in result[:400]` -- and filed the
result under `run_meta`, which report.md does not read and whose display path is
cut at 120 characters, mid-filename, on every path in this corpus. So the fact
was computed and no reader could learn from it WHICH file went missing, which is
this repository's first named failure mode (built, consumed by nothing) causing
its third (absence read as evidence).

MEASURED 2026-08-17 across every archived ledger in this checkout:

    17 files lost at least one fetch
    16 came back by another route -- a paged retry, a per-table fetch, or a read
       of the harness's spill file, which is the commonest of the three (21 of
       24 spilled overflows). Reporting those as lost would be crying wolf about
       our own side, which switches an instrument off as fast as silence does.
     1 never came back at all: 10.1038--s41537's supplementary workbook, 1,114,127
       characters, holding the latent-class model-selection statistics on which
       the paper's entire four-class result rests. That run disclosed it only
       because the model chose to write it into `not_checked` in prose.

So these tests pin two properties in opposite directions: a lost file is NAMED
and called unknown, and a recovered one is NOT reported as lost.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from tests.test_bundle import flat, review, section_html  # noqa: F401

from forensic_metascience_ai_toolkit.bundle import collect
from forensic_metascience_ai_toolkit.handoff import delivery_audit, undelivered_files

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "forensic_metascience_ai_toolkit"

SUPP = "/papers/x/EAT-58-1072-s001.docx"
OVERFLOW = ("Error: result (175,829 characters across 6,332 lines) exceeds "
            "maximum allowed tokens. Output has been saved to "
            "/home/u/.claude/tool-results/mcp-extract_supplement-1786913542808.txt.\n"
            "Format: Plain text")
SPILL = "/home/u/.claude/tool-results/mcp-extract_supplement-1786913542808.txt"


def _call(seq, tool, result, **inp):
    return {"seq": seq, "tool": f"mcp__forensic_metascience__{tool}",
            "input": inp, "result": result}


class TestALostFileIsNamed:
    def test_the_file_is_recorded_by_name(self):
        u = undelivered_files([_call(1, "extract_supplement", OVERFLOW, path=SUPP)])
        assert u["n_files"] == 1 and u["n_unread"] == 1
        f = u["files"][0]
        assert f["file"] == "EAT-58-1072-s001.docx", "a name, not a truncated path"
        assert f["path"] == SUPP
        assert f["status"] == "unread"

    def test_the_size_reported_is_the_PAYLOAD_not_the_error_string(self):
        """`result_chars` measures the error text -- 1,396 on the archived PNAS
        row while the message says 64,560. A reader told that 1,396 characters
        would not fit would rightly stop believing us."""
        u = undelivered_files([_call(1, "extract_supplement", OVERFLOW,
                                     path=SUPP)])
        assert u["files"][0]["chars"] == 175_829

    def test_it_says_UNKNOWN_and_never_that_the_file_is_empty(self):
        note = undelivered_files(
            [_call(1, "extract_supplement", OVERFLOW, path=SUPP)])["files"][0]["note"]
        assert "UNKNOWN" in note
        assert "not evidence that the file is empty" in note
        low = note.lower()
        for forbidden in ("no tables", "contains nothing", "was empty"):
            assert forbidden not in low, f"{forbidden!r} reads as a claim about the paper"

    def test_the_refusal_names_the_way_out(self):
        """A refusal must be actionable: name the input or command that fixes
        it, not merely the fact that something failed."""
        note = undelivered_files(
            [_call(1, "extract_supplement", OVERFLOW, path=SUPP)])["files"][0]["note"]
        assert "get_supplement_table" in note and "first_page" in note

    def test_a_tool_overflow_with_no_file_is_not_reported_as_a_file(self):
        """`check_regression_batch` overflows on its own output. Naming a file
        for it would put something in front of a reader that nothing in the run
        traces back to."""
        u = undelivered_files([_call(1, "check_regression_batch", OVERFLOW,
                                     rows=[{"b": 0.3}])])
        assert u["ok"] is True and u["files"] == []


class TestARecoveredFileIsNotReportedAsLost:
    """Both of `delivery_audit`'s early bugs ran toward overstating our own
    failure. These pin the other direction, which is where a coverage warning
    stops being believed."""

    def test_a_per_table_fetch_makes_it_partial_not_unread(self):
        u = undelivered_files([
            _call(1, "extract_supplement", OVERFLOW, path=SUPP),
            _call(2, "get_supplement_table", '{"label": "Table 2"}', path=SUPP),
        ])
        assert u["files"][0]["status"] == "partial"
        assert u["n_unread"] == 0 and u["n_partial"] == 1

    def test_reading_the_harness_SPILL_FILE_counts_as_delivery(self):
        """The commonest recovery of all: the harness parks the payload on disk
        and the model reads it back. Measured, 21 of the archive's 24 spilled
        overflows end this way -- including the PNAS run, where scoring only our
        own tools would have declared the ARTICLE unread while its text is
        plainly in the transcript."""
        u = undelivered_files([
            _call(1, "extract_supplement", OVERFLOW, path=SUPP),
            {"seq": 2, "tool": "Read", "input": {"file_path": SPILL},
             "result": '1\t{"text": "## Methods ..."}'},
        ])
        assert u["files"][0]["status"] == "partial", u["files"][0]["note"]

    def test_the_spill_path_is_matched_despite_the_full_stop(self):
        """The harness sentence ends `...txt.` -- the first cut kept the full
        stop, matched nothing, and scored all 21 recoveries as zero."""
        from forensic_metascience_ai_toolkit.handoff import _spill_path
        assert _spill_path(OVERFLOW) == SPILL

    def test_delivery_audit_also_credits_the_spill_read(self):
        d = delivery_audit([
            _call(1, "extract_supplement", OVERFLOW, path=SUPP),
            {"seq": 2, "tool": "Read", "input": {"file_path": SPILL},
             "result": '1\t{"text": "## Methods ..."}'},
        ])
        assert d["n_undelivered"] == 1, "the loss still happened and is recorded"
        assert d["n_unrecovered"] == 0, "and the payload did reach the model"

    def test_a_success_on_a_DIFFERENT_file_does_not_excuse_it(self):
        u = undelivered_files([
            _call(1, "extract_supplement", OVERFLOW, path=SUPP),
            _call(2, "extract_supplement", '{"text": "fine"}', path="/papers/x/other.docx"),
        ])
        assert u["n_unread"] == 1

    def test_partial_does_not_claim_the_rest_is_clean(self):
        note = undelivered_files([
            _call(1, "extract_supplement", OVERFLOW, path=SUPP),
            _call(2, "get_supplement_table", '{"label": "Table 2"}', path=SUPP),
        ])["files"][0]["note"]
        assert "not measured" in note and "UNKNOWN, not clean" in note

    def test_a_clean_run_says_so_without_a_file_list(self):
        u = undelivered_files([_call(1, "extract_pdf", '{"text": "ok"}',
                                     pdf_path="/papers/x/a.pdf")])
        assert u["ok"] is True and u["files"] == [] and u["n_files"] == 0

    def test_a_refusal_is_not_a_lost_file(self):
        u = undelivered_files([_call(1, "check_estimate_ci",
                                     '{"severity": "indeterminate"}',
                                     path=SUPP)])
        assert u["ok"] is True


class TestItReachesTheArtefact:
    """Detected in `handoff.py` since 2026-08-15 and reaching no reader is the
    defect, not the detection."""

    def test_the_viewer_renders_the_file_list(self):
        v = (SRC / "bundle.py").read_text(encoding="utf-8")
        assert "cs.undelivered" in v and "ud.files" in v
        assert "Files this review could not load" in v

    def test_the_call_level_table_names_the_file_too(self):
        """`lost[].input` is cut at 120 characters and every path in this corpus
        is longer -- the archived PNAS row ends `10.1073--pnas.08012`."""
        v = (SRC / "bundle.py").read_text(encoding="utf-8")
        i = v.index("Information that did not arrive")
        assert "x.file" in v[i - 900:i], "the table must name the file it lost"


class TestTheReportRenderer:
    def _cov(self, status="unread"):
        return {"undelivered": {
            "ok": False, "n_files": 1, "n_unread": int(status == "unread"),
            "n_partial": int(status != "unread"),
            "files": [{"file": "41537_2025_576_MOESM2_ESM.xlsx",
                       "status": status, "note": "`41537_2025_576_MOESM2_ESM.xlsx` "
                       "never reached this review -- UNKNOWN."}],
            "note": "1 file(s) this review reached for did not fully arrive."}}

class TestTheReaderSeesItInTheViewer:
    """Run the section the way a reader gets it, rather than grepping the
    source: a test that greps for a JS line passes just as happily when the
    block is built from the wrong array or never mounted at all."""

    def _payload(self, review, status="unread"):
        p = collect(review)
        u = undelivered_files([
            {"seq": 1, "tool": "mcp__forensic_metascience__extract_supplement",
             "input": {"path": SUPP}, "result": OVERFLOW}]
            + ([{"seq": 2, "tool": "Read", "input": {"file_path": SPILL},
                 "result": '1\t{"text": "..."}'}] if status == "partial" else []))
        # The viewer reads `cs.undelivered` from the payload's own
        # `coverage_summary` (the v2 document's top level); the serial
        # pipeline's `report_obj` copy is no longer read.
        p.setdefault("coverage_summary", {})["undelivered"] = u
        return p

    def test_the_lost_file_is_named_on_the_coverage_page(self, review, tmp_path):
        html = flat(section_html(self._payload(review), "coverage", tmp_path))
        assert "EAT-58-1072-s001.docx" in html
        assert "never loaded" in html

    def test_it_is_placed_above_the_coverage_figures_it_qualifies(self, review, tmp_path):
        """A denominator quoted before the reader knows a file never loaded is
        a denominator that misleads."""
        html = flat(section_html(self._payload(review), "coverage", tmp_path))
        assert html.index("EAT-58-1072-s001.docx") < html.index(
            "How much of the paper was checked")

    def test_the_page_says_it_is_OUR_gap(self, review, tmp_path):
        html = flat(section_html(self._payload(review), "coverage", tmp_path))
        assert "OUR gap" in html
        assert "not evidence that the file is empty" in html

    def test_a_recovered_file_is_not_shown_as_never_loaded(self, review, tmp_path):
        # The badge, not the word: the summary sentence legitimately contains
        # "0 never loaded at all", and asserting on the bare phrase would fail
        # on a correct page.
        html = flat(section_html(self._payload(review, "partial"), "coverage", tmp_path))
        assert "read in pieces" in html
        assert '<strong class="bad">never loaded' not in html

    def test_a_clean_run_shows_no_such_block(self, review, tmp_path):
        html = flat(section_html(collect(review), "coverage", tmp_path))
        assert "Files this review could not load" not in html


class TestOnTheRealArchive:
    """The three shapes, on the runs that produced them. Recomputed rather than
    hard-coded: the archive grows with every run, and what is pinned is that the
    instrument still separates a lost file from a recovered one."""

    def _ledger(self, rel):
        p = ROOT / rel
        if not p.is_file():
            pytest.skip(f"{rel} not in this checkout")
        return json.loads(p.read_text(encoding="utf-8"))

    def test_the_one_genuinely_lost_supplement_is_found(self):
        led = self._ledger("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1038--s41537-025-00576-3"
                           "/forensic_review_opus_08_09_2026/toolcalls.stage1.json")
        u = undelivered_files(led)
        assert u["n_unread"] == 1
        f = next(x for x in u["files"] if x["status"] == "unread")
        assert f["file"].endswith("41537_2025_576_MOESM2_ESM.xlsx")
        assert f["chars"] == 1_114_127

    def test_the_pnas_article_is_not_declared_unread(self):
        """It overflowed at 64,560 characters and the model read the spill file
        back on the very next call. Calling that article unread would discredit
        every finding in a run that was not starved at all."""
        led = self._ledger("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1073--pnas.0801268105"
                           "/forensic_review_2026-08-16/toolcalls.stage1.json")
        u = undelivered_files(led)
        assert u["n_unread"] == 0
        assert u["files"][0]["status"] == "partial"

    def test_the_romano_supplement_is_partial_not_lost(self):
        """Whole-file read overflowed, five per-table fetches came back, and one
        of those tables overflowed too -- so neither "lost" nor "clean" is the
        honest word."""
        led = self._ledger("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--eat.24415"
                           "/forensic_review_2026-08-13_supp/toolcalls.stage1.json")
        u = undelivered_files(led)
        f = next(x for x in u["files"] if x["file"] == "EAT-58-1072-s001.docx")
        assert f["status"] == "partial"
        assert "get_supplement_table" in f["tools"]

    def test_most_losses_are_recovered_across_the_whole_archive(self):
        """The instrument must not report the pipe as more broken than it is."""
        unread = partial = 0
        for p in ROOT.glob("**/toolcalls.stage*.json"):
            if "scratchpad" in str(p):
                continue
            try:
                led = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            u = undelivered_files(led)
            unread += u["n_unread"]
            partial += u["n_partial"]
        if unread + partial < 5:
            pytest.skip("archive not in this checkout")
        assert partial > unread * 5, (
            f"{unread} unread vs {partial} partial -- recovery is the common "
            "case, and an audit that says otherwise is crying wolf")
