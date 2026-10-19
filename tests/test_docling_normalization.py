"""Ligature splits and raw entities are healed at CACHE-WRITE time (schema 5).

WHY THIS FILE EXISTS. Docling renders a word containing a ligature glyph as
three space-separated fragments -- MEASURED 2026-08-21 in the live cache entry
for `10.1073--pnas.1211286109` (extractor 2.119.0): 75 sites in `text`, every
one of the shape `signi fi cantly` / `many fi elds`, plus raw `&lt;`/`&amp;`
entities around the paper's own p-values (`P &lt; 0.01`). Text in that state
hides comparisons from statcheck and breaks quote verification the same way
pdfplumber's `(cid:1)` glyphs did.

The repair is LEXICAL AND CLOSED, because the two shapes need opposite fixes
(`significantly` joins across both spaces; `many fields` keeps its word break)
and nothing in the string distinguishes them. A site neither reading of which
is a known word is LEFT ALONE: corrupt text we keep is the status quo, corrupt
text we manufacture is new. These tests pin the fix against the specific
instances that defined the defect (LESSONS.md #7), the guards that stop it
corrupting honest text, and the cache discipline around it: fresh entries are
stamped schema 5 and folded; older schemas are still served as-is.
"""
import json
from types import SimpleNamespace

import pytest

from metascience_agent.extraction import docling_tables as dl
from metascience_agent.extraction.docling_tables import (
    _heal_ligatures,
    _normalize_extracted,
)


class TestTheMeasuredCorruptionHeals:
    """Every case here is a real site from the measured cache entry."""

    @pytest.mark.parametrize("corrupt, healed", [
        # Mid-word splits: the fragments join across BOTH spaces.
        ("evaluate the ef fi cacy of educating faculty",
         "evaluate the efficacy of educating faculty"),
        ("as signi fi cantly more competent",
         "as significantly more competent"),
        ("a de fi cit of workers", "a deficit of workers"),
        ("declare no con fl ict of interest", "declare no conflict of interest"),
        ("regression coef fi cients", "regression coefficients"),
        ("equally quali fi ed men and women", "equally qualified men and women"),
        ("may in fl uence decisions", "may influence decisions"),
        ("dropped to nonsigni fi cance", "dropped to nonsignificance"),
        ("a funneled debrie fi ng", "a funneled debriefing"),
        # Word-initial splits: the word BEFORE the ligature is intact, so the
        # word break stays and only the split word rejoins.
        ("within many fi elds of science", "within many fields of science"),
        ("These fi ndings support hypothesis", "These findings support hypothesis"),
        ("our mediation fi ndings shed light", "our mediation findings shed light"),
        ("encouragement and fi nancial rewards",
         "encouragement and financial rewards"),
        ("create more fl exible work settings",
         "create more flexible work settings"),
        ("Undisclosed fl exibility in data collection",
         "Undisclosed flexibility in data collection"),
        ("it fi lls a critical gap", "it fills a critical gap"),
    ])
    def test_measured_sites(self, corrupt, healed):
        assert _heal_ligatures(corrupt) == healed

    def test_two_sites_in_one_word_pair(self):
        """`scienti fi c fi eld` carries a mid-word split and a word-initial
        split three characters apart; each must get its own repair."""
        assert (_heal_ligatures("participants ' scienti fi c fi eld, age")
                == "participants ' scientific field, age")

    def test_both_readings_being_words_needs_a_dangling_fragment_to_join(self):
        """`bene fi t` is `benefit`, but `fit` is also a word. The full join
        wins only because `bene` on its own is no reading at all."""
        assert (_heal_ligatures("opportunity to bene fi t from")
                == "opportunity to benefit from")
        assert (_heal_ligatures("Barriers: Ful fi lling the Potential")
                == "Barriers: Fulfilling the Potential")
        assert (_heal_ligatures("associated with de fi nite consequences")
                == "associated with definite consequences")

    def test_case_is_preserved(self):
        assert _heal_ligatures("Speci fi cally, we") == "Specifically, we"


