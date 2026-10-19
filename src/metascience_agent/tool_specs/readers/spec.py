"""The `readers` tool family: extract_figures, extract_pdf, extract_xml, get_table, extract_html, extract_supplement, get_supplement_table.

Each ToolSpec below was moved verbatim from registry.py (Phase 3a of the
modular refactor). Its MCP description and integrity card live in
TOOL.md beside this file; the implementation is in `metascience_agent.extraction.{html,jats,pdf,supplements_read}` and, for
`extract_figures`, the optional image analysis package (`extraction.figures`).
"""

from __future__ import annotations

from ...image_plugin import available as _image_available, load as _image_load, unavailable_record

if _image_available():
    extract_figures = _image_load("extraction.figures").extract_figures
else:
    def extract_figures(*args, **kwargs):
        """Figure extraction belongs to the image analysis package, not installed here."""
        return unavailable_record("extract_figures (figure extraction)")

from ...extraction.html import extract_html_text_with_tables
from ...extraction.jats import extract_xml_text_with_tables, get_table
from ...extraction.pdf import extract_text_with_tables
from ...extraction.supplements_read import extract_supplement, get_supplement_table
from ...registry import (
    REQUIRED,
    SCIENCE_AGENT,
    STAGE1,
    STAGE2,
    Param,
    ToolSpec,
)
from .. import descriptions

DESCRIPTIONS = descriptions(__file__)

SPECS = (
    ToolSpec(
        name="extract_figures",
        fn=extract_figures,
        description=DESCRIPTIONS["extract_figures"],
        params=(
            Param("pdf_path", str, REQUIRED),
            Param("out_dir", str, None),
            Param("dpi", int, 150),
            Param("render_pages", bool, True),
        ),
        stages=frozenset({STAGE1}),
        cli="extract-figures",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="extract_pdf",
        fn=extract_text_with_tables,
        description=DESCRIPTIONS["extract_pdf"],
        params=(
            Param("pdf_path", str, REQUIRED),
            Param("max_chars", int, 50000),
            Param("first_page", int, None),
            Param("last_page", int, None),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        cli="extract",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="extract_xml",
        fn=extract_xml_text_with_tables,
        description=DESCRIPTIONS["extract_xml"],
        params=(
            Param("xml_path", str, REQUIRED),
            Param("max_chars", int, 50000),
            Param("first_section", int, None),
            Param("last_section", int, None),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        cli="extract-xml",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="get_table",
        fn=get_table,
        description=DESCRIPTIONS["get_table"],
        params=(
            Param("xml_path", str, REQUIRED),
            Param("table_num", int, REQUIRED),
            Param("first_row", int, None),
            Param("last_row", int, None),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        cli="get-table",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="extract_html",
        fn=extract_html_text_with_tables,
        description=DESCRIPTIONS["extract_html"],
        params=(
            Param("html_path", str, REQUIRED),
            Param("max_chars", int, 50000),
            Param("first_section", int, None),
            Param("last_section", int, None),
        ),
        stages=frozenset({STAGE1, STAGE2, SCIENCE_AGENT}),
        cli="extract-html",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="extract_supplement",
        fn=extract_supplement,
        description=DESCRIPTIONS["extract_supplement"],
        params=(
            Param("path", str, REQUIRED),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        cli="extract-supplement",
        cli_required_flags=frozenset(),
    ),
    ToolSpec(
        name="get_supplement_table",
        fn=get_supplement_table,
        description=DESCRIPTIONS["get_supplement_table"],
        params=(
            Param("path", str, REQUIRED),
            Param("table", str, REQUIRED),
            Param("first_row", int, None),
            Param("last_row", int, None),
        ),
        stages=frozenset({STAGE1, STAGE2}),
        cli="get-supplement-table",
        cli_required_flags=frozenset(),
    ),
)
