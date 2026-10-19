"""On-demand jobs persist locally, use exact evidence, and never edit shared records."""
import copy
import json
import time
from concurrent.futures import ThreadPoolExecutor

import cv2
import numpy as np
import pytest

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.service import Service
from metascience_observatory_image_analysis.image_forensics.on_demand_video import file_sha, supported

ARGS = {'project': 'project', 'run': 'r1', 'item': 'within:paper:IMGDUP-1'}


def seed_video_catalog(path):
    catalog = Catalog(path)
    catalog.set_state('db_identity', 'fixture-database')
    pixels = np.random.default_rng(42).integers(0, 255, (80, 80, 3), dtype=np.uint8)
    sources = path.parent / 'sources'
    sources.mkdir(exist_ok=True)
    artifacts, panels = [], []
    for i, img in enumerate([pixels, cv2.rotate(pixels, cv2.ROTATE_180)]):
        p = sources / f'{i}.png'
        cv2.imwrite(str(p), img)
        sha = file_sha(p)
        catalog.register_file(p, sha)
        artifacts.append({'run_id': 1, 'artifact_uid': f'p{i}', 'content_sha256': sha,
                          'record': {'name': p.name, 'role': 'panel'}})
        panels.append({'uid': f'paper.pdf:xref{i}', 'paper_dir': 'paper',
                       'image': f'__runs/r1/p{i}', 'placements': [{'figure_label': 'Figure 1', 'page': 1}]})
    item = {'id': ARGS['item'], 'source_id': 'IMGDUP-1', 'kind': 'within',
            'detector_kind': 'transformed_match', 'panels': panels, 'rank': {'score': 1, 'reasons': ['Synthetic manual-video verification']},
            'paper': {'dir': 'paper', 'title': 'Synthetic on-demand video', 'year': 2026,
                      'journal': 'Test fixture', 'doi': ''},
            'papers': [{'dir': 'paper'}], 'sentence': 'Synthetic half-turn pair.',
            'measurements': {'rotation_deg': 180, 'scale': 1, 'flip': False,
                             'affine': [[-1, 0, 79], [0, -1, 79]],
                             'panel_px_a': [80, 80], 'panel_px_b': [80, 80],
                             'n_inliers': 20, 'inlier_ratio': .8,
                             'inlier_box_a': [10, 10, 60, 60], 'inlier_box_b': [19, 19, 69, 69]}}
    raw = {'id': 1, 'run_id': 1, 'owner_paper_id': 1, 'item_uid': item['id'], 'record': item}
    changes = [
        ('corpora', '[1]', {'id': 1, 'name': 'project'}),
        ('papers', '[1]', {'id': 1, 'corpus_id': 1, 'dir': 'paper'}),
        ('executions', '["e1"]', {'execution_uid': 'e1', 'corpus_id': 1, 'status': 'completed'}),
        ('runs', '[1]', {'id': 1, 'run_uid': 'r1', 'execution_uid': 'e1', 'paper_id': 1,
                         'component': 'image_forensics', 'status': 'completed'}),
        ('component_items', '[1]', raw),
    ]
    changes += [('run_artifacts', json.dumps([1, a['artifact_uid']]), a) for a in artifacts]
    catalog.apply_changes(changes, 1)
    catalog.save_detail('component_items', '[1]', raw, catalog.record_token('component_items', '[1]'))
    return catalog


@pytest.fixture
def service(tmp_path, monkeypatch):
    catalog = seed_video_catalog(tmp_path / 'local.sqlite3')
    instance = Service(catalog, background=False)
    # Deterministic job tests explicitly drive claim/execute; smoke uses the real worker.
    monkeypatch.setattr(instance.videos, 'start', lambda: None)
    yield instance
    instance.stop.set()
    instance.videos.close()
    catalog.close()


