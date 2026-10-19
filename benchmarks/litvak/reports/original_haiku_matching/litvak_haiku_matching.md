# FMA on the Litvak planted-error benchmark

**Matcher: scored by Litvak's protocol (haiku, one call per finding, no evidence required).**

100 planted errors over 10 paper(s). Reference run for `+X / -Y`: **FMA claude-opus-5**.

## 1. Leaderboard

Scored by **Litvak's protocol on every row** -- his haiku judge, one call per finding, no evidence requirement -- because that is how his fourteen systems were measured. Our stricter verified figure is the last column and is **not** comparable to anyone else's number.

| system | caught | /100 | total flags | +X | −Y | verified |
|---|---:|---:|---:|---:|---:|---:|
| GPT-5.5 (high reasoning) | 71 | 71% | 512 | 31 | 9 | 63 (sonnet) |
| GPT-5.5 (no reasoning) | 66 | 66% | 704 | 25 | 8 | 62 (sonnet) |
| Claude Sonnet 4.6 (no thinking) | 60 | 60% | 356 | 22 | 11 | 49 (sonnet) |
| GPT-5.4 (no reasoning) | 60 | 60% | 421 | 20 | 9 | 54 (sonnet) |
| Claude Opus 4.6 (no thinking) | 59 | 59% | 310 | 20 | 10 | 54 (sonnet) |
| Refine.ink | 57 | 57% | 305 | 18 | 10 | 47 (sonnet) |
| GPT-5.4 (high reasoning) | 56 | 56% | 278 | 18 | 11 | 55 (sonnet) |
| Claude Opus 4.6 (high thinking) | 55 | 55% | 293 | 18 | 12 | 52 (sonnet) |
| Claude Opus 4.8 (high thinking) | 52 | 52% | 227 | 11 | 8 | 49 (sonnet) |
| Claude Sonnet 4.6 (high thinking) | 51 | 51% | 241 | 17 | 15 | 45 (sonnet) |
| **FMA (Claude Opus 5)** | 49 | 49% | 206 | 0 | 0 | 40 (sonnet) |
| Claude Opus 4.8 (no thinking) | 47 | 47% | 279 | 9 | 11 | 43 (sonnet) |
| Gemini 3.1 Pro | 42 | 42% | 203 | 11 | 18 | 39 (sonnet) |
| Gemini 3 Flash | 36 | 36% | 200 | 12 | 25 | 25 (sonnet) |
| Reviewer3 | 30 | 30% | 125 | 6 | 25 | 24 (sonnet) |

Union of Litvak's systems: **93** of 100 — the empirical ceiling.

`total flags` is every issue that system reported across the ten papers, matched or not. It is the column that separates a precise system from a verbose one: on the unmodified papers, where nothing is planted, detections correlate with flag count at r = 0.726. **None of these systems, ours included, has a published precision figure** — the unmatched flags may be real problems in real papers or they may be noise, and only the clean-control run distinguishes them.

## 2. Adjusted leaderboard (Litvak's own correction)

`adjusted = detected on modified − detected on the UNMODIFIED papers`. Nothing is planted in the originals, so every match there is the judge matching something to nothing.

**This reorders the raw table by up to six places**, and the correction is not uniform: across his 14 systems, r(findings emitted, false positives on clean papers) = **0.726**. The judge credits a system roughly in proportion to how much it writes. The raw leaderboard rewards volume.

| system | raw | FP on clean | adjusted | rank shift |
|---|---:|---:|---:|---:|
| GPT-5.5 (high reasoning) | 71 | 24 | 47 | +0 |
| Refine.ink | 57 | 19 | 38 | +4 |
| GPT-5.4 (no reasoning) | 60 | 23 | 37 | +1 |
| Claude Opus 4.8 (high thinking) | 52 | 16 | 36 | +5 |
| Claude Opus 4.6 (no thinking) | 59 | 26 | 33 | +0 |
| GPT-5.5 (no reasoning) | 66 | 34 | 32 | -4 |
| Claude Sonnet 4.6 (no thinking) | 60 | 28 | 32 | -4 |
| Claude Opus 4.6 (high thinking) | 55 | 26 | 29 | +0 |
| Claude Sonnet 4.6 (high thinking) | 51 | 22 | 29 | +1 |
| Claude Opus 4.8 (no thinking) | 47 | 20 | 27 | +2 |
| Gemini 3.1 Pro | 42 | 17 | 25 | +2 |
| Reviewer3 | 30 | 9 | 21 | +3 |
| Gemini 3 Flash | 36 | 16 | 20 | +1 |
| GPT-5.4 (high reasoning) | 56 | — | *not computed* (baseline covers 4 of 10 papers)* | — |
| **FMA (Claude Opus 5)** | 49 | — | *not computed* (no clean-control run)* | — |

