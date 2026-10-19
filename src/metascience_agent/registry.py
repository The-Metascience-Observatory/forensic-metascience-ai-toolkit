"""Single source of truth for every forensic tool.

WHY THIS EXISTS
---------------
Adding a tool used to require touching seven places, in the right way, by hand:

    tools/<mod>.py -> tools/__init__.py -> tools_mcp.py (@tool + ALL_TOOLS)
    -> agent.py (STAGE1_TOOLS + STAGE2_TOOLS) -> cli.py
    -> prompts/tool_reference.md -> prompts/stage1_sweep.md

(`tool_reference.md` is now `docs/tool_reference.md`, for humans.)

Nothing enforced that, and six separate defects followed. Every one was an
omission in a DIFFERENT one of those seven places:

  1. `power_check`, `estimates`, `celltypes` -- validated, tested, and exposed
     via neither MCP nor the CLI.
  2. The same three absent from the CLI specifically, where a human types.
  3. `csf_test` not passing `design` through MCP, so the design gate that takes
     cluster-trial false positives from 41.2% to 0.0% was unreachable.
  4. `grimmer_check` not passing `data_type`, so an ordinary age was called
     impossible through the agent's real surface.
  5. All five newly exposed tools absent from the sweep PROCEDURE, which still
     directed the model at the untyped parser they replaced.
  6. `r_grim_ground_truth` / `r_sprite_ground_truth` allowed in both stages with
     no entry in the tool reference at all -- the tools whose entire job is
     cross-checking us against canonical R before we accuse anyone.

Tests can catch each omission after the fact. A registry makes the whole class
unrepresentable: one `ToolSpec` per tool, and the MCP wrappers, the per-stage
allowlists and the reference documentation are DERIVED from it.

WHAT IS DERIVED VS VERIFIED
---------------------------
Derived (cannot drift):  MCP tool objects, ALL_TOOLS, STAGE1_TOOLS, STAGE2_TOOLS.

Verified (not derived):  the CLI commands and `docs/tool_reference.md`. Both
                         carry per-tool prose that is worth more than
                         uniformity: a CLI command formats its own results
                         meaningfully, and a reference section explains WHEN a
                         check applies and what it refuses. Generating either
                         would flatten that into boilerplate. So the registry
                         declares the CLI name and its required flags, and tests
                         assert the command exists, exposes them, and that every
                         stage-1 tool has a reference entry.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, replace
from typing import Annotated, Any, Callable

# Sentinel: this parameter has no default and the caller must supply it.
REQUIRED = object()

# Recognised stages. A tool may belong to either, both, or neither (a tool in
# neither is reachable from the CLI and the Python API but never by the agent --
# legal, but it must be a deliberate choice, so `stages=frozenset()` is explicit).
# The three agent ROLES of the parallel pipeline (docs/specs/pipeline.md
# section 6). STAGE1/STAGE2 are deprecated aliases kept so the ~100 existing
# stanza tokens and call sites keep meaning what they now mean: the old
# stage-1 sweep set IS the tool-expert's, and the old stage-2 editorial set
# IS the adjudicator's spot-check surface.
TOOL_AGENT = "tool_agent"
SCIENCE_AGENT = "science_agent"
ADJUDICATOR = "adjudicator"
STAGE1 = TOOL_AGENT
STAGE2 = ADJUDICATOR

#: Registry names that are INFRASTRUCTURE, not forensic techniques -- the
#: extraction/parsing surface plus sandboxed code execution. Excluded from
#: the generated findings-v2 `technique` enum exactly as the v1 hand-enum
#: excluded them ("technique lists forensic techniques -- extract_pdf is not
#: in it", CLAUDE.md). A finding cites the CHECK its numbers went through,
#: never the reader that fetched them.
#: Tools whose verdicts the HARNESS files, never the model: `declare_table`'s
#: GRIM failures become `grim_harness.finding_rows` (producer `harness`,
#: technique `grim_check` / `grim_percentage`), and the model is told not to
#: file them again. Out of the technique enum so it cannot.
HARNESS_FILED_TOOLS = frozenset({"declare_table"})

NON_TECHNIQUE_TOOLS = frozenset({
    "extract_figures", "extract_html", "extract_pdf", "extract_supplement",
    "extract_xml", "get_supplement_table", "get_table",
    "parse_cells_as_declared", "parse_cells_typed", "parse_table",
    "run_python_script",
    "list_tables",   # a reader: the harness's table index
}) | HARNESS_FILED_TOOLS

#: Tools deliberately reachable from the CLI and never by a model, each with the
#: reason. A tool in NEITHER this map nor any stage is stranded by ACCIDENT --
#: `handoff.reachability` and `tests/test_tool_surface_is_declared` both read
#: this, so the decision lives in one place and an omission fails a test rather
#: than being discovered months later.
CLI_ONLY: dict[str, str] = {
    # NOT sequestered for danger -- the four that were (check_sd_range,
    # flag_round_n, reconstruct_2x2, required_n) are now reachable with their
    # premise made a parameter, which is the better fix. These two are
    # CLI-only for an unrelated reason: a SUBPROCESS calls them, not a model.
    "analyze_paper_images": (
        "called by the deterministic image track, a child subprocess running "
        "concurrently with the sweep, and never by the model -- an LLM "
        "mid-sweep must not launch a CV pipeline. Its findings reach stage 2 "
        "by injection, already quarantined."),
    "detect_tortured_phrases": (
        "called by the deterministic text track, a child subprocess running "
        "concurrently with the sweep, and never by the model -- a free "
        "deterministic screen must not cost paid sweep turns. Its findings "
        "reach stage 2 by injection, already quarantined."),
}

# --- What KIND of claim a tool's verdict is (Greg, 2026-08-09) -------------
#
# A reader auditing a single tool call needs to know, before anything else,
# whether the tool is saying "this is arithmetically impossible" or "this is
# improbable IF you grant these assumptions". Those are different claims with
# different remedies, and the toolkit reported both in the same grammar.
#
# ABSOLUTE -- arithmetic and BOUND-FREE: given the printed values and their
#   rounding intervals, the result is either reachable or it is not. GRIM is the
#   type case (a mean of integer responses over n cases must be a multiple of
#   1/n). These are the ONLY tools permitted to say `impossible`.
# PROBABILISTIC -- plausible vs highly implausible, resting on assumptions (a
#   distribution, a correlation, an independence premise, a design). These cap at
#   `suspicious` / `highly_suspicious` and may never say `impossible`, because
#   the premise, not the arithmetic, may be what failed.
# DESCRIPTIVE -- renders no verdict about a paper: extractors, parsers,
#   calculators, and the R ground-truth wrappers that report another
#   implementation's number.
#
# This is not cosmetic. It is the severity-ladder rule the codebase already
# enforces case by case ("an assumed bound caps at `suspicious`"), stated once,
# declared per tool, and testable.
EVIDENCE_ABSOLUTE = "absolute"
EVIDENCE_PROBABILISTIC = "probabilistic"
EVIDENCE_DESCRIPTIVE = "descriptive"

EVIDENCE_CLASSES = (EVIDENCE_ABSOLUTE, EVIDENCE_PROBABILISTIC, EVIDENCE_DESCRIPTIVE)

#: Plain-language gloss shown to a reader beside each class.
EVIDENCE_MEANING = {
    EVIDENCE_ABSOLUTE: (
        "Absolute (possible vs impossible). Exact arithmetic over the printed values "
        "and their rounding intervals. Subject to the preconditions below, a flagged "
        "result cannot be produced by any dataset."
    ),
    EVIDENCE_PROBABILISTIC: (
        "Probabilistic (plausible vs highly implausible), UNDER THE ASSUMPTIONS below. "
        "A flagged result is unlikely if those assumptions hold; if one fails, the "
        "finding may have an innocent explanation. Never reported as `impossible`."
    ),
    EVIDENCE_DESCRIPTIVE: (
        "Descriptive. Extracts, parses or computes a quantity; it does not itself "
        "render a verdict about the paper."
    ),
}

# The strongest verdict each class may reach. Enforced by test, not by hope.
EVIDENCE_CEILING = {
    EVIDENCE_ABSOLUTE: "impossible",
    EVIDENCE_PROBABILISTIC: "highly_suspicious",
    EVIDENCE_DESCRIPTIVE: "indeterminate",
}

# Provenance values that mean "we READ this off the artwork", as opposed to
# "the authors PRINTED it". `check_table` already takes this string and converts
# it into an `uncertainty` stamp on every exact param; the same three words have
# to mean the same thing on a DIRECT single-tool call, which is the only surface
# stage 2 has. Kept identical to `dispatch.check_table`'s tuple on purpose --
# `figure_pixels` is `check_effect_plausibility`'s spelling of the same idea.
MEASURED_PROVENANCE = frozenset({"measured_raster", "measured_vector", "figure_pixels"})

# Provenance values that mean "a MACHINE read this numeral off an image for us".
# Separate from MEASURED_PROVENANCE because the refusal has a different REASON
# and a different remedy, and a reader who is given the wrong one cannot audit
# it. See `extraction/figures.py` for the full argument; in short:
#
#   measured  -- there is no last printed digit. Remedy: none; use a
#                tolerance-aware check, or a value the paper printed.
#   ocr       -- there IS a last printed digit and we may have misread it.
#                Remedy: confirm the cell against the image and re-stamp it
#                `printed_table`, at which point every check runs normally.
#
# Both refuse the exact-arithmetic family, which is why they share a tier. They
# do not share a sentence.
TRANSCRIBED_PROVENANCE = frozenset({"ocr_table", "ocr_text"})

#: What the exact-arithmetic gate actually refuses. One name, so a future third
#: category is added in one place rather than in every `in (...)` tuple.
UNVERIFIED_PROVENANCE = MEASURED_PROVENANCE | TRANSCRIBED_PROVENANCE

#: Help text for the `provenance` param added to every exact-arithmetic check.
#: One string, because 15 copies of it would be 15 chances to drift.
PROVENANCE_HELP = (
    "Where these numbers came from. 'measured_raster' / 'measured_vector' mean you "
    "READ them off a figure's marks; this check then REFUSES, because it tests "
    "whether a value is possible to its LAST PRINTED DIGIT and a measured value has "
    "no last printed digit. 'ocr_table' / 'ocr_text' mean a MACHINE transcribed the "
    "numeral off an image (any cell an extractor returned with provenance 'ocr_table' "
    "-- scanned supplements arrive this way); this check refuses those too, for a "
    "different reason: the digit exists but we may have misread it, and a misread "
    "digit yields `impossible` against arithmetic that was fine. Anything the paper "
    "printed and we read from a text layer -- table, text, or a numeral inside a "
    "figure -- is not measured and runs normally."
)

#: The counterpart of the `bound_source` help, for the OTHER premise the
#: granularity family rests on. See `tools/grim.HARD_DISCRETENESS_SOURCES` for
#: the decision behind it (Greg, 2026-08-10).
DISCRETENESS_SOURCE_HELP = (
    "stated | logically_necessary | assumed (default). WHO says each subject "
    "contributed a WHOLE NUMBER. 'stated' only if the PAPER establishes it -- a "
    "quoted scale definition, an item count with its response options, 'number "
    "of falls'. 'logically_necessary' if it cannot be otherwise whatever the "
    "paper says. Otherwise leave it: a GRANULARITY verdict resting on an assumed "
    "discreteness caps at `suspicious` rather than `impossible`, because the "
    "arithmetic is airtight only if the premise holds, and a continuous measure "
    "or a mean of k items produces the identical arithmetic from honest data."
)


@dataclass(frozen=True)
class Param:
    """One tool parameter, described once for every surface that needs it."""

    name: str
    type: type
    default: Any = REQUIRED
    help: str = ""

    #: A precondition the model MUST be able to state (`data_type`,
    #: `bound_source`, `design`, `measure`). A misspecified scale bound INVERTS
    #: a check rather than weakening it, so a guard that cannot be set is not a
    #: refinement -- it is the difference between a tool that works and one that
    #: accuses ordinary numbers. (The 0.846 / 0.0000 specificity figures once
    #: quoted here were unsourced and were removed 2026-08-12.)
    guard: bool = False

    #: Deliberately NOT exposed to the model. These control how hard a tool
    #: searches (`max_iterations`, `rho_grid`); a model that can tune them can
    #: search until it gets the verdict it wants. Withheld params keep their
    #: default and never appear in the MCP schema.
    withheld: bool = False

    #: This argument's LAST PRINTED DIGIT is load-bearing. The check is exact
    #: arithmetic over the rounding interval of a printed value, so a MEASURED
    #: value -- read off a chart's marks -- has no last printed digit and the
    #: test is undefined on it. Such a call is REFUSED, not capped.
    #:
    #: Refusal rather than capping, because the arithmetic says so. A figure-read
    #: mean on a 1-7 scale at 400px carries sigma ~0.023, comparable to GRIM's
    #: entire granularity spacing at n=30 (1/30 = 0.033) and ~5x its decision
    #: window (0.005). A genuinely consistent mean perturbed that far lands back
    #: inside an admissible window only ~30% of the time -- so GRIM would falsely
    #: call it impossible about 70% of the time. Capping that to `suspicious`
    #: does not fix a 70% false-positive rate; it relabels false accusations as
    #: softer false accusations.
    exact: bool = False

    #: This argument is the PRINTED PRECISION of another argument, and the check
    #: cannot be run without it. Not the same as `exact`: `exact` marks the value
    #: being tested, `precision` marks the number of digits it was printed to,
    #: which is what sizes the rounding interval the whole test is about.
    #:
    #: Why a refusal and not a default. `grim_check.decimals` defaulted to 2 and
    #: `debit_check.decimals_mean/_sd` to 2, so a mean the paper printed "5.9"
    #: was tested as though it read "5.90" -- a rounding interval ten times too
    #: tight. MEASURED: grim_check(mean=5.9, n=12, data_type='likert') returns
    #: `impossible` on the default and `consistent` at decimals=1. Conditioned on
    #: rows that are consistent at 1 dp, the default produced a false-impossible
    #: verdict in 41.1% of GRIM rows and 73.6% of DEBIT rows.
    #:
    #: The default was not merely wrong, it was wrong in the ACCUSING direction:
    #: too many digits always shrinks the admissible set, and a smaller
    #: admissible set is what `impossible` means. So the missing value cannot be
    #: guessed -- a guess in the safe direction (re-deriving 1 dp from the float
    #: 5.9) silently hides real findings on any value printed with trailing
    #: zeros, and a guess in the unsafe direction accuses. Refuse instead.
    #:
    #: SCOPE, verified: `check_table` -> `dispatch._build_args` re-derives
    #: `decimals`/`decimals_mean`/`decimals_sd` from the cell LITERAL (via
    #: `celltypes._dp`) and passes them explicitly, so the table path never hits
    #: this gate. The exposed path is the DIRECT single-tool call -- which is the
    #: only path stage 2 has, since `check_table` is stage-1-only.
    precision: bool = False

    #: Read by `ToolSpec.call` and NEVER forwarded to the implementation. These
    #: describe the value's origin (`uncertainty`, `provenance`) rather than
    #: being an input to the arithmetic; passing one through would be a
    #: TypeError at call time.
    meta: bool = False

    @property
    def required(self) -> bool:
        return self.default is REQUIRED


#: Types a string may be coerced into. `bool` is deliberately ABSENT: Python
#: reads `bool("False")` as True, so coercing a stringified boolean would invert
#: a guard silently -- the one failure mode worse than refusing it.
_COERCIBLE = (int, float)


def _unescape_entity_args(spec: "ToolSpec", args: dict) -> dict:
    """Decode HTML/XML entities in string arguments.

    GATE 0b, beside the numeric coercion and for the same reason: a value the
    model read CORRECTLY off the page should not be lost to a transport detail.

    MEASURED 2026-08-16 across 2,706 archived tool calls: 19 `stalt_check` calls
    failed with `Could not parse threshold: '&lt;0.01'`. Verified still live
    before fixing -- `<0.01` parses, `&lt;0.01` and `&#60;0.01` do not.

    AND THE SOURCE IS NOT A MODEL ERROR. In JATS XML `<` is REQUIRED to be
    encoded as `&lt;`, so a threshold read out of publisher XML -- the format
    this pipeline prefers, because its tables are ground truth -- arrives
    escaped BY SPECIFICATION. The better our extraction gets, the more often
    this fires.

    `quotes.py` already unescapes the haystack before matching and
    `r_wrappers.py` unescapes text before statcheck, so both sides of every
    comparison are normalised the same way; doing it here closes the third gap
    rather than opening a new inconsistency.

    Only strings that actually CONTAIN an entity are touched, so an ordinary
    value passes through byte-identical.
    """
    import html as _html
    import re as _re

    if not isinstance(args, dict):
        return args
    pat = _re.compile(r"&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][A-Za-z0-9]{1,31});")
    out = dict(args)
    for k, v in args.items():
        if isinstance(v, str) and pat.search(v):
            decoded = _html.unescape(v)
            if decoded != v:
                out[k] = decoded
    return out


def _coerce_numeric_args(spec: "ToolSpec", args: dict) -> dict:
    """Read `"1"` as `1` where the parameter is declared numeric.

    MEASURED across the archived runs: 154 arguments declared `int` or `float`
    arrived from the model as strings -- 84 of them `decimals`, which is the
    PRECISION GATE, the parameter whose absence turns a check off entirely.

    None of them produced a wrong verdict: 92 raised a TypeError that
    `ToolSpec.call` converts to `indeterminate`, and the rest were refused by
    the precision gate. The cost was COVERAGE. A check that silently does not
    run is the failure this repo keeps rediscovering, and `decimals="1"` is not
    an ambiguity -- it is a serialisation slip on a value the model got right.

    DELIBERATELY STRICT, because the alternative failure is far worse than a
    refusal:
      * only `int` and `float` params are considered;
      * `bool` is never coerced (see `_COERCIBLE`);
      * a list is never flattened to a scalar -- `[0]` and `0` are different
        claims, and `check_summation` legitimately accepts a list for the same
        parameter another tool takes as a scalar;
      * an int param only accepts a string that is an EXACT integer, so "2.5"
        stays a string and meets the refusal it should;
      * anything unparseable is left untouched and meets the existing gates.
    """
    out = None
    for param in spec.params:
        if param.type not in _COERCIBLE or param.name not in args:
            continue
        value = args[param.name]
        if isinstance(value, bool) or not isinstance(value, str):
            continue
        text = value.strip()
        try:
            coerced = float(text)
        except (TypeError, ValueError):
            continue
        if param.type is int:
            if coerced != int(coerced):
                continue        # "2.5" for an int param is not a slip, it is wrong
            coerced = int(coerced)
        if out is None:
            out = dict(args)
        out[param.name] = coerced
    return out if out is not None else args


def uncoercible_numeric_args(spec: "ToolSpec", args: dict) -> list[str]:
    """Numeric params still holding a non-number after coercion.

    These must REFUSE BY NAME rather than crash. Before this, `decimals="2.5"`
    reached the arithmetic and raised `TypeError: bad operand type for unary -`
    straight out of `ToolSpec.call` -- a stack trace where a verdict belongs,
    saying nothing about which parameter was wrong or what to send instead. A
    refusal that names the parameter is actionable; a TypeError is not.
    """
    bad = []
    for param in spec.params:
        if param.type not in _COERCIBLE or param.name not in args:
            continue
        value = args[param.name]
        if value is None or isinstance(value, bool):
            continue
        if not isinstance(value, (int, float)):
            bad.append(param.name)
    return sorted(bad)


def _nonfinite_paths(value: Any, path: str = "") -> list[str]:
    """Every location inside `value` holding a NaN or an infinity.

    RECURSIVE on purpose. The batch tools take the same numbers one level down --
    `debit_check_batch(rows=[{"mean": nan, ...}])` is the identical failed
    extraction as `debit_check(mean=nan)` -- and a scalar-only scan would let the
    batch form through. That is exactly the gap the measured-value gate had (see
    `ToolSpec.call`), and repeating it here would be repeating it knowingly.

    Only floats are checked: an `int` cannot be non-finite, and a `str` is left
    alone so that a legitimate description reading "nan" is not gated. A numeric
    string spelling a non-finite value is therefore NOT caught -- reachable in
    principle through `grimu_check.reported_p`, which is declared `str`.
    """
    if isinstance(value, bool):          # bool is an int subclass; never non-finite
        return []
    if isinstance(value, float) and not math.isfinite(value):
        return [path or "<argument>"]
    out: list[str] = []
    if isinstance(value, dict):
        for k, v in value.items():
            out.extend(_nonfinite_paths(v, f"{path}.{k}" if path else str(k)))
    elif isinstance(value, (list, tuple)):
        for i, v in enumerate(value):
            out.extend(_nonfinite_paths(v, f"{path}[{i}]"))
    return out


@dataclass(frozen=True)
class ToolSpec:
    """Everything every surface needs to know about one tool."""

    name: str                          # MCP tool name
    fn: Callable                       # the validated implementation
    description: str                   # shown to the model; encodes guard guidance
    params: tuple[Param, ...]
    stages: frozenset                  # which agent stages may call it
    cli: str | None = None             # CLI command name, or None if MCP-only
    cli_required_flags: frozenset = frozenset()   # guards the CLI must expose
    reference: str = ""                # markdown body for docs/tool_reference.md
    adapter: Callable | None = None    # for the two tools whose args need shaping

    #: What KIND of claim this tool's verdict is: `absolute` (possible vs
    #: impossible, bound-free arithmetic), `probabilistic` (plausible vs highly
    #: implausible, under stated assumptions), or `descriptive` (no verdict).
    #: See EVIDENCE_* above. Every spec must declare it -- `tests/
    #: test_tool_integrity_docs.py` fails the build on an omission, because a
    #: silently-defaulted epistemic class is exactly the mislabel that lets an
    #: assumption-dependent finding be read as arithmetic fact.
    evidence: str = ""

    #: What must hold for this tool's verdict to mean what it says. For a
    #: `probabilistic` tool these are the statistical assumptions (normality of
    #: the sampling distribution of means, homoscedasticity, independence, an
    #: assumed equicorrelation); for an `absolute` tool they are the
    #: preconditions of the exactness (bounds STATED rather than assumed, printed
    #: precision known, values printed rather than read off a figure). Shown to
    #: the reader beside the finding, so a researcher can see what would
    #: invalidate it.
    assumptions: tuple[str, ...] = ()

    #: One line, plain language: what this tool decides. For the audit view.
    purpose: str = ""

    #: Does a call to this tool mean numeric content lifted off the paper
    #: reached a check?
    #:
    #: TRUE when the tool's inputs are the paper's own reported quantities --
    #: means, SDs and SEs, counts, percentages, estimates and their intervals,
    #: group sizes, p-values -- or a batch of rows of them. FALSE when the input
    #: is a file path, free text, a design declaration or a quantity we computed
    #: ourselves, and for the tools that extract, retrieve or type cells rather
    #: than check them.
    #:
    #: WHY IT IS DECLARED AND NOT INFERRED. `agent._checkable_coverage` needs
    #: this set and had no way to ask for it, so it counted the two tool shapes
    #: whose names it could pattern-match -- `*check_table` and `*_batch` -- and
    #: the report then printed "**NOTHING IN THE TABLES WAS CHECKED.**" over
    #: runs that had made a hundred per-cell checks. Nothing already in the
    #: registry implies the answer: `dispatch.DISPATCH` names only the 8 tools
    #: `check_table` ROUTES to, and `Param.exact` marks a different property
    #: (that the argument's last printed digit is load-bearing, which gates a
    #: refusal) that several cell-consuming tools have no reason to set. So it
    #: is declared per tool, beside `evidence`, and `None` means UNDECLARED:
    #: every spec must answer, and `tests/test_tool_integrity.py` fails the
    #: build on an omission -- a new tool silently defaulting to False is
    #: exactly how this counter went wrong the first time.
    consumes_table_cells: bool | None = None

    def required_params(self) -> tuple[Param, ...]:
        """Params the caller MUST supply -- the tool's minimum input set."""
        return tuple(p for p in self.params if p.required and not p.withheld)

    def optional_params(self) -> tuple[Param, ...]:
        return tuple(p for p in self.params
                     if not p.required and not p.withheld)

    def severity_ceiling(self) -> str | None:
        """The strongest verdict this tool may reach, or None if undeclared.

        NONE, NOT A DEFAULT. Failing open to `indeterminate` made an UNDECLARED
        spec indistinguishable from one declared `descriptive`, so an
        undocumented `grim_check` would have printed "this tool cannot accuse" on
        its own card -- the exact opposite of the truth, in the reader-facing
        artefact whose whole job is to say what kind of claim the tool makes. An
        absent declaration is a gap in OUR documentation and has to read as one.
        """
        return EVIDENCE_CEILING.get(self.evidence) if self.evidence else None

    def integrity_card(self) -> dict[str, Any]:
        """Everything a reader needs to audit ONE call to this tool.

        Greg, 2026-08-09: "there should be documentation for each tool, showing
        the user the minimum number of values required, the types of variables,
        and whether the results are absolute (possible vs impossible) or just
        probabilistic (plausible vs highly implausible, under certain
        assumptions)."

        DERIVED, not authored, wherever it can be: the minimum input set and the
        types come straight off `params`, so a card cannot drift from the
        signature the tool actually has. Only the epistemic class, the
        assumptions and the one-line purpose are declared, because nothing in the
        code implies them.
        """
        def _describe(p: Param) -> dict[str, Any]:
            return {
                "name": p.name,
                "type": getattr(p.type, "__name__", str(p.type)),
                "help": p.help,
                # PRECISION IS TESTED BEFORE GUARD. Every `precision` param is
                # also marked `guard`, so putting guard first made `role:
                # "precision"` unreachable on all 47 specs -- and precision is
                # the more specific fact, the one that says this argument sizes
                # the rounding interval the whole test is about.
                "role": ("precision" if p.precision else
                         "guard" if p.guard else
                         "exact_value" if p.exact else
                         "metadata" if p.meta else "value"),
            }

        # MINIMUM INPUTS INCLUDES THE PRECISION PARAMS. They carry defaults, so
        # `required_params()` alone omits them -- but `ToolSpec.call` REFUSES a
        # check whose printed precision is missing, so a card listing GRIM's
        # minimum as "mean, n" tells the reader the opposite of what the tool
        # does. That refusal is the fix for a measured 41.1% of GRIM rows and
        # 73.6% of DEBIT rows falsely reported `impossible` on a defaulted 2 dp;
        # understating the input set here would quietly invite it back.
        required = tuple(
            dict.fromkeys(self.required_params()
                          + tuple(p for p in self.params
                                  if p.precision and not p.withheld)))
        return {
            "tool": self.name,
            "purpose": self.purpose,
            "evidence": self.evidence,
            "evidence_meaning": EVIDENCE_MEANING.get(self.evidence, ""),
            "severity_ceiling": self.severity_ceiling(),
            "assumptions": list(self.assumptions),
            "minimum_inputs": [_describe(p) for p in required],
            "n_minimum_inputs": len(required),
            # Anything promoted into `required` above must not also appear here,
            # or a precision param is listed twice and reads as optional in one
            # breath and mandatory in the next.
            "optional_inputs": [_describe(p) for p in self.optional_params()
                                if p not in required],
            "guards": sorted(self.guards()),
            "precision_params": sorted(self.precision_params()),
            "exact_params": sorted(self.exact_params()),
            "stages": sorted(self.stages),
        }

    @property
    def brief(self) -> str:
        """The description's first sentence, at most 240 characters: what a
        `tool_access: mcp_brief` server sends in place of the description.
        The rest is one `describe_tool` call away."""
        import re as _re
        first = _re.split(r"(?<=[.!?])\s+", self.description.strip(), maxsplit=1)[0]
        return first if len(first) <= 240 else first[:237].rstrip() + "..."

    def schema(self) -> dict[str, Any]:
        """The MCP input schema: every non-withheld parameter.

        A param with `help` is emitted as `Annotated[type, help]`, which the SDK
        turns into that property's `description` in the JSON schema the model
        actually sees. Before this, 14 authored help strings -- "Printed decimals
        of b, read from the literal", "Describe the family you chose" -- were
        declared in this file and reached nobody: `schema()` dropped everything
        but the type. The advice existed and was invisible, which is the same
        class of defect as the six omissions this module was built to make
        unrepresentable.
        """
        return {p.name: (Annotated[p.type, p.help] if p.help else p.type)
                for p in self.params if not p.withheld}

    def guards(self) -> frozenset:
        return frozenset(p.name for p in self.params if p.guard)

    def precision_params(self) -> frozenset:
        """Params that carry another argument's printed precision."""
        return frozenset(p.name for p in self.params if p.precision)

    def withheld(self) -> frozenset:
        return frozenset(p.name for p in self.params if p.withheld)

    def exact_params(self) -> frozenset:
        """Params whose last printed digit is load-bearing."""
        return frozenset(p.name for p in self.params if p.exact)

    def is_exact_check(self) -> bool:
        return bool(self.exact_params())

    def call(self, args: dict) -> Any:
        """Invoke the implementation from an MCP argument dict.

        Withheld parameters are never read from `args` -- they keep their
        default, which is the point of withholding them.
        """
        # GATE 0 -- A NUMBER SENT AS A STRING IS STILL THAT NUMBER.
        #
        # MEASURED across the archived runs: 154 arguments declared `int` or
        # `float` arrived as strings, and 2 `decimals` arrived as a list. What
        # they cost is COVERAGE, not correctness -- 92 crashed into a TypeError
        # that this method converts to `indeterminate`, and the rest were
        # refused further down. Nothing was ever published from a malformed
        # argument.
        #
        # But a check that silently does not run is the failure this repo keeps
        # finding, and `decimals="1"` is not an ambiguity: it is a JSON
        # serialisation slip on a value the model got RIGHT. The largest single
        # offender is `decimals` at 84 calls -- the precision gate, which is
        # exactly the parameter whose absence turns a check off.
        #
        # STRICT. Only a string that parses cleanly to the declared type is
        # accepted, `bool` is never coerced (a "False" string is a trap), and a
        # list is never flattened into a scalar. Anything else keeps its
        # original value and meets the refusals below unchanged, because a
        # parameter we cannot read is precisely what those refusals are for.
        args = _unescape_entity_args(self, args)
        args = _coerce_numeric_args(self, args)
        unreadable = uncoercible_numeric_args(self, args)
        if unreadable:
            return {
                "severity": "indeterminate",
                "applicable": False,
                "consistent": False,
                "error": ("these arguments are declared numeric but did not "
                          f"arrive as numbers: {', '.join(unreadable)}"),
                "unreadable_params": unreadable,
                "explanation": (
                    "Not a statement about the paper. A value this check needs "
                    "could not be read as a number, so nothing was evaluated. "
                    'Send it as a JSON number -- 2, not "2" -- and call again.'
                ),
            }

        # GATE 1 -- NON-FINITE INPUT. First, and above every other gate, because
        # a NaN is not a fact about the paper at all: it is the signature of a
        # FAILED TABLE-CELL EXTRACTION on our side (an empty cell, an en dash, a
        # footnote marker parsed as a number). Publishing it as a verdict
        # publishes OUR bug as the author's impossibility.
        #
        # MEASURED, all reachable through the model's normal surface:
        #   check_sd_range(sd=nan, 1, 7)              -> impossible
        #   grim_percentage(percentage=nan, n=49)     -> impossible
        #   r_sprite_ground_truth(mean=nan)           -> impossible
        #   stalt_check(calculated_p=nan)             -> highly_suspicious,
        #       "~inf orders of magnitude smaller than the reported threshold"
        #   check_estimate_ci(estimate=nan)           -> suspicious,
        #       "the estimate nan lies outside its own CI"
        #   grim_check(mean=nan) / grimmer_check(mean=nan) -> ValueError
        #
        # `check_sd_range` is the clearest proof these are artefacts rather than
        # arithmetic: it prints "SD of nan exceeds maximum possible SD of 3.0000",
        # which is FALSE as arithmetic -- `nan > 3.0` is False. The sentence is
        # reachable only down an else branch that never asked.
        #
        # An infinity is the same class of failure (a divide-by-zero upstream),
        # so it is refused on the same terms rather than being reasoned about.
        nonfinite = sorted(set(_nonfinite_paths(
            {k: v for k, v in args.items() if k != "uncertainty"})))
        if nonfinite:
            return {
                "severity": "indeterminate",
                "applicable": False,
                "consistent": False,
                "error": (
                    f"{self.name} received non-finite numeric input at {nonfinite}. "
                    "Not evaluated."
                ),
                "explanation": (
                    "Not evaluated. This is a refusal, not a finding, and not a statement "
                    "about the paper. NaN and infinity are not values any paper printed -- "
                    "they are what OUR extraction produces when a cell is empty, holds a "
                    "dash or a footnote marker, or a conversion divided by zero. Re-read "
                    "the source value and call again, or report that the number could not "
                    "be extracted."
                ),
                "nonfinite_params": nonfinite,
                "methodology": "Non-finite argument gate.",
            }

        # GATE 2 -- MEASURED PROVENANCE. `check_table` already accepts this
        # string and converts it into an `uncertainty` stamp on every exact
        # param. The direct single-tool call had no equivalent, so the SAME
        # figure-read number refused through the table path and was judged
        # through the per-cell path -- and the per-cell path is the only one
        # stage 2 has. Same conversion, one place, so the two paths cannot
        # disagree. Sigma is unknown here (no geometry), so the stamp is `None`;
        # the gate below keys on PRESENCE, never on magnitude.
        uncertainty = dict(args.get("uncertainty") or {})
        if self.is_exact_check() and args.get("provenance") in UNVERIFIED_PROVENANCE:
            for name in self.exact_params():
                uncertainty.setdefault(name, None)
        # WHICH REFUSAL SENTENCE THIS EARNS. The gate is one gate -- both
        # channels are barred from exact arithmetic -- but the reason and the
        # remedy differ, and stating the measured reason over an OCR'd value is
        # a false statement in a document whose whole value is that its
        # statements can be audited. See TRANSCRIBED_PROVENANCE.
        transcribed = args.get("provenance") in TRANSCRIBED_PROVENANCE

        # THE GATE. One place, deliberately: a check implemented per-tool is
        # however many omissions waiting to happen, which is the entire lesson
        # of this file.
        #
        # `uncertainty` maps param name -> sigma in DATA UNITS, stamped by the
        # extractor that produced the value. Its PRESENCE on an exact param is
        # the refusal trigger -- there is no threshold to negotiate and nothing
        # for a model to argue its way past. A numeral printed in a figure
        # carries no sigma and passes, which is correct: it was asserted by the
        # paper.
        if uncertainty:
            # MUTABLE. `frozenset & set` is a frozenset, so the `.add` below
            # raised `AttributeError: 'frozenset' object has no attribute 'add'`
            # -- the batch branch could not have been run as written, and the
            # claim below that it WAS verified (commit 2b6b766) is therefore
            # false. What was verified is the defect, not the fix: the batch
            # branch was dead, and reaching it CRASHED the tool instead of
            # refusing. A crash is not a refusal; through MCP it surfaces as a
            # tool error, and an error on a figure-derived batch is exactly the
            # case that most needs a stated `indeterminate`.
            blocked = set(self.exact_params() & set(uncertainty))
            # A BATCH tool's exact param is the row LIST, so a stamp naming a
            # per-row field ("mean", "sd", "n") never intersects it by name and
            # the gate opened. Look inside the list: `debit_check` refuses on
            # figure-derived inputs while `debit_check_batch` took the same rows
            # through the only one of the two the model can reach over MCP.
            # Refusing the whole batch when any row is measured is the
            # conservative direction, which is the correct one here.
            for p in self.exact_params():
                v = args.get(p)
                if isinstance(v, list) and any(
                    isinstance(r, dict) and set(r) & set(uncertainty) for r in v
                ):
                    blocked.add(p)
            blocked = sorted(blocked)
            if blocked:
                if transcribed:
                    return {
                        "severity": "indeterminate",
                        "applicable": False,
                        "consistent": False,
                        "error": (
                            f"{self.name} is an exact-arithmetic check and cannot run on "
                            f"OCR-TRANSCRIBED values: {blocked}. The paper did print a last "
                            "digit here -- we just do not know that we read it correctly, "
                            "and this check's verdict turns entirely on that digit."
                        ),
                        "explanation": (
                            "Not evaluated. This is a refusal, not a weak finding, and not a "
                            "statement about the paper. An OCR error is not small noise around "
                            "the right value; it is a DIFFERENT value (48.90 read as 43.90), so "
                            "no tolerance describes it and running the check anyway would "
                            "report `impossible` against arithmetic that was fine. Confirm the "
                            "cell against the source image and re-submit it as "
                            "`provenance='printed_table'`; every check then runs normally. "
                            "That verification is the only route from an image to an "
                            "`impossible` verdict, and it is deliberately manual."
                        ),
                        "transcribed_params": blocked,
                        "methodology": (
                            "Exact-arithmetic applicability gate (machine-transcribed input)."),
                    }
                return {
                    "severity": "indeterminate",
                    "applicable": False,
                    "consistent": False,
                    "error": (
                        f"{self.name} is an exact-arithmetic check and cannot run on "
                        f"MEASURED values: {blocked}. It tests whether a number is possible "
                        "to its last printed digit, and a value read off a figure has no "
                        "last printed digit."
                    ),
                    "explanation": (
                        "Not evaluated. This is a refusal, not a weak finding, and not a "
                        "statement about the paper. Measurement noise on a figure-read value "
                        "is comparable to this check's entire decision window, so running it "
                        "would produce false accusations at a high rate rather than a "
                        "softened true one. Use a tolerance-aware check instead, or a value "
                        "the paper actually printed."
                    ),
                    "measured_params": blocked,
                    "methodology": "Exact-arithmetic applicability gate (measured input).",
                }

        # GATE 3 -- MISSING PRINTED PRECISION. See `Param.precision` for the
        # measured rates. Placed after the measured-value gate so that a
        # figure-read value is refused for the RIGHT reason: it has no printed
        # precision because it was never printed, and saying "supply decimals"
        # to a caller who cannot would be advice they can only follow by making
        # a number up.
        missing_precision = sorted(
            name for name in self.precision_params() if args.get(name) is None
        )
        if missing_precision:
            return {
                "severity": "indeterminate",
                "applicable": False,
                "consistent": False,
                "error": (
                    f"{self.name} requires the PRINTED precision of its inputs: "
                    f"{missing_precision}. Not evaluated."
                ),
                "explanation": (
                    "Not evaluated. This is a refusal, not a finding, and not a statement "
                    "about the paper. This check asks whether a value is possible to its "
                    "last printed digit, so the number of digits it was PRINTED to sets "
                    "the whole test. Assuming 2 decimals for a mean the paper printed "
                    "'5.9' shrinks its rounding interval tenfold and manufactures an "
                    "impossibility -- verified: mean 5.9 at n=12 reads `impossible` at 2 "
                    "decimals and `consistent` at 1. Read the decimals off the literal in "
                    "the paper and call again."
                ),
                "missing_precision_params": missing_precision,
                "methodology": "Printed-precision declaration gate.",
            }

        # GATE 4 -- THE VARIABLE THE PAPER DECLARED.
        #
        # A check that takes `scale_min`, `data_type` and their provenance is
        # restating properties of a variable the anatomy already recorded. The
        # TABLE path reads them off that record (dispatch._variable_kwargs ->
        # Variable.forensic_kwargs) and stamps `variable_id` on the result. The
        # MODEL path restates them freehand and ties them to nothing, so the two
        # were independent statements of one fact and never reconciled.
        #
        # Here, because this method is the one point the table dispatcher, the
        # model's MCP calls and the CLI all converge on. Reconciling in any of
        # them separately leaves the one that forgot.
        #
        # Inert unless the call names a `variable_id`: a call that mentions no
        # variable behaves exactly as before.
        _var_prov = None
        if args.get("variable_id") is not None:
            from . import declared as _declared
            _blocked = _declared.mean_is_undefined(args)
            if _blocked is not None and "mean" in {p.name for p in self.params}:
                return _blocked
            args, _var_prov = _declared.reconcile(
                {p.name for p in self.params}, args)

        if self.adapter is not None:
            return _attach_sourcing(
                _stamp_variable(self.adapter(self.fn, args), _var_prov), args)
        kwargs = {}
        # `provenance` is GATE METADATA on most tools, exactly as `uncertainty`
        # is: GATE 2 above converts it into an uncertainty stamp and the refusal
        # is decided here in the registry, not inside the check. Two tools --
        # `check_table` and `check_effect_plausibility` -- genuinely take it as
        # an argument and use it in their own reasoning, so the test is what the
        # FUNCTION accepts rather than a hardcoded list; forwarding it to the
        # other fifteen is a TypeError on every call.
        try:
            import inspect as _inspect
            accepts = set(_inspect.signature(self.fn).parameters)
            takes_kwargs = any(q.kind == q.VAR_KEYWORD
                               for q in _inspect.signature(self.fn).parameters.values())
        except (TypeError, ValueError):     # builtins and C functions
            accepts, takes_kwargs = set(), True
        for p in self.params:
            if p.withheld or p.meta or p.name == "uncertainty":
                continue
            if (p.name == "provenance" and not takes_kwargs
                    and "provenance" not in accepts):
                continue
            if p.name in args:
                kwargs[p.name] = args[p.name]
            elif not p.required:
                kwargs[p.name] = p.default
        return _attach_sourcing(
            _stamp_variable((__import__("metascience_agent.history_runtime", fromlist=["record_tool_copy"]).record_tool_copy(self.fn, kwargs) if self.name == "detect_raw_duplication" else self.fn(**kwargs)), _var_prov), args)


