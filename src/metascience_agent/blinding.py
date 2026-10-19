"""Materialize a paper the model can read without learning the answer.

Why this is not a filter
------------------------
The obvious design -- scrub retraction markers out of tool results on the way to
the model -- cannot work here, and the reasons are worth writing down because
they are the reasons a guard becomes inert:

* The sweep is told to `Read body.md` directly (`prompts/stage1_sweep.md`). The
  builtin `Read` passes through no code in this repository, so a filter at the
  MCP envelope never sees it. `Read` also reaches `provenance.json`, sibling
  `abstract.md`, and -- from `eval/ground_truth/papers/<id>/` -- the label file
  `../../manifest.csv` two directories up.
* `python_statcheck(pdf_path)` reads the PDF itself (`tools/r_wrappers.py`). It
  now goes through `extraction/pdf.py` first -- so a hook there WOULD see the
  common case -- but it still falls back to the statcheck package's own reader
  for a PDF our extractor cannot read, and that fallback bypasses `extraction/`
  entirely. A guard that holds on the happy path and not the fallback is the
  kind that reads as present and is not.
* `extract_figures` renders whole PAGES to PNG and the prompt tells the model to
  open them. "RETRACTED ARTICLE" is stamped on those pages as pixels. No text
  scrubber touches a pixel.

So blinding is done to the INPUTS. A sanitized directory is built up from an
allowlist, given an opaque name, and the run is pointed at it. The unblinded
bytes are not reachable by any name the model is given, which makes the property
hold for channels this module has never heard of.

Building up, not stripping down
-------------------------------
`extraction/figures.py` already argues this for the blind figure brief:
constructing a payload from named fields is verifiable, stripping fields out of
one is hopeful. Same rule here. A file type nobody has considered is excluded by
default rather than included unscrubbed, and the PDF -- which is simultaneously
the richest source and the one carrying unscrubbable pixels -- is excluded
outright in blinded mode.

Scrub narrowly, audit broadly
-----------------------------
`SCRUB` is a list of specific marker forms and is necessarily incomplete.
`AUDIT_TERMS` is deliberately over-broad: any surviving occurrence of "retract"
in any casing fails verification. The asymmetry is the point. An unknown marker
form is not silently admitted -- it trips the audit, and the pre-registration
(section 3.2) then excludes that paper as a blinding failure rather than scoring
it. A leak becomes a visible refusal, which is the house preference.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

# ---------------------------------------------------------------------------
# What may be copied into a blinded paper directory.
#
# Deliberately excluded, each for a reason that is not obvious:
#   *.pdf   -- page renders carry the watermark as PIXELS; unscrubable, and the
#              PDF is also the input to statcheck's private extractor.
#   *.html  -- publisher chrome carries retraction banners far from the body.
#   *.json  -- provenance sidecars name the source URL, publisher and often the
#              retraction; nothing in the analysis needs them.
#   figures/ -- rendered pages, same pixel problem.
# ---------------------------------------------------------------------------
ALLOWED_SUFFIXES = frozenset({".md", ".txt", ".xml", ".csv", ".tsv"})

# Directories never copied, whatever they contain.
#
# `forensic_review*` is not hypothetical: three paper directories in
# `eval/ground_truth/papers/` currently hold a PRIOR RUN'S report.md, and one of
# them reads "the article is published as RETRACTED (title carries the
# retraction marker); the second author is Diederik ...". Our own earlier output,
# sitting inside the corpus, naming both the label and the author. It is
# markdown, so an allowlist keyed on suffix alone copies it in.
DENIED_DIRS = frozenset({"figures", "__pycache__", ".git", "forensic_review"})


def _denied(rel: Path) -> bool:
    return any(p in DENIED_DIRS or p.startswith("forensic_review") for p in rel.parts[:-1])


#: Filenames that describe a file's ROLE and identify nothing, so they survive.
#: Anything else is renamed to the opaque id -- a stem like `10.1038--srep12770`
#: or `PMC4491304` is the paper's name, and a blinded path must not carry it.
_GENERIC_STEMS = frozenset({"body", "abstract", "fulltext", "text", "main",
                            "references", "tables", "supplement", "readme"})


def _blind_name(rel: Path, paper_id: str, index: int) -> str:
    stem = rel.stem.lower()
    if stem in _GENERIC_STEMS:
        return rel.name
    return f"{paper_id}{'' if index == 0 else f'_{index}'}{rel.suffix}"

# Specific marker forms, removed where found. Ordered longest-context first so a
# whole sentence goes before the bare word it contains.
SCRUB: tuple[tuple[str, str], ...] = (
    # Sentence-level retraction notices, bounded by sentence punctuation and by
    # tag boundaries -- NOT by line.
    #
    # These were originally written as `^.*<phrase>.*$` with re.MULTILINE, which
    # is correct for markdown and catastrophic for XML: JATS from EPMC arrives as
    # a SINGLE LINE, so `^.*` reached the start of the document and `.*$` the
    # end, and the rule deleted the entire paper. Measured before the fix: three
    # fraud XMLs (nature13375, pone.0001908, tcrm.s15812) were emptied to zero
    # bytes and every one of them then looked, downstream, like a paper with no
    # content -- our failure in the grammar of a claim about the paper.
    (r"(?i)[^.<>\n]*\b(?:this|the)\s+(?:article|paper|manuscript)\s+has\s+been\s+"
     r"retracted\b[^.<\n]*\.?", ""),
    (r"(?i)[^.<>\n]*\bretraction\s+note(?:\s+to)?\s*:?[^.<\n]*", ""),
    (r"(?i)[^.<>\n]*\bexpression\s+of\s+concern\b[^.<\n]*\.?", ""),
    (r"(?i)[^.<>\n]*\bthe\s+(?:authors?|editors?)\s+have\s+retracted\b[^.<\n]*\.?", ""),
    # Title and running-head prefixes: "RETRACTED ARTICLE: real title here".
    (r"(?i)\bretracted\s+article\s*:?\s*", ""),
    (r"(?i)\bretracted\s*:\s*", ""),
    (r"(?i)\bwithdrawn\s*:\s*", ""),
    # Page watermarks, which extraction drops inline with no delimiter, and the
    # spaced-out form some PDFs produce.
    (r"(?i)\bRETRACTED\s+ARTICLE\b", ""),
    (r"(?i)\bR\s+E\s+T\s+R\s+A\s+C\s+T\s+E\s+D\b", ""),
    # ORI / federal misconduct notices cited as related articles. Carry no
    # retraction vocabulary at all, so a "retract" scrubber leaves them.
    (r"(?i)\bfindings\s+of\s+research\s+misconduct\b\.?", ""),
    # JATS structure. Handled as text because the file is copied verbatim.
    (r"(?is)<related-article\b[^>]*?(?:/>|>.*?</related-article>)", ""),
    (r'(?i)\barticle-type\s*=\s*"[^"]*retract[^"]*"', 'article-type="research-article"'),
    (r"(?is)<subj-group\b[^>]*>\s*<subject>\s*retract.*?</subj-group>", ""),
    (r"(?is)<notes\b[^>]*\bretract.*?</notes>", ""),
    # THE WHOLE custom-meta BLOCK, not the lines that mention retraction.
    #
    # Measured: EPMC stamps `<meta-name>is-retracted</meta-name>` on BOTH
    # classes -- `yes` on 8 frauds and `no` on 27 controls -- so the element's
    # mere presence is not the tell, its VALUE is. Worse, its neighbours
    # `display-pdf` and `pmc-prop-has-pdf` separate the classes perfectly
    # (no/no on frauds, yes/yes on controls) while containing no retraction
    # vocabulary whatsoever. Retracted papers get their PDFs suppressed, which is
    # exactly why those flags separate. A scrubber keyed on the word "retract"
    # removes the obvious marker and leaves two perfect ones behind it.
    (r"(?is)<custom-meta-group\b.*?</custom-meta-group>", ""),
    (r"(?is)<custom-meta\b.*?</custom-meta>", ""),
)

# Two tiers, because one tier was wrong in both directions when measured.
#
# BLOCKING: words that state THIS document's status. A survivor is a blinding
# failure and the paper is excluded (PREREGISTRATION.md section 3.2).
#
# REVIEW: words that appear in perfectly ordinary scientific prose and cannot be
# auto-excluded on. Measured on the real corpus: the Stapel positive-mood paper
# says "it is not associated with fabrication of reality", and a PLoS peer-review
# sub-article carries the journal's generic instruction "if you have cited papers
# that have been retracted...". Auto-excluding those would throw away good papers
# for using a word. But "Findings of Research Misconduct" as a REFERENCE TITLE is
# a genuine tell, so they cannot simply be ignored either. They are surfaced for
# a logged human decision, and the default with no decision is exclusion -- a
# visible refusal, which the severity ladder prefers to either silent outcome.
# Blocking terms are PHRASES, not stems, and the distinction is measured rather
# than stylistic. Bare "retract" fires on a control's "stipulations are hard to
# retract" and on another's "retraction of the scapula"; bare "withdrawn" fires
# on drug withdrawal in 7 controls. Blocking on the stem would exclude honest
# papers for using a word while still missing the metadata channels above, which
# is the worst of both.
BLOCKING_TERMS: tuple[str, ...] = (
    r"has\s+been\s+retracted",
    r"have\s+retracted",
    r"retraction[-\s]forward",
    r"is-retracted",
    r"retracted\s+article",
    r"retraction\s+note",
    r"expression\s+of\s+concern",
    r"retraction\s*:",
    r"retracted\s*:",
    r"findings\s+of\s+research\s+misconduct",
)
# Stems that appear in ordinary prose. Surfaced for a logged human decision;
# the default with no decision is exclusion.
REVIEW_TERMS: tuple[str, ...] = (
    r"retract",
    r"withdrawn",
    r"misconduct",
    r"falsificat",
    r"fabricat",
    r"erratum",
    r"corrigendum",
)
_BLOCKING_RE = re.compile("|".join(BLOCKING_TERMS), re.IGNORECASE)
_REVIEW_RE = re.compile("|".join(REVIEW_TERMS), re.IGNORECASE)


def opaque_id(source: str, salt: str = "fmt-blind-v1") -> str:
    """A stable, non-reversible directory name.

    Deterministic so a run can be reproduced and resumed; hashed so the DOI is
    not sitting in the prompt, in every tool result's path, and in every error
    message. The id -> source map is written OUTSIDE the blinded root by
    `materialize_corpus`, because a map inside it is just the label with extra
    steps.
    """
    return "paper_" + hashlib.sha256((salt + "\x00" + source).encode()).hexdigest()[:12]


def scrub_text(text: str) -> tuple[str, list[str]]:
    """Apply every SCRUB rule. Returns the cleaned text and what was removed."""
    removed: list[str] = []
    for pattern, repl in SCRUB:
        def _note(m: re.Match) -> str:
            snippet = " ".join(m.group(0).split())
            removed.append(snippet[:200])
            return repl
        text = re.sub(pattern, _note, text)
    return text, removed


def audit_text(text: str, pattern: re.Pattern[str] | None = None) -> list[str]:
    """Every surviving hit, with a little context so a human can adjudicate."""
    hits = []
    for m in (pattern or _BLOCKING_RE).finditer(text):
        lo, hi = max(0, m.start() - 60), min(len(text), m.end() + 60)
        hits.append(" ".join(text[lo:hi].split()))
    return hits


@dataclass
class BlindedPaper:
    """The result of materializing one paper, and the evidence it is clean."""

    source: Path
    blinded_dir: Path
    paper_id: str
    files_copied: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    residual: list[str] = field(default_factory=list)
    needs_review: list[str] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        """Usable without a human decision.

        Requires BOTH tiers empty. A review-tier hit does not mean the paper is
        contaminated, only that nobody has looked; treating "unexamined" as
        "clean" is how the default silently becomes inclusion.
        """
        return not self.residual and not self.needs_review

    @property
    def excluded(self) -> bool:
        """Blocking hits exclude with no discretion available."""
        return bool(self.residual)

    def report(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "source": str(self.source),
            "clean": self.clean,
            "excluded": self.excluded,
            "files_copied": self.files_copied,
            "files_skipped": self.files_skipped,
            "n_removed": len(self.removed),
            "removed": self.removed[:50],
            "residual": self.residual[:50],
            "needs_review": self.needs_review[:50],
        }


# Filenames get the STEM test, not the phrase test. The phrase rules exist to
# spare ordinary prose ("hard to retract"), and a filename has no prose around
# it -- `RETRACTION_notice.txt` is decisive, and underscores mean the
# whitespace-bearing phrases would never match it anyway.
_PATH_STEM_RE = re.compile(r"retract|withdrawn|misconduct|fraud", re.IGNORECASE)


def _path_is_clean(name: str) -> bool:
    return not _PATH_STEM_RE.search(name)


def materialize(source: Path, dest_root: Path, paper_id: str | None = None) -> BlindedPaper:
    """Build a blinded copy of one paper directory.

    Never mutates `source`. Copies only allowlisted suffixes, scrubs each one,
    renames any file whose own NAME carries a marker, then audits every byte and
    every path in the result. A paper whose audit is non-empty is returned with
    `clean=False` -- it is the caller's job to exclude it, and
    `PREREGISTRATION.md` section 3.2 says to record it as a blinding failure
    rather than as a tool result.
    """
    source = Path(source)
    pid = paper_id or opaque_id(source.name)
    out = Path(dest_root) / pid
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    bp = BlindedPaper(source=source, blinded_dir=out, paper_id=pid)

    for src in sorted(p for p in source.rglob("*") if p.is_file()):
        rel = src.relative_to(source)
        if _denied(rel):
            bp.files_skipped.append(f"{rel} (directory denied)")
            continue
        if src.suffix.lower() not in ALLOWED_SUFFIXES:
            bp.files_skipped.append(f"{rel} (suffix not allowlisted)")
            continue
        try:
            text = src.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            bp.files_skipped.append(f"{rel} (unreadable: {exc})")
            continue
        cleaned, removed = scrub_text(text)
        bp.removed.extend(f"{rel}: {r}" for r in removed)

        # A scrubber that eats the document is broken, not thorough. This is a
        # real defect caught late: a line-anchored rule on single-line XML
        # deleted three whole papers, and the only visible symptom downstream
        # would have been "this paper has no content". Refuse loudly instead.
        # The ratio needs enough text to be meaningful. A 54-character file
        # reading "This article has been retracted. t(48) = 2.31, p = .04."
        # legitimately loses 57% of its length to a correct scrub, and the
        # ratio-only guard dropped the whole file -- taking the statistics with
        # it. Measured on exactly that string while testing the corpus runner.
        # Below the floor, trust the scrub; a real paper is thousands of
        # characters and the ratio does its job there.
        _MIN_FOR_RATIO = 500
        if (len(text.strip()) >= _MIN_FOR_RATIO
                and len(cleaned.strip()) < 0.5 * len(text.strip())):
            bp.anomalies.append(
                f"{rel}: scrubbing removed {1 - len(cleaned.strip()) / len(text.strip()):.0%} "
                f"of the file ({len(text)} -> {len(cleaned)} chars). A blinding rule is "
                f"over-matching; this is our bug, not a property of the paper."
            )
            bp.files_skipped.append(f"{rel} (scrub over-matched)")
            continue

        # A filename can carry the label as loudly as the text can -- and it
        # carries the IDENTITY even when it carries no label at all.
        #
        # `_path_is_clean` only rejects retraction words, so
        # `10.1038--srep12770.xml` passed and every blinded paper in the corpus
        # shipped its own DOI as its filename. MEASURED over all 78 papers via
        # the committed pipeline: `identity_residue` fired on 63 of 63 non-empty
        # papers, 183 hits, ALL of them DOI tokens in the path -- i.e. the
        # blinding failed its own audit on every paper it has ever processed,
        # and the model is told to `Read` that path.
        #
        # Renaming to the opaque id is the whole fix, and it belongs HERE rather
        # than in a caller: the demo directory that passed the audits was
        # renamed by an ad-hoc script, which is how a blind can look sound and be
        # unreproducible from the code that supposedly produced it.
        parts = list(rel.parts[:-1]) + [_blind_name(rel, pid, len(bp.files_copied))]
        if not all(_path_is_clean(p) for p in parts):
            parts = [(p if _path_is_clean(p) else f"d{i}") for i, p in enumerate(parts)]
        target = out.joinpath(*parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(cleaned, encoding="utf-8")
        bp.files_copied.append(str(Path(*parts)))

    bp.residual, bp.needs_review = verify(out)
    return bp


#: JATS elements whose CONTENT is identity, not evidence. Removed wholesale.
#:
#: Element-level removal, not string matching, because the strings do not exist
#: as strings. JATS splits an author into `<surname>` and `<given-names>`, so a
#: scrubber looking for "Laura Steenbergen" finds nothing and reports success
#: while "Steenbergen" survives five times. That is not hypothetical -- it is
#: what the first version of this function did, and its audit shared the same
#: matcher and certified the result clean.
#:
#: `ref-list` is here deliberately. A reference list identifies a paper almost
#: uniquely, self-citations name the authors outright, and NOTHING in a
#: forensic arithmetic check reads it. Keeping it would trade the whole point of
#: blinding for evidence we do not use.
_IDENTITY_ELEMENTS: tuple[str, ...] = (
    "article-id", "contrib-group", "aff", "author-notes", "journal-meta",
    "history", "permissions", "funding-group", "ack", "ref-list", "self-uri",
    "related-article", "article-categories", "custom-meta-group", "pub-date",
    "issn", "publisher", "issue", "volume", "fpage", "lpage", "elocation-id",
    "counts", "isbn", "supplementary-material", "title-group",
    # `history` does NOT match `<pub-history>` -- `<history\b` requires a word
    # boundary the prefix defeats -- so EPMC's `pub-history` block survived the
    # whole chain carrying `pmc-release`, `pmc-live` and a `pmc-last-change` ISO
    # timestamp. PMC re-touches a record when a retraction is linked, so the
    # blinding was deleting the retraction's WORDS and shipping its DATE.
    # MEASURED on the 25 papers carrying both dates: the release-to-last-change
    # gap averages 10.2 years for frauds against 5.2 for controls, AUC 0.785,
    # Mann-Whitney p = 0.038. A hand-listed element allowlist keeps failing in
    # exactly this prefix-and-sibling way; see the note on build-up below.
    "pub-history", "issue-id", "article-version", "event", "date",
)

#: THE STRUCTURAL LESSON, recorded rather than acted on today. This module's own
#: docstring argues for BUILDING UP from named fields rather than STRIPPING
#: DOWN, because "a file type nobody has considered is excluded by default
#: rather than included unscrubbed". `_IDENTITY_ELEMENTS` is a strip-down, and
#: it has now failed twice for the same reason -- `custom-meta` siblings, then
#: `pub-history` -- each time leaving a class-separating artefact behind. The
#: doctrine-consistent design keeps ONLY `<abstract>` and `<body>` and discards
#: the rest of the JATS tree unread. That is a bigger change than one sitting
#: allows and it alters what every downstream extractor sees, so it is filed
#: rather than rushed.

#: Patterns that identify a paper regardless of what the manifest says. The
#: audit uses these INDEPENDENTLY of whatever the caller asked to be scrubbed,
#: so a scrubber that missed something cannot also hide it.
_ID_PATTERNS: tuple[tuple[str, str], ...] = (
    ("doi", r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+"),
    ("pmcid", r"\bPMC\d{4,}\b"),
    ("pmid", r"\bpmid\b[^0-9]{0,10}\d{6,9}"),
    ("email", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("orcid", r"\b\d{4}-\d{4}-\d{4}-\d{3}[0-9X]\b"),
    ("url", r"https?://[^\s<>\"']+"),
    # TRIAL REGISTRATIONS. A registration id resolves to the exact study on a
    # public registry, and from there to its retraction, so it identifies a
    # paper as precisely as its DOI. MEASURED: 14 papers still carried one after
    # the identity scrub, including fraud 10.1371/journal.pone.0320595 with
    # NCT02510313 twice -- and `identity_residue` reported none of them, because
    # a registry id is in no manifest column and nobody had thought to list it.
    # That is the caller's-imagination failure the derived-identifier work was
    # meant to end, surviving one level up.
    ("registration", r"\b(?:NCT\d{8}|ISRCTN\d{6,}|ChiCTR[-\w]*\d{6,}|"
                     r"KCT\d{7}|UMIN\d{9}|ACTRN\d{14}|DRKS\d{8}|IRCT\d{11,}|NTR\d{3,4})\b"),
)

#: Labels whose value is a PHRASE of ordinary words. Scrubbed as a whole phrase,
#: never token by token.
#:
#: MEASURED: treating every word of a journal name as identity redacted ordinary
#: domain vocabulary in 73 of 78 papers -- all 13 body occurrences of
#: "motivation" in a motivation-psychology paper, "cell", "attention",
#: "perception", "emotion". Two harms, and the second is worse than the first.
#: It destroys the evidence under review, and the PATTERN of which common words
#: are missing reconstructs the journal for any reader who notices, so the
#: over-redaction is itself a watermark.
_PHRASE_ONLY = frozenset({"title", "abstract", "keywords", "journal",
                          "journalid", "publisher"})

#: Surnames that are also ordinary words. A model writing "the Beck Depression
#: Inventory" has not recognised a paper by an author named Beck.
_COMMON_WORDS = frozenset({
    "beck", "brain", "band", "will", "young", "long", "short", "white",
    "black", "green", "brown", "wood", "field", "park", "hill", "church",
    "cross", "day", "may", "man", "best", "rich", "read", "cook", "bell",
    "stone", "moore", "price", "power", "child", "case", "means", "mode",
    "cognitive", "medical", "health", "human", "social", "clinical",
})

#: Fields the MODEL wrote, as opposed to text OUR templates wrote.
#:
#: `recognition_hits` must be run over these and NOT over `report.md`. Measured
#: on the blinded demo runs, scanning the rendered report flagged 'retract',
#: 'misconduct' and 'fabricat' -- every one of them from our OWN boilerplate
#: ("no publication-level cross-checks -- registration, retraction status ...",
#: "not a finding of misconduct"). Scanning our disclaimer for the vocabulary
#: our disclaimer is required to use makes the check fire on every run and mean
#: nothing.
_MODEL_AUTHORED_FIELDS = ("title", "plain", "notes", "quote", "location",
                          "statement", "claim", "explanation", "reported",
                          "computed", "assumptions", "consequence")


def model_authored_text(review_dir: Path) -> str:
    """Concatenate only what the MODEL wrote in a review, for `recognition_hits`.

    Walks `findings.json` and `report.json` and keeps the free-text fields the
    model authored, so the recognition check is not reading our own templates
    back to itself.
    """
    out: list[str] = []

    def walk(node) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                if k in _MODEL_AUTHORED_FIELDS and isinstance(v, (str, int, float)):
                    out.append(str(v))
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for name in ("findings.json", "report.json"):
        p = Path(review_dir) / name
        if p.exists():
            try:
                walk(json.loads(p.read_text(encoding="utf-8", errors="replace")))
            except ValueError:
                continue
    return "\n".join(out)


#: Identifier labels whose words are the paper's SUBSTANCE, never scrubbed as
#: tokens. Blinding must not destroy the evidence being examined.
#:
#: MEASURED: token-scrubbing the title of 10.1038/srep12770 replaced "GABA" 103
#: times throughout the body, because the word is in the title. That is not
#: blinding, it is redaction of the thing under review, and a hostile reviewer
#: would be right to say the tool was never given the paper.
#:
#: The title still goes STRUCTURALLY -- `title-group` is in
#: `_IDENTITY_ELEMENTS` -- so it does not appear as metadata. What survives is
#: the vocabulary in the body, which is exactly the position double-blind peer
#: review takes: metadata can be hidden, subject matter cannot. Recognition from
#: content is therefore IRREDUCIBLE, and `recognition_hits` exists because the
#: honest response to an irreducible risk is to measure it, not to claim it away.
_CONTENT_BEARING = frozenset({"title", "abstract", "keywords"})


def _identity_tokens(identifiers: dict[str, str]) -> set[str]:
    """Every word worth hunting, derived from the identifiers by SPLITTING them.

    The whole failure this repairs is that identity appears in fragments: a
    manifest says "Laura Steenbergen" and the document says `<surname>`
    Steenbergen. Tokens are lowercased, 4+ characters, and stripped of the
    stopwords that would otherwise match half the paper.
    """
    stop = {"the", "and", "for", "with", "from", "study", "trial", "effects",
            "effect", "randomized", "randomised", "controlled", "double",
            "blind", "journal", "research", "review", "article", "retracted",
            "university", "department", "school", "institute", "center",
            "centre", "hospital", "college", "national", "international"}
    out: set[str] = set()
    for label, value in identifiers.items():
        if label.split('_')[0] in _CONTENT_BEARING | _PHRASE_ONLY:
            continue
        for tok in re.split(r"[^A-Za-z0-9]+", str(value or "")):
            low = tok.lower()
            if len(low) >= 4 and low not in stop and not low.isdigit():
                out.add(low)
            elif len(low) >= 4 and low.isdigit():
                out.add(low)
    return out


def derive_identifiers(source: Path, extra: dict[str, str] | None = None) -> dict[str, str]:
    """Read the paper's identity OUT OF THE PAPER, not out of a manifest.

    A hostile reviewer's next question after "did you remove the DOI" is "what
    else was in there that you did not think to list". Driving the scrub from a
    hand-written identifier list answers that badly, because the audit then
    hunts only what the caller remembered -- and a caller who forgets one gets a
    clean bill of health for it.

    MEASURED, and this is exactly how it failed: scrubbing 10.1038/srep12770
    from a manifest row (doi, title, author, journal) left the affiliation city
    "Leiden" in the text twice, and the audit reported zero residue because
    nobody had listed affiliations. The ethics-approval and funding sentences in
    the BODY name the institution, so element removal alone does not reach them.

    This pulls surnames, given names, affiliations, institutions, every
    `<article-id>`, the journal titles and ids, publisher, and any email --
    from the ORIGINAL document, before anything is removed. `extra` merges in
    whatever the caller does know (a manifest row) rather than replacing it.
    """
    source = Path(source)
    found: dict[str, str] = {}
    n = 0

    def add(label: str, value: str) -> None:
        nonlocal n
        value = re.sub(r"\s+", " ", str(value or "")).strip()
        if len(value) >= 4:
            n += 1
            found[f"{label}_{n}"] = value

    patterns = (
        ("surname", r"<surname\b[^>]*>(.*?)</surname>"),
        ("given", r"<given-names\b[^>]*>(.*?)</given-names>"),
        ("aff", r"<aff\b[^>]*>(.*?)</aff>"),
        ("institution", r"<institution\b[^>]*>(.*?)</institution>"),
        ("articleid", r"<article-id\b[^>]*>(.*?)</article-id>"),
        ("journal", r"<journal-title\b[^>]*>(.*?)</journal-title>"),
        ("journalid", r"<journal-id\b[^>]*>(.*?)</journal-id>"),
        ("publisher", r"<publisher-name\b[^>]*>(.*?)</publisher-name>"),
        ("email", r"<email\b[^>]*>(.*?)</email>"),
    )
    for p in sorted(source.rglob("*")):
        if not p.is_file() or p.suffix.lower() not in ALLOWED_SUFFIXES:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for label, pat in patterns:
            for m in re.findall(pat, text, flags=re.IGNORECASE | re.DOTALL):
                # An <aff> carries markup and a superscript label; keep the words.
                add(label, re.sub(r"<[^>]+>", " ", m))
    found.update(extra or {})
    return found


def scrub_identity(blinded_dir: Path, identifiers: dict[str, str]) -> dict:
    """Remove the paper's IDENTITY from an already-marker-blinded copy.

    MARKER-BLINDING IS NOT IDENTITY-BLINDING, and treating them as the same
    thing invalidates the measurement the blinding exists to protect.
    `materialize` removes retraction notices; it leaves the DOI, the authors,
    the journal and the title, because none of those is a retraction marker.

    MEASURED on 10.1038/srep12770 after a materialize that reported 0 surviving
    blocking markers: the blinded XML still contained the DOI twice,
    "Steenbergen" 4 times, "Colzato" 6 times, and the journal name. That is
    ample for a model that has read the literature to recognise the paper and
    recall that it was retracted -- so a "blind" run was blind to the notice and
    never to the subject, and any accuracy claim resting on it is unearned.

    `identifiers` is `{label: string}`, normally doi/title/first_author/journal
    straight from the ground-truth manifest, so the CALLER states what is being
    hidden instead of this function guessing. Matches are replaced with a
    labelled placeholder rather than deleted: removing an author list outright
    changes the document's structure, and a structural check could read that as
    a finding about the paper.

    Returns per-identifier replacement counts, so a caller can assert the scrub
    did something instead of assuming it did.
    """
    root = Path(blinded_dir)
    counts: dict[str, int] = {"elements_removed": 0, "patterns_removed": 0,
                              "phrases_removed": 0, "tokens_removed": 0,
                              "files_changed": 0}
    tokens = _identity_tokens(identifiers)
    tok_re = (re.compile(r"\b(" + "|".join(sorted(map(re.escape, tokens), key=len, reverse=True)) + r")\b",
                         re.IGNORECASE) if tokens else None)

    for p in sorted(root.rglob("*")):
        if not p.is_file():
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        original = text

        # 1. STRUCTURE. Whole elements out, greedily nested-safe via non-greedy
        #    match to the matching close tag. Self-closing forms too.
        for el in _IDENTITY_ELEMENTS:
            text, n = re.subn(rf"(?is)<{el}\b[^>]*>.*?</{el}>", "", text)
            counts["elements_removed"] += n
            text, n = re.subn(rf"(?is)<{el}\b[^>]*/>", "", text)
            counts["elements_removed"] += n

        # 2. PATTERNS. Anything DOI-shaped, PMC-shaped, an email, an ORCID or a
        #    URL, whether or not the caller knew to ask -- these identify a paper
        #    on their own and appear in prose as well as in metadata.
        for label, pat in _ID_PATTERNS:
            text, n = re.subn(pat, f"[{label.upper()}-REDACTED]", text)
            counts["patterns_removed"] += n

        # 3. PHRASES. Multi-word identifiers whose individual words are
        #    ordinary English -- a journal or a title -- are removed only as a
        #    whole phrase, so "Motivation and Emotion" goes and "motivation"
        #    stays. Longest first, so a title containing the journal name is
        #    replaced before the journal name is.
        phrases = sorted(
            ((lab, str(v or "").strip()) for lab, v in identifiers.items()
             if lab.split("_")[0] in _CONTENT_BEARING | _PHRASE_ONLY),
            key=lambda kv: len(kv[1]), reverse=True)
        for label, value in phrases:
            if len(value) < 8 or " " not in value:
                # A single ordinary word is not removable without destroying
                # prose; the structural pass already took it out of the metadata.
                continue
            text, n = re.subn(re.escape(value), "[REDACTED]", text, flags=re.IGNORECASE)
            counts["phrases_removed"] = counts.get("phrases_removed", 0) + n

        # 4. TOKENS. What is left of the caller's identifiers, word by word, so
        #    a surname that only ever appears alone is still caught.
        if tok_re is not None:
            text, n = tok_re.subn("[REDACTED]", text)
            counts["tokens_removed"] += n

        if text != original:
            p.write_text(text, encoding="utf-8")
            counts["files_changed"] += 1
    return counts


def identity_residue(blinded_dir: Path, identifiers: dict[str, str]) -> list[str]:
    """Anything identifying that survived. Empty is the only acceptable result.

    THE AUDIT MUST NOT SHARE THE SCRUBBER'S MATCHER. The first version of this
    pair searched for the same whole strings the scrubber replaced, so it could
    only ever confirm what the scrubber had already done: it reported a clean
    blind on a file still containing "Steenbergen" five times and "srep12770"
    nine times. A check that inherits the blind spot of the thing it checks does
    not merely fail to help, it manufactures confidence.

    So this works two ways the scrubber does not:

      * INDEPENDENT PATTERNS -- DOI, PMCID, PMID, email, ORCID and bare URLs
        are hunted whatever the caller listed, because they identify a paper on
        their own and a caller who forgot one is exactly the case to catch.
      * TOKENS, not phrases -- every identifier is split into words, so a
        surname that appears alone inside `<surname>` is found even though the
        full name never occurs.

    Paths are searched as well as contents: a clean file with a dirty name is
    not blind.
    """
    root = Path(blinded_dir)
    out: list[str] = []
    tokens = _identity_tokens(identifiers)
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        hay = str(rel)
        if p.is_file():
            try:
                hay += "\n" + p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                out.append(f"{rel}: UNREADABLE, so cannot be certified blind")
                continue
        low = hay.lower()
        for label, pat in _ID_PATTERNS:
            for hit in re.findall(pat, hay)[:3]:
                out.append(f"{rel}: {label} pattern survives ({hit[:60]!r})")
        for tok in sorted(tokens):
            if re.search(rf"\b{re.escape(tok)}\b", low):
                out.append(f"{rel}: identity token {tok!r} survives")
    return out


def recognition_hits(model_output: str, identifiers: dict[str, str]) -> list[str]:
    """Did the MODEL name the paper we blinded, or its status?

    The one thing input-blinding cannot do is stop a model recognising a famous
    paper from its content. Subject matter is not removable -- removing it
    removes the evidence -- so this risk is IRREDUCIBLE, and the honest response
    to an irreducible risk is to measure it rather than claim it away.

    A hostile reviewer's strongest line is "your model had read the retraction
    notice in training, so your blind is theatre." The answer is not to deny it.
    It is: we scrubbed every metadata channel, and we then checked the model's
    own words for the DOI, the authors, the journal and any retraction
    vocabulary. A run with a hit here is VOID, not merely caveated -- and the
    check runs on the output, so it catches recognition however it arrived.

    Returns the specific hits; empty means the output shows no sign the model
    knew what it was reading.
    """
    text = str(model_output or "")
    low = text.lower()
    out: list[str] = []
    # NAME-LIKE LABELS ONLY. Running this over EVERY identifier token fires on
    # ordinary subject vocabulary and voids every run: measured on the two
    # blinded demo runs, it flagged 'brain', 'cognitive', 'band' and 'beck' --
    # all pulled out of affiliation strings, and 'beck' being the Beck
    # Depression Inventory, i.e. the paper's own instrument. A detector that
    # fires on every run is a detector that gets switched off, which is the
    # lesson the guard alarm already taught this repo.
    #
    # A surname is high-specificity evidence of recognition; an institution's
    # city or a journal's adjective is not. Affiliations and journals still
    # cannot leak, because `_ID_PATTERNS` below and the whole-phrase pass in
    # `scrub_identity` cover them -- this narrows only what counts as the MODEL
    # having named the paper.
    name_like = {k: v for k, v in identifiers.items()
                 if k.split("_")[0] in ("surname", "given", "author")}
    for tok in sorted(_identity_tokens(name_like)):
        if tok in _COMMON_WORDS:
            continue
        if re.search(rf"\b{re.escape(tok)}\b", low):
            out.append(f"model output names identity token {tok!r}")
    for label, pat in _ID_PATTERNS:
        for hit in re.findall(pat, text)[:2]:
            out.append(f"model output contains a {label} ({hit[:50]!r})")
    # `BLOCKING_TERMS` are REGEX PATTERNS, not literals. Testing them with
    # `term.lower() in low` compiled fine, ran fine, and matched nothing: 8 of
    # the 10 contain `\s+` or a character class, so they cannot occur as literal
    # substrings of English. MEASURED before the fix -- "I recall that this
    # article has been retracted following an ORI investigation" returned [].
    #
    # The tier that voids a run for the model announcing the very status the
    # blind exists to hide was inert from the moment it was written, and it was
    # written as the answer to that exact risk. Use the compiled alternation the
    # module already maintains for its file audit, so the two cannot drift.
    for hit in audit_text(text, _BLOCKING_RE):
        out.append(f"model output uses retraction vocabulary: {hit}")
    # TWO TIERS, and only the first voids a run -- the same asymmetry the file
    # audit already uses, for the same reason.
    #
    # BLOCKING_TERMS are PHRASES ("this article has been retracted"), so a hit is
    # an assertion about THIS paper and is decisive. REVIEW_TERMS are bare stems
    # ("retract", "misconduct", "fabricat"), and a forensic report is required to
    # use that vocabulary: the model's own hedging says "not a finding of
    # misconduct" and "this is not evidence of fabrication". MEASURED on the two
    # blinded demo runs, treating stems as decisive flagged BOTH runs on exactly
    # such sentences. Voiding a run because its disclaimer used the word the
    # disclaimer exists to use is not a check, it is a tax.
    for term in REVIEW_TERMS:
        if re.search(term, text, re.IGNORECASE):
            out.append(f"REVIEW: model output uses status vocabulary {term!r} "
                       "-- read it in context before voiding; forensic prose "
                       "legitimately uses these words")
    return out


def voids_run(hits: list[str]) -> bool:
    """Does this set of recognition hits invalidate the run?

    Only the decisive tier. A caller that treats every hit as fatal will void
    every run and then stop running the check, which is how the guard alarm
    taught this repo to ignore its own audits.
    """
    return any(not h.startswith("REVIEW:") for h in hits)


def verify(blinded_dir: Path) -> tuple[list[str], list[str]]:
    """Scan a materialized directory for anything that survived.

    Every byte of every file AND every path component, because a clean file with
    a dirty name is not blind. Returns (blocking, review).
    """
    residual: list[str] = []
    review: list[str] = []
    root = Path(blinded_dir)
    for p in sorted(root.rglob("*")):
        rel = p.relative_to(root)
        if not _path_is_clean(str(rel)):
            residual.append(f"PATH {rel}")
        if p.is_file():
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError as exc:  # pragma: no cover - unreadable after we wrote it
                residual.append(f"UNREADABLE {rel}: {exc}")
                continue
            residual.extend(f"{rel}: {h}" for h in audit_text(text, _BLOCKING_RE))
            review.extend(f"{rel}: {h}" for h in audit_text(text, _REVIEW_RE))
    return residual, review


def materialize_corpus(
    sources: list[Path], dest_root: Path, map_path: Path
) -> list[BlindedPaper]:
    """Blind a whole corpus and write the id -> source map somewhere safe.

    `map_path` must not sit inside `dest_root`; a map beside the papers is the
    label with extra steps, and `Read` is not restricted by directory.
    """
    dest_root, map_path = Path(dest_root), Path(map_path)
    if map_path.resolve().is_relative_to(dest_root.resolve()):
        raise ValueError(
            f"the id->source map would sit inside the blinded root ({map_path}); "
            "the model can Read it. Put it beside the analyst's notes instead."
        )
    papers = [materialize(s, dest_root) for s in sources]
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(
        {p.paper_id: str(p.source) for p in papers}, indent=2, sort_keys=True
    ))
    return papers


def audit_ledger(ledger: list[dict], blinded_root: Path) -> list[str]:
    """Decide from the RUN what happened, not from a flag what was intended.

    The codebase's own doctrine (`_sandbox_audit`, `_figures_were_read`): a mode
    flag records an intention, the ledger records the behaviour. Every path the
    run actually touched must lie inside the blinded root. Reads outside it are
    how a blinded run quietly stops being one -- `../../manifest.csv` is two
    directories up from a paper and holds the label column.
    """
    root = Path(blinded_root).resolve()
    escapes: list[str] = []
    for entry in ledger:
        # The real ledger written by `write_review_outputs` keys these `tool`
        # and `input`; `name`/`arguments` is the MCP wire shape. Read both, or
        # the audit reports every escape against a tool called "?" -- which is
        # how an audit stops being actionable.
        name = entry.get("tool") or entry.get("name") or "?"
        args = entry.get("input") or entry.get("arguments") or {}
        if not isinstance(args, dict):
            continue
        for key, value in args.items():
            if not isinstance(value, str):
                continue
            if key not in {"file_path", "path", "pdf_path", "xml_path",
                           "html_path", "out_dir", "notebook_path"}:
                continue
            try:
                resolved = Path(value).resolve()
            except (OSError, ValueError):
                escapes.append(f"{name}: unresolvable path {value!r}")
                continue
            if not resolved.is_relative_to(root):
                escapes.append(f"{name}: {key}={value} is outside the blinded root")
    return escapes
