"""A model as SECOND READER of the account (Greg, 2026-09-06: "could any of this
verification of all the expected outputs be done by a model, rather than some
automated process? I.e. a sanity check").

WHAT IT IS. The account is handed, rendered, to a model together with the paper,
and the model says what looks wrong, unsupported or inconsistent -- the kind of
thing no invariant can see: that `EBP adherence 5.23 (1.13)` is a mean because
the Methods define it as one; that a table read as coefficient/SE in one place
and mean/SD in another has one right answer. It also spot-checks a fixed sample
of values against the paper's own text, one by one.

WHAT IT IS NOT. Not a certificate. Every note is a MODEL READING to be verified,
carried as such and rendered under that heading; the model-free denominator
(`numerals`) and the conservation checks (`reconstruct.verify`) are not touched
by it and it is told not to compute coverage or completeness -- "the denominator
must be independent of the finder" (register.py). A reviewer that could bless
its own account's completeness would be the self-certification this codebase
exists to refuse.

TWO ACCOUNTS. Given two independent accounts of one paper (test-retest), the
same reader lists where they disagree and which reading the paper supports,
with the evidence. That turns an instability measurement into a list of
decidable questions.
"""
from __future__ import annotations

import json
import random
import re
from typing import Any

from . import passes as _passes

REVIEW_VERSION = "review/2-table-renders"
SEVERITIES = ("observation", "needs_check", "likely_error")
VERDICTS = ("supported", "not_found", "contradicted", "ambiguous")
SAMPLE_SIZE = 20
#: MEASURED 2026-09-07 over the rendered accounts on disk: ajcp.70049's is
#: 160,309 characters and the old 160,000 cap ate the last 309 -- the tail of
#: the final evidence section, silently; jamanetworkopen.37679's is 230,093. A
#: reviewer asked what looks wrong in the account must be shown ALL of it, and
#: the clipped tail is evidence, not chrome. The cap is now above the largest
#: account we hold; at 240,000 characters (about 60k tokens) it sits beside a
#: 70,000-character paper inside any current context window.
ACCOUNT_CHARS = 240_000
PAPER_CHARS = 70_000
#: MEASURED on the account this index was built for (ajcp.70049 whole-text, 370
#: values, 15 comparisons, 8 studies): the full index is 52.0k characters, and a
#: 40k cap dropped 120 of the 370 value ids -- a third of the paper unaddressable
#: on the very run whose 12 disagreements applied nothing. Trimming the label
#: columns does not buy it back (20-character labels still give 49.2k; the ids
#: themselves are the bulk), so the cap is the thing to set, not the widths. 60k
#: is ~15k tokens beside a prompt already carrying two 80k accounts and the paper.
ID_INDEX_CHARS = 60_000


def _s(d: str = "") -> dict:
    return {"type": "string", "description": d} if d else {"type": "string"}


def _nullable(x: dict) -> dict:
    return {"anyOf": [x, {"type": "null"}]}


REVIEW_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "overall": _s("Two or three sentences: what the account gets right, and the one or two "
                      "things a human should look at first."),
        "notes": {"type": "array", "items": {"type": "object", "properties": {
            "where": _s("The account section, table id, value id or variable id the note is about."),
            "what": _s("What looks wrong, unsupported or inconsistent, in one sentence."),
            "why": _s("The evidence: what the paper says, quoted or located."),
            "severity": {"type": "string", "enum": list(SEVERITIES)},
            "suggested_check": _nullable(_s("What would settle it (a passage to read, a cell to compare, "
                                            "a recomputation), or null.")),
        }, "required": ["where", "what", "why", "severity", "suggested_check"], "additionalProperties": False}},
        "spot_checks": {"type": "array", "items": {"type": "object", "properties": {
            "value_id": _s("EXACTLY the id given."),
            "verdict": {"type": "string", "enum": list(VERDICTS)},
            "evidence": _s("The passage or cell in the paper you compared it with, quoted; or what you "
                           "searched for and did not find."),
            "note": _nullable(_s()),
        }, "required": ["value_id", "verdict", "evidence", "note"], "additionalProperties": False}},
        "unstable_readings": {"type": "array", "items": {"type": "object", "properties": {
            "where": _s(), "reading": _s("The account's reading."),
            "paper_says": _s("What the paper supports instead, with the passage."),
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        }, "required": ["where", "reading", "paper_says", "confidence"], "additionalProperties": False},
            "description": "Places where the account's reading of a kind, a variable, a level or a group "
                           "is not the one the paper supports."},
    },
    "required": ["overall", "notes", "spot_checks", "unstable_readings"],
    "additionalProperties": False,
}

#: What an adjudication may change on a record: a KIND from the closed vocabulary,
#: or an id from the declared structure. Never a printed number, a quote, a count.
#: `kind` is a VARIABLE's kind and reaches records only through the structural
#: adjudication (`structure.apply_structural_adjudication`); it is gated exactly
#: as a value's `statistic` is, below, because it is the same premise seen one
#: level up -- what kind of number this is.
CORRECTABLE_FIELDS = ("statistic", "kind", "variable_id", "level_id", "group_id", "reference_group_id",
                      "coordinate.study_id", "coordinate.group_id", "coordinate.phase_id", "bounds.source")

#: The two fields that say WHAT KIND OF NUMBER a record is: a value's statistic
#: and a variable's kind. Both are a check's premise, so both are gated by the
#: same two rules -- a move that makes a record checkable needs a structural or
#: Methods anchor, and neither may be overruled on a header when the reading
#: came from the text (G11).
KIND_FIELDS = ("statistic", "kind")

#: WHERE the deciding evidence sits. Closed, so that the SCOPE of a correction is
#: a lookup rather than a reading of the adjudicator's prose: a sentence in the
#: Discussion cannot decide what the parenthetical in Table 2 is, and until the
#: adjudicator says which kind of thing decided it, nothing downstream can tell
#: the two apart. `recomputation` is a member so the model can say it, and is
#: refused on arrival (see `apply_adjudication`): the model's own arithmetic is
#: not evidence.
ANCHOR_KINDS = ("table_caption", "table_header", "table_footnote", "body_sentence_naming_table",
                "methods_definition", "recomputation", "other")

