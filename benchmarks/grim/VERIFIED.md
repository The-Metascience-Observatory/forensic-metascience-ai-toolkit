# GRIM ground truth: verified papers

**21 papers with verified GRIM errors** (20 in `literature_2026-10`, 1 in the internal `kelly_pcit` set), holding 214 verified failing values. In the corpus folder `agent_for_forensic_metascience_papers/grim_ground_truth/`, the literature set's 20 are split 10/10 into `literature_2026-10/verified_dev/` and `verified_holdout/` (`literature_2026-10/splits.json`), and the Kelly paper is in `kelly_grim/verified/`. Built 2026-10-17 and 2026-10-18; every claim below traces to `labels.jsonl` and the set's `build_labels.py`.

A GRIM error here is a fact about printed numbers: the paper prints a mean or percentage that no set of whole-number observations at the paper's own n can produce. It is not a finding about anyone's conduct. Where the cause came out, it was usually a misreported n, not a wrong mean.

## What "verified" means

A paper is verified when at least one labelled value passes all four checks, or a paper-level proof stands (Banerjee 2012, below):

1. **Arithmetic.** It fails GRIM under both round-half and truncation, recomputed with the toolkit's own functions (`verify_labels.classify`). A value that fails only round-half is not counted: the tool treats truncation as a legitimate convention.
2. **A printed n.** The n is printed in the paper, not borrowed from another paper, assumed, or derived from degrees of freedom.
3. **Whole-number data.** The paper's own description makes the observations integers (counts, single-item ratings, totals of integer items), not averages, model estimates or imputed values.
4. **The value is in the paper.** Found in the paper's text (XML incl. tables, or `pdftotext`), or read by eye where the text layer is garbled; short values were also checked at their labelled row and column.

