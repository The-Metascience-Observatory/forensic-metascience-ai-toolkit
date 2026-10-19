"""Conservation on what a finished review writes: nothing owed is lost, and
nothing arrives unowned.

Capabilities in this codebase do not break; they stop being CALLED. At least
twelve were written, tested, and left behind when the path moved from
`agent.py` to `parallel.py` -- each passing every existence check while its
output silently stopped appearing.

READ `obligations.__doc__` BEFORE TRUSTING A GREEN RUN HERE. This proves
existence parity and CANNOT prove behaviour parity: `secondlook` was present,
imported, called, and told the adjudicator "No finding accuses the paper" beside
21 findings whose outcome was `problem`. Every assertion in this file would have
passed.
"""

from __future__ import annotations

import pytest

from forensic_metascience_ai_toolkit import obligations as O

# The REAL writer, with only the model stages faked. Fixtures are re-exported
# rather than reimplemented: a second canonical result would drift from the one
# the pipeline tests use, and then this file would be asserting conservation
# over a shape nothing produces.
from .test_parallel_pipeline import fakes, paper, run  # noqa: F401


@pytest.fixture()
def written(paper, fakes, tmp_path):  # noqa: F811 -- pytest fixture injection
    """Drive the REAL writer and return the filenames it produced."""
    from forensic_metascience_ai_toolkit import parallel
    out = tmp_path / "review"
    parallel.write_parallel_outputs(run(paper), out)
    return {f.name for f in out.rglob("*") if f.is_file()}, out


class TestNothingOwedIsLost:
    def test_every_required_artifact_appears(self, written):
        present, out = written
        missing = O.missing(present)
        assert not missing, (
            "the writer stopped producing:\n  " + "\n  ".join(
                f"{a.name} -- {a.why}" for a in missing))

    def test_the_registry_is_not_vacuous(self, written):
        """A conservation test that declares nothing passes forever."""
        present, _ = written
        assert len(O.required_names()) >= 15
        assert len(present) >= 10

    def test_a_deleted_artifact_is_detected(self, written):
        """The test must be able to FAIL -- proven, not assumed."""
        present, _ = written
        assert O.missing(present - {"findings.v2.json"})


class TestNothingArrivesUnowned:
    """The direction that makes this conservation rather than a checklist.

    An unregistered output is not a bug in itself; it is an unanswered question
    about what promise it makes to a reader. `report_v2` printed a `Reproduce:`
    line for months that nobody had validated -- 24 commands per run, of which
    6 actually ran.
    """

    def test_every_file_written_is_accounted_for(self, written):
        present, _ = written
        extra = O.unregistered(present)
        assert not extra, (
            "the writer produced files the registry does not account for:\n  "
            + "\n  ".join(extra)
            + "\n\nAdd each to obligations.PARALLEL_ARTIFACTS with a reason "
              "saying what a reader LOSES without it, or to PARALLEL_TOLERATED "
              "with a reason it need not be owed. Do not delete this test.")

    def test_a_new_unannounced_output_is_detected(self, written):
        """Proven able to fail: a planted unregistered file is caught."""
        present, _ = written
        assert O.unregistered(present | {"surprise_output.json"}) == [
            "surprise_output.json"]


class TestTheRegistryIsHonest:
    def test_every_artifact_says_what_is_lost_without_it(self):
        """A reason that only restates the filename is a sign nobody knows what
        it is for."""
        for a in O.PARALLEL_ARTIFACTS:
            stem = a.name.split(".")[0].replace("_", " ")
            assert len(a.why) > 25, f"{a.name}: give a real reason"
            assert a.why.lower() != stem, f"{a.name}: the reason restates the name"

    def test_every_tolerated_name_has_a_reason(self):
        for name, why in O.PARALLEL_TOLERATED.items():
            assert len(why) > 20, f"{name}: an unexplained exemption defeats the test"

    def test_no_name_is_both_owed_and_tolerated(self):
        overlap = O.declared_names() & set(O.PARALLEL_TOLERATED)
        overlap -= {a.or_error_file for a in O.PARALLEL_ARTIFACTS if a.or_error_file}
        assert not overlap, f"both owed and excused: {sorted(overlap)}"


