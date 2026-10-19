"""Statistical anatomy: enumeration, typing, multiplicity, narrative ranking."""
import contextlib

import pytest
from typer.testing import CliRunner

from metascience_agent.cli import app as cli_app
from metascience_agent.registry import BY_NAME
from metascience_agent.anatomy import (
    Hypothesis, PaperAnatomy, StatisticalTest, Study, Variable,
    anatomy_summary, assumption_risk, build_test_table,
    check_test_variable_compatibility, infer_narrative_tier,
    multiplicity_report, weight_finding_severity,
)


def _anatomy():
    a = PaperAnatomy(paper_id="p1")
    a.studies = [Study(id="s1", label="cohort", design="cross_sectional", n=1321, clustered=True)]
    a.variables = [
        Variable(id="v_bin", name="Intent", family="binary", measurement_level="nominal",
                 discreteness="discrete", lower_bound=0, upper_bound=1, confidence="high"),
        Variable(id="v_lik", name="Shame", family="likert_item", measurement_level="ordinal",
                 discreteness="discrete", lower_bound=1, upper_bound=5, confidence="high"),
        Variable(id="v_bp", name="Systolic BP", family="continuous", measurement_level="ratio",
                 discreteness="continuous", units="mmHg", confidence="high"),
    ]
    a.hypotheses = [Hypothesis(id="h1", statement="primary", status="preregistered_confirmatory")]
    return a


class TestVariableTyping:
    """Typed variables are what make the forensic guards usable instead of defaulted."""

    def test_continuous_variable_blocks_grim_family_tools(self):
        v = Variable(id="v", name="BP", family="continuous", confidence="high")
        assert v.forensic_kwargs()["data_type"] == "continuous"
        assert "grim" not in v.applicable_tools()

    def test_likert_supplies_real_bounds_not_the_default(self):
        # A VERIFIED provenance quote is now required alongside `confidence`
        # before bounds count as STATED -- see TestStatedBoundsNeedAVerifiedQuote.
        # What this test is about is the bounds themselves, not the promotion.
        # ...and the quote must NAME those bounds, added 2026-08-11. See
        # tests/test_bounds_provenance.py.
        v = Variable(id="v", name="item", family="likert_item",
                     lower_bound=1, upper_bound=5, confidence="high",
                     provenance_quote="scored 1 (not at all) to 5 (extremely)",
                     provenance_verdict="verbatim")
        kw = v.forensic_kwargs()
        assert (kw["scale_min"], kw["scale_max"]) == (1, 5)   # NOT the 1-7 default
        assert kw["bound_source"] == "stated"

    def test_unbounded_variable_never_claims_a_stated_bound(self):
        kw = Variable(id="v", name="x", family="continuous").forensic_kwargs()
        assert "scale_min" not in kw
        assert kw["bound_source"] == "assumed"

    def test_low_confidence_downgrades_bound_source(self):
        v = Variable(id="v", name="x", family="likert_item",
                     lower_bound=1, upper_bound=7, confidence="low")
        assert v.forensic_kwargs()["bound_source"] == "assumed"


class TestStatedBoundsNeedAVerifiedQuote:
    """`stated` bounds are what let GRIM/SPRITE reach `impossible`, so the claim
    that the paper stated them cannot be the model's own say-so.

    The old test was `confidence == "high"`, a self-assessment by the party
    being checked. A model writing `confidence: "high"` beside an invented 1-7
    scale promoted every GRIM verdict on that variable from `suspicious` to
    fabrication grade. The `provenance_quote` it was asked to supply as the
    evidence was never looked at.
    """

    # THE QUOTE NOW HAS TO MENTION THE BOUNDS (2026-08-11). A third condition
    # joined the two this class was written for: a verified sentence must be
    # verified ABOUT THIS. `provenance_quote` is specified as the sentence
    # establishing the TYPING, and 10 of 26 archived variables were licensing
    # `impossible` for a scale range their quote never named -- one of them on
    # "(2) difficulties resisting eating (M = 2.79, SD = 1.42)". The fixture
    # gains a quote that actually states 1 and 7; see
    # tests/test_bounds_provenance.py for the new condition's own tests.
    BOUNDS = dict(id="v", name="item", family="likert_item",
                  lower_bound=1, upper_bound=7, confidence="high",
                  provenance_quote="rated from 1 (never) to 7 (always)")

    def test_high_confidence_alone_no_longer_buys_stated(self):
        v = Variable(**self.BOUNDS)                       # no verdict recorded
        assert v.bounds_are_stated() is False
        assert v.forensic_kwargs()["bound_source"] == "assumed"

    @pytest.mark.parametrize("verdict", ["verbatim", "elided"])
    def test_a_locatable_quote_licenses_stated(self, verdict):
        """Both verdicts mean a reader can open the paper and find the text."""
        v = Variable(**self.BOUNDS, provenance_verdict=verdict)
        assert v.forensic_kwargs()["bound_source"] == "stated"

    @pytest.mark.parametrize("verdict", ["stitched", "unverified", "absent"])
    def test_an_unlocatable_quote_does_not(self, verdict):
        """`stitched` means WE composed the sentence, so it evidences nothing
        about what the authors stated; `unverified` means our search failed,
        which is not evidence either way and so is not evidence FOR."""
        v = Variable(**self.BOUNDS, provenance_verdict=verdict)
        assert v.forensic_kwargs()["bound_source"] == "assumed"

    def test_the_model_cannot_supply_the_verdict_itself(self):
        """Declaring the field would have been decorative if the model could
        just write it: both record-building paths filter a model dict against
        the dataclass fields, so the laundering would simply move one level
        down. `PIPELINE_ONLY_FIELDS` strips it on both."""
        from metascience_agent.anatomy import anatomy_from_findings
        forged = {
            "paper_id": "p",
            "anatomy": {"variables": [dict(self.BOUNDS, provenance_verdict="verbatim")]},
        }
        v = anatomy_from_findings(forged).variables[0]
        assert v.provenance_verdict is None
        assert v.forensic_kwargs()["bound_source"] == "assumed"

    def test_the_dispatch_path_strips_it_too(self):
        """check_table's per-variable path is the OTHER constructor, and it is
        the only one stage 2 has."""
        from metascience_agent.dispatch import _as_variable
        v = _as_variable(dict(self.BOUNDS, provenance_verdict="verbatim"))
        assert v.provenance_verdict is None
        assert v.forensic_kwargs()["bound_source"] == "assumed"


class TestTheItemCountOnlyTravelsWhenItIsRight:
    """`items` multiplies the denominator, so emitting it is a claim.

    The one tool that accepts it, `r_grim_ground_truth`, tests at n*items. For a
    composite scored as the MEAN of k items that is the correct granularity. For
    one scored as a SUM it is 1/n, and passing items=k there checks the value k
    times more loosely than it should be -- a silent false NEGATIVE, the failure
    no reader of the report can see.

    This test previously asserted the opposite: that a composite with `n_items`
    and NO declared scoring emits `items`. That is the permissive direction on
    the one question the emission depends on.
    """

    def _composite(self, **over):
        return Variable(id="v", name="scale", family="likert_composite",
                        n_items=10, confidence="high", **over)

    def test_a_mean_of_items_passes_its_item_count(self):
        v = self._composite(derivation="mean_of_items")
        assert v.forensic_kwargs()["items"] == 10

    def test_a_sum_of_items_does_NOT(self):
        """A PHQ-9 total is an integer per subject; the group mean moves in
        steps of 1/n and n*10 would be nine tenths of a check."""
        v = self._composite(derivation="sum_of_items")
        assert "items" not in v.forensic_kwargs()

    def test_an_UNDECLARED_scoring_does_NOT(self):
        """We do not know which it is, and the two answers differ by 10x in the
        direction that hides things."""
        assert "items" not in self._composite().forensic_kwargs()
        assert "items" not in self._composite(derivation="").forensic_kwargs()
        assert "items" not in self._composite(derivation="measured").forensic_kwargs()

    def test_no_item_count_emits_nothing_regardless_of_scoring(self):
        v = Variable(id="v", name="scale", family="likert_composite",
                     derivation="mean_of_items")
        assert "items" not in v.forensic_kwargs()

    def test_only_one_registered_tool_accepts_items_at_all(self):
        """If a second one ever appears, this gate has to be re-argued for it
        rather than silently inherited."""
        from metascience_agent import registry as R
        takers = sorted(s.name for s in R.SPECS
                        if any(p.name == "items" for p in s.params))
        assert takers == ["r_grim_ground_truth"]

    def test_dispatch_still_re_exports_the_scoring_sets(self):
        """`dispatch.MEAN_SCORED` has callers; the canonical copy moved to
        anatomy so `forensic_kwargs` could reach it without a cycle."""
        from metascience_agent import anatomy, dispatch
        assert dispatch.MEAN_SCORED is anatomy.MEAN_SCORED
        assert dispatch.SUM_SCORED is anatomy.SUM_SCORED


