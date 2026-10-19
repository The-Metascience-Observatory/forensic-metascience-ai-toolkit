Write the editorial forensic review for this paper.

Read the paper body with the Read tool: `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/wound_healing/paper/markdown/body.md`

What the sweep actually ran, which is the DENOMINATOR your verdict sits in:

```json
{
  "checks_passed": 41,
  "of_which_collapsed_by_check_table": 8,
  "checks_refused_indeterminate": 5,
  "checks_flagged": 4,
  "checks_total": 50,
  "by_severity": {
    "suspicious": 4,
    "indeterminate": 5,
    "consistent": 33
  },
  "by_outcome": {
    "flagged": 4,
    "refused": 5,
    "pass": 33
  },
  "rounding_convention": {
    "n_fit_only_under_truncation": 0,
    "n_granularity_checks": 25,
    "note": "Values that fail the round-half convention but are consistent if the reporter TRUNCATES (SPSS's default, and several journal styles). NOT a finding and never counted as one: a single instance is a house style. The RATE is the signal -- this class of anomaly is commoner in papers with more serious problems, so a high proportion is grounds to look harder, not evidence in itself."
  },
  "grace": {
    "n_items": 25,
    "n_reconciled_strictly": 25,
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
    "n_granularity_checks": 25,
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
      "id": "bmi_range_vs_inclusion",
      "location": "Table 2, BMI row vs Patients and methods inclusion criteria",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "not_computational: no metascience command applies",
      "quote": "BMI 23.0\u201345.0 34.5\u00b13.6 34.0",
      "inputs": {
        "table_range": "23.0\u201345.0",
        "inclusion": "BMI>30"
      },
      "reported": {
        "bmi_range_min": 23.0,
        "bmi_range_max": 45.0,
        "inclusion_bmi_gt": 30
      },
      "computed": {
        "contradiction": "Table 2 prints a BMI minimum of 23.0 while Methods states BMI>30 and that the sample contains no women with BMI below 30"
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "The paper's claim that the cohort is obese women with BMI>30 is incompatible with the printed BMI range starting at 23.0."
      },
      "notes": "The Table 2 range 23.0\u201345.0 is confirmed on the PDF page image, not an extraction artifact. Methods says 'with BMI>30 (so, we do not have a group of women with BMI below 30' and excludes 'women with BMI<30'. A contiguous Methods span and the Table 2 BMI row cannot both be true. Innocent readings include a mistyped lower bound (e.g. 33.0 printed as 23.0) or unreported protocol deviations. This is a contradiction between two printed statements, not an arithmetic impossibility."
    },
    {
      "id": "prose_counts_reported_as_percentages",
      "location": "Results Description and Discussion, whole-cohort wound-complication rates",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "not_computational: no metascience command applies",
      "quote": "wound gapping occurred in 12% of cases, wound seroma occurred in 10% of cases, wound erythema occurred in 18% of cases, and wound infection occurred in 20% of cases in the whole cohort of cases.",
      "inputs": {
        "prose_rates_percent": [
          12,
          10,
          18,
          20
        ],
        "table1_counts": [
          12,
          10,
          18,
          20
        ],
        "table1_percents": [
          3,
          2.5,
          4.5,
          5
        ],
        "n": 397
      },
      "reported": {
        "prose_gapping_pct": 12,
        "prose_seroma_pct": 10,
        "prose_erythema_pct": 18,
        "prose_infection_pct": 20,
        "table_gapping": "12 (3)",
        "table_seroma": "10 (2.5)",
        "table_erythema": "18 (4.5)",
        "table_infection": "20 (5)"
      },
      "computed": {
        "table1_rates_from_counts_over_397": "12/397 prints as 3%, 10/397 as 2.5%, 18/397 as 4.5%, 20/397 as 5% (check_count_percent consistent on those cells)"
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 4,
        "explanation": "Results and Discussion state whole-cohort complication rates fourfold higher than Table 1, by reprinting the event counts as percentages."
      },
      "notes": "Table 1 Yes cells are 12 (3), 10 (2.5), 18 (4.5), 20 (5) of n=397; check_count_percent matches those percentages to those counts. The same four integers reappear in Results and again in Discussion as 12%, 10%, 18%, and 20% 'of cases in the whole cohort'. The Abstract does not repeat the inflated percentages; it reports the Table 4 p-values and odds ratios. Two different printed renderings of the same four numerators."
    },
    {
      "id": "interrupted_lost_followup_two_vs_one",
      "location": "Table 1, Interrupted row vs Figure 1 and Methods",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "not_computational: no metascience command applies",
      "quote": "Interrupted 199(50.1)afterlostfollowupof2women",
      "inputs": {
        "table1_interrupted_lost": 2,
        "methods_interrupted_lost": 1,
        "analysed_interrupted": 199
      },
      "reported": {
        "table1_text": "199 (50.1) after lost follow up of 2 women",
        "consort_interrupted_lost": 1
      },
      "computed": {
        "200_minus_1": 199,
        "200_minus_2": 198
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "The Interrupted arm's lost-to-follow-up count is printed as 2 in Table 1 and as 1 in the CONSORT diagram and Methods; 199 analysed matches 200 minus 1, not minus 2."
      },
      "notes": "Methods: 'Two cases from the continuous group and one case from the interrupted group did not come for the follow up'. Figure 1: Interrupted lost N=1, analysed N=199; Continuous lost N=2, analysed N=198. Table 1 prints the same clause 'after lost follow up of 2 women' on BOTH the Continuous 198 (49.9) and Interrupted 199 (50.1) rows. The Continuous row matches the CONSORT 2; the Interrupted row is a copy of that clause onto a count that implies 1 loss."
    },
    {
      "id": "table3_subcut_depth_p",
      "location": "Table 3, Subcutaneous tissue depth row",
      "technique": "recalc_independent_t",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience ttest --mean1 4.5 --sd1 1.0 --n1 198 --mean2 4.4 --sd2 0.9 --n2 199 --reported-p 0.127 --decimals-p 3 --decimals-mean 1 --decimals-sd 0",
      "quote": "Subcutaneoustissuedepth(cm) 4.5\u00b11 4.4\u00b10.9.127",
      "inputs": {
        "mean1": 4.5,
        "sd1": 1.0,
        "n1": 198,
        "mean2": 4.4,
        "sd2": 0.9,
        "n2": 199,
        "reported_p": 0.127,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 0
      },
      "reported": {
        "mean_continuous": 4.5,
        "sd_continuous": 1,
        "mean_interrupted": 4.4,
        "sd_interrupted": 0.9,
        "p": 0.127
      },
      "computed": {
        "welch_t": 1.0471,
        "welch_p_two": 0.295708,
        "student_t": 1.0474,
        "student_p_two": 0.295573,
        "p_matches": false
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "Both the printed p=.127 and the recalculated p\u2248.296 are non-significant; the baseline 'no difference' claim is unchanged."
      },
      "notes": "Tool verdict suspicious: reported p=.127 fits neither Welch nor Student t on the printed means/SDs/ns, including after widening SD precision to 0 decimals because Continuous is printed 4.5\u00b11. The paper never names the test (no statistical-methods paragraph), so a rank-sum test remains an unruled-out innocent reading. One-tailed t p\u2248.148 still does not match .127. Re-run with decimals_sd=0 still returned p_matches=false."
    },
    {
      "id": "table4_gapping_or_ci_vs_p",
      "location": "Table 4, Wound gapping",
      "technique": "check_estimate_ci",
      "consistent": false,
      "severity": "indeterminate",
      "reproduction": "metascience check-ci --estimate 5.239 --ci-low 1.133 --ci-high 24.227 --measure OR --reported-p 0.019 --decimals 3",
      "quote": "Wound gapping 10 (5.1) 2 (1) .019 5.239 1.133\u201324.227",
      "inputs": {
        "estimate": 5.239,
        "ci_low": 1.133,
        "ci_high": 24.227,
        "measure": "OR",
        "reported_p": 0.019,
        "decimals": 3
      },
      "reported": {
        "or": 5.239,
        "ci": "1.133\u201324.227",
        "p": 0.019
      },
      "computed": {
        "recovered_p_from_wald_ci": 0.034,
        "implied_centre": 5.239,
        "ci_excludes_null": true
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "Chi-square p from the cell counts is .019 as printed; the Wald p implied by the CI is .034; both remain below .05."
      },
      "notes": "Tool severity was suspicious (Wald p from the CI is 0.0340, reported p=0.019). Downgraded: recalc_chi_squared on [[10,188],[2,197]] gives Pearson p=0.01857 matching .019, and fisher_odds_ratio=5.23936 matching OR=5.239. The paper never states that p came from the CI. Standard SPSS output places a Pearson/Fisher p beside a Woolf/Wald OR interval; those two p's need not agree. Tool quote: 'this recovery inverts a WALD interval, so if the paper used a bootstrap, exact, profile-likelihood or Fieller interval the two numbers are not comparable'."
    },
    {
      "id": "table4_seroma_or_ci_vs_p",
      "location": "Table 4, Wound seroma",
      "technique": "check_estimate_ci",
      "consistent": false,
      "severity": "indeterminate",
      "reproduction": "metascience check-ci --estimate 9.429 --ci-low 1.183 --ci-high 75.138 --measure OR --reported-p 0.011 --decimals 3",
      "quote": "Wound seroma 9 (4.5) 1 (0.5) .011 9.429 1.183\u201375.138",
      "inputs": {
        "estimate": 9.429,
        "ci_low": 1.183,
        "ci_high": 75.138,
        "measure": "OR",
        "reported_p": 0.011,
        "decimals": 3
      },
      "reported": {
        "or": 9.429,
        "ci": "1.183\u201375.138",
        "p": 0.011
      },
      "computed": {
        "recovered_p_from_wald_ci": 0.0341,
        "fisher_or_from_chi2_tool": 9.42857,
        "pearson_p": 0.01016
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "Printed p=.011 matches Pearson/Fisher from the 2x2; Wald p from the CI is .034; both remain below .05."
      },
      "notes": "Same mixed-method pattern as gapping. Tool suspicious on Wald-p vs printed p; downgraded because chi-square/Fisher from [[9,189],[1,198]] reproduces p=.011 and OR=9.429. Sparse cell (1 event in the interrupted arm) makes the Wald interval especially wide."
    },
    {
      "id": "table4_erythema_or_ci_vs_p",
      "location": "Table 4, Wound erythema",
      "technique": "check_estimate_ci",
      "consistent": false,
      "severity": "indeterminate",
      "reproduction": "metascience check-ci --estimate 3.709 --ci-low 1.199 --ci-high 11.475 --measure OR --reported-p 0.015 --decimals 3",
      "quote": "Wound erythema 14 (7.1) 4 (2) .015 3.709 1.199\u201311.475",
      "inputs": {
        "estimate": 3.709,
        "ci_low": 1.199,
        "ci_high": 11.475,
        "measure": "OR",
        "reported_p": 0.015,
        "decimals": 3
      },
      "reported": {
        "or": 3.709,
        "ci": "1.199\u201311.475",
        "p": 0.015
      },
      "computed": {
        "recovered_p_from_wald_ci": 0.0229,
        "pearson_p": 0.01538,
        "fisher_or": 3.70924
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 1,
        "explanation": "Printed p=.015 matches Pearson chi-square; Wald p from the CI is .023; both remain below .05."
      },
      "notes": "Same mixed-method pattern. Tool suspicious; downgraded because [[14,184],[4,195]] Pearson p=0.01538 matches .015 and Fisher OR=3.709."
    },
    {
      "id": "table4_infection_or_ci",
      "location": "Table 4, Wound Infection",
      "technique": "check_estimate_ci",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-ci --estimate 6.136 --ci-low 1.769 --ci-high 21.287 --measure OR --reported-p 0.001 --decimals 3",
      "quote": "Wound Infection 17 (8.6) 3 (1.5) .001 6.136 1.769\u201321.287",
      "inputs": {
        "estimate": 6.136,
        "ci_low": 1.769,
        "ci_high": 21.287,
        "measure": "OR",
        "reported_p": 0.001,
        "decimals": 3
      },
      "reported": {
        "or": 6.136,
        "ci": "1.769\u201321.287",
        "p": 0.001
      },
      "computed": {
        "recovered_p": 0.00425,
        "inferred_confidence_level": 0.99,
        "ci_excludes_null": true
      },
      "notes": "Tool: estimate, CI and p mutually consistent, with a note that the interval behaves like a 99% CI rather than 95%. Pearson chi-square p=0.00126 from [[17,181],[3,196]] matches printed p=.001; Fisher OR=6.136."
    },
    {
      "id": "consort_and_table_sums",
      "location": "Figure 1 and Tables 1, 4, 5",
      "technique": "check_summation_batch",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience summation-batch",
      "quote": "Description (n=397) after exclusion of 3 cases",
      "inputs": {
        "n_rows": 19
      },
      "reported": {
        "assessed": 411,
        "excluded": 11,
        "randomized": 400,
        "arms": [
          200,
          200
        ],
        "analysed": [
          199,
          198
        ]
      },
      "computed": {
        "n_evaluated": 19,
        "n_inconsistent": 0
      },
      "notes": "All 19 evaluated sums reconcile: 11+400=411; 200+200=400; 1+199=200; 2+198=200; 199+198=397; Table 1 Yes+No rows; Table 4 arm counts vs Table 1 totals; Table 5 33+9=42, 165+190=355, 33+165=198, 9+190=199."
    },
    {
      "id": "table1_continuous_count_percent",
      "location": "Table 1, Continuous row",
      "technique": "check_count_percent",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-count-percent --count 198 --percentage 49.9 --n 397 --decimals 1",
      "quote": "Continuous 198 (49.9) after lost follow up of 2 women",
      "inputs": {
        "count": 198,
        "percentage": 49.9,
        "n": 397,
        "decimals": 1
      },
      "reported": {
        "count": 198,
        "percent": 49.9
      },
      "computed": {
        "computed_percentage": 49.874
      },
      "notes": "198/397=49.87% matches 49.9. Companion Interrupted 199 (50.1), gapping 12 (3), seroma 10 (2.5), erythema 18 (4.5), infection 20 (5), any-complication 42 (10.6) and the matching No rows were also run and all matched n=397."
    },
    {
      "id": "table4_gapping_count_percent",
      "location": "Table 4, Wound gapping",
      "technique": "check_count_percent",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-count-percent --count 10 --percentage 5.1 --n 198 --decimals 1",
      "quote": "Wound gapping 10 (5.1) 2 (1) .019 5.239 1.133\u201324.227",
      "inputs": {
        "count": 10,
        "percentage": 5.1,
        "n": 198,
        "decimals": 1
      },
      "reported": {
        "count": 10,
        "percent": 5.1,
        "n": 198
      },
      "computed": {
        "computed_percentage": 5.0505
      },
      "notes": "10/198=5.05% matches 5.1. Interrupted 2 (1) of 199, seroma 9 (4.5) and 1 (0.5), erythema 14 (7.1) and 4 (2), infection 17 (8.6) and 3 (1.5), and Table 5 suture-type 33 (78.6), 165 (46.5), 9 (21.4), 190 (53.5) were also consistent against their column ns."
    },
    {
      "id": "table4_gapping_chi2",
      "location": "Table 4, Wound gapping",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience chi2 --observed '[[10, 188], [2, 197]]' --reported-p 0.019 --decimals-p 3",
      "quote": "Wound gapping 10 (5.1) 2 (1) .019 5.239 1.133\u201324.227",
      "inputs": {
        "observed": [
          [
            10,
            188
          ],
          [
            2,
            197
          ]
        ],
        "reported_p": 0.019,
        "decimals_p": 3
      },
      "reported": {
        "p": 0.019,
        "or": 5.239
      },
      "computed": {
        "pearson_chi2": 5.5412,
        "pearson_p": 0.01857,
        "fisher_p": 0.02039,
        "fisher_or": 5.23936,
        "p_matches": true
      },
      "notes": "Printed p=.019 matches Pearson chi-square (and is within Fisher's exact). Printed OR matches the 2x2 cross-product."
    },
    {
      "id": "table4_seroma_chi2",
      "location": "Table 4, Wound seroma",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience chi2 --observed '[[9, 189], [1, 198]]' --reported-p 0.011 --decimals-p 3",
      "quote": "Wound seroma 9 (4.5) 1 (0.5) .011 9.429 1.183\u201375.138",
      "inputs": {
        "observed": [
          [
            9,
            189
          ],
          [
            1,
            198
          ]
        ],
        "reported_p": 0.011,
        "decimals_p": 3
      },
      "reported": {
        "p": 0.011,
        "or": 9.429
      },
      "computed": {
        "pearson_p": 0.01016,
        "fisher_p": 0.01066,
        "fisher_or": 9.42857,
        "p_matches": true
      },
      "notes": "Expected cell in the interrupted-yes corner is 5.01 with observed 1; Pearson still matches printed p=.011. Yates p=0.024 would not match."
    },
    {
      "id": "table4_erythema_chi2",
      "location": "Table 4, Wound erythema",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience chi2 --observed '[[14, 184], [4, 195]]' --reported-p 0.015 --decimals-p 3",
      "quote": "Wound erythema 14 (7.1) 4 (2) .015 3.709 1.199\u201311.475",
      "inputs": {
        "observed": [
          [
            14,
            184
          ],
          [
            4,
            195
          ]
        ],
        "reported_p": 0.015,
        "decimals_p": 3
      },
      "reported": {
        "p": 0.015,
        "or": 3.709
      },
      "computed": {
        "pearson_p": 0.01538,
        "fisher_or": 3.70924,
        "p_matches": true
      }
    },
    {
      "id": "table4_infection_chi2",
      "location": "Table 4, Wound Infection",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience chi2 --observed '[[17, 181], [3, 196]]' --reported-p 0.001 --decimals-p 3",
      "quote": "Wound Infection 17 (8.6) 3 (1.5) .001 6.136 1.769\u201321.287",
      "inputs": {
        "observed": [
          [
            17,
            181
          ],
          [
            3,
            196
          ]
        ],
        "reported_p": 0.001,
        "decimals_p": 3
      },
      "reported": {
        "p": 0.001,
        "or": 6.136
      },
      "computed": {
        "pearson_p": 0.001264,
        "fisher_p": 0.00112,
        "fisher_or": 6.13628,
        "p_matches": true
      }
    },
    {
      "id": "table5_suture_type_chi2",
      "location": "Table 5, Suture type",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience chi2 --observed '[[33, 165], [9, 190]]' --reported-p 0.001 --decimals-p 3",
      "quote": "Continuous 33 (78.6) 165 (46.5) <.001",
      "inputs": {
        "observed": [
          [
            33,
            165
          ],
          [
            9,
            190
          ]
        ],
        "reported_p": 0.001,
        "decimals_p": 3
      },
      "reported": {
        "p_threshold": "<.001"
      },
      "computed": {
        "pearson_p": 8.37e-05,
        "fisher_or_crude": 4.222,
        "p_matches": true
      },
      "notes": "Crude OR from this 2x2 is 4.22; Table 6 adjusted OR for Continuous vs Interrupted is 7.743. Different because Table 6 is multivariable."
    },
    {
      "id": "table3_age_t",
      "location": "Table 3, Age",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 30.2 --sd1 3.2 --n1 198 --mean2 30.4 --sd2 3.4 --n2 199 --reported-p 0.444 --decimals-p 3 --decimals-mean 1 --decimals-sd 1",
      "quote": "Age (years) 30.2\u00b13.2 30.4\u00b13.4.444",
      "inputs": {
        "mean1": 30.2,
        "sd1": 3.2,
        "n1": 198,
        "mean2": 30.4,
        "sd2": 3.4,
        "n2": 199,
        "reported_p": 0.444,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "p": 0.444
      },
      "computed": {
        "welch_p": 0.54649,
        "p_matches": true
      },
      "notes": "Point Welch p from the rounded means is 0.546; the tool still matches .444 inside the rounding interval of 1-decimal means/SDs."
    },
    {
      "id": "table3_bmi_t",
      "location": "Table 3, BMI",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 34.8 --sd1 3.9 --n1 198 --mean2 34.2 --sd2 3.3 --n2 199 --reported-p 0.101 --decimals-p 3 --decimals-mean 1 --decimals-sd 1",
      "quote": "BMI 34.8\u00b13.9 34.2\u00b13.3.101",
      "inputs": {
        "mean1": 34.8,
        "sd1": 3.9,
        "n1": 198,
        "mean2": 34.2,
        "sd2": 3.3,
        "n2": 199,
        "reported_p": 0.101,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "p": 0.101
      },
      "computed": {
        "welch_p": 0.09888,
        "p_matches": true
      }
    },
    {
      "id": "table3_ga_t",
      "location": "Table 3, Gestational age",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 37.6 --sd1 1.1 --n1 198 --mean2 37.8 --sd2 1.0 --n2 199 --reported-p 0.114 --decimals-p 3 --decimals-mean 1 --decimals-sd 1",
      "quote": "GestationalageattimeofCS 37.6\u00b11.1 37.8\u00b11.114",
      "inputs": {
        "mean1": 37.6,
        "sd1": 1.1,
        "n1": 198,
        "mean2": 37.8,
        "sd2": 1.0,
        "n2": 199,
        "reported_p": 0.114,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "p": 0.114
      },
      "computed": {
        "welch_p": 0.0588,
        "p_matches": true
      },
      "notes": "Interrupted SD is printed as 1 (0 decimals) on the PDF. Tool matched .114 via the rounding interval of the printed inputs. PDF image confirms 37.8\u00b11, not 1.1."
    },
    {
      "id": "table3_sutures_t",
      "location": "Table 3, No. of subcutaneous sutures",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 6.3 --sd1 3 --n1 198 --mean2 6.3 --sd2 2.8 --n2 199 --reported-p 0.791 --decimals-p 3 --decimals-mean 1 --decimals-sd 1",
      "quote": "No.ofsubcutaneoussutures 6.3\u00b13 6.3\u00b12.8.791",
      "inputs": {
        "mean1": 6.3,
        "sd1": 3.0,
        "n1": 198,
        "mean2": 6.3,
        "sd2": 2.8,
        "n2": 199,
        "reported_p": 0.791,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "p": 0.791
      },
      "computed": {
        "welch_p_at_printed_means": 1.0,
        "p_matches": true
      },
      "notes": "Printed means are identical so t=0 at the rounded values; tool matches p=.791 inside 1-decimal rounding of 6.3\u00b13."
    },
    {
      "id": "table3_optime_t",
      "location": "Table 3, Operative time",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 40.1 --sd1 9.2 --n1 198 --mean2 45.5 --sd2 10.8 --n2 199 --reported-p 0.001 --decimals-p 3 --decimals-mean 1 --decimals-sd 1",
      "quote": "Operativetime(min) 40.1\u00b19.2 45.5\u00b110.8 <.001",
      "inputs": {
        "mean1": 40.1,
        "sd1": 9.2,
        "n1": 198,
        "mean2": 45.5,
        "sd2": 10.8,
        "n2": 199,
        "reported_p": 0.001,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "p": "<.001"
      },
      "computed": {
        "welch_p": 1.41e-07,
        "p_matches": true
      }
    },
    {
      "id": "table3_ebl_t",
      "location": "Table 3, Estimated blood loss",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 644.4 --sd1 164.2 --n1 198 --mean2 673.1 --sd2 165.4 --n2 199 --reported-p 0.084 --decimals-p 3 --decimals-mean 1 --decimals-sd 1",
      "quote": "Estimatedbloodloss(cc) 644.4\u00b1164.2 673.1\u00b1165.4.084",
      "inputs": {
        "mean1": 644.4,
        "sd1": 164.2,
        "n1": 198,
        "mean2": 673.1,
        "sd2": 165.4,
        "n2": 199,
        "reported_p": 0.084,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "p": 0.084
      },
      "computed": {
        "welch_p": 0.08353,
        "p_matches": true
      }
    },
    {
      "id": "table5_bmi_t",
      "location": "Table 5, BMI",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 37.8 --sd1 3.9 --n1 42 --mean2 34.1 --sd2 3.4 --n2 355 --reported-p 0.001 --decimals-p 3 --decimals-mean 1 --decimals-sd 1",
      "quote": "BMI 37.8\u00b13.9 34.1\u00b13.4 <.001",
      "inputs": {
        "mean1": 37.8,
        "sd1": 3.9,
        "n1": 42,
        "mean2": 34.1,
        "sd2": 3.4,
        "n2": 355,
        "reported_p": 0.001,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "p": "<.001"
      },
      "computed": {
        "welch_p": 3.54e-07,
        "p_matches": true
      }
    },
    {
      "id": "table5_sutures_t",
      "location": "Table 5, No. of sutures",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 5.1 --sd1 2.4 --n1 42 --mean2 6.4 --sd2 2.9 --n2 355 --reported-p 0.005 --decimals-p 3 --decimals-mean 1 --decimals-sd 1",
      "quote": "No.ofsuturessubcutaneous 5.1\u00b12.4 6.4\u00b12.9.005",
      "inputs": {
        "mean1": 5.1,
        "sd1": 2.4,
        "n1": 42,
        "mean2": 6.4,
        "sd2": 2.9,
        "n2": 355,
        "reported_p": 0.005,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "p": 0.005
      },
      "computed": {
        "student_p": 0.00547,
        "welch_p": 0.002,
        "p_matches": true
      },
      "notes": "Printed p=.005 matches Student's t (p=.00547) more closely than Welch (p=.00200)."
    },
    {
      "id": "table5_ga_t",
      "location": "Table 5, Gestational age",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 38 --sd1 1 --n1 42 --mean2 37.7 --sd2 1.1 --n2 355 --reported-p 0.077 --decimals-p 3 --decimals-mean 1 --decimals-sd 1",
      "quote": "GestationalageattimeofCS 38\u00b11 37.7\u00b11.1.077",
      "inputs": {
        "mean1": 38.0,
        "sd1": 1.0,
        "n1": 42,
        "mean2": 37.7,
        "sd2": 1.1,
        "n2": 355,
        "reported_p": 0.077,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 1
      },
      "reported": {
        "p": 0.077
      },
      "computed": {
        "welch_p": 0.07461,
        "p_matches": true
      }
    },
    {
      "id": "table5_ebl_t",
      "location": "Table 5, Estimated blood loss",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 754.8 --sd1 179 --n1 42 --mean2 647.5 --sd2 160 --n2 355 --reported-p 0.001 --decimals-p 3 --decimals-mean 1 --decimals-sd 0",
      "quote": "Estimatedbloodloss(cc) 754.8\u00b1179 647.5\u00b1160 <.001",
      "inputs": {
        "mean1": 754.8,
        "sd1": 179,
        "n1": 42,
        "mean2": 647.5,
        "sd2": 160,
        "n2": 355,
        "reported_p": 0.001,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 0
      },
      "reported": {
        "p": "<.001"
      },
      "computed": {
        "welch_p": 0.000523,
        "p_matches": true
      }
    },
    {
      "id": "table5_depth_t",
      "location": "Table 5, Subcutaneous tissue depth",
      "technique": "recalc_independent_t",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience ttest --mean1 5 --sd1 1 --n1 42 --mean2 4.4 --sd2 1 --n2 355 --reported-p 0.001 --decimals-p 3 --decimals-mean 1 --decimals-sd 0",
      "quote": "Subcutaneoustissuedepth(cm) 5\u00b11 4.4\u00b11 <.001",
      "inputs": {
        "mean1": 5.0,
        "sd1": 1.0,
        "n1": 42,
        "mean2": 4.4,
        "sd2": 1.0,
        "n2": 355,
        "reported_p": 0.001,
        "decimals_p": 3,
        "decimals_mean": 1,
        "decimals_sd": 0
      },
      "reported": {
        "p": "<.001"
      },
      "computed": {
        "welch_p": 0.000566,
        "p_matches": true
      }
    },
    {
      "id": "table6_bmi_or_ci",
      "location": "Table 6, BMI",
      "technique": "check_estimate_ci",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-ci --estimate 1.333 --ci-low 1.188 --ci-high 1.494 --measure OR --reported-p 0.001 --reported-p-operator '<' --decimals 3",
      "quote": "BMI 1.333 1.188\u20131.494 <.001",
      "inputs": {
        "estimate": 1.333,
        "ci_low": 1.188,
        "ci_high": 1.494,
        "measure": "OR",
        "reported_p": 0.001,
        "reported_p_operator": "<",
        "decimals": 3
      },
      "reported": {
        "or": 1.333,
        "ci": "1.188\u20131.494",
        "p": "<.001"
      },
      "computed": {
        "recovered_p": 8.83e-07,
        "ci_excludes_null": true
      },
      "notes": "All eight Table 6 rows were run with measure=OR. Age, gestational age, sutures, operative time, estimated blood loss, subcutaneous depth, and Continuous vs Interrupted were also consistent. Age CI was noted as behaving like a 90% interval but still passed."
    },
    {
      "id": "table6_suture_or_ci",
      "location": "Table 6, Continuous VS Interrupted Sutures",
      "technique": "check_estimate_ci",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-ci --estimate 7.743 --ci-low 3.030 --ci-high 19.788 --measure OR --reported-p 0.001 --reported-p-operator '<' --decimals 3",
      "quote": "Continuous VS Interrupted Sutures 7.743 3.030\u201319.788 <.001",
      "inputs": {
        "estimate": 7.743,
        "ci_low": 3.03,
        "ci_high": 19.788,
        "measure": "OR",
        "reported_p": 0.001,
        "reported_p_operator": "<",
        "decimals": 3
      },
      "reported": {
        "or": 7.743,
        "ci": "3.030\u201319.788",
        "p": "<.001"
      },
      "computed": {
        "recovered_p": 1.91e-05,
        "ci_excludes_null": true
      }
    },
    {
      "id": "table2_age_sd_range",
      "location": "Table 2, Age",
      "technique": "check_sd_range",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience sd-range --sd 3.3 --min-val 25 --max-val 35 --n 397 --decimals-sd 1 --bound-source stated",
      "quote": "Age (years) 25.0\u201335.0 30.3\u00b13.3 30.0",
      "inputs": {
        "sd": 3.3,
        "min_val": 25,
        "max_val": 35,
        "n": 397,
        "decimals_sd": 1,
        "bound_source": "stated"
      },
      "reported": {
        "sd": 3.3,
        "range": "25.0\u201335.0"
      },
      "computed": {
        "max_possible_sd": 5.006,
        "sd_as_fraction_of_max": 0.659,
        "is_plausible": true
      },
      "notes": "BMI, GA, sutures, operative time, blood loss, and subcutaneous depth Table 2 SDs were also within their printed ranges."
    },
    {
      "id": "table2_sutures_grimmer",
      "location": "Table 2, No. of sutures subcutaneous",
      "technique": "grimmer_check",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience grimmer --mean 6.3 --sd 2.9 --n 397 --decimals 1 --decimals-sd 1 --data-type count",
      "quote": "No. of sutures subcutaneous 3.0\u201313.0 6.3\u00b12.9 5.0",
      "inputs": {
        "mean": 6.3,
        "sd": 2.9,
        "n": 397,
        "decimals": 1,
        "decimals_sd": 1,
        "data_type": "count",
        "scale_min": 3,
        "scale_max": 13,
        "discreteness_source": "logically_necessary"
      },
      "reported": {
        "mean": 6.3,
        "sd": 2.9,
        "n": 397
      },
      "computed": {
        "found_valid_combination": true
      },
      "notes": "Sutures were counted (integer). GRIM itself has no discriminating power at n=397 with 1 decimal. Table 5 Yes-arm mean 5.1 SD 2.4 n=42 also GRIMMER-consistent. check_table on Table 2 ran 9 checks: 8 consistent (SD/SE, GRIMMER, SPRITE) and 1 indeterminate GRIM (no power)."
    },
    {
      "id": "table2_check_table",
      "location": "Table 2",
      "technique": "check_sd_or_se",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-table",
      "quote": "Table 2. Demonestrates analysis of the demographic data and operative parameters.",
      "inputs": {
        "n_checks_run": 9
      },
      "reported": {
        "n_mean_sd_cells": 7
      },
      "computed": {
        "n_consistent": 8,
        "n_indeterminate": 1
      },
      "notes": "Dispatcher: 8 consistent (check_sd_or_se on the six continuous rows plus GRIMMER and SPRITE on suture counts) and 1 indeterminate GRIM (no power at n=397, 1 dp)."
    },
    {
      "id": "table3_csf_baselines",
      "location": "Table 3, baseline p-values",
      "technique": "csf_test",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience csf --p-values 0.444,0.101,0.114,0.127 --method stouffer --design parallel_rct",
      "quote": "Age (years) 30.2\u00b13.2 30.4\u00b13.4.444",
      "inputs": {
        "p_values": [
          0.444,
          0.101,
          0.114,
          0.127
        ],
        "method": "stouffer",
        "design": "parallel_rct"
      },
      "reported": {
        "p_age": 0.444,
        "p_bmi": 0.101,
        "p_ga": 0.114,
        "p_depth": 0.127
      },
      "computed": {
        "similarity_p": 0.883,
        "mean_p": 0.1965,
        "direction": "normal"
      },
      "notes": "Used the four pre-randomisation characteristics (age, BMI, GA, subcut depth). Operative time, blood loss and suture count are intra-operative and were excluded. similarity_p=0.883 is not excess similarity. Paper is a three-hospital individually randomised trial; design passed as parallel_rct as stated ('prospective randomized study', allocation 1:1)."
    },
    {
      "id": "table3_bayesian_dispersion",
      "location": "Table 3, baseline rows",
      "technique": "bayesian_table1_dispersion",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience table1-dispersion",
      "quote": "Table 3. Shows a comparison between continuous and interrupted techniques as regard operative parameters and demographic data.",
      "inputs": {
        "design": "parallel_rct",
        "n_rows": 4
      },
      "reported": {
        "n_baseline_rows": 4
      },
      "computed": {
        "tau_hat": 0.72,
        "tau_ci": [
          0.08,
          1.45
        ]
      },
      "notes": "\u03c4\u0302=0.72 (CI includes 1) does not indicate under-dispersion. Internal p-values from the means/SDs/ns are the t-test p-values, not the printed ones; depth's recomputed p=0.296 enters this omnibus rather than the printed .127."
    },
    {
      "id": "tables_duplication",
      "location": "Tables 2, 3 and 5",
      "technique": "detect_duplication",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience duplication-detect",
      "quote": "Age (years) 25.0\u201335.0 30.3\u00b13.3 30.0",
      "inputs": {
        "n_blocks": 5,
        "n_comparisons": 490
      },
      "reported": {
        "n_mean_sd_blocks": 5
      },
      "computed": {
        "max_identical_pairs": 0
      },
      "notes": "GA 37.7\u00b11.1 and depth 4.4\u00b11.0 recur between Table 2 overall and Table 5 No (n=355 of 397); flagged as same-sample and round-value, severity consistent. Not independent samples."
    },
    {
      "id": "round_n",
      "location": "Figure 1 and Methods",
      "technique": "flag_round_n",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience flag-round-n --ns 411,400,200,200,199,198,397",
      "quote": "The two groups were randomly selected, 200 in each group.",
      "inputs": {
        "ns": [
          411,
          400,
          200,
          200,
          199,
          198,
          397
        ]
      },
      "reported": {
        "randomized_per_arm": 200
      },
      "computed": {
        "all_divisible_by_moderate": false
      },
      "notes": "Designed 200 per arm is an ordinary recruitment target; analysed 198/199 are not round."
    },
    {
      "id": "table4_multiplicity",
      "location": "Table 4, four wound-complication outcomes",
      "technique": "multiplicity_report",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience multiplicity",
      "quote": "showing statistical significant differences in all four wound complications presented with p values=.019, .011, .015, and .001",
      "inputs": {
        "family_label": "Table 4 four wound-complication outcomes on the same patients",
        "tests": [
          {
            "p_value": 0.019
          },
          {
            "p_value": 0.011
          },
          {
            "p_value": 0.015
          },
          {
            "p_value": 0.001
          }
        ],
        "alpha": 0.05
      },
      "reported": {
        "n_significant_uncorrected": 4
      },
      "computed": {
        "n_surviving_floor": 2,
        "n_surviving_ceiling": 4,
        "n_claims_lost_to_correction": 0,
        "bonferroni_threshold": 0.0125,
        "fwer_if_independent": 0.1855
      },
      "notes": "No correction is stated. BH and Holm keep all four; Bonferroni would drop gapping p=.019 and erythema p=.015 (threshold 0.0125), leaving seroma and infection. n_claims_lost_to_correction is 0 on Benjamini-Hochberg, the most permissive of the four methods. Family is the four complication endpoints on the same 397 women. Uncorrected testing is ordinary; this is the surviving-claims interval, not an accusation."
    },
    {
      "id": "optime_effect_size",
      "location": "Table 3, Operative time",
      "technique": "check_effect_plausibility",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience effect-size --mean1 40.1 --sd1 9.2 --n1 198 --mean2 45.5 --sd2 10.8 --n2 199 --design between",
      "quote": "Operative time (min) 40.1\u00b19.2 45.5\u00b110.8 <.001",
      "inputs": {
        "mean1": 40.1,
        "sd1": 9.2,
        "n1": 198,
        "mean2": 45.5,
        "sd2": 10.8,
        "n2": 199,
        "design": "between"
      },
      "reported": {
        "p": "<.001"
      },
      "computed": {
        "hedges_g": -0.537,
        "ci95_d": [
          -0.738,
          -0.338
        ]
      },
      "notes": "Interrupted closure is slower by g=0.54 (95% CI 0.34\u20130.74). Paper prints no effect size for this row."
    },
    {
      "id": "table5_bmi_effect_size",
      "location": "Table 5, BMI",
      "technique": "check_effect_plausibility",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience effect-size --mean1 37.8 --sd1 3.9 --n1 42 --mean2 34.1 --sd2 3.4 --n2 355 --design between",
      "quote": "BMI 37.8\u00b13.9 34.1\u00b13.4 <.001",
      "inputs": {
        "mean1": 37.8,
        "sd1": 3.9,
        "n1": 42,
        "mean2": 34.1,
        "sd2": 3.4,
        "n2": 355,
        "design": "between"
      },
      "reported": {
        "p": "<.001"
      },
      "computed": {
        "hedges_g": 1.069,
        "ci95_d": [
          0.742,
          1.399
        ]
      },
      "notes": "Large separation of BMI between those with and without wound complications. Magnitude is reported, not judged."
    },
    {
      "id": "optime_required_n",
      "location": "Table 3, Operative time",
      "technique": "required_n",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience required-n --test-type two_sample_t --effect-size 0.537 --alpha 0.05 --power 0.8 --tails 2 --actual-n 397",
      "quote": "Operative time (min) 40.1\u00b19.2 45.5\u00b110.8 <.001",
      "inputs": {
        "test_type": "two_sample_t",
        "effect_size": 0.537,
        "alpha": 0.05,
        "power": 0.8,
        "tails": 2,
        "actual_n": 397
      },
      "reported": {
        "n_analysed": 397
      },
      "computed": {
        "required_n_total": 112,
        "ratio": 3.545,
        "adequately_powered_for_this_effect": true
      },
      "notes": "Design-sensitivity only; not a defect. Effect size taken from check_effect_plausibility on the same row. No a-priori power calculation is printed anywhere in the paper."
    },
    {
      "id": "statcheck_no_apa",
      "location": "Full text",
      "technique": "statcheck",
      "consistent": true,
      "severity": "indeterminate",
      "reproduction": "metascience statcheck --pdf-path wound_healing.pdf",
      "quote": "p values=.019, .011, .015, and .001",
      "inputs": {
        "pdf_path": "wound_healing.pdf"
      },
      "reported": {
        "apa_stats_found": 0
      },
      "computed": {
        "stats_found": 0
      },
      "notes": "No APA-form statistics (t/F/\u03c7\u00b2 with df and p together) are printed. Tests appear as p-values beside means or n (%). Coverage limit of the scanner, not a clean bill. Recalculation used recalc_independent_t, recalc_chi_squared and check_estimate_ci instead."
    },
    {
      "id": "no_statistical_methods_section",
      "location": "Patients and methods",
      "technique": "not_computational",
      "consistent": false,
      "severity": "indeterminate",
      "reproduction": "not_computational: no metascience command applies",
      "quote": "Blood loss was estimated, operative time was recorded; all patients had preoperative antibiotic prophylaxis within 30min of incision time.",
      "inputs": {},
      "reported": {
        "tests_named": false
      },
      "computed": {
        "has_statistical_analysis_paragraph": false
      },
      "notes": "The paper never names t-test, chi-square, Fisher, logistic regression software, tails, or a multiplicity plan. Table 3/5 p-values sit beside mean\u00b1SD and Table 4/6 beside OR (CI). The Table 3 depth mismatch cannot be pinned to a named procedure. This is a reporting gap, not arithmetic."
    }
  ],
  "coverage": {
    "stats_found": 118,
    "tools_run": [
      "extract_pdf",
      "extract_xml",
      "parse_table",
      "parse_cells_typed",
      "parse_cells_as_declared",
      "check_summation_batch",
      "check_count_percent",
      "check_estimate_ci",
      "recalc_chi_squared",
      "recalc_independent_t",
      "grim_check",
      "grimmer_check",
      "check_sd_range",
      "check_table",
      "csf_test",
      "bayesian_table1_dispersion",
      "statcheck",
      "multiplicity_report",
      "detect_duplication",
      "flag_round_n",
      "check_effect_plausibility",
      "required_n"
    ],
    "tables_checked": [
      "Table 1",
      "Table 2",
      "Table 3",
      "Table 4",
      "Table 5",
      "Table 6",
      "Figure 1 CONSORT"
    ],
    "stats_checked": 96
  },
  "anatomy": {
    "studies": [
      {
        "id": "main",
        "label": "RCT of continuous versus interrupted subcutaneous closure at cesarean section in obese Egyptian women",
        "design": "rct",
        "n": 397,
        "unit_of_analysis": "participant",
        "clustered": false,
        "preregistered": true,
        "registry_id": "NCT03354078",
        "n_per_group": [
          {
            "label": "continuous",
            "n": 198
          },
          {
            "label": "interrupted",
            "n": 199
          }
        ],
        "sample_flow": [
          {
            "stage": "assessed for eligibility",
            "n": 411
          },
          {
            "stage": "excluded, refused to participate",
            "n": 11,
            "reason": "Refused to participate"
          },
          {
            "stage": "randomized",
            "n": 400
          },
          {
            "stage": "allocated to interrupted technique",
            "n": 200
          },
          {
            "stage": "allocated to continuous technique",
            "n": 200
          },
          {
            "stage": "lost follow-up interrupted",
            "n": 1,
            "reason": "did not come to follow up postoperative, patient from distant village"
          },
          {
            "stage": "lost follow-up continuous",
            "n": 2,
            "reason": "did not come to follow up postoperative, patient from distant village"
          },
          {
            "stage": "analysed interrupted",
            "n": 199
          },
          {
            "stage": "analysed continuous",
            "n": 198
          }
        ]
      }
    ],
    "variables": [
      {
        "id": "age",
        "name": "Age (years)",
        "measurement_level": "ratio",
        "discreteness": "unknown",
        "family": "continuous",
        "confidence": "high",
        "lower_bound": 25,
        "upper_bound": 35,
        "units": "years",
        "provenance_quote": "The age of patients included in this research was between 25 and 35 years"
      },
      {
        "id": "bmi",
        "name": "BMI",
        "measurement_level": "ratio",
        "discreteness": "continuous",
        "family": "continuous",
        "confidence": "high",
        "lower_bound": 23,
        "upper_bound": 45,
        "units": "kg/m^2",
        "provenance_quote": "BMI 23.0\u201345.0 34.5\u00b13.6 34.0"
      },
      {
        "id": "ga",
        "name": "Gestational age at time of CS",
        "measurement_level": "ratio",
        "discreteness": "continuous",
        "family": "continuous",
        "confidence": "high",
        "lower_bound": 35,
        "upper_bound": 39.7,
        "units": "weeks",
        "provenance_quote": "Gestational age at time of CS 35.0\u201339.7 37.7\u00b11.1 38.0"
      },
      {
        "id": "n_sutures",
        "name": "No. of sutures subcutaneous",
        "measurement_level": "ratio",
        "discreteness": "discrete",
        "family": "count",
        "confidence": "high",
        "lower_bound": 3,
        "upper_bound": 13,
        "units": "sutures",
        "derivation": "other",
        "derived_from": "each interrupted stitch, or each continuous loop from edge to edge, counted as one suture','provenance_quote':'The number of sutures was counted using a double-check method"
      },
      {
        "id": "optime",
        "name": "Operative time",
        "measurement_level": "ratio",
        "discreteness": "continuous",
        "family": "continuous",
        "confidence": "high",
        "lower_bound": 30,
        "upper_bound": 60,
        "units": "minutes",
        "provenance_quote": "Operative time (min) 30.0\u201360.0 42.8\u00b110.4 40.0"
      },
      {
        "id": "ebl",
        "name": "Estimated blood loss",
        "measurement_level": "ratio",
        "discreteness": "continuous",
        "family": "continuous",
        "confidence": "high",
        "lower_bound": 350,
        "upper_bound": 1000,
        "units": "cc",
        "provenance_quote": "Estimated blood loss (cc) 350.0\u20131000.0 658.8\u00b1165.2 650.0"
      },
      {
        "id": "depth",
        "name": "Subcutaneous tissue depth",
        "measurement_level": "ratio",
        "discreteness": "continuous",
        "family": "continuous",
        "confidence": "high",
        "lower_bound": 2,
        "upper_bound": 6.5,
        "units": "cm",
        "provenance_quote": "Subcutaneous tissue depth (cm) 2.0\u20136.5 4.4\u00b11.0 4.5"
      },
      {
        "id": "suture_type",
        "name": "Suture type",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "Continuous",
          "Interrupted"
        ],
        "derivation": "measured",
        "derived_from": "randomized allocation 1:1 to continuous or interrupted Vicryl 3-0 subcutaneous closure','provenance_quote':'The two groups were randomly selected, 200 in each group."
      },
      {
        "id": "wound_gapping",
        "name": "Wound gapping",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "Yes",
          "No"
        ],
        "derivation": "measured",
        "derived_from": "clinical inspection at postoperative visits','provenance_quote':'WoundGapping Yes 12(3) No 385(97)"
      },
      {
        "id": "wound_seroma",
        "name": "Wound seroma",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "Yes",
          "No"
        ],
        "derivation": "measured",
        "derived_from": "clinical inspection','provenance_quote':'Woundseroma Yes 10(2.5) No 387(97.5)"
      },
      {
        "id": "wound_erythema",
        "name": "Wound erythema",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "Yes",
          "No"
        ],
        "derivation": "measured",
        "derived_from": "clinical inspection','provenance_quote':'Wounderythema Yes 18(4.5) No 379(95.5)"
      },
      {
        "id": "wound_infection",
        "name": "Wound infection",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "Yes",
          "No"
        ],
        "derivation": "measured",
        "derived_from": "clinical inspection','provenance_quote':'Woundinfection Yes 20(5) No 377(95)"
      },
      {
        "id": "wound_complications",
        "name": "Any wound complication",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "medium",
        "n_categories": 2,
        "levels": [
          "Yes",
          "No"
        ],
        "derivation": "other",
        "derived_from": "composite of gapping, seroma, erythema, infection; 42 is less than the sum of the four Yes counts (60), so events overlap','provenance_quote':'Woundcomplications Yes 42(10.6) No 355(89.4)"
      }
    ],
    "tests": [
      {
        "id": "t3_age",
        "test_type": "independent_t",
        "location": "Table 3, Age",
        "confidence": "medium",
        "study_id": "main",
        "hypothesis_id": "h_baseline",
        "outcome_var": "age",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.444,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Age (years) 30.2\u00b13.2 30.4\u00b13.4.444"
      },
      {
        "id": "t3_bmi",
        "test_type": "independent_t",
        "location": "Table 3, BMI",
        "confidence": "medium",
        "study_id": "main",
        "hypothesis_id": "h_baseline",
        "outcome_var": "bmi",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.101,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "BMI 34.8\u00b13.9 34.2\u00b13.3.101"
      },
      {
        "id": "t3_ga",
        "test_type": "independent_t",
        "location": "Table 3, Gestational age",
        "confidence": "medium",
        "study_id": "main",
        "hypothesis_id": "h_baseline",
        "outcome_var": "ga",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.114,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "GestationalageattimeofCS 37.6\u00b11.1 37.8\u00b11.114"
      },
      {
        "id": "t3_sutures",
        "test_type": "independent_t",
        "location": "Table 3, No. of subcutaneous sutures",
        "confidence": "medium",
        "study_id": "main",
        "outcome_var": "n_sutures",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.791,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "No.ofsubcutaneoussutures 6.3\u00b13 6.3\u00b12.8.791"
      },
      {
        "id": "t3_optime",
        "test_type": "independent_t",
        "location": "Table 3, Operative time",
        "confidence": "medium",
        "study_id": "main",
        "outcome_var": "optime",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.001,
        "p_is_threshold": true,
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Operativetime(min) 40.1\u00b19.2 45.5\u00b110.8 <.001",
        "effect_size_estimated": {
          "value": -0.537,
          "kind": "hedges_g",
          "ci95": [
            -0.738,
            -0.338
          ],
          "computed_from": "Table 3 operative-time means, SDs and ns 198 vs 199",
          "tool": "check_effect_plausibility",
          "ci_spans_null": false
        }
      },
      {
        "id": "t3_ebl",
        "test_type": "independent_t",
        "location": "Table 3, Estimated blood loss",
        "confidence": "medium",
        "study_id": "main",
        "outcome_var": "ebl",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.084,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Estimatedbloodloss(cc) 644.4\u00b1164.2 673.1\u00b1165.4.084"
      },
      {
        "id": "t3_depth",
        "test_type": "independent_t",
        "location": "Table 3, Subcutaneous tissue depth",
        "confidence": "medium",
        "study_id": "main",
        "hypothesis_id": "h_baseline",
        "outcome_var": "depth",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.127,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Subcutaneoustissuedepth(cm) 4.5\u00b11 4.4\u00b10.9.127"
      },
      {
        "id": "t4_gapping",
        "test_type": "chi_squared",
        "location": "Table 4, Wound gapping",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_primary",
        "outcome_var": "wound_gapping",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.019,
        "p_is_threshold": false,
        "effect_size": "OR 5.239",
        "ci": "95% CI 1.133\u201324.227",
        "appears_in_abstract": true,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "Wound gapping 10 (5.1) 2 (1) .019 5.239 1.133\u201324.227"
      },
      {
        "id": "t4_seroma",
        "test_type": "chi_squared",
        "location": "Table 4, Wound seroma",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_primary",
        "outcome_var": "wound_seroma",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.011,
        "p_is_threshold": false,
        "effect_size": "OR 9.429",
        "ci": "95% CI 1.183\u201375.138",
        "appears_in_abstract": true,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "Wound seroma 9 (4.5) 1 (0.5) .011 9.429 1.183\u201375.138"
      },
      {
        "id": "t4_erythema",
        "test_type": "chi_squared",
        "location": "Table 4, Wound erythema",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_primary",
        "outcome_var": "wound_erythema",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.015,
        "p_is_threshold": false,
        "effect_size": "OR 3.709",
        "ci": "95% CI 1.199\u201311.475",
        "appears_in_abstract": true,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "Wound erythema 14 (7.1) 4 (2) .015 3.709 1.199\u201311.475"
      },
      {
        "id": "t4_infection",
        "test_type": "chi_squared",
        "location": "Table 4, Wound Infection",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_primary",
        "outcome_var": "wound_infection",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.001,
        "p_is_threshold": false,
        "effect_size": "OR 6.136",
        "ci": "95% CI 1.769\u201321.287",
        "appears_in_abstract": true,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "Wound Infection 17 (8.6) 3 (1.5) .001 6.136 1.769\u201321.287"
      },
      {
        "id": "t5_age",
        "test_type": "independent_t",
        "location": "Table 5, Age",
        "confidence": "medium",
        "study_id": "main",
        "outcome_var": "age",
        "grouping_var": "wound_complications",
        "n": 397,
        "p_value": 0.336,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Age (years) 29.9\u00b13.5 30.3\u00b13.2.336"
      },
      {
        "id": "t5_bmi",
        "test_type": "independent_t",
        "location": "Table 5, BMI",
        "confidence": "medium",
        "study_id": "main",
        "hypothesis_id": "h_predictors",
        "outcome_var": "bmi",
        "grouping_var": "wound_complications",
        "n": 397,
        "p_value": 0.001,
        "p_is_threshold": true,
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": false,
        "provenance_quote": "BMI 37.8\u00b13.9 34.1\u00b13.4 <.001",
        "effect_size_estimated": {
          "value": 1.069,
          "kind": "hedges_g",
          "ci95": [
            0.742,
            1.399
          ],
          "computed_from": "Table 5 BMI means, SDs and ns 42 vs 355",
          "tool": "check_effect_plausibility",
          "ci_spans_null": false
        }
      },
      {
        "id": "t5_ga",
        "test_type": "independent_t",
        "location": "Table 5, Gestational age",
        "confidence": "medium",
        "study_id": "main",
        "outcome_var": "ga",
        "grouping_var": "wound_complications",
        "n": 397,
        "p_value": 0.077,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "GestationalageattimeofCS 38\u00b11 37.7\u00b11.1.077"
      },
      {
        "id": "t5_sutures",
        "test_type": "independent_t",
        "location": "Table 5, No. of sutures",
        "confidence": "medium",
        "study_id": "main",
        "outcome_var": "n_sutures",
        "grouping_var": "wound_complications",
        "n": 397,
        "p_value": 0.005,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "No.ofsuturessubcutaneous 5.1\u00b12.4 6.4\u00b12.9.005"
      },
      {
        "id": "t5_optime",
        "test_type": "independent_t",
        "location": "Table 5, Operative time",
        "confidence": "medium",
        "study_id": "main",
        "outcome_var": "optime",
        "grouping_var": "wound_complications",
        "n": 397,
        "p_value": 0.141,
        "p_is_threshold": false,
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Operativetime(min) 44.8\u00b19.9 42.5\u00b110.4.141"
      },
      {
        "id": "t5_ebl",
        "test_type": "independent_t",
        "location": "Table 5, Estimated blood loss",
        "confidence": "medium",
        "study_id": "main",
        "hypothesis_id": "h_predictors",
        "outcome_var": "ebl",
        "grouping_var": "wound_complications",
        "n": 397,
        "p_value": 0.001,
        "p_is_threshold": true,
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Estimatedbloodloss(cc) 754.8\u00b1179 647.5\u00b1160 <.001"
      },
      {
        "id": "t5_depth",
        "test_type": "independent_t",
        "location": "Table 5, Subcutaneous tissue depth",
        "confidence": "medium",
        "study_id": "main",
        "hypothesis_id": "h_predictors",
        "outcome_var": "depth",
        "grouping_var": "wound_complications",
        "n": 397,
        "p_value": 0.001,
        "p_is_threshold": true,
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Subcutaneoustissuedepth(cm) 5\u00b11 4.4\u00b11 <.001",
        "effect_size_estimated": {
          "value": 0.599,
          "kind": "hedges_g",
          "ci95": [
            0.277,
            0.923
          ],
          "computed_from": "Table 5 depth means, SDs and ns 42 vs 355",
          "tool": "check_effect_plausibility",
          "ci_spans_null": false
        }
      },
      {
        "id": "t5_suture_type",
        "test_type": "chi_squared",
        "location": "Table 5, Suture type",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_primary",
        "outcome_var": "wound_complications",
        "grouping_var": "suture_type",
        "n": 397,
        "p_value": 0.001,
        "p_is_threshold": true,
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "Continuous 33 (78.6) 165 (46.5) <.001"
      },
      {
        "id": "t6_age",
        "test_type": "logistic_regression",
        "location": "Table 6, Age",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_predictors",
        "outcome_var": "wound_complications",
        "predictor_vars": [
          "age"
        ],
        "n": 397,
        "p_value": 0.943,
        "p_is_threshold": false,
        "effect_size": "OR 1.005",
        "ci": "95% CI 0.887\u20131.138",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Age (years) 1.005 0.887\u20131.138 .943"
      },
      {
        "id": "t6_bmi",
        "test_type": "logistic_regression",
        "location": "Table 6, BMI",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_predictors",
        "outcome_var": "wound_complications",
        "predictor_vars": [
          "bmi"
        ],
        "n": 397,
        "p_value": 0.001,
        "p_is_threshold": true,
        "effect_size": "OR 1.333",
        "ci": "95% CI 1.188\u20131.494",
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": false,
        "provenance_quote": "BMI 1.333 1.188\u20131.494 <.001"
      },
      {
        "id": "t6_ga",
        "test_type": "logistic_regression",
        "location": "Table 6, Gestational age",
        "confidence": "high",
        "study_id": "main",
        "outcome_var": "wound_complications",
        "predictor_vars": [
          "ga"
        ],
        "n": 397,
        "p_value": 0.149,
        "p_is_threshold": false,
        "effect_size": "OR 1.359",
        "ci": "95% CI 0.896\u20132.062",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Gestational age at time of CS 1.359 0.896\u20132.062 .149"
      },
      {
        "id": "t6_sutures",
        "test_type": "logistic_regression",
        "location": "Table 6, No. of sutures",
        "confidence": "high",
        "study_id": "main",
        "outcome_var": "wound_complications",
        "predictor_vars": [
          "n_sutures"
        ],
        "n": 397,
        "p_value": 0.87,
        "p_is_threshold": false,
        "effect_size": "OR 1.020",
        "ci": "95% CI 0.805\u20131.293",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "No. of sutures subcutaneous 1.020 0.805\u20131.293 .870"
      },
      {
        "id": "t6_optime",
        "test_type": "logistic_regression",
        "location": "Table 6, Operative time",
        "confidence": "high",
        "study_id": "main",
        "outcome_var": "wound_complications",
        "predictor_vars": [
          "optime"
        ],
        "n": 397,
        "p_value": 0.146,
        "p_is_threshold": false,
        "effect_size": "OR 1.037",
        "ci": "95% CI 0.987\u20131.089",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Operative time (min) 1.037 0.987\u20131.089 .146"
      },
      {
        "id": "t6_ebl",
        "test_type": "logistic_regression",
        "location": "Table 6, Estimated blood loss",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_predictors",
        "outcome_var": "wound_complications",
        "predictor_vars": [
          "ebl"
        ],
        "n": 397,
        "p_value": 0.001,
        "p_is_threshold": true,
        "effect_size": "OR 1.008",
        "ci": "95% CI 1.005\u20131.010",
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Estimated blood loss (cc) 1.008 1.005\u20131.010 <.001"
      },
      {
        "id": "t6_depth",
        "test_type": "logistic_regression",
        "location": "Table 6, Subcutaneous tissue depth",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_predictors",
        "outcome_var": "wound_complications",
        "predictor_vars": [
          "depth"
        ],
        "n": 397,
        "p_value": 0.009,
        "p_is_threshold": false,
        "effect_size": "OR 1.855",
        "ci": "95% CI 1.171\u20132.940",
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": false,
        "provenance_quote": "Subcutaneous tissue depth (cm) 1.855 1.171\u20132.940 .009"
      },
      {
        "id": "t6_suture",
        "test_type": "logistic_regression",
        "location": "Table 6, Continuous VS Interrupted Sutures",
        "confidence": "high",
        "study_id": "main",
        "hypothesis_id": "h_primary",
        "outcome_var": "wound_complications",
        "predictor_vars": [
          "suture_type"
        ],
        "n": 397,
        "p_value": 0.001,
        "p_is_threshold": true,
        "effect_size": "OR 7.743",
        "ci": "95% CI 3.030\u201319.788",
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true,
        "provenance_quote": "Continuous VS Interrupted Sutures 7.743 3.030\u201319.788 <.001"
      }
    ],
    "hypotheses": [
      {
        "id": "h_primary",
        "statement": "Interrupted subcutaneous closure is superior to continuous closure for postoperative wound complications in obese women undergoing cesarean section.",
        "status": "confirmatory",
        "study_id": "main",
        "appears_in_abstract": true,
        "provenance_quote": "Subcutaneous wound closure using interrupted technique of suturing in obese patients is superior to continuous technique as regard wound complications.",
        "confidence": "high"
      },
      {
        "id": "h_predictors",
        "statement": "BMI, estimated blood loss, subcutaneous tissue depth and continuous (versus interrupted) sutures predict wound complications.",
        "status": "exploratory",
        "study_id": "main",
        "appears_in_abstract": false,
        "provenance_quote": "multivariate analysis to explore predictors of wound complications",
        "confidence": "high"
      },
      {
        "id": "h_baseline",
        "statement": "Randomized arms do not differ on demographic and preoperative characteristics.",
        "status": "unstated",
        "study_id": "main",
        "appears_in_abstract": false,
        "provenance_quote": "showing statistical significant difference only regarding operative time with p value=<.001",
        "confidence": "medium"
      }
    ]
  },
  "paper_title": "Effect of subcutaneous tissue closure technique in cesarean section on postoperative wound complications in obese Egyptian women",
  "paper_metadata": {
    "authors": "Mahmoud Alalfy, Ahmed Elgazzar, Tamer Fares, Omar Nagy, Ahmed Ellithy, Yossra Lasheen, Ahmed Kamel, Mahmoud Soliman, Ahmed Hassan, Ahmed Samy, Ayman M. Taher, Asmaa I. Ogila, Hany Saad, Hend Salah, Mohamed Ramadan, Mohamed Nabil, Dina L. Hatem, Mohamed Fikry",
    "journal": "The Journal of Maternal-Fetal & Neonatal Medicine",
    "year": "2019",
    "doi": "10.1080/14767058.2018.1438399",
    "study_design": "rct",
    "corresponding_author": "Mahmoud Alalfy",
    "corresponding_email": "mahmoudalalfy@ymail.com"
  },
  "unchecked": [
    {
      "location": "Publisher XML",
      "reason": "extract_xml: no XML full text at the paper path; sweep used PDF + body.md. Table structure from docling/PDF grids and markdown."
    },
    {
      "location": "Figure 1 image crop",
      "reason": "extract_figures was denied by the tool-permission policy. CONSORT counts were read from body.md and the PDF page image and checked with check_summation_batch instead of check_flow_arithmetic (also denied)."
    },
    {
      "location": "Supplementary files",
      "reason": "No supplementary data files were present in the paper directory. Nothing to extract_supplement."
    },
    {
      "location": "Table 2 vs Table 3 vs Table 5 pooled means",
      "reason": "No registered tool checks whether two group means/SDs pool to the printed overall mean. Left unchecked rather than computed by hand."
    },
    {
      "location": "A-priori power calculation",
      "reason": "The paper prints none. verify_power_analysis cannot run without stated inputs. Recruited N=400 is recorded; required_n was run only on observed effects, which is design-sensitivity, not a reproduced power statement."
    },
    {
      "location": "ClinicalTrials.gov NCT03354078",
      "reason": "The identifier is printed. Registration contents and date versus the June\u2013December 2017 enrolment window were not retrieved (web search disabled)."
    },
    {
      "location": "Table 3 check_table cells",
      "reason": "check_table ran 0 of 18 dispatched checks because group n was not carried in the cells (n lives in Methods/CONSORT, not in Table 3 column headers). Independent t-tests were run separately with n1=198, n2=199."
    },
    {
      "location": "GRIM on n=397 means to 1 decimal",
      "reason": "grim_check refused for no discriminating power. Not a pass."
    },
    {
      "location": "Discussion statistics from cited trials",
      "reason": "Pain 0.17 vs 0.51 p=.04, operative time 24.6 vs 32.9 min p<.0001, and De Vivo ORs belong to cited papers [21,22], not this dataset."
    },
    {
      "location": "detect_tortured_phrases / image duplication",
      "reason": "Those detectors were not available or were permission-denied on this backend. Caption typos ('Demonestrates', 'between between') were noted but not raised as arithmetic findings."
    }
  ],
  "figures": [
    {
      "label": "Figure 1",
      "is_data_figure": false,
      "page": 4,
      "caption": "Consort flow diagram.",
      "n_panels": 1,
      "panels": [
        {
          "chart_type": "flow_diagram",
          "panel": "A",
          "shows": "CONSORT cascade: 411 assessed, 11 refused, 400 randomised 1:1, 1 and 2 lost to follow-up, 199 and 198 analysed."
        }
      ],
      "carries_unique_values": true
    }
  ],
  "statistics_register": [
    {
      "source": "abstract",
      "kind": "p_value",
      "values": {
        "p_gapping": 0.019,
        "p_seroma": 0.011,
        "p_erythema": 0.015,
        "p_infection": 0.001
      },
      "quote": "p values=.019, .011, .015, and .001, in consecutive order",
      "checkable": {
        "tools": [
          "recalc_chi_squared",
          "check_estimate_ci"
        ]
      },
      "id": "abs_p",
      "location": "Abstract, Results"
    },
    {
      "source": "abstract",
      "kind": "estimate_ci",
      "values": {
        "or_gapping": 5.239,
        "or_seroma": 9.429,
        "or_erythema": 3.709,
        "or_infection": 6.136
      },
      "quote": "odds ratio in wound gapping=5.239, wound seroma OR=9.429, wound erythema OR=3.709, and wound infection OR=6.136",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "recalc_chi_squared"
        ]
      },
      "id": "abs_or",
      "location": "Abstract, Results",
      "duplicate_of": "t4_ors"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "n_recruited": 400
      },
      "quote": "Four hundred pregnant women were recruited for this study",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "n400",
      "location": "Patients and methods"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "n_per_arm": 200
      },
      "quote": "The two groups were randomly selected, 200 in each group.",
      "checkable": {
        "tools": [
          "check_summation",
          "flag_round_n"
        ]
      },
      "id": "n200",
      "location": "Patients and methods"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "lost_continuous": 2,
        "lost_interrupted": 1,
        "n_continuous": 198,
        "n_interrupted": 199
      },
      "quote": "The net of the continuous group was 198 and that of the interrupted group was 199 ladies",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "n_analysed",
      "location": "Patients and methods"
    },
    {
      "source": "figure",
      "kind": "count",
      "values": {
        "assessed": 411,
        "excluded": 11,
        "randomized": 400
      },
      "quote": "Assessed (N= 411) Excluded (N =11) Refused to participate Randomized N= 400",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "consort_top",
      "location": "Figure 1"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 198,
        "pct": 49.9
      },
      "quote": "Continuous 198 (49.9) after lost follow up of 2 women",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_cont",
      "location": "Table 1, Continuous"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 199,
        "pct": 50.1
      },
      "quote": "Interrupted 199 (50.1) after lost follow up of 2 women",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_int",
      "location": "Table 1, Interrupted"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 12,
        "pct": 3
      },
      "quote": "Yes 12 (3)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_gap_y",
      "location": "Table 1, Wound Gapping Yes"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 385,
        "pct": 97
      },
      "quote": "No 385 (97)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_gap_n",
      "location": "Table 1, Wound Gapping No"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 10,
        "pct": 2.5
      },
      "quote": "Yes 10 (2.5)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_ser_y",
      "location": "Table 1, Wound seroma Yes"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 387,
        "pct": 97.5
      },
      "quote": "No 387 (97.5)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_ser_n",
      "location": "Table 1, Wound seroma No"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 18,
        "pct": 4.5
      },
      "quote": "Yes 18 (4.5)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_ery_y",
      "location": "Table 1, Wound erythema Yes"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 379,
        "pct": 95.5
      },
      "quote": "No 379 (95.5)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_ery_n",
      "location": "Table 1, Wound erythema No"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 20,
        "pct": 5
      },
      "quote": "Yes 20 (5)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_inf_y",
      "location": "Table 1, Wound infection Yes"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 377,
        "pct": 95
      },
      "quote": "No 377 (95)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_inf_n",
      "location": "Table 1, Wound infection No"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 42,
        "pct": 10.6
      },
      "quote": "Yes 42 (10.6)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_any_y",
      "location": "Table 1, Wound complications Yes"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n": 355,
        "pct": 89.4
      },
      "quote": "No 355 (89.4)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t1_any_n",
      "location": "Table 1, Wound complications No"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "gapping_pct": 12,
        "seroma_pct": 10,
        "erythema_pct": 18,
        "infection_pct": 20
      },
      "quote": "wound gapping occurred in 12% of cases, wound seroma occurred in 10% of cases, wound erythema occurred in 18% of cases, and wound infection occurred in 20% of cases in the whole cohort of cases.",
      "checkable": {
        "tools": [],
        "reason": "these percentages contradict Table 1 n (%); the contradiction is logical, not a GRIM question"
      },
      "id": "prose_pct_results",
      "location": "Results, Description"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "gapping_pct": 12,
        "seroma_pct": 10,
        "erythema_pct": 18,
        "infection_pct": 20
      },
      "quote": "the percentage of wound gapping occurred in 12% of cases, wound seroma occurred in 10% of cases, and wound erythema occurred in 18% of cases, while wound infection occurred in 20% of cases.",
      "checkable": {
        "tools": [],
        "reason": "duplicate of the Results 12%/10%/18%/20% misreporting"
      },
      "id": "prose_pct_disc",
      "location": "Discussion",
      "duplicate_of": "prose_pct_results"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 30.3,
        "SD": 3.3,
        "min": 25.0,
        "max": 35.0,
        "median": 30.0
      },
      "quote": "Age (years) 25.0\u201335.0 30.3\u00b13.3 30.0",
      "checkable": {
        "tools": [
          "grim_check",
          "check_sd_range"
        ]
      },
      "id": "t2_age",
      "location": "Table 2, Age"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 34.5,
        "SD": 3.6,
        "min": 23.0,
        "max": 45.0,
        "median": 34.0
      },
      "quote": "BMI 23.0\u201345.0 34.5\u00b13.6 34.0",
      "checkable": {
        "tools": [
          "check_sd_range"
        ]
      },
      "id": "t2_bmi",
      "location": "Table 2, BMI"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 37.7,
        "SD": 1.1,
        "min": 35.0,
        "max": 39.7,
        "median": 38.0
      },
      "quote": "Gestational age at time of CS 35.0\u201339.7 37.7\u00b11.1 38.0",
      "checkable": {
        "tools": [
          "check_sd_range"
        ]
      },
      "id": "t2_ga",
      "location": "Table 2, GA"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 6.3,
        "SD": 2.9,
        "min": 3.0,
        "max": 13.0,
        "median": 5.0
      },
      "quote": "No. of sutures subcutaneous 3.0\u201313.0 6.3\u00b12.9 5.0",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check",
          "sprite_reconstruct",
          "check_sd_range"
        ]
      },
      "id": "t2_sut",
      "location": "Table 2, sutures"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 42.8,
        "SD": 10.4,
        "min": 30.0,
        "max": 60.0,
        "median": 40.0
      },
      "quote": "Operative time (min) 30.0\u201360.0 42.8\u00b110.4 40.0",
      "checkable": {
        "tools": [
          "check_sd_range"
        ]
      },
      "id": "t2_opt",
      "location": "Table 2, operative time"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 658.8,
        "SD": 165.2,
        "min": 350.0,
        "max": 1000.0,
        "median": 650.0
      },
      "quote": "Estimated blood loss (cc) 350.0\u20131000.0 658.8\u00b1165.2 650.0",
      "checkable": {
        "tools": [
          "check_sd_range"
        ]
      },
      "id": "t2_ebl",
      "location": "Table 2, EBL"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M": 4.4,
        "SD": 1.0,
        "min": 2.0,
        "max": 6.5,
        "median": 4.5
      },
      "quote": "Subcutaneous tissue depth (cm) 2.0\u20136.5 4.4\u00b11.0 4.5",
      "checkable": {
        "tools": [
          "check_sd_range"
        ]
      },
      "id": "t2_dep",
      "location": "Table 2, depth"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 30.2,
        "SD1": 3.2,
        "M2": 30.4,
        "SD2": 3.4,
        "p": 0.444
      },
      "quote": "Age (years) 30.2\u00b13.2 30.4\u00b13.4.444",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t3_age",
      "location": "Table 3, Age"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 34.8,
        "SD1": 3.9,
        "M2": 34.2,
        "SD2": 3.3,
        "p": 0.101
      },
      "quote": "BMI 34.8\u00b13.9 34.2\u00b13.3.101",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t3_bmi",
      "location": "Table 3, BMI"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 37.6,
        "SD1": 1.1,
        "M2": 37.8,
        "SD2": 1.0,
        "p": 0.114
      },
      "quote": "GestationalageattimeofCS 37.6\u00b11.1 37.8\u00b11.114",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t3_ga",
      "location": "Table 3, GA"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 6.3,
        "SD1": 3.0,
        "M2": 6.3,
        "SD2": 2.8,
        "p": 0.791
      },
      "quote": "No.ofsubcutaneoussutures 6.3\u00b13 6.3\u00b12.8.791",
      "checkable": {
        "tools": [
          "recalc_independent_t",
          "grim_check"
        ]
      },
      "id": "t3_sut",
      "location": "Table 3, sutures"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 40.1,
        "SD1": 9.2,
        "M2": 45.5,
        "SD2": 10.8,
        "p": "<.001"
      },
      "quote": "Operativetime(min) 40.1\u00b19.2 45.5\u00b110.8 <.001",
      "checkable": {
        "tools": [
          "recalc_independent_t",
          "check_effect_plausibility"
        ]
      },
      "id": "t3_opt",
      "location": "Table 3, operative time"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 644.4,
        "SD1": 164.2,
        "M2": 673.1,
        "SD2": 165.4,
        "p": 0.084
      },
      "quote": "Estimatedbloodloss(cc) 644.4\u00b1164.2 673.1\u00b1165.4.084",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t3_ebl",
      "location": "Table 3, EBL"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 4.5,
        "SD1": 1.0,
        "M2": 4.4,
        "SD2": 0.9,
        "p": 0.127
      },
      "quote": "Subcutaneoustissuedepth(cm) 4.5\u00b11 4.4\u00b10.9.127",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t3_dep",
      "location": "Table 3, depth"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "n_c": 10,
        "pct_c": 5.1,
        "n_i": 2,
        "pct_i": 1,
        "p": 0.019,
        "or": 5.239,
        "ci_lo": 1.133,
        "ci_hi": 24.227
      },
      "quote": "Wound gapping 10 (5.1) 2 (1) .019 5.239 1.133\u201324.227",
      "checkable": {
        "tools": [
          "check_count_percent",
          "recalc_chi_squared",
          "check_estimate_ci"
        ]
      },
      "id": "t4_ors",
      "location": "Table 4, Wound gapping"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "n_c": 9,
        "pct_c": 4.5,
        "n_i": 1,
        "pct_i": 0.5,
        "p": 0.011,
        "or": 9.429,
        "ci_lo": 1.183,
        "ci_hi": 75.138
      },
      "quote": "Wound seroma 9 (4.5) 1 (0.5) .011 9.429 1.183\u201375.138",
      "checkable": {
        "tools": [
          "check_count_percent",
          "recalc_chi_squared",
          "check_estimate_ci"
        ]
      },
      "id": "t4_ser",
      "location": "Table 4, Wound seroma"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "n_c": 14,
        "pct_c": 7.1,
        "n_i": 4,
        "pct_i": 2,
        "p": 0.015,
        "or": 3.709,
        "ci_lo": 1.199,
        "ci_hi": 11.475
      },
      "quote": "Wound erythema 14 (7.1) 4 (2) .015 3.709 1.199\u201311.475",
      "checkable": {
        "tools": [
          "check_count_percent",
          "recalc_chi_squared",
          "check_estimate_ci"
        ]
      },
      "id": "t4_ery",
      "location": "Table 4, Wound erythema"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "n_c": 17,
        "pct_c": 8.6,
        "n_i": 3,
        "pct_i": 1.5,
        "p": 0.001,
        "or": 6.136,
        "ci_lo": 1.769,
        "ci_hi": 21.287
      },
      "quote": "Wound Infection 17 (8.6) 3 (1.5) .001 6.136 1.769\u201321.287",
      "checkable": {
        "tools": [
          "check_count_percent",
          "recalc_chi_squared",
          "check_estimate_ci"
        ]
      },
      "id": "t4_inf",
      "location": "Table 4, Wound Infection"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 29.9,
        "SD1": 3.5,
        "M2": 30.3,
        "SD2": 3.2,
        "p": 0.336
      },
      "quote": "Age (years) 29.9\u00b13.5 30.3\u00b13.2.336",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t5_age",
      "location": "Table 5, Age"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 37.8,
        "SD1": 3.9,
        "M2": 34.1,
        "SD2": 3.4,
        "p": "<.001"
      },
      "quote": "BMI 37.8\u00b13.9 34.1\u00b13.4 <.001",
      "checkable": {
        "tools": [
          "recalc_independent_t",
          "check_effect_plausibility"
        ]
      },
      "id": "t5_bmi",
      "location": "Table 5, BMI"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 38,
        "SD1": 1,
        "M2": 37.7,
        "SD2": 1.1,
        "p": 0.077
      },
      "quote": "GestationalageattimeofCS 38\u00b11 37.7\u00b11.1.077",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t5_ga",
      "location": "Table 5, GA"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 5.1,
        "SD1": 2.4,
        "M2": 6.4,
        "SD2": 2.9,
        "p": 0.005
      },
      "quote": "No.ofsuturessubcutaneous 5.1\u00b12.4 6.4\u00b12.9.005",
      "checkable": {
        "tools": [
          "recalc_independent_t",
          "grimmer_check"
        ]
      },
      "id": "t5_sut",
      "location": "Table 5, sutures"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 44.8,
        "SD1": 9.9,
        "M2": 42.5,
        "SD2": 10.4,
        "p": 0.141
      },
      "quote": "Operativetime(min) 44.8\u00b19.9 42.5\u00b110.4.141",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t5_opt",
      "location": "Table 5, operative time"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 754.8,
        "SD1": 179,
        "M2": 647.5,
        "SD2": 160,
        "p": "<.001"
      },
      "quote": "Estimatedbloodloss(cc) 754.8\u00b1179 647.5\u00b1160 <.001",
      "checkable": {
        "tools": [
          "recalc_independent_t"
        ]
      },
      "id": "t5_ebl",
      "location": "Table 5, EBL"
    },
    {
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "M1": 5,
        "SD1": 1,
        "M2": 4.4,
        "SD2": 1,
        "p": "<.001"
      },
      "quote": "Subcutaneoustissuedepth(cm) 5\u00b11 4.4\u00b11 <.001",
      "checkable": {
        "tools": [
          "recalc_independent_t",
          "check_effect_plausibility"
        ]
      },
      "id": "t5_dep",
      "location": "Table 5, depth"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n_yes": 33,
        "pct_yes": 78.6,
        "n_no": 165,
        "pct_no": 46.5,
        "p": "<.001"
      },
      "quote": "Continuous 33 (78.6) 165 (46.5) <.001",
      "checkable": {
        "tools": [
          "check_count_percent",
          "recalc_chi_squared"
        ]
      },
      "id": "t5_cont",
      "location": "Table 5, Continuous"
    },
    {
      "source": "table",
      "kind": "percentage",
      "values": {
        "n_yes": 9,
        "pct_yes": 21.4,
        "n_no": 190,
        "pct_no": 53.5
      },
      "quote": "Interrupted 9 (21.4) 190 (53.5)",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "t5_int",
      "location": "Table 5, Interrupted"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "or": 1.005,
        "ci_lo": 0.887,
        "ci_hi": 1.138,
        "p": 0.943
      },
      "quote": "Age (years) 1.005 0.887\u20131.138 .943",
      "checkable": {
        "tools": [
          "check_estimate_ci"
        ]
      },
      "id": "t6_age",
      "location": "Table 6, Age"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "or": 1.333,
        "ci_lo": 1.188,
        "ci_hi": 1.494,
        "p": "<.001"
      },
      "quote": "BMI 1.333 1.188\u20131.494 <.001",
      "checkable": {
        "tools": [
          "check_estimate_ci"
        ]
      },
      "id": "t6_bmi",
      "location": "Table 6, BMI"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "or": 1.359,
        "ci_lo": 0.896,
        "ci_hi": 2.062,
        "p": 0.149
      },
      "quote": "Gestational age at time of CS 1.359 0.896\u20132.062 .149",
      "checkable": {
        "tools": [
          "check_estimate_ci"
        ]
      },
      "id": "t6_ga",
      "location": "Table 6, GA"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "or": 1.02,
        "ci_lo": 0.805,
        "ci_hi": 1.293,
        "p": 0.87
      },
      "quote": "No. of sutures subcutaneous 1.020 0.805\u20131.293 .870",
      "checkable": {
        "tools": [
          "check_estimate_ci"
        ]
      },
      "id": "t6_sut",
      "location": "Table 6, sutures"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "or": 1.037,
        "ci_lo": 0.987,
        "ci_hi": 1.089,
        "p": 0.146
      },
      "quote": "Operative time (min) 1.037 0.987\u20131.089 .146",
      "checkable": {
        "tools": [
          "check_estimate_ci"
        ]
      },
      "id": "t6_opt",
      "location": "Table 6, operative time"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "or": 1.008,
        "ci_lo": 1.005,
        "ci_hi": 1.01,
        "p": "<.001"
      },
      "quote": "Estimated blood loss (cc) 1.008 1.005\u20131.010 <.001",
      "checkable": {
        "tools": [
          "check_estimate_ci"
        ]
      },
      "id": "t6_ebl",
      "location": "Table 6, EBL"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "or": 1.855,
        "ci_lo": 1.171,
        "ci_hi": 2.94,
        "p": 0.009
      },
      "quote": "Subcutaneous tissue depth (cm) 1.855 1.171\u20132.940 .009",
      "checkable": {
        "tools": [
          "check_estimate_ci"
        ]
      },
      "id": "t6_dep",
      "location": "Table 6, depth"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "or": 7.743,
        "ci_lo": 3.03,
        "ci_hi": 19.788,
        "p": "<.001"
      },
      "quote": "Continuous VS Interrupted Sutures 7.743 3.030\u201319.788 <.001",
      "checkable": {
        "tools": [
          "check_estimate_ci"
        ]
      },
      "id": "t6_sutype",
      "location": "Table 6, suture type"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "n_cited": 218
      },
      "quote": "they recruited a total of 218 women",
      "checkable": {
        "tools": [],
        "reason": "sample size of a cited trial, not this paper's data"
      },
      "id": "cited_218",
      "location": "Discussion"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "n_ops": 6930,
        "n_drain": 3495,
        "n_nodrain": 3435
      },
      "quote": "A total of 6930 operations were investigated",
      "checkable": {
        "tools": [],
        "reason": "cited meta-analysis [20], not this paper's data"
      },
      "id": "cited_6930",
      "location": "Discussion"
    },
    {
      "source": "prose",
      "kind": "p_value",
      "values": {
        "p": 0.04
      },
      "quote": "pain at 6 weeks postoperatively was statistically significantly less in the staple category (0.17 versus 0.51; p=.04)",
      "checkable": {
        "tools": [],
        "reason": "cited RCT [21], not this paper's data"
      },
      "id": "cited_pain",
      "location": "Discussion"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "n_cited": 212
      },
      "quote": "recruitment of 212 women at term giving birth by elective cesarean delivery",
      "checkable": {
        "tools": [],
        "reason": "cited observational study [22]"
      },
      "id": "cited_212",
      "location": "Discussion"
    }
  ],
  "second_look": {
    "n_accusatory": 4,
    "n_flagged": 4,
    "by_marker": {
      "quote_not_located": 4
    },
    "items": [
      {
        "id": "bmi_range_vs_inclusion",
        "severity": "suspicious",
        "location": "Table 2, BMI row vs Patients and methods inclusion criteria",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "prose_counts_reported_as_percentages",
        "severity": "suspicious",
        "location": "Results Description and Discussion, whole-cohort wound-complication rates",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "interrupted_lost_followup_two_vs_one",
        "severity": "suspicious",
        "location": "Table 1, Interrupted row vs Figure 1 and Methods",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table3_subcut_depth_p",
        "severity": "suspicious",
        "location": "Table 3, Subcutaneous tissue depth row",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      }
    ],
    "note": "4 of 4 accusation(s) carry a named weakness in their evidence. Each is listed with what would settle it. This is a worklist, not a verdict: none of these is wrong because it is listed, and a marker you resolve should be recorded in `triage` like any other triage decision."
  }
}
```

Triage these findings (confirm / deprioritize / reinterpret per the rulebook — especially baseline-similarity results), add the contextual reasoning the sweep cannot do, and emit the report JSON.