# Adjudication docket

## Where the paper is
ABSOLUTE paths. Your working directory is NOT the paper directory, on any backend -- a relative path will not resolve. Read the paper with `extract_xml` / `extract_pdf`, or `markdown/body.md` for the plain text.

- paper directory: `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/wound_healing/paper`
- plain text (markdown): `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/wound_healing/paper/markdown/body.md`
- main PDF (extract_pdf): `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/wound_healing/paper/wound_healing.pdf`
- analysis code the science agent wrote: `/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/agent_for_forensic_metascience/eval/runs/wound_healing/paper/analysis_code`

NEVER read a `*_from_xml.md` or `*_from_html.md`. Those are fetchpdf's conversions, and MEASURED 2026-08-22 over 418 of them, 152 (36%) dissolve their tables into the prose as undelimited digit runs while their own header certifies `tables: 0`. `markdown/body.md` is ours and keeps tables as `[Table N: ...]` placeholders.

7 finding(s) itemized below (7 problem/undecided total).
Checks that PASSED (not itemized): check_flow_arithmetic: 1 pass.

{"finding_id": "f_283798d106b66085", "slug": "methods_omit_definitions_analysis_ethics", "producer": "science_error", "technique": "not_computational", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 4, "impossible": false, "title": "Methods omit outcome definitions, analysis, randomization, and ethics", "description": "This interventional RCT reports wound gapping, seroma, erythema, infection, and a 42-event composite without diagnostic criteria, a named statistical test, a sample-size calculation, sequence generation, or allocation concealment. Skin closure method is never specified even though surgeons closed skin and subcutaneous layers and the primary claims are wound complications. The only ethics statement", "location": "Patients and methods", "quote": "Randomization of cases was done to the 400 pregnant women who were consented to participate in the study and were distributed in two groups: group A and group B. The randomization allocation was 1:1."}
{"finding_id": "f_8e7f4efcee23e022", "slug": "prose_counts_printed_as_percentages", "producer": "tool_expert", "technique": "not_computational", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 3, "impossible": false, "title": "Results print Table 1 counts as cohort percentages", "description": "Results and Discussion state that wound gapping, seroma, erythema and infection occurred in 12%, 10%, 18% and 20% of the whole cohort. Table 1 prints those same numerators as 12 (3), 10 (2.5), 18 (4.5) and 20 (5) of n=397. The prose therefore reports the event counts as percentages, inflating each incidence about four-fold. Table 1 and Table 4 cell counts agree with one another. The abstract uses ", "location": "Results and Discussion versus Table 1", "quote": "wound gapping occurred in 12% of cases, wound seroma occurred in 10% of cases, wound erythema occurred in 18% of cases, and wound infection occurred in 20% of cases in the whole cohort of cases."}
{"finding_id": "f_8a461c74de2b8322", "slug": "bmi_range_below_inclusion_threshold", "producer": "science_error", "technique": "internal_contradiction", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 4, "impossible": false, "title": "Table 2 BMI range 23.0-45.0 contradicts BMI>30 inclusion", "description": "Inclusion required BMI>30 and Methods state there is no group with BMI below 30 because the study was restricted to obese women. Table 2 prints BMI range 23.0-45.0 (mean 34.5, SD 3.6). Those two statements cannot both be true: either non-obese women were enrolled, or the reported range is wrong. The abstract and title frame the trial as a study of obese women.", "location": "Patients and methods versus Table 2, BMI row", "quote": "with BMI>30 (so, we do not have a group of women with BMI below 30 as our focus in the present research was to assess the obese women)"}
{"finding_id": "f_a6b28cb05fe71636", "slug": "prose_counts_reported_as_percentages", "producer": "science_error", "technique": "check_count_percent", "computed_by": "registry_tool", "outcome": "problem", "provisional_severity": 3, "impossible": false, "tool_verdict": "suspicious", "title": "Results treat Table 1 counts 12, 10, 18, 20 as cohort percentages", "description": "Results and Discussion state that wound gapping, seroma, erythema, and infection occurred in 12%, 10%, 18%, and 20% of the whole cohort. Table 1 prints those same integers as counts with percentages 12 (3%), 10 (2.5%), 18 (4.5%), and 20 (5%) at n=397. check_count_percent on 12/397 versus printed 12% yields 3.02%, outside the rounding interval, with implied denominator about 100. The same Discussio", "location": "Results Description and Discussion versus Table 1", "quote": "wound gapping occurred in 12% of cases, wound seroma occurred in 10% of cases, wound erythema occurred in 18% of cases, and wound infection occurred in 20% of cases in the whole cohort of cases.", "reported": {"gapping_percent_prose": 12, "seroma_percent_prose": 10, "erythema_percent_prose": 18, "infection_percent_prose": 20, "gapping_table": "12 (3)", "seroma_table": "10 (2.5)", "erythema_table": "18 (4.5)", "infection_table": "20 (5)", "n": 397}, "computed": {"gapping_percent_from_12_of_397": 3.02267, "seroma_percent_from_10_of_397": 2.518892, "erythema_percent_from_18_of_397": 4.534005, "infection_percent_from_20_of_397": 5.037783, "implied_denominator_for_prose_12pct": 100.0}, "reproduction": "metascience check-count-percent", "basis": "tool"}
{"finding_id": "f_b18c6b49b22ee707", "slug": "table1_interrupted_ltfu_arithmetic", "producer": "science_error", "technique": "check_flow_arithmetic", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 3, "impossible": false, "title": "Table 1 interrupted n=199 after losing 2 cannot equal 200-2", "description": "Methods and Figure 1 allocate 200 to interrupted, lose 1 to follow-up, and analyze 199. Table 1 prints Interrupted 199 (50.1) after lost follow-up of 2 women. Using Table 1's own operands, 200 minus 2 leaves 198, not 199. Both suture-type rows say lost follow-up of 2 women, which would be 4 exclusions, while the Table 1 header is n=397 after exclusion of 3 cases. The CONSORT cascade as printed (41", "location": "Table 1, Suture Type rows versus Figure 1", "quote": "Interrupted 199(50.1)afterlostfollowupof2women", "reported": {"allocated_interrupted": 200, "table1_lost_interrupted": 2, "table1_remaining_interrupted": 199, "consort_lost_interrupted": 1}, "computed": {"expected_remaining": 198, "observed_remaining": 199, "difference": 1}, "reproduction": "metascience flow-check", "basis": "tool"}
{"finding_id": "f_f921a11338ca1c43", "slug": "registry_1month_outcome_vs_7day_report", "producer": "science_error", "technique": "factual_claim", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 3, "impossible": false, "title": "Registered 1-month primary outcome not the paper's 7-day follow-up", "description": "NCT03354078 was first submitted 19 November 2017 after a stated 18 June 2017 start, so registration is retrospective. The registered primary outcome is participants without seroma, erythema, and infection at one month after cesarean. The paper says most complications were diagnosed at 7 days and does not report 1-month results. Registry eligibility is age 18-40 years; the paper includes ages 25-35", "location": "Abstract NCT ID, Methods follow-up, versus ClinicalTrials.gov NCT03354078", "quote": "The time interval from the wound closure till diagnosis of the wound complications (erythema, seroma, wound infection, and wound gapping) in most of the patients was 7d (at first visit postoperative)", "basis": "web_lookup", "web_unbacked": "claims basis: web_lookup but records ZERO web_sources -- the claim is unauditable; treat it as model knowledge (severity cap 3) unless a source is quoted", "ledger_web_context": ["https://clinicaltrials.gov/study/NCT03354078", "https://ichgcp.net/clinical-trials-registry/NCT03354078", "https://www.cdc.gov/nchs/products/databriefs/db35.htm"]}
{"finding_id": "f_265622f5cc9dca88", "slug": "citations_do_not_support_incidence_or_risks", "producer": "science_error", "technique": "factual_claim", "computed_by": "model_reading", "outcome": "problem", "provisional_severity": 2, "impossible": false, "title": "Citation [1] does not support the 3% to 30% CS complication range", "description": "The paper cites Brown et al. 2010 for cesarean wound-complication incidence ranging from 3% to 30%. That paper is a plastic-surgery study of psychosocial distress and self-rated scar severity in 82 patients and does not report cesarean wound-complication incidence. Wound-infection risk factors are cited to Menacker and Hamilton 2010 (ref 7) plus Wloch et al. 2012 (ref 8); the Menacker NCHS data br", "location": "Introduction, paragraph 2, references [1] and [7]", "quote": "Postoperative wound complications are one of the great issues in CS with an incidence ranging from 3% to 30% [1].", "basis": "web_lookup", "web_unbacked": "claims basis: web_lookup but records ZERO web_sources -- the claim is unauditable; treat it as model knowledge (severity cap 3) unless a source is quoted", "ledger_web_context": ["https://clinicaltrials.gov/study/NCT03354078", "https://ichgcp.net/clinical-trials-registry/NCT03354078", "https://www.cdc.gov/nchs/products/databriefs/db35.htm"]}

