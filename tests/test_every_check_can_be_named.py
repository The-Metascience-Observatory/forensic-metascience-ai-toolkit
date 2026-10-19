"""A tool the model can RUN must be a technique a finding can NAME.

FOUND 2026-08-20, in a paid eleven-paper run. On
`10.1111--j.1747-4949.2012.00901.x` stage 1 returned no findings JSON at all --
its last output was prose:

    The schema's `technique` enum has no value for `check_count_percent` (a
    registered tool that is missing from the enum) and uses `duplication`
    rather than `detect_duplication`.

The model was RIGHT on the first count, and rather than emit a finding it could
not label, it explained the problem. That explanation replaced the JSON, so the
whole stage-1 output was lost: no findings.json, no anatomy, and therefore no
value register for that paper -- unrepairable after the fact, because there are
no declared variables to bind values to.

`test_tool_surface_is_declared` already checks every tool can be CALLED. Nothing
checked that a tool's result could be REPORTED. A check the model may run and
may not name is a check whose findings have nowhere to go.

The enum is a vocabulary of TECHNIQUES, not of tool names, so several tools map
onto one value and some tools are not techniques at all. Both are fine -- but
they have to be declared, because a deliberate omission and a forgotten one look
identical in the source. That is the same argument `CLI_ONLY` makes one file
over.
"""
import json
from pathlib import Path

from forensic_metascience_ai_toolkit import registry

SCHEMA = (Path(__file__).resolve().parents[1] / "src" / "forensic_metascience_ai_toolkit"
          / "schema" / "findings.v2.schema.json")

#: Tools that produce no finding of their own. They fetch, parse or dispatch;
#: whatever they feed reports under its own technique.
NOT_A_TECHNIQUE = {
    "analyze_paper_images": "produces panels for image_duplication to judge",
    "extract_figures": "extraction",
    "extract_html": "extraction",
    "extract_pdf": "extraction",
    "extract_supplement": "extraction",
    "extract_xml": "extraction",
    "get_supplement_table": "extraction",
    "get_table": "extraction",
    "parse_cells_as_declared": "typing, not checking",
    "parse_cells_typed": "typing, not checking",
    "parse_table": "typing, not checking",
    "check_table": "a dispatcher: every check it runs reports under its own name",
    "list_tables": "the harness GRIM sweep's table index; a reader",
    "declare_table": (
        "a declaration for the harness GRIM sweep; the HARNESS files its "
        "failures under grim_check / grim_percentage "
        "(registry.HARNESS_FILED_TOOLS)"),
    "run_python_script": (
        "sandboxed script execution (science agent); a script-computed number "
        "is provenance (`computed_by: agent_code`), not a technique -- the "
        "finding names the check the script performed, or a v2 non-tool "
        "technique"),
    "check_flow_arithmetic": (
        "SCIENCE_AGENT/adjudicator tool; it is in the findings-v2 technique "
        "enum (registry-derived) and cannot appear in a v1 (legacy-pipeline) "
        "finding because no legacy stage may call it"),
    "required_n": "a power calculator; it answers a question, it does not find a defect",
    "paired_d_interval": (
        "reports the attainable RANGE of a within-subjects d_av when the "
        "correlation is unreported. Descriptive by class and capped at "
        "`indeterminate`: a wide interval is a fact about the reporting, so "
        "there is no defect for a finding to name. What it feeds -- an effect "
        "size compared against a literature -- reports under its own technique"),
}

#: A tool whose name differs from the technique it reports under.
REPORTS_AS = {
    "csf_test": "csf",
    "sprite_reconstruct": "sprite",
    "recalc_stat_to_p": "statcheck",
    "check_count_percent": "count_percent",
    "check_statistic_bounds": "statistic_bounds",
    "check_regression_batch": "check_regression",
    "check_summation_batch": "check_summation",
    "debit_check_batch": "debit",
    "r_grim_ground_truth": "grim",
    "r_sprite_ground_truth": "sprite",
}


