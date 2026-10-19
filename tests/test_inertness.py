"""The inertness scanner, and a positive control for every detector.

THE POINT OF THIS FILE. `inertness.py` hunts machinery that looks like it works
and does not. A detector that cannot fire is the same defect, one level up: it
reports zero exactly as convincingly as a clean codebase, and this repo has
already shipped that mistake -- an exclusion regex whose leading `\\b` became a
literal backspace matched nothing for a whole commit while reading correctly.

So every detector below gets BOTH halves:
  * a POSITIVE CONTROL that constructs the defect and asserts the detector sees
    it, and
  * a NEGATIVE CONTROL built from the named false-positive shape in that
    detector's docstring, asserting it stays quiet.

Delete either half and the detector's number stops meaning anything.
"""
import textwrap
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import inertness as I

REPO = Path(__file__).resolve().parents[1]


def _mod(tmp_path: Path, name: str, body: str) -> Path:
    p = tmp_path / f"{name}.py"
    p.write_text(textwrap.dedent(body), encoding="utf-8")
    return p


class TestDegenerateRegex:
    """The real instance: `eval/corpus_expansion.py`'s review exclusion, whose
    leading word boundary became 0x08 through a non-raw string. It matched
    nothing, looked right, and let reviews into a corpus of primary research."""

    def test_it_catches_the_backspace_accident(self, tmp_path):
        _mod(tmp_path, "bad", '''
            import re
            BAD = re.compile("\\breview\\b|\\bsurvey\\b", re.I)
        ''')
        got = I.find_degenerate_regexes(tmp_path)
        assert len(got) == 1, got
        assert got[0].confidence == "certain"
        assert got[0].extra["char"] == "\x08"
        assert "backspace" in got[0].what

    def test_the_same_pattern_written_raw_is_silent(self, tmp_path):
        """The negative control. If this fires, the detector flags correct code
        and will be switched off within a week."""
        _mod(tmp_path, "good", '''
            import re
            GOOD = re.compile(r"\\breview\\b|\\bsurvey\\b", re.I)
        ''')
        assert I.find_degenerate_regexes(tmp_path) == []

    def test_a_docstring_mentioning_the_character_is_not_a_finding(self, tmp_path):
        """Only strings in the PATTERN position of an `re.*` call are examined.
        Prose about the bug -- of which this repo now has a great deal -- must
        not become a finding about itself."""
        _mod(tmp_path, "prose", '''
            """A regex whose \\b became a backspace matches nothing."""
            X = "\\bnot a regex, just a string\\b"
        ''')
        assert I.find_degenerate_regexes(tmp_path) == []

    def test_the_live_source_tree_is_clean(self):
        """A gate: base rate zero today, so a failure means something new."""
        got = [f for f in I.find_degenerate_regexes(I.SRC)]
        assert not got, [f.where for f in got]


class TestEmptyAlternative:
    """detector: empty_regex_alternative -- an alternation with a blank branch
    matches the empty string everywhere, so as a guard it always passes and as
    a filter it excludes everything. Both are silent."""

    def test_a_trailing_pipe_is_caught(self, tmp_path):
        _mod(tmp_path, "e", '''
            import re
            R = re.compile(r"alpha|beta|")
        ''')
        got = I.find_unanchorable_alternatives(tmp_path)
        assert len(got) == 1 and got[0].confidence == "worklist"

    def test_an_ordinary_alternation_is_silent(self, tmp_path):
        _mod(tmp_path, "f", '''
            import re
            R = re.compile(r"alpha|beta")
        ''')
        assert I.find_unanchorable_alternatives(tmp_path) == []


