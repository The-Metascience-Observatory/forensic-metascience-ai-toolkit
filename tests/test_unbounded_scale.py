"""A check may not invent a scale it was not given.

Found by reading a real run through the bundle viewer. The paper reported
"Number of coalition members: 35.78 (33.74)" at n=64, declared `count` with no
stated bounds. check_table returned `impossible`:

  sprite_reconstruct: "The implied total 2290 lies outside the attainable range
  [64, 448] for n=64 on scale [1, 7]."

There is no 1-7 scale anywhere in that paper. `sprite_reconstruct` and
`grimmer_test` both default to scale_min=1, scale_max=7 -- a Likert scale
applied to whatever they are handed. A coalition of 35.78 members averaged over
64 coalitions is perfectly ordinary: 2290/64 = 35.78125, which rounds to 35.78.

`grim_check` got the same cell right (`suspicious`), because it caps severity
when `bound_source` is assumed. The other two have no such cap.
"""
import pytest

from metascience_agent.dispatch import UNBOUNDED_REASON, check_table

LABEL = "Number of coalition members"


def _run(variable):
    return check_table(
        cells=[{"raw": "35.78 (33.74)", "row_label": LABEL, "n": 64}],
        variables=[variable],
        bindings={LABEL: variable["id"]},
        provenance="printed_table",
    )


def _ran(result):
    return {r["tool"] for r in result.get("results", [])}


def _refused(result):
    return {t for e in result.get("not_run", []) for t in (e.get("tools") or [])}


class TestUnboundedCountIsNotAccused:
    def test_the_reported_false_accusation(self):
        r = _run({"id": "m", "name": LABEL, "family": "count"})
        assert r["severity"] != "impossible"

    def test_the_bounded_checks_are_refused_not_run(self):
        r = _run({"id": "m", "name": LABEL, "family": "count"})
        assert {"sprite_reconstruct", "grimmer_check"} <= _refused(r)
        assert "sprite_reconstruct" not in _ran(r)

    def test_the_refusal_says_why(self):
        r = _run({"id": "m", "name": LABEL, "family": "count"})
        reasons = " ".join(e.get("reason", "") for e in r.get("not_run", []))
        assert "STATED scale maximum" in reasons
        assert "1-7" in UNBOUNDED_REASON

    def test_grim_still_runs_since_it_needs_no_upper_bound(self):
        """GRIM needs only mean, n and decimals -- refusing it would lose real
        coverage, and it already caps itself under an assumed bound."""
        r = _run({"id": "m", "name": LABEL, "family": "count"})
        assert "grim_check" in _ran(r)


class TestStatedBoundsStillWork:
    def test_a_stated_bound_lets_the_checks_run(self):
        r = _run({"id": "m", "name": LABEL, "family": "count",
                  "lower_bound": 0, "upper_bound": 500})
        assert not _refused(r) & {"sprite_reconstruct", "grimmer_check"}

    def test_and_the_value_passes_on_a_real_scale(self):
        r = _run({"id": "m", "name": LABEL, "family": "count",
                  "lower_bound": 0, "upper_bound": 500})
        assert r["severity"] == "consistent"

    def test_a_genuine_impossibility_is_still_caught(self):
        """The fix must be "stop inventing bounds", not "stop checking".

        On a REAL 1-7 scale, a mean of 35.78 is genuinely impossible, and the
        check still RUNS and still FLAGS.

        It flags at `suspicious` rather than `impossible` through this path, and
        that is correct given what the dispatcher can currently prove.
        `sprite_reconstruct` and `grimmer_check` now cap a range-dependent
        verdict unless `bound_source` is hard -- the rule `grim_check` has always
        applied (tools/grim.py:161-170). Two things keep it capped here:

          1. the registry ToolSpecs for these two carry no `bound_source` Param,
             so `_build_args` cannot forward one, and the function default
             (`assumed`) stands; and
          2. this variable's `confidence` defaults to "low", and
             `Variable.forensic_kwargs` maps anything below "high" to
             `bound_source="assumed"` even when bounds ARE given.

        The tool-level guarantee -- a hard bound still licenses `impossible` --
        is pinned directly below and in tests/test_sprite.py.
        """
        r = _run({"id": "v", "name": "Likert item", "family": "likert_item",
                  "lower_bound": 1, "upper_bound": 7})
        assert r["severity"] == "suspicious"
        assert r["severity"] != "consistent"
        assert "sprite_reconstruct" in _ran(r)

    def test_a_stated_bound_still_licenses_impossible_at_the_tool(self):
        from metascience_agent.tools.sprite import sprite_reconstruct

        r = sprite_reconstruct(35.78, 33.74, n=64, scale_min=1, scale_max=7,
                               data_type="likert", decimals_mean=2, decimals_sd=2,
                               bound_source="stated")
        assert r["severity"] == "impossible"


class TestScope:
    @pytest.mark.parametrize("family", ["count", "continuous", "time_to_event"])
    def test_unbounded_families_are_protected(self, family):
        r = _run({"id": "m", "name": LABEL, "family": family})
        assert r["severity"] != "impossible"

    def test_a_bounded_family_without_bounds_is_untouched(self):
        """likert_item without bounds is a different problem, handled elsewhere;
        this rule must not silently expand to cover it."""
        r = _run({"id": "v", "name": "Item", "family": "likert_item"})
        assert "sprite_reconstruct" not in _refused(r)
