"""Shared implementation extracted for independent image analysis."""
from __future__ import annotations


import json


from pathlib import Path


CHANNEL_STATES = ("ran", "ran_result_discarded", "refused", "did_not_run",
                  "unknown")


_BUNDLE_SUFFIX = "_bundle"


def review_dirs(paper_dir: Path) -> list[Path]:
    """Every review directory in a paper, newest first, bundles excluded.

    Sorted by mtime rather than by name: the names encode a model and a date
    (`forensic_review_opus_08_09_2026`) but not consistently -- `forensic_review`
    and `forensic_review_current` carry no date at all -- so a name sort puts
    the undated ones wherever the alphabet happens to place them.
    """
    out = [d for d in paper_dir.iterdir()
           if d.is_dir()
           and d.name.startswith("forensic_review")
           and not d.name.endswith(_BUNDLE_SUFFIX)]
    return sorted(out, key=lambda d: d.stat().st_mtime, reverse=True)


def run_kind(doc: dict | None) -> str:
    """What produced a findings-v2 document: `full_review` (the tool expert
    ran), `image_track` (only the image track ran -- an `image-sweep` run),
    else `legacy`. ONE derivation: `db_push.push_run` copies it into
    `runs.kind`, `numeric_channel` and `corpus_stats._current_doc` read it,
    and before it existed an image-only review directory made the workbench
    report the NUMERIC pipeline as `ran` on a paper it never touched."""
    ch = (doc or {}).get("channels") or {}

    def _state(name: str):
        v = ch.get(name)
        return v.get("state") if isinstance(v, dict) else v

    # A PIPELINE THAT IS NOT A COMPLETE REVIEW is never `full_review`, however
    # much of the numeric pipeline it ran: a one-tool run or an unadjudicated
    # one would otherwise become the paper's current review in every reader
    # that selects on that kind. An image-only pipeline is the image track's
    # kind, as an `image-sweep` run is. Documents without the block predate
    # pipelines and keep the derivation below unchanged.
    pipeline = (doc or {}).get("pipeline")
    if isinstance(pipeline, dict) and pipeline.get("complete_review") is False:
        uses = {m.get("use") for m in pipeline.get("modules") or []
                if isinstance(m, dict)}
        if uses and uses <= {"image_analysis"}:
            return "image_track"
        return "partial_review"
    if _state("tool_expert") == "ran":
        return "full_review"
    if _state("image_forensics") == "ran":
        return "image_track"
    return "legacy"


_NOT_A_PAPER = frozenset({
    "done", "failed", "logs", "reviews", "blinded", "priority",
    "prioritized_cerebrolysin_papers", "already_retracted", "retracted",
})


_NESTED_PAPER_DIRS = frozenset({
    "done", "priority", "prioritized_cerebrolysin_papers",
    "already_retracted", "retracted",
})


_PAPER_INTERNAL = frozenset({
    "panels", "figures", "figmap", "supplementary", "supplement",
    "supplemental", "supplementary_material", "si", "review",
    "__pycache__", "node_modules",
    # `markdown/` is where `extraction.markdown_out` writes `body.md` and
    # `source.json`. It is as internal as `figures/`, and its absence here let
    # it be enumerated as a paper in its own right.
    "markdown", "pmc_figures",
})


_DO_NOT_DESCEND = _NOT_A_PAPER - _NESTED_PAPER_DIRS


def _is_paper_internal(name: str) -> bool:
    """Scaffolding that lives INSIDE a paper and is never a paper itself.

    THE BUNDLE CLAUSE IS WHY THIS COMMENT EXISTS. A viewer bundle is written
    either as `<run>_bundle` -- caught by the `forensic_review` prefix -- or as
    `bundle_HEAD_<date>`, which matched nothing. One such directory made its
    PARENT look like a folder-of-papers, so `_should_descend` recursed into a
    paper and enumerated its internals instead of it.

    MEASURED on the 12-paper working corpus: `10.1002--eat.24415`, which has
    EIGHT review runs, vanished from the index entirely; `bundle_HEAD_2026-08-12`
    and `markdown` appeared in its place; and `corpus-stats` reported "1/13
    papers" for a corpus of twelve -- corrupting the denominator of every fire
    rate, `by_journal` and `by_year` count on the page.
    """
    return (name in _PAPER_INTERNAL
            # fetchpdf writes <PDF stem>_images/ beside its source PDF.
            # DOI-prefixed image directories otherwise look like child papers,
            # making discovery descend past the actual paper and omit it.
            or name.endswith(("_images", "_figures"))
            or name.startswith("forensic_review")
            or name.startswith("bundle_")
            or name.endswith("_bundle"))


