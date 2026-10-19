"""Evidence and routing regressions behind the September 11 benign cases."""
import asyncio
from copy import deepcopy
import json

import numpy as np
import pytest

from metascience_observatory_image_analysis.image_forensics import screening as S
from metascience_observatory_image_analysis.image_forensics.caption_context import normalize_pdf_caption, pdf_caption_context
from metascience_observatory_image_analysis.image_forensics.channel_merge import measure
from metascience_observatory_image_analysis.image_forensics.figure_context import _captions_from_pdf
from metascience_observatory_image_analysis.image_forensics.pair_context import comparison_brief
from metascience_observatory_image_analysis.image_review import _panel_image
from tests.test_channel_merge import packet_and_answer, IDENTITY
from tests.test_workbench_catalog import catalog


def v6_answer():
    packet, answer = packet_and_answer()
    packet['policy'] = S.POLICY
    answer['relationship_assessment'] = {
        **answer['channel_assessment'], 'benign_explanation_status': 'supported',
        'benign_explanation': 'The same row and channel labels identify the disclosed merge.',
    }
    return packet, answer


def test_moved_supplement_prefers_exact_local_subdirectory(tmp_path):
    paper = tmp_path / 'paper'; panels = paper / 'panels'
    old = tmp_path / 'producer/panels/si_four/xref14.png'
    old.parent.mkdir(parents=True); old.write_bytes(b'correct recorded image')
    for name, data in [('si_four', b'correct recorded image'), ('si_two', b'wrong image')]:
        folder = panels / name; folder.mkdir(parents=True); (folder/'xref14.png').write_bytes(data)
    uid = 'four.pdf:xref14'
    (panels/'panel_index.json').write_text(json.dumps({'panels': [
        {'uid':uid,'image_path':str(old),'doc':'four.pdf'}]}))
    assert _panel_image(paper, uid, False) == ('panels/si_four/xref14.png', None)
    old.unlink()
    assert _panel_image(paper, uid, False)[0] == 'panels/si_four/xref14.png'
    (panels/'si_four/xref14.png').unlink()
    assert _panel_image(paper, uid, False)[0] is None


def test_rebased_image_must_match_existing_producer(tmp_path):
    paper=tmp_path/'paper'; (paper/'panels').mkdir(parents=True)
    old=tmp_path/'producer/panels/xref1.png';old.parent.mkdir(parents=True);old.write_bytes(b'original')
    (paper/'panels/xref1.png').write_bytes(b'replaced')
    (paper/'panels/panel_index.json').write_text(json.dumps({'panels':[{'uid':'p.pdf:xref1','image_path':str(old)}]}))
    image, why = _panel_image(paper,'p.pdf:xref1',False)
    assert image is None and 'differs from recorded' in why


def test_next_page_legend_beats_pointer_and_stays_document_scoped(tmp_path):
    import fitz
    path=tmp_path/'paper.pdf'
    with fitz.open() as doc:
        doc.new_page().insert_text((50,70),'Fig. 2 (See legend on next page.)')
        doc.new_page().insert_text((50,70),'(see figure on previous page)\nFig. 2 Red channel and Merge show the same field.')
        doc.save(path)
    captions,_ = _captions_from_pdf(path)
    assert captions['Figure 2'] == ('Red channel and Merge show the same field',2)
    st=path.stat(); detail=pdf_caption_context(str(path),st.st_size,st.st_mtime_ns,st.st_ctime_ns,'Figure 2')
    assert detail['pages'] == [2] and 'same field' in detail['raw']
    assert 'Figure 3' not in captions


def test_typography_repairs_require_recorded_line_endings():
    raw='immunofluo-\nrescence GDF-\n15 A′ and A, T-cell and n − 1'
    normalized, changes = normalize_pdf_caption(raw)
    assert normalized == 'immunofluorescence GDF-15 A′ and A, T-cell and n − 1'
    assert changes[0]['raw'] == 'o-\nr'
    assert normalize_pdf_caption('immunofluo- rescence')[0] == 'immunofluo- rescence'


