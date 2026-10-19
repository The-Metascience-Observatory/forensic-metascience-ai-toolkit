"""The nine defects an adversarial pass found in the checks bridge, pinned.

EVERY FIXTURE HERE WAS BUILT BY SOMEONE TRYING TO BREAK THE BRIDGE, not by the
person who wrote it, and each one RAN and produced a false accusation (or lost a
whole run) against the code as committed. They are kept verbatim rather than
paraphrased: a regression test written from a description of a defect tests the
description.

The paper is "the Delta trial" -- one synthetic account whose every answer is
known by construction, deliberately assembled by hand rather than through
`bind.assemble`, so that a defect in the assembler cannot hide a defect in the
bridge. `tests/test_scaffold_checks.py` covers the other direction, on an
account the assembler built.
"""

from __future__ import annotations

import copy
import json
import shutil

import pytest

from metascience_agent.scaffold import checks, structure

# --------------------------------------------------------------------------
# The Delta trial
# --------------------------------------------------------------------------

TEXT = """# The Delta Trial: falls and mood in older adults

## Methods

Thirty adults completed the study; the analysed sample was n = 30.
Falls were counted as whole events per participant, so each participant
contributes a whole number of falls over the study period.
Mood was rated on a 1 to 7 point scale and was scored in whole points.
Weight was measured in kilograms to one decimal place on a calibrated scale.
Adherence was expressed as a percentage of scheduled sessions attended.

## Results

Twenty-six (86.7%) of the 30 participants reported at least one fall.
The mean mood score was 3.50 (SD 1.20) and the mean weight was 71.4 kg.
Table 1 gives the descriptive statistics for the whole sample.
"""


def _var(vid, kind, *, source="not_stated", lower=None, upper=None,
         bquote=None, step=None, gquote=None, name=None):
    return {"id": vid, "name": name or vid.split(":")[-1], "kind": kind,
            "printed_as": [],
            "bounds": {"source": source, "lower": lower, "upper": upper, "quote": bquote},
            "granularity": {"per_subject_step": step, "quote": gquote}}


def _cell(vid, statistic, printed, *, row, col=1, variable_id=None, id_check="agrees",
          source="table", quote_verified="cell", group="grp:all", table="table:1",
          col_label="All participants"):
    got = checks._read_plain(printed)
    return {"id": vid, "statistic": statistic, "printed": printed,
            "numeric": (got or {}).get("value"), "decimals": (got or {}).get("decimals", 0),
            "printed_form": "plain", "units": None, "variable_id": variable_id,
            "id_check": id_check, "statistic_disputed": False,
            "coordinate": {"study_id": "study:main", "group_id": group, "phase_id": None},
            "applies_to_all_groups": False, "source": source,
            "location": {"kind": "table_cell", "table_id": table, "row": row, "col": col,
                         "row_label": "", "col_label": col_label},
            "quote": str(printed), "quote_verified": quote_verified, "section": "Table 1"}


def account(*, mood_mean="3.50") -> dict:
    """Honest by construction: every check below should run and clear."""
    return {
        "schema_version": "scaffold_account/1",
        "paper": {"doi": "10.0000/delta", "title": "The Delta Trial"},
        "studies": [{"id": "study:main", "label": "Main study",
                     "groups": [{"id": "grp:all", "label": "All participants (n = 30)",
                                 "n": 30, "n_source": "label"}]}],
        "variables": [
            _var("var:mood", "integer_score", source="stated", lower=1, upper=7,
                 bquote="Mood was rated on a 1 to 7 point scale",
                 step=1, gquote="was scored in whole points", name="Mood score"),
            _var("var:falls", "count", source="definitional", lower=0, upper=None,
                 bquote="Falls were counted as whole events per participant",
                 step=1, gquote="contributes a whole number of falls", name="Falls"),
            _var("var:weight", "continuous", name="Weight (kg)"),
            _var("var:adherence", "percentage_of_subjects", name="Any fall"),
        ],
        "values": [
            _cell("val:n", "n", "30", row=1),
            _cell("val:mood:mean", "mean", mood_mean, row=2, variable_id="var:mood"),
            _cell("val:mood:sd", "sd", "1.20", row=2, variable_id="var:mood"),
            _cell("val:falls:mean", "mean", "2.40", row=3, variable_id="var:falls"),
            _cell("val:falls:sd", "sd", "1.50", row=3, variable_id="var:falls"),
            _cell("val:any:count", "count", "26", row=4, variable_id="var:adherence"),
            _cell("val:any:pct", "percentage", "86.7", row=4, variable_id="var:adherence"),
        ],
        "comparisons": [], "claims": [],
        "statistical_analysis": {"alpha_declared": 0.05},
    }