#: The anchors printed INSIDE a table -- the only ones that may SUPPLY a premise
#: a record did not have. Invariant 2 (CLAUDE.md 8d): a derived boundary may
#: NARROW a premise, never supply one. A prose sentence that supplies a group id
#: supplies a denominator, which is the documented route from a coverage win to a
#: false accusation (`25e2f9f`, reverted once for exactly this).
STRUCTURAL_ANCHORS = ("table_caption", "table_header", "table_footnote")

#: Anchors that may say what a number IS: the table's own structure, or the
#: Methods definition of the measure. `body_sentence_naming_table` is NOT here --
#: a sentence citing a table is enough to locate a correction within that table,
#: and not enough to make an unchecked number checkable.
KIND_DEFINING_ANCHORS = STRUCTURAL_ANCHORS + ("methods_definition",)

#: The `statistic_basis` values meaning the kind was decided by what the paper
#: SAYS rather than by the table's own furniture (`reconstruct.STATISTIC_BASES`
#: carries `citing_text`; `methods_definition` is named here as the anchor kind
#: of the same reading, so this set does not have to be revisited if a basis of
#: that name arrives). A reading resting on one of these has already weighed the
#: text, so a header disagreeing with it is not new evidence -- see G11.
TEXT_DERIVED_BASES = ("citing_text", "methods_definition")

#: The anchors that can answer a text-derived reading IN KIND: a sentence naming
#: the table, or the Methods definition of the measure. A header, caption or
#: footnote cannot -- it is the other half of the disagreement, not its referee.
TEXT_ANCHORS = ("body_sentence_naming_table", "methods_definition")

#: The statistic kinds a granularity or feasibility check consumes as a premise
#: (GRIM asks whether a MEAN is attainable from n integer observations; SPRITE
#: needs the SD beside it; `check_count_percent` needs the count and its
#: denominator). Moving a value INTO this set makes it checkable, so it is the
#: transition that can manufacture an accusation, and it is gated hardest.
#: Moving OUT of it -- `sd` to `se`, anything to `other` -- only removes checks.
#: A move BETWEEN two members (`sd` to `mean`) is gated the same way as a move
#: into the set: it changes WHICH check binds and on what premise, so it is not
#: the narrowing that the out-of-set moves are.
GRIM_ELIGIBLE_STATISTICS = ("mean", "count", "percentage", "proportion", "n", "sd", "sem", "median")

#: The same transition one level up: a VARIABLE kind that hands a granularity
#: check its premise (GRIM needs to know that one subject's value is an integer,
#: or k of a fixed K). Moving a variable INTO this set makes every value bound to
#: it checkable, so it is gated like a statistic move, not like a relabelling.
GRIM_ELIGIBLE_VARIABLE_KINDS = ("count", "integer_score", "binary", "ordinal",
                                "percentage_of_observations", "percentage_of_subjects",
                                "proportion")

#: The fields that NAME a premise: which study, arm, phase, variable or level a
#: number is about. Filling one that was None is SUPPLY; changing one that was
#: already filled is a correction of a reading the account already committed to.
PREMISE_FIELDS = ("coordinate.study_id", "coordinate.group_id", "coordinate.phase_id",
                  "group_id", "reference_group_id", "variable_id", "level_id")

_ANCHOR = {"type": "object", "properties": {
    "kind": {"type": "string", "enum": list(ANCHOR_KINDS),
             "description": "WHAT decided it: `table_caption` / `table_header` / `table_footnote` -- something "
                            "printed in the table itself (give its `table_id`); `body_sentence_naming_table` -- a "
                            "sentence in the text that names the table by number (quote it); `methods_definition` "
                            "-- the Methods define the measure; `recomputation` -- your own arithmetic; `other`."},
    "table_id": _nullable(_s("The `table:<n>` the anchor is printed in, EXACTLY as the account writes it, for a "
                             "table anchor; null for anything else.")),
}, "required": ["kind", "table_id"], "additionalProperties": False}

COMPARE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "overall": _s(),
        "disagreements": {"type": "array", "items": {"type": "object", "properties": {
            "field_class": {"type": "string", "enum": ["studies", "groups", "phases", "variables", "levels",
                                                        "values", "statistic_kind", "comparisons", "claims",
                                                        "subjects", "other"]},
            "item": _s("What the two accounts disagree about, named so a reader can find it in both."),
            "reading_a": _s(), "reading_b": _s(),
            "paper_supports": {"type": "string", "enum": ["a", "b", "neither", "both_plausible", "undecidable"]},
            "evidence": _s("Why: the passage or cell that decides it and the reasoning, in your words."),
            "evidence_quote": _nullable(_s("A VERBATIM, contiguous span of the paper's text that decides it, long "
                                           "enough and specific enough to occur ONCE: it is located in the text "
                                           "automatically, and a span the paper did not print, or printed several "
                                           "times, carries no correction. Null when a table cell decides it.")),
            "evidence_anchor": _ANCHOR,
            "target_account": _nullable({"type": "string", "enum": ["a", "b"]}),
            "target_ids": {"type": "array", "items": _s(),
                           "description": "The ids (val:..., var:...) IN THE TARGET ACCOUNT whose field the "
                                          "paper shows to be wrong; empty when the disagreement is not about "
                                          "addressable records."},
            "correction": _nullable({"type": "object", "properties": {
                "field": {"type": "string", "enum": list(CORRECTABLE_FIELDS)},
                "to": _s("The value the paper supports: a statistic kind from the closed vocabulary, or a "
                         "declared id (var:..., lvl:..., grp:..., study:..., phase:...)."),
            }, "required": ["field", "to"], "additionalProperties": False}),
        }, "required": ["field_class", "item", "reading_a", "reading_b", "paper_supports", "evidence",
                        "evidence_quote", "evidence_anchor", "target_account", "target_ids", "correction"],
            "additionalProperties": False}},
    },
    "required": ["overall", "disagreements"],
    "additionalProperties": False,
}


