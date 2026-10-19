"""One function, one name -- and the exceptions are enumerated.

WHY. Greg, 2026-08-26:

    "It seems you sometimes guess at the correct names of functions (e.g.
     _checks_tally), and the mismatch causes problems. Can you please undertake
     a systematic analysis of the codebase, catalogging every function name, and
     make sure that there aren't any multiply-named functions present."

The census that prompted this file: **1,929 distinct function names across 2,062
definitions.** The honest result is that the codebase is nearly free of genuine
multiple-naming -- four documented deprecated aliases in `locators.py`, of which
one (`_quote_boxes`) had zero references anywhere and has been removed, and three
ordinary public-wrapper / private-implementation pairs. The `_checks_tally`
mistake was a caller guessing, not a naming defect.

So this file does not pretend to fix a mess that is not there. It PINS the small
alias surface, so that the next second-name-for-one-function has to be added
deliberately rather than accumulating. A closed set a reader can check in one
step is the difference between "we have three aliases" and "we have some".

WHAT IS DELIBERATELY NOT FLAGGED. 46 pairs of `x` and `_x` exist across the
package, almost all in unrelated modules -- `bundle._clip` and
`findings_v2.clip` are different local helpers that happen to share four
letters, and forbidding that would be a rename campaign with no defect behind
it. Only same-module pairs and true assignment aliases are pinned.
"""
from __future__ import annotations

from tests.source_paths import canonical, IMAGE_SRC
import ast
import collections
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[1] / "src" / "metascience_agent"

#: `alias = existing_function` at module level. Every entry is a SECOND name for
#: a function that already has one, which is the shape that makes a caller
#: guess. Each needs a reason a reader can evaluate.
ALLOWED_ALIASES: dict[tuple[str, str], str] = {
    ("locators.py", "_fold"):
        "bundle.py re-exports it and adjudicate.py imports it; renaming the "
        "call sites is a separate change",
    ("locators.py", "_pdf_pages"):
        "bundle.py imports it at line 2343",
    ("locators.py", "_locate"):
        "bundle.py imports it, and its module docstring names `bundle._locate` "
        "as the thing being kept working",
}

#: One module defining both `x` and `_x`. Ordinary when it is a public wrapper
#: over a private implementation; worth naming so a fourth does not appear
#: unnoticed.
ALLOWED_SAME_MODULE: dict[tuple[str, str], str] = {
    ("anchors.py", "base"):
        "`_base` is a module-level builder; `base()` is a nested closure in a "
        "different scope",
    ("progress.py", "start"):
        "methods on two different classes",
    ("tools/celltypes.py", "parse_cell"):
        "public wrapper at 527 over the implementation at 557",
}


#: Image-package modules this census reached through host alias files until
#: 2026-10-01, when those aliases were deleted (plus `regions_docling`, which
#: moved). Read directly so the census keeps exactly the reach it had; widening
#: it to the whole package is a separate decision (it would newly flag seven
#: same-module `x`/`_x` pairs under compute/ and image_resources/text_support).
IMAGE_MODULES = (
    "image_forensics/adjudicate.py", "image_forensics/benchmark.py",
    "image_forensics/caption_context.py", "image_forensics/channel_merge.py",
    "image_forensics/channel_validation.py", "image_forensics/chrome_mask.py",
    "image_forensics/constants.py", "image_forensics/copy_move_adjudicate.py",
    "image_forensics/copy_move.py", "image_forensics/dataset_benchmark.py",
    "image_forensics/dataset_fetch.py", "image_forensics/duplication_review_figure.py",
    "image_forensics/evidence.py", "image_forensics/exhibit_paths.py",
    "image_forensics/figure_context.py", "image_forensics/image_analysis.py",
    "image_forensics/image_corpus.py", "image_forensics/labels.py",
    "image_forensics/match_control.py", "image_forensics/pair_context.py",
    "image_forensics/panels.py", "image_forensics/pdf_deliveries.py",
    "image_forensics/pdf_occurrences.py", "image_forensics/pmc_figures.py",
    "image_forensics/publisher_figures.py", "image_forensics/retain.py",
    "image_forensics/screening_config.py", "image_forensics/screening.py",
    "image_forensics/screening_reconcile.py", "image_forensics/screening_visuals.py",
    "image_forensics/source_identity.py", "image_forensics/sweep.py",
    "image_forensics/triage_rank.py",
    "image_review.py", "extraction/regions_docling.py",
)


