"""One tool call, rendered as a self-contained VIGNETTE.

WHAT WAS WRONG WITH THE LEDGER PAGE. "Chain of reasoning" is the only surface
in the bundle that shows individual checks, and it showed them as two JSON
dumps under the headings `Input` and `Result`. Measured on the two runs this
was designed against -- `10.1073--pnas.0801268105/forensic_review_2026-08-16`
(36 calls) and `10.1007--s11031-011-9216-y/forensic_review_2026-08-17_scalefix`
(62 calls) -- a `grimmer_check` result carries 19 keys and runs to 24 across
the archive, of which the reader needs four and the rest are scaffolding. The
page was complete and unreadable, which in this repository is a named failure:
built, tested, consumed by nothing. A reader who cannot follow one check has
not been shown the working; they have been shown that working exists.

THE FIVE PARTS, as Greg framed them on 2026-08-09: what we asked, what the
paper said, what the tool computed, what that means, and what would change the
answer. The unit is one call, and it must be followable without holding the
rest of the report in the reader's head.

WHY THE MAJORITY MATTERS MOST. Across the 68 archived ledgers in this repo --
2,106 calls, counting each run once and not again through the copy every bundle
keeps under `analysis/` -- the severities are `consistent` 845, `indeterminate`
311, `suspicious` 211, `impossible` 112, `highly_suspicious` 54, and 573 calls
that recorded none. Passes and refusals are 75% of every call that returned a
verdict. A rendering tuned only for flags would drop the denominator, and the
denominator is the difference between "we ran 42 checks and 2 flagged" and
"2 things are wrong with this paper". `severity_ledger` already caught this
document dropping its `consistent` verdicts once; this surface will not.

-----------------------------------------------------------------------------
THE RULES THIS MODULE KEEPS
-----------------------------------------------------------------------------
NOTHING IS INVENTED. Every sentence is either (a) a value the tool itself
returned, (b) a declaration from `registry` about the tool, or (c) a fixed
sentence whose truth is a property of the call's own recorded fields. There is
no per-tool prose written here for 54 tools: `purpose`, `evidence_meaning` and
`assumptions` are already declared once in the registry and are read, not
restated. A call with no `source_quote` gets a slot saying it recorded none --
never a filled slot.

NOTHING IS DECORATION. "What would change the answer" always carries at least
one lever, and one of them is unconditional because it is always true and
always the most important: this verdict is about the numbers listed under
"What we asked", and if one of them was mis-read the verdict is about a number
the paper does not contain. That is house failure mode #2 -- our failure
recorded as the paper's property -- stated at the point of use rather than in a
preamble nobody reaches.

NO SEVERITY DEFINITIONS LIVE HERE. `SEV_DEF` is the viewer's, hand-written in
the JS and pinned by `test_viewer_vocabulary_drift`; the verdict word is
rendered by the existing `sev()` chip. Restating the ladder in Python would
create the second copy that module exists to prevent. Likewise the quoted
passage: `sourceHtml` already renders it with the verification verdict, so
`paper` carries only the STATE and lets the existing renderer speak.
"""
from __future__ import annotations

from typing import Any

#: The five headings, in order, shipped to the viewer rather than restated
#: there. `key` indexes into a composed vignette; `label` is what the reader
#: sees. One copy, so a part cannot be renamed in the JS and left behind here.
PARTS: tuple[tuple[str, str], ...] = (
    ("asked", "What we asked"),
    ("paper", "What the paper said"),
    ("computed", "What the tool computed"),
    ("means", "What that means"),
    ("changes", "What would change the answer"),
)

#: Lifted into their own slots, so repeating them among the tool's numbers
#: would be noise. `source_quote`/`source_locator` are part 2; the rest are
#: rendered as prose in parts 3 and 5.
_RENDERED_ELSEWHERE = frozenset({
    "severity", "methodology", "explanation", "note", "notes", "failure_reason",
    "source_quote", "source_locator", "source_quote_supplied",
    "caveat", "caveats", "warnings", "assumed_conventions", "benchmark_caveat",
    "discreteness_caveat", "bound_source", "discreteness_source", "provenance",
    "as_reported", "discriminating_power",
})

