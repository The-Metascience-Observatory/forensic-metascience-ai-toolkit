"""Detect supplementary material a paper relies on but that we do not have.

MEASURED: 83.2% of the high-value corpus (79 of 95 papers) references
supplementary material, and exactly ZERO of those supplements are on disk.
Corpus-wide it is 36.8% referenced, 1 present.

The pipeline already knows how to sweep an SI PDF -- `_si_pass_text()` builds a
whole prompt pass for it, and that prompt tells the model "SI studies often
carry the bulk of a paper's numeric claims -- do not skip them". But when no SI
file is found the function returns an empty string and the pass silently
disappears. So the analysis skips supplementary material in 100% of runs while
83% of papers point into it, and nothing in the output says so.

That is the difference between "we checked this paper" and "we checked the part
of this paper that happened to be in the directory". A reader has to be told
which one they are holding.

TWO WAYS THIS GATE WAS BLIND, both fixed here. It could not READ a PDF-only
paper (`paper_text` returned "" and no citation was ever found -- 97 of 97
corpus papers passed with 0 detected), and it accepted a file that was not
there (a zero-byte `paper_supplementary.pdf` satisfied `present_files`, which
matched on the filename alone). `missing` is now THREE-VALUED so the first
case can say so rather than answer "no".
"""

from __future__ import annotations

import json
import re
from pathlib import Path

#: Patterns are ordered most- to least- specific so a JAMA `eTable 3 in
#: Supplement 1` is reported as the eTable style rather than the generic one.
#: Frequencies are measured over the 400-paper corpus.
_PATTERNS: tuple[tuple[str, str], ...] = (
    ("eTable / eFigure (JAMA)", r"\be(?:Table|Figure|Appendix)\s*\d+"),
    ("Supplement N (JAMA)", r"\bin\s+Supplement\s+\d+"),
    ("Table S1 / Fig S1 style", r"\b(?:Table|Fig(?:ure)?)\.?\s*S\d+"),
    ("Supplementary Table/Figure", r"\bSupplement(?:ary|al)\s+(?:Table|Figure|Material|Data|File|Method|Text|Information|Appendix)"),
    ("Supporting Information", r"\bSupporting\s+Information\b"),
    ("Additional file N (BMC)", r"\bAdditional\s+file\s*\d+"),
    ("Appendix", r"\bAppendi(?:x|ces)\b"),
    ("Data supplement", r"\bdata\s+supplement\b"),
    ("available online", r"\bavailable\s+(?:online|as\s+supplementary)\b"),
)

#: Filenames that plausibly ARE the supplement, checked before warning.
_SI_HINTS = ("supp", "si_", "_si", "appendix", "additional", "esm", "smaterial")

#: A line that IS an appendix section heading — optionally `##`-prefixed
#: markdown, optionally titled ("Appendix A: study group"), but a line of its
#: own, which a running-prose citation ("see Appendix B for details of the
#: model, which…") is not.
_INLINE_APPENDIX = re.compile(
    r"^\s*(?:#{1,6}\s*)?Appendi(?:x|ces)\b[^\n]{0,60}$",
    re.IGNORECASE | re.MULTILINE,
)


#: A mention sitting next to one of these is the paper DENYING a supplement, not
#: citing one. Deliberately NOT an attempt to enumerate every negation -- that
#: approach failed on `artefacts.preregistration`, where a closed list still let
#: "Neither study was preregistered" through. Its job here is narrower and
#: safer: it decides only whether a mention counts as POSITIVE evidence of
#: dependence, and an unrecognised negation therefore falls back to the
#: conservative reading (treat as a citation, gate refuses), never to the
#: dangerous one.
_DENIAL_NEAR = re.compile(
    r"\b(?:no|not|none|neither|nor|without|absent|lack(?:s|ing)?|"
    r"un(?:available|necessary)|did\s+not|does\s+not|do\s+not|"
    r"was\s+not|were\s+not|is\s+not|are\s+not|has\s+not|have\s+not)\b",
    re.I)

#: THE NEGATION MUST GOVERN THE SUPPLEMENT, not merely share a clause with it.
#: `_DENIAL_NEAR` alone asks "is there a negation nearby", and MEASURED over the
#: 105-paper working corpus it produced 15 denials of which ALL FIFTEEN were
#: false -- every one a genuine citation sitting beside an unrelated negation:
#: a finding ("there was no association (Table 3, Table S1)"), a Likert level
#: ("'definitely not true' (eFigure 2)"), a variable value ("and no religion
#: (Table S4)"), a sample description ("participants who were not disenrolled
#: (online supplemental figure 1)"), and twice our OWN inserted placeholder
#: "(no section heading in the XML)". Zero true denials. That is the direction
#: `mention_context` calls dangerous: the gate then proceeds on a paper that
#: really does depend on a supplement we do not hold.
#:
#: So a denial now has to take one of two shapes, both of which put the
#: supplement itself under the negation:
#:   1. the negation immediately precedes the mention, with nothing but
#:      determiners and adjectives between -- "No supplementary material",
#:      "no such supplementary table";
#:   2. a PROVISION verb in the clause is negated -- "not provided", "were not
#:      included", "did not prepare", "none were deposited". What is being
#:      denied is the supplying of the thing, which is what we are asking.
#: A negated verb of any other kind ("did not increase", "no religion") no
#: longer denies anything.
_DENIAL_BEFORE = re.compile(
    r"\b(?:no|not|none|neither|without|lack(?:s|ing)?\s+(?:of\s+)?)\s+"
    r"(?:(?:such|any|other|further|additional|separate|accompanying|"
    r"online|associated|relevant)\s+){0,3}$", re.I)
_DENIAL_PROVISION = re.compile(
    r"\b(?:(?:is|are|was|were|has|have|had|will|would|be|been|"
    r"did|do|does|and|or|,)\s+)?"
    r"(?:no|not|none|neither|nor|never)\b[^.;]{0,40}?"
    r"\b(?:provid\w*|availab\w*|includ\w*|prepar\w*|deposit\w*|"
    r"submit\w*|suppli\w*|attach\w*|publish\w*|access\w*|"
    r"upload\w*|shar\w*|report\w*\s+(?:here|separately))\b", re.I)


def _denies(context: str, mention: str) -> bool:
    """Does `context` deny the supplement `mention`, rather than merely sit
    near a negation? See `_DENIAL_BEFORE` / `_DENIAL_PROVISION` for the two
    shapes and the 15 false denials that forced the narrowing."""
    ctx = context or ""
    i = ctx.lower().find((mention or "").lower())
    if i >= 0 and _DENIAL_BEFORE.search(ctx[:i]):
        return True
    return bool(_DENIAL_PROVISION.search(ctx))


#: How far either side of a mention to look for a denial. 60 characters catches
#: "No supplementary material is provided" and "we did not prepare any
#: supplementary tables" without reaching into an unrelated neighbouring clause.
_DENIAL_WINDOW = 60


#: Clause boundaries. A denial in a DIFFERENT clause is about something else.
_CLAUSE_EDGE = re.compile(r"[.;]")


