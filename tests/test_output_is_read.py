"""Every key the pipeline writes must be READ by something, or say why not.

This test exists because the same defect has now been found eight times, and
twice in code written the same week to fix it:

  * `not_run` -- machine-generated per (cell, check), reader-grade reasons,
    ZERO consumers for its entire existence until f5a9e81.
  * `coverage_summary.checkable` -- computed on every run by 0d33a9f, the commit
    whose message argued that coverage must be measured against what was
    checkable, and rendered NOWHERE. Filed where nobody looks, hours after the
    identical defect was fixed one layer down.
  * `TOOL_INTEGRITY` -- 49 hand-authored evidence cards across two commits,
    tested for completeness, consumed by no production surface. FIXED
    2026-08-10: rendered as the report's "What each check does" glossary. The
    first thing that rendering revealed was that the `bayesian_table1_dispersion`
    card had gone STALE -- it still described a bootstrap that had been replaced
    and claimed two quarantines that had been released. An artefact nobody
    renders is an artefact nobody proof-reads, which is the second-order cost of
    this defect and the reason the entry below is now a hard contract.
  * anatomy `provenance_verdict` -- computed, written, and then STRIPPED by both
    loaders on read.

The shape is always the same: a producer, a test proving the producer works, and
no consumer. Producer-side tests pass, CI is green, and the feature does not
exist for any reader. `tests/test_findings_schema_contract.py` closed the write
side of this -- it proves what we write matches its schema. This closes the read
side.

A key may be exempt, but only by NAMING ITSELF here with a reason. Silence is
not an exemption.
"""
from __future__ import annotations

from tests.source_paths import canonical, IMAGE_SRC
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[1] / "src" / "forensic_metascience_ai_toolkit"

#: Modules a human-facing reader actually sees. A key referenced only inside the
#: module that writes it is not consumed -- that is the bug.
CONSUMERS = ("report_render.py", "bundle.py", "cli.py", "consequence.py",
             "severity_reconcile.py",
             # The image review surfaces. Added 2026-09-08: until then a key
             # written into `review_manifest.json` had no reader this test
             # could see, so the ratchet was blind to the whole image track.
             # `review_media.py` is deliberately NOT here -- it is the WRITER
             # of the manifest, and a writer satisfying its own needle is the
             # defect this test exists to catch.
             # Both live in the image package; their host alias files were
             # removed 2026-10-01, so they are read from IMAGE_SRC directly.
             "image_review.py", "image_forensics/triage_rank.py")

#: The CONSUMERS that live in the standalone image package, not the host.
IMAGE_CONSUMERS = ("image_review.py", "image_forensics/triage_rank.py")

#: key -> the substring a consumer must contain for it to count as rendered.
#:
#: The needle is the QUOTED key, i.e. how the key is actually accessed, not the
#: bare word. Measured reason: at 0d33a9f the bare word "checkable" already
#: appeared in bundle.py -- inside the prose of a verdict glossary entry, "the
#: main claim was checkable" -- so a bare-word needle passed on a coincidence
#: while the field was rendered nowhere. A test that can be satisfied by an
#: unrelated English sentence is not a contract.
MUST_BE_RENDERED = {
    "coverage_summary.checkable": '"checkable"',
    # The per-tool integrity card. `evidence_meaning` is the key that says what
    # KIND of claim a verdict is, so if it reaches a reader the rest of the card
    # did too.
    "TOOL_INTEGRITY.evidence_meaning": '"evidence_meaning"',
    "source_quote_verified": '"source_quote_verified"',
    "unchecked": '"unchecked"',
    # The unaligned control and its gate, written by `review_media` into the
    # manifest; read by the feed (`image_review`) and the ranking
    # (`triage_rank`). A block nobody reads is the defect above, again.
    "review_manifest.measurements.control": '"control"',
    "review_manifest.exhibit_gate": '"exhibit_gate"',
}

