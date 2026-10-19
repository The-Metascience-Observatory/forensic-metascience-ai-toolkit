"""What the reader meets on the first screen.

Greg's constraint was that the reader must know WHAT REPORT THEY ARE READING on
the landing page, and only half of it was met: the paper was identified at the
top while who produced the review, when, and with what lived seven screens down
under "How this review was produced". A bundle that arrives by email needs both
above the fold.

Everything here is placement and honesty, not new computation -- the fields all
existed. Which is why it could go wrong quietly, and why it is tested.
"""
import json

from tests.test_bundle import flat, review, section_html  # noqa: F401

from forensic_metascience_ai_toolkit.bundle import _run_facts, collect, render_viewer


class TestTheModelRowStopsContradictingRunDetails:
    """A5. The Overview said one model; Run details, reading the same stages,
    said more than one. One page contradicting another about what produced the
    review, in a document whose value is that its claims can be audited."""

    def _facts(self, tmp_path, stages):
        return {f["fact"]: f for f in _run_facts(tmp_path, {"stages": stages})}

    def test_every_model_that_ran_is_named(self, tmp_path):
        """MEASURED on the archived cerebrolysin run: both stages resolve
        ['claude-haiku-4-5-20251001', 'claude-opus-5'] and bill opus. The row
        showed only the billed one."""
        row = self._facts(tmp_path, {
            "sweep": {"primary_billed_model": "claude-opus-5",
                      "models_resolved": ["claude-haiku-4-5-20251001",
                                          "claude-opus-5"]},
        })["Model"]
        assert "claude-haiku-4-5-20251001" in row["value"]
        assert "claude-opus-5" in row["value"]

    def test_it_says_which_model_carried_the_billing(self, tmp_path):
        """Naming both without saying which is primary trades one confusion for
        another."""
        row = self._facts(tmp_path, {
            "sweep": {"primary_billed_model": "claude-opus-5",
                      "models_resolved": ["claude-haiku-4-5-20251001",
                                          "claude-opus-5"]},
        })["Model"]
        assert "More than one model ran" in row["detail"]
        assert "claude-opus-5 carried the billing" in row["detail"]

    def test_a_single_model_run_gains_no_noise(self, tmp_path):
        row = self._facts(tmp_path, {
            "sweep": {"primary_billed_model": "claude-opus-5",
                      "models_resolved": ["claude-opus-5"]},
        })["Model"]
        assert row["value"] == "claude-opus-5"
        assert row["detail"] == ""

    def test_an_older_run_without_models_resolved_still_reports_something(self, tmp_path):
        """Bundles predate the field. Falling back to the billed model is right;
        printing nothing would be a regression for every archived run."""
        row = self._facts(tmp_path, {"sweep": {"model": "opus"}})["Model"]
        assert row["value"] == "opus"


class TestRunIdentityIsOnTheLandingPage:
    def test_the_strip_names_the_run_not_only_the_paper(self, review, tmp_path):
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert 'class="runid"' in html

    def test_it_is_built_from_run_facts_so_it_cannot_drift(self, review, tmp_path):
        """The strip and the table further down must be ONE computation. Two
        renderings of the same fact is exactly how the model row got into
        trouble, and this test's first draft asserted it with
        `assert X if hasattr(...) else True` -- always true, testing nothing.

        Assert it behaviourally instead: change a `run_facts` value and the
        strip must change with it."""
        payload = collect(review)
        marker = "TOOLKIT-SENTINEL-9137"
        for row in payload.get("run_facts") or []:
            if row["fact"] == "Pipeline version":
                row["value"] = marker
                break
        else:
            (payload.setdefault("run_facts", [])
             .append({"fact": "Pipeline version", "value": marker, "detail": ""}))
        html = flat(section_html(payload, "overview", tmp_path))
        assert marker in html, "the strip does not read from run_facts"

    def test_the_stochasticity_sentence_is_always_present(self, review, tmp_path):
        """MEASURED on the funder demo: `control_blinded` and
        `control_blinded_r2` are two runs of the SAME paper on the same day and
        returned 8 findings and 10, with the same verdict and confidence. The
        viewer presented one run as THE review and said nothing about that.

        Always shown, no per-run computation: there is nothing to get wrong, and
        the fact is true of every run this pipeline has ever produced."""
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert "overlapping, not identical, set of findings" in html


class TestBeforeYouRead:
    def test_the_panel_is_present(self, review, tmp_path):
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert 'class="beforeread"' in html

    def test_it_carries_the_three_things_that_matter(self, review, tmp_path):
        """The base rate, what a refusal means, and the one instruction. These
        lived in section 12 of 12, and nobody reads item 12 first."""
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert "a flag here is a question, not an accusation" in html
        assert "declined to guess" in html
        assert "public allegations are not an appropriate use of this output" in html

    def test_it_sits_ABOVE_the_verdict(self, review, tmp_path):
        """THE CAP IS THE DESIGN. The problem this page already fixed once was a
        conclusion pushed below the fold by material that came first; an
        uncapped preamble would re-create it with better intentions."""
        html = flat(section_html(collect(review), "overview", tmp_path))
        assert html.index('class="beforeread"') < html.index("<h3>Result</h3>")

    def test_the_verdict_is_still_on_the_first_screen(self, review, tmp_path):
        """A crude proxy, but the one that failed before: the panel must not
        push the Result down by more than a few hundred characters."""
        html = flat(section_html(collect(review), "overview", tmp_path))
        gap = html.index("<h3>Result</h3>") - html.index('class="beforeread"')
        assert gap < 1200, f"the panel grew to {gap} characters before the verdict"


class TestStartHereIsSecond:
    def test_it_is_renamed_and_moved(self, review):
        """"How to read this" describes a manual; "Start here" is an
        instruction. Position 12 of 12 was where it could not do its job."""
        html = render_viewer(collect(review))
        assert "moveStartHereSecond" in html
        assert "about.label='Start here'" in html

    def test_the_section_definition_did_not_move(self, review):
        """Reordering the mounted array rather than the `S.push` keeps a
        section's definition next to the code that builds it -- the next
        reorder is one line, not a merge conflict."""
        html = render_viewer(collect(review))
        assert "S.push({id:'about'" in html


class TestTheAbstractIsCollapsed:
    def test_a_long_abstract_becomes_a_details_element(self, review, tmp_path):
        """2,780 characters on the cerebrolysin paper -- the largest single
        block on the landing page of a document about that paper's arithmetic,
        and it is the paper's own marketing copy."""
        html = render_viewer(collect(review))
        assert "own summary, unedited" in html
        assert 'class="abstract"' in html

    def test_short_fields_are_untouched(self, review, tmp_path):
        """The rule keys on length AND on the field being the abstract, so a
        one-line abstract stays inline and no other metadata row is affected."""
        html = render_viewer(collect(review))
        assert "f.fact==='Abstract'" in html
        assert "f.value.length>240" in html
