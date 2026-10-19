import copy
import json

import numpy as np
import pytest

from metascience_observatory_image_analysis.image_forensics import source_identity as SI
from metascience_observatory_image_analysis.image_forensics.review_media import needs_animation
from metascience_observatory_image_analysis.extraction.figures import find_captions_in_blocks


@pytest.fixture
def assets(tmp_path):
    cv2 = pytest.importorskip('cv2')
    rng = np.random.default_rng(75)
    im = cv2.GaussianBlur(rng.integers(0, 256, (600, 800), dtype=np.uint8), (3, 3), .7)
    a, b = tmp_path/'pdf.png', tmp_path/'download_F0007_PB.jpg.png'
    cv2.imwrite(str(a), im)
    cv2.imwrite(str(b), cv2.resize(im, (560, 420)))
    (tmp_path/'paper.xml').write_text('<article xmlns:xlink="http://www.w3.org/1999/xlink"><fig><label>Figure 7</label><graphic xlink:href="F0007_OC.jpg"/></fig></article>')
    records = [dict(doc='paper.pdf', panel_id='xref1', image_path=str(a)),
               dict(doc='supplement', panel_id='media', image_path=str(b))]
    group = dict(kind='near_duplicate_phash', tier=3, panels=['paper.pdf:xref1','supplement:media'],
                 duplication_evidence=True, spans_figures=True, figure_labels=[])
    return records, group, tmp_path


def test_whole_figure_alias_is_proven_and_idempotent(assets):
    records, group, root = assets
    report = SI.resolve_groups([group], records, root)
    assert report['verified_artifacts'] == [1]
    assert group['duplication_evidence'] is False
    assert group['adjudication']['category'] == 'same_published_figure'
    old = copy.deepcopy(group)
    SI.resolve_groups([group], records, root)
    assert group == old


def test_renumbered_verified_alias_is_not_reopened_by_caption_refresh(assets):
    records, group, root = assets
    SI.resolve_groups([group], records, root)
    group['figure_labels'] = ['Figure 1', 'Figure 2']
    group['spans_figures'] = True  # caption refresh derives this from labels

    SI.resolve_groups([group], records, root)

    assert group['duplication_evidence'] is False
    assert group['spans_figures'] is False
    assert group['figure_attribution'] == 'same_published_figure'


def test_resized_crop_matches_same_parent_location(assets):
    records, group, root = assets
    child = {**records[0], 'panel_id': 'xref1-seg1', 'parent_panel_id': 'xref1', 'crop_box':[100, 200, 400, 500]}
    records.append(child)
    group.update(kind='transformed_match', panels=['paper.pdf:xref1-seg1','supplement:media'],
                 match_stats={'affine':[[.7,0,140],[0,.7,70]]})
    SI.resolve_groups([group], records, root)
    assert group['duplication_evidence'] is False


def test_displaced_copy_within_alternate_figures_is_not_suppressed(assets):
    records, group, root = assets
    records.append({**records[0], 'panel_id':'seg1', 'parent_panel_id':'xref1', 'crop_box':[100,200,400,500]})
    group.update(kind='transformed_match', panels=['paper.pdf:seg1','supplement:media'],
                 match_stats={'affine':[[.7,0,280],[0,.7,70]]})
    SI.resolve_groups([group], records, root)
    assert group['duplication_evidence'] is True


def test_renumbered_alternate_source_is_still_an_alias(assets):
    records, group, root = assets
    records[0]['figure_labels'] = ['Figure 8']
    SI.resolve_groups([group], records, root)
    assert group['duplication_evidence'] is False
    proof = group['source_identity']['pairs'][0]
    assert proof['renumbered'] is True
    assert proof['source_labels'] == {
        'paper.pdf': ['Figure 8'], 'supplement': ['Figure 7']}


def test_missing_provenance_does_not_clear(assets):
    records, group, root = assets
    (root/'paper.xml').unlink()
    SI.resolve_groups([group], records, root)
    assert group['duplication_evidence'] is True


def test_same_pdf_reuse_does_not_clear(assets):
    records, group, root = assets
    records[1]['doc'] = 'paper.pdf'
    group['panels'][1] = 'paper.pdf:media'
    SI.resolve_groups([group], records, root)
    assert group['duplication_evidence'] is True


def test_matching_patch_is_not_whole_figure_proof(assets):
    cv2 = pytest.importorskip('cv2')
    records, _, _ = assets
    a = cv2.imread(records[0]['image_path'], 0)
    other = np.zeros_like(a)
    other[:180,:200] = a[:180,:200]
    cv2.imwrite(records[1]['image_path'], other)
    assert SI.register_parents(records[0]['image_path'], records[1]['image_path']) is None


