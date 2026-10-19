"""The `tracks` tool family: analyze_paper_images, detect_tortured_phrases.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.tools.tortured_phrases` and, for
`analyze_paper_images`, the optional image analysis package (`image_forensics.image_analysis`).
"""

from __future__ import annotations

from ...image_plugin import available as _image_available, load as _image_load, unavailable_record

if _image_available():
    analyze_paper_images = _image_load("image_forensics.image_analysis").analyze_paper_images
else:
    def analyze_paper_images(*args, **kwargs):
        """The image-duplication detector belongs to the image analysis package, not installed here."""
        return unavailable_record("analyze_paper_images (image duplication detection)")

from ...registry import (
    REQUIRED,
    Param,
    ToolSpec,
)
from ...tools.tortured_phrases import detect_tortured_phrases
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="analyze_paper_images",
        fn=analyze_paper_images,
        description=DESCRIPTIONS["analyze_paper_images"],
        params=(
            Param("pdf_path", str, REQUIRED),
            Param("out_dir", str, None,
                  help="Where panel PNGs and panels.json land (default: "
                       "<paper_dir>/panels/)."),
            Param("stated_reuse", bool, False, guard=True,
                  help="The paper states these panels re-show earlier ones; "
                       "the result is then capped at indeterminate."),
            Param("si_pdfs", list, None,
                  help="Supplement PDFs to harvest into the same pool."),
            Param("paper_dir", str, None,
                  help="Paper directory; enables the supplement-container "
                       "media harvest (.docx/.epub zips, loose images)."),
            Param("captions", list, None,
                  help="Figure captions; scanned for stated-reuse phrases "
                       "(representative / re-shown / as in Fig ...), which "
                       "drop one severity tier with a named caveat."),
            Param("max_panels", int, 200, withheld=True),
        ),
        # CLI-ONLY BY DESIGN (`registry.CLI_ONLY` above holds the
        # reason of record): the deterministic image track calls this in a
        # child subprocess, not the model — its findings reach stage 2 by
        # injection, already quarantined.
        stages=frozenset(),
        cli="image-analysis",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="detect_tortured_phrases",
        fn=detect_tortured_phrases,
        description=DESCRIPTIONS["detect_tortured_phrases"],
        params=(
            Param("paper_dir", str, None,
                  help="Paper directory; text is read via paper_text's "
                       "fallback chain (body.md > XML > HTML > PDF layer)."),
            Param("text", str, None,
                  help="Raw text to screen instead of a paper_dir."),
            Param("data_dir", str, None, withheld=True),
        ),
        # CLI-ONLY BY DESIGN (`registry.CLI_ONLY` above holds the
        # reason of record): the deterministic text track calls this in a
        # child subprocess concurrent with the sweep, not the model — its
        # findings reach stage 2 by injection, already quarantined.
        stages=frozenset(),
        cli="tortured-phrases",
        cli_required_flags=frozenset(),
    ),
)
