"""`metascience batch` must build an `args` the batch runner can actually read.

FOUND 2026-08-19, on an eleven-paper run that had already been priced and
authorised: every paper failed with

    'Namespace' object has no attribute 'image_forensics'

before a single API call. `metascience_agent/batch.py` reads `args` as though
argparse had built it; `cli.batch` hand-builds a `Namespace` and five fields
were missing. The command whose docstring says "One command, fully automated"
could not analyse anything at all, on `origin/main`, and the suite was green.

It was green because every test of this command either dry-runs or monkeypatches
`run_batch`, so nothing ever asked whether the object handed across that seam
carries what the other side reads. This test asks exactly that, statically, so
it costs nothing and cannot be satisfied by a mock.
"""

import ast
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RUNNER = REPO / "src" / "metascience_agent" / "batch.py"
CLI = REPO / "src" / "metascience_agent" / "cli.py"


def _read_off_args(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {n.attr for n in ast.walk(tree)
            if isinstance(n, ast.Attribute)
            and isinstance(n.value, ast.Name)
            and n.value.id == "args"}


def _supplied_by_cli(path: Path) -> set[str]:
    m = re.search(r"args = Namespace\((.*?)\n    \)", path.read_text(encoding="utf-8"),
                  re.S)
    assert m, "cli.batch no longer builds `args = Namespace(...)`; update this test"
    return set(re.findall(r"(\w+)\s*=", m.group(1)))


@pytest.mark.skipif(not RUNNER.is_file(), reason="batch runner not in this checkout")
def test_every_field_the_runner_reads_is_supplied():
    needed = _read_off_args(RUNNER)
    supplied = _supplied_by_cli(CLI)
    missing = sorted(needed - supplied)
    assert not missing, (
        f"`metascience batch` will raise AttributeError on: {missing}. "
        "The runner reads these off `args` and cli.batch does not set them.")


@pytest.mark.skipif(not RUNNER.is_file(), reason="batch runner not in this checkout")
def test_the_two_track_flags_match_what_analyze_does():
    """Not merely present -- the same values, or the two entry points quietly
    disagree about which deterministic tracks ran."""
    supplied = re.search(r"args = Namespace\((.*?)\n    \)",
                         CLI.read_text(encoding="utf-8"), re.S).group(1)
    assert re.search(r"image_forensics\s*=\s*image_forensics", supplied), (
        "batch must forward its image-forensics option to the runner")
    assert re.search(r"text_forensics\s*=\s*True", supplied), (
        "the text track is free, local and on by default in `analyze`")
