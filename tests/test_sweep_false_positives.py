"""What a harness-fired sweep flags on HONEST papers, measured before it ships.

Greg asked for an exhaustive scheduler -- the harness firing every applicable
check on every eligible cell rather than the model choosing targets. Before
building it, the obvious question: what does a model-free sweep actually accuse
people of?

MEASURED, 2026-08-12, over 87 corpus papers: 2,113 checks fired and 21 came
back accusatory. Every one of the 21 was a FALSE POSITIVE, and both families
were visible by recomputing the printed numbers rather than by reading code:

  check_count_percent x 8, PLoS ONE 0128753 Table 1
       90/352 = 25.57%  printed 26.5%  -> implies n = 340
      127/352 = 36.08%  printed 37.3%  -> implies n = 340
      256/598 = 42.81%  printed 45.5%  -> implies n = 563
      209/598 = 34.95%  printed 37.1%  -> implies n = 563
    Rows agreeing on ONE unstated denominator are reporting over respondents to
    that item. Errors do not agree with each other; a denominator does.

  check_estimate_ci x 13, sparse odds ratios with a ZERO lower bound
      OR 0.01, CI [0.00, 32.53]   OR 1.88, CI [0.00, 31465.17]
    A ratio's CI is symmetric in log space and log(0) is undefined, so these
    have no geometric centre. Worse, the SCALE-INFERENCE rescue is itself
    gated on `ci_low > 0` -- so the exact condition that makes a ratio
    untestable also disabled the code that would have recognised it as a ratio,
    and the interval fell through to the arithmetic midpoint (16.27) and was
    flagged against it.

These tests pin the guards, and -- more importantly -- pin that the guards did
not buy the quiet by disarming the checks.
"""
import pathlib

import pytest

from forensic_metascience_ai_toolkit.dispatch import _clamp_shared_denominator, check_table
from forensic_metascience_ai_toolkit.tools.estimates import check_estimate_ci

ACCUSATORY = {"suspicious", "highly_suspicious", "impossible"}
REPO = pathlib.Path(__file__).resolve().parent.parent


class TestTheZeroLowerBound:
    def test_a_sparse_odds_ratio_is_not_accused(self):
        for est, lo, hi in [(0.01, 0.0, 0.76), (0.0, 0.0, 0.32),
                            (0.01, 0.0, 32.53), (1.88, 0.0, 31465.17)]:
            r = check_estimate_ci(est, lo, hi)
            assert r["severity"] not in ACCUSATORY, (est, lo, hi, r["severity"])

    def test_the_refusal_is_a_NOTE_and_not_a_problem(self):
        """Our inability to pick a scale is not an allegation about the paper.
        Appending it to `problems` would make it one."""
        r = check_estimate_ci(0.01, 0.0, 32.53)
        assert not r.get("problems")
        assert any("no scale" in str(n) for n in (r.get("notes") or []))

    def test_a_STATED_difference_with_a_zero_bound_is_still_tested(self):
        """The guard is about not knowing the scale, not about zero being
        magic. A difference's arithmetic midpoint is legitimate and must still
        be checked. `decimals` is passed because the tool requires it for a
        verdict -- omitting it widens the tolerance until nothing flags, which
        is what made this test fail on its first run."""
        good = check_estimate_ci(0.38, 0.0, 0.76,
                                 measure="mean difference", decimals=2)
        assert good["severity"] == "consistent"
        bad = check_estimate_ci(0.70, 0.0, 0.76,
                                measure="mean difference", decimals=2)
        assert bad["severity"] in ACCUSATORY

    def test_containment_still_runs_when_symmetry_cannot(self):
        """The scale-free half of the check is kept: an estimate outside its own
        interval is wrong on any scale."""
        r = check_estimate_ci(99.0, 0.0, 32.53)
        assert r["severity"] in ACCUSATORY


