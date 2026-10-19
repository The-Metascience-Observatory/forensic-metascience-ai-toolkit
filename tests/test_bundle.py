"""The bundle must be self-contained and must not lie about what it holds.

The viewer is opened by double-clicking, which means `file://`, which means
`fetch` is blocked. Anything the viewer RENDERS has to be embedded; anything it
merely offers can be linked, because navigation works where fetch does not. A
viewer that fetches its own data looks fine when served over HTTP and shows
empty panels when a user actually opens it.
"""
import json
import re
import shutil
import subprocess

import pathlib
import pytest

from metascience_agent.bundle import build_bundle, collect, render_viewer
from metascience_agent.version import NOT_RECORDED

#: A DOM stub thin enough to let the viewer's top-level code run and no
#: thinner. The section builders are the only thing under test here, but they
#: live at the bottom of a script that mounts a nav bar on load, so the script
#: must reach the end before `S` can be asked for anything. Everything a
#: builder needs is in `D`; everything else is a no-op.
#:
#: WHY EXECUTE IT AT ALL: the dropdowns, the finding order and the audit table
#: are all computed in the browser from the payload. A test that greps the
#: rendered HTML for a JS source line pins the code, not the behaviour -- it
#: passes just as happily when the option list is built from the wrong array.
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


def flat(html: str) -> str:
    """One space between words. The section builders are indented template
    literals, so a rendered sentence is broken by a newline and leading spaces
    wherever the SOURCE wrapped -- an assertion on a phrase would otherwise be
    an assertion on where a line happened to end."""
    return " ".join(str(html).split())


def _css_rules(payload: dict) -> dict:
    """`{selector: declarations}` for the viewer's stylesheet.

    Comments are stripped FIRST. A rule regex run over the raw sheet swallows
    the comment block above each rule into its selector, and this file's
    comments are paragraphs."""
    css = render_viewer(payload).split("<style>")[1].split("</style>")[0]
    css = re.sub(r"/\*.*?\*/", " ", css, flags=re.S)
    out = {}
    for m in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        for sel in m.group(1).split(","):
            out.setdefault(" ".join(sel.split()), "")
            out[" ".join(sel.split())] += m.group(2)
    return out


def _text(html: str) -> str:
    """Tags stripped, whitespace collapsed. `sev()` wraps each severity word in
    a span, so a rendered "consistent 3" contains markup between the two."""
    return " ".join(re.sub(r"<[^>]+>", " ", str(html)).split())


def section_html(payload: dict, section_id: str, tmp_path) -> str:
    """Render one viewer section by RUNNING it, the way a reader gets it."""
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


@pytest.fixture
def review(tmp_path):
    paper = tmp_path / "10.1234--demo"
    rev = paper / "forensic_review"
    rev.mkdir(parents=True)
    (paper / "body.md").write_text("# Body\n\nSome text.")
    (paper / "10.1234--demo.pdf").write_bytes(b"%PDF-1.4 fake")
    (rev / "findings.json").write_text(json.dumps({
        "paper_id": "10.1234--demo",
        "paper_title": "A demonstration paper",
        "paper_metadata": {"authors": "Doe, J.", "year": "2026", "doi": "10.1234/demo"},
        "anatomy": {
            "studies": [{"id": "s1", "label": "Study 1", "n": 40}],
            "variables": [{"id": "v1", "name": "Age", "family": "continuous",
                           "measurement_level": "ratio", "role": "covariate"}],
            "tests": [{"id": "t1", "test_type": "t_test", "location": "Table 1",
                       "outcome_var": "v1", "predictor_vars": []}],
        },
        "findings": [{"id": "f1", "severity": "suspicious", "location": "Table 1",
                      "technique": "grim", "reproduction": "metascience grim 5.5 30"}],
        "coverage": {"stats_found": 5},
        "unchecked": [{"location": "Fig 2", "reason": "figure"}],
    }))
    (rev / "report.md").write_text("# Forensic review\n\n**Bold** text.\n")
    (rev / "report.json").write_text(json.dumps({"verdict": "unresolved"}))
    (rev / "run_meta.json").write_text(json.dumps({
        "total_cost_usd": 12.5, "total_wall_seconds": 900,
        "stages": {"editorial": {"verdict": "unresolved", "confidence": "high"}},
    }))
    (rev / "sandbox_audit.json").write_text(json.dumps({"breaches": 0}))
    (rev / "toolcalls.stage1.json").write_text(json.dumps([
        {"seq": 1, "tool_short": "grim_check", "surface": "mcp", "validated": True,
         "input": {"mean": 5.5, "n": 30}, "result": '{"severity": "consistent"}'},
        {"seq": 2, "tool_short": "Read", "surface": "builtin_allowed", "validated": False,
         "input": {"file_path": "body.md"}, "result": "x" * 9000},
    ]))
    return rev


class TestCollect:
    def test_pulls_identity_and_anatomy(self, review):
        p = collect(review)
        assert p["paper_title"] == "A demonstration paper"
        assert len(p["anatomy"]["variables"]) == 1

    def test_report_markdown_is_prerendered_to_html(self, review):
        """Pre-rendered in Python because the viewer may not use a CDN."""
        assert "<strong>Bold</strong>" in collect(review)["report_html"]

    def test_tool_results_are_clipped(self, review):
        """A `Read` result can be an entire file; the ledger is for seeing what
        ran with which inputs."""
        big = [c for c in collect(review)["calls"] if c["tool"] == "Read"][0]
        assert len(big["result"]) < 9000
        assert "[clipped]" in big["result"]

    def test_severity_is_lifted_out_of_the_result(self, review):
        c = [x for x in collect(review)["calls"] if x["tool"] == "grim_check"][0]
        assert c["severity"] == "consistent"

    def test_unvalidated_surface_is_preserved(self, review):
        c = [x for x in collect(review)["calls"] if x["tool"] == "Read"][0]
        assert c["validated"] is False


class TestViewerIsSelfContained:
    def test_no_external_resources(self, review):
        """No resource may be LOADED from the network.

        This used to forbid `href="http` outright, which also caught an
        ordinary outbound hyperlink -- a DOI pointing at doi.org. That is
        navigation, not loading, and the distinction is the one this file's
        own docstring draws: what the viewer renders must be embedded, what it
        merely offers may be linked. A stylesheet or a script fetched over the
        network still breaks the bundle and is still forbidden.
        """
        html = render_viewer(collect(review))
        assert 'src="http' not in html
        assert "cdn." not in html
        assert not re.search(r'<link[^>]+href="http', html)
        assert not re.search(r'@import\s+(url\()?["\']?http', html)

    def test_an_outbound_hyperlink_is_allowed(self, review):
        """The DOI is a link to the paper. Navigation works from file:// where
        fetch does not, so linking out is safe and useful."""
        meta = json.loads((review / "findings.json").read_text())
        meta["paper_metadata"]["doi"] = "10.1234/demo"
        (review / "findings.json").write_text(json.dumps(meta))
        assert "doi.org" in render_viewer(collect(review))

    def test_no_fetch_or_xhr(self, review):
        """file:// blocks fetch. A viewer that fetches shows empty panels."""
        html = render_viewer(collect(review))
        assert "fetch(" not in html
        assert "XMLHttpRequest" not in html

    def test_payload_is_valid_json(self, review):
        html = render_viewer(collect(review))
        m = re.search(r'id="payload">(.*?)</script>', html, re.S)
        assert json.loads(m.group(1))["paper_id"] == "10.1234--demo"

    def test_payload_cannot_terminate_the_script_tag(self, review):
        """An unescaped </script> inside the data ends the block early and the
        rest of the page becomes visible garbage."""
        p = collect(review)
        p["paper_title"] = 'evil </script><script>alert(1)</script>'
        html = render_viewer(p)
        body = re.search(r'id="payload">(.*?)</script>', html, re.S).group(1)
        assert "</script>" not in body

    def test_disclaimer_is_present(self, review):
        assert "NOT adequate" in render_viewer(collect(review))


class TestBuildBundle:
    def test_creates_the_expected_layout(self, review, tmp_path):
        out = build_bundle(review, tmp_path / "b")
        assert (out / "viewer.html").exists()
        assert (out / "README.txt").exists()
        assert (out / "paper" / "body.md").exists()
        assert (out / "paper" / "10.1234--demo.pdf").exists()
        assert (out / "analysis" / "findings.json").exists()

    def test_the_pdf_is_linked_not_embedded(self, review, tmp_path):
        """Embedding a 1 MB PDF as base64 would triple the viewer's size for
        something the browser opens perfectly well by navigation.

        The href is built at runtime from the payload, so assert on the payload
        and on the absence of a data URI rather than on a literal href.
        """
        out = build_bundle(review, tmp_path / "b")
        html = (out / "viewer.html").read_text()
        payload = json.loads(re.search(r'id="payload">(.*?)</script>', html, re.S).group(1))
        assert payload["pdf_name"] == "10.1234--demo.pdf"
        assert "data:application/pdf" not in html
        assert (out / "paper" / "10.1234--demo.pdf").exists()

    def test_missing_optional_files_do_not_break_it(self, tmp_path):
        rev = tmp_path / "paper" / "forensic_review"
        rev.mkdir(parents=True)
        (rev / "findings.json").write_text("{}")
        out = build_bundle(rev, tmp_path / "b")
        assert (out / "viewer.html").exists()

    def test_rejects_a_non_directory(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            build_bundle(tmp_path / "nope")


class TestTheBundleDoesNotShipTheOperatorsMachine:
    """The bundle is FORWARDABLE -- it is built to be sent to the authors of
    the paper it criticises -- and it shipped the reviewer's laptop with it.

    MEASURED on `10.1002--eat.24415/forensic_review_wave3_bundle` before this:
    `viewer.html` carried 24 occurrences of `/mnt/c/Users/gregs/...`, 21 of
    `/home/gsfitzgerald/...`, 21 session UUIDs and the run's `total_cost_usd`;
    `analysis/report.md` carried the home directory on 5 lines. None of it is a
    fact about the paper.
    """

    LEAK = ("/home/operator/checkout/paper.xml "
            "/mnt/c/Users/operator/checkout/paper.xml "
            "session d16df72b-e488-4d75-b93f-bd7f8e5af18a")

    @pytest.fixture
    def leaky(self, review):
        (review / "report.md").write_text(
            f"# Forensic review\n\n**Reproduce:** `metascience extract-xml "
            f"--xml-path {self.LEAK}`\n")
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0]["reproduction"] = f"metascience grim --xml {self.LEAK}"
        (review / "findings.json").write_text(json.dumps(f))
        return review

    def test_the_viewer_carries_no_home_directory(self, leaky):
        html = render_viewer(collect(leaky))
        assert "/home/operator" not in html
        assert "/mnt/c/Users/operator" not in html
        # Collapsed, not deleted: the command still reads as a path and runs
        # once the reader substitutes their own checkout.
        assert "<home>/checkout/paper.xml" in html

    def test_the_viewer_carries_no_session_id(self, leaky):
        assert "d16df72b-e488-4d75-b93f-bd7f8e5af18a" not in render_viewer(collect(leaky))
        assert "<session-id>" in render_viewer(collect(leaky))

    def test_the_viewer_carries_no_run_cost(self, review):
        """All three spellings `run_meta` writes a price into: the run total,
        the per-stage `cost_usd`, and the vendor's own `costUSD` inside
        `model_usage`. Asserted against the embedded payload, not the whole
        file: "12.5" is also a font size in the stylesheet, and a test that
        cannot tell those apart would pass on the wrong reason forever."""
        meta = json.loads((review / "run_meta.json").read_text())
        meta["stages"]["editorial"].update(
            {"cost_usd": 3.07, "model_usage": {"opus": {"costUSD": 3.07}}})
        (review / "run_meta.json").write_text(json.dumps(meta))
        html = render_viewer(collect(review))
        assert "$12.5000" not in html

        def keys(v):
            if isinstance(v, dict):
                return [k for k, x in v.items() for k in [k] + keys(x)]
            if isinstance(v, list):
                return [k for x in v for k in keys(x)]
            return []

        payload = json.loads(re.search(r'id="payload">(.*?)</script>', html, re.S).group(1))
        assert not [k for k in keys(payload) if "cost" in str(k).lower()]

    def test_the_copied_report_md_is_scrubbed(self, leaky, tmp_path):
        """The one analysis file a reader opens, and the one that gets
        forwarded on its own."""
        out = build_bundle(leaky, tmp_path / "b")
        copied = (out / "analysis" / "report.md").read_text()
        assert "/home/operator" not in copied
        assert "/mnt/c/Users/operator" not in copied
        assert "d16df72b" not in copied
        assert "<home>/checkout/paper.xml" in copied
        # The original is untouched: it is the record of what was produced.
        assert "/home/operator" in (leaky / "report.md").read_text()

    def test_the_papers_own_text_is_left_byte_exact(self, review):
        """The paper is EVIDENCE, and the click-to-source sync indexes it by
        character offset -- a substitution inside it would move every finding's
        anchor onto the wrong sentence. A path printed in a data-availability
        statement is the authors' own text, not our leak."""
        body = review.parent / "body.md"
        body.write_text("Data are at /home/authorlab/study/data.csv\n")
        assert collect(review)["body_text"] == body.read_text()

    def test_the_corresponding_author_email_is_kept(self, review):
        """DELIBERATELY NOT STRIPPED. Whether the address the review is
        addressed to belongs in the forwarded bundle is an editorial call for
        the repo owner, not something this scrubber should decide silently.
        Pinned so that removing it is a decision, not a side effect."""
        f = json.loads((review / "findings.json").read_text())
        f["paper_metadata"]["corresponding_email"] = "a.author@university.edu"
        (review / "findings.json").write_text(json.dumps(f))
        assert "a.author@university.edu" in render_viewer(collect(review))

    def test_the_readme_says_the_raw_logs_are_not_scrubbed(self, review, tmp_path):
        """Partial scrubbing that looks total is worse than none: the operator
        must know that `analysis/` is still the unedited record."""
        out = build_bundle(review, tmp_path / "b")
        readme = (out / "README.txt").read_text()
        assert "BEFORE FORWARDING" in readme
        assert "analysis/" in readme


