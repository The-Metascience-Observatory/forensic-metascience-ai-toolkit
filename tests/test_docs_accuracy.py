"""The documented numbers must be the measured numbers.

WHY THIS FILE EXISTS
--------------------
An audit on 2026-08-07 found the top-level docs stale by 2-5x, and every one of
the stale claims was the kind that makes someone act wrongly:

  - README: "36 of the 38 tools are pure Python". The registry held 47. A reader
    counting tools to decide whether a technique was implemented got the wrong
    answer.
  - README: `pip install -e .` with no mention of the `statcheck` extra or of
    `metascience preflight`. A missing `statcheck` does not fail loudly -- it
    returns `success: false` and an empty result, which reads as "this paper has
    no NHST statistics". That exact mistake was made in this repository.
  - README: DENIED_TOOLS shown without `ToolSearch`, which is the one entry that
    stops a model loading tools outside the declared surface at runtime. A
    reader reproducing the sandbox from the README would have built a weaker one.
  - README: `metascience eval --skip-analysis` described as free. It is not, and
    it silently ran the paid pipeline on any fixture with no report.md.
  - README: output dir given as `forensic_review_<model>_<date>/` with 5 files.
    It is `forensic_review/` with 9, and the two most audit-relevant --
    `sandbox_audit.json` and `toolcalls.stage{1,2}.json` -- were not listed at
    all.
  - README: extraction described PDF-first. The code is XML-first, and the
    difference is 7 vs 86 usable cells on a real clinical Table 1.
  - CLAUDE.md: named `/home/dan/anaconda3/bin/python3.13` as the only
    interpreter with the dependencies. That path does not exist on this machine.

None of these are typos. Each one was true once, and nothing checked it after.
So the numbers a reader would act on are asserted here against the code.

The README is no longer pinned here (2026-10-18): it is being rewritten by
hand, and the checks against it were removed rather than kept in step with
every edit. What remains checks AGENTS.md, pyproject.toml, the prompts and
the docs/ files against the code.

Note what is NOT pinned: exact test counts and dollar figures. Those move every
day and a test that fails on them teaches people to edit tests. Structural
claims are pinned instead.
"""

import pathlib
import re

import pytest

from forensic_metascience_ai_toolkit import registry as R

ROOT = pathlib.Path(__file__).parent.parent
# The project guidance lives in AGENTS.md; CLAUDE.md only imports it.
GUIDE_MD = (ROOT / "AGENTS.md").read_text(encoding="utf-8")


def _numbers_near(text: str, phrase: str, window: int = 160) -> set[int]:
    """Every integer within `window` chars after `phrase`."""
    i = text.find(phrase)
    assert i != -1, f"phrase not found in doc: {phrase!r}"
    return {int(n) for n in re.findall(r"\b(\d+)\b", text[i : i + window])}


class TestToolCounts:
    def test_claude_md_states_the_registry_size(self):
        assert f"{len(R.SPECS)} registered tools" in GUIDE_MD


class TestInstall:
    def test_statcheck_is_a_base_dependency(self):
        """A missing statcheck fails SILENTLY, so the plain install must carry it.

        It was an extra until 1.85.4. Nearly every run uses the tools agent, so
        it is base now.
        """
        tomllib = pytest.importorskip("tomllib")
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        assert any(d.replace(" ", "").startswith("statcheck")
                   for d in project["dependencies"]), (
            "statcheck left [project].dependencies; `pip install -e .` now "
            "produces a run whose statcheck tool silently finds nothing")

    def test_pymupdf_is_a_base_dependency(self):
        """The toolkit reads PDF pages with PyMuPDF outside image analysis
        (quote page numbers, viewer pages, OCR of scanned PDFs), and most of
        those call sites return empty when it is missing. It sat only in the
        `images` extra until 1.93.1."""
        tomllib = pytest.importorskip("tomllib")
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        assert any(d.lower().replace(" ", "").startswith("pymupdf")
                   for d in project["dependencies"])

    def test_fetchpdf_is_a_base_dependency(self):
        """Without fetchpdf the landing-page check and the supplement audit
        degrade silently. It sat in the `html` extra until 1.94.1. The floor is
        0.1.2, the first release that does not require playwright."""
        tomllib = pytest.importorskip("tomllib")
        project = tomllib.loads((ROOT / "pyproject.toml").read_text())["project"]
        assert "fetchpdf>=0.1.2" in [d.replace(" ", "") for d in project["dependencies"]]

    def test_no_image_extras(self):
        """The image package declares its own dependencies; an extra here
        would be a second pin that can drift from it."""
        tomllib = pytest.importorskip("tomllib")
        extras = tomllib.loads(
            (ROOT / "pyproject.toml").read_text())["project"]["optional-dependencies"]
        assert not {"images", "text-localization"} & set(extras)

    def test_html_extra_is_not_a_local_path(self):
        """The fetchpdf pin used to be a file:// path that existed on one machine."""
        tomllib = pytest.importorskip("tomllib")
        extras = tomllib.loads(
            (ROOT / "pyproject.toml").read_text())["project"]["optional-dependencies"]
        for name, reqs in extras.items():
            for req in reqs:
                assert "file://" not in req, f"extra {name!r} pins a local path: {req}"

    def test_preflight_is_a_real_command(self):
        from forensic_metascience_ai_toolkit.cli import app

        names = {c.name or c.callback.__name__ for c in app.registered_commands}
        assert "preflight" in names


