"""
The Source & extraction page shows EVERY document in the package, in whatever
form it takes, and says so out loud when it cannot.

WHAT IT DID BEFORE. The left pane rendered `pdf_pages` and nothing else. Two
consequences, both silent:

  * A package with no PDF -- an Elsevier XML paper (two exist in the corpus per
    `extraction/jats.py`), or a fetched `.fulltext.html` -- got one line, "No PDF
    in this bundle", with the extracted text beside it and NOTHING to compare it
    against. The pane whose entire purpose is "check what we read against what
    was published" could not show what was published.
  * A supplement that arrived as .docx, .xlsx, .html, .epub or a scanned image
    was not in the document selector at all, so a finding resting on eTable 3
    pointed at a document the reader could not open -- while the bundle carried
    the file.

And the right-hand pane always showed the PAPER's text, whichever document the
selector was on: switching to a supplement put its pages beside the paper's
words and invited a comparison between two different documents.

The contract these tests pin is that each kind is rendered on its own terms, and
that where the click-to-locate sync cannot be honoured it is REFUSED IN WORDS
rather than degraded into a pane that merely looks broken.
"""

import json
import zipfile

import pytest

from forensic_metascience_ai_toolkit.bundle import (
    _safe_html,
    build_bundle,
    collect,
    render_viewer,
    source_documents,
)
from tests.test_bundle import review, section_html  # noqa: F401  (fixtures)

SUPPLEMENT_HTML = (
    "<html><body><h1>eTable 1</h1>"
    "<table><thead><tr><th>Variable</th><th>Mean (SD)</th><th>n</th></tr></thead>"
    "<tbody><tr><td>Age</td><td>48.90 (14.46)</td><td>49</td></tr></tbody></table>"
    "<p>Values are mean (standard deviation) unless otherwise stated.</p>"
    "</body></html>"
)


