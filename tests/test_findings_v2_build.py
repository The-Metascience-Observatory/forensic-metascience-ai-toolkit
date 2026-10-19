"""
Pins for findings_v2.py, the v2 record builder/annotator layer.

The load-bearing claims (docs/specs/findings_v2.md sections 1.4, 1.5, 5, 7, 9):
the finding id is a CONTENT hash, stable under input reordering, numeric
typography and anchor enrichment; `impossible` is derivable only from a
validated absolute-evidence tool call, never from the model's prose; every
clamp routes through severity9 with a registry-resolved evidence class; and
every structural guard here has a KNOWN POSITIVE (LESSONS #4 -- a guard that
cannot fire reads as though it had passed).
"""

from __future__ import annotations

import json
import re

import pytest

from metascience_agent import findings_v2 as fv
from metascience_agent import severity9
from metascience_agent.findings_v2 import (
    FINDING_ID_HASHER_VERSION,
    anchor_key,
    assign_finding_ids,
    channels_block,
    clamp_provisionals,
    derive_impossible,
    finding_id,
    paper_metadata_projection,
    tool_verdict_for,
    validate_producer_constraints,
)
from metascience_agent.webapp_index import CHANNEL_STATES

_ID_RE = re.compile(r"^f_[0-9a-f]{16}$")


def _ledger_call(tool: str, inputs: dict, result: dict,
                 validated: bool = True) -> dict:
    """One toolcall-ledger row in the shape `agent.py` writes and
    `severity_reconcile.severities_from_ledger` consumes."""
    return {"validated": validated, "tool_short": tool,
            "input": inputs, "result": json.dumps(result)}


# ---------------------------------------------------------------------------
# Hasher: stability and canonicalization (spec section 5)
# ---------------------------------------------------------------------------

def test_hasher_version_is_pinned():
    assert FINDING_ID_HASHER_VERSION == "1"


def test_finding_id_shape():
    fid = finding_id("p", "tool_expert", "grim_check", "k", {"mean": 3.53})
    assert _ID_RE.match(fid), fid


def test_same_evidence_same_id():
    args = ("10.1--x", "tool_expert", "grim_check", "table 2: bdi row",
            {"mean": 23.47, "n": 28, "decimals": 2})
    assert finding_id(*args) == finding_id(*args)


def test_input_dict_order_does_not_move_the_id():
    a = finding_id("p", "tool_expert", "grim_check", "k",
                   {"mean": 3.53, "n": 30, "decimals": 2})
    b = finding_id("p", "tool_expert", "grim_check", "k",
                   {"decimals": 2, "n": 30, "mean": 3.53})
    assert a == b


def test_numeric_typography_is_one_value():
    """"3.53" vs 3.53 vs "3.530" is one value seen three ways; hashing the
    typography would mint three ids for one finding and break every
    cross-run join the id exists to serve."""
    ids = {
        finding_id("p", "tool_expert", "grim_check", "k", {"mean": m})
        for m in (3.53, "3.53", "3.530", " 3.53 ")
    }
    assert len(ids) == 1


def test_integral_float_and_int_and_string_are_one_value():
    ids = {
        finding_id("p", "tool_expert", "grim_check", "k", {"n": n})
        for n in (4, 4.0, "4", "4.0")
    }
    assert len(ids) == 1


def test_different_values_are_different_ids():
    a = finding_id("p", "tool_expert", "grim_check", "k", {"mean": 3.53})
    b = finding_id("p", "tool_expert", "grim_check", "k", {"mean": 3.54})
    assert a != b


@pytest.mark.parametrize("field", [0, 1, 2, 3])
def test_each_header_field_moves_the_id(field):
    base = ["p", "tool_expert", "grim_check", "k"]
    other = list(base)
    other[field] = base[field] + "x"
    assert finding_id(*base, {"n": 3}) != finding_id(*other, {"n": 3})


def test_arrays_objects_and_nulls_are_excluded_from_the_hash():
    a = finding_id("p", "tool_expert", "grim_check", "k", {"mean": 3.53})
    b = finding_id("p", "tool_expert", "grim_check", "k",
                   {"mean": 3.53, "rows": [1, 2], "meta": {"x": 1},
                    "nothing": None})
    assert a == b


def test_booleans_do_not_collide_with_their_int_twins():
    """isinstance(True, int) is True in Python; a hash that renders True as
    "1" silently merges a flag with a count."""
    a = finding_id("p", "t", "grim_check", "k", {"x": True})
    b = finding_id("p", "t", "grim_check", "k", {"x": 1})
    assert a != b


def test_string_canonicalization_folds_unicode_and_whitespace():
    """Decomposed form built programmatically, never typed as a literal: an
    editor that NFC-normalizes the file on save would silently make two
    typed literals identical and this test vacuous (LESSONS #4)."""
    import unicodedata
    composed = "caf\u00e9"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed  # prove the instrument is pointed at something
    a = finding_id("p", "t", "grim_check", "k", {"label": composed})
    b = finding_id("p", "t", "grim_check", "k", {"label": f"  {decomposed} "})
    assert a == b


