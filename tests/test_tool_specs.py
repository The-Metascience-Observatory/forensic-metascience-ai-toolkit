"""Phase 3a: each tool's definition lives in `tool_specs/<family>/`.

The move was verbatim, and the pins that prove it are elsewhere:
`tests/data/registry_snapshot.json` (every tool's schema, description hash,
roles and CLI name) and `tests/test_pipeline_parity.py` (what every agent is
sent). This file pins the LAYOUT: every family is a folder with `spec.py` +
`TOOL.md`, every tool is defined exactly once and listed in `ORDER`, and the
integrity cards and descriptions are read from TOOL.md.
"""

from pathlib import Path

from metascience_agent import registry as R
from metascience_agent import tool_specs as TS

PKG = Path(TS.__file__).resolve().parent


def test_every_family_folder_is_listed_and_complete():
    folders = {p.name for p in PKG.iterdir()
               if p.is_dir() and not p.name.startswith(("_", "."))}
    assert folders == set(TS.FAMILIES)
    for fam in TS.FAMILIES:
        assert (PKG / fam / "spec.py").is_file(), fam
        assert (PKG / fam / "TOOL.md").is_file(), fam


def test_every_tool_is_defined_once_in_registry_order():
    assert [s.name for s in R.SPECS] == list(TS.ORDER)
    assert len(set(TS.ORDER)) == len(TS.ORDER) == len(R.SPECS)


def test_descriptions_come_from_tool_md_verbatim():
    for fam in TS.FAMILIES:
        descs = TS.descriptions(str(PKG / fam / "spec.py"))
        assert descs, fam
        for name, text in descs.items():
            assert R.BY_NAME[name].description == text


def test_integrity_cards_come_from_tool_md():
    cards = TS.integrity()
    assert set(cards) == {s.name for s in R.SPECS}
    for name, card in cards.items():
        spec = R.BY_NAME[name]
        assert spec.evidence == card["evidence"]
        assert tuple(spec.assumptions) == tuple(card["assumptions"])
        assert isinstance(card["assumptions"], tuple)


def test_a_family_folder_is_named_for_its_implementation():
    # `grim_harness` is named for its implementation too, which is a
    # harness module (`metascience_agent.grim_harness`), not a pure tool.
    grouped = {"readers", "cells", "check_table", "run_script", "tracks",
               "multiplicity", "raw_duplication", "grim_harness"}
    for fam in set(TS.FAMILIES) - grouped:
        for spec in R.SPECS:
            if spec.fn.__module__ == f"metascience_agent.tools.{fam}":
                break
        else:
            raise AssertionError(f"tool_specs/{fam} has no tools/{fam}.py tool")


def test_the_procedure_guidance_lives_beside_its_tools():
    """Phase 3b: the tools agent's step-3 bullets are in TOOL.md, numbered,
    each in the family of the first tool it names, and assembled back into
    the prompt (byte-identical to before: test_pipeline_parity)."""
    from metascience_agent.core import prompts
    blocks = TS.guidance()
    assert [b[0] for b in blocks] == list(range(1, len(blocks) + 1))
    fam = TS.family_of()
    for _n, text, names in blocks:
        assert text.startswith("   - `") and names, text[:60]
        lead = [n for n in __import__("re").findall(r"`(\w+)`", text.split(" — ")[0])
                if n in names]
        assert f"<!-- guidance:{_n:02d} -->" in (PKG / fam[lead[0]] / "TOOL.md").read_text()
    raw = __import__("metascience_agent.core.prompts", fromlist=["x"]).prompt_path("tool_expert.md").read_text()
    assert prompts.TOOL_GUIDANCE_MARK in raw and "`grimmer_check` —" not in raw
    body = prompts.tool_expert_body()
    assert prompts.TOOL_GUIDANCE_MARK not in body
    assert "   - `grimmer_check` — SDs from integer data." in body
    assert any("csf_test" in t for t in TS.guidance_for("csf_test"))
