"""Builders and annotators for the v2 finding record (docs/specs/findings_v2.md).

The ANNOTATOR layer of the v2 contract, standalone by design: nothing here is
wired into `agent.py` yet, so every function takes plain dicts. The
load-bearing rules per piece:

- `finding_id`/`anchor_key`/`assign_finding_ids` (spec section 5): the id is
  a CONTENT hash, never a list position, so a re-run mints the same id and a
  position-zip join is impossible.
- `tool_verdict_for` (section 1.4): deliberately NARROWER than
  `severity_reconcile._tool_severity` -- that function also trusts a
  model-transcribed `computed.severity`; this join reads ONLY the ledger.
- `derive_impossible` (section 1.5): "code can't mint impossible" made
  structural -- only a validated `evidence: absolute` registry call can.
- `clamp_provisionals` (section 7): every clamp routes through severity9, so
  no literal severity exists here either.
- `paper_metadata_projection` / `channels_block` (section 2): the two
  pipeline-written document blocks.
- `validate_producer_constraints` (section 9): problem records, never
  exceptions -- a validator that raises on the first bad row hides the rest.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from typing import Any

from . import severity9
from .discovery import CHANNEL_STATES
from .paper_metadata import needs_enrichment, upgrade_record
from .quotes import fold_rendering, normalise
from .core.prompts import NON_TOOL_TECHNIQUES
from .registry import BY_NAME, EVIDENCE_ABSOLUTE
from .severity_reconcile import (
    _candidate_tools,
    _comparable,
    _expand_rows,
    _scalars,
)
from .tools.severity import normalize_severity

#: Version of the finding-id hasher (spec section 5). Bump on ANY change to the
#: hash inputs or their canonicalization; existing ids are never recomputed in
#: place -- drift is handled by the DB alias table, not by rewriting ids.
FINDING_ID_HASHER_VERSION = "1"


# ---------------------------------------------------------------------------
# Canonicalization (spec section 5)
# ---------------------------------------------------------------------------

#: A string that IS a number and nothing else. Deliberately stricter than
#: `float()`, which also accepts "nan", "inf" and "infinity" -- words that
#: should hash as the words they are, not as IEEE sentinels.
_NUMERIC_STRING = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")

_INTEGER_STRING = re.compile(r"^[+-]?\d+$")


def _canon_text(s: str) -> str:
    """NFC-normalize and collapse whitespace -- the string canonicalization."""
    s = unicodedata.normalize("NFC", s)
    return re.sub(r"\s+", " ", s).strip()


def _canon_number(v: int | float) -> str:
    """Shortest round-trip repr, with integral floats as ints.

    `repr(float)` in Python 3 is already the shortest string that round-trips,
    so `3.530` and `3.53` meet here; `4.0` renders as `4` so an extractor that
    typed a count as a float and one that typed it as an int mint the same id.
    """
    if isinstance(v, int):
        return str(v)
    if math.isfinite(v) and v.is_integer():
        return str(int(v))
    return repr(v)


def _canon_scalar(v: Any) -> str | None:
    """One scalar's canonical rendering, or None for a non-scalar.

    None means EXCLUDED from the hash (arrays, objects, nulls). A numeric
    STRING canonicalizes through the number path -- `"3.530"`, `3.53` and
    `"3.53"` are one value seen three ways, and hashing the typography would
    mint three ids for one finding. Integer literals go through `int` rather
    than `float` so a long identifier ("12345678901234567890") is not
    silently rounded by IEEE doubles.
    """
    if v is None:
        return None
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _canon_number(v)
    if isinstance(v, str):
        t = _canon_text(v)
        if _NUMERIC_STRING.match(t):
            if _INTEGER_STRING.match(t):
                return str(int(t))
            try:
                return _canon_number(float(t))
            except (ValueError, OverflowError):  # pragma: no cover - regex-gated
                return t
        return t
    return None


def _fold_text(s: str) -> str:
    """`locators._fold`'s composition, minus its fallback (a hash key must not
    vary): stable across the PDF and XML renderings of one passage."""
    return fold_rendering(normalise(s or ""))


# ---------------------------------------------------------------------------
# anchor_key + finding_id (spec section 5)
# ---------------------------------------------------------------------------

#: Kind precedence for the anchor that feeds the id. Quote first: it is the
#: producer-mandatory anchor for text/numeric findings and the one stable
#: across surfaces.
_ANCHOR_PRECEDENCE = ("quote", "table_cell", "page_bbox")


def _key_for_anchor(kind: str, anchor: dict) -> str:
    """The hashable key for one producer anchor, or "" when it carries none."""
    if kind == "quote":
        return _fold_text(str(anchor.get("quote") or ""))
    if kind == "table_cell":
        container = str(anchor.get("sheet") or anchor.get("table") or "")
        cells = anchor.get("cells")
        cell_part = ",".join(sorted(str(c) for c in cells)) \
            if isinstance(cells, list) and cells else ""
        if not container and not cell_part:
            return ""
        return f"{_fold_text(container)}:{cell_part}"
    if kind == "page_bbox":
        file = anchor.get("file")
        page = anchor.get("page")
        if file is None or page is None:
            return ""
        # The PAGE, never the bbox: coordinates jitter across PyMuPDF
        # versions, and a hash input that moves with a library upgrade would
        # re-mint every image finding's id on that upgrade.
        return f"{file}:{page}"
    return ""


def anchor_key(finding: dict) -> str:
    """The anchor component of the content hash: the FIRST producer anchor of
    the highest-precedence kind present, else the folded `location` -- there
    is always SOME key, so a bare row never crashes the batch's ids."""
    if not isinstance(finding, dict):
        return ""
    first_of_kind: dict[str, dict] = {}
    anchors = finding.get("anchors")
    for anchor in anchors if isinstance(anchors, list) else []:
        if not isinstance(anchor, dict):
            continue
        kind = anchor.get("kind")
        if kind in _ANCHOR_PRECEDENCE and kind not in first_of_kind:
            first_of_kind[kind] = anchor
    for kind in _ANCHOR_PRECEDENCE:
        anchor = first_of_kind.get(kind)
        if anchor is None:
            continue
        key = _key_for_anchor(kind, anchor)
        if key:
            return key
    return _fold_text(str(finding.get("location") or ""))


