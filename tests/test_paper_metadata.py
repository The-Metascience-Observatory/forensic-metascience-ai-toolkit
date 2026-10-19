"""Bibliographic cache: a missing file is not an empty paper."""
import json
from datetime import datetime, timedelta, timezone

from forensic_metascience_ai_toolkit.paper_metadata import (
    authors_have_initials, authors_list_from_crossref, build_authors_list,
    citation_bits, derive_status, doi_from_slug, ensure_metadata, first_author,
    given_is_initials, has_core_identity, has_displayable, load_cached,
    needs_enrichment, needs_network, upgrade_record,
)


def _recent() -> str:
    """A fetched_at inside the 24h retry window, computed so the test does
    not rot: a hardcoded '2026-08-19' became stale the moment 24h passed
    and silently turned the not-retried test into a retried one."""
    return (datetime.now(timezone.utc) - timedelta(hours=1)) \
        .isoformat(timespec="seconds")


def test_doi_from_slug_strips_case_conflict_suffix():
    assert doi_from_slug("10.3831--kpi.2013.16.009 (Case Conflict)") \
        == "10.3831/kpi.2013.16.009"


def test_doi_from_slug_plain():
    assert doi_from_slug("10.1016--j.ijresmar.2015.03.003") \
        == "10.1016/j.ijresmar.2015.03.003"


def test_doi_from_slug_replaces_every_separator():
    """`doi_dirname` replaces every `/`, so the inverse must replace every
    `--`. Replacing the first only produced `10.1210/clinem--dgag124` for a
    paper whose only identity was its directory name (no XML, no
    provenance): a DOI that resolves nowhere, written into metadata.json."""
    from forensic_metascience_ai_toolkit.paper_ids import doi_dirname
    assert doi_from_slug("10.1210--clinem--dgag124") == "10.1210/clinem/dgag124"
    assert doi_from_slug("10.21203--rs.3.rs-3547685--v1") \
        == "10.21203/rs.3.rs-3547685/v1"
    for doi in ("10.1093/jnen/59.11.955", "10.1002/jfa2.70171"):
        assert doi_from_slug(doi_dirname(doi)) == doi


def test_first_author_is_the_first_semicolon_name():
    assert first_author("Nina Mazar; Dan Ariely") == "Nina Mazar"
    assert first_author("") is None
    assert first_author(None) is None


def test_first_author_from_a_comma_list_is_one_name():
    assert first_author(
        "Stefan Strilciuc, Constantin Radu, Diana-Alecsandra Grad"
    ) == "Stefan Strilciuc"
    assert first_author(
        "Hari Shanker Sharma, Dafin Fior Muresanu"
    ) == "Hari Shanker Sharma"


def test_first_author_keeps_a_last_comma_first_single_name():
    assert first_author("Mazar, Nina") == "Mazar, Nina"


def test_citation_bits_omit_empty_pieces():
    assert citation_bits({
        "journal": "Nature", "volume": "523", "issue": "7559", "year": 2015,
    }) == "Nature 523(7559) (2015)"
    assert citation_bits({"journal": "PLOS ONE", "year": 2020}) == "PLOS ONE (2020)"
    assert citation_bits({}) == ""


def test_offline_ensure_does_not_invent_a_title(tmp_path):
    paper = tmp_path / "10.1234--demo"
    paper.mkdir()
    rec = ensure_metadata(paper, network=False)
    assert rec.get("title") is None
    assert rec.get("doi") == "10.1234/demo"
    assert not (paper / "metadata.json").exists(), (
        "offline + nothing on disk must not write a file that later reads as "
        "a completed fetch")


def test_xml_seed_is_used_offline(tmp_path):
    paper = tmp_path / "10.1234--demo"
    paper.mkdir()
    (paper / "10.1234--demo.xml").write_text(
        '<?xml version="1.0"?><article><front><article-meta>'
        '<article-id pub-id-type="doi">10.1234/demo</article-id>'
        '<title-group><article-title>A Full Title</article-title></title-group>'
        '<contrib-group><contrib contrib-type="author">'
        '<name><surname>Mazar</surname><given-names>Nina</given-names></name>'
        '</contrib></contrib-group>'
        '<pub-date><year>2015</year></pub-date>'
        '</article-meta>'
        '<journal-meta><journal-title>Test Journal</journal-title></journal-meta>'
        '</front><body/></article>',
        encoding="utf-8",
    )
    rec = ensure_metadata(paper, network=False)
    assert rec["title"] == "A Full Title"
    assert rec["journal"] == "Test Journal"
    assert rec["first_author"]
    assert rec["source"] == "xml"
    assert rec["doi"] == "10.1234/demo"


