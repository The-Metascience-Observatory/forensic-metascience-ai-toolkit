"""One row per paper for the review workbench, from whatever is on disk.

WHY A SEPARATE SCANNER, AND NOT `bundle.collect`. `collect` is the right
function for ONE paper: it anchors findings to pages, sorts them through
`report_render.sort_findings` so the viewer and `report.md` number them
identically, and renders every PDF page to a JPEG. That last part costs
seconds per paper and hundreds of megabytes per corpus. An index needs none of
it. This module reads small JSON and calls `stat`; the detail view calls
`collect` on demand, for the one paper being looked at.

THE MEASUREMENT THIS IS SHAPED BY (2026-08-17, on the corpora in this
checkout):

    high_value_pdfs_to_run_on              6 papers, 12 review directories
    cerebrolysin_papers (sibling repo)   423 papers,  0 review directories
                                         372 with panels/
                                         370 with panels/panel_index.json
                                           1 with a retained detector result

Two things follow, and both contradict the obvious data model.

1. A PAPER IS NOT A RUN. Papers here carry several review directories --
   `forensic_review`, `forensic_review_current`, `forensic_review_warrant`,
   `forensic_review_opus_08_09_2026` -- which are different analyses of the
   same paper, often across a version boundary that CHANGELOG.md says makes
   them incomparable. A row per paper that silently shows "the" verdict picks
   one and hides the rest.

2. "THE CHECK RAN" AND "WE KEPT THE ANSWER" ARE DIFFERENT FACTS.
   `panel_index.json` is written by `analyze_paper_images` itself, so 370
   papers demonstrably ran the image detector -- and 369 of them retain no
   result. Reporting those as "image forensics: did not run" is false; as
   "ran" it invites a reader to conclude the panels were examined and cleared.
   Neither is true, so `ran_result_discarded` is its own state.

Every channel is therefore a TRI-STATE at minimum, never a boolean, and the
absence of an artifact is never rendered as a clean result. This is the same
discipline `extraction/supplements_read.py` enforces with its four refusal
states, and the same one `verdicts.canonical` enforces by returning None
rather than guessing.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from . import verdicts as _verdicts
from .report_render import severity_rank

#: Bumped when a consumer parsing this file would break.
SCHEMA_VERSION = "1.0"

#: What a channel can be. The first four are facts about the RUN; the fifth is
#: a fact about us.
#:
#: `ran`                   the check ran and its result is on disk
#: `ran_result_discarded`  it demonstrably ran and no result was retained
#: `refused`               it ran and declined to judge, with a named subtype
#: `did_not_run`           no evidence it ran
#: `unknown`               we could not tell -- a read failed, not an absence
from forensic_metascience_ai_toolkit.discovery import CHANNEL_STATES as CHANNEL_STATES

#: Every channel `scan_paper` CAN emit, in display order. ONE list, because it
#: was two: `_totals` carried its own literal copy, so a channel added to
#: `scan_paper` appeared on every paper and in no total.
_ALL_CHANNEL_NAMES = ("numeric", "image_forensics", "cross_paper",
                      "tortured_phrases", "figures")


def cross_paper_enabled() -> bool:
    """Is the between-paper duplication screen switched on?

    OFF BY DEFAULT since 2026-08-18. The sweep runs, and on the corpora here it
    returned nothing a reviewer wanted: 12 matches on cerebrolysin, none of them
    a finding. A screen that costs a reviewer attention and returns noise is
    worse than no screen, because the attention is the scarce thing.

    A SWITCH RATHER THAN A DELETION, and the distinction matters for what the
    workbench then claims. Off, the channel is not emitted at all, so no paper
    says "no cross-paper hits" -- which would be a claim we are no longer
    checking. The papers simply do not carry the channel, and a corpus scanned
    with it off is silent about the question rather than answering it.

    `METASCIENCE_CROSS_PAPER=1` turns it back on. The producer
    (`image_corpus.write_cross_paper_matches`) is untouched: re-running the
    sweep still writes its JSON, so turning this on shows what is already on
    disk without re-computing anything.
    """
    return os.environ.get("METASCIENCE_CROSS_PAPER", "").strip().lower() in (
        "1", "true", "yes", "on")


def channel_names() -> tuple[str, ...]:
    """The channels this scan will actually emit."""
    if cross_paper_enabled():
        return _ALL_CHANNEL_NAMES
    return tuple(c for c in _ALL_CHANNEL_NAMES if c != "cross_paper")

#: A review directory whose name ends this way is a BUNDLE, not a run: it holds
#: `analysis/report.md`, a scrubbed COPY of a review that also exists in its own
#: right. Counting it doubles every paper that has ever been bundled -- measured
#: 12 review directories across 6 papers in `high_value_pdfs_to_run_on`, of
#: which two are bundles of directories already in the list.
from forensic_metascience_ai_toolkit.discovery import _BUNDLE_SUFFIX as _BUNDLE_SUFFIX

_SEVERITIES = ("impossible", "highly_suspicious", "suspicious",
               "indeterminate", "consistent")


def _read_json(path: Path) -> Any:
    """Small JSON, or None. A read failure is not an absence, and callers that
    care about the difference check `path.exists()` themselves."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _channel(state: str, detail: str = "", **extra: Any) -> dict:
    assert state in CHANNEL_STATES, state
    return {"state": state, "detail": detail, **extra}


from forensic_metascience_ai_toolkit.discovery import review_dirs as review_dirs


#: A finding the IMAGE track produced, in the two vocabularies that reach this
#: file: `producer` on a findings-v2 row, and the technique name (v2 rows call
#: it `analyze_paper_images`, a v1 report row `image_duplication`).
IMAGE_PRODUCERS = frozenset({"image_track"})
IMAGE_TECHNIQUES = frozenset({"analyze_paper_images", "image_duplication"})

#: The id prefix the image track stamps on the findings it injects. A v1
#: report row carries no `technique` at all -- `stage1_finding_ids` is the only
#: thread back to who produced it.
_IMAGE_ID_PREFIX = "IMGDUP"


def is_image_finding(f: dict) -> bool:
    """Did the image track produce this finding?

    Kept separate from the count because the two surfaces disagree about what
    a finding IS: findings-v2 names its producer, a v1 report row does not and
    is identified only by the ids it merged. A report row that merged BOTH an
    image id and a numeric one is NOT image-only -- it says something about the
    numbers too, so it belongs in the non-image count.
    """
    if not isinstance(f, dict):
        return False
    if str(f.get("producer") or "") in IMAGE_PRODUCERS:
        return True
    if str(f.get("technique") or "") in IMAGE_TECHNIQUES:
        return True
    ids = [str(i) for i in (f.get("stage1_finding_ids") or [])
           if isinstance(i, (str, int))]
    return bool(ids) and all(i.startswith(_IMAGE_ID_PREFIX) for i in ids)


def severity_counts(findings: Iterable[dict]) -> dict[str, int]:
    """Tally by severity, with every rung present at zero.

    Present-at-zero on purpose: a missing key and a zero read differently in a
    UI, and only one of them is a claim. `0 impossible` says we looked.
    """
    counts = {s: 0 for s in _SEVERITIES}
    for f in findings:
        if not isinstance(f, dict):
            continue
        sev = str(f.get("severity") or "").strip().lower()
        if sev in counts:
            counts[sev] += 1
    return counts


def _worst_severity(counts: dict[str, int]) -> str | None:
    for s in _SEVERITIES:
        if counts.get(s):
            return s
    return None


from forensic_metascience_ai_toolkit.discovery import run_kind as run_kind


def scan_run(review_dir: Path) -> dict:
    """One review directory: what it concluded and what it cost.

    A run that ERRORED but still produced a full report is PARTIAL, not failed
    -- the same distinction `batch.py` had to learn after filing a
    complete, paid-for review into `failed.jsonl`. It is recorded here as
    `status`, so the workbench can show a partial run as partial rather than
    hiding it or trusting it.
    """
    report = _read_json(review_dir / "report.json") or {}
    meta = _read_json(review_dir / "run_meta.json") or {}
    findings_obj = _read_json(review_dir / "findings.json") or {}
    sweep = findings_obj.get("findings") if isinstance(findings_obj, dict) else None
    v2 = _read_json(review_dir / "findings.v2.json") or {}
    v2_extra = _v2_run_fields(v2)
    if v2 and not report:
        # A parallel/migrated run: the v2 document is the record of note.
        report = {"verdict": (v2.get("adjudication") or {}).get("verdict"),
                  "confidence": (v2.get("adjudication") or {}).get("confidence"),
                  "findings": []}

    raw_verdict = report.get("verdict")
    stages = meta.get("stages") or {}

    def _stage(name: str) -> dict:
        return stages.get(name) or {}

    errored = any(_stage(s).get("is_error")
                  for s in ("sweep", "editorial",
                            "tool_agent", "science_agent", "adjudicator"))
    has_report = bool(report)
    if has_report and errored:
        status = "partial"
    elif has_report:
        status = "complete"
    elif errored:
        status = "failed"
    else:
        status = "incomplete"

    counts = severity_counts(report.get("findings") or [])
    report_findings = [f for f in report.get("findings") or []
                       if isinstance(f, dict)]
    # The SAME source has to supply both counts, or the workbench shows a
    # non-image count from one run beside a total from another.
    if report_findings:
        n_non_image = sum(1 for f in report_findings if not is_image_finding(f))
    else:
        n_non_image = v2_extra.get("n_non_image_problem_findings", 0)
    return {
        "name": review_dir.name,
        "path": review_dir.name,
        "status": status,
        "kind": run_kind(v2) if v2 else "legacy",
        # Through `canonical`, so an archived run written in the retired
        # vocabulary sorts and filters beside a fresh one instead of forming
        # its own bucket. `verdict_recorded` keeps what the file actually says.
        "verdict": _verdicts.canonical(raw_verdict),
        "verdict_recorded": raw_verdict,
        "verdict_is_legacy": _verdicts.is_legacy(raw_verdict),
        "confidence": report.get("confidence"),
        "headline_severity": (report.get("headline") or {}).get("severity"),
        "n_findings": len(report.get("findings") or [])
        or v2_extra.get("n_problem_findings", 0),
        # What is left when the image track's own findings are set aside. The
        # image column already counts those, and on an image-only corpus the
        # two columns were the same number twice (310 of masliah's 311 problem
        # findings, measured 2026-08-21).
        "n_non_image_findings": n_non_image,
        "n_sweep_findings": len(sweep) if isinstance(sweep, list) else None,
        "severity_counts": counts,
        "worst_severity": _worst_severity(counts),
        "n_not_checked": len(report.get("not_checked") or []),
        **_analysed_at(review_dir, meta),
        "pipeline_version": meta.get("version"),
        "git_sha": meta.get("git_sha"),
        "prompt_sha256": meta.get("prompt_sha256"),
        "registry_sha256": meta.get("registry_sha256"),
        "cost_usd": _recorded_cost(meta),
        "wall_seconds": meta.get("total_wall_seconds"),
        "sandbox_level": (meta.get("sandbox") or {}).get("level")
        if isinstance(meta.get("sandbox"), dict) else None,
        "has_report_md": (review_dir / "report.md").is_file(),
        "has_bundle": (review_dir.parent / f"{review_dir.name}{_BUNDLE_SUFFIX}").is_dir(),
        **v2_extra,
    }


