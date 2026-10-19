"""Reveal uses the viewer's verified archive and local folder mappings."""
from pathlib import Path

import pytest

from metascience_agent.workbench.service import Service
from tests.test_workbench_integration import source_catalog


@pytest.mark.usefixtures("image_package")
def test_archived_reference_selects_verified_named_copy_in_mapped_folder(tmp_path):
    c, archived = source_catalog(tmp_path)
    try:
        paper = tmp_path / 'external papers' / 'paper'; paper.mkdir(parents=True)
        local = paper / 'article.xml'; local.write_bytes(archived.read_bytes())
        c.map_paper('project', 'paper', paper)
        service = Service(c, background=False)
        result = service.handle('reveal_target', {'project': 'project', 'dir': 'paper', 'f': '__runs/r1/xml'})
        assert result['file'] == str(local)
        assert result['directory'] == str(paper)
        assert result['note'] is None
        assert service.handle('reveal_target', {'project': 'project', 'dir': 'paper'}) == {
            'directory': str(paper), 'file': None}
        assert service.handle('reveal_target', {'project': 'project', 'dir': 'paper', 'f': 'article.xml'})['file'] == str(local)
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
@pytest.mark.parametrize('state', ['changed', 'absent', 'symlink'])
def test_current_copy_cannot_replace_different_preserved_evidence(tmp_path, state):
    c, archived = source_catalog(tmp_path)
    try:
        paper = tmp_path / 'paper'; paper.mkdir()
        local = paper / 'article.xml'
        if state == 'changed': local.write_text('a different version')
        if state == 'symlink': local.symlink_to(archived)
        c.map_paper('project', 'paper', paper)
        s = Service(c, background=False)
        result = s.handle('reveal_target', {'project': 'project', 'dir': 'paper', 'f': '__runs/r1/xml'})
        assert Path(result['file']) == archived
        assert 'preserved source' in result['note']
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_missing_or_wrong_project_artifact_never_opens_unrelated_folder(tmp_path):
    c, archived = source_catalog(tmp_path)
    try:
        c.map_paper('project', 'paper', tmp_path)
        s = Service(c, background=False)
        for args in [
            {'project': 'other', 'dir': 'paper', 'f': '__runs/r1/xml'},
            {'project': 'project', 'dir': 'paper', 'f': '../outside'},
            {'project': 'project', 'dir': 'paper', 'f': '/etc/passwd'},
        ]:
            with pytest.raises((ValueError, LookupError, FileNotFoundError)):
                s.handle('reveal_target', args)
        archived.unlink()
        with pytest.raises(FileNotFoundError):
            s.handle('reveal_target', {'project': 'project', 'dir': 'paper', 'f': '__runs/r1/xml'})
    finally:
        c.close()
