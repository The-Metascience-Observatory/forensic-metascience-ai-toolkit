# Validation

How we check that the toolkit gives the right answers, and what those checks
do and do not show.

There are two separate questions:

1. **Do the individual tools compute correctly?** A tool such as GRIM is plain
   arithmetic. We can check it against a trusted independent implementation,
   usually the R package written by the method's authors or by the field.
2. **Does the whole review find real problems without accusing innocent
   papers?** This involves AI agents reading the paper, picking the right
   numbers and choosing the right tool, so it can only be measured on real
   papers whose problems are already known.

A tool can be exactly right while the review still goes wrong: the agent can
feed it a number from the wrong table column, or a mean from a scale whose
bounds the paper never stated. That is why the second kind of check is needed
as well as the first.

## 1. Tools checked against independent references

| Check | Compared against | Result |
|---|---|---|
| GRIM | R `scrutiny::grim`, 400,400 enumerated cases | 326,785 compared, **0 disagreements** |
| SPRITE (is this mean/SD possible at all?) | R `rsprite2`, 153,707 enumerated cases | **0 disagreements** where the test can discriminate; 99.8% agreement overall |
| DEBIT | R `scrutiny` and exact truth, 28,720 enumerated cells | **0 false accusations** (`scrutiny` agrees with exact truth 91.4% of the time) |
| Power analysis | R `pwr` | 7 of 7 cases exact |
| Estimate/CI recovery | R | agreement to 1e-12 |

What the terms mean:

- **GRIM** asks whether a reported mean is possible for whole-number data with
  that sample size. For example, the average of 30 integer answers cannot be
  5.51.
- **SPRITE** asks whether any set of integer answers could produce both the
  reported mean and the reported standard deviation.
- **DEBIT** does the same for yes/no data, where the standard deviation is
  fixed by the proportion.
- **Enumerated cases** means we generated every combination of the values
  papers typically print (sample sizes, means, decimal places) and ran both
  implementations on each one, instead of hand-picking examples.
- **Where the test can discriminate**: when the sample is large relative to the
  number of decimals printed, every mean is reachable and the test cannot fail.
  Our code then declines to judge and says why, where the R package reports
  "consistent". We do not count a decline as a disagreement. All 182 SPRITE
  disagreements are in that weak region, and in every one our code said
  "possible" where `rsprite2` said "impossible", so ours errs on the side of
  not accusing.
- **DEBIT differs from `scrutiny` on purpose.** We test the whole range of
  proportions the printed mean could have been rounded from; `scrutiny` tests
  only exact fractions. Against exact truth, that choice produced no false
  accusations.

The GRIM and SPRITE comparisons are rerun by the scripts in
[benchmarks/r_differential/](../benchmarks/r_differential/README.md) (they need
R with `scrutiny` and `rsprite2`; about a minute each). The normal test suite
does not need R. It checks that the recorded results still match the current
code, and fails if `grim.py`, `sprite.py`, `rounding.py` or `severity.py` changed
since the last comparison.

One pitfall when comparing against R yourself: `rsprite2` reads the number of
decimals from how you type the value, so `mean=4.0` means zero decimals. Set
`m_prec` and `sd_prec` explicitly, or the two engines answer different
questions and appear to disagree.

## 2. The full review on papers with known answers

`metascience eval` runs the whole pipeline on four real papers (apple cider
vinegar, air force, wound healing, cerebrolysin) that have answer keys: lists
of the problems the paper is known to have, each with an expected severity. An
LLM judge then matches the review's findings against the key and reports:

- **recall**: how many known problems the review found, weighted by importance;
- **false positives**: findings against things that are not problems;
- whether the paper-level **verdict** matches the expected one;
- whether each matched finding got a **severity** in the expected range.

```bash
metascience eval --backend claude --model sonnet   # runs the paid pipeline on all 4 fixtures
metascience eval --skip-analysis                   # rescore saved runs; still calls the judge
```

`--skip-analysis` is not free. It reuses an existing analysis but still pays
for the LLM judge. On a fixture with no saved run it refuses, rather than
quietly running the paid pipeline.

The fixtures, papers and saved runs are in
[benchmarks/paper_reviews/](../benchmarks/paper_reviews/README.md). Every
benchmark, including GRIM recall on published papers and the Litvak 100-paper
comparison, is listed in [benchmarks/README.md](../benchmarks/README.md).

## 3. A larger set of fraud cases and controls

`eval/ground_truth/` holds 78 papers for corpus-level scoring:

- 30 **fraud cases**, 28 retracted and 2 with a misconduct finding but not
  retracted, each recording how the fraud was established (an investigation,
  statistical detection, an audit of the raw data, or a confession);
- 48 **controls**, papers with no known problem, to measure how often the
  toolkit raises an alarm on a clean paper.

`eval/ground_truth/manifest.csv` lists each paper with its source, which tools
it can validate, and whether its PDF and full-text XML are available.

## What validation cannot tell you

- **Correct arithmetic is not a correct review.** Most errors we have found
  came from the inputs (a misread table cell, an assumed scale bound, a
  threshold p-value read as exact), not from the tools.
- **Four answer keys are a small sample.** The eval detects regressions; it
  does not establish an accuracy rate for papers in general.
- **An impossible number is not proof of fabrication.** See
  [GRIM_CONTEXT_DEPENDENCY.md](GRIM_CONTEXT_DEPENDENCY.md) for the innocent
  ways a mean can come out impossible.