def _stamp_variable(result: Any, provenance: dict | None) -> Any:
    """Record which declared variable this check was run against, if any.

    Written onto the RESULT rather than kept in the arguments, because the
    argument list is what the check consumed and this is a statement about what
    it was entitled to consume. A reader tracing a granularity verdict can now
    reach the variable's family, NOIR level, discreteness and bounds from the
    finding itself, instead of matching a table row by hand.
    """
    if provenance is None or not isinstance(result, dict):
        return result
    result.setdefault("variable", provenance)
    return result


def _attach_sourcing(result: Any, args: dict) -> Any:
    """Record WHERE the caller says these values came from, on the result.

    Two rules, and they are the whole of it.

    RECORDED, NOT JUDGED. `source_quote` is authored by the model, so this
    function attaches the claim and stops. Whether the quote is actually in the
    paper is decided later by the pipeline against the real text, exactly as
    `quote_verified` and `reproduction_valid` are, because a self-assessment
    written by the party being checked is not a check. Any verdict-shaped field
    arriving in `args` is therefore STRIPPED rather than passed through: the
    tool surface is the one place a forged verdict could enter looking native.

    ABSENCE IS RECORDED TOO. A call with no quote is marked
    `source_quote_supplied: False` rather than left silent, so coverage can be
    measured. A field that is simply missing is indistinguishable from one
    nobody looked for, and that is how the earlier `quote` field went 505 calls
    without anyone noticing it was never verified.
    """
    if not isinstance(result, dict):
        return result
    for forged in ("source_quote_verified", "source_verified", "quote_verified"):
        result.pop(forged, None)
    quote = args.get("source_quote")
    locator = args.get("source_locator")
    result["source_quote"] = quote if isinstance(quote, str) and quote.strip() else None
    result["source_locator"] = (
        locator if isinstance(locator, str) and locator.strip() else None)
    result["source_quote_supplied"] = result["source_quote"] is not None
    return result


