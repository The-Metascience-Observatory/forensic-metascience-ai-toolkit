#!/usr/bin/env python3
"""Score an FMA run against Litvak's planted errors -- on the RIGHT denominator.

    python benchmarks/litvak/score.py ~/fmt-litvak/modified
    python benchmarks/litvak/score.py ~/fmt-litvak/original --control

THE DENOMINATOR IS 100. Every planted error is scored.

A two-category "declared scope" used to make the headline 20 of 100, on the
argument that the other eight categories were outside what this system attempts.
That was asserted before measurement, and the first complete run refuted it:
FMA caught 36 of the 80 supposedly-out-of-scope errors, including
construct_validity 6/10 and methodological_design 6/10. A category hit at 60%
is not one the system does not attempt. Retired 2026-08-23.

The comparison figure to print beside our number is the UNION of Litvak's
fourteen systems, recomputed on the same papers -- 93 of 100. That is the
empirical ceiling. The seven errors no system caught are a hard tail, not a
scope boundary, and only two of them are deletions: 15 of the 17 pure deletions
were caught by somebody, so omissions are difficult rather than impossible.

WHAT TO EXPECT, written down BEFORE the first run so the result cannot be
reinterpreted afterwards (measured from the ground-truth CSV 2026-08-21,
corrected 2026-08-23):

  - ONE is squarely deterministic: `p_value_inconsistent` (p .033 -> .003 where
    chi-square(3)=8.74 gives .0330). statcheck's own job.
    NOT TWO. `model_results_contradiction` was listed here as the second, and
    it is not: the modified text reports chi-square(1)=2.34, p=.126, and
    chi-square(1)=2.34 really does give p=.1261. statcheck PASSES it. The catch
    is that the prose still claims SDO is the stronger predictor after the test
    stopped saying so -- a text-vs-number contradiction, which is the science
    analyst's beat, not a recomputation.
  - ~6 need the register plus a text-to-table cross-reference:
    `exclusion_criterion_removed` (subcategory counts stop summing),
    `coder_count_changed`, `analysis_count_inconsistent`,
    `iatrogenic_means_reversed`, `effect_direction_reversed`,
    `stopping_rule_changed`.
  - ~6 need domain reasoning no check can do: a tool cannot know that `a*d`
    is the wrong serial-mediation formula.
  - 1 is a true deletion (`fisher_z_removed`); 19 are in-place alterations.
    Every error no system in Litvak's test caught was an omission, and we have
    one.

THREE PASSES, REPORTED SEPARATELY.

  `floor`  -- deterministic, quote or number overlap. Cheap, no model, and a
             genuine LOWER bound only after the fixes below; it still
             under-counts paraphrase badly.
  `judge`  -- Litvak's own protocol, ported: his `JUDGE_SYSTEM` verbatim, one
             call per finding against that paper's ten errors, first-claim-wins
             one-to-one assignment. Transport is `claude -p --model haiku`
             rather than an API call, so no API key is needed.

  `verify` -- one call per ERROR rather than per finding, shown every problem
             finding for that paper at once, and REQUIRED to quote verbatim the
             words that identify the defect. The quote is checked in code. This
             is the number to publish; the judge number is what makes us
             comparable to Litvak.

Where the passes disagree, the row is printed. That shortlist is the thing to
eyeball before any number leaves the repo.

WHAT WAS WRONG WITH THE FIRST VERSION OF THIS FILE, all of it measured:

  - It never filtered on `outcome`. findings-v2 rows are `problem`|`pass`|
    `undecided`, and `pass` means the check RAN AND FOUND NOTHING. A tool that
    checked the planted CI, quoted its numbers and cleared it was scored as
    having CAUGHT the planted error. The benchmark ran backwards.
  - It never read the CSV's `paper` column and pooled findings from the whole
    corpus, so an error planted in paper 3 could be "hit" by a finding in paper
    7. Litvak's scorer is strictly per-paper.
  - One finding could claim all twenty errors. Litvak's assignment is one-to-one.
  - `rglob` merged every `forensic_review_*` sibling, so an old run inflated a
    new one.
  - `fisher_z_removed` has an EMPTY `modified_snippet` (it is the deletion), and
    both match paths were guarded on non-empty text, so it was an automatic miss
    that still occupied a slot in the denominator.
  - The docstring claimed the matcher "over-counts nothing". Measured on the 20
    in-scope rows: 8 have a 60-char prefix identical to the UNMODIFIED original,
    so a finding about anything in that region scored as a hit; 9 have identical
    number sets before and after; 8 have no usable numbers at all.
  - The blob read `summary`/`evidence`/`explanation`, none of which exist in
    findings-v2, and skipped `reported`/`computed`/`inputs`/`reproduction` --
    the fields that actually carry the numbers a check used.
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Callable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paths import BenchmarkNotFound, add_bench_arg, resolve_bench  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]

#: RETIRED 2026-08-23. This was a two-category "declared scope" that made the
#: headline denominator 20 instead of 100. It was asserted before measurement,
#: and the first complete run refuted it: FMA caught 36 of the 80 errors the
#: scorer was calling out of scope, including construct_validity 6/10 and
#: methodological_design 6/10. A category hit at 60% is not one the system does
#: not attempt. `compare.py` keeps a reference for its own filter only until
#: that is removed too. THE DENOMINATOR IS 100.
IN_SCOPE: tuple[str, ...] = ()

NUM = re.compile(r"-?\d+\.?\d*")
_WS = re.compile(r"\s+")

#: Bumped whenever JUDGE_SYSTEM or the finding rendering changes, so a stale
#: cache cannot answer a question that is no longer the one being asked.
JUDGE_PROMPT_VERSION = "v1"
JUDGE_MODEL = "haiku"
#: The verifier reads a whole paper's findings at once and its answer is
#: the one we publish, so it runs on a stronger model than the first pass.
VERIFY_MODEL = "sonnet"
#: v2 (2026-08-24): the verifier renderer was normalised so an FMA
#: finding and a Litvak-system finding are shown in the same field set.
VERIFY_PROMPT_VERSION = "v2"
CACHE_PATH = Path(__file__).resolve().parent / "_judge_cache.json"


# --------------------------------------------------------------------------
# ground truth
# --------------------------------------------------------------------------

def ground_truth(bench: Path) -> list[dict]:
    with open(bench / "error_insertions.csv", encoding="utf-8-sig") as fh:
        rows = list(csv.DictReader(fh))
    for r in rows:
        r["paper"] = int(r["paper"])
    return rows


def paper_dir_number(p: Path) -> Optional[int]:
    """`litvak07` -> 7. None for anything that is not a prepared paper dir."""
    m = re.fullmatch(r"litvak0*(\d+)", p.name)
    return int(m.group(1)) if m else None


# --------------------------------------------------------------------------
# findings
# --------------------------------------------------------------------------

def review_dirs(paper_dir: Path) -> list[Path]:
    """Every review directory in a paper, newest first, bundles excluded.

    Mirrors `webapp_index.review_dirs`; duplicated rather than imported so this
    script runs without the package installed. Sorted by mtime, not by name:
    the names encode a model and a version but not consistently.
    """
    out = [d for d in paper_dir.iterdir()
           if d.is_dir() and d.name.startswith("forensic_review")
           and not d.name.endswith("_bundle")]
    return sorted(out, key=lambda d: d.stat().st_mtime, reverse=True)


def load_findings(paper_dir: Path, all_runs: bool = False) -> tuple[list[dict], list[Path]]:
    """This paper's findings, from its NEWEST review dir only by default.

    The default output dir is `forensic_review_<model>_v<version>`, so a re-run
    creates a SIBLING rather than replacing anything. A corpus-wide rglob merged
    every run of every paper into one pool, which both crossed papers and let a
    superseded run inflate the current one.
    """
    dirs = review_dirs(paper_dir)
    if not all_runs:
        dirs = dirs[:1]
    findings, used = [], []
    for d in dirs:
        for name in ("findings.v2.json", "findings.json"):
            fp = d / name
            if not fp.is_file():
                continue
            try:
                doc = json.loads(fp.read_text(encoding="utf-8"))
            except Exception:
                continue
            items = doc.get("findings") if isinstance(doc, dict) else doc
            if isinstance(items, list):
                findings.extend(x for x in items if isinstance(x, dict))
                used.append(fp)
            break          # v2 wins; never read both from one dir
    return findings, used


def load_findings_from_db(corpus: str, db_url: Optional[str] = None
                         ) -> tuple[dict[int, list[dict]], dict[int, dict]]:
    """Every paper's findings for one corpus, straight out of the findings database.

    The `findings.record` column holds the complete findings-v2 row -- quote,
    reported, computed, inputs and all -- so a run pushed from another machine
    is scoreable here without its files. Keyed by paper NUMBER, parsed from
    `papers.dir`, so the per-paper scoping is the same as the filesystem path's.

    NEWEST RUN PER PAPER, matching `load_findings`. A corpus can hold several
    runs of one paper and pooling them would let a superseded run inflate the
    current one -- the same defect as the corpus-wide rglob, one storage layer
    down.
    """
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from forensic_metascience_ai_toolkit.db_push import _connect      # noqa: PLC0415

    conn = _connect(db_url)
    try:
        cur = conn.cursor()
        cur.execute(
            "select distinct on (p.id) p.dir, r.id, r.run_uid, r.meta, "
            "r.analysed_at, r.cost_usd, r.verdict "
            "from papers p join corpora c on c.id = p.corpus_id "
            "join runs r on r.paper_id = p.id "
            "where c.name = %s order by p.id, r.analysed_at desc nulls last, r.id desc",
            (corpus,))
        runs = cur.fetchall()
        if not runs:
            raise SystemExit(f"no runs for corpus {corpus!r} in the database")

        out: dict[int, list[dict]] = {}
        meta: dict[int, dict] = {}
        for dirname, run_pk, run_uid, run_meta, at, cost, verdict in runs:
            n = paper_dir_number(Path(dirname))
            if n is None:
                continue
            cur.execute("select record from findings where run_id = %s", (run_pk,))
            rows = []
            for (rec,) in cur.fetchall():
                r = rec if isinstance(rec, dict) else json.loads(rec or "{}")
                if isinstance(r, dict) and r:
                    rows.append(r)
            out[n] = rows
            meta[n] = {"dir": dirname, "run_uid": run_uid, "analysed_at": at,
                       "cost_usd": cost, "verdict": verdict,
                       "meta": run_meta if isinstance(run_meta, dict)
                       else json.loads(run_meta or "{}")}
        return out, meta
    finally:
        conn.close()


def db_models(meta: dict) -> tuple[list[str], list[str]]:
    """(models_resolved, primary_billed) across a run's stages.

    Reported instead of `runs.model`, which is NULL for every row the batch
    runner pushed. `bundle.py` records a measured case where the stages resolve
    two models and bill one, so a single name is not the whole answer.
    """
    res, billed = set(), set()
    for st in ((meta.get("meta") or {}).get("stages") or {}).values():
        if isinstance(st, dict):
            res |= set(st.get("models_resolved") or [])
            if st.get("primary_billed_model"):
                billed.add(st["primary_billed_model"])
    return sorted(res), sorted(billed)


def split_by_outcome(findings: list[dict]) -> dict[str, list[dict]]:
    """`problem` / `pass` / `undecided` / `quarantined`, kept apart.

    THE LOAD-BEARING DISTINCTION. `pass` means the check ran and found nothing;
    counting one as a detection credits us with catching an error we cleared.
    v1 rows have no `outcome`; they fall back to the legacy `consistent` bool.
    """
    out: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        oc = f.get("outcome")
        if oc is None:                              # legacy v1 row
            oc = "pass" if f.get("consistent") is True else "problem"
        if f.get("quarantined"):
            out["quarantined"].append(f)
        out[oc if oc in ("problem", "pass", "undecided") else "undecided"].append(f)
    return out


def candidates(findings: list[dict], include_quarantined: bool) -> list[dict]:
    by = split_by_outcome(findings)
    rows = list(by["problem"])
    if not include_quarantined:
        rows = [f for f in rows if not f.get("quarantined")]
    return rows


# --------------------------------------------------------------------------
# deterministic floor matcher
# --------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Fold the differences a Word->PDF->docling round trip introduces.

    The snippets carry curly quotes, en dashes, multiplication signs and Greek
    letters (4 of the 20 in-scope rows do). An exact substring test against
    extracted text fails on all of them, which is most of why the quote path
    was near-dead in practice.
    """
    t = unicodedata.normalize("NFKD", text or "")
    for a, b in (("’", "'"), ("‘", "'"), ("“", '"'),
                 ("”", '"'), ("–", "-"), ("—", "-"),
                 ("−", "-"), ("×", "x"), (" ", " ")):
        t = t.replace(a, b)
    t = "".join(c for c in t if not unicodedata.combining(c))
    return _WS.sub(" ", t).strip().lower()