def _v2_run_fields(doc: dict) -> dict:
    """The findings-v2 additions to a run record (index schema addition,
    docs/specs/webapp_db.md section 9): the 1-9 axis beside the legacy one,
    per-technique counts, and the run_id. Empty for v1-only runs -- absence
    means 'no v2 document', never zero."""
    if not doc:
        return {}
    findings = [f for f in doc.get("findings") or [] if isinstance(f, dict)]
    sev9 = {str(n): 0 for n in range(1, 10)}
    techniques: dict[str, dict] = {}
    worst = None
    n_non_image = 0
    for f in findings:
        t = str(f.get("technique"))
        row = techniques.setdefault(t, {"findings": 0, "worst_9": None,
                                        "impossible": 0})
        action = (f.get("adjudication") or {}).get("action")
        if f.get("outcome") == "problem" and action != "discarded":
            row["findings"] += 1
            if not is_image_finding(f):
                n_non_image += 1
            sev = f.get("severity")
            if isinstance(sev, int):
                sev9[str(sev)] += 1
                if worst is None or sev > worst:
                    worst = sev
                if row["worst_9"] is None or sev > row["worst_9"]:
                    row["worst_9"] = sev
        if f.get("impossible"):
            row["impossible"] += 1
    adj = doc.get("adjudication") or {}
    n_problems = sum(v["findings"] for v in techniques.values())
    return {
        "run_id": doc.get("run_id"),
        "n_problem_findings": n_problems,
        "n_non_image_problem_findings": n_non_image,
        "severity9_counts": sev9,
        "worst_severity_9": worst,
        "techniques": techniques,
        "adjudicated": bool(adj.get("ran")),
        "n_v2_findings": len(findings),
        "severity_axis": ("assigned" if adj.get("ran") else "provisional"),
    }


def _recorded_cost(meta: dict):
    """The run's cost, or None when part of it was never reported.

    Codex reports tokens only, so its stages add 0.0 and a Codex run's
    `total_cost_usd` read as $0.00 (measured 2026-10-11, a gpt-5.6-terra
    review). Unknown is not free. Runs written before `cost_unreported_stages`
    existed are recognised by their backend and their zero.
    """
    total = meta.get("total_cost_usd")
    if meta.get("cost_unreported_stages"):
        return None
    if meta.get("llm_backend") == "codex" and not total:
        return None
    return total


def _analysed_at(review_dir: Path, meta: dict) -> dict:
    """When the run happened. Recorded stamp first; file mtime only if none.

    A file date is a different fact from a run date, so `analysed_at_source`
    says which. The workbench title attribute names a file date as a file date.
    """
    recorded = meta.get("analysed_at") if isinstance(meta, dict) else None
    if recorded:
        return {"analysed_at": recorded, "analysed_at_source": "recorded"}
    for cand in (review_dir / "run_meta.json", review_dir / "report.json"):
        if cand.is_file():
            when = datetime.fromtimestamp(cand.stat().st_mtime, tz=timezone.utc)
            return {
                "analysed_at": when.strftime("%Y-%m-%d %H:%M UTC"),
                "analysed_at_source": "file_mtime",
            }
    return {"analysed_at": None, "analysed_at_source": None}


def numeric_channel(runs: list[dict]) -> dict:
    if not runs:
        return _channel("did_not_run",
                        "no review directory: the numeric pipeline has not "
                        "been run on this paper")
    # An image-only run (`image-sweep`, kind `image_track`) writes a v2
    # document too; it says nothing about the numeric pipeline.
    numeric = [r for r in runs if r.get("kind") != "image_track"]
    if not numeric:
        return _channel("did_not_run",
                        "only image-track run(s) on this paper: the numeric "
                        "pipeline has not been run")
    complete = [r for r in numeric if r["status"] in ("complete", "partial")]
    if not complete:
        return _channel("refused",
                        "a review directory exists but holds no report.json; "
                        "the run did not reach a verdict",
                        subtype="no_report")
    if all(r.get("kind") == "partial_review" for r in complete):
        # Ran, but only as a PARTIAL pipeline: say so, so a one-tool run is
        # not read as the paper's numeric review.
        return _channel("ran", f"{len(complete)} partial pipeline run(s) "
                               "only; no complete review")
    return _channel("ran", f"{len(complete)} run(s) with a report")


def image_channel(paper_dir: Path, runs: list[dict], review_dirs_: list[Path]) -> dict:
    """The channel that needed a fifth state.

    Order matters: the most specific evidence wins. A retained detector result
    beats the harvest's leavings, and the harvest's leavings beat silence --
    but they are NOT the same claim, and the middle case is the common one.
    """
    # 1. A run that recorded the track's own status.
    for d in review_dirs_:
        meta = _read_json(d / "run_meta.json") or {}
        rec = (meta.get("stages") or {}).get("image_forensics")
        if isinstance(rec, dict):
            if rec.get("ran"):
                return _channel("ran", "the image track ran during a review",
                                run=d.name,
                                truncated=bool(rec.get("truncated_by_budget")
                                               or rec.get("truncated_by_timeout")))
            sub = rec.get("refusal_subtype")
            if sub:
                return _channel("refused", str(rec.get("detail") or ""),
                                subtype=sub, run=d.name)
    # 2. A retained detector result, inside a review or beside the paper.
    for cand in ([d / "image_analysis.json" for d in review_dirs_]
                 + [paper_dir / "image_duplication_findings.json"]):
        if cand.is_file():
            obj = _read_json(cand) or {}
            return _channel(
                "ran",
                f"{obj.get('n_duplicate_groups', '?')} duplicate group(s) of "
                f"{obj.get('n_panels', '?')} harvested panel(s)",
                result=cand.name,
                n_duplicate_groups=obj.get("n_duplicate_groups"),
                n_panels=obj.get("n_panels"),
                severity=obj.get("severity"),
                severity_before_quarantine=obj.get("severity_before_quarantine"))
    # 2b. THE REVIEW MANIFEST, which is a RETAINED RESULT and must be checked
    #     before the harvest leavings below.
    #
    #     `metascience-observatory-image-analysis/examples/exhibit_fired_groups.py` writes
    #     `panels/review/review_manifest.json`: one entry per fired group with
    #     the panel uids, the measurements, the adjudication verdict where
    #     there is one, and the artifact paths. That is an answer somebody kept.
    #
    #     Reported without this branch, such a paper came back
    #     `ran_result_discarded` -- the state added precisely so a discarded
    #     answer is not called a clean paper, misreporting a paper whose answer
    #     is on disk. Misreporting WHICH kind of absence is the whole failure
    #     the tri-state exists to prevent, so getting it wrong here is worse
    #     than not having the state at all.
    manifest = _read_json(paper_dir / "panels" / "review" / "review_manifest.json")
    if isinstance(manifest, dict) and manifest.get("groups") is not None:
        groups = manifest.get("groups") or []
        worst = _worst_severity({
            s_: sum(1 for g in groups
                    if str(g.get("severity_before_quarantine") or "").lower() == s_)
            for s_ in _SEVERITIES})
        return _channel(
            "ran",
            f"{len(groups)} fired group(s) with a reviewable exhibit; "
            f"{manifest.get('n_exhibits', 0)} still(s), "
            f"{manifest.get('n_videos', 0)} animation(s)",
            result="panels/review/review_manifest.json",
            n_groups=len(groups),
            n_exhibits=manifest.get("n_exhibits"),
            n_videos=manifest.get("n_videos"),
            severity_before_quarantine=worst)

    # 2c. A RECORDED REFUSAL. `image_forensics.retain` (metascience image-sweep) writes
    #     `panels/image_track_status.json` when the track declined, and it is
    #     checked BEFORE the harvest leavings below because it is the more
    #     specific fact: a scan whose pages are the rasters, or a download whose
    #     every stream is publisher chrome, is not a paper whose answer we
    #     mislaid. Without this branch those papers fall through to
    #     `ran_result_discarded`, which invites re-running a detector that will
    #     refuse again for the same unchanged reason.
    st = _read_json(paper_dir / "panels" / "image_track_status.json")
    if isinstance(st, dict) and st.get("ran") is False:
        return _channel(
            "refused", str(st.get("detail") or ""),
            subtype=st.get("refusal_subtype") or "unspecified",
            n_panels=st.get("n_panels"), n_eligible=st.get("n_eligible"))

    # 3. THE COMMON CASE. `panel_index.json` is written by
    #    `analyze_paper_images` itself, so its presence proves the detector
    #    ran -- and 369 of the 370 papers carrying one retain no result.
    #    Neither "ran" nor "did not run" is true of them.
    idx = paper_dir / "panels" / "panel_index.json"
    if idx.is_file():
        obj = _read_json(idx) or {}
        n = len(obj.get("panels") or [])
        return _channel(
            "ran_result_discarded",
            f"the detector ran and harvested {n} panel(s); no result file was "
            f"retained, so what it concluded is not recoverable without "
            f"re-running it. The panels themselves are still on disk.",
            n_panels=n)
    # 4. Panels harvested by the corpus describer, which is not the detector.
    if (paper_dir / "panels" / "panels.json").is_file():
        return _channel(
            "did_not_run",
            "panels were described for the cross-paper corpus sweep, but the "
            "within-paper duplication detector did not run")
    if (paper_dir / "panels").is_dir():
        return _channel(
            "did_not_run",
            "a panels/ directory exists but carries no detector index; "
            "treat the images as unexamined")
    return _channel("did_not_run", "no panel harvest on this paper")