def mention_context(text: str, match_start: int, match_end: int) -> str:
    """The clause a mention sits in, for both the check and the reader.

    BOUNDED BY CLAUSE, NOT JUST BY DISTANCE, and the first version was not.
    A plain 60-character window on "See Supplementary Table 1; no supplementary
    code is provided." reached across the semicolon, found the "no", and
    classified a GENUINE CITATION as a denial. That is the dangerous direction:
    the gate would then proceed on a paper that really does depend on a
    supplement we do not hold, and findings of the form "not reported" become
    artefacts of our own misreading.

    So the window is clipped at the nearest `.` or `;` on each side. A denial
    has to share a clause with the mention it denies.
    """
    text = text or ""
    lo = max(0, match_start - _DENIAL_WINDOW)
    hi = min(len(text), match_end + _DENIAL_WINDOW)
    left = text[lo:match_start]
    edges = list(_CLAUSE_EDGE.finditer(left))
    if edges:
        lo = lo + edges[-1].end()
    right = text[match_end:hi]
    edge = _CLAUSE_EDGE.search(right)
    if edge:
        hi = match_end + edge.start()
    return " ".join(text[lo:hi].split())


def classify_mentions(text: str) -> dict:
    """Every supplement mention, WITH the sentence around it and whether that
    sentence denies rather than cites.

    THE LOCATOR NOW CARRIES ITS EVIDENCE. `find_references` returned bare
    matched strings, so `audit` could count them and `gate` could refuse a paid
    run on the count -- with no way for anything downstream to see that the
    matched string sat inside "No supplementary material is provided for this
    article." VERIFIED 2026-08-18: that sentence yields
    {'Supplementary Table/Figure': ['supplementary material']}, the paper is
    judged to depend on a supplement we do not hold, and `gate` returns
    proceed=False -- a hard refusal, exit 2, for saying it has none.

    Returns `{"cited": [...], "denied": [...]}`, each entry
    `{style, text, context}`.
    """
    cited: list[dict] = []
    denied: list[dict] = []
    # CARRIED OVER FROM `find_references` AT THE 2026-08-18 MERGE. Dan added the
    # inline-appendix suppression there, and `audit` had just been moved off
    # that function onto this one -- so without this line the merge would have
    # kept his code and silently lost its effect, which is the worst kind of
    # reconciliation. An appendix printed in the paper is not a supplement we
    # lack, whichever function is asking.
    inline_appendix = bool(_INLINE_APPENDIX.search(text or ""))
    for label, pattern in _PATTERNS:
        if label == "Appendix" and inline_appendix:
            continue
        for m in re.finditer(pattern, text or "", flags=re.IGNORECASE):
            ctx = mention_context(text, m.start(), m.end())
            entry = {"style": label,
                     "text": " ".join(m.group(0).split()),
                     "context": ctx}
            (denied if _denies(ctx, entry["text"]) else cited).append(entry)
    return {"cited": cited, "denied": denied}


def find_references(text: str) -> dict[str, list[str]]:
    """Return {style: [matched strings]} for every supplement reference found.

    KEPT AS A PURE LOCATOR. It answers "where is the word", which is what a
    screen should do; `classify_mentions` is what answers "does this paper
    depend on a supplement", and `audit` uses that instead.

    An appendix PRINTED IN THE PAPER is not supplementary material we lack.
    10.1007--s00702-004-0248-2 says "See Appendix for a listing of the members
    of the Cerebrolysin Study Group" and then prints that appendix in the main
    text, two sections above the references — yet the bare-word pattern read
    the mention as a citation of an external file, no provider (correctly)
    listed one, and the gate refused a complete paper as incomplete. So when
    the text contains an appendix section heading, the generic "Appendix"
    style is suppressed: the cited material is IN the text we are searching.
    Every other style still fires independently — "eAppendix 2", "Table S1"
    and a NEJM-style "Supplementary Appendix" name external artifacts, and an
    inline appendix is no evidence about those.
    """
    inline_appendix = bool(_INLINE_APPENDIX.search(text or ""))
    found: dict[str, list[str]] = {}
    for label, pattern in _PATTERNS:
        if label == "Appendix" and inline_appendix:
            continue
        hits = re.findall(pattern, text or "", flags=re.IGNORECASE)
        if hits:
            # Preserve order, drop duplicates, cap so a report stays readable.
            seen, uniq = set(), []
            for h in hits:
                k = re.sub(r"\s+", " ", h).strip().lower()
                if k not in seen:
                    seen.add(k)
                    uniq.append(re.sub(r"\s+", " ", h).strip())
            found[label] = uniq[:12]
    return found


#: The signature each container format carries. A file whose NAME says `.xlsx`
#: and whose bytes say otherwise is not a supplement we hold, however
#: convincingly it is spelled -- the common case being an HTML paywall or error
#: page saved under the download's filename. `.csv` has no signature and is
#: checked on size and readability alone.
_MAGIC: dict[str, bytes] = {
    ".pdf": b"%PDF",
    ".docx": b"PK",
    ".xlsx": b"PK",
    ".zip": b"PK",
}

#: How far in to look for it. The signature is normally at byte 0, but the PDF
#: spec only requires the header within the first 1 kB and some producers emit
#: a preamble. Searching rather than anchoring errs toward ACCEPTING a real
#: file: a false refusal here costs an operator a puzzling message about a
#: supplement they can see on disk, and this check exists to catch empty
#: placeholders and HTML error pages, both of which fail it either way.
_MAGIC_WINDOW = 1024


def _unusable_because(p: Path) -> str:
    """Why this file cannot count as a supplement we hold, or "" if it can.

    A NAME is not a file. `present_files` matched on the filename alone, so a
    zero-byte `paper_supplementary.pdf` -- exactly what an interrupted download,
    a failed `touch`, or a git-lfs pointer that was never pulled leaves behind
    -- satisfied the gate and the analysis proceeded as though the SI had been
    read. That is the same failure the gate exists to prevent, arriving through
    the one door the gate does not watch: the run then reports "not reported"
    findings that are artefacts of an empty file, and they land as accusations
    against the authors.
    """
    try:
        size = p.stat().st_size
    except OSError as exc:
        return f"could not be read ({exc.strerror or exc})"
    if size == 0:
        return "is zero bytes -- an empty placeholder, not a supplement"
    try:
        with p.open("rb") as handle:
            head = handle.read(_MAGIC_WINDOW)
    except OSError as exc:
        return f"could not be opened ({exc.strerror or exc})"
    if not head:
        return f"reads back empty despite a size of {size} bytes"
    expected = _MAGIC.get(p.suffix.lower())
    if expected and expected not in head:
        return (f"carries no {p.suffix} file signature, so it is not the "
                "format its name claims")
    if p.suffix.lower() in _UNREADABLE_SUFFIXES:
        return (f"is a real {p.suffix} file that no reader in "
                "`extraction.supplements_read` can open, so its contents are "
                "held but unread")
    return ""


#: Formats a supplement can arrive as. TWO SETS, because the census must
#: distinguish a file we cannot read from a file that is not there -- which is
#: the rule the `undeclared` branch below already states in its own `why`, and
#: which a bare suffix filter breaks by SKIPPING the file entirely.
#:
#: MEASURED 2026-09-05 on Stern 2014 (`10.1038/npp.2014.69`). The fetcher pulled
#: nine real supplementary files -- four .ppt, four .jpg, one .doc -- and
#: `classify_inputs` reported "1 readable file(s): 1 article, 0 supplementary".
#: Not unusable, not undeclared: INVISIBLE, because none of those suffixes was
#: listed here. The .doc is Supplementary Table S1, "Summary of statistics",
#: carrying 68 F statistics with degrees of freedom and 92 p values. So a person
#: could fetch every supplement correctly and still be told the paper has none.
#:
#: The read set is imported rather than restated: a second copy of a format list
#: is how `_IMAGE_SUFFIXES` came to exist three ways and a .tif figure recorded
#: as "never opened".
from .extraction.supplements_read import READABLE as _READABLE_SUFFIXES