class TestTheItemsCheckWeDidNotBuild:
    """MEASURED NEGATIVE. Do not plumb `items` into `grim_check`.

    The standing request was to give `grim_check` an `items` parameter so that a
    composite scored as the MEAN of k items could be checked at its true
    granularity of 1/(k*n) instead of being refused. The data-model objection
    that blocked it before is now GONE -- `derivation` reaches the dispatcher and
    distinguishes mean- from sum-scoring. The reason not to build it is different
    and worse:

    AT THE PRECISION PAPERS ACTUALLY REPORT, THE CHECK CANNOT FAIL. Multiplying
    the denominator by k pushes the effective n past the range where GRIM has any
    power at all, so the check would return `consistent` on everything.

    That is not a neutral outcome. Today a mean-scored composite is REFUSED, and
    a refusal is visible -- it says we could not check this. Building the plumbing
    would convert every one of those refusals into a clean bill of health issued
    by a test that has no way of returning anything else: a false all-clear
    machine, which the cardinal rule ranks second only to a false accusation.
    """

    def _failure_rate(self, k, n, dp, trials=1500, seed=0):
        import random

        from metascience_agent.tools.grim import grim_test
        rng = random.Random(seed)
        fails = 0
        for _ in range(trials):
            mean = round(rng.uniform(1.0, 7.0), dp)
            r = grim_test(mean, n * k, decimals=dp, data_type="likert",
                          discreteness_source="stated")
            if r.get("failure_mode") == "granularity":
                fails += 1
        return fails / trials

    @pytest.mark.parametrize("k,n", [(5, 30), (7, 50), (10, 30), (20, 30)])
    def test_it_has_ZERO_power_at_the_precision_papers_report(self, k, n):
        """2 decimal places, every realistic item count and sample size. Not
        "low power" -- not one failure in 1500 draws."""
        assert self._failure_rate(k, n, dp=2) == 0.0

    def test_the_archive_is_overwhelmingly_that_precision(self):
        """The measurement above is only damning if papers report composites to
        2dp, so this counts what the model has actually been sent."""
        import collections
        import glob
        import json
        dp = collections.Counter()
        for f in glob.glob("**/toolcalls.stage*.json", recursive=True):
            try:
                data = json.load(open(f))
            except Exception:  # noqa: BLE001, PERF203
                continue
            for c in (data if isinstance(data, list) else data.get("calls", [])):
                inp = c.get("input") or {}
                if "grim" in str(c.get("tool") or c.get("name") or ""):
                    with contextlib.suppress(KeyError, TypeError, ValueError):
                        dp[int(inp["decimals"])] += 1
        if not dp:
            pytest.skip("no archived runs in this checkout")
        coarse = sum(v for k, v in dp.items() if k <= 2)
        assert coarse / sum(dp.values()) > 0.85, dict(dp)

    def test_the_refusal_that_would_have_been_replaced_still_stands(self):
        """What a mean-scored composite gets today, and must keep getting: a
        refusal that says why, not a verdict."""
        from metascience_agent.dispatch import _composite_reason, _is_composite
        v = {"family": "likert_composite", "derivation": "mean_of_items"}
        assert _is_composite(v) is True
        assert "manufacture an impossibility" in _composite_reason(v)

    def test_a_sum_scored_composite_is_still_checked_normally(self):
        """The refusal must not have widened. A sum score needs no `items` and
        ordinary GRIM is correct on it."""
        from metascience_agent.dispatch import _is_composite
        assert _is_composite(
            {"family": "likert_composite", "derivation": "sum_of_items"}) is False


class TestNarrativeRanking:
    """Tests are not created equal -- rank by what they carry."""

    def test_stated_primary_outcome_is_primary(self):
        t = StatisticalTest(id="t", test_type="chi_squared", is_stated_primary_outcome=True)
        assert infer_narrative_tier(t) == "primary"

    def test_abstract_presence_is_primary(self):
        t = StatisticalTest(id="t", test_type="chi_squared", appears_in_abstract=True)
        assert infer_narrative_tier(t) == "primary"

    def test_preregistered_hypothesis_is_primary(self):
        t = StatisticalTest(id="t", test_type="chi_squared", hypothesis_id="h1")
        h = Hypothesis(id="h1", statement="x", status="preregistered_confirmatory")
        assert infer_narrative_tier(t, h) == "primary"

    def test_unremarked_test_is_incidental(self):
        assert infer_narrative_tier(StatisticalTest(id="t", test_type="chi_squared")) == "incidental"

    def test_default_tier_does_not_shadow_inference(self):
        """Regression: a truthy default made `tier or infer(...)` never infer."""
        a = _anatomy()
        a.tests = [StatisticalTest(id="t", test_type="chi_squared", outcome_var="v_bin",
                                   is_stated_primary_outcome=True, confidence="high")]
        assert build_test_table(a)[0]["tier"] == "primary"

    def test_weighting_never_escalates_severity(self):
        w = weight_finding_severity("suspicious", "primary")
        assert w["severity"] == "suspicious"          # unchanged
        assert w["undermines_headline_claim"] is True


def _mult(pvals, alpha=0.05, family="the family under test"):
    """Build a family from bare p-values and report on it.

    `family_label` has no default -- the tool refuses without one, because a
    default of "all reported tests" was the exact pooling its own description
    told the model not to do -- so every call has to state a family.
    """
    tests = [StatisticalTest(id=f"t{i}", test_type="chi_squared", p_value=p)
             for i, p in enumerate(pvals)]
    return multiplicity_report(tests, family, alpha=alpha)


class TestMultiplicity:
    def test_arithmetic_is_correct(self):
        m = _mult([0.5] * 20, alpha=0.05)
        assert m["n_tests"] == 20
        assert m["expected_false_positives"] == pytest.approx(1.0)
        assert m["bonferroni_threshold"] == pytest.approx(0.0025)
        assert m["fwer_if_independent"] == pytest.approx(1 - 0.95**20, abs=1e-4)

    def test_author_corrected_tests_are_excluded(self):
        tests = [StatisticalTest(id="a", test_type="chi_squared", p_value=0.01,
                                 correction_applied="bonferroni"),
                 StatisticalTest(id="b", test_type="chi_squared", p_value=0.01)]
        assert multiplicity_report(tests, "two tests, one already corrected")["n_tests"] == 1

    def test_bh_is_less_conservative_than_bonferroni(self):
        m = _mult([0.001, 0.008, 0.02, 0.04, 0.3, 0.6])
        assert m["n_significant_bh"] >= m["n_significant_bonferroni"]
        assert m["n_significant_uncorrected"] >= m["n_significant_bh"]

    def test_caveats_are_always_stated(self):
        m = _mult([0.1])
        assert any("judgement" in c for c in m["caveats"])
        assert any("independence" in c.lower() for c in m["caveats"])

    def test_empty_family_is_handled(self):
        assert multiplicity_report([], "an empty family")["n_tests"] == 0

    def test_family_label_has_no_default(self):
        """Retired deliberately. The default pooled every test in the paper into
        one family, which is what the tool's own description forbids."""
        with pytest.raises(TypeError):
            multiplicity_report([StatisticalTest(id="t", test_type="chi_squared", p_value=0.01)])