def _numbers(text: str) -> set[str]:
    return {n for n in NUM.findall(text or "") if len(n) > 1}


#: Every findings-v2 field that can carry the numbers or the wording of a check.
#: `summary`, `evidence` and `explanation` are NOT among them -- they were in
#: the original blob and do not exist in the schema.
_TEXT_FIELDS = ("title", "description", "quote", "location", "reproduction",
                "anchor_summary", "consequence", "notes")
_OBJ_FIELDS = ("reported", "computed", "inputs")


def finding_blob(f: dict) -> str:
    parts = [str(f.get(k) or "") for k in _TEXT_FIELDS]
    for k in _OBJ_FIELDS:
        v = f.get(k)
        if isinstance(v, (dict, list)):
            parts.append(json.dumps(v, default=str))
        elif v is not None:
            parts.append(str(v))
    return " ".join(parts)


def floor_match(row: dict, findings: list[dict],
                skip: Optional[set[int]] = None) -> Optional[dict]:
    """Quote or number overlap. A FLOOR, and only after the caveats below.

    Returns None for `fisher_z_removed`, whose `modified_snippet` is empty
    because the error IS the deletion. The caller reports that as
    `unscoreable_by_construction` and drops it from the FLOOR's denominator --
    an automatic miss silently occupying a slot is a wrong denominator, which
    is the defect class this whole repo exists to catch. The judge scores it
    normally, from the description.
    """
    skip = skip or set()
    mod = (row.get("modified_snippet") or "").strip()
    if not mod:
        return {"how": "unscoreable_by_construction"}
    want = _numbers(mod)
    key = _norm(mod)[:60]
    for idx, f in enumerate(findings):
        if idx in skip:
            continue
        blob = finding_blob(f)
        hit = {"finding_index": idx, "id": f.get("finding_id") or f.get("id")}
        if len(key) > 25 and key in _norm(blob):
            return {"how": "quote", **hit}
        if want and want <= _numbers(blob):
            return {"how": "numbers", **hit}
    return None


def is_hit(entry: Optional[dict]) -> bool:
    """A matcher entry that is a DETECTION.

    `unscoreable_by_construction` is recorded so the row can be named, and it
    is not a hit. Counting it as one is how an automatic miss turns into a
    phantom catch, so every consumer goes through this function.
    """
    return bool(entry) and entry.get("how") != "unscoreable_by_construction"


def assign_floor(rows: list[dict], findings: list[dict]) -> dict[int, dict]:
    """One-to-one: a finding claims at most one error, first claim wins.

    Exclusion is by POSITION, not by `finding_id`: a v1 row may carry neither
    `finding_id` nor `id`, and a None key would let one finding claim every
    remaining error.
    """
    used: set[int] = set()
    out: dict[int, dict] = {}
    for i, r in enumerate(rows):
        hit = floor_match(r, findings, skip=used)
        if is_hit(hit):
            used.add(hit["finding_index"])
        if hit:
            out[i] = hit
    return out


# --------------------------------------------------------------------------
# LLM judge -- Litvak's protocol, Claude Code CLI transport
# --------------------------------------------------------------------------

#: VERBATIM from `benchmark/matching.py`. This prompt is the comparability
#: surface between our number and his fourteen; do not reword it.
JUDGE_SYSTEM = """You are a strict matching judge. You will be given a list of known errors that were inserted into a scientific paper, and a single reviewer finding. Your job is to determine if the reviewer's finding identifies the SAME SPECIFIC issue as any of the known errors.

IMPORTANT: A match requires that the reviewer identified the SPECIFIC problem that was introduced — not just that they commented on the same topic or section. For example:
- If the error was "changed between-subjects to within-subjects", the reviewer must flag the within-subjects design as wrong. Simply discussing the experimental design is NOT a match.
- If the error was "removed the robustness check", the reviewer must note that the robustness check is MISSING. Commenting on robustness in general is NOT a match.
- If the error was "added exclusion criteria", the reviewer must flag those specific exclusions as problematic. Discussing exclusion criteria in general is NOT a match.
- If the error was "reversed the effect direction", the reviewer must notice the direction is inconsistent. Discussing effect sizes in general is NOT a match.

The reviewer doesn't need to use the same words, but they must have noticed the same specific defect — not merely discussed the same topic area.

Respond with ONLY the error number (1-10) if there's a clear match, or "none" if the finding merely discusses a related topic without identifying the specific inserted problem. When in doubt, say "none"."""

#: Litvak parses a bare number out of free text with a regex. We force the
#: shape instead -- the only deviation from his protocol besides the two bug
#: fixes, and it can only remove parse noise, not change a judgement.
JUDGE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["error_number"],
    "properties": {
        "error_number": {
            "type": ["integer", "null"],
            "minimum": 1, "maximum": 10,
            "description": "The matching error's number, or null for no match.",
        },
    },
}


def errors_block(errors: list[dict]) -> str:
    """The ten errors for one paper, in Litvak's layout and 400-char truncation."""
    lines = []
    for i, e in enumerate(errors, 1):
        lines.append(
            f"""ERROR {i}:
- Category: {e['category']} / {e['subcategory']}
- What was changed: {e['description']}
- Original text (before modification): {(e.get('original_snippet') or '')[:400]}
- Modified text (what's in the paper now): {(e.get('modified_snippet') or '')[:400]}
""")
    return "\n".join(lines)


