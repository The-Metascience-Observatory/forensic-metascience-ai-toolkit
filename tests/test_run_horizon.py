"""A run older than the horizon is not evidence about the system as it is now.

GREG FITZGERALD, 2026-08-29, and the cost he is describing is measured:

    "many problems it finds were fixed, and things like the fable subagents keep
     assuming that those runs are representative of the output of our current
     system. It thwarts progress, because it promotes rediscovery and chasing
     false leads."

THE INCIDENT THAT PROMPTED IT. On 2026-08-28 a research round censused 416
findings across 16 archived run directories, found that none carried the fields
the severity gate reads, and concluded the toolkit's central safety guarantee
had never governed a shipped finding. The count was exact and the conclusion was
wrong twice: the gate was wired on 2026-08-21 and every one of those runs
predates it, and the current pipeline writes `findings.v2.json` while all 416
were `findings.json`. A live run then showed the gate firing on 34 of 34 rows.

Two properties carry the design, and each has a test that fails if it is lost.
"""
from __future__ import annotations

import datetime as _dt
import json

import pytest

from metascience_agent import runs

NOW = _dt.datetime(2026, 8, 29, tzinfo=_dt.timezone.utc)


def _run(tmp_path, name, analysed_at=None):
    d = tmp_path / name
    d.mkdir(parents=True)
    if analysed_at is not None:
        (d / "run_meta.json").write_text(
            json.dumps({"analysed_at": analysed_at}), encoding="utf-8")
    return d


class TestItFailsClosed:
    """An undatable run is STALE, not current. The runs that cannot be dated are
    in practice the old ones -- written before the pipeline recorded its own
    date -- so guessing 'current' would admit exactly the wrong set."""

    def test_a_run_with_no_date_at_all_is_stale(self, tmp_path):
        d = _run(tmp_path, "forensic_review")
        assert runs.run_date(d) == (None, "undatable")
        assert runs.is_current(d, now=NOW) is False

    def test_and_it_stays_stale_even_at_a_generous_horizon(self, tmp_path):
        """Widening the horizon must not turn 'we do not know' into 'recent'."""
        d = _run(tmp_path, "forensic_review")
        assert runs.is_current(d, now=NOW, horizon_days=3650) is False

    def test_a_malformed_run_meta_does_not_crash_or_pass(self, tmp_path):
        d = tmp_path / "forensic_review_x"
        d.mkdir()
        (d / "run_meta.json").write_text("{not json", encoding="utf-8")
        assert runs.is_current(d, now=NOW) is False


class TestMtimeIsNotUsed:
    """The sharp edge of the design, and the reason it exists.

    Measured 2026-08-29: all 15 archived run directories under
    `high_value_pdfs_to_run_on/` carry an mtime of 2026-08-22 from a bulk copy,
    while their own recorded `git_sha` values span 08-11 to 08-16. A filesystem
    timestamp dates the COPY. Trusting it would call every stale run current --
    this module's own failure, with the sign inverted.
    """

    def test_a_freshly_touched_old_run_is_still_old(self, tmp_path):
        d = _run(tmp_path, "forensic_review_old", analysed_at="2026-07-01T00:00:00Z")
        d.touch()                       # mtime is now; the run is two months old
        (d / "run_meta.json").touch()
        assert runs.is_current(d, now=NOW) is False
        assert runs.run_date(d)[1] == "analysed_at"


class TestTheOrderOfEvidence:
    def test_the_runs_own_stamp_beats_the_directory_name(self, tmp_path):
        """A human typed the directory name; the run stamped itself."""
        d = _run(tmp_path, "forensic_review_2026-08-28",
                 analysed_at="2026-06-01T00:00:00Z")
        when, how = runs.run_date(d)
        assert how == "analysed_at" and when.month == 6
        assert runs.is_current(d, now=NOW) is False

    def test_the_directory_name_is_used_when_the_run_did_not_stamp_itself(self, tmp_path):
        d = _run(tmp_path, "forensic_review_2026-08-27")
        when, how = runs.run_date(d)
        assert how == "directory_name" and when.day == 27
        assert runs.is_current(d, now=NOW) is True


