"""ROUND 30 -- THE STATEMENT ABOUT A CHECK WE DO NOT MAKE WAS ITSELF FALSE, TWICE.

Round 29 shipped `NOT_WIRED_TOOLS` and a "Checks this bridge does not make"
section in `checks.md`, so that a registry tool whose population this account CAN
form stops being an absence with no representation. The mechanism was right. The
`why` string it renders to a reader was wrong in two independent ways, and an
audit found both. This round fixes them and makes the second one unrepeatable.

DEFECT 1 -- THE DIRECTIONALITY CLAIM WAS FALSE ABOUT THE TOOL. The string said
`check_regression` "is not directional, so it accuses a paper for reporting a p
more conservative than its own numbers imply". `check_regression` delegates its p
comparison to `ttest._p_matches`, which is directional BY DEFAULT and has been
since 2026-08-12, added for this exact false-accusation reason:

    p_is_threshold=None   ->  calculated_p <= reported_p + half   (over-claim only)
    p_is_threshold=True   ->  calculated_p <= reported_p          (over-claim only)
    p_is_threshold=False  ->  both directions  ("pass `False` only having
                              checked that the paper printed an exact value")

Measured on the very cell the old string's neighbours name -- Table 3's
`8.57 (3.03)` against a printed `.01`, at df = infinity -- `False` returns
`suspicious` and `None` and `True` both return `consistent`. So the
non-directionality is a property of ONE ARGUMENT WE CHOOSE, not of the tool.

The hazard it was pointing at is real and is now stated as a hazard: the natural
wiring reads the argument off the printed literal
(`p_is_threshold = printed.startswith("<")`), which hands `False` to every plain
`.01` -- and `.01` is the commonest printed p in this account's regression
tables. That is a fixable argument, not a blocked wiring; reasons 1 and 2 block.

DEFECT 2 -- FOUR ASSERTED NUMBERS, IN A COMMENT WHOSE OWN RULE FORBIDS THEM. The
same string said the tool "flags 3 of 63 coefficient rows ON THE WORKING ACCOUNT
and at df = n - k it flags 6, four of them different rows", while
`NOT_WIRED_TOOLS`'s own docstring says the population "IS COUNTED FROM THE
ACCOUNT, NEVER ASSERTED HERE ... because a number written into a comment is
falsified by the next reading of the next paper and nothing fails when it is".

The subtlety worth keeping: those four numbers are REPRODUCIBLE. They are
measurements of `test_scaffold_checks_round29`'s hand-retyped `TABLE2`/`TABLE34`
fixture, which holds 63 rows because it retypes Tables 2, 3 and 4. The ACCOUNT
holds 42: it types Table 4's estimates `other` rather than `coefficient`. So a
fixture measurement was wearing the account's name, and `checks.md` printed

    | `check_regression` | 42 | ... flags 3 of 63 coefficient rows ... |

-- 42 and 63 in one table row, both about the same population. Not false
arithmetic; a false attribution, which is the harder kind to see and the reason
the rule is absolute rather than a preference.

Replayed over the account's own 42 rows the qualitative claim survives and is
STRONGER than the counts made it look: at df = infinity and at df = n - k the two
flagged sets share NO row at all. So the claim worth keeping needs no count --
"the flagged set turns on a df the paper never printed" -- and that is what the
string now says.

WHAT IS ENFORCED HERE. The rule existed in prose and nothing checked it, so it
was broken in the object the prose was attached to. `TestNoNumberInAReaderFacingString`
makes a digit in one of these strings a test failure. The ban is on the DIGIT and
not on "a count", because you cannot tell a count from a quoted printed literal by
parsing, and both go stale the same way -- `8.57 (3.03)` is a fact about one
reading of one paper, and round 29's own
`test_the_accused_row_is_not_a_conversion_artefact` exists because that reading
can change. A number that belongs to a reader belongs in a column something
computed.
"""

from __future__ import annotations

import copy
import json
import re
from pathlib import Path

import pytest

from metascience_agent import registry
from metascience_agent.scaffold import checks
from metascience_agent.tools.ttest import _p_matches

ACCOUNT = (Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "papers" /
           "high_value_pdfs_to_run_on" / "10.1002--ajcp.70049" / "scaffold" / "account.json")