def render_finding(f: dict) -> str:
    """FMA's findings-v2 row in the shape Litvak's judge expects.

    `reported`/`computed`/`inputs` are included because that is where a tool
    finding's numbers live; his `IssueFinding` had nowhere to put them and our
    first scorer left them out of the blob entirely.
    """
    def obj(k):
        v = f.get(k)
        return json.dumps(v, default=str)[:300] if isinstance(v, (dict, list)) else ""
    return f"""- Category: {f.get('technique') or 'not specified'}
- Subcategory: {f.get('slug') or 'not specified'}
- Description: {(str(f.get('title') or '') + '. ' + str(f.get('description') or ''))[:600]}
- Quote from paper: {(f.get('quote') or 'none provided')[:400]}
- Location: {f.get('location') or 'not specified'}
- Values reported in the paper: {obj('reported') or 'not specified'}
- Values this check computed: {obj('computed') or 'not specified'}"""


def cache_key(paper: int, finding: dict) -> str:
    """Stable across processes, and invalidated by a prompt change.

    Litvak's key is `hash((desc[:150], quote[:150]))`. `hash()` on a str is
    salted per process unless PYTHONHASHSEED is pinned, so his cache silently
    misses on every restart.
    """
    payload = json.dumps({"p": paper, "f": render_finding(finding)}, sort_keys=True)
    digest = hashlib.sha256(
        (JUDGE_PROMPT_VERSION + "|" + JUDGE_SYSTEM + "|" + payload).encode()
    ).hexdigest()
    return f"{JUDGE_PROMPT_VERSION}|{paper}|{digest[:32]}"


def judge_argv(system: str, model: str,
               schema: Optional[dict] = None) -> list[str]:
    """Modelled on `llm_backend._build_claude_invocation`, the argv this repo
    actually runs in production -- NOT on `tools/copy_move_adjudicate.py`.

    NO `--bare`. That flag was copied here from `copy_move_adjudicate`, whose
    own docstring says it is "Not wired into analyze_paper_images" -- so its
    argv had almost certainly never been run against the live CLI. `--bare`
    skips the config directory, and with it the OAuth credentials, so every
    call returned `Not logged in - Please run /login` on a machine that was
    perfectly well logged in. MEASURED 2026-08-23: `claude -p` answers, `claude
    -p --bare` does not, with nothing else changed.

    That mistake cost a whole scoring run and produced a confident diagnosis
    ("the daemon needs a re-login") about an environment that was fine. The
    lesson is the repo's own: an invocation nobody has run is not a pattern,
    it is a draft.

    `--append-system-prompt` rather than `--system-prompt`, matching the live
    builder. `--tools ""` and an empty `--allowedTools` disable the built-ins:
    the judge reads two blocks of text and returns a number, so any tool call
    is a defect.
    """
    return [
        "claude",
        "-p",
        "--model", model,
        "--effort", "low",
        "--allowedTools", "",
        "--tools", "",
        "--disallowedTools",
        "Bash Edit Write Read NotebookEdit WebFetch WebSearch Task Agent",
        "--append-system-prompt", system,
        "--permission-mode", "bypassPermissions",
        "--output-format", "json",
        "--json-schema", json.dumps(schema or JUDGE_SCHEMA),
        # NOT 1. `--json-schema` is served by a StructuredOutput TOOL CALL, so
        # a model that answers in prose first needs a second turn to emit it.
        # At 1 the run died with `subtype: error_max_turns` on every finding
        # whose system prompt was long enough to draw a prose answer -- and it
        # was still BILLED for the turns it took.
        "--max-turns", "4",
    ]


class JudgeError(RuntimeError):
    """The judge could not answer. NOT the same fact as 'no match'."""


class JudgeUnavailable(JudgeError):
    """An ENVIRONMENT fault that every later call will hit too.

    Not logged in, no CLI, no credit. Retrying 206 times produces 206 identical
    messages and one useless report; the first occurrence aborts the run and
    names the fix instead. Distinct from a per-call JudgeError, which really is
    worth recording per finding.
    """


#: Substrings in the CLI's own error text that mean "do not bother retrying".
_FATAL_JUDGE_ERRORS = ("not logged in", "please run /login", "invalid api key",
                       "authentication", "credit balance", "quota")


def _parse_judge(stdout: str) -> Optional[int]:
    """`error_number` out of the CLI's JSON envelope, or raise.

    The envelope's own `is_error` is checked FIRST. Without it a failed call
    surfaced as `claude exited 1:` with an empty stderr -- the CLI puts its
    reason in `result` and exits cleanly-ish -- so a whole scoring run reported
    206 identical blank errors instead of one line saying "Not logged in".
    """
    try:
        env = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise JudgeError(f"CLI stdout was not JSON: {exc}") from exc
    if isinstance(env, dict) and env.get("is_error"):
        # `subtype` and `terminal_reason` are included because `result` is NULL
        # for a max-turns abort, and reporting that as "unknown" is what turned
        # a one-line fix into a debugging session.
        why = str(env.get("result") or env.get("api_error_status")
                  or env.get("subtype") or env.get("terminal_reason") or "unknown")
        if any(k in why.lower() for k in _FATAL_JUDGE_ERRORS):
            raise JudgeUnavailable(why)
        raise JudgeError(f"claude reported an error: {why[:200]} "
                         f"(subtype={env.get('subtype')}, "
                         f"terminal_reason={env.get('terminal_reason')})")
    # `structured_output` is the canonical home of a --json-schema answer;
    # `result` carries the same object as a JSON STRING. Prefer the parsed one.
    if isinstance(env, dict) and isinstance(env.get("structured_output"), dict):
        payload = env["structured_output"]
    else:
        payload = env.get("result", env) if isinstance(env, dict) else env
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise JudgeError(f"result was not JSON: {exc}") from exc
    if not isinstance(payload, dict) or "error_number" not in payload:
        raise JudgeError(f"no error_number in judge reply: {str(payload)[:200]}")
    n = payload["error_number"]
    if n is None:
        return None
    if isinstance(n, int) and 1 <= n <= 10:
        return n
    raise JudgeError(f"error_number out of range: {n!r}")


