"""The viewer's coded words, counts and commands, read by someone who is not
a statistician. (PROPOSED: these classes are written to be appended to
tests/test_bundle.py, which owns the `review` fixture and `section_html`;
this scratch copy imports them so both code versions can be exercised.)"""
import json

from tests.test_bundle import review, section_html, flat  # noqa: F401

from forensic_metascience_ai_toolkit.bundle import collect, render_viewer


class TestCodedWordsAreDefinedAtPointOfUse:
    """The reader is not assumed to know the code, and the code was defined
    nowhere they look.

    MEASURED on the wave-3 `10.1002--mpr.70006` bundle: the Overview printed
    `verdict: questionable` -- the most prominent coded word in the document
    -- and the strings `trustworthy`/`untrustworthy` appeared ZERO times in
    the whole viewer, so the scale the word names was not stated anywhere a
    reader could find it, and `questionable` reads as "probably fraudulent",
    an accusation the system did not make. Severity words rendered as bare
    `<span class="sev suspicious">suspicious</span>` with their definitions
    on a different tab, and of the jargon the reports lean on --
    Benjamini-Hochberg, family-wise error rate, tau-hat (all measured in the
    corpus reports) -- two of three were defined nowhere in the bundle.

    Point of use now carries the definition: severity words and the verdict
    get a hover title plus a click-through (data-cb) to the codebook; the
    codebook defines the verdict scale; and known jargon in the rendered
    report is wrapped the way `linkRefs` wraps "Table 2", with wording taken
    from D.glossary so there is one text, not two."""

    def test_the_verdict_word_states_its_scale_and_what_it_is_not(self, review, tmp_path):
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert 'data-cb="cb-verdict"' in html
        assert "not a finding of misconduct" in html
        # RENAMED 2026-08-11 with the vocabulary. The tooltip still names the
        # whole three-value scale, which is the point of the assertion --
        # a reader met the middle word with nothing to place it against.
        assert "One of reconciles / unresolved / does_not_reconcile" in html

    def test_every_severity_word_carries_its_definition(self, review, tmp_path):
        # PORTED 2026-10-19. The five words now reach the page only as TOOL
        # verdicts (a v2 finding wears its 1-9 rung, and the words are never
        # minted from the ladder -- see TestV2Bundle), so the scenario is a
        # check that returned `suspicious`, read where the Overview tallies
        # what the checks returned. The Findings page no longer prints them.
        calls = json.loads((review / "toolcalls.tool_agent.json").read_text())
        calls[0]["result"] = '{"severity": "suspicious"}'
        (review / "toolcalls.tool_agent.json").write_text(json.dumps(calls))
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert ('class="sev suspicious" title="A discrepancy worth asking '
                "about." in html)

    def test_the_codebook_defines_the_verdict_scale(self, review, tmp_path):
        html = flat(section_html(collect(review), "about", tmp_path))
        assert 'id="cb-verdict"' in html
        for word in ("reconciles", "unresolved", "does_not_reconcile"):
            assert f"<code>{word}</code>" in html, word
        assert "NOT a finding of misconduct" in html

    def test_the_codebook_severity_table_shares_the_hover_wording(self, review, tmp_path):
        """Both are rendered from SEV_DEF, so they cannot drift apart."""
        html = flat(section_html(collect(review), "about", tmp_path))
        assert "A REFUSAL. A precondition could not be verified" in html
        assert "a question, not an accusation" in html

    def test_jargon_in_the_report_is_defined_from_the_glossary(self, review, tmp_path):
        (review / "report.md").write_text(
            "# Review\n\nAfter the Benjamini-Hochberg correction two of six "
            "survive; the family-wise error rate is controlled at .05.\n")
        html = flat(section_html(collect(review), "report", tmp_path))
        assert 'data-cb="terms">Benjamini-Hochberg</span>' in html
        assert "controls the share" in html          # the glossary's wording, in the title
        assert 'data-cb="terms">family-wise error rate</span>' in html

    def test_jargon_inside_an_attribute_is_left_alone(self, review, tmp_path):
        """The (>[^<]*?) guard from linkRefs: matching inside a tag would
        corrupt the markup it lands in."""
        (review / "report.md").write_text(
            '# Review\n\nSee [the appendix](https://example.com "about BH") '
            "for the BH procedure.\n")
        html = section_html(collect(review), "report", tmp_path)
        assert 'title="about BH"' in html            # attribute untouched
        assert 'data-cb="terms">BH</span>' in html   # the text node defined

    def test_the_new_glossary_terms_exist_and_name_real_tools(self):
        from forensic_metascience_ai_toolkit.bundle import GLOSSARY
        terms = {g["term"]: g for g in GLOSSARY}
        assert "Family-wise error rate" in terms
        assert "Tau-hat" in terms
        assert terms["Tau-hat"]["detects"] == ("bayesian_table1_dispersion",)


