"""Statistical anatomy of a paper: studies, variables, hypotheses, tests.

WHY THIS EXISTS
---------------
The forensic tools check individual numbers. They cannot tell you whether the
*right* test was run, how many tests were run in total, or whether a flagged
number is load-bearing for the paper's claims or a footnote nobody reads.

The anatomy is the inspectable INPUT layer: an auditable enumeration of what
the paper actually did, from which three things follow that are impossible
without it.

1. **Correct tool application.** Every misapplication guard needs to know what
   kind of thing it is looking at -- `grim_test(data_type=..., scale_min=...,
   scale_max=...)`, `debit_test(data_type="binary")`, `sprite_reconstruct(...)`.
   Today those arguments are defaulted (to a 1-7 Likert scale, which is wrong
   for most of a biomedical corpus). A typed variable record supplies them, so
   the anatomy is what makes the guards usable rather than merely present.

2. **Multiplicity.** You cannot correct for multiple comparisons without
   knowing how many comparisons there were. The count must come from an
   enumeration, not a guess.

3. **Proportionality.** A discrepancy in a paper's headline claim and one in an
   incidental baseline row are not the same event. Severity should be weighted
   by narrative role, which requires knowing the role.

DESIGN NOTES / DEFENSIBILITY
----------------------------
* **NOIR is necessary but not sufficient.** Stevens' nominal/ordinal/interval/
  ratio typology is the textbook default and is genuinely contested for test
  selection (Velleman & Wilkinson 1993, "Nominal, Ordinal, Interval, and Ratio
  Typologies are Misleading"). What actually determines whether a test is valid
  is a *bundle*: measurement level, discreteness, bounds, distributional
  family, and the independence structure. We record all of them, and we never
  reason from NOIR alone.
* **Every extracted claim carries provenance and confidence.** LLM extraction
  is itself a false-positive surface: "the paper used a t-test on ordinal data"
  can simply be wrong. A claim with no supporting quote is not usable as
  evidence and is reported as such.
* **Unreported assumption checks are the norm, not a finding.** The large
  majority of papers never state that they checked normality. Flagging all of
  them flags everything and means nothing. We therefore only escalate on the
  CONJUNCTION of risk factors (see `assumption_risk`).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------
# Controlled vocabularies
# --------------------------------------------------------------------------

MEASUREMENT_LEVELS = ("nominal", "ordinal", "interval", "ratio")
DISCRETENESS = ("discrete", "continuous")

# The distributional family matters more than NOIR for choosing a test, and it
# is what tells the forensic tools whether they may run at all.
DISTRIBUTION_FAMILIES = (
    "binary",            # 0/1 indicator            -> DEBIT applies
    "count",             # non-negative integers    -> GRIM applies
    "likert_item",       # single bounded integer   -> GRIM/GRIMMER/SPRITE apply
    "likert_composite",  # mean of k items          -> GRIM with items=k
    "proportion",        # bounded [0,1] continuous
    "continuous",        # unbounded real           -> GRIM/SPRITE do NOT apply
    "time_to_event",     # survival, censored
    "rate",              # events per exposure
    "ordinal_category",  # ordered categories, not numeric
    "nominal_category",
    "unknown",
)

#: How a multi-item composite is scored -- the field that decides the
#: granularity denominator. Defined HERE rather than in `dispatch` because
#: `Variable.forensic_kwargs` needs it and `dispatch` already imports anatomy;
#: `dispatch` re-exports both names, so its own references are unchanged.
SUM_SCORED = frozenset({"sum_of_items"})
MEAN_SCORED = frozenset({"mean_of_items"})

VARIABLE_ROLES = (
    "primary_outcome", "secondary_outcome", "exposure", "predictor",
    "covariate", "moderator", "mediator", "grouping", "baseline_characteristic",
)

# How load-bearing a test is for what the paper claims. This is the axis Greg
# identified: tests are not created equal.
NARRATIVE_TIERS = ("primary", "secondary", "exploratory", "incidental")

CONFIRMATORY_STATUS = ("preregistered_confirmatory", "confirmatory", "exploratory", "unstated")

# Tools each family unlocks -- the bridge from anatomy to the forensic layer.
FAMILY_TO_TOOLS = {
    "binary": ("debit", "grim_percentage", "reconstruct_2x2"),
    "count": ("grim", "grimmer", "sprite"),
    "likert_item": ("grim", "grimmer", "sprite", "debit_if_dichotomised"),
    "likert_composite": ("grim", "grimmer"),
    "proportion": ("grim_percentage",),
    "continuous": ("check_sd_range", "check_sd_or_se", "statcheck"),
    "time_to_event": ("statcheck",),
    "rate": (),
    "ordinal_category": ("grimu",),
    "nominal_category": ("reconstruct_2x2", "recalc_chi_squared"),
    "unknown": (),
}


# --------------------------------------------------------------------------
# Assumptions
# --------------------------------------------------------------------------

# What each test requires. Keys are canonical test types.
TEST_ASSUMPTIONS: dict[str, tuple[str, ...]] = {
    # CHECKABLE assumptions only -- things an author can run a diagnostic for.
    # Scale/type PRECONDITIONS (e.g. "outcome must be interval") are design
    # properties audited by check_test_variable_compatibility; listing them here
    # meant they could never be satisfied and permanently inflated the
    # unreported-assumption count.
    "independent_t": ("normality", "homogeneity_of_variance", "independence"),
    "paired_t": ("normality_of_differences", "independence"),
    "one_way_anova": ("normality", "homogeneity_of_variance", "independence"),
    "repeated_measures_anova": ("normality", "sphericity"),
    "ancova": ("normality", "homogeneity_of_variance", "homogeneity_of_regression_slopes", "independence"),
    "pearson_correlation": ("normality", "linearity", "no_outliers"),
    "linear_regression": ("linearity", "normality_of_residuals", "homoscedasticity", "independence", "no_multicollinearity"),
    "logistic_regression": ("independence", "linearity_of_logit", "no_multicollinearity"),
    "cox_regression": ("proportional_hazards", "independence"),
    "chi_squared": ("expected_cell_counts_ge_5", "independence"),
    "fishers_exact": ("independence",),
    "mann_whitney": ("independence",),
    "wilcoxon_signed_rank": ("independence", "symmetry_of_differences"),
    "kruskal_wallis": ("independence",),
    "mixed_model": ("normality_of_residuals", "correct_random_effects_structure"),
    "mcnemar": ("independence",),
    "log_rank": ("proportional_hazards", "independence"),
    # The two factorial ANOVAs. Named in `schema.TEST_FAMILIES` since the
    # scaffold's enum was written and absent here until 2026-09-11, so a paper
    # running either got no assumption list at all. A two-way ANOVA assumes what
    # a one-way ANOVA assumes; a mixed (split-plot) ANOVA is the union of the
    # between- and within-subjects cases, so it carries sphericity as well.
    "two_way_anova": ("normality", "homogeneity_of_variance", "independence"),
    "mixed_anova": ("normality", "homogeneity_of_variance", "sphericity", "independence"),
}

#: SPELLING JOIN between the two vocabularies, NOT a synonym dictionary.
#: `schema.TEST_FAMILIES` and `TEST_ASSUMPTIONS` name several of the same tests
#: differently (`t_test_independent` / `independent_t`), and `test_type` is a
#: free string on the legacy path -- so a test named in the scaffold's spelling
#: silently missed its assumption list. Only EXACT same-test pairs belong here.
#: An ambiguous family (`correlation`, which may be Spearman) must NOT be
#: aliased onto one member: it would demand a check its test never required,
#: which is the accusing direction. Those are declared below instead.
TEST_TYPE_ALIASES: dict[str, str] = {
    "t_test_independent": "independent_t",
    "t_test_paired": "paired_t",
    "fisher_exact": "fishers_exact",
}

#: Families in `schema.TEST_FAMILIES` that DELIBERATELY have no assumption
#: entry, with the reason. Each names a GROUP of tests whose members disagree
#: about what they assume, so any entry here would be a guess, and a guessed
#: requirement flags an honest paper for not reporting a check it never owed.
#: `assumption_risk` fails closed on them and returns `indeterminate`, which is
#: not an allegation. Reconciled against `TEST_FAMILIES` by
#: `TestTheTwoTestVocabulariesCoverTheSameUniverse`, so adding a family to
#: either list without deciding this question fails loudly.
TEST_FAMILIES_WITHOUT_ASSUMPTIONS: dict[str, str] = {
    "t_test_unspecified": "independent and paired t-tests assume different things "
                          "(normality of scores vs of differences)",
    "anova_unspecified": "one-way, factorial and repeated-measures ANOVA differ "
                         "(sphericity applies only to the within-subjects case)",
    "correlation": "may be Spearman or Kendall, which assume neither normality "
                   "nor linearity",
    "wilcoxon": "may be the signed-rank test (symmetry of differences) or the "
                "rank-sum test (Mann-Whitney), which does not assume it",
    "survival": "may be a Kaplan-Meier description, which assumes no "
                "proportional hazards, unlike Cox regression and the log-rank test",
    "other": "names nothing; the vocabulary's own escape hatch",
}


def canonical_test_type(test_type: str | None) -> str:
    """The assumption-vocabulary spelling of a test type, unchanged when it
    already is one (and when no join is known, so an unrecognised type still
    fails closed at the `TEST_ASSUMPTIONS` gate)."""
    return TEST_TYPE_ALIASES.get(test_type or "", test_type or "")


# Rank-based tests genuinely have weak distributional assumptions. Logistic and
# Cox regression are NOT parametric-normal but have their own hard, auditable
# assumptions (linearity of logit, proportional hazards) -- lumping them into a
# blanket "non-parametric, assumptions are weak" exemption made those
# structurally unauditable.
RANK_BASED_TESTS = frozenset({
    "mann_whitney", "wilcoxon_signed_rank", "kruskal_wallis", "fishers_exact", "mcnemar",
})

PARAMETRIC_TESTS = frozenset({
    "independent_t", "paired_t", "one_way_anova", "repeated_measures_anova",
    "ancova", "pearson_correlation", "linear_regression", "mixed_model",
})

# Outcome families for which a parametric location test is questionable.
NON_INTERVAL_FAMILIES = frozenset({
    "ordinal_category", "binary", "count", "likert_item", "proportion", "time_to_event",
})



# Authors write "Shapiro-Wilk test", not "normality". Requiring exact snake_case
# tokens meant `assumption_checks_reported` could never clear anything and the
# early return was dead code, so papers that DID check were still flagged.
#
# These keys LOCATE which assumption a phrase is about. They do NOT decide
# that it was checked -- `classify_assumption_mentions` does that, because
# every match here SUPPRESSES an entry from `unreported_assumptions()`, and a
# suppression is a claim that the authors did the work.
#
# Four keys were removed or narrowed 2026-08-18 for being polysemous in this
# literature. Counted over the 309-paper cerebrolysin corpus body text:
#   "tolerance"  308 hits -- morphine tolerance, and Stata's solver
#                parameter tolerance. Zero were the multicollinearity
#                statistic. Now "tolerance statistic".
#   "fisher"     170 hits -- Fisher's z transformation and post-hoc Fisher
#                (LSD) as well as Fisher's exact. Now "fisher's exact".
#   "clustering"  36 hits -- Schwann-cell clustering and hierarchical
#                clustering algorithms. Now "cluster-robust" /
#                "clustered standard error" / "intraclass correlation".
#   "leverage"    10 hits -- Stata's `leverage` option and the plain verb
#                ("leverage our large database"). Now "leverage value" /
#                "hat value" / "high leverage".
# The count is over body prose, while this table consumes the model's short
# `assumption_checks_reported` entries; it establishes that the words are
# ambiguous in this literature, not the rate at which they would mislead here.
ASSUMPTION_SYNONYMS: dict[str, str] = {
    "shapiro": "normality", "shapiro-wilk": "normality", "shapiro wilk": "normality",
    "kolmogorov": "normality", "kolmogorov-smirnov": "normality", "ks test": "normality",
    "anderson-darling": "normality", "qq plot": "normality", "q-q plot": "normality",
    "normal probability plot": "normality", "normality": "normality",
    "normality of residuals": "normality_of_residuals",
    "residual plot": "normality_of_residuals",
    "normality of differences": "normality_of_differences",
    "levene": "homogeneity_of_variance", "levene's test": "homogeneity_of_variance",
    "bartlett": "homogeneity_of_variance", "brown-forsythe": "homogeneity_of_variance",
    "homogeneity of variance": "homogeneity_of_variance",
    "homoscedasticity": "homoscedasticity", "breusch-pagan": "homoscedasticity",
    "white test": "homoscedasticity",
    "mauchly": "sphericity", "sphericity": "sphericity",
    "greenhouse-geisser": "sphericity", "huynh-feldt": "sphericity",
    "vif": "no_multicollinearity", "variance inflation": "no_multicollinearity",
    "tolerance statistic": "no_multicollinearity",
    "multicollinearity": "no_multicollinearity",
    "schoenfeld": "proportional_hazards", "log-minus-log": "proportional_hazards",
    "proportional hazards": "proportional_hazards", "ph assumption": "proportional_hazards",
    "expected cell count": "expected_cell_counts_ge_5",
    "expected counts": "expected_cell_counts_ge_5",
    "fisher's exact": "expected_cell_counts_ge_5",
    "fisher exact": "expected_cell_counts_ge_5",
    "linearity": "linearity", "scatterplot": "linearity",
    "box-tidwell": "linearity_of_logit", "linearity of logit": "linearity_of_logit",
    "icc": "independence", "design effect": "independence",
    "intraclass correlation": "independence",
    "cluster-robust": "independence", "clustered standard error": "independence",
    "durbin-watson": "independence", "independence": "independence",
    "outlier": "no_outliers", "cook's distance": "no_outliers",
    "leverage value": "no_outliers", "hat value": "no_outliers",
    "high leverage": "no_outliers",
    # "No outlying values were present" located NO assumption at all -- it is
    # not a variant of "outlier" under the word-bounded match -- so a paper
    # that reported a clean screen in those words got neither the credit nor
    # the accusation. Unambiguous in this literature, unlike the four words
    # removed 2026-08-18: "outlying" has no second sense. It arrives with the
    # matching result nouns in `_CHECK_RESULT`, because a synonym key WITHOUT
    # them converts a silent drop into a false accusation -- the phrasing is
    # negated by construction.
    "outlying value": "no_outliers", "outlying observation": "no_outliers",
    "outlying data point": "no_outliers",
    # THE NAMED OUTLIER TESTS. A paper that ran one of these checked for
    # outliers, and the table knew only the diagnostics (Cook's distance,
    # leverage) and the bare word -- so "Grubbs' test was applied to the
    # residuals" fell through to the unmatched branch, which stores the whole
    # sentence as its own token, and `unreported_assumptions()` went on to
    # report `no_outliers` as unchecked. Each key below can only SUPPRESS that
    # claim. Every name is a discriminating phrase, in the discipline the four
    # 2026-08-18 removals set: no bare "q test" (Cochran's Q, and the
    # heterogeneity Q) and no bare surname.
    "grubbs' test": "no_outliers", "grubbs test": "no_outliers",
    "grubbs's test": "no_outliers",
    "dixon's q test": "no_outliers", "dixon q test": "no_outliers",
    "dixon's q": "no_outliers",
    "tietjen-moore": "no_outliers", "tietjen moore": "no_outliers",
    "generalized extreme studentized deviate": "no_outliers",
    "generalised extreme studentized deviate": "no_outliers",
    "gesd test": "no_outliers",
}


#: Canonical assumption token -> what it means, in words a researcher can act on.
#:
#: Greg, 2026-08-09: "something I would like added to the statistical test
#: section of the output is the set of assumptions for each test. E.g.
#: parametric tests assuming normality of the distribution of means,
#: homoscedasticity, etc."
#:
#: The table already reported which required checks went UNREPORTED, which is
#: the complement of what he asked for: a reader could see that `normality` was
#: not checked without ever being told that this test assumes it, or what
#: "normality" means HERE. It is not the same claim in every test -- an
#: independent t-test needs the sampling distribution of the mean DIFFERENCE to
#: be near-normal, a paired test needs it of the DIFFERENCES, a linear
#: regression needs it of the RESIDUALS -- and collapsing all three to one token
#: is exactly the imprecision that makes an assumption list ignorable.
ASSUMPTION_DESCRIPTIONS: dict[str, str] = {
    "normality": (
        "Normality: the sampling distribution of the group means is approximately "
        "normal. With large per-group n the central limit theorem usually supplies "
        "this even for skewed raw data; with small n it does not."
    ),
    "normality_of_differences": (
        "Normality of the paired differences: it is the within-pair differences, "
        "not the raw scores, that must be approximately normal."
    ),
    "normality_of_residuals": (
        "Normality of the residuals: the model's errors, not the outcome itself, "
        "are assumed approximately normal."
    ),
    "homogeneity_of_variance": (
        "Homogeneity of variance (homoscedasticity): the groups share a common "
        "variance. Welch's correction relaxes this; the pooled/Student form does not."
    ),
    "homoscedasticity": (
        "Homoscedasticity: residual variance is constant across fitted values, "
        "rather than fanning out with the predicted value."
    ),
    "homogeneity_of_regression_slopes": (
        "Homogeneity of regression slopes: the covariate's relationship with the "
        "outcome is the same in every group, so a single adjustment is meaningful."
    ),
    "independence": (
        "Independent observations: each unit contributes once, and units are not "
        "clustered, paired or repeated. Clustering by site, class or family "
        "breaks this and inflates significance."
    ),
    "sphericity": (
        "Sphericity: the variances of all pairwise differences between conditions "
        "are equal. Violations are usual, hence Greenhouse-Geisser corrections."
    ),
    "linearity": (
        "Linearity: the relationship between the variables is a straight line on "
        "the analysed scale."
    ),
    "linearity_of_logit": (
        "Linearity of the logit: each continuous predictor is linearly related to "
        "the LOG-ODDS of the outcome, not to the outcome itself."
    ),
    "no_outliers": (
        "No influential outliers: a correlation in particular can be created or "
        "destroyed by one extreme point."
    ),
    "no_multicollinearity": (
        "No severe multicollinearity: predictors are not near-redundant, which "
        "would make individual coefficients unstable and their SEs large."
    ),
    "proportional_hazards": (
        "Proportional hazards: the hazard ratio between groups is constant over "
        "follow-up time, rather than converging or crossing."
    ),
    "expected_cell_counts_ge_5": (
        "Adequate expected cell counts (conventionally at least 5 per cell): "
        "below that the chi-square approximation is unreliable and Fisher's exact "
        "test is the appropriate choice."
    ),
    "symmetry_of_differences": (
        "Symmetry of the paired differences about their median, which the signed-"
        "rank test needs even though it does not assume normality."
    ),
    "correct_random_effects_structure": (
        "A correctly specified random-effects structure: the grouping levels "
        "modelled are the ones that actually induce dependence in the data."
    ),
}


def describe_assumptions(tokens) -> list[str]:
    """Plain-language description of each canonical assumption token.

    An unknown token is echoed rather than dropped: a silently missing
    assumption is worse than an unpolished one, and it would also hide a typo in
    TEST_ASSUMPTIONS from anyone reading the output.
    """
    return [ASSUMPTION_DESCRIPTIONS.get(t, t) for t in tokens]


#: NEGATION SCOPE, not clause splitting. The first attempt cut on commas so a
#: denial could not leak between list items -- and that broke the commonest
#: denial there is, because "No checks of normality, homogeneity of variance or
#: linearity were reported" puts the cue in the first item and the rest of the
#: list beyond it. Two of the three were then reported as checked, in the
#: dangerous direction.
#:
#: English negation scopes over the whole clause, in both directions ("normality
#: and homogeneity were NOT assessed" negates two subjects that precede it), and
#: stops at an adversative. So the unit is a segment bounded by a sentence edge
#: or by but/however/although/whereas/though/yet, and a cue anywhere in a
#: segment denies every assumption named in that segment.
_ASSUMPTION_SEGMENT = re.compile(
    r"[.;]|\b(?:but|however|although|though|whereas|yet)\b", re.I)

#: A clause that says the check was NOT done. The DEFAULT here is `checked`,
#: which is the opposite of the default chosen in `scope.classify_document`,
#: and the difference is deliberate: this function reads the model's own
#: `assumption_checks_reported` field, whose entries are affirmative by
#: construction -- the model was asked to list checks the paper REPORTED. The
#: defect is that a model sometimes writes a whole sentence, denial included.
#: So a negation cue is an EXCEPTION to an affirmative field, not a judgment
#: about arbitrary paper text, and a closed list is the right instrument.
_ASSUMPTION_DENIED = re.compile(
    r"\b(?:no|not|neither|nor|none|never|without|cannot|can't|couldn't|"
    r"didn't|wasn't|weren't|lack(?:s|ing|ed)?|absent|omitted|unreported|"
    r"unchecked|unexamined|untested|unverified)\b|"
    r"\b(?:was|were|is|are|has|have|had|could|would|did|do|does)\s+not\b|"
    r"\b(?:failed|unable)\s+to\b", re.I)

#: A negative RESULT of a check is not a refusal to run it. "No violations of
#: normality were found" means the authors looked; reading its "no" as a denial
#: would flip an affirmative report into a missing one. Same shape as
#: `artefacts._NO_DEVIATION`, which exists because CONSORT boilerplate
#: affirming fidelity to a plan was being printed as evidence of departing
#: from it. These spans are removed before the denial cues are looked for.
#:
#: The second alternation (2026-09-11) is the same rule for the OUTLIER result
#: nouns, which this list did not carry. "Grubbs' test identified no extreme
#: values" and "Cook's distance identified no influential outliers" are reports
#: of a screen that found nothing, and both read as denials -- so a paper that
#: checked for outliers was told it had not. That is the accusing direction,
#: unlike `ef1638d`, whose synonym additions could only suppress.
#:
#: WHAT SEPARATES THE TWO READINGS IS WHAT THE `no` ATTACHES TO. A RESULT
#: negates the finding ("no outliers were detected"); a DENIAL negates the
#: check ("no outlier analysis was conducted", "no test for outliers was
#: performed"). So the noun is treated as a result only when no check word
#: follows it -- the lookahead -- and a `no` attached to a check word never
#: matches the alternation at all. Noun FORMS only: "no outliers detected" is a
#: result, while "no outlier detection" is a denial.
#:
#: EXTENDED 2026-09-11 to the four assumptions that change above recorded as
#: measured-but-unfixed: multicollinearity, heteroscedasticity, clustering and
#: heterogeneity. They are the same defect -- "VIF values indicated no
#: multicollinearity" read as a refusal to look for it -- and they are treated
#: by the same grammar, with two differences forced by the vocabulary:
#:
#:   1. A CHECK WORD MAY SIT BEHIND A PREPOSITIONAL PHRASE. "No heterogeneity
#:      of variance testing was undertaken" is a denial whose check word is
#:      three tokens past the noun, a shape the outlier nouns do not produce.
#:      So the check-word lookahead admits one optional `of/in/for/...` phrase.
#:   2. THESE NOUNS TAKE A TREATMENT VERB, AND THE OUTLIER NOUNS DO NOT. One
#:      does not "account for" an outlier, but "no clustering was accounted
#:      for" is ordinary English and is a denial -- the paper is saying the
#:      dependence was left unmodelled. A second lookahead keeps those denied.
#:
#: ON `clustering` SPECIFICALLY, and why this does NOT reopen what 2026-08-18
#: closed. That pass removed `clustering` from `ASSUMPTION_SYNONYMS` because 36
#: hits over the cerebrolysin corpus were Schwann-cell clustering and
#: hierarchical clustering algorithms -- the word cannot be trusted to say that
#: a paper addressed INDEPENDENCE. Nothing here re-adds it: `clustering` is not
#: a synonym key and still locates no assumption. It appears only as a RESULT
#: noun, and a result noun can never introduce an assumption -- the segment
#: must already name one (`icc`, `intraclass correlation`, `cluster-robust`,
#: `design effect`, `durbin-watson`, `independence`) for `independence` to be
#: in play at all. So the unrelated senses reach nothing: "no clustering of
#: Schwann cells was observed" names no assumption before this rule and names
#: none after it. What the rule can do is confined to a segment that has
#: already committed to the independence diagnostics.
_CHECK_NOUN = (
    r"analys[ie]s|assessments?|tests?|testing|screenings?|checks?|"
    r"examinations?|evaluations?|diagnostics?|inspections?|detection|"
    r"procedures?|methods?|criteri(?:a|on)|"
    r"adjustments?|corrections?|controls?|accounting|adjusting"
)

#: Verbs that say the phenomenon was HANDLED rather than LOOKED FOR. "No
#: clustering was accounted for" denies the check; "no clustering was detected"
#: reports its result. Applied only to the 2026-09-11 nouns -- the outlier
#: nouns do not take these verbs, and widening a committed rule on a shape it
#: does not produce buys nothing and risks something.
_TREATMENT_VERB = (
    r"assessed|tested|examined|checked|evaluated|screened|investigated|"
    r"inspected|analy[sz]ed|explored|verified|conducted|performed|reported|"
    r"accounted|adjusted|corrected|controlled|modell?ed|accommodated|"
    r"addressed|considered|incorporated|undertaken"
)

#: Hedges a result noun may carry. One definition, used by every alternation
#: below, so a phrasing recognised for one assumption is recognised for all.
_RESULT_HEDGE = (
    r"(?:significant\s+|major\s+|substantial\s+|meaningful\s+|notable\s+|"
    r"appreciable\s+|marked\s+|severe\s+|serious\s+)?"
)

_CHECK_RESULT = re.compile(
    r"\bno\s+" + _RESULT_HEDGE +
    r"(?:violations?|evidence|departures?|deviations?|indication|problems?|"
    r"concerns?)\b|"
    r"\bno\s+" + _RESULT_HEDGE +
    r"(?:outliers?|extreme\s+values?|outlying\s+(?:values?|observations?|"
    r"cases?|data\s+points?|points?)|"
    r"influential\s+(?:outliers?|cases?|observations?|points?|data\s+points?))"
    r"(?!\s+(?:" + _CHECK_NOUN + r")\b)|"
    r"\bno\s+" + _RESULT_HEDGE +
    r"(?:(?:multi)?collinearity|heteros[ck]edasticity|heterogeneity|clustering)"
    r"(?!(?:\s+(?:of|in|for|across|between|among)(?:\s+the)?\s+\w+)?"
    r"\s+(?:" + _CHECK_NOUN + r")\b)"
    r"(?!\s+(?:was|were|is|are)\s+(?:\w+\s+){0,2}?"
    r"(?:" + _TREATMENT_VERB + r")\b)|"
    r"\b(?:was|were|are|is)\s+not\s+(?:violated|significant|rejected|"
    r"breached)\b", re.I)


def _assumption_segments(text: str) -> list[str]:
    """Negation-scope segments of one assumption entry."""
    out, last = [], 0
    for m in _ASSUMPTION_SEGMENT.finditer(text):
        out.append(text[last:m.start()])
        last = m.end()
    out.append(text[last:])
    return [seg for seg in out if seg.strip()]


def _segment_denies(segment: str) -> bool:
    """Does this segment say the check was NOT run?"""
    return bool(_ASSUMPTION_DENIED.search(_CHECK_RESULT.sub(" ", segment)))


def classify_assumption_mentions(reported: list[str]) -> dict[str, set[str]]:
    """Split free-text assumption mentions into checks AFFIRMED and DENIED.

    `ASSUMPTION_SYNONYMS` only says which assumption a phrase is ABOUT. Whether
    the paper checked it is a separate question, and it used to go unasked: a
    substring hit was taken as proof of a check, so

        "Neither normality nor homogeneity of variance was examined, and
         independence cannot be assumed."

    cleared all three, `unreported_assumptions()` returned empty, and the table
    printed `assumption risk: consistent` with the note "Required assumption
    checks were reported." A sentence saying nothing was checked was rendered
    as a clean bill of health -- the house failure mode, with the sign flipped.

    A denial is INFORMATION, not an absence, so it is returned rather than
    dropped: the authors telling us they did not check normality is a fact
    about the paper, and a caller that throws it away commits the same error in
    the other direction.
    """
    checked: set[str] = set()
    denied: set[str] = set()
    for raw in reported or []:
        text = " ".join(str(raw).split()).lower()
        if not text:
            continue
        canonical = ASSUMPTION_SYNONYMS.get(text)
        if canonical:                      # the whole entry IS the label
            (denied if _segment_denies(text) else checked).add(canonical)
            continue
        matched = False
        for segment in _assumption_segments(text):
            bucket = denied if _segment_denies(segment) else checked
            for key, canon in ASSUMPTION_SYNONYMS.items():
                # Word-bounded, not `in`: a bare substring test lets a short key
                # like "icc" match inside an unrelated word. The optional plural
                # is not decoration -- papers write "Outliers were not
                # examined", and a bare boundary on "outlier" missed it, which
                # cost both the suppression AND the denial.
                if re.search(r"(?<![a-z0-9])" + re.escape(key) + r"(?:e?s)?(?![a-z0-9])",
                             segment):
                    matched = True
                    bucket.add(canon)
        if not matched and not _segment_denies(text):
            checked.add(text.replace(" ", "_"))
    # An assumption both affirmed and denied across entries is not established.
    checked -= denied
    return {"checked": checked, "denied": denied}


def normalize_assumption_labels(reported: list[str]) -> set[str]:
    """Assumptions the paper is reported to have ACTUALLY checked.

    Unchanged signature: every caller uses this to SUPPRESS an entry from
    `unreported_assumptions()`, and only an affirmed check may do that.
    """
    return classify_assumption_mentions(reported)["checked"]


def denied_assumption_labels(reported: list[str]) -> set[str]:
    """Assumptions the paper explicitly says it did NOT check."""
    return classify_assumption_mentions(reported)["denied"]


# --------------------------------------------------------------------------
# Records
# --------------------------------------------------------------------------

#: Families whose n (%) cells give the share of the sample in one category.
CATEGORY_FAMILIES = frozenset({"nominal_category", "ordinal_category"})


@dataclass
class Variable:
    id: str
    name: str
    role: str = "predictor"
    measurement_level: str = "unknown"
    discreteness: str = "unknown"
    family: str = "unknown"
    lower_bound: float | None = None
    upper_bound: float | None = None
    units: str | None = None
    n_categories: int | None = None
    n_items: int | None = None          # for composites: GRIM's `items`

    #: HOW the variable was computed, if it was. Already in
    #: `findings.schema.json` with the enum measured|mean_of_items|
    #: sum_of_items|percentage|proportion|ratio|difference|change_score|
    #: standardized|log_transformed|recoded|other; already asked for in the
    #: sweep prompt; already rendered to the reader; already tested.
    #:
    #: IT WAS NEVER A FIELD HERE, so both loaders -- `_pick` and
    #: `dispatch._as_variable`, which filter to `Variable.__dataclass_fields__`
    #: -- silently dropped it before any check could see it. The model was
    #: answering a question nothing read.
    #:
    #: It decides the granularity denominator, which is the difference between
    #: a correct `impossible` and a manufactured one:
    #:   sum_of_items   each subject scores an INTEGER, so the group mean moves
    #:                  in steps of 1/n -- ordinary GRIM, no `items` needed.
    #:   mean_of_items  each subject scores a multiple of 1/k, so the mean moves
    #:                  in steps of 1/(k*n) -- needs an `items` parameter that
    #:                  `grim_test` does not have, so it stays refused.
    derivation: str | None = None

    #: The other two schema-declared variable fields that were dropped on load.
    #: `derived_from` is what the variable was computed FROM in the paper's own
    #: words; `levels` is the actual values a categorical variable takes. Both
    #: are asked for, both were discarded, neither has a checking consumer YET --
    #: but a declaration that survives loading can acquire one, and a declaration
    #: silently deleted cannot.
    derived_from: str | None = None
    levels: list[str] = field(default_factory=list)
    provenance_quote: str | None = None
    confidence: str = "low"             # low|medium|high

    #: Did `provenance_quote` turn out to be IN the paper? Set by the pipeline
    #: (`agent._annotate_quotes` via `quotes.classify`), NEVER by the model --
    #: `PIPELINE_ONLY_FIELDS` strips it from model input on both construction
    #: paths. Carries one of quotes.py's verdicts: verbatim | elided | stitched
    #: | unverified | absent, or None when no check has run.
    provenance_verdict: str | None = None

    def bounds_are_stated(self) -> bool:
        """May this variable's scale bounds license an `impossible` verdict?

        Only if the paper can be SHOWN to state them. `confidence` alone was the
        whole of the old test, and `confidence` is the model grading its own
        homework: a model writing `confidence: "high"` beside an invented 1-7
        scale promoted GRIM from `suspicious` to `impossible` on its own say-so,
        and the quote it was asked to supply as evidence was never checked.

        `verbatim` and `elided` mean a reader can open the paper and find the
        sentence. `stitched` means WE assembled the sentence and it does not
        appear there, so it cannot evidence that the authors stated anything;
        `unverified` means our search failed, which is not evidence either way
        and so is not evidence FOR. Both fall back to `assumed`, capping the
        verdict -- the safe direction.

        THIRD CONDITION, ADDED 2026-08-11: THE QUOTE MUST MENTION THE BOUNDS.
        The first two conditions check that a quote is real. They never checked
        that it is real ABOUT THIS -- and `provenance_quote` is specified in
        findings.schema.json as the "verbatim sentence establishing this
        TYPING", which is a different claim from the scale range. So a verified
        sentence about what kind of variable this is was licensing `impossible`
        for bounds it never mentioned.

        MEASURED over the archive, variables passing the old two-condition test
        AND declaring bounds: 26, of which only 14 have a quote containing the
        declared upper bound. Twelve of 26 (46%) were unlocking the top of the
        severity ladder on evidence that says nothing about the range. The
        clearest instance is a quote reading

            "(2) difficulties resisting eating (M = 2.79, SD = 1.42)"

        offered as evidence that the scale runs 1 to 5. It is a real sentence,
        really in the paper, and it establishes nothing whatever about bounds.

        This is the same rule the `warrant` vocabulary states for findings:
        evidence has to be about the thing it licenses. It is deliberately NOT
        implemented as a new `bounds_quote` field -- that is the better long-run
        shape and needs a schema change, a prompt change and a paid run to
        populate, whereas this is sound today and costs nothing. Coverage falls
        (26 -> 14 on the archive) and falls in the correct direction: every one
        of the twelve it removes was an unsound licence.
        """
        if not (self.confidence == "high"
                and self.provenance_verdict in ("verbatim", "elided")):
            return False
        return self._quote_mentions_bounds()

    def _quote_mentions_bounds(self) -> bool:
        """Does the provenance quote actually contain the declared bounds?

        Undeclared bounds are vacuously fine -- `bound_source` only matters to a
        check that was handed a range, and a variable with no range never
        reaches one. Number matching goes through `quotes._number_forms`, the
        same matcher the quote verifier uses, so `5`, `5.0` and `5.00` are one
        number here exactly as they are there.
        """
        lo, hi = self.lower_bound, self.upper_bound
        if lo is None and hi is None:
            return True
        quote = self.provenance_quote or ""
        if not quote.strip():
            return False
        try:
            from .quotes import _number_forms, normalise
        except Exception as exc:  # noqa: BLE001
            # CLOSES THE GATE AND SAYS SO. Failing silently here would restore
            # the permissive behavior this method exists to remove, and it
            # would do it invisibly -- the shape `lint-inert` calls a swallowed
            # failure. Refusing is the safe direction; refusing quietly is not.
            import warnings
            warnings.warn(
                f"anatomy: the quote matcher is unavailable, so no variable can "
                f"evidence its bounds and every range reads as assumed: "
                f"{type(exc).__name__}: {exc}", stacklevel=2)
            return False
        hay = normalise(quote)
        # A NUMBER, NOT A SUBSTRING OF ONE. `f in hay` matched the digit `5`
        # inside `4.51` and the digit `1` inside the same decimal, so a quote
        # reading only "Depression was measured with the CES-D (M = 4.51, SD =
        # 0.83)" -- which states no scale range whatever -- evidenced bounds of
        # 1 to 5. VERIFIED 2026-08-18: `bounds_are_stated()` returned True on
        # exactly that, removing the severity cap and licensing `impossible`.
        #
        # That defeats the very condition this method was added for on
        # 2026-08-11, whose own docstring says evidence has to be ABOUT the
        # thing it licenses. Digit-boundary matching restores it: a bound must
        # appear as its own number, not inside a longer one.
        import re as _re
        for bound in (lo, hi):
            if bound is None:
                continue
            forms = _number_forms(str(bound))
            # `(?:\.0+)?` keeps the decimal forms the docstring promises: `5.0`
            # and `5.00` ARE the number 5, and a first version of this boundary
            # rule rejected them -- caught by test_decimal_forms_of_the_same
            # _number_count, which existed precisely to pin that behavior.
            # What stays excluded is a digit inside a LONGER number: the `5` of
            # `4.51`, the `5` of `15`, the `1` of `1.42`.
            if not any(f and _re.search(
                    rf"(?<![\d.]){_re.escape(f)}(?:\.0+)?(?![\d.])", hay)
                       for f in forms):
                return False
        return True

    def discreteness_source(self) -> str:
        """May this variable's DISCRETENESS license an `impossible` verdict?

        The exact counterpart of `bounds_are_stated`, for the premise the
        granularity family actually turns on: that each subject contributed a
        WHOLE NUMBER. GRIM's "no integer sum over n rounds to this mean" is
        airtight arithmetic and a worthless accusation if the observations were
        never integers -- and until now nothing asked. `data_type` reached the
        tools carrying that claim, and `data_type` is derived from `family`,
        which the model wrote after reading prose.

        GREG'S CALL, 2026-08-10: this family is "very unlikely to be applicable
        for most studies... any such test should be 'guilty until proven
        innocent' owing to this low prior probability." The prior is the point:
        GRIM-tractable instruments are concentrated in psychology, and this
        toolkit runs across clinical, biological and environmental literature
        where a mean is far more often a continuous measurement.

        THE EVIDENCE BAR IS THE SAME ONE `bounds_are_stated` USES, and for the
        same reason (#87): `confidence` is the model grading its own homework,
        so a verified quote must back it. `provenance_verdict` is set by the
        pipeline (`agent._annotate_quotes` -> `quotes.classify`) and stripped
        from model input by `PIPELINE_ONLY_FIELDS`, so it cannot be forged.

        `discreteness` must ALSO say "discrete". The field has existed on this
        dataclass since the anatomy schema was written, is asked for in the
        sweep prompt, and is displayed in two renderers -- and no check has ever
        read it. Anything else, including the model declining to commit
        ("unknown"), reads as not-demonstrated and caps the verdict.
        """
        if str(self.discreteness or "").strip().lower() != "discrete":
            return "assumed"
        return "stated" if (self.confidence == "high"
                            and self.provenance_verdict in ("verbatim", "elided")) else "assumed"

    def forensic_kwargs(self, share: bool = False) -> dict:
        """Translate this variable into arguments the forensic tools accept.

        This is the whole point of typing variables: it replaces the silent
        Likert defaults with what the paper actually measured.

        `share`: the arguments are for the percentage in an n (%) cell. For a
        category family that percentage is the share of the sample in the
        category, so `data_type` is `proportion` -- what grim_percentage
        tests. Without it every such cell was refused: `nominal` and
        `integer` are not share types. Mean-type checks never pass it.
        """
        family_to_data_type = {
            "binary": "binary",
            "count": "count",
            "likert_item": "likert",
            "likert_composite": "likert",
            "proportion": "proportion",
            "continuous": "continuous",
            "time_to_event": "continuous",
            "rate": "continuous",
            # The two category families describe the VARIABLE: right for a
            # mean of ordinal codes, refused for a mean of a nominal one. Their
            # n (%) cells are shares (`share` below).
            "ordinal_category": "integer",
            "nominal_category": "nominal",
            "unknown": "unknown",
        }
        data_type = family_to_data_type.get(self.family, "unknown")
        if share and self.family in CATEGORY_FAMILIES:
            data_type = "proportion"
        kwargs: dict = {
            "data_type": data_type,
            # Emitted for EVERY variable, not only bounded ones: a granularity
            # failure does not need bounds, which is exactly why it was reaching
            # `impossible` unchecked.
            "discreteness_source": self.discreteness_source(),
        }
        if self.lower_bound is not None and self.upper_bound is not None:
            kwargs["scale_min"] = self.lower_bound
            kwargs["scale_max"] = self.upper_bound
            kwargs["bound_source"] = "stated" if self.bounds_are_stated() else "assumed"
        else:
            # No bounds means GRIM/SPRITE must not silently invent a 1-7 scale.
            kwargs["bound_source"] = "assumed"
        # `items` multiplies the denominator: the only tool that accepts it,
        # `r_grim_ground_truth`, tests at n*items. That is CORRECT for a mean of
        # k items and WRONG in the permissive direction for a SUM of k items,
        # whose per-subject total is an integer and whose granularity is 1/n.
        # Emitting it unconditionally made the scoring question decide nothing:
        # a declared sum-score with `n_items: 10` would have been checked 10x
        # more loosely than it should be -- a silent false NEGATIVE, which is
        # the failure no reader can see. `derivation` is the field that settles
        # it, so only the case it settles in favour of emits.
        if self.n_items and str(self.derivation or "") in MEAN_SCORED:
            kwargs["items"] = self.n_items
        return kwargs

    def applicable_tools(self) -> tuple[str, ...]:
        return FAMILY_TO_TOOLS.get(self.family, ())


@dataclass
class StatisticalTest:
    id: str
    test_type: str
    location: str = ""                  # "Table 3, row 2"
    study_id: str | None = None
    hypothesis_id: str | None = None
    outcome_var: str | None = None
    predictor_vars: list[str] = field(default_factory=list)
    grouping_var: str | None = None
    n: int | None = None
    df: str | None = None
    statistic_value: float | None = None

    #: DID THE PAPER PRINT THIS STATISTIC? `present` | `absent` | `unchecked`,
    #: stamped by `agent._annotate_quotes` from `quotes._number_present` and
    #: listed in `PIPELINE_ONLY_FIELDS` so the model cannot write it.
    #:
    #: WHY IT EXISTS. `effect_size` carries an explicit instruction -- "AS THE
    #: PAPER PRINTED IT ... do NOT put your own computation here; that goes in
    #: `effect_size_estimated`, and merging the two would make a number we
    #: derived indistinguishable from one the authors published." `statistic_
    #: value` carried no such instruction and no description at all, and the
    #: model duly filled it with arithmetic of its own.
    #:
    #: MEASURED on 10.1002--ajcp.70049: four of its `statistic_value` entries
    #: are Wald z's the model computed by dividing a printed coefficient by its
    #: printed SE -- 2.658 = 1.01/0.38, 2.233 = 1.34/0.60, 1.809 = 0.85/0.47,
    #: -3.007 = -4.51/1.50. None appears anywhere in the article. The worst is
    #: 10.0 = 0.01/0.001, a quotient of two rounded numbers whose true value,
    #: given the printed precision, lies roughly between 5 and 24.
    #:
    #: A statcheck-style tool exists to ask whether a printed statistic agrees
    #: with its printed p. Fed a statistic WE computed from that paper's own
    #: numbers, it is checking our arithmetic against their p and reporting the
    #: answer as a fact about them.
    #:
    #: THE TEST IS CORROBORATION, NOT A DECLARATION. A boolean the model sets
    #: fails open when the model forgets; asking whether the number is in the
    #: paper cannot be forgotten. `absent` does not accuse anyone -- it says
    #: this number is ours, so no tool may treat it as theirs.
    #:
    #: THE VERDICT IS ASYMMETRIC AND MUST BE READ THAT WAY. `absent` is
    #: DECISIVE: the numeral is nowhere in the article, so we wrote it.
    #: `present` is NOT evidence the paper printed it as a test statistic --
    #: only that the numeral occurs somewhere, and for a short or round number
    #: that is nearly free. MEASURED on ajcp.70049: the model's derived
    #: `2.658` is correctly caught `absent`, while its derived `10.0`
    #: (= 0.01/0.001, and the most corrupt of the four, since its true value
    #: given the printed precision spans roughly 5 to 24) stamps `present`
    #: because "10" appears in the paper, as it does in every paper.
    #:
    #: So the field may GATE a tool on `absent` and may never LICENSE one on
    #: `present`. A stronger test -- is the numeral present in a context that
    #: reads as a reported statistic -- is the follow-up, and until it exists
    #: `present` means "not shown to be ours", not "shown to be theirs".
    statistic_in_text: str | None = None
    p_value: float | None = None
    p_is_threshold: bool = False
    effect_size: str | None = None
    ci: str | None = None
    # AS COMPUTED BY US, kept separate from what the paper PRINTED so a derived
    # number can never be mistaken for a published one. MEASURED 2026-08-16 over
    # 2,091 archived anatomy rows: a printed effect size appears in 31% and an
    # interval in 22%, so roughly two thirds of the comparisons in the
    # literature reach a reader without the quantity that decides whether they
    # matter. `mde_80` is the design's sensitivity -- the smallest effect it
    # could reliably detect -- which is a property of n and alpha alone and
    # carries no assumption about what counts as large.
    effect_size_estimated: dict | None = None
    mde_80: dict | None = None
    correction_applied: str | None = None      # "bonferroni" | "fdr" | None
    assumption_checks_reported: list[str] = field(default_factory=list)
    narrative_tier: str | None = None   # None => infer; never default to a truthy tier
    appears_in_abstract: bool = False
    appears_in_conclusions: bool = False
    is_stated_primary_outcome: bool = False
    provenance_quote: str | None = None
    confidence: str = "low"

    @property
    def canonical_type(self) -> str:
        """The assumption-vocabulary spelling. `test_type` is a free string, and
        the scaffold names several tests differently (`t_test_paired`)."""
        return canonical_test_type(self.test_type)

    @property
    def is_parametric(self) -> bool:
        return self.canonical_type in PARAMETRIC_TESTS

    def required_assumptions(self) -> tuple[str, ...]:
        return TEST_ASSUMPTIONS.get(self.canonical_type, ())

    def unreported_assumptions(self) -> tuple[str, ...]:
        reported = normalize_assumption_labels(self.assumption_checks_reported)
        return tuple(a for a in self.required_assumptions() if a not in reported)


@dataclass
class Hypothesis:
    id: str
    statement: str
    study_id: str | None = None
    status: str = "unstated"            # CONFIRMATORY_STATUS
    test_ids: list[str] = field(default_factory=list)
    appears_in_abstract: bool = False
    provenance_quote: str | None = None
    confidence: str = "low"


#: What a paper may assert about a hypothesis, in its own voice.
INTERPRETATION_ASSERTS = ("supported", "not_supported", "mixed", "none")


@dataclass
class Interpretation:
    """What the paper SAID a result means, kept apart from what the result IS.

    The register says what was printed and `StatisticalTest` says what came
    out; this says what the authors told a reader it showed. The difference is
    the finding -- the same shape as the multiple-comparisons check, which
    fires on the ABSENCE of a correction rather than on a wrong number.

    WHY IT IS EXTRACTED SEPARATELY FROM `Hypothesis`. A hypothesis is a claim
    made in advance; an interpretation is a claim made about evidence, and the
    two diverge in exactly the case worth catching -- the hypothesis is
    unchanged while the abstract describes a null result as a positive one.
    Folding them together loses the divergence by construction.

    THE CEILING ON WHAT THIS MAY DECIDE. Almost everything in an interpretation
    is a judgment call, and a toolkit whose cardinal rule is no false
    accusation must not litigate judgment. So the fields divide in two:

      ARITHMETIC, and safe to check -- `asserts` and `hedged` against a printed
      p and a stated alpha. Whether p exceeds alpha is not a matter of opinion,
      and neither is whether the paper hedged, once the sentence is quoted.

      DESCRIPTIVE, and extraction-only -- `causal_language`, `generalization`,
      `location`. These are recorded because a reviewer wants them and because
      the expected-statistics checklist will, and they generate NO finding.
      `causal_language` on a cross-sectional design is a real criticism and a
      terrible automated accusation: "predicts" is causal in one field's
      register and standard usage in another's.

    `claim` is the paper's OWN sentence and must be quotable. An interpretation
    we paraphrase is our reading of their reading, and the whole point is to
    hold their words beside their numbers.
    """

    id: str
    claim: str
    location: str = "results"        # abstract|title|results|discussion|conclusion
    test_ids: list[str] = field(default_factory=list)
    hypothesis_id: str | None = None
    asserts: str = "none"            # INTERPRETATION_ASSERTS
    #: Any softening at all -- "suggests", "may", "trend", "warrants further
    #: study". A hedge is the paper telling a reader not to over-read the
    #: result, which is the honest behavior, so a hedged claim is never a
    #: finding no matter what the p-value says.
    hedged: bool = False
    causal_language: bool = False
    generalization: str | None = None
    provenance_quote: str | None = None
    confidence: str = "low"


@dataclass
class Study:
    id: str
    label: str
    design: str = "unknown"             # rct | cohort | cross_sectional | cluster_rct | ...
    n: int | None = None
    unit_of_analysis: str = "individual"
    preregistered: bool | None = None
    registry_id: str | None = None
    clustered: bool = False

    #: THE SIGNIFICANCE THRESHOLD THE PAPER ITSELF DECLARED, and only that.
    #: None means the paper did not say, which is the common case and is NOT a
    #: licence to assume .05: a paper that pre-registered .01, or adopted .10
    #: for an exploratory analysis, would be accused by that assumption for
    #: reporting exactly what it committed to. `claims.check_claim_vs_result`
    #: refuses rather than defaults, on the precedent of `76e9cc3`, which
    #: DELETED four precision defaults instead of defaulting them.
    alpha: float | None = None

    #: Declared in findings.schema.json, asked for in the prompt, and dropped on
    #: load until now for want of these two lines. Same defect as `derivation`.
    #:
    #: `n_per_group` is [{label, n}] per arm; `sample_flow` is [{stage, n,
    #: reason}] -- a CONSORT flow. Together they make an arithmetic check
    #: possible that nothing can do today: a flow must be non-increasing, arms
    #: must sum to the analysed total, and no test may claim more subjects than
    #: the stage it belongs to. MEASURED over the archive: 2 of 103 tests carry
    #: an n EXCEEDING their study's n, which is the impossible direction. The
    #: benign direction -- a test n BELOW the study n, from per-model
    #: missingness -- is common and must never be flagged.
    n_per_group: list[dict] = field(default_factory=list)
    sample_flow: list[dict] = field(default_factory=list)


@dataclass
class PaperAnatomy:
    paper_id: str
    studies: list[Study] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    hypotheses: list[Hypothesis] = field(default_factory=list)
    tests: list[StatisticalTest] = field(default_factory=list)
    interpretations: list[Interpretation] = field(default_factory=list)

    def variable(self, vid: str | None) -> Variable | None:
        return next((v for v in self.variables if v.id == vid), None)


# --------------------------------------------------------------------------
# Narrative ranking -- which tests carry the paper
# --------------------------------------------------------------------------

def infer_narrative_tier(test: StatisticalTest, hypothesis: Hypothesis | None = None) -> str:
    """Rank a test by how load-bearing it is for the paper's claims.

    A discrepancy in a headline result and one in an unremarked baseline row
    are not equivalent events, and severity should reflect that.
    """
    if test.is_stated_primary_outcome:
        return "primary"
    if test.appears_in_abstract:
        return "primary"
    if hypothesis is not None and hypothesis.status == "preregistered_confirmatory":
        return "primary"
    if test.appears_in_conclusions:
        return "secondary"
    if hypothesis is not None and hypothesis.status == "confirmatory":
        return "secondary"
    if hypothesis is not None and hypothesis.status == "exploratory":
        return "exploratory"
    if test.hypothesis_id:
        return "secondary"
    return "incidental"


SEVERITY_WEIGHT = {"primary": 1.0, "secondary": 0.7, "exploratory": 0.4, "incidental": 0.2}


def weight_finding_severity(base_severity: str, tier: str) -> dict:
    """Contextualise a forensic severity by narrative importance.

    This NEVER escalates -- an anomaly in a headline claim is not made worse
    than the mathematics supports. It only records how much the finding matters
    for the paper's conclusions, so a report can lead with what is load-bearing.

    UNWIRED, AND THE REASON IS MEASURED RATHER THAN AN OVERSIGHT (2026-08-11).
    Nothing calls this, so no finding carries `narrative_weight` and a report
    cannot tell a primary-outcome anomaly from a baseline-table one. The
    obvious wiring is to join each finding to an anatomy test and take
    `infer_narrative_tier` of it -- and THAT JOIN DOES NOT EXIST. Both sides
    carry only a free-text `location`, so it was measured over every archived
    run holding both a findings list and an anatomy block:

        11 runs, 283 findings
          89.0%  no matching test at all      (252)
           5.7%  exactly one, exact match      (16)
           4.9%  exactly one, by substring     (14)
           0.4%  ambiguous, several matched     (1)

    A tier stamped on 10.6% of findings is worse than none, because the 10.6%
    is not a random sample: it is the findings whose location string happened
    to be phrased like a test's, which skews toward verbose per-cell table
    locations and away from prose findings entirely. A report that leads with
    the "load-bearing" findings chosen that way leads with an artefact of
    string formatting, and `undermines_headline_claim` is exactly the flag a
    reader would weigh most.

    WHAT WOULD ACTUALLY WIRE IT: a `test_id` on the finding schema, emitted by
    the sweep beside `location`, so the join is DECLARED rather than guessed.
    That is a schema change needing a paid run to validate, so it is a decision
    rather than a fix. `tests/test_narrative_weight_join.py` pins the 89% so
    that the day a real join exists, it fails and says so.
    """
    return {
        "severity": base_severity,
        "narrative_tier": tier,
        "narrative_weight": SEVERITY_WEIGHT.get(tier, 0.2),
        "undermines_headline_claim": tier == "primary",
    }


# --------------------------------------------------------------------------
# Multiplicity
# --------------------------------------------------------------------------

# Values that mean "the authors applied NO correction". The schema documents
# `correction_applied: "none"`, and "none" is truthy -- so filtering on
# `not t.correction_applied` treated every compliantly-labelled test as already
# corrected and silently reported zero tests.
_NO_CORRECTION = {None, "", "none", "None", "NONE", "n/a", "na", "-"}

#: Values that mean NOBODY SAID, which is a third state and not a correction.
#:
#: MEASURED 2026-08-18: "not reported", "unclear", "unknown", "not stated" were
#: in neither set, so `_is_uncorrected` returned False for them and every one was
#: silently counted as ALREADY CORRECTED -- dropped from the family, shrinking
#: the multiplicity denominator on the strength of the authors not having said.
#: The direction is safe (it understates the problem rather than manufacturing
#: one) and it is still absence read as knowledge, which is the defect this
#: repository keeps finding in itself.
_UNKNOWN_CORRECTION = {
    "not reported", "unreported", "not stated", "unstated", "unclear",
    "unknown", "not applicable", "n.r.", "nr", "not specified", "unspecified",
}


def correction_status(test: "StatisticalTest") -> str:
    """`none` | `applied` | `unknown` -- three states, because there are three.

    `none` means the authors say they applied no correction. `unknown` means
    they did not say. Only the first is evidence about the paper's analysis;
    the second is evidence about its reporting, and folding it into either of
    the others loses the distinction the multiplicity arithmetic rests on.
    """
    c = test.correction_applied
    key = c.strip().lower() if isinstance(c, str) else c
    if key in {x.lower() if isinstance(x, str) else x for x in _NO_CORRECTION}:
        return "none"
    if isinstance(key, str) and key in _UNKNOWN_CORRECTION:
        return "unknown"
    return "applied"


def _is_uncorrected(test: "StatisticalTest") -> bool:
    """Kept, and now means exactly `correction_status(...) == "none"`.

    An UNKNOWN status is deliberately NOT uncorrected: counting a test whose
    correction the authors never described as one they declined to correct would
    manufacture a multiplicity problem out of a reporting gap, which is the
    error this codebase treats as unrecoverable. It is reported separately
    instead -- see `multiplicity_report`'s `n_correction_unknown`.
    """
    return correction_status(test) == "none"


def multiplicity_report(
    tests: list[StatisticalTest], family_label: str, alpha: float = 0.05
) -> dict:
    """Compute what running k tests at alpha actually implies.

    Deterministic arithmetic, not a judgement: the family-wise error rate under
    independence, four correction thresholds, and how many of the reported
    'significant' results survive each.

    FOUR METHODS, REPORTED AS A BOUND
    ---------------------------------
    "How many results survive correction" has no single answer -- it depends on
    which error rate you demand. So this reports the whole attainable interval
    and reads the verdict off a stated point, the same rule `tools/csf.py` uses
    for an unknown baseline correlation (report the sensitivity profile, take
    the verdict at `VERDICT_RHO`). Reporting one method's count as though it
    were the answer hides that the interval exists.

    * **Bonferroni** -- FWER, alpha/m. Strictest of the classical three.
    * **Holm** -- step-DOWN FWER. Same guarantee and same assumptions as
      Bonferroni and never rejects less, so Bonferroni alone was strictly
      dominated. `prompts/schema/findings.schema.json` has always ACCEPTED
      `holm` as a `correction_applied` value, so the toolkit could read the
      word off a paper and not compute it.
    * **Benjamini-Hochberg** -- step-UP FDR. The most permissive of the four,
      hence the ceiling.
    * **Benjamini-Yekutieli** -- BH with alpha divided by the harmonic number
      c(m) = sum_{i=1..m} 1/i. The honest FDR method when the test statistics
      are CORRELATED, which is the normal case in these papers (several
      outcomes measured on the same subjects). Correlation is why it belongs
      here at all: BH's guarantee is proved under independence or positive
      regression dependence, BY's holds under arbitrary dependence.

    THE ORDERING IS NOT THE TEXTBOOK ONE, so the floor is COMPUTED, not assumed.
    Bonferroni <= Holm <= BH <= uncorrected holds always, and BY <= BH holds
    always. But BY does NOT sit between: its first step-up threshold is
    alpha/(m*c(m)), which is SMALLER than Bonferroni's alpha/m, so a family with
    one small p and the rest large is rejected by Bonferroni and Holm and not by
    BY. Measured against R's `p.adjust` on 5,000 random p-vectors (m drawn from
    1..30, alpha = .05), BY rejected fewer than Holm on 141 of them -- 2.8%.
    Minimal case: p = [.02, .90], where Bonferroni and Holm each reject one and
    BY rejects none. Hard-coding "Bonferroni is the floor" would therefore have
    reported a floor above a number this function itself computed.

    CAVEATS, stated because they are easy to get wrong:
    * What counts as a FAMILY is a judgement call. We compute per supplied
      family and never assert that all tests in a paper form one family --
      which is why `family_label` has no default and the caller must state it.
    * The independence assumption inflates FWER relative to correlated tests,
      so `fwer_if_independent` is an UPPER bound.
    * Tests the authors already corrected are excluded from the naive count.
    * Undisclosed analytic flexibility (Gelman's "garden of forking paths")
      means the effective number of comparisons can exceed the reported count.
      This arithmetic is therefore a floor on the multiplicity problem.
    """
    considered = [t for t in tests if _is_uncorrected(t)]
    # COUNTED AND REPORTED, NEVER FOLDED IN EITHER DIRECTION. A test whose
    # correction status the authors never stated belongs in neither the naive
    # family nor the corrected one, and saying how many there are is the only
    # honest treatment: it tells a reader how much of this arithmetic rests on
    # what the paper actually disclosed.
    n_unknown = sum(1 for t in tests if correction_status(t) == "unknown")
    k = len(considered)
    if k == 0:
        return {"family": family_label, "n_tests": 0, "note": "no uncorrected tests"}

    p_values = [t.p_value for t in considered if isinstance(t.p_value, (int, float))]
    fwer = 1 - (1 - alpha) ** k
    bonferroni = alpha / k
    expected_false_positives = k * alpha

    # m is the FAMILY size (k), not the number of extractable p-values. Using
    # len(p_values) made the step-up methods anti-conservative exactly where
    # Bonferroni becomes conservative: 100 tests with 1 readable p gave a BH
    # threshold of 0.05, as though a single test had been run. Every method
    # below uses this same m, for that same reason.
    m = k
    # c(m), the harmonic number BY divides alpha by. c(1) = 1, so BY and BH
    # coincide on a family of one.
    c_m = sum(1.0 / i for i in range(1, m + 1))

    # `<=` throughout, matching R's p.adjust (p_adj <= alpha). Strict `<`
    # disagreed with R on 30 of 3012 fuzzed vectors -- e.g. five tests all at
    # p=.01 against a Bonferroni threshold of exactly .01.
    n_sig = sum(1 for p in p_values if p <= alpha)
    n_sig_bonf = sum(1 for p in p_values if p <= bonferroni)

    ordered = sorted(p_values)

    # Holm: step-DOWN. Reject while p_(i) <= alpha/(m - i + 1) and STOP at the
    # first failure -- everything after it is retained regardless of its own
    # p-value. That stop is the whole method; a loop that kept testing would be
    # a different, invalid procedure. It is what R's `p.adjust(method="holm")`
    # produces by running a cummax over (m - i + 1) * p_(i), which makes the
    # adjusted values non-decreasing and so counts exactly up to the first
    # failure.
    holm_threshold = None
    n_sig_holm = 0
    for i, p in enumerate(ordered, start=1):
        step = alpha / (m - i + 1)
        if p > step:
            break
        holm_threshold = step
        n_sig_holm = i

    # Benjamini-Hochberg: step-UP, largest i with p_(i) <= i/m * alpha.
    bh_threshold = None
    n_sig_bh = 0
    # Benjamini-Yekutieli: the same step-up against alpha/c(m).
    by_alpha = alpha / c_m
    by_threshold = None
    n_sig_by = 0
    for i, p in enumerate(ordered, start=1):
        if p <= (i / m) * alpha:
            bh_threshold = (i / m) * alpha
            n_sig_bh = i
        if p <= (i / m) * by_alpha:
            by_threshold = (i / m) * by_alpha
            n_sig_by = i

    # The bound, COMPUTED rather than assumed -- see the docstring: BY can fall
    # below Bonferroni (141 of 5,000 fuzzed vectors), so naming Bonferroni the
    # floor would state a floor above a number in this very dict.
    # Ordered strictest-intent first so a TIE -- which is the common case, since
    # all four coincide whenever every p is far from every threshold -- names
    # Bonferroni as the floor and Benjamini-Hochberg as the ceiling rather than
    # whichever label sorts first alphabetically.
    survivors = (
        ("Bonferroni", n_sig_bonf),
        ("Holm", n_sig_holm),
        ("Benjamini-Yekutieli", n_sig_by),
        ("Benjamini-Hochberg", n_sig_bh),
    )
    floor_method, n_floor = min(survivors, key=lambda kv: kv[1])
    ceiling_method, n_ceiling = max(reversed(survivors), key=lambda kv: kv[1])

    return {
        "family": family_label,
        "n_tests": k,
        "n_with_p": len(p_values),
        "alpha": alpha,
        "fwer_if_independent": round(fwer, 4),
        "expected_false_positives": round(expected_false_positives, 2),
        "bonferroni_threshold": bonferroni,
        "holm_threshold": holm_threshold,
        "bh_threshold": bh_threshold,
        "by_threshold": by_threshold,
        "by_alpha": by_alpha,
        "by_harmonic_c_m": c_m,
        "n_significant_uncorrected": n_sig,
        "n_significant_bonferroni": n_sig_bonf,
        "n_significant_holm": n_sig_holm,
        "n_significant_bh": n_sig_bh,
        "n_significant_by": n_sig_by,
        "n_surviving_floor": n_floor,
        "n_surviving_ceiling": n_ceiling,
        "floor_method": floor_method,
        "ceiling_method": ceiling_method,
        # DELIBERATELY STILL PINNED TO BH, now that a bound exists. Two reasons.
        # (1) BH is the most permissive of the four, so `n_sig - n_sig_bh` is the
        #     SMALLEST claim loss any of them supports -- the conservative point
        #     to read a verdict off, in the direction that under-accuses. Pinning
        #     it to the floor method instead would maximise the accusation by
        #     construction, on a family we chose and a correction the paper never
        #     applied.
        # (2) `consequence.py` turns this field into `claims_affected`, which
        #     ranks findings, and `cli.py` prints it. Both read this one key by
        #     name (CONSEQUENCE_KEYS), so re-pinning it would silently re-rank
        #     every past finding. The strict-end loss is not lost: it is
        #     `n_significant_uncorrected - n_surviving_floor`.
        "n_claims_lost_to_correction": n_sig - n_sig_bh,
        # HOW MANY TESTS THE PAPER NEVER SAID ABOUT. Reported beside the family
        # rather than folded into it: these are neither known-uncorrected nor
        # known-corrected, and a reader needs the number to judge how much of
        # the arithmetic above rests on what the authors actually disclosed.
        "n_correction_unknown": n_unknown,
        # Every method here is a threshold rule over the SAME ordered p-values,
        # so the ordering below is arithmetic, not an assumption:
        # Bonferroni <= Holm <= BH <= uncorrected (Holm's step-down thresholds
        # dominate Bonferroni's fixed one, and BH's i/m*alpha dominates Holm's
        # 1/(m-i+1)*alpha at every i because i(m-i+1) >= m), and BY <= BH since
        # BY is BH at a smaller alpha. BY vs Bonferroni is genuinely
        # order-free and is NOT asserted. If the computed chain breaks, the
        # arithmetic is wrong -- surface that instead of clamping it away behind
        # a max(0, ...).
        "internal_inconsistency": not (
            n_sig_bonf <= n_sig_holm <= n_sig_bh <= n_sig and n_sig_by <= n_sig_bh
        ),
        "n_missing_p": k - len(p_values),
        "interpretation": (
            f"{k} uncorrected tests at alpha={alpha} imply a family-wise error rate of up to "
            f"{fwer * 100:.1f}% and about {expected_false_positives:.1f} false positives by "
            f"chance alone. Of {n_sig} results significant uncorrected, between {n_floor} "
            f"({floor_method}) and {n_ceiling} ({ceiling_method}) survive correction, depending "
            f"on which error rate you demand: {n_sig_bonf} Bonferroni, {n_sig_holm} Holm "
            f"(both family-wise), {n_sig_bh} Benjamini-Hochberg and {n_sig_by} "
            f"Benjamini-Yekutieli (both false-discovery-rate; BY is the one that holds under "
            f"the correlated outcomes these papers usually have). Reported claim loss is read "
            f"off Benjamini-Hochberg, the most permissive of the four, so "
            f"{n_sig - n_sig_bh} lost is the smallest loss any of these corrections supports."
        ),
        "caveats": [
            "Family definition is a judgement; this is computed for the supplied family only.",
            "FWER assumes independence and is an upper bound for correlated tests.",
            "Undisclosed analytic flexibility means the true comparison count may be higher.",
            "Survivor counts are a BOUND, not one number; which method applies depends on "
            "whether the family needs family-wise or false-discovery-rate control, and BY "
            "rather than BH once the test statistics are correlated.",
        ],
    }


# --------------------------------------------------------------------------
# Assumption + test-choice auditing
# --------------------------------------------------------------------------

def assumption_risk(test: StatisticalTest, outcome: Variable | None, study: Study | None = None) -> dict:
    """Judge whether unreported assumption checks actually matter here.

    Reporting a normality check is the exception, not the rule, so an
    "assumption check not reported" flag on its own would fire on nearly every
    paper and carry no information. We escalate only when INDEPENDENT risk
    factors co-occur, and we say which ones fired.

    Two corrections a red-team pass forced:
    * Factors are deduplicated by KIND. "outcome is ordinal" and "outcome is
      bounded" are the same underlying fact for a Likert item, and counting both
      let a t-test at n=1,000,000 reach `suspicious` off one observation.
    * Large n neutralises the normality concern (CLT applies to the sampling
      distribution of the mean), so it cannot be a risk factor there.
    """
    unreported = test.unreported_assumptions()

    # AN UNKNOWN TEST TYPE IS AN UNKNOWN, NOT A CLEAN BILL. `required_assumptions`
    # returns `()` for anything absent from `TEST_ASSUMPTIONS`, so `unreported`
    # is empty and the branch below used to print "Required assumption checks
    # were reported." -- a POSITIVE FACTUAL CLAIM ABOUT THE PAPER that nothing
    # verified. The house failure mode: information we do not have, rendered
    # downstream as knowledge.
    #
    # MEASURED on 10.1002--ajcp.70049: the paper runs Poisson regression,
    # negative binomial regression and HLM. TEST_ASSUMPTIONS holds none of the
    # first two, so 10 of its 14 tests landed on `other` and every one was
    # certified as having reported its assumption checks. None had.
    #
    # THIS IS NOT A VOCABULARY GAP AND WIDENING THE VOCABULARY DOES NOT CLOSE
    # IT. `test_type` is a free string in the schema, not an enum -- the model
    # was always free to write `poisson_regression` and wrote `other`. Adding
    # names lowers how often this fires; only failing closed removes the
    # channel, and it removes it for every family nobody has thought of yet
    # (gee, quantile_regression, tobit, zero-inflated NB, Weibull AFT).
    #
    # THE PROJECT HAS ALREADY RULED ON THIS ERROR CLASS ON THE DENIAL PATH --
    # see the note above `_denial_clears`: an authors' denial cleared the check
    # and printed the same clean bill, "the house failure mode, with the sign
    # flipped." Same failure, second path.
    #
    # `indeterminate` is the honest severity: it is not an allegation, and the
    # note says which of the two facts we are missing.
    if test.canonical_type not in TEST_ASSUMPTIONS:
        return {
            "severity": "indeterminate",
            "unreported_assumptions": [],
            "reasons": [],
            "note": (
                f"Test type {test.test_type!r} is not in the assumption "
                "vocabulary, so which checks it requires is unknown and none "
                "was verified. This is a limit of ours, not a finding about "
                "the paper."
            ),
        }

    if test.canonical_type in RANK_BASED_TESTS:
        return {
            "severity": "consistent",
            "unreported_assumptions": list(unreported),
            "reasons": [],
            "note": "Rank-based test; distributional assumptions are weak.",
        }

    if not unreported:
        return {"severity": "consistent", "unreported_assumptions": [], "reasons": [],
                "note": "Required assumption checks were reported."}

    if not test.is_parametric:
        # Logistic/Cox etc. have hard assumptions of their own; report them
        # without escalating on distributional grounds.
        return {
            "severity": "indeterminate" if unreported else "consistent",
            "unreported_assumptions": list(unreported),
            "reasons": [],
            "note": (
                f"{test.test_type} does not assume normality, but its own assumptions "
                f"({', '.join(unreported)}) were not reported as checked."
            ),
        }

    # Independent risk factors, keyed so the same fact cannot be counted twice.
    factors: dict[str, str] = {}
    n = test.n if isinstance(test.n, int) else None

    if n is not None and n < 30:
        factors["small_n"] = (
            f"small sample (n={n}) where the CLT does not rescue non-normality"
        )

    # Measurement-scale concern: ONE factor, however many ways it is visible.
    if outcome is not None and n is not None and n < 100:
        if outcome.family in NON_INTERVAL_FAMILIES:
            factors["scale"] = (
                f"outcome '{outcome.name}' is {outcome.family}, for which a parametric "
                "location test is questionable at this sample size"
            )
        elif outcome.lower_bound is not None and outcome.upper_bound is not None:
            factors["scale"] = (
                f"outcome is bounded [{outcome.lower_bound}, {outcome.upper_bound}], so "
                "normality is at best an approximation at this sample size"
            )

    # Independence violated BY DESIGN is a structural problem, not a distributional one,
    # and holds at any n.
    if study is not None and study.clustered and "independence" in unreported:
        factors["clustering"] = (
            "clustered/multi-site design analysed without accounting for clustering "
            "(independence violated by design, not by chance)"
        )

    reasons = list(factors.values())
    if "clustering" in factors:
        severity = "suspicious"        # structural; stands on its own
    elif len(factors) >= 2:
        severity = "suspicious"
    elif len(factors) == 1:
        severity = "indeterminate"
    else:
        severity = "consistent"

    return {
        "severity": severity,
        "unreported_assumptions": list(unreported),
        "reasons": reasons,
        "risk_factors": sorted(factors),
        "note": (
            "Unreported assumption checks are near-universal and are NOT treated as a finding "
            "on their own; this escalates only when independent risk factors co-occur."
        ),
    }


def check_test_variable_compatibility(test: StatisticalTest, anatomy: PaperAnatomy) -> dict:
    """Did the design use a test its variables can support?

    Deliberately CONSERVATIVE after a red-team pass found the first version
    flagged 7 of 9 legitimate practices. Rules fire only when the variable's
    family is KNOWN and the mismatch is unambiguous. Widely-accepted practices
    that were previously flagged and are now explicitly allowed:

    * Pearson on a Likert COMPOSITE (standard in psychometrics) -- only a single
      ordinal item or an ordered-category variable is questionable.
    * Linear probability models on a binary outcome (standard in economics).
    * Chi-squared on binned continuous data (the binning makes it categorical).
    """
    problems: list[str] = []
    outcome = anatomy.variable(test.outcome_var)

    # Unknown typing is not evidence of anything. The default family is
    # "unknown", and the first version happily emitted "Logistic regression
    # requires a binary outcome; 'mortality' is unknown."
    if outcome is None or outcome.family in ("unknown", "", None):
        return {
            "severity": "indeterminate",
            "problems": [],
            "note": (
                "Outcome variable was not typed (family unknown), so test/variable "
                "compatibility cannot be assessed. Not a finding."
            ),
        }

    if test.is_parametric and outcome.family == "nominal_category":
        problems.append(
            f"{test.test_type} assumes a numeric outcome, but '{outcome.name}' is unordered "
            "categorical."
        )
    if test.test_type == "pearson_correlation" and outcome.family in (
        "ordinal_category", "likert_item",
    ):
        problems.append(
            f"Pearson correlation on '{outcome.name}' ({outcome.family}); Spearman is the "
            "conventional choice for a single ordinal item. (A Likert COMPOSITE would be fine.)"
        )
    if test.test_type == "logistic_regression" and outcome.family not in ("binary", "proportion"):
        problems.append(
            f"Logistic regression requires a binary/proportion outcome; '{outcome.name}' is "
            f"{outcome.family}."
        )
    if test.test_type in ("cox_regression", "log_rank") and outcome.family != "time_to_event":
        problems.append(
            f"{test.test_type} requires a time-to-event outcome; '{outcome.name}' is "
            f"{outcome.family}."
        )

    # Confidence gate: an extraction we do not trust must not become an accusation.
    # Compared case-insensitively -- "Low" previously slipped through to `suspicious`.
    low = {"low", ""}
    if problems and (
        str(test.confidence).strip().lower() in low
        or str(outcome.confidence).strip().lower() in low
    ):
        return {
            "severity": "indeterminate",
            "problems": problems,
            "note": (
                "Test/variable typing was extracted with LOW confidence, so this mismatch is "
                "reported for human confirmation rather than as a finding."
            ),
        }
    return {
        "severity": "suspicious" if problems else "consistent",
        "problems": problems,
        "note": "Test-to-variable compatibility check.",
    }


# --------------------------------------------------------------------------
# The per-paper table
# --------------------------------------------------------------------------

TABLE_COLUMNS = (
    "id", "tier", "location", "test_type", "outcome", "outcome_type",
    "n", "statistic", "p", "effect_size", "correction",
    "assumptions_required", "assumptions_unreported", "assumption_risk",
    "compatibility", "confidence",
)


def build_test_table(anatomy: PaperAnatomy, alpha: float = 0.05) -> list[dict]:
    """One row per statistical test -- the enumeration everything else needs."""
    studies = {s.id: s for s in anatomy.studies}
    hypotheses = {h.id: h for h in anatomy.hypotheses}
    rows = []
    for t in anatomy.tests:
        outcome = anatomy.variable(t.outcome_var)
        study = studies.get(t.study_id or "")
        tier = t.narrative_tier or infer_narrative_tier(t, hypotheses.get(t.hypothesis_id or ""))
        risk = assumption_risk(t, outcome, study)
        compat = check_test_variable_compatibility(t, anatomy)
        rows.append({
            "id": t.id,
            "tier": tier,
            "location": t.location,
            "test_type": t.test_type,
            "outcome": outcome.name if outcome else (t.outcome_var or ""),
            "outcome_type": (
                f"{outcome.family}/{outcome.measurement_level}" if outcome else "unknown"
            ),
            "n": t.n,
            "statistic": t.statistic_value,
            "p": t.p_value,
            "effect_size": t.effect_size,
            "correction": t.correction_applied or "none",
            # What the test REQUIRES, not merely what went unchecked. The
            # unreported list is the complement, and on its own it let a reader
            # see that `normality` was not checked without ever being told that
            # this test assumes it.
            "assumptions_required": list(t.required_assumptions()),
            "assumptions_unreported": ", ".join(risk["unreported_assumptions"]) or "-",
            "assumption_risk": risk["severity"],
            "compatibility": compat["severity"],
            "confidence": t.confidence,
        })
    rows.sort(key=lambda r: (NARRATIVE_TIERS.index(r["tier"]) if r["tier"] in NARRATIVE_TIERS else 9))
    return rows


def anatomy_summary(anatomy: PaperAnatomy, alpha: float = 0.05) -> dict:
    """Full anatomy report: table, multiplicity per tier, and audit flags."""
    table = build_test_table(anatomy, alpha=alpha)
    by_tier: dict[str, list[StatisticalTest]] = {}
    hypotheses = {h.id: h for h in anatomy.hypotheses}
    for t in anatomy.tests:
        tier = t.narrative_tier or infer_narrative_tier(t, hypotheses.get(t.hypothesis_id or ""))
        by_tier.setdefault(tier, []).append(t)

    return {
        "paper_id": anatomy.paper_id,
        "counts": {
            "studies": len(anatomy.studies),
            "variables": len(anatomy.variables),
            "hypotheses": len(anatomy.hypotheses),
            "tests": len(anatomy.tests),
            "tests_by_tier": {k: len(v) for k, v in by_tier.items()},
        },
        "test_table": table,
        # The whole-paper roll-up is labelled for what it is. It is NOT a claim
        # that every test in the paper is one family -- the per-tier reports
        # beside it are the ones with a defensible family, and the tool refuses
        # to invent a label when a caller supplies none.
        "multiplicity_overall": multiplicity_report(
            anatomy.tests, "every reported test, pooled (not a defensible family)", alpha
        ),
        "multiplicity_by_tier": {
            tier: multiplicity_report(ts, f"{tier} tests", alpha) for tier, ts in by_tier.items()
        },
        "low_confidence_extractions": [
            r["id"] for r in table if r["confidence"] == "low"
        ],
        "unverifiable_note": (
            "Rows marked low confidence were extracted without a supporting quote and must be "
            "confirmed against the paper before being relied on."
        ),
    }


# --------------------------------------------------------------------------
# Loading from the sweep's JSON
# --------------------------------------------------------------------------

#: Fields the PIPELINE sets and the model may never supply. Stripped from every
#: model-authored dict before it reaches a dataclass, on EVERY construction path.
#:
#: Without this the fix to `bounds_are_stated` would have been decorative: both
#: paths build their records by filtering a model dict against the dataclass
#: fields, so simply DECLARING `provenance_verdict` would have let the model
#: write `"provenance_verdict": "verbatim"` and re-acquire the `impossible`
#: ceiling it just lost -- the same laundering one level down. A verdict about
#: whether the model's quote is real cannot be authored by the model, for the
#: same reason `quote_verified` and `reproduction_valid` are not.
PIPELINE_ONLY_FIELDS = frozenset({"provenance_verdict", "statistic_in_text"})


def _pick(d: dict, cls) -> dict:
    """Keep only keys the dataclass declares, so schema drift cannot crash us.

    Also drops `PIPELINE_ONLY_FIELDS`: a model-supplied verdict about its own
    evidence is not evidence.
    """
    allowed = set(cls.__dataclass_fields__) - PIPELINE_ONLY_FIELDS
    return {k: v for k, v in (d or {}).items() if k in allowed}


def anatomy_from_findings(findings: dict) -> PaperAnatomy | None:
    """Build a PaperAnatomy from a findings.json `anatomy` block.

    Returns None when the sweep emitted no anatomy -- which is itself worth
    reporting, since without it the tools ran on defaults.
    """
    raw = (findings or {}).get("anatomy")
    if not raw:
        return None
    a = PaperAnatomy(paper_id=(findings.get("paper_id") or "unknown"))
    a.studies = [Study(**_pick(s, Study)) for s in raw.get("studies", []) or []]
    a.variables = [Variable(**_pick(v, Variable)) for v in raw.get("variables", []) or []]
    a.hypotheses = [Hypothesis(**_pick(h, Hypothesis)) for h in raw.get("hypotheses", []) or []]
    a.tests = [StatisticalTest(**_pick(t, StatisticalTest)) for t in raw.get("tests", []) or []]
    a.interpretations = [Interpretation(**_pick(i, Interpretation))
                         for i in raw.get("interpretations", []) or []]
    return a


def render_anatomy_markdown(anatomy: PaperAnatomy, alpha: float = 0.05) -> str:
    """The per-paper statistical-test table, as markdown."""
    s = anatomy_summary(anatomy, alpha=alpha)
    out = [f"## Statistical anatomy — {anatomy.paper_id}", ""]
    c = s["counts"]
    out.append(
        f"{c['studies']} study/ies · {c['variables']} variables · {c['hypotheses']} hypotheses · "
        f"{c['tests']} tests {c['tests_by_tier']}"
    )
    out.append("")
    m = s["multiplicity_overall"]
    if m.get("n_tests"):
        out += ["### Multiplicity", "", m["interpretation"], ""]
        for cav in m["caveats"]:
            out.append(f"- _{cav}_")
        out.append("")
    out += ["### Reported statistical tests (most load-bearing first)", "",
            "| tier | location | test | outcome (type) | n | p | correction | unreported assumptions | assumption risk | test/variable fit | conf |",
            "|---|---|---|---|---:|---:|---|---|---|---|---|"]
    for r in s["test_table"]:
        out.append(
            f"| {r['tier']} | {r['location']} | {r['test_type']} | {r['outcome']} ({r['outcome_type']}) "
            f"| {r['n'] if r['n'] is not None else ''} | {r['p'] if r['p'] is not None else ''} "
            f"| {r['correction']} | {r['assumptions_unreported']} | {r['assumption_risk']} "
            f"| {r['compatibility']} | {r['confidence']} |"
        )
    # WHAT EACH TEST ASSUMES. The table above lists only the assumptions that
    # went UNREPORTED, which is the complement of what a reader needs: it shows
    # `normality` unchecked without ever saying that this test assumes it, or
    # what normality means for THIS test (the sampling distribution of the group
    # means, of the paired differences, or of the residuals -- three different
    # claims that share one token).
    #
    # Grouped by test TYPE rather than repeated per test: a paper with 40
    # t-tests has one assumption set, and printing it 40 times would bury it.
    seen: list[str] = []
    for r in s["test_table"]:
        if r["test_type"] not in seen and r.get("assumptions_required"):
            seen.append(r["test_type"])
    if seen:
        out += ["", "### What each of these tests assumes", "",
                "_Assumptions are properties of the DESIGN AND DATA, which this review "
                "cannot inspect. They are listed so a reader knows what would have to "
                "hold for the reported result to mean what it says -- not as findings "
                "against the paper. Unreported assumption checks are near-universal in "
                "the literature._", ""]
        by_type = {r["test_type"]: r["assumptions_required"] for r in s["test_table"]}
        for test_type in seen:
            out.append(f"**{test_type}**")
            for line in describe_assumptions(by_type[test_type]):
                out.append(f"- {line}")
            out.append("")

    if s["low_confidence_extractions"]:
        out += ["", f"_Low-confidence extractions needing human confirmation: "
                    f"{', '.join(s['low_confidence_extractions'][:20])}_"]
    return "\n".join(out)
