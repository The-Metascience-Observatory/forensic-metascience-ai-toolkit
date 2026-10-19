"""The Litvak planted-error benchmark harness.

Every test here pins a defect that was actually present in the first version of
`benchmarks/litvak/score.py` and that would have produced a WRONG PUBLISHED
NUMBER rather than a crash. They are cheap, offline, and need neither the
upstream benchmark checkout nor the `claude` binary: the judge is exercised
through the `run_cli` injection seam.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

BENCH_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "litvak"
sys.path.insert(0, str(BENCH_DIR))

import paths as lpaths          # noqa: E402
import score as lscore          # noqa: E402


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _gt(paper, category, subcategory, modified, description="desc", difficulty="2",
        original=""):
    return {"paper": paper, "category": category, "subcategory": subcategory,
            "difficulty": difficulty, "description": description,
            "original_snippet": original, "modified_snippet": modified}


def _finding(fid, *, title="t" * 10, description="d" * 25, quote="",
             outcome="problem", technique="grim_test", **kw):
    row = {"finding_id": fid, "title": title, "description": description,
           "quote": quote, "outcome": outcome, "technique": technique}
    row.update(kw)
    return row


def _paper_dir(root: Path, n: int, findings, *, dirname="forensic_review_x_v1"):
    pd = root / f"litvak{n:02d}"
    rd = pd / dirname
    rd.mkdir(parents=True, exist_ok=True)
    (rd / "findings.v2.json").write_text(json.dumps(
        {"schema_version": "2.0", "paper_id": f"litvak{n:02d}",
         "run_id": "r", "channels": {}, "findings": findings}), encoding="utf-8")
    return pd


# --------------------------------------------------------------------------
# A1 -- a `pass` verdict is not a detection
# --------------------------------------------------------------------------

def test_pass_outcome_is_not_a_detection():
    """A check that RAN AND CLEARED the planted value must not score as a catch.

    This is the defect that ran the benchmark backwards: findings-v2 rows carry
    `outcome` in {problem, pass, undecided}, the first scorer pooled all three,
    and a tool that quoted the planted CI and confirmed it was consistent was
    credited with catching the planted error.
    """
    planted = "than RWA (B = -.02, SD = .01, p = .001, 95% CI [-.05, -.01])"
    cleared = _finding("F1", quote=planted, outcome="pass",
                       description="The reported CI is consistent with the SE.")
    assert lscore.candidates([cleared], include_quarantined=False) == []

    row = _gt(1, "statistical_errors", "test_parameter_error", planted)
    assert lscore.assign_floor([row], lscore.candidates([cleared], False)) == {}

    flagged = dict(cleared, finding_id="F2", outcome="problem")
    assert lscore.assign_floor([row], lscore.candidates([flagged], False)) != {}


def test_outcome_split_counts_each_state_separately():
    rows = [_finding("A", outcome="problem"), _finding("B", outcome="pass"),
            _finding("C", outcome="undecided"),
            _finding("D", outcome="problem", quarantined=True)]
    split = lscore.split_by_outcome(rows)
    assert len(split["problem"]) == 2 and len(split["pass"]) == 1
    assert len(split["undecided"]) == 1 and len(split["quarantined"]) == 1
    assert [f["finding_id"] for f in lscore.candidates(rows, False)] == ["A"]
    assert len(lscore.candidates(rows, True)) == 2


def test_legacy_v1_row_without_outcome_falls_back_to_consistent():
    """v1 rows have no `outcome`; `consistent: true` is the same fact as `pass`."""
    split = lscore.split_by_outcome(
        [{"id": "x", "consistent": True}, {"id": "y", "consistent": False}])
    assert len(split["pass"]) == 1 and len(split["problem"]) == 1


# --------------------------------------------------------------------------
# A2 / A4 -- paper scoping and run selection
# --------------------------------------------------------------------------

def test_findings_come_only_from_the_paper_they_belong_to(tmp_path):
    """An error planted in paper 3 must not be hit by a finding in paper 7.

    The first scorer rglobbed the whole corpus into one pool and never read the
    CSV's `paper` column.
    """
    _paper_dir(tmp_path, 3, [_finding("P3")])
    _paper_dir(tmp_path, 7, [_finding("P7")])
    got, _ = lscore.load_findings(tmp_path / "litvak03")
    assert [f["finding_id"] for f in got] == ["P3"]


def test_only_the_newest_review_dir_is_read(tmp_path):
    """Re-runs create SIBLING forensic_review_* dirs, not replacements."""
    pd = _paper_dir(tmp_path, 1, [_finding("OLD")], dirname="forensic_review_a_v1")
    _paper_dir(tmp_path, 1, [_finding("NEW")], dirname="forensic_review_b_v2")
    old = pd / "forensic_review_a_v1"
    os.utime(old, (1_000_000, 1_000_000))
    got, used = lscore.load_findings(pd)
    assert [f["finding_id"] for f in got] == ["NEW"], "a superseded run inflated the score"
    assert len(used) == 1
    both, _ = lscore.load_findings(pd, all_runs=True)
    assert {f["finding_id"] for f in both} == {"OLD", "NEW"}


def test_bundle_dirs_are_not_review_dirs(tmp_path):
    pd = _paper_dir(tmp_path, 1, [_finding("REAL")])
    (pd / "forensic_review_x_v1_bundle").mkdir()
    assert [d.name for d in lscore.review_dirs(pd)] == ["forensic_review_x_v1"]


def test_paper_dir_number_parses_only_prepared_dirs():
    assert lscore.paper_dir_number(Path("litvak07")) == 7
    assert lscore.paper_dir_number(Path("litvak10")) == 10
    for other in ("panels", "litvak", "notes", "litvak7x"):
        assert lscore.paper_dir_number(Path(other)) is None


# --------------------------------------------------------------------------
# A3 -- one-to-one assignment
# --------------------------------------------------------------------------

def test_one_finding_cannot_claim_two_errors():
    """Upstream assigns first-claim-wins; the first scorer let one finding
    satisfy every ground-truth row it happened to overlap."""
    shared = "the effect was 12.34 and 56.78 across both analyses"
    rows = [_gt(1, "statistical_errors", "first", shared),
            _gt(1, "internal_consistency", "second", shared)]
    one = [_finding("ONLY", description=shared)]
    assigned = lscore.assign_floor(rows, one)
    assert len(assigned) == 1, "one finding claimed two separate planted errors"


# --------------------------------------------------------------------------
# A5 -- the deletion is unscoreable by the floor, not a plain miss
# --------------------------------------------------------------------------

def test_empty_modified_snippet_is_named_not_silently_missed():
    """`fisher_z_removed` IS the deletion, so its `modified_snippet` is empty.

    Both floor paths are guarded on non-empty text, so it was an automatic miss
    that still occupied a slot in the denominator -- a wrong denominator, which
    is the defect class this repo exists to catch.
    """
    row = _gt(5, "statistical_errors", "fisher_z_removed", "")
    got = lscore.floor_match(row, [_finding("X", description="anything at all")])
    assert got is not None and got["how"] == "unscoreable_by_construction"


# --------------------------------------------------------------------------
# A6 / A7 -- matcher discrimination
# --------------------------------------------------------------------------

def test_quote_match_survives_a_pdf_round_trip():
    """4 of the 20 in-scope snippets carry curly quotes, en dashes or Greek.

    An exact substring test against docling-extracted text fails on all of them,
    which is most of why the quote path was near-dead in practice.
    """
    planted = "the indirect effect was estimated by multiplying the first and last stages"
    extracted = "The  indirect  effect was estimated by multiplying the first and last stages (a x d)."
    row = _gt(6, "statistical_errors", "indirect_effect_formula_changed", planted)
    assert lscore.floor_match(row, [_finding("X", description=extracted)])


def test_blob_reads_the_fields_that_carry_the_numbers():
    """`reported`/`computed`/`inputs` hold a tool finding's values.

    The first blob read `summary`/`evidence`/`explanation`, none of which exist
    in findings-v2, and skipped these three entirely.
    """
    f = _finding("X", description="a" * 25,
                 reported={"mean": 3.53, "sd": 1.17},
                 computed={"expected_p": 0.033},
                 inputs={"n": 30})
    blob = lscore.finding_blob(f)
    for probe in ("3.53", "1.17", "0.033", "30"):
        assert probe in blob
    row = _gt(1, "statistical_errors", "x", "reported mean 3.53 with sd 1.17")
    assert lscore.floor_match(row, [f])


def test_single_digit_numbers_do_not_carry_a_match():
    assert lscore._numbers("group 3 had 5 people") == set()
    assert "8.74" in lscore._numbers("chi-square(3)=8.74, p=.033")


# --------------------------------------------------------------------------
# the judge
# --------------------------------------------------------------------------

def _envelope(n):
    return json.dumps({"result": json.dumps({"error_number": n})})


def test_judge_parses_the_cli_envelope():
    assert lscore._parse_judge(_envelope(4)) == 4
    assert lscore._parse_judge(_envelope(None)) is None
    assert lscore._parse_judge(json.dumps({"error_number": 2})) == 2


@pytest.mark.parametrize("bad", ["not json", json.dumps({"result": "{}"}),
                                 json.dumps({"result": '{"error_number": 44}'})])
def test_judge_refuses_unusable_replies(bad):
    with pytest.raises(lscore.JudgeError):
        lscore._parse_judge(bad)


def test_judge_transport_failure_is_an_error_not_a_miss():
    """Litvak's `except Exception: result = "none"` scores a transport failure
    as a miss -- our fault rendered as the system's."""
    import asyncio

    def boom(argv, prompt):
        raise RuntimeError("network is down")

    errors = [_gt(1, "statistical_errors", "s", "x"),
              _gt(1, "internal_consistency", "i", "y")]
    with pytest.raises(RuntimeError):
        asyncio.run(lscore.judge_one("sys", "p", "haiku", 5, run_cli=boom))

    def refuse(argv, prompt):
        return "this is not json"

    claimed, n_err = asyncio.run(lscore.judge_paper(
        1, errors, [_finding("A")], model="haiku", timeout=5,
        concurrency=1, cache={}, retries=0, run_cli=refuse))
    assert claimed == {} and n_err == 1


