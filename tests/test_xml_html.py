"""XML article view: a missing PDF is a named gap plus a DOI link."""
from forensic_metascience_ai_toolkit.extraction.xml_html import article_view, doi_url


def _xml(tmp_path, body, doi="10.1234/demo"):
    paper = tmp_path / "10.1234--demo"
    paper.mkdir()
    (paper / "10.1234--demo.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<article><front><article-meta>'
        f'<article-id pub-id-type="doi">{doi}</article-id>'
        '<title-group><article-title>XML Only Paper</article-title></title-group>'
        '</article-meta></front>'
        f'<body>{body}</body></article>',
        encoding="utf-8",
    )
    return paper


def test_xml_only_renders_html_and_offers_a_doi_link(tmp_path):
    paper = _xml(tmp_path, "<sec><title>Results</title>"
                 "<p>The mean was 48.90.</p></sec>")
    view = article_view(paper)
    assert view["mode"] == "xml"
    assert view["has_pdf"] is False
    assert "XML Only Paper" in view["html"]
    assert "The mean was 48.90." in view["html"]
    assert view["doi_url"] == "https://doi.org/10.1234/demo"
    assert view["warning"] and "PDF not available" in view["warning"]
    assert "using XML" in view["warning"]


def test_a_pdf_wins_over_xml(tmp_path):
    paper = _xml(tmp_path, "<sec><title>R</title><p>x</p></sec>")
    (paper / "10.1234--demo.pdf").write_bytes(b"%PDF-1.4")
    view = article_view(paper)
    assert view["mode"] == "pdf"
    assert view["has_pdf"] is True
    assert view["warning"] is None
    # XML HTML is still built so a highlight that only exists in XML can
    # switch the pane.
    assert view["has_xml"] is True
    assert view["html"] and "x" in view["html"]


def test_nothing_at_all_still_offers_the_doi(tmp_path):
    paper = tmp_path / "10.9999--empty"
    paper.mkdir()
    (paper / "placeholder.txt").write_text("x")
    view = article_view(paper)
    assert view["mode"] == "none"
    assert view["doi_url"] == "https://doi.org/10.9999/empty"
    assert "Try downloading" in view["warning"]


def test_doi_url_normalises():
    assert doi_url("10.1/x") == "https://doi.org/10.1/x"
    assert doi_url("https://doi.org/10.1/x") == "https://doi.org/10.1/x"
    assert doi_url(None) is None
    assert doi_url("not-a-doi") is None


def test_figures_keep_extended_data_identity_and_complete_captions(tmp_path):
    import json
    from forensic_metascience_ai_toolkit.extraction.xml_html import article_media
    caption = 'Full caption ' * 160
    paper = _xml(tmp_path, '<sec><title>Results</title><p>Read the figures.</p>'
                 '<fig id="F1"><label>Figure 1</label><caption><p>Main caption</p></caption>'
                 '<graphic href="main.png"/></fig>'
                 f'<fig id="F5"><label>Extended Data Figure 1</label><caption><p>{caption}</p></caption>'
                 '<graphic href="extended.png"/></fig></sec>')
    folder = paper/'pmc_figures'; folder.mkdir()
    rows = []
    for fid, name in [('F1', 'main.png'), ('F5', 'extended.png')]:
        (folder/name).write_bytes(b'image')
        rows.append(dict(id=fid, href=name, file=name, figure_label='Figure 1', caption='truncated'))
    (folder/'manifest.json').write_text(json.dumps(dict(figures=rows)))
    view = article_media(article_view(paper), 'p&x', paper.name)
    assert view['html'].count('<img ') == 2
    assert view['html'].count('id="xml-figure-') == 2
    assert 'Extended Data Figure 1' in view['html']
    assert caption.strip() in view['html']
    assert 'truncated' not in view['html']
    assert 'project=p%26x' in view['html']
    assert [f['graphics'][0]['relpath'] for f in view['figures']] == ['pmc_figures/main.png', 'pmc_figures/extended.png']


def test_multiple_graphics_and_unsafe_or_missing_artwork(tmp_path):
    from forensic_metascience_ai_toolkit.extraction.xml_html import article_media
    paper = _xml(tmp_path, '<fig id="f"><label>Figure 1</label><caption><p>&lt;script&gt;caption</p></caption>'
                 '<graphic href="one.png"/><graphic href="two.png"/>'
                 '<graphic href="../escape.png"/><graphic href="https://example.com/x.png"/></fig>')
    (paper/'one.png').write_bytes(b'image'); (paper/'two.png').write_bytes(b'image')
    (tmp_path/'escape.png').write_bytes(b'image')
    view = article_media(article_view(paper), 'p', paper.name)
    assert view['html'].count('<img ') == 2
    assert view['html'].count('Image unavailable on this computer') == 2
    assert '<script>' not in view['html']
    assert '&lt;script&gt;' in view['html']
    assert 'example.com' not in view['html']


def test_elsevier_locator_is_resolved_without_a_graphic_tag(tmp_path):
    import json
    from forensic_metascience_ai_toolkit.extraction.xml_figures import xml_figures
    xml = tmp_path/'article.xml'
    xml.write_text('<full-text-retrieval-response xmlns:ce="urn:ce"><ce:figure id="f1">'
                   '<ce:label>Fig. 1</ce:label><ce:caption><ce:simple-para>Entire caption</ce:simple-para></ce:caption>'
                   '<ce:link locator="gr1"/></ce:figure></full-text-retrieval-response>')
    folder = tmp_path/'publisher_figures'; folder.mkdir(); (folder/'large.jpg').write_bytes(b'image')
    (folder/'manifest.json').write_text(json.dumps({'figures':[{'locator':'gr1','file':'large.jpg'}]}))
    figures = xml_figures(xml, paper_dir=tmp_path)
    assert figures[0]['caption'] == 'Entire caption'
    assert figures[0]['graphics'][0]['relpath'] == 'publisher_figures/large.jpg'


def test_archived_missing_image_is_not_replaced_by_current_file(tmp_path):
    from forensic_metascience_ai_toolkit.extraction.xml_figures import xml_figures
    paper = _xml(tmp_path, '<fig><label>Figure 1</label><graphic href="one.png"/></fig>')
    (paper/'one.png').write_bytes(b'contemporary')
    figures = xml_figures(next(paper.glob('*.xml')), paper_dir=paper, archived_assets=[
        {'name':'one.png','ref':'__runs/r/image','availability':'unavailable'}])
    assert figures[0]['graphics'][0]['relpath'] is None
    assert 'Archived image unavailable' in figures[0]['graphics'][0]['status']


def test_figure_dependencies_detect_nested_arrivals_and_manifest_changes(tmp_path):
    from forensic_metascience_ai_toolkit.extraction.xml_figures import figure_dependencies
    paper = _xml(tmp_path, '<fig><graphic href="nested/one.png"/></fig>')
    before = figure_dependencies(paper)
    (paper/'nested').mkdir(); (paper/'nested/one.png').write_bytes(b'image')
    after = figure_dependencies(paper)
    assert before != after
    (paper/'pmc_figures').mkdir(); (paper/'pmc_figures/manifest.json').write_text('{}')
    assert after != figure_dependencies(paper)
