"""The structural account as a frozen, first-class artifact.

WHY THIS EXISTS (D43, 2026-09-07). Given ONE structural vocabulary the
downstream passes are close to deterministic -- table values carried the same
variable id on 204 of 204 matched entries, prose values 0.94, comparisons 1.0.
Given fresh decompositions of the same paper they are not: 0.76 / 0.67 / 0.0.
And a wrong structural decision is propagated faithfully, which is the part that
matters -- one run read a column as `se` and the next as `sd`, each of them
consistently, all the way into every check's premise. So the paper is decomposed
ONCE, that one decomposition is adjudicated, it is frozen, and every later pass
SELECTS from it. A re-run never re-decomposes.

WHAT THE FILE IS. `<paper>/scaffold/structure.json` carries the pass-1 and
pass-2 products with their ids unchanged, the sha256 of the served document they
were read from, who produced them, a status in {draft, adjudicated, frozen}, an
integer version, the append-only adjudication audit, and `frozen_at`. Every
version is also kept at `structure.versions/<n>.json`; a frozen file is never
rewritten, and a change of any kind writes n+1 and leaves n on disk.

THE THREE PROPERTIES THIS MODULE ENFORCES, and each is a refusal rather than a
correction:

  1. A CLOSED VOCABULARY. Every study, group, phase, variable, level or test id
     a reading or pass 3 emits must be a member of this file's id sets. A
     foreign id is never accepted: the id becomes null, the text it was read as
     is kept in `<field>_as_read`, and the value is counted under
     `unbound_foreign_id`. No downstream pass may create a variable.
  2. NO MIXING OF VERSIONS. An account may not be assembled from artifacts that
     record different `structure_sha256` values -- the same rule `agreement`
     uses for schema versions, for the same reason: a figure spanning two
     vocabularies measures the vocabulary change.
  3. A CHANGED DOCUMENT IS SAID, NEVER SILENTLY RE-READ. If the served
     document's sha256 differs from the one the structure was built on, the run
     continues and the account is marked `stale_document` with both hashes and
     the character counts by source. Nothing is re-decomposed, and nothing
     proceeds without saying so.

The content hash deliberately covers the pass-1 and pass-2 products, the paper
identity and the document hash, and NOT the status, the version, the timestamps
or `produced_by`: freezing a draft does not change the vocabulary, so an
artifact read against the draft is still an artifact read against that
vocabulary. An adjudication DOES change the products, so it moves the hash, and
artifacts read against the un-adjudicated structure are then refused -- which is
the point.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "structure/1"

#: draft: written by passes 1 and 2 on a paper with no structure file.
#: adjudicated: a second reader's corrections have been applied under the gates.
#: frozen: fixed by an explicit command; nothing may re-decompose without
#: `--redecompose`, which writes the next version as a new draft.
STATUSES = ("draft", "adjudicated", "frozen")

FILENAME = "structure.json"
VERSIONS_DIRNAME = "structure.versions"


class StructureError(RuntimeError):
    """Any refusal this module makes. Never raised for a missing file."""


class StructureFrozen(StructureError):
    """A frozen version was asked to change. Use `--redecompose` for a new one."""


class StructureMismatch(StructureError):
    """Artifacts recording two different structures were asked to be one account."""


# --------------------------------------------------------------------------
# the id sets, and the closed vocabulary
# --------------------------------------------------------------------------

#: WHICH ID SET EACH FIELD DRAWS FROM. A field that is not named here is not an
#: id and is left alone -- `value_id` names a value row, `table_id` a table, and
#: neither is structural. The plural forms are the same vocabulary: a foreign
#: member of `contrast.group_ids` is dropped from the list and the list as read
#: is kept beside it.
#:
#: `test_id` is here and NO PASS EMITS ONE TODAY: the schemas carry
#: `test_type_stated` from a closed enum and `statistical_analysis.tests_named`
#: as free text, neither of which is an id. It is named so that the day a test
#: acquires an id, it is inside the closed vocabulary rather than outside it.
ID_KIND_OF_FIELD: dict[str, str] = {
    "study_id": "studies", "study_ids": "studies",
    "group_id": "groups", "group_ids": "groups", "reference_group_id": "groups",
    "phase_id": "phases", "phase_ids": "phases",
    "variable_id": "variables", "variable_ids": "variables",
    "outcome_variable_id": "variables", "y_variable_id": "variables",
    "level_id": "levels", "level_ids": "levels",
    "test_id": "tests", "test_ids": "tests",
}

ID_KINDS = ("studies", "groups", "phases", "variables", "levels", "tests")


def _pass1(structure: dict) -> dict:
    return structure.get("pass1") or {}


def _pass2(structure: dict) -> dict:
    return structure.get("pass2") or {}


def id_sets(structure: dict) -> dict[str, set[str]]:
    """The ids a downstream pass may name, by kind. Everything else is foreign."""
    p1, p2 = _pass1(structure), _pass2(structure)
    studies = p1.get("studies") or []
    variables = p2.get("variables") or []
    return {
        "studies": {s.get("id") for s in studies if s.get("id")},
        "groups": {g.get("id") for s in studies for g in (s.get("groups") or []) if g.get("id")},
        "phases": ({p.get("id") for s in studies for p in (s.get("phases") or []) if p.get("id")}
                   | {p.get("id") for p in (p1.get("phases") or []) if p.get("id")}),
        "variables": {v.get("id") for v in variables if v.get("id")},
        "levels": {l.get("id") for v in variables for l in (v.get("levels") or []) if l.get("id")},
        "tests": set(),
    }


def id_counts(structure: dict) -> dict[str, int]:
    return {k: len(v) for k, v in id_sets(structure).items()}


#: `n = 64`, `n=64`, `N = 101`. The `n` must be a WORD, so `Region n` and
#: `Wilcoxon = 64` cannot match. The trailing guard is the part that earns its
#: keep: a per-group n is a WHOLE COUNT OF UNITS, so `n = 12.5` is not one and
#: `n = 6-9` is a range across groups and not a group's own n (CLAUDE.md 8i:
#: "only a PRINTED n counts here; a range is not a per-group n"). The guard has
#: to forbid the whole continuation and not just the next character, or the
#: engine backtracks and reads `n = 12.5` as 1.
_N_IN_LABEL = re.compile(
    r"(?<![A-Za-z])[nN]\s*=\s*(\d+)(?![\d.,]|\s*[-–—]\s*\d)")


def group_n(group: dict) -> tuple[int | None, str | None]:
    """`(n, n_source)` for one declared group. Null when the label does not say.

    WHY THIS IS PARSED AND NOT ASKED FOR. Every declared group on ajcp.70049 has
    `n_printed: None` while its LABEL is the string `n = 64 coalitions` -- the
    number is right there and no field holds it, so a header like `Intervention
    (n = 34)` has nothing to join against. The parse is deterministic, so it is
    code's to do; asking a model for a number it can misread would be the wrong
    half of the division of labour this package rests on.

    EXACTLY ONE `n = <int>`, or nothing. `n = 101 programs in 35 coalitions`
    yields 101, because only one integer is introduced by an `n =`; a label
    carrying two of them (`n = 30 then n = 28`) yields null rather than a
    choice between them -- an ambiguous join binds nothing. `n_printed` wins
    where the model copied a bare integer out of the paper, because that is the
    paper's own printing of the group's n and this is a fallback for its absence.
    """
    printed = str(group.get("n_printed") or "").strip()
    if printed.isdigit():
        return int(printed), "n_printed"
    found = _N_IN_LABEL.findall(str(group.get("label") or ""))
    if len(found) == 1:
        return int(found[0]), "label"
    return None, None


def annotate_group_n(studies: list[dict]) -> dict:
    """Stamp `n` and `n_source` on every group of `studies`, in place; count."""
    by_source: dict[str, int] = {}
    total = 0
    for s in studies or []:
        for g in s.get("groups") or []:
            total += 1
            n, src = group_n(g)
            g["n"], g["n_source"] = n, src
            by_source[src or "not_stated"] = by_source.get(src or "not_stated", 0) + 1
    return {"groups": total, "with_n": total - by_source.get("not_stated", 0),
            "by_source": dict(sorted(by_source.items())),
            "note": ("A group's `n` is PARSED, never read: from `n_printed` when the model "
                     "copied a bare integer, else from exactly one `n = <int>` in the "
                     "group's own printed label. Two of them in one label yields null.")}


def close_vocabulary(sets: dict[str, set[str]], *artifacts: Any) -> dict:
    """Null every foreign id in `artifacts`, in place, and count them.

    THE ASYMMETRY IS DELIBERATE. Nulling an id can only remove a binding -- a
    value keeps its printed number, its cell and the words it was read as, and
    loses the claim that those words are THIS declared variable. Accepting a
    foreign id would do the opposite: it would let a reading coin a variable
    the paper's own decomposition does not contain, and every check downstream
    would then run on a premise nobody adjudicated.

    IT COUNTS THE SAME NUMBER TWICE. An id already nulled carries its
    `<field>_as_read` mark, and a second pass over the same artifact counts it
    again rather than reporting zero -- the account is assembled several times
    per run (once per residual iteration) and a count that fell to zero on the
    second call would have made the honest figure invisible in the artifact a
    reader sees.
    """
    counts: dict[str, int] = {}
    examples: list[dict] = []
    n = 0

    def note(field: str, value: Any, where: str) -> None:
        nonlocal n
        n += 1
        counts[field] = counts.get(field, 0) + 1
        if len(examples) < 20:
            examples.append({"field": field, "id_as_read": value, "in": where})

    def walk(node: Any, where: str) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, where)
            return
        if not isinstance(node, dict):
            return
        for key, value in list(node.items()):
            kind = ID_KIND_OF_FIELD.get(key)
            if kind is None:
                walk(value, where)
                continue
            allowed = sets.get(kind) or set()
            mark = node.get(f"{key}_as_read")
            if value is None or isinstance(value, str):
                if value and value not in allowed:
                    node[key] = None
                    node.setdefault(f"{key}_as_read", value)
                    note(key, value, where)
                elif value is None and isinstance(mark, str):
                    note(key, mark, where)          # nulled by an earlier pass
            elif isinstance(value, list) and all(isinstance(x, str) for x in value):
                foreign = [x for x in value if x and x not in allowed]
                if foreign:
                    node.setdefault(f"{key}_as_read", list(value))
                    node[key] = [x for x in value if x not in foreign]
                already = [m for m in mark if m not in value] if isinstance(mark, list) else []
                for x in foreign or already:
                    note(key, x, where)
            else:
                walk(value, where)

    for artifact in artifacts:
        walk(artifact, _where_of(artifact))
    return {"unbound_foreign_id": n, "by_field": dict(sorted(counts.items())),
            "examples": examples,
            "note": ("Every study, group, phase, variable, level and test id a reading or "
                     "pass 3 emitted was checked against the structure's own id sets. A "
                     "foreign id is nulled, its text kept in `<field>_as_read`, and counted "
                     "here; no downstream pass may create a variable.")}


def _where_of(artifact: Any) -> str:
    if isinstance(artifact, dict):
        for key, name in (("table_readings", "pass3"), ("dispositions", "residual"),
                          ("new_values", "residual")):
            if key in artifact:
                return name
    if isinstance(artifact, list):
        return "table readings"
    return "artifact"


# --------------------------------------------------------------------------
# the file
# --------------------------------------------------------------------------


def path(out_dir: str | Path) -> Path:
    return Path(out_dir) / FILENAME


def versions_dir(out_dir: str | Path) -> Path:
    return Path(out_dir) / VERSIONS_DIRNAME


def version_path(out_dir: str | Path, version: int) -> Path:
    return versions_dir(out_dir) / f"{int(version)}.json"


def load(out_dir: str | Path) -> dict | None:
    """The current structure, or None when the paper has none. A missing file is
    not an error: it is how a first run knows to decompose."""
    p = path(out_dir)
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def presence(out_dir: str | Path) -> str:
    """`absent` | `empty` | `present` -- three states, not two.

    A `structure.json` HOLDING `{}` IS NOT "NO STRUCTURE". `load` returns `{}`
    for it, every caller tests `if struct:`, and the file therefore reads
    exactly like a paper that was never decomposed -- while an account beside it
    claims a `structure_sha256` that nothing on disk hashes to. Measured: the
    run completed and `checks.json` reproduced the account's own unverified
    claim as the structure it had verified against. The three states are
    different facts and the caller needs them apart.
    """
    p = path(out_dir)
    if not p.is_file():
        return "absent"
    try:
        got = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return "empty"
    return "present" if got else "empty"


def load_version(out_dir: str | Path, version: int) -> dict | None:
    p = version_path(out_dir, version)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def versions_on_disk(out_dir: str | Path) -> list[int]:
    d = versions_dir(out_dir)
    if not d.is_dir():
        return []
    return sorted(int(m.group(1)) for f in d.glob("*.json")
                  if (m := re.fullmatch(r"(\d+)", f.stem)))


def content_sha256(structure: dict) -> str:
    """The hash of the VOCABULARY: the products, the identity and the document
    they were read from. Not the status, not the version, not the timestamps --
    freezing a draft does not change what a reading selected from."""
    payload = {"schema_version": structure.get("schema_version"),
               "paper_identity": structure.get("paper_identity"),
               "document_sha256": structure.get("document_sha256"),
               "pass1": _pass1(structure), "pass2": _pass2(structure)}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False)
                          .encode("utf-8")).hexdigest()


def stamp(structure: dict | None) -> dict:
    """What every downstream artifact records, so that mixing can be refused."""
    if not structure:
        return {}
    return {"structure_version": structure.get("version"),
            "structure_sha256": content_sha256(structure)}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _identity(p1: dict, doc: dict) -> dict:
    front = doc.get("front") or {}
    paper = p1.get("paper") or {}
    out = {k: front.get(k) or paper.get(k) for k in ("title", "journal", "year", "doi")}
    out["identity_source"] = f"front matter ({front.get('source')})" if front else "model reading"
    return out


def _document_chars(doc: dict) -> dict:
    src = doc.get("source") or {}
    return {"total": src.get("n_chars"),
            "article": src.get("n_chars_article"),
            "supplements": {s.get("file"): s.get("n_chars")
                            for s in (doc.get("supplement_spans") or [])}}


def build(p1: dict, p2: dict, doc: dict, *, produced_by: dict | None = None,
          version: int = 1, status: str = "draft") -> dict:
    """A structure record from the two passes' output. Pure: no I/O."""
    if status not in STATUSES:
        raise StructureError(f"status {status!r} is not one of {STATUSES}")
    src = doc.get("source") or {}
    rec = {
        "schema_version": SCHEMA_VERSION,
        "version": int(version),
        "status": status,
        "created_at": _now(),
        "frozen_at": _now() if status == "frozen" else None,
        "paper_identity": _identity(p1, doc),
        "document_sha256": src.get("text_sha256"),
        "document_chars": _document_chars(doc),
        "produced_by": produced_by or {},
        "pass1": p1,
        "pass2": p2,
        "adjudication": [],
    }
    rec["ids"] = id_counts(rec)
    rec["sha256"] = content_sha256(rec)
    return rec


