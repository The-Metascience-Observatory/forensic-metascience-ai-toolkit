"""What a file IS gets declared, never guessed from its name.

Greg, 2026-08-13: "The detection of supplements shouldn't be contingent on the
file naming. This is an issue for the pre-pipeline steps, wherein the user's use
of the tool requires distinguishing the main body from (1) supplements and (2)
repos." And: "this is something the model shouldn't have to deal with. The user
(or the agent they're interfacing with to use the CLI) should have to provide
these, and specify."

THE COST OF THE OLD RULE, MEASURED THE DAY IT WAS FOUND. Detection keyed on
seven filename substrings. Wiley names its supplement `EAT-58-1072-s001.docx`;
none of the seven appears in it; the file was skipped so quietly that it reached
NEITHER the usable nor the unusable list, `problems` stayed empty, and the run
reported no supplement for a paper whose supplement sat in its own directory
holding 7 tables and 599 cells, 99 of them consumable by a check. Adding it took
that paper's manifest from 325 checkable items to 924.

Of nine real publisher conventions the hint list matched four. It missed Wiley
`-s001`, Elsevier `mmc1`, PLOS `S1_Table` and `.s001`, and JAMA `-s001` -- and
it also missed OUR OWN FETCHER'S output, which saves supplements as
`<stem>_supplementary_info_N_<original>`. A hint list is always one publisher
behind, so there is no version of it worth keeping.

AND THE FETCHER HAS MORE THAN ONE MANGLING. Found 2026-08-19 on
`10.1161--strokeaha.124.049834`, which was refused as "supplement missing" while
`10.1161--strokeaha.124.049834_linked_data_dataverse_Z8WAKW_ESCAS.xlsx` sat in
its own directory, byte-identical to the file its record declares. The
supplementary-info path records the name it SAVED; the linked-data path records
the name it FETCHED (`10.7910_dvn_z8wakw/ESCAS.xlsx`), so exact matching had
nothing to match. See `TestOurOwnDownloadsAreRecognised`.

Three authorities now, and none of them guesses: the operator's `inputs.json`,
the article's own supplementary-material list, and the DOI stem for the article
file itself. Anything else is `undeclared` -- REPORTED, never skipped.
"""

from pathlib import Path

import pytest

from metascience_agent import supplements as S

REPO = Path(__file__).resolve().parents[1]


class TestNamingIsNoLongerAGate:
    """The specific file that exposed this, and the conventions like it."""

    @pytest.mark.parametrize("name", [
        "EAT-58-1072-s001.docx",                       # Wiley
        "1-s2.0-S0140673623001234-mmc1.pdf",           # Elsevier
        "S1_Table.xlsx",                               # PLOS
        "pone.0254493.s001.docx",                      # PLOS, other form
        "jamanetwopen-e2337679-s001.pdf",              # JAMA
        "totally_arbitrary_name.docx",                 # no convention at all
    ])
    def test_a_declared_file_is_a_supplement_whatever_it_is_called(
            self, tmp_path, name):
        (tmp_path / name).write_bytes(b"%PDF-1.4\n." if name.endswith(".pdf")
                                      else b"PK\x03\x04placeholder")
        S.write_declaration(tmp_path, supplements=[name])
        c = S.classify_inputs(tmp_path)
        assert name in c["supplements"], f"{name} declared and still not used"
        assert c["undeclared"] == []

    def test_none_of_those_names_matches_the_old_hint_list(self):
        """If they did, this whole test class would be proving nothing."""
        for name in ("EAT-58-1072-s001.docx", "1-s2.0-x-mmc1.pdf",
                     "S1_Table.xlsx", "pone.0254493.s001.docx"):
            assert not any(h in name.lower() for h in S._SI_HINTS), name


