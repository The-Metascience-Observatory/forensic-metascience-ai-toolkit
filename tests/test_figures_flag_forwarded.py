"""The --figures flag must actually reach analyze_paper.

The CLI declared `--figures`, printed "Figure pass enabled...", then called
analyze_paper WITHOUT forwarding it -- so the sweep ran with extract_figures
stripped and a prompt saying figures were off, while the operator was told the
pass was on. A silently-dropped explicit instruction. These tests pin the
forwarding at the two hops the subagent found broken.
"""

import inspect

import forensic_metascience_ai_toolkit.agent as agent_mod
from forensic_metascience_ai_toolkit.agent import analyze_paper_sync


def test_analyze_paper_sync_forwards_figures(monkeypatch):
    captured = {}

    async def fake_analyze_paper(paper_path, **kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(agent_mod, "analyze_paper", fake_analyze_paper)
    analyze_paper_sync("x.pdf", figures=True)
    assert captured.get("figures") is True, (
        "analyze_paper_sync dropped the figures flag on the way to analyze_paper"
    )


def test_cli_analyze_passes_figures_to_analyze_paper():
    # The CLI closure forwards `figures=figures`; assert the source wires it,
    # since the whole defect was a missing keyword at the call site.
    src = inspect.getsource(__import__("forensic_metascience_ai_toolkit.cli", fromlist=["analyze"]))
    assert "figures=figures" in src, "cli.analyze must forward figures to analyze_paper"
