"""Every validated tool is reachable from every surface that needs it.

WHY THIS FILE EXISTS
--------------------
Six defects came from one cause: a tool had to be declared by hand in seven
places, and nothing checked that it was.

  1. `power_check`, `estimates`, `celltypes` -- validated, tested, and exposed
     via neither MCP nor the CLI.
  2. The same three absent from the CLI, where a human types.
  3. `csf_test` not passing `design`, so the design gate that takes cluster-trial
     false positives from 41.2% to 0.0% was unreachable.
  4. `grimmer_check` not passing `data_type`, so an ordinary age (mean 48.90,
     SD 14.46, n=49) came back IMPOSSIBLE through the agent's real surface.
  5. All five newly exposed tools absent from the sweep PROCEDURE, which still
     pointed the model at the untyped parser they replaced.
  6. `r_grim_ground_truth` / `r_sprite_ground_truth` allowed in both stages with
     no entry in the tool reference at all.

`registry.py` now makes most of that class unrepresentable rather than merely
tested: the MCP tools and stage allowlists are DERIVED from one declaration per
tool, so they cannot disagree with it. What remains testable is the boundary
between the registry and the surfaces it does NOT generate -- the CLI and the
prompts -- plus the internal consistency of the specs themselves.

These tests import `registry` rather than parsing source. That is possible only
because `registry.py` deliberately does not import `claude_agent_sdk`; the SDK
is confined to `tools_mcp.py`. Had the specs lived there, the unit suite could
not see them -- which is the original reason this defect survived.
"""

from tests.source_paths import canonical, IMAGE_SRC
import ast
import inspect
import pathlib

import pytest

from metascience_agent import registry as R

SRC = pathlib.Path(__file__).parent.parent / "src" / "metascience_agent"
TOOLS_DIR = SRC / "tools"
CLI_SRC = SRC / "cli.py"