def _evidence_group_counts(obj: dict) -> dict | None:
    """`{suspicious, undecided, cleared}` over the detector's groups,
    VERDICT-AWARE.

    The old single count keyed on `n_duplicate_groups`, i.e. every standing
    group — and only `explained` ever clears one, so every
    `insufficient_evidence` verdict stayed in the number. MEASURED on the
    fully-adjudicated discovery corpus 2026-09-08: 834 standing groups on
    180 papers, of which only 344 on 128 papers were `unexplained`. Dan,
    reading the table: "can that be the number that passed adjudication —
    the adjudication LLM thinks they are suspicious, not innocuous? it
    seems wrong right now."

    `suspicious` counts a standing group the adjudicator left
    `unexplained` OR never judged — an unadjudicated group must count,
    because "nobody looked" rendered as 0 is absence read as evidence
    (the review queue's default lens applies the same rule). `undecided`
    is a standing `insufficient_evidence`: it leaves the headline number
    but must stay VISIBLE (the table names it in the cell tooltip),
    because silently excluded it would read as cleared, which it is not.
    A standing group whose verdict says `explained` (a clearing write
    that never landed) counts as suspicious: the standing flag is the
    record of record and adjudication is downgrade-only.

    The `n_duplicate_groups` scalar is only a FALLBACK for an object with
    no groups list — a scalar cannot see verdicts. A manifest with no
    retained detector file is not a count at all.
    """
    groups = obj.get("duplicate_groups")
    if isinstance(groups, list):
        counts = {"suspicious": 0, "undecided": 0, "cleared": 0}
        for g in groups:
            if not isinstance(g, dict):
                continue
            if g.get("duplication_evidence") is False:
                counts["cleared"] += 1
                continue
            adj = g.get("adjudication")
            verdict = adj.get("verdict") if isinstance(adj, dict) else None
            if verdict == "insufficient_evidence":
                counts["undecided"] += 1
            else:
                counts["suspicious"] += 1
        return counts
    n = obj.get("n_duplicate_groups")
    if isinstance(n, int):
        return {"suspicious": n, "undecided": 0, "cleared": 0}
    return None


def image_finding_counts(paper_dir: Path,
                         review_dirs_: list[Path] | None = None) -> dict | None:
    """Verdict-aware image-duplicate group counts, or None if none kept.

    Prefers the retained detector file. An exhibit manifest is not a source
    of the count: a leftover `review_manifest.json` from an older pass is
    how 55 Masliah papers showed 264 groups the current detector never
    retained. A paper whose detector ran and discarded the result is None,
    not 0. All-zero counts mean a retained file with no groups.
    Independent of whether a numeric sweep also ran.
    """
    paper_dir = Path(paper_dir)
    obj = _read_json(paper_dir / "image_duplication_findings.json")
    if isinstance(obj, dict):
        from .image_plugin import available, load as _image_load
        if not available():
            # A retained image result this toolkit cannot read: unknown, not
            # zero (`image_finding_count` reads None, never 0).
            return {"suspicious": None, "undecided": None, "cleared": None,
                    "unavailable": "image analysis package not installed"}
        current_items = _image_load("image_forensics.screening_reconcile").current_items
        active = [i for i in current_items(paper_dir) if i["kind"] == "within"]
        return {"suspicious": len(active), "undecided": 0, "cleared": 0}
    rdirs = review_dirs_ if review_dirs_ is not None else review_dirs(paper_dir)
    for d in rdirs:
        obj = _read_json(d / "image_analysis.json")
        if isinstance(obj, dict):
            # Legacy model verdicts are audit evidence, not publication rights.
            return {"suspicious": 0, "undecided": 0, "cleared": 0}
    return None


def image_finding_count(paper_dir: Path,
                        review_dirs_: list[Path] | None = None) -> int | None:
    """The table's headline number: standing groups the adjudicator left
    unexplained or never judged. See `_evidence_group_counts`."""
    counts = image_finding_counts(paper_dir, review_dirs_)
    return None if counts is None else counts["suspicious"]


def cross_paper_channel(paper_dir: Path) -> dict:
    """Has this paper been checked against the OTHER papers in its corpus?

    A DIFFERENT QUESTION FROM `image_channel`, and the reason it needs its own
    channel rather than a field on that one. `analyze_paper_images` asks whether
    a panel repeats inside one paper; the corpus sweep asks whether a panel
    appears in somebody else's. A paper can be exhaustively checked against
    itself and never once compared with its neighbours, and until this function
    existed the workbench reported that paper exactly like one that had been --
    `image_forensics: ran`, nothing else said.

    The stakes are the sharper half of the two. A within-paper repeat is often
    innocent (one field photographed for two figures); the same panel under two
    different authors' names is not, and it is the finding a reader is least
    able to reach on their own, because it is invisible from inside either
    paper.

    Ordered most-specific-first, like `image_channel`:

      1. `panels/review/cross_paper_matches.json` -- the machine-readable
         answer `image_corpus.write_cross_paper_matches` leaves. A `ran` here
         means a real comparison against a real corpus.
      2. `cross_paper_image_reuse.md` alone -- runs from before the JSON
         existed. The sweep DID run and did find something; what it found is
         prose, so a reviewer can read it but no surface can draw it. `ran`,
         with the limitation named rather than implied.
      3. `panels/panels.json` -- the describer ran, which is the sweep's input
         and not the sweep. Descriptors without a sweep are a prepared paper,
         not a compared one.
      4. nothing -- `did_not_run`.

    There is no `ran_result_discarded` branch and that is deliberate: the sweep
    writes nothing into a paper that had no match, so a swept paper with no hits
    and a never-swept paper look identical FROM INSIDE THE PAPER. Only the
    corpus knows which, so `scan_corpus` overrides this to `unknown` when the
    root carries no sweep at all -- see `_apply_corpus_sweep_state`. Calling
    that absence `did_not_run` from here would be a guess dressed as a finding.
    """
    matches = paper_dir / "panels" / "review" / "cross_paper_matches.json"
    obj = _read_json(matches) if matches.is_file() else None
    if isinstance(obj, dict) and obj.get("matches") is not None:
        rows = obj.get("matches") or []
        others = {
            (str((r.get("other_side") or {}).get("corpus_root") or ""),
             str((r.get("other_side") or {}).get("paper_key") or ""))
            for r in rows if isinstance(r, dict)}
        others.discard(("", ""))
        # Keyed on (root, paper_key), never on a bare id: 14 paper ids in this
        # configuration exist in two corpus roots, so counting distinct ids
        # would merge two different papers that happen to share a DOI slug.
        n_adjudicated = sum(
            1 for r in rows if isinstance(r, dict) and r.get("adjudication"))
        return _channel(
            "ran",
            f"{len(rows)} panel match(es) with {len(others)} other paper(s) in "
            f"the same corpus"
            + (f"; {n_adjudicated} adjudicated" if n_adjudicated else
               "; none adjudicated, so no innocuous explanation has been sought"),
            result="panels/review/cross_paper_matches.json",
            n_matches=len(rows),
            n_other_papers=len(others),
            n_adjudicated=n_adjudicated)
    if matches.is_file():
        # The file is there and unreadable or malformed. That is OUR failure and
        # must not be filed as the paper having no cross-paper hits.
        return _channel(
            "unknown",
            "cross_paper_matches.json exists but could not be parsed, so "
            "whether this paper shares panels with another is unknown")
    if (paper_dir / "cross_paper_image_reuse.md").is_file():
        return _channel(
            "ran",
            "the corpus sweep matched this paper against another, but this run "
            "predates the JSON writer, so the finding exists only as prose and "
            "cannot be drawn. Re-run `metascience image-corpus` to get a "
            "reviewable version.",
            result="cross_paper_image_reuse.md",
            prose_only=True)
    if (paper_dir / "panels" / "panels.json").is_file():
        return _channel(
            "did_not_run",
            "panels were described for the corpus sweep, but no cross-paper "
            "result reached this paper")
    return _channel(
        "did_not_run",
        "no panel descriptors on this paper, so it cannot have been compared "
        "with any other")


def text_channel(paper_dir: Path, review_dirs_: list[Path]) -> dict:
    for d in review_dirs_:
        meta = _read_json(d / "run_meta.json") or {}
        rec = (meta.get("stages") or {}).get("text_forensics")
        if isinstance(rec, dict):
            if rec.get("ran"):
                return _channel("ran", "the tortured-phrases track ran",
                                run=d.name)
            sub = rec.get("refusal_subtype")
            if sub:
                return _channel("refused", str(rec.get("detail") or ""),
                                subtype=sub, run=d.name)
        if (d / "text_forensics.json").is_file():
            obj = _read_json(d / "text_forensics.json") or {}
            n, unit = _text_track_count(obj)
            return _channel("ran", f"{n} {unit}", n_rows=n, run=d.name)
    return _channel("did_not_run", "no tortured-phrase screening on this paper")


