"""A paid table reading outlives the directory it was bought in.

THE DEFECT THESE TESTS PIN. `reconstruct._cache_key` computed a perfectly good
content address and then stored the reading it keyed inside the run's own
output directory -- so `rm -rf` on that directory destroyed money, three times
(D74, D75, D81), and nothing anywhere else on the machine held a copy.

The two properties that matter are opposite in direction and are tested as a
pair: a HIT must produce exactly what the run directory would have held, and a
MISS -- including every flavour of damaged entry -- must behave exactly as if
this module did not exist. A cache that is nearly right about a reading is
worse than no cache, because the reading is what a finding is made of.
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.scaffold import passes as PASSES
from forensic_metascience_ai_toolkit.scaffold import reading_store as RS
from forensic_metascience_ai_toolkit.scaffold import reconstruct as RC

# The walker cells and the reading that verifies against them are already
# written once, next door; pytest 9 defaults to the importlib import mode and
# no longer puts the test directory on the path (the repo's own precedent for
# this line is `test_backend_unavailable.py`).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_reconstruct import GOOD, WALKER, WRAP  # noqa: E402

KEY = "b3838c0e8bafec43"
OTHER = "36fd93233256a268"


def _bought(out: Path, name: str, key: str, data: dict | None = None,
            cost: float = 0.52) -> dict:
    """A run directory holding one reading, written exactly as `run_pass` does."""
    out.mkdir(parents=True, exist_ok=True)
    data = GOOD if data is None else data
    meta = {"cache_key": key, "model": "sonnet", "attempt": 0, "elapsed_s": 61.0,
            "cost_usd": cost, "num_turns": 2, "session_id": "s-1", "n_schema_problems": 0,
            "problems": []}
    (out / f"{name}.json").write_text(json.dumps(data, indent=1, ensure_ascii=False),
                                      encoding="utf-8")
    (out / f"{name}.meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    (out / f"{name}.prompt.md").write_text("read this table\n", encoding="utf-8")
    (out / f"{name}.raw.json").write_text('{"structured_output": {}}', encoding="utf-8")
    (out / f"{name}.schema.json").write_text('{"type": "object"}', encoding="utf-8")
    return meta


class TestTheRoot:
    def test_the_default_is_outside_every_run_directory(self):
        """The whole defect in one assertion: the store is not under a run."""
        assert RS.DEFAULT_ROOT == Path.home() / ".cache" / "metascience" / "readings"

    def test_the_environment_moves_it_and_can_switch_it_off(self, monkeypatch, tmp_path):
        monkeypatch.setenv(RS.ENV, str(tmp_path / "elsewhere"))
        assert RS.root() == tmp_path / "elsewhere"
        for off in ("off", "", "0", "NONE"):
            monkeypatch.setenv(RS.ENV, off)
            assert RS.root() is None, off

    def test_a_key_that_is_not_a_key_addresses_nothing(self, tmp_path, monkeypatch):
        """A key is pasted into a path. One that is not sixteen hex characters
        is refused rather than resolved, so no caller can write outside the
        store by handing it a name with a separator in it."""
        monkeypatch.setenv(RS.ENV, str(tmp_path))
        assert RS.entry_path("../../etc/passwd") is None
        assert RS.entry_path("NOTHEX") is None
        assert RS.entry_path(KEY) == tmp_path / "b3" / f"{KEY}.json"

    def test_with_the_store_off_nothing_is_written_and_nothing_is_said(self, tmp_path, monkeypatch):
        monkeypatch.setenv(RS.ENV, "off")
        run = tmp_path / "run"
        _bought(run, "table_1.recon", KEY)
        assert RS.deposit("table_1.recon", run, KEY)["status"] == "off"
        got, notes = RS.reuse("table_1.recon", run, KEY)
        assert got is not None and got["reused_from"] == "run_dir" and notes == []


class TestSurvivingTheWipe:
    def test_a_deposited_reading_is_restored_byte_for_byte_into_a_fresh_directory(self, tmp_path):
        """THE POINT OF THE MODULE. Buy it here, delete the directory, and the
        files come back with the same bytes -- so `load_pass` cannot tell the
        difference, which is the only definition of a cache hit worth having."""
        run = tmp_path / "run"
        _bought(run, "table_1.recon", KEY)
        before = {p.name: p.read_bytes() for p in run.iterdir()}
        assert RS.deposit("table_1.recon", run, KEY)["status"] == "deposited"

        import shutil
        shutil.rmtree(run)
        assert not run.exists()

        got, notes = RS.reuse("table_1.recon", run, KEY)
        assert got is not None and got["reused_from"] == "store" and notes == []
        assert got["data"] == GOOD
        assert got["meta"]["cost_usd"] == 0.52, "what it cost is part of the reading"
        for name, blob in before.items():
            assert (run / name).read_bytes() == blob, name

    def test_the_restored_directory_says_the_reading_was_not_bought_there(self, tmp_path):
        """A restored reading is otherwise indistinguishable from one paid for
        here, and its prompt names a PNG at a path that no longer exists."""
        run, second = tmp_path / "run", tmp_path / "second"
        _bought(run, "table_1.recon", KEY)
        RS.deposit("table_1.recon", run, KEY)
        got, _ = RS.reuse("table_1.recon", second, KEY)
        assert got is not None
        marker = json.loads((second / "table_1.recon.restored.json").read_text())
        assert marker["cache_key"] == KEY and marker["bought_as"] == "table_1.recon"
        assert marker["bought_in"] == str(run.resolve())
        assert marker["restored_as"] == "table_1.recon"

    def test_a_reading_bought_under_one_name_restores_under_the_caller_s(self, tmp_path):
        """The key addresses a table's CONTENT. The same table read at a
        different position in another run is the same purchase, and the pass
        name is the caller's business."""
        run, second = tmp_path / "run", tmp_path / "second"
        _bought(run, "table_3.recon", KEY)
        RS.deposit("table_3.recon", run, KEY)
        got, _ = RS.reuse("table_1.recon", second, KEY)
        assert got is not None and got["data"] == GOOD
        assert (second / "table_1.recon.json").is_file()
        assert not (second / "table_3.recon.json").exists()

    def test_a_run_directory_hit_backfills_the_store(self, tmp_path):
        """Without this the six readings already on disk on 2026-09-14 would
        have stayed unprotected: only NEW purchases would ever be stored, and
        the wipe that prompted the work would still have cost them."""
        run = tmp_path / "run"
        _bought(run, "table_1.recon", KEY)
        assert RS.load(KEY) == (None, None)
        got, notes = RS.reuse("table_1.recon", run, KEY)
        assert got["reused_from"] == "run_dir" and notes == []
        entry, why = RS.load(KEY)
        assert entry is not None and why is None

    def test_depositing_the_same_reading_twice_is_quiet(self, tmp_path):
        run = tmp_path / "run"
        _bought(run, "table_1.recon", KEY)
        assert RS.deposit("table_1.recon", run, KEY)["status"] == "deposited"
        again = RS.deposit("table_1.recon", run, KEY)
        assert again["status"] == "already_held" and again["note"] is None

    def test_a_reading_this_run_cannot_use_is_still_kept(self, tmp_path):
        """MEASURED on the ajcp run directory, 2026-09-14: two tables came back
        `not_attempted` because they no longer render, so their keys were never
        computed and $0.59 of readings sat unprotected beside four that were
        kept. What the run can USE and what the disk HOLDS are different
        questions, and only the second one decides what a wipe costs."""
        run = tmp_path / "run"
        _bought(run, "table_5.recon", KEY)
        _bought(run, "table_6.recon", OTHER)
        out = RS.backfill(run)
        assert out["counts"] == {"deposited": 2} and out["notes"] == []
        assert RS.load(KEY)[0] is not None and RS.load(OTHER)[0] is not None

    def test_a_pass_with_no_key_is_not_filed_under_one(self, tmp_path):
        """`pass1.meta.json` carries no `cache_key` -- passes 1, 2 and 3 are
        not content-addressed and this module does not pretend otherwise."""
        run = tmp_path / "run"
        run.mkdir()
        (run / "pass1.json").write_text("{}")
        (run / "pass1.meta.json").write_text(json.dumps({"model": "opus", "cost_usd": 7.49}))
        assert RS.backfill(run) == {"counts": {}, "notes": []}

    def test_a_miss_is_silent(self, tmp_path):
        """A first run must not accuse itself of anything."""
        got, notes = RS.reuse("table_1.recon", tmp_path / "run", KEY)
        assert got is None and notes == []


