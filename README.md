# Forensic Metascience AI Toolkit

## Installation

This package requires Python 3.10+. To install, clone/download the repo and run these commands: 

```bash
pip install -e .
git lfs install && git lfs pull   # evaluation corpora are LFS-tracked
```

**A database for storing findings is optional but necessary to use the webapp interface.**  
Without a database, every result is still saved as files in the paper's `forensic_review/` folder. The following command walks through database setup: 

```bash
metascience db-setup  
```

If for some reason you don't want a database, running `metascience db-setup --no-database` records that and preflight will stop asking for it. 

**The image analysis module is not included here**. 
The image analysis code is in a private repository called `metascience-observatory-image-analysis` and we are only sharing it with trusted parties. For access, email dan@metascienceobservatory.org with a note describing what you would like to do with it.

**Modules that use AI need an AI agent CLI installed, or OpenRouter API key**

The system supports Claude Code (`--backend claude`), Codex (`--backend
codex`), Grok Build (`--backend grok`), or Google Antigravity (`--backend antigravity`). Run `metascience backends` to see which of these are properly installed on your machine and which models each one offers. The system can also be run via an API subscription using OpenRouter, however this has not been tested much and costs about 15-25 times more compared to a $200/month Claude Code or Codex plan. To use OpenRouter, make sure OPENROUTER_API_KEY is set in your environment or is set in a .env file placed in the root of this repository.
 

## Quick start


**Review a paper with the full pipeline** (both analysts,
tracks, adjudicator; image pipeline if installed):

```bash
metascience analyze paper.pdf --backend claude --model sonnet --max-budget-usd 100 # or a paper directory
```

