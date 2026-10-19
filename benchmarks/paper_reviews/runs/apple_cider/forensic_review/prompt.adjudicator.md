# Adjudication docket

## Where the paper is
ABSOLUTE paths. Your working directory is NOT the paper directory, on any backend -- a relative path will not resolve. Read the paper with `extract_xml` / `extract_pdf`, or `markdown/body.md` for the plain text.

- paper directory: `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/apple_cider/paper`
- plain text (markdown): `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/apple_cider/paper/markdown/body.md`
- main PDF (extract_pdf): `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/apple_cider/paper/Apple cider vinegar.pdf`
- analysis code the science agent wrote: `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/apple_cider/paper/analysis_code`

NEVER read a `*_from_xml.md` or `*_from_html.md`. Those are fetchpdf's conversions, and MEASURED 2026-08-22 over 418 of them, 152 (36%) dissolve their tables into the prose as undelimited digit runs while their own header certifies `tables: 0`. `markdown/body.md` is ours and keeps tables as `[Table N: ...]` placeholders.

22 finding(s) itemized below (22 problem/undecided total).
Checks that PASSED (not itemized): check_count_percent: 1 pass, check_effect_plausibility: 2 pass, check_summation: 1 pass, check_variance_dispersion: 8 pass, csf_test: 2 pass, grim_percentage: 2 pass, statcheck: 1 pass.