def _looks_like_paper_leaf(d: Path) -> bool:
    """Positive evidence that `d` is a paper, not a folder of papers.

    Used only to decide whether a parent is a nest. Does not recurse: a
    paper's `panels/` or `forensic_review/` must not make the paper itself
    look like a nest.
    """
    if not d.is_dir() or d.name.startswith(".") or d.name in _NOT_A_PAPER:
        return False
    if _is_paper_internal(d.name):
        return False
    slug = d.name
    markers = (
        d / f"{slug}.pdf",
        d / f"{slug}.xml",
        d / f"{slug}.html",
        d / f"{slug}.landing.html",
        d / f"{slug}.provenance.json",
        d / "metadata.json",
        d / "image_duplication_findings.json",
        d / "forensic_review",
        d / "panels",
        d / "figures",
    )
    if any(p.exists() for p in markers):
        return True
    if slug.startswith("10.") and "--" in slug:
        return True
    return False


def _has_paper_children(d: Path) -> bool:
    try:
        return any(_looks_like_paper_leaf(child) for child in d.iterdir())
    except OSError:
        return False


def _should_descend(d: Path) -> bool:
    if not d.is_dir() or d.name.startswith("."):
        return False
    if d.name in _NESTED_PAPER_DIRS:
        return True
    if d.name in _DO_NOT_DESCEND:
        return False
    return _has_paper_children(d)


def iter_paper_dirs(root: Path) -> list[Path]:
    """Paper directories under a project, including `done/<slug>` and
    one extra level of batch folders such as `grok_run/<slug>`.

    Top-level `done/` and the named queue folders are scaffolding, not
    papers. The papers inside them are. A folder that is not on that list
    but that *contains* paper directories (a batch run dumped into
    `grok_run/`) is the same shape: not itself a paper, children are.
    One extra level only — a recursive walk would treat `panels/` and
    `forensic_review/` as papers.
    """
    root = Path(root)
    if not root.is_dir():
        return []
    out: list[Path] = []
    for d in sorted(root.iterdir()):
        if looks_like_paper(d):
            out.append(d)
        elif _should_descend(d):
            for child in sorted(d.iterdir()):
                if looks_like_paper(child):
                    out.append(child)
    return _dedupe_paper_copies(root, out)


def _newest_run_date(d: Path) -> str:
    """Newest analysed_at across a paper copy's runs ("" when undated) --
    the same ordering the DB's current_runs view and corpus_stats apply."""
    best = ""
    for rd in list(d.glob("forensic_review*")) + [d]:
        for probe in (rd / "run_meta.json", rd / "findings.v2.json"):
            try:
                doc = json.loads(probe.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            when = str(doc.get("analysed_at")
                       or (doc.get("legacy") or {}).get("analysed_at") or "")
            if when > best:
                best = when
    return best


def _dedupe_paper_copies(root: Path, dirs: list[Path]) -> list[Path]:
    """One entry per paper NAME. A batch script can leave a physical copy
    behind (measured: masliah's 10.1038--s41398-021-01709-9 sits top-level
    AND in grok_run/), and counting both doubles every one of its findings
    in the denominators -- caught live by `corpus-stats --verify`, where
    the database (which holds the paper once) disagreed with the file scan
    by exactly one paper's rows. The kept copy is the one whose newest run
    is newest -- the same rule the DB's current-run view applies -- with
    the top-level copy winning ties."""
    names: dict[str, list[Path]] = {}
    for d in dirs:
        names.setdefault(d.name, []).append(d)
    keep: dict[str, Path] = {}
    for name, copies in names.items():
        if len(copies) == 1:
            keep[name] = copies[0]
            continue
        keep[name] = max(
            copies,
            key=lambda d: (_newest_run_date(d), 1 if d.parent == root else 0))
    return [d for d in dirs if keep.get(d.name) == d]


def looks_like_paper(d: Path) -> bool:
    """A paper directory, as opposed to corpus scaffolding.

    DELIBERATELY ALMOST EVERYTHING, and the first version was not. It required
    a PDF, an XML, a `body.md`, a `panels/` or a review directory -- all of
    which are evidence that something WORKED. Measured on
    `cerebrolysin_papers`: that test dropped 50 of 423 directories, and 49 of
    them are papers whose FETCH FAILED. Each holds a `.landing.html`, a
    `.provenance.json` and a `_supplementary_info.json` and no PDF: the
    publisher served an interstitial and we kept the evidence.

    Those are the most important rows in the corpus. A paper nobody could
    download is a coverage hole, and a scanner that hides it reports a corpus
    of 373 fully-harvested papers when the truth is 422 papers of which 49
    were never obtained. That is the same substitution the toolkit exists to
    catch -- our failure rendered as an absence of findings -- committed by
    the tool that is supposed to make coverage visible.

    So the test is now negative: a directory is a paper unless it is known
    scaffolding, a folder *of* papers, or empty. `sources` says what is
    actually in it. A batch folder such as `grok_run/` is the folder-of-papers
    case: it is non-empty and not in `_NOT_A_PAPER`, but its children are the
    papers.
    """
    if not d.is_dir() or d.name.startswith(".") or d.name in _NOT_A_PAPER:
        return False
    if _is_paper_internal(d.name):
        return False
    try:
        if not any(d.iterdir()):
            return False
    except OSError:
        return False
    if _has_paper_children(d):
        return False
    return True
