"""The deterministic p-tool benchmark (benchmarks/pvalue_tools) as a regression gate.

Rescoring the human-labelled cases takes seconds and costs nothing, so every
change to the p arithmetic is held to the pinned scorecard here:

  * no labelled error the pinned scorecard caught may be lost, per tool and per
    group (all / source / stratum) -- a gain in one stratum cannot hide a loss
    in another;
  * no group may gain false flags on labelled-correct statistics.

An improvement is recorded by re-running `score.py` and committing the new
`scorecard.json` deliberately, with the CHANGELOG saying what moved. Writing a
worse scorecard to make this test pass would turn the gate into a mirror (the
same rule as the parity oracles).
"""

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "pvalue_tools"


def _score():
    import importlib.util
    spec = importlib.util.spec_from_file_location("pvalue_tools_score", BENCH / "score.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def scored():
    mod = _score()
    cases = mod.load_cases(BENCH / "cases.jsonl")
    results = {"recalc_stat_to_p": mod.run_recalc(cases)}
    try:
        import statcheck  # noqa: F401
        results["statcheck"] = mod.run_statcheck(cases)
    except ImportError:
        pass
    return mod.scorecard(cases, results)


@pytest.fixture(scope="module")
def pinned():
    return json.loads((BENCH / "scorecard.json").read_text())


@pytest.mark.parametrize("tool", ["recalc_stat_to_p", "statcheck"])
def test_no_pinned_catch_is_lost(scored, pinned, tool):
    if tool not in scored["tools"]:
        pytest.skip("statcheck not installed")
    lost = {}
    for group, g in pinned["tools"][tool].items():
        now = set(scored["tools"][tool].get(group, {}).get("caught", []))
        missing = sorted(set(g["caught"]) - now)
        if missing:
            lost[group] = missing
    assert not lost, f"{tool} no longer catches labelled errors: {lost}"


@pytest.mark.parametrize("tool", ["recalc_stat_to_p", "statcheck"])
def test_no_group_gains_false_flags(scored, pinned, tool):
    if tool not in scored["tools"]:
        pytest.skip("statcheck not installed")
    worse = {}
    for group, g in pinned["tools"][tool].items():
        now = scored["tools"][tool].get(group, {}).get("false_flags", [])
        if len(now) > len(g["false_flags"]):
            worse[group] = sorted(set(now) - set(g["false_flags"]))
    assert not worse, f"{tool} flags more labelled-correct statistics: {worse}"


def test_cases_are_the_built_ones():
    """cases.jsonl is generated; every case carries what the scorer needs."""
    cases = _score().load_cases(BENCH / "cases.jsonl")
    assert len({c["id"] for c in cases}) == len(cases)
    for c in cases:
        assert c["label"] in ("error", "correct"), c["id"]
        assert c["kind"] in ("t", "f", "chi2", "r", "z"), c["id"]
        assert c["p_relation"] in ("<", ">", "="), c["id"]
    sources = {c["source"] for c in cases}
    assert {"wicherts2011", "garcia2004", "nuijten2017", "corpus"} <= sources
    # The evaluation set is held out for the paid A/B: no corpus case from it.
    assert all(c.get("split") == "working_set" for c in cases if c["source"] == "corpus")
