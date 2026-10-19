"""Best-effort local producer notification, with a polling fallback in the service."""
import sqlite3

from .catalog import cache_path, is_run_workspace


def _notify(db_path, root):
    with sqlite3.connect(db_path, timeout=.1) as conn:
        conn.execute('insert or replace into notifications values(?)', [str(root)])


def register_shared(root):
    """Tell the shared workbench (the landing page's project list) about a
    corpus root. Idempotent; the shared service registers the folder and scans
    its papers. Every path that imports image results calls this, so a project
    with results is never missing from the landing page (2026-09-30: Yadong
    Huang's were imported but unlisted)."""
    if is_run_workspace(root):
        # A run's private workspace copy; its results reach the real corpus
        # through the archive, and registering it made a project per run.
        return {'state': 'run_workspace_ignored'}
    path = cache_path()
    if not path.exists():
        return {'state': 'workbench_not_initialized'}
    try:
        _notify(path, root)
        return {'state': 'notified'}
    except sqlite3.Error as exc:
        # A notification is an optimization; bounded root reconciliation remains active.
        return {'state': 'polling_fallback', 'detail': str(exc)}


def published(root):
    # Wake the durable local image worker without importing its service or
    # creating a second copy of the analysis package. Standalone publication
    # journals remain the recovery path when the host is absent.
    if is_run_workspace(root):
        return {'state': 'run_workspace_ignored'}
    from ..image_plugin import available
    if not available():
        # No image package, no local image worker to wake.
        return register_shared(root)
    from .image_review_host import load
    local = load("local_images").image_path()
    if local.exists():
        try:
            _notify(local, root)
        except sqlite3.Error:
            # The journal is durable; the next root reconciliation retries.
            pass
    return register_shared(root)