async def judge_one(system: str, prompt: str, model: str, timeout: int,
                    run_cli: Optional[Callable] = None,
                    schema: Optional[dict] = None,
                    parse: Optional[Callable] = None):
    """One judge call. Raises JudgeError rather than returning 'no match'.

    Litvak's `except Exception: result = "none"` scores a transport failure as
    a miss -- our fault rendered as the system's, which is the reading error
    this whole toolkit exists to prevent. Callers record `judge_error` and
    count it separately.
    """
    parse = parse or _parse_judge
    if run_cli is not None:
        return parse(run_cli(judge_argv(system, model, schema), prompt))
    binary = shutil.which("claude")
    if not binary:
        raise JudgeUnavailable("claude CLI is not on PATH")
    argv = [binary] + judge_argv(system, model, schema)[1:]
    proc = await asyncio.create_subprocess_exec(
        *argv, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(
            proc.communicate(prompt.encode()), timeout=timeout)
    except asyncio.TimeoutError as exc:
        proc.kill()
        raise JudgeError(f"judge timed out after {timeout}s") from exc
    stdout = out.decode("utf-8", "replace")
    # STDOUT FIRST, exit code second. The CLI reports "Not logged in" inside the
    # JSON envelope on stdout and leaves stderr EMPTY, so raising on the exit
    # code produced 206 copies of `claude exited 1:` with no reason attached --
    # the diagnostic that would have taken one line to act on, discarded in
    # favour of the one that could not be acted on at all.
    if stdout.strip():
        return parse(stdout)
    if proc.returncode != 0:
        raise JudgeError(f"claude exited {proc.returncode}: "
                         f"{err.decode('utf-8','replace')[:200] or 'no output'}")
    return parse(stdout)


def _judge_prompt(f: dict) -> str:
    return ("Now evaluate this reviewer finding:\n\nFINDING:\n"
            + render_finding(f)
            + "\n\nWhich error number (1-10) does this finding match, if any?")


def _system_for(errors: list[dict]) -> str:
    """The ten-error block goes in the SYSTEM prompt, not the user turn.

    Litvak's API call pins `cache_control: ephemeral` on it; the CLI manages
    caching itself and gives us no such handle, so putting the constant part in
    the system prompt is how the automatic prefix cache gets a chance to cover
    it.
    """
    return (JUDGE_SYSTEM
            + "\n\nHere are the 10 known errors inserted into this paper:\n\n"
            + errors_block(errors))


async def _judge_call(paper: int, idx: int, f: dict, system: str, *, model: str,
                      timeout: int, cache: dict, sem: asyncio.Semaphore,
                      retries: int, run_cli, on_done,
                      cached_only: bool = False) -> tuple[int, object]:
    """One finding, judged. Cache hit costs nothing and never takes a slot."""
    key = cache_key(paper, f)
    v = cache.get(key)
    if v is not None and v != "error":
        return idx, (None if v == "none" else int(v))

    if cached_only:
        # An uncached finding is NOT "no match" -- it is a question we never
        # asked. Returning "none" here would quietly shrink the numerator and
        # report a partial run as a complete one.
        return idx, "uncached"

    last: Optional[JudgeError] = None
    for attempt in range(retries + 1):
        async with sem:
            try:
                n = await judge_one(system, _judge_prompt(f), model, timeout, run_cli)
                cache[key] = "none" if n is None else str(n)
                if on_done:
                    on_done(True)
                return idx, n
            except JudgeUnavailable:
                raise                    # fatal; collected by the gather
            except JudgeError as exc:
                last = exc
        # RETRY OUTSIDE THE SEMAPHORE, so a backing-off call does not hold a
        # slot that a healthy call could use. Concurrency makes transient
        # failures likelier, and losing a judgement to one would silently
        # shrink the numerator.
        if attempt < retries:
            await asyncio.sleep(1.5 * (attempt + 1))
    print(f"    judge_error p{paper} finding {idx} after {retries + 1} "
          f"attempt(s): {last}", file=sys.stderr, flush=True)
    # NOT cached. A transport failure is a fact about the environment at this
    # moment, not about the finding, and caching it meant a fixed login still
    # replayed the old errors forever.
    if on_done:
        on_done(False)
    return idx, "error"


def _assign(errors: list[dict], findings: list[dict],
            results: list) -> tuple[dict[int, dict], int]:
    """First-claim-wins, and count the calls that failed."""
    claimed: dict[int, dict] = {}
    n_err = 0
    for idx, n in sorted(results, key=lambda r: r[0]):
        if n == "uncached":
            continue                 # never asked; counted by the caller
        if n == "error":
            n_err += 1
            continue
        if not isinstance(n, int):
            continue
        eidx = n - 1
        if 0 <= eidx < len(errors) and eidx not in claimed:
            claimed[eidx] = {"how": "judge",
                             "id": findings[idx].get("finding_id"),
                             "finding_index": idx}
    return claimed, n_err


async def _settle(coros):
    """gather, then re-raise -- fatal faults first.

    `return_exceptions=True` so a fatal fault does not propagate while sibling
    subprocesses are still draining: that orphaned the remaining `claude`
    processes and hung the run instead of ending it. Shared by the judge and
    the verifier so there is one pool discipline, not two.
    """
    out = await asyncio.gather(*coros, return_exceptions=True)
    fatal = next((r for r in out if isinstance(r, JudgeUnavailable)), None)
    if fatal is not None:
        raise fatal
    for r in out:
        if isinstance(r, BaseException):
            raise r
    return out


async def judge_corpus(jobs: list[tuple[int, list[dict], list[dict]]], *,
                       model: str, timeout: int, concurrency: int, cache: dict,
                       retries: int = 2, run_cli=None, on_paper_done=None,
                       on_call_done=None, cached_only: bool = False
                       ) -> dict[int, tuple[dict, int]]:
    """Every finding of every paper, under ONE shared semaphore.

    Papers used to be judged one after another, each with its own semaphore, so
    the concurrency limit was really a per-paper limit: a 14-finding paper could
    never fill more than 14 slots and the tail of every paper ran the pool down
    to one. Across ten papers that is most of the wall clock spent waiting on a
    handful of stragglers. One global pool keeps every slot busy until the whole
    corpus is done.

    The cache is a plain dict mutated from coroutines on a single event loop,
    with no await between read and write, so it needs no lock.
    """
    sem = asyncio.Semaphore(concurrency)

    async def one_paper(paper: int, errors: list[dict], findings: list[dict]):
        system = _system_for(errors)
        settled = await _settle(
            _judge_call(paper, i, f, system, model=model, timeout=timeout,
                        cache=cache, sem=sem, retries=retries, run_cli=run_cli,
                        on_done=on_call_done, cached_only=cached_only)
            for i, f in enumerate(findings))
        out = _assign(errors, findings, settled)
        if on_paper_done:
            on_paper_done(paper, out)
        return paper, out

    done = await _settle(one_paper(*j) for j in jobs)
    return {paper: res for paper, res in done}


async def judge_paper(paper: int, errors: list[dict], findings: list[dict],
                      *, model: str, timeout: int, concurrency: int,
                      cache: dict, retries: int = 2,
                      run_cli=None) -> tuple[dict[int, dict], int]:
    """One paper. Thin wrapper over `judge_corpus` -- same protocol, one job."""
    got = await judge_corpus([(paper, errors, findings)], model=model,
                             timeout=timeout, concurrency=concurrency,
                             cache=cache, retries=retries, run_cli=run_cli)
    return got[paper]


# --------------------------------------------------------------------------
# VERIFICATION PASS -- per ERROR, not per finding
# --------------------------------------------------------------------------
#
# The judge above is Litvak's protocol verbatim: one call per finding, asking
# "does this finding match any of these ten errors". That is what makes our
# number comparable to his fourteen, and it stays. But it has two measured
# failure modes on this corpus:
#
#   FALSE POSITIVE. p8 `directionality_changed` (a power calculation flipped
#   from non-directional to directional) was credited to a finding about
#   MULTIPLICITY -- "four co-primary indices and six pairwise comparisons with
#   no multiplicity plan". Same section of the paper, different defect.
#
#   FALSE NEGATIVE. p9 `analysis_count_inconsistent` (10 analyses changed to 8)
#   was scored a miss although TWO findings said "8 moderation analyses claimed
#   but 7 behaviors enumerated". Judged one at a time, in isolation, each looked
#   like a near miss; seen together they are plainly the planted defect.
#
# And it is NOT DETERMINISTIC: re-judging the p8 finding returned `none` where
# the run had returned `5`, same model, same prompt.
#
# This pass answers the inverted question -- one call per ERROR, shown every
# `problem` finding from that paper at once -- and REQUIRES A VERBATIM QUOTE
# from the finding it credits. The quote is checked in code against the
# finding's own text. A model cannot produce a quote about directionality from
# a finding about multiplicity, so the grounding requirement is what kills the
# false positive, and seeing all candidates together is what recovers the false
# negative.

VERIFY_SYSTEM = """You are verifying whether an AI reviewer caught a specific error that was deliberately planted in a scientific paper.

You will be given ONE planted error -- the original text, the modified text that replaced it, and a description of what was changed -- followed by EVERY problem the reviewer reported for that paper.

Decide whether any single reported problem identifies THIS SPECIFIC DEFECT.

A match requires the reviewer to have noticed the actual thing that was changed. It is NOT a match if the reviewer merely:
- discussed the same section, table, or analysis
- raised a different problem that happens to sit in the same paragraph
- criticised the same statistic for an unrelated reason

The reviewer need not use the same words, and need not know the original value. They must have identified the defect.

If a reported problem does match, you MUST quote, VERBATIM and from that problem's own text, the words that identify the defect. Copy them exactly; do not paraphrase, do not compose, do not quote from the planted error. If you cannot find such words to copy, it is not a match.

When in doubt, answer no match."""

VERIFY_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["finding_index", "evidence_quote"],
    "properties": {
        "finding_index": {
            "type": ["integer", "null"],
            "description": "Index of the matching reported problem, or null.",
        },
        "evidence_quote": {
            "type": ["string", "null"],
            "description": "Verbatim words COPIED from that problem's text "
                           "that identify the defect. Null when no match.",
        },
    },
}


def render_for_verify(i: int, f: dict) -> str:
    """One finding, in the SAME field set whoever produced it.

    NORMALISED ON PURPOSE, and it costs us something. FMA findings carry a
    crafted one-clause `title`; the systems in Litvak's benchmark do not. Show
    the verifier a title for our findings and nothing for theirs and we have
    handed ourselves an advantage inside the very instrument built to remove
    one -- a better-summarised finding is easier to match.

    So the title is DROPPED from the verifier's view rather than synthesised
    for theirs: inventing a title from a subcategory slug would put words in
    their systems' mouths that they never wrote. Removing ours is the
    conservative direction.

    Consequence, which is not optional: FMA's verified 42 was computed with the
    title visible, so it is not comparable to anything produced under this
    renderer and has to be recomputed. `VERIFY_PROMPT_VERSION` is bumped so the
    cache cannot answer the old question with the new one.
    """
    return (f"[{i}] {f.get('technique') or 'uncategorised'}"
            f" / {f.get('slug') or 'unspecified'}\n"
            f"    {str(f.get('description') or '')[:500]}\n"
            f"    quote from paper: {str(f.get('quote') or 'none')[:220]}\n"
            f"    location: {f.get('location') or 'not specified'}")


def verify_prompt(gt: dict, findings: list[dict]) -> str:
    lines = [f"""PLANTED ERROR
- Category: {gt['category']} / {gt['subcategory']}
- What was changed: {gt['description']}
- Original text: {(gt.get('original_snippet') or '(deleted text was removed entirely)')[:500]}
- Modified text now in the paper: {(gt.get('modified_snippet') or '(nothing -- the text was DELETED)')[:500]}

REPORTED PROBLEMS ({len(findings)}):"""]
    for i, f in enumerate(findings):
        lines.append(render_for_verify(i, f))
    lines.append("\nDid any reported problem identify this specific planted "
                 "defect? Give its index and a verbatim quote from ITS text, "
                 "or null.")
    return "\n".join(lines)


