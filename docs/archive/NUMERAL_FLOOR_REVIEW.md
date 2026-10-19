# Adversarial review: the numeral floor (`numerals.py`)

> **ARCHIVED 2026-10-16.** Every HIGH defect below was fixed in `numerals.py` (the reasons are in its docstrings); line references have drifted.

Reviewed 2026-08-18 on branch `unify-2026-08-12` (HEAD 4974608). Targets: `src/metascience_agent/numerals.py`,
`tests/test_numerals.py`, the wiring in `values.build_from_paper` and `bundle.py numeralBlock`.
CONFIRMED = reproduced by running code. SUSPECTED = reasoned from reading only. All 14 existing tests pass
while every defect below is present -- the suite never asserts the class of a statistic-shaped token.

## CONFIRMED -- HIGH

### H1. Any number followed by `(` is removed as "factorial design notation"
`_FACTORIAL_AFTER = re.compile(r"^\s*[\(（]|...")` -- the first alternative matches a bare open paren, so
`_class_of` stamps EVERY number immediately preceding a parenthesis as `ordinal`:

    N.index("The mean rating was 4.17 (SD = 1.19) overall.")
    # 4.17 -> ordinal | "factorial design notation, not a measurement"

That is the module's own flagship shape (`mean_sd_prose`). And the misfire is a one-way door:
`classify_with` skips any row whose class is not `unclassified`, so `BODY_PATTERNS` matches the full
`4.17 (SD = 1.19)` span and still cannot repair the row. Ran the exact `build_from_paper` flow on
`cerebrolysin_papers/10.1161--strokeaha.115.009416/body.md` (the corpus's stroke RCT):

    10.1±15.9 (0.0, 21.5)  -> 15.9 = ordinal/factorial, though mean_pm_prose matched "10.1±15.9"
    96 of 104 (92.3%)      -> 104  = ordinal/factorial
    MW=0.71 (95% confidence interval ...) -> 0.71 (the trial's primary effect estimate, both mentions)

So the `±` dispersion the commit celebrates rescuing (5,942 occurrences) is lost AGAIN whenever the pair
is followed by a parenthesised median/IQR -- and this time as a POSITIVE misidentification with recorded
evidence, which is worse than the silence it replaced. Scale, 12-paper random corpus sample: 689 tokens
classed factorial, 582 (84%) followed by statistical paren content (`(51.0, 28.0)`, `(92.3%)`, `(95% CI`,
table cells `133 (63.9)`). That paper's tally: 151 "ordinal" vs 61 "statistic", `share_judged` 31.4% with
most judgments wrong. Should: require factorial evidence on BOTH sides (e.g. `x` before, or `digit x` /
`(` + `:`-style factor syntax after), never a bare `(`.

### H2. `_COORDINATED` removes the number after "In Study 1, ..."
The coordinator list includes a bare comma and `[-\d,\s]*` swallows "1, ", so:

    N.index("In Study 1, 45 participants completed the task.")
    # 45 -> ordinal | "a further item in a list of document ordinals"
    N.index("In Experiment 2, 300 undergraduates were recruited.")   # 300 -> ordinal

"In Study 1, N ..." is the standard opening of a psychology results paragraph; the sample size is removed.
(On the eval paper all 10 coordinated firings were genuine `Experiments 1 and 2` -- the misfire needs a
number to follow the comma, which that paper happens never to do.) Should: only accept `,` as coordinator
when another bare integer (not a clause) follows, or require `and/&/through/to` before the final item.

### H3. `_CITATION` fires on a bracket or comma alone
Docstring: "Anchored on the bracket or the author, never on the digits alone." False -- the first
alternative `(?:\[|\(|;|,)\s*$` needs no author:

    "a subgroup (1989 patients) responded"          -> 1989 = citation_year
    "arms of 250, 2013, and 210 patients"           -> 2013 = citation_year
    "2016 households; 1994 responded"               -> 1994 = citation_year

A 4-digit N in 1900-2099 after `(`, `;` or a list comma is silently removed. The test suite's own defence
("1989 is a perfectly good sample size") only covers `N = 1989`. Should: bracket alone is not evidence;
require an author-like token or a digit-only bracket group (`[2004]`, `(1989)` closing immediately).

### H4. `_FACTORIAL`'s `[x×]\s*$` branch fires on any word ending in x
    "approx 30 participants" -> 30 = ordinal/factorial
    "the max 10 points"      -> 10 = ordinal/factorial   (also: index, sex, cortex...)
Should: require the `x` to be a standalone token preceded by a digit (the first alternative already does
this correctly; the second alternative is strictly looser and is the bug).

### H5. "Exhaustive by construction" is false: the tokeniser silently drops real statistics
The guards `(?!\w)` / `(?<![\w.])` make whole classes of numbers INVISIBLE -- the exact failure mode the
module exists to abolish ("a scan for \d cannot be silently incomplete" -- it can, and does):

    "mean RT was 542ms"        -> []      glued number+unit. Corpus: 293 occurrences of glued
    "a dose of 20mg daily"     -> []      multi-char units (24h, 250mg, 30min, 50mL...) in 55 of
    "after 24h"                -> []      305 papers; 692 in 100 papers counting panel refs (3d, 6g)
    "p = 1.2e-4"               -> []      scientific notation: mantissa killed by `e`, exponent killed
    "a rate of 3.5E6 cells"    -> []      by the _WORD_HYPHEN check ("e-" looks like COVID-19)
    "density of 10² cells"     -> []      superscript is \w (0 corpus occurrences; synthetic only)
    "The mean was 4.2.14 patients dropped out." -> []   glued sentence boundary kills BOTH numbers
    "see Section 2.3.1" / "SPSS 25.0.0" / "Fig.2"  -> []  (69 glued Fig./Table refs in 12 papers;
                                          351 dotted triples in 77 papers, mostly DOI fragments where
                                          invisibility is arguably right)

The glued-unit case is the third failure the docstring says there was "no way to know" about: real doses,
durations and volumes, at 42%-of-corpus-like prevalence (55/305 papers), invisible with no residue row.

## CONFIRMED -- MEDIUM

### M1. `tally` miscounts rows missing the `class` key
`by[r.get("class", "unclassified")] = by.get(r.get("class"), 0) + 1` -- the write key defaults to
`"unclassified"` but the read key is `None`, so every key-less row RESETS the count to 1 instead of
incrementing: `tally([{},{},{}])` -> `unclassified: 1`, `share_judged: 0.67` for three rows nobody judged.
Latent (rows from `index()` always carry the key), but it inflates `share_judged` -- the exact direction
the docstring promises is impossible -- the moment any caller round-trips rows through JSON-lossy code.

### M2. `n_total` counts numbers the paper never printed
On the eval paper, 4 of the 536 indexed tokens come from docling table placeholders
(`"— 1 rows x 9 cols; see tables]"`). The viewer heading is "Every number in the prose" and the module
docstring says "every number the paper printed"; pipeline-generated text is inside the denominator.

### M3. `share_judged`'s honesty claim covers abstention, not error
"A classifier that gives up shows a falling ratio" -- true, and `n_total` genuinely cannot shrink
(index is deterministic; `classify_with` only mutates `class`). But a classifier that GUESSES shows a
rising ratio: the `4.17 (SD = 1.19)` case reports `share_judged = 1.0` with the mean misfiled. Given
H1-H4 fire thousands of times on the corpus, the published ratio currently rewards the cheap rules for
being wrong. (Structural point; the metric is fine once the rules are.)

### M4. NBSP / thin-space digit grouping splits one number into two rows
`"N = 12\xa0345"` -> tokens `12`, `345`. `celltypes._DIGIT_GROUP` and `jats` normalise exactly this
elsewhere ("two values are never welded into a third the paper never printed" -- here one value is split
into two the paper never printed). Same input, different arithmetic, depending on which module reads it.

## CONFIRMED -- LOW

- `"F(2,300) = 4.5"` -> token `2,300`: an unspaced df pair is welded into a thousands number
  (0 hits in a 60-paper corpus sample, so synthetic for now).
- `COVID–19` (en dash) and `COVID‑19` (U+2011) leak `19` -- `_WORD_HYPHEN` only knows ASCII `-`.
  Noise direction (a spurious row, nothing removed).
- Docstring "nothing is filtered out here" vs the `_WORD_HYPHEN` `continue` in `index()` -- a documented,
  deliberate filter, but the sentence is literally false.
- `1st` / `2nd` are invisible (acceptable as ordinals, but they are numeric tokens the floor drops).

## SUSPECTED (reasoned only, not run)

- `numeralBlock` prints "Every number was judged." whenever `rows` is absent even if
  `by_class.unclassified > 0` (`un` is computed only from `rows`). Unreachable today -- `values.py`
  always ships `rows` -- but the message lies the day anyone slims the register.
- `if(!n||!n.n_total) return ''` hides the block when `n_total` is 0; `tally` cannot produce
  `n_total: 0` with non-empty rows, so this is latent. Similarly, `build_from_paper`'s
  `if numeral_index:` means a readable body with zero tokens produces NO `numerals` key --
  indistinguishable in the viewer from a pre-floor bundle (absence-as-knowledge, the house failure).
- `_ORDINAL`'s `week|day|month|year` removes outcome timepoints phrased as results
  ("median survival was reached at month 18") -- plausible, not found in corpus text reviewed.
- `classify_with` spans use `len(i["raw"])` where `raw` is `.strip()`ped; no BODY_PATTERN appears able
  to match edge whitespace, so the spans should be exact, but this was not exhaustively verified.

## Claims vs code (verified by running)

- **536 tokens on the eval paper**: CONFIRMED exactly (via `build_from_paper` on
  `eval/ground_truth/papers/10.1007--s11031-011-9216-y`).
- **"93% judged", "40 left for the model"**: 92.5% and 40 -- CONFIRMED (93 is a fair round). The commit's
  by-class split (59/17/12/4/7%) matches exactly. Note: "judged" is not "judged correctly" (see H1-H4).
- **"37 pairs" of `M = x, SD = y`**: CONFIRMED exactly (37 `mean_sd_apa` matches, all before `_body_end`).
- **"5,942 ± occurrences, 128 of 305 papers"**: substantively CONFIRMED, exact figure not reproduced.
  The corpus has 309 paper dirs, 305 with `body.md` -- "305" and "128" are exact. The published
  `mean_pm_prose` regex over `body.md` gives 5,917; adding `abstract.md` gives 5,948. Both within 0.5%
  of the claim; the precise 5,942 was presumably a slightly different scope.

## Wiring boundary (attacked, holds)

`build_from_paper` bounds the index at `completeness._body_end(text)`; `_body_items` computes the same
`_body_end(text)` on the same text, and its mojibake `¼`->`=` repair is length-preserving, so the
`classify_with` spans land on identical offsets. Both use `start >= limit` semantics (a token straddling
the boundary is kept by both). A `¼`-encoded `p ¼ 0.038` is correctly promoted to `statistic` through the
repaired-match spans. No disagreement found.

## What else I attacked and could NOT break

Leading-dot decimals (`.52`, `.011`), sentence-final numbers (`1.17.` -- the fixed regression stays
fixed), `12,345` thousands, signed numbers (`-19`, `+1.5`, `-.52`), tight and spaced `±`, en-dash ranges
(`1.08–1.9`: both bounds), `~30`, `≤` prefixes, `45%`, a number at offset 0, a number as the entire
string, dates (`2026-08-18` -> three tokens, all indexed), `1,2,3` lists (three tokens), full-width
digits (indexed, since `\d` is Unicode), `N = 1989` (not a citation year), `n = 45` (not a scale anchor),
`1 = sad` anchors, `COVID-19`/`p22`/`F1` (correctly zero tokens), offset uniqueness and
findall-equivalence of `index()`, `n_total == len(rows)` invariance under `classify_with`, and the
viewer's >40-row truncation and HTML escaping in `numeralBlock`. `_body_end` agreement as above.

## Bottom line

The exhaustiveness HALF of the design mostly holds (H5's glued units and scientific notation are the real
exceptions). The "cheap rules only remove what is demonstrably NOT a statistic" half is false at corpus
scale: on real clinical prose the paren rule alone misfiles hundreds of means, SDs, counts and the odd
primary endpoint per dozen papers as "factorial design notation", each with confident recorded evidence,
each permanently unrecoverable by `classify_with` -- a louder, better-documented version of the silence
the module was built to end.