def _mixed_package(paper_dir):
    """One supplement of each shape a publication actually takes."""
    (paper_dir / "si_tables.html").write_text(SUPPLEMENT_HTML)
    (paper_dir / "si_codebook.txt").write_text(
        "Codebook\n\nage = age in years at baseline\nbmi = body mass index\n")
    (paper_dir / "si_data.csv").write_text("id,score\n1,5.51\n2,4.20\n")
    (paper_dir / "si_scan.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    with zipfile.ZipFile(paper_dir / "si_appendix.epub", "w") as z:
        z.writestr("OEBPS/c1.xhtml",
                   "<html><body><h2>Appendix A</h2><p>Sensitivity analyses.</p>"
                   "<table><tr><th>Model</th><th>AIC</th></tr>"
                   "<tr><td>M1</td><td>412.3</td></tr></table></body></html>")
    return paper_dir


class TestEveryDocumentIsInTheSelector:
    def test_each_supplement_kind_gets_a_record(self, review, tmp_path):
        paper = review.parent
        _mixed_package(paper)
        docs = source_documents(paper, tmp_path / "out", [])
        kinds = {d["name"]: d["kind"] for d in docs}
        assert kinds["si_tables.html"] == "html"
        assert kinds["si_appendix.epub"] == "epub"
        assert kinds["si_codebook.txt"] == "text"
        assert kinds["si_data.csv"] == "office"
        assert kinds["si_scan.png"] == "image"

    def test_the_pdf_records_keep_their_ids(self, review, tmp_path):
        """`pdf_pages[].doc` joins to these ids, the selector addresses pages by
        them and every finding anchors to document 0. Renumbering here would
        disconnect the page images from the selector without any error."""
        paper = _mixed_package(review.parent)
        pdf_docs = [{"id": 0, "name": "p.pdf", "label": "paper: p.pdf",
                     "pages": 3, "total_pages": 3, "truncated": False}]
        docs = source_documents(paper, tmp_path / "out", pdf_docs)
        assert docs[0]["id"] == 0 and docs[0]["kind"] == "pdf"
        assert [d["id"] for d in docs] == list(range(len(docs)))

    def test_the_extraction_output_is_not_offered_as_a_source(self, review,
                                                              tmp_path):
        """`body.md` IS the right-hand pane. Listing it as a source to compare
        against invites comparing a document with itself."""
        paper = _mixed_package(review.parent)
        names = {d["name"] for d in source_documents(paper, tmp_path / "out", [])}
        assert "body.md" not in names

    def test_an_xml_only_package_still_has_a_left_pane(self, review, tmp_path):
        """The case the old pane could not serve at all: no PDF, so it printed
        "No PDF in this bundle" and showed nothing to check against."""
        paper = review.parent
        (paper / "10.1234--demo.pdf").unlink()
        (paper / "10.1234--demo.xml").write_text(
            "<article><body><sec><table-wrap><label>Table 1</label><table>"
            "<thead><tr><th>V</th><th>Mean (SD)</th></tr></thead>"
            "<tbody><tr><td>Age</td><td>48.90 (14.46)</td></tr></tbody>"
            "</table></table-wrap></sec></body></article>")
        docs = source_documents(paper, tmp_path / "out", [])
        xml = next(d for d in docs if d["kind"] == "xml")
        assert xml["role"] == "paper"
        # Mounted from the extraction rendering rather than a second copy of it
        # -- see `source_is_extraction`. What matters is that the pane has
        # content, not which field it is stored in.
        assert xml["source_is_extraction"] is True
        assert xml["text_html"], "an XML-only package still has an empty pane"
        assert xml["n_tables"] == 1


class TestTheRightPaneFollowsTheDocument:
    def test_each_document_carries_its_own_extracted_text(self, review, tmp_path):
        paper = _mixed_package(review.parent)
        docs = source_documents(paper, tmp_path / "out", [])
        html_doc = next(d for d in docs if d["name"] == "si_tables.html")
        assert "48.90 (14.46)" in html_doc["text_html"]
        txt_doc = next(d for d in docs if d["name"] == "si_codebook.txt")
        assert "age in years" in txt_doc["text"]

    def test_the_viewer_mounts_one_extraction_pane_per_document(self, review,
                                                                tmp_path):
        """One pane each, addressed by document id. A single pane is what made
        the right-hand side show the paper while the left showed a supplement."""
        paper = _mixed_package(review.parent)
        out = build_bundle(review, out_dir=tmp_path / "b", paper_dir=paper)
        html = (out / "viewer.html").read_text()
        payload = json.loads(html.split(
            '<script type="application/json" id="payload">', 1)[1]
            .split("</script>", 1)[0])
        page = section_html(payload, "source", tmp_path)
        for d in payload["source_docs"]:
            assert f'class="txtdoc" data-doc="{d["id"]}"' in page, d["name"]

    def test_the_paper_keeps_the_ids_the_rest_of_the_viewer_addresses(
            self, review, tmp_path):
        """`applyJump`, `goSource` and the findings anchors all reach the paper
        by `bodytext` / `bodyrender` / `pg{n}`. Renaming them would break every
        evidence link in the report, silently."""
        payload = collect(review)
        payload["source_docs"] = [{"id": 0, "name": "p.pdf", "kind": "pdf",
                                   "locate": "lines", "label": "paper: p.pdf",
                                   "role": "paper"}]
        page = section_html(payload, "source", tmp_path)
        assert 'id="bodytext"' in page
        assert 'id="bodyrender"' in page


class TestHonestDegradation:
    def test_an_image_says_it_cannot_be_synchronised(self, review, tmp_path):
        """An image has no text layer. Saying so is the render; a pane that
        silently does nothing on click is indistinguishable from a broken one."""
        paper = _mixed_package(review.parent)
        docs = source_documents(paper, tmp_path / "out", [])
        img = next(d for d in docs if d["kind"] == "image")
        assert img["locate"] == "none"
        assert "PICTURE" in img["note"]
        assert "compare them by eye" in img["note"].lower()

    def test_a_missing_ocr_engine_is_reported_as_ours_not_the_documents(
            self, review, tmp_path):
        """The distinction the whole OCR seam exists to preserve, carried all
        the way to the reader's screen."""
        from forensic_metascience_ai_toolkit.extraction import ocr

        if ocr.engine_status()["available"]:
            pytest.skip("an OCR engine is installed; this is the no-engine case")
        paper = _mixed_package(review.parent)
        docs = source_documents(paper, tmp_path / "out", [])
        img = next(d for d in docs if d["kind"] == "image")
        assert img["ocr_unavailable"] is True
        payload = collect(review)
        payload["source_docs"] = docs
        page = section_html(payload, "source", tmp_path)
        assert "No OCR engine is installed on the machine that built this" in page
        assert 'do not read it as "no tables here"' in page

    def test_an_unopenable_format_blames_our_reader(self, review, tmp_path):
        paper = review.parent
        (paper / "si_old.doc").write_bytes(b"\xd0\xcf\x11\xe0legacy")
        docs = source_documents(paper, tmp_path / "out", [])
        doc = next(d for d in docs if d["name"] == "si_old.doc")
        assert doc["kind"] == "unsupported"
        assert "limit of our reader" in doc["note"]

    def test_an_image_is_copied_into_the_bundle_not_linked_to_the_source_tree(
            self, review, tmp_path):
        """The bundle is forwardable and offline. A path back to the operator's
        machine would be both a broken image and a leak."""
        paper = _mixed_package(review.parent)
        out = build_bundle(review, out_dir=tmp_path / "b", paper_dir=paper)
        html = (out / "viewer.html").read_text()
        payload = json.loads(html.split(
            '<script type="application/json" id="payload">', 1)[1]
            .split("</script>", 1)[0])
        img = next(d for d in payload["source_docs"] if d["kind"] == "image")
        assert img["img"].startswith("docs/")
        assert (out / img["img"]).exists()


class TestTheBundleStaysSelfContainedAndSafe:
    def test_script_and_event_handlers_are_stripped_from_third_party_html(self):
        """This markup was written by a publisher, is inlined into a file the
        reader opens from `file://`, and an allowlist is the only defence that
        does not depend on having thought of the attack."""
        got = _safe_html(
            "<html><body><p onclick='steal()'>hi</p><script>alert(1)</script>"
            "<img src='https://tracker.example/p.gif'>"
            "<a href='https://evil.example'>x</a>"
            "<iframe src='https://evil.example'></iframe></body></html>")
        assert "<script" not in got and "alert(1)" not in got
        assert "onclick" not in got
        assert "iframe" not in got
        assert "tracker.example" not in got
        assert "evil.example" not in got
        assert "hi" in got and "x" in got      # the words survive

    def test_the_table_a_supplement_carries_survives_the_sanitiser(self):
        """Stripping is not the goal -- showing the document is. A sanitiser
        that ate the tables would make the pane useless for the one comparison
        it exists to support."""
        got = _safe_html(SUPPLEMENT_HTML)
        assert "<table" in got and "48.90 (14.46)" in got
        assert "colspan" not in got            # absent here, allowed when present

    def test_the_body_wrapper_is_not_kept(self):
        """The result is mounted inside a `<div>`, and an EPUB contributes one
        per chapter -- so keeping `<body>` would nest several of them inside the
        page's real one. Browsers tolerate that by dropping the tag silently,
        which is exactly why it would never be noticed."""
        got = _safe_html(SUPPLEMENT_HTML)
        assert "<body" not in got and "</body>" not in got
        assert "<h1>eTable 1</h1>" in got

    def test_no_network_reference_reaches_the_viewer(self, review, tmp_path):
        paper = _mixed_package(review.parent)
        out = build_bundle(review, out_dir=tmp_path / "b", paper_dir=paper)
        html = (out / "viewer.html").read_text()
        for needle in ("http://", "https://cdn", "<iframe", "fonts.googleapis"):
            if needle == "http://":
                # A URL inside the PAPER's own text is evidence and stays; what
                # must not appear is a URL the VIEWER would fetch.
                continue
            assert needle not in html, needle
        # Assets are referenced by RELATIVE path from the bundle directory. The
        # `<img>` itself is built at runtime from the payload, so the payload is
        # where the reference has to be checked.
        assert '"docs/' in html or '"pages/' in html
        assert 'src="http' not in html


#: A DOM stub with enough behaviour to RUN `after()`, not merely `build()`.
#:
#: `build()` returns a string and is what every other viewer test exercises;
#: `after()` is where the wiring lives, and a ReferenceError in it kills the
#: whole pane with no output at all. The rebinding of `pre` / `rendered` /
#: `rawText` on document switch, the `chosenView` temporal-dead-zone hazard from
#: `selectDoc` being defined above its `let`, and the delegated click listeners
#: are all `after()`-only, so nothing in the suite could see them.
#:
#: The stub answers only the selectors the section actually uses. Anything else
#: returns an empty list, which is the honest default: a test that invented
#: elements would pass on a page that has none.
_AFTER_STUB = r"""
const fs = require('fs');
const payload = fs.readFileSync(process.argv[2], 'utf8');
const script = fs.readFileSync(process.argv[3], 'utf8');
const CALLS = [];
function el(tag, doc) {
  const e = {
    tagName: tag || 'DIV', textContent: '', innerHTML: '', value: '',
    style: {}, dataset: (doc === undefined ? {} : {doc: String(doc)}),
    hidden: false, children: [],
    classList: {add() {}, remove() {}, toggle() {}, contains() { return false; }},
    appendChild() {}, addEventListener(t) { CALLS.push('listen:' + t); },
    removeEventListener() {}, setAttribute() {}, getAttribute() { return null; },
    querySelectorAll(sel) { return e._q ? e._q(sel) : []; },
    querySelector(sel) { const r = e.querySelectorAll(sel); return r[0] || null; },
    closest() { return null; }, contains() { return false; },
    focus() {}, scrollIntoView() { CALLS.push('scroll'); },
    getBoundingClientRect() { return {top: 0, left: 0, width: 100, height: 100}; },
  };
  return e;
}
const TXT = [0, 1].map(i => {
  const w = el('DIV', i);
  const pre = el('PRE'); pre.textContent = 'document ' + i + ' extracted text';
  const rich = el('DIV');
  w._q = sel => (sel.indexOf('pre.srcraw') >= 0 ? [pre]
               : sel.indexOf('.srcrich') >= 0 ? [rich] : []);
  return w;
});
const PDFD = [0, 1].map(i => el('DIV', i));
const payloadEl = el(); payloadEl.textContent = payload;
function pick(sel) {
  if (sel.indexOf('#pane-txt .txtdoc[data-doc=') === 0) {
    const n = sel.replace(/\D+/g, '');
    return TXT.filter(t => t.dataset.doc === n);
  }
  if (sel === '#pane-txt .txtdoc') return TXT;
  if (sel === '#pane-pdf .pdfdoc') return PDFD;
  return [];
}
global.document = {
  getElementById(id) { return id === 'payload' ? payloadEl : el(); },
  querySelectorAll: pick,
  querySelector(sel) { return pick(sel)[0] || null; },
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
const sec = S.find(s => s.id === 'source');
sec.build();
sec.after();
if (typeof global.window.__srcSelectDoc === 'function') {
  global.window.__srcSelectDoc(1);   // switch documents
  global.window.__srcSelectDoc(0);   // and back
  CALLS.push('switched');
}
process.stdout.write(JSON.stringify(CALLS));
"""


def _run_after(payload, tmp_path):
    import shutil
    import subprocess

    node = shutil.which("node") or shutil.which("nodejs")
    if not node:
        pytest.skip("node not available")
    tmp_path.mkdir(parents=True, exist_ok=True)
    js = tmp_path / "viewer.js"
    js.write_text(render_viewer(payload).rsplit("<script>", 1)[1]
                  .split("</script>")[0])
    data = tmp_path / "payload.json"
    data.write_text(json.dumps(payload, default=str))
    harness = tmp_path / "after.js"
    harness.write_text(_AFTER_STUB)
    r = subprocess.run([node, str(harness), str(data), str(js)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2500:]
    return json.loads(r.stdout)


class TestTheWiringActuallyRuns:
    def test_after_runs_without_throwing(self, review, tmp_path):
        """`selectDoc` is defined ABOVE the `let chosenView` it calls through
        `setView`, which is a temporal-dead-zone error waiting to happen if it
        is ever invoked during construction rather than after it. Running the
        real `after()` is the only thing that can see that."""
        calls = _run_after(collect(review), tmp_path)
        assert "listen:click" in calls

    def test_switching_documents_and_back_does_not_throw(self, review, tmp_path):
        """The switch rebinds `pre`, `rendered` and `rawText`. A stale handle
        would not raise -- it would quietly keep operating on the previous
        document, which is the bug this whole change is about -- so the value
        here is that the path is executed at all."""
        paper = _mixed_package(review.parent)
        out = build_bundle(review, out_dir=tmp_path / "b", paper_dir=paper)
        payload = json.loads((out / "viewer.html").read_text().split(
            '<script type="application/json" id="payload">', 1)[1]
            .split("</script>", 1)[0])
        assert "switched" in _run_after(payload, tmp_path / "run")


class TestTheSyncContractIsStatedPerDocument:
    def test_the_page_names_all_three_locate_modes(self, review, tmp_path):
        paper = _mixed_package(review.parent)
        out = build_bundle(review, out_dir=tmp_path / "b", paper_dir=paper)
        payload = json.loads((out / "viewer.html").read_text().split(
            '<script type="application/json" id="payload">', 1)[1]
            .split("</script>", 1)[0])
        modes = {d["locate"] for d in payload["source_docs"]}
        assert {"lines", "dom", "none"} <= modes

    def test_both_directions_are_implemented_for_non_pdf_documents(
            self, review, tmp_path):
        """A DOM document has elements with text where a PDF has line boxes, so
        the same scoring works on both. Refusing the sync for everything that is
        not a PDF would have been the easy answer and a much worse pane."""
        html = render_viewer(collect(review))
        assert "domSpans" in html
        assert "locateInExtraction" in html
        assert "_bestSpan" in html

    def test_an_evidence_link_returns_to_the_paper_first(self, review, tmp_path):
        """`applyJump` scrolls to `#pg{n}`, which lives inside a wrapper the
        selector hides whenever the reader is on a supplement --
        `scrollIntoView` on a hidden element does nothing. So a reader who had
        looked at a supplement got silence from every "show p.7" link."""
        html = render_viewer(collect(review))
        assert "__srcSelectDoc" in html
        i = html.find("function applyJump")
        assert "__srcSelectDoc" in html[i:i + 900]