def test_parent_alias_tolerates_border_and_panel_letter_typesetting(tmp_path):
    cv2 = pytest.importorskip('cv2')
    rng = np.random.default_rng(89)
    content = cv2.GaussianBlur(rng.integers(0, 256, (500, 700), dtype=np.uint8),
                               (3, 3), .7)
    a = cv2.copyMakeBorder(content, 8, 8, 10, 10, cv2.BORDER_CONSTANT, value=255)
    b = cv2.resize(a, (504, 361))
    cv2.rectangle(a, (18, 18), (42, 48), 255, -1)
    cv2.putText(a, 'A', (20, 43), cv2.FONT_HERSHEY_SIMPLEX, .8, 0, 2)
    cv2.rectangle(b, (13, 13), (31, 35), 255, -1)
    cv2.putText(b, 'B', (14, 32), cv2.FONT_HERSHEY_SIMPLEX, .58, 0, 2)
    pa, pb = tmp_path/'pdf.png', tmp_path/'pmc.png'
    cv2.imwrite(str(pa), a); cv2.imwrite(str(pb), b)
    proof = SI.register_parents(str(pa), str(pb))
    assert proof is not None
    assert proof['coverage_ab'] >= .9 and proof['coverage_ba'] >= .9


def _rendition_pair(tmp_path, factor=3.0):
    """A publisher-sized figure and a PMC-sized copy of it: the small one is the
    big one area-downsampled, so its fine grain is gone (bbamcr.2014.10.017)."""
    cv2 = pytest.importorskip('cv2')
    rng = np.random.default_rng(31)
    coarse = cv2.resize(rng.integers(0, 256, (90, 120), dtype=np.uint8), (1200, 900),
                        interpolation=cv2.INTER_CUBIC)
    big = np.clip(coarse.astype(float) + rng.normal(0, 18, coarse.shape), 0, 255).astype(np.uint8)
    small = cv2.resize(big, (int(1200 / factor), int(900 / factor)), interpolation=cv2.INTER_AREA)
    pa, pb = tmp_path/'pmc.png', tmp_path/'publisher.png'
    cv2.imwrite(str(pa), small); cv2.imwrite(str(pb), big)
    return pa, pb


def test_low_resolution_rendition_is_an_alias_of_the_publisher_copy(tmp_path, monkeypatch):
    pa, pb = _rendition_pair(tmp_path)
    proof = SI.register_parents(str(pa), str(pb))
    assert proof is not None and proof['compared_at'] == 'coarser_rendition'
    assert proof['scale'] == pytest.approx(3.0, rel=.02)
    assert SI.register_parents(str(pb), str(pa))['compared_at'] == 'coarser_rendition'
    # The old rule compared grain on the enlarged copy and refused this pair.
    monkeypatch.setattr(SI, '_RESAMPLE_ABOVE', float('inf'))
    assert SI.register_parents(str(pa), str(pb)) is None


def test_unrelated_figure_at_another_resolution_is_not_an_alias(tmp_path):
    cv2 = pytest.importorskip('cv2')
    pa, pb = _rendition_pair(tmp_path)
    rng = np.random.default_rng(32)
    other = cv2.resize(rng.integers(0, 256, (90, 120), dtype=np.uint8), (1200, 900),
                       interpolation=cv2.INTER_CUBIC)
    cv2.imwrite(str(pb), other)
    assert SI.register_parents(str(pa), str(pb)) is None


def test_hash_match_without_transform_is_located_by_its_crops():
    # Parent registration: B = 3 * A + (5, 7). A hash group carries no affine.
    reg = {'affine': [[3., 0., 5.], [0., 3., 7.]], 'shape_a': [300, 400], 'shape_b': [900, 1200]}
    a = {'parent_panel_id': 'pa', 'crop_box': [10, 20, 110, 220]}   # rows 10-110, cols 20-220
    b = {'parent_panel_id': 'pb', 'crop_box': [37, 65, 337, 665]}
    assert SI.same_location({}, a, b, reg)
    assert not SI.same_location({}, a, {**b, 'crop_box': [37, 125, 337, 725]}, reg)   # 60 px over
    assert not SI.same_location({}, a, {'crop_box': b['crop_box']}, reg)               # B has no parent
    assert SI.same_location({}, {}, {}, reg)                                           # whole parents