**Run only the forensic metascience tools agent** (the statistical
consistency checks on the paper's numbers):

```bash
metascience run tools_only paper.pdf --backend claude   
```

**Run only the scientific proofreading agent** (contradictions,
methodological flaws, CONSORT flow):

```bash
metascience run proofreading_only paper.pdf --backend claude
```

A run with only one agent is labelled a partial review and gets its own
output folder; it never stands as the paper's review.

**Choose a backend** with `--backend` (required on `analyze`, `run` and
`batch`; a pipeline file's `backend:` also counts, and the `image_detect` and
`raw_data_only` pipelines call no model so need none). Each backend needs its
CLI installed and signed in. To see what this machine has, run:

```bash
metascience backends                    # lists every backend available on your system: installed?, version, default model, models
metascience backends --backend codex    # one backend
metascience backends --no-models        # only check what is installed
```

For each backend it prints whether the CLI is on PATH (for OpenRouter:
whether `OPENROUTER_API_KEY` is set), its version, the default `--model`,
and the models it offers. The model lists are live (`grok models`, `codex
debug models`, `agy models`, OpenRouter's public catalog), so they show
what your sign-in can use. Claude Code has no listing command, so its
aliases (`fable`, `opus`, `sonnet`, `haiku`) are shown instead. If a
default model is missing from your account's list, it is flagged; pass
`--model` explicitly. It costs nothing (`--all` prints all of OpenRouter's
models, `--json` for scripts).

```bash
metascience analyze paper.pdf --backend claude        # Claude Code (model opus)
metascience analyze paper.pdf --backend codex         # Codex CLI (model gpt-5.6-sol)
metascience analyze paper.pdf --backend grok          # Grok CLI (model grok-4.6)
metascience analyze paper.pdf --backend openrouter    # our own agent loop; needs OPENROUTER_API_KEY
metascience run tools_only paper.pdf --backend grok --model grok-4.6
```

**A whole corpus:**

```bash
metascience batch corpus/ --backend claude --dry-run                   # free: plan and cost estimate
metascience batch corpus/ --backend claude --max-budget-usd 30 --workers 10 # resumable; finished papers are skipped
```

**You can also run individual tools the tools agent has access to through the command line** (no AI used):

```bash
metascience tool run grim_check --json '{"mean": 5.51, "n": 30, "decimals": 2, "data_type": "likert"}'
metascience tool run statcheck --json '{"text": "F(2, 57) = 3.10, p = .01"}'
metascience tool run statcheck --json '{"pdf_path": "paper.pdf"}'   # every APA-style statistic in a paper
metascience tool run debit_check --json '{"mean": 0.35, "sd": 0.48, "n": 100, "decimals_mean": 2, "decimals_sd": 2, "data_type": "binary"}'
metascience tool run check_estimate_ci --json '{"estimate": 1.42, "ci_low": 1.08, "ci_high": 1.87, "measure": "HR", "decimals": 2}'
metascience tool list                      # list every registered tool
metascience tool describe grim_check       # a tool's parameters

```

`metascience tool run` goes through the same guards the AI sees: without
`data_type` and `decimals` GRIM refuses, and the call above says
`suspicious`, not `impossible`, because the
scale bounds and integer data are assumed rather than stated by a paper.
Ambiguous input is refused, not guessed: `48.90 (14.46)` could be a mean and
SD, a count and percentage, or an estimate and CI, and `metascience tool run
parse_cells_typed` says so.

`batch` skips papers with *no full text* (nothing readable), with no flag to override it.
A paper whose cited supplementary material is not present is *analysed anyway*, with a
warning and a limitation in its report: a statistic in an absent file can read as one the
authors never reported, so "not reported" findings must be read against it.
`--ok-if-supplementary-missing` is accepted for old scripts and has no effect.

A paper directory may hold publisher XML, HTML, the PDF, `body.md` and
supplements. The analysts read XML first, then the PDF, then `body.md`: the XML
is the only source that keeps table structure (on one clinical Table 1, 86
usable cells from the XML against 7 from the PDF).

## Cost and usage considerations
If you plan to run a lot of papers, we recommend the $200 a month Claude Code subscription or $200 a month Codex subscription. The cost is roughly $0.5-$2 per pape in usage with using Opus or GPT-6. Note that we have observed this changing over time as Anthropic and OpenAI change the amount of usage you get. 

With Claude Code and Claude Code only, you can pass a `--max-budget-usd` argument to specify the maximum budget, in API equivalent cost. 

A usage guard pauses runs with Claude or Antigravity runs
when the 5-hour window reaches 90%. The guard stops runs using Claude, Codex, or Antigravity when the weekly gauge goes over 97%. To ignore the weekly usage guard, pass `--ignore-weekly-limit`. To disable both usage guards, use `--no-usage-guard`.

## Modules and workflows

The codebase has a modular design. Users can add/remove modules and define their own custom workflows. The full workflow looks like this: 

```mermaid
flowchart TD
    doi(["A DOI"]) --> fetch["<b>fetchpdf</b> (separate repo)<br/>XML, HTML, PDF, supplements and data; lists missing PDFs for a human to obtain"]
    fetch --> parse["<b>PDF parsing</b><br/>docling, PyMuPDF, publisher XML/HTML, Mistral OCR for corrupt text layers"]

    parse --> img["<b>Image detection</b><br/>deterministic"]
    parse --> txt["<b>Text forensics</b><br/>tortured phrases"]
    parse --> tools["<b>Forensic metascience tools agent</b> <br/>points the forensic tools at the paper's numbers; no web access"]
    parse --> sci["<b>Scientific proofreading agent</b> <br/>contradictions, scientific mistakes, methodological flaws"]
    img --> imgrev["<b>Image AI review</b> <br/>screens out false positives and innocuous duplications"]

    imgrev --> join["<b>Join and verify findings</b>"]
    txt --> join
    tools --> join
    sci --> join

    join --> adj["<b>Adjudicator agent (optional)</b> <br/>dedupes, triages false positives, sets final severity, writes the paper-level verdict"]
    adj --> db[("Save findings to database")]
    db -.-> human["<b>Human review</b> <br/>workbench; humans decide what goes to PubPeer, authors or editors"]

    classDef agent fill:#e0f2f1,stroke:#00695c,color:#000
    classDef ink fill:#263238,stroke:#263238,color:#fff
    class tools,sci,imgrev,adj agent
    class doi,human ink
    click fetch href "https://github.com/The-Metascience-Observatory/fetchpdf" _blank
```

Each module is a folder in `src/forensic_metascience_ai_toolkit/modules/` (definition,
code and, for agents, its prompt); each tool family is a folder in
`tool_specs/`. The two tools no agent can call, `analyze_paper_images` and
`detect_tortured_phrases`, are run by the deterministic tracks instead. See
[docs/specs/modules.md](docs/specs/modules.md).

Here are the main modules: 

- **Tools agent** (58 tools are callable by the tool expert; no internet, no
  code): reads the paper, types every table cell, and checks each statistic
  with the matching tool.
- **Scientific proofreading agent** (internet on, sandboxed Python): patient
  flow, internal contradictions, and facts it looks up, with sources recorded.
- **Image detection** (deterministic) and **AI image review**: duplicated or
  manipulated figure panels, from the separately distributed image analysis
  package. Only screened findings reach the adjudicator. Without that package
  the image channel says the figures were NOT examined; nothing else changes.
- **Text forensics** (tortured phrases) and the opt-in **raw-data** module:
  deterministic, quarantined signals that never become the headline.
- **Adjudicator**: dedupes, verifies quotes, may re-run tools, and assigns the
  final [severity levels](docs/errorlevels.md) and the paper verdict.


## Pipelines

A pipeline chooses which modules run. `full` is the default review.

```bash
metascience pipeline list
metascience run tools_grim paper.pdf --backend claude   # = analyze paper.pdf --pipeline tools_grim
```

| Pipeline | Runs |
|---|---|
| `full` | tools agent + scientific proofreading agent + image detection and AI review + text forensics + adjudicator |
| `no_adjudication` | as `full`, severities left provisional |
| `tools_only`, `tools_grim` | the tools agent alone, with all tools or GRIM only |
| `proofreading_only` | the scientific proofreading agent alone |
| `image_only`, `image_detect` | image detection with or without AI review (no LLM analysts; needs the image analysis package) |
| `raw_data_only`, `full_raw_data` | the copy-paste detector over the paper's spreadsheets, alone or added to `full` |
| `full_brief`, `full_skill` | `full` with a different tool-access mode (experiments) |

Write your own YAML (`metascience pipeline validate my.yaml`). Only a pipeline
with both analysts, the full toolset and the adjudicator counts as a paper's
review; any other run gets its own output folder and is labelled partial. See
[docs/specs/pipeline_config.md](docs/specs/pipeline_config.md).

## What a review produces

Outputs go to `forensic_review/` inside a paper directory, or to
`<paper>_forensic_review_<model>_v<version>/` beside a PDF (`-o` overrides).

- `report.md` (and `report.pdf`): rendered from the findings document, headline
  first, with what could NOT be checked and a provenance stamp.
- `findings.v2.json`: every finding with its id, producer, technique, final 1-9
  severity, tool verdict, quotes and a reproduction command. Discarded findings
  are kept with their disposition.
- `adjudication.json`: the adjudicator's raw output.
- `run_meta.json`: cost, tokens, timing, versions and prompt hashes.
- `analysis_code/`: every script the proofreading agent ran.
- `prompt.*.md`, `toolcalls.*.json`, `messages.*.json`: per agent, what it was
  sent and every tool call it made.
- `sandbox_audit.json`: **read this one.** It says whether anything ran outside
  the validated tool surface.
- A `_bundle/viewer.html` that opens offline (`metascience bundle`).

Runs from the old serial pipeline (removed in v1.27.0) use `report.json`,
`findings.json`, `toolcalls.stage{1,2}.json` and `messages.stage{1,2}.json`;
every reader still opens them.

## Finding severity levels

Every tool returns `impossible`, `highly_suspicious`, `suspicious`,
`indeterminate` or `consistent`. **`indeterminate` is the default under
uncertainty**: a tool whose preconditions are unknown declines to judge rather
than guess. `impossible` is a claim about arithmetic, not people: three printed
numbers cannot all be true, which says nothing about which is wrong or why.
Before reading anything into one, see
[docs/GRIM_CONTEXT_DEPENDENCY.md](docs/GRIM_CONTEXT_DEPENDENCY.md) (nineteen
innocent mechanisms). The adjudicator then gives each finding a final severity
on a 1-9 ladder. The severity ladder levels are documented in [docs/errorlevels.md](docs/errorlevels.md)

## Reviewing results: the workbench

A local web app for reviewing many papers and image matches:

```bash
python -m forensic_metascience_ai_toolkit.workbench.service --migrate
cd webapp && npm install && npm run dev      # http://localhost:3100
```

Findings on the left, the PDF on the right; image matches have their own queue
with side-by-side, blink and overlay comparison. Decisions are stored locally
and synced to the shared database. Nothing is published from it. See
[webapp/README.md](webapp/README.md) and
[docs/workbench_storage.md](docs/workbench_storage.md).


## Validation

How the tools are checked against independent R implementations, and how the
full review is scored on papers with known problems: see
[docs/VALIDATION.md](docs/VALIDATION.md).

## Python API

```python
from forensic_metascience_ai_toolkit.agent import analyze_paper_sync
from forensic_metascience_ai_toolkit.tools import grim_test

result = analyze_paper_sync("paper_dir/", mode="parallel", budget_usd=8.0)
print(grim_test(mean=5.51, n=30, scale_min=1, scale_max=7)["consistent"])  # False
```

## License

**Free for noncommercial use.** Researchers, universities, nonprofits,
journalists, government bodies and individuals may use, modify and share
this toolkit for noncommercial purposes. Two limits apply:

- **No commercial use.** You may not sell it, offer paid services built on
  it, or use it inside a for-profit company. For a commercial license,
  email dan@metascienceobservatory.org.
- **Less than 500 papers.** Before analyzing more than 500 papers in
  total across your organization, email dan@metascienceobservatory.org for
 permission. If you are using it for bulk analysis, the Metascience Observatory would like to be involved.  

The full terms are the [PolyForm Noncommercial License 1.0.0](https://polyformproject.org/licenses/noncommercial/1.0.0)
plus the additional terms in [LICENSE](LICENSE); the LICENSE file is what
governs.