class TestTheFamilyGateHoldsOnEverySurface:
    """A guard only one caller honours is not a guard.

    `registry` declares `family_label` MANDATORY and `_multiplicity_adapter`
    refuses a blank one over MCP. The hand-written `multiplicity` verb once
    printed the full correction table -- FWER, Bonferroni, Holm, BH, BY, claim
    loss -- under an empty `Family:` heading and exited 0: refused on one
    surface, answered on the other. Since 1.95.0 the command line is
    `metascience tool run`, which goes through the same gate; these pin that.
    """

    TESTS = [{"id": "t1", "p_value": 0.01}, {"id": "t2", "p_value": 0.04},
             {"id": "t3", "p_value": 0.2}]

    def _run(self, family_label, tests=None):
        import json as _json
        r = CliRunner().invoke(cli_app, [
            "tool", "run", "multiplicity_report", "--json",
            _json.dumps({"tests": tests or self.TESTS, "family_label": family_label})])
        assert r.exit_code == 0, r.output
        verdict, _, body = r.output.partition("\n")
        return verdict, _json.loads(body)

    def test_blank_family_label_is_refused_by_the_cli(self):
        verdict, out = self._run("")
        assert verdict.startswith("INDETERMINATE")
        # The arithmetic must not appear at all. A refusal that still prints the
        # numbers reads as a warning, and the numbers get quoted anyway.
        assert out["applicable"] is False
        assert not any("bonferroni" in k.lower() for k in out)

    def test_whitespace_only_family_label_is_refused_by_the_cli(self):
        assert self._run("   ")[1]["applicable"] is False

    def test_the_cli_refusal_says_why_a_family_cannot_be_defaulted(self):
        verdict, _ = self._run("")
        assert "judgement" in verdict
        assert "family" in verdict.lower()

    def test_the_two_surfaces_refuse_the_same_input(self):
        """MCP and CLI, same blank label, same outcome."""
        mcp = BY_NAME["multiplicity_report"].call(
            {"tests": [{"id": "t1", "p_value": 0.01}], "family_label": ""})
        assert mcp["applicable"] is False and mcp.get("error")
        assert self._run("", tests=[{"id": "t1", "p_value": 0.01}])[1]["applicable"] is False

    def test_a_named_family_still_runs(self):
        _, out = self._run("three primary outcomes")
        assert out.get("applicable") is not False
        assert "three primary outcomes" in str(out)


class TestAssumptions:
    """Unreported checks are the norm; only conjunctions are informative."""

    def test_unreported_alone_is_not_a_finding(self):
        a = _anatomy()
        t = StatisticalTest(id="t", test_type="independent_t", outcome_var="v_bp", n=500)
        assert assumption_risk(t, a.variable("v_bp"))["severity"] == "consistent"

    def test_conjunction_escalates(self):
        a = _anatomy()
        t = StatisticalTest(id="t", test_type="independent_t", outcome_var="v_lik", n=12)
        r = assumption_risk(t, a.variable("v_lik"), a.studies[0])
        assert r["severity"] == "suspicious"
        assert len(r["reasons"]) >= 2

    def test_nonparametric_is_exempt(self):
        a = _anatomy()
        t = StatisticalTest(id="t", test_type="mann_whitney", outcome_var="v_lik", n=12)
        assert assumption_risk(t, a.variable("v_lik"))["severity"] == "consistent"

    def test_reported_checks_clear_the_flag(self):
        a = _anatomy()
        t = StatisticalTest(id="t", test_type="independent_t", outcome_var="v_lik", n=12,
                            assumption_checks_reported=list(
                                StatisticalTest(id="x", test_type="independent_t").required_assumptions()))
        assert assumption_risk(t, a.variable("v_lik"))["severity"] == "consistent"


class TestTestVariableCompatibility:
    def test_pearson_on_ordinal_is_flagged(self):
        a = _anatomy()
        t = StatisticalTest(id="t", test_type="pearson_correlation", outcome_var="v_lik",
                            confidence="high")
        r = check_test_variable_compatibility(t, a)
        assert r["severity"] == "suspicious" and "Spearman" in r["problems"][0]

    def test_logistic_on_continuous_outcome_is_flagged(self):
        a = _anatomy()
        t = StatisticalTest(id="t", test_type="logistic_regression", outcome_var="v_bp",
                            confidence="high")
        assert check_test_variable_compatibility(t, a)["severity"] == "suspicious"

    def test_low_confidence_extraction_never_accuses(self):
        """An uncertain extraction must not become a methodological accusation."""
        a = _anatomy()
        t = StatisticalTest(id="t", test_type="pearson_correlation", outcome_var="v_lik",
                            confidence="low")
        assert check_test_variable_compatibility(t, a)["severity"] == "indeterminate"

    def test_appropriate_pairing_passes(self):
        a = _anatomy()
        t = StatisticalTest(id="t", test_type="logistic_regression", outcome_var="v_bin",
                            confidence="high")
        assert check_test_variable_compatibility(t, a)["severity"] == "consistent"


def test_summary_is_complete_and_sorted():
    a = _anatomy()
    a.tests = [
        StatisticalTest(id="lo", test_type="chi_squared", outcome_var="v_bin", p_value=0.4),
        StatisticalTest(id="hi", test_type="chi_squared", outcome_var="v_bin", p_value=0.01,
                        is_stated_primary_outcome=True, confidence="high"),
    ]
    s = anatomy_summary(a)
    assert s["counts"]["tests"] == 2
    assert s["test_table"][0]["id"] == "hi"          # primary first
    assert "multiplicity_overall" in s
    assert "lo" in s["low_confidence_extractions"]   # no quote/confidence => flagged


