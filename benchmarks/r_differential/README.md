# r_differential/

Exhaustive comparison of our GRIM (`tools/grim.py`) and SPRITE feasibility
verdict (`tools/sprite.py`) against R's `scrutiny::grim` and
`rsprite2::set_parameters`, over an enumerated grid of the values papers print.
The point is independence: our Python cannot find a bug in our Python.

| Script | Writes | Pass condition |
|---|---|---|
| `grim_r_differential.py` | `grim_r_differential.json` | zero disagreements |
| `sprite_r_differential.py` | `sprite_r_differential.json` | zero disagreements in `regions.in_power` (n < 10^m_prec, rsprite2's own rule for where the test discriminates) |
| `sprite_adjudicate.py` | `sprite_adjudication.json` | settles each SPRITE disagreement by exact enumeration, independent of both engines |

```bash
$(metascience python) benchmarks/r_differential/grim_r_differential.py
```

Needs `Rscript` with `scrutiny` and `rsprite2`. A full run takes about a minute (2026-10-18: 48 s GRIM, 55 s SPRITE);
`--quick` takes seconds and writes `*.quick.json` (git-ignored), so a smoke run
never replaces the record.

## How it stays honest without slowing the suite

Each result records the SHA-256 of every source file its verdict depends on
(`fingerprint.py`). `tests/test_r_differential_pin.py` runs in the normal suite,
reads the two JSONs and hashes those files: milliseconds, no R. It fails when
the code has changed since the last run, and the message names the script to
re-run. Editing `grim.py`, `sprite.py`, `rounding.py` or `severity.py` therefore
means re-running the differential before the suite is green again.

The live R comparison is in the same test file, opt-in:

```bash
RUN_R_DIFFERENTIAL=1 metascience-test tests/test_r_differential_pin.py -q
```