def _run(acc, text=TEXT):
    return checks.evaluate(acc, text)


def _ran(got, check_id):
    return next((r for r in got["checks"] if r["check_id"] == check_id), None)


def _ref(got, check_id):
    return next((r for r in got["refused"] if r["check_id"] == check_id), None)


def _by_id(acc, vid):
    return next(v for v in acc["values"] if v["id"] == vid)


def _var_of(acc, vid):
    return next(v for v in acc["variables"] if v["id"] == vid)


GRANULARITY_CHECKS = ("chk:grim:val:mood:mean", "chk:grimmer:val:mood:mean",
                      "chk:sprite:val:mood:mean")
BOUND_ARGS = ("scale_min", "scale_max", "variable_range_min", "variable_range_max",
              "min_val", "max_val")


class TestTheFixtureIsHonest:
    """Without this, every test below could pass by refusing everything."""

    def test_the_honest_account_runs_seven_checks_and_clears_them(self):
        got = _run(account())
        assert got["n_run"] == 7, json.dumps(got["refused_by_reason"])
        assert {r["severity"] for r in got["checks"]} <= {"consistent", "indeterminate"}

    def test_the_planted_mean_is_caught(self):
        """3.51 at n = 30 is GRIM-impossible. A bridge that refused everything
        would pass the whole file; this is what stops it."""
        r = _ran(_run(account(mood_mean="3.51")), "chk:grim:val:mood:mean")
        assert r["severity"] == "impossible" and r["result"]["failure_mode"] == "granularity"


# --------------------------------------------------------------------------
# 1. The located-quote gate accepted any substring
# --------------------------------------------------------------------------