def save(structure: dict, out_dir: str | Path) -> Path:
    """Write the current structure and snapshot its version.

    A FROZEN VERSION IS NEVER REWRITTEN. Saving a different content over the
    version on disk is refused; the way to change a frozen structure is to write
    the next version, which leaves this one where it is.
    """
    out = Path(out_dir)
    current = load(out)
    if (current is not None and current.get("status") == "frozen"
            and int(current.get("version") or 0) == int(structure.get("version") or 0)
            and content_sha256(current) != content_sha256(structure)):
        raise StructureFrozen(
            f"structure v{current.get('version')} is frozen and may not be rewritten "
            f"(frozen at {current.get('frozen_at')}); write the next version instead "
            "(`--redecompose`), which leaves this one on disk")
    structure["ids"] = id_counts(structure)
    structure["sha256"] = content_sha256(structure)
    body = json.dumps(structure, indent=1, ensure_ascii=False)
    versions_dir(out).mkdir(parents=True, exist_ok=True)
    version_path(out, structure["version"]).write_text(body, encoding="utf-8")
    p = path(out)
    p.write_text(body, encoding="utf-8")
    return p


def create(p1: dict, p2: dict, doc: dict, out_dir: str | Path, *,
           produced_by: dict | None = None, freeze_draft: bool = False) -> dict:
    """Version 1, written by passes 1 and 2 on a paper with no structure file."""
    rec = build(p1, p2, doc, produced_by=produced_by,
                version=1, status="frozen" if freeze_draft else "draft")
    save(rec, out_dir)
    return rec