{"finding_id": "f_3b213d597e3b6533", "slug": "baseline_biochemical_table1_vs_table3", "producer": "science_error", "technique": "internal_contradiction", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 4, "impossible": false, "title": "Baseline (week 0) FBS and TC values disagree between Table 1 and Table 3", "description": "Table 1 reports baseline FBS as 119.9±7.2 (Group 3) and 113.6±12.5 (Group 4), and baseline TC as 173.6±16.3 (Group 2). Table 3's own Week 0 column, describing the identical baseline measurement in the identical groups, instead prints FBS 119.9±12.2 (Group 3, SD differs), FBS 118.6±12.5 (Group 4, mean differs), and TC 175.6±12.9 (Group 2, both mean and SD differ); TG for Group 4 also differs (168.1", "location": "Table 1 (baseline biochemical row) vs Table 3, Week 0 column", "quote": "", "reproduction": "no_command_applies"}
{"finding_id": "f_332408d83d42a15d", "slug": "table1_table3_tc_g2_mismatch", "producer": "tool_expert", "technique": "internal_contradiction", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 3, "impossible": false, "title": "Table 1 vs Table 3: different baseline TC mean/SD for Group 2", "description": "Table 1 lists Group 2 baseline TC as 173.6±16.3; Table 3's Week 0 column prints 175.6±12.9 for the same group and variable -- both mean (2.0 mg/dL) and SD differ.", "location": "Table 1, TC row, Group 2 vs Table 3, TC row, Group 2, Week 0", "quote": "TC (mg/dL) 176.0±13.1 173.6±16.3 176.9±11.1 178.5±11.5", "reported": {"table1_g2_tc": "173.6±16.3", "table3_g2_tc_wk0": "175.6±12.9"}, "reproduction": "no_command_applies"}
{"finding_id": "f_f8da056b67e0b51e", "slug": "independent_ttest_for_paired_baseline_comparisons", "producer": "science_error", "technique": "not_computational", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 4, "impossible": false, "title": "Independent t-test used for within-subject repeated-measures comparisons", "description": "Methods state significance was determined \"by using an independent t-test,\" a single named procedure. But the overwhelming majority of the significance markers in Tables 2 and 3 are baseline-vs-follow-up comparisons WITHIN the same participants over time (the '*' symbol, defined as \"compared with baseline (week 0)\"), which are paired/repeated-measures data, not independent samples. No paired t-tes", "location": "Statistical methods and data analysis (Methods) vs Tables 2 and 3 footnotes", "quote": "", "reproduction": "no_command_applies"}
{"finding_id": "f_560ba7b66e510a7c", "slug": "csf_age_weight_height_cluster", "producer": "tool_expert", "technique": "csf_test", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 3, "impossible": false, "title": "Baseline Age, Weight, Height too similar across arms (p=0.006)", "description": "The recomputed one-way ANOVA p-values for baseline Age, Weight and Height (0.931, 0.991, 0.990) are all far above 0.9, and the Carlisle-Stouffer-Fisher test finds this excess similarity survives a conservative correlation adjustment (rho=0.5, similarity p=0.0061). Weight's own SDs (27.1, 28.5, 27.2, 28.6) are independently under-dispersed (variance-dispersion p=0.008). This subgroup was selected a", "location": "Table 1, Age/Weight/Height rows across Groups 1-4", "quote": "Age (years) 17.2±5.2 18.1±5.5 17.6±5.1 17.8±5.7", "reported": {"table1_means_sds": "see Table 1"}, "computed": {"similarity_p": 0.0061, "similarity_p_independence": 0.000194}, "reproduction": "metascience csf --p-values 0.9310,0.9905,0.9897 --method stouffer --design parallel_rct --correlation 0.5"}
{"finding_id": "f_d6633f134967cd3c", "slug": "discussion_overstates_weight_bmi_reduction_range", "producer": "science_error", "technique": "internal_contradiction", "computed_by": "agent_code", "outcome": "problem", "provisional_severity": 3, "impossible": false, "title": "Discussion claims 6-8 kg / 2.7-3.0 BMI-point reductions Table 2 doesn't support", "description": "The Discussion states ACV intake \"reduced the body weight by 6-8 kg and BMIs by 2.7-3.0 points.\" Table 2's own week 0-to-week 12 values give weight reductions of 5.1 kg (Group 1), 7.4 kg (Group 2) and 7.0 kg (Group 3), and BMI reductions of 1.8 (Group 1), 2.9 (Group 2) and 2.8 (Group 3) points. Group 1's weight loss (5.1 kg) falls below the claimed 6-8 kg range, Group 1's BMI loss (1.8) falls well", "location": "Discussion, paragraph beginning \"In Lebanon, the percentage...\" vs Table 2, Weight and BMI rows", "quote": "", "computed": {"weight_loss_kg": {"group1": 5.1, "group2": 7.4, "group3": 7}, "bmi_loss_points": {"group1": 1.8, "group2": 2.9, "group3": 2.8}}, "reproduction": "analysis_code/001_script.py"}
{"finding_id": "f_eeea930918c6818f", "slug": "table1_table3_fbs_g3_sd_mismatch", "producer": "tool_expert", "technique": "internal_contradiction", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 3, "impossible": false, "title": "Table 1 and Table 3 print different baseline FBS SDs for Group 3 (7.2 vs 12.2)", "description": "Table 1 lists Group 3 baseline FBS as 119.9±7.2 mg/dL; Table 3's Week 0 column for the same group and variable prints 119.9±12.2. The means agree but the SDs differ by nearly a factor of 2, confirmed independently via both the markdown and docling PDF extractions.", "location": "Table 1, FBS row, Group 3 vs Table 3, FBS row, Group 3, Week 0", "quote": "FBS (mg/dL) 120.1±10.9 118.9±13.1 119.9±7.2 113.6±12.5", "reported": {"table1_g3_fbs_sd": 7.2, "table3_g3_fbs_wk0_sd": 12.2}, "reproduction": "no_command_applies"}
{"finding_id": "f_492278fa506a51f8", "slug": "age_range_heterogeneity_not_stratified", "producer": "science_error", "technique": "not_computational", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 2, "impossible": false, "title": "Age range 12-25 pooled as one group without stratification", "description": "Inclusion criteria admit participants aged 12 to 25, a span covering early adolescence through full adulthood, yet all analyses pool this range within each of the four groups with no age-stratified analysis, no pediatric BMI-for-age percentiles (adult BMI cut-points of 27-34 kg/m2 were used uniformly), and body composition measured with a consumer bioelectrical-impedance device marketed for adult ", "location": "Participants (Methods, inclusion criteria) and Table 1", "quote": "", "reproduction": "no_command_applies"}
{"finding_id": "f_eeea930918c6818f-2", "slug": "table1_table3_fbs_g4_mean_mismatch", "producer": "tool_expert", "technique": "internal_contradiction", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 3, "impossible": false, "title": "Table 1 and Table 3 print different baseline FBS means for Group 4 (113.6 vs 118.6)", "description": "Table 1 lists Group 4 (placebo) baseline FBS as 113.6±12.5; Table 3's Week 0 column for the same group prints 118.6±12.5 -- a 5.0 mg/dL mean discrepancy despite an identical SD. Table 1's Group 4 value is also the lowest of the four groups, unlike Table 3's, which changes the shape of the baseline picture.", "location": "Table 1, FBS row, Group 4 vs Table 3, FBS row, Group 4, Week 0", "quote": "FBS (mg/dL) 120.1±10.9 118.9±13.1 119.9±7.2 113.6±12.5", "reported": {"table1_g4_fbs_mean": 113.6, "table3_g4_fbs_wk0_mean": 118.6}, "reproduction": "no_command_applies"}
{"finding_id": "f_7ef256175dfe066a", "slug": "zero_attrition_no_flow_diagram", "producer": "science_error", "technique": "not_computational", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 2, "impossible": false, "title": "No dropout, exclusion after enrolment, or CONSORT-style flow is reported over 12 weeks", "description": "All four groups are reported at n=30 at every timepoint (weeks 0, 4, 8, 12) in Tables 1-3, with venous blood draws and full anthropometric batteries required at each visit over a 12-week trial in adolescents and young adults. No flow diagram, no count of screened/excluded/lost-to-follow-up participants, and no discussion of missing data appears anywhere in the paper. Zero attrition over 12 weeks w", "location": "Participants (Methods) and Tables 1-3 (n=30 throughout)", "quote": "", "reproduction": "metascience flow-check flow.json"}
{"finding_id": "f_f1c349f876a22033", "slug": "variance_dispersion_weight", "producer": "tool_expert", "technique": "check_variance_dispersion", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 3, "impossible": false, "title": "Baseline Weight SDs (27.1, 28.5, 27.2, 28.6) are more uniform than sampling error predicts", "description": "Only 0.78% of honest draws under the equal-variance null cluster this tightly (max_z-min_z=0.108, p=0.0078). This is the strongest single-row signal in Table 1 and reinforces the Age/Weight/Height CSF finding, though it is capped at suspicious and is a relative screening signal, not proof.", "location": "Table 1, Weight row", "quote": "Weight (kg) 79.0±27.1 79.3±28.5 77.2±27.2 79.1±28.6", "computed": {"dispersion_p": 0.00777}, "reproduction": "metascience variance-dispersion --sds 27.1,28.5,27.2,28.6 --ns 30,30,30,30 --homogeneous-variances true --design parallel_rct"}
{"finding_id": "f_2b248813e814c6a3", "slug": "undefined_hash_symbol_table3", "producer": "science_error", "technique": "not_computational", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 1, "impossible": false, "title": "Table 3 prints an undefined '#' symbol and a doubled asterisk in two cells", "description": "Table 3's footnotes define only three symbols (*, dagger, double-dagger), but the Group 2 FBS cells at Week 8 and Week 12 print \"115.4±12.6*#*†\" and \"110.1±12.2*#*†\" -- an undefined '#' sandwiched between two asterisks. No other cell in the table carries a repeated or undefined symbol.", "location": "Table 3, FBS row, Group 2, Week 8 and Week 12", "quote": "", "reproduction": "no_command_applies"}
{"finding_id": "f_1940365da8c3fce7", "slug": "table1_table3_tg_g4_mean_mismatch", "producer": "tool_expert", "technique": "internal_contradiction", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 2, "impossible": false, "title": "Table 1 and Table 3 print different baseline TG means for Group 4 (168.1 vs 166.1)", "description": "Table 1 lists Group 4 (placebo) baseline TG as 168.1±18.2; Table 3's Week 0 column prints 166.1±18.2 for the same cell -- a 2.0 mg/dL mean discrepancy with identical SD.", "location": "Table 1, TG row, Group 4 vs Table 3, TG row, Group 4, Week 0", "quote": "TG (mg/dL) 170.1±17.9 167.2±13.2 165.9±13.8 168.1±18.2", "reported": {"table1_g4_tg_mean": 168.1, "table3_g4_tg_wk0_mean": 166.1}, "reproduction": "no_command_applies"}
{"finding_id": "f_481c4f1e806097ee", "slug": "no_trial_registration_reported", "producer": "tool_expert", "technique": "not_computational", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 2, "impossible": false, "title": "No clinical trial registry number reported for this RCT", "description": "The paper reports an institutional ethics approval number (HCR/EC 2023-005) but no clinical-trial-registry identifier (e.g. ClinicalTrials.gov, ISRCTN) anywhere in the text, which is expected for a prospective RCT.", "location": "Ethics approval / Methods sections", "quote": "The number/ID of the approval is HCR/EC 2023–005.", "reproduction": "no_command_applies"}
{"finding_id": "f_5d9bb1a945704e45", "slug": "discussion_weight_bmi_range_claim_mismatch", "producer": "tool_expert", "technique": "internal_contradiction", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 2, "impossible": false, "title": "Discussion's '6-8 kg / 2.7-3.0 points' summary undershoots Table 2's own range", "description": "The Discussion states ACV reduced body weight by 6-8 kg and BMI by 2.7-3.0 points, but Table 2's own week0-to-week12 changes span 5.1-7.4 kg (Group 1: 79.0-73.9=5.1 kg) and 1.8-2.9 BMI points (Group 1: 30.6-28.8=1.8), both below the claimed lower bound.", "location": "Discussion, penultimate paragraph vs Table 2 Weight/BMI rows", "quote": "daily oral intake of ACV for 12 weeks reduced the body weight by 6–8 kg and BMIs by 2.7–3.0 points", "computed": {"weight_change_range_kg": [5.1, 7.4], "bmi_change_range": [1.8, 2.9]}, "reproduction": "no_command_applies"}
{"finding_id": "f_88d5f25ba358bcd1", "slug": "design_independent_t_on_repeated_measures", "producer": "tool_expert", "technique": "not_computational", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 2, "impossible": false, "title": "Methods says 'independent t-test' for within-subject week-0 comparisons", "description": "The Statistical methods paragraph names only the independent t-test, but every within-group 'compared with baseline' significance marker (*) in Tables 2 and 3 is necessarily a repeated/paired measurement on the same 30 people over time, not an independent-samples comparison. Applying an independent-samples test to paired data is usually conservative (inflates the SE), so this is unlikely to have m", "location": "Statistical methods and data analysis paragraph vs Tables 2 and 3 footnotes", "quote": "Significant differences between groups were determined by using an indepen-dent t- test. Statistical significance was set at p<0.05.", "reproduction": "no_command_applies"}
{"finding_id": "f_f05b0569d8065e42", "slug": "gender_pct_g3_female_mismatch", "producer": "tool_expert", "technique": "check_count_percent", "computed_by": "registry_tool", "outcome": "problem", "provisional_severity": 2, "impossible": false, "tool_verdict": "suspicious", "title": "Group 3 female percentage (63.4%) does not match 19/30 under any rounding convention", "description": "19 of 30 Group 3 participants are female, which is 63.333%; the printed 63.4% falls outside the rounding interval [63.35, 63.50) computed both under round-to-nearest and truncation. The paired male figure (36.6% for 11/30) is internally consistent under truncation, so this looks like an isolated slip rather than a wrong count, and the two figures still sum to exactly 100%.", "location": "Table 1, Female row, Group 3", "quote": "Female 60.0 (n=18) 66.7 (n=20) 63.4 (n=19) 56.7 (n=17)", "reported": {"count": 19, "percentage": 63.4}, "computed": {"computed_percentage": 63.3333, "rounding_interval": [63.35, 63.5], "difference": -0.0667}, "reproduction": "metascience check-count-percent --count 19 --percentage 63.4 --n 30 --decimals 1"}
{"finding_id": "f_89cfa57e927b602d", "slug": "table3_undefined_hash_symbol", "producer": "tool_expert", "technique": "not_computational", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 1, "impossible": false, "title": "Table 3 Group 2 cells carry an undefined '#' symbol not listed in the footnotes", "description": "Group 2's FBS entries at week 8 and 12 read '115.4±12.6*#*†' and '110.1±12.2*#*†'; the table footnotes define only *, † and ‡. The '#' (and the doubled '*') appear to be a typesetting artifact.", "location": "Table 3, FBS row, Group 2, weeks 8 and 12", "quote": "Group 2 118.9±13.1 117.5±12.9*† 115.4±12.6*#*† 110.1±12.2*#*†", "reproduction": "no_command_applies"}
{"finding_id": "f_1835358965bb4560", "slug": "baseline_dispersion_whole_table", "producer": "tool_expert", "technique": "bayesian_table1_dispersion", "computed_by": "model_reading", "outcome": "undecided", "impossible": false, "title": "Whole-table baseline dispersion (11 rows) indeterminate but flags a concentrated cluster", "description": "Across all 11 baseline rows the precision multiplier tau-hat=1.44 (CI [0.20, 2.82]) does not distinguish Table 1 from honest randomisation, but an upper-tail Simes test on the row p-values (p=0.057) flags Age, Weight and Height as unusually similar within the whole table. Whole-table pooling dilutes this concentrated cluster.", "location": "Table 1, all 10 continuous rows + Gender", "quote": "Age (years) 17.2±5.2 18.1±5.5 17.6±5.1 17.8±5.7", "reported": {"tau_hat": 1.4417, "ci": [0.1987, 2.8216]}, "computed": {"upper_tail_simes_p": 0.0567, "flagged_rows": ["Age", "Weight", "Height"]}, "reproduction": "metascience table1-dispersion --design parallel_rct (see inputs)"}
{"finding_id": "f_2fe455c58e777c04", "slug": "variance_dispersion_height_borderline", "producer": "tool_expert", "technique": "check_variance_dispersion", "computed_by": "model_reading", "outcome": "undecided", "impossible": false, "title": "Baseline Height SDs borderline under-dispersed (p=0.049), below reporting threshold", "description": "4.85% of honest draws are this tightly clustered or tighter; the tool itself notes this is worth a look but not enough to report alone (canonical published cases sit near 1.2%).", "location": "Table 1, Height row", "quote": "Height (cm) 157.4±20.1 158.6±22.2 157.1±20.8 156.9±21.4", "computed": {"dispersion_p": 0.04851}, "reproduction": "metascience variance-dispersion --sds 20.1,22.2,20.8,21.4 --ns 30,30,30,30 --homogeneous-variances true --design parallel_rct"}
{"finding_id": "f_34cf6d99dfa6a3c7", "slug": "grim_pct_zero_decimal_no_discriminating_power", "producer": "tool_expert", "technique": "grim_percentage", "computed_by": "registry_tool", "outcome": "undecided", "impossible": false, "tool_verdict": "indeterminate", "title": "89%, 87% and 98% (0-decimal figures) carry no GRIM discriminating power at n=120", "description": "At n=120 with 0 printed decimals, every integer percentage from 0-100 is attainable by some count, so GRIM cannot fail on these three sociodemographic figures; a pass here is empty of evidence, not a clean bill.", "location": "Results, sociodemographic paragraph", "quote": "89% of them reported having a high eating frequency, with more than four meals per day", "reproduction": "metascience grim-percentage --percentage 89 --n 120 --decimals 0 --data-type proportion"}
{"finding_id": "f_7f69c27dd9e1161a", "slug": "within_subjects_thresholds_indeterminate", "producer": "tool_expert", "technique": "recalc_within_subjects_t", "computed_by": "registry_tool", "outcome": "undecided", "impossible": false, "tool_verdict": "indeterminate", "title": "Week-0-vs-week-12 significance claims cannot be verified from 'p<0.05' alone", "description": "For Weight (Groups 1-3) and BMI (Groups 1, 3), recovering the implied pre/post correlation from the p<0.05 threshold gives only a lower bound that intersects [-1,1] in every case checked, so no inconsistency can be established. Group 4 (placebo) rows used 'p>0.05', which is not a parseable threshold for this tool.", "location": "Table 2, Weight and BMI rows, Groups 1-3, Week 0 vs Week 12", "quote": "Group 1 79.0±27.1 78.1±26.5*‡ 77.3±26.0*‡ 73.9±23.7*‡", "reproduction": "metascience rivets-t --mean1 79.0 --sd1 27.1 --mean2 73.9 --sd2 23.7 --n1 30 --n2 30"}
{"finding_id": "f_900979ef3700a863", "slug": "csf_anthropometric_block", "producer": "tool_expert", "technique": "csf_test", "computed_by": "model_reading", "outcome": "undecided", "impossible": false, "title": "Full anthropometric block (7 rows) indeterminate under correlation adjustment", "description": "Age, Weight, Height, BMI, Waist, Hip, BFR together look too similar under an independence assumption (p=0.0068) but this does not survive a realistic rho=0.5 correlation adjustment (p=0.1085), so no finding is reported at this grouping.", "location": "Table 1, Age/Weight/Height/BMI/Waist/Hip/BFR rows", "quote": "Age (years) 17.2±5.2 18.1±5.5 17.6±5.1 17.8±5.7", "computed": {"similarity_p": 0.1085, "similarity_p_independence": 0.0068}, "reproduction": "metascience csf --p-values (7 values) --method stouffer --design parallel_rct --correlation 0.5"}

