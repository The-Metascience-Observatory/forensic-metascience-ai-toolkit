"""Declared dependencies that were absent, and invisible.

`python-docx` and `openpyxl` are HARD dependencies in pyproject.toml. They were
missing from the venv -- built by uv, no pip, editable install, which does not
re-resolve when the manifest changes -- so they were declared, absent, and
undetectable.

The cost: 56 supplements in the working corpus (50 .docx, 6 .xlsx) read as
empty. `extract_supplement` returned a structured error that looks like a
property of the FILE ("python-docx is not installed") rather than of our
environment, and a 1.77 MB Word supplement holding 3 tables and 11,198
characters was reduced to nothing in a billed run. `preflight` said READY.
"""
import importlib

import pytest

from metascience_agent.extraction.supplements_read import (
    READABLE,
    UNREADABLE,
    extract_supplement,
)


class TestTheLibrariesAreActuallyPresent:
    """These are not optional extras. A run without them produces confidently
    wrong coverage, which is the one failure mode preflight exists to stop."""

    @pytest.mark.parametrize("mod", ["docx", "openpyxl"])
    def test_importable(self, mod):
        importlib.import_module(mod)

    @pytest.mark.parametrize("mod", ["docx", "openpyxl"])
    def test_declared_in_the_manifest(self, mod):
        """If it is required to read half the corpus, it is a dependency."""
        from pathlib import Path
        text = Path("pyproject.toml").read_text()
        name = {"docx": "python-docx", "openpyxl": "openpyxl"}[mod]
        assert name in text


class TestPreflightWouldCatchTheirAbsence:
    """These checks moved from an inline block in `cli.py` into
    `preflight.py`, where the automatic pre-spend gate also reads them. That
    made the old source-grep assertions both wrong and weaker than they could
    be: the questions "is it checked" and "is it fatal" are now answerable by
    CALLING the thing rather than by matching strings in the file that happens
    to render it."""

    def test_both_are_checked(self):
        from metascience_agent.preflight import fatal_checks

        names = " ".join(n for n, _, _ in fatal_checks(refresh=True))
        assert "python-docx" in names and "openpyxl" in names

    @pytest.mark.parametrize("mod", ["docx", "openpyxl"])
    def test_they_are_fatal_not_advisory(self, monkeypatch, mod):
        """A warning would be skipped. The whole point is that the failure is
        silent and expensive -- so an absent library must REFUSE the run."""
        import importlib as _il

        from metascience_agent import preflight
        from metascience_agent.preflight import PreflightError, assert_ready

        real = _il.import_module

        def fake(name, *a, **kw):
            if name == mod:
                raise ImportError(f"No module named {name!r}")
            return real(name, *a, **kw)

        monkeypatch.setattr(preflight, "_CACHE", None)
        monkeypatch.delenv("METASCIENCE_SKIP_PREFLIGHT", raising=False)
        monkeypatch.setattr(preflight.importlib, "import_module", fake)
        with pytest.raises(PreflightError):
            assert_ready()
        preflight._CACHE = None

    def test_they_are_not_merely_advisory_rows(self):
        """They must not sit in the non-blocking set."""
        from metascience_agent.preflight import optional_checks

        optional = " ".join(n for n, _, _ in optional_checks())
        assert "python-docx" not in optional and "openpyxl" not in optional


class TestLegacyExcelRefusesByName:
    """`.xls` dispatched to openpyxl, which cannot read the legacy binary
    format at all -- so a real spreadsheet came back as a generic "could not
    read" instead of the named refusal every other unsupported format gets."""

    def test_xls_is_not_claimed_as_readable(self):
        assert ".xls" not in READABLE
        assert ".xlsx" in READABLE and ".xlsm" in READABLE

    def test_xls_has_a_named_reason(self):
        assert ".xls" in UNREADABLE
        assert "legacy binary" in UNREADABLE[".xls"]

    def test_the_reason_says_what_would_fix_it(self):
        """A refusal a reader can act on beats one they can only note."""
        assert ".xlsx" in UNREADABLE[".xls"]

    def test_a_real_xls_gets_the_named_error(self, tmp_path):
        f = tmp_path / "supp.xls"
        f.write_bytes(b"\xd0\xcf\x11\xe0")     # OLE2 magic
        r = extract_supplement(str(f))
        assert r["unreadable_format"] == ".xls"
        assert "legacy binary" in r["error"]
        assert r["n_tables"] == 0


class TestTheSupplementThatWasLost:
    """Regression anchor on the real file from the billed run."""

    PATH = ("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--hbm.26595/"
            "10.1002--hbm.26595_supplementary_info_1_HBM-45-e26595-s001.docx")

    def test_it_reads_now(self):
        from pathlib import Path
        if not Path(self.PATH).exists():
            pytest.skip("corpus supplement not present")
        r = extract_supplement(self.PATH)
        assert r.get("error") is None
        assert r["n_tables"] >= 3
        assert len(r["text"]) > 10_000
