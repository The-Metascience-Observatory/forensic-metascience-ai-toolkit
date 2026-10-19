# literature_2026-10

GRIM inconsistencies documented in critiques, journal notices and PubPeer
threads, assembled 2026-10-17 from three literature searches (`sources/*.json`:
Wansink's Cornell lab; Brown, Heathers and Anaya's own cases; PubPeer and
published audits). Every value was copied from a named source with its URL,
and on 2026-10-18 checked against the paper itself.

Tiers, the scorer and how to run it: [../README.md](../README.md).

## What is in it

29 papers, 279 cells.

| Paper status | Papers | Meaning |
|---|---|---|
| `confirmed_error` | 9 | a correction, retraction notice or the authors' own data confirms the printed statistics are wrong |
| `journal_action` | 8 | an expression of concern or retraction cites, or follows a report of, the inconsistencies |
| `published_critique` | 3 | a peer-reviewed critique, no journal action on the statistics |
| `unresolved_concern` | 9 | a blog post or PubPeer comment only |

| Tier | Cells |
|---|---|
| `primary` | 210, in 19 papers |
| `rounding_only` | 26 |
| `inferred_n` | 18 |
| `doubtful_premise` | 12 |
| `excluded` | 13 |

Shaaban et al. 2012 alone contributes 100 of the 210 primary cells, which is
why per-paper recall matters here. One more paper, Banerjee et al. 2012, is
verified at paper level (`paper_verified`) but has no primary cell, because
which of its means fail depends on an unprinted split (see below).

Five papers (Mueller & Dweck 1998, Sığırcı 2016, Guéguen's red-clothing paper,
Dubois et al. 2012, Ali & Peynircioğlu 2006) are documented positives whose
cells are not itemised anywhere we could read. They carry `cells: []` and are
not scored.

Judgements on top of the research records are in `build_labels.py`, each with
its reason: `STATUS` per DOI, `PREMISE` per cell, `VALUE_CHECK` for the cells
the text search missed, and the `n_basis` → `n_source` mapping.

## Papers

All 29 are in
`../agent_for_forensic_metascience_papers/grim_ground_truth/literature_2026-10/`,
fetched 2026-10-18 by `fetchpdf2` (23 through Anna's Archive; `dois.csv`,
`fetch.log`, `fetch.jsonl` and `source_tracking.csv` there). 28 are PDFs with a
text layer; Cureus is full-text XML only. Each matched its label's title. The
20 verified papers are split 10/10 into `verified_dev/` and `verified_holdout/`
(`splits.json`: seed 20261018, the Wansink pizza papers and the Strauer trials each
kept on one side); the other 9 are at the top level. Moved 2026-10-18; the fetch
records' paths were updated to match.

**Value check:** 262 of 279 values were found in their paper's text. The other
17 were read on the extracted lines and recorded in `VALUE_CHECK`:

- 15 are present but garbled by the text layer: the candy-dish paper's font
  maps the plus-minus sign to "7" (`4.9672.55` is 4.96 ± 2.55), and the
  Festinger and Rushton scans' OCR reads 5.18 as `S.18` and 1.50 as `I .50`.
- 2 are not in the paper: Peak-end pizza's Table I has no gender row, so the
  critics' statement that it copies the 2014 paper's table verbatim does not
  hold for those cells. They are `excluded`.

Found in the text is not found at the labelled place: a short value can match
anywhere. The 18 primary cells with two or fewer digits were read at their
labelled row and column (Shaaban, BALANCE, Chinese buffets, Cureus), and
Shaaban's column n are printed in its Table 1 and Results (41/25, 39/23,
22/17, 102/65/167), not only in Brown's spreadsheet. All 194 primary cells are
`value_verified`.

## Manual confirmation (2026-10-18)

