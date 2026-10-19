import pytest

pytest.importorskip("metascience_observatory_image_analysis", reason="needs the image analysis package")

import json
from pathlib import Path
import pytest
from forensic_metascience_ai_toolkit.analysis_runs import Archive
from forensic_metascience_ai_toolkit.workbench.image_cleanup import disk_plan,clear_disk


def test_cleanup_removes_results_preserves_sources_and_other_runs(tmp_path):
    paper=tmp_path/'paper';paper.mkdir()
    source=paper/'paper.pdf';source.write_bytes(b'original source')
    figures=paper/'figures';figures.mkdir();(figures/'original.png').write_bytes(b'source figure')
    panels=paper/'panels';panels.mkdir();(panels/'derived.png').write_bytes(b'derived panel')
    (paper/'image_duplication_findings.json').write_text('{}')
    (paper/'review.json').write_text(json.dumps({'findings':{'IMGDUP-1':{'decision':'false_positive'},'NUM-1':{'decision':'true_issue'}}}))
    archive=Archive(tmp_path)
    e=archive.execution('standalone',components=['image_forensics'])
    run=archive.start(e['id'],'image_forensics','paper')
    source_obj=archive.object(source);panel_obj=archive.object(panels/'derived.png')
    saved=archive.seal(run,items=[],artifacts={'source':{**source_obj,'role':'source'},'panel':{**panel_obj,'role':'panel'}},status='completed')
    e2=archive.execution('full',components=['comprehensive'])
    numeric=archive.seal(archive.start(e2['id'],'comprehensive','paper'),items=[],artifacts={},status='completed')
    plan=disk_plan(tmp_path);outcome=clear_disk(plan)
    assert outcome['runs']==1 and not panels.exists()
    assert source.read_bytes()==b'original source'
    assert (figures/'original.png').read_bytes()==b'source figure'
    assert (archive.base/'objects'/source_obj['sha256'][:2]/source_obj['sha256']).exists()
    assert not (archive.base/'objects'/panel_obj['sha256'][:2]/panel_obj['sha256']).exists()
    assert archive.run(numeric['id'])==numeric
    removed=archive.run(saved['id'])
    assert removed['details_retired'] and removed['status']=='unavailable' and not removed['items']
    assert json.loads((paper/'review.json').read_text())['findings']=={'NUM-1':{'decision':'true_issue'}}


def test_changed_output_is_not_deleted(tmp_path):
    paper=tmp_path/'paper';paper.mkdir()
    result=paper/'image_duplication_findings.json';result.write_text('{}')
    plan=disk_plan(tmp_path)
    result.write_text('{"new_run":true}')
    with pytest.raises(ValueError,match='changed since cleanup'):
        clear_disk(plan)
    assert result.exists()


def test_frozen_review_fixtures_are_preserved_like_pubpeer_labels(tmp_path):
    """`review_fixture_*.jsonl` is the frozen human-label set; the plan used
    to list every non-pubpeer .jsonl under .image_track for deletion while
    its own comment said it preserved ground-truth labels."""
    track=tmp_path/'.image_track';track.mkdir()
    keep=track/'review_fixture_20260912.jsonl';keep.write_text('{"decision":"false_positive"}\n')
    keep2=track/'pubpeer_labels.json';keep2.write_text('{}')
    drop=track/'sweep_run.jsonl';drop.write_text('{}\n')
    plan=disk_plan(tmp_path)
    listed=json.dumps(plan)
    assert 'sweep_run.jsonl' in listed
    assert 'review_fixture_20260912.jsonl' not in listed
    assert 'pubpeer_labels.json' not in listed
