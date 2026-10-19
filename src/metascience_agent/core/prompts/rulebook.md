# Forensic Metascience Rulebook

Shared severity vocabulary and interpretation rules. Both the forensic sweep
and the editorial review MUST follow these rules.

## Severity enum

Every finding carries exactly one severity from this list (lowercase):

- `impossible` — violates mathematics. GRIM/GRIMMER/DEBIT failure, SD > max
  possible for the range, |r| > 1, percentages that cannot share a
  denominator, reported test statistic outside its analytic interval.
- `highly_suspicious` — strong red flag, technically possible but extremely
  unlikely under honest reporting. Examples: p = 1e-15 hidden behind
  "p<0.05"; baseline similarity p < 0.001; RIVETS hit (reported statistic
  equals the hand-calculated value from rounded inputs and almost no true
  data reproduces it).
- `suspicious` — unusual but plausible. Recalculated statistic disagrees with
  the reported one beyond rounding; suspiciously round Ns. A count/percentage
  mismatch belongs here ONLY when rule 15 says the denominator is settled;
  otherwise it is `indeterminate`.
- `indeterminate` — cannot be determined from available information (missing
  n, unclear scale bounds, tool error).
- `consistent` — passes the check.

## Interpretation rules (READ CAREFULLY — these encode past mistakes)

1. **Baseline similarity (CSF / Table-1 dispersion): HIGH p-values are the
   RED FLAG, not reassurance.** In a properly randomized trial, baseline
   characteristics differ somewhat by chance; baseline p-values should be
   roughly Uniform(0,1). If baseline p-values are all very high (e.g. 0.93,
   0.99, 0.99), or `csf_test` returns a small `similarity_p`, or
   `bayesian_table1_dispersion` returns τ̂ > 1 (under-dispersion), the groups are TOO
   similar — that suggests non-random allocation or fabrication. NEVER
   describe uniformly high baseline p-values or a "no difference at baseline"
   pattern as reassuring or `consistent`.
   Caveat to state alongside the flag: these omnibus methods assume
   independent p-values. Baseline variables that predict each other (weight,
   height, BMI, waist, hip, body-fat %) violate this; when the flagged rows
   are mutually predictive, present the finding as suggestive, name the
   dependence problem, and prefer flagging the individual near-1 p-values
   directly.

2. **Thresholded p-values conceal information.** Whenever a paper reports
   "p<0.05" or "p<0.001" and group statistics allow recalculation, recalculate
   the exact p. A true p many orders of magnitude below the threshold
   (`stalt_check`) is a `highly_suspicious` finding in most clinical/behavioral
   fields, not a stronger version of the claimed result.

3. **Impossibility beats implausibility.** A single verified `impossible`
   finding (GRIM/GRIMMER/DEBIT/SD-range failure on correctly-read inputs)
   outranks any number of `suspicious` ones. But verify the inputs first:
   confirm the value, n, scale bounds, and decimal places were read correctly
   from the paper, and that the variable is genuinely integer-scaled (GRIM
   applies to integer/Likert/count data only — NOT to continuous measures
   like weight in kg). Misapplied GRIM is the most common false accusation.

