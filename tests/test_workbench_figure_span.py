"""The queue's "Figures" filter: is a match spread across two different figures?

Dan, 2026-09-30: a filter for findings spread across two figures of a paper.
The rule is the detector's own (`image_analysis._spans_figures`): the item's
placements name two DIFFERENT figures. Measured on the local review database
the same day: 39,995 of 244,179 queue items span figures, 178,982 stay inside
one, 24,235 cannot say (a panel has no label) and 967 are cross-paper.
"""
import json

import pytest

from forensic_metascience_ai_toolkit.workbench import image_review_host
image_review_host.configure()  # the host lends its storage first, as at runtime
from metascience_observatory_image_analysis.review_workbench.local_images import ImageCatalog, LocalImages  # noqa: E402
from forensic_metascience_ai_toolkit.workbench.match_regions import figure_span  # noqa: E402
from tests.test_local_image_review import local  # noqa: F401,E402  (fixture)


def _item(*labels, figure_labels=None, kind='within', dirs=None):
    dirs = dirs or ['paper'] * len(labels)
    return {'kind': kind, 'figure_labels': list(figure_labels or []),
            'panels': [{'paper_dir': d, 'figure_label': l} for d, l in zip(dirs, labels)]}


@pytest.mark.parametrize('labels,expected', [
    (('Figure 2', 'Figure 3'), 'different_figures'),
    (('Figure 1', 'Figure S1'), 'different_figures'),        # a supplement is its own figure
    (('Scheme 2.', 'Scheme 3'), 'different_figures'),        # outside figure_key's grammar
    (('Figure 6', 'Figure 6'), 'same_figure'),
    (('Figure 3', 'Figure 3 (cont.)'), 'same_figure'),       # a continued figure is one figure
    (('Figure 2A', 'Figure 2C'), 'same_figure'),             # panel letters are not figures
    (('Figure-5', 'Figure 5'), 'same_figure'),
    (('Extended Data 2:', 'Extended Data 2'), 'same_figure'),
    (('Figure 8', None), 'unknown'),                         # a missing label is not a match
    ((None, None), 'unknown'),
    (('Figure', 'Figure'), 'unknown'),                       # names no particular figure
])
def test_two_panels(labels, expected):
    assert figure_span(_item(*labels)) == expected


def test_one_image_printed_in_two_figures_spans_them():
    """Tier 1: ONE panel, placed twice. Only the item's labels carry the
    second figure -- 170 such items were `unknown` on panel labels alone."""
    assert figure_span(_item('Figure 1', figure_labels=['Figure 1', 'Figure 2'])) == 'different_figures'


def test_a_clone_inside_one_labelled_panel_is_one_figure():
    assert figure_span(_item('Figure 7', figure_labels=['Figure 7'])) == 'same_figure'
    assert figure_span(_item(None, figure_labels=['Figure 7'])) == 'unknown'


def test_cross_paper_is_its_own_answer():
    assert figure_span(_item('Figure 1', 'Figure 1', kind='cross', dirs=['a', 'b'])) == 'different_papers'
    assert figure_span(_item('Figure 1', 'Figure 2', dirs=['a', 'b'])) == 'different_papers'


def test_the_local_queue_backfills_filters_and_counts(local):  # noqa: F811
    rows = local.db.execute("select rowid,summary from image_queue where project='project' "
                            "and run='r_old' order by item limit 3").fetchall()
    shapes = [('Figure 2', 'Figure 3'), ('Figure 4', 'Figure 4'), ('Figure 1', 'Figure S1')]
    with local.db:
        for (rowid, summary), labels in zip(rows, shapes):
            s = json.loads(summary)
            s['panels'] = [{'paper_dir': 'nested/paper', 'figure_label': l} for l in labels]
            s['figure_labels'] = sorted(set(labels))
            local.db.execute('update image_queue set summary=? where rowid=?', [json.dumps(s), rowid])
        # As on a database written before the column existed.
        local.db.execute('drop index image_queue_filter')
        local.db.execute('alter table image_queue drop column figure_span')
    reopened = ImageCatalog(local.path)
    try:
        images = LocalImages(reopened)
        base = dict(project='project', run='r_old', verdict='all', judgments=None, limit=100)
        spread = images.feed(dict(base, figure_span='different_figures'))
        assert spread['pagination']['total'] == 2
        assert {i['figure_span'] for i in spread['items']} == {'different_figures'}
        assert images.feed(dict(base, figure_span='same_figure'))['pagination']['total'] == 1
        counts = {c['value']: c['count'] for c in images.feed(base)['figure_span_counts']}
        total = images.feed(base)['pagination']['total']
        assert counts == {'different_figures': 2, 'same_figure': 1, 'unknown': total - 3}
        indexed = {r[2] for r in reopened.db.execute('pragma index_info(image_queue_filter)')}
        assert 'figure_span' in indexed
    finally:
        reopened.close()
