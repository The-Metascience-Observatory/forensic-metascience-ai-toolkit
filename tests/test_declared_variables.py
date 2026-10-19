"""A check's scale and type must answer to the variable the paper declared."""

import pytest

from metascience_agent import declared
from metascience_agent.registry import BY_NAME

BDI = {"id": "v1", "name": "BDI-II total", "family": "likert_composite",
       "measurement_level": "interval", "discreteness": "discrete",
       "lower_bound": 0, "upper_bound": 63,
       "derivation": "sum_of_items", "n_items": 21}
ARM = {"id": "v2", "name": "Treatment arm", "family": "nominal_category",
       "measurement_level": "nominal", "discreteness": "discrete"}


@pytest.fixture(autouse=True)
def _declared():
    declared.set_variables([BDI, ARM])
    yield
    declared.clear()


class TestTheCallAnswersToTheRecord:
    """The TABLE path already reads bounds and type off the declared variable
    and stamps `variable_id` on the result. The MODEL path restated them
    freehand and tied them to nothing, so the anatomy and the check were two
    independent statements of one fact. Measured over the 72 archived
    findings.json: of 116 calls to the three bound-taking checks, 43 passed no
    scale bounds at all and 30 passed no `data_type`."""

    def test_a_named_variable_supplies_what_the_call_omitted(self):
        r = BY_NAME["grim_check"].call(
            {"mean": 20.51, "n": 35, "decimals": 2, "variable_id": "v1"})
        v = r["variable"]
        assert v["status"] == "reconciled"
        assert set(v["filled_from_the_paper"]) >= {"scale_min", "scale_max",
                                                   "data_type"}
        assert v["bounds"] == [0, 63]

    def test_a_contradiction_is_recorded_not_silently_resolved(self):
        r = BY_NAME["grim_check"].call(
            {"mean": 20.51, "n": 35, "decimals": 2, "variable_id": "v1",
             "scale_min": 1, "scale_max": 7, "data_type": "continuous"})
        v = r["variable"]
        assert v["status"] == "disagreed"
        params = {d["parameter"] for d in v["disagreements"]}
        assert params == {"scale_min", "scale_max", "data_type"}

    def test_a_contradiction_resolves_to_the_SAFER_reading(self):
        """Neither side is preferred. A check that quietly preferred the record
        would let a mis-declared variable drive an accusation; one that
        preferred the call would make the anatomy decorative. Each contested
        value goes to the reading that makes the check LESS likely to accuse."""
        args = {"mean": 20.51, "n": 35, "decimals": 2, "variable_id": "v1",
                "scale_min": 1, "scale_max": 7, "data_type": "continuous"}
        new, prov = declared.reconcile(
            {"scale_min", "scale_max", "data_type", "bound_source",
             "discreteness_source", "mean", "n", "decimals"}, args)
        assert new["scale_min"] == 0 and new["scale_max"] == 63   # the wider scale
        assert new["data_type"] == "unknown"                      # the least-licensing type
        # And the licence to say `impossible` is withdrawn outright.
        assert new["bound_source"] == "assumed"
        assert new["discreteness_source"] == "assumed"

    def test_a_variable_that_was_never_declared_fills_nothing(self):
        r = BY_NAME["grim_check"].call(
            {"mean": 20.51, "n": 35, "decimals": 2, "variable_id": "nope"})
        assert r["variable"]["status"] == "not_declared"

    def test_naming_no_variable_leaves_the_call_exactly_as_it_was(self):
        """This can turn an unreconciled call into a reconciled one and must
        never change a call that mentioned no variable."""
        r = BY_NAME["grim_check"].call({"mean": 20.51, "n": 35, "decimals": 2})
        assert "variable" not in r


class TestNOIRFinallyHasAConsumer:
    """`measurement_level` was asked for in the sweep prompt, carried on
    `Variable`, printed in the report table and the viewer -- and read by no
    check. The same defect the `derivation` field carried before it was wired:
    the model was answering a question nothing read."""

    def test_a_mean_of_a_nominal_variable_is_refused(self):
        r = BY_NAME["grim_check"].call(
            {"mean": 1.4, "n": 35, "decimals": 1, "variable_id": "v2"})
        assert r["applicable"] is False
        assert "nominal" in r["error"]

    def test_ordinal_is_deliberately_NOT_refused(self):
        """A Likert item is ordinal and GRIM on Likert means is the canonical
        use of the check. Refusing ordinal would delete the toolkit's main case
        to make a philosophical point."""
        declared.set_variables([{**BDI, "measurement_level": "ordinal"}])
        r = BY_NAME["grim_check"].call(
            {"mean": 20.51, "n": 35, "decimals": 2, "variable_id": "v1"})
        assert r.get("applicable") is not False

    def test_the_store_is_replaced_not_merged(self):
        """A variable must not survive into the next paper's review."""
        declared.set_variables([ARM])
        assert declared.get("v1") is None and declared.declared_count() == 1