## Second-look worklist (decidable weaknesses per accusation, from the deterministic annotators)
{"n_accusatory": 0, "n_flagged": 0, "by_marker": {}, "items": [], "note": "No finding accuses the paper, so there is nothing to re-check."}

## Checks tally
{"checks_passed": 17, "of_which_collapsed_by_check_table": 0, "checks_refused_indeterminate": 5, "checks_flagged": 17, "checks_total": 39, "by_severity": {"unknown": 22, "3": 6, "2": 7, "1": 2, "4": 2}, "by_outcome": {"refused": 5, "flagged": 17, "pass": 17}, "rounding_convention": {"n_fit_only_under_truncation": 1, "n_granularity_checks": 13, "note": "Values that fail the round-half convention but are consistent if the reporter TRUNCATES (SPSS's default, and several journal styles). NOT a finding and never counted as one: a single instance is a house style. The RATE is the signal -- this class of anomaly is commoner in papers with more serious problems, so a high proportion is grounds to look harder, not evidence in itself."}, "sd_convention": {"n_fit_only_under_population_sd": 0, "n_granularity_checks": 13, "note": "Values that fail under the sample (Bessel, n-1) SD but are consistent under the POPULATION (n) SD -- numpy's std default and Excel's STDEVP. NOT a finding and never counted as one: choosing a convention is not fabrication. The RATE is the signal, on the same reasoning as the rounding convention above."}, "harness_sweep": {"n_tables": 3, "n_accusatory": 1, "accusatory": [{"tool": "detect_duplication", "severity": "suspicious"}], "why": "These checks were aimed by the harness, not by the model: every eligible target in the paper's tables was enumerated and checked. That makes their coverage identical from run to run, which the model-aimed checks are not -- two runs of this pipeline on one paper overlapped on 0 of 10 model-aimed targets."}}

