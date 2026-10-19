"""Figure-label normalisation for the publisher-XML reader.

`Fig. 3` / `Figure 3.` / `FIGURE 3A` -> `Figure 3A`; `Supplementary Fig. 3`
-> `Figure S3`. The image analysis package keys its figure-level joins on
exactly this spelling (`extraction.figures.canonical_figure_number`,
`supplementary_figure_number` and `pmc_figures.normalise_label` there). Those
files are part of that package's detector fingerprint and cannot import from
here without moving it, so this is a COPY, and the image package's test suite
pins that the two agree label for label (`test_host_label_agreement.py`). A
second normaliser agrees until the day it does not; that test is the day.
"""
from __future__ import annotations

import re

SUPPLEMENTARY_PREFIX = r"Supplement(?:al|ary)?|Supp\.?|Supporting"
_SUPPLEMENTARY_BEFORE_RE = re.compile(
    r"(?i)(?:^|[^A-Za-z])(?:" + SUPPLEMENTARY_PREFIX + r")\s*$")

_FIG_LABEL_RE = re.compile(
    r"(?i)\b(?:fig(?:ure)?s?\.?)\s*((?:[A-Z]\.?)?[0-9]+(?:[-–.][0-9]+)?)([A-Za-z])?")


def canonical_figure_number(num: str) -> str:
    """`S 1` -> `S1`, `03` -> `3`, `2–7` -> `2-7`, `2.10` -> `2-10`,
    `A1.1` -> `A1-1`. Raises ValueError on text that carries no digits."""
    txt = "".join(str(num).split()).upper().replace("–", "-")
    i = 0
    while i < len(txt) and txt[i].isalpha():
        i += 1
    prefix, rest = txt[:i], txt[i:]
    parts = [p for p in re.split(r"[.\-]+", rest) if p]
    if not parts or not all(p.isdigit() for p in parts):
        raise ValueError(f"not a figure number: {num!r}")
    return prefix + "-".join(str(int(p)) for p in parts)


def supplementary_figure_number(num: str, preceding: str) -> str:
    """`3` written after `Supplementary` -> `S3`; a letter already glued to
    the digits (`S1`, `A1`) is the authors' own and is kept as is."""
    txt = "".join(str(num).split())
    if not txt or not txt[0].isdigit():
        return num
    if _SUPPLEMENTARY_BEFORE_RE.search(preceding or ""):
        return "S" + txt
    return num


def normalise_label(label: str | None, fallback_index: int | None = None) -> str | None:
    """`Fig. 3` / `Figure 3.` / `FIGURE 3A` -> `Figure 3A`."""
    if label:
        m = _FIG_LABEL_RE.search(str(label))
        if m:
            num = supplementary_figure_number(m.group(1), str(label)[:m.start()])
            return f"Figure {canonical_figure_number(num)}{(m.group(2) or '').upper()}"
        return str(label).strip() or None
    return f"Figure {fallback_index}" if fallback_index else None