def sample_values(account: dict, k: int = SAMPLE_SIZE, seed: int = 20260906) -> list[dict]:
    """A fixed, reproducible sample of the account's values with what a reader
    needs to check each: id, printed value, statistic, variable, location, quote
    or cell. Seeded, so two reviews of one account check the same values."""
    vals = [v for v in account.get("values", []) if v.get("printed")]
    vals.sort(key=lambda v: str(v.get("id")))
    rng = random.Random(seed)
    picked = vals if len(vals) <= k else rng.sample(vals, k)
    out = []
    for v in picked:
        loc = v.get("location") or {}
        out.append({"value_id": v.get("id"), "printed": v.get("printed"), "statistic": v.get("statistic"),
                    "variable": v.get("variable_as_read") or v.get("variable_id"),
                    "coordinate": v.get("coordinate"), "where": loc.get("kind"),
                    "table_id": loc.get("table_id"), "row_label": loc.get("row_label"),
                    "col_label": loc.get("col_label"), "quote_or_cell": v.get("quote")})
    return out


def _fence(label: str, body: str) -> str:
    return f"\n\n===== {label} =====\n{body}\n===== END {label} =====\n"


def _clip(text: str, n: int, what: str) -> str:
    text = text or ""
    if len(text) <= n:
        return text
    return text[:n] + f"\n[... {what} clipped at {n:,} characters of {len(text):,}]"


def without_headline(account_md: str) -> str:
    """The rendered account with section 0, the computed coverage headline,
    removed -- everything from its heading up to the next one.

    IT IS THE ONE SECTION A SECOND READER HAS NO USE FOR. Section 0 is a pure
    function of the account and the document (`coverage.headline`); the reader is
    told in the same breath NOT to compute coverage or certify completeness, so
    serving it spends the budget that the evidence sections need on the one block
    the reader may not act on. The rest of the account is what a note or a spot
    check has to be located in.
    """
    md = account_md or ""
    i = md.find("\n## 0. Headline coverage")
    if i < 0:
        return md
    j = md.find("\n## ", i + 4)
    return md if j < 0 else md[:i + 1] + md[j + 1:]


def _ix(x: Any, n: int = 40) -> str:
    """One cell of the index: whitespace collapsed and clipped, so that one
    record is one line and a label carrying a newline cannot split it in two.
    `--` for nothing, rather than an empty column the reader would miscount."""
    s = re.sub(r"\s+", " ", str(x)).strip() if x is not None and x != "" else ""
    if not s:
        return "--"
    return s if len(s) <= n else s[:n] + "..."


def _pos(x: Any) -> int:
    """A row or column number for sorting; -1 when the record has none."""
    try:
        return int(str(x).strip())
    except (TypeError, ValueError):
        return -1


def id_index(account: dict, limit: int = ID_INDEX_CHARS) -> str:
    """The account's addressable records, one per line, with their FULL ids --
    what an adjudicator copies `target_ids` from.

    WHY IT EXISTS, measured. On the first real application (ajcp.70049, 12
    disagreements) NOTHING was applied to either account. Two kind corrections
    carried empty `target_ids`; the ids the adjudicator did cite (`t4-comm`,
    `t2-idm`) are the SHORTENED ids the rendered account prints -- `render._short`
    keeps only the last `:`-segment -- and not the account's own ids
    (`cmp:t4-comm`, `val:t2:r3:c1:0:coefficient`). The rendered markdown is a
    document for a human reader and the wrong place to copy a machine id from.

    An id that is not here does not exist, and `apply_adjudication` skips a
    target it cannot find -- so an incomplete index costs a correction and cannot
    cost an accusation. That asymmetry is why the clipping note tells the reader
    to leave `target_ids` empty rather than reconstruct an id: a reconstructed id
    that happened to match another record would move the correction onto a record
    no evidence was ever read against.
    """
    studies = account.get("studies") or []
    # The small sections are built first and kept WHOLE: their ids are the
    # vocabulary a `correction.to` is drawn from, so losing one silently removes
    # the only legal value of a correction, while losing a value line only
    # removes one target.
    rest: list[str] = []

    def _section(header: str, lines: list[str]) -> None:
        rest.append("")
        rest.append(header if lines else header + " -- none")
        rest.extend(lines)

    _section("COMPARISONS (id | quote)",
             [f"{c.get('id')} | {_ix(c.get('quote'), 60)}" for c in account.get("comparisons") or []])
    _section("STUDIES (id | label | design_type)",
             [f"{s.get('id')} | {_ix(s.get('label'))} | {_ix(s.get('design_type'), 32)}" for s in studies])
    _section("GROUPS (study_id/group_id | label)",
             [f"{s.get('id')}/{g.get('id')} | {_ix(g.get('label'))}"
              for s in studies for g in (s.get("groups") or [])])
    _section("VARIABLES (id | name | kind | bounds.source)",
             [f"{v.get('id')} | {_ix(v.get('name'))} | {_ix(v.get('kind'), 32)} | "
              f"{_ix((v.get('bounds') or {}).get('source'), 24)}" for v in account.get("variables") or []])
    _section("PHASES (study_id/phase_id | label)",
             [f"{s.get('id')}/{p.get('id')} | {_ix(p.get('label'))}"
              for s in studies for p in (s.get("phases") or [])]
             + [f"{p.get('id')} | {_ix(p.get('label'))}" for p in account.get("phases") or []])

    # Values, sorted by table then row then col so a whole column reads as a
    # contiguous block -- a kind correction is per COLUMN, and the ids it must
    # list are then adjacent rather than scattered. A prose value has no table
    # and sorts after every table.
    vals = sorted(account.get("values") or [],
                  key=lambda v: (str((v.get("location") or {}).get("table_id") or "\uffff"),
                                 _pos((v.get("location") or {}).get("row")),
                                 _pos((v.get("location") or {}).get("col")), str(v.get("id"))))
    value_lines = []
    for v in vals:
        loc = v.get("location") or {}
        value_lines.append(
            f"{v.get('id')} | {_ix(loc.get('table_id') or 'prose', 24)} | {_ix(loc.get('row_label'))} | "
            f"{_ix(loc.get('col_label'))} | {_ix(v.get('printed'), 24)} | {_ix(v.get('statistic'), 24)} | "
            f"{_ix(v.get('variable_id'), 32)}")

    head = "VALUES (id | table | row_label | col_label | printed | statistic | variable_id)"
    rest_text = "\n".join(rest)
    budget = limit - len(rest_text) - len(head) - 1
    kept, used = [], 0
    for ln in value_lines:
        if used + len(ln) + 1 > budget:
            break
        kept.append(ln)
        used += len(ln) + 1
    # Clipped at a LINE boundary, never mid-line: half an id reads exactly like a
    # whole one and would be copied as one.
    if len(kept) < len(value_lines):
        kept.append(f"[... {len(value_lines) - len(kept):,} more value ids not listed: the index is clipped "
                    f"at {limit:,} characters. An id that is not listed cannot be corrected -- leave "
                    f"`target_ids` empty rather than reconstruct one.]")
    return "\n".join([head] + kept) + "\n" + rest_text