class TestHonestTextIsLeftAlone:
    """A wrong rejoin corrupts real words, which is worse than the split."""

    def test_a_capitalized_token_is_not_a_ligature(self):
        """Ligature glyphs have no uppercase form, so `Sci Fi` is two words."""
        s = "a classic Sci Fi movie"
        assert _heal_ligatures(s) == s

    def test_an_unrecognized_site_is_not_guessed_at(self):
        """Lowercase `sci fi genre` matches the split SHAPE, but neither
        `scifigenre` nor `figenre` is a word, so nothing may move."""
        s = "the sci fi genre was popular"
        assert _heal_ligatures(s) == s

    def test_a_genuinely_ambiguous_site_is_left_alone(self):
        """`in fi nite samples` reads as `infinite samples` AND as the honest
        statistics phrase `in finite samples`. Both are words, and `in` is a
        word too, so there is no dangling fragment to break the tie: leave it."""
        s = "the estimator is biased in fi nite samples"
        assert _heal_ligatures(s) == s

    def test_a_newline_split_is_not_matched(self):
        """The measured corruption is single-spaced; anything else is out of
        the pattern's reach on purpose."""
        s = "signi fi\ncantly"
        assert _heal_ligatures(s) == s


class TestEntities:
    def test_amp_unescapes(self):
        assert _normalize_extracted("John Wiley &amp; Sons") == "John Wiley & Sons"

    def test_comparisons_reach_statcheck_as_comparisons(self):
        """`P &lt; 0.01` hides the comparator from statcheck exactly the way
        pdfplumber's glyph references hid the minus sign."""
        assert (_normalize_extracted("was signi fi cant (all P &lt; 0.01)")
                == "was significant (all P < 0.01)")
        assert _normalize_extracted("all P &gt; 0.14") == "all P > 0.14"

    def test_unescape_is_single_pass(self):
        """A double-escaped entity unescapes ONE level, not to the character."""
        assert _normalize_extracted("&amp;lt;") == "&lt;"

    def test_empty_text_passes_through(self):
        assert _normalize_extracted("") == ""


# --- cache-write integration -------------------------------------------------

_CORRUPT_TEXT = ("The ef fi cacy of the treatment was signi fi cant "
                 "(P &lt; 0.01) across many fi elds &amp; cohorts.")
_HEALED_TEXT = ("The efficacy of the treatment was significant "
                "(P < 0.01) across many fields & cohorts.")


class _StubDoc:
    """The narrowest object `extract_pdf_tables` reads off a docling result."""

    def __init__(self, text, page_texts, grids):
        self._text = text
        self._page_texts = list(page_texts)
        self.pages = {i: object() for i in range(1, len(self._page_texts) + 1)}
        self.tables = [
            SimpleNamespace(
                data=SimpleNamespace(grid=[
                    [SimpleNamespace(text=c) for c in row] for row in g
                ]),
                prov=[SimpleNamespace(page_no=1)],
                captions=[],
            )
            for g in grids
        ]

    def export_to_markdown(self):
        return self._text

    def iterate_items(self):
        for i, t in enumerate(self._page_texts, 1):
            yield SimpleNamespace(prov=[SimpleNamespace(page_no=i)], text=t), 0


def _stub_converter(monkeypatch, doc):
    monkeypatch.setattr(dl, "available", lambda: (True, ""))
    monkeypatch.setattr(
        dl, "_converter",
        lambda: SimpleNamespace(convert=lambda _p: SimpleNamespace(document=doc)))


def _forbid_converter(monkeypatch):
    def _boom():  # pragma: no cover -- reaching it IS the failure
        raise AssertionError("the layout model must not start on a cache hit")
    monkeypatch.setattr(dl, "_converter", _boom)


@pytest.fixture
def pdf(tmp_path):
    p = tmp_path / "10.1234--lig.pdf"
    p.write_bytes(b"%PDF-1.4\nnot really a pdf\n")
    return p


