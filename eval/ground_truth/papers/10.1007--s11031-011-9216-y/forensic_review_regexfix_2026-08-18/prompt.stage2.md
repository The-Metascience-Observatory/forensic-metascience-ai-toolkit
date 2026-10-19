Write the editorial forensic review for this paper.

Read the paper text and tables with `extract_xml`: `/mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.xml` (tables come back as structured cells; the PDF, where one exists, is only for figures and cross-checking)

What the sweep actually ran, which is the DENOMINATOR your verdict sits in:

```json
{
  "checks_passed": 26,
  "of_which_collapsed_by_check_table": 20,
  "checks_refused_indeterminate": 1,
  "checks_flagged": 16,
  "checks_total": 43,
  "by_severity": {
    "impossible": 2,
    "highly_suspicious": 2,
    "suspicious": 12,
    "consistent": 6,
    "indeterminate": 1
  },
  "rounding_convention": {
    "n_fit_only_under_truncation": 0,
    "n_granularity_checks": 13,
    "note": "Values that fail the round-half convention but are consistent if the reporter TRUNCATES (SPSS's default, and several journal styles). NOT a finding and never counted as one: a single instance is a house style. The RATE is the signal -- this class of anomaly is commoner in papers with more serious problems, so a high proportion is grounds to look harder, not evidence in itself."
  },
  "sd_convention": {
    "n_fit_only_under_population_sd": 0,
    "n_granularity_checks": 13,
    "note": "Values that fail under the sample (Bessel, n-1) SD but are consistent under the POPULATION (n) SD -- numpy's std default and Excel's STDEVP. NOT a finding and never counted as one: choosing a convention is not fabrication. The RATE is the signal, on the same reasoning as the rounding convention above."
  }
}
```

`checks_passed` includes `of_which_collapsed_by_check_table` -- passes that
`check_table` returned as a count rather than repeating, so they are NOT in the
findings list below and you would otherwise never see them. Weigh them: a paper
with many passes behind a few flags is in a different position from one with
few. `checks_refused_indeterminate` is OUR reach failing, not evidence about the
paper, and must not count against it.

Stage-1 sweep findings:

```json
{
  "paper_id": "10.1007--s11031-011-9216-y",
  "schema_version": "1.0",
  "paper_title": "RETRACTED ARTICLE: Happiness as alchemy: Positive mood leads to self-serving responses to social comparisons",
  "paper_metadata": {
    "authors": "Camille S. Johnson, Diederik A. Stapel",
    "journal": "Motivation and Emotion",
    "year": "2011",
    "doi": "10.1007/s11031-011-9216-y",
    "study_design": "Four between-subjects factorial laboratory experiments plus a pilot study; retracted article"
  },
  "anatomy": {
    "studies": [
      {
        "id": "pilot",
        "label": "Pilot study: mood manipulation check and self-evaluation baseline",
        "design": "rct",
        "n": 45,
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "n_per_group": [
          {
            "label": "positive mood",
            "n": 15
          },
          {
            "label": "negative mood",
            "n": 15
          },
          {
            "label": "control/neutral filler",
            "n": 15
          }
        ],
        "sample_flow": [
          {
            "stage": "participants reported",
            "n": 45,
            "unit": "participants"
          },
          {
            "stage": "per-condition n",
            "unit": "participants",
            "reason": "NOT reported by the paper; 15/15/15 is our inference from N = 45 over three conditions and error df = 42",
            "inferred": true
          }
        ]
      },
      {
        "id": "exp1",
        "label": "Experiment 1: positive mood x shared birthday x comparison direction",
        "design": "rct",
        "n": 47,
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "n_per_group": [
          {
            "label": "shared birthday / upward",
            "n": 12
          },
          {
            "label": "shared birthday / downward",
            "n": 12
          },
          {
            "label": "different birthday / upward",
            "n": 12
          },
          {
            "label": "different birthday / downward",
            "n": 11
          }
        ],
        "sample_flow": [
          {
            "stage": "female students recruited and analysed",
            "n": 47,
            "unit": "participants"
          },
          {
            "stage": "cell sizes",
            "unit": "participants",
            "reason": "NOT reported; 47 does not divide evenly into the four cells, so the split above is our inference from error df = 43",
            "inferred": true
          }
        ]
      },
      {
        "id": "exp2",
        "label": "Experiment 2: mood (positive/negative) x direction x shared birthday, plus hanging control",
        "design": "rct",
        "n": 141,
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "sample_flow": [
          {
            "stage": "students participating",
            "n": 141,
            "unit": "participants"
          },
          {
            "stage": "implied in the 2x2x2 factorial from error df = 118",
            "n": 126,
            "unit": "participants",
            "inferred": true,
            "reason": "F(1, 118) implies 8 cells over 126 participants; the paper never states cell sizes"
          }
        ]
      },
      {
        "id": "exp3",
        "label": "Experiment 3: mood (positive/neutral) x direction x ambiguity of similarity cue",
        "design": "rct",
        "n": 96,
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "n_per_group": [
          {
            "label": "each of eight cells",
            "n": 12
          }
        ],
        "sample_flow": [
          {
            "stage": "students participating for course credit",
            "n": 96,
            "unit": "participants"
          },
          {
            "stage": "eight factorial cells",
            "n": 12,
            "unit": "participants",
            "inferred": true,
            "reason": "96/8; corroborated by error df = 88 (= 96 - 8) and by all eight cell means being GRIM-consistent at n = 12"
          }
        ]
      },
      {
        "id": "exp4",
        "label": "Experiment 4: mood (positive/neutral) x direction x cognitive load, plus hanging control",
        "design": "rct",
        "n": 193,
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "sample_flow": [
          {
            "stage": "students participating",
            "n": 193,
            "unit": "participants"
          },
          {
            "stage": "implied in the 2x2x2 factorial from error df = 110",
            "n": 118,
            "unit": "participants",
            "inferred": true,
            "reason": "F(1, 110) implies 8 cells over 118 participants, leaving 75 of the stated 193 unaccounted for"
          }
        ]
      }
    ],
    "hypotheses": [
      {
        "id": "h1",
        "study_id": "exp1",
        "statement": "Ambiguous similarity information (a shared birthday) must be present for positive mood to produce asymmetric, self-serving responses: assimilation to upward and contrast from downward comparison targets.",
        "status": "confirmatory",
        "confidence": "high",
        "appears_in_abstract": true,
        "provenance_quote": "In the presence of ambiguous information, participants in a positive mood were expected to respond asymmetrically: assimilating to upward comparison targets and contrasting with downward targets."
      },
      {
        "id": "h2",
        "study_id": "exp2",
        "statement": "Negative mood produces symmetric contrast rather than the asymmetric self-serving pattern, ruling out a mood-congruency account.",
        "status": "confirmatory",
        "confidence": "high",
        "appears_in_abstract": true,
        "provenance_quote": "However, the responses of participants in a negative mood were expected to be symmetric: contrast with both upward and downward comparison others."
      },
      {
        "id": "h3",
        "study_id": "exp3",
        "statement": "Self-serving responding occurs only when the similarity cue is explicitly ambiguous, not when it is explicitly unambiguous.",
        "status": "confirmatory",
        "confidence": "high",
        "appears_in_abstract": false,
        "provenance_quote": "Because the effects of positive mood are predicted to require ambiguous information, self-serving effects were expected to occur only when similarity information was ambiguous and open to alternative interpretation."
      },
      {
        "id": "h4",
        "study_id": "exp4",
        "statement": "Asymmetric self-serving responding is effortful and therefore disappears under cognitive load, leaving positive-mood participants looking like neutral-mood participants.",
        "status": "confirmatory",
        "confidence": "high",
        "appears_in_abstract": false,
        "provenance_quote": "When participants were under load, the positive mood effects on responses to downward comparisons were expected to dissipate, reflecting the resource-demanding nature of self-serving asymmetric interpretations."
      },
      {
        "id": "h5",
        "study_id": "pilot",
        "statement": "Mood manipulations do not by themselves change self-evaluations in the absence of comparison information.",
        "status": "confirmatory",
        "confidence": "high",
        "appears_in_abstract": false,
        "provenance_quote": "Thus, it was important to establish that mood, and the mood manipulations we employ, are not associated with changes in self-evaluations in the absence of comparison information."
      }
    ],
    "variables": [
      {
        "id": "v_selfeval7",
        "name": "Self-evaluation (self-rated attractiveness)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_item",
        "n_items": 1,
        "lower_bound": 1,
        "upper_bound": 7,
        "derivation": "measured",
        "confidence": "high",
        "provenance_quote": "Participants also rated their own attractiveness (How attractive are you?) on a seven-point scale (1 = not at all, 7 = extremely)."
      },
      {
        "id": "v_targetattr7",
        "name": "Target attractiveness rating",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_item",
        "n_items": 1,
        "lower_bound": 1,
        "upper_bound": 7,
        "derivation": "measured",
        "confidence": "high",
        "provenance_quote": "all participants reported their major, gender, age, and rated their own attractiveness and the target\u2019s attractiveness on seven-point scales (1 = not at all attractive and 7 = extremely attractive)"
      },
      {
        "id": "v_mood7",
        "name": "Self-reported mood (Experiments 2 and 4)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_item",
        "n_items": 1,
        "lower_bound": 1,
        "upper_bound": 7,
        "derivation": "measured",
        "confidence": "high",
        "provenance_quote": "Participants also reported how positive or negative they felt at that moment (1 = negative mood and 7 = positive mood)"
      },
      {
        "id": "v_mood9",
        "name": "Mood index (pilot study)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_composite",
        "n_items": 4,
        "lower_bound": 1,
        "upper_bound": 9,
        "derivation": "mean_of_items",
        "derived_from": "four nine-point bipolar mood items, Cronbach's alpha = .91",
        "confidence": "high",
        "provenance_quote": "The four mood items were averaged to create an index of mood (Cronbach\u2019s alpha = .91)"
      },
      {
        "id": "v_selfeval9",
        "name": "Self-evaluation index (pilot study)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_composite",
        "n_items": 3,
        "lower_bound": 1,
        "upper_bound": 9,
        "derivation": "mean_of_items",
        "derived_from": "three nine-point items: intelligent, competent, successful; Cronbach's alpha = .71",
        "confidence": "high",
        "provenance_quote": "they rated how well each of the following words described them on nine-point Likert scales (1 = not at all me, 9 = very much me): intelligent, competent, and successful."
      },
      {
        "id": "v_similarity",
        "name": "Perceived similarity index (Experiment 3)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_composite",
        "n_items": 3,
        "lower_bound": 1,
        "upper_bound": 9,
        "derivation": "mean_of_items",
        "derived_from": "three nine-point similarity questions, alpha = .87",
        "confidence": "high",
        "provenance_quote": "participant responses to the three similarity questions were averaged (alpha = .87)"
      },
      {
        "id": "v_mood_cond",
        "name": "Mood condition",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "nominal_category",
        "levels": [
          "positive",
          "negative",
          "neutral/control"
        ],
        "confidence": "high",
        "provenance_quote": "A 2(mood: positive vs. negative) \u00d7 2(direction of comparison: upward vs. downward) \u00d7 2(similarity cue: shared birthday vs. different birthday) factorial design was used, with an additional no-mood, no comparison control condition."
      },
      {
        "id": "v_direction",
        "name": "Direction of comparison",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "levels": [
          "upward (more attractive target)",
          "downward (less attractive target)"
        ],
        "confidence": "high",
        "provenance_quote": "2(direction of comparison: upward vs. downward)"
      },
      {
        "id": "v_cue",
        "name": "Similarity cue",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "levels": [
          "shared birthday",
          "different birthday",
          "ambiguous aesthetic preference",
          "unambiguous aesthetic preference"
        ],
        "confidence": "high",
        "provenance_quote": "2(similarity cue: shared birthday vs. different birthday)"
      },
      {
        "id": "v_load",
        "name": "Cognitive load",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "levels": [
          "load (hold 8-digit number)",
          "no load"
        ],
        "confidence": "high",
        "provenance_quote": "2(load: load vs. no load) factorial design, with an additional no mood induction, no comparison, no load control condition."
      }
    ],
    "tests": [
      {
        "id": "t_pilot_mood_anova",
        "study_id": "pilot",
        "test_type": "one_way_anova",
        "location": "Pilot study, Results",
        "outcome_var": "v_mood9",
        "predictor_vars": [
          "v_mood_cond"
        ],
        "statistic_value": 18.44,
        "df": "2, 42",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 45,
        "confidence": "high",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "correction_applied": "none",
        "provenance_quote": "A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_pilot_pos_vs_ctrl",
        "study_id": "pilot",
        "test_type": "independent_t",
        "location": "Pilot study, Results",
        "outcome_var": "v_mood9",
        "grouping_var": "v_mood_cond",
        "statistic_value": 3.43,
        "df": "42",
        "p_value": 0.001,
        "n": 30,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "Participants in the positive mood condition reported more positive mood (M = 7.20, SD = .93) that those in the control condition (M = 6.15, SD = .52), t(42) = 3.43, p = .001.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_pilot_neg_vs_ctrl",
        "study_id": "pilot",
        "test_type": "independent_t",
        "location": "Pilot study, Results",
        "outcome_var": "v_mood9",
        "grouping_var": "v_mood_cond",
        "statistic_value": -3.8,
        "df": "42",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 30,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "Participants in the negative mood condition reported more negative mood (M = 4.98, SD = .98) than those in the control condition, t(42) = -3.80, p < .001.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_pilot_selfeval",
        "study_id": "pilot",
        "test_type": "one_way_anova",
        "location": "Pilot study, Results",
        "outcome_var": "v_selfeval9",
        "predictor_vars": [
          "v_mood_cond"
        ],
        "statistic_value": 0.27,
        "df": "1, 42",
        "p_value": 0.76,
        "n": 45,
        "confidence": "high",
        "is_stated_primary_outcome": true,
        "correction_applied": "none",
        "provenance_quote": "Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e1_manipcheck",
        "study_id": "exp1",
        "test_type": "one_way_anova",
        "location": "Experiment 1, Manipulation check",
        "outcome_var": "v_targetattr7",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": 38.8,
        "df": "1, 43",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 47,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "the upward comparison target was rated more attractive (M = 5.71, SD = .75) than the downward target (M = 3.57, SD = 1.47), F(1,43) = 38.80, p < .001",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e1_cue_main",
        "study_id": "exp1",
        "test_type": "ancova",
        "location": "Experiment 1, Self-evaluations",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_cue"
        ],
        "statistic_value": 7.77,
        "df": "1, 43",
        "p_value": 0.008,
        "n": 47,
        "confidence": "high",
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "provenance_quote": "those sharing a birthday reported higher self-evaluations (M = 4.92, SD = 1.14) than those not sharing a birthday (M = 3.96, SD = 1.3), F(1, 43) = 7.77, p = .008",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e1_interaction",
        "study_id": "exp1",
        "test_type": "ancova",
        "location": "Experiment 1, Self-evaluations",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_cue",
          "v_direction"
        ],
        "statistic_value": 5.99,
        "df": "1, 43",
        "p_value": 0.019,
        "n": 47,
        "confidence": "high",
        "is_stated_primary_outcome": true,
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "provenance_quote": "These main effects were qualified by the significant and expected interaction effect on self-evaluations, F(1, 43) = 5.99, p = .019.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e1_simple_unshared",
        "study_id": "exp1",
        "test_type": "one_way_anova",
        "location": "Experiment 1, Self-evaluations, unshared birthday",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": 6.95,
        "df": "1, 46",
        "p_value": 0.011,
        "n": 24,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e2_mood_manip",
        "study_id": "exp2",
        "test_type": "ancova",
        "location": "Experiment 2, Manipulation check",
        "outcome_var": "v_mood7",
        "predictor_vars": [
          "v_mood_cond"
        ],
        "statistic_value": 340.44,
        "df": "1, 132",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 141,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "only the mood manipulation significantly affected mood, F(1, 132) = 340.44, p < .001",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e2_pos_vs_ctrl",
        "study_id": "exp2",
        "test_type": "independent_t",
        "location": "Experiment 2, Manipulation check",
        "outcome_var": "v_mood7",
        "grouping_var": "v_mood_cond",
        "statistic_value": 5.61,
        "df": "138",
        "p_value": 0.001,
        "p_is_threshold": true,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "Participants in the positive mood condition were more positive (M = 5.72, SD = .82) than the control condition (M = 4.40, SD = .83), t(138) = 5.61, p < .001.",
        "effect_size_estimated": {
          "kind": "hedges_g",
          "value": 3.29,
          "ci95": [
            2.68,
            3.96
          ],
          "ci_spans_null": false,
          "computed_from": "positive M = 5.72 SD = .82 vs negative M = 2.98 SD = .83, n assumed 45 per arm",
          "tool": "check_effect_plausibility"
        },
        "assumption_checks_reported": []
      },
      {
        "id": "t_e2_attr_manip",
        "study_id": "exp2",
        "test_type": "ancova",
        "location": "Experiment 2, Manipulation check",
        "outcome_var": "v_targetattr7",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": 716.92,
        "df": "1, 118",
        "p_value": 0.001,
        "p_is_threshold": true,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "The upward comparison target was rated more attractive (M = 5.98, SD = .69) than the downward target (M = 2.46, SD = .74), F(1,118) = 716.92, p < .001.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e2_threeway",
        "study_id": "exp2",
        "test_type": "ancova",
        "location": "Experiment 2, Self-evaluations",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_mood_cond",
          "v_direction",
          "v_cue"
        ],
        "statistic_value": 5.13,
        "df": "1, 118",
        "p_value": 0.03,
        "confidence": "high",
        "is_stated_primary_outcome": true,
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "provenance_quote": "which revealed the expected three-way interaction effect on self-evaluations, F(1, 118) = 5.13, p = .03",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e2_pos_interaction",
        "study_id": "exp2",
        "test_type": "ancova",
        "location": "Experiment 2, Positive mood",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_direction",
          "v_cue"
        ],
        "statistic_value": 9.39,
        "df": "1, 124",
        "p_value": 0.003,
        "confidence": "high",
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "provenance_quote": "the interaction effect of direction of comparison and similarity information, F(1, 124) = 9.39, p = .003, all significantly influenced self-ratings",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e2_neg_direction",
        "study_id": "exp2",
        "test_type": "ancova",
        "location": "Experiment 2, Negative mood",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": 56.97,
        "df": "1, 124",
        "p_value": 0.001,
        "p_is_threshold": true,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "only the main effect of direction was significant, F(1, 124) = 56.97, p < .001",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e3_mood_manip",
        "study_id": "exp3",
        "test_type": "ancova",
        "location": "Experiment 3, Manipulation check",
        "outcome_var": "v_mood7",
        "predictor_vars": [
          "v_mood_cond"
        ],
        "statistic_value": 104.58,
        "df": "1, 88",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 96,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "only the main effect of mood condition significantly influenced self-reported mood, F(1, 88) = 104.58, p < .001. Participants in the positive mood condition were more positive (M = 7.33, SD = .86) than the neutral condition (M = 5.44, SD = .97).",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e3_attr_manip",
        "study_id": "exp3",
        "test_type": "ancova",
        "location": "Experiment 3, Manipulation check",
        "outcome_var": "v_targetattr7",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": 170.34,
        "df": "1, 88",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 96,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e3_cue_mood",
        "study_id": "exp3",
        "test_type": "ancova",
        "location": "Experiment 3, Self-evaluations",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_cue",
          "v_mood_cond"
        ],
        "statistic_value": 19.87,
        "df": "1, 88",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 96,
        "confidence": "high",
        "is_stated_primary_outcome": true,
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "provenance_quote": "These were qualified by the two-way interaction effects of similarity cue and mood (F(1, 88) = 19.87, p < .001)",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e3_sim_threeway",
        "study_id": "exp3",
        "test_type": "ancova",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "v_similarity",
        "predictor_vars": [
          "v_mood_cond",
          "v_direction",
          "v_cue"
        ],
        "statistic_value": 15.32,
        "df": "1, 88",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 96,
        "confidence": "high",
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "provenance_quote": "These were further qualified by the significant three-way interaction effect, F(1, 88) = 15.32, p < .001.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e3_sim_amb_contrast",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "v_similarity",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": 53.17,
        "df": "1, 94",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 24,
        "confidence": "high",
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "provenance_quote": "participants in a positive mood rated upward comparison targets as more similar to the self than downward comparison targets, F(1, 94) = 53.17, p < .001",
        "effect_size_estimated": {
          "kind": "hedges_g",
          "value": 5.03,
          "ci95": [
            3.53,
            6.88
          ],
          "ci_spans_null": false,
          "computed_from": "Table 2 Similarity, Positive/Ambiguous: 7.06 (.53) vs 4.14 (.59), n = 12 per cell",
          "tool": "check_effect_plausibility"
        },
        "assumption_checks_reported": []
      },
      {
        "id": "t_e3_sim_unamb_neutral",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "v_similarity",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": 1.5,
        "df": "1, 94",
        "p_value": 0.83,
        "n": 24,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e3_sim_amb_neutral",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "v_similarity",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": 0.31,
        "df": "1, 94",
        "p_value": 0.58,
        "n": 24,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "direction of comparison did not influence ratings of similarity, F(1, 94) = .31, p = .58",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e3_r_pos_unamb",
        "study_id": "exp3",
        "test_type": "pearson_correlation",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_targetattr7"
        ],
        "statistic_value": 0.87,
        "df": "24",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 26,
        "effect_size": "r(24) = .87",
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "self and other attractiveness were significantly related in the positive, r(24) = .87, p < .001",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e3_r_neu_unamb",
        "study_id": "exp3",
        "test_type": "pearson_correlation",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_targetattr7"
        ],
        "statistic_value": 0.53,
        "df": "24",
        "p_value": 0.008,
        "n": 26,
        "effect_size": "r(24) = .53",
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "and neutral mood, r(24) = .53, p = .008, reflecting assimilation of self",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e4_mood_manip",
        "study_id": "exp4",
        "test_type": "ancova",
        "location": "Experiment 4, Manipulation check",
        "outcome_var": "v_mood7",
        "predictor_vars": [
          "v_mood_cond"
        ],
        "statistic_value": 14.94,
        "df": "1, 124",
        "p_value": 0.001,
        "p_is_threshold": true,
        "n": 193,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "there was a main effect of mood induction on mood, F(1, 124) = 14.94, p < .001",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e4_threeway",
        "study_id": "exp4",
        "test_type": "ancova",
        "location": "Experiment 4, Self-evaluations",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_load",
          "v_mood_cond",
          "v_direction"
        ],
        "statistic_value": 11.23,
        "df": "1, 110",
        "p_value": 0.001,
        "n": 193,
        "confidence": "high",
        "is_stated_primary_outcome": true,
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "provenance_quote": "Analysis revealed the expected three-way interaction effect of load, mood, and direction of comparison on attractiveness, F(1, 110) = 11.23, p = 001.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e4_noload_up",
        "study_id": "exp4",
        "test_type": "ancova",
        "location": "Experiment 4, No load conditions",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": 17.39,
        "df": "1, 124",
        "p_value": 0.001,
        "p_is_threshold": true,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "regardless of whether participants upwardly compared (M = 5.64, SD = .78; F(1,124) = 17.39, p < .001)",
        "assumption_checks_reported": []
      },
      {
        "id": "t_e4_load_down",
        "study_id": "exp4",
        "test_type": "independent_t",
        "location": "Experiment 4, Cognitive load conditions",
        "outcome_var": "v_selfeval7",
        "predictor_vars": [
          "v_direction"
        ],
        "statistic_value": -3.3,
        "df": "124",
        "p_value": 0.001,
        "confidence": "high",
        "correction_applied": "none",
        "provenance_quote": "downward comparison led to less positive self-ratings (M = 3.09, SD = .94), t(124) = -3.30, p = .001",
        "assumption_checks_reported": []
      }
    ]
  },
  "statistics_register": [
    {
      "id": "s01",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 7.2,
        "SD": 0.93
      },
      "quote": "Participants in the positive mood condition reported more positive mood (M = 7.20, SD = .93) that those in the control condition (M = 6.15, SD = .52), t(42) = 3.43, p = .001.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check"
        ],
        "reason": "4-item mean on a 1-9 scale; per-condition n is not reported, so granularity is 1/(4n) with n unknown"
      }
    },
    {
      "id": "s02",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 6.15,
        "SD": 0.52
      },
      "quote": "Participants in the positive mood condition reported more positive mood (M = 7.20, SD = .93) that those in the control condition (M = 6.15, SD = .52), t(42) = 3.43, p = .001.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [],
        "reason": "4-item composite mean, per-group n unreported"
      }
    },
    {
      "id": "s03",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 4.98,
        "SD": 0.98
      },
      "quote": "Participants in the negative mood condition reported more negative mood (M = 4.98, SD = .98) than those in the control condition, t(42) = -3.80, p < .001.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [],
        "reason": "4-item composite mean, per-group n unreported"
      }
    },
    {
      "id": "s04",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 18.44,
        "df1": 2,
        "df2": 42,
        "p": 0.001
      },
      "quote": "A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [
          "statcheck",
          "rivets_anova",
          "recalc_anova"
        ]
      }
    },
    {
      "id": "s05",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 6.98,
        "SD": 0.53
      },
      "quote": "Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [],
        "reason": "3-item composite mean on 1-9; per-group n unreported so granularity 1/(3n) is unknown"
      }
    },
    {
      "id": "s06",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 6.98,
        "SD": 0.8
      },
      "quote": "Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [],
        "reason": "3-item composite mean, per-group n unreported"
      }
    },
    {
      "id": "s07",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 6.82,
        "SD": 0.67
      },
      "quote": "Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [],
        "reason": "3-item composite mean, per-group n unreported"
      }
    },
    {
      "id": "s08",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 0.27,
        "df1": 1,
        "df2": 42,
        "p": 0.76
      },
      "quote": "did not differ F(1, 42) = .27, p = .76",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [
          "statcheck",
          "recalc_f_to_p"
        ]
      }
    },
    {
      "id": "s09",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 45,
        "female": 30,
        "M_age": 19.5
      },
      "quote": "a pilot study conducted in which participants (N = 45, 30 female, M age = 19.5) completed positive or negative mood manipulations",
      "location": "Pilot study, opening",
      "checkable": {
        "tools": [
          "flag_round_n"
        ],
        "reason": "N is reported but per-condition allocation is not"
      }
    },
    {
      "id": "s10",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 47
      },
      "quote": "Female university (N = 47) students participated in the study for monetary compensation.",
      "location": "Experiment 1, Participants and design",
      "checkable": {
        "tools": [],
        "reason": "a stated total with no cell breakdown; nothing to verify arithmetically"
      }
    },
    {
      "id": "s11",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.71,
        "SD": 0.75
      },
      "quote": "the upward comparison target was rated more attractive (M = 5.71, SD = .75) than the downward target (M = 3.57, SD = 1.47), F(1,43) = 38.80, p < .001",
      "location": "Experiment 1, Manipulation check",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "rivets_anova"
        ],
        "reason": "single 7-point item, but group n unreported"
      }
    },
    {
      "id": "s12",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 3.57,
        "SD": 1.47
      },
      "quote": "the upward comparison target was rated more attractive (M = 5.71, SD = .75) than the downward target (M = 3.57, SD = 1.47), F(1,43) = 38.80, p < .001",
      "location": "Experiment 1, Manipulation check",
      "checkable": {
        "tools": [
          "rivets_anova"
        ]
      }
    },
    {
      "id": "s13",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 38.8,
        "df1": 1,
        "df2": 43,
        "p": 0.001
      },
      "quote": "F(1,43) = 38.80, p < .001",
      "location": "Experiment 1, Manipulation check",
      "checkable": {
        "tools": [
          "statcheck",
          "rivets_anova"
        ]
      }
    },
    {
      "id": "s14",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 4.92,
        "SD": 1.14
      },
      "quote": "those sharing a birthday reported higher self-evaluations (M = 4.92, SD = 1.14) than those not sharing a birthday (M = 3.96, SD = 1.3), F(1, 43) = 7.77, p = .008",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [
          "grim_check"
        ],
        "reason": "marginal mean over two cells whose sizes are unreported"
      }
    },
    {
      "id": "s15",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 3.96,
        "SD": 1.3
      },
      "quote": "those sharing a birthday reported higher self-evaluations (M = 4.92, SD = 1.14) than those not sharing a birthday (M = 3.96, SD = 1.3), F(1, 43) = 7.77, p = .008",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [],
        "reason": "marginal mean, group n unreported"
      }
    },
    {
      "id": "s16",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 7.77,
        "df1": 1,
        "df2": 43,
        "p": 0.008
      },
      "quote": "F(1, 43) = 7.77, p = .008",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [
          "statcheck"
        ]
      }
    },
    {
      "id": "s17",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 5.99,
        "df1": 1,
        "df2": 43,
        "p": 0.019
      },
      "quote": "These main effects were qualified by the significant and expected interaction effect on self-evaluations, F(1, 43) = 5.99, p = .019.",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [
          "statcheck"
        ]
      }
    },
    {
      "id": "s18",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 3.33,
        "SD": 0.65
      },
      "quote": "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [
          "rivets_anova",
          "grimmer_check"
        ],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s19",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 4.64,
        "SD": 1.5
      },
      "quote": "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [
          "rivets_anova"
        ]
      }
    },
    {
      "id": "s20",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 6.95,
        "df1": 1,
        "df2": 46,
        "p": 0.011
      },
      "quote": "F(1, 46) = 6.95, p = 011.",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [
          "statcheck",
          "rivets_anova"
        ]
      }
    },
    {
      "id": "s21",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.08,
        "SD": 0.52
      },
      "quote": "participant responses showed asymmetric assimilation towards the upward comparison target (M = 5.08, SD = .52) and contrast away from the downward comparison target (M = 4.75, SD = 1.54)",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [
          "grimmer_check"
        ],
        "reason": "cell n unreported (47 does not divide evenly into four cells)"
      }
    },
    {
      "id": "s22",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 4.75,
        "SD": 1.54
      },
      "quote": "participant responses showed asymmetric assimilation towards the upward comparison target (M = 5.08, SD = .52) and contrast away from the downward comparison target (M = 4.75, SD = 1.54)",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s23",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 141,
        "women": 75
      },
      "quote": "University (N = 141, 75 women) students participated in the study for monetary compensation.",
      "location": "Experiment 2, Participants and design",
      "checkable": {
        "tools": [],
        "reason": "stated total; cell sizes never reported"
      }
    },
    {
      "id": "s24",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 340.44,
        "df1": 1,
        "df2": 132,
        "p": 0.001
      },
      "quote": "only the mood manipulation significantly affected mood, F(1, 132) = 340.44, p < .001",
      "location": "Experiment 2, Manipulation check",
      "checkable": {
        "tools": [
          "statcheck"
        ]
      }
    },
    {
      "id": "s25",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.72,
        "SD": 0.82
      },
      "quote": "Participants in the positive mood condition were more positive (M = 5.72, SD = .82) than the control condition (M = 4.40, SD = .83), t(138) = 5.61, p < .001.",
      "location": "Experiment 2, Manipulation check",
      "checkable": {
        "tools": [
          "check_effect_plausibility"
        ],
        "reason": "single 7-point item but group n unreported, so GRIM/GRIMMER cannot run"
      }
    },
    {
      "id": "s26",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 4.4,
        "SD": 0.83
      },
      "quote": "Participants in the positive mood condition were more positive (M = 5.72, SD = .82) than the control condition (M = 4.40, SD = .83), t(138) = 5.61, p < .001.",
      "location": "Experiment 2, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n unreported"
      }
    },
    {
      "id": "s27",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 2.98,
        "SD": 0.83
      },
      "quote": "The negative mood condition (M = 2.98, SD = .83), was more negative than the control condition, t(138) = -5.97, p < .001.",
      "location": "Experiment 2, Manipulation check",
      "checkable": {
        "tools": [
          "check_effect_plausibility"
        ],
        "reason": "group n unreported"
      }
    },
    {
      "id": "s28",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.98,
        "SD": 0.69
      },
      "quote": "The upward comparison target was rated more attractive (M = 5.98, SD = .69) than the downward target (M = 2.46, SD = .74), F(1,118) = 716.92, p < .001.",
      "location": "Experiment 2, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n unreported"
      }
    },
    {
      "id": "s29",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 2.46,
        "SD": 0.74
      },
      "quote": "The upward comparison target was rated more attractive (M = 5.98, SD = .69) than the downward target (M = 2.46, SD = .74), F(1,118) = 716.92, p < .001.",
      "location": "Experiment 2, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n unreported"
      }
    },
    {
      "id": "s30",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 5.25,
        "SD": 0.93
      },
      "quote": "5.25 (.93)",
      "location": "Table 1, Self-evaluation row, Positive mood/Same birthday/Upward",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ],
        "reason": "cell n unreported; the factorial N implied by error df (126) does not divide by 8, so no cell n can be assigned"
      }
    },
    {
      "id": "s31",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 5.53,
        "SD": 0.52
      },
      "quote": "5.53 (.52)",
      "location": "Table 1, Self-evaluation row, Positive mood/Same birthday/Downward",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s32",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 3.17,
        "SD": 0.98
      },
      "quote": "3.17 (.98)",
      "location": "Table 1, Self-evaluation row, Positive mood/Different birthday/Upward",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s33",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 5.13,
        "SD": 0.72
      },
      "quote": "5.13 (.72)",
      "location": "Table 1, Self-evaluation row, Positive mood/Different birthday/Downward",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s34",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 3.33,
        "SD": 0.9
      },
      "quote": "3.33 (.90)",
      "location": "Table 1, Self-evaluation row, Negative mood/Same birthday/Upward",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s35",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 5.2,
        "SD": 0.68
      },
      "quote": "5.20 (.68)",
      "location": "Table 1, Self-evaluation row, Negative mood/Same birthday/Downward",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s36",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 3.07,
        "SD": 0.62
      },
      "quote": "3.07 (.62)",
      "location": "Table 1, Self-evaluation row, Negative mood/Different birthday/Upward",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s37",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 5.35,
        "SD": 0.7
      },
      "quote": "5.35 (.70)",
      "location": "Table 1, Self-evaluation row, Negative mood/Different birthday/Downward",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s38",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 5.13,
        "df1": 1,
        "df2": 118,
        "p": 0.03
      },
      "quote": "which revealed the expected three-way interaction effect on self-evaluations, F(1, 118) = 5.13, p = .03",
      "location": "Experiment 2, Self-evaluations",
      "checkable": {
        "tools": [
          "statcheck"
        ]
      }
    },
    {
      "id": "s39",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 96
      },
      "quote": "University students (N = 96) participated in the study for course credit.",
      "location": "Experiment 3, Participants",
      "checkable": {
        "tools": [
          "required_n"
        ],
        "reason": "total is stated; eight equal cells of 12 follow from the design and are corroborated by error df = 88"
      }
    },
    {
      "id": "s40",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 7.33,
        "SD": 0.86
      },
      "quote": "Participants in the positive mood condition were more positive (M = 7.33, SD = .86) than the neutral condition (M = 5.44, SD = .97).",
      "location": "Experiment 3, Manipulation check",
      "checkable": {
        "tools": [
          "grim_check"
        ],
        "reason": "exceeds the 7-point ceiling the Method attributes to this measure"
      }
    },
    {
      "id": "s41",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.44,
        "SD": 0.97
      },
      "quote": "Participants in the positive mood condition were more positive (M = 7.33, SD = .86) than the neutral condition (M = 5.44, SD = .97).",
      "location": "Experiment 3, Manipulation check",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check"
        ],
        "reason": "group n = 48 inferable, but the applicable scale is contested (see 7.33 finding)"
      }
    },
    {
      "id": "s42",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 7.33,
        "SD": 1.19
      },
      "quote": "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001",
      "location": "Experiment 3, Manipulation check",
      "checkable": {
        "tools": [
          "grim_check"
        ]
      }
    },
    {
      "id": "s43",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 4.17,
        "SD": 1.19
      },
      "quote": "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001",
      "location": "Experiment 3, Manipulation check",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check"
        ],
        "reason": "applicable scale contested; SD identical to the upward cell"
      }
    },
    {
      "id": "s44",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 6.58,
        "SD": 0.9
      },
      "quote": "6.58 (.90)",
      "location": "Table 2, Self-evaluation row, Positive/Ambiguous/Upward",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s45",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 6.5,
        "SD": 0.8
      },
      "quote": "6.50 (.80)",
      "location": "Table 2, Self-evaluation row, Positive/Ambiguous/Downward",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s46",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 6.58,
        "SD": 0.52
      },
      "quote": "6.58 (.52)",
      "location": "Table 2, Self-evaluation row, Positive/Unambiguous/Upward",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s47",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 4.08,
        "SD": 0.52
      },
      "quote": "4.08 (.52)",
      "location": "Table 2, Self-evaluation row, Positive/Unambiguous/Downward",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s48",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 5.42,
        "SD": 0.79
      },
      "quote": "5.42 (.79)",
      "location": "Table 2, Self-evaluation row, Neutral/Ambiguous/Upward",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s49",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 5.33,
        "SD": 0.78
      },
      "quote": "5.33 (.78)",
      "location": "Table 2, Self-evaluation row, Neutral/Ambiguous/Downward",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s50",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 6.75,
        "SD": 0.87
      },
      "quote": "6.75 (.87)",
      "location": "Table 2, Self-evaluation row, Neutral/Unambiguous/Upward",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s51",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 4.33,
        "SD": 0.78
      },
      "quote": "4.33 (.78)",
      "location": "Table 2, Self-evaluation row, Neutral/Unambiguous/Downward",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s52",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 7.06,
        "SD": 0.53
      },
      "quote": "7.06 (.53)",
      "location": "Table 2, Similarity row, Positive/Ambiguous/Upward",
      "checkable": {
        "tools": [
          "check_effect_plausibility"
        ],
        "reason": "mean of 3 items: granularity 1/(3n); the GRIM family has no items parameter and refuses"
      }
    },
    {
      "id": "s53",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 4.14,
        "SD": 0.59
      },
      "quote": "4.14 (.59)",
      "location": "Table 2, Similarity row, Positive/Ambiguous/Downward",
      "checkable": {
        "tools": [
          "check_effect_plausibility"
        ],
        "reason": "3-item mean; GRIM family refuses"
      }
    },
    {
      "id": "s54",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 6.81,
        "SD": 1.16
      },
      "quote": "6.81 (1.16)",
      "location": "Table 2, Similarity row, Positive/Unambiguous/Upward",
      "checkable": {
        "tools": [],
        "reason": "3-item mean; GRIM family refuses"
      }
    },
    {
      "id": "s55",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 6.81,
        "SD": 0.63
      },
      "quote": "6.81 (.63)",
      "location": "Table 2, Similarity row, Positive/Unambiguous/Downward",
      "checkable": {
        "tools": [],
        "reason": "3-item mean; GRIM family refuses"
      }
    },
    {
      "id": "s56",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 5.72,
        "SD": 0.97
      },
      "quote": "5.72 (.97)",
      "location": "Table 2, Similarity row, Neutral/Ambiguous/Upward",
      "checkable": {
        "tools": [],
        "reason": "3-item mean; GRIM family refuses"
      }
    },
    {
      "id": "s57",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 5.44,
        "SD": 0.69
      },
      "quote": "5.44 (.69)",
      "location": "Table 2, Similarity row, Neutral/Ambiguous/Downward",
      "checkable": {
        "tools": [],
        "reason": "3-item mean; GRIM family refuses"
      }
    },
    {
      "id": "s58",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 6.72,
        "SD": 0.76
      },
      "quote": "6.72 (.76)",
      "location": "Table 2, Similarity row, Neutral/Unambiguous/Upward",
      "checkable": {
        "tools": [],
        "reason": "3-item mean; GRIM family refuses"
      }
    },
    {
      "id": "s59",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 6.83,
        "SD": 0.8
      },
      "quote": "6.83 (.80)",
      "location": "Table 2, Similarity row, Neutral/Unambiguous/Downward",
      "checkable": {
        "tools": [],
        "reason": "3-item mean; GRIM family refuses"
      }
    },
    {
      "id": "s60",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 1.5,
        "df1": 1,
        "df2": 94,
        "p": 0.83
      },
      "quote": "Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83.",
      "location": "Experiment 3, Perceptions of similarity",
      "checkable": {
        "tools": [
          "statcheck",
          "recalc_f_to_p"
        ]
      }
    },
    {
      "id": "s61",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 0.31,
        "df1": 1,
        "df2": 94,
        "p": 0.58
      },
      "quote": "direction of comparison did not influence ratings of similarity, F(1, 94) = .31, p = .58",
      "location": "Experiment 3, Perceptions of similarity",
      "checkable": {
        "tools": [
          "statcheck",
          "recalc_f_to_p"
        ]
      }
    },
    {
      "id": "s62",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "r": 0.53,
        "df": 24,
        "p": 0.008
      },
      "quote": "and neutral mood, r(24) = .53, p = .008, reflecting assimilation of self",
      "location": "Experiment 3, Perceptions of similarity",
      "checkable": {
        "tools": [
          "statcheck"
        ]
      }
    },
    {
      "id": "s63",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "r": 0.87,
        "df": 24,
        "p": 0.001
      },
      "quote": "self and other attractiveness were significantly related in the positive, r(24) = .87, p < .001",
      "location": "Experiment 3, Perceptions of similarity",
      "checkable": {
        "tools": [
          "statcheck"
        ]
      }
    },
    {
      "id": "s64",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 193,
        "female": 103
      },
      "quote": "University (N = 193, 103 female) students participated in the study for monetary compensation.",
      "location": "Experiment 4, Participants and design",
      "checkable": {
        "tools": [],
        "reason": "stated total; irreconcilable with the error df the analyses report (see finding exp4_n_vs_error_df)"
      }
    },
    {
      "id": "s65",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.35,
        "SD": 0.81
      },
      "quote": "Participants in the positive condition were more positive (M = 5.35, SD = .81) than participants in the neutral condition (M = 4.60, SD = .93).",
      "location": "Experiment 4, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n unreported"
      }
    },
    {
      "id": "s66",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 4.6,
        "SD": 0.93
      },
      "quote": "Participants in the positive condition were more positive (M = 5.35, SD = .81) than participants in the neutral condition (M = 4.60, SD = .93).",
      "location": "Experiment 4, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n unreported"
      }
    },
    {
      "id": "s67",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.58,
        "SD": 0.78
      },
      "quote": "the attractive comparison target was rated more attractive than the (M = 5.58, SD = .78) than the unattractive target (M = 2.99, SD = .89), F(1,110) = 259.08, p < .001",
      "location": "Experiment 4, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n unreported"
      }
    },
    {
      "id": "s68",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 2.99,
        "SD": 0.89
      },
      "quote": "the attractive comparison target was rated more attractive than the (M = 5.58, SD = .78) than the unattractive target (M = 2.99, SD = .89), F(1,110) = 259.08, p < .001",
      "location": "Experiment 4, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n unreported"
      }
    },
    {
      "id": "s69",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 4.2,
        "SD": 0.21
      },
      "quote": "Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found",
      "location": "Experiment 4, No load conditions, control condition",
      "checkable": {
        "tools": [
          "grimmer_check",
          "sprite_reconstruct",
          "check_sd_or_se"
        ]
      }
    },
    {
      "id": "s70",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.64,
        "SD": 0.78
      },
      "quote": "regardless of whether participants upwardly compared (M = 5.64, SD = .78; F(1,124) = 17.39, p < .001)",
      "location": "Experiment 4, No load conditions",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s71",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.15,
        "SD": 0.81
      },
      "quote": "or downwardly compared (M = 5.15, SD = .81), F(1,124) = 11.90, p = .001",
      "location": "Experiment 4, No load conditions",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s72",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.47,
        "SD": 0.51
      },
      "quote": "Upward comparison led to more positive self-ratings (M = 5.47, SD = .51) than the control condition, F(1,124) = 17.89, p < .001",
      "location": "Experiment 4, No load conditions",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s73",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 3.24,
        "SD": 1.09
      },
      "quote": "downward comparison led to less positive self-ratings than the control condition (M = 3.24, SD = 1.09), F(1,124) = 10.37, p = .002",
      "location": "Experiment 4, No load conditions",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s74",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.71,
        "SD": 0.83
      },
      "quote": "upward comparison led to more positive self-ratings (M = 5.71, SD = .83), F(1,124) = 23.14, p < .001",
      "location": "Experiment 4, Cognitive load conditions",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s75",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 3.09,
        "SD": 0.94
      },
      "quote": "downward comparison led to less positive self-ratings (M = 3.09, SD = .94), t(124) = -3.30, p = .001",
      "location": "Experiment 4, Cognitive load conditions",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s76",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 3.33,
        "SD": 1.05
      },
      "quote": "upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05), F(1,124) = 18.83, p < .001",
      "location": "Experiment 4, Cognitive load conditions",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s77",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 5.53,
        "SD": 0.87
      },
      "quote": "downward comparison led to less positive self-ratings (M = 5.53, SD = .87), F(1,124) = 7.84, p = .006, relative to the control condition",
      "location": "Experiment 4, Cognitive load conditions",
      "checkable": {
        "tools": [],
        "reason": "cell n unreported"
      }
    },
    {
      "id": "s78",
      "source": "prose",
      "kind": "p_value",
      "values": {
        "p": 0.13
      },
      "quote": "with the only difference being that the high load, neutral mood induction, downward comparison condition differed from the control at the p = .13 level as opposed to the p \\ .05 level",
      "location": "Experiment 4, footnote 5",
      "checkable": {
        "tools": [],
        "reason": "an author-reported Tukey HSD result with no statistic printed beside it"
      }
    },
    {
      "id": "s79",
      "source": "prose",
      "kind": "other",
      "values": {
        "cronbach_alpha_mood": 0.91,
        "cronbach_alpha_selfeval": 0.71
      },
      "quote": "The four mood items were averaged to create an index of mood (Cronbach\u2019s alpha = .91) and the three self-ratings were averaged to create an index of self-evaluations (Cronbach\u2019s alpha = .71).",
      "location": "Pilot study, Measures",
      "checkable": {
        "tools": [
          "check_statistic_bounds"
        ],
        "reason": "both are inside [0,1]; no further check applies without item-level data"
      }
    },
    {
      "id": "s80",
      "source": "prose",
      "kind": "other",
      "values": {
        "alpha": 0.87
      },
      "quote": "participant responses to the three similarity questions were averaged (alpha = .87)",
      "location": "Experiment 3, Perceptions of similarity",
      "checkable": {
        "tools": [],
        "reason": "reliability coefficient with no item-level data to recompute from"
      }
    }
  ],
  "figures": [
    {
      "label": "Figure 1",
      "is_data_figure": false,
      "n_panels": 1,
      "caption": "Conceptual model of the steps leading to symmetric versus asymmetric responding to social comparison, with the shaded area showing the positive-mood reinterpretation path.",
      "carries_unique_values": false,
      "panels": [
        {
          "chart_type": "schematic",
          "shows": "A theoretical flow diagram of how ambiguous similarity information is reinterpreted under positive mood; no data are plotted."
        }
      ]
    },
    {
      "label": "Figure 2",
      "is_data_figure": true,
      "n_panels": 1,
      "page": 11,
      "caption": "In the presence of ambiguous distinctiveness information, positive mood leads to more positive self-evaluations, across upward and downward comparisons, than does neutral mood (from Experiment 3)",
      "carries_unique_values": false,
      "panels": [
        {
          "chart_type": "bar",
          "shows": "Experiment 3 self-evaluation means by mood and comparison direction; the same eight means are printed in Table 2, so the figure adds no values the text does not carry."
        }
      ]
    },
    {
      "label": "Figure 3",
      "is_data_figure": true,
      "n_panels": 1,
      "page": 13,
      "caption": "Asymmetric responses to comparisons in positive mood are moderated by cognitive load; responses without mood induction are not. From Experiment 4",
      "carries_unique_values": false,
      "panels": [
        {
          "chart_type": "bar",
          "shows": "Experiment 4 self-evaluation means by load, mood and direction; every mean and SD plotted here is also printed in the No load / Cognitive load results paragraphs."
        }
      ]
    }
  ],
  "findings": [
    {
      "id": "table2_selfeval_658_052",
      "location": "Table 2, Self-evaluation row, Positive mood / Unambiguous cue / Upward comparison",
      "technique": "sprite",
      "consistent": false,
      "severity": "impossible",
      "quote": "6.58 (.52)",
      "reported": {
        "mean": 6.58,
        "sd": 0.52,
        "n": 12,
        "scale": "1-7 integer, single item"
      },
      "computed": {
        "grim_consistent": true,
        "only_admissible_integer_total": 79,
        "required_sum_of_squares_window": [
          523,
          523.12
        ],
        "integer_Q_with_matching_parity_in_window": 0,
        "sprite_outcome": "no_solution_proven",
        "grimmer_outcome": "no valid (S, Q) combination",
        "tool_severity": "impossible"
      },
      "inputs": {
        "mean": 6.58,
        "sd": 0.52,
        "n": 12,
        "scale_min": 1,
        "scale_max": 7,
        "decimals_mean": 2,
        "decimals_sd": 2,
        "data_type": "likert",
        "discreteness_source": "stated"
      },
      "reproduction": "metascience sprite --mean 6.58 --sd 0.52 --n 12 --scale-min 1 --scale-max 7 --decimals-mean 2 --decimals-sd 2 --data-type likert --discreteness-source stated",
      "consequence": {
        "basis": "computed",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "This cell is one of the two Experiment 3 unambiguous-cue conditions whose contrast (6.58 vs 4.08) is the paper's evidence that positive-mood participants assimilate to comparison targets when the cue is unambiguous."
      },
      "notes": "The self-evaluation measure is a single seven-point integer item, so each participant contributed a whole number and the arithmetic is exact and bound-free -- this is a granularity failure (no integer sum-of-squares of the required parity exists), not a range violation, so it does not depend on the scale endpoints at all. Two residual assumptions: n = 12 per cell (not printed, but it follows from N = 96 over eight cells, is corroborated by the error df of 88 = 96 - 8, and is further corroborated by all eight Self-evaluation means being GRIM-consistent at exactly n = 12); and that .52 is an SD rather than a mislabelled SE. Cross-check: R rsprite2 independently rejected the same triple, its own GRIMMER screen returning 'The standard deviation is not consistent with this mean and number of observations'. Our wrapper records that as an exception rather than a clean infeasible=true and cautions that a raise alone is not proof, so the confirmation is substantive but not formally clean; the GRIM-family R cross-check held by the editorial stage is still outstanding."
    },
    {
      "id": "table2_selfeval_408_052",
      "location": "Table 2, Self-evaluation row, Positive mood / Unambiguous cue / Downward comparison",
      "technique": "sprite",
      "consistent": false,
      "severity": "impossible",
      "quote": "4.08 (.52)",
      "reported": {
        "mean": 4.08,
        "sd": 0.52,
        "n": 12,
        "scale": "1-7 integer, single item"
      },
      "computed": {
        "grim_consistent": true,
        "only_admissible_integer_total": 49,
        "required_sum_of_squares_window": [
          203,
          203.12
        ],
        "integer_Q_with_matching_parity_in_window": 0,
        "sprite_outcome": "no_solution_proven",
        "grimmer_outcome": "no valid (S, Q) combination",
        "tool_severity": "impossible"
      },
      "inputs": {
        "mean": 4.08,
        "sd": 0.52,
        "n": 12,
        "scale_min": 1,
        "scale_max": 7,
        "decimals_mean": 2,
        "decimals_sd": 2,
        "data_type": "likert",
        "discreteness_source": "stated"
      },
      "reproduction": "metascience sprite --mean 4.08 --sd 0.52 --n 12 --scale-min 1 --scale-max 7 --decimals-mean 2 --decimals-sd 2 --data-type likert --discreteness-source stated",
      "consequence": {
        "basis": "computed",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "The other half of the 6.58-vs-4.08 contrast that carries Experiment 3's unambiguous-cue conclusion; both cells of that contrast are individually unreconstructable."
      },
      "notes": "Same reasoning and same residual assumptions as the 6.58 (.52) cell. That the two impossible cells are the two halves of one reported contrast, and that both carry the identical SD of .52, is worth the editorial stage's attention; but note that an SD repeated across two cells is not itself anomalous and detect_duplication found no duplicated (mean, SD) pair anywhere in the paper. R rsprite2 rejected this triple too, via its GRIMMER screen."
    },
    {
      "id": "exp4_control_420_021",
      "location": "Experiment 4, No load conditions and Cognitive load conditions, control-condition mean",
      "technique": "grimmer",
      "consistent": false,
      "severity": "highly_suspicious",
      "quote": "Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found",
      "reported": {
        "mean": 4.2,
        "sd": 0.21,
        "n": "not reported"
      },
      "computed": {
        "grimmer_at_n_10": "impossible (total 42, no integer Q of matching parity)",
        "grimmer_at_n_15": "impossible (total 63, required Q window [265.19, 265.25])",
        "grimmer_at_n_20": "impossible (total 84, no integer Q of matching parity)",
        "sprite_at_n_15": "no_solution_proven",
        "tool_severity": "impossible",
        "recorded_one_rung_lower_because": "n is unreported and only n in {10, 15, 20} was tested"
      },
      "inputs": {
        "mean": 4.2,
        "sd": 0.21,
        "n": [
          10,
          15,
          20
        ],
        "scale_min": 1,
        "scale_max": 7,
        "decimals": 2,
        "decimals_sd": 2,
        "data_type": "likert",
        "discreteness_source": "stated"
      },
      "reproduction": "metascience grimmer --mean 4.2 --sd 0.21 --n 15 --scale-min 1 --scale-max 7 --decimals 2 --decimals-sd 2 --data-type likert --discreteness-source stated",
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 8,
        "explanation": "This single control mean is the reference point for all eight contrasts reported in Experiment 4's No load and Cognitive load sections, so every one of those F tests is computed against it."
      },
      "notes": "GRIMMER and SPRITE both return impossible at every sample size tested, and n = 10, 15 and 20 are the plausible small-group values a mean of exactly 4.20 admits. I record this one rung below the tools' `impossible` because the control-group n is never printed and I did not test every admissible n. Two innocent explanations to weigh: .21 may be a standard ERROR mislabelled as an SD -- check_sd_or_se shows the SE reading implies SD = 0.81 at n = 15, entirely ordinary for this scale and in line with every other dispersion the paper reports -- or the value may be a typo. Note that .21 is not implausibly large; check_sd_or_se returned `consistent` on the range test, because the problem is that .21 is too SMALL to arise from integers with a mean of 4.20 (the minimum-spread integer configuration, a mixture of 4s and 5s, forces an SD near 0.41)."
    },
    {
      "id": "exp3_attractiveness_above_scale_ceiling",
      "location": "Experiment 3, Manipulation check",
      "technique": "grim",
      "consistent": false,
      "severity": "highly_suspicious",
      "quote": "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001",
      "reported": {
        "mean": 7.33,
        "sd": 1.19,
        "stated_scale_max": 7
      },
      "computed": {
        "failure_mode": "out_of_range",
        "nearest_admissible_integer_total": 352,
        "implied_mean_at_that_total": 7.333333,
        "scale_maximum_stated_in_method": 7,
        "tool_severity": "impossible",
        "recorded_one_rung_lower_because": "an unstated switch to a nine-point scale in Experiment 3 would rescue the value"
      },
      "inputs": {
        "mean": 7.33,
        "n": 48,
        "scale_min": 1,
        "scale_max": 7,
        "decimals": 2,
        "data_type": "likert",
        "bound_source": "stated",
        "discreteness_source": "stated"
      },
      "reproduction": "metascience grim --mean 7.33 --n 48 --scale-min 1 --scale-max 7 --decimals 2 --data-type likert --bound-source stated --discreteness-source stated",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "The manipulation check establishing that upward targets were seen as more attractive -- the precondition for every Experiment 3 comparison -- reports a mean above the ceiling of the scale the Method assigns to it."
      },
      "notes": "Experiments 1 and 2 both print the anchors: 'seven-point scales (1 = not at all attractive and 7 = extremely attractive)'. Experiment 3's Method says it reused them -- 'rated their own attractiveness (on the seam measures used in Experiments 1 and 2)'. On that reading 7.33 cannot occur, and neither can the Experiment 3 mood mean of 7.33 on the 1-7 mood scale Experiment 2 defines. The range violation does not depend on n. I record this at highly_suspicious rather than the tool's `impossible` because a live alternative reading exists: Experiment 3's similarity items ARE explicitly nine-point, and the pilot's self-ratings were nine-point, so Experiment 3 may silently have used nine-point attractiveness and mood scales. Either way the paper contradicts itself -- either the means exceed the stated scale, or the Method sentence misdescribes the instrument. Two further oddities in the same paragraph, offered as observations rather than as arithmetic: the mood mean and the attractiveness mean are the identical value 7.33, and the upward and downward attractiveness cells carry the identical SD of 1.19."
    },
    {
      "id": "pilot_mood_anova_f_out_of_range",
      "location": "Pilot study, mood manipulation ANOVA",
      "technique": "rivets_anova",
      "consistent": false,
      "severity": "suspicious",
      "quote": "A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001.",
      "reported": {
        "F": 18.44,
        "df": "2, 42",
        "group_means": [
          7.2,
          6.15,
          4.98
        ],
        "group_sds": [
          0.93,
          0.52,
          0.98
        ]
      },
      "computed": {
        "achievable_F_range_at_equal_ns_15_15_15": [
          26.01,
          27.04
        ],
        "achievable_F_range_at_ns_10_25_10": [
          22.2,
          23.13
        ],
        "achievable_F_range_at_ns_8_29_8": [
          19.99,
          20.86
        ],
        "reported_F_in_range_under_all_three_allocations": false,
        "monte_carlo_samples_per_run": 5000
      },
      "inputs": {
        "means": [
          7.2,
          6.15,
          4.98
        ],
        "sds": [
          0.93,
          0.52,
          0.98
        ],
        "ns_tested": [
          [
            15,
            15,
            15
          ],
          [
            10,
            25,
            10
          ],
          [
            8,
            29,
            8
          ]
        ],
        "reported_f": 18.44,
        "decimals_mean": 2,
        "decimals_sd": 2
      },
      "reproduction": "metascience rivets-anova --means 7.20,6.15,4.98 --sds 0.93,0.52,0.98 --ns 15,15,15 --reported-f 18.44 --decimals-mean 2 --decimals-sd 2 --decimals-f 2",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "The pilot's claim that the mood induction worked; the reported F is smaller than the group statistics support, so the conclusion of a significant effect is unaffected in direction."
      },
      "notes": "Capped at `suspicious` against the tool's highly_suspicious because the per-condition sample sizes are NOT reported -- 15/15/15 is my inference from N = 45 over three conditions. I therefore tested two unequal allocations as well. All three place the reported F BELOW the achievable interval, and the interval only approaches 18.44 under an allocation (8/29/8) that is implausible for three randomly assigned conditions. The direction matters: the reported F understates the effect its own means and SDs imply, which is the opposite of the pattern one would expect from inflation."
    },
    {
      "id": "exp1_simple_effect_f_out_of_range",
      "location": "Experiment 1, Self-evaluations, unshared-birthday simple effect",
      "technique": "rivets_anova",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.",
      "reported": {
        "F": 6.95,
        "df": "1, 46",
        "means": [
          3.33,
          4.64
        ],
        "sds": [
          0.65,
          1.5
        ]
      },
      "computed": {
        "achievable_F_range_at_n_12_per_cell": [
          7.55,
          7.89
        ],
        "reported_F_in_range": false,
        "fraction_of_monte_carlo_draws_matching_reported_F": 0
      },
      "inputs": {
        "means": [
          3.33,
          4.64
        ],
        "sds": [
          0.65,
          1.5
        ],
        "ns": [
          12,
          12
        ],
        "reported_f": 6.95,
        "decimals_mean": 2,
        "decimals_sd": 2
      },
      "reproduction": "metascience rivets-anova --means 3.33,4.64 --sds 0.65,1.50 --ns 12,12 --reported-f 6.95 --decimals-mean 2 --decimals-sd 2 --decimals-f 2",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "The symmetric-contrast result in the unshared-birthday condition, which the paper uses to argue that ambiguous information is necessary for self-serving responding; the reported F is smaller than the means and SDs imply, so significance is unaffected."
      },
      "notes": "Cell sizes are not reported and 47 participants do not divide evenly into four cells, so n = 12 per cell is my inference; a split of 11 and 12 would lower the achievable interval somewhat. Capped at `suspicious` for that reason. Reported separately from the df problem in the same sentence. As a control on the method, the same tool run on Experiment 1's manipulation check returned `consistent`, so the discrepancy here is not an artefact of assuming cell sizes."
    },
    {
      "id": "exp1_manipcheck_f_consistent",
      "location": "Experiment 1, Manipulation check",
      "technique": "rivets_anova",
      "consistent": true,
      "severity": "consistent",
      "quote": "the upward comparison target was rated more attractive (M = 5.71, SD = .75) than the downward target (M = 3.57, SD = 1.47), F(1,43) = 38.80, p < .001",
      "reported": {
        "F": 38.8,
        "means": [
          5.71,
          3.57
        ],
        "sds": [
          0.75,
          1.47
        ]
      },
      "computed": {
        "achievable_F_range": [
          38.39,
          39.68
        ],
        "reported_F_in_range": true,
        "no_rivets_hand_calculation_signature": true
      },
      "inputs": {
        "means": [
          5.71,
          3.57
        ],
        "sds": [
          0.75,
          1.47
        ],
        "ns": [
          23,
          24
        ],
        "reported_f": 38.8,
        "decimals_mean": 2,
        "decimals_sd": 2
      },
      "reproduction": "metascience rivets-anova --means 5.71,3.57 --sds 0.75,1.47 --ns 23,24 --reported-f 38.80 --decimals-mean 2 --decimals-sd 2 --decimals-f 2",
      "notes": "Recorded because it is the control that makes the other two RIVETS results interpretable: with group sizes inferred the same way, this F sits comfortably inside its achievable interval."
    },
    {
      "id": "statcheck_nhst_sweep",
      "location": "Results sections, Pilot study through Experiment 4",
      "technique": "statcheck",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83.",
      "reported": {
        "n_nhst_results_extracted": 65
      },
      "computed": {
        "stats_found": 65,
        "errors_after_rounding_allowance": 3,
        "decision_errors": 0,
        "error_1_F_1_94_eq_1.50_reported_p": 0.83,
        "error_1_computed_p": 0.223732,
        "error_2_F_1_42_eq_0.27_reported_p": 0.76,
        "error_2_computed_p": 0.60606,
        "error_3_r_24_eq_0.53_reported_p": 0.008,
        "error_3_computed_p": 0.005355
      },
      "inputs": {
        "text": "concatenated Results paragraphs, Pilot study through Experiment 4"
      },
      "reproduction": "metascience statcheck --text \"<Results sections, Pilot study through Experiment 4>\"",
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "Zero decision errors: no reported p falls on the wrong side of its own significance threshold, so none of the three inconsistencies changes a conclusion the paper draws."
      },
      "notes": "The rate is 3 in 65, and statcheck's own methodology note is worth carrying forward: inconsistencies at this rate are near-universal in honest work and must never support a misconduct verdict alone. Of the three, one (F(1, 42) = .27) reconciles exactly once the df is corrected -- see pilot_selfeval_df_typo -- leaving two. The F(1, 94) = 1.50, p = .83 case is the substantive one: the computed p is .22, and the sentence also describes this result as 'Identical' to a preceding F of .31, which it is not."
    },
    {
      "id": "pilot_selfeval_df_typo",
      "location": "Pilot study, self-evaluations ANOVA",
      "technique": "recalc_f_to_p",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76.",
      "reported": {
        "F": 0.27,
        "df_as_printed": "1, 42",
        "p": 0.76
      },
      "computed": {
        "p_at_printed_df_1_42": 0.60606,
        "p_at_corrected_df_2_42": 0.764694,
        "achievable_p_interval_at_df_2_42": [
          0.760929,
          0.768479
        ],
        "reported_p_matches_corrected_df": true
      },
      "inputs": {
        "f_value": 0.27,
        "df1": 2,
        "df2": 42,
        "reported_p": 0.76,
        "decimals_f": 2,
        "decimals_p": 2
      },
      "reproduction": "metascience f-to-p --f-value 0.27 --df1 2 --df2 42 --reported-p 0.76 --decimals-f 2 --decimals-p 2",
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "The numerator df is misprinted as 1 where the three-group one-way ANOVA requires 2; the p-value the authors report is correct for the analysis they describe."
      },
      "notes": "This is the responsible reading of one of statcheck's three flags, and it exonerates rather than accuses: the sentence describes a one-way ANOVA over three mood conditions, which has df1 = 2, and the companion mood ANOVA two paragraphs earlier is correctly printed as F(2, 42). Recomputing at df1 = 2 reproduces the printed p = .76 to within its rounding interval. The defect is a typographical one in the df, not a wrong p."
    },
    {
      "id": "exp4_n_vs_error_df",
      "location": "Experiment 4, Participants and design versus Results and discussion",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "University (N = 193, 103 female) students participated in the study for monetary compensation.",
      "reported": {
        "stated_N": 193,
        "three_way_anova_error_df": 110,
        "contrast_error_df": 124
      },
      "computed": {
        "participants_implied_by_error_df_110_over_8_cells": 118,
        "participants_implied_by_error_df_124": "126 under a two-group reading",
        "stated_N_minus_implied_factorial_N": 75
      },
      "inputs": {
        "stated_n": 193,
        "error_dfs_reported": [
          110,
          124
        ]
      },
      "reproduction": "no command applies -- this is a cross-reference reading of the stated N against the error degrees of freedom the same section prints",
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 9,
        "explanation": "Every Experiment 4 test is reported on df that cannot be reconciled with the stated sample, so the number of participants contributing to the paper's cognitive-load conclusion is unclear."
      },
      "notes": "A 2x2x2 ANOVA with error df = 110 implies 118 participants in the factorial. The paper states 193 and describes only one further group, a hanging control. That leaves roughly 75 participants unaccounted for, far more than a single control cell plausibly holds, and the paper reports no exclusions or missing data. Ordinary listwise deletion is the innocent explanation but would need to be stated and is not. Cell sizes are never given anywhere in the paper."
    },
    {
      "id": "exp2_internal_df_inconsistency",
      "location": "Experiment 2, Manipulation check and Self-evaluations",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "only the mood manipulation significantly affected mood, F(1, 132) = 340.44, p < .001",
      "reported": {
        "stated_N": 141,
        "error_dfs_used_in_the_same_experiment": [
          118,
          124,
          132,
          138
        ]
      },
      "computed": {
        "participants_implied_by_error_df_118_over_8_cells": 126,
        "participants_implied_by_t_df_138": 140,
        "spread_between_largest_and_smallest_error_df": 20
      },
      "inputs": {
        "stated_n": 141,
        "error_dfs_reported": [
          118,
          124,
          132,
          138
        ]
      },
      "reproduction": "no command applies -- this is a cross-reference reading of the error degrees of freedom printed across one experiment's Results",
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 12,
        "explanation": "The analyses supporting Experiment 2's three-way interaction and all its follow-up contrasts are reported on four mutually inconsistent error df within a single dataset."
      },
      "notes": "Some variation is legitimate and expected here, because the hanging control condition is included in the contrast analyses and excluded from the factorial ANOVA -- that alone explains part of the gap between df 118 and df 132. What is not explained is the full spread: the factorial implies 126 participants, the contrasts imply 134 to 140, and the paper states 141 with no exclusions reported and no cell sizes given anywhere. Recorded as a reporting-transparency problem rather than an arithmetic one."
    },
    {
      "id": "exp1_simple_effect_df_exceeds_design",
      "location": "Experiment 1, Self-evaluations",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "F(1, 46) = 6.95, p = 011.",
      "reported": {
        "stated_N": 47,
        "full_factorial_error_df": 43,
        "simple_effect_error_df": 46
      },
      "computed": {
        "error_df_available_for_a_two_group_comparison_of_all_47": 45,
        "error_df_available_within_the_two_unshared_birthday_cells": "about 22",
        "reported_error_df": 46
      },
      "inputs": {
        "stated_n": 47,
        "factorial_error_df": 43,
        "simple_effect_error_df": 46
      },
      "reproduction": "no command applies -- this is a cross-reference reading of the reported df against the stated sample size and design",
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "The simple effect establishing symmetric contrast in the unshared-birthday condition is reported on more error df than the whole 47-participant design provides."
      },
      "notes": "The 2x2 ANOVA correctly reports F(1, 43), which is 47 - 4. A simple effect computed within the two unshared-birthday cells has roughly 22 error df; even a two-group comparison using all 47 participants has only 45. The printed 46 exceeds every reading. The same sentence also prints the p-value as 'p = 011' with the decimal point dropped, and Experiment 4 has the matching typo 'p = 001'. Most likely a transcription error, but it sits in a load-bearing result."
    },
    {
      "id": "exp3_df_internally_consistent",
      "location": "Experiment 3, Participants and Results",
      "technique": "not_computational",
      "consistent": true,
      "severity": "consistent",
      "quote": "University students (N = 96) participated in the study for course credit.",
      "reported": {
        "stated_N": 96,
        "factorial_error_df": 88,
        "planned_comparison_error_df": 94
      },
      "computed": {
        "expected_factorial_error_df": "96 - 8 = 88, matching",
        "expected_two_group_error_df": "96 - 2 = 94, matching",
        "implied_cell_n": 12
      },
      "inputs": {
        "stated_n": 96,
        "error_dfs_reported": [
          88,
          94
        ]
      },
      "reproduction": "no command applies -- this is a cross-reference reading of the reported df against the stated sample size and design",
      "notes": "Recorded because it is the counter-example that makes the Experiment 1, 2 and 4 df findings meaningful: Experiment 3's degrees of freedom reconcile exactly with its stated N under both the factorial and the two-group planned comparisons. This is also what licenses n = 12 per cell for the Table 2 granularity checks."
    },
    {
      "id": "cross_table_duplication",
      "location": "Table 1 (Experiment 2) and Table 2 (Experiment 3)",
      "technique": "duplication",
      "consistent": true,
      "severity": "consistent",
      "quote": "All means and standard deviations are presented in Table 1.",
      "reported": {
        "table1_cells": 8,
        "table2_cells": 16
      },
      "computed": {
        "n_blocks": 2,
        "n_cells_total": 24,
        "n_cross_source_comparisons": 128,
        "max_identical_pairs": 0,
        "duplicate_groups": 0
      },
      "inputs": {
        "blocks": [
          "Table 1 Experiment 2 self-evaluation, 8 cells",
          "Table 2 Experiment 3 self-evaluation and similarity, 16 cells"
        ],
        "decimals_mean": 2,
        "decimals_sd": 2,
        "provenance": "printed_table"
      },
      "reproduction": "metascience duplication-detect --blocks-from-tables 1,2 --decimals-mean 2 --decimals-sd 2 --provenance printed_table",
      "notes": "Experiments 2 and 3 used different participants, so the blocks are genuinely independent and a match would have been meaningful. None was found across 128 cross-source comparisons. This is a clean negative result and should be reported as such: whatever is wrong with the individual cells, the paper's two tables are not copies of one another."
    },
    {
      "id": "table2_full_table_sweep",
      "location": "Table 2 (Experiment 3), all 16 cells",
      "technique": "grimmer",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Effects of upward versus downward comparisons on self-evaluations and ratings of target similarity as function of mood and ambiguity of similarity information",
      "reported": {
        "cells": 16,
        "self_evaluation_cells": 8,
        "similarity_cells": 8
      },
      "computed": {
        "checks_run": 24,
        "checks_refused": 8,
        "results_consistent": 20,
        "results_suspicious": 4,
        "distinct_cells_failing": 2,
        "denominator_note": "2 failing cells out of the 8 that could be checked; the other 8 cells were refused outright"
      },
      "inputs": {
        "cells": 16,
        "variables": [
          "self_eval 1-7 single item",
          "similarity 1-9 mean of 3 items"
        ],
        "bindings": {
          "Self-evaluation": "self_eval",
          "Similarity": "similarity"
        },
        "provenance": "printed_table"
      },
      "reproduction": "metascience check-table --cells-from-table 2 --variables self_eval,similarity --provenance printed_table",
      "consequence": {
        "basis": "computed",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "Two of the eight checkable cells in the paper's only fully checkable table cannot be reconstructed from integer data."
      },
      "notes": "Produced by check_table, which dispatches grim/grimmer/sprite per cell; recorded under grimmer as the failing family. The denominator matters: of Table 2's 16 cells, only the 8 Self-evaluation cells could be checked at all, and 2 of those 8 fail. The 8 Similarity cells were refused because that variable is a mean of three items, whose granularity is 1/(3n) rather than 1/n, and the GRIM family has no items parameter -- checking them at 1/n would have manufactured impossibilities. That is a gap in this toolkit, not a property of the paper. This row aggregates the two cell-level findings above and should not be counted as a third failure."
    },
    {
      "id": "table1_granularity_not_checkable",
      "location": "Table 1 (Experiment 2), all 8 cells",
      "technique": "grim",
      "consistent": false,
      "severity": "indeterminate",
      "quote": "5.25 (.93)",
      "reported": {
        "cells": 8,
        "cell_n": "not reported"
      },
      "computed": {
        "factorial_N_implied_by_error_df_118": 126,
        "cells": 8,
        "implied_mean_cell_size": 15.75,
        "is_integer": false,
        "granularity_checks_runnable": 0
      },
      "inputs": {
        "table": "Table 1",
        "cells": 8,
        "n_per_cell": "unavailable"
      },
      "reproduction": "no command applies -- no granularity check can be run without a cell denominator",
      "notes": "All eight of Experiment 2's cell means and SDs are unchecked, and the reason is the paper's: cell sizes are never reported, and the factorial N implied by the error df (126) does not divide evenly into eight cells, so no single denominator can be assigned. GRIM, GRIMMER and SPRITE all need one. Running them at a guessed n would have been the fastest route to a false accusation here. Experiment 2 is therefore the least verifiable of the four studies, and its three-way interaction is one of the paper's headline results."
    },
    {
      "id": "effect_sizes_extraordinary",
      "location": "Table 2 Similarity row and Experiment 2 Manipulation check",
      "technique": "check_effect_plausibility",
      "consistent": false,
      "severity": "suspicious",
      "quote": "participants in a positive mood rated upward comparison targets as more similar to the self than downward comparison targets, F(1, 94) = 53.17, p < .001",
      "reported": {
        "exp3_similarity_ambiguous_upward": "7.06 (.53)",
        "exp3_similarity_ambiguous_downward": "4.14 (.59)",
        "exp2_positive_mood": "5.72 (.82)",
        "exp2_negative_mood": "2.98 (.83)"
      },
      "computed": {
        "exp3_similarity_hedges_g": 5.03,
        "exp3_similarity_ci95": [
          3.53,
          6.88
        ],
        "exp3_pooled_sd": 0.561,
        "exp2_mood_hedges_g": 3.29,
        "exp2_mood_ci95": [
          2.68,
          3.96
        ],
        "exp2_pooled_sd": 0.825
      },
      "inputs": {
        "comparison_1": {
          "mean1": 7.06,
          "sd1": 0.53,
          "n1": 12,
          "mean2": 4.14,
          "sd2": 0.59,
          "n2": 12
        },
        "comparison_2": {
          "mean1": 5.72,
          "sd1": 0.82,
          "n1": 45,
          "mean2": 2.98,
          "sd2": 0.83,
          "n2": 45
        }
      },
      "reproduction": "metascience effect-size --mean1 7.06 --sd1 0.53 --n1 12 --mean2 4.14 --sd2 0.59 --n2 12 --design between --provenance printed_table",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 2,
        "explanation": "The magnitudes are reported, not graded; they bear on how the editorial stage weighs the paper's effects as a set rather than on whether any individual test is correctly computed."
      },
      "notes": "Reported as values, capped at `suspicious` per the rule that an effect size can be improbable but never impossible. The tool's own note applies: |d| = 5.03 is remarkable in any field. The three ordinary explanations were checked. Dispersion is labelled SD throughout and the magnitudes (.53 to 1.19 on 7- and 9-point scales) are the size one expects of SDs, not SEMs -- an SEM reading would imply near-zero variance. There is no waitlist comparator; these are randomly assigned laboratory conditions. Units are the same scale on both sides of each contrast. The Experiment 2 mood effect (g = 3.29) is a manipulation check, where large effects are normal; the Experiment 3 similarity effect (g = 5.03) is a substantive dependent variable, where it is not. Both n values are inferred, not printed."
    },
    {
      "id": "exp3_design_sensitivity",
      "location": "Experiment 3, cell sizes",
      "technique": "verify_power_analysis",
      "consistent": true,
      "severity": "consistent",
      "quote": "University students (N = 96) participated in the study for course credit.",
      "reported": {
        "n_per_cell": 12,
        "n_per_two_cell_contrast": 24,
        "power_analysis_reported_by_paper": "none"
      },
      "computed": {
        "n_total_required_for_d_0.8_at_80_percent_power": 52,
        "n_per_group_required": 26,
        "actual_n_total_for_a_two_cell_contrast": 24,
        "ratio_actual_to_required": 0.462,
        "adequately_powered_for_d_0.8": false
      },
      "inputs": {
        "test_type": "two_sample_t",
        "effect_size": 0.8,
        "alpha": 0.05,
        "power": 0.8,
        "tails": 2,
        "actual_n": 24
      },
      "reproduction": "metascience required-n --test-type two_sample_t --effect-size 0.8 --alpha 0.05 --power 0.8 --tails 2 --actual-n 24",
      "notes": "Context, not a defect, and the tool renders no verdict. No study in the paper reports an a-priori power analysis, so there is nothing to reproduce; this is the design-sensitivity question asked of the paper's own cell sizes instead. A 12-versus-12 contrast has under half the sample needed to detect even a large (d = 0.8) effect at 80% power, yet Experiment 3 reports effects several times that size at very small p. Small studies are not wrong, but a significant result from an underpowered design sits exactly where selection inflates estimates -- which is the relevant frame for reading this paper's effect sizes."
    },
    {
      "id": "xml_pdf_table2_reconciled",
      "location": "Table 2, both sources",
      "technique": "reconcile",
      "consistent": true,
      "severity": "consistent",
      "quote": "6.58 (.90)",
      "reported": {
        "xml_cells": 16,
        "pdf_cells": 16
      },
      "computed": {
        "cells_compared": 16,
        "cells_disagreeing": 0,
        "xml_alignment_uncertain": false,
        "xml_image_only": false,
        "spans_merged_header_cells": 6
      },
      "inputs": {
        "xml_source": "extract_xml table 2",
        "pdf_source": "extract_pdf page 11, docling grid"
      },
      "reproduction": "metascience get-table --xml-path 10.1007--s11031-011-9216-y.xml --table-num 2",
      "notes": "Recorded because two findings graded `impossible` rest on cells from this table, and a transcription error would be the likeliest innocent explanation for them. The independently extracted PDF grid reproduces all 16 cells identically, including the two failing values 6.58 (.52) and 4.08 (.52). Neither table in the paper was flagged alignment_uncertain or image_only, and the six merged cells are all in the header rows, so no data value was duplicated by the extraction."
    },
    {
      "id": "methods_typo_in_outcome_definition",
      "location": "Experiment 3, Procedure",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Participants reported their major, gender, age, and then rated their own attractiveness (on the seam measures used in Experiments 1 and 2).",
      "reported": {
        "printed_word": "seam",
        "intended_word": "same"
      },
      "computed": {},
      "inputs": {
        "sentence": "Experiment 3 Procedure, dependent-measure definition"
      },
      "reproduction": "no command applies -- this is a reading of the paper's Methods text",
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "This is the only sentence defining what scale Experiment 3's outcome was measured on, and it is the sentence the scale-ceiling contradiction turns on."
      },
      "notes": "A typo in an acknowledgement is nothing; this one is in the sentence that defines the primary outcome measure of an experiment, and it is precisely the sentence that has to be relied on to determine whether the Experiment 3 means of 7.33 exceed their scale. Recorded as evidence that the passage was not closely read, not as an arithmetic problem. The paper also prints 'Fours studies examine' in the Current studies section and 'when participants were under cognitive loaded' in the General discussion."
    },
    {
      "id": "exp1_main_effects_self_contradiction",
      "location": "Experiment 1, Self-evaluations",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "A 2(similarity cue: shared birthday vs. different birthday) \u00d7 2(direction: upward vs. downward) ANOVA revealed significant main effects of cue and direction of comparison such that those sharing a birthday reported higher self-evaluations (M = 4.92, SD = 1.14) than those not sharing a birthday (M = 3.96, SD = 1.3), F(1, 43) = 7.77, p = .008. No other main effects were significant.",
      "reported": {
        "main_effects_claimed_significant": 2,
        "main_effect_F_statistics_printed": 1
      },
      "computed": {},
      "inputs": {
        "passage": "Experiment 1 Self-evaluations, opening paragraph"
      },
      "reproduction": "no command applies -- this is a reading of two adjacent sentences in the Results",
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "The main effect of direction of comparison is asserted to be significant and then, one sentence later, implicitly denied, with no statistic printed either way."
      },
      "notes": "The passage claims significant main effects of BOTH cue and direction, prints an F for the cue effect only, and then states that no other main effects were significant -- which contradicts the claim about direction just made. In a 2x2 there are exactly two main effects, so 'no other' can only refer to direction. Unresolvable from the text: no statistic is given for the direction main effect anywhere in Experiment 1."
    },
    {
      "id": "data_availability_state_but_withhold",
      "location": "Experiment 3, footnote 4",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Complete data and results available from the first author.",
      "reported": {
        "data_availability_mechanism": "on request from the first author"
      },
      "computed": {},
      "inputs": {
        "footnote": "footnote 4, page 12 of the PDF"
      },
      "reproduction": "no command applies -- this is a reading of the paper's data-availability footnote",
      "notes": "The paper's only data-availability statement offers the complete data on request rather than depositing it. This is entirely ordinary for a 2011 psychology paper and is not evidence of anything on its own; it is recorded because several of the anomalies above (unreported cell sizes in every study, irreconcilable error df, two unreconstructable cells) are exactly the questions that access to the raw data would settle, and because the article has since been retracted."
    },
    {
      "id": "authors_own_multiplicity_disclosure",
      "location": "Experiment 4, footnote 5",
      "technique": "not_computational",
      "consistent": true,
      "severity": "consistent",
      "quote": "These analyses revealed a similar pattern of significant differences from the control condition, with the only difference being that the high load, neutral mood induction, downward comparison condition differed from the control at the p = .13 level as opposed to the p \\ .05 level.",
      "reported": {
        "correction_method": "Tukey HSD",
        "contrasts_losing_significance": 1,
        "p_after_correction": 0.13
      },
      "computed": {},
      "inputs": {
        "footnote": "footnote 5, page 13 of the PDF"
      },
      "reproduction": "no command applies -- this is a reading of the authors' own reported sensitivity analysis",
      "notes": "Recorded as good practice rather than as a problem, and as the reason I did not run multiplicity_report on Experiment 4's contrast family: the authors performed the correction themselves and disclosed which result does not survive it. One contrast drops from p < .05 to p = .13 under Tukey HSD. Experiment 2 carries a parallel footnote. The disclosure is honest and should be weighed against the paper's other reporting problems."
    }
  ],
  "unchecked": [
    {
      "location": "Table 1 (Experiment 2), all 8 self-evaluation cells",
      "reason": "Cell sizes are never reported and the factorial N implied by the error df (126) does not divide evenly into 8 cells, so no denominator can be assigned. GRIM, GRIMMER and SPRITE all require one; running them at a guessed n is the commonest route to a false accusation."
    },
    {
      "location": "Table 2 (Experiment 3), all 8 Similarity-row cells",
      "reason": "The similarity index is a MEAN of three nine-point items, so its granularity is 1/(3n) rather than 1/n. check_table refused all 8 cells because grim_test has no `items` parameter. This is a gap in our toolkit, not a property of the paper; the R `scrutiny` GRIM implementation does take an items argument and could check these."
    },
    {
      "location": "Pilot study, mood index and self-evaluation index means (6 mean/SD pairs)",
      "reason": "Both are multi-item composite means (4 items and 3 items) on 1-9 scales, and per-condition sample sizes are not reported. Neither the items granularity nor the denominator is available."
    },
    {
      "location": "All prose mean (SD) pairs in Experiments 1, 2 and 4 (roughly 25 pairs)",
      "reason": "The paper reports no cell sizes in any of the four experiments. Where a group n could be inferred from the design I ran the check; where the inference was not defensible I did not substitute a guess."
    },
    {
      "location": "Experiment 3, mood and attractiveness manipulation-check means (7.33, 5.44, 7.33, 4.17)",
      "reason": "GRIMMER and SPRITE need a settled scale, and which scale Experiment 3 used is precisely what is in dispute -- the Method says the 7-point measures of Experiments 1 and 2, while two of the reported means exceed 7. Only the range check, which is scale-agnostic in direction, could be run."
    },
    {
      "location": "Figures 2 and 3",
      "reason": "Both plot means that are also printed in Table 2 and in the Experiment 4 Results text respectively, so no unique value is lost; no figure-pixel measurement was attempted and none was needed. Figure 1 is a conceptual schematic with no data."
    },
    {
      "location": "Supplementary materials",
      "reason": "None are provided with this paper. Footnote 4 states that complete data and results are available from the first author rather than deposited, so there is no supplement to read."
    },
    {
      "location": "Multiplicity across the Experiment 2 and Experiment 4 contrast families",
      "reason": "Deliberately not run. The authors report their own Tukey HSD correction for both families in footnotes 2 and 5 and disclose which contrast fails it, so multiplicity_report would double-count a correction the paper already applied. multiplicity_report excludes author-corrected tests by design."
    },
    {
      "location": "GRIM-family R cross-check (r_grim_ground_truth) on the two Table 2 cells graded impossible",
      "reason": "That tool is held by the editorial stage, not this one. The SPRITE cross-check was run and R's rsprite2 rejected both triples via its own GRIMMER screen, but it did so by raising rather than returning a clean infeasible=true, so the confirmation is substantive rather than formally clean."
    }
  ],
  "coverage": {
    "stats_found": 80,
    "tables_checked": [
      "Table 1 (Experiment 2) -- typed, denominators unavailable, 0 of 8 cells checkable",
      "Table 2 (Experiment 3) -- typed and swept, 24 checks run, 8 refused, 2 of 8 checkable cells failing",
      "Table 2 cross-checked against the independently extracted PDF grid, 16 of 16 cells identical"
    ],
    "tools_run": [
      "extract_xml",
      "get_table",
      "extract_pdf",
      "parse_cells_typed",
      "check_table",
      "grim_check",
      "grimmer_check",
      "sprite_reconstruct",
      "r_sprite_ground_truth",
      "statcheck",
      "recalc_f_to_p",
      "rivets_anova",
      "detect_duplication",
      "check_sd_or_se",
      "check_effect_plausibility",
      "required_n"
    ]
  },
  "second_look": {
    "n_accusatory": 16,
    "n_flagged": 16,
    "by_marker": {
      "quote_not_located": 16
    },
    "items": [
      {
        "id": "table2_selfeval_658_052",
        "severity": "impossible",
        "location": "Table 2, Self-evaluation row, Positive mood / Unambiguous cue / Upward comparison",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table2_selfeval_408_052",
        "severity": "impossible",
        "location": "Table 2, Self-evaluation row, Positive mood / Unambiguous cue / Downward comparison",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "exp4_control_420_021",
        "severity": "highly_suspicious",
        "location": "Experiment 4, No load conditions and Cognitive load conditions, control-condition mean",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "exp3_attractiveness_above_scale_ceiling",
        "severity": "highly_suspicious",
        "location": "Experiment 3, Manipulation check",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "pilot_mood_anova_f_out_of_range",
        "severity": "suspicious",
        "location": "Pilot study, mood manipulation ANOVA",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "exp1_simple_effect_f_out_of_range",
        "severity": "suspicious",
        "location": "Experiment 1, Self-evaluations, unshared-birthday simple effect",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "statcheck_nhst_sweep",
        "severity": "suspicious",
        "location": "Results sections, Pilot study through Experiment 4",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "pilot_selfeval_df_typo",
        "severity": "suspicious",
        "location": "Pilot study, self-evaluations ANOVA",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "exp4_n_vs_error_df",
        "severity": "suspicious",
        "location": "Experiment 4, Participants and design versus Results and discussion",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "exp2_internal_df_inconsistency",
        "severity": "suspicious",
        "location": "Experiment 2, Manipulation check and Self-evaluations",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "exp1_simple_effect_df_exceeds_design",
        "severity": "suspicious",
        "location": "Experiment 1, Self-evaluations",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table2_full_table_sweep",
        "severity": "suspicious",
        "location": "Table 2 (Experiment 3), all 16 cells",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "effect_sizes_extraordinary",
        "severity": "suspicious",
        "location": "Table 2 Similarity row and Experiment 2 Manipulation check",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "methods_typo_in_outcome_definition",
        "severity": "suspicious",
        "location": "Experiment 3, Procedure",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "exp1_main_effects_self_contradiction",
        "severity": "suspicious",
        "location": "Experiment 1, Self-evaluations",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "data_availability_state_but_withhold",
        "severity": "suspicious",
        "location": "Experiment 3, footnote 4",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      }
    ],
    "note": "16 of 16 accusation(s) carry a named weakness in their evidence. Each is listed with what would settle it. This is a worklist, not a verdict: none of these is wrong because it is listed, and a marker you resolve should be recorded in `triage` like any other triage decision."
  }
}
```

Triage these findings (confirm / deprioritize / reinterpret per the rulebook — especially baseline-similarity results), add the contextual reasoning the sweep cannot do, and emit the report JSON.