class TestTheSharedDenominator:
    def _rows(self, triples):
        return [{"tool": "check_count_percent", "severity": "suspicious",
                 "inputs": {"count": c, "percentage": p, "n": n}}
                for c, p, n in triples]

    def test_rows_agreeing_on_one_denominator_are_capped(self):
        rows = self._rows([(90, 26.5, 352), (127, 37.3, 352), (123, 36.2, 352)])
        _clamp_shared_denominator(rows)
        assert all(r["severity"] == "indeterminate" for r in rows)
        assert all(r["clamped_by"] == "shared_section_denominator" for r in rows)
        assert "340" in rows[0]["clamp_reason"], "the implied n must be named"

    def test_a_LONE_row_NEAR_the_header_is_capped(self):
        """CHANGED 2026-08-20, Greg's call. A lone row used to stay accusable on
        the ground that agreement is the whole signal -- true, but a row alone in
        its column is usually alone BY ACCIDENT: it is the only cell we could
        type, not the only cell the paper printed.

        Measured on PLoS ONE 0128753 Table 1: `10 (2.9%)` against a header n of
        352 implies 345, seven below. That is item non-response, and from one
        row it is indistinguishable from a one-digit slip in the percentage.
        Softened, a real slip still reaches the reader as `indeterminate` with
        its implied denominator named; unsoftened, an honest paper is accused."""
        rows = self._rows([(90, 26.5, 352)])          # implies 340, 12 below
        _clamp_shared_denominator(rows)
        assert rows[0]["severity"] == "indeterminate"
        assert rows[0]["clamped_by"] == "lone_row_near_denominator"
        assert "340" in rows[0]["clamp_reason"]

    def test_a_LONE_row_FAR_from_the_header_is_still_accused(self):
        """The clamp is not a blanket amnesty. A gap too large to be
        non-response on one item keeps its severity."""
        rows = self._rows([(90, 60.0, 352)])          # implies 150, far below
        _clamp_shared_denominator(rows)
        assert rows[0]["severity"] == "suspicious"
        assert "clamped_by" not in rows[0]

    def test_a_lone_row_ABOVE_the_header_is_still_accused(self):
        """Only downward. A denominator larger than the sample is not missing
        data -- you cannot have more respondents than participants."""
        rows = self._rows([(90, 24.0, 352)])          # implies 375, above 352
        _clamp_shared_denominator(rows)
        assert rows[0]["severity"] == "suspicious"
        assert "clamped_by" not in rows[0]

    def test_rows_implying_DIFFERENT_denominators_are_not_capped(self):
        """Disagreement among the disagreements is the shape of real error."""
        rows = self._rows([(90, 26.5, 352), (127, 41.0, 352)])
        _clamp_shared_denominator(rows)
        assert all(r["severity"] == "suspicious" for r in rows)

    def test_it_caps_rather_than_deletes(self):
        """The reader still learns the printed percentage disagrees with the
        header n -- a real and useful fact. What is withdrawn is the allegation."""
        rows = self._rows([(90, 26.5, 352), (127, 37.3, 352)])
        _clamp_shared_denominator(rows)
        assert len(rows) == 2
        assert all(r["inputs"]["n"] == 352 for r in rows)


