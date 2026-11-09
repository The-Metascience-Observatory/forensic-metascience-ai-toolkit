"""A detector track's cross-paper queue and the finding-focus link into the
paper page, against the real SQLite cache (no network, no Python child)."""
import json

import pytest

from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.repository import Repository
from forensic_metascience_ai_toolkit.workbench.service import Service


def _finding(i, tier, bits):
    return {'id': i, 'run_id': 1, 'paper_id': 1, 'finding_id': f'f_{i}',
            'producer': 'rng_track', 'technique': 'no_tool_exists',
            'computed_by': 'deterministic_track', 'title': f'Finding {i}',
            'outcome': 'problem', 'severity': 3, 'severity_is_provisional': True,
            'quarantined': True, 'quarantine_reason': 'new detector',
            'track_basis': {'tier': tier, 'excess_bits': bits,
                            'generator': 'numpy_legacy:normal:even', 'seed': 42,
                            'n_values': 100 * i, 'page': 6}}


def seed(c):
    records = {
        'corpora': [{'id': 1, 'name': 'project'}],
        'papers': [{'id': 1, 'corpus_id': 1, 'dir': 'paper', 'paper_slug': 'paper',
                    'doi': '10.1/x', 'title': 'A seeded paper', 'journal': 'J', 'year': 2024}],
        'runs': [{'id': 1, 'run_uid': 'r_rng', 'paper_id': 1, 'kind': 'rng_track',
                  'component': 'rng_track', 'name': 'forensic_review_rng',
                  'status': 'complete', 'execution_status': 'completed',
                  'analysed_at': '2026-03-01'}],
        'users': [{'id': 1, 'name': 'Dan', 'legacy_name': 'Dan Elton'}],
        # Tier 1 beats tier 2 whatever the bits; within a tier, more bits first.
        'findings': [_finding(1, 2, 500.0), _finding(2, 1, 100.0), _finding(3, 1, 300.0)],
        'reviews': [{'id': 1, 'run_id': 1, 'issue_key': 'f_1', 'reviewer_id': 1,
                     'decision': 'disclosed_simulation', 'decided_at': '2026-03-02'}],
    }
    changes = []
    for entity, rows in records.items():
        for r in rows:
            changes.append((entity, json.dumps([r['id']]), r))
    c.apply_changes(changes, 1)


@pytest.fixture
def catalog(tmp_path):
    c = Catalog(tmp_path / 'local/cache.sqlite3')
    seed(c)
    yield c
    c.close()


class Offline:
    def connect(self):
        pytest.fail('connected to the database')


def test_track_sort_is_tier_then_excess_bits_and_rows_carry_paper_and_review(catalog):
    r = Repository(catalog); r.refresh()
    got = r.findings_page({'project': 'project', 'producer': 'rng_track', 'sort': 'track'})
    assert [f['finding_id'] for f in got['rows']] == ['f_3', 'f_2', 'f_1']
    row = got['rows'][0]
    assert row['dir'] == 'paper' and row['paper_title'] == 'A seeded paper'
    assert row['reviews']['decision'] is None
    decided = got['rows'][2]['reviews']['decision']
    assert decided['decision'] == 'disclosed_simulation' and decided['reviewer'] == 'Dan Elton'
    # The default order is unchanged: severity, then id.
    plain = r.findings_page({'project': 'project', 'producer': 'rng_track'})
    assert [f['finding_id'] for f in plain['rows']] == ['f_1', 'f_2', 'f_3']


def test_a_row_without_a_track_basis_sorts_last_never_as_tier_zero(catalog):
    r = Repository(catalog); r.refresh()
    r.findings[4] = {**_finding(4, 1, 999.0), 'track_basis': None}
    r.findings_by_run[1].append(r.findings[4])
    got = r.findings_page({'project': 'project', 'producer': 'rng_track', 'sort': 'track'})
    assert [f['finding_id'] for f in got['rows']][-1] == 'f_4'


def test_decided_filter_splits_the_queue(catalog):
    r = Repository(catalog); r.refresh()
    base = {'project': 'project', 'producer': 'rng_track', 'sort': 'track'}
    assert [f['finding_id'] for f in r.findings_page({**base, 'decided': '1'})['rows']] == ['f_1']
    assert [f['finding_id'] for f in r.findings_page({**base, 'decided': '0'})['rows']] == ['f_3', 'f_2']
    assert r.findings_page({**base, 'decided': 'maybe'})['pagination']['total'] == 3


def test_paper_page_serves_the_page_holding_the_named_finding(catalog):
    s = Service(catalog, Offline(), background=False)
    base = {'project': 'project', 'slug': 'paper', 'group': '0', 'limit': '1'}
    plain = s.handle('paper', base)['issues']
    assert plain['focus_index'] is None and plain['pagination']['offset'] == 0
    assert [i['id'] for i in plain['issues']] == ['f_1']
    focused = s.handle('paper', {**base, 'finding': 'f_2'})['issues']
    assert focused['pagination']['offset'] == 1 and focused['focus_index'] == 0
    assert [i['id'] for i in focused['issues']] == ['f_2']
    # Grouped (the default) finds it too; an unknown id changes nothing.
    grouped = s.handle('paper', {**base, 'group': '1', 'finding': 'f_3'})['issues']
    assert grouped['issues'][grouped['focus_index']]['id'] == 'f_3'
    unknown = s.handle('paper', {**base, 'offset': '2', 'finding': 'f_nope'})['issues']
    assert unknown['focus_index'] is None and unknown['pagination']['offset'] == 2


def test_source_for_an_explicitly_selected_detector_run_is_not_refused(catalog, tmp_path):
    """Opened from the queue, the page names the rng_track run; the source
    read used to look for it among comprehensive runs only and raise."""
    s = Service(catalog, Offline(), background=False)
    got = s.handle('source', {'project': 'project', 'slug': 'paper', 'dir': 'paper', 'run': 'r_rng'})
    assert 'article' in got and 'not recorded' not in json.dumps(got)
    with pytest.raises(ValueError, match='not recorded'):
        s.handle('source', {'project': 'project', 'slug': 'paper', 'dir': 'paper', 'run': 'r_missing'})