#: Formats we can SEE but not READ. Legacy Office binaries and slide decks: the
#: reader has no branch for them, so they are reported as held-and-unreadable
#: rather than silently dropped. Widening this set costs nothing and can make
#: nothing checkable -- it only ever moves a file from invisible to named.
_UNREADABLE_SUFFIXES = {".doc", ".ppt", ".pptx", ".rtf", ".odt", ".ods", ".odp"}

_DOC_SUFFIXES = _READABLE_SUFFIXES | _UNREADABLE_SUFFIXES | {".zip", ".xls"}

#: The operator's declaration, written next to the paper. This file is the
#: authority; everything else in this module is bookkeeping around it.
INPUTS_FILE = "inputs.json"

ROLES = ("article", "supplement", "dataset", "ignore")


def read_declaration(paper_dir: str | Path) -> dict:
    """What the OPERATOR said each file is. `{}` when nothing was declared.

    Greg, 2026-08-13: "The detection of supplements shouldn't be contingent on
    the file naming... this is something the model shouldn't have to deal with.
    The user (or the agent they're interfacing with to use the CLI) should have
    to provide these, and specify."

    That is the right split, and the alternative was measured the same day. The
    old gate accepted a file only if its name contained one of seven substrings.
    Wiley calls its supplement `EAT-58-1072-s001.docx`; none of the seven
    appears in it; the file was skipped so quietly that it reached NEITHER the
    usable nor the unusable list, `problems` stayed empty, and the run reported
    no supplement for a paper whose supplement was in its own directory holding
    7 tables and 99 checkable cells. Of nine real publisher conventions the hint
    list matched four -- it missed Wiley `-s001`, Elsevier `mmc1`, PLOS
    `S1_Table` and `.s001`, and JAMA `-s001` -- and a hint list is always one
    publisher behind.

    So nothing here guesses. Roles are declared, `metascience inputs` writes the
    declaration, and a file nobody declared is REPORTED as undeclared rather
    than silently dropped.
    """
    p = Path(paper_dir) / INPUTS_FILE
    if not p.is_file():
        return {}
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        # NOT AN EMPTY DECLARATION. A corrupt `inputs.json` returned `{}` here,
        # which is byte-identical to "the operator declared nothing" -- so a
        # typo in the one file that carries the operator's intent would have
        # silently reverted the whole directory to undeclared. `_error` travels
        # with it and `classify_inputs` puts it in front of the reader.
        return {"_error": f"{Path(paper_dir).name}/{INPUTS_FILE} could not be "
                          f"read ({type(exc).__name__}: {exc}), so nothing you "
                          "declared is in force"}
    return d if isinstance(d, dict) else {
        "_error": f"{Path(paper_dir).name}/{INPUTS_FILE} is not a JSON object, "
                  "so nothing you declared is in force"}


def declared_by_article(paper_dir: str | Path) -> dict[str, str]:
    """{lowercased filename: role} from the fetch record. Not a guess either.

    Second authority after the operator, and it draws on two things the record
    already holds:

      * the JATS `<supplementary-material>` elements, which NAME THEIR OWN
        FILES -- under `declared`, including ones the fetch then failed to
        download. On the paper that exposed this bug the record already held
        `eat-58-1072-s001.docx`, so the fact was present all along and only the
        filename gate stood between it and the run.
      * the files the FETCHER ITSELF wrote, each carrying its saved `filename`
        and an explicit `role`. Recognising our own output is bookkeeping, not
        inference -- and the saved names are mangled to
        `<stem>_supplementary_info_N_<original>`, which no publisher convention
        and no hint list would ever match.
    """
    out: dict[str, str] = {}
    # THE RAW RECORD, not `retrieval_record`. That function reshapes the file
    # for a reader and drops `declared` entirely, so reading it there returned
    # nothing and the article's own authority never reached the classifier --
    # the same "wired to the wrong end" defect this session keeps finding.
    rec: dict = {}
    try:
        for f in sorted(Path(paper_dir).glob("*_supplementary_info.json")):
            loaded = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                rec = loaded
            break
    except Exception:  # noqa: BLE001
        return out
    decl = rec.get("declared")
    if isinstance(decl, dict):
        for key in ("missing", "obtained_names", "names"):
            for n in (decl.get(key) or []):
                if n:
                    out[Path(str(n)).name.lower()] = "supplement"
    for f in (rec.get("files") or []):
        if not isinstance(f, dict):
            continue
        role = str(f.get("role") or "supplement")
        if role not in ROLES:
            role = "supplement"
        for key in ("filename", "original_name", "name"):
            n = f.get(key)
            if n:
                out[Path(str(n)).name.lower()] = role
    return out


def _fetched_under_a_mangled_name(
    filename: str, stem: str, by_article: dict[str, str],
) -> tuple[str, str] | None:
    """`(role, declared_as)` when this file is OUR OWN download of a declared one.

    RECOGNISING OUR OUTPUT IS BOOKKEEPING, NOT INFERENCE -- the same principle
    `declared_by_article` states -- but that function could only match a record
    name against itself, and the fetcher does not save files under the names it
    records. It has more than one mangling:

        <stem>_supplementary_info_<N>_<original>
        <stem>_linked_data_<repo>_<id>_<original>

    Only the first was ever anticipated, and `declared_by_article` matched
    neither: it keys on the record's OWN basename (`ESCAS.xlsx`), which no saved
    file is called.

    FOUND ON A REAL PAPER, 2026-08-19. `10.1161--strokeaha.124.049834` was
    refused as "supplement missing" while
    `10.1161--strokeaha.124.049834_linked_data_dataverse_Z8WAKW_ESCAS.xlsx` sat
    in its directory -- byte-identical (same md5) to the file the record
    declares. The fetcher had downloaded it on 12 August and this module could
    not see it. That is this repository's own worst failure mode, asserted
    about a paper: absence claimed where there is presence, and a whole analysis
    refused over it.

    The rule is deliberately narrow. A file qualifies only if it BEGINS with
    this paper's stem -- so it is a file we wrote, not one that merely happens
    to end in the same word -- and ENDS with `_<declared basename>`. A bare
    suffix test would let `data.xlsx` claim `raw_data.xlsx`, and a guessed role
    is exactly what the three-authority rule exists to prevent.
    """
    if not stem or not filename.startswith(stem + "_"):
        return None
    best: tuple[str, str] | None = None
    for declared, role in by_article.items():
        if not declared or not filename.endswith("_" + declared):
            continue
        # The LONGEST declared name wins, so `s001.pdf` cannot outrank
        # `str-47-151-s001.pdf` when a record declares both.
        if best is None or len(declared) > len(best[1]):
            best = (role, declared)
    return best


