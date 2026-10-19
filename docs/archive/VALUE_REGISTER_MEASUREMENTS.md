# Value-register measurements (archive survey, 2026-08-18)

> **ARCHIVED 2026-10-16.** Q1-Q4 measure v1 `findings.json` and `toolcalls.stage{1,2}.json` from the deleted serial pipeline. The register itself is live (see docs/VALUE_REGISTER_DESIGN.md).

Measurement pass over archived runs to discipline the value-register design. No designs proposed here.

## File-set scanned

Bounded walk of `high_value_pdfs_to_run_on/`, `funder_demo_2026-08-10/`, `eval/`, `scratchpad/`
(`.git/` and `cerebrolysin_papers/` excluded; repo root NOT walked -- too slow on this filesystem).

- `findings.json`: 57 on disk, **35 unique by content hash** (22 are byte-identical bundle/scratchpad
  copies of another file, e.g. `*_bundle/analysis/findings.json`). All numbers below use the 35 unique files.
- Tool-call log: there is **no `calls.json`**. The log is `toolcalls.stage1.json` / `toolcalls.stage2.json`
  per run dir: 114 on disk, **70 unique by content hash = 35 distinct run dirs** (bundles again).
- Unique file lists cached at the session scratchpad (`uniq_findings.txt`, `toolcall_files.txt`).

## Q1. Duplicate checks within a findings.json

Denominator: **745 findings carrying both `technique` and a dict-valued `inputs`**, out of 777 total
findings across the 35 unique files (95.9% have both; the 32 without are mostly the newest schema,
which replaced `inputs` with `reported`/`computed` -- e.g. `forensic_review_sonnet5_2026-08-18` has 13/13 missing `inputs`).

- Exact duplicates (same `technique` AND byte-identical canonicalised `inputs`, same file):
  **37 findings sit in a duplicate group (5.0% of 745)**; counted as redundant copies
  (group size minus 1) it is **25 findings (3.4%)**.
- 5 worst runs by redundant-copy count (extra / involved / findings-with-both):
  - 9 / 10 / 25 `high_value_pdfs_to_run_on/10.1002--eat.24415/forensic_review_2026-08-13_supp`
  - 4 / 6 / 18 `eval/ground_truth/papers/10.3349--ymj.2009.50.1.55/forensic_review_specificity`
  - 3 / 4 / 17 `high_value_pdfs_to_run_on/10.1073--pnas.0801268105/forensic_review_2026-08-16`
  - 2 / 3 / 27 `funder_demo_2026-08-10/reviews/fraud_blinded`
  - 2 / 4 / 12 `high_value_pdfs_to_run_on/10.1001--jamanetworkopen.2023.37679/forensic_review_2026-08-13`
- Near-duplicates (same `technique`, identical multiset of numeric leaf values in `inputs`, but at
  least two DISTINCT inputs dicts -- i.e. differing only in non-numeric content): **14 findings**
  (1.9% of 745). Examples: two `recalc_chi_squared` findings on the same numbers in
  `eval/.../10.3349--ymj.2009.50.1.55/forensic_review_regexfix_2026-08-18`.

## Q2. Call-path split: check_table vs direct per-cell checks

Denominator: **2,043 logged tool calls** across the 70 unique `toolcalls.stage{1,2}.json` files
(35 runs; all logged calls counted, including ones flagged `validated: false`).

- `check_table`: **39 calls** (all in stage 1; 21 of 35 runs used it at least once).
- Direct per-cell checks (grim_check 32, grimmer_check 62, sprite_reconstruct 14, grim_percentage 44,
  check_count_percent 18, check_estimate_ci 333, debit_check 14, check_sd_or_se 23): **540 calls**
  (436 stage 1, 104 stage 2; 32 of 35 runs used at least one).
- Ratio: **check_table : per-cell = 39 : 540 = 1 : 13.8**. Caveat: `check_estimate_ci` alone is 333 of
  the 540; excluding it the ratio is 39 : 207 = 1 : 5.3.

## Q3. Mean and SD split across findings (same file, same `location`)

Denominator: **53 findings whose `inputs` contain a key literally named `mean`** (across the 35 unique files).

- 34 of 53 also carry `sd` in the SAME finding (linked).
- 19 of 53 carry `mean` with no `sd` in the same finding.
- Of those 19, **5 findings have an `sd` in a DIFFERENT finding of the same file with the identical
  `location` string** (9 mean-sd cross-finding pairings in total). Example:
  `eval/.../10.3349--ymj.2009.50.1.55/forensic_review_2026-08-16_newprompts`, location "Table 1, Age row (both groups)".