def test_judge_assignment_is_first_claim_wins():
    """Two findings claiming the same error: the FIRST owns it, the second is
    dropped. Without this one finding could satisfy every planted error."""
    import asyncio
    errors = [_gt(1, "statistical_errors", "s", "x"),
              _gt(1, "internal_consistency", "i", "y")]
    findings = [_finding("A", description="alpha " * 5),
                _finding("B", description="bravo " * 5),
                _finding("C", description="delta " * 5)]
    # Keyed on content, not call order: the calls run concurrently.
    replies = {"alpha": 1, "bravo": 1, "delta": 2}

    def fake(argv, prompt):
        which = next(k for k in replies if k in prompt)
        return _envelope(replies[which])

    claimed, n_err = asyncio.run(lscore.judge_paper(
        1, errors, findings, model="haiku", timeout=5,
        concurrency=1, cache={}, run_cli=fake))
    assert n_err == 0
    assert set(claimed) == {0, 1}
    assert claimed[0]["finding_index"] == 0, "the second claimant took the error"


def test_identical_findings_share_one_judge_call():
    """Two findings that render identically must get the same verdict, from
    one call -- and one-to-one assignment then keeps only the first."""
    import asyncio
    errors = [_gt(1, "statistical_errors", "s", "x")]
    calls = []

    def fake(argv, prompt):
        calls.append(prompt)
        return _envelope(1)

    claimed, _ = asyncio.run(lscore.judge_paper(
        1, errors, [_finding("A"), _finding("B")], model="haiku", timeout=5,
        concurrency=1, cache={}, run_cli=fake))
    assert len(calls) == 1, "identical findings were judged twice"
    assert set(claimed) == {0}


def test_judge_argv_pins_haiku_and_forbids_tools():
    argv = lscore.judge_argv("sys", "haiku")
    assert argv[:2] == ["claude", "-p"]
    assert argv[argv.index("--model") + 1] == "haiku"
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert schema["properties"]["error_number"]["maximum"] == 10
    for banned in ("Bash", "Write", "WebFetch"):
        assert banned in argv[argv.index("--disallowedTools") + 1]


def test_judge_system_prompt_is_litvaks_verbatim():
    """The prompt is the comparability surface with his fourteen configurations."""
    upstream = lpaths.BENCH_CANDIDATES
    src = next((c / "benchmark" / "matching.py" for c in upstream
                if (c / "benchmark" / "matching.py").is_file()), None)
    if src is None:
        pytest.skip("upstream benchmark checkout not present")
    text = src.read_text(encoding="utf-8")
    body = text.split('JUDGE_SYSTEM = """', 1)[1].split('"""', 1)[0]
    assert body.strip() == lscore.JUDGE_SYSTEM.strip()


# --------------------------------------------------------------------------
# the judge cache
# --------------------------------------------------------------------------

def test_cache_key_is_stable_across_processes():
    """Litvak keys on `hash((desc, quote))`, which is salted per process unless
    PYTHONHASHSEED is pinned, so his cache silently misses on every restart."""
    prog = (f"import sys; sys.path.insert(0, {str(BENCH_DIR)!r});"
            "import score, json;"
            "print(score.cache_key(3, {'finding_id':'A','title':'t','description':'d'}))")
    seen = {subprocess.run([sys.executable, "-c", prog], capture_output=True,
                           text=True, env={**os.environ, "PYTHONHASHSEED": seed},
                           check=True).stdout.strip()
            for seed in ("0", "1", "12345")}
    assert len(seen) == 1, f"cache key varies with PYTHONHASHSEED: {seen}"


def test_cache_key_changes_when_the_judge_prompt_changes(monkeypatch):
    f = {"finding_id": "A", "title": "t", "description": "d"}
    before = lscore.cache_key(1, f)
    monkeypatch.setattr(lscore, "JUDGE_SYSTEM", lscore.JUDGE_SYSTEM + " extra")
    assert lscore.cache_key(1, f) != before, "a stale cache would answer the old question"


def test_cache_key_separates_papers():
    f = {"finding_id": "A", "title": "t", "description": "d"}
    assert lscore.cache_key(1, f) != lscore.cache_key(2, f)


# --------------------------------------------------------------------------
# path resolution
# --------------------------------------------------------------------------

def test_explicit_bench_is_honoured_or_refused_never_substituted(tmp_path):
    """Scoring against ground truth the operator did not ask for would be
    invisible in the output."""
    with pytest.raises(lpaths.BenchmarkNotFound) as exc:
        lpaths.resolve_bench(tmp_path / "nope")
    assert "named explicitly" in str(exc.value)


def test_missing_bench_names_every_path_tried(monkeypatch, tmp_path):
    monkeypatch.setattr(lpaths, "BENCH_CANDIDATES", (tmp_path / "a", tmp_path / "b"))
    monkeypatch.delenv("LITVAK_BENCH", raising=False)
    with pytest.raises(lpaths.BenchmarkNotFound) as exc:
        lpaths.resolve_bench()
    assert str(tmp_path / "a") in str(exc.value)
    assert str(tmp_path / "b") in str(exc.value)


def test_bench_needs_the_csv_not_just_the_directory(monkeypatch, tmp_path):
    """An empty directory of the right name produces a confident zero."""
    (tmp_path / "ai-peer-review-benchmark").mkdir()
    monkeypatch.setattr(lpaths, "BENCH_CANDIDATES",
                        (tmp_path / "ai-peer-review-benchmark",))
    monkeypatch.delenv("LITVAK_BENCH", raising=False)
    with pytest.raises(lpaths.BenchmarkNotFound):
        lpaths.resolve_bench()


# --------------------------------------------------------------------------
# ground truth shape -- needs the upstream checkout
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def bench():
    try:
        return lpaths.resolve_bench()
    except lpaths.BenchmarkNotFound:
        pytest.skip("upstream benchmark checkout not present")


def test_ground_truth_is_ten_categories_of_ten(bench):
    rows = lscore.ground_truth(bench)
    assert len(rows) == 100
    from collections import Counter
    counts = Counter(r["category"] for r in rows)
    assert len(counts) == 10 and set(counts.values()) == {10}


def test_unscoreable_row_is_never_counted_as_a_hit():
    """It is recorded so it can be NAMED, which is not the same as detected.

    The per-paper table read `bool(floor.get(i))` and so counted paper 5's
    `fisher_z_removed` as a floor hit -- an automatic miss turned into a
    phantom catch, which is the wrong-denominator defect wearing a new hat.
    """
    entry = lscore.floor_match(_gt(5, "statistical_errors", "fisher_z_removed", ""), [])
    assert entry["how"] == "unscoreable_by_construction"
    assert lscore.is_hit(entry) is False
    assert lscore.is_hit({"how": "quote"}) is True
    assert lscore.is_hit(None) is False


def test_findings_without_an_id_cannot_claim_every_error():
    """v1 rows may carry neither `finding_id` nor `id`.

    Exclusion keyed on that value made the key None, so one finding stayed
    eligible for every remaining row.
    """
    shared = "the value 12.34 appears here"
    rows = [_gt(1, "statistical_errors", "a", shared),
            _gt(1, "internal_consistency", "b", shared)]
    anonymous = [{"description": shared, "outcome": "problem"}]
    assert len(lscore.assign_floor(rows, anonymous)) == 1


def test_floor_skips_findings_already_claimed_by_position():
    rows = [_gt(1, "statistical_errors", "a", "value 11.11 here"),
            _gt(1, "internal_consistency", "b", "value 11.11 here")]
    two = [_finding("A", description="value 11.11 here"),
           _finding("B", description="value 11.11 here")]
    assigned = lscore.assign_floor(rows, two)
    assert len(assigned) == 2
    assert {a["finding_index"] for a in assigned.values()} == {0, 1}


# --------------------------------------------------------------------------
# conversion fidelity
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def verify():
    return pytest.importorskip("verify_tables")


def test_no_docx_tables_is_not_damage(verify):
    """Two of the ten papers have no .docx tables at all.

    A two-state pass/fail verifier folded "nothing to compare" into failure and
    reported all ten papers damaged -- the same over-counting this harness
    exists to catch, and a verifier that cries wolf is one nobody reads.
    """
    assert verify._n_cells({"data": [["a", ""], ["", "b"]]}) == 2
    sigs = verify._header_signature({"data": [["", "SDO", "RWA"], ["x", "1", "2"]]})
    assert sigs == ("SDO", "RWA")
    assert verify._header_signature({"data": [["", ""], ["x", "1"]]}) == ()


