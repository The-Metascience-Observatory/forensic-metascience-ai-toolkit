"""A model as second reader of the account: what the pass is handed, what it
may return, and that its output is marked as a reading throughout."""
from metascience_agent.scaffold import review as RV


def _account(n=30):
    return {"values": [{"id": f"val:{i:03d}", "printed": str(i), "statistic": "n", "variable_id": "var:x",
                        "coordinate": {}, "location": {"kind": "prose"}, "quote": f"n = {i}"} for i in range(n)]}


class TestTheSample:
    def test_is_fixed_and_carries_what_a_reader_needs(self):
        a = _account()
        s1, s2 = RV.sample_values(a), RV.sample_values(a)
        assert s1 == s2 and len(s1) == RV.SAMPLE_SIZE
        assert set(s1[0]) >= {"value_id", "printed", "statistic", "variable", "quote_or_cell", "where"}
        assert len(RV.sample_values(_account(5))) == 5, "a small account is checked whole"


class TestThePrompt:
    def test_forbids_coverage_claims_and_carries_the_three_inputs(self):
        p = RV.review_prompt("# account", "paper text", RV.sample_values(_account(3)))
        assert "do NOT compute coverage" in p and "SAMPLED VALUES TO CHECK" in p
        assert "THE ACCOUNT (rendered;" in p and "THE PAPER" in p and "val:001" in p

    def test_long_inputs_are_clipped_and_say_so(self):
        p = RV.review_prompt("x" * (RV.ACCOUNT_CHARS + 10), "y" * (RV.PAPER_CHARS + 10), [])
        assert "account clipped at" in p and "paper clipped at" in p

    def test_the_compare_prompt_asks_which_reading_the_paper_supports(self):
        p = RV.compare_prompt("A", "B", "paper")
        assert "ACCOUNT A" in p and "ACCOUNT B" in p and "which reading the paper supports" in p


class TestTheReviewerIsServedEveryEvidenceSection:
    """MEASURED 2026-09-07 on the accounts on disk: ajcp.70049's rendered
    account is 160,309 characters against a 160,000-character cap, so the
    reviewer was handed everything except the tail of the last evidence
    section, and the clip is invisible in the review's output. Section 0 is
    derived and the reviewer is told not to audit it, so it is not served; the
    cap rises above the largest account we hold (230,093 characters)."""

    def _rendered(self) -> str:
        from metascience_agent.scaffold import bind, render

        from tests.test_scaffold import P1, P2, P3, _doc
        return render.render(bind.assemble(_doc(), P1, P2, P3))

    def test_the_account_reaches_the_reviewer_down_to_its_last_line(self):
        md = self._rendered()
        p = RV.review_prompt(md, "paper", [])
        last = md.rstrip().splitlines()[-1]
        assert last.strip(), "the fixture account must end in a real line"
        assert last in p
        assert "account clipped at" not in p

    def test_only_section_0_is_dropped(self):
        md = self._rendered()
        served = RV.without_headline(md)
        assert "## 0. Headline coverage" in md and "## 0. Headline coverage" not in served
        for line in md.splitlines():
            if line.startswith("## ") and not line.startswith("## 0. "):
                assert line in served, line
        assert RV.without_headline("# no headline here\n\n## 1. Structure\n") \
            == "# no headline here\n\n## 1. Structure\n"

    def test_both_compared_accounts_lose_section_0_too(self):
        md = self._rendered()
        p = RV.compare_prompt(md, md, "paper")
        assert "## 0. Headline coverage" not in p and "## How to verify this account" in p


class TestTableRenders:
    def test_the_sampled_tables_renders_and_cells_are_handed_over(self):
        acct = {"values": [{"id": "val:t1", "printed": "38", "statistic": "count", "location": {"kind": "table_cell", "table_id": "table:1"}, "quote": "38 (59%)"}],
                "document": {"tables": [{"id": "table:1", "label": "Table 1", "caption": "c",
                                         "reconstruction": {"png": "/x/table_1.png"},
                                         "cells": [{"row_label": "r", "col_label": "c", "raw": "38 (59%)"}]},
                                        {"id": "table:2", "label": "Table 2", "cells": []}]}}
        sample = RV.sample_values(acct)
        renders = RV.table_renders(acct, sample)
        assert [r["table_id"] for r in renders] == ["table:1"] and renders[0]["image"] == "/x/table_1.png"
        p = RV.review_prompt("# acct", "paper", sample, renders)
        assert "TABLE RENDERS" in p and "/x/table_1.png" in p and "open its rendered image with the Read tool" in p


