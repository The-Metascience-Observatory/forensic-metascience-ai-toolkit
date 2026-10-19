# Reproduction commands

The pipeline writes each finding's `reproduction` itself. For a finding a
forensic tool produced, it replays the exact call behind it --
`metascience tool run <tool> --json '{...}'`, which re-runs the tool through
the same gates your call went through -- so record the inputs you passed in
`inputs` and leave `reproduction` out. Do not type a command: one the
pipeline cannot match to a call is marked as written by you, and an invented
one weakens the finding.

- A finding whose load-bearing number came from `run_python_script`:
  `reproduction` names the persisted script by the path the tool reported
  (e.g. `analysis_code/001_table4_roster.py`).
- A reading of the paper that no calculation reproduces: write
  `NO COMMAND APPLIES` and say why.