def as_mcp_content(result: Any) -> dict:
    """The uniform MCP response envelope every tool returns."""
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2, default=str)}]}


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------

from .anatomy import StatisticalTest
from .tools.r_wrappers import python_statcheck


# ---------------------------------------------------------------------------
# Adapters -- the two tools whose MCP arguments need shaping before the call
# ---------------------------------------------------------------------------

def _sd_or_se_adapter(fn, args: dict):
    """MCP schemas cannot express a tuple, so the range arrives as two scalars."""
    lo, hi = args.get("variable_range_min"), args.get("variable_range_max")
    return fn(
        reported_value=args["reported_value"],
        n=args["n"],
        reported_as=args.get("reported_as", "unknown"),
        plausible_sd_max=args.get("plausible_sd_max"),
        variable_range=(float(lo), float(hi)) if lo is not None and hi is not None else None,
        decimals=args.get("decimals"),
        bound_source=args.get("bound_source", "assumed"),
    )


def _multiplicity_adapter(fn, args: dict):
    """MCP cannot express a dataclass, so the family arrives as a list of dicts.

    Only two fields are load-bearing for the arithmetic -- `p_value` and
    `correction_applied` -- so anything else the model supplies is ignored
    rather than rejected. A test whose p_value is a THRESHOLD ("p < .05") is
    dropped, not coerced: the multiplicity arithmetic needs the reported value,
    and treating a bound as a point would silently change which results are
    counted as surviving.
    """
    raw = args.get("tests") or []
    tests: list[StatisticalTest] = []
    dropped_thresholds = 0
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        if item.get("p_is_threshold"):
            dropped_thresholds += 1
            continue
        p = item.get("p_value")
        tests.append(
            StatisticalTest(
                id=str(item.get("id") or f"t{i + 1}"),
                test_type=str(item.get("test_type") or "unspecified"),
                location=str(item.get("location") or ""),
                p_value=float(p) if isinstance(p, (int, float)) else None,
                correction_applied=item.get("correction_applied"),
            )
        )
    # NO DEFAULT FAMILY. This used to fall back to "all reported tests", which
    # is precisely the thing the tool's own description tells the model not to
    # do -- the advice and the behaviour contradicted each other, and the
    # behaviour won on every call that omitted the argument. A family is a
    # judgement no arithmetic can make, and the arithmetic is uninterpretable
    # without knowing which family it was computed over, so a missing label is
    # a refusal rather than a guess. Same shape as the exact-arithmetic gate in
    # `ToolSpec.call`: not evaluated, and not a statement about the paper.
    family_label = str(args.get("family_label") or "").strip()
    if not family_label:
        return {
            "severity": "indeterminate",
            "applicable": False,
            "error": "multiplicity_report requires `family_label`; it has no default.",
            "explanation": (
                "Not evaluated. What counts as a FAMILY of tests is a judgement the tool "
                "cannot make for you, and the same p-values give different answers under "
                "different families. Name the family you chose -- 'the nine cognitive "
                "outcomes of the 3x3 design', 'the six post-hoc contrasts within the "
                "significant omnibus F' -- and run this once per family."
            ),
            "methodology": "Multiplicity family-declaration gate.",
        }
    result = fn(
        tests,
        family_label=family_label,
        alpha=float(args.get("alpha", 0.05)),
    )
    if dropped_thresholds:
        result = dict(result)
        result["n_dropped_threshold_p"] = dropped_thresholds
        result.setdefault("caveats", []).append(
            f"{dropped_thresholds} test(s) reported p as a threshold rather than a value "
            "and were excluded; the family is that much larger than counted here."
        )
    return result