class TestExclusionIsNeverSilent:
    """This project's house failure mode is absence rendered as knowledge.
    'There were no runs' and 'there were nine and all were stale' are different
    facts, and a shorter list renders the second as the first."""

    def test_the_partition_names_every_exclusion_and_why(self, tmp_path):
        fresh = _run(tmp_path, "a", analysed_at="2026-08-28T00:00:00Z")
        old = _run(tmp_path, "b", analysed_at="2026-07-01T00:00:00Z")
        blind = _run(tmp_path, "c")
        got = runs.partition([fresh, old, blind], now=NOW)
        assert got["n_current"] == 1 and got["n_stale"] == 2
        assert "59 days old" in got["why"][str(old)]
        assert "undatable" in got["why"][str(blind)]

    def test_it_carries_a_sentence_a_caller_can_print(self, tmp_path):
        old = _run(tmp_path, "b", analysed_at="2026-07-01T00:00:00Z")
        note = runs.partition([old], now=NOW)["note"]
        assert "1 excluded" in note and "14 days" in note

    def test_and_says_nothing_when_nothing_was_excluded(self, tmp_path):
        fresh = _run(tmp_path, "a", analysed_at="2026-08-28T00:00:00Z")
        assert runs.partition([fresh], now=NOW)["note"] == ""


class TestTheOverrideIsDeliberateAndVisible:
    def test_the_horizon_can_be_widened_by_environment(self, tmp_path, monkeypatch):
        old = _run(tmp_path, "b", analysed_at="2026-07-01T00:00:00Z")
        assert runs.is_current(old, now=NOW) is False
        monkeypatch.setenv(runs.HORIZON_ENV, "90")
        assert runs.is_current(old, now=NOW) is True

    def test_all_disables_it_entirely_and_the_result_says_so(self, tmp_path, monkeypatch):
        blind = _run(tmp_path, "c")
        monkeypatch.setenv(runs.HORIZON_ENV, "all")
        got = runs.partition([blind], now=NOW)
        assert got["unbounded"] is True and got["n_current"] == 1

    def test_a_nonsense_setting_falls_back_to_the_default_rather_than_opening_up(
            self, tmp_path, monkeypatch):
        """A typo in an environment variable must not silently disable a guard."""
        old = _run(tmp_path, "b", analysed_at="2026-07-01T00:00:00Z")
        monkeypatch.setenv(runs.HORIZON_ENV, "yes please")
        assert runs.is_current(old, now=NOW) is False


class TestThePositiveControl:
    """Without this, every test above could pass on a predicate that always
    returns False, which would 'prevent stale reads' by preventing all reads."""

    def test_a_current_run_is_actually_admitted(self, tmp_path):
        d = _run(tmp_path, "forensic_review_now", analysed_at="2026-08-28T12:00:00Z")
        assert runs.is_current(d, now=NOW) is True

    def test_the_boundary_is_inclusive_at_the_horizon(self, tmp_path):
        exactly = _run(tmp_path, "d", analysed_at="2026-08-15T00:00:00Z")
        assert runs.is_current(exactly, now=NOW) is True     # 14 days
        just_over = _run(tmp_path, "e", analysed_at="2026-08-14T00:00:00Z")
        assert runs.is_current(just_over, now=NOW) is False  # 15 days


class TestTheConsumersActuallyUseIt:
    """A guard nothing calls is the artifact this project keeps producing."""

    @staticmethod
    def _body(fn) -> str:
        """A function's code with its docstring removed.

        Grepping `inspect.getsource` matches the DOCSTRING too, and the first
        version of the test below failed for exactly that reason: the fix
        explains in prose why it no longer sorts on `st_mtime`, and the test
        read its own explanation as the defect. A test that searches source text
        must search the code.
        """
        import ast
        import inspect
        import textwrap
        tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
        node = tree.body[0]
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)):
            node.body = node.body[1:]
        return ast.unparse(node)

    def test_register_view_no_longer_sorts_by_mtime(self):
        from metascience_agent import register_view
        body = self._body(register_view._latest_review)
        assert "st_mtime" not in body, (
            "_latest_review sorted on mtime, which dates the file rather than "
            "the run -- see TestMtimeIsNotUsed")
        assert "current_runs" in body

    def test_corpus_stats_deliberately_does_NOT_filter(self):
        """The guard belongs where a question is interpreted, not where
        arithmetic is done.

        A first version filtered inside `corpus_stats._v2_docs` and broke
        `test_current_doc_prefers_the_dated_run`, which computes over a
        deliberately historical fixture. That failure was right: `compute` runs
        over whatever it is handed, including an intentional archive, and it has
        no channel to report an exclusion -- so filtering there would be exactly
        the silent drop `partition` exists to prevent. The horizon lives in the
        `runs` verb, in `register_view` (which feeds the model), and in the rule
        in CLAUDE.md.
        """
        from metascience_agent import corpus_stats
        assert "current_runs" not in self._body(corpus_stats._v2_docs)

