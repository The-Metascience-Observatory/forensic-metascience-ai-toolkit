"""The findings adjudicator: docket in, verdicts out, every bound in code.

Contract: docs/specs/adjudicator.md (approved 2026-08-21). One LLM pass over
the merged findings of all four producers assigns final 1-9 severities; this
module is everything AROUND that pass -- `build_docket` (what the model
sees), `apply` (what its output is allowed to do), and `apply_skip` (the
paths where it never ran). The referee pattern is the fourth instance of the
contract the three adjudicator prototypes proved: verdicts join by explicit
id, never position; a clear requires a named benign category AND a locatable
evidence quote; silence keeps the finding; failure fails OPEN -- findings
are never lost to their own reviewing stage.
"""

from __future__ import annotations

from typing import Any

from .quotes import fold_rendering, normalise
from .findings_v2 import PRODUCER_TITLE_MAX, TITLE_MAX, fit_row_title
from .severity9 import LEVELS, QUARANTINE_CAP

DOCKET_ROW_CAP = 120
PAPER_TEXT_BUDGET_CHARS = 40_000
UNCHECKED_BUDGET_CHARS = 6_000

_UPGRADE_CATEGORIES = frozenset(
    {"merged_pattern", "consequence_reassessed", "manipulation"})
_ACTIONS = frozenset({"kept", "merged", "downgraded", "upgraded", "discarded"})
_UPGRADE_LIMIT = 2   # severity <= provisional + 2 unless exempt

_TITLE_BOUNDS = (8, TITLE_MAX)
_DESC_BOUNDS = (20, 700)


def _fold(s: str) -> str:
    """The locator path's typography fold: an evidence quote must be checked
    the same way a highlight would search for it."""
    return fold_rendering(normalise(s or ""))


def _fid(f: dict) -> str:
    return str(f.get("finding_id") or "")


# ---------------------------------------------------------------------------
# The docket
# ---------------------------------------------------------------------------

def _docket_row(f: dict) -> dict:
    tv = f.get("tool_verdict") if isinstance(f.get("tool_verdict"), dict) else {}
    inputs = f.get("inputs") if isinstance(f.get("inputs"), dict) else {}
    row = {
        "finding_id": _fid(f),
        "slug": f.get("slug"),
        "producer": f.get("producer"),
        "technique": f.get("technique"),
        "computed_by": f.get("computed_by"),
        "outcome": f.get("outcome"),
        "provisional_severity": f.get("provisional_severity"),
        "impossible": bool(f.get("impossible")),
        "tool_verdict": tv.get("severity"),
        "title": f.get("title"),
        "description": (f.get("description") or "")[:400],
        "location": f.get("location"),
        "quote": (f.get("quote") or "")[:300],
        "reported": f.get("reported"),
        "computed": f.get("computed"),
        "reproduction": f.get("reproduction"),
    }
    if f.get("quarantined"):
        row["quarantined"] = True
        row["quarantine_reason"] = f.get("quarantine_reason")
    if isinstance(inputs.get("image_adjudication"), dict):
        row["image_adjudication"] = inputs["image_adjudication"].get("verdict")
    if isinstance(inputs.get("ai_screening"), dict):
        # Full rationale, source packet and verified visual readings survive
        # the short narrative description used by reports.
        row["ai_screening"] = inputs["ai_screening"]
    if f.get("basis"):
        row["basis"] = f.get("basis")
    if isinstance(f.get("web_sources"), list):
        row["n_web_sources"] = len(f["web_sources"])
    if f.get("web_unbacked"):
        # The fabrication guard's output must reach its reader; until
        # 2026-08-21 the flag was written and read by nobody (the
        # write-only-key ratchet caught it). Two shapes, two sentences:
        # citations with no ledger call behind them, and (measured
        # 2026-08-22) a claimed lookup basis with no recorded source.
        row["web_unbacked"] = {
            "no_recorded_source": (
                "claims basis: web_lookup but records ZERO web_sources -- "
                "the claim is unauditable; treat it as model knowledge "
                "(severity cap 3) unless a source is quoted"),
        }.get(f.get("web_unbacked"),
              "cites web_sources but the ledger records no web call -- "
              "treat the citations as unverified")
        if isinstance(f.get("ledger_web_context"), list) \
                and f["ledger_web_context"]:
            # What the agent's ledger shows it actually visited: the
            # adjudicator can judge whether any of these plausibly backs
            # the claim, without the pipeline fabricating a citation.
            row["ledger_web_context"] = f["ledger_web_context"]
    return {k: v for k, v in row.items() if v is not None}