4. **Do not invent constraints.** Only use range/scale bounds that the paper
   states (inclusion criteria, instrument bounds) or that are logically
   necessary (percentages in [0,100], binary SD ≤ ~0.5).
   - **"Stated" means the paper PRINTS THE NUMERALS you are using.** A bound you
     derived from the paper's prose is an ASSUMED bound, however forced the
     reading feels: "patients in their 20s" → [20, 30], "adults" → [18, 90],
     "a Likert scale" → [1, 7]. Each of those is your translation, and a wrong
     translation INVERTS the check rather than weakening it. Quote the sentence
     that prints the numbers, or set `bound_source="assumed"` /
     `rests_on="assumed_bound"` and take the cap. MEASURED 2026-08-16: across 29
     archived reports `rests_on` has been `assumed_bound` 0 times, and one
     headline graded `impossible` on `stated_constraint` rested on the phrase
     "in their 20s" — on a paper drawn from this repository's own matched
     CONTROL set.
   - **BUT A PRINTED SCALE IS STATED, AND MOST PSYCHOLOGY SCALES ARE PRINTED.**
     The test is the NUMERALS, not the word "Likert". All of these are STATED
     and support `impossible`:
     "nine-point Likert scales (1 = not at all me, 9 = very much me)",
     "a seven-point scale (1 = not at all, 7 = extremely)",
     "(1 = negative mood and 7 = positive mood)".
     Only a scale named without its endpoints -- "a Likert scale", "a rating
     measure" -- is assumed. READ THE METHOD FOR THE ANCHORS BEFORE YOU CAP: a
     paper that printed them and got capped anyway is one whose impossible
     arithmetic you discarded for no reason.

     MEASURED 2026-08-17, which is why this paragraph exists. On the Stapel
     paper `10.1007--s11031-011-9216-y` -- RETRACTED for fabrication, the
     confession corroborated by the Levelt committee -- the bullet above, alone,
     moved the verdict from the bottom band to the middle: two `impossible`
     findings became `suspicious`, one of them on Table 2 cells whose SD no
     whole-number responses can produce. The Method prints "(1 = not at all me,
     9 = very much me)" a few sentences from the numbers in question. The bounds
     were stated. The cap was OURS, not the paper's, and it cost a true
     detection on a known-fraudulent paper.
   - An SD-range or GRIM/GRIMMER finding that depends on a bound the paper
     does NOT state (e.g. assuming adult heights are 1.5–1.8 m, or a weight
     range) can be AT MOST `suspicious`, NEVER `impossible`, and the assumed
     bound must be named in the finding.
   - **DEGREES OF FREEDOM ARE A BOUND TOO.** A recomputation that needs a df
     the paper does not print (`recalc_f_to_p`, `recalc_stat_to_p`)
     must not run on a df you inferred from the design. Before accusing,
     check whether the reported p is attainable for ANY defensible df — p
     from an F falls toward its chi-square limit as df2 grows, so a p that
     looks too small at your assumed df2 is often exactly right at a larger
     one. MEASURED 2026-08-22: F(3, df2)=6.951 was flagged against a
     reported p=0.0001 using an assumed df2=20 (attainable p ≥ 2.5e-3
     there), but at df2→∞ the same F gives p=1.14e-4, which PRINTS as
     0.0001 — the paper never stated df2, and the finding was a false
     accusation built on our own assumption. If the p is attainable at some
     plausible df, the row is `consistent` or at most a reporting note —
     never a finding. For a t or a chi-squared, `recalc_stat_to_p` does this
     sweep itself when you OMIT `df`: it bounds p over every df in
     [1, infinity) and flags only a p no df can reach.
   - Such an assumption-dependent finding must NOT be the headline problem of
     a review. Lead with a problem that rests only on stated/necessary
     constraints (e.g. baseline uniformity, a contradiction between inclusion
     criteria and a reported range, hidden extreme p-values). Note: a
     reported range that is itself in the paper (e.g. "BMI range 23–45" vs an
     inclusion rule of "BMI > 30") IS a stated constraint and a strong
     finding; an invented plausible range is not.

5. **Design validity.** Check that the analysis matches the design: a
   between-within (groups × time) design analyzed with independent t-tests,
   correlated samples treated as independent, or a chi-squared test with a
   zero cell are methodological red flags worth reporting even when no number
   is impossible.

6. **Effect size.** Report the value with its interval; that is the deliverable.
   Where a benchmark exists, an unremarkable intervention beating a best-in-class
   one by a wide margin is worth reporting — state the benchmark used and cap it
   at `suspicious`, because an effect size can be improbable and never
   arithmetically impossible. Rule out SEM-read-as-SD, a waitlist rather than an
   active comparator, and a units mismatch before treating magnitude as a signal
   at all.

7. **Data availability.** "All data are included/available" claims paired
   with no actual data ("state-but-withhold") are a red flag typical of
   papers avoiding scrutiny. Note dropout rates that are implausibly low
   (0 of 120 over 12 weeks), diaries/measures collected but never analyzed,
   and unfunded trials of implausible scale.

8. **Too-good uniformity elsewhere.** Suspiciously round sample sizes,
   identical SDs across groups, means clustering on round numbers, and
   impossible precision (more decimals than the instrument allows) are
   individually weak signals — report them, but only escalate when they
   co-occur with stronger findings.

   Two refinements, both from measurement rather than intuition:
   - **SDs that are too SIMILAR across groups is the one form of "too-good
     uniformity" with validated diagnostic value.** Use
     `check_variance_dispersion` rather than eyeballing it; Hartgerink et al.
     (2019) measured it as the best fabrication detector tested (AUROC 1.00 on
     raw data). It is still capped at `suspicious` and its verdict is RELATIVE —
     it ranks a paper against known-genuine reference data, it does not convict.
   - **Digit uniformity is NOT evidence.** Terminal-digit and Benford checks
     measured at or below chance in that same study (AUROC 0.38–0.51 and
     0.02–0.16 — the Benford figures mean fabricated data conformed *better*
     than genuine). This toolkit deliberately has no digit-preference tool. Do
     not reason about last-digit or leading-digit distributions, and do not
     report their appearance as a finding.