class TestUnconsumedDefinition:
    """The real instance: `unbacked_accusations()`, whose docstring says "A run
    linter must fire on this list", called from nothing but its own tests, while
    17 of 21 archived runs sat beside a BREACH verdict and every one exited 0."""

    def test_a_function_nothing_calls_is_reported(self, tmp_path):
        _mod(tmp_path, "lonely", '''
            def never_called_anywhere():
                return 1
        ''')
        got = I.find_unconsumed_definitions(tmp_path, tests=tmp_path / "no_tests")
        assert [f.extra["kind"] for f in got] == ["function"]
        assert "never_called_anywhere" in got[0].what
        assert got[0].confidence == "worklist", (
            "this detector can never prove deadness -- string dispatch exists")

    def test_a_name_used_only_inside_its_own_module_is_NOT_reported(self, tmp_path):
        """THE BUG THIS TEST EXISTS FOR. Keyed on "referenced by no OTHER
        module", the first version returned 232 candidates, essentially all of
        them ordinary module-local constants -- `PARTIAL_COVERAGE_NOTE`, which
        `agent.py` uses twice a hundred lines below where it is defined. A name
        used where it was defined is scoped, not inert. Fixing the predicate
        took it from 232 to 32."""
        _mod(tmp_path, "scoped", '''
            NOTE = "used right here"

            def f():
                return NOTE
        ''')
        got = I.find_unconsumed_definitions(tmp_path, tests=tmp_path / "no_tests")
        assert [f.what for f in got if "NOTE" in f.what] == []

    def test_a_name_another_module_imports_is_not_reported(self, tmp_path):
        _mod(tmp_path, "a", "def shared_helper():\n    return 1\n")
        _mod(tmp_path, "b", "from a import shared_helper\n\nshared_helper()\n")
        got = I.find_unconsumed_definitions(tmp_path, tests=tmp_path / "no_tests")
        assert not [f for f in got if "shared_helper" in f.what]

    def test_a_decorated_function_is_not_reported(self, tmp_path):
        """typer commands and MCP tools are registered by decorator and called
        by nobody in Python. Reporting them would bury the real findings."""
        _mod(tmp_path, "cli", '''
            import typer
            app = typer.Typer()

            @app.command("thing")
            def thing_cmd():
                return 1
        ''')
        got = I.find_unconsumed_definitions(tmp_path, tests=tmp_path / "no_tests")
        assert not [f for f in got if "thing_cmd" in f.what]

    def test_it_says_whether_only_the_tests_use_it(self, tmp_path):
        """Tested-and-inert is the most convincing disguise there is, so the
        finding must distinguish it from never-mentioned-at-all."""
        # The tests directory must sit OUTSIDE the scanned root, as it does in
        # the real repo (`tests/` beside `src/`). Nested inside, the scanner
        # reads the test file as source and the name looks used.
        src = tmp_path / "src"; src.mkdir()
        (src / "half.py").write_text("def only_tested():\n    return 1\n")
        t = tmp_path / "t"; t.mkdir()
        (t / "test_x.py").write_text("from half import only_tested\n")
        got = I.find_unconsumed_definitions(src, tests=t)
        f = next(f for f in got if "only_tested" in f.what)
        assert f.extra["referenced_in_tests"] is True
        assert "only by tests" in f.what