## Second-look worklist (decidable weaknesses per accusation, from the deterministic annotators)
{"n_accusatory": 6, "n_flagged": 0, "by_marker": {}, "items": [], "note": "All 6 accusation(s) were computed by a registered tool, quote a passage located in the paper, and none records an assumed bound -- though 6 of them state no bound provenance at all, so that clause is unverified for those. Nothing is flagged for a second look."}

## Checks tally
{"checks_passed": 19, "of_which_collapsed_by_check_table": 18, "checks_refused_indeterminate": 0, "checks_flagged": 7, "checks_total": 26, "by_severity": {"3": 4, "4": 2, "2": 1, "unknown": 1}, "by_outcome": {"flagged": 7, "pass": 1}, "rounding_convention": {"n_fit_only_under_truncation": 0, "n_granularity_checks": 25, "note": "Values that fail the round-half convention but are consistent if the reporter TRUNCATES (SPSS's default, and several journal styles). NOT a finding and never counted as one: a single instance is a house style. The RATE is the signal -- this class of anomaly is commoner in papers with more serious problems, so a high proportion is grounds to look harder, not evidence in itself."}, "grace": {"n_items": 25, "n_reconciled_strictly": 25, "n_rescued": 0, "by_grace": {}, "n_with_direction": 0, "n_leaning_high": 0, "n_leaning_low": 0, "sign_test_p": null, "reading": "Nothing needed an allowance; every item reconciled on its printed values."}, "sd_convention": {"n_fit_only_under_population_sd": 0, "n_granularity_checks": 25, "note": "Values that fail under the sample (Bessel, n-1) SD but are consistent under the POPULATION (n) SD -- numpy's std default and Excel's STDEVP. NOT a finding and never counted as one: choosing a convention is not fabrication. The RATE is the signal, on the same reasoning as the rounding convention above."}, "harness_sweep": {"n_tables": 6, "n_accusatory": 0, "accusatory": [], "why": "These checks were aimed by the harness, not by the model: every eligible target in the paper's tables was enumerated and checked. That makes their coverage identical from run to run, which the model-aimed checks are not -- two runs of this pipeline on one paper overlapped on 0 of 10 model-aimed targets."}}