def test_one_to_many_parent_alias_is_left_unresolved(assets):
    records, group, root = assets
    records[1]['doc_role'] = 'pmc_render'
    other = {**records[1], 'panel_id': 'media2'}
    records.append(other)
    second = copy.deepcopy(group)
    second['panels'][1] = 'supplement:media2'
    SI.resolve_groups([group, second], records, root)
    assert group['duplication_evidence'] is True
    assert second['duplication_evidence'] is True


@pytest.mark.parametrize('a,b,affine,parent', [
    ([2110,538,2556,995], [753,2,1215,473],
     [[.47562,-.000007,253.773923],[.000007,.47562,249.679896]],
     {'affine':[[.475437,0,.024],[0,.475437,-.368]],'shape_a':[2556,1581],'shape_b':[1215,752]}),
    ([0,3,1081,413], None, [[.457887,.000042,1.262265],[-.000042,.457887,-.00037]],
     {'affine':[[.457753,.0000196,-.0914],[-.0000196,.457753,.0737]],'shape_a':[1081,1748],'shape_b':[495,800]})])
def test_reported_false_positive_crop_coordinates(a,b,affine,parent):
    assert SI.same_location({'affine':affine}, {'crop_box':a}, {'crop_box':b}, parent)
    moved = copy.deepcopy(affine)
    moved[0][2] += 40
    assert not SI.same_location({'affine':moved}, {'crop_box':a}, {'crop_box':b}, parent)


class Page:
    def __init__(self, prefix):
        self.texts = [prefix, 'Figure 2. (A) The PEG wire was fixed on the proximal edge.', 'The same procedure is illustrated.']
    def get_text(self, kind):
        if kind == 'blocks':
            return [(0,0,200,30,'\n'.join(self.texts))]
        return {'blocks':[{'lines':[{'bbox':[0,i*10,200,(i+1)*10], 'spans':[{'text':t}]} for i,t in enumerate(self.texts)]}]}


def test_caption_after_panel_letters_not_after_prose():
    assert find_captions_in_blocks(Page('B'))[0][0] == 'Figure 2'
    assert find_captions_in_blocks(Page('See the illustration below:')) == []


def test_zoom_does_not_generate_video_but_flip_and_rotation_do():
    g = {'kind':'transformed_match','duplication_evidence':True,
         'match_stats':{'rotation_deg':0,'scale':2.106,'flip':False}}
    assert not needs_animation(g)[0]
    assert 'scale-only' in needs_animation(g)[1]
    g['match_stats']['rotation_deg'] = 31
    assert needs_animation(g)[0]
    g['match_stats'].update(rotation_deg=0, flip=True)
    assert needs_animation(g)[0]
    g['duplication_evidence'] = False
    assert not needs_animation(g)[0]


def test_repair_preserves_ids_originals_reviews_and_is_idempotent(assets):
    from metascience_observatory_image_analysis.image_forensics.repair_source_identity import audit_paper
    records, group, root = assets
    (root/'panels/review').mkdir(parents=True)
    result = {'duplicate_groups':[group], 'n_perceptual_eligible':2}
    (root/'image_duplication_findings.json').write_text(json.dumps(result))
    (root/'panels/panel_index.json').write_text(json.dumps({'panels':records}))
    review = '{"issues":{"image:IMGDUP-1":{"decision":"false_positive"}}}'
    (root/'review.json').write_text(review)
    manifest = {'groups':[{'findings_index':1,'group_index':1,'kind':group['kind'],
                          'panels':group['panels'],'video_mp4':'keep_original.mp4'}]}
    (root/'panels/review/review_manifest.json').write_text(json.dumps(manifest))
    report = audit_paper(root, True)
    assert report['verified_artifacts'] == [1]
    live = (root/'image_duplication_findings.json').read_text()
    assert json.loads(live)['duplicate_groups'][0]['panels'] == group['panels']
    assert json.loads(live)['n_duplicate_groups'] == 0
    archive = root/'.source_identity_repair'/f'v{SI.REVISION}'/'image_duplication_findings.json'
    assert json.loads(archive.read_text()) == result
    assert (root/'review.json').read_text() == review
    man = json.loads((root/'panels/review/review_manifest.json').read_text())
    assert man['groups'][0]['archived_video_mp4'] == 'keep_original.mp4'
    assert 'video_mp4' not in man['groups'][0]
    report2 = audit_paper(root, True)
    assert not report2['changed']
    assert (root/'image_duplication_findings.json').read_text() == live
    assert json.loads(archive.read_text()) == result