class TestTheSweepIsQuietOnHonestPapers:
    """The measurement that gates the scheduler. If a model-free sweep accuses
    honest papers, an exhaustive one accuses them more often."""

    #: `funder_demo_2026-08-10` was in this list until its removal on
    #: 2026-09-02; the denominator (`n_papers`) is smaller by its two blinded
    #: papers from then on.
    CORPORA = ["tests/fixtures/papers/high_value_pdfs_to_run_on", "eval",
               "tests/fixtures/papers/cerebrolysin_run_2026-08-09", "tests/fixtures/papers/cerebrolysin_run2_datasets_2026-08-09"]

    @pytest.fixture(scope="class")
    def sweep(self):
        from forensic_metascience_ai_toolkit import prepass
        dirs = sorted({x.parent for c in self.CORPORA
                       for x in (REPO / c).rglob("*.xml")})
        if len(dirs) < 20:
            pytest.skip("corpus not present in this checkout")
        flagged, n_run = [], 0
        for d in dirs:
            for t in prepass.paper_tables(d):
                cells = t.get("cells") or []
                if not cells:
                    continue
                r = check_table(cells, None, None)
                n_run += r.get("n_checks_run") or 0
                flagged += [x for x in (r.get("results") or [])
                            if x.get("severity") in ACCUSATORY]
        return {"n_papers": len(dirs), "n_run": n_run, "flagged": flagged}

    def test_it_fires_a_lot_of_checks(self, sweep):
        """If this collapses, the test below passes for the wrong reason."""
        assert sweep["n_run"] > 1500, sweep["n_run"]

    def test_and_accuses_nobody(self, sweep):
        assert not sweep["flagged"], (
            f"{len(sweep['flagged'])} accusatory flags from {sweep['n_run']} "
            f"harness-fired checks over {sweep['n_papers']} papers. Every one "
            "must be triaged by hand before the scheduler may run: this is the "
            "measurement that decides whether firing MORE checks is safe.\n"
            + "\n".join(f"  {f.get('tool')}: {f.get('inputs')}"
                        for f in sweep["flagged"][:10]))


class TestALoneStragglerInAnExplainedColumn:
    """A singleton is judged by the company it keeps.

    MEASURED on PLoS ONE 0128753 Table 1, column n=352: thirteen flagged rows.
    Twelve sit in agreeing groups -- 350, 349, 340 and 351 each appear two or
    more times -- and exactly one, implying 345, is alone. A column otherwise
    fully explained by shared denominators, with one straggler seven below the
    header, is another item's non-response. A column with SEVERAL unexplained
    disagreements is error-shaped and every one of them stays accusable.
    """

    @staticmethod
    def _rows(triples):
        return [{"tool": "check_count_percent", "severity": "suspicious",
                 "inputs": {"count": c, "percentage": p, "n": n}}
                for c, p, n in triples]

    def test_a_straggler_beside_explained_groups_is_capped(self):
        rows = self._rows([
            (193, 55.1, 352), (157, 44.9, 352),   # both imply 350 -- explained
            (10, 2.9, 352),                        # implies 345 -- the straggler
        ])
        _clamp_shared_denominator(rows)
        assert rows[0]["clamped_by"] == "shared_section_denominator"
        assert rows[2]["clamped_by"] == "lone_row_near_denominator"
        assert all(r["severity"] == "indeterminate" for r in rows)

    def test_two_unexplained_stragglers_are_both_still_accused(self):
        """Even when both sit near the header. Disagreement among the
        disagreements is the shape of real error."""
        rows = self._rows([
            (193, 55.1, 352), (157, 44.9, 352),   # explained
            (10, 2.9, 352),                        # implies 345
            (90, 26.5, 352),                       # implies 340 -- a second one
        ])
        _clamp_shared_denominator(rows)
        assert rows[2]["severity"] == "suspicious"
        assert rows[3]["severity"] == "suspicious"