def _statcheck_adapter(fn, args: dict):
    """Two input routes. `fn` is the text route (the spec's declared primary);
    the PDF route is a fallback that extracts text first."""
    if args.get("text"):
        return fn(args["text"])
    if args.get("pdf_path"):
        return python_statcheck(args["pdf_path"])
    return {"success": False, "error": "Provide either pdf_path or text parameter"}


# ---------------------------------------------------------------------------
# The registry
# ---------------------------------------------------------------------------

# Every ToolSpec lives in its family folder, `tool_specs/<family>/spec.py`, with its
# MCP description in the TOOL.md beside it (Phase 3a of the modular refactor:
# moved verbatim). Imported HERE, after the machinery above is defined, because
# the spec modules import `Param`, `ToolSpec` and the help texts from this
# module; `tool_specs.ORDER` keeps the registry order, which role allowlists --
# and so the commands each agent is sent -- follow.
from . import tool_specs as _tool_specs  # noqa: E402

SPECS: tuple[ToolSpec, ...] = _tool_specs.load()



# ---------------------------------------------------------------------------
# What KIND of claim each tool makes, and what has to hold for it to mean that
# ---------------------------------------------------------------------------
#
# Declared HERE rather than inside each ToolSpec literal so the whole epistemic
# picture is readable in one screen and reviewable as a unit: the interesting
# question is never "what does GRIM assume" alone, it is whether the 47 answers
# are consistent with each other and with the severity ladder. Applied to the
# specs immediately below, so there is still exactly one ToolSpec per tool and
# no second source of truth -- and `tests/test_tool_integrity.py` fails the
# build if this table and SPECS ever disagree in either direction.
#
# `assumptions` are USER-FACING: what a researcher reading a finding would need
# to know could invalidate it. For a `probabilistic` tool they are the
# statistical assumptions; for an `absolute` one they are the preconditions the
# exactness rests on (bounds STATED not assumed, printed precision known, values
# printed rather than read off a figure).
TOOL_INTEGRITY: dict[str, dict] = _tool_specs.integrity()
# Each card now lives in its tool family's TOOL.md frontmatter
# (`tool_specs/<family>/TOOL.md`), one table per family; the review-as-a-unit
# property is kept by `tests/test_tool_integrity.py`, which still checks every
# card against SPECS in both directions.