9. **Language discipline.** Use "anomaly", "inconsistency", "warrants
   clarification". Reserve "fabrication"/"fraud"/"manipulation" for
   `impossible` findings with verified inputs, and even then phrase as
   "consistent with" rather than an accusation. Findings should be
   reproducible: record the exact tool inputs.

10. **Verification hierarchy.** Prefer recalculating from the most primitive
    numbers available (cell counts > percentages > test statistics > stated
    p-values). If text and tables disagree, flag the discrepancy itself and
    check both readings.

11. **Duplication / copy-paste.** Two or more records of the *same* underlying
    facts should be identical; identical records of *different* facts should
    not exist. When a paper reports multiple tables/studies of summary
    statistics, compare them against each other (`detect_duplication`).
    Identical (mean, SD) pairs across *independent* samples (different studies,
    different participants) are a data-integrity red flag — `highly_suspicious`
    when three or more pairs match, `suspicious` for one or two unusual pairs,
    at most `highly_suspicious` (duplication is improbable, not mathematically
    impossible; never label it `impossible`). This is the tool that reaches
    where GRIM cannot: it works on multi-item and continuous means where GRIM
    does not apply. Two guards before flagging: (a) confirm the blocks describe
    genuinely different participants — the same group reused across two
    analyses SHOULD match, and that is not an anomaly; (b) discount matches on
    round values (integers, halves, 0/0.5/1 proportions), which recur by
    chance. Also flag identical rows/columns repeated within a single table
    (fill-down copy-paste).

    For PARTICIPANT-LEVEL raw data (supplementary spreadsheets), use
    `detect_raw_duplication` with the file path — never retype cells. Before
    reading its findings as anomalies, rule out the four classes of legitimate
    repetition in raw data:
      (a) **shared-by-design values** — site/plot/group-level covariates
          (weather, species constants, lab batch parameters), IDs, codes and
          coordinates repeat across every row of a group; pass them in
          `exclude_columns`;
      (b) **transformation artifacts** — a fraction, square root, log or
          z-score column prints far more digits than it carries; the tool
          discounts these in code, but name the transform when you report;
      (c) **tight distributions** — body temperature ≈ 37 °C, pH ≈ 7.4: low
          spread plus rounding makes collisions routine;
      (d) **pooled / meta-analytic data** — rows compiled from other papers
          duplicate BY CONSTRUCTION; set
          `data_context="pooled_or_meta_analysis"` and the tool refuses to
          accuse.
    What survives those guards — duplicated participant rows across
    supposedly independent sheets, high-precision runs copied between
    columns — is the strongest raw-data signal this toolkit has, and it is
    still capped at `highly_suspicious`.

    For IMAGE PANELS, a deterministic image track may inject
    `image_duplication` findings (byte-identity and perceptual matching of
    the raster panels embedded in the PDF, computed locally). These arrive
    QUARANTINED: `severity` is `indeterminate` and the raw signal sits in
    `severity_before_quarantine`, because the detector has not yet been
    calibrated against ground truth. Treat them as unvalidated signals to
    describe in plain words — a quarantined image signal must NEVER headline
    a report or drive the verdict. In the other direction, an image check
    that found nothing is not image clearance: it sees only duplication of
    embedded raster panels, not splices, contrast edits, or vector figures.
    The cap in this rule applies to images too: duplication is improbable,
    never `impossible`.