class TestExtractionOrder:
    """The code is XML-first: on a real clinical Table 1 the PDF yields 7
    usable cells per table and the XML yields 86."""

    def test_the_sweep_prompt_agrees(self):
        from forensic_metascience_ai_toolkit.core.prompts import tool_expert_body
        sweep = tool_expert_body()
        assert sweep.index("extract_xml") < sweep.index("extract_pdf")


class TestOneGuidanceFile:
    """AGENTS.md is the only copy; CLAUDE.md imports it.

    The two were kept as identical 900-line copies "synchronized" by hand, and
    every edit had to land twice -- concurrent sessions each edited one or both.
    """

    def test_claude_md_is_only_the_import(self):
        text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        assert text.strip() == "@AGENTS.md", (
            "CLAUDE.md must stay the one line `@AGENTS.md`; put guidance in AGENTS.md"
        )


class TestInterpreter:
    """AGENTS.md must not assert one machine's interpreter as THE path.

    It named a venv that does not exist on Dan's machine, and later a conda
    path that does not exist on Greg's -- each edit fixed one box by breaking
    the other. The doc now states the rule (read the console script's
    shebang) with the venv as an example; literal absolute interpreter
    paths are banned."""

    def test_claude_md_names_the_project_venv(self):
        assert "~/.venvs/metascience-agent/bin/python" in GUIDE_MD

    def test_claude_md_does_not_name_the_dead_anaconda_path(self):
        assert "/home/dan/anaconda3" not in GUIDE_MD

    def test_claude_md_states_the_interpreter_rule(self):
        assert "PY=$(metascience python)" in GUIDE_MD

    def test_no_doc_derives_the_interpreter_from_the_shebang(self):
        """`$(head -1 $(which metascience) | tr -d '#!')` is `/bin/sh` when the
        console script is a shell shim. An agent copied it, fed Python to it,
        and `/bin/sh` ran `import json` as ImageMagick's screen grabber: a
        48 MB screenshot named `json` in the repo root (2026-10-18). A line
        that names `/bin/sh` is describing the failure and may quote the idiom;
        no doc may present it as a command to run."""
        idiom = re.compile(r"\$\(\s*head -1 \$\(which metascience\)\s*\|\s*tr")
        offenders = []
        for doc in ROOT.rglob("*.md"):
            parts = doc.relative_to(ROOT).parts
            # hidden dirs hold other checkouts (.claude/worktrees/*)
            if any(p.startswith(".") for p in parts) or set(parts) & {
                    "node_modules", "fixtures", "archive"}:
                continue
            for n, line in enumerate(doc.read_text(encoding="utf-8",
                                                   errors="replace").splitlines(), 1):
                if idiom.search(line) and "`/bin/sh`" not in line:
                    offenders.append(f"{doc.relative_to(ROOT)}:{n}: {line.strip()}")
        assert not offenders, "use PY=$(metascience python):\n" + "\n".join(offenders)