class TestAFourDigitSampleSizeIsNotThreeDigits:
    """A regex alternation that manufactured accusations on honest papers.

    `dispatch._N_IN_LABEL` read a header's stated n as
    `(\\d{1,3}(?:,\\d{3})*|\\d+)`. The first alternative matches THREE digits
    with the comma group empty and succeeds, and `finditer` has nothing after
    the group to force backtracking -- so `N = 2749` was read as 274.

    That is not a cosmetic misparse. The truncated n enters
    `values.check_stated_denominators` at column level, where the near-miss
    rescue `explaining_denominator` searches only DOWNWARD from the stated n.
    A percentage computed over 2,749 is unreachable from any denominator
    <= 274, so every ordinary count in the column is accused.

    MEASURED on the table below, whose arithmetic is exact against N = 2749:
    before, `{'indeterminate': 1, 'suspicious': 3}`; after, `{'consistent': 4}`.

    The sibling copies in `celltypes` and `cellformat` carry the same
    alternation and are SAFE -- every use there sits inside a `re.fullmatch`
    with a trailing anchor, so backtracking rescues them. This was the only
    unanchored `finditer` use, which is the argument for one facet grammar
    rather than four hand-copied regexes.
    """

    HEADER = "Cohort, n (%) (N = 2749)"
    #: Female 1237/2749 = 45.0%, smoker 247/2749 = 9.0%, diabetes 110/2749 =
    #: 4.0%, prior stroke 27/2749 = 1.0%. Every row reproduces exactly.
    ROWS = [("Female", 1237, 45.0), ("Current smoker", 247, 9.0),
            ("Diabetes", 110, 4.0), ("Prior stroke", 27, 1.0)]

    @staticmethod
    def _cells(header, rows):
        return [{"raw": f"{c} ({p})", "row": i, "col": 1,
                 "row_label": lab, "col_label": header}
                for i, (lab, c, p) in enumerate(rows)]

    def test_the_header_n_is_read_whole(self):
        from forensic_metascience_ai_toolkit.dispatch import header_ns
        for label, expected in [("Early Adolescent Group (N=2749)", 2749),
                                ("Males (N = 1165)", 1165),
                                ("Total (N = 10432)", 10432),
                                ("Low-risk CVDs (n = 1293)", 1293),
                                ("Total (n = 1,204)", 1204),
                                ("Total (n = 1,234,567)", 1234567),
                                ("All coalitions (n = 64)", 64),
                                ("Placebo (n ¼ 68)", 68)]:
            got = header_ns(label)
            assert got and got[0]["n"] == expected, (label, got)

    def test_an_honest_column_is_not_accused(self):
        """The end-to-end proof, through the shipping path."""
        from forensic_metascience_ai_toolkit.tools.celltypes import parse_cells
        from forensic_metascience_ai_toolkit.values import build_register, check_stated_denominators
        cells = self._cells(self.HEADER, self.ROWS)
        reg = build_register(tables=[{"name": "Table 1",
                                      "parsed": parse_cells(cells), "cells": cells}])
        out = check_stated_denominators(reg)
        assert out["n_ran"] == 4, out
        assert out["by_severity"] == {"consistent": 4}, out["by_severity"]

    def test_the_guard_did_not_buy_quiet_by_disarming_the_check(self):
        """A real disagreement in the same shape must still be caught, or the
        test above passes for the wrong reason."""
        from forensic_metascience_ai_toolkit.tools.celltypes import parse_cells
        from forensic_metascience_ai_toolkit.values import build_register, check_stated_denominators
        wrong = [("Female", 1237, 45.0), ("Current smoker", 247, 31.0)]
        cells = self._cells(self.HEADER, wrong)
        reg = build_register(tables=[{"name": "Table 1",
                                      "parsed": parse_cells(cells), "cells": cells}])
        out = check_stated_denominators(reg)
        assert any(k in ACCUSATORY for k in out["by_severity"]), out["by_severity"]