class TestViewerJavaScriptIsValid:
    """The viewer's JS must actually parse.

    A backtick inside a section builder -- including inside an HTML comment --
    terminates the surrounding template literal and breaks the entire page with
    "Unexpected identifier". Every section then renders blank, and nothing in
    the Python test suite notices, because the failure is in the browser.

    This happened: a comment reading "`n` means sample size" took the whole
    viewer down and was caught only by a headless render.
    """

    def _script(self, review):
        html = render_viewer(collect(review))
        # The last <script> block is the viewer logic.
        return html.rsplit("<script>", 1)[1].split("</script>")[0]

    def test_node_parses_the_script(self, review, tmp_path):
        import shutil
        import subprocess

        node = shutil.which("node") or shutil.which("nodejs")
        if not node:
            pytest.skip("node not available")
        f = tmp_path / "viewer.js"
        f.write_text(self._script(review))
        # --check parses without executing (no DOM needed).
        r = subprocess.run([node, "--check", str(f)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr

    def test_severity_column_is_not_headed_n(self, review):
        """`n` is sample size. Using it to count findings is the category error
        this toolkit exists to catch."""
        script = self._script(review)
        assert "'severity','n'" not in script.replace(" ", "")
        assert "findings" in script


class TestAnchoring:
    """Findings must be locatable in the paper.

    Done at BUILD time because the browser's built-in PDF viewer exposes almost
    no API -- it can jump to a page with `#page=N` and reports no click position
    and no text coordinates. Resolving the page here is what makes "show me this
    in the paper" possible without bundling pdf.js.
    """

    def test_prose_quote_is_found_in_the_pdf_text(self):
        from metascience_agent.bundle import _locate
        pages = ["", "the sample began with 68 pennsylvania and missouri coalitions", ""]
        got = _locate("The sample began with 68 Pennsylvania and Missouri coalitions",
                      pages, "")
        assert got["page"] == 2

    def test_a_table_row_is_found_by_its_numbers(self):
        """Table quotes are markdown reconstructions and NEVER match the PDF
        verbatim. Exact matching alone found 5 of 36 findings on a real paper;
        numeric-token scoring took it to 33."""
        from metascience_agent.bundle import _locate
        pages = ["unrelated 9.99 text", "constant -4.51 (1.50) <.001 and 3.16 (0.98)"]
        got = _locate("Constant | - 4.51 (1.50) | <.001 | 3.16 (0.98)", pages, "")
        assert got["page"] == 2

    def test_a_single_shared_number_is_not_a_location(self):
        """One number in common is a coincidence, not a match."""
        from metascience_agent.bundle import _locate
        pages = ["something 4.51 elsewhere", "nothing relevant here at all"]
        assert "page" not in _locate("Constant | - 4.51", pages, "")

    def test_text_offset_is_recorded(self):
        from metascience_agent.bundle import _locate, _norm
        body = "preamble. the mean level of engaging communication was 3.83 on a scale"
        got = _locate("The mean level of engaging communication was 3.83", [], _norm(body))
        assert got["text_index"] == _norm(body).index("the mean level")

    def test_findings_without_a_quote_are_left_alone(self):
        from metascience_agent.bundle import anchor_findings
        out = anchor_findings([{"id": "x", "severity": "suspicious"}], None, "")
        assert "_anchor" not in out[0]

    def test_anchoring_survives_a_missing_pdf(self):
        from metascience_agent.bundle import anchor_findings
        out = anchor_findings([{"id": "x", "quote": "some text"}], None, "some text here")
        assert out[0]["_anchor"]["text_index"] == 0


class TestSourceViewLimits:
    def test_both_sync_directions_exist(self, review):
        """Both directions now work. The earlier build could only go
        text -> PDF, and even that stopped working after first load because
        Chrome's built-in viewer ignores a `#page=N` change once the document
        is loaded. Pages are rendered here instead, so neither limit applies.

        The direction names moved from "PDF" to "SOURCE" when the left pane
        stopped assuming a PDF. The same two directions now hold for an HTML,
        EPUB, spreadsheet or plain-text document; naming them after one format
        is what let the pane be built as though PDFs were all there is.
        """
        html = render_viewer(collect(review))
        assert "SOURCE -> text" in html
        assert "text -> SOURCE" in html

    def test_the_builtin_pdf_viewer_is_no_longer_used(self, review):
        """An <iframe> to the PDF would reintroduce exactly the bug this
        replaced: no click position, no text coordinates, and fragment
        navigation that silently stops working."""
        html = render_viewer(collect(review))
        assert "<iframe" not in html

    def test_the_pdf_pane_defaults_to_two_thirds(self, review):
        assert "flex:0 0 66%" in render_viewer(collect(review))

    def test_the_nav_can_be_collapsed(self, review):
        html = render_viewer(collect(review))
        assert "navhid" in html and "navtoggle" in html


class TestGuardsReachTheViewer:
    """The Guards pane said "No guard audit recorded for this run" on every run
    ever produced, because `collect` read a top-level `guard_audit.json` that
    nothing has ever written. `_guard_audit` runs on every stage and nests its
    result at `sandbox_audit.stages.<stage>.guards`; on the run this was found
    on, 7 of 9 guard slots were supplied and the per-tool breakdown was sitting
    in the file next to it.

    This matters more than a cosmetic pane: supplied the wrong scale bounds,
    GRIM does not get vaguer, it inverts. A defaulted guard is the single most
    likely cause of a false accusation in the report.
    """

    GUARDS = {
        "n_guarded_calls": 5, "n_guard_slots": 9, "n_supplied": 7,
        "n_defaulted": 2, "supplied_rate": 0.7778,
        "per_tool": {"check_table": {"supplied": 4, "defaulted": 2}},
        "defaulted_calls": [{"seq": 11, "tool": "check_table",
                             "guard": "provenance",
                             "consequence": "a value's origin was unrecorded"}],
    }

    def _with_guards(self, review):
        (review / "sandbox_audit.json").write_text(json.dumps({
            "verdict": "clean", "n_unvalidated_total": 0,
            "stages": {"stage1": {"guards": self.GUARDS}},
        }))
        return collect(review)

    def test_guards_are_read_from_the_sandbox_audit(self, review):
        assert self._with_guards(review)["guard_audit"]["stage1"]["n_supplied"] == 7

    def test_a_run_without_guards_yields_an_empty_map_not_a_crash(self, review):
        assert collect(review)["guard_audit"] == {}

    def test_the_per_tool_breakdown_survives_into_the_page(self, review):
        """Pages are built client-side, so what `render_viewer` can be held to
        is that the data reaches the embedded payload -- not that the DOM is
        right. The template's own use of it is covered by the Node parse test."""
        html = render_viewer(self._with_guards(review))
        assert '"per_tool"' in html and "check_table" in html

    def test_the_defaulted_guard_and_its_consequence_both_reach_the_page(self, review):
        html = render_viewer(self._with_guards(review))
        assert "a value's origin was unrecorded" in html
        assert '"guard": "provenance"' in html

    def test_the_template_reads_the_fields_the_audit_actually_writes(self, review):
        """The old code did `JSON.stringify(g)` into a `<pre>`, so it could not
        be wrong about field names. The replacement names them, and `guard` is
        singular per row -- the first version of this fix read `c.defaulted`
        and rendered an empty column."""
        html = render_viewer(self._with_guards(review))
        for field in ("supplied_rate", "n_guard_slots", "per_tool",
                      "defaulted_calls", "c.guard", "c.consequence"):
            assert field in html, field


class TestTheFilesListDoesNotLie:
    """It named `body.md` unconditionally. No XML-fetched paper has one, so the
    link 404'd on exactly the kind of paper most likely to be under review."""

    def test_a_file_that_exists_is_listed(self, review):
        paths = [f["path"] for f in collect(review)["files"]]
        assert "paper/body.md" in paths
        assert "analysis/findings.json" in paths

    def test_a_file_that_does_not_exist_is_not_listed(self, review):
        (review.parent / "body.md").unlink()
        paths = [f["path"] for f in collect(review)["files"]]
        assert "paper/body.md" not in paths
        assert "analysis/findings.json" in paths        # the rest survive

    def test_report_json_absent_is_not_linked(self, review):
        (review / "report.json").unlink()
        assert "analysis/report.json" not in [f["path"] for f in collect(review)["files"]]

    def test_every_file_carries_a_description(self, review):
        assert all(f["what"].strip() for f in collect(review)["files"])

    def test_the_dead_analysis_names_are_gone(self):
        """`tool_ledger.json` and `guard_audit.json` were listed for copying long
        after the writers changed name. Nothing has ever written either."""
        from metascience_agent.bundle import _ANALYSIS_FILES
        assert "tool_ledger.json" not in _ANALYSIS_FILES
        assert "guard_audit.json" not in _ANALYSIS_FILES


class TestPaperFacts:
    """The Overview showed a title, a citation and a severity count -- nothing
    about how complete the material behind the review was. All of these were
    computed elsewhere already and none of them reached the page."""

    def _facts(self, review, **kw):
        return {f["fact"]: f for f in collect(review, **kw)["paper_facts"]}

    def test_a_malformed_registry_id_is_reported_as_malformed(self, review):
        """Romano prints `NCT0204349` -- seven digits where NCT numbers have
        eight. The strict pattern correctly rejects it, but reporting "not
        detected" hides the more interesting case: a registration was claimed
        and it resolves to nothing."""
        (review.parent / "body.md").write_text("Registered as NCT0204349 at baseline.")
        f = self._facts(review)["Registry ID"]
        assert "NCT0204349" in f["value"] and "malformed" in f["value"]

    def test_a_well_formed_registry_id_is_not_called_malformed(self, review):
        (review.parent / "body.md").write_text("Registered as NCT02043496.")
        f = self._facts(review)["Registry ID"]
        assert "malformed" not in f["value"]

    def test_no_registry_id_at_all_uses_the_shared_wording(self, review):
        """Every unfilled row says the same thing, supplied once by the
        fixed-schema pass. "not detected" was rejected in review for implying
        a search wider than the paper."""
        assert self._facts(review)["Registry ID"]["value"] == "not mentioned in paper"

    def test_a_declared_but_unfetched_supplement_is_not_blamed_on_the_paper(self, review):
        """`supplements.audit` scans the paper's TEXT and on Romano found
        nothing, while the fetch manifest recorded that Europe PMC had listed a
        file that was never retrieved. Text silence is not evidence of absence,
        and the row must not read as a fault of the authors."""
        (review.parent / "x_supplementary_info.json").write_text(json.dumps({
            "status": "incomplete",
            "providers": [{"name": "europepmc_supplements", "status": "ok", "listed": 1}],
        }))
        f = self._facts(review)["Supplementary material"]
        assert f["value"] == "1 declared, none supplied to this review"
        assert "not a fault of the paper" in f["detail"].lower()

    def test_page_renders_are_not_counted_as_figures(self, review):
        """`figures/` holds the extractor's full-page `page_NNN.png` images
        beside the crops, so a directory glob reported two figures for a paper
        that has one."""
        figs = review / "figures"
        figs.mkdir()
        (figs / "Figure_1_p019.png").write_bytes(b"x")
        (figs / "page_019.png").write_bytes(b"x")
        assert self._facts(review)["Figures"]["value"] == "1 extracted"

    def test_no_figures_says_the_review_is_figure_blind(self, review):
        assert "figure-blind" in self._facts(review)["Figures"]["detail"]

    def test_absence_is_never_stated_as_absence(self, review):
        """Every one of these is a regex scan over extracted text. A
        data-availability statement dropped in conversion is indistinguishable
        from one that was never written, so the wording must not claim it."""
        for f in collect(review)["paper_facts"]:
            assert "not present in the paper" not in f["value"].lower()
            assert "the paper does not" not in f["value"].lower()


class TestRunFacts:
    def test_the_timestamp_fallback_says_it_is_a_fallback(self, review):
        """A file date is not a run date; presenting one as the other is worse
        than omitting it."""
        f = {x["fact"]: x for x in collect(review)["run_facts"]}["Analysed"]
        assert "file's timestamp" in f["detail"]

    def test_a_recorded_timestamp_is_used_verbatim_and_unqualified(self, review):
        meta = json.loads((review / "run_meta.json").read_text())
        meta["analysed_at"] = "2026-08-02 09:00 UTC"
        meta["version"] = "0.1.0"
        (review / "run_meta.json").write_text(json.dumps(meta))
        facts = {x["fact"]: x for x in collect(review)["run_facts"]}
        assert facts["Analysed"]["value"] == "2026-08-02 09:00 UTC"
        assert facts["Analysed"]["detail"] == ""
        # The row is "Pipeline version" and carries the COMPOSITE, not the bare
        # release number it used to print under the label "Toolkit version". The
        # release number moves about once a month while the code moves several
        # times a day, so "0.1.0" alone never identified what ran. The label
        # matches the report's wording so the two surfaces name one fact once.
        assert facts["Pipeline version"]["value"] == f"v0.1.0 (commit {NOT_RECORDED})"

    def test_the_pipeline_row_names_the_commit_when_one_was_recorded(self, review):
        meta = json.loads((review / "run_meta.json").read_text())
        meta.update({"analysed_at": "2026-08-02 09:00 UTC", "version": "0.2.0",
                     "git_sha": "1a2b3c4d5e6f", "git_dirty": True})
        (review / "run_meta.json").write_text(json.dumps(meta))
        facts = {x["fact"]: x for x in collect(review)["run_facts"]}
        assert facts["Pipeline version"]["value"] == (
            "v0.2.0 (g1a2b3c4d5e6f, uncommitted changes)")

    def test_wall_time_is_carried(self, review):
        facts = {x["fact"]: x for x in collect(review)["run_facts"]}
        assert facts["Wall time"]["value"] == "15 min"

    def test_the_run_cost_is_not_a_row(self, review):
        """This row printed `total_cost_usd` to 4 dp. The bundle is forwarded
        to the authors of the paper it criticises, and what the review cost us
        is a fact about our billing -- printed beside a verdict it reads as a
        price put on the accusation. It stays in the review directory's
        `run_meta.json`, which is not the shippable artefact."""
        facts = {x["fact"] for x in collect(review)["run_facts"]}
        assert not [f for f in facts if "cost" in f.lower()]


class TestSeverityIsSetInTheBodyFace:
    def test_the_shouting_is_gone(self, review):
        """11px/700/uppercase/letter-spaced made the word shout in every table
        cell it appeared in. Colour carries the level; rule weight carries it
        again for anyone who cannot use the colour."""
        css = render_viewer(collect(review)).split(".sev{")[1].split("}")[0]
        for shout in ("text-transform", "letter-spacing", "font-weight", "font-size"):
            assert shout not in css, shout

    def test_the_level_colours_survive(self, review):
        html = render_viewer(collect(review))
        assert ".sev{color:var(--flag)}" in html
        assert ".sev.suspicious{color:var(--warn)}" in html


class TestTheMetadataTableIsAFixedSchema:
    """"this metadata section must be the same for ALL the papers ... I get a
    sense that this table is being constructed ad hoc, and I absolutely don't
    want that." -- and it was: rows were appended only when a value was found,
    so a paper with no DOI produced a table with no DOI row. Two papers were
    then not comparable, and absence hid itself by making the list shorter."""

    def _rows(self, review):
        return [f["fact"] for f in collect(review)["paper_facts"]]

    def test_every_row_is_present_for_a_rich_paper(self, review):
        from metascience_agent.bundle import _METADATA_ROWS
        assert self._rows(review) == list(_METADATA_ROWS)

    def test_every_row_is_present_for_an_empty_paper(self, tmp_path):
        from metascience_agent.bundle import _METADATA_ROWS
        rev = tmp_path / "bare" / "forensic_review"
        rev.mkdir(parents=True)
        (rev / "findings.json").write_text("{}")
        assert [f["fact"] for f in collect(rev)["paper_facts"]] == list(_METADATA_ROWS)

    def test_two_papers_produce_the_same_shape(self, review, tmp_path):
        rev = tmp_path / "other" / "forensic_review"
        rev.mkdir(parents=True)
        (rev / "findings.json").write_text("{}")
        assert self._rows(review) == [f["fact"] for f in collect(rev)["paper_facts"]]

    def test_an_unfilled_row_says_it_was_not_in_the_paper(self, review):
        """"not detected" was rejected in review for implying a search wider
        than the paper itself ever took place."""
        rows = {f["fact"]: f["value"] for f in collect(review)["paper_facts"]}
        assert rows["Preregistration"] == "not mentioned in paper"
        assert "not detected" not in rows.values()

    def test_a_missing_bibliographic_field_is_not_blamed_on_the_paper(self, tmp_path):
        """A volume we failed to extract is our gap, not the paper's silence."""
        rev = tmp_path / "bare" / "forensic_review"
        rev.mkdir(parents=True)
        (rev / "findings.json").write_text("{}")
        rows = {f["fact"]: f["value"] for f in collect(rev)["paper_facts"]}
        assert rows["Volume"] == "not recorded"


class TestSankey:
    def test_a_finding_flows_from_the_tool_that_produced_it(self, review):
        s = collect(review)["sankey"]
        assert {"source": "grim_check", "target": "suspicious", "value": 1} in s["links"]

    def test_a_technique_naming_a_family_still_joins(self, review):
        """`technique: grim` against a `grim_percentage` call. Reuses
        `severity_reconcile._candidate_tools` rather than a second copy of the
        family map -- getting it wrong would attribute findings to tools that
        never ran."""
        (review / "toolcalls.stage1.json").write_text(json.dumps([
            {"seq": 1, "tool_short": "grim_percentage", "surface": "mcp",
             "validated": True, "input": {"percent": 71.0, "n": 142},
             "result": '{"severity": "consistent"}'}]))
        s = collect(review)["sankey"]
        assert any(l["source"] == "grim_percentage" for l in s["links"])

    def test_a_hand_computed_finding_is_named_as_such(self, review):
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0]["technique"] = "manual"
        (review / "findings.json").write_text(json.dumps(f))
        s = collect(review)["sankey"]
        assert any(l["source"] == "hand-computed" for l in s["links"])

    def test_a_tool_that_found_nothing_gets_an_explicit_sink(self, review):
        """"ran and found nothing" and "never ran" are different facts, and a
        diagram that omits the first implies the second."""
        calls = json.loads((review / "toolcalls.stage1.json").read_text())
        calls.append({"seq": 3, "tool_short": "statcheck", "surface": "mcp",
                      "validated": True, "input": {"text": "t(28)=2.1, p=.04"},
                      "result": '{"severity": "consistent"}'})
        (review / "toolcalls.stage1.json").write_text(json.dumps(calls))
        s = collect(review)["sankey"]
        assert {"source": "statcheck", "target": "no finding", "value": 1} in s["links"]

    def test_unvalidated_calls_do_not_appear(self, review):
        """The `Read` call in the fixture is not a forensic result."""
        s = collect(review)["sankey"]
        assert not any(l["source"] == "Read" for l in s["links"])

    def test_it_is_empty_rather_than_broken_with_no_data(self, tmp_path):
        rev = tmp_path / "bare" / "forensic_review"
        rev.mkdir(parents=True)
        (rev / "findings.json").write_text("{}")
        assert collect(rev)["sankey"] == {"nodes": [], "links": []}


class TestReferencesAndAuthors:
    def test_references_reach_the_payload(self, review):
        assert collect(review)["references"] == []      # no XML in the fixture

    def test_an_existing_references_json_is_preferred(self, review):
        (review.parent / "references.json").write_text(json.dumps(
            [{"id": 1, "title": "A cited work", "doi": "10.1/x"}]))
        assert collect(review)["references"][0]["title"] == "A cited work"


class TestTheExtractionPaneCanAnswerItsOwnQuestion:
    """The pane exists so a reader can see whether the tables survived
    extraction. Rendering the markdown alone cannot show that: the XML path
    deliberately keeps table content OUT of the running text and emits
    `[TABLE 1: ...; see tables]` in its place, so that a model cannot
    transcribe numbers from prose that has lost the column alignment. Right for
    the checks, useless for this pane -- so the real grids are spliced back in.
    """

    def test_a_placeholder_becomes_the_actual_table(self, tmp_path):
        from metascience_agent.bundle import _TABLE_PLACEHOLDER, _md_table
        text = "[Table 1: Participant characteristics. — 2 rows x 2 cols; see tables]"
        assert _TABLE_PLACEHOLDER.search(text)
        assert _TABLE_PLACEHOLDER.search(text).group("name") == "Table 1"

    def test_a_grid_becomes_a_markdown_table(self):
        from metascience_agent.bundle import _md_table
        md = _md_table([["", "n (%)"], ["Age", "40 (37%)"]])
        assert md.splitlines()[0] == "|  | n (%) |"
        assert md.splitlines()[1] == "|---|---|"
        assert "| Age | 40 (37%) |" in md

    def test_a_pipe_inside_a_cell_cannot_shift_the_row(self):
        """An unescaped `|` opens a phantom column and moves every value in the
        row one place left -- exactly the class of error this pane reveals."""
        from metascience_agent.bundle import _md_table
        md = _md_table([["a", "b"], ["x|y", "z"]])
        assert r"x\|y" in md
        assert md.splitlines()[-1].count(" | ") == 1

    def test_ragged_rows_are_padded_not_dropped(self):
        from metascience_agent.bundle import _md_table
        md = _md_table([["a", "b", "c"], ["only one"]])
        assert md.splitlines()[-1] == "| only one |  |  |"

    def test_the_raw_text_is_kept_alongside_the_rendered_view(self, review):
        """The click-to-jump arithmetic indexes by character offset into the
        raw text; rendering destroys those offsets, so both are mounted."""
        html = render_viewer(collect(review))
        assert 'id="bodytext"' in html and 'id="bodyrender"' in html

    def test_the_pane_is_not_named_after_a_file_that_may_not_exist(self, review):
        """It was labelled "Extracted text (body.md)". No XML-fetched paper has
        a body.md, and the content comes from `paper_text` either way."""
        html = render_viewer(collect(review))
        assert "Extracted text (body.md)" not in html

    def test_the_figures_pane_is_present_even_with_no_figures(self, review):
        """Requested explicitly: the reader should see that the review is
        figure-blind, not see nothing at all."""
        html = render_viewer(collect(review))
        assert "figstrip" in html and "No figures were extracted" in html


class TestFigureRecords:
    def test_records_are_read_from_figures_json(self, review):
        figs = review / "figures"
        figs.mkdir()
        (figs / "figures.json").write_text(json.dumps({"figures": [
            {"label": "Figure 2", "page": 7, "caption": "A plot.",
             "image_path": "Figure_2_p007.png"}]}))
        recs = collect(review)["figure_records"]
        assert recs[0]["caption"] == "A plot." and recs[0]["page"] == 7

    def test_filenames_are_used_when_no_record_file_exists(self, review):
        """Every run so far wrote crops without a record file, so the page
        showed nothing rather than the figure sitting next to it."""
        figs = review / "figures"
        figs.mkdir()
        (figs / "Figure_1_p019.png").write_bytes(b"x")
        (figs / "page_019.png").write_bytes(b"x")
        recs = collect(review)["figure_records"]
        assert len(recs) == 1
        assert recs[0]["label"] == "Figure 1" and recs[0]["page"] == 19
        assert recs[0]["reconstructed_from_filename"] is True


class TestAcronyms:
    """Taken from the paper's own definitions, deterministically. An invented
    expansion of a clinical instrument would be worse than none, so this is
    code rather than a model, and precision beats recall."""

    def _a(self, text):
        from metascience_agent.bundle import _acronyms
        return {x["acronym"]: x["expansion"] for x in _acronyms(text)}

    def test_a_plain_definition_is_captured(self):
        got = self._a("We used ecological momentary assessment (EMA) throughout.")
        assert got["EMA"] == "ecological momentary assessment"

    def test_a_connecting_word_inside_the_acronym_is_allowed(self):
        """The A of PANAS is the "and". Skipping stopwords loses it; keeping
        them loses the ones that omit them -- so both alignments are tried."""
        got = self._a("the Positive and Negative Affect Schedule (PANAS; Watson 1988)")
        assert got["PANAS"] == "Positive and Negative Affect Schedule"

    def test_a_connecting_word_outside_the_acronym_is_skipped(self):
        got = self._a("the Profile of Mood States (POMS) was used")
        assert got["POMS"] == "Profile of Mood States"

    def test_a_trailing_citation_does_not_block_the_match(self):
        assert "POMS" in self._a("Profile of Mood States (POMS, 1971)")

    def test_the_shortest_matching_phrase_wins(self):
        """Longer phrases also match by prefix; taking the first swallowed half
        the sentence -- "individuals' engagement in disordered eating
        behaviors" once stood for DEBs."""
        got = self._a("individuals' engagement in disordered eating behaviors (DEBs)")
        assert got["DEBs"] == "disordered eating behaviors"

    def test_a_statistical_abbreviation_is_not_an_acronym(self):
        got = self._a("the mean age (SD) was 40, with a confidence interval (CI)")
        assert "SD" not in got and "CI" not in got

    def test_a_bracket_that_is_not_an_acronym_is_rejected(self):
        """The initials must line up. Without that check any bracketed capital
        after any words became a definition."""
        assert self._a("results were collected in London (UK) last year") == {}

    def test_a_year_is_not_an_acronym(self):
        assert self._a("as shown previously (2019) by others") == {}


class TestResearchPractice:
    """Reported separately from findings, and positively where present: these
    are pervasive across the literature, and a paper that preregistered has
    done something most have not. Burying that among arithmetic discrepancies
    reads as though it were another fault."""

    def _p(self, review):
        return {x["practice"]: x for x in collect(review)["practice"]}

    def test_unknown_is_not_a_polite_no(self, review):
        """Saying "no" where the extraction cannot see charges the authors for
        our blind spot."""
        rows = self._p(review)
        assert rows["Sample size justified"]["status"] == "unknown"

    def test_a_practice_that_is_present_is_reported_as_present(self, review):
        f = json.loads((review / "findings.json").read_text())
        f["anatomy"]["tests"] = [{"id": "t1", "test_type": "t",
                                  "assumption_checks_reported": ["normality"]}]
        (review / "findings.json").write_text(json.dumps(f))
        assert self._p(review)["Assumption checks reported"]["status"] == "yes"

    def test_some_but_not_all_is_partial(self, review):
        f = json.loads((review / "findings.json").read_text())
        f["anatomy"]["tests"] = [
            {"id": "t1", "assumption_checks_reported": ["normality"]},
            {"id": "t2", "assumption_checks_reported": []}]
        (review / "findings.json").write_text(json.dumps(f))
        assert self._p(review)["Assumption checks reported"]["status"] == "partial"

    def test_a_registry_id_without_a_preregistration_claim_is_partial(self, review):
        f = json.loads((review / "findings.json").read_text())
        f["anatomy"]["studies"] = [{"id": "s1", "registry_id": "NCT1"}]
        (review / "findings.json").write_text(json.dumps(f))
        assert self._p(review)["Preregistered"]["status"] == "partial"

    def _unread(self, tmp_path):
        """A review of a paper whose text never arrived: no body, no XML, no
        anatomy. It happens -- a failed fetch, a PDF the converter could not
        read -- and the bundle is still built."""
        rev = tmp_path / "10.9999--unread" / "forensic_review"
        rev.mkdir(parents=True)
        (rev / "findings.json").write_text(json.dumps(
            {"paper_id": "10.9999--unread", "findings": [], "anatomy": {}}))
        return rev

    def test_a_paper_that_was_never_read_is_charged_with_nothing(self, tmp_path):
        """FOUR rows used to say `no` here: Preregistered, Data or code shared,
        Reference list machine-readable and Figures available -- about a paper
        nothing had read. `no` in this table reads as a fault of the authors,
        and a `no` that means "we could not look" is the same class of error as
        a false accusation."""
        rows = self._p(self._unread(tmp_path))
        assert [r for r in rows.values() if r["status"] == "no"] == []
        for name in ("Preregistered", "Data or code shared",
                     "Reference list machine-readable",
                     "Figures available to the checks"):
            assert rows[name]["status"] == "unknown", name

    def test_the_true_negatives_survive_the_gate(self, review):
        """The gate must not turn every `no` into `unknown`. This paper's text
        WAS read and contains no repository link and no figures: those are
        findings about the paper and the row still says so."""
        rows = self._p(review)
        assert rows["Data or code shared"]["status"] == "no"
        assert rows["Figures available to the checks"]["status"] == "no"

    def test_no_studies_extracted_cannot_answer_the_prereg_question(self, review):
        """`preregistered` and `registry_id` are study-level fields, so with no
        studies the `any()` runs over an empty list and every paper scores
        `no`."""
        f = json.loads((review / "findings.json").read_text())
        f["anatomy"]["studies"] = []
        (review / "findings.json").write_text(json.dumps(f))
        row = self._p(review)["Preregistered"]
        assert row["status"] == "unknown"
        assert "not a fact about the paper" in row["detail"]

    def test_the_missing_supplement_is_blamed_on_this_review(self, review):
        """Split in two: whether the PAPER cites a supplement is a fact about
        the publication, and whether WE were given it is a fact about our
        inputs. One row answering both read as a fault of the paper."""
        body = review.parent / "body.md"
        body.write_text(body.read_text() + "\n\nSee Table S1 in the Supplementary "
                                           "Material for the full model.\n")
        rows = self._p(review)
        assert rows["Supplementary material cited by the paper"]["status"] == "yes"
        row = rows["Supplementary material supplied to this review"]
        assert row["status"] == "no"
        assert "not of the publication" in row["detail"]

    def test_no_supplement_at_all_is_not_blamed_on_anyone(self, review):
        """The old single row said "a property of OUR inputs" even when the
        paper cited no supplement -- apologising for a file that never was."""
        row = self._p(review)["Supplementary material supplied to this review"]
        assert row["status"] == "n/a"


class TestGlossary:
    def test_every_entry_has_a_plain_reading_and_an_example(self):
        from metascience_agent.bundle import GLOSSARY
        for g in GLOSSARY:
            assert g["plain"].strip() and g["example"].strip(), g["term"]

    def test_named_tools_are_real(self):
        """A glossary that points at a check we do not have is worse than one
        that admits the gap."""
        from metascience_agent.bundle import GLOSSARY
        from metascience_agent.registry import BY_NAME
        for g in GLOSSARY:
            for tool in g["detects"]:
                assert tool in BY_NAME, f"{g['term']} names unknown tool {tool}"

    def test_a_problem_we_cannot_detect_says_so(self):
        from metascience_agent.bundle import GLOSSARY
        multi = [g for g in GLOSSARY if g["term"] == "Multicollinearity"][0]
        assert multi["detects"] == ()


class TestTheTableExtractionErrorIsNotBlamedOnThePaper:
    """`extract_xml_text_with_tables` RETURNS its parse error rather than
    raising -- deliberately, so a malformed publisher file cannot burn a billed
    stage -- and the bundle dropped it on the floor. A corrupt XML and a paper
    with no tables both reached the viewer as an empty list, and the pane said
    "No tables were extracted... a limit of our extraction rather than evidence
    the paper has none" for both. True in one case, and in the other it hid a
    file we could not read behind a sentence about what our extractor cannot
    do.
    """

    def _paper(self, tmp_path, xml: str):
        rev = tmp_path / "10.4321--broken" / "forensic_review"
        rev.mkdir(parents=True)
        (rev / "findings.json").write_text(json.dumps({"paper_id": "x", "findings": []}))
        (rev.parent / "10.4321--broken.xml").write_text(xml)
        return rev

    def test_a_corrupt_xml_reaches_the_payload_as_an_error(self, tmp_path):
        rev = self._paper(tmp_path, "<article><body><p>unclosed")
        p = collect(rev)
        assert p["table_records"] == []
        assert p["table_extraction"]["error"], "the parse failure was discarded"
        assert p["table_extraction"]["xml"] is True

    def test_a_paper_with_no_publisher_file_carries_no_error(self, review):
        """No XML is not a broken XML, and saying "error" there would be the
        same defect pointed the other way."""
        p = collect(review)
        assert p["table_extraction"]["error"] == ""
        assert p["table_extraction"]["xml"] is False

    def test_the_error_is_rendered_where_the_empty_strip_is(self, tmp_path):
        rev = self._paper(tmp_path, "<article><body><p>unclosed")
        html = flat(section_html(collect(rev), "source", tmp_path))
        assert "The table extraction reported an error" in html
        assert "XML parse failed" in html
        assert "not because the paper has no tables" in html

    def test_a_good_paper_says_nothing_extra(self, review, tmp_path):
        html = flat(section_html(collect(review), "source", tmp_path))
        assert "The table extraction reported an error" not in html


class TestTheFindingsPageAgreesWithTheReport:
    """Two documents ship in one bundle and numbered their findings
    differently. `report.md` prints them through `report_render.sort_findings`
    -- severity, then CONSEQUENCE, then the model's `rank` -- and the viewer
    printed report.json's array order. MEASURED on the wave-3
    `10.1002--eat.24415` run: 4 of 10 numbered findings named a different
    finding in the two documents, and the viewer was the harsher of the two --
    it put a finding that changes nothing above one that moves a conclusion,
    because JS has the severity ladder but no consequence rank.
    """

    @pytest.fixture
    def graded(self, review):
        """Two equally severe findings whose CONSEQUENCE differs, in the order
        that severity alone cannot fix."""
        (review / "report.json").write_text(json.dumps({"verdict": "unresolved", "findings": [
            {"id": "e1", "rank": 1, "title": "Changes nothing", "severity": "suspicious",
             "consequence": {"flips_significance": False, "claims_affected": 0,
                             "basis": "asserted"}},
            {"id": "e2", "rank": 2, "title": "Flips a headline result",
             "severity": "suspicious",
             "consequence": {"flips_significance": True, "claims_affected": 3,
                             "basis": "computed"}},
        ]}))
        return review

    def test_the_payload_is_in_the_reports_order(self, graded):
        from metascience_agent.report_render import sort_findings
        got = [f["title"] for f in collect(graded)["report_obj"]["findings"]]
        want = [f["title"] for f in sort_findings(
            json.loads((graded / "report.json").read_text())["findings"])]
        assert got == want
        assert got[0] == "Flips a headline result"

    def test_report_json_on_disk_is_not_rewritten(self, graded):
        collect(graded)
        on_disk = json.loads((graded / "report.json").read_text())["findings"]
        assert [f["title"] for f in on_disk] == ["Changes nothing",
                                                 "Flips a headline result"]

    def test_the_page_numbers_match_the_payload(self, graded, tmp_path):
        html = section_html(collect(graded), "findings", tmp_path)
        assert re.search(r"<h3>1\. Flips a headline result", html)


class TestTheViewerDoesNotOfferACommandThatCannotRun:
    """`reproduction_valid is False` is the write path's verdict that the
    command does not run as printed. `report.md` refused to print such a command
    for that reason; the viewer printed it anyway, in a <pre>, because it starts
    with the word "metascience". On the wave-3 eat.24415 run that is 3 of 10
    findings, and what it pasted was the raw tool note: a 2.3 kB
    --tests '[{...}]' blob with unsubstituted placeholders that errors on first
    use. A command that fails when a reader tries it reads as a broken tool,
    which is worse than admitting the gap.

    `report.md` has since stopped printing a reproduction command at all, which
    makes this the ONLY surface that offers a reader one -- so this refusal is
    now the whole of the guarantee, not one half of it."""

    @pytest.fixture
    def invalid(self, review):
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0].update({
            "reproduction": "metascience multiplicity --tests '[{\"id\":\"a\"}]'",
            "reproduction_valid": False,
            "reproduction_problem": "contains placeholder '{' -- not runnable as written",
        })
        (review / "findings.json").write_text(json.dumps(f))
        return review

    def test_an_invalid_command_is_not_offered_as_a_command(self, invalid, tmp_path):
        html = section_html(collect(invalid), "findings", tmp_path)
        assert "<pre>metascience multiplicity" not in html
        assert "The command was left as a template" in html

    def test_a_valid_command_is_still_offered(self, review, tmp_path):
        """The fixture's finding carries a runnable command and no verdict
        against it."""
        html = section_html(collect(review), "findings", tmp_path)
        assert "<pre>metascience grim 5.5 30</pre>" in html