def _text_track_count(obj: dict) -> tuple[int, str]:
    """Count from the file's real shape, not a key that used to be at the top.

    Modern `text_forensics.json` is `{findings_rows, result: {matches}}`.
    `obj.get("matches")` is always missing there, so the detail used to read
    "0 fingerprint match(es)" on every current artifact.
    """
    rows = obj.get("findings_rows")
    if isinstance(rows, list):
        return len(rows), "tortured-phrase row(s)"
    result = obj.get("result") if isinstance(obj.get("result"), dict) else obj
    matches = result.get("matches") if isinstance(result, dict) else None
    if isinstance(matches, list):
        return len(matches), "fingerprint match(es)"
    return 0, "fingerprint match(es)"


def figures_channel(paper_dir: Path, review_dirs_: list[Path]) -> dict:
    figmap = paper_dir / "panels" / "figmap"
    if figmap.is_dir():
        n = sum(1 for _ in figmap.glob("*.png"))
        if n:
            return _channel("ran", f"{n} figure crop(s) extracted", n_figures=n)
        return _channel(
            "ran_result_discarded",
            "a figmap/ directory exists but holds no crops; the figure pass "
            "ran and produced nothing readable")
    if (paper_dir / "figures").is_dir():
        return _channel("ran", "figures were extracted")
    for d in review_dirs_:
        if (d / "figures").is_dir():
            return _channel("ran", "figures were extracted", run=d.name)
    return _channel("did_not_run", "figures were not extracted")


#: Evidence a human can LOOK at, by the filename each producer writes.
#:
#: Six producers, six naming conventions, and they were never reconciled:
#:
#:   exhibit_fired_groups.py     panels/review/group01_transformed_match.png
#:   cli.py --montage            panels/review/group_1_identical_stream.png
#:   animate_panel_match.py      panels/review/fig3_h_i_match.mp4  + _key_*.png
#:   render_review_figure        duplication_review.png
#:   animate --pubpeer           panels/review/fig3_e_f_pubpeer.png
#:   extract_figures             panels/figmap/Figure_3_p004.png
#:
#: The mismatch is not cosmetic: `agent._image_adjudication_prompt` globs
#: `panels/review/group{i:02d}_*.png`, which ONLY the manual
#: `exhibit_fired_groups.py` produces -- so the `--montage` flag writes files
#: the adjudicator cannot see. Cataloguing them here does not fix that; it
#: makes it visible, and gives the workbench one list to render.
_EVIDENCE_KINDS = (
    # (suffix test, kind, what it shows)
    (lambda n: n.endswith((".mp4", ".webm")), "animation",
     "a blink/warp animation of the match"),
    (lambda n: "_key_" in n and n.endswith(".png"), "key_frame",
     "a single frame from the animation"),
    (lambda n: n.endswith("_pubpeer.png"), "pubpeer_exhibit",
     "the boxed side-by-side written for a public comment"),
    (lambda n: n.startswith(("group", "group_")) and n.endswith(".png"), "exhibit",
     "panels side by side, duplicated region boxed"),
    (lambda n: n.endswith(".gif"), "animation",
     "a blink comparison"),
)


#: `group07_transformed_match.png` / `group_7_identical_stream.mp4` -> 7,
#: and since 2026-09-08 `10.1152--ajpgi.00313.2020_group01_transformed_match.mp4`
#: -> 1: the video writer prefixes the DOI slug, so the token is searched
#: for at a `_` boundary rather than anchored at the start. All three
#: writers are matched because all three exist on disk.
_GROUP_STEM_RE = re.compile(r"(?:^|_)group[_]?(\d+)[_.]")


def _manifest_by_group(paper_dir: Path) -> dict[int, dict]:
    """`review_manifest.json` keyed by group number, or empty.

    THE PICTURE IS NOT THE FINDING. `exhibit_fired_groups.py` writes one entry
    per fired group carrying the panel uids, the measurements (`n_inliers`,
    `grain_residual_r`, `matched_frac`, `rotation_deg`, `scale`, `flip`, and
    since 1.34.0 the `control` block: the same two panels correlated
    UNALIGNED beside the aligned r, with `exhibit_gate` saying whether the
    alignment bought anything), the adjudication verdict where there is one,
    and -- for a group with NO artifact -- the REASON there is none.

    Without the join a reviewer gets an image and no numbers beside it, which
    is the worst possible form for image evidence: a picture of two similar
    panels is persuasive in exactly the way the measurements exist to
    discipline. `grain_residual_r` runs BACKWARDS on shared chart templates,
    so a match that looks convincing and scores 0.9 grain may be a plot
    template rather than a duplicated micrograph, and only the number says so.

    Keyed on the group NUMBER parsed from the filename rather than on
    `group_index`: the filename is what both writers agree on, and the
    manifest's `group_index` is 1-based while `image_track`'s is 0-based. Two
    fields of the same name counting from different origins is a join waiting
    to go wrong, so this one does not use either.
    """
    manifest = _read_json(paper_dir / "panels" / "review" / "review_manifest.json")
    if not isinstance(manifest, dict):
        return {}
    out: dict[int, dict] = {}
    for entry in manifest.get("groups") or []:
        if not isinstance(entry, dict):
            continue
        # Prefer the artifact filename the entry names; fall back to its index.
        num = None
        for key in ("exhibit_png", "video_mp4"):
            name = str(entry.get(key) or "")
            if name:
                m = _GROUP_STEM_RE.search(Path(name).name)
                if m:
                    num = int(m.group(1))
                    break
        if num is None and isinstance(entry.get("group_index"), int):
            num = entry["group_index"]
        if num is not None:
            out[num] = entry
    return out


def evidence_assets(paper_dir: Path) -> list[dict]:
    """Every image or video a reviewer could look at, newest first.

    VIDEO IS WHY THE WORKBENCH IS NOT THE BUNDLE. `animate_panel_match.py`
    writes ~6 MB H.264 MP4s (measured: `fig3_h_i_match.mp4`, 5,877 KB), and
    `bundle.py` exists to produce a file that opens from `file://` with
    everything inlined. A 6 MB video base64'd into a self-contained HTML page
    is a 8 MB page per clip. The workbench serves these from disk instead,
    which is a capability the offline bundle structurally cannot have.

    Paths are recorded RELATIVE to the paper directory: the index is read by a
    server that resolves them under a corpus root, and an absolute path from
    this machine would both leak the operator's home and break on any other.
    """
    out: list[dict] = []
    by_group = _manifest_by_group(paper_dir)
    for sub in (paper_dir / "panels" / "review", paper_dir):
        if not sub.is_dir():
            continue
        for f in sorted(sub.iterdir()):
            if not f.is_file():
                continue
            name = f.name
            if not name.endswith((".png", ".jpg", ".jpeg", ".mp4", ".webm", ".gif")):
                continue
            kind = shows = None
            for test, k, s in _EVIDENCE_KINDS:
                if test(name):
                    kind, shows = k, s
                    break
            if kind is None:
                if name in ("duplication_review.png", "media_duplication_review.png.png"):
                    kind, shows = "review_figure", "per-group thumbnails and a difference image"
                elif sub.name == "review":
                    kind, shows = "exhibit", "an exhibit written for human review"
                else:
                    continue          # a stray image beside the paper is not evidence
            try:
                size = f.stat().st_size
            except OSError:
                size = None
            asset = {
                "path": f.relative_to(paper_dir).as_posix(),
                "name": name,
                "kind": kind,
                "shows": shows,
                "bytes": size,
                "is_video": kind == "animation" and name.endswith((".mp4", ".webm")),
            }
            m = _GROUP_STEM_RE.search(name)
            entry = by_group.get(int(m.group(1))) if m else None
            if entry:
                asset["group"] = {
                    "kind": entry.get("kind"),
                    "panels": entry.get("panels"),
                    "figure_labels": entry.get("figure_labels"),
                    "spans_figures": entry.get("spans_figures"),
                    "sentence": entry.get("sentence"),
                    "measurements": entry.get("measurements"),
                    "adjudication": entry.get("adjudication"),
                    "severity_before_quarantine":
                        entry.get("severity_before_quarantine"),
                }
            out.append(asset)

    # Groups the detector fired on for which NO picture exists, carried with the
    # reason. A blank pane says nothing; "the animation would show nothing
    # moving, because the transform is near-identity" is a fact about the match
    # and belongs beside the ones that do have pictures. Same distinction
    # `ran_result_discarded` makes one level up.
    drawn = {int(_GROUP_STEM_RE.search(a["name"]).group(1))
             for a in out if _GROUP_STEM_RE.search(a["name"])}
    for num, entry in sorted(by_group.items()):
        if num in drawn:
            continue
        out.append({
            "path": None, "name": f"group{num:02d}", "kind": "no_artifact",
            "shows": str(entry.get("video_reason")
                         or "no exhibit was drawn for this group"),
            "bytes": None, "is_video": False,
            "group": {
                "kind": entry.get("kind"), "panels": entry.get("panels"),
                "figure_labels": entry.get("figure_labels"),
                "sentence": entry.get("sentence"),
                "measurements": entry.get("measurements"),
                "adjudication": entry.get("adjudication"),
            },
        })
    return out


