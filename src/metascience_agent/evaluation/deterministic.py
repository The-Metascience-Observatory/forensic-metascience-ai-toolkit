"""LLM-free checks on pipeline output.

These run offline and for free, so they double as regression tests: findings
JSON must parse and use the severity enum, reports must not leak model
preamble, and fixture `must_not_say` patterns must be absent.
"""

from __future__ import annotations

import re
import shlex
from typing import Any

from ..core import prompts
from .. import verdicts as _verdicts

# Meta-narration that indicates the model's working notes leaked into the
# report (historically: "Now I have all the data needed for the full report.")
_PREAMBLE_PATTERNS = [
    r"^now i have\b",
    r"^now let me\b",
    r"^let me\b",
    r"^i('ll| will) (now )?(write|produce|create|compile)\b",
    r"^(okay|ok|alright|great|perfect)[,.! ]",
    r"^the .* analysis fails because\b",
    r"^based on (all )?(my|the) (analysis|findings|checks), (here|i)\b",
    r"^here (is|'s) (the|my|a) (full |complete |final )?report\b",
]


def check_findings_json(findings: Any) -> dict:
    """Validate parsed findings against structural expectations.

    Dispatches on schema_version: 2.0 documents (the parallel pipeline /
    migrated corpora) validate the v2 invariants; anything else takes the
    v1 path unchanged.
    """
    if isinstance(findings, dict) and \
            str(findings.get("schema_version")) == "2.0":
        return check_findings_v2(findings)
    problems: list[str] = []
    if not isinstance(findings, dict):
        return {"passed": False, "problems": ["findings is not a JSON object"]}

    items = findings.get("findings")
    if not isinstance(items, list):
        problems.append("missing/invalid 'findings' array")
        items = []

    valid_severities = set(prompts.SEVERITY_VALUES)
    for i, f in enumerate(items):
        if not isinstance(f, dict):
            problems.append(f"finding[{i}] is not an object")
            continue
        sev = f.get("severity")
        if sev not in valid_severities:
            problems.append(f"finding[{i}] ({f.get('id')}) has invalid severity: {sev!r}")
        for key in ("id", "location", "technique", "reproduction"):
            if not f.get(key):
                problems.append(f"finding[{i}] ({f.get('id')}) missing {key}")

    if "coverage" not in findings:
        problems.append("missing 'coverage'")

    return {"passed": not problems, "problems": problems, "num_findings": len(items)}


def check_findings_v2(doc: dict) -> dict:
    """The v2 invariants (docs/specs/findings_v2.md section 9), the slice
    this module owns: outcome-null severity, title/description bounds, the
    impossible-requires-validated-absolute-tool rule, discarded rows
    RETAINED, and the adjudication record's honesty."""
    problems: list[str] = []
    items = doc.get("findings")
    if not isinstance(items, list):
        problems.append("missing/invalid 'findings' array")
        items = []
    adj = doc.get("adjudication")
    if not isinstance(adj, dict) or "ran" not in adj:
        problems.append("missing adjudication record (ran must be stated)")
        adj = {}
    n_discarded = 0
    for i, f in enumerate(items):
        if not isinstance(f, dict):
            problems.append(f"finding[{i}] is not an object")
            continue
        tag = f.get("slug") or f.get("finding_id")
        outcome = f.get("outcome")
        sev = f.get("severity")
        if outcome not in ("problem", "pass", "undecided"):
            problems.append(f"finding[{i}] ({tag}) invalid outcome {outcome!r}")
        if outcome != "problem" and sev is not None:
            problems.append(f"finding[{i}] ({tag}) carries a severity on a "
                            f"{outcome} row")
        action = (f.get("adjudication") or {}).get("action")
        if action == "discarded":
            n_discarded += 1
            if sev is not None:
                problems.append(f"finding[{i}] ({tag}) discarded but ranked")
        elif outcome == "problem" and adj.get("ran") and sev is None \
                and action != "merged":
            problems.append(f"finding[{i}] ({tag}) adjudicated problem row "
                            "with no severity")
        if outcome == "problem" and sev is not None and not (
                isinstance(sev, int) and 1 <= sev <= 9):
            problems.append(f"finding[{i}] ({tag}) severity {sev!r} off the "
                            "ladder")
        if f.get("impossible"):
            tv = f.get("tool_verdict") or {}
            if not (tv.get("validated") and tv.get("severity") == "impossible"):
                problems.append(
                    f"finding[{i}] ({tag}) claims impossible without a "
                    "validated impossible tool verdict")
        title = str(f.get("title") or "")
        desc = str(f.get("description") or "")
        if not 8 <= len(title) <= 90:
            problems.append(f"finding[{i}] ({tag}) title length {len(title)}")
        if not 20 <= len(desc) <= 700:
            problems.append(f"finding[{i}] ({tag}) description length "
                            f"{len(desc)}")
        if f.get("cross_check") == "not_run" and not f.get(
                "severity_is_provisional"):
            problems.append(f"finding[{i}] ({tag}) unrun cross-check on a "
                            "non-provisional row")
    declared = adj.get("n_discarded")
    if isinstance(declared, int) and declared != n_discarded:
        problems.append(f"adjudication says {declared} discarded; the rows "
                        f"hold {n_discarded} -- discards must be RETAINED")
    return {"passed": not problems, "problems": problems,
            "num_findings": len(items), "schema": "2.0"}


