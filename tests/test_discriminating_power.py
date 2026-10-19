"""A check that cannot fail must not report `consistent`.

GREG'S RULE, 2026-08-11:

    "we do the test on only those numbers available, flag it, and then test
     truncation etc. That way the reader can see the apparent violation (i.e.
     our toolkit working) but then judge for themselves whether the truncation
     etc is credible. But I agree to not do the decimal expansion if it ALWAYS
     rescues an otherwise impossible finding."

Two things follow, and this file is about both.

FIRST, THE OFF SWITCH. A rescue that is available for every value is not a
judgement about the paper. Granting it silently converts a real detection into
a guaranteed all-clear, so where round-half can reject and NOTHING survives both
conventions, the honest answer is that we cannot adjudicate.

SECOND, AND LARGER THAN THE RULE THAT PROMPTED IT. The same argument condemns
the underlying check wherever it has no resolution at all. MEASURED over 159
archived GRIM calls: 90 of them (56.6%) were in a regime where NO printable
value could have failed, and every one returned `consistent`. A further 15
(9.4%) sat in the off-switch band. Two thirds of this toolkit's GRIM output was
uninformative and was presented as a pass -- a false all-clear, which the
cardinal rule ranks second only to a false accusation.
"""
import pytest

from forensic_metascience_ai_toolkit.tools.grim import (
    _mean_passes_grim, _mean_passes_grim_truncation, discriminating_power,
    grim_test,
)


class TestThePowerCalculationItself:
    """Exact, not sampled. Attainable means are {S/n}, and S -> S+n shifts the
    mean by exactly 1, so one period of the printable grid settles the scale."""

    def test_two_decimals_is_dead_at_n_100_and_above(self):
        """1/100 = 0.01 is exactly the grid step, so every printable value is
        attainable and GRIM has nothing to say."""
        for n in (100, 120, 250, 1000):
            assert discriminating_power(n, 2)["check_can_fail"] is False

    def test_one_decimal_is_dead_for_every_realistic_sample_size(self):
        """This is where 72 of the 90 dead archived calls were. At 1 dp GRIM
        retains power only for single-digit n."""
        for n in range(10, 40):
            assert discriminating_power(n, 1)["check_can_fail"] is False
        assert discriminating_power(6, 1)["check_can_fail"] is True

    def test_zero_decimals_is_dead_at_every_n(self):
        for n in (2, 3, 5, 12, 40, 300):
            assert discriminating_power(n, 0)["check_can_fail"] is False

    def test_nothing_survives_both_conventions_above_n_66_at_two_decimals(self):
        """The band is not a tidy interval and must not be asserted as one:
        n = 80 and n = 96 are DEAD rather than off-switch, because there the
        round-half tolerance exactly reaches every printable value. What holds
        without exception is the weaker, load-bearing claim -- above n = 66 the
        union of the two conventions rejects nothing at all, so a `consistent`
        verdict there is empty however it was arrived at."""
        for n in range(67, 130):
            p = discriminating_power(n, 2)
            assert p["both_reject"] == 0.0, n
            assert (p["rescue_is_an_off_switch"] or not p["check_can_fail"]), n
        for n in (30, 50, 60, 66):
            p = discriminating_power(n, 2)
            assert p["rescue_is_an_off_switch"] is False, n
            assert p["both_reject"] > 0.0, n

    def test_the_two_ways_of_being_uninformative_are_distinguished(self):
        """`dead` and `off switch` are different facts and get different
        explanations, so the flags must not collapse into each other."""
        dead = discriminating_power(100, 2)
        off = discriminating_power(78, 2)
        assert dead["check_can_fail"] is False
        assert dead["rescue_is_an_off_switch"] is False
        assert off["check_can_fail"] is True
        assert off["rescue_is_an_off_switch"] is True

    def test_three_decimals_keeps_power_where_two_loses_it(self):
        """Precision, not sample size, is what GRIM actually runs on. The same
        n that is hopeless at 2 dp is a strong check at 3."""
        assert discriminating_power(100, 2)["check_can_fail"] is False
        assert discriminating_power(100, 3)["both_reject"] > 0.5

    def test_it_agrees_with_the_two_convention_functions_it_summarises(self):
        """The summary must not drift from the predicates it summarises."""
        n, dp = 30, 2
        p = discriminating_power(n, dp)
        both = sum(1 for i in range(100)
                   if not _mean_passes_grim(round(i / 100, 2), n, dp)[0]
                   and not _mean_passes_grim_truncation(round(i / 100, 2), n, dp)[0])
        assert p["both_reject"] == pytest.approx(both / 100)

    def test_garbage_in_does_not_disable_the_check(self):
        """A malformed (n, decimals) must fail SAFE -- claiming no power would
        suppress every finding on that call."""
        for bad in ((0, 2), (-5, 2), (30, None), (30, -1), (30, 99)):
            assert discriminating_power(*bad)["check_can_fail"] is True