class TestTheSchemas:
    def test_verdicts_and_severities_are_closed(self):
        import jsonschema
        jsonschema.Draft202012Validator.check_schema(RV.REVIEW_SCHEMA)
        jsonschema.Draft202012Validator.check_schema(RV.COMPARE_SCHEMA)
        good = {"overall": "fine", "notes": [{"where": "table:1", "what": "x", "why": "y", "severity": "needs_check",
                                             "suggested_check": None}],
                "spot_checks": [{"value_id": "val:001", "verdict": "supported", "evidence": "n = 1", "note": None}],
                "unstable_readings": []}
        jsonschema.Draft202012Validator(RV.REVIEW_SCHEMA).validate(good)
        bad = dict(good, spot_checks=[{"value_id": "v", "verdict": "looks fine", "evidence": "", "note": None}])
        assert list(jsonschema.Draft202012Validator(RV.REVIEW_SCHEMA).iter_errors(bad))


class TestItIsMarkedAsAReading:
    def test_run_review_stamps_the_basis_and_counts_verdicts(self, monkeypatch):
        def fake_run_pass(name, prompt, out_dir, **kw):
            assert kw.get("tools") == "Read" and kw.get("schema") is RV.REVIEW_SCHEMA
            return {"data": {"overall": "ok", "notes": [], "unstable_readings": [],
                             "spot_checks": [{"value_id": "val:000", "verdict": "supported", "evidence": "n = 0", "note": None},
                                             {"value_id": "val:001", "verdict": "not_found", "evidence": "-", "note": None}]},
                    "problems": [], "meta": {"cost_usd": 0.5, "elapsed_s": 10}}
        monkeypatch.setattr(RV._passes, "run_pass", fake_run_pass)
        rv = RV.run_review(_account(2), "# acct", "paper", "/tmp/x", model="sonnet")
        assert rv["basis"].startswith("model_reading") and rv["spot_checks_by_verdict"] == {"supported": 1, "not_found": 1}
        assert rv["n_sampled"] == 2 and rv["cost_usd"] == 0.5

    def test_the_rendered_section_names_it_a_reading(self):
        from metascience_agent.scaffold import render as R
        assert "readings to verify, not computed facts" in R.render.__code__.co_consts.__repr__() or \
               "readings to verify, not computed facts" in open(R.__file__, encoding="utf-8").read()


#: THE ADJUDICATION FIXTURE, shared by the two classes below. `Values are means.`
#: is printed twice on purpose: a quote that occurs twice cannot say which
#: occurrence decided anything, and the uniqueness gate is measured on it.
_TEXT = ("Results in Tables 2, 3, 4 are shown as coefficients. "
         "The parenthetical is the standard error. "
         "Anxiety was scored on the scale defined in the Methods. "
         "Values are means. Values are means.")


def _cell(vid, table, stat, printed, numeric, group=None):
    return {"id": vid, "printed": printed, "numeric": numeric, "statistic": stat, "variable_id": None,
            "coordinate": {"study_id": "study:a", "group_id": group, "phase_id": None},
            "location": {"kind": "table_cell", "table_id": table, "row": 1, "col": 1}}


