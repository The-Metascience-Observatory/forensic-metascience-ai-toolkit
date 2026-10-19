"""The repair log, and the one thing it is allowed to change.

We already edit papers to read them -- glyph repairs, entity substitution, `¼`
to `=`, whitespace collapsing -- and until now none of it was recorded. These
tests pin the ledger and, more importantly, pin the LIMITS on the single
behaviour change it introduces: a declared repair may become the paper's text,
and only when it can prove which text it was made against.
"""

from __future__ import annotations

import shutil
import warnings
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import repairs as R
from forensic_metascience_ai_toolkit.extraction.jats import paper_text_with_source

CORPUS = Path(__file__).resolve().parents[1] / "tests/fixtures/papers/high_value_pdfs_to_run_on"
PAPER = CORPUS / "10.1002--ajcp.70049"

pytestmark = pytest.mark.skipif(
    not PAPER.is_dir(), reason="working corpus not present")


@pytest.fixture()
def paper(tmp_path: Path) -> Path:
    """A copy of the fixture paper WITH its `markdown/body.md` materialised.

    The tracked corpus ships no `markdown/` (it is a derived file the
    pipeline writes in `ensure_paper_extracted`, before any agent starts),
    and every test below edits that file. Until 2026-09-02 this fixture only
    copied the directory; the module skipped on every checkout where the
    paper sat at the old top-level path, and the first checkout where it
    resolved failed all nine with FileNotFoundError -- our missing derived
    file, reported as the resolver's defect.
    """
    from forensic_metascience_ai_toolkit.extraction.markdown_out import materialise
    d = tmp_path / "paper"
    shutil.copytree(PAPER, d)
    rec = materialise(d)
    assert rec.get("action") in ("written", "current", "rewritten"), rec
    return d


def _declare(d: Path, against: str, *, repairs=1) -> None:
    log = R.RepairLog(paper_id="p", original_sha256=R.sha256(against),
                      declares_body_md=True)
    for i in range(repairs):
        log.add(R.Repair(rule="hand", reason="restores a destroyed character",
                         before="n ¼ 68", after="n = 68", offset=i,
                         narrows_only=True))
    R.save(d, log)


def _edit_body(d: Path, marker: str = "SENTINEL_42") -> None:
    from forensic_metascience_ai_toolkit.extraction.markdown_out import body_path
    p = body_path(d)
    p.write_text(p.read_text(encoding="utf-8", errors="replace")
                 + f"\n\n{marker}\n", encoding="utf-8")


class TestItIsOptIn:
    """No log means the resolver behaves exactly as it did."""

    def test_no_log_changes_nothing(self, paper: Path):
        text, source = paper_text_with_source(paper)
        assert source == "xml_publisher"
        assert text

    def test_an_undeclared_edit_is_not_read(self, paper: Path):
        base, _ = paper_text_with_source(paper)
        _edit_body(paper)
        text, source = paper_text_with_source(paper)
        assert "SENTINEL_42" not in text
        assert source == "xml_publisher"

    def test_an_undeclared_edit_is_reported_rather_than_hidden(self, paper: Path):
        """Reporting is the fail-closed direction: an unrecorded hand-edit that
        silently became the paper is the outcome the log exists to prevent."""
        _edit_body(paper)
        text, _ = paper_text_with_source(paper)
        assert R.divergence(paper, text)["state"] == "undeclared"

    def test_an_untouched_paper_reports_match(self, paper: Path):
        text, _ = paper_text_with_source(paper)
        assert R.divergence(paper, text)["state"] == "match"