def test_apply_appends_history_revision_consumed_by_workbench(tmp_path, monkeypatch):
    import asyncio
    from metascience_observatory_image_analysis.image_forensics import repair_source_identity as repair
    from metascience_observatory_image_analysis.image_forensics import screening_reconcile
    from metascience_observatory_image_analysis import history_runtime, image_review

    paper = tmp_path/'paper'
    paper.mkdir()
    (paper/'image_duplication_findings.json').write_text('{}')
    monkeypatch.setattr(repair, 'audit_paper', lambda *_: {
        'paper': 'paper', 'verified_artifacts': [1], 'pending_context': [],
        'n_parent_pairs_evaluated': 1, 'n_parent_aliases': 1,
        'n_ambiguous_parents': 0, 'newly_cleared': [],
    })
    monkeypatch.setattr(repair, 'refresh_project_index',
                        lambda *_: {'updated': True})
    monkeypatch.setattr(screening_reconcile, 'reconcile_paper',
                        lambda *_args, **_kw: {'changed': [], 'errors': []})
    captured = []
    def preserve(target, event, **provenance):
        captured.append((target, event, provenance))
        return {'id': 'revision-2', 'revision_of': 'original-run'}
    monkeypatch.setattr(history_runtime, 'preserve_image', preserve)
    monkeypatch.setattr(image_review, 'write_cache',
                        lambda *_args, **_kw: {'items': []})

    report = asyncio.run(repair.run(tmp_path, apply=True))
    assert captured == [(paper, 'Source identity repair',
                         {'source_identity_revision': SI.REVISION})]
    assert report['history_refresh']['runs'] == [{
        'paper': 'paper', 'run_id': 'revision-2',
        'revision_of': 'original-run'}]


def test_geometry_claim_cannot_invent_rotation():
    from metascience_agent.agent import _check_image_geometry_claims
    g = {'match_stats':{'rotation_deg':0.,'flip':False}}
    r = {'verdict':'unexplained','explanation':'This is a magnified, rotated version of Figure 3C.'}
    _check_image_geometry_claims(r,g)
    assert r['verdict'] == 'insufficient_evidence'
    assert 'measured rotation is 0' in r['explanation']
    negated = {'verdict':'explained','explanation':'This is not a rotated version.'}
    _check_image_geometry_claims(negated,g)
    assert negated['verdict'] == 'explained'


def test_require_all_cannot_clear_when_a_model_failed():
    from metascience_observatory_image_analysis.image_forensics.adjudicate import combine
    g = {'kind':'transformed_match','duplication_evidence':True,'panels':['a','b']}
    result = combine({'duplicate_groups':[g]}, [
        {'backend':'claude','model':'haiku','records':[{'verdict':'explained','category':'same_condition_in_both_figures'}]},
        {'backend':'claude','model':'sonnet','records':[],'is_error':True}])
    assert result['duplicate_groups'][0]['duplication_evidence'] is True
    assert result['duplicate_groups'][0]['adjudication']['verdict'] == 'insufficient_evidence'


def test_legacy_single_panel_placement_list_is_preserved(tmp_path):
    groups = [{'kind':'repeated_element','tier':1,'duplication_evidence':False,
               'panels':['paper.pdf:xref1'], 'placements':[{'page':1,'bbox':[0,0,50,50],'figure_label':'Figure 1'}]}]
    result = {'success':True,'duplicate_groups':groups,'n_perceptual_eligible':2}
    records = [{'doc':'paper.pdf','panel_id':'xref1'}]
    report = SI.resolve_retained(result, records, tmp_path)
    assert not report['errors']
    assert isinstance(groups[0]['placements'], list)
    assert groups[0]['figure_labels'] == ['Figure 1']


def test_xml_caption_punctuation_is_not_a_conflicting_figure(assets):
    records, group, root = assets
    path = root/'paper.xml'
    path.write_text(path.read_text().replace('Figure 7</label>', 'Figure 7.</label>'))
    records[0]['figure_labels'] = ['Figure 7']
    records[0]['placements'] = [{'figure_label':'Figure 7'}]
    SI.resolve_groups([group], records, root)
    assert group['duplication_evidence'] is False
    assert group['figure_labels'] == ['Figure 7']


def test_subset_exhibit_is_resolved_by_panel_identity(tmp_path):
    from metascience_observatory_image_analysis.image_forensics.exhibit_paths import exhibit_for_group
    review = tmp_path/'panels/review'
    review.mkdir(parents=True)
    for name in ['group01.png','group04.png']:
        (review/name).write_bytes(b'fixture')
    wrong = dict(kind='transformed_match',panels=['wrong-a','wrong-b'],exhibit_png='panels/review/group01.png')
    right = dict(kind='transformed_match',panels=['a','b'],exhibit_png='panels/review/group04.png')
    manifest = review/'review_manifest.json'
    manifest.write_text(json.dumps({'groups':[wrong,right]}))
    group = dict(kind='transformed_match',panels=['a','b'])
    assert exhibit_for_group(tmp_path,group).name == 'group04.png'
    manifest.write_text(json.dumps({'groups':[wrong,right,right]}))
    assert exhibit_for_group(tmp_path,group) is None
    manifest.unlink()
    assert exhibit_for_group(tmp_path,group) is None


