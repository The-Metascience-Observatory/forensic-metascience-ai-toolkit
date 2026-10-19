"""Shared implementation extracted for independent image analysis."""
import json


import os


import re


_FENCED_JSON_RE = re.compile(r"```(?:json)?\s*\n(.*?)\n```", re.DOTALL)


_DOCUMENT_MARKERS = ("schema_version", "paper_id")


def _salvage_documents(blob: str) -> list[dict]:
    """Every COMPLETE, well-formed document embedded in `blob`, richest first.

    WHY THIS TIER EXISTS -- MEASURED 2026-09-04 on a live grok tool-expert run
    (airforce, the A/B's parallel/parallel arm). The stage made 87 tool calls
    over 1,030 s and produced one `impossible` verdict. Its final result was
    61,300 chars that began with a REAL document, degenerated at char 4,904
    into `Extra. Extra. Extra...` repeated, and then re-emitted a COMPLETE
    18-finding document (34 register rows, 8 unchecked) occupying the rest of
    the stream.

    `_extract_json` returned `failed` and threw all of it away, because every
    tier it had reads the stream from the START: `json.loads` on the whole
    string dies on the abandoned prefix, and the fenced-block tier finds
    nothing because grok emits bare JSON. The run was then charged for a paid
    `_repair_json` retry -- and in the archive that retry came back empty, so
    a stage that had done the work was recorded as having produced nothing.

    THE ANALYST LOSS IS THEREFORE PARTLY OURS, not the model's. The model
    degenerates mid-document (this is the `n.n.n.n...` signature from
    wound_healing wearing different filler), but it RECOVERS and re-emits.
    What lost the work was an extractor that could not skip a prefix.

    RICHEST, NOT LAST. The model emits empty skeleton placeholders throughout a
    grok run -- that is normal and documented -- so "the last complete object"
    would happily return an empty skeleton emitted after the real document.
    Ties break toward the later object.

    NOTHING IS EVER SYNTHESISED. Only objects that decode COMPLETELY via
    `raw_decode` and carry a document marker are eligible; a truncated document
    is not repaired here, it is skipped.
    """
    if not isinstance(blob, str) or not blob.strip():
        return []
    decoder = json.JSONDecoder()
    found: list[tuple[int, dict]] = []
    for match in re.finditer(r'\{\s*"', blob):
        start = match.start()
        try:
            obj, _end = decoder.raw_decode(blob, start)
        except ValueError:
            continue
        if isinstance(obj, dict) and any(k in obj for k in _DOCUMENT_MARKERS):
            found.append((start, obj))
    found.sort(key=lambda pair: (len(pair[1].get("findings") or []), pair[0]),
               reverse=True)
    return [obj for _start, obj in found]


#: The parse path of a document taken from the transcript's accepted
#: StructuredOutput call because no `result` event delivered it.
ACCEPTED_TOOL_CALL_PATH = "structured_output_tool_use"


def _accepted_structured_output(messages) -> dict | None:
    """The input of the LAST StructuredOutput call the CLI accepted.

    MEASURED 2026-10-18 (v1.83.0 sonnet batch, statcheck working set): six
    stages show the model calling StructuredOutput with a full document and
    the CLI answering "Structured output provided successfully", then the
    stream ends with no `result` event -- the CLI dropped it at exit (see
    `runtime._FileLineReader`). The document is the one the CLI's schema gate
    accepted; the `result` event would only have repeated it. A call whose
    tool_result is an error (a schema rejection), or that has no tool_result
    at all, is never used: nothing confirmed it.
    """
    accepted: dict[str, bool] = {}
    calls: list[tuple[str, dict]] = []
    for msg in messages or []:
        if not isinstance(msg, dict):
            continue
        inner = msg.get("message") if isinstance(msg.get("message"), dict) else {}
        for block in inner.get("content") or []:
            if not isinstance(block, dict):
                continue
            if (msg.get("type") == "assistant" and block.get("type") == "tool_use"
                    and block.get("name") == "StructuredOutput"
                    and isinstance(block.get("input"), dict) and block.get("id")):
                calls.append((block["id"], block["input"]))
            elif msg.get("type") == "user" and block.get("type") == "tool_result":
                accepted[block.get("tool_use_id")] = not block.get("is_error")
    for call_id, doc in reversed(calls):
        if accepted.get(call_id):
            return doc
    return None


def accepted_tool_call_note(stage: dict, label: str) -> str:
    """The limitation for a document recovered by `_accepted_structured_output`."""
    note = (f"the {label} stage's document was read from its accepted "
            "StructuredOutput call in the transcript")
    if stage.get("result_event") is False:
        note += (": the stream ended without the CLI's final `result` event, "
                 "so this stage's cost and token totals are UNKNOWN (recorded "
                 "as 0), not zero")
    return note


