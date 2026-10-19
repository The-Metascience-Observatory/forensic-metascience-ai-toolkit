"""The scaffold schema: the contract for each pass and for the merged account.

THE DESIGN QUESTION. Two consumers want the same description of a paper and
would, left to themselves, organise it in opposite ways.

  A READER wants the paper's own organisation: per experiment, what was done, to
  whom, what was measured, what came out, what the authors say it means. Values
  belong in the table or figure they were printed in. Prose is fine.

  A CHECK wants a relational shape: which mean goes with which n, whether that n
  is the denominator of this percentage, what the variable's bounds are, and it
  wants to find all of that by KEY, not by reading. A check must be able to say
  "every (mean, n) pair for an integer-scored variable with stated bounds" and get
  a finite list, deterministically, so that the set of valid checks is a function
  of the scaffold's composition and nothing else.

THE RESOLUTION: a normalised core and projected views. The core is a small set
of entity tables joined by human-readable ids, and every VALUE is a row at a
COORDINATE:

    (study_id, group_id, phase_id, variable_id, statistic)

The reader's view is a projection: group the rows by study, pivot a table's rows
back into the table's own layout, list the claims under the studies they rest
on. Nothing is stored twice; the rendering is a function of the rows, so it
cannot disagree with them. The ids are readable on purpose (`var:pct_freezing`,
`grp:igf2_30`, `phase:test_24h`) so that the JSON is itself legible and a person
checking a row against the paper does not have to dereference anything.

WHAT A COORDINATE BUYS. A percentage at (study, group, phase, var) and an n at
(study, group) join on their shared keys; `check_count_percent` binds to the
join. A mean at a coordinate joins to its variable's `granularity` and to the n
at its group; GRIM binds when all three are present and refuses, naming the
missing key, when they are not. There is no guessing step in between, and the
absence of a premise is a named row in `gaps`, not a default.

THE THREE PASS SCHEMAS BELOW are what the model is asked for, in order. They are
deliberately NOT the merged account: pass 1 describes studies in words and names
groups and phases; pass 2 turns the words into typed variables with levels and
binds the groups to levels; pass 3 reads the tables and prose IN TERMS of those
ids. The model never transcribes a table number -- cells come from the walker and
pass 3 supplies only the READING of the table (which column is which coordinate,
which row is which variable, what statistic form the cells take). Code applies
the reading to the cells. That is invariant 2 (a derived structure may narrow a
premise, never supply one) applied to extraction: a wrong reading costs
coverage, and the cell values themselves are never the model's to get wrong.

NOT STATED IS AN ANSWER. Every field whose value the paper may not give is
nullable and, where it matters for a check, carries a companion `*_source` enum
with `not_stated` as a member. The prompt instructs the model that a null with
the right source is correct and a plausible fill is a defect.
"""

from __future__ import annotations

import copy
import re
from typing import Any, Iterable

# --------------------------------------------------------------------------
# JSON-schema helpers -- a small vocabulary, so every pass schema reads alike.
# --------------------------------------------------------------------------


def _s(description: str = "") -> dict:
    d: dict[str, Any] = {"type": "string"}
    if description:
        d["description"] = description
    return d


def _n(description: str = "") -> dict:
    d: dict[str, Any] = {"type": "number"}
    if description:
        d["description"] = description
    return d


def _b(description: str = "") -> dict:
    d: dict[str, Any] = {"type": "boolean"}
    if description:
        d["description"] = description
    return d


def _nullable(schema: dict, description: str = "") -> dict:
    d: dict[str, Any] = {"anyOf": [schema, {"type": "null"}]}
    if description:
        d["description"] = description
    return d


def _enum(values: list[str], description: str = "") -> dict:
    d: dict[str, Any] = {"type": "string", "enum": list(values)}
    if description:
        d["description"] = description
    return d


def _arr(items: dict, description: str = "") -> dict:
    d: dict[str, Any] = {"type": "array", "items": items}
    if description:
        d["description"] = description
    return d


def _obj(properties: dict, required: list[str] | None = None,
         description: str = "") -> dict:
    d: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "required": list(required if required is not None else properties.keys()),
        "additionalProperties": False,
    }
    if description:
        d["description"] = description
    return d


QUOTE = _s("A verbatim, contiguous span of the paper's text that establishes "
           "this. It is verified against the text automatically; a span the "
           "paper did not print is recorded as such. Never paraphrase here.")

# --------------------------------------------------------------------------
# Controlled vocabularies. Small, and each member is a distinction a check or a
# reader needs -- not a taxonomy for its own sake.
# --------------------------------------------------------------------------

#: What a variable IS in the design. `manipulated_factor` has levels the
#: experimenter set; `measured_outcome` is what came out; `derived_outcome` is
#: computed from other measurements by a stated formula; `design_parameter` is a
#: fixed setting of the procedure (shock intensity, session length) -- a value the
#: paper reports that is not an outcome and not a factor, and which a reader needs
#: to understand the study. `time` is the within-subject axis (test 1 / test 2,
#: 24 h / 7 d). `blocking` is a variable held fixed or counterbalanced.
VARIABLE_ROLES = ("manipulated_factor", "measured_outcome", "derived_outcome",
                  "design_parameter", "time", "covariate", "blocking",
                  "population_descriptor")

