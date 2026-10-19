"""Which severities accuse — one definition each, for the two things that means.

`ACCUSATORY` was defined ELEVEN times across this codebase with zero imports
between them, and it had split into two member sets. The split turned out NOT
to be a copy error: it is two genuine concepts wearing one name, and merging
them into a single set would have silently moved a pre-registered threshold.

    ACCUSES_AT_ALL    suspicious + above -- does this say anything against the
                      paper? Used for "warn the reader", "re-check this",
                      "we dropped an accusation".
    ACCUSATION_GRADE  highly_suspicious + above -- is it strong enough to be an
                      accusation we would defend? Used for pre-registered
                      fire-rate thresholds and for the sensitivity harness,
                      where `suspicious` is deliberately below the bar.

THE ONE THAT WAS WRONG. `cli.py` carried the GRADE set under a comment reading
"Severities that constitute an accusation against a paper" -- the at-all
meaning -- and `warn_if_assumed` acts on that meaning: it prints what was
ASSUMED whenever an accusation rests on an unstated premise. So a `suspicious`
verdict resting on an assumed data type printed no warning, on every CLI
invocation without `--data-type`. Every other module treats `suspicious` as
accusing; the CLI disagreed with all of them, silently, under a comment that
agreed with them.

THE TWO THAT WERE RIGHT, and must stay at the higher bar:
`evaluation/corpus.py` (PREREGISTRATION.md section 4, carried beside
`ACCUSATORY_SECONDARY` "so neither can be quoted alone") and `simulation.py`
(whose comments reason about injected flaws "capped at `suspicious` -- below
ACCUSATORY").
"""
from __future__ import annotations

import ast
import pathlib

import pytest

from metascience_agent.tools.severity import (ACCUSATION_GRADE, ACCUSES_AT_ALL,
                                              HIGHLY_SUSPICIOUS, IMPOSSIBLE,
                                              SUSPICIOUS)

SRC = pathlib.Path(__file__).resolve().parent.parent / "src" / "metascience_agent"


class TestTheTwoConceptsAreDistinct:
    def test_they_differ_by_exactly_suspicious(self):
        assert ACCUSES_AT_ALL == {IMPOSSIBLE, HIGHLY_SUSPICIOUS, SUSPICIOUS}
        assert ACCUSATION_GRADE == {IMPOSSIBLE, HIGHLY_SUSPICIOUS}
        assert ACCUSES_AT_ALL - ACCUSATION_GRADE == {SUSPICIOUS}

    def test_they_are_built_from_the_named_constants(self):
        """String literals are how the eleven copies drifted. If someone
        re-spells these as literals the drift becomes possible again."""
        src = (SRC / "tools" / "severity.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign):
                continue
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if not ({"ACCUSES_AT_ALL", "ACCUSATION_GRADE"} & set(names)):
                continue
            for leaf in ast.walk(node.value):
                assert not isinstance(leaf, ast.Constant) or not isinstance(leaf.value, str), (
                    f"{names} contains a string literal; build it from the "
                    "named severity constants instead")


class TestTheCliNowWarnsOnSuspicious:
    def test_the_cli_uses_the_at_all_meaning_its_comment_describes(self):
        from metascience_agent.cli import ACCUSATORY
        assert SUSPICIOUS in ACCUSATORY, (
            "warn_if_assumed prints what was ASSUMED whenever an accusation "
            "rests on an unstated premise; a `suspicious` verdict on an assumed "
            "data type is exactly that case")
        assert ACCUSATORY == ACCUSES_AT_ALL


class TestTheDeliberateHigherBarSurvives:
    def test_the_preregistered_thresholds_are_unchanged(self):
        """A pre-registered threshold that moves silently invalidates every rate
        published against it. Both are carried, so neither can be quoted alone."""
        from metascience_agent.evaluation.corpus import (ACCUSATORY,
                                                         ACCUSATORY_SECONDARY)
        assert ACCUSATORY == ACCUSATION_GRADE
        assert ACCUSATORY_SECONDARY == ACCUSES_AT_ALL
        assert SUSPICIOUS not in ACCUSATORY

    def test_the_sensitivity_harness_keeps_suspicious_below_the_bar(self):
        from metascience_agent.simulation import ACCUSATORY
        assert ACCUSATORY == ACCUSATION_GRADE
        assert SUSPICIOUS not in ACCUSATORY


class TestNoModuleRedefinesIt:
    """The ratchet. A twelfth copy is how this comes back."""

    def test_no_source_module_assigns_the_name_to_a_literal(self):
        offenders = []
        for path in SRC.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError:                      # pragma: no cover
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Assign):
                    continue
                names = {t.id for t in node.targets if isinstance(t, ast.Name)}
                if not any(n.lstrip("_").startswith("ACCUSATOR") for n in names):
                    continue
                # An assignment from a Name (an import alias) is the shared
                # definition; a literal collection is a new copy.
                if isinstance(node.value, (ast.Set, ast.Tuple, ast.List, ast.Call)):
                    offenders.append(f"{path.relative_to(SRC)}:{node.lineno} {sorted(names)}")
        assert not offenders, (
            "these define an accusatory set from a literal rather than importing "
            "one of the two named sets from tools/severity.py: " + "; ".join(offenders))

    def test_the_ratchet_can_fire(self):
        """A guard that cannot fire passed for the wrong reason."""
        tree = ast.parse('ACCUSATORY = {"impossible"}\n')
        node = tree.body[0]
        assert isinstance(node, ast.Assign) and isinstance(node.value, ast.Set)