class TestTheThreeFindingCountsAreLabelled:
    """Three counts shared the one word "findings" with no reconciliation.

    MEASURED on the wave-3 `10.1002--mpr.70006` bundle: the Overview said
    `findings 21` (sweep tool verdicts), the Findings badge in the contents
    said 13 (the report's findings) and Run details printed a bare `21` under
    `result` -- three quantities, one word, no labels, reading as one
    contradictory number. (`10.1002--eat.24415` wave 4 shows 13 against 6.)
    Each count now names its universe, and the Overview states the relation
    between the two -- "the report carried K of them".

    RELABELLED 2026-08-11, same intent, one universe further. The sweep row was
    headed "sweep tool verdicts -- one per check that returned a verdict, passes
    included", which is a THIRD universe again: `D.findings` holds the sweep's
    FINDINGS, and the checks that returned returned more of them (24 against 20
    on the archived cerebrolysin run, including two `consistent` the row could
    not show). So the row is now "sweep findings the review recorded", and the
    tool universe gets rows of its own, derived in Python from the check table
    (`viewer_facts.severity_ledger`) so the summary cannot disagree with the
    table it summarises."""

    # PORTED 2026-10-19. The serial pipeline's two universes (the editorial
    # report's findings vs the sweep's) are one on a v2 run: the findings
    # document IS the report's record, set-aside rows included. What survives
    # is the rule that every count names its universe.

    def test_the_bare_findings_row_is_gone(self, review, tmp_path):
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert '<th scope="row">findings</th>' not in html

    def test_the_findings_row_names_its_universe(self, review, tmp_path):
        """One row, labelled with what it counts. No "findings in the report"
        row may reappear beside it: a second count of the same rows is how the
        three contradictory numbers happened."""
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert "findings in the report" not in html
        assert "findings the review recorded</th><td>1" in html

    def test_the_nav_badge_states_its_universe(self, review):
        """The badge is wired at mount time, outside any section builder, so
        this pins the wiring the way TestTitleEscaping pinned fTitle."""
        html = render_viewer(collect(review))
        assert "countTitle" in html
        assert "adjudicated findings (1-9 ladder)" in html
        # "tool verdicts" was the wrong universe here too -- `D.findings` is the
        # findings document, not one row per check that returned.
        assert "tool verdicts; see Overview" not in html

    def test_run_details_labels_the_stage_count_and_the_verdict(self, review, tmp_path):
        meta = json.loads((review / "run_meta.json").read_text())
        meta["stages"] = {
            "tool_agent": {"model": "opus", "num_findings": 21,
                           "output_tokens": 1, "wall_seconds": 1},
            "adjudicator": {"model": "opus", "verdict": "unresolved",
                            "output_tokens": 1, "wall_seconds": 1}}
        (review / "run_meta.json").write_text(json.dumps(meta))
        html = flat(section_html(collect(review), "run", tmp_path))
        assert '21 <span class="muted">tool verdicts recorded</span>' in html
        assert "(the verdict)" in html


