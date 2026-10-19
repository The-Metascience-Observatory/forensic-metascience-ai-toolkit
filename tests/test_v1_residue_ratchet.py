"""Three v1 structures the live path never produces, still read by live modules.

`report.json` carries `report_obj`, `coverage_summary` and the editorial
`stage1_finding_ids` join. `grep -c "report.json" parallel.py` returns 0 -- the
current path does not write that file. So every live read of these returns `{}`
or `None`, silently.

FOUR SYMPTOMS OF THIS SHIPPED, and each was a false statement to a reader:

  the viewer said NONE of 34 findings reached the report   (stage1_finding_ids)
  the census note blamed the run's age for a missing tool  (coverage_summary)
  every finding graded "reviewer reading", including 5 a
    registered tool computed                              (stage1_finding_ids)
  the evidence ledger graded nothing at all, so the fix
    to the grade above could not reach the page            (report_obj)

Each was fixed where it surfaced. The STRUCTURES are still there, and they will
produce a fifth.

THIS RATCHET DOES NOT FIX THAT. It stops it growing while the real work --
delete the readers, or port them to a v2 equivalent -- is done deliberately. A
count that only falls is the cheapest thing that makes a slow migration
finishable.
"""

from __future__ import annotations

import collections
import pathlib
import re

import pytest

SRC = pathlib.Path(__file__).resolve().parents[1] / "src" / "forensic_metascience_ai_toolkit"

#: The structures. Named rather than pattern-matched, because the point is
#: these three specifically -- not "anything v1-shaped".
V1_ONLY = ("report_obj", "stage1_finding_ids")

#: `agent.py` IS the legacy path and these are CORRECT there; `review_issues`
#: and `migrate_v2` exist to read v1 documents. Reads in those files are not
#: residue and are excluded rather than counted and waived.
LEGACY_BY_DESIGN = {"agent.py", "review_issues.py"}

#: THE MIGRATION MAP, measured 2026-09-03 by call-site analysis, so the next
#: person does not have to derive it again. Import reachability is the WRONG
#: instrument here -- almost every module is importable from `parallel.py`, and
#: that says nothing about whether the residue-reading FUNCTION is ever called.
#: At function level the 25 reads split cleanly:
#:
#:   LEGACY-ONLY (16 reads) -- the enclosing function has no caller outside
#:   `agent.py`, so these are DELETION candidates, not porting work:
#:     anchoring.anchor_of / annotate_anchoring / clamp_unanchored_norms
#:     bundle._reported_ids / _tool_cards / collect
#:     cli._published_findings
#:     finding_files.artefacts_for_editorial
#:     report_render.render_report / _render_quote /
#:       _render_severity_divergence / _render_divergence_accounting
#:     severity_reconcile.clamp_uncomputed
#:     warrants.clamp_supplied_norms
#:     webapp_index.is_image_finding
#:
#:   REACHABLE (7 reads) -- these need a v2 equivalent before the readers go:
#:     completeness.reconcile_findings      <- handoff.py
#:     consequence.annotate                 <- quotes, severity_reconcile, sourcing
#:     viewer_facts.evidence_grade          <- severity_reconcile
#:     viewer_facts.evidence_ledger         <- bundle   (LIVE: the viewer)
#:     viewer_facts.finding_index           <- bundle   (LIVE: the viewer)
#:
#: CAVEAT ON THAT SPLIT: "called from outside agent.py" is not the same as
#: "live". `severity_reconcile` itself has its only call site in `agent.py`
#: (section 8i), so anything reached only through it is transitively legacy.
#: The two marked LIVE are the ones that reach a reader today, through the
#: bundle -- and both were the site of a real reader-facing defect this week.
#:
#: UPDATED BY THE MERGE, 2026-09-04. Dan's v1.23.0 ported the coverage census
#: to the parallel path, retiring 11 counted reads and taking
#: `coverage_summary` out of `V1_ONLY` entirely. Every `coverage_summary`
#: line in the map above is therefore DONE -- and done the way this file
#: asks for, by porting the reader rather than patching a symptom. One of
#: the three structures is migrated; two remain.
#:
#: Measured 2026-09-01 at `ceb7cbc` as 25 over three structures; 20 over two
#: after that port. LOWER IS THE ONLY ACCEPTABLE DIRECTION.
#: Do not raise this to make a change pass -- a new read is a fifth symptom
#: waiting to happen, and the fix is to read the v2 record instead.
#: 9 since 2026-10-19 (1.100.0): the readers of the serial pipeline's output
#: layout were removed -- bundle, cli, completeness.reconcile_findings,
#: finding_files, viewer_facts.finding_index, webapp_index. What is left is
#: the serial pipeline's annotator family (anchoring, consequence,
#: report_render, severity_reconcile, warrants), reachable only via agent.py.
MAX_LIVE_READS = 9