class TestABandDoesNotBindTheRowsBeneathIt:
    """A row-section band leaking its variable into the rows it governs.

    `fold_section_bands` writes a band into the row label as `Band | Stub`, and
    `binding_candidates` matched its containment rule against the WHOLE label --
    so the band's variable name was handed to rows that are about something
    else.

    MEASURED on 10.1002--ajcp.70049: three of thirteen auto-bindings wrong, all
    three by this mechanism. The one that matters is below: a mean of 35.78
    coalition MEMBERS bound to `Level of technical assistance received`, an
    `ordinal_category` declaring bounds 0-3. The mis-binding manufactured a
    scale ceiling the paper never stated, `dispatch._drop_unbounded` then
    admitted the bounded checks the true binding refuses, and the admitted tool
    returns `impossible` on a correctly reported number.
    """

    VARS = [
        {"id": "v_ta", "name": "Level of technical assistance received",
         "family": "ordinal_category", "lower_bound": 0, "upper_bound": 3},
        {"id": "v_members", "name": "Number of active coalition members",
         "family": "count", "lower_bound": 0, "upper_bound": None},
        {"id": "v_state", "name": "State", "family": "binary"},
        {"id": "v_ctc", "name": "Follows the Communities That Care model",
         "family": "binary"},
        {"id": "v_idm", "name": "Inclusive decision making",
         "family": "likert_composite", "lower_bound": 1, "upper_bound": 5},
    ]

    #: The three real mis-bindings, verbatim from the run's `auto_bound_rows`.
    LEAKED = [
        "Level of technical assistance received | Number of coalition members (mean, SD)",
        "State | Communities That Care (n, %)",
        "State | Externally funded (n, %)",
    ]

    def _rows(self, labels):
        from forensic_metascience_ai_toolkit.values import binding_candidates
        return {r["row_label"]: r for r in binding_candidates(labels, self.VARS)}

    #: What each leaked row SHOULD bind to. Two are recoverable once the band
    #: stops competing, because the declared name wraps the row label with
    #: words on both sides -- which substring containment cannot see and the
    #: token rule can. The third needs stemming (funded/funding) and stays
    #: unbound, which is the safe direction.
    TRUTH = {
        "Level of technical assistance received | Number of coalition members (mean, SD)": "v_members",
        "State | Communities That Care (n, %)": "v_ctc",
        "State | Externally funded (n, %)": None,
    }

    def test_a_band_never_binds_the_rows_beneath_it(self):
        """The invariant is about the BAND, not about refusing to bind. A row
        may bind on its own stub; it may never acquire the band's variable."""
        rows = self._rows(self.LEAKED)
        for label in self.LEAKED:
            band_var = label.split(" | ")[0]
            got = [c["variable_id"] for c in rows[label]["candidates"]]
            band_ids = [c["variable_id"] for c in rows[label].get("band_candidates") or []]
            assert not (set(got) & set(band_ids)), (label, got, band_ids)

    def test_the_rows_bind_correctly_once_the_band_stops_competing(self):
        """Refusing was never the goal -- it was the safe fallback. Measured
        against a hand-made ground truth for the 16 Table 1 rows of
        10.1002--ajcp.70049: containment on the whole folded label scores 8
        correct / 0 wrong / 8 missed and takes 3 WRONG bindings the moment a
        band over-extends; containment on the innermost stub alone scores 3 /
        1 / 12; the live rule scores 9 / 0 / 7 and takes 0 wrong under an
        over-extended band."""
        rows = self._rows(self.LEAKED)
        for label, want in self.TRUTH.items():
            got = [c["variable_id"] for c in rows[label]["candidates"]]
            if want is None:
                assert len(got) != 1, (label, got)
            else:
                assert got == [want], (label, got, want)

    def test_a_bare_numeral_row_label_cannot_bind_by_string(self):
        """`1`, `2 or 3` and `None` are LEVEL names, and a bare numeral is a
        substring of half the prose in any corpus. The model wrote the variable
        name "EBP fidelity (also printed as 'EBP adherence' in Table 1)" -- a
        parenthetical NOTE in an identifier field -- so the row label `1`
        matched it on the digit in "Table 1". Currently inert, because the
        cell-kind gate admits only grim_percentage/check_count_percent for an
        `n_percent` row whatever it is bound to; one mean_sd row away from
        admitting the bounded-scale checks."""
        vs = self.VARS + [{"id": "v_fid2", "family": "likert_composite",
                           "lower_bound": 1, "upper_bound": 7,
                           "name": "EBP fidelity (also printed as 'EBP adherence' in Table 1)"}]
        from forensic_metascience_ai_toolkit.values import binding_candidates
        for label in ("1", "2 or 3", "  7  "):
            r = binding_candidates([label], vs)[0]
            assert r["status"] == "unmatched", (label, r["candidates"])

    def test_the_band_relationship_is_still_reported(self):
        """Refusing to bind is not the same as pretending we saw nothing. The
        loss must be inspectable, or a coverage drop reads as a parser bug."""
        r = self._rows(self.LEAKED)["State | Communities That Care (n, %)"]
        assert r["band"] == "State"
        assert [c["variable_id"] for c in r["band_candidates"]] == ["v_state"]

    def test_a_row_whose_own_stub_names_a_variable_still_binds(self):
        """The guard must not buy its quiet by disarming the rule."""
        label = "Measures of inclusive decision-making | Inclusive decision making (mean, SD)"
        r = self._rows([label])[label]
        assert r["status"] == "bound"
        assert r["candidates"][0]["variable_id"] == "v_idm"

    def test_the_mis_binding_admitted_a_tool_that_accuses(self):
        """WHY the binding matters, stated as arithmetic rather than assertion.

        Under the wrong variable the row acquires a 0-3 ceiling and SPRITE is
        applicable; under the right one it is refused for want of an upper
        bound. Same printed numbers, opposite verdict."""
        from forensic_metascience_ai_toolkit.tools.sprite import sprite_reconstruct
        r = sprite_reconstruct(mean=35.78, sd=33.74, n=64,
                               scale_min=0, scale_max=3,
                               bound_source="stated", discreteness_source="stated")
        assert r["severity"] == "impossible", r["severity"]

        from forensic_metascience_ai_toolkit.dispatch import _drop_unbounded
        v_ta = dict(self.VARS[0])
        v_members = dict(self.VARS[1])
        kept_wrong, _ = _drop_unbounded(
            ("grim_check", "grimmer_check", "sprite_reconstruct"), v_ta)
        kept_right, refused = _drop_unbounded(
            ("grim_check", "grimmer_check", "sprite_reconstruct"), v_members)
        assert "sprite_reconstruct" in kept_wrong
        assert "sprite_reconstruct" not in kept_right and "sprite_reconstruct" in refused