def _ranked(rows: list[dict]) -> list[dict]:
    """Severity-desc then impossible-first WITHIN each producer, interleaved
    round-robin ACROSS producers so one noisy producer cannot evict another's
    rows entirely (spec section 2.3)."""
    by_producer: dict[str, list[dict]] = {}
    for f in rows:
        by_producer.setdefault(str(f.get("producer")), []).append(f)
    for pool in by_producer.values():
        pool.sort(key=lambda f: (-(f.get("provisional_severity") or 0),
                                 not f.get("impossible"), _fid(f)))
    out: list[dict] = []
    pools = [by_producer[p] for p in sorted(by_producer)]
    while any(pools):
        for pool in pools:
            if pool:
                out.append(pool.pop(0))
    return out


def _sources_block(sources: Any) -> list[str]:
    """The `## Where the paper is` lines, or a named absence.

    THE ADJUDICATOR COULD NOT FIND THE PAPER, AND NOTHING TOLD IT WHERE.
    `_resolve_paper_sources` already states the rule this violates: "every path
    the model can read is one this function put in the prompt -- the model has
    no `Glob`, no `Bash` and no directory-listing tool, by decision -- so a
    supplement that is not merged here is a supplement that does not exist as
    far as the review is concerned." The two analysts get those paths. The
    adjudicator got none: `grep -c "/home/dan" prompt.adjudicator.md` returned
    0 on every paper of the 2026-08-22 biomedical batch.

    MEASURED consequence, from grok's own session logs for that batch:

        role           sessions  tool calls  failed        reached MCP
        tool_expert          18       1,487  3    ( 0%)    1,238 (83%)
        science_error        15         498  8    ( 2%)      295 (59%)
        ADJUDICATOR          13       1,038  680  (66%)      145 (14%)

    Every adjudicator failure was the same shape -- `read_file` on
    `<cwd>/body.md`, `<cwd>/paper/body.md`, `<cwd>/paper.md`, `<cwd>/docket.json`,
    names it guessed, against a grok sandbox that holds only `.grok/config.toml`.
    One paper (`10.1016--j.ynstr.2021.100304`) stalled mid-thrash and held a
    worker for 70 minutes.

    ABSOLUTE PATHS, ALWAYS. Grok runs with `--cwd <sandbox>` and its own
    `<user_info>` tells the model "Prefer using relative paths over absolute
    paths"; claude runs with `workdir=None` and inherits whatever directory
    `metascience` was invoked from. Neither is the paper directory, so a
    relative path is wrong on both backends.
    """
    if not sources:
        # Named, not omitted. An adjudicator that is told nothing about the
        # paper's location should know that is OUR gap, not a reason to go
        # guessing -- the guessing is what cost the 66%.
        return ["## Where the paper is",
                "NOT SUPPLIED to this docket. Do not guess at filenames: you "
                "have no directory listing, and a `read_file` on a path you "
                "invented fails silently into your turn budget. Work from the "
                "docket rows and the paper text below, and say in your "
                "rationale that you could not re-read the source.", ""]

    lines = ["## Where the paper is",
             "ABSOLUTE paths. Your working directory is NOT the paper "
             "directory, on any backend -- a relative path will not resolve. "
             "Read the paper with `extract_xml` / `extract_pdf`, or "
             "`markdown/body.md` for the plain text.", ""]
    for label, value in sources.items():
        if not value:
            continue
        if isinstance(value, (list, tuple)):
            for v in value:
                lines.append(f"- {label}: `{v}`")
        else:
            lines.append(f"- {label}: `{value}`")
    lines.append("")
    lines.append("NEVER read a `*_from_xml.md` or `*_from_html.md`. Those are "
                 "fetchpdf's conversions, and MEASURED 2026-08-22 over 418 of "
                 "them, 152 (36%) dissolve their tables into the prose as "
                 "undelimited digit runs while their own header certifies "
                 "`tables: 0`. `markdown/body.md` is ours and keeps tables as "
                 "`[Table N: ...]` placeholders.")
    lines.append("")
    return lines


