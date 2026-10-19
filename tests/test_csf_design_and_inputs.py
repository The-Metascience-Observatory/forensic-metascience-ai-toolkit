"""CSF: the design gate must not invert, and a non-p-value must not be combined.

Both bugs here shared one shape -- the tool reached its STRONGEST available
verdict for a reason that had nothing to do with the trial:

* `design_known = bool(design_key)` counted ANY non-empty string as a known
  design, so a truthful British-spelled design lifted the severity cap instead
  of applying it. Measured against the old expression, `design="cluster-
  randomised"` returned `highly_suspicious` where the design gate should have
  refused outright: the set holds `cluster_randomized` with a z, and the
  British spelling matched neither the gate nor anything else, which left it
  looking like a known independent design.
* `arr[(arr > 0) & (arr <= 1)]` dropped NaN and out-of-range p-values silently
  and then echoed the ORIGINAL list back as `individual_p_values`, so a table
  whose extraction half failed was combined from the survivors and reported as
  though all of it had been used.
"""

import math

import pytest

from metascience_agent.tools.csf import DEPENDENT_DESIGNS, _resolve_design, csf_test

# p-values extreme enough that the verdict is decided by the design gate and the
# cap, not by the arithmetic: similarity_p < 1e-6 at rho = 0.5.
EXTREME = [1.0, 1.0, 1.0]


def _old_severity(design):
    """What the pre-fix code returned for `design` on EXTREME p-values.

    Reproduces the two old expressions verbatim -- the gate `design_key in
    DEPENDENT_DESIGNS` and `design_known = bool(design_key)` -- so the tests
    below are pinned against measured old behaviour rather than a recollection
    of it.
    """
    key = str(design or "").strip().lower().replace("-", "_").replace(" ", "_")
    if key in DEPENDENT_DESIGNS:
        return "indeterminate"
    return "highly_suspicious" if key else "suspicious"


class TestTheDesignGateNoLongerInverts:
    @pytest.mark.parametrize("design", [
        "cluster-randomised",
        "cluster randomised trial",
        "randomised with minimisation by centre",
        "stratified randomisation",
        "multicentre",
        "matched-pair cluster design",
    ])
    def test_a_british_spelled_dependent_design_is_refused_not_escalated(self, design):
        """These are the cases that flipped. Each one names a design in which
        baseline balance is forced BY CONSTRUCTION, and each one used to come
        back `highly_suspicious` -- the tool accusing a trial of fabrication on
        the strength of the trial having described itself accurately."""
        assert _old_severity(design) == "highly_suspicious"      # the bug
        assert csf_test(EXTREME, design=design)["severity"] == "indeterminate"

    @pytest.mark.parametrize("design", ["unclear", "typo", "some design we never modelled"])
    def test_an_unrecognised_design_is_unknown_and_keeps_the_cap(self, design):
        """An unrecognised string is UNKNOWN, not known-independent. Unknown
        keeps the cap, because the designs it might be naming are exactly the
        ones that would explain extreme similarity innocently."""
        assert _old_severity(design) == "highly_suspicious"      # the bug
        assert csf_test(EXTREME, design=design)["severity"] == "suspicious"

    @pytest.mark.parametrize("design", ["randomised", "randomized", "parallel_rct",
                                        "parallel-group RCT", "simple randomisation"])
    def test_a_recognised_independent_design_still_lifts_the_cap(self, design):
        """The cap exists to be lifted by a design that actually licenses the
        test. This is the half that must NOT regress into blanket caution: a
        tool that refuses everything is as useless as one that accuses
        everything."""
        r = csf_test(EXTREME, design=design)
        assert r["severity"] == "highly_suspicious"
        assert r["design_recognized"] is True

    def test_a_design_that_denies_randomisation_does_not_resolve_through_randomis(self):
        """`quasi-randomised` contains `randomis`. Substring matching without
        this guard would hand a non-randomised study the uncapped ceiling on the
        strength of the very word it used to deny randomisation."""
        assert _resolve_design("quasi-randomised") is None
        assert csf_test(EXTREME, design="quasi-randomised")["severity"] == "suspicious"

    def test_no_design_at_all_is_still_capped(self):
        for design in (None, "", "   "):
            assert csf_test(EXTREME, design=design)["severity"] == "suspicious"

    def test_the_resolved_design_is_echoed_so_a_reader_can_check_it(self):
        r = csf_test(EXTREME, design="Stratified block randomisation")
        assert r["design"] == "Stratified block randomisation"   # what was passed
        assert r["design_resolved"] == "stratified"              # what was understood
        clear = csf_test(EXTREME, design="parallel_rct")
        assert clear["design_resolved"] == "parallel_rct"
        unknown = csf_test(EXTREME, design="typo")
        assert unknown["design_resolved"] is None
        assert unknown["design_recognized"] is False

    def test_an_unrecognised_design_says_so_rather_than_claiming_none_was_given(self):
        """Two different ways to be unknown. `not supplied` sent a reader to
        the paper; `not RECOGNISED` sends them here, which is where the fix is."""
        assert "was not supplied" in csf_test(EXTREME)["explanation"]
        assert "not RECOGNISED" in csf_test(EXTREME, design="typo")["explanation"]

    def test_cluster_beats_randomis_in_the_pattern_order(self):
        """Every dependence-inducing design also contains `randomis`. If the
        plain-randomisation pattern were tested first, every one of them would
        resolve to simple randomisation and lose its refusal."""
        assert _resolve_design("cluster randomised") == "cluster_randomized"
        assert _resolve_design("stratified randomised trial") == "stratified"
        assert _resolve_design("randomised by minimisation") == "minimisation"


