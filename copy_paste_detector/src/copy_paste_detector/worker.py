"""One killable detection process, invoked by the batch coordinator."""

import json
import sys

from .paper import detect_paper_duplication
from .readers import DetectionLimits
from .storage import atomic_json


def main():
    request = json.load(sys.stdin)
    try:
        result = detect_paper_duplication(
            request["files"],
            paper_id=request["paper_id"],
            data_context=request.get("data_context", "unknown"),
            limits=DetectionLimits(**request.get("limits", {})),
            max_row_pairs=request.get("max_row_pairs", 0),
        )
    except Exception as exc:
        result = {
            "error": f"{type(exc).__name__}: {exc}",
            "severity": "indeterminate",
            "coverage": {"status": "not_evaluable"},
        }
    atomic_json(request["output"], result)
    return int(bool(result.get("error")))


if __name__ == "__main__":
    raise SystemExit(main())
