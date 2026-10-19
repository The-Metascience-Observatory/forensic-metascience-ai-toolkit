"""How often does the model supply a guard, versus letting it default?

A guard is a precondition without which a check does not degrade -- it INVERTS.
Specificity is 0.846 with correct scale bounds and 0.0000 with misspecified
ones, and at most 0.31% of numeric cells in a real corpus are GRIM-eligible at
all. A defaulted `data_type` is therefore the single most likely cause of a
false accusation, not a minor omission.

This audit is also the cheap experiment that settles a live design
disagreement. One position is that the CLI is sufficient and the agent should
just run; the other is that a human-authored run-spec should declare the guards.
If guards turn out to be near-always supplied, the spec is unnecessary. If they
are often defaulted, that number is the argument for it. Free, always on, and it
needs no spec file to produce.
"""
import pytest

from metascience_agent.agent import _guard_audit


def _call(seq, tool, **args):
    return {"seq": seq, "tool_short": tool, "input": args}


#: `grim_check`'s alarmable guards, i.e. every guard it has except `provenance`,
#: whose default is excused (`_SOUND_GUARD_DEFAULTS`). `decimals` joined the set
#: on 2026-08-07, when it went from `default=2, guard=False` to `default=None,
#: guard=True` -- on rows consistent at 1 dp the 2-dp default returned a false
#: `impossible` 41.1% of the time, which is exactly what a guard is for.
#: `discreteness_source` joined on 2026-08-10 for the same reason `decimals`
#: joined: it went from "not a parameter at all" to a guard, because GRIM's
#: GRANULARITY branch was reaching `impossible` on the premise that the
#: observations are integers -- a premise `data_type` merely asserts. Counts
#: below are derived from this dict rather than written out, so the next guard
#: cannot silently desync them.
GRIM_GUARDS_SUPPLIED = {"data_type": "likert", "bound_source": "stated", "decimals": 1,
                        "discreteness_source": "stated"}
N_GRIM_GUARDS = len(GRIM_GUARDS_SUPPLIED)


class TestCounting:
    def test_supplied_guards_are_counted(self):
        a = _guard_audit([_call(1, "grim_check", mean=5.51, n=30,
                                **GRIM_GUARDS_SUPPLIED)])
        assert a["n_supplied"] == N_GRIM_GUARDS and a["n_defaulted"] == 0
        assert a["supplied_rate"] == 1.0

    def test_defaulted_guards_are_counted(self):
        a = _guard_audit([_call(1, "grim_check", mean=5.51, n=30)])
        assert a["n_supplied"] == 0 and a["n_defaulted"] == N_GRIM_GUARDS
        assert {d["guard"] for d in a["defaulted_calls"]} == set(GRIM_GUARDS_SUPPLIED)

    def test_empty_string_counts_as_defaulted(self):
        """A guard present but blank was not actually declared."""
        a = _guard_audit([_call(1, "csf_test", p_values=[0.9, 0.9, 0.9], design="")])
        assert a["n_defaulted"] == 1

    def test_none_counts_as_defaulted(self):
        a = _guard_audit([_call(1, "csf_test", p_values=[0.9, 0.9, 0.9], design=None)])
        assert a["n_defaulted"] == 1

    def test_unguarded_tools_are_ignored(self):
        """Only guarded tools have guard slots; the rest are not counted."""
        # (recalc_f_to_p was the example until 1.86.0 made `p_relation` a guard.)
        a = _guard_audit([_call(1, "check_count_percent", count=142,
                                percentage=71.0, n=200)])
        assert a["n_guard_slots"] == 0

    def test_unknown_tool_does_not_crash(self):
        assert _guard_audit([_call(1, "no_such_tool", x=1)])["n_guard_slots"] == 0

    def test_empty_ledger(self):
        a = _guard_audit([])
        assert a["n_guard_slots"] == 0 and a["supplied_rate"] is None
        assert "no guarded tools" in a["verdict"]