#: What kind of number the variable produces PER UNIT OF OBSERVATION. This, with
#: `granularity`, is what a granularity check needs. `percentage_of_observations`
#: is a percentage whose per-subject value is k/K for a fixed K (freezing scored
#: every 10 s over 3 min gives K = 18); `percentage_of_time` is a continuous
#: proportion; `percentage_of_subjects` is a group-level count over the group n.
VARIABLE_KINDS = ("continuous", "count", "integer_score", "binary",
                  "categorical", "ordinal", "percentage_of_observations",
                  "percentage_of_time", "percentage_of_subjects",
                  "percentage_of_reference", "proportion", "duration",
                  "mass", "concentration", "temperature", "rate", "other")

BOUND_SOURCES = ("stated", "definitional", "not_stated")

#: What a value row IS. `n_range` is a sample size printed as a range across
#: groups (`n = 6-9`), which is a real and common way for a paper to report n
#: and is NOT a per-group n; nothing that needs a per-group n may bind to it.
STATISTICS = ("mean", "sem", "sd", "dispersion_unstated", "median", "iqr", "n",
              "n_range", "count", "percentage", "proportion", "min", "max", "range",
              "dose", "duration", "timepoint", "threshold", "p_value", "p_threshold",
              "test_statistic", "df", "effect_size", "ci_lower", "ci_upper",
              "ratio", "rate", "setting", "other",
              # from the tidy table reading (reconstruct.TIDY_STATISTICS)
              "coefficient", "se", "score")

SIGNIFICANCE = ("significant", "not_significant", "trend", "not_reported")
#: CLOSED, because a free-text direction drifted between two readings of the
#: same paper (2026-09-06: "Positive: more inclusive leadership went with more
#: EBPs" vs "Positive."). `first`/`second` refer to the ORDER of
#: `contrast.group_ids` / `phase_ids`; `positive`/`negative` are for an
#: association or coefficient; the words go in `direction_words`.
DIRECTIONS = ("first_higher", "second_higher", "positive", "negative",
              "no_difference", "not_stated")
#: WHERE a comparison is reported, closed. A comparison is a result the paper
#: REPORTS with evidence; a sentence in the abstract or discussion that restates
#: one without a printed statistic, p or threshold is a CLAIM and is demoted to
#: one by `bind` (2026-09-06: 15 of a linear pass's 24 comparisons were such
#: restatements).
REPORTED_IN_KINDS = ("results_text", "table", "figure", "supplement", "methods",
                     "abstract", "discussion")

CLAIM_KINDS = ("finding", "mechanism", "safety", "translational", "method",
               "background", "limitation")

CLAIM_LOCATIONS = ("title", "abstract", "introduction", "results",
                   "discussion", "conclusion", "figure_caption")

#: TEST FAMILIES, enumerated. Greg (2026-09-05): every field where consistency
#: matters is a choice from a stated set or a number with a unit, never free
#: prose, because a free-text `test` field is phrased differently on every run
#: and everything downstream is then conditioned on which run you got. The
#: paper's own wording goes in `test_type_quote`, which is verbatim and cannot
#: drift. `other` is allowed and is a signal that the set is incomplete.
#:
#: Six members were added 2026-09-11, reconciling this enum with
#: `anatomy.TEST_ASSUMPTIONS` -- the vocabulary the assumption checker keys on,
#: which has known, auditable entries for all six while this enum offered no
#: member for any of them. A paper running an ANCOVA, McNemar's test, a Cox
#: regression or a log-rank test had to be recorded as `other`, and a Pearson
#: correlation or a Wilcoxon signed-rank test could only be recorded under the
#: ambiguous `correlation` / `wilcoxon`: the account could not say what the
#: paper plainly said. Note the ambiguous members STAY -- they are the honest
#: answer when the paper does not say which test it ran. The two lists are now
#: reconciled by a test (`TestTheTwoTestVocabulariesCoverTheSameUniverse`), so
#: neither can drift away from the other silently again.
TEST_FAMILIES = ("t_test_independent", "t_test_paired", "t_test_unspecified",
                 "one_way_anova", "two_way_anova", "repeated_measures_anova",
                 "mixed_anova", "anova_unspecified", "ancova", "chi_squared",
                 "fisher_exact", "mcnemar", "mann_whitney", "wilcoxon",
                 "wilcoxon_signed_rank", "kruskal_wallis", "correlation",
                 "pearson_correlation", "linear_regression",
                 "logistic_regression", "mixed_model", "cox_regression",
                 "log_rank", "survival", "other")

POST_HOC = ("dunnett", "newman_keuls", "bonferroni", "tukey", "sidak", "holm",
            "fdr", "lsd", "scheffe", "other", "none_stated")

