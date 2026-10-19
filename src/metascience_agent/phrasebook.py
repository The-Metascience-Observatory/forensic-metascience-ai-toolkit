"""
Fingerprint dictionary + tokenizer + scanner for the tortured-phrases screen.

This module is the ENGINE ONLY: it loads the fingerprint dictionary shipped in
`data/tortured_phrases/`, normalizes text, and reports verbatim matches with
character offsets. It assigns no severity and draws no conclusions -- that is
`tools/tortured_phrases.py`'s job. Three consumers share it (the tool, the
CLI, the calibration script), which is why it lives at the package root beside
`artefacts.py` and `glyphs.py` rather than in `tools/`.

THE DICTIONARY AND THE TEXT SHARE ONE NORMALIZER (`tokenize`). Every variant
the matcher tolerates -- case, curly apostrophes, ligatures, hyphen vs space
vs linebreak -- is defined once, in the tokenizer, so the dictionary rows can
stay in plain display form and never encode variants themselves. A fingerprint
matched under a generated variant (plural fold, linebreak-hyphen join) reports
its CANONICAL form plus which variant fired, never the variant silently.

Matching is a token-tuple lookup: normalize once, tokenize once, index all
fingerprints by first token, scan linearly. ~80k tokens for a 500 KB paper,
one dict probe per position -- no regex alternation over 7k patterns, no
character-level automaton.

The dictionary identity travels with every result: `manifest.json:version` is
the human-readable dictionary version, and `sha256` is computed AT LOAD TIME
over the TSV bytes -- computed, not copied from the manifest, so it cannot
drift from the files (the `version.py` lesson). Two runs under different
dictionaries are not comparable, and the sha is how a reader finds out.
"""

from __future__ import annotations

import csv
import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Iterator, NamedTuple, Optional

DATA_DIR = Path(__file__).resolve().parent / "data" / "tortured_phrases"

#: The three fingerprint families. `family` in every TSV row must be one.
FAMILIES = ("tortured_phrase", "llm_boilerplate", "tortured_acronym")

#: llm_boilerplate rows carry a subclass; the severity ladder keys on it.
BOILERPLATE_SUBCLASSES = ("first_person_disclaimer", "chat_artifact",
                          "knowledge_cutoff")

#: The TSV files that constitute the dictionary, in sha-computation order.
#: `blocklist.tsv` is included: retiring a fingerprint changes what a run can
#: find just as adding one does.
_TSV_FILES = ("fingerprints.tsv", "tortured_acronyms.tsv",
              "llm_boilerplate.tsv", "blocklist.tsv")

_TSV_COLUMNS = ("tortured", "expected", "family", "subclass", "sources",
                "flags", "ambiguity", "acronym", "note")


class PhrasebookError(RuntimeError):
    """The dictionary could not be loaded -- a property of the INSTALLATION
    (missing/garbled data files), never of any paper."""


class Token(NamedTuple):
    """One word of normalized text, with offsets into the ORIGINAL string."""

    text: str   # NFKC, lowercased, curly->straight apostrophe
    raw: str    # NFKC + apostrophe-normalized, case PRESERVED (for `cs`)
    start: int  # char offset of the first character in the original text
    end: int    # char offset one past the last character
    line_hyphen_next: bool  # a hyphen+linebreak separates this token from the next


@dataclass(frozen=True)
class Fingerprint:
    tortured: str                 # canonical display form (identity)
    expected: str                 # the phrase it counterfeits ("" = none)
    family: str
    subclass: str                 # llm_boilerplate only, else ""
    sources: tuple[str, ...]
    flags: frozenset[str]         # "cs" (exact-case), "allow1" (1 token ok)
    ambiguity: str                # "low" | "high"; high never counts toward k
    acronym: str                  # tortured_acronym only: the expected acronym
    note: str
    tokens: tuple[str, ...] = field(default=(), compare=False)
    raw_tokens: tuple[str, ...] = field(default=(), compare=False)


class Match(NamedTuple):
    fingerprint: Fingerprint
    start: int          # offsets into the ORIGINAL text
    end: int
    matched_text: str   # the original span, verbatim
    variant: Optional[str]  # None | "plural" | "line_hyphenation"


