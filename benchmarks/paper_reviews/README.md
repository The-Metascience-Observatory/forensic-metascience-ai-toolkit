# Paper-review benchmark (the eval harness)

Four real papers, each with an answer key. The benchmark runs the full review
pipeline on each paper, then scores what it found against the key. It answers
the question: **does the toolkit find the problems a careful human reviewer
found, without inventing new ones?**

Run it with `metascience eval`. This was the toolkit's eval harness before the
`benchmarks/` folder existed, and that is still the CLI command's name.

> **Private, do not publish.** `papers/` holds publishers' copyrighted PDFs and
> third-party reviews that name live, non-retracted papers. You can share it
> with collaborators on this private repository. You cannot share it publicly,
> and making the repository public would publish it through git history. See
> [papers/README.md](papers/README.md).

## What is here

| Path | What it is |
|---|---|
| `fixtures/<paper>.yaml` | The answer key for one paper. It names the PDF and the human review, and lists the expected verdict (`verdict_expected`). Under `key_findings` it lists each problem with a weight (critical/major/minor), a description, aliases the judge accepts as the same finding, and the expected 1–9 severity range. |
| `papers/` | The PDFs and the hand-written reviews the keys were built from. |
| `runs/<paper>/` | The latest run for each paper: the pipeline's full output (`forensic_review/`), the PDF copy and its extracted text (`paper/`), and the per-paper scorecard. |
| `runs/scorecard.json` | The combined scorecard from the latest run of all papers. |

| Fixture | Paper | Where the answer key came from |
|---|---|---|
| `apple_cider` | Apple cider vinegar weight-loss RCT | Human review (`papers/Apple cidar vinegar.md`) |
| `airforce` | Air Force study | Human review (`papers/airforce.md`) |
| `wound_healing` | Wound-healing study | Human review (`papers/wound_healing.md`) |
| `cerebrolysin_flow` | Cerebrolysin rat spinal-cord injury | A validated pipeline run from 2026-08-21. This is a regression check: it confirms the pipeline still finds what it once found, not what a human found. |

## How a paper is scored

1. **Prepare.** The harness copies the PDF into `runs/<paper>/paper/` and
   extracts its text. It never changes `papers/`.
2. **Analyse.** It runs the normal pipeline: the tools agent and the scientific
   proofreading agent, then the adjudicator.
3. **Judge.** An LLM judge (pinned to Claude Sonnet) reads the review and the
   answer key and decides which key findings were covered. It also counts
   accusations that are not in the key.
4. **Deterministic checks.** Code checks that need no LLM: the report's
   structure, no leaked model preamble, the verdict, and whether each finding's
   severity falls inside its expected range.
5. **Scorecard.** The harness writes weighted recall, false positives, verdict
   match and severity calibration to `runs/<paper>/` and `runs/scorecard.json`.
   Each scorecard records the pipeline version, backend and model that
   produced it.

## Running it

A run costs money: about $5–7 per paper on Sonnet. The default budget is $8
per paper.

```bash
metascience eval --paper apple_cider                 # one paper
metascience eval --backend claude --model sonnet     # all four
metascience eval --skip-analysis --paper apple_cider # re-judge a saved run
```

`--skip-analysis` still calls the LLM judge, so it is not free. It refuses to
run if the saved run it needs is missing, rather than silently running the full
paid pipeline. A new run **overwrites** `runs/<paper>/`, so the previous result
survives only in git history. Commit a run you want to keep before re-running.

To score another set of papers, pass `--fixtures <dir>` and `--runs-dir <dir>`.

## Adding a paper

Write `fixtures/<name>.yaml` following an existing fixture. Use
`apple_cider.yaml` for one with a human-review key and `cerebrolysin_flow.yaml`
for one with a regression key. Put the PDF, and the review if there is one, in
`papers/`. Give each key finding:

- `id`
- `weight`
- `description`
- `aliases`
- `reachable` (whether the toolkit can detect it at all)
- `severity_expected`
- `confidence`

The code is in `src/forensic_metascience_ai_toolkit/evaluation/`: `harness.py`, `judge.py`
and `deterministic.py`. The paths above are declared once, in
`harness.BENCHMARK_DIR`.