#: What a parameter's registry role means to a reader who has never seen the
#: signature. `precision` is separated from `guard` for the reason the registry
#: separates them: a wrong printed precision produced a measured 41.1% of GRIM
#: rows and 73.6% of DEBIT rows falsely reported `impossible`, so it is the
#: input most worth showing a reader by name.
_ROLE_LABEL = {
    "exact_value": "the value under test",
    "precision": "the precision it was printed to",
    "guard": "a precondition we asserted",
    "metadata": "where the value came from",
    "value": "input",
}

#: A value long enough that printing it whole would bury the ones that matter.
#: The raw result is still on the same card, one click away, so nothing is lost.
_VALUE_CLIP = 160

#: Beyond this the numbers stop being readable as a list. `get_table` returns
#: up to 29 keys and `grimmer_check` up to 24; both are still fully present in
#: the raw result below, and the count of what was elided is printed.
_MAX_FIGURES = 14


def _short(value: Any) -> str:
    """One line, readable, and never a machine path.

    File arguments arrive as absolute paths. The scrubber already removes the
    home directory, but a 90-character path in the list of what we asked pushes
    `mean`, `sd` and `n` off the reader's screen, so only the leaf is shown.
    """
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "not supplied"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, str):
        text = " ".join(value.split())
        if "/" in text and text.endswith((".pdf", ".xml", ".md", ".json")):
            text = text.rsplit("/", 1)[-1]
        return text if len(text) <= _VALUE_CLIP else text[:_VALUE_CLIP] + " ..."
    import json as _json
    text = _json.dumps(value, default=str)
    return text if len(text) <= _VALUE_CLIP else text[:_VALUE_CLIP] + " ..."


def _roles(card: dict | None) -> dict[str, str]:
    """Parameter name -> registry role, for whichever inputs the card declares."""
    out: dict[str, str] = {}
    for key in ("minimum_inputs", "optional_inputs"):
        for param in (card or {}).get(key) or []:
            if isinstance(param, dict) and param.get("name"):
                out[str(param["name"])] = str(param.get("role") or "value")
    return out


def _texts(value: Any) -> list[str]:
    """A result field as a list of unique, whitespace-normalised lines.

    Deduplicated as INSURANCE, not as a fix for an observed defect: 0 of the
    111 caveat/warning lists in the archive carries an internal duplicate. Kept
    anyway because it costs one set-membership test, and because the failure it
    prevents -- one reservation rendered as two, which reads as two independent
    reservations -- is one a reader has no way to detect.
    """
    items = value if isinstance(value, list) else ([value] if value else [])
    out: list[str] = []
    for item in items:
        text = " ".join(str(item).split())
        if text and text not in out:
            out.append(text)
    return out


def _first_text(result: dict, *keys: str) -> str:
    for key in keys:
        value = result.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())
        if isinstance(value, list) and value:
            joined = "; ".join(str(v) for v in value if str(v).strip())
            if joined.strip():
                return " ".join(joined.split())
    return ""


# ---------------------------------------------------------------------------
# Part 1 -- what we asked
# ---------------------------------------------------------------------------

def _asked(entry: dict, card: dict | None) -> dict:
    """The question, from the registry, and the arguments it was asked with.

    The question is `purpose`, declared once per tool beside the code that
    implements it. Generating a sentence per tool here would be a second
    description of 54 tools, and the two would disagree within a month.
    """
    roles = _roles(card)
    raw = entry.get("input")
    values = []
    for name, value in (raw if isinstance(raw, dict) else {}).items():
        if name in ("source_quote", "source_locator"):
            continue                        # part 2 renders these
        values.append({
            "name": str(name),
            "value": _short(value),
            "role": _ROLE_LABEL.get(roles.get(str(name), "value"), "input"),
        })
    question = str((card or {}).get("purpose") or "")
    # A tool with no registry card is not a forensic check -- `Read` and the
    # harness's `StructuredOutput` are the whole population across the archived
    # corpus. Saying so is more use to a reader than an empty heading, and it
    # matches `_tool_cards`, which declines to list them as undescribed.
    #
    # The sentence is written HERE and not in the viewer's JS for the reason
    # that governs this whole module: prose the page authors is prose no test
    # reaches, and three such sentences were measurably wrong on a real bundle
    # before `viewer_facts` moved them into Python.
    return {
        "question": question or (
            "Not a forensic check. This call reads a file or emits the run's "
            "structured output; it asks nothing of the paper."
            if card is None else
            "This check declares no purpose in our registry. That is a gap in "
            "OUR documentation, not a statement about the paper."),
        "no_question": not question,
        "not_a_check": card is None,
        "values": values,
    }


