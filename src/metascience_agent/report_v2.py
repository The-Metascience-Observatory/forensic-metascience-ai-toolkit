"""Render a findings-v2 document to the review markdown (parallel mode).

The structural guarantees are the renderer's, not the model's (the same
doctrine as `report_render`): headline first, findings ordered by FINAL
severity descending, an explicit "what we could NOT check" section, the
limitations block, the coverage stamp, and the published disclaimer. The
narrative slot is the adjudicator's bounded `summary` -- no model free-text
survives anywhere else. Discarded findings are RENDERED, labeled as
discarded with the adjudicator's rationale: ran-and-discarded must stay
visible, never disappear into an absence.
"""

from __future__ import annotations

from typing import Any

from .names import display as _display
from .severity9 import LEVELS


#: The adjudicator actions whose findings REACH THE REPORT. `None` is included
#: because a run whose adjudicator did not execute still prints its findings --
#: `apply_skip` leaves the action unset and the report shows the provisional
#: ladder, which is the honest behaviour and must not read as "discarded".
REPORTED_ACTIONS = ("kept", "downgraded", "upgraded", None)


def reported_finding_ids(doc: dict) -> set[str]:
    """The ids this renderer actually prints, by the renderer's own rule.

    EXPORTED SO NOBODY RESTATES IT. `bundle.py` needs the same answer for its
    "in report" column and derived it instead from `report.json`'s editorial
    list -- a file the parallel path never writes. `report_obj` was therefore
    `{}`, `editorial` was `[]`, `[] is not None` slipped the guard, and the
    viewer told a reader that ZERO of 34 findings reached the report while
    `report.md` carried fifteen.

    Keyed on `finding_id`, which is what a v2 row carries; `bundle` was reading
    `id`, so even a populated editorial list would not have matched.
    """
    findings = [f for f in (doc or {}).get("findings") or [] if isinstance(f, dict)]
    actions = {f.get("finding_id"): (f.get("adjudication") or {}).get("action")
               for f in findings}
    return {str(f.get("finding_id")) for f in findings
            if f.get("outcome") == "problem"
            and actions.get(f.get("finding_id")) in REPORTED_ACTIONS}


def _quote_lines(f: dict) -> list[str]:
    """A blockquote, and a label when the words are not the paper's.

    A `>` blockquote under a finding reads as the paper speaking. For 11 of the
    137 quoted findings in this repo's v2 archive that is false: 7 are
    `stitched` and 4 `unverified`. `quotes.classify` already decided this and
    already wrote the sentence explaining it --

        "Every number here appears in the paper, but this exact sentence does
         not -- it was composed by the review, so searching the PDF for it will
         find nothing."

    -- and this renderer read NEITHER field (`grep quote_verified report_v2.py`
    returned nothing). The legacy renderer gates on it at report_render.py:1194
    and 1206, and so does the viewer at bundle.py:6687, so a reader of the
    markdown was told something a reader of either other surface was not.

    NOT SUPPRESSED, LABELLED. A stitched quote is still the most useful pointer
    to where the finding came from, and dropping it would leave the finding
    unsupported; what it must not do is claim to be a passage a reader can find.
    `verbatim` and `elided` are `viewer_facts.LOCATED_VERDICTS` -- the
    codebase's own definition of located -- and are printed bare, as before.
    """
    quote = str(f.get("quote") or "").strip()
    if not quote:
        return []

    from .viewer_facts import LOCATED_VERDICTS
    verdict = str(f.get("quote_verified") or "")
    if verdict in LOCATED_VERDICTS:
        return [f"> {quote}"]

    known = {
        "stitched": ("composed by this review, not a passage in the paper -- "
                     "the numbers appear there, this sentence does not"),
        "unverified": "not checked against the paper",
        "absent": "could not be located in the paper",
    }
    why = str(f.get("quote_problem") or "").strip() or known.get(
        verdict, f"quote verification returned {verdict!r}" if verdict
        else "no verification was recorded for this quote")
    return [f"> {quote}", "",
            f"*Not the paper's words as printed: {why}*"]


