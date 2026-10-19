"""An append-only record of every edit we make to a paper in order to read it.

WHY THIS EXISTS. We already edit papers. `glyphs.apply_proven_repairs` rewrites
mojibake, `extraction.jats.repair_extraction_damage` substitutes XML entities
and repairs `¼` to `=`, `completeness._repair_equals` does the same in another
copy, and `jats._normalise` collapses whitespace -- the last of which destroys
the only evidence that ``VBFM N = 38   BFM N = 27`` names two groups rather than
one. NONE of it was recorded anywhere. A reader of a finding could not tell
whether the number it rests on is the number the paper printed.

The policy this implements (Greg, 2026-08-29) does not loosen anything. It makes
an existing undocumented practice auditable:

    Every repair is logged (file, byte range, before, after, rule, reason); the
    original is retained; and the adjudicator receives, per finding, the repairs
    its evidence depends on, so a finding that survives ONLY because of a repair
    can be judged as such.

TWO LIMITS, BOTH INHERITED FROM THE INVARIANTS.

1. A repair may RESTORE a distinction, never INVENT one. ``n ¼ 68`` -> ``n = 68``
   restores a character a font destroyed. Splitting a fused header on a
   whitespace run ASSERTS two columns, which is a reading, and belongs in the
   interpretation layer carrying a confidence -- not here.

2. A repair may NARROW what a check does, never widen it. This is invariant 2
   ("a derived boundary may narrow a premise, never supply one") applied to
   text. `narrows_only` records which side a repair falls on, and a repair that
   cannot say is recorded as widening, because the field FAILS CLOSED.

WHAT THIS MODULE IS NOT. It does not perform repairs and does not decide whether
one is justified. It is the ledger. Callers repair; they record here; the
adjudicator reads.

THE SECOND JOB: AUTHORISING A HAND-REPAIRED BODY. `markdown/body.md` is written
by `extraction.markdown_out` as a faithful copy of whatever the resolver chain
produced, so that a human can check that conversion did not mangle the paper.
MEASURED 2026-08-31 over the 12-paper working corpus: all 12 carry
``markdown/body.md``, none carries a top-level ``body.md``, and
`jats.paper_text_with_source` reads ONLY the top-level name -- so an edit to the
canonical file is invisible to the pipeline. Appending a sentinel to
`markdown/body.md` and re-resolving returns text without it, on both an
XML-sourced and a PDF-sourced paper.

That makes the policy above unusable as written: the obvious place to put a
repaired body does nothing, silently. So a repair log ALSO acts as the
declaration that turns `markdown/body.md` from a derived artifact into an input.
It is strictly opt-in -- absent a log, resolution is exactly what it was -- and
that is deliberate: changing the chain's preference order for every paper is a
much larger change than this policy asks for, and would relabel the source of
all 12 corpus papers as a side effect.

AN UNDECLARED EDIT IS NOT A REPAIR. If `markdown/body.md` diverges from the
derived text and no log declares it, that is a stale artifact or an
unrecorded hand-edit. `divergence` reports it; the resolver keeps ignoring it.
Reporting rather than reading is the fail-closed direction: an undeclared edit
that silently became the paper is precisely the outcome the log exists to
prevent.
"""

from __future__ import annotations

import hashlib
import json
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

#: Lives beside `body.md` and `source.json` in the paper's `markdown/` dir.
REPAIRS_NAME = "repairs.json"

REPAIRS_SCHEMA = 1


@dataclass
class Repair:
    """One edit, with enough detail to undo it and to judge it.

    `before`/`after` are the literal strings, so a reader never has to re-run
    the rule to know what changed. `offset` is a byte offset into the ORIGINAL
    text -- the retained one -- because offsets into the repaired text shift
    with every earlier repair and would make the log unreadable in order.
    """

    rule: str                      # e.g. "glyphs.proven_repairs"
    reason: str                    # why this restores rather than invents
    before: str
    after: str
    offset: int | None = None
    target: str = "body"           # body | table | supplement | <table id>
    #: Does this repair NARROW what a check can do, or widen it? Invariant 2
    #: applied to text. FAILS CLOSED: a repair that cannot justify itself as
    #: narrowing is recorded as widening, and is the kind an adjudicator
    #: should weigh against a finding that depends on it.
    narrows_only: bool = False

    def key(self) -> str:
        return f"{self.rule}:{self.target}:{self.offset}:{self.before}"


