"""A filter-wide review decision, and the three things it must refuse.

The queue's per-page bulk action covers 50 loaded rows. Measured on
the embargoed 2026-09 corpus: ~1,944 items reviewed by hand, 58 decisions persisted --
the most valuable artifact of that run existed only in a chat message. These
tests pin the server-side path that replaces it: every matching item, each
against its own run, through the durable outbox, and never over the top of a
decision somebody already recorded.
"""
from __future__ import annotations

import pytest


class _Repo:
    """The two repository methods `save_review_filter` actually calls."""

    BULK_REVIEW_MAX = 5

    def __init__(self, items):
        self.items = items
        self.saved = []

    def feed(self, args):
        offset = int(args.get('offset') or 0)
        limit = int(args.get('limit') or 50)
        rows = self.items[offset:offset + limit]
        return {'items': rows, 'pagination': {'total': len(self.items), 'offset': offset}}

    def save_review(self, args):
        if args['item'] == 'boom':
            raise ValueError('Decision target not in selected run')
        self.saved.append(args)
        return {'event_id': f"rv_{len(self.saved)}", **args}


def _repo(items):
    from metascience_agent.workbench.repository import Repository
    repo = _Repo(items)
    repo.save_review_filter = Repository.save_review_filter.__get__(repo, _Repo)
    return repo


def _item(uid, run='run-a', decision=None):
    return {'id': uid, 'run_id': run, 'decision': decision}


def _args(**kw):
    return {'project': 'p', 'run': 'latest', 'decision': 'false_positive',
            'reviewer': 'Dan', 'reason': 'chart_or_graph', **kw}


def test_every_matching_item_is_saved_against_its_own_run():
    repo = _repo([_item('a', 'run-a'), _item('b', 'run-b'), _item('c', 'run-b')])
    result = repo.save_review_filter(_args())
    assert (result['matched'], result['saved'], result['failed']) == (3, 3, [])
    assert [(s['item'], s['run']) for s in repo.saved] == [
        ('a', 'run-a'), ('b', 'run-b'), ('c', 'run-b')]
    assert all(s['extra']['bulk_reason'] == 'chart_or_graph' for s in repo.saved)


def test_an_existing_decision_is_never_overwritten():
    # The three `true_issue` rows a reviewer recorded by hand must survive a
    # filter-wide "these are all charts" sweep.
    repo = _repo([_item('a'), _item('b', decision={'decision': 'true_issue'})])
    result = repo.save_review_filter(_args())
    assert (result['saved'], result['skipped_already_decided']) == (1, 1)
    assert [s['item'] for s in repo.saved] == ['a']


def test_a_moved_queue_refuses_rather_than_labelling_a_different_set():
    repo = _repo([_item('a'), _item('b')])
    with pytest.raises(ValueError, match='now matches 2 items, not 7'):
        repo.save_review_filter(_args(expected_total=7))
    assert repo.saved == []


def test_a_match_set_over_the_ceiling_refuses_rather_than_labelling_a_prefix():
    repo = _repo([_item(str(n)) for n in range(6)])
    with pytest.raises(ValueError, match='narrow the filter'):
        repo.save_review_filter(_args())
    assert repo.saved == []


def test_one_bad_row_does_not_lose_the_rest():
    repo = _repo([_item('a'), _item('boom'), _item('c')])
    result = repo.save_review_filter(_args())
    assert (result['saved'], len(result['failed'])) == (2, 1)
    assert result['failed'][0]['id'] == 'boom'


@pytest.mark.parametrize('bad,message', [
    ({'reviewer': '  '}, 'Reviewer required'),
    ({'decision': 'not_a_decision'}, 'Valid decision required'),
])
def test_the_decision_and_the_reviewer_are_both_required(bad, message):
    repo = _repo([_item('a')])
    with pytest.raises(ValueError, match=message):
        repo.save_review_filter(_args(**bad))
    assert repo.saved == []


class TestAnExplicitSelection:
    """The queue's bulk button: one request for the whole selection.

    It used to send one HTTP request per row -- MEASURED 2026-09-12 at ~95
    decisions a minute, so 1,944 selected rows took twenty minutes, every
    request re-refreshing the service projection and bumping the revision the
    reviewer's own queue was paging through (which is what produced "Results
    changed while loading. Please retry." in the middle of their work).
    """

    def test_the_selection_is_saved_without_consulting_the_feed(self):
        repo = _repo([])   # an empty feed: the explicit path must not read it
        result = repo.save_review_filter(_args(items=[
            {'run': 'run-a', 'id': 'a'}, {'run': 'run-b', 'id': 'b'}]))
        assert (result['matched'], result['saved']) == (2, 2)
        assert [(s['item'], s['run']) for s in repo.saved] == [('a', 'run-a'), ('b', 'run-b')]

    def test_a_visible_selection_may_overwrite_a_decision(self):
        # The reviewer is LOOKING at these rows, unlike a filter-wide sweep.
        repo = _repo([])
        repo.items = [_item('a', decision={'decision': 'true_issue'})]
        result = repo.save_review_filter(_args(items=[{'run': 'run-a', 'id': 'a'}]))
        assert (result['saved'], result['skipped_already_decided']) == (1, 0)

    def test_failures_are_named_so_the_client_can_keep_them_selected(self):
        repo = _repo([])
        result = repo.save_review_filter(_args(items=[
            {'run': 'run-a', 'id': 'a'}, {'run': 'run-a', 'id': 'boom'}]))
        assert result['saved'] == 1
        assert [f['id'] for f in result['failed']] == ['boom']

    @pytest.mark.parametrize('bad', [[], 'a', {'id': 'a'}])
    def test_an_empty_or_malformed_selection_refuses(self, bad):
        repo = _repo([_item('a')])
        with pytest.raises(ValueError, match='non-empty list'):
            repo.save_review_filter(_args(items=bad))
        assert repo.saved == []

    def test_the_ceiling_applies_to_a_selection_too(self):
        repo = _repo([])
        with pytest.raises(ValueError, match='the ceiling is'):
            repo.save_review_filter(_args(items=[
                {'run': 'run-a', 'id': str(n)} for n in range(6)]))
        assert repo.saved == []