def _reproduction_line(f: dict) -> str | None:
    """The `Reproduce:` line, or an honest statement of why there is not one.

    `report_render` DELETED its own `_render_reproduction` and left the rule
    behind in a comment: "Anything that reintroduces a command into this
    renderer has to reintroduce that check too." This renderer reintroduced the
    command and not the check, so every command was offered as paste-ready
    whether or not it runs.

    IT MATTERS BECAUSE MOST OF THEM DO NOT RUN. Measured by executing all 523
    distinct reproduction strings in this repo's archive: 60 (11.5%) exited 0,
    352 (67.3%) passed the static check and then exited NON-ZERO, 111 (21.2%)
    failed the static check. A command that errors on first use reads as a
    broken tool rather than as a bad citation, and the failure is OURS in every
    one of those cases -- the reader learns nothing about the paper from it.

    THREE STATES, mirroring the viewer's `reproHtml` exactly (bundle.py), so a
    reader of the markdown and a reader of the bundle are told the same thing:

      `reproduction_valid is True`  -- the command was EXECUTED and exited 0.
                                      Offered to paste.
      `reproduction_valid is False` -- executed and failed. Named as our
                                      failure, using the measured vocabulary in
                                      `report_render._REPRO_FAILURE_CLAUSE`,
                                      never our raw stderr.
      absent                        -- nobody checked. The parallel path never
                                      calls `_annotate_reproductions`, so this
                                      is the live case: 24 of 34 findings on
                                      the current run carry a command and 0
                                      carry a verdict. Shown as an unverified
                                      template, NOT as something to paste --
                                      the same call the viewer's `tpl` makes.
    """
    cmd = str(f.get("reproduction") or "").strip()
    if not cmd:
        return None

    valid = f.get("reproduction_valid")
    if valid is True:
        return f"Reproduce: `{cmd}`"

    if valid is False:
        try:
            from .report_render import _repro_failure_clause
            clause = _repro_failure_clause(f)
        except Exception:  # noqa: BLE001 -- never lose the finding to its footer
            clause = "the review's command did not validate"
        return f"Reproduce: not available -- {clause}"

    # No verdict recorded. Saying "Reproduce:" here would assert a property of
    # the command nobody established.
    return (f"Reproduction command (UNVERIFIED -- not executed, so it may not "
            f"run as written): `{cmd}`")


def _level_tag(sev: int | None) -> str:
    if not isinstance(sev, int) or sev not in LEVELS:
        return "unranked"
    return f"Level {sev} — {LEVELS[sev].label}"


def _sort_key(f: dict) -> tuple:
    sev = f.get("severity")
    prov = f.get("provisional_severity")
    return (-(sev if isinstance(sev, int) else
              (prov if isinstance(prov, int) else 0)),
            not f.get("impossible"),
            str(f.get("finding_id")))


def _partial_pipeline_banner(pipeline) -> list[str]:
    if not isinstance(pipeline, dict) or pipeline.get("complete_review") is not False:
        return []
    modules = [m for m in pipeline.get("modules") or [] if isinstance(m, dict)]
    ran = ", ".join(str(m.get("use")) for m in modules) or "none"
    tools = next((m.get("tools") for m in modules
                  if m.get("use") == "tools_agent"), None)
    toolset = (f" The tools agent could call only: {', '.join(tools)}."
               if tools else "")
    return [f"> **PARTIAL PIPELINE (`{pipeline.get('name')}`) — not a complete "
            f"review.** Modules run: {ran}.{toolset} Anything those modules do "
            "not cover was not examined; its absence below is not a finding "
            "that the paper is clean.", ""]


def _truncated_stages_banner(run_meta) -> list[str]:
    """A STAGE CUT SHORT SAYS SO ON PAGE 1.

    `_stage_meta` has recorded `truncated_by_budget` per stage all along, and
    the run is filed `incomplete`, but this renderer printed nothing about it:
    a report whose tools agent spent its budget before emitting findings read
    as a complete review that found little. The serial pipeline injected a
    PARTIAL COVERAGE limitation; that went with it in v1.27.0, and this is its
    replacement. A timeout or stall is the same fact for the reader (the stage
    stopped before it had finished looking), so `truncated_by_timeout` counts
    too, with its own cause named. Ledger-only rows (`source: spend_ledger`)
    are billed attempts, not stage records, and never carry either flag.
    """
    stages = (run_meta or {}).get("stages") if isinstance(run_meta, dict) else None
    if not isinstance(stages, dict):
        return []
    cut: list[str] = []
    for label, meta in stages.items():
        if not isinstance(meta, dict) or meta.get("source") == "spend_ledger":
            continue
        causes = []
        if meta.get("truncated_by_budget"):
            causes.append("ran out of budget")
        if meta.get("truncated_by_timeout"):
            causes.append("was cut off by the time limit")
        if causes:
            cut.append(f"{_display(label) or label} ({' and '.join(causes)})")
    if not cut:
        return []
    return [f"> **PARTIAL COVERAGE — a stage stopped before it finished.** "
            f"{'; '.join(cut)}. What that stage had not reached was not "
            "examined, so the absence of a finding there is not evidence that "
            "the paper is clean, and this report is not a complete review.", ""]