# ---------------------------------------------------------------------------
# anchor_key (spec section 5)
# ---------------------------------------------------------------------------

def test_quote_anchor_key_is_typography_folded():
    a = {"anchors": [{"kind": "quote", "quote": "M = 23.47, SD = 9.1"}]}
    b = {"anchors": [{"kind": "quote", "quote": "m =  23.47, SD = 9.1"}]}
    assert anchor_key(a) == anchor_key(b)
    assert anchor_key(a)  # non-empty


def test_anchor_enrichment_never_moves_the_key():
    """`anchors.annotate_findings` enriches anchors IN PLACE post-adjudication;
    the id must not move when it does, or every adjudicated finding gets a
    new identity."""
    minimal = {"anchors": [{"kind": "quote", "quote": "BDI-II M = 23.47"}]}
    enriched = {"anchors": [{"kind": "quote", "quote": "BDI-II M = 23.47",
                             "page": 6, "char_start": 1200, "status": "found"}]}
    assert anchor_key(minimal) == anchor_key(enriched)


def test_quote_wins_over_page_bbox_regardless_of_list_order():
    finding = {"anchors": [
        {"kind": "page_bbox", "file": "paper.pdf", "page": 6,
         "bbox": [1, 2, 3, 4]},
        {"kind": "quote", "quote": "the load-bearing span"},
    ]}
    assert anchor_key(finding) == anchor_key(
        {"anchors": [{"kind": "quote", "quote": "the load-bearing span"}]})


def test_page_bbox_key_uses_the_page_and_never_the_bbox():
    """Coordinates jitter across PyMuPDF versions; a key that moves with a
    library upgrade re-mints every image finding's id on that upgrade."""
    a = {"anchors": [{"kind": "page_bbox", "file": "paper.pdf", "page": 6,
                      "bbox": [72.0, 401.5, 291.2, 540.0]}]}
    b = {"anchors": [{"kind": "page_bbox", "file": "paper.pdf", "page": 6,
                      "bbox": [72.1, 401.4, 291.0, 540.2]}]}
    assert anchor_key(a) == anchor_key(b) == "paper.pdf:6"


def test_table_cell_key_sorts_cells_and_prefers_sheet_over_table():
    a = {"anchors": [{"kind": "table_cell", "sheet": "S1",
                      "cells": ["C4", "B4"]}]}
    b = {"anchors": [{"kind": "table_cell", "sheet": "S1", "table": "ignored",
                      "cells": ["B4", "C4"]}]}
    assert anchor_key(a) == anchor_key(b)
    assert anchor_key(a).endswith("B4,C4")


def test_no_anchors_falls_back_to_folded_location():
    assert anchor_key({"location": "Table  2, BDI row"}) == \
        anchor_key({"location": "table 2, bdi row", "anchors": []})


def test_empty_quote_anchor_falls_through_to_the_next_kind():
    finding = {"anchors": [
        {"kind": "quote", "quote": ""},
        {"kind": "page_bbox", "file": "paper.pdf", "page": 3},
    ], "location": "unused"}
    assert anchor_key(finding) == "paper.pdf:3"


# ---------------------------------------------------------------------------
# assign_finding_ids: batch assignment + collision suffixing
# ---------------------------------------------------------------------------

def test_assign_stamps_id_and_hasher_version():
    rows = [{"producer": "tool_expert", "technique": "grim_check",
             "location": "Table 2", "inputs": {"mean": 3.53, "n": 30}}]
    out = assign_finding_ids(rows, "10.1--x")
    assert out is rows
    assert _ID_RE.match(rows[0]["finding_id"])
    assert rows[0]["finding_id_hasher"] == FINDING_ID_HASHER_VERSION


def test_within_run_collisions_get_dash_n_suffixes():
    row = {"producer": "tool_expert", "technique": "grim_check",
           "location": "Table 2", "inputs": {"mean": 3.53, "n": 30}}
    rows = [dict(row), dict(row), dict(row),
            dict(row, inputs={"mean": 3.54, "n": 30})]
    assign_finding_ids(rows, "p")
    base = rows[0]["finding_id"]
    assert _ID_RE.match(base)
    assert rows[1]["finding_id"] == f"{base}-2"
    assert rows[2]["finding_id"] == f"{base}-3"
    # the genuinely different row keeps its own unsuffixed hash
    assert rows[3]["finding_id"] != base
    assert _ID_RE.match(rows[3]["finding_id"])


def test_typographically_different_duplicates_still_collide():
    """The collision handler must see through the same canonicalization the
    hash uses: 3.53 emitted once as a float and once as "3.530" is one
    finding said twice, not two findings."""
    rows = [
        {"producer": "tool_expert", "technique": "grim_check",
         "location": "Table 2", "inputs": {"mean": 3.53, "n": 30}},
        {"producer": "tool_expert", "technique": "grim_check",
         "location": "Table 2", "inputs": {"mean": "3.530", "n": 30.0}},
    ]
    assign_finding_ids(rows, "p")
    assert rows[1]["finding_id"] == rows[0]["finding_id"] + "-2"