class TestTheSeverityFilterListsWhatIsOnThePage:
    """The dropdown was built from the SWEEP, and the cards rendered at top
    level are the editorial findings plus the orphans. Both directions of the
    mismatch are wrong, and both happen: on the wave-3 `10.1002--mpr.70006` run
    the editorial stage published one `impossible` finding and the sweep
    contains none, so the single most consequential card on the page could not
    be isolated; where a sweep `impossible` is triaged down instead, the word
    appears in a control that then hides every card when selected. `impossible`
    is the strongest claim this system can make, and it must never appear in
    the interface without a finding behind it."""

    def _sevs(self, html):
        block = re.search(r'<select id="fsev">(.*?)</select>', html, re.S).group(1)
        return re.findall(r"<option>([a-z_]+)</option>", block)

    def _report(self, review, findings):
        (review / "report.json").write_text(json.dumps(
            {"verdict": "unresolved", "findings": findings}))

    def test_a_severity_only_the_editorial_stage_used_is_offered(self, review, tmp_path):
        """The sweep's worst is `suspicious`; the review's own conclusion is
        `impossible`. The filter has to reach it."""
        self._report(review, [{"id": "e1", "title": "Cannot co-exist",
                               "severity": "impossible", "stage1_finding_ids": ["f1"]}])
        assert "impossible" in self._sevs(section_html(collect(review), "findings", tmp_path))

    def test_a_severity_the_editorial_stage_triaged_away_is_not_offered(self, review, tmp_path):
        """The sweep says `impossible`, the review triaged it to `suspicious`,
        and the tool verdict is nested inside that card -- where it keeps its
        own severity but does not set the card's. Offering `impossible` here
        promises a finding the page cannot show."""
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0]["severity"] = "impossible"
        (review / "findings.json").write_text(json.dumps(f))
        self._report(review, [{"id": "e1", "title": "Triaged down",
                               "severity": "suspicious", "stage1_finding_ids": ["f1"]}])
        assert self._sevs(section_html(collect(review), "findings", tmp_path)) == ["suspicious"]

    def test_an_orphan_check_still_reaches_the_filter(self, review, tmp_path):
        """An orphan IS rendered at top level, so its severity belongs in the
        list -- the gate is what the page shows, not which stage produced it."""
        self._report(review, [{"id": "e1", "title": "Unrelated",
                               "severity": "indeterminate", "stage1_finding_ids": []}])
        got = self._sevs(section_html(collect(review), "findings", tmp_path))
        assert got == ["suspicious", "indeterminate"]      # ladder order, orphan included


class TestTheAuditTableUsesTheVerdictsPredicate:
    """`CLEAN` printed directly above a table headed "The out-of-surface
    calls". The verdict counts `surface == "UNVALIDATED"`; the table filtered
    `validated === false`, which is `surface != "forensic_mcp"` and therefore
    includes every allowlisted `Read`. MEASURED on the three wave-3 runs: all
    three certify CLEAN and printed 16, 13 and 20 rows of Read/StructuredOutput
    calls underneath as out-of-surface. An audit that contradicts itself on the
    one question it exists to answer is worse than no audit."""

    def test_a_clean_run_prints_no_out_of_surface_table(self, review, tmp_path):
        (review / "sandbox_audit.json").write_text(json.dumps(
            {"n_unvalidated_total": 0, "n_severe_total": 0}))
        html = section_html(collect(review), "audit", tmp_path)
        assert "CLEAN" in html
        assert "The out-of-surface calls" not in html

    def test_a_real_breach_is_still_listed(self, review, tmp_path):
        (review / "sandbox_audit.json").write_text(json.dumps(
            {"n_unvalidated_total": 1, "n_severe_total": 1}))
        calls = json.loads((review / "toolcalls.stage1.json").read_text())
        calls.append({"seq": 3, "tool_short": "Bash", "surface": "UNVALIDATED",
                      "validated": False, "input": {"command": "python -c ..."},
                      "result": "0.42"})
        (review / "toolcalls.stage1.json").write_text(json.dumps(calls))
        html = section_html(collect(review), "audit", tmp_path)
        assert "SEVERE BREACH" in html
        assert "The out-of-surface calls" in html
        assert "Bash" in html
        assert "grim_check" not in html.split("The out-of-surface calls")[1].split("<details")[0]

    def test_a_breach_the_ledger_cannot_identify_says_so(self, review, tmp_path):
        """An older ledger recorded no per-call surface. An empty section under
        a breach verdict would read as a contradiction of the other kind."""
        (review / "sandbox_audit.json").write_text(json.dumps(
            {"n_unvalidated_total": 2, "n_severe_total": 0}))
        html = section_html(collect(review), "audit", tmp_path)
        assert "does not record which" in html


class TestTheRunTabDoesNotInventAZeroCost:
    """The cost column read `v.cost_usd` from the payload. With the cost keys
    stripped it rendered `$0.0000` for every stage -- not a redaction but a
    false statement that the review was free, which is exactly the kind of
    number this toolkit exists to catch in other people's work."""

    def test_no_cost_column(self, review, tmp_path):
        meta = json.loads((review / "run_meta.json").read_text())
        meta["stages"] = {"sweep": {"model": "opus", "cost_usd": 7.58,
                                    "output_tokens": 132020, "wall_seconds": 1426}}
        (review / "run_meta.json").write_text(json.dumps(meta))
        html = flat(section_html(collect(review), "run", tmp_path))
        assert "$0.0000" not in html
        assert "<th data-col=\"3\">cost</th>" not in html
        assert "132020" in html      # the rest of the row survives

    def test_a_clean_surface_with_an_unbacked_finding_is_not_CLEAN(self, review, tmp_path):
        """The same defect as the table, one line up. `sandbox_audit.json`
        already recorded "BREACH (unbacked)" and the page printed CLEAN
        directly above it -- seen on the rebuilt wave-3 eat.24415 bundle. An
        unbacked finding is the likelier failure of the two and is invisible to
        a tool-surface check, so it cannot be folded into CLEAN."""
        (review / "sandbox_audit.json").write_text(json.dumps(
            {"n_unvalidated_total": 0, "n_severe_total": 0,
             "n_unbacked_findings": 1,
             "verdict": "BREACH (unbacked): 1 finding(s) name a check that never ran"}))
        html = flat(section_html(collect(review), "audit", tmp_path))
        assert "<b>CLEAN</b>" not in html
        assert "UNBACKED FINDING" in html
        assert "asserted rather than" in html.lower()


class TestTheScrubberIsNarrow:
    """A scrubber that eats the paper's own links is a different kind of lie
    about the record. `https://osf.io/home/xyz` is a shared-data URL, not our
    home directory, and the bundle exists to show what the paper offered."""

    def test_a_url_containing_home_survives(self):
        from metascience_agent.bundle import scrub
        assert scrub("https://osf.io/home/xyz") == "https://osf.io/home/xyz"
        assert scrub("https://github.com/Users/foo") == "https://github.com/Users/foo"

    def test_the_three_home_shapes_are_all_caught(self):
        from metascience_agent.bundle import scrub
        assert scrub("--xml /home/op/p.xml") == "--xml <home>/p.xml"
        assert scrub("/mnt/c/Users/op/p.xml") == "<home>/p.xml"
        assert scrub(r"C:\Users\op\p.xml") == r"<home>\p.xml"
        assert scrub("file:///home/op/x") == "file://<home>/x"

    def test_a_findings_own_cost_input_is_not_deleted(self):
        """The scrubber names its keys instead of matching the substring
        "cost". A health-economics paper's finding can carry `mean_cost` in its
        inputs, and dropping that would delete the evidence under a finding --
        a worse failure than the leak this exists to close."""
        from metascience_agent.bundle import _scrub
        got = _scrub({"inputs": {"mean_cost": 412.0, "cost_per_qaly": 30000},
                      "cost_usd": 7.58})
        assert got == {"inputs": {"mean_cost": 412.0, "cost_per_qaly": 30000}}