class TestTheDetectorsOwnTwoBlindSpots:
    """FOUND BY AN ADVERSARIAL TRIAGE OF ITS OWN OUTPUT, 2026-08-11. Both fail
    in the direction that matters -- they made the linter QUIETER -- and both
    are exactly the shape of defect it exists to find, which is the reason this
    class is worth its length.

    Before: 33 findings, four of them false and three real ones missing.
    After: 39, with the four gone and the three (plus seven more) present."""

    def test_a_re_export_through_init_py_counts_as_a_caller(self, tmp_path):
        """BLIND SPOT 1. `_py_files` excluded `__init__.py` so the definition
        scanners would not trip over re-export blocks -- but the REFERENCE
        corpus was built from that same list, so a name whose only consumer was
        a re-export read as consumed by nobody. `find_unconsumed_definitions`'
        docstring claimed this shape was handled. It was not, and four of the
        33 (`TTestData`, `ANOVAData`, `ChiSquaredData`, `PercentageData`) were
        this and nothing else."""
        pkg = tmp_path / "pkg"; pkg.mkdir()
        (pkg / "schemas.py").write_text("class PublicModel:\n    pass\n")
        (pkg / "__init__.py").write_text(
            "from .schemas import PublicModel\n\n__all__ = ['PublicModel']\n")
        got = I.find_unconsumed_definitions(tmp_path, tests=tmp_path / "none")
        assert not [f for f in got if "PublicModel" in f.what], (
            "a name re-exported for external callers is not unconsumed")

    def test_a_name_only_its_own_comments_mention_is_still_reported(self, tmp_path):
        """BLIND SPOT 2, own-module half. `own_uses` was a raw token count over
        the whole file, so two mentions in the module's own PROSE satisfied the
        "used where it was defined" gate. This is worse than an ordinary miss:
        the prose is likeliest to exist exactly where somebody once noticed the
        wiring was absent and wrote down why."""
        _mod(tmp_path, "chatty", '''
            """This module owns recognition_hits.

            recognition_hits is the output half of the check and it matters.
            """
            # recognition_hits reads the model's own words back.

            def recognition_hits():
                return 1
        ''')
        got = I.find_unconsumed_definitions(tmp_path, tests=tmp_path / "none")
        assert [f.what for f in got if "recognition_hits" in f.what], (
            "three mentions in its own docstrings and comments hid it")

    def test_a_name_another_modules_comment_mentions_is_still_reported(self, tmp_path):
        """BLIND SPOT 2, cross-module half -- the worse one. A comment in module
        B naming a function in module A is not a call. `sigma_from_geometry` was
        suppressed by ONE line of `extraction/ocr.py`'s module docstring, and
        `recognition_hits` was suppressed by the docstring in `inertness.py`
        that explains why it was being missed. The linter silenced itself with
        its own explanation."""
        _mod(tmp_path, "a", "def sigma_from_geometry():\n    return 1\n")
        _mod(tmp_path, "b", '''
            """Sigma is computable from pixel geometry (`sigma_from_geometry`)."""
            X = 1
        ''')
        got = I.find_unconsumed_definitions(tmp_path, tests=tmp_path / "none")
        assert [f.what for f in got if "sigma_from_geometry" in f.what]

    def test_a_string_literal_still_counts_as_a_use(self, tmp_path):
        """THE LIMIT OF THE FIX, and it must not be crossed. Stripping prose
        must not strip string DISPATCH: the tool registry maps names to
        callables by string, so `BY_NAME["statcheck"]` is a real call. Only
        docstrings and comments are discounted."""
        _mod(tmp_path, "reg", '''
            def dispatched_by_string():
                return 1

            BY_NAME = {"dispatched_by_string": dispatched_by_string}
        ''')
        got = I.find_unconsumed_definitions(tmp_path, tests=tmp_path / "none")
        assert not [f for f in got if "dispatched_by_string" in f.what]

    def test_the_real_repo_still_reports_its_own_founding_example(self):
        """`unbacked_accusations` (agent.py) is the instance this whole detector
        was built from, and the comment-prose bug was hiding it. There are two
        implementations of the idea; the private one runs, the public one --
        whose docstring says "A run linter must fire on this list" -- does not."""
        got = I.find_unconsumed_definitions()
        names = {f.what.split("`")[1] for f in got}
        assert "unbacked_accusations" in names
    """The real instance: `paper_text` swallowed every extraction crash and
    returned "", so four of its five consumers published a clean result on a
    paper they had never opened."""

    def test_a_handler_that_records_nothing_is_reported(self, tmp_path):
        _mod(tmp_path, "silent", '''
            def read_it(p):
                try:
                    return open(p).read()
                except Exception:
                    return ""
        ''')
        got = I.find_swallowed_failures(tmp_path)
        assert len(got) == 1 and got[0].confidence == "certain"

    def test_a_handler_that_records_the_failure_is_silent(self, tmp_path):
        """The distinction is not how broad the `except` is -- this pipeline
        deliberately guards paid analyses -- but whether anything is left
        behind for a reader."""
        _mod(tmp_path, "loud", '''
            def read_it(p, problems):
                try:
                    return open(p).read()
                except Exception as exc:
                    problems.append(str(exc))
                    return ""
        ''')
        assert I.find_swallowed_failures(tmp_path) == []

    def test_an_availability_probe_is_silent(self, tmp_path):
        """The named false-positive shape: absence IS the answer, and it is
        recorded in a variable the caller inspects."""
        _mod(tmp_path, "probe", '''
            try:
                import lxml
                HAVE_LXML = True
            except ImportError:
                HAVE_LXML = False
        ''')
        assert I.find_swallowed_failures(tmp_path) == []

    def test_a_commented_guard_drops_to_worklist(self, tmp_path):
        """This repo's convention is a comment on a deliberate guard. That does
        not make the guard safe, but it does mean somebody decided -- so it is
        an invitation to look, not a claim of breakage."""
        _mod(tmp_path, "guarded", '''
            def f(p):
                try:
                    return open(p).read()
                # never lose a paid analysis to a bookkeeping error
                except Exception:
                    return ""
        ''')
        got = I.find_swallowed_failures(tmp_path)
        assert len(got) == 1 and got[0].confidence == "worklist"