#: key -> why no reader-facing surface consumes it. Each entry is a DECISION,
#: and a wrong one is visible here rather than invisible in the codebase.
OPERATOR_ONLY = {
    "blot_scan.json": (
        "The blot pass's research sidecar (panels/blots/, 2026-10-01), read by "
        "image_forensics/blots/score.py through `blot-benchmark` -- an operator's "
        "calibration instrument with no thresholds and no verdicts. No review "
        "surface renders it until the strip matcher is calibrated and wired as a "
        "detector tier; score.py's NOT_SCORED register (pinned by "
        "test_blots_score.py) is where each of its pair keys is accounted for."
    ),
    "title_quality": (
        "Measures whether the model followed the finding-title spec. It is a "
        "grade on US, not a fact about the paper, and surfacing it to a paper's "
        "reader would be noise. STALE UNTIL 2026-08-13: this said the "
        "90-character cap and one-defect-per-title 'stay enforced'. Neither "
        "does. Both were measured flagging good headings as often as bad ones "
        "-- the cap condemned 52.6% of well-formed single-defect titles -- and "
        "were reduced to reported counts. The one rule still enforced is that a "
        "title must name the DEFECT rather than our method. The field stays "
        "operator-facing by choice; read from run_meta.json by an operator."
    ),
    "source_coverage.json": (
        "Written per run as an operator artifact; the bundle deliberately "
        "recounts inline rather than reading the file, so the numbers cannot "
        "drift apart silently."
    ),
    # Four stage-record keys the 2026-09-02 audit found written by
    # `_stage_meta` / `_provenance` and read by no renderer. Each is a fact
    # about the HARNESS, read by an operator from run_meta.json.
    "run_meta.stages.current_tool": (
        "The MCP tool the stage was inside when it was cut off. Useful to an "
        "operator diagnosing a stall (it names the hung tool), meaningless to "
        "a paper's reader, for whom the rendered `truncated_by_timeout` flag "
        "already says the stage did not finish looking."
    ),
    "run_meta.stages.mcp_discovery": (
        "Whether the CLI listed our MCP server's tools before the stage began. "
        "A liveness fact about the harness, recorded so a run with zero tool "
        "calls can be told apart from a run whose server never came up; an "
        "operator reads it, and sandbox_audit.json (rendered) carries the "
        "reader-facing consequence."
    ),
    "run_meta.stages.usage_guard": (
        "What the pre-spend usage probe saw (a pause, a weekly-limit stop). "
        "Operator bookkeeping about OUR account, not about the paper; the "
        "only reader-facing consequence is a stage that did not run, which "
        "the stage table already shows."
    ),
    "run_meta.backend_default_model": (
        "The model the backend would have chosen had none been requested. "
        "Provenance for an operator comparing runs across backends; the model "
        "that actually ran is `models_resolved`, which the viewer renders in "
        "'Which model actually ran'."
    ),
}