def _unchecked_block(unchecked: Any) -> list[str]:
    """Each analyst's `unchecked` list, handoff notes included.

    Both analyst prompts say a handoff note in `unchecked` "is how your
    suspicion reaches the adjudicator", but the docket never carried it: the
    two analysts run concurrently, so the note had no reader at all. MEASURED
    2026-10-16 on 10.1371--journal.pone.0042828 (sonnet, v1.78.0): the
    science agent wrote that the Table 2 count means "look inconsistent with
    GRIM at n=6", the tools agent never ran GRIM, and 7 of the 20 means fail
    it. Bounded, and the bound is announced."""
    import json as _json
    rows = [(str(prod), u) for prod, items in (unchecked or {}).items()
            for u in (items or []) if isinstance(u, dict)]
    if not rows:
        return []
    lines = ["## What the analysts did NOT check (their `unchecked` lists, "
             "including handoff notes to each other)"]
    used, shown = 0, 0
    for prod, u in rows:
        entry = {"producer": prod,
                 **{k: u.get(k) for k in ("location", "reason", "n_cells")
                    if u.get(k) is not None}}
        line = _json.dumps(entry, ensure_ascii=False)
        if used + len(line) > UNCHECKED_BUDGET_CHARS:
            break
        lines.append(line)
        used += len(line)
        shown += 1
    if shown < len(rows):
        lines.append(f"UNCHECKED CAP: {len(rows) - shown} of {len(rows)} "
                     "entries not shown.")
    lines.append("")
    return lines


