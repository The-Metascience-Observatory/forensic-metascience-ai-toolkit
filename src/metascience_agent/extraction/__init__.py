"""PDF, XML and statistics extraction utilities."""

from .jats import (
    extract_xml_text,
    extract_xml_tables,
    extract_xml_text_with_tables,
    find_xml,
    paper_text,
)
from .pdf import extract_text, extract_tables
from .schemas import (
    ExtractedStatistic,
    GroupStatistics,
    TTestData,
    ANOVAData,
    ChiSquaredData,
    PercentageData,
    Location,
)

__all__ = [
    "extract_text",
    "extract_tables",
    "extract_xml_text",
    "extract_xml_tables",
    "extract_xml_text_with_tables",
    "find_xml",
    "paper_text",
    "ExtractedStatistic",
    "GroupStatistics",
    "TTestData",
    "ANOVAData",
    "ChiSquaredData",
    "PercentageData",
    "Location",
]
