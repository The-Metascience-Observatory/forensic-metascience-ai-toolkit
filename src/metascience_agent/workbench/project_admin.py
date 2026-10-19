"""Landing-page project housekeeping on THIS machine: mark done, and delete.

Both are local. The project list comes from the shared database, and neither
action touches it: "done" is a reviewer's bookkeeping, and "delete" removes the
project's folder(s) from this disk and hides the project here. Other machines
and reviewers still see the shared records (Dan, 2026-09-26).

Delete is two-step. `delete_plan` names every folder that would go, how big it
is, which OTHER projects live inside it (an author corpus holds its
`analysis_sessions/*/corpus` projects), and every folder it refuses to touch;
`start_delete` re-derives the same plan, requires an explicit yes, and removes
the files in a background thread whose file-level progress `jobs` reports. A refusal blocks the whole delete: a partial delete of a project
reads as a clean deletion and leaves the rest orphaned.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import threading
import time
import uuid

from .catalog import encode, now

#: Stop measuring a folder after this long; the plan then says "at least".
SIZE_BUDGET_SECONDS = 4.0


#: A folder whose removal would take more than this many OTHER projects with
#: it is a collection directory registered by mistake, not a project.
MAX_ALSO_REMOVES = 10

#: A project name registered at more folders than this is a name collision,
#: not one corpus: on 2026-09-26 the name `corpus` (a run work directory's
#: basename) held 1,871 roots across every author corpus on this machine.
MAX_FOLDERS = 3


def flags(catalog):
    rows = catalog.reader.execute('select project,body from project_flags').fetchall()
    return {p: json.loads(b) for p, b in rows}


def _set(catalog, project, **fields):
    with catalog.lock, catalog.db:
        row = catalog.db.execute('select body from project_flags where project=?', [project]).fetchone()
        body = {**(json.loads(row[0]) if row else {}), **fields}
        catalog.db.execute('insert or replace into project_flags values(?,?)', [project, encode(body)])
    return body


def mark_done(catalog, project, done=True):
    if not project:
        raise ValueError('A project name is required')
    return {'project': project, **_set(catalog, project, done=bool(done), done_at=now() if done else None)}


def apply_flags(catalog, result):
    """Drop deleted projects from the landing-page summary and mark done ones.

    A deleted project whose folder is registered again (a new sweep wrote it
    back) reappears: the deletion hid the files that were removed, not the name.
    """
    marks = flags(catalog)
    rooted = {r['project'] for r in catalog.roots() if r['available']}
    rows = []
    for row in result['projects']:
        mark = marks.get(row['name'], {})
        if mark.get('deleted_at') and row['name'] not in rooted:
            continue
        rows.append({**row, 'done': bool(mark.get('done')), 'done_at': mark.get('done_at')})
    return {**result, 'projects': rows, 'n_projects': len(rows),
            'n_papers': sum(r['n_papers'] for r in rows)}


def _inside(path, base):
    return path == base or base in path.parents


def _measure(path, deadline):
    files = size = 0
    stack = [path]
    while stack:
        if time.monotonic() > deadline:
            return files, size, False
        try:
            with os.scandir(stack.pop()) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        else:
                            files += 1
                            size += entry.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return files, size, True


#: Every absolute path the image regression gate reads. The gate's corpora are
#: scratch copies registered under ordinary project names (`masliah_subset`),
#: so a landing-page delete could otherwise wipe what `metascience image-gate`
#: needs to run at all.
GATE_CONFIG = Path(__file__).resolve().parents[3] / 'eval' / 'gate' / 'config.json'


def _gate_paths(config=None):
    try:
        obj = json.loads(Path(config or GATE_CONFIG).read_text())
    except (OSError, ValueError):
        return set()
    found, stack = set(), [obj]
    while stack:
        x = stack.pop()
        if isinstance(x, dict):
            stack.extend(x.values())
        elif isinstance(x, list):
            stack.extend(x)
        elif isinstance(x, str) and x.startswith('/'):
            found.add(Path(x))
    return found


def _guarded(catalog, protected):
    """Folders a project delete may never remove, nor any folder containing
    them, each with the reason a refusal should name."""
    repo = Path(__file__).resolve().parents[3]
    guarded = {Path('/'): 'protected folder', Path.home().resolve(): 'protected folder',
               repo: 'protected folder', catalog.path.parent.resolve(): 'protected folder'}
    for p in _gate_paths():
        guarded.setdefault(p.expanduser().resolve(), f'used by the image regression gate ({GATE_CONFIG.name})')
    for p in protected or []:
        if p:
            guarded.setdefault(Path(p).expanduser().resolve(), 'protected folder')
    return guarded


def delete_plan(catalog, project, protected=()):
    if not project:
        raise ValueError('A project name is required')
    roots = catalog.roots(project)
    if not roots and catalog.discover_root(project):
        roots = catalog.roots(project)
    guarded = _guarded(catalog, protected)
    if len(roots) > MAX_FOLDERS:
        # Name a gate corpus among them first: that is the refusal that matters.
        gate = [{'path': r['path'], 'reason': f'contains {g}: {why}'} for r in roots
                for g, why in guarded.items()
                if why.startswith('used by') and _inside(g, Path(r['path']).resolve())]
        return {'project': project, 'folders': [], 'missing': [], 'kept_mapped_papers': 0,
                'also_removes': [], 'partly_affects': [], 'can_delete': False,
                'refused': gate + [{'path': f'{len(roots)} registered folders',
                             'reason': f'this name is registered at {len(roots)} separate folders, '
                                       'which is a name collision, not one project; delete them by hand'}]}
    others = [r for r in catalog.roots() if r['project'] != project]
    folders, refused, missing = [], [], []
    deadline = time.monotonic() + SIZE_BUDGET_SECONDS
    for root in roots:
        raw = Path(root['path'])
        if not raw.exists():
            missing.append(str(raw))
            continue
        path = raw.resolve()
        if raw.is_symlink() or str(path) != str(raw):
            refused.append({'path': str(raw), 'reason': 'the registered folder is a symlink'})
            continue
        if not path.is_dir():
            refused.append({'path': str(raw), 'reason': 'not a directory'})
            continue
        hit = next((g for g in guarded if _inside(g, path)), None)
        if hit is not None:
            refused.append({'path': str(path), 'reason': f'contains {hit}: {guarded[hit]}'})
            continue
        if len(path.parts) < 4:
            refused.append({'path': str(path), 'reason': 'too close to the filesystem root'})
            continue
        contained = sorted({o['project'] for o in others if _inside(Path(o['path']), path)})
        within = sorted({o['project'] for o in others if _inside(path, Path(o['path'])) and Path(o['path']) != path})
        files, size, complete = _measure(path, deadline)
        folders.append({'path': str(path), 'files': files, 'bytes': size, 'measured': complete,
                        'also_removes': contained, 'inside_project': within})
    gone = [Path(f['path']) for f in folders]
    by_project = {}
    for o in others:
        by_project.setdefault(o['project'], []).append(Path(o['path']))
    touched = {p for f in folders for p in f['also_removes']}
    # Hidden with this project only when EVERY folder of theirs goes too.
    also = sorted(p for p in touched if all(any(_inside(r, g) for g in gone) for r in by_project[p]))
    partly = sorted(touched - set(also))
    if len(also) > MAX_ALSO_REMOVES:
        refused.append({'path': ', '.join(map(str, gone)),
                        'reason': f'would also remove {len(also)} other projects; '
                                  'this looks like a collection folder, not a project'})
    mapped = [path for _p, _d, _b, path in catalog.local_papers(project)
              if path and not any(_inside(Path(path), g) for g in gone)]
    return {'project': project, 'folders': folders, 'refused': refused, 'missing': missing,
            'kept_mapped_papers': len(mapped), 'also_removes': also, 'partly_affects': partly,
            'can_delete': not refused}


def _count(folders):
    total = 0
    for folder in folders:
        for _root, _dirs, files in os.walk(folder):
            total += len(files)
    return total


def _remove(folders, job):
    """Bottom-up removal that reports each file, so a large corpus shows progress."""
    removed, failed = [], []
    for folder in folders:
        errors = []
        for root, dirs, files in os.walk(folder, topdown=False):
            for name in files:
                try:
                    os.unlink(os.path.join(root, name))
                except OSError as exc:
                    errors.append(f'{type(exc).__name__}: {exc}')
                job['done'] += 1
            for name in dirs:
                path = os.path.join(root, name)
                try:
                    os.unlink(path) if os.path.islink(path) else os.rmdir(path)
                except OSError as exc:
                    errors.append(f'{type(exc).__name__}: {exc}')
        try:
            os.rmdir(folder)
        except OSError as exc:
            errors.append(f'{type(exc).__name__}: {exc}')
        if errors:
            failed.append({'path': folder, 'reason': f'{len(errors)} error(s); first: {errors[0]}'})
        else:
            removed.append(folder)
    return removed, failed


def _finalize(catalog, project, plan, removed):
    stamp = now()
    for name in [project, *plan['also_removes']]:
        _set(catalog, name, deleted_at=stamp, deleted_paths=removed if name == project else [],
             deleted_with=None if name == project else project)
    gone = [Path(p) for p in removed]
    with catalog.lock, catalog.db:
        for name in [project, *plan['also_removes']]:
            catalog.db.execute('delete from roots where project=?', [name])
            catalog.db.execute('delete from papers_local where project=?', [name])
        # A partly affected project keeps its other folders, not the removed ones.
        for name, root in catalog.db.execute('select project,path from roots').fetchall():
            if any(_inside(Path(root), g) for g in gone):
                catalog.db.execute('delete from roots where project=? and path=?', [name, root])
    return stamp


def _checked_plan(catalog, project, confirm, protected):
    if confirm is not True:
        raise ValueError('Deletion was not confirmed')
    plan = delete_plan(catalog, project, protected)
    if plan['refused']:
        raise ValueError('Refused: ' + '; '.join(f"{r['path']}: {r['reason']}" for r in plan['refused']))
    return plan


def _run(catalog, job, plan):
    try:
        folders = [f['path'] for f in plan['folders']]
        job['total'] = _count(folders)
        job['state'] = 'deleting'
        job['deleting_since'] = time.time()
        removed, failed = _remove(folders, job)
        job.update(removed=removed, failed=failed)
        if failed:
            # Nothing is hidden: a project whose files are half gone must stay visible.
            job['state'] = 'failed'
            job['error'] = '; '.join(f"{f['path']}: {f['reason']}" for f in failed)
        else:
            job['deleted_at'] = _finalize(catalog, job['project'], plan, removed)
            job['state'] = 'done'
    except Exception as exc:  # A dead thread must not leave a job reading "deleting" forever.
        job['state'] = 'failed'
        job['error'] = f'{type(exc).__name__}: {exc}'
    job['finished_at'] = time.time()


#: Jobs live in the service process. A restart mid-delete leaves the project
#: listed with whatever files remain, and deleting it again resumes the work.
_jobs = {}
_jobs_lock = threading.Lock()
_ACTIVE = ('counting', 'deleting')
#: Finished jobs stay reportable this long, so a page opened afterwards still says so.
KEEP_FINISHED_SECONDS = 600


def start_delete(catalog, project, confirm, protected=()):
    with _jobs_lock:
        job = _jobs.get(project)
        if job and job['state'] in _ACTIVE:
            return dict(job)
    plan = _checked_plan(catalog, project, confirm, protected)
    job = {'id': uuid.uuid4().hex, 'project': project, 'state': 'counting', 'total': 0, 'done': 0,
           'folders': [f['path'] for f in plan['folders']], 'also_removes': plan['also_removes'],
           'started_at': time.time(), 'error': None}
    with _jobs_lock:
        current = _jobs.get(project)
        if current and current['state'] in _ACTIVE:
            return dict(current)
        _jobs[project] = job
    job['thread'] = threading.Thread(target=_run, args=(catalog, job, plan), daemon=True,
                                     name=f'delete:{project}')
    job['thread'].start()
    return {k: v for k, v in job.items() if k != 'thread'}


def jobs():
    cutoff = time.time() - KEEP_FINISHED_SECONDS
    with _jobs_lock:
        for name in [n for n, j in _jobs.items() if j.get('finished_at', time.time()) < cutoff]:
            del _jobs[name]
        out = [{k: v for k, v in j.items() if k != 'thread'} for j in _jobs.values()]
    now_s = time.time()
    for j in out:
        j['elapsed'] = (j.get('finished_at') or now_s) - j['started_at']
    return {'jobs': sorted(out, key=lambda j: j['started_at'])}


def delete(catalog, project, confirm, protected=()):
    """Synchronous delete: the same plan, removal and bookkeeping as a job."""
    plan = _checked_plan(catalog, project, confirm, protected)
    job = {'project': project, 'done': 0}
    removed, failed = _remove([f['path'] for f in plan['folders']], job)
    if failed:
        return {**plan, 'removed': removed, 'failed': failed, 'deleted': False}
    stamp = _finalize(catalog, project, plan, removed)
    return {**plan, 'removed': removed, 'failed': [], 'deleted': True, 'deleted_at': stamp}