def redecompose(previous: dict, p1: dict, p2: dict, doc: dict, out_dir: str | Path, *,
                produced_by: dict | None = None, freeze_draft: bool = False) -> tuple[dict, dict]:
    """The next version, as a new DRAFT, and the diff against the one it
    replaces. The previous version stays on disk under its own number."""
    rec = build(p1, p2, doc, produced_by=produced_by,
                version=int(previous.get("version") or 1) + 1,
                status="frozen" if freeze_draft else "draft")
    save(rec, out_dir)
    return rec, versions_diff(previous, rec)


def freeze(structure: dict, out_dir: str | Path) -> dict:
    """Fix this version. Refused on one already frozen -- freezing twice would
    move `frozen_at` and make the record of when it was fixed untrue."""
    if structure.get("status") == "frozen":
        raise StructureFrozen(f"structure v{structure.get('version')} is already frozen "
                              f"(at {structure.get('frozen_at')})")
    rec = dict(structure)
    rec["status"] = "frozen"
    rec["frozen_at"] = _now()
    save(rec, out_dir)
    return rec


# --------------------------------------------------------------------------
# the versions diff (D38's instrument, between versions rather than between runs)
# --------------------------------------------------------------------------


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float | None:
    sa, sb = set(a), set(b)
    return round(len(sa & sb) / len(sa | sb), 3) if (sa | sb) else None