The labels came from third parties (critiques, journal notices, PubPeer, Kelly's survey); checks 1-4 were done here. Strength of the third-party evidence:

| Evidence | Papers |
|---|---|
| `confirmed_error`: confirmed by a correction, retraction notice or the authors' data | 7 |
| `journal_action`: an expression of concern or retraction cites the problems | 6 |
| `published_critique`: peer-reviewed or preprint critique only | 4 |
| `unresolved_concern`: blog post or PubPeer comment only | 4 |

## How the set was built

1. **Search (2026-10-17).** Three literature searches: Wansink's Cornell lab ("Statistical heartburn", Anaya, van der Zee); Brown, Heathers and Anaya's own cases and journal notices; PubPeer threads and published audits. Each value was copied from a named source with its URL (`literature_2026-10/sources/`).
2. **Arithmetic and tiers.** Every cell recomputed under both conventions and tiered (`primary`, `rounding_only`, `inferred_n`, `doubtful_premise`, `excluded`, `false_alarm`).
3. **Papers fetched (2026-10-18)** with fetchpdf2; each matched its label's title. 262 of 279 values found automatically in the text; 15 more read by eye where the text layer garbles them; 2 not in the paper at all (excluded).
4. **Manual confirmation (2026-10-18).** Every paper whose label rested on an unconfirmed premise was read for it. Outcomes in the table at the end and in each paper's `manual_check`.
5. **Kelly's PCIT survey (internal).** Kelly's 2023 revision itemises 31 flagged means for four anonymised papers; they were identified by matching (N, mean) values against Kelly's 89 search results. 25 of the 31 turned out to be false alarms. Kept outside git under an embargo marker.

## Dev and holdout

The 20 literature papers are split 10/10 at random (seed 20261018), keeping papers that share data on the same side: the four Wansink pizza papers (one dataset) and the two Strauer stem-cell trials (overlapping patients). Holdout reviews are not inspected, scored or tuned against until the final test. Score a split with `score.py --split dev`.

- **dev**: 10 papers (9 with scorable values), 160 verified values; the largest is 10.1007/s00404-012-2277-7 with 100
- **holdout**: 10 papers (10 with scorable values), 50 verified values; the largest is 10.1038/sj.ijo.0803217 with 11

A paper verified only at paper level has no scorable value. The split was not re-drawn to even out the halves: choosing among draws would spend the holdout.

## The verified papers

### 1. Just, D., Sığırcı, Ö., & Wansink, B. (2014). Lower Buffet Prices Lead to Less Taste Satisfaction. *Journal of Sensory Studies*, 29(5), 362-370. https://doi.org/10.1111/joss.12117

- Split: **dev**
- Evidence: `confirmed_error`: 2017 erratum cites the critique and gives per-row n.
- Outcome: corrected (erratum, 2 Aug 2017); not retracted per the Retraction Watch database records exposed by Crossref (checked 2026-10-17)
- Verified values: 5 (3 in Table 1, 2 in Table 2); value check: 5 by text.
  - 57.4% at n = 62 (Table 1, Gender (male percent), $4 buffet column (N = 62))
  - 47.9% at n = 60 (Table 1, Gender (male percent), $8 buffet column (N = 60))
  - 6.64 at n = 60 (Table 1, 'I was hungry when I came in', $8 buffet column (N = 60))
  - 7.44 at n = 60 (Table 2, 'The pizza, in general, tasted really great', $8 buffet column (N = 60))
  - 7.34 at n = 60 (Table 2, 'The first piece of pizza I ate was very satisfying', $8 buffet column (N = 60))

### 2. Just, D., Sigirci, O., & Wansink, B. (2015). Peak-end pizza: prices delay evaluations of quality. *Journal of Product & Brand Management*, 24(7), 770-778. https://doi.org/10.1108/JPBM-01-2015-0802

- Split: **dev**
- Evidence: `confirmed_error`: 2017 correction says Table I reported the wrong n.
- Outcome: corrected (correction notice attached to the article, July 2017); not retracted per Retraction Watch database records exposed by Crossref
- Verified values: 1 (1 in Table I (copy of Article 1 Table 1)); value check: 1 by text.
  - 6.64 at n = 60 (Table I (copy of Article 1 Table 1), 'I was hungry when I came in', $8 buffet (n = 60))

### 3. Kniffin, K., Sigirci, O., & Wansink, B. (2016). Eating Heavily: Men Eat More in the Company of Women. *Evolutionary Psychological Science*, 2(1), 38-46. https://doi.org/10.1007/s40806-015-0035-3

- Split: **dev**
- Evidence: `published_critique`: Statistical heartburn (BMC Nutrition 2017); editorial note silent on statistics.
- Outcome: editorial note (24 Apr 2017), recorded as a correction by Retraction Watch; not retracted per Retraction Watch database records exposed by Crossref
- Verified values: 12 (7 in Table 2, 5 in Table 3); value check: 12 by text.
  - 1.46 at n = 40 (Table 2, 'I felt rushed', Males eating with females (N = 40))
  - 2.11 at n = 40 (Table 2, 'I am physically uncomfortable', Males eating with females (N = 40))
  - 2.76 at n = 20 (Table 2, 'I overate', Males eating with males (N = 20))
  - 2.27 at n = 20 (Table 2, 'I am physically uncomfortable', Males eating with males (N = 20))
  - 2.73 at n = 35 (Table 2, 'I overate', Females eating with males (N = 35))
  - 1.18 at n = 10 (Table 2, 'I felt rushed', Females eating with females (N = 10))
  - ... and 6 more in `labels.jsonl`

### 4. Siğirci, Ö., & Wansink, B. (2015). RETRACTED ARTICLE: Low prices and high regret: how pricing influences regret at all-you-can-eat buffets. *BMC Nutrition*, 1(1), 36. https://doi.org/10.1186/s40795-015-0030-x

- Split: **dev**
- Evidence: `confirmed_error`: 2017 retraction notice cites the critique.
- Outcome: retracted (15 Sep 2017)
- Verified values: 21 (11 in Table 3, 10 in Table 2); value check: 21 by text.
  - 2.63 at n = 18 (Table 2, 'I ate more pizza than I should have', $4 One piece (n = 18))
  - 4.82 at n = 18 (Table 2, 'I ate more pizza than I should have', $4 Two pieces (n = 18))
  - 2.26 at n = 17 (Table 2, 'I feel guilty about how much I ate', $8 One piece (n = 17))
  - 1.97 at n = 17 (Table 2, 'I am physically uncomfortable', $8 One piece (n = 17))
  - 1.67 at n = 17 (Table 2, 'I overate', $8 One piece (n = 17))
  - 1.45 at n = 19 (Table 2, 'I am physically uncomfortable', $8 Two pieces (n = 19))
  - ... and 15 more in `labels.jsonl`

### 5. Wansink, B., Painter, J., & Lee, Y. (2006). The office candy dish: proximity's influence on estimated and actual consumption. *International Journal of Obesity*, 30(5), 871-875. https://doi.org/10.1038/sj.ijo.0803217

- Split: **holdout**
- Evidence: `unresolved_concern`: Anaya blog post.
- Outcome: none found (no correction or retraction in Crossref / Retraction Watch database records, checked 2026-10-17)
- Verified values: 11 (11 in Table 1); value check: 11 by eye.
  - 4.96 at n = 40 (Table 1, 'It was difficult to resist eating them', Proximate (placed on-desk), Visible (clear bowl))
  - 3.91 at n = 40 (Table 1, 'It was difficult to resist eating them', Proximate (placed on-desk), Non-visible (opaque bowl))
  - 3.74 at n = 40 (Table 1, 'I thought of eating the chocolates often', Proximate (placed on-desk), Non-visible (opaque bowl))
  - 4.39 at n = 40 (Table 1, 'I actually forgot they were around', Proximate (placed on-desk), Non-visible (opaque bowl))
  - 3.96 at n = 40 (Table 1, 'They kept attracting my attention', Proximate (placed on-desk), Non-visible (opaque bowl))
  - 2.04 at n = 40 (Table 1, 'They kept attracting my attention', Less proximate (placed 2 m from desk), Non-visible (opaque bowl))
  - ... and 5 more in `labels.jsonl`
- Manual check: n confirmed as printed: 40 participants in a within-subject design, each given the 9-point questionnaire every week, analysed by repeated-measures MANOVA (complete cases, so one common n of at most 40). At n = 40, 11 of the 32 Table 1 means fail both conventions -- exactly the 11 labelled. Of every n from 5 to 40, only n = 23 fits: 0 fail both, 3 fail round-half. The means were almost certainly computed on 23 responses; the printed n is 40.

### 6. Wansink, B., & Payne, C. (2008). Eating Behavior and Obesity at Chinese Buffets. *Obesity*, 16(8), 1957-1960. https://doi.org/10.1038/oby.2008.286

- Split: **holdout**
- Evidence: `confirmed_error`: 2017 corrigendum: column n were maxima, gives true per-cell n.
- Outcome: corrected (corrigendum, 26 Jun 2017)
- Verified values: 11 (11 in Table 2); value check: 11 by text.
  - 71.0% at n = 71 (Table 2, 'Browse buffet (vs. serve self immediately)', BMI bottom third (n = 71))
  - 86.3% at n = 71 (Table 2, 'Large plate (vs. only small)', BMI bottom third (n = 71))
  - 38.2% at n = 71 (Table 2, 'Sat at booth (vs. table)', BMI bottom third (n = 71))
  - 47.8% at n = 70 (Table 2, 'Sat at booth (vs. table)', Middle third (n = 70))
  - 15.9% at n = 72 (Table 2, 'Sat at booth (vs. table)', Top third (n = 72))
  - 23.5% at n = 71 (Table 2, 'Chopsticks (vs. fork)', BMI bottom third (n = 71))
  - ... and 5 more in `labels.jsonl`

### 7. Just, D., & Wansink, B. (2011). The Flat-Rate Pricing Paradox: Conflicting Effects of “All-You-Can-Eat” Buffet Pricing. *Review of Economics and Statistics*, 93(1), 193-200. https://doi.org/10.1162/REST_a_00057

- Split: **dev**
- Evidence: `unresolved_concern`: Anaya blog post.
- Outcome: none found (no notice in Crossref / Retraction Watch database records, checked 2026-10-17)
- Verified values: 3 (3 in Table 1); value check: 3 by text.
  - 6.43 at n = 31 (Table 1, '"I am very satisfied with the quality of pizza I ate"', Half-Price Buffet (n = 31))
  - 5.20 at n = 31 (Table 1, '"I ate more pizza than I should have"', Half-Price Buffet (n = 31))
  - 7.24 at n = 35 (Table 1, '"I ate enough pizza to get my money's worth"', Regular Price Buffet (n = 35))

### 8. Wansink, B., van Ittersum, K., & Painter, J. (2006). Ice Cream Illusions. *American Journal of Preventive Medicine*, 31(3), 240-243. https://doi.org/10.1016/j.amepre.2006.04.003

- Split: **holdout**
- Evidence: `unresolved_concern`: Anaya blog post.
- Outcome: none found (no notice in Crossref / Retraction Watch database records, checked 2026-10-17)
- Verified values: 6 (6 in Table 1); value check: 6 by text.
  - 2.22 at n = 20 (Table 1, 'Spoonfuls served: Number', Small bowl 17 oz, Small spoon (n = 20))
  - 1.90 at n = 26 (Table 1, 'Spoonfuls served: Number', Small bowl 17 oz, Large spoon (n = 26))
  - 5.37 at n = 20 (Table 1, 'How big was your bowl?', Small bowl 17 oz, Small spoon (n = 20))
  - 4.47 at n = 20 (Table 1, 'How big was your serving spoon?', Small bowl 17 oz, Small spoon (n = 20))
  - 6.11 at n = 20 (Table 1, 'My bowl is smaller/larger than normal', Small bowl 17 oz, Small spoon (n = 20))
  - 4.53 at n = 20 (Table 1, 'The serving spoon was smaller/larger than normal', Small bowl 17 oz, Small spoon (n = 20))

### 9. Wansink, B., van Ittersum, K., & Painter, J. (2005). How descriptive food names bias sensory perceptions in restaurants. *Food Quality and Preference*, 16(5), 393-400. https://doi.org/10.1016/j.foodqual.2004.06.005

- Split: **dev**
- Evidence: `confirmed_error`: 2017 corrigendum; it also says Table 1 holds adjusted means.
- Outcome: corrected (corrigendum, published online June 2017; FQP 62:379)
- Verified values: 4 (4 in Table 2); value check: 4 by text.
  - 54.3% at n = 56 (Table 2, 'Gender (% female)', Regular name (control group) (n = 56))
  - 46.7% at n = 84 (Table 2, 'Gender (% female)', Descriptive name (n = 84))
  - 61.5% at n = 56 (Table 2, 'Education (% high)', Regular name (control group) (n = 56))
  - 52.0% at n = 84 (Table 2, 'Education (% high)', Descriptive name (n = 84))

### 10. Eskine, K., Kacinik, N., & Prinz, J. (2011). A Bad Taste in the Mouth. *Psychological Science*, 22(3), 295-299. https://doi.org/10.1177/0956797611398497

- Split: **holdout**
- Evidence: `confirmed_error`: authors' dataset: group sizes swapped in the text.
- Outcome: none
- Verified values: 5 (4 in Table 1, 1 in Table 1 (Participants' Mean Taste Ratings of the Three Drinks)); value check: 5 by text.
  - 1.76 at n = 18 (Table 1 (Participants' Mean Taste Ratings of the Three Drinks), row 'Bitter taste', column 'Sweet drink')
  - 5.52 at n = 18 (Table 1, row 'Sweet taste', column 'Sweet drink')
  - 1.81 at n = 18 (Table 1, row 'Neutral taste', column 'Sweet drink')
  - 1.17 at n = 21 (Table 1, row 'Bitter taste', column 'Water')
  - 1.89 at n = 21 (Table 1, row 'Disgusting taste', column 'Water')

### 11. Banerjee, P., Chatterjee, P., & Sinha, J. (2012). Is It Light or Dark? Recalling Moral Behavior Changes Perception of Brightness. *Psychological Science*, 23(4), 407-409. https://doi.org/10.1177/0956797611432497

- Split: **dev**
- Evidence: `journal_action`: 2021 expression of concern itemises the GRIM failures.
- Outcome: expression of concern (2021-11-09)
- **Verified at paper level:** Study 2 (N = 74 from t(72)): no split of 74 between the two conditions makes all six single-item 7-point means (lamp 2.34/4.16, candle 2.37/3.62, flashlight 2.35/4.33) GRIM-consistent, under round-half or truncation; at least two fail at every split. Agrees with the journal's 2021 expression of concern.
- Manual check: Study 2 confirmed at paper level; Study 1 not (several splits of N = 40 fit 5.3 and 4.71).

### 12. Guéguen, N. (2012). Risk taking and Women’s Menstrual Cycle: Near Ovulation, Women Avoid a Doubtful Man. *Letters on Evolutionary Behavioral Science*, 3(1), 1-3. https://doi.org/10.5178/lebs.2012.17

- Split: **holdout**
- Evidence: `journal_action`: 2020 expression of concern itemises both cells.
- Outcome: expression of concern (2020-03-15)
- Verified values: 1 (1 in Table 1); value check: 1 by text.
  - 0.32 at n = 15 (Table 1, variable 'gaze-smile during interaction', high fertility risk group)

### 13. Festinger, L., & Carlsmith, J. (1959). Cognitive consequences of forced compliance. *The Journal of Abnormal and Social Psychology*, 58(2), 203-210. https://doi.org/10.1037/h0041593

- Split: **holdout**
- Evidence: `unresolved_concern`: Heino's annotated table.
- Outcome: none
- Verified values: 3 (2 in Table 1, 1 in Table 1 (Average Ratings on Interview Questions for Each Condition)); value check: 2 by text, 1 by eye.
  - 3.08 at n = 20 (Table 1 (Average Ratings on Interview Questions for Each Condition), row 'How much they learned (rated from 0 to 10)', column 'Control (N = 20)')
  - 5.18 at n = 20 (Table 1, row 'Scientific importance (rated from 0 to 10)', column 'Twenty Dollars (N = 20)')
  - -.62 at n = 20 (Table 1, row 'Participate in similar exp. (rated from -5 to +5)', column 'Control (N = 20)')
- Manual check: premise confirmed: each subject 'was asked to rate his opinion or reaction on an 11-point scale' (-5..+5 or 0..10), and 'There remain, for analysis, 20 Ss in each' condition. At n = 20 a mean is a multiple of .05.

### 14. Olgun Keleş, B., & Kaya, M. (2024). The Effect of Topical Benzydamine Hydrochloride and Cuff Pressure Monitorization on Postoperative Sore Throat Due to Intubation. *Cureus*. https://doi.org/10.7759/cureus.53725

- Split: **dev**
- Evidence: `confirmed_error`: 2026 retraction notice cites mathematically impossible percentages.
- Outcome: retracted (22 January 2026); notice cites "multiple mathematically impossible percentages with missing raw counts"
- Verified values: 12 (7 in Table 3, 5 in Table 2); value check: 12 by text.
  - 66.9% at n = 70 (Table 3, POST (postoperative sore throat), Group 3 (n=70))
  - 15.1% at n = 70 (Table 3, Hoarseness, Group 1 (n=70))
  - 17.2% at n = 70 (Table 3, Hoarseness, Group 2 (n=70))
  - 71.9% at n = 70 (Table 3, Hoarseness, Group 3 (n=70))
  - 15.8% at n = 70 (Table 3, Dysphagia, Group 1 (n=70))
  - 19.0% at n = 70 (Table 3, Dysphagia, Group 2 (n=70))
  - ... and 6 more in `labels.jsonl`

### 15. Gauhar, Y. (2016). The Efficacy of EMDR in the Treatment of Depression. *Journal of EMDR Practice and Research*, 10(2), 59-69. https://doi.org/10.1891/1933-3196.10.2.59

- Split: **holdout**
- Evidence: `journal_action`: retracted: editors lost confidence in the data.
- Outcome: retracted ("The editors have lost confidence in the integrity of the data presentation"; author could not provide raw data)
- Verified values: 1 (1 in Experimental group); value check: 1 by text.
  - 56.47 at n = 10 (Experimental group, pre-assessment Trauma Symptom Checklist-40 mean)

### 16. Teymourian, H., Mohajerani, S., & Farahbod, A. (2015). Magnesium and Ketamine Gargle and Postoperative Sore Throat. *Anesthesiology and Pain Medicine*, 5(3). https://doi.org/10.5812/aapm.5(3)2015.22367

- Split: **dev**
- Evidence: `journal_action`: 2026 expression of concern, assessment ongoing.
- Outcome: expression of concern (2026), assessment ongoing
- Verified values: 2 (2 in Table 1); value check: 2 by text.
  - 55% at n = 50 (Table 1, 'Male, %', Magnesium group (n = 50))
  - 52.5% at n = 50 (Table 1, 'Male, %', Ketamine group (n = 50))
- Manual check: n confirmed: Results print 'Fifty patients received ketamine and 50 received magnesium', with no exclusions. The values are Table 1's Male %, not Table 2 as the notice says; at n = 50 a percentage is a multiple of 2.

### 17. Strauer, B., Yousef, M., & Schannwell, C. (2010). The Acute and Long-Term Effects of Intracoronary Stem Cell Transplantation in 191 Patients with Chronic heARt Failure: The STAR-Heart Study. *European Journal of Heart Failure*, 12(7), 721-729. https://doi.org/10.1093/eurjhf/hfq095

- Split: **holdout**
- Evidence: `published_critique`: three peer-reviewed critiques; journal acted only on duplicate publication.
- Outcome: corrigendum (2013) about duplicate publication only; journal did not act on the internal discrepancies
- Verified values: 6 (6 in Table 1); value check: 6 by text.
  - 33.4% at n = 191 (Table 1, infarct-related coronary artery RCA, stem-cell recipients)
  - 31.2% at n = 200 (Table 1, infarct-related coronary artery RCA, controls)
  - 49.1% at n = 191 (Table 1, infarct-related coronary artery LAD, recipients)
  - 50.7% at n = 200 (Table 1, infarct-related coronary artery LAD, controls)
  - 17.5% at n = 191 (Table 1, infarct-related coronary artery RCX, recipients)
  - 18.1% at n = 200 (Table 1, infarct-related coronary artery RCX, controls)

### 18. Yousef, M., Schannwell, C., Köstering, M., Zeus, T., Brehm, M., & Strauer, B. (2009). The BALANCE Study. *Journal of the American College of Cardiology*, 53(24), 2262-2269. https://doi.org/10.1016/j.jacc.2009.02.051

- Split: **holdout**
- Evidence: `published_critique`: Francis et al. 2013.
- Outcome: none found
- Verified values: 5 (5 in Table 1); value check: 5 by text.
  - 32.6% at n = 62 (Table 1, infarct-related artery RCA, recipients)
  - 28% at n = 62 (Table 1, infarct-related artery RCA, controls)
  - 48.8% at n = 62 (Table 1, infarct-related artery LAD, recipients)
  - 18.6% at n = 62 (Table 1, infarct-related artery RCX, recipients)
  - 57% at n = 62 (Table 1, obesity, controls)

### 19. Shaaban, M., Ahmed, W., Khadr, Z., & El-Sayed, H. (2012). Obstetricians’ perspective towards cesarean section delivery based on professional level: experience from Egypt. *Archives of Gynecology and Obstetrics*, 286(2), 317-323. https://doi.org/10.1007/s00404-012-2277-7

- Split: **dev**
- Evidence: `journal_action`: 2026 expression of concern cites discrepancies.
- Outcome: editorial expression of concern (6 August 2026): "discrepancies in the numbers and percentages reported in Tables 2, 3, and 4"
- Verified values: 100 (94 in Table 3, 4 in Table 4, 2 in Table 2); value check: 100 by text.
  - 31.7% at n = 65 (Table 2, "Percent of CS in private practice", Total / MOH staff (N=65))
  - 35.2% at n = 167 (Table 2, "Percent of CS in private practice", Total / Total (N=167))
  - 55% at n = 41 (Table 3, "Accepting selected vaginal breech delivery", Consultant / University staff (N=41))
  - 59.4% at n = 66 (Table 3, "Accepting selected vaginal breech delivery", Consultant / Total (N=66))
  - 65.9% at n = 39 (Table 3, "Accepting selected vaginal breech delivery", Specialist / University staff (N=39))
  - 66.7% at n = 23 (Table 3, "Accepting selected vaginal breech delivery", Specialist / MOH staff (N=23))
  - ... and 94 more in `labels.jsonl`

### 20. Lola, A., & Tzetzis, G. (2025). The effect of explicit, implicit and analogy instruction on decision-making skill for novices under stress. *International Journal of Sport and Exercise Psychology*, 23(1), 141-162. https://doi.org/10.1080/1612197X.2021.1877325

- Split: **holdout**
- Evidence: `journal_action`: 2021 expression of concern; 2024 correction of unclear scope.
- Outcome: expression of concern (11 Oct 2021); later correction (7 Nov 2024) revising Tables 1, 2 and 4 and test statistics
- Verified values: 1 (1 in Number of explicit rules recalled after the intervention); value check: 1 by text.
  - 1.03 at n = 15 (Number of explicit rules recalled after the intervention, Analogy group (M = 1.03, SD = .25))

### 21. Internal: Kelly's Paper 2 (`kelly_pcit`)

- Identity withheld: Kelly anonymised the papers, and the set is internal. See `grim_ground_truth/kelly_grim/set/README.md`.
- Evidence: `published_critique`: Kelly 2023: the author did not take up the offer; all unexplained.
- Verified values: 4, totals of integer items at n printed per column in the paper's Table 1.

## Not verified, and why

| Paper | Why not |
|---|---|
| [10.3389/fpsyg.2016.01298](https://doi.org/10.3389/fpsyg.2016.01298) | no failing values itemised in any source we could read |
| [10.1111/j.1540-4560.2005.00405.x](https://doi.org/10.1111/j.1540-4560.2005.00405.x) | NOT confirmable: the df-implied split 18/19/18 fails, but 19/18/18 makes all three composite means (7.47, 6.85, 6.59; 3 items each) consistent and needs only the second t's df to be 35 instead of the printed 34. |
| [10.1016/0191-8869(92)90072-W](https://doi.org/10.1016/0191-8869(92)90072-W) | NOT confirmable: values confirmed at their cells on the scan (Table 2), but each respondent ranks three groups, so complete answers make a row's three means sum to 6.00; the Oriental rows sum to 5.92-6.00, so items had missing or tied answers and the per-item n is not 73. The cells also fail only round-half. |
| [10.1037/0022-3514.75.1.33](https://doi.org/10.1037/0022-3514.75.1.33) | no failing values itemised in any source we could read |
| [10.1080/00224545.2011.605398](https://doi.org/10.1080/00224545.2011.605398) | no failing values itemised in any source we could read |
| [10.1086/661890](https://doi.org/10.1086/661890) | no failing values itemised in any source we could read |
| [10.1016/j.rbmo.2014.03.011](https://doi.org/10.1016/j.rbmo.2014.03.011) | NOT confirmable: Table 1 prints 'Age (years)' and 'Duration of infertility (years)' as mean +/- SD; nothing says they were recorded in whole years. |
| [10.1111/j.1447-0756.2012.02016.x](https://doi.org/10.1111/j.1447-0756.2012.02016.x) | NOT confirmable: ages printed as mean +/- SD with no statement that they were recorded in whole years. |
| [10.1177/0305735606067168](https://doi.org/10.1177/0305735606067168) | no failing values itemised in any source we could read |
| Kelly Paper 1 (internal) | its one positive, 29.35 at N = 90, fails only round-half, and the paper's other raw-score means cannot show whether the authors rounded or truncated; its other flag (5.65) is a false alarm |
| Kelly Paper 3 (internal) | all 11 flags are false alarms: the authors confirmed per-subject subscale averaging |
| Kelly Paper 4 (internal) | all 13 flags are false alarms: 10 explained by the authors (averaging), 3 settled by the paper's own methods (pooled multiple-imputation values) |

## False alarms

`kelly_pcit` holds 25 `false_alarm` cells: means a critic flagged that are not errors. 22 were explained by the authors as per-subject averages of a subscale; 3 more are pooled multiple-imputation values, as the paper itself says. A tool that flags them is wrong; the scorer counts those flags separately.