# ---------------------------------------------------------------------------
# Part 2 -- what the paper said
# ---------------------------------------------------------------------------

#: The three states a call's sourcing can be in. `unrecorded` and `not_offered`
#: are DIFFERENT and were once the same sentence: an extractor has no reported
#: value to source and was never given the argument, while a check that had the
#: argument and left it empty declined to say where its numbers came from.
#: Collapsing them reports a design decision as a coverage failure on every run.
def _paper(entry: dict) -> dict:
    if entry.get("source_quote"):
        return {"state": "quoted"}
    if entry.get("sourceable"):
        return {"state": "unrecorded"}
    return {
        "state": "not_offered",
        "note": ("This call reads the document rather than a reported value, so "
                 "it was never offered a source passage. There is no quote to "
                 "show and none is missing."),
    }


# ---------------------------------------------------------------------------
# Part 3 -- what the tool computed
# ---------------------------------------------------------------------------

def _computed(entry: dict, result: dict | None) -> dict:
    """The verdict, the mechanism, and the tool's own numbers.

    `methodology` is the mechanism sentence the tool writes about itself -- it
    is present on 1,420 of the 1,533 archived results that carry a severity, so
    for 93% of graded calls the "how" needs no help from here. Where it is absent the
    slot says so rather than paraphrasing the code.

    The numbers are the result's own scalars, minus what other parts already
    render. Not an allowlist: a curated set of interesting keys per tool would
    silently drop the field that mattered on the one paper nobody tested, and
    the omission would be invisible. Everything elided is counted, and the raw
    result sits on the same card.
    """
    if entry.get("is_error"):
        raw = str(entry.get("result") or "").strip()
        return {
            "errored": True,
            "verdict": None,
            # OUR FAILURE, LABELLED AS OURS. A tool that raised tells the reader
            # nothing about the paper, and the one thing this must never do is
            # let a crash read as an absence of findings.
            "headline": ("This call FAILED. That is a fact about this run, not "
                         "about the paper: nothing was checked here, and nothing "
                         "here clears or implicates anything."),
            "detail": raw.split("\n")[0][:400],
            "figures": [], "n_more": 0,
        }
    if not isinstance(result, dict):
        raw = str(entry.get("result") or "").strip()
        return {
            "errored": False,
            "verdict": None,
            "headline": ("This call returned text, not a structured verdict. "
                         "It computed nothing to pass or fail."),
            "detail": raw.split("\n")[0][:400],
            "figures": [], "n_more": 0,
        }

    figures = []
    elided = 0
    for key, value in result.items():
        # `_ALTERNATIVES` is named here as well as in `_RENDERED_ELSEWHERE`
        # because part 5 spells those booleans out in prose ("still infeasible"),
        # and the same fact twice on one card -- once as `feasible_ignoring_bounds
        # no`, once as a sentence -- is the density this rendering exists to undo.
        if key in _RENDERED_ELSEWHERE or key in _ALTERNATIVES:
            continue
        if isinstance(value, (int, float, bool)) or (
                isinstance(value, str) and len(value) <= _VALUE_CLIP):
            if len(figures) < _MAX_FIGURES:
                figures.append({"name": key, "value": _short(value)})
            else:
                elided += 1
        else:
            elided += 1
    return {
        "errored": False,
        "verdict": result.get("severity") or None,
        "method": _first_text(result, "methodology"),
        "no_method": not _first_text(result, "methodology"),
        "detail": _first_text(result, "explanation", "failure_reason", "note", "notes"),
        "figures": figures,
        "n_more": elided,
    }