class TestAQuoteHasToProveSomething:
    @pytest.mark.parametrize("quote", ["a", "the", "1"])
    def test_a_quote_shorter_than_the_minimum_fragment_licenses_no_bound(self, quote):
        """`quotes._MIN_FRAGMENT` exists for exactly this and was not applied.
        Measured: a bounds quote of `a` located, licensed `bound_source: stated`
        against a planted 1-2 scale, and returned GRIM `impossible`."""
        acc = account()
        _var_of(acc, "var:mood")["bounds"] = {"source": "stated", "lower": 1, "upper": 2,
                                              "quote": quote}
        got = _run(acc)
        for cid in GRANULARITY_CHECKS + ("chk:sd_or_se:val:mood:sd",):
            assert _ran(got, cid) is None, (cid, _ran(got, cid)["severity"])
            assert _ref(got, cid)["reason"] == "bound_quote_not_located"

    def test_a_real_sentence_is_not_evidence_for_a_bound_it_does_not_print(self):
        """The paper's own scale sentence, offered for a planted 1-2 scale. It
        locates, it is 38 characters, and it is about the right variable -- and
        it states 1 and 7, not 1 and 2."""
        acc = account()
        _var_of(acc, "var:mood")["bounds"] = {
            "source": "stated", "lower": 1, "upper": 2,
            "quote": "Mood was rated on a 1 to 7 point scale"}
        got = _run(acc)
        for cid in GRANULARITY_CHECKS + ("chk:sd_or_se:val:mood:sd",):
            assert _ran(got, cid) is None
            assert _ref(got, cid)["reason"] == "bound_quote_does_not_state_it"

    def test_the_papers_own_bound_still_passes(self):
        r = _ran(_run(account()), "chk:grim:val:mood:mean")
        assert (r["args"]["scale_min"], r["args"]["scale_max"]) == (1, 7)
        assert r["args"]["bound_source"] == "stated"

    def test_a_definitional_bound_the_kind_makes_necessary_needs_no_numeral(self):
        """`Falls were counted as whole events per participant` never prints the
        0. A count cannot go below 0 by definition, which is what
        `bound_source: logically_necessary` means."""
        r = _ran(_run(account()), "chk:grim:val:falls:mean")
        assert r["args"]["scale_min"] == 0 and r["args"]["scale_max"] is None
        assert r["args"]["bound_source"] == "logically_necessary"

    def test_a_definitional_bound_the_kind_does_not_force_is_held_to_the_numeral(self):
        acc = account()
        _var_of(acc, "var:falls")["bounds"] = {
            "source": "definitional", "lower": 2, "upper": None,
            "quote": "Falls were counted as whole events per participant"}
        got = _run(acc)
        assert _ref(got, "chk:grim:val:falls:mean")["reason"] == "bound_quote_does_not_state_it"

    @pytest.mark.parametrize("quote,why", [
        ("a", "one character"),
        ("the", "a stopword"),
        ("1", "a single digit"),
        ("Weight was measured in kilograms to one decimal place",
         "a 53-character real sentence about a DIFFERENT, CONTINUOUS variable"),
        ("Table 1 gives the descriptive statistics",
         "a real sentence about nothing relevant"),
    ])
    def test_a_quote_that_establishes_no_discreteness_licenses_no_grim(self, quote, why):
        """D3 says GRIM runs only where the PAPER establishes the step. Every
        quote here located, stamped `discreteness_source: stated`, and returned
        `impossible` / `granularity` on the planted mean -- including the one
        about a variable measured to one decimal place."""
        acc = account(mood_mean="3.51")
        _var_of(acc, "var:mood")["granularity"] = {"per_subject_step": 1, "quote": quote}
        got = _run(acc)
        for cid in GRANULARITY_CHECKS:
            assert _ran(got, cid) is None, (why, cid, _ran(got, cid)["args"])
            assert _ref(got, cid)["reason"] == "discreteness_assumed"

    def test_discreteness_language_about_another_variable_is_not_about_this_one(self):
        """`Falls were counted as whole events per participant` IS a granularity
        sentence. It is not evidence about Mood."""
        acc = account(mood_mean="3.51")
        _var_of(acc, "var:mood")["granularity"] = {
            "per_subject_step": 1,
            "quote": "Falls were counted as whole events per participant"}
        got = _run(acc)
        assert _ran(got, "chk:grim:val:mood:mean") is None
        row = _ref(got, "chk:grim:val:mood:mean")
        assert row["reason"] == "discreteness_assumed"
        assert "var:falls" in row["reasons"][0]["detail"]

    def test_the_papers_own_granularity_sentence_still_passes(self):
        r = _ran(_run(account(mood_mean="3.51")), "chk:grim:val:mood:mean")
        assert r["args"]["discreteness_source"] == "stated"
        assert r["premises"]["discreteness"]["quote_states_discreteness"] is True


# --------------------------------------------------------------------------
# 2. The coefficient guard matched one string and protected one family
# --------------------------------------------------------------------------


def _coefficient_table(acc, estimate_statistic, *, caption=None, disputed=False):
    """`8.57 (3.03)` in a `Coefficient (SE)` column -- the ajcp Table 2 cell,
    typographically identical to a mean beside its SD (CLAUDE.md 8h)."""
    for vid, stat, printed in (("val:t2:b", estimate_statistic, "8.57"),
                               ("val:t2:sd", "sd", "3.03")):
        v = _cell(vid, stat, printed, row=1, table="table:2", variable_id="var:mood",
                  col_label="Coefficient (SE)")
        v["statistic_disputed"] = disputed
        acc["values"].append(v)
    if caption is not None:
        acc["document"] = {"tables": [{"id": "table:2", "caption": caption}]}
    return acc