class TestMultiplicityAgainstR:
    """Mutation testing showed BH could be replaced with `p <= alpha` and the
    suite still passed. Pin the arithmetic to R's p.adjust instead of to our
    own implementation."""

    #: The four methods, as our key and R's `p.adjust` name for each. R
    #: implements all four, so there is no method here we have to trust
    #: ourselves on.
    METHODS = (
        ("n_significant_bonferroni", "bonferroni"),
        ("n_significant_holm", "holm"),
        ("n_significant_bh", "BH"),
        ("n_significant_by", "BY"),
    )

    @classmethod
    def _r_counts(cls, pvals, alpha=0.05):
        """Counts of p.adjust(...) <= alpha, one per method, in METHODS order.

        `<=`, not `<`: strict `<` disagreed with R on 30 of 3012 fuzzed vectors
        (five tests all at p=.01 against a Bonferroni threshold of exactly .01),
        and the same boundary exists in all four methods.
        """
        import shutil, subprocess
        if not shutil.which("Rscript"):
            pytest.skip("R not available")
        vec = ",".join(repr(float(p)) for p in pvals)
        code = f"p<-c({vec});cat(" + ",".join(
            f"sum(p.adjust(p,method='{r_name}')<={alpha})" for _, r_name in cls.METHODS
        ) + ")"
        out = subprocess.run(["Rscript", "-e", code], capture_output=True, text=True).stdout.split()
        return [int(x) for x in out]

    @pytest.mark.parametrize("pvals", [
        [0.01] * 5,
        [0.001, 0.008, 0.02, 0.04, 0.3, 0.6],
        [0.05, 0.05, 0.05],
        [0.0001, 0.9, 0.9, 0.9, 0.9],
        [0.02, 0.03, 0.04, 0.045, 0.049],
        [0.5],
        # Holm strictly beats Bonferroni here: .02 clears alpha/2 = .025 and
        # .03 then clears alpha/1, so Holm rejects both and Bonferroni one.
        [0.02, 0.03],
        # Holm's step-down STOP: .02 fails alpha/3, so .04 is retained despite
        # clearing alpha/1.
        [0.02, 0.03, 0.04],
        # The case that killed "BY sits between Bonferroni and BH": BY's first
        # step-up threshold is alpha/(m*c(m)) = .0167, so Bonferroni and Holm
        # reject one result here and BY rejects none.
        [0.02, 0.90],
    ])
    def test_matches_r_p_adjust(self, pvals):
        r_counts = self._r_counts(pvals)
        m = _mult(pvals)
        assert [m[key] for key, _ in self.METHODS] == r_counts

    def test_matches_r_p_adjust_on_fuzzed_families(self, tmp_path):
        """One Rscript call over 200 random families, because a handful of
        hand-picked vectors is exactly what let a broken BH survive mutation
        testing. Batched into a single subprocess: 200 separate `Rscript -e`
        invocations cost about a minute of suite time for the same evidence.
        """
        import random, shutil, subprocess
        if not shutil.which("Rscript"):
            pytest.skip("R not available")
        rng = random.Random(11)
        families = [[round(rng.random(), 4) for _ in range(rng.randint(1, 30))]
                    for _ in range(200)]
        # Built as a literal R list rather than parsed from JSON: `jsonlite` is
        # not part of base R and a skipped cross-check is worth nothing.
        r_list = ",".join("c(" + ",".join(repr(float(p)) for p in f) + ")" for f in families)
        methods = ",".join(f"'{r_name}'" for _, r_name in self.METHODS)
        code = (
            f"fams<-list({r_list})\n"
            f"out<-sapply(fams,function(p) sapply(c({methods}),"
            "function(mm) sum(p.adjust(p,method=mm)<=0.05)))\n"
            "cat(paste(out,collapse=' '))\n"
        )
        # Written to a FILE, not passed to `Rscript -e`. Rscript truncates a -e
        # expression at 4096 bytes and echoes the truncated text to stdout with
        # a WARNING, which parsed as a silent partial cross-check rather than a
        # failure. This payload is ~23 kB.
        script = tmp_path / "p_adjust_cross_check.R"
        script.write_text(code)
        proc = subprocess.run(["Rscript", str(script)], capture_output=True, text=True)
        assert proc.returncode == 0, proc.stderr.strip()[:400]
        flat = [int(x) for x in proc.stdout.split()]
        assert len(flat) == len(families) * len(self.METHODS)
        for i, pvals in enumerate(families):
            expected = flat[i * len(self.METHODS):(i + 1) * len(self.METHODS)]
            m = _mult(pvals)
            assert [m[key] for key, _ in self.METHODS] == expected, pvals

    def test_the_ordering_the_bound_rests_on(self):
        """Bonferroni <= Holm <= BH <= uncorrected, and BY <= BH.

        These are the orderings that are ARITHMETIC, not convention, so the
        floor/ceiling pair can be trusted. BY vs Bonferroni is deliberately
        absent: it is order-free, and asserting it would encode the textbook
        story the implementation had to abandon.
        """
        import random
        rng = random.Random(11)
        for _ in range(200):
            pvals = [round(rng.random(), 4) for _ in range(rng.randint(1, 30))]
            m = _mult(pvals)
            assert m["n_significant_bonferroni"] <= m["n_significant_holm"]
            assert m["n_significant_holm"] <= m["n_significant_bh"]
            assert m["n_significant_by"] <= m["n_significant_bh"]
            assert m["n_significant_bh"] <= m["n_significant_uncorrected"]
            assert m["n_surviving_floor"] <= m["n_surviving_ceiling"]
            assert m["n_surviving_ceiling"] <= m["n_significant_uncorrected"]
            assert m["internal_inconsistency"] is False

    def test_by_can_be_stricter_than_bonferroni_so_the_floor_is_computed(self):
        """The reason `n_surviving_floor` is a min() and not the Bonferroni count.

        Measured against R over 5,000 random p-vectors (m in 1..30, alpha=.05),
        BY rejected fewer than Holm on 141 -- 2.8%. Hard-coding Bonferroni as
        the floor would have reported a floor ABOVE a number in the same dict.
        """
        m = _mult([0.02, 0.90])
        assert m["n_significant_bonferroni"] == 1 and m["n_significant_holm"] == 1
        assert m["n_significant_by"] == 0
        assert m["n_surviving_floor"] == 0 and m["floor_method"] == "Benjamini-Yekutieli"
        assert m["n_surviving_ceiling"] == 1

    def test_holm_stops_at_the_first_failure(self):
        """Step-down, not "count everything that clears its own threshold".

        m=3, so the step thresholds are .01667, .025, .05. p_(1) = .02 fails the
        first, so the whole family is retained -- even though p_(3) = .04 clears
        its own step of alpha/1. A loop that kept testing past the first failure
        would report 1 here, and it would not be Holm.
        """
        m = _mult([0.02, 0.03, 0.04])
        assert m["n_significant_holm"] == 0
        assert m["n_significant_uncorrected"] == 3

    def test_the_bound_is_reported_not_a_single_number(self):
        m = _mult([0.001, 0.008, 0.02, 0.04, 0.3, 0.6])
        assert "between" in m["interpretation"]
        for name in ("Bonferroni", "Holm", "Benjamini-Hochberg", "Benjamini-Yekutieli"):
            assert name in m["interpretation"]
        assert m["n_claims_lost_to_correction"] == (
            m["n_significant_uncorrected"] - m["n_significant_bh"]
        )

    def test_none_string_is_not_a_correction(self):
        """Regression: the schema documents 'none', and 'none' is truthy."""
        for label in ("none", "None", "NONE", "", None, "n/a"):
            tests = [StatisticalTest(id=f"t{i}", test_type="chi_squared", p_value=0.01,
                                     correction_applied=label) for i in range(40)]
            assert multiplicity_report(tests, "forty tests")["n_tests"] == 40, (
                f"{label!r} dropped the family")
        tests = [StatisticalTest(id="t", test_type="chi_squared", p_value=0.01,
                                 correction_applied="bonferroni")]
        assert multiplicity_report(tests, "one corrected test")["n_tests"] == 0

    def test_every_method_uses_family_size_not_readable_p_count(self):
        tests = ([StatisticalTest(id="p", test_type="chi_squared", p_value=0.04)]
                 + [StatisticalTest(id=f"x{i}", test_type="chi_squared") for i in range(99)])
        m = multiplicity_report(tests, "100 tests, 1 with a readable p")
        assert m["n_tests"] == 100 and m["n_missing_p"] == 99
        assert m["n_significant_bh"] == 0     # 0.04 > (1/100)*0.05
        assert m["n_significant_by"] == 0
        assert m["n_significant_holm"] == 0    # 0.04 > 0.05/100
        assert m["n_significant_bonferroni"] == 0


class TestAssumptionGateIsNotArbitrary:
    """The >=2 conjunction must reflect INDEPENDENT factors, and large n must
    neutralise normality concerns (CLT)."""

    def test_large_n_never_escalates_on_distributional_grounds(self):
        v = Variable(id="v", name="item", family="likert_item", measurement_level="ordinal",
                     lower_bound=1, upper_bound=5, confidence="high")
        for n in (100, 1_000, 1_000_000):
            r = assumption_risk(StatisticalTest(id="t", test_type="independent_t",
                                                outcome_var="v", n=n), v)
            assert r["severity"] == "consistent", f"escalated at n={n}"

    def test_one_fact_is_not_counted_twice(self):
        """'ordinal' and 'bounded' are the same fact for a Likert item."""
        v = Variable(id="v", name="item", family="likert_item", measurement_level="ordinal",
                     lower_bound=1, upper_bound=5, confidence="high")
        r = assumption_risk(StatisticalTest(id="t", test_type="independent_t",
                                            outcome_var="v", n=60), v)
        assert len(r.get("risk_factors", [])) <= 1

    def test_human_readable_check_labels_are_honoured(self):
        v = Variable(id="v", name="item", family="likert_item", lower_bound=1,
                     upper_bound=5, confidence="high")
        t = StatisticalTest(id="t", test_type="independent_t", outcome_var="v", n=12,
                            assumption_checks_reported=["Shapiro-Wilk test", "Levene's test",
                                                        "ICC reported"])
        assert assumption_risk(t, v)["severity"] == "consistent"

    def test_assumption_map_is_not_junk(self):
        """Independent of required_assumptions(), so a corrupted map is caught."""
        t = StatisticalTest(id="t", test_type="independent_t")
        assert "normality" in t.required_assumptions()
        assert "homogeneity_of_variance" in t.required_assumptions()
        assert "proportional_hazards" in StatisticalTest(
            id="t", test_type="cox_regression").required_assumptions()
        # Scale preconditions belong to the compatibility check, not here.
        assert "interval_or_ratio_outcome" not in t.required_assumptions()

    def test_rank_based_only_exempted(self):
        v = Variable(id="v", name="x", family="binary", confidence="high")
        assert assumption_risk(StatisticalTest(id="t", test_type="mann_whitney",
                                               outcome_var="v", n=10), v)["severity"] == "consistent"
        cox = assumption_risk(StatisticalTest(id="t", test_type="cox_regression",
                                              outcome_var="v", n=200), v)
        assert "does not assume normality" in cox["note"]


