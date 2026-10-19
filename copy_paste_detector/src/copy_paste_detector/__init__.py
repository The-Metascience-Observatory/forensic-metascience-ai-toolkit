"""Independent detection of copy-paste signatures in raw data."""

from .detector import detect_raw_duplication
from .highlight import highlight_workbook
from .paper import detect_paper_duplication
from .readers import DetectionLimits

__all__ = [
    "detect_raw_duplication",
    "detect_paper_duplication",
    "DetectionLimits",
    "highlight_workbook",
]
__version__ = "0.2.0"