class TestSchemaBeatsAge:
    """Age is a proxy for code identity; `schema_version` is the thing itself.

    Measured 2026-08-29: `forensic_review_2026-08-16` is thirteen days old --
    inside the horizon -- and is schema 1.0, written before the parallel
    pipeline and before the severity gate. It emits `findings.json` where the
    current pipeline emits `findings.v2.json`, and reading the first as the
    second is the mistake that cost a night. Corpus-wide: 25 runs at 1.0, 2 at
    2.0, and the horizon alone admitted two of the 1.0s.
    """

    def test_a_recent_run_from_a_retired_pipeline_is_stale(self, tmp_path):
        d = tmp_path / "forensic_review_recent"
        d.mkdir()
        (d / "run_meta.json").write_text(json.dumps({
            "analysed_at": "2026-08-28T00:00:00Z", "schema_version": "1.0",
        }), encoding="utf-8")
        assert runs.is_current(d, now=NOW) is False

    def test_and_widening_the_horizon_does_not_rescue_it(self, tmp_path):
        d = tmp_path / "forensic_review_recent"
        d.mkdir()
        (d / "run_meta.json").write_text(json.dumps({
            "analysed_at": "2026-08-28T00:00:00Z", "schema_version": "1.0",
        }), encoding="utf-8")
        assert runs.is_current(d, now=NOW, horizon_days=3650) is False

    def test_a_bundle_inherits_the_status_of_the_run_it_copies(self, tmp_path):
        """A copy of stale output is stale output. The bundle carries no
        `run_meta.json`, so without this it slips through on its name."""
        src = tmp_path / "forensic_review_2026-08-28"
        src.mkdir()
        (src / "run_meta.json").write_text(json.dumps({
            "analysed_at": "2026-08-28T00:00:00Z", "schema_version": "1.0",
        }), encoding="utf-8")
        (tmp_path / "forensic_review_2026-08-28_bundle").mkdir()
        assert runs.is_current(src, now=NOW) is False
        assert runs.is_current(tmp_path / "forensic_review_2026-08-28_bundle",
                               now=NOW) is False

    def test_a_bundle_with_no_run_beside_it_is_judged_on_its_own(self, tmp_path):
        orphan = tmp_path / "forensic_review_2026-08-28_bundle"
        orphan.mkdir()
        assert runs.is_current(orphan, now=NOW) is True


class TestTheConstantCannotSilentlyDrift:
    """`CURRENT_RUN_SCHEMA` is a hand-written copy of what the pipeline emits.
    Bumping the pipeline without bumping it would silently readmit the old
    shape -- the failure this module exists to prevent."""

    def test_it_matches_what_a_real_run_wrote(self):
        import json as _json
        import pathlib
        # BOTH archives, from the repo root. The fixture corpus under
        # tests/fixtures/papers/ holds v1-schema runs only (39 of them, measured
        # 2026-09-02); the runs at the CURRENT schema are the eval archive's.
        # Looking at the corpus alone reported "newest on disk is 1.0" against
        # a constant of 2.0 and read the fixture's age as a pipeline drift.
        root = pathlib.Path(__file__).resolve().parents[1]
        metas = sorted(
            list((root / "tests" / "fixtures" / "papers").rglob("run_meta.json"))
            + list((root / "benchmarks" / "paper_reviews" / "runs").rglob("run_meta.json")))
        metas = [m for m in metas if "scratchpad" not in m.parts]
        if not metas:
            pytest.skip("no archived runs in this checkout")
        seen = set()
        for m in metas:
            try:
                seen.add(str(_json.loads(m.read_text()).get("schema_version")))
            except Exception:                                # noqa: BLE001
                continue
        newest = max(seen - {"None"}, default=None)
        assert newest == runs.CURRENT_RUN_SCHEMA, (
            f"the newest schema on disk is {newest} but CURRENT_RUN_SCHEMA is "
            f"{runs.CURRENT_RUN_SCHEMA}; a pipeline bump without a constant "
            f"bump silently readmits retired runs")


