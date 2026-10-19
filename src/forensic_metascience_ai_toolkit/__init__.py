"""
Forensic Metascience AI Toolkit

AI tools for detecting statistical inconsistencies, image reuse and other anomalies in scientific papers.
Based on techniques from James Heathers' "Introduction to Forensic Metascience".
"""

# Re-exported, not defined here. `version.py` is the single source of truth and
# `pyproject.toml` reads the same literal via hatchling, so the number cannot
# drift between the installed package and the code. It used to be declared in
# both files independently.
from .version import NOT_RECORDED, __version__, git_state, pipeline_version

__all__ = ["__version__", "pipeline_version", "git_state", "NOT_RECORDED"]