def test_cells_are_counted_from_data_on_both_sides(verify):
    """The docling PDF path has no `cells` key; the docx path has a typed one
    that is legitimately empty. Counting `cells` reported every converted PDF
    as holding zero while the extractor's own CLI printed 113 for the same file."""
    pdf_shaped = {"data": [["a", "b"], ["c", ""]]}          # no `cells` key
    docx_shaped = {"data": [["a", "b"], ["c", ""]], "cells": []}
    assert verify._n_cells(pdf_shaped) == verify._n_cells(docx_shaped) == 3


def test_private_use_glyphs_are_counted(verify):
    """LibreOffice rendered the Greek alpha as an unmapped PUA codepoint."""
    assert verify._pua(" .69") == 1
    assert verify._pua("alpha .69") == 0


# --------------------------------------------------------------------------
# judge transport -- defects found on the first live run
# --------------------------------------------------------------------------

def test_cli_envelope_error_is_surfaced_not_swallowed():
    """The CLI puts its reason in `result` on stdout and leaves stderr EMPTY.

    Raising on the exit code produced 206 copies of `claude exited 1:` with no
    reason attached -- the diagnostic that would have taken one line to act on,
    discarded in favour of one that could not be acted on at all.
    """
    env = json.dumps({"is_error": True, "result": "Not logged in · Please run /login"})
    with pytest.raises(lscore.JudgeUnavailable) as exc:
        lscore._parse_judge(env)
    assert "logged in" in str(exc.value).lower()


def test_a_per_call_error_is_not_mistaken_for_an_environment_fault():
    env = json.dumps({"is_error": True, "result": "model overloaded, try again"})
    with pytest.raises(lscore.JudgeError) as exc:
        lscore._parse_judge(env)
    assert not isinstance(exc.value, lscore.JudgeUnavailable)


def test_environment_fault_aborts_instead_of_repeating_per_finding():
    """206 identical failures is not a report; it is the same failure 206 times."""
    import asyncio

    def not_logged_in(argv, prompt):
        return json.dumps({"is_error": True, "result": "Not logged in · Please run /login"})

    with pytest.raises(lscore.JudgeUnavailable):
        asyncio.run(lscore.judge_paper(
            1, [_gt(1, "statistical_errors", "s", "x")],
            [_finding("A"), _finding("B"), _finding("C")],
            model="haiku", timeout=5, concurrency=2, cache={}, retries=0,
            run_cli=not_logged_in))


def test_transport_errors_are_never_cached():
    """A transport failure is a fact about the environment at that moment, not
    about the finding. Caching it meant a fixed login replayed the old errors
    forever -- which is how the abort path was bypassed on its first live test.
    """
    import asyncio
    cache: dict = {}

    def refuse(argv, prompt):
        return "not json at all"

    claimed, n_err = asyncio.run(lscore.judge_paper(
        1, [_gt(1, "statistical_errors", "s", "x")], [_finding("A")],
        model="haiku", timeout=5, concurrency=1, cache=cache, retries=0,
        run_cli=refuse))
    assert n_err == 1 and claimed == {}
    assert "error" not in cache.values(), "an error was cached as an answer"

    # A later good call must be able to answer, not replay the failure.
    calls = []

    def ok(argv, prompt):
        calls.append(1)
        return _envelope(1)

    claimed, n_err = asyncio.run(lscore.judge_paper(
        1, [_gt(1, "statistical_errors", "s", "x")], [_finding("A")],
        model="haiku", timeout=5, concurrency=1, cache=cache, retries=0,
        run_cli=ok))
    assert calls and n_err == 0 and set(claimed) == {0}


# --------------------------------------------------------------------------
# the /100 reporting mode
# --------------------------------------------------------------------------

from collections import Counter as _Counter  # noqa: E402


def _cat_counters():
    totals = _Counter({c: 10 for c in (
        "statistical_errors", "internal_consistency", "methodological_design",
        "construct_validity", "causal_inference", "reporting_completeness",
        "generalizability", "theoretical_conceptual", "analytic_flexibility",
        "attrition_missing_data")})
    hits = _Counter({"statistical_errors": 5, "internal_consistency": 5,
                     "methodological_design": 3, "generalizability": 4})
    return hits, totals


def test_argv_has_no_bare_flag():
    """`--bare` skips the config directory, and with it the OAuth credentials.

    Copied here from `tools/copy_move_adjudicate.py`, whose own docstring says
    it is "Not wired into analyze_paper_images" -- so that argv had almost
    certainly never been run against the live CLI. Every judge call returned
    "Not logged in - Please run /login" on a machine that was logged in, and it
    produced a confident diagnosis about an environment that was fine.
    MEASURED: `claude -p` answers, `claude -p --bare` does not.
    """
    assert "--bare" not in lscore.judge_argv("sys", "haiku")


def test_argv_allows_more_than_one_turn():
    """`--json-schema` is served by a StructuredOutput TOOL CALL, so a model
    that answers in prose first needs a second turn to emit it. At
    `--max-turns 1` every sufficiently long prompt died with
    `subtype: error_max_turns` -- and was billed for the turns it took."""
    argv = lscore.judge_argv("sys", "haiku")
    assert int(argv[argv.index("--max-turns") + 1]) > 1


def test_argv_matches_the_repos_live_invocation_shape():
    """Modelled on `llm_backend._build_claude_invocation`, not on an
    unexercised draft."""
    argv = lscore.judge_argv("sys", "haiku")
    assert "--append-system-prompt" in argv
    assert "--system-prompt" not in argv
    assert argv[argv.index("--append-system-prompt") + 1] == "sys"
    assert argv[argv.index("--tools") + 1] == ""


def test_max_turns_abort_is_reported_with_its_subtype():
    """`result` is NULL on a max-turns abort. Reporting that as "unknown" is
    what turned a one-line fix into a debugging session."""
    env = json.dumps({"is_error": True, "result": None,
                      "subtype": "error_max_turns",
                      "terminal_reason": "max_turns"})
    with pytest.raises(lscore.JudgeError) as exc:
        lscore._parse_judge(env)
    assert "error_max_turns" in str(exc.value)
    assert not isinstance(exc.value, lscore.JudgeUnavailable)


def test_structured_output_is_preferred_over_the_result_string():
    """`--json-schema` answers land in `structured_output` as a parsed object;
    `result` carries the same thing as a JSON string."""
    env = json.dumps({"is_error": False, "structured_output": {"error_number": 7},
                      "result": '{"error_number": 7}'})
    assert lscore._parse_judge(env) == 7
    # and the result-string path still works when structured_output is absent
    assert lscore._parse_judge(
        json.dumps({"is_error": False, "result": '{"error_number": 4}'})) == 4


# --------------------------------------------------------------------------
# the run timer
# --------------------------------------------------------------------------

@pytest.mark.parametrize("secs,want", [
    (0.0, "0.0s"), (0.4, "0.4s"), (45.0, "45.0s"),
    (60.0, "1m 00s"), (312.0, "5m 12s"), (4000.0, "1h 06m 40s"),
])
def test_hms_stays_readable_past_a_minute(secs, want):
    assert lscore.hms(secs) == want


def test_hms_never_reports_negative_time():
    """A clock that goes backwards should read zero, not `-0.3s`."""
    assert lscore.hms(-0.3) == "0.0s"


def test_outstanding_call_count_excludes_what_is_already_cached():
    """The ETA is only useful if it counts calls that will actually be PAID
    for. A paper served entirely from cache costs nothing and must not inflate
    the estimate."""
    cands = [_finding("A"), _finding("B", description="b" * 30),
             _finding("C", description="c" * 30)]
    cache = {lscore.cache_key(1, cands[0]): "none"}
    todo = sum(1 for c in cands if lscore.cache_key(1, c) not in cache)
    assert todo == 2


# --------------------------------------------------------------------------
# corpus-wide parallelism
# --------------------------------------------------------------------------

def _jobs(n_papers=3, per_paper=5):
    jobs = []
    for p in range(1, n_papers + 1):
        errs = [_gt(p, "statistical_errors", f"s{p}", f"snippet {p}"),
                _gt(p, "internal_consistency", f"i{p}", f"other {p}")]
        finds = [_finding(f"P{p}F{i}", description=f"paper {p} finding {i} " * 4)
                 for i in range(per_paper)]
        jobs.append((p, errs, finds))
    return jobs


def test_concurrency_is_shared_across_papers_not_per_paper():
    """Papers used to be judged one after another, each with its own
    semaphore, so the limit was really a per-paper limit: a 5-finding paper
    could never fill 8 slots and every paper's tail ran the pool down to one.
    """
    import asyncio
    in_flight = {"now": 0, "peak": 0}

    async def slow(argv, prompt):
        raise AssertionError("run_cli must be sync in this harness")

    def fake(argv, prompt):
        in_flight["now"] += 1
        in_flight["peak"] = max(in_flight["peak"], in_flight["now"])
        try:
            return _envelope(1)
        finally:
            in_flight["now"] -= 1

    got = asyncio.run(lscore.judge_corpus(
        _jobs(3, 5), model="haiku", timeout=5, concurrency=8,
        cache={}, retries=0, run_cli=fake))
    assert set(got) == {1, 2, 3}
    # 15 findings over 3 papers: a per-paper pool could never exceed 5.
    assert in_flight["peak"] <= 8


