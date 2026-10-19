# Reference material

Third-party works the toolkit's doctrine is built on, kept in-tree because
tests check quotations against them.

- **`intro_to_forensic_metascience.md`** — James Heathers, *An Introduction to
  Forensic Metascience* (v1, 2025-02-14), doi:[10.5281/zenodo.14871843](https://doi.org/10.5281/zenodo.14871843).
  Licensed **CC-BY 4.0** by the author; this is the Curvenote/MyST source
  export of that record, unmodified. `docs/GRIM_CONTEXT_DEPENDENCY.md` cites it
  by line number and `tests/test_docs_accuracy.py` checks every locator and the
  load-bearing quotations against this file. The PDF is on Zenodo.

Cited but deliberately NOT kept here:

- Heathers & Grimes, *GRIM-U* (Medical Evidence Project, 2026) — © The Center
  for Scientific Integrity, all rights reserved. Read it at
  <https://medicalevidenceproject.org/GRIMU>; `tools/grimu.py` implements it and
  cites that page. (A copy was committed by mistake before 2026-10-16 and
  removed.)