def finding_id(paper_id: str, producer: str, technique: str,
               anchor_key: str, inputs: dict | None = None) -> str:
    """`f_` + 16 hex of the canonical content hash (spec section 5).

    Only the SCALAR entries of `inputs` feed the hash -- the model reproduces
    arrays/objects with varying formatting and they add no discriminating
    power (same reasoning as `severity_reconcile._scalars`). Fields join on
    \\x1f, records on \\x1e, so no printable payload collides by concatenation.
    """
    head = "\x1f".join(_canon_text(str(part or ""))
                       for part in (paper_id, producer, technique, anchor_key))
    pairs: list[tuple[str, str]] = []
    for k, v in (inputs.items() if isinstance(inputs, dict) else ()):
        rendered = _canon_scalar(v)
        if rendered is None:
            continue
        pairs.append((_canon_text(str(k)), rendered))
    records = [head] + [f"{k}\x1f{v}" for k, v in sorted(pairs)]
    payload = "\x1e".join(records)
    return "f_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def assign_finding_ids(rows: list[dict], paper_id: str) -> list[dict]:
    """Stamp `finding_id` + `finding_id_hasher` on every row, in place.

    Within-run collisions get `-2`/`-3`... suffixes: two identical hashes are
    a duplicate emission, and both rows must survive rather than one silently
    overwriting the other -- a suffixed id IS the signal that the producer
    said the same thing twice. Returns the same list for chaining; non-dict
    entries are skipped (the validator reports them separately).
    """
    seen: dict[str, int] = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        base = finding_id(
            paper_id,
            str(row.get("producer") or ""),
            str(row.get("technique") or ""),
            anchor_key(row),
            row.get("inputs") if isinstance(row.get("inputs"), dict) else None,
        )
        n = seen.get(base, 0) + 1
        seen[base] = n
        row["finding_id"] = base if n == 1 else f"{base}-{n}"
        row["finding_id_hasher"] = FINDING_ID_HASHER_VERSION
    return rows


_URLISH = re.compile(r"^(?:https?://|www\.)\S*$", re.I)


def title_is_a_bare_url(title: Any) -> bool:
    """A finding title that is nothing but a link.

    MEASURED 2026-08-22, `10.15585--mmwr.mm6923e2`: the science agent filed
    three `pass` rows titled `https://en.wikipedia.org/wiki/Sodium_hypochlorite`,
    `https://ibc.utah.edu/library/...` and `https://doh.wa.gov/...`, under the
    techniques `check_summation_batch`, `check_flow_arithmetic` and
    `not_computational` -- a Wikipedia link filed as a summation check. They
    stayed out of the report because they were passes, and sat in
    `findings.v2.json` and the value register as noise a human would have to
    read past.

    Narrow on purpose: only a title that is ENTIRELY a URL. A title that
    quotes a URL inside a sentence ("Named deposit URL nigdb.cineca.it does
    not resolve") is a real finding and must survive untouched.
    """
    text = " ".join(str(title or "").split())
    return bool(text) and bool(_URLISH.match(text))


#: The stored title bound (`findings.v2.schema.json`, `title.maxLength`).
TITLE_MAX = 90
#: What a PRODUCER may submit (`prompts.producer_findings_schema`, and the
#: adjudicator's verdict rewrites). MEASURED 2026-10-18 over the 116 archived
#: stages of the statcheck_pvalue_errors benchmark (Claude Sonnet + grok
#: 4.6): 40 stages had a StructuredOutput submission rejected, and 44 of the
#: 52 rejections were titles over 90 characters and nothing else (119 titles,
#: median 96, longest 126) -- a paid turn per resubmission, and the
#: resubmission loop is where the CLI's stream was cut in the 1.85.1
#: lost-findings bug. The prompts still ask for 90; the schema accepts up to
#: this and `fit_title` brings the stored row back to `TITLE_MAX`.
PRODUCER_TITLE_MAX = 160


def fit_title(title: Any) -> tuple[Any, str | None]:
    """`(title, None)` when it fits `TITLE_MAX`, else `(cut, full)`.

    The cut is at a WORD boundary, with an ellipsis: a hard cut splits the
    numbers a title is made of ("p = 0.0012" becomes "p = 0.00…", a value
    the paper never printed). `full` is the whitespace-collapsed original,
    for the caller to keep."""
    if not isinstance(title, str) or len(title) <= TITLE_MAX:
        return title, None
    full = " ".join(title.split())
    if len(full) <= TITLE_MAX:
        return full, None
    cut = full[: TITLE_MAX - 1]
    space = cut.rfind(" ")
    if space >= TITLE_MAX // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:([{-\u2013\u2014") + "\u2026", full


def fit_row_title(row: dict, who: str) -> bool:
    """Apply `fit_title` to a finding row in place. The full title is kept,
    appended to `notes` (the viewer renders it) -- never dropped. Returns
    whether the title was cut."""
    short, full = fit_title(row.get("title"))
    if full is None:
        if short is not row.get("title"):
            row["title"] = short
        return False
    row["title"] = short
    kept = (f"Full title ({who}'s, cut to {TITLE_MAX} characters by the "
            f"pipeline): {full}")
    row["notes"] = " ".join(x for x in (str(row.get("notes") or ""), kept) if x)
    return True