class TestADerivedStatisticIsNotAPrintedOne:
    """`statistic_value` is a printed-reading field that carried no instruction.

    `effect_size` says in the schema: "AS THE PAPER PRINTED IT ... do NOT put
    your own computation here; that goes in `effect_size_estimated`, and merging
    the two would make a number we derived indistinguishable from one the
    authors published." `statistic_value` had no description at all, and the
    model filled it with Wald z's it computed itself.

    MEASURED on 10.1002--ajcp.70049: 2.658 = 1.01/0.38, 2.233 = 1.34/0.60,
    1.809 = 0.85/0.47, -3.007 = -4.51/1.50 -- none in the article. A
    statcheck-style tool fed one of these checks OUR arithmetic against THEIR
    p-value and reports the answer as a fact about their paper.

    The guard is corroboration, not a declaration: a flag the model must set
    fails open the moment it forgets, while asking whether the number is in the
    paper cannot be forgotten.
    """

    PAPER = REPO / "tests/fixtures/papers/high_value_pdfs_to_run_on" / "10.1002--ajcp.70049"

    def test_the_model_cannot_write_the_verdict(self):
        from forensic_metascience_ai_toolkit.anatomy import PIPELINE_ONLY_FIELDS
        assert "statistic_in_text" in PIPELINE_ONLY_FIELDS

    def test_a_derived_wald_z_is_caught(self):
        if not self.PAPER.is_dir():
            pytest.skip("corpus paper not present in this checkout")
        from forensic_metascience_ai_toolkit import agent
        res = {"findings": {"anatomy": {"tests": [
            {"id": "t1", "test_type": "poisson_regression", "location": "Table 2",
             "statistic_value": 2.658},
        ]}, "findings": []}}
        agent._annotate_quotes(res, str(self.PAPER))
        assert res["findings"]["anatomy"]["tests"][0]["statistic_in_text"] == "absent"

    def test_a_number_the_paper_printed_is_not_called_ours(self):
        """The off-switch: if everything came back `absent` the test above would
        pass for the wrong reason."""
        if not self.PAPER.is_dir():
            pytest.skip("corpus paper not present in this checkout")
        from forensic_metascience_ai_toolkit import agent
        res = {"findings": {"anatomy": {"tests": [
            {"id": "t1", "test_type": "other", "location": "Table 1",
             "statistic_value": 35.78},
        ]}, "findings": []}}
        agent._annotate_quotes(res, str(self.PAPER))
        assert res["findings"]["anatomy"]["tests"][0]["statistic_in_text"] == "present"

    def test_present_is_documented_as_weak(self):
        """`present` must never be read as verification. The most corrupt of the
        four derived values on this paper -- 10.0, a quotient of two rounded
        numbers -- stamps `present` because "10" occurs in every paper. Anything
        that later gates on this field must gate on `absent`, and the docstring
        is where that is recorded."""
        import forensic_metascience_ai_toolkit.anatomy as A
        import inspect
        src = inspect.getsource(A)
        assert "may GATE a tool on `absent` and may never LICENSE one on" in src


