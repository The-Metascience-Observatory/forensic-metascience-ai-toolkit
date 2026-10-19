# FMA on the Litvak planted-error benchmark

**Matcher: scored by the grounded verifier (sonnet, one call per error, verbatim evidence quote required and checked in code).**

100 planted errors over 10 paper(s). Reference run for `+X / -Y`: **FMA claude-opus-5**.

## 1. Leaderboard

Scored by the **grounded verifier on every ranked row**: one call per planted error, shown every finding for that paper, required to quote verbatim the words identifying the defect, with the quote checked in code.

| system | caught | /100 | total flags | +X | −Y | verified |
|---|---:|---:|---:|---:|---:|---:|
| GPT-5.5 (high reasoning) | 63 | 63% | 512 | 28 | 5 | 63 (sonnet) |
| GPT-5.5 (no reasoning) | 62 | 62% | 704 | 27 | 5 | 62 (sonnet) |
| GPT-5.4 (high reasoning) | 55 | 55% | 278 | 21 | 6 | 55 (sonnet) |
| Claude Opus 4.6 (no thinking) | 54 | 54% | 310 | 23 | 9 | 54 (sonnet) |
| GPT-5.4 (no reasoning) | 54 | 54% | 421 | 21 | 7 | 54 (sonnet) |
| Claude Opus 4.6 (high thinking) | 52 | 52% | 293 | 20 | 8 | 52 (sonnet) |
| Claude Opus 4.8 (high thinking) | 49 | 49% | 227 | 14 | 5 | 49 (sonnet) |
| Claude Sonnet 4.6 (no thinking) | 49 | 49% | 356 | 20 | 11 | 49 (sonnet) |
| Refine.ink | 47 | 47% | 305 | 14 | 7 | 47 (sonnet) |
| Claude Sonnet 4.6 (high thinking) | 45 | 45% | 241 | 14 | 9 | 45 (sonnet) |
| Claude Opus 4.8 (no thinking) | 43 | 43% | 279 | 11 | 8 | 43 (sonnet) |
| **FMA (Claude Opus 5)** | 40 | 40% | 206 | 0 | 0 | 40 (sonnet) |
| Gemini 3.1 Pro | 39 | 39% | 203 | 14 | 15 | 39 (sonnet) |
| Gemini 3 Flash | 25 | 25% | 200 | 3 | 18 | 25 (sonnet) |
| Reviewer3 | 24 | 24% | 125 | 4 | 20 | 24 (sonnet) |

Union of Litvak's systems: **89** of 100 — the empirical ceiling.

`total flags` is every issue that system reported across the ten papers, matched or not. It is the column that separates a precise system from a verbose one: on the unmodified papers, where nothing is planted, detections correlate with flag count at r = 0.726. **None of these systems, ours included, has a published precision figure** — the unmatched flags may be real problems in real papers or they may be noise, and only the clean-control run distinguishes them.

## 2. Adjusted leaderboard (Litvak's own correction)

`adjusted = detected on modified − detected on the UNMODIFIED papers`. Nothing is planted in the originals, so every match there is the judge matching something to nothing.

**This reorders the raw table by up to six places**, and the correction is not uniform: across his 14 systems, r(findings emitted, false positives on clean papers) = **0.726**. The judge credits a system roughly in proportion to how much it writes. The raw leaderboard rewards volume.

| system | raw | FP on clean | adjusted | rank shift |
|---|---:|---:|---:|---:|
| GPT-5.5 (high reasoning) | 63 | 24 | 39 | +0 |
| Claude Opus 4.8 (high thinking) | 49 | 16 | 33 | +5 |
| GPT-5.4 (no reasoning) | 54 | 23 | 31 | +2 |
| GPT-5.5 (no reasoning) | 62 | 34 | 28 | -2 |
| Claude Opus 4.6 (no thinking) | 54 | 26 | 28 | -1 |
| Refine.ink | 47 | 19 | 28 | +3 |
| Claude Opus 4.6 (high thinking) | 52 | 26 | 26 | -1 |
| Claude Sonnet 4.6 (high thinking) | 45 | 22 | 23 | +2 |
| Claude Opus 4.8 (no thinking) | 43 | 20 | 23 | +2 |
| Gemini 3.1 Pro | 39 | 17 | 22 | +3 |
| Claude Sonnet 4.6 (no thinking) | 49 | 28 | 21 | -3 |
| Reviewer3 | 24 | 9 | 15 | +3 |
| Gemini 3 Flash | 25 | 16 | 9 | +1 |
| GPT-5.4 (high reasoning) | 55 | — | *not computed* (baseline covers 4 of 10 papers)* | — |
| **FMA (Claude Opus 5)** | 40 | — | *not computed* (no clean-control run)* | — |