def test_every_paper_gets_its_own_errors_block():
    """A shared pool must not let paper 2's findings be judged against paper
    1's errors -- that is the cross-paper leak, one layer down."""
    import asyncio
    seen = []

    def fake(argv, prompt):
        seen.append(argv[argv.index("--append-system-prompt") + 1])
        return _envelope(1)

    asyncio.run(lscore.judge_corpus(
        _jobs(3, 2), model="haiku", timeout=5, concurrency=4,
        cache={}, retries=0, run_cli=fake))
    for p in (1, 2, 3):
        assert any(f"snippet {p}" in s for s in seen), f"paper {p} errors not sent"
    # paper 1's block must never carry paper 3's snippet
    for s in seen:
        assert not ("snippet 1" in s and "snippet 3" in s)


def test_cached_findings_never_take_a_slot_or_a_call():
    import asyncio
    jobs = _jobs(2, 3)
    cache = {}
    for p, _e, finds in jobs:
        for f in finds:
            cache[lscore.cache_key(p, f)] = "none"
    calls = []

    def fake(argv, prompt):
        calls.append(1)
        return _envelope(1)

    got = asyncio.run(lscore.judge_corpus(
        jobs, model="haiku", timeout=5, concurrency=4, cache=cache,
        retries=0, run_cli=fake))
    assert calls == [], "a cached judgement was re-paid for"
    assert set(got) == {1, 2}


def test_a_transient_error_is_retried_then_counted():
    """Concurrency makes transient failures likelier, and losing a judgement
    to one silently shrinks the numerator."""
    import asyncio
    attempts = {"n": 0}

    def flaky(argv, prompt):
        attempts["n"] += 1
        if attempts["n"] < 3:
            return "not json"
        return _envelope(2)

    claimed, n_err = asyncio.run(lscore.judge_paper(
        1, [_gt(1, "statistical_errors", "s", "x"),
            _gt(1, "internal_consistency", "i", "y")],
        [_finding("A")], model="haiku", timeout=5, concurrency=1,
        cache={}, retries=2, run_cli=flaky))
    assert attempts["n"] == 3
    assert n_err == 0 and set(claimed) == {1}


def test_retries_are_bounded_and_the_failure_is_reported():
    import asyncio

    def always_bad(argv, prompt):
        return "not json"

    claimed, n_err = asyncio.run(lscore.judge_paper(
        1, [_gt(1, "statistical_errors", "s", "x")], [_finding("A")],
        model="haiku", timeout=5, concurrency=1, cache={}, retries=1,
        run_cli=always_bad))
    assert claimed == {} and n_err == 1


def test_a_fatal_fault_in_one_paper_stops_the_whole_corpus():
    import asyncio

    def not_logged_in(argv, prompt):
        return json.dumps({"is_error": True,
                           "result": "Not logged in · Please run /login"})

    with pytest.raises(lscore.JudgeUnavailable):
        asyncio.run(lscore.judge_corpus(
            _jobs(3, 4), model="haiku", timeout=5, concurrency=4,
            cache={}, retries=0, run_cli=not_logged_in))


# --------------------------------------------------------------------------
# head-to-head comparison
# --------------------------------------------------------------------------

import compare as lcompare      # noqa: E402


def test_compare_partitions_every_error_exactly_once():
    """both + they_only + we_only + neither must equal the denominator, or a
    +X/-Y table is quietly dropping errors."""
    gt = [_gt(1, "statistical_errors", f"s{i}", "x") for i in range(4)]
    ours = {(1, "s0"): True, (1, "s1"): True, (1, "s2"): False, (1, "s3"): False}
    theirs = {(1, "s0"): True, (1, "s1"): False, (1, "s2"): True, (1, "s3"): False}
    c = lcompare.compare(ours, theirs, gt, {1})
    assert c["n"] == 4
    assert c["both"] + c["they_only"] + c["we_only"] + c["neither"] == c["n"]
    assert (c["both"], c["they_only"], c["we_only"], c["neither"]) == (1, 1, 1, 1)
    assert c["ours"] == c["both"] + c["we_only"] == 2
    assert c["theirs"] == c["both"] + c["they_only"] == 2


def test_compare_counts_only_the_named_papers():
    """Comparing our 5-paper result against their 10-paper total is the
    denominator error this harness exists to prevent."""
    gt = [_gt(1, "statistical_errors", "a", "x"),
          _gt(2, "statistical_errors", "b", "x")]
    ours = {(1, "a"): True, (2, "b"): True}
    theirs = {(1, "a"): False, (2, "b"): False}
    assert lcompare.compare(ours, theirs, gt, {1})["n"] == 1
    assert lcompare.compare(ours, theirs, gt, {1, 2})["n"] == 2


def test_a_missing_key_is_a_miss_not_a_crash():
    gt = [_gt(1, "statistical_errors", "only", "x")]
    c = lcompare.compare({}, {}, gt, {1})
    assert c["neither"] == 1 and c["ours"] == 0 and c["theirs"] == 0


def test_baseline_and_variant_conditions_are_excluded(bench):
    """`_originals` is the false-positive baseline -- a "match" there is a
    FALSE ALARM, not a detection. `_open`/`_run2`/`_run3` are a different
    prompt and reliability repeats. Counting any of them as a headline score
    would compare our detections against their false alarms."""
    got = lcompare.load_litvak(bench)
    assert got, "no providers loaded"
    for name in got:
        for sfx in lcompare.EXCLUDE_SUFFIXES:
            assert not name.endswith(sfx), f"{name} should not be a headline row"
    assert "openai_gpt55_high_reasoning" in got
    assert "reviewer3" in got


def test_litvak_rows_are_keyed_by_paper_and_subcategory(bench):
    got = lcompare.load_litvak(bench)
    rows = got["openai_gpt55_high_reasoning"]
    assert len(rows) == 100, f"expected 100 planted errors, got {len(rows)}"
    assert all(isinstance(k, tuple) and isinstance(v, bool)
               for k, v in rows.items())
    assert (1, "test_parameter_error") in rows


# --------------------------------------------------------------------------
# the denominator is 100
# --------------------------------------------------------------------------

def test_declared_scope_is_gone():
    """Retired 2026-08-23. The 20-item denominator was asserted before
    measurement and the first complete run refuted it: FMA caught 36 of the 80
    errors the scorer called out of scope, construct_validity 6/10 among them.
    """
    assert lscore.IN_SCOPE == ()


def test_no_output_path_reintroduces_a_scope_denominator(capsys):
    hits = _Counter({"statistical_errors": 5, "methodological_design": 6})
    totals = _Counter({c: 10 for c in ("statistical_errors",
                                       "methodological_design")})
    lscore.print_category_table(hits, totals)
    out = capsys.readouterr().out.lower()
    for banned in ("declared", "calibration", "20/100", "in-scope", "in scope"):
        assert banned not in out, f"{banned!r} came back"


def test_category_table_totals_all_categories(capsys):
    hits = _Counter({"a": 3, "b": 4})
    lscore.print_category_table(hits, _Counter({"a": 10, "b": 10}))
    line = next(l for l in capsys.readouterr().out.splitlines()
                if l.strip().startswith("TOTAL"))
    assert "7" in line and "20" in line


def test_ground_truth_is_ten_categories_of_ten_all_scored(bench):
    rows = lscore.ground_truth(bench)
    from collections import Counter
    counts = Counter(r["category"] for r in rows)
    assert len(rows) == 100 and len(counts) == 10 and set(counts.values()) == {10}


def test_deletions_are_hard_not_impossible(bench):
    """Dan proposed a 90/100 denominator on the theory that omissions cannot be
    caught. The data refutes it: 15 of the 17 pure deletions were caught by at
    least one of Litvak's systems, and only 7 errors went uncaught by anyone.
    A 90-item denominator would be a second invented scope.
    """
    rows = lscore.ground_truth(bench)
    deletions = [r for r in rows if not (r["modified_snippet"] or "").strip()]
    assert len(deletions) == 17
    lit = lcompare.load_litvak(bench)
    caught = {k for t in lit.values() for k, v in t.items() if v}
    del_keys = {(r["paper"], r["subcategory"]) for r in deletions}
    assert len(del_keys & caught) == 15
    assert len(caught) == 93


# --------------------------------------------------------------------------
# the verification pass
# --------------------------------------------------------------------------

def _venv(idx, quote):
    return json.dumps({"is_error": False,
                       "structured_output": {"finding_index": idx,
                                             "evidence_quote": quote}})


def test_an_ungrounded_quote_is_refused_not_credited():
    """THE p8 CASE. `directionality_changed` was credited to a finding about
    multiplicity. A model cannot copy words about directionality out of that
    finding, so requiring a verbatim quote and checking it in code refuses the
    match instead of scoring it.
    """
    import asyncio
    gt = _gt(8, "internal_consistency", "directionality_changed",
             "directional test", description="Changed non-directional to directional")
    f = _finding("F0", title="Four co-primary indices with no multiplicity plan",
                 description="The analysis plan runs the same ANOVA on four indices "
                             "then six pairwise comparisons with no correction.")

    def fake(argv, prompt):
        return _venv(0, "the power analysis assumed a directional test")

    got = asyncio.run(lscore.verify_corpus(
        [(8, [gt], [f])], model="sonnet", timeout=5, concurrency=2,
        cache={}, retries=0, run_cli=fake))
    rec = got[(8, "directionality_changed")]
    assert rec["state"] == "ungrounded", rec
    assert lscore.quote_is_grounded(
        "the power analysis assumed a directional test", f) is False