# Fold the declarations above into the specs, so there is still exactly ONE
# ToolSpec per tool and `integrity_card()` reads from the same object every
# other surface does. Done here rather than inside 47 literals because the
# table is reviewable as a unit; `tests/test_tool_integrity.py` enforces that
# the two stay in step, in BOTH directions -- a spec with no entry, and an
# entry naming no spec, are each a build failure.
SPECS = tuple(
    replace(spec, **TOOL_INTEGRITY[spec.name]) if spec.name in TOOL_INTEGRITY
    else spec
    for spec in SPECS
)


# --- Where did these numbers come from? (Greg, 2026-08-09) -----------------
#
# "I would like all the tools to report the exact quote/context of the paper
# from which given values were extracted."
#
# The ledger records that grim_check was called with mean=48.90; NOTHING records
# that 48.90 was the Age row of Table 1. So a reader checking a finding has to
# go and find the value themselves, which is the thing this was meant to spare
# them, and an evaluating agent cannot tell a correctly-read value from a
# misread one at all.
#
# Declared as META params, so they are captured by `ToolSpec.call` and NEVER
# forwarded to the arithmetic -- the same mechanism `provenance` and
# `uncertainty` already use. That is what makes this ONE change rather than 37
# signature changes, and it means no check can accidentally start reasoning
# about the quote instead of the number.
#
# Added only to tools that RENDER A VERDICT about reported values. An extractor
# has no input value to source, and asking for a quote there would be noise that
# teaches the model to supply one pro forma -- the same
# teach-the-reader-to-skip-it failure the guard alarm had.
SOURCE_QUOTE_HELP = (
    "VERBATIM text from the paper containing the values you are passing -- one "
    "contiguous span, copied exactly, not reassembled. Prefer a short exact "
    "quote over a long approximate one. This is checked against the paper: a "
    "quote that cannot be located is reported as OUR search failing, but a "
    "quote you compose rather than copy is reported as composed, so copy it."
)

