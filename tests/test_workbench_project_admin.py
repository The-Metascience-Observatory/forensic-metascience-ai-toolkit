"""Landing-page Done / Delete: local to this machine, on real folders and SQLite."""
import json

import pytest

from metascience_agent.workbench import project_admin
from metascience_agent.workbench.catalog import Catalog
from metascience_agent.workbench.service import Service


@pytest.fixture
def setup(tmp_path):
    data = tmp_path / 'data' / 'collection'
    author = data / 'author_corpus'
    session = author / 'analysis_sessions' / 's1' / 'corpus'
    other = data / 'other_corpus'
    for d in (author / '10.1--a', session / '10.1--a', other / '10.1--b'):
        d.mkdir(parents=True)
        (d / 'paper.pdf').write_bytes(b'%PDF' + b'x' * 100)
    c = Catalog(tmp_path / 'cache' / 'cache.sqlite3')
    c.apply_changes([('corpora', json.dumps([i]), {'id': i, 'name': n}) for i, n in
                     enumerate(['author', 'author__s1', 'other', 'shared_only'], 1)], 1)
    c.register_root('author', author)
    c.register_root('author__s1', session)
    c.register_root('other', other)
    s = Service(c, background=False)
    yield s, c, data
    c.close()


def wait(job):
    thread = project_admin._jobs[job['project']]['thread']
    thread.join(10)
    return next(j for j in project_admin.jobs()['jobs'] if j['id'] == job['id'])


@pytest.fixture(autouse=True)
def fresh_jobs():
    project_admin._jobs.clear()
    yield
    project_admin._jobs.clear()


def names(s):
    return {p['name']: p for p in s.handle('projects', {})['projects']}


def test_done_is_a_local_flag_and_reversible(setup):
    s, c, _ = setup
    assert names(s)['other']['done'] is False
    s.handle('project_done', {'project': 'other', 'done': True})
    assert names(s)['other']['done'] is True  # the cached summary was invalidated
    s.handle('project_done', {'project': 'other', 'done': False})
    assert names(s)['other']['done'] is False


def test_plan_names_nested_projects_and_sizes_without_deleting(setup):
    s, c, data = setup
    plan = s.handle('project_delete_plan', {'project': 'author'})
    assert [f['path'] for f in plan['folders']] == [str(data / 'author_corpus')]
    assert plan['folders'][0]['files'] == 2 and plan['folders'][0]['measured']
    assert plan['also_removes'] == ['author__s1'] and plan['can_delete']
    assert (data / 'author_corpus').is_dir()


def test_delete_requires_the_name_then_removes_folder_and_hides_nested(setup):
    s, c, data = setup
    for unconfirmed in ('author', 'yes', None, 1):
        with pytest.raises(ValueError, match='not confirmed'):
            s.handle('project_delete', {'project': 'author', 'confirm': unconfirmed})
    assert (data / 'author_corpus').is_dir()
    job = wait(s.handle('project_delete', {'project': 'author', 'confirm': True}))
    assert job['state'] == 'done' and job['total'] == job['done'] == 2
    assert not (data / 'author_corpus').exists()
    assert (data / 'other_corpus').is_dir()
    shown = names(s)
    assert 'author' not in shown and 'author__s1' not in shown
    assert 'other' in shown and 'shared_only' in shown
    assert c.roots('author') == [] and c.roots('author__s1') == []


def test_deleting_a_nested_project_leaves_its_parent(setup):
    s, c, data = setup
    wait(s.handle('project_delete', {'project': 'author__s1', 'confirm': True}))
    assert not (data / 'author_corpus' / 'analysis_sessions' / 's1' / 'corpus').exists()
    assert (data / 'author_corpus' / '10.1--a' / 'paper.pdf').is_file()
    assert 'author' in names(s) and 'author__s1' not in names(s)


def test_protected_and_collection_folders_are_refused(setup, monkeypatch):
    s, c, data = setup
    c.register_root('whole', data)
    plan = s.handle('project_delete_plan', {'project': 'whole', 'protected': [str(data / 'other_corpus')]})
    assert not plan['can_delete'] and 'protected folder' in plan['refused'][0]['reason']
    with pytest.raises(ValueError, match='Refused'):
        s.handle('project_delete', {'project': 'whole', 'confirm': True,
                                    'protected': [str(data / 'other_corpus')]})
    monkeypatch.setattr(project_admin, 'MAX_ALSO_REMOVES', 1)
    plan = s.handle('project_delete_plan', {'project': 'whole'})
    assert not plan['can_delete'] and 'collection folder' in plan['refused'][0]['reason']
    assert data.is_dir() and (data / 'other_corpus' / '10.1--b').is_dir()