def check_no_preamble(report_markdown: str) -> dict:
    """The report must start with content, not model meta-narration."""
    first_line = ""
    for line in (report_markdown or "").splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped:
            first_line = stripped
            break
    hits = [
        p for p in _PREAMBLE_PATTERNS
        if re.search(p, first_line, flags=re.IGNORECASE)
    ]
    return {
        "passed": bool(first_line) and not hits,
        "first_line": first_line[:200],
        "matched_patterns": hits,
    }


def check_must_not_say(report_markdown: str, patterns: list[str]) -> dict:
    """Fixture anti-patterns (case-insensitive regex) must be absent."""
    text = report_markdown or ""
    hits = []
    for pattern in patterns or []:
        m = re.search(pattern, text, flags=re.IGNORECASE)
        if m:
            hits.append({"pattern": pattern, "match": m.group(0)[:200]})
    return {"passed": not hits, "hits": hits}


def check_verdict(verdict: str | None, expected: str) -> dict:
    """Score the run-level verdict, comparing through the CURRENT vocabulary.

    A raw `==` would have made the rename a mass eval failure for no reason
    that is about the papers: `metascience eval --skip-analysis` rescores
    reports already on disk, 34 of which were written as
    `trustworthy | questionable | untrustworthy`, and a fixture updated to the
    new words would have failed every one of them. Both sides go through
    `verdicts.canonical`, so an archived run and a fresh run of the same paper
    score identically -- which is the only reading under which the rename is a
    rename rather than a silent regression.

    `canonical` returns None for a word in neither vocabulary, and two Nones
    must NOT compare equal: an unparseable verdict scored against an
    unparseable expectation is not a pass. `valid_value` still tests the raw
    string against the schema enum, because a fresh run emitting a retired word
    IS a defect even though it scores correctly here.
    """
    got = _verdicts.canonical(verdict)
    want = _verdicts.canonical(expected)
    return {
        "passed": got is not None and got == want,
        "verdict": verdict,
        "expected": expected,
        "valid_value": verdict in prompts.VERDICT_VALUES,
    }


