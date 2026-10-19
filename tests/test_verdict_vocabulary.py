"""The two documents in one bundle must print the same verdict word.

THE DEFECT. `verdicts.py` renamed the three run-level verdicts on 2026-08-11 --
`trustworthy | questionable | untrustworthy` became `reconciles | unresolved |
does_not_reconcile` -- and the module argues at length that `untrustworthy`
"asserts exactly what the disclaimer spends four paragraphs saying we cannot
assert". The rename reached the viewer and the tests. It reached nothing else:
`grep` showed no module under `src/` importing `verdicts`, `report.schema.json`
still enumerated the retired words, and `report_render` printed
`report["verdict"]` raw.

So `<review>_bundle/analysis/report.md` and `<review>_bundle/viewer.html`
printed DIFFERENT verdict words for the same run, out of the same
`report.json` -- and the one that printed the retired, accusatory word was
`report.md`, which `bundle._FILE_BLURBS` describes as "The review itself -- what
you would read" and which is therefore the file people forward.

A rename that reaches one of two renderers is not a rename. These tests are the
property, stated once: whatever a report records, every surface says the same
thing about it, and neither surface says the retired word.
"""
import json
import re
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import report_render, verdicts
from forensic_metascience_ai_toolkit.bundle import collect

from tests.test_bundle import flat, review, section_html  # noqa: F401

RETIRED = ("trustworthy", "questionable", "untrustworthy")

#: The renderers under test, each as (name, callable taking a verdict -> text).
#: `report.md` is markdown and the viewer is HTML, so the comparison is on the
#: WORDS each contains, never on layout.


class TestBothSurfacesAgree:
    """The end-to-end property, and the one the defect actually broke."""

    @pytest.mark.parametrize("recorded", ["unresolved", "questionable"])
    def test_neither_surface_shows_the_retired_word_as_the_verdict(
            self, review, tmp_path, recorded):  # noqa: F811
        rev = review  # the fixture yields the forensic_review dir itself
        obj = json.loads((rev / "report.json").read_text())
        obj["verdict"] = recorded
        (rev / "report.json").write_text(json.dumps(obj))

        overview = flat(section_html(collect(review), "overview", tmp_path))
        # The retired word may appear in a "recorded as ..." note; it may not
        # appear as the rendered verdict. Anchor on the label a reader reads.
        m = re.search(r"verdict on this run.{0,200}", overview, re.S)
        assert m, "the Overview no longer labels the verdict"
        shown = m.group(0)
        for word in RETIRED:
            assert not re.search(rf">\s*{word}\s*<", shown), (
                f"the viewer renders {word!r} as the verdict itself")


class TestTheDefinitionHasExactlyOneHome:
    def test_the_viewer_reads_the_vocabulary_from_the_payload(self):
        """Not from a JS literal. Both copies existed, and the JS comment
        claimed the map was shipped in the payload under a key that did not
        exist -- which is how the third renderer ended up with no copy at all.
        """
        src = Path("src/forensic_metascience_ai_toolkit/bundle.py").read_text()
        assert "const VERDICT_DEF=((D.facts||{}).verdict_vocab||{}).defs" in src
        assert "const VERDICT_LEGACY=((D.facts||{}).verdict_vocab||{}).legacy" in src
        assert "reconciles:'" not in src, (
            "a JS literal definition of the vocabulary has come back")

    def test_no_module_under_src_spells_the_retired_words_as_a_map(self):
        """`cli.py` held its own `{trustworthy: green, ...}` colour map, which
        is the same defect wearing different clothes: a surface that knows the
        words without knowing where they came from."""
        for path in Path("src/forensic_metascience_ai_toolkit").rglob("*.py"):
            if path.name == "verdicts.py":
                continue
            text = path.read_text(encoding="utf-8")
            for word in RETIRED:
                assert f'"{word}":' not in text and f"'{word}':" not in text, (
                    f"{path} maps the retired verdict {word!r}; read it "
                    f"through verdicts.canonical instead")
