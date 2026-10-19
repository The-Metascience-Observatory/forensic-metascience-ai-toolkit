"""The seen-papers registry keeps deleted corpora from being fetched again."""
import csv
import gzip

import pytest

from metascience_agent import seen_papers


def _write(path, rows):
    with gzip.open(path, "wt", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["doi", "state", "corpora"])
        w.writerows(rows)
    return path


@pytest.fixture
def registry(tmp_path, monkeypatch):
    path = _write(tmp_path / "seen.tsv.gz", [
        ["10.1/analysed", "analysed", "jun_ren_rw20260922__pubpeer_checked_x;jun_ren_rw20260922"],
        ["10.1/fetched", "fetched", "screen_2026-09"],
        ["10.1/listed", "fetch_listed", "screen_2026-09"],
        ["10.1/selected", "selected", "masliah_papers"],
        ["10.1/failed", "failed_fetch", "masliah_papers"],
        ["10.1/shared", "analysed", "jun_ren_rw20260922;bokyung_sung_rw20260922"],
    ])
    monkeypatch.setenv("METASCIENCE_SEEN_PAPERS", str(path))
    return path


def test_blocking_states_only(registry):
    assert seen_papers.seen_dois() == {"10.1/analysed", "10.1/fetched", "10.1/listed", "10.1/shared"}


def test_normalises_doi_forms(registry):
    assert seen_papers.is_seen("https://doi.org/10.1/ANALYSED")
    assert not seen_papers.is_seen("10.1/selected")


def test_exempt_corpus_readmits_only_its_own_papers(registry):
    seen = seen_papers.seen_dois(exempt_corpus="jun_ren_rw20260922")
    assert "10.1/analysed" not in seen          # its only home, sessions included
    assert "10.1/shared" in seen                # also held by another corpus


def test_missing_registry_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("METASCIENCE_SEEN_PAPERS", str(tmp_path / "absent.tsv.gz"))
    with pytest.raises(seen_papers.SeenRegistryMissing):
        seen_papers.seen_dois()


def test_empty_registry_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setenv("METASCIENCE_SEEN_PAPERS", str(_write(tmp_path / "e.tsv.gz", [])))
    with pytest.raises(seen_papers.SeenRegistryMissing):
        seen_papers.seen_dois()


def test_explicit_off(monkeypatch):
    monkeypatch.setenv("METASCIENCE_SEEN_PAPERS", "off")
    assert seen_papers.seen_dois() == set()


def test_committed_registry_is_readable(monkeypatch):
    monkeypatch.delenv("METASCIENCE_SEEN_PAPERS", raising=False)
    assert seen_papers.DEFAULT_REGISTRY.exists()
    assert len(seen_papers.seen_dois()) > 10_000


def test_exempt_a_whole_cohort(registry):
    seen = seen_papers.seen_dois(exempt_corpus=["jun_ren_rw20260922", "bokyung_sung_rw20260922"])
    assert "10.1/shared" not in seen and "10.1/analysed" not in seen
    assert "10.1/fetched" in seen
