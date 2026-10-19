"""ROUND 29 -- A CHECK WE DO NOT MAKE IS AN ABSENCE, AND ABSENCES MUST BE
REPRESENTABLE.

WHAT WAS TESTED, AND WHY IT IS NOT A WIRING. The registry holds 62 tools and this
bridge calls 5. The other 57 were invisible in the docket: every total
`checks.json` carries counts something the bridge CONSIDERED, so a paper whose
127 candidates all refuse reads as "nothing here is checkable" when the truer
sentence is much narrower. This round asked whether wiring a sixth family --
`check_regression`, the tool for the coefficient-and-SE cells `to_sd_or_se_kwargs`
already refuses 24 times by name -- is sound. It is NOT, and the three reasons are
measured on the only real account this repo holds (ajcp.70049, 2026-09-13):

  1. NO df, AND THE VERDICT TURNS ON IT. Without a df `check_regression` returns
     `indeterminate` on every row. Supplied df = infinity it flags 3 of the 63
     rows RETYPED INTO THE FIXTURE BELOW from that paper's three regression
     tables; supplied df = n - k = 57 it flags 6, and FOUR OF THE SIX ARE
     DIFFERENT ROWS. Honest rows are accused by nothing but a df we would have
     invented, which is CLAUDE.md 8d invariant 1's prohibited move stated
     exactly.

     READ THE WORD "FIXTURE" THERE. Those counts are measurements of
     `TABLE2`/`TABLE34`, which retype Tables 2, 3 and 4 by hand; they are NOT
     measurements of the account, which types Table 4's estimates `other` rather
     than `coefficient` and so forms 42 rows, not 63. Stated without that
     qualifier they travelled into `NOT_WIRED_TOOLS["check_regression"]["why"]`
     as "3 of 63 coefficient rows on the working account", and `checks.md`
     printed 42 and 63 in one table row until 2026-09-13. A count is safe in a
     test that computes it and unsafe the moment it is copied into prose --
     which is the whole reason `unwired_population` counts and the `why` does
     not.
  2. THE SE PREMISE IS UNSTABLE INSIDE ONE ACCOUNT. Tables 2, 3 and 4 of that
     paper carry a byte-identical column band (`Coefficient | M (SD)`), and the
     reading typed their parentheticals `se`, `sd` and `dispersion_unstated`. The
     paper's own header and footnote call all three SD. So a wiring keyed on
     `statistic == "se"` takes its population from a coin flip: keyed on `se` it
     reaches Table 2's `-4.51 (1.50)` against a printed `< .001`, keyed on `sd`
     it reaches Table 3's `8.57 (3.03)` instead -- and `8.57 (3.03)` is the cell
     CLAUDE.md 8f records as having already produced one false `impossible` here.
  3. CORRECTED 2026-09-13 -- IT IS DIRECTIONAL, AND THE HAZARD IS THE ARGUMENT.
     This read "IT IS NOT DIRECTIONAL", which is false about the tool:
     `check_regression` delegates to `ttest._p_matches`, directional by default
     since 2026-08-12 for exactly this reason. Only `p_is_threshold=False` tests
     both sides. What is true is that the natural wiring supplies `False` -- it
     would read the argument off the printed literal, and a plain `.01` is not a
     threshold -- so conservative reporting would be flagged by an argument we
     chose. That fixes an argument; it does not block a wiring. Reasons 1 and 2
     block.

SO WHAT SHIPPED IS THE STATEMENT, NOT THE CALL. `NOT_WIRED_TOOLS` names the tool
and the premise; `unwired_population` COUNTS the population from the account so
the number cannot go stale; the `dispersion_of_coefficient` refusal names the
tool that would take the pair. Nothing new is called and no severity can move.

AND THE COUNT IS THE HALF THAT EARNS ITS PLACE. The session that prompted this
was told `recalc_stat_to_p` had 64 waiting p-values; the measured population on
the same account is ZERO, because the paper prints B, SE and p and never a test
statistic. A number computed from the account cannot make that mistake twice.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import registry
from forensic_metascience_ai_toolkit.scaffold import checks

ACCOUNT = (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "papers" /
           "high_value_pdfs_to_run_on" / "10.1002--ajcp.70049" / "scaffold" / "account.json")


@pytest.fixture(scope="module")
def account() -> dict:
    if not ACCOUNT.exists():
        pytest.skip(f"the working account is not on disk at {ACCOUNT}")
    return json.loads(ACCOUNT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def got(account) -> dict:
    return checks.evaluate(copy.deepcopy(account))


class TestTheStatementIsMadeAndCosts_Nothing:
    def test_every_not_wired_tool_is_a_real_registry_tool(self):
        """A tool named as unwired but absent from the registry would be a
        promise nobody can keep -- and five of the census's own seven tool names
        were stale exactly that way when `checks.py` came to call them."""
        for name in checks.NOT_WIRED_TOOLS:
            assert name in registry.BY_NAME, name

    def test_no_not_wired_tool_is_also_wired(self):
        """The two lists may not overlap, or the docket would say a tool is not
        called in the same breath as calling it."""
        assert not set(checks.NOT_WIRED_TOOLS) & set(checks.TOOL_OF.values())

    def test_every_blocked_on_is_in_the_closed_reason_vocabulary(self):
        """`blocked_on` is a refusal reason, so it obeys the same closed
        vocabulary every refusal does rather than inventing a second one."""
        for name, rec in checks.NOT_WIRED_TOOLS.items():
            assert rec["blocked_on"] in checks.REASONS, (name, rec["blocked_on"])

    def test_the_statement_accuses_nobody(self, got):
        """THE CARDINAL RULE, AND THE WHOLE SAFETY ARGUMENT FOR THIS ROUND. The
        change adds words and a count; it may not move a verdict, because it
        calls nothing."""
        assert got["n_run"] == 0
        assert got["by_severity"] == {}
        assert got["n_candidates"] == got["n_run"] + got["n_refused"]

    def test_the_population_is_counted_and_not_asserted(self, got, account):
        """The count must come from the account. Recount it here by a second,
        deliberately dumber route -- every table cell holding a coefficient and a
        dispersion with a p in the next column -- so a bridge that quietly
        returned a constant fails."""
        rec = {r["tool"]: r for r in got["tools_not_wired"]}
        cells: dict[tuple, set] = {}
        for v in account["values"]:
            loc = v.get("location") or {}
            if loc.get("kind") == "table_cell":
                cells.setdefault((loc["table_id"], loc["row"], loc["col"]), set()).add(
                    v.get("statistic"))
        want = sum(
            1 for (tid, row, col), stats in cells.items()
            if "coefficient" in stats
            and stats & {"sd", "se", "sem", "dispersion_unstated"}
            and "p_value" in cells.get((tid, row, col + 1), set()))
        assert rec["check_regression"]["population_in_this_account"] == want
        assert want > 0, "this account is the reason the round exists; it must be non-empty"

    def test_a_population_of_zero_is_reported_as_zero(self, got):
        """`recalc_stat_to_p` was reported to this session as 64 waiting
        p-values. The paper prints B, SE and p and never a test statistic, so its
        population is zero -- and a docket that rounded that up to "not wired,
        64 available" would have sent someone to build the wrong thing."""
        rec = {r["tool"]: r for r in got["tools_not_wired"]}
        assert rec["recalc_stat_to_p"]["population_in_this_account"] == 0

    def test_the_refusal_names_the_tool_that_would_take_the_pair(self, got):
        """A coefficient's SE refused as `dispersion_of_coefficient` must say
        that `check_regression` exists and takes it. Saying only "wrong family"
        is how a missing PREMISE reads as a missing CAPABILITY."""
        rows = [r for r in got["refused"] if r["reason"] == "dispersion_of_coefficient"]
        assert rows, "this account carries coefficient/SE cells; some must refuse this way"
        for r in rows:
            detail = next(x["detail"] for x in r["reasons"]
                          if x["reason"] == "dispersion_of_coefficient")
            assert "check_regression" in detail
            assert checks.NOT_WIRED_TOOLS["check_regression"]["blocked_on"] in detail

    def test_the_markdown_shows_it(self, got):
        md = checks.render_markdown(got)
        assert "Checks this bridge does not make" in md
        assert "check_regression" in md
        # A tool with no population here is not printed as a row -- an empty
        # count is not a finding about this paper.
        assert "recalc_stat_to_p" not in md.split("Checks this bridge does not make")[1]