class TestNothingIsSkippedInSilence:
    """A file we passed over is indistinguishable from a file that is not
    there. That confusion is what cost a whole supplement."""

    def test_an_undeclared_file_is_reported_not_dropped(self, tmp_path):
        (tmp_path / "mystery.docx").write_bytes(b"PK\x03\x04x")
        c = S.classify_inputs(tmp_path)
        assert c["undeclared"] == ["mystery.docx"]
        assert "UNDECLARED" in c["note"]
        assert c["supplements"] == []

    def test_the_note_says_what_it_costs_the_reader(self, tmp_path):
        (tmp_path / "mystery.docx").write_bytes(b"PK\x03\x04x")
        note = S.classify_inputs(tmp_path)["note"]
        assert "were not used" in note and "never had them" in note

    def test_a_clean_directory_says_so_without_a_warning(self, tmp_path):
        (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4\n.")
        S.write_declaration(tmp_path, articles=["paper.pdf"])
        c = S.classify_inputs(tmp_path)
        assert c["undeclared"] == [] and "UNDECLARED" not in c["note"]


class TestTheAuthoritiesRankCorrectly:
    def test_the_operator_overrides_the_article(self, tmp_path):
        (tmp_path / "thing.pdf").write_bytes(b"%PDF-1.4\n.")
        (tmp_path / "x_supplementary_info.json").write_text(
            '{"declared": {"missing": ["thing.pdf"]}}', encoding="utf-8")
        assert S.classify_inputs(tmp_path)["supplements"] == ["thing.pdf"]
        S.write_declaration(tmp_path, ignores=["thing.pdf"])
        c = S.classify_inputs(tmp_path)
        assert c["supplements"] == []
        assert [f["declared_by"] for f in c["files"]] == ["operator"]

    def test_the_article_file_is_never_read_as_its_own_supplement(self, tmp_path):
        d = tmp_path / "10.1234--demo"
        d.mkdir()
        (d / "10.1234--demo.pdf").write_bytes(b"%PDF-1.4\n.")
        c = S.classify_inputs(d)
        assert c["supplements"] == []
        assert c["files"][0]["role"] == "article"

    def test_our_own_fetchers_saved_name_is_recognised(self, tmp_path):
        """The fetcher writes `<stem>_supplementary_info_N_<original>`, which no
        publisher convention resembles. Reading our own record is bookkeeping,
        not inference."""
        d = tmp_path / "10.1234--demo"
        d.mkdir()
        saved = "10.1234--demo_supplementary_info_1_appendix.pdf"
        (d / saved).write_bytes(b"%PDF-1.4\n.")
        (d / "10.1234--demo_supplementary_info.json").write_text(
            '{"files": [{"filename": "' + saved + '", "role": "supplement"}]}',
            encoding="utf-8")
        assert S.classify_inputs(d)["supplements"] == [saved]

    def test_a_declared_name_still_has_to_be_a_real_file(self, tmp_path):
        """A NAME IS NOT A FILE, whoever declared it. A zero-byte placeholder is
        what an interrupted download leaves behind, and it used to satisfy the
        gate while the run proceeded as though the SI had been read."""
        (tmp_path / "empty.pdf").write_bytes(b"")
        S.write_declaration(tmp_path, supplements=["empty.pdf"])
        c = S.classify_inputs(tmp_path)
        assert c["supplements"] == []
        assert "zero bytes" in c["unusable"][0]["reason"]


class TestRawDataIsItsOwnRole:
    """Greg named three things to tell apart: the main body, supplements, and
    repos. A duplication sweep consumes a data file and a table check does not,
    so flattening the third into the second loses that."""

    def test_a_dataset_is_declared_and_kept_separate(self, tmp_path):
        (tmp_path / "trial_rows.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        S.write_declaration(tmp_path, datasets=["trial_rows.csv"])
        c = S.classify_inputs(tmp_path)
        assert c["datasets"] == ["trial_rows.csv"]
        assert c["supplements"] == []

    def test_but_it_still_reaches_the_checks(self, tmp_path):
        """Kept separate for labelling, not withheld: excluding data files from
        `present_files` is how a 7,738-cell dataset became invisible."""
        (tmp_path / "trial_rows.csv").write_text("a,b\n1,2\n", encoding="utf-8")
        S.write_declaration(tmp_path, datasets=["trial_rows.csv"])
        assert "trial_rows.csv" in S.present_files(tmp_path)


class TestTheRealPaperItWasFoundOn:
    DIR = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1002--eat.24415"

    def test_the_wiley_docx_is_found_with_no_declaration_written(self):
        """The fetch record already named it. The information was there all
        along; only the filename gate stood between it and the run."""
        if not self.DIR.is_dir():
            pytest.skip("Romano not in this checkout")
        c = S.classify_inputs(self.DIR)
        assert "EAT-58-1072-s001.docx" in c["supplements"]
        assert c["undeclared"] == []

    def test_it_reaches_the_completeness_manifest(self):
        if not self.DIR.is_dir():
            pytest.skip("Romano not in this checkout")
        from metascience_agent import completeness as C
        m = C.build_manifest(self.DIR)
        # 325 items before the docx was recognised, 924 after.
        assert m["n_supplement_items"] > 500, (
            "the docx is present and contributed nothing; the manifest is back "
            "to counting only the article")


class TestACorruptDeclarationIsNotAnEmptyOne:
    """`{}` on a JSON error is byte-identical to "the operator declared
    nothing", so one typo in the single file carrying their intent would have
    silently reverted the directory to undeclared. Caught by `lint-inert` as a
    29th proven-inert finding, not by review."""

    def test_it_says_the_declaration_is_not_in_force(self, tmp_path):
        (tmp_path / "inputs.json").write_text("{ not json", encoding="utf-8")
        (tmp_path / "x.docx").write_bytes(b"PK\x03\x04x")
        c = S.classify_inputs(tmp_path)
        assert c["problems"] and "could not be read" in c["problems"][0]
        assert "nothing you declared is in force" in c["note"]
        assert c["declaration_present"] is False

    def test_a_json_array_is_refused_the_same_way(self, tmp_path):
        (tmp_path / "inputs.json").write_text("[]", encoding="utf-8")
        c = S.classify_inputs(tmp_path)
        assert c["problems"] and "not a JSON object" in c["problems"][0]


class TestOurOwnDownloadsAreRecognised:
    """A file this pipeline downloaded, for a file the article declares, is not
    an unknown file. Failing to recognise it made `supplements.gate` refuse a
    whole paper as incomplete while its supplement lay in the directory -- an
    absence asserted where there was presence, which is the failure this
    repository exists to avoid making about a PAPER, let alone about itself.
    """

    @staticmethod
    def _paper(tmp_path, stem, saved_name, declared_name, role="supplement"):
        import json as _json

        d = tmp_path / stem
        d.mkdir()
        (d / f"{stem}.pdf").write_bytes(b"%PDF-1.4\n.")
        # Real magic bytes for the real suffix: `_unusable_because` rejects a
        # .pdf that is not one, and that guard is right -- a fixture must not
        # trip it while pretending to test naming.
        (d / saved_name).write_bytes(
            b"%PDF-1.4\n." if saved_name.lower().endswith(".pdf")
            else b"PK\x03\x04placeholder")
        (d / f"{stem}_supplementary_info.json").write_text(_json.dumps({
            "schema_version": 1, "stem": stem, "status": "ok",
            "files": [{"index": 1, "filename": declared_name,
                       "original_name": Path(declared_name).name,
                       "role": role}],
        }), encoding="utf-8")
        return d

    def test_the_linked_data_mangling_is_recognised(self, tmp_path):
        # The real shape, from 10.1161--strokeaha.124.049834.
        stem = "10.1161--strokeaha.124.049834"
        d = self._paper(tmp_path, stem,
                        f"{stem}_linked_data_dataverse_Z8WAKW_ESCAS.xlsx",
                        "10.7910_dvn_z8wakw/ESCAS.xlsx")
        c = S.classify_inputs(d)
        row = next(r for r in c["files"] if r["name"].endswith("ESCAS.xlsx"))
        assert row["role"] == "supplement"
        assert row["declared_by"] == "fetcher"
        assert c["undeclared"] == []

    def test_the_supplementary_info_mangling_still_matches_exactly(self, tmp_path):
        # This one the record names as saved, so it never needed the new path.
        stem = "10.1161--strokeaha.115.009416"
        saved = f"{stem}_supplementary_info_1_str-47-151-s001.pdf"
        d = self._paper(tmp_path, stem, saved, saved)
        row = next(r for r in S.classify_inputs(d)["files"] if r["name"] == saved)
        assert row["role"] == "supplement"
        assert row["declared_by"] == "article"

    def test_a_file_we_did_not_write_is_not_claimed(self, tmp_path):
        # No stem prefix, so it is not our output and gets no role from this
        # rule. `undeclared` is the honest answer, and it is REPORTED.
        stem = "10.1161--demo"
        d = self._paper(tmp_path, stem, "someone_elses_ESCAS.xlsx",
                        "10.7910_dvn_x/ESCAS.xlsx")
        row = next(r for r in S.classify_inputs(d)["files"]
                   if r["name"] == "someone_elses_ESCAS.xlsx")
        assert row["role"] == "undeclared"

    def test_a_coincidental_ending_does_not_win_a_role(self, tmp_path):
        # `<stem>_data.xlsx` ends with "data.xlsx" but not with "_raw_data.xlsx",
        # so it must not inherit the declared file's role. A bare suffix test
        # would have claimed it, and a guessed role is a guessed analysis.
        stem = "10.1161--demo"
        d = self._paper(tmp_path, stem, f"{stem}_data.xlsx", "repo/raw_data.xlsx")
        row = next(r for r in S.classify_inputs(d)["files"]
                   if r["name"] == f"{stem}_data.xlsx")
        assert row["role"] == "undeclared"

    def test_the_longest_declared_name_wins(self):
        # A record declaring both `s001.pdf` and `str-47-151-s001.pdf` must not
        # let the shorter one decide the role of a file that matches both.
        assert S._fetched_under_a_mangled_name(
            "10.1161--x_linked_data_repo_id_str-47-151-s001.pdf",
            "10.1161--x",
            {"s001.pdf": "dataset", "str-47-151-s001.pdf": "supplement"},
        ) == ("supplement", "str-47-151-s001.pdf")

    def test_the_gate_opens_once_the_file_is_seen(self, tmp_path):
        stem = "10.1161--demo"
        d = self._paper(tmp_path, stem,
                        f"{stem}_linked_data_dataverse_ABC_ESCAS.xlsx",
                        "10.7910_dvn_abc/ESCAS.xlsx")
        body = "Additional detail is available in the Supplemental Material."
        (d / "body.md").write_text(body, encoding="utf-8")
        assert S.gate(d, body_text=body)["proceed"] is True