def test_caption_geometry_fallback_reads_real_pdf(tmp_path):
    fitz = pytest.importorskip('fitz')
    path = tmp_path/'paper.pdf'
    with fitz.open() as pdf:
        page = pdf.new_page()
        page.insert_text((100,210),'B\nFigure 2. (A) A procedural example.',fontsize=11)
        pdf.save(path)
    records = [{'placements':[{'page':1,'bbox':[100,100,290,200],'figure_label':None}]}]
    recovered = SI.recover_captions(path,records)
    assert records[0]['placements'][0]['figure_label'] == 'Figure 2'
    assert recovered[0]['label'] == 'Figure 2'


@pytest.mark.parametrize('outcome', ['valid_retry','invalid_retry','semantic_refusal'])
def test_quote_retry_is_bounded_and_does_not_retry_semantic_refusals(tmp_path, monkeypatch, outcome):
    import asyncio
    from metascience_observatory_image_analysis.image_forensics import adjudicate
    from metascience_observatory_image_analysis.image_forensics.repair_source_identity import rejudge
    calls = []
    async def judge(paper, work, *, backend, model, **kwargs):
        calls.append(work)
        if outcome == 'semantic_refusal':
            rec = {'verdict':'unexplained','category':'none'}
        elif len(calls) == 2 and outcome == 'valid_retry':
            assert work['adjudication_validation_feedback'] is True
            rec = {'verdict':'explained','category':'same_condition_in_both_figures','quote_verified':'verbatim'}
        else:
            rec = {'verdict':'insufficient_evidence','category':'same_condition_in_both_figures',
                   'quote_verified':'stitched','demoted_because':'the supporting quote could not be located in the paper'}
        return {'backend':backend,'model':model,'records':[rec],'cost_usd':.1,'is_error':False}
    monkeypatch.setattr(adjudicate,'judge_once',judge)
    result = {'duplicate_groups':[{'panels':['a','b'],'duplication_evidence':True,
                                  'adjudications':{'claude:haiku':{'verdict':'unexplained'}}}]}
    report = asyncio.run(rejudge(tmp_path,result,[1]))
    assert not report['errors']
    assert len(calls) == (1 if outcome == 'semantic_refusal' else 2)
    assert result['duplicate_groups'][0]['duplication_evidence'] is (outcome != 'valid_retry')


def test_adjudication_persists_artifact_clear_even_when_no_model_is_needed(assets):
    import asyncio
    from metascience_observatory_image_analysis.image_forensics.adjudicate import adjudicate_paper
    records,group,root=assets
    (root/'panels').mkdir()
    (root/'panels/panel_index.json').write_text(json.dumps({'panels':records}))
    result={'success':True,'duplicate_groups':[group],'n_perceptual_eligible':2}
    (root/'image_duplication_findings.json').write_text(json.dumps(result))
    row=asyncio.run(adjudicate_paper(root,models=[],render_media=False))
    assert row['skipped']=='no_evidence_groups'
    live=json.loads((root/'image_duplication_findings.json').read_text())
    assert live['duplicate_groups'][0]['duplication_evidence'] is False
    assert live['n_duplicate_groups']==0


def test_context_selector_only_rechecks_changes_affected_by_this_fix():
    from metascience_observatory_image_analysis.image_forensics.repair_source_identity import affected_context_indices
    ordinary={'kind':'near_duplicate_phash','figure_labels':['Figure 1'],
              'duplication_evidence':True,'adjudication':{'category':'same_condition_in_both_figures'}}
    resize={**copy.deepcopy(ordinary),'kind':'transformed_match','match_stats':{'scale':2,'rotation_deg':0}}
    rotated={**copy.deepcopy(resize),'match_stats':{'scale':2,'rotation_deg':90}}
    old={'duplicate_groups':[ordinary,resize,rotated,copy.deepcopy(ordinary)]}
    now=copy.deepcopy(old)
    now['duplicate_groups'][3]['figure_labels']=['Figure 1','Figure 2']
    assert affected_context_indices(now,old)==[2,4]
    now['duplicate_groups'][1]['adjudication_history']=[{'reason':'already rechecked'}]
    assert affected_context_indices(now,old)==[4]
