"""A number sent as a string is still that number -- and anything else refuses.

MEASURED across every archived run: 154 arguments declared `int` or `float`
arrived from the model as strings, and 2 `decimals` arrived as a list. The
largest single offender is `decimals` at 84 calls, which is the PRECISION GATE
-- the parameter whose absence turns a check off entirely.

WHAT IT COST WAS COVERAGE, NOT CORRECTNESS. Of 120 affected calls, 92 raised a
TypeError and the rest were refused by the precision gate; none produced a wrong
verdict. But a check that silently does not run is the failure this repo keeps
rediscovering, and `decimals="1"` is not an ambiguity -- it is a JSON
serialisation slip on a value the model got right.
"""
import pytest

from metascience_agent import registry as R

GRIM = dict(mean=5.51, n=30, data_type="likert", discreteness_source="stated")


def _grim(**over):
    return R.BY_NAME["grim_check"].call({**GRIM, **over})


class TestAStringNumberIsRead:
    @pytest.mark.parametrize("sent", ["2", " 2 ", "2.0", "+2"])
    def test_an_integer_written_as_a_string_runs_the_check(self, sent):
        """5.51 at n=30 is the canonical GRIM impossibility. It must reach that
        verdict whether `decimals` arrives as 2 or "2"."""
        assert _grim(decimals=sent)["severity"] == "impossible"

    def test_it_agrees_with_the_native_type(self):
        assert _grim(decimals="2") == _grim(decimals=2)

    def test_a_float_param_takes_a_string_too(self):
        native = R.BY_NAME["stalt_check"].call(
            {"calculated_p": 0.0001, "reported_threshold": "<0.05"})
        coerced = R.BY_NAME["stalt_check"].call(
            {"calculated_p": "0.0001", "reported_threshold": "<0.05"})
        assert coerced["severity"] == native["severity"]


class TestWhatIsDeliberatelyNotCoerced:
    def test_a_non_integer_string_on_an_int_param_is_NOT_rounded(self):
        """"2.5" for a printed-decimals parameter is not a serialisation slip,
        it is wrong. Guessing which way to round it would size a rounding
        interval off a number nobody sent."""
        r = _grim(decimals="2.5")
        assert r["severity"] == "indeterminate"
        assert "decimals" in r["unreadable_params"]

    @pytest.mark.parametrize("sent", ["abc", "", "  ", "1e", "two"])
    def test_an_unparseable_string_refuses_by_name(self, sent):
        r = _grim(decimals=sent)
        assert r["severity"] == "indeterminate"
        assert r["unreadable_params"] == ["decimals"]

    def test_a_list_is_never_flattened_into_a_scalar(self):
        """`[0]` and `0` are different claims, and `check_summation`
        legitimately accepts a list for the same parameter name another tool
        takes as a scalar."""
        r = _grim(decimals=[2])
        assert r["severity"] == "indeterminate"

    def test_a_param_declared_list_is_left_alone_entirely(self):
        """`check_summation.decimals` is declared `list`, so the coercion must
        not touch it -- a per-value precision list is the tool's real API."""
        spec = R.BY_NAME["check_summation"]
        assert next(p.type for p in spec.params if p.name == "decimals") is list
        out = spec.call({"values": [6, 6, 6, 8], "expected_sum": 26, "decimals": 0})
        assert out.get("severity")

    def test_bool_is_never_coerced(self):
        """Python reads `bool("False")` as True, so coercing a stringified
        boolean would INVERT a guard silently -- worse than refusing it."""
        from metascience_agent.registry import _COERCIBLE
        assert bool not in _COERCIBLE


class TestTheRefusalIsActionable:
    def test_it_names_the_parameter_and_says_what_to_send(self):
        """Before this, the same input raised `TypeError: bad operand type for
        unary -` out of `ToolSpec.call` -- a stack trace where a verdict
        belongs, saying nothing about which parameter was wrong."""
        r = _grim(decimals="abc")
        assert "decimals" in r["error"]
        assert '2, not "2"' in r["explanation"]

    def test_it_is_not_a_statement_about_the_paper(self):
        r = _grim(decimals="abc")
        assert r["applicable"] is False
        assert "Not a statement about the paper" in r["explanation"]
        assert r["severity"] not in ("impossible", "highly_suspicious", "suspicious")

    def test_a_genuinely_absent_decimals_keeps_its_OWN_refusal(self):
        """The precision gate's message is more specific than the type one and
        must not be replaced by it."""
        r = _grim(decimals=None)
        assert r["severity"] == "indeterminate"
        assert "unreadable_params" not in r


class TestTheArchivedCallsWouldNowRun:
    """The measurement that motivated this, replayed."""

    def test_the_offending_shapes_from_the_archive(self):
        import collections
        import glob
        import json

        NUM = ("decimals", "decimals_mean", "decimals_sd", "decimals_p")
        seen = collections.Counter()
        for f in glob.glob("**/toolcalls.stage*.json", recursive=True):
            try:
                data = json.load(open(f))
            except Exception:
                continue
            for c in (data if isinstance(data, list) else data.get("calls", [])):
                for k, v in (c.get("input") or {}).items():
                    if k in NUM and isinstance(v, str):
                        seen[v] += 1
        if not seen:
            pytest.skip("no archived runs in this checkout")
        # Every string actually observed is a plain integer, which is exactly
        # the case coercion recovers -- not a single one was ambiguous.
        assert all(s.strip().lstrip("+-").isdigit() for s in seen), dict(seen)