def classify_inputs(paper_dir: str | Path) -> dict:
    """Every readable file in the directory, its role, and WHO SAID SO.

    Three authorities, and no inference below them:

      `operator`        `inputs.json`, written by `metascience inputs`. Wins
                        outright -- it is the only source that can be right
                        about a file nothing else describes.
      `article`         the paper's own supplementary-material list, via the
                        fetch record.
      `doi_stem`        the article file itself, which the fetcher named for the
                        DOI. Bookkeeping, not a judgement.

    Anything else is `undeclared`, and that is a REPORTED STATE, not a skip. A
    file we passed over looks exactly like a file that does not exist, and this
    module exists because that confusion once cost a whole supplement.
    """
    base = Path(paper_dir)
    if not base.is_dir():
        return {"files": [], "supplements": [], "datasets": [],
                "undeclared": [], "unusable": [],
                "note": "no such directory"}

    decl = read_declaration(base)
    problems: list[str] = [decl["_error"]] if decl.get("_error") else []
    by_operator: dict[str, str] = {}
    for role in ROLES:
        for n in (decl.get(role + "s") or ([decl[role]] if decl.get(role) else [])):
            by_operator[Path(str(n)).name.lower()] = role
    by_article = declared_by_article(base)
    stem = base.name.lower()

    files, supplements, datasets, undeclared, unusable = [], [], [], [], []
    for p in sorted(base.iterdir()):
        if not p.is_file() or p.suffix.lower() not in _DOC_SUFFIXES:
            continue
        low = p.name.lower()
        row: dict = {"name": p.name}

        role = by_operator.get(low)
        source = "operator"
        if role is None:
            if p.stem.lower() == stem:
                role, source = "article", "doi_stem"
            elif low in by_article:
                role, source = by_article[low], "article"
            else:
                fetched = _fetched_under_a_mangled_name(low, stem, by_article)
                if fetched:
                    role, source = fetched[0], "fetcher"
        if role is None:
            row.update(role="undeclared", declared_by=None,
                       why="nobody has said what this file is. Declare it with "
                           "`metascience inputs` -- it is listed here rather "
                           "than skipped, because a file we passed over is "
                           "indistinguishable from one that is not there.")
            undeclared.append(p.name)
            files.append(row)
            continue

        # A NAME IS NOT A FILE, whoever declared it. A zero-byte placeholder --
        # an interrupted download, an unpulled git-lfs pointer -- used to
        # satisfy the old gate, and the analysis proceeded as though the SI had
        # been read.
        bad = _unusable_because(p)
        if bad and role != "ignore":
            row.update(role="unusable", declared_by=source, why=bad)
            unusable.append({"name": p.name, "reason": bad})
            files.append(row)
            continue

        row.update(role=role, declared_by=source,
                   why=_ROLE_WHY.get((role, source), f"declared {role}"))
        if role == "supplement":
            supplements.append(p.name)
        elif role == "dataset":
            datasets.append(p.name)
        files.append(row)

    note = _classify_note(files, supplements, datasets, undeclared, unusable,
                          bool(decl) and not decl.get("_error"))
    if problems:
        note = " ".join(problems) + " " + note
    return {"files": files, "supplements": supplements, "datasets": datasets,
            "undeclared": undeclared, "unusable": unusable,
            "problems": problems,
            "declaration_present": bool(decl) and not decl.get("_error"),
            "note": note}


_ROLE_WHY = {
    ("article", "doi_stem"): "named for the article's own DOI stem",
    ("supplement", "article"): ("the article's own supplementary-material list "
                                "names this file"),
    ("supplement", "fetcher"): ("our own fetcher downloaded this for a file the "
                                "article declares, and saved it under a mangled "
                                "name"),
    ("dataset", "fetcher"): ("our own fetcher downloaded this for a dataset the "
                             "article declares, and saved it under a mangled "
                             "name"),
    ("supplement", "operator"): "declared a supplement by the operator",
    ("dataset", "operator"): ("declared raw data by the operator: a duplication "
                              "sweep consumes it, a table check does not"),
    ("article", "operator"): "declared the article by the operator",
    ("ignore", "operator"): "declared not part of this paper by the operator",
}


def _classify_note(files, supplements, datasets, undeclared, unusable,
                   have_decl) -> str:
    if not files:
        return "No readable document files in this directory."
    n_art = sum(1 for f in files if f["role"] == "article")
    # "readable" was the wrong word once `_DOC_SUFFIXES` widened to cover
    # formats we can hold but not open: it counted every file in the census,
    # unreadable ones included, and then a later sentence called some of them
    # unreadable. Say what the number is.
    head = (f"{len(files)} document file(s) found: {n_art} article, "
            f"{len(supplements)} supplementary, {len(datasets)} raw data.")
    if not have_decl:
        head += (" No `inputs.json`, so every role above came from the article "
                 "or the DOI stem rather than from you.")
    if unusable:
        # SPLIT BY CAUSE. A file that is the wrong format or empty is a broken
        # download; a .doc or .ppt is intact and simply has no reader. Reporting
        # both as "empty, or not the format its name claims" told an operator
        # holding a perfectly good Supplementary Table S1 that their file was
        # corrupt -- and pointed the fix at the download rather than at us.
        no_reader = [u for u in unusable
                     if "no reader in" in str((u or {}).get("reason", ""))]
        n_broken = len(unusable) - len(no_reader)
        if n_broken:
            head += (f" {n_broken} file(s) declared but unreadable -- empty, or "
                     "not the format its name claims.")
        if no_reader:
            head += (f" {len(no_reader)} file(s) held but UNREAD: an intact "
                     f"{', '.join(sorted({Path(u['name']).suffix for u in no_reader}))}"
                     " that no reader in `extraction.supplements_read` opens.")
    if undeclared:
        return (head + f" {len(undeclared)} FILE(S) ARE UNDECLARED and were not "
                "used. Run `metascience inputs <dir>` to say what each one is; "
                "until then the coverage figures describe a paper missing those "
                "files, and nothing in the report can tell that from a paper "
                "that never had them.")
    return head


def write_declaration(paper_dir: str | Path, **roles) -> dict:
    """Record what the operator says each file is. Returns the declaration.

    Merges: declaring a supplement does not un-declare the article.
    """
    base = Path(paper_dir)
    cur = read_declaration(base) or {"schema_version": 1}
    for role in ROLES:
        key = role + "s"
        given = roles.get(key) or roles.get(role)
        if not given:
            continue
        names = [given] if isinstance(given, str) else list(given)
        merged = list(dict.fromkeys(
            list(cur.get(key) or []) + [Path(str(n)).name for n in names]))
        cur[key] = merged
    (base / INPUTS_FILE).write_text(json.dumps(cur, indent=2) + "\n",
                                    encoding="utf-8")
    return cur


def _scan(paper_dir: Path) -> tuple[list[str], list[dict]]:
    """Supplementary files, split into the usable and the not.

    Kept as the shape its callers expect; the decision lives in
    `classify_inputs`. Raw-data files come through too -- a duplication sweep is
    a check like any other, and excluding them here was how a 7,738-cell
    dataset became invisible to the coverage figures.
    """
    if not paper_dir.is_dir():
        return [], []
    c = classify_inputs(paper_dir)
    return list(c["supplements"]) + list(c["datasets"]), list(c["unusable"])


def present_files(paper_dir: Path) -> list[str]:
    """Files in the paper directory that ARE supplementary material -- by
    declaration, never by name -- AND are actually there: non-zero, openable,
    and of the format they claim."""
    return _scan(paper_dir)[0]