def review_state(paper_dir: Path) -> dict:
    """The human decisions, and the third state that is not a decision.

    `unreviewed` is NOT `withheld`. A paper nobody has opened must never render
    as a paper someone declined to publish, and a UI that shows both as "not
    published" makes the reviewer's silence look like their judgement.

    Schema 1.1 adds `paper.status` (`unreviewed` | `in_progress` | `complete`).
    The project table's "human reviewed" column counts `complete` only.
    A 1.0 file with any finding decision is `in_progress`, not complete.
    """
    obj = _read_json(paper_dir / "review.json")
    if not isinstance(obj, dict):
        return {"reviewed": False,
                "publication": {"state": "unreviewed"},
                "reporting": {"state": "unreviewed"},
                "n_decisions": 0,
                "paper_status": "unreviewed",
                "reviewed_by": None,
                "reviewed_at": None,
                "submitted_to_pubpeer": None,
                "pubpeer_url": None,
                "pubpeer_note": None}

    def _gate(key: str) -> dict:
        g = obj.get(key)
        if not isinstance(g, dict):
            return {"state": "unreviewed"}
        if g.get("approved") is True:
            return {"state": "approved", "reviewer": g.get("reviewer"),
                    "at": g.get("at")}
        if g.get("approved") is False:
            return {"state": "withheld", "reviewer": g.get("reviewer"),
                    "at": g.get("at"),
                    "reason": g.get("withheld_reason")}
        return {"state": "unreviewed"}

    findings = obj.get("findings")
    issues = obj.get("issues")
    n_old = len(findings) if isinstance(findings, dict) else 0
    n_new = len(issues) if isinstance(issues, dict) else 0
    paper = obj.get("paper") if isinstance(obj.get("paper"), dict) else {}
    status = paper.get("status")
    if status not in ("unreviewed", "in_progress", "complete"):
        status = "in_progress" if (n_old or n_new) else "unreviewed"
    # Missing is not False: we have not recorded a submission. The workbench
    # checkbox treats both as unchecked; the project count only adds True.
    if "submitted_to_pubpeer" in paper:
        submitted = bool(paper.get("submitted_to_pubpeer"))
    else:
        submitted = None
    url = paper.get("pubpeer_url")
    note = paper.get("pubpeer_note")
    return {"reviewed": True,
            "publication": _gate("publication"),
            "reporting": _gate("reporting"),
            "n_decisions": n_new or n_old,
            "paper_status": status,
            "reviewed_by": paper.get("reviewed_by") or paper.get("reviewer"),
            "reviewed_at": paper.get("reviewed_at") or paper.get("at"),
            "submitted_to_pubpeer": submitted,
            "pubpeer_url": url if isinstance(url, str) and url else None,
            "pubpeer_note": note if isinstance(note, str) and note else None}


def viewed_state(paper_dir: Path, review: dict | None = None) -> dict:
    """Has a human ever OPENED this paper's results page?

    THREE SOURCES, NAMED, because they are three different facts and a bare
    yes/no would fuse them:

    `recorded`              `views.json` holds at least one view. Somebody
                            opened the review page and the workbench saw it.
    `unreadable`            The file beside the paper exists and could not be
                            parsed. Whether anyone opened it is UNKNOWN, which
                            is not `False` -- reading a torn file as "nobody
                            looked" is the substitution this toolkit exists to
                            catch, committed by the scanner.
    `inferred_from_review`  No `views.json`, but a human recorded a decision
                            or moved the paper off `unreviewed`. That paper
                            was certainly open in front of somebody -- view
                            tracking simply did not exist yet. MEASURED
                            2026-08-22: 53 papers in the corpora have a
                            `review.json`, 20 of them `complete`. Reporting
                            those as never-viewed would tell the reader that
                            twenty papers a human demonstrably reviewed had
                            never been opened.
    `none`                  Nothing recorded.

    `none` is NOT "nobody has read this paper". Nothing was tracking before
    `views_io` existed, and a `viewer.html` bundle opened from `file://`, a
    PDF opened in Preview, or a colleague reading over a shoulder cannot
    report back by construction. The UI renders this as "no view recorded".
    """
    from .views_io import load_views

    doc = load_views(paper_dir)
    if doc.get("unreadable"):
        return {"viewed": None, "n_views": None, "first_at": None,
                "last_at": None, "viewers": [], "source": "unreadable"}
    viewers = doc.get("viewers") or []
    if viewers:
        return {"viewed": True,
                "n_views": doc.get("n_views") or len(viewers),
                "first_at": doc.get("first_at"),
                "last_at": doc.get("last_at"),
                "viewers": [v.get("name") for v in viewers],
                "source": "recorded"}

    rev = review if isinstance(review, dict) else review_state(paper_dir)
    judged = bool(rev.get("n_decisions")) or \
        rev.get("paper_status") in ("in_progress", "complete") or \
        (rev.get("publication") or {}).get("state") in ("approved", "withheld")
    if judged:
        return {"viewed": True,
                # Not a view count: we know it was open, not how often.
                "n_views": 0,
                "first_at": None,
                "last_at": rev.get("reviewed_at"),
                "viewers": [rev.get("reviewed_by")],
                "source": "inferred_from_review"}

    return {"viewed": False, "n_views": 0, "first_at": None, "last_at": None,
            "viewers": [], "source": "none"}


def _paper_identity(paper_dir: Path, review_dirs_: list[Path]) -> dict:
    """Title, authors, journal, DOI -- from the richest source that exists.

    `metadata.json` (written by `paper_metadata.ensure_metadata`) is preferred
    when it has a title: that is the Crossref/OpenAlex/PubMed cascade, which
    carries first-author names and journal/volume/issue the XML and the
    directory name often lack. The scanner does not fetch; it only reads.

    An image-only paper has no `findings.json`, so without the cache the
    identity has to come off the fetcher's provenance sidecar or, failing
    that, the directory name. The directory name IS a DOI with `/` written
    as `--`, which is enough to identify the paper even when nothing else
    survives.
    """
    from .paper_metadata import (
        doi_from_slug, first_author, has_displayable, identity_from_metadata,
        load_cached,
    )

    slug = paper_dir.name
    out: dict[str, Any] = {"paper_id": slug,
                           "doi": doi_from_slug(slug),
                           "title": None, "authors": None, "first_author": None,
                           "journal": None, "volume": None, "issue": None,
                           "year": None,
                           "identity_source": "directory_name"}
    cached = load_cached(paper_dir)
    if has_displayable(cached):
        out.update(identity_from_metadata(cached))
        out["identity_source"] = "metadata.json"
        return out
    for d in review_dirs_:
        obj = _read_json(d / "findings.json")
        if isinstance(obj, dict) and (obj.get("paper_title") or obj.get("paper_metadata")):
            pm = obj.get("paper_metadata") or {}
            title = obj.get("paper_title") or pm.get("title")
            authors = pm.get("authors")
            out.update({"title": title, "authors": authors,
                        "first_author": first_author(authors) if isinstance(authors, str) else None,
                        "journal": pm.get("journal"),
                        "volume": pm.get("volume"), "issue": pm.get("issue"),
                        "year": pm.get("year"),
                        "doi": pm.get("doi") or out["doi"],
                        "identity_source": f"findings.json ({d.name})"})
            return out
    for cand in (paper_dir / f"{slug}.provenance.json", paper_dir / "provenance.json"):
        obj = _read_json(cand)
        if isinstance(obj, dict):
            meta = obj.get("metadata") if isinstance(obj.get("metadata"), dict) else obj
            title = meta.get("title")
            if title:
                authors = meta.get("authors")
                out.update({"title": title, "authors": authors,
                            "first_author": first_author(authors) if isinstance(authors, str) else None,
                            "journal": meta.get("journal"),
                            "volume": meta.get("volume"), "issue": meta.get("issue"),
                            "year": meta.get("year"),
                            "doi": meta.get("doi") or out["doi"],
                            "identity_source": cand.name})
                return out
    from .paper_metadata import xml_seed
    seed = xml_seed(paper_dir)
    if seed.get("title"):
        out.update(identity_from_metadata(seed))
        out["doi"] = seed.get("doi") or out["doi"]
        out["identity_source"] = "xml"
        return out
    return out