SOURCE_LOCATOR_HELP = (
    "Where in the paper that quote lives, in the terms a reader would use: "
    "'Table 1, Age row', 'Results, paragraph 2', 'eTable 3'. Short. This is what "
    "makes a refusal legible -- 'we could not check the Age row' beats 'we could "
    "not check cell 7'."
)

_SOURCING_PARAMS = (
    Param("source_quote", str, None, meta=True, help=SOURCE_QUOTE_HELP),
    Param("source_locator", str, None, meta=True, help=SOURCE_LOCATOR_HELP),
)

# "Descriptive" and "has no input value to source" are not the same predicate,
# and using the first as a proxy for the second left three tools unsourceable
# that are handed numbers the model transcribed off the page. An extractor is
# given a FILE PATH and produces the values everything else consumes; these are
# given the values themselves, so a reader of a finding that cites them has no
# route back to the page.
#
# `multiplicity_report` is the one that mattered in practice. MEASURED over the
# archived ledgers: 21 calls consumed 147 p-values gathered from across the
# paper, and 9 findings cite its output ("only k of n survive Holm"). Every one
# of those p-values was untraceable, and the correction verdict rests entirely
# on the model having transcribed them correctly.
_DESCRIPTIVE_BUT_CONSUMES_TRANSCRIBED_VALUES = frozenset({
    "multiplicity_report",    # p-values read from across the paper
    "r_grim_ground_truth",    # mean/n copied from a table
    "r_sprite_ground_truth",  # mean/sd/n copied from a table
    # Added 2026-08-16 with the stage offer. It is descriptive -- it judges
    # nothing -- but `effect_size` and `actual_n` are both read off the page,
    # and "this design needed 128 and had 21" is a sentence a reader will want
    # to trace. Declaring the pair inline instead would suppress the injection
    # below and hand the model two parameters with no help text.
    "required_n",             # effect_size/actual_n copied from the results
    # Added 2026-08-26 on the `required_n` precedent, which this file records
    # as an exemption that expired: a tool handed the paper's OWN numbers needs
    # a route back to the page, whatever its evidence class. `dz` (or `t` and
    # `n`) are read off the results section, and "d_av lies between 0.28 and
    # 1.19" is a sentence a reader will want to trace to the sentence that
    # reported the d_z.
    "paired_d_interval",      # dz / t / n copied from the results
})


