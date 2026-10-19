"""Figure extraction, from the optional image analysis package.

With the package installed this module IS
`metascience_observatory_image_analysis.extraction.figures` (an alias, so its
detector fingerprint and every caller see one module). Without it, only the OCR
provenance channel names are defined -- `extraction.ocr` re-exports them and
the statistical gates read them -- and anything else raises
`ImagePluginUnavailable` by name.
"""
import sys as _sys

from ..image_plugin import ImagePluginUnavailable, INSTALL_HINT, available as _available, load as _load

if _available():
    _impl = _load("extraction.figures")
    if __name__ == "__main__":
        raise SystemExit(_impl.main())
    _sys.modules[__name__] = _impl
else:
    OCR_TABLE = "ocr_table"  # transcribed by OCR from a table image
    OCR_TEXT = "ocr_text"    # transcribed by OCR from body/figure text
    TRANSCRIBED = frozenset({OCR_TABLE, OCR_TEXT})
    #: Median relative error of a value read off a figure, from the image
    #: package's figure-extractor benchmark (pinned equal by its test suite);
    #: `effect_size` widens tolerances by it for measured provenance.
    FIGURE_ERROR_BUDGET = {"central": 0.0044, "dispersion": 0.0389}

    def __getattr__(name):
        if name.startswith("__"):
            raise AttributeError(name)
        raise ImagePluginUnavailable(f"extraction.figures.{name}: {INSTALL_HINT}")