#: fetchpdf's linked-deposit folder: `<stem>_data_artifacts/<deposit>/<file>`
#: (`fetchpdf.retrieval.supplementary.DATA_ARTIFACT_INFIX`). A suffix match,
#: because the stem is fetchpdf's encoding of the DOI, which is not always
#: this toolkit's `doi_dirname`.
DATA_ARTIFACT_INFIX = "_data_artifacts"

#: What a review takes from a deposit: tables and documents, plus the formats
#: it must NAME as unreadable (`.xls`, `.zip`, `.doc`) rather than pass over.
#: Images, code and READMEs are left out on purpose -- a deposit can hold 199
#: members of a vendored Stata package or a thousand microscopy TIFFs, and
#: each image here would be sent to OCR and named in the analysts' prompt.
DATA_ARTIFACT_SUFFIXES = frozenset({
    ".pdf", ".docx", ".xlsx", ".xlsm", ".csv", ".tsv",
    ".xls", ".zip", ".doc"})

#: Most deposit files one review takes. The rest are counted, not dropped
#: silently: `data_artifact_files` returns how many were left out.
MAX_DATA_ARTIFACT_FILES = 50


def data_artifact_files(paper_dir: str | Path) -> tuple[list[Path], int]:
    """Files fetchpdf downloaded from the paper's linked data deposits.

    Returns `(files, n_left_out)`: the analysable ones under every
    `*_data_artifacts/` folder at the top of `paper_dir`, sorted, hidden files
    excluded, capped at `MAX_DATA_ARTIFACT_FILES`; and how many more matched
    the cap left out. The ONE scan for these folders -- the source resolver and
    the raw-data module both read it, so they cannot disagree about which
    deposit files a run had.
    """
    base = Path(paper_dir)
    if not base.is_dir():
        return [], 0
    found: list[Path] = []
    for folder in sorted(base.glob(f"*{DATA_ARTIFACT_INFIX}")):
        if not folder.is_dir():
            continue
        for p in sorted(folder.rglob("*")):
            rel = p.relative_to(folder)
            if (p.is_file() and p.suffix.lower() in DATA_ARTIFACT_SUFFIXES
                    and not any(part.startswith((".", "~$", "__MACOSX"))
                                for part in rel.parts)):
                found.append(p)
    return found[:MAX_DATA_ARTIFACT_FILES], max(0, len(found) - MAX_DATA_ARTIFACT_FILES)


def _scan_supplied(extra) -> tuple[list[str], list[dict]]:
    """The same usability verdict as `_scan`, for files named on the command line.

    A SUPPLIED FILE IS NOT A TRUSTED FILE. `--supplement` used to bypass this
    check completely -- the CLI tested `.exists()` and nothing else -- so a
    zero-byte `etable.xlsx` passed a gate that the identical file sitting IN the
    paper directory is refused by. That is the gate's own override defeating the
    gate's own defence, and the failure it lets through is the one the module
    exists to stop: a run that reports "not reported" against authors because
    our copy of their supplement was an empty placeholder.

    Two differences from `_scan`, both deliberate. There is no `_SI_HINTS`
    filter -- the operator naming a file IS the assertion that it is the
    supplement, and a file called `etable3.xlsx` should not be silently ignored
    for failing a filename heuristic. And there is no suffix filter, because
    `extract_supplement` reads formats `_scan` does not list; whether we can
    parse it is that function's answer to give, not this one's.
    """
    usable: list[str] = []
    unusable: list[dict] = []
    for p in extra or []:
        p = Path(p)
        reason = _unusable_because(p) if p.is_file() else "is not a file"
        if reason:
            unusable.append({"name": p.name, "reason": reason})
        else:
            usable.append(str(p))
    return usable, unusable


#: The fetcher's skip codes, in a sentence. These are bare slugs in the record
#: -- `duplicate-of` is not even a phrase, and a reader met it under a heading
#: reading "why it failed" with nothing to say what it was a duplicate OF. The
#: vocabulary is small and closed; measured across every archived record here,
#: it is exactly these four.
SKIP_REASONS = {
    "duplicate-of": ("Not a failure. The same file had already been obtained "
                     "from another provider, so this copy was skipped."),
    "no-bundle": ("The provider offers no supplement bundle at that address. "
                  "It may still publish the files individually."),
    "not-a-document": ("What came back was not a document we can read -- an "
                       "error page or an image, not a file with content."),
    "empty": "The download completed and the file had no content.",
}