#: THE VIEWER IS THE COMPLETENESS CONTRACT, not a presentation layer.
#:
#: `viewer.html` is the one artefact a reader opens, and it is meant to be the
#: surface on which, in principle, EVERY piece of information the pipeline
#: produces is reachable. That makes "computed but unreachable in the viewer" a
#: defect of the viewer rather than a missed opportunity -- and it makes the
#: omissions visible as holes in a known shape instead of invisible.
#:
#: MUST_BE_RENDERED above is satisfied by any consumer, so `report_render.py`
#: alone can discharge it. That is the right rule for a key whose home is the
#: markdown report; it is the wrong rule for one whose home is the browser, and
#: measured on 2026-08-10 it was letting real holes through:
#: `coverage_summary.checkable` passed while the viewer read the whole
#: `coverage_summary` object nowhere, so a run that located 741 statistics and
#: checked 122 of them advertised the 741 on its coverage page.
#:
#: The needle is how `bundle.py` actually reaches the field. A bare word is not
#: enough -- see the note on MUST_BE_RENDERED, where "checkable" matched an
#: unrelated English sentence in a glossary entry.
VIEWER_MUST_RENDER = {
    "report.coverage_summary.stats_checked": "cs.stats_checked",
    "report.coverage_summary.checkable": "cs.checkable",
    "report.coverage_summary.completeness": "cs.completeness",
    "report.coverage_summary.computation_audit": "cs.computation_audit",
    # WHICH FILES NEVER LOADED. A supplement the model could not pull through a
    # tool result is absent from the review, and on every surface it looks
    # exactly like a supplement with nothing in it. `.files` is pinned
    # separately because the counts alone cannot name the file, and a reader
    # told that something was lost but not WHAT cannot act on it.
    "report.coverage_summary.undelivered": "cs.undelivered",
    "report.coverage_summary.undelivered.files": "ud.files",
    "report.coverage_summary.computation_audit.n_derived": "ca.n_derived",
    "report.coverage_summary.computation_audit.n_transcribed": "ca.n_transcribed",
    "report.coverage_summary.completeness.n_supplement_items": "n_supplement_items",
    "report.coverage_summary.completeness.n_checked_measurable": "n_checked_measurable",
    "run_meta.limitations": "(D.run_meta||{}).limitations",
    "report.headline.statement": "hl.statement",
    "report.headline.evidence": "hl.evidence",
    "report.headline.rests_on": "hl.rests_on",
    "anatomy.hypotheses": "a.hypotheses",
    "anatomy.provenance_quote": "provenance_quote",
    "TOOL_INTEGRITY.evidence_meaning": "evidence_meaning",
    "TOOL_INTEGRITY.severity_ceiling": "severity_ceiling",
    "supplements.retrieval_record": "_supplement_retrieval",
    "sandbox_audit.verdict": "sa.verdict",
    "run_meta.severity_reconciliation.divergences": "severity_reconciliation.divergences",
    # The sibling of `truncated_by_budget` (already pinned below it in the
    # viewer's stage table). A stage cut off by the wall clock or the stall
    # detector is the same coverage fact as one cut off by the spend cap, and
    # until 2026-09-02 it was written by `_stage_meta` and read by nothing --
    # the "new subtype only half the predicates know about" failure the
    # agent.py comment above `_CUT_OFF_SUBTYPES` warns against.
    "run_meta.stages.truncated_by_timeout": "v.truncated_by_timeout",
    # WHY there is no report.pdf. `report_render.last_pdf_error()` carried
    # the reason since defect #163 and had no caller; the writer now records
    # it in run_meta and the viewer prints it beside the provenance.
    "run_meta.pdf_error": "rm.pdf_error",
    # The v2 register. It was written at the top level of findings.v2.json and
    # read as `coverage_summary.statistics_register`, a key no parallel run
    # has -- written by one path, looked for on another, rendering empty on
    # every current run. The needle is the payload read, not the legacy one.
    "findings_v2.statistics_register": "D.statistics_register",
    # The census's v2 home. The eleven `cs.*` needles below still pin the
    # ACCESSORS, which are unchanged; this pins the FALLBACK that makes them
    # reach a parallel run at all. Both matter: the accessors say the page can
    # render it, this says the page can find it.
    "findings_v2.coverage_summary": "D.coverage_summary",
    "run_meta.stages.truncated_by_budget": "truncated_by_budget",
    "run_meta.stages.models_resolved": "models_resolved",
    # WHICH READER PRODUCED THE TEXT. It changes how an absence should be read,
    # so it is a reader-facing fact, not operator telemetry.
    "run_meta.text_provenance": "rm.text_provenance",
    # The anatomy table is where a reader judges whether any of the paper's
    # analyses matter, so a computed effect size or a design sensitivity that
    # reaches the payload and not the table is worth nothing. Added 2026-08-16.
    "anatomy.tests[].effect_size_estimated": "t.effect_size_estimated",
    "anatomy.tests[].mde_80": "t.mde_80",
    "run_meta.text_provenance.by_file": "tp.by_file",
}