def test_non_dict_rows_are_skipped_without_crashing():
    rows = ["not a row",
            {"producer": "tool_expert", "technique": "grim_check",
             "location": "x", "inputs": {}}]
    assign_finding_ids(rows, "p")
    assert "finding_id" in rows[1]


# ---------------------------------------------------------------------------
# tool_verdict_for (spec section 1.4)
# ---------------------------------------------------------------------------

def test_v2_technique_equality_joins_to_its_call():
    ledger = [_ledger_call("grim_check",
                           {"mean": 3.53, "n": 30, "decimals": 2},
                           {"severity": "impossible"})]
    verdict = tool_verdict_for(
        {"technique": "grim_check", "inputs": {"mean": 3.53, "n": 30}}, ledger)
    assert verdict == {"severity": "impossible", "tool": "grim_check",
                       "validated": True, "quarantined_raw": None}


def test_legacy_family_technique_joins_to_the_member_tool():
    """A converted legacy row says `technique: "grim"`; the ledger records
    `grim_check`. The family mapping is severity_reconcile's, reused."""
    ledger = [_ledger_call("grim_check", {"mean": 3.53, "n": 30},
                           {"severity": "impossible"})]
    verdict = tool_verdict_for(
        {"technique": "grim", "inputs": {"mean": 3.53, "n": 30}}, ledger)
    assert verdict is not None
    assert verdict["tool"] == "grim_check"
    assert verdict["severity"] == "impossible"


def test_unvalidated_calls_are_invisible_to_the_join():
    ledger = [_ledger_call("grim_check", {"mean": 3.53, "n": 30},
                           {"severity": "impossible"}, validated=False)]
    assert tool_verdict_for(
        {"technique": "grim_check", "inputs": {"mean": 3.53, "n": 30}},
        ledger) is None


def test_disagreeing_calls_with_no_scalars_yield_no_verdict():
    """Two calls, two verdicts, and a finding naming no comparable scalars:
    guessing which one the model meant could clear a finding using a
    different row's verdict, so the join must refuse."""
    ledger = [
        _ledger_call("grim_check", {"mean": 3.53, "n": 30},
                     {"severity": "impossible"}),
        _ledger_call("grim_check", {"mean": 2.10, "n": 30},
                     {"severity": "consistent"}),
    ]
    assert tool_verdict_for(
        {"technique": "grim_check", "inputs": {"note": "prose only"}},
        ledger) is None


def test_scalar_subset_join_picks_the_right_call():
    ledger = [
        _ledger_call("grim_check", {"mean": 3.53, "n": 30},
                     {"severity": "impossible"}),
        _ledger_call("grim_check", {"mean": 2.10, "n": 30},
                     {"severity": "consistent"}),
    ]
    verdict = tool_verdict_for(
        {"technique": "grim_check", "inputs": {"mean": 2.10}}, ledger)
    assert verdict is not None and verdict["severity"] == "consistent"


def test_flow_findings_join_on_nested_stage_headcounts():
    """check_flow_arithmetic's only discriminating argument is the nested
    `stages` list, so the scalar join sees nothing. Measured on the
    2026-08-21 cerebrolysin run: two flow calls (the Results reading:
    consistent; the abstract reading: impossible), an empty `wanted`, and
    the unanimity rule refusing -- the flagship science tool could never
    join its own verdict. The nested-`n` fallback must pick by headcounts."""
    ledger = [
        _ledger_call("check_flow_arithmetic",
                     {"stages": [{"label": "randomized", "n": 30},
                                 {"label": "2nd Op (Results)", "n": 21},
                                 {"label": "3rd Op", "n": 15}]},
                     {"severity": "consistent"}),
        _ledger_call("check_flow_arithmetic",
                     {"stages": [{"label": "randomized", "n": 30},
                                 {"label": "2nd Op (abstract)", "n": 16},
                                 {"label": "3rd Op", "n": 15}]},
                     {"severity": "impossible"}),
    ]
    verdict = tool_verdict_for(
        {"technique": "check_flow_arithmetic",
         "inputs": {"stages": [
             {"label": "randomized", "n": 30, "excluded_total": 9},
             {"label": "2nd Op (abstract)", "n": 16},
             {"label": "3rd Op", "n": 15}]}},
        ledger)
    assert verdict is not None and verdict["severity"] == "impossible"


def test_nested_headcounts_matching_no_call_refuse_rather_than_guess():
    """A non-empty nested-`n` key set that matches no call must yield None:
    falling back to 'all calls' here would attribute a verdict to headcounts
    the tool never saw."""
    ledger = [_ledger_call(
        "check_flow_arithmetic",
        {"stages": [{"label": "randomized", "n": 30},
                    {"label": "completed", "n": 21}]},
        {"severity": "consistent"})]
    assert tool_verdict_for(
        {"technique": "check_flow_arithmetic",
         "inputs": {"stages": [{"label": "randomized", "n": 40},
                               {"label": "completed", "n": 21}]}},
        ledger) is None


