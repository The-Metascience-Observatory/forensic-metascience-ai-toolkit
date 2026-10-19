"""The v2 findings contract does what docs/specs/findings_v2.md says it does.

Four properties, each guarding a named failure:

- The spec's own example rows VALIDATE. The examples are the contract's only
  worked instances; a schema that rejects its own spec's examples is a schema
  nobody has run against a known positive (LESSONS #4).
- The producer subset REJECTS the annotator/adjudicator fields. Section 4's
  rule is enforcement by OMISSION -- if `finding_id`, `severity` or
  `impossible` ever become emittable by a producer, a model can mint its own
  ids and verdicts, and the anti-forgery property is gone without any test
  failing elsewhere.
- The technique enum tracks the registry LIVE. Both sides are computed here
  (registry names from `registry.SPECS`, the six non-tool values transcribed
  from the spec), so a tool added to the registry without reaching the enum --
  or an enum entry with no registry backing, the `grim` vs `grim_check`
  drift -- fails this file, not a downstream join months later.
- The channel vocabulary has ONE home. The five states are defined in
  `webapp_index.CHANNEL_STATES` and repeated in the schema file; two homes
  that can drift apart is exactly how `_totals`' private channel list broke,
  so the two are pinned equal here.

And one negative property: v1 is untouched. The live two_stage pipeline stays
on v1 until cutover, so `findings_schema()` must keep returning exactly what
`findings.schema.json` says, and that file must keep saying what it said
before v2 existed.
"""

import hashlib
import json

import jsonschema
import pytest

from forensic_metascience_ai_toolkit import registry
from forensic_metascience_ai_toolkit.core import prompts
from forensic_metascience_ai_toolkit.webapp_index import CHANNEL_STATES

SCHEMA = prompts.findings_schema_v2()
FINDING = SCHEMA["properties"]["findings"]["items"]

# ---------------------------------------------------------------------------
# The four example rows from docs/specs/findings_v2.md section 6, transcribed.
# Two classes of edit, both forced and both deliberate:
#
# - Prose the spec elides with an ellipsis (`"description": "…"`) is filled to
#   meet the schema's own hard length bounds (section 8: description 20-700).
#   An ellipsis is a placeholder, not content, and a test row that fails the
#   contract's length rule would prove nothing about the fields under test.
# - Rows 3 and 4 print `technique: image_duplication` / `tortured_phrases`,
#   which are neither registry names nor the six non-tool values. Section 1.2
#   is normative ("registry-derived EXACT tool names"; it exists to END the
#   name drift those literals are an instance of), and the spec's own header
#   says the corrected rule wins over an earlier sketch -- so the techniques
#   here are the registry names of the tools the rows' own `tool_verdict`
#   blocks cite: `analyze_paper_images` and `detect_tortured_phrases`.
# ---------------------------------------------------------------------------

ROW_TOOL_EXPERT = {
    "finding_id": "f_9c1e22ab34cd56ef", "finding_id_hasher": "1",
    "slug": "table2_bdi_mean_grim", "producer": "tool_expert",
    "technique": "grim_check", "computed_by": "registry_tool",
    "title": "Table 2: BDI-II mean 23.47 is impossible for n=28",
    "description": (
        "Table 2 reports mean 23.47 (SD 9.1) for the BDI-II in the "
        "intervention arm (n=28). No set of 28 integer scores can produce a "
        "mean of 23.47 at two decimals; the nearest attainable values are "
        "23.46 and 23.50. A transcription slip in the mean or the n would "
        "explain it."
    ),
    "location": "Table 2, BDI-II row", "outcome": "problem",
    "provisional_severity": 3, "severity": 3, "severity_is_provisional": False,
    "impossible": True, "quarantined": False,
    "tool_verdict": {"severity": "impossible", "tool": "grim_check",
                     "validated": True, "quarantined_raw": None},
    "quote": "BDI-II scores in the intervention group (M = 23.47, SD = 9.1, n = 28)…",
    "inputs": {"mean": 23.47, "n": 28, "decimals": 2, "data_type": "integer",
               "bound_source": "stated"},
    "anchors": [{"kind": "quote", "quote": "BDI-II scores…", "label": "Table 2"}],
    "reproduction": "metascience grim --mean 23.47 --n 28 --decimals 2",
    "adjudication": {"action": "kept", "category": "…",
                     "rationale": "Cross-checked against r_grim; no bound ambiguity."},
}