class TestTheConstraintRecordIsAlwaysWritten:
    """`producer_constraint_problems` ships even when empty.

    THE INVESTIGATION THAT PRODUCED THIS, recorded because the reported defect
    turned out not to exist and the residue is small and real.

    A live run on 2026-08-29 showed 13 of 34 findings carrying no
    `provisional_severity`, and that was reported as a governance gap -- 38% of
    rows ungoverned by `clamp_provisionals`. It is not one. All 13 are
    `outcome: pass` or `undecided`, which correctly have no severity to clamp
    (`migrate_v2.py:127` sets one only when `outcome == "problem"`), and every
    `problem` row carried one.

    Nor is the delegated question unasked. `clamp_provisionals`' docstring says
    "whether one SHOULD be present is `validate_producer_constraints`' question",
    and that function does ask it: a `problem` row with no provisional is flagged
    `problem_requires_provisional`. It runs on every parallel run
    (`parallel.py:854`).

    What was actually wrong was one line: the result was written `if
    producer_problems:`, so a clean run and a run where the validator never
    executed produced the identical artifact. Every neighbouring key on that doc
    ships empty for exactly this reason.
    """

    def test_a_problem_row_missing_its_provisional_is_flagged(self):
        from metascience_agent import findings_v2 as fv2
        got = fv2.validate_producer_constraints([{
            "slug": "x", "producer": "tool_expert", "outcome": "problem",
            "provisional_severity": None, "severity": None,
            "technique": "grim_check", "computed_by": "registry_tool"}])
        assert "problem_requires_provisional" in [p.get("constraint") for p in got]

    def test_a_pass_row_without_one_is_not_flagged(self):
        """The 13. A finding that is not a problem has no severity to clamp."""
        from metascience_agent import findings_v2 as fv2
        got = fv2.validate_producer_constraints([{
            "slug": "x", "producer": "tool_expert", "outcome": "pass",
            "provisional_severity": None, "severity": None}])
        assert "problem_requires_provisional" not in [
            p.get("constraint") for p in got]

    def test_the_key_is_written_unconditionally(self):
        """Absence of the key must not be the way a clean run is expressed --
        it is indistinguishable from the validator never having run."""
        import ast
        import inspect
        import textwrap
        from metascience_agent import parallel
        tree = ast.parse(textwrap.dedent(
            inspect.getsource(parallel._coordinate_analysis)))
        # the comment quoting the old code must not be mistaken for the code:
        # parse it, do not grep it. An earlier check in this session matched its
        # own explanation twice.
        guarded = [n for n in ast.walk(tree) if isinstance(n, ast.If)
                   and "producer_problems" in ast.unparse(n.test)]
        assert not guarded, (
            "producer_constraint_problems is written behind a condition again; "
            "a clean run and an unrun validator then look identical")
        # THE KEY IS PRESENT AND ITS VALUE IS NOT A LITERAL EMPTY LIST. This
        # used to pin the exact expression `'...': producer_problems`, which
        # broke the moment the value became a call -- the validator now runs at
        # BOTH seams and the results are merged, because three constraints
        # cannot fire before adjudication. The property that matters is that
        # the key is written and carries real output, not how it is spelled.
        src = ast.unparse(tree)
        assert "producer_constraint_problems" in src
        assert "'producer_constraint_problems': []" not in src, (
            "the key ships a hardcoded empty list; a clean run and an unrun "
            "validator then look identical again")
        assert ("producer_problems" in src or
                "_merge_constraint_problems" in src), (
            "the key no longer carries the validator's output")