def test_batch_rows_join_per_row_not_at_the_call_level():
    """A batch call's own severity is the WORST row; joining a single-row
    finding to it would make every row in the table look like the worst
    one. The per-row expansion is severity_reconcile's, reused."""
    ledger = [_ledger_call(
        "check_regression_batch",
        {"rows": [{"b": 1.0, "se": 0.5, "reported_t": 9.9},
                  {"b": 2.0, "se": 0.5, "reported_t": 4.0}]},
        {"severity": "impossible",
         "results": [
             {"row": 0, "b": 1.0, "se": 0.5, "severity": "impossible"},
             {"row": 1, "b": 2.0, "se": 0.5, "severity": "consistent"},
         ]})]
    verdict = tool_verdict_for(
        {"technique": "check_regression", "inputs": {"reported_t": 4.0}},
        ledger)
    assert verdict is not None and verdict["severity"] == "consistent"


def test_non_tool_techniques_carry_no_verdict():
    ledger = [_ledger_call("grim_check", {"mean": 3.53, "n": 30},
                           {"severity": "impossible"})]
    for technique in ("not_computational", "factual_claim",
                      "internal_contradiction", "legacy_unattributed"):
        assert tool_verdict_for({"technique": technique, "inputs": {}},
                                ledger) is None


def test_model_prose_is_never_trusted():
    """severity_reconcile._tool_severity reads `computed.severity` as its
    first route; spec 1.4 says the verdict is joined from the ledger and
    never trusted from prose, so an empty ledger means NO verdict even when
    the model transcribed one."""
    finding = {"technique": "grim_check",
               "inputs": {"mean": 3.53, "n": 30},
               "computed": {"severity": "impossible"}}
    assert tool_verdict_for(finding, []) is None
    assert tool_verdict_for(finding, None) is None


def test_quarantined_raw_is_surfaced_from_the_call():
    ledger = [_ledger_call("detect_tortured_phrases", {"path": "x.md"},
                           {"severity": "indeterminate",
                            "severity_before_quarantine": "suspicious"})]
    verdict = tool_verdict_for(
        {"technique": "detect_tortured_phrases", "inputs": {}}, ledger)
    assert verdict == {"severity": "indeterminate",
                       "tool": "detect_tortured_phrases",
                       "validated": True, "quarantined_raw": "suspicious"}


# ---------------------------------------------------------------------------
# derive_impossible (spec section 1.5)
# ---------------------------------------------------------------------------

def _absolute_impossible_row(**over) -> dict:
    row = {
        "producer": "tool_expert", "technique": "grim_check",
        "computed_by": "registry_tool", "quarantined": False,
        "outcome": "problem",
        "tool_verdict": {"severity": "impossible", "tool": "grim_check",
                         "validated": True, "quarantined_raw": None},
    }
    row.update(over)
    return row


def test_impossible_known_positive_through_the_full_path():
    """The one route that exists: a validated call of an absolute-evidence
    tool returned `impossible` and the join attributed it to this row."""
    ledger = [_ledger_call("grim_check", {"mean": 3.53, "n": 30},
                           {"severity": "impossible"})]
    finding = {"producer": "tool_expert", "technique": "grim_check",
               "computed_by": "registry_tool",
               "inputs": {"mean": 3.53, "n": 30}}
    finding["tool_verdict"] = tool_verdict_for(finding, ledger)
    assert derive_impossible(finding) is True


def test_impossible_from_a_non_absolute_tool_is_false():
    """detect_duplication is probabilistic-evidence; even a stray
    `impossible` string attributed to it may not mint the flag (duplication
    is improbable, never a math violation -- rulebook rules 3/9/11)."""
    row = _absolute_impossible_row(
        technique="detect_duplication",
        tool_verdict={"severity": "impossible", "tool": "detect_duplication",
                      "validated": True, "quarantined_raw": None})
    assert derive_impossible(row) is False


def test_impossible_from_a_descriptive_tool_is_false():
    row = _absolute_impossible_row(
        tool_verdict={"severity": "impossible", "tool": "multiplicity_report",
                      "validated": True, "quarantined_raw": None})
    assert derive_impossible(row) is False


def test_unvalidated_call_is_false():
    row = _absolute_impossible_row()
    row["tool_verdict"]["validated"] = False
    assert derive_impossible(row) is False


def test_model_claimed_with_no_ledger_row_is_false():
    """The model wrote "impossible" in its prose; the join found no call.
    tool_verdict is None and the flag is unreachable."""
    finding = {"producer": "tool_expert", "technique": "grim_check",
               "computed_by": "registry_tool",
               "inputs": {"mean": 3.53, "n": 30},
               "title": "mean 3.53 is impossible for n=30"}
    finding["tool_verdict"] = tool_verdict_for(finding, [])
    assert finding["tool_verdict"] is None
    assert derive_impossible(finding) is False


def test_non_impossible_verdict_is_false():
    row = _absolute_impossible_row()
    row["tool_verdict"]["severity"] = "highly_suspicious"
    assert derive_impossible(row) is False


def test_quarantined_rows_cannot_carry_impossible():
    assert derive_impossible(_absolute_impossible_row(quarantined=True)) is False


