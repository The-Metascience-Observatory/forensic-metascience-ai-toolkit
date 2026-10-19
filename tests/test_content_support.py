"""Diagnostics must describe evidence without becoming a new rejection gate."""
import copy
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from metascience_observatory_image_analysis.image_forensics import content_support as cs


@pytest.fixture
def packet(tmp_path):
    rng=np.random.default_rng(7)
    field=rng.integers(30,220,(240,280,3),dtype=np.uint8)
    panels=[]
    for side in ('a','b'):
        path=tmp_path/f'{side}.png'; Image.fromarray(field).save(path)
        panels.append(dict(uid=side,path=str(path),sha256=cs.file_sha(path)))
    return dict(id='within:paper:1',panels=panels,measurements={'affine':[[1,0,0],[0,1,0]]},attachments=[])


NO_TEXT=[dict(status='measured',boxes=[],engine='test') for _ in range(2)]


def test_known_positive_and_input_unchanged(packet):
    before=copy.deepcopy(packet)
    result,_,_=cs.measure(packet,text_regions=NO_TEXT)
    assert result['status'] in ('measured','inconclusive')
    assert result['saved_support']['eligible_supporting_pairs']>10
    assert result['independent_masked_fit']['inliers']>10
    assert packet==before
    assert 'decision' not in result and 'duplication_evidence' not in result
    a=result['agreement']
    assert a['original_agree_px']<=a['eligible_overlap_px']<=a['overlap_px']
    assert a['closed_region_px']==a['original_agree_px']+a['closing_added_px']


@pytest.mark.parametrize('kind',['missing','changed','unhashed','singular','nonfinite','group'])
def test_unavailable_is_not_zero(packet,kind):
    if kind=='missing': Path(packet['panels'][0]['path']).unlink()
    if kind=='changed': Path(packet['panels'][0]['path']).write_bytes(b'changed')
    if kind=='unhashed': packet['panels'][0]['sha256']=None
    if kind=='singular': packet['measurements']['affine']=[[0,0,0],[0,0,0]]
    if kind=='nonfinite': packet['measurements']['affine']=[[float('nan'),0,0],[0,1,0]]
    if kind=='group': packet['panels'].append(packet['panels'][0])
    result,_,_=cs.measure(packet,text_regions=NO_TEXT)
    assert result['status']=='unavailable' and result['reason']
    assert 'saved_support' not in result


def test_overmasking_and_ocr_absence_never_clear(packet):
    texts=[dict(status='measured',boxes=[[0,0,280,240]]),dict(status='unavailable',boxes=[])]
    result,_,_=cs.measure(packet,text_regions=texts)
    assert result['status']=='inconclusive'
    assert result['saved_support']['supporting_pairs']>10
    assert result['saved_support']['eligible_supporting_pairs']==0
    assert len(result['limitations'])>=2
    assert 'decision' not in result


def test_masked_fit_can_describe_different_transform(packet):
    packet['measurements']['affine']=[[1,0,80],[0,1,60]]
    result,_,_=cs.measure(packet,text_regions=NO_TEXT)
    assert result['saved_support']['supporting_pairs']==0
    assert result['independent_masked_fit']['inliers']>10
    assert np.allclose(result['independent_masked_fit']['transform'],[[1,0,0],[0,1,0]],atol=.1)


def test_flip_uses_native_coordinates(packet):
    path=Path(packet['panels'][1]['path'])
    im=np.asarray(Image.open(path));Image.fromarray(np.fliplr(im)).save(path)
    packet['panels'][1]['sha256']=cs.file_sha(path)
    packet['measurements']['flip']=True
    result,_,_=cs.measure(packet,text_regions=NO_TEXT)
    assert result['saved_support']['eligible_supporting_pairs']>10
    r=next(r for r in result['correspondences'] if r['supports_saved'])
    assert abs(r['a'][0]+r['b'][0]-279)<.1


def test_segmentation_failure_preserves_parent(packet,monkeypatch):
    from metascience_observatory_image_analysis.image_forensics import panels
    def fail(*a): raise RuntimeError('segmentation failed')
    monkeypatch.setattr(panels,'segment_gray',fail)
    result,_,_=cs.measure(packet,text_regions=NO_TEXT)
    assert result['status']=='inconclusive'
    assert result['saved_support']['eligible_supporting_pairs']>10
    assert result['panels'][0]['segmentation']['status']=='failed'


