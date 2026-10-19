# benchmarks/

| Benchmark | What it measures | Run with |
|---|---|---|
| [paper_reviews/](paper_reviews/README.md) | The full review pipeline on four real papers with answer keys (apple cider vinegar, air force, wound healing, cerebrolysin): recall of known problems, false accusations, verdict and severity calibration. Paid. | `metascience eval` |
| [litvak/](litvak/README.md) | The pipeline against Litvak's published findings on a 100-paper set | scripts in `litvak/` |
| [copy_paste/](copy_paste/README.md) | The raw-data copy-paste detector on public datasets with reported concerns | `copy-paste-dataset` |
| [grim/](grim/README.md) | Recall of the GRIM checker, cell by cell, on published papers with documented GRIM inconsistencies, one subfolder per ground-truth set: checked / flagged / reported. Papers in the sibling `_papers` corpus. | `benchmarks/grim/score.py` |
| [r_differential/](r_differential/README.md) | Our GRIM and SPRITE against R's `scrutiny` and `rsprite2`, case by case over an enumerated grid (~400k GRIM, ~154k SPRITE cases). Needs R; about a minute each. The suite only checks, for free, that the recorded result still matches the current source (`tests/test_r_differential_pin.py`). | `benchmarks/r_differential/*_r_differential.py` |

Related, outside this folder: `eval/ground_truth/` (78 papers, adjudicated
fraud cases plus controls, for corpus-level scoring) and `metascience benchmark`
(synthetic papers; free; fails if a clean paper is accused).