class TestADeadCheckRefusesInsteadOfPassing:
    def test_one_decimal_place_returns_indeterminate_not_consistent(self):
        r = grim_test(3.4, 30, decimals=1, data_type="likert",
                      discreteness_source="stated")
        assert r["severity"] == "indeterminate"
        assert r["failure_mode"] == "no_discriminating_power"
        assert r["applicable"] is False

    def test_it_says_plainly_that_the_verdict_would_be_empty(self):
        r = grim_test(3.42, 120, decimals=2, data_type="likert")
        assert "no reported figure could have failed" in r["explanation"]
        assert "not evidence that the numbers are in order" in r["explanation"]

    def test_it_is_not_a_statement_about_the_paper(self):
        r = grim_test(3.4, 30, decimals=1, data_type="likert")
        assert r["severity"] not in ("impossible", "highly_suspicious", "suspicious")
        assert r["applicable"] is False

    def test_OUT_OF_RANGE_SURVIVES_the_dead_check_exit(self):
        """A DIFFERENT CLAIM, and it does not depend on granularity power at
        all: 128.43 is outside a 1-7 scale whatever n and precision are. An
        unconditional exit deleted this finding, which is how the bug was
        caught -- one archived test pins it at `impossible` on stated bounds."""
        r = grim_test(128.43, 100, data_type="likert")
        assert r["failure_mode"] == "out_of_range"
        assert r["severity"] == "suspicious"
        r2 = grim_test(128.43, 100, data_type="likert", bound_source="stated")
        assert r2["severity"] == "impossible"

    def test_THE_PERCENTAGE_CAVEAT_SURVIVES_TOO(self):
        """Also a different check with its own power: it asks whether mean/100
        is attainable at `decimals + 2`, a finer grid than the dead one. The
        archived false clear this caveat exists for (18.3 at n = 12, 1 dp) sits
        squarely in the no-power regime, so a bare early return would have
        deleted the fix that found it."""
        r = grim_test(18.3, 12, decimals=1, data_type="count", scale_min=0,
                      scale_max=200, discreteness_source="stated")
        assert r["failure_mode"] == "no_discriminating_power"
        assert r["percentage_reading"]["reading"] == "percentage"

    def test_a_real_check_is_untouched(self):
        """The canonical impossibility must survive all of this."""
        r = grim_test(5.51, 30, decimals=2, data_type="likert",
                      discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "granularity"


class TestTheRescueThatRescuesEverything:
    def test_inside_the_band_it_refuses_rather_than_clearing(self):
        """3.02 at n = 78 fails round-half. Truncation 'saves' it -- and saves
        every other failing value at that n too, so it explains nothing."""
        r = grim_test(3.02, 78, decimals=2, data_type="likert",
                      discreteness_source="stated")
        assert r["severity"] == "indeterminate"
        assert r["failure_mode"] == "no_discriminating_power"

    def test_it_shows_the_reader_what_failed_before_declining_to_call_it(self):
        r = grim_test(3.02, 78, decimals=2, data_type="likert",
                      discreteness_source="stated")
        ar = r["as_reported"]
        assert "not attainable" in ar["statement"]
        assert "available for every number" in ar["why_we_will_not_call_it"]

    def test_OUTSIDE_the_band_the_truncation_rescue_still_applies(self):
        """The gate must not have disabled the rescue generally. 3.46 at n = 30
        is the repo's own reproduction: 16 threes and 14 fours sum to 104, and
        104/30 = 3.4666 is printed 3.46 by a truncating reporter. At n = 30 only
        14% of round-half failures are rescuable, so this is a specific
        explanation rather than a generic one."""
        r = grim_test(3.46, 30, decimals=2, data_type="likert",
                      discreteness_source="stated")
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "rounding_convention"


class TestTheApparentViolationIsVISIBLE:
    """Greg: "the reader can see the apparent violation (i.e. our toolkit
    working) but then judge for themselves whether the truncation etc is
    credible."

    The de-escalation stays -- a truncating reporter is a house style, not
    fabrication, and it must not enter the findings as an accusation. What was
    wrong is that it left NOTHING to judge: the reader saw a clean verdict and
    never learned the arithmetic had failed as printed.
    """

    def _rescued(self):
        return grim_test(3.46, 30, decimals=2, data_type="likert",
                         discreteness_source="stated")

    def test_it_states_what_failed_as_printed(self):
        ar = self._rescued()["as_reported"]
        assert "3.46 is not attainable" in ar["statement"]
        assert "104" in ar["statement"]

    def test_it_states_what_would_have_happened_without_the_convention(self):
        """Naming the severity that was withheld is the difference between a
        de-escalation the reader can audit and one they cannot see."""
        assert self._rescued()["as_reported"]["severity_if_taken_at_face_value"] == "impossible"

    def test_it_explains_the_rescue_in_the_papers_terms(self):
        ar = self._rescued()["as_reported"]
        assert "truncated rather than rounded" in ar["explanation"]
        assert "SPSS" in ar["explanation"]

    def test_it_reports_HOW_OFTEN_that_excuse_is_available(self):
        """The credibility number. An explanation available for 14% of failures
        at this n is specific; one available for 90% is not, and the reader
        cannot weigh the claim without knowing which."""
        share = self._rescued()["as_reported"]["how_often_that_excuse_is_available"]
        assert 0.0 < share < 0.25

    def test_it_tells_the_reader_what_would_settle_it(self):
        jf = self._rescued()["as_reported"]["judge_for_yourself"]
        assert "house style" in jf
        assert "rate" in jf.lower()

    def test_the_severity_is_still_not_an_accusation(self):
        """GREG, 2026-08-10, unchanged: "I wouldn't want to classify it as
        suspicious in the findings." Visible is not the same as accused."""
        assert self._rescued()["severity"] == "consistent"

    def test_every_result_carries_the_power_it_was_judged_at(self):
        """So a reader can tell a check that passed from one that could not
        have failed, without re-deriving it."""
        for r in (self._rescued(),
                  grim_test(5.51, 30, decimals=2, data_type="likert"),
                  grim_test(3.4, 30, decimals=1, data_type="likert")):
            assert r["discriminating_power"]["check_can_fail"] in (True, False)


class TestTheArchiveReplayed:
    """The measurement that motivated all of the above, in the suite."""

    def test_most_archived_grim_calls_could_not_have_failed(self):
        import collections
        import glob
        import json
        tally = collections.Counter()
        for f in glob.glob("**/toolcalls.stage*.json", recursive=True):
            try:
                d = json.load(open(f))
            except Exception:  # noqa: BLE001, PERF203
                continue
            for c in (d if isinstance(d, list) else d.get("calls", [])):
                if "grim" not in str(c.get("tool") or c.get("name") or ""):
                    continue
                inp = c.get("input") or {}
                try:
                    n, dec = int(inp["n"]), int(inp["decimals"])
                except Exception:  # noqa: BLE001, PERF203
                    continue
                p = discriminating_power(n, dec)
                tally["dead" if not p["check_can_fail"]
                      else "off_switch" if p["rescue_is_an_off_switch"]
                      else "real"] += 1
        if not sum(tally.values()):
            pytest.skip("no archived runs in this checkout")
        total = sum(tally.values())
        assert tally["dead"] / total > 0.4, dict(tally)
        assert tally["real"] / total < 0.5, dict(tally)


class TestTheApparentViolationREACHESTheReader:
    """Built, tested, never consumed is this repo's recurring failure, and it
    already has three instances in exactly this neighbourhood: none of
    `discreteness_caveat`, `denominator_question` or `percentage_reading`
    renders anywhere in the viewer. `as_reported` would have been the fourth.
    """

    def _call(self, result: dict) -> dict:
        import json

        from forensic_metascience_ai_toolkit.bundle import _distil_calls
        return _distil_calls(
            [{"seq": 1, "tool_short": "grim_check", "input": {},
              "result": json.dumps(result)}], "stage2")[0]

    def test_the_bundle_lifts_it_out_of_the_raw_result_blob(self):
        """Left inside the result string it is technically present and
        effectively invisible -- which is the state Greg objected to."""
        r = grim_test(3.46, 30, decimals=2, data_type="likert",
                      discreteness_source="stated")
        entry = self._call(r)
        assert entry["as_reported"]["explained_by"] == "truncation"
        assert entry["discriminating_power"]["check_can_fail"] is True

    def test_a_dead_check_carries_its_power_to_the_page(self):
        r = grim_test(3.4, 30, decimals=1, data_type="likert")
        entry = self._call(r)
        assert entry["discriminating_power"]["check_can_fail"] is False

    def test_an_ordinary_call_gains_no_extra_keys(self):
        """The fields must be absent, not present-and-empty: the renderer keys
        on truthiness and an empty dict would print a heading with nothing
        under it."""
        entry = self._call(grim_test(5.51, 30, decimals=2, data_type="likert",
                                     discreteness_source="stated"))
        assert "as_reported" not in entry

    def test_a_result_that_is_not_json_does_not_crash_the_distiller(self):
        from forensic_metascience_ai_toolkit.bundle import _distil_calls
        out = _distil_calls([{"seq": 1, "tool_short": "read_file",
                              "input": {}, "result": "plain text"}], "stage1")
        assert out and "as_reported" not in out[0]

    def test_the_renderer_and_its_styling_are_both_in_the_page(self):
        """The JS half. `powerHtml` deliberately renders NOTHING for an
        ordinary powered check, so its presence in the source is what has to be
        asserted here; the behavioural check is the node run in the commit."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src/forensic_metascience_ai_toolkit/bundle.py").read_text(encoding="utf-8")
        assert "function asReportedHtml" in src
        assert "function powerHtml" in src
        assert "asReportedHtml(c.as_reported)" in src
        assert "powerHtml(c.discriminating_power)" in src
        assert ".asrep{" in src

    def test_it_is_not_styled_as_an_accusation(self):
        """A dashed rule and the page's own colours, never the severity
        palette. Giving explained arithmetic accusation colour would
        reintroduce as DESIGN the escalation the severity ladder avoids."""
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src/forensic_metascience_ai_toolkit/bundle.py").read_text(encoding="utf-8")
        i = src.index(".asrep{")
        block = src[i:i + 200]
        for accusatory in ("--bad", "--impossible", "--danger", "red"):
            assert accusatory not in block


class TestThePopulationSDConventionIsShownToo:
    """The same defect, the same fix. MEASURED before keeping the rescue at
    all, against Greg's off-switch rule: over 500 arbitrary (GRIM-consistent
    mean, random SD) pairs the population reading rescued 88 while 299 were
    still caught at `impossible`. A 22.7% rescue rate retains three quarters of
    the check's power -- an explanation, not an off switch, and nothing like
    truncation's 100% at n = 67..99.
    """

    def _rescued(self):
        from forensic_metascience_ai_toolkit.tools.sd_checks import grimmer_test
        # The repo's own verified false accusation: [1,2,2,3,3,3,4,4,4,4] has
        # mean 3.0 and population SD exactly 1.0, and was branded `impossible`.
        return grimmer_test(3.0, 1.0, 10, scale_min=1, scale_max=7, decimals=2,
                            decimals_sd=2, data_type="likert",
                            discreteness_source="stated")

    def test_the_de_escalation_is_unchanged(self):
        r = self._rescued()
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "sd_convention"

    def test_but_the_failed_arithmetic_is_now_visible(self):
        ar = self._rescued()["as_reported"]
        assert "Bessel" in ar["statement"]
        assert ar["severity_if_taken_at_face_value"] == "impossible"

    def test_it_names_the_convention_in_tools_a_reader_can_check(self):
        ex = self._rescued()["as_reported"]["explanation"]
        assert "STDEVP" in ex and "numpy" in ex

    def test_it_reports_how_often_the_excuse_is_available(self):
        share = self._rescued()["as_reported"]["how_often_that_excuse_is_available"]
        assert 0.15 < share < 0.35

    def test_a_real_sd_impossibility_is_untouched(self):
        """The check must still fire. This is the property every one of these
        changes is at risk of quietly destroying."""
        from forensic_metascience_ai_toolkit.tools.sd_checks import grimmer_test
        r = grimmer_test(3.0, 1.02, 10, scale_min=1, scale_max=7, decimals=2,
                         decimals_sd=2, data_type="likert",
                         discreteness_source="stated")
        assert r["severity"] == "impossible"
        assert r["failure_mode"] == "sd_granularity"
        # No convention explains it, so there is nothing to show and nothing to
        # excuse: the finding stands on its own.
        assert "as_reported" not in r


class TestThePercentagePathGetsTheSameTreatment:
    """A percentage printed to `decimals` dp is a proportion at `decimals + 2`,
    and the proportion predicate is bit-for-bit the mean predicate (verified),
    so the same power function settles it.

    MEASURED: for WHOLE percentages the check is dead at n >= 100 and the
    truncation rescue is an off switch at n = 78; at 1 dp it survives to n = 200
    and is dead by n = 1000. Two extra digits of resolution buys about two
    orders of magnitude in n -- and then runs out exactly like the mean check.
    """

    def _pct(self, **kw):
        from forensic_metascience_ai_toolkit.tools.grim import grim_test_percentage
        return grim_test_percentage(**kw)

    def test_a_whole_percentage_against_a_large_n_cannot_fail(self):
        """The archived case: '1108/1851 rounds to 60%'. Attainable percentages
        there are 0.054 points apart against a 1-point grid."""
        r = self._pct(percentage=60.0, n=1851, decimals=0)
        assert r["severity"] == "indeterminate"
        assert r["failure_mode"] == "no_discriminating_power"
        assert r["applicable"] is False

    def test_the_off_switch_band_refuses_here_too(self):
        r = self._pct(percentage=61.0, n=78, decimals=0)
        assert r["severity"] == "indeterminate"
        assert "explains this value no better" in r["as_reported"]["why_we_will_not_call_it"]

    def test_the_real_truncating_paper_is_still_rescued_and_now_shown(self):
        """10.3389/fnins.2023.1186751: '9 patients (9.6%)' against a stated 93.
        9/93 = 9.6774, which rounds to 9.7 and truncates to 9.6. We called that
        `impossible` -- top of the ladder -- against a paper consistent with its
        own stated N."""
        r = self._pct(percentage=9.6, n=93, decimals=1)
        assert r["severity"] == "consistent"
        assert r["failure_mode"] == "rounding_convention"
        assert "9.6% is not attainable" in r["as_reported"]["statement"]
        assert r["as_reported"]["severity_if_taken_at_face_value"] == "impossible"

    def test_a_genuine_percentage_impossibility_still_fires(self):
        """The property every one of these changes risks destroying."""
        r = self._pct(percentage=9.7, n=12, decimals=1)
        assert r["severity"] == "impossible"

    def test_it_still_reports_out_of_range_when_the_count_is_impossible(self):
        """As with means, range is a separate claim from granularity and must
        survive the dead-check exit."""
        r = self._pct(percentage=140.0, n=1851, decimals=0)
        assert r["severity"] != "consistent"


class TestDEBITShowsItsWorkingToo:
    """The last member of the family, and the one that needed it least.

    MEASURED against Greg's off-switch rule before keeping either rescue: over
    400 arbitrary (mean, sd, n) triples DEBIT still reached `impossible` on 388.
    Only 12 cleared, and only 2 of those via the population convention. It
    retains 97% of its power. That is structural rather than lucky: for 0/1 data
    the SD is FULLY DETERMINED by the count of 1s and n, so the admissible set
    is tiny and no reporting convention widens it much.
    """

    def _rescued(self):
        from forensic_metascience_ai_toolkit.tools.debit import debit_test
        # Found by the sweep: clears only under truncation.
        return debit_test(mean=0.7, sd=0.45, n=400, decimals_mean=2,
                          decimals_sd=2, data_type="binary")

    def test_the_de_escalation_is_unchanged(self):
        assert self._rescued()["severity"] == "consistent"

    def test_the_failed_arithmetic_is_now_visible(self):
        ar = self._rescued()["as_reported"]
        assert "not attainable" in ar["statement"]
        assert ar["severity_if_taken_at_face_value"] == "impossible"

    def test_it_says_which_convention_carried_it(self):
        assert self._rescued()["as_reported"]["explained_by"] in (
            "truncation", "population_sd")

    def test_it_explains_why_the_constraint_is_tight(self):
        """A reader who does not know DEBIT cannot tell a tight constraint from
        a loose plausibility band, and the two deserve different reactions."""
        assert "fully" in self._rescued()["as_reported"]["statement"].lower()

    def test_a_triple_no_convention_explains_gets_no_excuse_block(self):
        from forensic_metascience_ai_toolkit.tools.debit import debit_test
        r = debit_test(mean=0.5, sd=0.51, n=100, decimals_mean=2,
                       decimals_sd=2, data_type="binary")
        assert r["severity"] == "impossible"
        assert "as_reported" not in r

    def test_the_check_still_has_its_power(self):
        """The property every one of these changes risks destroying, measured
        rather than asserted."""
        import random

        from forensic_metascience_ai_toolkit.tools.debit import debit_test
        rng = random.Random(2)
        accused = 0
        for _ in range(120):
            n = rng.choice([28, 50, 120, 400])
            r = debit_test(mean=round(rng.uniform(0.05, 0.95), 2),
                           sd=round(rng.uniform(0.05, 0.6), 2), n=n,
                           decimals_mean=2, decimals_sd=2, data_type="binary")
            if r["severity"] in ("impossible", "highly_suspicious", "suspicious"):
                accused += 1
        assert accused / 120 > 0.85