def check_tortured_track(paper_dir: Any, expected: Any) -> dict:
    """Run the tortured-phrases track directly (local, free -- no LLM) and
    score it against the fixture's `tortured_expected`.

    `expected` is either the string "none" (the track must RUN and find zero
    guarded fingerprints -- a refusal is a FAIL here, because "could not
    read" cannot stand in for "clean") or a dict like `{"k_min": 3}` (the
    track must run and find at least that many distinct guarded
    fingerprints).
    """
    from ..text_track import run_track

    try:
        out = run_track(paper_dir)
    except Exception as exc:  # noqa: BLE001 -- a crash is a plain failure
        return {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
    status = out.get("status", {})
    k = (out.get("result") or {}).get("n_distinct_fingerprints", 0)
    result = {"ran": status.get("ran"), "k": k,
              "refusal_subtype": status.get("refusal_subtype"),
              "expected": expected}
    if not status.get("ran"):
        result["passed"] = False
        return result
    if expected == "none":
        result["passed"] = k == 0
    elif isinstance(expected, dict):
        result["passed"] = k >= int(expected.get("k_min", 1))
    else:
        result["passed"] = False
        result["error"] = f"unrecognised tortured_expected: {expected!r}"
    return result


def run_all(
    findings: Any,
    report_markdown: str,
    verdict: str | None,
    fixture: dict,
    paper_dir: Any = None,
) -> dict:
    """Run every deterministic check for one paper; returns per-check results
    plus an overall pass flag."""
    checks = {
        "findings_json": check_findings_json(findings),
        "no_preamble": check_no_preamble(report_markdown),
        "must_not_say": check_must_not_say(
            report_markdown, fixture.get("must_not_say", [])
        ),
        "verdict": check_verdict(verdict, fixture["verdict_expected"]),
    }
    # Opt-in per fixture: the track is local and free, so asserting BOTH fire
    # (a known-tortured paper) and silence (gold papers) costs no tokens.
    if fixture.get("tortured_expected") is not None and paper_dir is not None:
        checks["tortured_track"] = check_tortured_track(
            paper_dir, fixture["tortured_expected"])
    checks["passed"] = all(
        c["passed"] for c in checks.values() if isinstance(c, dict)
    )
    return checks


# ---------------------------------------------------------------------------
# Reproduction-command validation
#
# The findings schema REQUIRES a `reproduction` string, but the only check was
# that it is non-empty. In the committed gold run all six were unrunnable --
# four named flags or commands that do not exist, two contained literal `...`.
# A finding nobody can reproduce is not auditable, which defeats the purpose.
# ---------------------------------------------------------------------------

#: Markers that always mean "this was left as a template".
_PLACEHOLDER_MARKERS = ("...", "…", "TODO", "FIXME", "XXX")

#: Markers that mean a template OUTSIDE a quoted argument and mean nothing
#: inside one. These four sat in the unconditional list above, and on a real
#: batch that produced a ~35% false-positive rate: 10 of 13, 8 of 10 and 11 of
#: 11 flagged commands were rejected over a brace belonging to a perfectly
#: runnable JSON payload --
#:     metascience multiplicity --tests '[{"id":"M1","p_value":0.001}]'
#: -- after which the report printed "not runnable as written" beside a command
#: that runs. A validator with that error rate teaches a reader to ignore it,
#: which is worse than not having one.
_QUOTED_SAFE_MARKERS = ("{", "}", "<", ">")


def _outside_quotes(cmd: str) -> str:
    """The command with the CONTENTS of quoted arguments removed.

    Placeholder detection runs on this, so a JSON payload cannot be mistaken
    for a template. Both quote styles; an unterminated quote is treated as
    running to the end, which is fine -- a half-quoted command is broken for
    other reasons and the parse below will say so.
    """
    out: list[str] = []
    quote: str | None = None
    for ch in cmd:
        if quote is None and ch in "\"'":
            quote = ch
        elif quote is not None and ch == quote:
            quote = None
        elif quote is None:
            out.append(ch)
    return "".join(out)


def known_commands() -> set[str]:
    """The verbs `metascience` actually accepts."""
    from ..cli import app

    names = set()
    for cmd in app.registered_commands:
        name = cmd.name or (cmd.callback.__name__ if cmd.callback else None)
        if name:
            names.add(name.replace("_", "-"))
    # Sub-apps (`metascience tool ...`, `metascience pipeline ...`) are verbs too.
    for group in getattr(app, "registered_groups", []):
        if group.name:
            names.add(group.name)
    return names


# Reviewed calculation verbs only. New CLI workflows must not become runnable
# merely because they were registered: image-sweep, review-write and others
# have side effects, and analyze/batch/eval can spend money. Keep this policy at
# the subprocess boundary, shared with the live annotator.
_REPRODUCTION_COMMANDS = frozenset({
    "absence-of-evidence", "anova", "check-bounds", "check-ci",
    "check-count-percent", "check-ratio", "chi2", "csf", "debit",
    "duplication-detect", "effect-size", "effect-size-from-f", "f-to-p",
    "flag-round-n", "flag-uninformative", "flow-check", "grim", "grim-sweep",
    "grimmer", "grimu", "grimu-coexist", "multiplicity", "paired-d-interval",
    "power-check", "prop-from-normal", "reconstruct-2x2", "regression-batch",
    "required-n", "rivets-anova", "rivets-t", "sd-or-se", "sd-range",
    "sprite", "stalt", "stat-to-p", "statcheck", "summation", "summation-batch",
    "table1-dispersion", "ttest", "variance-dispersion",
})


#: Tools whose `metascience tool run` replay may execute: the calculations
#: behind the verbs above, plus the four calculations that never had a verb.
#: Readers, parsers, the dispatcher, the tracks, the R wrappers and
#: `run_python_script` are not replayed.
def reproducible_tools() -> frozenset:
    """Computed on first use: the registry imports modules that import this one."""
    global _REPRODUCIBLE
    if _REPRODUCIBLE is not None:
        return _REPRODUCIBLE
    from ..registry import SPECS
    _REPRODUCIBLE = frozenset(
        {s.name for s in SPECS if s.cli in _REPRODUCTION_COMMANDS}
        | {"debit_check_batch", "grim_percentage", "check_regression",
           "recalc_within_subjects_t"})
    return _REPRODUCIBLE


_REPRODUCIBLE: frozenset | None = None


def reproduction_execution_problem(command: str) -> str | None:
    """Why automatic execution is refused; None permits a calculation.

    This is an execution policy, not a judgement about the paper or a promise
    that the command's arguments are valid. CLI parsing checks those on replay.
    """
    try:
        parts = shlex.split(command)
    except ValueError as exc:
        return f"invalid command quoting: {exc}"
    if len(parts) >= 2 and parts[:2] == ["metascience", "tool"]:
        # The generic command: only `run`, only a replayable calculation, and
        # only with inline JSON (an --args-file would read an arbitrary path).
        if (len(parts) < 4 or parts[2] != "run" or parts[3] not in reproducible_tools()
                or "--args-file" in parts):
            return ("not automatically executed: only `metascience tool run` of a "
                    "reviewed calculation may be replayed")
        return None
    if len(parts) < 2 or parts[0] != "metascience" or parts[1] not in _REPRODUCTION_COMMANDS:
        return "not automatically executed: only reviewed calculation commands may be replayed"
    if any(arg.split("=", 1)[0] == "--output" or arg.startswith("-o")
           for arg in parts[2:]):
        return "not automatically executed: reproduction checks may not write output files"
    return None


#: The value a finding SHOULD carry when no command can reproduce it. Named so
#: the prompt and the schema can point at one string instead of the model
#: inventing a different sentence every time.
NO_COMMAND = "NO COMMAND APPLIES"

#: Prose the model already writes when it means `NO_COMMAND`. Recognised so the
#: accounting is right for runs ALREADY ARCHIVED, not only for those made after
#: the schema gained a proper value: 127 of the 360 recorded reproduction
#: "failures" across this repo's archive are this, and calling them failures is
#: simply wrong. Consulted ONLY when the string does not begin with
#: `metascience`, so it can never swallow a real command.
_NO_COMMAND_RE = re.compile(
    r"^\s*(?:no\b|none\b|n/?a\b|not applicable\b|not reproducible\b|"
    r"mcp[\s-]?only\b|no command\b|no cli\b|no tool\b)", re.I)

#: The same honest answer written as a TAIL rather than a lead. `_NO_COMMAND_RE`
#: anchors at the start, so the model's "Reading of Table 2 against the Results;
#: no command applies." was classified as a command and failed validation with
#: "must invoke `metascience`, got 'Reading'". MEASURED on the 2026-09-01
#: flagged batch: 11 of 26 invalid rows were this, every one of them a finding
#: correctly reporting that nothing reproduces a reading.
#:
#: Consulted ONLY for a string that does not begin with `metascience`, and the
#: fallback stays "command", so a TYPO'd verb (`metascienc grim ...`) still
#: fails loudly rather than being laundered into "there was nothing to check".
#: That direction matters: this must never convert a broken command into an
#: absence of one.
_NO_COMMAND_TAIL_RE = re.compile(
    r"\bno\s+(?:command|cli|forensic\s+tool|tool)\b[^.;]{0,40}?"
    r"\b(?:applies|applicable|exists)\b", re.I)

#: A reproduction that names a persisted analysis script instead of a CLI verb.
#: `modules/scientific_proofreading_agent/prompt.md` INSTRUCTS the model to write exactly this for any
#: finding whose load-bearing number came from `run_python_script` ("its
#: `reproduction` names the persisted script by the path the tool result
#: reported"), and the validator demanded `metascience` -- so the prompt's own
#: prescribed answer shipped as `reproduction_valid: false`. Measured on the
#: 2026-09-01 flagged batch: 2 of 2 `computed_by: agent_code` findings.
#:
#: `reproduction_kind: "script"` was ALREADY declared in three schemas, read by
#: `parallel.py:388` and documented by `run_script.py` as the audit artefact
#: behind such a finding. Nothing ever set it. Anchored on the `analysis_code/`
#: directory that `run_script` actually writes to, so prose merely mentioning a
#: .py file is not mistaken for a citation.
_SCRIPT_RE = re.compile(r"(analysis_code/[\w.\-/]+\.py)\b")


def classify_reproduction(command: str) -> str:
    """`no_command_applies`, `script`, `command`, or `empty`.

    A FINDING THAT IS A JUDGEMENT HAS NO COMMAND, AND THAT IS NOT A FAILURE.
    "No confidence intervals are reported for any null claim" is a reading of
    the paper, not an arithmetic result: nothing reproduces it and nothing
    should. `reproduction` is typed as a required string described as an
    "exact `metascience ...` CLI command", with no way to say "not
    applicable" -- so the model's honest answer ("No forensic tool applies",
    "MCP-only tool, no CLI verb exists") was scored as a broken command and
    counted against the toolkit's own reproducibility.
    """
    cmd = (command or "").strip()
    if not cmd:
        return "empty"
    if cmd.upper().startswith(NO_COMMAND):
        return "no_command_applies"
    if cmd.split()[0] == "metascience":
        return "command"
    if _SCRIPT_RE.search(cmd):
        return "script"
    if _NO_COMMAND_RE.match(cmd) or _NO_COMMAND_TAIL_RE.search(cmd):
        return "no_command_applies"
    return "command"


def validate_reproduction(command: str) -> dict:
    """Statically check that a reproduction string could actually be run.

    Returns {"valid": bool, "problems": [str]}. Static only -- see
    `run_reproduction` to execute it.
    """
    problems: list[str] = []
    cmd = (command or "").strip()

    if not cmd:
        return {"valid": False, "problems": ["empty reproduction command"]}

    bare = _outside_quotes(cmd)
    for marker in _PLACEHOLDER_MARKERS:
        if marker in cmd:
            problems.append(f"contains placeholder {marker!r} -- not runnable as written")
    for marker in _QUOTED_SAFE_MARKERS:
        if marker in bare:
            problems.append(f"contains placeholder {marker!r} -- not runnable as written")

    parts = cmd.split()
    if parts[0] != "metascience":
        problems.append(f"must invoke `metascience`, got {parts[0]!r}")
    elif len(parts) < 2:
        problems.append("no subcommand given")
    else:
        verb = parts[1]
        valid = known_commands()
        if verb not in valid:
            problems.append(f"unknown subcommand {verb!r} (valid: {', '.join(sorted(valid))})")

    return {"valid": not problems, "problems": problems}


#: The ladder, for reading a verdict back out of a tool's own output.
_LADDER = ("impossible", "highly_suspicious", "suspicious", "indeterminate",
           "consistent")


def reported_severity(stdout: str) -> str | None:
    """The severity a tool PRINTED, or None if we could not read one.

    Tools announce their verdict first and in the clear -- `CONSISTENT: Mean
    3.14 is possible for n=28`, `indeterminate  correlation = 11.3` -- so the
    first ladder word in the output is the tool's answer. Searched over the
    opening only: `consistent` appears in explanatory prose further down
    ("...is consistent with...") and matching that would read the explanation
    as the verdict.

    None means UNREADABLE, and every caller must treat it as "we cannot tell"
    rather than as agreement. That distinction is the whole point of the
    change.
    """
    head = " ".join(str(stdout or "")[:200].split()).lower()
    best: tuple[int, str] | None = None
    for word in _LADDER:
        i = head.find(word)
        if i >= 0 and (best is None or i < best[0]):
            best = (i, word)
    if best is None:
        return None
    # `highly_suspicious` contains `suspicious`; prefer the longer word when
    # both start at effectively the same place.
    for word in ("highly_suspicious", "highly suspicious"):
        j = head.find(word)
        if j >= 0 and j <= best[0]:
            return "highly_suspicious"
    return best[1]


def run_reproduction(command: str, timeout: int = 180,
                     claimed_severity: str | None = None,
                     claimed_outcome: str | None = None) -> dict:
    """Execute a reproduction command and ask whether it AGREES with the finding.

    THE SEMANTICS THIS FIXES (Greg, 2026-08-11). Until now `ok` was
    `proc.returncode == 0`, which certifies only that the command RAN. Every
    forensic verb in this CLI exits 0 whichever verdict it reaches:

        $ metascience check-bounds 11.3 correlation
        indeterminate  correlation = 11.3            # exit 0

    So a finding claiming `impossible` could carry a green reproduction badge
    whose command, executed, said `indeterminate` -- the badge certified
    executability and was read as agreement. That is the weakest link in the
    evidence chain, because it is the one place a reader is invited to stop
    checking.

    Now:
      `executed`  -- the process ran and exited 0. What `ok` used to mean.
      `agrees`    -- the severity the tool PRINTED equals the one the finding
                     CLAIMS. True / False / None, where None is "unreadable".
      `valid`     -- executed AND agrees is not False. A disagreement is a
                     failure; an unreadable verdict is NOT promoted to success.

    FAIL-SAFE DIRECTION. With no `claimed_severity` to compare against, `agrees`
    is None and `valid` falls back to executability -- the old behaviour, and the
    honest one, since nothing was claimed to disagree with. What must never
    happen is a disagreement being scored as a pass, and that is the case the
    conjunction closes.

    Safe: every `metascience` subcommand is a pure local computation with no
    network access and no writes outside an explicit --output. The timeout is
    generous because CLI start-up is ~2s and these run in batch; a 60s cap
    produced spurious failures under heavy machine load.
    """
    import subprocess

    static = validate_reproduction(command)
    if not static["valid"]:
        return {"ran": False, "executed": False, "ok": False,
                "agrees": None, **static}

    problem = reproduction_execution_problem(command)
    if problem:
        return {"ran": False, "executed": False, "ok": False, "valid": False,
                "agrees": None, "problems": [problem]}

    try:
        proc = subprocess.run(
            shlex.split(command), capture_output=True, text=True, timeout=timeout
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        return {"ran": False, "executed": False, "ok": False, "valid": True,
                "agrees": None,
                "problems": [f"execution failed: {exc}"]}

    executed = proc.returncode == 0
    said = reported_severity(proc.stdout)
    claim = str(claimed_severity).strip().lower() if claimed_severity else None

    agrees: bool | None = None
    problems: list[str] = []
    if not executed:
        problems.append(f"exited {proc.returncode}: {proc.stderr.strip()[:200]}")
    elif claim:
        if said is None:
            problems.append(
                "the command ran but printed no verdict this checker could "
                f"read, so agreement with the claimed `{claim}` is unknown")
        else:
            # THE TWO SIDES SPEAK DIFFERENT VOCABULARIES. A v2 finding carries
            # a NUMERIC severity (`2`) while a tool prints the 5-enum STRING
            # (`suspicious`), so `said == claim` was structurally incapable of
            # being true and every v2 row with a readable verdict was told its
            # own command disagreed with it. MEASURED on the 2026-09-01 flagged
            # batch: it fired on the headline `check_count_percent` hit, which
            # the tool and the finding actually AGREE about.
            #
            # This is the frozen-v1-vocabulary defect for the third time
            # (`secondlook.ACCUSATORY`, `report_render`'s ladder). Bridged by
            # importing `severity9.OUTCOME_FROM_FIVE` -- the one stated
            # definition -- rather than writing a second mapping here.
            #
            # ON THE OUTCOME AXIS, NOT THE RUNG. A tool verdict does not pin a
            # rung: `impossible` is a 2-3 with `impossible: true`, because the
            # ladder grades consequence and the tool grades arithmetic. What a
            # tool CAN settle is whether this is a problem at all, and a tool
            # saying `consistent` under a finding claiming a problem is a real
            # disagreement worth printing.
            if claim.isdigit():
                from ..severity9 import OUTCOME_FROM_FIVE
                want = OUTCOME_FROM_FIVE.get(said)
                got = (claimed_outcome or "").strip().lower() or None
                # Fail-safe: an unmappable verdict or a missing outcome is
                # `None` (unknown), never False. We do not manufacture a
                # disagreement out of a vocabulary we could not read.
                agrees = None if (want is None or got is None) else (want == got)
                if agrees is False:
                    problems.append(
                        f"THE COMMAND DISAGREES WITH THE FINDING: it reports "
                        f"`{said}` (outcome `{want}`) where the finding claims "
                        f"outcome `{got}` at severity {claim}. The command ran "
                        "perfectly well -- that is the point. Re-read the "
                        "finding before the paper.")
            else:
                agrees = (said == claim)
            if agrees is False and not claim.isdigit():
                problems.append(
                    f"THE COMMAND DISAGREES WITH THE FINDING: it reports "
                    f"`{said}` where the finding claims `{claim}`. The command "
                    "ran perfectly well -- that is the point. Re-read the "
                    "finding before the paper.")

    return {
        "ran": True,
        "executed": executed,
        # `ok` kept as the executability fact under its old name, because
        # archived records and the viewer both read it. Its MEANING is now
        # stated rather than implied.
        "ok": executed,
        "valid": executed and agrees is not False,
        "agrees": agrees,
        "reported_severity": said,
        "claimed_severity": claim,
        "returncode": proc.returncode,
        "problems": problems,
        "stdout": proc.stdout[:500],
    }


#: A title carrying one of these, capitalised mid-phrase, is almost always a
#: sentence rather than the noun phrase the schema asks for. Deliberately short
#: and conservative: this is a NOTE on the output, never a rejection, and a
#: false positive here would nag about a title that is fine.
_SENTENCE_VERBS = (
    " prints ", " states ", " reports ", " omits ", " contains ", " injects ",
    " carries ", " shows ", " gives ", " uses ", " fails ", " appears ",
    " is ", " are ", " was ", " were ", " has ", " have ", " does ", " do ",
    " cannot ", " does not ", " contradicts ", " misstates ", " disagrees ",
)

#: RAISED 90 -> 120 on 2026-08-13, because the cap was condemning good work.
#:
#: MEASURED over all 357 finding titles in every archived report here: median
#: 93 characters, and a heading naming ONE defect has a median of 92. At 90 the
#: cap flagged 52.6% of single-defect titles; at 120 it flags 4.6% while still
#: catching 36.7% of the genuinely compound ones. 120 characters is still a
#: legible heading.
#:
#: This is the noun-phrase rule's mistake, one iteration later. That rule was
#: relaxed on 2026-08-10 after six prompt revisions failed to move a 0% pass
#: rate, and the reasoning given was that "a rule nobody follows devalues the
#: rules that matter". A cap the median well-formed title breaks is the same
#: rule in a different costume -- and it lives in a spec that also carries the
#: severity ladder, which is a bad neighbourhood for an instruction the model
#: learns to read as approximate.
_TITLE_MAX = 120

#: A heading that reads as two complaints. COUNTED, NEVER A FAILURE -- see
#: `check_titles`. Surface syntax cannot tell "two defects" from "one defect in
#: two clauses", and the archive is full of the latter:
#:
#:   "Moderation is claimed but never tested; the inference is a
#:    difference-in-significance fallacy"        <- one defect, restated
#:   "Blinding of outcome assessment absent, and randomisation stated only for
#:    the 37-animal sub-experiment"              <- genuinely two
#:
#: Both match. Roughly half of what this pattern flags is elaboration, so it
#: reports a number and decides nothing.
_COMPOUND_TITLE = re.compile(r";\s|,\s+and\s+|\band in one case\b", re.I)

#: THE ONE TITLE RULE WHERE SYNTAX REALLY IS THE MEANING: the heading names OUR
#: METHOD instead of the paper's defect. "GRIM check" and "Three independent
#: tool calls" are the schema's own BAD examples, and a reader scanning headings
#: learns nothing from either.
#:
#: Verified against known positives 2026-08-13 -- it fires on all five of the
#: schema's bad examples and on none of five real good titles, including "GRIM
#: inconsistency in the Table 2 means for the treatment arm", which names a tool
#: and still describes a defect. It matches 0 of the 357 archived titles: the
#: model does not make this mistake, and a guard proven able to fire that finds
#: nothing is a different thing from one that cannot fire at all.
_TITLE_NAMES_METHOD = re.compile(
    r"^\s*(?:\w+\s+)?(?:GRIM|GRIMMER|SPRITE|statcheck|DEBIT|STALT)\b"
    r"(?:\s+(?:check|test|analysis|sweep))?\s*$"
    r"|^\s*(?:\w+\s+){0,2}tool calls?\b"
    r"|^\s*(?:three|two|four|several|multiple)\s+\w+\s+(?:checks?|calls?|tests?)\s*$",
    re.I)


def check_titles(report: dict) -> dict:
    """Are finding titles noun phrases, as the schema asks?

    MEASURED on a real batch: 8 of 31 were. The rest were declarative
    sentences, several joining two unrelated defects with a semicolon. The
    prompt asked for noun phrases and got sentences, so this reports the gap
    rather than assuming the instruction took.

    A NOTE, not a failure. Title style does not make a finding wrong, and a
    check that blocks on prose would be worse than the problem. But an
    unmeasured instruction is an instruction nobody knows is being ignored.

    RE-MEASURED 2026-08-09, over every archived report in this repository:
    **0 of 14 pass. Not one, across 8 papers and several prompt revisions.**
    Both failure modes persist -- sentences with finite main verbs, and titles
    past 90 characters -- and the schema's `title` description already carries
    three GOOD and four BAD worked examples, so the instruction is about as
    explicit as prose can be made.

    RESOLVED (Greg, 2026-08-10): **the noun-phrase rule is relaxed.** Sentence
    shape is now counted and reported but is NOT a failure; the two rules that
    remain failures are the ones that are not matters of taste:

      * the 90-character cap, which is what actually affects a heading's
        legibility in the report and the viewer, and
      * the semicolon join, which is not a style problem at all -- a title
        naming two defects means the finding should have been split in two.

    The reasoning is that six prompt revisions did not move a 0% compliance
    rate, and a rule nobody follows devalues the rules that matter. Enforcing it
    mechanically was rejected: it would put our prose over the model's on the
    single most reader-facing string the system produces, and could flatten a
    title that was clearer as written.

    RECALIBRATED 2026-08-13, because the two surviving rules had the same defect
    the relaxed one did -- I had kept the reasoning and not applied it to the
    numbers.

    MEASURED over all 357 finding titles in every archived report here:

      * the 90-character cap flagged 52.6% of titles that name ONE defect,
        whose median length is 92. It was condemning the median piece of good
        work. Raised to 120, where it flags 4.6% of them and still catches
        36.7% of the compound ones.
      * the semicolon test caught 5 titles (1.4%) while the true compound rate
        is 8.4% -- it missed five compound headings in every six, because the
        ordinary way to join two complaints is ", and", not ";".

    The one-defect rule is the one worth enforcing: a heading naming two
    complaints means the finding should have been split, which is a real defect
    in the review rather than a matter of taste. The cap only has to stay short
    enough to be scannable.

    Archived reports passing this check went from 0 of 14 under the old
    calibration to 17 of 37 under this one, and the 20 that still fail do so on
    genuinely compound or genuinely overlong titles.

    Its result is written to `run_meta["title_quality"]`, deliberately not to
    the shipped bundle -- it is a grade on US, not a fact about the paper. See
    `OPERATOR_ONLY` in `tests/test_output_is_read.py`, which pins that decision
    so the field cannot quietly become unread for a different reason.
    """
    # A REPORT THAT FAILED TO PARSE IS `None`, and crashing on it turns an
    # upstream failure into a traceback here -- caught by the 2026-08-13 stress
    # pass. `pass: True` is right: there are no titles to be wrong, and this
    # check must not be the thing that reports a broken report.
    findings = (report or {}).get("findings") if isinstance(report, dict) else None
    if not isinstance(findings, list):
        return {"pass": True, "n": 0,
                "detail": "no findings to check"
                          + ("" if isinstance(report, dict)
                             else " (no readable report was given)")}

    sentences, joined, overlong, named_method = [], [], [], []
    for f in findings:
        if not isinstance(f, dict):
            continue
        title = str(f.get("title") or "").strip()
        if not title:
            continue
        low = " " + title.lower() + " "
        if any(v in low for v in _SENTENCE_VERBS):
            sentences.append(title)
        if _COMPOUND_TITLE.search(title):
            joined.append(title)
        if len(title) > _TITLE_MAX:
            overlong.append(title)
        if _TITLE_NAMES_METHOD.search(title):
            named_method.append(title)

    n = len([f for f in findings if isinstance(f, dict) and f.get("title")])
    problems = []
    # SENTENCE SHAPE, LENGTH AND COMPOUND SHAPE ARE ALL COUNTED, NEVER FAILURES.
    # Each was a syntactic proxy for a semantic property, and each condemned
    # good work: see the docstring for the three measurements. The counts stay
    # in the payload because they are the evidence for the relaxations, and
    # dropping them would make those decisions unauditable.
    if named_method:
        problems.append(
            f"{len(named_method)} title(s) name the METHOD rather than the "
            "defect -- a reader scanning the headings learns nothing from them")

    return {
        "pass": not problems,
        "n": n,
        "n_sentence_shaped": len(sentences),
        "sentence_shape_enforced": False,
        "n_joined": len(joined),
        "joined_enforced": False,
        "n_overlong": len(overlong),
        "overlong_enforced": False,
        "n_named_method": len(named_method),
        "length_guidance": _TITLE_MAX,
        # NAMED FOR ITS TRUNCATION, because it sits immediately beside the count
        # it is a sample of. A clamped run published `n_overlong: 4` next to an
        # `examples` list of 3, and a reader who set out to fix all four found
        # three. `examples_shown`/`n_examples_omitted` make the gap a stated
        # fact rather than something the reader has to notice.
        "examples_first_3": (named_method + joined + overlong)[:3],
        "n_examples_omitted": max(
            0, len(named_method) + len(joined) + len(overlong) - 3),
        "problems": problems,
        "detail": "; ".join(problems) or (
            f"all {n} title(s) name a defect rather than a method. "
            f"{len(overlong)} run past {_TITLE_MAX} characters and "
            f"{len(joined)} read as two clauses; both are reported, neither is "
            "a failure -- measured, those patterns flag good headings as often "
            "as bad ones."
        ),
    }


# DELETED 2026-08-11: `check_reproductions(findings, execute=False)`.
#
# Superseded by `agent._annotate_reproductions`, which is wired into the
# annotator chain and runs on every analysis. This one had no caller left:
# `run_all` above never included it, and `harness.run_all` is the eval entry
# point, so its last consumer went with the rewrite that
# `tests/test_reproduction_wiring.py` documents.
#
# IT WAS NOT MERELY DEAD. Two staleness bugs had accumulated behind the
# agreement change, and both fail in the direction that certifies a broken
# command as sound:
#
#   * it called `run_reproduction(cmd)` with no `claimed_severity`, so `agrees`
#     was always None and `valid` fell back to executability -- the exact
#     pre-change behaviour the rewrite existed to eliminate. Every forensic verb
#     exits 0 whichever verdict it reaches, so "it ran" says nothing about
#     whether it reached the verdict the finding claims;
#   * `n_valid` counted the legacy `ok` key, i.e. "exited 0", so a command whose
#     tool printed a DIFFERENT severity than its finding asserts was counted
#     valid.
#
# A tested, importable function that scores agreement by not checking it is
# worse than no function, because the next person to need one finds it first.
# If an eval entry point is wanted again, build it on `_run_repro_cached` and
# forward `claimed_severity=f.get("severity")`.