def render_report_v2(doc: dict, run_meta: dict | None = None,
                     limitations: list[str] | None = None) -> str:
    adj: dict[str, Any] = doc.get("adjudication") or {}
    findings = [f for f in doc.get("findings") or [] if isinstance(f, dict)]
    problems = [f for f in findings if f.get("outcome") == "problem"]
    actions = {f.get("finding_id"): (f.get("adjudication") or {}).get("action")
               for f in findings}
    kept = [f for f in problems
            if actions.get(f.get("finding_id")) in REPORTED_ACTIONS]
    discarded = [f for f in problems
                 if actions.get(f.get("finding_id")) == "discarded"]
    merged = [f for f in problems
              if actions.get(f.get("finding_id")) == "merged"]
    kept.sort(key=_sort_key)

    lines: list[str] = [f"# Forensic review — {doc.get('paper_id')}", ""]

    # A PARTIAL PIPELINE SAYS SO BEFORE ANYTHING ELSE. A one-tool or
    # unadjudicated run renders the same sections as a review; without this
    # line its silence about everything it never ran reads as a clean paper.
    lines += _partial_pipeline_banner(doc.get("pipeline"))
    # A STAGE THAT RAN OUT OF BUDGET OR TIME says so just as early, for the
    # same reason: what it never reached is otherwise silent.
    lines += _truncated_stages_banner(run_meta)

    # Headline first.
    headline_id = adj.get("headline_finding_id")
    headline = next((f for f in kept
                     if f.get("finding_id") == headline_id), None)
    if headline:
        lines += [f"## Headline — {_level_tag(headline.get('severity'))}",
                  "",
                  f"**{headline.get('title')}**",
                  "",
                  str(headline.get("description") or ""), ""]
    verdict = adj.get("verdict")
    v_line = f"**Verdict: {verdict or 'not adjudicated'}**"
    if isinstance(adj.get("paper_severity"), int):
        v_line += f" — paper severity {_level_tag(adj['paper_severity'])}"
    if adj.get("confidence"):
        v_line += f" (confidence: {adj['confidence']})"
    lines += [v_line, ""]

    if adj.get("summary"):
        lines += ["## Summary", "", str(adj["summary"]), ""]

    if not adj.get("ran", False):
        reason = adj.get("skipped_reason") or adj.get("failure") or "unknown"
        lines += ["> **SEVERITIES ARE PROVISIONAL.** The adjudicator did not "
                  f"run ({reason}); every level below is the producer's own "
                  "estimate, and findings marked `impossible` did not receive "
                  "their R ground-truth cross-check.", ""]

    if kept:
        lines += ["## Findings", ""]
        for f in kept:
            sev = f.get("severity")
            prov = " (provisional)" if f.get("severity_is_provisional") else ""
            stamp = (" — **cross-check not run**"
                     if f.get("cross_check") == "not_run" else "")
            imp = " · arithmetically impossible" if f.get("impossible") else ""
            lines.append(f"### {_level_tag(sev)}{prov} — "
                         f"{f.get('title')}{stamp}")
            lines.append("")
            lines.append(str(f.get("description") or ""))
            meta_bits = [f"producer: {_display(f.get('producer'))}",
                         f"technique: {f.get('technique')}"]
            if f.get("location"):
                meta_bits.append(f"location: {f['location']}")
            lines.append(f"*({'; '.join(meta_bits)}{imp})*")
            lines += _quote_lines(f)
            repro = _reproduction_line(f)
            if repro:
                lines.append(repro)
            fr = (f.get("adjudication") or {}).get("merged_from") or []
            if fr:
                lines.append(f"*Merged pattern: absorbs {len(fr)} sibling "
                             "finding(s).*")
            lines.append("")
    else:
        lines += ["## Findings", "",
                  "No problem findings survived adjudication.", ""]

    if discarded or merged:
        lines += ["## Findings set aside by the adjudicator "
                  "(retained on the record)", ""]
        for f in discarded:
            a = f.get("adjudication") or {}
            lines.append(f"- **discarded** ({a.get('category')}): "
                         f"{f.get('title')} — {a.get('rationale')}")
        for f in merged:
            a = f.get("adjudication") or {}
            lines.append(f"- **merged into `{a.get('merged_into')}`**: "
                         f"{f.get('title')}")
        lines.append("")

    unchecked = doc.get("unchecked") or []
    tally = doc.get("checks_tally") or {}
    # A DOCKET THAT DID NOT SURVIVE SERIALIZATION IS NOT A COVERAGE STATEMENT.
    #
    # MEASURED 2026-08-22, `10.1186--s12889-025-24026-y` on grok-4.6: the tool
    # agent made 76 forensic calls, then filed a docket with one finding,
    # `coverage: {"stats_found": 0, "tools_run": []}`, and no `unchecked`
    # entries. The retry was empty too. This section then printed "Nothing was
    # recorded as uncheckable" -- our own failure rendered as an absence of
    # findings, on the page whose job is making coverage visible.
    # `tools_run_source == "ledger"` MUST COUNT AS LOST. Once
    # `_coverage_with_ledger_fallback` rebuilds the tool list from the
    # transcript, `tools_run` is no longer empty -- but only the LIST was
    # recovered. The findings, the anatomy and the statistics register are
    # still gone, so a reader must still be told. Keying this on emptiness
    # alone would have switched the warning off the moment the recovery
    # landed, which is the quiet way a coverage guard stops guarding.
    _cov = doc.get("coverage") or {}
    docket_lost = (
        (not (_cov.get("tools_run") or [])
         or _cov.get("tools_run_source") == "ledger")
        and bool(tally.get("checks_total"))
    )
    # REPORTING CONVENTIONS, RENDERED. Greg, 2026-08-26: "even if a
    # suspicious/impossible finding reconciles after accounting for
    # rounding/truncation, I want the impossibility of the original finding to
    # be there for the end user to notice."
    #
    # `agent.py` has computed both rates since the conventions were added, and
    # `checks_tally` has carried them into every findings-v2 document. NOTHING
    # RENDERED THEM. The reader saw the rescued verdict and never the rescue,
    # which is the house failure -- built, filed, consumed by nobody -- on the
    # one signal that distinguishes a house style from a habit.
    #
    # A RATE, NEVER A VERDICT, and printed even at zero. "0 of 13" says we
    # looked; an absent section says nothing at all, and a reader cannot tell
    # those apart. The severity of every rescued check is unchanged: a
    # convention is a choice, not a fabrication, and this section may never
    # read as an accusation.
    conv_rows = []
    for key, label, phrase in (
        ("rounding_convention", "n_fit_only_under_truncation",
         "reconcile only if the reporter TRUNCATES rather than rounds "
         "(SPSS's default, and several journal styles)"),
        ("sd_convention", "n_fit_only_under_population_sd",
         "reconcile only under the POPULATION (n) SD rather than the sample "
         "(n-1) SD (numpy's `std` default, Excel's STDEVP)"),
    ):
        block = tally.get(key) or {}
        hit = block.get(label)
        denom = block.get("n_granularity_checks")
        if hit is None or not denom:
            continue
        conv_rows.append(f"- **{hit} of {denom}** granularity checks {phrase}.")
    if conv_rows:
        lines += ["## Reporting conventions", ""]
        lines += conv_rows
        lines.append(
            "- These are NOT findings and no severity rests on them. Choosing a "
            "convention is not fabrication, and one instance is a house style. "
            "**The rate is the signal**: a high proportion beside genuine "
            "`impossible` findings is grounds to look harder, not evidence in "
            "itself.")
        lines.append("")

    lines += ["## What we could NOT check", ""]
    if docket_lost:
        lines.append(
            "- **This section is not a coverage statement for this run.** The "
            "tool docket did not survive serialization -- the ledger records "
            f"{tally.get('checks_total')} check(s) that the filed report does "
            "not itemise -- so the territory below is what happened to be "
            "recorded, not the complement of what was examined.")
    if unchecked:
        for u in unchecked:
            if isinstance(u, dict):
                lines.append(f"- {u.get('location', '?')}: "
                             f"{u.get('reason', 'no reason recorded')}")
            else:
                lines.append(f"- {u}")
    else:
        lines.append("- Nothing was recorded as uncheckable. That is a claim "
                     "about the record, not a certificate of coverage.")
    lines.append("")

    lines += ["## Limitations", ""]
    lims = list(limitations or []) + [str(x) for x in
                                      (run_meta or {}).get("limitations", [])
                                      if x not in (limitations or [])]
    for lim in lims:
        lines.append(f"- {lim}")
    passes = [f for f in findings if f.get("outcome") == "pass"]
    n_undecided = sum(1 for f in findings if f.get("outcome") == "undecided")
    # TWO NUMBERS FOR ONE QUANTITY IS NOT ACCEPTABLE OUTPUT FROM THIS TOOL.
    #
    # `passes` counts pass ROWS the producer filed; `checks_tally.checks_passed`
    # counts passing checks on the TOOL LEDGER, which is where `check_table`'s
    # collapsed per-cell checks live. On a healthy paper they agree and the
    # distinction is pedantry. On `10.1186--s12889-025-24026-y` (2026-08-22)
    # they were 0 and 26, and the report printed the 0 in Limitations while the
    # adjudicator's summary -- which reads the tally -- printed "Twenty-six
    # table checks were consistent with the printed cells". A reader had no way
    # to tell which number was about what. Print both, each named for its
    # source, whenever they disagree.
    ledger_passed = tally.get("checks_passed")
    if isinstance(ledger_passed, int) and ledger_passed != len(passes):
        collapsed = tally.get("of_which_collapsed_by_check_table") or 0
        lines.append(
            f"- Checks recorded as passing: {len(passes)} filed as findings, "
            f"{ledger_passed} on the tool ledger"
            + (f" ({collapsed} of them per-cell checks collapsed by "
               f"check_table)" if collapsed else "")
            + f"; undecided: {n_undecided}. The two counts differ, so the "
              "filed report does not describe everything the tools did.")
    else:
        lines.append(f"- Checks recorded as passing: {len(passes)}; "
                     f"undecided: {n_undecided}.")
    channels = doc.get("channels") or {}
    for name, ch in sorted(channels.items()):
        state = ch.get("state") if isinstance(ch, dict) else ch
        if state == "ran" and name == "image_forensics" and isinstance(ch, dict):
            detail = ch.get("detail") or "ran; coverage detail not recorded"
            lines.append(f"- Image analysis: {detail.rstrip('.')}.")
        if state != "ran":
            detail = ch.get("detail", "") if isinstance(ch, dict) else ""
            lines.append(f"- {_display(name)} (`{name}`) did not produce a retained "
                         f"result: {state}{' — ' + detail if detail else ''}.")
    lines.append("")

    cov = doc.get("coverage") or {}
    if cov:
        lines += ["## Coverage", "",
                  f"- statistics found: {cov.get('stats_found', '?')}; "
                  f"checked: {cov.get('stats_checked', '?')}",
                  f"- tools run: {', '.join(cov.get('tools_run') or []) or 'none recorded'}"
                  + ("  *(recovered from the tool-call ledger; the producer's "
                     "own report listed none)*"
                     if cov.get("tools_run_source") == "ledger" else "")]
        if (cov.get("grim_sweep") or {}).get("line"):
            lines.append(f"- {cov['grim_sweep']['line']}")
        if docket_lost:
            # "none recorded" is a fact about the record; without this line a
            # reader takes it for a fact about the run.
            lines.append(
                "- The docket did not survive serialization. "
                + ("The tool list above was rebuilt from the transcript, but "
                   "the findings, anatomy and statistics register from those "
                   "calls are gone and the counts below are not a coverage "
                   "statement."
                   if cov.get("tools_run_source") == "ledger" else
                   "This block is EMPTY BECAUSE OF THAT, not because nothing "
                   "ran.")
                + " See Limitations.")
        lines.append("")

    rm = run_meta or {}
    prov_bits = [f"pipeline {rm.get('version') or rm.get('pipeline_version') or '?'}",
                 f"run {doc.get('run_id')}",
                 f"analysed {rm.get('analysed_at') or '?'}"]
    if rm.get("llm_backend"):
        prov_bits.append(f"backend {rm['llm_backend']}")
    lines += ["---", f"*{' · '.join(prov_bits)}*", ""]

    # THE WHOLE CLOSING SECTION, not the disclaimer alone.
    #
    # This imported `DISCLAIMER_LONG` and printed it by itself. That paragraph
    # ends "The full breakdown is in 'What this has been tested on', below." --
    # and there was no below: `report_v2` rendered no scope section, so the
    # document pointed at something it did not contain. It also dropped
    # `ACTION_NOTE`, the sentence telling a reader to verify a number by hand
    # before treating it as a problem and that public allegations are not an
    # appropriate response. That is the single most important sentence in the
    # file for a reader who has just been shown an accusation.
    #
    # `closing_section_markdown` assembles all three and already exists for
    # exactly this; the legacy renderer calls it. 38 lines, ~5.9 KB.
    from .disclaimer import closing_section_markdown
    lines += ["## About this report", ""]
    lines += closing_section_markdown()
    lines += [""]
    return "\n".join(lines)
