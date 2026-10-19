"""Which check families would have every premise present, at which coordinates.

READ-ONLY, BY DESIGN. This module calls no tool and renders no verdict. It
exists to demonstrate the claim the scaffold rests on -- that once the premises
are extracted, the set of valid checks is a finite, deterministic function of
the scaffold's composition -- by computing that function and printing it: for
each check family, the coordinates where every premise is present (bindable)
and, for the rest, WHICH premise is missing. Wiring a family to its tool is the
next step and needs Greg's eye on the schema first (2026-09-05).

A PREMISE IS A KEY, NOT A GUESS. GRIM needs a mean, the per-subject step of the
variable, and the n of the group the mean describes. Here each of those is a
lookup: the mean is a value row at (study, group, phase, variable); the step is
`variables[variable].granularity.per_subject_step`; the n is a value row with
statistic `n` at (study, group). If any lookup fails, the family is blocked at
that coordinate and the missing key is named. Nothing here defaults, infers
from a label, or reads position -- which is the whole difference from the
register's `applicable_tools`, where a check that could not find its premise
would guess one and occasionally accuse an honest paper for it.
"""

from __future__ import annotations

from typing import Any

from . import premises as _premises

#: (family, the tool(s) it stands for in the registry, the premises it needs).
#: Premise names are the keys `_premises_at` resolves.
#:
#: THE TOOL NAMES ARE THE REGISTRY'S OWN, verified against `registry.BY_NAME`
#: (`tests/test_scaffold_checks.py` fails on a name that is not registered).
#: Five were stale when `checks.py` came to call them: `grim_test` is registered
#: as `grim_check`, `grimmer_test`/`sprite` as `grimmer_check` /
#: `sprite_reconstruct`, `sd_range` as `check_sd_range`, `stat_to_p` as
#: `recalc_stat_to_p`. Two name nothing at all and say so, because "no registry
#: tool takes this family's premises" is a fact a reader needs and an invented
#: name hides.
FAMILIES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("range_within_bounds", "(no registry tool)",
     ("central_value", "variable_bounds")),
    ("grim", "grim_check",
     ("mean", "per_subject_step", "group_n")),
    ("grimmer_or_sprite", "grimmer_check / sprite_reconstruct",
     ("mean", "dispersion_sd_or_sem", "per_subject_step", "variable_bounds", "group_n")),
    ("count_percent", "check_count_percent",
     ("percentage", "group_n")),
    ("sd_or_se_plausibility", "check_sd_or_se / check_sd_range",
     ("mean", "dispersion_sd_or_sem", "variable_bounds", "group_n")),
    ("statistic_to_p", "statcheck / recalc_stat_to_p",
     ("test_statistic", "df", "exact_p")),
    ("claim_vs_result", "(no registry tool)",
     ("claim_linked_to_comparison", "comparison_significance", "declared_alpha")),
)


def _index(account: dict) -> dict[str, Any]:
    values = account.get("values", [])
    by_coord: dict[tuple, dict[str, list[dict]]] = {}
    group_n: dict[tuple, list[dict]] = {}
    for v in values:
        # A value whose provenance premise refuses is admitted to no check, so
        # it is not bindable either. THE RULE IS `premises.provenance`, READ
        # RATHER THAN RESTATED: this census used to test `printed_in_quote is
        # False` on its own, which admitted a prose value whose reading never
        # WROTE the field, and disagreed with the bridge about which values
        # exist -- two derivations of one fact, which `census_vs_bridge` then
        # had to reconcile.
        if _premises.provenance(v)[0] is None:
            continue
        c = v.get("coordinate") or {}
        key = (c.get("study_id"), c.get("group_id"), c.get("phase_id"), v.get("variable_id"))
        by_coord.setdefault(key, {}).setdefault(v["statistic"], []).append(v)
        if v["statistic"] == "n" and v.get("numeric") is not None and c.get("study_id"):
            # A study-level n counts for every group ONLY when the sentence says
            # it applies to all of them (`n = 7` for a whole panel); an n with no
            # group and no such statement binds to nothing.
            if c.get("group_id") or v.get("applies_to_all_groups"):
                group_n.setdefault((c.get("study_id"), c.get("group_id")), []).append(v)
    variables = {v["id"]: v for v in account.get("variables", [])}
    return {"by_coord": by_coord, "group_n": group_n, "variables": variables}


def _premises_at(coord: tuple, stats: dict[str, list[dict]], idx: dict) -> dict[str, bool]:
    study, group, phase, vid = coord
    var = idx["variables"].get(vid) or {}
    bounds = var.get("bounds") or {}
    gran = var.get("granularity") or {}
    has_group_n = bool(idx["group_n"].get((study, group))) or bool(idx["group_n"].get((study, None)))
    return {
        "central_value": any(s in stats for s in ("mean", "median", "percentage", "min", "max")),
        "mean": "mean" in stats,
        "percentage": "percentage" in stats,
        "dispersion_sd_or_sem": ("sd" in stats) or ("sem" in stats),
        "variable_bounds": (bounds.get("source") in ("stated", "definitional")
                            and (bounds.get("lower") is not None or bounds.get("upper") is not None)),
        "per_subject_step": gran.get("per_subject_step") is not None,
        "group_n": has_group_n,
    }