def versions_diff(old: dict, new: dict) -> dict:
    """Studies / groups / variables Jaccard between two versions.

    This is the D38 test-retest instrument pointed at two VERSIONS rather than
    two runs. It renders no verdict: a low Jaccard says the two decompositions
    disagree, which is the fact a reader needs before deciding that the new one
    is better.
    """
    so, sn = id_sets(old), id_sets(new)
    return {
        "from_version": old.get("version"), "to_version": new.get("version"),
        "from_sha256": content_sha256(old)[:16], "to_sha256": content_sha256(new)[:16],
        "jaccard": {k: _jaccard(so[k], sn[k]) for k in ("studies", "groups", "variables", "levels", "phases")},
        "counts": {k: {"from": len(so[k]), "to": len(sn[k])}
                   for k in ("studies", "groups", "variables", "levels", "phases")},
        "note": ("Jaccard over the id sets of the two versions. It says how far the "
                 "decomposition moved, not which of the two the paper supports."),
    }


def format_diff(diff: dict) -> str:
    j, c = diff.get("jaccard") or {}, diff.get("counts") or {}
    return (f"structure v{diff.get('from_version')} -> v{diff.get('to_version')}: "
            + ", ".join(f"{k} {c[k]['from']}->{c[k]['to']} (jaccard {j[k]})" for k in j))


# --------------------------------------------------------------------------
# artifacts: which structure each was read against
# --------------------------------------------------------------------------


def artifact_stamps(out_dir: str | Path) -> dict[str, str | None]:
    """`{artifact: structure_sha256 or None}` over every pass meta on disk.

    An artifact produced before this stamp existed carries None and is not a
    mismatch -- it is an artifact whose structure we cannot name, which is a
    different fact from one read against a different structure.
    """
    out = Path(out_dir)
    found: dict[str, str | None] = {}
    for p in sorted(out.glob("*.meta.json")) + sorted((out / "tables").glob("*.meta.json")):
        try:
            meta = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        found[p.name] = meta.get("structure_sha256")
    return found