def test_fast_screen_cannot_carry_impossible():
    assert derive_impossible(
        _absolute_impossible_row(producer="fast_screen")) is False


@pytest.mark.parametrize("channel", ["agent_code", "model_reading"])
def test_agent_code_and_model_reading_cannot_carry_impossible(channel):
    assert derive_impossible(
        _absolute_impossible_row(computed_by=channel)) is False


def test_unknown_tool_name_is_false():
    row = _absolute_impossible_row(
        tool_verdict={"severity": "impossible", "tool": "no_such_tool",
                      "validated": True, "quarantined_raw": None})
    assert derive_impossible(row) is False


# ---------------------------------------------------------------------------
# clamp_provisionals (spec section 7, via severity9)
# ---------------------------------------------------------------------------

def _problem_row(technique: str, sev: int, **over) -> dict:
    row = {"slug": f"{technique}_row", "technique": technique,
           "producer": "tool_expert", "outcome": "problem",
           "provisional_severity": sev, "quarantined": False}
    row.update(over)
    return row


def test_analyst_provisional_nine_survives_clamp():
    """v1.14.0: no ceiling. A tool-backed row citing its tool keeps the rung
    it claimed, all the way to 9, and is not marked as clamped."""
    rows = [_problem_row("grim_check", 9, computed_by="registry_tool")]
    summary = clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == 9
    assert "provisional_severity_from" not in rows[0]
    assert summary["n_clamped"] == 0 and summary["clamps"] == []


def test_no_class_cap_on_probabilistic_or_descriptive_tools():
    """The registry `evidence` class no longer caps anything; only the
    channel does. `detect_duplication` is probabilistic, `check_sd_range`
    absolute -- both keep a 6."""
    rows = [_problem_row("detect_duplication", 6, computed_by="registry_tool"),
            _problem_row("check_sd_range", 6, computed_by="registry_tool")]
    clamp_provisionals(rows)
    assert [r["provisional_severity"] for r in rows] == [6, 6]


def test_clamp_summary_names_the_channel():
    rows = [_problem_row("grim_check", 6, computed_by="agent_code")]
    summary = clamp_provisionals(rows)
    assert summary["n_clamped"] == 1
    assert "grim_check_row" in summary["clamps"][0]
    assert "agent_code" in summary["clamps"][0]


def test_quarantine_composes_by_min():
    rows = [_problem_row("grim_check", 5, quarantined=True)]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == severity9.QUARANTINE_CAP


def test_model_knowledge_basis_routes_through_the_evidence_channel():
    rows = [_problem_row("factual_claim", 5, basis="model_knowledge",
                         computed_by="model_reading",
                         producer="science_error")]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == severity9.MODEL_KNOWLEDGE_CAP


def test_unsourced_web_lookup_is_model_knowledge_for_the_clamp():
    # MEASURED 2026-08-22 (four-paper grok rematch): ten basis=web_lookup
    # rows with web_sources: [], one at severity 4 -- above the cap an
    # unsourced claim is allowed. No recorded source = memory.
    rows = [_problem_row("factual_claim", 5, basis="web_lookup",
                         web_sources=[], computed_by="model_reading",
                         producer="science_error")]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == severity9.MODEL_KNOWLEDGE_CAP


def test_sourced_web_lookup_keeps_its_channel():
    rows = [_problem_row("factual_claim", 5, basis="web_lookup",
                         web_sources=[{"url": "https://x", "quote": "q"}],
                         computed_by="model_reading",
                         producer="science_error")]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == 5


def test_unsourced_lookup_with_a_tool_verdict_keeps_the_tool_channel():
    # The tool result, not the lookup, is that row's evidence.
    rows = [_problem_row("grim_check", 5, basis="web_lookup",
                         web_sources=[], computed_by="registry_tool",
                         producer="science_error")]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == 5


def test_agent_code_channel_caps_at_four():
    rows = [_problem_row("grim_check", 5, computed_by="agent_code",
                         producer="science_error")]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == severity9.AGENT_CODE_CAP


def test_fast_screen_producer_caps_at_four():
    # `registry_tool`, not `model_reading`: this test isolates the PRODUCER
    # cap, and `model_reading` on a tool technique now carries a tighter one of
    # its own (3), which would mask what this asserts.
    rows = [_problem_row("grim_check", 5, producer="fast_screen",
                         computed_by="registry_tool")]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == severity9.FAST_SCREEN_CAP


def test_model_reading_on_a_tool_technique_caps_at_three():
    """MEASURED 2026-08-22: two findings shipped at severity 4 in a
    `does_not_reconcile` verdict claiming `recalc_anova` / `recalc_independent_t`
    with no inputs, no computed block and no tool_verdict -- arithmetic
    asserted rather than performed. One is a verified false positive."""
    rows = [_problem_row("recalc_anova", 4, computed_by="model_reading")]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == severity9.MODEL_READING_CAP


def test_model_reading_on_a_non_tool_warrant_is_untouched():
    """An `internal_contradiction` has no arithmetic to cite; reading the page
    IS its honest channel. The gate is `registry.BY_NAME`, so this row never
    reaches the cap."""
    rows = [_problem_row("internal_contradiction", 4,
                         computed_by="model_reading")]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == 4