def _needs_sourcing(spec: ToolSpec) -> bool:
    if any(p.name == "source_quote" for p in spec.params):
        return False  # already declared inline
    if spec.evidence != EVIDENCE_DESCRIPTIVE:
        return True
    return spec.name in _DESCRIPTIVE_BUT_CONSUMES_TRANSCRIBED_VALUES


SPECS = tuple(
    replace(spec, params=spec.params + _SOURCING_PARAMS) if _needs_sourcing(spec) else spec
    for spec in SPECS
)


#: Arguments that RESTATE a property of a declared variable rather than of the
#: cell. A check taking any of these is asserting something about the variable,
#: and can therefore contradict what the anatomy recorded about it.
_VARIABLE_RESTATING = frozenset({
    "scale_min", "scale_max", "data_type",
    "bound_source", "discreteness_source", "items",
})

#: GATE METADATA, not a tool argument -- same shape as `uncertainty` and
#: `provenance` above, and excluded from kwargs by the same rule.
#:
#: Added HERE rather than inline on each spec so it cannot drift: a check added
#: later that takes `scale_min` gets it automatically, and the alternative --
#: eight hand-edited literals -- is precisely how `derivation` came to be a
#: field the model answered and nothing read.
_VARIABLE_PARAM = (
    Param("variable_id", str, None, meta=True,
          help=("The `id` of the variable in the statistical anatomy that this "
                "value measures. Supply it whenever the paper declared one. It "
                "is not a substitute for the scale arguments -- the two are "
                "CHECKED AGAINST EACH OTHER, and a contradiction between them "
                "widens the scale, downgrades the provenance to `assumed` and "
                "is reported. Naming the variable is how a granularity verdict "
                "becomes traceable to the declaration that licensed it.")),
)


def _restates_a_variable(spec: ToolSpec) -> bool:
    names = {p.name for p in spec.params}
    if "variable_id" in names:
        return False                       # already declared inline
    # `mean` earns it too: the NOIR gate refuses a mean-based check on a
    # variable declared nominal, and it needs the id to find the declaration.
    return bool(names & _VARIABLE_RESTATING) or "mean" in names


SPECS = tuple(
    replace(spec, params=spec.params + _VARIABLE_PARAM)
    if _restates_a_variable(spec) else spec
    for spec in SPECS
)