class TestTheChainOfReasoningSaysWhereEachNumberCameFrom:
    """Greg, 2026-08-09: every tool should "report the exact quote/context of
    the paper from which given values were extracted". The ledger recorded that
    grim_check was called with mean=48.90; nothing recorded that 48.90 was the
    Age row of Table 1, so a reader auditing the finding had to go and locate
    the value themselves -- the work this exists to spare them."""

    def test_a_sourced_call_shows_its_passage_and_our_verdict(self, review, tmp_path):
        (review / "toolcalls.stage1.json").write_text(json.dumps([
            {"seq": 1, "tool_short": "grim_check", "surface": "mcp", "validated": True,
             "input": {"mean": 48.9, "n": 142, "source_quote": "Mean age was 48.9 years",
                       "source_locator": "Table 1, Age row"},
             "source_quote_verified": "verbatim", "source_quote_source": "body",
             "result": '{"severity": "consistent"}'}]))
        html = flat(section_html(collect(review), "calls", tmp_path))
        assert "Read from" in html
        assert "Mean age was 48.9 years" in html
        assert "Table 1, Age row" in html
        assert "found in the paper in body" in html

    def test_an_unlocated_quote_is_blamed_on_our_search(self, review, tmp_path):
        """A quote we cannot find is far more often a limit of our extraction
        than a fabrication -- hand-adjudicating every one of 22 unlocated quotes
        over 499 findings turned up no fabrications at all."""
        (review / "toolcalls.stage1.json").write_text(json.dumps([
            {"seq": 1, "tool_short": "grim_check", "surface": "mcp", "validated": True,
             "input": {"mean": 48.9, "source_quote": "nowhere in this paper"},
             "source_quote_verified": "unverified",
             "result": '{"severity": "consistent"}'}]))
        html = flat(section_html(collect(review), "calls", tmp_path))
        assert "NOT located" in html
        assert "our extraction or our search, not the authors" in html

    def test_an_unsourced_check_says_so(self, review, tmp_path):
        """WORDING CHANGED 2026-08-11, intent unchanged. "No source passage
        recorded -- these numbers cannot be traced to the page from this bundle"
        was the Overview's over-claim in miniature: the CALL did not record a
        passage, which is a fact about the ledger entry, not a statement that
        the number is untraceable. The finding it feeds usually quotes the paper
        and was usually located verbatim."""
        html = flat(section_html(collect(review), "calls", tmp_path))
        assert "did not record the passage" in html
        assert "may still quote the paper" in html

    def test_an_extractor_is_not_scored_as_unsourced(self, review, tmp_path):
        """`Read` was never offered the argument. Marking it unsourced would
        report a design decision as a coverage failure on every single run."""
        (review / "toolcalls.stage1.json").write_text(json.dumps([
            {"seq": 1, "tool_short": "Read", "surface": "builtin_allowed",
             "validated": False, "input": {"file_path": "body.md"}, "result": "x"}]))
        (review / "toolcalls.stage2.json").unlink(missing_ok=True)
        html = flat(section_html(collect(review), "calls", tmp_path))
        assert "No source passage recorded" not in html
        assert "checks recorded the passage" not in html

    def test_the_page_counts_its_own_coverage(self, review, tmp_path):
        (review / "toolcalls.stage1.json").write_text(json.dumps([
            {"seq": 1, "tool_short": "grim_check", "surface": "mcp", "validated": True,
             "input": {"mean": 48.9, "source_quote": "Mean age was 48.9 years"},
             "source_quote_verified": "verbatim", "result": "{}"},
            {"seq": 2, "tool_short": "grim_check", "surface": "mcp", "validated": True,
             "input": {"mean": 3.1}, "result": "{}"},
            {"seq": 3, "tool_short": "Read", "surface": "builtin_allowed",
             "validated": False, "input": {"file_path": "body.md"}, "result": "x"}]))
        html = flat(section_html(collect(review), "calls", tmp_path))
        assert "1 of 2</b> checks recorded the passage" in html


class TestTheFindingShowsWhereItsNumbersWereRead:
    """`f.quote` is the model's choice of what to quote ABOUT a finding;
    `f.source` is the passage the CHECKED NUMBERS were read from, joined to the
    finding by `sourcing.annotate` from the validated call that produced it.
    A reader auditing an accusation wants the second."""

    def _one(self, review, tmp_path, source):
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0]["source"] = source
        (review / "findings.json").write_text(json.dumps(f))
        return flat(section_html(collect(review), "findings", tmp_path))

    def test_a_located_passage_is_shown_with_its_locator(self, review, tmp_path):
        html = self._one(review, tmp_path, {
            "source_quote": "Mean age was 48.9 years", "source_locator": "Table 1, Age row",
            "source_quote_verified": "verbatim", "source_quote_source": "a table"})
        assert "Numbers read from" in html
        assert "Mean age was 48.9 years" in html
        assert "Table 1, Age row" in html
        assert "found in a table" in html

    def test_an_unlocated_passage_does_not_make_the_as_printed_promise(self, review, tmp_path):
        """Same discipline as quoteLabel: only the two verdicts that actually
        located the text may claim the words are in the paper."""
        html = self._one(review, tmp_path, {
            "source_quote": "a sentence nobody can find",
            "source_quote_verified": "unverified"})
        assert "not located by our search" in html
        assert "most often our extraction, not the authors" in html

    def test_a_finding_with_no_source_renders_no_row(self, review, tmp_path):
        """The ROW, specifically. The page header names the row in its own
        explanatory sentence, so a bare phrase match passes for the wrong
        reason -- as this test did until the header was added."""
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "<dt>Numbers read from</dt>" not in html

    def test_the_page_counts_how_much_of_it_is_traceable(self, review, tmp_path):
        """Now ONE sentence, computed in Python (`viewer_facts`) and shared with
        the Overview, so the two cannot answer the same question with different
        numbers. The old sentence also said the untraced findings "cite values
        this bundle cannot trace back to the page" when they quote the paper --
        see the note at the Overview site."""
        html = self._one(review, tmp_path, {
            "source_quote": "Mean age was 48.9 years",
            "source_quote_verified": "verbatim"})
        assert "findings quote a passage of the paper" in html

    def test_manual_findings_are_not_counted_as_untraceable(self, review, tmp_path):
        """No producing call exists for a hand-read value, so counting it as a
        miss would report a design fact as a coverage failure."""
        f = json.loads((review / "findings.json").read_text())
        for row in f["findings"]:
            row["technique"] = "manual"
        (review / "findings.json").write_text(json.dumps(f))
        html = flat(section_html(collect(review), "findings", tmp_path))
        # The JOIN clause is what must not appear: no producing call exists for
        # a hand-read value, so counting it as untraceable reports a design fact
        # as a coverage failure. The quote sentence itself is still true of
        # them, and suppressing it too would be the opposite error -- so the
        # positive half must still be stated.
        assert "could not be tied" not in html
        assert "no producing call exists for them" in html



class TestTheOverviewLeadsWithTheReviewNotThePaper:
    """MEASURED at 1280x900 on the jpm11060545 bundle: the entire first screen
    of the document was publisher metadata, and the paper's own abstract pushed
    the verdict a screen and a half down. A reader opening a forensic review
    met the paper's marketing copy first and the review's conclusion never, if
    they did not scroll.
    """

    def _ov(self, review, tmp_path):
        return flat(section_html(collect(review), "overview", tmp_path))

    def test_the_result_block_comes_before_the_metadata_block(self, review, tmp_path):
        html = self._ov(review, tmp_path)
        assert html.index("<h3>Result</h3>") < html.index("<h3>Metadata</h3>")

    def test_the_headline_sentence_is_printed_not_just_the_coded_verdict(
            self, review, tmp_path):
        """`report.headline.statement` has always carried one plain sentence
        saying what the review found. The Overview showed only `questionable`,
        a three-valued label with no direction, standing in for a sentence that
        already existed in the payload."""
        r = json.loads((review / "report.json").read_text())
        r["headline"] = {"severity": "suspicious",
                         "statement": "One denominator does not match the rest."}
        (review / "report.json").write_text(json.dumps(r))
        assert "One denominator does not match the rest." in self._ov(review, tmp_path)


class TestWhatThisReviewCouldNotDo:
    """The cardinal rule, made structural.

    Every restraining fact a run records was true, written down, and on a
    DIFFERENT page from the verdict. Of all the arrangements of these same
    facts, that is the one that makes a finding look more damning than the
    evidence supports.
    """

    def _limits(self, review, tmp_path, **files):
        for name, obj in files.items():
            path = review / f"{name}.json"
            cur = json.loads(path.read_text()) if path.exists() else {}
            cur.update(obj)
            path.write_text(json.dumps(cur))
        html = flat(section_html(collect(review), "overview", tmp_path))
        start = html.index("What this review could not do")
        return html[start:html.index("<h3>Metadata</h3>")]

    def test_the_block_sits_between_the_verdict_and_the_paper_metadata(
            self, review, tmp_path):
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert (html.index("<h3>Result</h3>")
                < html.index("What this review could not do")
                < html.index("<h3>Metadata</h3>"))

    def test_the_checked_against_found_ratio_is_stated(self, review, tmp_path):
        """`stats_found` was on the Coverage page and `stats_checked` was on no
        page at all, so a run that located 741 statistics and checked 122
        advertised the 741."""
        html = self._limits(review, tmp_path, report={
            "coverage_summary": {"stats_found": 741, "stats_checked": 122}})
        assert "<b>122 of 741</b>" in html
        assert "nothing here is evidence about them" in html

    def test_refusals_are_counted_from_the_longer_of_the_two_lists(
            self, review, tmp_path):
        """Both stages record refusals and the editorial list is consistently
        the longer -- measured 9 against 8, 12 against 10, 13 against 11."""
        html = self._limits(review, tmp_path, report={
            "not_checked": [{"location": f"L{i}", "reason": "r"} for i in range(9)]})
        assert "<b>9</b> places in the paper were examined and then REFUSED" in html

    def test_a_finding_with_no_tool_behind_it_is_declared_beside_the_verdict(
            self, review, tmp_path):
        """THE PREDICATE CHANGED, and that is what this test now pins.

        It used to count findings with no `stage1_finding_ids`.
        `evidence_grade`'s own docstring already recorded that predicate as
        wrong -- "measured on the run that motivated it, that predicate fires on
        0 of 8" -- and this line was the surviving instance of it. MEASURED
        across the archive: the old predicate caught 17 of 222 findings (8%)
        where the ledger's chain predicate catches 88 (40%), so the overview
        understated the phenomenon FIVE-FOLD in every bundle shipped.

        The third finding below is the case the old predicate could not see and
        which is the commonest in practice: it CITES a sweep finding, so it
        looks backed, and that sweep finding is `technique: manual` -- the
        model's own arithmetic.
        """
        html = self._limits(review, tmp_path,
            findings={"findings": [
                {"id": "f1", "technique": "grim_check"},
                {"id": "f2", "technique": "manual"},
            ]},
            report={"findings": [
                {"severity": "suspicious", "title": "computed",
                 "stage1_finding_ids": ["f1"]},
                {"severity": "suspicious", "title": "a reading",
                 "stage1_finding_ids": []},
                {"severity": "suspicious", "title": "looks backed, is not",
                 "stage1_finding_ids": ["f2"]},
            ]})
        assert "<b>2 of 3</b> findings in this report rest on no validated" in html
        assert "ASSERTED, or hand-worked by the model" in html

    def test_the_discredited_predicate_is_gone_from_the_overview(self):
        """It counted 8% where the truth is 40%, and there is no fallback path
        that can reprint it. I wrote one and then could not reach it in a test:
        `collect` computes the facts block on every build, so the branch was
        unreachable code with a wrong answer inside it.

        ANCHORED ON THE SENTENCE, NOT ON ONE EXPRESSION'S SPELLING. This used to
        `index()` the literal `const evc=((D.facts||{}).evidence||{}).counts`,
        so splitting that line into two while KEEPING the property -- which is
        what fixing the "18 of 0" denominator required -- failed a test whose
        subject had not changed.
        """
        import pathlib
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src/metascience_agent/bundle.py").read_text(encoding="utf-8")
        i = src.index("on no validated computation")
        block = src[max(0, i - 1600):i + 400]
        # The discredited predicate must not be back...
        assert "stage1_finding_ids||[]).length" not in block
        # ...and both halves of the ratio must come from the facts block, which
        # is the v2 source. `rep.findings` is the v1 `report_obj` the parallel
        # path never writes, and reading it there is what printed "18 of 0".
        assert "D.facts" in block and "evidence" in block
        # The CODE form, not the phrase: the comment above the fix explains the
        # bug and necessarily names `rep.findings.length`, so a bare substring
        # test matches its own documentation.
        assert "const ed=rep.findings" not in block
        assert "+ed.length" not in block

    def test_a_recorded_breach_verdict_is_quoted_verbatim(self, review, tmp_path):
        """QUOTED, not recomputed. The sandbox counts findings that NAME a check
        which never ran; the line above it counts findings that CITE no sweep
        finding. Two independently computed tallies of near-identical predicates
        read as a contradiction when they differ, and on a real run they do."""
        html = self._limits(review, tmp_path, sandbox_audit={
            "verdict": "BREACH (unbacked): 1 finding(s) name a check that never ran",
            "n_unvalidated_total": 0, "n_unbacked_findings": 1})
        assert "BREACH (unbacked): 1 finding(s) name a check that never ran" in html

    def test_reproduction_commands_that_do_not_run_are_declared(self, review, tmp_path):
        html = self._limits(review, tmp_path, run_meta={
            "reproducibility": {"n_findings": 38, "n_invalid": 32}})
        assert "<b>32 of 38</b>" in html
        assert "says nothing about whether the findings are right" in html

    def test_the_standing_base_rate_is_stated_on_every_run(self, review, tmp_path):
        """Printed whether or not anything else applies: it is a property of the
        pipeline, not of the paper, and it caps how much any single flag means.

        REFRAMED 2026-08-16. This asserted the literal string "at or below 1%".
        That number was written 2026-07-27, before most of the current pipeline
        existed, and was never sourced -- `docs/FORENSIC_INTEGRITY_HARDENING.md`
        had already flagged that it "needs a cited method or a reframing". It
        sat outside `prompts/`, so `test_prompt_claims_are_dated.py` never
        caught it, and this assertion pinned it in place.

        The qualitative claim carries the same guard and is defensible: nearly
        all the failure is extraction, not arithmetic. Do not restore a number
        here without a measurement behind it.
        """
        html = self._limits(review, tmp_path)
        assert "getting numbers off a PDF" in html
        assert "1%" not in html, "an unsourced precision figure came back"

    def test_nothing_is_printed_as_a_reassuring_zero(self, review, tmp_path):
        """A line that does not apply is omitted. "0 findings without tool
        backing" invites the reader to score the run out of ten; the purpose
        here is disclosure, not a scorecard."""
        html = self._limits(review, tmp_path, report={"findings": [
            {"severity": "suspicious", "stage1_finding_ids": ["f1"]}]})
        assert "cites no sweep tool verdict" not in html
        assert "cite no sweep tool verdict" not in html


class TestWhatEachCheckCanConclude:
    """`registry.TOOL_INTEGRITY` carried a hand-authored card for all 49 tools
    and no viewer surface read one. It is the answer to the question this
    document most needs answered: when it says `impossible`, what kind of claim
    is that?
    """

    def test_a_card_is_built_for_a_tool_the_run_called(self, review):
        cards = collect(review)["tool_cards"]["cards"]
        assert any(c["tool"] == "grim_check" for c in cards)

    def test_the_card_carries_the_class_the_ceiling_and_the_assumptions(self, review):
        card = next(c for c in collect(review)["tool_cards"]["cards"]
                    if c["tool"] == "grim_check")
        assert card["evidence"] == "absolute"
        assert card["severity_ceiling"] == "impossible"
        assert card["assumptions"]

    def test_a_technique_family_resolves_to_the_tool_that_owns_the_card(self, review):
        """The model writes `technique: "grim"` for a `grim_percentage` call and
        `"duplication"` for `detect_duplication`, so a naive lookup finds no
        card for exactly the findings a reader most wants classified. The
        mapping is severity_reconcile's, not a second copy of it."""
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0]["technique"] = "duplication"
        (review / "findings.json").write_text(json.dumps(f))
        cards = collect(review)["tool_cards"]
        assert cards["aliases"]["duplication"] == "detect_duplication"

    def test_manual_is_not_reported_as_a_check_we_cannot_describe(self, review):
        """`manual` is not an undocumented tool, it is the ABSENCE of one, and
        the codebook already calls it the weakest evidence class here. Listing
        it as undescribable would report the system's most candid admission as
        a documentation gap."""
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0]["technique"] = "manual"
        (review / "findings.json").write_text(json.dumps(f))
        assert "manual" not in collect(review)["tool_cards"]["undescribed"]

    def test_a_name_we_cannot_describe_is_named_rather_than_dropped(self, review):
        f = json.loads((review / "findings.json").read_text())
        f["coverage"] = {"tools_run": ["grim_check", "no_such_tool"]}
        (review / "findings.json").write_text(json.dumps(f))
        assert collect(review)["tool_cards"]["undescribed"] == ["no_such_tool"]

    def test_the_codebook_renders_a_card_a_finding_can_link_to(self, review, tmp_path):
        html = flat(section_html(collect(review), "about", tmp_path))
        assert "What each check can conclude" in html
        assert 'id="cb-tool-grim_check"' in html

    def test_a_probabilistic_check_says_so_inline_never_impossible(
            self, review, tmp_path):
        """The two RESTRAINING classes carry their restraint in the chip itself.
        A reader must not have to click to learn that a check cannot reach
        `impossible`."""
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0]["technique"] = "check_effect_plausibility"
        (review / "findings.json").write_text(json.dumps(f))
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "probabilistic, never impossible" in html

    def test_a_severity_above_the_tools_ceiling_is_disclosed_not_hidden(
            self, review, tmp_path):
        """Rare and real: measured over every archived run, 2 of 294 stamped
        findings record a severity above their tool's declared ceiling, both
        `multiplicity_report` -- a descriptive tool -- carried at `suspicious`.
        The severity there is the write-up's, not the check's."""
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0].update(technique="multiplicity_report", severity="suspicious")
        (review / "findings.json").write_text(json.dumps(f))
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "recorded above what this check can return" in html

    def test_a_finding_read_off_the_paper_says_no_tool_computed_it(
            self, review, tmp_path):
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0]["technique"] = "manual"
        (review / "findings.json").write_text(json.dumps(f))
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "not computed by a tool" in html


