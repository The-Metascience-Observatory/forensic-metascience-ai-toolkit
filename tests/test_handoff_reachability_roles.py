"""`handoff` must not be wired through the legacy pipeline it audits.

PREREQUISITES (c) AND (d) FOR THE LEGACY DELETION, both a variant of one
failure: this module decided whether the pipeline was wired by asking
`agent.py`'s LEGACY names, so deleting the legacy body would have made the
audit that exists to catch a stranded tool report OUR OWN CLEANUP as a broken
pipeline -- or raise AttributeError and answer "could not be measured" on every
run. An audit that cries wolf about a deliberate change is ignored at exactly
the rate a real break needs it not to be.

(c) `reachability` read `agent.STAGE1_TOOLS` / `STAGE2_TOOLS`; it now asks
`registry.stage_tools` for the three roles, which is what those aliases were
derived from anyway.

(d) Four `_reads` needles pointed into the legacy body or at
`stage2_editorial.md`; they now name the live pipeline's equivalents.
"""
from __future__ import annotations

import re

import pytest

from metascience_agent import handoff, registry

SRC = handoff.SRC


class TestReachabilityAsksTheRegistryRoles:
    def test_it_does_not_import_agent(self):
        """Importing a module it no longer reads would tie this audit's
        survival to the legacy pipeline's.

        Asserted on CODE, not on prose: the function's comment explains what it
        used to read, and an assertion that scanned the whole text would fire
        on its own explanation.
        """
        body = (SRC / "handoff.py").read_text(encoding="utf-8")
        fn = body[body.index("def reachability"):]
        nxt = fn.find("\ndef ", 1)
        if nxt != -1:
            fn = fn[:nxt]
        code = "\n".join(ln for ln in fn.splitlines()
                         if not ln.lstrip().startswith("#"))
        assert "import agent" not in code
        assert "_agent.STAGE1_TOOLS" not in code
        assert "_agent.STAGE2_TOOLS" not in code

    def test_every_registered_tool_is_still_reachable(self):
        out = handoff.reachability()
        assert out["ok"] is True, out.get("stranded")
        assert out["n_registered"] == len(registry.SPECS)

    def test_the_role_counts_are_reported_and_non_zero(self):
        out = handoff.reachability()
        for key in ("n_tool_agent", "n_science_agent", "n_adjudicator"):
            assert out[key] > 0, key

    def test_the_retired_stage_keys_are_gone(self):
        """Not kept as aliases: one number under two names, the second naming a
        pipeline that no longer exists, is the duplication this cleanup is for."""
        out = handoff.reachability()
        assert "n_stage1" not in out and "n_stage2" not in out


class TestEveryWiringNeedleStillResolves:
    """THE GUARD THAT MAKES THE DELETION SAFE. `_reads` returns False for a
    missing file OR a vanished name -- silently. So a needle aimed at deleted
    code degrades this audit from "wired" to "not wired" with no error at all,
    which is the failure mode the whole module exists to make impossible.

    Every needle in `handoff.py` must name something that is actually there.
    """

    @staticmethod
    def _needles():
        body = (SRC / "handoff.py").read_text(encoding="utf-8")
        return re.findall(r'_reads\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', body)

    def test_at_least_the_known_needles_are_found(self):
        assert len(self._needles()) >= 5, (
            "the needle scan stopped matching; this guard would pass vacuously")

    @pytest.mark.parametrize("module,needle", _needles.__func__())
    def test_the_needle_resolves(self, module, needle):
        assert handoff._reads(module, needle), (
            f"handoff asks whether {module} mentions {needle!r} and it does "
            f"not -- so this hand-off silently reports as UNWIRED. If the code "
            f"moved, re-point the needle; do not delete the check.")

    def test_no_needle_names_a_legacy_prompt(self):
        for module, _needle in self._needles():
            assert "stage1_sweep" not in module and "stage2_editorial" not in module, (
                f"{module} is deleted with the legacy pipeline")
