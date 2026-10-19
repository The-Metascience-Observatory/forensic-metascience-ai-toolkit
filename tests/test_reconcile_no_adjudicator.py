"""1.91.0: tool verdicts and filed findings reconciled when no adjudicator runs.

`deduplicate_by_statistic` collapses p-check rows about ONE printed statistic
(statcheck and recalc_stat_to_p both filing `t(94) = 1.64, p < .001`), keyed on
the statistic and never the quote; `parallel._unaccounted_record` is the
structured list of accusing tool results the final review does not account for.
"""

from metascience_agent import findings_v2 as fv2
from metascience_agent import parallel


def _row(fid, technique, outcome="problem", **kw):
    return {"finding_id": fid, "technique": technique, "outcome": outcome, **kw}


class TestDeduplicateByStatistic:
    def test_statcheck_and_recalc_on_one_statistic_merge(self):
        rows = [_row("a", "statcheck", title="t(94) = -1.64, p < .001 is inconsistent"),
                _row("b", "recalc_stat_to_p", computed_by="registry_tool",
                     inputs={"statistic": -1.64, "df": 94, "reported_p": 0.001})]
        kept, removed = fv2.deduplicate_by_statistic(rows)
        assert [r["finding_id"] for r in kept] == ["b"]  # the registry-tool row
        assert "Also reported by statcheck" in kept[0]["notes"]
        assert removed == [{"finding_id": "a", "kept": "b", "technique": "statcheck",
                            "outcome": "problem",
                            "title": "t(94) = -1.64, p < .001 is inconsistent"}]

    def test_a_shared_footnote_quote_never_merges_different_statistics(self):
        """MEASURED 2026-10-18 (10.1007--s40200-021-00832-0, grok 1.88): four
        recalc_anova rows shared the table footnote as their quote."""
        foot = "Values are mean ± SD; P values from one-way ANOVA."
        rows = [_row(str(i), "recalc_anova", quote=foot,
                     inputs={"means": means, "reported_p": p})
                for i, (means, p) in enumerate([([27.1, 28.3, 29.0], 0.18),
                                                ([9.1, 10.2, 11.5], 0.09),
                                                ([1510, 1490, 1530], 0.41),
                                                ([88.0, 91.2, 95.4], 0.02)])]
        kept, removed = fv2.deduplicate_by_statistic(rows)
        assert len(kept) == 4 and removed == []

    def test_a_problem_and_a_pass_on_one_statistic_both_stay(self):
        """A disagreement between two checks is evidence, not a duplicate."""
        rows = [_row("a", "statcheck", title="F(1, 40) = 4.10, p = .01"),
                _row("b", "recalc_stat_to_p", outcome="pass",
                     inputs={"statistic": 4.10, "df": 1, "df2": 40, "reported_p": 0.01})]
        kept, removed = fv2.deduplicate_by_statistic(rows)
        assert len(kept) == 2 and removed == []

    def test_different_p_on_the_same_statistic_value_does_not_merge(self):
        rows = [_row("a", "recalc_stat_to_p", inputs={"statistic": 2.1, "reported_p": 0.04}),
                _row("b", "recalc_stat_to_p", inputs={"statistic": 2.1, "reported_p": 0.03})]
        assert len(fv2.deduplicate_by_statistic(rows)[0]) == 2

    def test_rows_outside_the_p_family_are_untouched(self):
        rows = [_row("a", "grim_check", inputs={"mean": 3.5, "n": 30}),
                _row("b", "grim_check", inputs={"mean": 3.5, "n": 30}),
                _row("c", "not_computational", title="t(9) = 2.0, p = .07")]
        assert len(fv2.deduplicate_by_statistic(rows)[0]) == 3

    def test_the_sign_of_the_statistic_does_not_split_a_group(self):
        rows = [_row("a", "statcheck", title="t(20) = -2.50, p = .30"),
                _row("b", "recalc_stat_to_p", inputs={"statistic": 2.5, "reported_p": 0.3})]
        assert len(fv2.deduplicate_by_statistic(rows)[0]) == 1


def _call(seq, tool, args, severity):
    import json
    return {"seq": seq, "tool": f"mcp__forensic_metascience__{tool}", "tool_short": tool,
            "surface": "forensic_mcp", "validated": True, "input": args,
            "result": json.dumps({"severity": severity}), "result_truncated": False}


class TestUnaccountedRecord:
    LEDGER = [_call(1, "grim_check", {"mean": 3.53, "n": 30, "decimals": 2}, "impossible"),
              _call(2, "grim_check", {"mean": 4.10, "n": 30, "decimals": 2}, "suspicious"),
              _call(3, "grim_check", {"mean": 2.00, "n": 30, "decimals": 2}, "consistent")]

    def test_lists_unfiled_accusing_calls_with_their_arguments(self):
        rec = parallel._unaccounted_record([], self.LEDGER, None)
        assert rec["n"] == 2 and [i["seq"] for i in rec["items"]] == [1, 2]
        assert rec["items"][0]["input"] == {"mean": 3.53, "n": 30, "decimals": 2}

    def test_a_dismissed_call_is_accounted_for(self):
        dismissed = [{"tool": "grim_check", "input": {"mean": 4.10, "n": 30, "decimals": 2}}]
        rec = parallel._unaccounted_record([], self.LEDGER, dismissed)
        assert [i["seq"] for i in rec["items"]] == [1] and rec["n_dismissed"] == 1

    def test_a_filed_problem_row_accounts_for_its_call(self):
        filed = [{"technique": "grim_check", "outcome": "problem",
                  "inputs": {"mean": 3.53, "n": 30}}]
        assert [i["seq"] for i in parallel._unaccounted_record(filed, self.LEDGER, None)["items"]] == [2]

    def test_no_ledger_is_an_empty_record_not_an_error(self):
        assert parallel._unaccounted_record([], None, None) == {
            "n": 0, "n_dismissed": 0, "items": []}


def test_coverage_summary_carries_both_records(tmp_path):
    meta = {"unaccounted_tool_results": {"n": 1, "n_dismissed": 0, "items": [{"seq": 4}]},
            "deduplicated": [{"finding_id": "a", "kept": "b"}]}
    out = parallel._build_coverage_summary(
        {"paper_path": str(tmp_path), "run_meta": meta}, {}, {"findings": []})
    assert out["unaccounted_tool_results"]["n"] == 1
    assert out["deduplicated"] == [{"finding_id": "a", "kept": "b"}]