class TestCoverageShowsTheDenominatorAndTheLongerRefusalList:
    def test_the_checked_against_found_pair_is_rendered(self, review, tmp_path):
        r = json.loads((review / "report.json").read_text())
        r["coverage_summary"] = {"stats_found": 704, "stats_checked": 37}
        (review / "report.json").write_text(json.dumps(r))
        html = flat(section_html(collect(review), "coverage", tmp_path))
        # WORDING CHANGED 2026-08-10 and the change is the point: both numbers
        # are model-asserted, so they are labelled as the review's own account
        # and are no longer divided into a percentage. See
        # TestNoPercentageIsBuiltFromTwoGuesses. Both must still be SHOWN --
        # suppressing the review's self-report would be its own dishonesty.
        assert "the review says it located" in html and "704" in html
        assert "the review says it checked" in html and "37" in html

    def test_the_cell_census_and_its_own_note_are_rendered(self, review, tmp_path):
        """Computed on every run by the commit that argued coverage must be
        measured against what was CHECKABLE -- and rendered nowhere a reader
        goes. Its `note` is the plainest sentence in the payload, so it is
        printed verbatim rather than paraphrased."""
        r = json.loads((review / "report.json").read_text())
        r["coverage_summary"] = {"stats_found": 704, "stats_checked": 37, "checkable": {
            "n_cells": 902, "n_consumable": 525, "cells_checked_via_check_table": 0,
            "blocked_on_declaration": 525, "blocked_on_input": 0,
            "note": "Coverage: 0 of 525 checkable cells were checked (0%)."}}
        (review / "report.json").write_text(json.dumps(r))
        html = flat(section_html(collect(review), "coverage", tmp_path))
        assert "Coverage: 0 of 525 checkable cells were checked (0%)." in html
        # Relabelled 2026-08-10: each blocked bucket now names WHOSE limit it
        # is, because a single undifferentiated shortfall reads as a task list
        # abandoned. This one is the fixable case.
        assert "no one declared what kind of quantity the row is" in html

    def test_the_editorial_refusal_list_leads_and_the_sweeps_is_kept(
            self, review, tmp_path):
        """They are NOT merged: the two lists paraphrase the same refusals
        differently, so any dedupe short of fuzzy matching leaves near
        duplicates side by side, and fuzzy matching would drop a genuine entry
        to tidy the table."""
        r = json.loads((review / "report.json").read_text())
        r["not_checked"] = [{"location": "Table 9", "reason": "the editorial reason"}]
        (review / "report.json").write_text(json.dumps(r))
        html = flat(section_html(collect(review), "coverage", tmp_path))
        assert "the editorial reason" in html
        assert "The sweep recorded its own 1 refusal" in html
        assert "figure" in html   # the sweep's own entry, from the fixture

    def test_the_reviews_own_limitations_are_shown_where_coverage_is(
            self, review, tmp_path):
        r = json.loads((review / "report.json").read_text())
        r["limitations"] = ["statcheck recovered zero statistics."]
        (review / "report.json").write_text(json.dumps(r))
        html = flat(section_html(collect(review), "coverage", tmp_path))
        assert "statcheck recovered zero statistics." in html

    def test_our_failed_download_is_not_reported_as_the_paper_having_none(
            self, review, tmp_path):
        """Two opposite facts wore the same words. Measured over the paper
        directories in this repo: 7 `retrieval_failed` against 4
        `nothing_published`, so the commoner case is our own 404."""
        paper = review.parent
        (paper / "10.1234--demo_supplementary_info.json").write_text(json.dumps({
            "status": "none_found", "providers_queried": ["a"] * 14, "files": [],
            "attempts": [{"provider": "europepmc_supplements", "listed": ["x.zip"],
                          "obtained": [], "error": "no-bundle", "http_status": 404}],
        }))
        payload = collect(review)
        assert payload["supplement_retrieval"].get("verdict")
        html = flat(section_html(payload, "coverage", tmp_path))
        assert "Supplementary material" in html


class TestTheAnatomyShowsWhatTheReviewThinksThePaperClaims:
    """The anatomy is the inspectable INPUT layer -- what the review believes
    the paper claims, so a finding can be traced back to what it actually saw
    -- and its first element is the hypothesis. 16 of the 26 archived runs
    carry a populated `hypotheses` array and none of it reached a reader.
    """

    def _with_hypotheses(self, review, rows):
        f = json.loads((review / "findings.json").read_text())
        f["anatomy"]["hypotheses"] = rows
        (review / "findings.json").write_text(json.dumps(f))
        return collect(review)

    def test_the_hypothesis_statement_is_rendered(self, review, tmp_path):
        payload = self._with_hypotheses(review, [{
            "id": "H1", "statement": "The drug beats placebo on motor recovery.",
            "status": "confirmatory", "appears_in_abstract": True,
            "confidence": "high"}])
        assert "The drug beats placebo on motor recovery." in flat(
            section_html(payload, "anatomy", tmp_path))

    def test_exploratory_and_in_the_abstract_are_two_neutral_columns(
            self, review, tmp_path):
        """The pair a reader can draw their own inference from. Stated as
        columns, not as a flag: there is no check behind it, and a column is
        not the same thing as an accusation."""
        payload = self._with_hypotheses(review, [{
            "id": "H1", "statement": "An exploratory claim.",
            "status": "exploratory", "appears_in_abstract": True}])
        html = flat(section_html(payload, "anatomy", tmp_path))
        assert "stated as" in html and "in the abstract" in html
        assert "exploratory" in html

    def test_the_passage_a_hypothesis_was_read_from_is_reachable(
            self, review, tmp_path):
        payload = self._with_hypotheses(review, [{
            "id": "H1", "statement": "A claim.", "provenance_verdict": "verbatim",
            "provenance_quote": "We hypothesised that the drug would win."}])
        html = flat(section_html(payload, "anatomy", tmp_path))
        assert "We hypothesised that the drug would win." in html
        assert "found in the paper" in html

    def test_a_run_without_hypotheses_renders_no_empty_section(
            self, review, tmp_path):
        html = flat(section_html(collect(review), "anatomy", tmp_path))
        assert "<h3>Hypotheses</h3>" not in html


class TestRunDetailsStopsHidingTheRunsOwnCaveats:
    def test_the_divergences_themselves_are_listed_not_only_counted(
            self, review, tmp_path):
        """"n diverged: 6" told a reader that six verdicts were rewritten and
        refused to say which six or in which direction -- and an UPGRADE is the
        most accusation-relevant record in the whole run."""
        m = json.loads((review / "run_meta.json").read_text())
        m["severity_reconciliation"] = {"n_compared": 15, "n_diverged": 1,
            "divergences": ["table2_asterisk: tool=indeterminate model=suspicious "
                            "(upgraded, explained)"]}
        (review / "run_meta.json").write_text(json.dumps(m))
        html = flat(section_html(collect(review), "run", tmp_path))
        assert "table2_asterisk: tool=indeterminate model=suspicious" in html
        assert "MORE severe than the check that produced it" in html

    def test_a_stage_cut_short_by_its_budget_says_so(self, review, tmp_path):
        """A stage that stopped early did not finish looking, which is a
        coverage fact, and it was reachable nowhere."""
        m = json.loads((review / "run_meta.json").read_text())
        m["stages"]["sweep"] = {"model": "claude-opus-5", "truncated_by_budget": True}
        (review / "run_meta.json").write_text(json.dumps(m))
        html = flat(section_html(collect(review), "run", tmp_path))
        assert "STAGE TRUNCATED BY BUDGET" in html

    def test_every_model_that_ran_is_named_not_just_the_headline_one(
            self, review, tmp_path):
        """The stage table names one model per stage while every archived run
        records `model_switched: true` with two resolved models."""
        m = json.loads((review / "run_meta.json").read_text())
        m["stages"]["sweep"] = {"model": "claude-opus-5", "model_switched": True,
                                "models_resolved": ["claude-haiku-4-5", "claude-opus-5"]}
        (review / "run_meta.json").write_text(json.dumps(m))
        html = flat(section_html(collect(review), "run", tmp_path))
        assert "claude-haiku-4-5" in html
        assert "more than one model was used in this stage" in html


class TestABrokenReproductionCommandDoesNotShoutOverTheFinding:
    def test_a_long_exec_failure_is_folded_away_but_kept(self, review, tmp_path):
        """200-odd characters of click usage text and box drawing were printed
        inline directly beneath the accusation, so the last thing under a
        finding that says `impossible` was a wall of tooling failure. Kept,
        because it names the exact broken argument; folded, because the reader
        needs "you cannot re-run this", not our stack."""
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0].update(
            reproduction="metascience grim 5.5 30", reproduction_valid=False,
            reproduction_problem="exited 2: Usage: metascience grim [OPTIONS] " + "x" * 120)
        (review / "findings.json").write_text(json.dumps(f))
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "Not reproducible by a single command." in html
        assert "what went wrong when we tried" in html
        assert "exited 2: Usage: metascience grim" in html

    def test_a_short_reason_stays_inline(self, review, tmp_path):
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0].update(reproduction="grim 5.5 30", reproduction_valid=False,
                                reproduction_problem="exited 1:")
        (review / "findings.json").write_text(json.dumps(f))
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "what went wrong when we tried" not in html


class TestABundleThatCannotOpenItsPaperSaysSo:
    """MEASURED FAILURE, 2026-08-10. A bundle was rebuilt after its paper
    directory had been tidied to hold only the review and the previous bundle.
    `bundle` resolves the paper from the review's parent, found nothing, and
    wrote a viewer with `body_text: ""`, `table_records: []` and
    `table_extraction: {"xml": false, "error": ""}` -- then printed a path and
    exited 0. The empty `error` is the tell: nothing failed, because nothing
    was attempted. It overwrote a good viewer, and the only reason the content
    was recoverable is that the OLD bundle kept its own copy under `paper/`.

    An empty pane is indistinguishable from a clean one, so silence here is the
    house failure this repo keeps finding: a degraded result reported as
    success."""

    def test_the_payload_records_the_unreachable_paper(self, review, capsys):
        for f in review.parent.glob("*"):
            if f != review:
                f.unlink()
        p = collect(review)
        assert p["table_extraction"]["paper_unreachable"]
        assert "WARNING:" in capsys.readouterr().err

    def test_the_reader_is_told_on_the_page_they_land_on(self, review, tmp_path):
        """stderr is gone by the time anyone opens the file. The bundle is the
        artefact that gets handed over, so the bundle has to carry the warning."""
        for f in review.parent.glob("*"):
            if f != review:
                f.unlink()
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert "could not open the paper it describes" in html

    def test_and_again_beside_the_empty_panes(self, review, tmp_path):
        """A reader who deep-links to Source and extraction never passes the
        Overview, and Source and extraction is exactly where the emptiness
        shows."""
        for f in review.parent.glob("*"):
            if f != review:
                f.unlink()
        html = flat(section_html(collect(review), "source", tmp_path))
        assert "could not open the paper it describes" in html

    def test_a_healthy_bundle_shows_no_alarm(self, review, tmp_path):
        assert "paper_unreachable" not in collect(review)["table_extraction"]
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert "could not open the paper" not in html


class TestACellIsNotANumberUntilItsFootnoteIsRead:
    """Greg, 2026-08-10: "many of the cells have annotations like asterisks".

    MEASURED on 10.1038/s41537-025-00576-3. Table 2 prints `180.74**`; its one
    footnote reads "*P < 0.01; **P < 0.001." Table 3's reads "OR odds ratio, CI
    confidence interval." The extractor returned both. The bundle counted them
    -- the card said "1 footnote" -- and threw the text away, so a reader was
    told a note existed and given no way to learn what the asterisks meant.
    """

    @pytest.fixture
    def with_footnote(self, review):
        p = collect(review)
        p["table_records"] = [{
            "label": "Table 2", "caption": "Comorbidity by group.",
            "n_rows": 2, "width": 2, "n_footnotes": 1,
            "rows": [["Group", "chi2"], ["Gender", "180.74**"]],
            "footnotes": [{"marker": "", "text": "*P < 0.01; **P < 0.001."}],
            "warnings": [],
        }]
        return p

    def test_the_note_that_defines_the_asterisks_is_on_the_card(
            self, with_footnote, tmp_path):
        html = flat(section_html(with_footnote, "source", tmp_path))
        assert "*P &lt; 0.01; **P &lt; 0.001." in html

    def test_it_is_in_the_full_size_window_too(self, with_footnote, tmp_path):
        """The popout is where a reader studies the cells closely, so it is the
        last place that may leave `**` undefined."""
        js = render_viewer(with_footnote).rsplit("<script>", 1)[1].split("</script>")[0]
        assert "t.footnotes" in js.split("function openTable")[1].split("\nfunction ")[0]

    def test_a_table_with_no_footnotes_adds_no_empty_block(
            self, review, tmp_path):
        p = collect(review)
        p["table_records"] = [{"label": "Table 1", "caption": "", "n_rows": 1,
                               "width": 1, "rows": [["x"]], "footnotes": [],
                               "warnings": []}]
        assert "tfoot" not in flat(section_html(p, "source", tmp_path))

    def test_a_blank_footnote_is_not_rendered_as_one(self, review, tmp_path):
        """Publishers emit empty `<fn/>` elements. Counting one and printing
        nothing is the same lie in a smaller box."""
        p = collect(review)
        p["table_records"] = [{"label": "Table 1", "caption": "", "n_rows": 1,
                               "width": 1, "rows": [["x"]], "warnings": [],
                               "footnotes": [{"marker": "", "text": "   "}]}]
        assert "tfoot" not in flat(section_html(p, "source", tmp_path))


class TestTheToolsOwnVerdictIsInTheAccounting:
    """Greg, 2026-08-10: consistent checks "ought to be classified as
    trustworthy in the accounting, even if they are omitted from the main
    report". They were not in the accounting at all. "What each check returned"
    had one severity column, and it counted the MODEL'S write-ups.

    MEASURED on 10.1038/s41537-025-00576-3: `check_estimate_ci` ran 43 times and
    returned 21 `consistent` and 22 `indeterminate`; the page showed a column
    summing to 4. And in the other direction, `grim_percentage` returned
    `impossible` twice and `grim_sweep` once, while the report's tally showed no
    `impossible` anywhere -- three checks said the strongest thing this toolkit
    can say and a reader could not see that the review had not carried it.
    """

    @pytest.fixture
    def graded(self, review):
        (review / "toolcalls.stage1.json").write_text(json.dumps(
            [{"seq": i, "tool_short": "check_estimate_ci", "surface": "mcp",
              "validated": True, "input": {}, "result": '{"severity": "consistent"}'}
             for i in range(3)]
            + [{"seq": 9, "tool_short": "grim_percentage", "surface": "mcp",
                "validated": True, "input": {},
                "result": '{"severity": "impossible"}'}]))
        return collect(review)

    def test_the_passes_are_counted(self, graded, tmp_path):
        row = [r for r in graded["check_table"] if r["check"] == "check_estimate_ci"][0]
        assert row["calls"] == 3
        assert row["tool_verdicts"] == {"consistent": 3}
        assert "consistent 3" in _text(section_html(graded, "overview", tmp_path))

    def test_a_tool_verdict_the_write_up_dropped_is_still_shown(
            self, graded, tmp_path):
        """The case that matters most. A check returning `impossible` that
        reaches no finding is either our false positive or the review missing
        something, and both are things a reader must be able to see."""
        row = [r for r in graded["check_table"] if r["check"] == "grim_percentage"][0]
        assert row["tool_verdicts"] == {"impossible": 1}
        # The write-up recorded `suspicious` for the same check. The two
        # columns disagreeing is the whole point of showing both.
        assert row["severities"] == {"suspicious": 1}
        assert "impossible 1" in _text(section_html(graded, "overview", tmp_path))

    def test_the_two_columns_are_named_apart(self, graded, tmp_path):
        """One unqualified `severities` heading over the write-up counts is how
        the tool's own verdicts came to be invisible."""
        html = flat(section_html(graded, "overview", tmp_path))
        assert "the tool returned" in html
        assert "in the write-up" in html

    def test_a_call_with_no_severity_contributes_nothing(self, review):
        """`get_table` and `extract_xml` return data, not verdicts. Counting
        them as an absent severity would invent a category."""
        p = collect(review)
        row = [r for r in p["check_table"] if r["check"] == "Read"]
        assert not row or not row[0]["tool_verdicts"]


class TestADeDuplicationIsNotADownloadFailure:
    """MEASURED across every archived retrieval record in this repo: 43 skips,
    32 of them (74%) `duplicate-of`. The fetcher asks several providers for the
    same paper, so the same file arrives more than once and every copy after the
    first is skipped -- which is the fetcher WORKING. All of them went into one
    table headed "why it failed", so on 10.1038/s41537-025-00576-3 the page
    listed six failures when the true number was zero and all three files were
    obtained. Same defect class as `_page_ink` blaming a decoder failure on the
    document: our own bookkeeping published as an adverse fact.
    """

    @pytest.fixture
    def rec(self, review, tmp_path):
        (review.parent / "x_supplementary_info.json").write_text(json.dumps({
            "status": "ok",
            "providers": [{"name": "pmc_s3", "listed": 2},
                          {"name": "springer_esm", "listed": 2}],
            "files": [{"name": "a.xlsx"}],
            "skipped": [
                {"provider": "springer_esm", "original_name": "a.xlsx",
                 "reason": "duplicate-of"},
                {"provider": "pmc_s3", "original_name": "b.docx",
                 "reason": "no-bundle", "status": 404},
            ],
        }))
        return collect(review)

    def test_the_kinds_of_skip_are_separated_in_the_record(self, rec):
        """UPDATED 2026-08-11: `no-bundle` is no longer filed as a failure.
        Measured on a fresh 15-paper fetch, every one of those skips is either a
        licence wall or a 404 at a URL the fetcher constructs from the PMCID
        before knowing a bundle exists -- neither is a transfer that broke."""
        r = rec["supplement_retrieval"]
        assert [f["reason"] for f in r["failures"]] == []
        assert [f["reason"] for f in r["speculative_addresses"]] == ["no-bundle"]
        assert [f["reason"] for f in r["duplicates"]] == ["duplicate-of"]

    def test_the_slug_is_given_a_sentence(self, rec):
        r = rec["supplement_retrieval"]
        assert "no supplement bundle" in r["speculative_addresses"][0]["explanation"]

    def test_the_page_files_them_apart(self, rec, tmp_path):
        html = _text(section_html(rec, "coverage", tmp_path))
        assert "Asked at a guessed address (1)" in html
        assert "Skipped as already held (1)" in html
        assert "retrieval working, not failing" in html
        assert "absence, not a file somebody published" in html

    def test_a_licence_wall_gets_its_own_heading_and_says_a_library(
            self, review, tmp_path):
        """It is neither a failure nor an absence, and the operator action is
        different from both."""
        (review.parent / "x_supplementary_info.json").write_text(json.dumps({
            "status": "none_found",
            "providers": [{"name": "europepmc_supplements", "listed": 1}],
            "files": [],
            "skipped": [{"provider": "europepmc_supplements",
                         "original_name": "PMC1_SupplementaryFiles.zip",
                         "reason": "no-bundle",
                         "detail": "Article with id PMC1 is not open access one"}],
        }))
        html = _text(section_html(collect(review), "coverage", tmp_path))
        assert "Exists, but not ours to download (1)" in html
        assert "behind a licence" in html
        assert "library" in html

    def test_a_run_whose_only_skips_were_duplicates_reports_no_failure(
            self, review, tmp_path):
        (review.parent / "x_supplementary_info.json").write_text(json.dumps({
            "status": "ok", "providers": [{"name": "pmc_s3", "listed": 1}],
            "files": [{"name": "a.xlsx"}],
            "skipped": [{"provider": "springer_esm", "original_name": "a.xlsx",
                         "reason": "duplicate-of"}],
        }))
        p = collect(review)
        assert p["supplement_retrieval"]["failures"] == []
        assert "Nothing we asked for failed to arrive" in _text(
            section_html(p, "coverage", tmp_path))