class TestNonPValuesAreRefusedNotDropped:
    def test_a_nan_makes_the_whole_table_indeterminate(self):
        r = csf_test([0.99, float("nan"), 0.99, 0.99])
        assert r["severity"] == "indeterminate"
        assert r["dropped_p_values"] == ["nan"]
        assert r["individual_p_values"] == [0.99, 0.99, 0.99]

    def test_the_old_behaviour_reached_a_finding_on_the_survivors(self):
        """The failure this prevents, measured. Dropping the NaN leaves three
        p-values of 0.99, which combine to `suspicious` -- a finding against a
        paper produced by an extraction that had already failed once on the
        same table, with nothing in the output saying so."""
        survivors = [p for p in [0.99, float("nan"), 0.99, 0.99]
                     if math.isfinite(p) and 0 < p <= 1]
        assert csf_test(survivors)["severity"] == "suspicious"       # the old answer
        assert csf_test([0.99, float("nan"), 0.99, 0.99])["severity"] == "indeterminate"

    @pytest.mark.parametrize("bad", [0.0, -0.5, 1.5, float("inf"), float("-inf")])
    def test_every_out_of_range_value_is_refused(self, bad):
        r = csf_test([0.4, bad, 0.6, 0.8])
        assert r["severity"] == "indeterminate"
        assert len(r["dropped_p_values"]) == 1

    def test_dropped_values_survive_json(self):
        """JSON has no NaN literal and every tool result is serialised before a
        reader sees it, so a non-finite reject is echoed as text. Losing the
        rejected value to the serialiser would leave a refusal with no reason."""
        import json
        r = csf_test([0.4, float("nan"), 0.6, 0.8])
        assert json.loads(json.dumps(r, allow_nan=False))["dropped_p_values"] == ["nan"]

    def test_a_clean_table_reports_exactly_what_it_combined(self):
        r = csf_test([0.93, 0.99, 0.99])
        assert r["individual_p_values"] == [0.93, 0.99, 0.99]
        assert r["dropped_p_values"] == []

    def test_p_equal_one_is_echoed_unclipped(self):
        """1.0 is a legal p-value. The 1e-10 clip is a numerical guard against
        norm.ppf(1.0) returning +inf, not a change to what the paper printed,
        and echoing the clipped value would report 0.9999999999 back."""
        assert csf_test([1.0, 1.0, 1.0])["individual_p_values"] == [1.0, 1.0, 1.0]

    def test_an_empty_list_is_still_the_empty_list_error(self):
        assert csf_test([])["error"] == "No valid p-values provided"

    def test_all_bad_values_still_report_an_error(self):
        """Pins the pre-existing contract that `test_no_valid_p_values` covers:
        the message changed, the presence of `error` did not."""
        r = csf_test([-0.5, 1.5])
        assert "error" in r and r["severity"] == "indeterminate"


class TestADenialOfADesignIsNotThatDesign:
    """`_resolve_design` had two hand-built negation lists -- `_NOT_RANDOMISED`
    and `_NEGATED_PAIRING` -- each added after someone was bitten by one stem.
    Three cases were still live, and each resolved to a DEPENDENT design, which
    suppresses the check entirely and returns an `explanation` interpolating the
    false design into a stated fact about the trial ("This is a <design> design,
    in which baseline observations are correlated BY DESIGN").

    Replaced by one negation rule that applies to every stem, clause-bounded so
    a denial in one phrase cannot travel to another.
    """

    NEGATED = [
        ("no stratification is not stratified",
         "parallel-group RCT, individually randomised, no stratification",
         "parallel_rct"),
        ("not cluster randomised is not a cluster trial",
         "this trial was not cluster randomised", None),
        ("not a multicentre trial is not multi-site",
         "not a multicentre trial", None),
        ("unpaired is not matched pairs, and the first clause still resolves",
         "individually randomised, unpaired", "randomized"),
        ("unmatched is not matched", "unmatched case-control", None),
        ("non-randomised is not randomised", "non-randomised cohort", None),
    ]
    AFFIRMED = [
        ("matched pairs design", "matched_pairs"),
        ("cluster randomised trial", "cluster_randomized"),
        ("stratified by site", "stratified"),
        ("crossover trial", "crossover"),
        ("stepped wedge", "stepped_wedge"),
        ("parallel group RCT", "parallel_rct"),
    ]

    def test_a_negated_design_does_not_resolve_to_it(self):
        from metascience_agent.tools.csf import _resolve_design
        wrong = [(n, _resolve_design(d), want) for n, d, want in self.NEGATED
                 if _resolve_design(d) != want]
        assert not wrong, f"negated designs still resolving: {wrong}"

    def test_real_designs_still_resolve(self):
        from metascience_agent.tools.csf import _resolve_design
        wrong = [(d, _resolve_design(d), want) for d, want in self.AFFIRMED
                 if _resolve_design(d) != want]
        assert not wrong, f"the negation rule broke real designs: {wrong}"

    def test_negating_everything_yields_unknown_which_KEEPS_the_cap(self):
        """None is safe in both directions: `design_known` is False, so the
        severity cap stays on AND the dependent-design gate does not fire."""
        from metascience_agent.tools.csf import _resolve_design
        assert _resolve_design("not a multicentre trial") is None