class TestWhyItIsNotWired:
    """The three measurements, pinned so that a later session proposing the
    wiring has to falsify them rather than rediscover them."""

    #: Table 2 of ajcp.70049, read off the publisher markup and confirmed against
    #: the rendered image: (label, B, SE, printed p, p is a threshold).
    TABLE2 = (
        ("Communication", 1.01, 0.38, 0.01, False),
        ("Inclusive decision making", 1.34, 0.60, 0.03, False),
        ("Inclusion of community residents", 0.85, 0.47, 0.07, False),
        ("Number of EBP at baseline M1", 0.31, 0.04, 0.001, True),
        ("Number of EBP at baseline M2", 0.35, 0.04, 0.001, True),
        ("Number of EBP at baseline M3", 0.36, 0.05, 0.001, True),
        ("Communities That Care M1", 0.37, 0.26, 0.15, False),
        ("Communities That Care M2", 0.13, 0.24, 0.59, False),
        ("Communities That Care M3", 0.12, 0.24, 0.63, False),
        ("Externally funded M1", -0.34, 0.29, 0.24, False),
        ("Externally funded M2", -0.10, 0.28, 0.72, False),
        ("Externally funded M3", -0.23, 0.28, 0.41, False),
        ("Technical assistance M1", -0.01, 0.17, 0.97, False),
        ("Technical assistance M2", -0.01, 0.17, 0.98, False),
        ("Technical assistance M3", 0.10, 0.16, 0.55, False),
        ("Number of members M1", -0.03, 0.04, 0.45, False),
        ("Number of members M2", 0.02, 0.04, 0.66, False),
        ("Number of members M3", -0.01, 0.04, 0.72, False),
        ("Constant M1", -4.51, 1.50, 0.001, True),
        ("Constant M2", -6.24, 2.51, 0.01, False),
        ("Constant M3", -4.13, 1.91, 0.03, False),
    )

    #: Tables 3 and 4, same shape. Table 3 is the negative binomial and Table 4
    #: the hierarchical linear model, so the three tables are three different
    #: estimators under one column band -- which is the point: whatever df a
    #: wiring picked would have to be right for all three at once.
    #: (label, B, SE, printed p, p is a threshold, decimals of the SE).
    TABLE34 = (
        ("T3 Communication", 3.91, 1.78, 0.03, False, 2),
        ("T3 Inclusive decision making", 8.57, 3.03, 0.01, False, 2),
        ("T3 Inclusion of community residents", 4.53, 2.05, 0.03, False, 2),
        ("T3 Number of EBP at baseline M1", 0.01, 0.002, 0.01, False, 3),
        ("T3 Number of EBP at baseline M3", 0.01, 0.002, 0.001, True, 3),
        ("T3 Communities That Care M1", 3.16, 0.98, 0.001, True, 2),
        ("T3 Communities That Care M2", 2.16, 0.79, 0.01, False, 2),
        ("T3 Communities That Care M3", 1.61, 1.05, 0.13, False, 2),
        ("T3 Externally funded M1", 1.14, 1.04, 0.27, False, 2),
        ("T3 Externally funded M2", 1.88, 0.88, 0.03, False, 2),
        ("T3 Externally funded M3", 1.33, 1.05, 0.20, False, 2),
        ("T3 Technical assistance M1", -0.39, 0.72, 0.59, False, 2),
        ("T3 Technical assistance M2", -1.20, 0.73, 0.10, False, 2),
        ("T3 Technical assistance M3", -0.25, 0.66, 0.70, False, 2),
        ("T3 Number of members M1", -0.15, 0.17, 0.39, False, 2),
        ("T3 Number of members M2", 0.09, 0.17, 0.60, False, 2),
        ("T3 Number of members M3", -0.19, 0.18, 0.27, False, 2),
        ("T3 Constant M1", -13.55, 6.99, 0.05, False, 2),
        ("T3 Constant M2", -32.89, 12.17, 0.01, False, 2),
        ("T3 Constant M3", -15.93, 7.99, 0.05, False, 2),
        ("T4 Communication", 0.53, 0.60, 0.38, False, 2),
        ("T4 Inclusive decision making", -0.05, 0.98, 0.96, False, 2),
        ("T4 Inclusion of community residents", -0.10, 0.72, 0.89, False, 2),
        ("T4 Quality of EBP at baseline M1", 0.25, 0.13, 0.06, False, 2),
        ("T4 Quality of EBP at baseline M2", 0.24, 0.14, 0.08, False, 2),
        ("T4 Quality of EBP at baseline M3", 0.24, 0.14, 0.08, False, 2),
        ("T4 Communities That Care M1", -0.08, 0.38, 0.83, False, 2),
        ("T4 Communities That Care M2", -0.27, 0.33, 0.43, False, 2),
        ("T4 Communities That Care M3", -0.26, 0.33, 0.43, False, 2),
        ("T4 Externally funded M1", -0.23, 0.45, 0.61, False, 2),
        ("T4 Externally funded M2", -0.11, 0.44, 0.80, False, 2),
        ("T4 Externally funded M3", -0.09, 0.47, 0.84, False, 2),
        ("T4 Technical assistance M1", 0.27, 0.25, 0.28, False, 2),
        ("T4 Technical assistance M2", 0.32, 0.27, 0.23, False, 2),
        ("T4 Technical assistance M3", 0.32, 0.25, 0.20, False, 2),
        ("T4 Number of members M1", 0.02, 0.06, 0.80, False, 2),
        ("T4 Number of members M2", 0.01, 0.07, 0.82, False, 2),
        ("T4 Number of members M3", 0.02, 0.06, 0.80, False, 2),
        ("T4 Constant M1", 1.77, 2.55, 0.48, False, 2),
        ("T4 Constant M2", 4.13, 4.27, 0.33, False, 2),
        ("T4 Constant M3", 4.32, 2.99, 0.15, False, 2),
    )

    @staticmethod
    def _call(b, se, p, thr, df, decimals_se=2):
        return registry.BY_NAME["check_regression"].call(
            {"b": b, "se": se, "reported_p": p, "p_is_threshold": thr, "df": df,
             "decimals_b": 2, "decimals_se": decimals_se,
             "decimals_p": 3 if thr else 2,
             "source_quote": f"{b} ({se})", "source_locator": "regression table"})

    @classmethod
    def _accused(cls, df):
        out = set()
        for lbl, b, se, p, thr in cls.TABLE2:
            if cls._call(b, se, p, thr, df)["severity"] not in ("consistent", "indeterminate"):
                out.add(f"T2 {lbl}")
        for lbl, b, se, p, thr, dse in cls.TABLE34:
            if cls._call(b, se, p, thr, df, dse)["severity"] not in (
                    "consistent", "indeterminate"):
                out.add(lbl)
        return out

    def test_without_a_df_the_tool_renders_no_verdict_at_all(self):
        """So wiring it truthfully -- refusing to invent the df the paper does
        not print -- buys ZERO verdicts on this paper. The coverage win is not
        merely risky; on the evidence we have it does not exist."""
        for _lbl, b, se, p, thr in self.TABLE2:
            assert self._call(b, se, p, thr, None)["severity"] == "indeterminate"

    def test_the_invented_df_decides_who_is_accused(self):
        """THE MEASUREMENT THAT SETTLES IT. The same 63 rows, the same tool, two
        defensible-looking df conventions, and the accused set MOVES -- five of
        the seven rows either convention names are named by only one of them.

        A check whose accusation set is chosen by a parameter the paper never
        printed is not a check, and this is why `check_regression` stays
        unwired rather than wired with a default.

        THE FIXTURE CAUGHT ME FIRST, and it is worth recording: the divergence
        is NOT inside Table 2, where both conventions accuse exactly one row.
        Asserting it on Table 2 alone was a claim the fixture could not support,
        which is the shape of defect this repo calls a fixture that excludes the
        defect region."""
        normal = self._accused(10 ** 6)
        residual = self._accused(57)
        # Both conventions agree about the one row this paper's own arithmetic
        # makes unambiguous.
        assert "T2 Constant M1" in normal and "T2 Constant M1" in residual
        # And they disagree about everything else.
        assert normal != residual
        assert len(normal ^ residual) >= 4, sorted(normal ^ residual)
        # The rows only ONE convention accuses are honest rows the other reads
        # as consistent. Each is a false accusation waiting on a coin flip.
        assert normal - residual, sorted(normal)
        assert residual - normal, sorted(residual)

    def test_the_accused_row_is_not_a_conversion_artefact(self, account):
        """The one row both conventions name is read off the account, not
        retyped into this test: `-4.51 (1.50)` against a printed `< .001` in
        Table 2. If a later reading changes any of the three, the arithmetic
        above is about a paper we are no longer reading."""
        by_id = {v["id"]: v for v in account["values"]}
        assert by_id["val:t2:r9:c1:0:coefficient"]["printed"] == "-4.51"
        assert by_id["val:t2:r9:c1:1:se"]["printed"] == "1.50"
        assert by_id["val:t2:r9:c2:0:p_value"]["printed"] == "< .001"
        # And the account says it is the intercept, which is the row label the
        # paper printed (`Constant`).
        assert by_id["val:t2:r9:c1:0:coefficient"]["binding"] == "intercept"

    def test_the_conservative_direction_is_accused_by_one_argument_we_choose(self):
        """CORRECTED 2026-09-13, AND THE CORRECTION IS THE POINT. This test was
        called `test_the_tool_accuses_the_conservative_direction` and its
        docstring said `check_regression` "computes the direction and does not
        use it". THAT IS FALSE ABOUT THE TOOL. It delegates its p comparison to
        `ttest._p_matches`, which is directional by DEFAULT and documents it at
        length: `p_is_threshold=None` and `True` both enforce the interval only
        in the over-claim direction, and only `False` -- "pass `False` only
        having checked that the paper printed an exact value" -- tests both
        sides. The assertion below passed the whole time because `_call`
        hard-codes `False`.

        So this is a hazard of ONE ARGUMENT WE CHOOSE, not a property of the
        tool -- and the hazard is real, because the natural wiring reads that
        argument off the printed literal (`p_is_threshold =
        printed.startswith("<")`), which hands `False` to every plain `.01`.
        `8.57 (3.03)` against a printed `.01` recomputes to .0047: the paper
        printed a p LARGER than its own numbers give, and `False` calls that
        conservative reporting `suspicious`.

        BOTH BRANCHES ARE ASSERTED so neither half can rot: the `False` branch
        pins the hazard, the `None` branch pins the fix."""
        hazard = self._call(8.57, 3.03, 0.01, False, 10 ** 6)
        assert hazard["grace"]["direction"] == 1, "this is the under-claiming direction"
        assert hazard["severity"] == "suspicious"
        # THE SAME CELL, THE SAME df, THE SAFE ARGUMENT. `None` means "we have
        # not established that this p is exact", which is the truth about every
        # p a table prints, and it clears the row.
        safe = registry.BY_NAME["check_regression"].call(
            {"b": 8.57, "se": 3.03, "reported_p": 0.01, "p_is_threshold": None,
             "df": 10 ** 6, "decimals_b": 2, "decimals_se": 2, "decimals_p": 2,
             "source_quote": "8.57 (3.03)", "source_locator": "regression table"})
        assert safe["severity"] == "consistent"
        # The sibling states the rule explicitly, read from the registry rather
        # than restated, so a repair on one side cannot leave this asserting the
        # other.
        # Since 1.86.0 the rule is relation-dependent: the under-claim is
        # flagged only for a p the paper printed EXACT, and `None` gives
        # bound-shaped values like this `.01` the bound reading.
        assumptions = " ".join(registry.BY_NAME["recalc_stat_to_p"].assumptions).lower()
        assert "only when the p was printed exact" in assumptions

    def test_the_se_premise_is_typed_three_ways_in_one_account(self, account):
        """The instability, pinned. Three regression tables, one column band, and
        the dispersion typed three different ways -- so the population of any
        wiring keyed on the statistic name is a coin flip. This is a fact about
        the READING, so it is asserted as an inequality rather than a target: if
        a later reading makes all three agree, this test should be revisited
        rather than silently satisfied."""
        typed: dict[str, set] = {}
        for v in account["values"]:
            loc = v.get("location") or {}
            if loc.get("kind") != "table_cell":
                continue
            if loc.get("table_id") not in ("table:2", "table:3", "table:4"):
                continue
            if v.get("statistic") in ("sd", "se", "sem", "dispersion_unstated"):
                typed.setdefault(loc["table_id"], set()).add(v["statistic"])
        bands = {v["location"]["col_label"] for v in account["values"]
                 if (v.get("location") or {}).get("table_id") in ("table:2", "table:3", "table:4")
                 and (v.get("location") or {}).get("col") == 1}
        assert len(bands) == 1, f"the three tables share one column band: {bands}"
        assert typed == {"table:2": {"se"}, "table:3": {"sd"},
                         "table:4": {"dispersion_unstated"}}, typed
