"""Repeated measures is `paired` with k > 2, and it was the one dependent
design family with no entry in the vocabulary.

`check_variance_dispersion` refuses on cluster, crossover, matched-pairs,
stratified and minimised designs, because each forces group variances to be
similar BY DESIGN and the test reads that similarity as under-dispersion. The
same people measured at several visits do exactly the same thing -- and
"repeated measures", "longitudinal", "within-subjects", "pre-post" and "panel
study" ALL resolved to None, so declaring the design truthfully did not help.

It matters more than the rate suggests: this verdict carries "the signature
Hartgerink et al. (2019) found most diagnostic of fabricated data".
"""

from __future__ import annotations

import random
import statistics as st

import pytest

from forensic_metascience_ai_toolkit.tools.csf import DEPENDENT_DESIGNS, _resolve_design
from forensic_metascience_ai_toolkit.tools.variance_dispersion import check_variance_dispersion


class TestTheVocabularyRecognisesRepeatedMeasures:
    @pytest.mark.parametrize("text, canonical", [
        ("repeated measures", "repeated_measures"),
        ("single-group repeated measures", "repeated_measures"),
        ("repeated-measures ANOVA", "repeated_measures"),
        ("within-subjects", "within_subjects"),
        ("within-person design", "within_subjects"),
        ("longitudinal", "longitudinal"),
        ("panel study", "longitudinal"),
        ("multi-wave panel", "longitudinal"),
        ("pre-post", "pre_post"),
        ("before-after study", "pre_post"),
    ])
    def test_it_resolves_and_is_dependent(self, text, canonical):
        resolved = _resolve_design(text)
        assert resolved == canonical
        assert resolved in DEPENDENT_DESIGNS

    @pytest.mark.parametrize("text, canonical", [
        ("parallel-group RCT", "parallel_rct"),
        ("individually randomised", "individually_randomised"),
    ])
    def test_independent_designs_are_untouched(self, text, canonical):
        resolved = _resolve_design(text)
        assert resolved == canonical
        assert resolved not in DEPENDENT_DESIGNS

    def test_a_randomised_repeated_measures_trial_is_not_simple_randomisation(self):
        """Every dependence-inducing design also contains "randomis", which is
        why the pattern order matters -- the same reason `cluster` is tested
        first."""
        assert _resolve_design("randomised crossover trial") == "crossover"
        assert _resolve_design("randomised repeated-measures trial") \
            == "repeated_measures"

    def test_an_unknown_design_still_resolves_to_none(self):
        """Returning None matters more than any mapping: a string this module
        has never heard of must not count as a known independent design."""
        assert _resolve_design("some novel allocation scheme") is None


class TestItRefusesRatherThanAccuses:
    def test_a_declared_repeated_measures_design_is_refused(self):
        r = check_variance_dispersion(
            sds=[9.81, 9.79, 9.83, 9.80], ns=[40] * 4,
            sd_texts=["9.81", "9.79", "9.83", "9.80"],
            homogeneous_variances=True, design="single-group repeated measures",
            iterations=2000)
        assert r["severity"] == "indeterminate"
        assert r.get("criterion") == "design"

    def _rate(self, rho, design, k=4, n=40, trials=60, seed=7):
        rnd = random.Random(seed)
        hits = 0
        for _ in range(trials):
            base = [rnd.gauss(50, 10) for _ in range(n)]
            texts = []
            for _v in range(k):
                vals = [rho * b + (1 - rho) * rnd.gauss(50, 10) + rnd.gauss(0, 3)
                        for b in base]
                texts.append(f"{st.pstdev(vals):.2f}")
            r = check_variance_dispersion(
                sds=[float(x) for x in texts], ns=[n] * k, sd_texts=texts,
                homogeneous_variances=True, design=design, iterations=1500)
            if r["severity"] in ("suspicious", "highly_suspicious", "impossible"):
                hits += 1
        return 100.0 * hits / trials

    @pytest.mark.parametrize("rho", [0.8, 0.95, 0.98])
    def test_honest_correlated_visits_are_not_flagged(self, rho):
        """Measured before the fix: 9.3%, 14.0% and 13.3% at these three
        correlations, with the design declared truthfully."""
        assert self._rate(rho, "single-group repeated measures") == 0.0

    def test_an_independent_design_keeps_its_power(self):
        """The refusal must not become "stop checking". A paper CLAIMING
        independent groups whose SDs are this similar is exactly what this test
        exists to find."""
        assert self._rate(0.95, "parallel-group RCT") > 0.0
