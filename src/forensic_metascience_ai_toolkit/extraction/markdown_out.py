"""The paper as markdown, written by US, in one place an agent can find.

WHY THIS EXISTS
---------------
Three separate facts, measured 2026-08-22 over 1,293 paper directories:

1. **Nothing reads the markdown that is there.** `paper_text_with_source` and
   `find_body_md` know `body.md` (286 papers) and `<stem>_from_pdf_body.md`
   (27). `fetchpdf --to-markdown` writes `<stem>_from_xml.md` (418) and
   `<stem>_from_html.md` (37), which appear NOWHERE in this repo's source. So
   the commonest conversion on disk is invisible to us, and **980 of 1,293
   papers (76%) present to an agent as having no markdown at all**.

2. **The agents go looking anyway, and burn the run doing it.** On the
   2026-08-22 biomedical batch the adjudicator failed 66% of its tool calls
   and reached the forensic MCP server on 14% of them, against 0-2% / 83% for
   the tool expert. Nearly every failure was `read_file` for `body.md`,
   `paper/body.md`, `paper.md`, `docket.json` -- names it guessed. One paper
   (`10.1016--j.ynstr.2021.100304`) stalled mid-turn during that thrash and
   held a worker for 70 minutes.

3. **fetchpdf's markdown must NOT be the answer.** Of the 418 papers holding
   both an XML and a `_from_xml.md`, **152 (36%) declare fewer tables in their
   front matter than the XML actually contains** -- nearly all `tables: 0`,
   including a Lancet paper with 7. The table content is not dropped, it is
   DISSOLVED INTO THE PROSE with no delimiters::

       2-AG at post-injury5.111.870.232.730.007**AEA at post-injury0.21...

   which is B=5.11, SE=1.87, beta=0.23, t=2.73, p=0.007. The file's own header
   says `tables_not_machine_readable: 0` -- it certifies that nothing was
   lost. That is the exact failure `jats.py`'s invariant exists to prevent:
   some publishers nest `<table-wrap>` INSIDE a `<p>`, so paragraph flattening
   must skip table markup or a model transcribes numbers from prose that has
   already lost its column alignment.

WHAT THIS WRITES, AND WHY FROM `paper_text_with_source`
-------------------------------------------------------
`<paper_dir>/markdown/body.md` plus `source.json`, generated from
`paper_text_with_source` -- which already resolves the best available channel
AND already applies the `[Table N: caption -- R rows x C cols]` placeholder
rule. That is the whole reason this folder is ours to write rather than
fetchpdf's to hand over: the placeholder is the guarantee, and we only have it
on our own output.

`body.md` is named for what the agents already guess. The cheapest repair for
a wrong guess is to make the guess right.

STALENESS, IN TWO LAYERS
------------------------
`materialise` is the AUTHORITY and compares content: it re-resolves the text
and regenerates unless the sha256 in `source.json` still matches. It runs from
`ensure_paper_extracted`, before any agent starts, so within a run the folder
is current by construction.

The READ path (`cached_body`) cannot afford that resolve -- it is the thing the
resolve was supposed to avoid -- so it uses an mtime guard over the candidate
source files instead. That over-regenerates after a Dropbox/Drive sync, which
rewrites mtimes without changing content, and never serves a stale body. One
wasted resolve against a review written about a version of the paper that is
no longer on disk is not a close call.
"""

from __future__ import annotations

import hashlib
import json
import warnings
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

#: The folder, and the names inside it. One place, one spelling.
MARKDOWN_DIRNAME = "markdown"
BODY_NAME = "body.md"
SOURCE_NAME = "source.json"

#: Bumped when the CONTENT of `body.md` would change for the same source --
#: a placeholder-format change, a different channel preference. An older
#: stamp regenerates rather than being served, on the `docling_tables`
#: reasoning: a file whose provenance we cannot pin is not a saving.
# 2 (2026-08-31): added the glyph verdict -- `text_is_clean`, `quarantine`,
# `glyph_sites`, `glyph_patterns`, `digits_corrupted`. Bumped rather than added
# silently BECAUSE `materialise` treats a schema match as "current": without the
# bump every paper already on disk would keep the old shape forever and the new
# fields would appear only on papers converted for the first time. The currency
# check reading the schema is what makes that work; it was already there.
MARKDOWN_SCHEMA = 2

#: The table placeholder `jats.py` emits. Counted into `source.json` so a
#: reader can see at a glance that tables were kept OUT of the prose -- the
#: property that distinguishes this file from `<stem>_from_xml.md`.
_PLACEHOLDER = re.compile(r"\[Table\s", re.I)


def markdown_dir(paper_dir: str | Path) -> Path:
    return Path(paper_dir) / MARKDOWN_DIRNAME


def body_path(paper_dir: str | Path) -> Path:
    return markdown_dir(paper_dir) / BODY_NAME


def source_path(paper_dir: str | Path) -> Path:
    return markdown_dir(paper_dir) / SOURCE_NAME


