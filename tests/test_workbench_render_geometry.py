"""A rendered crop must prove its pixels before replacing a parent locator."""
import copy

import fitz
import numpy as np
import pytest
from PIL import Image

from metascience_observatory_image_analysis.review_workbench.image_geometry import recover_item_geometry
from metascience_observatory_image_analysis.image_forensics.panels import _luma_gray


@pytest.fixture
def fixture(tmp_path):
    pdf = tmp_path / 'paper.pdf'
    image = tmp_path / 'panel.png'
    doc = fitz.open()
    page = doc.new_page(width=300, height=400)
    # Colored detail proves the detector's truncating luma conversion, not PIL's.
    page.draw_rect(fitz.Rect(40,70,110,150), color=(.2,.3,.8), fill=(.2,.3,.8))
    page.draw_circle(fitz.Point(85,115), 19, color=(.7,.1,.3), fill=(.7,.1,.3))
    doc.save(pdf)
    box = [30.25,60.75,180.2,220.1]
    pix = page.get_pixmap(matrix=fitz.Matrix(150/72,150/72), clip=fitz.Rect(box))
    crop = [60,50,160,180]
    gray = _luma_gray(np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,pix.n))
    Image.fromarray(gray[60:160,50:180]).save(image)
    item = dict(id='pair',papers=[dict(dir='p',pdf='__runs/run/pdf')],panels=[dict(
        uid='render_region:render:Figure_3_p004-seg2',paper_dir='p',image='__runs/run/panel',
        document=dict(id='doc',path='/retired/work/paper.pdf',role='main',status='unavailable'),
        crop_box=crop,placements=[dict(page=1,bbox=box,parent_bbox=box,bbox_kind='parent_approximate',
                                      geometry_gap='Parent transform not recoverable')])],
        targets=[dict(id='pair:a:0',paper_dir='p',bbox_kind='parent_approximate',boxes=[dict(x0=30,y0=60,x1=180,y1=220)])])
    def resolve(directory, ref):
        assert directory == 'p'
        return dict(path=str(pdf if ref.endswith('/pdf') else image),availability='verified')
    expected=[(pix.x+50)/(150/72),(pix.y+60)/(150/72),(pix.x+180)/(150/72),(pix.y+160)/(150/72)]
    return item, resolve, image, expected


def test_exact_luma_crop_recovers_pixel_rounded_geometry_and_locator(fixture):
    item,resolve,_,expected=fixture
    result=recover_item_geometry(item,resolve)
    pl=result['panels'][0]['placements'][0]
    assert pl['bbox_kind']=='crop_exact'
    assert pl['bbox']==pytest.approx(expected)
    assert pl['geometry_gap'] is None
    assert pl['bbox_source']=='verified_render_pixels'
    assert result['panels'][0]['document']['path']=='__runs/run/pdf'
    assert result['targets'][0]['boxes'][0]['x0']==pytest.approx(expected[0])


def test_changed_panel_invalidates_cached_proof(fixture):
    item,resolve,image,_=fixture
    assert recover_item_geometry(copy.deepcopy(item),resolve)['panels'][0]['placements'][0]['bbox_kind']=='crop_exact'
    pixels=np.array(Image.open(image));pixels[0,0]^=255;Image.fromarray(pixels).save(image)
    pl=recover_item_geometry(item,resolve)['panels'][0]['placements'][0]
    assert pl['bbox_kind']=='parent_approximate'
    assert 'does not equal' in pl['geometry_gap']
    assert item['targets'][0]['boxes']==[]
    assert item['targets'][0]['method']=='placement_page'


def test_unverified_current_files_cannot_supply_archive_geometry(fixture):
    item,resolve,_,_=fixture
    result=recover_item_geometry(item,lambda d,r:{**resolve(d,r),'availability':'local_current'})
    assert result['panels'][0]['placements'][0]['bbox_kind']=='parent_approximate'
    assert 'hash-verified' in result['panels'][0]['placements'][0]['geometry_gap']


def test_existing_exact_placements_do_not_read_media(fixture):
    item,_,_,_=fixture
    item['panels'][0]['placements'][0]['bbox_kind']='crop_exact'
    before=copy.deepcopy(item)
    assert recover_item_geometry(item,lambda *_:pytest.fail('unneeded media read'))==before


def test_source_pdf_scope_cannot_fall_back_from_supplement_to_main(fixture):
    item,_,_,_=fixture
    item['panels'][0]['document']['role']='supplement'
    result=recover_item_geometry(item,lambda *_:pytest.fail('wrong document'))
    assert 'No retained PDF' in result['panels'][0]['placements'][0]['geometry_gap']