def test_automatic_rules_do_not_limit_manual_requests(service):
    from metascience_observatory_image_analysis.image_forensics.review_media import needs_animation
    item = service.handle('item', ARGS)
    assert supported(item)[0]
    assert not needs_animation({'kind': 'transformed_match', 'match_stats': item['measurements']})[0]
    out = service.handle('video_generate', ARGS)
    assert out['status'] == 'queued'
    with pytest.raises(ValueError, match='exact'):
        service.handle('video_generate', {**ARGS, 'run': 'latest'})
    with pytest.raises(ValueError):
        service.handle('video_generate', {**ARGS, 'run': 'unknown'})


def test_duplicate_requests_and_peer_claim(service):
    before = service.catalog.all_records()
    with ThreadPoolExecutor(max_workers=3) as pool:
        responses = list(pool.map(lambda _: service.handle('video_generate', ARGS), range(3)))
    assert len({r['job_id'] for r in responses}) == 1
    peer_catalog = Catalog(service.catalog.path)
    peer = Service(peer_catalog, background=False)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            claims = list(pool.map(lambda v: v.claim(), [service.videos, peer.videos]))
        assert sum(c is not None for c in claims) == 1
        assert service.catalog.all_records() == before
    finally:
        peer_catalog.close()


def test_restart_recovers_queue_and_interrupted_job_is_retryable(service):
    result = service.handle('video_generate', ARGS)
    peer_catalog = Catalog(service.catalog.path)
    peer = Service(peer_catalog, background=False)
    try:
        assert peer.handle('video_status', ARGS)['job_id'] == result['job_id']
        row = peer.videos.claim()
        assert row['id'] == result['job_id']
        with peer_catalog.lock, peer_catalog.db:
            peer_catalog.db.execute('update local_video_jobs set lease=?', (time.time() - 1,))
        assert service.handle('video_status', ARGS)['status'] == 'failed'
        assert service.videos.claim() is None
        assert service.handle('video_generate', ARGS)['status'] == 'queued'
    finally:
        peer_catalog.close()


def ready_video(service, contents=b'video-fixture'):
    service.handle('video_generate', ARGS)
    row = service.videos.claim()
    path = service.videos.root / 'objects'
    path.mkdir(parents=True, exist_ok=True)
    import hashlib
    sha = hashlib.sha256(contents).hexdigest()
    video = path / f'{sha}.mp4'
    video.write_bytes(contents)
    service.videos.finish(row, 'ready', sha=sha)
    return row, video


def video_feed(service):
    """The feed's items carrying a video. The queue's has-video filter was
    removed on 2026-09-30; the feed still attaches a ready local video."""
    feed = service.handle('feed', {'project': 'project', 'run': 'r1', 'verdict': 'all'})
    shown = [i for i in feed['items'] if i.get('video')]
    return {'items': shown, 'pagination': {'total': len(shown)}}


@pytest.mark.parametrize('scope', [
    ['other-db', 'project', 'r1', ARGS['item']],
    ['fixture-database', 'project', 'other-run', ARGS['item']],
    ['fixture-database', 'other-project', 'r1', ARGS['item']],
])
def test_video_queue_uses_exact_ownership(service, scope):
    row, _ = ready_video(service)
    with service.catalog.lock, service.catalog.db:
        service.catalog.db.execute('update local_video_jobs set scope=? where id=?',
                                   (json.dumps(scope), row['id']))
    assert video_feed(service)['pagination']['total'] == 0
    assert service.handle('video_status', ARGS)['video'] is None


@pytest.mark.parametrize('change', ['failed', 'missing', 'corrupt', 'signature'])
def test_video_queue_and_detail_drop_unavailable_media_without_record_change(service, change):
    assert video_feed(service)['pagination']['total'] == 0
    row, video = ready_video(service)
    before = service.handle('video_status', ARGS)
    shown = video_feed(service)
    assert shown['pagination']['total'] == 1
    assert shown['items'][0]['video'] == before['video']
    cached = service.repo.feed_pages[('project', 'r1', 'image_forensics')]
    assert not cached[0].get('video'), 'A local video must not mutate shared feed projections'
    token = service.catalog.record_token('component_items', '[1]')
    if change == 'missing':
        video.unlink()
    elif change == 'corrupt':
        video.write_bytes(b'changed video')
    else:
        field, value = ('status', 'failed') if change == 'failed' else ('signature', 'changed')
        with service.catalog.lock, service.catalog.db:
            service.catalog.db.execute(f'update local_video_jobs set {field}=? where id=?', (value, row['id']))
    after = service.handle('video_status', ARGS)
    assert not after['video']
    assert after['revision'] != before['revision']
    assert video_feed(service)['pagination']['total'] == 0
    assert service.catalog.record_token('component_items', '[1]') == token


