---
name: raw_data
kind: deterministic
producer: raw_data_track
label: raw_data
order: 60
display: Raw data (copy-paste detector)
---
# Raw data

The copy-paste detector (`copy_paste_detector.detect_paper_duplication`) over
the paper's spreadsheets and CSVs: the top level plus the allowlisted
supplement folders (`raw_track.SUPPLEMENT_SUBDIRS`). It runs in a child
process, calls no model, and is opt-in: add `- use: raw_data` to a pipeline,
or run `raw_data_only`.

Its rows are QUARANTINED (`raw_track.QUARANTINE_REASON`): one per (file,
kind) with an accusatory group, capped at `QUARANTINE_CAP`, never the
headline. Row-pair matches have no chance model, and model-generated tables
repeat values by design. A paper with no structured file records the channel
as `did_not_run`, never as a clean result.