#: DESIGN TEMPLATES: which parts of a study a design type REQUIRES. Two runs
#: may then disagree about values, never about the shape of the account, and a
#: study whose declared design does not match its parts is flagged by
#: `bind` (`template_problems`) rather than silently accepted. Greg: "It might
#: need templates for common study designs."
DESIGN_TEMPLATES: dict[str, dict] = {
    "between_subjects": {"min_groups": 2, "min_phases": 0, "needs_numeric_factor": False},
    "within_subjects": {"min_groups": 1, "min_phases": 2, "needs_numeric_factor": False},
    "mixed": {"min_groups": 2, "min_phases": 2, "needs_numeric_factor": False},
    "dose_response": {"min_groups": 3, "min_phases": 0, "needs_numeric_factor": True},
    "descriptive": {"min_groups": 1, "min_phases": 0, "needs_numeric_factor": False},
    # HUMAN AND OBSERVATIONAL DESIGNS (2026-09-06). The first JATS paper was a
    # two-wave panel of 64 coalitions; every one of its 8 studies had to be
    # forced into the animal-lab vocabulary above. A closed vocabulary that
    # lacks the paper's design invites `other`, which no template can check.
    "parallel_rct": {"min_groups": 2, "min_phases": 0, "needs_numeric_factor": False},
    "crossover": {"min_groups": 1, "min_phases": 2, "needs_numeric_factor": False},
    "pre_post": {"min_groups": 1, "min_phases": 2, "needs_numeric_factor": False},
    "longitudinal_panel": {"min_groups": 1, "min_phases": 2, "needs_numeric_factor": False},
    "cross_sectional": {"min_groups": 1, "min_phases": 0, "needs_numeric_factor": False},
    "cohort": {"min_groups": 1, "min_phases": 1, "needs_numeric_factor": False},
    "case_control": {"min_groups": 2, "min_phases": 0, "needs_numeric_factor": False},
    "other": {"min_groups": 0, "min_phases": 0, "needs_numeric_factor": False},
}

#: Every disposition a numeral in the analytic text can have. `unaccounted` is
#: the honest residual: a number nobody has judged yet. It is a state, not a
#: failure, and it is reported rather than dropped.
#: PLACEMENT HAS THREE OUTCOMES, NOT TWO (Greg, 2026-09-05). `value` is PLACED
#: at one coordinate; `ambiguous` means the value plausibly belongs to two or
#: more coordinates and the paper does not settle which -- the candidate list
#: is emitted with what would distinguish them, which a human adjudicates in
#: seconds; `unaccounted` is UNPLACED: no coordinate in the scaffold fits, with
#: the reason. A binary design forces every genuinely ambiguous value into a
#: guess or a silence, and both lose information.
NUMERAL_DISPOSITIONS = ("value", "ambiguous", "design_parameter", "sample_size",
                        "axis_tick", "citation_year", "citation_page",
                        "figure_or_table_ref", "panel_or_item_label",
                        "coordinate_label", "section_or_list_number", "date_or_id",
                        "affiliation", "unit_or_catalog", "textual_count",
                        "duplicate_of_value", "unaccounted")

# --------------------------------------------------------------------------
# PASS 1 -- comprehension
# --------------------------------------------------------------------------