class TestAModelOutputIsNotADescriptiveStatistic:
    @pytest.mark.parametrize("cid", ["chk:sd_or_se:val:t2:sd", "chk:grim:val:t2:b",
                                     "chk:grimmer:val:t2:b", "chk:sprite:val:t2:b"])
    def test_the_documented_mislabel_reaches_no_granularity_family(self, cid):
        """Retype the neighbour `mean` and the old guard -- which asked only
        `value_ids.get("coefficient")`, and only for `check_sd_or_se` -- saw
        nothing. Measured: GRIM `impossible`, GRIMMER `suspicious`, SPRITE
        `suspicious` on an honest regression coefficient."""
        got = _run(_coefficient_table(account(), "mean"))
        assert _ran(got, cid) is None, (cid, _ran(got, cid)["severity"])
        assert _ref(got, cid)["reason"] == "reports_model_output"

    @pytest.mark.parametrize("estimate", ["effect_size", "ratio", "rate", "other",
                                          "score", "test_statistic", "coefficient"])
    def test_no_estimate_shaped_word_gets_the_dispersion_adjudicated(self, estimate):
        acc = _coefficient_table(account(), estimate)
        acc["values"].append(_cell("val:t2:mean", "mean", "4.10", row=1, table="table:2",
                                   variable_id="var:mood", col_label="Coefficient (SE)"))
        got = _run(acc)
        assert _ran(got, "chk:sd_or_se:val:t2:sd") is None, estimate

    def test_the_tables_own_caption_is_read_when_the_band_says_nothing(self):
        acc = account()
        for vid, stat, printed in (("val:t2:b", "mean", "8.57"), ("val:t2:sd", "sd", "3.03")):
            acc["values"].append(_cell(vid, stat, printed, row=1, table="table:2",
                                       variable_id="var:mood", col_label="Model 1"))
        acc["document"] = {"tables": [{"id": "table:2", "caption":
                                       "Associations between inclusive leadership and EBP use"}]}
        got = _run(acc)
        assert _ref(got, "chk:grim:val:t2:b")["reason"] == "reports_model_output"

    def test_the_guard_is_the_repos_own_and_not_a_second_copy(self):
        from metascience_agent import prepass
        assert prepass.reports_model_output("Coefficient (SE)", None)
        assert prepass.reports_model_output(None, "Associations between x and y")
        assert prepass.reports_model_output("All participants", "Descriptive statistics") is None

    def test_a_cell_the_account_marks_disputed_is_refused(self):
        """`reconstruct.kind_consistency` sets `statistic_disputed` when the same
        header and printed form was read as another kind elsewhere in the paper.
        A kind is these checks' premise; the bridge read the field nowhere."""
        acc = account()
        _by_id(acc, "val:mood:mean")["statistic_disputed"] = True
        _by_id(acc, "val:mood:sd")["statistic_disputed"] = True
        got = _run(acc)
        for cid in GRANULARITY_CHECKS + ("chk:sd_or_se:val:mood:sd",):
            assert _ran(got, cid) is None, cid
            assert "statistic_kind_disputed" in {x["reason"] for x in _ref(got, cid)["reasons"]}

    def test_an_ordinary_descriptive_column_is_untouched(self):
        assert _run(account())["n_run"] == 7


# --------------------------------------------------------------------------
# 3. The denominator passed no provenance or binding gate
# --------------------------------------------------------------------------