class TestFieldsInsideTheFilesAreOwedToo:
    """The losses a file registry cannot see.

    The parallel writer emits MORE files than the legacy one (17 against 16).
    What went missing twelve times was FIELDS INSIDE those files -- and
    `reproduction_valid` is the clean case: measured on the 2026-08-29 ajcp
    run, 24 findings carried a `Reproduce:` command and ZERO carried a verdict,
    in a file that existed, was well-formed, and passed every structural check.
    """

    def test_it_detects_the_defect_it_was_built_from(self):
        """A regression fixture in the shape of the real pre-fix output."""
        findings = [{"finding_id": f"f_{i}", "reproduction": "metascience grim"}
                    for i in range(24)]
        rows = O.unmet_field_obligations(findings)
        assert len(rows) == 1
        assert rows[0]["field"] == "reproduction_valid"
        assert rows[0]["n_missing"] == 24 and rows[0]["n_applicable"] == 24

    def test_a_finding_with_no_command_owes_no_verdict(self):
        assert O.unmet_field_obligations([{"finding_id": "f_1"}]) == []

    def test_a_verdict_of_false_satisfies_the_obligation(self):
        """The obligation is to have LOOKED, not to have succeeded."""
        assert O.unmet_field_obligations(
            [{"finding_id": "f_1", "reproduction": "x",
              "reproduction_valid": False}]) == []

    def test_a_quote_owes_a_verification(self):
        rows = O.unmet_field_obligations([{"finding_id": "f_1", "quote": "abc"}])
        assert [r["field"] for r in rows] == ["quote_verified"]

    def test_the_real_writer_meets_them(self, written, tmp_path, paper, fakes):
        """Drives the REAL pipeline and writer. Not vacuous: it asserts that
        the fixture actually produced findings first, because an empty findings
        list satisfies every obligation trivially."""
        import json

        from forensic_metascience_ai_toolkit import parallel
        out = tmp_path / "review_fields"
        parallel.write_parallel_outputs(run(paper), out)
        doc = json.loads((out / "findings.v2.json").read_text())
        findings = doc.get("findings") or []
        assert findings, "no findings were produced; this test would pass vacuously"

        unmet = O.unmet_field_obligations(findings)
        assert not unmet, (
            "the writer produced findings owing fields they do not carry:\n  "
            + "\n  ".join(f"{r['field']} missing on {r['n_missing']}/"
                          f"{r['n_applicable']} -- {r['why']}" for r in unmet))

    def test_every_obligation_names_a_field_the_v2_schema_declares(self):
        """The schema is the contract. `severity_source`, `computation` and
        `sourcing` are named as lost capabilities in the project notes but are
        NOT in findings.v2.schema.json -- they are v1 fields, and a v2 document
        omitting them honours a different contract rather than losing one.
        Asserting them would manufacture a debt instead of recording one."""
        import json
        import pathlib

        schema = json.loads(
            (pathlib.Path(__file__).resolve().parents[1] / "src"
             / "forensic_metascience_ai_toolkit" / "schema"
             / "findings.v2.schema.json").read_text(encoding="utf-8"))
        declared = set(schema["properties"]["findings"]["items"]["properties"])
        for ob in O.FINDING_FIELDS:
            assert ob.field in declared, (
                f"{ob.field} is not in the v2 schema; asserting it would "
                f"manufacture an obligation the contract does not contain")
            if ob.owed_when_present:
                assert ob.owed_when_present in declared