def scan_paper(paper_dir: Path, *, corpus_root: Path | None = None,
               image_publication_counts: bool = True) -> dict:
    """One paper, from whatever exists. Never raises on a malformed corpus.

    `dir` is the path relative to `corpus_root` when one is given, so a paper
    living in `done/<slug>` is addressable. Without a root it stays the
    directory name, which is what every existing caller expects.
    """
    paper_dir = Path(paper_dir)
    if corpus_root is not None:
        try:
            rel = paper_dir.relative_to(Path(corpus_root)).as_posix()
        except ValueError:
            rel = paper_dir.name
    else:
        rel = paper_dir.name
    rdirs = review_dirs(paper_dir)
    runs = [scan_run(d) for d in rdirs]
    # A paper-level findings.v2.json with no review directory is a MIGRATED
    # track-only record (the masliah orphan class): synthesize its run row so
    # 544 converted papers do not read as never-analysed.
    if (paper_dir / "findings.v2.json").is_file():
        v2 = _read_json(paper_dir / "findings.v2.json") or {}
        extra = _v2_run_fields(v2)
        if extra:
            legacy = v2.get("legacy") or {}
            runs = runs + [{
                "name": "(migrated)", "path": ".", "status": "partial",
                "verdict": _verdicts.canonical(
                    (v2.get("adjudication") or {}).get("verdict")),
                "verdict_recorded": None, "verdict_is_legacy": False,
                "confidence": None, "headline_severity": None,
                "n_findings": extra.get("n_problem_findings", 0),
                "n_non_image_findings":
                    extra.get("n_non_image_problem_findings", 0),
                "n_sweep_findings": None,
                "severity_counts": severity_counts([]),
                "worst_severity": None, "n_not_checked": 0,
                "analysed_at": legacy.get("analysed_at"),
                "analysed_at_source": legacy.get("analysed_at_source"),
                "pipeline_version": legacy.get("pipeline_version"),
                "git_sha": None, "prompt_sha256": None,
                "registry_sha256": None, "cost_usd": None,
                "wall_seconds": None, "sandbox_level": None,
                "has_report_md": False, "has_bundle": False,
                **extra,
            }]
    channels = {
        "numeric": numeric_channel(runs),
        "image_forensics": image_channel(paper_dir, runs, rdirs),
        # A SEPARATE CHANNEL, not a field on `image_forensics`: within-paper and
        # cross-paper are different questions with different evidence and
        # different stakes, and folding them together let a paper checked only
        # against itself read as fully checked. Omitted entirely when the screen
        # is off, so the index never answers a question we stopped asking.
        **({"cross_paper": cross_paper_channel(paper_dir)}
           if cross_paper_enabled() else {}),
        "tortured_phrases": text_channel(paper_dir, rdirs),
        "figures": figures_channel(paper_dir, rdirs),
    }
    # A PARTIAL PIPELINE never supplies the paper's verdict or counts: a
    # one-tool or unadjudicated run is an experiment, listed in `runs` but not
    # the review the paper row summarises (`run_kind`, pipeline_config.py).
    latest = next((r for r in runs if r["status"] in ("complete", "partial")
                   and r.get("kind") != "partial_review"), None)
    review = review_state(paper_dir)
    # Catalog discovery must not reconstruct exhibits or decode PDF image streams.
    # The retained image catalog supplies review counts independently.
    img_counts = image_finding_counts(paper_dir, rdirs) if image_publication_counts else None
    return {
        **_paper_identity(paper_dir, rdirs),
        "dir": rel,
        "channels": channels,
        # `n_runs` is not `len(runs)` by accident: a paper with three review
        # directories has been analysed three times, possibly across a version
        # boundary that CHANGELOG.md says makes them incomparable. The workbench
        # shows the latest and says how many others there are, rather than
        # picking one silently.
        "n_runs": len(runs),
        "runs": runs,
        "latest_run": latest["name"] if latest else None,
        "verdict": latest["verdict"] if latest else None,
        "worst_severity": latest["worst_severity"] if latest else None,
        "n_findings": latest["n_findings"] if latest else None,
        "n_non_image_findings": (latest.get("n_non_image_findings")
                                 if latest else None),
        # The release that produced the run the rest of this record describes.
        # Two reviews across a MINOR boundary are not comparable (CHANGELOG.md),
        # so the workbench has to be able to say which one it is looking at.
        "pipeline_version": latest.get("pipeline_version") if latest else None,
        # Over the paper's REVIEW runs: a partial experiment's severity-9
        # row must not become the paper's worst level beside a clean review.
        "worst_severity_9": max(
            (r["worst_severity_9"] for r in runs
             if isinstance(r.get("worst_severity_9"), int)
             and r.get("kind") != "partial_review"), default=None),
        # Standing groups the adjudicator left unexplained or never judged;
        # `insufficient_evidence` survivors sit beside it, NOT inside it —
        # the table tooltip names them, so "couldn't judge" neither inflates
        # the headline nor silently reads as cleared.
        "n_image_findings": img_counts["suspicious"] if img_counts else None,
        "n_image_undecided": img_counts["undecided"] if img_counts else None,
        "cost_usd": latest["cost_usd"] if latest else None,
        "analysed_at": latest["analysed_at"] if latest else None,
        "analysed_at_source": (latest.get("analysed_at_source")
                               if latest else None),
        "review": review,
        # A SEPARATE FACT FROM `review`, and the reason it is not a field on
        # it: opening a paper is not judging it. A view must never move a
        # paper's review status, and this key must never be read as one.
        "viewed": viewed_state(paper_dir, review),
        "sources": _sources(paper_dir),
        # Enumerated in the index rather than discovered per-page, so the
        # corpus screen can say "3 papers have a visual exhibit" -- which is
        # the only way anyone finds the three, given that exhibits are written
        # by manual scripts nothing in the pipeline calls.
        "evidence": evidence_assets(paper_dir) if image_publication_counts else [],
        "evidence_indexed": image_publication_counts,
    }


def _sources(paper_dir: Path) -> dict:
    """What of the paper we actually hold, and why not, when we hold nothing.

    `state` is the field a corpus screen sorts on, and `not_fetched` is the one
    that had to be added: 49 of 423 directories in `cerebrolysin_papers` carry
    a `.landing.html` and a `.provenance.json` and no PDF. The publisher served
    an interstitial. Reporting those as "no text" alongside a paper we simply
    have not processed conflates a fetch that FAILED with a fetch nobody
    attempted, and only the first is a thing anyone can act on -- by fetching
    it again, by hand, or from a library.
    """
    pdf_paths = sorted(paper_dir.glob("*.pdf"),
                       key=lambda p: p.stat().st_size, reverse=True)
    pdf = bool(pdf_paths)
    xml = any(paper_dir.glob("*.xml"))
    body = (paper_dir / "body.md").is_file()
    landing = any(paper_dir.glob("*.landing.html"))
    attempted = landing or any(paper_dir.glob("*.provenance.json")) \
        or (paper_dir / "provenance.json").is_file()

    if pdf or xml or body:
        state = "held"
    elif attempted:
        state = "not_fetched"
    else:
        state = "empty"

    out = {
        "state": state,
        "pdf": pdf,
        "xml": xml,
        "body_md": body,
        "landing_page_only": landing and not (pdf or xml or body),
        "n_supplements": sum(1 for _ in (paper_dir / "supplementary").glob("*"))
        if (paper_dir / "supplementary").is_dir() else 0,
    }
    probe = probe_main_pdf_stub(paper_dir, pdf_paths=pdf_paths, has_xml=xml)
    if probe is not None:
        out.update(probe)
    return out


def probe_main_pdf_stub(paper_dir: Path, *,
                        pdf_paths: "list[Path] | None" = None,
                        has_xml: "bool | None" = None) -> "dict | None":
    """Is the main PDF a publisher preview stub? None when N.A. (no pdf+xml).

    A one-page PDF beside a full-text XML is a PREVIEW STUB, not the paper --
    and "pdf: true" invites the reader to believe the figures were available
    to every image check. MEASURED 2026-08-22:
    `10.1016--j.neuroscience.2024.05.006` holds a 1.9 MB, ONE-page
    ScienceDirect first-page preview (so file size is not the tell; the page
    count is), and its v1.3.0 review ran figure-blind without saying so
    anywhere a reviewer would look. Gated on XML so only PDFs whose stub-ness
    is decidable AND actionable are opened (the XML proves full text exists
    to re-fetch); fitz reads a page count in ~0.4 ms without parsing pages.
    Absent fitz, the count is None -- unknown, never a claim either way.

    Shared by the corpus scanner (`_sources`), the pre-spend warning in
    `metascience analyze`, and the run limitation in the parallel pipeline,
    so all three surfaces answer "was the paper actually here" the same way.
    """
    if pdf_paths is None:
        pdf_paths = sorted(paper_dir.glob("*.pdf"),
                           key=lambda p: p.stat().st_size, reverse=True)
    if has_xml is None:
        has_xml = any(paper_dir.glob("*.xml"))
    if not pdf_paths or not has_xml:
        return None
    try:
        import fitz
        with fitz.open(pdf_paths[0]) as doc:
            pages = int(doc.page_count)
    except Exception:
        pages = None   # no fitz, or an unopenable PDF: unknown, recorded
    result: dict[str, Any] = {"main_pdf_pages": pages}
    if pages is not None and pages <= 2:
        result["pdf_suspect_stub"] = True
    return result


#: Directories in a corpus root that are not papers. Everything else is,
#: including directories holding nothing but a failed fetch.
#: `done/` is the post-run archive; `priority/` and
#: `prioritized_cerebrolysin_papers/` are pre-run queues. All hold paper
#: directories one level down, and none is itself a paper.
from forensic_metascience_ai_toolkit.discovery import _NOT_A_PAPER as _NOT_A_PAPER

#: Scaffolding dirs whose *children* are papers. One extra level only: a
#: recursive walk would double-count any paper that also sat at the top level.
from forensic_metascience_ai_toolkit.discovery import _NESTED_PAPER_DIRS as _NESTED_PAPER_DIRS

#: Names that live INSIDE a paper. A parent that contains only these is
#: still a paper; a parent that contains other paper directories is a nest
#: (a batch folder such as `grok_run/`).
from forensic_metascience_ai_toolkit.discovery import _PAPER_INTERNAL as _PAPER_INTERNAL

#: Known scaffolding we do not open even when it happens to hold directories.
#: `failed/` is a batch dump, not a review queue; `logs`/`reviews`/`blinded`
#: are not paper corpora.
from forensic_metascience_ai_toolkit.discovery import _DO_NOT_DESCEND as _DO_NOT_DESCEND


from forensic_metascience_ai_toolkit.discovery import _is_paper_internal as _is_paper_internal


from forensic_metascience_ai_toolkit.discovery import _looks_like_paper_leaf as _looks_like_paper_leaf


from forensic_metascience_ai_toolkit.discovery import _has_paper_children as _has_paper_children


from forensic_metascience_ai_toolkit.discovery import _should_descend as _should_descend


from forensic_metascience_ai_toolkit.discovery import iter_paper_dirs as iter_paper_dirs


from forensic_metascience_ai_toolkit.discovery import _newest_run_date as _newest_run_date


from forensic_metascience_ai_toolkit.discovery import _dedupe_paper_copies as _dedupe_paper_copies


from forensic_metascience_ai_toolkit.discovery import looks_like_paper as looks_like_paper


