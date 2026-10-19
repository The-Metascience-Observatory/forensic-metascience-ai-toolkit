# Numeral rules catalogue

> **ARCHIVED 2026-10-16.** Partly implemented (R1 in glyphs.py, R2 `table_cell` in numerals.py); the class names in section 2 differ from `numerals.CLASSES`. The section 1 prior-art survey is the durable part.

What the `unclassified` residue of `numerals.index` actually contains, what prior art
already solved, and which rules are worth their false-positive cost. Written 2026-08-18
to inform `numerals.py`; deliberately NOT code. MEASURED and REASONED are marked
throughout: counts and verbatim quotes are measured; failure-direction arguments are
reasoned.

**Method (MEASURED).** Production wiring replicated exactly (`values.py:896-913`):
`_read_body` -> `_body_items` -> `numerals.index(text, upto=_body_end)` ->
`classify_with(body_items spans)`. Sample: 15 papers -- 8 clinical/neuro from
`cerebrolysin_papers/*/body.md`, 7 psychology from `eval/ground_truth/papers/*.xml` --
chosen to span the two conventions the old enumerator missed. Totals: 4,349 tokens,
2,020 judged (46%), 2,329 unclassified. The split is the headline: psychology papers
judge well (10.1007--s11031-011-9216-y: 496/536 = 93%) because BODY_PATTERNS speaks
APA; clinical papers do not (10.1007--bf02461150: 46/301 = 15%) because their residue
is citations, tables, and PDF damage. Residue was clustered by three priority-ordered
heuristic passes; counts below are non-overlapping.

## 1. Prior art

- **statcheck** (R, GPL-3, pure regex). Extracts only full APA NHST triples (t, F, r,
  chi2, Z, Q + operator + p). Verdict on the operator question: SOLVED THERE -- its
  p regex is `p\s?[<>=]\s?\d?\.\d+`, the operator is split out (`RGX_COMP`), `n.s.` is
  recoded to `p > alpha`, and `error_test.R` branches on every (test_op, p_op) pair, so
  `p < .05` is checked one-sidedly and `p = .03` against a rounding interval. Exactly
  the `p_is_threshold` semantics (`anatomy.py:700`), published. Also ships mangled-minus
  and per-journal PDF-encoding repairs (`b`->`<`, `N`->`>`) -- precedent for §2 R1.
  Transfers: the operator grammar and ns-recode, as translated ideas (GPL: no vendoring).
- **JATSdecoder `get.stats()`** (R, GPL-3). Broadest statistic extractor found: Z, t, F,
  chi2, r, R2, beta, d, eta2, U, H, Q, OR, RR, BF, SE, df -- and EVERY value column has a
  sibling `*_op` column (`p_op`, `t_op`, ...). That output shape -- value + operator as one
  record -- is the right design for the inequality gap. Also normalises Unicode operators
  (`≺`->`<`) and broken exponents. Transfers as design, not code.
- **MeasEval** (SemEval-2021 Task 8; data CC-BY). The one published taxonomy of what a
  number IS in scientific text. Quantity spans carry modifiers: `IsCount, IsApproximate,
  IsRange, IsList, IsMean, IsMedian, IsMeanHasSD, IsMeanHasTolerance, HasTolerance,
  IsRangeHasTolerance`. Binds pairs by design: `1.5-2.6 m` is ONE Quantity with IsRange;
  `1.23±0.25` one with IsMeanHasSD. Gap: inequalities are flattened to open-ended ranges,
  operator not recorded. Transfers: the modifier vocabulary, citable, for §3 group kinds.
- **grobid-quantities** (Java+CRF, Apache-2.0). Measurement objects typed `value |
  interval min-max (quantityLeast/quantityMost) | interval base-range (quantityBase/
  quantityRange) | list`. The cleanest interval model: `1.10-1.45` and `65.2 ± 1.17` are
  DIFFERENT kinds, both one object. Transfers: the schema; not the Java/ML service.
- **quantulum3** (Python, MIT). Units + `±` uncertainty bound into one Quantity, but a
  range comes back as TWO quantities -- reproduces our bug. Its ± regex is liftable (MIT).
- **papercheck/metacheck** (R, AGPL). `stats()` wraps statcheck; `extract_p_values()` has
  a good Unicode operator class `[=<>~≈≠≤≥...]` returned as a field.
- **Numeracy NLP / claim corpora** (NumGLUE, Wallace et al., EBM-NLP, SciFact): magnitude
  reasoning or claim-level labels; no token-role taxonomy. Does not transfer.