def pass1_schema() -> dict:
    """What a careful reader knows after one full read: the argument, the
    experiments, who was in them, what was measured in words, what was found in
    the authors' words, and what they claim it means. No typing yet, no numbers
    beyond the sample sizes and doses the design is described by."""
    group = _obj({
        "id": _s("`grp:<slug>` -- short, readable, unique within the study."),
        "label": _s("The paper's own label for this group, e.g. `IGF-II 30 µg/kg`."),
        "description": _s("What distinguishes this group: treatment, dose, "
                          "timing, antibody, training state."),
        "n_printed": _nullable(_s(), "The n AS PRINTED for this group, e.g. `8`, "
                               "or null when the paper gives only a range across "
                               "groups or nothing. Do not resolve a range."),
        "n_quote": _nullable(QUOTE),
    })
    phase = _obj({
        "id": _s("`phase:<slug>` -- the within-subject occasion: a test, a "
                 "timepoint, an extinction trial, a training block."),
        "label": _s(),
        "when": _s("When it occurs relative to the anchor event, in the paper's "
                   "words, e.g. `24 h after training`."),
    })
    reported_in = _obj({
        "kind": _enum(["figure", "table", "prose", "supplement"]),
        "label": _s("`Figure 1`, `Table 1`, `Supplementary Figure S2`."),
        "panels": _arr(_s(), "Panel letters, e.g. [\"a\"], or empty."),
    })
    study = _obj({
        "id": _s("`study:<slug>`. One study per experiment the paper reports as "
                 "a unit -- usually one figure panel or one panel group with a "
                 "shared design. Split rather than lump when the groups differ."),
        "label": _s("A one-line human label."),
        "aim": _s("The question this experiment answers, in one sentence."),
        "section_heading": _s("The Results subsection heading it is reported under."),
        "reported_in": _arr(reported_in),
        "design_type": _enum(list(DESIGN_TEMPLATES),
                             "One of the design templates. `longitudinal_panel` for "
                             "the same units measured at waves; `cross_sectional` for "
                             "one occasion; `parallel_rct` / `crossover` / `pre_post` "
                             "for trials; `cohort` / `case_control` for observational "
                             "epidemiology; `other` ONLY when none fits."),
        "design_description": _s("The comparison structure in words: what is "
                                 "compared with what, across which occasions."),
        "n_range_printed": _nullable(_s(), "A sample size printed as a RANGE "
                                     "across groups, e.g. `6–9`, as printed."),
        "n_range_quote": _nullable(QUOTE),
        "n_scope": _enum(["per_group", "per_group_range", "total", "unclear", "not_stated"],
                         "WHAT the printed n refers to. `per_group`: the paper says or "
                         "its convention makes plain that the figure is per group (then "
                         "fill each group's `n_printed`). `per_group_range`: a range "
                         "across groups (`n_range_printed`). `total`: one figure for all "
                         "subjects together. `unclear`: a single figure, e.g. `(n = 7)` "
                         "in a caption, that the paper does not say is per group or "
                         "total -- record it in `n_range_printed` as the bare string and "
                         "leave the groups' `n_printed` null. MEASURED 2026-09-05 on two "
                         "runs of the same paper: every one of nine study-level "
                         "disagreements was this figure read per-group once and as a "
                         "study total once; the printed string agreed each time."),
        "groups": _arr(group),
        "phases": _arr(phase),
        "outcomes_described": _arr(_s(), "Each outcome measured, in words, one "
                                   "per entry, e.g. `percentage of time freezing`."),
        "manipulations_described": _arr(_s(), "Each manipulated factor, in words."),
        "result_summary_quotes": _arr(QUOTE, "The sentences in Results that "
                                      "state what was found, verbatim."),
        "interpretation_quotes": _arr(QUOTE, "The sentences where the authors "
                                      "say what the result means, verbatim."),
        "procedure_ids": _arr(_s(), "`proc:` ids from `procedures`."),
    })
    claim = _obj({
        "id": _s("`claim:<n>`"),
        "text": QUOTE,
        "location": _enum(list(CLAIM_LOCATIONS)),
        "kind": _enum(list(CLAIM_KINDS)),
        "study_ids": _arr(_s(), "Studies whose results this claim rests on. "
                          "Empty for background claims."),
        "hedged": _b("Does the sentence hedge (`may`, `suggest`, `appears`)?"),
        "generalizes_beyond_sample": _b("Does it extend to a population the "
                                        "study did not sample, e.g. humans?"),
        "causal": _b("Does it assert a causal mechanism?"),
    })
    procedure = _obj({
        "id": _s("`proc:<slug>`"),
        "name": _s(),
        "section_heading": _s("The Methods subsection that describes it."),
        "summary": _s("Two sentences: what the animal/participant does and what "
                      "is recorded."),
        "scored_blind": _nullable(_b(), "Does the paper say the scorer was blind "
                                  "to condition? null when it does not say."),
    })
    legend = _obj({
        "marker": _s("`*`, `**`, `***`, `n.s.`"),
        "threshold": _nullable(_n(), "The p threshold the marker denotes."),
        "quote": QUOTE,
    })
    aim = _obj({"id": _s("`aim:<n>`"), "text": _s(), "quote": QUOTE})
    prior = _obj({"statement": _s(), "cited_as": _s("The citation as printed.")})
    supplement = _obj({
        "label": _s("`Supplementary Table S1`"),
        "referenced_for": _s("What the paper says is there."),
        "quote": QUOTE,
    })
    return _obj({
        "paper": _obj({
            "title": _s(), "authors": _arr(_s()), "journal": _nullable(_s()),
            "year": _nullable(_n()), "doi": _nullable(_s()),
            "species_or_population": _s(),
        }),
        "background": _obj({
            "problem": _s("The problem the paper addresses, one or two sentences."),
            "prior_findings": _arr(prior),
            "gap": _s("What was not known that this paper tests."),
            "aims": _arr(aim),
        }),
        "subjects": _obj({
            # WHO OR WHAT THE UNITS ARE. Animal fields and human/organizational
            # fields side by side, each null when the paper does not say; a
            # community-coalition study fills `population` and
            # `unit_of_analysis` and leaves `species` null, and the renderer
            # prints only what is filled.
            "population": _nullable(_s(), "Who or what the units are, as printed: "
                                    "`64 community coalitions`, `undergraduates`, "
                                    "`adults with type 2 diabetes`."),
            "unit_of_analysis": _nullable(_s(), "What one n counts: a mouse, a "
                                          "participant, a coalition, a school."),
            "setting": _nullable(_s(), "Where: country, region, institution type."),
            "recruitment": _nullable(_s(), "How units entered the study, as printed."),
            "eligibility": _nullable(_s(), "Inclusion/exclusion rules, as printed."),
            "species": _nullable(_s()), "strain": _nullable(_s()),
            "sex": _nullable(_s()), "age": _nullable(_s()),
            "supplier": _nullable(_s()), "housing": _nullable(_s()),
            "total_n_stated": _b("Does the paper state a total number of "
                                 "subjects anywhere?"),
            "quote": QUOTE,
        }),
        "statistical_analysis": _obj({
            "methods_quote": QUOTE,
            "tests_named": _arr(_s(), "Each test family named, one per entry."),
            "alpha_declared": _nullable(_n(), "ONLY if the paper declares a "
                                        "significance threshold in words. The "
                                        "legend's lowest star is NOT a declaration."),
            "alpha_quote": _nullable(QUOTE),
            "significance_legend": _arr(legend),
            "detailed_statistics_location": _nullable(_s(), "Where the paper says "
                                                      "full test statistics live, "
                                                      "if not in the main text."),
            "test_to_experiment_mapping_in_main_text": _b(
                "Does the main text say WHICH test was used for WHICH experiment?"),
        }),
        "procedures": _arr(procedure),
        # PAPER-LEVEL OCCASIONS (2026-09-06). Phases were per-study (an
        # experiment's test occasions); a two-wave survey's waves belong to the
        # whole paper, and Methods-level values naming `phase:wave1` had no
        # study to resolve against -- 9 integrity problems on the first JATS
        # run. A study whose occasions ARE the paper's leaves its own `phases`
        # empty; `validate_account` accepts a paper-level id anywhere.
        "phases": _arr(phase, "Occasions the WHOLE paper is organized by: survey "
                              "waves, visits, follow-up years, semesters. Empty when "
                              "every occasion belongs to one study."),
        "studies": _arr(study),
        "claims": _arr(claim),
        "supplements_referenced": _arr(supplement),
    })