class TestTheFoldRunsAtCacheWriteTime:
    def test_text_pages_and_cells_are_folded_and_stamped_schema_5(
            self, pdf, monkeypatch):
        doc = _StubDoc(
            _CORRUPT_TEXT,
            page_texts=[_CORRUPT_TEXT],
            grids=[[["Measure", "Value"],
                    ["Signi fi cance", "0.03 ± 0.01"],
                    ["Groups", "A &amp; B"]]],
        )
        _stub_converter(monkeypatch, doc)

        out = dl.extract_pdf_tables(pdf, use_cache=False)
        assert out["error"] is None
        # BUMPED TO 7, 2026-08-29: cells now carry their physical `col`, and a
        # cache written before that serves coordinate-less cells that no
        # consumer can address by position. The literal is deliberate -- it is
        # a ratchet, so a schema bump must be acknowledged by a human here
        # rather than sliding through against the constant.
        assert out["cache_schema"] == dl.CACHE_SCHEMA == 7
        assert out["text"] == _HEALED_TEXT
        assert out["pages"][0]["text"] == _HEALED_TEXT

        data = out["tables"][0]["data"]
        assert data[1][0] == "Significance"
        assert data[2][1] == "A & B"
        # THE SAME FOLD ONLY: the cell is otherwise byte-faithful -- the `±`
        # the authors printed survives (the pdf4llm normalizer's `+-` rewrite
        # is recorded in docs/archive/ingestion_learnings.md as what NOT to do).
        assert data[1][1] == "0.03 ± 0.01"

        # And the fold is in the WRITTEN entry, not only the return value:
        # the cache is what every later reader sees.
        on_disk = json.loads(dl._cache_path(pdf).read_text(encoding="utf-8"))
        assert on_disk["cache_schema"] == 7
        assert on_disk["text"] == _HEALED_TEXT
        assert on_disk["tables"][0]["data"][1][0] == "Significance"

    def test_use_cache_false_still_writes(self, pdf, monkeypatch):
        """Read and write are separate decisions; `--force` must persist."""
        doc = _StubDoc(_CORRUPT_TEXT, page_texts=[_CORRUPT_TEXT], grids=[])
        _stub_converter(monkeypatch, doc)
        assert not dl._cache_path(pdf).is_file()
        dl.extract_pdf_tables(pdf, use_cache=False)
        assert dl._cache_path(pdf).is_file()
        # tmp+rename: no half-written temp file left beside the entry
        leftovers = [f for f in dl._cache_path(pdf).parent.iterdir()
                     if f.suffix == ".tmp"]
        assert leftovers == []


class TestOlderSchemasAreStillServedAsIs:
    """Deliberate discipline (see the read path in `extract_pdf_tables`):
    invalidating every pre-5 entry to obtain the fold would make every cheap
    read pay for a re-extraction, which is the same regression that once took
    the suite from 260 s to 596 s. A stale entry keeps its splits until someone
    re-extracts with `--force`."""

    @pytest.mark.parametrize("schema", [2, 3, 4])
    def test_a_pre_fold_entry_is_served_unmodified(self, pdf, monkeypatch, schema):
        _forbid_converter(monkeypatch)
        entry = {"tables": [], "text": _CORRUPT_TEXT, "error": None,
                 "n_tables": 0, "pages": [{"page_num": 1, "text": _CORRUPT_TEXT}],
                 "cache_schema": schema}
        c = dl._cache_path(pdf)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(entry), encoding="utf-8")

        out = dl.extract_pdf_tables(pdf, use_cache=True)
        assert out["cached"] is True
        assert out["cache_schema"] == schema
        assert out["text"] == _CORRUPT_TEXT, (
            "a pre-schema-5 entry was rewritten on read; older schemas are "
            "served as-is and re-folded only by an explicit re-extraction")

    def test_an_unstamped_entry_is_served_too(self, pdf, monkeypatch):
        _forbid_converter(monkeypatch)
        entry = {"tables": [], "text": _CORRUPT_TEXT}
        c = dl._cache_path(pdf)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(entry), encoding="utf-8")

        out = dl.extract_pdf_tables(pdf, use_cache=True)
        assert out["cached"] is True
        assert out["text"] == _CORRUPT_TEXT


class TestBothFlavorsOfSchema5AreStale:
    """The stacked-headers merge found TWO branches had independently stamped
    cache_schema 5 with different contents -- one 5 meant ligature healing,
    the other stacked-header labels. An on-disk 5 therefore cannot prove it
    carries either fix, so `cache_status` must report it stale (schema is now
    6), whichever flavor wrote it."""

    def test_a_schema_5_entry_is_reported_stale(self, pdf):
        entry = {"tables": [], "text": "body", "pages": [{"text": "body"}],
                 "cache_schema": 5, "error": None}
        c = dl._cache_path(pdf)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(entry), encoding="utf-8")
        ok, why = dl.cache_status(pdf)
        assert ok is False
        assert "5" in why

    def test_a_schema_6_entry_is_current(self, pdf):
        entry = {"tables": [], "text": "body", "pages": [{"text": "body"}],
                 "cache_schema": dl.CACHE_SCHEMA, "error": None}
        c = dl._cache_path(pdf)
        c.parent.mkdir(parents=True, exist_ok=True)
        c.write_text(json.dumps(entry), encoding="utf-8")
        ok, why = dl.cache_status(pdf)
        assert ok is True, why