def refuse_mixed_versions(stamps: dict[str, str | None], expected: str | None = None,
                          require: bool = False) -> None:
    """Raise when the artifacts on hand were read against two structures.

    The same rule `agreement` applies to schema versions: two artifacts built on
    different vocabularies cannot be matched, and an account spanning them
    measures the vocabulary change rather than the paper.

    `require` MAKES ABSENCE A REFUSAL RATHER THAN AN AGREEMENT, and it is off by
    default because `artifact_stamps` is deliberately three-valued: "an artifact
    made before the stamp existed says nothing about which structure it was read
    against, which is a different fact from being read against a different one".

    Where the artifacts ARE expected to be stamped -- `checks.py` reads two
    stamps the account writes about itself -- a missing stamp is not that third
    fact, it is an unproven premise, and the set comprehension below counted it
    as agreement. Measured: an account whose two stamps were `""` or `None` ran
    all seven checks beside a structure on disk that hashes to something else,
    and the artifact then printed THAT structure's sha256 as the one it had
    verified against. So the caller expecting stamps asks for them, and is told
    by name which one is absent.
    """
    if require:
        missing = sorted(k for k, v in (stamps or {}).items()
                         if not str(v if v is not None else "").strip())
        if missing or not stamps:
            raise StructureMismatch(
                "the artifacts on hand do not name the structure they were read against, "
                "so agreement cannot be shown: "
                + ("; ".join(f"{k} is unstamped" for k in missing)
                   or "no artifact carries a stamp at all")
                + (f"; the structure now on disk is {expected[:12]}" if expected else ""))
    seen = {s for s in (stamps or {}).values() if s}
    if expected:
        seen.add(expected)
    if len(seen) > 1:
        where = "; ".join(f"{k} -> {v[:12] if v else 'unstamped'}"
                          for k, v in sorted((stamps or {}).items()) if v)
        raise StructureMismatch(
            f"artifacts were read against {len(seen)} different structures "
            f"({', '.join(sorted(s[:12] for s in seen))}); an account may not be "
            f"assembled from them: {where}"
            + (f"; the structure now on disk is {expected[:12]}" if expected else ""))


# --------------------------------------------------------------------------
# the structural adjudication (step 2 of the lifecycle)
# --------------------------------------------------------------------------

#: The three edits a structural adjudication may make that a FIELD correction
#: cannot express. Each has its own gate below, because each is a different kind
#: of claim: an addition asserts the paper contains something the decomposition
#: missed, and a removal asserts it does not contain something the decomposition
#: has. Nothing here can rename or renumber -- an id, once emitted, is the thing
#: every artifact points at.
#: ...plus `add_printed_as`, which adds no id at all: it records a label the
#: PAPER already prints for a variable the decomposition already has. Its gate is
#: not a sentence in the body -- a table row stub is not prose and is not there --
#: but the row labels the TABLE EXTRACTOR read, which is stronger evidence for a
#: claim about what a table prints than any sentence would be.
STRUCTURAL_OPS = ("add_study", "add_variable", "add_level", "remove_variable",
                  "add_printed_as")

STRUCTURAL_EDIT_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "op": {"type": "string", "enum": list(STRUCTURAL_OPS)},
        "id": {"type": "string", "description": "For an addition, the NEW id (`study:`, `var:`, "
                                                "`lvl:`); for a removal, the id to remove; for "
                                                "`add_printed_as`, the DECLARED variable the "
                                                "printed label belongs to."},
        "parent_variable_id": {"anyOf": [{"type": "string"}, {"type": "null"}],
                               "description": "For `add_level`, the declared variable it is a "
                                              "level of; null otherwise."},
        "label": {"anyOf": [{"type": "string"}, {"type": "null"}],
                  "description": "For `add_printed_as`, the label VERBATIM as the table prints "
                                 "it; a human label otherwise."},
        "role": {"anyOf": [{"type": "string"}, {"type": "null"}],
                 "description": "For `add_variable`, a member of `schema.VARIABLE_ROLES`."},
        "kind": {"anyOf": [{"type": "string"}, {"type": "null"}],
                 "description": "For `add_variable`, a member of `schema.VARIABLE_KINDS`."},
        "quote": {"anyOf": [{"type": "string"}, {"type": "null"}],
                  "description": "The VERBATIM, contiguous sentence of the paper that shows this "
                                 "study, variable or level exists. An addition without one is "
                                 "refused: it would be the model adding to the paper. For "
                                 "`add_printed_as`, give the table row label VERBATIM AND IN "
                                 "FULL, banner and statistic form included -- that is where the "
                                 "label is printed, and it is checked against the extractor's "
                                 "own row labels."},
        "why": {"type": "string"},
    },
    "required": ["op", "id", "parent_variable_id", "label", "role", "kind", "quote", "why"],
    "additionalProperties": False,
}


def structure_adjudication_schema() -> dict:
    """The compare schema plus `structural_edits`. The FIELD corrections keep the
    machine form `review.apply_adjudication` already accepts, unchanged -- the
    additions and the removal are what that form cannot express."""
    from . import review as _review
    sch = json.loads(json.dumps(_review.COMPARE_SCHEMA))
    sch["properties"]["structural_edits"] = {"type": "array", "items": STRUCTURAL_EDIT_SCHEMA}
    sch["required"] = list(sch["required"]) + ["structural_edits"]
    return sch


