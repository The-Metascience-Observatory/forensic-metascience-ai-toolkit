"""The service's request dispatcher: queued work the caller abandoned is skipped."""
import io
import json
import threading
import time

from metascience_agent.workbench.service import Dispatcher


class Blocking:
    def __init__(self):
        self.release = threading.Event(); self.calls = []; self.lock = threading.Lock()

    def handle(self, method, args):
        with self.lock: self.calls.append(args['n'])
        self.release.wait(5)
        return {'n': args['n']}


def test_cancelled_request_is_skipped_once_queued_and_still_answered():
    service, out = Blocking(), io.StringIO()
    d = Dispatcher(service, out)
    # Two detail workers: requests 1 and 2 start, 3 and 4 wait in the queue.
    for n in (1, 2, 3, 4):
        d.dispatch(json.dumps({'id': n, 'method': 'item_core', 'params': {'n': n}}))
    deadline = time.monotonic() + 5
    while len(service.calls) < 2 and time.monotonic() < deadline: time.sleep(0.01)
    d.dispatch(json.dumps({'id': None, 'method': 'cancel', 'params': {'id': 3}}))
    # Cancelling a running or unknown request changes nothing.
    d.dispatch(json.dumps({'id': None, 'method': 'cancel', 'params': {'id': 1}}))
    d.dispatch(json.dumps({'id': None, 'method': 'cancel', 'params': {'id': 99}}))
    service.release.set(); d.shutdown()
    answers = {m['id']: m for m in map(json.loads, out.getvalue().splitlines())}
    assert sorted(service.calls) == [1, 2, 4]
    assert answers[3]['cancelled'] and 'withdrawn' in answers[3]['error']
    assert answers[1]['result'] == {'n': 1} and answers[4]['result'] == {'n': 4}
    assert not d.queued and not d.cancelled  # nothing accumulates


def test_malformed_lines_are_answered_not_fatal():
    out = io.StringIO(); d = Dispatcher(Blocking(), out)
    d.dispatch('not json'); d.dispatch('5'); d.shutdown()
    assert [json.loads(l)['id'] for l in out.getvalue().splitlines()] == [None, None]
