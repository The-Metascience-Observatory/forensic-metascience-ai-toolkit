"""LaTeX-flavoured extractor output, normalised so the floor can read it.

WHY THIS IS SAFE WHEN THE GLYPH REPAIRS WERE NOT. `glyphs.proven_repairs`
refuses to map a raw control byte globally, because a font glyph index means
whatever that font says: MEASURED, `\\x06` is `±` in three corpus papers and a
DECIMAL POINT in a fourth. A LaTeX command name is the opposite kind of thing --
it is a STANDARD. `\\pm` means `±` in every document that has ever been written,
so the mapping needs no per-document proof. This is the same class as decoding
`&lt;`, not the same class as guessing at `/C6`.

WHY IT IS NEEDED. Mathpix returns mathematics as LaTeX rather than Unicode, which
is arguably better for forensics -- `\\pm` is unambiguous where a rendered `±`
could itself be a mis-recognition. But `completeness.BODY_PATTERNS` matches
printed text, so a paper arriving as `$65 \\pm 1.17$` yields NOTHING. MEASURED on
10.1007--s00702-004-0248-2: the text layer gives our floor 40 statistics, Mistral
39, and Mathpix 2. The extraction was excellent and our reader could not see it.

MEASURED vocabulary over the 22 Mathpix outputs: 2,253 inline `$...$` spans, no
display math, and a short command list led by `\\pm` (678), `\\mathrm` (910),
`\\mu` (110) and `\\beta` (80). Twenty mappings cover essentially all of it.

LENGTH-PRESERVING, the same discipline as every other repair here: each
substitution is padded back to the width of what it replaced, so an offset into
the normalised text is an offset into the original and `raw` can still be sliced
from the source a reader would recognise.
"""

from __future__ import annotations

import re

#: Commands that carry a CHARACTER. Everything here is a standard LaTeX name
#: with one unambiguous Unicode counterpart.
_CHAR = {
    "pm": "±", "mp": "∓", "leq": "≤", "le": "≤", "geq": "≥", "ge": "≥",
    "neq": "≠", "ne": "≠", "times": "×", "cdot": "·", "div": "÷",
    "approx": "≈", "sim": "∼", "propto": "∝", "infty": "∞",
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ", "epsilon": "ε",
    "mu": "µ", "sigma": "σ", "tau": "τ", "phi": "φ", "chi": "χ", "eta": "η",
    "lambda": "λ", "theta": "θ", "rho": "ρ", "omega": "ω", "kappa": "κ",
    "Delta": "Δ", "Sigma": "Σ", "Omega": "Ω", "Phi": "Φ",
    "circ": "°", "degree": "°", "dagger": "†", "ddagger": "‡", "S": "§",
    "varnothing": "∅", "emptyset": "∅", "star": "*", "ast": "*",
    "percent": "%",
}

#: Commands that carry only FORMATTING. Their argument is kept; the command
#: itself becomes whitespace. Dropping the wrapper is what lets `\mathrm{N}=68`
#: read as `N=68`.
_DROP = {
    "mathrm", "mathbf", "mathit", "mathsf", "mathtt", "boldsymbol", "text",
    "textbf", "textit", "operatorname", "left", "right", "quad", "qquad",
    "displaystyle", "scriptstyle", "rm", "bf", "it", "hspace", "vspace",
    "normalsize", "small", "footnotesize", "large", "Large",
}

_CMD = re.compile(r"\\([a-zA-Z]+)")
#: `$`, `{`, `}` carry no content of their own once the commands are handled.
_PUNCT = re.compile(r"[${}]")
#: A single escaped character -- `\%`, `\&`, `\_` -- is that character.
_ESCAPED = re.compile(r"\\([%&_#])")


def _pad(replacement: str, width: int) -> str:
    """`replacement`, padded with spaces to exactly `width` characters."""
    if len(replacement) >= width:
        return replacement[:width]
    return replacement + " " * (width - len(replacement))


def to_unicode(text: str) -> str:
    """`text` with LaTeX notation rendered as the characters it stands for.

    Length-preserving. Whitespace is used as the padding because every
    `BODY_PATTERNS` entry already tolerates `\\s*` around an operator, so a
    widened gap changes nothing about what matches.
    """
    if not text or "\\" not in text and "$" not in text:
        return text or ""

    def sub_cmd(m: "re.Match") -> str:
        name = m.group(1)
        whole = m.group(0)
        if name in _CHAR:
            return _pad(_CHAR[name], len(whole))
        if name in _DROP:
            return " " * len(whole)
        # An unrecognised command is dropped rather than guessed at. It cannot
        # be a number, and leaving the backslash in would only give the floor a
        # token it will never match.
        return " " * len(whole)

    out = _ESCAPED.sub(lambda m: _pad(m.group(1), len(m.group(0))), text)
    out = _CMD.sub(sub_cmd, out)
    out = _PUNCT.sub(" ", out)
    return out


def looks_like_latex(text: str, min_spans: int = 3) -> bool:
    """Is this document worth running `to_unicode` over at all?

    Cheap enough to run on every paper, and it keeps the normalisation off text
    that never needed it -- a `$` in a cost table is not mathematics.
    """
    if not text:
        return False
    return len(re.findall(r"\$[^$\n]{1,80}\$", text)) >= min_spans or \
        len(_CMD.findall(text)) >= min_spans