# --------------------------------------------------------------------------
# PASS 2 -- variables and their characteristics
# --------------------------------------------------------------------------


def pass2_schema() -> dict:
    """Every variable, typed; every factor's levels; every group bound to its
    levels; every design parameter with its value. This is the layer the checks
    read their premises from, so its rule is the strictest: a bound, a unit, a
    granularity or a level that the paper does not state is null with
    `not_stated`, never a plausible fill."""
    level = _obj({
        "id": _s("`lvl:<slug>`"),
        "label": _s("As the paper names it."),
        "value": _nullable(_n(), "The numeric value when the level is a number "
                           "(a dose, a timepoint)."),
        "units": _nullable(_s()),
    })
    bounds = _obj({
        "lower": _nullable(_n()),
        "upper": _nullable(_n()),
        "source": _enum(list(BOUND_SOURCES),
                        "`stated`: the paper prints the bound (quote it). "
                        "`definitional`: the bound follows from the variable's "
                        "definition in the paper (a percentage is 0-100; a score "
                        "defined as 0-15 in Methods). `not_stated`: neither."),
        "quote": _nullable(QUOTE),
    })
    granularity = _obj({
        "per_subject_step": _nullable(_n(), "The smallest step a SINGLE subject's "
                                      "value can take, when the paper's definition "
                                      "fixes it: 1 for an integer score; 100/K for "
                                      "a percentage of K discrete observations. "
                                      "null when continuous or not derivable."),
        "basis": _nullable(_s(), "How the step follows from the paper's "
                           "definition, or why it does not."),
        "quote": _nullable(QUOTE),
    })
    variable = _obj({
        "id": _s("`var:<slug>`"),
        "name": _s(),
        "role": _enum(list(VARIABLE_ROLES)),
        "kind": _enum(list(VARIABLE_KINDS)),
        "units": _nullable(_s(), "As printed. null when the paper prints none, "
                           "even when the unit is obvious."),
        "units_source": _enum(["stated", "not_stated"]),
        "bounds": bounds,
        "granularity": granularity,
        "derivation": _nullable(_s(), "The formula in the paper's words, when the "
                                "variable is computed from others."),
        "derived_from": _arr(_s(), "Variable ids or measured quantities it is "
                             "computed from."),
        "procedure_id": _nullable(_s(), "`proc:` id of the instrument or task."),
        # A CLOSED FIELD, AND A CLAIM THAT IS RE-DERIVED RATHER THAN BELIEVED.
        # `interpret.verified_aliases` checks every label here against the row
        # labels the TABLE EXTRACTOR read, before any model saw the table; one
        # that matches nothing printed corroborates nothing, and one two
        # variables claim binds neither.
        "printed_as": _arr(_s(), "Every label the paper PRINTS this variable under in a "
                           "table row stub or column header, VERBATIM and in full -- e.g. "
                           "`Externally funded` for a variable named `External funding "
                           "indicator`. Empty when the paper prints it only under its own "
                           "name. Do not invent a plausible label: each one is checked "
                           "against the labels the table extractor actually read, and one "
                           "the paper does not print counts for nothing."),
        "levels": _arr(level, "For factors and time axes: every level, in order."),
        "studies_using": _arr(_s(), "`study:` ids."),
        "quote": QUOTE,
        "notes": _nullable(_s()),
    })
    group_coord = _obj({
        "study_id": _s(), "group_id": _s(),
        "assignments": _arr(_obj({"variable_id": _s(), "level_id": _s()}),
                            "One entry per manipulated factor: which level this "
                            "group received."),
    })
    phase_coord = _obj({
        "study_id": _s(), "phase_id": _s(),
        "variable_id": _s("The `time` variable this phase is a level of."),
        "level_id": _s(),
    })
    parameter = _obj({
        "procedure_id": _s(),
        "variable_id": _nullable(_s(), "`var:` id when this parameter is also "
                                 "registered as a design_parameter variable."),
        "name": _s(),
        "printed": _s("The value AS PRINTED, e.g. `0.7`."),
        "numeric": _nullable(_n()),
        "units": _nullable(_s()),
        "quote": QUOTE,
    })
    outcome_binding = _obj({
        "study_id": _s(),
        "variable_ids": _arr(_s(), "The measured/derived outcome variables of "
                             "this study."),
    })
    return _obj({
        "variables": _arr(variable),
        "group_coordinates": _arr(group_coord),
        "phase_coordinates": _arr(phase_coord),
        "procedure_parameters": _arr(parameter),
        "outcome_bindings": _arr(outcome_binding),
        "population_descriptors": _arr(_obj({
            "name": _s(), "printed": _s(), "numeric": _nullable(_n()),
            "units": _nullable(_s()), "quote": QUOTE,
        }), "Age, weight, sex ratio -- descriptors of the sample as a whole."),
    })


# --------------------------------------------------------------------------
# PASS 3 -- values, in terms of the structure
# --------------------------------------------------------------------------


