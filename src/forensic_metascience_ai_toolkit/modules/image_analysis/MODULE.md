---
name: image_analysis
kind: ai_review
producer: image_track
label: image_forensics
order: 30
options: [ai_screening, segment_montages, reassemble_tiles]
display: Image analysis
---
# Image analysis

A thin host-side adapter over the independent image package
(`metascience_observatory_image_analysis.image_forensics.pipeline`), reached
only through `image_plugin`. The detector and screening code are not changed
here, and without the package this module refuses by name: the channel reads
`refused` and the run says the figures were NOT examined.

It was two modules until 2026-10-18 (`image_detection` + `image_review`),
but the package owns detect-then-screen as one unit and the review module
only reported what the detection call had done. The old names are not
accepted.

**`ai_screening: true`** (the default) makes the package's combined call,
`pipeline.run`: detect, then AI-screen (Luna screens, Grok confirms; the
models are set by `METASCIENCE_IMAGE_SCREEN` / `METASCIENCE_IMAGE_CONFIRM`,
not the YAML -- choosing them per pipeline would need `screen_paper_result`
to take them, and editing `screening.py` invalidates every pair-screening
stamp). Only screened `issue` items become publishable findings.

**`ai_screening: false`** (the shipped `image_detect` pipeline) runs the
detector alone (`pipeline.run_detection`) and files every candidate as an
UNSCREENED row: built by the package's own row builder, `quarantined: true`,
`inputs.ai_screening: {status: not_run}`. Such a row:

- is never the headline -- enforced in code (`adjudicate.apply`), not only by
  the rulebook;
- is never published -- publication reads the screening ledger, and an
  unscreened item has no record there;
- is named in the run's limitations, with the count.

The detector's coverage gaps come from `pipeline.coverage_limitations`, the
same helper `pipeline.run` uses.