STRUCTURE_FOCUS = """\
You are the SECOND READER of the STRUCTURAL account of a paper -- its studies,
groups, phases, variables and levels, and nothing else. This decomposition is
made ONCE and frozen; every later pass selects from it and none may add to it,
so an error here is an error in every value that follows.

Read the paper and say, with the passage that decides each:
- are the studies separated correctly -- is one study two, or two studies one?
- is a group or a phase missing, or named as something it is not?
- is every variable the paper measures, manipulates, derives or fixes declared,
  and is any variable declared TWICE under two names?
- are the levels of each factor the ones the paper prints? A level list may be
  INCOMPLETE and still be right: a paper that prints `Male, No. (%)` and nothing
  for female has printed one level of two, and recording one level is correct.
  Do not add a level the paper does not print.
- is each variable's kind and role justified by a located sentence? Where a table
  header says one thing and the text another, say so as a disagreement -- that
  is a conflict to record, not a thing for you to settle.

Give a field correction in the machine form for anything the paper decides, and
use `structural_edits` for what that form cannot say: adding a study, a variable
or a level, or removing a variable the paper does not contain. Every addition
needs a verbatim sentence from the paper. A removal is refused while any value
binds to the variable, so say what should happen to those values in `why`.
"""


def structure_review_prompt(structure: dict, paper_text: str, paper_chars: int = 70_000) -> str:
    """The STRUCTURE-focused second reading. Paid, and never run implicitly."""
    from . import review as _review
    body = {"studies": _pass1(structure).get("studies"),
            "phases": _pass1(structure).get("phases"),
            "subjects": _pass1(structure).get("subjects"),
            "procedures": [{"id": p.get("id"), "name": p.get("name")}
                           for p in _pass1(structure).get("procedures") or []],
            "variables": _pass2(structure).get("variables"),
            "group_coordinates": _pass2(structure).get("group_coordinates"),
            "phase_coordinates": _pass2(structure).get("phase_coordinates")}
    # THE INDEX FENCE IS SERVED, because the task text tells the reader to copy
    # `target_ids` out of it. An instruction pointing at a fence that is not
    # there is a false instruction (`_ID_INDEX_TASK`'s own warning), and the
    # correction it produces would be dropped for an id that matches nothing.
    return (STRUCTURE_FOCUS
            + _review._ID_INDEX_TASK.replace("ID INDEX A and ID INDEX B", "ID INDEX")
                                    .replace("that account's index", "the index")
            + _review._fence("THE STRUCTURE (version "
                             f"{structure.get('version')}, status {structure.get('status')})",
                             json.dumps(body, indent=1, ensure_ascii=False))
            + _review._fence("THE PAPER", _review._clip(paper_text, paper_chars, "paper"))
            + _review._fence("ID INDEX (copy target_ids from here)",
                             _review.id_index(_account_view(structure))))


def _account_view(structure: dict) -> dict:
    """The structure in the shape `review.apply_adjudication` reads: the same
    records, addressed by the same ids. Not a copy -- the gates edit the
    structure's own studies and variables in place, which is the point."""
    p1, p2 = _pass1(structure), _pass2(structure)
    return {"studies": p1.get("studies") or [], "phases": p1.get("phases") or [],
            "variables": p2.get("variables") or [], "values": [],
            "document": {"tables": []}}


def apply_structural_adjudication(structure: dict, adjudication: dict, paper_text: str, *,
                                  side: str = "a", bound_variable_ids: set[str] | None = None,
                                  printed_row_labels: set[str] | None = None,
                                  out_dir: str | Path | None = None) -> tuple[dict, dict]:
    """Apply a structural adjudication under the existing gates, extended.

    Returns `(the next version of the structure, the audit)`. The field
    corrections go through `review.apply_adjudication` UNCHANGED -- one
    implementation of G1-G11, not a second copy of it -- and the three edits it
    cannot express are gated here:

      * an ADDED study, variable or level requires a verbatim quote located in
        the paper. Without one the addition is the model adding to the paper,
        which is the one thing a decomposition may never do.
      * a REMOVED variable is refused while any value binds to it. `bound_variable_ids`
        must be supplied to remove anything: not knowing what binds is not the
        same as knowing nothing does, and the fail-closed reading is the only one
        that cannot orphan a value.
      * a KIND change follows G11 in `review`: a header may not overrule a
        text-derived kind, and the disagreement is recorded as a `kind_conflict`
        on the variable rather than resolved.
      * an added `printed_as` label is refused unless the TABLE EXTRACTOR read
        that label. `printed_row_labels` is `interpret.row_label_vocabulary` over
        the served document's tables; without it every such edit is refused,
        because not knowing what the tables print is not the same as knowing
        they print this.

    The audit is appended to `structure['adjudication']`, which is append-only,
    and the result is written as version n+1 with status `adjudicated` when
    `out_dir` is given.
    """
    from . import review as _review
    # THE VERSION IT REPLACES IS NOT TOUCHED. Every gate below edits records in
    # place, so the copy is what makes n+1 a new version rather than a rewrite of
    # n -- the property `save` refuses to break on disk, kept in memory too.
    rec = json.loads(json.dumps(structure))
    view = _account_view(rec)
    # THIS ROUND'S CONFLICTS, not every conflict on the record. A conflict is
    # kept on the variable for good, so counting them all would report the
    # first round's disagreement again in the second, and the account would say
    # a conflict was recorded by a round that recorded nothing.
    before = {v.get("id"): json.dumps(v.get("kind_conflict"), sort_keys=True)
              for v in view["variables"]}
    summary = _review.apply_adjudication(view, adjudication, paper_text, side=side)
    edits_applied, edits_skipped = _apply_structural_edits(
        rec, adjudication.get("structural_edits") or [], paper_text,
        bound_variable_ids=bound_variable_ids, printed_row_labels=printed_row_labels)
    conflicts = [{"variable_id": v.get("id"), **(v.get("kind_conflict") or {})}
                 for v in view["variables"] if v.get("kind_conflict")
                 and json.dumps(v.get("kind_conflict"), sort_keys=True) != before.get(v.get("id"))]
    audit = {
        "at": _now(),
        "adjudicator": {"model": adjudication.get("model"), "version": adjudication.get("version")},
        "applied": list(summary["applied"]) + edits_applied,
        "skipped": list(summary["skipped"]) + edits_skipped,
        "conflicts": conflicts,
        "n_applied": len(summary["applied"]) + len(edits_applied),
        "n_skipped": len(summary["skipped"]) + len(edits_skipped),
        "n_conflicts": len(conflicts),
        "basis": ("model_review -- every correction is a model's adjudication, gated, and "
                  "recorded on the record with what it replaced"),
    }
    rec["version"] = int(structure.get("version") or 1) + 1
    rec["status"] = "adjudicated"
    rec["frozen_at"] = None
    rec["created_at"] = _now()
    rec["adjudication"] = list(structure.get("adjudication") or []) + [audit]
    rec["ids"] = id_counts(rec)
    rec["sha256"] = content_sha256(rec)
    if out_dir is not None:
        save(rec, out_dir)
    return rec, audit


