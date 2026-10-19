"""Image-queue columns and orderings, shared by the local and shared queues.

Pure functions of one item record. They lived in the host's
`workbench/repository.py`; the host re-exports them from there.
"""
from __future__ import annotations

from pathlib import Path


def run_time(run):
    return str(run.get('analysed_at') or (run.get('history_record') or {}).get('completed_at') or (run.get('history_record') or {}).get('started_at') or '')



def judgment_decision(item):
    decision = (item.get('screening') or {}).get('decision')
    if decision:
        return decision
    if item.get('cleared'):
        return 'automatic_clearance'
    # Detection-only runs have no screening object. Absence is not a legacy
    # judgment; that category requires an actual saved adjudicator verdict.
    return 'legacy' if (item.get('adjudication') or {}).get('verdict') else 'missing'


def _folder_search_forms(raw):
    """The paper-column string and the slash/dash DOI spellings of its basename."""
    text = str(raw or '').strip()
    if not text:
        return ()
    name = Path(text).name or text
    return (text, name, text.replace('--', '/'), name.replace('--', '/'),
            text.replace('/', '--'), name.replace('/', '--'))


def matches_paper_folder(item, q):
    """Substring match on the folder shown in the queue's Paper column.

    A DOI pasted with a slash still hits the `--` directory name. Empty or
    whitespace is the absence of a filter, never a match against every folder.
    """
    needle = str(q or '').strip().lower()
    if not needle:
        return True
    dirs = []
    paper = item.get('paper') or {}
    if isinstance(paper, dict) and paper.get('dir'):
        dirs.append(paper['dir'])
    for extra in item.get('papers') or []:
        if isinstance(extra, dict) and extra.get('dir'):
            dirs.append(extra['dir'])
    for panel in item.get('panels') or []:
        if isinstance(panel, dict) and panel.get('paper_dir'):
            dirs.append(panel['paper_dir'])
    seen = set()
    for raw in dirs:
        if raw in seen:
            continue
        seen.add(raw)
        if any(needle in form.lower() for form in _folder_search_forms(raw)):
            return True
    return False


def paper_column(item):
    """The string the queue shows in the Paper column, used as the sort key."""
    if item.get('kind') == 'cross':
        dirs = [str(p.get('dir') or '') for p in (item.get('papers') or []) if isinstance(p, dict)]
        dirs = [d for d in dirs if d]
        if dirs:
            return ' ~ '.join(dirs)
    paper = item.get('paper') or {}
    return str(paper.get('dir') or '')


def sort_feed_items(rows, sort=None, direction=None):
    """Order the filtered queue before pagination.

    Default is the triage rule (`triage_rank.sort_key`: cleared and measured
    lookalikes last, then verdict tier, score and inliers), then id. `paper` is the folder shown in
    the Paper column; within one folder the score order is kept (stable).
    An unknown key or direction is the default, never a second ordering.
    """
    key = str(sort or 'triage').strip().lower()
    if key not in ('triage', 'score', 'paper', 'decision'):
        key = 'triage'
    dirn = str(direction or '').strip().lower()
    if dirn not in ('asc', 'desc'):
        dirn = 'desc' if key == 'score' else 'asc'
    rows.sort(key=lambda i: str(i.get('id') or ''))
    if key == 'triage':
        # The shared triage rule (`triage_rank.sort_key`), as the local queue.
        from ..image_plugin import load
        sort_value = load("image_forensics.triage_rank").sort_value
        rows.sort(key=lambda i: sort_value(i.get('rank') or {}), reverse=(dirn == 'desc'))
        return rows
    if key == 'decision':
        # Same order as the local queue (`LocalImages.DECISION_RANK`);
        # undecided rows stay last in both directions.
        rank = {'true_issue': 0, 'unsure': 1, 'conflict': 2, 'false_positive': 3}
        def value(i):
            d = i.get('decision')
            if d:
                return d.get('decision') or ''
            return 'conflict' if (i.get('reviews') or {}).get('conflict') else None
        rows.sort(key=lambda i: float((i.get('rank') or {}).get('score') or 0), reverse=True)
        decided = [i for i in rows if value(i) is not None]
        decided.sort(key=lambda i: (rank.get(value(i), 4), value(i)), reverse=(dirn == 'desc'))
        rows[:] = decided + [i for i in rows if value(i) is None]
    elif key == 'paper':
        rows.sort(key=lambda i: float((i.get('rank') or {}).get('score') or 0), reverse=True)
        rows.sort(key=lambda i: paper_column(i).lower(), reverse=(dirn == 'desc'))
    else:
        rows.sort(key=lambda i: float((i.get('rank') or {}).get('score') or 0), reverse=(dirn != 'asc'))
    return rows


def adjudicator_output(item):
    """Match the queue's displayed judgment, including legacy and absent results."""
    decision = judgment_decision(item)
    if decision == 'automatic_clearance':
        return 'Automatically cleared — AI not needed'
    if decision == 'missing':
        return 'No saved AI judgment'
    screen = item.get('screening')
    if screen and screen.get('decision'):
        return f"Saved AI judgment: {screen['decision']} · {screen.get('confidence') or 'confidence unavailable'}"
    if item.get('cleared'):
        return 'cleared'
    adjudication = item.get('adjudication') or {}
    verdict = adjudication.get('verdict')
    if not verdict:
        return 'not adjudicated'
    category = adjudication.get('category')
    return f'{verdict} · {category}' if category and category != 'none' else verdict
