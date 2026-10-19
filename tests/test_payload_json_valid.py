"""A single non-finite number blanked the entire viewer.

The viewer is `const D = JSON.parse(document.getElementById('payload')
.textContent)` and every section reads from D. Python's `json.dumps` emits a
non-finite float as the bare token `NaN` / `Infinity`, which is NOT valid JSON;
the browser's strict `JSON.parse` throws on it, D never binds, and the whole
page renders blank. A forensic check that could not compute a value -- a
divide-by-zero, the SD of one observation -- produces exactly such a NaN, so
this is reachable from ordinary input, not only a hostile one.

Reproduced: a finding with computed.tau_hat = float("nan") produced a payload
that a browser could not parse. `render_viewer` now nulls every non-finite
float and dumps with allow_nan=False, so an unparseable page cannot ship.
"""
import json
import re

import pytest

from forensic_metascience_ai_toolkit.bundle import render_viewer

#: A parser that rejects NaN/Infinity exactly as the browser's JSON.parse does.
#: Python's json.loads ACCEPTS them by default, so a naive round-trip test would
#: pass on the very bug this file exists to catch.
def _browser_parse(raw: str):
    def reject(c):
        raise ValueError("non-finite constant: " + c)
    return json.loads(raw, parse_constant=reject)


def _payload_json(html: str) -> str:
    m = re.search(r'id="payload">(.*?)</script>', html, re.S)
    assert m, "no payload block in the viewer"
    return m.group(1).replace("<\\/", "</")


NON_FINITE_PAYLOADS = [
    {"findings": [{"id": "a", "severity": "consistent",
                   "computed": {"tau_hat": float("nan")}}]},
    {"findings": [{"id": "b", "severity": "consistent",
                   "reported": {"ci_hi": float("inf"), "ci_lo": float("-inf")}}]},
    {"deep": [[{"x": float("nan")}]], "run_facts": [{"v": float("inf")}]},
]


class TestThePayloadIsAlwaysBrowserParseable:
    @pytest.mark.parametrize("payload", NON_FINITE_PAYLOADS)
    def test_a_non_finite_float_does_not_break_the_page(self, payload):
        raw = _payload_json(render_viewer(payload))
        _browser_parse(raw)  # raises if NaN/Infinity leaked

    def test_the_nan_becomes_null_not_a_dropped_key(self):
        """Null is the honest rendering -- the value is undefined, not absent."""
        raw = _payload_json(render_viewer(
            {"findings": [{"id": "a", "computed": {"tau_hat": float("nan")}}]}))
        d = _browser_parse(raw)
        assert d["findings"][0]["computed"]["tau_hat"] is None

    def test_an_ordinary_payload_is_unaffected(self):
        raw = _payload_json(render_viewer(
            {"findings": [{"id": "a", "computed": {"tau_hat": 1.38}}]}))
        d = _browser_parse(raw)
        assert d["findings"][0]["computed"]["tau_hat"] == 1.38