class TestConstantOutcomeCheck:
    """The real instance: GRIM ran 159 times in the archive and 90 of those
    calls were in a regime where the check cannot fail -- every one returned
    `consistent` and was shown to a reader as a pass."""

    def _archive(self, tmp_path, rows):
        import json
        d = tmp_path / "run"
        d.mkdir()
        (d / "findings.v2.json").write_text(json.dumps({"findings": rows}))
        return tmp_path

    def test_a_tool_with_one_outcome_over_many_calls_is_reported(self, tmp_path):
        rows = [{"technique": "always_passes", "tool_verdict": {"severity": "consistent"}}] * 20
        got = I.find_constant_outcome_checks(self._archive(tmp_path, rows))
        assert len(got) == 1
        assert got[0].extra["n_calls"] == 20
        assert got[0].confidence == "worklist", (
            "a clean corpus produces this too -- it is a question, not a verdict")

    def test_a_tool_that_has_ever_returned_something_else_is_silent(self, tmp_path):
        rows = ([{"technique": "t", "tool_verdict": {"severity": "consistent"}}] * 19
                + [{"technique": "t", "tool_verdict": {"severity": "suspicious"}}])
        assert I.find_constant_outcome_checks(self._archive(tmp_path, rows)) == []

    def test_a_tool_with_too_few_calls_is_not_reported(self, tmp_path):
        """Three identical results are not evidence of anything, and reporting
        them is how a linter earns its reputation for noise."""
        rows = [{"technique": "rare", "tool_verdict": {"severity": "consistent"}}] * 3
        assert I.find_constant_outcome_checks(self._archive(tmp_path, rows)) == []


class TestPromptRules:
    """The real instance: `stage2_editorial.md` had told the model for months
    that a hand-worked finding may not reach `impossible`. Nothing enforced it,
    and over 23 runs it leaked twice -- both at the top of the ladder, the only
    place the rule matters."""

    def test_it_extracts_hard_rules_and_flags_the_unanchored_ones(self, tmp_path):
        (tmp_path / "p.md").write_text(
            "A finding you worked out by hand MUST NOT reach `impossible`.\n"
            "Some ordinary prose that states no rule at all goes here.\n"
            "Every reading NEVER omits its `warrant` field, no exceptions ever.\n")
        got = I.find_unenforced_prompt_rules(tmp_path)
        assert len(got) == 2, [f.what for f in got]
        assert all(f.confidence == "worklist" for f in got), (
            "whether a rule is enforced is a judgement, not a property of text")

    def test_it_reports_whether_the_rule_names_anything_in_the_code(self, tmp_path):
        (tmp_path / "p.md").write_text(
            "A finding MUST NOT reach `zzz_nothing_named_this` in any run.\n")
        got = I.find_unenforced_prompt_rules(tmp_path)
        assert got[0].extra["names_code"] is False
        assert "NONE" in got[0].evidence

    def test_the_live_prompts_produce_a_worklist_not_an_empty_set(self):
        """If this ever returns nothing, the extractor has broken -- the prompts
        are full of hard rules and that is the point of them."""
        got = I.find_unenforced_prompt_rules()
        assert len(got) > 10


