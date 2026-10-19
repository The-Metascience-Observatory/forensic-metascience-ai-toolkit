"""The Findings page showed the sweep and hid the review.

Two stages produce findings. The SWEEP emits one per tool verdict, titled by
structure ("Granularity of a mean (GRIM) -- Table 2"). The EDITORIAL stage
triages those into the review's own conclusions, each with a written `title`,
a `consequence`, and `stage1_finding_ids` naming what it rests on.

The page rendered the sweep. So a reader met 23 tool verdicts where the review
had written 13 conclusions, and `title` -- in `report.schema.json` from the
beginning -- was never read by the viewer at all.

Nothing is dropped by the inversion: every sweep finding is either nested under
the finding that cites it or listed as one the report did not carry, and
`findings.json` is in the bundle regardless.
"""
import json
from pathlib import Path

import pytest

from metascience_agent import cli
from metascience_agent.bundle import collect, render_viewer

REVIEW = Path("tests/fixtures/papers/high_value_pdfs_to_run_on/10.1002--mpr.70006/forensic_review_wave3")
pytestmark = pytest.mark.skipif(not REVIEW.exists(), reason="corpus not present")


@pytest.fixture(scope="module")
def payload():
    return collect(REVIEW)


@pytest.fixture(scope="module")
def html(payload):
    return render_viewer(payload)


class TestEditorialFindingsArePrimary:
    def test_the_editorial_titles_reach_the_page(self, payload, html):
        """`title` existed in the schema and the viewer never read it."""
        titles = [f["title"] for f in payload["report_obj"]["findings"] if f.get("title")]
        assert titles, "this fixture is pointless without them"
        assert titles[0] in html

    def test_the_evidence_link_survives_into_the_viewer(self, payload):
        """The nesting is built from `stage1_finding_ids`, so it has to be
        populated and has to point at ids the sweep actually emitted."""
        sweep_ids = {str(f.get("id")) for f in payload["findings"]}
        cited = [str(i) for f in payload["report_obj"]["findings"]
                 for i in (f.get("stage1_finding_ids") or [])]
        assert cited, "no editorial finding cites a sweep finding"
        resolved = [i for i in cited if i in sweep_ids]
        assert len(resolved) == len(cited), "an editorial finding cites an id that does not exist"

    def test_findings_not_carried_into_the_report_are_still_shown(self, payload, html):
        """"ran and found nothing" is a different fact from "never ran", and
        neither should be invisible."""
        cited = {str(i) for f in payload["report_obj"]["findings"]
                 for i in (f.get("stage1_finding_ids") or [])}
        orphans = [f for f in payload["findings"] if str(f.get("id")) not in cited]
        assert orphans, "this fixture is pointless without them"
        assert "Checks the report did not carry" in html

    def test_the_page_falls_back_to_the_sweep_when_there_is_no_editorial_stage(self):
        from metascience_agent.bundle import render_viewer as rv

        assert "The editorial stage produced no findings" in rv({})


class TestTitleEscaping:
    def test_a_location_containing_markup_cannot_inject_it(self, html):
        """`fTitle` interpolated `location` into a heading unescaped."""
        assert "const where=esc(String(f.location||'').trim());" in html

    def test_the_location_is_no_longer_truncated_at_seventy(self, html):
        """A location is WHERE to look; truncating it stops exactly where it
        starts being useful."""
        assert "where.slice(0,70)" not in html


class TestConsequenceIsNotStringified:
    def test_consequence_is_an_object_in_the_real_data(self, payload):
        c = payload["report_obj"]["findings"][0].get("consequence")
        assert isinstance(c, dict), "the [object Object] bug needs this to be true"

    def test_the_page_renders_it_through_the_existing_helper(self, html):
        """`cHtml` already knew how to render it, including the
        computed-vs-asserted distinction. A second renderer would drift."""
        assert "${cHtml(e)}" in html
        assert "[object Object]" not in html


class TestQuestionsSection:
    def test_it_is_its_own_section(self, html):
        assert "S.push({id:'questions'" in html

    def test_it_carries_the_address_the_questions_would_be_sent_to(self, payload, html):
        assert payload["report_obj"]["questions_for_authors"], "fixture needs questions"
        assert "Send to" in html

    def test_an_empty_list_says_so_rather_than_vanishing(self, html):
        assert "This review produced none" in html


def _cost_keys(value, path="") -> list[str]:
    """Every path in a nested structure whose KEY names a price."""
    out = []
    if isinstance(value, dict):
        for k, v in value.items():
            if "cost" in str(k).lower():
                out.append(f"{path}/{k}")
            out += _cost_keys(v, f"{path}/{k}")
    elif isinstance(value, list):
        for i, v in enumerate(value):
            out += _cost_keys(v, f"{path}[{i}]")
    return out


class TestRunDetails:
    """Cost is INTERNAL. It used to be printed here to 4 dp, and both halves of
    that were right about different audiences.

    The 4-dp rule was correct and is NOT abandoned -- `$0.00` reads as "free"
    when it means "under half a cent", so a run summary that prints a price must
    print four places. What changed is WHERE a price may be printed at all. The
    bundle is built to be forwarded to the authors of the paper it criticises,
    and what the review cost us is a fact about our billing, not about their
    work; beside a verdict it reads as a price put on the accusation. So the
    number is stripped from the shippable artefact. The CLI end-of-run line
    no longer prints a price either. The 4-dp rule now lives on
    `run_meta.json` in the review directory, the remaining local record.
    Those are pinned below.

    NOTE for the repo owner: which surfaces count as author-facing rather than
    internal is a wider question still being decided; these tests fix only the
    bundle, which is the one artefact that is definitionally forwardable.
    """

    def test_no_price_reaches_the_forwardable_artefact(self, payload, html):
        """The whole payload, not just the row that used to carry it -- the leak
        this closes was 24 machine paths, 21 session ids AND the run total, so a
        check on one field would have missed most of it."""
        assert _cost_keys(payload) == []
        assert not [r for r in payload["run_facts"] if "cost" in r["fact"].lower()]
        assert "cost_usd" not in html, "the per-stage cost column is gone too"

    def test_the_cli_summary_does_not_print_a_price(self):
        """The end-of-run line is verdict, counts, runtime. Cost stays in
        `run_meta.json`. If a price is reintroduced on the CLI it still owes
        four places (`$0.00` at two places is a false 'free'), but it must
        not come back as a default print."""
        assert f"${0.0037:.2f}" == "$0.00", "the failure mode this rule prevents"
        assert f"${0.0037:.4f}" == "$0.0037"
        src = Path(cli.__file__).read_text(encoding="utf-8")
        assert "Cost: ${result['total_cost_usd']:.4f}" not in src
        assert "_print_analyze_summary" in src

    def test_the_price_is_still_recorded_locally(self):
        """Stripping the bundle must not lose the number -- `run_meta.json` sits
        in the review directory, which is not the shippable artefact."""
        meta = json.loads((REVIEW / "run_meta.json").read_text(encoding="utf-8"))
        assert float(meta["total_cost_usd"]) > 0
        assert all(float(s["cost_usd"]) > 0 for s in meta["stages"].values())

    @pytest.mark.parametrize("heading,answers", [
        ("Commands that would not run", "cannot re-run it"),
        ("How many findings say what they change", "depends on them"),
        ("Did the write-up keep the tool's verdict?", "escalated or softened"),
    ])
    def test_each_opaque_section_now_says_what_it_answers(self, html, heading, answers):
        """Greg could not tell what "Problems", "Consequence" and "Tool severity
        vs recorded severity" were, so a reader will not either."""
        assert heading in html
        assert answers in html
