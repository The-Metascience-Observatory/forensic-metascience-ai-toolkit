# When an `impossible` GRIM result is fine

> Written 2026-08-10. The reasoning here is current and `tests/test_docs_accuracy.py` pins its quotations against the in-tree book.

GRIM's arithmetic is trivial and its *application* is not. A GRIM failure says
"these three printed numbers cannot all be true together". It does not say which
one is wrong, and it does not say anyone did anything wrong. Most GRIM failures
in ordinary literature have innocent causes, and a toolkit that reports them as
accusations will be wrong far more often than the arithmetic is.

This document exists because the toolkit produced three false `impossible`
verdicts against non-retracted papers in a single day, all from reporting
conventions rather than arithmetic error. Every one would have been caught by
working through the list below before publishing.

**Sourcing.** Quotations are from James Heathers, *An Introduction to Forensic
Metascience* (2025), doi:[10.5281/zenodo.14871843](https://doi.org/10.5281/zenodo.14871843)
(CC-BY 4.0). Locators are line numbers in the Curvenote/MyST source export of
that Zenodo record (v1, 2025-02-14); every quote here was checked against it
while a copy was kept in this repository (removed 2026-10-19).

**What Heathers does and does not cover, stated plainly.** He never catalogues
reasons a GRIM failure might be innocent, and the word "composite" does not
appear in the book at all. What he gives is a worked example of the *reasoning*,
which is more useful than a list would be. Items below are marked **[H]** where
they are his and **[D]** where we derived them. The largest single source of
false GRIM accusations in this toolkit -- the 1/(items·n) denominator -- has no
counterpart in the book.

---

## 1. The doctrine, in his words

After a mean fails GRIM, his first move is not a verdict. It is to ask what else
could have produced the number.

> With a little bit of inference, we can speculate on exactly what went wrong.
> For instance, maybe someone left the question blank, and the denominator isn't
> actually 30? Perhaps there's a single missing value (n=29) or maybe two
> (n=28)?
> — `intro_to_forensic_metascience.md:989-991`

He varies the denominator first, then the data-collection instrument:

> The 'silly answer' scenario is actually an analytical possibility you may have
> to consider -- we have encountered this before in the wild when requesting
> data! But also consider that a silly answer might be straightforwardly
> impossible if, say, the question was answered on a computerized form that made
> you click a radio button corresponding to the digits of 1 to 5. There is no way
> that *could* be anything except an integer.
> — `:1025`

And the limiting case, which defines GRIM's whole domain of validity:

> if you allow the answer to the item in question to be any decimal, *GRIM
> doesn't work at all* as any eventual mean is possible.
> — `:1023`

He closes the passage with the practical consequence:

> (Details like this are one of the many reasons why analysts get annoyed by
> papers that do not clearly specify their methods!)
> — `:1027`

That sentence is the honest statement of the problem. **Most GRIM ambiguity is
not resolvable from the paper**, which is why the correct destination for an
unresolved flag is a question to the authors, not a finding.

On rounding specifically:

> **Note: always check these solutions manually, because R does not round values
> in the traditional manner!** In this case, the solution at n=80 is 0.6375
> exactly, which we would typically round to 0.638.
> — `:1193`

---

## 2. The list: why an `impossible` GRIM result might be fine

For each: the mechanism, how a careful reader could tell, and whether the
toolkit can rule it out automatically.

### Family 1 — the denominator is not the printed N

| # | Mechanism | How to tell | Automatable? |
|---|---|---|---|
| 1 **[H]** | **Item non-response.** A respondent skipped this item, so the mean divides by n−k. | Sweep n−1, n−2 …; a hit at a nearby n is the tell. | **Yes** — report the nearest consistent n rather than a bare fail. |
| 2 **[D]** | **Post-hoc exclusions** — per-protocol vs ITT, outlier removal, complete-case analysis. | CONSORT flow; "per protocol"/"complete case" in methods. | Partly — text-mine exclusions, then sweep. Cannot be ruled out silently. |
| 3 **[D]** | **Conditional or branching administration.** Items shown only to a screened subset. | The instrument's skip logic, usually not in the paper. | Only via sweep. We can say "consistent at some n < N"; we cannot confirm why. |
| 4 **[H]** | **Per-item denominators across a row of percentages**, so no single n fits all of them. | Exactly Heathers' Ballot case: no common n exists. | **Yes** — `grim_sweep`. Note his own conclusion there was "data missing haphazardly", not fabrication. |
| 5 **[D]** | **Trimmed means.** Trimming changes the denominator to the trimmed n. | Methods section. | Guard by text search; optionally re-test at standard trim fractions. |
| 6 **[D]** | **Weighted or cluster designs.** A weighted mean has no 1/n granularity at all. | "Sampling weights", "svy", complex survey language. | **Yes, as a refusal** — if weights are mentioned, GRIM does not apply. |

### Family 2 — the observations are not integers

| # | Mechanism | How to tell | Automatable? |
|---|---|---|---|
| 7 **[H]** | **Non-integer responses** — free-entry fields, half-points, a "silly answer". | Response mode. A radio button cannot be 3.5; a paper form can. | **No.** Record "integer responses" as an explicit defeasible assumption and cap severity when the response mode is unstated. |
| 8 **[D]** | **Finer granularity than assumed** — 0.5 steps, sliders, VAS. | Instrument description. | **Yes** — re-test at candidate granularities and report which rescues it. |
| 9 **[D]** | **Imputation.** Imputed values are not integers. | Methods mention imputation. | **Yes, as a refusal.** |

### Family 3 — the reported quantity is not a plain mean of raw scores

| # | Mechanism | How to tell | Automatable? |
|---|---|---|---|
| 10 **[D]** | **Composite scored as a MEAN of k items.** Granularity is 1/(k·n), not 1/n. | Is the score a mean-of-items or a sum? | Partly — needs the item count. **This is our largest false-accusation source and is not in the book.** |
| 11 **[D]** | **Subscale scored on an item subset by field convention.** | Follow the scale's originating citation. | **Very hard.** Cross-document retrieval; cap at indeterminate when unresolved. |
| 12 **[D]** | **Normed or transformed scores** — T-scores, z-scores, age norms. | Norm tables cited; values outside the raw range. | Partly, via range checks. |
| 13 **[D]** | **Not an arithmetic mean at all** — adjusted/estimated marginal means, geometric means, or a median mislabelled as a mean. | Headers and footnotes: "adjusted", "EMM", "median (IQR)". | Partly — parse headers; ambiguity caps severity. |
| 14 **[D]** | **The underlying variable was never integer** — ages, durations, concentrations displayed rounded. | Variable type. | **Yes, and this is the single most important guard.** Classify the variable *before* testing. |

### Family 4 — the reporting layer, not the data

| # | Mechanism | How to tell | Automatable? |
|---|---|---|---|
| 15 **[H]** | **Rounding convention.** Round-half-up, round-half-even and truncation disagree. | Test all standard rules before declaring failure. | **Fully.** Accept if consistent under any standard convention, and say which was needed. |
| 16 **[H]** | **The authors mis-rounded by one unit in the last place.** | The value sits 1 ULP from a consistent one. | **Yes** — report "consistent within 1 ULP" as a distinct, milder verdict. |
| 17 **[H]** | **A transcription typo.** The datum is fine; a digit in the manuscript is wrong. | The same quantity reported elsewhere in the paper disagrees. | **Yes** — cross-check within the paper. An isolated failure among otherwise-consistent values is "concerning rather than fatal". |

### Family 5 — the failure is ours

| # | Mechanism | How to tell | Automatable? |
|---|---|---|---|
| 18 **[D]** | **We paired the wrong n with the value** — a header N reused for a cell it does not govern, a group n, a post-dropout timepoint n. | Careful table reading. | This is an extraction failure. Flag low-confidence pairings instead of emitting verdicts from them. |
| 19 **[D]** | **We assumed the wrong printed precision.** `decimals` wrong by one inverts the test. | The literal as printed. | **Yes** — read decimals from the literal, never from a float. |

---

## 3. NON-reasons: rescues that are arithmetically wrong

Over-excusing is its own failure. These sound like they should rescue a GRIM
failure and do not:

- **Reverse-scored items.** `x' = (min + max) − x` maps integers to integers.
  The sum stays an integer, the denominator is unchanged. **GRIM is unaffected.**
- **Winsorised means.** Winsorising replaces extremes with an observed order
  statistic, which is itself a data value. Integers in, integers out. **GRIM
  applies at the same n.**
- **Change or difference scores** between two integer measurements. The
  difference of two integers is an integer. **GRIM applies at the same n.**
- **Composite SUM totals.** Each subject's total is an integer, so granularity is
  1/n and ordinary GRIM is correct. Refusing these because they are "composites"
  loses real detections: a PHQ-9 total of 12.27 at n=42 has **zero** solutions at
  1/42 and three at 1/378.

---

## 4. What the toolkit must do before publishing an `impossible`

1. Classify the variable as genuinely integer-granular (item 14).
2. Sweep a plausible n window and report the nearest consistent n (items 1–4).
3. Test every standard rounding convention and the 1-ULP case (items 15–16).
4. Search the methods for weights, imputation, trimming, exclusions and subscale
   structure (items 2, 5, 6, 9, 11).
5. Record which of these could **not** be ruled out, and cap severity accordingly.

Items 7 and 11 can essentially never be ruled out automatically. That is not a
gap to be closed; it is the reason unresolved flags belong in **Questions for the
authors** rather than in the findings list — a route the toolkit already
produces, and the one Heathers himself takes when a paper does not specify its
methods.