def scan_corpus(root: str | Path, limit: int | None = None, *,
                image_publication_counts: bool = True) -> dict:
    """Every paper under `root`, including one extra level of batch folders.

    `done/<slug>` and `grok_run/<slug>` are papers; `done/` and `grok_run/`
    are not. Deeper than that is not scanned: `panels/` and
    `forensic_review/` live inside a paper, and walking them would mint
    phantom rows. Two copies of the same DOI (top-level fetch vs a batch
    folder) are two directories and two rows; `dir` is what distinguishes
    them.
    """
    root = Path(root)
    papers: list[dict] = []
    errors: list[dict] = []
    if not root.is_dir():
        return {"schema_version": SCHEMA_VERSION, "root": root.as_posix(),
                "papers": [], "errors": [{"path": root.as_posix(),
                                          "error": "not a directory"}],
                "totals": _totals([])}
    for d in iter_paper_dirs(root):
        try:
            papers.append(scan_paper(d, corpus_root=root,
                                     image_publication_counts=image_publication_counts))
        except Exception as exc:  # noqa: BLE001 - one bad paper is not a bad corpus
            try:
                rel = d.relative_to(root).as_posix()
            except ValueError:
                rel = d.name
            errors.append({"path": rel,
                           "error": f"{type(exc).__name__}: {exc}"})
        if limit and len(papers) >= limit:
            break
    _apply_corpus_sweep_state(root, papers)
    _apply_pubpeer_labels(root, papers)
    return {"schema_version": SCHEMA_VERSION, "root": root.as_posix(),
            "papers": papers, "errors": errors, "totals": _totals(papers)}


#: Written by `image_corpus.write_reports` once per swept corpus. Its presence
#: is the only evidence, from outside a paper, that the sweep ran at all.
_CORPUS_SWEEP_REPORT = "image_corpus_report.md"


def _load_pubpeer_labels(root: Path) -> tuple[dict[str, dict], set[str], bool]:
    """`(by_paper_dir, unknown_dois, asked)`.

    Absence of a file is not "no paper has a PubPeer entry" -- it is that
    we have not asked. Unknown DOIs are lookup failures, not empty pages.
    """
    for cand in (root / ".image_track" / "pubpeer_labels.json",
                 root / "pubpeer_labels.json"):
        obj = _read_json(cand)
        if not isinstance(obj, dict):
            continue
        labels = obj.get("labels")
        if not isinstance(labels, dict):
            continue
        by_dir: dict[str, dict] = {}
        for rec in labels.values():
            if isinstance(rec, dict) and rec.get("paper_dir"):
                by_dir[str(rec["paper_dir"])] = rec
        unknown = {str(d) for d in (obj.get("unknown_dois") or [])}
        return by_dir, unknown, True
    return {}, set(), False


def _apply_pubpeer_labels(root: Path, papers: list[dict]) -> None:
    """Stamp each paper with what PubPeer already said, when we have asked.

    The workbench queue cannot be sorted toward the 69 Masliah
    image-integrity papers if the index does not carry the label. A missing
    labels file leaves `pubpeer` None -- we have not asked -- which is not
    the same as `has_entry: false`. A DOI whose lookup failed is also
    None: unknown is not empty.
    """
    labels, unknown, asked = _load_pubpeer_labels(root)
    for p in papers:
        rec = None
        for key in (p.get("paper_id"), p.get("dir"),
                    Path(str(p.get("dir") or "")).name):
            if key and key in labels:
                rec = labels[key]
                break
        doi = str(p.get("doi") or "")
        if rec is None:
            p["pubpeer"] = None if (not asked or doi in unknown) else {
                "has_entry": False,
                "is_image_integrity": False,
                "figures": [],
                "n_comments": 0,
            }
            continue
        url = rec.get("url")
        if not (isinstance(url, str) and url.startswith("https://pubpeer.com/")):
            url = None
        p["pubpeer"] = {
            "has_entry": True,
            "is_image_integrity": bool(rec.get("is_image_integrity")),
            "figures": list(rec.get("figures") or []),
            "n_comments": rec.get("total_comments") or 0,
            "url": url,
        }


def _apply_corpus_sweep_state(root: Path, papers: list[dict]) -> None:
    """Downgrade `cross_paper: did_not_run` to `unknown` on an unswept corpus.

    THE ONE CHANNEL A PAPER CANNOT ANSWER ABOUT ITSELF. The sweep writes into a
    paper only when it MATCHED something, so a paper that was compared against
    four hundred others and found clean leaves exactly the same trace as one
    that was never compared at all: nothing.

    From inside the paper those are indistinguishable, and `cross_paper_channel`
    correctly refuses to guess. From here they are not: if the corpus carries no
    `image_corpus_report.md`, no sweep has run over this root, and every
    `did_not_run` in it is really "we cannot tell from a paper alone" -- which
    is what `unknown` is for. If the report IS present the sweep ran, and a
    paper with no match file genuinely has no cross-paper hit, so
    `did_not_run` stands and means what it says.

    This is the same failure the tri-state exists to prevent, one level up: an
    absence caused by OUR not running something, reported as a fact about the
    paper. Getting it wrong here is worse than having no channel, because a
    reader would conclude four hundred papers had been cleared of sharing
    panels when not one comparison had been made.
    """
    if not cross_paper_enabled():
        return
    if (root / _CORPUS_SWEEP_REPORT).is_file():
        return
    for p in papers:
        ch = (p.get("channels") or {}).get("cross_paper")
        if isinstance(ch, dict) and ch.get("state") == "did_not_run":
            ch["state"] = "unknown"
            ch["detail"] = (
                f"no {_CORPUS_SWEEP_REPORT} in this corpus, so the sweep has "
                f"not run over this root and whether this paper shares panels "
                f"with another has not been asked. This is our gap, not a "
                f"clean result.")


def _totals(papers: list[dict]) -> dict:
    """Corpus-level counts, computed here so the UI cannot compute them
    differently. Channel states are tallied per channel and per state, with
    every state present at zero for the same reason `severity_counts` is."""
    by_channel: dict[str, dict[str, int]] = {}
    # Seeded from `scan_paper`'s own channel set, not from a literal list. The
    # list was a second copy, and adding `cross_paper` to `scan_paper` left it
    # counted in no total -- present on every paper, absent from every summary,
    # which is precisely the "wired and empty" shape this file exists to expose.
    for ch in channel_names():
        by_channel[ch] = {s: 0 for s in CHANNEL_STATES}
    verdicts_seen = {v: 0 for v in _verdicts.VERDICTS}
    verdicts_seen["none"] = 0
    severities = {s: 0 for s in _SEVERITIES}
    reviewed = {"unreviewed": 0, "approved": 0, "withheld": 0}
    human = {"unreviewed": 0, "in_progress": 0, "complete": 0}
    n_pdf = n_xml = n_agent = n_image = n_image_discarded = n_image_refused = n_text = 0
    n_pubpeer = n_pubpeer_image = n_submitted_pubpeer = 0
    # Papers somebody has OPENED. Counted only where a view is on file or a
    # review decision proves the paper was open; `unknown` holds the papers
    # whose view record could not be read, so the two numbers are never one.
    n_viewed = n_viewed_unknown = 0
    # Counted at the top level, not buried in `sources`, because it is the
    # denominator every other number in this dict is a fraction of. A corpus
    # screen reporting "369 papers whose image result was discarded" over a
    # silent 49 we never obtained is reporting a rate against the wrong total.
    sources = {"held": 0, "not_fetched": 0, "empty": 0}
    evidence = {"papers_with_evidence": 0, "papers_with_video": 0,
                "n_assets": 0, "n_videos": 0}
    cost = 0.0
    for p in papers:
        st_src = (p.get("sources") or {}).get("state", "empty")
        sources[st_src if st_src in sources else "empty"] += 1
        assets = p.get("evidence") or []
        if assets:
            evidence["papers_with_evidence"] += 1
            evidence["n_assets"] += len(assets)
            vids = [a for a in assets if a.get("is_video")]
            if vids:
                evidence["papers_with_video"] += 1
                evidence["n_videos"] += len(vids)
        for ch, rec in (p.get("channels") or {}).items():
            if ch in by_channel:
                by_channel[ch][rec["state"]] += 1
        v = p.get("verdict")
        verdicts_seen[v if v in verdicts_seen else "none"] += 1
        w = p.get("worst_severity")
        if w in severities:
            severities[w] += 1
        st = ((p.get("review") or {}).get("publication") or {}).get("state", "unreviewed")
        reviewed[st if st in reviewed else "unreviewed"] += 1
        hs = ((p.get("review") or {}).get("paper_status") or "unreviewed")
        human[hs if hs in human else "unreviewed"] += 1
        vw = p.get("viewed") if isinstance(p.get("viewed"), dict) else {}
        if vw.get("viewed") is True:
            n_viewed += 1
        elif vw.get("source") == "unreadable":
            n_viewed_unknown += 1
        src = p.get("sources") or {}
        if src.get("pdf"):
            n_pdf += 1
        if src.get("xml"):
            n_xml += 1
        ch = p.get("channels") or {}
        if (ch.get("numeric") or {}).get("state") == "ran":
            n_agent += 1
        img_state = (ch.get("image_forensics") or {}).get("state")
        if img_state == "ran":
            n_image += 1
        elif img_state == "ran_result_discarded":
            n_image_discarded += 1
        elif img_state == "refused":
            n_image_refused += 1
        if (ch.get("tortured_phrases") or {}).get("state") == "ran":
            n_text += 1
        if isinstance(p.get("cost_usd"), (int, float)):
            cost += float(p["cost_usd"])
        pp = p.get("pubpeer")
        if isinstance(pp, dict) and pp.get("has_entry"):
            n_pubpeer += 1
            if pp.get("is_image_integrity"):
                n_pubpeer_image += 1
        if (p.get("review") or {}).get("submitted_to_pubpeer") is True:
            n_submitted_pubpeer += 1
    return {"n_papers": len(papers), "channels": by_channel,
            "verdicts": verdicts_seen, "worst_severity": severities,
            "publication": reviewed, "sources": sources,
            "evidence": evidence, "total_cost_usd": round(cost, 2),
            "n_pdf": n_pdf, "n_xml": n_xml, "n_agent_run": n_agent,
            "n_image_run": n_image, "n_image_discarded": n_image_discarded,
            "n_image_refused": n_image_refused, "n_text_run": n_text,
            "n_pubpeer": n_pubpeer, "n_pubpeer_image": n_pubpeer_image,
            "n_submitted_pubpeer": n_submitted_pubpeer,
            "n_viewed": n_viewed, "n_viewed_unknown": n_viewed_unknown,
            "human_review": human}