def retrieval_record(paper_dir: str | Path) -> dict:
    """Read the fetcher's `*_supplementary_info.json`, and refuse to let its
    `status` speak for the paper.

    The fetcher writes `"status": "none_found"` for two situations that are
    OPPOSITE facts:

      * every provider was queried and none lists a supplement -- positive
        evidence that there is nothing to obtain; and
      * a provider DID list a file and our download of it failed.

    MEASURED over every fetch record in this repository: of 5 saying
    `none_found`, **3 had a provider list a file we then failed to fetch** (all
    three EuropePMC bundle URLs, HTTP 404 `no-bundle`). Only 2 were true
    negatives. So the majority of `none_found` verdicts are OUR retrieval
    failure wearing the grammar of a fact about the paper -- the same defect
    class as `_page_ink` blaming a decoder failure on the document.

    The distinction is not academic: it decides what the operator should DO.
    "Nobody publishes one" means `--ok-if-supplementary-missing` is the honest route.
    "We failed to download the one that exists" means retry or fetch it by
    hand, and running without it would discard a file that is actually there.

    Returns `{"present": False}` when no record exists -- which is a third
    state again, and must not be read as either of the other two.
    """
    paper_dir = Path(paper_dir)
    if not paper_dir.is_dir():
        return {"present": False, "verdict": "no_record"}
    records = sorted(paper_dir.glob("*_supplementary_info.json"))
    if not records:
        return {"present": False, "verdict": "no_record"}
    try:
        d = json.loads(records[0].read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        # An unreadable record is not evidence of anything. Say so rather than
        # falling through to a verdict.
        return {"present": False, "verdict": "unreadable_record", "error": str(exc)}

    providers = d.get("providers") or []
    skipped = d.get("skipped") or []
    obtained = d.get("files") or []
    listed = [p for p in providers if (p.get("listed") or 0) > 0]

    # A SKIP IS NOT A FAILURE, and 74% of them are not.
    #
    # The fetcher asks several providers for the same paper, so the same file
    # arrives more than once and every copy after the first is skipped with
    # `duplicate-of` -- which is the fetcher WORKING. All of `skipped` was
    # published as `failures` under the heading "why it failed", so the
    # de-duplications read as download errors.
    #
    # MEASURED across every archived retrieval record here: 43 skips, of which
    # 32 (74%) are `duplicate-of`. On 10.1038/s41537-025-00576-3 the page listed
    # six failures and the true number was zero -- all three files were
    # obtained. Same defect class as `_page_ink` blaming a decoder failure on
    # the document: our own bookkeeping reported as an adverse fact.
    def _row(s: dict) -> dict:
        # `detail` is the provider's own words. It is the only thing that tells
        # a licence refusal apart from a plain 404 on the same skip code, so it
        # is carried through rather than collapsed into our slug.
        return {"provider": s.get("provider"), "name": s.get("original_name"),
                "url": s.get("url"), "reason": s.get("reason"),
                "http": s.get("status"), "detail": s.get("detail"),
                "explanation": SKIP_REASONS.get(str(s.get("reason") or ""), "")}

    duplicates = [_row(s) for s in skipped if s.get("reason") == "duplicate-of"]
    failures = [_row(s) for s in skipped if s.get("reason") != "duplicate-of"]

    # A LICENCE WALL IS NOT A FETCH FAILURE, and telling them apart changes what
    # the operator should do. Europe PMC answers its supplement-bundle endpoint
    # for ANY PMCID, and for a subscription article it returns
    # `<errMsg>Article with id PMCnnnn is not open access one</errMsg>`. The
    # supplement almost certainly exists; it is simply not ours to download.
    # Reported as `retrieval_failed` it reads as "retry", which will never work.
    #
    # MEASURED 2026-08-11 over a fresh 15-paper fetch: 7 `no-bundle` skips, of
    # which 3 carry that licence message and 4 are a bare 404.
    def _is_walled(f: dict) -> bool:
        return (f.get("reason") == "no-bundle"
                and "not open access" in str(f.get("detail") or "").lower())

    walled = [f for f in failures if _is_walled(f)]

    # ...AND A CONSTRUCTED URL IS NOT A LISTING. The fetcher names a bundle
    # `{PMCID}_SupplementaryFiles.zip` from the PMCID alone, before knowing one
    # exists, and reports `listed: 1` for it. Treating that as "a provider
    # listed a file we then failed to fetch" sends an operator hunting for a
    # file nothing ever claimed was there -- our own optimism reported as an
    # adverse fact, the same defect class as `_page_ink`. A bare 404 on that
    # constructed address is evidence of ABSENCE, not of our failure.
    speculative = [f for f in failures
                   if f.get("reason") == "no-bundle" and not _is_walled(f)]
    real_failures = [f for f in failures
                     if f.get("reason") != "no-bundle"]

    if obtained:
        verdict = "obtained"
    elif walled:
        verdict = "not_open_access"
    elif real_failures:
        verdict = "retrieval_failed"
    elif d.get("status") == "none_found" or speculative:
        verdict = "nothing_published"
    elif listed:
        verdict = "retrieval_failed"
    else:
        verdict = "unknown"

    return {
        "present": True,
        "verdict": verdict,
        "reported_status": d.get("status"),
        "providers_queried": len(providers),
        "n_obtained": len(obtained),
        "listed_by": [p.get("name") for p in listed],
        "failures": real_failures,
        "not_open_access": walled,
        "speculative_addresses": speculative,
        "duplicates": duplicates,
        "record_file": records[0].name,
    }


def retrieval_sentence(rec: dict) -> str:
    """One line stating what we know, with the agent of any failure named.

    Never says "no supplementary material exists" on the strength of a
    `none_found` we did not earn.
    """
    v = (rec or {}).get("verdict")
    if v == "not_open_access":
        who = ", ".join(sorted({str(f.get("provider"))
                                for f in rec.get("not_open_access") or []}))
        return (f"A supplement exists but {who or 'the provider'} will not serve "
                "it to us: the article is not open access. This is a licence "
                "wall, not a download that failed and not evidence the authors "
                "published nothing -- retrying will never work. Get it from the "
                "publisher or a library, or run without it and say so.")
    if v == "nothing_published":
        spec = rec.get("speculative_addresses") or []
        extra = ("" if not spec else
                 " (one provider was asked at an address built from the PMCID "
                 "alone and returned nothing, which is an absence rather than a "
                 "listing we failed to fetch)")
        return (f"We queried {rec['providers_queried']} providers and none lists "
                "supplementary material for this paper, so there is likely nothing "
                f"to obtain{extra}.")
    if v == "retrieval_failed":
        bits = []
        for f in rec.get("failures") or []:
            http = f" HTTP {f['http']}" if f.get("http") else ""
            bits.append(f"{f.get('name') or 'a file'} via {f.get('provider')}"
                        f" ({f.get('reason')}{http})")
        listed = ", ".join(rec.get("listed_by") or []) or "a provider"
        detail = ("; ".join(bits)) or "the download did not complete"
        return (f"A supplement WAS listed by {listed}, and OUR retrieval of it "
                f"failed: {detail}. The file may well exist -- this is our "
                "failure to fetch it, not evidence the authors published none.")
    if v == "obtained":
        return f"The fetcher obtained {rec['n_obtained']} supplementary file(s)."
    if v == "unreadable_record":
        return "A retrieval record exists but could not be read, so it says nothing."
    return "No retrieval record, so we do not know whether anyone looked."


def audit(paper_dir: str | Path, body_text: str | None = None, extra=None) -> dict:
    """Is this paper's supplementary material referenced, and do we have it?

    Returns a dict that is safe to embed in findings.json and to render.
    `missing` is the only field a caller needs to branch on, and it is
    THREE-VALUED: True (cited and absent), False (nothing missing), and None
    (we could not read the paper, so the question was not answered). None is
    not "no" -- a caller that treats it as one has reinstated the bug below.

    `extra` is files named with `--supplement`, which may live outside the paper
    directory. They are merged here rather than by the caller so that a supplied
    file and a discovered one get the SAME usability verdict, and so that the
    one function the report and the gate both read cannot be told two different
    stories about which files we hold. The CLI previously overwrote
    `files_present` and forced `missing = False` after the fact, which asserted
    we held a file nothing had opened.
    """
    from .extraction.jats import paper_text_with_source

    paper_dir = Path(paper_dir)
    source = None
    if body_text is None:
        # Falls back to the XML full text, then to the PDF text layer. This one
        # matters most: `missing` was `bool(refs) and not have`, so empty text
        # made `find_references` return nothing and the gate passed
        # unconditionally -- the gate whose entire purpose is to stop the
        # pipeline reviewing an incomplete paper.
        body_text, source = paper_text_with_source(paper_dir)

    discovered, unusable = _scan(paper_dir)
    supplied_ok, supplied_bad = _scan_supplied(extra)
    have = discovered + [f for f in supplied_ok if f not in discovered]
    unusable = unusable + supplied_bad

    # FAIL CLOSED WHEN THERE IS NO TEXT TO SEARCH.
    #
    # `bool(refs) and not have` gave the SAME answer -- False, proceed -- for
    # "this paper cites no supplement" and for "we could not read a word of
    # this paper", because an empty string matches no pattern. Those are
    # opposite facts and the gate could not tell them apart.
    #
    # MEASURED with only the main PDF in a clean directory, before `paper_text`
    # learned to read one: 0 characters of text and the gate PROCEEDED on 7 of
    # 7 PDF-only ground-truth papers, and on 97 of 97 corpus papers with 0 of
    # them detected as citing a supplement. With the PDF fallback the same 97
    # papers yield 70 that cite a supplement and 26 that pass.
    # `OVERRIDE_WARNING` never printed, so no report ever said the SI had been
    # absent.
    #
    # The fallback fixes the common case; this fixes the case the fallback
    # cannot reach -- a scanned PDF with no text layer, an unparseable XML, an
    # empty directory. "A precondition could not be verified" is `indeterminate`,
    # and the honest answer is to decline and say why, not to assume the best.
    if not (body_text or "").strip():
        # A cold docling cache is not a scan. `paper_text` returns
        # source="pdf_not_extracted" for that case; collapsing it into
        # text_available=False made `metascience batch` print "scanned or
        # corrupt" for five readable PDF-only papers (nina_mazar/grok_test,
        # 2026-08-20) whose harvest markdown the resolver also never opened.
        text_status = (
            "not_extracted" if source == "pdf_not_extracted" else "empty"
        )
        # SATISFACTION HERE IS KEYED ON `discovered`, NOT `have`. A SUPPLIED
        # SUPPLEMENT DOES NOT MAKE THE PAPER READABLE. `--supplement` answers
        # "do we hold the supplement"; this branch is about whether we can read
        # the ARTICLE it belongs to, and the two are different questions -- a
        # scan that was never OCR'd and a corrupt PDF are not fixed by an
        # attachment. Letting `extra` in here would turn the flag into a way
        # past the unreadability refusal as well as the supplement one, which is
        # the bypass `cli._supplement_gate` was written to close. `files_present`
        # still reports everything we hold, because that part is simply true.
        if discovered:
            # We hold candidate SI files. Presence is the same evidence the
            # normal path accepts, so the gate is satisfied -- but the citation
            # question stays unanswered and is reported as unanswered.
            return {
                "references_supplement": None,
                "reference_count": 0,
                "styles": {},
                "files_present": have,
                "files_unusable": unusable,
                "text_available": False,
                "text_status": text_status,
                "missing": False,
                "note": (
                    "No readable text could be extracted from this paper (no "
                    "body.md, no parseable XML, no PDF text layer), so whether "
                    "it cites supplementary material is UNKNOWN. "
                    f"{len(have)} candidate supplement file(s) are present: "
                    f"{', '.join(have)}."
                ),
            }
        held = (
            f"and the {len(have)} supplementary file(s) supplied on the command "
            f"line ({', '.join(Path(f).name for f in have)}) do not make it "
            "readable"
            if have else
            "and no supplementary files are present"
        )
        note = (
            "No readable text could be extracted from this paper (no body.md, "
            f"no parseable XML, no PDF text layer), {held}. Whether this paper "
            "cites supplementary material is "
            "UNKNOWN -- it was not checked and found absent, it could not be "
            "checked at all. Treat this as indeterminate: an analysis run on a "
            "paper we cannot read cannot report what the paper does and does "
            "not contain."
        )
        if unusable:
            note += (
                f" {len(unusable)} file(s) look like supplements but are "
                "unusable: "
                + "; ".join(f"{u['name']} {u['reason']}" for u in unusable) + "."
            )
        return {
            "references_supplement": None,
            "reference_count": 0,
            "styles": {},
            "files_present": have,
            "files_unusable": unusable,
            "text_available": False,
            "text_status": text_status,
            "missing": None,
            "note": note,
        }

    refs = find_references(body_text)
    n_refs = sum(len(v) for v in refs.values())

    # A DENIAL IS NOT A CITATION, and counting matched strings could not tell
    # them apart. VERIFIED 2026-08-18: "No supplementary material is provided
    # for this article." matched as a REFERENCE TO supplementary material, so
    # `missing` became True and `gate` refused the run -- exit 2, a paper
    # refused analysis for stating it has none.
    #
    # `missing` now rests on mentions that are NOT denials. Denials are kept and
    # reported, because "the paper says it has no supplement" is worth recording
    # -- it is simply not evidence that we are missing one.
    #
    # THE FALLBACK DIRECTION IS DELIBERATE. `_DENIAL_NEAR` does not try to
    # enumerate every negation; that approach already failed once tonight on
    # `artefacts.preregistration`. An unrecognised negation therefore leaves the
    # mention classified as a citation, and the gate refuses -- the conservative
    # error, a blocked run rather than findings written against authors whose
    # supplement we never read.
    _mentions = classify_mentions(body_text)
    cited_mentions = _mentions["cited"]
    denied_mentions = _mentions["denied"]
    missing = bool(cited_mentions) and not have

    if missing:
        note = (
            f"This paper references supplementary material ({n_refs} distinct "
            f"references across {len(refs)} citation styles) and NONE of it is "
            "present in the paper directory. The supplement was therefore not "
            "analysed. Supplementary tables routinely carry the sensitivity "
            "analyses and the per-subgroup statistics, so coverage here is "
            "partial and any statement about what the paper reports should be "
            "read as applying only to the main text."
        )
    elif refs and have:
        note = (f"Supplementary material is referenced and {len(have)} candidate "
                f"file(s) are present: {', '.join(have)}.")
    else:
        note = "No supplementary material is referenced in the extracted text."

    if unusable:
        # Named, because "we have no supplement" and "we have a zero-byte file
        # named like one" send an operator to different places.
        note += (
            " " + "; ".join(
                f"{u['name']} {u['reason']}, so it does not count as present"
                for u in unusable
            ) + "."
        )

    return {
        "references_supplement": bool(cited_mentions),
        "reference_count": n_refs,
        "styles": refs,
        "files_present": have,
        "files_unusable": unusable,
        "text_available": True,
        "text_status": "ok",
        "missing": missing,
        # THE EVIDENCE TRAVELS WITH THE VERDICT. Each entry carries the clause
        # it was found in, so a reader -- or the model -- can see what the
        # screen actually matched instead of taking `missing` on trust.
        "mentions_cited": cited_mentions,
        "mentions_denied": denied_mentions,
        "note": note,
    }


#: Printed in the report when a run proceeds WITHOUT a referenced supplement.
#: The SUBJECT of the first sentence is this review, not the paper.
#:
#: The wording used to open "THIS ANALYSIS WAS RUN ON AN INCOMPLETE PAPER",
#: which reads as a charge against the authors however carefully the rest of
#: the paragraph attributes it to the operator -- and it is set as a bold
#: blockquote between the verdict and the findings, where a charge is exactly
#: what a reader expects to find. The supplement is not missing from the
#: publication; it is missing from OUR COPY, and those are different facts
#: about different people.
OVERRIDE_WARNING = (
    "**THIS REVIEW WAS RUN WITHOUT THE PAPER'S SUPPLEMENTARY MATERIAL.** The "
    "material listed below is cited by the paper and was not present in the "
    "package supplied to this review, which proceeded without it. This is a "
    "limitation of our inputs, not a fault of the publication.\n\n"
    "Read every finding with that in mind. This tool reasons about what a paper "
    "does and does not report, so a statistic that lives in a supplement we do "
    "not hold is indistinguishable here from a statistic the authors never "
    "reported. Any finding of the form 'not reported', 'no power analysis', "
    "'no sensitivity analysis' or 'unavailable' may therefore be an artefact of "
    "the absent file rather than a property of the paper -- and would be an "
    "unfair charge against the authors. The verdict describes the main text "
    "only, and is not a verdict on the paper."
)


def gate(paper_dir, allow_incomplete: bool = False, body_text: str | None = None,
         extra=None) -> dict:
    """Decide whether an analysis may proceed, and what to warn about.

    A MISSING SUPPLEMENT WARNS; IT DOES NOT BLOCK (Dan, 2026-10-18). The gate
    used to refuse a paper that cites supplementary material we do not hold
    (Greg's decision, 2026-08-10), on the ground that a statistic living in a
    missing eTable is indistinguishable from one the authors never reported.
    That risk is real, but refusing threw away every check the main text CAN
    support -- on the GRIM ground truth it skipped a paper whose GRIM failures
    are all in the article itself. So the paper now runs, the warning is
    printed, and the run records the missing material as a limitation
    (`parallel.py`), so a 'not reported' finding can be read against it.

    AN UNREADABLE ARTICLE STILL BLOCKS (`missing is None`), whatever flag is
    passed: with no body.md, no parseable XML and no PDF text layer we cannot
    read the paper at all, which is a different fact from a missing supplement.
    `metascience batch` already refused it without an override; `analyze` now
    agrees. `allow_incomplete` (`--ok-if-supplementary-missing`) is accepted
    and no longer changes anything.

    `extra` (files named with `--supplement`) counts toward the requirement.

    Returns {"proceed": bool, "audit": dict, "message": str} (plus "retrieval"
    when a supplement is cited and missing).
    """
    a = audit(paper_dir, body_text, extra=extra)

    # `missing is None` means the question was not answered, not answered "no".
    if a["missing"] is None:
        return {
            "proceed": False, "audit": a,
            "message": (
                "Refusing to analyse a paper whose text could not be read.\n\n"
                "  No body.md, no parseable XML and no PDF text layer were found, so\n"
                "  the paper cannot be read at all. Supply the text -- a PDF with a\n"
                "  text layer, the publisher XML, or body.md -- and run again."
            ),
        }

    if not a["missing"]:
        return {"proceed": True, "audit": a, "message": ""}

    listing = "\n".join(
        f"    {style}: {', '.join(refs[:6])}" for style, refs in a["styles"].items()
    )
    # What the FETCHER already learned, phrased so that our own download failure
    # is never reported as the authors having published nothing.
    rec = retrieval_record(paper_dir)
    retrieval_line = f"\n  What the fetcher found: {retrieval_sentence(rec)}\n"
    if rec.get("verdict") == "not_open_access":
        remedy = ("  The supplement exists but the provider will not serve it (not open\n"
                  "  access): get it from the publisher or a library.")
    elif rec.get("verdict") == "retrieval_failed":
        remedy = ("  A supplement was listed and our download failed: retry the fetch, or\n"
                  "  download it by hand.")
    elif rec.get("verdict") == "nothing_published":
        remedy = "  No provider lists a supplement for this paper; there may be nothing to supply."
    else:
        remedy = "  To include it: --supplement path/to/file, or put it in the paper directory."
    return {
        "proceed": True, "audit": a, "retrieval": rec,
        "message": (
            "WARNING: analysing WITHOUT the supplementary material this paper cites:\n"
            f"{listing}\n"
            f"{retrieval_line}"
            "  A 'not reported' finding may be an artefact of the missing files; the\n"
            "  report records this as a limitation.\n"
            f"{remedy}"
        ),
    }


# ---------------------------------------------------------------------------
# what KIND of document a supplement is
# ---------------------------------------------------------------------------

#: The roles a supplement can have. CLOSED, so two readings of one corpus
#: cannot drift on the word, and so a caller can switch on it.
SUPPLEMENT_ROLES = ("results", "protocol", "methods_detail", "data", "other")

#: Phrases that make a document one of these things, tested against its
#: HEADINGS and its first 2,000 characters -- the title block, where a document
#: says what it is. Every test is POSITIVE: a supplement matching nothing is
#: `other`, never "probably a protocol".
_ROLE_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    # `data` IS TESTED AGAINST THE HEADINGS ALONE. A JAMA Data Sharing
    # Statement lists "Deidentified participant data, Data dictionary" in its
    # body and is a statement ABOUT data, not data; its headings say what it is.
    ("data", ("data dictionary", "codebook", "variable list", "variable dictionary")),
    ("results", ("supplementary table", "supplemental table", "etable", "efigure",
                 "supplementary figure", "supplementary results", "supplemental results",
                 "supplemental online content", "supplementary material")),
    ("methods_detail", ("supplementary method", "supplemental method", "emethods",
                        "supplementary data", "search strateg", "materials and methods",
                        "supplementary appendix", "supplemental information")),
)