ROW_SCIENCE_ERROR = {
    "finding_id": "f_77aa01bc9932de10", "finding_id_hasher": "1",
    "slug": "gfap_antibody_species", "producer": "science_error",
    "technique": "factual_claim", "computed_by": "model_reading",
    "basis": "web_lookup",
    "web_sources": [{"url": "https://…", "title": "Anti-GFAP ab7260 datasheet",
                     "quote": "Rabbit polyclonal to GFAP", "accessed": "2026-08-21"}],
    "title": "Methods: ab7260 described as a mouse monoclonal; it is rabbit polyclonal",
    "description": (
        "The Methods section describes Abcam ab7260 as a mouse monoclonal "
        "antibody; the manufacturer's datasheet lists ab7260 as a rabbit "
        "polyclonal, so the catalogue number and the stated reagent cannot "
        "both be right."
    ),
    "location": "Methods, Immunohistochemistry",
    "outcome": "problem", "provisional_severity": 4, "severity": 4,
    "severity_is_provisional": False, "impossible": False, "quarantined": False,
    "tool_verdict": None,
    "quote": "…mouse monoclonal anti-GFAP (Abcam ab7260, 1:500)…",
    "anchors": [{"kind": "quote", "quote": "…mouse monoclonal anti-GFAP (Abcam ab7260, 1:500)…"}],
    "reproduction_kind": "no_command_applies",
    "adjudication": {"action": "kept",
                     "rationale": "Datasheet confirms the species/clonality mismatch."},
}

ROW_IMAGE_TRACK = {
    "finding_id": "f_31f00c2ab8d94477", "finding_id_hasher": "1",
    "slug": "fig3_panel_dup", "producer": "image_track",
    "technique": "analyze_paper_images", "computed_by": "deterministic_track",
    "title": "Figure 3: panels B and D share a duplicated region across treatment groups",
    "description": (
        "A region of Figure 3 panel B recurs in panel D, and the caption "
        "presents the two panels as different treatment groups. The image "
        "adjudicator found no innocent explanation for the repeat."
    ),
    "location": "Figure 3, panels B/D",
    "outcome": "problem", "provisional_severity": 4, "severity": 4,
    "severity_is_provisional": False, "impossible": False,  # duplication is NEVER impossible
    "quarantined": False,
    "tool_verdict": {"severity": "highly_suspicious", "tool": "analyze_paper_images",
                     "validated": True, "quarantined_raw": None},
    "inputs": {"image_adjudication": {"verdict": "unexplained", "…": "…"}},
    "anchors": [{"kind": "page_bbox", "file": "paper.pdf", "page": 6,
                 "bbox": [72.0, 401.5, 291.2, 540.0]}],
    "reproduction": "metascience image-dup …",
}

ROW_TEXT_TRACK = {
    "finding_id": "f_ab8812c4e07731fa", "finding_id_hasher": "1",
    "slug": "tortured_phrase_counterfeit", "producer": "text_track",
    "technique": "detect_tortured_phrases", "computed_by": "deterministic_track",
    "title": "Discussion uses 'counterfeit consciousness' for 'artificial intelligence'",
    "description": (
        "The Discussion uses the phrase 'counterfeit consciousness' where the "
        "field's term is 'artificial intelligence' -- the signature of "
        "paraphrase-tool rewriting. The dictionary behind this detector is a "
        "seed list, so the row is quarantined rather than accusatory."
    ),
    "location": "Discussion, para 4",
    "outcome": "problem", "provisional_severity": 2, "severity": 2,
    "severity_is_provisional": True,  # adjudicator declined to re-rank a quarantined row
    "impossible": False, "quarantined": True,
    "quarantine_reason": "Dictionary is a 51-row seed; per-phrase precision unmeasured.",
    "tool_verdict": {"severity": "indeterminate", "tool": "detect_tortured_phrases",
                     "validated": True, "quarantined_raw": "suspicious"},
    "anchors": [{"kind": "quote", "quote": "…counterfeit consciousness…"}],
    "reproduction": "metascience tortured-phrases …",
}

SPEC_ROWS = {
    "tool_expert": ROW_TOOL_EXPERT,
    "science_error": ROW_SCIENCE_ERROR,
    "image_track": ROW_IMAGE_TRACK,
    "text_track": ROW_TEXT_TRACK,
}