@dataclass
class Phrasebook:
    fingerprints: tuple[Fingerprint, ...]
    version: str
    sha256: str
    n_blocked: int
    per_family: dict[str, int]
    sources: tuple[str, ...]
    data_dir: Path
    # first normalized token -> ((token_tuple, fingerprint, variant), ...)
    index: dict[str, tuple[tuple[tuple[str, ...], Fingerprint, Optional[str]], ...]]

    @property
    def n_fingerprints(self) -> int:
        return len(self.fingerprints)

    def dictionary_block(self) -> dict:
        """The provenance block every result must carry."""
        return {
            "version": self.version,
            "sha256": self.sha256,
            "n_fingerprints": self.n_fingerprints,
            "per_family": dict(self.per_family),
            "n_blocked": self.n_blocked,
            "sources": list(self.sources),
        }


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

#: Characters treated as hyphens when they sit between a token and a line
#: break: ASCII hyphen, soft hyphen, Unicode hyphen, non-breaking hyphen.
_HYPHENS = "-­‐‑"

_APOSTROPHES = str.maketrans({"’": "'", "‘": "'", "ʼ": "'"})


def _is_word_char(ch: str) -> bool:
    return ch.isalnum()


def tokenize(text: str) -> list[Token]:
    """Split `text` into normalized word tokens with original offsets.

    Hyphens and ALL whitespace are separators, so `signal-to-noise`,
    `signal to noise` and `signal\\nto noise` tokenize identically.
    Apostrophes are word-internal (`don't` is one token). `line_hyphen_next`
    marks the one genuinely ambiguous PDF artifact -- a hyphen immediately
    followed by a line break -- so the matcher can try both the hard reading
    (two tokens) and the soft reading (one word split by justification).
    Offsets always index the ORIGINAL string; normalization (NFKC, casing)
    applies to the token text only.
    """
    tokens: list[Token] = []
    i, n = 0, len(text)
    while i < n:
        if not _is_word_char(text[i]):
            i += 1
            continue
        start = i
        while i < n and (_is_word_char(text[i])
                         or (text[i] in "'’‘ʼ"
                             and i + 1 < n and _is_word_char(text[i + 1]))):
            i += 1
        raw_span = text[start:i]
        raw = unicodedata.normalize("NFKC", raw_span).translate(_APOSTROPHES)
        # Peek at the separator: hyphen(s) directly after the token, then
        # whitespace containing a newline, then the next word => a line-break
        # hyphenation site.
        j = i
        while j < n and text[j] in _HYPHENS:
            j += 1
        hyphen_next = False
        if j > i:  # at least one hyphen directly after the token
            k = j
            saw_newline = False
            while k < n and text[k].isspace():
                saw_newline = saw_newline or text[k] == "\n"
                k += 1
            hyphen_next = saw_newline and k < n and _is_word_char(text[k])
        tokens.append(Token(text=raw.lower(), raw=raw, start=start, end=i,
                            line_hyphen_next=hyphen_next))
    return tokens


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _parse_tsv(path: Path) -> Iterator[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as fh:
        rows = csv.reader(
            (ln for ln in fh if ln.strip() and not ln.lstrip().startswith("#")),
            delimiter="\t")
        try:
            header = next(rows)
        except StopIteration:
            return
        for lineno, row in enumerate(rows, start=2):
            padded = list(row) + [""] * (len(header) - len(row))
            yield dict(zip(header, (c.strip() for c in padded)))


def _fp_key(tortured: str, family: str) -> tuple[tuple[str, ...], str]:
    return tuple(t.text for t in tokenize(tortured)), family


def _plural_fold(tokens: tuple[str, ...]) -> Optional[tuple[str, ...]]:
    """The generated surface variant: last token's trailing `s` toggled.

    Deliberately shallow -- no stemming, no mid-phrase inflection. The PPS
    list already enumerates common surface forms; deeper inflection is where
    the false-positive risk starts.
    """
    last = tokens[-1]
    if not last or not last[-1].isalpha():
        return None
    folded = last[:-1] if last.endswith("s") and len(last) > 3 else last + "s"
    if folded == last or not folded:
        return None
    return tokens[:-1] + (folded,)


def _load_uncached(data_dir: Path) -> Phrasebook:
    if not data_dir.is_dir():
        raise PhrasebookError(
            f"fingerprint data directory not found: {data_dir}. This is a "
            "property of the installation, not of any paper.")
    manifest_path = data_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise PhrasebookError(
            f"could not read {manifest_path.name}: {exc}") from exc
    version = str(manifest.get("version", "")) or "unversioned"

    sha = hashlib.sha256()
    for name in _TSV_FILES:
        p = data_dir / name
        if p.is_file():
            sha.update(name.encode())
            sha.update(p.read_bytes())

    blocked: set[tuple[tuple[str, ...], str]] = set()
    block_path = data_dir / "blocklist.tsv"
    if block_path.is_file():
        for row in _parse_tsv(block_path):
            if row.get("tortured") and row.get("family"):
                blocked.add(_fp_key(row["tortured"], row["family"]))

    fingerprints: list[Fingerprint] = []
    seen: set[tuple[tuple[str, ...], str]] = set()
    n_blocked = 0
    sources: set[str] = set()
    per_family = {fam: 0 for fam in FAMILIES}

    for name in ("fingerprints.tsv", "tortured_acronyms.tsv",
                 "llm_boilerplate.tsv"):
        path = data_dir / name
        if not path.is_file():
            continue
        for row in _parse_tsv(path):
            tortured = row.get("tortured", "")
            family = row.get("family", "")
            if not tortured:
                continue
            if family not in FAMILIES:
                raise PhrasebookError(
                    f"{name}: unknown family {family!r} for {tortured!r}")
            subclass = row.get("subclass", "")
            if subclass and subclass not in BOILERPLATE_SUBCLASSES:
                raise PhrasebookError(
                    f"{name}: unknown subclass {subclass!r} for {tortured!r}")
            flags = frozenset(f for f in row.get("flags", "").split(",") if f)
            toks = tokenize(tortured)
            if len(toks) < 2 and "allow1" not in flags:
                raise PhrasebookError(
                    f"{name}: single-token fingerprint {tortured!r} without "
                    "the `allow1` flag -- single words are the false-positive "
                    "class dictionary matching cannot survive.")
            key = (tuple(t.text for t in toks), family)
            if key in blocked:
                n_blocked += 1
                continue
            if key in seen:
                continue
            seen.add(key)
            src = tuple(s for s in row.get("sources", "").split(",") if s)
            sources.update(src)
            ambiguity = row.get("ambiguity", "") or "low"
            if ambiguity not in ("low", "high"):
                raise PhrasebookError(
                    f"{name}: ambiguity must be low|high, got {ambiguity!r} "
                    f"for {tortured!r}")
            per_family[family] += 1
            fingerprints.append(Fingerprint(
                tortured=tortured, expected=row.get("expected", ""),
                family=family, subclass=subclass, sources=src, flags=flags,
                ambiguity=ambiguity, acronym=row.get("acronym", ""),
                note=row.get("note", ""),
                tokens=key[0], raw_tokens=tuple(t.raw for t in toks)))

    if not fingerprints:
        raise PhrasebookError(
            f"no fingerprints loaded from {data_dir} -- the dictionary is "
            "empty or its TSVs are missing. A screen with an empty dictionary "
            "must refuse, not report a clean paper.")

    index: dict[str, list] = {}
    for fp in fingerprints:
        index.setdefault(fp.tokens[0], []).append((fp.tokens, fp, None))
        folded = _plural_fold(fp.tokens)
        if folded is not None:
            index.setdefault(folded[0], []).append((folded, fp, "plural"))
    frozen = {k: tuple(sorted(v, key=lambda e: -len(e[0])))
              for k, v in index.items()}

    return Phrasebook(
        fingerprints=tuple(fingerprints), version=version,
        sha256=sha.hexdigest(), n_blocked=n_blocked, per_family=per_family,
        sources=tuple(sorted(sources)), data_dir=data_dir, index=frozen)


@lru_cache(maxsize=4)
def _load_cached(data_dir_str: str) -> Phrasebook:
    return _load_uncached(Path(data_dir_str))


def load_phrasebook(data_dir: str | Path | None = None) -> Phrasebook:
    """Load (and cache) the dictionary from `data_dir` (default: bundled)."""
    return _load_cached(str(Path(data_dir) if data_dir else DATA_DIR))


# ---------------------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------------------

def _match_at(fp_tokens: tuple[str, ...], tokens: list[Token], i: int,
              first_joined: bool) -> Optional[tuple[int, bool]]:
    """Try to match `fp_tokens` at position `i`.

    Returns (index of last consumed token, any_hyphen_join) or None. At a
    `line_hyphen_next` boundary the SOFT reading -- two text tokens joined as
    one word -- is also tried; only at actual line-break hyphens, so it cannot
    fire mid-prose.
    """
    ti = i
    joined = first_joined
    for k, ft in enumerate(fp_tokens):
        if k == 0 and first_joined:
            # caller already consumed tokens[i] + tokens[i+1] as fp_tokens[0]
            ti = i + 2
            continue
        if ti >= len(tokens):
            return None
        tok = tokens[ti]
        if tok.text == ft:
            ti += 1
            continue
        if (tok.line_hyphen_next and ti + 1 < len(tokens)
                and tok.text + tokens[ti + 1].text == ft):
            ti += 2
            joined = True
            continue
        return None
    return ti - 1, joined


def _case_ok(fp: Fingerprint, tokens: list[Token], i: int, j: int) -> bool:
    """`cs`-flagged fingerprints must reproduce the canonical casing exactly
    ("Regenerate response" is a UI artifact whose casing IS the fingerprint;
    the lowercase bigram belongs to ordinary prose)."""
    if "cs" not in fp.flags:
        return True
    raws = [t.raw for t in tokens[i:j + 1]]
    if len(raws) != len(fp.raw_tokens):  # hyphen-join changed the token count
        return "".join(raws).replace("-", "") == "".join(fp.raw_tokens)
    return tuple(raws) == fp.raw_tokens


def scan_text(text: str, book: Phrasebook) -> list[Match]:
    """All fingerprint matches in `text`, greedy left-to-right.

    Longest candidate wins at each position; a consumed span is not rescanned,
    so one stretch of text yields one match. Every Match reports the CANONICAL
    fingerprint; generated variants surface only in `variant`.
    """
    tokens = tokenize(text)
    matches: list[Match] = []
    i = 0
    n = len(tokens)
    while i < n:
        tok = tokens[i]
        candidates: list[tuple[tuple[str, ...], Fingerprint, Optional[str], bool]] = [
            (tup, fp, var, False) for tup, fp, var in book.index.get(tok.text, ())]
        if tok.line_hyphen_next and i + 1 < n:
            joined_first = tok.text + tokens[i + 1].text
            candidates += [(tup, fp, var, True)
                           for tup, fp, var in book.index.get(joined_first, ())]
        best: Optional[tuple[int, Fingerprint, Optional[str]]] = None
        for tup, fp, var, first_joined in candidates:
            hit = _match_at(tup, tokens, i, first_joined)
            if hit is None:
                continue
            j, hyphen_joined = hit
            if not _case_ok(fp, tokens, i, j):
                continue
            variant = var
            if hyphen_joined:
                variant = "line_hyphenation" if var is None else var
            if best is None or j > best[0]:
                best = (j, fp, variant)
        if best is None:
            i += 1
            continue
        j, fp, variant = best
        matches.append(Match(
            fingerprint=fp, start=tokens[i].start, end=tokens[j].end,
            matched_text=text[tokens[i].start:tokens[j].end], variant=variant))
        i = j + 1
    return matches


def context_snippet(text: str, start: int, end: int, width: int = 80) -> str:
    """±`width` chars of whitespace-collapsed context around a span."""
    lo, hi = max(0, start - width), min(len(text), end + width)
    snippet = " ".join(text[lo:hi].split())
    prefix = "…" if lo > 0 else ""
    suffix = "…" if hi < len(text) else ""
    return f"{prefix}{snippet}{suffix}"