class TestTheRunDirectoryWins:
    def test_a_differing_store_entry_does_not_overrule_the_run_directory(self, tmp_path):
        """A cache that can overrule the artifact beside the account is a cache
        that can change a published number."""
        bought_elsewhere, run = tmp_path / "elsewhere", tmp_path / "run"
        _bought(bought_elsewhere, "table_1.recon", KEY, data={**GOOD, "notes": "from elsewhere"})
        RS.deposit("table_1.recon", bought_elsewhere, KEY)
        _bought(run, "table_1.recon", KEY, data={**GOOD, "notes": "from this run"})

        got, notes = RS.reuse("table_1.recon", run, KEY)
        assert got["data"]["notes"] == "from this run"
        assert len(notes) == 1 and "DIFFERENT reading" in notes[0]
        assert str(bought_elsewhere.resolve()) in notes[0], "the disagreement names both sides"
        entry, _ = RS.load(KEY)
        assert json.loads(entry["files"][".json"]["text"])["notes"] == "from elsewhere", (
            "preferring the run directory does not mean rewriting the store")

    def test_restoring_over_a_stale_reading_is_announced(self, tmp_path):
        """The displaced file was somebody's evidence, even though a paid call
        would have overwritten it just the same."""
        first, run = tmp_path / "first", tmp_path / "run"
        _bought(first, "table_1.recon", KEY)
        RS.deposit("table_1.recon", first, KEY)
        _bought(run, "table_1.recon", OTHER, data={**GOOD, "notes": "the old cells"})
        got, notes = RS.reuse("table_1.recon", run, KEY)
        assert got is not None and got["reused_from"] == "store"
        assert any(OTHER in n and KEY in n for n in notes)