The eight papers whose best label rested on an unconfirmed premise were read
for that premise (`build_labels.MANUAL`, each paper's `manual_check`):

| Paper | Outcome |
|---|---|
| Teymourian 2015 | **confirmed**: Results print 50 per group; the values are Table 1's Male % (not Table 2) |
| Wansink candy dish 2006 | **confirmed**: 40 participants, within-subject, repeated-measures MANOVA. At n = 40 the 11 labelled means fail both conventions; of every n from 5 to 40 only n = 23 fits (0 fail both), so the means were almost certainly computed on 23 responses |
| Festinger & Carlsmith 1959 | **confirmed**: an '11-point scale', 20 per condition, so means are multiples of .05 |
| Banerjee 2012 | **confirmed at paper level**: no split of Study 2's N = 74 makes all six means consistent, under either convention |
| Cuddy 2005 | not confirmable: a one-character df typo (t(34) for t(35)) makes all three means consistent |
| Rushton 1992 | not confirmable: rank rows sum to 5.92-6.00, so per-item n varies; also rounding-only |
| El Refaeey 2014, Gibreel 2013 | not confirmable: nothing says ages or durations were recorded in whole years |

## Scores on dev

Primary, value-verified cells of the 10 dev papers (`score.py --split dev`).
The holdout has not been run or inspected.

| When | What ran | Cells reached |
|---|---|---|
| 2026-10-18, 1.79.3 | Sonnet, `tools_only` (model-aimed checks) | 38 of 135 checked, all 38 flagged; Shaaban 7 of 100 (two papers did not run) |
| 2026-10-18, 1.82.0, offline | harness sweep, no declarations | 4 of 160 (the printed `n (%)` cells) |
| 2026-10-18, 1.82.0, offline | harness sweep, declarations written by hand from each table | 121 of 160 fail at the stated n; the other 39 fail at it but pass at an n up to 5% smaller (`explained_by_nonresponse`); 0 failures on values the critics did not list |

| 2026-10-18, 1.84.0, paid, `tools_only` | Sonnet (`forensic_review_tools_only_sonnet_1_84`, $9.53) | 160 of 160 flagged and reported: 118 fail at the stated n, 42 only explained if a few participants skipped the item; 0 failures on values the critics did not list; 75 problem findings (15 harness, 60 tools agent) |
| 2026-10-18, 1.84.0, paid, `tools_only` | Grok 4.6 (`forensic_review_tools_only_grok_1_84`, $9.11) | 156 of 160 flagged by the sweep (117 strict, 39 non-response), 158 reported; misses: AAPM's 2 (no tables declared at all) and Shaaban's 2 "Percent of CS in private practice" cells (row not declared a share, a defensible reading); 0 extra failures; 146 problem findings (14 harness, 132 tools agent) |
| 2026-10-18, 1.89.0, `tools_only` | Gemini 3.8 Flash via Antigravity (`forensic_review_tools_only_flash_1_89`; cost not reported by the backend; median 17 min/paper, 11.6M input tokens) | 160 of 160 flagged and reported: 118 strict, 42 non-response; 0 extra failures; 123 problem findings (16 harness, 107 tools agent) |

The hand-written declarations are an upper bound for what `declare_table` can
reach. The 1.84 runs reached it (Sonnet) or nearly (Grok): the model now
declares the tables, including n's stated only in prose (Shaaban's subgroup
sizes, quoted from the Results), and the harness checks every declared cell.

## Known gaps

- **A verified value is not a verified location** for the longer values: the
  text search confirms the number is printed in the paper, not that it sits at
  the labelled cell. Only the short values were checked by place.
- **Positives only.** A false-positive rate needs negatives; the passing cells
  in the same tables are the obvious first source.
- **Not yet mined:** OSF was down until 2026-10-19 and blocked the GRIM survey's
  article list (osf.io/3fcbr), Brown & Heathers' Guéguen report (osf.io/98nzj),
  the Mueller & Dweck cell list (osf.io/ngwn8), a PCIT GRIM survey and a
  Barbalho critique. Supplementary files not downloaded: De Cassai et al. 2024
  (Can J Anaesth, eAppendix XLSX, 55 nerve-block trials with inconsistent
  means: the largest biomedical source found), a 2026 sinomenine meta-analysis
  (Front Pharmacol, .docx), and the DAMASCENE (BMJ 2014) and Cole et al. (BMJ
  2015) appendices.
- **PubPeer coverage is thin.** Its search sits behind a human check, and
  search engines do not index comment text, so threads were found through
  notices, Europe PMC and OpenAlex full-text search.
- The 71 articles of Brown & Heathers' 2017 survey are anonymised by design;
  only Eskine et al. has since been identified.