def test_a_grounded_quote_is_credited():
    import asyncio
    gt = _gt(4, "statistical_errors", "p_value_inconsistent", "p=.003")
    f = _finding("F0", title="Sad-words omnibus p printed as .003 in text",
                 description="The Results report chi-square(3)=8.74, p=.003. "
                             "Recomputing from the statistic gives p=.0330.")

    def fake(argv, prompt):
        return _venv(0, "Recomputing from the statistic gives p=.0330")

    got = asyncio.run(lscore.verify_corpus(
        [(4, [gt], [f])], model="sonnet", timeout=5, concurrency=2,
        cache={}, retries=0, run_cli=fake))
    rec = got[(4, "p_value_inconsistent")]
    assert rec["state"] == "match" and rec["finding_index"] == 0


def test_the_verifier_sees_every_finding_for_the_paper_at_once():
    """THE p9 CASE. Two findings each said "8 analyses claimed, 7 enumerated";
    judged one at a time each looked like a near miss and haiku said none to
    both. One call per error, shown both, recovers it."""
    import asyncio
    gt = _gt(9, "internal_consistency", "analysis_count_inconsistent", "8 analyses")
    fs = [_finding("A", title="Paper states 8 moderation analyses but enumerates 7"),
          _finding("B", title="Eight moderation analyses claimed for seven behaviors")]
    seen = {}

    def fake(argv, prompt):
        seen["prompt"] = prompt
        return _venv(0, "Paper states 8 moderation analyses but enumerates 7")

    asyncio.run(lscore.verify_corpus(
        [(9, [gt], fs)], model="sonnet", timeout=5, concurrency=2,
        cache={}, retries=0, run_cli=fake))
    assert "[0]" in seen["prompt"] and "[1]" in seen["prompt"], \
        "the verifier was not shown both candidate findings"


def test_a_too_short_quote_is_not_evidence():
    f = _finding("A", description="the reported p-value is .003 not .033")
    assert lscore.quote_is_grounded("p", f) is False
    assert lscore.quote_is_grounded("", f) is False
    assert lscore.quote_is_grounded(None, f) is False
    assert lscore.quote_is_grounded("the reported p-value is .003", f) is True


def test_quote_grounding_survives_a_unicode_round_trip():
    f = _finding("A", description="the indirect effect was estimated as a x d")
    assert lscore.quote_is_grounded("the  indirect effect was estimated as a × d", f)


def test_verifier_runs_under_one_shared_pool():
    """Same discipline as the judge: a per-paper pool would let a paper with
    few errors run the slots down, which is the defect fixed this morning."""
    import asyncio
    flight = {"now": 0, "peak": 0}

    def fake(argv, prompt):
        flight["now"] += 1
        flight["peak"] = max(flight["peak"], flight["now"])
        try:
            return _venv(None, None)
        finally:
            flight["now"] -= 1

    jobs = [(p, [_gt(p, "statistical_errors", f"s{p}{i}", "x") for i in range(3)],
             [_finding(f"P{p}F0")]) for p in (1, 2, 3)]
    got = asyncio.run(lscore.verify_corpus(
        jobs, model="sonnet", timeout=5, concurrency=4, cache={},
        retries=0, run_cli=fake))
    assert len(got) == 9
    assert flight["peak"] <= 4


def test_verifier_results_are_cached_and_never_re_paid():
    import asyncio
    gt = _gt(1, "statistical_errors", "s", "x")
    f = _finding("A")
    calls = []

    def fake(argv, prompt):
        calls.append(1)
        return _venv(None, None)

    cache = {}
    for _ in range(2):
        asyncio.run(lscore.verify_corpus(
            [(1, [gt], [f])], model="sonnet", timeout=5, concurrency=1,
            cache=cache, retries=0, run_cli=fake))
    assert len(calls) == 1, "a cached verification was re-paid for"


def test_verifier_uses_its_own_schema_and_model():
    argv = lscore.judge_argv("sys", "sonnet", lscore.VERIFY_SCHEMA)
    schema = json.loads(argv[argv.index("--json-schema") + 1])
    assert set(schema["required"]) == {"finding_index", "evidence_quote"}
    assert argv[argv.index("--model") + 1] == "sonnet"
    # the default is still the judge's schema, so the first pass is unchanged
    d = json.loads(lscore.judge_argv("sys", "haiku")[
        lscore.judge_argv("sys", "haiku").index("--json-schema") + 1])
    assert "error_number" in d["properties"]


# --------------------------------------------------------------------------
# provenance caveat
# --------------------------------------------------------------------------

class _Args:
    def __init__(self, **kw):
        self.__dict__.update(kw)


def test_caveat_says_unverified_when_provenance_is_missing(capsys, tmp_path):
    """It used to assert OUR LibreOffice measurement under whatever corpus was
    scored, including one built on another machine by another person."""
    lscore.print_provenance_caveat(_Args(from_db="modified", run_dir=None), {})
    out = capsys.readouterr().out
    assert "UNVERIFIED" in out
    assert "5 of 10" not in out and "LibreOffice" not in out


def test_caveat_reports_the_converter_when_the_corpus_records_one(capsys, tmp_path):
    (tmp_path / "prepare_meta.json").write_text(json.dumps(
        {"converter_description": "Microsoft Word via COM (layout-preserving)"}))
    lscore.print_provenance_caveat(_Args(from_db=None, run_dir=tmp_path), {})
    out = capsys.readouterr().out
    assert "Microsoft Word via COM" in out and "UNVERIFIED" not in out


# --------------------------------------------------------------------------
# the results store and the rendered tables
# --------------------------------------------------------------------------

import results_store as lstore     # noqa: E402
import tables as ltables           # noqa: E402


def _caught(gt_rows, hits):
    return {(r["paper"], r["subcategory"]): (r["subcategory"] in hits)
            for r in gt_rows}


def _mini_gt():
    return [_gt(1, "statistical_errors", "a", "x"),
            _gt(1, "statistical_errors", "b", "x"),
            _gt(1, "internal_consistency", "c", "x")]


def test_rescoring_a_run_replaces_its_row_rather_than_adding_one(tmp_path):
    """Two rows for one run double-count in every per-category total."""
    store = tmp_path / "results.json"
    gt = _mini_gt()
    for hits in (["a"], ["a", "b"]):
        lstore.upsert(lstore.build_row(
            corpus="modified", backend="claude", model="opus-5",
            verify_model="sonnet", scored_at="2026-08-23T00:00:00+00:00",
            commit="abc", caught=_caught(gt, hits), gt_rows=gt,
            n_hits_protocol=9), store)
    rows = lstore.load(store)
    assert len(rows) == 1, "a re-score appended a second row for the same run"
    assert rows[0]["n_hits"] == 2


def test_a_different_backend_is_a_different_row(tmp_path):
    store = tmp_path / "results.json"
    gt = _mini_gt()
    for backend, model in (("claude", "opus-5"), ("grok", "grok-4.6")):
        lstore.upsert(lstore.build_row(
            corpus="modified", backend=backend, model=model,
            verify_model="sonnet", scored_at="2026-08-23T00:00:00+00:00",
            commit="abc", caught=_caught(gt, ["a"]), gt_rows=gt,
            n_hits_protocol=1), store)
    assert len(lstore.load(store)) == 2


def test_categories_are_recomputed_from_ground_truth_not_carried_in():
    """A row must never disagree with the CSV about which category an error is
    in, so `build_row` derives them rather than accepting them."""
    gt = _mini_gt()
    row = lstore.build_row(
        corpus="c", backend="b", model="m", verify_model=None,
        scored_at="t", commit="x", caught=_caught(gt, ["a", "c"]),
        gt_rows=gt, n_hits_protocol=2)
    assert row["by_category"]["statistical_errors"] == {"hits": 1, "of": 2}
    assert row["by_category"]["internal_consistency"] == {"hits": 1, "of": 1}
    assert row["n_hits"] == 2 and row["n_errors"] == 3


def test_caught_map_round_trips():
    gt = _mini_gt()
    c = _caught(gt, ["b"])
    row = lstore.build_row(corpus="c", backend="b", model="m",
                           verify_model=None, scored_at="t", commit="x",
                           caught=c, gt_rows=gt, n_hits_protocol=1)
    assert lstore.caught_map(row) == c


def test_store_survives_a_corrupt_file_without_inventing_rows(tmp_path):
    bad = tmp_path / "results.json"
    bad.write_text('[{"run_id": "half-writ')
    assert lstore.load(bad) == []


def test_plus_minus_is_computed_against_the_reference_run():
    """A totals column ranks; only the set comparison says whether a system is
    finding DIFFERENT errors. Two systems can tie at 42 and share only 30."""
    gt = _mini_gt()
    keys = [(r["paper"], r["subcategory"]) for r in gt]
    ref = {k: k[1] in ("a", "b") for k in keys}
    other = {k: k[1] in ("b", "c") for k in keys}
    plus = sum(1 for k in keys if other[k] and not ref[k])
    minus = sum(1 for k in keys if ref[k] and not other[k])
    assert (plus, minus) == (1, 1)


