# Copy-paste ground truth — manifest (2026-11-06)

Data files live outside git, at
`/media/dan/data/agent_for_forensic_metascience_copy_paste_files/ground_truth/`
(run `findmnt` first; the disk can mount at `data1`). This directory holds
everything needed to rebuild and check them: catalogs with published digests,
the label ledger, the synthetic generator and the checker. A copy of this file
sits at the ground-truth root.

## Layout

```
ground_truth/<tier>/
  incoming/<file_id>/<filename>   bytes as downloaded, kept only on a digest match
  incoming/download_receipt.json  per-file download status
  inputs/<paper_id>/<filename>    imported copy, one folder per dataset version
  import_receipt.json             per-file verified / missing
  manifest.jsonl                  copy-paste-batch input, one line per version
  labels.jsonl                    issue-level labels (labels_draft/ before merge)
  evidence/                       PubPeer thread text + screenshots (science_detective, famous)
```

`paper_id` is `<case_id>-v<dryad version_id>`. Original and corrected versions
of one paper are separate papers in the same `family_id`.

## Tiers

| Tier | Versions | Files | Source | Labels |
|---|---|---|---|---|
| `science_detective` | 34 version jobs, 33 with local bytes | 46 of 47 verified | Dryad, catalog `sciencedetective_catalog.json` | 37 records, from the PubPeer reports |
| `famous` | 4 | 4 | PMC / OSF / Dryad, catalog `famous_catalog.json` | 4 records: Südhof PNAS 2023, Data Colada 98 and 109 (Shu et al. 2012), Pruitt AmNat 2016 |
| `synthetic` | 22 | 23 | `make_synthetic.py` (seed 20260910) | 22 records; jobs 00-15 are the 2026-09-10 engineering fixtures, byte-identical |
| `negatives` | 100 | see EVALUATION.md | Dryad, catalog `comparison_catalog.json` | none: unlabelled until reviewed |

Not acquired:
- the NKA file of `sd-fb03de478c9e` (Dryad returns 404 to authenticated API,
  version and zip requests alike);
- `sd-1c816f199083` and `sd-6edda0b2d086`, which have no supported data
  files (labelled `-vunavailable`, `unavailable_evidence`);
- the Data Colada 98 file is `.xls`, which the detector refuses (scored
  `source_unavailable`, not missed).

## Labels

`labels.jsonl` here is the merged ledger of every tier (`tier` field added),
written by `check_labels.py --merge` only when every check passes. The format is
the contract in `README.md`.

- **Every real-paper issue is `reviewer: "claude-draft"`.** The labels were drafted
  from the PubPeer threads, corrections and public write-ups before the detector
  was run on any of the files. Each labelled cell has been checked against the
  bytes. None has been signed off by a person yet.
- A corrected version whose duplication is gone has `issues: []` and a
  top-level `confirmed_error`. It is **not** a verified negative.
- Byte-identical versions (metadata-only Dryad revisions) carry identical
  issues. Recall over issue/version instances therefore counts them more than
  once, so EVALUATION.md also reports a deduplicated figure.

## Rebuild and check

```sh
PY=$(metascience python)
export PYTHONPATH=copy_paste_detector/src
GT=/media/dan/data/agent_for_forensic_metascience_copy_paste_files/ground_truth
$PY -m copy_paste_detector.datasets download --catalog benchmarks/copy_paste/sciencedetective_catalog.json \
  --incoming $GT/science_detective/incoming          # DRYAD_CLIENT_ID/SECRET in .env
$PY -m copy_paste_detector.datasets import --catalog benchmarks/copy_paste/sciencedetective_catalog.json \
  --incoming $GT/science_detective/incoming --output $GT/science_detective
$PY benchmarks/copy_paste/make_synthetic.py --output $GT/synthetic
$PY -I benchmarks/copy_paste/check_labels.py --root $GT  # 0 failures required
$PY -m copy_paste_detector.batch $GT/science_detective/manifest.jsonl --output-dir runs/sd --workers 4
$PY -m copy_paste_detector.benchmark --labels $GT/science_detective/labels.jsonl \
  --run-index runs/sd/index.json --output runs/sd/score
```

The famous tier was assembled by hand from `famous_catalog.json` (source URL,
retrieval date, sha256 for each file); `pnas.org` returned 403, so the Südhof
`sd01.xlsx` comes from the PMC copy.
