"""Remove the operator's machine from a string bound for someone else.

WHY THIS IS ITS OWN MODULE. The function lived in `bundle.py` and was applied
to the bundle's COPY of the review -- `<review>_bundle/analysis/report.md` --
and to nothing else. The file the pipeline actually writes,
`forensic_review/report.md`, was never scrubbed, and `bundle._FILE_BLURBS`
describes that file as "The review itself -- what you would read". It is the
one people forward.

MEASURED: `/mnt/c/Users/gregs/...` appears in archived reports on this
checkout, inside a reproduction-failure message printed directly under an
`IMPOSSIBLE` heading. A forensic review is a document about someone else's
work that may end up in front of that person, an editor, or a journal's
integrity office; the operator's home directory is not evidence about the
paper and has no business travelling with it.

Three surfaces need the identical function now -- the bundle, the review
written to disk, and the artifact published to the website -- and a redaction
rule with three implementations is a redaction rule with three failure modes.
Same argument `disclaimer.py` makes for keeping one copy of the disclaimer.

WHAT IS DELIBERATELY NOT SCRUBBED. The paper's own text is EVIDENCE and is
left byte-exact: a substitution inside it would move every character offset
the viewer's click-to-source sync does arithmetic on, so a finding's anchor
would land on the wrong sentence. `bundle._UNSCRUBBED_KEYS` names those keys.
"""

from __future__ import annotations

import re

#: An absolute path into somebody's home directory says who ran this and on
#: what machine. Replaced rather than deleted so the shape of the path survives
#: and a reader substitutes their own checkout.
#:
#: The lookbehind keeps a URL out of it: `https://osf.io/home/xyz` has `/home/`
#: in it and is the PAPER's shared-data link, not our machine. A path we care
#: about always begins a token -- after a space, a quote, an `=`, or the `//`
#: of a `file://` URI -- never immediately after a word character or a dot.
HOME_RE = re.compile(
    r"(?<![\w.:])("
    r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\"']+"   # C:\Users\name
    r"|/mnt/[a-z]/Users/[^/\s\"']+"             # /mnt/c/Users/name (WSL)
    r"|/(?:home|Users)/[^/\s\"']+"              # /home/name, /Users/name
    r")"
)

#: A session UUID identifies one run on one machine in the vendor's logs. It is
#: an operator credential-adjacent identifier, not evidence about the paper.
UUID_RE = re.compile(
    r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I)


def scrub(text: str) -> str:
    """Remove the operator's machine from a string bound for someone else."""
    return UUID_RE.sub("<session-id>", HOME_RE.sub("<home>", str(text)))