class TestTheSpecsExampleRowsValidate:
    @pytest.mark.parametrize("producer", sorted(SPEC_ROWS))
    def test_example_row_validates(self, producer):
        jsonschema.validate(SPEC_ROWS[producer], FINDING)

    def test_extra_properties_really_are_forbidden(self):
        """If this ever stops holding, the validations above prove nothing."""
        assert FINDING["additionalProperties"] is False
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({**ROW_TOOL_EXPERT, "invented_field": 1}, FINDING)

    def test_a_minimal_document_validates(self):
        doc = {
            "schema_version": "2.0",
            "paper_id": "10.1000--example",
            "run_id": "r_2f7c1a90",
            "findings": [ROW_TOOL_EXPERT],
            "channels": {"numeric": {"state": "ran"},
                         "image_forensics": {"state": "ran_result_discarded",
                                             "detail": "panel_index.json written, no findings retained"}},
        }
        jsonschema.validate(doc, SCHEMA)

    def test_a_channel_state_outside_the_vocabulary_is_rejected(self):
        doc = {
            "schema_version": "2.0",
            "paper_id": "10.1000--example",
            "run_id": "r_2f7c1a90",
            "findings": [],
            # 'skipped' is the kind of plausible near-synonym that erodes a
            # vocabulary -- it must be said as `did_not_run` or `refused`.
            "channels": {"numeric": {"state": "skipped"}},
        }
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate(doc, SCHEMA)


# ---------------------------------------------------------------------------
# Anti-forgery: the producer subset must reject the pipeline's fields.
# ---------------------------------------------------------------------------

#: What a producer legitimately emits for the tool_expert example: the spec
#: row minus every field a producer never writes.
SUBSET_ROW = {
    k: v for k, v in ROW_TOOL_EXPERT.items()
    if k not in ("finding_id", "finding_id_hasher", "producer", "severity",
                 "severity_is_provisional", "impossible", "tool_verdict",
                 "computed_by", "adjudication", "quarantined")
}