class TestTheDenominatorIsAnInput:
    @pytest.mark.parametrize("source", ["figure", "figure_caption", "supplement"])
    def test_a_figure_read_denominator_reaches_no_check(self, source):
        """Measured: an n read off a figure supplied the denominator of an exact
        GRIM call stamped `provenance: printed_table`, and 3.51 at that n came
        back `impossible`."""
        acc = account(mood_mean="3.51")
        _by_id(acc, "val:n").update({"source": source, "quote_verified": "verbatim",
                                     "printed_in_quote": True,
                                     "location": {"kind": "figure_caption", "offset": 5,
                                                  "end": 25}})
        got = _run(acc)
        assert got["n_run"] == 0, [r["check_id"] for r in got["checks"]]
        assert _ref(got, "chk:grim:val:mood:mean")["reason"] == "n_not_printed"

    @pytest.mark.parametrize("verdict", ["stitched", "unverified", "absent", None])
    def test_a_denominator_whose_quote_never_verified_reaches_no_check(self, verdict):
        acc = account(mood_mean="3.51")
        _by_id(acc, "val:n").update({"source": "prose", "quote_verified": verdict,
                                     "printed_in_quote": False,
                                     "location": {"kind": "results", "offset": 10, "end": 20}})
        got = _run(acc)
        assert got["n_run"] == 0
        assert _ref(got, "chk:grim:val:mood:mean")["reason"] == "n_not_printed"

    def test_a_denominator_whose_number_is_not_in_its_own_quote_reaches_no_check(self):
        """`applicability.census._index` has always skipped these rows: "an
        unverifiable premise is the thing this census must not use". The bridge
        used them."""
        acc = account(mood_mean="3.51")
        _by_id(acc, "val:n").update({"source": "prose", "quote_verified": "verbatim",
                                     "printed_in_quote": False,
                                     "quote": "thirty adults completed the study",
                                     "location": {"kind": "results", "offset": 10, "end": 20}})
        assert _run(acc)["n_run"] == 0

    @pytest.mark.parametrize("token", ["disagrees", "unjoined"])
    def test_a_denominator_the_join_contradicts_reaches_no_check(self, token):
        """The same row was refused as a mean everywhere in the run and supplied
        every denominator in it."""
        acc = account()
        _by_id(acc, "val:n")["id_check"] = token
        got = _run(acc)
        assert got["n_run"] == 0
        assert _ref(got, "chk:grim:val:mood:mean")["reason"] == "n_binding_not_corroborated"

    def test_the_docket_names_the_row_that_was_not_used(self):
        """`n rows ['30']` beside `n_not_printed` reads as a contradiction. The
        fact a person needs is which row was dropped, and under which gate."""
        acc = account()
        _by_id(acc, "val:n").update({"source": "figure", "quote_verified": "verbatim"})
        detail = _ref(_run(acc), "chk:grim:val:mood:mean")["reasons"][0]["detail"]
        assert "val:n" in detail and "provenance" in detail

    def test_the_denominators_value_id_is_in_value_ids(self):
        """The spec defines `value_ids` as "the value ids of every input (mean,
        sd, n, count, percentage)". An invariant asserted over it could not see
        the row that supplied the denominator of every call in the run."""
        got = _run(account())
        assert got["checks"]
        for r in got["checks"]:
            assert r["value_ids"].get("n") == "val:n", r["check_id"]

    @pytest.mark.parametrize("token", ["disagrees", "unjoined"])
    def test_no_uncorroborated_value_supplies_any_input(self, token):
        acc = account()
        _by_id(acc, "val:n")["id_check"] = token
        got = _run(acc)
        for r in got["checks"]:
            used = set(r["value_ids"].values()) | set(
                (r["premises"].get("n") or {}).get("value_ids") or [])
            assert "val:n" not in used, r["check_id"]


# --------------------------------------------------------------------------
# 4. The structure-version guard failed open
# --------------------------------------------------------------------------


def _a_structure(tag):
    return {"schema_version": "structure/1", "version": 2, "status": "frozen",
            "paper_identity": {"doi": "10.0000/delta"}, "document_sha256": tag,
            "pass1": {"studies": [{"id": "study:main", "note": tag}]},
            "pass2": {"variables": [{"id": "var:mood"}]}}


def _dir(tmp_path, name, *, provenance, block, struct):
    out = tmp_path / name
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    acc = account()
    if provenance is not ...:
        acc["provenance"] = {"structure_sha256": provenance, "structure_version": 2}
    if block is not ...:
        acc["structure"] = {"version": 2, "sha256": block}
    (out / "account.json").write_text(json.dumps(acc), encoding="utf-8")
    (out / "body.repaired.md").write_text(TEXT, encoding="utf-8")
    if struct is not None:
        (out / "structure.json").write_text(json.dumps(struct), encoding="utf-8")
    return out


class TestAnAbsentStampIsNotAgreement:
    def test_agreeing_stamps_run(self, tmp_path):
        st = _a_structure("AAA")
        sha = structure.content_sha256(st)
        out = _dir(tmp_path, "G0", provenance=sha, block=sha, struct=st)
        got = checks.run(out)
        assert got["n_run"] == 7 and got["structure_sha256"] == sha

    def test_an_unstamped_account_beside_a_structure_on_disk_refuses(self, tmp_path):
        """It ran, and `checks.json` then printed the disk structure's sha256 as
        the one it had verified against -- a claim the account never made."""
        out = _dir(tmp_path, "G1", provenance=..., block=..., struct=_a_structure("AAA"))
        with pytest.raises(structure.StructureMismatch, match="do not name the structure"):
            checks.run(out)
        assert not (out / "checks.json").exists()

    @pytest.mark.parametrize("empty", ["", None])
    def test_an_empty_or_null_stamp_beside_another_structure_refuses(self, tmp_path, empty):
        out = _dir(tmp_path, "G5", provenance=empty, block=empty,
                   struct=_a_structure("BBB"))
        with pytest.raises(structure.StructureMismatch, match="do not name the structure"):
            checks.run(out)

    def test_one_stamp_present_and_one_absent_refuses_and_names_it(self, tmp_path):
        sha = structure.content_sha256(_a_structure("AAA"))
        out = _dir(tmp_path, "G4", provenance=..., block=sha, struct=_a_structure("AAA"))
        with pytest.raises(structure.StructureMismatch, match="provenance. is unstamped"):
            checks.run(out)

    def test_an_account_that_names_no_structure_at_all_still_runs(self, tmp_path):
        """The third fact `artifact_stamps` exists to keep: an account with no
        structure names none, so there is none to have mixed."""
        out = _dir(tmp_path, "G8", provenance=..., block=..., struct=None)
        got = checks.run(out)
        assert got["n_run"] == 7 and got["structure_sha256"] is None

    def test_the_default_still_admits_a_legacy_unstamped_artifact(self):
        """`bind.assemble` passes artifact stamps where None means "made before
        the stamp existed", and that must stay a non-mismatch."""
        structure.refuse_mixed_versions({"pass3.meta.json": None,
                                         "table_1.recon.meta.json": "a" * 64}, "a" * 64)