def table_renders(account: dict, sample: list[dict]) -> list[dict]:
    """The rendered images of the tables the sample draws on, so a table value
    is checked against the PRINTED table, not against the prose. MEASURED on
    the first review (37679): all 16 'not found' spot checks were table cells,
    and the reviewer had been given the paper's text, where an XML table is a
    caption placeholder -- it could not see them by construction."""
    wanted = {s.get("table_id") for s in sample if s.get("table_id")}
    out: list[dict] = []
    for t in (account.get("document") or {}).get("tables") or []:
        if t["id"] in wanted:
            png = ((t.get("reconstruction") or {}).get("png"))
            out.append({"table_id": t["id"], "label": t.get("label"), "caption": t.get("caption"),
                        "image": png, "note": None if png else "no render on disk; use the cells below",
                        "cells": [{"row_label": c.get("row_label"), "col_label": c.get("col_label"),
                                   "raw": c.get("raw")} for c in (t.get("walker_cells") or t.get("cells") or [])][:400]})
    return out


def review_prompt(account_md: str, paper_text: str, sample: list[dict],
                  renders: list[dict] | None = None) -> str:
    task = """\
You are the SECOND READER of a structured account of a scientific paper. The account was built
by an extraction pipeline; you have the paper. Your job is to say what in the account looks wrong,
unsupported, or inconsistent with the paper, and to check a sample of its values against the
paper one by one. You are a reader, not an auditor of completeness: do NOT compute coverage,
totals, or shares, and do NOT certify that anything is complete -- those are measured elsewhere
without a model, and your saying so would add nothing but false comfort.

What to look for (each a `note`, located, with the paper's evidence and a severity):
- a statistic's KIND that the paper defines otherwise (a `(y)` called SD where the Methods say SE;
  `other` where the Methods define the measure);
- a variable, level, group or study the account names that the paper does not, or names differently;
- a value placed at a coordinate the paper does not support (wrong arm, wrong wave, wrong table);
- a comparison or claim attributed to the paper that it does not make, or hedged differently;
- internal inconsistencies of the account (two readings of the same printed thing).
Then, for EACH sampled value below, find it in the paper and give a verdict: `supported` (the
printed value appears where the account says, meaning what the account says), `not_found`,
`contradicted` (the paper prints something else there), or `ambiguous` -- with the passage or
cell you compared it with, quoted. A value from a TABLE is checked against the printed table:
open its rendered image with the Read tool (paths under TABLE RENDERS) and read the cell; the
extractor's cells are given beside it as a second witness. The paper text below carries prose
only -- a table appears there as a caption placeholder, which is not evidence of absence.
Finally list `unstable_readings`: places where the account's reading of a kind, variable, level or
group is not the one the paper supports, with what the paper supports and your confidence.
Be specific and brief. An empty list is a fine answer where you find nothing.
"""
    return (task
            + _fence("SAMPLED VALUES TO CHECK", json.dumps(sample, indent=1, ensure_ascii=False))
            + _fence("TABLE RENDERS (read the image for a table value)",
                     json.dumps(renders or [], indent=1, ensure_ascii=False))
            + _fence("THE ACCOUNT (rendered; section 0, the computed coverage headline, is not "
                     "served -- it is derived, and you are not asked to audit it)",
                     _clip(without_headline(account_md), ACCOUNT_CHARS, "account"))
            + _fence("THE PAPER (prose; tables are placeholders here)", _clip(paper_text, PAPER_CHARS, "paper")))


#: The instruction that turns a decision into an APPLICABLE correction, added only
#: when the id indexes are actually served -- an instruction to copy from a fence
#: that is not there would be a false instruction.
#:
#: MEASURED (ajcp.70049, 12 disagreements, 0 applied on either account): the two
#: kind corrections carried EMPTY `target_ids`; the ids that were cited came from
#: the rendered account, where `render._short` prints `t4-comm` for `cmp:t4-comm`;
#: and the decided items on the design label and on bounds gave target ids with no
#: `correction` at all. One paragraph below per failure.
_ID_INDEX_TASK = f"""
COPY EVERY `target_ids` ENTRY FROM THE ID INDEX OF THE TARGET ACCOUNT, character for character.
The ID INDEX A and ID INDEX B fences list every addressable record of each account with its FULL
id. The rendered accounts above print SHORTENED ids -- `t4-comm` where the account's id is
`cmp:t4-comm`, `t2-idm` where it is `val:t2:r3:c1:0:coefficient` -- and a shortened or
reconstructed id matches no record, so the correction is silently dropped. An id you cannot find
in the index does not exist: leave `target_ids` empty and list the disagreement without a
correction, rather than composing an id that might land on a record no evidence was read against.

A CORRECTION OF A STATISTIC'S KIND FOR A TABLE COLUMN MUST LIST EVERY VALUE ID IN THAT COLUMN
that carries the wrong kind -- every matching line of the index, not the first one and not an
example. The header or footnote that decides a column governs the whole column, and a cell left
out of `target_ids` keeps the reading the paper does not support.

A DECIDED DISAGREEMENT ABOUT A DESIGN LABEL, A BOUND'S SOURCE, A VARIABLE ID, A LEVEL ID OR A
GROUP ID MUST BE GIVEN IN MACHINE FORM: `correction.field` from the allowed set
({', '.join(CORRECTABLE_FIELDS)}) and `correction.to` a member of the closed vocabulary or an id
copied from that account's index. A decision without a machine form cannot be applied and is
listed only -- which is where a study's design label lands today, since the allowed set has no
field for it: name the study and both readings and leave the correction null.
"""