def test_queue_uses_cached_full_evidence_with_compact_summaries(service):
    ready_video(service)
    c = service.catalog
    full = c.detail('component_items', '[1]')
    compact = copy.deepcopy(full)
    compact['record'].pop('measurements')
    for panel in compact['record']['panels']:
        panel.pop('placements')
    c.apply_changes([('component_items', '[1]', compact)], 2)
    c.save_detail('component_items', '[1]', full, c.record_token('component_items', '[1]'))
    assert video_feed(service)['pagination']['total'] == 1
    assert service.handle('video_status', ARGS)['video']


def test_queue_and_detail_reject_video_after_evidence_changes(service):
    ready_video(service)
    assert video_feed(service)['pagination']['total'] == 1
    c = service.catalog
    changed = copy.deepcopy(c.detail('component_items', '[1]'))
    changed['record']['measurements']['affine'][0][2] = 78
    c.apply_changes([('component_items', '[1]', changed)], 2)
    c.save_detail('component_items', '[1]', changed, c.record_token('component_items', '[1]'))
    assert not service.handle('video_status', ARGS)['video']
    assert video_feed(service)['pagination']['total'] == 0


def test_ready_video_persists_and_is_scoped_and_hash_checked(service):
    before = service.catalog.all_records()
    _, video = ready_video(service)
    peer_catalog = Catalog(service.catalog.path)
    peer = Service(peer_catalog, background=False)
    try:
        item = peer.handle('item', ARGS)
        ref = item['video']
        assert ref.startswith('__videos/')
        params = {'project': 'project', 'dir': 'paper', 'f': ref}
        assert peer.artifact(params)['path'] == str(video)
        with pytest.raises(ValueError):
            peer.artifact({**params, 'project': 'other'})
        with pytest.raises(ValueError):
            peer.artifact({**params, 'dir': 'other'})
        with pytest.raises(ValueError):
            peer.artifact({**params, 'f': ref.rsplit('/', 1)[0] + '/../../outside'})
        peer_catalog.set_state('db_identity', 'other-db')
        assert peer.handle('video_status', ARGS)['video'] is None
        with pytest.raises(ValueError):
            peer.artifact(params)
        peer_catalog.set_state('db_identity', 'fixture-database')
        video.write_bytes(b'changed')
        assert peer.handle('video_status', ARGS)['status'] == 'failed'
        with pytest.raises(ValueError, match='hash'):
            peer.artifact(params)
        assert service.catalog.all_records() == before
    finally:
        peer_catalog.close()


def test_review_changes_do_not_invalidate_video(service):
    ready_video(service)
    ref = service.handle('item', ARGS)['video']
    service.handle('review', {**ARGS, 'decision': 'true_issue', 'reviewer': 'Tester'})
    assert service.handle('item', ARGS)['video'] == ref


def test_missing_source_and_invalid_geometry_have_explicit_errors(service):
    item = service.handle('item', ARGS)
    malformed = copy.deepcopy(item)
    malformed['measurements']['affine'] = [[0, 0, 0], [0, 0, 0]]
    assert not supported(malformed)[0]
    malformed['detector_kind'] = 'intra_panel_clone'
    assert not supported(malformed)[0]
    resolved = service.artifact({'project': 'project', 'dir': 'paper', 'f': item['panels'][0]['image']})
    from pathlib import Path
    Path(resolved['path']).unlink()
    with pytest.raises(FileNotFoundError, match='Historical evidence unavailable'):
        service.handle('video_generate', ARGS)


