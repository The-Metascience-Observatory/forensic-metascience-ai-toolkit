"""A saved review reaches the network before routine pulls, without early ACKs."""
import pytest
from forensic_metascience_ai_toolkit.workbench.catalog import Catalog
from forensic_metascience_ai_toolkit.workbench.service import Service

@pytest.mark.parametrize('initialized', [True, False])
@pytest.mark.parametrize('failure', [None, 'send', 'pull'])
def test_review_sync_order_and_durability(tmp_path, initialized, failure):
    calls = []
    with_catalog = Catalog(tmp_path / 'cache.sqlite3')
    if initialized:
        with_catalog.set_state('cursor', 0)
    with_catalog.enqueue({'event_id': 'review-1'})

    class Remote:
        bytes = 0
        def sync(self, catalog):
            calls.append('pull')
            if catalog.state('cursor') is None:
                catalog.set_state('cursor', 0)
                return
            assert catalog.pending(), 'Must retain local decision through the pull'
            if failure == 'pull':
                raise RuntimeError('pull failed')
        def send_review(self, event):
            calls.append('send')
            if failure == 'send':
                raise RuntimeError('offline')
        def close(self):
            pass

    service = Service(with_catalog, Remote(), background=False)
    # Run exactly one real worker iteration, without sleeping.
    service.wake.wait = lambda _: service.stop.set()
    try:
        service.background()
        assert calls == (['send', 'pull'] if initialized else ['pull', 'send', 'pull'])
        assert bool(with_catalog.pending()) == bool(failure)
        if failure:
            service.stop.clear()
            failure = None
            service.background()
            assert with_catalog.pending() == []
    finally:
        with_catalog.close()