#: Any run of digits. See the module docstring for why the ban is this wide.
_DIGITS = re.compile(r"\d")

#: The fields of a `NOT_WIRED_TOOLS` record that reach a reader -- `why` and
#: `blocked_on` are rendered into `checks.md` directly, `population` is rendered
#: into `checks.json`, and all three are read by anyone opening this module.
#: Enumerated rather than "every string", so that adding a field is a decision
#: about whether it is reader-facing and not an accident.
_READER_FACING = ("population", "blocked_on", "why")


@pytest.fixture(scope="module")
def account() -> dict:
    if not ACCOUNT.exists():
        pytest.skip(f"the working account is not on disk at {ACCOUNT}")
    return json.loads(ACCOUNT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def got(account) -> dict:
    return checks.evaluate(copy.deepcopy(account))


class TestNoNumberInAReaderFacingString:
    """THE RULE `NOT_WIRED_TOOLS` STATES ABOUT ITSELF, ENFORCED.

    It said the population is counted and never asserted, and then asserted four
    numbers in the string beside the count. Prose cannot hold a rule; a test can.
    """

    def test_no_reader_facing_string_contains_a_digit(self):
        """THE ONE THAT WOULD HAVE CAUGHT IT. `"... flags 3 of 63 coefficient
        rows ... it flags 6, four of them different rows"` fails here on the
        first character of `3`.

        If a future entry genuinely needs a number, the answer is a counter in
        `unwired_population` and a column in `render_markdown` -- the same answer
        round 29 already chose for the population itself."""
        offenders = []
        for name, rec in checks.NOT_WIRED_TOOLS.items():
            for field in _READER_FACING:
                found = _DIGITS.findall(rec.get(field, ""))
                if found:
                    offenders.append(f"{name}.{field}: {''.join(found)!r} in {rec[field]!r}")
        assert not offenders, (
            "a number in one of these strings is a measurement of one reading of "
            "one paper, shipped to a reader as though it were a property of the "
            "tool. Count it in `unwired_population` instead:\n  "
            + "\n  ".join(offenders))

    def test_the_detector_fires_on_a_planted_number(self):
        """THE POSITIVE CONTROL, and it is not optional here. A scan that cannot
        fail reads exactly like a scan that passed, and this repo has shipped a
        regression test holding the disputed region constant before. Plant the
        exact sentence that was live at 404efd25 and require the detector to
        name it."""
        planted = {"check_regression": {
            "population": "a coefficient and its dispersion printed in one table cell",
            "blocked_on": "df_not_captured",
            "why": "at df = infinity this tool flags 3 of 63 coefficient rows on the "
                   "working account and at df = n - k it flags 6, four of them "
                   "different rows",
        }}
        offenders = [f"{n}.{f}" for n, rec in planted.items() for f in _READER_FACING
                     if _DIGITS.search(rec.get(f, ""))]
        assert offenders == ["check_regression.why"], offenders

    def test_the_rendered_section_carries_no_number_but_the_counted_one(self, got):
        """THE SAME RULE AT THE ARTIFACT BOUNDARY, which is where a reader meets
        it. Every digit in the section must come from the population column --
        the one number here that something computed."""
        md = checks.render_markdown(got)
        assert "Checks this bridge does not make" in md
        section = md.split("### Checks this bridge does not make")[1].split("\n### ")[0]
        rows = [ln for ln in section.splitlines() if ln.startswith("| `")]
        assert rows, "this account forms a non-empty population; a row must render"
        counted = {str(r["population_in_this_account"]) for r in got["tools_not_wired"]}
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            tool, population, blocked_on, why = cells[0], cells[1], cells[2], cells[3]
            assert population in counted, (tool, population)
            assert not _DIGITS.search(blocked_on), row
            assert not _DIGITS.search(why), row


class TestTheToolIsDirectional:
    """DEFECT 1, pinned from the tool's side, so the claim cannot be restated.

    Every assertion reads the live function rather than repeating a sentence
    about it -- the divergence being fixed is precisely a sentence that went on
    being true-sounding after the code it described had changed.
    """

    #: A p reported LARGER than the inputs imply: conservative reporting, and the
    #: case the old `why` said was accused. Values from `_p_matches`'s own
    #: worked example.
    CONSERVATIVE = dict(calculated_p=3.545e-05, reported_p=0.01, decimals_p=2)

    def test_the_default_does_not_flag_the_conservative_direction(self):
        """`None` -- what a caller gets for saying nothing -- enforces the
        interval in the over-claim direction only."""
        assert _p_matches(**self.CONSERVATIVE) is True
        assert _p_matches(**self.CONSERVATIVE, p_is_threshold=True) is True

    def test_only_an_explicit_false_tests_both_directions(self):
        """So non-directionality is reachable, and only by asserting something
        about the paper that a printed `.01` does not establish."""
        assert _p_matches(**self.CONSERVATIVE, p_is_threshold=False) is False

    def test_check_regression_inherits_the_direction_from_that_argument(self):
        """End to end through the registry, on the cell the comment names.
        `8.57 (3.03)` against a printed `.01` recomputes to about .0047."""
        def call(p_is_threshold):
            return registry.BY_NAME["check_regression"].call(
                {"b": 8.57, "se": 3.03, "reported_p": 0.01,
                 "p_is_threshold": p_is_threshold, "df": 10 ** 6,
                 "decimals_b": 2, "decimals_se": 2, "decimals_p": 2,
                 "source_quote": "8.57 (3.03)",
                 "source_locator": "regression table"})["severity"]
        assert call(False) == "suspicious"
        assert call(None) == "consistent"
        assert call(True) == "consistent"

    def test_no_why_string_claims_the_tool_is_not_directional(self):
        """The sentence that was wrong, banned by its own words. Cheap, and it
        is the half a reader actually reads."""
        for name, rec in checks.NOT_WIRED_TOOLS.items():
            why = rec["why"].lower()
            assert "not directional" not in why, name
            assert "non-directional" not in why, name

    def test_the_safe_argument_is_named_where_a_wiring_would_look(self):
        """A hazard recorded without its remedy sends the next session to
        re-derive the remedy. `p_is_threshold` is named in this module, beside
        the reason, so the wiring that walks into it finds the fix in the same
        place."""
        source = Path(checks.__file__).read_text(encoding="utf-8")
        head = source.split("NOT_WIRED_TOOLS: dict")[0]
        assert "p_is_threshold" in head
        assert "_p_matches" in head


class TestThePopulationIsStillTheAccountsOwn:
    """The half of round 29 that was right, re-asserted against the numbers that
    were wrong -- because the fix removes prose and must not move a count."""

    def test_the_counted_population_is_not_the_fixtures_sixty_three(self, got, account):
        """THE MISATTRIBUTION, MADE INTO AN ASSERTION. The round 29 fixture
        retypes three regression tables and so holds 63 rows; the account types
        Table 4's estimates `other` rather than `coefficient`, so it forms two
        tables' worth. Both facts are asserted here, because the old string's
        error was believing they were one fact.

        A later reading that promotes Table 4 SHOULD move this number -- and
        then the old string would have been wrong in a third way, which is the
        argument for never writing it down."""
        rec = {r["tool"]: r for r in got["tools_not_wired"]}
        counted = rec["check_regression"]["population_in_this_account"]
        assert counted > 0

        cells: dict[tuple, set] = {}
        for v in account["values"]:
            loc = v.get("location") or {}
            if loc.get("kind") == "table_cell":
                cells.setdefault((loc["table_id"], loc["row"], loc["col"]), set()).add(
                    v.get("statistic"))
        assert counted == sum(
            1 for (tid, row, col), stats in cells.items()
            if "coefficient" in stats
            and stats & {"sd", "se", "sem", "dispersion_unstated"}
            and "p_value" in cells.get((tid, row, col + 1), set()))

        # The gap itself: Table 4's estimates are typed `other` in the account
        # and `coefficient` in the fixture, which is the whole of 63 minus 42.
        t4 = {v.get("statistic") for v in account["values"]
              if (v.get("location") or {}).get("table_id") == "table:4"}
        assert "coefficient" not in t4, (
            "Table 4 now types coefficients; the population moved and this "
            "test's premise -- not the `why` string -- is what should change")

    def test_the_correction_moved_no_verdict(self, got):
        """THE CARDINAL RULE. This round changes strings and adds a test. If a
        severity moved, something else changed too."""
        assert got["n_run"] == 0
        assert got["by_severity"] == {}
        assert got["n_candidates"] == got["n_run"] + got["n_refused"]
