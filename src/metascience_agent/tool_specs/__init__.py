"""Tool definitions, one folder per family (Phase 3a of the modular refactor).

`tool_specs/<family>/` holds a family's agent-facing definition:

- `spec.py`: each tool's `ToolSpec` (typed parameters, guards, roles, CLI name),
  moved verbatim from registry.py;
- `TOOL.md`: each tool's MCP description, which is exactly what the model is
  shown, plus its integrity card (evidence class, purpose and assumptions) as
  frontmatter.

The pure functions stay in `tools/*.py`, where ~120 call sites import them;
a folder is named after the implementation module it defines (`tool_specs/grim/`
-> `tools/grim.py`), with grouped folders for readers, cell parsers and tracks.

`registry.py` keeps the machinery (`Param`, `ToolSpec`, the gates) and loads
the specs from here, in `ORDER`. Order is part of the contract: role allowlists,
and therefore the commands each agent is sent, follow it. `registry_snapshot.json`
and `tests/test_pipeline_parity.py` pin both the content and the order.

Spec modules import machinery from the partially initialised `registry`
(this package is loaded from inside it, after the machinery is defined).
Import `registry` first; never import a spec module on its own.
"""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import yaml

#: Registry order of every tool (the order `registry.SPECS` had before Phase 3a).
ORDER: tuple[str, ...] = (
    "check_table", "check_effect_plausibility", "paired_d_interval",
    "extract_figures", "absence_of_evidence", "bayesian_table1_dispersion",
    "check_variance_dispersion", "check_estimate_ci", "check_proportion_from_normal",
    "check_regression", "check_sd_or_se", "check_sd_range",
    "check_summation", "check_flow_arithmetic", "run_python_script",
    "check_ratio", "check_regression_batch", "check_summation_batch",
    "multiplicity_report", "csf_test", "debit_check",
    "debit_check_batch", "detect_duplication", "detect_raw_duplication",
    "analyze_paper_images", "detect_tortured_phrases", "extract_pdf",
    "extract_xml", "get_table", "extract_html",
    "extract_supplement", "effect_size_from_f", "recalc_stat_to_p",
    "check_statistic_bounds", "check_count_percent", "get_supplement_table",
    "flag_round_n", "flag_uninformative_stat", "grim_check",
    "grim_percentage", "grim_sweep", "grimmer_check",
    "grimu_check", "grimu_coexistence", "parse_cells_typed",
    "parse_cells_as_declared", "parse_table", "r_grim_ground_truth",
    "r_sprite_ground_truth", "recalc_anova", "recalc_chi_squared",
    "recalc_f_to_p", "recalc_independent_t", "recalc_within_subjects_t",
    "reconstruct_2x2", "required_n", "rivets_anova",
    "rivets_independent_t", "sprite_reconstruct", "stalt_check",
    "statcheck", "verify_power_analysis", "list_tables", "declare_table",
)

#: The family folders.
FAMILIES: tuple[str, ...] = (
    "check_table", "effect_size", "readers", "estimates",
    "table1_dispersion", "variance_dispersion", "continuous_to_categorical", "regression",
    "se_sd", "sd_checks", "summation", "flow",
    "run_script", "ratio", "multiplicity", "csf",
    "debit", "duplication", "raw_duplication", "tracks",
    "effect_size_from_f", "stat_to_p", "bounds", "count_percent",
    "heuristics", "grim", "grimu", "cells",
    "r_wrappers", "anova", "chi_squared", "ttest",
    "power_check", "rivets", "sprite", "stalt", "grim_harness",
)

_DESCRIPTION = re.compile(r"<!-- description:(\w+) -->\n(.*?)\n<!-- /description:\1 -->", re.S)


def _tool_md(folder: Path) -> tuple[dict, str]:
    text = (folder / "TOOL.md").read_text(encoding="utf-8")
    _, front, body = text.split("---\n", 2)
    return yaml.safe_load(front) or {}, body


def descriptions(spec_file: str) -> dict[str, str]:
    """{tool: MCP description} from the TOOL.md beside `spec_file`, verbatim."""
    _, body = _tool_md(Path(spec_file).resolve().parent)
    return {m.group(1): m.group(2) for m in _DESCRIPTION.finditer(body)}


def load() -> tuple:
    """Every family's ToolSpecs, in ORDER. A tool missing from ORDER, or an
    ORDER entry no family defines, is an error -- never a silent drop."""
    by_name = {}
    for family in FAMILIES:
        module = importlib.import_module(f"{__name__}.{family}.spec")
        for spec in module.SPECS:
            if spec.name in by_name:
                raise ValueError(f"tool {spec.name!r} defined twice")
            by_name[spec.name] = spec
    if set(by_name) != set(ORDER):
        raise ValueError(
            f"tool_specs and ORDER disagree: missing from ORDER "
            f"{sorted(set(by_name) - set(ORDER))}, undefined "
            f"{sorted(set(ORDER) - set(by_name))}")
    return tuple(by_name[name] for name in ORDER)


def integrity() -> dict[str, dict]:
    """{tool: integrity card} from every TOOL.md frontmatter, in ORDER."""
    cards = {}
    for family in FAMILIES:
        front, _ = _tool_md(Path(__file__).resolve().parent / family)
        for name, card in (front.get("tools") or {}).items():
            if card is not None:
                cards[name] = {k: (tuple(v) if isinstance(v, list) else v)
                               for k, v in card.items()}
    return {name: cards[name] for name in ORDER if name in cards}


def family_of() -> dict[str, str]:
    """{tool: the family folder that defines it}, read from each TOOL.md."""
    out = {}
    for family in FAMILIES:
        front, _ = _tool_md(Path(__file__).resolve().parent / family)
        for name in front.get("tools") or {}:
            out[name] = family
    return out


def guidance_for(name: str) -> list[str]:
    """The tools agent's procedure guidance that names `name` (filled in by the
    guidance relocation; empty until a TOOL.md carries any)."""
    return [text for _, text, tools in guidance() if name in tools]


_GUIDANCE = re.compile(r"<!-- guidance:(\d+) -->\n(.*?)\n<!-- /guidance:\1 -->", re.S)


def guidance() -> list[tuple[int, str, frozenset]]:
    """Every `<!-- guidance:NN -->` block across the TOOL.md files, in order:
    (order, text, registry tools the block names anywhere).

    These are the bullets of the tools agent's procedure step 3, which live
    beside the tool they are about and are assembled back into
    `tool_expert.md` (`prompts.tool_expert_body`) byte for byte. A duplicate
    or missing number is an error: the order IS the prompt."""
    known = set(ORDER)
    blocks = []
    for family in FAMILIES:
        _, body = _tool_md(Path(__file__).resolve().parent / family)
        for m in _GUIDANCE.finditer(body):
            names = frozenset(n for n in re.findall(r"`(\w+)`", m.group(2)) if n in known)
            blocks.append((int(m.group(1)), m.group(2), names))
    blocks.sort(key=lambda b: b[0])
    numbers = [b[0] for b in blocks]
    if numbers != list(range(1, len(numbers) + 1)):
        raise ValueError(f"tool guidance blocks are not numbered 1..n: {numbers}")
    return blocks