class TestConstraintsAreValidatedAtBothSeams:
    """Three producer constraints cannot fire where the validator ran.

    `validate_producer_constraints` is called at parallel.py:896, BEFORE
    adjudication. `severity_requires_problem`, `severity_on_discarded` and
    `fast_screen_provisional` read `severity`, `adjudication.action` and
    `severity_is_provisional` -- none of which exists until `adjudicate.apply`
    writes them. So an empty `producer_constraint_problems` meant "the
    constraints that could fire at this seam held", and the artifact did not say
    which those were.
    """

    def test_a_post_adjudication_violation_is_invisible_pre_adjudication(self):
        """The fact that makes the second pass necessary."""
        from forensic_metascience_ai_toolkit import findings_v2 as fv2
        row = {"slug": "s", "producer": "tool_expert", "outcome": "pass",
               "provisional_severity": None, "technique": "grim_check",
               "title": "t" * 10, "description": "d" * 30, "location": "Table 2"}
        assert fv2.validate_producer_constraints([row]) == []
        adjudicated = dict(row, severity=5, adjudication={"action": "kept"})
        assert fv2.validate_producer_constraints([adjudicated])

    def test_both_seams_are_merged_and_labelled(self):
        from forensic_metascience_ai_toolkit.parallel import _merge_constraint_problems
        pre = [{"index": 0, "slug": "a", "code": "x"}]
        post = [{"index": 0, "slug": "a", "code": "x"},
                {"index": 1, "slug": "b", "code": "y"}]
        out = _merge_constraint_problems(pre, post)
        assert [p["seen_at"] for p in out] == ["pre", "post"]

    def test_the_same_row_failing_two_constraints_stays_two_problems(self):
        from forensic_metascience_ai_toolkit.parallel import _merge_constraint_problems
        post = [{"index": 0, "slug": "a", "code": "x"},
                {"index": 0, "slug": "a", "code": "y"}]
        assert len(_merge_constraint_problems([], post)) == 2

    def test_a_clean_run_still_reports_an_empty_list(self):
        from forensic_metascience_ai_toolkit.parallel import _merge_constraint_problems
        assert _merge_constraint_problems([], []) == []

    def test_the_real_writer_reports_the_key(self, written):
        """`ALWAYS WRITTEN, EMPTY LIST AND ALL` -- absence must stay
        distinguishable from a validator that never ran."""
        import json
        present, out = written
        doc = json.loads((out / "findings.v2.json").read_text())
        assert "producer_constraint_problems" in doc


class TestTheWritersRealOutputsAreAllDeclared:
    """The conservation test is only as good as the file list it is handed.

    MEASURED TWICE, 2026-09-02 and 2026-09-03: `report.pdf` and then
    `source_coverage.json` were added to `write_parallel_outputs` and neither
    was registered. Both were caught by luck rather than by this suite -- the
    pipeline tests drive the writer with fakes that produce neither file, so
    `unregistered()` was never asked about them. This asks directly.
    """

    #: Every name `parallel.write_parallel_outputs` can write. Read off the
    #: function, not off a run, so a new `_w(...)` call has to appear here.
    WRITER_OUTPUTS = {
        "findings.v2.json", "adjudication.json", "report.md", "report.pdf",
        "run_meta.json", "source_coverage.json", "source_coverage.error.txt",
        "sandbox_audit.json", "sandbox_audit.error.txt",
        "value_register.json",
        *(f"{k}.{a}.{e}" for k, e in (("prompt", "md"), ("system_prompt", "md"),
                                      ("toolcalls", "json"), ("messages", "json"))
          for a in ("tool_agent", "science_agent", "adjudicator")),
    }

    def test_nothing_the_writer_emits_is_unregistered(self):
        from forensic_metascience_ai_toolkit import obligations as O
        stray = O.unregistered(self.WRITER_OUTPUTS)
        assert not stray, (
            f"{stray} can be written by write_parallel_outputs but is in "
            "neither PARALLEL_ARTIFACTS nor PARALLEL_TOLERATED -- an "
            "unannounced output is how the conservation direction gets "
            "quietly defeated")

    def test_the_list_is_not_silently_stale(self):
        """A `_w("something.json", ...)` the list above does not know about."""
        import inspect
        import re

        from forensic_metascience_ai_toolkit import parallel
        src = inspect.getsource(parallel.write_parallel_outputs)
        literals = set(re.findall(r'_w\(\s*"([a-z_0-9.]+\.(?:json|md))"', src))
        unknown = literals - self.WRITER_OUTPUTS
        assert not unknown, (
            f"write_parallel_outputs writes {unknown}, which WRITER_OUTPUTS "
            "does not list; add it there and to obligations.py")