# --------------------------------------------------------------------------
# 5. Two closed vocabularies failed open
# --------------------------------------------------------------------------


class TestTheVocabulariesAreAllowlists:
    def test_an_unrecognised_bound_source_passes_no_number(self):
        """`BOUND_SOURCE_OF.get(src, "assumed")` beside `if src == "not_stated"`
        let `inferred` keep its numeric 1-7 while labelling it `assumed`."""
        acc = account()
        _var_of(acc, "var:mood")["bounds"] = {
            "source": "inferred", "lower": 1, "upper": 7,
            "quote": "Mood was rated on a 1 to 7 point scale"}
        got = _run(acc)
        for r in got["checks"]:
            if r["variable_id"] != "var:mood":
                continue
            for name in BOUND_ARGS:
                assert r["args"].get(name) is None, (r["check_id"], name)
            assert r["args"].get("bound_source", "assumed") == "assumed"

    def test_the_two_admitted_sources_are_the_only_two(self):
        assert set(checks.BOUND_SOURCE_OF) == {"stated", "definitional"}

    @pytest.mark.parametrize("token", ["DISAGREES", "disagree", "Disagrees",
                                       "unjoined ", "no", "corroborated", ""])
    def test_an_id_check_outside_the_closed_set_is_not_corroboration(self, token):
        acc = account()
        _by_id(acc, "val:mood:mean")["id_check"] = token
        got = _run(acc)
        assert _ran(got, "chk:grim:val:mood:mean") is None, token
        assert _ref(got, "chk:grim:val:mood:mean")["reason"] == "binding_not_corroborated"

    @pytest.mark.parametrize("token", ["agrees", "join"])
    def test_the_two_corroborations_still_run(self, token):
        acc = account()
        _by_id(acc, "val:mood:mean")["id_check"] = token
        assert _ran(_run(acc), "chk:grim:val:mood:mean") is not None

    def test_a_model_only_binding_keeps_its_own_reason(self):
        acc = account()
        _by_id(acc, "val:mood:mean")["id_check"] = None
        assert _ref(_run(acc), "chk:grim:val:mood:mean")["reason"] == "binding_model_only"


# --------------------------------------------------------------------------
# 6. No per-call isolation, and a declared n was truncated not compared
# --------------------------------------------------------------------------