def test_failure_preserves_earlier_video(service):
    ready_video(service)
    ref = service.handle('item', ARGS)['video']
    service.videos.renderer = 'new-renderer'
    service.handle('video_generate', ARGS)
    row = service.videos.claim()
    service.videos.finish(row, 'failed', error='encoding failed')
    item = service.handle('item', ARGS)
    assert item['video'] == ref
    assert item['video_generation']['error'] == 'encoding failed'
    assert item['video_generation']['status'] == 'failed'
    assert video_feed(service)['items'][0]['video'] == ref


def test_changed_panel_is_not_rendered(service):
    service.handle('video_generate', ARGS)
    row = service.videos.claim()
    payload = json.loads(row['payload'])
    from pathlib import Path
    Path(payload['sources'][0]['path']).write_bytes(b'changed')
    service.videos.execute(row)
    status = service.handle('video_status', ARGS)
    assert status['status'] == 'failed'
    assert 'changed' in status['error']


@pytest.mark.parametrize('stop_worker', [False, True])
def test_timeout_and_shutdown_kill_renderer_and_leave_retryable_job(service, monkeypatch, stop_worker):
    import subprocess
    import sys
    from metascience_observatory_image_analysis.review_workbench import videos
    real_popen = subprocess.Popen
    children = []
    def sleeping_renderer(command, **kwargs):
        proc = real_popen([sys.executable, '-c', 'import time; time.sleep(30)'], **kwargs)
        children.append(proc)
        return proc
    monkeypatch.setattr(videos.subprocess, 'Popen', sleeping_renderer)
    monkeypatch.setattr(videos, 'JOB_TIMEOUT_SECONDS', 0)
    service.handle('video_generate', ARGS)
    row = service.videos.claim()
    if stop_worker:
        service.stop.set()
    service.videos.execute(row)
    assert len(children) == 1 and children[0].poll() is not None
    out = service.handle('video_status', ARGS)
    assert out['status'] == 'failed'
    assert ('interrupted' if stop_worker else 'ten minutes') in out['error']


def test_title_thumbnail_is_scoped_and_hash_checked(service):
    row, _ = ready_video(service)
    from PIL import Image
    path = service.videos.root / 'objects' / 'title.png'
    Image.new('RGB', (1600, 900), 'white').save(path)
    sha = file_sha(path)
    final = path.with_name(f'{sha}.png')
    path.rename(final)
    with service.catalog.lock, service.catalog.db:
        service.catalog.db.execute('update local_video_jobs set thumbnail_sha=? where id=?', (sha, row['id']))
    state = service.handle('video_status', ARGS)
    assert state['thumbnail'] == f'__videos/{row["id"]}/{sha}.png'
    args = {'project': 'project', 'dir': 'paper', 'f': state['thumbnail']}
    resolved = service.artifact(args)
    assert resolved['path'] == str(final)
    assert resolved['record']['name'] == 'IMGDUP-1-thumbnail.png'
    with pytest.raises(ValueError):
        service.artifact({**args, 'project': 'other'})
    final.write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash'):
        service.artifact(args)
    assert service.handle('video_status', ARGS)['status'] == 'failed'
    assert service.handle('video_generate', ARGS)['status'] == 'queued'


