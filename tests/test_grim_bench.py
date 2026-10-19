"""The GRIM recall ground truth (`benchmarks/grim/`).

Each scoring test pins a mistake the first version of `score.py` made on the
real reviews of 10.1371--journal.pone.0042828 (2026-10-17), every one of which
inflated a recall number rather than crashing:

* a GRIMMER failure (an SD test) counted as a GRIM detection;
* an `out_of_range` failure against a scale bound the model assumed counted
  as a GRIM detection;
* a finding's `quote` (the whole source row) and `inputs` (`means_tested`)
  counted as reporting every value they print, passing ones included.

The label tests run over EVERY set folder (`benchmarks/grim/<set>/` holding a
labels.jsonl): each set's labels are what its build_labels.py makes from its
research records, so a hand edit cannot drift from the recorded judgements.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

BENCH = Path(__file__).resolve().parents[1] / "benchmarks" / "grim"


def _load(path: Path, name: str):
    # Unique module names: benchmarks/litvak also has a `score.py`, and two
    # test files importing `score` in one worker would share one module.
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


verify = _load(BENCH / "verify_labels.py", "grim_bench_verify_labels")
score = _load(BENCH / "score.py", "grim_bench_score")

#: Every ground-truth set: a subfolder holding a labels.jsonl.
SETS = sorted(d for d in BENCH.iterdir() if (d / "labels.jsonl").is_file())


def _papers(set_dir: Path) -> list[dict]:
    return [json.loads(line) for line in
            (set_dir / "labels.jsonl").read_text().splitlines() if line.strip()]


def _cell(value, n, decimals=1, **kw):
    return {"id": "c001", "value": value, "n": n, "decimals": decimals,
            "items_k": 1, "kind": "mean", "n_source": "printed",
            "premise": "ok", **kw}


class TestArithmetic:
    @pytest.mark.parametrize("value,n,decimals,k,kind,want", [
        ("51.9", 6, 1, 1, "mean", "fails_both"),          # pone.0042828 Table 2
        ("16.5", 6, 1, 1, "mean", "passes"),              # 99/6
        ("6.62", 62, 2, 1, "mean", "fails_rounding_only"),  # Just 2014 Table 1
        ("6.85", 19, 2, 3, "mean", "fails_rounding_only"),  # k-item: n*k = 57
        ("57.4", 62, 1, 1, "percentage", "fails_both"),   # Just 2014, % male
        ("50.0", 2, 1, 1, "percentage", "passes"),
    ])
    def test_classify(self, value, n, decimals, k, kind, want):
        cell = _cell(value, n, decimals, items_k=k, kind=kind)
        assert verify.classify(cell)["verdict"] == want

    def test_items_multiply_the_denominator(self):
        # 7.47 is a mean of 3 items at n=18: steps of 1/54, not 1/18.
        cell = _cell("7.47", 18, 2, items_k=3)
        assert verify.classify(cell)["n_effective"] == 54


class TestTier:
    def _tiered(self, **kw):
        cell = _cell("51.9", 6, **kw)
        cell["arithmetic"] = verify.classify(cell)
        return verify.tier(cell)

    def test_primary(self):
        assert self._tiered() == "primary"

    def test_inferred_n_is_not_primary(self):
        assert self._tiered(n_source="inferred") == "inferred_n"

    def test_doubtful_premise_is_not_primary(self):
        assert self._tiered(premise="doubtful") == "doubtful_premise"

    def test_not_applicable_is_excluded(self):
        assert self._tiered(premise="not_applicable") == "excluded"

    def test_false_alarm_wins_over_the_arithmetic(self):
        assert self._tiered(label="false_alarm") == "false_alarm"

    def test_rounding_only(self):
        cell = _cell("6.62", 62, 2)
        cell["arithmetic"] = verify.classify(cell)
        assert verify.tier(cell) == "rounding_only"


class TestPrintedInText:
    def test_whole_number_only(self):
        assert verify.printed("mean 51.9 (2.1)", "51.9")
        assert not verify.printed("mean 151.9", "51.9")
        assert not verify.printed("mean 51.95", "51.9")

    def test_leading_dot_forms_and_unicode_minus(self):
        assert verify.printed("rated −.62 on average", "-.62")
        assert verify.printed("rated -0.62", "-.62")
        assert verify.printed("p = .32", "0.32")


def _review(tmp_path, calls, findings):
    d = tmp_path / "paper" / "forensic_review_x"
    d.mkdir(parents=True)
    (d / "run_meta.json").write_text(json.dumps({"analysed_at": "2026-10-17T00:00:00Z"}))
    (d / "toolcalls.tool_agent.json").write_text(json.dumps(calls))
    (d / "findings.v2.json").write_text(json.dumps({"findings": findings}))
    return tmp_path


def _call(tool, mean, n, severity, failure_mode):
    return {"tool": f"mcp__forensic_metascience__{tool}",
            "input": {"mean": mean, "n": n, "decimals": 1},
            "result": json.dumps({"severity": severity, "failure_mode": failure_mode})}


def _labels(*cells):
    out = []
    for i, c in enumerate(cells, 1):
        c = dict(c, id=f"c{i:03d}")
        c["arithmetic"] = verify.classify(c)
        c["tier"] = verify.tier(c)
        c["value_verified"] = True
        out.append(c)
    return [{"paper_id": "paper", "status": "confirmed_error", "cells": out}]


class TestScore:
    def test_grimmer_and_out_of_range_do_not_count_as_flagged(self, tmp_path):
        root = _review(tmp_path, [
            _call("grimmer_check", 51.9, 6, "impossible", "sd_granularity"),
            _call("grim_check", 51.9, 6, "suspicious", "out_of_range"),
        ], [])
        r = score.score(_labels(_cell("51.9", 6)), root, "forensic_review_*")
        row = r["cells"][0]
        assert row["checked"] and not row["flagged"]

    def test_grimmer_flags_only_a_mean_granularity_failure(self, tmp_path):
        root = _review(tmp_path, [_call("grimmer_check", 51.9, 6, "suspicious", "granularity")], [])
        r = score.score(_labels(_cell("51.9", 6)), root, "forensic_review_*")
        assert r["cells"][0]["flagged"]

    def test_granularity_counts_as_flagged(self, tmp_path):
        root = _review(tmp_path, [_call("grim_check", 51.9, 6, "impossible", "granularity")], [])
        r = score.score(_labels(_cell("51.9", 6)), root, "forensic_review_*")
        assert r["headline_cells"]["flagged"] == 1

    def test_a_percentage_detection_has_no_failure_mode(self, tmp_path):
        """grim_percentage says `impossible` with failure_mode None; the first
        flag rule missed all 12 Cureus detections (2026-10-18)."""
        call = {"tool": "mcp__forensic_metascience__grim_percentage",
                "input": {"percentage": 66.9, "n": 70, "decimals": 1},
                "result": json.dumps({"severity": "impossible", "failure_mode": None})}
        root = _review(tmp_path, [call], [])
        r = score.score(_labels(_cell("66.9", 70, kind="percentage")), root, "forensic_review_*")
        assert r["cells"][0]["flagged"]

    def test_a_one_value_sweep_over_the_n_flags(self, tmp_path):
        one = {"tool": "mcp__forensic_metascience__grim_sweep",
               "input": {"values": [10.3], "n_min": 2, "n_max": 25},
               "result": json.dumps({"severity": "impossible", "failure_mode": None})}
        root = _review(tmp_path, [one], [])
        r = score.score(_labels(_cell("10.3", 25, kind="percentage")), root, "forensic_review_*")
        assert r["cells"][0]["checked"] and r["cells"][0]["flagged"]

    def test_a_shared_n_sweep_checks_but_does_not_flag(self, tmp_path):
        many = {"tool": "mcp__forensic_metascience__grim_sweep",
                "input": {"values": [10.3, 72.4], "n_min": 2, "n_max": 25},
                "result": json.dumps({"severity": "impossible", "failure_mode": None})}
        root = _review(tmp_path, [many], [])
        r = score.score(_labels(_cell("10.3", 25, kind="percentage")), root, "forensic_review_*")
        assert r["cells"][0]["checked"] and not r["cells"][0]["flagged"]

    def test_check_table_rows_are_read(self, tmp_path):
        batch = {"tool": "mcp__forensic_metascience__check_table", "input": {},
                 "result": json.dumps({"results": [
                     {"tool": "grim_check", "inputs": {"mean": 51.9, "n": 6},
                      "severity": "suspicious",
                      "result": {"failure_mode": "granularity"}}]})}
        root = _review(tmp_path, [batch], [])
        r = score.score(_labels(_cell("51.9", 6)), root, "forensic_review_*")
        assert r["cells"][0]["flagged"]

    def test_quote_and_inputs_do_not_report_a_value(self, tmp_path):
        finding = {"technique": "grim_check", "outcome": "problem",
                   "title": "Table 2: 7 of 20 means unreachable",
                   "description": "51.9 cannot be a mean of six integers.",
                   "quote": "| CON(6) | 51.9 | 16.5 |",
                   "inputs": {"means_tested": [51.9, 16.5]}}
        root = _review(tmp_path, [], [finding])
        r = score.score(_labels(_cell("51.9", 6), _cell("16.5", 6)), root,
                        "forensic_review_*")
        reported = {row["value"]: row["reported"] for row in r["cells"]}
        assert reported == {"51.9": True, "16.5": False}

    def test_a_fraction_is_not_the_value(self, tmp_path):
        finding = {"technique": "grim_sweep", "outcome": "problem",
                   "title": "10.3% impossible", "description": "1/10 = 10.0%, 2/19 = 10.5%"}
        root = _review(tmp_path, [], [finding])
        r = score.score(_labels(_cell("10", 25, decimals=0, kind="percentage")), root,
                        "forensic_review_*")
        assert not r["cells"][0]["reported"]

    def test_a_discarded_finding_reports_nothing(self, tmp_path):
        finding = {"technique": "grim_check", "outcome": "problem",
                   "title": "51.9 impossible", "description": "51.9",
                   "adjudication": {"action": "discarded"}}
        root = _review(tmp_path, [], [finding])
        r = score.score(_labels(_cell("51.9", 6)), root, "forensic_review_*")
        assert not r["cells"][0]["reported"]

    def test_a_flagged_false_alarm_is_a_tool_error_not_a_hit(self, tmp_path):
        root = _review(tmp_path, [_call("grim_check", 51.9, 6, "impossible", "granularity")], [])
        r = score.score(_labels(_cell("51.9", 6, label="false_alarm")), root,
                        "forensic_review_*")
        assert r["false_alarms"]["flagged"] == 1
        assert r["headline_cells"]["cells"] == 0

    def test_papers_are_counted_once(self, tmp_path):
        root = _review(tmp_path, [_call("grim_check", 51.9, 6, "impossible", "granularity")], [])
        r = score.score(_labels(_cell("51.9", 6), _cell("45.9", 6)), root,
                        "forensic_review_*")
        assert r["headline_papers"] == {"papers": 1, "checked": 1, "flagged": 1,
                                        "reported": 0}


class TestPaperDir:
    def test_direct_and_subfolder(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "verified" / "b").mkdir(parents=True)
        for mod in (verify, score):
            assert mod.paper_dir(tmp_path, "a") == tmp_path / "a"
            assert mod.paper_dir(tmp_path, "b") == tmp_path / "verified" / "b"
            assert not mod.paper_dir(tmp_path, "c").exists()

    def test_two_copies_refuse(self, tmp_path):
        (tmp_path / "a").mkdir()
        (tmp_path / "verified" / "a").mkdir(parents=True)
        with pytest.raises(ValueError):
            verify.paper_dir(tmp_path, "a")

    def test_score_finds_a_review_in_a_subfolder(self, tmp_path):
        root = _review(tmp_path, [_call("grim_check", 51.9, 6, "impossible", "granularity")], [])
        (root / "verified").mkdir()
        (root / "paper").rename(root / "verified" / "paper")
        r = score.score(_labels(_cell("51.9", 6)), root, "forensic_review_*")
        assert r["headline_cells"]["flagged"] == 1


class TestSplit:
    def test_select_split(self, tmp_path):
        labels = [{"paper_id": "a"}, {"paper_id": "b"}, {"paper_id": "c"}]
        lp = tmp_path / "labels.jsonl"
        (tmp_path / "splits.json").write_text(json.dumps({"dev": ["a", "c"], "holdout": ["b"]}))
        assert [p["paper_id"] for p in score.select_split(labels, lp, "dev")] == ["a", "c"]
        assert score.select_split(labels, lp, None) == labels
        with pytest.raises(KeyError):
            score.select_split(labels, lp, "test")


@pytest.mark.parametrize("set_dir", [d for d in SETS if (d / "splits.json").is_file()],
                         ids=lambda d: d.name)
class TestSplitsFile:
    """A split that leaks, overlaps or drops a verified paper is not a holdout."""

    def _verified(self, set_dir):
        return {p["paper_id"] for p in _papers(set_dir)
                if p.get("paper_verified")
                or any(c["tier"] == "primary" and c["value_verified"] for c in p["cells"])}

    def test_disjoint_and_complete(self, set_dir):
        sp = json.loads((set_dir / "splits.json").read_text())
        dev, hold = set(sp["dev"]), set(sp["holdout"])
        assert not dev & hold
        assert dev | hold == self._verified(set_dir)

    def test_families_stay_together(self, set_dir):
        sp = json.loads((set_dir / "splits.json").read_text())
        slug = {p["doi"]: p["paper_id"] for p in _papers(set_dir)}
        for fam in sp["families"].values():
            sides = {"dev" if slug[d] in sp["dev"] else "holdout" for d in fam["members"]}
            assert len(sides) == 1, fam


STAMPED = {"arithmetic", "tier", "value_verified", "value_verified_by"}


def test_there_is_a_set():
    assert SETS, "no benchmarks/grim/<set>/labels.jsonl found"


@pytest.mark.parametrize("set_dir", SETS, ids=lambda d: d.name)
class TestLabels:
    def test_labels_are_what_the_builder_makes(self, set_dir):
        builder = set_dir / "build_labels.py"
        assert builder.is_file(), f"{set_dir.name} has no build_labels.py"
        build = _load(builder, f"grim_bench_build_{set_dir.name.replace('-', '_')}")
        strip = lambda papers: [  # noqa: E731
            {**p, "cells": [{k: v for k, v in c.items() if k not in STAMPED}
                            for c in p["cells"]]} for p in papers]
        assert strip(_papers(set_dir)) == strip(build.build())

    def test_every_cell_is_stamped_and_tiered(self, set_dir):
        for paper in _papers(set_dir):
            for c in paper["cells"]:
                assert c["tier"] == verify.tier(c), (paper["paper_id"], c["id"])
                assert c["arithmetic"] == verify.classify(c), (paper["paper_id"], c["id"])

    def test_every_paper_has_a_status_and_evidence(self, set_dir):
        for paper in _papers(set_dir):
            assert paper["status"] in {"confirmed_error", "journal_action",
                                       "published_critique", "unresolved_concern"}
            assert paper["evidence"], paper["paper_id"]

    def test_paper_ids_are_unique(self, set_dir):
        ids = [p["paper_id"] for p in _papers(set_dir)]
        assert len(ids) == len(set(ids))


class TestHarnessSweep:
    """1.82.0: the harness checks cells itself; the scorer reads run_meta."""

    def _review(self, tmp_path, checked, findings):
        root = _review(tmp_path, [], findings)
        meta = root / "paper" / "forensic_review_x" / "run_meta.json"
        meta.write_text(json.dumps({"exhaustive_checks": {"grim": {
            "checked_cells": checked}}}))
        return root

    def test_a_harness_failure_is_checked_flagged_and_reported(self, tmp_path):
        cell = {"table": "T1", "row": 3, "col": 2, "raw": "51.9", "what": "mean",
                "value": 51.9, "n": 6, "status": "inconsistent"}
        finding = {"producer": "harness", "technique": "grim_check",
                   "outcome": "problem", "title": "Table 2: 1 mean(s)",
                   "description": "...", "inputs": {"cells": [cell]}}
        root = self._review(tmp_path, [cell], [finding])
        row = score.score(_labels(_cell("51.9", 6)), root, "forensic_review_*")["cells"][0]
        assert row["checked"] and row["flagged"] and row["reported"]

    def test_a_harness_pass_is_checked_not_flagged(self, tmp_path):
        cell = {"table": "T1", "raw": "51.9", "what": "mean", "value": 51.9,
                "n": 6, "status": "consistent"}
        root = self._review(tmp_path, [cell], [])
        row = score.score(_labels(_cell("51.9", 6)), root, "forensic_review_*")["cells"][0]
        assert row["checked"] and not row["flagged"] and not row["reported"]

    def test_a_harness_row_reports_only_cells_at_the_labelled_n(self, tmp_path):
        cell = {"raw": "51.9", "what": "mean", "value": 51.9, "n": 7,
                "status": "inconsistent"}
        finding = {"producer": "harness", "technique": "grim_check",
                   "outcome": "problem", "inputs": {"cells": [cell]}}
        root = self._review(tmp_path, [cell], [finding])
        row = score.score(_labels(_cell("51.9", 6)), root, "forensic_review_*")["cells"][0]
        assert not row["reported"]