class TestCompatibilityIsConservative:
    @pytest.mark.parametrize("test_type,family,expected", [
        ("pearson_correlation", "likert_composite", "consistent"),   # standard psychometrics
        ("linear_regression", "binary", "consistent"),               # linear probability model
        ("chi_squared", "nominal_category", "consistent"),
        ("logistic_regression", "binary", "consistent"),
        ("pearson_correlation", "likert_item", "suspicious"),        # single ordinal item
        ("logistic_regression", "continuous", "suspicious"),
    ])
    def test_legitimate_practice_is_not_flagged(self, test_type, family, expected):
        a = PaperAnatomy(paper_id="p")
        a.variables = [Variable(id="v", name="y", family=family, confidence="high")]
        t = StatisticalTest(id="t", test_type=test_type, outcome_var="v", confidence="high")
        assert check_test_variable_compatibility(t, a)["severity"] == expected

    def test_unknown_family_never_accuses(self):
        a = PaperAnatomy(paper_id="p")
        a.variables = [Variable(id="v", name="mortality", confidence="high")]  # family defaults unknown
        t = StatisticalTest(id="t", test_type="logistic_regression", outcome_var="v",
                            confidence="high")
        r = check_test_variable_compatibility(t, a)
        assert r["severity"] == "indeterminate" and r["problems"] == []

    @pytest.mark.parametrize("conf", ["low", "Low", "LOW", ""])
    def test_confidence_gate_is_case_insensitive(self, conf):
        a = PaperAnatomy(paper_id="p")
        a.variables = [Variable(id="v", name="y", family="likert_item", confidence="high")]
        t = StatisticalTest(id="t", test_type="pearson_correlation", outcome_var="v",
                            confidence=conf)
        assert check_test_variable_compatibility(t, a)["severity"] == "indeterminate"


class TestAssumptionsAreStatedNotJustCounted:
    """Greg, 2026-08-09: the statistical-test section must give "the set of
    assumptions for each test", e.g. parametric tests assuming normality of the
    distribution of means, homoscedasticity.

    The table reported only the assumptions that went UNREPORTED -- the
    complement. A reader could see `normality` listed as unchecked without ever
    being told that this test assumes it, or what normality means HERE: for an
    independent t-test it is the sampling distribution of the mean difference,
    for a paired test the differences, for a regression the residuals. Three
    different claims sharing one token.
    """

    def _anatomy(self, *test_types):
        from metascience_agent.anatomy import PaperAnatomy, StatisticalTest, Study, Variable
        a = PaperAnatomy(paper_id="p")
        a.studies = [Study(id="s1", label="trial", design="parallel_rct", n=100)]
        a.variables = [Variable(id="v1", name="score", family="continuous",
                                role="outcome")]
        a.tests = [
            StatisticalTest(id=f"t{i}", test_type=tt, location=f"Table {i}",
                            study_id="s1", outcome_var="v1", n=100, p_value="0.03")
            for i, tt in enumerate(test_types)
        ]
        return a

    def test_every_assumption_token_has_a_plain_language_description(self):
        """A token with no description would render as a bare label like
        `homogeneity_of_regression_slopes`, which tells a reader nothing."""
        from metascience_agent.anatomy import ASSUMPTION_DESCRIPTIONS, TEST_ASSUMPTIONS
        used = set().union(*TEST_ASSUMPTIONS.values())
        assert not sorted(used - set(ASSUMPTION_DESCRIPTIONS))

    def test_the_required_set_reaches_the_table_row(self):
        from metascience_agent.anatomy import build_test_table
        row = build_test_table(self._anatomy("independent_t"))[0]
        assert set(row["assumptions_required"]) == {
            "normality", "homogeneity_of_variance", "independence"}

    def test_the_rendered_report_states_them_in_words(self):
        from metascience_agent.anatomy import render_anatomy_markdown
        md = render_anatomy_markdown(self._anatomy("independent_t"))
        assert "What each of these tests assumes" in md
        assert "Homogeneity of variance" in md
        assert "sampling distribution of the group means" in md

    def test_each_test_type_is_described_once_not_once_per_test(self):
        """A paper with 40 t-tests has one assumption set; printing it 40 times
        would bury it."""
        from metascience_agent.anatomy import render_anatomy_markdown
        md = render_anatomy_markdown(self._anatomy(*["independent_t"] * 5))
        assert md.count("**independent_t**") == 1

    def test_distinct_test_types_each_get_their_own_set(self):
        from metascience_agent.anatomy import render_anatomy_markdown
        md = render_anatomy_markdown(self._anatomy("independent_t", "chi_squared"))
        assert "**independent_t**" in md and "**chi_squared**" in md
        assert "expected cell counts" in md

    def test_the_section_says_these_are_not_accusations(self):
        """Unreported assumption checks are near-universal; a bare list of
        assumptions beside a forensic report would read as a charge sheet."""
        from metascience_agent.anatomy import render_anatomy_markdown
        md = render_anatomy_markdown(self._anatomy("independent_t"))
        assert "not as findings against the paper" in md

    def test_an_unknown_token_is_echoed_rather_than_dropped(self):
        """A silently missing assumption is worse than an unpolished one, and
        dropping it would also hide a typo in TEST_ASSUMPTIONS."""
        from metascience_agent.anatomy import describe_assumptions
        assert describe_assumptions(["not_a_real_token"]) == ["not_a_real_token"]


class TestNoDeclaredFieldIsSilentlyDiscarded:
    """The model is asked for these. Something must keep them.

    `derivation` was in the schema, in the prompt, rendered to the reader and
    covered by a test -- and `Variable` had no such field, so both loaders
    (`_pick` and `dispatch._as_variable`, which filter to
    `__dataclass_fields__`) deleted every declaration before a check could see
    it. It cost a real detection: the composite refusal could not tell a sum
    score from an item mean, and suppressed a correct `impossible`.

    Four more fields were being dropped the same way. This test is the mechanism
    that stops a tenth instance: a schema property must be a dataclass field, or
    it must name itself below with a reason.
    """

    #: schema property -> why nothing loads it. Empty, and it should stay that
    #: way; an entry here is a decision to throw away something we asked for.
    DISCARDED: dict[tuple[str, str], str] = {}

    @staticmethod
    def _pairs():
        import json
        from pathlib import Path

        from metascience_agent.anatomy import (
            Hypothesis,
            StatisticalTest,
            Study,
            Variable,
        )
        root = Path(__file__).resolve().parents[1]
        schema = json.loads(
            (root / "src" / "metascience_agent" / "schema"
             / "findings.v2.schema.json").read_text(encoding="utf-8"))
        anatomy = schema["properties"]["anatomy"]["properties"]
        return anatomy, [("variables", Variable), ("tests", StatisticalTest),
                         ("studies", Study), ("hypotheses", Hypothesis)]

    def test_every_schema_property_survives_loading(self):
        anatomy, pairs = self._pairs()
        offenders = []
        for key, cls in pairs:
            node = anatomy.get(key) or {}
            props = set((node.get("items") or {}).get("properties") or {})
            for prop in sorted(props - set(cls.__dataclass_fields__)):
                if (key, prop) not in self.DISCARDED:
                    offenders.append(f"{key}.{prop}")
        assert not offenders, (
            f"the schema asks the model for {offenders} and no dataclass field "
            f"keeps them, so both loaders discard them on read. Add the field, "
            f"or add it to DISCARDED with a reason."
        )

    def test_the_field_whose_absence_cost_a_detection_is_present(self):
        from metascience_agent.anatomy import Variable
        assert "derivation" in Variable.__dataclass_fields__

    def test_every_discard_states_a_reason(self):
        for key, reason in self.DISCARDED.items():
            assert len(reason) > 60, f"{key} needs a real reason"