#: A markdown pipe-table row: at least two cell separators on one line. Two
#: rather than one, because a line may legitimately contain a single `|`
#: (a regex in a methods section, a units column header) and a table row
#: cannot have fewer than two.
_PIPE_ROW = re.compile(r"^\s*\|.*\|.*\|\s*$", re.MULTILINE)


def _count_inlined_table_rows(text: str) -> int:
    """How many markdown table rows sit in the prose, uninlined by anybody.

    The counterpart to `n_table_placeholders`, and the reason
    `tables_are_placeholders_not_inlined` can be computed rather than claimed.
    A row here means a model is reading numbers whose column association came
    from an extractor rather than from markup we walked -- and, when the same
    table is ALSO flattened into the page text, reading each of them twice.

    Counts rows, not tables, deliberately: a table's row count is a fact this
    function can establish from the text alone, whereas grouping rows into
    tables would need the separator conventions of whichever converter wrote
    them, and guessing that is how this field became a promise in the first
    place.
    """
    return len(_PIPE_ROW.findall(text or ""))


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def read_source(paper_dir: str | Path) -> dict | None:
    """`source.json` as a dict, or None when it is absent or unreadable.

    Unreadable is None rather than `{}`: a caller must not be able to mistake
    "we could not read the provenance" for "there is no provenance".
    """
    p = source_path(paper_dir)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


#: NO `cached_body` READER LIVES HERE, on purpose. This folder is written FOR
#: AGENTS to `read_file`; it is never an input to our own text path. See the
#: comment in `paper_text_with_source` for the measurement that settled it.


def write_markdown(paper_dir: str | Path, text: str, channel: str | None,
                   source_file: str | Path | None = None) -> dict:
    """Write `markdown/body.md` + `source.json`. Returns the provenance dict.

    NEVER RAISES ON A WRITE IT CANNOT DO. This is a convenience artifact
    materialised on the way into a paid run; a read-only corpus mount must
    degrade to "the folder is not there" and let the run proceed on the text
    it already has in memory, not abort a paper over a cache write.
    """
    text = text or ""
    meta: dict[str, Any] = {
        "markdown_schema": MARKDOWN_SCHEMA,
        "source_channel": channel,
        "source_file": (Path(source_file).name if source_file else None),
        "converted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_chars": len(text),
        # The property that makes this file safe to hand a model, stated as a
        # number rather than a promise -- see the module docstring on
        # `_from_xml.md`, whose header promises and does not deliver.
        "n_table_placeholders": len(_PLACEHOLDER.findall(text)),
        # MEASURED, NOT ASSERTED. This was hardcoded `True` on the line below
        # the comment above, which is the same defect that comment criticises
        # in somebody else's file: a header that promises and does not check.
        #
        # It is wrong whenever the text did not come from `jats.py`, because
        # the placeholder is emitted THERE and nowhere else. The commonest such
        # case is `source_channel == "body_md"` -- a `body.md` already on disk,
        # written by an older pipeline or by a converter that is not ours, read
        # back and stamped with our guarantee without anyone looking at it.
        #
        # MEASURED 2026-08-26 on the 12-paper working corpus: 6 papers resolve
        # to publisher XML and carry real placeholders; 6 resolve to a PDF text
        # layer or a pre-existing body.md and carry none, and 3 of those hold
        # markdown pipe tables inline -- 6, 9 and 10 table rows. On
        # `benchmarks/paper_reviews/runs/apple_cider` the same three tables appear TWICE, once as
        # column-collapsed page prose and again as pipe tables, under a
        # `source.json` reporting `n_table_placeholders: 0` beside
        # `tables_are_placeholders_not_inlined: true`.
        "n_inlined_table_rows": _count_inlined_table_rows(text),
        "tables_are_placeholders_not_inlined":
            _count_inlined_table_rows(text) == 0,
        "text_sha256_16": _digest(text),
        "written_by": "forensic_metascience_ai_toolkit.extraction.markdown_out",
    }
    # WHETHER THIS TEXT IS KNOWN TO BE CHARACTER-CORRUPT.
    #
    # This file exists so a human can check that conversion did not mangle the
    # paper. It recorded schema, channel, length and a hash -- everything
    # EXCEPT the one property it was written to expose. A quarantined paper's
    # `source.json` was byte-identical in shape to a clean one's.
    #
    # MEASURED on the 12-paper corpus, 2026-08-31: eleven papers convert clean;
    # `10.1371--journal.pone.0069841` carries 23 corruption sites --
    # 14 `<` rendered as `,` (so `p < .0001` reads `p , .0001`) and 9 lost
    # operators before a decimal (`B = -.006` reads `B = 2 .006`, which puts an
    # invented leading digit and a wrong sign into a value a check will read).
    # `glyphs.scan` detects all 23 and `proven_repairs` correctly returns `{}`
    # -- nothing is repairable, so nothing is repaired. That verdict simply
    # never reached the artifact a reader opens.
    #
    # A DOCUMENT THAT LOOKS CLEAN AND IS NOT is the house failure mode: the
    # system holds the knowledge and the file renders its absence as health.
    try:
        from ..glyphs import scan as _glyph_scan
        verdict = _glyph_scan(text) or {}
        meta["text_is_clean"] = bool(verdict.get("clean", True))
        meta["quarantine"] = bool(verdict.get("quarantine", False))
        meta["glyph_sites"] = int(verdict.get("total_occurrences") or 0)
        meta["glyph_patterns"] = [
            {"pattern": pat.get("pattern"), "count": pat.get("count"),
             "corrupts_digits": bool(pat.get("corrupts_digits"))}
            for pat in (verdict.get("patterns") or [])]
        meta["digits_corrupted"] = any(
            p.get("corrupts_digits") for p in (verdict.get("patterns") or []))
    except Exception as exc:  # noqa: BLE001 -- never fail a convenience write
        # RECORDED, not swallowed. A missing verdict must not read as a clean
        # one: `None` is distinguishable from `True` by every consumer, and
        # silence here would restore exactly the defect this block closes.
        meta["text_is_clean"] = None
        meta["quarantine"] = None
        meta["glyph_scan_error"] = f"{type(exc).__name__}: {exc}"
    try:
        d = markdown_dir(paper_dir)
        d.mkdir(parents=True, exist_ok=True)
        from ..atomicio import atomic_write_text
        atomic_write_text(d / BODY_NAME, text)
        atomic_write_text(d / SOURCE_NAME, json.dumps(meta, indent=1) + "\n")
    except Exception as exc:  # noqa: BLE001 -- see the docstring
        meta["error"] = f"{type(exc).__name__}: {exc}"
    return meta