def clip(text: Any, limit: int) -> str:
    """Whitespace-collapse and hard-cap a string to a schema length bound
    (spec section 8: title <= 90, description <= 700). The producer must cut
    over-long prose itself: a row rejected by `--json-schema` for its length
    would silently drop a finding, which is worse than an ellipsis."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


# ---------------------------------------------------------------------------
# tool_verdict (spec section 1.4)
# ---------------------------------------------------------------------------

def _nested_n_pairs(obj: Any, depth: int = 0) -> set[tuple[str, int]]:
    """Every integral `n` inside a nested argument structure, as ("n", value).

    The scalar join deliberately ignores lists and dicts -- right for every
    tool whose identity lives in top-level scalars, and structurally blind
    for `check_flow_arithmetic`, whose ONLY discriminating argument is the
    nested `stages` list. Measured on the 2026-08-21 cerebrolysin run: the
    flow finding's `wanted` set was empty, every flow call matched, the two
    calls disagreed (consistent vs impossible), and the unanimity rule
    correctly refused -- so the science agent's flagship tool could never
    join its own verdict. Stage/arm headcounts ARE a flow check's identity,
    so they are the fallback join key. Only the literal key `n` counts:
    model-side summary fields (`excluded_total`) do not survive the round
    trip and must not be required to.
    """
    if depth > 6:
        return set()
    out: set[tuple[str, int]] = set()
    if isinstance(obj, dict):
        v = obj.get("n")
        if isinstance(v, bool):
            pass
        elif isinstance(v, int) or (isinstance(v, float) and v.is_integer()):
            out.add(("n", int(v)))
        for v in obj.values():
            if isinstance(v, (dict, list)):
                out |= _nested_n_pairs(v, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            out |= _nested_n_pairs(item, depth + 1)
    return out


def _ledger_verdicts(
    ledger: list[dict] | None,
) -> list[tuple[str, set, str, str | None, Any, dict, bool]]:
    """(tool, argument scalars, severity, quarantined_raw, raw call input,
    the ledger call, whether the row was expanded out of a batch) per
    validated call.

    `severity_reconcile.severities_from_ledger`'s walk plus one field that
    function discards: `severity_before_quarantine` -> `quarantined_raw`.
    A wrapper over the shared `_expand_rows`/`_scalars`, not a fork, so a fix
    to the join lands in both modules. The raw input rides along for the
    nested-`n` fallback join (batch-expanded rows carry the CALL-level
    input; their per-row scalars are what distinguishes them).
    """
    out: list[tuple[str, set, str, str | None, Any, dict, bool]] = []
    for call in ledger or []:
        if not isinstance(call, dict) or not call.get("validated"):
            continue
        text = call.get("result")
        if not isinstance(text, str) or not text.strip():
            continue
        try:
            parsed = json.loads(text)
        except (ValueError, TypeError):
            continue
        if not isinstance(parsed, dict):
            continue
        raw_q = parsed.get("severity_before_quarantine")
        quarantined_raw = normalize_severity(raw_q) \
            if isinstance(raw_q, str) and raw_q.strip() else None
        tool = str(call.get("tool_short") or "")
        expanded = _expand_rows(tool, parsed, call.get("input"))
        if expanded:
            out.extend((name, scalars, sev, quarantined_raw, call.get("input"),
                        call, True)
                       for name, scalars, sev in expanded)
            continue
        raw = parsed.get("severity")
        if not isinstance(raw, str) or not raw.strip():
            continue
        out.append((tool, _scalars(call.get("input")),
                    normalize_severity(raw), quarantined_raw,
                    call.get("input"), call, False))
    return out


#: The finding fields whose prose can tie an inputs-less row to a call.
_TIE_TEXT_FIELDS = ("quote", "location", "title", "description")
_NUMBER_IN_TEXT = re.compile(r"\d+(?:\.\d+)?|\.\d+")


def _tie_number(v: float) -> float:
    # Sign-blind: prose writes "−0.5" with a Unicode minus, and the tie only
    # asks whether the number was named.
    return round(abs(float(v)), 9)


def _text_numbers(finding: dict) -> set[float]:
    """Every number printed in the finding's quote, location, title or
    description."""
    out: set[float] = set()
    for field in _TIE_TEXT_FIELDS:
        text = finding.get(field)
        if isinstance(text, str):
            out.update(_tie_number(tok)
                       for tok in _NUMBER_IN_TEXT.findall(text))
    return out


def _arg_numbers(args: set) -> set[float]:
    return {_tie_number(v) for _k, v in args
            if isinstance(v, (int, float)) and not isinstance(v, bool)
            and math.isfinite(v)}


def _text_tied(finding: dict, candidates: list) -> list[int]:
    """Indices of the candidate calls an inputs-less finding's prose ties to.

    Only numbers that tell the calls apart can tie: an `n` or `decimals`
    every call shares is in every GRIM finding's text and would tie it to
    every call. Among the calls whose distinguishing numbers the text
    names, those naming the MOST win, so "51.9 at n=6" ties the 51.9/n=6
    call and not a 45.9/n=6 one when the calls' n differ. Calls nothing
    tells apart (one call, or identical arguments) are all tied.

    MEASURED 2026-10-16 (10.1371--journal.pone.0042828, grok-4.6, v1.78.0):
    grim_check returned `impossible` on seven Table 2 means at n=6 and the
    one inputs-less finding named only 51.9. Matching it to "any call of
    that tool" accounted for all seven, so the unfiled-results recovery
    never asked about the other six.
    """
    values = [_arg_numbers(c[1]) for c in candidates]
    if not values:
        return []
    shared = set.intersection(*values)
    distinct = [v - shared for v in values]
    if not any(distinct):
        return list(range(len(candidates)))
    said = _text_numbers(finding)
    scores = [len(d & said) for d in distinct]
    best = max(scores)
    if best == 0:
        return []
    return [i for i, s in enumerate(scores) if s == best]


def _param_names(tool: str) -> frozenset:
    """The parameters a registered tool (or its `_batch` form) takes."""
    spec = BY_NAME.get(tool) or BY_NAME.get(str(tool).removesuffix("_batch"))
    return frozenset(p.name for p in spec.params) if spec else frozenset()


def _joined(finding: dict, candidates: list) -> list[int]:
    """Indices of the `_ledger_verdicts` entries (already narrowed to the
    finding's candidate tools) that the finding accounts for. The ONE join
    behind `tool_verdict_for`, `backing_call` and `unaccounted_verdicts`."""
    wanted = _comparable(_scalars(finding.get("inputs")))
    if wanted:
        hit = [i for i, c in enumerate(candidates)
               if wanted <= _comparable(c[1])]
        if hit:
            return hit
        # A KEY THE TOOL DOES NOT TAKE CANNOT CONTRADICT ITS CALL. Analysts add
        # bookkeeping to `inputs` (`n_checked`, `n_inconsistent`, `ci_level`)
        # that no call ever received, and the strict subset then joined
        # nothing: the row read as unfiled and the recovery pass asked for it
        # again, filing a duplicate. MEASURED 2026-10-18 (statcheck_pvalue_errors
        # working set, tools_only): 14 of 156 grok problem rows failed the
        # strict join, 7 of them only on such keys. A fallback, so every join
        # that held before holds identically.
        out = []
        for i, c in enumerate(candidates):
            names = _param_names(c[0])
            w = {kv for kv in wanted if kv[0] in names}
            if w and w <= _comparable(c[1]):
                out.append(i)
        return out
    # No comparable top-level scalars. Try the nested-`n` join (see
    # `_nested_n_pairs`): when the finding's inputs carry stage/arm
    # headcounts, they must pick the call that actually contains them --
    # and a non-empty key set that matches no call refuses, never guesses.
    nested = _nested_n_pairs(finding.get("inputs"))
    if nested:
        return [i for i, c in enumerate(candidates)
                if nested <= _nested_n_pairs(c[4])]
    # Nothing structured to join on: only the calls the prose names.
    return _text_tied(finding, candidates)


def _hits(finding: dict, toolcalls_ledger: list[dict] | None):
    """(candidate tools, matching ledger rows) for one finding -- the join
    `tool_verdict_for` and `backing_call` share. Each hit is (tool, severity,
    quarantined_raw, ledger call, expanded-from-a-batch)."""
    if not isinstance(finding, dict):
        return (), []
    technique = finding.get("technique")
    if technique in NON_TOOL_TECHNIQUES:
        return (), []
    tools = _candidate_tools(technique)
    if not tools:
        return (), []
    verdicts = _ledger_verdicts(toolcalls_ledger)
    candidates = [v for v in verdicts if v[0] in tools]
    if not candidates:
        return tools, []
    hits = []
    for i in _joined(finding, candidates):
        name, _args, sev, qraw, _raw, call, exp = candidates[i]
        hits.append((name, sev, qraw, call, exp))
    return tools, hits


def backing_call(finding: dict, toolcalls_ledger: list[dict] | None) -> dict | None:
    """The one ledger call whose arguments a reproduction should replay, or
    None.

    Same join as `tool_verdict_for`, then stricter: every matching call must
    have been made with IDENTICAL arguments (otherwise which one the finding
    rests on is a guess), and none may be a row expanded out of a batch call
    (replaying the batch answers a different question). The call's own input
    is what the tool received, which the finding's `inputs` only restate.
    """
    _tools, hits = _hits(finding, toolcalls_ledger)
    if not hits or any(exp for *_x, exp in hits):
        return None
    if len({sev for _n, sev, _q, _c, _e in hits}) != 1:
        return None
    first = hits[0][3]
    key = json.dumps(first.get("input"), sort_keys=True, default=str)
    if any(json.dumps(c.get("input"), sort_keys=True, default=str) != key
           for _n, _s, _q, c, _e in hits):
        return None
    return first


def tool_verdict_for(finding: dict, toolcalls_ledger: list[dict] | None) -> dict | None:
    """The section-1.4 `tool_verdict` block for one finding, or None.

    None means "no validated tool call backs this row" -- and never a guess:
    per-tool impossible/fire statistics count on this field, so a guessed
    join here is a corrupted statistic there. The join is
    `severity_reconcile`'s (its `_TECHNIQUE_TOOLS` family mapping serves
    converted legacy rows; a v2 technique equality-joins via the identity
    fallback), with two deliberate differences from `_tool_severity`:
    `computed.severity` is NEVER read (model prose), and the joined TOOL NAME
    is returned because `derive_impossible` needs the evidence class of the
    tool that actually ran, not of the technique label.
    """
    tools, hits = _hits(finding, toolcalls_ledger)
    if not hits:
        return None
    hits = [(name, sev, qraw) for name, sev, qraw, _call, _exp in hits]
    # Unanimity, exactly as severity_reconcile requires it: if the matched
    # calls disagree we cannot say which row the model meant, and guessing
    # would clear or convict a finding on a different row's verdict.
    severities = {sev for _, sev, _ in hits}
    if len(severities) != 1:
        return None
    severity = severities.pop()
    hit_names = {name for name, _, _ in hits}
    tool = next(n for n in tools if n in hit_names)
    qraws = {q for _, _, q in hits if q is not None}
    return {
        "severity": severity,
        "tool": tool,
        "validated": True,
        "quarantined_raw": qraws.pop() if len(qraws) == 1 else None,
    }


# ---------------------------------------------------------------------------
# impossible (spec section 1.5)
# ---------------------------------------------------------------------------

def derive_impossible(finding: dict) -> bool:
    """True iff a validated absolute-evidence tool call said `impossible`.

    Reads the ANNOTATOR-written `tool_verdict` (via `tool_verdict_for`),
    never the model's prose -- a model that writes "impossible" in a title
    with no ledger row behind it derives False, which is what keeps per-tool
    impossible-fire counts trustworthy. Explicitly unreachable from
    quarantined rows, `fast_screen`, `agent_code`/`model_reading`, and any
    non-absolute tool (spec section 1.5).
    """
    if not isinstance(finding, dict):
        return False
    if finding.get("quarantined"):
        return False
    if finding.get("producer") == "fast_screen":
        return False
    if finding.get("computed_by") in ("agent_code", "model_reading"):
        return False
    verdict = finding.get("tool_verdict")
    if not isinstance(verdict, dict):
        return False
    if verdict.get("validated") is not True:
        return False
    if verdict.get("severity") != "impossible":
        return False
    tool = verdict.get("tool")
    spec = BY_NAME.get(tool) if isinstance(tool, str) else None
    return spec is not None and spec.evidence == EVIDENCE_ABSOLUTE


# ---------------------------------------------------------------------------
# provisional clamp (spec section 7, via severity9)
# ---------------------------------------------------------------------------

#: Techniques that declare the model did the arithmetic itself (computation.py).
UNCOMPUTED_TECHNIQUES = frozenset({"no_tool_exists", "tool_existed_unused"})


def clamp_provisionals(rows: list[dict]) -> dict:
    """Clamp every row's `provisional_severity` in place; return a summary.

    Each row clamps under `severity9.clamp_provisional` with its evidence
    CHANNEL: `computed_by` (a `basis: model_knowledge` row passes that basis
    through the channel slot), `producer`, whether the technique names a
    registered tool, and the quarantine flag. There is no cap keyed on the
    technique's evidence class and no ceiling (v1.14.0): a row whose channel
    carries no cap keeps the rung it claimed. Every clamp is listed in the
    summary: a severity quietly lowered is its own kind of dishonesty (the
    `severity_reconcile.clamp_uncomputed` rule). Absent provisionals are
    skipped -- whether one SHOULD be present is
    `validate_producer_constraints`' question.
    """
    summary: dict[str, Any] = {
        "n_rows": 0, "n_clamped": 0, "n_skipped": 0,
        "clamps": [], "problems": [],
    }
    for i, row in enumerate(rows or []):
        if not isinstance(row, dict):
            continue
        summary["n_rows"] += 1
        sev = row.get("provisional_severity")
        if sev is None:
            continue
        slug = str(row.get("slug") or f"row {i}")
        if isinstance(sev, bool) or not isinstance(sev, int) or not 1 <= sev <= 9:
            summary["n_skipped"] += 1
            summary["problems"].append({
                "index": i, "slug": row.get("slug"),
                "constraint": "provisional_severity_type",
                "problem": (f"provisional_severity must be an int 1-9, "
                            f"got {sev!r}; left unclamped"),
            })
            continue
        technique = row.get("technique")
        basis = row.get("basis")
        computed_by = row.get("computed_by")
        # A web_lookup row with NO recorded source is a model-knowledge row
        # for severity purposes (measured 2026-08-22: ten such rows across
        # four grok runs, one at severity 4 -- above the cap an unsourced
        # claim is allowed). A joined tool verdict keeps its own channel:
        # the tool result, not the lookup, is that row's evidence.
        unsourced_lookup = (basis == "web_lookup"
                            and not (row.get("web_sources") or [])
                            and computed_by != "registry_tool")
        channel = ("model_knowledge"
                   if basis == "model_knowledge" or unsourced_lookup
                   else computed_by)
        # Does the technique name a REGISTERED TOOL? That is what makes
        # `model_reading` cappable: a row claiming `recalc_anova` and citing no
        # call asserted arithmetic it never performed, while an
        # `internal_contradiction` has no arithmetic to cite.
        technique_is_tool = (isinstance(technique, str)
                             and technique in _tool_names())
        # ARITHMETIC DONE OUTSIDE THE GUARDS (1.91.0). `no_tool_exists` and
        # `tool_existed_unused` say the model computed the number itself;
        # the prompt promised them the model-reading cap and nothing applied
        # it (`severity_reconcile.clamp_uncomputed` reads only v1 reports).
        if technique in UNCOMPUTED_TECHNIQUES and channel != "model_knowledge":
            technique_is_tool, channel = True, "model_reading"
        producer = (row.get("producer")
                    if isinstance(row.get("producer"), str) else None)
        quarantined = bool(row.get("quarantined"))
        tv = row.get("tool_verdict") if isinstance(row.get("tool_verdict"), dict) else {}
        clamped = severity9.clamp_provisional(
            sev,
            quarantined=quarantined,
            computed_by=channel if isinstance(channel, str) else None,
            producer=producer,
            technique_is_tool=technique_is_tool,
            tool_verdict=tv.get("severity") if tv.get("validated") else None,
        )
        if clamped != sev:
            # THE ROW CARRIES ITS OWN HISTORY, because the summary does not
            # survive. `parallel.py:401` calls this function and DISCARDS the
            # return value, so `n_clamped` and the before/after list were
            # computed and thrown away -- and this clamp OVERWRITES
            # `provisional_severity`, so nothing anywhere recorded that a
            # ceiling had been applied or what the model originally claimed.
            #
            # `adjudicate._clamp` already works this way: it writes
            # `severity_from` onto the finding, and the spec's rule is that "a
            # clamp is visible, never silent". This is the same rule one stage
            # earlier, and marking the ROW rather than plumbing a summary
            # through two call sites means it cannot be dropped by a caller
            # again.
            row["provisional_severity_from"] = sev
            row["provisional_severity"] = clamped
            summary["n_clamped"] += 1
            summary["clamps"].append(
                f"{slug}: {sev} -> {clamped} (channel={channel!r}, "
                f"producer={producer!r}, quarantined={quarantined})")
    return summary


# ---------------------------------------------------------------------------
# Document blocks (spec section 2)
# ---------------------------------------------------------------------------

#: The keys the v2 `paper_metadata` block names (schema section 2): the v1
#: keys plus metadata 1.1's additions. `title` is NOT here -- the document
#: carries `paper_title` at the top level -- and neither are volume/issue/url,
#: which the block does not declare.
_PROJECTED_METADATA_KEYS = (
    "authors", "journal", "year", "doi", "study_design",
    "corresponding_author", "corresponding_email",
    "journal_normalized", "authors_list", "metadata_status",
)

_AUTHOR_FIELDS = ("given", "family", "full")


def paper_metadata_projection(metadata_json: dict | None) -> dict:
    """The pipeline-written `paper_metadata` block from a `metadata.json`.

    A 1.0 record is upgraded IN MEMORY first (zero network cost, the
    caller's dict untouched). A missing or unreadable record projects to
    `{}`: inventing a status for a file we never read would be a claim about
    a fetch that never happened. Author entries drop None fields -- the
    schema types every field as a string, and `build_authors_list`
    legitimately records `given: None` for a single-token name.
    """
    if not isinstance(metadata_json, dict):
        return {}
    meta = upgrade_record(metadata_json) if needs_enrichment(metadata_json) \
        else metadata_json
    out: dict[str, Any] = {}
    for key in _PROJECTED_METADATA_KEYS:
        value = meta.get(key)
        if value in (None, "", "NaN"):
            continue
        if key == "authors_list":
            if isinstance(value, list):
                entries = [
                    {f: entry[f] for f in _AUTHOR_FIELDS
                     if isinstance(entry.get(f), str) and entry[f]}
                    for entry in value if isinstance(entry, dict)
                ]
                entries = [e for e in entries if e]
                if entries:
                    out[key] = entries
            continue
        out[key] = value
    return out


def channels_block(channels: dict | None = None, **named: Any) -> dict:
    """Build the document's `channels` block from name -> state declarations.

    Each value may be a bare state string, a `(state, detail)` pair, or a
    `{"state": ..., "detail": ...}` dict. States are validated against
    `webapp_index.CHANNEL_STATES` -- ONE vocabulary, imported from its home
    -- and an unknown state raises rather than degrading to `"unknown"`: a
    typo'd state silently becoming "we could not tell" is the
    absence-read-as-evidence substitution this vocabulary exists to prevent.
    Consumer reminder (spec section 2): for a denominator, "ran" means state
    in {ran, ran_result_discarded}.
    """
    merged: dict[str, Any] = {}
    if channels:
        merged.update(channels)
    merged.update(named)
    out: dict[str, dict] = {}
    for name, value in merged.items():
        detail = ""
        if isinstance(value, str):
            state = value
        elif isinstance(value, (tuple, list)) and len(value) == 2:
            state, detail = value
        elif isinstance(value, dict):
            extra = set(value) - {"state", "detail"}
            if extra:
                raise ValueError(
                    f"channel {name!r} carries unknown keys {sorted(extra)}; "
                    "the block admits only state and detail")
            state = value.get("state")
            detail = value.get("detail", "")
        else:
            raise ValueError(
                f"channel {name!r} must be a state string, a (state, detail) "
                f"pair, or a state/detail dict, got {type(value).__name__}")
        if state not in CHANNEL_STATES:
            raise ValueError(
                f"channel {name!r} has unknown state {state!r}; expected one "
                f"of {CHANNEL_STATES}")
        out[name] = {"state": state, "detail": str(detail or "")}
    return out


# ---------------------------------------------------------------------------
# Producer constraints (spec section 9)
# ---------------------------------------------------------------------------

def _problem(index: int | None, slug: Any, constraint: str, sentence: str) -> dict:
    return {"index": index, "slug": slug if isinstance(slug, str) else None,
            "constraint": constraint, "problem": sentence}


def validate_producer_constraints(rows: list[dict]) -> list[dict]:
    """Spec section 9's structural subset (invariants 1, 3-presence, 4, 5),
    as problem records.

    Never raises: a validator that throws on the first bad row hides every
    row after it. An empty list means the checked invariants held, NOT that
    the rows pass the JSON schema (a separate gate). A missing FINAL
    severity is deliberately not flagged -- annotation order legitimately
    leaves it unset until adjudication has run or been skipped.
    """
    problems: list[dict] = []
    if rows is None:
        return problems
    if not isinstance(rows, (list, tuple)):
        return [_problem(None, None, "rows_not_a_list",
                         f"expected a list of finding rows, "
                         f"got {type(rows).__name__}")]
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            problems.append(_problem(
                i, None, "row_not_a_dict",
                f"finding rows must be dicts, got {type(row).__name__}"))
            continue
        slug = row.get("slug")
        producer = row.get("producer")
        outcome = row.get("outcome")
        provisional = row.get("provisional_severity")
        severity = row.get("severity")
        adjudication = row.get("adjudication")
        action = adjudication.get("action") \
            if isinstance(adjudication, dict) else None

        if row.get("computed_by") == "agent_code" and producer != "science_error":
            problems.append(_problem(
                i, slug, "agent_code_producer",
                f"computed_by 'agent_code' is legal only with producer "
                f"'science_error', not {producer!r} (spec 1.3)"))

        if producer == "fast_screen":
            if row.get("severity_is_provisional") is not True:
                problems.append(_problem(
                    i, slug, "fast_screen_provisional",
                    "fast_screen rows must carry severity_is_provisional: "
                    "true -- a screen's ranking is never final"))
            if row.get("impossible"):
                problems.append(_problem(
                    i, slug, "fast_screen_impossible",
                    "fast_screen rows can never carry impossible: true -- "
                    "a screen is a funnel, not evidence"))
            if (isinstance(provisional, int)
                    and not isinstance(provisional, bool)
                    and provisional > severity9.FAST_SCREEN_CAP):
                problems.append(_problem(
                    i, slug, "fast_screen_cap",
                    f"fast_screen provisional_severity {provisional} exceeds "
                    f"the cap of {severity9.FAST_SCREEN_CAP}"))

        # A TOOL-TECHNIQUE ROW WITH NO `inputs` CANNOT BE JOINED TO ITS OWN
        # EVIDENCE. `tool_verdict_for` matches on the finding's scalar inputs;
        # with none, the join returns None and whatever the tool actually said
        # never reaches the record -- even when the tool ran and agreed.
        #
        # MEASURED 2026-08-22 on 10.1037--0022-3514.94.2.94.2.196: four
        # `recalc_*` rows carried `inputs: null` and `tool_verdict: NONE` while
        # `recalc_anova` and `recalc_independent_t` had returned `suspicious`
        # on exactly those numbers. Corpus-wide the join is weakening -- rows
        # carrying `inputs` fell from 85% (v1.5.1) to 56% (v1.7.0) and
        # tool_verdict from 54% to 44% -- and nothing counted it.
        #
        # RECORDED, NOT REJECTED. The row is still a real observation; it is
        # under-evidenced, and `clamp_provisionals` now caps it for that
        # (MODEL_READING_CAP). This makes the RATE visible instead of leaving
        # it to be discovered by hand.
        if (outcome == "problem" and not row.get("inputs")
                and isinstance(row.get("technique"), str)
                and BY_NAME.get(row["technique"]) is not None):
            problems.append(_problem(
                i, slug, "tool_technique_without_inputs",
                f"technique {row['technique']!r} names a registered tool but "
                "the row carries no `inputs`, so no ledger call can be joined "
                "to it and the tool's own verdict cannot reach the record"))

        if provisional is not None and outcome != "problem":
            problems.append(_problem(
                i, slug, "provisional_requires_problem",
                f"provisional_severity is set but outcome is {outcome!r}; "
                "it must be null unless outcome is 'problem'"))
        if outcome == "problem" and provisional is None:
            problems.append(_problem(
                i, slug, "problem_requires_provisional",
                "outcome is 'problem' but provisional_severity is null; "
                "a problem row must be ranked"))
        if severity is not None:
            if outcome != "problem":
                problems.append(_problem(
                    i, slug, "severity_requires_problem",
                    f"severity is set but outcome is {outcome!r}; final "
                    "severity is null unless outcome is 'problem'"))
            elif action == "discarded":
                problems.append(_problem(
                    i, slug, "severity_on_discarded",
                    "severity is set on a discarded row; discarded rows are "
                    "retained with severity: null"))

        if row.get("quarantined") and not str(
                row.get("quarantine_reason") or "").strip():
            problems.append(_problem(
                i, slug, "quarantine_without_reason",
                "quarantined without quarantine_reason; a bare cap with no "
                "reason is forbidden"))
    return problems


def unaccounted_verdicts(findings: list[dict] | None, ledger: list[dict] | None,
                         severities=None) -> list[dict]:
    """Ledger verdicts at `severities` that NO filed finding accounts for.

    "Accounts for" is `tool_verdict_for`'s join (`_joined`), read the other
    way round: a finding whose technique names the tool and whose `inputs`
    scalars are a subset of the call's (or, with no comparable scalars, its
    nested `n` pairs; or, with neither, whose quote, location, title or
    description names the call's distinguishing numbers -- `_text_tied`)
    covers the call. An inputs-less finding covers only the calls its prose
    names, never every call of its tool.

    A `pass` row does NOT cover a call that accused (1.91.0). It says the
    analyst's own tool was wrong without saying why, which is the silent
    contradiction this list exists to surface; the recovery pass then asks for
    a filing or a dismissal with a reason. An `undecided` row still covers: it
    is a visible filing, and the recovery prompt itself offers it. MEASURED
    2026-10-18 (statcheck_pvalue_errors working set): excluding pass rows adds
    14 calls on grok's 1.88 run, one a known error; excluding undecided too
    would add 47, mostly results already filed as undecided.

    MEASURED 2026-10-13 (apple_cider, grok-4.6): tools agents that made 79 and
    95 forensic calls -- dozens of them suspicious or worse -- filed ONE
    finding each, and every other result was lost to the review.
    """
    if severities is None:
        # The verdicts an analyst must account for: suspicious or worse.
        from .tools.severity import ACCUSES_AT_ALL as severities
    verdicts = _ledger_verdicts(ledger)
    covered: set[int] = set()
    for f in findings or []:
        if not isinstance(f, dict):
            continue
        if f.get("technique") in NON_TOOL_TECHNIQUES or f.get("outcome") == "pass":
            continue
        tools = _candidate_tools(f.get("technique"))
        idx = [i for i, v in enumerate(verdicts) if v[0] in tools]
        if idx:
            covered.update(idx[j]
                           for j in _joined(f, [verdicts[i] for i in idx]))
    out = []
    for i, (name, _args, sev, _q, _raw, call, expanded) in enumerate(verdicts):
        if sev in severities and i not in covered:
            out.append({"tool": name, "severity": sev, "call": call,
                        "expanded": expanded})
    return out


# --- from the image package's copy (not re-exported before) ---
def _tool_names():
    """The host's tool registry, looked up at CALL time. A module-level
    `from .integration import forensic_tool_names` bound None for good when
    this module was imported before the host configured the hook, so every
    host tool name then read as unregistered."""
    from . import integration
    names = integration.forensic_tool_names
    return names() if names else ("analyze_paper_images",)


# --- deterministic deduplication when there is no adjudicator (1.91.0) ---
#: The p-value checks whose rows describe ONE printed statistic. Two such rows
#: about the same statistic are the same finding filed twice -- typically once
#: from statcheck and once from `recalc_stat_to_p`.
P_STATISTIC_TECHNIQUES = frozenset({
    "statcheck", "recalc_stat_to_p", "recalc_f_to_p", "recalc_anova",
    "recalc_independent_t", "recalc_within_subjects_t", "recalc_chi_squared",
    "check_estimate_ci", "check_regression"})

_APA_STAT = re.compile(
    r"(?:\bt|\bF|\br|\bz|χ2|chi2)\s*(?:\(\s*[\d.]+\s*(?:,\s*[\d.]+)?\s*\))?\s*=\s*(-?\d*\.?\d+)"
    r".{0,60}?\bp\s*[<>=]\s*(0?\.\d+)", re.I)


def _abs_num(x):
    try:
        v = abs(float(x))
    except (TypeError, ValueError):
        return None
    return round(v, 6) if math.isfinite(v) else None


def statistic_signature(row: dict):
    """What statistic a p-check row is about, or None.

    Built from the row's own `inputs` (reported p plus the statistic value, or
    the group means), else from an APA statistic in its title or quote. NEVER
    from the quote alone: MEASURED 2026-10-18 on a grok tools_only run
    (10.1007--s40200-021-00832-0), four recalc_anova rows about BMI, visceral
    fat, RMR/FFM and waist shared one quote -- the table's footnote -- and a
    quote-keyed merge would have collapsed four different statistics.
    """
    if row.get("technique") not in P_STATISTIC_TECHNIQUES:
        return None
    inp = row.get("inputs") if isinstance(row.get("inputs"), dict) else {}
    p = _abs_num(inp.get("reported_p"))
    stat = next((_abs_num(inp[k]) for k in ("statistic", "f_value", "t", "reported_t",
                                             "reported_f", "reported_chi2", "estimate")
                 if k in inp and _abs_num(inp[k]) is not None), None)
    if p is not None and stat is not None:
        return ("stat", stat, p)
    means = inp.get("means")
    if p is not None and isinstance(means, list) and means:
        return ("means", tuple(_abs_num(m) for m in means), p)
    m = _APA_STAT.search(" ".join(str(row.get(k) or "") for k in ("title", "quote")))
    if m and _abs_num(m.group(1)) is not None and _abs_num(m.group(2)) is not None:
        return ("stat", _abs_num(m.group(1)), _abs_num(m.group(2)))
    return None


def deduplicate_by_statistic(rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Collapse p-check rows about the SAME statistic to one, for the path with
    no adjudicator to merge them. Returns (kept rows, one record per removed row).

    Only rows with the same outcome merge. The kept row is the one backed by a
    registry tool, then the higher severity, then the first filed. It
    notes which other techniques reported the statistic, and the removed rows
    are listed in the return value (the run writes them to
    `coverage_summary.deduplicated`), so nothing disappears unrecorded.
    MEASURED 2026-10-18 on the statcheck_pvalue_errors working set: 7 such
    duplicates in grok's 1.83 tools_only run and 15 in its 1.88 run; none
    merged two different known errors.
    """
    groups: dict = {}
    order = []
    for i, r in enumerate(rows):
        if not isinstance(r, dict):
            continue
        sig = statistic_signature(r)
        if sig is None:
            continue
        # Same statistic AND same outcome: a `problem` and a `pass` about one
        # statistic are a disagreement between checks, and both stay visible.
        sig = (sig, r.get("outcome"))
        if sig not in groups:
            groups[sig] = []
            order.append(sig)
        groups[sig].append(i)
    drop: set[int] = set()
    removed: list[dict] = []
    for sig in order:
        idx = groups[sig]
        if len(idx) < 2:
            continue
        def rank(i):
            r = rows[i]
            return (0 if r.get("computed_by") == "registry_tool" else 1,
                    -(r.get("severity") or r.get("provisional_severity") or 0), i)
        keep = min(idx, key=rank)
        kept = rows[keep]
        others = [i for i in idx if i != keep]
        also = sorted({str(rows[i].get("technique")) for i in others}
                      - {str(kept.get("technique"))})
        if also:
            note = f"Also reported by {', '.join(also)} (deduplicated: same statistic)."
            kept["notes"] = " ".join(x for x in (str(kept.get("notes") or ""), note) if x)
        for i in others:
            drop.add(i)
            removed.append({"finding_id": rows[i].get("finding_id"),
                            "kept": kept.get("finding_id"),
                            "technique": rows[i].get("technique"),
                            "outcome": rows[i].get("outcome"),
                            "title": rows[i].get("title")})
    return [r for i, r in enumerate(rows) if i not in drop], removed
