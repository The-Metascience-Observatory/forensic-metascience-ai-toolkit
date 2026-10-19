"""A statistic printed in a sentence is a number, not a string.

`groups_from_body_items` hard-coded `value: None`, so every statistic the floor
found in running text reached the register as a printed span and nothing else.

MEASURED over the eleven-paper cerebrolysin run, on the papers' OWN values
(supplement raw data excluded):

    table-anchored   2,003 parsed     0 unparsed
    body-anchored        0 parsed   826 unparsed

The split was total, and total per kind: 275/275 `mean_pm_prose`, 165/165
`named_equality`, 160/160 `percentage`, 116/116 `p_value`. Not a degradation --
a path that was never finished. The floor detected the shapes correctly and
nothing turned them into numbers.

What it cost: on `10.1161--strokeaha.124.049834` all 141 body values were
valueless including all 56 p-values, and the five complete
`WTS=31.386, df=3, P<0.001` blocks the paper prints handed statcheck nothing.
"""

import pytest

from forensic_metascience_ai_toolkit.values import groups_from_body_items, prose_values


class TestTheNumberIsRecovered:
    @pytest.mark.parametrize("kind,raw,expected", [
        ("mean_pm_prose", "65.2 ± 1.17", [("mean", 65.2), ("sd", 1.17)]),
        ("mean_pm_prose", "17.366±10.303", [("mean", 17.366), ("sd", 10.303)]),
        ("named_equality", "n = 202", [("n", 202.0)]),
        ("named_equality", "OR = 1.27", [("estimate", 1.27)]),
        ("named_equality", "SD = 0.21", [("sd", 0.21)]),
        ("named_equality", "MWcombined = 0.69", [("estimate", 0.69)]),
        ("percentage", "32%", [("percentage", 32.0)]),
        ("p_value", "P<0.001", [("p", 0.001)]),
        ("n_of_total", "11 of 60", [("count", 11.0), ("denominator", 60.0)]),
    ])
    def test_shapes(self, kind, raw, expected):
        got = [(v["role"], v["value"]) for v in prose_values(kind, raw)]
        assert got == expected

    def test_decimals_travel(self):
        """GRIM needs the decimal count, not only the value."""
        v = prose_values("mean_pm_prose", "65.20 ± 1.1")
        assert [x["decimals"] for x in v] == [2, 1]


class TestASeparatorIsNotAMinusSign:
    """A first version scanned for numbers and took the next two, so
    `0.548 (95% CI, 0.182-0.912)` produced `ci_high = -0.912` -- an upper bound
    below its own lower bound. A checker handed that reports an interval the
    paper never printed, against authors who printed an ordinary one."""

    def test_a_hyphen_range_keeps_both_bounds_positive(self):
        v = prose_values("estimate_ci_prose", "0.548 (95% CI, 0.182-0.912)")
        assert [(x["role"], x["value"]) for x in v] == [
            ("estimate", 0.548), ("ci_low", 0.182), ("ci_high", 0.912)]

    def test_a_genuinely_negative_interval_keeps_its_signs(self):
        v = prose_values("ci_to_form", "95% CI -1.2 to -0.3")
        assert [(x["role"], x["value"]) for x in v] == [
            ("ci_low", -1.2), ("ci_high", -0.3)]

    def test_a_negative_estimate_with_a_negative_interval(self):
        v = prose_values("estimate_ci_prose", "-0.85 (95% CI -1.2, -0.3)")
        assert [(x["role"], x["value"]) for x in v] == [
            ("estimate", -0.85), ("ci_low", -1.2), ("ci_high", -0.3)]

    @pytest.mark.parametrize("raw", [
        "95% CI 0.50 to 0.81", "95% CI, 31.289–39.869", "95% CI 1.000-1.074",
    ])
    def test_the_upper_bound_is_never_below_the_lower(self, raw):
        v = {x["role"]: x["value"] for x in prose_values("ci_to_form", raw)}
        assert v["ci_high"] >= v["ci_low"], f"inverted interval from {raw!r}"

    def test_the_confidence_level_is_not_a_bound(self):
        v = [x["value"] for x in prose_values("ci_to_form", "95% CI 0.50 to 0.81")]
        assert 95 not in v and 95.0 not in v


class TestARefusalIsStillRecorded:
    """An unparsed statistic is still a statistic the paper printed. Dropping it
    would shrink the floor that exists to say what was overlooked."""

    def test_an_unparseable_span_keeps_its_row_and_its_text(self):
        rows = groups_from_body_items(
            [{"kind": "p_value", "raw": "P = not reported", "offset": 10}])
        vals = rows[0]["values"]
        assert len(vals) == 1
        assert vals[0]["value"] is None
        assert vals[0]["printed"] == "P = not reported"

    def test_a_censored_p_keeps_the_comparator_on_the_printed_string(self):
        """`P < 0.001` is not a p-value of 0.001. The bound is the number; that
        it is a bound is what `printed` still says."""
        rows = groups_from_body_items(
            [{"kind": "p_value", "raw": "P < 0.001", "offset": 3}])
        v = rows[0]["values"][0]
        assert v["value"] == 0.001
        assert "<" in v["printed"]

    def test_an_unmapped_symbol_is_unknown_rather_than_guessed(self):
        v = prose_values("named_equality", "alpha = 0.025")
        assert v[0]["role"] == "unknown"
        assert v[0]["value"] == 0.025