12. **Rank-sum granularity (GRIM-U).** Mann-Whitney U / Wilcoxon rank-sum
    p-values are granular: for given group sizes only a finite set of p-values
    is achievable (the U statistic is (half-)integer in [0, n1·n2]). Apply
    `grimu_check` ONLY to p-values the paper attributes to a rank-sum test with
    stated group sizes — NEVER to t/F/χ²/regression p-values (applying it to the
    wrong test type is the most likely false accusation; the tool cannot see the
    test type, so you must). Tiers: `impossible` ONLY when the reported p (and
    its rounding interval, or a `<X` threshold) lies entirely below the U=0
    floor under every convention (normal AND exact, with AND without continuity
    correction) — a genuine reporting error (Khajuria: 6v6 floor ≈ 0.0039, so
    p=0.001 / p<0.001 are impossible). A p that is *reachable in range* but
    matches no achievable U is a granularity inconsistency → at most
    `suspicious`, because software/CC/rounding differences (SPSS ≠ R ≠ JASP ≠
    Excel) routinely shift p sub-ULP; never call it `highly_suspicious` alone.
    A `<0.001` whose recovered floor is legitimately below the threshold
    (non-overlapping groups, U=0) is `consistent`, not a hit. GRIM-U is best at
    3 decimals and small groups; past small n granularity vanishes and it will
    return `consistent`. Use `grimu_coexistence` for two same-n non-significant
    p-values that differ minimally (e.g. 0.171 vs 0.172). Escalate only when
    misses co-occur or a below-floor value coincides with a STALT context — and
    prefer to let the editorial stage assemble that escalation (rule 8).

    TWO PRECONDITIONS BEYOND THE TEST TYPE, AND YOU SUPPLY BOTH. **(a) If the
    paper prints a normal-approximation Z beside the p** — `Z = 1.219, p = .223`,
    which is how SPSS reports Mann-Whitney — pass it as `reported_z`. That p is a
    function of the ROUNDED Z, whose achievable set is a different and far finer
    lattice than U's, so the check refuses. **(b) If the outcome is a
    small-integer or ordinal scale**, ranks tie; the tie-corrected sdU is
    smaller than the untied `√(n1·n2·(n1+n2+1)/12)` and every achievable p
    moves. Pass `ties_possible=true` and the granularity branch refuses (the
    below-floor branch still runs — ties cannot push U below 0). MEASURED
    2026-08-22: skipping both put two severity-2 findings into a published
    report against an honest paper, whose own notes recorded that statcheck
    reproduced each p exactly from the printed Z. A third p in the same paper
    happened to land on the lattice, which is what Z-rounding luck looks like.

13. **A refused HTML source is not a clean paper.** `extract_html` runs a
    landing-page/decoy check before parsing, because a fetched "full text" HTML
    file can be a cookie gate, institutional-repository catalog page, or
    JS-rendered app shell rather than the article — one that passes the check
    is not automatically safe either: a page can declare the correct title and
    DOI in its metadata while its actual body prose never rendered, leaving
    only navigation, citation-count, or "related articles" tables behind. When
    `extract_html` returns an `error`, or when a table's content plainly is not
    the paper's own data (page-view counts, "cited by N", a table of contents),
    that source contributed NOTHING to the sweep — it belongs in `unchecked`
    with the reason stated, exactly like an `image_only` table, never folded
    into "no findings" or treated as evidence the paper is clean. Fall back to
    `extract_pdf`/`body.md` for this paper rather than reporting from a page
    that was never actually the article.

