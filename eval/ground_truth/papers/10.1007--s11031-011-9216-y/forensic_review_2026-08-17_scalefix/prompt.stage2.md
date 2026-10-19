Write the editorial forensic review for this paper.

Read the paper text and tables with `extract_xml`: `/mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.xml` (tables come back as structured cells; the PDF, where one exists, is only for figures and cross-checking)

What the sweep actually ran, which is the DENOMINATOR your verdict sits in:

```json
{
  "checks_passed": 24,
  "of_which_collapsed_by_check_table": 20,
  "checks_refused_indeterminate": 3,
  "checks_flagged": 15,
  "checks_total": 42,
  "by_severity": {
    "impossible": 3,
    "suspicious": 12,
    "indeterminate": 3,
    "consistent": 4
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
  "schema_version": "1.0",
  "paper_id": "10.1007--s11031-011-9216-y",
  "paper_title": "RETRACTED ARTICLE: Happiness as alchemy: Positive mood leads to self-serving responses to social comparisons",
  "paper_metadata": {
    "authors": "Camille S. Johnson, Diederik A. Stapel",
    "doi": "10.1007/s11031-011-9216-y",
    "journal": "Motivation and Emotion",
    "year": "2011",
    "study_design": "Four between-subjects factorial laboratory experiments plus a pilot study; article is marked RETRACTED on every page of the PDF"
  },
  "anatomy": {
    "studies": [
      {
        "id": "pilot",
        "label": "Pilot study: mood induction validation",
        "design": "rct",
        "n": 45,
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
            "label": "neutral filler control",
            "n": 15
          }
        ],
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "sample_flow": [
          {
            "stage": "participants reported",
            "n": 45,
            "unit": "participants"
          },
          {
            "stage": "implied by ANOVA error df (42) + 3 groups",
            "n": 45,
            "unit": "participants",
            "inferred": true
          }
        ]
      },
      {
        "id": "exp1",
        "label": "Experiment 1: positive mood, shared vs different birthday, upward vs downward target",
        "design": "rct",
        "n": 47,
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "sample_flow": [
          {
            "stage": "participants reported",
            "n": 47,
            "unit": "participants"
          },
          {
            "stage": "implied by ANOVA error df (43) + 4 cells",
            "n": 47,
            "unit": "participants",
            "inferred": true
          }
        ]
      },
      {
        "id": "exp2",
        "label": "Experiment 2: 2 mood x 2 direction x 2 birthday cue, plus hanging control",
        "design": "rct",
        "n": 141,
        "n_per_group": [
          {
            "label": "factorial cells (8) combined",
            "n": 126
          },
          {
            "label": "no-mood no-comparison control",
            "n": 15
          }
        ],
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "sample_flow": [
          {
            "stage": "participants reported",
            "n": 141,
            "unit": "participants"
          },
          {
            "stage": "implied in factorial by ANOVA error df (118) + 8 cells",
            "n": 126,
            "unit": "participants",
            "inferred": true
          },
          {
            "stage": "control, as the complement of the factorial",
            "n": 15,
            "unit": "participants",
            "inferred": true
          }
        ]
      },
      {
        "id": "exp3",
        "label": "Experiment 3: 2 mood x 2 direction x 2 ambiguity of similarity cue",
        "design": "rct",
        "n": 96,
        "n_per_group": [
          {
            "label": "each of 8 crossed cells",
            "n": 12
          }
        ],
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "sample_flow": [
          {
            "stage": "participants reported",
            "n": 96,
            "unit": "participants"
          },
          {
            "stage": "implied by ANOVA error df (88) + 8 cells",
            "n": 96,
            "unit": "participants",
            "inferred": true
          }
        ]
      },
      {
        "id": "exp4",
        "label": "Experiment 4: 2 mood x 2 direction x 2 cognitive load, plus hanging control",
        "design": "rct",
        "n": 193,
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": false,
        "sample_flow": [
          {
            "stage": "participants reported in Method",
            "n": 193,
            "unit": "participants"
          },
          {
            "stage": "implied in factorial by ANOVA error df (110) + 8 cells",
            "n": 118,
            "unit": "participants",
            "inferred": true
          },
          {
            "stage": "implied in total by contrast error df (124) + 9 groups",
            "n": 133,
            "unit": "participants",
            "inferred": true
          }
        ]
      }
    ],
    "hypotheses": [
      {
        "id": "h1",
        "study_id": "exp1",
        "statement": "Positive mood leads to asymmetric, self-serving responses to social comparison targets (assimilation upward, contrast downward) only when ambiguous similarity information is present.",
        "status": "confirmatory",
        "appears_in_abstract": true,
        "confidence": "high",
        "provenance_quote": "In the presence of ambiguous information, participants in a positive mood were expected to respond asymmetrically: assimilating to upward comparison targets and contrasting with downward targets."
      },
      {
        "id": "h2",
        "study_id": "exp2",
        "statement": "Negative mood produces symmetric contrast rather than asymmetric self-serving responding, ruling out a mood-congruency account.",
        "status": "confirmatory",
        "appears_in_abstract": true,
        "confidence": "high",
        "provenance_quote": "However, the responses of participants in a negative mood were expected to be symmetric: contrast with both upward and downward comparison others."
      },
      {
        "id": "h3",
        "study_id": "exp3",
        "statement": "Self-serving responding requires the similarity information to be ambiguous; explicitly unambiguous similarity information produces symmetric assimilation regardless of mood.",
        "status": "confirmatory",
        "appears_in_abstract": true,
        "confidence": "high",
        "provenance_quote": "Because the effects of positive mood are predicted to require ambiguous information, self-serving effects were expected to occur only when similarity information was ambiguous and open to alternative interpretation."
      },
      {
        "id": "h4",
        "study_id": "exp4",
        "statement": "Asymmetric self-serving responding under positive mood is effortful and is abolished by cognitive load.",
        "status": "confirmatory",
        "appears_in_abstract": true,
        "confidence": "high",
        "provenance_quote": "When participants were under load, the positive mood effects on responses to downward comparisons were expected to dissipate, reflecting the resource-demanding nature of self-serving asymmetric interpretations."
      }
    ],
    "variables": [
      {
        "id": "selfeval7",
        "name": "Self-evaluation (own attractiveness)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_item",
        "lower_bound": 1,
        "upper_bound": 7,
        "n_items": 1,
        "derivation": "measured",
        "units": "scale points",
        "confidence": "high",
        "provenance_quote": "Participants also rated their own attractiveness (How attractive are you?) on a seven-point scale (1 = not at all, 7 = extremely)."
      },
      {
        "id": "targetattr7",
        "name": "Rated attractiveness of the comparison target",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_item",
        "lower_bound": 1,
        "upper_bound": 7,
        "n_items": 1,
        "derivation": "measured",
        "units": "scale points",
        "confidence": "high",
        "provenance_quote": "rated their own attractiveness and the target's attractiveness on seven-point scales (1 = not at all attractive and 7 = extremely attractive)"
      },
      {
        "id": "mood7",
        "name": "Self-reported mood (Experiments 2 and 4)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_item",
        "lower_bound": 1,
        "upper_bound": 7,
        "n_items": 1,
        "derivation": "measured",
        "units": "scale points",
        "confidence": "high",
        "provenance_quote": "Participants also reported how positive or negative they felt at that moment (1 = negative mood and 7 = positive mood)"
      },
      {
        "id": "moodindex9",
        "name": "Mood index (pilot study)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_composite",
        "lower_bound": 1,
        "upper_bound": 9,
        "n_items": 4,
        "derivation": "mean_of_items",
        "derived_from": "four nine-point bipolar mood items, averaged (Cronbach's alpha = .91)",
        "units": "scale points",
        "confidence": "high",
        "provenance_quote": "The four mood items were averaged to create an index of mood (Cronbach's alpha = .91)"
      },
      {
        "id": "selfindex9",
        "name": "Self-evaluation index (pilot study)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_composite",
        "lower_bound": 1,
        "upper_bound": 9,
        "n_items": 3,
        "derivation": "mean_of_items",
        "derived_from": "intelligent, competent, successful, each on a nine-point Likert scale, averaged (alpha = .71)",
        "units": "scale points",
        "confidence": "high",
        "provenance_quote": "they rated how well each of the following words described them on nine-point Likert scales (1 = not at all me, 9 = very much me): intelligent, competent, and successful"
      },
      {
        "id": "similarity9",
        "name": "Similarity index (Experiment 3)",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "likert_composite",
        "lower_bound": 1,
        "upper_bound": 9,
        "n_items": 3,
        "derivation": "mean_of_items",
        "derived_from": "three nine-point similarity questions, averaged (alpha = .87)",
        "units": "scale points",
        "confidence": "high",
        "provenance_quote": "participant responses to the three similarity questions were averaged (alpha = .87)"
      },
      {
        "id": "moodcond",
        "name": "Mood induction condition",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "nominal_category",
        "levels": [
          "positive",
          "negative",
          "neutral/control"
        ],
        "n_categories": 3,
        "derivation": "measured",
        "confidence": "high",
        "provenance_quote": "A 2(mood: positive vs. negative) x 2(direction of comparison: upward vs. downward) x 2(similarity cue: shared birthday vs. different birthday) factorial design was used, with an additional no-mood, no comparison control condition."
      },
      {
        "id": "direction",
        "name": "Direction of comparison",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "levels": [
          "upward (more attractive target)",
          "downward (less attractive target)"
        ],
        "n_categories": 2,
        "derivation": "measured",
        "confidence": "high",
        "provenance_quote": "2(direction of comparison: upward vs. downward)"
      },
      {
        "id": "cue",
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
        "n_categories": 2,
        "derivation": "measured",
        "confidence": "high",
        "provenance_quote": "2(cue: shared birthday vs. different birthday)"
      },
      {
        "id": "load",
        "name": "Cognitive load (Experiment 4)",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "levels": [
          "load (8-digit number rehearsal)",
          "no load"
        ],
        "n_categories": 2,
        "derivation": "measured",
        "confidence": "high",
        "provenance_quote": "2(load: load vs. no load) factorial design"
      }
    ],
    "tests": [
      {
        "id": "t_pilot_mood_anova",
        "study_id": "pilot",
        "test_type": "one_way_anova",
        "location": "Pilot study, first results paragraph",
        "outcome_var": "moodindex9",
        "predictor_vars": [
          "moodcond"
        ],
        "n": 45,
        "df": "2, 42",
        "statistic_value": 18.44,
        "p_value": 0.001,
        "p_is_threshold": true,
        "hypothesis_id": "h1",
        "is_stated_primary_outcome": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001.",
        "assumption_checks_reported": []
      },
      {
        "id": "t_pilot_pos_vs_ctrl",
        "study_id": "pilot",
        "test_type": "independent_t",
        "location": "Pilot study, first results paragraph",
        "outcome_var": "moodindex9",
        "predictor_vars": [
          "moodcond"
        ],
        "n": 45,
        "df": "42",
        "statistic_value": 3.43,
        "p_value": 0.001,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "Participants in the positive mood condition reported more positive mood (M = 7.20, SD = .93) that those in the control condition (M = 6.15, SD = .52), t(42) = 3.43, p = .001."
      },
      {
        "id": "t_pilot_neg_vs_ctrl",
        "study_id": "pilot",
        "test_type": "independent_t",
        "location": "Pilot study, first results paragraph",
        "outcome_var": "moodindex9",
        "predictor_vars": [
          "moodcond"
        ],
        "n": 45,
        "df": "42",
        "statistic_value": -3.8,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "Participants in the negative mood condition reported more negative mood (M = 4.98, SD = .98) than those in the control condition, t(42) = -3.80, p < .001."
      },
      {
        "id": "t_pilot_selfeval_anova",
        "study_id": "pilot",
        "test_type": "one_way_anova",
        "location": "Pilot study, second results paragraph",
        "outcome_var": "selfindex9",
        "predictor_vars": [
          "moodcond"
        ],
        "n": 45,
        "df": "1, 42",
        "statistic_value": 0.27,
        "p_value": 0.76,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76."
      },
      {
        "id": "t_e1_manip",
        "study_id": "exp1",
        "test_type": "one_way_anova",
        "location": "Experiment 1, Manipulation check",
        "outcome_var": "targetattr7",
        "predictor_vars": [
          "direction"
        ],
        "n": 47,
        "df": "1, 43",
        "statistic_value": 38.8,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "the upward comparison target was rated more attractive (M = 5.71, SD = .75) than the downward target (M = 3.57, SD = 1.47), F(1,43) = 38.80, p < .001."
      },
      {
        "id": "t_e1_cue_main",
        "study_id": "exp1",
        "test_type": "one_way_anova",
        "location": "Experiment 1, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "cue"
        ],
        "n": 47,
        "df": "1, 43",
        "statistic_value": 7.77,
        "p_value": 0.008,
        "p_is_threshold": false,
        "hypothesis_id": "h1",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "those sharing a birthday reported higher self-evaluations (M = 4.92, SD = 1.14) than those not sharing a birthday (M = 3.96, SD = 1.3), F(1, 43) = 7.77, p = .008."
      },
      {
        "id": "t_e1_interaction",
        "study_id": "exp1",
        "test_type": "one_way_anova",
        "location": "Experiment 1, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "cue",
          "direction"
        ],
        "n": 47,
        "df": "1, 43",
        "statistic_value": 5.99,
        "p_value": 0.019,
        "p_is_threshold": false,
        "hypothesis_id": "h1",
        "is_stated_primary_outcome": true,
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "These main effects were qualified by the significant and expected interaction effect on self-evaluations, F(1, 43) = 5.99, p = .019."
      },
      {
        "id": "t_e1_simple_unshared",
        "study_id": "exp1",
        "test_type": "one_way_anova",
        "location": "Experiment 1, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "direction"
        ],
        "n": 47,
        "df": "1, 46",
        "statistic_value": 6.95,
        "p_value": 0.011,
        "p_is_threshold": false,
        "hypothesis_id": "h1",
        "correction_applied": "none",
        "confidence": "medium",
        "provenance_quote": "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011."
      },
      {
        "id": "t_e2_mood_manip",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Manipulation check",
        "outcome_var": "mood7",
        "predictor_vars": [
          "moodcond"
        ],
        "n": 141,
        "df": "1, 132",
        "statistic_value": 340.44,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "only the mood manipulation significantly affected mood, F(1, 132) = 340.44, p < .001."
      },
      {
        "id": "t_e2_attr_manip",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Manipulation check",
        "outcome_var": "targetattr7",
        "predictor_vars": [
          "direction"
        ],
        "n": 141,
        "df": "1, 118",
        "statistic_value": 716.92,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "The upward comparison target was rated more attractive (M = 5.98, SD = .69) than the downward target (M = 2.46, SD = .74), F(1,118) = 716.92, p < .001."
      },
      {
        "id": "t_e2_threeway",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "moodcond",
          "direction",
          "cue"
        ],
        "n": 126,
        "df": "1, 118",
        "statistic_value": 5.13,
        "p_value": 0.03,
        "p_is_threshold": false,
        "hypothesis_id": "h2",
        "is_stated_primary_outcome": true,
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "which revealed the expected three-way interaction effect on self-evaluations, F(1, 118) = 5.13, p = .03."
      },
      {
        "id": "t_e2_cue_main",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "cue"
        ],
        "n": 126,
        "df": "1, 118",
        "statistic_value": 21.84,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "The analysis also revealed significant effects of similarity cue, F(1, 118) = 21.84, p < .001;"
      },
      {
        "id": "t_e2_dir_main",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "direction"
        ],
        "n": 126,
        "df": "1, 118",
        "statistic_value": 131.87,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "direction, F(1, 118) = 131.87, p < .001; and mood, F(1, 118) = 14.48, p < .001."
      },
      {
        "id": "t_e2_mood_x_cue",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "moodcond",
          "cue"
        ],
        "n": 126,
        "df": "1, 118",
        "statistic_value": 18.84,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "the two-way interaction effects of mood and similarity cue, F(1, 118) = 18.84, p < .001;"
      },
      {
        "id": "t_e2_mood_x_dir",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "moodcond",
          "direction"
        ],
        "n": 126,
        "df": "1, 118",
        "statistic_value": 11.74,
        "p_value": 0.001,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "mood and direction, F(1, 118) = 11.74, p = .001;"
      },
      {
        "id": "t_e2_cue_x_dir",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "cue",
          "direction"
        ],
        "n": 126,
        "df": "1, 118",
        "statistic_value": 14.11,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and similarity cue and direction, F(1, 118) = 14.11, p < .001, were also significant."
      },
      {
        "id": "t_e2_pos_dir",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Positive mood",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "direction"
        ],
        "df": "1, 124",
        "statistic_value": 14.79,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "in the positive mood conditions, direction of comparison, F(1, 124) = 14.79, p < .001;"
      },
      {
        "id": "t_e2_pos_cue",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Positive mood",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "cue"
        ],
        "df": "1, 124",
        "statistic_value": 18.61,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "presence of similarity cue (shared birthday or not), F(1, 124) = 18.61, p < .001;"
      },
      {
        "id": "t_e2_pos_interaction",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Positive mood",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "cue",
          "direction"
        ],
        "df": "1, 124",
        "statistic_value": 9.39,
        "p_value": 0.003,
        "p_is_threshold": false,
        "hypothesis_id": "h1",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and the interaction effect of direction of comparison and similarity information, F(1, 124) = 9.39, p = .003, all significantly influenced self-ratings."
      },
      {
        "id": "t_e2_c1",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Positive mood contrasts vs control",
        "outcome_var": "selfeval7",
        "df": "1, 132",
        "statistic_value": 13.76,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "participants in both the upward, F(1,132) = 13.76, p < .001, and downward, F(1,132) = 21.53, p < .001, comparison conditions rated themselves more positively."
      },
      {
        "id": "t_e2_c2",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Positive mood contrasts vs control",
        "outcome_var": "selfeval7",
        "df": "1, 132",
        "statistic_value": 21.53,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and downward, F(1,132) = 21.53, p < .001, comparison conditions rated themselves more positively."
      },
      {
        "id": "t_e2_c3",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Positive mood contrasts vs control",
        "outcome_var": "selfeval7",
        "df": "1, 132",
        "statistic_value": 14.06,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "they lowered self-ratings after upward comparison, F(1,132) = 14.06, p < .001 and raised self-ratings after downward comparison, F(1,132) = 10.69, p = .001."
      },
      {
        "id": "t_e2_c4",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Positive mood contrasts vs control",
        "outcome_var": "selfeval7",
        "df": "1, 132",
        "statistic_value": 10.69,
        "p_value": 0.001,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and raised self-ratings after downward comparison, F(1,132) = 10.69, p = .001."
      },
      {
        "id": "t_e2_neg_dir",
        "study_id": "exp2",
        "test_type": "one_way_anova",
        "location": "Experiment 2, Negative mood",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "direction"
        ],
        "df": "1, 124",
        "statistic_value": 56.97,
        "p_value": 0.001,
        "p_is_threshold": true,
        "hypothesis_id": "h2",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "Among the negative mood conditions, only the main effect of direction was significant, F(1, 124) = 56.97, p < .001."
      },
      {
        "id": "t_e3_mood_manip",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Manipulation check",
        "outcome_var": "mood7",
        "predictor_vars": [
          "moodcond"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 104.58,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "only the main effect of mood condition significantly influenced self-reported mood, F(1, 88) = 104.58, p < .001."
      },
      {
        "id": "t_e3_attr_manip",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Manipulation check",
        "outcome_var": "targetattr7",
        "predictor_vars": [
          "direction"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 170.34,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001."
      },
      {
        "id": "t_e3_cue",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "cue"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 11.4,
        "p_value": 0.001,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "ANOVA revealed significant effects of similarity cue (F(1, 88) = 11.40, p = .001), direction (F(1, 88) = 67.88, p < .001), and mood (F(1, 88) = 9.65, p = .003)."
      },
      {
        "id": "t_e3_dir",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "direction"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 67.88,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "direction (F(1, 88) = 67.88, p < .001), and mood (F(1, 88) = 9.65, p = .003)."
      },
      {
        "id": "t_e3_mood",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "moodcond"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 9.65,
        "p_value": 0.003,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and mood (F(1, 88) = 9.65, p = .003)."
      },
      {
        "id": "t_e3_cue_x_mood",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "cue",
          "moodcond"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 19.87,
        "p_value": 0.001,
        "p_is_threshold": true,
        "hypothesis_id": "h3",
        "is_stated_primary_outcome": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "These were qualified by the two-way interaction effects of similarity cue and mood (F(1, 88) = 19.87, p < .001) and similarity cue and direction (F(1, 88) = 59.27, p < .001)."
      },
      {
        "id": "t_e3_cue_x_dir",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "cue",
          "direction"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 59.27,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and similarity cue and direction (F(1, 88) = 59.27, p < .001)."
      },
      {
        "id": "t_e3_amb_mood",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Similarity cue and mood effects on responses",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "moodcond"
        ],
        "df": "1, 94",
        "statistic_value": 11.82,
        "p_value": 0.001,
        "p_is_threshold": false,
        "hypothesis_id": "h3",
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "participants in the positive mood reported significantly higher self-evaluations than those in the neutral mood condition, regardless of the direction of comparison, F(1,94) = 11.82, p = .001,"
      },
      {
        "id": "t_e3_unamb_dir",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Similarity cue and direction of comparison effects on responses",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "direction"
        ],
        "df": "1, 94",
        "statistic_value": 92.47,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "However, when the cue was unambiguous, participants assimilated to the comparison targets, as expected, F(1, 94) = 92.47, p < .001.",
        "effect_size_estimated": {
          "kind": "hedges_g",
          "value": 4.642,
          "ci95": [
            3.23,
            6.386
          ],
          "ci_spans_null": false,
          "computed_from": "Table 2 Self-evaluation, Positive/Unambiguous Upward 6.58 (.52) vs Downward 4.08 (.52), n = 12 per cell",
          "tool": "check_effect_plausibility"
        }
      },
      {
        "id": "t_e3_sim_cue",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "cue"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 55.38,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "the significant main effects of similarity cue, F(1,88) = 55.38, p < .001 and direction, F(1, 88) = 22.80, p < .001,"
      },
      {
        "id": "t_e3_sim_dir",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "direction"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 22.8,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and direction, F(1, 88) = 22.80, p < .001, were qualified by the two-way interaction effects of direction and mood, F(1,88) = 18.14, p < .001,"
      },
      {
        "id": "t_e3_sim_dir_x_mood",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "direction",
          "moodcond"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 18.14,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "were qualified by the two-way interaction effects of direction and mood, F(1,88) = 18.14, p < .001, and similarity cue and direction, F(1,88) = 26.20, p < .001."
      },
      {
        "id": "t_e3_sim_cue_x_dir",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "cue",
          "direction"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 26.2,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and similarity cue and direction, F(1,88) = 26.20, p < .001."
      },
      {
        "id": "t_e3_sim_threeway",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "cue",
          "direction",
          "moodcond"
        ],
        "n": 96,
        "df": "1, 88",
        "statistic_value": 15.32,
        "p_value": 0.001,
        "p_is_threshold": true,
        "hypothesis_id": "h3",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "These were further qualified by the significant three-way interaction effect, F(1, 88) = 15.32, p < .001."
      },
      {
        "id": "t_e3_sim_pos_amb",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity, planned comparison",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "direction"
        ],
        "df": "1, 94",
        "statistic_value": 53.17,
        "p_value": 0.001,
        "p_is_threshold": true,
        "hypothesis_id": "h3",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "in the presence of ambiguous information, participants in a positive mood rated upward comparison targets as more similar to the self than downward comparison targets, F(1, 94) = 53.17, p < .001.",
        "effect_size_estimated": {
          "kind": "hedges_g",
          "value": 5.027,
          "ci95": [
            3.53,
            6.883
          ],
          "ci_spans_null": false,
          "computed_from": "Table 2 Similarity, Positive/Ambiguous Upward 7.06 (.53) vs Downward 4.14 (.59), n = 12 per cell",
          "tool": "check_effect_plausibility"
        }
      },
      {
        "id": "t_e3_sim_pos_unamb",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity, planned comparison",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "direction"
        ],
        "df": "1, 94",
        "statistic_value": 1,
        "p_value": 0.05,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "participants rated the upward and downward comparison targets as equally similar to the self, F(1, 94) = 1.00, p > .05."
      },
      {
        "id": "t_e3_sim_neu_amb",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity, planned comparison",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "direction"
        ],
        "df": "1, 94",
        "statistic_value": 0.31,
        "p_value": 0.58,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "in the neutral mood condition, when information was ambiguous, direction of comparison did not influence ratings of similarity, F(1, 94) = .31, p = .58."
      },
      {
        "id": "t_e3_sim_neu_unamb",
        "study_id": "exp3",
        "test_type": "one_way_anova",
        "location": "Experiment 3, Perceptions of similarity, planned comparison",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "direction"
        ],
        "df": "1, 94",
        "statistic_value": 1.5,
        "p_value": 0.83,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83."
      },
      {
        "id": "t_e3_r_pos_unamb",
        "study_id": "exp3",
        "test_type": "pearson_correlation",
        "location": "Experiment 3, Perceptions of similarity, correlations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "targetattr7"
        ],
        "df": "24",
        "statistic_value": 0.87,
        "p_value": 0.001,
        "p_is_threshold": true,
        "effect_size": "r(24) = .87",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "self and other attractiveness were significantly related in the positive, r(24) = .87, p < .001, and neutral mood, r(24) = .53, p = .008, reflecting assimilation of self."
      },
      {
        "id": "t_e3_r_neu_unamb",
        "study_id": "exp3",
        "test_type": "pearson_correlation",
        "location": "Experiment 3, Perceptions of similarity, correlations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "targetattr7"
        ],
        "df": "24",
        "statistic_value": 0.53,
        "p_value": 0.008,
        "p_is_threshold": false,
        "effect_size": "r(24) = .53",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and neutral mood, r(24) = .53, p = .008, reflecting assimilation of self."
      },
      {
        "id": "t_e3_r_sim_attr",
        "study_id": "exp3",
        "test_type": "pearson_correlation",
        "location": "Experiment 3, Perceptions of similarity, correlations",
        "outcome_var": "similarity9",
        "predictor_vars": [
          "targetattr7"
        ],
        "df": "24",
        "statistic_value": 0.7,
        "p_value": 0.001,
        "p_is_threshold": true,
        "effect_size": "r(24) = .70",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "However, in a positive mood, ratings of similarity were correlated with ratings of other attractiveness, r(24) = .70, p < .001."
      },
      {
        "id": "t_e4_mood_manip",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Manipulation check",
        "outcome_var": "mood7",
        "predictor_vars": [
          "moodcond"
        ],
        "df": "1, 124",
        "statistic_value": 14.94,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "there was a main effect of mood induction on mood, F(1, 124) = 14.94, p < .001."
      },
      {
        "id": "t_e4_attr_manip",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Manipulation check",
        "outcome_var": "targetattr7",
        "predictor_vars": [
          "direction"
        ],
        "df": "1, 110",
        "statistic_value": 259.08,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "the attractive comparison target was rated more attractive than the (M = 5.58, SD = .78) than the unattractive target (M = 2.99, SD = .89), F(1,110) = 259.08, p < .001."
      },
      {
        "id": "t_e4_threeway",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "load",
          "moodcond",
          "direction"
        ],
        "df": "1, 110",
        "statistic_value": 11.23,
        "p_value": 0.001,
        "p_is_threshold": false,
        "hypothesis_id": "h4",
        "is_stated_primary_outcome": true,
        "appears_in_conclusions": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "Analysis revealed the expected three-way interaction effect of load, mood, and direction of comparison on attractiveness, F(1, 110) = 11.23, p = 001."
      },
      {
        "id": "t_e4_load",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "load"
        ],
        "df": "1, 110",
        "statistic_value": 8,
        "p_value": 0.006,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "The effects of load, F(1, 110) = 8.00, p = .006; mood F(1, 110) = 9.83, p = .002;"
      },
      {
        "id": "t_e4_mood",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "moodcond"
        ],
        "df": "1, 110",
        "statistic_value": 9.83,
        "p_value": 0.002,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "mood F(1, 110) = 9.83, p = .002; direction, F(1, 110) = 135.31, p < .001;"
      },
      {
        "id": "t_e4_dir",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "direction"
        ],
        "df": "1, 110",
        "statistic_value": 135.31,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "direction, F(1, 110) = 135.31, p < .001; load and mood, F(1, 110) = 10.97, p = .001;"
      },
      {
        "id": "t_e4_load_x_mood",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "load",
          "moodcond"
        ],
        "df": "1, 110",
        "statistic_value": 10.97,
        "p_value": 0.001,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "load and mood, F(1, 110) = 10.97, p = .001; load and direction, F(1, 110) = 10.44, p = .002"
      },
      {
        "id": "t_e4_load_x_dir",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "load",
          "direction"
        ],
        "df": "1, 110",
        "statistic_value": 10.44,
        "p_value": 0.002,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "load and direction, F(1, 110) = 10.44, p = .002 and mood and direction, F(1, 110) = 4.14, p = .04, were also significant."
      },
      {
        "id": "t_e4_mood_x_dir",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Self-evaluations",
        "outcome_var": "selfeval7",
        "predictor_vars": [
          "moodcond",
          "direction"
        ],
        "df": "1, 110",
        "statistic_value": 4.14,
        "p_value": 0.04,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and mood and direction, F(1, 110) = 4.14, p = .04, were also significant."
      },
      {
        "id": "t_e4_nl_pos_up",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, No load conditions",
        "outcome_var": "selfeval7",
        "df": "1, 124",
        "statistic_value": 17.39,
        "p_value": 0.001,
        "p_is_threshold": true,
        "hypothesis_id": "h4",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "regardless of whether participants upwardly compared (M = 5.64, SD = .78; F(1,124) = 17.39, p < .001) or downwardly compared (M = 5.15, SD = .81), F(1,124) = 11.90, p = .001."
      },
      {
        "id": "t_e4_nl_pos_down",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, No load conditions",
        "outcome_var": "selfeval7",
        "df": "1, 124",
        "statistic_value": 11.9,
        "p_value": 0.001,
        "p_is_threshold": false,
        "hypothesis_id": "h4",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "or downwardly compared (M = 5.15, SD = .81), F(1,124) = 11.90, p = .001."
      },
      {
        "id": "t_e4_nl_neu_up",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, No load conditions",
        "outcome_var": "selfeval7",
        "df": "1, 124",
        "statistic_value": 17.89,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "Upward comparison led to more positive self-ratings (M = 5.47, SD = .51) than the control condition, F(1,124) = 17.89, p < .001,"
      },
      {
        "id": "t_e4_nl_neu_down",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, No load conditions",
        "outcome_var": "selfeval7",
        "df": "1, 124",
        "statistic_value": 10.37,
        "p_value": 0.002,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and downward comparison led to less positive self-ratings than the control condition (M = 3.24, SD = 1.09), F(1,124) = 10.37, p = .002."
      },
      {
        "id": "t_e4_l_pos_up",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Cognitive load conditions",
        "outcome_var": "selfeval7",
        "df": "1, 124",
        "statistic_value": 23.14,
        "p_value": 0.001,
        "p_is_threshold": true,
        "hypothesis_id": "h4",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "upward comparison led to more positive self-ratings (M = 5.71, SD = .83), F(1,124) = 23.14, p < .001,"
      },
      {
        "id": "t_e4_l_pos_down",
        "study_id": "exp4",
        "test_type": "independent_t",
        "location": "Experiment 4, Cognitive load conditions",
        "outcome_var": "selfeval7",
        "df": "124",
        "statistic_value": -3.3,
        "p_value": 0.001,
        "p_is_threshold": false,
        "hypothesis_id": "h4",
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and downward comparison led to less positive self-ratings (M = 3.09, SD = .94), t(124) = -3.30, p = .001."
      },
      {
        "id": "t_e4_l_neu_up",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Cognitive load conditions",
        "outcome_var": "selfeval7",
        "df": "1, 124",
        "statistic_value": 18.83,
        "p_value": 0.001,
        "p_is_threshold": true,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "in which upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05), F(1,124) = 18.83, p < .001,"
      },
      {
        "id": "t_e4_l_neu_down",
        "study_id": "exp4",
        "test_type": "one_way_anova",
        "location": "Experiment 4, Cognitive load conditions",
        "outcome_var": "selfeval7",
        "df": "1, 124",
        "statistic_value": 7.84,
        "p_value": 0.006,
        "p_is_threshold": false,
        "correction_applied": "none",
        "confidence": "high",
        "provenance_quote": "and downward comparison led to less positive self-ratings (M = 5.53, SD = .87), F(1,124) = 7.84, p = .006, relative to the control condition."
      }
    ]
  },
  "statistics_register": [
    {
      "id": "s_pilot_n",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 45,
        "female": 30,
        "M_age": 19.5
      },
      "quote": "a pilot study conducted in which participants (N = 45, 30 female, M age = 19.5) completed positive or negative mood manipulations",
      "location": "Pilot study, Participants",
      "checkable": {
        "tools": [
          "flag_round_n"
        ]
      }
    },
    {
      "id": "s_pilot_alpha_mood",
      "source": "prose",
      "kind": "other",
      "values": {
        "cronbach_alpha": 0.91
      },
      "quote": "The four mood items were averaged to create an index of mood (Cronbach's alpha = .91)",
      "location": "Pilot study, Measures",
      "checkable": {
        "tools": [],
        "reason": "a reliability coefficient with no item-level covariance matrix printed; no registered check applies"
      }
    },
    {
      "id": "s_pilot_alpha_self",
      "source": "prose",
      "kind": "other",
      "values": {
        "cronbach_alpha": 0.71
      },
      "quote": "the three self-ratings were averaged to create an index of self-evaluations (Cronbach's alpha = .71)",
      "location": "Pilot study, Measures",
      "checkable": {
        "tools": [],
        "reason": "a reliability coefficient with no item-level covariance matrix printed; no registered check applies"
      }
    },
    {
      "id": "s_pilot_f_mood",
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
          "rivets_anova",
          "recalc_anova",
          "recalc_f_to_p",
          "statcheck"
        ]
      }
    },
    {
      "id": "s_pilot_means_mood",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_pos": 7.2,
        "SD_pos": 0.93,
        "M_ctrl": 6.15,
        "SD_ctrl": 0.52,
        "t": 3.43,
        "df": 42,
        "p": 0.001
      },
      "quote": "Participants in the positive mood condition reported more positive mood (M = 7.20, SD = .93) that those in the control condition (M = 6.15, SD = .52), t(42) = 3.43, p = .001.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [
          "rivets_anova",
          "statcheck"
        ]
      }
    },
    {
      "id": "s_pilot_means_neg",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_neg": 4.98,
        "SD_neg": 0.98,
        "t": -3.8
      },
      "quote": "Participants in the negative mood condition reported more negative mood (M = 4.98, SD = .98) than those in the control condition, t(42) = -3.80, p < .001.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [
          "rivets_anova"
        ]
      }
    },
    {
      "id": "s_pilot_selfeval",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_neg": 6.98,
        "SD_neg": 0.53,
        "M_pos": 6.98,
        "SD_pos": 0.8,
        "M_ctrl": 6.82,
        "SD_ctrl": 0.67,
        "F": 0.27,
        "df1": 1,
        "df2": 42,
        "p": 0.76
      },
      "quote": "Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76.",
      "location": "Pilot study, Results",
      "checkable": {
        "tools": [
          "recalc_f_to_p",
          "recalc_anova",
          "statcheck"
        ]
      }
    },
    {
      "id": "s_e1_n",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 47
      },
      "quote": "Female university (N = 47) students participated in the study for monetary compensation.",
      "location": "Experiment 1, Participants and design",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      }
    },
    {
      "id": "s_e1_manip",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_up": 5.71,
        "SD_up": 0.75,
        "M_down": 3.57,
        "SD_down": 1.47,
        "F": 38.8,
        "df1": 1,
        "df2": 43
      },
      "quote": "the upward comparison target was rated more attractive (M = 5.71, SD = .75) than the downward target (M = 3.57, SD = 1.47), F(1,43) = 38.80, p < .001.",
      "location": "Experiment 1, Manipulation check",
      "checkable": {
        "tools": [
          "recalc_anova"
        ],
        "reason": "cell n not stated; any recomputation assumes the 47 split evenly by direction"
      }
    },
    {
      "id": "s_e1_cue_main",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_shared": 4.92,
        "SD_shared": 1.14,
        "M_diff": 3.96,
        "SD_diff": 1.3,
        "F": 7.77,
        "df1": 1,
        "df2": 43,
        "p": 0.008
      },
      "quote": "those sharing a birthday reported higher self-evaluations (M = 4.92, SD = 1.14) than those not sharing a birthday (M = 3.96, SD = 1.3), F(1, 43) = 7.77, p = .008.",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [
          "statcheck"
        ],
        "reason": "cell n not stated, so GRIM and GRIMMER cannot run"
      }
    },
    {
      "id": "s_e1_interaction",
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
          "recalc_f_to_p",
          "statcheck"
        ]
      }
    },
    {
      "id": "s_e1_simple",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_up": 3.33,
        "SD_up": 0.65,
        "M_down": 4.64,
        "SD_down": 1.5,
        "F": 6.95,
        "df1": 1,
        "df2": 46
      },
      "quote": "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [
          "recalc_f_to_p"
        ],
        "reason": "the printed p has no decimal point, so no p comparison is possible as printed"
      }
    },
    {
      "id": "s_e1_shared",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_up": 5.08,
        "SD_up": 0.52,
        "M_down": 4.75,
        "SD_down": 1.54
      },
      "quote": "asymmetric assimilation towards the upward comparison target (M = 5.08, SD = .52) and contrast away from the downward comparison target (M = 4.75, SD = 1.54)",
      "location": "Experiment 1, Self-evaluations",
      "checkable": {
        "tools": [],
        "reason": "cell n not stated and 47 does not divide evenly into 4 cells, so no granularity check can be run"
      }
    },
    {
      "id": "s_e2_n",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 141,
        "women": 75
      },
      "quote": "University (N = 141, 75 women) students participated in the study for monetary compensation.",
      "location": "Experiment 2, Participants and design",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      }
    },
    {
      "id": "s_e2_mood_manip",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_pos": 5.72,
        "SD_pos": 0.82,
        "M_ctrl": 4.4,
        "SD_ctrl": 0.83,
        "t": 5.61,
        "df": 138
      },
      "quote": "Participants in the positive mood condition were more positive (M = 5.72, SD = .82) than the control condition (M = 4.40, SD = .83), t(138) = 5.61, p < .001.",
      "location": "Experiment 2, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n not printed; the control n of 15 is derived rather than stated"
      }
    },
    {
      "id": "s_e2_neg",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_neg": 2.98,
        "SD_neg": 0.83,
        "t": -5.97,
        "df": 138
      },
      "quote": "The negative mood condition (M = 2.98, SD = .83), was more negative than the control condition, t(138) = -5.97, p < .001.",
      "location": "Experiment 2, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n not printed"
      }
    },
    {
      "id": "s_e2_attr",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_up": 5.98,
        "SD_up": 0.69,
        "M_down": 2.46,
        "SD_down": 0.74,
        "F": 716.92,
        "df1": 1,
        "df2": 118
      },
      "quote": "The upward comparison target was rated more attractive (M = 5.98, SD = .69) than the downward target (M = 2.46, SD = .74), F(1,118) = 716.92, p < .001.",
      "location": "Experiment 2, Manipulation check",
      "checkable": {
        "tools": [
          "recalc_anova"
        ],
        "reason": "group n not printed; 126 does not split evenly into the 8 cells"
      }
    },
    {
      "id": "s_e2_t1_row",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "pos_same_up": 5.25,
        "sd1": 0.93,
        "pos_same_down": 5.53,
        "sd2": 0.52,
        "pos_diff_up": 3.17,
        "sd3": 0.98,
        "pos_diff_down": 5.13,
        "sd4": 0.72
      },
      "quote": "5.25 (.93)",
      "location": "Table 1, Self-evaluation row, positive mood columns",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ],
        "reason": "cell n cannot be derived: the factorial holds 126 participants across 8 cells, which is not an integer split"
      }
    },
    {
      "id": "s_e2_t1_row_neg",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "neg_same_up": 3.33,
        "sd1": 0.9,
        "neg_same_down": 5.2,
        "sd2": 0.68,
        "neg_diff_up": 3.07,
        "sd3": 0.62,
        "neg_diff_down": 5.35,
        "sd4": 0.7
      },
      "quote": "3.33 (.90)",
      "location": "Table 1, Self-evaluation row, negative mood columns",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ],
        "reason": "cell n cannot be derived, as for s_e2_t1_row"
      }
    },
    {
      "id": "s_e2_ctrl_footnote",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 4.2,
        "SD": 0.86
      },
      "quote": "Mean self-evaluations in the control condition were 4.20 with a standard deviation of .86.",
      "location": "Table 1 footnote (PDF page 9; absent from the XML)",
      "checkable": {
        "tools": [
          "grimmer_check",
          "detect_duplication"
        ]
      }
    },
    {
      "id": "s_e3_n",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 96
      },
      "quote": "University students (N = 96) participated in the study for course credit.",
      "location": "Experiment 3, Participants",
      "checkable": {
        "tools": [
          "check_summation",
          "required_n"
        ]
      }
    },
    {
      "id": "s_e3_mood",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_pos": 7.33,
        "SD_pos": 0.86,
        "M_neu": 5.44,
        "SD_neu": 0.97
      },
      "quote": "Participants in the positive mood condition were more positive (M = 7.33, SD = .86) than the neutral condition (M = 5.44, SD = .97).",
      "location": "Experiment 3, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "Experiment 3 never states the range of its mood measure; without stated bounds neither a range check nor a granularity check may run"
      }
    },
    {
      "id": "s_e3_attr",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_up": 7.33,
        "SD_up": 1.19,
        "M_down": 4.17,
        "SD_down": 1.19,
        "F": 170.34,
        "df1": 1,
        "df2": 88
      },
      "quote": "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001.",
      "location": "Experiment 3, Manipulation check",
      "checkable": {
        "tools": [
          "grim_check",
          "recalc_anova"
        ]
      }
    },
    {
      "id": "s_e3_t2_selfeval",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "pos_amb_up": 6.58,
        "sd1": 0.9,
        "pos_amb_down": 6.5,
        "sd2": 0.8,
        "pos_unamb_up": 6.58,
        "sd3": 0.52,
        "pos_unamb_down": 4.08,
        "sd4": 0.52
      },
      "quote": "6.58 (.52)",
      "location": "Table 2, Self-evaluation row, positive mood columns",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s_e3_t2_selfeval_neu",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "neu_amb_up": 5.42,
        "sd1": 0.79,
        "neu_amb_down": 5.33,
        "sd2": 0.78,
        "neu_unamb_up": 6.75,
        "sd3": 0.87,
        "neu_unamb_down": 4.33,
        "sd4": 0.78
      },
      "quote": "5.42 (.79)",
      "location": "Table 2, Self-evaluation row, neutral mood columns",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ]
      }
    },
    {
      "id": "s_e3_t2_sim",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "pos_amb_up": 7.06,
        "sd1": 0.53,
        "pos_amb_down": 4.14,
        "sd2": 0.59,
        "pos_unamb_up": 6.81,
        "sd3": 1.16,
        "pos_unamb_down": 6.81,
        "sd4": 0.63
      },
      "quote": "7.06 (.53)",
      "location": "Table 2, Similarity row, positive mood columns",
      "checkable": {
        "tools": [
          "check_effect_plausibility"
        ],
        "reason": "a mean of three items, so granularity is 1/(3n) and grim/grimmer/sprite have no items parameter; check_table refused all 8 similarity cells for this reason"
      }
    },
    {
      "id": "s_e3_t2_sim_neu",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "neu_amb_up": 5.72,
        "sd1": 0.97,
        "neu_amb_down": 5.44,
        "sd2": 0.69,
        "neu_unamb_up": 6.72,
        "sd3": 0.76,
        "neu_unamb_down": 6.83,
        "sd4": 0.8
      },
      "quote": "5.72 (.97)",
      "location": "Table 2, Similarity row, neutral mood columns",
      "checkable": {
        "tools": [],
        "reason": "multi-item composite with granularity 1/(3n), as for s_e3_t2_sim"
      }
    },
    {
      "id": "s_e3_alpha",
      "source": "prose",
      "kind": "other",
      "values": {
        "alpha": 0.87
      },
      "quote": "participant responses to the three similarity questions were averaged (alpha = .87)",
      "location": "Experiment 3, Perceptions of similarity",
      "checkable": {
        "tools": [],
        "reason": "reliability coefficient with no item covariances printed"
      }
    },
    {
      "id": "s_e3_1_50",
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
          "recalc_f_to_p",
          "statcheck"
        ]
      }
    },
    {
      "id": "s_e3_031",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "F": 0.31,
        "df1": 1,
        "df2": 94,
        "p": 0.58
      },
      "quote": "direction of comparison did not influence ratings of similarity, F(1, 94) = .31, p = .58.",
      "location": "Experiment 3, Perceptions of similarity",
      "checkable": {
        "tools": [
          "recalc_f_to_p",
          "statcheck"
        ]
      }
    },
    {
      "id": "s_e3_r87",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "r": 0.87,
        "df": 24,
        "p": 0.001
      },
      "quote": "self and other attractiveness were significantly related in the positive, r(24) = .87, p < .001, and neutral mood, r(24) = .53, p = .008, reflecting assimilation of self.",
      "location": "Experiment 3, Perceptions of similarity",
      "checkable": {
        "tools": [
          "statcheck",
          "recalc_stat_to_p"
        ]
      }
    },
    {
      "id": "s_e3_r70",
      "source": "prose",
      "kind": "test_statistic",
      "values": {
        "r": 0.7,
        "df": 24,
        "p": 0.001
      },
      "quote": "However, in a positive mood, ratings of similarity were correlated with ratings of other attractiveness, r(24) = .70, p < .001.",
      "location": "Experiment 3, Perceptions of similarity",
      "checkable": {
        "tools": [
          "statcheck",
          "recalc_stat_to_p"
        ]
      }
    },
    {
      "id": "s_e4_n",
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 193,
        "female": 103
      },
      "quote": "University (N = 193, 103 female) students participated in the study for monetary compensation.",
      "location": "Experiment 4, Participants and design",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      }
    },
    {
      "id": "s_e4_mood",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_pos": 5.35,
        "SD_pos": 0.81,
        "M_neu": 4.6,
        "SD_neu": 0.93
      },
      "quote": "Participants in the positive condition were more positive (M = 5.35, SD = .81) than participants in the neutral condition (M = 4.60, SD = .93).",
      "location": "Experiment 4, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n not printed and the experiment's own df do not reconcile with its stated N, so no denominator can be trusted"
      }
    },
    {
      "id": "s_e4_attr",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_attr": 5.58,
        "SD_attr": 0.78,
        "M_unattr": 2.99,
        "SD_unattr": 0.89,
        "F": 259.08,
        "df1": 1,
        "df2": 110
      },
      "quote": "the attractive comparison target was rated more attractive than the (M = 5.58, SD = .78) than the unattractive target (M = 2.99, SD = .89), F(1,110) = 259.08, p < .001.",
      "location": "Experiment 4, Manipulation check",
      "checkable": {
        "tools": [],
        "reason": "group n not printed, as for s_e4_mood"
      }
    },
    {
      "id": "s_e4_ctrl",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M": 4.2,
        "SD": 0.21
      },
      "quote": "Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found",
      "location": "Experiment 4, No load conditions",
      "checkable": {
        "tools": [
          "grimmer_check",
          "sprite_reconstruct",
          "r_sprite_ground_truth"
        ]
      }
    },
    {
      "id": "s_e4_nl_pos",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_up": 5.64,
        "SD_up": 0.78,
        "F_up": 17.39,
        "M_down": 5.15,
        "SD_down": 0.81,
        "F_down": 11.9,
        "p_down": 0.001
      },
      "quote": "regardless of whether participants upwardly compared (M = 5.64, SD = .78; F(1,124) = 17.39, p < .001) or downwardly compared (M = 5.15, SD = .81), F(1,124) = 11.90, p = .001.",
      "location": "Experiment 4, No load conditions",
      "checkable": {
        "tools": [
          "statcheck"
        ],
        "reason": "cell n not printed, so granularity checks cannot run"
      }
    },
    {
      "id": "s_e4_nl_neu",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_up": 5.47,
        "SD_up": 0.51,
        "F_up": 17.89,
        "M_down": 3.24,
        "SD_down": 1.09,
        "F_down": 10.37,
        "p_down": 0.002
      },
      "quote": "Upward comparison led to more positive self-ratings (M = 5.47, SD = .51) than the control condition, F(1,124) = 17.89, p < .001, and downward comparison led to less positive self-ratings than the control condition (M = 3.24, SD = 1.09), F(1,124) = 10.37, p = .002.",
      "location": "Experiment 4, No load conditions",
      "checkable": {
        "tools": [
          "statcheck"
        ],
        "reason": "cell n not printed"
      }
    },
    {
      "id": "s_e4_load",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "M_pos_up": 5.71,
        "SD_pos_up": 0.83,
        "M_pos_down": 3.09,
        "SD_pos_down": 0.94,
        "t": -3.3,
        "M_neu_up": 3.33,
        "SD_neu_up": 1.05,
        "M_neu_down": 5.53,
        "SD_neu_down": 0.87
      },
      "quote": "upward comparison led to more positive self-ratings (M = 5.71, SD = .83), F(1,124) = 23.14, p < .001, and downward comparison led to less positive self-ratings (M = 3.09, SD = .94), t(124) = -3.30, p = .001. This pattern was identical to the neutral mood condition, in which upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05), F(1,124) = 18.83, p < .001, and downward comparison led to less positive self-ratings (M = 5.53, SD = .87), F(1,124) = 7.84, p = .006, relative to the control condition.",
      "location": "Experiment 4, Cognitive load conditions",
      "checkable": {
        "tools": [
          "statcheck"
        ],
        "reason": "cell n not printed"
      }
    },
    {
      "id": "s_e2_tukey",
      "source": "prose",
      "kind": "p_value",
      "values": {
        "p": 0.07
      },
      "quote": "the negative mood, shared birthday, upward comparison condition differs from the control at the p = .07 level",
      "location": "Experiment 2, footnote 2 (PDF page 8)",
      "checkable": {
        "tools": [],
        "reason": "a Tukey HSD p reported without its statistic or group ns; no registered check applies"
      }
    },
    {
      "id": "s_e4_tukey",
      "source": "prose",
      "kind": "p_value",
      "values": {
        "p": 0.13
      },
      "quote": "the high load, neutral mood induction, downward comparison condition differed from the control at the p = .13 level",
      "location": "Experiment 4, footnote 5 (PDF page 13)",
      "checkable": {
        "tools": [],
        "reason": "a Tukey HSD p reported without its statistic or group ns"
      }
    }
  ],
  "findings": [
    {
      "id": "e3_target_attractiveness_off_scale",
      "location": "Experiment 3, Manipulation check",
      "technique": "grim",
      "consistent": false,
      "severity": "impossible",
      "quote": "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001.",
      "reported": {
        "M": 7.33,
        "SD": 1.19,
        "scale_max_stated": 7
      },
      "computed": {
        "tool_verdict": "impossible",
        "failure_mode": "out_of_range",
        "implied_sum_at_n48": 351.84,
        "max_attainable_sum_on_1_to_7_scale_at_n48": 336,
        "granularity_at_n48": 0.0208333,
        "bound_source": "stated",
        "tool": "grim_check"
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
        "explanation": "The reported mean attractiveness of the upward comparison target exceeds the maximum of the scale the paper says was used, so Experiment 3's direction-of-comparison manipulation check rests on a value the instrument cannot produce."
      },
      "notes": "The mean is off-scale regardless of n, so the n = 48 passed here is immaterial to the verdict. The scale is established by a two-step reference the paper itself makes: Experiment 3 says participants rated attractiveness 'on the seam measures used in Experiments 1 and 2', and both of those print the numerals -- Experiment 1: 'a seven-point scale (1 = not at all, 7 = extremely)'; Experiment 2: 'seven-point scales (1 = not at all attractive and 7 = extremely attractive)'. Corroboration that the 7-point reading is right: every self-evaluation cell in Table 2, the same instrument, tops out at 6.75. THE INNOCENT EXPLANATION, which must be stated: Experiment 3 may in fact have used a nine-point scale (the Pilot's self-ratings and Experiment 3's own similarity items are nine-point) and the Methods sentence -- which contains a typo, 'seam' for 'same' -- may misdescribe the measure. On that reading the mean is fine and the Methods are wrong. Either way the paper contradicts itself. Awaiting the stage-2 r_grim_ground_truth cross-check."
    },
    {
      "id": "e4_control_sd_impossible",
      "location": "Experiment 4, No load conditions and Cognitive load conditions, control condition",
      "technique": "grimmer",
      "consistent": false,
      "severity": "impossible",
      "quote": "Higher levels of self-evaluations relative to the control condition (M = 4.20, SD = .21) were found",
      "reported": {
        "M": 4.2,
        "SD": 0.21
      },
      "computed": {
        "tool_verdict_at_n15": "impossible",
        "tool_verdict_at_n75": "impossible",
        "failure_mode": "sd_granularity",
        "grim_sum_at_n15": 63,
        "grim_sum_at_n75": 315,
        "sum_of_squares_window_at_n15": [
          265.19,
          265.25
        ],
        "feasible_ignoring_bounds": false,
        "r_rsprite2_verdict": "fails GRIMMER test",
        "tool": "grimmer_check, sprite_reconstruct and r_sprite_ground_truth"
      },
      "inputs": {
        "mean": 4.2,
        "sd": 0.21,
        "n": [
          15,
          75
        ],
        "scale_min": 1,
        "scale_max": 7,
        "decimals": 2,
        "decimals_sd": 2,
        "data_type": "likert",
        "discreteness_source": "stated"
      },
      "reproduction": "metascience grimmer --mean 4.20 --sd 0.21 --n 15 --scale-min 1 --scale-max 7 --decimals 2 --decimals-sd 2 --data-type likert --discreteness-source stated",
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 8,
        "explanation": "This control condition is the baseline against which all eight of Experiment 4's contrasts are tested, so every claim in that experiment is referred to a mean and SD that no sample of whole-number ratings can produce."
      },
      "notes": "Robust to the one thing that is uncertain here. Experiment 4's control n is not printed, and the paper's own degrees of freedom disagree about it (see e4_sample_size_reconciliation): the contrast df imply 15, the stated N would imply 75. The pair fails at BOTH. The tool reports feasible_ignoring_bounds = false, so the verdict does not rest on the 1-7 scale bounds at all, only on the responses being whole numbers, which a single seven-point rating item makes so. R's rsprite2 independently refuses these parameters with 'The standard deviation is not consistent with this mean and number of observations (fails GRIMMER test)', so the two engines agree; our wrapper records that refusal as indeterminate for SPRITE purposes because a raise is not proof, and the severity here therefore rests on our own GRIMMER with R as corroboration. Note that Experiment 2's control condition is reported with the SAME mean, 4.20, but SD = .86, which is entirely feasible at n = 15 (checked, consistent). Awaiting the stage-2 r_grim_ground_truth cross-check."
    },
    {
      "id": "table2_sd_52_impossible",
      "location": "Table 2, Self-evaluation row, Positive/Unambiguous Upward and Positive/Unambiguous Downward cells",
      "technique": "grimmer",
      "consistent": false,
      "severity": "impossible",
      "quote": "6.58 (.52)",
      "reported": {
        "cell_1": "6.58 (.52)",
        "cell_2": "4.08 (.52)",
        "n_per_cell_derived": 12
      },
      "computed": {
        "tool_verdict_both_cells": "impossible",
        "failure_mode": "sd_granularity",
        "grim_sum_cell_1": 79,
        "grim_sum_cell_2": 49,
        "sum_of_squares_window_cell_1": [
          523,
          523.12
        ],
        "sum_of_squares_window_cell_2": [
          203,
          203.12
        ],
        "only_attainable_sd_both_cells": 0.51,
        "feasible_ignoring_bounds": false,
        "r_rsprite2_verdict": "fails GRIMMER test, both cells",
        "tool": "grimmer_check, sprite_reconstruct and r_sprite_ground_truth"
      },
      "inputs": {
        "mean": [
          6.58,
          4.08
        ],
        "sd": 0.52,
        "n": 12,
        "scale_min": 1,
        "scale_max": 7,
        "decimals": 2,
        "decimals_sd": 2,
        "data_type": "likert",
        "discreteness_source": "stated"
      },
      "reproduction": "metascience grimmer --mean 6.58 --sd 0.52 --n 12 --scale-min 1 --scale-max 7 --decimals 2 --decimals-sd 2 --data-type likert --discreteness-source stated",
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "These two cells are the Positive/Unambiguous contrast reported as F(1, 94) = 92.47, the result establishing that unambiguous similarity information produces symmetric assimilation."
      },
      "notes": "The cell n of 12 is DERIVED, not printed: Experiment 3 states N = 96 in a fully crossed 2x2x2, and its ANOVA error df of 88 plus 8 cells returns exactly 96, so all 96 entered the factorial. Two things corroborate the even split: check_table found all eight Table 2 self-evaluation means GRIM-consistent at n = 12, which a wrong denominator would not generally produce, and the paper's planned comparisons carry df of 94 = 96 - 2. If cells were in fact unequal (n = 13 would rescue 4.08, for instance) this finding does not stand, and that is the one assumption a reader must accept. The failures are near misses: in both cells the only attainable SD is .51 where .52 is printed, so a rounding convention we have not reproduced is a live alternative, though it would have to be the same convention twice. feasible_ignoring_bounds = false, so the 1-7 bounds are not load-bearing. Both cells reach identical arithmetic. R's rsprite2 refuses both with 'fails GRIMMER test'; the severity rests on our GRIMMER, with R as corroboration. Denominator: 24 checks ran on Table 2, 20 consistent, these 4 not."
    },
    {
      "id": "e4_sample_size_reconciliation",
      "location": "Experiment 4, Participants and design vs Results and discussion",
      "technique": "check_summation",
      "consistent": false,
      "severity": "suspicious",
      "quote": "University (N = 193, 103 female) students participated in the study for monetary compensation.",
      "reported": {
        "N_stated": 193,
        "contrast_error_df": 124,
        "factorial_error_df": 110,
        "n_groups": 9
      },
      "computed": {
        "implied_total_from_contrast_df_124_plus_9_groups": 133,
        "shortfall_against_stated_N": -60,
        "implied_factorial_n_from_110_plus_8_cells": 118,
        "exp2_same_arithmetic_132_plus_9_vs_141": 0,
        "exp3_same_arithmetic_88_plus_8_vs_96": 0,
        "exp1_same_arithmetic_43_plus_4_vs_47": 0,
        "pilot_same_arithmetic_42_plus_3_vs_45": 0,
        "n_rows_inconsistent": 2,
        "n_rows_evaluated": 6,
        "tool": "check_summation_batch"
      },
      "inputs": {
        "rows": "6 rows, each error df + number of groups against the stated N, for the pilot and Experiments 1-4",
        "tolerance": 0,
        "decimals": [
          0,
          0
        ]
      },
      "reproduction": "metascience summation-batch --rows '[{\"values\":[124,9],\"expected_sum\":193,\"decimals\":[0,0],\"tolerance\":0,\"description\":\"Exp 4 contrast error df plus 9 groups vs stated N\"},{\"values\":[132,9],\"expected_sum\":141,\"decimals\":[0,0],\"tolerance\":0,\"description\":\"Exp 2 same arithmetic\"},{\"values\":[88,8],\"expected_sum\":96,\"decimals\":[0,0],\"tolerance\":0,\"description\":\"Exp 3 same arithmetic\"}]'",
      "consequence": {
        "basis": "computed",
        "flips_significance": null,
        "claims_affected": 12,
        "explanation": "Every test in Experiment 4 is reported on error df implying about 133 analysed participants, so if 193 were recruited the analysis silently drops roughly 60 people with no exclusion reported anywhere."
      },
      "notes": "The reconciliation rule used here is the paper's own. In Experiment 2, structurally identical (2x2x2 plus one hanging control, contrasts run against a 9-group one-way error term), 132 + 9 lands exactly on the stated 141; the pilot and Experiments 1 and 3 also land exactly. Experiment 4 alone is out, and by a large margin. The innocent explanations are ordinary and the paper closes one of them: exclusions would account for it, but none are reported, and the load manipulation's obvious exclusion route is explicitly ruled out -- 'All participants were able to recall the number at the end of the session.' A typo in the printed N (193 for 133) would also account for it and is the least dramatic reading. Note that 110 + 8 = 118 and 118 + 15 = 133 is internally coherent, so Experiment 4's degrees of freedom agree with each other and only the stated N is the outlier."
    },
    {
      "id": "e4_means_reversed_in_prose",
      "location": "Experiment 4, Cognitive load conditions, final sentence",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "This pattern was identical to the neutral mood condition, in which upward comparison led to more positive self-ratings (M = 3.33, SD = 1.05), F(1,124) = 18.83, p < .001, and downward comparison led to less positive self-ratings (M = 5.53, SD = .87), F(1,124) = 7.84, p = .006, relative to the control condition.",
      "reported": {
        "control_M": 4.2,
        "upward_M_labelled_more_positive": 3.33,
        "downward_M_labelled_less_positive": 5.53
      },
      "computed": {
        "observation": "the mean labelled 'more positive' is below the control mean and the mean labelled 'less positive' is above it, so the two means are transposed relative to their own labels",
        "contrast_with_the_same_paragraph": "in the positive-mood load pair the labels match the means (5.71 above control, 3.09 below), and in the no-load neutral pair they also match (5.47 above, 3.24 below)",
        "method": "ordering each printed mean against the printed control mean in the same sentence; no arithmetic beyond comparison"
      },
      "inputs": {
        "source": "Experiment 4 Results, verified identically in the XML full text and on PDF page 13"
      },
      "reproduction": "No command applies: this is a reading of the paper's prose against its own printed means, not a calculation.",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "The sentence asserts that positive mood under load becomes indistinguishable from neutral mood, which is Experiment 4's central claim; as printed, the neutral-mood means it cites run the opposite way to the description."
      },
      "notes": "Confirmed against PDF page 13, so not an XML extraction artifact. The simplest explanation is that the two means were transposed when the sentence was written, which is a proofreading failure rather than a data problem; the F values do not disambiguate which mean belongs to which condition. Figure 3 plots these means and would settle it, but the plotted values could not be read here."
    },
    {
      "id": "pilot_selfeval_df1_wrong",
      "location": "Pilot study, second results paragraph",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Those in the negative mood (M = 6.98, SD = .53), positive mood (M = 6.98, SD = .80), and the control condition (M = 6.82, SD = .67), did not differ F(1, 42) = .27, p = .76.",
      "reported": {
        "F": 0.27,
        "df1_printed": 1,
        "df2": 42,
        "p": 0.76,
        "n_groups_described": 3
      },
      "computed": {
        "p_at_printed_df_1_and_42": 0.60606,
        "p_at_design_implied_df_2_and_42": 0.764694,
        "achievable_p_interval_at_df1_of_2": [
          0.760929,
          0.768479
        ],
        "reported_p_falls_inside_the_df1_2_interval": true,
        "tool": "recalc_f_to_p, run twice"
      },
      "inputs": {
        "f_value": 0.27,
        "df1": [
          1,
          2
        ],
        "df2": 42,
        "reported_p": 0.76,
        "decimals_f": 2,
        "decimals_p": 2
      },
      "reproduction": "metascience f-to-p --f-value 0.27 --df1 2 --df2 42 --reported-p 0.76 --decimals-f 2 --decimals-p 2",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "The claim is a null one, that mood alone did not move self-evaluations, and it survives either df, so the error is in the notation rather than the conclusion."
      },
      "notes": "This is a cross-reference contradiction, not an arithmetic dispute: the same paragraph reports the mood ANOVA over the same three groups as F(2, 42), so the numerator df for a three-group one-way is 2 and the printed 1 is a misprint. The two recalc_f_to_p runs are supporting evidence and settle which number is wrong, since the printed p of .76 reconciles at df1 = 2 and not at df1 = 1. Note that recalc_f_to_p returned `consistent` for the printed F(1, 42) = .27, p = .76 pairing, because it is directional and flags only over-claims; the reported p is larger than the printed statistic supports, which it treats as conservative reporting. The finding therefore rests on the design contradiction, not on that tool's verdict."
    },
    {
      "id": "e3_f150_p83",
      "location": "Experiment 3, Perceptions of similarity, final sentence",
      "technique": "statcheck",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Identical effects emerged when the information was unambiguous, F(1, 94) = 1.50, p = .83.",
      "reported": {
        "F": 1.5,
        "df1": 1,
        "df2": 94,
        "p": 0.83
      },
      "computed": {
        "p_implied_by_F_1_94_of_1_50": 0.223732,
        "achievable_p_interval_given_printed_precision": [
          0.222968,
          0.224499
        ],
        "one_tailed_equivalent": 0.111866,
        "statcheck_error_flag": true,
        "statcheck_decision_error": false,
        "tool": "statcheck and recalc_f_to_p"
      },
      "inputs": {
        "f_value": 1.5,
        "df1": 1,
        "df2": 94,
        "reported_p": 0.83,
        "decimals_f": 2,
        "decimals_p": 2
      },
      "reproduction": "metascience f-to-p --f-value 1.50 --df1 1 --df2 94 --reported-p 0.83 --decimals-f 2 --decimals-p 2",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "Both the reported and the recomputed p are far above .05, so the null conclusion the sentence draws is unaffected and only the printed p is wrong."
      },
      "notes": "Two tools disagree, and the disagreement is worth stating plainly. statcheck flags this as an inconsistency. recalc_f_to_p returns `consistent` because it is deliberately directional: it flags only p-values SMALLER than the statistic supports, treating a larger one as conservative reporting or a correction. I have recorded `suspicious` on statcheck's flag, not by overriding recalc_f_to_p. What distinguishes this from the paper's other statcheck flags is magnitude -- .83 against .224 is far outside any rounding window, whereas the rest (for instance .008 against .007877) are rounding artifacts and should not be reported as errors. Innocent explanations: an adjustment would raise a p, though the paper reports no correction for Experiment 3, or .83 is a typo. The sentence also calls this effect 'identical' to the F(1, 94) = .31, p = .58 result immediately before it, which recomputes exactly."
    },
    {
      "id": "e1_p_missing_decimal_and_df",
      "location": "Experiment 1, Self-evaluations",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Exposure to the upward comparison target led to lowered self-evaluations (M = 3.33, SD = .65) compared to the downward comparison target (M = 4.64, SD = 1.50), F(1, 46) = 6.95, p = 011.",
      "reported": {
        "F": 6.95,
        "df1": 1,
        "df2": 46,
        "p_as_printed": "011"
      },
      "computed": {
        "observation_1": "the p is printed without a decimal point, so as printed it is not a p-value at all",
        "observation_2": "the error df of 46 corresponds to no group structure in this experiment: the 2x2 ANOVA reported two sentences earlier uses F(1, 43), where 43 = 47 minus 4 cells, and a two-group comparison of the 47 participants would give 45",
        "method": "comparison of the printed df against the df the paper itself reports for the same design; no calculation"
      },
      "inputs": {
        "source": "Experiment 1 Results, verified identically in the XML full text and on PDF page 6"
      },
      "reproduction": "No command applies: this is a notation and cross-reference reading, not a calculation.",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "The simple effect establishing symmetric contrast in the unshared-birthday conditions is reported with a malformed p and an error df inconsistent with the design the paper describes."
      },
      "notes": "Both defects are in the published PDF, not introduced by extraction. 'p = 011' is almost certainly '.011', which is what F(1, 43) = 6.95 would give; on that reading the p is fine and only the decimal point and the df are wrong. Recorded as one finding because both sit in the same sentence and both point at the same thing, that the sentence was not proofread."
    },
    {
      "id": "table1_caption_promises_absent_measures",
      "location": "Table 1 caption vs Table 1 body",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Effects of upward (more attractive) versus downward (less attractive) comparisons on self-evaluations, ratings of target similarity, and use of information to benefit the self as a function of mood and shared birthday information",
      "reported": {
        "measures_named_in_caption": 3,
        "body_rows_present": 1,
        "row_label_present": "Self-evaluation"
      },
      "computed": {
        "missing_rows": [
          "ratings of target similarity",
          "use of information to benefit the self"
        ],
        "confirmed_in_both_sources": "the XML grid and the PDF grid each return exactly one body row",
        "method": "comparison of the caption's enumerated measures against the table's row labels"
      },
      "inputs": {
        "xml_table_num": 1,
        "pdf_page": 9
      },
      "reproduction": "metascience get-table --xml-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.xml --table-num 1",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 2,
        "explanation": "Two dependent measures the caption says the table reports appear nowhere in Table 1, and Experiment 2's Results text analyses neither of them, so two measures named as collected are never reported."
      },
      "notes": "Verified against the PDF, so not an extraction failure: both sources return a single Self-evaluation row. Experiment 2's Dependent measures section likewise describes only attractiveness ratings and a mood item, with no similarity index and no 'use of information' measure, so the caption may have been copied from Table 2 (which does carry a Similarity row) or from a template. The alternative and more consequential reading is that measures were collected and not reported."
    },
    {
      "id": "control_mean_4_20_recurs_across_experiments",
      "location": "Table 1 footnote (Experiment 2) and Experiment 4, No load conditions",
      "technique": "duplication",
      "consistent": true,
      "severity": "indeterminate",
      "quote": "Mean self-evaluations in the control condition were 4.20 with a standard deviation of .86.",
      "reported": {
        "exp2_control": "M = 4.20, SD = .86",
        "exp4_control": "M = 4.20, SD = .21"
      },
      "computed": {
        "tool_verdict": "indeterminate",
        "max_identical_mean_sd_pairs_across_independent_blocks": 0,
        "n_comparisons": 97,
        "only_pattern_returned": "near_match 5.35 vs 5.53, relation digit_transposition, severity indeterminate",
        "tool": "detect_duplication"
      },
      "inputs": {
        "blocks": "4 blocks: Exp 2 control, Exp 4 control, Exp 2 cell means from Table 1, Exp 4 cell means from prose",
        "decimals_mean": 2,
        "decimals_sd": 2
      },
      "reproduction": "metascience duplication-detect --blocks '[{\"label\":\"Exp2 control\",\"sample_id\":\"exp2\",\"cells\":[{\"label\":\"control\",\"value\":4.20,\"sd\":0.86}]},{\"label\":\"Exp4 control\",\"sample_id\":\"exp4\",\"cells\":[{\"label\":\"control\",\"value\":4.20,\"sd\":0.21}]}]' --decimals-mean 2 --decimals-sd 2",
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": null,
        "explanation": "No claim depends on this; it is recorded because two independent experiments' baselines coincide exactly on the mean while one of the two SDs is arithmetically impossible."
      },
      "notes": "The tool declined to flag and I have not overridden it. detect_duplication matches on (mean, SD) PAIRS, and these pairs differ because the SDs do; a mean-only coincidence at two decimals between two conditions measured on the same 7-point instrument is unremarkable on its own. It is recorded here only because it sits beside e4_control_sd_impossible: the Experiment 2 control (4.20, .86) is GRIMMER-consistent at n = 15 and the Experiment 4 control (4.20, .21) is not, at any candidate n. The Table 1 footnote carrying the Experiment 2 value is absent from the XML and was recovered only from PDF page 9."
    },
    {
      "id": "pilot_mood_anova_f_out_of_range",
      "location": "Pilot study, mood manipulation check",
      "technique": "rivets_anova",
      "consistent": false,
      "severity": "suspicious",
      "quote": "A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001.",
      "reported": {
        "F": 18.44,
        "df": "2, 42",
        "M_pos": 7.2,
        "SD_pos": 0.93,
        "M_ctrl": 6.15,
        "SD_ctrl": 0.52,
        "M_neg": 4.98,
        "SD_neg": 0.98
      },
      "computed": {
        "tool_verdict": "highly_suspicious",
        "recorded_severity": "suspicious",
        "monte_carlo_f_interval_at_assumed_equal_ns": [
          26.011162,
          27.03798
        ],
        "point_f_at_truncated_inputs": 26.482082,
        "reported_f_in_range": false,
        "assumed_ns": [
          15,
          15,
          15
        ],
        "tool": "rivets_anova"
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
        "ns": [
          15,
          15,
          15
        ],
        "reported_f": 18.44,
        "reported_p": 0.001,
        "p_is_threshold": true,
        "decimals_mean": 2,
        "decimals_sd": 2,
        "decimals_f": 2
      },
      "reproduction": "metascience rivets-anova --means '[7.20,6.15,4.98]' --sds '[0.93,0.52,0.98]' --ns '[15,15,15]' --reported-f 18.44 --reported-p 0.001 --p-is-threshold --decimals-mean 2 --decimals-sd 2 --decimals-f 2",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "The reported F is smaller than the printed means and SDs support, so the mood manipulation check is if anything understated and the manipulation is significant either way."
      },
      "notes": "DELIBERATELY RECORDED BELOW THE TOOL'S VERDICT. rivets_anova returned `highly_suspicious`; I have recorded `suspicious` because the group sizes are my assumption, not the paper's. The pilot states only N = 45 across three conditions and never prints cell sizes, so the equal split of 15/15/15 is an inference, and rulebook rule 4 caps an assumption-dependent finding at `suspicious`. The assumption is not arbitrary -- 45 divides evenly by three and the ANOVA error df of 42 confirms three groups totalling 45 -- but unequal cells would change the achievable F interval and could reconcile the reported value. Not suitable as a headline for that reason."
    },
    {
      "id": "e3_effect_sizes_extreme",
      "location": "Table 2, Self-evaluation and Similarity rows, positive mood columns",
      "technique": "check_effect_plausibility",
      "consistent": false,
      "severity": "suspicious",
      "quote": "However, when the cue was unambiguous, participants assimilated to the comparison targets, as expected, F(1, 94) = 92.47, p < .001.",
      "reported": {
        "selfeval_cells": "6.58 (.52) vs 4.08 (.52)",
        "similarity_cells": "7.06 (.53) vs 4.14 (.59)",
        "effect_size_printed_by_paper": "none"
      },
      "computed": {
        "hedges_g_selfeval": 4.64191,
        "ci95_selfeval": [
          3.229672,
          6.385713
        ],
        "hedges_g_similarity": 5.027274,
        "ci95_similarity": [
          3.5305,
          6.883139
        ],
        "pooled_sd_selfeval": 0.52,
        "n_per_group": 12,
        "tool_verdict": "consistent, the tool reports magnitude and declines to judge it",
        "tool": "check_effect_plausibility"
      },
      "inputs": {
        "comparison_1": {
          "mean1": 6.58,
          "sd1": 0.52,
          "n1": 12,
          "mean2": 4.08,
          "sd2": 0.52,
          "n2": 12
        },
        "comparison_2": {
          "mean1": 7.06,
          "sd1": 0.53,
          "n1": 12,
          "mean2": 4.14,
          "sd2": 0.59,
          "n2": 12
        },
        "design": "between"
      },
      "reproduction": "metascience effect-size --mean1 6.58 --sd1 0.52 --n1 12 --mean2 4.08 --sd2 0.52 --n2 12 --design between",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 2,
        "explanation": "The two headline Experiment 3 contrasts imply standardised effects near g = 5 on single-item and three-item rating scales, an order of magnitude above what this literature ordinarily reports."
      },
      "notes": "ESCALATED ABOVE THE TOOL'S VERDICT, and the grounds are stated so a reader can discount it. check_effect_plausibility returned `consistent`, because it reports magnitude and explicitly declines to judge it without a comparison class; I have recorded `suspicious` under rulebook rule 6, resting on the tool's own note that '|d| = 4.64 is remarkable in any field' and on the same pattern appearing in both contrasts. The three ordinary causes the tool names were considered: a units mismatch is ruled out, since both rows are the paper's own rating scales; a waitlist comparator does not apply, since these are randomised between-subjects cells; SEM-read-as-SD cannot be fully ruled out, because NEITHER table carries a footnote defining the parenthetical value -- the reading as SD comes from the prose, which writes 'M = x, SD = y' for the same quantities. If the parentheses were SEMs these d values would be inflated by sqrt(12). That ambiguity is a genuine limit on this finding."
    },
    {
      "id": "table2_check_denominator",
      "location": "Table 2 (Experiment 3), all 16 cells",
      "technique": "grimmer",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Effects of upward versus downward comparisons on self-evaluations and ratings of target similarity as function of mood and ambiguity of similarity information",
      "reported": {
        "n_cells": 16,
        "n_self_evaluation_cells": 8,
        "n_similarity_cells": 8
      },
      "computed": {
        "n_checks_run": 24,
        "n_consistent": 20,
        "n_flagged": 4,
        "n_refused": 8,
        "refusal_reason": "all 8 Similarity cells are a multi-item composite whose granularity is 1/(items*n), and grim/grimmer/sprite have no items parameter",
        "tools_dispatched": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct"
        ],
        "tool": "check_table (dispatching grim_check, grimmer_check and sprite_reconstruct)"
      },
      "inputs": {
        "cells": 16,
        "n_per_cell": 12,
        "variables": "selfeval7 (likert_item, 1-7, 1 item) and similarity9 (likert_composite, 1-9, 3 items)",
        "bindings": {
          "Self-evaluation": "selfeval7",
          "Similarity": "similarity9"
        }
      },
      "reproduction": "metascience check-table --cells '[{\"raw\":\"6.58 (.52)\",\"row_label\":\"Self-evaluation\",\"col_label\":\"Positive | Unambiguous | Upward\",\"n\":12}]' --variables '[{\"id\":\"selfeval7\",\"name\":\"Self-evaluation\",\"measurement_level\":\"ordinal\",\"discreteness\":\"discrete\",\"family\":\"likert_item\",\"lower_bound\":1,\"upper_bound\":7,\"bounds_are_stated\":true,\"n_items\":1,\"confidence\":\"high\"}]' --bindings '{\"Self-evaluation\":\"selfeval7\"}'",
      "consequence": {
        "basis": "computed",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "This is the coverage denominator for Table 2: 2 of the 8 self-evaluation cells fail granularity checks and the 8 similarity cells could not be checked at all."
      },
      "notes": "Recorded so the two impossible cells are read against the right denominator. All eight Self-evaluation means pass GRIM at n = 12, and six of eight also pass GRIMMER and SPRITE. The eight Similarity cells are a genuine coverage hole rather than a clean result: they are means of three nine-point items, so their granularity is 1/36 rather than 1/12, and the dispatch correctly refuses them rather than checking at the wrong step size. All 16 cells typed as `ambiguous` on syntax alone, since an unlabelled 'X (Y)' is equally a mean (SD) and an n (%), and were resolved only by declaring the variables from the Method text. The technique is recorded as grimmer because check_table is a dispatcher rather than a technique; the checks it ran were grim_check, grimmer_check and sprite_reconstruct."
    },
    {
      "id": "table1_uncheckable_for_want_of_n",
      "location": "Table 1 (Experiment 2), all 8 cells",
      "technique": "grim",
      "consistent": false,
      "severity": "indeterminate",
      "quote": "5.25 (.93)",
      "reported": {
        "n_cells": 8,
        "n_per_cell_printed": null
      },
      "computed": {
        "n_checks_run": 0,
        "n_refused": 24,
        "refusal_reason": "grim_check, grimmer_check and sprite_reconstruct each need n and no cell carries one",
        "why_n_could_not_be_derived": "the factorial holds 126 participants (error df 118 plus 8 cells) across 8 cells, and 126 is not divisible by 8, so the cells are provably unequal and no single n applies",
        "tool": "check_table (dispatching grim_check, grimmer_check and sprite_reconstruct)"
      },
      "inputs": {
        "cells": 8,
        "variables": "selfeval7 (likert_item, 1-7, 1 item)",
        "bindings": {
          "Self-evaluation": "selfeval7"
        },
        "n": "not supplied, because none can be derived"
      },
      "reproduction": "metascience check-table --cells '[{\"raw\":\"5.25 (.93)\",\"row_label\":\"Self-evaluation\",\"col_label\":\"Positive mood | Same birthday | Upward\"}]' --variables '[{\"id\":\"selfeval7\",\"name\":\"Self-evaluation\",\"measurement_level\":\"ordinal\",\"discreteness\":\"discrete\",\"family\":\"likert_item\",\"lower_bound\":1,\"upper_bound\":7,\"bounds_are_stated\":true,\"n_items\":1,\"confidence\":\"high\"}]' --bindings '{\"Self-evaluation\":\"selfeval7\"}'",
      "consequence": {
        "basis": "computed",
        "flips_significance": null,
        "claims_affected": null,
        "explanation": "Experiment 2's entire results table is outside the reach of granularity checking, so nothing in this report should be read as clearing it."
      },
      "notes": "This is a refusal, not a clean bill. The same arithmetic that made Table 2 checkable defeats Table 1: Experiment 3's 96 splits evenly into 8 cells of 12, whereas Experiment 2's 126 does not split evenly into 8, and the paper prints no cell sizes. Unlike Table 2 there is no even-split assumption available, so I did not guess an n; doing so is the standard route to a false GRIM accusation. Experiment 2's eight cell means are therefore recorded as unchecked. The technique is recorded as grim because check_table is a dispatcher rather than a technique."
    },
    {
      "id": "xml_pdf_table_reconciliation",
      "location": "Tables 1 and 2, XML grid against PDF grid",
      "technique": "reconcile",
      "consistent": true,
      "severity": "consistent",
      "quote": "6.58 (.90)",
      "reported": {
        "xml_cells_table1": 8,
        "pdf_cells_table1": 8,
        "xml_cells_table2": 16,
        "pdf_cells_table2": 16
      },
      "computed": {
        "discrepant_cells": 0,
        "header_structure_agrees": true,
        "one_material_difference": "the XML reports 0 footnotes for Table 1, while the PDF carries a footnote giving Experiment 2's control condition (M = 4.20, SD = .86) that the XML dropped entirely",
        "method": "cell-by-cell comparison of the get_table grid against the extract_pdf grid for the same two tables"
      },
      "inputs": {
        "xml_tables": [
          1,
          2
        ],
        "pdf_pages": [
          9,
          11
        ]
      },
      "reproduction": "metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.pdf --first-page 9 --last-page 11",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": null,
        "explanation": "Confirms that every granularity finding on Table 2 rests on values both sources agree the paper printed."
      },
      "notes": "Neither table was flagged alignment_uncertain or image_only, and the reconciliation confirms that. The one gap runs the other way: the XML lost a Table 1 footnote carrying a mean and SD found nowhere else in the paper. A review working from the XML alone would have missed Experiment 2's control condition entirely, and with it the fact that the same control mean of 4.20 appears in Experiment 4."
    },
    {
      "id": "multiplicity_exp3_planned_comparisons",
      "location": "Experiment 3, planned comparisons",
      "technique": "multiplicity_report",
      "consistent": true,
      "severity": "consistent",
      "quote": "in the presence of ambiguous information, participants in a positive mood rated upward comparison targets as more similar to the self than downward comparison targets, F(1, 94) = 53.17, p < .001.",
      "reported": {
        "family_size_as_submitted": 6,
        "n_with_exact_p": 3,
        "n_reported_as_threshold": 3
      },
      "computed": {
        "n_tests_evaluated": 3,
        "fwer_if_independent": 0.1426,
        "bonferroni_threshold": 0.016667,
        "by_threshold": 0.009091,
        "n_significant_uncorrected": 1,
        "n_surviving_floor": 1,
        "n_surviving_ceiling": 1,
        "n_claims_lost_to_correction": 0,
        "tool": "multiplicity_report"
      },
      "inputs": {
        "family_label": "Experiment 3 planned comparisons on self-evaluation and similarity (the only experiment with no stated Tukey HSD follow-up)",
        "alpha": 0.05,
        "n_tests_submitted": 6
      },
      "reproduction": "metascience multiplicity --family-label 'Experiment 3 planned comparisons' --alpha 0.05 --tests '[{\"id\":\"e3_sim_amb_pos\",\"p_value\":0.001,\"correction_applied\":\"none\"},{\"id\":\"e3_sim_neu_amb\",\"p_value\":0.58,\"correction_applied\":\"none\"},{\"id\":\"e3_sim_neu_unamb\",\"p_value\":0.83,\"correction_applied\":\"none\"}]'",
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "No Experiment 3 claim is lost to any of the four corrections; the significant results sit far below every corrected threshold."
      },
      "notes": "Recorded partly to document that multiplicity is NOT a problem in this paper, which is worth saying explicitly. Experiment 3 was chosen as the family because it is the only experiment lacking a stated correction: footnote 2 (PDF page 8) states that Experiment 2's contrasts were re-run with Tukey's HSD, and footnote 5 (PDF page 13) states the same for Experiment 4, each reporting which single contrast changed status. That is more multiplicity discipline than most papers of this vintage show. Three of the six Experiment 3 comparisons report p as a threshold and were dropped rather than coerced, so the real family is larger than the three evaluated."
    },
    {
      "id": "e3_manipulation_f_recomputes",
      "location": "Experiment 3, Manipulation check, direction of comparison",
      "technique": "recalc_anova",
      "consistent": true,
      "severity": "consistent",
      "quote": "the upward comparison target was rated more attractive (M = 7.33, SD = 1.19) than the downward target (M = 4.17, SD = 1.19), F(1,88) = 170.34, p < .001.",
      "reported": {
        "F": 170.34,
        "df": "1, 88"
      },
      "computed": {
        "calculated_f": 169.235506,
        "achievable_f_interval": [
          166.761786,
          171.748545
        ],
        "f_matches": true,
        "ms_between": 239.6544,
        "ms_within": 1.4161,
        "tool": "recalc_anova"
      },
      "inputs": {
        "means": [
          7.33,
          4.17
        ],
        "sds": [
          1.19,
          1.19
        ],
        "ns": [
          48,
          48
        ],
        "reported_f": 170.34,
        "decimals_mean": 2,
        "decimals_sd": 2
      },
      "reproduction": "metascience anova --means '[7.33,4.17]' --sds '[1.19,1.19]' --ns '[48,48]' --reported-f 170.34 --decimals-mean 2 --decimals-sd 2",
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "The manipulation-check F is exactly what its own printed means and SDs imply."
      },
      "notes": "Worth reading alongside e3_target_attractiveness_off_scale. The F is internally coherent with the two means, one of which lies above the maximum of the scale the paper says was used. Whatever produced these numbers produced a mutually consistent set, so the inconsistency is with the instrument rather than within the arithmetic. The recomputation uses a one-way error df of 94 where the paper prints 88, its factorial error term, which is a legitimate difference and does not affect the F."
    },
    {
      "id": "e1_manipulation_f_indeterminate",
      "location": "Experiment 1, Manipulation check",
      "technique": "recalc_anova",
      "consistent": false,
      "severity": "indeterminate",
      "quote": "the upward comparison target was rated more attractive (M = 5.71, SD = .75) than the downward target (M = 3.57, SD = 1.47), F(1,43) = 38.80, p < .001.",
      "reported": {
        "F": 38.8,
        "df": "1, 43"
      },
      "computed": {
        "calculated_f_one_way": 40.021088,
        "achievable_f_interval": [
          39.324747,
          40.729203
        ],
        "f_matches": false,
        "tool_verdict": "suspicious",
        "recorded_severity": "indeterminate",
        "assumed_ns": [
          24,
          23
        ],
        "tool": "recalc_anova"
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
          24,
          23
        ],
        "reported_f": 38.8,
        "decimals_mean": 2,
        "decimals_sd": 2
      },
      "reproduction": "metascience anova --means '[5.71,3.57]' --sds '[0.75,1.47]' --ns '[24,23]' --reported-f 38.80 --decimals-mean 2 --decimals-sd 2",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": null,
        "explanation": "Nothing follows from this: the mismatch is fully explained by the tool having recomputed a different model from the one the paper ran."
      },
      "notes": "DELIBERATELY RECORDED BELOW THE TOOL'S VERDICT, and it should not be read as a finding against the paper. recalc_anova returned `suspicious`, but it computes a ONE-WAY F, and the paper explicitly ran a 2x2 ANOVA -- 'A 2(similarity cue: shared birthday vs. different birthday) x 2(direction: upward vs. downward) ANOVA' -- whose error term removes the cue main effect and the interaction and is therefore not the pooled two-group variance the tool used. The printed error df of 43 confirms the 2x2 error term. A discrepancy of this size is exactly what that model difference produces. The cell sizes of 24 and 23 are also assumed, since 47 does not split evenly. Two independent reasons why no verdict is available here."
    },
    {
      "id": "statcheck_sweep",
      "location": "Whole article, all NHST results reported in prose",
      "technique": "statcheck",
      "consistent": false,
      "severity": "suspicious",
      "quote": "A one-way Analysis of Variance (ANOVA) revealed that the mood manipulation significantly affected participant mood, F(2, 42) = 18.44, p < .001.",
      "reported": {
        "stats_extracted": 22
      },
      "computed": {
        "errors_flagged": 20,
        "decision_errors": 0,
        "flags_that_are_rounding_artifacts_on_inspection": 18,
        "flags_with_a_material_gap": 2,
        "material_flag_1": "F(1, 42) = .27, p = .76 where the printed df imply p = .606",
        "material_flag_2": "F(1, 94) = 1.50, p = .83 where the statistic implies p = .224",
        "example_of_an_artifact_flag": "F(1, 43) = 7.77, p = .008 against a computed .007877",
        "tool": "statcheck"
      },
      "inputs": {
        "pdf_path": "/mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.pdf"
      },
      "reproduction": "metascience statcheck --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.1007--s11031-011-9216-y/10.1007--s11031-011-9216-y.pdf",
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "Zero decision errors: no reported p crosses .05 in the wrong direction, so no significance claim in the paper changes on recomputation."
      },
      "notes": "The headline count of 20 errors in 22 statistics badly overstates the problem and must not be reported as-is. statcheck compares a reported p against the recomputed one without carrying the printed precision, so it flags .008 against .007877 and .03 against .025341 as errors when both are ordinary rounding. Reading the 22 rows individually, 18 are of that kind. The two with a material gap are recorded as separate findings, pilot_selfeval_df1_wrong and e3_f150_p83. statcheck's own decision_errors count of 0 is the more informative number here. Note also that statcheck parses only prose in APA form, so the many results this paper reports as 'Fs < 1', 'p > .05' or 'ps > .84' are invisible to it and the denominator of 22 understates the number of comparisons made."
    },
    {
      "id": "exp3_design_sensitivity",
      "location": "Experiment 3, Participants",
      "technique": "check_effect_plausibility",
      "consistent": true,
      "severity": "consistent",
      "quote": "University students (N = 96) participated in the study for course credit.",
      "reported": {
        "N": 96,
        "n_per_cell_derived": 12,
        "n_per_pairwise_contrast": 24,
        "power_analysis_reported_by_paper": "none"
      },
      "computed": {
        "required_n_total_for_d_of_0_8_at_80_percent_power": 52,
        "required_n_per_group": 26,
        "achieved_power_at_that_n": 0.8075,
        "actual_n_total_per_pairwise_contrast": 24,
        "ratio_actual_to_required": 0.462,
        "adequately_powered_for_d_0_8": false,
        "tool": "required_n"
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
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": null,
        "explanation": "Context for the reader, not a defect: a pairwise cell contrast in Experiment 3 rests on 12 participants per group."
      },
      "notes": "No experiment in this paper reports an a-priori power analysis, so verify_power_analysis has nothing to check, and that absence is itself the reporting observation. required_n renders no verdict and its severity is always `consistent`; a small study is not a wrong one. The comparison worth making is against e3_effect_sizes_extreme: a design with 12 per cell, powered to detect roughly d = 0.8 only at twice its size, returns observed effects near g = 5. That is the combination in which selection inflates estimates, and it is for the editorial pass to weigh."
    },
    {
      "id": "data_availability_state_but_withhold",
      "location": "Experiment 3, footnote 4 (PDF page 12)",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "4 Complete data and results available from the first author.",
      "reported": {
        "data_availability_statement": "available from the first author",
        "data_actually_provided": "none",
        "supplementary_files_present": "none"
      },
      "computed": {
        "observation": "the paper's sole data-availability provision is a promise routed through one author, with no repository, accession number, or supplementary file",
        "method": "reading of the paper's footnotes and inspection of the paper directory for supplementary material"
      },
      "inputs": {
        "source": "PDF page 12, footnote 4"
      },
      "reproduction": "No command applies: this is a reporting-practice observation, not a calculation.",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": null,
        "explanation": "None of the granularity anomalies in this report can be resolved without the underlying data, and the paper provides no route to it that does not depend on an author's cooperation."
      },
      "notes": "Rulebook rule 7. A 'data available on request' footnote was entirely conventional for a 2011 psychology paper and is not by itself evidence of anything. It is recorded because it is the only data provision the paper makes, and because the impossible mean and SD pairs found here are precisely the claims that raw data would settle. The paper carries no supplementary files, so nothing further could be swept."
    },
    {
      "id": "methods_typo_in_scale_defining_sentence",
      "location": "Experiment 3, Procedure",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "Participants reported their major, gender, age, and then rated their own attractiveness (on the seam measures used in Experiments 1 and 2).",
      "reported": {
        "printed_word": "seam",
        "intended_word": "same"
      },
      "computed": {
        "observation": "the misspelling sits in the only sentence that identifies which instrument Experiment 3 used to measure attractiveness, and therefore the only sentence establishing that experiment's scale range",
        "method": "reading; confirmed present in both the XML full text and on PDF page 10"
      },
      "inputs": {
        "source": "Experiment 3 Procedure, XML and PDF page 10"
      },
      "reproduction": "No command applies: this is a textual observation, not a calculation.",
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "This sentence is the sole basis for treating Experiment 3's attractiveness ratings as 7-point, which is what makes the reported mean of 7.33 out of range."
      },
      "notes": "A typo alone is trivial and would not normally be recorded. It is recorded here because of where it sits: the load-bearing sentence for the paper's strongest single anomaly. It weakens confidence that the sentence was checked, and so weakens confidence in the cross-reference on which e3_target_attractiveness_off_scale depends. The paper contains other errors of the same character in results-carrying sentences -- 'p = 011' in Experiment 1, 'p = 001' in Experiment 4, and 'the attractive comparison target was rated more attractive than the (M = 5.58, SD = .78) than the unattractive target' in Experiment 4 -- suggesting the Results and Methods were not closely proofread."
    }
  ],
  "figures": [
    {
      "label": "Fig. 1",
      "is_data_figure": false,
      "caption": "Referenced throughout as a conceptual model ('as shown in the right-most portion of Fig. 1'; 'The shaded area of Fig. 1 illustrates the steps to asymmetric responding'). The caption text itself was not recovered from either source.",
      "n_panels": 1,
      "carries_unique_values": false,
      "panels": [
        {
          "panel": "A",
          "chart_type": "schematic",
          "shows": "A process diagram of the hypothesised route from ambiguous similarity information to asymmetric (self-serving) versus symmetric responding, with a shaded region marking the steps positive mood is argued to enable."
        }
      ]
    },
    {
      "label": "Fig. 2",
      "page": 11,
      "is_data_figure": true,
      "caption": "In the presence of ambiguous distinctiveness information, positive mood leads to more positive self-evaluations, across upward and downward comparisons, than does neutral mood (from Experiment 3)",
      "n_panels": 1,
      "carries_unique_values": false,
      "panels": [
        {
          "panel": "A",
          "chart_type": "bar",
          "shows": "Experiment 3 self-evaluation means by mood (positive vs neutral), ambiguity of the similarity cue, and direction of comparison -- the same eight means printed in Table 2."
        }
      ]
    },
    {
      "label": "Fig. 3",
      "page": 13,
      "is_data_figure": true,
      "caption": "Asymmetric responses to comparisons in positive mood are moderated by cognitive load; responses without mood induction are not. From Experiment 4",
      "n_panels": 1,
      "carries_unique_values": false,
      "panels": [
        {
          "panel": "A",
          "chart_type": "bar",
          "shows": "Experiment 4 self-evaluation means by cognitive load, mood and direction of comparison -- the eight cell means plus the control, all also printed in the Results prose. This is the figure that would settle whether the transposed means in e4_means_reversed_in_prose are a writing error or a data error."
        }
      ]
    }
  ],
  "coverage": {
    "stats_found": 46,
    "tables_checked": [
      "Table 1 (Experiment 2) - XML grid, PDF grid, and the PDF-only footnote",
      "Table 2 (Experiment 3) - XML grid and PDF grid"
    ],
    "tools_run": [
      "extract_xml",
      "get_table",
      "extract_pdf",
      "parse_cells_typed",
      "check_table",
      "statcheck",
      "grim_check",
      "grimmer_check",
      "sprite_reconstruct",
      "r_sprite_ground_truth",
      "recalc_f_to_p",
      "recalc_anova",
      "rivets_anova",
      "check_summation_batch",
      "detect_duplication",
      "multiplicity_report",
      "check_effect_plausibility",
      "required_n"
    ]
  },
  "unchecked": [
    {
      "location": "Table 1 (Experiment 2), all 8 self-evaluation cells",
      "reason": "No cell n is printed and none can be derived: the factorial holds 126 participants (error df 118 plus 8 cells) across 8 cells, and 126 is not divisible by 8, so the cells are provably unequal. check_table refused all 24 candidate checks for want of n. Guessing a denominator here is the standard route to a false GRIM accusation."
    },
    {
      "location": "Table 2 (Experiment 3), all 8 Similarity cells",
      "reason": "The similarity index is the mean of three nine-point items, so its granularity is 1/(3n) = 1/36 rather than 1/12. grim_check, grimmer_check and sprite_reconstruct have no items parameter, so checking these at 1/n would manufacture impossibilities; check_table refused all 8 for exactly this reason. A GRIM implementation taking an items argument, such as R scrutiny, could check them."
    },
    {
      "location": "Pilot study, mood index and self-evaluation index means",
      "reason": "Both are means of multiple nine-point items (4 items and 3 items respectively), so the same items-granularity limit applies as for the Table 2 similarity cells. Cell sizes are also unstated."
    },
    {
      "location": "Experiment 3, Manipulation check, self-reported mood (M = 7.33, SD = .86; M = 5.44, SD = .97)",
      "reason": "Experiment 3 never states the range of its mood measure. Experiment 2 used a 1-7 mood item and the Pilot used a 1-9 index; neither is stated to apply here. Without stated bounds no range check may run, and inventing a bound would invert the check rather than weaken it. Note the mean of 7.33 is the same value as the (checkable, out-of-range) target-attractiveness mean in the same section."
    },
    {
      "location": "Experiment 2 and Experiment 4, all cell means reported in prose",
      "reason": "No cell sizes are printed for either experiment, and in Experiment 4 the stated N contradicts the degrees of freedom (see e4_sample_size_reconciliation), so no denominator can be trusted even approximately. Granularity checks were not attempted."
    },
    {
      "location": "Figures 1, 2 and 3",
      "reason": "Values plotted in the figures were not read. No figure caption defines what any error bar represents, so no dispersion could be recovered even if the marks were measured. Figures 2 and 3 appear to plot means also printed in Table 2 and in Experiment 4's prose respectively, so this is not believed to be a coverage hole, but that could not be confirmed without reading the plots. Figure 3 would settle whether the transposed means in e4_means_reversed_in_prose are a writing error or a data error."
    },
    {
      "location": "Supplementary materials",
      "reason": "The paper directory contains no supplementary files and the article provides none: its only data provision is footnote 4, 'Complete data and results available from the first author.' Recorded as not provided, rather than present-but-unreadable."
    },
    {
      "location": "Reported Cronbach's alpha values (.91, .71, .87)",
      "reason": "Reliability coefficients cannot be verified without the item-level covariance matrix, which the paper does not print. No registered tool applies."
    },
    {
      "location": "Results reported as 'Fs < 1', 'p > .05', 'ps > .84' and 'p > .9'",
      "reason": "These are bounds with no statistic attached. statcheck cannot parse them and no recomputation is possible; they are counted in neither the statcheck denominator of 22 nor the multiplicity families, so both understate the true number of comparisons made."
    },
    {
      "location": "Experiment 2 and Experiment 4 Tukey HSD re-analyses (footnotes 2 and 5)",
      "reason": "The footnotes report only which single contrast changed status and at what p (.07 and .13 respectively), with no test statistics or group sizes. Nothing can be recomputed, though their existence is why no multiplicity finding was raised against those two experiments."
    },
    {
      "location": "Experiment 2, mood and attractiveness manipulation-check means",
      "reason": "Group sizes are not printed. The control n of 15 is derivable from the degrees of freedom, but the positive and negative mood group sizes are not, since 126 does not split evenly into the 8 factorial cells."
    }
  ],
  "second_look": {
    "n_accusatory": 15,
    "n_flagged": 15,
    "by_marker": {
      "quote_not_located": 15
    },
    "items": [
      {
        "id": "e3_target_attractiveness_off_scale",
        "severity": "impossible",
        "location": "Experiment 3, Manipulation check",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "e4_control_sd_impossible",
        "severity": "impossible",
        "location": "Experiment 4, No load conditions and Cognitive load conditions, control condition",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table2_sd_52_impossible",
        "severity": "impossible",
        "location": "Table 2, Self-evaluation row, Positive/Unambiguous Upward and Positive/Unambiguous Downward cells",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "e4_sample_size_reconciliation",
        "severity": "suspicious",
        "location": "Experiment 4, Participants and design vs Results and discussion",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "e4_means_reversed_in_prose",
        "severity": "suspicious",
        "location": "Experiment 4, Cognitive load conditions, final sentence",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "pilot_selfeval_df1_wrong",
        "severity": "suspicious",
        "location": "Pilot study, second results paragraph",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "e3_f150_p83",
        "severity": "suspicious",
        "location": "Experiment 3, Perceptions of similarity, final sentence",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "e1_p_missing_decimal_and_df",
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
        "id": "table1_caption_promises_absent_measures",
        "severity": "suspicious",
        "location": "Table 1 caption vs Table 1 body",
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
        "location": "Pilot study, mood manipulation check",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "e3_effect_sizes_extreme",
        "severity": "suspicious",
        "location": "Table 2, Self-evaluation and Similarity rows, positive mood columns",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table2_check_denominator",
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
        "id": "statcheck_sweep",
        "severity": "suspicious",
        "location": "Whole article, all NHST results reported in prose",
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
        "location": "Experiment 3, footnote 4 (PDF page 12)",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "methods_typo_in_scale_defining_sentence",
        "severity": "suspicious",
        "location": "Experiment 3, Procedure",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      }
    ],
    "note": "15 of 15 accusation(s) carry a named weakness in their evidence. Each is listed with what would settle it. This is a worklist, not a verdict: none of these is wrong because it is listed, and a marker you resolve should be recorded in `triage` like any other triage decision."
  }
}
```

Triage these findings (confirm / deprioritize / reinterpret per the rulebook — especially baseline-similarity results), add the contextual reasoning the sweep cannot do, and emit the report JSON.