def test_cached_file_is_preferred(tmp_path, monkeypatch):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "metadata.json").write_text(json.dumps({
        "schema_version": "1.0",
        "title": "Cached Title",
        "authors": "Ada Lovelace",
        "first_author": "Ada Lovelace",
        "journal": "Notes",
        "year": 1843,
        "doi": "10.1/x",
    }))
    def boom(*a, **k):
        raise AssertionError("network must not run when the cache is displayable")
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi", boom)
    rec = ensure_metadata(paper, network=True)
    assert rec["title"] == "Cached Title"


def test_scan_paper_reads_metadata_json(tmp_path):
    from forensic_metascience_ai_toolkit.webapp_index import scan_paper
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "x.pdf").write_text("x")
    (paper / "metadata.json").write_text(json.dumps({
        "title": "The Full Title of the Paper",
        "authors": "Ada Lovelace; Charles Babbage",
        "first_author": "Ada Lovelace",
        "journal": "Philosophical Transactions",
        "volume": "1", "issue": "2", "year": 1843,
        "doi": "10.1/x",
    }))
    rec = scan_paper(paper)
    assert rec["title"] == "The Full Title of the Paper"
    assert rec["first_author"] == "Ada Lovelace"
    assert rec["journal"] == "Philosophical Transactions"
    assert rec["volume"] == "1"
    assert rec["issue"] == "2"
    assert rec["year"] == 1843
    assert rec["identity_source"] == "metadata.json"


def test_record_for_run_is_offline_under_pytest(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit.paper_metadata import record_for_run
    called = {}
    def fake(paper_dir, force=False, network=True):
        called["network"] = network
        return {"title": None, "source": "none"}
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.ensure_metadata", fake)
    record_for_run(tmp_path)
    assert called["network"] is False


def test_record_for_run_does_not_raise(tmp_path, monkeypatch):
    from forensic_metascience_ai_toolkit.paper_metadata import record_for_run
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.ensure_metadata",
        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crossref down")))
    rec = record_for_run(tmp_path / "nope")
    assert rec.get("error")
    assert "RuntimeError" in rec["error"]


def test_failed_fetch_is_recorded_not_silent(tmp_path, monkeypatch):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: None)
    rec = ensure_metadata(paper, network=True)
    assert rec.get("error")
    assert (paper / "metadata.json").is_file()
    again = load_cached(paper)
    assert again["error"]
    assert not has_displayable(again)


def test_title_and_author_are_enough_even_without_volume():
    assert has_core_identity({
        "title": "A Paper", "authors": "Ada Lovelace",
    })
    assert not has_core_identity({"title": "A Paper"})
    assert not has_core_identity({"authors": "Ada Lovelace"})
    assert not needs_network({
        "title": "A Paper", "authors": "Ada Lovelace",
        "volume": None, "issue": None,
    })


def test_title_without_authors_is_refetched(tmp_path, monkeypatch):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "metadata.json").write_text(json.dumps({
        "schema_version": "1.0",
        "title": "Title Only",
        "authors": None,
        "doi": "10.1/x",
        "fetched_at": "2026-08-01T00:00:00+00:00",
    }))
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: {"title": "Title Only", "authors": "Ada Lovelace",
                     "journal": "Notes", "volume": None, "issue": None,
                     "pages": None, "year": 1843, "url": None})
    rec = ensure_metadata(paper, network=True)
    assert rec["authors"] == "Ada Lovelace"
    assert rec["first_author"] == "Ada Lovelace"


def test_stale_error_is_retried(tmp_path, monkeypatch):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "metadata.json").write_text(json.dumps({
        "schema_version": "1.0",
        "error": "DOI APIs returned nothing",
        "fetched_at": "2020-01-01T00:00:00+00:00",
        "doi": "10.1/x",
    }))
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: {"title": "Recovered", "authors": "Ada",
                     "journal": None, "volume": None, "issue": None,
                     "pages": None, "year": None, "url": None})
    rec = ensure_metadata(paper, network=True)
    assert rec["title"] == "Recovered"