def _enum():
    """The LOADED v2 enum, not the file's.

    `findings.v2.schema.json` ships the literal placeholder
    `__TECHNIQUE_ENUM_INJECTED_AT_LOAD__`; `prompts.findings_schema_v2()`
    replaces it with every `registry.SPECS` name at load time (CLAUDE.md,
    wiring-checklist step 4). Reading the FILE therefore sees one fake value
    and reports every real tool as unnameable -- the opposite of the truth.
    """
    from forensic_metascience_ai_toolkit.core import prompts
    s = prompts.findings_schema_v2()

    def owner(node):
        if isinstance(node, dict):
            p = node.get("properties") or {}
            if "technique" in p and "enum" in p["technique"]:
                return p["technique"]["enum"]
            for v in node.values():
                r = owner(v)
                if r: return r
        elif isinstance(node, list):
            for v in node:
                r = owner(v)
                if r: return r
        return None

    e = owner(s)
    assert e, "findings.schema.json no longer declares a technique enum"
    return set(e)


def _technique_of(name, enum):
    """IDENTITY FIRST, since v2. The v2 enum is injected from `registry.SPECS`,
    so a tool's technique IS its registry name; `REPORTS_AS` is a v1 remnant
    mapping tool names onto the paraphrases that schema used
    (`check_count_percent` -> `count_percent`). Consulting it first returns a
    v1 paraphrase that the v2 enum does not contain, and reports a perfectly
    nameable tool as unnameable."""
    if name in NOT_A_TECHNIQUE:
        return None
    if name in enum:
        return name
    if name in REPORTS_AS:
        return REPORTS_AS[name]
    for cand in (name, name.replace("check_", ""), name.replace("detect_", ""),
                 name.replace("_check", ""), name.replace("recalc_", "")):
        if cand in enum:
            return cand
    return "MISSING"


class TestEveryCheckCanBeNamed:
    def test_no_tool_is_unnameable(self):
        """v2 ENUM, AND EXTRACTION TOOLS ARE EXEMPT BY DESIGN. CLAUDE.md: they
        "return extraction data rather than a `severity`, and are absent from
        the `technique` enum". Their absence is a decision, and counting it as
        a defect is the same error as missing a real one."""
        enum = _enum()
        exempt = {n for n in (s.name for s in registry.SPECS)
                  if n.startswith(("extract_", "parse_", "get_"))
                  or n == "run_python_script"}
        stranded = sorted(n for n in (s.name for s in registry.SPECS)
                          if n not in exempt and _technique_of(n, enum) == "MISSING")
        assert not stranded, (
            "these tools can be RUN but a finding cannot say which technique it "
            f"used: {stranded}. Add a value to the schema's `technique` enum, "
            "map it in REPORTS_AS, or declare it in NOT_A_TECHNIQUE with the "
            "reason. A model that cannot label a finding may emit prose instead "
            "of JSON, and the whole stage is then lost.")

    def test_the_one_that_cost_a_run_is_nameable(self):
        assert _technique_of("check_count_percent", _enum()) in _enum()

    def test_every_mapping_points_at_a_real_enum_value(self):
        enum = _enum()
        # Only the mappings still REACHED matter: identity wins first now, so a
        # v1 paraphrase for a tool the v2 enum names directly is dead weight,
        # not a broken pointer.
        reached = {k: v for k, v in REPORTS_AS.items() if k not in enum}
        bad = {k: v for k, v in reached.items() if v not in enum}
        assert not bad, f"REPORTS_AS points at values the schema does not offer: {bad}"

    def test_every_declaration_names_a_real_tool(self):
        names = {s.name for s in registry.SPECS}
        gone = sorted((set(NOT_A_TECHNIQUE) | set(REPORTS_AS)) - names)
        assert not gone, f"declared here but no longer a registered tool: {gone}"

    def test_exclusions_carry_a_reason(self):
        empty = [k for k, v in NOT_A_TECHNIQUE.items() if not str(v).strip()]
        assert not empty, f"NOT_A_TECHNIQUE entries with no stated reason: {empty}"