## Paper text
--- Page 1 ---
The Journal of Maternal-Fetal & Neonatal Medicine
ISSN: 1476-7058 (Print) 1476-4954 (Online) Journal homepage: www.tandfonline.com/journals/ijmf20
Effect of subcutaneous tissue closure technique
in cesarean section on postoperative wound
complications in obese Egyptian women
Mahmoud Alalfy, Ahmed Elgazzar, Tamer Fares, Omar Nagy, Ahmed Ellithy,
Yossra Lasheen, Ahmed Kamel, Mahmoud Soliman, Ahmed Hassan, Ahmed
Samy, Ayman M. Taher, Asmaa I. Ogila, Hany Saad, Hend Salah, Mohamed
Ramadan, Mohamed Nabil, Dina L. Hatem & Mohamed Fikry
To cite this article: Mahmoud Alalfy, Ahmed Elgazzar, Tamer Fares, Omar Nagy, Ahmed Ellithy,
Yossra Lasheen, Ahmed Kamel, Mahmoud Soliman, Ahmed Hassan, Ahmed Samy, Ayman M.
Taher, Asmaa I. Ogila, Hany Saad, Hend Salah, Mohamed Ramadan, Mohamed Nabil, Dina L.
Hatem & Mohamed Fikry (2019) Effect of subcutaneous tissue closure technique in cesarean
section on postoperative wound complications in obese Egyptian women, The Journal of
Maternal-Fetal & Neonatal Medicine, 32:15, 2452-2459, DOI: 10.1080/14767058.2018.1438399
To link to this article: https://doi.org/10.1080/14767058.2018.1438399
Published online: 20 Feb 2018.
Submit your article to this journal
Article views: 519
View related articles
View Crossmark data
Citing articles: 5 View citing articles
Full Terms & Conditions of access and use can be found at
https://www.tandfonline.com/action/journalInformation?journalCode=ijmf20

--- Page 2 ---
THEJOURNALOFMATERNAL-FETAL&NEONATALMEDICINE
2019,VOL.32,NO.15,2452–2459
https://doi.org/10.1080/14767058.2018.1438399
ORIGINAL ARTICLE
Effect of subcutaneous tissue closure technique in cesarean section on
postoperative wound complications in obese Egyptian women
Mahmoud Alalfya , Ahmed Elgazzarb, Tamer Faresc, Omar Nagyd , Ahmed Ellithyb, Yossra Lasheenb,
Ahmed Kamelb, Mahmoud Solimanb, Ahmed Hassane, Ahmed Samyb, Ayman M. Taherb, Asmaa I. Ogilab,
Hany Saadb, Hend Salahc, Mohamed Ramadanb, Mohamed Nabilb, Dina L. Hatemb and Mohamed Fikryb
aDepartment ofReproductiveHealthandFamily Planning,NationalResearchCentre,Aljazeerah Hospital, CAIFM,Geza, Egypt;
bDepartmentofObstetricsandGynecology, Kasralainy,CairoUniversity,Cairo,Egypt;cDepartment ofObstetricsand Gynecology,
AlAzharUniversity, Cairo,Egypt;dDepartmentofReproductiveHealthandFamily Planning,NationalResearchCentre, Cairo,Egypt;
eDepartmentofObstetricsandGynecology, SuezCanal University,Ismaelia,Egypt
ABSTRACT ARTICLEHISTORY
Subcutaneous tissue closure technique is a wide area of interest for obstetricians who perform Received1December2017
cesareansectionespeciallyonobesewomenwhilemanyobserversstudiedinanextensiveman- Revised29January2018
nerpostoperativepainandwoundcosmeticresults. Accepted5February2018
Aim of the work: The main goal of our work was to display the differences in wound outcome
KEYWORDS
results as regard postoperative wound complications comparing the two widely implemented
Subcutaneous;seroma;
techniquesinsubcutaneoustissueclosure(interruptedversuscontinuousmethods).
woundgapping;wound
Results: A comparative analysis between continuous and interrupted techniques regarding
infection;erythema
wound complications (gapping, seroma, erythema, and infection) showing statistical significant
differences in all four wound complications presented with p values=.019, .011, .015, and .001,
in consecutive order with odds ratio in wound gapping=5.239, wound seroma OR=9.429,
wounderythemaOR=3.709,andwoundinfectionOR=6.136.
Conclusions: Subcutaneous wound closure using interrupted technique of suturing in obese
patientsissuperiortocontinuoustechniqueasregardwoundcomplications.
Clinicaltrials.govIDIdentifier(NCT03354078).
Introduction performed and assessed the influence of subcutaneous
tissue closure in the past 20 years [9,10]. The apparent
Only a small number of research studies evaluated the
advantage of closing the subcutaneous layer is the
impact of various subcutaneous tissue and skin closure
decline in wound tension applied on tissues and the
methods at cesarean section (CS) [1,2]. In a meta-
obliteration of dead space in which serous fluid and
analysis, a major decline in incision site rupture was
blood may collect resulting in infection and disruption
revealed when suturing the subcutaneous tissue in
[11,12]. From another aspect, there are many theoret-
women with a subcutaneous depth >2cm [3,4].
ical drawbacks that include prolonged operative
However, the outcome of these, the research per-
time, reduced tissue mobility, and the presence of
formed, are made on a small number of patients,
foreign material in the wound acting as a focus for
insufficient follow-up period of time for accurate long-
infection [13].
term assessment [5,6].
A racial difference in the relations between BMI and
Postoperative wound complications are one of the
body fat distribution [14,15] and body fat percentage
great issues in CS with an incidence ranging from 3% [16] and risk of disease [9,17] were observed,
to 30% [1]. Obesity, operative time, diabetes, age of Therefore, there are physiologic variations for racial
the patient, anemia, associated infection (e.g. cho- differences in cesarean complications among morbidly
rioamnionitis), delayed labor with many vaginal exami- obese women.
nations, and reduced nutrition are recognized risk Esthetic results after closure of the subcutaneous
factors for wound infections [7,8]. With the seek to layer of fat is of great importance to be considered.
avoid wound infection, many research studies were Development of hypertrophic scarring is thought to be
CONTACT Mahmoud Alalfy mahmoudalalfy@ymail.com Department of Reproductive Health and Family Planning, National Research Centre,
AljazeerahHospital,CAIFM,Geza,Egypt
(cid:1)2018InformaUKLimited,tradingasTaylor&FrancisGroup

