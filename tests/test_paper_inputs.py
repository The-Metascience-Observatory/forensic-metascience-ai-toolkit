"""Tests for paper-input resolution, including supplementary-PDF handling."""

from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit.agent import (
    _build_sweep_prompt,
    _is_supplementary,
    _resolve_paper_inputs,
    _resolve_paper_sources,
)

_XML = (
    "<article><body><sec><title>Results</title><p>Text.</p>"
    "<table-wrap><label>Table 1</label><table><tbody>"
    "<tr><td>Age</td><td>1</td></tr></tbody></table></table-wrap>"
    "</sec></body></article>"
)


def _touch(path: Path, content: str = "x") -> Path:
    path.write_text(content)
    return path


class TestSupplementaryDetection:
    def test_supplementary_name_patterns(self):
        for name in (
            "paper_SUPPLEMENTARY_INFO",
            "paper_supplementary",
            "10.1_SI",
            "study-si",
            "foo_supp_material",
        ):
            assert _is_supplementary(Path(f"{name}.pdf")), name

    def test_main_paper_not_supplementary(self):
        for name in ("10.1234--jexample.5678901", "paper", "main_article"):
            assert not _is_supplementary(Path(f"{name}.pdf")), name


class TestResolveInputs:
    def test_directory_separates_main_and_si_pdfs(self, tmp_path):
        d = tmp_path / "10.1234--jexample.5678901"
        d.mkdir()
        _touch(d / "body.md", "# body")
        main = _touch(d / "10.1234--jexample.5678901.pdf")
        si = _touch(d / "10.1234--jexample.5678901_SUPPLEMENTARY_INFO.pdf")
        _touch(d / "10.1234--jexample.5678901_SUPPLEMENTARY_INFO.md", "# si md")

        body_md, pdf, si_pdfs = _resolve_paper_inputs(str(d))
        assert body_md == d / "body.md"
        assert pdf == main
        assert si_pdfs == [si]

    def test_main_pdf_prefers_dirname_match(self, tmp_path):
        d = tmp_path / "study42"
        d.mkdir()
        _touch(d / "aaa_other.pdf")
        canonical = _touch(d / "study42.pdf")
        body_md, pdf, si_pdfs = _resolve_paper_inputs(str(d))
        assert pdf == canonical

    def test_single_si_pdf_path(self, tmp_path):
        si = _touch(tmp_path / "paper_SUPPLEMENTARY_INFO.pdf")
        body_md, pdf, si_pdfs = _resolve_paper_inputs(str(si))
        assert pdf is None
        assert si_pdfs == [si]

    def test_plain_pdf_path(self, tmp_path):
        main = _touch(tmp_path / "paper.pdf")
        body_md, pdf, si_pdfs = _resolve_paper_inputs(str(main))
        assert pdf == main
        assert si_pdfs == []

    def test_sweep_prompt_includes_si_pass(self, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        _touch(d / "body.md", "# body")
        _touch(d / "p.pdf")
        _touch(d / "p_SUPPLEMENTARY_INFO.pdf")
        body_md, pdf, si_pdfs = _resolve_paper_inputs(str(d))
        prompt = _build_sweep_prompt(body_md, pdf, "p", si_pdfs)
        assert "Supplementary information" in prompt
        assert "SUPPLEMENTARY_INFO.pdf" in prompt
        # and it must point at the PDF, not the SI markdown
        assert "_SUPPLEMENTARY_INFO.md" not in prompt

    def test_sweep_prompt_no_si_when_absent(self, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        _touch(d / "body.md", "# body")
        _touch(d / "p.pdf")
        body_md, pdf, si_pdfs = _resolve_paper_inputs(str(d))
        prompt = _build_sweep_prompt(body_md, pdf, "p", si_pdfs)
        assert "Supplementary information" not in prompt


class TestXmlResolution:
    """The re-fetched corpus ships `<stem>.xml` and no `body.md` at all."""

    def _paper(self, tmp_path, *, xml=True, pdf=True, name="p"):
        d = tmp_path / name
        d.mkdir()
        if xml:
            _touch(d / f"{name}.xml", _XML)
        if pdf:
            _touch(d / f"{name}.pdf")
        return d

    def test_harvest_from_pdf_body_resolves_as_body_md(self, tmp_path):
        d = tmp_path / "10.1002--bdm.1794"
        d.mkdir()
        harvest = _touch(d / "10.1002--bdm.1794_from_pdf_body.md", "# body")
        _touch(d / "10.1002--bdm.1794.pdf")
        sources = _resolve_paper_sources(str(d))
        assert sources.body_md == harvest

    def test_xml_is_discovered_alongside_the_pdf(self, tmp_path):
        d = self._paper(tmp_path)
        sources = _resolve_paper_sources(str(d))
        assert sources.xml == d / "p.xml"
        assert sources.main_pdf == d / "p.pdf"
        assert sources.body_md is None

    def test_xml_only_paper_resolves_instead_of_crashing(self, tmp_path):
        """
        Regression for the two corpus papers that held XML but no PDF and
        raised FileNotFoundError, so they were never reviewed at all.
        """
        d = self._paper(tmp_path, pdf=False)
        sources = _resolve_paper_sources(str(d))
        assert sources.xml is not None
        assert sources.main_pdf is None
        assert any((sources.body_md, sources.main_pdf, sources.xml, sources.si_pdfs))

    def test_legacy_three_tuple_still_works_and_agrees(self, tmp_path):
        d = self._paper(tmp_path)
        legacy = _resolve_paper_inputs(str(d))
        assert len(legacy) == 3
        assert legacy == _resolve_paper_sources(str(d))[:3]

    def test_bare_xml_path_resolves(self, tmp_path):
        x = _touch(tmp_path / "solo.xml", _XML)
        assert _resolve_paper_sources(str(x)).xml == x

    def test_supplements_are_split_by_readability(self, tmp_path):
        d = self._paper(tmp_path)
        _touch(d / "p_supplementary_info_1.docx")
        _touch(d / "p_supplementary_info_2.jpg")
        _touch(d / "p_supplementary_info_3.doc")
        sources = _resolve_paper_sources(str(d))
        assert [f.suffix for f in sources.si_readable] == [".docx"]
        assert sorted(f.suffix for f in sources.si_unreadable) == [".doc", ".jpg"]


class TestXmlSweepPrompt:
    def test_xml_comes_first_and_the_pdf_is_only_a_cross_check(self, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        _touch(d / "p.xml", _XML)
        _touch(d / "p.pdf")
        s = _resolve_paper_sources(str(d))
        prompt = _build_sweep_prompt(
            s.body_md, s.main_pdf, "p", s.si_pdfs, xml=s.xml)
        assert prompt.index("extract_xml") < prompt.index("extract_pdf")
        assert "cross-check" in prompt.lower()
        assert "Do NOT re-sweep" in prompt

    def test_xml_without_pdf_states_the_figure_limitation(self, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        _touch(d / "p.xml", _XML)
        s = _resolve_paper_sources(str(d))
        prompt = _build_sweep_prompt(
            s.body_md, s.main_pdf, "p", s.si_pdfs, xml=s.xml)
        assert "no PDF" in prompt
        assert "figures" in prompt

    def test_unreadable_supplements_are_named_not_omitted(self, tmp_path):
        d = tmp_path / "p"
        d.mkdir()
        _touch(d / "p.xml", _XML)
        _touch(d / "p_supplementary_info_1.docx")
        _touch(d / "p_supplementary_info_2.jpg")
        s = _resolve_paper_sources(str(d))
        prompt = _build_sweep_prompt(
            s.body_md, s.main_pdf, "p", s.si_pdfs, xml=s.xml,
            si_readable=s.si_readable, si_unreadable=s.si_unreadable)
        assert "extract_supplement" in prompt
        assert ".docx" in prompt or "info_1.docx" in prompt
        assert "info_2.jpg" in prompt
        assert "unreadable" in prompt

    def test_prompt_is_unchanged_when_there_is_no_xml(self, tmp_path):
        """The markdown+PDF path must not shift for the eval fixtures."""
        d = tmp_path / "p"
        d.mkdir()
        _touch(d / "body.md", "# body")
        _touch(d / "p.pdf")
        s = _resolve_paper_sources(str(d))
        assert (
            _build_sweep_prompt(s.body_md, s.main_pdf, "p", s.si_pdfs, xml=None)
            == _build_sweep_prompt(s.body_md, s.main_pdf, "p", s.si_pdfs)
        )


class TestSuppliedSupplementsAreSwept:
    """A `--supplement` path must reach the prompt, not just the gate.

    The flag was consumed by `cli._supplement_gate` and stopped there:
    `analyze_paper` had no parameter for it, and the file list the sweep works
    from is built independently by `_resolve_paper_sources` globbing the paper
    directory. So `--supplement /elsewhere/etable.xlsx` bought a proceed past
    the refuse-by-default gate for a file nothing ever opened.

    The model cannot recover from that itself. `Glob` and `Bash` are not in its
    tool surface, by decision (`BUILTIN_TOOLS`/`DENIED_TOOLS`), so a path that
    is not interpolated into the prompt does not exist as far as the review is
    concerned.
    """

    def _paper(self, tmp_path, *, xml=False):
        d = tmp_path / "p"
        d.mkdir()
        _touch(d / "p.pdf")
        if xml:
            _touch(d / "p.xml", _XML)
        else:
            _touch(d / "body.md", "# body")
        return d

    def _outside(self, tmp_path, name):
        out = tmp_path / "elsewhere"
        out.mkdir(exist_ok=True)
        return _touch(out / name)

    def test_a_supplied_spreadsheet_lands_in_the_readable_bucket(self, tmp_path):
        d = self._paper(tmp_path)
        si = self._outside(tmp_path, "etable.xlsx")
        s = _resolve_paper_sources(str(d), [si])
        assert s.si_readable == [si.resolve()]

    def test_a_supplied_pdf_lands_in_the_si_pdf_bucket(self, tmp_path):
        d = self._paper(tmp_path)
        si = self._outside(tmp_path, "appendix.pdf")
        s = _resolve_paper_sources(str(d), [si])
        assert s.si_pdfs == [si.resolve()]
        assert s.main_pdf == d / "p.pdf"

    def test_a_format_no_reader_opens_is_named_unreadable_not_dropped(self, tmp_path):
        """"Present but unreadable" and "not provided" are different facts."""
        d = self._paper(tmp_path)
        si = self._outside(tmp_path, "data.zip")
        s = _resolve_paper_sources(str(d), [si])
        assert s.si_unreadable == [si.resolve()]

    def test_a_supplied_xls_is_unreadable_because_the_reader_refuses_it(self, tmp_path):
        """`agent._SI_READABLE` still lists `.xls`; `supplements_read` removed it
        on purpose, openpyxl being unable to read the legacy binary format. The
        prompt must not promise a read the reader refuses."""
        d = self._paper(tmp_path)
        si = self._outside(tmp_path, "legacy.xls")
        assert _resolve_paper_sources(str(d), [si]).si_unreadable == [si.resolve()]

    def test_a_supplied_tsv_is_readable_though_the_discovery_table_omits_it(self, tmp_path):
        d = self._paper(tmp_path)
        si = self._outside(tmp_path, "raw.tsv")
        assert _resolve_paper_sources(str(d), [si]).si_readable == [si.resolve()]

    def test_a_file_already_in_the_directory_is_not_listed_twice(self, tmp_path):
        d = self._paper(tmp_path)
        inside = _touch(d / "supp_data.xlsx")
        s = _resolve_paper_sources(str(d), [inside])
        assert s.si_readable == [inside.resolve()]

    @pytest.mark.parametrize("xml", [True, False], ids=["xml", "body_md+pdf"])
    def test_the_supplied_path_reaches_the_sweep_prompt(self, tmp_path, xml):
        """Parametrized over the branch, because `_si_other_text` was called
        from only two of the five branches in `_build_sweep_prompt`. On the
        body.md+PDF layout -- the one an operator most often reaches for
        `--supplement` on -- a supplied spreadsheet was threaded in and then
        dropped without a word."""
        d = self._paper(tmp_path, xml=xml)
        si = self._outside(tmp_path, "etable.xlsx")
        s = _resolve_paper_sources(str(d), [si])
        prompt = _build_sweep_prompt(
            s.body_md, s.main_pdf, "p", s.si_pdfs, xml=s.xml, html=s.html,
            si_readable=s.si_readable, si_unreadable=s.si_unreadable)
        assert str(si.resolve()) in prompt
        assert "extract_supplement" in prompt
        assert "detect_raw_duplication" in prompt

    @pytest.mark.parametrize("xml", [True, False], ids=["xml", "body_md+pdf"])
    def test_an_unreadable_supplement_is_named_on_every_branch(self, tmp_path, xml):
        d = self._paper(tmp_path, xml=xml)
        si = self._outside(tmp_path, "data.zip")
        s = _resolve_paper_sources(str(d), [si])
        prompt = _build_sweep_prompt(
            s.body_md, s.main_pdf, "p", s.si_pdfs, xml=s.xml, html=s.html,
            si_readable=s.si_readable, si_unreadable=s.si_unreadable)
        assert str(si.resolve()) in prompt
        assert "unreadable" in prompt

    def test_a_discovered_spreadsheet_reaches_the_body_md_branch_too(self, tmp_path):
        """Not only supplied files: the same omission hid every directory-local
        data supplement on the non-XML branches."""
        d = self._paper(tmp_path)
        _touch(d / "supp_data.xlsx")
        s = _resolve_paper_sources(str(d))
        prompt = _build_sweep_prompt(
            s.body_md, s.main_pdf, "p", s.si_pdfs,
            si_readable=s.si_readable, si_unreadable=s.si_unreadable)
        assert "supp_data.xlsx" in prompt
