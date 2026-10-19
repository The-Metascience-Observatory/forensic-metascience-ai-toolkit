"""The rotation/mirror flight must land on the very pixels the blink uses."""
import json
from types import SimpleNamespace

import numpy as np
import pytest

from metascience_observatory_image_analysis.image_forensics import review_media as RM
from tests.test_video_title_card import _paper, _result, _stub_animator

cv2 = pytest.importorskip('cv2')


@pytest.mark.parametrize('angle,flip', [(0, True), (90, True), (-90, True), (180, False), (90, False)])
def test_flight_preserves_rotation_then_reflection_and_lands_exactly(angle, flip):
    animator = RM._load_animator()
    # An asymmetric image catches a dropped flip even when shapes still match.
    a = np.zeros((80, 110), np.uint8)
    a[7:29, 12:35] = 180
    a[43:60, 65:101] = 250
    theta = np.radians(angle)
    s = 1.4
    raw = np.array([[s*np.cos(theta), -s*np.sin(theta), 130],
                    [s*np.sin(theta), s*np.cos(theta), 130]])
    reflected = np.array([[-1, 0, 319], [0, 1, 0], [0, 0, 1]])
    target = (reflected @ np.vstack([raw, [0, 0, 1]]))[:2] if flip else raw
    b = cv2.warpAffine(a, target, (320, 320))
    stats = dict(affine=raw.tolist(), flip=flip, rotation_deg=angle, scale=s,
                 inlier_box_a=[12, 7, 100, 60], inlier_box_b=[5, 5, 200, 200])
    m = RM._match_from_stats(animator, stats, a, b, None)
    pair = animator.PairRenderer(SimpleNamespace(size=(1600, 900)), a, b, m, 'A', 'B')
    assert m.flip is flip
    np.testing.assert_allclose(pair.flight_transform(0), pair.box_a.affine(), atol=1e-4)
    end = pair.flight_transform(1)
    np.testing.assert_array_equal(end, pair.T_land)
    np.testing.assert_allclose(pair.flight_transform(1-1e-8), end, atol=1e-4)
    if flip:
        rotated = pair.flight_transform(.65)
        assert np.linalg.det(rotated[:, :2]) > 0
        assert np.linalg.det(pair.flight_transform(.95)[:, :2]) < 0
        assert np.degrees(np.arctan2(rotated[1, 0], rotated[0, 0])) == pytest.approx(angle)
    # Undo display placement, compare actual endpoint pixels with target B.
    display_inv = np.vstack([cv2.invertAffineTransform(pair.box_b.affine()), [0, 0, 1]])
    recovered = (display_inv @ np.vstack([end, [0, 0, 1]]))[:2]
    np.testing.assert_allclose(cv2.warpAffine(a, recovered, (320, 320)), b, atol=1)


def test_repair_is_idempotent_and_survives_manifest_rewrites(tmp_path, monkeypatch):
    _paper(tmp_path)
    result = _result()
    (tmp_path / 'image_duplication_findings.json').write_text(json.dumps(result))
    video = tmp_path / 'panels/review/group01_transformed_match.mp4'
    video.write_bytes(b'legacy')
    calls = []
    monkeypatch.setattr(RM, '_load_animator', lambda: _stub_animator(calls))
    assert RM.video_todo(tmp_path, repair_existing=True)['repair'] == 1
    man = RM.render_review_media(tmp_path, result, render_videos=True, repair_existing=True)
    # The repair writes the DOI-named file and retires the legacy name it replaces.
    named = tmp_path / 'panels/review/10.1--x_group01_transformed_match.mp4'
    assert named.read_bytes() == b'mp4' and not video.exists()
    assert man['groups'][0]['video_mp4'] == 'panels/review/10.1--x_group01_transformed_match.mp4'
    assert len(calls) == 1
    stamp = man['groups'][0]['video_render']
    assert not stamp['missing_citation_fields']
    assert RM.video_todo(tmp_path, repair_existing=True)['repair'] == 0
    RM.render_review_media(tmp_path, result, render_videos=False)
    assert RM.video_todo(tmp_path, repair_existing=True)['repair'] == 0
    RM.render_review_media(tmp_path, result, render_videos=True, repair_existing=True)
    assert len(calls) == 1
    meta = json.loads((tmp_path / 'metadata.json').read_text())
    meta['title'] = 'Corrected title'
    (tmp_path / 'metadata.json').write_text(json.dumps(meta))
    assert RM.video_todo(tmp_path, repair_existing=True)['repair'] == 1