class TestTheRowsStayWellFormed:
    def test_two_values_from_one_span_get_distinct_ids(self):
        rows = groups_from_body_items(
            [{"kind": "mean_pm_prose", "raw": "65.2 ± 1.17", "offset": 42}])
        ids = [v["id"] for v in rows[0]["values"]]
        assert len(ids) == len(set(ids)) == 2

    def test_both_values_belong_to_the_one_group(self):
        rows = groups_from_body_items(
            [{"kind": "mean_pm_prose", "raw": "65.2 ± 1.17", "offset": 42}])
        assert len({v["group"] for v in rows[0]["values"]}) == 1
        assert rows[0]["values"][0]["group"] == rows[0]["id"]

    def test_role_class_follows_the_role(self):
        rows = groups_from_body_items(
            [{"kind": "named_equality", "raw": "n = 202", "offset": 1}])
        v = rows[0]["values"][0]
        assert v["role"] == "n" and v["role_class"] == "design"


class TestTheLeadingDecimalForm:
    """`.0525` is how APA style prints a p-value -- the leading zero is dropped
    by convention -- and it is everywhere in medical writing.

    A first version of `_PROSE_NUM` required a digit first, so `P = .0525`
    matched only `0525` and registered as **525.0**, and `P < .001` registered
    as **1.0**: a p-value the paper called highly significant, recorded as the
    least significant value possible. Five of 116 p-values across the nine
    registers were outside [0, 1].

    Found by a corpus invariant, not by a unit test -- every fixture I had
    written used a leading zero.
    """

    @pytest.mark.parametrize("raw,expected", [
        ("P = .0525", 0.0525),
        ("P < .001", 0.001),
        ("P = .05", 0.05),
        ("P = 0.0525", 0.0525),
    ])
    def test_a_p_value_keeps_its_magnitude(self, raw, expected):
        assert prose_values("p_value", raw)[0]["value"] == expected

    def test_a_leading_decimal_interval_parses_at_all(self):
        got = [(v["role"], v["value"])
               for v in prose_values("estimate_ci_prose", ".85 (95% CI .70 to .95)")]
        assert got == [("estimate", 0.85), ("ci_low", 0.70), ("ci_high", 0.95)]

    def test_a_negative_leading_decimal_interval_keeps_its_signs(self):
        got = [(v["role"], v["value"])
               for v in prose_values("ci_to_form", "95% CI -.30 to -.05")]
        assert got == [("ci_low", -0.30), ("ci_high", -0.05)]

    def test_every_p_value_lies_in_the_unit_interval(self):
        """The invariant that caught it, kept as a test."""
        for raw in ("P = .0525", "P < .001", "P = 0.05", "P = 1.0", "P = .999"):
            v = prose_values("p_value", raw)[0]["value"]
            assert 0.0 <= v <= 1.0, f"{raw!r} parsed to {v}"


class TestLancetHouseStyleDecimals:
    """`Lancet`, `BMJ` and the journals following their style set decimals as
    MIDDLE DOTS: `4·5`, not `4.5`. `International Journal of Stroke` does it 158
    times in a single paper of the eleven-paper run.

    Unrepaired, `-5·077 (95% CI: -7·716 to -2·437)` reached the register as
    estimate **77**, ci_low **716**, ci_high **-2**: every number wrong, a whole
    digit lost from the estimate, the sign lost, and the interval inverted --
    with `check_estimate_ci` ready to pronounce on the result.

    Three separate readers had to learn the convention, which is the honest
    shape of the problem: `completeness._NUM` decides where the span STARTS,
    `celltypes.repair_unicode` makes the text parseable, and
    `values.prose_values` reads the numbers out of it.
    """

    def test_a_middle_dot_between_digits_is_a_decimal_point(self):
        from forensic_metascience_ai_toolkit.tools.celltypes import repair_unicode
        assert repair_unicode("4·5")[0] == "4.5"
        assert repair_unicode("4·5")[1] == 1, "the repair is counted, not silent"

    def test_a_middle_dot_that_is_not_between_digits_is_left_alone(self):
        """It is a bullet and a separator elsewhere, and this codebase may not
        rewrite it on sight."""
        from forensic_metascience_ai_toolkit.tools.celltypes import repair_unicode
        assert repair_unicode("a · bullet")[0] == "a · bullet"
        assert repair_unicode("a · bullet")[1] == 0

    def test_the_verbatim_interval_from_the_run(self):
        from forensic_metascience_ai_toolkit.values import prose_values
        got = {v["role"]: v["value"] for v in
               prose_values("estimate_ci_prose", "-5·077 (95% CI: -7·716 to -2·437)")}
        assert got["estimate"] == -5.077
        assert got["ci_low"] == -7.716 and got["ci_high"] == -2.437
        assert got["ci_low"] < got["estimate"] < got["ci_high"], (
            "the estimate must sit inside its own interval")

    def test_the_span_matcher_starts_at_the_sign_not_mid_number(self):
        """`completeness._NUM` decides where the span begins. Without the middle
        dot it matched only `077`, so everything downstream was handed a number
        that began three characters late."""
        import re
        from forensic_metascience_ai_toolkit.completeness import BODY_PATTERNS
        text = "the difference was -5·077 (95% CI: -7·716 to -2·437) overall"
        m = re.search(BODY_PATTERNS["estimate_ci_prose"], text)
        assert m and m.group(0).startswith("-5·077"), m.group(0) if m else None

    def test_an_ordinary_decimal_point_is_unaffected(self):
        from forensic_metascience_ai_toolkit.values import prose_values
        got = {v["role"]: v["value"] for v in
               prose_values("estimate_ci_prose", "0.548 (95% CI, 0.182 to 0.912)")}
        assert got["estimate"] == 0.548
        assert got["ci_low"] == 0.182 and got["ci_high"] == 0.912