--- Page 3 ---
THEJOURNALOFMATERNAL-FETAL&NEONATALMEDICINE 2453
caused by many different factors, tension acting on a patients in this study. Diathermy was not used in the
scar has been concluded to be a widespread factor to skin cutting to decrease rate of infection, meticulous
initiate the pathological process [18,19]. Closure of hemostasis was made in all abdominal wall layers, suc-
dead spaces, closure of the subcutaneous tissue layer tion drainage was used if there is any oozing tissues
is believed to reduce tension on the above skin layer. to drain all layers. Patients were randomly distributed
Sutures closing the subcutaneous tissue layer could, to the 10 surgeons.
therefore, lead to superior esthetic result by lessening The age of patients included in this research was
strain on the sutures of the skin layer. Interestingly, to between 25 and 35 years, with BMI>30 (so, we do
mention, suturing of the subcutaneous fat greatly not have a group of women with BMI below 30 as our
decreases the incidence of postoperative hematoma focus in the present research was to assess the obese
formation and seroma development and could avoid women), ladies who are candidate to perform first CS
retraction of the scar below the level of the neighbor- and have no medical disorders with pregnancy e.g.
ing skin, by sealing of dead space and performing DM, HTN. All patients were subjected to full history
best possible leveling of the opposing wound edges. taking and examination.
In another aspect, suture closure of subcutaneous tis- The following patients were excluded women with
sue at pathological level result in an inflammatory BMI<30, who made previous CS, or have any medical
response against the suture material resulting in poor disorders with pregnancy as DM, HTN with pregnancy.
cosmoses [6,10]. The number of sutures was counted using a dou-
Evidence-based studies conclude and support the ble-check method by a team of members composed
fact that suture closure of the subcutaneous fat layer of a resident and a nurse in the operating room and
during the CS decreases the risk of wound infection counting sutures in the continuous technique was
and disruption in women with a subcutaneous tissue based on counting each loop as one suture when it
deeper than 2cm [6,10,19], the effect of this interven- passes from edge to edge through the subcutaneous
tion on esthetic outcome is not adequately explored tissue, so we aimed at unification of the statistical
in research studies [6,10,19]. terms in suturing by using a term of number of
sutures in both the interrupted and continuous groups
(as we considered loop as suture when it passes from
Patients and methods
edge to edge). Calculation of depth of subcutaneous
This is a prospective randomized study that was con- tissue was estimated by a special device used (a steri-
ducted in at multicenters in Algazeerah Hospital, lized operative ruler).
Al Hussein Hospital and Kasralainy Hospital in Egypt. Blood loss was estimated, operative time was
Four hundred pregnant women were recruited for this recorded; all patients had preoperative antibiotic
study who accepted to share in the present study in prophylaxis within 30min of incision time.
the period from June 2017 to December 2017 to com- Continuous or interrupted method was chosen
pare continuous versus interrupted suturing of the according to the randomization of patients.
subcutaneous layer in CS using Vicryl 3-0 in obese Randomization of cases was done to the 400 pregnant
Egyptian women. women who were consented to participate in the
study and were distributed in two groups: group A
and group B. The randomization allocation was 1:1.
Consent
The two groups were randomly selected, 200 in each
All pregnant women who accepted to participate in group. Two cases from the continuous group and one
this study signed an informed consent after complete case from the interrupted group did not come for the
explanation of the procedure to the participant follow up after CS and they were living far away from
woman. the hospital and continued their follow up in another
Ten surgeons performed the whole procedure of CS near by hospital to their homes so we excluded them
including the closure of subcutaneous and skin layer, from the results. The net of the continuous group was
all these surgeons were the consultants and specialists 198 and that of the interrupted group was 199 ladies
in Kasralainy Hospital, Alhussein Hospital and and this is illustrated in Figure 1.
Algazeerah Hospital. No residents were responsible for Care of the incision in the hospital was performed
performing the procedure, the residents only were by keeping the wound dry and covering it with a steri-
assistants in the surgery. The surgeons had a standard lized dressing (steripad). Preoperative prophylactic
operative procedure according to nice guidelines with dose of intravenous cephalosporins (before giving the
a Pfannenstiel skin incision which was made to all anesthesia) and two postoperative doses of IV