**Blunt summary: no tool does the whole job; three pieces compose.** statcheck/
JATSdecoder solve operator-vs-reported; grobid-quantities + MeasEval solve pair binding,
as schema; nothing solves citation/table/mojibake disposal -- that part is ours alone,
and it is most of the clinical residue.

## 2. Proposed vocabulary

Token classes (extending `CLASSES`): `statistic`, `measurement` (unit-bearing procedure/
instrument quantity), `citation_ref` (numeric reference citation), `citation_year`,
`ordinal`, `scale_anchor`, `table_cell` (routed to the table pass, not disposed),
`document_meta` (identifiers, versions, dates, addresses), `unclassified`.

Token attribute: `op` in `{'=', '<', '>', '<=', '>=', '~'}` (default `'='`), following
JATSdecoder's `*_op` design. A reported value is `=`; a threshold or bound keeps its
operator so `p < .05` can never silently become `p = .05`. `n.s.` recodes to `op='>'`
against alpha (statcheck's rule).

Group kinds for bound pairs (grobid/MeasEval vocabulary, joining the register design's
`group.kind`): `interval_min_max` (`1.10-1.45`, `0.53 to 0.85`), `base_range`
(`65.2 ± 1.17`), `point_with_interval` (`2 (1-4)`), `count_denominator` (`12/30`),
`list` (`0.450/0.446`, `62.8 and 66.3%`). Binding is co-membership, never deletion:
both tokens stay in the index; the group states they are one printed quantity.

## 3. Rules, each with its false positive

**R1. Encoding repair layer (before classification).** MEASURED: `&lt;`/`&gt;` entities
appear on 2,070 lines in 228/305 corpus papers; 60 residue rows in-sample are p-values
BODY_PATTERNS cannot see -- `significant (p &lt; 0.05)`, `stoke (p &lt; 0.015;
Mantel-Haenszel test)`. Font-mojibake family (same class as the existing `¼`->`=`
repair): `=` as `5` (`placebo (n 5 121)`, `P 5 .0002`; 15 rows), `±` as `6` or `/C6`
(`75.2 6 14.8`, `65 /C6 1.17`; 14 rows), minus as `2` (`95% CI, 2 30.284 to 2 0.340
seconds`; 2 rows), `%` as `°/o`, `<` as `,` (`p values of , .0001`), `>=` as `$`
(`improvement of $ 4 points`). Resolves ~93 sample rows and converts them into
CLASSIFIABLE statistics -- the only rule here that grows the checkable set.
FALSE POSITIVE: `6` between numbers in a run (`| 4 - 5 | 12 | 11 |` -- a genuine 6 in
`5 6 7` would become ±). Guard as `¼` is guarded: contextual (digit-space-6-space-digit
plus a `mean 6 SD` label or `n 5` shape in the same paper), length-preserving, and
per-paper -- font damage is paper-local (pm-as-6: 3/305 papers). Repairing `,` as `<`
globally would be reckless; only after `p`/`P` and before a decimal.

**R2. `table_cell` routing.** MEASURED: >=135 residue rows sit inside markdown table
lines serialized into body text -- `| 67.6 6 8.0 | 67.3 6 8.0 |`, `| 37 (47.4) | 37
(54.4) |` -- all clinical. Cue: pipe characters flanking the token's line.
`prepass.paper_tables`/`celltypes` already parse these; in the prose index they are
double-counted noise. FALSE POSITIVE: a prose sentence containing `|` (rare; docling
emits pipes only for tables). Cost is low because this is re-routing, not disposal --
the token stays, classed `table_cell`, and the table pass owns it. The real risk is a
table row the table parser ALSO missed, which this class at least makes countable.

**R3. `citation_ref`, square-bracket form only.** MEASURED: 355 residue rows; corpus:
3,375 bracket-citation lines in 148/305 papers -- the single largest non-statistic
class. Cue: `[` + integers/commas/ranges only + `]` -- `[13, 16, 21, 60]`, `[3, 4, 8,
14-16, 42]`; plus the post-period superscript remnant `pathology. 1,2 Vascular` (13
rows; integers glued after sentence-final period, next word capitalised).
FALSE POSITIVE, measured in-sample: `[0.80 (2, 2), P &gt;0.45]` -- a bracketed TEST
STATISTIC whose df `(2, 2)` are integer lists. Guard: reject if the bracket contains
a decimal, `%`, `=`, `<`, `p`, or an inner paren. The superscript form's FP: a real
count opening a sentence (`... were enrolled. 12 patients withdrew`) -- require the
comma-list or a citation elsewhere with the same number? No: cap at accepting only
when the integers are <=3 digits AND the sentence before ends in a noun -- still
leaky, so the superscript sub-rule ships only if its in-sample FP rate is measured 0.

**R4. Named equality -> `statistic`.** MEASURED: 114 + 17 + a large share of the final
residue: `n = 202`, `N = 34`, `M high = 2,002 ms, SD = 339`, `partial η² = 0.048`,
`ηp² = .16`, `MWcombined = 0.69`, `Mfemales = 6.22, SDfemales = 0.75` (subscripts fuse
into the symbol in extraction). Cue: statistical symbol (n/N/M/SD/SE/Mdn/OR/RR/HR/MW/
d/g/β/η²/χ²/α/κ/ICC/AUC/R²/BF, with optional glued suffix) + `[=:]` + the token.
BODY_PATTERNS has no bare `n =` or `η² =` shape, so the paper's sample sizes -- GRIM's
denominator -- currently sit unclassified. Safe direction: a positive classification
ADDS a checkable row; it removes nothing. FALSE POSITIVE, measured: `block size = 4`
(design parameter) and `resolution of 1,024 by 768` -- design settings enrolled as
statistics become undischargeable register noise (the §2-of-`completeness` failure),
not accusations. Bound the symbol list; never match bare words (`size`, `level`).

**R5. Ordinal extensions.** MEASURED: 78 rows. `_ORDINAL` lacks plurals -- in
`Experiments 1 and 2` the `1` is residue while the `2` is caught by `_COORDINATED`
(singular `experiment\s*$` fails on `Experiments`); `study days 1, 3, 7, 14, 21`,
`items 5 and 6`. Missing words: `time` (`at Time 1 and Time 2`, 35 psych rows),
`hypothesis` (`consistent with Hypothesis 2`), `session`, `block`, `trial`, `arm`,
`grade`, `stage`. Markdown heading numbers: `## 3.2. The effect of` (21 rows; cue
`#{1,6}\s*$` before). FALSE POSITIVE: `level` must NOT join the list -- measured:
`a -level of 0.025` is a mangled alpha (α-level), and `trial` risks `trial 24 weeks`
readings; each added word must be checked against the sample before shipping. An
ordinal disposal is real disposal -- a wrongly-ordinaled statistic leaves the index.

**R6. Operator recording (`op`).** MEASURED: 54 rows carry an explicit comparator or
word-form bound: `Fs < 1`, `MW &lt; 10 kDa`, `NIHSS scale of more than 2 points`,
`at least 24 weeks`, `KMO > 0.70 threshold`. After R1, entity forms join them. The
class records the operator; it does not decide threshold-vs-measurement -- that is the
(existing) anatomy's `p_is_threshold` call, now fed honestly. REASONED failure mode,
both directions: recording `p < .05` as `=` makes statcheck test an exact value the
author never claimed -- a manufactured inconsistency against an honest paper; recording
`p = .011` as `<` waives the strongest check statcheck has. The operator must be copied
from the characters, never inferred from convention.

**R7. Pair binding as groups.** MEASURED: 270 range rows + 21 slash + 5 IQR/CI-word +
`to`-form CIs (`95% CI 0.50 to 0.81, derived SMD 0.57` -- the parenthesised
`estimate_ci_prose` shape misses the `to` form entirely) + `3 (0 - 6)` median(range)
cells. Binding cues, in confidence order: `±` (base_range); `x (a-b)` after a label
(point_with_interval); `a-b` with both sides numeric and an interval word nearby
(CI/IQR/range/to/between); `n/N` with n<=N (count_denominator). FALSE POSITIVES, all
measured in-sample: `CA 92093-0624` (ZIP), `International 10–20 EEG System` (proper
name), `0.8-0.5% carbon monoxide` (descending -- two settings, not a range),
`2-3 days` (duration), `[14-16]` (page/citation ranges -- R3 must run first), and the
slash trap: `Week 16 (0.677/0.671)` is two ARMS' values -- reading it as 677 of 671
"events" is an impossible fraction that `_is_result` would then accuse. Guard: a
count_denominator group requires n<=N (the existing `completeness` rule) AND an
integer pair; a bound group never deletes its members, so the worst FP is a wrong
edge, not a vanished number. `12/30` vs `05/06/2004`: three slash-joined integers or
a month name kill the fraction reading.

**R8. `measurement` (unit-bearing).** MEASURED: ~226 rows: `10 μl of 1 M
2-vinylpyridine`, `4% paraformaldehyde`, `1:250, Santa Cruz` (dilutions), `37°C`,
`60 Hz`, `50 mL Cerebrolysin`, `1,024 by 768`. ARGUED: these are instrument settings
and procedure parameters -- GRIM/SPRITE/statcheck consume none of them, and enrolling
them repeats the `_REAGENT_AFTER` lesson. But they stay indexed as `measurement`, not
dropped: a dose inconsistency (50 mL here, 30 mL there) is a real forensic signal a
later check may want. FALSE POSITIVE, measured: `points` cannot join the unit list --
`LS mean difference, 6.325 points; 95% CI, 4.185-8.463 points` is the paper's PRIMARY
OUTCOME wearing a unit noun. Same for `%` (already `statistic`), `ms` in RT means
(`M high = 2,002 ms` -- R4 must outrank R8), and `21 consecutive days` when it is a
reported adherence result. Unit nouns that are also outcome scales make this the rule
with the worst removal risk after R10.

**R9. Compound and nomenclature numbers.** MEASURED: 65 rows: `8-digit number`,
`90-day outcome`, `5-HT`, `2-vinylpyridine`, `50-W lamps`, `10-min rinse`. Cue: token
+ hyphen + letter (the mirror of the existing `_WORD_HYPHEN`, which only guards
LETTER-hyphen-token). FALSE POSITIVE, reasoned: `2-sided`/`one-tailed` carry test
sidedness a statcheck consumer needs; and in `improved by 12-38%` the `12` is a range
bound whose hyphen is followed by a digit, not a letter -- the letter requirement is
load-bearing. Low risk otherwise: a compound's number genuinely measures nothing.

**R10. The rules NOT to implement.** (a) Parenthesised single-integer citations
`(1,9)`, `(5,12,16)`: measured collision -- in psychology `(3) How similar are you`
is an item enumerator, in tables `1 (0)` is n(%), and `(n = 3, 3)` is a sample size;
Vancouver `(1)` is indistinguishable from all three by shape. A false `citation_ref`
here deletes a real count from the index -- the number nobody will ever check. Ship
only the square-bracket form. (b) `score/value/level of X -> statistic`: measured FP
in the first 45-row sample -- `a -level of 0.025` (a threshold), `NIH Image 1.43`
(a version). Both non-implementations cost only `unclassified` rows, which the model
pass still sees; the honest state is the cheap one.

## 4. Ranked order (residue resolved per unit of risk)

1. **R1 encoding repair** -- ~93 rows + unblocks p-values in 75% of corpus papers;
   deterministic for entities; font repairs paper-local, `¼`-precedented. Risk ~0.
2. **R2 table routing** -- 135+ rows; re-routing, not disposal. Risk ~0.
3. **R4 named equality** -- ~150+ rows; positive-only, adds GRIM's `n`. Risk: register
   noise, never removal.
4. **R3 bracket citations** -- 355 rows; one measured FP shape, cheaply guarded.
5. **R5 ordinal plurals/time/headings** -- 78 rows; small, testable word list.
6. **R6 operator field** -- 54 rows + everything R1 frees; semantic prerequisite for
   honest statcheck routing; the cost is schema, not misclassification.
7. **R7 pair binding** -- 270+ rows; groups add structure without deleting tokens, but
   the edge-error catalogue (ZIP, 10-20, descending, slash-arms) is real: bind only
   with an interval cue word or `±`.
8. **R9 compounds** -- 65 rows; keep the letter-after-hyphen requirement.
9. **R8 measurements** -- ~226 rows but the `points`/`ms` collisions put real primary
   outcomes at risk; ship last, with outcome-scale nouns excluded, or leave to the
   model pass.

Residue after all of the above, extrapolated from the final unclustered remainder
(~584 rows, of which roughly half are R1-R8 shapes my heuristics under-matched): the
irreducible core is unmarked prose statistics (`baseline scores of 14.1`, `4.75 vs.
4.11`, `62.8 and 66.3% of the variance`, `13 out of 14 scales` -- note `out of` is
missing from `n_of_total`) plus OCR rubble from pre-1995 scans. That core is the model
classifier's job, which is the design's original position: cheap rules dispose only of
what is demonstrably not a statistic; everything else stays visible.