def materialise(paper_dir: str | Path) -> dict:
    """Ensure `markdown/` matches the paper's current best text.

    Idempotent and cheap when it is already current: one text resolve and one
    digest compare, no write. Called from `ensure_paper_extracted`, which runs
    before any agent starts, so the folder is there when the first tool call
    goes looking for it.

    Reports what it did rather than returning a bare bool -- a caller that
    wants to tell an operator "the markdown was rebuilt" needs the reason, and
    a silent no-op is indistinguishable from a silent failure.
    """
    paper_dir = Path(paper_dir)
    out: dict[str, Any] = {"paper": paper_dir.name, "action": "skipped"}
    if not paper_dir.is_dir():
        out["reason"] = f"not a directory: {paper_dir}"
        return out

    # Deferred: `jats` imports this module's siblings, and the resolve chain
    # is what this function exists to snapshot.
    from .jats import paper_text_with_source

    try:
        text, channel = paper_text_with_source(paper_dir)
    except Exception as exc:  # noqa: BLE001
        out["reason"] = f"could not resolve the paper's text: {type(exc).__name__}"
        return out

    if not (text or "").strip():
        # "" is UNKNOWN, never "this paper says nothing" -- the rule
        # `paper_text_with_source` states. Writing an empty body.md would turn
        # our failure to read into an artifact asserting the paper is blank.
        out["reason"] = ("no text could be resolved from any source; nothing "
                         "written, because an empty body.md would assert the "
                         "paper is blank")
        return out

    # IS THE FILE ON DISK STILL THE FILE WE WROTE? The currency check below
    # compares the RECORDED digest against the freshly derived text; it never
    # reads body.md itself. So a hand-edited body.md passes as `current`, and
    # this function's docstring promise -- "markdown/ matches the paper's
    # current best text" -- becomes false without anything saying so.
    #
    # That matters now that a repair MAY be declared. body.md is the file we
    # tell a person to inspect, so it is where they will make a repair, and the
    # three outcomes must be distinguishable: a declared repair is READ, an
    # undeclared one is IGNORED, and until now being ignored looked exactly
    # like being applied. The edit is not destroyed either -- it simply sits
    # there while the pipeline reads something else.
    try:
        from ..repairs import divergence as _divergence
        out["body_md"] = _divergence(paper_dir, text)
        if out["body_md"].get("state") == "undeclared":
            warnings.warn(
                f"{body_path(paper_dir)} differs from the text the pipeline "
                f"resolves, and no repair log declares it. The edit is being "
                f"IGNORED, not applied. Declare it with a repairs.json (see "
                f"forensic_metascience_ai_toolkit.repairs) or delete the file to have it "
                f"rewritten.", stacklevel=2)
    except Exception as exc:  # noqa: BLE001 -- a report must never cost the snapshot
        # Recorded rather than swallowed: a caller that sees no `body_md` key
        # must be able to tell "checked, and it matches" from "never checked".
        out["body_md"] = {"state": "unknown",
                          "why": f"{type(exc).__name__}: {exc}"}

    digest = _digest(text)
    meta = read_source(paper_dir)
    if (meta and meta.get("text_sha256_16") == digest
            and int(meta.get("markdown_schema") or 0) == MARKDOWN_SCHEMA
            and body_path(paper_dir).is_file()):
        out.update(action="current", source_channel=meta.get("source_channel"),
                   n_chars=meta.get("n_chars"))
        return out

    written = write_markdown(paper_dir, text, channel)
    out.update(action="written" if not written.get("error") else "failed",
               **{k: written.get(k) for k in
                  ("source_channel", "n_chars", "n_table_placeholders", "error")})
    return out