--- Page 4 ---
2454 M.ALALFYETAL.
All patients who are eligible to participate
Enrollment
in the study
Assessed (N= 411)
Excluded (N =11)
Refused to participate
Randomized
N= 400
Allocation
-Allocated to interrupted Technique
Allocated to continous
N=200
Technique
-Received allocated technique N=200
N=200
-Received allocated technique N=200
Follow up
Lost follow up ( did not come Lost follow up ( did not come to
to follow up postoperative follow up postoperative ,patient from
,patient from distant village distant village away from hospital )
away from hospital ) ( N= 1) (N= 2)
Analysis
Analysed (N=199 ) Analysed (N=198)
Figure 1. Consort flow diagram.
cephalosporins were given to each woman after sensi- hardening of the surrounding area, yellowish, or green
tivity skin test. Patients were discharged from hospital discharge, unusual increasing pain, excessive bleeding,
48h postoperatively. if there is a change in the incision size or fever, then
All patients were requested about the care of the asked to come to hospital for inspection of the wound
wound after discharge from the hospital by keeping it 1 week postoperative and then to visit the hospital
dry for 1 week and, after prophylactic oral antibiotic 10d postoperatively for stitches removal.
intake, patients were instructed to come to hospital Thetimeintervalfromthewoundclosuretilldiagno-
when there is any warning sign as wound redness or sis of the wound complications (erythema, seroma,

--- Page 5 ---
THEJOURNALOFMATERNAL-FETAL&NEONATALMEDICINE 2455
wound infection, and wound gapping) in most of the Table 1. Descriptive analysis of wound complications in rela-
patients was 7d (at first visit postoperative); however, tion to suture technique.
one of the ladies came to hospital when she noticed Variables Description(n=397)afterexclusionof3cases
redness of wound 5d postoperatively and another lady SutureType
Continuous 198(49.9)afterlostfollowupof2women
came complaining of discharge from the wound diag- Interrupted 199(50.1)afterlostfollowupof2women
nosedtohavewoundinfection6dpostoperatively. WoundGapping
Yes 12(3)
No 385(97)
Aim of the research Woundseroma
Yes 10(2.5)
The main goal of our work was to display the differ- No 387(97.5)
Wounderythema
ence in wound outcome results as regard postopera-
Yes 18(4.5)
tive wound complications comparing the two widely No 379(95.5)
implemented techniques in subcutaneous tissue clos- Woundinfection
Yes 20(5)
ure (interrupted versus continuous methods).
No 377(95)
Woundcomplications
Yes 42(10.6)
Results
No 355(89.4)
Description
Table 2. Demonestrates analysis of the demographic data
Table 1 describes and displays the following variables: and operative parameters.
type of suturing: wound complications in both study Variables Range Mean±SD Median
groups wound gapping, seroma, erythema, infection. Age(years) 25.0–35.0 30.3±3.3 30.0
BMI 23.0–45.0 34.5±3.6 34.0
Continuous and interrupted groups are nearly similar GestationalageattimeofCS 35.0–39.7 37.7±1.1 38.0
in the number of study subjects involved, wound gap- No.ofsuturessubcutaneous 3.0–13.0 6.3±2.9 5.0
Operativetime(min) 30.0–60.0 42.8±10.4 40.0
ping occurred in 12% of cases, wound seroma Estimatedbloodloss(cc) 350.0–1000.0 658.8±165.2 650.0
occurred in 10% of cases, wound erythema occurred Subcutaneoustissuedepth(cm) 2.0–6.5 4.4±1.0 4.5
in 18% of cases, and wound infection occurred in 20%
Table 3. Shows a comparison between continuous and inter-
of cases in the whole cohort of cases.
rupted techniques as regard operative parameters and demo-
Table 2 displays and demonstrates the following graphic data.
study variables: age, BMI, GA at time of CS, number of
Suturetype
sutures in subcutaneous tissue operative time, esti-
Continuous Interrupted pvalue
mated blood loss, and subcutaneous tissue depth. The
Age(years) 30.2±3.2 30.4±3.4.444
mean age of the whole cohort studied=30.3±3.3 BMI 34.8±3.9 34.2±3.3.101
years, mean BMI=34.5, mean gestational age at time GestationalageattimeofCS 37.6±1.1 37.8±1.114
No.ofsubcutaneoussutures 6.3±3 6.3±2.8.791
of CS 37.7±1.1 weeks, mean number of sutures of Operativetime(min) 40.1±9.2 45.5±10.8 <.001
subcutaneous tissue=6.3±2.9, operative time (min) Estimatedbloodloss(cc) 644.4±164.2 673.1±165.4.084
Subcutaneoustissuedepth(cm) 4.5±1 4.4±0.9.127
mean=42.8±10.4min, estimated blood loss (cc)
mean=658.8±165.2cc, subcutaneous tissue depth
Table 4. Display a comparison between between continuous
(cm) mean=4.4±1.0cm. and interrupted techniques regarding wound complications.
Table 3 compares the following variables: between Suturetype
continuous and interrupted sutures including age, BMI,
Continuous Interrupted
GA at the time of CS, number of sutures in subcutane- (n=198) (n=199) pvalue OR 95%CIofOR
ous tissue operative time (min), estimated blood loss Woundgapping 10(5.1) 2(1) .019 5.239 1.133–24.227
Woundseroma 9(4.5) 1(0.5) .011 9.429 1.183–75.138
(cc), subcutaneous tissue depth (cm), and showing Wounderythema 14(7.1) 4(2) .015 3.709 1.199–11.475
statistical significant difference only regarding opera- WoundInfection 17(8.6) 3(1.5) .001 6.136 1.769–21.287
tive time with p value¼<.001. OR:oddsratio;CI:confidenceinterval.
Table 4 displays and contrasts comparative analysis
between continuous and interrupted regarding wound OR=9.429, wound erythema OR=3.709, and wound
complications (gapping, seroma, erythema, and infec- infection OR=6.136.
tion) showing statistical significant differences in all Table 5 represents univariant analysis as regard
four wound complications presented with p values¼ wound complications and statistical significant differ-
.019, .011, .015, and .001, in consecutive order with ence was observed as regard BMI p value¼<.001,
odds ratio in wound gapping=5.239, wound seroma number of sutures with p value=.005, estimated