- Paired-key variants never split: `mean1` co-occurs with `sd1` in 29/29 findings, `means` with `sds` in 13/13.
- This is a floor: it only catches splits where the two findings typed the `location` string
  identically. Near-identical locations ("Table 1, Age row" vs "Results, para 1 / Table 1, Age row") are not counted.

## Q4. Value reuse across techniques (5 largest runs)

Unit: distinct numeric leaf values in `inputs` per file; a value is credited to every distinct
`technique` whose findings contain it. Distribution = values appearing in 1 / 2 / 3+ distinct techniques.

| run (findings with technique+inputs) | distinct values | 1 tech | 2 | 3+ |
|---|---|---|---|---|
| 10.1002--ajcp.70049/forensic_review_current (36) | 81 | 66 | 12 | 3 |
| 10.1002--ajcp.70049/forensic_review_newschema (36) | 76 | 55 | 14 | 7 |
| 10.1371--journal.pone.0069841/forensic_review_2026-08-13 (33) | 61 | 47 | 10 | 4 |
| funder_demo_2026-08-10/reviews/control_blinded (28) | 40 | 21 | 10 | 9 |
| funder_demo_2026-08-10/reviews/fraud_blinded (27) | 36 | 27 | 6 | 3 |

Pooled over these 5 runs: 294 distinct values, 216 (73%) in one technique, 52 (18%) in two, 26 (9%) in 3+.
Caveat: some multi-technique values are structural small integers (n, df, group sizes: 64, 9, 10, 12, 15),
not substantive statistics; excluding only `decimals*` keys barely changes the distribution (e.g.
control_blinded goes 21/11/8). Real data values do recur across techniques too (e.g. 71.1 and 44.1 in 5
techniques each in control_blinded; 32.81 / 35.94 / 14.06 in 2 in ajcp_current).

## What I could not measure

- No `calls.json` exists anywhere in the scanned tree; I searched for `calls*.json` and found only
  `toolcalls.stage1/2.json`, which I used instead.
- The 32 newest-schema findings (no `inputs` dict, values under `reported`/`computed`) are excluded from
  Q1/Q3/Q4 denominators; their duplicate/reuse behaviour is unmeasured.
- Q3 measures key names, not semantics: means stored under other keys (`treatment_arm_mean`,
  `control_mean_as_printed`, values inside `rows`/`cells` lists) are invisible to it, and location-string
  paraphrases are not matched. The 5/19 figure is therefore a lower bound.
- Whether a cross-finding mean/sd pair is truly "the same statistic" was not verified against the papers.
- Runs archived outside the four scanned directories (e.g. `cerebrolysin_run_2026-08-09/`,
  `run_logs/`, `examples/`) were not scanned, per the performance constraint.

## The register on the Zotero corpus, with both rails working (2026-08-19)

Every earlier register number on this corpus was taken against a blank prose
half -- `_read_body` returned 0 characters for all 217 papers because
`_article_pdf` required a DECLARED article and these directories hold a bare
`paper.pdf`. With that fixed, and the proven-glyph repair applied to cells,
this is the first honest measurement of the register on a heterogeneous corpus.

58 papers, 5,049 groups, 5,899 values, 40 design values.

    descriptive     2878   48.8%
    unknown         1932   32.8%
    inferential     1026   17.4%
    design            63    1.1%

    by rail:   table 3,591 (61%)     prose 2,308 (39%)

Numerals, 34,916 of them:

    unclassified   17214   49.3%
    table_cell     12646   36.2%
    statistic       2093    6.0%
    citation_year   1790    5.1%
    ordinal         1173    3.4%
    share_judged   0.5070

Read against the earlier cerebrolysin figures (46.0% unknown, 37.4%
descriptive, 16.5% inferential, 0.0% design), every class moved the right way:
unknown falls 13 points, descriptive rises 11, and `design` is no longer
structurally zero now that header-borne `n` is indexed as a value.

TWO THINGS THIS DOES NOT SAY. `share_judged` of 0.51 is not a coverage figure --
half of every paper's numerals are still unjudged, which is exactly the residue
`classification_batch` exists to hand to the model, and nothing in the pipeline
calls it yet. And 32.8% of values reading `unknown` is the anatomy's absence
measured again: these runs declare no variables, so an ambiguous cell stays
ambiguous by design.