def test_symlinked_root_is_refused(setup, tmp_path):
    s, c, data = setup
    link = tmp_path / 'link'
    link.symlink_to(data / 'other_corpus')
    c.db.execute('insert into roots values(?,?)', ['linked', str(link)]); c.db.commit()
    plan = s.handle('project_delete_plan', {'project': 'linked'})
    assert plan['refused'][0]['reason'] == 'the registered folder is a symlink'


def test_a_project_without_a_local_folder_is_only_hidden(setup):
    s, c, _ = setup
    job = wait(s.handle('project_delete', {'project': 'shared_only', 'confirm': True}))
    assert job['state'] == 'done' and job['removed'] == [] and 'shared_only' not in names(s)


def test_a_deleted_project_reappears_when_its_folder_is_registered_again(setup):
    s, c, data = setup
    wait(s.handle('project_delete', {'project': 'other', 'confirm': True}))
    assert 'other' not in names(s)
    (data / 'other_corpus').mkdir()
    c.register_root('other', data / 'other_corpus')
    assert 'other' in names(s)


def test_a_name_registered_at_many_folders_is_refused(setup, tmp_path):
    s, c, data = setup
    for i in range(project_admin.MAX_FOLDERS + 1):
        (tmp_path / f'w{i}' / 'corpus').mkdir(parents=True)
        c.register_root('corpus', tmp_path / f'w{i}' / 'corpus')
    plan = s.handle('project_delete_plan', {'project': 'corpus'})
    assert not plan['can_delete'] and 'name collision' in plan['refused'][0]['reason']
    with pytest.raises(ValueError, match='Refused'):
        s.handle('project_delete', {'project': 'corpus', 'confirm': True})
    assert all((tmp_path / f'w{i}' / 'corpus').is_dir() for i in range(project_admin.MAX_FOLDERS + 1))


def test_a_failed_removal_keeps_the_project_listed_and_says_why(setup, monkeypatch):
    s, c, data = setup
    real = project_admin.os.unlink
    def refuse(path, *a, **k):
        if path.endswith('paper.pdf'): raise PermissionError('read-only')
        return real(path, *a, **k)
    monkeypatch.setattr(project_admin.os, 'unlink', refuse)
    job = wait(s.handle('project_delete', {'project': 'other', 'confirm': True}))
    assert job['state'] == 'failed' and 'PermissionError' in job['error']
    assert 'other' in names(s) and c.roots('other')


def test_a_second_request_while_running_returns_the_same_job(setup, monkeypatch):
    s, c, data = setup
    import threading
    gate = threading.Event()
    monkeypatch.setattr(project_admin, '_count', lambda folders: (gate.wait(5), 1)[1])
    first = s.handle('project_delete', {'project': 'other', 'confirm': True})
    again = s.handle('project_delete', {'project': 'other', 'confirm': True})
    assert again['id'] == first['id'] and s.handle('project_delete_jobs', {})['jobs'][0]['state'] == 'counting'
    gate.set()
    assert wait(first)['state'] == 'done'


def test_image_gate_corpora_are_never_deletable(setup, tmp_path, monkeypatch):
    """The gate's scratch corpus is registered as an ordinary project
    (`masliah_subset`); deleting it from the landing page would stop
    `metascience image-gate` from running at all."""
    s, c, data = setup
    config = tmp_path / 'gate.json'
    config.write_text(json.dumps({'masliah': {'corpus': str(data / 'other_corpus'),
                                              'labels': str(data / 'other_corpus' / 'labels.json')},
                                  'rsiid': {'limit': 40}}))
    monkeypatch.setattr(project_admin, 'GATE_CONFIG', config)
    plan = s.handle('project_delete_plan', {'project': 'other'})
    assert not plan['can_delete'] and 'image regression gate' in plan['refused'][0]['reason']
    with pytest.raises(ValueError, match='Refused'):
        s.handle('project_delete', {'project': 'other', 'confirm': True})
    assert (data / 'other_corpus' / '10.1--b' / 'paper.pdf').is_file()
