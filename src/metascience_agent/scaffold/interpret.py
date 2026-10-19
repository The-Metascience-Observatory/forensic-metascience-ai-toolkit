"""Banner interpretation as a JOIN on declared structure (step 3, 2026-09-06).

THE QUESTION section 8d recorded as undecidable from inside the table: does a
banner name a VARIABLE-WITH-LEVELS (`State` over `Pennsylvania` / `Missouri`)
or a TOPIC-WITH-VARIABLES (`Covariates` over `Communities That Care` /
`Externally funded`)? The markup is identical. Greg, 2026-09-05: "a clear
delineation of what values a given variable can take will help understand
these nested rows as breakdowns within a variable rather than new variables"
-- with declared levels it becomes a lookup, not a judgement.

`values.binding_candidates` is the ONE matcher for label -> variable and
refuses where more than one variable fits; it is reused here, not copied. What
this module adds is the second half of the lookup: a stub under a banner that
names a variable is checked against THAT variable's declared levels, by label
or by coded value. Exactly one level -> bound as a level. No level -> the
banner may be a topic after all, so the stub is tried as a variable in its own
right. Anything else is REFUSED with the candidates listed, which is the
property that matters: `2 or 3` under `Level of technical assistance received`
merges two declared levels, and a human sees that in seconds; a rule that
picked one would have chosen a denominator.

THE CONSUMER, so this is not zero bits: pass 3's `row_map` is the MODEL's
reading of the same row. Where both bind a variable, agreement is recorded per
row; disagreement is the step-3 measurement, not a verdict.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from .. import values as _values

_PARENS = re.compile(r"\([^)]*\)")


def _clean(s: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(s or "")).split())


def strip_parens(s: Any) -> str:
    """`Missouri (n, %)` -> `Missouri`: the statistic form is not the label."""
    return _clean(_PARENS.sub(" ", _clean(s)))


def _norm(s: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _clean(s).lower())


def _words(s: Any) -> list[str]:
    return re.findall(r"[a-z0-9]+", _clean(s).lower())


def _phrase_in(needle: list[str], hay: list[str]) -> bool:
    n = len(needle)
    return n > 0 and any(hay[i:i + n] == needle for i in range(len(hay) - n + 1))


#: The separator the walker writes when it folds a row-section banner into the
#: labels beneath it (`Covariates | Externally funded`).
BANNER = "|"

#: A row that is a regression INTERCEPT and can never be a study variable. Whole
#: labels only, never a substring: `Constant` is the intercept and `Constant
#: comparison group` is not. Measured on ajcp.70049: 27 of the 41 entries with no
#: variable id at all are this one row, filed as a binding failure when it is the
#: correct answer -- there is no variable for the model's intercept to be.
INTERCEPT_LABELS = frozenset({"constant", "intercept", "cons", "modelintercept"})


def label_forms(label: Any) -> set[str]:
    """Every normalised form under which one printed row label may be named.

    The label itself; the segment after the last banner separator, because the
    walker folds a row section into every label beneath it (`Covariates |
    Externally funded`); and each of those with its statistic-form parenthetical
    removed, because `(mean, SD)` is the form of the number and not the name of
    the thing. Nothing else -- no stemming, no prefix matching. The diagnosis
    measured what stemming buys: 29 of 78 resolved and 30 more turned into five-
    and eleven-way ambiguity.
    """
    raw = _clean(label)
    if not raw:
        return set()
    parts = {raw, raw.split(BANNER)[-1]}
    return {n for p in parts for n in (_norm(p), _norm(strip_parens(p))) if n}


def row_label_vocabulary(tables: list[dict]) -> set[str]:
    """Every form of every row label the WALKER read, over all the paper's tables.

    The walker's cells are what the extractor lifted off the markup before any
    model saw the table, so this set is the paper's own printed vocabulary. A
    verified reconstruction REPLACES `cells`, which is why `walker_cells` is
    preferred here: the labels on a read table are the reading's.
    """
    out: set[str] = set()
    for t in tables or []:
        for c in (t.get("walker_cells") or t.get("cells") or []):
            out |= label_forms(c.get("row_label"))
    return out


def verified_aliases(variables: list[dict],
                     printed: set[str]) -> tuple[dict[str, str], list[dict]]:
    """`({normalised alias: variable_id}, refusals)` over every `printed_as`.

    THE MODEL SUPPLIES THE ALIAS AND THE CODE CHECKS IT, which is the
    `parallel.py:910` pattern -- there, the model's own `provenance_verdict` is
    popped and re-derived rather than believed. Here the claim is "the paper
    prints this variable under this label", and the walker's own row labels
    settle it. Three refusals, each named:

      * an alias the paper does not print as a row label. A hallucinated alias
        would otherwise corroborate a wrong id, which is the whole hazard;
      * an alias two variables claim. It binds neither -- an ambiguous join binds
        nothing;
      * an alias that is another declared variable's own NAME. Aliasing a
        variable to a second variable's name is a rename, not a printed label,
        and it would silently move every value of one onto the other.
    """
    names = {n: v.get("id") for v in variables if v.get("id")
             for n in label_forms(v.get("name"))}
    claimed: dict[str, set[str]] = {}
    for v in variables:
        vid = v.get("id")
        if not vid:
            continue
        for alias in v.get("printed_as") or []:
            for form in label_forms(alias):
                claimed.setdefault(form, set()).add(vid)
    out: dict[str, str] = {}
    refused: list[dict] = []
    for form, vids in sorted(claimed.items()):
        if form not in printed:
            refused.append({"alias": form, "variable_ids": sorted(vids),
                            "why": "no table row label the extractor read has this text"})
        elif len(vids) > 1:
            refused.append({"alias": form, "variable_ids": sorted(vids),
                            "why": "two declared variables claim this label; it binds neither"})
        elif names.get(form) and names[form] not in vids:
            refused.append({"alias": form, "variable_ids": sorted(vids),
                            "why": f"this is `{names[form]}`'s own name, not an alias"})
        else:
            out[form] = next(iter(vids))
    return out, refused


def is_intercept(label: Any) -> bool:
    """A regression intercept row. Whole label, after the banner and the form."""
    return bool(label_forms(label) & INTERCEPT_LABELS)


def _variable_for(label: str, variables: list[dict]) -> tuple[str | None, list[str]]:
    """The one declared variable a label names, by the repo's own rule; else the candidates."""
    rows = _values.binding_candidates([label], variables)
    if not rows:
        return None, []
    row = rows[0]
    cands = [str(c.get("variable_id")) for c in (row.get("candidates") or [])]
    if row.get("status") == "bound" and len(cands) == 1:
        return cands[0], cands
    return None, cands