class TestAHighlightIsReadableInBothThemes:
    """Greg screenshotted this: in dark mode the yellow highlight painted pale
    text on a pale ground, making the highlighted passage the LEAST readable
    thing on screen. `mark.hit` and `tr.flash` were fixed then. Reading the
    rendered pane on 2026-08-10 found the same bug in two more places --
    `.blk.hit` and `.tgt`, which are what a reader hits when they follow a
    finding INTO the paper, the one moment a highlight has a job to do.

    Root cause: both painted through `var(--hit,#fdf3c8)` and `--hit` was
    defined NOWHERE, so the inline fallback was the only value that could ever
    apply and no theme could override it.
    """

    def test_every_css_variable_used_is_defined(self, review):
        """The general invariant, not the four instances. A `var()` naming
        nothing silently freezes its fallback, which is exactly the failure
        above and is invisible in light mode."""
        css = render_viewer(collect(review)).split("<style>")[1].split("</style>")[0]
        defined = set(re.findall(r"(--[a-z0-9-]+)\s*:", css))
        used = set(re.findall(r"var\(\s*(--[a-z0-9-]+)", css))
        assert not (used - defined), f"used but never defined: {sorted(used - defined)}"

    @pytest.mark.parametrize("selector", [
        "mark.hit", "tr.flash", ".blk.hit", ".tgt"])
    def test_each_highlight_pins_its_own_foreground(self, review, selector):
        """Setting only a background inherits the page's text colour, which is
        near-white in dark mode."""
        css = render_viewer(collect(review)).split("<style>")[1].split("</style>")[0]
        rules = [m.group(0) for m in re.finditer(r"[^{}]+\{[^{}]*\}", css)
                 if selector in m.group(0).split("{")[0]]
        assert rules, f"no rule for {selector}"
        assert any(re.search(r"color\s*:\s*#[0-3]", r) for r in rules), \
            f"{selector} never pins a dark foreground"

    def test_the_highlight_ground_is_defined_for_every_theme_state(self, review):
        """Three states: bare `:root`, the `prefers-color-scheme` block, and
        both explicit `data-theme` overrides. A token defined in only some of
        them changes value when a reader flips the toggle."""
        css = render_viewer(collect(review)).split("<style>")[1].split("</style>")[0]
        assert css.count("--hit:") == 4


class TestTheQuestionsCanBeCopiedWithoutOurNotes:
    """Greg, 2026-08-10. The questions are written to be SENT. "Would resolve"
    is our note to ourselves about why each is worth asking, and pasting it to
    an author reads as us explaining our suspicions to them."""

    @pytest.fixture
    def asked(self, review):
        r = json.loads((review / "report.json").read_text())
        r["questions_for_authors"] = [
            {"question": "Could you confirm the Table 1 denominator?",
             "why": "This is the headline finding."},
            {"question": "Was a Firth correction considered?", "why": "Separation."},
        ]
        (review / "report.json").write_text(json.dumps(r))
        return collect(review)

    def test_the_copy_carries_the_questions_and_not_the_notes(self, asked, tmp_path):
        html = section_html(asked, "questions", tmp_path)
        body = html.split('id="qtext"')[1].split("</textarea>")[0]
        assert "Could you confirm the Table 1 denominator?" in body
        assert "Was a Firth correction considered?" in body
        assert "Would resolve" not in body
        assert "This is the headline finding" not in body

    def test_they_are_numbered_the_way_the_page_numbers_them(self, asked, tmp_path):
        body = section_html(asked, "questions", tmp_path).split(
            'id="qtext"')[1].split("</textarea>")[0]
        assert re.search(r"1\.\s*Could you confirm", body)
        assert re.search(r"2\.\s*Was a Firth", body)

    def test_the_notes_still_show_on_the_page(self, asked, tmp_path):
        """Copying without them is not the same as hiding them."""
        assert "Would resolve" in _text(section_html(asked, "questions", tmp_path))

    def test_the_button_says_how_many(self, asked, tmp_path):
        assert "Copy the 2 questions" in _text(
            section_html(asked, "questions", tmp_path))

    def test_the_hidden_textarea_is_still_laid_out(self, review):
        """`execCommand('copy')` copies the SELECTION and an element that is
        not laid out cannot hold one. `display:none` here would break the only
        copy path a `file://` page has when the clipboard API refuses -- which
        Chrome does whenever its window is not the OS foreground window
        ("NotAllowedError: Document is not focused"), measured while building
        this."""
        rules = _css_rules(collect(review))
        assert ".offscreen" in rules, "no .offscreen rule"
        assert "display:none" not in rules[".offscreen"]
        assert "position:absolute" in rules[".offscreen"]

    def test_a_review_with_no_questions_offers_no_button(self, review, tmp_path):
        html = _text(section_html(collect(review), "questions", tmp_path))
        assert "Copy the" not in html
        assert "did not write any" in html


class TestTheSidebarCountStaysOnItsOwnRow:
    """MEASURED by looking at the rendered page: `nav .c` was `float:right`
    inside a block anchor, and a float only stays on the line if the line has
    room. "Questions for the authors" fills the sidebar, so its `7` was pushed
    below that anchor's single-line box and rendered beside the Findings count
    as `9` with a superscript `7` -- while its own row appeared to have no
    count at all. The DOM was correct throughout: one badge per anchor, every
    number right. Nothing but rendering the page could have found it."""

    def test_the_anchor_lays_its_count_out_rather_than_floating_it(self, review):
        rules = _css_rules(collect(review))
        assert "float" not in rules["nav .c"], \
            "a float escapes an anchor whose line is already full"
        assert "display:flex" in rules["nav a"]

    def test_every_section_with_a_count_still_has_exactly_one(self, review, tmp_path):
        """The layout fix must not have changed what the numbers are."""
        html = render_viewer(collect(review))
        nav = html.split("<nav")[1].split("</nav>")[0]
        for a in re.findall(r"<a [^>]*>.*?</a>", nav, re.S):
            assert a.count('class="c"') <= 1


class TestTheLandingPageSaysWhichPaperThisIs:
    """Greg, 2026-08-10: "it is absolutely critical to the user that they know
    what report they're reading on the landing page."

    Moving the metadata table below the verdict fixed a real problem -- the
    abstract used to push the conclusion a screen and a half down -- but it
    took the paper's IDENTITY along with the marketing copy, and those are not
    the same thing. The tab title is not a document."""

    def test_the_title_is_above_the_verdict(self, review, tmp_path):
        html = section_html(review and collect(review), "overview", tmp_path)
        assert "A demonstration paper" in html
        assert html.index("A demonstration paper") < html.index("verdict on this run")

    def test_the_byline_and_doi_are_there_too(self, review, tmp_path):
        html = _text(section_html(collect(review), "overview", tmp_path))
        assert "Doe, J." in html
        assert "10.1234/demo" in html

    def test_the_abstract_is_not_hoisted_with_them(self, review, tmp_path):
        """The abstract is what buried the verdict. Identity is four lines; the
        table and the abstract stay below."""
        p = collect(review)
        p["paper_facts"] = (p.get("paper_facts") or []) + [
            {"fact": "Abstract", "value": "ZZABSTRACTZZ"}]
        html = section_html(p, "overview", tmp_path)
        assert html.index("verdict on this run") < html.index("ZZABSTRACTZZ")

    def test_a_long_author_list_is_cut_by_people_not_characters(
            self, review, tmp_path):
        p = collect(review)
        for f in p["paper_facts"]:
            if f["fact"] == "Authors":
                f["value"] = "Ann Alpha, Bo Beta, Cy Gamma, Di Delta, Ed Epsilon"
        html = _text(section_html(p, "overview", tmp_path))
        assert "Ann Alpha, Bo Beta, Cy Gamma and 2 others" in html


class TestTheTwoGradesSayWhichScaleTheyAreOn:
    """Greg: "why is the top-line Result 'highly suspicious' but the 'verdict'
    is 'questionable'? These are basically the same thing, but they are being
    characterized differently."

    They are not the same thing, and nothing on the page said so. The verdict
    grades THE PAPER on three values; a severity grades ONE FINDING on five.
    Printed side by side unlabelled they read as one grade contradicting
    itself."""

    @pytest.fixture
    def graded(self, review):
        r = json.loads((review / "report.json").read_text())
        r["headline"] = {"severity": "highly_suspicious", "statement": "A thing."}
        (review / "report.json").write_text(json.dumps(r))
        return collect(review)

    def test_the_headline_severity_names_its_object(self, graded, tmp_path):
        assert "Most severe finding" in _text(
            section_html(graded, "overview", tmp_path))

    def test_the_verdict_row_names_its_object(self, graded, tmp_path):
        html = _text(section_html(graded, "overview", tmp_path))
        # RENAMED 2026-08-11 with the vocabulary: the row said "verdict on
        # the paper", which is the same overclaim the old words made.
        # It grades what the checks found, across the paper.
        assert "verdict on this run" in html

    def test_the_page_says_outright_that_the_scales_differ(self, graded, tmp_path):
        """A reader who sees two different words must not have to infer that
        they measure different things.

        WORDING UPDATED 2026-08-18. f245dd0 rewrote this row -- ninety words
        defining one term, cut to a single visible line with the reasoning one
        click away -- and left this test pinning the old sentence, "a different
        scale from the finding severity above". The guarantee is unchanged and
        is asserted here in the terms the page now uses: the distinction is
        VISIBLE without opening anything, and the two scale sizes are stated.
        """
        html = _text(section_html(graded, "overview", tmp_path))
        # Visible without clicking: the row says which object it grades.
        assert "the whole run, not the finding above" in html
        # And the sizes of the two scales are given, so "different" is not
        # left as an assertion the reader has to take on trust.
        assert "has three values" in html and "has five" in html


class TestAGradeOnUsNeverShipsToTheAuthor:
    """`title_quality` scores whether the MODEL followed our finding-title spec.
    `deterministic.check_titles` says in its own docstring that the result is
    "deliberately not [written] to the shipped bundle", and `OPERATOR_ONLY` in
    tests/test_output_is_read.py records the same decision.

    It was in 8 of 8 shipped bundles. The existing test pinned that an operator
    READS the field from run_meta.json and never that the bundle EXCLUDES it,
    so the half that mattered was unenforced -- the decision was written down
    twice and implemented nowhere.

    Greg found it by reading the page and asking what it meant, which is the
    fair question: a panel headed "title quality" inside a review of someone's
    paper reads as a criticism of THEIR title. It grades ours."""

    def test_the_bundle_does_not_carry_it(self, review):
        m = json.loads((review / "run_meta.json").read_text())
        m["title_quality"] = {"pass": False, "n": 9, "n_overlong": 4}
        (review / "run_meta.json").write_text(json.dumps(m))
        assert "title_quality" not in collect(review)["run_meta"]

    def test_nor_does_the_rendered_page(self, review, tmp_path):
        m = json.loads((review / "run_meta.json").read_text())
        m["title_quality"] = {"pass": False, "n": 9,
                              "detail": "ZZTITLEGRADEZZ"}
        (review / "run_meta.json").write_text(json.dumps(m))
        html = render_viewer(collect(review))
        assert "ZZTITLEGRADEZZ" not in html
        assert "title quality" not in _text(html).lower()

    def test_the_operator_copy_is_untouched(self, review):
        """Redaction is of the SHIPPED artefact only. The number is how we know
        whether the spec is being followed; deleting it would end the
        measurement rather than keep it off the author's screen."""
        m = json.loads((review / "run_meta.json").read_text())
        m["title_quality"] = {"pass": False, "n": 9}
        (review / "run_meta.json").write_text(json.dumps(m))
        collect(review)
        again = json.loads((review / "run_meta.json").read_text())
        assert again["title_quality"] == {"pass": False, "n": 9}

    def test_the_cost_of_the_run_is_still_redacted_too(self, review):
        """The rule this joins, pinned so a future edit to the set cannot
        silently drop the case that motivated it."""
        m = json.loads((review / "run_meta.json").read_text())
        m["total_cost_usd"] = 12.5
        (review / "run_meta.json").write_text(json.dumps(m))
        assert "total_cost_usd" not in collect(review)["run_meta"]