# Public functions in tools/ deliberately NOT exposed as tools.
# Each entry needs a reason. "It's a helper" is a reason; silence is not.
INTERNAL_ONLY: dict[str, str] = {
    # SECURITY. Exposing this hands the model arbitrary code execution and
    # defeats DENIED_TOOLS -- it would simply rewrite the checks in R.
    "r_wrappers.run_r_code": "arbitrary R execution; exposing it defeats the tool sandbox",
    "r_wrappers.r_statcheck": "R variant; the `statcheck` tool covers this path",
    "r_wrappers.python_statcheck": "PDF fallback route inside the statcheck adapter",
    # Text repair, not a check: it undoes four extraction artefacts (HTML
    # entities, capital `P`, docling's `\` for `<`, runs of whitespace) that
    # make a printed statistic invisible to statcheck's regexes. Returns a
    # string, has no severity, and asking the agent to "run
    # normalise_for_statcheck on this paper" is meaningless.
    "r_wrappers.normalise_for_statcheck": (
        "text repair applied inside statcheck; returns a string, not a severity"
    ),
    # Driven by `claims.claim_consistency_report`, a deterministic sweep over
    # the anatomy, for the same reason `multiplicity_report` is not a tool: the
    # join it needs (interpretation -> test) already exists in the anatomy, and
    # a check the model must remember to call is a check that silently stops
    # running. Exposing it would also hand the model the `alpha` and
    # `n_tests_claimed` arguments, which are exactly the two that decide
    # whether an honest paper gets accused.
    # The sweep itself: driven by `prepass.run_exhaustive`, which both the
    # legacy and parallel paths call, so it runs on every paper rather than
    # when the model remembers. Harness-aimed coverage is the property that
    # makes it comparable run to run.
    "claims.claim_consistency_report": (
        "harness sweep driven by prepass.run_exhaustive on every paper; not "
        "model-aimed, so its coverage is identical from run to run"
    ),
    "claims.check_claim_vs_result": (
        "driven by the claim_consistency_report sweep; exposing it would let "
        "the model supply the alpha and test-count that gate the accusation"
    ),
    # Single-cell entry points superseded by their batch equivalents.
    "celltypes.parse_cell": "single-cell; `parse_cells_typed` is the exposed batch surface",
    "tableparse.parse_cell": "single-cell; superseded by celltypes.parse_cells",
    "tableparse.reconcile_tables": "reached through parse_table's cross_check argument",
    # WRITES FILES, and answers no forensic question. It re-crops montage
    # sub-panels out of their parent's PNG so a human or an adjudicator can
    # SEE a group -- the segmentation contract gives a crop no PNG of its
    # own, and every segment image path in an adjudication prompt therefore
    # pointed at a file that did not exist (1,744 of 1,744, measured on the
    # Masliah corpus). It is called by the prompt builder, on demand.
    "image_analysis.materialise_crops": (
        "writes crop PNGs so a fired group can be looked at; a file-writing "
        "side effect, not a check the agent chooses to run"
    ),
    # Run bookkeeping for the detector, imported by sweep/retain/
    # within_parallel/overlap_bench. None answers a forensic question.
    "image_analysis.active_experiments": (
        "reads METASCIENCE_IMAGE_EXPERIMENTS for the run stamp; configuration, "
        "not a check, and a model choosing experiments would choose the verdict"
    ),
    "image_analysis.new_refusal_tally": (
        "empty per-run record of transformed-tier refusals; a dict constructor"
    ),
    "image_analysis.merge_refusal_tally": (
        "folds one worker's refusal tally into another; bookkeeping, no severity"
    ),
    # Answers no forensic question and has no severity: it returns a numpy
    # mask saying which PIXELS of a panel are chrome (tick labels, panel
    # letters, scale bars, instrument footers, painted annotation) so the
    # keypoint tier can withhold them from `detectAndCompute`. It is an
    # argument to a detector, not a check anyone would choose to run -- asking
    # the agent to "run chrome_mask on this paper" is meaningless, and the
    # thing it feeds (`content_match_ratio`) is already reported in
    # `match_stats` on every transformed match.
    "chrome_mask.chrome_mask": (
        "pixel mask consumed by the keypoint tier; an input to a check, not "
        "a check, and it returns an array rather than a severity"
    ),
    "chrome_mask.kept_fraction": (
        "one float describing the mask above; reported inside match_stats so "
        "content_match_ratio can be diagnosed, not asked as a question"
    ),
    "chrome_mask.colour_direction": (
        "a panel's mean chromatic direction, consumed by the keypoint tier to "
        "separate two channels of one field; a vector or None, not a verdict"
    ),
    # Pure helpers with no standalone forensic meaning.
    "celltypes.infer_decimal_convention": (
        "document-level verdict on which character this paper uses as its "
        "decimal separator, read once in values.build_from_paper before any "
        "cell is parsed; `74,874` is undecidable from the cell and decidable "
        "from the paper, so this is a property of the conversion rather than a "
        "check an agent chooses to run, and its evidence rides on the "
        "register's `problems` where a reader can audit it"
    ),
    "celltypes.decimal_comma_repair": (
        "separator normaliser run inside parse_cell and read by "
        "values._num_and_decimals; `0,561` was reaching checks as 561.0 -- a "
        "thousandfold error with its printed precision destroyed, which is "
        "what GRIM's granularity depends on. Deciding a separator belongs to "
        "parsing, not to a check the agent chooses to run, and the genuinely "
        "ambiguous `74,874` is deliberately left to document-level inference"
    ),
    "celltypes.repair_unicode": (
        "character normaliser run inside parse_cell; a Unicode minus was "
        "silently deleting estimate-plus-CI cells, and the repair belongs to "
        "parsing rather than being a check the agent chooses to run"
    ),
    # STALE RATIONALE, CORRECTED 2026-08-11. This read "label heuristic used
    # inside parse_cell", which stopped being true when the singular was
    # superseded by the plural `_label_hints` -- that is what `_parse_cell`
    # calls (celltypes.py:338). `label_hint` is called by nothing. An allowlist
    # entry whose stated reason is FALSE is worse than an unexplained one,
    # because it pre-answers the question a reviewer would otherwise ask.
    "celltypes.label_hint": (
        "unwired wrapper over `_label_hints`, which is what `_parse_cell` "
        "actually calls; retained only as the single-kind reading of a label"
    ),
    "estimates.is_ratio_measure": "predicate used inside the estimate checks",
    "estimates.is_difference_measure": "predicate used inside the estimate checks",
    # The declared-format module. `apply_format` is the ONE exposed surface
    # (`parse_cells_as_declared`); everything else here is a piece of it, and
    # each is withheld for a reason rather than because nobody got round to it.
    "cellformat.parse_cell_as": "single-cell; `parse_cells_as_declared` is the exposed batch surface",
    "cellformat.parse_format": "declaration validator run inside apply_format; raises rather than returning a result",
    "cellformat.shape_of": "string abstraction used to cluster unread cells; judges nothing",
    "cellformat.is_numeric_shaped": "predicate separating an unread VALUE from an ordinary row label",
    "cellformat.vocabulary": (
        "the declarable-format menu. Already reachable -- every refusal embeds it "
        "in the error the model reads -- so a second route would be the same list "
        "maintained twice"
    ),
    "cellformat.suggest_formats": (
        "WITHHELD DELIBERATELY: it answers 'which formats would parse these "
        "numbers', and a model that could call it directly could choose a pairing "
        "by fit instead of by reading the table. `142 (71.0)` is equally a valid "
        "mean (SD) and a valid n (%); only the header says which. So the "
        "suggestions are delivered attached to a cluster the model has to read, "
        "never as a question it can put to the numbers alone"
    ),
    "cellformat.describe_unparsed": (
        "reached through `parse_cells_typed`, which runs it on its own results and "
        "returns it as `unparsed`. A separate tool would make the diagnosis "
        "optional, and a whole table failing one cell at a time is precisely what "
        "goes unnoticed when noticing it is opt-in"
    ),
    "cellformat.cluster_unparsed": "the same diagnosis over already-typed cells; the route parse_cells uses",
    "bounds.canonical_measure": (
        "input normaliser: maps the aliases the model writes (`r`, `p`, `R2`, "
        "`AUROC`) onto the canonical measure names `check_statistic_bounds` "
        "keys its table on"
    ),
    "bounds.rescalings_that_fit": (
        "HELPER, NOT A CHECK: which power-of-ten slips would put an "
        "out-of-bounds value back inside its bound. It judges no paper and "
        "returns no severity -- `check_statistic_bounds` attaches its output so "
        "a reader can confirm the alternative reading against the page in one "
        "glance. Not exposed because a model that could call it directly could "
        "rescale a value until it fits and then report the rescaled reading as "
        "though the paper had printed it"
    ),
    "grim.canonical_data_type": "input normaliser used inside the GRIM family",
    "grim.discriminating_power": (
        "PROPERTY OF THE TEST, NOT OF THE PAPER: what share of the printable "
        "grid each rounding convention can reject at a given (n, decimals). It "
        "takes no reported value, judges nothing, and returns no severity -- "
        "`grim_test` consults it to decide whether a `consistent` verdict would "
        "be vacuous, and refuses instead. Not exposed because it answers "
        "'could this check ever fire?', and a model able to ask that before "
        "choosing which cells to check could steer its own coverage toward the "
        "regimes where nothing can be found"
    ),
    "grim.percentage_reading_disagrees": (
        "CAVEAT GENERATOR, NOT A CHECK: asks whether a value consistent as a mean "
        "would be inconsistent read as a percentage of the same n, and returns a "
        "sentence `grim_test` attaches to its own result. It issues no severity "
        "and judges no paper. Not exposed because a model that could call it "
        "directly could shop between the two readings, which is the exact false "
        "clear it exists to surface"
    ),
    "grim.nearby_denominators": (
        "DIAGNOSTIC, NOT A CHECK: which denominators near the supplied n would "
        "make a mean GRIM-consistent. It judges no paper and returns no severity "
        "-- `grim_test` attaches its output as a question for the authors and "
        "leaves the verdict alone. Deliberately NOT exposed: a model that could "
        "call it directly could search for a denominator that clears a finding, "
        "and the measurement in its docstring shows 70-80% of GENUINE failures "
        "fit at some nearby n"
    ),
    "grim.granularity_ceiling": (
        "the severity rule GRIM/GRIMMER/SPRITE share -- given who established that "
        "the observations are integers, what is the strongest verdict a granularity "
        "failure may reach. Not a check: it judges no paper and reads no reported "
        "value, and exposing it would let a caller ask for the ceiling instead of "
        "being bound by it"
    ),
    "effect_size.cohens_d": "computed inside check_effect_plausibility, which is exposed",
    "effect_size.available_fields": "enumerates benchmark keys for the CLI error message",
    "duplication_review_figure.render_review_figure": (
        "PURE RENDERER, NOT A CHECK: turns findings that already exist into a "
        "side-by-side PNG for the human who has to confirm them. It reads no "
        "paper, computes no statistic and returns no severity -- exposing it "
        "would only let the model spend a turn drawing a picture of a verdict "
        "it has already been given"
    ),
    "quarantine.quarantine": (
        "withholds the verdict of a check whose ACCUSATORY calibration is not yet "
        "validated on simulated and real data; applied at a check's own call site, "
        "never chosen by the model -- a model that could decline to quarantine a "
        "held-back check would defeat the point of holding it back"
    ),
    # NOT WIRED, AND THE REASON IS TWO MEASUREMENTS. Exact on synthetic
    # ground truth (recovers a planted paste at offset (330, 0)), but over the
    # full corpus it fired on 369 of 2,372 panels -- 131 papers, 58%. The
    # segment-first fix was tried and made it 139 papers, 61.2%: a corpus
    # panel is one raster whose sub-panels are flush to its edges, so
    # `segment_gray` correctly refuses to split precisely the images that
    # need it, and the search falls back to whole-image mode where montage
    # pitch dominates. Exposing it would accuse three papers in five.
    "copy_move.detect_copy_move": (
        "within-image copy-move search, held out of the registry: 58% corpus "
        "fire rate, and segmenting first did not fix it (61.2%). Needs panel "
        "boundaries in edge-flush montages; see the module docstring"
    ),
    "grimu.canonical_test_type": (
        "normalises test_type aliases for the GRIM-U applicability guard; "
        "not a check -- called only by grimu_check / grimu_coexistence"
    ),
    "ttest.is_conventional_alpha": (
        "shared predicate for the conventional-alpha dual-read guard; "
        "not a check and not callable by the model"
    ),
    # The p_relation machinery (1.86.0): shared by the six p tools that take a
    # `p_relation`, each of which IS registered. None is a check on its own.
    "ttest.looks_like_printed_bound": (
        "shared predicate: could this p be the endpoint of a printed bound; "
        "decides the unstated p_relation, not a check"
    ),
    "ttest.resolve_p_relation": (
        "normalises p_relation / p_is_threshold for the p tools; not a check"
    ),
    "ttest.p_under_claimed": (
        "shared under-claim comparison called by the registered p tools"
    ),
    "ttest.under_claim_finding": (
        "builds the under-claim result fields for the registered p tools"
    ),
    "ttest.under_claim_note": (
        "explanation text for an unknown-relation p; plumbing, not a check"
    ),
    "ttest.bound_is_stated": (
        "shared rule: a declared bound gets no rounding slack; called by the p tools"
    ),
    "ttest.check_p_adjustment": (
        "validates the p tools' `p_adjustment` parameter; plumbing, not a check"
    ),
    "ttest.explain_under_claim": (
        "demotes an under-claim the paper explains (a declared correction, a "
        "reconstructed test); called by the registered p tools"
    ),
    "severity.normalize_severity": "severity-string plumbing",
    "severity.severity_from_consistency": "severity-string plumbing",
    "severity.refuse_if_nonfinite": "shared non-finite input guard, called by the raw check functions",
    # Rounding arithmetic. Every check comparing a recomputed quantity against
    # a reported one runs through these; none is a forensic technique on its
    # own, and a model able to call them separately would be doing a check's
    # arithmetic outside the check, where nothing validates the result.
    "rounding.half_width": "rounding arithmetic inside every interval-based check",
    "rounding.tolerance": "rounding arithmetic inside every interval-based check",
    "rounding.interval": "rounding arithmetic inside every interval-based check",
    "rounding.matches_at_precision": "rounding arithmetic inside every interval-based check",
    "rounding.accumulated_half_width": "rounding arithmetic inside the summation check",
    "rounding.quotient_interval": "rounding arithmetic inside the regression check",
    "rounding.decimals_of_value": "fallback precision reader for parsed floats",
    "rounding.decimals_of_text": "printed-precision reader used by the cell parser",
    "rounding.coarsest_decimals": "printed-precision reader used by the cell parser",
    # The rounding-CONVENTION windows. Internal for the same reason as the rest
    # of this module: they return an interval, not a severity, and "run
    # rounding.window on this paper" is not a question. They are shared by
    # grim, grimmer and sprite so the three cannot disagree about one cell.
    "rounding.window": "rounding arithmetic; returns an interval, not a verdict",
    "rounding.windows": "rounding arithmetic; returns intervals, not a verdict",
    # Copy-move adjudication plumbing (2026-08-21). These serve the
    # deterministic image track's post-hoc adjudication -- a child process
    # renders a red/green overlay and a cheap vision model rules on it via
    # metascience-observatory-image-analysis/examples/adjudicate_copy_move.py -- and none is a check the agent
    # chooses to run mid-sweep (the same reason analyze_paper_images itself
    # is CLI-only).
    "copy_move.classify_panel_kind": (
        "labels a panel photo/chart/text for the overlay prompt; an input "
        "preparer, not a forensic verdict"
    ),
    "copy_move.render_overlay": (
        "writes the red/green overlay PNG a human or adjudicator looks at; "
        "a file-writing side effect, not a check"
    ),
    "copy_move_adjudicate.overlay_png_bytes": "overlay bytes for the vision prompt",
    "copy_move_adjudicate.overlay_stats": "pixel counts summarised into the prompt",
    "copy_move_adjudicate.resolve_backend": "transport selection (OpenRouter vs claude CLI)",
    "copy_move_adjudicate.adjudicate_copy_move_overlay": (
        "the driver: one vision call per overlay, fail-open; launched by the "
        "example script, never by an agent mid-sweep"
    ),
    "copy_move_adjudicate.apply_copy_move_adjudication": (
        "applies the verdict to the stored hit record; bookkeeping, not a check"
    ),
    "copy_move_adjudicate.adjudicate_hit": "per-hit wrapper over the driver",
}


