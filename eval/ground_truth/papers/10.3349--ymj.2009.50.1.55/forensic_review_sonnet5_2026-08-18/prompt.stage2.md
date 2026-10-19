Write the editorial forensic review for this paper.

Read the paper text and tables with `extract_xml`: `/mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.3349--ymj.2009.50.1.55/10.3349--ymj.2009.50.1.55.xml` (tables come back as structured cells; the PDF, where one exists, is only for figures and cross-checking)

What the sweep actually ran, which is the DENOMINATOR your verdict sits in:

```json
{
  "checks_passed": 6,
  "of_which_collapsed_by_check_table": 0,
  "checks_refused_indeterminate": 3,
  "checks_flagged": 1,
  "checks_total": 10,
  "by_severity": {
    "consistent": 6,
    "indeterminate": 3,
    "suspicious": 1
  },
  "rounding_convention": {
    "n_fit_only_under_truncation": 0,
    "n_granularity_checks": 8,
    "note": "Values that fail the round-half convention but are consistent if the reporter TRUNCATES (SPSS's default, and several journal styles). NOT a finding and never counted as one: a single instance is a house style. The RATE is the signal -- this class of anomaly is commoner in papers with more serious problems, so a high proportion is grounds to look harder, not evidence in itself."
  },
  "sd_convention": {
    "n_fit_only_under_population_sd": 0,
    "n_granularity_checks": 8,
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
  "anatomy": {
    "studies": [
      {
        "id": "S1",
        "label": "Orthognathic surgery antibiotic prophylaxis RCT",
        "design": "rct",
        "n": 56,
        "n_per_group": [
          {
            "label": "Experimental (single preop dose, no postop antibiotics)",
            "n": 28
          },
          {
            "label": "Control (preop dose + postop antibiotics x3 days)",
            "n": 28
          }
        ],
        "clustered": false,
        "preregistered": false,
        "unit_of_analysis": "patient",
        "sample_flow": [
          {
            "stage": "enrolled",
            "n": 56,
            "unit": "patients"
          },
          {
            "stage": "randomized to experimental arm",
            "n": 28,
            "unit": "patients"
          },
          {
            "stage": "randomized to control arm",
            "n": 28,
            "unit": "patients"
          }
        ]
      }
    ],
    "variables": [
      {
        "id": "age",
        "name": "Patient age",
        "measurement_level": "ratio",
        "discreteness": "unknown",
        "family": "continuous",
        "units": "years",
        "derivation": "measured",
        "confidence": "medium",
        "provenance_quote": "The mean (SD) age of the experimental group was 23.9 years (5.84)"
      },
      {
        "id": "sex",
        "name": "Sex (Male:Female ratio)",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "nominal_category",
        "levels": [
          "male",
          "female"
        ],
        "confidence": "high",
        "provenance_quote": "Sex (Male : Female) | 16 : 12 | 14 : 14"
      },
      {
        "id": "infection",
        "name": "Postoperative wound infection occurrence (surgical site infection, SSI, per CDC criteria)",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "levels": [
          "infected",
          "not infected"
        ],
        "confidence": "high",
        "provenance_quote": "There were 3 infections in the experimental group and 2 infections in the control group, observed 2 weeks after surgery (Table 1)."
      },
      {
        "id": "dehiscence",
        "name": "Wound dehiscence occurrence",
        "measurement_level": "nominal",
        "discreteness": "discrete",
        "family": "binary",
        "levels": [
          "dehiscence",
          "no dehiscence"
        ],
        "confidence": "high",
        "provenance_quote": "only 1 patient in the control group developed wound dehiscence only without any drainage, fever, or swelling in the maxillary area"
      }
    ],
    "tests": [
      {
        "id": "T1",
        "test_type": "chi_squared",
        "location": "Results, para 2 / Table 1",
        "study_id": "S1",
        "outcome_var": "infection",
        "predictor_vars": [
          "treatment_group"
        ],
        "n": 56,
        "p_value": 0.639,
        "p_is_threshold": false,
        "ci": "",
        "effect_size": "",
        "is_stated_primary_outcome": true,
        "appears_in_abstract": true,
        "appears_in_conclusions": true,
        "hypothesis_id": "H1",
        "confidence": "high",
        "provenance_quote": "According to the \u03c7\u00b2-test, there was no significant difference in the prevalence of postoperative wound infections between the patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639)."
      }
    ],
    "hypotheses": [
      {
        "id": "H1",
        "statement": "There is no difference in the prevalence of postoperative wound infections between patients who did and did not receive continued postoperative prophylactic antibiotics after orthognathic surgery.",
        "status": "confirmatory",
        "study_id": "S1",
        "appears_in_abstract": true,
        "confidence": "high",
        "provenance_quote": "The aims of this clinical study were to evaluate the prevalence of postoperative wound infections with or without antibiotic prophylaxis after orthognathic surgery in young patients without any specific medical history, and to identify criteria for appropriate use of prophylactic antibiotics in orthognathic surgery."
      }
    ]
  },
  "coverage": {
    "stats_found": 13,
    "tools_run": [
      "extract_xml",
      "extract_pdf",
      "statcheck",
      "parse_cells_typed",
      "parse_cells_as_declared",
      "recalc_chi_squared",
      "check_summation_batch",
      "grim_check",
      "grimmer_check",
      "flag_round_n"
    ],
    "tables_checked": [
      "Table 1 (image_only in XML, recovered from PDF)"
    ]
  },
  "paper_id": "10.3349--ymj.2009.50.1.55",
  "paper_title": "The Efficacy of Postoperative Prophylactic Antibiotics in Orthognathic Surgery: A Prospective Study in Le Fort I Osteotomy and Bilateral Intraoral Vertical Ramus Osteotomy",
  "paper_metadata": {
    "authors": "Sang-Hoon Kang, Jae-Ha Yoo, Choong-Kook Yi",
    "journal": "Yonsei Medical Journal",
    "doi": "10.3349/ymj.2009.50.1.55",
    "year": "2009",
    "study_design": "parallel-arm randomized controlled trial, open-label"
  },
  "schema_version": "1.0",
  "findings": [
    {
      "id": "chi2_infection_recalc",
      "location": "Results, para 2",
      "technique": "recalc_chi_squared",
      "consistent": true,
      "severity": "consistent",
      "quote": "According to the \u03c7\u00b2-test, there was no significant difference in the prevalence of postoperative wound infections between the patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639).",
      "reported": {
        "observed": [
          [
            3,
            25
          ],
          [
            2,
            26
          ]
        ],
        "p": 0.639
      },
      "computed": {
        "chi2_pearson": 0.2196078431372549,
        "p_pearson": 0.639338884785466,
        "fisher_odds_ratio": 1.56,
        "tool": "recalc_chi_squared"
      },
      "inputs": {
        "observed": [
          [
            3,
            25
          ],
          [
            2,
            26
          ]
        ],
        "reported_p": 0.639,
        "decimals_p": 3
      },
      "reproduction": "metascience chi2 --observed \"[[3,25],[2,26]]\" --reported-p 0.639 --decimals-p 3",
      "notes": "Reconstructed the 2x2 table from Table 1's raw counts (3 infected / 25 not-infected of 28 experimental; 2/26 of 28 control). Pearson chi2 = 0.2196, p = 0.6393, matching the reported p = 0.639 exactly. No inconsistency."
    },
    {
      "id": "sex_ratio_sums",
      "location": "Table 1, Sex row",
      "technique": "check_summation",
      "consistent": true,
      "severity": "consistent",
      "quote": "Sex (Male : Female) | 16 : 12 | 14 : 14",
      "reported": {
        "experimental": "16:12",
        "control": "14:14"
      },
      "computed": {
        "experimental_sum": 28,
        "control_sum": 28,
        "tool": "check_summation_batch"
      },
      "inputs": {
        "rows": [
          {
            "values": [
              16,
              12
            ],
            "expected_sum": 28
          },
          {
            "values": [
              14,
              14
            ],
            "expected_sum": 28
          }
        ]
      },
      "reproduction": "metascience summation-batch --rows '[{\"values\":[16,12],\"expected_sum\":28},{\"values\":[14,14],\"expected_sum\":28}]'",
      "notes": "Both group sex counts sum exactly to their stated group n of 28. Also matches the ratios given in prose (4:3 and 1:1, i.e. 16:12 and 14:14 reduced)."
    },
    {
      "id": "age_grim_experimental",
      "location": "Results, para 1 / Table 1, Age row",
      "technique": "grim",
      "consistent": true,
      "severity": "indeterminate",
      "quote": "The mean (SD) age of the experimental group was 23.9 years (5.84)",
      "reported": {
        "mean": 23.9,
        "n": 28
      },
      "computed": {
        "tool": "grim_check",
        "failure_mode": "no_discriminating_power",
        "note": "At n=28 with 1 decimal place, GRIM cannot fail for any mean printable to that precision, so a pass here is uninformative rather than reassuring."
      },
      "inputs": {
        "mean": 23.9,
        "n": 28,
        "decimals": 1,
        "data_type": "integer",
        "scale_min": 0,
        "scale_max": 120,
        "discreteness_source": "assumed",
        "bound_source": "logically_necessary"
      },
      "reproduction": "metascience grim --mean 23.9 --n 28 --decimals 1 --data-type integer --scale-min 0 --scale-max 120",
      "notes": "Age is not stated by the paper to be recorded as whole years, so discreteness is ASSUMED, not stated -- this check cannot reach 'impossible' regardless of outcome. An initial pass mistakenly left the tool's default Likert scale_min/max=1-7 in place, which returned a spurious 'out of range' failure -- an artifact of my own tool-call error, not a property of the paper (age is obviously not a 1-7 scale). Rerun with a defensible, logically-necessary human-age bound [0,120]: GRIM has no discriminating power at this n/precision, so the result is indeterminate, not evidence either way."
    },
    {
      "id": "age_grim_control",
      "location": "Results, para 1 / Table 1, Age row",
      "technique": "grim",
      "consistent": true,
      "severity": "indeterminate",
      "quote": "The mean (SD) age of the control group was 24.3 years (6.33)",
      "reported": {
        "mean": 24.3,
        "n": 28
      },
      "computed": {
        "tool": "grim_check",
        "failure_mode": "no_discriminating_power"
      },
      "inputs": {
        "mean": 24.3,
        "n": 28,
        "decimals": 1,
        "data_type": "integer",
        "scale_min": 0,
        "scale_max": 120,
        "discreteness_source": "assumed",
        "bound_source": "logically_necessary"
      },
      "reproduction": "metascience grim --mean 24.3 --n 28 --decimals 1 --data-type integer --scale-min 0 --scale-max 120",
      "notes": "Same caveat as age_grim_experimental: discreteness assumed, GRIM uninformative at this n/precision."
    },
    {
      "id": "age_grimmer_experimental",
      "location": "Results, para 1 / Table 1, Age row",
      "technique": "grimmer",
      "consistent": true,
      "severity": "consistent",
      "quote": "The mean (SD) age of the experimental group was 23.9 years (5.84)",
      "reported": {
        "mean": 23.9,
        "sd": 5.84,
        "n": 28
      },
      "computed": {
        "tool": "grimmer_check",
        "working_combinations_found": 5,
        "example": {
          "sum": 669,
          "exact_mean": 23.89286,
          "exact_sd": 5.839453
        }
      },
      "inputs": {
        "mean": 23.9,
        "sd": 5.84,
        "n": 28,
        "decimals": 1,
        "decimals_sd": 2,
        "data_type": "integer",
        "scale_min": 0,
        "scale_max": 120,
        "discreteness_source": "assumed"
      },
      "reproduction": "metascience grimmer --mean 23.9 --sd 5.84 --n 28 --decimals 1 --decimals-sd 2 --data-type integer --scale-min 0 --scale-max 120",
      "notes": "Under a defensible logically-necessary age bound [0,120] (rather than the tool's default 1-7 Likert range, which is inapplicable to age and produced a spurious out-of-range result on the first, mis-specified call), integer sum/sum-of-squares combinations exist that reproduce mean=23.9, SD=5.84 at n=28. Consistent, though discreteness of age-in-years is assumed rather than stated by the paper."
    },
    {
      "id": "age_grimmer_control",
      "location": "Results, para 1 / Table 1, Age row",
      "technique": "grimmer",
      "consistent": true,
      "severity": "consistent",
      "quote": "The mean (SD) age of the control group was 24.3 years (6.33)",
      "reported": {
        "mean": 24.3,
        "sd": 6.33,
        "n": 28
      },
      "computed": {
        "tool": "grimmer_check",
        "working_combinations_found": 4,
        "example": {
          "sum": 680,
          "exact_mean": 24.28571,
          "exact_sd": 6.329573
        }
      },
      "inputs": {
        "mean": 24.3,
        "sd": 6.33,
        "n": 28,
        "decimals": 1,
        "decimals_sd": 2,
        "data_type": "integer",
        "scale_min": 0,
        "scale_max": 120,
        "discreteness_source": "assumed"
      },
      "reproduction": "metascience grimmer --mean 24.3 --sd 6.33 --n 28 --decimals 1 --decimals-sd 2 --data-type integer --scale-min 0 --scale-max 120",
      "notes": "Consistent under a logically-necessary age bound; discreteness assumed."
    },
    {
      "id": "sample_sizes_round_n",
      "location": "Patients and Methods, para 1 / Table 1",
      "technique": "flag_round_n",
      "consistent": true,
      "severity": "consistent",
      "quote": "Fifty-six patients in their 20s without a specific medical history...were enrolled in this study.",
      "reported": {
        "ns": [
          28,
          28,
          56
        ]
      },
      "computed": {
        "tool": "flag_round_n",
        "all_divisible_by_moderate": false,
        "all_divisible_by_strong": false
      },
      "inputs": {
        "ns": [
          28,
          28,
          56
        ],
        "moderate_modulus": 50,
        "strong_modulus": 100
      },
      "reproduction": "metascience flag-round-n --ns 28,28,56",
      "notes": "Not suspiciously round; heuristic only per rulebook rule 8."
    },
    {
      "id": "statcheck_no_apa_stats",
      "location": "Whole text (Results/Discussion)",
      "technique": "statcheck",
      "consistent": true,
      "severity": "indeterminate",
      "quote": "According to the \u03c7\u00b2-test, there was no significant difference in the prevalence of postoperative wound infections between the patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639).",
      "reported": {
        "stats_found": 0
      },
      "computed": {
        "tool": "statcheck",
        "message": "No statistics found in text"
      },
      "inputs": {
        "text": "full Results/Discussion body text"
      },
      "reproduction": "metascience statcheck --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.3349--ymj.2009.50.1.55/10.3349--ymj.2009.50.1.55.pdf",
      "notes": "statcheck scans for APA-formatted inline statistics (e.g. chi2(1)=X, p=Y). The paper reports only a bare p-value (\"p = 0.639\") with no accompanying chi2 statistic or df printed in text, so statcheck's text-pattern scanner finds nothing to parse -- this is a property of the paper's minimal reporting style, not evidence of anything. The chi2 statistic itself was independently recalculated and verified above from the raw counts."
    },
    {
      "id": "infection_case_narrative_ambiguity",
      "location": "Results, para 2",
      "technique": "not_computational",
      "consistent": false,
      "severity": "suspicious",
      "quote": "One patient in the experimental group was diagnosed with an infection by facial swelling, redness and sinus haziness in the waters' view, and the other 4 patients were diagnosed with a postoperative infection by swelling and redness, and pain on the mandibular area.",
      "reported": {
        "experimental_group_infections_table": 3,
        "control_group_infections_table": 2
      },
      "computed": {
        "method": "count check by inspection: sentence literally attributes '1 patient' plus 'the other 4 patients' to symptom categories directly following the phrase 'in the experimental group', summing to 5 patients, versus Table 1's stated 3 infections in the experimental group (and 2 in control, total 5)."
      },
      "inputs": {},
      "reproduction": "",
      "consequence": {
        "basis": "asserted",
        "claims_affected": 1,
        "explanation": "If read literally, this sentence attributes 5 infected patients to the experimental group alone, contradicting the Table 1 / preceding-sentence count of 3 experimental-group infections (and 2 control-group infections, total 5). The more probable reading is that '1 patient' belongs to the experimental group and 'the other 4' are distributed across both groups (2 exp + 2 control, or similar), which would reconcile the totals (1+4=5=3+2), but the sentence as written does not make that split explicit.",
        "flips_significance": false
      },
      "notes": "This is a wording/reporting-clarity issue, not an arithmetic impossibility -- the paper never assigns each of the 4 remaining infected patients to a specific group, so the ambiguity cannot be resolved by any forensic tool. Capped at suspicious per instruction; flagged because it sits in the passage describing the primary outcome (infection counts feeding directly into the headline chi-squared test)."
    },
    {
      "id": "table1_image_only_recovered",
      "location": "Table 1",
      "technique": "not_computational",
      "consistent": true,
      "severity": "consistent",
      "quote": "Table 1. Results according to the Postoperative Antibiotic Prophylaxis",
      "reported": {},
      "computed": {},
      "inputs": {},
      "reproduction": "metascience extract --pdf-path /mnt/c/Users/gregs/agent_for_forensic_metascience/eval/ground_truth/papers/10.3349--ymj.2009.50.1.55/10.3349--ymj.2009.50.1.55.pdf",
      "notes": "The JATS XML encodes Table 1 as an image with no extractable cells (image_only=true). Recovered the table from the PDF (docling grid extraction), which yielded the same 4 rows x 2 columns seen nowhere else. All figures in the table were cross-checked against the values restated in prose (age means/SDs, sex ratios, infection counts) and agree exactly -- no XML/PDF or table/prose discrepancy found."
    }
  ],
  "figures": [],
  "statistics_register": [
    {
      "id": "reg1",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "mean": 23.9,
        "sd": 5.84,
        "n": 28
      },
      "quote": "The mean (SD) age of the experimental group was 23.9 years (5.84) with male-female ratio of 4 : 3.",
      "location": "Results, para 1",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check"
        ]
      }
    },
    {
      "id": "reg2",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "mean": 23.9,
        "sd": 5.84,
        "n": 28
      },
      "quote": "Age (Mean \u00b1 SD) | 23.9 \u00b1 5.84 yrs | 24.3 \u00b1 6.33 yrs",
      "location": "Table 1, Age row",
      "duplicate_of": "reg1",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check"
        ]
      }
    },
    {
      "id": "reg3",
      "source": "prose",
      "kind": "mean_sd",
      "values": {
        "mean": 24.3,
        "sd": 6.33,
        "n": 28
      },
      "quote": "The mean (SD) age of the control group was 24.3 years (6.33) with male-female ratio of 1 : 1.",
      "location": "Results, para 1",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check"
        ]
      }
    },
    {
      "id": "reg4",
      "source": "table",
      "kind": "mean_sd",
      "values": {
        "mean": 24.3,
        "sd": 6.33,
        "n": 28
      },
      "quote": "Age (Mean \u00b1 SD) | 23.9 \u00b1 5.84 yrs | 24.3 \u00b1 6.33 yrs",
      "location": "Table 1, Age row",
      "duplicate_of": "reg3",
      "checkable": {
        "tools": [
          "grim_check",
          "grimmer_check"
        ]
      }
    },
    {
      "id": "reg5",
      "source": "prose",
      "kind": "count",
      "values": {
        "male": 16,
        "female": 12
      },
      "quote": "male-female ratio of 4 : 3",
      "location": "Results, para 1",
      "checkable": {
        "tools": [],
        "reason": "a reduced ratio, not counts with a stated n; the underlying counts are given in Table 1 (reg6) which is what was checked"
      }
    },
    {
      "id": "reg6",
      "source": "table",
      "kind": "count",
      "values": {
        "male": 16,
        "female": 12
      },
      "quote": "Sex (Male : Female) | 16 : 12 | 14 : 14",
      "location": "Table 1, Sex row",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      }
    },
    {
      "id": "reg7",
      "source": "table",
      "kind": "count",
      "values": {
        "male": 14,
        "female": 14
      },
      "quote": "Sex (Male : Female) | 16 : 12 | 14 : 14",
      "location": "Table 1, Sex row",
      "checkable": {
        "tools": [
          "check_summation"
        ]
      }
    },
    {
      "id": "reg8",
      "source": "prose",
      "kind": "count",
      "values": {
        "experimental_infections": 3,
        "control_infections": 2
      },
      "quote": "There were 3 infections in the experimental group and 2 infections in the control group, observed 2 weeks after surgery (Table 1).",
      "location": "Results, para 2",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      }
    },
    {
      "id": "reg9",
      "source": "table",
      "kind": "count",
      "values": {
        "experimental_infections": 3,
        "control_infections": 2
      },
      "quote": "Postoperative infection (n) | 3 | 2",
      "location": "Table 1, Postoperative infection row",
      "duplicate_of": "reg8",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      }
    },
    {
      "id": "reg10",
      "source": "table",
      "kind": "count",
      "values": {
        "experimental_dehiscence": 0,
        "control_dehiscence": 1
      },
      "quote": "Wound dehiscence (n) | 0 | 1",
      "location": "Table 1, Wound dehiscence row",
      "checkable": {
        "tools": [],
        "reason": "single-cell counts with no comparator statistic reported over them; nothing to recompute"
      }
    },
    {
      "id": "reg11",
      "source": "prose",
      "kind": "p_value",
      "values": {
        "p": 0.639
      },
      "quote": "According to the \u03c7\u00b2-test, there was no significant difference in the prevalence of postoperative wound infections between the patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639).",
      "location": "Results, para 2",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      }
    },
    {
      "id": "reg12",
      "source": "abstract",
      "kind": "p_value",
      "values": {
        "p": 0.639
      },
      "quote": "There was no significant difference in the incidence of postoperative wound infections between patients who had received postoperative prophylactic antibiotic administration and those who had not (p = 0.639).",
      "location": "Abstract, Results",
      "duplicate_of": "reg11",
      "checkable": {
        "tools": [
          "recalc_chi_squared"
        ]
      }
    },
    {
      "id": "reg13",
      "source": "prose",
      "kind": "other",
      "values": {
        "alpha": 0.05,
        "beta": 0.2,
        "p1_planned": 0.05,
        "p2_planned": 0.35,
        "n_per_group": 28
      },
      "quote": "The samples were selected at a significance level of \u03b1= 0.05 and a test power \u03b2= 0.20. A smaller infection rate was set to 5%, and the difference in the estimated infection rate was set to 30%, based on previous report that the incidence of postoperative wound infection using prophylactic antibiotics, ranges from 5.6% to 33.4%.",
      "location": "Discussion, para 4",
      "checkable": {
        "tools": [],
        "reason": "an a-priori two-proportions power justification; verify_power_analysis/required_n take a single precomputed effect_size (e.g. Cohen's h) and neither accepts raw proportions p1/p2 to derive it internally -- deriving h = 2asin(sqrt(p1)) - 2asin(sqrt(p2)) by hand is barred as manual statistical computation, so no registered tool can verify this power calculation end-to-end"
      }
    },
    {
      "id": "reg14",
      "source": "prose",
      "kind": "percentage",
      "values": {
        "pct": 52.6
      },
      "quote": "Zijderveld et al.[14] suggested that the incidence of postoperative infections (52.6%) increased without the administration of prophylactic antibiotics.",
      "location": "Discussion, para 3",
      "checkable": {
        "tools": [],
        "reason": "a figure cited from a different, external study, not this paper's own data"
      }
    },
    {
      "id": "reg15",
      "source": "prose",
      "kind": "percentage",
      "values": {
        "pct_low": 5.6,
        "pct_high": 33.4
      },
      "quote": "the incidence of postoperative wound infection using prophylactic antibiotics, ranges from 5.6% to 33.4%.[17]",
      "location": "Discussion, para 4",
      "checkable": {
        "tools": [],
        "reason": "a range cited from an external study, used only as this study's design justification, not this paper's own result"
      }
    }
  ],
  "unchecked": [
    {
      "location": "Discussion, para 4: a-priori sample size/power justification (\u03b1=0.05, \u03b2=0.20, p1=5%, p2=35%, n=28/group)",
      "reason": "verify_power_analysis and required_n require a single precomputed effect_size input (e.g. Cohen's h for two proportions); neither tool accepts raw proportions p1/p2 to derive that effect size internally, and deriving it by hand (arcsine transform) is disallowed manual statistical computation. No registered tool can verify this power calculation end-to-end."
    },
    {
      "location": "Results, para 2 / Abstract: the 'no significant difference' conclusion (p=0.639)",
      "reason": "absence_of_evidence needs either a printed CI or a (b, se) pair for the effect estimate. The paper reports only a bare chi-squared p-value with no odds ratio, risk difference, or confidence interval printed anywhere, and deriving an SE for an effect estimate from the raw 2x2 table by hand is disallowed manual computation. Cannot assess the largest effect the data still permit."
    },
    {
      "location": "Table 1, Sex row (ratios '16:12' and '14:14')",
      "reason": "parse_cells_typed and parse_cells_as_declared could not read count:count ratio cells under any of the closed-vocabulary formats (mean_sd, mean_se, n_percent, median_iqr, median_range, estimate_ci); no candidate format applied. Checked instead via check_summation directly on the two integers, which is sufficient for this cell (see findings)."
    },
    {
      "location": "Whole paper: baseline group comparability beyond age and sex",
      "reason": "csf_test / bayesian_table1_dispersion need multiple independent baseline p-values or several rows of means/SDs+counts; this paper reports only one continuous baseline variable (age, no p-value given for the between-group difference) and one categorical one (sex, no p-value given), too few and without printed p-values to run an omnibus baseline-similarity test."
    },
    {
      "location": "Whole paper: trial registration status",
      "reason": "No trial registry ID, protocol number, or registration statement appears anywhere in the text; hypothesis H1 is recorded as 'confirmatory' rather than 'preregistered_confirmatory' for lack of any such citation."
    }
  ],
  "second_look": {
    "n_accusatory": 1,
    "n_flagged": 1,
    "by_marker": {
      "quote_not_located": 1
    },
    "items": [
      {
        "id": "infection_case_narrative_ambiguity",
        "severity": "suspicious",
        "location": "Results, para 2",
        "markers": [
          "quote_not_located"
        ],
        "what_to_do": [
          "the quoted passage could not be found in the paper. Either the values were transcribed rather than copied, or our extraction differs from what the model read. Re-read the source span before keeping this."
        ]
      }
    ],
    "note": "1 of 1 accusation(s) carry a named weakness in their evidence. Each is listed with what would settle it. This is a worklist, not a verdict: none of these is wrong because it is listed, and a marker you resolve should be recorded in `triage` like any other triage decision."
  }
}
```

Triage these findings (confirm / deprioritize / reinterpret per the rulebook — especially baseline-similarity results), add the contextual reasoning the sweep cannot do, and emit the report JSON.