def _eval_js(payload: dict, expr: str, tmp_path) -> str:
    """Run an expression against the viewer's own script, so a test measures
    what ships rather than a copy of it."""
    node = shutil.which("node") or shutil.which("nodejs")
    if not node:
        pytest.skip("node not available")
    js = render_viewer(payload).rsplit("<script>", 1)[1].split("</script>")[0]
    # Only the top-level helpers are needed; the DOM stub lets the script reach
    # its end so they exist.
    harness = tmp_path / "h.js"
    harness.write_text(_DOM_STUB.replace(
        "const S = (0, eval)(script + '\\n;S');",
        "const S = (0, eval)(script + '\\n;S');").replace(
        "const sec = S.find(s => s.id === process.argv[4]);\n"
        "if (!sec) { console.error('no such section: ' + process.argv[4]); process.exit(2); }\n"
        "process.stdout.write(sec.build());",
        "process.stdout.write(String((0, eval)(script + '\\n;(' + process.argv[4] + ')')));"))
    (tmp_path / "v.js").write_text(js)
    (tmp_path / "p.json").write_text(json.dumps(payload, default=str))
    r = subprocess.run([node, str(harness), str(tmp_path / "p.json"),
                        str(tmp_path / "v.js"), expr], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


class TestAClickSyncsTheWordsYouClickedOn:
    """Greg, 2026-08-10: clicking the raw text "only highlights the
    corresponding text in the pdf if it is in a different paragraph", and the
    rendered pane "snaps to seemingly a random line from the paragraph in which
    the clicked text resides".

    MEASURED by replaying the old handlers against the real
    10.1038/s41537-025-00576-3 payload at four click positions in each of four
    paragraphs: the raw pane produced ONE distinct probe out of four clicks in
    every paragraph, and the rendered pane handed over the whole paragraph --
    a 1706-character abstract beginning "Cardiovascular diseases (CVDs) are
    the leading cause..." jumped to line 16, "based on their dominant
    characteristics: low-risk CVDs (47.8...".

    One mistake made twice: markdown puts a paragraph on ONE line, so the raw
    pane's newline-to-newline window IS the paragraph, and the rendered pane
    passed `el.textContent`, which is the paragraph by definition. Neither used
    the click position it already had.

    Same replay after the fix: 16/16 clicks gave distinct, monotonically
    advancing PDF lines, each containing a word from under the caret."""

    def test_two_clicks_in_one_paragraph_give_two_different_probes(
            self, review, tmp_path):
        para = ("Alpha beta gamma delta epsilon zeta eta theta iota kappa "
                "lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi "
                "omega alphabet betatron gammaray deltawing epsilonic zetalike "
                "etatype thetawise iotabase kappaform lambdanode muonic")
        out = _eval_js(collect(review), f"""
          (()=>{{ const s={json.dumps(para)};
            const a=probeAround(s, 10), b=probeAround(s, s.length-10);
            return JSON.stringify({{same: a===b, aStart: s.indexOf(a),
                                    bStart: s.indexOf(b)}}); }})()""", tmp_path)
        got = json.loads(out)
        assert got["same"] is False
        assert got["aStart"] < got["bStart"], "the window must follow the caret"

    def test_the_window_never_starts_or_ends_mid_word(self, review, tmp_path):
        """A half-word is a token that matches nothing and dilutes the score."""
        para = "seventeen " * 60
        out = _eval_js(collect(review), f"""
          (()=>{{ const s={json.dumps(para)}, p=probeAround(s, 300);
            const i=s.indexOf(p);
            return JSON.stringify({{
              startsClean: i===0 || s[i-1]===' ',
              endsClean: i+p.length===s.length || s[i+p.length]===' '}}); }})()""",
            tmp_path)
        got = json.loads(out)
        assert got["startsClean"] and got["endsClean"]

    def test_an_unknown_caret_degrades_to_the_old_behaviour(
            self, review, tmp_path):
        """A browser with neither caret API returns -1. That must be the
        previous behaviour, not an empty probe: no worse, never broken."""
        out = _eval_js(collect(review), """
          (()=>{ const s='x '.repeat(200);
            return JSON.stringify(probeAround(s,-1)===s); })()""", tmp_path)
        assert json.loads(out) is True

    def test_a_short_paragraph_is_passed_whole(self, review, tmp_path):
        """Nothing to localise, and trimming it would only lose signal."""
        out = _eval_js(collect(review), """
          (()=>{ const s='one two three four five';
            return JSON.stringify(probeAround(s,3)===s); })()""", tmp_path)
        assert json.loads(out) is True

    def test_the_span_stays_near_one_typeset_line(self, review, tmp_path):
        """The matcher scores by how much of a PDF LINE the probe covers, so
        the probe must CONTAIN a line (~60-70 chars) without becoming a
        paragraph -- which is what made the old scoring report `frac 1` on
        every wrong jump."""
        out = _eval_js(collect(review), "String(PROBE_SPAN)", tmp_path)
        assert 90 <= int(out.strip()) <= 200


class TestNoPercentageIsBuiltFromTwoGuesses:
    """Greg opened the Coverage page and read "16%" as near-total failure.

    MEASURED (Opus audit, 2026-08-10): `stats_found` and `stats_checked` are
    BOTH model-asserted, written by different stages into schema fields that
    never define what one "statistic" is. On 10.1038/s41537-025-00576-3,
    `stats_found` 741 is dominated by table cells -- one of its own component
    terms is literally written "~300" -- while `stats_checked` 122 approximates
    check operations, against 116 atomic checks in the ledger. Different units,
    both guessed, and the viewer divided them.

    Worse, 741 exceeds the checkable surface: `cell_census` on that paper
    returns 920 cells, 497 consumable, 145 runnable. Against the runnable
    surface the same run checked ~30%. The published 16% was not a coverage
    rate."""

    @pytest.fixture
    def asserted(self, review):
        r = json.loads((review / "report.json").read_text())
        r["coverage_summary"] = {"stats_found": 741, "stats_checked": 122}
        (review / "report.json").write_text(json.dumps(r))
        return collect(review)

    def test_the_two_numbers_are_never_divided(self, asserted, tmp_path):
        html = _text(section_html(asserted, "coverage", tmp_path))
        assert "741" in html and "122" in html
        assert "16%" not in html
        assert not re.search(r"\b\d+%\.\s*The rest", html)

    def test_they_are_labelled_as_the_review_s_own_account(self, asserted, tmp_path):
        html = _text(section_html(asserted, "coverage", tmp_path))
        assert "written by the model" in html
        assert "not a measurement" in html

    def test_a_missing_census_says_so_instead_of_falling_back_silently(
            self, asserted, tmp_path):
        """The census is computed on every run at current HEAD; a bundle
        rebuilt from an older run has none. The page used to fall back to the
        model's numbers with nothing said, so a reader could not tell the
        audited figure was missing rather than merely unflattering."""
        html = _text(section_html(asserted, "coverage", tmp_path))
        assert "No audited cell count for this run" in html

    def test_the_census_leads_when_it_is_present(self, review, tmp_path):
        r = json.loads((review / "report.json").read_text())
        r["coverage_summary"] = {"stats_found": 741, "stats_checked": 122,
            "checkable": {"n_cells": 920, "n_consumable": 497, "n_runnable": 145,
                          "cells_checked_via_check_table": 43,
                          "blocked_on_input": 352, "blocked_on_declaration": 0,
                          "missing_inputs": {"n": 352}}}
        (review / "report.json").write_text(json.dumps(r))
        html = _text(section_html(collect(review), "coverage", tmp_path))
        assert "the audited count" in html
        assert "920" in html and "497" in html and "145" in html
        assert "No audited cell count" not in html

    def test_a_blocked_input_is_attributed_to_the_paper(self, review, tmp_path):
        """352 of 497 consumable cells are blocked because the PAPER prints no
        n. Filing that under our shortfall converts a property of the
        publication into an apparent failure of ours."""
        r = json.loads((review / "report.json").read_text())
        r["coverage_summary"] = {"stats_found": 741, "stats_checked": 122,
            "checkable": {"n_cells": 920, "n_consumable": 497, "n_runnable": 145,
                          "cells_checked_via_check_table": 43,
                          "blocked_on_input": 352, "blocked_on_declaration": 0}}
        (review / "report.json").write_text(json.dumps(r))
        html = _text(section_html(collect(review), "coverage", tmp_path))
        assert "THE PAPER does not print an input" in html

    def test_the_checked_count_says_it_understates_itself(self, review, tmp_path):
        """`cells_checked_via_check_table` counts only cells routed through
        `check_table`; a run that called a check directly per cell scores 0.
        Printing that bare, beside a large denominator, is a number that reads
        as a failure and is not one."""
        r = json.loads((review / "report.json").read_text())
        r["coverage_summary"] = {"stats_found": 741, "stats_checked": 122,
            "checkable": {"n_cells": 920, "n_consumable": 497,
                          "cells_checked_via_check_table": 0}}
        (review / "report.json").write_text(json.dumps(r))
        html = _text(section_html(collect(review), "coverage", tmp_path))
        assert "UNDERSTATES" in html


class TestARefusalSaysWhoseLimitItWas:
    """Greg, 2026-08-10: "the naive reading is that our tool failed, when in
    fact it means something more flattering like supplemental materials weren't
    available or insufficient info was reported."

    Classified by hand on the run's own 12 refusals before the code existed:
    the reading "our tool failed 12 times" is wrong on 10 of them."""

    def _refusals(self, review, rows):
        r = json.loads((review / "report.json").read_text())
        r["not_checked"] = rows
        (review / "report.json").write_text(json.dumps(r))
        return collect(review)

    def test_an_explicit_not_applicable_beats_every_keyword(
            self, review, tmp_path):
        """CAUGHT IN TESTING, and the worst direction this can fail in. The
        real entry "detect_duplication across tables -- Not applicable. The
        paper reports no means with standard deviations anywhere..." was filed
        under "the paper does not report it", because the paper keywords
        matched before `na` was tested. That turns a check that simply does not
        apply into an implied deficiency of the publication."""
        p = self._refusals(review, [{"location": "detect_duplication",
            "reason": "Not applicable. The paper reports no means with standard "
                      "deviations anywhere, so there are no (mean, SD) pairs."}])
        html = _text(section_html(p, "coverage", tmp_path))
        assert "does not apply here" in html
        assert "1 does not apply" in html

    def test_our_own_limit_is_never_filed_as_the_paper_s(self, review, tmp_path):
        """Ties resolve AGAINST us on purpose. A classifier that read an
        ambiguous refusal in its own favour would be worse than none."""
        p = self._refusals(review, [{"location": "Table 3",
            "reason": "no batch form of check_estimate_ci exists, and the paper "
                      "prints no test statistic either"}])
        html = _text(section_html(p, "coverage", tmp_path))
        assert "our tooling" in html

    def test_a_reason_it_cannot_place_is_admitted_not_guessed(
            self, review, tmp_path):
        p = self._refusals(review, [{"location": "somewhere",
                                     "reason": "we simply did not get to it"}])
        html = _text(section_html(p, "coverage", tmp_path))
        assert "not classified" in html

    def test_the_counts_come_before_the_table(self, review, tmp_path):
        """The counts are the point: a reader who reads no further should still
        learn that most of the list is not our shortfall."""
        p = self._refusals(review, [
            {"location": "a", "reason": "Not applicable."},
            {"location": "b", "reason": "The paper prints no degrees of freedom."},
            {"location": "c", "reason": "the supplement was not supplied to this review"},
            {"location": "d", "reason": "no batch form exists"}])
        html = section_html(p, "coverage", tmp_path)
        # Against the SORTABLE table, not the phrase "whose limit" -- the
        # intro prose uses those words too, and matching that occurrence would
        # pass whatever the order.
        assert html.index("does not apply to this paper") < html.index("data-sortable")
        flat_ = _text(html)
        for want in ["1 does not apply", "1 the paper does not report",
                     "1 the material was not supplied", "1 this toolkit could not"]:
            assert want in flat_, want


class TestAJudgementIsNotAnUnreproducibleFinding:
    """Greg read "n valid 1 / n invalid 34" under "Reproducibility of findings"
    as near-total failure, which is exactly what it looks like.

    MEASURED over the archive (633 distinct commands): 127 are the model
    correctly reporting that no command reproduces a judgement, 205 are a real
    command in a shape the CLI does not accept, 28 never ran. Only the last two
    are defects, and NEITHER is a defect in the finding -- one of the 9
    chi-square cases was re-run by hand in the correct argument shape and
    returned the paper's printed 180.74 exactly."""

    def test_no_command_applies_is_a_third_state(self):
        from metascience_agent.evaluation.deterministic import classify_reproduction
        for s in ["No", "No forensic tool applies to this finding.",
                  "MCP-only tool, no CLI verb exists", "n/a", "Not applicable",
                  "NO COMMAND APPLIES"]:
            assert classify_reproduction(s) == "no_command_applies", s

    def test_a_real_command_is_never_swallowed_by_the_prose_matcher(self):
        """The matcher is consulted ONLY when the string does not begin with
        `metascience`, so no command can be reclassified out of the count."""
        from metascience_agent.evaluation.deterministic import classify_reproduction
        for s in ["metascience grim 5.5 30",
                  "metascience summation-batch --rows '[]'",
                  "metascience nonexistent-verb --no-such-flag"]:
            assert classify_reproduction(s) == "command", s

    def test_something_that_is_neither_stays_a_command_and_stays_invalid(self):
        """`python foo.py` is a wrong command, not a declaration that none
        applies. Filing it as the latter would hide a real defect."""
        from metascience_agent.evaluation.deterministic import classify_reproduction
        assert classify_reproduction("python foo.py") == "command"

    def test_the_rate_is_stated_over_findings_that_should_have_a_command(
            self, review, tmp_path):
        m = json.loads((review / "run_meta.json").read_text())
        m["reproducibility"] = {"n_findings": 35, "n_valid": 1, "n_invalid": 30,
                                "n_no_command_applies": 4, "n_command_expected": 31,
                                "n_unparseable": 0, "executed": True,
                                "n_ran_ok": 1, "n_ran_failed": 30}
        (review / "run_meta.json").write_text(json.dumps(m))
        html = _text(section_html(collect(review), "run", tmp_path))
        assert "1 of 31" in html
        assert "4 are a reading of the paper" in html
        assert "Not a failure, and not counted as one" in html

    def test_the_panel_says_a_bad_string_is_not_a_bad_finding(
            self, review, tmp_path):
        m = json.loads((review / "run_meta.json").read_text())
        m["reproducibility"] = {"n_findings": 5, "n_valid": 1, "n_command_expected": 5,
                                "n_no_command_applies": 0, "n_ran_ok": 1,
                                "n_ran_failed": 4, "executed": True}
        (review / "run_meta.json").write_text(json.dumps(m))
        html = _text(section_html(collect(review), "run", tmp_path))
        assert "says nothing about whether those findings are right" in html
        assert "wrong argument SHAPE, not wrong arithmetic" in html

    def test_an_old_bundle_gets_the_split_backfilled_from_its_own_findings(
            self, review, tmp_path):
        """Not a rewrite of the archive: the classification is deterministic
        and every input -- each finding's own reproduction string -- is already
        in the payload. The review directory is left untouched."""
        f = json.loads((review / "findings.json").read_text())
        f["findings"] = [
            {"id": "a", "severity": "suspicious", "reproduction": "metascience grim 5.5 30"},
            {"id": "b", "severity": "suspicious", "reproduction": "No forensic tool applies."}]
        (review / "findings.json").write_text(json.dumps(f))
        m = json.loads((review / "run_meta.json").read_text())
        m["reproducibility"] = {"n_findings": 2, "n_valid": 1, "n_invalid": 1,
                                "executed": True, "n_ran_ok": 1, "n_ran_failed": 0}
        (review / "run_meta.json").write_text(json.dumps(m))
        rep = collect(review)["run_meta"]["reproducibility"]
        assert rep["n_no_command_applies"] == 1
        assert rep["n_command_expected"] == 1
        assert "predates the three-way split" in rep["backfilled"]
        # the on-disk record is untouched
        assert "n_no_command_applies" not in json.loads(
            (review / "run_meta.json").read_text())["reproducibility"]

    def test_the_executed_counts_are_never_recomputed_on_a_rebuild(self, review):
        """Running a command is not something a rebuild may do behind the
        operator's back."""
        m = json.loads((review / "run_meta.json").read_text())
        m["reproducibility"] = {"n_findings": 1, "n_valid": 0, "n_invalid": 1,
                                "executed": False, "n_ran_ok": 0, "n_ran_failed": 0}
        (review / "run_meta.json").write_text(json.dumps(m))
        rep = collect(review)["run_meta"]["reproducibility"]
        assert rep["executed"] is False and rep["n_ran_ok"] == 0


class TestAnAbsentRunCountIsNotAZero:
    """FOUND BY THE PAYLOAD/RENDER AUDIT, 2026-08-11, and it was a false
    statement about our own work in published output.

    `reproTally`'s own comment says "an absent row is honest, an invented zero
    is not". `n_ran_ok` was the one field it did not guard: written
    `+r.n_ran_ok||0`, an ABSENT count -- every run that did not pass
    `--execute`, which is nearly all of them -- became a hard zero, and the rate
    line printed "0 of 35 findings ... can be re-run (0%). The shortfall is a
    defect in how we WRITE commands" on a run where no command was ever executed
    and all 34 had passed the static shape check.

    Verified by EXECUTING the shipped function against a real payload, not by
    reading it -- the repo's standing lesson about viewer work."""

    def _run(self, repro: dict) -> str:
        import json as _json
        import re as _re
        import subprocess
        import tempfile
        # Pull the function out of the SHIPPED source rather than retyping it.
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1]
               / "src/metascience_agent/bundle.py").read_text(encoding="utf-8")
        m = _re.search(r"function reproTally\(rep\)\{.*?\n\}", src, _re.S)
        assert m, "reproTally not found in bundle.py"
        prog = ("const D={};const esc=s=>String(s==null?'':s);\n"
                + m.group(0) + f"\nconsole.log(reproTally({_json.dumps(repro)}));")
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as fh:
            fh.write(prog)
            path = fh.name
        out = subprocess.run(["node", path], capture_output=True, text=True)
        if out.returncode:
            pytest.skip(f"node unavailable or failed: {out.stderr[:120]}")
        return " ".join(out.stdout.split())

    def test_no_execution_reports_no_rate_instead_of_zero_percent(self):
        html = self._run({"n_findings": 35, "n_no_command_applies": 1,
                          "n_command_expected": 34})
        assert "0%" not in html
        assert "defect in how we WRITE commands" not in html
        assert "No reproduction command was executed" in html

    def test_a_real_execution_still_reports_its_rate(self):
        """The guard must not silence the case the panel exists for."""
        html = self._run({"n_findings": 35, "n_no_command_applies": 1,
                          "n_command_expected": 34, "n_ran_ok": 30,
                          "n_ran_failed": 4})
        assert "30 of 34" in html
        assert "88%" in html

    def test_a_genuine_zero_still_reads_as_a_defect_of_ours(self):
        """Executed, and none reproduced: that IS our shortfall and must still
        say so. Guarding on absence must not become guarding on zero."""
        html = self._run({"n_findings": 35, "n_no_command_applies": 1,
                          "n_command_expected": 34, "n_ran_ok": 0,
                          "n_ran_failed": 34})
        assert "0 of 34" in html
        assert "defect in how we WRITE commands" in html


class TestTheViewerIsBuiltWithoutBeingAskedFor:
    """Greg, 2026-08-11: "its creation should also be automatic, not needing an
    additional command/prompt."

    `report.md` is the machine's notes; the bundle is the document a person
    reads -- the paper beside the findings, every tool call with the passage it
    read, the refusal list with whose limit each one was. Behind a second verb,
    a run could finish, cost ten dollars, and hand back a directory whose most
    useful artefact did not exist. The standing instruction to "always build
    the bundle" is itself the evidence that nobody reliably remembered."""

    def _analyze_src(self):
        from pathlib import Path as _P
        return (_P(__file__).resolve().parents[1]
                / "src/metascience_agent/cli.py").read_text(encoding="utf-8")

    def test_analyze_builds_the_bundle_itself(self):
        # `analyze` is the FIRST command in the file, so the body is between the
        # first `@app.command()` and the second -- not everything before the
        # first, which is what this originally sliced and which contained no
        # command at all.
        src = self._analyze_src()
        first = src.index("@app.command()")
        second = src.index("@app.command()", first + 1)
        body = src[first:second]
        assert "build_bundle" in body, (
            "the analyze command must build the viewer, not leave it to a "
            "second verb nobody remembers")

    def test_it_can_be_turned_off_but_defaults_on(self):
        src = self._analyze_src()
        assert '"--bundle/--no-bundle"' in src
        assert 'typer.Option(\n        True, "--bundle/--no-bundle"' in src

    def test_a_failed_bundle_does_not_lose_the_analysis(self):
        """The analysis is already paid for and already on disk when this runs.
        A viewer that cannot be built must say so and name the retry, never
        take the review down with it -- and never fail silently either, which
        is the defect this repo keeps finding."""
        src = self._analyze_src()
        i = src.index("build_bundle")
        window = src[i:i + 1200]
        assert "except Exception" in window
        assert "Viewer bundle failed" in window
        assert "metascience bundle" in window, "must name the retry command"

    def test_it_prints_a_windows_path(self):
        """Greg opens these from Windows Explorer; a /mnt/c path is not
        actionable there.

        RE-PINNED 2026-08-22: the analyze command's end-of-run output went
        deliberately quiet (verdict, counts, runtime -- no paths; see the
        CHANGELOG entry and the comment above its bundle call), so the
        Windows path now belongs to the one place a viewer path IS printed:
        the `bundle` command. This used to slice the analyze body and sat
        red as a 'known failure' pinning behavior that had been removed on
        purpose."""
        src = self._analyze_src()
        i = src.index("Bundle written:")
        window = src[i:i + 600]
        assert "_windows_path" in window
        assert "Windows path:" in window


class TestTheValuesSection:
    """The viewer's index over the value register: every value the paper
    printed, what it belongs to, and which checks reached it."""

    @pytest.fixture
    def with_register(self, review):
        import json
        (review / "value_register.json").write_text(json.dumps({
            "n_values": 2, "n_groups": 1, "n_values_bound_to_a_variable": 2,
            "n_per_cell_checks_joined": 1, "n_per_cell_checks_unmatched": 0,
            "n_calls_with_no_matchable_value": 3,
            "is_a_floor": "every count is a LOWER BOUND.",
            "coverage": {"n_table_groups": 1, "n_checked": 1,
                         "n_refused_with_a_reason": 0,
                         "n_no_applicable_tool": 0, "n_silent": 0},
            "same_value": {},
            "groups": [{"id": "grp:t1:r1:i0", "quote": "6.58 (.52)",
                        "variable_id": "v1",
                        "anchor": {"where": "table", "table": "t1", "row": 1,
                                   "col_label": "Upward"},
                        "values": [{"id": "val:t1:r1:i0:mean", "role": "mean",
                                    "printed": "6.58"},
                                   {"id": "val:t1:r1:i0:sd", "role": "sd",
                                    "printed": ".52"}],
                        "applicable_tools": ["grimmer_check"],
                        "checks": [{"tool": "grimmer_check",
                                    "severity": "impossible", "passed": False,
                                    "joined_by": "argument values"}]}],
        }))
        return collect(review)

    def test_it_renders_the_values_and_their_verdicts(self, with_register, tmp_path):
        html = _text(section_html(with_register, "values", tmp_path))
        assert "6.58" in html and ".52" in html
        assert "grimmer_check" in html and "impossible" in html
        assert "mean" in html and "sd" in html

    def test_a_bundle_predating_the_register_says_so(self, review, tmp_path):
        """ABSENT AND EMPTY ARE DIFFERENT. Every bundle built before the
        register existed has no key at all, and rendering "no values" for those
        would be this project's standing failure -- an absence rendered as
        knowledge."""
        html = _text(section_html(collect(review), "values", tmp_path))
        assert "predates the value register" in html
        assert "not a statement that the paper printed no values" in html

    def test_a_group_with_no_verdict_says_why(self, review, tmp_path):
        import json
        (review / "value_register.json").write_text(json.dumps({
            "n_values": 1, "n_groups": 1, "coverage": {}, "same_value": {},
            "groups": [{"id": "g1", "quote": "47 (60.3)", "anchor": {"where": "table"},
                        "values": [{"id": "v", "role": "count", "printed": "47"}],
                        "applicable_tools": ["grim_percentage"], "checks": [],
                        "not_run": [{"reason": "needs n and this cell carries none"}]}],
        }))
        html = _text(section_html(collect(review), "values", tmp_path))
        assert "refused" in html and "needs n" in html

    def test_the_silent_count_names_whose_gap_it_is(self, with_register, tmp_path):
        html = _text(section_html(with_register, "values", tmp_path))
        assert "our gap, not the paper's" in html


class TestTheNumberFloorInTheViewer:
    """The value groups come from a pattern pass, and a shape it has not seen is
    invisible rather than unclassified. This block is every numeric token, which
    cannot be silently incomplete."""

    @pytest.fixture
    def with_numerals(self, review):
        import json
        (review / "value_register.json").write_text(json.dumps({
            "n_groups": 0, "n_values": 0, "coverage": {}, "same_value": {},
            "groups": [],
            "numerals": {
                "n_total": 4, "n_judged": 3, "share_judged": 0.75,
                "by_class": {"statistic": 2, "citation_year": 1, "ordinal": 0,
                             "scale_anchor": 0, "unclassified": 1},
                "note": "n_total is every numeric token.",
                "rows": [
                    {"printed": "4.64", "class": "statistic", "context": "M = 4.64"},
                    {"printed": "1.50", "class": "statistic", "context": "SD = 1.50"},
                    {"printed": "1989", "class": "citation_year", "context": "Wood (1989)"},
                    {"printed": ".91", "class": "unclassified",
                     "context": "Cronbach's alpha = .91"},
                ]},
        }))
        return collect(review)

    def test_the_tally_is_shown_with_its_denominator(self, with_numerals, tmp_path):
        html = _text(section_html(with_numerals, "values", tmp_path))
        assert "Every number in the prose" in html
        assert "Share of 4" in html
        assert "statistic" in html and "citation year" in html

    def test_the_unjudged_residue_is_listed_not_hidden(self, with_numerals, tmp_path):
        """`unclassified` is the honest state for a number the rules could not
        name -- not a failure, and not something to hide behind a count."""
        html = _text(section_html(with_numerals, "values", tmp_path))
        assert "Not yet judged (1)" in html
        assert ".91" in html and "Cronbach" in html

    def test_a_register_without_numerals_renders_nothing_extra(self, review, tmp_path):
        import json
        (review / "value_register.json").write_text(json.dumps({
            "n_groups": 0, "n_values": 0, "coverage": {}, "same_value": {},
            "groups": []}))
        html = _text(section_html(collect(review), "values", tmp_path))
        assert "Every number in the prose" not in html


