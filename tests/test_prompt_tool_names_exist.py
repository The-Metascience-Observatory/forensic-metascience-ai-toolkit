"""A tool name in a prompt that is one word off a real tool.

THE DRIFT CLASS. The prompts are prose and the registry is code, so a rename
lands in one and not the other; the model then writes a `technique` string the
schema rejects, discarding the finding and sometimes the whole stage.
`prompts.findings_schema_v2()`'s docstring records this costing 2 of 11 papers
their entire output.

FOUND BY AUDIT, 2026-08-29, in `rulebook.md` -- which `rulebook_roles.md` binds
to EVERY live agent:

    `recalc_chi2_to_p`   -> no such tool (real: recalc_stat_to_p)
    `table1_dispersion`  -> no such tool (real: bayesian_table1_dispersion)

WHAT THIS CATCHES, AND WHAT IT DELIBERATELY DOES NOT. It catches the first
shape: a token with the same number of segments as a real tool, matching in all
but one position (`recalc_[chi2]_to_p` against `recalc_[stat]_to_p`). At least
two segments must match positionally, because on a two-segment token "one
position differs" is half the name and fires on every unrelated pair --
measured: `cross_check`/`grim_check`, `actual_n`/`required_n`,
`printed_table`/`check_table`, all legitimate non-tool vocabulary.

It does NOT catch the second shape -- a token that is a real tool minus one
leading segment -- and that is a decision, not an oversight. `table1_dispersion`
inside `bayesian_table1_dispersion` is structurally IDENTICAL to
`tortured_phrases` inside `detect_tortured_phrases` and `estimate_ci` inside
`check_estimate_ci`, which are a technique value and a cell kind, correctly
named. No rule over token shape separates the bug from the convention, so
attempting it buys false positives in a guard whose whole value is that a
failure means something. The honest statement is that this test halves the
class rather than closing it.

A first cut used shared PREFIXES instead, which produced five false positives
(schema fields, payload keys, a statistic) AND missed `table1_dispersion`
entirely, since that shares no prefix with anything. Prefix was the wrong
signal; recorded so nobody tries it again.
"""
from __future__ import annotations

import pathlib
import re

import pytest

#: Positional matches required before "one segment differs" means anything.
_MIN_SHARED_SEGMENTS = 2


def _registered() -> set[str]:
    from metascience_agent import registry
    return {s.name for s in registry.SPECS}


def near_misses(token: str, names: set[str]) -> list[str]:
    """Registered names differing from `token` in exactly one segment."""
    t = token.split("_")
    if len(t) < _MIN_SHARED_SEGMENTS + 1:
        return []
    out = []
    for n in names:
        r = n.split("_")
        if len(t) != len(r):
            continue
        same = sum(a == b for a, b in zip(t, r))
        if same == len(t) - 1 and same >= _MIN_SHARED_SEGMENTS:
            out.append(n)
    return sorted(out)


def suspects(text: str, names: set[str]) -> dict[str, list[str]]:
    found = {}
    for tok in set(re.findall(r"`([a-z][a-z0-9_]{3,})`", text)):
        if tok in names:
            continue
        near = near_misses(tok, names)
        if near:
            found[tok] = near
    return found


#: The prompts, plus the human tool reference in `docs/` -- sent to no model,
#: but a renamed tool rots it exactly the same way.
_DOC_REFERENCE = pathlib.Path(__file__).resolve().parents[1] / "docs" / "tool_reference.md"


@pytest.mark.parametrize("path", [*__import__("metascience_agent.core.prompts", fromlist=["x"]).prompt_files(), _DOC_REFERENCE], ids=lambda p: p.name)
def test_no_prompt_names_a_tool_one_word_off_a_real_one(path):
    found = suspects(path.read_text(encoding="utf-8"), _registered())
    assert not found, (
        f"{path.name} names tokens one segment away from a registered tool, "
        f"which is the signature of a rename that did not reach the prompt: "
        + "; ".join(f"{k} -> did you mean {v}?" for k, v in sorted(found.items())))


class TestTheGuardCanFire:
    """A ratchet that cannot fire is one that passed for the wrong reason."""

    def test_it_catches_the_defect_it_was_built_for(self):
        assert "recalc_stat_to_p" in near_misses("recalc_chi2_to_p", _registered())

    def test_it_does_not_fire_on_fields_keys_kinds_or_statistics(self):
        names = _registered()
        for benign in ("effect_size", "effect_size_estimated", "checks_passed",
                       "checks_refused_indeterminate", "r_squared", "col_label",
                       "provenance_quote", "cross_check", "actual_n",
                       "printed_table", "estimate_ci", "tortured_phrases",
                       "image_duplication"):
            assert not near_misses(benign, names), benign

    def test_the_limit_is_real_and_recorded(self):
        """`table1_dispersion` is NOT caught. Pinned so that a later reader
        finds the reason here rather than assuming the guard is complete."""
        assert not near_misses("table1_dispersion", _registered())