## Paper text (text truncated at 40,000 of 41,085 chars -- use Read for the rest)
--- Page 1 ---
Open access Original research
Apple cider vinegar for weight
management in Lebanese adolescents
and young adults with overweight and
obesity: a randomised, double-b lind,
placebo- controlled study
Rony Abou- Khalil ,1 Jeanne Andary,2 Elissar El- Hayek1
To cite: Abou-K halil R, AbSTRACT
WHAT IS ALREADY KNOWN ON THIS TOPIC
Andary J, El- Hayek E. Apple background and aims Obesity and overweight have
cider vinegar for weight become significant health concerns worldwide, leading ⇒ Recently, there has been increasing interest in al-
management in Lebanese to an increased interest in finding natural remedies for ternative remedies to support weight management,
adolescents and young adults
weight reduction. One such remedy that has gained and one such remedy that has gained popularity is
with overweight and obesity:
popularity is apple cider vinegar (ACV). apple cider vinegar (ACV).
a randomised, double- blind,
Objective To investigate the effects of ACV consumption ⇒ A few small- scale studies conducted on humans
placebo-c ontrolled study. BMJ
Nutrition, Prevention & Health on weight, blood glucose, triglyceride and cholesterol have shown promising results, with ACV consump-
2024;0:e000823. doi:10.1136/ levels in a sample of the Lebanese population. tion leading to weight loss, reduced body fat and
bmjnph-2023-000823 Materials and methods 120 overweight and obese decreased waist circumference.
1Department of Biology, Holy individuals were recruited. Participants were randomly WHAT THIS STUDY ADDS
Spirit University of Kaslik, assigned to either an intervention group receiving 5, 10
Jounieh, Lebanon or 15 mL of ACV or a control group receiving a placebo ⇒ No study has been conducted to investigate the
2Nutrition and Food Science (group 4) over a 12- week period. Measurements of potential antiobesity effect of ACV in the Lebanese
Department, American University anthropometric parameters, fasting blood glucose, population. By conducting research in this demo-
of Science and Technology, triglyceride and cholesterol levels were taken at weeks 0, graphic, the study provides region- specific data and
Beirut, Lebanon 4, 8 and 12. offers a more comprehensive understanding of the
impact of ACV on weight loss and metabolic health.
Results Our findings showed that daily consumption of
Correspondence to
Dr Rony Abou-K halil, the three doses of ACV for a duration of between 4 and HOW THIS STUDY MIGHT AFFECT RESEARCH,
Department of Biology, Holy 12 weeks is associated with significant reductions in PRACTICE OR POLICY
Spirit University of Kaslik, anthropometric variables (weight, body mass index, waist/
⇒ The results might contribute to evidence- based
Jounieh, Lebanon; hip circumferences and body fat ratio), blood glucose,
recommendations for the use of ACV as a dietary
r onyaboukhalil@ usek.e du. lb triglyceride and cholesterol levels. No significant risk
intervention in the management of obesity.
factors were observed during the 12 weeks of ACV intake.
⇒ The study could stimulate further research in the
Conclusion Consumption of ACV in people with
Received 10 November 2023 field, prompting scientists to explore the underlying
overweight and obesity led to an improvement in the
Accepted 10 January 2024 mechanisms and conduct similar studies in other
anthropometric and metabolic parameters. ACV could be
populations.
a promising antiobesity supplement that does not produce
any side effects.
since 1975.4 The World Obesity Federation’s
INTRODUCTION 2023 Atlas predicts that by 2035 more than
Obesity is a growing global health concern half of the world’s population will be over-
characterised by excessive body fat accu- weight or obese.5
mulation, often resulting from a combina- According to the 2022 Global Nutrition
tion of genetic, environmental and lifestyle Report, Lebanon has made limited prog-
factors.1 It is associated with an increased risk ress towards meeting its diet-r elated non-
of numerous chronic illnesses such as type communicable diseases target. A total of
2 diabetes, cardiovascular diseases, several 39.9% of adult (aged ≥18 years) women and
© Author(s) (or their common cancers and osteoarthritis.1–3 30.5% of adult men are living with obesity.
employer(s)) 2024. Re- use According to the WHO, more than Lebanon’s obesity prevalence is higher than
permitted under CC BY- NC. No
1.9 billion adults were overweight worldwide the regional average of 10.3% for women
commercial re- use. See rights
in 2016, of whom more than 650 million were and 7.5% for men.6 In Lebanon, obesity was
and permissions. Published by
BMJ. obese.4 Worldwide obesity has nearly tripled considered as the most important health
Abou-K halil R, et al. bmjnph 2024;0:e000823. doi:10.1136/bmjnph-2023-000823 1
BMJNPH:
first
published
as
10.1136/bmjnph-2023-000823
on
12
March
2024.
Downloaded
from
http://nutrition.bmj.com/
on
May
6,
2024
by
guest.
Protected
by
copyright.

--- Page 2 ---
BMJ Nutrition, Prevention & Health
problem by 27.6% and ranked fifth after cancer, cardio- STUDY DESIGN
vascular, smoking and HIV/AIDS.7 This study was a double-b lind, randomised clinical trial
In recent years, there has been increasing interest in conducted for 12 weeks.
alternative remedies to support weight management, Subjects were divided randomly into four groups: three
and one such remedy that has gained popularity is apple treatment groups and a placebo group. A simple rando-
cider vinegar (ACV), which is a type of vinegar made by misation method was employed using the randomisation
fermenting apple juice. ACV contains vitamins, minerals, allocation software. Groups 1, 2 and 3 consumed 5, 10
amino acids and polyphenols such as flavonoids, which and 15 mL, respectively, of ACV (containing 5% of acetic
are believed to contribute to its potential health bene- acid) diluted in 250 mL of water daily, in the morning
fits.8 9 on an empty stomach, for 12 weeks. The control group
It has been used for centuries as a traditional remedy received a placebo consisting of water with similar taste
for various ailments and has recently gained attention for and appearance. In order to mimic the taste of vinegar,
its potential role in weight management. the placebo group’s beverage (250 mL of water) contained
In hypercaloric- fed rats, the daily consumption of ACV lactic acid (250 mg/100 mL). Identical-l ooking ACV and
showed a lower rise in blood sugar and lipid profile.10 placebo bottles were used and participants were instructed
In addition, ACV seems to decrease oxidative stress and to consume their assigned solution without knowing its
reduces the risk of obesity in male rats with high- fat identity. The subject’s group assignment was withheld
consumption.11 from the researchers performing the experiment.
A few small- scale studies conducted on humans have Subjects consumed their normal diets throughout
shown promising results, with ACV consumption leading the study. The contents of daily meals and snacks were
to weight loss, reduced body fat and decreased waist recorded in a diet diary. The physical activity of the subjects
circumference.12 13 In fact, It has been suggested that was also recorded. Daily individual phone messages were
ACV by slowing down gastric emptying, might promote sent to all participants to remind them to take the ACV or
satiety and reduce appetite.14–16 Furthermore, ACV intake the placebo. A mailing group was also created. Confiden-
seems to ameliorate the glycaemic and lipid profile in tiality was maintained throughout the procedure.
healthy adults17 and might have a positive impact on At weeks 0, 4, 8 and 12, anthropometric measure-
ments were taken for all participants, and the level of
insulin sensitivity, potentially reducing the risk of type 2
diabetes.8 10 18 glucose, triglycerides and total cholesterol was assessed by
collecting 5 mL of fasting blood from each subject.
Unfortunately, the sample sizes and durations of these
studies were limited, necessitating larger and longer-t erm
studies for more robust conclusions. Anthropometric measurements
This work aims to study the efficacy and safety of ACV in Body weight was measured in kg, to the nearest 0.01 kg,
reducing weight and ameliorating the lipid and glycaemic by standardised and calibrated digital scale. Height was
profiles in a sample of overweight and obese adolescents measured in cm, to the nearest 0.1 cm, by a stadiom-
and young adults of the Lebanese population. To the best eter. Anthropometric measurements were taken for all
of our knowledge, no study has been conducted to inves- participants, by a team of trained field researchers, after
tigate the potential antiobesity effect of ACV in the Leba- 10–12 hours fast and while wearing only undergarments.
nese population. Body mass indices (BMIs) were calculated using the
following equation:
Materials and methods BMI(kg/m2)= BodyWeight(kg)
(1)
(Height(m))2
Participants
A total of 120 overweight and obese adolescents and The waist circumference measurement was taken
young adults (46 men and 74 women) were enrolled in between the lowest rib margin and the iliac crest while the
the study and assigned to either placebo group or experi- subject was in a standing position (to the nearest 0.1 cm).
mental groups (receiving increasing doses of ACV). Hip circumference was measured at the widest point of
The subjects were evaluated for eligibility according the hip (to the nearest 0.1 cm).
to the following inclusion criteria: age between 12 and The body fat ratio (BFR) was measured by the bioelec-
25 years, BMIs between 27 and 34 kg/m2, no chronic trical impedance analysis method (OMRON Fat Loss
diseases, no intake of medications, no intake of ACV over Monitor, Model No HBF-3 06C; Japan). Anthropometric
the past 8 weeks prior to the beginning of the study. The variables are shown in table 1.
subjects who met the inclusion criteria were selected by
convenient sampling technique. Those who experienced blood biochemical analysis
heartburn due to vinegar were excluded. Serum glucose was measured by the glucose oxidase
Demographic, clinical data and eating habits were method.19 Triglyceride levels were determined using a
collected from all participants by self-a dministered serum triglyceride determination kit (TR0100, Sigma-
questionnaire. Aldrich). Cholesterol levels were determined using a
2 Abou- Khalil R, et al. bmjnph 2024;0:e000823. doi:10.1136/bmjnph-2023-000823
BMJNPH:
first
published
as
10.1136/bmjnph-2023-000823
on
12
March
2024.
Downloaded
from
http://nutrition.bmj.com/
on
May
6,
2024
by
guest.
Protected
by
copyright.