#: Formats that ARE data rather than a document about it.
_DATA_SUFFIXES = {".csv", ".tsv", ".xlsx", ".xlsm", ".xls"}

#: A line naming the document a protocol. SHORT and near the top: a document
#: that IS a protocol says so as its title, and one that merely MENTIONS a
#: protocol says it in a sentence. Measured on the two files that forced this
#: distinction -- 10.1038/s41392-026-02904-0's second supplement opens
#: `Clinical Study Protocol` (23 characters) and is 194,792 characters of trial
#: protocol; its FIRST supplement, 14,607 characters of supplementary results
#: with eleven tables, carries `Appendix 1. List of participating centers, study
#: protocol approval details, and principal/sub investigator` (105 characters)
#: and every one of the same keywords. A keyword count cannot tell them apart
#: and a title line can.
_PROTOCOL_TITLE = re.compile(r"^(?:.{0,30}\b)?(?:clinical |study |trial |research )?protocol\b",
                             re.I)
_PROTOCOL_TITLE_MAX_CHARS = 60
_PROTOCOL_TITLE_LINES = 12


def classify_role(file_name: str, text: str) -> dict:
    """What KIND of document this supplement is: `{role, basis, matched}`.

    ONLY `protocol` HAS CONSEQUENCES, and that is deliberate. A trial protocol
    is a long regulatory document -- 194,792 characters on
    10.1038/s41392-026-02904-0, more than four times the article -- whose prose
    is the sponsor's procedures and not the study's results, and serving it
    costs about $19.50 of the $50.73 that paper's reading was priced at. So a
    `protocol` supplement's PROSE is served only on request; its TABLES are
    walked and counted exactly as any other supplement's, because they are
    evidence wherever they live (Greg, 2026-08-27).

    The other roles are DESCRIPTIVE. Nothing switches on them, so a supplement
    of results filed as `methods_detail` costs a reader a slightly wrong label
    and costs the account nothing -- which is the point of keeping the one
    consequential class behind a title-line test rather than a keyword count.
    """
    text = text or ""
    heads = [l.strip("# ").strip() for l in text.splitlines() if l.startswith("#")]
    lines = [l.strip() for l in text.splitlines() if l.strip()][:40]
    scope = (" | ".join(heads) + " || " + " | ".join(lines) + " || " + text[:2000]).lower()
    suffix = Path(file_name).suffix.lower()
    if suffix in _DATA_SUFFIXES:
        return {"role": "data", "basis": "format", "matched": suffix}
    for line in (heads + lines)[:_PROTOCOL_TITLE_LINES]:
        if len(line) <= _PROTOCOL_TITLE_MAX_CHARS and _PROTOCOL_TITLE.match(line):
            return {"role": "protocol", "basis": "title_line", "matched": line}
    head_scope = (" | ".join(heads) + " || " + " | ".join(lines[:6])).lower()
    for role, phrases in _ROLE_SIGNALS:
        where = head_scope if role == "data" else scope
        hit = next((p for p in phrases if p in where), None)
        if hit:
            return {"role": role,
                    "basis": "heading" if role == "data" else "heading_or_first_2k",
                    "matched": hit}
    return {"role": "other", "basis": "no_positive_test_matched", "matched": None}