def _acct():
    return {"document": {"tables": [{"id": "table:2", "label": "Table 2"},
                                    {"id": "table:3", "label": "Table 3"}]},
            "studies": [{"id": "study:a", "phases": [],
                         "groups": [{"id": "grp:vet", "n_printed": "64"},
                                    {"id": "grp:nonvet", "n_printed": "8"}]}],
            "phases": [], "variables": [{"id": "var:x", "levels": [{"id": "lvl:1"}],
                                         "bounds": {"source": "definitional"}}],
            "values": [_cell("val:1", "table:2", "sd", "0.60", 0.6),
                       _cell("val:2", "table:2", "count", "40", 40),
                       _cell("val:3", "table:2", "coefficient", "1.20", 1.2),
                       _cell("val:4", "table:2", "sd", "0.31", 0.31, group="grp:vet"),
                       _cell("val:other", "table:3", "sd", "0.10", 0.1),
                       {"id": "val:prose", "printed": "5.23", "numeric": 5.23, "statistic": "sd",
                        "variable_id": None, "location": {"kind": "prose"},
                        "coordinate": {"study_id": "study:a", "group_id": None, "phase_id": None}}]}


def _adj(**over):
    d = {"field_class": "statistic_kind", "item": "Table 2 parenthetical", "reading_a": "sd", "reading_b": "se",
         "paper_supports": "b", "evidence": "the Methods say SE",
         "evidence_quote": "The parenthetical is the standard error.",
         "evidence_anchor": {"kind": "table_header", "table_id": "table:2"},
         "target_account": "a", "target_ids": ["val:1"], "correction": {"field": "statistic", "to": "se"}}
    d.update(over)
    return {"overall": "", "model": "opus", "version": RV.REVIEW_VERSION, "disagreements": [d]}


def _val(account, vid):
    return next(v for v in account["values"] if v["id"] == vid)


def _indexable():
    """The fixture account with the labels an index line prints. Deliberately
    built on `_acct()`: the ids the index must publish are the ids the gates in
    `apply_adjudication` match on, and a second fixture would let the two drift."""
    a = _acct()
    a["values"][0]["location"].update({"row_label": "Inclusive leadership", "col_label": "b (SE)"})
    a["comparisons"] = [{"id": "cmp:t4-comm", "quote": "Communication predicted adherence, b = 0.31."}]
    a["studies"][0].update({"label": "Wave 1 panel", "design_type": "longitudinal_panel",
                            "phases": [{"id": "phase:w1", "label": "Wave 1"}]})
    a["studies"][0]["groups"][0]["label"] = "Veterans"
    a["variables"][0].update({"name": "Anxiety", "kind": "integer_score"})
    return a


class TestTheIdIndex:
    """The index exists because the rendered account is the wrong place to copy an
    id from: `render._short` prints `t4-comm` for `cmp:t4-comm`, and on the first
    real application every cited id was a shortened one, so nothing applied."""

    def test_it_lists_a_value_with_its_full_id_and_where_it_was_printed(self):
        idx = RV.id_index(_indexable())
        line = next(l for l in idx.splitlines() if l.startswith("val:1 |"))
        for part in ("table:2", "Inclusive leadership", "b (SE)", "0.60", "sd"):
            assert part in line, (part, line)

    def test_it_publishes_the_ids_a_correction_must_name(self):
        idx = RV.id_index(_indexable())
        assert "cmp:t4-comm | Communication predicted adherence" in idx, "the full comparison id, not `t4-comm`"
        assert "study:a | Wave 1 panel | longitudinal_panel" in idx
        assert "study:a/grp:vet | Veterans" in idx and "study:a/phase:w1 | Wave 1" in idx
        assert "var:x | Anxiety | integer_score | definitional" in idx

    def test_values_are_grouped_by_table_and_prose_comes_last(self):
        idx = RV.id_index(_indexable())
        assert idx.index("val:1 |") < idx.index("val:other |") < idx.index("val:prose |")

    def test_clipping_drops_whole_lines_and_says_what_is_missing(self):
        idx = RV.id_index(_indexable(), limit=600)
        assert "more value ids not listed" in idx and "leave" in idx
        assert not any(l.startswith("val:") and l.count(" | ") != 6 for l in idx.splitlines()), \
            "a line clipped mid-id reads exactly like a whole one"