class TestOneCandidateCannotTakeTheRunWithIt:
    def test_a_zero_denominator_is_named_before_any_tool_divides_by_it(self):
        """`ZeroDivisionError` used to come out of the loop, and nothing at all
        was written: no `checks.json`, no docket, no record of the candidates
        that were fine.

        WAVE 7b MOVED THE ANSWER EARLIER, and this test moved with it. A
        denominator of `0` is not a small denominator, it is not a denominator,
        so it is refused by name before a tool sees it: `n_not_positive` on
        every candidate at that coordinate rather than one exception and six
        `indeterminate` verdicts computed from a number no paper printed. The
        conservation law is what this test was really about and it still holds.
        """
        acc = account()
        _by_id(acc, "val:n")["printed"] = "0"
        acc["studies"][0]["groups"][0]["n"] = None
        got = _run(acc)
        assert got["n_run"] + got["n_refused"] == got["n_candidates"]
        assert not [r for r in got["refused"] if r["reason"] == "check_raised"]
        assert "n_not_positive" in {r["reason"] for r in got["refused"]}
        assert not [r for r in got["checks"]], [r["check_id"] for r in got["checks"]]

    def test_a_candidate_that_raises_is_still_one_refusal_and_not_the_run(self):
        """The isolation itself, with a tool that raises on purpose -- because
        the vehicle the defect was found with (a zero denominator) no longer
        reaches a tool, and a guard tested only through a route that is now
        closed is a guard that has stopped being tested."""
        from metascience_agent import registry

        class _Boom:
            def call(self, args):
                raise RuntimeError("planted")

        real = registry.BY_NAME["grim_check"]
        try:
            registry.BY_NAME["grim_check"] = _Boom()
            got = _run(account())
        finally:
            registry.BY_NAME["grim_check"] = real
        raised = [r for r in got["refused"] if r["reason"] == "check_raised"]
        assert raised and "RuntimeError: planted" in raised[0]["reasons"][0]["detail"]
        assert got["n_run"] >= 1, "the other families went down with it"
        assert got["n_run"] + got["n_refused"] == got["n_candidates"]

    def test_a_hand_edited_group_n_still_writes_the_sidecar(self, tmp_path):
        out = tmp_path / "X5"
        out.mkdir()
        acc = account()
        acc["studies"][0]["groups"][0]["n"] = "thirty"
        (out / "account.json").write_text(json.dumps(acc), encoding="utf-8")
        (out / "body.repaired.md").write_text(TEXT, encoding="utf-8")
        checks.run(out)
        assert (out / "checks.json").is_file() and (out / "checks.md").is_file()

    @pytest.mark.parametrize("declared", [30.4, "thirty", "30.5", 29.99])
    def test_a_declared_n_that_is_not_an_exact_integer_refuses(self, declared):
        """`int(declared) != int(n)` passed 30.4 against a printed 30 and raised
        on `"thirty"`. Neither can be shown to agree with anything."""
        acc = account()
        acc["studies"][0]["groups"][0]["n"] = declared
        got = _run(acc)
        assert got["n_run"] == 0
        assert _ref(got, "chk:grim:val:mood:mean")["reason"] == "declared_n_not_comparable"

    @pytest.mark.parametrize("declared", [29, "29"])
    def test_a_declared_n_that_disagrees_still_refuses(self, declared):
        acc = account()
        acc["studies"][0]["groups"][0]["n"] = declared
        assert _ref(_run(acc), "chk:grim:val:mood:mean")["reason"] == "n_disagrees_with_structure"

    def test_a_declared_n_that_agrees_still_runs(self):
        for declared in (30, "30", 30.0):
            acc = account()
            acc["studies"][0]["groups"][0]["n"] = declared
            assert _ran(_run(acc), "chk:grim:val:mood:mean") is not None, declared

    def test_every_emitted_reason_is_in_the_closed_vocabulary(self):
        acc = account()
        _by_id(acc, "val:n")["printed"] = "0"
        acc["studies"][0]["groups"][0]["n"] = None
        for row in _run(acc)["refused"]:
            assert row["reason"] in checks.REASONS
            for r in row["reasons"]:
                assert r["premise"] in checks.PREMISE_ORDER


# --------------------------------------------------------------------------
# 7. check_count_percent never checked the percentage's scale
# --------------------------------------------------------------------------