--- Page 3 ---
BMJ Nutrition, Prevention & Health
Table 1 Baseline demographic, anthropometric and biochemical variables of the three apple cider vinegar groups (group 1, 2
and 3) and the placebo group (group 4)
Group 1 Group 2 Group 3 Group 4 (placebo)
Variable (n=30) (n=30) (n=30) (n=30)
Gender (%)
Male 40.0 (n=12) 33.3 (n=10) 36.6 (n=11) 43.3 (n=13)
Female 60.0 (n=18) 66.7 (n=20) 63.4 (n=19) 56.7 (n=17)
Age (years) 17.2±5.2 18.1±5.5 17.6±5.1 17.8±5.7
Weight (kg) 79.0±27.1 79.3±28.5 77.2±27.2 79.1±28.6
Height (cm) 157.4±20.1 158.6±22.2 157.1±20.8 156.9±21.4
BMI (kg/m2) 30.6±3.1 30.2±2.8 30.0±3.0 30.7±3.2
Waist (cm) 85.9±3.8 84.7±4.4 85.3±4.8 84.2±4.3
Hip (cm) 106.4±3.5 105.8±3.4 105.1±3.9 106.6±3.7
BFR (%) 29.8±6.7 28.1±5.5 30.4±6.3 29.1±5.8
FBS (mg/dL) 120.1±10.9 118.9±13.1 119.9±7.2 113.6±12.5
TG (mg/dL) 170.1±17.9 167.2±13.2 165.9±13.8 168.1±18.2
TC (mg/dL) 176.0±13.1 173.6±16.3 176.9±11.1 178.5±11.5
All values are mean±SD unless stated otherwise
Group 1: daily intake of 5 mL of ACV; group 2: daily intake of 10 mL of ACV; group 3: daily intake of 15 mL of ACV.
ACV, apple cider vinegar; BFR, body fat ratio; BMI, body mass index; FBS, fasting blood sugar; TC, total cholesterol; TG, triglycerides.
cholesterol quantitation kit (MAK043, Sigma- Aldrich). a high eating frequency, with more than four meals
Biochemical variables are shown in table 1. per day. Eighty-s even per cent had no family history of
obesity and 98% had no history of childhood obesity.
Statistical methods and data analysis
The majority reported not having a regular exercise
Data are presented as mean±SD. Statistical analyses were
routine and experiencing negative emotions or anxiety.
performed using Statistical Package for the Social Sciences
All participants were non- smokers and non- drinkers. A
(SPSS) software (version 23.0). Significant differences
small percentage (6.7%) were following a therapeutic
between groups were determined by using an indepen-
diet.
dent t- test. Statistical significance was set at p<0.05.
Effects of ACv intake on anthropometric variables
The addition of 5 mL, 10 mL or 15 mL of ACV to the diet
ETHICAL APPROvAL
resulted in significant decreases in body weight and BMI
The study protocol was reviewed and approved by the
at weeks 4, 8 and 12 of ACV intake, when compared with
research ethics committee (REC) of the Higher Centre
baseline (week 0) (p<0.05). The decrease in body weight
for Research (HCR) at The Holy Spirit University of Kaslik
and BMI seemed to be dose- dependent, with the group
(USEK), Lebanon. The number/ID of the approval is
receiving 15 mL of ACV showing the most important
HCR/EC 2023–005. The participants were informed
reduction (table 2). of the study objectives and signed a written informed
The impact of ACV on body weight and BMI seems consent before enrolment. The study was conducted
to be time-d ependent as well. Reductions were more
in accordance to the International Conference and
pronounced as the study progressed, with the most signif-
Harmonisation E6 Guideline for Good Clinical Practice
icant changes occurring at week 12.
and the Ethical principles of the Declaration of Helsinki.
The circumferences of the waist and hip, along with the
Body Fat Ratio (BFR), decreased significantly in the three
RESULTS treatment groups at weeks 8 and 12 compared with week
Sociodemographic, nutritional and other baseline 0 (p<0.05). No significant effect was observed at week 4,
characteristics of the participants compared with baseline (p>0.05). The effect of ACV on
A total of 120 individuals (46 men and 74 women) with these parameters seems to be time-d ependent with the
BMIs between 27 and 34 kg/m2, were enrolled in the most prominent effect observed at week 12 compared
study. The mean age of the subjects was 17.8±5.7 years with week 4 and 8. However it does not seem to be dose
and 17.6±5.4 years in the placebo and experimental dependent, as the three doses of ACV showed a similar
groups respectively. level of efficacy in reducing the circumferences of the
The majority of participants, approximately 98.3%, waist/hip circumferences and the BFR at week 8 and 12,
were non- vegetarian and 89% of them reported having compared with baseline (table 2).
Abou- Khalil R, et al. bmjnph 2024;0:e000823. doi:10.1136/bmjnph-2023-000823 3
BMJNPH:
first
published
as
10.1136/bmjnph-2023-000823
on
12
March
2024.
Downloaded
from
http://nutrition.bmj.com/
on
May
6,
2024
by
guest.
Protected
by
copyright.

--- Page 4 ---
BMJ Nutrition, Prevention & Health
Table 2 Anthropometric variables of the participants at weeks 0, 4, 8 and 12
Variable Week 0 Week 4 Week 8 Week 12
Weight (kg)
Group 1 79.0±27.1 78.1±26.5*‡ 77.3±26.0*‡ 73.9±23.7*‡
Group 2 79.3±28.5 78.1±27.4*† 77.2±27.4*† 71.9±26.1*†
Group 3 77.2±27.2 74.0±26.6*†‡ 72.6±26.4*†‡ 70.2±25.0*†‡
Group 4 (placebo) 79.1±28.6 79.3±28.4†‡ 78.4±28.7†‡ 78.8±28.6†‡
BMI (kg/m2)
Group 1 30.6±3.1 30.3±2.9*‡ 30.0±2.8*‡ 28.8±2.2*‡
Group 2 30.2±2.8 29.8±2.5*† 29.4±2.6*† 27.3±2.7*†
Group 3 30.0±3.0 28.7±3.1*†‡ 28.1±3.2*†‡ 27.2±2.9*†‡
Group 4 (placebo) 30.7±3.2 30.8±3.1†‡ 30.4±3.3†‡ 30.6±3.2†‡
Waist (cm)
Group 1 85.9±3.8 84.8±3.9 83.9±3.7* 83.0±3.9*
Group 2 84.7±4.4 83.2±4.5 82.4±4.6* 82.0±3.8*
Group 3 85.3±4.8 83.4±4.7 82.7±4.5* 81.9±5.0*
Group 4 (placebo) 84.2±4.3 84.2±4.4 84.5±4.5 84.4±4.6
Hip (cm)
Group 1 106.4±3.5 105.7±3.6 105.1±3.4* 104.6±3.6*
Group 2 105.8±3.4 104.9±3.3 104.4±3.2* 103.8±3.5*
Group 3 105.1±3.9 104.0±3.8 103.5±4.0* 102.9±3.8*
Group 4 (placebo) 106.6±3.7 106.5±3.9 106.4±3.9 106.7±3.5
BFR (%)
Group 1 29.8±6.7 29.6±6.6 29.1±6.8* 28.5±6.6*
Group 2 28.1±5.5 27.6±5.4 27.1±5.6* 26.6±5.4*
Group 3 30.4±6.3 29.7±6.4 29.2±6.5* 28.5±6.3*
Group 4 (placebo) 29.1±5.8 29.2±5.9 29.3±6.0 29.4±5.6
Group 1: daily intake of 5 mL of ACV; group 2: daily intake of 10 mL of ACV; group 3: daily intake of 15 mL of ACV.
All values are mean±SD.
*p<0.05; compared with baseline (week 0).
†p<0.05; compared with group 1 within a specific week.
‡p<0.05; compared with group 2 within a specific week.
ACV, apple cider vinegar; BFR, body fat ratio; BMI, body mass index.
The placebo group did not experience any significant There were no changes in glucose, triglyceride and
changes in the anthropometric variables throughout cholesterol levels in the placebo groups at weeks 4, 8 and
the study (p>0.05). This highlights that the observed 12 compared with week 0 (table 3).
improvements in body weight, BMI, waist and hip circum- These data suggest that continued intake of 15 mL of
ferences and Body Fat Ratio were likely attributed to the ACV for more than 8 weeks is effective in reducing blood
consumption of ACV. fasting sugar, triglyceride and total cholesterol levels in
overweight/obese people.
Effects of ACv on blood biochemical parameters
The consumption of ACV also led to a time and dose Adverse reactions of ACv
dependent decrease in serum glucose, serum triglyceride No apparent adverse or harmful effects were reported by
and serum cholesterol levels. (table 3). the participants during the 12 weeks of ACV intake.
Serum glucose levels decreased significantly by three
doses of ACV at week 4, 8 and 12 compared with week
0 (p<0.05) (table 3). Triglycerides and total cholesterol DISCUSSION
levels decreased significantly at weeks 8 and 12, compared During the past two decades of the last century, child-
with week 0 (p<0.05). A dose of 15 mL of ACV for a dura- hood and adolescent obesity have dramatically increased
tion of 12 weeks seems to be the most effective dose in healthcare costs.20 21 Diet and exercise are the basic
reducing these three blood biochemical parameters. elements of weight loss. Many complementary therapies
4 Abou- Khalil R, et al. bmjnph 2024;0:e000823. doi:10.1136/bmjnph-2023-000823
BMJNPH:
first
published
as
10.1136/bmjnph-2023-000823
on
12
March
2024.
Downloaded
from
http://nutrition.bmj.com/
on
May
6,
2024
by
guest.
Protected
by
copyright.