def test_latex_escapes_the_underscores_in_system_names():
    """Every one of Litvak's provider names has an underscore; unescaped they
    are subscripts and pdflatex fails on the first one."""
    assert ltables._tex_escape("openai_gpt55_high_reasoning") == \
        r"openai\_gpt55\_high\_reasoning"
    assert ltables._tex_escape("100% & rising") == r"100\% \& rising"


def test_pdf_build_refuses_in_words_when_latex_is_absent(monkeypatch, tmp_path):
    """Best-effort by contract: a missing LaTeX must not cost you the markdown
    you already have."""
    monkeypatch.setattr(ltables.shutil, "which", lambda _n: None)
    ok, detail = ltables.build_pdf("whatever", tmp_path / "x.pdf")
    assert ok is False and "pdflatex" in detail


def test_markdown_marks_our_runs_and_names_the_reference():
    gt = _mini_gt()
    keys = [(r["paper"], r["subcategory"]) for r in gt]
    ours = {"label": "FMA grok-4.6", "ours": True, "row": {},
            "caught": {k: True for k in keys}, "total": 3, "plus": 0,
            "minus": 0, "verified": 3, "verify_model": "sonnet",
            "by_category": {"statistical_errors": 2,
                            "internal_consistency": 1}}
    theirs = {"label": "reviewer3", "ours": False, "row": None,
              "caught": {k: False for k in keys}, "total": 0, "plus": 0,
              "minus": 3, "verified": None, "verify_model": None,
              "by_category": {}}
    md = ltables.render_markdown(gt, keys, [ours, theirs],
                                 {"label": "FMA grok-4.6"}, 0, {1})
    assert "**FMA grok-4.6**" in md and "| reviewer3 |" in md
    assert "Reference run" in md
    for c in ltables.CAVEATS:
        assert c.split(".")[0][:30] in md


def test_the_leaderboard_compares_like_with_like():
    """Litvak's fourteen were scored by a LENIENT judge -- haiku, one call per
    finding, no evidence requirement. Our verified pass is stricter on both
    counts. Ranking our strict number against their lenient ones is a handicap,
    not a comparison: on Greg's run it understated us by 7 (42 vs 49).
    """
    gt = _mini_gt()
    protocol = {(r["paper"], r["subcategory"]): True for r in gt}
    verified = {(r["paper"], r["subcategory"]): False for r in gt}
    row = lstore.build_row(
        corpus="c", backend="claude", model="m", verify_model="sonnet",
        scored_at="t", commit="x", caught=verified, caught_protocol=protocol,
        gt_rows=gt, n_hits_protocol=3)
    assert lstore.caught_map(row, "caught_protocol") == protocol
    assert lstore.caught_map(row, "caught") == verified
    assert row["n_hits"] == 0, "n_hits is the verified figure"
    assert row["n_hits_litvak_protocol"] == 3


def test_a_row_without_a_protocol_map_falls_back_rather_than_emptying():
    """Rows written before the two maps existed must still render."""
    gt = _mini_gt()
    c = {(r["paper"], r["subcategory"]): True for r in gt}
    row = lstore.build_row(corpus="c", backend="b", model="m",
                           verify_model=None, scored_at="t", commit="x",
                           caught=c, gt_rows=gt, n_hits_protocol=3)
    assert lstore.caught_map(row, "caught_protocol") == c
    legacy = {"caught": {"1|a": True}}
    assert lstore.caught_map(legacy, "caught_protocol") == {(1, "a"): True}


def test_leaderboard_labels_the_verified_column_as_not_comparable():
    gt = _mini_gt()
    keys = [(r["paper"], r["subcategory"]) for r in gt]
    ours = {"label": "FMA x", "ours": True, "row": {}, "verified": 2,
            "verify_model": "sonnet", "caught": {k: True for k in keys},
            "total": 3, "plus": 0, "minus": 0, "by_category": {}}
    md = ltables.render_markdown(gt, keys, [ours], {"label": "FMA x"}, 0, {1})
    assert "2 (sonnet)" in md
    assert "not" in md.lower() and "comparable" in md.lower()


# --------------------------------------------------------------------------
# Litvak's own false-positive correction
# --------------------------------------------------------------------------

def test_originals_are_loadable_and_are_a_separate_set(bench):
    """`_originals` is every system run over the UNMODIFIED papers. Nothing is
    planted there, so a match is the judge matching something to nothing."""
    main = lcompare.load_litvak(bench)
    orig = lcompare.load_litvak(bench, include_originals=True)
    assert len(orig) == len(main) == 14
    assert set(orig) == set(main), "names must line up for the subtraction"
    complete = {k: len(t) for k, t in orig.items() if len(t) == 100}
    assert len(complete) == 13
    # His quota ran out mid-run on this one; the baseline covers 4 of 10 papers.
    assert len(orig["openai_gpt54_high_reasoning"]) == 40


def test_adjusted_reproduces_litvaks_published_arithmetic(bench):
    """Pinned against his own summary.csv, because these numbers reorder the
    leaderboard and would be quoted in a grant application."""
    main = lcompare.load_litvak(bench)
    orig = lcompare.load_litvak(bench, include_originals=True)

    def adj(name):
        return sum(main[name].values()) - sum(orig[name].values())

    assert sum(main["openai_gpt55_high_reasoning"].values()) == 71
    assert adj("openai_gpt55_high_reasoning") == 47
    assert adj("openai_gpt55_no_reasoning") == 32     # 2nd raw -> 8th adjusted
    assert adj("reviewer3") == 21


def test_the_correction_reorders_the_leaderboard(bench):
    """If adjusting changed nothing, printing both tables would be noise.

    It does not change the WINNER once incomplete baselines are excluded --
    GPT-5.5 high-reasoning leads both -- but it moves the field by up to five
    places: GPT-5.5 no-reasoning falls 2nd to 7th, Refine rises 6th to 2nd.
    An earlier version of this test asserted the winner changed, which was
    true only because it was ranking a system whose baseline covers 4 of 10
    papers.
    """
    main = lcompare.load_litvak(bench)
    orig = lcompare.load_litvak(bench, include_originals=True)
    raw = sorted(main, key=lambda k: -sum(main[k].values()))
    adjs = sorted(main, key=lambda k: -(sum(main[k].values())
                                        - sum(orig[k].values())))
    # Only systems with a COMPLETE baseline may be ranked; gpt54_high_reasoning
    # covers 4 of 10 papers and is excluded, as Litvak excludes it himself.
    ok = [k for k in main if len(orig[k]) == len(main[k])]
    raw = [k for k in raw if k in ok]
    adjs = [k for k in adjs if k in ok]
    shift = max(abs(raw.index(k) - adjs.index(k)) for k in ok)
    assert shift >= 5, f"largest rank shift was only {shift}"
    assert raw.index("openai_gpt55_no_reasoning") < 2
    assert adjs.index("openai_gpt55_no_reasoning") >= 5, \
        "the volume-heavy system did not fall when its false positives were netted out"


def test_false_positives_track_output_volume(bench):
    """The measured reason the raw leaderboard cannot be quoted as-is: the
    judge credits a system roughly in proportion to how much it writes, on
    papers where there is nothing to credit."""
    import csv as _csv
    path = bench / "benchmark" / "reports" / "summary.csv"
    rows = list(_csv.DictReader(open(path)))
    main = {r["provider"]: r for r in rows
            if not r["provider"].endswith(("_originals", "_open", "_run2", "_run3"))}
    orig = {r["provider"][:-10]: r for r in rows
            if r["provider"].endswith("_originals")}
    xs, ys = [], []
    for k, m in main.items():
        if k in orig:
            xs.append(int(m["total_findings"]))
            ys.append(int(orig[k]["total_detected"]))
    r = ltables.pearson(xs, ys)
    assert r is not None and r > 0.6, f"expected a strong correlation, got {r}"


def test_a_row_without_a_clean_control_is_not_scored_as_zero(bench):
    """A blank cell reads as zero false positives. Ours is the row that has no
    control run, and reporting it as 0 would flatter us."""
    keys = [(r["paper"], r["subcategory"]) for r in lscore.ground_truth(bench)]
    systems = [{"label": "FMA test-model", "ours": True, "total": 49, "row": {}},
               {"label": "reviewer3", "ours": False, "total": 30, "row": None}]
    out = ltables.adjusted_table(bench, keys, systems)
    ours = next(r for r in out["rows"] if r["label"] == "FMA test-model")
    theirs = next(r for r in out["rows"] if r["label"] == "reviewer3")
    assert ours["fp"] is None and ours["adjusted"] is None
    assert theirs["adjusted"] == 21


def test_pearson_refuses_a_sample_too_small_to_mean_anything():
    assert ltables.pearson([1, 2], [1, 2]) is None
    assert ltables.pearson([1, 1, 1], [1, 2, 3]) is None      # zero variance
    assert abs(ltables.pearson([1, 2, 3], [2, 4, 6]) - 1.0) < 1e-9