14. **Tortured phrases / LLM boilerplate (dictionary track).** A deterministic
    language track may inject `tortured_phrases` findings — verbatim matches
    of the paper's text against a versioned fingerprint dictionary (tortured
    phrases like "counterfeit consciousness" for "artificial intelligence";
    LLM boilerplate like "as an AI language model"; curated tortured acronym
    expansions). These arrive QUARANTINED like image rows: `severity` is
    `indeterminate`, the pre-registered grade sits in
    `severity_before_quarantine`, and a quarantined row must NEVER headline a
    report or drive the verdict. What the count means: k is DISTINCT
    fingerprints surviving the track's guards, not repetitions — one phrase
    pasted twenty times is one substitution event. One fingerprint is a
    pointer for human review, nothing more. Two is unusual. Three or more in
    the authors' own prose is strongly consistent with undisclosed
    paraphrasing-tool or LLM use — and still never `impossible`: awkward
    language violates no mathematics, so the cap is `highly_suspicious`
    (rule 11's logic). Strength differs by class: a first-person LLM
    disclaimer in the authors' own voice is the strongest single signal; a
    tortured phrase is strong only in numbers; an acronym whose initials
    mismatch its expansion is `indeterminate` on its own (non-English
    expansions and LASER-style acronyms mismatch honestly). Duties before you
    report a row: QUOTE the matched span verbatim with surrounding context,
    and check the match is not inside quotation marks, not in the
    references/bibliography (sleuths legitimately cite retracted tortured
    titles), and not in a passage that DISCUSSES tortured phrases, paper
    mills, or AI writing — a paper about the phenomenon quotes its specimens,
    and flagging it accuses the fire brigade of arson. A references-section
    match may be mentioned only as "cites work whose title contains a known
    fingerprint", which is a fact about the cited paper. In the other
    direction, zero hits is not clearance: the dictionary lists KNOWN
    fingerprints with a CS/engineering/biomedical skew, so a silent screen on
    an out-of-field or non-English paper says almost nothing — never describe
    a null as evidence of human authorship. Phrase every conclusion as
    "consistent with undisclosed paraphrasing-tool/LLM use, pending human
    review of the quoted spans" — never "plagiarised", never "AI-generated"
    as fact (rule 9).

15. **A percentage that narrowly misses its column n is usually a denominator
    fact, not an arithmetic fact.** In clinical and epidemiological tables the
    modal innocent cause of a count/percentage mismatch is available-case
    analysis: the percentage was computed over the patients with non-missing
    data for THAT row, and the column header's enrolment n does not show it.
    `check_count_percent` prints `implied_denominator` on every call. Read it
    before grading.

    - If the implied denominator sits BELOW the stated n by an amount ordinary
      missingness explains, the finding is `indeterminate`. The bound the
      deterministic pass uses, and the one to use here so that the two never
      disagree about the same cell, is **three patients OR five per cent of n,
      whichever is the more generous**. Both are needed: an absolute bound alone
      forgives a gap of ten in a sample of fifty, which is a fifth of an arm
      silently missing one variable; a relative bound alone refuses a gap of ONE
      in a sample of seventeen, which is one person and the commonest thing in a
      baseline table. Record the implied denominator and report the
      thing a reader can act on: *the paper does not state the analysis
      denominator for this row*. "Cannot be produced from the printed
      denominator" asserts knowledge of a denominator nobody has.

    - **Implied denominators that DIFFER from row to row are what available-case
      analysis PRODUCES**, because each variable has its own missing patients.
      "No single alternative base explains them" is therefore not an argument
      against the innocent reading — it is that reading's signature. Never use
      it to escalate. MEASURED 2026-08-20 on the eleven-paper run: of 18
      `suspicious` count/percentage verdicts, 15 were reproduced exactly by a
      denominator one to six patients below the one the check was given.

    - Never title a finding with an error mechanism you inferred — "computed
      over the opposite arm's denominator". Report what the number does; the
      mechanism is the authors' to explain.

    - To grade the mismatch `suspicious` you need ONE of: (a) the paper states
      the denominator FOR THAT ROW — a footnote, an in-cell n, an explicit
      completeness statement; the column header alone never suffices; (b) a
      structural contradiction a TOOL computed — the row family's counts sum to
      the stated n while a printed percentage still misses, or two disjoint
      categories of one arm admit no shared denominator in the plausible range
      (`grim_sweep` returns no joint solution); or (c) an implied denominator
      far from any n the paper prints anywhere. Quote the span or the tool
      result that settles it.

    - Two DIFFERENT printed renderings of the same fraction — 20.3% in one
      table and 20.7% in another, for the same 12 of 59 — are a contradiction
      between passages, not a denominator question. This rule does not apply.

    - An `indeterminate` under this rule is still recorded and still reaches the
      report, and a CLUSTER of them in one table is exactly what "warrants
      clarification" is for. It is not the headline.

17. **A finding whose own `notes` explain the value away does not publish
    above severity 1.** If you have written the innocent reading down —
    "statcheck confirms the printed Z converts to this p", "one or two missing
    responses on a smaller base give this percentage", "the cross-check
    agrees" — then you have already decided the value is explained, and the
    severity must follow your reasoning rather than the tool's default.

    MEASURED 2026-08-22: three findings shipped at severity 2 carrying notes
    that fully accounted for the number they flagged. A reader who reaches the
    note learns the flag was withdrawn in the same breath it was made; a reader
    who stops at the headline reaches an accusation. Both readings are the
    report's fault, not the reader's.

    Record it as a `pass` with the explanation, or at 1 when the innocent
    reading is likely rather than established. Keeping the number visible is
    the point — what is not allowed is presenting it as evidence while
    privately conceding it is not.

    (Numbered 17: the roles preamble appended to the parallel prompts already
    holds 16, and two rules sharing a number is what the binding table there
    exists to avoid.)


18. **What a significance mark compares is a premise, not a printed fact.**
    A dagger, star or letter beside a cell says "this differs from
    something". WHICH something — the other arm at the same time point, the
    same arm at baseline, the placebo column — is defined only by the
    paper's legend or Methods. If the paper does not state it, your reading
    of the pairing is ASSUMED, exactly like an assumed bound (rule 4): a
    recomputation built on it is a question for the authors (at most 3),
    never `impossible`, and never the headline. Quote the legend sentence
    that defines the comparison when you rely on it. Also check the TEST
    against the design: a within-group change over time is a paired
    comparison, and recomputing it with an independent-samples t-test
    manufactures a discrepancy the paper never made.

    MEASURED 2026-10-13 (36 eval runs, Claude and Grok): "the †/‡ marks on
    identical means 78.1 vs 78.1 are impossible" was the Level-5 headline in
    six runs, resting each time on an inferred pairing the paper never
    defined; the gold review does not raise it, and a code cap now holds any
    finding whose own tool returned `indeterminate` or `consistent` at 3 or
    below (`severity9.TOOL_VERDICT_CAPS`).
