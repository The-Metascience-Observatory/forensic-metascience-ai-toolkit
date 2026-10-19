Write the editorial forensic review for this paper.

Read the paper body with the Read tool: `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/airforce/paper/markdown/body.md`

What the sweep actually ran, which is the DENOMINATOR your verdict sits in:

```json
{
  "checks_passed": 24,
  "of_which_collapsed_by_check_table": 9,
  "checks_refused_indeterminate": 5,
  "checks_flagged": 6,
  "checks_total": 35,
  "by_severity": {
    "suspicious": 5,
    "impossible": 1,
    "consistent": 15,
    "indeterminate": 5
  },
  "by_outcome": {
    "flagged": 6,
    "pass": 15,
    "refused": 5
  },
  "rounding_convention": {
    "n_fit_only_under_truncation": 0,
    "n_granularity_checks": 43,
    "note": "Values that fail the round-half convention but are consistent if the reporter TRUNCATES (SPSS's default, and several journal styles). NOT a finding and never counted as one: a single instance is a house style. The RATE is the signal -- this class of anomaly is commoner in papers with more serious problems, so a high proportion is grounds to look harder, not evidence in itself."
  },
  "grace": {
    "n_items": 43,
    "n_reconciled_strictly": 43,
    "n_rescued": 0,
    "by_grace": {},
    "n_with_direction": 0,
    "n_leaning_high": 0,
    "n_leaning_low": 0,
    "sign_test_p": null,
    "reading": "Nothing needed an allowance; every item reconciled on its printed values."
  },
  "sd_convention": {
    "n_fit_only_under_population_sd": 0,
    "n_granularity_checks": 43,
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
  "paper_id": "paper",
  "findings": [
    {
      "id": "table3_survey_denominators_grim_sweep",
      "location": "Table III, survey rows (brief effectiveness and MVI compliance)",
      "technique": "grim_sweep",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience grim-sweep --values 95.89,90.41,14.86,37.84,20.27 --n-max 80 --n-min 2 --decimals 2 --value-type percentage --n-max-source stated",
      "quote": "Furthermore, all trainees completed questionnaires regarding their perceptions regarding the usefulness and effectiveness of their MVI briefing and were asked to quantify their MVI compliance.",
      "inputs": {
        "values": [
          95.89,
          90.41,
          14.86,
          37.84,
          20.27
        ],
        "n_max": 80,
        "n_min": 2,
        "decimals": 2,
        "value_type": "percentage",
        "n_max_source": "stated"
      },
      "reported": {
        "video_only_n_header": 80,
        "in_person_n_header": 79,
        "video_survey_pcts": [
          95.89,
          90.41,
          14.86,
          37.84,
          20.27
        ],
        "in_person_survey_pcts": [
          98.63,
          34.25,
          63.01,
          8.22
        ]
      },
      "computed": {
        "video_joint_viable_ns": [],
        "video_briefing_unique_n": 73,
        "video_briefing_counts": "70/73 and 66/73",
        "video_compliance_unique_n": 74,
        "video_compliance_counts": "11/74, 28/74, 15/74",
        "in_person_joint_viable_n": 73,
        "in_person_counts": "72/73, 25/73, 46/73, 6/73",
        "missing_vs_enrolled_video_briefing": 7,
        "missing_vs_enrolled_video_compliance": 6,
        "missing_vs_enrolled_in_person": 6
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "Chi-squared p-values in Table III match the implied survey ns of 73\u201374, so the significance claims survive; the printed column ns of 80 and 79 are not the analysis denominators."
      },
      "notes": "Tool grim_sweep returned empty joint n-set for the five video-only survey percentages over the stated n_max=80 (verdict impossible). Downgraded to suspicious: the percentages are uniquely recovered at n=73 (briefing items) and n=74 (compliance items), and the in-person survey items share a unique n=73 rather than 79. Recalculated chi-squared p-values from those reconstructed 2\u00d72 tables match the printed p-values, so the authors analysed the smaller denominators. The 6\u20137 person gap exceeds the three-patient-or-5%-of-n missingness bound (Rule 15), and Methods states all trainees completed questionnaires, which is an explicit completeness claim for these rows. Innocent reading is item-level nonresponse under an enrollment header. GRIM-family impossible verdicts await the R scrutiny cross-check (editorial stage)."
    },
    {
      "id": "table3_survey_pct_vs_enrolled_n",
      "location": "Table III, Found brief effective / Confident / Took MVI daily / most days / Never rows",
      "technique": "grim_percentage",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience grim-sweep --values 95.89,90.41,14.86,37.84,20.27 --n-max 80 --decimals 2 --value-type percentage --n-max-source stated",
      "quote": "| Found brief effective in explaining why MVI prescribed | 95.89                                        | 98.63                                        | .31                                          |",
      "inputs": {
        "percentages_video_n80": [
          95.89,
          90.41,
          14.86,
          37.84,
          20.27
        ],
        "percentages_inperson_n79": [
          98.63,
          34.25,
          63.01,
          8.22
        ],
        "decimals": 2,
        "data_type": "proportion"
      },
      "reported": {
        "n_video": 80,
        "n_inperson": 79
      },
      "computed": {
        "n80_implied_counts": [
          76.712,
          72.328,
          11.888,
          30.272,
          16.216
        ],
        "n79_implied_counts": [
          77.9177,
          27.0575,
          49.7779,
          6.4938
        ],
        "grim_at_enrolled_n": "impossible for 9 of 10 two-decimal survey cells; 100% at n=79 is consistent",
        "grim_at_implied_n73": "95.89% = 70/73 consistent"
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "Percentages are attainable at n=73 or 74, not at the printed enrollment ns; tests used the smaller n."
      },
      "notes": "Nine two-decimal survey percentages fail GRIM at the column header ns (80 and 79); 100% in-person confidence is the only survey cell that passes at n=79. check_table on Table III ran 22 grim_percentage checks: 10 impossible, 9 consistent, 3 indeterminate (0-dp cells with no discriminating power). The 10 impossibles are these survey cells plus video-only Medical hold 1.27%. Same denominator issue as the sweep finding; severity kept at suspicious rather than impossible because check_table\u2019s n_provenance note states the supplied n is typically the enrolled total and analysed n is often smaller. Awaiting R GRIM cross-check."
    },
    {
      "id": "table3_medical_hold_video_127",
      "location": "Table III, Medical hold row, video-only column",
      "technique": "grim_percentage",
      "consistent": false,
      "severity": "impossible",
      "reproduction": "metascience grim-sweep --values 1.27 --n-max 80 --n-min 80 --decimals 2 --value-type percentage --n-max-source stated",
      "quote": "| Medical hold                                           | 1.27                                         | 1.27                                         | .99                                          |",
      "inputs": {
        "percentage": 1.27,
        "n": 80,
        "decimals": 2,
        "data_type": "proportion"
      },
      "reported": {
        "video_only_pct": 1.27,
        "in_person_pct": 1.27,
        "n_video": 80,
        "n_inperson": 79,
        "p": 0.99
      },
      "computed": {
        "implied_count_at_n80": 1.016,
        "nearest_attainable_at_n80": "1/80 = 1.25%",
        "implied_count_at_n79": 1.0033,
        "in_person_1_of_79": "1.27% consistent"
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "Chi-squared p=.99 still matches one event in each arm (1/80 vs 1/79); only the video-only percentage is misstated."
      },
      "notes": "Routinely collected training-delay data, with the paper stating there were no losses or exclusions of routinely collected and linked data, so n=80 is the analysis denominator for this row (not a survey missingness issue). 1.27% is exactly 1/79, the in-person value printed in the adjacent cell; 1/80 prints as 1.25%. Innocent reading is copy-paste of 1.27 into both columns. Awaiting R GRIM cross-check. Chi-squared of [[1,79],[1,78]] gives p=0.993, matching the printed .99."
    },
    {
      "id": "table3_mski_chi2",
      "location": "Table III, MSKI row",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience chi2",
      "quote": "| MSKI                                                   | 31.25                                        | 17.72                                        | .047                                         |",
      "inputs": {
        "observed": [
          [
            25,
            55
          ],
          [
            14,
            65
          ]
        ],
        "reported_p": 0.047,
        "decimals_p": 3
      },
      "reported": {
        "video_pct": 31.25,
        "inperson_pct": 17.72,
        "p": 0.047
      },
      "computed": {
        "pearson_chi2": 3.9298,
        "pearson_p": 0.04744,
        "yates_p": 0.07217,
        "fisher_p": 0.06476,
        "or": 2.11
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "Pearson chi-squared matches p=.047; Yates and Fisher would not meet \u03b1=0.05, but the paper stated the chi-squared test and expected counts are all >5."
      },
      "notes": "Counts reconstructed as 25/80 vs 14/79, the unique 2\u00d72 that GRIM-passes both percentages at N=159. Headline MSKI result is convention-sensitive: Pearson p=0.047 matches the paper; Yates p=0.072 and Fisher p=0.065 would be non-significant. Not scored as an error because Methods specified chi-squared."
    },
    {
      "id": "table3_bsi_chi2",
      "location": "Table III, BSI row",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience chi2",
      "quote": "| BSI                                                    | 15                                           | 5.06                                         | .037                                         |",
      "inputs": {
        "observed": [
          [
            12,
            68
          ],
          [
            4,
            75
          ]
        ],
        "reported_p": 0.037,
        "decimals_p": 3
      },
      "reported": {
        "video_pct": 15,
        "inperson_pct": 5.06,
        "p": 0.037
      },
      "computed": {
        "pearson_chi2": 4.3365,
        "pearson_p": 0.0373,
        "yates_p": 0.06894,
        "fisher_p": 0.06232,
        "or": 3.31
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "Pearson chi-squared matches p=.037; Yates and Fisher would not meet \u03b1=0.05."
      },
      "notes": "Unique reconstruction 12/80 vs 4/79. Four BSI events in the in-person arm. Expected cell counts remain >5, so Pearson is the test the paper named. Same convention-sensitivity note as MSKI."
    },
    {
      "id": "table3_mski_reconstruct",
      "location": "Table III, MSKI row",
      "technique": "reconstruct_2x2",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience reconstruct-2x2 --pct-col1 31.25 --pct-col2 17.72 --n-total 159 --decimals 2 --value-type percentage",
      "quote": "| MSKI                                                   | 31.25                                        | 17.72                                        | .047                                         |",
      "inputs": {
        "pct_col1": 31.25,
        "pct_col2": 17.72,
        "n_total": 159,
        "decimals": 2
      },
      "reported": {
        "pct_video": 31.25,
        "pct_inperson": 17.72,
        "N": 159
      },
      "computed": {
        "n_solutions": 1,
        "A": 25,
        "B": 14,
        "col1_total": 80,
        "col2_total": 79
      }
    },
    {
      "id": "table3_bsi_reconstruct",
      "location": "Table III, BSI row",
      "technique": "reconstruct_2x2",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience reconstruct-2x2 --pct-col1 15 --pct-col2 5.06 --n-total 159 --decimals 2 --value-type percentage",
      "quote": "| BSI                                                    | 15                                           | 5.06                                         | .037                                         |",
      "inputs": {
        "pct_col1": 15,
        "pct_col2": 5.06,
        "n_total": 159,
        "decimals": 2
      },
      "reported": {
        "pct_video": 15,
        "pct_inperson": 5.06,
        "N": 159
      },
      "computed": {
        "n_solutions": 1,
        "A": 12,
        "B": 4,
        "col1_total": 80,
        "col2_total": 79
      }
    },
    {
      "id": "table3_survey_chi2_at_implied_n",
      "location": "Table III, survey p-values reconstructed at n=73/74",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience chi2",
      "quote": "| Took MVI daily                                         | 14.86                                        | 34.25                                        | .0063                                        |",
      "inputs": {
        "daily": [
          [
            11,
            63
          ],
          [
            25,
            48
          ]
        ],
        "most_days": [
          [
            28,
            46
          ],
          [
            46,
            27
          ]
        ],
        "never": [
          [
            15,
            59
          ],
          [
            6,
            67
          ]
        ],
        "confident": [
          [
            66,
            7
          ],
          [
            73,
            0
          ]
        ],
        "effective": [
          [
            70,
            3
          ],
          [
            72,
            1
          ]
        ]
      },
      "reported": {
        "p_daily": 0.0063,
        "p_most_days": 0.0023,
        "p_never": 0.037,
        "p_confident": 0.007,
        "p_effective": 0.31
      },
      "computed": {
        "p_daily_pearson": 0.006291,
        "p_most_days_pearson": 0.00227,
        "p_never_pearson": 0.036825,
        "p_confident_pearson": 0.006697,
        "p_effective_pearson": 0.310589
      },
      "notes": "Printed survey p-values match Pearson chi-squared on the GRIM-implied denominators (video briefing n=73, video compliance n=74, in-person n=73), not on the Table III header ns of 80 and 79. Confirms the survey percentages are internally consistent once the analysed n is used."
    },
    {
      "id": "table3_training_delay_chi2",
      "location": "Table III, Medical hold / Recycle rows",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience chi2",
      "quote": "| Recycle: fitness failure                               | 2.50                                         | 2.53                                         | .99                                          |",
      "inputs": {
        "medical_hold": [
          [
            1,
            79
          ],
          [
            1,
            78
          ]
        ],
        "fitness": [
          [
            2,
            78
          ],
          [
            2,
            77
          ]
        ],
        "admin": [
          [
            0,
            80
          ],
          [
            1,
            78
          ]
        ]
      },
      "reported": {
        "p_hold": 0.99,
        "p_fitness": 0.99,
        "p_admin": 0.31
      },
      "computed": {
        "p_hold_pearson": 0.9929,
        "p_fitness_pearson": 0.9898,
        "p_admin_pearson": 0.3127
      },
      "notes": "Training-delay percentages at enrollment n (except the video-only Medical hold 1.27% cell) reconstruct as 1, 0, 2 events and the printed p-values match Pearson chi-squared."
    },
    {
      "id": "table3_injury_grim_consistent",
      "location": "Table III, MSKI and BSI percentages at enrollment n",
      "technique": "grim_percentage",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience grim-sweep --values 31.25,17.72 --n-max 80 --decimals 2 --value-type percentage --n-max-source stated",
      "quote": "| MSKI                                                   | 31.25                                        | 17.72                                        | .047                                         |",
      "inputs": {
        "mski_video": {
          "percentage": 31.25,
          "n": 80,
          "decimals": 2
        },
        "mski_inperson": {
          "percentage": 17.72,
          "n": 79,
          "decimals": 2
        },
        "bsi_inperson": {
          "percentage": 5.06,
          "n": 79,
          "decimals": 2
        }
      },
      "reported": {
        "mski": [
          31.25,
          17.72
        ],
        "bsi": [
          15,
          5.06
        ]
      },
      "computed": {
        "mski_video_count": 25,
        "mski_inperson_count": 14,
        "bsi_inperson_count": 4
      },
      "notes": "Injury percentages (routinely collected; no losses) GRIM-pass at the printed enrollment ns. Video-only BSI 15% at 0 dp has no discriminating power at n=80 but equals 12/80 exactly."
    },
    {
      "id": "table2_age_uninformative",
      "location": "Table II, Age row, and Results sentence claiming no age difference",
      "technique": "flag_uninformative_stat",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience flag-uninformative --means 21,23 --sds 3,5 --ns 80,79 --decimals-mean 0 --decimals-sd 0",
      "quote": "No significant differences in age or BMI between cohorts were detected.",
      "inputs": {
        "means": [
          21,
          23
        ],
        "sds": [
          3,
          5
        ],
        "ns": [
          80,
          79
        ],
        "decimals_mean": 0,
        "decimals_sd": 0
      },
      "reported": {
        "age_video": "21 \u00b1 3",
        "age_inperson": "23 \u00b1 5",
        "claim": "no significant differences in age"
      },
      "computed": {
        "p_min": 6e-07,
        "p_max": 0.135,
        "straddles_0.05": true,
        "point_p_from_rounded_means_student": 0.00258,
        "point_d": -0.483,
        "ci95_d": [
          -0.801,
          -0.17
        ]
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "The printed 0-decimal age means are too coarse to confirm or refute the 'no significant difference in age' claim; if a true age difference exists it would confound the injury comparison."
      },
      "notes": "Point t from the rounded means is Welch t=\u22123.05, two-tailed p=0.0028, but the Monte Carlo/corner p-range given 0-dp rounding is [0.000, 0.135] and straddles 0.05. Do not read the point p as evidence that the authors missed a significant baseline difference: the paper\u2019s NS claim remains compatible with the rounding interval. BMI 24.1\u00b12.6 vs 24.0\u00b12.8 gives p\u22480.82, consistent with NS. Cap is suspicious per the tool (uninformative statistics are a flag, not an error)."
    },
    {
      "id": "table2_age_effect_size",
      "location": "Table II, Age row",
      "technique": "check_effect_plausibility",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience effect-size --mean1 21 --sd1 3 --n1 80 --mean2 23 --sd2 5 --n2 79 --design between",
      "quote": "| Age, year     | 21 \u00b1 3                        | 23 \u00b1 5                       |",
      "inputs": {
        "mean1": 21,
        "sd1": 3,
        "n1": 80,
        "mean2": 23,
        "sd2": 5,
        "n2": 79,
        "design": "between"
      },
      "reported": {
        "means": [
          21,
          23
        ],
        "sds": [
          3,
          5
        ]
      },
      "computed": {
        "hedges_g": -0.483,
        "cohens_d": -0.486,
        "ci95_d": [
          -0.801,
          -0.17
        ],
        "ci_spans_null": false
      },
      "notes": "Effect size from the printed (rounded) group statistics. Interval excludes 0 at the point estimates but see the uninformative-stat finding for the 0-dp rounding interval."
    },
    {
      "id": "table2_bmi_ttest",
      "location": "Table II, BMI row",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 24.1 --sd1 2.6 --n1 80 --mean2 24.0 --sd2 2.8 --n2 79 --decimals-mean 1 --decimals-sd 1",
      "quote": "| BMI           | 24.1 \u00b1 2.6                    | 24.0 \u00b1 2.8                   |",
      "inputs": {
        "mean1": 24.1,
        "sd1": 2.6,
        "n1": 80,
        "mean2": 24.0,
        "sd2": 2.8,
        "n2": 79,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "claim": "No significant differences in age or BMI"
      },
      "computed": {
        "welch_t": 0.233,
        "welch_p_two": 0.816
      },
      "notes": "No printed t or p; recomputed p\u22480.82 is compatible with the NS claim. Tool returned indeterminate for want of a reported p; recorded here as consistent with that claim."
    },
    {
      "id": "table2_duplication",
      "location": "Table II, two cohort columns",
      "technique": "detect_duplication",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience duplication-detect",
      "quote": "Values are reported as averages \u00b1 standard deviations (SD).",
      "inputs": {
        "blocks": 2,
        "cells_per_block": 2
      },
      "computed": {
        "max_identical_pairs": 0
      },
      "notes": "Only one mean/SD table; the two arms do not share identical (mean, SD) pairs."
    },
    {
      "id": "cohort_n_sum",
      "location": "Results, paragraph 1",
      "technique": "check_summation_batch",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience summation-batch",
      "quote": "Demographic characteristics of the 159 female trainees (80 in the video-only cohort,  and 79 in the in-person cohort)",
      "inputs": {
        "values": [
          80,
          79
        ],
        "expected_sum": 159
      },
      "computed": {
        "actual_sum": 159
      },
      "notes": "ARR identities also consistent: 17.72+13.5 versus 31.25 (difference 0.03, inside the printed-precision window); 5.06+10 versus 15."
    },
    {
      "id": "mski_rrr_nnipb",
      "location": "Discussion, MSKI and BSI risk reductions",
      "technique": "check_ratio",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-ratio --numerator 13.53 --denominator 31.25 --reported-ratio 0.43 --decimals-numerator 2 --decimals-denominator 2 --decimals-ratio 2",
      "quote": "The relative and absolute risk reductions for diagnosis with all MSKI were 43% and 13.5%, respectively. This absolute risk reduction corresponds to a number needed to in-person brief (NNIPB) of 7.4 to avoid one MSKI.",
      "inputs": {
        "mski_rrr": {
          "numerator": 13.53,
          "denominator": 31.25,
          "reported": 0.43
        },
        "nnipb": {
          "numerator": 100,
          "denominator": 13.5,
          "reported": 7.4
        },
        "events_prevented": {
          "numerator": 40,
          "denominator": 7.4,
          "reported": 5.4
        },
        "bsi_rrr": {
          "numerator": 9.94,
          "denominator": 15,
          "reported": 0.66
        }
      },
      "reported": {
        "mski_rrr": "43%",
        "mski_arr": "13.5%",
        "nnipb": 7.4,
        "prevent_per_brief": 5.4,
        "bsi_rrr": "66%",
        "bsi_arr": "10%",
        "bsi_nnipb": 10
      },
      "computed": {
        "mski_rrr": 0.433,
        "nnipb": 7.407,
        "prevent": 5.405,
        "bsi_rrr": 0.663
      }
    },
    {
      "id": "multiplicity_table3_all_chi2",
      "location": "Table III, all between-cohort chi-squared tests",
      "technique": "multiplicity_report",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience multiplicity",
      "quote": "Associations between categorical variables were analyzed using the chi-squared test. Significance was set to \u03b1\u2264 0.05.",
      "inputs": {
        "family_label": "Table III between-cohort chi-squared comparisons of survey, injury, and training-delay outcomes",
        "alpha": 0.05,
        "n_tests": 10,
        "p_values": [
          0.31,
          0.007,
          0.0063,
          0.0023,
          0.037,
          0.047,
          0.037,
          0.99,
          0.31,
          0.99
        ]
      },
      "reported": {
        "correction": "none"
      },
      "computed": {
        "n_significant_uncorrected": 6,
        "n_surviving_floor": 0,
        "n_surviving_ceiling": 3,
        "n_claims_lost_to_correction": 3,
        "bonferroni_threshold": 0.005,
        "bh_threshold": 0.015
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": true,
        "claims_affected": 3,
        "explanation": "Of six uncorrected p<.05 results, Benjamini\u2013Hochberg (most permissive) retains three and Bonferroni retains one (most days p=.0023); MSKI p=.047 and BSI p=.037 do not survive family-wise correction in this 10-test family."
      },
      "notes": "Uncorrected testing is ordinary; this is arithmetic on the printed family, not an accusation. BSI is nested in MSKI and survey items are correlated, so Benjamini\u2013Yekutieli is the relevant FDR bound (0 surviving). A tighter injury-only family of two tests has n_surviving_floor=0 (Bonferroni 0.025) and n_surviving_ceiling=2 (BH), with n_claims_lost_to_correction=0 on BH. Survey family of five: 3\u20134 of 4 uncorrected significant results survive."
    },
    {
      "id": "multiplicity_injury_family",
      "location": "Table III / Results, MSKI and BSI",
      "technique": "multiplicity_report",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience multiplicity",
      "quote": "In regard to injury, a significantly smaller proportion of the in-person cohort suffered MSKI (17.72% vs. 31.25%, P = .047) and BSI (5.06% vs.  15%, P = .037) compared to the video-only cohort.",
      "inputs": {
        "family_label": "injury outcomes MSKI and BSI",
        "alpha": 0.05,
        "p_values": [
          0.047,
          0.037
        ]
      },
      "computed": {
        "n_significant_uncorrected": 2,
        "n_surviving_floor": 0,
        "n_surviving_ceiling": 2,
        "n_claims_lost_to_correction": 0,
        "bonferroni_threshold": 0.025
      },
      "notes": "Load-bearing pair. Neither p survives Bonferroni/Holm at m=2; both survive BH. BSI is a subset of MSKI so the tests are dependent; BY would retain neither."
    },
    {
      "id": "power_analysis_not_reproducible",
      "location": "Methods, power analysis paragraph",
      "technique": "verify_power_analysis",
      "consistent": false,
      "severity": "indeterminate",
      "reproduction": "metascience power-check --test-type two_proportions --effect-size 0.25 --alpha 0.05 --target-power 0.99 --n-reported 77 --n-reported-is-per-group",
      "quote": "a power analysis calculation was completed using \u03b1\u2264 0.05 for the significance level, a power of 0.99. We estimated a 25% relatively greater daily MVI compliance in trainees receiving the in-person brief compared to those viewing the video alone, which yielded a need for each cohort to have 77 trainees to demonstrate a significant difference.",
      "inputs": {
        "test_type": "two_proportions",
        "effect_size_tried_as_h": 0.25,
        "alpha": 0.05,
        "target_power": 0.99,
        "n_reported": 77,
        "n_reported_is_per_group": true
      },
      "reported": {
        "alpha": 0.05,
        "power": 0.99,
        "relative_increase": "25%",
        "n_per_group": 77
      },
      "computed": {
        "if_h_equals_0.25_required_n_per_group": 588,
        "achieved_power_at_n77_if_h_0.25": 0.3416
      },
      "notes": "The paper does not state a control-arm compliance rate, so '25% relatively greater' is not a Cohen\u2019s h and the power statement cannot be recomputed from stated inputs. Feeding h=0.25 as one reading of '25%' requires n=588/group for 99% power and does not reproduce 77. That attempted mapping is ours, not theirs; the finding is a reporting gap (indeterminate), not an underpowered-versus-stated-parameters accusation."
    },
    {
      "id": "vitamin_c_unit_table1",
      "location": "Table I, Vitamin C row",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "no CLI command applies",
      "quote": "| Vitamin C (as ascorbic acid)                         | 100 \u03bc g                                           |                                                         83 |",
      "inputs": {},
      "reported": {
        "amount": "100 \u03bcg",
        "percent_dv": 83
      },
      "computed": {},
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "Does not change the trial\u2019s outcome statistics; it is a unit error in the supplement-facts table used to describe the intervention."
      },
      "notes": "THERE IS NO ARITHMETIC HERE beyond the incompatibility of the printed unit with the printed %DV. Adjacent rows use \u03bcg correctly for vitamins A, D, folate and B12, and list Vitamin D as '10 \u03bcg (400 IU)' with 67% DV. Vitamin C at 83% DV for pregnant/lactating women is the conventional pairing with 100 mg, not 100 \u03bcg. Load-bearing for the description of what was distributed."
    },
    {
      "id": "cluster_randomization_individual_chi2",
      "location": "Methods, randomization and analysis",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "no CLI command applies",
      "quote": "These flights were randomly assigned to cohorts, which would receive one of two MVI-briefing modalities.",
      "inputs": {},
      "reported": {
        "n_flights": 4,
        "n_cohorts": 2,
        "test": "chi-squared on individual trainees"
      },
      "computed": {},
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 2,
        "explanation": "Ignoring clustering in a 2-cluster-per-arm design anti-conservatively inflates the injury and survey chi-squared tests that carry the paper\u2019s claims."
      },
      "notes": "THERE IS NO ARITHMETIC HERE. The paper later names 'block rather than individual randomization' as a limitation. Analysis used individual-level chi-squared tests (SAS 9.4) with two flights per arm (~40 trainees per flight). Four clusters is too few for a cluster-robust variance; CSF/Table-1 dispersion tools refuse this design and were not run."
    },
    {
      "id": "duplicated_results_clause",
      "location": "Results, compliance paragraph",
      "technique": "not_computational",
      "consistent": false,
      "severity": "indeterminate",
      "reproduction": "no CLI command applies",
      "quote": "a significantly higher proportion within the in-person cohort, a significantly higher proportion within the in-person cohort  reported taking the MVI on most days (or more) (63.01% vs.  37.84%, P = .0023)",
      "inputs": {},
      "notes": "THERE IS NO ARITHMETIC HERE. The clause 'a significantly higher proportion within the in-person cohort' is duplicated in the same sentence. Descriptive language residue, not a numeric defect."
    },
    {
      "id": "most_days_table_vs_prose",
      "location": "Table III 'Took MVI most days' vs Results prose 'most days (or more)'",
      "technique": "not_computational",
      "consistent": false,
      "severity": "indeterminate",
      "reproduction": "no CLI command applies",
      "quote": "reported taking the MVI on most days (or more) (63.01% vs.  37.84%, P = .0023)",
      "inputs": {},
      "notes": "THERE IS NO ARITHMETIC HERE. Table III labels the row 'Took MVI most days' (34.25% and 63.01% beside a separate 'Took MVI daily' row). Results describes those same percentages as 'most days (or more)'. If the three compliance rows were mutually exclusive single-choice options, in-person daily+most+never = 34.25+63.01+8.22 = 105.48% (check_summation_batch suspicious). The nested reading in the prose ('or more') makes 63.01% include daily and removes the >100% problem. P=.0023 matches the nested/row-wise 2\u00d72 of 28/74 vs 46/73, i.e. the printed percentages treated as separate binaries. Label mismatch, not proven over-count."
    },
    {
      "id": "data_availability_state_but_withhold",
      "location": "DATA AVAILABILITY section",
      "technique": "not_computational",
      "consistent": false,
      "severity": "indeterminate",
      "reproduction": "no CLI command applies",
      "quote": "All relevant data are included in manuscript.",
      "inputs": {},
      "notes": "THERE IS NO ARITHMETIC HERE. The statement accompanies only cohort-level percentages and two mean(SD) rows; no participant-level file is provided. Compatible with a summary-only paper, and with Rule 7\u2019s state-but-withhold pattern. Survey analysed n (73\u201374) is not among the included data."
    },
    {
      "id": "statcheck_no_apa",
      "location": "Full PDF text",
      "technique": "statcheck",
      "consistent": true,
      "severity": "indeterminate",
      "reproduction": "metascience statcheck --pdf-path air_force.pdf",
      "quote": "Associations between categorical variables were analyzed using the chi-squared test. Significance was set to \u03b1\u2264 0.05.",
      "inputs": {
        "pdf_path": "air_force.pdf"
      },
      "computed": {
        "stats_found": 0
      },
      "notes": "No APA-form statistic (\u03c7\u00b2 with df and p together) is printed. Recalculation used recalc_chi_squared on reconstructed tables instead. Zero hits is a fact about format, not about the paper."
    },
    {
      "id": "flag_round_n",
      "location": "Results, sample sizes",
      "technique": "flag_round_n",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience flag-round-n --ns 80,79,159,77",
      "quote": "Demographic characteristics of the 159 female trainees (80 in the video-only cohort,  and 79 in the in-person cohort)",
      "inputs": {
        "ns": [
          80,
          79,
          159,
          77
        ]
      },
      "computed": {
        "all_divisible_by_moderate": false
      }
    }
  ],
  "coverage": {
    "stats_found": 72,
    "tools_run": [
      "extract_pdf",
      "extract_xml",
      "statcheck",
      "parse_table",
      "parse_cells_typed",
      "check_table",
      "grim_percentage",
      "grim_sweep",
      "grim_check",
      "grimmer_check",
      "recalc_chi_squared",
      "recalc_independent_t",
      "flag_uninformative_stat",
      "check_effect_plausibility",
      "check_ratio",
      "check_summation_batch",
      "reconstruct_2x2",
      "verify_power_analysis",
      "required_n",
      "multiplicity_report",
      "flag_round_n",
      "detect_duplication",
      "check_statistic_bounds"
    ],
    "tables_checked": [
      "Table I",
      "Table II",
      "Table III"
    ],
    "stats_checked": 58
  },
  "anatomy": {
    "studies": [
      {
        "id": "bmt_mvi_brief",
        "label": "Female BMT trainees, December 2021 squadron, video-only vs in-person MVI briefing",
        "design": "cluster_rct",
        "n": 159,
        "unit_of_analysis": "trainee",
        "clustered": true,
        "preregistered": false,
        "n_per_group": [
          {
            "label": "video-only",
            "n": 80
          },
          {
            "label": "in-person",
            "n": 79
          }
        ],
        "sample_flow": [
          {
            "stage": "enrolled (all female trainees in 4 flights of one squadron)",
            "n": 159
          },
          {
            "stage": "randomized by flight to briefing modality",
            "n": 159
          },
          {
            "stage": "analysed, routinely collected injury and training data",
            "n": 159,
            "reason": "paper states no losses or exclusions of routinely collected and linked data"
          },
          {
            "stage": "analysed, survey briefing/compliance items (implied, not printed)",
            "n": 146,
            "reason": "GRIM-implied unique ns 73 and 74 in video-only and 73 in-person; not printed",
            "inferred": true
          }
        ]
      }
    ],
    "variables": [
      {
        "id": "age",
        "name": "Age, year",
        "measurement_level": "ratio",
        "discreteness": "discrete",
        "family": "continuous",
        "confidence": "medium",
        "units": "years",
        "provenance_quote": "| Age, year     | 21 \u00b1 3                        | 23 \u00b1 5                       |"
      },
      {
        "id": "bmi",
        "name": "BMI",
        "measurement_level": "ratio",
        "discreteness": "continuous",
        "family": "continuous",
        "confidence": "high",
        "units": "kg/m^2",
        "derivation": "other",
        "derived_from": "height (meters) and weight (kilograms) marked BMI calculated using height (meters) and weight (kilograms)."
      },
      {
        "id": "brief_effective",
        "name": "Found brief effective in explaining why MVI prescribed",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "yes",
          "no"
        ],
        "derivation": "percentage",
        "derived_from": "questionnaire item"
      },
      {
        "id": "brief_confident",
        "name": "Confident in understanding why MVI was prescribed",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "yes",
          "no"
        ],
        "derivation": "percentage"
      },
      {
        "id": "mvi_daily",
        "name": "Took MVI daily",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "yes",
          "no"
        ],
        "derivation": "percentage"
      },
      {
        "id": "mvi_most_days",
        "name": "Took MVI most days",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "medium",
        "n_categories": 2,
        "levels": [
          "Took MVI most days",
          "Took MVI most days (or more)"
        ],
        "derivation": "percentage",
        "derived_from": "questionnaire; table and prose labels disagree on nesting with daily"
      },
      {
        "id": "mvi_never",
        "name": "Never took MVI",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "yes",
          "no"
        ],
        "derivation": "percentage"
      },
      {
        "id": "mski",
        "name": "MSKI",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "diagnosed MSKI",
          "no MSKI"
        ],
        "derivation": "percentage",
        "derived_from": "sports medicine MSKI database"
      },
      {
        "id": "bsi",
        "name": "BSI",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "diagnosed bone stress injury",
          "no BSI"
        ],
        "derivation": "percentage"
      },
      {
        "id": "med_hold",
        "name": "Medical hold",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "yes",
          "no"
        ],
        "derivation": "percentage"
      },
      {
        "id": "recycle_admin",
        "name": "Recycle: admin issue",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "yes",
          "no"
        ],
        "derivation": "percentage"
      },
      {
        "id": "recycle_fitness",
        "name": "Recycle: fitness failure",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "yes",
          "no"
        ],
        "derivation": "percentage"
      },
      {
        "id": "cohort",
        "name": "Briefing modality",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "nominal_category",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "video-only",
          "in-person"
        ],
        "derivation": "recoded",
        "derived_from": "flight assignment"
      }
    ],
    "tests": [
      {
        "id": "t_brief_effective",
        "test_type": "chi_squared",
        "location": "Table III, Found brief effective",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_knowledge",
        "outcome_var": "brief_effective",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 146,
        "p_value": 0.31,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "| Found brief effective in explaining why MVI prescribed | 95.89                                        | 98.63                                        | .31                                          |"
      },
      {
        "id": "t_brief_confident",
        "test_type": "chi_squared",
        "location": "Table III, Confident",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_knowledge",
        "outcome_var": "brief_confident",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 146,
        "p_value": 0.007,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "who stated they felt confident in their understanding of why they were prescribed the MVI (100% vs. 90.41%, P = .007)."
      },
      {
        "id": "t_mvi_daily",
        "test_type": "chi_squared",
        "location": "Table III, Took MVI daily",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_compliance",
        "outcome_var": "mvi_daily",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 147,
        "p_value": 0.0063,
        "p_is_threshold": false,
        "appears_in_abstract": true,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "| Took MVI daily                                         | 14.86                                        | 34.25                                        | .0063                                        |"
      },
      {
        "id": "t_mvi_most_days",
        "test_type": "chi_squared",
        "location": "Table III, Took MVI most days",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_compliance",
        "outcome_var": "mvi_most_days",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 147,
        "p_value": 0.0023,
        "p_is_threshold": false,
        "appears_in_abstract": true,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "reported taking the MVI on most days (or more) (63.01% vs.  37.84%, P = .0023)"
      },
      {
        "id": "t_mvi_never",
        "test_type": "chi_squared",
        "location": "Table III, Never took MVI",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_compliance",
        "outcome_var": "mvi_never",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 147,
        "p_value": 0.037,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "a significantly lower proportion reported never taking the MVI (8.22% vs. 20.27%, P = .037)."
      },
      {
        "id": "t_mski",
        "test_type": "chi_squared",
        "location": "Table III, MSKI",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_injury",
        "outcome_var": "mski",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 159,
        "p_value": 0.047,
        "p_is_threshold": false,
        "effect_size": "43% relative risk reduction; 13.5% ARR; NNIPB 7.4",
        "appears_in_abstract": true,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "a significantly smaller proportion of the in-person cohort suffered MSKI (17.72% vs. 31.25%, P = .047)",
        "effect_size_estimated": {
          "value": 2.11,
          "kind": "odds_ratio",
          "computed_from": "reconstructed 25/80 vs 14/79",
          "tool": "recalc_chi_squared",
          "ci_spans_null": false
        }
      },
      {
        "id": "t_bsi",
        "test_type": "chi_squared",
        "location": "Table III, BSI",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_injury",
        "outcome_var": "bsi",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 159,
        "p_value": 0.037,
        "p_is_threshold": false,
        "effect_size": "66% relative risk reduction; 10% ARR; NNIPB 10",
        "appears_in_abstract": true,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "and BSI (5.06% vs.  15%, P = .037) compared to the video-only cohort.",
        "effect_size_estimated": {
          "value": 3.31,
          "kind": "odds_ratio",
          "computed_from": "reconstructed 12/80 vs 4/79",
          "tool": "recalc_chi_squared",
          "ci_spans_null": false
        }
      },
      {
        "id": "t_med_hold",
        "test_type": "chi_squared",
        "location": "Table III, Medical hold",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_training",
        "outcome_var": "med_hold",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 159,
        "p_value": 0.99,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "| Medical hold                                           | 1.27                                         | 1.27                                         | .99                                          |"
      },
      {
        "id": "t_recycle_admin",
        "test_type": "chi_squared",
        "location": "Table III, Recycle: admin issue",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_training",
        "outcome_var": "recycle_admin",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 159,
        "p_value": 0.31,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "| Recycle: admin issue                                   | 0                                            | 1.27                                         | .31                                          |"
      },
      {
        "id": "t_recycle_fitness",
        "test_type": "chi_squared",
        "location": "Table III, Recycle: fitness failure",
        "confidence": "high",
        "study_id": "bmt_mvi_brief",
        "hypothesis_id": "h_training",
        "outcome_var": "recycle_fitness",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 159,
        "p_value": 0.99,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "| Recycle: fitness failure                               | 2.50                                         | 2.53                                         | .99                                          |"
      },
      {
        "id": "t_age",
        "test_type": "independent_t",
        "location": "Table II / Results, age comparison (p not printed)",
        "confidence": "medium",
        "study_id": "bmt_mvi_brief",
        "outcome_var": "age",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 159,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "No significant differences in age or BMI between cohorts were detected.",
        "effect_size_estimated": {
          "value": -0.483,
          "kind": "hedges_g",
          "ci95": [
            -0.801,
            -0.17
          ],
          "computed_from": "means 21 vs 23, SDs 3 vs 5, ns 80 vs 79",
          "tool": "check_effect_plausibility",
          "ci_spans_null": false
        },
        "mde_80": {
          "value": 0.483,
          "kind": "cohens_d",
          "alpha": 0.05,
          "observed_clears_it": true,
          "tool": "required_n"
        }
      },
      {
        "id": "t_bmi",
        "test_type": "independent_t",
        "location": "Table II / Results, BMI comparison (p not printed)",
        "confidence": "medium",
        "study_id": "bmt_mvi_brief",
        "outcome_var": "bmi",
        "predictor_vars": [
          "cohort"
        ],
        "grouping_var": "cohort",
        "n": 159,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "No significant differences in age or BMI between cohorts were detected."
      }
    ],
    "hypotheses": [
      {
        "id": "h_knowledge",
        "statement": "In-person SME briefing improves female BMT trainee knowledge and confidence regarding the MVI relative to video-only.",
        "status": "confirmatory",
        "study_id": "bmt_mvi_brief",
        "appears_in_abstract": true,
        "provenance_quote": "This study aimed to determine whether the addition of an in-person brief of the MVI by subject-matter experts (SMEs) at the time of distribution would improve female BMT trainee knowledge, confidence, and compliance with the MVI",
        "confidence": "high"
      },
      {
        "id": "h_compliance",
        "statement": "In-person SME briefing improves MVI compliance relative to video-only.",
        "status": "confirmatory",
        "study_id": "bmt_mvi_brief",
        "appears_in_abstract": true,
        "provenance_quote": "We estimated a 25% relatively greater daily MVI compliance in trainees receiving the in-person brief compared to those viewing the video alone, which yielded a need for each cohort to have 77 trainees to demonstrate a significant difference.",
        "confidence": "high"
      },
      {
        "id": "h_injury",
        "statement": "Greater MVI compliance from in-person briefing reduces MSKI and BSI incidence.",
        "status": "confirmatory",
        "study_id": "bmt_mvi_brief",
        "appears_in_abstract": true,
        "provenance_quote": "and whether this, in turn, would affect MSKI/BSI incidence and training outcomes.",
        "confidence": "high"
      },
      {
        "id": "h_training",
        "statement": "Briefing modality affects medical hold and recycle/training-delay rates.",
        "status": "confirmatory",
        "study_id": "bmt_mvi_brief",
        "appears_in_abstract": false,
        "provenance_quote": "and whether this, in turn, would affect MSKI/BSI incidence and training outcomes.",
        "confidence": "medium"
      }
    ]
  },
  "paper_title": "Multivitamin Compliance Reduces Injuries of Female Recruits at Air Force Basic Training: A Randomized Controlled Cohort Study",
  "paper_metadata": {
    "authors": "Korey B. Kasper, Meredith Cockerell, Clarissa Escamilla, Richard Gonzalez",
    "journal": "Military Medicine",
    "year": "2024",
    "doi": "10.1093/milmed/usae044",
    "study_design": "cluster-randomized (flights) controlled cohort study of briefing modality among female BMT trainees"
  },
  "unchecked": [
    {
      "location": "Power analysis control-arm compliance rate",
      "reason": "Paper states a 25% relatively greater daily MVI compliance and n=77/group at power 0.99, but never prints the control proportion needed to convert that relative increase into Cohen\u2019s h. verify_power_analysis cannot be completed from stated inputs."
    },
    {
      "location": "Age and BMI hypothesis tests",
      "reason": "Paper claims no significant differences but prints no t, df, or p. Recalculation from 0-decimal age means is uninformative (p-range straddles 0.05)."
    },
    {
      "location": "Null claims (training delays; age/BMI)",
      "reason": "No confidence intervals are printed, so absence_of_evidence cannot bound the largest compatible effect."
    },
    {
      "location": "Publisher XML / HTML",
      "reason": "No JATS XML or publisher HTML was present; tables were taken from extract_pdf (docling) and body.md and agreed."
    },
    {
      "location": "Supplementary data file",
      "reason": "None provided. DATA AVAILABILITY says all relevant data are in the manuscript."
    },
    {
      "location": "Figures",
      "reason": "Paper has no data figures; extract_figures was denied by the tool policy. Nothing unique is carried only in a plot."
    },
    {
      "location": "Table I percent-daily-value arithmetic",
      "reason": "Reference DV amounts are not printed, so check_ratio cannot verify %DV except via the Vitamin C unit incompatibility recorded as not_computational."
    },
    {
      "location": "GRIM R cross-check",
      "reason": "r_grim_ground_truth is held for the editorial stage and was denied on this backend. All grim_percentage impossible cells are flagged as awaiting it."
    },
    {
      "location": "CSF / Table 1 dispersion",
      "reason": "Only two baseline variables, no printed baseline p-values, and allocation was by flight (cluster). CSF/bayesian_table1_dispersion refuse or are uninformative here."
    },
    {
      "location": "Survey item wording and missingness counts",
      "reason": "Questionnaire items and per-item n are not printed; implied ns 73/74 come from GRIM, not from a reported denominator."
    }
  ],
  "figures": [],
  "statistics_register": [
    {
      "source": "abstract",
      "kind": "count",
      "values": {
        "n_control": 80,
        "n_test": 79
      },
      "quote": "The control cohort ( n = 80) was presented with the standard educational video created by BMT-registered dietitians, while the test cohort ( n = 79) was presented the video and then also briefed in-person by a group of subject matter experts.",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "abs_n",
      "location": "Abstract, Materials and Methods"
    },
    {
      "source": "abstract",
      "kind": "percentage",
      "values": {
        "rrr_mski": 43,
        "rrr_bsi": 66
      },
      "quote": "diagnosed with MSKI and bone stress injuries at significantly lower rates (43% and 66% relative risk reductions, respectively).",
      "checkable": {
        "tools": [
          "check_ratio"
        ]
      },
      "id": "abs_rrr",
      "location": "Abstract, Results",
      "duplicate_of": "disc_rrr_mski"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "male_bsi": 13.87,
        "female_bsi": 14.13
      },
      "quote": "13.87% of male trainees and 14.13% of female trainees were clinically diagnosed with BSI at BMT.",
      "checkable": {
        "tools": [],
        "reason": "citation of another paper, not this study\u2019s sample"
      },
      "id": "intro_bsi_lit",
      "location": "Introduction"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 21,
        "SD": 3,
        "n": 80
      },
      "quote": "| Age, year     | 21 \u00b1 3                        | 23 \u00b1 5                       |",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "recalc_independent_t",
          "flag_uninformative_stat",
          "check_effect_plausibility"
        ]
      },
      "id": "t2_age_video",
      "location": "Table II, Age"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 23,
        "SD": 5,
        "n": 79
      },
      "quote": "| Age, year     | 21 \u00b1 3                        | 23 \u00b1 5                       |",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "recalc_independent_t"
        ]
      },
      "id": "t2_age_inperson",
      "location": "Table II, Age"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 24.1,
        "SD": 2.6,
        "n": 80
      },
      "quote": "| BMI           | 24.1 \u00b1 2.6                    | 24.0 \u00b1 2.8                   |",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t2_bmi_video",
      "location": "Table II, BMI"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 24.0,
        "SD": 2.8,
        "n": 79
      },
      "quote": "| BMI           | 24.1 \u00b1 2.6                    | 24.0 \u00b1 2.8                   |",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t2_bmi_inperson",
      "location": "Table II, BMI"
    },
    {
      "source": "table",
      "kind": "count",
      "values": {
        "n": 80
      },
      "quote": "| Total, n      | 80                            | 79                           |",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "t2_n_video",
      "location": "Table II"
    },
    {
      "source": "table",
      "kind": "count",
      "values": {
        "n": 79
      },
      "quote": "| Total, n      | 80                            | 79                           |",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "t2_n_inperson",
      "location": "Table II"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "N": 159
      },
      "quote": "Demographic characteristics of the 159 female trainees (80 in the video-only cohort,  and 79 in the in-person cohort)",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "res_n159",
      "location": "Results, paragraph 1"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "alpha": 0.05,
        "power": 0.99,
        "n_per_group": 77,
        "relative_increase_pct": 25
      },
      "quote": "a power analysis calculation was completed using \u03b1\u2264 0.05 for the significance level, a power of 0.99. We estimated a 25% relatively greater daily MVI compliance in trainees receiving the in-person brief compared to those viewing the video alone, which yielded a need for each cohort to have 77 trainees to demonstrate a significant difference.",
      "checkable": {
        "tools": [
          "verify_power_analysis",
          "required_n"
        ]
      },
      "id": "methods_power",
      "location": "Methods, power analysis"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 95.89
      },
      "quote": "| Found brief effective in explaining why MVI prescribed | 95.89                                        | 98.63                                        | .31                                          |",
      "checkable": {
        "tools": [
          "grim_percentage",
          "grim_sweep"
        ]
      },
      "id": "t3_eff_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 98.63
      },
      "quote": "| Found brief effective in explaining why MVI prescribed | 95.89                                        | 98.63                                        | .31                                          |",
      "checkable": {
        "tools": [
          "grim_percentage",
          "grim_sweep"
        ]
      },
      "id": "t3_eff_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.31
      },
      "quote": "| Found brief effective in explaining why MVI prescribed | 95.89                                        | 98.63                                        | .31                                          |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_eff_p",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 90.41
      },
      "quote": "| Confident in understanding why MVI was prescribed      | 90.41                                        | 100                                          | .007                                         |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_conf_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 100
      },
      "quote": "| Confident in understanding why MVI was prescribed      | 90.41                                        | 100                                          | .007                                         |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_conf_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.007
      },
      "quote": "| Confident in understanding why MVI was prescribed      | 90.41                                        | 100                                          | .007                                         |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_conf_p",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 14.86
      },
      "quote": "| Took MVI daily                                         | 14.86                                        | 34.25                                        | .0063                                        |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_daily_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 34.25
      },
      "quote": "| Took MVI daily                                         | 14.86                                        | 34.25                                        | .0063                                        |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_daily_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.0063
      },
      "quote": "| Took MVI daily                                         | 14.86                                        | 34.25                                        | .0063                                        |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_daily_p",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 37.84
      },
      "quote": "| Took MVI most days                                     | 37.84                                        | 63.01                                        | .0023                                        |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_most_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 63.01
      },
      "quote": "| Took MVI most days                                     | 37.84                                        | 63.01                                        | .0023                                        |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_most_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.0023
      },
      "quote": "| Took MVI most days                                     | 37.84                                        | 63.01                                        | .0023                                        |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_most_p",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 20.27
      },
      "quote": "| Never took MVI                                         | 20.27                                        | 8.22                                         | .037                                         |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_never_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 8.22
      },
      "quote": "| Never took MVI                                         | 20.27                                        | 8.22                                         | .037                                         |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_never_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.037
      },
      "quote": "| Never took MVI                                         | 20.27                                        | 8.22                                         | .037                                         |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_never_p",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 31.25
      },
      "quote": "| MSKI                                                   | 31.25                                        | 17.72                                        | .047                                         |",
      "checkable": {
        "tools": [
          "grim_percentage",
          "reconstruct_2x2",
          "recalc_chi_squared"
        ]
      },
      "id": "t3_mski_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 17.72
      },
      "quote": "| MSKI                                                   | 31.25                                        | 17.72                                        | .047                                         |",
      "checkable": {
        "tools": [
          "grim_percentage",
          "reconstruct_2x2",
          "recalc_chi_squared"
        ]
      },
      "id": "t3_mski_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.047
      },
      "quote": "| MSKI                                                   | 31.25                                        | 17.72                                        | .047                                         |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_mski_p",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 15
      },
      "quote": "| BSI                                                    | 15                                           | 5.06                                         | .037                                         |",
      "checkable": {
        "tools": [
          "grim_percentage",
          "reconstruct_2x2",
          "recalc_chi_squared"
        ]
      },
      "id": "t3_bsi_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 5.06
      },
      "quote": "| BSI                                                    | 15                                           | 5.06                                         | .037                                         |",
      "checkable": {
        "tools": [
          "grim_percentage",
          "reconstruct_2x2"
        ]
      },
      "id": "t3_bsi_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.037
      },
      "quote": "| BSI                                                    | 15                                           | 5.06                                         | .037                                         |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_bsi_p",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 1.27
      },
      "quote": "| Medical hold                                           | 1.27                                         | 1.27                                         | .99                                          |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_hold_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 1.27
      },
      "quote": "| Medical hold                                           | 1.27                                         | 1.27                                         | .99                                          |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_hold_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.99
      },
      "quote": "| Medical hold                                           | 1.27                                         | 1.27                                         | .99                                          |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_hold_p",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 0
      },
      "quote": "| Medical hold: MSKI                                     | 0                                            | 0                                            | -                                            |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_holdmski",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 0
      },
      "quote": "| Recycle: admin issue                                   | 0                                            | 1.27                                         | .31                                          |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_admin_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 1.27
      },
      "quote": "| Recycle: admin issue                                   | 0                                            | 1.27                                         | .31                                          |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_admin_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.31
      },
      "quote": "| Recycle: admin issue                                   | 0                                            | 1.27                                         | .31                                          |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_admin_p",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 2.5
      },
      "quote": "| Recycle: fitness failure                               | 2.50                                         | 2.53                                         | .99                                          |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_fit_v",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "pct": 2.53
      },
      "quote": "| Recycle: fitness failure                               | 2.50                                         | 2.53                                         | .99                                          |",
      "checkable": {
        "tools": [
          "grim_percentage"
        ]
      },
      "id": "t3_fit_i",
      "location": "Table III"
    },
    {
      "source": "table",
      "kind": "p_value",
      "values": {
        "p": 0.99
      },
      "quote": "| Recycle: fitness failure                               | 2.50                                         | 2.53                                         | .99                                          |",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      },
      "id": "t3_fit_p",
      "location": "Table III"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "pct1": 100,
        "pct2": 90.41,
        "p": 0.007
      },
      "quote": "who stated they felt confident in their understanding of why they were prescribed the MVI (100% vs. 90.41%, P = .007).",
      "checkable": {
        "tools": [
          "grim_percentage",
          "recalc_chi_squared"
        ]
      },
      "id": "res_conf",
      "location": "Results, briefing paragraph",
      "duplicate_of": "t3_conf_p"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "pct1": 63.01,
        "pct2": 37.84,
        "p": 0.0023
      },
      "quote": "reported taking the MVI on most days (or more) (63.01% vs.  37.84%, P = .0023)",
      "checkable": {
        "tools": [
          "grim_percentage",
          "recalc_chi_squared"
        ]
      },
      "id": "res_most",
      "location": "Results, compliance paragraph",
      "duplicate_of": "t3_most_p"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "pct1": 8.22,
        "pct2": 20.27,
        "p": 0.037
      },
      "quote": "a significantly lower proportion reported never taking the MVI (8.22% vs. 20.27%, P = .037).",
      "checkable": {
        "tools": [
          "grim_percentage",
          "recalc_chi_squared"
        ]
      },
      "id": "res_never",
      "location": "Results, compliance paragraph",
      "duplicate_of": "t3_never_p"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "pct1": 17.72,
        "pct2": 31.25,
        "p": 0.047
      },
      "quote": "a significantly smaller proportion of the in-person cohort suffered MSKI (17.72% vs. 31.25%, P = .047)",
      "checkable": {
        "tools": [
          "grim_percentage",
          "recalc_chi_squared"
        ]
      },
      "id": "res_mski",
      "location": "Results, injury paragraph",
      "duplicate_of": "t3_mski_p"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "pct1": 5.06,
        "pct2": 15,
        "p": 0.037
      },
      "quote": "and BSI (5.06% vs.  15%, P = .037) compared to the video-only cohort.",
      "checkable": {
        "tools": [
          "grim_percentage",
          "recalc_chi_squared"
        ]
      },
      "id": "res_bsi",
      "location": "Results, injury paragraph",
      "duplicate_of": "t3_bsi_p"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "rrr": 43,
        "arr": 13.5
      },
      "quote": "The relative and absolute risk reductions for diagnosis with all MSKI were 43% and 13.5%,  respectively.",
      "checkable": {
        "tools": [
          "check_ratio",
          "check_summation"
        ]
      },
      "id": "disc_rrr_mski",
      "location": "Discussion"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "nnipb": 7.4
      },
      "quote": "This absolute risk reduction corresponds to a number needed to in-person brief (NNIPB) of 7.4 to avoid one MSKI.",
      "checkable": {
        "tools": [
          "check_ratio"
        ]
      },
      "id": "disc_nnipb_mski",
      "location": "Discussion"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "prevented": 5.4,
        "brief_n": 40
      },
      "quote": "with \u223c 40 female trainees in a briefing,  each in-person brief delivered would be expected to prevent 5.4 MSKI compared to the video-only brief.",
      "checkable": {
        "tools": [
          "check_ratio"
        ]
      },
      "id": "disc_prevent_mski",
      "location": "Discussion"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "rrr": 66,
        "arr": 10
      },
      "quote": "The relative and absolute risk reductions for diagnosis with BSI were 66% and 10%, respectively",
      "checkable": {
        "tools": [
          "check_ratio"
        ]
      },
      "id": "disc_rrr_bsi",
      "location": "Discussion"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "nnipb": 10
      },
      "quote": "this corresponds to  a  NNIPB  of  10.",
      "checkable": {
        "tools": [
          "check_ratio"
        ]
      },
      "id": "disc_nnipb_bsi",
      "location": "Discussion"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "prevented": 4,
        "brief_n": 40
      },
      "quote": "each in-person brief (of  40  female  trainees)  would  be  expected  to  prevent  four BSIs.",
      "checkable": {
        "tools": [
          "check_ratio"
        ]
      },
      "id": "disc_prevent_bsi",
      "location": "Discussion"
    },
    {
      "source": "table",
      "kind": "other",
      "values": {
        "amount_ug": 100,
        "pct_dv": 83
      },
      "quote": "| Vitamin C (as ascorbic acid)                         | 100 \u03bc g                                           |                                                         83 |",
      "checkable": {
        "tools": [],
        "reason": "reference DV not printed; unit incompatibility recorded as not_computational"
      },
      "id": "t1_vitc",
      "location": "Table I, Vitamin C"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "vitamin_d_iu": 400,
        "iron_mg": 27,
        "requirement_mg": 22
      },
      "quote": "Though the vitamin D content (400 IU) is half the dose associated with decreased  stress  fractures  among  navy  recruits  reported  by Lappe et al., 28 the 27 mg of iron approximates the estimated 22 mg daily requirement for females in military training.",
      "checkable": {
        "tools": [],
        "reason": "product facts and a cited estimate, not this sample\u2019s statistics"
      },
      "id": "intro_mvi_contents",
      "location": "Introduction"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "attrition_reduction": 26
      },
      "quote": "deemed the 26% associated reduction in medical attrition as 'operationally adequate to justify continuation' of the program.",
      "checkable": {
        "tools": [],
        "reason": "result cited from Barnes et al., not this study"
      },
      "id": "intro_barnes",
      "location": "Introduction"
    }
  ],
  "second_look": {
    "n_accusatory": 6,
    "n_flagged": 6,
    "by_marker": {
      "quote_not_located": 6
    },
    "items": [
      {
        "id": "table3_survey_denominators_grim_sweep",
        "severity": "suspicious",
        "location": "Table III, survey rows (brief effectiveness and MVI compliance)",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table3_survey_pct_vs_enrolled_n",
        "severity": "suspicious",
        "location": "Table III, Found brief effective / Confident / Took MVI daily / most days / Never rows",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table3_medical_hold_video_127",
        "severity": "impossible",
        "location": "Table III, Medical hold row, video-only column",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table2_age_uninformative",
        "severity": "suspicious",
        "location": "Table II, Age row, and Results sentence claiming no age difference",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "vitamin_c_unit_table1",
        "severity": "suspicious",
        "location": "Table I, Vitamin C row",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "cluster_randomization_individual_chi2",
        "severity": "suspicious",
        "location": "Methods, randomization and analysis",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      }
    ],
    "note": "6 of 6 accusation(s) carry a named weakness in their evidence. Each is listed with what would settle it. This is a worklist, not a verdict: none of these is wrong because it is listed, and a marker you resolve should be recorded in `triage` like any other triage decision."
  }
}
```

Triage these findings (confirm / deprioritize / reinterpret per the rulebook — especially baseline-similarity results), add the contextual reasoning the sweep cannot do, and emit the report JSON.