This is a forensic review of the following paper:

https://www.researchhub.com/paper/6448687/apple-cider-vinegar-for-weight-management-in-lebanese-adolescents-and-young-adults-with-overweight-and-obesity-a-randomised-double-blind-placebo-controlled-study

 

BACKGROUND

This paper assigns morning apple cider vinegar consumption at 0mL, 5mL, 10mL and 15mL to a sample of 120 Lebanese adolescents and young adults. Intervention groups lost ~5 to 7 kgs in twelve weeks. The paper has been downloaded ~67K times, and Altmetric lists its mention in 127 media outlets. Some examples are listed below:

https://www.brisbanetimes.com.au/lifestyle/health-and-wellness/the-benefits-of-introducing-apple-cider-vinegar-to-your-diet-20240418-p5fkrp.html

https://www.salon.com/2024/04/11/drinking-apple-cider-vinegar-may-help-with-weight-loss-but-its-health-benefits-are-overstated_partner/

https://theconversation.com/drinking-apple-cider-vinegar-may-help-with-weight-loss-but-its-health-benefits-are-overstated-226055

https://www.msn.com/de-de/gesundheit/other/apfelessig-stoffwechsel-boost-6-gr%C3%BCnde-warum-du-t%C3%A4glich-apfelessig-trinken-solltest/ar-AA1o4QaW

https://www.nytimes.com/2024/04/09/well/eat/apple-cider-vinegar-benefits.html

The study also has a variety of problematic features.

These are as follows:

 

(1) Data Availability

The paper states "All data relevant to the study are included in the article or uploaded as supplementary information." They are not, as no data is available. The supplementary material includes only a press release. This oversight ('state-but-withhold') is typically seen in papers which are deliberately trying to avoid scrutiny.

 

(2) Unlikely Distributions

Investigating distributions is best done when the data has listed constraints in addition to summary statistics. The paper states: "The subjects were evaluated for eligibility according to the following inclusion criteria: age between 12 and 25 years, BMIs between 27 and 34 kg/m2". The relevant figures are given in Table 1, with the descriptor "All values are mean±SD unless stated otherwise".

They are:

Age (years) 17.2±5.2 18.1±5.5 17.6±5.1 17.8±5.7

BMI (kg/m2) 30.6±3.1 30.2±2.8 30.0±3.0 30.7±3.2

SPRITE (Heathers et al. 2018; https://www.researchhub.com/paper/6448709/recovering-data-from-summary-statistics-sample-parameter-reconstruction-via-iterative-techniques-sprite) gives a method for reconstructing potential data from the above.

An example for BMI, Group 1:

range: 27 to 34

mean: 30.6

stdev: 3.1

n: 30

From 25 reconstructions, the mean distribution appears as below:



This describes a curiously strong preponderance of low values (BMI = 27) and high values (BMI = 34). As the samples are extremely similar, an identical and similarly non-realistic pattern emerges in all of the BMI data.

An example for age, Group 1:

range: 12 to 25

mean: 17.2

stdev: 5.2

n: 30

This distribution shows a strong over-representation at the lower bound (i.e. the 12 years old cut off). Again, similar patterns in the other age data can be observed.



This is more realistic than the data given above, as some distributions can be found that do not contain the lower bound stack - however, these have few (or zero) recruited participants between ~17-21 years of age.



 

(3) Extremely Unlikely Randomization

When investigating potentially unusual baseline data, an omnibus p-value can be calculated easily from multiple independent p-values via the Stouffer, Fisher, or other related methods. The key word above is independent. Here, a strong mutual predictivity probably exists between weight, height, BMI, waist, hip, and BFR% measurements. As the level of dependence cannot be easily calculated, the method should not be used here. The below are the calculated p-values (green) using a 1way ANOVA.



When these values (not given in the paper) are calculated, a strange pattern exists: age, height, and weight are almost identical between the randomized participants (p=0.93, p=0.99, p=0.99). This extreme uniformity likely represents a failure of randomization, although it is unclear how this arose.

 

(4) Statistical Analysis

The paper simply states: "Statistical analyses were performed using Statistical Package for the Social Sciences (SPSS) software (version 23.0). Significant differences between groups were determined by using an independent t-test. Statistical significance was set at p<0.05."

This is wildly insufficient, both as a description and a method. The samples are not independent - this is a standard between-within design, where multiple independent groups (between subjects) are assessed over time (within subjects). Likewise, the relevant p-values within any within subject comparison are likely extreme, but cannot be recalculated due to the unavailability of data. Of course, these are hidden behind the perpetually irritating veil of "p<0.05".

 

(5) The Effect Size

In the highest vinegar consumption group, weight loss was around 9% of body mass. This handily beats semaglutide, which after the same timepoint (12 weeks) results in a 6% body mass loss. https://www.nejm.org/doi/full/10.1056/NEJMoa2032183

If this was in fact the case, it seems likely that vinegar would be in wider use as a therapeutic agent. The industrial cost of production of vinegar is extremely low, as it can be bulk fermented close to orchards by primary producers. Given the availability and bulk cost of vinegar:

https://www.opentip.com/Azure-Market-Organics-Vinegar-Raw-Apple-Cider-Organic-p-12734366_AZU-CO185.html

... a 15mL dose costs around $1 per month. Ozempic at present US market prices costs approximately $935 per month before insurance.

An unpatentable, freely available, absolutely harmless dietary intervention that is 50% more effective at short/medium term weight loss than GLP-1 agonists for ~1/1000th of the price feels improbable.

 

(6) Further Details

* a full dietary diary is collected but never analysed

* a 12 week 120 person RCT was run without funding support

* "98% had no history of childhood obesity" is a strange statement to include, as many participants are obese children

* no participants were lost or failed to return data at any point

 

(7) Summary

I have no confidence in the accuracy of this study.