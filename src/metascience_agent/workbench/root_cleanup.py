"""Remove polluted `roots` rows from the local workbench caches. Dry run by default.

Two kinds of row are removed, and nothing else is touched -- no folder on disk,
no other table, nothing in the shared database:

  pytest      a root under a pytest temporary folder (`/tmp/pytest-of-<user>/`).
              Tests notified the operator's real cache before
              `tests/conftest.py` pointed it at a tmp file.
  collision   a root registered under a folder's basename (`corpus`, `project`)
              by the producer notification. A run workspace
              (`.analysis_runs/work/<run>/corpus`) is dropped outright; an
              author session corpus is re-registered under its real name
              (`catalog.project_for_root`) unless that row already exists.

    python -m metascience_agent.workbench.root_cleanup            # list counts
    python -m metascience_agent.workbench.root_cleanup --apply    # delete them
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3
import tempfile

from .catalog import cache_path, project_for_root

COLLISION_NAMES = ('corpus', 'project')


def _pytest_tmp(path):
    parts = Path(path).parts
    tmp = Path(tempfile.gettempdir()).parts
    return parts[:len(tmp)] == tmp and len(parts) > len(tmp) and parts[len(tmp)].startswith('pytest-of-')


def plan(db):
    rows = db.execute('select project,path from roots').fetchall()
    existing = set(rows)
    remove, add = [], []
    for project, path in rows:
        if _pytest_tmp(path):
            remove.append(('pytest', project, path))
        elif project in COLLISION_NAMES and project == Path(path).name:
            remove.append(('collision', project, path))
            real = project_for_root(path)
            if real and real != project and (real, path) not in existing:
                add.append((real, path))
                existing.add((real, path))
    return remove, add


def run(path, apply=False):
    path = Path(path)
    if not path.is_file():
        return {'db': str(path), 'state': 'absent'}
    db = sqlite3.connect(path, timeout=30)
    db.execute('pragma busy_timeout=30000')
    remove, add = plan(db)
    report = {
        'db': str(path),
        'roots_before': db.execute('select count(*) from roots').fetchone()[0],
        'remove': dict(Counter(kind for kind, _, _ in remove)),
        'remove_by_project': dict(Counter(p for _, p, _ in remove).most_common(15)),
        'reregister': [{'project': p, 'path': r} for p, r in add],
        'applied': False,
    }
    if apply:
        with db:
            db.executemany('insert or ignore into roots values(?,?)', add)
            db.executemany('delete from roots where project=? and path=?', [(p, r) for _, p, r in remove])
        report['applied'] = True
        report['roots_after'] = db.execute('select count(*) from roots').fetchone()[0]
    db.close()
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--apply', action='store_true', help='Delete the listed rows (default: dry run)')
    parser.add_argument('--db', action='append', help='Cache file(s); default: the workbench and image-review caches')
    args = parser.parse_args(argv)
    default = [cache_path()]
    from ..image_plugin import available
    if available():
        from .image_review_host import load
        default.append(load("local_images").image_path())
    for path in args.db or default:
        print(json.dumps(run(path, args.apply), indent=1))


if __name__ == '__main__':
    main()
