"""The viewer must show a panel even when that panel's wiring fails.

Measured 2026-09-01 in a real browser, on a real shipped bundle: clicking
"Findings" -- the main tab, on every current (v2) run -- produced a page
containing nothing but the nav.

`show()` hid every section, then built, then wired, then ran `after()`, and
only THEN added the `on` class. `build()` early-returns `v2FindingsPage()` on a
v2 run and renders none of the v1 filter markup, while `after()` still ran the
v1 wiring and threw on `document.getElementById('fcount')`. One null lookup in
one panel blanked the whole document.
"""
import re

from metascience_agent import bundle


def _show_source() -> str:
    src = bundle.__dict__.get("VIEWER_JS") or ""
    if not src:
        # The viewer script is embedded in this module's source.
        import inspect
        src = inspect.getsource(bundle)
    m = re.search(r"function show\(id\)\{.*?\n\}", src, re.S)
    assert m, "show() not found in the viewer source"
    return m.group(0)


class TestAPanelErrorCannotBlankThePage:
    def test_the_section_is_shown_before_anything_fallible_runs(self):
        s = _show_source()
        i_on = s.index("classList.add('on')")
        i_build = s.index("s.build()")
        assert i_on < i_build, (
            "the panel is still made visible only after build(); a throw in "
            "build/after leaves every section hidden")

    def test_build_and_after_are_both_caught(self):
        s = _show_source()
        assert s.count("try {") >= 3, "build, wireTables and after must each be caught"
        assert "catch" in s

    def test_a_failure_is_reported_in_the_panel(self):
        # Silence would read as "this section is empty", which is a claim about
        # the paper. It must read as a viewer fault.
        s = _show_source()
        assert "viewer fault" in s


class TestABuilderMayReturnANode:
    def test_show_accepts_a_node_as_well_as_a_string(self):
        # `tables` builds with createElement and returns the element; every
        # other section returns HTML text. `innerHTML=` stringified it, so that
        # pane rendered the literal `[object HTMLDivElement]` while the nav
        # beside it correctly counted 3 tables.
        s = _show_source()
        assert "nodeType" in s, "a node-returning builder is still stringified"
        assert "appendChild" in s

    def test_the_tables_builder_still_returns_a_node(self):
        # If this ever changes to a string the guard above is harmless, but the
        # pairing is what this test documents.
        import inspect
        src = inspect.getsource(bundle)
        m = re.search(r"S\.push\(\{id:'tables'.*?\n\}\);", src, re.S)
        assert m and "createElement" in m.group(0)


class TestTheV2GuardMatchesTheBuilder:
    def test_after_keys_on_the_same_flag_the_builder_branches_on(self):
        # Reading the same flag, rather than probing for one of the elements,
        # is what keeps the two halves of the section from drifting apart
        # again -- which is how they got here.
        import inspect
        src = inspect.getsource(bundle)
        m = re.search(r"S\.push\(\{id:'findings'.*?\n\}\);", src, re.S)
        assert m, "findings section not found"
        body = m.group(0)
        assert "if(D.findings_format==='v2') return v2FindingsPage();" in body
        after = body[body.index("after()"):]
        assert "if(D.findings_format==='v2') return;" in after


class TestTheEvidenceBannerDenominator:
    """"18 of 0 findings in this report rest on no validated computation."

    Seen live on 10.1002--jfa2.70171, on EVERY panel, because the sentence sits
    in a persistent header. The numerator came from `D.facts.evidence.counts`
    (v2, correct); the denominator came from `rep.findings.length`, and `rep`
    is the v1 `report_obj` the parallel path never writes.
    """

    def _src(self):
        import inspect
        from metascience_agent import bundle
        return inspect.getsource(bundle)

    def test_the_denominator_no_longer_reads_report_obj(self):
        src = self._src()
        assert "' of '+ed.length" not in src
        assert "const ed=rep.findings||[];" not in src

    def test_it_reads_n_from_the_same_block_as_the_counts(self):
        src = self._src()
        assert "evd.n" in src, "the denominator must come from the evidence block"
        assert "evd.counts" in src, "the numerator must come from the same block"

    def test_an_absent_denominator_prints_no_ratio(self):
        # A ratio against a missing population is worse than no ratio. With no
        # usable `n` the sentence states the count alone rather than inventing
        # something to divide by.
        src = self._src()
        assert "(evN?' of '+evN:'')" in src