def test_citing_the_tool_lifts_the_model_reading_cap():
    rows = [_problem_row("recalc_anova", 4, computed_by="registry_tool")]
    clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == 4


def test_fixed_non_tool_techniques_have_no_cap():
    rows = [_problem_row("not_computational", 6),
            _problem_row("factual_claim", 6, producer="science_error")]
    clamp_provisionals(rows)
    assert [r["provisional_severity"] for r in rows] == [6, 6]


def test_hand_arithmetic_takes_the_model_reading_cap():
    """1.91.0: the tools prompt promises `no_tool_exists` and
    `tool_existed_unused` the cap, and nothing applied it."""
    from metascience_agent.severity9 import MODEL_READING_CAP
    rows = [_problem_row("no_tool_exists", 6),
            _problem_row("tool_existed_unused", 6),
            _problem_row("no_tool_exists", 2)]
    clamp_provisionals(rows)
    assert [r["provisional_severity"] for r in rows] == [MODEL_READING_CAP] * 2 + [2]
    assert rows[0]["provisional_severity_from"] == 6


def test_unknown_technique_is_not_clamped_and_not_reported():
    """v1.14.0: there is no class cap for an unknown technique to fall to,
    and whether a technique name is valid is the schema enum's question
    (`--json-schema` rejects it), not this function's."""
    rows = [_problem_row("grim_chekc", 6)]  # deliberate typo
    summary = clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == 6
    assert summary["problems"] == []


def test_below_cap_severity_is_untouched():
    rows = [_problem_row("grim_check", 3)]
    summary = clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == 3
    assert summary["n_clamped"] == 0 and summary["clamps"] == []


def test_null_provisional_is_skipped_not_crashed():
    rows = [{"slug": "pass_row", "technique": "grim_check",
             "outcome": "pass", "provisional_severity": None}]
    summary = clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] is None
    assert summary["n_rows"] == 1 and summary["n_clamped"] == 0


def test_malformed_provisional_is_reported_never_raised():
    rows = [_problem_row("grim_check", 6) | {"provisional_severity": "high"}]
    summary = clamp_provisionals(rows)
    assert rows[0]["provisional_severity"] == "high"  # left as evidence
    assert summary["n_skipped"] == 1
    assert summary["problems"][0]["constraint"] == "provisional_severity_type"


# ---------------------------------------------------------------------------
# paper_metadata_projection (spec section 2)
# ---------------------------------------------------------------------------

_META_11 = {
    "schema_version": "1.1",
    "doi": "10.1000/x1", "title": "A Paper", "authors": "Nina Mazar; Dan Ariely",
    "first_author": "Mazar", "journal": "J. Neural Transm.",
    "journal_normalized": "Journal of Neural Transmission",
    "authors_list": [
        {"given": "Nina", "family": "Mazar", "full": "Nina Mazar"},
        {"given": None, "family": "Ariely", "full": "Ariely"},
    ],
    "volume": "12", "issue": "3", "pages": "1-9", "year": 2019,
    "url": "https://doi.org/10.1000/x1", "error": None,
    "metadata_status": "ok", "source": "crossref", "fetched_at": "2026-08-21",
}


def test_projection_carries_the_v2_block_keys():
    block = paper_metadata_projection(_META_11)
    assert block["doi"] == "10.1000/x1"
    assert block["journal"] == "J. Neural Transm."
    assert block["journal_normalized"] == "Journal of Neural Transmission"
    assert block["year"] == 2019
    assert block["metadata_status"] == "ok"
    assert block["authors"] == "Nina Mazar; Dan Ariely"


def test_projection_does_not_leak_non_block_keys():
    block = paper_metadata_projection(_META_11)
    for absent in ("title", "volume", "issue", "pages", "url", "error",
                   "fetched_at", "source", "first_author", "schema_version"):
        assert absent not in block


def test_projection_filters_author_entries_to_string_fields():
    """build_authors_list legitimately records given: None; the block's item
    schema types every field as a string, so None fields are dropped rather
    than emitted."""
    block = paper_metadata_projection(_META_11)
    assert block["authors_list"] == [
        {"given": "Nina", "family": "Mazar", "full": "Nina Mazar"},
        {"family": "Ariely", "full": "Ariely"},
    ]


def test_projection_upgrades_a_one_point_oh_record_in_memory():
    """A 1.0 metadata.json predates the 1.1 fields; the projection derives
    them locally (zero network) so the block never silently lacks the
    normalized journal -- and the caller's dict is not mutated."""
    v10 = {"doi": "10.1000/x2", "title": "Old", "authors": "Kim Lee",
           "journal": "Some Unknown Journal", "year": "2015",
           "source": "crossref", "error": None}
    before = dict(v10)
    block = paper_metadata_projection(v10)
    assert v10 == before
    # passthrough for an unmapped journal: known journal never maps to null
    assert block["journal_normalized"] == "Some Unknown Journal"
    assert block["metadata_status"]
    assert block["authors_list"]