def build_docket(merged_findings: list[dict], paper_text: str = "",
                 tally: str = "", second_look: Any = None,
                 sources: Any = None, unchecked: Any = None) -> dict:
    """The adjudicator's entire evidence packet, size-bounded and honest
    about every bound (a capped docket must announce itself).

    `sources` is an ordered mapping of label -> absolute path (or list of
    paths). It is part of the DOCKET rather than concatenated at the call site
    so the packet stays one object that knows what it contains -- and so this
    module's tests can assert the paths are in it.

    `unchecked` maps producer -> that analyst's `unchecked` entries (see
    `_unchecked_block`).
    """
    findings = [f for f in merged_findings or [] if isinstance(f, dict)]
    work = [f for f in findings if f.get("outcome") in ("problem", "undecided")]
    passes: dict[str, int] = {}
    for f in findings:
        if f.get("outcome") == "pass":
            key = str(f.get("technique"))
            passes[key] = passes.get(key, 0) + 1

    ranked = _ranked(work)
    itemized, overflow = ranked[:DOCKET_ROW_CAP], ranked[DOCKET_ROW_CAP:]
    withheld: dict[str, int] = {}
    for f in overflow:
        key = f"{f.get('producer')}/{f.get('technique')}"
        withheld[key] = withheld.get(key, 0) + 1

    lines = ["# Adjudication docket", ""]
    # FIRST, not last: this is what the model needs before it starts reaching
    # for tools, and a packet that buries it is a packet it will not read in
    # time.
    lines += _sources_block(sources)
    lines.append(f"{len(itemized)} finding(s) itemized below "
                 f"({len(work)} problem/undecided total).")
    if overflow:
        parts = ", ".join(f"{k}: {n}" for k, n in sorted(withheld.items()))
        lines.append(
            f"DOCKET CAP: {len(overflow)} row(s) withheld ({parts}). They "
            "will ship at their provisional severity -- this docket is "
            "PARTIAL and the record says so.")
    if passes:
        parts = ", ".join(f"{k}: {n} pass"
                          for k, n in sorted(passes.items()))
        lines.append(f"Checks that PASSED (not itemized): {parts}.")
    else:
        lines.append("No passing checks were recorded.")
    lines.append("")
    import json as _json
    for row in itemized:
        lines.append(_json.dumps(_docket_row(row), ensure_ascii=False))
    lines.append("")
    if second_look:
        lines.append("## Second-look worklist (decidable weaknesses per "
                     "accusation, from the deterministic annotators)")
        lines.append(_json.dumps(second_look, ensure_ascii=False)[:8000])
        lines.append("")
    lines += _unchecked_block(unchecked)
    if tally:
        lines.append("## Checks tally")
        lines.append(str(tally))
        lines.append("")
    text = paper_text or ""
    if text:
        clipped = text[:PAPER_TEXT_BUDGET_CHARS]
        note = ("" if len(text) <= PAPER_TEXT_BUDGET_CHARS else
                f" (text truncated at {PAPER_TEXT_BUDGET_CHARS:,} of "
                f"{len(text):,} chars -- use Read for the rest)")
        lines.append(f"## Paper text{note}")
        lines.append(clipped)
    else:
        lines.append("## Paper text")
        lines.append("NO EXTRACTED TEXT WAS AVAILABLE -- use Read on the "
                     "paper directory; do not clear or condemn from the "
                     "docket rows alone.")
    return {
        "text": "\n".join(lines),
        "n_itemized": len(itemized),
        "n_not_adjudicated": len(overflow),
        "included_ids": [_fid(f) for f in itemized],
        "overflow_ids": [_fid(f) for f in overflow],
    }


# ---------------------------------------------------------------------------
# apply() -- every bound in code
# ---------------------------------------------------------------------------

def _keep_provisional(f: dict, action: str = "kept",
                      rationale: str | None = None) -> None:
    f["severity"] = f.get("provisional_severity")
    f["severity_is_provisional"] = True
    adj = {"action": action,
           "rationale": rationale or "not addressed by the adjudicator"}
    f["adjudication"] = adj


def _clamp(model_sev: int, f: dict, category: str) -> int:
    """The severity clamps of spec section 5.4, in order. Records nothing
    itself -- the caller compares against the model's number.

    There is NO ceiling (v1.14.0): the adjudicator may write any rung 1-9.
    What remains bounds MOVEMENT and CHANNEL, not level: an upgrade may lift
    a finding at most `_UPGRADE_LIMIT` above its provisional unless it is a
    merged pattern (pervasiveness may express 6-9 that no single row could),
    an upgrade typed with an ineligible category reverts to the provisional,
    and a quarantined detector's row never rises above `QUARANTINE_CAP`.
    """
    prov = f.get("provisional_severity") or 0
    sev = model_sev
    if sev > prov and category != "merged_pattern":
        if category not in _UPGRADE_CATEGORIES:
            sev = max(prov, 1)          # upgrade with an ineligible category
        elif sev > prov + _UPGRADE_LIMIT:
            sev = prov + _UPGRADE_LIMIT
    if f.get("quarantined"):
        sev = min(sev, QUARANTINE_CAP)
    cap = _tool_verdict_cap(f)
    if cap is not None:
        sev = min(sev, cap)
    sev = min(sev, max(LEVELS))
    return max(sev, 1)


def _tool_verdict_cap(f: dict) -> int | None:
    """`severity9.TOOL_VERDICT_CAPS` for a finding: a registered-tool row whose
    own validated call came back consistent or indeterminate cannot be
    ranked above what that call supported (see severity9)."""
    from .registry import BY_NAME
    from .severity9 import tool_verdict_cap
    tv = f.get("tool_verdict") if isinstance(f.get("tool_verdict"), dict) else {}
    if not tv.get("validated"):
        return None
    return tool_verdict_cap(technique_is_tool=f.get("technique") in BY_NAME,
                            computed_by=f.get("computed_by"),
                            tool_verdict=tv.get("severity"))


