"""Named refusals for unsupported legacy/raw-data formats."""

UNREADABLE = {
    ".doc": "legacy binary Word format (only .docx is readable)",
    ".xls": (
        "legacy binary Excel format; openpyxl reads only .xlsx/.xlsm. "
        "Re-saving it as .xlsx would make it analysable"
    ),
    ".zip": "archive; unpack it before analysing",
    ".tex": "LaTeX source; not a data table",
}