class TestAnAssumptionDenialIsNotAnAssumptionCheck:
    """`ASSUMPTION_SYNONYMS` says which assumption a phrase is ABOUT. It used
    to be read as proof the check was RUN, and every match suppresses an entry
    from `unreported_assumptions()` -- so a sentence saying nothing was checked
    produced `assumption risk: consistent` and the note "Required assumption
    checks were reported." The house failure mode with the sign flipped: a
    denial rendered as a clean bill of health.
    """

    FOOL = ["Neither normality nor homogeneity of variance was examined, "
            "and independence cannot be assumed."]

    def test_the_denial_no_longer_clears_the_required_checks(self):
        from metascience_agent.anatomy import StatisticalTest
        t = StatisticalTest(id="t1", test_type="independent_t",
                            assumption_checks_reported=list(self.FOOL))
        assert set(t.unreported_assumptions()) == {
            "normality", "homogeneity_of_variance", "independence"}

    def test_the_denial_is_KEPT_not_merely_dropped(self):
        """A stated non-check is information about the paper. Discarding it
        would be this codebase's own error in the other direction."""
        from metascience_agent.anatomy import denied_assumption_labels
        assert denied_assumption_labels(self.FOOL) == {
            "normality", "homogeneity_of_variance", "independence"}

    def test_negation_scopes_over_a_LIST_not_just_the_first_item(self):
        """The first attempt cut on commas so a denial could not leak between
        list items, and thereby broke the commonest denial there is."""
        from metascience_agent.anatomy import classify_assumption_mentions as C
        r = C(["No checks of normality, homogeneity of variance or linearity "
               "were reported."])
        assert r["checked"] == set()
        assert r["denied"] == {"normality", "homogeneity_of_variance", "linearity"}

    def test_negation_scopes_BACKWARD_over_the_subjects_it_negates(self):
        from metascience_agent.anatomy import classify_assumption_mentions as C
        r = C(["Normality and sphericity were not assessed."])
        assert r["denied"] == {"normality", "sphericity"}

    def test_an_adversative_ends_the_negation_scope(self):
        from metascience_agent.anatomy import classify_assumption_mentions as C
        r = C(["Normality was assessed with Shapiro-Wilk, but sphericity was "
               "not tested."])
        assert "normality" in r["checked"]
        assert "sphericity" in r["denied"]

    def test_a_negative_RESULT_is_not_a_refusal_to_check(self):
        """"No violations of normality were found" means the authors looked.
        Reading its "no" as a denial would turn an affirmative report into a
        missing one -- the same shape as `artefacts._NO_DEVIATION`."""
        from metascience_agent.anatomy import classify_assumption_mentions as C
        assert "normality" in C(["No violations of normality were found."])["checked"]
        assert "sphericity" in C(
            ["The sphericity assumption was not violated."])["checked"]

    def test_a_plain_list_of_real_checks_still_clears(self):
        from metascience_agent.anatomy import normalize_assumption_labels as N
        assert N(["Levene's test, Shapiro-Wilk, and Q-Q plots were inspected"]) == {
            "homogeneity_of_variance", "normality"}

    def test_plurals_match(self):
        """Papers write "Outliers were not examined"; a bare word boundary on
        the singular key missed it, costing both the suppression and the
        denial."""
        from metascience_agent.anatomy import classify_assumption_mentions as C
        assert C(["Outliers were not examined."])["denied"] == {"no_outliers"}
        assert C(["Outliers were inspected."])["checked"] == {"no_outliers"}


class TestPolysemousAssumptionKeys:
    """Four keys were removed or narrowed because they are ambiguous in this
    literature. Counts are over the 309-paper cerebrolysin corpus body text --
    which establishes that the words are ambiguous here, not the rate at which
    they would mislead in the model's short entries."""

    # (name, entry, the canonical token it must NOT produce)
    MUST_NOT_MATCH = [
        ("morphine tolerance, and Stata's solver parameter tolerance (308 hits)",
         "Morphine tolerance developed over nine days", "no_multicollinearity"),
        ("Fisher's z transformation and post hoc Fisher/LSD (170 hits)",
         "Fisher's z transformation was applied", "expected_cell_counts_ge_5"),
        ("Schwann-cell and hierarchical clustering (36 hits)",
         "Participants were grouped by hierarchical clustering.", "independence"),
        ("Stata's `leverage` option, and the plain verb (10 hits)",
         "We leverage our large database for matching", "no_outliers"),
    ]
    MUST_STILL_MATCH = [
        ("Fisher's exact", "Fisher's exact test was used", "expected_cell_counts_ge_5"),
        ("leverage values", "Leverage values and Cook's distance were inspected",
         "no_outliers"),
        ("ICC", "ICC was computed", "independence"),
        ("cluster-robust SEs", "Cluster-robust standard errors were used",
         "independence"),
    ]

    def test_an_ambiguous_word_does_not_clear_an_assumption(self):
        from metascience_agent.anatomy import classify_assumption_mentions as C
        wrong = [(n, tok) for n, entry, tok in self.MUST_NOT_MATCH
                 if tok in (C([entry])["checked"] | C([entry])["denied"])]
        assert not wrong, f"polysemous keys still firing: {wrong}"

    def test_the_specific_forms_still_clear(self):
        from metascience_agent.anatomy import normalize_assumption_labels as N
        missing = [(n, tok) for n, entry, tok in self.MUST_STILL_MATCH
                   if tok not in N([entry])]
        assert not missing, f"narrowing the keys broke real checks: {missing}"

    def test_a_short_key_cannot_match_inside_a_word(self):
        """`in` matching let "icc" clear `independence` from any word
        containing those three letters."""
        from metascience_agent.anatomy import normalize_assumption_labels as N
        assert "independence" not in N(["Patients reported hiccups"])


class TestTheNamedOutlierTestsAreRecognised:
    """`ASSUMPTION_SYNONYMS` knew the outlier DIAGNOSTICS (Cook's distance,
    leverage, the bare word) and none of the named outlier TESTS, so a paper
    that ran one was still told it had not checked for outliers.

    SAFETY DIRECTION, AND IT IS ONE-WAY BY CONSTRUCTION. Every match here can
    only remove `no_outliers` from `unreported_assumptions()`; nothing in this
    table can add a required assumption or raise a verdict. `pearson_correlation`
    is the fixture because it is the test whose required set names `no_outliers`.
    """

    PHRASES = ["Grubbs' test was applied to the residuals.",
               "Grubbs test was performed on each variable.",
               "Grubbs's test was used.",
               "Dixon's Q test was run on the smallest sample.",
               "Dixon Q test was applied.",
               "Outliers were screened with Dixon's Q.",
               "The Tietjen-Moore test was used for multiple outliers.",
               "A Tietjen Moore test was applied.",
               "We used the generalized extreme studentized deviate procedure.",
               "The generalised extreme studentized deviate approach was used.",
               "A GESD test screened for extreme values."]

    def _test(self, reported):
        from metascience_agent.anatomy import StatisticalTest
        return StatisticalTest(id="t1", test_type="pearson_correlation",
                               assumption_checks_reported=list(reported))

    def test_without_a_check_the_claim_stands(self):
        """The control: `no_outliers` is genuinely claimed when nothing says
        otherwise, so a suppression below is a real change and not a fixture
        that never carried the claim."""
        assert "no_outliers" in self._test([]).unreported_assumptions()

    @pytest.mark.parametrize("phrase", PHRASES)
    def test_each_phrasing_suppresses_the_false_claim(self, phrase):
        from metascience_agent.anatomy import normalize_assumption_labels
        assert "no_outliers" in normalize_assumption_labels([phrase]), phrase
        assert "no_outliers" not in self._test([phrase]).unreported_assumptions()

    @pytest.mark.parametrize("phrase", PHRASES)
    def test_no_unrelated_assumption_is_affected(self, phrase):
        """The other two assumptions `pearson_correlation` requires must still
        be reported as unchecked -- a synonym may clear its own token and
        nothing else."""
        got = set(self._test([phrase]).unreported_assumptions())
        assert got == {"normality", "linearity"}, phrase

    def test_a_denial_of_a_named_test_still_does_not_clear_it(self):
        """The `classify_assumption_mentions` rule applies to the new keys like
        any other: naming a test the paper says it did NOT run is not a check."""
        from metascience_agent.anatomy import classify_assumption_mentions as C
        r = C(["Grubbs' test was not performed."])
        assert "no_outliers" not in r["checked"]
        assert "no_outliers" in r["denied"]
        assert "no_outliers" in self._test(["Grubbs' test was not performed."]
                                           ).unreported_assumptions()

    def test_the_polysemous_bare_forms_were_deliberately_not_added(self):
        """The 2026-08-18 discipline, applied to these four: a bare surname and
        a bare `Q test` (Cochran's Q, the heterogeneity Q) are not outlier
        evidence, and adding them would suppress a true claim."""
        from metascience_agent.anatomy import ASSUMPTION_SYNONYMS
        for bare in ("grubbs", "dixon", "q test", "tietjen", "moore", "deviate"):
            assert bare not in ASSUMPTION_SYNONYMS