def test_on_demand_exports_exact_title_frame(tmp_path, monkeypatch):
    from metascience_observatory_image_analysis.image_forensics import on_demand_video as demand
    from metascience_observatory_image_analysis.image_forensics import review_media as rm
    catalog = seed_video_catalog(tmp_path / 'local.sqlite3')
    service = Service(catalog, background=False)
    try:
        item = service.handle('item', ARGS)
        sources = [{'path': str(tmp_path / 'sources' / f'{i}.png'),
                    'sha256': file_sha(tmp_path / 'sources' / f'{i}.png')} for i in range(2)]
        request = tmp_path / 'request.json'
        request.write_text(json.dumps({'item': item, 'sources': sources}))
        animator = rm._load_animator()
        frames = []
        emissions = []
        context = np.full((900,1600,3), 127, np.uint8)
        from metascience_observatory_image_analysis.image_forensics import video_context
        monkeypatch.setattr(video_context, 'render', lambda sections: context)
        class Video:
            def __init__(self, path, size, fps): self.path, self.size = path, size
            def blank(self): return np.full((self.size[1], self.size[0], 3), 255, np.uint8)
            def emit(self, frame, seconds, key=None):
                frames.append(frame.copy())
                emissions.append((key, seconds))
            def close(self): self.path.write_bytes(b'video'); return self.path
        class Pair:
            def __init__(self, *a, **kw): pass
            def act_side_by_side(self, *a): pass
            def act_warp(self): pass
            def act_blink(self): pass
        monkeypatch.setattr(animator, 'Video', Video)
        monkeypatch.setattr(animator, 'PairRenderer', Pair)
        monkeypatch.setattr(rm, '_load_animator', lambda: animator)
        output = tmp_path / 'video.mp4'
        demand.render(request, output)
        thumbnail = cv2.imread(str(output.with_suffix('.png')))
        assert thumbnail.shape == (900, 1600, 3)
        assert np.array_equal(thumbnail, frames[0])
        assert emissions[:2] == [("title", 5.0), ("source_context", 2.5)]
        assert np.array_equal(frames[1], context)
        card = rm.title_card_args(tmp_path)
        assert card.logo and 'herschel' in card.logo
        assert card.ref_journal == 'Test fixture'
        # Both the reference and the bundled woodcut contribute visible ink.
        assert thumbnail[:, :800].std() > 10
        assert thumbnail[:, 1200:].std() > 10
    finally:
        service.stop.set()
        service.videos.close()
        catalog.close()


def test_video_reference_fetches_doi_placeholder(monkeypatch):
    from metascience_observatory_image_analysis.image_forensics.on_demand_video import reference_metadata
    from metascience_observatory_image_analysis import fetch_metadata_from_doi as api
    calls = []
    def fetch(doi):
        calls.append(doi)
        return dict(title='Real article title', authors='Jane Smith', journal='Journal', year=2021,
                    volume='42', issue='3', pages='12–18')
    monkeypatch.setattr(api, 'fetch_metadata_from_doi', fetch)
    paper = dict(doi='10.1234/test', title='10.1234/test')
    result = reference_metadata(paper)
    assert result['title'] == 'Real article title'
    assert result['pages'] == '12–18'
    assert paper['title'] == '10.1234/test'
    assert calls == ['10.1234/test']
    assert reference_metadata(result) == result
    assert len(calls) == 1
    monkeypatch.setattr(api, 'fetch_metadata_from_doi', lambda doi: None)
    with pytest.raises(ValueError, match='Full reference unavailable'):
        reference_metadata(paper)


def test_video_labels_omit_subpanels_and_rotation_parentheses():
    from metascience_observatory_image_analysis.image_forensics import review_media as rm
    assert rm.video_figure_label('Figure 3 · sub-panel 7') == 'From Figure 3'
    assert rm.video_figure_label('Figure S2G') == 'From Figure S2'
    assert rm.video_figure_label('xref7-seg3') == 'Figure not identified'
    animator = rm._load_animator()
    assert animator.rotation_label(179.2) == '179 deg'
    assert animator.rotation_label(-179.8) == '180 deg'


def test_old_complete_inventory_video_is_not_reused(service):
    row, _ = ready_video(service)
    item = service.handle('item', ARGS)
    item['run_id'] = 'complete_cross_fixture_000000'
    scope = service.videos.scope('project', item)
    from metascience_observatory_image_analysis.review_workbench.videos import digest, snapshot
    with service.catalog.lock, service.catalog.db:
        payload = json.loads(row['payload'])
        payload.pop('source_color_version', None)
        service.catalog.db.execute('update local_video_jobs set scope=?,signature=?,payload=? where id=?',
            (scope, digest(snapshot(item)), json.dumps(payload), row['id']))
    state = service.videos.view('project', item)
    assert state['video'] is None and state['status'] == 'idle'