def test_projection_of_nothing_is_an_empty_block():
    """A missing metadata.json projects to {}: the absence IS the statement,
    and inventing a status for a fetch that never happened would be the
    file-date-as-run-date substitution in miniature."""
    assert paper_metadata_projection(None) == {}
    assert paper_metadata_projection("not a dict") == {}


def test_projection_drops_blank_values():
    block = paper_metadata_projection(
        {"schema_version": "1.1", "doi": "", "journal": None, "authors": "A B",
         "journal_normalized": None, "authors_list": [],
         "metadata_status": "partial"})
    assert "doi" not in block and "journal" not in block
    assert "journal_normalized" not in block and "authors_list" not in block
    assert block["metadata_status"] == "partial"


# ---------------------------------------------------------------------------
# channels_block (spec section 2)
# ---------------------------------------------------------------------------

def test_every_state_in_the_shared_vocabulary_is_accepted():
    block = channels_block({f"ch_{s}": s for s in CHANNEL_STATES})
    assert set(block) == {f"ch_{s}" for s in CHANNEL_STATES}
    for entry in block.values():
        assert set(entry) == {"state", "detail"}


def test_channels_block_accepts_all_three_value_forms():
    block = channels_block(
        {"a": "ran",
         "b": ("ran_result_discarded", "no result retained"),
         "c": {"state": "refused", "detail": "no_text_layer"}},
        d="did_not_run")
    assert block["a"] == {"state": "ran", "detail": ""}
    assert block["b"] == {"state": "ran_result_discarded",
                          "detail": "no result retained"}
    assert block["c"] == {"state": "refused", "detail": "no_text_layer"}
    assert block["d"] == {"state": "did_not_run", "detail": ""}


def test_unknown_state_raises_instead_of_degrading():
    """KNOWN POSITIVE: a typo'd state silently becoming 'unknown' would be
    absence-read-as-evidence inside the very vocabulary built to prevent
    it."""
    with pytest.raises(ValueError, match="unknown state"):
        channels_block({"image": "ran_but_discarded"})  # not a real state


def test_dict_form_with_stray_keys_is_refused():
    with pytest.raises(ValueError, match="unknown keys"):
        channels_block({"image": {"state": "ran", "verdict": "clean"}})


def test_channel_vocabulary_matches_the_v2_schema_enum():
    """One five-state vocabulary, three homes: webapp_index, this builder,
    and the schema. The schema's enum must be the same tuple verbatim."""
    from metascience_agent.core.prompts import findings_schema_v2
    enum = findings_schema_v2()["properties"]["channels"][
        "additionalProperties"]["properties"]["state"]["enum"]
    assert enum == list(CHANNEL_STATES)


# ---------------------------------------------------------------------------
# validate_producer_constraints (spec section 9)
# ---------------------------------------------------------------------------

def _clean_problem_row(**over) -> dict:
    # `inputs` is part of CLEAN for a tool-technique problem row: without it
    # `tool_verdict_for` has nothing to match on, so the tool's own verdict
    # cannot reach the record (constraint `tool_technique_without_inputs`).
    row = {"slug": "ok_row", "producer": "tool_expert",
           "technique": "grim_check", "outcome": "problem",
           "provisional_severity": 3, "quarantined": False,
           "computed_by": "registry_tool",
           "inputs": {"mean": 5.51, "n": 30, "decimals": 2}}
    row.update(over)
    return row


def _constraints(rows):
    return [p["constraint"] for p in validate_producer_constraints(rows)]


def test_clean_rows_yield_no_problems():
    assert validate_producer_constraints([_clean_problem_row()]) == []


def test_tool_expert_claiming_agent_code_must_flag():
    """THE known positive the spec demands: agent_code is legal only with
    producer science_error; a tool_expert row claiming it is claiming an
    evidence channel its producer does not have."""
    problems = validate_producer_constraints(
        [_clean_problem_row(computed_by="agent_code")])
    assert [p["constraint"] for p in problems] == ["agent_code_producer"]
    assert problems[0]["index"] == 0
    assert problems[0]["slug"] == "ok_row"


def test_science_error_with_agent_code_is_legal():
    assert validate_producer_constraints(
        [_clean_problem_row(producer="science_error",
                            computed_by="agent_code")]) == []


def test_fast_screen_structural_caps_all_fire():
    row = _clean_problem_row(
        producer="fast_screen", computed_by="model_reading",
        severity_is_provisional=False, impossible=True,
        provisional_severity=severity9.FAST_SCREEN_CAP + 1)
    got = _constraints([row])
    assert "fast_screen_provisional" in got
    assert "fast_screen_impossible" in got
    assert "fast_screen_cap" in got


def test_compliant_fast_screen_row_is_clean():
    row = _clean_problem_row(
        producer="fast_screen", computed_by="model_reading",
        severity_is_provisional=True, impossible=False,
        provisional_severity=severity9.FAST_SCREEN_CAP)
    assert validate_producer_constraints([row]) == []


def test_provisional_on_a_non_problem_outcome_flags():
    assert _constraints([_clean_problem_row(outcome="pass")]) == \
        ["provisional_requires_problem"]


