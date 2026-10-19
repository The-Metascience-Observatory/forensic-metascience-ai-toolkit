"""What the prompts and the findings schema promise must be true of the code.

Every case here is a path an adversarial audit (2026-08-07) found could emit
`impossible` -- the strongest claim the system can make, and the one that is not
recoverable once published -- for a reason that has nothing to do with the paper.
`indeterminate` means "a precondition could not be verified, so I decline to
judge", and it is the correct destination for all of them.
"""

import pathlib

import pytest

from forensic_metascience_ai_toolkit.core import prompts


def _md(name: str) -> str:
    """A prompt's text, or "" if it has been retired. `tool_expert.md` is read
    as ASSEMBLED: its per-tool guidance lives in the tool folders' TOOL.md."""
    if name == "tool_expert.md":
        from forensic_metascience_ai_toolkit.core.prompts import tool_expert_body
        return tool_expert_body()
    path = prompts.prompt_path(name)   # the agents' prompts live in modules/
    return path.read_text(encoding="utf-8") if path.is_file() else ""


#: The human tool reference, sent to no model; read by path, NOT through `_md`,
#: whose "" for a missing file would turn every check below vacuous the day the
#: file moved (it did, to `docs/`, on 2026-10-18).
REFERENCE_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs" / "tool_reference.md"
REFERENCE = REFERENCE_PATH.read_text(encoding="utf-8")

#: The prompts the LIVE pipeline sends. Cross-document rules are parametrised
#: over these plus `tool_reference.md`.
#:
#: WHY IT IS BUILT THIS WAY. `TestBatchToolsAreJustifiedByCorrectness` used to
#: parametrise over a literal dict of the two LEGACY prompts plus
#: `tool_reference.md`, so deleting the legacy pipeline would have shrunk the
#: parametrisation from three cases to one -- and shrinking a parametrisation
#: PASSES. The rules would have stopped being enforced with nothing going red.
#:
#: Worse, measured 2026-09-04: `tool_expert.md` -- a prompt the live pipeline
#: actually sends -- carries the `55 of 124` anecdote those rules police and was
#: in NO case at all. It happens to be correctly dated, so it was passing by
#: luck rather than by enforcement. Anchoring on the live set fixes a gap that
#: exists today, not only one the deletion would open.
LIVE_DOCS = {name: _md(name) for name in
             ("tool_expert.md", "science_error.md", "adjudication.md",
              "rulebook.md")}
TOOL_EXPERT = _md("tool_expert.md")
ADJUDICATION = _md("adjudication.md")



def _technique_enum() -> list[str]:
    """The LIVE technique enum.

    Read the V1 schema until 2026-09-04 -- a file the legacy deletion removes,
    and not the enum the live pipeline enforces anyway. The v2 enum is injected
    at load time from `registry.SPECS`, so it cannot drift from the registry.
    """
    schema = prompts.findings_schema_v2()
    return schema["properties"]["findings"]["items"]["properties"]["technique"]["enum"]