#: Tool modules that moved from `tools/` into `image_forensics/`. Their
#: `INTERNAL_ONLY` keys stay stem-based so the reasons recorded there survive
#: the move; the shims left behind in `tools/` define no functions.
_MOVED_TOOL_STEMS = ("image_analysis", "chrome_mask", "copy_move",
                     "copy_move_adjudicate", "duplication_review_figure")



try:  # the separately distributed image package; absent -> its modules are not scanned
    IMAGE_SRC = __import__("pathlib").Path(__import__("metascience_observatory_image_analysis").__file__).parent
except ImportError:
    IMAGE_SRC = None
def _public_tool_functions() -> dict[str, object]:
    """Qualified name -> function, for every public top-level function in tools/."""
    out = {}
    paths = [p for p in sorted(TOOLS_DIR.glob("*.py")) if p.name != "__init__.py"]
    if IMAGE_SRC is not None:
        paths += [IMAGE_SRC / "image_forensics" / f"{stem}.py" for stem in _MOVED_TOOL_STEMS]
    for path in paths:
        tree = ast.parse(canonical(path).read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
                out[f"{path.stem}.{node.name}"] = node.name
    return out


def _cli_commands() -> dict[str, set[str]]:
    """CLI command name -> its parameter names."""
    import inspect
    from metascience_agent.cli import app
    return {info.name or info.callback.__name__.replace("_", "-"):
            set(inspect.signature(info.callback).parameters)
            for info in app.registered_commands}



class TestRegistryIntegrity:
    """The specs must be internally consistent before anything derives from them."""

    def test_names_are_unique(self):
        names = [s.name for s in R.SPECS]
        dupes = sorted({n for n in names if names.count(n) > 1})
        assert not dupes, f"duplicate tool names shadow each other: {dupes}"

    def test_legacy_verbs_are_unique(self):
        """Archived reproductions are read back to a tool by their retired
        verb; two tools claiming one verb would misattribute them."""
        verbs = [s.legacy_verb for s in R.SPECS if s.legacy_verb]
        dupes = sorted({c for c in verbs if verbs.count(c) > 1})
        assert not dupes, f"two tools claim the same retired verb: {dupes}"

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_every_spec_is_callable(self, spec):
        assert callable(spec.fn) or spec.adapter is not None, (
            f"{spec.name} has no implementation and no adapter"
        )

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_params_match_the_implementation_signature(self, spec):
        """A param the function does not accept is a TypeError waiting to fire.

        This is the check that would have caught a rename in `tools/` that the
        registry did not follow -- the failure mode a registry introduces, and
        therefore the one it must be tested against.
        """
        if spec.adapter is not None:
            return  # adapters shape args deliberately; covered by equivalence tests
        sig = inspect.signature(spec.fn)
        accepted = set(sig.parameters)
        if any(p.kind == p.VAR_KEYWORD for p in sig.parameters.values()):
            return
        # `uncertainty` is GATE METADATA, not a tool argument: ToolSpec.call()
        # reads it to decide whether to refuse, and never forwards it. It is
        # declared as a Param so it reaches the MCP schema -- without that the
        # gate is unreachable from the agent, which is exactly how it shipped
        # unreachable the first time.
        # `provenance` is gate metadata on the same terms wherever the function
        # does not declare it: the registry converts it into an `uncertainty`
        # stamp and refuses there, so the check itself never sees it. Two tools
        # DO take it -- `check_table` and `check_effect_plausibility` -- and use
        # it in their own reasoning, which is why this is exempted per FUNCTION
        # rather than by name.
        # Exempt EVERY meta param the function does not accept, rather than a
        # hardcoded pair. `ToolSpec.call` skips all of them when assembling
        # kwargs, so "declared meta and not in the signature" is exactly the
        # legal case -- and naming them individually meant the next one
        # (`source_quote`, `source_locator`) broke 72 tests on arrival while
        # being just as correct as `uncertainty` was.
        gate_meta = {p.name for p in spec.params if p.meta and p.name not in accepted}
        gate_meta.add("uncertainty")
        unknown = sorted({p.name for p in spec.params} - accepted - gate_meta)
        assert not unknown, f"{spec.name}: {spec.fn.__name__}() does not accept {unknown}"

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_required_implementation_args_are_declared(self, spec):
        """Every argument the function REQUIRES must be a declared param.

        Otherwise the tool raises TypeError the first time the model calls it.
        """
        if spec.adapter is not None:
            return
        sig = inspect.signature(spec.fn)
        needed = {
            name for name, p in sig.parameters.items()
            if p.default is inspect.Parameter.empty
            and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
        }
        declared = {p.name for p in spec.params}
        missing = sorted(needed - declared)
        assert not missing, f"{spec.name}: {spec.fn.__name__}() requires undeclared {missing}"

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_description_is_substantive(self, spec):
        assert len(spec.description.strip()) >= 40, (
            f"{spec.name}: description too thin for the model to route on"
        )

    @pytest.mark.parametrize("spec", R.SPECS, ids=lambda s: s.name)
    def test_stages_are_recognised(self, spec):
        # The three roles of the parallel pipeline (docs/specs/pipeline.md
        # section 6); STAGE1/STAGE2 are deprecated aliases of the first two.
        roles = {R.TOOL_AGENT, R.SCIENCE_AGENT, R.ADJUDICATOR}
        assert spec.stages <= roles, f"{spec.name}: unknown stage"


class TestGuardsAndWithholding:
    """Guards must be settable; search budgets must not be."""

    #: Preconditions without which the tool accuses ordinary numbers.
    #: Specificity is 0.846 with correct bounds and 0.0000 with wrong ones.
    EXPECTED_GUARDS = {
        "grim_check": {"data_type", "bound_source"},
        "grimmer_check": {"data_type", "decimals", "decimals_sd"},
        "sprite_reconstruct": {"data_type"},
        "debit_check": {"data_type"},
        "csf_test": {"design"},
        "check_estimate_ci": {"measure"},
        "verify_power_analysis": {"test_type"},
    }

    #: Deliberately withheld: a model that can widen a search can search until
    #: it gets the verdict it wants.
    EXPECTED_WITHHELD = {
        "sprite_reconstruct": {"max_iterations"},
        "csf_test": {"rho_grid"},
    }

    @pytest.mark.parametrize("name,guards", EXPECTED_GUARDS.items())
    def test_guards_are_declared(self, name, guards):
        assert guards <= R.BY_NAME[name].guards(), (
            f"{name}: {sorted(guards - R.BY_NAME[name].guards())} not marked guard=True"
        )

    @pytest.mark.parametrize("name,guards", EXPECTED_GUARDS.items())
    def test_guards_reach_the_model(self, name, guards):
        missing = sorted(guards - set(R.BY_NAME[name].schema()))
        assert not missing, (
            f"{name} does not accept {missing} through MCP, so the model cannot set it "
            "and the tool silently runs on defaults."
        )

    @pytest.mark.parametrize("name,withheld", EXPECTED_WITHHELD.items())
    def test_withheld_params_never_reach_the_model(self, name, withheld):
        leaked = sorted(withheld & set(R.BY_NAME[name].schema()))
        assert not leaked, (
            f"{name} now exposes {leaked}. These control how hard the tool searches; "
            "a model that can tune them can search until the verdict suits it."
        )

    def test_a_guard_is_never_also_withheld(self):
        for spec in R.SPECS:
            both = spec.guards() & spec.withheld()
            assert not both, f"{spec.name}: {sorted(both)} is both guard and withheld"

    def test_withheld_params_have_defaults(self):
        """A withheld param with no default makes the tool uncallable."""
        for spec in R.SPECS:
            for p in spec.params:
                if p.withheld:
                    assert not p.required, (
                        f"{spec.name}.{p.name} is withheld but required -- the model "
                        "cannot supply it and it has no default, so the tool can never run"
                    )


class TestCoverage:
    """Nothing validated may be left unreachable."""

    def test_every_public_tool_is_registered_or_declared_internal(self):
        registered = {getattr(s.fn, "__name__", None) for s in R.SPECS}
        unreachable = [
            qual for qual, fname in _public_tool_functions().items()
            if fname not in registered and qual not in INTERNAL_ONLY
        ]
        assert not unreachable, (
            "Validated tools reachable from NEITHER the registry nor INTERNAL_ONLY, "
            "so the agent cannot call them:\n  " + "\n  ".join(unreachable)
            + "\n\nAdd a ToolSpec, or add them to INTERNAL_ONLY WITH A REASON."
        )

    @pytest.mark.usefixtures("image_package")
    def test_internal_only_entries_still_exist(self):
        stale = sorted(set(INTERNAL_ONLY) - set(_public_tool_functions()))
        assert not stale, (
            f"INTERNAL_ONLY names functions that no longer exist: {stale}. Remove them "
            "so the allowlist cannot mask a future function of the same name."
        )

    def test_internal_only_reasons_are_substantive(self):
        for name, reason in INTERNAL_ONLY.items():
            assert len(reason.strip()) >= 15, f"{name}: give a real reason, got {reason!r}"

    #: Demoted out of both stages by the redundancy audit; still CLI-reachable.
    #: Each entry needs a reason -- a tool nobody can call is either a mistake or
    #: a decision, and the difference has to be written down.
    # THE REGISTER LIVES IN `registry.CLI_ONLY`, not here. This file used to
    # keep its own literal copy, and after four tools were re-offered to the
    # stages the copy still listed them as deliberately unreachable -- two
    # registers of intent, disagreeing, with nothing to notice.
    CLI_ONLY = R.CLI_ONLY

    def test_copy_move_stays_unwired(self):
        """58% corpus fire rate; wiring it accuses three papers in five.

        Named here so a well-meaning 'add the missing tool' cannot land
        without deleting this test and the measurements it cites.
        """
        from metascience_agent.agent import STAGE1_TOOLS, STAGE2_TOOLS
        from metascience_agent.tools_mcp import ALL_TOOLS
        names = {s.name for s in R.SPECS}
        assert "detect_copy_move" not in names
        assert "copy_move" not in names
        mcp_names = {getattr(t, "name", None) for t in ALL_TOOLS}
        assert "detect_copy_move" not in mcp_names
        joined = " ".join(STAGE1_TOOLS + STAGE2_TOOLS)
        assert "copy_move" not in joined
        assert "detect_copy_move" not in joined

    def test_every_tool_is_callable_by_at_least_one_stage(self):
        orphans = [s.name for s in R.SPECS if not s.stages and s.name not in self.CLI_ONLY]
        assert not orphans, (
            f"served by MCP but no stage may call them: {orphans}. If that is "
            "intentional, say so here."
        )


class TestCliSurface:
    """`metascience tool run` is the ONE command-line route to a tool.

    The hand-written per-tool verbs called `tools/*.py` directly and skipped
    `ToolSpec.call`'s gates (`grim` defaulted `decimals=2` where the MCP
    surface refuses a missing precision). They were retired in 1.95.0. These
    pin both halves: none comes back, and nothing became unreachable.
    """

    @pytest.mark.usefixtures("image_package")
    def test_no_tool_has_a_hand_written_verb(self):
        commands = _cli_commands()
        back = sorted(s.legacy_verb for s in R.SPECS
                      if s.legacy_verb and s.legacy_verb in commands)
        assert not back, (
            f"per-tool verb(s) are back in the CLI: {back}. They skip the "
            "registry's gates; use `metascience tool run <tool> --json ...`.")

    def test_every_tool_runs_from_the_command_line(self, monkeypatch):
        """An operator (no role, no manifest in the environment) can run every
        registered tool -- the two CLI-only ones included, since `tool run`
        is now their only command-line route."""
        from metascience_agent import tool_cli
        monkeypatch.delenv("METASCIENCE_MCP_STAGE", raising=False)
        monkeypatch.delenv("METASCIENCE_MCP_TOOLS", raising=False)
        served = set(tool_cli._served())
        unreachable = sorted(s.name for s in R.SPECS
                             if s.name not in served
                             and not tool_cli._operator_may_run(s.name))
        assert not unreachable, f"tools with no command-line route: {unreachable}"

    def test_a_fenced_agent_still_cannot_run_the_cli_only_tools(self, monkeypatch):
        from metascience_agent import tool_cli
        monkeypatch.setenv("METASCIENCE_MCP_STAGE", R.TOOL_AGENT)
        for name in R.CLI_ONLY:
            assert not tool_cli._operator_may_run(name), name


class TestPromptCoverage:
    """A tool the prompts never mention will not be used."""

    #: Tools whose absence from the sweep PROCEDURE would change what it does.
    MUST_APPEAR_IN_PROCEDURE = [
        "parse_cells_typed",
        "check_estimate_ci",
        "absence_of_evidence",
        "verify_power_analysis",
        # check_table was exposed in STAGE1 and named NOWHERE in this prompt, so
        # the model never called it and swept table cells one at a time instead.
        # Measured on one pre-batch run (2026-07-27): 110 of 124 calls were two
        # checks invoked once per cell. Cost is the visible symptom; the defect
        # is correctness -- check_table carries each cell's OWN precision,
        # binding and provenance into the check, which per-cell calls made by
        # hand do not.
        "check_table",
        # extract_html is the whole XML-not-available fallback path; if the
        # procedure stops naming it, a paper fetched as HTML silently degrades
        # straight to body.md/PDF with the richer table structure never used.
        "extract_html",
    ]

    def _sweep(self):
        # Assembled: the per-tool guidance lives in each tool's TOOL.md.
        from metascience_agent.core.prompts import tool_expert_body
        return tool_expert_body()

    def _reference(self):
        return (SRC.parents[1] / "docs" / "tool_reference.md").read_text(encoding="utf-8")

    @pytest.mark.parametrize("tool", MUST_APPEAR_IN_PROCEDURE)
    def test_named_in_the_sweep_procedure(self, tool):
        assert tool in self._sweep(), (
            f"{tool} is registered and allowed in stage 1, but the sweep prompt never "
            "mentions it, so the model will not use it."
        )

    def test_every_stage1_tool_carries_a_description_the_model_actually_gets(self):
        """The MCP `description` is the only per-tool prose that reaches the sweep.

        This replaces the tool_reference.md coverage check above. A tool allowed
        in stage 1 with a stub description is the real version of the defect that
        test was aiming at: the model has nothing to route on. Threshold is
        deliberately low (80 chars) -- this catches "TODO" and a bare restatement
        of the name, not thin-but-real prose.
        """
        thin = sorted(
            f"{name} ({len(R.BY_NAME[name].description)} chars)"
            for name in R.stage_tools(R.STAGE1)
            if len(R.BY_NAME[name].description) < 80
        )
        assert not thin, (
            "Allowed in the sweep but with no usable description in the ONLY "
            f"per-tool text the model receives: {thin}"
        )

    def test_the_human_tool_reference_still_covers_every_stage1_tool(self):
        """Kept, but for its real purpose: a human reading the repo.

        Demoted from "the model has no description to route on" (false -- see
        above) to what it actually protects. `r_grim_ground_truth` and
        `r_sprite_ground_truth` were once allowed in both stages with no entry
        here at all, and a maintainer auditing the toolkit would not have known
        they existed.
        """
        reference = self._reference()
        undocumented = sorted(
            name for name in R.stage_tools(R.STAGE1) if name not in reference
        )
        assert not undocumented, (
            "Allowed in the sweep but absent from the human tool reference: "
            f"{undocumented}"
        )

    def test_every_command_the_human_tool_reference_shows_still_exists(self):
        """The reference's CLI examples are the part a reader copies and runs,
        and the part that rots silently when a verb or flag is renamed. Since
        1.95.0 they are `metascience tool run <tool>`, so the tool named must
        be registered too."""
        import re
        from typer.main import get_command
        from metascience_agent.cli import app
        commands = get_command(app).commands
        reference = self._reference()
        verbs = (set(re.findall(r"^metascience ([a-z][a-z0-9-]+)", reference, re.M))
                 | set(re.findall(r"`metascience ([a-z][a-z0-9-]+)", reference)))
        # The image verbs exist only with the image package installed.
        missing = sorted(v for v in verbs
                         if v not in commands and not v.startswith("image"))
        assert not missing, f"docs/tool_reference.md shows verbs that do not exist: {missing}"
        bad_flags = []
        for m in re.finditer(r"^metascience ([a-z0-9-]+)(.*)$", reference, re.M):
            cmd = commands.get(m.group(1))
            if cmd is None:
                continue
            rest = m.group(2)
            sub = re.match(r"\s+([a-z][a-z0-9-]*)", rest)
            if hasattr(cmd, "commands") and sub and sub.group(1) in cmd.commands:
                # A group (`metascience tool run ...`): the flags are the
                # subcommand's.
                cmd, rest = cmd.commands[sub.group(1)], rest[sub.end():]
            # Text inside quotes is an argument (a JSON payload), not a flag.
            rest = re.sub(r"'[^']*'|\"[^\"]*\"", "", rest)
            opts = {o for p in cmd.params for o in p.opts}
            bad_flags += [f"{m.group(1)} {f}" for f in re.findall(r"(--[a-z0-9-]+)", rest)
                          if f not in opts]
        assert not bad_flags, f"docs/tool_reference.md shows flags that do not exist: {bad_flags}"
        tools = set(re.findall(r"metascience tool (?:run|describe) ([a-z0-9_]+)", reference))
        unknown = sorted(t for t in tools if t not in R.BY_NAME)
        assert not unknown, f"docs/tool_reference.md runs tools that do not exist: {unknown}"
        assert len(tools) > 20, "the tool-run pattern stopped matching the reference"

    def test_typed_parsing_precedes_every_checking_step(self):
        """`parse_table` alone reads `142 (71.0)` as mean=142, sd=71.0.

        Pinned to ORDER rather than to a literal step heading -- the headings
        were renumbered when the batched `check_table` step was inserted, and a
        test that breaks on renumbering says nothing about the property it is
        supposed to protect.
        """
        sweep = self._sweep()
        typed = sweep.index("parse_cells_typed")
        for marker in ("check_table` ONCE", "Check each remaining statistic"):
            assert marker in sweep, f"sweep procedure no longer contains {marker!r}"
            assert typed < sweep.index(marker), (
                "typed parsing must be instructed in the READ step, before any check runs"
            )

    def test_the_batched_table_check_precedes_the_per_statistic_tools(self):
        """Offering the individual tools first is how 55 per-cell calls happened."""
        sweep = self._sweep()
        assert sweep.index("check_table` ONCE") < sweep.index("Check each remaining statistic")


class TestTheHelpStringsActuallyReachTheModel:
    """135 authored help strings existed and none was ever sent.

    `ToolSpec.schema` emits `Annotated[type, help]` and its docstring explains
    why: an earlier round found 14 help strings that "existed and were
    invisible". `mcp_server._to_json_schema` then looked the annotated type up
    in a dict keyed on BARE types, missed, and took the `.get(typ, "string")`
    fallback -- discarding the description AND mistyping the parameter, in one
    line, silently. A fix at one layer undone at the next.

    The parameter this mattered most for is `source_quote`: no tool DESCRIPTION
    mentions it, so the model was asked for it with no statement anywhere of
    what it is for, which is the project's primary feature.
    """

    @staticmethod
    def _seen(name):
        from metascience_agent.mcp_server import _to_json_schema
        from metascience_agent.registry import BY_NAME
        return _to_json_schema(BY_NAME[name].schema())["properties"]

    def test_the_primary_features_instruction_is_on_the_wire(self):
        desc = self._seen("grim_check")["source_quote"].get("description", "")
        assert "VERBATIM" in desc
        assert "contiguous span" in desc

    def test_no_tool_description_repeats_it_so_the_schema_is_the_only_route(self):
        from metascience_agent.registry import SPECS
        assert not [s.name for s in SPECS if "VERBATIM text from the paper" in s.description]

    def test_every_authored_help_string_reaches_the_model(self):
        from metascience_agent.mcp_server import _to_json_schema
        from metascience_agent.registry import SPECS
        missing = []
        for spec in SPECS:
            props = _to_json_schema(spec.schema())["properties"]
            for p in spec.params:
                if p.withheld or not getattr(p, "help", None):
                    continue
                if not props.get(p.name, {}).get("description"):
                    missing.append(f"{spec.name}.{p.name}")
        assert not missing, f"help authored and not sent: {missing[:10]}"

    def test_an_annotated_parameter_keeps_its_real_type(self):
        """31 params were advertised as strings when they are not -- every
        `decimals` among them, whose whole job is to carry a printed precision
        as an integer."""
        assert self._seen("grim_check")["decimals"]["type"] == "integer"
        assert self._seen("check_regression")["decimals_b"]["type"] == "integer"

    def test_no_parameter_is_mistyped_as_string(self):
        from metascience_agent.mcp_server import _PY_TYPE_TO_JSON, _to_json_schema
        from metascience_agent.registry import SPECS
        bad = []
        for spec in SPECS:
            props = _to_json_schema(spec.schema())["properties"]
            for p in spec.params:
                if p.withheld:
                    continue
                want = _PY_TYPE_TO_JSON.get(p.type, "string")
                got = props.get(p.name, {}).get("type")
                if got != want:
                    bad.append(f"{spec.name}.{p.name}: {got} != {want}")
        assert not bad, bad[:10]

    def test_a_plain_type_still_works(self):
        from metascience_agent.mcp_server import _to_json_schema
        assert _to_json_schema({"x": int}) == {
            "type": "object", "properties": {"x": {"type": "integer"}}}

    def test_an_already_built_json_schema_passes_through(self):
        from metascience_agent.mcp_server import _to_json_schema
        given = {"type": "object", "properties": {"y": {"type": "string"}}}
        assert _to_json_schema(given) is given