class TestADeclarationMustProveWhatItRepaired:
    """The staleness guard -- the reason this is not the idea `_derive_paper_text`
    rejects. A cached body invalidates on the SOURCE changing and not on the
    EXTRACTOR changing; a declaration pins the derived text by hash, so an
    extractor that moves invalidates it."""

    def test_a_valid_declaration_is_read(self, paper: Path):
        base, _ = paper_text_with_source(paper)
        _edit_body(paper)
        _declare(paper, against=base)
        text, source = paper_text_with_source(paper)
        assert "SENTINEL_42" in text
        assert source == "body_md_repaired"

    def test_a_declaration_against_other_text_is_refused(self, paper: Path):
        _edit_body(paper)
        _declare(paper, against="what an older extractor produced")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            text, source = paper_text_with_source(paper)
        assert "SENTINEL_42" not in text
        assert source == "xml_publisher"
        assert any("Refusing the declaration" in str(w.message) for w in caught)

    def test_a_declaration_with_no_repairs_is_refused(self, paper: Path):
        """A claim that the body was edited and that nothing was edited is not
        a state to act on."""
        base, _ = paper_text_with_source(paper)
        _edit_body(paper)
        _declare(paper, against=base, repairs=0)
        text, source = paper_text_with_source(paper)
        assert "SENTINEL_42" not in text
        assert source == "xml_publisher"

    def test_an_undeclared_log_does_not_authorise(self, paper: Path):
        base, _ = paper_text_with_source(paper)
        _edit_body(paper)
        log = R.RepairLog(paper_id="p", original_sha256=R.sha256(base),
                          declares_body_md=False)
        log.add(R.Repair(rule="hand", reason="r", before="a", after="b"))
        R.save(paper, log)
        text, source = paper_text_with_source(paper)
        assert "SENTINEL_42" not in text
        assert source == "xml_publisher"


class TestItFailsClosed:
    def test_a_malformed_log_is_not_read_as_no_repairs(self, tmp_path: Path):
        from forensic_metascience_ai_toolkit.extraction.markdown_out import markdown_dir
        d = tmp_path / "p"
        markdown_dir(d).mkdir(parents=True)
        R.path(d).write_text("{not json", encoding="utf-8")
        assert R.load(d) is None
        assert R.authorises_body_md(d) is None

    def test_a_future_schema_is_refused(self, tmp_path: Path):
        import json
        from forensic_metascience_ai_toolkit.extraction.markdown_out import markdown_dir
        d = tmp_path / "p"
        markdown_dir(d).mkdir(parents=True)
        R.path(d).write_text(json.dumps({"schema_version": 99, "repairs": []}),
                             encoding="utf-8")
        assert R.load(d) is None

    def test_narrows_only_defaults_to_widening(self):
        """Invariant 2 applied to text: a repair that cannot justify itself as
        narrowing is recorded as the kind an adjudicator should weigh against
        a finding depending on it."""
        assert R.Repair(rule="r", reason="x", before="a", after="b").narrows_only is False


class TestThePerFindingJoin:
    """What the policy is FOR: an adjudicator receiving, per finding, the
    repairs its evidence depends on."""

    def test_it_names_the_repair_a_quote_depends_on(self):
        log = R.RepairLog().add(
            R.Repair(rule="glyphs", reason="r", before="n ¼ 68", after="n = 68"))
        assert [r.rule for r in log.depended_on_by("the sample was n = 68")] == ["glyphs"]

    def test_it_stays_silent_on_an_unaffected_quote(self):
        log = R.RepairLog().add(
            R.Repair(rule="glyphs", reason="r", before="n ¼ 68", after="n = 68"))
        assert log.depended_on_by("participants were recruited locally") == []

    def test_an_empty_quote_names_nothing(self):
        log = R.RepairLog().add(R.Repair(rule="g", reason="r", before="a", after="b"))
        assert log.depended_on_by("") == []


