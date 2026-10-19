"""Missed duplications recorded in the workbench become scoreable ground truth."""
from tests.source_paths import IMAGE_ROOT
import importlib.util
import json
from pathlib import Path

from forensic_metascience_ai_toolkit.workbench import image_review_host
image_review_host.configure()  # the host lends its storage first, as at runtime
from metascience_observatory_image_analysis.review_workbench.local_images import ImageCatalog, LocalImages  # noqa: E402
from metascience_observatory_image_analysis.image_forensics.review_fixture import export_missed, missed_ground_truth  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def scorer():
    spec = importlib.util.spec_from_file_location('gt_score', IMAGE_ROOT / 'scripts/image_ground_truth_score.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_recorded_missed_duplication_exports_and_scores(tmp_path):
    c = ImageCatalog(tmp_path / 'images.sqlite3')
    try:
        images = LocalImages(c)
        images.record_missed(dict(project='corpus', reviewer='Dan', manipulation='rotation_flip', note='mirrored blot',
            event_id='m1', regions=[
                dict(paper_dir='10.1--x', document='paper.pdf', page=3, bbox_pt=[100, 100, 200, 200], figure='Figure 2'),
                dict(paper_dir='10.1--x', document='paper.pdf', page=3, bbox_pt=[300, 100, 400, 200], panel_uid='paper.pdf:xref9')]))
        images.record_missed(dict(project='elsewhere', reviewer='Dan', manipulation='other', event_id='m2', regions=[
                dict(paper_dir='10.2--y', document='p.pdf', page=1, bbox_pt=[0, 0, 1, 1]),
                dict(paper_dir='10.2--y', document='p.pdf', page=1, bbox_pt=[2, 2, 3, 3])]))
    finally:
        c.close()
    papers = missed_ground_truth(tmp_path / 'images.sqlite3', 'corpus')
    assert list(papers) == ['10.1--x']
    gt = papers['10.1--x']
    assert gt['doi'] == '10.1/x' and gt['counts'] == {'issues': 1}
    issue = gt['issues'][0]
    assert issue['relationship'] == 'rotation_flip' and issue['transform'] == 'rotation/flip' and issue['note'] == 'mirrored blot'
    export_missed(tmp_path / 'images.sqlite3', 'corpus', tmp_path / 'gt', log=lambda s: None)
    written = json.loads((tmp_path / 'gt' / '10.1--x.json').read_text())
    assert written['issues'][0]['panels'][1]['panel_uid'] == 'paper.pdf:xref9'

    # A paper whose figure (xref8) is split into two crops on page 3, plus a
    # separate panel xref9; the detector grouped crop seg1 with xref9.
    paper = tmp_path / '10.1--x'; (paper / 'panels').mkdir(parents=True)
    from PIL import Image
    Image.new('RGB', (200, 100)).save(paper / 'panels' / 'xref8.png')
    index = {'panels': [
        dict(uid='paper.pdf:xref8', placements=[dict(page=3, bbox=[100, 100, 300, 200])], doc_role='main'),
        dict(uid='paper.pdf:xref8-seg1', parent_panel_id='xref8', crop_box=[0, 0, 100, 100], placements=[]),
        dict(uid='paper.pdf:xref8-seg2', parent_panel_id='xref8', crop_box=[0, 100, 100, 200], placements=[]),
        dict(uid='paper.pdf:xref9', placements=[dict(page=3, bbox=[300, 100, 400, 200])]),
    ]}
    (paper / 'panels' / 'panel_index.json').write_text(json.dumps(index))
    (paper / 'image_duplication_findings.json').write_text(json.dumps({'duplicate_groups': [
        dict(kind='transformed_match', panels=['paper.pdf:xref8-seg1', 'paper.pdf:xref9'])]}))
    module = scorer()
    panels = module._load_panels(paper)
    side_a, _ = module.side_uids(panels, written, written['issues'][0]['panels'][0])
    assert 'paper.pdf:xref8-seg1' in side_a and 'paper.pdf:xref8-seg2' not in side_a
    out = tmp_path / 'score.json'
    module.main([str(tmp_path / 'gt' / '10.1--x.json'), str(paper), '--json', str(out)])
    assert json.loads(out.read_text())['caught'] == 1