class TestProducerSubsetEnforcesByOmission:
    def test_a_subset_legal_row_validates(self):
        """The known positive: without it, the rejections below could just be
        a schema that rejects everything (LESSONS #4)."""
        subset = prompts.producer_findings_schema("tool_expert")
        jsonschema.validate(SUBSET_ROW, subset["properties"]["findings"]["items"])

    @pytest.mark.parametrize("field,value", [
        ("finding_id", "f_9c1e22ab34cd56ef"),
        ("severity", 3),
        ("impossible", True),
    ])
    def test_a_forged_pipeline_field_is_rejected(self, field, value):
        """A producer that can emit these can mint its own ids and verdicts."""
        subset = prompts.producer_findings_schema("tool_expert")
        item = subset["properties"]["findings"]["items"]
        assert item["additionalProperties"] is False
        with pytest.raises(jsonschema.ValidationError):
            jsonschema.validate({**SUBSET_ROW, field: value}, item)

    @pytest.mark.parametrize("field", [
        "finding_id", "finding_id_hasher", "producer", "severity",
        "severity_is_provisional", "impossible", "tool_verdict", "computed_by",
        "adjudication", "legacy", "anchor_summary",
        # anchor_problem is producer-writable by design (anchors.md section 5)
        # and therefore deliberately absent from this stripped-field list.
        "quote_verified", "quote_source", "quote_problem", "source",
        "artefacts", "reproduction_kind", "reproduction_valid",
        "reproduction_problem",
    ])
    @pytest.mark.parametrize("producer", ["tool_expert", "science_error",
                                          "image_track", "text_track",
                                          "fast_screen"])
    def test_no_excluded_field_is_reachable_from_any_producer_schema(self, producer, field):
        item = prompts.producer_findings_schema(producer)["properties"]["findings"]["items"]
        assert field not in item["properties"]
        assert field not in item["required"]

    @pytest.mark.parametrize("producer", ["tool_expert", "science_error",
                                          "image_track", "text_track",
                                          "fast_screen"])
    def test_anchor_problem_is_producer_writable(self, producer):
        """The named-absence escape hatch (anchors.md section 5): a producer
        that cannot supply a passage says WHY, rather than leaving anchors
        silently empty. Adjudicated 2026-08-21."""
        item = prompts.producer_findings_schema(producer)["properties"]["findings"]["items"]
        assert "anchor_problem" in item["properties"]
        row = {**SUBSET_ROW, "anchor_problem": "figure caption only; no verbatim span exists"}
        if "quarantined" in item["required"]:  # the track producers must declare it
            row = {**row, "quarantined": True, "quarantine_reason": "screen not yet calibrated"}
        jsonschema.validate(row, item)

    def test_web_sources_exist_only_in_the_science_agents_subset(self):
        science = prompts.producer_findings_schema("science_error")
        sweep = prompts.producer_findings_schema("tool_expert")
        for key in ("web_sources", "basis"):
            assert key in science["properties"]["findings"]["items"]["properties"]
            assert key not in sweep["properties"]["findings"]["items"]["properties"]

    def test_quarantine_keys_belong_to_the_track_builders_alone(self):
        for producer in ("image_track", "text_track"):
            item = prompts.producer_findings_schema(producer)["properties"]["findings"]["items"]
            assert "quarantined" in item["properties"]
            assert "quarantine_reason" in item["properties"]
        for producer in ("tool_expert", "science_error", "fast_screen"):
            item = prompts.producer_findings_schema(producer)["properties"]["findings"]["items"]
            assert "quarantined" not in item["properties"]

    def test_doc_level_pipeline_fields_are_stripped_too(self):
        subset = prompts.producer_findings_schema("tool_expert")
        for key in ("run_id", "paper_metadata", "channels", "adjudication",
                    "checks_tally", "provenance"):
            assert key not in subset["properties"]
        assert subset["additionalProperties"] is False

    def test_anatomy_is_required_of_the_sweep_and_optional_elsewhere(self):
        sweep = prompts.producer_findings_schema("tool_expert")
        for key in ("coverage", "anatomy", "statistics_register"):
            assert key in sweep["required"]
        science = prompts.producer_findings_schema("science_error")
        for key in ("anatomy", "statistics_register", "figures"):
            assert key not in science["required"]
            assert key in science["properties"]  # may emit, not forced to

    def test_figures_is_required_of_the_sweep_ONLY_WHEN_THE_PASS_IS_ON(self):
        """`figures` used to sit beside the other three, required
        unconditionally -- so with `--figures` off the sweep was ordered to fill
        an array whose instructions had been stripped from its prompt and whose
        tool had been removed from its allowlist. Structured-output validation
        then either rejects, or the model invents an empty shape to satisfy it.

        The other three keys are NOT conditional and must stay unconditional:
        this is a narrowing of one requirement, not a loosening of the sweep's
        obligations."""
        on = prompts.producer_findings_schema("tool_expert", figures=True)
        off = prompts.producer_findings_schema("tool_expert", figures=False)
        assert "figures" in on["required"]
        assert "figures" not in off["required"]
        assert "figures" in off["properties"], (
            "off means not DEMANDED, not forbidden -- a run that somehow read a "
            "figure must still have somewhere to put it")
        for key in ("coverage", "anatomy", "statistics_register"):
            assert key in on["required"] and key in off["required"], key

    def test_the_default_is_off(self):
        """The default must match the CLI's recorded decision, or the flag is
        decorative in the other direction."""
        assert "figures" not in prompts.producer_findings_schema(
            "tool_expert")["required"]

    def test_legacy_producers_have_no_producer_facing_schema(self):
        """Converter rows are FULL records; a subset for them would imply the
        converter is bound by it."""
        for producer in ("legacy_sweep", "legacy_editorial"):
            with pytest.raises(ValueError):
                prompts.producer_findings_schema(producer)
        with pytest.raises(ValueError):
            prompts.producer_findings_schema("no_such_producer")

    def test_the_subset_does_not_mutate_the_cached_full_schema(self):
        """`producer_findings_schema` deep-copies; without that, the first
        subset call would strip `finding_id` out of `findings_schema_v2()` for
        every later caller."""
        prompts.producer_findings_schema("tool_expert")
        full_item = prompts.findings_schema_v2()["properties"]["findings"]["items"]
        assert "finding_id" in full_item["properties"]
        anchors = full_item["properties"]["anchors"]["items"]
        assert anchors["additionalProperties"] is True


# ---------------------------------------------------------------------------
# Anti-drift: the technique enum is the registry plus exactly six values.
# ---------------------------------------------------------------------------

#: Transcribed from spec section 1.2 -- deliberately NOT imported from
#: prompts.NON_TOOL_TECHNIQUES, so drift in the module constant is caught too.
SPEC_NON_TOOL_VALUES = [
    "not_computational", "no_tool_exists", "tool_existed_unused",
    "legacy_unattributed", "factual_claim", "internal_contradiction",
]


