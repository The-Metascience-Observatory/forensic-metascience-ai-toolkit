"""Small helpers shared by the review workbench's SQLite stores.

They used to live in the host's `workbench/catalog.py`; the host re-exports
them from there, so both stores name one implementation.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


#: WAL bytes kept after a checkpoint resets it (SQLite truncates down to it).
WAL_LIMIT = 64 * 1024 * 1024


def now():
    return datetime.now(timezone.utc).isoformat()


def encode(value):
    return json.dumps(value, default=str, ensure_ascii=False)


def cache_path():
    if os.environ.get('METASCIENCE_WORKBENCH_DB'):
        return Path(os.environ['METASCIENCE_WORKBENCH_DB']).expanduser()
    if sys.platform == 'win32':
        base = Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData/Local'))
    elif sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    else:
        base = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    return base / 'metascience/workbench.sqlite3'


def is_run_workspace(root):
    """A private analysis workspace (`.analysis_runs/work/<run>/corpus`) is a
    copy made for one run, never a project a reviewer browses."""
    return '.analysis_runs' in Path(root).parts


def project_for_root(root, roots=()):
    """The project name a notified folder is registered under, or None.

    A folder's basename is not its project name: an author corpus's session
    `<author>/analysis_sessions/<session>/corpus` is `<author>__<session>`
    (the rule `webapp_index` lists it under), and naming it `corpus` put
    1,870 unrelated folders under one project on 2026-09-26. `roots` is the
    catalog's existing rows; a folder already registered keeps its name."""
    root = Path(root)
    if is_run_workspace(root):
        return None
    if root.name == 'corpus' and root.parent.parent.name == 'analysis_sessions':
        return f'{root.parent.parent.parent.name}__{root.parent.name}'
    mapped = next((r['project'] for r in roots if Path(r['path']) == root), None)
    return mapped or root.name


def db_primary_key(database_record):
    """SQL envelope primary key; unrelated to the v2 record's finding_id."""
    return database_record['id']


def page(rows, args):
    offset = max(0,int(args.get('offset') or 0))
    limit = max(1,min(100,int(args.get('limit') or 50)))
    return rows[offset:offset+limit],dict(offset=offset,limit=limit,total=len(rows),
                                       next_offset=offset+limit if offset+limit<len(rows) else None)


def component(run):
    return run.get('component') or {'full_review':'comprehensive','legacy':'comprehensive',
                                  'image_track':'image_forensics','copy_paste':'copy_paste'}.get(run.get('kind'),run.get('kind'))


def run_pipeline(run):
    """What a run's pipeline was, in words a reviewer can read, or None.

    A partial pipeline (`tools_only`: tools agent alone, no adjudicator) is
    never the paper's review, and its severities are the analyst's own,
    unadjudicated ones -- so a run picker that names it only by version and
    date lets a reviewer read provisional rows as a complete review. Returns
    {'name', 'complete_review', 'label'}; the label is e.g. "tools only ·
    provisional". A complete review under the default pipeline (or a run
    that predates pipelines) returns None: there is nothing extra to say.
    A partial run whose record has lost the pipeline block still says it is
    partial -- the component is authority enough for that.
    """
    params = (((run.get('history_record') or {}).get('provenance') or {}).get('parameters') or {})
    block = params.get('pipeline') if isinstance(params.get('pipeline'), dict) else {}
    partial = component(run) == 'partial_review' or block.get('complete_review') is False
    name = block.get('name')
    if not partial and name in (None, 'full'):
        return None
    words = str(name).replace('_', ' ') if name else 'partial pipeline'
    return {'name': name, 'complete_review': not partial,
            'label': words + (' · provisional' if partial else '')}