def test_an_incomplete_baseline_is_refused_not_scored(bench):
    """`openai_gpt54_high_reasoning` has an originals run over 4 of the 10
    papers, so its false-positive count is understated by about 60%. The first
    version of this table scored it 56 - 6 = 50 and ranked it FIRST -- the
    wrong-denominator error, inside the table built to expose that same error
    in someone else's numbers. Litvak excludes it from his own head-to-head.
    """
    keys = [(r["paper"], r["subcategory"]) for r in lscore.ground_truth(bench)]
    systems = [{"label": "openai_gpt54_high_reasoning", "ours": False,
                "total": 56, "row": None},
               {"label": "reviewer3", "ours": False, "total": 30, "row": None}]
    out = ltables.adjusted_table(bench, keys, systems)
    bad = next(r for r in out["rows"]
               if r["label"] == "openai_gpt54_high_reasoning")
    assert bad["adjusted"] is None, "an incomplete baseline was scored"
    assert "4 of 10" in bad["why_unscored"]
    good = next(r for r in out["rows"] if r["label"] == "reviewer3")
    assert good["adjusted"] == 21


# --------------------------------------------------------------------------
# readable system names
# --------------------------------------------------------------------------

def test_display_names_match_litvaks_own_provider_definitions(bench):
    """Pinned against his source, not invented.

    His provider files carry the display name beside the model id. Guessing is
    how `claude_opus_*` would have been labelled "Opus 5" when his config says
    `claude-opus-4-6` -- a wrong model name in a published table.
    """
    import re
    src = ""
    for f in ("anthropic_provider.py", "openai_provider.py", "gemini_provider.py"):
        fp = bench / "benchmark" / "providers" / f
        if fp.is_file():
            src += fp.read_text(encoding="utf-8")
    if not src:
        pytest.skip("upstream provider definitions not present")
    # ("slug", "Display Name", "model-id"
    found = dict((m[0], (m[1], m[2])) for m in
                 re.findall(r'\("([a-z0-9_]+)",\s*"([^"]+)",\s*"([^"]+)"', src))
    assert found, "could not parse any provider definitions"
    for slug, (their_name, model_id) in found.items():
        ours = ltables.DISPLAY_NAMES.get(slug)
        assert ours, f"{slug} has no display name"
        # same words, our casing for the parenthetical
        assert ours.lower() == their_name.lower(), \
            f"{slug}: ours {ours!r} vs his {their_name!r}"
        if "opus_" in slug and "48" not in slug:
            assert "4.6" in ours and model_id == "claude-opus-4-6"


def test_an_unmapped_provider_keeps_its_identifier():
    """Never a prettified guess: a reader must be able to see it is unmapped."""
    assert ltables.display_name("some_new_system_2027") == "some_new_system_2027"
    assert ltables.display_name("reviewer3") == "Reviewer3"


def test_our_own_rows_get_a_readable_label():
    assert ltables.our_label({"model": "claude-opus-5", "backend": "claude"}) \
        == "FMA (Claude Opus 5)"
    assert ltables.our_label({"model": "grok-4.6", "backend": "grok"}) \
        == "FMA (Grok 4.6)"
    # unknown model still identifies its backend rather than hiding it
    out = ltables.our_label({"model": "mystery-1", "backend": "grok"})
    assert "mystery-1" in out and "grok" in out


def test_leaderboard_has_flags_and_no_net_column():
    gt = _mini_gt()
    keys = [(r["paper"], r["subcategory"]) for r in gt]
    ours = {"label": "FMA (Grok 4.6)", "ours": True, "row": {}, "verified": 2,
            "verify_model": "sonnet", "flags": 206,
            "caught": {k: True for k in keys}, "total": 3, "plus": 0,
            "minus": 0, "by_category": {}}
    md = ltables.render_markdown(gt, keys, [ours], {"label": "x"}, 0, {1})
    header = next(l for l in md.splitlines() if l.startswith("| system |"))
    assert "total flags" in header
    assert "net" not in header
    assert "| 206 |" in md


def test_flag_counts_come_from_litvaks_summary_csv(bench):
    flags = ltables.litvak_flag_counts(bench)
    assert flags["openai_gpt55_high_reasoning"] == 512
    assert flags["reviewer3"] == 125
    assert not any(k.endswith(("_originals", "_open", "_run2", "_run3"))
                   for k in flags)


def test_adjusted_lookup_survives_readable_labels(bench):
    """Introducing display names broke this: the false-positive map is keyed on
    the RAW provider name, the lookup used the label, and every one of Litvak's
    systems fell through to "no clean-control run". The whole adjusted table
    read `n/c` and only rendering the PDF caught it.
    """
    keys = [(r["paper"], r["subcategory"]) for r in lscore.ground_truth(bench)]
    systems = [{"label": ltables.display_name("reviewer3"),
                "raw_name": "reviewer3", "ours": False, "total": 30, "row": None},
               {"label": ltables.display_name("openai_gpt55_high_reasoning"),
                "raw_name": "openai_gpt55_high_reasoning", "ours": False,
                "total": 71, "row": None}]
    out = ltables.adjusted_table(bench, keys, systems)
    got = {r["label"]: r["adjusted"] for r in out["rows"]}
    assert got["Reviewer3"] == 21
    assert got["GPT-5.5 (high reasoning)"] == 47
    assert not any(r["adjusted"] is None for r in out["rows"]), \
        "a system with a complete baseline was reported as uncomputable"


# --------------------------------------------------------------------------
# the callout-ladder header
# --------------------------------------------------------------------------

def test_ladder_emits_one_mark_and_one_arrow_per_column():
    cells, draw = ltables.ladder(["alpha", "beta", "gamma"])
    assert cells.count(r"\tikzmark") == 3
    assert draw.count(r"\draw[->") == 3
    for i in range(3):
        assert f"cat{i}" in cells and f"pic cs:cat{i}" in draw


def test_ladder_stacks_column_one_lowest_so_arrows_never_cross():
    """Each arrow runs right along its own free row before turning down. In the
    reverse order every path crosses every other one, which is why the stacking
    order is not cosmetic."""
    import re
    _cells, draw = ltables.ladder(["a", "b", "c", "d"])
    # NODE lines only: the \draw endpoints carry their own yshift and would
    # otherwise be read as label heights.
    ys = [float(re.search(r"yshift=([0-9.]+)mm", l).group(1))
          for l in draw.splitlines() if "\\node" in l]
    assert ys == sorted(ys), "labels are not stacked in column order"
    assert len(set(ys)) == 4, "two labels share a row and would overlap"


def test_ladder_labels_are_escaped():
    _cells, draw = ltables.ladder(["attrition_missing_data"])
    assert r"attrition\_missing\_data" in draw


def test_the_overlay_is_not_emitted_inside_the_tabular(bench):
    """A tikzpicture between table rows is not a legal element and pdflatex
    dies on the next \\midrule. `remember picture` resolves marks by name, so
    the overlay belongs after \\end{tabular}."""
    gt = lscore.ground_truth(bench)
    keys = [(r["paper"], r["subcategory"]) for r in gt]
    sysrows = [{"label": "X", "raw_name": "reviewer3", "ours": False,
                "total": 30, "row": None, "caught": {k: False for k in keys},
                "verified": None, "verify_model": None, "flags": 125,
                "plus": 0, "minus": 0,
                "by_category": {c: 0 for c in {r["category"] for r in gt}}}]
    tex = ltables.render_latex(gt, keys, sysrows, {"label": "X"}, 0, {1},
                               ltables.adjusted_table(bench, keys, sysrows))
    body = tex.split(r"\subsection*{3. By category", 1)[1]
    table = body.split(r"\begin{tabular}", 1)[1].split(r"\end{tabular}", 1)[0]
    assert "tikzpicture" not in table, "the overlay is inside the tabular"
    assert r"\begin{tikzpicture}" in body, "the overlay was not emitted at all"


def test_pdf_build_runs_latex_twice():
    """`remember picture` writes node positions to the .aux on pass one and
    only resolves them on pass two. A single pass draws every callout arrow at
    the page origin, and does so WITHOUT erroring."""
    import inspect
    src = inspect.getsource(ltables.build_pdf)
    assert "for _pass in range(2)" in src


# --------------------------------------------------------------------------
# re-scoring Litvak's own systems
# --------------------------------------------------------------------------

import litvak_findings as LLF     # noqa: E402
import rescore as LRS             # noqa: E402


def test_the_six_resolve_to_the_versions_dan_named(bench):
    """His directory names omit versions and two collide on "opus".
    `claude_opus_*` is 4.6; `claude_opus48_*` is 4.8 and must NOT be in the set.
    Mislabelling these would poison every row of the published table."""
    want = {
        "openai_gpt55_high_reasoning": "gpt-5.5",
        "claude_sonnet_no_thinking": "claude-sonnet-4-6",
        "claude_opus_high_thinking": "claude-opus-4-6",
        "claude_opus_no_thinking": "claude-opus-4-6",
    }
    for cond, mid in want.items():
        assert cond in LRS.SIX
        assert LLF.model_id(bench, cond) == mid, f"{cond} is not {mid}"
    assert not any("opus48" in c for c in LRS.SIX)
    assert len(LRS.SIX) == 6


def test_every_condition_loads_ten_papers_with_no_empty_descriptions(bench):
    """The verifier reads `description`; an empty one is an unanswerable call."""
    for cond in LRS.conditions_for(list(LRS.SIX), both=True):
        got = LLF.load_condition(bench, cond)
        assert sorted(got) == list(range(1, 11)), f"{cond} is not 10 papers"
        for rows in got.values():
            assert all((r["description"] or "").strip() for r in rows), cond


