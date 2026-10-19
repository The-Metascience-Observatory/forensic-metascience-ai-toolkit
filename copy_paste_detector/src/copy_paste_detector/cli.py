"""Command-line entry point; JSON on stdout, diagnostics on stderr."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import detect_raw_duplication, highlight_workbook
from .constants import _CONTEXTS, _MAX_ROW_PAIRS
from .readers import DetectionLimits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect copied raw-data rows, runs, and values.")
    parser.add_argument("path", type=Path, help="Input .csv/.tsv/.xlsx/.xlsm/.docx")
    parser.add_argument("--sheet", help="Restrict to one worksheet")
    parser.add_argument(
        "--exclude-column",
        "-x",
        action="append",
        dest="exclude_columns",
        help="Column shared by design; repeat to exclude multiple columns",
    )
    parser.add_argument("--data-context", choices=_CONTEXTS, default="unknown")
    parser.add_argument(
        "--max-row-pairs",
        type=int,
        default=_MAX_ROW_PAIRS,
        help="Row-pair comparison budget (default: %(default)s)",
    )
    parser.add_argument("--highlight-out", type=Path, help="Write a highlighted .xlsx copy")
    parser.add_argument("--output", "-o", type=Path, help="Write JSON here instead of stdout")
    parser.add_argument(
        "--run-dir", type=Path, help="Write a portable immutable run with source evidence"
    )
    for name, default in (("max-rows", 5000), ("max-columns", 100), ("max-sheets", 8)):
        parser.add_argument("--" + name, type=int, default=default, help="0 = unlimited")
    args = parser.parse_args(argv)
    try:
        args.limits = DetectionLimits(args.max_rows, args.max_columns, args.max_sheets)
    except ValueError as exc:
        parser.error(str(exc))
    import uuid
    from datetime import datetime, timezone

    portable_id = "cp_" + uuid.uuid4().hex
    started_at = datetime.now(timezone.utc).isoformat()
    if args.max_row_pairs < 1:
        parser.error("--max-row-pairs must be positive")
    if args.output and args.output.resolve() == args.path.resolve():
        parser.error("--output must differ from the input path")
    if args.highlight_out and args.highlight_out.resolve() == args.path.resolve():
        parser.error("--highlight-out must differ from the input path")
    if args.highlight_out and args.output and args.highlight_out.resolve() == args.output.resolve():
        parser.error("JSON and highlighted-workbook outputs must use different paths")
    if args.run_dir and args.path.is_file():
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory(prefix="copy-paste-run-") as temporary:
            source = Path(temporary) / args.path.name
            shutil.copy2(args.path, source)
            return _run(args, portable_id, started_at, source)
    return _run(args, portable_id, started_at, args.path)


def _run(args, portable_id, started_at, source):
    try:
        result = detect_raw_duplication(
            str(source),
            sheet=args.sheet,
            exclude_columns=args.exclude_columns,
            data_context=args.data_context,
            max_row_pairs=args.max_row_pairs,
            limits=args.limits,
        )
    except Exception as exc:
        # Libraries may raise on corrupt files. A CLI must not turn that into
        # an apparent clean result or emit an implementation traceback.
        result = {"error": f"{type(exc).__name__}: {exc}", "severity": "indeterminate"}
    if source != args.path:
        result = json.loads(json.dumps(result).replace(str(source), str(args.path)))
    failed = bool(result.get("error"))
    if args.highlight_out and not failed:
        if args.highlight_out.suffix.lower() != ".xlsx":
            highlight = {"error": "--highlight-out must have an .xlsx extension"}
        else:
            highlight = highlight_workbook(source, result["duplicate_groups"], args.highlight_out)
        result["highlight"] = highlight
        if highlight.get("error"):
            print(highlight["error"], file=sys.stderr)
            failed = True
    try:
        if args.run_dir:
            from .portable import save_run

            save_run(
                args.run_dir,
                portable_id,
                started_at,
                source,
                result,
                {
                    "sheet": args.sheet,
                    "exclude_columns": args.exclude_columns,
                    "data_context": args.data_context,
                    "max_row_pairs": args.max_row_pairs,
                    "limits": __import__("dataclasses").asdict(args.limits),
                },
                args.highlight_out,
            )
        payload = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
        if args.output:
            args.output.write_text(payload, encoding="utf-8")
        else:
            sys.stdout.write(payload)
    except (OSError, ValueError) as exc:
        print(f"Could not write JSON: {exc}", file=sys.stderr)
        return 1
    if result.get("error"):
        print(result["error"], file=sys.stderr)
    return 1 if failed else 0