class TestADamagedEntryIsAMiss:
    def _deposited(self, tmp_path) -> Path:
        run = tmp_path / "run"
        _bought(run, "table_1.recon", KEY)
        RS.deposit("table_1.recon", run, KEY)
        return Path(RS.entry_path(KEY))

    def _rejected(self, tmp_path, mutate) -> str:
        path = self._deposited(tmp_path)
        entry = json.loads(path.read_text())
        mutate(entry)
        path.write_text(json.dumps(entry))
        got, why = RS.load(KEY)
        assert got is None and why, "a damaged entry is never served"
        return why

    def test_a_truncated_entry_is_refused_rather_than_parsed(self, tmp_path):
        path = self._deposited(tmp_path)
        blob = path.read_text()
        path.write_text(blob[: len(blob) // 2])
        got, why = RS.load(KEY)
        assert got is None and "unreadable" in why

    def test_an_edited_reading_fails_its_own_checksum(self, tmp_path):
        """The one failure this module must not have: half a file served as a
        model's reading of a table."""
        def edit(entry):
            entry["files"][".json"]["text"] = entry["files"][".json"]["text"][:-40]
        assert "checksum" in self._rejected(tmp_path, edit)

    def test_an_entry_filed_under_the_wrong_key_is_refused(self, tmp_path):
        assert "claims to be" in self._rejected(tmp_path, lambda e: e.update({"cache_key": OTHER}))

    def test_a_reading_whose_own_meta_names_another_key_is_refused(self, tmp_path):
        """This is what makes a restored directory behave like the one that
        bought the reading: `reconstruct` compares `meta.cache_key` to the key
        it just computed, and a restore that could not pass that test would be
        a hit here and a miss one line later."""
        def edit(entry):
            meta = json.loads(entry["files"][".meta.json"]["text"])
            meta["cache_key"] = OTHER
            text = json.dumps(meta, indent=1)
            entry["files"][".meta.json"] = {"sha256": RS._sha(text), "text": text}
        assert "own meta says" in self._rejected(tmp_path, edit)

    def test_an_entry_from_another_store_version_is_refused(self, tmp_path):
        why = self._rejected(tmp_path, lambda e: e.update({"store_version": 99}))
        assert "store version" in why

    def test_an_entry_missing_the_reading_itself_is_refused(self, tmp_path):
        assert "missing .json" in self._rejected(tmp_path, lambda e: e["files"].pop(".json"))

    def test_a_damaged_entry_is_replaced_by_the_next_good_one(self, tmp_path):
        """Keeping it protects nothing: it can never be served."""
        path = self._deposited(tmp_path)
        path.write_text("{ this is not json")
        run = tmp_path / "run2"
        _bought(run, "table_1.recon", KEY)
        out = RS.deposit("table_1.recon", run, KEY)
        assert out["status"] == "replaced" and "unusable" in out["note"]
        entry, why = RS.load(KEY)
        assert entry is not None and why is None

    def test_a_run_directory_missing_its_meta_deposits_nothing(self, tmp_path):
        """Half a purchase is not a purchase."""
        run = tmp_path / "run"
        _bought(run, "table_1.recon", KEY)
        (run / "table_1.recon.meta.json").unlink()
        out = RS.deposit("table_1.recon", run, KEY)
        assert out["status"] == "incomplete" and ".meta.json" in out["note"]
        assert RS.load(KEY) == (None, None)


class TestThroughReconstruct:
    """The real call path, with the model stubbed: what a wiped run costs."""

    TABLE = {"label": "Table 2", "cells": list(WALKER), "source": "article",
             "table_id": "T2", "table_num": 1, "position": 1}
    ROOT = f"<article><body>{WRAP}</body></article>"

    @pytest.fixture()
    def stub(self, monkeypatch):
        """`render_png` needs a browser and `run_pass` needs money; neither is
        what this test is about. The stub writes the same files `run_pass`
        writes, so the deposit sees a real pass on disk."""
        calls: list[str] = []

        def render(html, png, meta=None):
            Path(png).parent.mkdir(parents=True, exist_ok=True)
            Path(png).write_bytes(b"\x89PNG\r\n\x1a\n")
            if meta is not None:
                meta["render"] = "stub"
            return None

        def run_pass(name, prompt, out_dir, **kw):
            calls.append(name)
            meta = _bought(Path(out_dir), name, kw["extra_meta"]["cache_key"])
            return {"data": GOOD, "problems": [], "meta": meta}

        monkeypatch.setattr(RC, "render_png", render)
        monkeypatch.setattr(PASSES, "run_pass", run_pass)
        return calls

    def _read(self, paper: Path, out: Path, model: str | None, problems: list[str]) -> dict:
        table = {**self.TABLE, "cells": list(WALKER)}
        return RC.reconstruct_table(paper, table, 1, out, model=model,
                                    root=ET.fromstring(self.ROOT), problems=problems)

    def test_a_wiped_run_directory_rebuilds_the_reading_without_paying(self, tmp_path, stub):
        paper, out = tmp_path / "paper", tmp_path / "paper" / "scaffold" / "tables"
        problems: list[str] = []
        first = self._read(paper, out, "sonnet", problems)
        assert first["status"] == "verified" and stub == ["table_1.recon"]

        import shutil
        shutil.rmtree(out)

        again: list[str] = []
        second = self._read(paper, out, None, again)  # --no-llm: nothing may be bought
        assert stub == ["table_1.recon"], "the second build made no call"
        assert second["status"] == "verified" and second["reused_from"] == "store"
        assert second["cost_usd"] == first["cost_usd"] == 0.52
        assert second["verification"] == first["verification"]
        assert again == [], "a clean restore is not a problem"

    def test_without_the_store_the_same_wipe_costs_the_reading(self, tmp_path, stub, monkeypatch):
        """The control. With the store off, `--no-llm` on a wiped directory has
        nothing -- which is the behaviour every run had until today."""
        monkeypatch.setenv(RS.ENV, "off")
        paper, out = tmp_path / "paper", tmp_path / "paper" / "scaffold" / "tables"
        assert self._read(paper, out, "sonnet", [])["status"] == "verified"

        import shutil
        shutil.rmtree(out)

        rec = self._read(paper, out, None, [])
        assert rec["status"] == "not_attempted" and "--no-llm" in rec["reason"]

    def test_a_re_bought_reading_drops_the_marker_that_says_it_was_restored(self, tmp_path, stub):
        """A provenance note that outlives what it describes is read as true."""
        paper, out = tmp_path / "paper", tmp_path / "paper" / "scaffold" / "tables"
        self._read(paper, out, "sonnet", [])
        import shutil
        shutil.rmtree(out)
        self._read(paper, out, None, [])
        marker = out / "table_1.recon.json"
        assert (out / "table_1.recon.restored.json").is_file()

        # the same table, read again after its cells moved: a new key, a new
        # purchase, and the files under that name are this run's after all
        table = {**self.TABLE, "cells": [{**c, "raw": c["raw"] + " "} for c in WALKER]}
        RC.reconstruct_table(paper, table, 1, out, model="sonnet",
                             root=ET.fromstring(self.ROOT), problems=[])
        assert not (out / "table_1.recon.restored.json").exists()
        assert marker.is_file()

    def test_the_run_directory_is_still_reused_first_and_costs_nothing(self, tmp_path, stub):
        paper, out = tmp_path / "paper", tmp_path / "paper" / "scaffold" / "tables"
        self._read(paper, out, "sonnet", [])
        rec = self._read(paper, out, "sonnet", [])
        assert stub == ["table_1.recon"], "a second run in the same directory buys nothing"
        assert rec["reused_from"] == "run_dir" and rec["reused"] is True

    def test_every_paid_reading_in_this_module_goes_to_the_store(self, tmp_path, stub):
        """Buying and keeping are one act (`_buy_reading`), so a third call
        site cannot be added that pays without depositing."""
        import ast
        import inspect
        pays = set()
        for fn in ast.walk(ast.parse(inspect.getsource(RC))):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == "run_pass" for n in ast.walk(fn)):
                pays.add(fn.name)
        assert pays == {"_buy_reading"}, f"reconstruct pays only through _buy_reading, not {pays}"
        assert "_store.deposit" in inspect.getsource(RC._buy_reading)