def _live_reads() -> collections.Counter:
    counts: collections.Counter = collections.Counter()
    for f in sorted(SRC.rglob("*.py")):
        if f.name in LEGACY_BY_DESIGN:
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for name in V1_ONLY:
            # READS only. A mention in a comment or docstring is not a
            # dependency, and this file is full of comments about them.
            n = (len(re.findall(rf'\.get\(\s*["\']{name}["\']', text))
                 + len(re.findall(rf'\[\s*["\']{name}["\']\s*\]', text)))
            if n:
                counts[(f.name, name)] += n
    return counts


class TestTheResidueDoesNotGrow:
    def test_the_count_has_not_risen(self):
        counts = _live_reads()
        total = sum(counts.values())
        assert total <= MAX_LIVE_READS, (
            f"{total} live reads of v1-only structures, above the pinned "
            f"{MAX_LIVE_READS}.\n"
            + "\n".join(f"  {n}x {name} in {mod}"
                        for (mod, name), n in sorted(counts.items()))
            + "\n\nThese structures come from report.json, which parallel.py "
              "does not write, so a new read returns {} or None silently. Read "
              "the v2 record instead -- `computed_by`, the finding's own "
              "`adjudication.action`, or `report_v2.reported_finding_ids`."
        )

    def test_the_ratchet_is_not_vacuous(self):
        """A ratchet whose measurement is empty passes forever."""
        assert sum(_live_reads().values()) > 0

    def test_it_would_notice_a_new_read(self):
        """Proven, not assumed: the counter fires on the pattern it claims to."""
        probe = 'x.get("report_obj")\ny["stage1_finding_ids"]\n'
        n = sum(len(re.findall(rf'\.get\(\s*["\']{k}["\']', probe))
                + len(re.findall(rf'\[\s*["\']{k}["\']\s*\]', probe))
                for k in V1_ONLY)
        assert n == 2

    def test_a_comment_is_not_counted_as_a_dependency(self):
        """This repo's files are full of comments about these structures."""
        probe = "# report_obj is a v1 structure; see stage1_finding_ids\n"
        n = sum(len(re.findall(rf'\.get\(\s*["\']{k}["\']', probe))
                + len(re.findall(rf'\[\s*["\']{k}["\']\s*\]', probe))
                for k in V1_ONLY)
        assert n == 0


class TestTheLegacyPathIsExcludedDeliberately:
    @pytest.mark.parametrize("mod", sorted(LEGACY_BY_DESIGN))
    def test_the_excluded_module_exists(self, mod):
        """An exclusion naming a file that no longer exists is a silent
        widening of the allowlist."""
        assert (SRC / mod).is_file(), mod

    def test_parallel_still_does_not_produce_them(self):
        """The fact that makes every live read return nothing. If this ever
        changes, this whole ratchet should be revisited."""
        text = (SRC / "parallel.py").read_text(encoding="utf-8")
        for name in V1_ONLY:
            assert name not in text, name


# ---------------------------------------------------------------------------
# Field-level residue
# ---------------------------------------------------------------------------

#: THE HOLE IN THE RATCHET ABOVE. `V1_ONLY` names three STRUCTURES by hand, so
#: it cannot see a FIELD read under a v1 name: `secondlook.worklist` wrote
#: `"id": f.get("id")` on rows that carry `finding_id`, shipped
#: `{"id": null, "severity": null}` to the adjudicator on 4 of 10 control runs
#: (litvak02/05/06/07, v1.22.0), and this file stayed green throughout.
#:
#: The field set is DERIVED from the schemas at test time -- every property the
#: v1 finding or v1 report finding declares that the v2 finding does not -- so
#: it cannot go stale by hand the way a tuple of three names did.
_SCHEMA = SRC / "schema"


#: FROZEN, because the schemas this was derived FROM no longer exist. Dan's
#: v1.27.0 deleted the serial pipeline and with it `findings.schema.json` and
#: `report.schema.json`, so the subtraction that produced this set cannot be
#: recomputed from the tree. Re-deriving it at `100773d`, the last commit that
#: had both files, gives exactly these eleven -- and that is the right answer
#: forever: the v1 vocabulary is closed, because nothing will add to a schema
#: that has been deleted.
#:
#: To audit this, the derivation is one command:
#:   git show 100773d:src/metascience_agent/prompts/schema/findings.schema.json
#: union the same for report.schema.json, minus findings.v2.schema.json's
#: properties.
_V1_ONLY_FIELDS = frozenset({
    "assumptions", "confidence", "consistent", "explanation", "id", "passages",
    "plain", "rank", "severity_before_quarantine", "stage1_finding_ids",
    "warrant",
})