class TestTechniqueEnum:
    """The enum is a HARD gate: findings JSON is enforced with `--json-schema`.

    A technique missing from it is not a documentation gap. The model runs the
    tool, gets a real result, and then cannot name it -- so the finding is either
    dropped or relabelled as something it is not. All four below are stage-1
    tools the sweep procedure explicitly instructs the model to run:
    `check_estimate_ci` is called "the highest-yield check on clinical and
    epidemiological papers" there, and it could not be reported.
    """

    @pytest.mark.parametrize(
        "technique",
        [
            "absence_of_evidence",
            "check_effect_plausibility",
            "check_estimate_ci",
            "verify_power_analysis",
        ],
    )
    def test_the_analyst_can_name_the_technique_it_was_told_to_run(self, technique):
        """RE-POINTED to the live prompt. All four are in the v2 enum
        (verified), which is auto-injected from `registry.SPECS` -- so on v2
        the original defect is structurally impossible rather than merely
        absent."""
        assert f"`{technique}`" in TOOL_EXPERT, (
            f"the tool expert no longer instructs {technique}")
        assert technique in _technique_enum(), (
            f"{technique} is instructed by the live analyst but is not a legal "
            "`technique` value, so a real result from it cannot be reported")

    def test_every_forensic_tool_a_live_prompt_names_is_reportable(self):
        """THE STRONGER FORM, and the reason the four-technique fixture above
        is no longer the interesting test. The enum is a HARD gate enforced by
        `--json-schema`: a technique the prompt instructs but the enum omits
        means the model runs the tool, gets a real result, and then cannot name
        it -- so the finding is dropped or relabelled as something it is not.

        Extraction tools are excluded BY DESIGN (CLAUDE.md: they "return
        extraction data rather than a `severity`, and are absent from the
        `technique` enum"), so their absence is a decision, not a gap.
        """
        import re

        from forensic_metascience_ai_toolkit import registry

        enum = set(prompts.findings_schema_v2()["properties"]["findings"]
                   ["items"]["properties"]["technique"]["enum"])
        registered = {spec.name for spec in registry.SPECS}
        # ...and the harness-filed tools, whose results the HARNESS reports
        # (`registry.HARNESS_FILED_TOOLS`): nothing is lost by the model
        # being unable to name them.
        exempt = {n for n in registered
                  if n.startswith(("extract_", "parse_", "get_", "list_"))
                  or n == "run_python_script"} | set(registry.HARNESS_FILED_TOOLS)
        for name, doc in LIVE_DOCS.items():
            named = set(re.findall(r"`([a-z0-9_]{4,})`", doc)) & registered
            missing = sorted(named - enum - exempt)
            assert not missing, (
                f"{name} instructs {missing}, which the v2 technique enum "
                f"cannot express -- the model would run it and be unable to "
                f"report the result")


class TestFigureCoverageIsStructuralOnV2:
    """RETIRED AS A PROMPT RULE, 2026-09-04, because v2 supersedes it.

    `stage2_editorial.md` ordered the model to state whether figures were read.
    That was a prompt REQUEST -- the model could forget it, and once did the
    opposite: it wrote "figures were not read" on a run where six extracted
    figure PNGs sat in the run directory, killing the renderer branch that
    would have said otherwise.

    On v2 the same fact is COMPUTED, not requested. `findings.v2.json` carries
    `channels.image_forensics` as a tri-state, and `report_v2` renders any
    channel that is not `ran` as "did not produce a retained result: <state> --
    <detail>". Measured on the archive: every parallel run records
    `image_forensics: did_not_run ("image track disabled")`.

    So the capability is not lost with the legacy prompt -- it is stronger, and
    it is pinned by `test_report_v2.py::test_disclaimer_and_channel_absences_render`.
    This class exists so that the retirement is a recorded decision rather than
    a test that quietly disappeared.
    """

    def test_the_structural_guarantee_is_pinned_elsewhere(self):
        source = (pathlib.Path(__file__).parent / "test_report_v2.py").read_text(
            encoding="utf-8")
        assert "channel_absences_render" in source, (
            "the test that replaced this one is gone; the figure-coverage "
            "guarantee is now unguarded on both paths")

    def test_the_renderer_still_reports_a_channel_that_did_not_run(self):
        from forensic_metascience_ai_toolkit.report_v2 import render_report_v2

        md = render_report_v2(
            {"schema_version": "2.0", "paper_id": "p", "findings": [],
             "channels": {"image_forensics": {"state": "did_not_run",
                                              "detail": "image track disabled"}}},
            {}, [])
        assert "image_forensics" in md and "did not produce a retained" in md


