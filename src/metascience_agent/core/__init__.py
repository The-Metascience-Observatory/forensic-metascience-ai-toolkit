"""The pipeline core: run context and module scheduler (docs/specs/modules.md).

The core knows the module CONTRACT, never a specific module: it schedules
producers by their declared `needs`, merges their results in canonical
order, and hands everything to the finaliser. The always-on correctness
passes (quote verification, provisional clamps, producer constraints,
anchors, sourcing, severity reconciliation) stay in `parallel.py`, because
no pipeline may switch them off.
"""
