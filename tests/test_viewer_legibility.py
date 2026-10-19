"""The viewer's coded words, counts and commands, read by someone who is not
a statistician. (PROPOSED: these classes are written to be appended to
tests/test_bundle.py, which owns the `review` fixture and `section_html`;
this scratch copy imports them so both code versions can be exercised.)"""
import json

from tests.test_bundle import review, section_html, flat  # noqa: F401

from metascience_agent.bundle import collect, render_viewer


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
        for section in ("overview", "findings"):
            html = flat(section_html(collect(review), section, tmp_path))
            assert ('class="sev suspicious" title="A discrepancy worth asking '
                    "about." in html), section

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
        from metascience_agent.bundle import GLOSSARY
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

    def _with_editorial(self, review, n=2):
        (review / "report.json").write_text(json.dumps({
            "verdict": "unresolved",
            "findings": [{"id": f"e{i}", "title": f"T{i}",
                          "severity": "suspicious",
                          "stage1_finding_ids": ["f1"] if i == 0 else []}
                         for i in range(n)]}))
        return review

    def test_overview_labels_the_two_universes_separately(self, review, tmp_path):
        html = flat(section_html(collect(self._with_editorial(review)),
                                 "overview", tmp_path))
        assert "findings in the report</th><td>2" in html
        assert "sweep findings the review recorded</th><td>1" in html
        assert "the report carried 1 of them" in html
        # And the OTHER universe is now shown under its own name rather than
        # borrowing this one's.
        assert "the checks returned at" in html or "the write-up recorded at" in html

    def test_the_bare_findings_row_is_gone(self, review, tmp_path):
        html = flat(section_html(collect(self._with_editorial(review)),
                                 "overview", tmp_path))
        assert '<th scope="row">findings</th>' not in html

    def test_without_an_editorial_stage_only_the_sweep_row_shows(self, review, tmp_path):
        """The badge falls back to the sweep count there, so a report row
        saying 0 would contradict it."""
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert "findings in the report" not in html
        assert "sweep findings the review recorded</th><td>1" in html

    def test_the_nav_badge_states_its_universe(self, review):
        """The badge is wired at mount time, outside any section builder, so
        this pins the wiring the way TestTitleEscaping pins fTitle."""
        html = render_viewer(collect(review))
        assert "countTitle" in html
        assert "findings in the report (the sweep recorded" in html
        # "tool verdicts" was the wrong universe here too -- `D.findings` is the
        # sweep's findings, not one row per check that returned.
        assert "tool verdicts; see Overview" not in html

    def test_run_details_labels_the_stage_count_and_the_verdict(self, review, tmp_path):
        meta = json.loads((review / "run_meta.json").read_text())
        meta["stages"] = {
            "sweep": {"model": "opus", "num_findings": 21,
                      "output_tokens": 1, "wall_seconds": 1},
            "editorial": {"model": "opus", "verdict": "unresolved",
                          "output_tokens": 1, "wall_seconds": 1}}
        (review / "run_meta.json").write_text(json.dumps(meta))
        html = flat(section_html(collect(review), "run", tmp_path))
        assert '21 <span class="muted">tool verdicts recorded</span>' in html
        assert "(the verdict)" in html


class TestATemplateWithNoRecordedVerdictIsNotOfferedAsACommand:
    """`reproduction_valid` is stamped by the write path -- but only on runs
    made after that validator existed. On a review without the stamp the only
    check here was `reproduction_valid !== false`, which an ABSENT field
    passes: a literal `metascience grim <mean> <n>` -- the template the model
    was given, with nothing filled in -- rendered as
    `<pre>metascience grim &lt;mean&gt; &lt;n&gt;</pre>`, a paste-and-run
    offer of a command that cannot run. REPRODUCED on this fixture before the
    fix.

    The client-side mirror copies `evaluation/deterministic.py`, including
    its narrowness: `<`, `>`, `{`, `}` count only OUTSIDE quoted arguments.
    That boundary is load-bearing -- CONSTRUCTED counterexample, verified by
    execution: `metascience statcheck --text "... (chi2(3) = 18.9,
    p < 0.001)."` carries `<` inside a quoted argument, and
    `validate_reproduction` calls it valid while `run_reproduction` exits 0.
    Calling it a template would bury a working reproduction under "This one
    IS a defect" -- a false accusation against a sound finding, and the exact
    ~35% false-positive rate deterministic.py measured before it learned
    about quotes."""

    def _finding(self, review, **kw):
        f = json.loads((review / "findings.json").read_text())
        f["findings"][0].pop("reproduction_valid", None)
        f["findings"][0].update(kw)
        (review / "findings.json").write_text(json.dumps(f))
        return review

    def test_an_unjudged_template_is_not_offered_as_a_command(self, review, tmp_path):
        self._finding(review, reproduction="metascience grim <mean> <n>")
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "<pre>metascience grim &lt;mean&gt; &lt;n&gt;</pre>" not in html
        assert "The command was left as a template" in html
        # The template stays visible, marked as what it is, because the
        # reader is told to fill in its inputs and cannot fill what they
        # cannot see.
        assert ("The template: <code>metascience grim &lt;mean&gt; "
                "&lt;n&gt;</code>" in html)

    def test_an_ellipsis_template_is_caught_too(self, review, tmp_path):
        self._finding(review, reproduction="metascience grim ... 30")
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "<pre>metascience grim ... 30</pre>" not in html
        assert "The command was left as a template" in html

    def test_a_quoted_less_than_is_a_command_not_a_template(self, review, tmp_path):
        self._finding(review, reproduction=(
            'metascience statcheck --text "time in service '
            '(chi2(3) = 18.9, p < 0.001)."'))
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "<pre>metascience statcheck" in html
        assert "left as a template" not in html

    def test_a_quoted_json_payload_is_a_command_not_a_template(self, review, tmp_path):
        self._finding(review, reproduction=(
            "metascience multiplicity --tests "
            "'[{\"id\":\"a\",\"p_value\":0.03}]'"))
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "<pre>metascience multiplicity" in html
        assert "left as a template" not in html

    def test_a_recorded_execution_verdict_outranks_the_static_mirror(self, review, tmp_path):
        """`reproduction_valid: true` rests on an actual execution. A static
        mirror must not overrule a measured run in either direction."""
        self._finding(review, reproduction="metascience grim <mean> <n>",
                      reproduction_valid=True)
        html = flat(section_html(collect(review), "findings", tmp_path))
        assert "<pre>metascience grim &lt;mean&gt; &lt;n&gt;</pre>" in html

    def test_the_write_paths_own_judgement_agrees_with_the_mirror(self):
        """The mirror and deterministic.py must call the same things
        templates, or the bundle disagrees with the report beside it."""
        from metascience_agent.evaluation.deterministic import validate_reproduction
        assert validate_reproduction("metascience grim <mean> <n>")["valid"] is False
        assert validate_reproduction(
            """metascience tool run statcheck --json '{"text": "(chi2(3) = 18.9, p < 0.001)."}'"""
        )["valid"] is True
