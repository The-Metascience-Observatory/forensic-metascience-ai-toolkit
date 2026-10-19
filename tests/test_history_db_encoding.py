"""The two ways a corpus sync silently produced NOTHING, pinned without a DB.

Both were found on 2026-09-14 when the viewer kept showing a superseded sweep
of the embargoed 2026-09 corpus as current. The sync had failed twice over -- first on a
NUL byte in three papers' captions, then on the 256 MB jsonb cap once the
archive held 14,451 runs -- and each failure rolled back the whole corpus and
was recorded only in a file nobody was looking at. These tests need no
database: they pin the encoder and the batcher, which is where both defects
lived.
"""
from __future__ import annotations

import json

from metascience_agent import history_db as H


def test_nul_is_removed_at_every_depth():
    out = H.encode_for_postgres({"caption": "Figs1 \x00 tail",
                                 "nested": [{"x": "a\x00b", "n": 1}], "ok": "fine"})
    assert "\\u0000" not in out
    assert json.loads(out) == {"caption": "Figs1  tail", "nested": [{"x": "ab", "n": 1}],
                               "ok": "fine"}


def test_encoder_is_otherwise_plain_json_dumps_with_default_str():
    from pathlib import Path
    out = H.encode_for_postgres({"p": Path("/x"), "s": "no nul here"})
    assert json.loads(out) == {"p": "/x", "s": "no nul here"}


class _Cursor:
    """Records each execute's parameters; returns RETURNING rows when asked."""

    def __init__(self, returning: bool):
        self.calls: list[tuple] = []
        self.description = object() if returning else None

    def execute(self, sql, params):
        self.calls.append(params)

    def fetchall(self):
        # One RETURNING row per element of the LAST parameter's JSON array.
        return [(i,) for i in range(len(json.loads(self.calls[-1][-1])))]


def test_batched_splits_at_sync_batch_and_concatenates_returning_rows(monkeypatch):
    monkeypatch.setattr(H, "SYNC_BATCH", 4)
    cur = _Cursor(returning=True)
    rows = [{"i": i} for i in range(10)]
    got = H._batched(cur, "insert ... %s", rows, encode=H.encode_for_postgres)
    assert len(cur.calls) == 3, "10 rows at batch 4 is 3 statements"
    sizes = [len(json.loads(c[-1])) for c in cur.calls]
    assert sizes == [4, 4, 2]
    assert len(got) == 10, "RETURNING rows must be concatenated across batches"


def test_batched_passes_leading_parameters_before_the_array(monkeypatch):
    monkeypatch.setattr(H, "SYNC_BATCH", 2)
    cur = _Cursor(returning=False)
    H._batched(cur, "insert ... %s ... %s", [{"a": 1}, {"a": 2}, {"a": 3}],
               encode=H.encode_for_postgres, before=(42,))
    assert all(c[0] == 42 for c in cur.calls)
    assert all(isinstance(c[-1], str) for c in cur.calls)


def test_batched_executes_once_on_empty_input_and_returns_nothing():
    cur = _Cursor(returning=True)
    got = H._batched(cur, "insert ... %s", [], encode=H.encode_for_postgres)
    assert len(cur.calls) == 1 and json.loads(cur.calls[0][-1]) == []
    assert got == []


def test_a_statement_without_returning_does_not_fetch():
    cur = _Cursor(returning=False)
    got = H._batched(cur, "insert ... %s", [{"a": 1}], encode=H.encode_for_postgres)
    assert got == []


def test_sync_batch_keeps_a_run_payload_well_under_the_jsonb_cap():
    """The cap is 268,435,455 bytes. The largest per-run `meta` measured on the
    corpus that hit it was well under 100 KB; the batch must leave an order of
    magnitude of headroom, because the next corpus's manifests will be bigger."""
    assert H.SYNC_BATCH * 100_000 < 268_435_455 / 10