class TestTheTwoTestVocabulariesCoverTheSameUniverse:
    """`schema.TEST_FAMILIES` (the scaffold's closed enum for
    `comparison.test_type_stated`) and `anatomy.TEST_ASSUMPTIONS` (the legacy
    free-string vocabulary the assumption checker keys on) were written at
    different times and disagreed on BOTH membership and spelling: of 19
    families only 8 were assumption keys, and `independent_t` / `t_test_independent`
    are the same test under two names.

    Two separate consequences, and they run in opposite directions:
    * A paper running an ANCOVA, McNemar, Cox regression or log-rank test could
      not NAME that test in a scaffold account -- the enum offered no member, so
      it collapsed to `other`.
    * A test named in the scaffold's spelling and read on the legacy path
      (`test_type` is a free string there, not an enum) missed its assumption
      list entirely and fell through the fail-closed gate to `indeterminate`.
    """

    def _test(self, test_type, **kw):
        return StatisticalTest(id="t1", test_type=test_type, location="Results",
                               study_id="s1", outcome_var="v1", n=100, **kw)

    def test_every_family_is_either_an_assumption_key_or_a_declared_refusal(self):
        """The drift guard. A family added to either list must be reconciled
        here, or this fails loudly rather than silently costing coverage."""
        from metascience_agent.anatomy import (
            TEST_ASSUMPTIONS, TEST_FAMILIES_WITHOUT_ASSUMPTIONS, canonical_test_type)
        from metascience_agent.scaffold.schema import TEST_FAMILIES
        unreconciled = [f for f in TEST_FAMILIES
                        if canonical_test_type(f) not in TEST_ASSUMPTIONS
                        and f not in TEST_FAMILIES_WITHOUT_ASSUMPTIONS]
        assert not unreconciled, unreconciled

    def test_the_refusal_list_names_only_real_families(self):
        """A stale refusal would silently exempt a family that no longer exists
        while a real one went unchecked."""
        from metascience_agent.anatomy import TEST_FAMILIES_WITHOUT_ASSUMPTIONS
        from metascience_agent.scaffold.schema import TEST_FAMILIES
        assert not set(TEST_FAMILIES_WITHOUT_ASSUMPTIONS) - set(TEST_FAMILIES)

    def test_every_assumption_key_can_be_named_in_a_scaffold_account(self):
        """The other direction: a test the assumption checker understands must
        be expressible in the closed enum, or the account records `other` and
        the knowledge is unreachable."""
        from metascience_agent.anatomy import TEST_ASSUMPTIONS, canonical_test_type
        from metascience_agent.scaffold.schema import TEST_FAMILIES
        reachable = {canonical_test_type(f) for f in TEST_FAMILIES}
        assert not set(TEST_ASSUMPTIONS) - reachable

    @pytest.mark.parametrize("family", ["ancova", "mcnemar", "cox_regression", "log_rank"])
    def test_the_four_missing_families_are_now_nameable(self, family):
        from metascience_agent.scaffold.schema import TEST_FAMILIES
        assert family in TEST_FAMILIES

    @pytest.mark.parametrize("family,expected", [
        ("two_way_anova", {"normality", "homogeneity_of_variance", "independence"}),
        ("mixed_anova", {"normality", "homogeneity_of_variance", "sphericity",
                         "independence"}),
    ])
    def test_the_factorial_anovas_now_carry_their_assumptions(self, family, expected):
        assert set(self._test(family).required_assumptions()) == expected

    @pytest.mark.parametrize("spelling,canonical", [
        ("t_test_independent", "independent_t"),
        ("t_test_paired", "paired_t"),
        ("fisher_exact", "fishers_exact"),
    ])
    def test_a_spelling_variant_resolves_to_the_same_assumptions(self, spelling, canonical):
        """Purely a spelling join: the same test under the other vocabulary's
        name must get the same required set, never an empty one."""
        assert (self._test(spelling).required_assumptions()
                == self._test(canonical).required_assumptions())
        assert self._test(spelling).required_assumptions()

    def test_an_aliased_parametric_test_is_still_parametric(self):
        assert self._test("t_test_independent").is_parametric
        assert self._test("independent_t").is_parametric

    def test_an_aliased_rank_based_test_keeps_its_weak_assumption_note(self):
        """`fisher_exact` must not escalate where `fishers_exact` does not."""
        a = assumption_risk(self._test("fisher_exact"), None)
        assert a["severity"] == "consistent"
        assert "Rank-based" in a["note"]

    @pytest.mark.parametrize("family", ["correlation", "wilcoxon", "t_test_unspecified",
                                        "anova_unspecified", "survival", "other"])
    def test_an_ambiguous_family_still_fails_closed(self, family):
        """These name a GROUP of tests with different assumptions -- `correlation`
        may be Spearman, `survival` may be a Kaplan-Meier curve that assumes no
        proportional hazards. Guessing one member's assumptions would flag an
        honest paper for not reporting a check its test never required, so they
        stay unmapped and the gate returns `indeterminate`, which is not an
        allegation."""
        from metascience_agent.anatomy import TEST_FAMILIES_WITHOUT_ASSUMPTIONS
        assert family in TEST_FAMILIES_WITHOUT_ASSUMPTIONS
        r = assumption_risk(self._test(family), None)
        assert r["severity"] == "indeterminate"
        assert r["unreported_assumptions"] == []

    def test_the_new_coverage_does_not_accuse_a_paper_that_reported_its_checks(self):
        """The one-way rule: this may only ADD coverage. A paper that ran a
        two-way ANOVA and reported every check it requires must come back
        `consistent` with nothing unreported."""
        t = self._test("two_way_anova", assumption_checks_reported=[
            "Normality was assessed with Shapiro-Wilk.",
            "Levene's test confirmed homogeneity of variance.",
            "Independence of observations was verified.",
        ])
        r = assumption_risk(t, None)
        assert r["unreported_assumptions"] == []
        assert r["severity"] == "consistent"