class TestTheWriterAndTheReaderAgree:
    """`markdown_out.materialise` WRITES body.md by calling the resolver, and
    the resolver may now READ body.md. That is a fixed point, not a loop -- but
    only if it does not drift, so it is pinned rather than argued."""

    def test_materialise_and_resolve_reach_a_fixed_point(self, paper: Path):
        import json
        from forensic_metascience_ai_toolkit.extraction import markdown_out as MO

        base, _ = paper_text_with_source(paper)
        MO.body_path(paper).write_text(base + "\n\nSENTINEL_42\n", encoding="utf-8")
        _declare(paper, against=base)

        lengths, channels = set(), set()
        for _ in range(3):
            MO.materialise(paper)
            text, source = paper_text_with_source(paper)
            assert "SENTINEL_42" in text
            assert source == "body_md_repaired"
            lengths.add(len(MO.body_path(paper).read_text(encoding="utf-8")))
            channels.add(json.loads(MO.source_path(paper).read_text())
                         .get("source_channel"))

        assert len(lengths) == 1, f"body.md drifted across passes: {lengths}"
        assert channels == {"body_md_repaired"}
        assert R.authorises_body_md(paper) is not None
        assert R.divergence(paper, paper_text_with_source(paper)[0])["state"] == "match"


class TestAbsentAndBrokenAreDifferentFacts:
    """Nobody wrote the file that is not there; somebody DID write the one that
    will not parse, and meant it to be read. Collapsing both to silence is the
    house failure mode -- an absence rendered as knowledge."""

    def _dir(self, tmp_path: Path) -> Path:
        from forensic_metascience_ai_toolkit.extraction.markdown_out import markdown_dir
        d = tmp_path / "p"
        markdown_dir(d).mkdir(parents=True)
        return d

    def test_an_absent_log_is_silent(self, tmp_path: Path):
        d = self._dir(tmp_path)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert R.load(d) is None
        assert not [w for w in caught if "repair log" in str(w.message)]

    @pytest.mark.parametrize("body, needle", [
        ("{not json", "could not be read"),
        ('["a list"]', "not an object"),
        ('{"schema_version": 99, "repairs": []}', "schema_version"),
        ('{"schema_version": 1, "repairs": [{"nope": 1}]}', "does not match"),
    ])
    def test_a_broken_log_says_so(self, tmp_path: Path, body: str, needle: str):
        d = self._dir(tmp_path)
        R.path(d).write_text(body, encoding="utf-8")
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert R.load(d) is None
        msgs = [str(w.message) for w in caught]
        assert any(needle in m for m in msgs), msgs
        assert any("will NOT be applied" in m for m in msgs), msgs


class TestMaterialiseReportsWhatItDidNotDo:
    """`materialise` reports `current` from the RECORDED digest and never reads
    body.md, so a hand-edited body passed as current while the pipeline read
    something else. Being ignored looked exactly like being applied."""

    def test_it_reports_an_undeclared_edit_it_is_ignoring(self, paper: Path):
        from forensic_metascience_ai_toolkit.extraction import markdown_out as MO

        MO.materialise(paper)
        body = MO.body_path(paper)
        body.write_text(body.read_text(encoding="utf-8") + "\n\nEDIT\n",
                        encoding="utf-8")

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = MO.materialise(paper)

        assert result["body_md"]["state"] == "undeclared"
        assert any("IGNORED, not applied" in str(w.message) for w in caught)
        # And the edit is not destroyed either -- it sits there, unread.
        assert "EDIT" in body.read_text(encoding="utf-8")

    def test_an_untouched_paper_reports_match_and_stays_quiet(self, paper: Path):
        from forensic_metascience_ai_toolkit.extraction import markdown_out as MO

        MO.materialise(paper)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = MO.materialise(paper)

        assert result["body_md"]["state"] == "match"
        assert not [w for w in caught if "IGNORED" in str(w.message)]

    def test_a_declared_repair_is_not_warned_about(self, paper: Path):
        from forensic_metascience_ai_toolkit.extraction import markdown_out as MO

        base, _ = paper_text_with_source(paper)
        MO.body_path(paper).write_text(base + "\n\nEDIT\n", encoding="utf-8")
        _declare(paper, against=base)

        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = MO.materialise(paper)

        assert result["body_md"]["state"] == "match"
        assert not [w for w in caught if "IGNORED" in str(w.message)]