#: key -> why the VIEWER does not surface it. Same discipline as OPERATOR_ONLY:
#: each entry is a decision, and a wrong one is visible here.
VIEWER_EXEMPT = {
    "check_table.declaration_template": (
        "Real in `dispatch.py` and covered by its own tests, and absent from "
        "every one of the 48 archived `check_table` result records -- it was "
        "committed on 2026-08-10, after the last archived run. Rendering it "
        "today would add a surface that displays nothing on any real bundle, "
        "which is this repo's dominant defect wearing the opposite disguise. "
        "Render it once a run at current HEAD produces one; the Coverage page's "
        "'blocked on a variable declaration' count is the hole it would fill."
    ),
    "coverage_summary.checkable.never_submitted": (
        "REWRITTEN 2026-08-11, because this test caught its old reason going "
        "stale. That reason said `n_checked` had never reached a payload; the "
        "Romano run of 2026-08-11 carries `n_checked: 21`, so the field is now "
        "produced and the premise was false. It is still not rendered, on new "
        "and worse grounds: that run reports `n_runnable: 0` beside "
        "`n_checked: 21`, so 21 cells were checked out of 0 that could be run, "
        "and `never_submitted` is the difference between those two -- clamped "
        "to 0. Rendering a counter derived from arithmetic that does not "
        "cohere would publish a number no reader could act on. Fix the census "
        "first; the incoherence is the finding, not the counter."
    ),
    "run_meta.sandbox.verdict": (
        "RE-DECIDED 2026-08-11, same answer, different reason. The old text "
        "opened with 'it exists in memory and in none of the 30 archived "
        "files'; the serialisation order has since been fixed and the Romano "
        "run of 2026-08-11 carries it. That clause is dead. The SUBSTANTIVE "
        "reason survives untouched and is why the exemption stands: the "
        "identical verdict string is written to `sandbox_audit.json` -- "
        "verified byte-for-byte on that run -- the viewer reads it from there, "
        "and it appears on the Overview as well as the Audit page. Rendering "
        "the run_meta copy would give one fact two sources and a reader no "
        "information."
    ),
    "run_meta.stages.*.token_and_transport_fields": (
        "`input_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`, "
        "`return_code`, `error_subtype` and `output_parse_path` are vendor "
        "transport telemetry. They say nothing about the paper and nothing about "
        "whether a check was entitled to its verdict, and the bundle is built to "
        "be forwarded to the authors being criticised. The three stage fields "
        "that DO bear on trust -- which models ran, whether the stage was "
        "truncated by its budget, and what it fell back to -- are rendered under "
        "'Which model actually ran'. The raw values stay in "
        "`analysis/run_meta.json`, which ships in the bundle and is linked from "
        "the Overview file tree."
    ),
    "run_meta.total_cost_usd": (
        "Deliberately scrubbed. The bundle is forwarded to the authors of the "
        "paper it criticises and our billing is not evidence about their work; "
        "`_is_operator_key` removes it, and the per-stage `cost_usd` and "
        "`model_usage` costs with it. Confirmed unreachable by rendering every "
        "section of a real bundle and searching for the values."
    ),
}


def _consumer_path(name: str) -> Path:
    path = IMAGE_SRC / name if name in IMAGE_CONSUMERS else SRC / name
    # A consumer that is not on disk must FAIL, not be skipped: the old
    # `if exists()` filter would have silently dropped the image-review
    # surfaces the day their host alias files were deleted.
    assert path.exists(), f"consumer {name!r} not found at {path}"
    return path


def _consumer_text() -> str:
    if IMAGE_SRC is None:
        # Two consumers are the image package's; without it the reader set is
        # incomplete, so "no reader" could not be told from "reader absent".
        pytest.skip("needs the image analysis package (two consumers live there)")
    return "\n".join(canonical(_consumer_path(name)).read_text(encoding="utf-8")
                     for name in CONSUMERS)


class TestWhatWeWriteIsRead:
    @pytest.mark.parametrize("key,needle", sorted(MUST_BE_RENDERED.items()))
    def test_a_written_key_reaches_a_reader(self, key, needle):
        assert needle in _consumer_text(), (
            f"{key!r} is written by the pipeline and no consumer in {CONSUMERS} "
            f"mentions {needle!r}. Either render it, or add it to OPERATOR_ONLY "
            f"with a reason. This is the eighth instance of this defect; the "
            f"seventh was this exact key."
        )

class TestTheViewerCanExpressTheWholeOutput:
    """The viewer is where "all the information, legibly" has to be true.

    A key that reaches `report.md` and not `viewer.html` is reachable only by
    the reader who opens a markdown file in a directory called `analysis/`,
    which is not the reader this bundle is built for.
    """

    @pytest.mark.parametrize("key,needle", sorted(VIEWER_MUST_RENDER.items()))
    def test_a_written_key_reaches_the_viewer(self, key, needle):
        viewer = (SRC / "bundle.py").read_text(encoding="utf-8")
        assert needle in viewer, (
            f"{key!r} is written by the pipeline and `bundle.py` never reaches "
            f"it ({needle!r} not found). The viewer is the completeness "
            f"contract: either render it, or add it to VIEWER_EXEMPT with a "
            f"reason saying why a reader does not need it."
        )