def pass3_schema() -> dict:
    """The reading of every table (not its numbers), every value in prose and
    captions located at a coordinate, every comparison the paper reports, and
    the figure panels as a map of what is drawn where."""
    column_map = _obj({
        "col_label": _s("The column label EXACTLY as given in the cells list."),
        "study_id": _nullable(_s()),
        "group_id": _nullable(_s()),
        "phase_id": _nullable(_s()),
    })
    row_map = _obj({
        "row_label": _s("The row label EXACTLY as given in the cells list."),
        "variable_id": _nullable(_s(), "null when no variable fits -- say why in "
                                 "`note`, do not force one."),
        "statistic_form": _enum(["mean_pm_sem", "mean_pm_sd", "mean_pm_unstated",
                                 "percentage_of_subjects", "count", "median_iqr",
                                 "single_value", "text", "other"],
                                "What the cells in this row ARE. `mean_pm_unstated` "
                                "when the table prints `x (±y)` and says nowhere "
                                "whether y is SEM or SD."),
        "dispersion_stated_where": _nullable(_s(), "Where the paper says what the "
                                             "± is for THIS table, if anywhere."),
        "note": _nullable(_s()),
    })
    table_reading = _obj({
        "table_id": _s("EXACTLY the id given in the tables list."),
        "caption": _nullable(QUOTE),
        "n_per_column_stated": _b("Does the table or its caption/footnote state "
                                  "the n behind each column?"),
        "n_note": _nullable(_s()),
        "column_map": _arr(column_map),
        "row_map": _arr(row_map),
    })
    coordinate = _obj({
        "study_id": _nullable(_s()),
        "group_id": _nullable(_s()),
        "phase_id": _nullable(_s()),
    })
    prose_value = _obj({
        "id": _s("`val:<slug>`"),
        "variable_id": _nullable(_s()),
        "statistic": _enum(list(STATISTICS)),
        "printed": _s("EXACTLY as printed, including a range like `6–9`."),
        "numeric": _nullable(_n(), "The number, when `printed` is a single number."),
        "units": _nullable(_s()),
        "coordinate": coordinate,
        "applies_to_all_groups": _b("True for an n or a setting the sentence "
                                    "gives for every group at once."),
        "quote": QUOTE,
        "location": _enum(["abstract", "methods", "results", "discussion",
                           "figure_caption", "table_caption", "table_footnote"]),
        "note": _nullable(_s()),
    })
    contrast = _obj({
        "group_ids": _arr(_s()),
        "phase_ids": _arr(_s()),
        "description": _s("What is compared with what, in words."),
    })
    comparison = _obj({
        "id": _s("`cmp:<slug>`"),
        "study_id": _s(),
        "outcome_variable_id": _nullable(_s()),
        "contrast": contrast,
        "test_type_stated": _nullable(_enum(list(TEST_FAMILIES)),
                                      "The test the paper names FOR THIS comparison, "
                                      "as a member of the stated set. null when Methods "
                                      "lists tests without saying which applies here."),
        "test_type_quote": _nullable(QUOTE),
        "post_hoc_stated": _nullable(_enum(list(POST_HOC)),
                                     "The post hoc procedure named for THIS comparison."),
        "statistic_printed": _nullable(_s()),
        "df_printed": _nullable(_s()),
        "p_printed": _nullable(_s(), "An exact p as printed, or null."),
        "p_threshold": _nullable(_n(), "When the result is given only as a star "
                                 "or `P<0.05`: the threshold."),
        "significance": _enum(list(SIGNIFICANCE)),
        "direction": _enum(list(DIRECTIONS),
                           "`first_higher`/`second_higher` by the ORDER of the contrast's "
                           "group_ids/phase_ids; `positive`/`negative` for an association "
                           "or coefficient; `no_difference` when the paper says so; "
                           "`not_stated` when the sentence gives no direction."),
        "direction_words": _nullable(_s(), "The paper's own words for the direction."),
        "reported_in_kind": _enum(list(REPORTED_IN_KINDS),
                                  "A comparison must carry a printed statistic, an exact p "
                                  "or a threshold. A sentence in the abstract or discussion "
                                  "that restates a result without one is a CLAIM, not a "
                                  "comparison -- do not list it here."),
        "reported_in": _s("`Figure 1a`, `Table 1`, `Results text`."),
        "quote": QUOTE,
        "detailed_statistics_elsewhere": _nullable(_s(), "Where the full "
                                                   "statistics are said to be."),
    })
    panel = _obj({
        "figure": _s("`Figure 1`"),
        "panel": _s("`a`"),
        "study_id": _nullable(_s()),
        "y_variable_id": _nullable(_s()),
        "group_ids": _arr(_s()),
        "phase_ids": _arr(_s()),
        "n_printed": _nullable(_s(), "The n the caption gives for this panel, as printed."),
        "error_bar": _nullable(_s(), "`SEM`, `SD`, or null when the caption does not say."),
        "caption_quote": QUOTE,
    })
    return _obj({
        "table_readings": _arr(table_reading),
        "prose_values": _arr(prose_value),
        "comparisons": _arr(comparison),
        "figure_panels": _arr(panel),
    })


# --------------------------------------------------------------------------
# PASS 3b -- the residual: every numeral not yet accounted for
# --------------------------------------------------------------------------