def _levels_for(stub: str, variable: dict) -> list[dict]:
    """Declared levels of `variable` that `stub` names, by label or by coded value."""
    s = _norm(strip_parens(stub))
    if not s:
        return []
    # WHOLE WORDS, never characters. Character containment matched `None`
    # inside `one-on-one` and handed a stub two candidates it names in no
    # sense; a stub names a level when its words are the label's words, or a
    # contiguous run of them.
    sw = _words(strip_parens(stub))
    hits = []
    for lv in variable.get("levels") or []:
        lw = _words(strip_parens(lv.get("label")))
        val = lv.get("value")
        if sw and lw and (sw == lw or _phrase_in(sw, lw) or _phrase_in(lw, sw)):
            hits.append(lv)
        elif val is not None and s == _norm(str(val)):
            hits.append(lv)
    if hits:
        return hits
    # A MERGED CODED LEVEL (`2 or 3`, `0/1`, `1-2`): each numeric token against
    # the declared values, so the merge surfaces as AMBIGUOUS with both
    # candidates rather than as no match. Whole-label matching came first, so
    # a hyphenated label (`Alcohol-exposed`) is never split.
    toks = [t for t in re.split(r"\s*(?:\bor\b|\band\b|\bto\b|/|,|\u2013|-)\s*", strip_parens(stub)) if t]
    if len(toks) >= 2 and all(re.fullmatch(r"\d+(?:\.\d+)?", t) for t in toks):
        for lv in variable.get("levels") or []:
            val = lv.get("value")
            if val is not None and any(_norm(t) == _norm(str(val)) for t in toks):
                hits.append(lv)
    return hits


