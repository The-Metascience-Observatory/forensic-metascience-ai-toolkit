"""Region size is measured in BOTH panels and filtered before pagination."""
import json

import pytest

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.match_regions import region_coverage, region_kind
from forensic_metascience_ai_toolkit.workbench.remote import Remote, summary_expr
from forensic_metascience_ai_toolkit.workbench.repository import Repository
from tests.test_workbench_catalog import seed


def candidate(a=.2, b=.3, **stats):
    return {'panels': [{'uid': 'a'}, {'uid': 'b'}], 'detector_kind': 'transformed_match',
            'measurements': {'engine': 'SIFT', 'matched_frac_a': a, 'matched_frac': b,
                             'inlier_box_a': [10, 20, 80, 90], 'inlier_box_b': [5, 15, 70, 85], **stats}}


@pytest.mark.parametrize('a,b,expected', [(.2, .3, 'partial_both'), (.2, .9, 'partial_one'),
                                        (.9, .2, 'partial_one'), (.9, .95, 'large_both'),
                                        (.8, .8, 'partial_both')])
def test_each_fraction_uses_its_own_panel(a, b, expected):
    item = candidate(a, b, coverage_frac=1.0)
    assert region_kind(region_coverage(item)) == expected
    assert region_kind(region_coverage(candidate(.6, .6)), 50) == 'large_both'


@pytest.mark.parametrize('patch', [
    {'matched_frac_a': None}, {'matched_frac': None}, {'matched_frac_a': 0},
    {'matched_frac': -1}, {'matched_frac': 1.1}, {'matched_frac_a': True},
    {'matched_frac_a': '0.2'}, {'matched_frac': float('nan')},
    {'inlier_box_b': None}, {'inlier_box_a': [80, 20, 10, 90]},
    {'inlier_box_a': [0, 0, float('inf'), 20]}, {'engine': 'masked_ncc'},
])
def test_missing_invalid_and_shared_denominators_are_unknown(patch):
    assert region_kind(region_coverage(candidate(**patch))) == 'unknown'


def test_two_regions_inside_one_image_are_not_two_images():
    item = candidate()
    item['panels'] = [{'uid': 'one'}]
    assert region_coverage(item) is None
    item = candidate()
    item['detector_kind'] = 'intra_panel_clone'
    assert region_coverage(item) is None


@pytest.mark.usefixtures("image_package")
def test_feed_pagination_facets_and_compact_summaries(tmp_path):
    c = Catalog(tmp_path / 'cache.sqlite3')
    try:
        seed(c)
        rows = c.records('component_items')
        # The only partial-both hit is the last unfiltered row, outside page 1.
        for row in rows:
            row['record'].update(candidate(.95, .95))
            if row['item_uid'] == 'i_0':
                row['record'].update(candidate(.21, .235))
            elif row['item_uid'] == 'i_1':
                row['record'].update(candidate(.2, .9))
            elif row['item_uid'] == 'i_2':
                row['record']['measurements'] = {}
            row['record']['region_measurements'] = row['record'].pop('measurements')
        c.apply_changes([('component_items', json.dumps([r['id']]), r) for r in rows], 2)
        repo = Repository(c); repo.refresh('project', 'r_old', 'image_forensics')
        args = {'project': 'project', 'run': 'r_old', 'verdict': 'all'}
        all_rows = repo.feed(args)
        only = repo.feed({**args, 'match_region': 'partial_both', 'region_max_percent': '80'})
        assert only['pagination']['total'] == 1
        assert [r['id'] for r in only['items']] == ['i_0']
        assert only['items'][0]['region_coverage'] == {'a': .21, 'b': .235}
        assert only['match_region_counts'] == all_rows['match_region_counts']
        assert {r['value']: r['count'] for r in only['match_region_counts']} == {
            'partial_both': 1, 'partial_one': 1, 'large_both': 120, 'unknown': 1}
        # A tighter cutoff changes the result and its faceted counts together.
        tighter = repo.feed({**args, 'match_region': 'partial_both', 'region_max_percent': 20})
        assert tighter['pagination']['total'] == 0
        assert repo.feed({**args, 'match_region': 'unknown'})['items'][0]['id'] == 'i_2'
        assert repo.feed({**args, 'match_region': 'partial_both', 'kind': 'absent'})['match_region_counts'] == [
            {'value': x['value'], 'count': 0} for x in only['match_region_counts']]
        assert repo.feed({**args, 'match_region': 'obsolete'})['pagination']['total'] == 123
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_old_cache_gets_bounded_geometry_without_moving_cursor_or_losing_details(tmp_path):
    c = Catalog(tmp_path / 'cache.sqlite3')
    try:
        seed(c)
        target = next(r for r in c.records('component_items') if r['id'] == 1)
        target['record']['panels'] = candidate()['panels']
        c.apply_changes([('component_items', '[1]', target)], 1)
        c.save_detail('component_items', '[1]', {'full_evidence': True}, c.record_token('component_items', '[1]'))
        repo = Repository(c); repo.refresh('project', 'r_old', 'image_forensics')
        args = {'project': 'project', 'run': 'r_old', 'verdict': 'all', 'match_region': 'partial_both'}
        assert repo.feed(args)['pagination']['total'] == 0
        class Connection:
            calls = 0
            def execute(self, sql, values):
                self.calls += 1
                assert "t.record->'measurements'->'matched_frac_a'" in sql
                assert 'to_jsonb(t)' not in sql
                return self
            def fetchall(self):
                return [(1, candidate()['measurements'])]
        remote = Remote(); connection = Connection()
        remote.connect = lambda: connection
        remote.refresh_region_summaries(c)
        assert c.state('cursor') == 1
        assert c.detail('component_items', '[1]') == {'full_evidence': True}
        assert len(c.records('component_items')) == 123
        repo.refresh('project', 'r_old', 'image_forensics')
        assert [r['id'] for r in repo.feed(args)['items']] == ['i_0']
        remote.refresh_region_summaries(c)
        assert connection.calls == 1  # no repeated corpus scan / network read
        sql = summary_expr('component_items')
        assert "'region_measurements'" in sql
        assert "t.record->'measurements'->'inlier_box_b'" in sql
    finally:
        c.close()


@pytest.mark.usefixtures("image_package")
def test_transformation_and_incomplete_coverage_filter_before_pagination(tmp_path):
    from forensic_metascience_ai_toolkit.workbench.match_regions import transformation_kind
    assert transformation_kind(candidate(rotation_deg=37, scale=1, flip=False)) == 'rotation'
    assert transformation_kind(candidate(rotation_deg=37, scale=.5, flip=True)) == 'combined'
    assert transformation_kind(candidate()) == 'unknown'
    c = Catalog(tmp_path/'transform.sqlite')
    try:
        seed(c)
        rows = c.records('component_items')
        for row in rows:
            row['record'].update(candidate(rotation_deg=0, scale=1, flip=False))
            if row['item_uid'] == 'i_0':
                row['record'].update(candidate(rotation_deg=37, scale=1, flip=True))
                row['record']['coverage_status'] = 'incomplete'
            row['record']['region_measurements'] = row['record'].pop('measurements')
        c.apply_changes([('component_items', json.dumps([r['id']]), r) for r in rows], 2)
        repo = Repository(c)
        repo.refresh('project', 'r_old', 'image_forensics')
        result = repo.feed({'project': 'project', 'run': 'r_old', 'verdict': 'all',
                            'transformation': 'combined', 'coverage': 'incomplete'})
        assert result['pagination']['total'] == 1
        assert result['items'][0]['id'] == 'i_0'
    finally:
        c.close()
