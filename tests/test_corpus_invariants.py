"""Properties that must hold over the REAL registers, not over fixtures.

WHY THIS FILE EXISTS. Hand-built fixtures passed while real data failed, three
separate times on 2026-08-20:

  * a table fix went into one of three grid readers and measured ZERO on the
    corpus, because the affected papers all arrive by a different reader;
  * a claimed `estimate_ci` 74 -> 0 was measured before a later change and was
    still 74 in the code that shipped;
  * `_PROSE_NUM` required a digit first, so `P = .0525` registered as **525.0**
    and `P < .001` as **1.0** -- a p-value the paper called highly significant,
    recorded as the least significant value possible. Every unit fixture used a
    leading zero, so every unit test passed.

That last one was found by the invariant below, minutes after it was written.
Fixtures test what I imagined; these test what exists.

The numbers are PINNED AT WHAT WAS MEASURED, not at what would be nice. A
ratchet may be lowered when something is fixed; raising one to green a red suite
defeats the file.
"""

import json
import os
import pathlib

import pytest

#: The eleven-paper corpus lives OUTSIDE this repo, in the sibling papers
#: checkout. Resolution order: `METASCIENCE_PAPERS_ROOT` (the documented
#: override), then the sibling directory beside this repo, then the WSL
#: path this file was first written against. Until 2026-09-02 only the
#: last existed here, so on every other machine all six tests skipped and
#: the ratchets guarded nothing.
_PAPERS_ROOT_ENV = "METASCIENCE_PAPERS_ROOT"
_PAPERS_ROOT_CANDIDATES = (
    pathlib.Path(os.environ[_PAPERS_ROOT_ENV]) if os.environ.get(_PAPERS_ROOT_ENV) else None,
    pathlib.Path(__file__).resolve().parents[2] / "agent_for_forensic_metascience_papers",
    pathlib.Path("/mnt/c/Users/gregs/Dropbox/agent_for_forensic_metascience_papers"),
)
_CORPUS_REL = pathlib.Path("cerebrolysin_papers") / "prioritized_cerebrolysin_papers"
CORPUS = next((r / _CORPUS_REL for r in _PAPERS_ROOT_CANDIDATES
               if r is not None and (r / _CORPUS_REL).is_dir()),
              _PAPERS_ROOT_CANDIDATES[-1] / _CORPUS_REL)


def _registers():
    if not CORPUS.is_dir():
        pytest.skip(f"the eleven-paper corpus is not on this machine -- set "
                    f"{_PAPERS_ROOT_ENV} to the papers checkout that holds "
                    f"{_CORPUS_REL}")
    regs = [json.loads(f.read_text(encoding="utf-8"))
            for f in sorted(CORPUS.glob("*/forensic_review/value_register.json"))]
    if len(regs) < 5:
        pytest.skip("too few registers to measure a corpus property")
    return regs


def _own_values(reg):
    """The paper's own values. Supplement raw data is excluded: 85% of a
    register can be spreadsheet cells, and they would swamp every rate."""
    for g in reg.get("groups") or []:
        table = str(((g.get("anchor") or {}).get("table")) or "")
        if table.startswith("supp:") or "supp-" in table:
            continue
        for v in g.get("values") or []:
            yield g, v


class TestEveryValueIsAValue:
    def test_no_paper_own_value_lacks_a_number(self):
        """Was 826 of 2,829 before the prose parser -- and ALL of them
        body-anchored. The table path parsed everything; the prose path had
        never been finished."""
        missing = [(v.get("printed"), g.get("kind"))
                   for reg in _registers() for g, v in _own_values(reg)
                   if v.get("value") is None]
        assert not missing, f"{len(missing)} values carry no number: {missing[:5]}"


class TestNumbersLieInTheirOwnRange:
    """A value outside the range its role permits is OUR parse error. It cannot
    be a fact about the paper -- no journal prints a p-value of 525."""

    def test_every_p_value_is_a_probability(self):
        bad = [(v.get("printed"), v.get("value"))
               for reg in _registers() for _g, v in _own_values(reg)
               if str(v.get("role")) == "p" and v.get("value") is not None
               and not 0.0 <= v["value"] <= 1.0]
        assert not bad, f"{len(bad)} p-values outside [0,1]: {bad[:5]}"

    def test_every_percentage_is_a_percentage(self):
        bad = [(v.get("printed"), v.get("value"))
               for reg in _registers() for _g, v in _own_values(reg)
               if str(v.get("role")) == "percentage" and v.get("value") is not None
               and not 0.0 <= v["value"] <= 100.0]
        assert not bad, f"{len(bad)} percentages outside [0,100]: {bad[:5]}"

    def test_no_interval_is_inverted(self):
        """An upper bound below its lower bound is an interval no paper
        printed. It is how a separator gets read as a minus sign."""
        bad = []
        for reg in _registers():
            for g in reg.get("groups") or []:
                vals = {str(v.get("role")): v.get("value") for v in g.get("values") or []}
                lo, hi = vals.get("ci_low"), vals.get("ci_high")
                if lo is not None and hi is not None and hi < lo:
                    bad.append((g.get("quote"), lo, hi))
        assert not bad, f"{len(bad)} inverted intervals: {bad[:5]}"


class TestTheTypingIsNotObviouslyWrong:
    #: MEASURED 2026-08-20: 2 groups, both "Modified Rankin Scale maximum
    #: (range, 0-6 points)" -- an ordinal scale's min and max read as a
    #: confidence interval. Lower this when the range form is typed properly.
    MAX_IQR_TYPED_AS_CI = 2

    def test_an_interval_is_not_typed_as_a_ci_when_the_row_says_otherwise(self):
        """A confidence interval and an interquartile range are not the same
        quantity, and `check_estimate_ci` must never run on the second. Was 74
        on one paper before section bands reached the typer."""
        bad = []
        for reg in _registers():
            for g in reg.get("groups") or []:
                row = str(g.get("row_label") or "").lower()
                if str(g.get("kind")) == "estimate_ci" and any(
                        w in row for w in ("iqr", "median", "q1", "range")):
                    bad.append((reg.get("paper"), g.get("row_label")))
        assert len(bad) <= self.MAX_IQR_TYPED_AS_CI, (
            f"{len(bad)} intervals typed `estimate_ci` whose row label says "
            f"otherwise, above the pinned {self.MAX_IQR_TYPED_AS_CI}: {bad[:4]}")


class TestTheRegisterAccountsForItsCalls:
    #: MEASURED 2026-08-20 over the nine registers: **0 of 700**. Was 145 of
    #: 723 (20.1%). Zero is the only honest ceiling for a conservation law; see
    #: `test_call_conservation.TestTheRatchet` for what the residual was hiding.
    MAX_UNACCOUNTED_SHARE = 0.0

    def test_calls_do_not_vanish(self):
        calls = unacct = 0
        for reg in _registers():
            c = reg.get("calls") or {}
            calls += c.get("n_calls") or 0
            unacct += abs(c.get("n_unaccounted") or 0)
        if not calls:
            pytest.skip("no registers carry a call ledger yet")
        share = unacct / calls
        assert share <= self.MAX_UNACCOUNTED_SHARE, (
            f"{unacct} of {calls} calls ({share:.1%}) end in no recorded state")