class TestAPercentageIsOnAHundred:
    def test_a_proportion_variable_is_not_a_percentage(self):
        """`check_count_percent` compares `count / n * 100` to `percentage`; a
        fraction of one fails that by a factor of a hundred on a paper that did
        nothing wrong."""
        acc = account()
        _var_of(acc, "var:adherence")["kind"] = "proportion"
        _by_id(acc, "val:any:pct")["printed"] = "0.867"
        got = _run(acc)
        assert _ran(got, "chk:count_percent:val:any:pct") is None
        assert _ref(got, "chk:count_percent:val:any:pct")["reason"] == "percentage_is_a_proportion"

    def test_a_bare_fraction_under_no_percentage_kind_is_refused(self):
        """`0.73` is `0.73%` and `73%` in the same digits, and nothing here says
        which."""
        acc = account()
        _var_of(acc, "var:adherence")["kind"] = "categorical"
        _by_id(acc, "val:any:pct")["printed"] = "0.867"
        got = _run(acc)
        row = _ref(got, "chk:count_percent:val:any:pct")
        assert row["reason"] == "percentage_scale_not_established"

    def test_a_percent_sign_settles_it_whatever_the_kind(self):
        """The module's own rule: the `%` sign is not required and not
        forbidden. Where the paper prints one, the scale is not in doubt."""
        acc = account()
        _var_of(acc, "var:adherence")["kind"] = "categorical"
        _by_id(acc, "val:any:pct")["printed"] = "0.867%"
        assert _ran(_run(acc), "chk:count_percent:val:any:pct") is not None

    def test_a_percentage_kind_settles_it_without_a_percent_sign(self):
        r = _ran(_run(account()), "chk:count_percent:val:any:pct")
        assert r["args"]["percentage"] == 86.7

    def test_a_value_above_one_cannot_be_a_proportion_and_still_runs(self):
        """The gate is evidence, not vocabulary: demanding a percentage KIND
        refuses 109 honest cells on jamanetworkopen.37679, where the variable is
        `Age` and the column is the percentage in each band."""
        acc = account()
        _var_of(acc, "var:adherence")["kind"] = "categorical"
        assert _ran(_run(acc), "chk:count_percent:val:any:pct") is not None


# --------------------------------------------------------------------------
# 8. The dispersion's witness mean was provenance-checked and nothing else
# --------------------------------------------------------------------------


class TestTheWitnessMeetsEveryRuleTheInputsDo:
    @pytest.mark.parametrize("token", ["disagrees", "unjoined"])
    def test_a_witness_the_join_contradicts_licenses_no_adjudication(self, token):
        """The claim `this is a DESCRIPTIVE dispersion` rests entirely on the
        mean. The same row was refused for every other family in the run."""
        acc = account()
        _by_id(acc, "val:mood:mean")["id_check"] = token
        got = _run(acc)
        assert _ran(got, "chk:sd_or_se:val:mood:sd") is None
        assert _ref(got, "chk:sd_or_se:val:mood:sd")["reason"] == "binding_not_corroborated"

    @pytest.mark.parametrize("printed", ["Twenty-six", "84,299", "approximately 3.5",
                                         "6–9", "3.5*"])
    def test_a_witness_the_strict_grammar_refuses_licenses_no_adjudication(self, printed):
        acc = account()
        _by_id(acc, "val:mood:mean").update({"printed": printed, "numeric": None,
                                             "printed_form": "other"})
        got = _run(acc)
        assert _ran(got, "chk:sd_or_se:val:mood:sd") is None, printed
        assert _ref(got, "chk:sd_or_se:val:mood:sd")["reason"] == "printed_not_plain_numeral"

    def test_a_witness_in_a_model_output_column_licenses_no_adjudication(self):
        acc = account()
        _by_id(acc, "val:mood:mean")["location"]["col_label"] = "Coefficient (SE)"
        got = _run(acc)
        assert _ran(got, "chk:sd_or_se:val:mood:sd") is None

    def test_no_value_the_bridge_refuses_elsewhere_appears_in_any_call(self):
        """The general form: a value the strict grammar cannot read appears in
        NO call, in any role, including as a witness."""
        for printed in ("Twenty-six", "84,299", "approximately 3.5", "6–9"):
            acc = account()
            _by_id(acc, "val:mood:mean")["printed"] = printed
            got = _run(acc)
            bad = {v["id"] for v in acc["values"]
                   if checks._read_plain(v["printed"]) is None}
            assert bad
            for r in got["checks"]:
                assert not (set(r["value_ids"].values()) & bad), (r["check_id"], printed)

    def test_the_honest_witness_is_recorded_on_the_record(self):
        r = _ran(_run(account()), "chk:sd_or_se:val:mood:sd")
        assert r["premises"]["pairing"]["mean"] == "val:mood:mean"
        assert r["premises"]["binding"]["mean"] == "agrees"


# --------------------------------------------------------------------------
# The account is still never modified, whatever any of the above did
# --------------------------------------------------------------------------


def test_no_gate_writes_back_into_the_account():
    acc = _coefficient_table(account(mood_mean="3.51"), "mean")
    before = json.dumps(acc, sort_keys=True, default=str)
    checks.evaluate(copy.deepcopy(acc), TEXT)
    checks.evaluate(acc, TEXT)
    assert json.dumps(acc, sort_keys=True, default=str) == before
