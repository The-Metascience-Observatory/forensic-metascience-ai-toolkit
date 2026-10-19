"""A flow can only lose people -- when both stages count the same people.

`check_flow_arithmetic` treated every stage count as a count of the same unit,
so an ordinary cluster-randomised trial (24 schools randomised, 1043 pupils
analysed) returned `impossible`: "Nobody can be analyzed who was never
randomized." Cluster designs are routine in education, public health and
implementation science, which is the literature this toolkit is aimed at.
"""

from __future__ import annotations

import pytest

from metascience_agent.tools.flow import check_flow_arithmetic as check

CLUSTER = [{"label": "Schools assessed", "n": 30},
           {"label": "Schools randomized", "n": 24},
           {"label": "Pupils analyzed", "n": 1043}]


def _modes(result):
    return {f["failure_mode"] for f in (result.get("failures") or [])}


class TestAUnitChangeIsNotAnImpossibility:
    def test_the_cluster_trial_is_no_longer_impossible(self):
        assert check(stages=CLUSTER)["severity"] != "impossible"

    def test_neither_hard_mode_fires(self):
        modes = _modes(check(stages=CLUSTER))
        assert "analyzed_exceeds_randomized" not in modes
        assert "step_mismatch" not in modes

    def test_undeclared_units_are_reported_not_alleged(self):
        """The increase is real and worth showing; a unit change explains it
        exactly as well as an error does, and no arithmetic separates them."""
        r = check(stages=CLUSTER)
        assert "exceeds_randomized_or_unit_change" in _modes(r)
        sentence = " ".join(f["sentence"] for f in r["failures"])
        assert "SAME UNIT" in sentence
        assert "cluster" in sentence.lower()

    def test_declared_differing_units_report_nothing_at_all(self):
        """Flagging a declared cluster design would train a reader to ignore
        this check on every cluster trial."""
        declared = [dict(s, unit=u) for s, u in
                    zip(CLUSTER, ("schools", "schools", "pupils"))]
        declared[0] = dict(declared[0], excluded=[["declined", 6]])
        r = check(stages=declared)
        assert r["severity"] == "indeterminate"
        assert not _modes(r)


class TestARealErrorStillReachesImpossible:
    """The premise being wrong must not become "stop checking"."""

    @pytest.mark.parametrize("u1, u2", [
        ("participants", "participants"),
        ("patients", "subjects"),      # both alias to `person`
        ("schools", "clinics"),        # both alias to `cluster`
    ])
    def test_the_same_declared_unit_keeps_the_hard_verdict(self, u1, u2):
        r = check(stages=[{"label": "Randomized", "n": 240, "unit": u1},
                          {"label": "Analyzed", "n": 260, "unit": u2}])
        assert r["severity"] == "impossible"
        assert "analyzed_exceeds_randomized" in _modes(r)

    def test_an_ordinary_decreasing_flow_is_unchanged(self):
        r = check(stages=[{"label": "Assessed", "n": 300},
                          {"label": "Randomized", "n": 240},
                          {"label": "Analyzed", "n": 232}])
        assert r["severity"] != "impossible"
        assert "unaccounted_attrition" in _modes(r)

    def test_a_fully_explained_flow_is_still_clean(self):
        r = check(stages=[
            {"label": "Assessed", "n": 300, "unit": "participants",
             "excluded": [["ineligible", 60]]},
            {"label": "Randomized", "n": 240, "unit": "participants",
             "excluded": [["withdrew", 8]]},
            {"label": "Analyzed", "n": 232, "unit": "participants"}])
        assert r["severity"] not in ("impossible", "highly_suspicious",
                                     "suspicious")


class TestTheUnitRelationIsThreeWay:
    """`same` licenses the hard verdict, `different` reports nothing, and
    `unknown` reports without alleging. Undeclared is never `same` -- the
    accusation is what needs licensing."""

    @pytest.mark.parametrize("a, b, expected", [
        ("participants", "patients", "same"),      # both -> person
        ("schools", "sites", "same"),              # both -> cluster
        ("schools", "pupils", "different"),
        # Undeclared, and the labels name nothing: unchanged behaviour, which
        # is what keeps the canonical randomized -> analyzed flow hard.
        (None, None, "same"),
    ])
    def test_relation_from_declared_units(self, a, b, expected):
        from metascience_agent.tools.flow import _norm_unit, _unit_relation
        cur = {"label": "stage a", "unit": _norm_unit(a)}
        nxt = {"label": "stage b", "unit": _norm_unit(b)}
        assert _unit_relation(cur, nxt) == expected

    @pytest.mark.parametrize("la, lb, expected", [
        ("Schools randomized", "Pupils analyzed", "unknown"),
        ("Patients randomized", "Patients analyzed", "same"),
        ("randomized", "analyzed", "same"),        # names no unit at all
        ("Clusters randomized", "Sites analyzed", "same"),   # both -> cluster
    ])
    def test_relation_inferred_from_labels(self, la, lb, expected):
        """RULE 1: only POSITIVE evidence of two DIFFERENT units narrows
        anything. A label naming no unit yields None and licenses nothing."""
        from metascience_agent.tools.flow import _unit_relation
        assert _unit_relation({"label": la}, {"label": lb}) == expected

    def test_an_unrecognised_unit_is_kept_verbatim(self):
        """A vocabulary miss must not silently collapse two units into one."""
        from metascience_agent.tools.flow import _norm_unit, _unit_relation
        assert _norm_unit("knees") == "knees"
        assert _unit_relation({"unit": "knees"}, {"unit": "person"}) == "different"
