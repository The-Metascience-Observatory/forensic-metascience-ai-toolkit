"""The paper scaffold: a complete, structured description of what a paper contains.

WHAT THIS IS. A component whose ONLY job is extraction -- every study, variable,
value, comparison and claim a paper makes, each located where the paper made it.
It renders no verdicts and runs no checks. It is the layer the checks are meant to
bind to, and the layer a human can read to understand a paper's structure without
any error-checking at all.

WHY IT EXISTS. FMT is organised around FINDINGS: checks fire on table cells and
meaning is attached afterwards. The anatomy layer (`anatomy.py`) sits beside that
rather than under it; measured on a live run, 3.8% of registered values were bound
to any variable. Greg Fitzgerald's position (2026-09-04) is that the ordering is
backwards: read the paper the way a person would -- comprehension, then variables
and their characteristics, then values expressed in terms of that structure -- and
the checks become a deterministic function of what was extracted. The false
accusations this project has measured came from MISSING structure (a guessed
bound, denominator or unit), not from too much checking. With premises extracted
rather than inferred, the check does not guess; the risk moves to the extraction,
where it can be measured against a paper a human can read.

THE SHAPE, in one sentence: a normalised core -- entity tables with human-readable
ids (studies, groups, phases, variables, procedures, values, comparisons, claims)
where every value is a row at a COORDINATE (study, group, phase, variable,
statistic) -- plus rendered views for people. The data is never duplicated for
presentation; the human account is a projection of the same rows back into the
paper's own organisation. See `schema.py` for the argument and `render.py` for
the projection.

THE THREE PASSES (`passes.py`): comprehension, variables, values -- outside-in.
Between them sits deterministic code (`bind.py`): table cells come from the
existing walker (`prepass.paper_tables`), never from the model's transcription;
quotes are verified against the text with `quotes.classify`; every numeral in the
analytic sections is accounted for or listed as a residual with a reason
(`numerals.index` is the floor). `not stated` is always a correct answer. An
invented value never is.

WHAT IT DOES NOT DO. It is NOT wired into the finding pipeline or the binder.
`applicability.py` ENUMERATES which check families would have every premise at
which coordinates -- a read-only census that demonstrates the determinism claim --
and calls no tool.
"""

from __future__ import annotations

SCHEMA_VERSION = "scaffold/0.1"

__all__ = ["SCHEMA_VERSION"]
