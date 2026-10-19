"""The viewer must speak the pipeline's vocabulary, not a copy of last month's.

Greg, 2026-08-11, on finding `trustworthy` still on the viewer's Start-here page
hours after the verdict vocabulary changed: "make sure the viewer uses
consistent language and framework as the pipeline proper."

THE STRUCTURAL PROBLEM. `bundle.py` embeds its JavaScript inside raw Python
strings, so every controlled vocabulary the page renders is a SECOND COPY of one
that Python already owns. Two copies drift, and this repo has already paid for
it twice:

  * `REFUSAL_KINDS` existed in Python and in the JS, and the JS `na` tier was
    six alternations behind -- the same reason could be bucketed one way by a
    test and another way by the page that test was supposed to cover. Fixed by
    SHIPPING the table in the payload instead of restating it.
  * the verdict words were renamed in `verdicts.py`, with tests, and the
    viewer's Start-here page and codebook went on saying `trustworthy` -- a
    reader was told the paper had been graded on a scale the pipeline no longer
    uses.

So this file does not check spelling. It checks that no vocabulary word appears
in the rendered page unless Python defines it, and that every word Python does
define is reachable. The fix when it fails is usually to SHIP the vocabulary
from Python rather than to edit the string.
"""
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BUNDLE = REPO / "src/forensic_metascience_ai_toolkit/bundle.py"


@pytest.fixture(scope="module")
def viewer_src() -> str:
    return BUNDLE.read_text(encoding="utf-8")


def _code_only(src: str) -> str:
    """Drop Python comment lines. The file DOCUMENTS the old words at length --
    every rename carries a note saying what it replaced -- and matching that
    prose would make this test fire on its own history."""
    return "\n".join(l.split("#", 1)[0] if l.lstrip().startswith("#") else l
                     for l in src.splitlines())


class TestTheVerdictVocabulary:
    """34 archived reports use the old words, so the viewer must still MAP
    them. What it must not do is present them as the current scale."""

    def test_the_current_words_are_the_ones_python_defines(self, viewer_src):
        from forensic_metascience_ai_toolkit.verdicts import VERDICTS
        for v in VERDICTS:
            assert v in viewer_src, f"viewer never mentions `{v}`"

    def test_the_legacy_words_survive_only_as_a_mapping(self, viewer_src):
        """`questionable` may appear as a key that maps forward. It may not
        appear as a definition the reader is offered."""
        # A WINDOW, NOT A LINE. Rename notes are prose and prose wraps: the
        # first version of this checked the matched LINE only and fired on its
        # own explanation, which had the old words on one line and the new ones
        # on the next. Third time today a source-text assertion has tripped on
        # the comment that documents the rule it enforces.
        from forensic_metascience_ai_toolkit.verdicts import LEGACY
        code = _code_only(viewer_src)
        for old, new in LEGACY.items():
            for m in re.finditer(rf"\b{old}\b", code):
                window = code[max(0, m.start() - 400): m.start() + 400]
                excused = ("VERDICT_LEGACY" in window or new in window
                           or "Renamed from" in window or "recorded `" in window
                           or "replaced on" in window)
                snippet = " ".join(
                    code[max(0, m.start() - 60): m.start() + 60].split())
                assert excused, (
                    f"`{old}` appears in the viewer with no nearby mapping or "
                    f"rename note:\n    ...{snippet}...")

    def test_the_codebook_defines_every_current_verdict(self, viewer_src):
        from forensic_metascience_ai_toolkit.verdicts import VERDICTS
        for v in VERDICTS:
            assert f"row('{v}'" in viewer_src, (
                f"the codebook has no entry for `{v}` -- the verdict is the "
                "most prominent coded word in the document")

    def test_an_unrecognised_verdict_is_not_coerced(self, viewer_src):
        """A verdict the page cannot place is a corruption of the one field a
        reader acts on. Guessing at it would hide that."""
        assert "if(!c) return esc(v??'')" in viewer_src


class TestTheWarrantVocabulary:
    def test_every_warrant_python_defines_reaches_the_page(self, viewer_src):
        from forensic_metascience_ai_toolkit.warrants import WARRANTS
        for w in WARRANTS:
            assert w in viewer_src, f"viewer never mentions warrant `{w}`"

    def test_the_codebook_explains_the_field(self, viewer_src):
        assert "row('warrant'" in viewer_src
        from forensic_metascience_ai_toolkit.warrants import SUPPLIED_CEILING
        i = viewer_src.index("row('warrant'")
        assert SUPPLIED_CEILING in viewer_src[i:i + 1400], (
            "the codebook must say what `field_norm` caps at, since the cap is "
            "the whole reason the field exists")