def test_caption_continuation_keeps_pages_and_document_identity(tmp_path):
    import fitz
    for name, text in [('main', 'Untreated material.'), ('supplement', 'Different treated material.')]:
        path = tmp_path / f'{name}.pdf'
        with fitz.open() as doc:
            doc.new_page().insert_text((50,70), f'Fig. 2 {text}')
            doc.new_page().insert_text((50,70), 'Fig. 2 (continued)\nAdditional panel descriptions.')
            doc.save(path)
        st = path.stat()
        detail = pdf_caption_context(str(path), st.st_size, st.st_mtime_ns, st.st_ctime_ns, 'Figure 2')
        assert detail['pages'] == [1, 2]
        assert text in detail['raw'] and 'Additional panel descriptions.' in detail['raw']
        if name == 'main':
            assert 'Different treated material.' not in detail['raw']


def test_overview_detail_supports_two_subpanels_and_parent_context():
    packet, answer=v6_answer()
    quote='(Q) Magnified images show colocalization.'
    for p in packet['panels']: p['caption']=quote
    answer.update(evidence_quote=quote)
    answer['channel_assessment'].update(relationship='not_applicable',evidence_quote='')
    answer['relationship_assessment'].update(relationship='overview_detail',evidence_quote=quote)
    answer['panel_readings'][0].update(context_text='Parent Q, GDF-15/DAPI, Patient 1 above Patient 2; detail images.')
    answer['panel_readings'][1]['subpanels']=[
        {'label_raw':letter,'label_normalized':letter,'region':region,'context_text':context}
        for letter,region,context in [('I','upper','Patient 1 overview'),('J','lower','Patient 2 overview')]]
    result=S.validate(answer,packet,True)
    assert result['validated'],result
    assert 'Scientific relationship:' in result['explanation']
    answer['panel_readings'][1]['subpanels'][0]['label_normalized']='K'
    assert not S.validate(answer,packet,True)['validated']


@pytest.mark.parametrize('relationship', ['same_field_merge','overview_detail','shared_control','furniture'])
def test_benign_cue_cannot_override_distinct_experimental_claims(relationship):
    packet,answer=v6_answer()
    answer.update(decision='issue', category='scientific_content',independent_claim_quote='A is untreated; B is treated.')
    answer['channel_assessment'].update(relationship='distinct_claims',evidence_quote=answer['independent_claim_quote'])
    answer['relationship_assessment'].update(relationship=relationship,evidence_quote=answer['independent_claim_quote'])
    assert not S.validate(answer,packet,True)['validated']
    answer['relationship_assessment'].update(relationship='distinct_claims',benign_explanation_status='rejected',
        benign_explanation='The same specimens, not just the ruler, recur under distinct treatment claims.')
    result=S.validate(answer,packet,True)
    assert result['validated'] and result['decision']=='issue',result


def test_unresolved_relationship_escalates_even_with_high_confidence():
    answer={'validated':True,'confidence':'high','decision':'issue',
            'relationship_assessment':{'benign_explanation_status':'unresolved'}}
    assert S.needs_escalation(answer)


def test_conflicting_context_readings_cannot_clear_at_high_confidence():
    packet, answer = v6_answer()
    answer['confidence'] = 'high'
    answer['relationship_assessment']['relationship'] = 'overview_detail'
    result = S.validate(answer, packet, True)
    assert not result['validated'] and S.needs_escalation(result)
    # `same_field_merge` means the same thing in both vocabularies, so it still
    # binds the scientific relationship. Only the channel token whose two
    # meanings diverge (`distinct_claims`: "a merge does not explain this pair"
    # vs the relationship enum's ISSUE token) was freed.
    assert any('contradicts scientific relationship' in e
               for e in result['validation_errors']), result['validation_errors']


def test_printed_channel_name_is_a_valid_subpanel_label():
    packet,answer=v6_answer()
    answer['panel_readings'][0]['subpanels']=[{'label_raw':'α-tubulin','label_normalized':'α-tubulin',
                                             'region':'column header','context_text':'red channel'}]
    assert S.validate(answer,packet,True)['validated']
    answer['panel_readings'][0]['subpanels'][0]['label_normalized']='Merge'
    assert not S.validate(answer,packet,True)['validated']


