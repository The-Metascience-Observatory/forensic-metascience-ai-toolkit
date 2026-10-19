"""The converted document must say whether conversion damaged it.

`markdown/body.md` exists so a human can check that conversion did not mangle
the paper -- Greg's stated reason for wanting it: "for the sake of
inspectability/auditability it is important for the human user (or in my case,
developer) to see whether the converted document doesn't inherit gross
errors/artifacts from the conversion process."

THE DEFECT. `source.json` recorded schema, channel, length, table-placeholder
counts and a hash -- everything EXCEPT that property. A paper whose text layer
is known character-corrupt produced a `source.json` identical in shape to a
clean one's, and a `body.md` that opens like any other document.

MEASURED on the 12-paper corpus, 2026-08-31: eleven convert clean;
`10.1371--journal.pone.0069841` carries 23 corruption sites -- 14 `<` rendered
as `,` (so `p < .0001` reads `p , .0001`) and 9 lost operators before a decimal
(`B = -.006` reads `B = 2 .006`, putting an invented leading digit AND a wrong
sign into a value a check will read). `glyphs.scan` detects all 23;
`proven_repairs` correctly returns `{}` because none is provable. The knowledge
existed and did not reach the artifact a reader opens.

That is the house failure mode with the sign flipped: not a missing capability,
but a file that renders the ABSENCE of a warning as health.
"""
from __future__ import annotations

import json
import pathlib

import pytest

from forensic_metascience_ai_toolkit.extraction import markdown_out as M

REPO = pathlib.Path(__file__).resolve().parent.parent
CORPUS = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on"
CORRUPT = "10.1371--journal.pone.0069841"


class TestTheVerdictIsRecorded:
    def test_a_clean_conversion_says_so(self, tmp_path):
        rec = M.write_markdown(tmp_path, "A clean paper. The mean was 4.2 (SD 1.1).", "pdf")
        assert rec["text_is_clean"] is True
        assert rec["quarantine"] is False
        assert rec["glyph_sites"] == 0
        assert rec["digits_corrupted"] is False

    def test_a_corrupt_conversion_says_so_and_names_the_damage(self, tmp_path):
        corrupt = ("Change was significant, B = 2 .012, b = 2 .124, "
                   "t (73) = 2 2.39, p =.02, and p , .0001 elsewhere.")
        rec = M.write_markdown(tmp_path, corrupt, "pdf")
        assert rec["text_is_clean"] is False
        assert rec["quarantine"] is True
        assert rec["glyph_sites"] > 0
        assert rec["digits_corrupted"] is True, (
            "the operator-lost pattern puts a wrong sign and an invented "
            "leading digit into a value a check will read; that is the half "
            "of the verdict that matters")
        names = {p["pattern"] for p in rec["glyph_patterns"]}
        assert names, rec["glyph_patterns"]

    def test_a_scan_failure_is_not_recorded_as_clean(self, tmp_path, monkeypatch):
        """FAILS OPEN IS THE ONE THING THIS MUST NOT DO. A missing verdict has
        to be distinguishable from a clean one, or the field is worse than
        absent -- it would certify health it never checked."""
        import forensic_metascience_ai_toolkit.glyphs as G
        monkeypatch.setattr(G, "scan", lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("boom")))
        rec = M.write_markdown(tmp_path, "text", "pdf")
        assert rec["text_is_clean"] is None
        assert rec["quarantine"] is None
        assert "glyph_scan_error" in rec


class TestTheSchemaBumpReachesPapersAlreadyOnDisk:
    def test_the_currency_check_reads_the_schema(self):
        """`materialise` skips a rewrite when the text hash matches. Adding a
        metadata field without bumping the schema would therefore leave every
        paper already converted with the old shape, forever."""
        import inspect
        src = inspect.getsource(M.materialise)
        assert "markdown_schema" in src and "MARKDOWN_SCHEMA" in src

    def test_the_schema_is_past_the_version_that_lacked_the_verdict(self):
        assert M.MARKDOWN_SCHEMA >= 2


@pytest.mark.skipif(not (CORPUS / CORRUPT / "markdown" / "source.json").is_file(),
                    reason="corpus not converted in this checkout")
class TestTheLiveCorpus:
    def _meta(self, name):
        return json.loads((CORPUS / name / "markdown" / "source.json").read_text(encoding="utf-8"))

    def test_the_known_corrupt_paper_is_flagged(self):
        m = self._meta(CORRUPT)
        assert m["text_is_clean"] is False and m["quarantine"] is True
        assert m["digits_corrupted"] is True
        assert m["glyph_sites"] >= 20

    def test_the_others_are_not_flagged(self):
        """The off-switch: a stamp that flagged everything would be useless."""
        clean = [d.name for d in sorted(CORPUS.iterdir())
                 if d.is_dir() and (d / "markdown" / "source.json").is_file()
                 and d.name != CORRUPT]
        assert clean, "no other converted papers to compare against"
        for name in clean:
            assert self._meta(name)["text_is_clean"] is True, name
