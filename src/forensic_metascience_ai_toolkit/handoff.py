"""Does every stage hand its work to the next, and does the next stage read it?

Greg, 2026-08-13, before committing to a paid run: "may be worth running checks
to see whether every step works, producing good output and passing it off
successfully to the next step, which actually sees and uses the passed-along
work. (that's one of our house failures!)"

It is THE house failure. The record, all from this repository:

    `grace.py`                 shipped with 12 tests and zero callers
    `completeness`             written into every run, rendered nowhere
    `check_table`'s
      `declaration_template`   returned by the tool, named in no description
    `triage`                   a prompt instruction with no schema field to
                                 answer into, for weeks
    `computation_audit`        written 2026-08-13, would have shipped unread
    `_SI_HINTS`                a whole supplement dropped in silence

Six instances of one shape: a producer that works, and nothing downstream that
looks. Testing each part in isolation cannot catch it -- every one of those
components passed its own tests.

SO THIS AUDIT CHECKS LINKS, NOT PARTS. For each hand-off it asks three separate
questions, because they fail independently:

    PRODUCED   did the upstream stage actually write it, on this paper?
    WIRED      does the downstream stage's source refer to it at all?
    CONSUMED   is the value the downstream stage received non-empty?

`WIRED` is static and `PRODUCED`/`CONSUMED` are measured on a real run. A link
can be wired and empty (the consumer reads a key nobody filled), or produced and
unwired (the classic), and those need different fixes.

It runs offline and costs nothing, so it can gate a paid run.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

SRC = Path(__file__).resolve().parent


def _reads(module: str, needle: str) -> bool:
    """Does this module's SOURCE refer to the key at all?

    Deliberately a source-text search rather than an import graph: the failure
    being hunted is a consumer that never mentions the field, and a consumer
    that mentions it is at least reachable by a human asking why.
    """
    p = SRC / module
    if not p.is_file():
        return False
    return needle in p.read_text(encoding="utf-8")


def _dig(obj: Any, path: str) -> Any:
    cur = obj
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _size(v: Any) -> int:
    if v is None:
        return 0
    if isinstance(v, (list, tuple, dict, str)):
        return len(v)
    return 1


def audit(paper_dir: str | Path, review_dir: str | Path | None = None) -> dict:
    """Every hand-off in the pipeline, checked on a real paper.

    `review_dir` is an archived run; without one, the stages that need model
    output are reported as `not_measured` rather than as failures. A missing
    measurement is not a zero -- entry 1 of LESSONS.md, and this module would be
    a poor place to break it.
    """
    base = Path(paper_dir)
    rows: list[dict] = []
    _UNREADABLE.clear()

    def link(name: str, producer: str, consumer: str,
             produce: Callable[[], Any], wired: bool, note: str = "") -> Any:
        try:
            value = produce()
            err = None
        except Exception as exc:  # noqa: BLE001
            value, err = None, f"{type(exc).__name__}: {exc}"
        n = _size(value)
        rows.append({
            "link": name, "producer": producer, "consumer": consumer,
            "produced": err is None and n > 0, "n": n, "error": err,
            "wired": wired, "note": note,
            "ok": err is None and n > 0 and wired,
        })
        return value

    # 1. THE FILES -> everything. If this is wrong nothing downstream can be right.
    from . import supplements as _supp
    inputs = link(
        "files are classified", "supplements.classify_inputs",
        "prepass + completeness",
        lambda: (_supp.classify_inputs(base).get("files") or []),
        wired=_reads("prepass.py", "classify_inputs")
        or _reads("completeness.py", "present_files"),
        note="roles: " + ", ".join(sorted({
            str(f.get("role")) for f in (_supp.classify_inputs(base).get("files") or [])
        })) if base.is_dir() else "")

    undeclared = (_supp.classify_inputs(base).get("undeclared") or []) if base.is_dir() else []

    # 2. EXTRACTION CACHE -> prepass. The link that only exists since extraction
    #    became an explicit step; a cold cache here means the sweep sees no
    #    tables and says the paper has none.
    from .extraction import docling_tables as _dl
    pdfs = [base / f["name"] for f in (inputs or [])
            if f.get("role") in ("article", "supplement", "dataset")
            and str(f.get("name", "")).lower().endswith(".pdf")]
    cached = [p for p in pdfs if _dl._cache_path(p).is_file()] if pdfs else []
    has_xml = bool(list(base.glob("*.xml"))) if base.is_dir() else False
    rows.append({
        "link": "PDF tables are extracted", "producer": "metascience extract-tables",
        "consumer": "prepass.paper_tables",
        "produced": bool(cached) or has_xml, "n": len(cached),
        "error": None, "wired": _reads("prepass.py", "docling_tables"),
        "ok": bool(cached) or has_xml,
        "note": (f"{len(cached)}/{len(pdfs)} declared PDFs cached"
                 + ("; XML present so the article needs no extraction" if has_xml else "")),
    })

    # 3. TABLES -> manifest and census.
    from . import prepass as _pre
    tables = link(
        "tables are enumerated", "prepass.paper_tables",
        "completeness.build_manifest",
        lambda: _pre.paper_tables(base, include_supplements=True),
        wired=_reads("completeness.py", "paper_tables"))
    # NOT `list(...)`: that built a plain list and dropped the walker's
    # `.problems`, so until 2026-09-02 this was always empty and the audit
    # said "ok" over tables it could not read.
    tbl_problems = list(getattr(tables, "problems", None) or []) if tables is not None else []
    if tbl_problems and rows:
        rows[-1]["note"] = ((rows[-1].get("note") or "") + "; " if rows[-1].get("note") else "") + (
            f"{len(tbl_problems)} problem(s) reported by the walker: "
            + "; ".join(str(p) for p in tbl_problems[:3]))
        rows[-1]["ok"] = False

    # 4. MANIFEST -> coverage_summary.completeness AND the computation haystack.
    from . import completeness as _c
    link(
        "manifest is built", "completeness.build_manifest",
        "agent.coverage_summary + _number_haystack",
        lambda: (_c.build_manifest(base).get("items") or []),
        # `parallel.py`, not `agent.py`: both call sites the legacy version
        # named live INSIDE the body the deletion removes (agent.py:2985 and
        # :3078), while the live pipeline has its own at parallel.py:1530/1558.
        # `_number_haystack`'s DEFINITION survives in agent.py -- it is shared
        # -- so that half is asked of the definition and the call of the caller.
        wired=_reads("parallel.py", "build_manifest")
        and _reads("agent.py", "def _number_haystack"))

    # 5. THE HAYSTACK -> the computation audit's rescue. Wiring this was itself
    #    a hand-off that nearly shipped broken: `audit()` had no `haystack`
    #    argument at the call site, so the rescue could never run.
    from .agent import _number_haystack
    link(
        "paper text reaches the computation audit", "agent._number_haystack",
        "computation.audit(haystack=)",
        lambda: (_number_haystack(base, _c.build_manifest(base))[0] or ""),
        # agent.py's `haystack=_hay` is inside the legacy body; the live
        # pipeline passes `haystack=hay` at parallel.py:1559.
        wired=_reads("parallel.py", "haystack=hay"))

    # 6. THE ADMISSIBILITY GATE -> `analyze`. NOT a data hand-off, and that is
    #    exactly why it was missing.
    #
    #    MEASURED 2026-08-13 on Kross 2013 (10.1371--journal.pone.0069841):
    #    this audit printed "All 5 hand-offs carry data and have a consumer that
    #    reads them" and `metascience inputs` reported no complaint -- and then
    #    `metascience analyze` exited 2, because the article's own Supporting
    #    Information section lists Text S1-S6 and not one of them was present.
    #
    #    The pre-flight existed so an operator would not pay for a run that
    #    cannot succeed, and it was checking only whether DATA moved between
    #    stages, never whether the run was ADMISSIBLE. So it said GO on a paper
    #    the runner refuses. A pre-flight that passes what the runner rejects is
    #    worse than no pre-flight, because it is trusted.
    #
    #    `missing` is THREE-VALUED and is reproduced three-valued here. `None`
    #    means the paper could not be read, so the question was never answered;
    #    reporting that as a pass is the same absence-as-evidence defect this
    #    module exists to catch, one level up.
    supp = _supp.audit(base) if base.is_dir() else {"missing": None, "note":
                                                   "no paper directory"}
    _missing = supp.get("missing")
    if _missing is None:
        _gate_note = ("NOT MEASURED: the paper's text could not be read, so "
                      "whether it cites an absent supplement is UNKNOWN. "
                      + str(supp.get("note") or ""))
    elif _missing:
        _gate_note = (
            f"WILL WARN: the article cites {supp.get('reference_count', 0)} "
            f"supplementary item(s) across {len(supp.get('styles') or {})} "
            "citation style(s) and none is present. The run proceeds and records "
            "the missing material as a limitation; supply the files with "
            "--supplement to include them.")
    else:
        _gate_note = (
            f"{len(supp.get('files_present') or [])} supplementary file(s) "
            "present" if supp.get("references_supplement")
            else "the article cites no supplementary material")
    rows.append({
        "link": "cited supplements are present",
        "producer": "supplements.audit",
        "consumer": "analyze (admissibility gate)",
        "produced": None if _missing is None else not _missing,
        "n": len(supp.get("files_present") or []),
        "error": None,
        "wired": _reads("cli.py", "supplements") or _reads("agent.py", "gate"),
        "ok": None if _missing is None else not _missing,
        "note": _gate_note,
    })

    # ---- everything below needs a run ----
    if review_dir is None:
        rows.append({"link": "stage 1 -> stage 2 -> report -> viewer",
                     "producer": "-", "consumer": "-", "produced": None,
                     "n": 0, "error": None, "wired": None, "ok": None,
                     "note": "NOT MEASURED: no review directory given. This is "
                             "not a pass and not a failure."})
        return _finish(_summarise(rows, undeclared), review_dir)

    rd = Path(review_dir)
    findings = _load(rd / "findings.json")
    report = _load(rd / "report.json")
    # WHEN WAS THIS RUN MADE? A field absent from an ARCHIVED run because the
    # code did not exist yet is not a broken hand-off, and reporting it as one
    # is entry 8 of LESSONS.md -- "check whether the code POSTDATES the archive
    # you are measuring". The first version of this module failed Romano on
    # three fields added after that run, which is precisely the mistake it was
    # written to catch, committed inside the catcher.
    stale, stale_why = _predates_head(rd)

    fl = (findings or {}).get("findings") or []
    rows.append({
        # RE-POINTED AT THE LIVE PIPELINE (prerequisite (d), 2026-09-04). The
        # needle was `agent.py`'s `findings_for_stage2`, a legacy-body local
        # that the deletion removes -- and `_reads` returns False for a missing
        # file or a vanished name, so this audit would have reported OUR OWN
        # CLEANUP as an unwired pipeline. An audit that cries wolf about a
        # deliberate change gets ignored at exactly the rate a real break needs
        # it not to be.
        "link": "the analysts' findings reach the adjudicator",
        "producer": "tool + science analysts",
        "consumer": "adjudicate.build_docket", "produced": bool(fl),
        "n": len(fl), "error": None,
        "wired": _reads("parallel.py", "build_docket"),
        "ok": bool(fl), "note": ""})

    # 6. SECOND LOOK -> stage 2. Wired only if the PROMPT explains it, because a
    #    payload the prompt never mentions is a payload the model will not use.
    from . import secondlook as _sl
    work = _sl.worklist(fl)
    # Same re-pointing, and the same reason: `stage2_editorial.md` is deleted
    # with the legacy path. `adjudication.md` carries the `second_look`
    # explanation now, and `parallel.py` passes the worklist into the docket --
    # BOTH are required, because a payload the prompt never mentions is a
    # payload the model will not use, and a prompt explaining a payload that is
    # never passed is worse.
    prompt_ok = (_reads("modules/adjudicator/prompt.md", "second_look")
                 and _reads("parallel.py", "second_look="))
    rows.append({
        "link": "second_look reaches the adjudicator",
        "producer": "secondlook.worklist",
        "consumer": "adjudication.md",
        "produced": work.get("n_accusatory", 0) > 0, "n": work.get("n_flagged", 0),
        "error": None, "wired": prompt_ok,
        "ok": prompt_ok and work.get("n_accusatory", 0) >= 0,
        "note": f"{work.get('n_flagged')} of {work.get('n_accusatory')} accusations flagged"})

    # 7. STAGE 1 -> STAGE 2 dispositions.
    rec = _c.reconcile_findings(fl, report or {})
    rows.append({
        "link": "every stage-1 finding gets a disposition",
        "producer": "completeness.reconcile_findings",
        "consumer": "viewer Coverage page",
        "produced": rec.get("reconcilable") is not False,
        "n": rec.get("n_stage1") or 0, "error": None,
        "wired": _reads("bundle.py", "stage1_reconciliation"),
        "ok": rec.get("reconcilable") is not False,
        "note": f"{rec.get('n_dropped')} dropped, "
                f"{rec.get('n_accusatory_unexplained')} accusations unexplained"})

    # 8. COVERAGE_SUMMARY -> viewer, key by key. This is the exact surface where
    #    `completeness` sat unread for weeks.
    for key, needle in (("checkable", "cs.checkable"),
                        ("completeness", "cs.completeness"),
                        ("computation_audit", "cs.computation_audit"),
                        ("undelivered", "cs.undelivered"),
                        ("stage1_reconciliation", "cs.stage1_reconciliation")):
        v = _dig(report or {}, f"coverage_summary.{key}")
        wired = _reads("bundle.py", needle)
        if v is None and stale:
            rows.append({
                "link": f"coverage_summary.{key} is rendered",
                "producer": "agent.py", "consumer": "bundle.py viewer",
                "produced": None, "n": 0, "error": None, "wired": wired,
                "ok": None,
                "note": f"NOT MEASURED: {stale_why}. The consumer is wired; "
                        "only a run at current HEAD shows whether the value "
                        "arrives."})
            continue
        rows.append({
            "link": f"coverage_summary.{key} is rendered",
            "producer": "agent.py", "consumer": "bundle.py viewer",
            "produced": _size(v) > 0, "n": _size(v), "error": None,
            "wired": wired, "ok": wired and _size(v) > 0,
            "note": "" if v is not None else "absent from this run's report.json"})

    return _finish(_summarise(rows, undeclared), review_dir)


def _finish(out: dict, review_dir: str | Path | None) -> dict:
    """Attach the other two legs of the def-use analysis and re-decide `ready`.

    Applied at BOTH exits of `audit`. The first cut attached them at one exit
    only -- the early return taken when no run directory is given -- so a
    pre-flight got the new checks and a full audit silently did not, which is
    the precise shape of defect this whole module exists to detect.
    """
    # DELIVERY needs the tool-call ledger, so it is post-hoc by nature. On a
    # pre-flight it is reported as NOT MEASURED rather than as clean.
    out["delivery"] = {"ok": None, "note": (
        "no review directory given, so whether the model's fetches ARRIVED is "
        "not measured. Pass -r <run> to check it.")}
    if review_dir:
        # The tools agent's ledger. Until 2026-09-03 only the serial sweep's
        # `toolcalls.stage1.json` was tried, so on every parallel run this kept
        # the pre-flight sentence above -- "no review directory given ... Pass
        # -r <run>" -- when one HAD been passed, and `ready` stayed True on an
        # unmeasured leg. A wrong reason printed with confidence is worse than
        # the missing measurement.
        names = ("toolcalls.tool_agent.json",)
        found = [n for n in names if (Path(review_dir) / n).exists()]
        for name in names:
            led = _load(Path(review_dir) / name)
            if isinstance(led, list):
                out["delivery"] = delivery_audit(led)
                break
        else:
            if found:
                out["delivery"] = {
                    "ok": None,
                    "note": f"the tool-call ledger ({found[0]}) could not be read"}
            else:
                out["delivery"] = {"ok": None, "note": (
                    "this run directory holds neither toolcalls.tool_agent.json "
                    "nor toolcalls.stage1.json, so whether the model's fetches "
                    "ARRIVED is not measured")}

    # READY MEANS ALL THREE LEGS. A run whose hand-offs are sound, whose tools
    # are stranded, or whose fetches never arrived, is not ready in any sense a
    # reader would recognise.
    out["ready"] = bool(out["ready"]
                        and out["reachability"].get("ok") is not False
                        and out["delivery"].get("ok") is not False)
    return out


def _predates_head(review_dir: Path) -> tuple[bool, str]:
    """Was this run made at a commit that is an ANCESTOR of HEAD?

    `(is_older, why)`. True means the run may predate a field it lacks, so its
    absence is reported as unmeasured rather than as a broken hand-off. The
    reason travels because "we could not tell" and "it is genuinely older" are
    different facts and only one of them is about the pipeline.
    """
    meta = _load(review_dir / "run_meta.json") or {}
    sha = str(meta.get("git_sha") or "").strip()
    if not sha:
        # Unknown provenance. Excusing a missing field is the SAFE direction --
        # it produces "not measured" rather than a false failure -- but the
        # reason is returned so a caller can say which it was.
        return True, "this run records no git_sha, so its age is unknown"
    import subprocess
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=SRC.parents[1],
                              capture_output=True, text=True, timeout=10)
    except Exception as exc:  # noqa: BLE001
        return True, f"git could not be run ({type(exc).__name__}), age unknown"
    if head.returncode != 0:
        return True, "git rev-parse failed, so the run's age is unknown"
    if head.stdout.strip().startswith(sha):
        return False, ""
    return True, f"this run was made at {sha}, which is not HEAD"


#: Files this audit could not read, as opposed to files that are not there.
#: Kept module-level so `_load` stays a one-liner at its call sites while the
#: distinction still reaches the reader -- a corrupt report.json and a missing
#: one produce identical downstream behaviour and completely different fixes.
_UNREADABLE: list[str] = []


def _load(p: Path) -> dict | None:
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        _UNREADABLE.append(f"{p.name}: {type(exc).__name__}: {exc}")
        return None


def _summarise(rows: list[dict], undeclared: list[str]) -> dict:
    measured = [r for r in rows if r["ok"] is not None]
    broken = [r for r in measured if not r["ok"]]
    unwired = [r for r in measured if r.get("wired") is False]
    empty = [r for r in measured if r.get("wired") and not r.get("produced")]
    return {
        "rows": rows,
        "n_links": len(measured),
        "n_ok": len(measured) - len(broken),
        "broken": broken,
        "unwired": [r["link"] for r in unwired],
        "produced_but_empty": [r["link"] for r in empty],
        "undeclared_files": undeclared,
        "unreadable_files": list(_UNREADABLE),
        "ready": not broken and not undeclared,
        "note": _note(measured, broken, unwired, empty, undeclared),
        # THE OTHER TWO LEGS OF THE SAME QUESTION. The rows above ask whether
        # each stage's output is PRODUCED and CONSUMED. `reachability` asks
        # whether the model can call a tool at all, and `delivery` (added by
        # `audit` when a run directory is given) whether what it asked for
        # arrived. Together they are the def-use analysis: is there a use for
        # every definition, a definition for every use, and does the value
        # survive the trip.
        "reachability": reachability(),
    }


def reachability() -> dict:
    """Can the model call every registered tool, or are some stranded?

    MEASURED 2026-08-15: four of 54 registered tools were offered to NEITHER
    stage -- registered, tested, CLI-exposed, and uncallable. Two of them had
    49 and 18 archived calls apiece, so they had been offered once and were
    withdrawn without being deleted.

    Static and paper-independent, so it costs nothing to run on every audit and
    catches a whole-surface regression on whichever paper happens to be next.
    """
    try:
        # `agent` is deliberately NOT imported here any more: this audit now
        # asks the registry roles directly (prerequisite (c)), and importing a
        # module it no longer reads would tie the audit's survival to the
        # legacy pipeline's.
        from . import registry as _registry
    except Exception as exc:  # noqa: BLE001
        return {"ok": None, "note": f"could not be measured ({type(exc).__name__}: {exc})"}

    reg = {s.name for s in _registry.SPECS}
    # ASKED OF THE REGISTRY ROLES, NOT OF agent.py's LEGACY ALIASES
    # (prerequisite (c), 2026-09-04). This read `_agent.STAGE1_TOOLS` /
    # `STAGE2_TOOLS`, which the legacy deletion removes -- so the audit that
    # exists to catch a stranded tool would itself have raised AttributeError
    # and reported "could not be measured" on every run. `registry.stage_tools`
    # is the source those aliases were derived from anyway
    # (CLAUDE.md: "Per-role tool lists come from registry.stage_tools"), so
    # this is the same question asked one layer closer to the truth.
    #
    # Verified identical before the swap: both unions cover 60 tools and strand
    # nothing. Pinned in `tests/test_handoff_reachability_roles.py`.
    s1 = set(_registry.stage_tools(_registry.TOOL_AGENT)) & reg
    s2 = set(_registry.stage_tools(_registry.ADJUDICATOR)) & reg
    s3 = set(_registry.stage_tools(_registry.SCIENCE_AGENT)) & reg
    # DECLARED CLI-ONLY TOOLS ARE NOT STRANDED. Counting a decision as a defect
    # is the same error as missing one, and an audit that reports our own
    # deliberate choices back to us gets ignored at exactly the same rate.
    declared = set(getattr(_registry, "CLI_ONLY", {}) or {})
    stranded = sorted(reg - s1 - s2 - s3 - declared)
    return {
        "ok": not stranded,
        "n_registered": len(reg),
        # Role-named, because "stage 1/2" named a pipeline that no longer
        # exists. The old `n_stage1`/`n_stage2` keys are NOT kept as aliases:
        # `cli.py` was their only reader and now reads these, so an alias would
        # be a second name for one number, naming a retired pipeline -- exactly
        # the kind of duplication that makes this codebase hard to read.
        "n_tool_agent": len(s1), "n_science_agent": len(s3),
        "n_adjudicator": len(s2),
        "stranded": stranded, "cli_only": sorted(declared),
        "note": ("every registered tool is reachable by at least one stage"
                 if not stranded else
                 f"{len(stranded)} registered tool(s) are offered to NEITHER stage "
                 f"and can never be called: {', '.join(stranded)}. Registered, "
                 "tested and uncallable is a definition with no reachable use."),
    }


def _note(measured, broken, unwired, empty, undeclared) -> str:
    if not measured:
        return "Nothing could be measured."
    if not broken and not undeclared:
        return (f"All {len(measured)} hand-offs carry data and have a consumer "
                "that reads them.")
    parts = [f"{len(measured) - len(broken)} of {len(measured)} hand-offs are "
             "sound"]
    if unwired:
        parts.append(f"{len(unwired)} produce output NOTHING DOWNSTREAM READS -- "
                     "this is the failure this audit exists for")
    if empty:
        parts.append(f"{len(empty)} have a consumer but arrived EMPTY, which "
                     "reads downstream as 'there was nothing to report'")
    if undeclared:
        parts.append(f"{len(undeclared)} file(s) in the directory are undeclared "
                     "and will not be used")
    return "; ".join(parts) + "."


# --- Delivery: did the payload actually ARRIVE? ---------------------------
#
# The third leg of the def-use analysis this module already does two-thirds of.
# `audit` above asks whether a stage's output is PRODUCED and CONSUMED. This asks
# the question underneath both: when the model reached for something, did it get
# it?
#
# MEASURED 2026-08-15 over all 2,706 archived tool calls: 46 (1.7%) returned
# nothing usable, and 30 of those are the EXTRACTION tools -- the ones whose only
# job is delivering the paper:
#
#     extract_supplement   "result (3,241,286 characters across 139,991 lines)
#                           exceeds maximum allowed tokens"
#     detect_raw_duplication  467,978 characters, same outcome
#
# The data existed. It was fetched. It could not be passed to the model. So a
# whole supplement went unread, and NOTHING SAID SO: `result_truncated` was
# already computed and stored in the ledger, and no renderer read it.
#
# This is the worst version of the failure this repository keeps having, because
# it does not merely lose a finding -- it makes the coverage denominator count
# items the model could not possibly have seen, so the run reads as incurious
# when it was starved.

#: A result that means "the tool ran and you got nothing", as opposed to a
#: refusal, which is a first-class answer and must NOT be counted here.
_UNDELIVERED = _re.compile(
    r"exceeds maximum allowed tokens|^\s*Error:", _re.M) if (_re := __import__("re")) else None

#: How big the payload actually was, from the harness's own sentence:
#: "result (175,829 characters across 6,332 lines) exceeds maximum allowed
#: tokens". `result_chars` on the ledger row measures the ERROR STRING, not the
#: payload -- on the archived PNAS run it reads 1,396 while the message says
#: 64,560 -- so a reader told "1,396 characters would not fit" would rightly
#: stop believing us. The number in the sentence is the one that is true.
_OVERFLOW_CHARS = _re.compile(r"result \(([\d,]+) characters")

#: THE SPILL FILE. An overflow does not destroy the payload -- the harness writes
#: it to `.../tool-results/<tool>-<ts>.txt` and tells the model to read it back,
#: and the model usually does. MEASURED 2026-08-17 over the archived runs: 24
#: overflow rows carry a spill path and 21 of them are followed by a successful
#: read of that path, so an audit blind to this route would have reported nearly
#: every overflow as a lost file -- including the PNAS run, where the article
#: itself would have been declared unread while its text was demonstrably in the
#: transcript. Overstating our own failure switches the instrument off exactly
#: as fast as understating it.
_SPILL_PATH = _re.compile(r"saved to (\S+)")


def _spill_path(result: str) -> str:
    """Where the harness parked an overflowed payload, if it said."""
    m = _SPILL_PATH.search(result[:600])
    # The sentence ends "...txt." -- the first cut kept the full stop, so the
    # path never matched the read that recovered it and all 21 recoveries above
    # scored as zero.
    return m.group(1).rstrip(".") if m else ""


def _undelivered_kind(result: str, truncated: bool) -> str | None:
    """`"overflow"` | `"error"` | None -- did this call carry a usable payload?

    A REFUSAL IS NOT A FAILURE and does not appear here; see `delivery_audit`.
    Shared by the two audits below so they cannot drift into disagreeing about
    what "did not arrive" means, which is the sort of split that ends with one
    surface reporting a lost supplement and another reporting a clean run.
    """
    if "exceeds maximum allowed tokens" in result[:400]:
        return "overflow"
    if _UNDELIVERED and _UNDELIVERED.search(result[:400]):
        return "error"
    if truncated and not result.strip():
        return "error"
    return None


def delivery_audit(ledger: list[dict] | None) -> dict:
    """What the model asked for and did not get.

    A REFUSAL IS NOT A FAILURE. A tool that declines to judge -- reversed CI
    bounds, a missing scale bound, a precondition it cannot verify -- has
    delivered its answer, and counting those here would bury the real thing
    under routine noise. Only results that carry no usable payload count.
    """
    rows = [c for c in (ledger or []) if isinstance(c, dict)]
    lost: list[dict] = []
    for c in rows:
        result = str(c.get("result") or "")
        kind = _undelivered_kind(result, bool(c.get("result_truncated")))
        if kind is None:
            continue
        name = str(c.get("tool") or c.get("name") or "?").split("__")[-1]
        inp_full = {k: str(v) for k, v in (c.get("input") or {}).items()
                    if k in ("pdf_path", "xml_path", "path", "supplement_path",
                             "first_page", "last_page", "table_num")}
        lost.append({
            "seq": c.get("seq"),
            "tool": name,
            "kind": kind,
            "chars": c.get("result_chars"),
            # THE FILENAME, WHOLE, because the display path below is cut at 120
            # characters and every path in this corpus is longer than that --
            # the archived PNAS row ends `10.1073--pnas.08012`, mid-name. A
            # table that cannot name the file it lost is a table that tells a
            # reader something went missing and not what.
            "file": _basename(next((v for k, v in inp_full.items()
                                    if k.endswith("path")), "")),
            # TRUNCATED FOR DISPLAY ONLY. The first cut truncated to 120 chars
            # and then compared THOSE against the full paths of the retry calls,
            # so any path longer than 120 characters -- which is every path in
            # this corpus -- never matched and every recovered fetch was reported
            # as unrecovered. Our instrument overstating our own failure is the
            # same error as understating it, one direction along.
            "input": {k: v[:120] for k, v in inp_full.items()},
            "_paths": [v for k, v in inp_full.items() if k.endswith("path")],
            "detail": result[:160].replace("\n", " ").strip(),
        })

    # AN OVERFLOW THAT WAS NEVER RECOVERED IS THE DANGEROUS ONE. The model
    # usually recovers, and a recovered fetch costs turns but loses nothing.
    #
    # RECOVERY IS ANY LATER SUCCESSFUL CALL ON THE SAME PATH, not just a paged
    # retry of the same tool. The first cut looked only for
    # first_page/last_page/max_chars and therefore missed the commonest recovery
    # of all: switching tool SHAPE. On Romano the whole-document
    # `extract_supplement` overflowed and the model recovered by pulling the
    # supplement's tables one at a time with `get_supplement_table` -- five
    # successful calls that the narrow test scored as no recovery at all.
    #
    # Both of this function's early errors ran the same way, toward reporting
    # our pipe as more broken than it is. An instrument that cries wolf about
    # its own side gets switched off exactly as fast as one that stays silent.
    #
    # THE THIRD RECOVERY ROUTE, added 2026-08-17 and the commonest of all: the
    # harness spills the overflowed payload to a file and the model reads it
    # back. Measured, 21 of the archive's 24 spilled overflows end that way, so
    # crediting only OUR tools would have called them all unrecovered.
    def _paths_of(call: dict) -> list[str]:
        inp = call.get("input") or {}
        return [str(v) for k, v in inp.items() if k.endswith("path") and v]

    spilled = {s: _paths_of(c) for c in rows
               if (s := _spill_path(str(c.get("result") or "")))}

    recovered: set[str] = set()
    for c in rows:
        result = str(c.get("result") or "")
        if "exceeds maximum allowed tokens" in result[:400] or result.startswith("Error:"):
            continue
        if not result.strip():
            continue
        recovered.update(_paths_of(c))
        # A read of the spill file delivers the ORIGINAL file, so it is credited
        # to that path and not to the temporary one nobody asked for.
        for v in (str(x) for x in (c.get("input") or {}).values()):
            for s, origins in spilled.items():
                if s in v:
                    recovered.update(origins)
    retried = recovered
    unrecovered = [x for x in lost if not any(v in retried for v in x.get("_paths") or [])]
    for x in lost:
        x.pop("_paths", None)

    extraction = [x for x in lost if x["tool"].startswith(("extract_", "get_"))]
    ok = not lost
    if ok:
        note = "every tool call returned a usable payload."
    else:
        note = (
            f"{len(lost)} tool call(s) returned NO usable payload"
            f"{f', {len(extraction)} of them extraction calls' if extraction else ''}"
            f"; {len(unrecovered)} were never retried with a narrower request. "
            "Where an extraction overflowed and was not retried, that file is "
            "absent from this review -- and any coverage figure counts items the "
            "model could not have seen. This is OUR pipe being too narrow, not "
            "the paper reporting less.")
    return {"ok": ok, "n_calls": len(rows), "n_undelivered": len(lost),
            "n_extraction": len(extraction), "n_unrecovered": len(unrecovered),
            "lost": lost[:25], "note": note}


def _basename(path: str) -> str:
    """Last segment of a path, whichever separator the harness recorded."""
    p = str(path or "").rstrip("/\\").replace("\\", "/")
    return p.rsplit("/", 1)[-1] if p else ""


def _overflow_chars(result: str) -> int | None:
    m = _OVERFLOW_CHARS.search(result[:400])
    return int(m.group(1).replace(",", "")) if m else None


def undelivered_files(ledger: list[dict] | None) -> dict:
    """WHICH FILES this review could not load, and what that leaves UNKNOWN.

    `delivery_audit` above counts undelivered CALLS, which is the operator's
    question -- how leaky is the pipe. This asks the reader's question, the one
    that decides how a report should be read: a supplement whose 175,829
    characters would not fit through the context window is ABSENT from the
    review, and on the page it looks exactly like a supplement with nothing in
    it.

    WHAT WE HAD INSTEAD WAS THE MODEL'S GOODWILL. Measured across the archive,
    no field in report.json, report.md or viewer.html holds this fact -- where a
    reader learned of a dropped file at all, it was because the model chose to
    write it into `not_checked` in prose, as the s41537 run did ("Present but
    not deliverable... 1,114,127 characters"). That is a good disclosure and it
    is discretionary, unverifiable and absent by default. This makes it a
    record.

    MEASURED 2026-08-17 over every archived ledger in this checkout, and the
    three shapes it has to keep apart:

      10.3389--fnins.2023.1186751  `extract_supplement` overflowed on a
                                   3,241,286-character dataset and the model
                                   read the SPILL FILE back -- partial, not lost.
      10.1038--s41537-025-00576-3  `extract_supplement` overflowed on a
                                   1,114,127-character supplement and nothing
                                   ever came back for it: UNREAD, and the run
                                   reads as though the file held nothing.
      10.1002--eat.24415           the whole-file read of `EAT-58-1072-s001.docx`
                                   overflowed and five per-table fetches
                                   returned content, but `get_supplement_table`
                                   table 4 overflowed too: partial, and "the
                                   rest is unknown" is the only honest report.

    Grouped by PATH, not by call: a reader does not care how many times we
    asked. Status is decided by whether ANY route delivered content for that
    path -- our own narrower tools, a paged retry, or a read of the harness's
    spill file -- because scoring only our tools called 21 of the archive's 24
    spilled overflows lost files when the text was in the transcript.
    """
    rows = [c for c in (ledger or []) if isinstance(c, dict)]

    def _paths(call: dict) -> list[str]:
        return [str(v) for k, v in (call.get("input") or {}).items()
                if k.endswith("path") and v]

    files: dict[str, dict] = {}
    spilled: dict[str, list[str]] = {}
    for c in rows:
        result = str(c.get("result") or "")
        # A tool result that overflowed without naming a file is a real loss and
        # `delivery_audit` counts it. It is not a FILE, and inventing one here
        # would put a name in front of a reader that nothing traces back to.
        paths = _paths(c)
        if not paths:
            continue
        kind = _undelivered_kind(result, bool(c.get("result_truncated")))
        if kind is None:
            continue
        if spill := _spill_path(result):
            spilled[spill] = paths
        tool = str(c.get("tool") or c.get("name") or "?").split("__")[-1]
        chars = _overflow_chars(result)
        for p in paths:
            rec = files.setdefault(p, {
                "file": _basename(p) or p, "path": p, "tools": [],
                "kinds": [], "n_lost_calls": 0, "chars": None})
            rec["n_lost_calls"] += 1
            if tool not in rec["tools"]:
                rec["tools"].append(tool)
            if kind not in rec["kinds"]:
                rec["kinds"].append(kind)
            if chars and chars > (rec["chars"] or 0):
                rec["chars"] = chars
    if not files:
        return {"ok": True, "n_files": 0, "n_unread": 0, "n_partial": 0,
                "files": [], "note": "every file this review reached for arrived."}

    arrived: dict[str, int] = {}
    for c in rows:
        result = str(c.get("result") or "")
        if not result.strip() or _undelivered_kind(
                result, bool(c.get("result_truncated"))):
            continue
        for p in _paths(c):
            if p in files:
                arrived[p] = arrived.get(p, 0) + 1
        for v in (str(x) for x in (c.get("input") or {}).values()):
            for spill, origins in spilled.items():
                if spill in v:
                    for p in origins:
                        arrived[p] = arrived.get(p, 0) + 1

    out: list[dict] = []
    for p, rec in files.items():
        n_ok = arrived.get(p, 0)
        rec["n_delivered_calls"] = n_ok
        rec["status"] = "partial" if n_ok else "unread"
        how = " and ".join(f"`{t}`" for t in rec["tools"])
        size = f" at {rec['chars']:,} characters" if rec["chars"] else ""
        got = (f"{how} "
               f"{'overflowed' if 'overflow' in rec['kinds'] else 'returned nothing'}"
               f"{size}")
        if rec["status"] == "unread":
            # NOT "the file is empty" and NOT "the paper reports nothing here".
            # This repository's third named failure mode is absence read as
            # evidence, and a dropped supplement is its purest instance: the
            # coverage denominator goes on counting items the model could not
            # have seen, so a starved run reads as an incurious one.
            # WITHOUT THE FILENAME IN FRONT: both consumers -- the report's
            # bullet and the viewer's table -- print the name in the adjacent
            # column, and a sentence that repeats it reads as boilerplate and
            # gets skipped, which is not what this sentence is for.
            rec["note"] = (
                f"{got}, and no "
                "later call, retry or spill-file read brought any of it back. "
                "WHAT IT CONTAINS IS UNKNOWN: that is our reader being too "
                "narrow, and it is not evidence that the file is empty or that "
                "the paper reports nothing in it. To close the gap, re-run and "
                "fetch it in pieces -- `get_supplement_table` one table at a "
                "time, or `extract_pdf` with `first_page`/`last_page`.")
        else:
            # HOW MUCH of the file the later calls cover is not measured, and
            # this says so rather than picking a direction. Same rule as the
            # coverage stamp one layer up: an uncountable population may be
            # reported as uncountable, never turned into a claim either way.
            rec["note"] = (
                f"{got}, and "
                f"{n_ok} later call(s) did return content from it. What those "
                "brought back was reviewed; how much of the file they cover is "
                "not measured, so anything they missed is UNKNOWN, not clean.")
        out.append(rec)
    out.sort(key=lambda r: (r["status"] != "unread", r["file"]))

    n_unread = sum(1 for r in out if r["status"] == "unread")
    named = ", ".join(f"`{r['file']}`" for r in out[:6])
    note = (
        f"{len(out)} file(s) this review reached for did not fully arrive "
        f"({n_unread} never loaded at all, {len(out) - n_unread} in pieces "
        f"only): {named}. A file we could not load is OUR gap: what is in it is "
        "UNKNOWN to this review, and nothing here is evidence that it is empty "
        "or that the paper has no tables in it. Every coverage figure in this "
        "report counts only what did arrive.")
    return {"ok": False, "n_files": len(out), "n_unread": n_unread,
            "n_partial": len(out) - n_unread, "files": out[:25], "note": note}