class TestAShortStubDoesNotMatchInsideALongerWord:
    """`in` is not a word test, and six live wrong bindings came from that.

    MEASURED over eight papers' declared variables and 2,467 distinct row
    labels: 112 bound, of which 6 wrong -- every one through the un-word-bounded
    containment arm. The row stub `No` matched `Number of comorbid CVD
    diagnoses` (the `N` and the `o` of "Number of") and bound five medication
    rows to a `count` variable; `Other` matched `mother-daughter
    intergenerational closeness`.

    `anatomy.py` fixed exactly this class in its assumption matcher, in these
    words: "Word-bounded, not `in`: a bare substring test lets a short key like
    'icc' match inside an unrelated word." The binder never got the fix.
    """

    VS = [{"id": "V_ncomorb", "name": "Number of comorbid CVD diagnoses", "family": "count"},
          {"id": "V_intergen", "name": "mother-daughter intergenerational closeness",
           "family": "continuous"},
          {"id": "v_fidelity", "family": "likert_composite",
           "name": "EBP fidelity (also printed as 'EBP adherence' in Table 1)"}]

    def _status(self, label):
        from forensic_metascience_ai_toolkit.values import binding_candidates
        return binding_candidates([label], self.VS)[0]

    def test_a_level_word_does_not_bind_inside_a_longer_word(self):
        for label in ("No", "Other", "On", "Or"):
            assert self._status(label)["status"] == "unmatched", (
                label, self._status(label)["candidates"])

    def test_the_guard_did_not_disarm_legitimate_containment(self):
        """`EBP adherence` sits inside a parenthetical note in the declared
        name, separated by punctuation and quotes -- the boundary must let that
        through, or the fix bought its quiet by breaking the rule."""
        r = self._status("EBP adherence")
        assert r["status"] == "bound" and r["candidates"][0]["variable_id"] == "v_fidelity"


class TestACitationYearIsNotAMeasurement:
    """Classifying a numeral as a citation year REMOVES it from the checkable
    floor, so this pattern is loosened only against a false-removal battery.

    MEASURED over the 12-paper corpus: 697 numerals sit inside an in-text
    citation marker and 577 (83%) reached the floor `unclassified`,
    indistinguishable from a number the paper reported. On one paper, 39 of the
    first 40 rows the viewer showed under "Not yet judged" were citation years.

    The cause was one house style against another: the connective alternation
    required whitespace before every connective, so `Smith et al. [2022]`
    matched and `Smith et al., [2016]` did not.
    """

    #: Must classify -- real citation shapes.
    CITATIONS = ["as shown by Smith et al., [", "as shown by Smith et al. [",
                 "prior work (Wood, ", "see Smith and Jones (", "as in Smith, 1997a, "]

    #: MUST NOT classify. A false positive here deletes a real number from the
    #: floor permanently and invisibly, which is the worse direction.
    NOT_CITATIONS = ["a cohort of (1989 ", "arms of 250, 2013, and ", "the test F (1,",
                     "the statistic t (", "we enrolled 2013 ", "collected in 2013, ",
                     "at baseline ("]

    def test_it_classifies_both_house_styles(self):
        from forensic_metascience_ai_toolkit.numerals import _CITATION
        for s in self.CITATIONS:
            assert _CITATION.search(s), s

    def test_and_removes_nothing_that_is_a_measurement(self):
        from forensic_metascience_ai_toolkit.numerals import _CITATION
        for s in self.NOT_CITATIONS:
            assert not _CITATION.search(s), s

    def test_the_docstring_claim_matches_the_code(self):
        """The comment above `_CITATION_AFTER` asserted that `(Wood 1989)`
        passes. It does not -- an author with no comma before the year never
        matches `_CITATION`. A false claim in a docstring is how the next
        person builds on a premise nobody checked."""
        from forensic_metascience_ai_toolkit.numerals import _CITATION
        assert not _CITATION.search("prior work (Wood ")
        assert _CITATION.search("prior work (Wood, ")