def mark_no_document(stage: dict) -> None:
    """A stage that delivered no document FAILED, whatever the CLI said.

    The v1.83.0 sonnet batch recorded six such stages as `is_error: false`
    beside a limitation saying they produced nothing, so the channel read
    `ran` and the report counted the analyst as present (AGENTS.md: a failed
    or truncated stage must announce itself). An earlier, more specific
    subtype (budget, timeout, schema gate) is kept.
    """
    if not stage.get("is_error"):
        stage["is_error"] = True
        stage["error_subtype"] = ("no_result_event"
                                  if stage.get("result_event") is False
                                  else "no_parseable_output")


def _extract_json(stage: dict) -> tuple[dict | None, str]:
    """Parse structured output from a stage.

    Returns (parsed, parse_path) where parse_path is one of
    'json_schema', 'structured_output_tool_use', 'fenced_block',
    'salvaged_object', 'failed'.

    Grok (and some Claude builds) populate `result.structured_output` as a
    dict. Without reading it every grok stage falls through to a paid repair.
    """
    so = stage.get("structured_output")
    if isinstance(so, dict):
        return so, "json_schema"
    raw = stage.get("result")
    if isinstance(raw, dict):
        return raw, "json_schema"
    if isinstance(raw, str) and raw.strip():
        try:
            return json.loads(raw), "json_schema"
        except json.JSONDecodeError:
            pass
    # Before any tier that guesses from prose: a document the CLI's schema
    # gate ACCEPTED is in the transcript even when the stream lost the
    # `result` event that would have carried it.
    accepted = _accepted_structured_output(stage.get("messages"))
    if accepted is not None:
        return accepted, ACCEPTED_TOOL_CALL_PATH
    # Fall back to the last fenced JSON block in the assistant text.
    candidates = _FENCED_JSON_RE.findall(stage.get("text") or "")
    if isinstance(raw, str):
        candidates += _FENCED_JSON_RE.findall(raw)
    for block in reversed(candidates):
        try:
            return json.loads(block), "fenced_block"
        except json.JSONDecodeError:
            continue
    # LAST DETERMINISTIC TIER, BEFORE ANYTHING PAID. A stream that begins with
    # an abandoned document still often CONTAINS a complete one; see
    # `_salvage_documents` for the measurement that put this here. Free, and it
    # runs before `_repair_json` spends money re-asking for output we already
    # have.
    for blob in (raw if isinstance(raw, str) else "", stage.get("text") or ""):
        salvaged = _salvage_documents(blob)
        if salvaged:
            return salvaged[0], "salvaged_object"
    return None, "failed"


def _validate_track_output(obj, *, technique: str,
                           label: str) -> tuple[dict, list[dict]]:
    """Structural validation of a forensic-track child's stdout against its
    contract (`schema/text_track.schema.json` here, `image_track.schema.json`
    in the image package's `prompts/schema/`).

    STRICT by design: one malformed row invalidates the whole output and zero
    findings are injected (`track_output_invalid`), because a partially
    trusted channel from a subprocess into the paid editorial prompt is how
    garbage becomes a finding. The severity check is the quarantine enforced
    a second time, at the boundary: no accusatory value may cross it,
    whatever the child claims. The expected technique and severity set are
    HARD-CODED per track by the wrappers below, never imported from the
    child's constants -- defense in depth.
    """
    if not isinstance(obj, dict) or obj.get("schema_version") != "1.0":
        raise ValueError(f"not a {label} v1.0 object")
    status = obj.get("status")
    if not isinstance(status, dict) or "ran" not in status:
        raise ValueError("status block missing or malformed")
    rows = obj.get("findings_rows")
    if not isinstance(rows, list):
        raise ValueError("findings_rows is not a list")
    required = ("id", "location", "technique", "consistent", "severity",
                "reproduction")
    for row in rows:
        if not isinstance(row, dict) or any(k not in row for k in required):
            raise ValueError("findings row missing required keys")
        if row["technique"] != technique:
            raise ValueError(f"row technique {row['technique']!r} is not "
                             f"{technique}")
        if row["severity"] not in ("indeterminate", "consistent"):
            raise ValueError(f"accusatory severity {row['severity']!r} tried "
                             "to cross the track boundary")
    return status, rows


def _track_timeout(env_var: str, default: float) -> float:
    try:
        return float(os.environ.get(env_var, default))
    except ValueError:
        return default