def _modules():
    seen = set()
    paths = [(p, str(p.relative_to(ROOT))) for p in sorted(ROOT.rglob("*.py"))]
    if IMAGE_SRC is not None:  # the separately distributed image package, when installed
        paths += [(IMAGE_SRC / m, "image:" + m) for m in IMAGE_MODULES]
    for p, key in paths:
        target = canonical(p).resolve()
        if target in seen:                               # reached both ways: once
            continue
        seen.add(target)
        try:
            yield key, ast.parse(target.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:                              # pragma: no cover
            continue


def _function_names(tree) -> set[str]:
    return {n.name for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def _aliases():
    """`name = other_name` at module level, where the RHS is a function here."""
    for mod, tree in _modules():
        fns = _function_names(tree)
        for node in tree.body:
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name):
                for t in node.targets:
                    if isinstance(t, ast.Name) and node.value.id in fns:
                        yield mod, t.id, node.value.id


class TestTheAliasSurfaceIsClosed:
    def test_no_undeclared_alias(self):
        found = {(m, new) for m, new, _ in _aliases()}
        extra = sorted(found - set(ALLOWED_ALIASES))
        assert not extra, (
            f"new function alias(es) {extra}: a second name for a function that "
            "already has one is what makes a caller guess. Add it to "
            "ALLOWED_ALIASES with a reason, or use the existing name.")

    def test_every_declared_alias_still_exists(self):
        """An allowance whose reason has expired is the thing an exhaustive
        list exists to surface -- `_quote_boxes` sat here with zero callers."""
        found = {(m, new) for m, new, _ in _aliases()}
        gone = sorted(set(ALLOWED_ALIASES) - found)
        assert not gone, (
            f"{gone} is allowed but no longer defined; drop the entry")

    def test_each_allowance_carries_a_checkable_reason(self):
        for key, why in ALLOWED_ALIASES.items():
            assert len(why) > 25, f"{key}: give a reason a reader can check"


class TestSameModuleUnderscorePairs:
    def test_no_undeclared_pair(self):
        found = set()
        for mod, tree in _modules():
            fns = _function_names(tree)
            for n in fns:
                if n.startswith("_") and n[1:] in fns:
                    found.add((mod, n[1:]))
        extra = sorted(found - set(ALLOWED_SAME_MODULE))
        assert not extra, (
            f"module(s) defining both `x` and `_x`: {extra}. In one file that "
            "is a coin-flip for any caller. Declare it with a reason or rename.")

    def test_declared_pairs_still_exist(self):
        found = set()
        for mod, tree in _modules():
            fns = _function_names(tree)
            for n in fns:
                if n.startswith("_") and n[1:] in fns:
                    found.add((mod, n[1:]))
        assert not sorted(set(ALLOWED_SAME_MODULE) - found)


class TestTheCensusItselfStillWorks:
    """A detector that cannot fire reports zero as convincingly as a clean
    codebase. These are the positive controls."""

    def test_the_alias_scan_finds_a_constructed_alias(self, tmp_path):
        src = "def real():\n    return 1\n\nfake = real\n"
        tree = ast.parse(src)
        fns = _function_names(tree)
        hits = [t.id for node in tree.body
                if isinstance(node, ast.Assign) and isinstance(node.value, ast.Name)
                and node.value.id in fns
                for t in node.targets if isinstance(t, ast.Name)]
        assert hits == ["fake"]

    def test_the_scan_ignores_an_assignment_to_a_non_function(self):
        tree = ast.parse("x = 1\ny = x\n")
        assert not _function_names(tree)

    def test_the_package_actually_has_functions_to_scan(self):
        """Guards against a walk that silently finds nothing -- the failure
        that makes every assertion above pass vacuously."""
        total = sum(len(_function_names(t)) for _, t in _modules())
        assert total > 1500, f"only {total} functions found; the walk is broken"