def bind_entries(tables: list[dict], variables: list[dict]) -> dict:
    """Every tidy entry's `variable` and `level` joined to pass 2's declared
    variables and levels. Annotates the entries in place (`variable_id`,
    `level_id`, `variable_candidates`, `binding`) and returns counts. Never a
    verdict: an entry the join cannot place stays placed by the model's own
    words, which the account prints beside it."""
    by_id = {v["id"]: v for v in variables if isinstance(v, dict) and v.get("id")}
    aliases, alias_refusals = verified_aliases(variables, row_label_vocabulary(tables))
    cache: dict[str, tuple[str | None, list[str]]] = {}
    from collections import Counter
    status: Counter = Counter()
    n = 0
    n_alias = 0
    for t in tables:
        for cell in t.get("cells") or []:
            for e in cell.get("entries") or []:
                n += 1
                name = strip_parens(e.get("variable") or "")
                if name not in cache:
                    cache[name] = _variable_for(name, variables)
                vid, cands = cache[name]
                # THE VERIFIED ALIAS, WHERE THE NAME JOIN FOUND NOTHING. Only
                # where it found nothing: an alias can fill a join, never
                # override one. Measured on ajcp.70049, all 78 entries the join
                # could not check reduce to five printed labels whose declared
                # names differ morphologically (`Externally funded` against
                # `External funding indicator`), and a looser string matcher
                # bought 29 of them at the price of turning 30 more into five-
                # and eleven-way ambiguity. An exact printed label costs
                # neither. When the model also asserted an id, this only makes
                # the cross-check possible -- it may as easily produce
                # `disagrees`, which is the safe direction.
                if vid is None:
                    hit = next((aliases[f] for f in label_forms(e.get("variable"))
                                if f in aliases), None) or \
                          next((aliases[f] for f in label_forms(cell.get("row_label"))
                                if f in aliases), None)
                    if hit:
                        vid, e["alias_matched"] = hit, True
                        n_alias += 1
                # THE MODEL'S ID, WHEN IT GAVE ONE THAT EXISTS, is the binding;
                # the name join is its cross-check and stands in when it gave
                # none. Agreement is counted, never adjudicated.
                model_vid = e.get("variable_id") if e.get("variable_id") in by_id else None
                e["join_variable_id"], e["variable_candidates"] = vid, cands
                if model_vid:
                    e["variable_id"], e["variable_id_source"] = model_vid, "model"
                    e["agrees_with_join"] = (vid == model_vid) if vid else None
                    # THE CORROBORATION OUTCOME, ON THE ENTRY. `unjoined` means
                    # the model asserted an id the name join could not check --
                    # measured 82 of 222 on ajcp, one of them wrong (`Coalitions
                    # n = 64` -> var:zero_reach_inclusion). A check whose premise
                    # is the variable's kind or bounds should read this first.
                    e["id_check"] = ("agrees" if e["agrees_with_join"] else
                                     ("disagrees" if e["agrees_with_join"] is False else "unjoined"))
                    status["model_id_" + e["id_check"]] += 1
                    vid = model_vid
                else:
                    e["variable_id"], e["variable_id_source"] = vid, ("join" if vid else None)
                    e["agrees_with_join"] = None
                    e["id_check"] = "join" if vid else None
                model_lid = e.get("level_id")
                e["level_id"] = None
                if vid and model_lid and any(l.get("id") == model_lid for l in (by_id.get(vid) or {}).get("levels") or []):
                    e["level_id"] = model_lid
                    e["binding"] = "variable_and_level"
                elif vid and e.get("level"):
                    lv = _levels_for(e["level"], by_id.get(vid) or {})
                    if len(lv) == 1:
                        e["level_id"] = lv[0].get("id")
                        e["binding"] = "variable_and_level"
                    elif len(lv) > 1:
                        e["binding"] = "ambiguous_level"
                        e["level_candidates"] = [l.get("id") for l in lv]
                    else:
                        e["binding"] = "variable_only_level_unmatched"
                elif vid:
                    e["binding"] = "variable"
                # A REGRESSION INTERCEPT IS NOT AN UNBOUND VARIABLE. There is no
                # variable for a model's constant term to be, so filing it under
                # the same word as a failed join says the account missed
                # something it did not. 27 of ajcp.70049's 41 unbound entries
                # are this one row. Only where nothing bound it: a declared
                # variable the paper happens to call `Constant` still wins.
                elif is_intercept(e.get("variable")) or is_intercept(cell.get("row_label")):
                    e["binding"] = "intercept"
                elif len(cands) > 1:
                    e["binding"] = "ambiguous_variable"
                else:
                    e["binding"] = "unbound"
                status[e["binding"]] += 1
    return {"entries": n, "by_binding": dict(status),
            "bound_to_a_variable": sum(1 for t in tables for c in (t.get("cells") or [])
                                       for e in (c.get("entries") or []) if e.get("variable_id")),
            # FORMS, not labels: one printed label yields the form with its
            # statistic parenthetical and the form without, and both are keys.
            "printed_as": {"alias_forms_verified": len(aliases),
                           "entries_joined_by_a_verified_alias": n_alias,
                           "refused": alias_refusals,
                           "note": ("A declared variable's `printed_as` label counts only after "
                                    "the label is found among the row labels the table extractor "
                                    "read; the refusals name every one that was not.")}}
