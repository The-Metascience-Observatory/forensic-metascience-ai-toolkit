"""Paper folders sorted into grouping folders of a project root.

The 2026-11-17 RNG triage moved 36 of rng_europepmc_screen_pdfs's 54 paper
folders into `likely_innocent/` and `screen_artefacts/`. The catalog still
held each folder's old top-level path, so the papers table showed their
folder names instead of their titles, and the review page could not reach
their files. A recorded paper is now also found one level down, by exact
folder name, when exactly one grouping folder holds it."""
import json

import pytest

from forensic_metascience_ai_toolkit.workbench.catalog import (
    Catalog, grouped_paper_folder, grouped_paper_folders)
from forensic_metascience_ai_toolkit.workbench.repository import Repository


def _paper(folder, title):
    folder.mkdir(parents=True)
    (folder / 'metadata.json').write_text(json.dumps({'title': title}), encoding='utf-8')


def test_finds_a_paper_one_level_down_by_exact_name(tmp_path):
    _paper(tmp_path / 'screen_artefacts' / '10.1--a', 'A')
    _paper(tmp_path / 'top', 'Top')
    assert grouped_paper_folder(tmp_path, '10.1--a') == tmp_path / 'screen_artefacts' / '10.1--a'
    for bad in ('10.1', 'top', 'screen_artefacts/10.1--a', '..', '.', ''):
        assert grouped_paper_folder(tmp_path, bad) is None
    assert grouped_paper_folders(tmp_path) == {'10.1--a': tmp_path / 'screen_artefacts' / '10.1--a'}


def test_a_name_in_two_groups_is_ambiguous(tmp_path):
    _paper(tmp_path / 'g1' / 'p', 'one')
    _paper(tmp_path / 'g2' / 'p', 'two')
    assert grouped_paper_folder(tmp_path, 'p') is None
    assert grouped_paper_folders(tmp_path) == {}


def test_symlinked_group_is_not_followed(tmp_path):
    _paper(tmp_path / 'outside' / 'p', 'P')
    (tmp_path / 'root').mkdir()
    (tmp_path / 'root' / 'g').symlink_to(tmp_path / 'outside')
    assert grouped_paper_folder(tmp_path / 'root', 'p') is None
    assert grouped_paper_folders(tmp_path / 'root') == {}


def test_known_and_paper_folders_are_not_entered(tmp_path):
    _paper(tmp_path / 'known' / 'sub', 'x')       # a known paper's own subfolder
    _paper(tmp_path / 'paperish', 'y')            # holds metadata.json: a paper
    (tmp_path / 'paperish' / 'forensic_review').mkdir()
    assert grouped_paper_folders(tmp_path, skip={'known'}) == {}


def test_paper_path_and_titles_follow_a_moved_folder(tmp_path):
    root = tmp_path / 'project'
    _paper(root / 'stays', 'Stays put')
    _paper(root / 'moves', 'Was moved')
    c = Catalog(tmp_path / 'cache.sqlite3')
    try:
        c.register_root('project', root)
        for d in ('stays', 'moves'):
            c.map_paper('project', d, root / d)
        # The triage sort moves one folder after it was recorded.
        (root / 'screen_artefacts').mkdir()
        (root / 'moves').rename(root / 'screen_artefacts' / 'moves')
        assert c.paper_path('project', 'moves') == root / 'screen_artefacts' / 'moves'
        assert c.paper_path('project', 'stays') == root / 'stays'
        # A folder the project does not record is still refused.
        (root / 'screen_artefacts' / 'unrecorded').mkdir()
        with pytest.raises(ValueError, match='Invalid paper directory'):
            c.paper_path('project', 'unrecorded')
        repo = Repository(c)
        repo.refresh('project', 'latest', None)
        rows = repo.papers_page({'project': 'project', 'limit': 10, 'offset': 0})['papers']
        assert {r['dir']: r.get('title') for r in rows} == {'stays': 'Stays put', 'moves': 'Was moved'}
    finally:
        c.close()