--- Page 6 ---
2456 M.ALALFYETAL.
Table 5. Shows univariate determinants of wound difference with a p value¼<.001. That reflects
complications. reduced operative time in the continuous group of
Woundcomplications patients in which the mean time in the continuous
Yes(n=42) No(n=355) pvalue group=40.1±9.2min and the interrupted group¼
Age(years) 29.9±3.5 30.3±3.2.336 45.5±10.8min. But as regard wound gapping, statistic-
BMI 37.8±3.9 34.1±3.4 <.001
ally significant difference has been observed with the
GestationalageattimeofCS 38±1 37.7±1.1.077
No.ofsuturessubcutaneous 5.1±2.4 6.4±2.9.005 number in the continuous group=10 cases (5.1%),
Operativetime(min) 44.8±9.9 42.5±10.4.141 number in the interrupted group¼two cases (1%),
Estimatedbloodloss(cc) 754.8±179 647.5±160 <.001
Subcutaneoustissuedepth(cm) 5±1 4.4±1 <.001 p value=.019; in addition, wound seroma showed
Suturetype statistically significant difference in the number of the
Continuous 33(78.6) 165(46.5) <.001
continuous group with a mean=9 cases (4.5%), mean
Interrupted 9(21.4) 190(53.5)
of the interrupted group=1 case (0.5%), p value¼
Table 6. Multivariate analysis (logistic regression model) to .011; wound erythema displayed also statistically sig-
explore predictors of wound complications. nificant difference in the number of the continuous
OR 95%CIforOR pvalue group=14 cases (7.1%); number in the interrupted
Age(years) 1.005 0.887–1.138.943 group=4 cases (2%), p value=.015; lastly the number
BMI 1.333 1.188–1.494 <.001
GestationalageattimeofCS 1.359 0.896–2.062.149 of cases that had wound infection in the continuous
No.ofsuturessubcutaneous 1.020 0.805–1.293.870 group=17 cases (8.6%) and number in the interrupted
O Es p ti e m ra a t t i e ve d t b im lo e od (m lo in ss ) (cc) 1 1 . . 0 0 0 3 8 7 1 0 . . 0 9 0 8 5 7– – 1 1 . . 0 0 8 1 9 0 <. . 0 14 0 6 1 group=3 cases (1.5%), p value=.001.
Subcutaneoustissuedepth(cm) 1.855 1.171–2.940.009 Univariant analysis as regard wound complications
ContinuousVSInterruptedSutures 7.743 3.030–19.788 <.001
displayed statistically significant difference that had
been observed regarding BMI with a p value¼<.001,
blood loss (cc)<0.001, subcutaneous tissue depth number of sutures with p value=.005, estimated
(cm) p value¼<.001, and continuous suture type blood loss (cc)<0.001, subcutaneous tissue
p value¼<.001. depth (cm) p value¼<.001, continuous suture type
Table 6 displays and reveals multivariate analysis to p value¼<.001.
explore predictors of wound complications showing Similarly, other authors made a research in which
BMI of statistical significance with p value¼<.001, they categorized the study subjects into two groups
OR=1.333, estimated blood loss (cc) of statistical sig- (subcutaneous tissue closure group versus non-closure
nificance with p value¼<.001, subcutaneous tissue of subcutaneous tissue), in addition they compared
depth (cm) of statistical significance with p value¼ between skin closure with staples or intra-cutaneous
.009, OR=1.855, continuous versus interrupted sutures sutures, the researchers compared the following varia-
of statistical significance with p value¼<.001, bles similar to our study in some items such as opera-
OR=7.743.
tive time and wound complications, and other items
were added that were not performed in our study
such as postoperative pain; in addition, they observed
Discussion
and evaluated long-term cosmetic out come and it
The results of the present study displayed the follow- was evaluated 1 year postoperatively using the Patient
ing after interpretation and analysis of data in the and Observer Scar Assessment Scale (POSAS) and
whole cohort of cases studied: the percentage of Numeric Rating Scale (NRS). Similar to the number of
wound gapping occurred in 12% of cases, wound cases recruited in our study, they recruited a total of
seroma occurred in 10% of cases, and wound ery- 218 women, in which they observed the following
thema occurred in 18% of cases, while wound infec- findings: no statistical significant difference as regard
tion occurred in 20% of cases. The mean age of the long-term cosmetic results between the study research
whole cohort studied was 30.3±3.3 years, mean categories closure techniques investigated, except for
BMI=34.5, mean gestational age at the time of CS closure time, there were no observed differences in
was 37.7±1.1 weeks, mean number of sutures of sub- other secondary outcome measures. They concluded
cutaneous tissue=6.3±2.9, operative time (min) mean the following at CS performance: suturing the subcuta-
was 42.8±10.4min, estimated blood loss (cc) mean neous tissue or not and using staples or intracutane-
equals 658.8±165.2cc, and subcutaneous tissue depth ous sutures results in a similar long-term cosmetic
(cm) mean=4.4±1.0cm. Statistical significant differ- appearance of the resultant scar [9].
ence between continuous and interrupted groups as Another research performed to investigate obese
regard operative time showed statistical significant patients wound. Surgical drainage was conducted as