def test_descriptor_neighborhood_not_just_center():
    import cv2
    mask=np.zeros((100,100),np.uint8);mask[40:60,55:75]=1
    class Detector:
        def detectAndCompute(self,*args):
            return [cv2.KeyPoint(50,50,10)],np.ones((1,128),np.float32)
    features=cs._features(np.zeros_like(mask),mask,Detector(),cv2)
    assert mask[50,50]==0 and not features[2][0]


def test_generate_load_and_media_integrity(packet,tmp_path,monkeypatch):
    monkeypatch.setattr(cs,'_ocr',lambda p:NO_TEXT[0])
    src=tmp_path/'packet.json';src.write_text(json.dumps(packet))
    root=tmp_path/'root'; output=root/'.image_track/content_support'
    result=cs.generate(src,output)
    read,folder=cs.load_sidecar(root,cs.digest(packet),packet['id'])
    assert read['key']==result['key'] and len(read['artifacts'])>=8
    from metascience_observatory_image_analysis.review_workbench.content_support import detail,artifact
    class Catalog:
        def roots(self,project): return [{'path':str(root)}]
    item={'id':packet['id'],'screening':{'evidence_packet':{'sha256':cs.digest(packet)}}}
    before=copy.deepcopy(item)
    response=detail(Catalog(),'p',item)
    assert item==before and response['saved_support']['supporting_pairs']>10
    assert 'correspondences' not in response
    assert 'correspondences' not in response['independent_masked_fit']
    assert 'correspondences' in json.loads((folder/'diagnostic.json').read_text())
    art=artifact(Catalog(),'p',response['artifacts'][0]['ref'])
    assert art['availability']=='verified'
    Path(art['path']).write_bytes(b'changed')
    with pytest.raises(ValueError,match='changed'): artifact(Catalog(),'p',response['artifacts'][0]['ref'])
    with pytest.raises(ValueError): artifact(Catalog(),'p','__diagnostics/../../etc/passwd')
    with pytest.raises(ValueError): cs.load_sidecar(root,cs.digest(packet),'wrong item')
    (folder/'diagnostic.json').write_text('{}')
    assert detail(Catalog(),'p',item)['status']=='unavailable'


def test_production_fingerprint_excludes_diagnostics():
    from metascience_observatory_image_analysis.image_forensics.retain import FINGERPRINT_FILES
    assert 'content_support.py' not in FINGERPRINT_FILES
    from metascience_observatory_image_analysis.image_forensics import evidence,screening
    import inspect
    assert 'content_support' not in inspect.getsource(evidence.code_stamp)
    assert 'content_support' not in inspect.getsource(screening.input_stamp)


@pytest.mark.parametrize('mode',['small_patch','chart','blot','fluorescence','white_background'])
def test_content_classes_remain_diagnostic(packet,mode):
    import cv2
    rng=np.random.default_rng(5)
    rgb=np.array(Image.open(packet['panels'][0]['path']))
    if mode=='chart':
        rgb[:]=255
        for n in range(20): cv2.circle(rgb,(int(rng.integers(20,260)),int(rng.integers(20,220))),4,(80,80,80),-1)
    elif mode=='blot':
        rgb[:]=220
        for n in range(8): cv2.rectangle(rgb,(15+30*n,80),(30+30*n,120),(50,50,50),-1)
    elif mode=='fluorescence': rgb[:,:,0]=0;rgb[:,:,2]=0
    elif mode=='white_background': rgb[:80]=255;rgb[:,:70]=255
    other=rgb.copy()
    if mode=='small_patch':
        other=rng.integers(30,220,rgb.shape,dtype=np.uint8);other[60:130,80:150]=rgb[60:130,80:150]
    for panel,im in zip(packet['panels'],[rgb,other]):
        Image.fromarray(im).save(panel['path']);panel['sha256']=cs.file_sha(panel['path'])
    before=copy.deepcopy(packet)
    result,_,_=cs.measure(packet,text_regions=NO_TEXT)
    assert packet==before and result['status']!='unavailable'
    assert 'decision' not in result
    if mode in ('small_patch','fluorescence','white_background'):
        assert result['saved_support']['supporting_pairs']>0


def test_reported_montage_pair_retains_unmasked_evidence():
    root=Path(__file__).parent/'data/content_support'
    p=json.loads((root/'pair.json').read_text())
    for panel in p['panels']: panel['path']=str(root/panel.pop('file'))
    before=copy.deepcopy(p)
    result,_,_=cs.measure(p,text_regions=NO_TEXT)
    assert result['saved_support']['supporting_pairs']>30
    assert result['saved_support']['eligible_supporting_pairs']<result['saved_support']['supporting_pairs']
    assert p==before
    assert result['artifacts']==[]  # Pure measure writes nothing.