# ---------------------------------------------------------------------------
# Part 4 -- what that means
# ---------------------------------------------------------------------------

#: WHAT THIS CHECK DID NOT ESTABLISH, per verdict. The severity word's own
#: definition is the viewer's (`SEV_DEF`); these say what a reader may carry
#: away from THIS call, which is the sentence the ledger page never had.
#:
#: The `consistent` line is the one that earns the module. 845 of 2,106
#: archived calls are passes, and `inertness` measured 90 of 159 archived GRIM
#: calls returning `consistent` from a regime where the check COULD NOT FAIL --
#: every one of them presented to a reader as a pass. Even a pass that could
#: have failed is a pass on one arithmetic identity over three printed numbers,
#: and this is the only place in the bundle that says so.
_MEANS = {
    "consistent": ("A PASS, and only on what this check tests. It does not say "
                   "the analysis is correct, that the underlying data exist, or "
                   "that any other check would pass -- only that these numbers "
                   "do not contradict each other in the way this check looks for."),
    "indeterminate": ("A REFUSAL, not a pass. A precondition could not be "
                      "established, so the check declined to judge. The paper is "
                      "neither cleared nor implicated on this point, and reading "
                      "this as 'nothing found' is the mistake it exists to prevent."),
    "suspicious": ("A QUESTION, not a determination. Something does not "
                   "reconcile; a reporting or transcription slip is the "
                   "commonest cause and is not ruled out."),
    "highly_suspicious": ("Hard to explain innocently, and NOT arithmetically "
                          "ruled out. This is still short of a claim that no "
                          "dataset could produce these numbers."),
    "impossible": ("No dataset satisfying the stated preconditions produces "
                   "these numbers. It is a statement about the arithmetic as "
                   "printed -- not about anyone's conduct, and a typo produces "
                   "it just as readily as anything worse."),
}


def _means(entry: dict, result: dict | None, card: dict | None) -> dict:
    verdict = (result or {}).get("severity") if isinstance(result, dict) else None
    evidence = str((card or {}).get("evidence") or "")
    out: dict[str, Any] = {
        "verdict": verdict or None,
        "scope": _MEANS.get(str(verdict or ""), ""),
        "evidence": evidence,
        "evidence_meaning": str((card or {}).get("evidence_meaning") or ""),
        "ceiling": (card or {}).get("severity_ceiling") or None,
    }
    if card is None:
        # "it read a file" was wrong for half the population: the two uncarded
        # tools in the archive are `Read`, which does, and the harness's
        # `StructuredOutput`, which emits the run's own result object. Naming
        # only one of them made the other's card say something false about it.
        out["scope"] = ("This is not one of the forensic checks -- it moves a "
                        "file or the run's own output around. It computes "
                        "nothing about the paper and can neither clear nor "
                        "implicate it.")
    elif verdict is None and evidence == "descriptive":
        out["scope"] = ("This call returned DATA, not a judgement. Descriptive "
                        "tools render no verdict; what follows from these "
                        "numbers is decided by the checks that read them.")
    elif verdict is None:
        # A GRADING TOOL THAT GRADED NOTHING, which is not the same as a
        # descriptive one and must not be worded like it. 44 of the 2,106
        # archived calls land here -- 36 of them `statcheck`, which returns
        # `errors_found: 20` and no `severity` at all, so it registers as a
        # blank in every severity tally in this bundle.
        #
        # Named rather than smoothed over, because the smoothing is the third
        # house failure mode exactly: absence read as evidence. A check that
        # recorded no verdict has not passed the paper.
        out["no_verdict"] = True
        out["scope"] = ("This call recorded NO verdict. It ran and returned its "
                        "numbers but graded none of them, so nothing here is a "
                        "pass and nothing here is a flag -- reading it as either "
                        "is reading something the tool did not say. That is a "
                        "gap in OUR tool's output, not a finding about the paper.")
    elif not out["scope"]:
        # A severity we have no line for. Named rather than left blank: a silent
        # empty slot is how a vocabulary drifts without anyone noticing.
        out["scope"] = ("This review has no plain-language reading for the "
                        f"verdict `{verdict}`. That is a gap in our "
                        "documentation, not a statement about the paper.")
    if entry.get("validated") is False or entry.get("surface") == "UNVALIDATED":
        out["unvalidated"] = ("This call did not go through a validated forensic "
                              "tool, so whatever it returned is not a computed "
                              "check result.")
    return out