class TestTheScanReportsWhatDidNotFire:
    def test_every_detector_is_counted_even_at_zero(self):
        """A detector that reported nothing and a detector that never ran are
        indistinguishable in a bare list of findings -- this module's own bug
        class, turned on itself."""
        r = I.scan(only=["degenerate_regex"])
        assert r["by_detector"] == {"degenerate_regex": 0} or \
               list(r["by_detector"]) == ["degenerate_regex"]
        assert "degenerate_regex" in r["by_detector"]

    def test_every_detector_has_a_positive_control_in_this_file(self):
        """The load-bearing meta-test. A detector added without a control is a
        number nobody can trust, and the whole module is about numbers nobody
        can trust."""
        here = Path(__file__).read_text(encoding="utf-8")
        for name in I.DETECTORS:
            assert name in here, (
                f"detector `{name}` has no test in this file. Add a positive "
                "control that constructs the defect, and a negative control "
                "from its docstring's named false-positive shape.")

    def test_every_detector_docstring_names_its_false_positive(self):
        for name, fn in I.DETECTORS.items():
            doc = (fn.__doc__ or "").upper()
            assert "FALSE POSITIVE" in doc or "NOT AN ACCUSATION" in doc \
                or "CANNOT DECIDE" in doc, name


class TestBroadVersusNarrowCatches:
    """A ROUND OF FALSE POSITIVES, kept as tests. Keyed on "discards and
    records nothing" alone, `swallowed_failure` returned 47 `certain` findings
    and every one I checked was a typed parse guard -- `except (TypeError,
    ValueError): return None` around a `float()`. Nothing is hidden there: the
    exception type IS the answer. The bug that motivated the detector,
    `paper_text`, was `except Exception`, which also swallows a MemoryError, a
    decoder crash and a bug in our own code, and calls all of them an empty
    paper."""

    def test_a_typed_parse_guard_is_not_a_swallow(self, tmp_path):
        _mod(tmp_path, "parse", '''
            def as_float(s):
                try:
                    return float(s)
                except (TypeError, ValueError):
                    return None
        ''')
        assert I.find_swallowed_failures(tmp_path) == []

    def test_a_bare_except_is_broad(self, tmp_path):
        _mod(tmp_path, "bare", '''
            def f(p):
                try:
                    return open(p).read()
                except:
                    return ""
        ''')
        assert len(I.find_swallowed_failures(tmp_path)) == 1

    def test_a_tuple_containing_Exception_is_broad(self, tmp_path):
        _mod(tmp_path, "mixed", '''
            def f(p):
                try:
                    return open(p).read()
                except (KeyError, Exception):
                    return ""
        ''')
        assert len(I.find_swallowed_failures(tmp_path)) == 1