class TestAddATool:
    """The checklist would not work as written.

    Steps 3 and 4 said to hand-edit `ALL_TOOLS` in tools_mcp.py and
    `STAGE1_TOOLS`/`STAGE2_TOOLS` in agent.py. Both are DERIVED from the registry
    -- following the checklist produces a duplicate wrapper and a stage list that
    disagrees with the registry, which is the exact defect class the registry
    exists to make unrepresentable.
    """

    def test_the_checklist_points_at_the_registry(self):
        i = GUIDE_MD.find("Adding a new tool")
        section = GUIDE_MD[i : i + 2500]
        assert "ToolSpec" in section and "registry.py" in section
        assert "derived" in section.lower()

    def test_the_checklist_does_not_tell_you_to_hand_edit_the_derived_lists(self):
        i = GUIDE_MD.find("Adding a new tool")
        section = GUIDE_MD[i : i + 2500]
        for phrase in ("append to `ALL_TOOLS`", "Add to `STAGE1_TOOLS`"):
            assert phrase not in section, (
                f"checklist still instructs {phrase!r}, which is derived from the registry"
            )

    def test_the_derivation_actually_holds(self):
        """Pin the claim the checklist now makes, so it cannot become false."""
        from forensic_metascience_ai_toolkit.agent import STAGE1_TOOLS, STAGE2_TOOLS

        for stage, listed in ((R.STAGE1, STAGE1_TOOLS), (R.STAGE2, STAGE2_TOOLS)):
            derived = {f"mcp__forensic_metascience__{n}" for n in R.stage_tools(stage)}
            assert derived == set(listed) - {"Read"}


class TestGrimContextDependencyDoc:
    """Documentation nothing points at is the same defect as code nothing calls.

    Written after three false `impossible` verdicts against non-retracted papers
    in one day, all from reporting conventions rather than arithmetic error.
    """

    @staticmethod
    def _doc():
        from pathlib import Path
        return (Path(__file__).resolve().parents[1] / "docs"
                / "GRIM_CONTEXT_DEPENDENCY.md").read_text(encoding="utf-8")

    def test_every_quoted_line_number_resolves_in_the_in_tree_book(self):
        """The locators must be checkable, or the doc is hearsay about a source
        that sits in the same repository."""
        import re
        from pathlib import Path
        book = (Path(__file__).resolve().parents[1] / "docs" / "reference"
                / "intro_to_forensic_metascience.md").read_text(
                    encoding="utf-8").splitlines()
        cited = {int(n) for m in re.finditer(
            r"intro_to_forensic_metascience\.md:(\d+)(?:-(\d+))?", self._doc())
            for n in m.groups() if n}
        assert cited, "the doc cites the book by line and must keep doing so"
        for n in sorted(cited):
            assert 0 < n <= len(book), f"line {n} is past the end of the book"

    @staticmethod
    def _flat(text):
        """Collapse whitespace and fold smart punctuation.

        A quote wrapped across markdown lines is still verbatim, and the book
        uses typographic apostrophes where the doc types ASCII. Comparing raw
        would fail on formatting rather than on fidelity; this compares words.
        """
        import re as _re
        for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'),
                     ("\u201d", '"'), ("\u2014", "--")):
            text = text.replace(a, b)
        return _re.sub(r"[\s>*]+", " ", text)

    def test_the_load_bearing_quotes_are_verbatim(self):
        from pathlib import Path
        book = self._flat((Path(__file__).resolve().parents[1] / "docs" / "reference"
                           / "intro_to_forensic_metascience.md").read_text(encoding="utf-8"))
        doc = self._flat(self._doc())
        for fragment in (
            "maybe someone left the question blank, and the denominator isn't actually 30",
            "GRIM doesn't work at all as any eventual mean is possible",
            "analysts get annoyed by papers that do not clearly specify their methods",
            "R does not round values in the traditional manner",
        ):
            assert fragment in book, f"not in the book as quoted: {fragment}"
            assert fragment in doc, f"in the book but not quoted in the doc: {fragment}"

    def test_it_separates_his_claims_from_ours(self):
        """Heathers never catalogues innocent GRIM failures, so most of the list
        is derived. Presenting it as his would misattribute it."""
        doc = self._doc()
        assert "**[H]**" in doc and "**[D]**" in doc
        assert "composite" in doc.lower()

    def test_it_keeps_the_non_reasons(self):
        """Over-excusing is its own failure mode. Reverse-scoring, winsorising,
        change scores and sum composites all preserve integer granularity."""
        doc = self._doc()
        for term in ("Reverse-scored", "Winsorised", "Change or difference",
                     "Composite SUM"):
            assert term in doc, term