# ---------------------------------------------------------------------------
# Part 5 -- what would change the answer
# ---------------------------------------------------------------------------

#: Result fields that name a condition the verdict rests on, with the reading
#: for each recorded value. Sourced from the archived corpus, not imagined:
#: `bound_source` appears on 71 calls (assumed 41 / stated 28 /
#: logically_necessary 2), `discreteness_source` on 31 (stated 21 / assumed 9 /
#: logically_necessary 1), `provenance` on 69.
#:
#: A VALUE WITH NO READING GETS NO LEVER, which is the right silence. Eight
#: archived `provenance` values are `publisher_xml`, `reported_table`,
#: `table_text` or `text`, and this module has no declared reading for what
#: each implies about a rounding interval. Guessing one would be exactly the
#: invention the module forbids; the omission costs a lever, a guess would cost
#: the reader a false premise.
#:
#: The `stated` readings are here on purpose. A lever that only ever fires when
#: something is wrong teaches a reader that its absence means nothing, when in
#: fact "the paper gave us the bounds" is exactly what tells them this verdict
#: does NOT rest on an assumption of ours.
_LEVERS: dict[str, dict[str, tuple[str, str]]] = {
    "bound_source": {
        # THE CAP IS CONDITIONAL, AND THE WORDING HAS TO BE. An earlier draft
        # said a verdict resting on assumed bounds "is capped below
        # `impossible`" -- and the first real call it rendered was a
        # `grimmer_check` with `bound_source: assumed` and a verdict of
        # `impossible`, because its failure mode was `sd_granularity`, which is
        # bound-free. A caveat that contradicts the verdict printed six lines
        # above it teaches a reader to stop reading the caveats.
        "assumed": ("The scale bounds are ours, not the paper's",
                    "This review supplied the minimum and maximum; the paper was "
                    "not quoted stating them. Anything in this verdict that "
                    "depends on the range rests on our assumption rather than "
                    "the paper's, and a finding that rests ONLY on assumed "
                    "bounds is capped below `impossible`. Whether this one "
                    "depends on them is answered by the alternatives the check "
                    "tried, below."),
        "stated": ("The bounds came from the paper",
                   "The scale was read from the paper's own text, so this verdict "
                   "does not rest on a range we assumed."),
        "logically_necessary": ("The bounds cannot be otherwise",
                                "The range follows from what the quantity is, "
                                "whatever the paper says, so there is nothing "
                                "here for a reader to grant us."),
    },
    "discreteness_source": {
        "assumed": ("We assumed each subject contributed a whole number",
                    "The paper was not quoted establishing that the responses are "
                    "integers. A continuous measure, or a mean of several items, "
                    "produces this same arithmetic from honest data -- so a "
                    "granularity verdict on an assumed discreteness caps at "
                    "`suspicious`."),
        "stated": ("The paper states the responses are whole numbers",
                   "Integer responses were read from the paper -- a quoted scale "
                   "definition or item count -- not assumed by us."),
        "logically_necessary": ("Whole numbers are unavoidable here",
                                "The quantity cannot take a fractional value, so "
                                "the granularity premise needs no concession."),
    },
    "provenance": {
        "measured": ("These numbers were read off a figure",
                     "A measured value has no last printed digit, so exact "
                     "arithmetic over its rounding interval is undefined and the "
                     "check refuses rather than judging."),
        "printed_table": ("Read from a printed table",
                          "The values carry a last printed digit, which is what "
                          "the rounding interval in this check is computed from."),
        "printed_text": ("Read from the running text",
                         "The values carry a last printed digit, which is what "
                         "the rounding interval in this check is computed from."),
    },
}