class TestTheRatchets:
    """MEASURED counts, pinned so an improvement is permanent and a regression
    is loud. Deliberately NOT written as "must be zero": the corpus-invariants
    module's own caveat applies here first -- converting a noisy audit into a
    build failure wholesale breaks every build forever, and a red suite everyone
    learns to ignore enforces nothing, which is this file's own bug class."""

    #: MEASURED 2026-08-11 at commit-time. `certain` findings are proven
    #: properties of the code: broad `except` handlers that leave no trace.
    #: Lower this as they are fixed. RAISE IT ONLY WITH THE NEW INSTANCE NAMED
    #: HERE -- a pin that moves silently measures nothing.
    #:
    #: 27 -> 28 on merging Dan's 2a87e94 (progress callback). The new instance
    #: is `agent.py`'s handler around the `on_progress` call, and it is
    #: DELIBERATE with the reason written at the site: "a broken display must
    #: not cost a run". Same posture as the annotator chain, and correct -- a
    #: formatting bug in a status line must never destroy a paid stage.
    #:
    #: NOT FIXED BY TEACHING THE DETECTOR TO READ THE JUSTIFICATION. A handler
    #: excused by the comment beside it is precisely the prose-suppression bug
    #: found in this linter the same day (see `_code_uses`), where a name's own
    #: explanation of why it was unwired silenced the check that would have
    #: reported it. The count stays honest and the exception stays visible.
    #: RE-PINNED 2026-08-21 at the stacked-headers merge: 28 -> 45, READ
    #: before raising. Every one is a `swallowed_failure`, and the delta is
    #: two campaigns' deliberate best-effort contracts landing at once --
    #: bundle rendering, anchors' never-fail-the-run catches, provenance
    #: probes. Lower this as they gain logging; raising it to green a red
    #: suite without reading defeats the detector.
    #: 45 -> 47 (2026-08-21, merge follow-through): the value-register and
    #: harness-prepass hooks in parallel.py, both under the never-fail-a-
    #: paid-run contract their neighbors already carry.
    #: 47 -> 48 (2026-08-21, stats drift-check fixes): db_push's
    #: metadata.json fill-only fallback -- an unreadable metadata file
    #: legitimately leaves the doc's own projection in place.
    #: 48 -> 47 (2026-09-02, audit): `_render_report_pdf` no longer discards
    #: the render failure -- `_record_pdf_error` writes the reason into
    #: run_meta -- so one proven-inert site is gone. Lowered to match.
    #: 47 -> 48 (2026-09-14): `image_forensics/gate.py:_git_state` is the
    #: provenance probe that already exists on `version.git_state` -- a
    #: subprocess failure must not fail the detector gate, and the empty
    #: dict is the named unknown. Read, then re-pinned.
    MAX_CERTAIN = 48

    @pytest.fixture(scope="class")
    def scan(self):
        """ONE SCAN FOR THE CLASS, and the reason is measurable. `I.scan()`
        AST-parses every module in `src/`; three tests calling it separately
        cost 105 of the suite's 516 seconds -- 20% of the whole run, spent
        three times on an identical answer. Dan asked whether 4,412 tests were
        excessive (2026-08-11); the count was not the problem, this was."""
        return I.scan()

    def test_the_proven_findings_have_not_multiplied(self, scan):
        r = scan
        n = r["by_confidence"].get("certain", 0)
        assert n <= self.MAX_CERTAIN, (
            f"{n} proven-inert findings, above the pinned {self.MAX_CERTAIN}. "
            "Run `metascience lint-inert --certain-only` and read the new ones.")

    def test_the_worklist_is_reported_but_not_gated(self, scan):
        """The worklist is large by design -- 83 of it is every hard rule the
        prompts state, which is a reading list, not a defect list. Gating on it
        would be the mistake this class exists to avoid."""
        r = scan
        assert r["by_confidence"].get("worklist", 0) > 0
        assert r["by_detector"]["prompt_rule"] > 10

    def test_the_scan_covers_every_detector(self, scan):
        """A scan that quietly stopped running a detector would report fewer
        findings and look like progress."""
        r = scan
        assert set(r["by_detector"]) == set(I.DETECTORS)


class TestTheReceiverMustBeRe:
    """A FALSE-POSITIVE ROUND, kept. `split`, `match` and `sub` are string
    methods as well as `re` functions, and `"a|b".split("|")` is not a regex.
    Three of the four `empty_regex_alternative` findings on the live tree were
    exactly that -- the detector was mostly reporting ordinary string splitting
    as a broken pattern."""

    def test_a_string_split_on_a_pipe_is_not_a_regex(self, tmp_path):
        _mod(tmp_path, "s", '''
            def f(row):
                return row.split("|")
        ''')
        assert I.find_unanchorable_alternatives(tmp_path) == []
        assert I.find_degenerate_regexes(tmp_path) == []

    def test_re_split_with_the_same_argument_still_is(self, tmp_path):
        _mod(tmp_path, "r", '''
            import re
            def f(row):
                return re.split(r"alpha|beta|", row)
        ''')
        assert len(I.find_unanchorable_alternatives(tmp_path)) == 1