def census(account: dict) -> dict[str, Any]:
    """Per family: bindable coordinates, and blocked coordinates by missing premise."""
    idx = _index(account)
    out: dict[str, Any] = {"families": [], "note": (
        "read-only enumeration; no tool was called. `bindable` counts coordinates "
        "where every premise the family needs is a present key in the scaffold; "
        "`blocked_by` names the first missing premise at each other coordinate "
        "that has the family's primary statistic.")}
    coord_families = [f for f in FAMILIES if f[0] not in ("statistic_to_p", "claim_vs_result")]
    for fam, tools, needs in coord_families:
        primary = needs[0]
        bindable: list[dict] = []
        blocked: dict[str, int] = {}
        for coord, stats in idx["by_coord"].items():
            have = _premises_at(coord, stats, idx)
            if not have.get(primary):
                continue
            missing = [p for p in needs if not have.get(p)]
            row = {"study_id": coord[0], "group_id": coord[1], "phase_id": coord[2],
                   "variable_id": coord[3]}
            if not missing:
                bindable.append(row)
            else:
                blocked[missing[0]] = blocked.get(missing[0], 0) + 1
        out["families"].append({"family": fam, "tools": tools, "premises": list(needs),
                                "n_candidate_coordinates": len(bindable) + sum(blocked.values()),
                                "n_bindable": len(bindable), "bindable": bindable,
                                "blocked_by": blocked})
    # Comparison-level families.
    cmps = account.get("comparisons", [])
    stp = [c for c in cmps if c.get("statistic_printed") and c.get("df_printed") and c.get("p_printed")]
    blocked_stp: dict[str, int] = {}
    for c in cmps:
        if not c.get("statistic_printed"):
            blocked_stp["test_statistic"] = blocked_stp.get("test_statistic", 0) + 1
        elif not c.get("df_printed"):
            blocked_stp["df"] = blocked_stp.get("df", 0) + 1
        elif not c.get("p_printed"):
            blocked_stp["exact_p"] = blocked_stp.get("exact_p", 0) + 1
    out["families"].append({"family": "statistic_to_p", "tools": "statcheck / stat_to_p",
                            "premises": ["test_statistic", "df", "exact_p"],
                            "n_candidate_coordinates": len(cmps), "n_bindable": len(stp),
                            "bindable": [{"comparison_id": c["id"]} for c in stp],
                            "blocked_by": blocked_stp})
    alpha = (account.get("statistical_analysis") or {}).get("alpha_declared")
    claims = account.get("claims", [])
    cmp_by_study: dict[str, list[dict]] = {}
    for c in cmps:
        cmp_by_study.setdefault(c.get("study_id"), []).append(c)
    bindable_claims = []
    blocked_cl: dict[str, int] = {}
    for cl in claims:
        linked = [c for sid in cl.get("study_ids", []) for c in cmp_by_study.get(sid, [])]
        if not linked:
            blocked_cl["claim_linked_to_comparison"] = blocked_cl.get("claim_linked_to_comparison", 0) + 1
            continue
        if not any(c.get("significance") not in (None, "not_reported") for c in linked):
            blocked_cl["comparison_significance"] = blocked_cl.get("comparison_significance", 0) + 1
            continue
        if alpha is None:
            blocked_cl["declared_alpha"] = blocked_cl.get("declared_alpha", 0) + 1
            continue
        bindable_claims.append({"claim_id": cl["id"]})
    out["families"].append({"family": "claim_vs_result", "tools": "check_claim_vs_result",
                            "premises": ["claim_linked_to_comparison", "comparison_significance",
                                         "declared_alpha"],
                            "n_candidate_coordinates": len(claims),
                            "n_bindable": len(bindable_claims), "bindable": bindable_claims,
                            "blocked_by": blocked_cl})
    out["n_bindable_total"] = sum(f["n_bindable"] for f in out["families"])
    return out


def render_markdown(cen: dict) -> str:
    lines = ["| family | tools | candidates | bindable | blocked by (first missing premise) |",
             "|---|---|---:|---:|---|"]
    for f in cen["families"]:
        blocked = ", ".join(f"{k}: {v}" for k, v in sorted(f["blocked_by"].items(), key=lambda kv: -kv[1])) or "--"
        lines.append(f"| {f['family']} | {f['tools']} | {f['n_candidate_coordinates']} | "
                     f"{f['n_bindable']} | {blocked} |")
    lines.append("")
    lines.append(f"Total bindable check coordinates: {cen['n_bindable_total']}. {cen['note']}")
    return "\n".join(lines)