class TestVocabulariesAreShippedNotRestated:
    """The durable fix. A vocabulary the page RECEIVES cannot drift; one it
    RESTATES already has, twice."""

    def test_the_refusal_table_is_shipped(self, viewer_src):
        assert '"refusal_kinds"' in viewer_src
        assert "D.facts||{}).refusal_kinds" in viewer_src.replace("(", "")

    def test_the_things_still_restated_are_named_here(self, viewer_src):
        """Not a failure -- a register. `VERDICT_DEF`, `VERDICT_LEGACY` and
        `SEV_DEF` are still hand-written in the JS, and the tests above are what
        keeps them honest until they are shipped from Python too. If you ship
        one, delete its line here."""
        still_restated = ["VERDICT_DEF", "VERDICT_LEGACY", "SEV_DEF"]
        for name in still_restated:
            assert f"const {name}" in viewer_src, (
                f"{name} is no longer restated in the JS -- if it is shipped "
                "from Python now, remove it from this list")


class TestTheSourcePaneDefaultsToRaw:
    """Greg, 2026-08-11, REVERSING his own earlier call: "make the default view
    for the 'what the check reads' pane the raw text, not the rendered text. I
    want it this way until we fix the process of having clicks of the pdf and
    the rendered text instantly map to each other like the pdf and raw text
    do."

    Only the raw <pre> carries `data-src-offset`, so only the raw pane
    click-syncs with the PDF. A reader clicking a passage in the rendered view
    gets nothing, and a pane that silently does not respond is worse than a wall
    of pipe characters that does.

    THE CONDITION FOR REVERTING IS IN THE SOURCE, not just here: when the
    rendered view carries offsets and click-to-jump works from it, flip both
    the selector and `chosenView` back and delete this class."""

    def test_the_selector_opens_on_raw(self, viewer_src):
        assert '<option value="raw" selected>raw</option>' in viewer_src
        assert '<option value="rendered" selected>' not in viewer_src

    def test_the_initial_view_state_is_raw(self, viewer_src):
        assert "let chosenView = 'raw';" in viewer_src

    def test_rendered_is_still_reachable(self, viewer_src):
        """The reversal is about the DEFAULT. Removing the rendered view would
        lose the only answer to 'did the tables survive extraction'."""
        assert '<option value="rendered">rendered</option>' in viewer_src
        assert "setView('rendered'" in viewer_src or "mode!=='rendered'" in viewer_src

    def test_the_reason_and_its_expiry_are_recorded_in_the_source(self, viewer_src):
        """A default flipped with no note is a default somebody flips back."""
        i = viewer_src.index("RAW IS THE DEFAULT")
        window = viewer_src[i:i + 1200]
        assert "REVERT THIS" in window
        assert "data-src-offset" in window


class TestBothVerdictRenderersUseTheSameMapper:
    """CAUGHT BY A RED TEST, 2026-08-11, and worth keeping because the shape
    recurs. Two functions render the verdict. `verdictWord` was taught the
    legacy map; `verdictHtml` indexed `VERDICT_DEF` directly with the RAW value,
    so an archived report saying `questionable` fell straight through to
    `esc(v)` -- the Overview printed a bare word with no definition, no codebook
    link and no scale. That is precisely the defect the codebook work existed to
    fix, reintroduced by fixing its neighbour and leaving the sibling behind."""

    def test_neither_renderer_indexes_the_definition_table_with_a_raw_value(
            self, viewer_src):
        for fn in ("verdictWord", "verdictHtml"):
            i = viewer_src.index(f"function {fn}(v)")
            body = viewer_src[i:i + 900]
            assert "verdictCanonical(v)" in body, (
                f"{fn} must map through verdictCanonical, or a legacy verdict "
                "renders undefined")
            assert "VERDICT_DEF[String(v)" not in body, (
                f"{fn} indexes VERDICT_DEF with the raw value again")

    def test_a_legacy_verdict_still_gets_its_definition_and_codebook_link(self):
        """The end-to-end property, not the implementation: what a reader of an
        archived bundle actually receives."""
        import json
        import re
        import shutil
        import subprocess
        import tempfile
        node = shutil.which("node") or shutil.which("nodejs")
        if not node:
            pytest.skip("node not available")
        from forensic_metascience_ai_toolkit import verdicts as _verdicts

        src = BUNDLE.read_text(encoding="utf-8")
        m = re.search(r"const VERDICT_DEF=.*?\nfunction verdictHtml\(v\)\{.*?\n\}",
                      src, re.S)
        assert m, "the verdict renderers moved"
        # `D` IS THE POINT NOW, not a stub to get the snippet to run. The
        # definitions and the legacy map used to be JS literals; they are read
        # from the payload, so this program feeds the JS exactly what
        # `bundle.collect` ships and the assertions below prove the two halves
        # agree. Building it from `verdicts.MEANING`/`LEGACY` is what makes the
        # test fail if either side is edited alone.
        payload = {"facts": {"verdict_vocab": {
            "defs": dict(_verdicts.MEANING), "legacy": dict(_verdicts.LEGACY)}}}
        prog = ("const esc=s=>String(s==null?'':s);\n"
                f"const D={json.dumps(payload)};\n" + m.group(0) +
                "\nconsole.log(JSON.stringify(verdictHtml('questionable')));")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(prog)
            path = fh.name
        out = subprocess.run([node, path], capture_output=True, text=True)
        assert out.returncode == 0, out.stderr[:300]
        html = json.loads(out.stdout.strip())
        assert 'data-cb="cb-verdict"' in html
        assert "unresolved" in html
        assert "could not be settled" in html