class TestTheConsequenceTravelsWithTheCount:
    """A bare count is not actionable; the cost of each default is stated."""

    def test_every_default_names_its_consequence(self):
        a = _guard_audit([_call(1, "grim_check", mean=5.51, n=30)])
        assert a["defaulted_calls"]
        for d in a["defaulted_calls"]:
            assert len(d["consequence"]) > 40

    def test_data_type_default_names_the_verified_false_positive(self):
        a = _guard_audit([_call(1, "grim_check", mean=5.51, n=30)])
        consequence = next(d["consequence"] for d in a["defaulted_calls"]
                           if d["guard"] == "data_type")
        assert "128.43" in consequence, "cite the verified case, not a generality"

    def test_design_default_names_the_cluster_trial_rate(self):
        a = _guard_audit([_call(1, "csf_test", p_values=[0.9, 0.9, 0.9])])
        assert "71%" in a["defaulted_calls"][0]["consequence"]


class TestVerdict:
    def test_a_low_rate_says_why_it_matters(self):
        """Pins the CLAIM, not the numbers that used to carry it.

        This asserted that the verdict string contained "0.846" and "0.0000".
        Those specificity figures were removed on 2026-08-12: an audit found
        nothing in the tree computes them -- they were prose in the README,
        quoted back by comments in five source files, by the CLI, and by this
        verdict string, which put an unsourced number into the model's own
        instructions.

        The claim underneath is sound and independently demonstrated (the
        population-SD and truncated-mean false accusations both came from a
        defaulted guard), so what the verdict must say is that a defaulted
        guard INVERTS a check rather than weakening it. The magnitude is
        unmeasured and must not be asserted until it is measured.
        """
        a = _guard_audit([_call(1, "grim_check", mean=5.51, n=30)])
        assert "false accusation" in a["verdict"]
        assert "inverts" in a["verdict"].lower()
        assert "0.846" not in a["verdict"], "the unsourced figure is back"

    def test_a_high_rate_says_the_spec_would_add_little(self):
        calls = [_call(i, "grim_check", mean=5.51, n=30, **GRIM_GUARDS_SUPPLIED)
                 for i in range(10)]
        assert "add little" in _guard_audit(calls)["verdict"]

    def test_per_tool_breakdown_localises_the_problem(self):
        a = _guard_audit([
            _call(1, "grim_check", mean=5.51, n=30),
            _call(2, "csf_test", p_values=[0.9, 0.9, 0.9], design="parallel_rct"),
        ])
        assert a["per_tool"]["grim_check"]["defaulted"] == N_GRIM_GUARDS
        assert a["per_tool"]["csf_test"]["supplied"] == 1


ALARM = "most likely cause of a false accusation"


def _check_table(seq=1, **extra):
    """A `check_table` call with both no-default guards supplied.

    `provenance` is omitted, which is what the model actually did on all three
    wave-3 papers.
    """
    args = {"cells": [{"raw": "5.51 (1.20)", "row_label": "Anxiety"}],
            "variables": [{"id": "v1", "family": "continuous"}],
            "bindings": {"Anxiety": "v1"}}
    args.update(extra)
    return _call(seq, "check_table", **args)


def _read(seq, path):
    return _call(seq, "Read", file_path=path)


class TestASoundDefaultIsNotABreach:
    """The alarm fired on every single wave-3 run, always for the same slot.

    23 of 26 guard slots were supplied across the three papers -- 88%, under the
    0.9 threshold -- so all three reports printed "A defaulted guard is the most
    likely cause of a false accusation". All three misses were `check_table`'s
    `provenance`, once per paper; the other seven guarded slots were supplied
    100% of the time. An audit that fires on every clean run trains its reader
    to skip it, which is the same failure the `StructuredOutput` false breach
    had before it was fixed the same way.
    """

    def test_a_defaulted_provenance_on_a_printed_table_is_not_counted(self):
        a = _guard_audit([_check_table()])
        assert a["n_defaulted"] == 0
        assert a["defaulted_calls"] == []
        assert a["supplied_rate"] == 1.0

    def test_the_alarm_does_not_fire(self):
        assert ALARM not in _guard_audit([_check_table()])["verdict"]

    def test_the_excusal_is_recorded_rather_than_hidden(self):
        """Recorded, not counted. An excusal nobody can see is not auditable."""
        a = _guard_audit([_check_table()])
        assert a["n_excused"] == 1
        e = a["excused_calls"][0]
        assert (e["tool"], e["guard"]) == ("check_table", "provenance")
        assert e["default"] == "printed_table", "state the value being excused"
        assert len(e["why_sound"]) > 40, "the reason travels with the count"
        assert a["per_tool"]["check_table"]["excused"] == 1

    def test_the_verdict_says_a_slot_was_excused(self):
        assert "correct for the input" in _guard_audit([_check_table()])["verdict"]

    def test_slots_still_reconcile_with_the_rate(self):
        """The viewer prints these as one sentence -- "N of M supplied (P%)" --
        so `n_guard_slots` must stay the denominator of `supplied_rate`."""
        a = _guard_audit([_check_table()])
        assert a["n_guard_slots"] == a["n_supplied"] + a["n_defaulted"] == 2
        assert a["supplied_rate"] == a["n_supplied"] / a["n_guard_slots"]

    def test_a_supplied_provenance_is_still_counted_as_supplied(self):
        a = _guard_audit([_check_table(provenance="measured_raster")])
        assert a["n_supplied"] == 3 and a["n_excused"] == 0