class TestTheIdIndexReachesThePrompt:
    def test_the_fences_and_the_copy_exactly_instruction_are_served_together(self):
        p = RV.compare_prompt("A", "B", "paper", _indexable(), _indexable())
        assert "ID INDEX A" in p and "ID INDEX B" in p
        assert "COPY EVERY `target_ids` ENTRY FROM THE ID INDEX" in p
        assert "MUST LIST EVERY VALUE ID IN THAT COLUMN" in p and "MACHINE FORM" in p
        assert "bounds.source" in p, "the allowed fields are named, so `to` can be checked against them"
        assert "val:1 | table:2 |" in p and "cmp:t4-comm |" in p

    def test_without_accounts_nothing_is_added(self):
        """An instruction to copy from a fence that is not served would be a false
        instruction, so the un-indexed prompt is left exactly as it was."""
        p = RV.compare_prompt("A", "B", "paper")
        assert "ID INDEX" not in p and "COPY EVERY" not in p

    def test_run_compare_passes_the_accounts_through(self, monkeypatch):
        seen = {}

        def fake_run_pass(name, prompt, out_dir, **kw):
            seen["prompt"] = prompt
            return {"data": {"overall": "", "disagreements": []}, "problems": [], "meta": {"cost_usd": 0.1}}
        monkeypatch.setattr(RV._passes, "run_pass", fake_run_pass)
        RV.run_compare("A", "B", "paper", "/tmp/x", model="opus",
                       account_a=_indexable(), account_b=_indexable())
        assert "ID INDEX A" in seen["prompt"] and "val:1 | table:2 |" in seen["prompt"]


class TestApplyAdjudication:
    def test_a_decided_located_correction_is_applied_and_kept_reversible(self):
        """END TO END: `sd` -> `se` is a NARROWING (out of the checkable set), on
        a table header anchor of the value's own table, with a quote that occurs
        exactly once. Everything a reader needs to reverse it is on the record."""
        a = _acct()
        s = RV.apply_adjudication(a, _adj(), _TEXT, side="a")
        v = _val(a, "val:1")
        assert v["statistic"] == "se" and v["printed"] == "0.60" and v["numeric"] == 0.6
        assert v["statistic_basis"] == "adjudicated", "the third premise tier is carried, not hidden"
        rec = v["adjudications"][0]
        assert rec["from"] == "sd" and rec["to"] == "se" and rec["adjudicated_by"] == "model_review"
        assert rec["evidence_kind"] == "verbatim" and rec["evidence_anchor"]["kind"] == "table_header"
        assert rec["reading_a"] == "sd" and rec["reading_b"] == "se" and rec["paper_supports"] == "b"
        assert rec["presentation"] == "a" and rec["adjudicator"] == {"model": "opus", "version": RV.REVIEW_VERSION}
        assert s["n_applied"] == 1 and s["n_skipped"] == 0
        assert s["applied"][0]["anchor_kind"] == "table_header"

    def test_the_gates_each_skip_by_name(self):
        for over, why in [
            ({"paper_supports": "both_plausible"}, "does not decide"),
            ({"target_account": "b"}, "targets account"),
            ({"correction": None}, "no machine-form correction"),
            ({"correction": {"field": "statistic", "to": "standard_error"}}, "not in the vocabulary"),
            ({"correction": {"field": "variable_id", "to": "var:coined"}}, "not in the vocabulary or declared ids"),
            ({"evidence_quote": "A sentence the paper never printed."}, "not located"),
            ({"target_ids": ["val:99"]}, "no target id exists"),
            ({"evidence_anchor": {"kind": "hunch", "table_id": None}}, "no evidence anchor of a known kind"),
        ]:
            a = _acct()
            s = RV.apply_adjudication(a, _adj(**over), _TEXT, side="a")
            assert s["n_applied"] == 0 and _val(a, "val:1")["statistic"] == "sd", over
            assert any(why in sk["why"] for sk in s["skipped"]), (over, s["skipped"])

    def test_a_cell_decides_without_a_quote_and_is_marked_unlocated(self):
        a = _acct()
        s = RV.apply_adjudication(a, _adj(evidence_quote=None, evidence="the column header reads b (SE)",
                                               evidence_anchor={"kind": "table_footnote", "table_id": "table:2"}),
                                  _TEXT, side="a")
        assert s["n_applied"] == 1 and _val(a, "val:1")["adjudications"][0]["evidence_kind"] == "unlocated"

    def test_a_printed_number_can_never_be_a_correction_target(self):
        assert "printed" not in RV.CORRECTABLE_FIELDS and "numeric" not in RV.CORRECTABLE_FIELDS
        assert "quote" not in RV.CORRECTABLE_FIELDS