class TestTechniqueEnumTracksTheRegistry:
    def test_enum_is_registry_names_plus_the_six(self):
        # Minus the infrastructure set: a finding cites the CHECK its numbers
        # went through, never the reader that fetched them (registry.
        # NON_TECHNIQUE_TOOLS is the register of record).
        enum = FINDING["properties"]["technique"]["enum"]
        expected = sorted(s.name for s in registry.SPECS
                          if s.name not in registry.NON_TECHNIQUE_TOOLS)
        assert enum == expected + SPEC_NON_TOOL_VALUES

    def test_the_infrastructure_set_is_infrastructure(self):
        """Every excluded name is an extraction/parsing reader, the code
        runner, or a tool whose verdicts the harness files -- never a check
        whose result only the model can report."""
        for name in registry.NON_TECHNIQUE_TOOLS:
            assert name.startswith(("extract_", "get_", "parse_", "list_")) \
                or name == "run_python_script" \
                or name in registry.HARNESS_FILED_TOOLS, name
        assert "grim_check" not in registry.NON_TECHNIQUE_TOOLS

    def test_the_placeholder_did_not_leak(self):
        assert not any(v.startswith("__") for v in
                       FINDING["properties"]["technique"]["enum"])

    def test_v1s_manual_is_retired(self):
        """The converter maps it per the 2026-08-13 split; new rows never use it."""
        assert "manual" not in FINDING["properties"]["technique"]["enum"]

    def test_the_raw_file_refuses_to_validate_a_real_technique(self):
        """The file alone is deliberately not a usable schema: bypassing
        `findings_schema_v2()` must fail loudly, not validate against a stale
        hand-maintained list."""
        raw = json.loads(prompts.findings_schema_v2_path().read_text())
        raw_enum = raw["properties"]["findings"]["items"]["properties"]["technique"]["enum"]
        assert raw_enum == ["__TECHNIQUE_ENUM_INJECTED_AT_LOAD__"]


class TestProducerVocabulary:
    def test_fast_screen_is_in_the_producer_enum_from_day_one(self):
        assert "fast_screen" in FINDING["properties"]["producer"]["enum"]

    def test_the_schema_and_the_module_agree_on_the_producer_list(self):
        assert tuple(FINDING["properties"]["producer"]["enum"]) == prompts.PRODUCERS
        assert len(prompts.PRODUCERS) == 9   # harness, 2026-10-18


class TestChannelVocabularyHasOneHome:
    def test_channel_states_match_webapp_index_exactly(self):
        schema_states = SCHEMA["properties"]["channels"]["additionalProperties"][
            "properties"]["state"]["enum"]
        assert tuple(schema_states) == CHANNEL_STATES


# ---------------------------------------------------------------------------
# v1 is untouched: the live pipeline keeps consuming exactly what it did.
# ---------------------------------------------------------------------------

#: sha256 of findings.schema.json as measured 2026-08-21, the day v2 was added
#: beside it. A deliberate v1 edit updates this pin; the point is that v2 work
#: can never BE that edit silently. RE-PINNED at the 2026-08-21
#: stacked-headers merge: Greg's branch legitimately evolved the v1 schema
#: (censored values, prose-value fields) -- that is a legacy-pipeline edit,
#: exactly the deliberate kind this pin exists to make visible.
#:
#: RE-PINNED 2026-08-22 for `effect_size_from_f`. The v1 ACCESSOR extends this
#: file's enum with every registry name at load time, so the new tool was
#: already nameable in a v1 finding without the edit -- but
#: `test_every_check_can_be_named` reads the FILE, deliberately, as the ratchet
#: that stops a new tool being unnameable. The tool is STAGE1-reachable, so a
#: legacy sweep really can produce a finding naming it: a legacy-pipeline edit,
#: made visibly.
#:
#: RE-PINNED 2026-08-29 for the `statistic_value` description. The field was a
#: bare `{"type": "number"}` with no instruction, beside an `effect_size` that
#: carries an explicit one -- and the model duly filled it with Wald z's it
#: computed itself (2.658 = 1.01/0.38 on ajcp.70049, absent from the article).
#: A legacy-pipeline edit, made visibly. THE SAME DESCRIPTION WAS ADDED TO
#: findings.v2.schema.json IN THE SAME CHANGE: v2 is what the parallel path
#: writes, and fixing only v1 is the exact shape of the defect recorded in
#: CLAUDE.md section 8c -- a capability that existed and did not come across
#: when the path changed.
#:
#: RE-PINNED 2026-08-29 (second time today) for description-only edits to
#: `df`, `p_value`, `n` and both scale bounds. Each was a bare type sitting
#: beside fields that carry an as-printed instruction -- the same channel
#: `statistic_value` had, where the model filled a printed-reading field with
#: its own arithmetic. `df` is the sharpest: `rulebook.md` documents the exact
#: false accusation an inferred df produces, and the field where an inferred
#: one would land is indistinguishable from a printed one.
#:
#: THE SAME TEXT WENT INTO findings.v2.schema.json IN THE SAME CHANGE. v2 is
#: what the parallel path writes; editing only v1 is the defect class recorded
#: in CLAUDE.md section 8c.
V1_FILE_SHA256 = "8fd774680b07b7370c769d82db390f5bfd8e6de9a27d7e7f365cd4601f0a9173"