def test_legacy_analysis_panels_supply_color_to_web_thumbnails_and_video(service, tmp_path, monkeypatch):
    from PIL import Image
    from metascience_observatory_image_analysis.image_forensics.panels import _luma_gray
    inventory = tmp_path/'paper/panels/inventory'
    inventory.mkdir(parents=True)
    records, rows, colors = {}, [], []
    for i in range(2):
        rgb = np.array(Image.open(tmp_path/'sources'/f'{i}.png').convert('RGB'))
        color, gray = inventory/f'{i}.color.png', inventory/f'{i}.gray.png'
        Image.fromarray(rgb).save(color)
        Image.fromarray(_luma_gray(rgb)).save(gray)
        sha = file_sha(gray)
        service.catalog.register_file(gray, sha)
        records[f'p{i}'] = dict(content_sha256=sha, record=dict(role='panel',paper='paper',
            original_path=f'panels/complete_sources/{sha}.png',name=gray.name))
        rows.append(dict(pixel_sha256=sha,color=dict(file=color.name,sha256=file_sha(color))))
        colors.append(str(color))
    (inventory/'manifest.json').write_text(json.dumps(dict(panels=rows)))
    monkeypatch.setattr(service.catalog,'artifact_record',lambda project,run,aid:records[aid])
    monkeypatch.setattr(service.catalog,'paper_path',lambda project,directory:tmp_path/'paper')
    display=service.artifact(dict(project='project',dir='paper',f='__runs/r1/p0'))
    assert display['path']==colors[0]
    thumbnail=service.thumbnails.generate(display)
    pixels=np.array(Image.open(thumbnail['path']).convert('RGB'))
    assert np.any(pixels[:,:,0]!=pixels[:,:,1])
    service.handle('video_generate',ARGS)
    job=service.videos.claim()
    payload=json.loads(job['payload'])
    assert [s['path'] for s in payload['sources']]==colors
    assert payload['source_color_version']==1


def test_complete_panel_display_is_decoded_and_hashed_once(service, tmp_path, monkeypatch):
    """Every media/thumbnail/item_core call decoded a complete-workflow panel
    and re-hashed its colour copy; both are now keyed by file identity."""
    from PIL import Image
    from metascience_observatory_image_analysis.image_forensics.panels import _luma_gray
    inventory = tmp_path/'paper/panels/inventory'
    inventory.mkdir(parents=True)
    rgb = np.array(Image.open(tmp_path/'sources'/'0.png').convert('RGB'))
    color, gray = inventory/'0.color.png', inventory/'0.gray.png'
    Image.fromarray(rgb).save(color); Image.fromarray(_luma_gray(rgb)).save(gray)
    sha = file_sha(gray); service.catalog.register_file(gray, sha)
    record = dict(content_sha256=sha, record=dict(role='panel', paper='paper',
        original_path=f'panels/complete_sources/{sha}.png', name=gray.name))
    (inventory/'manifest.json').write_text(json.dumps(dict(panels=[dict(pixel_sha256=sha, color=dict(file=color.name, sha256=file_sha(color)))])))
    monkeypatch.setattr(service.catalog, 'artifact_record', lambda project, run, aid: record)
    monkeypatch.setattr(service.catalog, 'paper_path', lambda project, directory: tmp_path/'paper')
    args = dict(project='project', dir='paper', f='__runs/r1/p0')
    assert service.artifact(args)['path'] == str(color)
    decodes, hashes = [], []
    import PIL.Image
    real_open, real_register = PIL.Image.open, service.catalog.register_file
    monkeypatch.setattr(PIL.Image, 'open', lambda *a, **k: (decodes.append(a[0]), real_open(*a, **k))[1])
    monkeypatch.setattr(service.catalog, 'register_file', lambda *a, **k: (hashes.append(a[0]), real_register(*a, **k))[1])
    for _ in range(3):
        assert service.artifact(args)['path'] == str(color)
    assert decodes == [] and hashes == []