class TestTheAdjudicationGates:
    """One test per gate. The gates exist because the adjudicator is the SAME
    model that wrote both accounts: what makes a reading safe to apply is the
    kind of evidence behind it and whether that evidence reaches the record, not
    the model's confidence. A correction that supplies a premise supplies a
    denominator, and a wrong denominator is the route to accusing an honest paper."""

    def test_g1_every_disagreement_carries_an_anchor_and_the_prompt_asks_for_one(self):
        import jsonschema
        jsonschema.Draft202012Validator.check_schema(RV.COMPARE_SCHEMA)
        d = _adj()["disagreements"][0]
        doc = {"overall": "", "disagreements": [d]}
        jsonschema.Draft202012Validator(RV.COMPARE_SCHEMA).validate(doc)
        bare = {k: v for k, v in d.items() if k != "evidence_anchor"}
        assert list(jsonschema.Draft202012Validator(RV.COMPARE_SCHEMA).iter_errors(
            {"overall": "", "disagreements": [bare]})), "a disagreement without an anchor is not valid"
        p = RV.compare_prompt("A", "B", "paper")
        assert "RELIABILITY, not accuracy" in p and "`neither`" in p and "`undecidable`" in p
        assert "evidence_anchor" in p and "recomputation" in p

    def test_g2_the_evidence_must_reach_the_record_it_corrects(self):
        for over in [
            # a header of ANOTHER table
            {"evidence_anchor": {"kind": "table_header", "table_id": "table:3"}},
            # a sentence that names no table at all
            {"evidence_anchor": {"kind": "body_sentence_naming_table", "table_id": None}},
            # a table anchor against a value the account read from prose
            {"target_ids": ["val:prose"]},
        ]:
            a = _acct()
            s = RV.apply_adjudication(a, _adj(**over), _TEXT, side="a")
            assert s["n_applied"] == 0, over
            assert any("does not cover the target" in sk["why"] for sk in s["skipped"]), (over, s["skipped"])
        # and a sentence that DOES name the table reaches it, plural form included
        a = _acct()
        s = RV.apply_adjudication(a, _adj(
            evidence_quote="Results in Tables 2, 3, 4 are shown as coefficients.",
            evidence_anchor={"kind": "body_sentence_naming_table", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 1 and _val(a, "val:1")["statistic"] == "se"

    def test_g3_a_quote_must_be_long_enough_and_occur_exactly_once(self):
        from metascience_agent import quotes as Q
        for quote in ("Values are means.",           # verbatim, and printed twice
                      "means."):                     # under _MIN_FRAGMENT
            a = _acct()
            s = RV.apply_adjudication(a, _adj(evidence_quote=quote), _TEXT, side="a")
            assert s["n_applied"] == 0 and any("not unique/too short" in sk["why"] for sk in s["skipped"]), quote
        assert len("means.") < Q._MIN_FRAGMENT <= len("The parenthetical is the standard error.")

    def test_g4_a_recomputation_is_recorded_and_never_applied(self):
        a = _acct()
        s = RV.apply_adjudication(a, _adj(evidence_quote=None, evidence="0.53/0.60 = 0.88 -> p = .38",
                                               evidence_anchor={"kind": "recomputation", "table_id": None}),
                                  _TEXT, side="a")
        assert s["n_applied"] == 0 and _val(a, "val:1")["statistic"] == "sd"
        assert any("recomputation is model arithmetic" in sk["why"] for sk in s["skipped"])

    def test_g5_a_premise_may_be_supplied_only_by_the_table_that_printed_it(self):
        supply = {"correction": {"field": "coordinate.group_id", "to": "grp:vet"},
                  "evidence_quote": "Results in Tables 2, 3, 4 are shown as coefficients."}
        a = _acct()
        s = RV.apply_adjudication(a, _adj(**supply, evidence_anchor={
            "kind": "body_sentence_naming_table", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 0 and _val(a, "val:1")["coordinate"]["group_id"] is None
        assert any("supplies a premise from prose" in sk["why"] for sk in s["skipped"])
        # the same correction from the table's own header is a reading of the table
        a = _acct()
        s = RV.apply_adjudication(a, _adj(**supply), _TEXT, side="a")
        assert s["n_applied"] == 1 and _val(a, "val:1")["coordinate"]["group_id"] == "grp:vet"
        # and REPLACING a group the account already committed to is not a supply
        a = _acct()
        s = RV.apply_adjudication(a, _adj(
            target_ids=["val:4"], correction={"field": "coordinate.group_id", "to": "grp:nonvet"},
            evidence_quote="Results in Tables 2, 3, 4 are shown as coefficients.",
            evidence_anchor={"kind": "body_sentence_naming_table", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 1 and _val(a, "val:4")["coordinate"]["group_id"] == "grp:nonvet"

    def test_g5_bounds_may_only_lose_authority(self):
        a = _acct()
        s = RV.apply_adjudication(a, _adj(
            target_ids=["var:x"], correction={"field": "bounds.source", "to": "stated"},
            evidence_quote="Anxiety was scored on the scale defined in the Methods.",
            evidence_anchor={"kind": "methods_definition", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 0 and a["variables"][0]["bounds"]["source"] == "definitional"
        assert any("promotion of bounds to stated is refused" in sk["why"] for sk in s["skipped"])
        a = _acct()
        s = RV.apply_adjudication(a, _adj(
            target_ids=["var:x"], correction={"field": "bounds.source", "to": "not_stated"},
            evidence_quote="Anxiety was scored on the scale defined in the Methods.",
            evidence_anchor={"kind": "methods_definition", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 1 and a["variables"][0]["bounds"]["source"] == "not_stated"

    def test_g5_a_kind_that_makes_a_value_checkable_needs_a_structural_anchor(self):
        into = {"target_ids": ["val:3"], "correction": {"field": "statistic", "to": "mean"},
                "evidence_quote": "Results in Tables 2, 3, 4 are shown as coefficients."}
        a = _acct()
        s = RV.apply_adjudication(a, _adj(**into, evidence_anchor={
            "kind": "body_sentence_naming_table", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 0 and _val(a, "val:3")["statistic"] == "coefficient"
        assert any("needs a structural or Methods anchor" in sk["why"] for sk in s["skipped"])
        a = _acct()
        s = RV.apply_adjudication(a, _adj(**into), _TEXT, side="a")
        assert s["n_applied"] == 1 and _val(a, "val:3")["statistic"] == "mean"
        # out of the checkable set is narrowing, and a body sentence carries it
        a = _acct()
        s = RV.apply_adjudication(a, _adj(
            target_ids=["val:1"], correction={"field": "statistic", "to": "other"},
            evidence_quote="Results in Tables 2, 3, 4 are shown as coefficients.",
            evidence_anchor={"kind": "body_sentence_naming_table", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 1 and _val(a, "val:1")["statistic"] == "other"

    def test_g6_one_record_per_non_structural_evidence_item(self):
        a = _acct()
        s = RV.apply_adjudication(a, _adj(
            target_ids=["val:1", "val:3"], correction={"field": "statistic", "to": "se"},
            evidence_quote="Results in Tables 2, 3, 4 are shown as coefficients.",
            evidence_anchor={"kind": "body_sentence_naming_table", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 1 and _val(a, "val:3")["statistic"] == "coefficient"
        assert any("one record per non-structural evidence item" in sk["why"] for sk in s["skipped"])
        # a column header governs its whole column, so a structural anchor may correct many
        a = _acct()
        s = RV.apply_adjudication(a, _adj(target_ids=["val:1", "val:3"]), _TEXT, side="a")
        assert s["n_applied"] == 2 and _val(a, "val:3")["statistic"] == "se"

    def test_g7_a_field_is_adjudicated_once_and_the_record_is_append_only(self):
        a = _acct()
        RV.apply_adjudication(a, _adj(), _TEXT, side="a")
        s = RV.apply_adjudication(a, _adj(correction={"field": "statistic", "to": "other"}), _TEXT, side="a")
        v = _val(a, "val:1")
        assert s["n_applied"] == 0 and v["statistic"] == "se" and len(v["adjudications"]) == 1
        assert any("field already adjudicated; append-only" in sk["why"] for sk in s["skipped"])

    def test_g8_an_adjudicated_kind_is_a_third_premise_tier(self):
        from metascience_agent.scaffold import reconstruct as RC
        assert "adjudicated" in RC.STATISTIC_BASES
        assert "adjudicated" in RC.RECON_SCHEMA["properties"]["cells"]["items"]["properties"][
            "numbers"]["items"]["properties"]["statistic_basis"]["enum"]
        assert "suspicious" in RV.apply_adjudication.__doc__ and "impossible" in RV.apply_adjudication.__doc__
        a = _acct()
        RV.apply_adjudication(a, _adj(), _TEXT, side="a")
        assert _val(a, "val:1")["statistic_basis"] == "adjudicated"

    def test_g9_a_count_may_not_exceed_the_group_it_is_moved_into(self):
        move = {"target_ids": ["val:2"], "evidence_quote": None}
        a = _acct()
        s = RV.apply_adjudication(a, _adj(**move, correction={"field": "coordinate.group_id", "to": "grp:nonvet"}),
                                  _TEXT, side="a")
        assert s["n_applied"] == 0 and _val(a, "val:2")["coordinate"]["group_id"] is None
        assert any("count exceeds the target group's printed n" in sk["why"] for sk in s["skipped"])
        a = _acct()
        s = RV.apply_adjudication(a, _adj(**move, correction={"field": "coordinate.group_id", "to": "grp:vet"}),
                                  _TEXT, side="a")
        assert s["n_applied"] == 1 and _val(a, "val:2")["coordinate"]["group_id"] == "grp:vet"

    def test_g11_a_header_may_not_overrule_a_text_derived_kind(self):
        """THE MEASURED CASE, ajcp.70049 Table 4 (2026-09-07). The parenthetical
        of a `Coefficient | M (SD)` column was typed `se` on `citing_text` -- the
        Results say the tables show coefficients, and an earlier adjudicator had
        confirmed SE by recomputing the Wald ratio against the printed p. A later
        adjudicator moved 21 values to `sd` on the header `M (SD)`, while writing
        in its own evidence that these are "almost certainly model standard
        errors". Faithful to the print, and an SE handed to every check that
        reads the kind. The header and the text disagree; the account says so."""
        a = _acct()
        v = _val(a, "val:1")
        v["statistic"], v["statistic_basis"] = "se", "citing_text"
        s = RV.apply_adjudication(a, _adj(
            reading_a="se", reading_b="sd", correction={"field": "statistic", "to": "sd"},
            evidence="the header reads M (SD) and the footnote says SD, standard deviation",
            evidence_quote=None,
            evidence_anchor={"kind": "table_header", "table_id": "table:2"}), _TEXT, side="a")
        assert s["n_applied"] == 0
        assert v["statistic"] == "se" and v["statistic_basis"] == "citing_text", "neither is touched"
        assert "adjudications" not in v, "a skip is not a correction and leaves no correction record"
        assert v["statistic_disputed"] is True
        assert v["kind_conflict"]["printed_kind"] == "sd" and v["kind_conflict"]["text_kind"] == "se"
        assert "M (SD)" in v["kind_conflict"]["header_evidence"]
        assert v["kind_conflict"]["item"] == "Table 2 parenthetical"
        assert any("header cannot overrule a text-derived kind" in sk["why"] for sk in s["skipped"])

    def test_g11_a_text_anchor_may_still_correct_a_text_derived_kind(self):
        """The exemption: evidence of the same kind -- a located sentence naming
        the table, or the Methods definition -- answers a text-derived reading,
        and the correction applies as before."""
        a = _acct()
        v = _val(a, "val:1")
        v["statistic_basis"] = "citing_text"
        s = RV.apply_adjudication(a, _adj(
            evidence_quote="Results in Tables 2, 3, 4 are shown as coefficients.",
            evidence_anchor={"kind": "body_sentence_naming_table", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 1 and v["statistic"] == "se"
        assert v["statistic_basis"] == "adjudicated" and "kind_conflict" not in v
        # The measured case's OWN direction (`se` -> `sd`, INTO the checkable
        # set) cannot reach this exemption on a table cell, and G11 is not what
        # holds it: the older gate wants a structural or Methods anchor, and
        # `_anchor_covers` refuses a Methods anchor for a cell. Asserted so the
        # two gates are not read as one.
        a = _acct()
        _val(a, "val:1").update({"statistic": "se", "statistic_basis": "citing_text"})
        s = RV.apply_adjudication(a, _adj(
            correction={"field": "statistic", "to": "sd"},
            evidence_quote="Results in Tables 2, 3, 4 are shown as coefficients.",
            evidence_anchor={"kind": "body_sentence_naming_table", "table_id": None}), _TEXT, side="a")
        assert s["n_applied"] == 0
        assert any("needs a structural or Methods anchor" in sk["why"] for sk in s["skipped"])

    def test_g11_a_header_derived_kind_is_still_corrected_by_a_header(self):
        """The reading the gate does NOT touch: nothing in the text decided this
        kind, so a header is the best evidence there is and stays a correction."""
        a = _acct()
        v = _val(a, "val:1")
        v["statistic_basis"] = "column_header"
        s = RV.apply_adjudication(a, _adj(), _TEXT, side="a")
        assert s["n_applied"] == 1 and v["statistic"] == "se"
        assert v["statistic_basis"] == "adjudicated"
        assert "kind_conflict" not in v and "statistic_disputed" not in v

    def test_g10_the_rendered_section_shows_the_anchor_and_names_agreement_as_reliability(self):
        from metascience_agent.scaffold import render as R
        a = _acct()
        summary = RV.apply_adjudication(a, _adj(), _TEXT, side="a")
        # Rendered from the summary alone: this section is a function of the
        # adjudication, and the fixture account is not a whole paper.
        md = R.render({"adjudication": summary})
        assert "reliability, not accuracy" in md
        assert "| target | field | from | to | anchor | evidence | item |" in md
        assert "table_header (table:2)" in md


class TestReferenceGroup:
    def test_an_unknown_reference_group_is_an_integrity_problem(self):
        from metascience_agent.scaffold import schema as S
        a = {k: {} for k in S.ACCOUNT_TOP_LEVEL}
        for k in ("procedures", "phases", "studies", "variables", "values", "comparisons", "claims",
                  "figure_panels", "supplements_referenced", "gaps", "accounting"):
            a[k] = []
        a["studies"] = [{"id": "study:a", "groups": [{"id": "grp:vet"}], "phases": []}]
        a["values"] = [{"id": "val:1", "statistic": "ratio", "printed": "1.7", "reference_group_id": "grp:nonvet",
                        "coordinate": {"study_id": "study:a", "group_id": "grp:vet", "phase_id": None}}]
        assert any("unknown reference group" in p for p in S.validate_account(a))
        a["values"][0]["reference_group_id"] = "grp:vet"
        assert not any("reference group" in p for p in S.validate_account(a))

    def test_the_reading_schema_keeps_the_field_optional_so_cached_readings_load(self):
        from metascience_agent.scaffold import reconstruct as RC
        cell = RC.RECON_SCHEMA["properties"]["cells"]["items"]
        assert "reference_group_id" in cell["properties"] and "reference_group_id" not in cell["required"]
        rec = {"column_labels": ["AOR"], "cells": [{"row_label": "r", "section": None, "column_index": 1, "column_label": "AOR",
                                                     "cell": "1.7", "variable": "x", "level": None, "group": None,
                                                     "variable_id": None, "level_id": None, "group_id": None,
                                                     "reference_group_id": "grp:nonvet", "contrast": "vet vs nonvet",
                                                     "numbers": [{"statistic": "ratio", "statistic_basis": "column_header", "value": "1.7"}]}]}
        e = RC.entries_of(rec)[0]
        assert e["reference_group_id"] == "grp:nonvet" and RC.adapt(rec)[0]["entries"][0]["reference_group_id"] == "grp:nonvet"