def _parse_verify(stdout: str) -> tuple[Optional[int], Optional[str]]:
    env = json.loads(stdout) if stdout.strip() else {}
    if isinstance(env, dict) and env.get("is_error"):
        why = str(env.get("result") or env.get("subtype")
                  or env.get("terminal_reason") or "unknown")
        if any(k in why.lower() for k in _FATAL_JUDGE_ERRORS):
            raise JudgeUnavailable(why)
        raise JudgeError(f"verifier error: {why[:200]}")
    payload = env.get("structured_output") if isinstance(env, dict) else None
    if not isinstance(payload, dict):
        raw = env.get("result") if isinstance(env, dict) else env
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError as exc:
            raise JudgeError(f"verifier reply was not JSON: {exc}") from exc
    if not isinstance(payload, dict) or "finding_index" not in payload:
        raise JudgeError(f"no finding_index in verifier reply: {str(payload)[:160]}")
    return payload.get("finding_index"), payload.get("evidence_quote")


def quote_is_grounded(quote: Optional[str], finding: dict) -> bool:
    """Is the quote actually IN the finding it was offered for?

    Checked in code, never taken on trust. This is the whole point of asking
    for a quote: a model cannot copy words about directionality out of a
    finding about multiplicity, so an ungrounded quote is a refused match
    rather than a credited one. Normalised the same way the floor matcher
    normalises, so a curly quote or a collapsed space is not a rejection.
    """
    if not quote or not quote.strip():
        return False
    q = _norm(quote)
    if len(q) < 12:            # too short to be evidence of anything
        return False
    return q in _norm(finding_blob(finding))


def verify_cache_key(paper: int, gt: dict, findings: list[dict]) -> str:
    payload = json.dumps({"p": paper, "sub": gt["subcategory"],
                          "f": [render_finding(f) for f in findings]},
                         sort_keys=True)
    digest = hashlib.sha256(
        (VERIFY_PROMPT_VERSION + "|" + VERIFY_SYSTEM + "|" + payload).encode()
    ).hexdigest()
    return f"V{VERIFY_PROMPT_VERSION}|{paper}|{gt['subcategory']}|{digest[:32]}"


async def _verify_one(paper: int, gt: dict, findings: list[dict], *, model: str,
                      timeout: int, cache: dict, sem: asyncio.Semaphore,
                      retries: int, run_cli, on_done, cached_only: bool):
    key = verify_cache_key(paper, gt, findings)
    hit = cache.get(key)
    if isinstance(hit, dict):
        return (paper, gt["subcategory"]), hit
    if cached_only:
        return (paper, gt["subcategory"]), {"state": "uncached"}

    last: Optional[JudgeError] = None
    for attempt in range(retries + 1):
        async with sem:
            try:
                idx, quote = await judge_one(
                    VERIFY_SYSTEM, verify_prompt(gt, findings), model, timeout,
                    run_cli, schema=VERIFY_SCHEMA, parse=_parse_verify)
                if idx is None or not (0 <= idx < len(findings)):
                    rec = {"state": "no_match"}
                elif quote_is_grounded(quote, findings[idx]):
                    rec = {"state": "match", "finding_index": idx,
                           "quote": quote,
                           "finding_id": findings[idx].get("finding_id")}
                else:
                    # Claimed a match it could not quote. Reported, not silently
                    # downgraded: an ungrounded claim is evidence about the
                    # verifier, and it is the signature of the p8 failure.
                    rec = {"state": "ungrounded", "finding_index": idx,
                           "quote": quote,
                           "finding_id": findings[idx].get("finding_id")}
                cache[key] = rec
                if on_done:
                    on_done(True)
                return (paper, gt["subcategory"]), rec
            except JudgeUnavailable:
                raise
            except JudgeError as exc:
                last = exc
        if attempt < retries:
            await asyncio.sleep(1.5 * (attempt + 1))
    print(f"    verify_error p{paper} {gt['subcategory']}: {last}",
          file=sys.stderr, flush=True)
    if on_done:
        on_done(False)
    return (paper, gt["subcategory"]), {"state": "error", "reason": str(last)}


async def verify_corpus(jobs, *, model: str, timeout: int, concurrency: int,
                        cache: dict, retries: int = 2, run_cli=None,
                        on_call_done=None, cached_only: bool = False) -> dict:
    """One call per ERROR, every error of every paper under ONE semaphore.

    `jobs` is [(paper, [gt_row, ...], [finding, ...])]. Same pool discipline as
    `judge_corpus` -- shared semaphore across the corpus, retries backing off
    outside the slot, `_settle` for fatal faults. A per-paper pool here would
    repeat the defect fixed earlier today, where a paper with few items could
    never fill the slots and every paper's tail ran the pool down to one.
    """
    sem = asyncio.Semaphore(concurrency)
    tasks = [
        _verify_one(paper, gt, findings, model=model, timeout=timeout,
                    cache=cache, sem=sem, retries=retries, run_cli=run_cli,
                    on_done=on_call_done, cached_only=cached_only)
        for paper, gts, findings in jobs for gt in gts
    ]
    return dict(await _settle(tasks))


def load_cache() -> dict:
    if CACHE_PATH.is_file():
        try:
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: dict) -> None:
    """Write atomically: temp file in the same directory, then `os.replace`.

    A plain `write_text` truncates before it writes, so anything reading the
    cache while a run is mid-save gets a half-written file and a JSONDecodeError
    -- and `load_cache` swallows that into an empty dict, which would silently
    re-pay for every judgement already bought. `os.replace` is atomic on POSIX
    and Windows, so a reader sees either the old file or the new one.
    """
    tmp = CACHE_PATH.with_suffix(CACHE_PATH.suffix + f".tmp{os.getpid()}")
    tmp.write_text(json.dumps(cache, indent=0, sort_keys=True), encoding="utf-8")
    os.replace(tmp, CACHE_PATH)


# --------------------------------------------------------------------------
# reporting
# --------------------------------------------------------------------------

def hms(seconds: float) -> str:
    """`4m 12s`. Seconds alone stop being readable somewhere around a minute."""
    seconds = max(0.0, seconds)
    if seconds < 60:
        return f"{seconds:.1f}s"
    m, sec = divmod(int(round(seconds)), 60)
    if m < 60:
        return f"{m}m {sec:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {sec:02d}s"


def commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                              capture_output=True, text=True,
                              cwd=REPO_ROOT).stdout.strip() or "unknown"
    except Exception:
        return "unknown"


def _bar(n: int, of: int, width: int = 10) -> str:
    filled = 0 if of == 0 else round(width * n / of)
    return "#" * filled + "." * (width - filled)


def litvak_ceiling(a, papers) -> Optional[dict]:
    """What Litvak's systems achieved on THESE papers, from his stored results.

    Recomputed on the scored subset rather than quoted from his published /100,
    so the two share a denominator. Returns None when the upstream results are
    not present -- an absent comparison is reported as absent, never as zero.
    """
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import compare as _c                                  # noqa: PLC0415
        bench = resolve_bench(a.bench)
        lit = _c.load_litvak(bench)
    except Exception:                                          # noqa: BLE001
        return None
    if not lit:
        return None
    rows = [r for r in ground_truth(bench) if r["paper"] in papers]
    keys = [(r["paper"], r["subcategory"]) for r in rows]
    caught_by_any = {k: any(t.get(k, False) for t in lit.values()) for k in keys}
    per_system = {name: sum(1 for k in keys if t.get(k, False))
                  for name, t in lit.items()}
    best_name = max(per_system, key=lambda n: per_system[n])
    by_cat = Counter()
    for r in rows:
        if caught_by_any[(r["paper"], r["subcategory"])]:
            by_cat[r["category"]] += 1
    return {
        "union": sum(1 for k in keys if caught_by_any[k]),
        "best": per_system[best_name],
        "best_name": best_name,
        "n_systems": len(lit),
        "caught_by_any": caught_by_any,
        "per_system": per_system,
        "by_category": by_cat,
    }


def print_category_table(hits_by_cat: Counter, totals: Counter,
                         ceiling: Optional[dict] = None) -> None:
    """Hits per category, beside what the whole field managed.

    The `ceiling` column is what makes a low row readable: 3 of 10 next to a
    ceiling of 10 is our weakness, 3 of 10 next to a ceiling of 4 is the
    benchmark's hard tail. Without it every low row looks the same.
    """
    by_cat_ceiling: Counter = (ceiling or {}).get("by_category") or Counter()
    print("BY CATEGORY")
    if ceiling:
        print("  `field` = how many of that category ANY of Litvak's systems "
              "caught, so a low")
        print("  row reads as our weakness or as the benchmark's hard tail, not "
              "ambiguously.\n")
    hdr = f"  {'category':<24} {'hits':>4} {'of':>3}  {'':<10}"
    if ceiling:
        hdr += "  field"
    print(hdr)
    for cat in sorted(totals):
        n, of = hits_by_cat[cat], totals[cat]
        line = f"  {cat:<24} {n:>4} {of:>3}  {_bar(n, of)}"
        if ceiling:
            line += f"  {by_cat_ceiling.get(cat, 0):>5}"
        print(line)
    print(f"  {'-' * 24} {'-' * 4} {'-' * 3}")
    tot_line = (f"  {'TOTAL':<24} {sum(hits_by_cat.values()):>4} "
                f"{sum(totals.values()):>3}  "
                f"{_bar(sum(hits_by_cat.values()), sum(totals.values()))}")
    if ceiling:
        tot_line += f"  {sum(by_cat_ceiling.values()):>5}"
    print(tot_line)
    print()