def placement_candidate_schema() -> dict:
    """One candidate coordinate for an AMBIGUOUS numeral."""
    return _obj({
        "study_id": _nullable(_s()),
        "group_id": _nullable(_s()),
        "phase_id": _nullable(_s()),
        "variable_id": _nullable(_s()),
        "statistic": _nullable(_enum(list(STATISTICS))),
        "why": _s("Why this coordinate is plausible, from the sentence."),
    })


def disposition_row_schema(id_description: str = "EXACTLY the id given.") -> dict:
    """One numeral's placement outcome: placed (`value`), `ambiguous` with the
    candidate list, or unplaced (`unaccounted`) with the reason."""
    return _obj({
        "numeral_id": _s(id_description),
        "disposition": _enum(list(NUMERAL_DISPOSITIONS)),
        "value_id": _nullable(_s(), "When disposition is `value` or "
                              "`duplicate_of_value`: the `val:` id it belongs to, "
                              "or a NEW `val:` id you define in `new_values`."),
        "candidates": _arr(placement_candidate_schema(),
                           "REQUIRED non-empty when disposition is `ambiguous`: every "
                           "coordinate the value could belong to. Empty otherwise."),
        "distinguisher": _nullable(_s(), "For `ambiguous`: what in the paper would "
                                   "settle it, and why it is absent."),
        "note": _nullable(_s(), "For `unaccounted`: WHY no coordinate fits."),
    })


def residual_schema() -> dict:
    """One placement outcome per residual numeral: placed, ambiguous, or unplaced."""
    row = disposition_row_schema()
    new_value = pass3_schema()["properties"]["prose_values"]["items"]
    return _obj({
        "dispositions": _arr(row),
        "new_values": _arr(new_value, "Values the earlier pass missed, discovered "
                           "while classifying the residual."),
    })


# --------------------------------------------------------------------------
# The merged account -- what `bind.assemble` writes. Documented as a schema so
# a reader of the JSON has a contract; validated by `validate_account`.
# --------------------------------------------------------------------------

ACCOUNT_TOP_LEVEL = (
    "schema_version", "paper", "document", "background", "subjects",
    "statistical_analysis", "procedures", "phases", "studies", "variables", "values",
    "comparisons", "claims", "figure_panels", "supplements_referenced", "gaps",
    "accounting", "completeness", "provenance",
)


