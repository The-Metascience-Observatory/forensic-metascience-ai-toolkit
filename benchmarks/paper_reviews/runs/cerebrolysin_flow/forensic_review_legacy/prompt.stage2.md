Write the editorial forensic review for this paper.

Read the paper body with the Read tool: `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/cerebrolysin_flow/paper/markdown/body.md`

What the sweep actually ran, which is the DENOMINATOR your verdict sits in:

```json
{
  "checks_passed": 20,
  "of_which_collapsed_by_check_table": 11,
  "checks_refused_indeterminate": 2,
  "checks_flagged": 12,
  "checks_total": 34,
  "by_severity": {
    "suspicious": 11,
    "highly_suspicious": 1,
    "indeterminate": 2,
    "consistent": 9
  },
  "by_outcome": {
    "flagged": 12,
    "refused": 2,
    "pass": 9
  },
  "rounding_convention": {
    "n_fit_only_under_truncation": 0,
    "n_granularity_checks": 1,
    "note": "Values that fail the round-half convention but are consistent if the reporter TRUNCATES (SPSS's default, and several journal styles). NOT a finding and never counted as one: a single instance is a house style. The RATE is the signal -- this class of anomaly is commoner in papers with more serious problems, so a high proportion is grounds to look harder, not evidence in itself."
  },
  "grace": {
    "n_items": 1,
    "n_reconciled_strictly": 1,
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
    "n_granularity_checks": 1,
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
      "id": "table3_combined_copied_from_table2",
      "location": "Table 3, Combined (Wei-Lachin) row",
      "technique": "detect_duplication",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience duplication-detect --decimals-mean 4 --decimals-sd 4 --near-match true",
      "quote": "| Combined (Wei-Lachin) |                                   | 0,5611 | (0,5456 to 0,5766) | 10 / 3  | <0.0001 |",
      "inputs": {
        "blocks": [
          {
            "label": "Table 2 multidimensional histology MW and p",
            "sample_id": "table2_stimulus",
            "independent": true,
            "cells": [
              {
                "label": "Combined",
                "value": 0.5611,
                "sd": 0.0001
              }
            ]
          },
          {
            "label": "Table 3 muscle assessments MW and p",
            "sample_id": "table3_muscle",
            "independent": true,
            "cells": [
              {
                "label": "Combined",
                "value": 0.5611,
                "sd": 0.0001
              }
            ]
          }
        ],
        "decimals_mean": 4,
        "decimals_sd": 4,
        "near_match": true
      },
      "reported": {
        "mw": 0.5611,
        "ci": [
          0.5456,
          0.5766
        ],
        "n1_n2": "10 / 3",
        "p": "<0.0001"
      },
      "computed": {
        "duplicate_groups": 1,
        "matched_pair": [
          0.5611,
          0.0001
        ],
        "chance_probability": 7.160868147053851e-07,
        "table3_component_mw": [
          0.625,
          0.8182
        ],
        "table3_component_n": [
          "16 / 5",
          "11 / 2"
        ]
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "Table 3's headline combined p<0.0001 is the same Combined (Wei-Lachin) row as Table 2, not a combination of Table 3's own muscle rows."
      },
      "notes": "detect_duplication flagged one identical (MW, p) pair across Table 2 and Table 3 Combined rows (coincidence probability about 7.2e-07). Table 3's own components are Muscle Marlene MW=0.6250 N=16/5 and Muscle Catoi MW=0.8182 N=11/2; the pasted combined line keeps Table 2's N1/N2=10/3 and MW=0.5611, which lies below both Table 3 component MWs. Innocent reading: the forest-plot combined row was copied with the Table 2 caption rather than recomputed. Cap remains suspicious under rule 11 (duplication is improbable, not impossible)."
    },
    {
      "id": "table3_p_values_copied_from_table2",
      "location": "Table 3, Muscle Marlene and Muscle Catoi P column",
      "technique": "not_computational",
      "consistent": false,
      "severity": "highly_suspicious",
      "reproduction": "metascience grimu --n1 16 --n2 5 --reported_p 0.4146 --decimals 4 --method both --test_type mann_whitney",
      "quote": "| Muscle Marlene        |                                   | 0,6250 | (0,3993 to 0,8507) | 16 / 5  | 0,4146  |",
      "inputs": {
        "table2_p": [
          0.4146,
          0.4936
        ],
        "table3_p": [
          0.4146,
          0.4936
        ]
      },
      "reported": {
        "muscle_marlene_p": 0.4146,
        "muscle_catoi_p": 0.4936,
        "nntxdiam_p": 0.4146,
        "nntxarea_p": 0.4936
      },
      "computed": {
        "identical_p_pairs": 2,
        "grimu_marlene_16v5": "p=0.4146 matches no U (nearest U=29.5 p=0.409, U=30 p=0.4328)",
        "grimu_catoi_11v2": "p=0.4936 matches no U (nearest U=7 p=0.4897 and 0.5128)"
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": true,
        "claims_affected": 1,
        "explanation": "Table 3 reports both muscle tests non-significant using p-values that belong to different Table 2 rows; Muscle Catoi's own CI (0.5578 to 1.0000) excludes the Mann-Whitney null of 0.5."
      },
      "notes": "The first two p-values in Table 3 are digit-for-digit the first two p-values in Table 2 (0.4146, 0.4936), despite different MW statistics, different CIs, and different group sizes (16/5 and 11/2 versus 10/3). grimu_check found neither p on the lattice for its printed n. Muscle Catoi MW=0.8182 with 95% CI 0.5578\u20131.0000 excludes 0.5, so a correctly paired p would be <0.05; the pasted p=0.4936 does not. Two copied p-values plus the copied combined row is three copied statistics of different tests (rule 11)."
    },
    {
      "id": "table2_nntxdiam_nntxarea_same_mw_ci_different_p",
      "location": "Table 2, NNTXDIAM and NNTXAREA rows",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience check-ci --estimate 0.4000 --ci-low 0.0704 --ci-high 0.7296 --measure md --null-value 0.5 --decimals 4",
      "quote": "| NNTXDIAM                     |                                   | 0,4000 | (0,0704 to 0,7296) | 10 / 3  | 0,4146  |",
      "inputs": {
        "mw": 0.4,
        "ci": [
          0.0704,
          0.7296
        ],
        "n1": 10,
        "n2": 3,
        "p_diam": 0.4146,
        "p_area": 0.4936
      },
      "reported": {
        "nntxdiam_p": 0.4146,
        "nntxarea_p": 0.4936,
        "shared_mw": 0.4,
        "shared_ci": "(0,0704 to 0,7296)"
      },
      "computed": {
        "check_estimate_ci_wald_p_from_shared_ci": 0.5521
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "Both component tests remain non-significant under either printed p; the contradiction is internal reporting, not a flipped claim."
      },
      "notes": "NNTXDIAM and NNTXAREA print the same MW (0.4000), the same 95% CI to four decimals, and the same N1/N2=10/3, but different p-values (0.4146 vs 0.4936). For an untied Mann-Whitney test, U = MW\u00d7n1\u00d7n2 is the same number, so the p must be the same. Different tie corrections could split the p-values; they would not be expected to produce identical confidence intervals to four decimals. check_estimate_ci recovers p\u22480.552 from the shared Wald interval (null 0.5), which matches neither printed p. Severity stays suspicious because ties are a possible innocent split of the p column."
    },
    {
      "id": "table2_nntxmax_ci_excludes_null",
      "location": "Table 2, NNTXMAX row",
      "technique": "check_estimate_ci",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience check-ci --estimate 0.8000 --ci-low 0.5362 --ci-high 1.0000 --measure md --reported-p 0.9017 --reported-p-operator = --null-value 0.5 --decimals 4 --confidence-level 0.95",
      "quote": "| NNTXMAX                      |                                   | 0,8000 | (0,5362 to 1,0000) | 10 / 3  | 0,9017  |",
      "inputs": {
        "estimate": 0.8,
        "ci_low": 0.5362,
        "ci_high": 1.0,
        "measure": "md",
        "reported_p": 0.9017,
        "reported_p_operator": "=",
        "null_value": 0.5,
        "decimals": 4,
        "confidence_level": 0.95
      },
      "reported": {
        "mw": 0.8,
        "ci": [
          0.5362,
          1.0
        ],
        "p": 0.9017,
        "n1_n2": "10 / 3"
      },
      "computed": {
        "recovered_p": 0.011227760363422767,
        "recovered_se": 0.11831850066082725,
        "ci_excludes_null": true,
        "implied_centre": 0.7681
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": true,
        "claims_affected": 1,
        "explanation": "The printed 95% CI excludes the Mann-Whitney null of 0.5, so this component would be significant at alpha=0.05, but the printed p=0.9017 is not."
      },
      "notes": "Tool verdict suspicious: the CI excludes the null (0.5) while p=0.9017 says non-significant. The upper bound is truncated at 1.0000, so the Wald recovered p (0.0112) and implied centre (0.7681) are not trustworthy as point recoveries; the lower bound 0.5362>0.5 does not depend on that Wald inversion. Methods print two-sided 95% CIs. grimu_check: p=0.9017 matches no U for 10v3 (nearest U=13.5 p=0.8658, U=14 p=0.9326), which is the p of a near-null U, not of MW=0.8000 (U=24)."
    },
    {
      "id": "table3_catoi_ci_excludes_null",
      "location": "Table 3, Muscle Catoi row",
      "technique": "check_estimate_ci",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience check-ci --estimate 0.8182 --ci-low 0.5578 --ci-high 1.0000 --measure md --reported-p 0.4936 --reported-p-operator = --null-value 0.5 --decimals 4 --confidence-level 0.95",
      "quote": "| Muscle Catoi          |                                   | 0,8182 | (0,5578 to 1,0000) | 11 / 2  | 0,4936  |",
      "inputs": {
        "estimate": 0.8182,
        "ci_low": 0.5578,
        "ci_high": 1.0,
        "measure": "md",
        "reported_p": 0.4936,
        "reported_p_operator": "=",
        "null_value": 0.5,
        "decimals": 4,
        "confidence_level": 0.95
      },
      "reported": {
        "mw": 0.8182,
        "ci": [
          0.5578,
          1.0
        ],
        "p": 0.4936,
        "n1_n2": "11 / 2"
      },
      "computed": {
        "recovered_p": 0.004791644595675937,
        "ci_excludes_null": true
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": true,
        "claims_affected": 1,
        "explanation": "Muscle Catoi's interval excludes 0.5 while the printed p=0.4936 (the same digits as Table 2 NNTXAREA) is non-significant."
      },
      "notes": "Same CI-versus-p contradiction as NNTXMAX, and the p is the copied Table 2 NNTXAREA value. Upper bound truncated at 1.0000, so Wald p=0.0048 is only supportive; the printed lower bound 0.5578>0.5 already excludes the null. This is the same cell as the p-copy finding; both are recorded so the interval contradiction is visible even if the copy-paste reading is rejected."
    },
    {
      "id": "table2_nntxtotal_p_vs_ci",
      "location": "Table 2, NNTXTOTAL row",
      "technique": "check_estimate_ci",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience check-ci --estimate 0.5667 --ci-low 0.2855 --ci-high 0.8479 --measure md --reported-p 0.2347 --reported-p-operator = --null-value 0.5 --decimals 4 --confidence-level 0.95",
      "quote": "| NNTXTOTAL                    |                                   | 0,5667 | (0,2855 to 0,8479) | 10 / 3  | 0,2347  |",
      "inputs": {
        "estimate": 0.5667,
        "ci_low": 0.2855,
        "ci_high": 0.8479,
        "measure": "md",
        "reported_p": 0.2347,
        "reported_p_operator": "=",
        "null_value": 0.5,
        "decimals": 4
      },
      "reported": {
        "mw": 0.5667,
        "ci": [
          0.2855,
          0.8479
        ],
        "p": 0.2347
      },
      "computed": {
        "recovered_p": 0.6420037893046435,
        "recovered_se": 0.14347202408721269,
        "implied_centre": 0.5667,
        "ci_excludes_null": false
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "Both the interval and the printed p are non-significant; they simply do not agree with each other."
      },
      "notes": "Unlike NNTXMAX/NNTXMIN/NNTXMYELIN, this interval is not truncated at 0 or 1 and is symmetric about the printed MW, so the Wald caveat does not apply. Recovered p from the CI is 0.642; reported p is 0.2347. Mann-Whitney exact p can differ from Wald, but not by this much at n=10/3. grimu_check: p=0.2347 matches no 10v3 U (nearest U=7 p=0.2168, U=7.5 p=0.2367)."
    },
    {
      "id": "table2_grimu_all_component_p_miss_lattice",
      "location": "Table 2, P column, eight component rows",
      "technique": "grimu_coexistence",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience grimu-coexist --n1 10 --n2 3 --p-values 0.4146,0.4936,0.1928,0.1020,0.7533,0.9017,0.2347,0.3505 --decimals 4 --method both --test-type mann_whitney --p-source unspecified --ties-possible false",
      "quote": "| NNTXDIAM                     |                                   | 0,4000 | (0,0704 to 0,7296) | 10 / 3  | 0,4146  |",
      "inputs": {
        "n1": 10,
        "n2": 3,
        "p_values": [
          0.4146,
          0.4936,
          0.1928,
          0.102,
          0.7533,
          0.9017,
          0.2347,
          0.3505
        ],
        "decimals": 4,
        "method": "both",
        "one_sided": false,
        "test_type": "mann_whitney",
        "p_source": "unspecified",
        "ties_possible": false
      },
      "reported": {
        "p_values": [
          0.4146,
          0.4936,
          0.1928,
          0.102,
          0.7533,
          0.9017,
          0.2347,
          0.3505
        ],
        "n1_n2": "10 / 3"
      },
      "computed": {
        "n_flagged": 8,
        "n_coexistence_violations": 0,
        "floor_p_exact": 0.006993006993006993,
        "n_achievable_p": 45
      },
      "consequence": {
        "basis": "computed",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "All eight component p-values remain non-significant; the lattice misses do not flip the paper's NS calls, but they mean these digits are not Mann-Whitney p-values for 10v3."
      },
      "notes": "Paper attributes these p-values to the Wilcoxon-Mann-Whitney / Wei-Lachin family with printed group sizes 10/3. grimu_coexistence: 8 of 8 p-values are individually flagged (none match an achievable U under normal, continuity-corrected, or exact conventions); no pairwise co-existence violation among them. Rule 12 caps granularity misses at suspicious and forbids highly_suspicious on granularity alone; co-occurrence of all eight is why the family is reported together. Directional (one-sided) re-run of p=0.4146 also missed. If the histometric outcomes are small-integer/ordinal with ties, the granularity branch would refuse (demonstrated for NNTXAXON with ties_possible=true \u2192 indeterminate). Diameter/area/myelin named as continuous histometrics, so ties_possible=false is the default for those rows. Combined p<0.0001 was not entered here because it is a multivariate Wei-Lachin p, not a rank-sum p."
    },
    {
      "id": "weillachin_combined_ci_implausibly_tight",
      "location": "Table 2, Combined (Wei-Lachin) row",
      "technique": "no_tool_exists",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience check-ci --estimate 0.5611 --ci-low 0.5456 --ci-high 0.5766 --measure md --reported-p 0.0001 --reported-p-operator < --null-value 0.5 --decimals 4",
      "quote": "The combined result of the histological assessments shows significant superiority of the 'stimulus yes' group of animals versus the 'stimulus no' group (MW=0.5611, 95%CI 0.5456-0.5766, Wei-Lachin procedure, directional test, exploratory interpretation.",
      "inputs": {
        "estimate": 0.5611,
        "ci_low": 0.5456,
        "ci_high": 0.5766,
        "n1_n2": "10 / 3"
      },
      "reported": {
        "mw": 0.5611,
        "ci": [
          0.5456,
          0.5766
        ],
        "p": "<0.0001",
        "n1_n2": "10 / 3"
      },
      "computed": {
        "check_estimate_ci_combined_recovered_se": 0.007908308582332144,
        "check_estimate_ci_combined_recovered_p": 1.1102230246251565e-14,
        "check_estimate_ci_combined_recovered_z": 7.726051577767566,
        "check_estimate_ci_nntxdiam_recovered_se": 0.16816635540236594,
        "method": "Compare Combined recovered SE from check_estimate_ci with the component recovered SE at the same printed N1/N2; Wei-Lachin combined variance cannot be an order of magnitude below every component when outcomes are on the same 13 animals."
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": true,
        "claims_affected": 1,
        "explanation": "The only statistically significant result the paper claims (combined Wei-Lachin p<0.0001) is carried by this interval; if the interval is mis-scaled, that claim is not supported by the component tests, all of which are NS with wide CIs."
      },
      "notes": "check_estimate_ci finds the Combined MW, CI and p<0.0001 internally consistent (midpoint 0.5611, recovered p=1.11e-14). No registered tool checks a Wei-Lachin multivariate SE against its components, so this row is no_tool_exists and capped at suspicious. The same printed N1/N2=10/3 that produces component recovered SEs around 0.13\u20130.17 (NNTXDIAM recovered_se=0.168) is attached to a combined recovered_se=0.0079. Independent averaging of eight outcomes would shrink SE by about sqrt(8), not by a factor of twenty, and positive within-animal correlation would shrink it less, not more. All eight component 95% CIs include 0.5 (except NNTXMAX, whose p is internally contradictory). stalt_check on the recovered p versus '<0.0001' is consistent (APA-style floor)."
    },
    {
      "id": "second_op_n_abstract_vs_results",
      "location": "Abstract versus Results, Surgery",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience summation --values 21 --expected-sum 16 --decimals 0 --tolerance 0",
      "quote": "2nd Op at day 90 (16 surviving rats) for open proof of reinnervation",
      "inputs": {
        "abstract_n": 16,
        "results_n": 21
      },
      "reported": {
        "abstract_day90": 16,
        "results_2nd_op": 21
      },
      "computed": {
        "difference_abstract_minus_results": -5
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": null,
        "explanation": "The analysed n for CMAP and for the Wei-Lachin tables cannot be read off a single printed flow."
      },
      "notes": "Abstract: 16 surviving rats at the day-90 2nd Op. Results: '21 rats underwent the 2 nd Op for transplant revision'. Early-death addends in Results (2+1 on day 0, then 1, 1, 1, 2, 1) sum to 9, and 30\u22129=21, so the Results cascade is internally additive (check_summation_batch). The abstract 16 is not that cascade. Figure 4 uses 8 of 16; Figure 12 caption uses 7 of 14."
    },
    {
      "id": "cmap_positive_count_conflict",
      "location": "Abstract; Results; Figure 4 caption; Figure 12 caption; Table 4",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience summation --values 7,10 --expected-sum 17 --decimals 0 --tolerance 0",
      "quote": "Eight rats showed positive CMAPs.",
      "inputs": {
        "abstract_positive": 8,
        "figure4": "8 of 16",
        "figure12": "7 out of the 14",
        "table4_plus_rows": 7,
        "table4_minus_rows": 10
      },
      "reported": {
        "abstract": 8,
        "results_of_21": 8,
        "figure4": "8 of 16",
        "figure12": "7 out of the 14 surviving animals",
        "table4_positive_cases": [
          "5",
          "6",
          "10",
          "13",
          "19",
          "21",
          "28"
        ]
      },
      "computed": {
        "table4_n_plus": 7,
        "table4_n_minus": 10,
        "table4_total": 17
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "Stimulus yes versus no is the grouping for the paper's only significant test, but the paper never pins down how many animals were yes."
      },
      "notes": "Positive CMAP/EMG counts printed as 8 (abstract; Results 'positive in only 8 rats'; Figure 4 '8 of 16 rats') versus 7 (Figure 12 '7 out of the 14 surviving animals'; Table 4 lists seven (+) cases and ten (\u2212) cases). Table 4's 17 rows also exceed both 15 completers and the abstract's 16 at day 90; tissues from animals that died at the 2nd Op (No 21, 28) are said to have been saved, which can explain extras, but not the 8 versus 7 split. Table 2's N1/N2=10/3 matches none of 8 vs 8, 8 vs 13, 7 vs 10, or 16 vs 5."
    },
    {
      "id": "vecuronium_dose_table1_vs_figure5",
      "location": "Table 1 Vecuronium row versus Figure 5 caption",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience check-ratio --numerator 80 --denominator 1000 --reported-ratio 0.08 --decimals-numerator 0 --decimals-denominator 0 --decimals-ratio 2",
      "quote": "Vecuronium \u00ae IV (80 \u00b5g/kg) application during artificial ventilation",
      "inputs": {
        "table1_mg_per_kg": [
          0.04,
          0.05
        ],
        "figure5_ug_per_kg": 80
      },
      "reported": {
        "table1": "0.04 - 0.05 mg/kg",
        "figure5": "80 \u00b5g/kg"
      },
      "computed": {
        "ug_per_kg_equivalent_of_table1": [
          40,
          50
        ],
        "figure5_as_mg_per_kg": 0.08
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": 1,
        "explanation": "Vecuronium response is the functional proof offered for mixed cholinergic/glutamatergic transmission; the dose used is not a single printed number."
      },
      "notes": "Table 1 lists Vecuronium 0.04\u20130.05 mg/kg IV. Figure 5 caption lists 80 \u00b5g/kg, which is 0.08 mg/kg, outside that range. Four CMAP-positive rats received it. No arithmetic tool is missing: the two printed doses are different quantities."
    },
    {
      "id": "angiogenesis_score_prose_vs_table4",
      "location": "Figure 9 caption versus Table 4, case 6 ang cell",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "reproduction": "metascience check-ratio --numerator 13 --denominator 10 --reported-ratio 1.3 --decimals-numerator 0 --decimals-denominator 0 --decimals-ratio 1",
      "quote": "was more intense in EMG-positive cases (individual final scores of 2 and 3; score average 2.57) than in EMG-negative cases (individual final scores of 1 and 2; score average 1.3)",
      "inputs": {
        "prose_positive_scores": [
          2,
          3
        ],
        "table4_case6_ang": 1
      },
      "reported": {
        "positive_average": 2.57,
        "negative_average": 1.3
      },
      "computed": {
        "check_ratio_negative_1_3": "consistent from Table 4 ang scores 2,1,1,1,2,2,1,1,1,1 summing to 13 over 10 cases"
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": false,
        "claims_affected": 0,
        "explanation": "A descriptive contrast of angiogenesis by EMG group, not a hypothesis test."
      },
      "notes": "EMG-negative average 1.3 reproduces from Table 4 ang grades (check_ratio 13/10=1.3). EMG-positive prose says individual scores were only 2 and 3, but Table 4 case 6 (+) lists ang (1). Case 28 (+) has no ang grade printed. No combination of the printed positive ang grades (2, 1, 3, 3, 2, 3) averages to 2.57."
    },
    {
      "id": "two_sided_methods_vs_directional_caption",
      "location": "Statistical Methods versus Table 2 caption",
      "technique": "not_computational",
      "consistent": false,
      "severity": "indeterminate",
      "reproduction": "metascience grimu --n1 10 --n2 3 --reported_p 0.4146 --decimals 4 --one_sided true --method both --test_type mann_whitney",
      "quote": "The level of alpha was defined as alpha=0.05, and a two-sided test was used for superiority.",
      "inputs": {
        "methods": "two-sided",
        "caption": "directional test"
      },
      "reported": {
        "alpha": 0.05,
        "methods_tails": "two-sided",
        "caption": "directional test, exploratory interpretation"
      },
      "computed": {
        "one_sided_grimu_p_4146": "still unmatched"
      },
      "consequence": {
        "basis": "asserted",
        "flips_significance": null,
        "claims_affected": null,
        "explanation": "Which tail convention was used is not recoverable from the printed p-values, which miss both the two-sided and one-sided 10v3 lattices."
      },
      "notes": "Methods: two-sided test for superiority and two-sided 95% CIs. Table 2/3 captions: 'directional test, exploratory interpretation.' Both cannot be the procedure that produced the p column. Recorded as indeterminate because the paper also labels the analysis exploratory and warns about small n; the tail contradiction is a reporting defect, not a number that can be rerun."
    },
    {
      "id": "table2_group_arm_sums",
      "location": "Methods, group assignment and Results completers",
      "technique": "check_summation_batch",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience summation-batch",
      "quote": "they were 12 Cere (verum), 11 NaCl (placebo) well randomized, and 7 controls (nil)",
      "inputs": {
        "rows": [
          {
            "values": [
              12,
              11,
              7
            ],
            "expected_sum": 30,
            "decimals": [
              0,
              0,
              0
            ],
            "tolerance": 0
          },
          {
            "values": [
              5,
              7,
              3
            ],
            "expected_sum": 15,
            "decimals": [
              0,
              0,
              0
            ],
            "tolerance": 0
          },
          {
            "values": [
              2,
              1,
              1,
              1,
              1,
              2,
              1
            ],
            "expected_sum": 9,
            "decimals": [
              0,
              0,
              0,
              0,
              0,
              0,
              0
            ],
            "tolerance": 0
          },
          {
            "values": [
              4,
              2
            ],
            "expected_sum": 6,
            "decimals": [
              0,
              0
            ],
            "tolerance": 0
          }
        ]
      },
      "reported": {
        "randomized": {
          "CERE": 12,
          "NaCl": 11,
          "controls": 7
        },
        "completed": {
          "CERE": 5,
          "NaCl": 7,
          "controls": 3
        }
      },
      "computed": {
        "n_evaluated": 5,
        "n_inconsistent": 0
      },
      "notes": "12+11+7=30; completers 5+7+3=15; early-death addends 9; 2nd-Op deaths 4+2=6. These identities hold. They do not reconcile the abstract's 16 at day 90 with Results' 21 at 2nd Op."
    },
    {
      "id": "mortality_50_percent",
      "location": "Results, Surgery",
      "technique": "check_count_percent",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-count-percent --count 15 --percentage 50 --n 30 --decimals 0",
      "quote": "the overall mortality of 50% was still high",
      "inputs": {
        "count": 15,
        "percentage": 50,
        "n": 30,
        "decimals": 0
      },
      "reported": {
        "percentage": 50,
        "enrolled": 30,
        "completed": 15
      },
      "computed": {
        "computed_percentage": 50.0,
        "implied_denominator": 30.0
      },
      "notes": "15 deaths among 30 enrolled prints as 50%. Results also mention 14 unexplained deaths plus one surgical failure (No 4), which is the same 15."
    },
    {
      "id": "table2_table3_estimate_in_ci",
      "location": "Table 2 and Table 3, MW (95% CI) cells",
      "technique": "check_estimate_ci",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-table",
      "quote": "The combined result of the histological assessments shows significant superiority of the 'stimulus yes' group of animals versus the 'stimulus no' group (MW=0.5611, 95%CI 0.5456-0.5766, Wei-Lachin procedure, directional test, exploratory interpretation.",
      "inputs": {
        "n_cells": 11,
        "n_checks_run": 11
      },
      "reported": {
        "kind_counts": {
          "estimate_ci": 11
        }
      },
      "computed": {
        "n_checks_run": 11,
        "summary_by_severity": {
          "consistent": 11
        },
        "note": "check_table ran estimate-in-CI only, without the p column; p-versus-CI mismatches are the separate check_estimate_ci findings."
      },
      "notes": "All 11 printed MW point estimates lie inside their printed 95% CIs (check_table, 11/11). Combined MW=0.5611 is the midpoint of 0.5456\u20130.5766. This is containment only; it does not license the p column."
    },
    {
      "id": "combined_weillachin_estimate_ci_p_internally_consistent",
      "location": "Table 2, Combined (Wei-Lachin) row",
      "technique": "check_estimate_ci",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-ci --estimate 0.5611 --ci-low 0.5456 --ci-high 0.5766 --measure md --reported-p 0.0001 --reported-p-operator < --null-value 0.5 --decimals 4",
      "quote": "| Combined (Wei-Lachin)        |                                   | 0,5611 | (0,5456 to 0,5766) | 10 / 3  | <0.0001 |",
      "inputs": {
        "estimate": 0.5611,
        "ci_low": 0.5456,
        "ci_high": 0.5766,
        "measure": "md",
        "reported_p": 0.0001,
        "reported_p_operator": "<",
        "null_value": 0.5,
        "decimals": 4
      },
      "reported": {
        "mw": 0.5611,
        "ci": [
          0.5456,
          0.5766
        ],
        "p": "<0.0001"
      },
      "computed": {
        "recovered_p": 1.1102230246251565e-14,
        "recovered_se": 0.007908308582332144,
        "ci_excludes_null": true
      },
      "notes": "The Combined estimate, interval and p<0.0001 are mutually consistent on a Wald reading. stalt_check treats p=1.11e-14 behind '<0.0001' as correct APA-style flooring, not a hidden extreme p. The separate no_tool_exists finding is about whether this interval can come from n=10/3 given the component intervals."
    },
    {
      "id": "emg_negative_angiogenesis_mean_1_3",
      "location": "Figure 9 caption and Table 4 ang grades for EMG-negative cases",
      "technique": "check_ratio",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-ratio --numerator 13 --denominator 10 --reported-ratio 1.3 --decimals-numerator 0 --decimals-denominator 0 --decimals-ratio 1",
      "quote": "than in EMG-negative cases (individual final scores of 1 and 2; score average 1.3)",
      "inputs": {
        "numerator": 13,
        "denominator": 10,
        "reported_ratio": 1.3,
        "decimals_numerator": 0,
        "decimals_denominator": 0,
        "decimals_ratio": 1
      },
      "reported": {
        "average": 1.3
      },
      "computed": {
        "computed_ratio": 1.3
      },
      "notes": "Table 4 EMG-negative ang grades 2,1,1,1,2,2,1,1,1,1 sum to 13; 13/10=1.3. Individual scores are only 1 and 2, as the caption states."
    },
    {
      "id": "mw_statistic_bounds",
      "location": "Table 2, Combined MW",
      "technique": "check_statistic_bounds",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience check-bounds --value 0.5611 --measure auc --extraction-verified true",
      "quote": "MW=0.5611, 95%CI 0.5456-0.5766",
      "inputs": {
        "value": 0.5611,
        "measure": "auc",
        "extraction_verified": true
      },
      "reported": {
        "mw": 0.5611
      },
      "computed": {
        "bound": [
          0.0,
          1.0
        ]
      },
      "notes": "Mann-Whitney effect size treated as an AUC-like probability in [0,1]. 0.5611 is inside the bound, as are the other printed MW values."
    },
    {
      "id": "stalt_combined_threshold",
      "location": "Table 2, Combined p<0.0001",
      "technique": "stalt_check",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience stalt --calculated-p 1.1102230246251565e-14 --reported-threshold <0.0001",
      "quote": "| Combined (Wei-Lachin)        |                                   | 0,5611 | (0,5456 to 0,5766) | 10 / 3  | <0.0001 |",
      "inputs": {
        "calculated_p": 1.1102230246251565e-14,
        "reported_threshold": "<0.0001"
      },
      "reported": {
        "p": "<0.0001"
      },
      "computed": {
        "bound_satisfied": true,
        "orders_of_magnitude_smaller": 9.954589770191003
      },
      "notes": "Tool: a p many orders below '<0.0001' is what the threshold notation is for (APA floor), not a STALT hit. The recovered p itself comes from the Combined CI, whose width is the separate tightness finding."
    },
    {
      "id": "statcheck_no_apa_stats",
      "location": "Full PDF text",
      "technique": "statcheck",
      "consistent": true,
      "severity": "indeterminate",
      "reproduction": "metascience statcheck --pdf-path cerebrolysin_rat_sci.pdf",
      "quote": "The combined result of the histological assessments shows significant superiority of the 'stimulus yes' group of animals versus the 'stimulus no' group (MW=0.5611, 95%CI 0.5456-0.5766, Wei-Lachin procedure, directional test, exploratory interpretation.",
      "inputs": {
        "pdf_path": "/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/cerebrolysin_flow/paper/cerebrolysin_rat_sci.pdf"
      },
      "reported": {
        "apa_nhst_count": 0
      },
      "computed": {
        "stats_found": 0
      },
      "notes": "statcheck found no APA-form t/F/r/chi2/z statistics. The paper reports Mann-Whitney / Wei-Lachin MW, CI and p, which that scanner does not parse. Coverage gap of format, not a clean NHST audit."
    },
    {
      "id": "multiplicity_table2_components",
      "location": "Table 2, eight component tests",
      "technique": "multiplicity_report",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience multiplicity --family-label Table 2 individual Mann-Whitney histometric outcomes --alpha 0.05",
      "quote": "An adjustment for multiplicity was not performed due to the exploratory character of the study.",
      "inputs": {
        "n_tests": 8,
        "alpha": 0.05,
        "correction": "none"
      },
      "reported": {
        "n_significant_uncorrected": 0
      },
      "computed": {
        "fwer_if_independent": 0.3366,
        "n_surviving_floor": 0,
        "n_surviving_ceiling": 0,
        "n_claims_lost_to_correction": 0
      },
      "notes": "Authors state no multiplicity adjustment because the study is exploratory. None of the eight uncorrected component p-values is <0.05, so correction would not retire a component claim. The Combined p<0.0001 is a single multivariate test, not part of this family."
    },
    {
      "id": "flag_round_n_sample_sizes",
      "location": "Methods and Results sample sizes",
      "technique": "flag_round_n",
      "consistent": true,
      "severity": "consistent",
      "reproduction": "metascience flag-round-n --ns 30,12,11,7,16,15,21",
      "quote": "Randomization was for 30 animals",
      "inputs": {
        "ns": [
          30,
          12,
          11,
          7,
          16,
          15,
          21
        ]
      },
      "reported": {
        "ns": [
          30,
          12,
          11,
          7,
          16,
          15,
          21
        ]
      },
      "computed": {
        "all_divisible_by_moderate": false
      },
      "notes": "Ethics-capped n=30 with uneven arms 12/11/7 and irregular survivorship. No round-N flag."
    }
  ],
  "coverage": {
    "stats_found": 72,
    "tools_run": [
      "extract_pdf",
      "statcheck",
      "check_estimate_ci",
      "grimu_check",
      "grimu_coexistence",
      "check_summation_batch",
      "check_count_percent",
      "stalt_check",
      "multiplicity_report",
      "parse_table",
      "parse_cells_typed",
      "check_table",
      "detect_duplication",
      "check_ratio",
      "check_statistic_bounds",
      "absence_of_evidence",
      "required_n",
      "flag_round_n"
    ],
    "tables_checked": [
      "Table 1",
      "Table 2",
      "Table 3",
      "Table 4"
    ],
    "stats_checked": 58
  },
  "anatomy": {
    "studies": [
      {
        "id": "s1",
        "label": "Rat T10 sural-nerve-graft RCT, Cerebrolysin vs NaCl vs nil",
        "design": "rct",
        "n": 30,
        "unit_of_analysis": "rat",
        "clustered": false,
        "preregistered": false,
        "n_per_group": [
          {
            "label": "Cerebrolysin",
            "n": 12
          },
          {
            "label": "NaCl sham",
            "n": 11
          },
          {
            "label": "controls nil",
            "n": 7
          }
        ],
        "sample_flow": [
          {
            "stage": "sanctioned / randomized",
            "n": 30,
            "reason": "30 adult white female Sprague Dawley rats; coin-flip for two treatment groups plus identified controls"
          },
          {
            "stage": "2nd Op day 90 (Results text)",
            "n": 21,
            "reason": "nine early deaths before revision"
          },
          {
            "stage": "2nd Op day 90 (Abstract)",
            "n": 16,
            "reason": "abstract reports 16 surviving rats; conflicts with Results 21"
          },
          {
            "stage": "completed 100 days / 3rd Op",
            "n": 15,
            "reason": "5 CERE, 7 NaCl, 3 controls; tissues from some 2nd-Op deaths also examined"
          }
        ]
      }
    ],
    "variables": [
      {
        "id": "group",
        "name": "treatment group",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "nominal_category",
        "confidence": "high",
        "n_categories": 3,
        "levels": [
          "Cerebrolysin (CERE)",
          "NaCl 0.9% sham",
          "controls (nil)"
        ],
        "derivation": "measured",
        "derived_from": "coin-flip randomization plus identified controls, unblinded years later as 12/11/7"
      },
      {
        "id": "cmap_positive",
        "name": "compound muscle action potential present at 2nd Op",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "confidence": "high",
        "n_categories": 2,
        "levels": [
          "positive (stimulus yes)",
          "negative (stimulus no)"
        ],
        "derivation": "measured",
        "derived_from": "intraoperative CMAP of IOAM / PNG"
      },
      {
        "id": "mw_histometric",
        "name": "Mann-Whitney effect size on histometric nerve measures",
        "measurement_level": "interval",
        "discreteness": "continuous",
        "family": "proportion",
        "confidence": "medium",
        "lower_bound": 0,
        "upper_bound": 1,
        "units": "P(X<Y)+0.5P(X=Y)",
        "derivation": "other",
        "derived_from": "Wei-Lachin / Wilcoxon-Mann-Whitney on NNTXDIAM, AREA, AXON, MYELIN, MIN, MAX, TOTAL, CUMUL"
      },
      {
        "id": "muscle_fiber_diameter",
        "name": "IOAM muscle fibre diameter",
        "measurement_level": "ratio",
        "discreteness": "continuous",
        "family": "continuous",
        "confidence": "high",
        "units": "\u00b5m, also as percent of contralateral",
        "derivation": "measured",
        "derived_from": "histometric count by ML (Luebeck) and CC (Cluj)"
      },
      {
        "id": "axon_regen_score",
        "name": "axonal regeneration/sprouting grade",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "ordinal_category",
        "confidence": "high",
        "lower_bound": 0,
        "upper_bound": 3,
        "n_categories": 4,
        "levels": [
          "0 none",
          "1 mild (1-20 axons/HPF)",
          "2 moderate (21-50)",
          "3 intense (>50)"
        ],
        "derivation": "mean_of_items",
        "derived_from": "mean over at least 10 HPF from serial slides"
      },
      {
        "id": "ang_score",
        "name": "angiogenesis grade in/around SNG",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "ordinal_category",
        "confidence": "high",
        "lower_bound": 0,
        "upper_bound": 3,
        "n_categories": 4,
        "levels": [
          "0 none",
          "1 mild (1 microvessel/HPF)",
          "2 moderate (2-3)",
          "3 intense (>3)"
        ],
        "derivation": "mean_of_items",
        "derived_from": "mean over HPF"
      },
      {
        "id": "gc_score",
        "name": "Gitter cell grade",
        "measurement_level": "ordinal",
        "discreteness": "discrete",
        "family": "ordinal_category",
        "confidence": "high",
        "lower_bound": 0,
        "upper_bound": 3,
        "n_categories": 4,
        "derivation": "mean_of_items",
        "derived_from": "mean Gc/HPF"
      },
      {
        "id": "sng_depth",
        "name": "nerve-graft insertion depth",
        "measurement_level": "ratio",
        "discreteness": "continuous",
        "family": "continuous",
        "confidence": "high",
        "units": "mm",
        "derivation": "measured",
        "derived_from": "histology of SNG position"
      },
      {
        "id": "body_weight",
        "name": "body weight at enrolment",
        "measurement_level": "ratio",
        "discreteness": "continuous",
        "family": "continuous",
        "confidence": "high",
        "lower_bound": 220,
        "upper_bound": 280,
        "units": "g",
        "derivation": "measured",
        "derived_from": "Charles River Sprague Dawley, 220 to 280 g"
      },
      {
        "id": "fb_positive",
        "name": "Fast Blue labelled spinal neurons",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "count",
        "confidence": "high",
        "derivation": "measured",
        "derived_from": "fluorescence microscopy of SC sections"
      }
    ],
    "tests": [
      {
        "id": "t2_nntxdiam",
        "test_type": "mann_whitney",
        "location": "Table 2, NNTXDIAM",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "mw_histometric",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.4,
        "p_value": 0.4146,
        "p_is_threshold": false,
        "effect_size": "MW = 0.4000",
        "ci": "95% CI 0.0704 to 0.7296",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t2_nntxarea",
        "test_type": "mann_whitney",
        "location": "Table 2, NNTXAREA",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "mw_histometric",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.4,
        "p_value": 0.4936,
        "p_is_threshold": false,
        "effect_size": "MW = 0.4000",
        "ci": "95% CI 0.0704 to 0.7296",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t2_nntxaxon",
        "test_type": "mann_whitney",
        "location": "Table 2, NNTXAXON",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "mw_histometric",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.6667,
        "p_value": 0.1928,
        "p_is_threshold": false,
        "effect_size": "MW = 0.6667",
        "ci": "95% CI 0.3738 to 0.9596",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t2_nntxmyelin",
        "test_type": "mann_whitney",
        "location": "Table 2, NNTXMYELIN",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "mw_histometric",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.7333,
        "p_value": 0.102,
        "p_is_threshold": false,
        "effect_size": "MW = 0.7333",
        "ci": "95% CI 0.4660 to 1.0000",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t2_nntxmin",
        "test_type": "mann_whitney",
        "location": "Table 2, NNTXMIN",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "mw_histometric",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.7667,
        "p_value": 0.7533,
        "p_is_threshold": false,
        "effect_size": "MW = 0.7667",
        "ci": "95% CI 0.4988 to 1.0000",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t2_nntxmax",
        "test_type": "mann_whitney",
        "location": "Table 2, NNTXMAX",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "mw_histometric",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.8,
        "p_value": 0.9017,
        "p_is_threshold": false,
        "effect_size": "MW = 0.8000",
        "ci": "95% CI 0.5362 to 1.0000",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t2_nntxtotal",
        "test_type": "mann_whitney",
        "location": "Table 2, NNTXTOTAL",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "mw_histometric",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.5667,
        "p_value": 0.2347,
        "p_is_threshold": false,
        "effect_size": "MW = 0.5667",
        "ci": "95% CI 0.2855 to 0.8479",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t2_nntxcumul",
        "test_type": "mann_whitney",
        "location": "Table 2, NNTXCUMUL",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "mw_histometric",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.6333,
        "p_value": 0.3505,
        "p_is_threshold": false,
        "effect_size": "MW = 0.6333",
        "ci": "95% CI 0.3476 to 0.9191",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t2_combined",
        "test_type": "other",
        "location": "Table 2, Combined (Wei-Lachin)",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "mw_histometric",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.5611,
        "p_value": 0.0001,
        "p_is_threshold": true,
        "effect_size": "MW = 0.5611",
        "ci": "95% CI 0.5456 to 0.5766",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true
      },
      {
        "id": "t3_marlene",
        "test_type": "mann_whitney",
        "location": "Table 3, Muscle Marlene",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "muscle_fiber_diameter",
        "grouping_var": "cmap_positive",
        "n": 21,
        "statistic_value": 0.625,
        "p_value": 0.4146,
        "p_is_threshold": false,
        "effect_size": "MW = 0.6250",
        "ci": "95% CI 0.3993 to 0.8507",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t3_catoi",
        "test_type": "mann_whitney",
        "location": "Table 3, Muscle Catoi",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "muscle_fiber_diameter",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.8182,
        "p_value": 0.4936,
        "p_is_threshold": false,
        "effect_size": "MW = 0.8182",
        "ci": "95% CI 0.5578 to 1.0000",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": false,
        "is_stated_primary_outcome": false
      },
      {
        "id": "t3_combined",
        "test_type": "other",
        "location": "Table 3, Combined (Wei-Lachin)",
        "confidence": "high",
        "study_id": "s1",
        "hypothesis_id": "h_reinnervation",
        "outcome_var": "muscle_fiber_diameter",
        "grouping_var": "cmap_positive",
        "n": 13,
        "statistic_value": 0.5611,
        "p_value": 0.0001,
        "p_is_threshold": true,
        "effect_size": "MW = 0.5611",
        "ci": "95% CI 0.5456 to 0.5766",
        "correction_applied": "none",
        "appears_in_abstract": false,
        "appears_in_conclusions": true,
        "is_stated_primary_outcome": true
      }
    ],
    "hypotheses": [
      {
        "id": "h_reinnervation",
        "statement": "Graft-induced reinnervation of IOAM via PNG from T10, with cholinergic and glutamatergic co-transmission at the NMJ.",
        "status": "confirmatory",
        "study_id": "s1",
        "appears_in_abstract": true,
        "confidence": "high"
      },
      {
        "id": "h_cerebrolysin",
        "statement": "Postoperative Cerebrolysin produces pharmacological neuromodulation (less fibrosis/scarring, larger muscle fibre diameters) versus NaCl and nil.",
        "status": "confirmatory",
        "study_id": "s1",
        "appears_in_abstract": true,
        "confidence": "high"
      },
      {
        "id": "h_brunelli_switch",
        "statement": "Replication of Brunelli's exclusive glutamatergic neurotransmitter switch at the NMJ.",
        "status": "confirmatory",
        "study_id": "s1",
        "appears_in_abstract": true,
        "confidence": "high"
      }
    ]
  },
  "paper_title": "New Aspects of Graft-induced Central Plasticity and Neuroregeneration at T 10 in a Rat Model",
  "paper_metadata": {
    "authors": "von Wild KRH, Catoi C, Tobias von Wild, Giorgio Brunelli, Dafin Muresanu, Peter Trillenberg, Marc Heidbreder, Laura Farcas, Adrian F Gal, Marian A Taulescu, Alexandru I Gudea, Johannes C Vester, Marlene L\u00f6hnhardt",
    "journal": "Journal of Neurology & Neurophysiology",
    "year": "2017",
    "doi": "10.4172/2155-9562.1000450",
    "study_design": "randomized double-blind placebo-controlled experimental study in rat",
    "corresponding_author": "Klaus RH von Wild",
    "corresponding_email": "kvw@neurosci.de"
  },
  "unchecked": [
    {
      "location": "Figure 12 muscle-fibre-diameter chart",
      "reason": "extract_figures was denied by permission policy; group averages appear only as black squares on the figure and are not printed as numbers in the caption. Values needed for effect-size reconstruction of the CERE versus NaCl/nil contrast are therefore unread.",
      "n_cells": 1
    },
    {
      "location": "CONSORT-style flow",
      "reason": "check_flow_arithmetic was denied by permission policy. Additive identities were checked with check_summation_batch instead; the abstract-versus-results n clash is recorded as not_computational.",
      "n_cells": 1
    },
    {
      "location": "Table 4 axon-diameter mean (range) and axon-count cells",
      "reason": "No registered tool tests whether a printed mean lies inside a printed min\u2013max range, or whether a trailing integer is an axon count versus an area. Fourteen mean (range) cells and the associated counts were not fed to GRIM/SPRITE (continuous \u00b5m).",
      "n_cells": 28
    },
    {
      "location": "CERE versus NaCl/nil muscle-fibre comparison",
      "reason": "Authors say the CERE effect was not statistically significant but show no CI or p for that three-arm contrast. absence_of_evidence needs an interval; the Table 3 CIs are stimulus yes/no, not treatment arm.",
      "n_cells": 1
    },
    {
      "location": "Western blot Figure 6",
      "reason": "Qualitative band presence/absence; no optical-density means, SDs or n printed.",
      "n_cells": 1
    },
    {
      "location": "Publisher XML / supplements",
      "reason": "No JATS XML and no supplementary data files were in the paper directory. Sweep used extract_pdf plus body.md. Table 1 is a drug-list, not a results table.",
      "n_cells": 0
    },
    {
      "location": "Wei-Lachin combined SE versus components",
      "reason": "No registered tool reconstructs a Wei-Lachin multivariate standard error from component MW intervals and a correlation. Recorded as no_tool_exists rather than improvised.",
      "n_cells": 1
    }
  ],
  "figures": [
    {
      "label": "Figure 1",
      "is_data_figure": false,
      "page": 2,
      "caption": "Brunelli's Paradigm 'Graft induced Glutamate Neurotransmitter Switch at the neuromuscular junction (NMJ) of skeletal muscle",
      "n_panels": 1,
      "panels": [
        {
          "chart_type": "schematic",
          "shows": "Sketch of CNS-PNS grafting from lateral descending tracts via sural graft to IOAM nerve near the NMJ."
        }
      ],
      "carries_unique_values": false
    },
    {
      "label": "Figure 2",
      "is_data_figure": false,
      "page": 2,
      "caption": "First operation the grafting procedure (prone position): 3rd step microsurgical Identification of the skeletal nerve of right internal obliquus abdominal muscle (IOAM)",
      "n_panels": 3,
      "panels": [
        {
          "chart_type": "photograph",
          "panel": "Left",
          "shows": "Paravertebral incision and IOAM nerve."
        },
        {
          "chart_type": "photograph",
          "panel": "Middle",
          "shows": "Bipolar identification of the nerve; CMAPs at 2 mA and 3 mA."
        },
        {
          "chart_type": "photograph",
          "panel": "Right",
          "shows": "Nerve next to NMJ before bisection."
        }
      ],
      "carries_unique_values": false
    },
    {
      "label": "Figure 3",
      "is_data_figure": false,
      "page": 3,
      "caption": "2nd Op 3 months after grafting procedure (prone position): Revision of the transplant, proof of functional muscle reinnervation and type of neurotransmission/ reinnervation",
      "n_panels": 3,
      "panels": [
        {
          "chart_type": "photograph",
          "shows": "Re-exploration of transplant in rat No 28 CERE."
        }
      ],
      "carries_unique_values": false
    },
    {
      "label": "Figure 4",
      "is_data_figure": true,
      "page": 6,
      "caption": "Compound muscle action potential CMAP during bipolar IOAM electro-stimulation (Positive amplitudes demonstrate IOAM re-innervation, as it was the case in 8 of 16 rats t3 months after the grafting procedure.",
      "n_panels": 1,
      "panels": [
        {
          "chart_type": "line",
          "shows": "CMAP waveform versus time in msec."
        }
      ],
      "carries_unique_values": true,
      "error_bars": ""
    },
    {
      "label": "Figure 5",
      "is_data_figure": true,
      "page": 6,
      "caption": "Vecuronium application shows mixed cholinergic/glutamatergic neuromuscular reinnervation (Vecuronium \u00ae IV (80 \u00b5g/kg)",
      "n_panels": 1,
      "panels": [
        {
          "chart_type": "line",
          "shows": "CMAP amplitude versus time after Vecuronium in rat No. 21 CERE."
        }
      ],
      "carries_unique_values": true
    },
    {
      "label": "Figure 6",
      "is_data_figure": true,
      "page": 6,
      "caption": "Western Blot: Detection for VGlu 1 transporter in the re-innervated muscle endplates",
      "n_panels": 1,
      "panels": [
        {
          "chart_type": "other",
          "shows": "Western blot lanes for VGluT1 in CMAP-positive and CMAP-negative muscles."
        }
      ],
      "carries_unique_values": true
    },
    {
      "label": "Figure 7",
      "is_data_figure": true,
      "page": 7,
      "caption": "Synopsis graft- positioning by histology- morphology analysis inside the SC at T 10",
      "n_panels": 1,
      "panels": [
        {
          "chart_type": "schematic",
          "shows": "SNG position (grey shapes) in each examined cord, with depth and angle ranges."
        }
      ],
      "carries_unique_values": true
    },
    {
      "label": "Figure 8",
      "is_data_figure": false,
      "page": 9,
      "caption": "Graft induced neuroregeneration in histology- morphology (No 10, CERE).",
      "n_panels": 3,
      "panels": [
        {
          "chart_type": "photograph",
          "panel": "A",
          "shows": "Scoring-system illustration."
        },
        {
          "chart_type": "photograph",
          "panel": "B",
          "shows": "SNG in ventral horn, case 10."
        },
        {
          "chart_type": "photograph",
          "panel": "C",
          "shows": "Axon regeneration overview, case 10."
        }
      ],
      "carries_unique_values": false
    },
    {
      "label": "Figure 9",
      "is_data_figure": false,
      "page": 10,
      "caption": "Detailed histological findings related to SNG regeneration at T 10 (No10 CERE)",
      "n_panels": 6,
      "panels": [
        {
          "chart_type": "photograph",
          "shows": "H&E panels of axon growth, Schwann cells, angiogenesis."
        }
      ],
      "carries_unique_values": false
    },
    {
      "label": "Figure 10",
      "is_data_figure": false,
      "page": 11,
      "caption": "A (left) No 10 CERE: SNG outside the SC, cross-section: axons with green fluorescence - FITC",
      "n_panels": 3,
      "panels": [
        {
          "chart_type": "photograph",
          "shows": "VGluT2 immunofluorescence in graft and muscle."
        }
      ],
      "carries_unique_values": false
    },
    {
      "label": "Figure 11",
      "is_data_figure": false,
      "page": 11,
      "caption": "FB+ Neurotracer accumulation in different perikaryons of SC",
      "n_panels": 12,
      "panels": [
        {
          "chart_type": "photograph",
          "shows": "Fast Blue labelled neurons in specified laminae and segments."
        }
      ],
      "carries_unique_values": false
    },
    {
      "label": "Figure 12",
      "is_data_figure": true,
      "page": 16,
      "caption": "Histology- Morphology of reinnervated muscle fibers for statistical proof reinnervation Average diameter of fibers in the abdominal oblique internal muscle: emg positive and emg negative cases. The values are given as percentages of the control",
      "n_panels": 1,
      "panels": [
        {
          "chart_type": "bar",
          "shows": "Per-case IOAM fibre diameter as percent of contralateral, EMG-positive versus negative, with group averages as black squares and a CERE-versus-other tendency."
        }
      ],
      "carries_unique_values": true
    }
  ],
  "statistics_register": [
    {
      "source": "abstract",
      "kind": "count",
      "values": {
        "n": 30
      },
      "quote": "Randomized double blind controlled study in rat, which was limited to 30 animals (Charles River, 220 to 280 g).",
      "checkable": {
        "tools": [
          "check_summation_batch",
          "flag_round_n"
        ]
      },
      "id": "abs_n30",
      "location": "Abstract, Methods"
    },
    {
      "source": "abstract",
      "kind": "other",
      "values": {
        "min_g": 220,
        "max_g": 280
      },
      "quote": "limited to 30 animals (Charles River, 220 to 280 g).",
      "checkable": {
        "tools": [
          "check_statistic_bounds"
        ]
      },
      "id": "abs_weight",
      "location": "Abstract"
    },
    {
      "source": "abstract",
      "kind": "count",
      "values": {
        "CERE": 12,
        "NaCl": 11,
        "controls": 7
      },
      "quote": "a) verum Cerebrolysin \u00ae  IP=12-b) shams NaCl 0.9% IP=11, and c) 7 controls (nil).",
      "checkable": {
        "tools": [
          "check_summation_batch"
        ]
      },
      "id": "abs_arms",
      "location": "Abstract"
    },
    {
      "source": "abstract",
      "kind": "count",
      "values": {
        "n": 16
      },
      "quote": "2nd Op at day 90 (16 surviving rats) for open proof of reinnervation",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "abs_n16",
      "location": "Abstract"
    },
    {
      "source": "abstract",
      "kind": "count",
      "values": {
        "n": 15
      },
      "quote": "10 days later, on the 3rd Op N=15, euthanasia and organ fixation were performed.",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "abs_n15",
      "location": "Abstract"
    },
    {
      "source": "abstract",
      "kind": "count",
      "values": {
        "n_positive": 8
      },
      "quote": "Eight rats showed positive CMAPs.",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "abs_cmap8",
      "location": "Abstract, Results"
    },
    {
      "source": "abstract",
      "kind": "count",
      "values": {
        "n_vecuronium": 4
      },
      "quote": "Four CAMP- positive- rats received Vecuronium \u00ae",
      "checkable": {
        "tools": [],
        "reason": "count of a subset with no percentage or test statistic attached"
      },
      "id": "abs_vec4",
      "location": "Abstract"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "CERE": 12,
        "NaCl": 11,
        "controls": 7
      },
      "quote": "they were 12 Cere (verum), 11 NaCl (placebo) well randomized, and 7 controls (nil)",
      "checkable": {
        "tools": [
          "check_summation_batch"
        ]
      },
      "id": "meth_arms",
      "location": "Methods, Synopsis of the medication",
      "duplicate_of": "abs_arms"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "alpha": 0.05
      },
      "quote": "The level of alpha was defined as alpha=0.05, and a two-sided test was used for superiority.",
      "checkable": {
        "tools": [
          "check_statistic_bounds"
        ]
      },
      "id": "meth_alpha",
      "location": "Statistical Methods"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.4,
        "ci_low": 0.0704,
        "ci_high": 0.7296,
        "p": 0.4146,
        "n1": 10,
        "n2": 3
      },
      "quote": "| NNTXDIAM                     |                                   | 0,4000 | (0,0704 to 0,7296) | 10 / 3  | 0,4146  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t2_diam",
      "location": "Table 2, NNTXDIAM"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.4,
        "ci_low": 0.0704,
        "ci_high": 0.7296,
        "p": 0.4936,
        "n1": 10,
        "n2": 3
      },
      "quote": "| NNTXAREA                     |                                   | 0,4000 | (0,0704 to 0,7296) | 10 / 3  | 0,4936  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t2_area",
      "location": "Table 2, NNTXAREA"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.6667,
        "ci_low": 0.3738,
        "ci_high": 0.9596,
        "p": 0.1928,
        "n1": 10,
        "n2": 3
      },
      "quote": "| NNTXAXON                     |                                   | 0,6667 | (0,3738 to 0,9596) | 10 / 3  | 0,1928  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t2_axon",
      "location": "Table 2, NNTXAXON"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.7333,
        "ci_low": 0.466,
        "ci_high": 1.0,
        "p": 0.102,
        "n1": 10,
        "n2": 3
      },
      "quote": "| NNTXMYELIN                   |                                   | 0,7333 | (0,4660 to 1,0000) | 10 / 3  | 0,1020  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t2_myelin",
      "location": "Table 2, NNTXMYELIN"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.7667,
        "ci_low": 0.4988,
        "ci_high": 1.0,
        "p": 0.7533,
        "n1": 10,
        "n2": 3
      },
      "quote": "| NNTXMIN                      |                                   | 0,7667 | (0,4988 to 1,0000) | 10 / 3  | 0,7533  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t2_min",
      "location": "Table 2, NNTXMIN"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.8,
        "ci_low": 0.5362,
        "ci_high": 1.0,
        "p": 0.9017,
        "n1": 10,
        "n2": 3
      },
      "quote": "| NNTXMAX                      |                                   | 0,8000 | (0,5362 to 1,0000) | 10 / 3  | 0,9017  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t2_max",
      "location": "Table 2, NNTXMAX"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.5667,
        "ci_low": 0.2855,
        "ci_high": 0.8479,
        "p": 0.2347,
        "n1": 10,
        "n2": 3
      },
      "quote": "| NNTXTOTAL                    |                                   | 0,5667 | (0,2855 to 0,8479) | 10 / 3  | 0,2347  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t2_total",
      "location": "Table 2, NNTXTOTAL"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.6333,
        "ci_low": 0.3476,
        "ci_high": 0.9191,
        "p": 0.3505,
        "n1": 10,
        "n2": 3
      },
      "quote": "| NNTXCUMUL                    |                                   | 0,6333 | (0,3476 to 0,9191) | 10 / 3  | 0,3505  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t2_cumul",
      "location": "Table 2, NNTXCUMUL"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.5611,
        "ci_low": 0.5456,
        "ci_high": 0.5766,
        "p": 0.0001,
        "n1": 10,
        "n2": 3
      },
      "quote": "| Combined (Wei-Lachin)        |                                   | 0,5611 | (0,5456 to 0,5766) | 10 / 3  | <0.0001 |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "stalt_check"
        ]
      },
      "id": "t2_combined",
      "location": "Table 2, Combined (Wei-Lachin)"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.625,
        "ci_low": 0.3993,
        "ci_high": 0.8507,
        "p": 0.4146,
        "n1": 16,
        "n2": 5
      },
      "quote": "| Muscle Marlene        |                                   | 0,6250 | (0,3993 to 0,8507) | 16 / 5  | 0,4146  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t3_marlene",
      "location": "Table 3, Muscle Marlene"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.8182,
        "ci_low": 0.5578,
        "ci_high": 1.0,
        "p": 0.4936,
        "n1": 11,
        "n2": 2
      },
      "quote": "| Muscle Catoi          |                                   | 0,8182 | (0,5578 to 1,0000) | 11 / 2  | 0,4936  |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "grimu_check"
        ]
      },
      "id": "t3_catoi",
      "location": "Table 3, Muscle Catoi"
    },
    {
      "source": "table",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.5611,
        "ci_low": 0.5456,
        "ci_high": 0.5766,
        "p": 0.0001,
        "n1": 10,
        "n2": 3
      },
      "quote": "| Combined (Wei-Lachin) |                                   | 0,5611 | (0,5456 to 0,5766) | 10 / 3  | <0.0001 |",
      "checkable": {
        "tools": [
          "check_estimate_ci",
          "detect_duplication"
        ]
      },
      "id": "t3_combined",
      "location": "Table 3, Combined (Wei-Lachin)",
      "duplicate_of": "t2_combined"
    },
    {
      "source": "prose",
      "kind": "estimate_ci",
      "values": {
        "MW": 0.5611,
        "ci_low": 0.5456,
        "ci_high": 0.5766
      },
      "quote": "(MW=0.5611, 95%CI 0.5456-0.5766, Wei-Lachin procedure, directional test, exploratory interpretation.",
      "checkable": {
        "tools": [
          "check_estimate_ci"
        ]
      },
      "id": "t2_caption_mw",
      "location": "Table 2 caption",
      "duplicate_of": "t2_combined"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "pct": 50
      },
      "quote": "the overall mortality of 50% was still high",
      "checkable": {
        "tools": [
          "check_count_percent",
          "grim_percentage"
        ]
      },
      "id": "res_mort50",
      "location": "Results, Surgery"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "n": 21
      },
      "quote": "Consequently, 21 rats underwent the 2 nd Op for transplant revision",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "res_n21",
      "location": "Results, Surgery"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "CERE": 5,
        "NaCl": 7,
        "controls": 3
      },
      "quote": "They were 5 out of 12 CERE (No 10, 11, 17, 24, 27), 7 out of 11 NaCl ( No 9,12, 13, 18, 25, 26, 29), and 3 out of 7 controls (No. 5, 6, 7).",
      "checkable": {
        "tools": [
          "check_summation_batch"
        ]
      },
      "id": "res_completers",
      "location": "Results, Surgery"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "n_positive": 8,
        "n_tested": 21
      },
      "quote": "electro-stimulation of the PNG transplant in 21 rats was positive in only 8 rats.",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "res_cmap_8of21",
      "location": "Results, Direct electrical muscle stimulation"
    },
    {
      "source": "figure",
      "kind": "count",
      "values": {
        "n_positive": 8,
        "n": 16
      },
      "quote": "as it was the case in 8 of 16 rats t3 months after the grafting procedure.",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "fig4_8of16",
      "location": "Figure 4 caption"
    },
    {
      "source": "figure",
      "kind": "count",
      "values": {
        "n_positive": 7,
        "n": 14
      },
      "quote": "Positive EMG potentials were observed in 7 out of the 14 surviving animals.",
      "checkable": {
        "tools": [
          "check_count_percent"
        ]
      },
      "id": "fig12_7of14",
      "location": "Figure 12 caption"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "mean_pos": 2.57,
        "mean_neg": 1.3
      },
      "quote": "was more intense in EMG-positive cases (individual final scores of 2 and 3; score average 2.57) than in EMG-negative cases (individual final scores of 1 and 2; score average 1.3)",
      "checkable": {
        "tools": [
          "check_ratio"
        ]
      },
      "id": "ang_means",
      "location": "Figure 9 caption / Angiogenesis"
    },
    {
      "source": "prose",
      "kind": "percentage",
      "values": {
        "pct": 75
      },
      "quote": "the EMG-positive cases exhibited a larger average muscle fiber diameter compared with the EMG-negative cases, reaching nearly 75% of the contralateral muscle fiber diameter.",
      "checkable": {
        "tools": [],
        "reason": "approximate ('nearly 75%') with no integer count or n printed beside it"
      },
      "id": "res_75pct",
      "location": "Results, Histometric examination"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "n_2nd_op_deaths_immediate": 4,
        "n_next_day": 2
      },
      "quote": "four more animals died immediately after the surgery (No 8, 21, 23, 28), and another two (No 2 and No 3) on the first postoperative day.",
      "checkable": {
        "tools": [
          "check_summation_batch"
        ]
      },
      "id": "res_2nd_op_deaths",
      "location": "Results, Surgery"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "n_fb_cases": 4
      },
      "quote": "SC examination revealed four cases (three EMG-positive and one EMG-negative case) of neurotracer accumulation (FB+)",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "res_fb4",
      "location": "Results, Fluorescence microscopy"
    },
    {
      "source": "figure",
      "kind": "other",
      "values": {
        "dose_ug_kg": 80
      },
      "quote": "Vecuronium \u00ae IV (80 \u00b5g/kg) application during artificial ventilation of the rat",
      "checkable": {
        "tools": [],
        "reason": "dose comparison with Table 1 is a unit conversion across passages, recorded as not_computational"
      },
      "id": "fig5_vec_dose",
      "location": "Figure 5 caption"
    },
    {
      "source": "table",
      "kind": "other",
      "values": {
        "dose_mg_kg_low": 0.04,
        "dose_mg_kg_high": 0.05
      },
      "quote": "| Competitive ACh- neuromuscular blocking                                              | Vecuronium Inresa \u00ae 10 mg/5 ml                                                              | Vecuronium bromid 10 mg/5 ml=Vecuronium Kation 8.75 mg/5 ml                                  | 0.04 - 0.05 mg/kg                                                                      | IV                       | Inresa Arzneimittel GmbH Freiburg, D            |",
      "checkable": {
        "tools": [],
        "reason": "dosing table, not a sample statistic"
      },
      "id": "t1_vecuronium",
      "location": "Table 1, Vecuronium row"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "depth_pos_min": 0.52,
        "depth_pos_max": 1.53,
        "depth_neg_min": 0.12,
        "depth_neg_max": 1.91
      },
      "quote": "NG positions varied in both depth (ranging from 0.52 mm to 1.53 mm in electromyography (emg) positive cases, respectively, from 0.12 mm to 1.91 mm in emg negative cases",
      "checkable": {
        "tools": [],
        "reason": "ranges of a continuous millimetre measurement; no mean/SD/n for GRIM or SD-range"
      },
      "id": "fig7_depths",
      "location": "Figure 7 caption"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "angle_pos_min": 9,
        "angle_pos_max": 40,
        "angle_neg_min": 0,
        "angle_neg_max": 43
      },
      "quote": "ranging from 9\u00b0 to 40\u00b0 in emg positive cases and from 0\u00b0 to 43\u00b0 in emg negative cases",
      "checkable": {
        "tools": [],
        "reason": "angular ranges, no distributional summary"
      },
      "id": "fig7_angles",
      "location": "Figure 7 caption"
    },
    {
      "source": "table",
      "kind": "count",
      "values": {
        "n_plus": 7,
        "n_minus": 10
      },
      "quote": "| 5 (+)  | 40 o , 1.16 mm Rxl 7-9",
      "checkable": {
        "tools": [
          "check_summation_batch"
        ]
      },
      "id": "t4_n_plus_minus",
      "location": "Table 4 case column"
    },
    {
      "source": "prose",
      "kind": "count",
      "values": {
        "n_unexplained_deaths": 14
      },
      "quote": "sudden insult and death of the 14 rats, both intra- or postoperatively",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      },
      "id": "res_14deaths",
      "location": "Results, Unpredictable sudden deaths"
    },
    {
      "source": "prose",
      "kind": "other",
      "values": {
        "pmax_mbar": 18,
        "freq": 50,
        "flow_l_min": 1.5,
        "FiO2": 0.7
      },
      "quote": "Pmax: 18 mbar, ventilation frequency-50/min, flow-1.5 l/",
      "checkable": {
        "tools": [],
        "reason": "equipment settings, not sample statistics"
      },
      "id": "meth_ventilator",
      "location": "Methods, Surgical equipment"
    }
  ],
  "second_look": {
    "n_accusatory": 12,
    "n_flagged": 12,
    "by_marker": {
      "quote_not_located": 12,
      "model_computed": 1
    },
    "items": [
      {
        "id": "table3_combined_copied_from_table2",
        "severity": "suspicious",
        "location": "Table 3, Combined (Wei-Lachin) row",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table3_p_values_copied_from_table2",
        "severity": "highly_suspicious",
        "location": "Table 3, Muscle Marlene and Muscle Catoi P column",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table2_nntxdiam_nntxarea_same_mw_ci_different_p",
        "severity": "suspicious",
        "location": "Table 2, NNTXDIAM and NNTXAREA rows",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table2_nntxmax_ci_excludes_null",
        "severity": "suspicious",
        "location": "Table 2, NNTXMAX row",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table3_catoi_ci_excludes_null",
        "severity": "suspicious",
        "location": "Table 3, Muscle Catoi row",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table2_nntxtotal_p_vs_ci",
        "severity": "suspicious",
        "location": "Table 2, NNTXTOTAL row",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "table2_grimu_all_component_p_miss_lattice",
        "severity": "suspicious",
        "location": "Table 2, P column, eight component rows",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "weillachin_combined_ci_implausibly_tight",
        "severity": "suspicious",
        "location": "Table 2, Combined (Wei-Lachin) row",
        "markers": [
          "model_computed",
          "quote_not_located"
        ],
        "what_to_do": [
          "no registered tool produced this number -- the model did the arithmetic itself, so it has not been through the guards that make a severity safe to state. If a tool covers this check, re-run it with the tool. If none does, say in `triage` what you did to satisfy yourself the arithmetic is right, or drop the finding to `indeterminate`.",
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "second_op_n_abstract_vs_results",
        "severity": "suspicious",
        "location": "Abstract versus Results, Surgery",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "cmap_positive_count_conflict",
        "severity": "suspicious",
        "location": "Abstract; Results; Figure 4 caption; Figure 12 caption; Table 4",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "vecuronium_dose_table1_vs_figure5",
        "severity": "suspicious",
        "location": "Table 1 Vecuronium row versus Figure 5 caption",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      },
      {
        "id": "angiogenesis_score_prose_vs_table4",
        "severity": "suspicious",
        "location": "Figure 9 caption versus Table 4, case 6 ang cell",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      }
    ],
    "note": "12 of 12 accusation(s) carry a named weakness in their evidence. Each is listed with what would settle it. This is a worklist, not a verdict: none of these is wrong because it is listed, and a marker you resolve should be recorded in `triage` like any other triage decision."
  }
}
```

Triage these findings (confirm / deprioritize / reinterpret per the rulebook — especially baseline-similarity results), add the contextual reasoning the sweep cannot do, and emit the report JSON.