def test_pdf_geometry_verifies_stream_source_and_affine(packet,tmp_path):
    import fitz
    path=tmp_path/'paper'/'article.pdf';path.parent.mkdir()
    pdf=fitz.open();page=pdf.new_page(width=400,height=400)
    xref=page.insert_image(fitz.Rect(0,0,280,240),filename=packet['panels'][0]['path'])
    page.insert_text((90,110),'Shared label',fontsize=15)
    pdf.save(path);pdf.close()
    with fitz.open(path) as pdf:
        rect,m=pdf[0].get_image_rects(xref,transform=True)[0]
        import hashlib
        sha=hashlib.sha256(pdf.extract_image(xref)['image']).hexdigest()
    panel={**packet['panels'][0], 'uid':f'article.pdf:xref{xref}', 'paper_dir':'paper',
           'stream_sha256':sha,'document':{'id':'d','path':'article.pdf','sha256':cs.file_sha(path)},
           'placements':[dict(page=1,document_id='d',bbox_kind='stream_exact',transform=list(m),parent_size=[280,240])]}
    text=cs._pdf_text(panel,tmp_path)
    assert text['status']=='measured' and text['boxes']
    assert 80<text['boxes'][0][0]<100
    panel['document']['sha256']='0'*64
    assert cs._pdf_text(panel,tmp_path)['status']=='unavailable'


def test_workbench_read_never_generates_or_changes_baseline(packet,tmp_path,monkeypatch):
    import threading
    from types import SimpleNamespace
    from metascience_agent.workbench.service import Service
    from metascience_observatory_image_analysis.review_workbench import content_support as access
    baseline=dict(id=packet['id'],rank={'score':7,'reasons':['unchanged']},publication_status='published',
                  measurements=copy.deepcopy(packet['measurements']),screening={'decision':'issue','validated':True},
                  decision={'decision':'true_issue'},panels=copy.deepcopy(packet['panels']))
    service=Service.__new__(Service)
    service._workers=threading.local()
    service._workers.lock=threading.RLock()
    service._workers.repo=SimpleNamespace(refresh=lambda *args:None,find_item=lambda args:{'id':1},
                                         item_view=lambda *args:copy.deepcopy(baseline))
    service.detail=lambda *args: {'record':copy.deepcopy(baseline)}
    service.catalog=SimpleNamespace(roots=lambda project:[],record_token=lambda *args:'revision-1')
    # Item reads may attach local video availability, but may not generate it.
    service.videos=SimpleNamespace(view=lambda *args:{'status':'idle','video':None})
    def fail(*args,**kwargs): raise AssertionError('Interactive reads must not generate diagnostics')
    monkeypatch.setattr(cs,'generate',fail)
    monkeypatch.setattr(cs,'measure',fail)
    result=service.handle('item',{'project':'p'})
    assert result.pop('video_generation')=={'status':'idle','video':None}
    assert result.pop('record_revision')=='revision-1' and result==baseline
    diagnostic=service.handle('item_diagnostics',{'project':'p'})['content_support']
    assert diagnostic['status']=='not_measured'
    monkeypatch.setattr(access,'detail',fail)
    result=service.handle('item',{'project':'p'})
    assert result.pop('video_generation')=={'status':'idle','video':None}
    assert result.pop('record_revision')=='revision-1' and result==baseline
    diagnostic=service.handle('item_diagnostics',{'project':'p'})['content_support']
    assert diagnostic['status']=='unavailable'


def test_sidecar_digest_hashes_written_bytes_not_text_newline_convention(packet,tmp_path,monkeypatch):
    def windows_text(path,text):
        Path(path).write_bytes(text.replace('\n','\r\n').encode())
    monkeypatch.setattr(cs,'atomic_write_text',windows_text)
    monkeypatch.setattr(cs,'_ocr',lambda p:NO_TEXT[0])
    path=tmp_path/'packet.json';path.write_text(json.dumps(packet))
    root=tmp_path/'root'
    generated=cs.generate(path,root/'.image_track/content_support')
    read,_=cs.load_sidecar(root,cs.digest(packet),packet['id'])
    assert read['key']==generated['key']