--- Page 5 ---
BMJ Nutrition, Prevention & Health
Table 3 Biochemical variables of the participants at weeks 0, 4, 8 and 12
Variable Week 0 Week 4 Week 8 Week 12
FBS (mg/dl)
Group 1 120.1±10.9 118.6±10.6*‡ 116.8±10.7*‡ 114.6±9.8*‡
Group 2 118.9±13.1 117.5±12.9*† 115.4±12.6*#*† 110.1±12.2*#*†
Group 3 119.9±12.2 116.6±12.6*†‡ 115.1±12.1*†‡ 108.0±11.1*†‡
Group 4 118.6±12.5 118.7±12.6† 118.5±12.8†‡ 117.2±12.9†‡
TG (mg/dL)
Group 1 170.1±17.9 168.2±18.2 166.0±17.8*‡ 163.1±17.6*‡
Group 2 167.2±13.2 165.2±13.6 163.0±13.2*† 154.7±12.6*†
Group 3 165.9±13.8 163.7±13.7 161.8±13.6*†‡ 151.8±12.0*†‡
Group 4 166.1±18.2 166.3±18.0 166.5±18.3†‡ 166.7±18.1†‡
TC (mg/dL)
Group 1 176.0±13.1 174.2±13.5 171.9±13.1*‡ 170.0±13.9*‡
Group 2 175.6±12.9 173.8±13.2 171.3±12.9*† 164.2±12.8*†
Group 3 176.9±11.1 174.7±11.7 172.5±11.1*†‡ 162.2±11.3*†‡
Group 4 178.5±11.5 178.8±11.2 177.8±11.9†‡ 178.6±11.7†‡
Group 1: daily intake of 5 mL of ACV; group 2: daily intake of 10 mL of ACV; group 3: daily intake of 15 mL of ACV.
All values are mean±SD.
*p<0.05; compared with baseline (week 0).
†p<0.05; Compared with group 1 within a specific week.
‡p<0.05; Compared with group 2 within a specific week.
ACV, apple cider vinegar; FBS, fasting blood sugar; TC, total cholesterol; TG, triglycerides.
have been promoted to treat obesity, but few are truly energy expenditure, improved insulin sensitivity, appetite
beneficial. and satiety regulation.
The present study is the first to investigate the anti- While vinegar is composed of various ingredients, its
obesity effectiveness of ACV, the fermented juice from primary component is acetic acid (AcOH). It has been
crushed apples, in the Lebanese population. shown that after 15 min of oral ingestion of 100 mL
A total of 120 overweight and obese adolescents and vinegar containing 0.75 g acetic acid, the serum acetate
young adults (46 men and 74 women) with BMIs between levels increases from 120 µmol/L at baseline to 350 µmol/
27 and 34 kg/m2, were enrolled. Participants were L24; this fast increase in circulatory acetate is due to its fast
randomised to receive either a daily dose of ACV (5, 10 or absorption in the upper digestive tract.24 25
15 mL) or a placebo for a duration of 12 weeks. Biological action of acetate may be mediated by binding
Some previous studies have suggested that taking ACV to the G-p rotein coupled receptors (GPRs), including
before or with meals might help to reduce postprandial GPR43 and GPR41.25 These receptors are expressed in
blood sugar levels,22 23 but in our study, participants took various insulin- sensitive tissues, such as adipose tissue,26
ACV in the morning on an empty stomach. The choice of skeletal muscle, liver,27 and pancreatic beta cells,28 but
ACV intake timing was motivated by the aim to study the also in the small intestine and colon.29 30
impact of apple cider vinegar without the confounding Yamashita and colleagues have revealed that oral
variables introduced by simultaneous food intake. In administration of AcOH to type 2 diabetic Otsuka Long-
addition, taking ACV before meals could better reduce Evans Tokushima Fatty rats, improves glucose tolerance
appetite and increase satiety. and reduces lipid accumulation in the adipose tissue and
Our findings reveal that the consumption of ACV in liver. This improvement in obesity-l inked type 2 diabetes
people with overweight and obesity led to an improve- is due to the capacity of AcOH to inhibit the activity of
ment in the anthropometric and metabolic parameters. carbohydrate- responsive, element- binding protein, a
It is important to note that the diet diary and physical transcription factor involved in regulating the expres-
activity did not differ among the three treatment groups sion of lipogenic genes such as fatty acid synthase and
and the placebo throughout the whole study, suggesting acetyl- CoA carboxylase.26 31 Sakakibara and colleagues,
that the decrease in anthropometric and biochemical have reported that AcOH, besides inhibiting lipogenesis,
parameters was caused by ACV intake. reduces the expression of genes involved in gluconeogen-
Studies conducted on animal models often attribute esis, such as glucose-6 - phosphatase.32 The effect of AcOH
these effects to various mechanisms, including increased on lipogenesis and gluconeogenesis is in part mediated
Abou- Khalil R, et al. bmjnph 2024;0:e000823. doi:10.1136/bmjnph-2023-000823 5
BMJNPH:
first
published
as
10.1136/bmjnph-2023-000823
on
12
March
2024.
Downloaded
from
http://nutrition.bmj.com/
on
May
6,
2024
by
guest.
Protected
by
copyright.

--- Page 6 ---
BMJ Nutrition, Prevention & Health
by the activation of 5'-AMP- activated protein kinase in the metabolic parameters, knowing that acidic substances,
liver.32 This enzyme seems to be an important pharma- including acetic acid, could contribute to enamel erosion
cological target for the treatment of metabolic disorders over time. In addition to promoting oral health, neutral-
such as obesity, type 2 diabetes and hyperlipidaemia.32 33 ising the acidity of ACV could improve its taste, making it
5'-AMP- activated protein kinase is also known to stim- more palatable. Furthermore, studying the effects of ACV
ulate fatty acid oxidation, thereby increasing energy on weight loss in young Lebanese individuals provides
expenditure.32 33 These data suggest that the effect of valuable insights, but further research is needed for a
ACV on weight and fat loss may be partly due to the ability comprehensive understanding of how the effect of ACV
of AcOH to inhibit lipogenesis and gluconeogenesis and might vary across different age groups, particularly in
activate fat oxidation. older populations and menopausal women.
Animal studies suggest that besides reducing energy
expenditure, acetate may also reduce energy intake, by
regulating appetite and satiety. In mice, an intraperito-
CONCLUSION
neal injection of acetate significantly reduced food intake
by activating vagal afferent neurons.32–34 It is important The findings of this study indicate that ACV consump-
tion for 12 weeks led to significant reduction in anthro-
to note that animal studies done on the effect of acetate
pometric variables and improvements in blood glucose,
on vagal activation are contradictory. This might be due
triglyceride and cholesterol levels in overweight/obese
to the site of administration of acetate and the use of
adolescents/adults. These results suggest that ACV might
different animal models.
have potential benefits in improving metabolic parame-
In addition, in vitro and in vivo animal model studies
ters related to obesity and metabolic disorders in obese
suggest that acetate increases the secretion of gut- derived
individuals. The results may contribute to evidence-b ased
satiety hormones by enter endocrine cells (located in the
gut) such as GLP-1 and PYY hormones.25 32–35 recommendations for the use of ACV as a dietary inter-
vention in the management of obesity. The study dura-
Human studies related to the effect of vinegar on body
tion of 12 weeks limits the ability to observe long- term
weight are limited.
effects. Additionally, a larger sample size would enhance In accordance with our study, a randomised clinical
the generalisability of the results.
trial conducted by Khezri and his colleagues has shown
that daily consumption of 30 mL of ACV for 12 weeks
Contributors RA- K: conceptualisation, methodology, data curation, supervision,
significantly reduced body weight, BMI, hip circumfer-
guarantor, project administration, visualisation, writing–original draft. EE-H :
ence, Visceral Adiposity Index and appetite score in obese conceptualisation, methodology, data curation, visualisation, writing–review and
subjects subjected to a restricted calorie diet, compared editing. JA: investigation, validation, writing–review and editing.
with the control group (restricted calorie diet without Funding The authors have not declared a specific grant for this research from any
ACV). Furthermore, Khezri and his colleagues showed funding agency in the public, commercial or not- for- profit sectors.
that plasma triglyceride and total cholesterol levels Competing interests No, there are no competing interests.
significantly decreased, and high density lipoprotein Patient consent for publication Consent obtained from parent(s)/guardian(s)
cholesterol concentration significantly increased, in the
Ethics approval This study involves human participants and was approved by
ACV group in comparison with the control group.13 32–34 the research ethics committee of the Higher Center for Research (HCR) at The Holy
Similarly, Kondo and his colleagues showed that daily Spirit University of Kaslik (USEK), Lebanon. The number/ID of the approval is HCR/
EC 2023- 005. Participants gave informed consent to participate in the study before
consumption of 15 or 30 mL of ACV for 12 weeks reduced
taking part.
body weight, BMI and serum triglyceride in a sample of
the Japanese population.12 13 32–34 Provenance and peer review Not commissioned; externally peer reviewed.
Data availability statement All data relevant to the study are included in the
In contrast, Park et al reported that daily consumption
article or uploaded as supplementary information.
of 200 mL of pomegranate vinegar for 8 weeks signifi-
Open access This is an open access article distributed in accordance with the
cantly reduced total fat mass in overweight or obese
Creative Commons Attribution Non Commercial (CC BY- NC 4.0) license, which
subjects compared with the control group without signifi-
permits others to distribute, remix, adapt, build upon this work non-c ommercially,
cantly affecting body weight and BMI.36 This contradic- and license their derivative works on different terms, provided the original work is
tory result could be explained by the difference in the properly cited, appropriate credit is given, any changes made indicated, and the use
is non- commercial. See: http://creativecommons.org/licenses/by-nc/4.0/.
percentage of acetate and other potentially bioactive
compounds (such as flavonoids and other phenolic ORCID iD
compounds) in different vinegar types. Rony Abou-K halil http://orcid.org/0000-0002-0214-242X
In Lebanon, the percentage of the population with
a BMI of 30 kg/m2 or more is approximately 32%. The
results of the present study showed that in obese Leba-
REFERENCES
nese subjects who had BMIs ranging from 27 and 34 kg/
1 Jehan S, Zizi F, Pandi- Perumal SR, et al. Energy imbalance: obesity,
m2, daily oral intake of ACV for 12 weeks reduced the associated comorbidities, prevention, management and public health
body weight by 6–8 kg and BMIs by 2.7–3.0 points. implications. Adv Obes Weight Manag Control 2020;10:146–61.
2 Fruh SM. Obesity: risk factors, complications, and strategies for
It would be interesting to investigate in future studies the
sustainable long‐term weight management. J Am Assoc Nurse Pract
effect of neutralised acetic acid on anthropometric and 2017;29:S3–14.
6 Abou- Khalil R, et al. bmjnph 2024;0:e000823. doi:10.1136/bmjnph-2023-000823
BMJNPH:
first
published
as
10.1136/bmjnph-2023-000823
on
12
March
2024.
Downloaded
from
http://nutrition.bmj.com/
on
May
6,
2024
by
guest.
Protected
by
copyright.

