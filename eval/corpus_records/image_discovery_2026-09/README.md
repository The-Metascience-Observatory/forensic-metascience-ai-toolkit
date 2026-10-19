# image_discovery_2026-09 — record of what was run

This record was written on 2026-09-28, just before Dan deleted the corpus folder
`/media/dan/data/metascience_observatory_image_analysis_papers/image_discovery_2026-09`
(23 GB) to free disk space. It captures which papers were analysed, with which
code, and what was found. All values are read from the corpus's own records;
nothing was re-run.

## Files here (in git)

| File | Contents |
|---|---|
| `summary.json` | Totals: 1,105 paper folders, 998 with a main PDF, 3,083 sweep rows, 2,151 sealed runs, 3,017 findings, 47 review events |
| `papers.tsv` | One row per paper. Metadata: DOI, year, journal, first author, title, main-PDF SHA-256, number of PDFs. Last sweep: sweep id, outcome or refusal reason, detector release, **detector fingerprint**, flags, completion time, evidence and context group counts. Newest run: id, version, code fingerprint, git sha, item count, screening policy. |
| `sweep_history.jsonl.gz` | Every sweep attempt, one JSON line per paper per attempt (all 3,083), each with its full stamp: detector release + fingerprint + fingerprinted files, flags, inputs digest, outcome, tiers, timing |
| `runs.jsonl.gz` | Every sealed analysis run (2,151). Run level: provenance (version, code fingerprint, git sha, dirty flag, screening policy and model routing), timestamps and status. Per item: id, kind, detector kind, figure labels, sentence and panels. Also the AI screening attempts. |
| `review_events.json` | The 47 local human review events: 31 false positive (other), 8 true issue, 6 false positive (same condition), 1 unsure, 1 other |
| `raw_archive_index.json` | Paths, SHA-256 and sizes of the raw archives below |

## Raw archives (Dropbox, outside git)

`/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/corpus_records_raw/image_discovery_2026-09/`, 19 MB:

- `discovery.tar.gz`: how the corpus was selected (`seeds`, `authors`, `works`, `decisions`)
- `pubpeer_cache.tar.gz`
- `sweeps.tar.gz`: sweep manifests, `sweep.json`, adjudication logs
- `analysis_runs_manifests.tar.gz`: the full sealed run manifests
- `analysis_runs_executions.tar.gz`
- `analysis_runs__index.json`, `fetchpdf_resolution.json`, `image_track__furniture.json`

## Code versions, as recorded

- **Detection sweep:** every paper's latest sweep ran detector release **1.28.0**,
  fingerprint `ec648ced3c6b…` (full hash in `papers.tsv`), sweep
  `discovery_2026-09_full`, completed 2026-09-05/06, with
  `segment_montages`, `include_supplements`, `max_panels=200`, `rendered_regions`
  and `copy_move` on. Outcomes: 1,010 ran, 92 refused, 1 crashed, 2 timed out.
- **Archived runs:**
  - 1,125 carry version 1.28.0 but no code fingerprint.
  - 1,015 carry no version.
  - Both groups were imported from pre-archive results, so their code is known
    only through the sweep stamps above.
  - 11 are later re-screens at 1.38.1–1.39.0, fingerprint `b508712c98f1`, git
    `134b22fc15a5`, dirty.
- **What is not recorded:** the source PDFs and figures themselves. Only their
  hashes are kept, in `papers.tsv`. The DOIs are enough to re-fetch.