def _v1_only_fields() -> frozenset:
    return _V1_ONLY_FIELDS


#: A read counts only when BOTH hold: the receiver is spelled like a row
#: (`f.get("id")`, `finding["warrant"]`), AND the enclosing function touches a
#: findings collection -- as a name, an argument, an attribute, or a string
#: key such as `payload.get("findings")`. The first alone flags JSON-RPC
#: messages (`item.get("id")` in llm_backend), figures, and anatomy rows; the
#: second alone flags nothing at all in a one-row helper. Neither is proof.
ROW_NAMES = frozenset({"f", "finding", "fnd", "row", "card", "it", "item", "h",
                       "tgt", "hl", "b", "fi", "rec", "hit", "fr", "found",
                       "first", "dup", "cur", "prev", "r"})
FINDING_CONTEXT = frozenset({"findings", "finding", "merged", "sweep",
                             "stage1_findings", "merged_findings",
                             "report_findings", "kept", "cards"})


def _field_reads(text: str, fields: frozenset = None) -> list:
    """(line, field, receiver, function) for every counted read in `text`."""
    import ast
    fields = fields if fields is not None else _v1_only_fields()
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    fns = sorted((n for n in ast.walk(tree)
                  if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))),
                 key=lambda n: -((n.end_lineno or n.lineno) - n.lineno))
    owner: dict = {}
    for fn in fns:                       # largest first, so the innermost wins
        for n in ast.walk(fn):
            owner[n] = fn
    context: dict = {}

    def touches_findings(fn) -> bool:
        if fn not in context:
            seen = set()
            for n in ast.walk(fn):
                if isinstance(n, ast.Name):
                    seen.add(n.id)
                elif isinstance(n, ast.Attribute):
                    seen.add(n.attr)
                elif isinstance(n, ast.arg):
                    seen.add(n.arg)
                elif isinstance(n, ast.Constant) and isinstance(n.value, str):
                    seen.add(n.value)
            context[fn] = bool(seen & FINDING_CONTEXT)
        return context[fn]

    def receiver(node):
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            return node.attr
        return None

    out = []
    for n in ast.walk(tree):
        key = recv = None
        if (isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant)
                and isinstance(n.slice.value, str) and isinstance(n.ctx, ast.Load)):
            key, recv = n.slice.value, receiver(n.value)
        elif (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
              and n.func.attr == "get" and n.args
              and isinstance(n.args[0], ast.Constant)
              and isinstance(n.args[0].value, str)):
            key, recv = n.args[0].value, receiver(n.func.value)
        if key in fields and recv in ROW_NAMES:
            fn = owner.get(n)
            if fn is not None and touches_findings(fn):
                out.append((n.lineno, key, recv, fn.name))
    return out


def _live_field_reads() -> collections.Counter:
    counts: collections.Counter = collections.Counter()
    fields = _v1_only_fields()
    for f in sorted(SRC.rglob("*.py")):
        if f.name in LEGACY_BY_DESIGN or f.name == "finding_view.py":
            # `finding_view.ref` is the ONE place the `id` fallback may live.
            continue
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        for line, key, recv, fn in _field_reads(text, fields):
            counts[(f.name, key, fn)] += 1
    return counts


#: Measured 2026-09-04 after `secondlook`, `viewer_facts`, `bundle` and
#: `evaluation/agreement` were pointed at `finding_view`. LOWER IS THE ONLY
#: ACCEPTABLE DIRECTION. What remains is mostly the legacy renderer and the
#: legacy clamps (`report_render`, `severity_reconcile`, `anchoring`,
#: `warrants`, `completeness`, `computation`, `consequence.annotate`,
#: `finding_files`) -- reachable only from `agent.py` but living in modules
#: this file cannot exclude wholesale -- plus two deliberate v1 reads
#: (`evaluation/deterministic.check_findings_json`'s schema-gated v1 branch,
#: `parallel._rows_from_producer`'s `consistent` -> `outcome` default).
#: Of the 45, four are a known false positive -- `cli.lint_inert_cmd` reads
#: `confidence` on LINT rows, in a function whose prose mentions findings --
#: kept rather than special-cased, because an allowlist is the drift point
#: this ratchet exists to avoid. Lower it when you remove a real read.
#: 46 since 2026-10-16: `history_db._sync_report_findings` reads `id` on
#: legacy report rows. Not a new read -- the general modules moved back from
#: the image package into this tree, which brought it inside the scan.
#: 38 since 2026-10-19 (1.100.0, the old-layout readers removed).
MAX_LIVE_FIELD_READS = 38