--- Page 7 ---
BMJ Nutrition, Prevention & Health
3 Poirier P, Giles TD, Bray GA, et al. Obesity and cardiovascular 20 Wang G, Dietz WH. Economic burden of obesity in youths aged 6 to
disease: pathophysiology, evaluation, and effect of weight loss. 17 years: 1979- 1999. Pediatrics 2002;109:E81–1.
Circulation 2006;113:898–918. 21 Sanyaolu A, Okorie C, Qi X, et al. Childhood and adolescent obesity
4 World Health Organization. Obesity and overweight. 2021. Available: in the United States: a public health concern. Glob Pediatr Health
https://www.who.int/news-room/fact-sheets/detail/obesity-and- 2019;6:2333794X19891305.
overweight 22 Nosrati HR, Mousavi SE, Sajjadi P, et al. Effect of apple cider vinegar
5 Reuters. More than half of the world will be overweight or obese on postprandial blood glucose in type 2 diabetic patients treated
by 2035 - report. 2023. Available: https://www.reuters.com/ with hypoglycemic agents. Journal of Babol University of Medical
business/healthcare-pharmaceuticals/more-than-half-world-will-be- Sciences 2013;15:7–11.
overweight-or-obese-by-2035-report-2023-03-02/ 23 Johnston CS, Quagliano S, White S. White S.vinegar ingestion at
6 Global Nutrition Report. Country nutrition projects, Available: https:// mealtime reduced fasting glucose concentrations in healthy adults at
globalnutritionreport.org/resources/nutrition-profiles/asia/western- risk for type 2 diabetes. Journal of Functional Foods 2013;5:2007–11.
asia/lebanon/ 24 Sugiyama S, Fushimi T, Kishi M, et al. Bioavailability of acetate from
7 Mallat S, Geagea AG, Jurjus RA, et al. Obesity in Lebanon: a national two vinegar supplements: capsule and drink. J Nutr Sci Vitaminol
problem. WJCD 2016;06:166–74. 2010;56:266–9.
8 Chiu H- F, Chiang M, Liao H-J , et al. The ergogenic activity of cider 25 Hernández MAG, Canfora EE, Jocken JWE, et al. The short- chain
vinegar: a randomized cross- over, double- blind, clinical trial. Sports fatty acid acetate in body weight control and insulin sensitivity.
Med Health Sci 2020;2:38–43. Nutrients 2019;11:1943.
9 Yagnik D, Serafin V, J Shah A. Antimicrobial activity of apple cider 26 Le Poul E, Loison C, Struyf S, et al. Functional characterization
vinegar against Escherichia coli, Staphylococcus aureus and
of human receptors for short chain fatty acids and their role in
Candida albicans; downregulating cytokine and microbial protein
polymorphonuclear cell activation. J Biol Chem 2003;278:25481–9.
expression. Sci Rep 2018;8:1732.
27 Brown AJ, Goldsworthy SM, Barnes AA, et al. The orphan G
10 Ousaaid D, Laaroussi H, Bakour M, et al. Beneficial effects of apple
protein-c oupled receptors Gpr41 and Gpr43 are activated by
vinegar on hyperglycemia and hyperlipidemia in hypercaloric-f ed
propionate and other short chain carboxylic acids. J Biol Chem
rats. J Diabetes Res 2020;2020:9284987.
2003;278:11312–9.
11 Halima BH, Sonia G, Sarra K, et al. Apple cider vinegar attenuates
28 Priyadarshini M, Villa SR, Fuller M, et al. An acetate- specific GPCR,
oxidative stress and reduces the risk of obesity in high-f at- fed male
FFAR2, regulates insulin secretion. Mol Endocrinol 2015;29:1055–66.
Wistar rats. J Med Food 2018;21:70–80.
29 Karaki S- I, Tazoe H, Hayashi H, et al. Expression of the short-
12 Kondo T, Kishi M, Fushimi T, et al. Vinegar intake reduces body
chain fatty acid receptor, Gpr43, in the human colon. J Mol Histol
weight, body fat mass, and serum triglyceride levels in obese
2008;39:135–42.
Japanese subjects. Biosci Biotechnol Biochem 2009;73:1837–43.
30 Tazoe H, Otomo Y, Karaki S- I, et al. Expression of short- chain
13 Khezri SS, Saidpour A, Hosseinzadeh N, et al. Beneficial effects of
fatty acid receptor Gpr41 in the human colon. Biomed Res apple cider vinegar on weight management, visceral adiposity index
2009;30:149–56.
and lipid profile in overweight or obese subjects receiving restricted
31 Yamashita H, Fujisawa K, Ito E, et al. Improvement of obesity and
calorie diet: a randomized clinical trial. Journal of Functional Foods
glucose tolerance by acetate in type 2 diabetic Otsuka Long-
2018;43:95–102.
14 Darzi J, Frost GS, Montaser R, et al. Influence of the tolerability Evans Tokushima Fatty (OLETF) rats. Biosci Biotechnol Biochem
of vinegar as an oral source of short- chain fatty acids on appetite 2007;71:1236–43.
control and food intake. Int J Obes (Lond) 2014;38:675–81. 32 Sakakibara S, Yamauchi T, Oshima Y, et al. Acetic acid activates
15 Hlebowicz J, Darwiche G, Björgell O, et al. Effect of apple cider hepatic AMPK and reduces hyperglycemia in diabetic KK- A(Y) mice.
vinegar on delayed gastric emptying in patients with type 1 diabetes Biochem Biophys Res Commun 2006;344:597–604.
mellitus: a pilot study. BMC Gastroenterol 2007;7:46. 33 Schimmack G, Defronzo RA, Musi N. AMP- activated protein kinase:
16 Santos HO, de Moraes WMAM, da Silva GAR, et al. Vinegar (acetic role in metabolism and therapeutic implications. Diabetes Obes
acid) intake on glucose metabolism: a narrative review. Clin Nutr Metab 2006;8:591–602.
ESPEN 2019;32:1–7. 34 Goswami C, Iwasaki Y, Yada T. Short-c hain fatty acids suppress
17 Hadi A, Pourmasoumi M, Najafgholizadeh A, et al. The effect of food intake by activating vagal afferent neurons. J Nutr Biochem
apple cider vinegar on lipid profiles and glycemic parameters: a 2018;57:130–5.
systematic review and meta- analysis of randomized clinical trials. 35 Ahima RS, Antwi DA. Brain regulation of appetite and satiety.
BMC Complement Med Ther 2021;21:179. Endocrinol Metab Clin North Am 2008;37:811–23.
18 Morgan J, Mosawy S. The potential of apple cider vinegar in the 36 Park JE, Kim JY, Kim J, et al. Pomegranate vinegar beverage
management of type 2 diabetes. Int J Diabetes Res 2016;5:129–34. reduces visceral fat accumulation in association with AMPK
19 Walker HK, Hall WD, Hurst JW, eds. Clinical Methods: The History, activation in overweight women: a double- blind, randomized,
Physical, and Laboratory Examinations.3rd ed. Boston: Butterworths, and placebo- controlled trial. Journal of Functional Foods
1990. 2014;8:274–81.
Abou- Khalil R, et al. bmjnph 2024;0:e000823. doi:10.1136/bmjnph-2023-000823 7
BMJNPH:
first
published
as
10.1136/bmjnph-2023-000823
on
12
March
2024.
Downloaded
from
http://nutrition.bmj.com/
on
May
6,
2024
by
guest.
Protected
by
copyright.