@dataclass
class RepairLog:
    """Append-only. `original_sha256` pins WHICH text the offsets refer to."""

    paper_id: str = ""
    original_sha256: str = ""
    original_source: str | None = None   # the `paper_text_with_source` label
    schema_version: int = REPAIRS_SCHEMA
    #: Set only when the log declares `markdown/body.md` to BE the paper text.
    #: A log that merely records repairs made in-memory leaves this false, and
    #: resolution is unchanged.
    declares_body_md: bool = False
    repairs: list[Repair] = field(default_factory=list)

    def add(self, repair: Repair) -> "RepairLog":
        self.repairs.append(repair)
        return self

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["n_repairs"] = len(self.repairs)
        return d

    def depended_on_by(self, quote: str) -> list[Repair]:
        """The repairs whose `after` text appears in `quote`.

        This is the per-finding join the policy asks for. It is deliberately a
        SUBSTRING test on the repaired form: if the quote contains text that
        only exists because we rewrote it, the finding resting on that quote
        depends on the repair. Over-inclusive by design -- naming a repair that
        turned out not to matter costs an adjudicator one glance, while missing
        one hides exactly what the log was built to surface.
        """
        if not quote:
            return []
        return [r for r in self.repairs if r.after and r.after in quote]


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", "replace")).hexdigest()


def path(paper_dir: str | Path) -> Path:
    from .extraction.markdown_out import markdown_dir
    return markdown_dir(paper_dir) / REPAIRS_NAME


def load(paper_dir: str | Path) -> RepairLog | None:
    """The log, or None when there is none or it cannot be trusted.

    Fails closed on every error: a malformed log must not be read as "no
    repairs were made", but it also must not authorise a body we cannot
    validate, so the caller sees None and keeps the unrepaired behavior.

    ABSENT AND BROKEN ARE DIFFERENT FACTS, and returning None for both is the
    house failure mode -- an absence rendered as knowledge. Nobody wrote the
    file that is not there; somebody DID write the one that will not parse, and
    intended it to be read. So a present-but-unreadable log WARNS while an
    absent one is silent. The return value stays None either way, because the
    safe behavior is identical; it is the reader who needs to be told.
    """
    p = path(paper_dir)
    if not p.exists():
        return None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 -- unreadable, or not JSON
        warnings.warn(f"{p}: a repair log is present but could not be read "
                      f"({exc.__class__.__name__}); it is being ignored, so "
                      f"any repair it declares will NOT be applied.",
                      stacklevel=2)
        return None
    why = None
    if not isinstance(raw, dict):
        why = "the top level is not an object"
    elif raw.get("schema_version") != REPAIRS_SCHEMA:
        why = (f"schema_version is {raw.get('schema_version')!r}, "
               f"not {REPAIRS_SCHEMA}")
    if why:
        warnings.warn(f"{p}: a repair log is present but unusable ({why}); it "
                      f"is being ignored, so any repair it declares will NOT "
                      f"be applied.", stacklevel=2)
        return None
    try:
        reps = [Repair(**r) for r in (raw.get("repairs") or [])
                if isinstance(r, dict)]
    except TypeError as exc:
        warnings.warn(f"{p}: a repair log is present but one of its entries "
                      f"does not match the Repair schema ({exc}); it is being "
                      f"ignored, so any repair it declares will NOT be "
                      f"applied.", stacklevel=2)
        return None
    return RepairLog(
        paper_id=str(raw.get("paper_id") or ""),
        original_sha256=str(raw.get("original_sha256") or ""),
        original_source=raw.get("original_source"),
        declares_body_md=bool(raw.get("declares_body_md")),
        repairs=reps,
    )


def save(paper_dir: str | Path, log: RepairLog) -> Path:
    p = path(paper_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    from .atomicio import atomic_write_text
    atomic_write_text(p, json.dumps(log.to_dict(), indent=2, ensure_ascii=False))
    return p


def authorises_body_md(paper_dir: str | Path) -> RepairLog | None:
    """The log iff it declares `markdown/body.md` to be the paper's text.

    Requires `declares_body_md` AND at least one recorded repair: a declaration
    with an empty repair list is a claim that the body was edited and that
    nothing was edited, which is not a state we should act on.
    """
    log = load(paper_dir)
    if log is None or not log.declares_body_md or not log.repairs:
        return None
    return log


def divergence(paper_dir: str | Path, derived_text: str) -> dict:
    """Whether `markdown/body.md` still matches the text the chain derives.

    Returns `state` in:
      `absent`     -- no body.md on disk
      `match`      -- byte-identical to the derived text (the normal case: it
                      is a copy written by `markdown_out`)
      `declared`   -- differs, and a repair log declares it
      `undeclared` -- differs, and nothing declares it

    `undeclared` is the one worth acting on and is NOT an accusation of anyone:
    the common cause is a stale copy written before a converter changed. It is
    reported so that "the file on disk is not what the pipeline reads" stops
    being invisible.
    """
    from .extraction.jats import find_body_md
    p = find_body_md(paper_dir)
    if p is None:
        return {"state": "absent", "n_repairs": 0}
    try:
        on_disk = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {"state": "absent", "n_repairs": 0}
    if on_disk == derived_text:
        return {"state": "match", "n_repairs": 0, "path": str(p)}
    log = authorises_body_md(paper_dir)
    return {
        "state": "declared" if log else "undeclared",
        "n_repairs": len(log.repairs) if log else 0,
        "path": str(p),
        "disk_sha256": sha256(on_disk),
        "derived_sha256": sha256(derived_text),
    }