## Glyph damage: what the whole sweep bought (2026-08-19)

One PDF can reach us as two different corruptions of the same character,
because two extractors spell a broken `ToUnicode` CMap differently. On
`10.1007--s00702-004-0248-2`, pdf2mdjson's `body.md` reads `65 /C6 1.17` (the
PostScript glyph NAME) and docling's cells read `65 \x06 1.17` (the raw glyph
INDEX). Both are `65 ± 1.17`.

Decoded across the corpora, by evidence rather than by guess:

    /C6  ±        /C14  °       /C12  beta      /C19  accent
    /C0  MINUS    /C213 '       /C1   middot    /C15  bullet

### What was being read WRONG, not merely missed

Three live corruptions, all of the class this repository calls the worst
possible output -- a confident finding computed on a number the paper never
printed:

  - `P < 0\x0605` -> `p_value` with raw `P < 0`. A printed p < 0.05 reaching a
    check as a p of ZERO, which is impossible. 12 in one paper.
  - `the effect was /C0 0.85 (95% CI /C0 1.2, /C0 0.3)` -> `estimate_ci_prose`
    of **0.85**. A printed -0.85 with CI [-1.2, -0.3] reaching a check as
    POSITIVE, with a confidence interval attached.
  - `\x00 3.5 \x06 7.6` in EPIVI7B3's tables -> 21 means with the WRONG SIGN.

### What is repaired, and the rule

REPAIRED ONLY WHERE THE DOCUMENT PROVES IT, and the proof must be textual: the
glyph standing between two WORDS (`mean \x06 SD`, `Values shown mean /C6 SEM`)
where no digit is at stake and only `±` reads, AND no literal `±` anywhere in
that document. Both, or nothing.

    prose, cerebrolysin   mean_pm_prose  725 -> 863   (+138, 4 papers proven)
    cells, EPIVI7B3       coverage     0.440 -> 0.698 (158 cells repaired)
                          mean_sd          0 -> 124
    prose total, corpus                17,116 -> 17,248

REFUSED WHERE IT IS NOT PROVEN, which is most of it: 8 of the 12 `/Cn` papers
have no anchor, YLHWMEJ3's 50 `\x06` are very probably `±` with nothing to prove
it, and `/C0` has no textual anchor for a minus at all. Those numbers are
quarantined and reported, never guessed. Being nearly sure is still a guess
about a digit.

### Two of my own guards were wrong first

- The control-character pattern looked only BETWEEN digits, so it missed every
  lost sign -- which is the more dangerous half.
- The glyph-name guard then searched seven characters back and over-refused: a
  legend reading `/C3 ¼ p < 0.05` is `* = p < 0.05`, where `/C3` is the ASTERISK
  and the p-value is intact. It threw away four undamaged p-values before being
  anchored so the glyph must END where the number begins.

Final cost, corpus-wide: 6 items refused, all the SD half of a damaged pair in a
paper with no proof.

## All four signals verified together on one real bundle (2026-08-19)

Each of these was verified in isolation as it was built, which is not the same
as verifying they coexist. Built on `10.1007--s00702-004-0248-2` with a real
anatomy, a real glyph scan and a real floor, then rendered by calling the
viewer's own functions under node -- the banner and blocks are assembled in the
browser, so grepping the HTML proves nothing.

    value_register            64 groups, 1 design value, 319 numerals indexed
    classification            ready, 141 residue items handed over
    statistics_register       1 row, 0 VERIFIED, floor: 40 unmatched of 40
    text_integrity            quarantined: glyph name leak, glyph name in a number

Rendered output, confirmed:

  - "The model's own register" -- counts, `by source`, `Read from: extractor =
    pdf2mdjson`, and the headline "40 of 40 statistics the regex enumerator
    found are NOT in the model's register".
  - "Group sizes the tables printed" -- the design value, hoverable.
  - The limits banner -- "This paper's extracted text is character-corrupt in a
    way that affects DIGITS", in `L`, the list that bears on the findings.

THE FLOOR COMPARISON IS THE LINE THAT MATTERS and it is the one I had broken:
the first cut read `fl.n_missed`, which `floor_check` does not return, so the
single most important number in the block rendered as nothing at all. It was
invisible to code review and to the tests, and only appeared when the function
was actually executed.