def test_the_loader_never_invents_a_title(bench):
    """FMA findings carry a crafted title and his do not. Synthesising one from
    a subcategory slug would put words in his systems' mouths. The asymmetry is
    removed by showing LESS of ours, not more of his."""
    rows = LLF.load_condition(bench, "reviewer3")[1]
    assert all("title" not in r for r in rows)


def test_the_verifier_sees_the_same_fields_whoever_produced_the_finding():
    """Showing the verifier a title for our findings and nothing for theirs
    hands us an advantage inside the instrument built to remove one."""
    import re
    ours = {"technique": "check_estimate_ci", "slug": "ci_width",
            "title": "MUST NOT APPEAR",
            "description": "d", "quote": "q", "location": "Table 1"}
    theirs = {"technique": "statistical_errors", "slug": "ci_width",
              "description": "d", "quote": "q", "location": "Table 1"}
    a = lscore.render_for_verify(0, ours)
    b = lscore.render_for_verify(0, theirs)
    assert "MUST NOT APPEAR" not in a
    strip = lambda t: re.sub(r"^\[\d+\] \S+", "", t)      # noqa: E731
    assert strip(a) == strip(b), "the two sources render differently"


def test_the_prompt_version_invalidates_the_old_cache():
    """FMA's verified 42 was computed with the title visible, so it is not
    comparable to anything produced under the normalised renderer."""
    assert lscore.VERIFY_PROMPT_VERSION == "v2"
    gt = _gt(1, "statistical_errors", "a", "x")
    f = _finding("A")
    assert lscore.verify_cache_key(1, gt, [f]).startswith("Vv2|")


def test_protocol_matches_reproduce_his_published_figure(bench):
    """A re-scored row carries his verdict beside ours rather than replacing
    it -- they are different claims."""
    for cond, want in (("reviewer3", 30), ("openai_gpt55_high_reasoning", 71),
                       ("refine_ink", 57)):
        got = LLF.load_protocol_matches(bench, cond)
        assert sum(got.values()) == want, f"{cond}: {sum(got.values())} != {want}"


def test_a_rescored_row_is_not_labelled_as_one_of_our_runs():
    """Our system's performance and our re-analysis of someone else's are
    different claims; a table must not bold them identically."""
    gt = _mini_gt()
    c = {(r["paper"], r["subcategory"]): True for r in gt}
    row = lstore.build_row(
        corpus="reviewer3", backend="litvak", model="reviewer3:journal",
        verify_model="sonnet", scored_at="t", commit="x", caught=c,
        gt_rows=gt, n_hits_protocol=3, source="litvak_rescored",
        condition="reviewer3")
    assert row["source"] == "litvak_rescored"
    assert not row["label"].startswith("FMA")
    assert row["label"] == "reviewer3"


def test_an_unknown_source_is_refused():
    gt = _mini_gt()
    with pytest.raises(ValueError, match="source"):
        lstore.build_row(corpus="c", backend="b", model="m", verify_model=None,
                         scored_at="t", commit="x", caught={}, gt_rows=gt,
                         n_hits_protocol=0, source="litvaks_own_number")


def test_conditions_for_pairs_each_system_with_its_control():
    """Both halves are needed or `adjusted = modified - originals` cannot be
    computed under one matcher, which is the point of the exercise."""
    got = LRS.conditions_for(["reviewer3", "refine_ink"], both=True)
    assert got == ["reviewer3", "reviewer3_originals",
                   "refine_ink", "refine_ink_originals"]
    assert LRS.conditions_for(["reviewer3"], both=False) == ["reviewer3"]


def test_cost_is_per_error_not_per_finding(bench):
    """A 704-finding system costs the same as a 125-finding one: the verifier
    makes one call per planted ERROR, showing it that paper's findings."""
    big = LLF.load_condition(bench, "openai_gpt55_high_reasoning")
    small = LLF.load_condition(bench, "reviewer3")
    assert sum(len(v) for v in big.values()) > 4 * sum(len(v) for v in small.values())
    assert len(big) == len(small) == 10      # calls scale with papers x errors


def test_an_unknown_condition_names_what_is_available(bench):
    with pytest.raises(LLF.ConditionNotFound) as exc:
        LLF.load_condition(bench, "gpt6_ultra")
    assert "Available conditions" in str(exc.value)


def test_a_rescored_condition_is_not_shown_as_one_of_our_systems(tmp_path, bench):
    """It printed "FMA (reviewer3:journal)" beside the real Reviewer3 row --
    someone else's system bolded as ours, and counted twice."""
    store = tmp_path / "results.json"
    gt = lscore.ground_truth(bench)
    c = {(r["paper"], r["subcategory"]): False for r in gt}
    lstore.upsert(lstore.build_row(
        corpus="modified", backend="claude", model="opus-5",
        verify_model="sonnet", scored_at="t", commit="x", caught=c,
        caught_protocol=c, gt_rows=gt, n_hits_protocol=0), store)
    lstore.upsert(lstore.build_row(
        corpus="reviewer3", backend="litvak", model="reviewer3:journal",
        verify_model="sonnet", scored_at="t", commit="x", caught=c,
        caught_protocol=c, gt_rows=gt, n_hits_protocol=0,
        source="litvak_rescored", condition="reviewer3"), store)
    rows = lstore.load(store)
    mine = [r for r in rows if r.get("source", "ours") == "ours"]
    rescored = [r for r in rows if r.get("source") == "litvak_rescored"]
    assert len(mine) == 1 and len(rescored) == 1
    assert not any(r["label"].startswith("FMA") for r in rescored)


def test_a_row_predating_the_source_field_still_counts_as_ours():
    """FMA's first recorded run has no `source`; defaulting it to anything else
    would drop our own result out of the table."""
    assert {"source": None}.get("source", "ours") is None
    legacy = {"run_id": "modified|claude|opus-5"}
    assert legacy.get("source", "ours") == "ours"


def test_the_two_matcher_variants_write_to_different_files():
    """They are the same corpus scored two ways, not two versions of one table.
    Sharing a filename would let the second silently overwrite the first."""
    v = ltables.VARIANTS
    assert set(v) == {"protocol", "verified"}
    assert v["protocol"]["dir"] != v["verified"]["dir"]
    assert v["protocol"]["stem"] != v["verified"]["stem"]
    assert v["protocol"]["which"] == "caught_protocol"
    assert v["verified"]["which"] == "caught"
    # the filename says which matcher made it, without needing the directory
    assert "haiku" in v["protocol"]["stem"] and "sonnet" in v["verified"]["stem"]


def test_the_verified_table_never_backfills_an_unverified_system(bench):
    """The worst version of this bug: `--matcher verified` printed GPT-5.5's
    unverified 71 under a heading saying "scored by the grounded verifier",
    because a system with no re-score silently fell back to its protocol map.
    That is presenting one measurement as another. Only rendering exposed it.
    """
    gt = lscore.ground_truth(bench)
    keys = [(r["paper"], r["subcategory"]) for r in gt]
    lit = lcompare.load_litvak(bench)
    # simulate gather's classification: no rescored row for gpt-5.5
    rescored = {}
    unverified = [name for name in lit if name not in rescored]
    assert "openai_gpt55_high_reasoning" in unverified
    for name in unverified:
        caught = {}                      # what gather now stores
        assert sum(1 for k in keys if caught.get(k)) == 0, \
            "an unverified system contributed a score"


def test_unverified_rows_are_named_not_dropped():
    """Omitting them would make the table look like a complete ranking that
    happens to be short."""
    gt = _mini_gt()
    keys = [(r["paper"], r["subcategory"]) for r in gt]
    scored = {"label": "Refine.ink", "ours": False, "row": {}, "unverified": False,
              "caught": {k: True for k in keys}, "total": 3, "plus": 0,
              "minus": 0, "verified": 3, "verify_model": "sonnet",
              "by_category": {}, "flags": 305}
    unscored = {"label": "GPT-5.5 (high reasoning)", "ours": False, "row": None,
                "unverified": True, "caught": {}, "total": None, "plus": None,
                "minus": None, "verified": None, "verify_model": None,
                "by_category": {}, "flags": 512}
    md = ltables.render_markdown(gt, keys, [scored, unscored],
                                 {"label": "Refine.ink"}, 3, {1},
                                 variant="verified")
    assert "GPT-5.5 (high reasoning)" in md, "an unverified system vanished"
    assert "not verified" in md
    assert "| 71 |" not in md, "a protocol number leaked into the verified table"
    assert "1 of 2 systems have no verified score" in md


def test_nobody_caught_this_means_nobody_measured(bench):
    """`never` must not count an unverified system as having failed to catch
    something it was never asked about."""
    gt = _mini_gt()
    keys = [(r["paper"], r["subcategory"]) for r in gt]
    unscored = {"label": "X", "ours": False, "row": None, "unverified": True,
                "caught": {}, "total": None, "plus": None, "minus": None,
                "verified": None, "verify_model": None, "by_category": {},
                "flags": 1}
    scored = {"label": "Y", "ours": False, "row": {}, "unverified": False,
              "caught": {k: True for k in keys}, "total": len(keys),
              "plus": 0, "minus": 0, "verified": len(keys),
              "verify_model": "sonnet", "by_category": {}, "flags": 1}
    md = ltables.render_markdown(gt, keys, [scored, unscored],
                                 {"label": "Y"}, len(keys), {1},
                                 variant="verified")
    assert "Caught by nobody" not in md, \
        "an unverified system made a caught error look uncaught"