class TestMeasuredValuesMustDeclareProvenance:
    """The sweep promised a refusal that nothing performed.

    It said the granularity tools "refuse such values, by design" for numbers
    read off a figure. They refuse only when told: `provenance` defaults to
    `printed_table`, and nothing in a tool can tell a figure-read value from a
    typed one. Leaving the argument out is not a neutral omission -- it asserts
    the number was printed, which is the false premise the accusation is built
    on. A figure-read mean at n=30 is called impossible about 70% of the time.
    """

    # RE-POINTED 2026-09-04 from `stage1_sweep.md` to `tool_expert.md`, the
    # prompt the live pipeline actually sends. Verified before the swap: every
    # phrase these tests assert is present in BOTH files, so this changes which
    # document is policed and not what is required of it.
    def test_the_prompt_says_the_refusal_is_not_automatic(self):
        i = TOOL_EXPERT.find("Do NOT read values off the marks")
        assert i != -1
        section = TOOL_EXPERT[i : i + 1600]
        assert "refusal is not automatic" in section
        assert "printed_table" in section, "must name the DEFAULT it is overriding"
        assert "measured_raster" in section and "measured_vector" in section

    def test_the_prompt_no_longer_claims_the_tools_refuse_unprompted(self):
        assert "Those tools refuse such values, by design" not in TOOL_EXPERT

    def test_it_covers_tools_that_have_no_provenance_argument(self):
        """`check_estimate_ci`, `check_sd_or_se` and the `recalc_*` family take no
        `provenance`, so for them there is no refusal to reach at all. The prompt
        has to say what to do instead rather than implying a guard exists.
        """
        i = TOOL_EXPERT.find("Do NOT read values off the marks")
        section = TOOL_EXPERT[i : i + 1600]
        assert "no `provenance` argument" in section
        assert "unchecked" in section

    def test_the_provenance_vocabulary_matches_the_registry(self):
        from forensic_metascience_ai_toolkit.registry import MEASURED_PROVENANCE

        i = TOOL_EXPERT.find("Do NOT read values off the marks")
        section = TOOL_EXPERT[i : i + 1600]
        named = {v for v in MEASURED_PROVENANCE if v in section}
        assert named, (
            "the live analyst names no value the registry treats as measured; "
            f"the registry's set is {sorted(MEASURED_PROVENANCE)}"
        )


class TestStage2ClaimsNoFenceItDoesNotHave:
    """"You have a reduced tool subset" was a written fence with no enforcement.

    Under `--permission-mode bypassPermissions` (which agent.py passes),
    `--allowedTools` is an AUTO-APPROVE list, not an allow-list -- the comment at
    agent.py:419-433 says so, and it is the reason DENIED_TOOLS exists at all.
    `mcp_server.py` serves `ALL_TOOLS` with no stage filter whatsoever, so the
    stage-2 subset is advertised and not enforced. A written fence with no
    enforcement is the worst of both: the model is told it cannot do something it
    can, so a violation looks like a model failure rather than a design gap.

    The claim is deleted rather than enforced -- enforcement belongs in
    mcp_server.py, which this change does not own.
    """

    def test_the_prompt_does_not_assert_a_reduced_subset(self):
        assert "You have a reduced tool subset" not in ADJUDICATION

    def test_the_rule_is_still_stated_as_a_rule(self):
        """Deleting the false mechanism must not delete the intent.

        RE-POINTED to `adjudication.md`, which carries the intent in its own
        words: section 6 is "Tool spot-checks", and it says a check on values
        neither analyst touched is "a third sweep this stage does not do".
        """
        low = " ".join(ADJUDICATION.split()).lower()   # hard-wrapped, see above
        assert "spot-check" in low
        assert ("third sweep this stage does not do" in low
                or "not a second sweep" in low)

    def test_the_server_serves_offered_tools_with_no_stage_partition(self):
        """The fact the deleted claim depended on.

        The server lists every spec with a stage, and `_call_tool` takes no
        stage, so it cannot tell which stage is calling. CLI-only tools are
        the exception -- they must not be listed at all (a sweep LLM that
        can see them will call them instead of running the numeric sweep).
        Re-adding the "reduced tool subset" sentence to stage2_editorial.md
        requires changing the no-stage-param pin first.
        """
        import inspect

        from forensic_metascience_ai_toolkit import mcp_server
        from forensic_metascience_ai_toolkit import registry as R

        offered = {s.name for s in R.SPECS if s.stages}
        assert set(mcp_server._TOOLS_BY_NAME) == offered
        leaked = set(R.CLI_ONLY) & set(mcp_server._TOOLS_BY_NAME)
        assert not leaked, (
            f"CLI-only tools served over MCP: {sorted(leaked)}"
        )
        handler = mcp_server._call_tool
        params = set(inspect.signature(handler).parameters)
        assert "stage" not in params, (
            "the MCP server now receives a stage -- if it filters on it, "
            "stage2_editorial.md may state the reduced subset again"
        )