def _apply_structural_edits(structure: dict, edits: list[dict], paper_text: str, *,
                            bound_variable_ids: set[str] | None,
                            printed_row_labels: set[str] | None = None
                            ) -> tuple[list[dict], list[dict]]:
    from .. import quotes as _quotes
    from . import interpret as _interpret
    from .bind import _Hay
    hay = _Hay(paper_text or "")
    from . import schema as _schema
    sets = id_sets(structure)
    p1, p2 = _pass1(structure), _pass2(structure)
    applied: list[dict] = []
    skipped: list[dict] = []

    def located(q: Any) -> bool:
        return (isinstance(q, str) and len(q.strip()) >= _quotes._MIN_FRAGMENT
                and hay.verify(q).get("quote_verified") == "verbatim")

    for e in edits:
        op, new_id = e.get("op"), e.get("id")
        item = e.get("why") or op
        if op not in STRUCTURAL_OPS:
            skipped.append({"item": item, "why": f"op {op!r} is not one of {STRUCTURAL_OPS}"}); continue
        if not new_id:
            skipped.append({"item": item, "why": f"{op} names no id"}); continue
        if op == "remove_variable":
            if new_id not in sets["variables"]:
                skipped.append({"item": item, "why": f"`{new_id}` is not a declared variable"}); continue
            if bound_variable_ids is None:
                skipped.append({"item": item, "target": new_id,
                                "why": "removal refused: what binds to this variable is unknown, "
                                       "and an unknown is not an absence"}); continue
            if new_id in bound_variable_ids:
                skipped.append({"item": item, "target": new_id,
                                "why": "removal refused: values bind to this variable"}); continue
            p2["variables"] = [v for v in p2.get("variables") or [] if v.get("id") != new_id]
            applied.append({"item": item, "op": op, "target": new_id})
            sets = id_sets(structure)
            continue
        if op == "add_printed_as":
            # NOT A SENTENCE, AND NOT A NEW ID. The claim is "the paper prints
            # this variable under this label in a table", so the evidence is the
            # row labels the extractor read off the markup before any model saw
            # the table -- `Covariates | Externally funded` is not in the body
            # text and never will be. Both the LABEL and the QUOTE must be found
            # there, so the edit names the alias and where it is printed, and
            # neither is the model's word alone.
            var = next((v for v in p2.get("variables") or [] if v.get("id") == new_id), None)
            label = (e.get("label") or "").strip()
            if var is None:
                skipped.append({"item": item, "target": new_id,
                                "why": f"`{new_id}` is not a declared variable"}); continue
            if not label:
                skipped.append({"item": item, "target": new_id,
                                "why": "a printed label edit names no label"}); continue
            if printed_row_labels is None:
                skipped.append({"item": item, "target": new_id,
                                "why": "refused: what the tables print is unknown here, and an "
                                       "unknown is not a printing"}); continue
            for field in ("label", "quote"):
                got = (e.get(field) or "").strip()
                if not (_interpret.label_forms(got) & printed_row_labels):
                    skipped.append({"item": item, "target": new_id,
                                    "why": f"the {field} `{got[:60]}` is not a table row label the "
                                           "extractor read"})
                    break
            else:
                if label in (var.get("printed_as") or []):
                    skipped.append({"item": item, "target": new_id,
                                    "why": f"`{label}` is already a printed label of this variable"})
                else:
                    var.setdefault("printed_as", []).append(label)
                    applied.append({"item": item, "op": op, "target": new_id,
                                    "label": label, "quote": e.get("quote")})
            continue
        if not located(e.get("quote")):
            skipped.append({"item": item, "target": new_id,
                            "why": "an addition needs a verbatim quote located in the paper"}); continue
        if op == "add_study":
            if new_id in sets["studies"]:
                skipped.append({"item": item, "target": new_id, "why": "that study id already exists"}); continue
            p1.setdefault("studies", []).append({
                "id": new_id, "label": e.get("label") or new_id, "aim": e.get("why") or "",
                "section_heading": "", "reported_in": [], "design_type": "other",
                "design_description": e.get("why") or "", "n_range_printed": None,
                "n_range_quote": None, "n_scope": "not_stated", "groups": [], "phases": [],
                "outcomes_described": [], "manipulations_described": [],
                "result_summary_quotes": [], "interpretation_quotes": [], "procedure_ids": [],
                "added_by_adjudication": {"quote": e.get("quote"), "why": e.get("why")}})
        elif op == "add_variable":
            if new_id in sets["variables"]:
                skipped.append({"item": item, "target": new_id, "why": "that variable id already exists"}); continue
            if e.get("role") not in _schema.VARIABLE_ROLES or e.get("kind") not in _schema.VARIABLE_KINDS:
                skipped.append({"item": item, "target": new_id,
                                "why": "an added variable needs a role and a kind from the closed "
                                       f"vocabularies (got {e.get('role')!r}, {e.get('kind')!r})"}); continue
            p2.setdefault("variables", []).append({
                "id": new_id, "name": e.get("label") or new_id, "role": e["role"], "kind": e["kind"],
                "units": None, "units_source": "not_stated",
                # AN ADDED VARIABLE STARTS WITH NO BOUNDS AND NO GRANULARITY. Both
                # are premises a check consumes; supplying either here would let an
                # addition do what a correction may not (CLAUDE.md 8d, Rule 1).
                "bounds": {"lower": None, "upper": None, "source": "not_stated", "quote": None},
                "granularity": {"per_subject_step": None, "basis": None, "quote": None},
                "derivation": None, "derived_from": [], "procedure_id": None, "levels": [],
                "studies_using": [], "quote": e["quote"], "notes": e.get("why"),
                "added_by_adjudication": {"quote": e.get("quote"), "why": e.get("why")}})
        elif op == "add_level":
            parent = e.get("parent_variable_id")
            var = next((v for v in p2.get("variables") or [] if v.get("id") == parent), None)
            if var is None:
                skipped.append({"item": item, "target": new_id,
                                "why": f"`{parent}` is not a declared variable"}); continue
            if new_id in sets["levels"]:
                skipped.append({"item": item, "target": new_id, "why": "that level id already exists"}); continue
            var.setdefault("levels", []).append({
                "id": new_id, "label": e.get("label") or new_id, "value": None, "units": None,
                "added_by_adjudication": {"quote": e.get("quote"), "why": e.get("why")}})
        applied.append({"item": item, "op": op, "target": new_id, "quote": e.get("quote")})
        sets = id_sets(structure)
    return applied, skipped