def test_cached_error_is_not_retried(tmp_path, monkeypatch):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "metadata.json").write_text(json.dumps({
        "schema_version": "1.0",
        "error": "DOI APIs returned nothing",
        "fetched_at": _recent(),
        "doi": "10.1/x",
    }))
    def boom(*a, **k):
        raise AssertionError("must not refetch a recorded failure")
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi", boom)
    rec = ensure_metadata(paper, network=True)
    assert rec["error"] == "DOI APIs returned nothing"


def test_force_retries_a_cached_error(tmp_path, monkeypatch):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "metadata.json").write_text(json.dumps({
        "schema_version": "1.0",
        "error": "DOI APIs returned nothing",
        "fetched_at": _recent(),
        "doi": "10.1/x",
        "title": None,
    }))
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: {"title": "Recovered", "authors": "Ada", "journal": "Notes",
                     "volume": None, "issue": None, "pages": None, "year": 1843,
                     "url": None})
    rec = ensure_metadata(paper, network=True, force=True)
    assert rec["title"] == "Recovered"
    assert not rec.get("error")


# ---------------------------------------------------------------------------
# Schema 1.1: journal_normalized, authors_list, metadata_status, enrichment
# ---------------------------------------------------------------------------

def test_authors_list_shape_from_canned_crossref_payload():
    payload = {"author": [
        {"given": "Nina", "family": "Mazar", "sequence": "first"},
        {"given": "Dan", "family": "Ariely"},
        {"name": "The GRIM Consortium"},
    ]}
    out = authors_list_from_crossref(payload)
    assert out == [
        {"given": "Nina", "family": "Mazar", "full": "Nina Mazar"},
        {"given": "Dan", "family": "Ariely", "full": "Dan Ariely"},
        {"given": None, "family": None, "full": "The GRIM Consortium"},
    ]


def test_authors_list_from_joined_string():
    out = build_authors_list({"authors": "Nina Mazar; Dan Ariely"})
    assert out == [
        {"given": "Nina", "family": "Mazar", "full": "Nina Mazar"},
        {"given": "Dan", "family": "Ariely", "full": "Dan Ariely"},
    ]
    # 'Last, First' single name splits on the comma.
    assert build_authors_list({"authors": "Mazar, Nina"}) == [
        {"given": "Nina", "family": "Mazar", "full": "Nina Mazar"},
    ]
    assert build_authors_list({"authors": None}) == []


def test_structured_authors_survive_a_round_trip():
    """Crossref structure, once had, is preserved — not re-guessed from the
    joined string, which would mis-file multi-word surnames."""
    structured = [{"given": "Hari Shanker", "family": "Sharma",
                   "full": "Hari Shanker Sharma"}]
    out = build_authors_list({
        "authors": "Hari Shanker Sharma",
        "authors_list": structured,
    })
    assert out == structured


def test_given_is_initials_positives():
    for given in ("J.", "J. R.", "J", "A.C.", "J.K."):
        assert given_is_initials(given), given


def test_given_is_initials_negatives():
    # 'Ji-Woo' is a full given name, not initials; so are short and
    # all-caps names. One full word anywhere clears the whole name.
    for given in ("Ji-Woo", "Jo", "JAN", "Nina", "J. Robert", "", None):
        assert not given_is_initials(given), given


def test_authors_have_initials_reads_structured_list_first():
    assert authors_have_initials({"authors_list": [
        {"given": "J.", "family": "Smith", "full": "J. Smith"}]})
    assert not authors_have_initials({"authors_list": [
        {"given": "Ji-Woo", "family": "Kim", "full": "Ji-Woo Kim"}]})
    assert authors_have_initials({"authors": "J. Smith; Alice Jones"})
    assert not authors_have_initials({"authors": "John Smith"})
    assert not authors_have_initials({"authors": None})