class TestExemptionsAreDecisionsNotOversights:
    @pytest.mark.parametrize("key", sorted(OPERATOR_ONLY))
    def test_every_exemption_states_a_reason(self, key):
        reason = OPERATOR_ONLY[key]
        assert len(reason) > 80, f"{key} needs a real reason, not a label"

    def test_an_exemption_is_not_also_claimed_to_be_rendered(self):
        assert not (set(OPERATOR_ONLY) & set(MUST_BE_RENDERED))

    @pytest.mark.parametrize("key", sorted(VIEWER_EXEMPT))
    def test_every_viewer_exemption_states_a_reason(self, key):
        reason = VIEWER_EXEMPT[key]
        assert len(reason) > 120, (
            f"{key} needs a reason a reviewer can disagree with, not a label. "
            f"An unexplained omission is where the next defect hides."
        )

    def test_a_viewer_exemption_is_not_also_claimed_to_be_rendered(self):
        assert not (set(VIEWER_EXEMPT) & set(VIEWER_MUST_RENDER))

    def test_an_exemption_that_becomes_available_must_be_re_decided(self):
        """Some data exemptions rest on the claim that the field is absent from
        every archived run because its producer landed after them. That claim
        expires. This pins it, so the day a run at current HEAD writes one of
        these, the exemption fails and has to be argued again rather than
        quietly outliving its reason.

        IT HAS FIRED ONCE, on 2026-08-11, on `never_submitted`. That is the
        evidence it works, and the reason the entry below is now a list of one
        rather than two."""
        import glob
        import json
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        # `never_submitted` LEFT THIS LIST on 2026-08-11, having done its job.
        # The Romano run produced it, this test failed as designed, and the
        # exemption was re-argued -- no longer on absence (the field is there
        # now) but on incoherence: that run reports `n_runnable: 0` beside
        # `n_checked: 21`, and a counter derived from those two is not a number
        # to publish. It is out of the tripwire because the tripwire tests one
        # specific justification, "absent from every archived run", and that is
        # no longer the justification being used. Leaving it here would make
        # the suite red forever over a decision already taken.
        absent = {
            "declaration_template": "check_table.declaration_template",
        }
        found: list[str] = []
        # Two depths: dated run dirs sit at `<corpus>/<paper>/forensic_review*`,
        # and the same papers live under `tests/fixtures/papers/<corpus>/<paper>/...`.
        _REVIEW_GLOBS = (
            "*/*/forensic_review*/{leaf}",
            "tests/fixtures/papers/*/*/forensic_review*/{leaf}",
        )
        for leaf in ("report.json", "toolcalls.stage*.json"):
            for pattern in _REVIEW_GLOBS:
                for path in glob.glob(str(root / pattern.format(leaf=leaf))):
                    if "funder_demo" in path:
                        continue
                    raw = Path(path).read_text(encoding="utf-8", errors="replace")
                    for token, key in absent.items():
                        if f'"{token}"' in raw and key not in found:
                            found.append(key)
        assert not found, (
            f"{found} now appear(s) in a real run, so the VIEWER_EXEMPT reason "
            f"'absent from every archived run' is no longer true. Render it, or "
            f"rewrite the exemption."
        )

        meta = []
        for pattern in _REVIEW_GLOBS:
            meta.extend(glob.glob(str(root / pattern.format(leaf="run_meta.json"))))
        meta = [p for p in meta if "funder_demo" not in p]
        assert meta, "no archived run_meta.json to check the sandbox exemption against"
        # DISCHARGED 2026-08-11. This fired when the serialisation order was
        # fixed and `sandbox` began reaching disk. The exemption was re-decided
        # and stands on its surviving reason -- the same verdict string is in
        # `sandbox_audit.json`, which IS rendered -- so the tripwire has done
        # its job and is retired rather than left to fail forever. What is
        # asserted now is the reason itself: that the rendered source carries
        # the same fact.
        for path in meta:
            m = json.loads(Path(path).read_text())
            if isinstance(m.get("sandbox"), dict) and m["sandbox"].get("verdict"):
                audit = Path(path).with_name("sandbox_audit.json")
                if not audit.exists():
                    continue
                assert json.loads(audit.read_text()).get("verdict") == \
                    m["sandbox"]["verdict"], (
                    f"{path}: run_meta.sandbox.verdict is exempt only because "
                    "sandbox_audit.json carries the SAME string and is rendered. "
                    "They have diverged, so the exemption's reason is void.")
        # (A trailing `assert True, "run_meta.sandbox now exists on disk;
        # re-decide the exemption."` stood here until 2026-09-02. It could
        # not fail; the assertions above are the test.)
        _ = (
            "run_meta.sandbox now exists on disk; re-decide the exemption."
        )


