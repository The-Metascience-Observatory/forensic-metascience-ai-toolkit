# System audit — 2026-09-05

Base: `ad2dcec` (`origin/stacked-headers`, already fast-forwarded into local
`main`). Fixes: `a58afde`, on `review/system-audit-2026-09-05`.

The offline suite, actual CLI with fake model stages, production webapp build,
and a real archived viewer all work under the checks below. This is not an
end-to-end test of paid model services or a measurement of scientific precision.

## Verified defects fixed

| Defect | Effect before | Change and evidence |
| --- | --- | --- |
| Integer list parsing used `int(float(token))` | `--ns 30.9,30` reached ANOVA as `[30,30]`; `9007199254740993` became `9007199254740992`; infinity raised an unhandled exception | Parse exact decimal values, require finite whole numbers, and return a named CLI input error. Integral spellings such as `30.0` and `3e1` remain accepted. Tests exercise both the parser and actual ANOVA verb. |
| List parsing discarded empty entries | `1,,3` became `[1,3]`, silently changing the supplied data | Reject missing entries; retain support for a genuinely empty list so each tool can apply its own arity rules. |
| Crash records ignored the chosen default output directory | A failed analysis wrote `run_crash.json` into the caller's working directory instead of its versioned review directory | Write to the already selected output directory. A CLI execution test verifies the location and preserves the $1.25 spend ledger across the async exception boundary. |
| Crash-directory creation happened outside the protected error handler | A filesystem failure replaced the original stage exception | Protect directory creation along with record writing. A CLI test verifies that the original exception survives an unwritable destination. |
| `--artefact` announced inclusion without delivering its paths to either analyst | A review could appear to consider evidence that was never supplied to the pipeline | Explicitly refuse the unsupported option before extraction or spend. Point readable files to `--supplement`; repository/archive review remains unimplemented. This does **not** add artefact support. |
| Reproduction execution trusted all registered CLI verbs; a separate caller blocked only four | Direct calls could launch `analyze`; the live annotator could launch newer workflows such as `image-sweep` while validating a finding | Share an explicit calculation-command allowlist at the subprocess boundary and annotator. Refuse output-file options and malformed quoting. Blocked commands receive a visible reproduction problem, not a verdict about the paper. Tests replace subprocess execution to prove that operational commands never launch. |

The first CLI/parser regression run produced **14 failures** against the old
code. The subsequent reproduction-boundary tests also failed against the old
runner before the fix. These were reproduced failures, not lint suspicions.

No statistical algorithm, severity threshold, extraction premise, or
adjudication rule was changed. Across 80 finding rows in four archived v2
evaluation runs, 42 strings were classified as commands and 27 passed the
existing static validator. **None of those 27 is blocked by the new execution
policy.** The other 15 were already invalid; they are not newly lost coverage.

The new CLI success test invokes `analyze`, passes through its gates, runs the
real parallel orchestration and adjudication with fake model responses, and
checks the resulting findings, report, metadata and default viewer. It closes
the execution gap that allowed the deleted lazy writer import to escape tests.

## Verification

Environment: Linux ext4 checkout; Python 3.13.9 from the installed
`metascience` console script. No `/mnt/c` worktree was involved.

| Check | Result |
| --- | --- |
| Original full Python suite | 9,408 passed, 151 skipped, 1 expected failure; 81.82 s |
| Final full Python suite | **9,436 passed, 151 skipped, 1 expected failure**; 160.50 s |
| CLI/parser/pipeline focused run | 154 passed |
| Reproduction/pipeline focused run | 146 passed, 1 skipped |
| Documentation/pipeline check after comment corrections | 92 passed |
| `metascience preflight` | READY; account authentication is explicitly not probed by this command |
| Webapp `npm test` | Passed |
| Webapp `npx tsc --noEmit --incremental false` | Passed |
| Webapp `npm run build` | Passed |
| Rebuilt real Air Force evaluation viewer | 12 findings; all 14 navigation panels visible and populated; no uncaught browser errors or displayed viewer faults |
| Changed-source undefined-name checks and `git diff --check` | Passed |
| Python 3.10/3.11 syntax parsing of source and tests | Passed; this is **not** runtime validation on those interpreters |

The full suite emitted 3,288 warnings both before and after. It is green, not
warning-free. The skipped tests and expected failure remain explicit; no
failure was reclassified as an environmental skip to obtain this result.