def validate_account(account: dict) -> list[str]:
    """Referential integrity of the merged account. Returns problems, never raises.

    Every id a row points at must exist; every value must sit at a coordinate
    whose parts exist; every comparison must name a study. A dangling id is not
    a warning -- it is a value nothing can bind to, which is the defect this
    whole layer exists to remove.
    """
    problems: list[str] = []
    for key in ACCOUNT_TOP_LEVEL:
        if key not in account:
            problems.append(f"missing top-level key `{key}`")
    studies = {s["id"]: s for s in account.get("studies", [])}
    variables = {v["id"] for v in account.get("variables", [])}
    procedures = {p["id"] for p in account.get("procedures", [])}
    groups = {(s["id"], g["id"]) for s in studies.values() for g in s.get("groups", [])}
    phases = {(s["id"], p["id"]) for s in studies.values() for p in s.get("phases", [])}
    # A paper-level occasion is valid at ANY study coordinate, including none.
    paper_phases = {p.get("id") for p in account.get("phases", []) if isinstance(p, dict)}
    # THE SAME PARTS WITHOUT THEIR STUDY, FOR A VALUE THAT NAMES NO STUDY. A
    # coordinate carries three axes and a reading may fill fewer -- an abstract
    # sentence naming an arm and no study is the ordinary case -- so a value may
    # arrive with `study_id: null` and a real `group_id`. The pair sets above are
    # keyed `(study, part)` and `(None, part)` is in neither, so such a value was
    # reported as naming an unknown group "in `None`" while the account declared
    # that group perfectly well. It is `sid`'s missing guard: the study check one
    # line below has it (`sid is not None and ...`) and its two siblings did not.
    # Measured over 17 paid accounts: 469 integrity problems, 461 of them this,
    # and every one of the 461 named an id the account DECLARES. `_Index`
    # withdraws any candidate whose input the record names, so 206 candidates
    # were refused as `account_integrity_problem` -- the account calling itself
    # broken. AND WHAT THAT COST WAS THE REASON, NOT THE CHECK: with the alarm
    # gone, 204 of the 206 are refused one gate later by a premise that is
    # actually missing (`no_paired_mean` 90, `binding_model_only` 86,
    # `no_variable` 12, `no_group_n` 10, `printed_not_plain_numeral` 6) and 2
    # remain, on the real defect this still catches. No check ran that had not
    # run before and no verdict moved, on any of the 17. So the fix buys a true
    # refusal docket rather than coverage -- worth having, and not the 206
    # checks it looked like from the refusal counts alone.
    #
    # ASKED OF EVERY STUDY, NOT SKIPPED. Dropping the check where `sid` is null
    # would let `(None, grp:ghost)` through unnamed; asking whether the part is
    # declared ANYWHERE keeps the guarantee that an id names a record, which is
    # all this function ever claimed. It is the rule `reference_group_id` below
    # has always used for a group id that arrives without a study.
    any_group = {g for _s, g in groups}
    any_phase = {p for _s, p in phases} | paper_phases

    def _undeclared(part: Any, sid: Any, pairs: set, anywhere: set) -> bool:
        """Does this coordinate part name nothing? A value that names a study is
        held to THAT study's parts; a value that names none is held to all."""
        return part not in anywhere if sid is None else (sid, part) not in pairs

    seen_value_ids: set[str] = set()
    for v in account.get("values", []):
        vid = v.get("id")
        if vid in seen_value_ids:
            problems.append(f"duplicate value id `{vid}`")
        seen_value_ids.add(vid)
        c = v.get("coordinate") or {}
        sid, gid, pid = c.get("study_id"), c.get("group_id"), c.get("phase_id")
        if sid is not None and sid not in studies:
            problems.append(f"value `{vid}` names unknown study `{sid}`")
        where = f"in `{sid}`" if sid is not None else "at any study"
        if gid is not None and _undeclared(gid, sid, groups, any_group):
            problems.append(f"value `{vid}` names unknown group `{gid}` {where}")
        if pid is not None and _undeclared(pid, sid, phases, any_phase) \
                and pid not in paper_phases:
            problems.append(f"value `{vid}` names unknown phase `{pid}` {where}")
        if v.get("variable_id") is not None and v["variable_id"] not in variables:
            problems.append(f"value `{vid}` names unknown variable `{v['variable_id']}`")
        if v.get("statistic") not in STATISTICS:
            problems.append(f"value `{vid}` has statistic `{v.get('statistic')}` "
                            "outside the vocabulary")
        rg = v.get("reference_group_id")
        if rg is not None and not any((s_id, rg) in groups for s_id in studies):
            problems.append(f"value `{vid}` names unknown reference group `{rg}`")
    for cmp_ in account.get("comparisons", []):
        if cmp_.get("study_id") not in studies:
            problems.append(f"comparison `{cmp_.get('id')}` names unknown study "
                            f"`{cmp_.get('study_id')}`")
        ov = cmp_.get("outcome_variable_id")
        if ov is not None and ov not in variables:
            problems.append(f"comparison `{cmp_.get('id')}` names unknown variable `{ov}`")
        d = cmp_.get("direction")
        if d is not None and d not in DIRECTIONS:
            problems.append(f"comparison `{cmp_.get('id')}` has direction `{d}` outside the vocabulary")
    for cl in account.get("claims", []):
        for sid in cl.get("study_ids", []):
            if sid not in studies:
                problems.append(f"claim `{cl.get('id')}` names unknown study `{sid}`")
    # AN ID IS A HANDLE AND TWO VARIABLES MAY NOT SHARE ONE. The duplicate VALUE
    # id is reported above; the variable table is read into a SET at the top of
    # this function (`variables = {v["id"] for ...}`), so a collision was
    # invisible to the one function whose job is to name it -- while every reader
    # downstream builds `{id: variable}` last-write-wins and adjudicates a value
    # against whichever of the two was written second. A slug-from-name reading
    # mints one id for two quantities the moment a paper names them alike.
    seen_variable_ids: set[Any] = set()
    for v in account.get("variables", []):
        vid = v.get("id")
        if vid in seen_variable_ids:
            problems.append(f"duplicate variable id `{vid}`")
        seen_variable_ids.add(vid)
    for v in account.get("variables", []):
        pid = v.get("procedure_id")
        if pid is not None and pid not in procedures:
            problems.append(f"variable `{v['id']}` names unknown procedure `{pid}`")
        for sid in v.get("studies_using", []):
            if sid not in studies:
                problems.append(f"variable `{v['id']}` names unknown study `{sid}`")
    return problems


#: The subject of a VALUE-level problem `validate_account` emits. Every such
#: message above opens either ``value `<id>` ...`` or ``duplicate value id
#: `<id>```, and this pattern sits beside them so the two sides cannot be edited
#: apart. `tests/test_scaffold.py` drives the real validator over a
#: deliberately broken account and asserts that every message naming a value is
#: recognised here, so a message in a new shape FAILS rather than going quietly
#: unread -- which is this project's recurring defect (two sides written at
#: different times, one moved) arriving through a string format.
_VALUE_PROBLEM = re.compile(r"^(?:duplicate value id|value) `([^`]+)`")


def values_with_problems(problems: Iterable[str]) -> set[str]:
    """The value ids that `validate_account`'s problems are ABOUT.

    WHY ANYTHING WANTS THIS. `bind.assemble` writes the problem list to
    `account["integrity_problems"]` and, until now, nothing but the renderer
    read it -- so the checks bridge adjudicated values the account itself
    already said were broken. A value naming a group the structure never
    declared is the documented route to a false accusation: it finds no n at its
    own coordinate, falls through to the study-level n, and inherits the whole
    cohort's denominator. Round 3's completers (32 of the 40 enrolled) came back
    `check_count_percent` `suspicious` and GRIM `impossible` on an honest paper
    by exactly that path.

    Reading it can only ever REMOVE a check, so it cannot accuse anybody, and an
    empty problem list -- the ordinary case -- makes it a no-op.
    """
    out: set[str] = set()
    for p in problems or ():
        m = _VALUE_PROBLEM.match(str(p))
        if m:
            out.add(m.group(1))
    return out


def pass_schema(name: str) -> dict:
    """The schema for a named pass, deep-copied so a caller cannot mutate the source."""
    table = {"pass1": pass1_schema, "pass2": pass2_schema,
             "pass3": pass3_schema, "residual": residual_schema}
    if name not in table:
        raise KeyError(f"no pass named {name!r}; one of {sorted(table)}")
    return copy.deepcopy(table[name]())
