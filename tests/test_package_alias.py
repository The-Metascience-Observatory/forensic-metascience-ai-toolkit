"""`metascience_agent` is the old import name; it must keep working.

The package was renamed `forensic_metascience_ai_toolkit` in 1.96.1. Old
scripts, archived reproductions and recorded MCP commands still say
`metascience_agent`, so the alias must return the SAME module objects --
a second copy would duplicate module-level state (the tool registry,
caches, locks) and two halves of one process would disagree.
"""
import subprocess
import sys
import warnings

import forensic_metascience_ai_toolkit
import forensic_metascience_ai_toolkit.registry as registry
import forensic_metascience_ai_toolkit.tools.grim as grim


def _old(name):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import importlib
        return importlib.import_module(name)


def test_old_package_is_the_new_package():
    assert _old("metascience_agent") is forensic_metascience_ai_toolkit


def test_old_submodules_are_the_same_objects():
    assert _old("metascience_agent.registry") is registry
    assert _old("metascience_agent.tools.grim") is grim
    assert _old("metascience_agent.tools.grim").grim_test is grim.grim_test


def test_from_import_through_old_name():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from metascience_agent.tools.grim import grim_test
    assert grim_test is grim.grim_test


def test_unknown_old_submodule_still_fails():
    import pytest
    with pytest.raises(ModuleNotFoundError):
        _old("metascience_agent.no_such_module")


def test_python_dash_m_through_old_name():
    """Recorded commands run `python -m metascience_agent.X`."""
    out = subprocess.run(
        [sys.executable, "-W", "ignore::DeprecationWarning",
         "-m", "metascience_agent.cli", "--help"],
        capture_output=True, text=True, timeout=120)
    assert out.returncode == 0, out.stderr[-2000:]
    assert "Usage" in out.stdout