class TestNoImpossibleWithoutAnRCrossCheck:
    """The R cross-check gate lived only in `tool_reference.md`, which is never sent.

    So "use these before any `impossible` verdict leaves the sweep" reached
    nobody, and neither did the caveat that an R error is not evidence -- one of
    the audited paths by which an R crash turned into an `impossible`.
    """

    def test_the_adjudicator_gates_impossible_on_it(self):
        """RE-POINTED to `adjudication.md`, which states the SAME rule in its
        own words -- the v2 pipeline has no editorial stage, and the adjudicator
        is the role holding `r_grim_ground_truth`.

        Asserting the legacy sentence would have read its absence as the rule's
        absence, which is the "absence as evidence" error this repo's LESSONS
        file names. The rule is at adjudication.md section 6.
        """
        assert "r_grim_ground_truth" in ADJUDICATION
        # FLATTENED: the prompts are hard-wrapped, so an assertion on a phrase
        # that straddles a line break fails on the formatting rather than on
        # the rule -- which would be a guard that reports its own layout.
        flat = " ".join(ADJUDICATION.split())
        i = flat.find("r_grim_ground_truth")
        section = flat[max(0, i - 400): i + 600]
        assert "impossible" in section, "the gate must name what it gates"
        # An engine that cannot run is never a disagreement -- the half that
        # actually caused a corpus of GRIM findings to be silently capped.
        assert "cannot run" in section
        assert "never a disagreement" in section

    def test_the_stage_that_names_a_tool_can_actually_call_it(self):
        """The reason the GRIM cross-check is instructed in stage 2 and not the
        sweep: `r_grim_ground_truth` is registered STAGE2-only, while
        `r_sprite_ground_truth` is in both. Naming it in the sweep would produce
        a refused call, which costs a turn and reads to the model like a check
        that happened.
        """
        from forensic_metascience_ai_toolkit import registry as R

        assert R.STAGE2 in R.BY_NAME["r_grim_ground_truth"].stages
        assert R.STAGE1 in R.BY_NAME["r_sprite_ground_truth"].stages
        # The live analyst must not name a tool only the adjudicator can call:
        # a refused call costs a turn and reads to the model like a check that
        # happened. `tool_expert.md` may REFER to it when routing the request.
        assert "run `r_grim_ground_truth`" not in TOOL_EXPERT

    def test_the_rsprite2_precision_trap_is_stated_where_it_is_sent(self):
        """`rsprite2` infers precision from the LITERAL, so mean=4.0 reads as 0
        decimals. Unpinned, the engines answer different questions and appear to
        disagree -- which has already produced one false "the repo is broken".
        """
        for name, doc in (("tool_expert.md", TOOL_EXPERT),):
            flat = " ".join(doc.split())  # the prompts are hard-wrapped
            assert "infers" in flat and "LITERAL" in flat, name
            assert "reads as ZERO decimals" in flat, name