#: Tool-authored caveats, carried through VERBATIM under the heading each one
#: deserves. The tool knows things about its own run that nothing here can
#: reconstruct -- which conventions it assumed, which independence it took on
#: trust -- and the honest move is to repeat it, not to summarise it.
#:
#: `warnings` is separated from the rest and headed differently because it is
#: usually OUR READER FAILING, not a caveat about the paper: the worst archived
#: `parse_cells_typed` call emits sixteen of them, of the form "could not parse
#: '1458 EUR' as a numeric cell". Filed as caveats they read as sixteen
#: reservations about the authors' table. They are sixteen cells our
#: parser could not type, which is house failure mode #2 -- our failure
#: recorded as the paper's property -- and the heading has to say so.
_CAVEAT_FIELDS = ("caveats", "caveat", "assumed_conventions", "benchmark_caveat",
                  "discreteness_caveat")

#: How many `warnings` are quoted before the rest are counted. Beyond this the
#: repeated items stop informing and start hiding the levers below them; the
#: number elided is stated in the same lever, and every one of them is in the
#: raw result on the same card. The `_CAVEAT_FIELDS` above are NOT capped --
#: they are deduplicated instead, and the longest run in the archive is the
#: five distinct caveats `multiplicity_report` writes about its own family.
_MAX_WARNINGS = 5

#: Alternatives the tool records having tried, and how to read each boolean.
#: These are the reader's answer to "did it only fail under one convention?" --
#: the question that separates a house style from a fabrication.
_ALTERNATIVES = {
    "feasible_ignoring_bounds": "ignoring the scale bounds entirely",
    "population_feasible_in_bounds": "the population (n) SD convention, within bounds",
    "population_feasible_ignoring_bounds": "the population (n) SD convention, bounds ignored",
    "consistent_under_population_convention": "the population (n) SD convention",
}


def _read_off_lever(entry: dict, card: dict | None) -> dict:
    """ALWAYS PRESENT, whatever the call returned.

    Every verdict on this page is a verdict about the numbers in part 1. If one
    of them is not what the paper printed then the arithmetic is impeccable and
    about nothing -- which is house failure mode #2, our extraction failure
    recorded as the paper's property. It is the single lever that applies to
    all 2,106 archived calls, so it is not conditional on a field being
    present.

    Its strength is conditional, though, and the wording tracks the verification
    verdict decided by `quotes.verify_ledger` against the paper -- never by the
    model that made the call.
    """
    tail = ("If any value above is not what the paper printed, this verdict is "
            "about a number the paper does not contain.")
    verified = str(entry.get("source_quote_verified") or "")
    if card is None:
        return {
            "lever": "Nothing -- this call is bookkeeping, not evidence",
            "detail": ("It is listed so the chain of reasoning has no gaps. A "
                       "ledger that hides its own housekeeping is one a reader "
                       "cannot count."),
        }
    if not entry.get("sourceable") and not entry.get("source_quote"):
        return {
            "lever": "A different extraction would give this call different text",
            "detail": ("What this call saw is one extraction of one file. A "
                       "damaged text layer, an image-only table or a different "
                       "extractor yields different input -- and every check "
                       "downstream reads this output, not the PDF."),
        }
    if verified in ("verbatim", "elided"):
        return {
            "lever": "The numbers were read from a passage we located in the paper",
            "detail": "The quoted passage was found in the paper's own text. " + tail,
        }
    if entry.get("source_quote"):
        return {
            "lever": "We could not locate the passage these numbers came from",
            "detail": ("The review quoted a passage, and our search of the "
                       "extracted text did not find it -- most often a limit of "
                       "our extraction rather than anything about the authors. "
                       "A mis-read is not ruled out. " + tail),
        }
    return {
        "lever": "This call did not record where its numbers came from",
        "detail": ("No source passage was supplied, so nothing traces these "
                   "values back to the page here. " + tail),
    }