def test_refetched_names_update_only_when_more_complete(monkeypatch):
    from forensic_metascience_ai_toolkit.paper_metadata import _expand_abbreviated_authors
    rec = {"doi": "10.1/x", "title": "T",
           "authors": "J. Smith; A. Jones",
           "authors_list": build_authors_list({"authors": "J. Smith; A. Jones"})}

    # More complete -> updated (and Last, First answers are folded first).
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: {"authors": "Smith, John; Jones, Alice"})
    out = _expand_abbreviated_authors(rec)
    assert out["authors"] == "John Smith; Alice Jones"
    assert out["first_author"] == "John Smith"
    assert out["authors_list"][0] == {
        "given": "John", "family": "Smith", "full": "John Smith"}

    # Fewer authors (wrong-paper match) -> unchanged.
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: {"authors": "J. Smith"})
    assert _expand_abbreviated_authors(rec)["authors"] == "J. Smith; A. Jones"

    # Same quality (still initials) -> unchanged.
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: {"authors": "J. A. Smith; A. B. Jones"})
    assert _expand_abbreviated_authors(rec)["authors"] == "J. Smith; A. Jones"

    # A crashing refetch never breaks the record.
    def boom(doi):
        raise RuntimeError("crossref down")
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi", boom)
    assert _expand_abbreviated_authors(rec)["authors"] == "J. Smith; A. Jones"


def test_full_names_are_not_refetched_at_all(monkeypatch):
    from forensic_metascience_ai_toolkit.paper_metadata import _expand_abbreviated_authors
    def boom(*a, **k):
        raise AssertionError("full names must not cost a network call")
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi", boom)
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata._fetch_by_title", boom)
    rec = {"doi": "10.1/x", "authors": "John Smith; Alice Jones"}
    assert _expand_abbreviated_authors(rec) == rec


def test_needs_enrichment_tri_state():
    assert needs_enrichment(None)          # missing file: the backfill visits
    assert needs_enrichment({"schema_version": "1.0", "title": "T",
                             "authors": "Ada Lovelace"})
    assert not needs_enrichment({
        "schema_version": "1.1", "title": "T", "authors": "Ada Lovelace",
        "journal_normalized": None,        # presence, not truthiness:
        "authors_list": [],                # a paper with no journal is legal
        "metadata_status": "ok",
    })


def test_derive_status_four_states():
    assert derive_status({"source": "doi_api", "title": "T",
                          "authors": "Ada"}) == "ok"
    assert derive_status({"source": "doi_api", "title": "T"}) == "partial"
    assert derive_status({"source": "xml", "title": "T", "authors": "Ada",
                          "error": "no DOI on this paper"}) == "partial"
    assert derive_status({"source": "failed",
                          "error": "DOI APIs returned nothing"}) == "failed"
    assert derive_status({"source": "xml", "title": "T",
                          "authors": "Ada"}) == "offline"
    assert derive_status(None) == "failed"


def test_fetch_path_emits_all_v11_fields(tmp_path, monkeypatch):
    paper = tmp_path / "10.1234--x"
    paper.mkdir()
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: {"title": "T", "authors": "Nina Mazar; Dan Ariely",
                     "journal": "Dev. Sci", "volume": None, "issue": None,
                     "pages": None, "year": 2015, "url": None})
    rec = ensure_metadata(paper, network=True)
    assert rec["schema_version"] == "1.1"
    assert rec["journal_normalized"] == "Developmental Science"
    assert rec["authors_list"][0]["family"] == "Mazar"
    assert rec["metadata_status"] == "ok"
    assert not needs_enrichment(rec)


def test_unknown_journal_normalizes_to_itself_never_null(tmp_path, monkeypatch):
    paper = tmp_path / "10.1234--x"
    paper.mkdir()
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: {"title": "T", "authors": "Ada Lovelace",
                     "journal": "Journal of Entirely Imaginary Results",
                     "volume": None, "issue": None, "pages": None,
                     "year": 2020, "url": None})
    rec = ensure_metadata(paper, network=True)
    assert rec["journal_normalized"] == "Journal of Entirely Imaginary Results"


def test_10_to_11_upgrade_in_place_round_trip(tmp_path, monkeypatch):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "metadata.json").write_text(json.dumps({
        "schema_version": "1.0",
        "title": "Cached Title",
        "authors": "Ada Lovelace; Charles Babbage",
        "first_author": "Ada Lovelace",
        "journal": "Dev. Sci",
        "year": 1843,
        "doi": "10.1/x",
        "source": "doi_api",
        "fetched_at": "2015-01-01T00:00:00+00:00",
    }))
    def boom(*a, **k):
        raise AssertionError("full names + core identity must not refetch")
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi", boom)
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata._fetch_by_title", boom)

    rec = ensure_metadata(paper, network=True)
    assert rec["schema_version"] == "1.1"
    assert rec["title"] == "Cached Title"           # 1.0 fields survive
    assert rec["journal"] == "Dev. Sci"             # original kept beside
    assert rec["journal_normalized"] == "Developmental Science"
    assert [a["full"] for a in rec["authors_list"]] \
        == ["Ada Lovelace", "Charles Babbage"]
    assert rec["metadata_status"] == "ok"

    on_disk = load_cached(paper)                    # upgraded IN PLACE
    assert on_disk["schema_version"] == "1.1"
    assert not needs_enrichment(on_disk)

    again = ensure_metadata(paper, network=True)    # second call: early return
    assert again == on_disk