def sort_papers(papers: list[dict]) -> list[dict]:
    """Worst first, then unreviewed before reviewed.

    The workbench's default order is a work queue, not an alphabet: the paper
    that most needs a human is the one with the most severe finding nobody has
    looked at yet.
    """
    def key(p: dict):
        # PubPeer image-integrity papers first: those are the findings a
        # human already named, and the workbench had no way to surface them
        # (MEASURED 2026-08-19: 31 Masliah reviews, zero of them PubPeer
        # image papers).
        pp = p.get("pubpeer") if isinstance(p.get("pubpeer"), dict) else {}
        pubpeer_image = 0 if pp.get("is_image_integrity") else 1
        rank = severity_rank(p.get("worst_severity"))
        rank = 99 if rank is None else rank
        unreviewed = 0 if not (p.get("review") or {}).get("reviewed") else 1
        return (pubpeer_image, rank, unreviewed, p.get("paper_id") or "")
    return sorted(papers, key=key)


DEFAULT_PAPERS_ROOT = (
    "/home/dan/Dropbox/AAA_METASCIENCE_OBSERVATORY/"
    "agent_for_forensic_metascience_papers"
)

PROJECTS_SCHEMA_VERSION = "1.1"

_NOT_A_PROJECT = frozenset({
    "done", "failed", "logs", "reviews", "blinded", "node_modules",
    ".git", ".next",
})


def scan_projects(papers_root: str | Path, limit: int | None = None) -> dict:
    """One row per project (immediate child of the papers root).

    A project is a directory that contains paper folders. Counts never drop
    unfetched papers: they stay in `n_papers` so the table cannot look cleaner
    than the disk.
    """
    root = Path(papers_root)
    projects: list[dict] = []
    errors: list[dict] = []
    if not root.is_dir():
        return {
            "schema_version": PROJECTS_SCHEMA_VERSION,
            "papers_root": root.as_posix(),
            "projects": [],
            "n_projects": 0,
            "n_papers": 0,
            "errors": [{"path": root.as_posix(), "error": "not a directory"}],
        }
    candidates = []
    for d in sorted(root.iterdir()):
        if not d.is_dir() or d.name.startswith(".") or d.name in _NOT_A_PROJECT:
            continue
        candidates.append((d.name, d))
        # Explicit author-session layout only: never recurse into run workspaces.
        sessions = d / "analysis_sessions"
        if sessions.is_dir():
            for session in sorted(sessions.iterdir()):
                corpus_root = session / "corpus"
                if (session / "population.json").is_file() and corpus_root.is_dir():
                    if corpus_root.resolve().is_relative_to(d.resolve()):
                        candidates.append((f"{d.name}__{session.name}", corpus_root))
    for name, d in candidates:
        try:
            corpus = scan_corpus(d, limit=limit, image_publication_counts=False)
        except Exception as exc:  # noqa: BLE001
            errors.append({"path": d.name, "error": f"{type(exc).__name__}: {exc}"})
            continue
        T = corpus["totals"]
        projects.append({
            "name": name,
            "root": d.as_posix(),
            "n_papers": T["n_papers"],
            "n_pdf": T.get("n_pdf", 0),
            "n_xml": T.get("n_xml", 0),
            "n_agent_run": T.get("n_agent_run", 0),
            "n_image_run": T.get("n_image_run", 0),
            "n_image_discarded": T.get("n_image_discarded", 0),
            "n_image_refused": T.get("n_image_refused", 0),
            "n_text_run": T.get("n_text_run", 0),
            "n_human_reviewed": (T.get("human_review") or {}).get("complete", 0),
            "n_in_progress": (T.get("human_review") or {}).get("in_progress", 0),
            "n_not_fetched": (T.get("sources") or {}).get("not_fetched", 0),
            "n_pubpeer": T.get("n_pubpeer", 0),
            "n_pubpeer_image": T.get("n_pubpeer_image", 0),
            "n_submitted_pubpeer": T.get("n_submitted_pubpeer", 0),
            "n_viewed": T.get("n_viewed", 0),
            "n_viewed_unknown": T.get("n_viewed_unknown", 0),
            "corpus": corpus,
        })
    return {
        "schema_version": PROJECTS_SCHEMA_VERSION,
        "papers_root": root.as_posix(),
        "projects": projects,
        "n_projects": len(projects),
        "n_papers": sum(p["n_papers"] for p in projects),
        "errors": errors,
    }


def default_index_path() -> Path:
    env = (os.environ.get("METASCIENCE_INDEX") or "").strip()
    if env:
        return Path(env)
    return Path(__file__).resolve().parents[2] / "webapp" / "data" / "index.json"


def _apply_project_totals(proj: dict, papers: list[dict]) -> None:
    T = _totals(papers)
    proj.setdefault("corpus", {})["papers"] = papers
    proj["corpus"]["totals"] = T
    proj["n_papers"] = T["n_papers"]
    proj["n_pdf"] = T.get("n_pdf", 0)
    proj["n_xml"] = T.get("n_xml", 0)
    proj["n_agent_run"] = T.get("n_agent_run", 0)
    proj["n_image_run"] = T.get("n_image_run", 0)
    proj["n_image_discarded"] = T.get("n_image_discarded", 0)
    proj["n_image_refused"] = T.get("n_image_refused", 0)
    proj["n_text_run"] = T.get("n_text_run", 0)
    proj["n_human_reviewed"] = (T.get("human_review") or {}).get("complete", 0)
    proj["n_in_progress"] = (T.get("human_review") or {}).get("in_progress", 0)
    proj["n_not_fetched"] = (T.get("sources") or {}).get("not_fetched", 0)
    proj["n_pubpeer"] = T.get("n_pubpeer", 0)
    proj["n_pubpeer_image"] = T.get("n_pubpeer_image", 0)
    proj["n_submitted_pubpeer"] = T.get("n_submitted_pubpeer", 0)
    proj["n_viewed"] = T.get("n_viewed", 0)
    proj["n_viewed_unknown"] = T.get("n_viewed_unknown", 0)


def _merge_index_paper(paper_dir: str | Path,
                        index_path: Path | None = None) -> dict:
    """Patch one paper into the workbench index after a run.

    The project table reads `index.json`, not the disk. A finished analyze
    that is not written back there shows `n_findings: —` next to a review
    that is sitting on disk. Missing index, unreadable file, or a paper
    outside every indexed project is a no-op — never fail a paid run.

    Called under the shared index transaction lock by refresh_index_paper.
    """
    paper_dir = Path(paper_dir).resolve()
    if paper_dir.is_file():
        paper_dir = paper_dir.parent
    path = Path(index_path) if index_path else default_index_path()
    if not path.is_file():
        return {"updated": False, "reason": "no index"}
    try:
        idx = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"updated": False, "reason": "unreadable index"}
    if not isinstance(idx, dict) or not idx.get("projects"):
        return {"updated": False, "reason": "old index shape"}

    for proj in idx["projects"]:
        root = Path(proj.get("root") or "")
        try:
            real_root = root.resolve() if root.exists() else root
            rel = paper_dir.relative_to(real_root).as_posix()
        except (ValueError, OSError):
            continue
        rec = scan_paper(paper_dir, corpus_root=real_root)
        rec["dir"] = rel
        papers = list((proj.get("corpus") or {}).get("papers") or [])
        hit = False
        for i, p in enumerate(papers):
            if p.get("dir") == rel:
                papers[i] = rec
                hit = True
                break
        if not hit:
            papers.append(rec)
        _apply_project_totals(proj, sort_papers(papers))
        idx["n_papers"] = sum(p.get("n_papers") or 0 for p in idx["projects"])
        from .atomicio import atomic_write_text
        atomic_write_text(path, json.dumps(idx, indent=2, default=str) + "\n")
        return {"updated": True, "dir": rel,
                "n_findings": rec.get("n_findings"),
                "n_runs": rec.get("n_runs")}
    return {"updated": False, "reason": "paper not under any indexed project"}


def refresh_index_paper(paper_dir: str | Path, index_path: Path | None = None) -> dict:
    """Serialize index read/merge/publish against scans and other paper updates."""
    from .atomicio import file_lock
    target = Path(index_path) if index_path else default_index_path()
    if not target.is_file():
        return {"updated": False, "reason": "no index"}
    with file_lock(target.with_suffix(".lock")):
        return _merge_index_paper(paper_dir, target)


if __name__ == "__main__":
    import sys
    print(json.dumps(refresh_index_paper(sys.argv[1])))


def refresh_image_project_index(project: Path) -> dict:
    import shutil
    from .image_plugin import load as _image_load
    _m = _image_load("image_forensics.repair_source_identity")
    REVISION, save = _m.REVISION, _m.save
    path = default_index_path()
    if not path.is_file():
        return {'updated': False, 'reason': 'no existing web index'}
    idx = json.loads(path.read_text())
    for proj in idx.get('projects', []):
        if Path(proj.get('root') or '').resolve() != project.resolve():
            continue
        archive = project / '.source_identity_repair' / f'v{REVISION}' / 'webapp_index.json'
        if not archive.exists():
            archive.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, archive)
        papers = []
        for old in (proj.get('corpus') or {}).get('papers', []):
            directory = project / old['dir']
            rec = scan_paper(directory, corpus_root=project)
            rec['dir'] = old['dir']
            papers.append(rec)
        _apply_project_totals(proj, sort_papers(papers))
        idx['n_papers'] = sum(p.get('n_papers') or 0 for p in idx['projects'])
        save(path, idx)
        return {'updated': True, 'papers': len(papers)}
    return {'updated': False, 'reason': 'project not indexed'}
