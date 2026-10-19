"""One DOI-to-directory mapping, because there were five and two disagreed.

FOUND 2026-08-13 by running the suite in a PRISTINE CHECKOUT ON EXT4 rather
than in the working tree on `/mnt/c`. Two tests failed there and passed here:

    assert len(results) == 78
    AssertionError: assert 76 == 78

`eval/ground_truth/manifest.csv` records DOIs as the publisher prints them, and
two of its 78 rows carry uppercase -- `10.2147/TCRM.S15812` and
`10.2147/TCRM.S43811`. The fetcher that created the directories lowercases
(`doi.strip().lower().replace("/", "--")`), so every directory on disk is
lowercase. Four other call sites hand-rolled `doi.replace("/", "--")` WITHOUT
the `.lower()`.

On `/mnt/c` -- a Windows filesystem, case-insensitive -- the mismatch is
invisible: `10.2147--TCRM.S15812` opens the directory named
`10.2147--tcrm.s15812`. On ext4, and therefore on any Linux collaborator's
machine and in any CI container, it does not, and `evaluation/corpus_run.py`
recorded those two papers as `papers_missing_on_disk` -- OUR lookup failing,
filed as a fact about the corpus, with the evaluation denominator quietly
dropping from 78 to 76.

DOIs are case-insensitive by specification (DOI Handbook §2.4), so lowercasing
is the correct normalisation and not merely the convenient one.

The rule this module exists to enforce: no caller spells the mapping itself. A
mapping written out five times is five chances to write it differently, and the
one that differs is invisible on the filesystem most of this work happens on.
"""
from __future__ import annotations

__all__ = ["doi_dirname"]


def doi_dirname(doi: str) -> str:
    """The directory name this DOI's paper lives in.

    Lowercased, with `/` replaced by `--`. Matches
    `eval/ground_truth/tools/fetch_paper.py`, which is what actually created
    the directories -- the producer defines the convention and everything else
    reads it.
    """
    return str(doi or "").strip().lower().replace("/", "--")