def _tool_unsupported(f: dict) -> bool:
    """A finding its own tool did not support never headlines the review."""
    return _tool_verdict_cap(f) is not None


def apply(merged_findings: list[dict], adjudicator_output: dict,
          paper_text: str = "", image_delivery: dict | None = None) -> tuple[list[dict], dict]:
    """Deterministic, pure, no LLM. Joined on finding_id, never position.

    `paper_text` backs the evidence-quote verification of section 5.5 (the
    spec's signature omits it, but the verification it mandates cannot run
    without a haystack); empty text means every clear demotes -- the
    conservative direction.
    """
    findings = [f for f in merged_findings or [] if isinstance(f, dict)]
    by_id = {_fid(f): f for f in findings if _fid(f)}
    counts: dict[str, int] = {
        "n_kept": 0, "n_merged": 0, "n_discarded": 0, "n_downgraded": 0,
        "n_upgraded": 0, "n_unknown_ids": 0, "n_readonly_flip_attempts": 0,
    }
    haystack = _fold(paper_text)

    raw = adjudicator_output if isinstance(adjudicator_output, dict) else {}
    verdicts = [v for v in (raw.get("verdicts") or []) if isinstance(v, dict)]

    # Pass 1: index sane verdicts by id; count the rest.
    by_verdict: dict[str, dict] = {}
    for v in verdicts:
        fid = str(v.get("finding_id") or "")
        if fid not in by_id:
            counts["n_unknown_ids"] += 1
            continue
        for ro in ("impossible", "tool_verdict", "outcome", "producer",
                   "technique", "computed_by", "quarantined"):
            if ro in v:
                counts["n_readonly_flip_attempts"] += 1
        by_verdict[fid] = v

    # Pass 2: resolve actions (merge targets validated against verdict
    # actions, not just existence -- no chains, no into-discarded).
    def action_of(fid: str) -> str:
        v = by_verdict.get(fid)
        a = str(v.get("action")) if v else "kept"
        return a if a in _ACTIONS else "kept"

    for fid, v in by_verdict.items():
        f = by_id[fid]
        action = action_of(fid)
        category = str(v.get("category") or "none")
        rationale = str(v.get("rationale") or "")[:500]
        if ((f.get("inputs") or {}).get("ai_screening") or {}).get("evidence_packet"):
            receipt = (image_delivery or {}).get(fid, {})
            if not receipt.get("complete"):
                _keep_provisional(f, rationale="Image reinterpretation withheld: delivery of the "
                                  "screened candidate AND context images was not verified.")
                f["adjudication"]["image_delivery"] = receipt
                counts["n_image_delivery_withheld"] = counts.get("n_image_delivery_withheld", 0) + 1
                counts["n_kept"] += 1
                continue
        adj: dict[str, Any] = {"action": action, "rationale": rationale,
                               "category": category}

        if action == "merged":
            target = str(v.get("merged_into") or "")
            target_ok = (target in by_id and target != fid
                         and action_of(target) in
                         ("kept", "downgraded", "upgraded"))
            if not target_ok:
                counts["n_invalid_merges"] = counts.get("n_invalid_merges", 0) + 1
                _keep_provisional(f, rationale="invalid merge target "
                                  f"{target!r}; both rows kept")
                counts["n_kept"] += 1
                continue
            adj["merged_into"] = target
            tgt = by_id[target]
            tgt.setdefault("adjudication", {}).setdefault(
                "merged_from", []).append(fid)
            f["severity"] = None
            f["severity_is_provisional"] = False
            f["adjudication"] = adj
            counts["n_merged"] += 1
            continue

        # Evidence-quote verification: an INNOCENT-EXPLANATION clear rests on
        # something the paper says, so it must quote it (and the quote must
        # locate). A misapplication/insufficient_evidence discard rests on
        # the tool-input mismatch already in the record -- no paper quote
        # exists for it to carry.
        clears = (category == "innocent_explanation"
                  and action in ("discarded", "downgraded"))
        if clears:
            quote = str(v.get("evidence_quote") or "")
            # A FRAGMENT TOO SHORT TO PROVE ANYTHING IS NOT EVIDENCE.
            #
            # `_fold("   ")` is `""`, and `"" in haystack` is True, so a
            # whitespace-only `evidence_quote` PASSED the gate whose stated
            # purpose is that "a fabricated supporting sentence must not clear
            # a finding". So did the word "The". Verified for both.
            #
            # `quotes._MIN_FRAGMENT` is 12 and exists for exactly this reason --
            # "'the' or '0.05' appears in every paper, so requiring them found
            # would pass anything" -- and was not applied here. Imported rather
            # than restated so the two cannot drift.
            #
            # This makes CLEARING harder, which is the accusatory direction, so
            # it was measured before shipping: the archive contains ZERO
            # `innocent_explanation` verdicts and zero recorded evidence
            # quotes, so no existing clear is affected. A demoted clear keeps
            # the finding at its PROVISIONAL severity -- already capped by the
            # producer clamps -- and records why, rather than escalating
            # anything.
            from .quotes import _MIN_FRAGMENT
            folded = _fold(quote)
            if len(folded) < _MIN_FRAGMENT:
                counts["n_demoted_clears"] = counts.get("n_demoted_clears", 0) + 1
                _keep_provisional(
                    f, rationale="clear demoted: its evidence_quote is too "
                    f"short to prove anything ({len(folded)} characters after "
                    f"folding, minimum {_MIN_FRAGMENT}) -- a fragment this "
                    "short appears in every paper, so finding it shows "
                    "nothing")
                counts["n_kept"] += 1
                continue
            if not quote or _fold(quote) not in haystack:
                counts["n_demoted_clears"] = counts.get("n_demoted_clears", 0) + 1
                _keep_provisional(
                    f, rationale="clear demoted: its evidence_quote could "
                    "not be located in the paper -- a fabricated supporting "
                    "sentence must not clear a finding")
                counts["n_kept"] += 1
                continue
            adj["evidence_quote"] = quote

        if action == "discarded":
            f["severity"] = None
            f["severity_is_provisional"] = False
            f["adjudication"] = adj
            counts["n_discarded"] += 1
            continue

        if f.get("outcome") != "problem":
            # severity exists only on problem rows; a kept/downgraded verdict
            # on a pass/undecided row records the action, never a number.
            f["severity"] = None
            f["severity_is_provisional"] = False
            f["adjudication"] = adj
            counts[f"n_{action}"] = counts.get(f"n_{action}", 0) + 1
            continue
        sev = v.get("severity")
        if not isinstance(sev, int) or isinstance(sev, bool) \
                or not 1 <= sev <= 9:
            _keep_provisional(f)
            counts["n_kept"] += 1
            continue
        final = _clamp(sev, f, category)
        if final != sev:
            adj["severity_from"] = sev
        title = v.get("title")
        if isinstance(title, str) and \
                _TITLE_BOUNDS[0] <= len(title) <= PRODUCER_TITLE_MAX:
            adj["title_was"] = f.get("title")
            f["title"] = title
            fit_row_title(f, "adjudicator")
        desc = v.get("description")
        if isinstance(desc, str) and \
                _DESC_BOUNDS[0] <= len(desc) <= _DESC_BOUNDS[1]:
            adj["description_was"] = f.get("description")
            f["description"] = desc
        f["severity"] = final
        f["severity_is_provisional"] = False
        # merge_from lists written by other rows must survive:
        existing = f.get("adjudication") or {}
        if existing.get("merged_from"):
            adj["merged_from"] = existing["merged_from"]
        f["adjudication"] = adj
        counts[f"n_{action}"] = counts.get(f"n_{action}", 0) + 1

    # Pass 3: the silence rule for everything the model never mentioned.
    for fid, f in by_id.items():
        if "adjudication" not in f or (
                f.get("adjudication", {}).get("action") is None):
            _keep_provisional(f)
            counts["n_kept"] += 1
        elif "action" not in f["adjudication"]:
            # a row holding only merged_from from pass 2
            f["adjudication"]["action"] = "kept"
            f["adjudication"].setdefault(
                "rationale", "merge target; severity assigned above")
            if f.get("severity") is None and f.get("outcome") == "problem" \
                    and not f["adjudication"].get("merged_into"):
                _sev = f.get("provisional_severity")
                f["severity"] = _sev
                f["severity_is_provisional"] = True
            counts["n_kept"] += 1

    # Paper block.
    paper = raw.get("paper") if isinstance(raw.get("paper"), dict) else {}
    p_sev = paper.get("paper_severity")
    if isinstance(p_sev, int) and not isinstance(p_sev, bool):
        p_sev = max(1, min(p_sev, max(LEVELS)))
    else:
        p_sev = None
    headline = str(paper.get("headline_finding_id") or "")
    h = by_id.get(headline)
    headline_ok = (h is not None and h.get("outcome") == "problem"
                   and h.get("adjudication", {}).get("action")
                   in ("kept", "downgraded", "upgraded")
                   and not h.get("cross_check") == "not_run"
                   and not _unscreened(h)
                   and not _tool_unsupported(h))
    if not headline_ok:
        counts["n_headline_fallback"] = counts.get("n_headline_fallback", 0) + 1
        candidates = [f for f in findings
                      if f.get("outcome") == "problem"
                      and isinstance(f.get("severity"), int)
                      and f.get("adjudication", {}).get("action")
                      in ("kept", "downgraded", "upgraded")
                      and not _unscreened(f)
                      and not _tool_unsupported(f)]
        candidates.sort(key=lambda f: (-(f.get("severity") or 0), _fid(f)))
        headline = _fid(candidates[0]) if candidates else None

    summary = {
        "ran": True,
        "verdict": paper.get("verdict"),
        "paper_severity": p_sev,
        "headline_finding_id": headline or None,
        "confidence": paper.get("confidence"),
        "summary": str(paper.get("summary") or "")[:2000],
        **counts,
        "failure": None,
    }
    return findings, summary