BY_NAME: dict[str, ToolSpec] = {s.name: s for s in SPECS}


#: Registered tools that FETCH or PARSE rather than compute a verdict about a
#: number. A finding's `technique` can never be one of these, and a tool call to
#: one is not a check.
#:
#: ONE LIST, owned here because this module owns tool names. `values` composes
#: its own not-a-check set from this plus `Read` and `StructuredOutput`, which
#: are not registered tools.
NOT_A_TECHNIQUE = frozenset({
    "analyze_paper_images", "check_table", "extract_figures", "extract_html",
    "extract_pdf", "extract_supplement", "extract_xml", "get_supplement_table",
    "get_table", "parse_cells_as_declared", "parse_cells_typed", "parse_table",
})


def technique_names() -> tuple[str, ...]:
    """Every registered tool whose name a finding may give as its `technique`.

    THE SCHEMA AND THE PROMPT USED TO CONTRADICT EACH OTHER. The `technique`
    field's own description reads "Use the registry name of the tool that
    actually computed it" -- and the enum beside it was a hand-maintained
    PARAPHRASE of those names: `count_percent` for `check_count_percent`,
    `grim` for `grim_check`, `sprite` for `sprite_reconstruct`, `duplication`
    for `detect_duplication`. MEASURED 2026-08-20: **32 of 58 registered tools
    could not be named as a technique**, 20 of them real checks.

    A model that follows the instruction is then rejected by the validator, and
    the rejection is not partial: stage 1 emits ONE structured output, so a
    single unacceptable technique string discards the whole statistical anatomy.
    That cost the entire stage-1 output on 2 of the 11 papers in the
    cerebrolysin run -- both left with no findings and no value register at all,
    for spelling a tool's name the way the registry spells it.

    Derived, so a tool added tomorrow is nameable tomorrow. The paraphrases stay
    accepted as aliases, because archived runs used them and a schema that
    invalidates history explains nothing.
    """
    return tuple(sorted(n for n in BY_NAME if n not in NOT_A_TECHNIQUE))



def stage_tools(stage: str) -> list[str]:
    """MCP tool names a given agent stage may call, in registry order."""
    return [s.name for s in SPECS if stage in s.stages]


def cell_consuming_tools() -> frozenset[str]:
    """Tools a call to which is evidence a paper's own numbers reached a check.

    The set `agent._checkable_coverage` must consult before the report may
    print "NOTHING IN THE TABLES WAS CHECKED". ASK, do not restate: a caller
    that keeps its own copy of this list is a caller whose list falls behind
    the registry, which is precisely the defect this exists to close.
    """
    return frozenset(s.name for s in SPECS if s.consumes_table_cells)


def cli_specs() -> dict[str, ToolSpec]:
    """CLI command name -> spec, for the commands the registry expects to exist."""
    return {s.cli: s for s in SPECS if s.cli}


def cli_syntax_reference(stage: str | None = None,
                         drop: frozenset[str] | set[str] | None = None) -> str:
    """A compact CLI-name map for the model, generated from the registry.

    `stage` filters the map to one role's callable tools: an agent handed a
    map naming 54 tools when it can call 15 is being invited to recommend
    off-list calls (and the recommends-only-callable-tools tests treat the
    map as a recommendation).

    `drop` removes tools the ROLE could call but this RUN has switched off --
    today only the figure pass. Same argument one level down: a map naming a
    tool that has been removed from the allowlist invites exactly the off-list
    recommendation the `stage` filter exists to prevent.

    WHY THIS EXISTS, and why the full `tool_reference.md` should NOT be in the
    system prompt.

    Every tool was documented twice: once as its MCP definition (~7,088 tokens)
    and again in tool_reference.md (~3,885 tokens), both sent on every turn. The
    MCP description already carries the guard guidance -- `grimmer_check`'s says
    "You MUST pass data_type" and cites the systolic-BP case -- so the prose was
    genuinely redundant.

    What the MCP definitions do NOT carry is the CLI command name, and the model
    needs that to write a runnable `reproduction` string. The CLI verb often
    differs from the tool name (`grim_check` -> `grim`, `check_estimate_ci` ->
    `check-ci`), which is exactly how a real run emitted
    `metascience recalc_independent_t --mean1 ...` -- a command that does not
    exist.

    So: the mapping, and nothing else. ~600 tokens instead of ~3,885, on every
    turn of every paper.
    """
    lines = [
        "# CLI names for `reproduction` commands",
        "",
        "Every finding's `reproduction` must be a real `metascience` command that runs",
        "as written. The CLI verb is often NOT the tool name -- use this mapping.",
        "Malformed commands are detected and the finding is marked",
        '"not independently reproducible", which weakens it.',
        "",
    ]
    _drop = frozenset(drop or ())
    pool = [s for s in SPECS
            if (stage is None or stage in s.stages) and s.name not in _drop]
    for spec in sorted(pool, key=lambda s: s.name):
        if spec.cli:
            lines.append(f"  {spec.name} -> metascience {spec.cli}")
    mcp_only = sorted(s.name for s in pool if not s.cli)
    if mcp_only:
        lines += [
            "",
            "MCP-only (no CLI form). A finding resting on one of these cannot carry a",
            "runnable reproduction command; say so rather than inventing a verb:",
        ]
        lines += [f"  {n}" for n in mcp_only]
    return "\n".join(lines)


def reproduction_command(tool: str, args: dict) -> tuple[str | None, str | None]:
    """The command that re-runs this call, or why none exists.

    THE MODEL MAY NAME THE CHECK; IT MAY NOT WRITE THE COMMAND. Model-written
    commands guessed at signatures they had never been shown: 461 of 801
    archived ones (57.6%) failed validation (measured 2026-08-13).

    Since Phase 3b this is `metascience tool run <tool> --json '<args>'`, the
    generic command (`tool_cli.py`), and no longer a per-tool verb. Two things
    change, both deliberate:

      * It RUNS THROUGH `ToolSpec.call`, so a replay applies the same gates the
        model's call did. The per-tool verbs call `tools/*.py` directly and
        skip them -- `metascience grim` defaulted `decimals=2` where the MCP
        surface refuses a missing precision.
      * STRUCTURED INPUT RIDES ALONG. The per-tool generator refused any list
        or dict argument (`cells`, `rows`, `blocks`) because no flag could
        carry it -- 54.2% of calls had no command. JSON carries them.

    Refuses: an unknown tool; a tool that is not a replayable calculation
    (readers, parsers, the tracks, `run_python_script`); recorded inputs that
    lack a required argument. `source_quote`/`source_locator`/`variable_id`
    are left off: they bind a call to this run's paper and declarations, not
    to the arithmetic, and a replay is of the arithmetic.
    """
    import json as _json
    import shlex as _shlex

    spec = BY_NAME.get(tool)
    if spec is None:
        return None, f"no registered tool named {tool!r}"
    from .evaluation.deterministic import reproducible_tools
    if tool not in reproducible_tools():
        return None, (f"`{tool}` reads or transforms the paper rather than "
                      "computing a verdict, so there is no calculation to replay")
    dropped = {"source_quote", "source_locator", "variable_id"}
    known = {p.name for p in spec.params if not p.withheld and p.name not in dropped}
    clean = {k: v for k, v in (args or {}).items() if k in known}
    missing = [p.name for p in spec.required_params() if p.name not in clean]
    if missing:
        return None, (f"the recorded inputs lack required argument(s) "
                      f"{missing}; the exact inputs are on this finding")
    try:
        payload = _json.dumps(clean, sort_keys=True, separators=(",", ":"),
                              allow_nan=False)
    except (TypeError, ValueError) as exc:
        return None, f"the inputs cannot be written as JSON ({exc})"
    return f"metascience tool run {tool} --json {_shlex.quote(payload)}", None


def _shell_quote(s: str) -> str:
    """Quote only when needed, so the common case stays readable."""
    import re as _re
    return s if _re.fullmatch(r"[A-Za-z0-9_.:/=+-]+", s or "") else "'" + s.replace("'", "'\\''") + "'"