def _changes(entry: dict, result: dict | None, card: dict | None) -> list[dict]:
    levers: list[dict] = []
    result = result if isinstance(result, dict) else {}

    for field, readings in _LEVERS.items():
        value = str(result.get(field) or "")
        if value in readings:
            lever, detail = readings[value]
            levers.append({"lever": lever, "detail": detail})

    # DIRECTLY AFTER THE BOUNDS LEVER, because it is what settles it: the
    # assumed-bounds caveat asks whether this verdict depends on the range, and
    # `feasible_ignoring_bounds` answers it. Separated by two other levers, the
    # question and its answer read as unrelated.
    tried = [(name, result[key]) for key, name in _ALTERNATIVES.items()
             if isinstance(result.get(key), bool)]
    if tried:
        levers.append({
            "lever": "Alternative conventions the check already tried",
            "detail": "; ".join(
                f"{name}: {'still feasible' if ok else 'still infeasible'}"
                for name, ok in tried)
            + ". A result that fails under one convention and passes under "
              "another is a reporting style, not a fabrication -- these say "
              "which happened.",
        })

    # PRECISION, WHEN THE CALL RECORDS IT. Too many digits always shrinks the
    # admissible set, and a smaller admissible set is what `impossible` means --
    # so this is a lever that moves in the accusing direction, and a reader
    # deciding how much to trust a flag is entitled to see which precision the
    # check was actually run at.
    printed = [f"{k} = {v}" for k, v in (entry.get("input") or {}).items()
               if k.startswith("decimals") and v is not None]
    if printed:
        levers.append({
            "lever": "The verdict was computed at the precision we read: "
                     + ", ".join(printed),
            "detail": ("Printed precision sizes the rounding interval this whole "
                       "check is about. Read one digit too many and values that "
                       "are fine become impossible; one too few and real "
                       "problems disappear."),
        })

    for field in _CAVEAT_FIELDS:
        for text in _texts(result.get(field)):
            levers.append({"lever": "The check states its own caveat",
                           "detail": text})

    warnings = _texts(result.get("warnings"))
    if warnings:
        shown = warnings[:_MAX_WARNINGS]
        more = len(warnings) - len(shown)
        levers.append({
            "lever": f"{len(warnings)} value"
                     f"{'' if len(warnings) == 1 else 's'} this call could not read",
            "detail": " | ".join(shown)
                      + (f" | and {more} more, all in the raw result below."
                         if more else "")
                      + " A value we could not parse was not checked. It is not "
                        "a value the paper got wrong, and nothing about it is "
                        "cleared by this call's verdict.",
        })

    levers.append(_read_off_lever(entry, card))

    # The rest of the tool's declared preconditions, POINTED AT rather than
    # reprinted. A run makes several times more calls than it uses tools, so
    # inlining five assumptions per call would bury the levers above in
    # boilerplate -- the same reason `_tool_cards` is one card per tool.
    assumptions = [a for a in (card or {}).get("assumptions") or [] if str(a).strip()]
    if assumptions:
        levers.append({
            "lever": f"{len(assumptions)} further precondition"
                     f"{'' if len(assumptions) == 1 else 's'} this check declares",
            "detail": "Where one of these is unmet the verdict is capped, not "
                      "merely caveated.",
            "card": str((card or {}).get("tool") or ""),
        })
    return levers


# ---------------------------------------------------------------------------

def compose(entry: dict, result: dict | None, card: dict | None) -> dict:
    """Build the five-part vignette for one distilled ledger entry.

    `result` is the call's result PARSED, passed in rather than re-parsed from
    `entry["result"]`: the ledger entry carries the result clipped to 2,000
    characters, and a `check_table` result runs to 30 kB. Composing from the
    clipped copy would silently drop the tail of every large result -- which
    would be this repository's signature defect, a degraded output reported as
    a complete one.
    """
    return {
        "asked": _asked(entry, card),
        "paper": _paper(entry),
        "computed": _computed(entry, result),
        "means": _means(entry, result, card),
        "changes": _changes(entry, result, card),
    }
