"""Eval harness: run the pipeline on the gold-standard papers and score it.

Per fixture:
  1. Prepare a scratch paper dir under benchmarks/paper_reviews/runs/<paper>/paper/ with the PDF
     and a pre-extracted body.md (never mutates benchmarks/paper_reviews/papers/).
  2. Run analyze_paper(mode="parallel") and write the standard review files.
Outputs benchmarks/paper_reviews/runs/scorecard.json and prints a
summary table. Every scorecard records what produced it -- `pipeline_version`,
`mode`, `backend`, `model` -- because until 2026-09-02 none did, and the only
way to learn that the three non-apple_cider fixtures had been scored on grok
rather than claude was to open each run's run_meta.json by hand.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import shutil
import sys
from pathlib import Path
from typing import Any

import yaml

from ..agent import analyze_paper
from ..extraction.pdf import extract_text_with_tables
from ..version import pipeline_version
from . import deterministic
from .judge import judge_paper

#: The benchmark's home, relative to the repo root: the fixtures (gold labels),
#: the papers and human reviews they cite, and the archived runs + scorecards.
#: Declared once; the CLI's --skip-analysis precheck reads the same constants.
BENCHMARK_DIR = Path("benchmarks") / "paper_reviews"
FIXTURES_DIR = BENCHMARK_DIR / "fixtures"
RUNS_DIR = BENCHMARK_DIR / "runs"

#: Where the run lives under benchmarks/paper_reviews/runs/<paper>/, and the scorecard beside it.
#: A dict with one entry rather than two bare constants: `review_layout`
#: REFUSES an unknown mode, which is what stops a typo silently writing a run
#: into a directory nothing reads.
MODE_REVIEW_DIRS = {"parallel": ("forensic_review", "scorecard.json")}


def review_layout(mode: str) -> tuple[str, str]:
    """`(review dirname, scorecard filename)` for an eval mode; refuses others."""
    try:
        return MODE_REVIEW_DIRS[mode]
    except KeyError:
        raise ValueError(
            f"eval mode {mode!r} is not one of {sorted(MODE_REVIEW_DIRS)}") from None


def repo_root() -> Path:
    # src/metascience_agent/evaluation/harness.py -> repo root is 3 up from src
    return Path(__file__).resolve().parents[3]


def load_fixtures(fixtures_dir: Path, only: str | None = None) -> list[dict]:
    fixtures = []
    for path in sorted(fixtures_dir.glob("*.yaml")):
        fixture = yaml.safe_load(path.read_text())
        fixture["_path"] = str(path)
        if only and fixture.get("paper") != only:
            continue
        fixtures.append(fixture)
    return fixtures


def prepare_paper_dir(fixture: dict, run_dir: Path, root: Path) -> Path:
    """Create benchmarks/paper_reviews/runs/<paper>/paper/ with the PDF + extracted body.md."""
    pdf_src = root / fixture["pdf"]
    if not pdf_src.exists():
        raise FileNotFoundError(f"fixture PDF not found: {pdf_src}")

    paper_dir = run_dir / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    pdf_dst = paper_dir / pdf_src.name
    if not pdf_dst.exists():
        shutil.copy2(pdf_src, pdf_dst)

    body_md = paper_dir / "body.md"
    if not body_md.exists():
        extracted = extract_text_with_tables(pdf_dst, max_chars=1_000_000)
        parts = [extracted["text"]]
        if extracted["tables"]:
            parts.append("\n\n## Extracted tables\n")
            for t in extracted["tables"]:
                parts.append(f"\n### Page {t['page']}, table {t['table_num']}\n")
                for row in t["data"]:
                    parts.append("| " + " | ".join(str(c) for c in row) + " |")
        body_md.write_text("\n".join(parts))
    return paper_dir


async def eval_one(
    fixture: dict,
    runs_dir: Path,
    root: Path,
    budget_usd: float | None,
    timeout: int | None,
    model: str | None,
    skip_analysis: bool,
    verbose: bool,
    backend=None,
    mode: str = "parallel",
    pipeline=None,
    judge_backend: str = None,
    judge_model: str = None,
) -> dict:
    name = fixture["paper"]
    judge_backend = judge_backend or JUDGE_BACKEND
    judge_model = judge_model or JUDGE_MODEL
    run_dir = runs_dir / name
    review_dirname, scorecard_name = review_layout(mode)
    review_dir = run_dir / review_dirname

    from ..llm_backend import resolve_backend
    _be = resolve_backend(backend)
    if not model:
        # ONE resolution, used by the analysis AND the judge. "sonnet" is
        # the measured aligned-down default for claude ($4.97 vs $22.01 on
        # fable); any other backend takes its own default -- forwarding the
        # claude name to grok made its CLI exit with "unknown model id"
        # before spending a cent (measured 2026-08-21, cerebrolysin_flow).
        model = "sonnet" if _be.name == "claude" else _be.default_model
    print(f"[{name}] preparing inputs...")
    paper_dir = prepare_paper_dir(fixture, run_dir, root)

    analysis_cost = 0.0
    if skip_analysis and (review_dir / "report.md").exists():
        print(f"[{name}] reusing existing analysis in {review_dir}")
        report_md = (review_dir / "report.md").read_text()
        findings: Any = None
        # v2 first (the parallel pipeline / migrated runs); v1 fallback.
        v2_path = review_dir / "findings.v2.json"
        findings_path = review_dir / "findings.json"
        if v2_path.exists():
            findings = json.loads(v2_path.read_text())
        elif findings_path.exists():
            findings = json.loads(findings_path.read_text())
        run_meta_path = review_dir / "run_meta.json"
        verdict = None
        run_meta: dict = {}
        if isinstance(findings, dict) and \
                str(findings.get("schema_version")) == "2.0":
            verdict = (findings.get("adjudication") or {}).get("verdict")
        if run_meta_path.exists():
            run_meta = json.loads(run_meta_path.read_text())
            verdict = verdict or run_meta.get("stages", {}).get(
                "editorial", {}).get("verdict")
            analysis_cost = float(run_meta.get("total_cost_usd") or 0)
    else:
        from ..llm_backend import resolve_backend
        be = resolve_backend(backend)
        if budget_usd is not None and not be.supports_budget:
            # Grok hard-rejects --max-budget-usd (BudgetUnsupported), and the
            # eval CLI always defaults one -- without this the documented
            # `metascience eval --backend grok` invocation errored before
            # spending a cent, which is the wrong direction to fail.
            print(f"[{name}] {be.name} has no spend cap; running WITHOUT "
                  f"the ${budget_usd} budget")
            budget_usd = None
        print(f"[{name}] running the {mode} analysis...")
        result = await analyze_paper(
            str(paper_dir),
            verbose=verbose,
            timeout=timeout,
            mode=mode,
            budget_usd=budget_usd,
            model=model,
            backend=backend,
            **({"pipeline": pipeline} if pipeline is not None else {}),
        )
        run_meta = result.get("run_meta") or {}
        from ..parallel import write_parallel_outputs
        write_parallel_outputs(result, review_dir)
        report_md = (review_dir / "report.md").read_text()
        findings = result.get("findings_v2")
        verdict = result.get("verdict")
        analysis_cost = result.get("total_cost_usd", 0.0)

    print(f"[{name}] deterministic checks...")
    det = deterministic.run_all(findings, report_md, verdict, fixture,
                                paper_dir=paper_dir)

    print(f"[{name}] LLM judge...")
    judged = await judge_paper(
        fixture, report_md, findings, model=judge_model, verbose=verbose,
        backend=judge_backend, effort=JUDGE_EFFORT,
    )

    scorecard = {
        "paper": name,
        # What produced this scorecard. `pipeline_version` describes the
        # ARCHIVED run (its run_meta stamp), never the code scoring it now:
        # re-scoring an old run with today's number would attribute the
        # findings to code that did not produce them.
        # Which pipeline produced this scorecard (None = the flag default,
        # i.e. `full`): an arm of a tool_access comparison is otherwise
        # indistinguishable from a default run in the scorecard.
        "pipeline": ((run_meta.get("pipeline") or {}).get("name")
                     if run_meta else None),
        "pipeline_digest": ((run_meta.get("pipeline") or {}).get("digest")
                            if run_meta else None),
        "pipeline_version": pipeline_version(run_meta) if run_meta
                            else pipeline_version({}),
        "mode": mode,
        "backend": _be.name,
        # The GRADER, fixed whatever produced the review (see JUDGE_BACKEND).
        "judge_backend": judge_backend,
        "judge_model": judge_model,
        "judge_effort": JUDGE_EFFORT,
        "model": model,
        "verdict": verdict,
        "verdict_expected": fixture["verdict_expected"],
        "verdict_match": det["verdict"]["passed"],
        "deterministic": det,
        "judge": judged,
        "recall_weighted": judged.get("recall_weighted"),
        "recall_weighted_reachable": judged.get("recall_weighted_reachable"),
        "num_false_positives": judged.get("num_false_positives"),
        "cost_usd": {
            "analysis": analysis_cost,
            "judge": judged.get("cost_usd", 0.0),
        },
    }
    (run_dir / scorecard_name).write_text(
        json.dumps(scorecard, indent=2, default=str)
    )
    return scorecard


def print_summary(scorecards: list[dict]) -> None:
    print("\n" + "=" * 78)
    header = (
        f"{'paper':<16} {'mode':<10} {'verdict':<15} {'match':<6} "
        f"{'recall':<7} {'recall*':<8} {'FPs':<4} {'det':<4} {'cost $':<8}"
    )
    print(header)
    print("-" * 78)
    for sc in scorecards:
        cost = sum(v or 0 for v in sc["cost_usd"].values())
        print(
            f"{sc['paper']:<16} "
            f"{str(sc.get('mode', 'parallel'))[:10]:<10} "
            f"{str(sc['verdict']):<15} "
            f"{'✓' if sc['verdict_match'] else '✗':<6} "
            f"{str(sc.get('recall_weighted')):<7} "
            f"{str(sc.get('recall_weighted_reachable')):<8} "
            f"{str(sc.get('num_false_positives')):<4} "
            f"{'✓' if sc['deterministic']['passed'] else '✗':<4} "
            f"{cost:<8.2f}"
        )
    print("-" * 78)
    print("recall  = weighted recall over all expected findings")
    print("recall* = weighted recall over findings reachable without web access")


def _pipeline(spec):
    """`--pipeline` (a shipped name or a YAML path) as a config, or None."""
    if not spec:
        return None
    from ..pipeline_config import load
    config = load(spec)
    if not config.complete_review:
        raise SystemExit(
            f"--pipeline {spec!r} is not a complete review; the gold fixtures "
            "score complete reviews only")
    return config


async def run_eval(args: argparse.Namespace) -> int:
    root = repo_root()
    fixtures_dir = Path(args.fixtures) if args.fixtures else root / FIXTURES_DIR
    runs_dir = Path(args.runs_dir) if args.runs_dir else root / RUNS_DIR

    fixtures = load_fixtures(fixtures_dir, only=args.paper)
    if not fixtures:
        print(f"No fixtures found in {fixtures_dir}"
              + (f" for paper={args.paper}" if args.paper else ""), file=sys.stderr)
        return 1

    mode = "parallel"
    _, aggregate_name = review_layout(mode)

    scorecards = []
    for fixture in fixtures:  # sequential: keeps output readable, cost visible
        scorecards.append(await eval_one(
            fixture, runs_dir, root,
            budget_usd=args.budget_usd,
            timeout=args.timeout,
            model=args.model,
            skip_analysis=args.skip_analysis,
            verbose=args.verbose,
            backend=getattr(args, "backend", None),
            judge_backend=getattr(args, "judge_backend", None),
            judge_model=getattr(args, "judge_model", None),
            mode=mode,
            pipeline=_pipeline(getattr(args, "pipeline", None)),
        ))

    (runs_dir / aggregate_name).write_text(
        json.dumps(scorecards, indent=2, default=str)
    )
    print_summary(scorecards)
    print(f"\nScorecards written to {runs_dir}/")

    all_ok = all(
        sc["verdict_match"] and sc["deterministic"]["passed"] for sc in scorecards
    )
    return 0 if all_ok else 2


#: ONE JUDGE FOR EVERY BACKEND. The judge used to follow `--backend`, so a
#: Grok review was graded by Grok and a Claude review by Claude, and recall
#: across backends compared two different graders. MEASURED 2026-10-13 on 25
#: apple_cider/airforce/wound_healing/cerebrolysin_flow runs re-graded by
#: Sonnet: the Grok judge returned recall 0.0 with empty notes on a run that
#: filed 26 findings (Sonnet: 0.462), and graded one review 0.273 that Sonnet
#: graded 0.818. Override only to study the judge itself.
JUDGE_BACKEND = "claude"
JUDGE_MODEL = "sonnet"
#: HIGH (Dan, 2026-10-14). Medium was tried first to save usage and graded a
#: Claude airforce run 0.0 that had filed "Survey percentages imply n=73 and
#: 74, but Table III headers state n=80 and 79" -- the critical gold finding
#: every other run was credited for. Judging is a small share of a run's
#: usage; a mis-grade swings recall by 0.4 and corrupts any comparison.
JUDGE_EFFORT = "high"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper", help="Run only this fixture (apple_cider | airforce | wound_healing)")
    parser.add_argument("--fixtures", help="Fixtures directory (default: benchmarks/paper_reviews/fixtures)")
    parser.add_argument("--runs-dir", help="Output directory (default: benchmarks/paper_reviews/runs)")
    parser.add_argument("--max-budget-usd", "--budget-usd", dest="budget_usd", type=float, default=8.0,
                        help="Per-paper analysis budget (default: 8.0)")
    parser.add_argument("--timeout", type=int, default=1800,
                        help="Per-stage timeout seconds (default: 1800)")
    parser.add_argument("--model", default=None,
                        help="default: sonnet on claude, the backend's own "
                             "default otherwise")
    parser.add_argument("--judge-backend", default=None,
                        help=f"Backend that GRADES the review (default {JUDGE_BACKEND}, "
                             "whatever --backend produced it)")
    parser.add_argument("--judge-model", default=None,
                        help=f"Judge model (default {JUDGE_MODEL})")
    parser.add_argument("--backend", default=None,
                        help="LLM CLI: claude (default) or grok")
    parser.add_argument("--pipeline", default=None,
                        help="A complete-review pipeline (shipped name or YAML "
                             "path), e.g. full_brief; default: the flag default")
    parser.add_argument("--skip-analysis", action="store_true",
                        help="Rescore existing benchmarks/paper_reviews/runs/<paper>/forensic_review outputs without re-running the pipeline")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return asyncio.run(run_eval(args))


if __name__ == "__main__":
    sys.exit(main())