The real viewer check used an isolated copy of the existing Air Force paper
and review. Each navigation check waited for the **requested** panel to be
visible, rather than merely checking whichever panel was previously active.
The findings page was also inspected visually. Browser measurements are in
`system-audit-2026-09-05-viewer.json` beside this report.

## Remaining work, in priority order

1. **Recover and review the proposed `agent.py` split.** Its branch and
   `cbf1236` object were not available in this checkout or the advertised
   remote branches during the audit. The current `parallel.py` references
   **42 distinct `agent` names, 76 uses, including 31 private names**. These
   are measured counts, slightly different from the handoff. Start with stage
   execution/spend accounting, source resolution, and forensic-track helpers;
   keep orchestration and archive writing separately identifiable. Re-run the
   supplied move generator against the final `agent.py` only after obtaining
   it, and require representative replay equality before landing. Do not
   recreate the unavailable split from its summary or hand-resolve it blindly.

2. **Make archive completion and write failures explicit.** The CLI's stage
   crash handler still ends before `write_parallel_outputs`; a failure in the
   writer itself is a separate persistence failure. Preflight the selected
   output destination before spending, write files through temporary files,
   and publish a completion marker only after required outputs are durable.
   Preserve paid results when enrichment or packaging fails. This deserves a
   focused change with injected write failures, not a broad exception swallow.

3. **Keep legacy readers behind explicit adapters.** `finding_view` correctly
   distinguishes absent severity from a cleared row's explicit `None`; preserve
   that contract. `viewer_facts.finding_index` still builds only from
   `report_obj` while `evidence_ledger` falls back to current findings. The v2
   findings page has its own renderer, so this is redundant/inconsistent
   payload work, **not evidence that the visible v2 page is empty**. Consolidate
   population selection and severity sorting when separating the adapters.

4. **Break up the largest modules by responsibility.** At the audit base,
   `bundle.py` is 8,987 lines, `cli.py` 6,120, `agent.py` 5,762 and `registry.py`
   4,913. Extract the viewer's JS/CSS into separately checkable assets while
   retaining a self-contained generated HTML deliverable; separate CLI input
   handling from paid-run orchestration and output persistence. Move historical
   incident narratives to documentation, leaving concise invariants at call
   sites. Corrected the most misleading current architecture comments in
   `CLAUDE.md` and `parallel.py` during this audit.

5. **Reduce existing lint/deprecation debt incrementally.** The baseline Ruff
   scan reports 1,681 findings: 654 long lines, 250 import-order issues, 108
   unused-import reports and many naming/style warnings. No undefined-name
   finding was reported in that baseline. `lint-inert --certain-only` reports
   45 candidates before and after these fixes (229 additional worklist items).
   Those labels are scanner output, not 45 independently verified runtime
   defects. Triage reachable swallowed exceptions first. Avoid a blanket
   unused-import cleanup: this repo deliberately re-exports compatibility
   names, and previous automatic removal broke consumers.

6. **Isolate tests from tracked paper data.** Both full suite runs rewrote
   `test_pdfs/high_value_pdfs_to_run_on/10.1001--jamanetworkopen.2023.37679/tables/index.json`
   solely to change its absolute `paper_dir` from Greg's checkout to this one.
   That generated edit was restored after verification. Tests that exercise
   cache/manifest writers should copy their paper fixtures into temporary
   directories so running the suite leaves the checkout clean. Validate
   supported Python versions in an actual runtime matrix, beyond syntax checks.

7. **Finish the human clean-control adjudication separately.** The handoff
   reports a ten-paper control run and a preregistered human scoring rule. This
   audit did not score those papers, infer a false-positive rate from the
   software tests, or substitute LLM judgement for human adjudication.

## Handoff reconciliation and limits

The fatal lazy `write_review_outputs` import was already fixed in `ad2dcec`;
cherry-picking the handoff's alternate commit was unnecessary. The static lazy
import guard and four-shape finding contracts passed in the full suite. The
reported split's 30/30 replay equality and 9,314-test result belong to the other
agent's unavailable branch and were not claimed as evidence for this branch.

No new paid paper analysis, live database write, deployment, or human control
adjudication was performed. The workbench was built and type-checked; its live
account/database workflows were not exercised. The offline viewer received
the browser navigation check. This was a broad repository audit with targeted
source review and execution, not an exhaustive proof of every scientific check.