def test_failed_repair_preserves_old_video_and_reports_failure(tmp_path, monkeypatch):
    _paper(tmp_path)
    video = tmp_path / 'panels/review/group01_transformed_match.mp4'
    video.write_bytes(b'old')
    monkeypatch.setattr(RM, '_load_animator', lambda: _stub_animator([]))
    def fail(*a, **k):
        raise RuntimeError('encoding failed')
    monkeypatch.setattr(RM, '_render_video', fail)
    man = RM.render_review_media(tmp_path, _result(), render_videos=True, repair_existing=True)
    assert video.read_bytes() == b'old'
    g = man['groups'][0]
    assert g['video_mp4'] and 'encoding failed' in g['video_reason']
    assert 'video_render' not in g


def test_encoding_failure_never_overwrites_old_mp4(tmp_path, monkeypatch):
    animator = RM._load_animator()
    video = tmp_path / 'existing.mp4'
    video.write_bytes(b'old')
    vid = animator.Video(video, (160, 90), 2)
    vid.emit(vid.blank(), 1)
    from metascience_observatory_image_analysis.compute import video as encoding
    monkeypatch.setattr(encoding.shutil, 'which', lambda _: '/ffmpeg')
    monkeypatch.setattr(encoding.subprocess, 'run', lambda *a, **k: SimpleNamespace(returncode=1, stderr=b'failure'))
    with pytest.raises(RuntimeError, match='encoding failed'):
        vid.close()
    assert video.read_bytes() == b'old'


def test_citation_preparation_reaches_card_and_reports_missing_fields(tmp_path, monkeypatch):
    from metascience_agent import paper_metadata
    _paper(tmp_path, meta=None)
    calls = []
    def prepare(p):
        meta = {'title': 'Recovered title', 'authors': 'Ada Lovelace', 'journal': 'Journal', 'year': 2020, 'doi': '10.1/x'}
        (p / 'metadata.json').write_text(json.dumps(meta))
        return meta
    monkeypatch.setattr(paper_metadata, 'record_for_run', prepare)
    monkeypatch.setattr(RM, '_load_animator', lambda: _stub_animator(calls))
    man = RM.render_review_media(tmp_path, _result(), render_videos=True)
    assert calls[0][1].ref_title == 'Recovered title'
    assert calls[0][1].ref_authors == 'Lovelace A'
    assert man['groups'][0]['video_render']['missing_citation_fields'] == []
    (tmp_path / 'metadata.json').write_text('{}')
    monkeypatch.setattr(paper_metadata, 'record_for_run', lambda _: {'error': 'offline'})
    man = RM.render_review_media(tmp_path, _result(), render_videos=True, repair_existing=True)
    assert 'citation unavailable' in man['groups'][0]['video_reason']
    assert 'ref_title' in man['groups'][0]['video_render']['missing_citation_fields']


def test_mirror_act_labels_and_draws_the_turn_before_aligned_blink():
    animator = RM._load_animator()
    frames = []
    class Preview:
        size = (800, 450)
        keyframes = []
        def blank(self):
            return np.full((450, 800, 3), animator.WHITE, np.uint8)
        def emit_anim(self, seconds, draw, **kwargs):
            frames.extend(draw(t) for t in (.30, .42, .47, .55, .72))
    a = np.arange(80*110, dtype=np.uint8).reshape(80, 110)
    stats = dict(affine=[[0, -1, 79], [1, 0, 0]], flip=True,
                 rotation_deg=90, scale=1)
    b = np.rot90(a).copy()
    match = RM._match_from_stats(animator, stats, a, b, None)
    old_ui = animator.UI
    animator.UI = .625
    try:
        pair = animator.PairRenderer(Preview(), a, b, match, 'A', 'B')
        headlines = []
        pair._headline = lambda frame, text, sub='': headlines.append(text)
        pair.act_warp()
        assert 'Mirror horizontally' in headlines
        assert 'mirrored' in headlines[-1] and headlines[-1].startswith('aligned:')
        assert len({f.tobytes() for f in frames}) == 5
        assert {k for k, _ in pair.v.keyframes} == {'rotated', 'mirror'}
    finally:
        animator.UI = old_ui