def test_fallback_retries_placeholder_once_and_retains_attempts(monkeypatch):
    calls=[]
    async def judge(packet,backend,model,**kwargs):
        calls.append(kwargs.get('previous'))
        return {'decision':'unresolved','confidence':'low','validated':False,'images_delivered':False}
    monkeypatch.setattr(S,'judge',judge)
    attempts=asyncio.run(S.review_packet({'policy':S.POLICY},('codex','luna'),('codex','astra')))
    assert len(attempts)==3 and calls[0] is None and calls[1]==attempts[0]


def test_missing_source_does_not_waste_a_fallback(monkeypatch):
    calls=[]
    async def judge(*args,**kwargs):
        calls.append(1)
        return {'decision':'unresolved','confidence':'low','validated':False,'terminal_evidence_block':'missing_evidence'}
    monkeypatch.setattr(S,'judge',judge)
    assert len(asyncio.run(S.review_packet({},('a','b'),('c','d'))))==1
    assert len(calls)==1


def test_red_channel_matches_merge_in_both_directions():
    rng=np.random.default_rng(11); red=np.zeros((80,80,3),np.uint8)
    red[:,:,0]=rng.integers(30,230,(80,80)); merge=red.copy()
    merge[:,:,1]=rng.integers(0,140,(80,80))
    for a,b,side in [(red,merge,'A'),(merge,red,'B')]:
        result=measure(a,b,IDENTITY)
        assert result['possible_channel_merge'] and result['component_candidate']==side,result
    unrelated=merge.copy();unrelated[:,:,0]=rng.integers(30,230,(80,80))
    assert not measure(red,unrelated,IDENTITY)['possible_channel_merge']


def test_brief_deduplicates_captions_without_losing_manifest():
    packet,_=v6_answer();packet['id']='example'
    for p in packet['panels']:
        p.update(caption_key='same',caption_raw='Raw legend',caption_normalized='Normalized legend')
    packet['context']={'doc':{'methods':{'text':'Unrelated long Methods'},'mentions':{'Figure 2':[]}}}
    brief=comparison_brief(packet)
    assert len(brief['captions'])==1
    assert brief['attachments']==packet['attachments']
    assert 'Unrelated long Methods' not in json.dumps(brief)


def test_brief_preserves_legacy_caption_and_eval_denominator():
    from metascience_observatory_image_analysis.image_forensics.context_eval import summarize
    packet, _ = v6_answer(); packet['id'] = 'example'
    brief = comparison_brief(packet)
    assert next(iter(brief['captions'].values()))['caption_raw'] == packet['panels'][0]['caption']
    row = {'id':'example','variant':'repaired','reviewer':'test',
           'final':{'decision':'innocuous','validated':True,'confidence':'high'},'attempts':[]}
    result = summarize([row, row, row], {'example':'innocuous'})
    assert result['results']['repaired/test']['evaluations'] == 3
    assert result['results']['repaired/test']['unique_cases'] == 1
    assert result['results']['repaired/test']['false_clearances'] is None
    assert result['promotion_eligible'] is False


def test_ineligible_unresolved_is_not_a_clearance(catalog):
    from forensic_metascience_ai_toolkit.workbench.repository import Repository
    repo=Repository(catalog);repo.refresh()
    raw=deepcopy(repo.items[1])
    raw['record']['screening'].update(decision='unresolved',validated=False)
    repo.publication[(1,raw['item_uid'])]={'eligible':False,'policy':'p','source_fingerprint':'s'}
    view=repo.item_view(raw)
    assert view['publication_status']=='unscreened'
    assert view['screening_status']=='failed' and view['scientific_disposition'] is None
    raw['record']['screening'].update(decision='innocuous',validated=True)
    view=repo.item_view(raw)
    assert view['publication_status']=='cleared' and view['scientific_disposition']=='innocuous'
    assert view['eligibility_detail'] == 'Not published: validated innocuous match.'