--- Page 7 ---
THEJOURNALOFMATERNAL-FETAL&NEONATALMEDICINE 2457
follows: an electronic exploration was applied on No statistical differences were observed concerning
research; articles comparing subcutaneous tissue incision cosmetic appearance and women’s satisfac-
prophylactic drainage with no drainage performed tion. They concluded from their research performed
were recognized and categorized by level of evidence. that staples are the methodology of choice for skin
If adequate randomized controlled research trials were closure for elective term cesareans in their investigated
involved, a meta-analysis was conducted applying the cohort [21].
random-effects model. Fifty-two randomized controlled Similarly, another group of researchers conducted a
research trials were integrated in a meta-analysis, and study evaluating and assessing the impact of some
sub-categories were defined by particular surgical particular gestational and other factors correlated with
approaches including CS and other surgical proce- in adequate wound healing process in cases delivered
dures. Research studies were put in comparison as by CS. Their study design was as an observational, pro-
regard the following out comes and variables for the spective research study at the University Hospital of
following wound complications: hematoma formation, Messina with a recruitment of 212 women at term giv-
wound healing morbidities, seroma, abscess, and infec- ing birth by elective cesarean delivery. The method-
tion. A total of 6930 operations were investigated by ology conducted was implemented by collecting data
the research group as appropriate for this statistical concerning demographic and gestational parameters
research analysis. There were 3495 operations in the were at hospital admission, and subcutaneous tissue
drain category and 3435 in the no-drain group. depth was measured intra-operatively from fascia to
Prophylactic subcutaneous drainage displayed a statis- the surface of skin, while the length of surgical incision
tically significant privilege only for (1) avoidance of was measured after skin closure. The following out-
hematoma formation in breast biopsy surgical proce- comes were measured and observed including wound
dures and (2) prevention and avoidance of seromas in morbidities for example infection, seroma collection,
axillary node surgical dissections. However, in all other hematoma formation, abscess, or wound dehiscence
procedures observed and investigated including CS in >1cm. The results obtained and displayed by their
obese patients, drainage did not show any acquired research group were body mass index (BMI) at term
advantage, denoting that CS operations can be con- [odd ratio (OR) 1.2, 95%CI 1.03–1.38; p=.01], wound
ducted with great security without applying prophy- length (OR 1.03, 95%CI 1.01–1.05; p<.001), and cor-
lactic surgical drainage. Therefore, the meta-analysis ticosteroid administration (OR 3.4, 95%CI 1.5–7.9;
implied that obstetricians believed omitting drainage p=.004) were revealed to be linked with various
after CS performance, Interestingly, in addition, sur- wound complications observed. The receiver operating
geons are not obligated to place surgical drains characteristics curve analysis uncovered a cut-off value
prophylactically in obese cases. On the other hand, of 31.1 for the BMI at term and 166mm for the wound
surgical drain placement after a surgical procedure length with an OR of 2.28 (95%CI 1.18–4.39; p=.013)
performed is the surgeon’s option and can be based and 4.3 (95%CI 2.2–8.6; p<.001), consecutively. The
on various factors [20]. multivariate logistic regression model, conducted and
Another research randomized controlled trial of 101 implemented on these observed variables and to
women was conducted. Cases were randomly recruited administration of corticosteroid, presented an inde-
to subcuticular suturing or staples. Operative mode pendent statistical interrelation and association (at
and approach and postoperative analgesia were term BMI>31.1: OR 2.04, 1.01–4.13, p=.047; surgical
homogeneous. Stratification was performed for pri- wound length >166mm: OR 4.89, 2.36–10.14, p<.001;
mary versus repeat cesarean deliveries. The difference administration of corticosteroids: OR 3.11, 1.38–6.95,
in this research is that postoperative pain was the p=.006). They concluded that in order to prevent
main variable to be investigated Analog pain and sat- postoperative wound complications surgeons perform-
isfaction scales ranging from 0 to 10 were completed ing the procedure should be cautious in steroid
at postoperative days 1 and 3, and at 6 weeks postop- administration before implementation of surgery, as
eratively. A digital photographic copy of the surgical regard length of skin incision that should be made as
incision was taken at 6-week postoperative time and small as possibly achievable and in cautiously monitor-
assessed by three independent blinded research ing and clinically observing pregnancy BMI [22].
observers. The research group concluded the following In the present study, multivariate analysis to explore
that pain at 6 weeks postoperatively was statistically predictors of wound complications showed that BMI
significantly less in the staple category (0.17 versus has a statistical significance with p value¼<.001,
0.51; p=.04). Operative time was significantly shorter OR=1.333, estimated blood loss (cc) has a statistical
in that category (24.6 versus 32.9min; p<.0001). significance with p value¼<.001, subcutaneous tissue

