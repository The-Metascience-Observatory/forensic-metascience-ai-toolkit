"""Hooks shared by the toolkit and the optional image analysis package.

These were host hooks the image package's copy of the general modules read,
set by `image_integration.configure()` at import. The general modules now live
in the toolkit, so the values are the toolkit's own and are set here; the image
package's `integration` module is an alias of this one, so both read the same
values. Tests may still monkeypatch them.
"""
from pathlib import Path


def notify_published(root):
    from .workbench.notifications import published as notify
    return notify(root)


def refresh_index(project):
    from .webapp_index import refresh_image_project_index
    return refresh_image_project_index(project)


def forensic_tool_names():
    from .registry import SPECS
    return [s.name for s in SPECS]


def metadata_provenance():
    from .version import __version__, git_state
    return {"version": __version__, **git_state()}


#: Repo root `.env` only (two levels above `src/metascience_agent`), never the
#: cwd: a paper corpus must not be able to plant a `.env`.
default_env_file = Path(__file__).resolve().parents[2] / ".env"
forensic_source_root = Path(__file__).resolve().parents[1]
#: The forensic MCP server, as a `python -m` module name.
forensic_mcp_module = "metascience_agent.mcp_server"


def published(root, run=None):
    """Journal exact sealed runs; notification failure cannot erase an archive."""
    journal_error = None
    if run and run.get("component") == "image_forensics":
        import json
        import os
        from pathlib import Path
        path = Path(root) / ".analysis_runs" / "review_publications.jsonl"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a") as stream:
                stream.write(json.dumps({"run": run["id"], "digest": run.get("sealed_digest")}) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            journal_error = str(exc)  # The sealed manifest is the durable fallback.
    result = ({"state": "standalone", "detail": "Workbench refreshes through its normal polling."}
              if notify_published is None else notify_published(root))
    if journal_error:
        result = {**result, "state": "polling_fallback", "journal_error": journal_error}
    return result


def refresh_project_index(project):
    if refresh_index is None:
        return {"updated": False, "reason": "Standalone output uses the existing database/artifact contracts."}
    return refresh_index(project)