class TestAnAbbreviationDoesNotStealAnotherVariablesRefusal:
    """A variable a paper names by an ABBREVIATION, taking an averaging refusal
    away from the variable the averaging statement was actually about.

    THE SHAPE, AND IT IS HERE SO IT CANNOT COME BACK QUIETLY. `premises.
    anchor_score` requires a matched word of four characters, so `ADL`, `PSS`,
    `IQ` and `BMI` scored 0.0 against every sentence of their own paper and no
    premise could be attributed to them either way. `108e9ec6` relaxed the floor
    for tokens the account itself prints in capitals, which is right -- and the
    same score is read in the opposite direction too, to decide what a sentence
    is NOT about. An abbreviation is the strongest possible rival by
    construction: ONE content word, so 1.0 whenever it appears at all, against
    the 0.5 a two-word name scores when a paper writes `vigour` for `Seed
    vigour`.

    MEASURED, default path, no flag, honest paper: seed vigour graded 0-16 in
    whole points by each of two inspectors and reported as the mean of the two
    cards, so it moves in HALF points and no integer total reaches its mean.
    Declare a `BMI` beside it and the paper's own withdrawal --

        The vigour and BMI figures were averaged across the two inspectors'
        cards.

    -- is read as BMI's, the step of 1 stands and GRIM returns `impossible`.
    Clean at `a24add71`, `impossible` at `108e9ec6`, on FOUR sentence shapes
    through THREE different comparisons (`premises.anchor_score_agreed`,
    `is_anaphoric_averaging`, `_best_named`).

    THE RULE THE FIX STATES: the relaxation may RAISE a variable's own score and
    may never let a newly-anchorable rival remove a refusal from another one.

    Full fixture, mechanism-level assertions and the trap in the obvious fix:
    `tests/test_scaffold_checks_round19.py::
    TestAnAbbreviationMayNotTakeAnotherVariablesRefusalAway`.
    """

    @staticmethod
    def _r19():
        from tests import test_scaffold_checks_round19 as R19
        return R19

    def test_no_shape_of_it_accuses_the_honest_paper(self):
        R19 = self._r19()
        cases = dict(R19.STEALS)
        for label, sentence in cases.items():
            acc, text = R19.rival_account(), R19.paper(sentence)
            assert R19.accusations(acc, text) == [], label
        acc = R19.rival_account()
        assert R19.accusations(acc, R19.rival_antecedent_paper()) == [], \
            "the antecedent shape"

    def test_the_check_still_runs_so_the_quiet_is_not_bought(self):
        """The same account with nothing withdrawing the step IS convicted, and
        the honest whole-number companion is checked and passes. A guard that
        bought its silence by refusing everything fails here."""
        R19 = self._r19()
        fams = R19.families(R19.account(), R19.paper())
        assert ("grim", "var:vigour", "impossible") in fams
        assert ("grim", "var:packets", "consistent") in fams

    def test_the_abbreviation_itself_still_anchors(self):
        """And the recall `108e9ec6` bought is not reverted: a variable named
        `BMI` still scores against a sentence of its own paper."""
        from forensic_metascience_ai_toolkit.scaffold import premises
        v = {"id": "v", "name": "BMI", "label": "BMI", "printed_as": []}
        words = premises._sentence_words("BMI was measured at entry.")
        assert premises.anchor_score(v, words) == 1.0