class TestTheAlarmCanStillFire:
    """Excusing one correct default must not disarm the audit."""

    def test_a_defaulted_data_type_still_alarms(self):
        """`unknown` is an admission, not an answer, so it stays alarmable.

        Both ignorance sentinels must survive the excusal machinery that landed
        for `provenance`: `data_type='unknown'` is refused by every
        applicability guard, so the cost is a check that silently did not
        happen, and `bound_source='assumed'` caps an out-of-range finding at
        `suspicious` where 'stated' licenses `impossible` (29/495 sample sizes
        vs 495/495 on those same numbers). `grim_check` also gained a
        `provenance` slot, which IS excused -- one excusal must not carry the
        other two. `discreteness_source` is the third sentinel of the same kind,
        added 2026-08-10: `assumed` caps a GRANULARITY failure at `suspicious`
        where `stated` licenses `impossible`.
        """
        a = _guard_audit([_call(1, "grim_check", mean=5.51, n=30)])
        assert ({"data_type", "bound_source", "discreteness_source"}
                <= {d["guard"] for d in a["defaulted_calls"]})
        assert a["n_defaulted"] == N_GRIM_GUARDS and a["n_excused"] == 1
        assert ALARM in a["verdict"]

    def test_check_table_still_alarms_on_its_other_guards(self):
        """`variables` and `bindings` have no default at all -- defaulting them
        means the dispatch never learned the cell's variable family."""
        a = _guard_audit([_call(1, "check_table", cells=[])])
        assert a["n_defaulted"] == 2 and a["n_excused"] == 1
        assert {d["guard"] for d in a["defaulted_calls"]} == {"variables", "bindings"}

    def test_effect_plausibility_provenance_is_deliberately_not_excused(self):
        """Same guard name, different tool, and the difference is the point:
        `check_effect_plausibility` is the check BUILT to accept figure-derived
        inputs, so a digitised value arriving there is the designed route rather
        than an edge case, and letting `printed_text` stand relabels it."""
        a = _guard_audit([_call(1, "check_effect_plausibility", d=0.8, field="medicine_rct")])
        assert a["n_excused"] == 0
        assert [d["guard"] for d in a["defaulted_calls"]] == ["provenance"]

    def test_one_sound_default_does_not_rescue_a_bad_run(self):
        """Two excusals here (`check_table` and `grim_check` provenance) and the
        alarm still fires on every real miss: 2 supplied against `grim_check`'s
        four defaulted guards."""
        a = _guard_audit([_check_table(1), _call(2, "grim_check", mean=5.51, n=30)])
        assert a["n_supplied"] == 2 and a["n_defaulted"] == N_GRIM_GUARDS
        assert a["n_excused"] == 2
        assert ALARM in a["verdict"]


class TestTheExcusalIsWithdrawnWhenAFigureWasRead:
    """`printed_table` is only the right reading while no measured value can
    have reached the table. That is checkable from the same ledger rather than
    assumed: `check_table` is stage-1-only and so is every figure read, so if a
    crop was opened it is in the ledger the audit already receives.
    """

    def test_opening_a_figure_puts_the_slot_back_on_the_alarm(self):
        a = _guard_audit([_read(1, "figures/Figure_2_p004.png"), _check_table(2)])
        assert a["n_excused"] == 0
        assert [d["guard"] for d in a["defaulted_calls"]] == ["provenance"]
        assert ALARM in a["verdict"]

    def test_reading_only_text_leaves_the_slot_excused(self):
        """Reading the paper is not reading a figure -- 27 `Read` calls across
        the three wave-3 runs, not one of them an image."""
        a = _guard_audit([_read(1, "body.md"), _check_table(2)])
        assert a["n_excused"] == 1 and a["n_defaulted"] == 0

    def test_extracting_figures_without_opening_them_is_not_reading_them(self):
        """`extract_figures` ran once on every wave-3 paper and not one crop was
        ever opened. Extraction is not inspection."""
        a = _guard_audit([_call(1, "extract_figures", pdf_path="p.pdf"), _check_table(2)])
        assert a["n_excused"] == 1 and a["n_defaulted"] == 0


