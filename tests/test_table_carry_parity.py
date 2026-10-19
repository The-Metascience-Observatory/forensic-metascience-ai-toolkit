"""What the model is told to rely on must reach the deterministic floor too.

THE ASYMMETRY THIS EXISTS TO CATCH. `jats._build_table` produces one record per
table. Two projections read it: `get_table`, which the MODEL calls directly, and
`prepass.paper_tables`, the single enumerator the deterministic floor walks.
Same extractor, two projections -- and for two weeks one of them was quietly
poorer.

    a685211  `caption`, `footnotes`, `section`, `id`, `page`, `header_rows`
             were dropped. On 10.1002--eat.24415 Table 1 the footnote reads
             "Note: N = 107" -- the table's own stated denominator -- while the
             agent prompt instructs the model to "Read each table's footnotes
             before typing". The model got them; the floor did not.
    fb60fd2  the same shape again: `header_rows` carried while the producer
             emitted the depth as `n_header_rows`, so depth was null on 8 of 26.

Both were found by hand-diffing two dicts. Neither had a test. Measured
2026-08-29: ZERO assertions anywhere in this suite covered a field either commit
added, so both fixes could have been reverted silently.

WHY THE PARITY TEST IS ANCHORED TO THE PROMPT AND NOT TO THE FLOOR. An
allowlist written from current floor behaviour passes on the day it is written
and can never fail -- on 2026-08-27 `footnotes` WAS a drop, so it would have
been listed with a plausible reason and the check would have been green through
the entire defect. `docs/tool_reference.md` is the canonical statement of what
a table offers, written independently and earlier, and `agent.py` says of those
fields that "each one exists because ignoring it produces a false accusation".
Requiring the floor to see what the model is told to rely on is therefore a real
constraint, and it FAILS TODAY.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from metascience_agent import prepass

CORPUS = Path("tests/fixtures/papers/high_value_pdfs_to_run_on")

#: Per-table fields `docs/tool_reference.md` documents `get_table` as
#: returning. Copied from the prompt, not from the code -- that is the point.
PROMPT_TABLE_FIELDS = frozenset({
    "cells", "data", "headers", "label", "caption", "section",
    "footnotes", "spans", "alignment_uncertain", "image_only", "width",
})

#: Fields the floor deliberately does not carry, each with the reason. A field
#: may be exempted, but not silently: adding a name here is a decision someone
#: has to write a sentence for.
FLOOR_EXEMPT = {
    "data": "a projection of `cells`, which is canonical and carried verbatim",
    "headers": "a projection of `cells`",
    "width": "recomputable from `cells`",
}


def _tables():
    if not CORPUS.is_dir():
        pytest.skip("working corpus not in this checkout")
    for d in sorted(p for p in CORPUS.iterdir() if p.is_dir()):
        for t in prepass.paper_tables(d, include_supplements=True):
            yield d.name, t


class TestTheShippedFixesCannotSilentlyRevert:
    """a685211 and fb60fd2 had no test. They do now."""

    def test_the_table_facts_a685211_restored_are_still_carried(self):
        seen = {k: 0 for k in ("caption", "footnotes", "section", "table_id", "page")}
        n = 0
        for _paper, t in _tables():
            n += 1
            for k in seen:
                if t.get(k):
                    seen[k] += 1
        assert n > 20, "the corpus must actually yield tables or this proves nothing"
        assert seen["caption"] > 0 and seen["footnotes"] > 0 and seen["section"] > 0, (
            f"a685211's table facts stopped reaching the floor: {seen}")

    def test_the_footnote_carrying_the_stated_n_still_arrives(self):
        """The specific record the whole defect was found on."""
        d = CORPUS / "10.1002--eat.24415"
        if not d.is_dir():
            pytest.skip("eat.24415 not in this checkout")
        blob = " ".join(
            str(f.get("text", "")) for t in prepass.paper_tables(d, include_supplements=True)
            for f in (t.get("footnotes") or []))
        assert "N = 107" in blob, (
            "the table's own stated denominator no longer reaches the floor")

    def test_header_depth_is_known_on_every_table(self):
        """fb60fd2. The producer emits the list as `header_rows` on some paths
        and the count as `n_header_rows` on others; a consumer wanting the depth
        must not have to know which producer it got."""
        missing = [(p, t.get("label")) for p, t in _tables()
                   if t.get("n_header_rows") is None
                   and not isinstance(t.get("header_rows"), list)]
        assert not missing, f"header depth unavailable on {len(missing)} table(s)"


class TestTheFloorSeesWhatTheModelIsToldToUse:
    """The parity constraint. Not circular: the prompt predates the carry list.

    THIS TEST FAILS TODAY, deliberately, and is marked xfail rather than
    weakened. `spans` and `alignment_uncertain` are documented to the model and
    do not reach the floor -- `spans` is what the queued Pattern A work needs,
    and `alignment_uncertain` is a refusal gate the prompt tells the model to
    honour and the floor cannot see. Carrying them is a production change with
    its own accusation review, so it is filed rather than smuggled in under a
    test fix.
    """

    @pytest.mark.xfail(strict=True, reason=(
        "spans and alignment_uncertain are documented to the model and do not "
        "reach the floor; carrying them is queued, see the module docstring"))
    def test_every_documented_field_reaches_the_floor_or_is_exempt(self):
        carried: set[str] = set()
        for _paper, t in _tables():
            carried |= {k for k, v in t.items() if v not in (None, [], {})}
        # the floor renames two: `id` -> `table_id`, and adds `sections`
        carried |= {"id"} if "table_id" in carried else set()
        missing = sorted(PROMPT_TABLE_FIELDS - carried - set(FLOOR_EXEMPT))
        assert not missing, (
            f"the prompt tells the model to rely on {missing}, and the "
            f"deterministic floor never sees them. Either carry them in "
            f"prepass.paper_tables, or add each to FLOOR_EXEMPT with a reason.")

    def test_the_exemptions_all_carry_a_reason(self):
        """An exemption without a written reason is a silent drop wearing a
        constant."""
        assert all(isinstance(v, str) and len(v) > 20
                   for v in FLOOR_EXEMPT.values())