class TestTheWriteOnlyKeyDetector:
    """A computed answer stored under a key nobody reads.

    `unconsumed_definition` finds an unused NAME. This finds an unused ANSWER,
    which is how every expensive defect of 2026-08-20 happened: `column_header`
    and `image_only` set and discarded, `result_truncated` "computed and stored
    in this ledger for months and read by no renderer", `exhaustive_checks`
    holding 265 harness-aimed comparisons with one occurrence in the tree, and
    `predictor_disagrees` recorded beside a comment promising it was.
    """

    def test_it_finds_write_only_keys_in_the_main_module(self):
        """NAMES NO KEY, DELIBERATELY. The read side is raw text, so naming one
        here counts as an occurrence and the finding vanishes -- the first
        version of this test asserted a specific key, which dropped the count
        from 20 to 19 and then failed against itself. A test for this detector
        asserts its METHOD."""
        from forensic_metascience_ai_toolkit.inertness import scan

        found = scan(only=["write_only_key"])["findings"]
        assert any("agent.py" in f["where"] for f in found), (
            "the detector finds nothing in the module where every historical "
            "instance of this defect lived")

    def test_it_reports_a_worklist_never_a_certainty(self):
        """A key read through `**kwargs`, a variable subscript or an external
        tool is invisible to any static rule."""
        from forensic_metascience_ai_toolkit.inertness import scan

        assert all(f["confidence"] == "worklist"
                   for f in scan(only=["write_only_key"])["findings"])

    def test_tool_results_are_not_accused(self):
        """`registry` returns every tool payload as `json.dumps(result)` in an
        MCP text block: the MODEL is the reader, and no static analysis sees it.
        Including `tools/` accused `fisher_odds_ratio`, `achievable_t_interval`
        and a dozen more that are read on every call."""
        from forensic_metascience_ai_toolkit.inertness import scan

        wheres = {f["where"] for f in scan(only=["write_only_key"])["findings"]}
        assert not [w for w in wheres if "/tools/" in w]

    def test_dict_literals_are_out_of_scope(self):
        """Including them produced 336 items dominated by LaTeX symbol maps and
        env-var names. Every real instance was a SUBSCRIPT write -- "I computed
        this and stored it somewhere"."""
        from forensic_metascience_ai_toolkit.inertness import scan

        keys = {f["extra"]["key"] for f in scan(only=["write_only_key"])["findings"]}
        assert not {"Delta", "Omega", "Sigma", "TORCHDYNAMO_DISABLE"} & keys


class TestTheWriteOnlyRatchet:
    #: MEASURED 2026-08-20: 20. Two of them (`harness_sweep`, `ledger_problems`)
    #: are keys added that day which DO reach a reader through the report and
    #: register JSON -- the known false-positive class, since a static rule
    #: cannot see a human reading an artefact. Lower this as real ones are
    #: wired; raising it to green a red suite defeats the detector.
    #: RE-PINNED 2026-08-21 at the stacked-headers merge: 20 -> 32, read
    #: first. The detector also stopped sweeping node_modules/.next (172 s
    #: and vendored text silently "consuming" keys) and stopped crediting
    #: prefixes (`.key` inside `.keyword`), which surfaced honest new rows.
    #: The 32 are HTTP header names (read by servers), run_meta/ledger keys
    #: (read by humans and the model in artefacts), and Grok transcript
    #: fields. One real catch was wired instead of pinned: `web_unbacked`
    #: now reaches the adjudicator docket.
    #: RE-PINNED 2026-10-19: 32 -> 33, and no key became write-only. The
    #: serial-pipeline transcripts (`messages.stage{1,2}.json`) were deleted
    #: from tests/fixtures, and `permission_denials` (a run_meta field copied
    #: from the CLI's result event, read by people) had only ever counted as
    #: "consumed" because its name appeared inside those transcripts.
    MAX_WRITE_ONLY = 33

    def test_write_only_keys_have_not_multiplied(self):
        from forensic_metascience_ai_toolkit.inertness import scan

        n = scan(only=["write_only_key"])["n"]
        assert n <= self.MAX_WRITE_ONLY, (
            f"{n} write-only keys, above the pinned {self.MAX_WRITE_ONLY}. "
            "Run `metascience lint-inert` and read the new ones: each is an "
            "answer computed and delivered to nobody.")