def test_offline_upgrade_is_returned_but_not_written(tmp_path):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "metadata.json").write_text(json.dumps({
        "schema_version": "1.0",
        "title": "Cached Title",
        "authors": "Ada Lovelace",
        "doi": "10.1/x",
        "source": "doi_api",
    }))
    rec = ensure_metadata(paper, network=False)
    assert rec["schema_version"] == "1.1"
    assert "journal_normalized" in rec
    on_disk = json.loads((paper / "metadata.json").read_text())
    assert on_disk["schema_version"] == "1.0", (
        "the scanner path only reads; the upgrade is written on the next "
        "network fetch, not by a page open")


def test_upgrade_refetches_initials_only_authors(tmp_path, monkeypatch):
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "metadata.json").write_text(json.dumps({
        "schema_version": "1.0",
        "title": "Cached Title",
        "authors": "J. Smith; A. Jones",
        "doi": "10.1/x",
        "source": "doi_api",
    }))
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi",
        lambda doi: {"authors": "John Smith; Alice Jones"})
    rec = ensure_metadata(paper, network=True)
    assert rec["authors"] == "John Smith; Alice Jones"
    assert rec["first_author"] == "John Smith"
    assert load_cached(paper)["authors"] == "John Smith; Alice Jones"


def test_upgrade_survives_a_failed_name_refetch(tmp_path, monkeypatch):
    """A downed API must not block the schema upgrade: names stay
    abbreviated, the file still becomes 1.1, nothing raises."""
    paper = tmp_path / "10.1--x"
    paper.mkdir()
    (paper / "metadata.json").write_text(json.dumps({
        "schema_version": "1.0",
        "title": "Cached Title",
        "authors": "J. Smith; A. Jones",
        "doi": "10.1/x",
        "source": "doi_api",
    }))
    def boom(doi):
        raise RuntimeError("crossref down")
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata.fetch_metadata_from_doi", boom)
    rec = ensure_metadata(paper, network=True)
    assert rec["schema_version"] == "1.1"
    assert rec["authors"] == "J. Smith; A. Jones"
    assert load_cached(paper)["schema_version"] == "1.1"


def test_no_doi_paper_falls_back_to_title_search(tmp_path, monkeypatch):
    paper = tmp_path / "paper-with-no-doi"
    paper.mkdir()
    (paper / "paper.xml").write_text(
        '<?xml version="1.0"?><article><front><article-meta>'
        '<title-group><article-title>The Found Title</article-title>'
        '</title-group></article-meta></front><body/></article>',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata._fetch_by_title",
        lambda title: {"doi": "10.9/z", "authors": "Ada Lovelace",
                       "title": "The Found Title", "journal": "Notes",
                       "volume": None, "issue": None, "pages": None,
                       "year": 1843, "url": None})
    rec = ensure_metadata(paper, network=True)
    assert rec["source"] == "title_api+xml"
    assert rec["doi"] == "10.9/z"
    assert rec["authors"] == "Ada Lovelace"
    assert not rec.get("error")
    assert rec["metadata_status"] == "ok"


def test_no_doi_and_no_title_match_is_recorded_not_invented(tmp_path, monkeypatch):
    paper = tmp_path / "paper-with-no-doi"
    paper.mkdir()
    (paper / "paper.xml").write_text(
        '<?xml version="1.0"?><article><front><article-meta>'
        '<title-group><article-title>An Unfindable Title</article-title>'
        '</title-group></article-meta></front><body/></article>',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "forensic_metascience_ai_toolkit.paper_metadata._fetch_by_title", lambda title: None)
    rec = ensure_metadata(paper, network=True)
    assert "no DOI" in rec["error"]
    # The 'no DOI' error still parks the paper: asking again cannot help.
    assert not needs_network(load_cached(paper))