--- Page 8 ---
2458 M.ALALFYETAL.
depth (cm) has a statistical significance with Disclosure statement
p value=.009, OR=1.855, continuous versus inter-
All authors declare that there are no any financial and per-
rupted sutures has a statistical significance with
sonal relationships with other people or organizations that
p value¼<.001, OR=7.743. couldinappropriately influence(bias)their work.
So in the present study, the previously mentioned
results denote that all wound complications are signifi-
ORCID
cantly less when interrupted mode of suturing is
MahmoudAlalfy http://orcid.org/0000-0002-8429-6376
applied although operative time is significantly
Omar Nagy http://orcid.org/0000-0002-6028-6421
observed to be much prolonged in interrupted group,
additionally BMI could be used as a predictor tool for
wound complications. Estimated blood loss by the sur-
References
geon was a prominent parameter for the prediction of
wound complications. In our research, subcutaneous [1] Brown BC, Moss TP, McGrouther DA, et al. Skin scar
tissue depth and suturing technique are even tools preconceptions must be challenged: importance of
that can be implemented in predictability of wound selfperception in skin scarring. J Plast Reconstr
AesthetSurg.2010;63(6):1022–1029.
complications. In the future, all variables that revealed
[2] Yamasato K, Yoshino K, Chang AL, et al.
value in predictability of wound complications could
Cesarean delivery complications in women with mor-
be adjusted in broader studies to be clinically used to bid obesity. J Matern Fetal Neonat Med. 2016;29(23):
predict and manage wound morbidities helping to cal- 3885–3888.
culate the risk of wound complications leading to [3] Mackeen AD, Berghella V, Larsen ML. Techniques and
materials for skin closure in caesarean section.
better management of obese patients surgically
Cochrane Database Syst Rev. 2012;11:CD003577:
particularly preoperative preparation, intra-operative
CD003577.
management technique of closure, and postoperative [4] CORONIS Collaborative Group, Abalos E, Addo V, et al.
care providing a guidance in effectively managing Caesarean section surgical techniques (CORONIS): a
fractional, factorial, unmasked, randomised controlled
these cases by using a special formula integrating
trial.Lancet.2013;382(9888):234–248.
these predictors.
[5] Figueroa D, Jauk VC, Szychowski JM, et al. Surgical
staples compared with subcuticular suture for skin
closure after cesarean delivery: a randomized con-
Conclusions trolledtrial.Obstet Gynecol.2013;121(1):33–38.
[6] Cromi A, Ghezzi F, Gottardi A, et al. Cosmetic out-
Subcutaneous tissue closure in our study groups
comes of various skin closure methods following
revealed that subcutaneous wound closure using cesarean delivery: a randomized trial. Am J Obstet
interrupted technique of suturing in obese patients is Gynecol.2010;203(1):36.e1–36.e8.
superior to continuous technique as regard wound [7] Menacker F, Hamilton BE. Recent trends in cesarean
delivery in the United States. NCHS data brief, no 35.
complications; however, operative time is more.
Hyattsville, MD: National Center for Health Statistics;
Future research should include more variables that
2010.
could play a role such as ethnic differences, and [8] Wloch C, Wilson J, Lamagni T, et al. Risk factors for
operator performance variability, postoperative wound surgical site infection following caesarean section in
England: results from a multicentre cohort study.
pain, and cosmetic results with a more wide cohort
BJOG.2012;119(11):1324–1333.
of patients.
[9] Huppelschoten AG, van Ginderen JC, van den Broek
The variables used in the present study could be
KC, et al. Different ways of subcutaneous tissue and
implemented in the future to calculate the risk of skin closure at cesarean section: a randomized clinical
wound infection in obese pregnant women perform- trial on the long-term cosmetic outcome. Acta Obstet
GynecolScand.2013;92(8):916–924.
ing a CS. This will result in applying better manage-
[10] Gaertner I, Burkhardt T, Beinder E. Scar appearance of
ment protocols for obese cases with a special
different skin and subcutaneous tissue closure techni-
preoperative preparation, intra-operative closure tech-
ques in caesarean section: a randomized study. Eur J
nique, and postoperative care. ObstetGynecolReprod Biol.2008;138(1):29–33.
[11] de Graaf IM, Oude Rengerink K, Wiersma IC, et al.
Techniques for wound closure at caesarean section: a
Acknowledgements randomized clinical trial. Eur J Obstet Gynecol Reprod
Biol.2012;165(1):47–52.
The authors would like to thank all medical staff members [12] Islam A, Ehsan A. Comparison of suture material
who helped usin completingthisresearch. and technique of closure of subcutaneous fat and

--- Page 9 ---
THEJOURNALOFMATERNAL-FETAL&NEONATALMEDICINE 2459
skin in caesarean section. N Am J Med Sci. 2011; [18] Conner SN, Verticchio JC, Tuuli MG, et al. Maternal
3(2):85–88. obesity and risk of postcesarean wound complica-
[13] Veisi F, Zangeneh M, Malekkhosravi S, et al. tions.AmJPerinatol.2014;31(4):299–304.
Subcutaneous Vicryl suture covering efficacy on [19] Corbacioglu Esmer A, Cilesiz Goksedef P, Akca A, et al.
wound complications after cesarean section. Role of subcutaneous closure in preventing wound
JKermanshah UnivMedSci.2016;15:157–164. complications after cesarean delivery with
[14] Mathai M, Hofmeyr GJ, Mathai NE. Abdominal surgical Pfannenstiel incision: a randomized clinical trial.
incisions for caesarean section. Cochrane Database JObstetGynaecol Res.2014;40(3):728–735.
SystRev.2007;1:CD004453. [20] Kosins AM, Scholz T, Cetinkaya M, et al. Evidence-
[15] Tuuli MG, Stout MJ, Martin S, et al. Comparison of based value of subcutaneous surgical wound drain-
suture materials for subcuticular skin closure at cesar- age: the largest systematic review and meta-analysis.
ean delivery. Am J Obstet Gynecol. 2016;215(4): PlastReconstrSurg. 2013;132(2):443–450.
490.e1–490.e5. [21] Rousseau J-A, Girard K, Turcot-Lemay L, et al.
[16] Abdelrahman RM. Closure versus non-closure of sub- A randomized study comparing skin closure in cesar-
cutaneous tissue after cesarean section in diabetic ean sections: staples vs subcuticular sutures. Am J
patients.NCT02664285.2016. ObstetGynecol.2009;200(3):265.e1–265.e4.
[17] Wu X, Kubilay NZ, Ren J, et al. Antimicrobial-coated [22] De Vivo A, Mancuso A, Giacobbe A, et al. Wound
sutures to decrease surgical site infections: a system- lengthandcorticosteroidadministration asrisk factors
atic review and meta-analysis. Eur J Clin Microbiol for surgical-site complications following cesarean sec-
InfectDis.2017;36(1):19–32. tion.ActaObstetGynecolScand. 2010;89(3):355–359.


## Extracted tables


### Page 4, table 1

|  | Follow up |
| Lost follow up ( did not come
to follow up postoperative
,patient from distant village
away from hospital ) ( N= 1) |  |