class TestDoclingIsARequirementNotAnEnhancement:
    """Greg, 2026-08-13: "I want docling to become a dependency for this
    project -- it dramatically improves the content that all downstream
    processes have to work with."

    MEASURED, and the text gap is worse than the table gap that prompted the
    original swap. Against publisher XML on the seven papers here carrying both
    formats, table recall goes 60.4% -> 95.8% and precision 88.3% -> 92.0%. On
    body text, pdfplumber renders operators as glyph references and our own
    debris filter strips them, so `t(28) = -3.33` reaches a checker as
    `t(28)3.33` -- comparator and minus sign gone. statcheck finds 0 statistics
    in pdfplumber's text of Ophir 2009 and 26 in docling's.

    This pins the decision so docling cannot drift back to optional. The
    failure it guards against is specific: an `ImportError` swallowed into a
    fallback, and the pipeline quietly returning to the extractor that loses
    minus signs -- which nothing downstream could detect, because a sign flip
    reads as an ordinary number.
    """

    @staticmethod
    def _required() -> list[str]:
        """The QUOTED entries of `[project] dependencies`, comments excluded.

        Not a substring search of the file: this module's own docstring records
        that a bare-word needle once passed on an unrelated English sentence,
        and pyproject.toml is now mostly prose explaining WHY each dependency
        is there. `tomllib` is 3.11+ and this venv is 3.10, so the block is
        read directly.
        """
        root = Path(__file__).resolve().parents[1]
        text = (root / "pyproject.toml").read_text(encoding="utf-8")
        block = text.split("dependencies = [", 1)[1].split("]", 1)[0]
        out = []
        for line in block.splitlines():
            line = line.strip()
            if line.startswith("#") or not line.startswith('"'):
                continue
            out.append(line.strip('",').split(">=")[0].split("==")[0])
        return out

    def test_it_is_a_hard_dependency(self):
        assert "docling" in self._required(), (
            "docling was declared a requirement on 2026-08-13; if it moved to "
            "optional, the text path silently reverts to the extractor that "
            "drops minus signs")

    def test_pdfplumber_is_kept_deliberately(self):
        """Not a leftover. Page counts, table detection, the scanned-paper
        guard and every page-range read still run through it, and it serves the
        text whenever the docling cache is cold."""
        assert "pdfplumber" in self._required()

    def test_the_text_path_states_which_extractor_ran(self):
        """A result that does not say where its text came from cannot be
        audited, and the two extractors differ on the characters that matter."""
        src = canonical(SRC / "extraction" / "pdf.py").read_text(encoding="utf-8")
        assert '"text_extractor"' in src
        assert '"text_extractor_note"' in src


class TestEveryRunMetaCarriesTheTextProvenance:
    """FOUND BY ASKING THE ARTEFACT A QUESTION, 2026-08-13.

    Greg, of the paid Kross review: "was the content run through docling?" The
    field that exists to answer exactly that -- `run_meta.text_provenance` --
    was ABSENT from the run. `_text_provenance` was wired into
    `_findings_only_result`, the DEGRADED path taken when the editorial stage
    cannot be afforded, and into nothing else. Every ordinary two-stage run,
    which is every run anybody reads, recorded no provenance, while the branch
    note and the PR both stated that it did.

    `test_output_is_read` already pinned the VIEWER end of this
    (`rm.text_provenance` -> `tp.by_file`), and passed throughout, because a
    renderer for a field nobody writes renders nothing and complains about
    nothing.

    So this checks the PRODUCER, and checks it structurally rather than at one
    call site: every `run_meta` a result path builds must carry the key, so a
    third path added later cannot quietly omit it.
    """

    @staticmethod
    def _run_meta_literals() -> list[str]:
        import pathlib
        src = (lambda r: (r / "src/forensic_metascience_ai_toolkit/agent.py").read_text(encoding="utf-8")
                   + (r / "src/forensic_metascience_ai_toolkit/parallel.py").read_text(encoding="utf-8")
                   )(pathlib.Path(__file__).resolve().parents[1])
        out, i = [], 0
        while (i := src.find("run_meta = {", i)) != -1:
            depth, j = 0, src.index("{", i)
            k = j
            while k < len(src):
                if src[k] == "{":
                    depth += 1
                elif src[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            out.append(src[j:k + 1])
            i = k
        return out

    def test_the_producer_answers_for_a_real_paper(self):
        import pathlib

        import pytest

        from forensic_metascience_ai_toolkit.agent import _text_provenance
        d = (pathlib.Path(__file__).resolve().parents[1]
             / "tests/fixtures/papers/high_value_pdfs_to_run_on/10.1371--journal.pone.0069841")
        if not d.is_dir():
            pytest.skip("paper not in this checkout")
        tp = _text_provenance(d)
        assert tp.get("by_file"), tp
        assert tp.get("n_docling", 0) >= 1, (
            "this paper has a docling cache; a provenance record that cannot "
            "see it is worse than none")