def run_backend_model(a, per_paper) -> tuple[str, str]:
    """Which engine produced the findings being scored.

    From the run's own stage metadata, not from `runs.model`, which is NULL for
    every row the batch runner pushes. Falls back to the corpus name rather
    than guessing "claude": a mislabelled row in a published table is worse
    than an unlabelled one.
    """
    for info in per_paper.values():
        meta = (info.get("db_meta") or {}).get("meta") or {}
        stages = meta.get("stages") or {}
        for st in stages.values():
            if isinstance(st, dict) and st.get("models_resolved"):
                billed = st.get("primary_billed_model")
                return (str(meta.get("llm_backend") or "?"),
                        str(billed or meta.get("model") or "?"))
        if meta.get("model"):
            return str(meta.get("llm_backend") or "?"), str(meta["model"])
    return "?", "?"


def print_provenance_caveat(a, per_paper) -> None:
    """What we actually know about the input, not what we assume.

    This block used to hardcode "we convert .docx with a layout-preserving
    converter" and "verify_tables.py found 5 of 10 papers damaged" -- both facts
    about OUR local LibreOffice conversion, printed under whatever corpus was
    being scored, including one built on another machine by another person. A
    caveat that states someone else's situation as fact is worse than no caveat,
    so an unestablished converter is now named as unestablished.
    """
    conv = None
    if not a.from_db and a.run_dir:
        meta = a.run_dir / "prepare_meta.json"
        if meta.is_file():
            try:
                conv = json.loads(meta.read_text()).get("converter_description")
            except Exception:                                  # noqa: BLE001
                conv = None

    print("\nINPUT PROVENANCE")
    if conv:
        print(f"  converter : {conv}  (from prepare_meta.json)")
    else:
        print("  converter : UNVERIFIED for this corpus.")
        print("              No prepare_meta.json was read, so how these papers")
        print("              were produced from the .docx originals is not")
        print("              established here. It matters: Litvak's systems read")
        print("              the flattened text PDF from `docx_to_pdf.py`, and a")
        print("              layout-preserving conversion favours us on every")
        print("              table-bound check. Establish it before publishing.")
    print("  tables    : run `verify_tables.py <corpus>` to measure whether the")
    print("              column structure survived. Not run automatically -- it")
    print("              needs a warm docling cache and the .docx originals.")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir", type=Path, nargs="?", default=None,
                    help="Corpus root: the directory of litvakNN paper dirs")
    ap.add_argument("--from-db", metavar="CORPUS", default=None,
                    help="Score a run pushed to the findings database instead of local files "
                         "(e.g. --from-db modified). Needs METASCIENCE_DB_URL.")
    ap.add_argument("--db-url", default=None)
    ap.add_argument("--json", type=Path, default=None)
    add_bench_arg(ap)
    ap.add_argument("--control", action="store_true",
                    help="Score the CLEAN originals: count flags, not recall")
    ap.add_argument("--no-judge", action="store_true",
                    help="Deterministic floor only; no model calls, no spend")
    ap.add_argument("--all-runs", action="store_true",
                    help="Pool every forensic_review_* sibling (default: newest only)")
    ap.add_argument("--include-quarantined", action="store_true")
    ap.add_argument("--model", default=JUDGE_MODEL)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--concurrency", type=int, default=10,
                    help="Judge calls in flight ACROSS THE WHOLE CORPUS "
                         "(default 10). Each is a `claude` subprocess at "
                         "~600 MB, so this is bounded by RAM, not CPU.")
    ap.add_argument("--cached-only", action="store_true",
                    help="Judge using ONLY answers already in the cache; make "
                         "no calls and spend nothing. Findings with no cached "
                         "judgement are reported as uncovered rather than "
                         "silently counted as 'no match'.")
    ap.add_argument("--retries", type=int, default=2,
                    help="Retries per judge call on a transient error. "
                         "Concurrency makes those likelier, and losing a "
                         "judgement to one silently shrinks the numerator.")
    ap.add_argument("--verify-model", default=VERIFY_MODEL,
                    help=f"Model for the per-error verification pass "
                         f"(default {VERIFY_MODEL}). It sees a whole paper's "
                         f"findings at once and its answer is the one reported.")
    ap.add_argument("--no-record", action="store_true",
                    help="Do not append this run to results.json.")
    ap.add_argument("--no-verify", action="store_true",
                    help="Skip verification; report the Litvak-protocol number "
                         "alone. Faster and cheaper, and measurably noisier.")
    ap.add_argument("--full-100", action="store_true",
                    help="Accepted and ignored. All 100 errors are always "
                         "scored now; the flag existed when the headline was "
                         "20 of 100.")
    a = ap.parse_args()

    try:
        bench = resolve_bench(a.bench)
    except BenchmarkNotFound as exc:
        print(exc, file=sys.stderr)
        return 1
    if not a.from_db and (a.run_dir is None or not a.run_dir.is_dir()):
        print(f"not a directory: {a.run_dir}  (or pass --from-db CORPUS)",
              file=sys.stderr)
        return 1

    rows = ground_truth(bench)
    by_paper: dict[int, list[dict]] = defaultdict(list)
    for r in rows:
        by_paper[r["paper"]].append(r)

    db_findings: dict[int, list[dict]] = {}
    db_meta: dict[int, dict] = {}
    if a.from_db:
        db_findings, db_meta = load_findings_from_db(a.from_db, a.db_url)
        paper_dirs = [Path(db_meta[n]["dir"]) for n in sorted(db_findings)]
    else:
        paper_dirs = sorted((p for p in a.run_dir.iterdir()
                             if p.is_dir() and paper_dir_number(p) is not None),
                            key=lambda p: paper_dir_number(p))
        if not paper_dirs:
            print(f"no litvakNN paper directories under {a.run_dir}",
                  file=sys.stderr)
            return 1

    cache = load_cache()
    per_paper: dict[int, dict] = {}
    missing_runs: list[str] = []
    n_calls = n_cached = 0
    t_start = time.monotonic()
    judge_seconds = 0.0
    verify_seconds = 0.0
    v_calls = 0
    verified: dict = {}


    # PASS 1 -- gather every paper's findings. No model calls here, so the
    # whole corpus is known before the first one is spent.
    jobs: list[tuple[int, list[dict], list[dict]]] = []
    for pd in paper_dirs:
        n = paper_dir_number(pd)
        if a.from_db:
            findings = db_findings.get(n) or []
            used = [db_meta[n]["run_uid"]] if n in db_meta else []
        else:
            findings, used = load_findings(pd, a.all_runs)
        if not used:
            missing_runs.append(pd.name)
        split = split_by_outcome(findings)
        cands = candidates(findings, a.include_quarantined)
        per_paper[n] = {
            "dir": pd.name, "run": [str(u) for u in used],
            "n_findings": len(findings),
            "n_problem": len(split["problem"]),
            "n_pass": len(split["pass"]),
            "n_undecided": len(split["undecided"]),
            "n_quarantined": len(split["quarantined"]),
            "n_candidates": len(cands),
            "cands": cands,
            "db_meta": db_meta.get(n) if a.from_db else None,
            "floor": {} if a.control else assign_floor(by_paper[n], cands),
            "judged": {}, "judge_errors": 0,
        }
        if not a.control and not a.no_judge and cands:
            jobs.append((n, by_paper[n], cands))

    # PASS 2 -- judge the WHOLE CORPUS in one pool.
    if jobs:
        todo = sum(1 for n, _e, cs in jobs
                   for c in cs if cache_key(n, c) not in cache)
        print(f"  {todo} judge call(s) to make across {len(jobs)} paper(s) "
              f"at concurrency {a.concurrency}; the rest are cached. Ctrl-C is "
              f"safe -- the cache is written as papers finish.",
              file=sys.stderr, flush=True)
        for n, _e, cs in jobs:
            info = per_paper[n]
            cached_n = sum(1 for c in cs if cache_key(n, c) in cache)
            # Say WHICH 16 of 27, not just "16 finding(s)". The bare count reads
            # as "this paper produced 16 findings" when it produced 27 and 16
            # are eligible -- an unexplained denominator is the defect class
            # this whole harness exists to catch.
            print(f"    {info['dir']}: {len(cs)} of {info['n_findings']} "
                  f"eligible (problem only; {info['n_pass']} pass, "
                  f"{info['n_undecided']} undecided excluded), "
                  f"{cached_n} cached", file=sys.stderr, flush=True)

        t_judge = time.monotonic()
        done_calls = [0]

        def _on_call(ok: bool):
            done_calls[0] += 1
            k = done_calls[0]
            if k % 10 and k != todo:
                return
            el = time.monotonic() - t_judge
            rate = el / k
            left = max(0, todo - k)
            print(f"    {k}/{todo} calls  [{hms(el)}, {rate:.1f}s/call"
                  + (f", ~{hms(left * rate)} left" if left else "")
                  + "]", file=sys.stderr, flush=True)

        def _on_paper(paper: int, res):
            claimed, jerr = res
            per_paper[paper]["judged"] = claimed
            per_paper[paper]["judge_errors"] = jerr
            save_cache(cache)          # a finished paper is never re-paid for
            print(f"    done {per_paper[paper]['dir']}: {len(claimed)} claimed"
                  + (f", {jerr} error(s)" if jerr else ""),
                  file=sys.stderr, flush=True)

        try:
            asyncio.run(judge_corpus(
                jobs, model=a.model, timeout=a.timeout,
                concurrency=a.concurrency, cache=cache, retries=a.retries,
                run_cli=None, on_paper_done=_on_paper, on_call_done=_on_call,
                cached_only=a.cached_only))
        except JudgeUnavailable as exc:
            save_cache(cache)
            print(f"\nJUDGE UNAVAILABLE: {exc}", file=sys.stderr)
            print("Every remaining call would fail the same way, so the run "
                  "is stopped rather than\nreporting 200 identical errors as "
                  "if they were findings about the papers.\n"
                  "Fix the environment and re-run -- everything judged so far "
                  "is cached -- or\npass --no-judge for the deterministic "
                  "floor, which needs no model at all.", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            save_cache(cache)
            print(f"\nINTERRUPTED. {done_calls[0]} call(s) completed and cached; "
                  "re-run to resume.", file=sys.stderr)
            return 130
        save_cache(cache)
        judge_seconds = time.monotonic() - t_judge
        n_calls = done_calls[0]
        n_cached = sum(len(cs) for _n, _e, cs in jobs) - n_calls

    if jobs and not a.no_verify:
        vjobs = [(n, by_paper[n], cs) for n, _e, cs in jobs]
        v_todo = sum(1 for n, gts, cs in vjobs for g in gts
                     if not isinstance(cache.get(verify_cache_key(n, g, cs)), dict))
        print(f"  verifying {sum(len(g) for _n, g, _c in vjobs)} error(s) with "
              f"{a.verify_model}, {v_todo} call(s) to make, concurrency "
              f"{a.concurrency}", file=sys.stderr, flush=True)
        t_v = time.monotonic()
        v_done = [0]

        def _on_v(ok: bool):
            v_done[0] += 1
            k = v_done[0]
            if k % 10 and k != v_todo:
                return
            el = time.monotonic() - t_v
            rate = el / k
            print(f"    {k}/{v_todo} verified  [{hms(el)}, {rate:.1f}s/call"
                  + (f", ~{hms((v_todo - k) * rate)} left" if v_todo > k else "")
                  + "]", file=sys.stderr, flush=True)

        try:
            verified = asyncio.run(verify_corpus(
                vjobs, model=a.verify_model, timeout=a.timeout,
                concurrency=a.concurrency, cache=cache, retries=a.retries,
                run_cli=None, on_call_done=_on_v, cached_only=a.cached_only))
        except JudgeUnavailable as exc:
            save_cache(cache)
            print(f"\nVERIFIER UNAVAILABLE: {exc}", file=sys.stderr)
            return 2
        except KeyboardInterrupt:
            save_cache(cache)
            print(f"\nINTERRUPTED during verification. {v_done[0]} cached; "
                  "re-run to resume.", file=sys.stderr)
            return 130
        save_cache(cache)
        verify_seconds = time.monotonic() - t_v
        v_calls = v_done[0]

    print(f"run       : {a.from_db and f'db corpus {a.from_db!r}' or a.run_dir}")
    print(f"benchmark : {bench}")
    if a.from_db and db_meta:
        res, billed = db_models(next(iter(db_meta.values())))
        first = next(iter(db_meta.values()))
        pv = (first.get("meta") or {}).get("version")
        print(f"pipeline  : {pv}   models_resolved={res}  billed={billed}")
        print("            (`runs.model` is NULL for these rows; the model is "
              "read from the stage metadata)")
    print(f"commit    : {commit()}   <- every number below is a claim about THIS code")
    print(f"matcher   : floor(deterministic)"
          + ("" if a.no_judge or a.control else f" + judge({a.model} via claude CLI)"))
    if n_calls or n_cached:
        print(f"judge     : {n_calls} call(s) made, {n_cached} served from cache"
              f"  ({CACHE_PATH.name} -- a re-run costs nothing)")
        print(f"            {hms(judge_seconds)} judging"
              + (f", {judge_seconds / n_calls:.1f}s per call" if n_calls else ""))
    if v_calls:
        print(f"verifier  : {a.verify_model}, {v_calls} call(s), "
              f"{hms(verify_seconds)}, {verify_seconds / v_calls:.1f}s per call")
    if missing_runs:
        print(f"\n!! NO REVIEW OUTPUT in {len(missing_runs)} paper dir(s): "
              f"{', '.join(missing_runs)}")
        print("   These are UNANALYSED, not clean. They are excluded from every")
        print("   denominator below rather than scored zero.")

    scored = [n for n in per_paper if per_paper[n]["run"]]
    tot = {k: sum(per_paper[n][k] for n in scored)
           for k in ("n_findings", "n_problem", "n_pass", "n_undecided",
                     "n_quarantined", "n_candidates")}
    print(f"\nfindings  : {tot['n_findings']}  =  {tot['n_problem']} problem"
          f" / {tot['n_pass']} pass / {tot['n_undecided']} undecided"
          f"   ({tot['n_quarantined']} quarantined)")
    print(f"            {tot['n_candidates']} eligible to match "
          f"(`problem` only -- a `pass` is a check that RAN AND CLEARED the value,")
    print("            so counting one as a detection would score the benchmark backwards)")

    if a.control:
        rc = report_control(a, per_paper, scored, by_paper)
    else:
        rc = report_recall(a, per_paper, scored, by_paper, rows, verified,
                           {"judge_calls": n_calls, "judge_cache_hits": n_cached,
                            "verify_calls": v_calls,
                            "judge_seconds": judge_seconds,
                            "verify_seconds": verify_seconds})
    print(f"\nelapsed   : {hms(time.monotonic() - t_start)}"
          + (f"  ({hms(judge_seconds)} of it judging)" if judge_seconds else ""))
    return rc


def report_recall(a, per_paper, scored, by_paper, rows,
                  verified: Optional[dict] = None,
                  run_stats: Optional[dict] = None) -> int:
    # Passed in, not closed over: these are locals of `main`, and referencing
    # them here raised NameError on every --json run. Latent because the plain
    # report never touched them.
    run_stats = run_stats or {}
    use_judge = not a.no_judge
    hits_by_cat, totals = Counter(), Counter()
    hit_rows, miss_rows, disagree, unscoreable = [], [], [], []
    vdis: list = []
    caught: dict[tuple[int, str], bool] = {}
    caught_protocol: dict[tuple[int, str], bool] = {}

    for n in scored:
        info = per_paper[n]
        for i, r in enumerate(by_paper[n]):
            totals[r["category"]] += 1
            f_hit = info["floor"].get(i)
            f_ok = is_hit(f_hit)
            j_ok = i in info["judged"]
            v = (verified or {}).get((n, r["subcategory"]))
            v_ok = bool(v) and v.get("state") == "match"
            # THE VERIFIED ANSWER WINS when the pass ran. It sees every finding
            # for the paper at once and must quote the words that identify the
            # defect; the first pass sees one finding at a time and need not
            # ground its answer at all.
            got = v_ok if v else (j_ok if use_judge else f_ok)
            caught[(n, r["subcategory"])] = got
            # Litvak's protocol, kept SEPARATELY. Every comparison against his
            # fourteen systems must use this one: they were scored by the same
            # lenient per-finding haiku pass, and putting our strict verified
            # number beside their lenient one understates us by construction.
            caught_protocol[(n, r["subcategory"])] = j_ok if use_judge else f_ok
            if v and use_judge and v_ok != j_ok:
                vdis.append((r, "verifier only" if v_ok else "judge only",
                             v.get("state")))
            if f_hit and f_hit["how"] == "unscoreable_by_construction":
                unscoreable.append(r)
            if got:
                hits_by_cat[r["category"]] += 1
                hit_rows.append(r)
            else:
                miss_rows.append(r)
            if use_judge and f_ok != j_ok:
                disagree.append((r, "floor only" if f_ok else "judge only"))

    n_errors = sum(totals.values())
    n_hits = sum(hits_by_cat.values())
    pct = f"{100 * n_hits / n_errors:.0f}%" if n_errors else "n/a"
    ceiling = litvak_ceiling(a, scored)

    n_judge = sum(1 for n in scored for i, _r in enumerate(by_paper[n])
                  if i in per_paper[n]["judged"]) if use_judge else None
    label = "VERIFIED" if verified else "RECALL"
    print(f"\n{label} RECALL: {n_hits} of {n_errors}  ({pct})")
    if verified and n_judge is not None and n_judge != n_hits:
        print(f"  Litvak-protocol pass (per finding, {a.model}): {n_judge}.")
        print(f"  Verified pass (per error, {a.verify_model}, evidence quote "
              f"required and checked in code): {n_hits}.")
        print(f"  The two disagree on {len(vdis)} error(s), listed below. The "
              f"verified figure is the one to quote;")
        print(f"  the gap of {abs(n_hits - n_judge)} is the uncertainty in a "
              f"single-pass judge, not noise to average away.")
    if ceiling:
        print(f"  Litvak's {ceiling['n_systems']} systems on the same errors: "
              f"union {ceiling['union']}, best single {ceiling['best']} "
              f"({ceiling['best_name']}).")
        print(f"  The union is the empirical ceiling. The "
              f"{n_errors - ceiling['union']} error(s) no system caught are a "
              f"hard tail, not a scope boundary.")
    print()

    print_category_table(hits_by_cat, totals, ceiling)

    print("BY PAPER  (10 planted errors per paper)")
    for n in sorted(per_paper):
        info = per_paper[n]
        if not info["run"]:
            print(f"  litvak{n:02d}   --  NO RUN")
            continue
        got = sum(1 for i, _r in enumerate(by_paper[n])
                  if (i in info["judged"] if use_judge
                      else is_hit(info["floor"].get(i))))
        je = f"  judge_errors={info['judge_errors']}" if info["judge_errors"] else ""
        print(f"  litvak{n:02d}  {got:>2} of {len(by_paper[n])}   "
              f"findings={info['n_candidates']}{je}")

    tot_jerr = sum(per_paper[n]["judge_errors"] for n in scored)
    if tot_jerr:
        print(f"\n!! {tot_jerr} judge call(s) FAILED and are counted as errors, not")
        print("   as misses. A transport failure is our fault, not the system's.")

    if unscoreable:
        print(f"\nUNSCOREABLE BY THE FLOOR ({len(unscoreable)}): the planted error IS")
        print("   a deletion, so `modified_snippet` is empty -- no text to quote and")
        print("   no numbers to name. The judge scores these from the description;")
        print("   the floor cannot, and does not pretend to. NOT impossible: 15 of")
        print("   the 17 deletions were caught by at least one of Litvak's systems.")

    if vdis:
        print(f"\nJUDGE vs VERIFIER DISAGREE ({len(vdis)}) -- the shortlist "
              "worth a human eye:")
        for r, which, state in vdis:
            note = "  (verifier could not quote its own match)" \
                if state == "ungrounded" else ""
            print(f"  {which:<14} p{r['paper']:<3} {r['subcategory'][:32]:<34} "
                  f"{r['description'][:40]}{note}")
        ung = [1 for _r, _w, st in vdis if st == "ungrounded"]
        if ung:
            print(f"  {len(ung)} of these were claimed by the verifier but "
                  "REFUSED for lack of a grounded quote.")

    if disagree:
        print(f"\nFLOOR vs JUDGE DISAGREE ({len(disagree)}) -- adjudicate by hand.")
        print("  The floor is weak on prose: across the 100 errors, 17 have an empty")
        print("  modified_snippet, 52 have no usable numbers, and 35 have a 60-char")
        print("  prefix identical to the UNMODIFIED original. Read `floor only` as")
        print("  noise unless the row proves otherwise; `judge only` is informative.")
        for r, which in disagree:
            print(f"  {which:<11} p{r['paper']:<3} {r['subcategory'][:34]:<34} "
                  f"{r['description'][:44]}")

    print(f"\nMISSED ({len(miss_rows)}):")
    for r in miss_rows:
        mark = ""
        if ceiling and not ceiling["caught_by_any"].get(
                (r["paper"], r["subcategory"]), False):
            mark = "  <- no system caught this"
        print(f"  d{r['difficulty']} p{r['paper']:<3} {r['subcategory'][:32]:<32} "
              f"{r['description'][:42]}{mark}")

    if ceiling:
        solo = [r for r in hit_rows if not ceiling["caught_by_any"].get(
            (r["paper"], r["subcategory"]), False)]
        if solo:
            print(f"\nCAUGHT BY US, BY NO SYSTEM LITVAK TESTED ({len(solo)}):")
            for r in solo:
                print(f"  p{r['paper']:<3} {r['subcategory'][:34]:<36} "
                      f"{r['description'][:44]}")

    print_provenance_caveat(a, per_paper)

    # Record the run so `tables.py` can render it without re-scoring. Recorded
    # rather than recomputed on demand because the judge is not deterministic:
    # a table rebuilt by re-running would quietly change under its reader.
    if not a.no_record and caught:
        try:
            import results_store as _rs                        # noqa: PLC0415
            import datetime as _dt                             # noqa: PLC0415
            backend, model = run_backend_model(a, per_paper)
            row = _rs.build_row(
                corpus=a.from_db or (a.run_dir.name if a.run_dir else "?"),
                backend=backend, model=model,
                verify_model=None if a.no_verify else a.verify_model,
                scored_at=_dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
                commit=commit(), caught=caught,
                caught_protocol=caught_protocol, gt_rows=rows,
                n_hits_protocol=n_judge,
                n_findings=sum(per_paper[n]["n_candidates"] for n in scored))
            _rs.upsert(row)
            print(f"\nrecorded : {row['run_id']} -> {_rs.STORE_PATH.name}"
                  f"   (render with `python benchmarks/litvak/tables.py`)")
        except Exception as exc:                               # noqa: BLE001
            print(f"\n!! could not record this run: {exc}", file=sys.stderr)

    if a.json:
        a.json.write_text(json.dumps({
            "commit": commit(), "run_dir": str(a.run_dir), "mode": "recall",
            "matcher": "judge" if use_judge else "floor",
            "judge_model": None if a.no_judge else a.model,
            "n_errors": n_errors, "n_hits": n_hits,
            "n_hits_litvak_protocol": n_judge,
            "verify_model": None if a.no_verify else a.verify_model,
            "judge_verifier_disagreements": [
                {"paper": r["paper"], "subcategory": r["subcategory"],
                 "direction": w, "verifier_state": st} for r, w, st in vdis],
            "litvak_union": (ceiling or {}).get("union"),
            "litvak_best": (ceiling or {}).get("best"),
            "judge_calls": run_stats.get("judge_calls"),
            "judge_cache_hits": run_stats.get("judge_cache_hits"),
            "verify_calls": run_stats.get("verify_calls"),
            "judge_seconds": run_stats.get("judge_seconds"),
            "verify_seconds": run_stats.get("verify_seconds"),
            "papers_scored": sorted(scored),
            "papers_without_run": [per_paper[n]["dir"] for n in per_paper
                                   if not per_paper[n]["run"]],
            "by_category": {c: {"hits": hits_by_cat[c], "of": totals[c]}
                            for c in totals},
            "judge_errors": tot_jerr,
            "caught": {f"{k[0]}|{k[1]}": v for k, v in caught.items()},
            "hits": [r["subcategory"] for r in hit_rows],
            "misses": [r["subcategory"] for r in miss_rows],
            "denominator_note": (
                "All 100 planted errors. The 20-item 'declared scope' framing was "
                "removed 2026-08-23: it was asserted before measurement and the "
                "measurement contradicted it -- FMA caught 36 of the 80 errors it "
                "supposedly did not attempt."),
        }, indent=1), encoding="utf-8")
    return 0


def report_control(a, per_paper, scored, by_paper) -> int:
    """The clean originals. Recall is meaningless here; count flags."""
    print("\nCLEAN CONTROL -- flags per unmodified paper")
    print("  Recall is undefined here: nothing was planted. What this measures is")
    print("  how often FMA raises a `problem` on a real, unmodified manuscript.\n")
    print("  READ THIS BEFORE QUOTING IT:")
    print("  1. A flag is NOT automatically a false positive. These are real papers")
    print("     and real papers contain real errors. The number is 'flags per clean")
    print("     paper, N adjudicated by hand' -- the adjudication is not optional.")
    print("  2. This is a REPLICATION, not a first. Litvak ran all ten originals")
    print("     through every provider he tested; see benchmark/reports/summary.csv")
    print("     (the `*_originals` rows: Reviewer3 9, Refine 19, GPT-5.5 24,")
    print("     Sonnet-no-thinking 28) and the adjusted = modified - originals")
    print("     leaderboard in benchmark/ANALYSIS_LOG.md. He also records that ~15%")
    print("     of matches on originals are unavoidable overlap with real issues.\n")

    total = 0
    for n in sorted(per_paper):
        info = per_paper[n]
        if not info["run"]:
            print(f"  litvak{n:02d}   --  NO RUN")
            continue
        total += info["n_candidates"]
        print(f"  litvak{n:02d}  {info['n_candidates']:>3} flag(s)   "
              f"({info['n_pass']} pass, {info['n_undecided']} undecided, "
              f"{info['n_quarantined']} quarantined)")
    if scored:
        print(f"\n  {total} flags over {len(scored)} clean paper(s) "
              f"= {total/len(scored):.1f} per paper, 0 adjudicated by hand so far.")

    if a.json:
        a.json.write_text(json.dumps({
            "commit": commit(), "run_dir": str(a.run_dir), "mode": "control",
            "papers_scored": sorted(scored),
            "flags_per_paper": {per_paper[n]["dir"]: per_paper[n]["n_candidates"]
                                for n in scored},
            "total_flags": total,
            "note": ("Flags on unmodified papers. NOT a false-positive rate until "
                     "each is adjudicated by hand: real papers contain real errors. "
                     "Litvak already published this measurement for 14 configs "
                     "(benchmark/reports/summary.csv, *_originals rows)."),
        }, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