class TestEstimateCiDecimalsGuidance:
    """The two consequences were swapped in tool_reference.md.

    `estimates._decimals` now delegates to `rounding.decimals_of_value`, which
    errs toward the WIDER interval only: `1.40` still reads as 1 dp (too
    coarse -> tolerance ten times too loose), but an integral `5` reads as
    0 dp -- exact -- where the old `str()`-based fallback read it as 1 dp, ten
    times too TIGHT, the one direction that accuses an ordinary number
    (measured: honest "OR 4 (1-9)" came back suspicious). tool_reference.md's
    `5`-reads-too-tight sentence now describes the RETIRED fallback and needs
    its own update; the pairing test below keeps checking the doc's internal
    ordering until it is rewritten.
    """

    def test_the_measured_behaviour_is_the_wide_erring_fallback(self):
        from forensic_metascience_ai_toolkit.tools.estimates import _decimals

        assert _decimals(float("1.40")) == 1, "printed 2 dp, read as 1: too coarse"
        assert _decimals(float("5")) == 0, "integral values read exact, never tight"

    def test_the_doc_pairs_each_literal_with_the_right_consequence(self):
        """`1.40` -> too LOOSE, and that direction is still live.

        This test used to also require the doc to present an integral `5` as
        reading TOO TIGHT. That was true of the old fallback and is no longer:
        `decimals_of_value` now infers 0 decimals for an integral, which is what
        it asserts, and `OR 4 (1-9)` -- the correct 0 dp rounding of 3.6
        (1.4-9.4) -- no longer comes back `suspicious`. A test that requires the
        documentation to keep describing a fixed defect as current is a test
        that keeps the documentation wrong.
        """
        start = REFERENCE.index("## Estimate vs its own confidence interval")
        i = REFERENCE.index("**Pass `decimals`**", start)
        para = " ".join(REFERENCE[i : i + 1100].split())
        coarse = para.index("1.40")
        assert para.index("LOOSE") > coarse, (
            "`1.40` must be paired with the TOO LOOSE consequence"
        )
        assert "still live" in para, (
            "the doc must say WHICH direction remains a reason to pass `decimals`"
        )
        assert "FIXED" in para and para.index("FIXED") < para.index("TIGHT"), (
            "the integral-`5` case must be marked fixed BEFORE its old "
            "consequence is described, or a reader takes it as current"
        )


class TestBatchToolsAreJustifiedByCorrectness:
    """"each call is a turn" is false, and it was the entire stated reason.

    Turns are not what a call costs, and pricing the batch tools that way meant
    the real reason went unsaid: the batch ROW carries its own `df`,
    `decimals_*`, `tolerance` and `label`. One set of precisions across a whole
    table is wrong for most of it, and a row whose `df` was not carried comes
    back `indeterminate` with nothing checked. Cost is the symptom; the defect
    is that the per-call form checks the wrong window.
    """

    DOCS = {**LIVE_DOCS, "tool_reference.md": REFERENCE}

    @pytest.mark.parametrize("name", sorted(DOCS))
    def test_the_false_justification_is_gone(self, name):
        assert "call is a turn" not in self.DOCS[name]

    @pytest.mark.parametrize("name", sorted(DOCS))
    def test_the_anecdotes_are_dated_as_pre_batch(self, name):
        """Two runs are cited by their call counts. They predate the batch tools,
        so quoting them undated implies the batch form exists and is unused.
        """
        doc = self.DOCS[name]
        for count in ("55 of 124", "79 of 111"):
            if count in doc:
                i = doc.index(count)
                window = doc[max(0, i - 200) : i + 200]
                assert "pre-batch" in window and "2026-07-27" in window, (
                    f"{name}: the '{count}' anecdote is undated"
                )

    def test_the_real_reason_is_given_where_the_batch_tools_are_recommended(self):
        for marker in ("check_summation_batch", "check_regression_batch"):
            i = REFERENCE.find("**Use the batch form because it is the only form")
            assert i != -1, f"tool_reference.md no longer justifies {marker} on correctness"

    def test_the_registry_rows_really_carry_per_row_arguments(self):
        """Pin the claim the docs now make."""
        from forensic_metascience_ai_toolkit.registry import BY_NAME

        for name in ("check_summation_batch", "check_regression_batch"):
            assert {p.name for p in BY_NAME[name].params} >= {"rows"}
            assert "decimals" in BY_NAME[name].description


class TestTheParametrisationCannotSilentlyShrink:
    """A parametrised case list that shrinks PASSES, which is how a rule stops
    being enforced with nothing going red. These pins are the reason the
    legacy-prompt deletion is safe to run.
    """

    def test_the_live_prompts_are_all_present_and_non_empty(self):
        for name, text in LIVE_DOCS.items():
            assert text.strip(), f"{name} is missing or empty"

    def test_the_cross_document_rules_cover_the_live_prompts(self):
        covered = set(TestBatchToolsAreJustifiedByCorrectness.DOCS)
        assert set(LIVE_DOCS) <= covered, (
            "a live prompt is not in the cross-document rule set; deleting the "
            "legacy prompts would leave those rules policing almost nothing")

    def test_the_rule_set_never_falls_below_the_live_set(self):
        assert len(TestBatchToolsAreJustifiedByCorrectness.DOCS) >= len(LIVE_DOCS)