## Extracted tables


### Page 3, table 1

| Table 1 Baseline demographic, anthropometric and biochemical variables of the three apple cider vinegar groups (group 1, 2
and 3) and the placebo group (group 4) |  |  |  |  |
| Variable | Group 1
(n=30) | Group 2
(n=30) | Group 3
(n=30) | Group 4 (placebo)
(n=30) |
| Gender (%) |  |  |  |  |
| Male 40.0 (n=12) 33.3 (n=10) 36.6 (n=11) 43.3 (n=13) |  |  |  |  |
| Female 60.0 (n=18) 66.7 (n=20) 63.4 (n=19) 56.7 (n=17) |  |  |  |  |
| Age (years) 17.2±5.2 18.1±5.5 17.6±5.1 17.8±5.7 |  |  |  |  |
| Weight (kg) 79.0±27.1 79.3±28.5 77.2±27.2 79.1±28.6 |  |  |  |  |
| Height (cm) 157.4±20.1 158.6±22.2 157.1±20.8 156.9±21.4 |  |  |  |  |
| BMI (kg/m2) 30.6±3.1 30.2±2.8 30.0±3.0 30.7±3.2 |  |  |  |  |
| Waist (cm) 85.9±3.8 84.7±4.4 85.3±4.8 84.2±4.3 |  |  |  |  |
| Hip (cm) 106.4±3.5 105.8±3.4 105.1±3.9 106.6±3.7 |  |  |  |  |
| BFR (%) 29.8±6.7 28.1±5.5 30.4±6.3 29.1±5.8 |  |  |  |  |
| FBS (mg/dL) 120.1±10.9 118.9±13.1 119.9±7.2 113.6±12.5 |  |  |  |  |
| TG (mg/dL) 170.1±17.9 167.2±13.2 165.9±13.8 168.1±18.2 |  |  |  |  |
| TC (mg/dL) 176.0±13.1 173.6±16.3 176.9±11.1 178.5±11.5 |  |  |  |  |
| All values are mean±SD unless stated otherwise
Group 1: daily intake of 5 mL of ACV; group 2: daily intake of 10 mL of ACV; group 3: daily intake of 15 mL of ACV.
ACV, apple cider vinegar; BFR, body fat ratio; BMI, body mass index; FBS, fasting blood sugar; TC, total cholesterol; TG, triglycerides. |  |  |  |  |

### Page 4, table 1

| Table 2 Anthropometric variables of the participants at weeks 0, 4, 8 and 12 |  |  |  |  |
| Variable | Week 0 | Week 4 | Week 8 | Week 12 |
| Weight (kg) |  |  |  |  |
| Group 1 79.0±27.1 78.1±26.5*‡ 77.3±26.0*‡ 73.9±23.7*‡ |  |  |  |  |
| Group 2 79.3±28.5 78.1±27.4*† 77.2±27.4*† 71.9±26.1*† |  |  |  |  |
| Group 3 77.2±27.2 74.0±26.6*†‡ 72.6±26.4*†‡ 70.2±25.0*†‡ |  |  |  |  |
| Group 4 (placebo) 79.1±28.6 79.3±28.4†‡ 78.4±28.7†‡ 78.8±28.6†‡ |  |  |  |  |
| BMI (kg/m2) |  |  |  |  |
| Group 1 30.6±3.1 30.3±2.9*‡ 30.0±2.8*‡ 28.8±2.2*‡ |  |  |  |  |
| Group 2 30.2±2.8 29.8±2.5*† 29.4±2.6*† 27.3±2.7*† |  |  |  |  |
| Group 3 30.0±3.0 28.7±3.1*†‡ 28.1±3.2*†‡ 27.2±2.9*†‡ |  |  |  |  |
| Group 4 (placebo) 30.7±3.2 30.8±3.1†‡ 30.4±3.3†‡ 30.6±3.2†‡ |  |  |  |  |
| Waist (cm) |  |  |  |  |
| Group 1 85.9±3.8 84.8±3.9 83.9±3.7* 83.0±3.9* |  |  |  |  |
| Group 2 84.7±4.4 83.2±4.5 82.4±4.6* 82.0±3.8* |  |  |  |  |
| Group 3 85.3±4.8 83.4±4.7 82.7±4.5* 81.9±5.0* |  |  |  |  |
| Group 4 (placebo) 84.2±4.3 84.2±4.4 84.5±4.5 84.4±4.6 |  |  |  |  |
| Hip (cm) |  |  |  |  |
| Group 1 106.4±3.5 105.7±3.6 105.1±3.4* 104.6±3.6* |  |  |  |  |
| Group 2 105.8±3.4 104.9±3.3 104.4±3.2* 103.8±3.5* |  |  |  |  |
| Group 3 105.1±3.9 104.0±3.8 103.5±4.0* 102.9±3.8* |  |  |  |  |
| Group 4 (placebo) 106.6±3.7 106.5±3.9 106.4±3.9 106.7±3.5 |  |  |  |  |
| BFR (%) |  |  |  |  |
| Group 1 29.8±6.7 29.6±6.6 29.1±6.8* 28.5±6.6* |  |  |  |  |
| Group 2 28.1±5.5 27.6±5.4 27.1±5.6* 26.6±5.4* |  |  |  |  |
| Group 3 30.4±6.3 29.7±6.4 29.2±6.5* 28.5±6.3* |  |  |  |  |
| Group 4 (placebo) 29.1±5.8 29.2±5.9 29.3±6.0 29.4±5.6 |  |  |  |  |
| Group 1: daily intake of 5 mL of ACV; group 2: daily intake of 10 mL of ACV; group 3: daily intake of 15 mL of ACV.
All values are mean±SD.
*p<0.05; compared with baseline (week 0).
†p<0.05; compared with group 1 within a specific week.
‡p<0.05; compared with group 2 within a specific week.
ACV, apple cider vinegar; BFR, body fat ratio; BMI, body mass index. |  |  |  |  |

### Page 5, table 1

| Table 3 Biochemical variables of the participants at weeks 0, 4, 8 and 12 |  |  |  |  |
| Variable | Week 0 | Week 4 | Week 8 | Week 12 |
| FBS (mg/dl) |  |  |  |  |
| Group 1 120.1±10.9 118.6±10.6*‡ 116.8±10.7*‡ 114.6±9.8*‡ |  |  |  |  |
| Group 2 118.9±13.1 117.5±12.9*† 115.4±12.6*#*† 110.1±12.2*#*† |  |  |  |  |
| Group 3 119.9±12.2 116.6±12.6*†‡ 115.1±12.1*†‡ 108.0±11.1*†‡ |  |  |  |  |
| Group 4 118.6±12.5 11