def compare_prompt(account_a_md: str, account_b_md: str, paper_text: str,
                   account_a: dict | None = None, account_b: dict | None = None) -> str:
    task = """\
Two independent structured accounts of the SAME paper were produced by the same pipeline on two
runs. Where they disagree -- about the studies and their design, the groups and phases, the
variables and their levels, the kind of a statistic (SD vs SE, coefficient vs mean), a value's
placement, the comparisons or the claims -- say which reading the paper supports, with the passage
or cell that decides it. Where both are defensible say so; where the paper cannot decide say so.
Do not tally, score or summarise coverage; list the disagreements a human would want decided.

FIRST ASK WHETHER THE PAPER SUPPORTS EITHER READING. The two accounts came from the same pipeline
and the same model, so where they agree they can be wrong together: agreement between two runs is
RELIABILITY, not accuracy, and it is not evidence of anything. Answer `neither` when the paper
supports a third reading, and `undecidable` when the paper does not settle it -- use both freely
and at no cost. A correction that is merely plausible puts a wrong premise into the account, and a
wrong premise is how a checking tool comes to accuse an honest paper.

For each disagreement the paper DOES decide, also give the machine form: which account is wrong
(`target_account`), the ids of the records in it that carry the wrong reading (`target_ids`, copied
exactly from that account), and the `correction` -- the field and the value the paper supports, a kind
from the closed vocabulary or an id declared in that account. Give `evidence_quote` as a verbatim span
of the paper's text when a passage decides it; null when a table cell decides it. A correction you
cannot express this way is still worth listing without one.

GIVE THE `evidence_anchor` FOR EVERY DISAGREEMENT, and for every correction it is what decides
whether the correction may be applied at all: name WHAT decided it -- the table's own caption,
column header or footnote (with that table's `table_id`), a body sentence that names the table by
number (quote the sentence), a definition in the Methods, your own arithmetic (`recomputation`), or
`other`. Evidence must reach the record it corrects: a sentence about Table 3 does not decide a cell
of Table 2, and only what is printed in a table may supply a group, phase or variable a cell did not
already have. A recomputation is recorded and never applied -- your arithmetic is a claim, not a
check.
"""
    indexed = account_a is not None or account_b is not None
    out = ((task + _ID_INDEX_TASK if indexed else task)
           # Section 0 is dropped from both, for the reason `without_headline`
           # gives: the adjudicator is told not to tally or score coverage, so
           # the one block it may not act on is the one that should not be
           # competing with the evidence sections for the budget.
           + _fence("ACCOUNT A", _clip(without_headline(account_a_md), ACCOUNT_CHARS // 2, "account A"))
           + _fence("ACCOUNT B", _clip(without_headline(account_b_md), ACCOUNT_CHARS // 2, "account B"))
           + _fence("THE PAPER", _clip(paper_text, PAPER_CHARS, "paper")))
    if indexed:
        # LAST, and after the rendered accounts on purpose: this is the fence the
        # model copies from, and the rendered account above it is the one whose
        # shortened ids it must not copy.
        out += (_fence("ID INDEX A (copy target_ids for account A from here)", id_index(account_a or {}))
                + _fence("ID INDEX B (copy target_ids for account B from here)", id_index(account_b or {})))
    return out


def run_review(account: dict, account_md: str, paper_text: str, out_dir, *, model: str) -> dict:
    """The review as a saved pass (`review.json` beside the account), marked as
    model readings. Returns the review record to attach as `account['review']`."""
    sample = sample_values(account)
    renders = table_renders(account, sample)
    res = _passes.run_pass("review", review_prompt(account_md, paper_text, sample, renders), out_dir,
                           model=model, schema=REVIEW_SCHEMA, tools="Read", timeout_s=1800, retries=1,
                           extra_meta={"review_version": REVIEW_VERSION, "n_sampled": len(sample)})
    data = dict(res["data"])
    by_verdict: dict[str, int] = {}
    for sc in data.get("spot_checks") or []:
        by_verdict[sc.get("verdict")] = by_verdict.get(sc.get("verdict"), 0) + 1
    return {"version": REVIEW_VERSION, "model": model, "cost_usd": res["meta"].get("cost_usd"),
            "elapsed_s": res["meta"].get("elapsed_s"), "schema_problems": res["problems"],
            "n_sampled": len(sample), "sample": sample, "spot_checks_by_verdict": by_verdict,
            "basis": "model_reading -- every note is a claim to verify, not a computed fact",
            **data}


def run_compare(account_a_md: str, account_b_md: str, paper_text: str, out_dir, *, model: str,
                account_a: dict | None = None, account_b: dict | None = None) -> dict:
    res = _passes.run_pass("review_compare",
                           compare_prompt(account_a_md, account_b_md, paper_text, account_a, account_b), out_dir,
                           model=model, schema=COMPARE_SCHEMA, tools="", timeout_s=1800, retries=1,
                           extra_meta={"review_version": REVIEW_VERSION})
    return {"version": REVIEW_VERSION, "model": model, "cost_usd": res["meta"].get("cost_usd"),
            "basis": "model_reading -- each adjudication is a claim to verify", **res["data"]}


# ---------------------------------------------------------------------------
# consuming an adjudication
# ---------------------------------------------------------------------------

def _get_path(rec: dict, field: str):
    cur: Any = rec
    for part in field.split("."):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _set_path(rec: dict, field: str, value) -> None:
    parts = field.split(".")
    cur = rec
    for part in parts[:-1]:
        cur = cur.setdefault(part, {})
    cur[parts[-1]] = value


def _declared(account: dict) -> dict[str, set]:
    from . import schema as _schema
    studies = account.get("studies") or []
    return {
        "statistic": set(_schema.STATISTICS),
        "kind": set(_schema.VARIABLE_KINDS),
        "bounds.source": set(_schema.BOUND_SOURCES),
        "variable_id": {v.get("id") for v in account.get("variables") or []},
        "level_id": {l.get("id") for v in account.get("variables") or [] for l in (v.get("levels") or [])},
        "group_id": {g.get("id") for s in studies for g in (s.get("groups") or [])},
        "reference_group_id": {g.get("id") for s in studies for g in (s.get("groups") or [])},
        "coordinate.study_id": {s.get("id") for s in studies},
        "coordinate.group_id": {g.get("id") for s in studies for g in (s.get("groups") or [])},
        "coordinate.phase_id": ({p.get("id") for s in studies for p in (s.get("phases") or [])}
                                | {p.get("id") for p in account.get("phases") or []}),
    }


def _table_of(rec: dict) -> str | None:
    """The id of the table a record was PRINTED IN, or None when it was not
    printed in one. A record with no table has no scope test we can run."""
    loc = rec.get("location") or {}
    return loc.get("table_id") if loc.get("kind") == "table_cell" else None


def _table_label(account: dict, table_id: str | None) -> str:
    for t in (account.get("document") or {}).get("tables") or []:
        if t.get("id") == table_id:
            return str(t.get("label") or "")
    return ""


_DIGITS = re.compile(r"\d+")


def _quote_names_table(quote: str | None, label: str, table_id: str | None) -> bool:
    """Does the quoted sentence name THIS table? The word `table` plus the
    table's own number, as a whole token.

    NOT an exact match on the label: a paper cites several tables in one
    sentence and writes the word once -- `Results in Tables 2, 3, 4 are shown as
    coefficients` names Table 2 while containing neither the string `Table 2`
    nor a singular `Table`. Requiring the exact label would refuse the commonest
    honest form of the evidence. Requiring the number as a whole token is what
    stops `Table 12` from answering for `table:2`.
    """
    from .. import quotes as _quotes
    m = _DIGITS.search(label or "") or _DIGITS.search(table_id or "")
    if not m or not quote:
        return False
    q = _quotes.normalise(quote)
    return "table" in q and re.search(rf"(?<!\d){re.escape(m.group())}(?!\d)", q) is not None


def _anchor_covers(rec: dict, anchor: dict, quote: str | None, account: dict, *, is_variable: bool) -> bool:
    """Does the evidence the adjudicator names REACH the record it corrects?

    A table cell is decided by that table's own caption, header or footnote, or
    by a body sentence that names the table -- not by a sentence about another
    table, and not by an unlocated `other`. A variable is decided by the Methods
    definition of the measure, or by a body sentence.

    A value the account read from PROSE is refused here, deliberately: the scope
    test we can run for a cell (does the anchor name the cell's own table?) has
    no counterpart for a sentence, so there is nothing to check the reach of, and
    the failure mode of guessing is a premise supplied to the wrong record. That
    costs corrections we could in principle make; it cannot cost an accusation.
    """
    kind = anchor.get("kind")
    if is_variable:
        return kind in ("methods_definition", "body_sentence_naming_table")
    tid = _table_of(rec)
    if tid is None:
        return False
    if kind in STRUCTURAL_ANCHORS:
        return anchor.get("table_id") == tid
    if kind == "body_sentence_naming_table":
        return _quote_names_table(quote, _table_label(account, tid), tid)
    return False


def _occurrences(quote: str, hay_norm: str, hay_folded: str) -> int:
    """How many times the quote occurs in the paper, in the SAME two drawings of
    the text that `quotes.classify` searches: the normalised text, and -- only
    when the normalised text does not hold it -- the folded rendering.

    Counting in one drawing only would report zero for a quote `classify` calls
    `verbatim` on the folded pass (a hyphenated line break, a ligature the
    extractor split), and the skip would then say `not unique` about a quote
    that is in the paper exactly once. The two passes ask one question of two
    drawings of the same bytes; so does this count.
    """
    from .. import quotes as _quotes
    nq = _quotes.normalise(quote)
    n = hay_norm.count(nq) if nq else 0
    if n:
        return n
    fq = _quotes.fold_rendering(_quotes._unwrap(nq))
    return hay_folded.count(fq) if fq else 0


def _as_int(x: Any) -> int | None:
    """`8` or `8.0` or `1,043` as an int; None for anything else, including a
    range (`6-9`) -- a range is not a per-group n and nothing may treat it as one."""
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x
    if isinstance(x, float):
        return int(x) if float(x).is_integer() else None
    s = str(x or "").strip().replace(",", "")
    try:
        f = float(s)
    except ValueError:
        return None
    return int(f) if f.is_integer() else None


def apply_adjudication(account: dict, adjudication: dict, paper_text: str, *, side: str) -> dict:
    """Apply the adjudication's corrections to THIS account (`side` is "a" or
    "b": which of the two compared accounts this is), under the gates below,
    and return what was applied and what was skipped, with reasons.

    WHY THE GATES ARE THIS HEAVY. The adjudicator is the same model that wrote
    both accounts, reading them against the paper. Everything it says is a model
    reading; what makes a reading safe to APPLY is not its confidence but the
    kind of evidence behind it and whether that evidence reaches the record. A
    correction that supplies a group id supplies a denominator, and a wrong
    denominator is the documented route to accusing an honest paper -- so the
    asymmetry is deliberate throughout: a correction that REMOVES a check needs
    only located, scoped evidence; a correction that CREATES one needs evidence
    printed in the table or stated in the Methods.

    THE GATES, each a named skip:
    - the paper must decide it (`paper_supports` names one side) and the
      correction must target THIS account;
    - a correction must be given in machine form and its field must be one a
      model may change (CORRECTABLE_FIELDS: a kind or an id -- never a printed
      number, a quote, a count);
    - `to` must exist: a member of the closed vocabulary or an id this account
      declares -- an adjudication cannot coin a variable any more than a reading can;
    - an `evidence_anchor` of a known kind must be given, and `recomputation` is
      refused: the model's own arithmetic is a claim, not a check;
    - the deciding `evidence_quote`, when given, must be long enough to prove
      anything (`quotes._MIN_FRAGMENT`), located in the paper, and UNIQUE in it --
      a quote that occurs twice does not say which occurrence decided anything;
    - the anchor must COVER the target (`_anchor_covers`);
    - one correction per field per record: an already-adjudicated field is
      appended to, never overwritten;
    - SUPPLY vs NARROW (invariant 2, CLAUDE.md 8d): filling a premise field that
      was None needs a structural anchor from the record's own table; a kind that
      makes a record checkable -- a value's `statistic` or a variable's `kind` --
      needs a structural or Methods anchor; `bounds.source` may only move AWAY
      from `stated`;
    - a count moved into a group cannot exceed that group's printed n;
    - a kind correction may not overrule a TEXT-DERIVED kind on a header,
      caption or footnote anchor: the two are the paper disagreeing with itself,
      and the disagreement is RECORDED (`kind_conflict`, `statistic_disputed`)
      rather than resolved.

    EVERY CORRECTED RECORD KEEPS WHAT IT SAID: `adjudications` on the record lists
    field, from, to, both readings, the evidence and its anchor, and who
    adjudicated it. Nothing is deleted.

    THE THIRD PREMISE TIER. A corrected `statistic` sets the value's
    `statistic_basis` to `adjudicated`, which is neither `stated` (the paper says
    so, in a header, a footnote or the Methods) nor `inferred` (nothing says so).
    It means: a model read the paper and says so, under these gates. Downstream
    checks MAY run on an adjudicated kind and MUST ceiling their verdict at
    `suspicious` -- never `impossible` -- because an impossibility claim rests on
    the premise being the paper's, and here it is ours. That enforcement lives
    with the checks; this function only carries the tier honestly.
    """
    from .. import quotes as _quotes
    from .bind import _Hay
    hay = _Hay(paper_text or "")
    hay_norm = _quotes.normalise(paper_text or "")
    hay_folded = _quotes.fold_rendering(hay_norm)
    declared = _declared(account)
    by_id: dict[str, dict] = {}
    for v in account.get("values") or []:
        by_id[str(v.get("id"))] = v
    variable_ids: set[str] = set()
    for v in account.get("variables") or []:
        by_id[str(v.get("id"))] = v
        variable_ids.add(str(v.get("id")))
    groups = {g.get("id"): g for s in account.get("studies") or [] for g in (s.get("groups") or [])}
    adjudicator = {"model": adjudication.get("model"), "version": adjudication.get("version")}
    applied: list[dict] = []
    skipped: list[dict] = []
    for d in adjudication.get("disagreements") or []:
        item = d.get("item")
        supports = d.get("paper_supports")
        if supports not in ("a", "b"):
            skipped.append({"item": item, "why": f"paper does not decide it ({supports})"}); continue
        if d.get("target_account") != side:
            skipped.append({"item": item, "why": f"targets account {d.get('target_account')!r}, this is {side!r}"}); continue
        corr = d.get("correction")
        if not corr or corr.get("field") not in CORRECTABLE_FIELDS:
            skipped.append({"item": item, "why": "no machine-form correction in an allowed field"}); continue
        field, to = corr["field"], corr.get("to")
        if to not in declared.get(field, set()):
            skipped.append({"item": item, "why": f"`{to}` is not in the vocabulary or declared ids for {field}"}); continue
        anchor = d.get("evidence_anchor") or {}
        kind = anchor.get("kind")
        if kind not in ANCHOR_KINDS:
            skipped.append({"item": item, "why": f"no evidence anchor of a known kind ({kind!r})"}); continue
        # A RECOMPUTATION IS THE MODEL'S OWN ARITHMETIC. It is exactly the kind of
        # claim this codebase refuses to let a model make about itself: `computed`
        # was a false authority label on 12 of 34 live findings (CLAUDE.md 8e)
        # because nothing corroborated it. THIS IS WHERE A REGISTERED TOOL WOULD BE
        # WIRED IN -- statcheck reproducing the p from the test statistic, or
        # `check_count_percent` reproducing the percentage from its count and
        # denominator -- and the correction would then rest on the tool's result,
        # with the ledger entry to show for it, rather than on the model's sum.
        if kind == "recomputation":
            skipped.append({"item": item,
                            "why": "recomputation is model arithmetic; not evidence until a registered tool reproduces it"}); continue
        q = d.get("evidence_quote")
        ev_status = hay.verify(q).get("quote_verified") if q else "unlocated"
        if q:
            # LONG ENOUGH, LOCATED, AND UNIQUE. `_MIN_FRAGMENT` exists because a
            # short fragment is found in every paper and so proves nothing -- the
            # word "The" cleared a finding once (CLAUDE.md 8i). Uniqueness is the
            # other half: a sentence that occurs twice cannot say WHICH occurrence
            # decided the reading, and a table label appearing in both occurrences
            # is exactly how a correction lands on the wrong table. The uniqueness
            # test is on the contiguous span, so a `stitched` quote (verified, but
            # assembled from parts) cannot carry a correction; that is the intended
            # narrowing, not an accident.
            if len(q.strip()) < _quotes._MIN_FRAGMENT:
                skipped.append({"item": item,
                                "why": f"evidence quote not unique/too short (under {_quotes._MIN_FRAGMENT} characters)"}); continue
            if ev_status not in ("verbatim", "stitched"):
                skipped.append({"item": item, "why": f"evidence quote not located in the paper ({ev_status})"}); continue
            n_occ = _occurrences(q, hay_norm, hay_folded)
            if n_occ != 1:
                skipped.append({"item": item,
                                "why": f"evidence quote not unique/too short ({n_occ} occurrence(s) in the paper)"}); continue
        targets = [t for t in (d.get("target_ids") or []) if t in by_id]
        missing = [t for t in (d.get("target_ids") or []) if t not in by_id]
        if not targets:
            skipped.append({"item": item, "why": f"no target id exists in this account ({missing[:3]})"}); continue
        # ONE SENTENCE DECIDES ONE RECORD. A column header or a footnote governs
        # its whole column, so a structural anchor may correct many cells of ITS
        # OWN table (each still checked below). A sentence in the text, a Methods
        # definition or an `other` does not carry that scope with it -- applying
        # one to a list of records is the model asserting the scope, not reading it.
        if kind not in STRUCTURAL_ANCHORS and len(targets) > 1:
            for extra in targets[1:]:
                skipped.append({"item": item, "target": extra,
                                "why": "one record per non-structural evidence item"})
            targets = targets[:1]
        for tid in targets:
            rec = by_id[tid]
            is_var = tid in variable_ids
            before = _get_path(rec, field)
            if before == to:
                continue
            if not _anchor_covers(rec, anchor, q, account, is_variable=is_var):
                skipped.append({"item": item, "target": tid,
                                "why": f"evidence anchor does not cover the target ({kind})"}); continue
            if any(a.get("field") == field for a in rec.get("adjudications") or []):
                skipped.append({"item": item, "target": tid,
                                "why": "field already adjudicated; append-only"}); continue
            structural_own_table = (kind in STRUCTURAL_ANCHORS and anchor.get("table_id") == _table_of(rec))
            if field in PREMISE_FIELDS and before is None and not structural_own_table:
                skipped.append({"item": item, "target": tid, "why": "supplies a premise from prose"}); continue
            # BOUNDS MAY ONLY LOSE AUTHORITY. `stated` means the paper prints the
            # bound and the account quotes it; a model deciding that a bound is
            # stated when the account recorded otherwise would hand a plausibility
            # check a ceiling the paper never committed to (CLAUDE.md 8h, the
            # `check_sd_or_se` row: a bound assumed by us must disclose that it is
            # ours). Moving the other way only weakens what rests on it.
            if field == "bounds.source" and to == "stated":
                skipped.append({"item": item, "target": tid,
                                "why": "promotion of bounds to stated is refused"}); continue
            checkable = (GRIM_ELIGIBLE_VARIABLE_KINDS if field == "kind" else GRIM_ELIGIBLE_STATISTICS)
            if field in KIND_FIELDS and to in checkable and kind not in KIND_DEFINING_ANCHORS:
                skipped.append({"item": item, "target": tid,
                                "why": f"a checkable {field} needs a structural or Methods anchor"}); continue
            # G11 -- A HEADER MAY NOT OVERRULE A TEXT-DERIVED KIND. MEASURED
            # 2026-09-07 on ajcp.70049 Table 4, column `Coefficient | M (SD)`:
            # the parenthetical was typed `se` with `statistic_basis:
            # citing_text`, because the Results say "Results in Tables 2, 3, 4
            # are shown as coefficients" and an earlier adjudicator had
            # confirmed SE by recomputing the Wald ratio against the printed p.
            # A later adjudicator moved 21 values to `sd` on a `table_header`
            # anchor (header `M (SD)`, footnote "SD, standard deviation") --
            # while writing in its own evidence text that "substantively these
            # are almost certainly model standard errors". The gates allowed it
            # because a header is a structural anchor. The correction is
            # faithful to the PRINT and wrong for every downstream check that
            # reads the kind: an SE treated as an SD.
            #
            # So this is not a correction, it is the paper's header and the
            # paper's text disagreeing, and the account records the CONFLICT
            # instead of picking a winner. Only evidence of the same kind --
            # another sentence, or the Methods definition, located in the paper
            # -- can move a reading the text already decided. The reverse
            # direction is untouched: a text anchor correcting a header-derived
            # kind is still a correction, under the gates above.
            # A VARIABLE'S KIND IS TEXT-DERIVED BY CONSTRUCTION when pass 2
            # located the sentence that establishes the typing: that is what the
            # `quote` field on a declared variable IS. So the same gate applies,
            # and a table header cannot retype a variable the Methods define.
            text_derived = (rec.get("statistic_basis") in TEXT_DERIVED_BASES
                            or (is_var and field == "kind"
                                and rec.get("quote_verified", "verbatim") in ("verbatim", "stitched")
                                and bool(rec.get("quote"))))
            if field in KIND_FIELDS and text_derived and not (
                    kind in TEXT_ANCHORS and ev_status in ("verbatim", "stitched")):
                rec["kind_conflict"] = {"printed_kind": to, "text_kind": before,
                                        "header_evidence": d.get("evidence"), "item": item}
                rec["statistic_disputed"] = True
                skipped.append({"item": item, "target": tid,
                                "why": "header cannot overrule a text-derived kind; recorded as kind_conflict"})
                continue
            # THE ARITHMETIC THE MOVE ITSELF DISPROVES. Moving a count into an arm
            # asserts that those observations came from that arm; a count larger
            # than the arm's printed n says the assertion is wrong, and applying it
            # would leave a value whose own group refutes it -- the shape of a
            # manufactured `impossible`. Only a PRINTED n counts here; a range
            # (`n = 6-9`) is not a per-group n and parses to None. A study or
            # phase move names no group, so there is nothing to test it against
            # and it is not tested -- the check is only run where it can be run.
            if field in ("coordinate.group_id", "group_id") and rec.get("statistic") == "count":
                n = _as_int((groups.get(to) or {}).get("n_printed"))
                cnt = _as_int(rec.get("numeric"))
                if cnt is None:
                    cnt = _as_int(rec.get("printed"))
                if n is not None and cnt is not None and cnt > n:
                    skipped.append({"item": item, "target": tid,
                                    "why": f"count exceeds the target group's printed n ({cnt} > {n})"}); continue
            _set_path(rec, field, to)
            if field == "statistic" and not is_var:
                rec["statistic_basis"] = "adjudicated"
            rec.setdefault("adjudications", []).append({
                "field": field, "from": before, "to": to, "item": item,
                "reading_a": d.get("reading_a"), "reading_b": d.get("reading_b"),
                "paper_supports": supports, "presentation": side,
                "evidence": d.get("evidence"), "evidence_quote": q, "evidence_kind": ev_status,
                "evidence_anchor": anchor, "adjudicated_by": "model_review",
                "adjudicator": adjudicator})
            rec["adjudicated_by"] = "model_review"
            applied.append({"item": item, "target": tid, "field": field, "from": before, "to": to,
                            "evidence_kind": ev_status, "anchor_kind": kind,
                            "anchor_table_id": anchor.get("table_id")})
        if missing:
            skipped.append({"item": item, "why": f"{len(missing)} target id(s) not in this account: {missing[:3]}"})
    summary = {"side": side, "applied": applied, "skipped": skipped,
               "n_applied": len(applied), "n_skipped": len(skipped),
               "basis": "model_review -- every correction is a model's adjudication, recorded on the record with what it replaced"}
    account["adjudication"] = summary
    return summary