class TestTheFieldLevelResidueDoesNotGrow:
    def test_the_field_set_is_derived_not_typed(self):
        fields = _v1_only_fields()
        assert {"id", "consistent", "explanation", "stage1_finding_ids",
                "warrant"} <= fields, sorted(fields)
        assert "finding_id" not in fields and "severity" not in fields

    def test_the_count_has_not_risen(self):
        counts = _live_field_reads()
        total = sum(counts.values())
        assert total <= MAX_LIVE_FIELD_READS, (
            f"{total} reads of v1-only finding FIELDS on row-shaped receivers, "
            f"above the pinned {MAX_LIVE_FIELD_READS}.\n"
            + "\n".join(f"  {n}x {key!r} in {mod}:{fn}"
                        for (mod, key, fn), n in sorted(counts.items()))
            + "\n\nA v2 row carries `finding_id`, not `id`; an integer "
              "`severity`/`provisional_severity`, not a word; and no "
              "`stage1_finding_ids`, `warrant`, `explanation` or `consistent`. "
              "Read the row through `finding_view` (ref, effective_severity, "
              "severity_level, is_accusatory) instead of restating its shape."
        )

    def test_the_ratchet_is_not_vacuous(self):
        assert sum(_live_field_reads().values()) > 0

    def test_it_would_have_caught_the_secondlook_defect(self):
        """The known positive: the exact shape of secondlook.py:244 at 7a97df8."""
        probe = (
            "def worklist(findings):\n"
            "    rows = []\n"
            "    for f in findings:\n"
            '        rows.append({"id": f.get("id"), "severity": f.get("severity")})\n'
            "    return rows\n")
        hits = _field_reads(probe)
        assert [(k, r) for _, k, r, _ in hits] == [("id", "f")], hits

    def test_a_string_key_findings_context_counts(self):
        """`viewer_facts.evidence_ledger` reaches its rows through
        `payload.get("findings")` -- a string key, not a name. A context rule
        that read only names missed all four of its residue reads."""
        probe = ('def evidence_ledger(payload):\n'
                 '    for f in payload.get("findings") or []:\n'
                 '        ids = f.get("stage1_finding_ids")\n')
        assert [k for _, k, _, _ in _field_reads(probe)] == ["stage1_finding_ids"]

    def test_what_it_cannot_see_is_stated(self):
        """WHAT THIS RATCHET CANNOT SEE, proven on the shapes of two live
        defects it would have missed, so nobody reads a green run as more
        than it is:

        1. A VALUE-VOCABULARY mismatch. `agreement._band` read the right
           field (`severity`) and compared it against the wrong ladder
           (`str(sev) in ACCUSATORY`, five words, on integers) -- 285 of 285
           control rows banded "clears". The field name is fine; the
           comparison is wrong; no key-name scan can tell.
        2. A row reached through a receiver this rule does not know, in a
           function that never says "findings" -- `agreement.count` iterates
           `runs` and `run`.

        The instrument for (1) is `finding_view.is_accusatory` at every call
        site and the contract tests in tests/test_finding_row_contract.py,
        not this count."""
        vocabulary = ('def _band(sev):\n'
                      '    return "accuses" if str(sev) in ACCUSATORY else "clears"\n')
        assert _field_reads(vocabulary) == []
        unknown_context = ('def count(runs):\n'
                           '    return {cluster_key(f) for run in runs for f in run\n'
                           '            if f["stage1_finding_ids"]}\n')
        assert _field_reads(unknown_context) == []

    def test_a_variables_table_is_not_a_finding_row(self):
        """`id` is generic. Receiver AND context are both required."""
        probe = ("def cell_census(variables):\n"
                 '    return {v.get("id"): v for v in variables}\n')
        assert _field_reads(probe) == []

    def test_a_row_shaped_receiver_outside_findings_context_is_not_counted(self):
        probe = ("def feed(items):\n"
                 "    for item in items:\n"
                 '        yield item.get("id")\n')
        assert _field_reads(probe) == []

    def test_a_comment_is_not_counted(self):
        probe = '# f.get("id") is the v1 spelling; see finding_view\nx = 1\n'
        assert _field_reads(probe) == []

    def test_the_shared_reader_is_excluded_by_name_and_exists(self):
        """`finding_view.ref` is the ONE place the `id` fallback may live, so it
        is excluded from the count -- and an exclusion naming a file that no
        longer exists is a silent widening, exactly as for LEGACY_BY_DESIGN."""
        assert (SRC / "finding_view.py").is_file()
        assert not any(mod == "finding_view.py" for mod, _, _ in _live_field_reads())