class TestUnboundRowsAreVisibleToAReader:
    """275 cells across the archive are blocked on an unbound row. A bare count
    cannot tell "nothing was declared for this row" from "several were and they
    conflict" -- and the second is the actionable one."""

    @pytest.fixture
    def with_unbound(self, review):
        import json
        (review / "value_register.json").write_text(json.dumps({
            "n_groups": 0, "n_values": 0, "coverage": {}, "same_value": {},
            "groups": [],
            "unbound_rows": [{
                "row_label": "Self-evaluation", "status": "ambiguous",
                "n_candidates": 2,
                "candidates": [
                    {"variable_id": "v_item", "family": "likert_item",
                     "name": "Self-evaluation (own attractiveness, single item)"},
                    {"variable_id": "v_comp", "family": "likert_composite",
                     "name": "Self-evaluation index, pilot study"}],
                "note": "Several candidates, and they may differ in FAMILY."}],
        }))
        return collect(review)

    def test_the_row_its_candidates_and_their_families_are_shown(
            self, with_unbound, tmp_path):
        html = _text(section_html(with_unbound, "values", tmp_path))
        assert "Rows with no variable bound (1)" in html
        assert "Self-evaluation" in html
        # The families are the point: they decide which checks may run.
        assert "likert_item" in html and "likert_composite" in html

    def test_it_says_why_no_choice_was_made(self, with_unbound, tmp_path):
        html = _text(section_html(with_unbound, "values", tmp_path))
        assert "differ in FAMILY" in html

    def test_a_register_with_everything_bound_renders_nothing(self, review, tmp_path):
        import json
        (review / "value_register.json").write_text(json.dumps({
            "n_groups": 0, "n_values": 0, "coverage": {}, "same_value": {},
            "groups": []}))
        html = _text(section_html(collect(review), "values", tmp_path))
        assert "Rows with no variable bound" not in html


class TestTheBundleAndTheWalkerAgreeAboutTables:
    """Three readers used to answer "how many tables does this paper have":
    `prepass.paper_tables` (shared with `agent._checkable_coverage`),
    `bundle._table_records` (publisher XML only) and `_table_provenance`
    (`tables.json`). `paper_tables`' own docstring warns against exactly this --
    "two walks of the same tables would be two denominators" -- and the bundle
    was the second walk.

    MEASURED on 10.1007--s00702-004-0248-2: the bundle said 0 tables while the
    value register built 64 groups out of that paper's 2 tables and 32 cells."""

    PAPER = (pathlib.Path(__file__).resolve().parents[1]
             / "tests" / "fixtures" / "papers" / "cerebrolysin_papers" / "10.1007--s00702-004-0248-2")

    @pytest.mark.skipif(not PAPER.is_dir(), reason="corpus not present")
    def test_the_counts_match_the_shared_walker(self):
        from metascience_agent import prepass
        from metascience_agent.bundle import _table_records
        st: dict = {}
        recs = _table_records(self.PAPER, status=st)
        walker = prepass.paper_tables(self.PAPER, include_supplements=True)
        assert len(walker) > 0, "fixture paper must actually have tables"
        assert len(recs) == len(walker) == st["n_tables"]

    @pytest.mark.skipif(not PAPER.is_dir(), reason="corpus not present")
    def test_a_pdf_record_carries_its_grid_and_its_extractor(self):
        from metascience_agent.bundle import _table_records
        recs = _table_records(self.PAPER, status={})
        r = recs[0]
        assert r["source"], "a reader must be able to tell which extractor ran"
        assert r["rows"] and any(any(c for c in row) for row in r["rows"])
        assert r["width"] == len(r["rows"][0])

    def test_not_extracted_yet_warns_but_is_not_called_an_error(self, tmp_path):
        """`error` means our attempt FAILED. "Never attempted" is a different
        fact, and collapsing the two is the same defect the corrupt-XML test
        guards, pointed the other way."""
        from metascience_agent.bundle import _table_records
        d = tmp_path / "10.9999--nopdf"
        d.mkdir()
        (d / "10.9999--nopdf.pdf").write_bytes(b"%PDF-1.4\nnot really\n")
        st: dict = {}
        _table_records(d, status=st)
        assert st["error"] == ""
        assert st["xml"] is False


class TestTheTextIntegrityWarningReachesTheReader:
    """`agent.py` has been computing `coverage_summary.text_integrity` and NO
    PAGE READ IT -- `text_integrity` appeared zero times in bundle.py. A paper
    whose font encoding corrupts digits reached a reader with no sign of it, and
    the corruption is not hypothetical: `P < 0\\x0605` was reaching checks as a
    p of ZERO, and `the effect was /C0 0.85 (95% CI /C0 1.2, /C0 0.3)` as a
    POSITIVE 0.85. A detector nobody renders is the same as no detector.

    THESE ARE WIRING TESTS, NOT RENDER TESTS, and the distinction is honest:
    the viewer builds its banner in the browser, so the warning text exists only
    as separate JS string literals in the file and is concatenated at runtime.
    What is checkable here is that the DATA reaches the payload and the BRANCH
    that consumes it exists. The rendering itself was confirmed in a browser."""

    def _payload(self, tmp_path, integrity):
        rd = tmp_path / "10.9999--demo" / "forensic_review"
        rd.mkdir(parents=True)
        (rd / "findings.json").write_text(json.dumps({"paper_id": "x", "findings": []}))
        (rd / "report.json").write_text(json.dumps(
            {"coverage_summary": {"text_integrity": integrity}}))
        return collect(rd)

    def test_the_integrity_verdict_reaches_the_payload(self, tmp_path):
        p = self._payload(tmp_path, {
            "quarantine": True,
            "patterns": [{"pattern": "control character in a number",
                          "count": 12, "corrupts_digits": True, "examples": []}]})
        ti = (p["report_obj"].get("coverage_summary") or {}).get("text_integrity")
        assert ti and ti["quarantine"] is True
        assert ti["patterns"][0]["corrupts_digits"] is True

    def test_a_failed_scan_reaches_the_payload_as_an_error(self, tmp_path):
        """The absence-as-knowledge failure in its usual place: a scan that
        could not run must not arrive as a paper with no corruption."""
        p = self._payload(tmp_path, {"error": "glyph scan failed: OSError"})
        ti = (p["report_obj"].get("coverage_summary") or {}).get("text_integrity")
        assert ti.get("error") and "quarantine" not in ti

    def test_the_viewer_consumes_it(self):
        """Pins the consumer. Before this, `text_integrity` appeared ZERO times
        in bundle.py -- computed every run, rendered never."""
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src" / "metascience_agent" / "bundle.py").read_text()
        assert "cs.text_integrity" in src
        assert "corrupts_digits" in src
        # In `L`, which bears on the findings, not `B`, which bounds the
        # unexplored remainder. Corrupt digits bear on every number above.
        i = src.index("const ti=cs.text_integrity")
        assert "L.push" in src[i:i + 1400]


class TestTheModelsOwnRegisterIsRendered:
    """`register.validate` has run on every review and written its verdict to
    `coverage_summary.statistics_register`, and NOTHING RENDERED IT -- the
    string did not appear in bundle.py. That is the second detector found
    computing a result nobody could see, after `text_integrity`.

    It is the more consequential of the two: `register.py` exists so the model
    is the FINDER while the denominator stays INDEPENDENT of it, and this is
    where a reader learns how many of the model's own claimed statistics could
    be located in the paper, and how many the regex floor found that the model
    never mentioned."""

    def test_the_viewer_consumes_it(self):
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src" / "metascience_agent" / "bundle.py").read_text()
        assert "cs.statistics_register" in src
        assert "modelRegisterBlock()" in src

    def test_it_reads_the_keys_floor_check_actually_returns(self):
        """`floor_check` returns `n_unmatched` and `n_floor`. The first cut read
        `n_missed`, which does not exist, so the comparison rendered nothing at
        all -- a silent blank where the headline number belongs."""
        from metascience_agent import register as R
        r = R.validate(
            [{"quote": "M = 4.2 (SD 0.3)", "values": [4.2, 0.3],
              "source": "table", "checkable": {"tools": ["grim_check"]}}],
            text="the mean was M = 4.2 (SD 0.3) overall",
            floor_items=[{"raw": "M = 4.2"}, {"raw": "p < .05"}])
        assert set(r["floor"]) >= {"n_floor", "n_unmatched"}
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src" / "metascience_agent" / "bundle.py").read_text()
        i = src.index("function modelRegisterBlock()")
        block = src[i:i + 3000]
        assert "fl.n_unmatched" in block
        # `n_missed` may still appear in the comment recording the mistake; what
        # must not survive is a READ of it.
        assert "fl.n_missed" not in block

    def test_absent_stays_distinct_from_empty(self):
        """`register.py` insists on this and the renderer must not collapse it:
        no register emitted is OUR wiring or the model's refusal; an empty one
        is a claim about the paper."""
        from metascience_agent import register as R
        assert R.validate(None)["absent"] is True
        assert R.validate([])["absent"] is False
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src" / "metascience_agent" / "bundle.py").read_text()
        i = src.index("function modelRegisterBlock()")
        assert "sr.absent" in src[i:i + 3000]

    def test_the_provenance_travels_with_it(self):
        """A register built from quarantined text carries values that may be
        wrong in ways no arithmetic can detect -- a lost minus sign reads as an
        ordinary number -- so the reader has to see which text it came from."""
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src" / "metascience_agent" / "bundle.py").read_text()
        i = src.index("function modelRegisterBlock()")
        assert "sr.provenance" in src[i:i + 3000]


class TestAFailedRegisterSaysSoInsteadOfBlamingTheBundle:
    """`agent.py` writes `value_register.error.txt` when the register build
    throws, and its first line says in as many words "This is OUR gap, not a
    fact about the paper". NOTHING LOADED IT.

    So a crashed build reached a reader as the Values section's empty state,
    which read "This review predates the value register" -- naming a cause the
    viewer could not possibly know, in the one branch written to avoid exactly
    that. Three states, kept apart: never built, built and failed, built and
    empty."""

    def _collect(self, tmp_path, *, error: str | None, register: dict | None):
        rd = tmp_path / "10.9999--demo" / "forensic_review"
        rd.mkdir(parents=True)
        (rd / "findings.json").write_text(json.dumps({"paper_id": "x", "findings": []}))
        if error is not None:
            (rd / "value_register.error.txt").write_text(error)
        if register is not None:
            (rd / "value_register.json").write_text(json.dumps(register))
        return collect(rd)

    def test_the_reason_reaches_the_payload(self, tmp_path):
        p = self._collect(tmp_path, error="could not be built\nKeyError('row_label')",
                          register=None)
        assert "KeyError" in (p.get("value_register_error") or "")
        assert not p.get("value_register")

    def test_a_review_that_never_built_one_has_no_error(self, tmp_path):
        """The pre-register bundles. Absent is not failed."""
        p = self._collect(tmp_path, error=None, register=None)
        assert not p.get("value_register_error")
        assert not p.get("value_register")

    def test_the_viewer_prefers_the_reason_over_the_age_excuse(self):
        src = (pathlib.Path(__file__).resolve().parents[1]
               / "src" / "metascience_agent" / "bundle.py").read_text()
        i = src.index("D.value_register_error")
        j = src.index("predates the value register")
        assert i < j, ("the failure branch must be tested BEFORE the "
                       "predates-the-register branch, or a crash keeps "
                       "rendering as an old bundle")

    def test_read_text_is_not_load(self):
        """`_load` returns None for anything that is not json, which is every
        one of these written-out failure reasons."""
        from metascience_agent.bundle import _load, _read_text
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = pathlib.Path(d) / "why.txt"
            f.write_text("not json, just a reason")
            assert _load(f) is None
            assert _read_text(f) == "not json, just a reason"
            assert _read_text(pathlib.Path(d) / "absent.txt") == ""


@pytest.fixture
def v2_review(tmp_path):
    """A PARALLEL-era run dir (v1.0.0+ layout): findings.v2.json + per-agent
    ledgers. Until 2026-08-22 `collect` read only the legacy filenames and
    every bundle of a current run was HOLLOW -- report prose and paper panes,
    zero finding cards, zero ledger -- while exiting 0."""
    paper = tmp_path / "10.9999--v2demo"
    rev = paper / "forensic_review_grok-4-6_v1.5.0"
    rev.mkdir(parents=True)
    (paper / "body.md").write_text(
        "# Body\n\nMethods list Anti-CD3. Results blot CD31.")
    (rev / "findings.v2.json").write_text(json.dumps({
        "schema_version": "2.0",
        "paper_id": "10.9999--v2demo",
        "paper_metadata": {"title": "A v2 demonstration paper",
                           "authors": "Doe, J.", "year": "2026"},
        "adjudication": {
            "verdict": "unresolved", "paper_severity": 4,
            "headline_finding_id": "f_headline1234567890",
            "confidence": "medium",
            "summary": "One reagent-vs-result mismatch anchors the review.",
        },
        "findings": [
            {"finding_id": "f_minor00000000000000", "slug": "notation_nit",
             "producer": "tool_expert", "technique": "statcheck",
             "title": "A rounding notation nit", "description": "Minor.",
             "quote": "p = .049", "location": "Table 2",
             "outcome": "problem", "severity": 2,
             "adjudication": {"action": "kept", "severity": 2,
                              "rationale": "minor but real"}},
            {"finding_id": "f_headline1234567890", "slug": "cd3_vs_cd31",
             "producer": "science_error", "technique": "factual_claim",
             "title": "Methods list Anti-CD3; Results report CD31",
             "description": "The antibody cannot produce the blot shown.",
             "quote": "Methods list Anti-CD3", "location": "Methods",
             "outcome": "problem", "severity": 4, "quote_verified": "verbatim",
             "adjudication": {"action": "kept", "severity": 4,
                              "rationale": "verified in both passages"}},
            {"finding_id": "f_dead0000000000000a", "slug": "chance_pair",
             "producer": "tool_expert", "technique": "detect_duplication",
             "title": "Two matching means", "description": "Chance-level.",
             "quote": "3.1 (0.4)", "location": "Table 1",
             "outcome": "problem", "severity": 3,
             "adjudication": {"action": "discarded",
                              "category": "chance_expected",
                              "rationale": "two shared values is chance"}},
        ],
        "coverage": {"stats_found": 7},
        "anatomy": {"studies": [], "variables": [], "tests": []},
        "unchecked": [{"location": "Fig 3", "reason": "figure"}],
    }))
    (rev / "adjudication.json").write_text(json.dumps({"verdicts": []}))
    (rev / "report.md").write_text("# Review\n\nProse.\n")
    (rev / "run_meta.json").write_text(json.dumps({
        "total_cost_usd": 0.7, "analysed_at": "2026-08-22T12:00:00Z"}))
    for agent_name in ("tool_agent", "science_agent", "adjudicator"):
        (rev / f"toolcalls.{agent_name}.json").write_text(json.dumps([
            {"seq": 1, "tool_short": f"{agent_name}_call", "surface": "forensic_mcp",
             "validated": True, "input": {"x": 1},
             "result": '{"severity": "consistent"}'}]))
    return rev


class TestV2Bundle:
    def test_v2_findings_become_cards(self, v2_review):
        p = collect(v2_review)
        assert p["findings_format"] == "v2"
        cards = p["findings"]
        assert len(cards) == 3
        by_slug = {c["slug"]: c for c in cards}
        assert by_slug["cd3_vs_cd31"]["severity"] == "S4"
        assert by_slug["cd3_vs_cd31"]["severity_9"] == 4
        assert by_slug["cd3_vs_cd31"]["severity_colors"]
        assert by_slug["cd3_vs_cd31"]["id"] == "f_headline1234567890"

    def test_the_five_enum_words_are_never_minted_from_the_ladder(self, v2_review):
        # "impossible" is reachable only through the pipeline's derivation;
        # a 9->5 display mapping would put this system's strongest word on
        # findings that never earned it.
        for c in collect(v2_review)["findings"]:
            assert c["severity"] not in ("impossible", "highly_suspicious",
                                         "suspicious")

    def test_discarded_rows_sink_but_are_retained(self, v2_review):
        cards = collect(v2_review)["findings"]
        assert cards[-1]["slug"] == "chance_pair"
        assert cards[-1]["adjudication_action"] == "discarded"
        assert cards[0]["severity_9"] == 4, "live problems sort severity-desc"

    def test_the_three_agent_ledgers_are_distilled(self, v2_review):
        stages = {c["stage"] for c in collect(v2_review)["calls"]}
        assert stages == {"tool_expert", "science_error", "adjudicator"}

    def test_the_adjudication_block_reaches_the_payload(self, v2_review):
        adj = collect(v2_review)["adjudication"]
        assert adj["verdict"] == "unresolved"
        assert adj["headline_finding_id"] == "f_headline1234567890"

    def test_identity_comes_from_the_v2_doc(self, v2_review):
        p = collect(v2_review)
        assert p["paper_id"] == "10.9999--v2demo"
        assert p["paper_title"] == "A v2 demonstration paper"
        assert p["coverage"] == {"stats_found": 7}
        assert p["unchecked"] and p["unchecked"][0]["location"] == "Fig 3"

    def test_build_bundle_archives_the_v2_files(self, v2_review, tmp_path):
        out = build_bundle(v2_review, tmp_path / "out")
        for name in ("findings.v2.json", "adjudication.json",
                     "toolcalls.science_agent.json"):
            assert (out / "analysis" / name).exists(), name

    def test_the_viewer_carries_the_v2_page(self, v2_review, tmp_path):
        out = build_bundle(v2_review, tmp_path / "out")
        html = (out / "viewer.html").read_text()
        assert "Methods list Anti-CD3; Results report CD31" in html
        assert "findings_format" in html
        assert "v2FindingsPage" in html

    def test_the_findings_section_renders_the_cards(self, v2_review, tmp_path):
        html = section_html(collect(v2_review), "findings", tmp_path)
        assert "Methods list Anti-CD3; Results report CD31" in html
        assert "S4" in html
        assert "the headline finding" in html
        assert "Set aside by the adjudicator" in html
        assert "unresolved" in html

    def test_a_hollow_bundle_refuses_to_ship(self, v2_review, tmp_path,
                                             monkeypatch):
        """The regression pin: if the adapter breaks again, the build must
        FAIL, not produce a viewer with the evidence missing."""
        from metascience_agent import bundle as B
        real = B.collect

        def sabotaged(review_dir, paper_dir=None):
            p = real(review_dir, paper_dir)
            p["findings"] = []
            return p

        monkeypatch.setattr(B, "collect", sabotaged)
        with pytest.raises(RuntimeError, match="hollow bundle"):
            B.build_bundle(v2_review, tmp_path / "out")

    def test_legacy_runs_still_collect_as_legacy(self, review):
        assert collect(review)["findings_format"] == "legacy"