class TestACleanOutlierCheckIsNotADenial:
    """The denial detector read "identified no extreme values" as a refusal to
    run the check, so a paper that DID screen for outliers and found none was
    told it had not screened -- `no_outliers` reported as unreported.

    This is the accusing direction, unlike the synonym additions of `ef1638d`,
    which could only suppress. It fired identically on `cook's distance` and on
    the bare word, so at least three tokens carried it.

    `_CHECK_RESULT` already exists for exactly this shape -- "no violations of
    normality were found" -- and its noun list simply did not include the
    outlier result nouns. What separates the two readings is grammatical: a
    RESULT negates the finding ("no outliers were detected"), a DENIAL negates
    the check itself ("no outlier analysis was conducted"), so the fix turns on
    whether a check word follows the noun.
    """

    def _flags(self, phrase):
        from metascience_agent.anatomy import classify_assumption_mentions
        return classify_assumption_mentions([phrase])

    @pytest.mark.parametrize("phrase", [
        "Grubbs' test identified no extreme values.",
        "No extreme values were identified by the GESD test.",
        "No outliers were detected.",
        "No outliers were identified.",
        "No significant outliers were present.",
        "Cook's distance identified no influential outliers.",
        "No influential cases were detected using leverage values.",
        "Examination of leverage values revealed no influential observations.",
    ])
    def test_a_check_that_found_nothing_counts_as_checked(self, phrase):
        r = self._flags(phrase)
        assert "no_outliers" in r["checked"], phrase
        assert "no_outliers" not in r["denied"], phrase

    @pytest.mark.parametrize("phrase", [
        "Outliers were not assessed.",
        "Outliers were not examined.",
        "No outlier analysis was conducted.",
        "No outlier screening was undertaken.",
        "No test for outliers was performed.",
        "No assessment of outliers was reported.",
        "No outlier diagnostics were reported.",
    ])
    def test_a_genuine_denial_is_still_a_denial(self, phrase):
        """The half that must not break. A check word after the noun -- or `no`
        attached to the check rather than to the finding -- keeps the denial."""
        r = self._flags(phrase)
        assert "no_outliers" in r["denied"], phrase
        assert "no_outliers" not in r["checked"], phrase

    def test_the_claim_reaches_the_reported_assumptions(self):
        """End to end through the consumer: a Pearson correlation requires
        `no_outliers`, and a clean screen must clear it."""
        t = StatisticalTest(id="t1", test_type="pearson_correlation",
                            location="Results", n=80,
                            assumption_checks_reported=[
                                "Grubbs' test identified no extreme values."])
        assert "no_outliers" not in t.unreported_assumptions()
        denied = StatisticalTest(id="t2", test_type="pearson_correlation",
                                 location="Results", n=80,
                                 assumption_checks_reported=["Outliers were not assessed."])
        assert "no_outliers" in denied.unreported_assumptions()

    def test_the_other_assumptions_are_untouched(self):
        """The control: clearing `no_outliers` must clear nothing else."""
        t = StatisticalTest(id="t1", test_type="pearson_correlation",
                            location="Results", n=80,
                            assumption_checks_reported=[
                                "Cook's distance identified no influential outliers."])
        assert set(t.unreported_assumptions()) == {"normality", "linearity"}

    def test_a_phrasing_that_located_no_assumption_at_all(self):
        """"No outlying values were present" matched no synonym key, so it gave
        neither the credit nor the accusation -- it was silently dropped.
        Recorded by the outlier fix and closed here. The synonym key and the
        result noun had to arrive together: the key alone would have converted
        a silent drop into a false accusation, because the phrasing is negated
        by construction."""
        r = self._flags("No outlying values were present.")
        assert "no_outliers" in r["checked"]
        assert "no_outliers" not in r["denied"]
        assert "no_outliers" in self._flags(
            "Outlying values were not examined.")["denied"]


class TestTheCleanResultRuleReachesTheOtherFourAssumptions:
    """The four assumptions the outlier fix measured and left: a clean result
    for multicollinearity, heteroscedasticity, clustering or heterogeneity read
    as a refusal to look. Same defect, same grammar, in the accusing direction.

    TWO DIFFERENCES THE VOCABULARY FORCES, and each has its own case below. A
    check word may sit behind a prepositional phrase ("no heterogeneity OF
    VARIANCE testing was undertaken"), a shape the outlier nouns do not
    produce; and these nouns take a TREATMENT verb, so "no clustering was
    accounted for" denies the check while "no clustering was detected" reports
    its result. One does not "account for" an outlier.

    ON `clustering`. The 2026-08-18 pass removed it from `ASSUMPTION_SYNONYMS`
    because the word means Schwann-cell clustering and hierarchical clustering
    36 times over in this literature. Nothing here re-adds it: it is a RESULT
    noun only, it still locates no assumption, and a segment must already name
    the independence diagnostics for anything to happen -- which is what
    `test_the_unrelated_senses_of_clustering_reach_nothing` holds.
    """

    def _flags(self, phrase):
        from metascience_agent.anatomy import classify_assumption_mentions
        return classify_assumption_mentions([phrase])

    @pytest.mark.parametrize("phrase,token", [
        ("VIF values indicated no multicollinearity.", "no_multicollinearity"),
        ("Collinearity diagnostics showed no multicollinearity.", "no_multicollinearity"),
        ("Variance inflation factors revealed no severe collinearity.",
         "no_multicollinearity"),
        ("Breusch-Pagan test revealed no heteroscedasticity.", "homoscedasticity"),
        ("The White test showed no heteroskedasticity.", "homoscedasticity"),
        ("The ICC indicated no clustering.", "independence"),
        ("Intraclass correlation coefficients indicated no meaningful clustering.",
         "independence"),
        ("Levene test showed no significant heterogeneity.",
         "homogeneity_of_variance"),
        ("Levene's test revealed no heterogeneity of variance.",
         "homogeneity_of_variance"),
    ])
    def test_a_check_that_found_nothing_counts_as_checked(self, phrase, token):
        r = self._flags(phrase)
        assert token in r["checked"], phrase
        assert token not in r["denied"], phrase

    @pytest.mark.parametrize("phrase,token", [
        ("Multicollinearity was not assessed.", "no_multicollinearity"),
        ("No multicollinearity diagnostics were reported.", "no_multicollinearity"),
        ("No test for multicollinearity was performed.", "no_multicollinearity"),
        ("No multicollinearity was assessed.", "no_multicollinearity"),
        ("Homoscedasticity was not examined.", "homoscedasticity"),
        ("The Breusch-Pagan test was not run.", "homoscedasticity"),
        ("Intraclass correlation was not reported.", "independence"),
        ("No clustering was accounted for in the ICC model.", "independence"),
        ("No clustering adjustment was applied despite the ICC.", "independence"),
        ("No clustering was modelled despite the design effect.", "independence"),
        ("Levene's test was not performed.", "homogeneity_of_variance"),
    ])
    def test_a_genuine_denial_is_still_a_denial(self, phrase, token):
        """The half that must not break -- the treatment-verb and check-word
        lookaheads exist for these."""
        r = self._flags(phrase)
        assert token in r["denied"], phrase
        assert token not in r["checked"], phrase

    def test_a_check_word_behind_a_prepositional_phrase(self):
        """"No heterogeneity OF VARIANCE testing was undertaken" is a denial
        whose check word is three tokens past the noun. Without the optional
        prepositional phrase in the lookahead it would strip as a result."""
        from metascience_agent.anatomy import _segment_denies
        assert _segment_denies("No heterogeneity of variance testing was undertaken.")
        assert not _segment_denies("Levene's test revealed no heterogeneity of variance.")

    def test_the_unrelated_senses_of_clustering_reach_nothing(self):
        """WHY THIS DOES NOT REOPEN 2026-08-18. `clustering` is not a synonym
        key and locates no assumption, so the biological and algorithmic senses
        cannot touch `independence` however they are negated. The rule can only
        act inside a segment that already names the independence diagnostics."""
        for phrase in ("No clustering of Schwann cells was observed.",
                       "Hierarchical clustering was performed on the expression data.",
                       "No clustering of the cells was apparent."):
            r = self._flags(phrase)
            assert "independence" not in r["checked"], phrase
            assert "independence" not in r["denied"], phrase

    @pytest.mark.parametrize("phrase,test_type,cleared", [
        ("VIF values indicated no multicollinearity.", "linear_regression",
         "no_multicollinearity"),
        ("Breusch-Pagan test revealed no heteroscedasticity.", "linear_regression",
         "homoscedasticity"),
        ("The ICC indicated no clustering.", "linear_regression", "independence"),
        ("Levene test showed no significant heterogeneity.", "independent_t",
         "homogeneity_of_variance"),
        ("No outlying values were present.", "pearson_correlation", "no_outliers"),
    ])
    def test_the_claim_reaches_the_reported_assumptions(self, phrase, test_type,
                                                        cleared):
        """End to end through the consumer, and the control in one: the clean
        result clears its own assumption and the test's other required
        assumptions still report as unreported."""
        t = StatisticalTest(id="t1", test_type=test_type, location="Results", n=80,
                            assumption_checks_reported=[phrase])
        unreported = set(t.unreported_assumptions())
        assert cleared not in unreported, phrase
        assert unreported == set(t.required_assumptions()) - {cleared}, phrase