def test_long_reference_keeps_full_title_and_footer_inside_frame(tmp_path, monkeypatch):
    from PIL import ImageDraw
    animator = RM._load_animator()
    title = ('A retrospective study of factors associated with restoration of thoracic kyphosis '
             'in patients with adolescent idiopathic scoliosis and long term clinical outcomes')
    meta = {'title': title, 'authors': '; '.join(f'First Lastname{i}' for i in range(12)),
            'journal': 'International Medical Journal of Experimental and Clinical Research',
            'volume': '27', 'pages': '1-100', 'year': 2021, 'doi': '10.1/long'}
    _paper(tmp_path, meta)
    monkeypatch.setenv(RM._TITLE_LOGO_ENV, '/nonexistent')
    card = RM.title_card_args(tmp_path)
    # Force the narrow citation column used alongside the artwork.
    from PIL import Image
    artwork = tmp_path / 'art.png'
    Image.new('RGB', (760, 900), 'white').save(artwork)
    card.logo = str(artwork)
    drawn = []
    original = ImageDraw.ImageDraw.text
    def spy(self, xy, text, *args, **kwargs):
        if self._image.size == (1600, 900):
            drawn.append((self._image, xy, text, kwargs.get('font')))
        return original(self, xy, text, *args, **kwargs)
    monkeypatch.setattr(ImageDraw.ImageDraw, 'text', spy)
    emitted = []
    vid = SimpleNamespace(size=(1600, 900),
        blank=lambda: np.full((900, 1600, 3), 255, np.uint8),
        emit=lambda frame, seconds, **kw: emitted.append(frame))
    animator.title_slide(vid, card)
    assert len(emitted) == 1
    final_image = drawn[-1][0]
    final = [r for r in drawn if r[0] is final_image]
    text = ' '.join(r[2] for r in final)
    assert title in text and 'Forensic Metascience AI Toolkit' in text
    for _, (x, y), text, font in final:
        _, _, right, bottom = font.getbbox(text)
        assert x + right <= 1600 and y + bottom <= 900


def test_pipeline_ends_with_blink_without_connections_or_checker(tmp_path):
    from tests.test_video_title_card import _Vid
    acts = []
    class Pair:
        def __init__(self, *a, **kw): pass
        def act_side_by_side(self, *a):
            assert a == ('', '')
            acts.append('printed')
        def act_correspondences(self): pytest.fail('keypoint-connection segment is retired')
        def act_warp(self): acts.append('transform')
        def act_blink(self): acts.append('blink')
        def act_checker(self): pytest.fail('checkerboard segment is retired')
    animator = SimpleNamespace(Video=_Vid, PairRenderer=Pair)
    RM._render_video(animator, tmp_path/'test.mp4', None, None, None, 'A', 'B')
    assert acts == ['printed', 'transform', 'blink']


@pytest.mark.parametrize('shape', [(197, 124), (200, 134), (90, 400), (1200, 1800)])
def test_small_panels_fill_viewport_and_blink_keeps_alignment(shape, monkeypatch):
    animator = RM._load_animator()
    monkeypatch.setattr(animator, 'UI', 1.25)
    # Distinct constant colours make the occupied pixel bounds measurable in
    # the actual emitted frames, rather than merely asserting layout numbers.
    a = np.full(shape, 80, np.uint8)
    b = np.full(shape, 160, np.uint8)
    stats = dict(affine=[[1, 0, 0], [0, 1, 0]], rotation_deg=0, scale=1)
    match = RM._match_from_stats(animator, stats, a, b, None)
    frames = []
    video = SimpleNamespace(size=(1600, 900), fps=3, n=0, keyframes=[],
                            blank=lambda: np.full((900, 1600, 3), 255, np.uint8),
                            writer=SimpleNamespace(write=lambda f: frames.append(f.copy())))
    col_a, col_b = (20, 80, 140), (40, 160, 200)
    pair = animator.PairRenderer(video, a, b, match, 'A', 'B',
                                  a_color=np.full((*shape, 3), col_a, np.uint8),
                                  b_color=np.full((*shape, 3), col_b, np.uint8))
    side = pair._base('Panels')
    ys, xs = np.where(np.all(side == col_a, axis=2))
    assert max(xs.max()-xs.min(), ys.max()-ys.min()) >= 520
    pair.act_blink()
    bounds = []
    for frame, colour in [(frames[0], col_a), (frames[2], col_b)]:
        ys, xs = np.where(np.all(frame == colour, axis=2))
        bounds.append((xs.min(), ys.min(), xs.max(), ys.max()))
        assert max(xs.max()-xs.min(), ys.max()-ys.min()) >= 620
        assert xs.min() >= 75 and xs.max() < 1525
        assert ys.min() >= 175 and ys.max() < 800
    assert bounds[0] == bounds[1]  # the two phases never shift or rescale