def _unscreened(row: dict) -> bool:
    """An image candidate no AI review looked at (`image_analysis` with
    `ai_screening: false`). The rulebook says a quarantined row never headlines;
    for these the rule is enforced HERE, because a model choosing one as the
    headline would publish a detector's guess as the paper's lead finding."""
    if row.get("producer") == "raw_data_track":
        # The raw-data detector's rows are never reviewed by anyone before
        # the report: the same rule, for the same reason.
        return True
    screening = (row.get("inputs") or {}).get("ai_screening")
    return isinstance(screening, dict) and screening.get("status") == "not_run"


def apply_skip(merged_findings: list[dict], *, skipped_reason: str | None = None,
               failure: str | None = None) -> tuple[list[dict], dict]:
    """The skip-entirely paths (budget floor, zero findings, crash before
    apply). Per the skip-vs-silence pin: NO per-row adjudication object is
    written -- its absence is the statement 'the adjudicator never saw this
    run' -- and every `impossible` row is stamped `cross_check: "not_run"`
    (the R ground-truth surface is adjudicator-only; an unrun cross-check
    must never read as a passed one)."""
    findings = [f for f in merged_findings or [] if isinstance(f, dict)]
    for f in findings:
        f["severity"] = f.get("provisional_severity")
        f["severity_is_provisional"] = True
        f.pop("adjudication", None)
        if f.get("impossible"):
            f["cross_check"] = "not_run"
    summary = {
        "ran": False,
        "skipped_reason": skipped_reason,
        "failure": failure,
        "n_kept": len(findings),
    }
    return findings, {k: v for k, v in summary.items() if v is not None
                      or k in ("skipped_reason", "failure")}