*not computed* means the correction cannot be made honestly for that row -- either no clean-control run exists (ours), or its baseline does not cover the same papers. `openai_gpt54_high_reasoning` is the latter: its originals run covers 4 of the 10 papers, so its false-positive count is understated by about 60%, and Litvak excludes it from his own head-to-head for that reason. A blank cell would read as zero false positives; it is not.

## 3. By category

| system | analytic flexibility | attrition missing data | causal inference | construct validity | generalizability | internal consistency | methodological design | reporting completeness | statistical errors | theoretical conceptual | total |
|---|---|---|---|---|---|---|---|---|---|---|---|
| GPT-5.5 (high reasoning) | 8 | 7 | 6 | 7 | 7 | 6 | 9 | 7 | 7 | 7 | 71 |
| GPT-5.5 (no reasoning) | 7 | 7 | 4 | 7 | 7 | 8 | 8 | 6 | 7 | 5 | 66 |
| Claude Sonnet 4.6 (no thinking) | 7 | 7 | 4 | 6 | 6 | 4 | 8 | 6 | 5 | 7 | 60 |
| GPT-5.4 (no reasoning) | 5 | 6 | 4 | 6 | 5 | 4 | 8 | 8 | 7 | 7 | 60 |
| Claude Opus 4.6 (no thinking) | 5 | 6 | 5 | 5 | 4 | 9 | 8 | 5 | 6 | 6 | 59 |
| Refine.ink | 7 | 4 | 2 | 6 | 3 | 8 | 9 | 3 | 8 | 7 | 57 |
| GPT-5.4 (high reasoning) | 6 | 5 | 5 | 6 | 6 | 5 | 8 | 5 | 5 | 5 | 56 |
| Claude Opus 4.6 (high thinking) | 5 | 5 | 6 | 7 | 4 | 6 | 7 | 5 | 5 | 5 | 55 |
| Claude Opus 4.8 (high thinking) | 4 | 6 | 3 | 6 | 3 | 8 | 7 | 5 | 6 | 4 | 52 |
| Claude Sonnet 4.6 (high thinking) | 7 | 4 | 3 | 7 | 5 | 7 | 6 | 3 | 5 | 4 | 51 |
| **FMA (Claude Opus 5)** | 4 | 5 | 3 | 6 | 4 | 6 | 6 | 5 | 7 | 3 | 49 |
| Claude Opus 4.8 (no thinking) | 5 | 5 | 2 | 5 | 4 | 7 | 5 | 5 | 5 | 4 | 47 |
| Gemini 3.1 Pro | 4 | 6 | 3 | 6 | 3 | 5 | 4 | 3 | 6 | 2 | 42 |
| Gemini 3 Flash | 2 | 4 | 5 | 4 | 4 | 4 | 3 | 3 | 3 | 4 | 36 |
| Reviewer3 | 3 | 6 | 4 | 3 | 2 | 2 | 3 | 2 | 4 | 1 | 30 |

Each category holds 10 planted errors.

## 4. Caught by nobody

| paper | error | category |
|---|---|---|
| 4 | temporal_logic_altered | causal inference |
| 5 | adaptation_detail_removed | reporting completeness |
| 5 | centering_removed | construct validity |
| 5 | institutional_diversity_reduced | internal consistency |
| 7 | temporal_inference_removed | causal inference |
| 10 | fixation_cutoff_changed | attrition missing data |

## Caveats

1. Litvak's figures are recomputed from his stored per-error results on the papers scored here, not quoted from his published leaderboard.
2. Different input: his systems read the flattened text PDF from `docx_to_pdf.py`; ours read whatever the scored corpus was built from. A layout-preserving conversion favours us on table-bound checks.
3. Leaderboard and category figures use LITVAK'S PROTOCOL on every row: his haiku judge, one call per finding, no evidence requirement. That is how his systems were scored, so it is the only like-for-like comparison.
4. The `verified` column is a separate, stricter measurement of our runs only -- one judgement per error, shown every finding for that paper, required to quote verbatim the words identifying the defect, with the quote checked in code. It is the better estimate of what we caught and is NOT comparable to the other rows.
5. `+X` = errors that system caught and the reference run missed. `-Y` = errors the reference run caught and it missed.
6. Litvak's RAW scores are inflated in proportion to how much a system writes: r(findings, false positives on clean papers) = 0.726 over his 14 systems. His adjusted table is the defensible ranking, and we cannot yet appear on it -- we have no clean-control run.