# --------------------------------------------------------------------------
# what the account says about the structure it selected from
# --------------------------------------------------------------------------


def stale_document(structure: dict, doc: dict) -> dict | None:
    """The document served now against the one the structure was read from.

    NOTHING IS RE-DECOMPOSED HERE. A changed document is a fact about the run,
    reported with both hashes and the character counts by source, so a reader
    can see whether a supplement appeared (which is what happened between the
    D43 runs) or the article itself moved.
    """
    was = structure.get("document_sha256")
    now = (doc.get("source") or {}).get("text_sha256")
    if not was or not now or was == now:
        return None
    before, after = structure.get("document_chars") or {}, _document_chars(doc)
    files = sorted(set(before.get("supplements") or {}) | set(after.get("supplements") or {}))
    return {
        "document_sha256_in_structure": was,
        "document_sha256_now": now,
        "chars_in_structure": before,
        "chars_now": after,
        "changed_by_source": {
            "total": [before.get("total"), after.get("total")],
            "article": [before.get("article"), after.get("article")],
            **{f: [(before.get("supplements") or {}).get(f), (after.get("supplements") or {}).get(f)]
               for f in files},
        },
        "consequence": ("the structure was read from a different document; it was NOT "
                        "re-decomposed and nothing was re-read -- every id below is the "
                        "vocabulary of the earlier document"),
    }


def adjudication_counts(structure: dict) -> dict:
    """Applied / skipped / conflicts over the append-only audit."""
    rounds = structure.get("adjudication") or []
    return {"rounds": len(rounds),
            "applied": sum(int(r.get("n_applied") or 0) for r in rounds),
            "skipped": sum(int(r.get("n_skipped") or 0) for r in rounds),
            "conflicts": sum(int(r.get("n_conflicts") or 0) for r in rounds)}


def account_block(structure: dict, doc: dict, closed: dict | None = None) -> dict:
    """What section 1 of the account prints: which structure this account
    selected from, whether it is adjudicated, whether the document still
    matches, and what the closed vocabulary refused."""
    stale = stale_document(structure, doc)
    return {
        "schema_version": structure.get("schema_version"),
        "version": structure.get("version"),
        "status": structure.get("status"),
        "adjudicated": bool(structure.get("adjudication")),
        "frozen_at": structure.get("frozen_at"),
        "created_at": structure.get("created_at"),
        "sha256": content_sha256(structure),
        "document_sha256": structure.get("document_sha256"),
        "document_matches": stale is None,
        "stale_document": stale,
        "ids": id_counts(structure),
        "adjudication": adjudication_counts(structure),
        "closed_vocabulary": closed or {},
        "produced_by": structure.get("produced_by") or {},
    }
