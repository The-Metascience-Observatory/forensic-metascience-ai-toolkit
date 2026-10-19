"""A quote the pipeline could not verify must not be labelled "As printed".

`quotes.annotate` deliberately says NOTHING when the paper cannot be opened
(`build_haystack` returns `{}` -- e.g. a scanned PDF with no text layer, or a
package with no body.md/XML): it strips `quote_verified` and returns the
findings unstamped, because "no haystack is not a verdict on any quote"
(src/metascience_agent/quotes.py, `annotate`).

The viewer then converts that deliberate silence into the affirmative promise:
`quoteLabel` (src/metascience_agent/bundle.py) returns "As printed" for every
value of `quote_verified` other than "stitched"/"unverified" -- including
ABSENT. The label's own docstring calls "As printed" "a promise: that these
words are in the paper", made here about a paper nobody could open. That is
the house failure pattern: our inability to read the paper arriving in the
grammar of a claim about the paper.

This test FAILS against current code and documents the bug. It renders the
findings section the way a reader gets it (executing the viewer JS), with one
finding whose quote is unstamped, and asserts the card does not promise the
words are in the paper.
"""
import json
import shutil
import subprocess

import pytest

from metascience_agent.bundle import render_viewer
from metascience_agent.quotes import annotate

_DOM_STUB = r"""
const fs = require('fs');
const payload = fs.readFileSync(process.argv[2], 'utf8');
const script = fs.readFileSync(process.argv[3], 'utf8');
function el() {
  return {
    textContent: '', innerHTML: '', value: '', style: {}, dataset: {},
    hidden: false, offsetTop: 0, scrollTop: 0,
    classList: {add() {}, remove() {}, toggle() {}, contains() { return false; }},
    appendChild() {}, addEventListener() {}, removeEventListener() {},
    setAttribute() {}, getAttribute() { return null; },
    querySelectorAll() { return []; }, querySelector() { return null; },
    focus() {}, scrollIntoView() {}, insertBefore() {}, remove() {},
    selectNodeContents() {}, setStart() {}, setEnd() {},
    getBoundingClientRect() { return {top: 0, left: 0, width: 0, height: 0}; },
  };
}
const payloadEl = el();
payloadEl.textContent = payload;
global.document = {
  getElementById(id) { return id === 'payload' ? payloadEl : el(); },
  querySelectorAll() { return []; }, querySelector() { return null; },
  createElement() { return el(); }, createRange() { return el(); },
  getSelection() { return null; },
  body: el(), documentElement: el(), addEventListener() {},
};
global.window = {addEventListener() {}, scrollTo() {}, location: {hash: ''}};
global.localStorage = {getItem() { return null; }, setItem() {}};
global.addEventListener = () => {};
global.location = {hash: ''};
global.matchMedia = () => ({matches: false, addEventListener() {}});
global.requestAnimationFrame = (f) => f();
const S = (0, eval)(script + '\n;S');
const sec = S.find(s => s.id === process.argv[4]);
if (!sec) { console.error('no such section: ' + process.argv[4]); process.exit(2); }
process.stdout.write(sec.build());
"""


def _section_html(payload: dict, section_id: str, tmp_path) -> str:
    node = shutil.which("node") or shutil.which("nodejs")
    if not node:
        pytest.skip("node not available")
    html = render_viewer(payload)
    js = tmp_path / "viewer.js"
    js.write_text(html.rsplit("<script>", 1)[1].split("</script>")[0])
    data = tmp_path / "payload.json"
    data.write_text(json.dumps(payload, default=str))
    harness = tmp_path / "harness.js"
    harness.write_text(_DOM_STUB)
    r = subprocess.run([node, str(harness), str(data), str(js), section_id],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return r.stdout


def test_unverifiable_quote_is_not_promised_as_printed(tmp_path):
    # An unreadable paper: the directory exists but nothing yields text.
    paper = tmp_path / "paper"
    paper.mkdir()

    finding = {
        "id": "f1", "technique": "grim", "severity": "suspicious",
        "location": "Table 1",
        "quote": "mean age 48.90 (SD 14.46), n = 49",
        "reported": "mean 48.90",
    }
    annotated = annotate([finding], paper)
    # The pipeline's contract: no haystack means no verdict on the quote.
    assert "quote_verified" not in annotated[0]

    payload = {
        "paper_id": "demo", "findings": annotated,
        "report_obj": {}, "run_meta": {}, "calls": [],
        "paper_facts": [], "run_facts": [], "practice": [],
        "check_table": [], "sankey": {"nodes": [], "links": []}, "files": [],
    }
    html = _section_html(payload, "findings", tmp_path)
    assert "mean age 48.90" in html  # the quote is on the card
    # The promise "these words are in the paper" must not be made for a quote
    # nothing verified. Current code prints exactly that.
    assert "As printed" not in html, (
        "viewer labels an unverified quote 'As printed' when quote_verified "
        "is absent (quotes.annotate said nothing because the paper could not "
        "be opened)"
    )