class TestAgainstTheRealWave3Runs:
    """Regression anchor on the artefacts that prompted this."""

    #: RE-MEASURED 2026-08-07, after `provenance` was extended from `check_table`
    #: alone to every exact-arithmetic check. The alarmable side is UNCHANGED --
    #: still 0 defaulted and a 1.0 supplied rate on all three papers, i.e. 14/14
    #: alarmable slots (4 + 6 + 4) -- but the excusal count moved from 1 per
    #: paper to one per guarded call, because 15 more tools now carry the slot.
    #: hbm.26595's 41 is dominated by 34 `rivets_anova` calls; every one of the
    #: 47 excusals across the three papers is a `provenance` slot.
    EXCUSED = {"10.1002--eat.24415": 4, "10.1002--hbm.26595": 41,
               "10.1002--mpr.70006": 2}

    #: Guards added to a tool AFTER these wave-3 artefacts were recorded. A
    #: frozen toolcall log cannot supply a parameter that did not exist when it
    #: was written, so such a slot shows as `defaulted` through no failure of the
    #: run -- it is tool evolution, not a missing input. Both landed 2026-08-08:
    #: `bound_source` on `check_sd_or_se` (it already existed on `grim_check`),
    #: and `data_type` on `grim_percentage` (it already existed on `grim_check`;
    #: eat.24415 called grim_percentage 60 times and hbm.26595 6 times, none
    #: with a data_type). The C3 property is measured over the guards that DID
    #: exist at run time.
    POST_WAVE3_GUARDS = {("check_sd_or_se", "bound_source"),
                         ("grim_percentage", "data_type")}

    @pytest.mark.parametrize("paper", ["10.1002--eat.24415", "10.1002--hbm.26595",
                                       "10.1002--mpr.70006"])
    def test_the_only_defaulted_slot_was_the_sound_one(self, paper):
        """Before: 23/26 supplied (88%) across the three papers and the alarm on
        every one. After: every alarmable slot that EXISTED at run time was
        supplied, and every excusal is the one guard whose default is the correct
        reading of a printed value. A guard added later (see POST_WAVE3_GUARDS)
        cannot be supplied retroactively, so it is measured out of the property."""
        import json
        from pathlib import Path
        p = Path(f"tests/fixtures/papers/high_value_pdfs_to_run_on/{paper}/forensic_review_wave3/"
                 "toolcalls.stage1.json")
        if not p.exists():
            pytest.skip("run artefacts not present")
        a = _guard_audit(json.loads(p.read_text()))

        post = [d for d in a["defaulted_calls"]
                if (d["tool"], d["guard"]) in self.POST_WAVE3_GUARDS]
        contemporaneous = [d for d in a["defaulted_calls"]
                           if (d["tool"], d["guard"]) not in self.POST_WAVE3_GUARDS]
        # The real regression property: no guard that existed when this run was
        # recorded was left at its default.
        assert contemporaneous == []
        assert a["n_excused"] == self.EXCUSED[paper]
        assert {e["guard"] for e in a["excused_calls"]} == {"provenance"}
        assert "check_table" in {e["tool"] for e in a["excused_calls"]}

        if post:
            # hbm.26595 and eat.24415: guard slots the frozen runs could not
            # fill because the guards postdate them. The alarm they now raise is
            # a TRUE by-design ignorance-sentinel signal (a defaulted data_type /
            # bound_source can cause a false ALL-CLEAR by under-escalation, or a
            # false accusation by running a granularity test on continuous data),
            # NOT the every-run false alarm C3 removed. On a live run the model
            # would be nudged to supply them, exactly as for `grim_check`.
            assert {(d["tool"], d["guard"]) for d in post} <= self.POST_WAVE3_GUARDS
        else:
            assert a["supplied_rate"] == 1.0
            assert ALARM not in a["verdict"]
