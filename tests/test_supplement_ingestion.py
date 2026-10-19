"""`--supplement` must reach the sweep, not stop at the gate.

The flag was declared on `metascience analyze`, existence-checked, handed to
`cli._supplement_gate` -- and dropped. `analyze_paper` had no parameter for it,
and the file list the sweep works from is built independently by
`_resolve_paper_sources` globbing the paper directory. So the flag bought a
proceed past the refuse-by-default gate for a file nothing ever opened, and a
SECOND audit recomputed inside the run then printed "THIS REVIEW WAS RUN
WITHOUT THE PAPER'S SUPPLEMENTARY MATERIAL" into the finished report, about the
file the operator had just supplied.

Same shape as the `--figures` defect (see `test_figures_flag_forwarded.py`): an
explicit operator instruction silently discarded at the call site. These tests
pin the two hops, plus the one that makes the hops worth taking -- the model has
no `Glob` and no `Bash`, so a path that is not interpolated into the prompt does
not exist as far as the review is concerned.
"""

import inspect

import pytest

import forensic_metascience_ai_toolkit.agent as agent_mod


class TestTheFlagIsForwarded:
    def test_cli_analyze_passes_extra_supplements_to_analyze_paper(self):
        src = inspect.getsource(
            __import__("forensic_metascience_ai_toolkit.cli", fromlist=["analyze"]))
        assert "extra_supplements=supplement" in src, (
            "cli.analyze must forward --supplement to analyze_paper; without it "
            "the flag only satisfies the gate"
        )

    def test_analyze_paper_accepts_them(self):
        params = inspect.signature(agent_mod.analyze_paper).parameters
        assert "extra_supplements" in params

class TestTheModelCannotFindFilesItself:
    """Why the inventory has to be computed in Python and named in the prompt.

    `--allowedTools` is an auto-approve list, not an allow-list, under
    `--permission-mode bypassPermissions`. The restriction is `--tools` +
    `--disallowedTools`, and it is load-bearing for integrity, not just cost: a
    real Opus sweep used `Bash` to hand-write scipy t-tests and GRIM-style
    reconstructions, bypassing every validated tool and guard. So no discovery
    tool can be handed to the model to solve this -- the orchestrator must name
    every path.
    """

    def test_there_is_no_directory_listing_tool(self):
        assert agent_mod.BUILTIN_TOOLS == ["Read"]
        for denied in ("Bash", "Task", "ToolSearch"):
            assert denied in agent_mod.DENIED_TOOLS

    def test_no_registered_tool_lists_a_directory(self):
        from forensic_metascience_ai_toolkit.registry import SPECS

        names = {s.name for s in SPECS}
        assert not (names & {"glob", "list_files", "list_dir", "ls"})


class TestSuppliedFilesAreClassifiedByTheReaderThatWillOpenThem:
    """Not by `agent._SI_READABLE`, which is a narrower hand-maintained copy.

    It lists `.xls`, which `supplements_read` deliberately removed because
    openpyxl cannot read the legacy binary format, and omits `.xlsm`, `.tsv`,
    `.txt` and `.epub`, which it can. A prompt that promises a read the reader
    refuses, or that drops a file the reader could have opened, is wrong in both
    directions -- and the second is silent.
    """

    @pytest.mark.parametrize("name,bucket", [
        ("etable.xlsx", "si_readable"),
        ("raw.tsv", "si_readable"),
        ("notes.txt", "si_readable"),
        ("book.epub", "si_readable"),
        ("macro.xlsm", "si_readable"),
        ("legacy.xls", "si_unreadable"),
        ("archive.zip", "si_unreadable"),
        ("source.tex", "si_unreadable"),
        ("old.doc", "si_unreadable"),
        ("appendix.pdf", "si_pdfs"),
    ])
    def test_each_format_reaches_the_bucket_its_reader_implies(
            self, tmp_path, name, bucket):
        d = tmp_path / "p"
        d.mkdir()
        (d / "body.md").write_text("# body")
        (d / "p.pdf").write_text("x")
        si = tmp_path / name
        si.write_text("x")
        sources = agent_mod._resolve_paper_sources(str(d), [si])
        assert getattr(sources, bucket) == [si.resolve()], (
            f"{name} landed somewhere other than {bucket}"
        )

    def test_nothing_is_dropped_on_the_floor(self, tmp_path):
        """A format in neither table is listed as unreadable, never omitted:
        "present but unreadable" and "not provided" are different facts."""
        d = tmp_path / "p"
        d.mkdir()
        (d / "body.md").write_text("# body")
        si = tmp_path / "data.sav"
        si.write_text("x")
        sources = agent_mod._resolve_paper_sources(str(d), [si])
        assert si.resolve() in sources.si_unreadable