*not computed* means the correction cannot be made honestly for that row -- either no clean-control run exists (ours), or its baseline does not cover the same papers. `openai_gpt54_high_reasoning` is the latter: its originals run covers 4 of the 10 papers, so its false-positive count is understated by about 60%, and Litvak excludes it from his own head-to-head for that reason. A blank cell would read as zero false positives; it is not.

## 3. By category

| system | analytic flexibility | attrition missing data | causal inference | construct validity | generalizability | internal consistency | methodological design | reporting completeness | statistical errors | theoretical conceptual | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GPT-5.5 (high reasoning) | 8 | 5 | 6 | 7 | 6 | 4 | 8 | 6 | 6 | 7 | 63 |
| GPT-5.5 (no reasoning) | 7 | 6 | 4 | 7 | 8 | 6 | 7 | 6 | 7 | 4 | 62 |
| GPT-5.4 (high reasoning) | 6 | 6 | 3 | 6 | 6 | 5 | 8 | 6 | 3 | 6 | 55 |
| Claude Opus 4.6 (no thinking) | 5 | 4 | 6 | 4 | 4 | 8 | 7 | 5 | 5 | 6 | 54 |
| GPT-5.4 (no reasoning) | 5 | 3 | 3 | 7 | 5 | 4 | 8 | 6 | 6 | 7 | 54 |
| Claude Opus 4.6 (high thinking) | 5 | 5 | 5 | 7 | 2 | 6 | 7 | 7 | 5 | 3 | 52 |
| Claude Opus 4.8 (high thinking) | 4 | 6 | 2 | 7 | 3 | 6 | 6 | 6 | 5 | 4 | 49 |
| Claude Sonnet 4.6 (no thinking) | 6 | 4 | 3 | 6 | 4 | 4 | 7 | 6 | 4 | 5 | 49 |
| Refine.ink | 4 | 3 | 3 | 5 | 3 | 7 | 7 | 2 | 6 | 7 | 47 |
| Claude Sonnet 4.6 (high thinking) | 6 | 3 | 4 | 7 | 5 | 6 | 5 | 1 | 5 | 3 | 45 |
| Claude Opus 4.8 (no thinking) | 5 | 5 | 2 | 5 | 5 | 6 | 4 | 4 | 3 | 4 | 43 |
| **FMA (Claude Opus 5)** | 4 | 4 | 2 | 6 | 4 | 4 | 5 | 2 | 6 | 3 | 40 |
| Gemini 3.1 Pro | 5 | 4 | 3 | 5 | 4 | 5 | 4 | 3 | 4 | 2 | 39 |
| Gemini 3 Flash | 3 | 3 | 3 | 3 | 2 | 3 | 4 | 1 | 1 | 2 | 25 |
| Reviewer3 | 3 | 3 | 3 | 3 | 2 | 3 | 3 | 1 | 3 | 0 | 24 |

Each category holds 10 planted errors.

## 4. Caught by nobody

| paper | error | category |
|---|---|---|
| 3 | information_constraint_removed | causal inference |
| 5 | adaptation_detail_removed | reporting completeness |
| 5 | centering_removed | construct validity |
| 5 | institutional_diversity_reduced | internal consistency |
| 7 | interference_balance_removed | methodological design |
| 7 | temporal_inference_removed | causal inference |
| 8 | exposure_exclusion_removed | attrition missing data |
| 8 | gpower_option_changed | statistical errors |
| 9 | moderator_roles_swapped | theoretical conceptual |
| 10 | fixation_cutoff_changed | attrition missing data |

## Caveats

1. Litvak's figures are recomputed from his stored per-error results on the papers scored here, not quoted from his published leaderboard.
2. Different input: his systems read the flattened text PDF from `docx_to_pdf.py`; ours read whatever the scored corpus was built from. A layout-preserving conversion favours us on table-bound checks.
3. Leaderboard and category figures use LITVAK'S PROTOCOL on every row: his haiku judge, one call per finding, no evidence requirement. That is how his systems were scored, so it is the only like-for-like comparison.
4. The `verified` column is a separate, stricter measurement of our runs only -- one judgement per error, shown every finding for that paper, required to quote verbatim the words identifying the defect, with the quote checked in code. It is the better estimate of what we caught and is NOT comparable to the other rows.
5. `+X` = errors that system caught and the reference run missed. `-Y` = errors the reference run caught and it missed.
6. Litvak's RAW scores are inflated in proportion to how much a system writes: r(findings, false positives on clean papers) = 0.726 over his 14 systems. His adjusted table is the defensible ranking, and we cannot yet appear on it -- we have no clean-control run.