def test_problem_without_provisional_flags():
    assert _constraints(
        [_clean_problem_row(provisional_severity=None)]) == \
        ["problem_requires_provisional"]


def test_final_severity_on_a_pass_flags():
    assert "severity_requires_problem" in _constraints(
        [_clean_problem_row(outcome="pass", provisional_severity=None,
                            severity=3)])


def test_final_severity_on_a_discarded_row_flags():
    """Discarded rows are RETAINED with severity: null -- 'ran and
    discarded' must stay distinguishable from 'did not run'."""
    assert _constraints(
        [_clean_problem_row(severity=3,
                            adjudication={"action": "discarded"})]) == \
        ["severity_on_discarded"]


def test_final_severity_on_a_kept_problem_is_clean():
    assert validate_producer_constraints(
        [_clean_problem_row(severity=3,
                            adjudication={"action": "kept"})]) == []


def test_quarantine_without_reason_flags():
    assert _constraints([_clean_problem_row(quarantined=True)]) == \
        ["quarantine_without_reason"]
    assert validate_producer_constraints(
        [_clean_problem_row(quarantined=True,
                            quarantine_reason="seed dictionary")]) == []


def test_validator_never_raises_on_malformed_input():
    problems = validate_producer_constraints(["not a dict", 42, None])
    assert [p["constraint"] for p in problems] == ["row_not_a_dict"] * 3
    bad = validate_producer_constraints({"not": "a list"})
    assert bad[0]["constraint"] == "rows_not_a_list"
    assert validate_producer_constraints(None) == []


def test_problem_records_are_structured_not_prose_only():
    problems = validate_producer_constraints(
        [_clean_problem_row(computed_by="agent_code")])
    for p in problems:
        assert set(p) == {"index", "slug", "constraint", "problem"}
        assert isinstance(p["problem"], str) and p["problem"]


def test_a_tool_technique_row_with_no_inputs_cannot_be_joined_to_its_evidence():
    """MEASURED 2026-08-22 on 10.1037--0022-3514.94.2.94.2.196: four `recalc_*`
    rows carried `inputs: null` and `tool_verdict: NONE` while the tools had
    returned `suspicious` on exactly those numbers. Corpus-wide, rows carrying
    `inputs` fell from 85% to 56% between two runs and nothing counted it."""
    assert _constraints([_clean_problem_row(technique="recalc_anova",
                                            inputs=None)]) == \
        ["tool_technique_without_inputs"]


def test_a_non_tool_technique_needs_no_inputs():
    """An `internal_contradiction` has no tool to join to."""
    assert _constraints([_clean_problem_row(
        technique="internal_contradiction", inputs=None)]) == []


def test_a_pass_row_without_inputs_is_not_flagged():
    """The constraint is about accusations that cannot show their evidence.
    A cleared row is not accusing anyone."""
    assert _constraints([_clean_problem_row(
        outcome="pass", provisional_severity=None, inputs=None)]) == []



class TestABareUrlIsNotAFindingTitle:
    """MEASURED 2026-08-22, `10.15585--mmwr.mm6923e2`. The science agent filed
    three `pass` rows whose title was nothing but a link -- a Wikipedia page on
    sodium hypochlorite filed under the technique `check_summation_batch`, a
    university chemical-incompatibility page under `check_flow_arithmetic`, and
    a state health department page under `not_computational`. They stayed out
    of the report because they were passes, and sat in `findings.v2.json` and
    the value register as noise a reader has to page past.
    """

    def test_the_three_real_titles_are_caught(self):
        for url in ("https://en.wikipedia.org/wiki/Sodium_hypochlorite",
                    "https://ibc.utah.edu/library/sodium-hypochlorite-bleach"
                    "-chemical-incompatibility.php",
                    "https://doh.wa.gov/community-and-environment/"
                    "contaminants/bleach-mixing-dangers"):
            assert fv.title_is_a_bare_url(url), url

    def test_a_url_inside_a_sentence_is_a_real_finding(self):
        """`10.1016--j.ebiom.2021.103246` filed exactly this, at severity 3."""
        assert not fv.title_is_a_bare_url(
            "Named sequencing deposit URL nigdb.cineca.it does not resolve")

    def test_ordinary_titles_and_empties_pass(self):
        assert not fv.title_is_a_bare_url(
            "Abstract PSM OR 1.89 disagrees with Table 5 OR 1.95")
        assert not fv.title_is_a_bare_url("")
        assert not fv.title_is_a_bare_url(None)

    def test_the_row_survives_and_the_link_moves_to_notes(self):
        from metascience_agent.parallel import _rows_from_producer
        url = "https://en.wikipedia.org/wiki/Sodium_hypochlorite"
        rows = _rows_from_producer(
            {"findings": [{"title": url, "technique": "check_summation_batch",
                           "description": "d", "outcome": "pass"}]},
            "science_error", [], "10.15585--mmwr")
        assert len(rows) == 1, "the row is kept; only its title is repaired"
        assert rows[0]["title"] != url
        assert url in rows[0]["notes"]
