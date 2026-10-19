# Changelog

The version this file tracks is `__version__` in
[`src/forensic_metascience_ai_toolkit/version.py`](src/forensic_metascience_ai_toolkit/version.py) — the one
place it is declared. `pyproject.toml` reads it from there, and
`tests/test_version.py` fails if the two ever disagree.

Every report stamps `pipeline_version()` on page 1 and in its **Provenance**
section: the release number below, the git sha that actually ran, and whether
that tree had uncommitted edits.

## [1.96.1] — 2026-10-19 — the import package is `forensic_metascience_ai_toolkit`

PATCH: a rename, no change to any output. The prompt and registry hashes are
unchanged (`4046c09965bd9de4`, `80515031f2a04ec0`), and so is the image code
fingerprint (`eb73b22b05bf`).

- **`src/metascience_agent/` is now `src/forensic_metascience_ai_toolkit/`**,
  matching the distribution name `forensic-metascience-ai-toolkit` that the
  project took on 2026-10-01. `metascience` and `metascience-test` are
  unchanged.
- **`metascience_agent` stays as an alias** (`src/metascience_agent/__init__.py`).
  `import metascience_agent.X` returns the same module object as
  `forensic_metascience_ai_toolkit.X`, never a second copy, and
  `python -m metascience_agent.X` still runs, so archived commands and old
  scripts keep working. Importing it raises a `DeprecationWarning`.
- **What a review sends changed in one place: the MCP server command.** Each
  stage now launches `python -m forensic_metascience_ai_toolkit.mcp_server`
  (from `integration.forensic_mcp_module`, which `agent.py` now reads too
  instead of its own literal). New parity oracle `parity_1_96_1.json`;
  `test_1_96_1_changed_only_the_mcp_server_module_name` shows that the tree
  with the old name restored captures the 1.93 oracle byte for byte.
- **Recorded runs keep the name they ran under.** Transcripts, parity records
  and fixtures that say `metascience_agent` were not rewritten; they are
  records of what ran.

## [1.96.0] — 2026-10-19 — start a review from a DOI: `analyze --doi --run-full-on-everything`

MINOR: fetched linked-dataset files now reach both analysts and the raw-data
module, so a review can see inputs it could not see before. No prompt, tool or
severity change.

- **`metascience analyze --doi <DOI>`** fetches the paper with fetchpdf into
  a new folder named for the DOI (`10.1/x` -> `./10.1--x/`; `--fetch-dir`
  moves it), then reviews it. The article is fetched as publisher XML or
  full-text HTML **and** the PDF; the review reads XML first, then HTML, then
  the PDF, as it already did for a folder. `metascience run <pipeline> --doi`
  works too.
- **`--run-full-on-everything`** fetches everything -- the article, the
  supplementary files and the linked data deposits (unpacked) -- and runs the
  complete review on all of it: both analysts, the image and text tracks, the
  copy-paste detector on the spreadsheets, and the adjudicator (`full_raw_data`,
  which is `full` plus the raw-data module). A narrower `--pipeline` beside it
  is refused before anything is fetched. `--max-supplementary-mb` /
  `--max-data-mb` cap the downloads, `--refetch` re-runs fetchpdf over an
  existing folder (otherwise it is reused).
- **Deposit files are read.** fetchpdf's `<stem>_data_artifacts/<deposit>/`
  was below every scan: the source resolver read the top level and the
  raw-data module an allowlist of folder names. `supplements.data_artifact_files`
  is now the one scan both use (tables and documents; images and code left
  out; capped at 50 with the overflow counted).
- **What the fetch got is on the record.** `fetch.json` in the folder and
  `run_meta.fetch` give each channel as obtained / not obtained / none listed
  / error / not requested, and each gap adds a Limitations line worded as a
  fetch result, not as something the paper lacks. A DOI with no copy of the
  article stops with exit 2 before any spend.
## [1.95.0] — 2026-10-19 — one command per tool: `metascience tool run`

MINOR: the per-tool CLI verbs are removed, and two reproduction writers change
form. No prompt, tool, severity or finding logic changes.

- **The 55 hand-written per-tool verbs are gone** (`metascience grim`,
  `check-ci`, `statcheck`, `extract-xml`, `tortured-phrases`, ...). Every
  tool runs as `metascience tool run <tool> --json '{...}'`, through
  `ToolSpec.call` -- the gates the agents get. The verbs called `tools/*.py`
  directly and skipped those gates (`grim` defaulted `decimals=2` where the
  registry refuses a missing precision), so a person at the terminal got a
  looser tool than the model. `metascience tool list` and `tool describe
  <tool>` list the tools and their parameters.
- **`tool run` serves the two CLI-only tools to an operator.**
  `detect_tortured_phrases` and `analyze_paper_images` stay off the MCP
  surface, and stay refused under any agent fence (`METASCIENCE_MCP_STAGE`
  or a tool manifest); with neither set they run, since this is now their
  only command-line route.
- **`tool run` is stricter about its input.** An argument name the tool does
  not have is a usage error (exit 2) instead of being dropped, which ran the
  tool on that parameter's default. A tool that raises returns the MCP
  server's structured `indeterminate` instead of a traceback. A library's
  progress lines go to stderr, so stdout opens with the verdict line that a
  replay reads (statcheck printed several first).
- **Reproductions are `tool run` everywhere.** The table dispatcher's rows
  (including the split count/percent check) and the tortured-phrases track
  wrote verb-form commands; they now go through
  `registry.reproduction_command`. Archived runs keep their verb-form
  commands: the checker reports each as a per-tool command retired in 1.95.0
  and names the `tool run` form, never as an unknown subcommand, and does
  not execute it. `ToolSpec.cli` is renamed `legacy_verb` and kept for that
  reading; `cli_required_flags`, `registry.cli_specs` and
  `registry.cli_syntax_reference` (no longer sent to any model) are removed.
- `cli_compat` stays: the image analysis package's CLI still uses it.
- The `--figures` hint no longer points at `figure-extractor.html`, which
  exists in neither repository.
## [1.94.4] — 2026-10-19 — `--budget-usd` is now `--max-budget-usd`

PATCH: CLI naming only; no prompt, tool, severity or finding changes.

- **The per-paper spend cap is spelled `--max-budget-usd`** on `analyze`,
  `run`, `batch`, `eval`, `python -m metascience_agent.batch` and the eval
  harness. It is a ceiling, not a target, and "budget" alone did not say so.
  `--budget-usd` is still accepted as the old name, so existing scripts keep
  working (`tests/test_eval_cli.py::TestMaxBudgetFlagName`). The value is
  still the total for the whole paper; each stage's share (tools agent 0.40,
  proofreading agent 0.25, adjudicator the remainder) is what reaches Claude
  Code's own `--max-budget-usd`. Default unchanged: no cap (eval: $8.00).

## [1.94.3] — 2026-10-19 — no dev extra: pytest-xdist and ruff are base

PATCH: packaging only; no prompt, tool, severity or finding changes.

- **pytest-xdist and ruff are base dependencies; `dev` is empty** (kept so
  `.[dev]` still resolves). About 29 MB, nearly all ruff, beside several GB
  of docling and PyTorch. As an extra, `tests/test_ruff_errors.py` -- which
  keeps unused variables and imports out of `src/` -- skipped on every
  machine without it. The ruff floor rises to 0.15, the version that check
  was last run clean under.
- **`metascience-test` no longer runs `pip install`.** It used to install
  pytest-xdist into the running interpreter when it was missing. An older
  install without xdist now runs serially and says to reinstall the toolkit.

## [1.94.2] — 2026-10-19 — WeasyPrint and pytest are in the plain install

PATCH: packaging and documentation only; no prompt, tool, severity or finding
changes.

- **WeasyPrint is a base dependency (`weasyprint>=60`).** It renders
  `report.pdf` when `wkhtmltopdf` is absent, and wkhtmltopdf has been
  unmaintained since 2023. About 19 MB beyond what docling already installs.
  It needs Pango from the operating system, which pip cannot supply; without
  it (or under Anaconda, whose GLib clashes with the system Pango) the import
  fails, rendering falls through to pandoc, and the reason is recorded in
  `run_meta.pdf_error` as before. `.[pdf]` still resolves, empty.
- **pytest and pytest-asyncio are base dependencies.** `metascience-test` is
  a console script every install gets and died on `import pytest` without the
  `dev` extra. `dev` now holds only pytest-xdist (which the runner installs
  itself when missing) and ruff.
- **ruff selects only `E9` and `F`**, the rules `tests/test_ruff_errors.py`
  enforces. The style families were selected but never enforced, and their
  1,655 findings in `src/` buried the real ones in a plain `ruff check`.

## [1.94.1] — 2026-10-19 — fetchpdf is in the plain install

PATCH: packaging and documentation only; no prompt, tool, severity or finding
changes.

- **fetchpdf is a base dependency again (`fetchpdf>=0.1.2`).** It supplies
  two checks: the landing-page test for papers whose only full text is a
  fetched HTML page, and the supplement integrity audit in `metascience
  batch`. As the `html` extra, a plain install lost both without an error: a
  cookie wall that clears the built-in stub check was read as the article,
  and a git-lfs pointer stub as the paper's supplement. It was an extra only
  because its pin had been a `file://` path on one machine. The floor is
  0.1.2 because 0.1.0 required playwright (about 180 MB installed), which
  neither check uses; fetchpdf 0.1.2 moves it to `fetchpdf[browser]`.
  `.[html]` still resolves, empty. Preflight's two fetchpdf rows say it is a
  base dependency when it is missing.

## [1.94.0] — 2026-10-19 — the findings database is set up, or declined

MINOR: a new command, and a new way runs can be told not to push. No prompt,
tool, severity or finding changes.

- **`psycopg` and `watchfiles` are base dependencies.** Every finished run
  pushes to the local findings database when a URL is configured. As an
  extra, a machine with a URL but no driver finished every run normally and
  queued each one in `db_push_pending.jsonl` without a word (`auto_push`'s
  result is not read by either call site). `.[db]` is kept as an empty alias.
- **`metascience db-setup`** walks a machine to one of two settled states.
  `ready`: it checks PostgreSQL is installed (prints install commands for
  apt, dnf, Homebrew or winget if not), the server is running (prints the
  start command), the database exists (offers to create it, and prints the
  `createuser`/`createdb` command when the role is missing or may not create
  databases), and the schema is current (applies `db/schema.sql` then
  migrations 003-006, from the first missing step forward, never back: 006
  redefines a function 005 defines), then saves the URL to the repo `.env`.
  `off`: `--no-database` writes `METASCIENCE_NO_DB_PUSH=1` to the `.env`,
  which `auto_push` now reads there as well as from the environment.
  `--check` exits 1 unless the machine is in one of the two.
- **Preflight has a "Findings database" row** (`db_setup.status`): never
  fatal, passing for `ready` or `off`, and naming the state otherwise
  (not configured, remote refused, server unreachable, login refused, no
  database, schema missing). At a terminal, `metascience preflight` offers
  the walkthrough when the row does not pass.
- Checked against this machine's PostgreSQL 16: the live database reports
  `ready`; a throwaway schema went from all five steps missing to none, and
  with 006's marker removed only 006 was re-applied. The walkthrough's
  "permission denied to create database" hint was wrong on its first real
  run (it said `createuser` to a role that exists) and now prints
  `sudo -u postgres createdb -O <user> <db>`.

## [1.93.1] — 2026-10-19 — PyMuPDF is in the plain install; no image extras

PATCH: packaging and documentation only; no prompt, tool, severity or finding
changes.

- **PyMuPDF is a base dependency.** The toolkit uses it outside image
  analysis: the PDF page a quote is on (`locators`, `quotes`, `anchors`), the
  viewer's page images (`bundle`), and rendering scanned PDF pages for OCR
  (`extraction/supplements_read`, `ocr`, `image_tables`). Most of those return
  an empty result when it is missing, so a plain install quietly lost page
  numbers and page images. Preflight's row is now "PyMuPDF (PDF pages)".
- **The `images` and `text-localization` extras are gone.** The image
  analysis package declares OpenCV, docling, PyMuPDF and EasyOCR itself, so
  installing it is the whole step; the extras were a second set of pins that
  could drift from it. The README says so.

## [1.93.0] — 2026-10-18 — a one-tailed test explains a p only when the paper says so

MINOR: severities change and four MCP tool definitions change (parity oracle
`parity_1_93.json`: only `registry_sha256` moves).

statcheck's rule (`OneTailedTxt`): a p that is right only as a one-tailed test
counts as consistent only when the paper's text says "one-tailed", "one-sided"
or "directional". Before this release our tools accepted the one-tailed
reading automatically:
- `recalc_stat_to_p` for every F(1, df) and chi-squared(1);
- `recalc_f_to_p` at df1 = 1, in both its paths;
- `check_regression` for every coefficient.

Measured on the deterministic p-tool benchmark (`benchmarks/pvalue_tools`,
scorecard re-pinned), `recalc_stat_to_p`:

| | 1.92.0 | 1.93.0 |
|---|---|---|
| errors caught, all sources | 60/86 | 83/86 |
| Wicherts et al. (2011) errors caught | 27/49 | 48/49 |
| errors on a printed bound | 32/55 | 54/55 |
| false flags on 1,370 labelled-correct statistics | 4 | 4 |

The automatic rescue decided 23 benchmark cases, and all 23 were labelled
errors.

- **New `one_tailed_stated` parameter** (default False) on `recalc_stat_to_p`,
  `recalc_f_to_p`, `check_regression`, and as a row key on
  `check_regression_batch`.
  - **True:** the one-tailed reading makes the result `indeterminate`, as
    before. For `recalc_stat_to_p` this now also covers a two-tailed t, z or
    r, since statcheck applies its rule to every test.
  - **False:** the mismatch is `suspicious`, failure_mode
    `reconciles_only_one_tailed_unstated`, and the one-tailed reading is
    named beside it, so no model can write that none exists.
- **`p_adjustment.declares_one_tailed`** finds the sentence: statcheck's
  pattern with word boundaries, and "non-directional" excluded. The analysts'
  prompt quotes it when a paper has one, as it does for a declared
  correction.
- `check_regression_batch` now also passes each row's `p_adjustment`, which
  it had been dropping since 1.90.0.

This reverses one recorded decision. On PNAS 0801268105 (2026-08-16) three
F(1, 19) p-values that reconcile only one-tailed were made `indeterminate`.
That paper never states one-tailed testing (checked 2026-10-18), so they are
flagged again under statcheck's rule, capped at `suspicious` and with the
one-tailed reading stated. The tests that pinned the old rescue now pin both
halves.

## [1.92.0] — 2026-10-18 — internal contradictions have one owner

MINOR: the tools agent's system prompt changes on every backend (parity oracle
`parity_1_92.json`), and so does the configuration note a partial pipeline
without the proofreading agent sends it. The proofreading agent and the
adjudicator are byte-identical.

The tools agent was told three different things about a contradiction such
as "abstract 551, Results 553":
- the top of its prompt said to hand it off, "never a finding";
- the `not_computational` definition named it as one of "the most valuable
  things this stage produces";
- the `tools_only` configuration note called contradiction review out of
  scope.

MEASURED 2026-10-18 on the statcheck_pvalue_errors working set (`tools_only`):
grok filed 24 and sonnet 25 `not_computational` problem rows. Most were
contradictions between passages. Several, such as a df that cannot come from
the stated n or an MSE ten times its siblings', rested on arithmetic and so
dodged the hand-computation cap.

- **The proofreading agent owns every internal contradiction**, including the
  same number printed differently in two places. It already keeps a register
  of the paper's commitments and quotes both sides. The tools agent records a
  handoff note in `unchecked`.
- **The one exception is a figure that disagrees with the text**, when the
  tools agent is given figures: the proofreading agent never sees them.
- **When no proofreading agent runs** (the `tools_only` and `tools_grim`
  pipelines), a handoff note reaches no one.
  So the tools agent files the numeric class itself: the same quantity printed
  with two values, as `internal_contradiction` with both printings quoted as
  `said`/`against` anchors. Contradictions in words, methodology, flow and
  reporting practice stay out of scope there.
- **`not_computational` is narrowed** to how one statistic is written: a
  notation error, an unreadable interval, a malformed statistic. Anything that
  took arithmetic is `no_tool_exists`, which carries the 1.91.0 cap, or a tool
  call.

Not measured on a paid run yet: the Grok balance was exhausted on 2026-10-18.

## [1.91.0] — 2026-10-18 — tool verdicts reconciled with findings: one finding per statistic, every accusing result accounted for

MINOR: the tools agent's system prompt changes on every backend (parity oracle
`parity_1_91.json`), a severity cap is now enforced, and a pass row no longer
counts as accounting for an accusing tool result. Re-scored offline on the
existing `tools_only` reviews of the statcheck_pvalue_errors working set
(`benchmarks/pvalue/score.py`, 28 known errors): no known-error match is lost
on any of the three runs.

| | grok 1.83 before → after | grok 1.88 before → after | sonnet 1.83 |
|---|---|---|---|
| final `problem` findings | 195 → 188 | 243 → 228 | 131 (unchanged) |
| extra filings of a known error | 16 → 13 | 20 → 12 | 2 (unchanged) |
| final at severity ≥ 3 | 158 → 151 | 182 → 170 | 63 (unchanged) |
| known errors reported | 22/28 → 22/28 | 23/28 → 23/28 | 23/28 |

- **One finding per statistic when no adjudicator runs**
  (`findings_v2.deduplicate_by_statistic`, called before `apply_skip`).
  statcheck and `recalc_stat_to_p` both filed `t(94) = 1.64, p < .001`, and
  both stood. The key is the statistic (value and reported p from `inputs`,
  else the group means, else an APA statistic in the title or quote), never
  the quote alone: four `recalc_anova` rows on one table shared its footnote as
  their quote. Only rows with the same outcome merge, so a problem and a pass
  on one statistic stay visible as a disagreement. The kept row (registry-tool
  row first) notes the other techniques, and every removed row is listed in
  `run_meta.deduplicated` and `coverage_summary.deduplicated`.
- **A structured record of unaccounted tool results**
  (`run_meta.unaccounted_tool_results`, copied to `coverage_summary`): the
  tools agent's suspicious-or-worse calls that no final finding accounts for
  and the recovery pass did not dismiss, one per call with its arguments. It
  used to exist only as a sentence in `limitations`. The recovery pass now
  records which calls it dismissed (`dismissed_calls` on its stage).
- **A pass row no longer accounts for an accusing result**
  (`unaccounted_verdicts`). It says the tool was wrong without saying why; the
  recovery pass now asks for a filing or a dismissal with a reason. An
  `undecided` row still accounts. Measured on grok 1.88's run: +14 calls (one a
  known error); excluding undecided too would have added 47.
- **A bookkeeping key no longer breaks the finding-to-call join**
  (`findings_v2._joined`). Keys the tool does not take (`n_checked`,
  `n_inconsistent`, `ci_level`) made 7 of grok 1.88's filed rows look unfiled,
  and the recovery pass asked for them again. A fallback only: every join that
  held before holds identically.
- **Claude gets the unfiled-results pass** (`UNFILED_RECOVERY_BACKENDS`).
  Sonnet's run left 56 of its own suspicious-or-worse results neither filed
  nor dismissed. The zero-call second retry stays as it was
  (`ZERO_CALL_RETRY_BACKENDS`, without Claude).
- **The tools prompt states the accounting rule for every backend**, not only
  in the Grok route: a suspicious result is a problem row, an `unchecked`
  entry with a reason, or an undecided row, never a pass row. It also stops
  calling an unstated hypothesis status "itself a finding"; it is recorded in
  the anatomy.
- **Hand arithmetic takes the model-reading cap.** The prompt promised
  `no_tool_exists` and `tool_existed_unused` a cap and nothing applied it
  (`severity_reconcile.clamp_uncomputed` reads only v1 reports);
  `clamp_provisionals` now does. No row in the three runs was affected.

Not changed, and why: a `problem` row whose own tool said `consistent` stays a
problem (demoting it to undecided changed nothing measurable on these runs),
and `not_computational` problem rows (24-25 per run) are left alone pending a
policy decision.

## [1.90.0] — 2026-10-18 — p tools calibrated on human-labelled statistics: bounds exact, declared corrections explain

MINOR: the severities the p tools return change, six MCP tool definitions
change, and two parameters are new. Measured on the new deterministic p-tool
benchmark (`benchmarks/pvalue_tools`; 1,456 human-labelled statistics, no
model), which `tests/test_pvalue_tools_bench.py` pins: no caught error may be
lost and no group may gain false flags.

| | 1.89.1 | 1.90.0 |
|---|---|---|
| `recalc_stat_to_p`: Wicherts 2011 errors caught | 15/49 | 27/49 |
| `recalc_stat_to_p`: errors on a printed bound | 20/55 | 32/55 |
| `recalc_stat_to_p`: false flags, all labelled-correct | 109/1,370 | 4/1,370 |
| `recalc_stat_to_p`: Wicherts false flags | 12/1,071 | 0/1,071 |
| statcheck wrapper: Wicherts errors caught | 18/49 | 49/49 |
| statcheck wrapper: errors on a printed bound | 23/55 | 55/55 |

- **A declared bound is written exactly** (`ttest.bound_is_stated`). "p < .01"
  used to get the printed precision's rounding slack, so `t(15) = 2.75,
  p < .01` (true p .0149) passed. Now only the statistic's own rounding
  protects the paper. This applies to `recalc_stat_to_p` (including its 1-df
  one-tailed reading), the three ANOVA paths, `recalc_chi_squared` and
  `recalc_independent_t`; `check_regression` already did it. An UNKNOWN
  relation on a conventional alpha keeps the slack, since it may be an
  exact .05.
- **The statcheck wrapper no longer cancels a flag on a bound.**
  `_within_printed_precision` used to round the computed p to a bound's
  decimals, so `round(.0149, 2) == .01` cancelled a correct flag. It rounds
  an exact `p = x` only. On the Wicherts hand coding this had cancelled 31 of
  the 49 labelled errors.
- **`p_adjustment` on the six p tools** (`recalc_stat_to_p`, `recalc_f_to_p`,
  `recalc_anova`, `recalc_independent_t`, `recalc_chi_squared`,
  `check_regression`). Values are `sphericity`, `multiplicity`, `none` and
  `unknown`. A correction the paper declares (Greenhouse-Geisser /
  Huynh-Feldt with the uncorrected df; a Bonferroni, Holm, Tukey or Scheffé
  adjusted p) explains a printed p LARGER than the statistic implies. That
  direction becomes `indeterminate` (`under_claim_explained_by_adjustment`);
  a p SMALLER than the numbers allow is never excused. All 12 Wicherts false
  flags were Huynh-Feldt p's, and 95 of the 96 correction-explained Nuijten
  flags were flagged. `p_adjustment.py` finds a declared correction in the
  paper and quotes the paper's clause to the analysts, as
  `survey_design.py` does for complex surveys. The prompt block appears only
  for a paper that declares one.
- **`test_confirmed` on `recalc_independent_t` and `recalc_anova`.** These
  rebuild the test from printed means and SDs. A printed p larger than the
  rebuilt one is legitimate under an ANCOVA, mixed-model, Welch or
  nonparametric analysis, so that direction is `indeterminate`
  (`under_claim_unconfirmed_test`) unless the paper says it ran this test. A
  printed t that contradicts the means stays a finding. This is the Grok
  1.88 working-set class "6-week PHQ-9 p = 0.002 understates a tiny t p".
- **A fractional df is a rounded value** (`recalc_stat_to_p`): "df = 5.5" is
  anywhere in [5.45, 5.55), and p is evaluated at the corners. `df`/`df2` are
  now declared floats so a Welch or Greenhouse-Geisser df is accepted, not
  truncated.
- The `recalc_stat_to_p` description no longer tells the agent to "report
  the unprinted df itself as an incompletely reported test". The tool's
  `df_note` still records it; a missing df is not an arithmetic finding.
- **Not changed, open question:** 22 of the 22 Wicherts errors
  `recalc_stat_to_p` still misses are `F(1, df)` statistics that its
  undeclared one-tailed reading reconciles. These return `indeterminate`, as
  designed ("undisclosed testing choice"). The Wicherts coders counted them
  as errors.

Parity: `parity_1_90.json` differs from 1.88's in `registry_sha256` only;
`test_1_90_changed_only_the_p_tool_definitions` proves it.

## [1.89.1] — 2026-10-18 — `metascience backends`: what is installed, and its models

PATCH: a new read-only CLI verb; no prompt, tool, severity or finding changes.

- **`metascience backends [--backend X] [--no-models] [--all] [--json]`**.
  For each of the five backends: whether its CLI is on PATH (OpenRouter:
  whether `OPENROUTER_API_KEY` is set), its version, the toolkit's default
  `--model`, and the models it offers. Lists are live where the backend can
  answer -- `grok models`, `codex debug models` (visibility `list` only),
  `agy models`, OpenRouter's public `/api/v1/models` -- so they reflect this
  sign-in; Claude Code has no listing command, so its aliases are shown and
  labelled `static`. A default absent from a live list is flagged.
  Measured on this machine at release: Codex's default `gpt-5.6-sol` is not
  in the account's catalog (`gpt-6-luna`, `gpt-5.6-terra`, `gpt-5.6-luna`).

## [1.89.0] — 2026-10-18 — Google Antigravity (`agy`) as a backend, with a model selector

MINOR: a new backend (as Codex was in 1.13.0). Claude, Grok, Codex and
OpenRouter argv and prompts are unchanged; Antigravity launches get one
backend-only prompt addendum, `core/prompts/antigravity_route.md`.

- **`--backend antigravity` (alias `agy`)** on `analyze`, `batch`, `eval`,
  `preflight` and pipeline YAML. Measured against agy 1.4.2. agy has no
  `--mcp-config`, `--system-prompt`, tool-allowlist flag or config-home
  variable, so each launch runs under its own `HOME`
  (`~/.cache/metascience/antigravity-sandbox/`): `mcp_config.json` with the
  forensic server (role-fenced, `enabledTools`, handed the real `HOME` so
  receipts survive), `settings.json` with trust and deny rules, and a custom
  agent whose body is the system prompt and whose `tools:` list is the
  built-in allowlist (`view_file`, `finish`; the web pair for the science
  agent). Sign-in stays in the OS keyring. Details and what is still
  unmeasured: `docs/specs/pipeline.md` §11c.
- **`metascience models [--backend antigravity] [--json]`**: the model
  selector. Lists the models this sign-in can use, live from `agy models`
  (13 on 2026-10-18: Gemini 4 Argon and Gemini 3.8 Flash at
  low/medium/high, Claude Opus 5.5 and Sonnet 5.5 at low/medium/high,
  GPT-OSS 120B at medium). `--model` takes a slug (`gemini-4-argon-high`,
  sent alone) or a base name (`gemini-4-argon`, the default, with `--effort`
  clamped to what that model offers).
- **Stream normalizer** for agy's `init`/`step_update`/`result` events:
  `call_mcp_tool` becomes `mcp__<server>__<tool>`; a large MCP result the CLI
  spills to a file is read back into the ledger; a schema-bearing turn that
  ends without `finish` is the schema gate (`error_max_structured_output_retries`),
  never an empty review. No cost figure (`cost_reported: False`).
- **Usage guard** reads the free `agy -p /usage`, counting only the quota
  groups the run's model draws on. Account-level agy refusals
  (authentication, quota, credits) stop a batch once.
- **The MCP server's stdout carries JSON-RPC only** (`mcp_server._protocol_stdout`):
  the protocol writes to a private duplicate of fd 1, and fd 1 / `sys.stdout`
  point at stderr. The statcheck package prints "Extracting statistics from
  text" on every call; Claude's client skipped the line, but agy's marked the
  server failed and refused every later call in the stage (measured on the
  second apple_cider eval: `csf_test` never ran). Pinned by
  `tests/test_mcp_stdout_is_protocol_only.py`.
- **A schema-gate retry on Antigravity RESUMES the conversation**
  (`--conversation <id>` under the kept per-run HOME) instead of restarting
  or recovering from the ledger, for both analysts and the adjudicator. The
  first apple_cider eval (gemini-3.8-flash-medium) showed why: the tools
  agent declared its tables and ended without `finish` before running a
  check, and the tool-less ledger recovery could only describe that setup.
  The resumed turn gets `core/prompts/antigravity_resume.md`; the archived
  transcript is both turns. Falls back to the usual retry if it delivers
  nothing.

## [1.88.0] — 2026-10-18 — a t or chi-squared without its df is bounded, not refused

Released on its branch as 1.86.0; renumbered 1.88.0 when merged after the
1.86.0 (batch robustness) and 1.87.0 (exact p) merges.

MINOR: a tool gains a capability, its MCP description changes, and rulebook
rule 4 gains a sentence -- what every role is told changes, so reviews across
this boundary are not comparable.

- **`recalc_stat_to_p` checks a t or chi-squared printed WITHOUT its df.** For
  a fixed |t| the p falls as df grows; for a fixed chi-squared it rises
  (verified on a grid, and pinned by
  `test_the_monotonicity_the_bound_rests_on_holds`). So with `df` omitted the
  tool bounds p over every df in [1, infinity) -- the ends of the range ARE
  the extremes -- and a reported p outside that interval is unreachable at
  every df. Before, it refused. MEASURED 2026-10-18: two of the tools agent's
  five misses on the statcheck_pvalue_errors working set were this shape.
  New optional `df_min`/`df_max` narrow the range when the paper prints
  numerals that force it (a stated N caps a t's df); the result reports
  `df_range`, `computed_p_range_over_df`, `holds_for_every_df`, and
  `verdict_needs_df_bounds` when bounds were supplied. Severity is unchanged:
  ceiling `suspicious`, directional as before, and the 1-df one-tailed rule
  applies whenever df = 1 is admissible. F still refuses without both df (its
  p is not monotone in df2 -- at df1 = 10, F = 0.7 it falls then rises), and
  says why. CLI: `stat-to-p --df-min/--df-max`.
- What the two misses now return, on the tree with 1.87.0's exact-p rule.
  Etindele Sosso 2020 (`t = 9.748, p = .523`): p is at most .0651 at any df,
  so .523 is an under-claim at every df; .523 is no conventional bound, so it
  reads as exact and is flagged `suspicious` (with `p_relation='<'` it stays
  `consistent`, correctly). Wansink 2012 (`chi2 = 2.355; P = .06`):
  two-tailed it is unreachable at every df (p >= .1248), but the 1-df
  one-tailed reading gives .062, so it stays `indeterminate` with
  `one_tailed_reconciles`, exactly as it would with df = 1 printed. The same
  paper's `t(78) = 1.65, P = .05` is also exact only one-tailed.
- Parity: new oracle `parity_1_88.json`;
  `test_1_88_changed_only_system_prompts_and_the_stat_to_p_definition` shows
  the only differences from 1.87 are every role's system prompt and
  `registry_sha256`. The 1.85.1 and 1.86 scope tests, which capture today's
  tree, now mask every role's system prompt (`_mask_system_prompts`) rather
  than the tools agent's alone; output schemas stay compared in full.

## [1.87.0] — 2026-10-18 — an exact p is checked in both directions; a stated CI level is not overridden

MINOR (released on its branch as 1.86.0; renumbered 1.87.0 when merged after the 1.86.0 batch-robustness release): what severities the p checks can return changes, six MCP tool
definitions change, and the tools agent's system prompt changes (parity oracle
`parity_1_87.json`; `test_1_87_changed_only_the_tool_agents_prompt_and_registry`
shows nothing else moved). Found by benchmarking `--pipeline tools_only` on the
statcheck_pvalue_errors corpus: each case below is a documented published
error that came back `consistent`.

- **A printed p ABOVE what its statistic allows is now an under-claim when the
  p was printed EXACT.** `_p_matches` and each tool's interval test were
  directional: a recomputed p below the printed one passed, which is right for
  a bound ("p < .05", true p 2e-5) and wrong for "p = .696". New
  `p_relation` parameter ('=', '<', '<=', '>', '>=') on `recalc_stat_to_p`,
  `recalc_chi_squared`, `recalc_anova`, `recalc_f_to_p`,
  `recalc_independent_t` and `check_regression(_batch)` (where it supersedes
  `p_is_threshold`). An exact p above the whole achievable interval returns
  `suspicious` -- never higher, it is a reporting inconsistency, not evidence
  of fabrication -- with failure mode `reported_p_above_recomputed`,
  `p_direction: under_claim` and `decision_error` when it crosses .05; a "<"
  bound keeps the directional rule; "p > x" is contradicted only from above.
  UNSTATED, a value that is no conventional bound (.696, .26, .71) is read as
  exact and .05/.01/.001/≤.001 keep the bound reading, with
  `under_claim_if_exact` and a note saying what the exact reading would find
  (`ttest.resolve_p_relation`). Now caught: `t(38) = 3.94, p = .696`
  (10.1037/a0024422, true p .00034); `F(2, 66) = 11.38, p = .26`
  (10.1037/a0028447, true 6e-5); Singh 1997's `[[5,12],[7,8]]` printed .71
  and `[[3,4,10],[0,4,11]]` printed .63 (10.1093/gerona/52A.1.M27). The
  under-claim side always uses the LARGEST p reachable: the top of the
  rounding interval (t-test: either flavor, Welch df floor min(n) - 1), and on
  chi-squared every convention -- Pearson, Yates, Fisher, McNemar, and two new
  ones computed for this, the likelihood-ratio G and an exact
  Fisher-Freeman-Halton p on 2xC tables (`_freeman_halton_2xc`).
- **`check_estimate_ci` no longer overrides a STATED confidence level.**
  `confidence_level` now defaults to None ("the paper states none", 95%
  assumed, a level rescue is a note as before). A stated level whose p
  reconciles only at another common level returns `suspicious` with failure
  mode `reconciles_only_at_other_level` and `level_that_reconciles`
  (unlabelled-measure path: `p_unreachable_at_stated_level`). Heymsfield 2021
  (10.1001/jamanetworkopen.2020.33457), 80% CI 0.31-2.43 around 1.37 with a
  printed P = .01 the journal later corrected to .10, came back `consistent`
  as "behaves like a 95% CI".
- **Every tail reading is held to the relation.** Under an exact p, a
  one-tailed rescue (regression, t-test, 1-df F and chi-squared) requires the
  printed p to sit inside the halved interval from both sides, as
  `p_is_threshold=False` already did. On the Romano ledger
  (`test_regression_df_sensitivity`) the df-30 and df-100 probes now accuse
  too: an exact `.048` at df 30 matched neither tail. The batch verdict there
  is unchanged (`indeterminate`, unstable across df). The t-test's
  conventional-alpha dual reading (`p_reading_ambiguous`) applies only when the
  relation is unstated.
- `p_relation` is a registry guard, so the run's guard ledger reports when it
  was defaulted (`agent._GUARD_CONSEQUENCE`). Tests: `tests/test_p_relation.py`
  (every published case above, plus the bound, convention and rounding
  rescues). `test_stat_to_p`'s "only an over-claim is flagged" and
  `test_regression_df_sensitivity`'s reported-df verdict asserted the old
  directional behaviour and were rewritten to the new contract.

## [1.86.0] — 2026-10-18 — a retry's work is kept, long titles are cut not rejected, a failed MCP probe is not cached

MINOR: the same paper may now produce different findings. Tool-agent rows
recovered from a ledger now join their tool verdicts, a re-run that did the
work is no longer discarded, and the producer-facing output schemas accept
longer titles. New parity oracle `parity_1_86.json`;
`test_1_86_changed_only_the_title_bound_in_the_output_schemas` shows the
current tree with the old bound restored captures the 1.85.1 oracle byte for
byte. All three were measured on the 2026-10-18 statcheck p-value benchmark
batches (`--pipeline tools_only`, Claude Sonnet and grok 4.6, 10 workers each).

- **A failed MCP liveness probe is retried and never cached**
  (`llm_backend.Backend.assert_mcp_live`). The FAILURE used to be cached per
  process: one failed `grok mcp doctor` failed all 20 grok papers of the
  batch instantly, per-paper retries included. Now 3 attempts with 2 s / 5 s
  pauses (`MCP_PROBE_ATTEMPTS`, `MCP_PROBE_BACKOFF_SECONDS`); only a success
  is cached; a server that fails every attempt still raises MCPUnavailable,
  naming each distinct error. The blocking probe runs in a worker thread
  (`asyncio.to_thread`) rather than stalling every other paper's stage on the
  batch's event loop.
- **A stage stopped before its spawn releases its invocation** (`runtime.
  _run_stage`). A refused preflight, MCPUnavailable, a weekly-limit stop or a
  cancel left the Grok sandbox directory behind, one per refused stage.
- **Finding titles over 90 characters are accepted and cut, not rejected.**
  44 of the 52 StructuredOutput rejections across the 116 archived stages of
  the benchmark were titles over 90 and nothing else (119 titles, median 96,
  longest 126), each a paid resubmission turn. The producer subsets and the
  adjudicator's verdict rewrite accept up to `findings_v2.PRODUCER_TITLE_MAX`
  (160); `findings_v2.fit_row_title` cuts the stored row back to 90 at a word
  boundary (a number is never split) and appends the full title to `notes`,
  which the viewer renders. The stored schema is still 90, and the prompts
  still ask for 90. An adjudicator rewrite over 90 used to be ignored without
  a word; it is now applied and cut.
- **A retry that did the work is recovered and kept** (`modules/_analyst.
  retry_if_empty`). On 10.1001--archpediatrics.2012.999 (grok) the first
  attempt made no tool call and the full re-run made 25 forensic calls (its
  receipts include two `suspicious` results) but filed no usable document;
  the zero-call attempt was returned, and the paper was refused for making
  "no call on its forensic tool list (not even a reader)" -- false. The
  re-run's ledger now goes to the document-only recovery
  (`<label>_retry_recover`), and if that fails too the stage kept is the one
  with the calls.
- **A docket recovered from a ledger keeps that ledger** (`_carrying_work`).
  The document-only recovery has no tool calls of its own and was returned
  bare, so the rows it composed joined NO tool verdict, and the tool-call
  audit, checks tally and receipts join were built from an empty transcript.
  True of the first-attempt recovery since 1.17.0. The kept stage now carries
  the tool-running attempt's transcript ahead of its own; `messages.<label>.json`
  holds both.

## [1.85.5] — 2026-10-18 — batch output describes this run

PATCH: `metascience batch` console output and corpus paper discovery; no
prompt, tool, severity or finding changes. Seen while watching the GRIM
ground-truth dev set (`--pipeline tools_only`, three batches of the same ten
papers):

- **"Batch cost (this run)" is this run's spend.** The summary re-read
  `batch_costs.jsonl` and summed every row whose paper NAME was in the batch,
  so the third batch printed $26.47 for papers that cost $9.53. It is now
  summed from what this process recorded, refused papers' spend included.
  The corpus total stays in "Usage for this corpus (all recorded runs)",
  whose rows now say they are totals over all runs ("paper runs recorded:
  39 (10 distinct papers)", "API-equivalent cost, all runs", "/run").
- **The plan and usage tables have no empty header row** (blank column
  titles rendered as an empty boxed row).
- **Dot folders are not papers.** `pick_papers` counted the run archive
  `.analysis_runs/` as a paper with no full text ("papers found 11",
  "SKIP .analysis_runs"). Real paper folders without text are still counted
  and named.
- **The per-paper line says why there is no verdict**: "verdict: none -- this
  pipeline has no adjudicator; severities provisional" on a tools_only run
  (or "the adjudicator failed" / "not adjudicated"), not "verdict: -".
- The MCP server's PYTHONPATH already carried this tree's
  `copy_paste_detector/src` since 1.85.3 (`forensic_pythonpath`). The image
  package needs no equivalent: parent and child resolve it from the same
  inherited PYTHONPATH or editable install.

## [1.85.4] — 2026-10-18 — statcheck is in the plain install

PATCH: packaging and documentation only; no prompt, tool, severity or finding
changes.

- **`statcheck` is a base dependency.** Nearly every run uses the tools agent,
  and a missing statcheck does not fail: the tool returns an empty result that
  reads as "this paper has no test statistics". `pip install -e .` now carries
  it; `.[statcheck]` is kept as an empty extra so older instructions resolve.
  The preflight failure message no longer says to install the extra.
- **The `html` extra installs `fetchpdf` from PyPI** (`fetchpdf>=0.1.0`)
  instead of a `file://` path that existed on one machine. 0.1.0 carries both
  functions the toolkit calls (`validate_t2`, `verify.audit_tree`). It stays
  optional: both call sites fall back without it.
- **The README explains each extra**: why it is optional, what each package
  is, and what happens without it. `tests/test_docs_accuracy.py` now pins that
  every non-empty extra has a README row, that statcheck is in
  `[project].dependencies`, and that no extra pins a local path.

## [1.85.3] — 2026-10-18 — a worktree run imports only its own tree

PATCH (released on its branch as 1.85.1; renumbered 1.85.3 when merged after
the 1.85.1 and 1.85.2 merges -- the oracle and its test keep the `1_85_1`
name they were written under): no prompt, tool, severity or finding changes;
only the environment of child processes. What the default run sends changes in exactly that
value: new parity oracle `parity_1_85_1.json`, and
`test_1_85_1_changed_only_the_childrens_pythonpath` shows the current tree
with the old `<src>`-only value restored still captures 1.84's oracle byte
for byte. `parity_capture.py` drops the caller's own PYTHONPATH extras,
which are the machine's, not the tree's.

- **Every child that imports the toolkit gets BOTH source roots of the tree
  it was launched from** (`llm_backend.forensic_pythonpath`): `<root>/src`,
  then `<root>/copy_paste_detector/src`, then the caller's own
  `PYTHONPATH` entries. The forensic MCP server's env used to carry only
  `<root>/src`, so a worktree run resolved `copy_paste_detector` through the
  editable install's `.pth` -- the shared checkout. MEASURED 2026-10-18: a
  pinned 1.83.0 benchmark lost every tools agent on grok and claude
  (`MCPUnavailable`, server `ImportError: cannot import name '_compat'`)
  when a peer changed the detector on main. Covered: the claude MCP config,
  grok's `config.toml`, codex's `-c` env and its stdio probe, the skill
  launch's `metascience tool run`, the OpenRouter loop process, and the
  text/raw track children (`tests/test_child_source_roots.py`, including a
  child-import known positive).

## [1.85.2] — 2026-10-18 — the prompt is on stdin before the CLI starts waiting

PATCH (released on its branch as 1.84.2; renumbered when merged after 1.85.1): no prompt, schema or tool change; only how the prompt reaches the
child process.

- **Large parallel batches no longer lose papers to `claude -p`'s 3 s stdin
  wait.** `_run_stage` spawned the CLI on a pipe and wrote the prompt once
  the event loop returned to it. With 10 claude and 10 grok workers on one
  loop that took more than 3 s, and both stages of 10.3389--fpsyg.2011.00199
  exited 1 at 0 tokens ("no stdin data received in 3s ... Input must be
  provided either through stdin or as a prompt argument"). The same failure
  reproduces with the real CLI by blocking the loop 5 s between spawn and
  write. Every `stdin`-delivery backend (Claude, Codex, OpenRouter) now gets
  an anonymous temporary file that already holds the whole prompt when the
  child starts. A file does not depend on the loop and has no pipe-buffer
  limit, and nothing is left on disk. Grok's `--prompt-file` path still gets
  a pipe closed at once. `tests/test_prompt_stdin_race.py` blocks the loop
  after the spawn and fails without this change.

## [1.85.1] — 2026-10-18 — a stage's stream is no longer lost at the CLI's exit

PATCH (released on its branch as 1.84.3; renumbered when merged after 1.85.0): no prompt, tool, schema or severity changes. Which document a stage
is read from changes only where the stream lost its `result` event.

- **The CLI's stdout is a file we tail, not a pipe** (`runtime._FileLineReader`).
  `claude -p` 2.1.301 drops whatever it has not written when it exits with
  its stdout pipe full, and exits 0. In the v1.83.0 sonnet batch on the
  statcheck working set (20 stages on one event loop), 7 of 57 stages ended
  with no `result` event; one (10.1007--s40200-021-00832-0, tools agent) lost
  its last 100 s including the accepted findings. Reproduced with the real CLI
  through `_run_stage` with the loop blocked 60 s: on a pipe, rc 0, 4 events,
  last line cut, no `result`; on the file, all 13 events and the cost.
- **The accepted StructuredOutput call is read when no `result` event came**
  (`track_contracts._accepted_structured_output`, parse path
  `structured_output_tool_use`). Only a call whose tool_result is not an error
  is used. On the six affected transcripts that had one, it recovers 9, 6, 11,
  11 and 16 findings and an adjudication of 17 verdicts; two of those stages
  had been read from prose instead, one under a false "DEGENERATED" warning.
  The limitation says the document came from the transcript and that the
  stage's cost is UNKNOWN; run_meta's stage records `result_event: false`
  (and `stdout_ended_mid_line` when the stream was cut).
- **A stage that delivered no document is `is_error: true`**
  (`track_contracts.mark_no_document`: `no_result_event` or
  `no_parseable_output`; a budget, timeout or schema-gate subtype is kept), for
  both analysts and the adjudicator. Those stages used to read
  `is_error: false` beside a limitation saying they produced nothing.

## [1.85.0] — 2026-10-18 — no compatibility aliases

MINOR: import paths and pipeline module names are removed. No prompt, tool,
severity or finding changes. (Also on main since 1.84.2, from another
session: `--backend` is required whenever a run calls a model; see d7c12108.)

- **The toolkit keeps no aliases of moved modules.** Deleted:
  `metascience_agent/image_forensics/` (10 forwarding files),
  `metascience_agent/image_track.py`, the nine image aliases in `workbench/`
  (`content_support`, `image_equivalence`, `image_geometry`,
  `local_image_import`, `local_image_service`, `local_images`,
  `text_regions`, `thumbnails`, `videos`), `highlight_render.py`,
  `tools/raw_duplication.py`, and `copy_paste_detector/_compat.py`. Import the
  real modules: the image package's own paths (host code through
  `image_plugin.load`), and `copy_paste_detector` directly.
  `extraction/figures.py` stays: without the package it supplies the OCR
  provenance names the statistical gates read.
- **Three aliases were also binding the host.** `local_images`,
  `local_image_import` and `local_image_service` called
  `image_review_host.configure()` / `configure_service()` before forwarding,
  which lends the host's `Catalog`, `Repository` and `Service` to the image
  package. Host code now loads them through `workbench.image_review_host.load`,
  which binds first. Imported unbound, they raise `HostUnavailable`. The
  import CLI that ran through the alias, `python -m
  metascience_agent.workbench.local_image_import`, is now `python -m
  metascience_agent.workbench.image_import` (same arguments).
- **The old image module names no longer parse.** `image_detection` /
  `image_review` are unknown modules. `LEGACY_MODULES` and `legacy_digest` are
  gone, so a partial `image_detect` / `image_only` run recorded before 1.84.2
  no longer counts as done, and the batch re-runs it once.
- **The detector-root hint moved.** The "re-run `pip install -e .`" message
  for a shadowed `copy_paste_detector` used to live in the two shims. It is
  now raised by `metascience_agent.tools`, the first importer
  (`tests/test_detector_import_guard.py`, run in a child interpreter).

## [1.84.2] — 2026-10-18 — one image module

PATCH: no prompt, tool, severity or finding changes. Pipeline digests change
(the module list is hashed); the pre-merge digest is still recognised.

- **`image_detection` + `image_review` are one module, `image_analysis`.**
  The review module never ran anything -- the image package's `pipeline.run`
  detects and screens as one unit, and `image_review` only reported that
  call. AI screening is now the `ai_screening` option (default true;
  `image_detect` sets it false). Producer `image_track` and the
  `image_forensics` channel/stage label are unchanged, so finding ids and
  stored runs read as before.
- **Old names still load.** `pipeline_config.LEGACY_MODULES` maps old
  pipeline files and old runs' recorded blocks onto `image_analysis`
  (detection alone becomes `ai_screening: false`). The batch skip compares a
  recorded digest against both the new digest and `legacy_digest`, so partial
  runs from before the merge are not re-run; the pre-merge digests of the
  shipped pipelines are pinned in `TestLegacyImageModules`.
## [1.84.1] — 2026-10-18 — the `prompts/` package is retired

PATCH: no prompt or schema changes. What each agent is sent, and every
producer schema, hashes identical before and after the move.

- **`metascience_agent/prompts/` is gone.** Since the modular refactor
  (1.76.1) it held no prompt text, only the assembler and the schemas, so
  the folder name misled people into looking there for prompts. The
  assembler is now `core/prompts/__init__.py`
  (`metascience_agent.core.prompts`), beside the shared text it loads, and
  the JSON schemas are `metascience_agent/schema/`. Every importer moved and
  no shim was left behind. `test_modules` now fails if the old folder comes
  back.

## [1.84.0] — 2026-10-18 — the per-paper prompt asks for the table declarations

MINOR: the tools agent's user prompt changes (parity oracle
`parity_1_84.json`; that prompt is the only difference from 1.82/1.83).

- **The declaration step reaches the per-paper instructions.** 1.82.0 put
  `list_tables` / `declare_table` in the tools agent's system prompt (step
  2a), but the per-paper prompt still said, for every table, "pass the cells
  to `parse_cells_typed`, then run `check_table`", and never named the paper
  directory `list_tables` takes. Found reading the prompt the dev GRIM run
  had received, before re-running it. Every source layout now ends with a
  "Table declarations (GRIM)" block naming the directory
  (`agent.table_declarations_text`); a pipeline whose toolset lacks
  `declare_table` drops it (`parallel._restrict_user_prompt`).

## [1.83.0] — 2026-10-18 — Group Findings, and each GRIM failure highlighted in its cell

MINOR: the harness GRIM sweep files fewer cells (truncation-only cells are no
longer failures), and the review workbench gains grouping and cell anchors.
No prompt or tool change.

- **Group Findings, on by default** (Dan's request). In the review list, one
  tool family (`tool_specs.family_of`: grim_check and grim_percentage are both
  `grim`) in one table, or in PDF pages within one page of each other, is one
  row that opens to its findings (`finding_groups.group_issues`). Grouped
  server-side BEFORE pagination, so a group is never split across pages; the
  pager counts rows and the header says "N findings in M rows". The arrow keys
  step between rows; ‹ finding › still steps one finding at a time. A finding
  with no recorded tool or no place is never grouped. Off restores the flat
  list (`metascience.groupFindings` in the reader's browser). Decisions stay
  per finding. The cached finding summary gains `location_basis` (printed
  location, anchor pages, tables named), backfilled once with `tool_basis`;
  before this, summaries carried no location at all.
- **Each failing cell is highlighted, in the XML table and on the PDF page.**
  New anchor kinds `xml_cell` and `pdf_cell` (`docs/specs/anchors.md` §10a):
  the XML pane marks the very `<td>`; the PDF gets a box only when the row
  label is unique on the page and the value occurs in that row band exactly
  as often as the extracted row prints it, else the page alone. Measured on
  Shaaban 2012 page 4: every box sits on its number; the sparse rows the
  sweep refuses get none. Before this, `annotate_findings` replaced a
  finding's anchors from its quotes and silently dropped every `table_cell`
  anchor. More than eight places step one at a time (‹ k of N ›).
- **Truncation is not a GRIM failure.** A cell that fails round-half GRIM but
  passes under truncation (or where truncation rescues every failure at that
  n, `no_discriminating_power`) is `rounding_only`: counted in the coverage
  line, never filed. Measured on Cureus Table 1, `41 (58%)` at n = 70.
- **A printed count stays fixed in the non-response test.** `41 (58%)` was
  "explained" by 40/69; only k/m for the printed k may explain it now.
- Sealed runs get locators from their persisted anchors (they had none);
  their files are never re-searched. The list now shows which highlight is
  current (it compared the finding id with a passage key, so none ever was).
- XML table cells render with `data-row`/`data-col` (the reader's address)
  and each table with `data-table-num`.
- The small grey line under each finding (priority reason and location) is
  gone (Dan): the title already names the place.

## [1.82.0] — 2026-10-18 — GRIM on every table cell: the model declares, the harness checks and files

MINOR: two new tools (`list_tables`, `declare_table`), a new producer
(`harness`), a tools-agent prompt step (2a), and findings the model did not
write. Reviews across this boundary are not comparable.

- **`grim_harness`: GRIM over every mean and percentage cell of every table.**
  Measured on the dev half of the GRIM ground truth
  (`benchmarks/grim/literature_2026-10`, Sonnet, `tools_only`): the tools
  agent checked 38 of 135 known-bad values and flagged all 38; on Shaaban 2012
  it checked 7 of about 180 percentages. The harness now enumerates. Each
  cell's n carries its source: printed in the cell, the column header
  (innermost level only), a header row the publisher put in the body
  (Cureus), the row label, or a declaration. Disagreeing sources give no n.
- **`declare_table` / `list_tables` (tools agent).** The model states what a
  table's cells ARE: rows bound to variables, bare percentages that are shares
  of the participants, n's printed only in prose ("the consultants were 41 ...
  and 25"). The tool returns the sweep for that table; after the run the
  harness reads every declaration back from the ledger and sweeps all tables.
  Without declarations only printed `n (%)` / `k/n (%)` cells are checkable,
  and that is all the harness checks: measured offline on dev, 4 of 160
  primary cells; with declarations written from reading each table, 121
  fail at the stated n and the other 39 fail at it but pass at an n up to 5%
  smaller (`explained_by_nonresponse`), with zero failures on values the
  critics did not list.
- **Failures are findings** (Dan's decision; `docs/DESIGN_DECISIONS.md`): one
  row per table, producer `harness`, provisional severity 4 (a cell fails at
  its stated n) or 3 (every failure is one non-response explains), never
  `impossible`; each failing cell is a `table_cell` anchor. Refused and
  counted, never checked: test-statistic and p-value columns, model-output
  columns, a sparse row under columns of different n (docling puts a spanning
  value under the first subcolumn; six false failures on Shaaban Table 2
  before this), averaged subscales, continuous variables, and every cell of a
  paper that declares a complex survey design.
- **The report's Coverage block states the GRIM sweep**: cells enumerated,
  checked, inconsistent, explained by non-response, and the top reasons the
  rest were not checked. `coverage.grim_sweep` carries the counts.
- **Docling tables are labelled by their printed caption.** A docling caption
  is a reference into the document's texts, and `_label_of` printed the
  reference: every captioned PDF table was labelled `cref='#/texts/49'` with
  no caption. New extractions resolve it ("Table 2", "TABLE 3",
  "Supplementary Table S1"); existing caches keep the old labels until
  re-extracted (`metascience extract-tables --force`). No cache-schema bump,
  which would have forced every corpus to re-extract.
- A harness-sweep crash is now a limitation in the report, not a silent pass.

## [1.81.2] — 2026-10-18 — the printed-table export keeps every column

PATCH: the human-readable `tables/` package only. No tool, prompt, schema or
severity change; the analysts never read this export.

- **`table_package` keys columns by index, not by label.** Two columns can
  share a label: PLOS ONE `10.1371/journal.pone.0042828` Table 2 prints
  "Locomotor Activity" and "Rearing Activity" as spanners, but its XML splits
  each into two `colspan="1"` cells, so columns 2 and 4 both fold to
  "Activity | Day28 ISCH". Keyed by label, the second overwrote the first:
  `tables/printed/01_table-2.md` had 6 of 7 columns, the locomotor Day-28
  values were gone, and the rearing Day-28 values sat under the locomotor
  heading. Cells that carry `col` are now placed by it (and ordered by it);
  only a cell with no `col` falls back to its label. The labels themselves
  are the XML's own and are not merged. Tests in
  `tests/test_table_package.py::TestATwoRowHeaderKeepsEveryColumn`, built
  from that table's structure in both its split-word and spanned forms; the
  split-word case fails on 1.79.3.
## [1.81.1] — 2026-10-18 — partial runs' findings reach the workbench, each tagged with its tool

PATCH: database upload and the review workbench. No tool, prompt, schema or
severity change. The cached finding summary gains `tool_basis`, backfilled
on the next sync.

- **A partial run's findings are uploaded.** `history_db` sent findings only
  for `comprehensive` runs, so a `tools_only` run (`partial_review`) reached
  the database as a run row with no findings, and the importer skipped the
  report push for the same run id. Measured 2026-10-18 on the GRIM
  ground-truth `verified_dev` archive: 0 findings before, 842 from 37 partial
  runs after. `runs.kind` is now `partial_review` (was `component`), matching
  `discovery.run_kind`.
- **A paper whose only runs are partial shows its newest one** on the paper
  page (`Repository.partial_fallback`), with a note that it is unadjudicated,
  instead of "No run recorded for this selection". `latest` still leaves
  partial runs out of counts, severity and the queue.
- **A finding's detail opens on its own run.** `Reviewer.tsx` called
  `issue_detail` without `run`, so the service refreshed `latest`, which no
  partial run is part of, and every such finding failed "Finding not in this
  project".
- **Run options name their pipeline and model**, e.g. "tools only ·
  provisional · grok-4.6" (`common.run_pipeline`).
- **Every finding carries the tool that triggered it**
  (`review_issues.finding_tool`), shown as a badge on its card: the joined
  `tool_verdict`, else the recorded ledger call, else a technique that names
  a registry tool (drawn dashed: the analyst named the tool, no recorded call
  backs it), else "model judgement". On `verified_dev`'s Sonnet runs: 60 of 87
  findings by verdict, 13 by technique alone, 15 model judgement. A summary
  cached before the field reads "tool not recorded", never "model judgement".
- Tests: `tests/test_history_database.py`, `tests/test_pipeline_config.py`,
  `tests/test_workbench_sync_keys.py`, `tests/test_workbench_remote.py`; the
  rendered check is `METASCIENCE_TEST_SCENARIO=partial` in
  `webapp/test/workbench-browser.mjs`.
## [1.81.0] — 2026-10-18 — every GRIM failure reaches the analyst; category shares are tested

MINOR: tool behaviour. `grim_percentage` now evaluates category shares it
refused and names its failures, and an inputs-less finding accounts for fewer
tool results. No prompt, schema or severity-ladder change.

- **An inputs-less finding accounts only for the calls its prose names**
  (`findings_v2._joined`, shared by `tool_verdict_for`, `backing_call` and
  `unaccounted_verdicts`). With no `inputs`, a finding used to cover EVERY
  ledger call of its tool, so one finding hid the rest from the unfiled-results
  recovery. It now covers the calls whose distinguishing numbers (values not
  shared by every call of that tool) appear in its quote, location, title or
  description. The calls naming the most such numbers win. Measured on the
  2026-10-16 Grok run on `10.1371/journal.pone.0042828`: grim_check failed
  seven Table 2 means at n=6 and the one finding named 51.9. The old join left
  0 results unaccounted; the new one leaves 28 (13 direct GRIM failures plus 15
  `check_table` rows). Tests in
  `tests/test_unfiled_recovery.py::TestInputsLessFinding`.
- **The n (%) of a category reaches `grim_percentage` as a proportion.**
  `dispatch.DISPATCH` routed `nominal_category` and `ordinal_category` n (%)
  cells to `grim_percentage`, but the tool refused their declared types
  (`nominal`, `integer`), so every such cell came back indeterminate.
  `Variable.forensic_kwargs(share=True)` gives a category family `proportion`.
  The table path passes it for n (%) and count/denominator cells, and
  `declared.reconcile` uses the same reading for a check that takes a
  percentage, so the call reconciles instead of being downgraded to `unknown`.
  `grim_percentage` also accepts `nominal` / `categorical` directly. Mean-type
  GRIM is unchanged: a mean of a nominal category is still refused. Tests in
  `tests/test_misapplication_guards.py::TestCategoricalShares`.
- **`grim_percentage` names its failure.** An inconsistent percentage returned
  `impossible` with `failure_mode: None`; it now says `granularity`, as
  `grim_check` does. A share outside 0-100% says `out_of_range`. Before this,
  such a share passed the range test (the helper returns a count of 0 off the
  unit interval) and then came back `consistent` under the truncation rescue:
  120% at n = 10 was cleared. The checks tally in `agent.py` and
  `severity_reconcile` do not read this mode; `benchmarks/grim/score.py`
  `_flags` already counts `granularity`. Tests in
  `tests/test_grim.py::TestPercentageFailureMode`.

## [1.80.1] — 2026-10-18 — the budget is split over the stages a pipeline runs

PATCH: how `--budget-usd` is divided. No tool, prompt, schema or severity change.

- **An analyst's cap is its fraction rescaled over the paid stages the
  pipeline runs** (`_analyst.stage_budget_share`). The fractions (tools 0.40,
  science 0.25, adjudicator the rest) assumed all three ran, so a `tools_only`
  run capped its only agent at 40%: two GRIM dev papers were cut off at ~$1.25
  of $3. `full` is unchanged; `tools_only` / `tools_grim` give the tools agent
  the whole budget, `proofreading_only` the science agent; `no_adjudication`
  splits it 0.615 / 0.385.
- **`run_meta.stages.<agent>.budget_cap_usd`** records the cap each analyst
  ran under. Tests in `tests/test_pipeline_config.py::TestBudgetSplitFollowsThePipeline`.

## [1.80.0] — 2026-10-18 — a missing supplement warns; the paper still runs

MINOR: which papers get a review. No tool, prompt, schema or severity change.

- **`supplements.gate` no longer refuses a paper that cites supplementary
  material we do not hold** (Dan, 2026-10-18; replaces Greg's 2026-08-10
  refuse-by-default). Refusing threw away every check the main text supports:
  the GRIM ground-truth dev batch skipped a paper whose GRIM failures are all in
  the article. `analyze` prints the warning and runs; `batch` lists the paper as
  "supplement cited and missing (INCLUDED, warned)" and warns per paper.
- **The run records it.** `parallel.py` adds a limitation naming the cited,
  absent items, so report.md says a 'not reported' finding may be an artefact
  of them.
- **An unreadable article still refuses, in `analyze` too.** The flag used to
  let `analyze` run on a paper with no readable text; `batch` never did.
- `--ok-if-supplementary-missing` is accepted and has no effect. README,
  docs/DESIGN_DECISIONS.md (superseding entry), handoff note and tripwire
  docstring updated.

## [1.79.3] — 2026-10-18 — a failed JSON repair no longer fails the paper

PATCH: error handling. No tool, prompt, schema or severity change.

- **`agent.StageError` is `runtime.StageError`.** `agent.py` declared an
  identical class of its own, so every `except StageError` there, and the
  adjudicator's per-paper failure tuple, caught nothing the stage runner
  raised. `_repair_json` is meant to swallow a failed repair; on 2026-10-18 one
  failed a whole paper of a Sonnet `tools_only` batch instead
  (`10.1186/s40795-015-0030-x`).
- **The tool-free repair's MCP config is valid.** A partial pipeline repairs
  unparseable output with `--mcp-config "{}"`, which the `claude` CLI rejects
  ("mcpServers: expected record, received undefined"), so every partial-pipeline
  repair failed. It now passes `{"mcpServers": {}}`, checked against the CLI.
  Tests in `tests/test_pipeline_config.py`.

## [1.79.2] — 2026-10-18 — a different model is a new batch run, not a redo

PATCH: which papers `metascience batch` skips. No tool, prompt, schema or
severity change.

- **`completed_review` matches the backend and model**, for complete reviews
  and partial pipelines alike. It compared only the pipeline, so a Grok
  `tools_only` batch would have skipped every paper a Sonnet `tools_only`
  batch had just finished (found 2026-10-18 on the GRIM dev set), and a model
  comparison needed `--redo`, which then re-pays every paper on a resume. A
  finished run now counts only if its `run_meta` backend and model match the
  request; the model matches the recorded alias or any model that actually
  answered (`models_resolved`). A run that recorded neither predates the
  record and still counts, so old corpora are not re-paid. Both batch entry
  points pass the resolved backend and model; other callers keep the old rule.
  Tests in `tests/test_pipeline_config.py::TestReaders`.

## [1.79.1] — 2026-10-18 — `metascience batch` shows a grid of every paper in flight

PATCH: display only. No tool, prompt, schema or severity change.

- **A grid, one row per stage of every paper in flight**
  (`progress.BatchGrid`). Its header counts the whole corpus (done / running /
  queued / ok / partial / failed / skipped, plus batch elapsed), and the last
  few finished papers stay listed with their status. The one-line-per-paper
  view folded every stage into one line, which showed whichever stage reported
  last. Each stage now keeps its own tool, tokens and clock. Measured on
  real-sized snapshots at 64, 80, 110 and 160 columns: the clock column is
  never clipped. The long stage title "scientific proofreading agent" had
  pushed it off the edge at 110.
- **A redirected batch printed NO progress at all.** `batch.py` passed
  `live=not args.verbose`, which forced Rich Live onto a non-terminal stderr,
  and a transient Live writes nothing there. The comment beside it promised
  a 15 s plain line. It now passes `live=None` (TTY detection), so a
  `> log 2>&1` run gets one line per (paper, stage).
- **The plain-line throttle is per row, not global**, in both `BatchGrid` and
  `LiveBatchStatus` (`analyze`). One shared 15 s window let a single line
  through, so ten workers showed each paper about every 2.5 minutes. A stage
  finishing is always logged, once.
- **`batch -v` with several workers tags every streamed line with its paper**
  (`progress.CURRENT_PAPER` + `prefix_stdout_by_paper`). Lines are buffered
  per paper until their newline, so a half-printed line is never spliced into
  another paper's.
- **`run_batch` flushes stdout before returning.** The image package's
  `managed_run` stops a multiprocessing manager `Server` in-process, and
  CPython's `Server.serve_forever` then resets `sys.stdout` to
  `sys.__stdout__`, stranding buffered output in any redirected stream. The
  always-on Live had been flushing as a side effect. Found by
  `test_batch_cli.py::TestFullTextGate::test_skipped_directories_are_not_analysed`.
  The reset itself belongs to the image repository.
- The `batch` help said it runs serially by default (`--workers 1`). The
  default has been 10.

## [1.79.0] — 2026-10-16 — GRIM runs on count data with no stated maximum; handoff notes reach the adjudicator

MINOR: a tool description and the adjudicator prompt change how a paper is
analysed. Reviews across this boundary are not comparable.

- **`grim_check`'s MCP description no longer reads as needing a scale.** It
  said "given sample size and integer scale" beside defaults of 1-7, and never
  said the granularity test is bound-free. MEASURED on
  `10.1371--journal.pone.0042828` (v1.78.0): the Sonnet tools agent skipped
  GRIM on Table 2 because "no scale was stated", although the Methods say the
  open-field counts were tallied per rat at n=6. Seven of the 20 count means
  fail GRIM under both rounding conventions, and Grok's run on the same paper
  confirms it with the tool. The description now says a missing maximum is
  never a reason to skip GRIM, how to pass a count's bounds, when
  `discreteness_source` is `stated`, and that a per-subject average over k
  trials or observers moves in steps of 1/(k*n). The tools-agent guidance bullet
  says the same. `tests/data/registry_snapshot.json`: `grim_check` desc_sha only.
- **The analysts' `unchecked` lists are in the adjudication docket.** Both
  analyst prompts send cross-territory suspicions as handoff notes in
  `unchecked`, "how your suspicion reaches the adjudicator", but the docket
  never carried them. On the same run the science agent's note that the
  Table 2 means "look inconsistent with GRIM at n=6" had no reader.
  `adjudicate.build_docket(unchecked=)` adds a bounded, cap-announcing section,
  and the adjudicator prompt makes a handoff naming a check on specific
  printed values the one exception to "no third sweep": it runs that check on
  those values and reports it in `summary`, minting no row. Tests in
  `tests/test_adjudicate.py::TestDocket`.
- **New parity oracle `tests/data/parity_1_79.json`.**
  `test_1_79_changed_only_prompts_and_the_grim_description` proves it differs
  from 1.75b only in the tools agent's and adjudicator's system prompts and
  `registry_sha256`; the science agent's invocation is byte-identical.
- Unchanged, deliberately: `UNFILED_RECOVERY_BACKENDS` still excludes Claude
  (measured 0 of 10 Claude runs with unfiled results), and it could not have
  helped here, since the check was never run.

## [1.78.2] — 2026-10-16 — a stage cut short says so in report.md

PATCH: what the report prints, not how the paper is analysed. No tool, prompt
or severity change.

- **A budget-truncated stage now announces itself on page 1 of `report.md`.**
  `_stage_meta` has recorded `truncated_by_budget` per stage, and the run is
  filed `incomplete`, but `report_v2.render_report_v2` printed nothing about it
  -- the serial pipeline's PARTIAL COVERAGE limitation went with that pipeline
  in v1.27.0 -- so a report whose tools agent spent its budget before emitting
  findings read as a complete review. A `PARTIAL COVERAGE` banner now follows
  the partial-pipeline banner, naming each stage that stopped early and why
  (`ran out of budget`, or `was cut off by the time limit` for
  `truncated_by_timeout`, which `agent._CUT_OFF_SUBTYPES` says every
  truncation consumer must treat alike). Ledger-only retry rows are skipped.
  Tests in `tests/test_report_v2.py::TestTruncatedStageBanner`.

## [1.78.1] — 2026-10-16 — `examples/` is gone; the batch runner is a package module

PATCH: a refactor. No analysis, prompt, tool or severity change; reports are
unaffected.

- **`metascience batch` no longer needs a source checkout.** It imported
  `examples/batch_analyze.py` through a `sys.path` insert; that file is now
  `metascience_agent.batch` (`python -m metascience_agent.batch` replaces the
  script).
- **The author-corpus scripts left the repository** for the sibling folder
  `../author_corpora/` (`author_corpora`, `build_author_corpus`,
  `build_discovery_corpus`, `build_berrio_corpus`, their PubPeer/fetch helpers
  and retry steps), with their four test files and a conftest of their own.
- **Everything else in `examples/` was deleted**: calibration, evaluation and
  prompt-comparison scripts, two stale usage examples, and
  `test_image_prompt_comparison.py`, which tested only its own script. Docs
  that cite one say it is in git history. The tortured-phrases quarantine
  reason now says its release gates are in the tool's docstring.

## [1.78.0] — 2026-10-16 — local databases only; the remote Neon database is retired

MINOR: configuration surface removed. No analysis, prompt, tool or severity
change; reports are unaffected.

- **Every database is on this machine.** The findings database is the local
  PostgreSQL 16 server (migrated from Neon 2026-09-12 with equal row counts on
  all 18 tables; Neon has refused connections since, its quota exceeded).
  `db_push.resolve_db_url` now reads ONE variable, `METASCIENCE_DB_URL`
  (environment or repo `.env`), and REFUSES a URL naming any host other than
  localhost / 127.0.0.1 / ::1 / a unix socket (`DbUnavailable`). The run-
  completion auto-push and `history_db.try_sync` report that refusal instead
  of raising, so a stale `.env` can neither fail a paid run nor send findings
  off the machine.
- **Removed:** the `NEON_DB_URL` alias, the `METASCIENCE_DB_PROFILES` /
  `METASCIENCE_DB_PROFILE` switcher, the workbench `databases` method, the
  webapp's database switcher (`DatabaseForm`, `/api/database`, the
  `db_profile` setting), and the importer's Neon storage ceiling
  (`storage_budget`, `capacity_blocked`).
- **Renamed:** the live Postgres test opt-in is `METASCIENCE_TEST_POSTGRES=1`
  (was `METASCIENCE_TEST_NEON`); the image package's
  `local_image_import --from-neon` is `--from-db` (image package 0.25.0).
- `tests/test_workbench_db_switch.py` became `tests/test_db_local_only.py`; the
  cache-reset-on-identity-change tests are kept, since a recreated local
  cluster changes identity too.

## [1.77.0] — 2026-10-16 — the toolkit runs without the image analysis package

MINOR: a packaging change. The image analysis system becomes a separately
distributed, private package that DEPENDS ON this toolkit; the toolkit installs
and runs without it. With the package installed every default run is unchanged
(parity oracle, registry snapshot), the detector fingerprint is unchanged
(`eb73b22b05bf`, so no gate re-run and no stale sweep stamp), the GPU worker
files are byte-identical (qualifications stand) and the cross-paper matcher's
code identity is unchanged.

- **The general modules came home.** The 2026-09-11 extraction had moved ~22k
  lines of general code INTO the image package (LLM backends and the stage
  runtime, extraction, the severity scale, findings_v2/quotes, the archive,
  history, db_push, metadata) and the toolkit borrowed them through
  `sys.modules` aliases, so `import metascience_agent` failed without the
  image package (measured: 201 of 315 modules). They live in
  `metascience_agent` again; the image package keeps reverse aliases at the
  old paths.
- **One door.** `metascience_agent.image_plugin` is the only way toolkit code
  reaches the package (`load()`, `available()`, `ImagePluginUnavailable`), pinned
  by `tests/test_runs_without_image_plugin.py`, which also runs the CLI, the tool
  registry, a statistical tool, preflight and the workbench service in an
  interpreter where the package cannot be imported.
- **Without the package** the image module's channel reads `refused` with the
  limitation "the figures were NOT examined ... not a clean result", and the
  history component is sealed `unavailable`; `extract_figures` and
  `analyze_paper_images` stay registered and refuse by name; the `image-*`
  verbs and `--device` options are absent; workbench image routes raise
  `ImagePluginUnavailable`; docling runs in-process on the CPU under its own
  execution identity (`extraction/document_compute.py`).
- **Kept identical by construction:** `retain.HOST_FINGERPRINT_FILES` reads the
  fingerprinted `extraction/ocr.py` from the toolkit under its old name;
  `code_identity` names a reverse-aliased module by its package name.
- **The docling cache re-extracts once per paper**: its execution identity
  hashes `extraction/docling_tables.py`, which now routes through the broker
  door. A cache miss, never a wrong hit; the GPU `document` workload needs its
  `compute-calibrate` comparison re-run.
- **Fixed on the way:** `review_io.write_review` had imported
  `refresh_index_paper` from `discovery` (which has none) since the extraction,
  and a bare `except` hid it, so the web index never refreshed after a review
  save. It imports from `webapp_index` again.
- `METASCIENCE_BLOCK_IMAGE_PLUGIN=1` runs the suite as a plugin-less install.
- **The package left this repository.** It lives in its own private repository
  (`metascience-observatory-image-analysis`, history kept), checked out beside
  this one and installed editable after the toolkit. With it went `eval/gate`,
  `eval/bench`, `eval/ground_truth/image`, `eval/rollout`, `eval/blots`, the
  Masliah image scorecards, the image docs and the image half of CLAUDE.md
  (1,539 -> ~920 lines). The wheel no longer bundles it; the webapp image queue
  and the host-side image adapters stay here.


## [1.76.1] — 2026-10-15 — the raw_data module's limitations reach the report

PATCH. Found by the first real run (`metascience run raw_data_only` on a copy
of `10.3390--healthcare11101497`): the detector's coverage was PARTIAL and
the run's limitations were EMPTY, because only agent modules' limitations
were merged. A partial spreadsheet scan read as a complete one. The module's
partial-coverage, crash and timeout statements are now merged after the image
track's; tests cover a partial scan and a timeout.


## [1.76.0] — 2026-10-15 — the modular refactor finished: raw_data module, prompts with their modules, follow-up fixes

MINOR: a new module and producer (`raw_data`, `raw_data_track`). The default
run sends exactly what 1.75.0 sent (parity oracle). The entries below were
released together.

### the modular refactor's last pieces: prompts beside their modules, `metascience run`

PATCH (a move and an alias; what every model is sent is byte-identical, pinned
by the parity oracle).

- **Each agent's system prompt lives in its module folder**:
  `modules/tools_agent/prompt.md` (was `prompts/tool_expert.md`),
  `modules/scientific_proofreading_agent/prompt.md` (`science_error.md`),
  `modules/adjudicator/prompt.md` (`adjudication.md`). The shared text --
  `rulebook.md`, `rulebook_roles.md`, `reproduction.md`, `grok_mcp_route.md`
  -- is `core/prompts/`. `prompts.PROMPT_FILES` maps the old names, so
  `_read("tool_expert.md")` still works; `prompts/` keeps `schema/` and
  `tool_reference.md` (sent to no model).
- **Scanners read `prompts.prompt_files()`.** Two guards would have gone
  silently blind after the move and were fixed with it: `handoff.py`'s
  second_look check read `prompts/adjudication.md` by path, and
  `test_prompt_contract._md` returns "" for a missing file, so every check on
  the adjudicator prompt would have passed vacuously. `inertness` and the
  prompt-scanning tests now use the list; the unenforced-rule worklist is 93
  rules before and after.
- **`metascience run PIPELINE PAPER`** is `metascience analyze PAPER
  --pipeline PIPELINE`; further analyze options pass through.
- **Plan items deliberately NOT done** (recorded so they are decisions, not
  omissions): registry.py down to ~500 lines (it is 1,410: the remaining code
  is the gate machinery), dropping the per-tool CLI verbs and `cli=` fields
  (kept beside `metascience tool`), generating `tool_reference.md`, a module
  listed twice, `tool_access: code`, screening models in the pipeline YAML
  (editing `screening.py` invalidates every pair stamp), and a live
  OpenRouter test (Dan, 2026-10-15: not needed).


### the raw_data module: the copy-paste detector inside a review

MINOR at release (a new module and producer; the default run is unchanged and
its parity oracle holds byte for byte).

- **`raw_data`** (modules/raw_data/) runs
  `copy_paste_detector.detect_paper_duplication` over the paper's
  spreadsheets and CSVs in a child process (`metascience_agent.raw_track`),
  with the per-file CLI's bounded limits. No model. Opt-in through the new
  pipelines `raw_data_only` and `full_raw_data`.
- **Producer `raw_data_track`** (findings schema enum and `prompts.PRODUCERS`).
  Its rows are quarantined, one per (file, kind) with an accusatory group, and
  capped at `QUARANTINE_CAP`. Measured 2026-10-15 on three fixture
  spreadsheets: 2,088 accusatory row-pair groups, almost all model-generated
  tables, so a row per group would bury a report, and row-pair matches still
  have no chance model. Groups, row pairs and rows are separate counts.
  `adjudicate._unscreened` keeps them off the headline.
- **Channel `raw_data`** (only when configured): `did_not_run` when the paper
  has no structured file, never a clean result. The history `copy_paste`
  component, `not_requested` on every run until now, records what the module
  did.


### refactor follow-ups: the run's own archive, the forensic-tools gate, an adjudicator crash

Found while checking the modular refactor's last phases against main
(2026-10-15). No prompt change; the parity oracle is unchanged.

- **The report is written to the archive the run started in.** The report
  writers re-resolved the history archive by marker at report time, and the
  image track creates `.image_track/` in the paper's parent directory mid-run,
  so a paper staged beneath an archive-bearing ancestor lost the whole paid
  run at the last step (`ValueError: unknown or unsealed run`; wound_healing
  and cerebrolysin_flow, 2026-10-13). The root is pinned on the result at
  analysis start (`result["history_root"]`, `history_runtime.result_archive`).
  The fix had been sitting uncommitted in one checkout.
- **The forensic-tools gate fires in the parallel pipeline.**
  `_assert_forensic_tools_ran` only checks the legacy labels `sweep` and
  `analysis`, so it never ran for `tool_agent`. A tools agent whose attempts,
  retries included, made no call on its forensic list now has its document
  refused with a named limitation. It is checked after the retries, so the
  1.75.0 zero-call retry still gets its chance.
- **An adjudicator stage that raises keeps the findings.** A `StageError` or
  `MCPUnavailable` from the adjudicator (or its retry) now finalises through
  `apply_skip` with provisional severities instead of propagating and writing
  no findings.v2 (Astra design item #8, deferred since Phase 1).
  `BackendUnavailable` and `WeeklyLimitReached` still propagate so a batch
  stops.
- Tests: the shared fake tools-agent stage and the parity capture now include
  the paper read every real run makes; a test that wants zero calls installs
  its own fake.


## [1.75.0] — 2026-10-14 — backend parity: a severity cap from the tool's own verdict, one eval judge, Grok's write-up repaired

**Measured (`metascience eval`, every run graded by the high-effort Sonnet
judge; audit: https://claude.ai/artifact/PtcTyxp1MsUv7q8qk321hP).**

- **The modular refactor did not regress Claude.** Sonnet, two runs per
  fixture, pre-refactor 05537458 (with a two-file report-time fix so its
  wound_healing/cerebrolysin runs are not lost; analysis untouched) against
  this release's code (de2da2a1): mean weighted recall 0.730 vs 0.705, the
  same gold findings covered paper by paper, verdict right 5/8 vs 8/8,
  mean analysis cost $2.18 vs $2.51. The recall difference is inside the
  judge's own test-retest noise: 15 reviews graded twice, 2 changed recall
  (max 0.18) and false-positive counts moved by up to 3.
- **Grok on this release:** mean recall 0.58 over 9 runs (1.74: 0.48 over
  11), verdict 8/9 (1.74: 7/11); level with Sonnet on airforce and
  wound_healing, behind on apple_cider (0.76 vs 1.00) and cerebrolysin
  (0.65 vs 1.00). Every run's unfiled-results pass accounted for its items
  (one run left 3 unaccounted, stated in its report).
- On the same numbers the two backends' tools agree except 6
  `check_effect_plausibility` calls with a different declared `field` or
  `design`.


MINOR at release: a new severity cap, a changed tool interface
(`check_flow_arithmetic` takes `also_reported`), and prompt edits on every
backend (rulebook rule 18, rule 16, the science agent's flow steps, the
adjudicator's verdict bands, Grok's addendum). Two oracles pin the scope
(`tests/test_pipeline_parity.py`): `parity_1_75.json` (adjudicator and Grok
only; Claude's analysts byte-identical) and `parity_1_75b.json` (only the
three system prompts, `prompt_sha256` and `registry_sha256` differ: no argv
flag, output schema, user prompt, environment or allowlist moved).

### Errors found by the backend parity audit, most harmful first

- **A finding is capped by its own tool's verdict** (`severity9.TOOL_VERDICT_CAPS`,
  applied in `clamp_provisional` and again in `adjudicate._clamp`): a
  registered-tool finding whose validated tool returned `consistent` is
  capped at 2, `indeterminate` at 3, and neither can be the headline (the
  check and the fallback both skip it). Caps compose by MIN with the
  evidence-channel caps. In all six Claude 1.73 apple_cider runs the Level 5
  headline was "the dagger marks contradict identical means 78.1 vs 78.1"
  while `recalc_independent_t` returned indeterminate: the claim rested on a
  guess about which comparison a dagger denotes. Replayed on the 36 saved
  runs (no model call): 19 kept rows change, 7 of them headlines (those six
  plus a false-positive headline in a Claude 1.74 cerebrolysin run), and no
  gold finding falls below its expected severity. `suspicious` is
  deliberately not capped: that would have lowered the real cerebrolysin
  headline. Rulebook rule 18 says the same in words: a significance mark's
  comparison is a premise, at most 3, never `impossible`, never the headline.
- **The eval judge runs at HIGH effort** (Dan, 2026-10-14). At medium it
  scored a run 0.0 that contained the paper's critical finding (implied
  n=73/74 against printed 80/79); at high, 0.375 like every other airforce
  run. The judge now sees a compact view of every kept finding (it used to
  truncate at 30K characters) and credits a finding that names the same
  defect by another route; airforce's GRIM aliases gained "implied n".
- **An analyst that never opens the paper is told what to call first.** In 3
  of 20 Grok runs the science agent returned an empty report in about 7
  seconds with zero tool calls: a placeholder JSON taken as the answer. The
  retry now names the first call with the real path (`extract_xml` /
  `extract_pdf` / `Read` of body.md) and says a JSON-only message ends the
  run; a second zero-call dump on grok/openrouter/codex gets one more
  attempt (`<label>_retry2`).
- **A flow check cannot clear a stage the paper prints two ways.**
  `check_flow_arithmetic` takes a per-stage `also_reported: [{n, source}]`;
  a disagreement is `conflicting_reports` at highly_suspicious (a hard
  arithmetic failure still wins). A Grok review had kept "the animal flow
  30->21->15 reconciles" although the abstract says 16 at the second
  operation and the Results say 21. The science agent's flow steps now
  collect counts from every section, and a pass names its source.
- **The unfiled-results pass counts exactly and leaves a trace.** Items are
  numbered; a filed row or dismissal starts with `result #N`, and filed,
  dismissed and still-unaccounted are counted by number (dismissals used to
  be counted as unaccounted too). The call is archived as
  `messages.<label>_unfiled.json`.
- **Reassurance language is flagged by the pipeline** (`reassurance.py`,
  the eval's `must_not_say` reassurances as one list): a hit in a kept
  finding or the adjudicator's summary is a `producer_constraint_problems`
  entry plus a report limitation; the text is never rewritten. Replayed: 8
  of 36 saved runs carry one, 7 Grok or mixed-backend and 1 Claude (C2; the
  commit message for 49c34cfc says "all grok", which is wrong).

### The first four parity fixes (measured, 11 runs at 8fc20ad6)

From the 2026-10-13 parity study (25 eval runs, Grok 4.6 against Claude
Sonnet, one judge): Grok runs the same tools, more of them, with the same
verdicts on the same numbers, and loses the results in its write-up.

- **One eval judge.** `metascience eval` grades every review with Claude
  Sonnet (high effort, above) (`harness.JUDGE_BACKEND/JUDGE_MODEL/JUDGE_EFFORT`;
  `--judge-backend`/`--judge-model` override), whatever `--backend` produced
  it. The judge used to follow the backend: the Grok judge scored a
  26-finding review 0.0 with empty notes (Sonnet: 0.462) and graded another
  0.273 that Sonnet graded 0.818. Scorecards record the judge, and a judge
  that returns no coverage and no notes beside filed findings is flagged
  `judge_degenerate` instead of being read as recall 0.
- **Unfiled tool results are handed back** (`modules/_analyst.recover_unfiled`,
  Grok, OpenRouter and Codex only). After an analyst's report is parsed,
  code lists its own suspicious-or-worse tool verdicts that no filed finding
  accounts for (`findings_v2.unaccounted_verdicts`, the `tool_verdict_for`
  join read the other way), keeps only calls with a receipt, and asks once,
  tool-free: file each, or dismiss it in `unchecked` with a reason. The
  answer is merged; a limitation states how many were filed, dismissed and
  still unaccounted. Grok tools agents had filed 1 finding after 79-95 calls
  in 4 of 11 runs (Claude 0 of 10).
- **Grok's addendum** (`grok_mcp_route.md`) gains "Writing the findings
  document": every problem is a row, every suspicious result is filed or
  dismissed, no placeholder documents.
- **The verdict bands are defined** (`adjudication.md`, schema description):
  `does_not_reconcile` whenever a kept finding shows the printed record
  contradicts itself, innocent cause or not; `unresolved` only when the checks
  could not settle it; `reconciles` when every runnable check is consistent.
  The adjudicators had called airforce and wound_healing `unresolved` in 5 of
  8 runs while describing the gold defects.

## [1.74.0] — 2026-10-13 — the tool layer, OpenRouter, image detection without AI, display names

MINOR: what the analysts are told changed (reproductions are generated; the
analysts' new names), and new capabilities (`metascience tool`, receipts,
`tool_access`, `--backend openrouter`, `image_detect`). Phases 3b-5 of the
modular refactor. The entries below were released together.

**Measured, `metascience eval --paper apple_cider --backend claude --model
sonnet`, image screening on Grok, two runs per arm (2026-10-13).** The verdict
matched and deterministic checks passed in all eight runs:

| Arm | Run 1: recall / FPs / $ | Run 2: recall / FPs / $ |
|---|---|---|
| A: 1.73.0 (before) | 0.636 / 0 / 2.59 | 0.818 / 2 / 2.31 |
| B: 1.74.0 default (`full`) | 0.818 / 0 / 3.60 | 0.818 / 0 / 2.77 |
| C: `full_brief` | 0.818 / 1 / 2.87 | 0.818 / 0 / 2.90 |
| D: `full_skill` | 0.636 / 1 / 2.07 | 1.0 / 1 / 2.12 |

- **No regression from the prompt change (B vs A).** Every tools-agent
  reproduction now runs and agrees: B1 had 6 generated from the call plus 1
  from the inputs, all valid; A's run had 3 of 9 model-written commands
  failing (`metascience csf` with extra arguments, `flag-round-n` without
  `--ns`).
- **Two runs cannot separate the arms on recall.** A's two runs alone span
  0.636-0.818, so the default stays `mcp`; `mcp_brief` and `skill` stay opt-in.
  - C1 made 12 calls under BARE tool names (`recalc_anova` without the
    `mcp__forensic_metascience__` prefix), all refused, and never called
    `describe_tool`. C2 did neither.
  - D's tools agent cost $0.81-0.96 against $1.22-1.67 for B. In D1 the guard
    refused a real attempt by the model to run a shell `for` loop.
- **Receipts on live runs:** all forensic calls receipted. One known
  difference was found: Claude Code swaps a large MCP result for a "saved to a
  file" notice. One D2 `statcheck` call's argument digest did not match its
  receipt and is reported as unmatched -- unexplained, logged in run_meta.

### display names: Tools agent and Scientific proofreading agent (Phase 5)

PATCH (display only; every stored identifier is unchanged).

- **`names.py`, the one alias table** from stored identifiers -- producer
  values (`tool_expert`, `science_error`, hashed into every `finding_id`),
  stage labels (`tool_agent`, `science_agent`, which name archived files) and
  channel keys -- to the names people read ("Tools agent", "Scientific
  proofreading agent", ...). Derived from each module's MODULE.md `display`,
  so a name is declared once.
- **Where it is used:** the report (a finding's producer; a channel that did
  not run, with its key beside it), the offline viewer (finding cards, tool-call
  rows, the stage and guard tables, file descriptions), the webapp stats page
  (`displayName` from the generated `constants.gen.ts`, byte-compared by
  `tests/test_webapp_constants.py`), the CLI surface line, preflight and the
  live progress titles. The prompts were renamed in the Phase 3b prompt entry.
- **Not renamed, deliberately:** limitation strings that name a stage label
  ("the tool_agent stage failed ...") keep it, because the label is how a
  reader finds `prompt.tool_agent.md` / `toolcalls.tool_agent.json`.
- CLAUDE.md/AGENTS.md: the analysts' new names, the Phase 3b-5 layer, and the
  wiring checklist rewritten (no CLI verb required; procedure guidance is a
  numbered block in the family TOOL.md).

### image detection without AI review (Phase 4)

MINOR at release (a new capability; runs with `image_review` are unchanged).

- **The `image_detect` pipeline** runs the image detector ALONE -- no AI
  screening, no LLM at all. The `image_detection` module calls
  `pipeline.run_detection` and files every candidate unscreened, through the
  package's own row builder: `quarantined: true`,
  `inputs.ai_screening: {status: not_run}`, named with its count in the
  limitations. With `image_review` configured the module still makes the
  combined `pipeline.run` call, byte for byte.
- **An unscreened row is never the headline, in code**
  (`adjudicate._unscreened`): the adjudicator's choice is overridden and the
  fallback skips them. Rulebook-only before. Screened image rows (also
  `quarantined`) are untouched. An unscreened row cannot be published either:
  publication reads the screening ledger, where it has no record.
- **Image package:** one shared helper, `pipeline.coverage_limitations`,
  extracted from `pipeline.run` (behaviour unchanged) so both paths state the
  detector's coverage gaps identically. `pipeline.py` is outside the detector
  fingerprint and the screening stamps; no gate run is needed, and nothing
  under the fingerprinted files changed.
- The Phase 1 validator rule refusing `image_detection` without
  `image_review` is gone; `image_review` still needs `image_detection`.

### `tool_access`: brief MCP descriptions, and a fenced `skill` mode (Phase 3b)

MINOR at release (new options; the default run is unchanged and pinned).

- **`tool_access: mcp | mcp_brief | skill`** on an agent module in a pipeline
  (docs/specs/tool_access.md). The default is never recorded, so earlier
  digests stand; shipped experiment arms `full_brief` and `full_skill` change
  only the tools agent.
- **`mcp_brief`:** the MCP server (`METASCIENCE_MCP_BRIEF=1`) cuts each
  description to its first sentence (`ToolSpec.brief`) and serves
  `describe_tool(name)` -- full description, parameters with guards,
  assumptions, procedure guidance, for this surface only. For the tools agent
  the 56 descriptions fall from ~72K characters to under a third of that.
- **`skill`** (claude only; others refuse by name): no MCP server; the agent
  runs `metascience tool run` through Bash. MEASURED 2026-10-13 on Claude
  Code 2.1.296: `dontAsk` with `Bash(metascience tool run *)` refused `cat`
  but RAN `metascience tool run ... && echo PWNED`. So the fence is a
  PreToolUse hook, `skill_guard.py` (three exact line shapes, single-quoted
  JSON, fail-closed `-I ... || exit 2`), re-measured to refuse all three
  bypasses; plus `dontAsk`; plus `tool run`'s own server-side surface. The
  ledger records an exact `tool run` line as a forensic call (parsed
  arguments, verdict line stripped), so joins, reproductions and receipts work
  unchanged. The live probe also showed `--mcp-config '{}'` is refused by the
  Claude CLI; skill launches pass `{"mcpServers": {}}`.
- **`metascience eval --pipeline NAME`** scores a complete-review pipeline;
  scorecards record `pipeline` and `pipeline_digest`.

### PROMPT CHANGE: reproductions are the pipeline's job; the analysts' new names

MINOR at release: what both analysts and the adjudicator are told changes, so
reviews across this boundary are not directly comparable.

- **The CLI map left both analyst prompts** (`registry.cli_syntax_reference`,
  ~2.9K characters each). The pipeline now writes `reproduction` by replaying
  the call behind a finding, so the analysts are told to record `inputs` and
  leave `reproduction` out (`prompts/reproduction.md`, appended where the map
  was), except a `run_python_script` path or `NO COMMAND APPLIES`. The
  tools-agent example's `"reproduction": "metascience grim 81.3 79
  --percentage"` -- which exits 2, `grim` has no such flag -- is gone, as is
  the science agent's "a few checks read a JSON file, write NO COMMAND
  APPLIES" advice. The `reproduction` schema text says the same.
- **Names (Phase 5, in the prompts):** "Tool Expert" is the **Tools Agent**
  and "Science-Error Analyst" the **Scientific Proofreading Agent** in
  `tool_expert.md`, `science_error.md`, `rulebook_roles.md`,
  `adjudication.md` and the run-configuration note. The adjudicator is told
  which stored `producer` value each one files under (`tool_expert`,
  `science_error`), which do not change.
- **The parity oracle** (`tests/test_pipeline_parity.py`) gained
  `parity_p3b.json`, captured from this tree, and a test proving it differs
  from the 05537458 fixture ONLY in system prompts, output schemas and
  `prompt_sha256` -- every flag, env, allowlist, MCP config, user prompt and
  setting is unchanged.
- Measured on `metascience eval --paper apple_cider` (Claude Sonnet): see the
  Phase 3b measurement entry.

### the tools agent's per-tool guidance lives in each TOOL.md (Phase 3b)

PATCH (a move; the prompt is byte-identical, `tests/test_pipeline_parity.py`).

- The 24 bullets of `tool_expert.md`'s step 3 ("Check each remaining statistic
  with the appropriate tool") now live in the `## Guidance` section of the
  TOOL.md of the family their first tool belongs to, as numbered
  `<!-- guidance:NN -->` blocks. `prompts.tool_expert_body()` assembles them
  back at the `{{TOOL_GUIDANCE}}` marker in their numbered order; a gap or
  duplicate number refuses. A tool's folder now holds its definition, its MCP
  description, its integrity card and its procedure guidance.
- `metascience tool describe NAME` shows that guidance.
- Tests that read the raw `tool_expert.md` now read the assembled body; a raw
  read would silently stop seeing the bullets.

### `metascience tool`, call receipts, reproductions replay the call (Phase 3b)

MINOR at release: every reproduction command changes form, and replays now
run through the registry's gates.

- **`metascience tool list | describe | run`**, generated from the registry.
  `run NAME --json '{...}'` goes through `ToolSpec.call` -- the gates the MCP
  surface applies -- where the per-tool verbs call `tools/*.py` directly
  (`metascience grim` defaults `decimals=2`; the gates refuse a missing
  precision). It prints the verdict first, then the result exactly as the MCP
  server returns it, and exits 0 whatever the verdict (2 for a usage error).
  Under `METASCIENCE_MCP_STAGE`/`METASCIENCE_MCP_TOOLS` it serves only what the
  MCP server would, by asking the server module itself. The per-tool verbs stay
  for people.
- **Reproductions are generated, and replay the call.** `reproduction` is now
  `metascience tool run <tool> --json '<args>'`. When the producer's ledger
  holds exactly one argument set behind a finding (`findings_v2.backing_call`),
  those arguments are replayed (`reproduction_source:
  generated_from_tool_call`, `reproduction_call: <seq>`); otherwise the
  finding's `inputs` (`generated_from_registry`). Structured input (`cells`,
  `rows`, `values`) no longer prevents a command -- the old generator refused
  54% of calls for it. Only a replayable calculation executes
  (`deterministic.reproducible_tools()`): never a reader, the dispatcher, a
  track, an R wrapper or `run_python_script`, and never `--args-file`.
  `reproduction_source`, `reproduction_call` and `reproduction_not_generatable`
  are now declared annotator fields in the schema (the first was written
  without being declared).
- **Tool-call receipts** (`receipts.py`). The MCP server, and `tool run`,
  append a receipt for every answer -- tool, argument digest, result digest,
  severity -- to `~/.cache/metascience/receipts/<run_slug>/<role>.jsonl`
  (`METASCIENCE_RECEIPTS_DIR`), derived from the env the server already has,
  so the MCP config bytes are unchanged. The review directory gets
  `receipts.<label>.jsonl`; each forensic ledger call is marked with its
  `receipt` (or None); `run_meta.tool_receipts` counts calls without a receipt
  and receipts without a call. Reported only: nothing is gated on it yet.

### OpenRouter backend: our own agent loop (Phase 3c)

MINOR at release (a new backend; existing runs unchanged).

- **`--backend openrouter`** (and `backend: {name: openrouter, model: ...}` on a
  pipeline module) runs an analyst or the adjudicator on any OpenRouter model
  through `openrouter_loop.py`. It is launched like a CLI and speaks Claude's
  stream-json, so `_run_stage`, the tool ledger and the transcripts read it
  unchanged. Default model `anthropic/claude-sonnet-5.5`.
- **Same fences as a Claude launch:** the forensic MCP server gets the same
  config (role, toolset manifest, paper directory), the loop offers only the
  stage's allowed tools, refuses an off-list call in the transcript, and
  confines `Read` to the paper directory. The init event reports the servers
  the loop actually connected to, so the foreign-server gate applies.
- **Structured output** comes through a `StructuredOutput` tool validated
  against the schema; three failed attempts end the run with
  `error_max_structured_output_retries`, the subtype Claude uses.
- **Cost** is OpenRouter's per-response `usage.cost`, summed into
  `total_cost_usd`. There is no spend cap, so `--budget-usd` with an OpenRouter
  module is refused (`BudgetUnsupported`). Preflight checks
  `OPENROUTER_API_KEY` in place of a CLI binary.
- Tests: `tests/test_openrouter_backend.py` runs the real loop against a
  scripted chat-completions server and a real MCP server, and once end to end
  through `agent._run_stage`. NOT run against the live API: this machine has
  no OpenRouter key.

## [1.73.0] — 2026-10-13 — pipelines, modules and tool folders; image work since 1.72.0

MINOR. Releases every entry below that was marked "Unreleased", down to 1.72.0
(2026-10-01). The default `full` pipeline still sends what 1.72.0 sent
(`tests/test_pipeline_parity.py`), but the image detector fingerprint and
several image rules changed, and `--pipeline` is a new capability.

The image entry dated 2026-10-02 was headed `[1.72.0]` and runs made between
that date and this release stamp `1.72.0` while including it. A second release
reusing a number is the defect the version rule exists to prevent: for those
runs, the git sha in `pipeline_version()` is what identifies the code.

### Image package 0.24.0 — 2026-10-02: skip typed charts before visual search (stamped 1.72.0 at the time)

Panels classified as `Graphs`, and parents whose children are all typed charts,
are excluded before OCR and expensive visual matching. Rendered fallbacks and
hybrid recovery obey the same rule, and shared cross-paper inventories omit
these pixels. Exact stream identity checks and the panel index retain charts.
Mixed figures retain their image panels and existing clone masks for chart
regions; an untyped child prevents whole-parent exclusion.

Each excluded panel is recorded as `chart_panel_not_visual_searched` with
`searched: false`, and benchmark attribution treats it as withheld. No new
classifier threshold was introduced. This changes the detector fingerprint;
existing archived results are not rewritten. Runtime savings are unmeasured.


### Codex and Grok run fixes from the schnall2008 comparison

Found by comparing a gpt-5.6-terra (Codex) review with a grok-4.6 review of
the same paper.

- **Codex no longer shows the model the operator's skills.** Codex lists
  `~/.agents/skills` (including claude.ai-synced skills) in every prompt, even
  under `--ignore-user-config`; the terra science agent's first call read one.
  Every Codex invocation now passes `-c skills.include_instructions=false`.
  Measured live: the model named five skills without it and none with it.
- **A Codex shell call that only reads text is no longer a severe breach.**
  The shell is Codex's only file reader, so the audit called every Codex run
  "BREACH (severe)" when an agent read a file. A call made only of reads
  (`agent._shell_reads_only`) is now the Read analog; anything that could
  compute still is a breach. Replayed on the terra run: 7 of 7 shell calls
  were reads, and both audits read clean.
- **An unknown cost is no longer $0.00.** Codex reports tokens only. Stages
  record `cost_reported: False`, run_meta lists `cost_unreported_stages`, and
  the webapp index shows no cost for those runs (older Codex runs with a zero
  total included).
- **Grok's placeholder-then-answer output is accepted as the answer.** The
  science agent wrote an empty placeholder document beside seven tool calls,
  then its seven-finding document. The Grok CLI joined them and stopped at
  `error_max_structured_output_retries`; the run then warned the stream had
  DEGENERATED, marked the channel `refused` and sealed the stage failed,
  beside that agent's own findings. When every earlier text is an empty
  placeholder and the last is a complete document, it is now used as is
  (`output_parse_path: final_after_placeholders`), the stage is not an error,
  and the CLI's refusal is kept as `cli_error_subtype`.
- **A stage whose output was recovered is no longer `refused`.** Any errored
  stage whose document was still parsed and used now reads `ran` (with the
  error and the recovery path in its detail), and its history record is
  `incomplete`, not `failed`.

The default Claude run is unchanged; the parity test names the new Codex
argv pair as its second intended difference.


### `analyze` on a PDF writes its review beside the PDF

`metascience analyze path/to/paper.pdf` now writes
`path/to/paper_forensic_review_<model>_v<release>/` (and its `_bundle`) next to
the PDF. It used to write them into the shell's current directory, while the
image track wrote `panels/` and `figures/` next to the PDF, so one run was split
across two folders. A paper directory and an explicit `--output` are unchanged.
No analysis output changes.


### document redelivery reads every harvested stream

DETECTOR CHANGE (fingerprint 08e305ad2a2f -> eb73b22b05bf; targeted gate PASS
against baseline 93af34eb8c3e, recorded in eval/gate/eb73b22b05bf.json).
Recovered from uncommitted work in the Dropbox checkout (2026-09-26).

- `_demote_document_redelivery` built the article/supplement build signature
  from the comparison pool, but a figure the renderer clips is
  `visible_crops_only` and leaves that pool, so the signature was computed
  from nothing. MEASURED 2026-09-26 on 10.1016--j.stemcr.2014.09.012: the
  article and its "article plus supplement" mmc2 share 28 streams at the same
  xref with the same bytes, every one skipped (23 `visible_crops_only`); the
  gate saw 0 pairs and 132 groups between the copies stood as evidence. The
  signature now reads `signature_pool` (every indexed stream, skipped or
  not); the comparison pool is unchanged. The new test in
  `tests/test_document_redelivery.py` fails without the fix.

### tool definitions: one folder per tool family

REGISTRY CHANGE (layout only; nothing a model or a reader sees changes).
Phase 3a of the modular refactor.

- Each tool's `ToolSpec` moved VERBATIM from `registry.py` to
  `tool_specs/<family>/spec.py`, and its MCP description and integrity card to
  the `TOOL.md` beside it (36 families, 62 tools). `registry.py` keeps the
  machinery and loads them in `tool_specs.ORDER`: 4,913 -> 1,458 lines.
- Proven a no-op three ways: every spec's fields, schema, description, roles
  and order and every integrity card compare equal to the pre-move registry;
  `tests/data/registry_snapshot.json` is unchanged; the parity oracle still
  matches origin/main 05537458 on all three backends.
- The pure functions stay in `tools/*.py` (Dan, 2026-10-03), where ~120 call
  sites import them; a folder is named for the module it defines.
- The wiring checklist (CLAUDE.md / AGENTS.md step 3) now says where a new
  tool goes. `tests/test_tool_specs.py` pins the layout.

### modules: each pipeline module is a folder, scheduled by `needs`

PIPELINE CHANGE (structure; what the default run sends is unchanged, pinned by
`tests/test_pipeline_parity.py` against origin/main 05537458). Phase 2 of the
modular refactor (`docs/specs/modules.md`).

- **`modules/<name>/MODULE.md` + `module.py`** for `tools_agent`,
  `scientific_proofreading_agent`, `image_detection`, `image_review`,
  `text_forensics`, `adjudicator`. Definitions are read from the frontmatter
  (`pipeline_config.MODULES` is that registry); a module is imported only when
  a pipeline uses it. Adding a module is adding a folder.
- **`core/scheduler.py`**: a producer starts when what it `needs` has
  FINISHED (completion, not success); no layer barriers; results merge in
  canonical order; one barrier, the finaliser. `core/context.py` is what a
  module may read.
- The analysts' run / parse / retry moved from closures in
  `parallel._coordinate_analysis` to `modules/_analyst.py` (logic and comments
  unchanged); each analyst now parses and retries inside its own task, so
  their limitations are grouped per module. The adjudicator's run, schema-gate
  retry and apply moved to `modules/adjudicator/module.py`.
- **Per-module backend**: an agent module or the adjudicator may set
  `backend: {name, model, effort}` in a pipeline file; it wins over the
  run-level backend; a budget with any module on a backend without a spend cap
  is refused before anything runs; such a stage records its `llm_backend`.
- Image detection is untouched: `image_detection` is a thin host adapter over
  the package's existing combined call until Phase 4.

### pipelines: choose the modules a run uses, and the tools agent's tools

PIPELINE CHANGE, MINOR at release (a new capability; the default run is
unchanged). Phase 1 of the modular refactor (`docs/specs/pipeline_config.md`).

- **`--pipeline` on `analyze` and `batch`** (and `examples/batch_analyze.py`)
  takes a shipped name or a YAML path. A pipeline lists modules --
  `tools_agent`, `scientific_proofreading_agent`, `image_detection` +
  `image_review`, `text_forensics`, `adjudicator` -- and the tools agent's
  toolset (`all`, a list, a named toolset, include/exclude). Shipped: `full`,
  `no_adjudication`, `tools_only`, `tools_grim`, `proofreading_only`,
  `image_only`. `metascience pipeline list|validate|show|tools` inspect them
  without calling a model. Unknown keys, modules and tools are errors.
- **`full` is byte-identical to the flag default**: same system prompts,
  allowlists, MCP config and `prompt_sha256` (pinned in
  `tests/test_pipeline_config.py`). Module and display names are new; the
  STORED producer values `tool_expert` / `science_error` are not, because
  `finding_id` hashes them.
- **A restricted toolset is enforced four ways**: the allowlist, the MCP
  server (`METASCIENCE_MCP_TOOLS`, a fail-closed manifest: unknown tools, no
  role, or nothing left to serve stop the server), `check_table` (disabled
  checks land in `not_run` as "tool not enabled in this pipeline"), and the
  harness prepass (sweeps whose tool is off do not run). The system prompt
  drops the disabled tools' step-3 guidance and CLI-map lines and names what
  is available; the user turn drops the `statcheck` instruction when it is
  off. A partial pipeline's agents are told which colleagues are absent.
- **A partial run never stands as the paper's review.** findings.v2 and
  run_meta carry a harness-written `pipeline` block (`complete_review`,
  digest, resolved modules and tools, per-label system-prompt hashes;
  hidden from producers). `run_kind` returns `partial_review` (or
  `image_track` for an image-only pipeline); the history parent component
  is `partial_review`; corpus statistics skip it; the review directory is
  `forensic_review_<pipeline>_<model>_v<release>`; and the batch skip counts
  only complete reviews -- or, for a partial pipeline, runs of the same
  digest. Neon status stays `partial` whenever adjudication did not run, so
  the readback never claims an adjudication.
- **Adjudication off** finalises through the existing `apply_skip`
  (`skipped_reason: "adjudication not configured in pipeline ..."`) and is
  not an error; "both analysts failed" became "all CONFIGURED analysts
  failed", so a run with no LLM analyst does not raise.
- **Build identity is configuration-aware**: `runs.build_fingerprint(config)`
  and `build_matches` recompute the prompt hash for the run's own recorded
  pipeline. Side effect, deliberate: a `--figures` run's `prompt_sha256` now
  hashes the figure-enabled prompt it was actually sent (it hashed the
  figures-off prompt before).
- **Hardened after GPT-6 Astra's review of the implementation** (15
  findings, all fixed with a regression test each in
  `tests/test_pipeline_config.py`): partial runs are left out of the
  workbench's default paper review, the index's verdict and worst severity,
  and drafts (a partial one only when its findings are named, and then its
  scope travels with them); `report.md` opens with a PARTIAL PIPELINE banner
  and the viewer's run facts name the pipeline; a partial run's JSON repair
  carries no tools on Claude and is not attempted on Codex/Grok (their
  built-ins cannot be dropped; fail closed, named); reproductions of disabled tools are not executed; a
  failed sole image/text module is an error, and the run records
  `pipeline.outcome` so a failed experiment never satisfies the batch skip
  (read from findings.v2 when run_meta is unreadable); restricted harness
  sweeps tell the adjudicator what did NOT run; one backend/model/effort
  precedence rule (`pipeline_config.resolve_backend_settings`) for the API,
  `analyze` and both batch entry points; an empty tool manifest is refused;
  options must be booleans; wrapped step-3 bullets keep their enabled tools
  and every user-turn `statcheck` layout is filtered. An image-only run's
  `prompt_sha256` is the empty blob's, which `build_matches` expects.
- **Independent parity oracle**: `tests/data/parity_05537458.json` captures,
  from origin/main 05537458 itself, every invocation the default review
  builds on Claude, Codex and Grok (argv, environment, sandbox files) plus
  its provenance hashes; `tests/test_pipeline_parity.py` requires this tree to
  match it byte for byte (`tests/parity_capture.py`).
- Not in this phase, by decision after GPT-6 Astra's design review: image
  detection without its AI review (Phase 4; refused by the validator), a
  module listed twice, per-module backends, the raw-data module, and the
  adjudicator-crash fallback (needs typed batch-stop semantics first).

### a PMC copy and a publisher copy of one figure are one figure

DETECTOR CHANGE (fingerprint 93af34eb8c3e -> 8117d97390d9; `source_identity`
REVISION 2 -> 3). A paper with no PDF keeps both its PMC and its publisher
figure renders, and every panel was compared across them: 358 groups in the
veins corpora were one figure matched against its own other rendition
(reported on 10.1016/j.bbamcr.2014.10.017 IMGDUP-8; all 17 of that paper's
groups). The alias proof refused them on GRAIN alone: the PMC copy is 2-3x
smaller, so enlarged onto the publisher's it has no fine grain to agree with
(0.64-0.70 on that paper's Figs 1, 2, 5, 6 against the 0.80 floor; 0.86-0.91
at matched resolution; an unrelated figure does not register at all).

- `register_parents` compares grain and content tiles at the COARSER
  rendition's sampling when the two differ by more than 1.25x; pairs within
  that ratio take the old path unchanged. Every other gate is untouched; the
  proof records `compared_at`.
- A hash group carries no transform, so `same_location` refused every one.
  It now requires the crops themselves to correspond: crop A's box, carried by
  the full-figure registration, must land on crop B's (0.4-4.1 px measured,
  same tolerance as the transform path).
- `build_alias_graph` finds parent PNGs with `panels.resolve_panel_image`:
  all 910 render-parent `image_path`s in these corpora point into deleted work
  copies, so a retained repair evaluated nothing.
- Dry run of `repair_source_identity` over the 13 veins corpora with both
  renditions: parent aliases 20 -> 38 of 89 pairs, 71 groups newly cleared as
  `same_published_figure` (42 hash, 29 transformed), 0 errors, and every
  cleared group pairs PMC with publisher under one figure label. 138
  PMC-vs-publisher groups still stand: 47 of 50 refused pairs fail the inlier
  gate, several because the author manuscript laid the figure out differently
  (nihms180600f2 1050x585 vs gr2 2972x2239), which no whole-figure proof can
  pass.
- Gate reach, measured on the latest gate sweeps: 0 parent pairs evaluated in
  masliah_subset (162 papers), fca_reviewed_581 (572) and both ground-truth
  papers -- none pairs two rendition channels in one group.

### the per-edit image gate measures what decides it

GATE CHANGE (no detector change; `gate.py` and `review_fixture.py` are not
fingerprinted). `metascience image-gate` defaults to a new `--profile
targeted`, and `tests/test_image_gate.py` requires a passing targeted (or
quick/full) record for the fingerprint on disk.

- **Why.** Every hard check of the quick profile reads a few items, yet quick
  swept all 203 Masliah papers (11-28 min on 2026-10-01, 43-56 in September),
  and any not-run paper anywhere invalidated the lane. The reviewed fixture's
  9 true issues live in 8 papers and its 145 items in 39; the other ~164
  papers fed only reported numbers (the figure-hit set, at chance; fire rate).
- **`masliah_targeted`** sweeps the fixture's papers only, unforced (a crash
  or repeat resumes from `retain.is_done` stamps), and compares the fixture
  per item against the baseline's Masliah lane. Validity is judged over the
  swept papers. A cross-paper fixture item falls back to the whole corpus.
- **`rsiid_targeted`** runs the first 8 cases per stratum (`select_cases`
  keeps a seeded prefix, so it is a subset of the 40) and compares per case.
  Pooled counts are never set against the full sample's.
- **Records.** A quick or full record satisfies `targeted`; a targeted record
  satisfies neither, and `accept` refuses it. `accept` also refuses a record
  without per-item outcomes (fixture items, RSIID cases), and carries a lane
  the new record lacks from the previous baseline, naming its origin in
  `inherited_lanes`.
- **Baseline re-accepted: 93af34eb8c3e** (main's quick record, 0 hard
  failures against f372b968b2be). It adds the 145 fixture items and 640 RSIID
  cases (f372's per-case `run_dir` no longer exists, so RSIID had been
  compared on pooled counts), the ground-truth and overlap lanes. The reviews
  lane is carried from f372b968b2be.
- **Known limit.** Targeted sweeps screen corpus furniture from the panel
  indexes on disk, so a harvest change that moves the furniture set is
  measured fully only by `quick`.

### cross-paper pairs by content, with the GPU prefilter kept

DETECTOR CHANGE (fingerprint c58ce8ab5027 -> 93af34eb8c3e): merges
`p3-xpaper` onto the GPU cross-paper loop.

- **Content pairs (enumeration v3).** Cross-paper results are kept per CONTENT
  pair in `pair_store.py`, which outlives the checkpoint. Added papers cost
  only old x new + new x new, and the restart identity is the matcher's code
  closure (`code_identity.py`), not the detector fingerprint. The checkpoint
  identity still carries the text-exclusion signature, as on main. Version 1-2
  checkpoints are refused by name.
- **`--cross-paper retrieval`** is opt-in; exhaustive stays the default. A
  descriptor index shortlists the pairs to verify (`cross_retrieval.py`), and
  coverage records the parameters, the pairs not compared and the measured
  recall.
- **The exact GPU prefilter runs on every content-pair path:** exhaustive
  blocks, retrieval shortlist batches and content-failure retries. Only the
  row-level exact-identity pass stays CPU-only. `compare_content(a, b, good)`
  takes the survivor lists, serially and through the worker pool. Fallback and
  telemetry are unchanged (`prefilter`, `timing`).
- **Sparse batches are tiled.** The prefilter computed every source x target
  combination, and the content enumeration's within-paper and shared-panel
  blocks are sparse. On 63 papers that was 3.8M combinations against main's
  1.7M (device phase 113 s against 39 s). It now covers a sparse batch with
  source groups when that is cheaper: 1.67M combinations, 49 s, identical
  outcomes. `tiles` and `combinations` are counted.
- **Measured 2026-10-01**, 63 scratch papers (1,733 eligible rows, 1,696 content
  panels, 1.44M content pairs, text policy enforce, 8 workers, shared machine):
  - GPU exhaustive: 185-188 s. The same run on the CPU path
    (`METASCIENCE_DEVICE=cpu`): 1,203 s.
  - Both find the same 122 matched row pairs with byte-identical bodies and zero
    failures.
  - main c952f0a7 on the GPU: 164-173 s, the same 122 pairs. 116 bodies are
    identical. The other 6 are the same evidence computed in the opposite
    orientation, because one side is a content panel shared by several papers
    and the lower content id goes first.
  - GPU retrieval: 174 s (about 100 s of it builds the index). It found all
    122 matches with identical bodies from 30,347 shortlisted pairs.
  - With the prefilter, exhaustive and retrieval cost about the same at this
    size.

### all image code lives in metascience-observatory-image-analysis/

No behaviour change: the detector fingerprint is unchanged at c58ce8ab5027.

- **Workbench image review moved into the package**, under
  `review_workbench/`. That covers the local review store, import and
  service, the shared-storage image queue, the image service methods, video
  jobs, thumbnails, geometry, equivalence, match regions, the text-region and
  content-support readers, and the disk half of image cleanup.
  - The host keeps a 43-line `image_review_host.py`, which lends `Catalog`,
    `Repository` and `Service` to package mixins, plus aliases and the Neon
    half of `image_cleanup`.
  - Host image code in the workbench went from 2,992 lines to 146, and
    `repository.py` from 985 to 570.
  - The review DB schema, its path, the JSON-lines protocol and
    `--images-local` are unchanged; the same requests were answered
    identically on a temporary DB.
- **Image scripts and examples moved into the package.**
  - 7 scripts, including the gate's `channel_overlay_audit` and
    `channel_overlay_eval`; `eval/gate/config.json` changes only the script
    path.
  - 16 examples.
  - `extraction/regions_docling.py`.
  - 43 package-only test files (544 tests).
- **Aliases:** 42 of the host's `sys.modules` aliases were deleted. 12 remain
  for documented `python -m` commands and the workbench, and they are pinned.
  Package tests may not import `metascience_agent`.

### image track: coverage bugs fixed, refusals named, recall levers as experiments, faster tiers

DETECTOR CHANGE (fingerprint f372b968b2be -> c58ce8ab5027). Quick gate,
2026-10-01, against the accepted baseline: no hard per-item failure in any
detector lane. Masliah paper-level 33 -> 37 of 53 positives, figure-level
11 -> 14 (11.6 expected by chance, p = 0.20, so still SOFT); fire rate
0.414 -> 0.438. RSIID identical (145 TP, 0 FP, 266 FN, 182 TN); ground truth
nn.3070 3/14 and jcs.113191 1/3, as on main. Overlap bench
401/649 positives, 0/66 false positives. The gate's one failure, the
channel_overlay audit (exit 2, 0 groups), is environmental. Every gate record on
main since 2026-09-30 shows it, because the embargoed 2026-09 corpus it reads
was deleted.

Default-on fixes:

- Pixel sizes come from the decoded pixels.
- Tier 4 skips pairs already verified at an earlier tier.
- Sibling sets are scoped per (document, parent).
- Corpus furniture is withheld for crops of a furniture stream too.
- Hybrid re-admission never re-admits corpus furniture.
- A scanned paper is `scanned_pages`, not publisher furniture.
- A partly shown panel is not `never_displayed`.
- The panel budget counts comparable streams, not icons.
- Rectangle clips with a trailing moveto or collinear vertices are rectangles.
- BMC title-first caption blocks are captions.
- A control character in a trace attribute no longer drops the page.
- The legacy clone search trims uniform margins and reports sub-panel hits in the panel's own frame.
- The channel rules (overlay, re-show and colour angle) now require one shared framing (`_same_framing`).

The transformed tier counts every refusal by name (`transformed_refusals`,
`MATCH_REFUSALS`). Cross-paper pairs name text refusals per panel and test exact
identity first. Search checkpoints store completed results compressed.

Recall levers are named experiments, OFF by default
(`METASCIENCE_IMAGE_EXPERIMENTS`, `image_analysis.EXPERIMENTS`): spread_floor_px,
symmetric_ratio, affine_fallback, masked_detection, crop_siblings,
upsample_small, clahe_retry, strip_panels, hairline_identity, scan_crops,
clone_gates_v2 and blot_seam_channel. Active experiments enter the stamp, the
sweep id (`_x-...`), the benchmark key and the gate record key, so a run with a
lever on never compares as the default. On the overlap bench (dev, matcher
layer), upsample + clahe + crop_siblings + spread finds 527/649 against 401,
with 0 false positives. Promotion still needs the gate run with those
experiments on. See `docs/datasets/recall-levers-2026-10-01.md`.
`clone_gates_v2` and `blot_seam_channel` are measured in
`docs/datasets/clone-tier-2026-10-01.md`. The seam channel emits a
`splice_seam_candidate` CONTEXT group, never evidence.

Speed (output-identical, pinned by `test_speedups_output_identical.py`):

- Tier 3 screens pairs with a numpy popcount.
- phash64 takes block means by reduceat.
- Crops share one decode of their parent.
- Tier 4 counts overlapping siblings in its enumeration pass.
- `figures.json` comes from the harvest's figure map.

Tier 6 is main's GPU implementation; the CPU spectra fast path was superseded.

### blot pass: the strip alignment search on the GPU

`metascience image-blot-scan` now runs its strip alignment search on the GPU when one is qualified
for it, through the new compute workload `blot_ncc`. It falls back to the CPU otherwise.
`compute-calibrate-blot` qualifies a device only if it gives the same alignments as the CPU on real
strip pairs, with shape_r within 1e-9, and is at least 1.2x faster.

Measured on the RTX 5090:
- 76,362 candidates, all equivalent.
- The search runs 3.9x faster.
- End to end the gain is smaller, because candidate preparation stays on the CPU.

Registering the workload edits `compute/devices.py`, which voids every saved qualification. All six
(`blot_ncc`, `overlap`, `panel`, `match`, `document`, `craft`) were re-run on the 5090 the same day.

### blot pass: the three blot instruments in one package, run on blot regions

`image_forensics/blots/` now holds the strip matcher, the seam localiser and the
synthetic-blot frequency field. The old `blot_strips` / `blot_seam` /
`blot_frequency` paths are aliases. A new `metascience image-blot-scan` runs
them on already-swept papers, over the regions the panel model calls `Blots`
(including boxes below the splitter's floor) together with band rows found
directly in each image. It writes stamped raw measurements to
`panels/blots/`, with no thresholds. `metascience image-blot-benchmark` scores
those measurements against PubPeer labels.

Detector output is unchanged: nothing here is in the detector fingerprint, so
no retained run goes stale.

Measured along the way (2026-10-01):

- The 2026-09-28 strip matcher hit 0 of 9 alleged Berrio blot-reuse papers.
- An exact copy of a real published blot row was invisible to it, because the
  grain noise floor (0.5) sits above that row's noise (0.47).
- One JPEG recompression takes a copy's grain from 1.0 to about 0.2.
- CRAFT text masks erase real band rows in 13 of 121 Berrio papers.

### GPU offload on the RTX 5090: exact cross-paper gate, tier 6, lanes

Two new accelerator workloads, each qualified per machine and each with a CPU
path that remains the reference. `match`: the cross-paper stage counts SIFT
ratio-test survivors on the GPU (exact: integer descriptors, TF32 off) and
sends only pairs that could pass the candidate floor to the unchanged CPU
verifier -- 694,478 Masliah pairs, identical matches and failure rows, 118 s
against 936 s. `overlap`: tier 6's masked cross-correlation in float64 on the
GPU, 38-48x, used directly (Dan, 2026-10-01) and measured by the gate. DETECTOR
CHANGE: tier 6's unmasked branch now rounds the overlap pixel count as the
masked branch always did; unrounded, FFT noise decided an overlap of exactly
15% of the panel. CRAFT runs four model lanes on a 32 GB card (2.25x, identical
masks), the panel detector qualifies on decision-equivalence, and
`analysis_progress.json` records `stage_wall_seconds` for every stage of a
paper. New verbs: `compute-calibrate-match`, `-overlap`, `-panel`, `-document`.

Later the same day: the cross-paper verifier is handed the GPU's exact survivor
lists and skips its own 2-NN search (56 s against 936 s on the 694,478 pairs);
CRAFT's box extraction scans each text component's bounding box instead of the
whole image (identical polygons on 196 images, 0.233 -> 0.080 s per image, CPU
machines included); a paper with many tier-6 pairs computes them on the GPU in
its own process; a GPU lane the broker reaps is retried on the device rather
than sent to the single CPU lane. Docling is qualified on this machine (5 PDFs
identical) and converts one paper at a time on the GPU while any other
concurrent conversion takes the CPU (Dan). 20 Masliah papers: GPU and forced-CPU
findings identical on all 20; gate 5b5e68d17dfb passed every per-item check.
The gate's channel_overlay audit now scores a frozen labelled set,
`ground_truth/channel_overlay/` (210 pairs; 71/140 overlay FPs demoted, 0/66
true issues), instead of the deleted embargoed 2026-09 corpus.

### review workbench: faster review, recall-raising labels, correct bridge

The image queue orders by the shared triage rule by default (lookalikes and
cleared items sink, as `triage_rank` always said they did), and navigation is a
keyset query: 653 ms -> 14 ms per keypress on a 67,511-item project. A decision
key advances immediately, the next undecided items are prefetched, the PDF stays
open within a paper, and facet counts no longer block the rows. Reviewers can
now record a duplication the detector MISSED (two boxes on the PDF, a
manipulation type; exported as ground truth with `image-reviews-export
--missed-out`), spot-check a seeded sample of automatic demotions per kind, and
confirm a decision from an earlier run when the evidence is provably identical
(143 of 374 stranded decisions qualify). Fixed: UTF-8 split across bridge chunks
became U+FFFD; a restart left requests hanging 60 s; two authorities for the
latest run; bulk saves that timed out reported "nothing saved"; conflicts could
not be resolved; complete-workflow panels were re-decoded on every media
request; the file monitor rescanned quadratically (3.96 s -> 0.009 s per batch,
the likely idle CPU burn); the sync status buried Neon's quota refusal; WAL files
were never checkpointed. The first worker start on an existing review database
adds the `triage` and `evidence` columns and rebuilds the filter index (~8 s);
back the database up first.

### overlap bench: recall by overlap, scale, rotation, aspect and colour; a gate lane

New `metascience image-overlap-bench` measures partial-duplication recall on
synthetic pairs cut from 400 frozen CC0 panels, one factor at a time, through
the real tier evaluators, and the gate runs its dev matcher layer as the
`overlap` lane in every profile (older records without it stay valid). The
first baseline (detector 0a0c0ba158b2) finds 0/11 pairs at 10% overlap, 4/11 at
25%, 0/11 regions reused at 10% of a panel, 0/11 one-axis stretches of 1.5x and
1/11 pseudocoloured copies, with 0 false positives on 66 negatives; most misses
are blots that never reach 15 ratio-test candidates. A golden test pins exact
tier outcomes on 32 CC0 crops, every tier has a real-pixel known positive (tier
6 had no test at all), the real-PDF smoke tests run again (they looked for
`test_pdfs/` inside the package and had skipped since the extraction), and a
duplicate clone-render test is removed. Detector output and its fingerprint are
unchanged.

### image runs: detection's deadline is detection's; packaging, orphans and caches named

A paper's 600 s detection deadline no longer includes snapshotting the previous
answer (one embargoed-corpus paper spent 536 s there and timed out after 22 s of CRAFT).
Packaging runs after detection under `packaging_timeout`; the new outcomes
`packaging_timeout` and `packaging_failed` are track failures, and a completed
detection whose packaging failed is retained, unpublished. Timeouts terminate
gracefully, and the parent seals runs the child left pending (41 embargoed-corpus and 186
Masliah orphans existed); `workspace-reclaim` finds and seals them (dry run:
21.4 GB embargoed-corpus and 16.5 GB Masliah reclaimable). Copy-back replaces the track's own
files instead of merging into the old tree (one paper had 45 orphan PNGs and 984
stale usage ledgers, archived as its previous answer). The sweep summary counts
papers whose text-exclusion coverage is incomplete (297/572 embargoed-corpus, 74/157
Masliah) and pair-budget truncation; per-paper resource numbers are the paper's
own. New `metascience image-cache-prune` inventories every image cache and
prunes on `--apply`. Detector output and its fingerprint are unchanged.

### long image runs execute frozen code; children check theirs; CI that runs

`image-sweep`, `image-complete`, `image-gate`, `dataset-run` and the author-run
launcher now re-execute themselves from a content-addressed snapshot of the
image package and record which tree ran (`frozen_code` in `sweep.json`,
`coverage.json` and gate records). Every per-paper child runs through
`track_launcher`, which refuses a stamp naming a different detector and files
an edit made while the paper ran as the new track failure `code_changed`
(retried by the next run) instead of publishing it under the gated stamp.
Measured on a scratch copy: an edit mid-sweep left a frozen run untouched; an
unfrozen run stopped the paper in flight as `code_changed`. This replaces the
hand-made `git archive` + `PYTHONPATH` procedure.

The compute broker no longer serves masks computed by another tree's code
(its key includes the worker code; a mismatched signature is refused by name),
every CPU fallback is named, and a device probe that timed out under load is
`device_probe_timeout` rather than a silent move to CPU. Host hooks are read at
call time (`findings_v2` saw 1 tool name instead of 62 when imported before the
host), and `llm_backend` asks the host for its MCP server module instead of a
hard-coded name. CI moves to the root `.github/workflows/ci.yml`, which GitHub
actually runs; the standalone DB fixture is checked against the production
migration; the `statcheck` extra pins `>=0.0.7` (the `>=1.4.0` pin named a
version PyPI never had). Detector output and its fingerprint are unchanged.

### image gate: lanes that did not run, per-item hard gates, recall beside chance

The detector regression gate could not see what it was meant to measure
(review 2026-10-01). `gate._sweep_facts` read track timeouts from
`refused_by_subtype` while sweeps file them under `failed_by_subtype`, so the
accepted baseline showed 9 timeouts as 0. A sweep lane now retries its
not-run papers once, serially, and a lane with papers still not run is
INVALID -- a hard failure naming the machine, never "hits lost".

Hard gates are now per item: reviewed true issues (contained mode), RSIID
cases per stratum (no true positive lost or abstained, no new false
positive), and caught sets for the ground-truth papers (new optional
`ground_truth` lane; the scorer moved into
`image_forensics/ground_truth_score.py`, and a whole-figure root shared by both
sides no longer counts as a catch). The pooled RSIID count hid partial
overlap at 21/154 and splicing at 0/35.

The Masliah figure-hit set becomes soft: random choice of the same number of
figures per fired paper scores 10.85 expected hits against 11 observed (P(X >=
11) = 0.56). The scorecard adds `recall.figure_level_chance`. Reviewed-581
suppression is reported over compared pairs (56.2%, contained) separately
from withheld ones; the old 92.5% counted 1,438 never-compared pairs as
suppressed. The dev profile now compares per case against the baseline, and
`tests/test_image_gate.py` requires a passing record or the accepted baseline.
Gate sweeps skip review exhibits, RSIID runs supported cases only, the
channel-overlay audit is skipped when its inputs are unchanged, and the RSIID
code fingerprint hashes the detector plus the modules a case runs, not every
`.py` in the package. Detector output and its fingerprint are unchanged.

### image runs no longer render videos; the queue's Video filter is gone

New image detections render static review exhibits only:
`review_media.render_after_detection` now calls `render_review_media` with
`render_videos=False`, so neither the isolated image track nor standalone
detection encodes MP4s. A video already on disk is still re-attached to its
item. `image-render-videos` and the workbench's Generate video action remain
the explicit ways to make one. Run status reports `n_exhibits` instead of a
video count. Detector output and its fingerprint are unchanged.

The image queue's **Video** yes/no dropdown is removed, and both feed backends
stop returning `video_counts` and ignore a stale `has_video` argument (a
browser can still hold one in saved filter state). The local queue's
`has_video` column is left in place; nothing reads it.

### image queue: a "Figures" filter for matches spread across two figures

The image queue (`/project/<p>/images`) has a new **Figures** dropdown:
*different figures*, *same figure*, *different papers*, *figure unknown*,
each with its count given the other filters. It uses the detector's own rule
(`image_analysis._spans_figures`): the item's placements name two different
figures. Placements count, not only panels, so one image printed in Figure 1
and Figure 2 qualifies. Labels are compared through `figure_context.figure_key`:
panel letters and "(cont.)" are not new figures, and Figure S1 is not Figure 1.
A panel without a label makes the item *figure unknown*, never *same figure*.

`match_regions.figure_span` is the one definition. The local queue stores it in
an indexed `figure_span` column, which is backfilled once from the stored
summaries when the image worker starts: 284,009 rows, about 3 s of computation.
The shared (rollback) backend computes the same facet, and the local-vs-shared
parity test covers it. The filter-wide bulk decision honours it.

Measured on the local review database, 2026-09-30: 39,995 of 244,179 current
items span figures, 178,982 stay within one, 24,235 are unknown and 967 are
cross-paper. On the embargoed 2026-09-30 veins batch: 354 span figures, 3,105 stay
within one and 1,085 are unknown.

### a test no longer rewrites a tracked corpus table package

`tests/test_processed_table_view.py::TestItReachesTheRenderedPage` bundled the
first archived run in `high_value_pdfs_to_run_on` IN PLACE, and
`build_bundle` builds the derived `tables/` package beside the paper it
bundles. With `.extraction_cache` present the rewrite was byte-identical, so
nobody saw it. In a fresh checkout the walker found nothing extracted and
emptied the tracked three-table package of `10.1001--jamanetworkopen.2023.37679`
(289 lines deleted). Found with a per-test hash tripwire over a full suite run.
The fixture now bundles a copy under `tmp_path` and asserts that the corpus
folder is byte-identical afterwards. Test-only; no pipeline change.

### two swallowed failures now leave a trace; the inertness pin holds at 48

`lint-inert` counted 50 proven-inert findings against a pin of 48. Diffing the
`certain` list at `77446bfa` (the last re-pin) against `b39f7907` showed
exactly two new `except Exception` handlers that discarded the failure:

- **Image CPU admission** (`image_resources._host_cpu_held_by_others`,
  from `0256ddcb`). An unreadable host lease ledger was returned as "no other
  run holds slots". It still falls back to the fixed deadline, but
  `Coordinator` now counts `ledger_read_failures` (also in `describe()`) and a
  resulting timeout names the unread ledger instead of blaming memory/CPU
  pressure alone.
- **Workbench landing-page warm-up** (`Service.background`, from `9153a2bf`).
  A failed `projects()` warm-up is stored as `warmup_error`, returned by
  `Catalog.status()` and shown in the status line. The next successful
  warm-up clears it.

No change to detection, screening or the detector fingerprint.

### channel re-shows judged channel by channel; covered images are hidden

This changes the detector fingerprint. Both changes come from Dan's
2026-09-29 review of `masliah_subset`.

**Your labels are now a fixture.** Built with `image-reviews-export
--local-db` from a snapshot of the two review tables:

- 184 standing decisions, all joined. 39 pairs were reviewed on both
  2026-09-25 and 2026-09-29; the 1 disagreement was false_positive vs
  false_positive_same_condition.
- Deduplicated to the newest decision per pair: 145 pairs (58
  `false_positive_overlay`, 67 `false_positive`, 10 same_condition, 1
  magnification, 9 `true_issue`).
- Files: `validation_20260929/masliah-reviewed-current-20260929{,.dedup}.jsonl`.
- **Before** (`gate_be44f340f96f`, no re-sweep): all 136 labelled false
  positives still fire, and 9 of 9 true issues are kept.
- The per-reason table (`review_negatives.by_decision`) was computed but
  never printed; the scorecard now renders it.

**Why the old overlay rule missed them.** `channel_overlay.measure` answers
only "one channel (or grey) beside a merge", with roles judged on the whole
panel. Of the 48 overlay FPs labelled on 2026-09-29:

- 43 abstained before any correlation ("no channel asymmetry"): 23 had
  equal channel sets, 10 strict subsets, 10 partial overlaps;
- 2 were measured at rank r 0.69 and 0.68;
- 3 were tier 6, which is never measured.

**`channel_overlay.measure_reshow`** judges channel by channel inside the
matched region. It reports a re-show when:

- every channel both panels carry reproduces at rank r ≥ 0.70, and
- at least one channel is carried by one side only (the other side's share
  ≤ 0.33 of it).

It demotes to `channel_overlay_reshow` only for a same-figure pair at the
same registration (`same_registration`, or translation_frac ≤ 0.05).
`channel_overlay_path` says which verdict fired.

**Protected by design.**

- A channel carried by BOTH panels and uncorrelated stays evidence: that is
  the reused-field signature of true issue `jbc.m115.678185` IMGDUP-47.
- A pair with no shared channel (green-only vs red-only) is not decided,
  because co-localisation and a recoloured copy look alike.

**Replay** on archived pixels of the 145 pairs, text masks off:

| Class | Demoted |
|---|---|
| Overlay FPs | 31 / 58 |
| True issues | **0 / 9** |
| Other FPs | 12 / 78 |

**How the thresholds were chosen.** Across the grid (absent-ratio
0.25–0.50, floor 0.60–0.70) 0 of 9 true issues were demoted every time:
registration protects 7 of them and colour the other 2. The absent-ratio
therefore guards the class the labels lack, and is kept at 0.33.

**Tier 6 is not wired.** None of its 3 labelled overlay pairs would clear.

**What gets correlated depends on the backdrop** (added after the first
clean gate run).

- **The problem.** Opening unlabelled demotions from that run turned up
  `pnas.2411492122` IMGDUP-15: one brightfield field with a red band in A
  and yellow blobs in B. It read "shared red r=0.93" and was demoted, because
  a grey backdrop carries the same structure in every raw channel.
- **The rule.** When either side's mean per-pixel minimum channel exceeds 55
  (a grey backdrop), each channel's chromatic excess (the channel minus the
  pixel's minimum) is correlated instead of its level. On the labels the
  floor separates cleanly: every overlay FP ≤ 45.8, every brightfield /
  template-map pair ≥ 66.5.
- **Replay:** 31/58 overlay FPs, 0/78 other FPs (was 12, all
  brightfield/template maps from three PNAS papers), 0/9 true issues.
- **Unlabelled check:** of the 93 unlabelled pairs the first version
  demoted, 25 are no longer called re-shows (24 grey backdrop, 1 at r 0.69).
  They stay evidence.

**`pdf_occurrences` REVISION 4: occlusion.** Visibility was judged per draw
from clips, masks and alpha, and a later image painted over a draw was never
considered.

- **The case:** on `10.1038/s41423-019-0260-y` p.11, a corrected Figure 8
  (xref780) is pasted over the original (xref779). Both were harvested and
  segmented, and every panel matched its own twin: IMGDUP-5..27, 16 of them
  evidence. Among those are the IMGDUP-13/14/16/24 that Dan reported.
- **The fix:** `apply_occlusion` hides a draw covered by a later draw that
  is axis-aligned, alpha 1 and Normal blend, in a known clip, and whose
  stream has no `/SMask`, `/Mask` or `/ImageMask`.
  - Its fully covered draws become hidden. The existing hidden-image path
    then says "painted over ... by a later opaque image" instead of "placed
    outside the visible page".
  - An uncovered remainder that is a single rectangle becomes `partial`; any
    other shape becomes `unknown`.
  - Unproven opacity covers nothing. An identical redraw (same xref and
    transform) is one appearance.
- **Re-run on that paper:** 0 groups touch xref779/780 (was 23), and the
  Figure 1 channel pairs become `channel_overlay_reshow`.
- **The spurious hit.** `s41423` was a Masliah figure-level "hit" only
  through those self-matches. The alleged 8d reuse lives in the original,
  now covered by its correction.
- **How common:** a census of the 197 subset PDFs found 61 draws ≥ 95%
  covered by a later image, on 12 papers (31 figure-sized, on 7). At the
  group level only `s41423` changed.

**Gate baseline re-accepted: `f372b968b2be` replaces `be44f340f96f`
(2026-09-30).** Full profile. The Masliah fixture is now the deduplicated
2026-09-29 one.

- **Unchanged:** RSIID tp 145 / fp 0; Masliah reviewed true issues 9/9.
- **Reviewed FPs:** 105 of 136 still fire. The 31 suppressed are exactly 31
  of 58 overlay FPs.
- **Figure-level 14/38 → 11/38.** All three losses were spurious agreements,
  each checked by eye:
  - `s41423-019-0260-y`: self-matches with a pasted-over correction.
  - `pone.0034713`: a green vs red channel pair.
  - `s40478-016-0410-8`: a channel beside its merge in Fig 3, where the
    allegation is 3B reused in 9A.
- **Paper-level 38 → 33.** The other 4 fired only on unnamed figures, all
  channel re-shows.
- **One run was discarded:** a first gate run under concurrent load (another
  session's fetch batch plus test suites: 22 track timeouts, 744 RSIID
  timeouts).
- **Pre-existing, not from this change:** the reviewed-581 true issue
  `acsinfecdis.5c00088` no longer fires (0/1).
  - Reproduced with both new mechanisms off, and on commit 1bb8ec85.
  - It went unseen because every baseline accepted since 2026-09-14 was
    quick-profile.
  - The absolute rule keeps failing every full run until it is fixed.

### Masliah PubPeer labels rebuilt; image terms measured; the gate knows its labels

**Rebuilt Masliah labels:**
`masliah_papers/.image_track/pubpeer_labels_20260928.json`, built with the
10-per-request lookup and the new figure parser. The frozen
`pubpeer_labels.json` (2026-08-17) is unchanged. It carries a 429 refusal for
25 DOIs.

- **Threads:** 122 entries (frozen: 114). No entry was lost. 0 lookups
  refused; 32 of 91 batches got HTTP 429 at 1.5 s and were re-asked at 6 s.
- **Positives:** 83 (frozen: 69). None were removed, and 14 were added:
  - 6 from missed lookups: `s12868-015-0218-7`, `s12974-016-0585-8`,
    `jad-2011-110914`, `jad-2011-111208`, `nbd.2021.105478`,
    `pnas.96.4.1563`;
  - 2 from comments posted since 2026-08-17: `s12974-020-01888-0`,
    `jneurosci.4390-09.2009`;
  - 6 from the new terms below: `s12640-009-9073-6`, `s12276-021-00562-6`,
    `s41467-018-05958-z`, `science.287.5456.1265`, `scitranslmed.3003799`,
    `embr.201541438`.
- **Figures:** figures changed on 36 papers. Two main-text labels were
  supplementary figures misread:
  - `s41423-019-0260-y`: Figure 5/5D/6F became S5/S5D/S6F. It is still a hit,
    via Figure 8D.
  - `s41380-020-0776-7`: Figure 8 became S8/S8A/S8B.
- **The 14 new positives were visually reviewed** into `pubpeer_review/`.
  None is in the gate's 203-paper scratch subset.

**`parse_comments` decodes the comment's JSON string.** 82 of 489 Masliah
comments carried literal `–`/` `/`\n`. As a result "Fig 7B–D" was
read as 7B alone, and panel letters were lost on 3 papers.

**`_IMAGE_TERMS` gains measured phrasings.** Each one comes from a real
thread the old list read as non-image:

- `reuse`/`re-use` (replacing `reused`/`re-used`);
- `similar than`, `remarkably similar`, `unexpectedly similar`,
  `high similarit`;
- `mix-up`, `mixed up`;
- six `vertical …` splice phrases.

Measured on the 48 Masliah non-image threads and the 122 cached
image_discovery threads: 9 + 24 flips, all image allegations except one
("re-use the material" after a retraction). Rejected on the same threads:
`background` (a false positive, and no gain over `vertical`), bare `similar`,
`image`, `panel`, `copy`, `same field` (no hits).

**Not fixable by terms:** most of the 48 Masliah non-image threads are an
annotated image with a signature and no text. They need visual review, not
keywords.

**`image-gate` records `labels_sha256` per labelled lane.** Comparing records
scored against different label sets is now a hard failure asking for a
deliberate `--accept`. A baseline without the field is named in a note.

**Re-scoring `gate_be44f340f96f` (no detector change):**

| | Frozen labels | Rebuilt labels |
|---|---|---|
| Figure-level | 13/36 (all named 52) | 14/38 (all named 68) |
| Paper-level | 38/52 | 38/52 |
| `not_in_corpus` | 16 | 30 |

- One bucket moved: `journal.pone.0034713` went from wrong_figure to hit.
  Its Expression of Concern names Figs 7A/10A/10B for vertical
  discontinuities, and the detector fired on Figure 10. That match
  (`IMGDUP-17`, run `ar_ddd3f844`) is panel G vs L: the same cells in the
  green and the red channel, not the alleged blot splice. The +1 is
  figure-number agreement, not a catch.
- **Gate baseline re-accepted: `be44f340f96f` replaces `5104d40bbcaf`
  (2026-09-29), a label-set change only.**
  - A forced quick run on the rebuilt labels reproduced the re-score exactly:
    figure-level 14/38, paper-level 38/52, fire rate 0.446.
  - RSIID (tp 145, fp 0, 47 incomplete) and the channel_overlay audit (1,189
    groups) are unchanged.
  - The old baseline's 13 hits are a subset of the new 14.
  - The baseline now records `labels_sha256` (469ce908...), so the next
    label change fails the gate until it is re-accepted.
- Two examined no-fire positives gained named figures:
  `jneurosci.4321-06.2007` and `jneurosci.6159-08.2009`. The figures come
  from the new terms: their "remarkably/unexpectedly similar" comments name
  the figures, and the comment the old terms matched did not.

### PubPeer lookups stop losing entries; scorecards read human-screened negatives

**The v3 lookup returned at most 10 entries per request**, whatever the batch
size. Measured 2026-09-28 on DOIs that all have threads: asking 1/5/10/20/50
returned 1/5/10/10/10. `pubpeer.lookup` sent 50 per batch, so every entry past
the tenth in a batch was silently dropped and read as "no PubPeer entry".

- **Berrío 2025 set:** 50-DOI batches found 54 of the 106 papers whose threads
  the review's own spreadsheet links.
- **Masliah** (907 DOIs, re-looked-up the same day): 122 entries against the
  114 in the frozen labels.
  - None of the 114 was lost.
  - 8 were missed. By the keyword rule, 3 of those are image allegations
    (`10.1186/s12868-015-0218-7`, `10.1186/s12974-016-0585-8`,
    `10.3233/jad-2011-110914`), and at least two more are image concerns the
    keywords do not catch.
  - The frozen Masliah labels, and the gate's recall denominators built on
    them, are therefore short by at least 3 positives. They are NOT rebuilt
    here, because the gate baseline is measured on them.
- **Also affected:** the discovery builder's and the embargoed-corpus builder's "already on
  PubPeer" exclusions used the same call. Their batches are sparse, so losses
  there need a batch holding more than 10 commented papers.

The fix:

- `BATCH` is now `V3_MAX_FEEDBACKS` (10).
- A saturated answer to a larger batch is split and asked again. It is never
  cached, and never read as complete.
- Seven of 91 requests got HTTP 429 at 3 s spacing. They stay named refusals
  (status unknown), as before.

**`image-benchmark` reads human-screened negatives** (for the Berrío set):

- **New `screened_negatives` block:** examined / fired / fire rate on papers a
  human screened and did not flag. The block states that this is an upper
  bound. Evidence groups are counted by tier and suppressed context groups by
  kind. Uncertain, contested and lookup-unknown papers are excluded and
  counted.
- **New `recall_by_label_field` block:** recall split by `split` / `bik_type`
  / `spreadsheet_blot`.
- **`figure_state: corrected`** from the visual review. It means the publisher
  replaced the alleged figure in the PDF we hold. Such papers become
  `corrected_in_place` and are kept out of every recall denominator. An
  unstated state is `unknown`, never `original`.
- Both blocks are null on PubPeer-only corpora; the Masliah scoring is
  unchanged.

### PubPeer figure references read supplements, lists and ranges

Found while building the Berrío 2025 ground-truth set (2026-09-28). The one
regex behind every PubPeer figure label mishandled three forms:

- It returned **nothing** for `Figure S4` / `Fig. S3B`.
- It read `Supplementary Figure 4a` as main-text `Figure 4A`.
- It kept only the first item of `Figs. 2c, 2d`, `Fig. 3B-D` and
  `Figures 2 and 3`.

So a supplementary allegation either vanished or was scored against the wrong
picture, and every list lost all but its first figure.

- **`pubpeer.parse_figure_refs` / `figure_refs`** replace it. `Supplementary`
  / `Suppl.` / `Supporting` give `Figure SN`, matching the caption parser's
  `SUPPLEMENTARY_PREFIX`; `Extended Data` keeps a plain number, as there.
  Lists and ranges expand. A bare panel letter or number after `and` counts
  only when it ends the phrase ("Figure 3A and I think" is one figure).
- **`figures_agree`** never matches `Figure S4` with `Figure 4`.
- **Masliah unchanged**, measured by re-scoring `gate_be44f340f96f` under both
  functions: figure-level 13/36, paper-level 38/52, zero papers moved. Its
  frozen labels and the supplement-free gate sweep only ever say `Figure N`.
  Any Masliah label that was really a supplementary figure stays conflated
  until those labels are rebuilt.

### cross-paper matching 1.9x faster, identical results

Dan, 2026-09-27: the `image-complete` cross-paper stage for
`bharat_b_aggarwal` (43.5M pairs) used ~3.5 of 20 cores. Each worker was at
35-40% because pairs were dispatched in enumeration order, so almost every pair
brought a target panel the worker had never seen. That meant re-reading the
PNG, re-hashing it, and loading normal plus mirrored features: ~1.75 TB of
reads per worker in 13 h.

- **`exhaustive_pairs._pooled`.** A pooled batch (now 200,000 pairs,
  `POOLED_BATCH_PAIRS`) runs target-major in contiguous groups, one worker per
  group, so a worker keeps the batch's source panels hot while targets stream
  past.
- **`ComparisonPool.map_groups`.** Threads claim groups dynamically, instead of
  every 18-pair chunk waiting for its slowest pair.
- **Unchanged:** the matcher's caches allow 64 entries under the same byte
  ceiling. Enumeration, the checkpoint cursor, per-pair timeouts and every
  result are unchanged.
- **Measured:** on Das's 95 frozen inventories, the first 100k pairs with 4
  workers ran at **605 vs 312 pairs/s**, with matches (7) and refusals
  (10,938) identical row for row.
- **Gate:** `be44f340f96f` PASS, identical to baseline `5104d40bbcaf`.

### a paper reprinted in a book is no longer cross-paper reuse

`image-complete` exported every figure of three Molecular and Cellular
Biochemistry 196 articles as reused in the Springer book that reprints that
volume (`10.1007/978-1-4615-5097-6`): 7 of the 10 cross-paper items in the Das
run. The export now labels such a match `reprinted_publication`, a retained
context kind, when >= 75% of one paper's word 6-grams appear in a document
>= 5x its size. MEASURED over 17 author corpora (~3,500 papers): only those
three pairs qualify (0.87-0.94 contained, 18-24x); equal-sized overlap
(preprints, possible duplicate publication, up to 0.865) stays evidence. No
detector file, threshold or fingerprint changed; existing runs are not
re-exported.

### journal logos no longer reach the cross-paper queue

Dan marked 10 `image-complete` cross-paper candidates on
`anthony_adame_rw20260922` as "False positive: logo". Four more were the same
logos filed as "channels". All 14 were whole-image matches between identical,
uncaptioned streams: the Neurology wordmark and AAN logo (each in 4 papers),
and the Sci Transl Med and J Neurosci Res mastheads (each in 2). The complete
workflow's all-pairs stage (`exhaustive_pairs.run_pairs`) never applied the
corpus-furniture screen that the legacy cross-paper sweep has.

- **`exhaustive_pairs.screen_shared_marks`** runs before pair enumeration. It
  withholds identical analysis pixels found in >= 3 papers
  (`corpus_furniture`), or in exactly 2 papers with no figure caption on any
  copy (`uncaptioned_shared_mark`). Both rules need every copy placed on a
  PDF page. Media inside a supplement container (docx/pptx) has no caption to
  be absent, so it is never withheld: the same blot in two papers' SI files
  stays evidence. The checkpoint state records every
  withheld stream under `withheld_marks` and adds one limitation sentence.
- **Replay on the frozen Adame inventories:** 12 of 4,186 panels withheld,
  and 14 of 43 queue items prevented. Those are exactly the 14 logo items;
  the other 29 are untouched. Over Masliah plus both discovery corpora, the
  ten largest uncaptioned two-paper streams were all stamps or mastheads.
  Every >= 3-paper stream that carried a caption was also furniture.
- `exhaustive_pairs.py` is fingerprinted, so the detector fingerprint
  changes and the next complete run gets a new identity.

### author image runs 2.7x faster, identical findings

Measured 2026-09-25 on a scratch copy of `changhwan_yoon_rw20260922` (37
papers, complete profile, legacy clone engine, warm text-mask cache).

| configuration | wall | mean CPU |
|---|---|---|
| old code, 3 paper workers (best static split) | 312 s | 22% |
| old code, 6 paper workers | 221 s | 31% |
| fair sharing, 6 paper workers | 211 s | 32% |
| fair sharing, 6 paper workers, `OMP_NUM_THREADS=4` | 117 s | 56% |

All 20 analysed papers' findings are identical across these runs, once run
IDs, telemetry and cache counts are excluded. No fingerprinted file changes.

- **Fair CPU sharing between papers** (`image_resources.FairShare`, in both
  the run coordinator and the GPU broker). Each paper may request the whole
  budget. A paper is capped at `budget // active papers`, where active means
  holding slots, waiting, or seen in the last 20 s. The sweep no longer
  splits `cpus // paper_jobs` statically: with 18 paper workers that split
  gave every paper one core. A paper holding no slots now waits while
  another live paper's stage runs, instead of failing at 120 s. In Dan's
  18-worker run, `10.1002--bjs.11181` crashed on exactly that admission
  timeout. A paper already holding slots keeps the 120 s deadline, so two
  papers cannot deadlock.
- **Panel-detector threads.** The learned panel detector sizes its ONNX
  session from `OMP_NUM_THREADS`, capped at 4 and admitted. The author
  launcher pinned it to 1, so the model took 1.6 s per figure: 139 of the
  slowest paper's 152 s. At 4 threads it takes 0.49 s, and detections were
  identical on 40 real figures. BLAS and MKL stay at one thread. Changed in
  `examples/run_author_image_corpora.py` and the author runbook.

### a gate that can pass under enforced text exclusion

Decided by Dan, 2026-09-25. No fingerprinted file changes.

- **RSIID `incomplete` cases** (text masking left too few non-text keypoints
  to reach the 15-inlier floor) are no longer record errors. They stay
  excluded from tp/fp/fn/tn and are counted. The gate fails when the count
  exceeds the accepted baseline's, and with no baseline any incomplete case
  still fails; the development sample stays strict. Measured on
  `97dd97f7872c`: 47 incomplete cases (29 positive, 18 negative, none fired).
  The pre-text-exclusion baseline fired on 3 of those 29 positives.
- **The channel_overlay audit** reads masks from
  `scripts/text_mask_backfill.py`. That script localizes the exact pixels the
  audit loads, using the production CRAFT store, into a scratch root outside
  the corpus. The audit now fails when no group gets past text eligibility,
  or when more than 5% of attempted groups are incomplete; incomplete groups
  stay counted and listed. Before this, all 32,081 embargoed-corpus
  groups were incomplete and it measured nothing.
- **Baseline moved** from `ee86704a3f92` to `5104d40bbcaf`
  (`image-gate --accept`). The one Masliah figure hit lost,
  `10.1002--jnr.22089`, rested on a Figure 3 vs Figure 4 whole-figure match
  of the shared template (column headers, panel letters, chart axes;
  different micrographs). Text exclusion correctly removes that match. The
  labelled 4A/5A duplication was not found with exclusion on or off.
- The accepted record measures: Masliah figure-level 13/36 and paper-level
  38/52, with a fire rate of 44.6% (alarm, reported, not blocking). RSIID
  tp 145, fp 0, fn 266, tn 182, with 47 incomplete cases. The
  channel_overlay audit exits 0 with 1,189 groups measured and 667 of
  32,081 (2.1%) incomplete (489 excessive masks, 178 retained PNGs gone).
  These numbers are identical to `97dd97f7872c`: the clone-tier commits in
  between do not reach these lanes, which run with `copy_move` off.
- The RSIID lane runs 12 workers instead of 4 (`eval/gate/config.json`),
  about 26 minutes instead of 52. Speed only: every case is compared by
  outcome.

### the title-page publisher mark is furniture

- `panels._classify_furniture` gains a fourth rule. A stream placed only on
  page 1, with no figure label, at most 72 pt on each side and wholly inside
  the top quarter of the page is withheld as `page_furniture`. Placements
  carry a new `first_page_header` flag.
- Why: the Elsevier tree logo (60x65 pt, bottom edge at 17% of the page) sits
  just below the 10% margin band and appears once per paper. It therefore
  cleared every existing rule, including the ≥3-paper corpus SHA screen, since
  it ships as three different streams. On `sajani_s_lakka_rw20260922` it was 6
  of the 12 cross-paper items in the `image-complete` run.
- Recall check: a read-only scan of existing panel indexes found this shape
  in 4 of 9,024 eligible Masliah-subset panels and 14 of 42,165 reviewed embargoed-corpus
  panels. All 18 are header marks: the Elsevier tree and cover thumbnail,
  CrossMark, ASM and Ivyspring.
- The detector fingerprint moves because `panels.py` is fingerprinted.
  Existing runs keep their items until the affected papers are re-harvested.
- Gate `97dd97f7872c` (quick, measured together with the clone-search
  speedups) reports the same four hard failures as the committed
  `9a1b24e315ea`: the channel_overlay audit exits 2, 47 RSIID cases are
  incomplete, and `10.1002--jnr.22089` is lost. Masliah hits, fire rates and
  RSIID tp/fp are identical. The one change: `10.1016--s0304-3940(98)00399-1`
  is a 1-bit scan whose only eligible panel was the Elsevier tree. It used
  to count as "ran" and is now refused as `scanned_pages`. The baseline is
  not moved.

### charts are not searched for within-panel clones

- Dan, 2026-09-25: panels the learned detector types `Graphs` are withheld
  from the clone tier (`chart_panel_not_clone_searched`), and a figure's
  chart-typed sub-panels are masked out of its whole-figure clone search
  (`chart_regions_masked`); a figure whose typed sub-panels are all charts is
  withheld like a chart. Only the explicit type gates this (the one class with
  measured precision); untyped panels are searched as before. Why: on
  `changhwan_yoon_rw20260922` (hybrid_core) 5,401 of 7,930 clone candidates
  were on Graphs panels -- repeated markers, caps and glyphs -- and on
  10.1124/mol.112.078402 the parent figures re-found the same chart content
  (1,438 of 2,978 parent candidates inside chart sub-panels). That paper:
  3,226 -> 1,146 clone candidates. Changes results; detector fingerprint moves.

### faster within-panel clone search, identical results

- FIX (same day): the verifier rewrite built region origins from OpenCV's
  numpy int32 component stats. Values were identical, but on panels of 1 MP or
  more they reached hit bboxes as int32 and failed JSON serialisation
  ("Object of type int32 is not JSON serializable"): 11 of 21 analysed papers
  in `changhwan_yoon_rw20260922` lost clone searches on large panels. Origins
  are Python ints again. The equivalence test compared values only; it now
  compares types too, and fails on the previous commit.

- `clone_regions.RegionVerifier`, which re-checks every proposed transform at
  original resolution (48% of hybrid clone time on the Neuron sample, most of
  it on whole figures), no longer scans the whole check window once per
  connected component, evaluates the 8 px self-map test only where
  correlation already holds, and keeps component masks cropped to their own
  box until the window stops growing. Same float64 expressions, same arrays:
  0 mismatches in 11,800 real verifications across all four proposal engines;
  1.45-2.94x faster on 7-11.6 MP figures, ~1.08x on small crops.
  `tests/_clone_verifier_reference.py` keeps the previous implementation
  verbatim and `test_clone_regions` requires exact equality with it.
- `copy_move_hybrid._template_models` evaluated the 8 px self-match disk over
  the whole score map for every patch (918 us beside 1,379 us for
  `matchTemplate` itself); it now evaluates the same expression on the only
  window that can satisfy it. `_Discoveries.equivalent` screens the IoU > .7
  precondition of `_same_discovery` with a vectorised copy of `_overlap`
  (same operations, float64) before calling it in insertion order. Template
  proposals are identical in order (97,223 on four crops), 1.1-1.7x faster.
- Not changed, and why: RANSAC (`estimateAffinePartial2D`, up to 21% of a
  crop) consumes OpenCV's seeded RNG stream, and SIFT `knnMatch` (60% of the
  keypoint engine on whole figures) orders near-tied matches that feed it;
  neither can move to a GPU or change order without changing results. A GPU
  prefilter for `matchTemplate` with an exact CPU recheck was measured exact
  (0 misses in 164,628 patches) but skipped 11-19% of patches on chart and
  microscopy crops, where near-flat windows make OpenCV's own score
  unpredictable, so it was not shipped.
- The within-panel clone stage (`--copy-move`, and always in `image-complete`)
  reserved a flat 3 GiB per worker, so a 20-CPU machine with ~39 GiB free ran 9
  searches on 10.1016/j.neuron.2016.05.021. Measured peaks are 0.16-0.39 GB for
  0.03-0.3 MP panels and 1.7-1.9 GB for 6.5-7.1 MP whole figures. Worker slots
  now lease 1 GiB each and `run_clones` starts a panel only while the
  size-based estimates of the panels in flight fit the lease (an oversize
  panel runs alone). Scheduling only: results are merged by index, and four
  real panels (28,942 hits) are byte-identical to the previous path. The
  detector fingerprint moves because `within_parallel.py` is fingerprinted.
- Whole-detector check, previous vs new code in one process on sample panels
  of 10.1016/j.neuron.2016.05.021: 12 panels (0.03-7 MP, ~114,000 hits)
  byte-identical, 1.06-1.28x per panel. Gate `97dd97f7872c` (this change plus
  the publisher-mark rule) reports FAIL only on the failures already recorded
  for `9a1b24e315ea`; the gate sweeps without `--copy-move`, so it does not
  exercise the clone search. Baseline not moved.

### image summary figure

- The image finding page's Paper row has **generate summary figure**: the whole
  printed figure(s) rendered from the PDF (the embedded image each panel was
  cropped from, plus margin) with the same duplication boxes as the PDF pane.
  Two pages or papers sit side by side or stacked, whichever is nearer square;
  one page with both sides is one crop. Each figure carries its paper's full
  reference (no DOI) from `fetch-metadata`, via `POST /api/images/reference`,
  which caches `metadata.json` beside the paper. A crop tool keeps and
  downloads a cropped PNG. Viewing a finding never fetches; only the button does.

### image/workbench audit fixes

- Port the still-missing fixes from `8c4468f9`: isolate HTML evidence and guard
  browser mutations, prevent cross-paper spreadsheet cache collisions, preserve
  nested image identities and cumulative exclusions, persist visit counts,
  distinguish missing image coverage from zero findings, sort displayed counts,
  and prefer verified archived XML with a verified PDF toggle.
- Preserve newer detector, publication, request-cache and navigation behavior.
  See `docs/image_workbench_audit_fixes.md` for the integration decisions.

### gate measurement integrity

- Require complete, profile-appropriate gate receipts and an exact detector
  fingerprint before treating a detector as measured. Interrupted checkpoints
  remain resumable; malformed receipts do not satisfy the guard.
- Fail comparisons and baseline acceptance for incomplete measurements or failed
  audits, including when no scientific baseline exists. Preserve audit stderr and
  write checkpoints atomically. Existing scientific thresholds and the soft
  timeout policy are unchanged.

## [1.72.0] — 2026-10-01 — Greg's scaffold checks layer merged; two live false-accusation paths closed

MINOR: two changes alter what the live pipeline can report on the same paper.
Both only narrow: each removes an accusation path and adds none. This merges
`best-source-acquisition-2026-09-05` (48 commits by Greg Fitzgerald,
2026-09-08 → 09-15). The branch name is stale: its source-acquisition work
was merged on 09-08, and everything after that is the scaffold work below.

Live pipeline:

- **Assumption checks (`anatomy.py`).** A clean screen is now read as a
  result, not a denial: "no outliers were detected", "VIF values indicated no
  multicollinearity", and similar wording for heteroscedasticity, clustering
  and heterogeneity. Before, a paper that ran the check was told it had not.
  Named outlier tests (Grubbs, Dixon's Q, Tietjen-Moore, GESD) now count as an
  outlier check.
  - `two_way_anova` and `mixed_anova` get assumption lists.
  - `TEST_TYPE_ALIASES` / `canonical_test_type` join the scaffold's
    test-type spellings to the assumption vocabulary.
  - Ambiguous families (`correlation`, `wilcoxon`, `survival`, …) are declared
    in `TEST_FAMILIES_WITHOUT_ASSUMPTIONS` and still fail closed to
    `indeterminate`.
- **Headerless tables (`extraction/jats.py` `_header_depth`,
  `supplements_read._finish`).** When row 0 reads as measurements, the table
  now gets header depth 0. Its columns are reported `(unlabelled column N)` and
  a warning is attached. Before, the first data row became the column labels:
  on PMC5532079 Table 1, a column was named `49`. An ambiguous row 0 still gets
  depth 1. Ported into the image package's canonical extraction modules (not
  fingerprinted; detector answers are unchanged).

Not a live change:

- **`grim_test` accepts `scale_min=None` / `scale_max=None`** ("no stated bound
  on this side"), which skips the range check on that side only. Output with
  both bounds is byte-identical. The registry/MCP spec still takes integers, so
  only the scaffold checks pass `None` today.
- **The `scaffold/` package gains a deterministic checks and premises layer.**
  New modules: `checks.py`, `premises.py`, `premise_reading.py`,
  `adjudication*.py` and `reading_store.py`, plus about 25k lines of
  adversarial tests. It is still not wired into the analysis pipeline; run it
  with `python -m metascience_agent.scaffold`.
  - The paid premise reading is opt-in (`--read-premises`) and capped at
    `MAX_CANDIDATES_PER_PAPER = 2000` (about $10).
  - Paid table readings persist in `~/.cache/metascience/readings`
    (`METASCIENCE_READING_CACHE`; set it to `off` for test-retest). The test
    suite isolates this store per test.

## [1.71.0] — 2026-09-24 — default text exclusion and development benchmark

- Enable shared CRAFT text exclusion by default for all integrated visual consumers
  on new runs, as explicitly requested by the operator. Preserve exact reuse,
  retained masks, audit overlays and incomplete-state guards. Retain scientific
  acceptance as incomplete; do not lower the baseline. Enforced Masliah recall
  remains 13/36 at figure level and 38/52 at paper level; candidate groups fall
  511 to 456. This does not establish a precision improvement.
- Added `image-gate --profile dev`: a fixed two-per-stratum sample of supported
  RSIID tasks (32 current cases), with separate output and no paper corpus sweep.
  Existing `quick` and `full` profiles retain their longer coverage. Development
  records cannot replace the accepted baseline. Benchmark resume identities now
  include text policy/backend requests, and incomplete text work is not scored
  as a completed negative.

- Added explicit operator rollout authorization for the complete-profile launcher,
  tied to code, numerical environment, profile and text policy. The saved record
  retains known limitations and incomplete scientific acceptance.

## Unreleased — managed GPU execution

- Added explicit CPU/CUDA/MPS selection, real capability probes, workload-specific
  qualification, shared CPU/RAM/VRAM admission and persistent accelerator workers.
  Automatic execution retains CPU fallback and reports the actual backend.
- Routed CRAFT, learned ONNX panel detection and Docling through managed execution;
  corrected the effective RapidOCR GPU options and retained provider/model evidence.
  Scientific cache identities and panel stamps include backend implementations.
- Added qualified equal-shape CRAFT batching and explicit cold/warm comparisons
  against the CPU worker pool. CPU-only operation remains available without GPU
  probing. Text-exclusion activation and scientific acceptance are recorded separately.
- Added NVENC/VideoToolbox encoding with software fallback and validated frame count,
  dimensions, frame rate and seeking before replacing an existing video. Retained
  text-region audit views now show the localization backend.
- RTX 3060 qualification on 2026-09-24 measured 3.60× CRAFT localization throughput
  versus the configured CPU pool, with exact masks/statuses for 205 unique images.
  The quick scientific gate retained the pre-GPU results and the same existing
  Masliah baseline failure; GPU qualification does not constitute scientific acceptance.

## Unreleased — OCR text-support diagnostics

- Added a conservative OCR check of the original transformed-match keypoints,
  including colored and rotated labels, region retry, bounded caching, and named
  abstentions. Initial rollout is diagnostic: candidate classifications remain
  unchanged pending real-data acceptance of automatic context demotion.
- Added local-review export against sealed run identities and verified panel
  hashes, with disagreement and AI-review handling, and an isolated pair replay.
- Workbench details render text boxes and support counts. The new text-context
  queue filter retains access and respects explicit positive review overrides.

## Unreleased — parallel searches within one paper

- Single-paper image sweeps allocate the available CPU budget to bounded process
  pools for feature preparation, transformed comparisons and clone searches.
  Prepared descriptors and read-only pixel maps avoid repeated image decoding;
  identical pixel deliveries share clone computation while retaining every source.
- Added `--image-workers`, memory-aware stage limits, live tqdm progress,
  `analysis_progress.json`, and recorded stage timings. Memory-limited clone
  processes share the native OpenCV thread budget, including remainder cores;
  BLAS remains serial. Ordered results and
  per-comparison RNG initialization make scheduling independent of findings.
- A fixed 276-comparison sample from the Neuron paper measured 10.07 seconds
  serial versus 5.67 seconds with 20 processes on 2026-09-23, with identical
  matches. This sample does not estimate full-paper or clone-search speedup.

## Unreleased — local image rapid review

- Image review now has a durable local SQLite store and an independent worker;
  compact item reads and SQL queue pages do not hydrate corpus-wide candidates.
- Panels and decisions load first. Paper viewing is independent; explanations,
  diagnostics and video tools load on demand.
- Added resumable archive/cache import, optional one-time Neon catch-up, local
  review events, exact-run publication notifications and a shared-backend rollback.

## What the number means

The release number exists to answer one question a git sha cannot: **are these
two reviews comparable?** A sha tells you the code differed. It never tells you
whether the difference could have changed a finding.

| Bump  | When | What it tells a reader |
|-------|------|------------------------|
| MAJOR | The report layout or an output schema (`findings.schema.json`, `report.schema.json`, `run_meta.json`) changed such that something parsing it downstream would break. | Re-read the format before trusting your tooling. |
| MINOR | A new tool; a change to which severity a check can return; a change to a guard, a threshold, or a prompt that governs interpretation. **The same paper may now produce different findings.** | Two reviews across a MINOR boundary are *not* directly comparable. |
| PATCH | A fix with no change to output semantics: a crash, a rendering detail, a doc, a test, a refactor. | Differences between two such runs are about the papers, or about model nondeterminism — not about us. |

The MINOR rule is the load-bearing one, and it is deliberately broad. Prompts
and severity caps are not implementation details here: they decide what gets
published as an accusation. A prompt edit that changes when `impossible` is
reachable is a MINOR bump even though no Python signature moved.

**Bump in the same commit as the change.** A version bumped later is attached to
the wrong runs, and the runs are the whole point.

### What the number does *not* cover

Prompts and the tool registry move several times a day, far faster than this
number. `run_meta.json` and the report's Provenance section therefore also carry
`prompt_sha256` and `registry_sha256` (see `agent._provenance`). Two runs are
directly comparable only when the pipeline version **and** both hashes match.
The release number is the human-readable summary, not the whole identity.

---

## [1.70.0] — document-scoped image identity and consistent local video availability (2026-09-23)

- Figure labels and parent IDs are compared within their source document through
  one identity helper. A main-paper Figure 1 and a supplement's Figure 1 no
  longer clear a channel/merge match as same-figure reuse. Missing attribution
  remains unknown; verified rendition equivalence still uses source registration.
  The standalone image package is 0.22.0, and its detector fingerprint includes
  the identity helper. Existing results are not rerun or rewritten automatically.
- Search checkpoint startup retries transient SQLite lock contention with a
  bounded backoff and closes failed connections without discarding saved work.
- Queue and detail share local-video availability checks for the exact database,
  project, run, item, evidence signature and validated file. Queue projections
  remain immutable; failed or missing videos cannot leave a stale local marker.
  Video controls reconcile refreshed job/media revisions independently of the
  finding revision and ignore responses for superseded status snapshots.
- Both historical and current source conversions coalesce by cache key. Unrelated
  XML documents can convert concurrently; failures remain retryable and source
  hash validation still precedes cached conversion reuse.
- Scratch detector gates explicitly disable the ordinary sweep's database push,
  including on machines with shared-database credentials.
- Validation: the 203-paper scratch measurement matches gate `8ffd9cfc7edf` in
  figure hits, paper hits, fire rates and miss categories. It retains that older
  record's hard failure against the accepted baseline (lost figure hit for
  `10.1186/s40478-016-0409-1`); the baseline was not changed. The subsequent
  synthetic benchmark was stopped, so this is not a completed passing quick gate.

## [1.69.0] — experimental transformed clone search and resumable complete coverage (2026-09-22)

MINOR: image package 0.21.0 introduces opt-in `clone_engine=hybrid`, with
keypoint, reflected, dense and multiscale proposals verified in original image
coordinates. It reports multiple A/B region pairs, measured transformations,
finite search limits and explicit unfinished stages. Size, periodicity, uncertain
segmentation and possible templates are review annotations in this mode.
The legacy engine and historical result readers remain available.

The experimental `image-complete` profile requires supplements, rendered
fallback, verified higher-resolution pixels, unlimited panel/pair counts and
exhaustive cross-paper enumeration over a shared versioned inventory. It makes
no AI screening or adjudication calls. Committed comparison batches and completed
clone-engine stages can resume without presenting unfinished work as negative.
Run and approval identities bind the detector, profile and numerical libraries.
Large-image mask storage preserves native coordinates; malformed transforms are
rejected before numerical decomposition instead of aborting the panel.

Document-scoped explicit zoom/inset passages can explain the corresponding
panel pair; they cannot dismiss a separate internal clone. The viewer carries
A/B polygons, alignment, source geometry and coverage, with queue filters for
clone scope, transformations and explained context. Source staging includes
supplement containers and figure deliveries in retained workspaces.

**Rollout remains gated.** A real population snapshot preserves 6,138 historic
selection entries (6,136 paper folders and two administrative entries), including
the 93 older and 69 expansion panel-budget cases. The complete command refuses
without current localization, real-dataset, viewer, full-stack, zero-AI and pilot
evidence. Development measurements and timeouts are not acceptance; historical
embargoed-corpus runs and review decisions are preserved. See the image package's
`docs/complete-coverage.md` for commands, limitations and current status.

## [1.68.0] — three reasons one paper's duplications were invisible: a count floor, a box floor, and a mask that claimed the specimen (2026-09-14)

MINOR: detector answers change in `image_analysis.py` and `panel_detector.py`
(both fingerprinted), so every sweep stamped before this reads
`stale:fingerprint`. Image package 0.20.0. Nothing re-sweeps by itself.

Dan labelled ground truth for `10.1038/nn.3070` and asked why a second paper
in the same corpus, `10.1242/jcs.113191`, produced **zero** groups when
PubPeer documents several duplications in it. Three screenshots, three
labelled pairs, and **three unrelated causes** -- none of them a threshold
tuned to this paper. New ground truth in
`eval/ground_truth/image/10.1242--jcs.113191.json`; the paper goes **0 → 3 of
3**, and `10.1038/nn.3070` holds at 9 of 14.

- **A sparse field cannot reach 30 inliers by construction.**
  `_MIN_INLIERS` (30, Acuna's figure) is calibrated on textured photographic
  panels. White neurites on a black field yield far fewer keypoints per unit
  area, so an honest shared patch is refused by the count while its
  photometry is emphatic: Fig. S7 carries 17-26 inliers at scale 1.00 and
  rotation 0.0 with grain 0.83-0.84, Fig. S6 18-31 inliers with grain
  0.55-0.72, both against the 0.25 the detector already uses to mean "the
  same pixels", and both beating their unaligned control by +0.45 to +1.07.
  The floor stays where it is for geometry ALONE; below it, down to
  `_MIN_INLIERS_CORROBORATED` (15), the match is admitted only when the
  matched region's own pixels agree, and the group's sentence says which
  evidence carried it. A corroborated match is then chrome-tested on the
  SHARE of inliers that survives the mask (`_CONTENT_RATIO_MIN`, 0.30) rather
  than on an absolute count: re-applying a floor of 15 to a count already at
  15 refuses every such match by construction, which is what happened to both
  jcs pairs on the first attempt (masked 11 of 18 and 9 of 15). The ratio cut
  has its own measurement -- on 105 workbench-labelled false-positive
  `transformed_match` groups it demoted 21 where a masked-inlier floor
  demoted 44.
- **A panel-box floor in absolute pixels is a statement about resolution,
  not about figures.** On Figure 2 the learned detector returns 17 detections
  at 0.96-0.97 confidence **including all twelve micrographs**, and
  `MIN_PANEL_SIDE = 100` kept five of them -- the bar charts. The micrographs
  are about 85 x 113 px in a 926 px figure, and the F2-red duplication lies
  between two of them, so the pair could not be formed at all. The floor is
  now `max(MIN_PANEL_SIDE_PX, MIN_PANEL_SIDE_FRAC x the figure's long side)`
  = `max(40, 5%)`: the two agree at 2,000 px, so nothing changes for a
  full-resolution embedded stream, below that the floor follows the figure,
  and the absolute bound stops a thumbnail yielding 20 px boxes.
  `docs/datasets/panels600.md` had measured this ceiling on 4,888 annotated
  boxes (53.6% have a side under 100 px, 93.9% of Blots, median side 26 px)
  and asked for this experiment since 2026-09-12. The gutter splitter's own
  `_SEG_MIN_PANEL_SIDE` is unchanged and the test pinning the two equal is
  gone: they were never the same claim -- the gutter's floor says "a BAND
  this narrow in a projection profile is not a panel", this one judges a box
  the model returned at confidence >= 0.4.
- **A recount taken through a mask that withheld most of the panel is not a
  second opinion.** With the boxes fixed, tier 4 matched the F2-red pair at
  68 inliers, inlier ratio 0.99 and grain 0.919 -- and demoted it to
  `chart_furniture` on a chrome-masked recount of 13. The mask had withheld
  **53% of a 112 x 85 px micrograph**: the AP stain is a sparse purple
  precipitate on a white slide covering 9.3% of it, so `chrome_mask` signal 1
  reads it as painted annotation (it is under the 15% area guard, which was
  calibrated on red letters over a grayscale TEM field) and dilating those
  scattered specks by 5 px takes an 11% raw mask to 53% withheld. The
  demotion's claim is "the aligning content was the frame, not the specimen",
  and that claim is unsupportable when the mask claimed the specimen. So the
  recount must now leave at least `_CHROME_RECOUNT_MIN_KEPT` (0.50) of both
  panels to demote anything, and every group records
  `chrome_recount_admissible` beside the ratio. This is the abstain pattern
  the codebase already uses for `colour_direction`, `match_control` and
  `r_absent`: the absence of a measurement is not a measurement.
  `chrome_mask.kept_fraction` was written for precisely this diagnosis -- "a
  ratio without its denominator's provenance cannot be told apart from an
  over-aggressive mask" -- and until now **nothing read it**. 0.50 is not a
  fitted midpoint: it is the point where the mask has withheld more than it
  kept and stopped being the scalpel the module documents (about 11% of
  keypoints on the TEM panels it was calibrated on). The corpus offers no
  valley to cut at -- the saturation-gap distribution over the 357 Masliah
  panels where signal 1 fires is broad and unimodal -- so the threshold is
  the definition rather than a mode, and the CAUSE is pinned by a test that
  will fail if `chrome_mask` ever stops reading a sparse chromogenic stain as
  annotation.
- **A measuring-tool bug, fixed in the same pass and worth naming.**
  `scripts/image_ground_truth_score.py` clustered a figure's grid rows over
  every crop, and Figure S6's bar charts are taller than its micrographs and
  sit at y-centres BETWEEN the micrograph rows -- so a chart was absorbed as
  a row and every row below it shifted. The scorer reported S6-red as MISSED
  while the run's own group list held it as evidence. Charts are now excluded
  from the clustering, with a fallback to every crop when that leaves too
  few. The lesson is the one LESSONS.md already records: the first suspect
  for a disagreement between a detector and a score is the score.
- Tests: the corroborated floor (grain admits a small match; the same count
  with grain below the same-source threshold is still refused; an absolute
  floor is not re-applied to a corroborated count), the recount's
  admissibility (a blinded panel demotes nothing; the SAME recount through a
  surgical mask still demotes; one blinded side is enough; an unrecorded kept
  fraction does not block the test; the synthetic sparse stain that
  reproduces the cause), and the size floor (Figure 2's twelve sub-100-px
  micrographs kept in a 926 px figure; a thumbnail refused with the floor
  named; a 2,000 px figure keeping the old 100 px exactly).

GROUND TRUTH. `10.1242/jcs.113191` **0 → 3 of 3**, and `10.1038/nn.3070`
**9 → 10 of 14** -- the gain there is Fig. 4a green, a near-blank GFP control
against its supplement copy at 18 candidate correspondences, admitted by the
corroborated floor on the matched region's own pixels. Neither set lost an
issue. A change measured on one paper that also raises recall on an
independently labelled one is the evidence these are general mechanisms;
see `docs/datasets/jcs113191-ground-truth-2026-09-14.md`.

PANELS600, the independent box ground truth (600 figures, 4,888 annotated
boxes, same model and split as every earlier run). This is the measurement
`docs/datasets/panels600.md` has asked for since 2026-09-12, and it is the
evidence the box floor is a general fix rather than one tuned to one figure:

| | before | after |
|---|---|---|
| box recall, side < 100 px | 0.6% (16/2621) | **61.7%** (1617/2621) |
| box recall, all boxes | 44.5% | **78.1%** |
| box **precision** | 90.7% | **94.9%** |
| multi-box figures split | 77.5% | **95.5%** |
| one-box figures returned UNSPLIT | 97.9% | **97.9%** |
| annotated Blots reaching the type call | 36 | **171** |
| Blots typed `Graphs` | 0 | **0** |

Precision RISING while recall gains 34 points says the boxes the gate removed
were mostly correct boxes, so the old 44.5% was measuring our gate rather than
the model. The one-box-figure guarantee did not move, which is the property
that had to hold. **The cost is runtime**: more kept boxes means more sibling
crops and the tier-3/4 pair count is quadratic in them, so the 203-paper
Masliah gate lane went 836 s (accepted baseline) -> 1,272 s (1.67.0) ->
2,070 s (1.68.0), about 1.6x for this release and 2.5x since the baseline.
Budget for that before re-sweeping anything large.

GATE (full profile, against the accepted baseline `ee86704a3f92`): running at
the time of this commit. The record and the numbers land in `eval/gate/` and a
follow-up commit, as for 1.66.0. The price to watch is the negatives lane: on
the 203-paper Masliah subset, 42 of 176 `chart_furniture` demotions keep under
half their panel and become evidence again under the abstention above.

## [1.67.0] — the supplement is compared, the clipped figure is split, the keypoint tier looks at every pair, and a shifted field is found (2026-09-14)

MINOR: detector answer changes in `panels.py` and `image_analysis.py` (both
fingerprinted), so every earlier sweep reads `stale:fingerprint`. Image
package 0.19.0. Nothing re-sweeps by itself. Every change below was
measured on the regression gate before landing (numbers at the end) and on
the new per-paper ground truth for `10.1038/nn.3070`
(`docs/datasets/nn3070-ground-truth-2026-09-14.md`): **0 → 9 of 14** PubPeer
reuses caught, with three sparse-field overlaps still open.

- **A cut-out soft mask is read, not refused.** `_soft_mask_verdict` names a
  mask `opaque` (every sample 255), `cutout` (samples 0 or 255: a transparency
  cut-out, the way a figure with a white surround is dropped on a page),
  `blend` (intermediate alpha, still withheld) or `undecodable`. A cut-out's
  hidden pixels are blanked to white before hashing and comparison, so only
  what a reader saw can match, and the placement is read as unmasked. On
  nn.3070 every one of the supplement's ten figure streams carried one
  (67–99.9% opaque) and the whole supplement was compared by nobody, with no
  caveat -- eight of the fourteen reuses live there.
- **A renderer-clipped figure's visible crop is split.** A CMYK JPEG placed
  under a hairline clip is `visible_crops_only`; the crop was compared but
  never segmented, so a 3 x 5 montage was one panel that could match nothing
  inside itself. Montage-sized visible crops now take the segmentation pass
  (small ones stay untyped: typing every crop cost one ONNX call each and
  took `sj.emboj.7600845` from 1 s to 29 s). And a montage may be ONE ROW:
  `_montage_sized` asks for a long side over 400 px and a short side over
  150 (Figure 5a is 6 x 2 micrographs in 1420 x 371 px).
- **The keypoint tier compares every pair it can.**
  `_MAX_TRANSFORM_PAIRS_LEARNED` 1,600 → 100,000, and above the budget pairs
  go in order of perceptual-hash distance rather than uid. With the
  supplement admitted nn.3070 has 57,256 candidate pairs; at 1,600 the tier
  compared the first 4% by xref number, a 49-inlier reuse among the 96% it
  never looked at, and the only symptom was one caveat line.
- **Keypoints for faint stains and dark fields.** A panel with fewer than 300
  keypoints at SIFT's default contrast threshold is detected again at 0.02;
  textured panels never are. GFP/AP-Nogo66 vs its supplement copy: 154 → 571
  keypoints, 9 → 57 inliers.
- **Gates that read small panels as knots.** The 40-px inlier-cluster floor
  becomes `min(40, 15% of the panel's short side)` and refuses only a KNOT
  (small in both directions) -- a band is the sliver rule's business. A
  match with at least 40 inliers may have an inlier share down to 0.20
  (was 0.25 for all). The 2-NN descriptor ratio is 0.7 (Acuna 0.6, Lowe
  0.8). And when a pair had at least 30 candidate correspondences forward
  and failed a later gate, the other direction is tried: the ratio test is
  asymmetric, and Supp. Fig. 9 a/c NoZymosan clears every gate as b→a (86
  inliers, 0.262) and fails as a→b by two thousandths.
- **Tier 6, `shared_field_overlap`** (`image_forensics/overlap_field.py`,
  fingerprinted): one field of view shown twice with a shift -- the
  commonest reuse in the Bik taxonomy, invisible to keypoints on a dark
  sparse field (6–24 candidates on nn.3070's Figure 1a pairs under every
  SIFT setting). Padfield's masked normalised cross-correlation over EVERY
  translation, on the dominant colour channel after a light blur, between
  crops of one parent; a pair fires at peak >= 0.75 AND a peak-to-sidelobe
  margin >= 0.20, the overlap at most 85% of the smaller panel, and the
  overlap at least 100 px on BOTH sides. Three tests, three measured
  false-positive classes: the margin refuses striped tissue and banded lanes
  that correlate at many shifts (peak 0.93, margin 0.007 on nn.3070's retina
  sections); the overlap ceiling refuses two panels at the SAME framing,
  which correlate over their whole area at ~zero shift where the margin is
  high for free (any fine-grained image decorrelates a few pixels off its own
  alignment) and which tiers 3-4 already own; the side floor refuses a
  20-52 px band down one edge, a shared label row or scale bar. The first
  version carried only the peak and the margin, fired ONCE in nn.3070's 1,774
  sibling pairs, and then fired **208 times in 24 of the 203 Masliah papers**
  -- thresholds fitted to one paper. With the two geometric tests, grid-
  searched over both sets together: Masliah 208 groups in 24 papers → **5 in
  3**, nn.3070's labelled Figure 1a overlap (107 x 181 px at 23%) still
  fires. `overlap_field.refusal()` names which test refused a pair and the
  per-paper caveat counts them. Translation only; the affine it records is
  tier 4's convention, so the exhibit box needs no special case. About
  35 ms per sibling pair.
- Tests: cut-out vs blend masks, the shared-field search (known offset
  recovered, independent fields refused, a shifted stripe pattern refused
  by the margin with a peak near 1, the same framing at zero shift refused by
  the overlap ceiling, a shared edge strip refused by the side floor, a real
  corner overlap kept, the affine convention), a one-row montage, a partially visible
  montage's crop split, the low-contrast retry, the budget's new wording,
  the smoke paper's crops-of-crops.

RECALL ON THE INDEPENDENT SET. Masliah figure-level 6 → 10 of 36 with no hit
lost (the cut-out masks, the split visible crops and the pair budget carry
that; tier 6 contributes none of it) -- the evidence that these are general
mechanisms rather than a fit to one paper.

GATE (full profile, worktree code vs the accepted baseline ee86704a3f92):
MASLIAH LANE (203 papers, fingerprint `8987a6ae396a` against the accepted
baseline `ee86704a3f92`):

| | baseline | 1.67.0 |
|---|---|---|
| papers examined | 150 | **157** (8 fewer refused `all_panels_withheld`) |
| figure-level hits | 6 of 34 examined named | **10 of 36** |
| papers with a figure hit | 6 | **10**, none lost |
| papers firing | 39 | 62 |
| `transformed_match` fire rate | 0.153 | 0.325 |
| `shared_field_overlap` fire rate | — | 0.032 |

The four papers gained are `10.1007--s13365-016-0502-z`,
`10.1016--j.neuron.2014.11.027`, `10.1038--ncb2090` and
`10.1523--jneurosci.3527-05.2005`. The fire rate trips the format alarm at
0.39, which is the stated price of admitting the supplements and splitting the
clipped figures; it is a skim cost in the webapp under the standing
recall-first policy, and no hit was lost buying it.

THE OTHER LANES HAVE NO USABLE MEASUREMENT AT THIS FINGERPRINT, and the reason
is an error of mine rather than an interruption. That gate started at 18:08
and computed `8987a6ae396a` from the 1.67.0 files; at **19:49:50 I overwrote
`image_analysis.py` and `panel_detector.py` in the same checkout with the
1.68.0 versions while it was still running.** Its parent kept the modules it
had already imported, but every per-paper child spawned afterwards read the
new files from disk -- so those papers were examined by 1.68.0 code and
recorded under a 1.67.0 label. The Masliah lane is unaffected (1,272 s from
18:08, finished about 18:30, so the numbers above stand); the reviewed-581
lane straddles the edit and is VOID; RSIID and audits never completed.
`eval/gate/8987a6ae396a.json` now carries a `CONTAMINATED` block saying so
lane by lane, because a mixed-code record is not a failed measurement that
announces itself -- it is a plausible-looking file whose label does not
describe the code that produced it.

The rule this broke is stated in CLAUDE.md: never edit a file in
`retain.FINGERPRINT_FILES` while a sweep is running. The earlier 1.67.0 work
had done this correctly, in the `wt_jcs` worktree; copying the next change
into the checkout the gate was reading is what undid it. The clean measurement
of 1.68.0 is `eval/gate/8ffd9cfc7edf.json`, from a gate started at 19:51:42,
after the edit -- see the next entry.

## [1.66.3] — the exhibit draws the region the panels SHARE, not just the keypoint hull (2026-09-14)

PATCH, exhibits only: no detector file moved, so every stamp stands and the
change is backfillable with `metascience image-rebuild-exhibits`.

Dan, on `10.1038--nn.3070` `IMGDUP-136` (Supplementary Figure 9, two retina
sections): the finding is right and "the relevant box for the transformation
is actually larger" than what was drawn. Two things were wrong with the
drawing, neither with the detection.

- The thick box is the bounding hull of the RANSAC inliers, and SIFT plants
  keypoints on corners: on a section whose whole width corresponds, the hull
  was a 32 x 218 px strip down one nuclear layer (`matched_frac` 0.15 while
  the transform maps 57% of the panel across).
- The second marker was the other panel's whole frame projected UNCLIPPED.
  Under that pair's rotation of -7.3 degrees and scale of 0.76 it leaves the
  panel, and it rendered as two diagonals running off the corner of the
  image -- worse than nothing, because it reads as a drawing error.

`animate_panel_match.pubpeer_figure` now draws, in green on BOTH panels, the
region the two panels SHARE under the recovered transform: each panel's own
rectangle intersected with the other's mapped rectangle, so it is always
inside both. The keypoint hull stays, in blue, inside it, and the legend says
which is which and that the hull understates the correspondence. Every
exhibit of the travis_dickendesher_papers corpus was rebuilt
(`image-rebuild-exhibits`, 5 papers with groups, 10 scored).

`tests/test_exhibit_shared_region.py` pins the geometry (a pure translation,
that pair's rotation-and-scale, disjoint panels) and that a rendered still
carries both colours.

## [1.66.2] — a review decision advances to the next undecided item (2026-09-14)

PATCH: workbench navigation only; detector answers and findings are unchanged.

Clicking a feedback button on an image item (or pressing 1–9), and the
same buttons on copy/paste review, records the decision and then opens
the next undecided item in the current filter. A failed save stays put.
`n` is still the manual skip.

## [1.66.1] — sort the image queue by paper folder (2026-09-14)

PATCH: workbench navigation only; detector answers and findings are unchanged.

The image queue Paper column is a sort header (A→Z, Z→A, then back to rank
score). Sort runs on the server before pagination so it covers the whole run,
not the 50 loaded rows. Score stays the default order; clicking it toggles
high→low / low→high. The copy/paste queue's Paper / file header does the
same. Reset filters restores score order.

## [1.66.0] — the hi-res lever, publisher renders harvested, DAPI beside its merge demoted, stencil figures, labels from the next page, one form for supplementary figures (2026-09-14)

MINOR: detector answer changes in `panels.py`, `image_analysis.py`,
`pdf_occurrences.py`, `channel_overlay.py`, `extraction/figures.py`, so
every earlier sweep reads `stale:fingerprint`. Image package 0.19.0.
Gate: baseline `ee86704a3f92` (1.65.1) accepted before the first change;
the after-record and the comparison are named at the end of this entry.

- **`hires_pixels`** (STAMP flag, opt-in, `--hires-pixels`, sweep id
  `_hires`): the analysis builds the figure source ledger in-process after
  the harvest and lets a keypoint-VERIFIED, whole-frame rendition at
  >= 1.25x an embedded stream's width supply that stream's PIXELS to the
  transformed and clone tiers. Crops (montage segments and the visible
  crops of a partly shown stream) read the same rendition through a scaled
  box. Identity, `phash`, placements and tiers 1-2 take nothing from it
  (Dan's decision). Refusals are counted by name (`hires_refused:
  no_verified_link | sub_region | smaller_than_stream | contradicted`),
  groups carry `pixel_sources` and a sentence with both sizes, the exhibit
  is rendered from the substitute for whole-stream panels, and a substitute
  that fails to load falls back to the stream and says so. Flag off is
  byte-identical to before (tested). MEASURED on Cell 2015 (7 figures, all
  with 2905-px Elsevier renditions): 7 streams substituted, the transformed
  tier finds one more genuine same-figure pair (119 inliers) and three
  chart-furniture context groups it demotes; 14 s -> 29 s.
- **`harvest_publisher_figures`**: `publisher_figures/` renders become
  `publisher_render` panels through the one body the PMC harvest now shares
  (`_harvest_manifest_renders`; the PMC output is pinned byte-identical).
  Beside an identified main PDF they stay `alternate_source_ignored`; for a
  PDF-less paper they are coverage. The manifest joins
  `retain.inputs_digest`, so a fetch re-runs the paper.
- **`channel_overlay.active_channels`** scores each channel's EXCESS over
  the per-pixel minimum instead of its raw level. Scored by level, a
  DAPI-only panel read blue+green+red (ratio 1.00/0.21/0.18) and the
  demotion abstained for "no channel asymmetry"; five DAPI-vs-merge pairs
  on `10.1242/dev.134627` Figure 6 were filed as duplication evidence.
  Scored by excess the same panels read [blue] (0.05/0.01) and their
  merges [blue, green] (0.36-0.43); measured on all three flagged pairs.
- **`label_basis` on every placement and `adjacent_caption_labels`** (STAMP
  flag, opt-in, `--adjacent-caption-labels`, sweep id `_adjlabels`):
  `_map_placement_to_figure` returns how a label was assigned
  (`same_page_caption` / `adjacent_page_pointer` / `manifest` / `inherited`),
  and a page holding raster placements at >= 10% cover with no same-page
  caption now emits `figure_label_unassigned: page N, K raster placement(s)
  (largest cover M%), no same-page caption` and counts under
  `n_pages_unlabelled` -- the silent None is gone. With the flag on, a
  "(see figure on previous page)" caption on page p+1
  (`caption_context.PREVIOUS_PAGE_POINTER_RE`, now fingerprinted) labels
  page p's placements only when they form ONE bbox cluster; two clusters
  refuse `adjacent_pointer_ambiguous`. Flag off is byte-identical on 5
  fixture PDFs and the 14 Dickendesher PDFs; no pointer occurs in any of
  them, so the flag-on path is measured on synthetic pages only until the
  gate sees a population. The review manifest carries `label_basis`.
- **One canonical form for supplementary figures**: `extraction/figures.py`
  (`SUPPLEMENTARY_PREFIX`, `supplementary_figure_number`),
  `figure_context.figure_key` and `pmc_figures.normalise_label` all emit
  `Figure S<n>` for the Supplementary / Supplemental / Supp. / Supporting
  family, so a JATS or Elsevier "Supplementary Figure 1" no longer shares a
  key with "Figure 1" (six figures under three labels on
  `10.1016/j.jalz.2018.02.017`). Prose mentions follow (`Supplementary
  Figures 3 and 4` cites `Figure S3`/`Figure S4`). Extended Data / Online /
  Appendix keep today's form in all four readers.
- **Harvest hygiene** (`panels.py`, `pdf_occurrences.py` REVISION 2):
  every embedded stream carries `raw_stream_sha256`, `passthrough` and
  `stream_filter` beside the unchanged `content_sha256` (the proof from
  `figure_sources.raw_stream_proof`, shared, not copied); inline BI/ID/EI
  images are counted per page and named, never silently absent; a stream
  MuPDF fails to decode is withheld with the filter named -- the raising
  case (JPX) as `undecoded_<Filter>`, and the NON-raising case, measured on
  PyMuPDF 1.27.2 where junk JBIG2 and CCITT return an all-zero bitmap and
  only leave "cannot complete jbig2 image" / "overflow in 1d faxd" in the
  warning store, as `decode_errors_<Filter>`, because a pHash on garbage is
  a manufactured finding. `trace_images` now reads `fill_image_mask` like
  `fill_image`: an `/ImageMask` drawn as artwork used to fail the whole
  page's inventory, and on `10.1074/jbc.m001151200` 3 of the 4 JPEG
  micrographs were withheld `visibility_unresolved` for that alone
  (eligible panels 1 of 6 -> 4 of 6 at default flags). `stencil_art`
  (STAMP flag, opt-in, `--stencil-art`, sweep id `_stencil`) harvests a
  1-bit mask with a shorter side >= 600 px as a `stencil_art` panel
  (outside `ORIGINAL_BYTES`, perceptual/keypoint tiers only): the JBC
  figures at 4155x1819 and 4281x2000 become eligible (6 of 6). Supplement
  containers: `.pptx` and `.xlsx` read like `.docx`; a one-level `.zip`
  yields its image members and the docx/pptx/xlsx inside it; `.doc` is
  converted with LibreOffice when `soffice` exists (cached under
  `.extraction_cache/doc2docx/`) and otherwise counted
  `unreadable_container` by name. A canonical alias records the xrefs it
  absorbed as `alias_xrefs`.
- Publisher adapters: `figure_label` promotes to `Figure S<n>` only for the
  Supplementary family or the Elsevier `figs<n>` locator, agreeing with the
  shared normaliser by test.
- **Gate (quick profile, `eval/gate/c9415ab960fa.json` against baseline
  `ee86704a3f92`): PASS.** Masliah figure-level 6 of 36 examined (was 6 of
  34; `pdf_occurrences` REVISION 2 lets two more named figures be examined),
  paper-level 20 of 52 (was 20 of 50), fire rate 25.3% (was 26.0%); RSIID
  true positives 80 (was 79), false positives 0. A first after-run was
  contaminated by a concurrent gate on the same scratch corpus (15 positives
  `not_run_this_sweep`, one hit "lost"); gate.py now takes a `.gate.lock`
  (f0b3ae88) and the run recorded here was made under it. What
  `pdf_occurrences` REVISION 2 bought, read off the two records: Masliah
  refusals `all_panels_withheld` 31 -> 26 and `scanned_pages` 8 -> 5, so
  EIGHT papers that were refused are now examined, and the two alleged
  figures previously missed as `refused:all_panels_withheld` are gone from
  the miss attribution. The hit count is unchanged at 6 because those eight
  papers fired on nothing a sleuth had named -- a bigger honest denominator,
  not a recall gain.

## [1.65.1] — paper-folder search on the image and copy/paste queues (2026-09-14)

PATCH: workbench navigation only; detector answers and findings are unchanged.

The image queue (and the copy/paste queue) can search by paper folder name
(`10.1007--s004010050748`). The match is a case-insensitive substring of the
folder shown in the Paper column, including a DOI pasted with a slash, and
runs on the server before pagination so it covers the whole run rather than
the 50 loaded rows. Reset filters clears it. The papers list already searched
`dir`; its placeholder now says so.

## [1.65.0] — every figure's renditions, measured and linked to the PDF stream; panel identity persisted; publisher adapters (2026-09-14)

MINOR: three new surfaces, no detector answer change (nothing in
`retain.FINGERPRINT_FILES` moved; every existing sweep stays `done`).
Image package 0.18.0.

Dan, 2026-09-14: "we want original images when available and highest
resolution versions obviously, while also tracking figure number,
subfigure letter, location in the pdf (for the webapp viewer) and caption
when possible." Measured the same day on the Dickendesher corpus, Fig 1
width: Cell 2015 PDF 1743 / PMC 800 / Elsevier `_lrg` 2905; Nat Neurosci
2012 PDF 1742 / PMC 669 / Nature `full/` 946; Development 2016 PDF 1067 /
PMC 800 / Silverchair 1004. No source wins in general, so nothing can
prefer a publisher copy by rule -- it has to be measured per figure, and
it has to be PROVEN the same picture, because an accepted manuscript and
the version of record renumber figures.

- **`image_forensics/figure_sources.py` (NEW, not fingerprinted) and
  `metascience image-figure-sources`**: `panels/figure_sources.json`, one
  record per figure key listing every rendition on disk -- the embedded
  PDF stream(s) with a raw-stream proof (`raw_stream_sha256`,
  `passthrough`, `filter`, ported from fetchpdf's extractor, the first
  time `content_sha256` is checked against the bytes the authors
  embedded), the visible crop of a partially shown stream, `pmc_figures/`,
  `publisher_figures/`, fetchpdf `<stem>_figures/` (its first consumer;
  its `provenance: original` is the PMC S3 object, measured 669-800 px,
  not the authors' file) and supplement copies -- each with decoded pixel
  size and a keypoint LINK to a PDF stream: `verified_keypoint`,
  `contradicted` (its best whole-frame match carries a different figure
  label), `phash_only`, `unverified`. `best_pixels` is the largest
  verified whole-frame rendition and never a contradicted one. Identity
  stays with the PDF stream (Dan's decision): uids, `content_sha256`,
  placements and the byte tiers take nothing from here. Absence is
  named: `not_fetched` / `refused:<kind>` / `unreadable` per source.
  Page renders of the captioned figure regions serve as link TARGETS
  (never candidates) for figures the harvest holds no usable stream for.
  MEASURED on 58 Elsevier Masliah papers (383 publisher renditions):
  first build 328 verified / 52 unverified / 3 contradicted -- the misses
  were 1-bit CCITT stencil figures (skipped as masks), figures built from
  dozens of sub-250-px streams, and 5-12% sub-region matches miscalled as
  contradictions; with page-render targets, multi-scale matching and a
  50% coverage floor for contradiction: 370 verified (97%) / 10 / 3. The 3
  survivors are REAL: on `10.1074/jbc.m001151200` page 3 the region
  `extract_figures` labels Figure 1 renders the micrographs that are
  Figure 2 and vice versa (also `s0006-8993(01)02772-x` 3<->2). The link
  is therefore also a corpus-wide detector of caption-artwork
  mis-assignment. A non-PDF rendition holds the most verified pixels on
  243 of 380 Elsevier figures (median publisher/PDF width ratio 1.33) and
  on 2 of 7 Cell 2015 figures; on Nature and Company of Biologists papers
  the PDF stream keeps winning. Review items carry `panel.figure_sources`
  (renditions, links, best, ledger state) and the item page lists them.
- **`image_forensics/panel_identity.py` (NEW, not fingerprinted) and
  `metascience image-identity-backfill`**: `panels/panel_identity.json`,
  per placement the page, page size and rotation, the affine, the exact
  crop polygon and the sub-panel letter read from the PDF's own text --
  computed ONCE from the PDF and keyed to its sha256 and the panel index
  sha256. `evidence.enrich_panel` reads it first and names
  `identity_sidecar_absent|stale|no_record|no_placement` when it cannot,
  which is what stops a replaced PDF silently degrading every crop to
  `parent_approximate`. The geometry loop is one function (`_place`)
  shared by the live path and the sidecar, so they cannot diverge.
  `evidence.classify_panel_label` names the label kinds `normalise_subletter`
  refuses (`ii` roman, `2a` alnum, `A*01:01` allele, `R444C` mutation, `A₂`
  subscript -- 17 of 21 measured mismatches, CHANGELOG 1.42.1) and `_labels`
  records roman/alnum as `candidate`, never `observed`. The review manifest
  keeps `bbox`, `occurrence_id`, `bbox_kind`, `subfigure` per placement.
- **Webapp**: `buildPaneLocator` carries `method`, so a page-only image
  placement reads "Figure on p. N" instead of the text-quote sentence;
  `paneDocument` substitutes the main PDF only for a main/unknown PDF role
  and otherwise renders `NativeImagePane` -- the parent image with the crop
  polygon and the sentence "No PDF location: this panel comes from
  <document>; shown on its native image" -- for PMC/publisher renders,
  `.docx` members and loose supplement images, which used to open the
  main PDF at page 1 without a caveat. The panel block lists the ledger's
  renditions (source, px, link, best) and the identity sidecar state.
- **`image_forensics/publisher_figures.py`** is an adapter registry
  (`--publisher auto|elsevier|springer|silverchair|wiley`, manifest 1.1
  with `publisher`, `route`, DECODED width/height and a dated
  `measured_note` per adapter; 1.0 manifests still read). Elsevier adds the
  keyless `gr<n>_lrg.jpg` CDN route by PII (the formatted PII's check
  character sits in position nine, which the first unformatter got wrong
  and a test caught); Springer rewrites `lw685/` to `full/` and, on the
  JATS route, tries the `.jpg`/`.png` sibling because the media server
  answered 502 for the JATS-named `.jpg` and 200 for `.png` on
  `s12325-024-02850-9`; Silverchair refetches the article page over IPv4
  (a scoped `socket.getaddrinfo` swap) for its signed URLs and refuses
  `network_route_unavailable` on a Cloudflare challenge -- this machine is
  not always on the entitled route; Wiley is enumerated and refused
  `entitlement:403` by name, unmeasured. Elsevier supplementary attachments
  (`figs<n>`, raw label "Supplementary Fig. N") are labelled `Figure S<n>`
  instead of colliding with `Figure <n>` (six figures under three labels on
  `j.jalz.2018.02.017`). LIVE on the 12 Dickendesher papers: Cell 7/7
  (2905, 2897, 2230, 2232, 2233, 1644, 2889 px), Neuron 1/1, Development
  and JCS 8/8 large; Nature refused `no_article_html` (NIHMS graphic names,
  honest); Springer 0/2 before the sibling fix.
- `figure_sources` treats `Figure S3` and `Figure 3` as one number for the
  contradiction test only: the PDF caption parser and `figure_key` consume
  the Supplementary prefix while the new manifests keep it. Unifying the
  canonical form across `extraction/figures.py`, `figure_key` and
  `pmc_figures.normalise_label` is fingerprinted work for the next bump.

## [1.64.0] — the detector regression gate, and false positives that say why (2026-09-14)

MINOR: a new verb and a wider decision vocabulary; no detector answer
changes (nothing fingerprinted moved). Image package 0.17.0.

- **`metascience image-gate`** (`image_forensics/gate.py`). Three detector
  changes shipped today, each checked by hand-run sweeps on scratch copies
  against numbers recalled from memory files; it worked because one person
  remembered which scorecard to diff, which negatives mode to read
  (`contained`), and that the 25-row `missed_papers` cap fakes "gained"
  papers. The gate runs those measurements for the code on disk -- the
  203-paper Masliah PubPeer subset (recall), the 581 papers carrying the
  1,979 human false-positive marks (precision; `--profile full`), RSIID at
  40 per family, and the single-rule audits -- on SCRATCH copies only (each
  must carry a `SCRATCH` marker; the sweep is forced) and writes
  `eval/gate/<fingerprint>.json`, one record per detector fingerprint, lanes
  resumable. Hard gates against `eval/gate/baseline.json`, moved only by
  `--accept <fp> --note ...`: the SET of Masliah figure-level hits may not
  shrink, the 581 true issue must still fire, RSIID true positives may not
  drop nor its false positives rise. Soft (reported): negatives still
  firing, fire rate per tier, timeouts, p50 per paper.
  `tests/test_image_gate.py` pins the comparison on synthetic records and,
  once a baseline is accepted, fails on this machine when the fingerprint
  on disk has no record. No adjudication is reachable from the verb.
  Scorecards and per-pair listings land under the config's `scratch_out`
  (the reviewed corpus is embargoed); the committed JSON carries counts and the
  Masliah hit set.
- **Reason-specific false positives.** `false_positive_chart`, `_overlay`,
  `_supplement`, `_magnification` join the image decision vocabulary
  (`review_io.IMAGE_DECISIONS`; workbench keys 6-9; the review page's
  columns; `constants.gen.ts` regenerated). Every reader tests the
  `false_positive` PREFIX now (`image_review`, `screening`,
  `screening_eval`, `benchmark.is_false_positive`) so a new reason is never
  read as "not rejected", and the negatives block splits outcomes
  `by_decision` -- "355 still fire" becomes a count per class, which is what
  the overlay audit had to produce by hand this morning.
- `tests/test_context_kinds_registered.py`: every context kind the detector
  emits (read from its source) must be in `image_review.CONTEXT_KINDS` and
  the exhibit palette; it found `chart_furniture` and `chart_template`
  drawn in the fallback colour. The colour-angle demotion gets its first
  known-positive and known-negative tests (LESSONS.md section 4).

## [1.63.0] — a rectangle is a rectangle however the producer spelled it; a stream-less inventory row is not a mismatch (2026-09-14)

MINOR: `image_forensics/pdf_occurrences.py` is fingerprinted, so every earlier
image sweep resumes `stale:detector`, and panels that were withheld are now
compared. MEASURED on the 14-paper Dickendesher corpus swept with supplements:

- `_rectangle` accepted one spelling of a rectangular clip,
  `moveto + 3 lineto + closepath`. Elsevier (Cell) and Company of Biologists
  (Development, JCS) PDFs write `moveto + 3 lineto` with no closepath, or
  `moveto + 4 lineto` returning to the start; a clip path is closed
  implicitly (PDF 8.5.4). 16 figure draws were `unknown` and every one of
  those panels was withheld `visibility_unresolved`. After: 0 unknown on all
  four papers. A triangle, a pentagon or a diagonal is still refused.
- `page_inventory` demanded `len(draws) == len(get_image_info)`. On
  10.1007/s12325-024-02850-9 p.1 `get_image_info` lists a rasterised
  shading as a 30x30 image with xref 0 and the trace device calls it
  `fill_shade`, so the page raised and its figure was withheld.
  `align_inventory` now pairs rows with draws by geometry and tolerates a
  leftover row that has NO stream (xref 0: nothing the harvest could
  extract); a leftover row with a real xref, or a draw no row explains, is
  still a mismatch. The standalone package is 0.16.0.

- **A supplement that is the article delivered again is not a reuse of its
  figures** (`image_analysis._demote_document_redelivery`, fingerprinted).
  Cell Press ships "article + supplement" as one PDF and the fetcher files it
  as `supplementary_info_2.pdf`; the bytes differ from the article's, so the
  byte-identical drop never sees it, and every figure of the article is then
  byte-identical in "another document". MEASURED on
  `10.1016--j.cell.2015.11.060`: 7 of 9 streams at the SAME xref with the
  SAME sha256, 6 groups between the copies, 11 model calls for the screen to
  say "pixel-identical copies of the same Figure 3 in two PDFs of the same
  article". Two documents of one paper sharing >= 3 (xref, sha256) pairs are
  two builds of one PDF; a group whose members collapse to one object number
  across them is the `document_redelivery` context kind, evidence False,
  kept for the reader. Members at DIFFERENT object numbers (Figure 2 found
  again as Figure S4) stay evidence. The result carries `document_redelivery`
  (pairs, shared counts, demotions).

Read but NOT changed, for the record: the three `no_rasters` refusals in this
corpus are correct (the renderer's 185 and 3 "image" draws are 3-pixel glyph
bitmaps; the figures are vector art, `--rendered-regions` is the route), and
the 20 withheld supplement panels of 10.1038/nn.3070 carry real soft masks
(0.1%-25% of samples below 255).

 — the author builder asks five indexes: Europe PMC and Crossref join OpenAlex, Semantic Scholar and PubMed (2026-09-14)

PATCH, `examples/build_author_corpus.py` only; the pipeline is untouched.

Dan asked that every bibliographic API be consulted (OSF deliberately
excluded here). Two new sources, each behind a structural guard:

- **Europe PMC** `AUTH:"<Surname> <I>"`, cursor-paginated; the hit's
  `authorString` must carry the surname. Its `pubType` list is kept in its
  own `epmc_types` field and never pre-empts NLM's `pub_types`.
- **Crossref** `query.author=<surname>`, relevance-sorted OFFSET pages,
  stopping at the first page whose items include none of the target's works.
  The work's own `author` array must carry the surname AND the first initial.
  Two measured traps: `cursor` paging returns index order, not score (the
  first 1,000 of 57,183 fuzzy hits for the full name held none of the 13
  real works, so the stop rule quit with zero); and the full-name query
  ranked two 14/15-author papers past the first empty page, where the bare
  surname scores exactly the 13. Crossref types are mapped onto the OpenAlex
  vocabulary, and OpenAlex's by-DOI type now OVERRIDES a Crossref-only type
  (Crossref calls a book's "Contributors" page `book-chapter`; OpenAlex says
  `paratext`).

`--skip-europepmc` / `--skip-crossref` mirror the existing skips. On the
Dickendesher build every kept DOI is now confirmed by 3-5 sources and the
union did not change.

## [1.62.1] — a sweep run on this machine registers its corpus folder with the workbench (2026-09-14)

PATCH, workbench plumbing and wording; no analysis output changes.

Dan, on the Dickendesher thesis review page: "Paper files unavailable on this
computer; register a local folder -- no DOI on disk to build a download link
from ... if no DOI it should read pdf from folder". The folder was there. The
workbench resolves a paper's directory only through a registered local root,
and the only code that registered one was the full-pipeline path
(`image_integration._notify`); `image-sweep` synced its runs and never said
where the corpus was. The DOI sentence was a second wrong signal: it belongs
to the "PDF not available, using XML" warning and was rendered beside every
warning.

- `image_forensics/sweep.py`: after the database sync, whatever it did, the
  sweep calls `integration.published(corpus)` -- the directory it just read
  exists on this machine -- logs `local root: notified` (or the standalone /
  polling-fallback state) and records it in `sweep.json` as
  `local_root_notice`.
- `workbench/catalog.py:paper_path`: the refusal names the project and the
  paper directory and says the remedy (Files page, or re-run the sweep here).
- `SourcePane.tsx`: the download-link sentence renders only for the XML
  fallback.
- The same missing root also broke every image page of the run: archived
  artifacts (`__runs/<run>/<artifact>`) are looked up under
  `<root>/.analysis_runs/objects`, and with no root there was nowhere to
  look -- pdf.js reported `MissingPDFException` and every panel was an empty
  grey box. Two independent ways a root becomes known now: the sweep's
  notification (above) and `corpora.papers_root`, which
  `history_db.sync` now records (the column existed, nothing wrote it) and
  `catalog.discover_root` uses -- only when that folder exists on this disk,
  never a symlink -- from `paper_path` and the artifact resolver. Another
  machine's path is ignored. The artifact refusal names the file, the
  project and how many roots are registered.
- `PdfPane.tsx` shows the media route's JSON `error` instead of pdf.js's
  "Missing PDF" wrapper; `ImageItem.tsx` names a panel image that failed to
  load with the same server reason, instead of a grey rectangle.

---

## [1.62.0] — a figure number is one grammar: dotted chapters and appendix letters (2026-09-14)

MINOR: `extraction/figures.py` is in `retain.FINGERPRINT_FILES`, so every
earlier image sweep resumes as `stale:detector`; and a paper's figure labels,
caption joins and citing sentences can now differ from the previous release.

MEASURED on the first 314-page document through the image track, the
Dickendesher (U Michigan 2013) thesis, 66 embedded streams, 58 figures:

- captions read `Figure 2.10:`. `_CAPTION_RE` accepted the dotted chapter
  form (added for the dashed Stiles thesis in 1.60.0) but
  `figure_context._KEY_RE`, `pmc_figures._FIG_LABEL_RE` and the prose-mention
  grammar did not, so `figure_key("Figure 2.10")` was `Figure 2`: every
  chapter-2 figure keyed to one label for screening context, and
  `uses_compound_numbers` said the document was not chapter-numbered;
- the appendix figures read `Figure A1.1:` and matched NOTHING -- three
  figures out of 58 were not figures (Dan: "appendix figures missing is a big
  issue");
- page 176 carried the widow of a cross-reference sentence, `Figure 3.1.`
  alone on a line, and the parser filed it as a second, uncropped
  `Figure 3-1` fourteen pages before the real one.

Now:

- `extraction.figures.FIGURE_NUMBER` is the ONE grammar -- an optional letter
  glued to a digit (`S1`, `A1`), digits, an optional chapter tail after a
  hyphen, en dash or dot -- and `canonical_figure_number` the one spelling
  (`2.10` -> `2-10`, `A1.1` -> `A1-1`, `A. 1` -> `A1`, `S 03` -> `S3`). The
  caption parser's label, `figure_key`, `pmc_figures.normalise_label` and the
  mention reader all go through it, so a label and its key cannot drift
  apart again (`test_figure_key_agrees_with_the_image_tracks_normaliser_on_plain_labels`
  now covers the dotted and lettered forms). `Fig. A.1.` renders `Figure A1`
  (it rendered `Figure A.1`, which `figure_key` could not key at all).
- The compound (chapter-numbered) mention reading accepts a glued dot:
  `Figure 2.10a` is figure 2-10 panel a; `Figure 2. Ten mice` stays figure 2
  and a sentence end. The journal reading is unchanged (`2.10` is not a range).
  The letter prefix is accepted at the head of a citation list only and never
  as the tail of a word: `Figs. 2 and 3` does not cite a `Figure D3`, and
  `Figure 2, N2a cells` does not cite a `Figure N2`.
- A bare numbered label with no caption text on a page with no artwork is
  named a cross-reference widow in `warnings` and not recorded. Research
  Square's bare `Figure 1` labels on figure-only pages are kept (those pages
  have artwork), and a page whose images could not be decoded keeps its
  record (that is a failure of our reader, not a fact about the page).

- `image_forensics/pdf_occurrences.py:trace_images` (also fingerprinted):
  the same thesis is the first TAGGED PDF (Word/Acrobat PDFMaker) through
  the track, and MuPDF's trace device nests every drawing event of a tagged
  page inside `<structure standard="Figure">` (and `Sect`, `P`, ...), with
  alt-texted figures further inside `<metatext>`. The parser walks the
  root's children, so it saw ZERO `fill_image` events against a non-zero
  `get_image_info`, `page_inventory` raised its count mismatch, and the
  sweep withheld 64 of 66 streams `visibility_unresolved` and refused the
  paper `all_panels_withheld` -- coverage zero, honestly reported, on a
  document whose figures were all in plain sight. Both containers are now
  flattened to inert markers exactly as `group` and `layer` already were
  (structure carries no graphics state; a clip opened inside one still
  pairs with its pop). MEASURED: 0 of 65 figure pages resolved -> 311 of 314
  pages after `structure` -> 314 of 314 after `metatext`.
- **An all-opaque soft mask is not a mask** (`panels.py`, `pdf_occurrences.py`,
  both fingerprinted). Word attaches a soft mask (`/SMask`) to most PNG
  figures it embeds, and the harvest withheld every soft-masked stream as
  `visibility_unresolved` -- correctly, for a mask that hides pixels, since
  the decoded stream then differs from what a reader sees. MEASURED on the
  same thesis: 16 of 66 streams carry one, and in **12** the mask is every
  sample 255, hiding nothing -- a quarter of the data figures never
  compared. `Panel.smask_opaque` records that the mask was decoded and is
  all-255 (an undecodable mask is unknown, and unknown stays withheld);
  `trace_images` reports `self_mask_only` and `visibility_if_mask_opaque`
  for a draw whose only unsupported clip is its own `clip_image_mask`; the
  harvest reads such a placement as unmasked and says so in the panel's
  warnings. The 4 streams whose masks do hide pixels stay withheld with the
  same named reason. `tests/test_pdf_occurrences.py` builds a PDF from an
  RGBA PNG under both alphas.

Thesis after: 58 figures, 58 cropped `high`, no duplicate labels; the
standalone package is 0.15.0.

---

## [1.61.2] — the run dropdown lists one line per event (2026-09-14)

PATCH, workbench listing only; no answer changes.

- `workbench/repository.py:catalog_runs`: a run record whose execution is in
  the listing FOLDS into that execution's option (`run_ids`, `n_runs`,
  `components`, the version and component appended to the label, `N papers`
  when more than one). Selecting the execution already selected its records,
  so nothing becomes unreachable; a record whose execution is not listed
  still stands on its own. MEASURED on the Stiles thesis project: seven events
  showed as twelve lines (Dan: "one run should not be shown twice"); now six.
  On an N-paper sweep the old listing was N+1 lines per sweep.
- `webapp/app/RunSelector.tsx`: the folded run ids are the option's tooltip.

---

## [1.61.1] — a PubMed record is identified by its own ArticleIdList, not by the last paper it cites (2026-09-14)

PATCH, `examples/build_author_corpus.py` only; no pipeline output changes.

`pubmed_records` and `pubmed_types_for_pmids` built their id map with
`art.iter("ArticleId")`, which walks the whole `PubmedArticle` -- and efetch
XML now ships each record's `<ReferenceList>`, where every cited paper carries
its own `IdType="doi"` / `IdType="pubmed"`. The dict kept the LAST one, so a
record came back under a cited paper's DOI and PMID with its own title intact.
MEASURED on `Dickendesher T[au]`: 2 of 10 records (J Cell Sci 2013 as
`10.1074/jbc.M311292200`, Development 2016 as `10.1038/ncb1045`), and because
the title still matched, `dedupe_by_title` collapsed the CORRECT DOI from
OpenAlex into the wrong one -- the corpus would have fetched two strangers'
papers under this author's titles. Now `_pubmed_article_ids` reads
`PubmedData/ArticleIdList` only. Any author corpus built before this whose
PubMed records carried reference lists may hold the same substitution; the
Masliah build (2026-08-17, 962 PubMed records) has not been re-checked.

## [1.61.0] — a channel shown beside its own merge is demoted, deterministically (2026-09-14)

MINOR: a detector answer change (`image_analysis.py` and the new
`channel_overlay.py`, both fingerprinted), so every earlier sweep reads
`stale:fingerprint`. Image package 0.14.0. Nothing re-sweeps by itself.

Dan, on `10.1128--jvi.00651-17` Figure 3: the grey alpha-NSP2 488 nm channel
beside the Overlay panel of the same row was surfaced as a duplication -- and
was, by every pixel gate, "the same pixels" (grain r = 0.949), because the
overlay CONTAINS the channel. The most common false positive on the corpus,
and three things meant to catch it could not: the colour-angle demotion needs
both panels chromatic and abstains on the grey one; `_overlay_split` returns
None for an achromatic panel; `channel_merge.measure` runs only inside the
paid screen and correlates over the whole warped overlap, where this pair
reads 0.44 (inside the inlier box, 0.98).

- `image_forensics/channel_overlay.py` (NEW, in `FINGERPRINT_FILES`):
  on every tier-3 and tier-4 pair, roles from the whole panels (grey vs
  colour by chromatic fraction, or one active channel vs several), then the
  SPEARMAN correlation of the single channel against each channel of the
  merge INSIDE THE MATCHED REGION (the inlier box; identity for a hash pair),
  with the merge required to be coloured there -- a grey micrograph embedded
  in a colourful whole figure (jvi Fig 10C vs Fig 7) abstains by name
  rather than reading as a merge. Rank, not Pearson: a merge is re-encoded
  and contrast-stretched, and the LAMP-1 pair of `j.cell.2021.08.002` reads
  0.77 by rank against 0.45 by Pearson. Tri-state, recorded on every pair as
  `match_stats.channel_overlay` (tier 3: group-level `channel_overlay`).
- `image_analysis`: `_CHANNEL_OVERLAY_MIN_R = 0.70`. A same-figure pair over
  the floor (same parent, or one shared figure label) becomes the
  `channel_overlay_reshow` context kind, evidence False, sentence naming the
  channel and the r; ordered after the chart demotion and before the
  sliver/chrome/grain rules, which cannot speak to a whole-panel re-show
  carrying full grain. A cross-figure pair over the floor STAYS evidence,
  tagged `channel_overlay_cross_figure`, says so in its sentence, and
  `triage_rank` sorts it with the lookalikes -- a grey field recoloured into
  another figure's merge is a real class.
- MEASURED on the current output of the embargoed 2026-09 corpus without a re-sweep
  (`scripts/channel_overlay_audit.py`, stored affines + retained panels):
  2,683 two-panel evidence groups; 224 measure as a single channel beside a
  merge, 2,271 abstain for no asymmetry, 11 abstain because the matched
  region of the "colour" panel is grey. Of the 224, rank r >= 0.70 holds for
  201 (>= 0.90: 133); **196 sit in one figure and would be demoted** (77
  tier-4 and 49 hash single-vs-multi, 46 tier-4 and 24 hash grey-vs-colour),
  5 cross-figure would be tagged, 23 fall under the floor. jvi IMGDUP-9
  measures 0.95 (green), `elife.62155` 0.85, `j.cell.2021.08.002` 0.77.
- RECALL, re-swept on scratch copies (never the corpus). Masliah subset
  (203 papers, PubPeer labels) against the 2026-09-12 scorecard: figure-level
  recall UNCHANGED at 5 of 30; paper-level 18 -> 15 of 43, and all three are
  fires on a figure PubPeer did not name -- one of them this demotion
  (`brainres.2014.10.013` Fig 2, alleged Fig 5), two the 1.57.0 chart
  demotion measured for the first time here; fire rate 29.5% -> 25.6%, the
  transformed-match tier under the 20% alarm for the first time (27 -> 19
  papers). None of the 12 demoted groups sits on an alleged figure.
  Reviewed-581 negatives (`docs/datasets/reviews.md`): contained mode 355 of
  1,953 labelled false-positive pairs still fire against 371 under R2
  (81.8% suppressed, was 81.0%), exact 203 against 214; the one true issue
  (`acsinfecdis.5c00088`) still fires. Only 12 labelled pairs became
  `channel_overlay_reshow`: the labelled set was drawn from a gutter sweep
  and most of its overlay pairs were already withheld by later gates; the
  196 on the live corpus is the number that matters to the queue.
- Exhibits: a measured block is appended to the control sentence, so
  `elife.62155` no longer reads "nothing coherent inside them is the same"
  about a green channel that is plainly inside the merge beside it.
  `duplication_review_figure` and `image_review.CONTEXT_KINDS` know the new
  kind; the webapp's kind dropdown is data-driven and needs nothing.
- Untouched on purpose: `channel_merge.py` (its `code_sha` is a screening
  stamp), the screening prompts and schema. The screen's `same_field_merge`
  relationship is a reading of labels and captions; this is a statement
  about pixels, upstream of it.

## [1.60.0] — a chapter-numbered figure is one figure (2026-09-14)

MINOR: a detector answer change (`extraction/figures.py` is fingerprinted, so
every earlier sweep reads `stale:fingerprint` -- the same break 1.59.0 made
this morning, nothing re-sweeps by itself). Image package 0.13.0.

- `extraction/figures.py`: a caption opener may carry a chapter-compound
  number -- `Figure 2-7`, `Figure 3-10`, en-dash or hyphen -- and the label
  keeps it. MEASURED 2026-09-14 on the Stiles (UCSD 2013) dissertation, the
  first document of that shape run here: `_parse_caption_block("Figure 2-7
  CCRII ...")` returned `("Figure 2", "7 CCRII ...")`, so all seven chapter-2
  figures were filed under one label, every placement in the figure got the
  wrong caption, and the screening model would have been handed seven
  captions under one name.
- `image_forensics/figure_context.py`: `figure_key("Figure 2-7")` is
  `Figure 2-7` (was `Figure 2`). In-text mentions are read PER DOCUMENT:
  `Figures 2-4` in a journal paper is still a range, `Figure 2-7` in a
  chapter-numbered document is one figure, and the document decides through
  its own captions (`uses_compound_numbers`, threaded as
  `extract_mentions(compound_numbers=)`). Under the journal reading a range
  end may now be more than one digit (`Figures 2-10` read as 2 and 1 before).
- `image_forensics/pmc_figures.py`: `normalise_label` agrees (`Figure 2-7`,
  `Figure 2-7A`), so the figure-level joins line up on such labels.
- `extraction/figures.py`: a List of Figures page is refused by name.
  `is_contents_page` (two caption openers AND two dot-leader page-number
  lines) makes `find_captions_in_blocks` return nothing there, and
  `extract_figures` names the pages in a warning. MEASURED on the same
  thesis: pages 11-12 yielded 27 caption-shaped entries, `figures.json`
  held 55 figures for 28 labels, and `resolve_captions` (first hit per
  key, pages in order) served the contents line -- title, leaders, page
  number -- for every figure; now 28 of 28, all `crop_confidence: high`.
- `image_forensics/figure_context.py`: the mention scan skips any sentence
  that overlaps a contents LINE (the splitter cuts `Figure 2-6. RAP ...
  48` at the label, so the fragments carry no leaders themselves).

---

## [1.59.0] — a page of 300,000 paths no longer hangs the harvest; stale exhibits go; the sweep id names rendered regions (2026-09-14)

MINOR: a detector answer change (`extraction/figures.py` is fingerprinted),
so every earlier sweep reads `stale:fingerprint`. Image package 0.12.0.
Nothing re-sweeps by itself; the 3,032 results on the embargoed 2026-09 corpus stand
until a re-sweep is decided.

- `extraction/figures.py`: four papers of the embargoed 2026-09 corpus
  (`10.1073--pnas.2317690121`, `10.1016--j.cell.2016.10.019`,
  `10.1016--j.cell.2021.11.022`, `10.1016--j.immuni.2019.07.007`) timed out
  at 1,800 s in three consecutive sweeps, deterministically, before
  `panel_index.json` was written. faulthandler stacks on a scratch copy all
  sat in `_figure_region`. Cause: pnas p5 carries 299,465 vector paths;
  above `_MAX_PRIMITIVES` (1,500) `_page_ink` skipped the quadratic
  clustering -- correctly -- and handed the RAW primitives on, so every one
  of them entered the growth pool of `_figure_region`, which is quadratic
  too and ran once per seed. A guard that protects one loop by feeding the
  next. Now: above the cap the primitives are coalesced onto a grid of
  `_DENSE_CELL` (24-point) cells first, one rectangle per occupied cell,
  which bounds the pool by the page area (≤ 858 on US letter) and lets the
  clustering run on the result; and the growth loop's `list.remove` is
  replaced by a per-pass rebuild with identical decisions (pinned against
  the original on 200 random pools). pnas: 1,800 s → 40 s, 51 panels,
  `panel_index.json` written. On a page under the cap nothing changes.
- `image_forensics/review_media.py`: `render_review_media` unlinks every
  `group*.png` in `panels/review/` that the manifest it is writing does not
  reference, and records them under `stale_exhibits_removed`.
  `retain._drop_stale` removed the old manifest but left its exhibits, and a
  later run's `group01` is a different pair than the last run's: 5 of 32
  exhibits in a 10-paper sample were from two sweeps back, and one of them
  had a reader judging line graphs when the current finding was a pair of
  western blots. Videos and `labels.json` are untouched.
- `image_forensics/sweep.py`: `default_sweep_id` now takes
  `rendered_regions` and appends `_regions`. It was in `retain.STAMP_FLAGS`
  (the resume key) but not in the id (the resume directory), so two
  same-day sweeps differing only in that flag shared a directory and the
  resumed one refused 617 papers whose stamps carried the other value.
  `tests/test_sweep_id_covers_stamp_flags.py` now requires every
  `STAMP_FLAGS` entry to either move the id or be listed with its reason.

## [1.58.3] — kind counts on the image queue, and PDF zoom on the image item page (2026-09-14)

PATCH, workbench UI only. The image-queue **kind** dropdown now shows per-kind
counts in parentheses, the same facet shape and before-filter contract as
**Image type**. The image-item PDF pane gets the same − / fit / + overlay the
paper page already had; zoom is buttons-only there because `-` / `=` / `0`
already zoom the comparator.

## [1.58.2] — say in `image_corpus.py` that keypoint_mode does not reach the cross-paper pass (2026-09-13)

PATCH, docs only. The module docstring now states that the corpus sweep's
descriptors are plain SIFT under `FEATURE_VERSION` and its matching is the
plain 2-NN ratio test in every `keypoint_mode`, and why (the cache is keyed
on that constant, and the mode is worth one paper on real figures, which
does not buy a corpus-wide recompute). The last open item of the 1.51.0
plan; nothing in the output changes. Image package 0.11.2.

## [1.58.1] — BioFors CSTD gets its first measured number: a seam localiser, not a screen (2026-09-13)

PATCH and not MINOR deliberately: `blot_seam` is an instrument with **no
production consumer**. No tier reads it, it is outside
`retain.FINGERPRINT_FILES`, and no paper's findings move. Two reviews across
this boundary are comparable.

**BioFors CSTD stops being `unsupported`.** 181 annotated cut/sharp-transition
positives on real published blots had never been examined by anything here,
because every detection tier compares two things and a lane cut out of a
membrane has no duplicate source. Full numbers, every null, and the four things
the measurement corrected: `docs/datasets/blot-seam-cstd-2026-09-13.md`.

**The frequency descriptor field is DECLINED for cut blots.** `blot_frequency`
keys on generative-upsampler lattices; on CSTD it scores image-level AUC 0.498
(patch 32) / 0.573 (patch 24) and localises 20.1% against an **18.5%
random-patch null** — a 1.09x lift. Recorded like TruFor and the Cicconet
embedding. Its Step A verdict for *synthetic* blots is unchanged; a synthesis
detector is not a scalpel detector, and the WIFS 2024 authors measured the same
asymmetry from the other side (their localiser loses to TruFor on the
hand-edited GIMP arm).

**New `image_forensics/blot_seam.py`** (ours, from the geometry of the ground
truth, 16 tests). Scans candidate seam LINES, not patches — every one of CSTD's
595 boxes is smaller than one `blot_frequency` patch, median min side 8 px, 70%
taller than wide. Three measurements per line (`intensity_step`, `noise_step`,
`coherence`), the panel as its own control, refusals BY NAME. `coherence` — does
the step hold one sign down the whole line — is load-bearing and has its own
test: a band edge and a cut of identical contrast in one panel, and the cut must
win, because without it this fires on every lane boundary in the corpus.

**Measured, axis `vertical`, margin 24 px:** top seam localises an annotated
manipulation **64/179 = 35.8% against an 8.9% null (4.0x)**; top-2 46.9% vs
16.8%. Image-level AUC 0.625. **Held out** -- margin re-chosen on half the
papers and scored on the other half, split by PAPER, eight splits -- the lift
is **median 3.01x (range 1.18-7.40x)**, so the effect survives validation and
the fitted 4.0x was optimistic by about a quarter. **3x is the number to
quote.** The fit halves chose 16, 24 and 32 on different splits and the
full-data curve is flat across them, so the constant's exact value is not
load-bearing -- it only has to clear the crop edge. 179/181 positives and 1,477/1,534 negatives
scored, the rest refusing by name. **This licenses a reviewer-facing localiser
on a panel already under suspicion, and NOT a screen** — 0.625 wired
corpus-wide is mostly noise, and the task negatives are not asserted clean, so
the true specificity is unknown from this set.

Four corrections the measurement forced, all in the doc:

* **The horizontal axis destroyed the metric.** 68.0% localised looked like
  recall against a **51.4% null** (a full-width box on a 348x58 strip hits
  trivially); vertical-only the null is 8.9%.
* **56% of top seams were reading the crop edge**, not the figure — a panel is
  a crop, and a page-background margin beside a membrane is a perfectly
  coherent full-height step. Hence `DEFAULT_MARGIN_PX = 24`, chosen on a sweep
  against its own null at each margin, then **held out** on a by-paper split
  rather than left fitted on its own report.
* **Raw component AUCs read 0.42-0.48, below chance, from a confound**: a raw
  step carries the panel's own contrast, so comparing it across panels measures
  how busy a strip is. `SeamField.component_z()` exists so nothing repeats that.
* **JPEG blocking is not the confound this was built for.** It quantises each
  8x8 block independently, so the step's sign flips between block rows and
  coherence averages it away; the grid-aligned share sits at the 1/8 chance
  rate across heights 24-128 and qualities 10-75. `grid_aligned_fraction`
  stays a check, never a correction.

Note the interaction: before the margin, the best single component (0.558) beat
the declared combination (0.543), which by the pre-declared rule condemned the
weighting. After the furniture was removed the combination leads (0.625 vs
0.606). The rule was right; what it caught was the furniture.

Also `scripts/blot_seam_cstd_score.py` — four disjoint counts and a null beside
every rate, the same instrument as `biofors_idd_score.py`.

## [1.58.0] — the panel typer was never running, and the type call is now measured per class (2026-09-12)

Dan asked whether we can reliably tell an image, a blot and a graph apart. The
answer had a prerequisite nobody had checked: **the only mechanism that can
type a panel had never run on a production corpus.**

- **`auto` could not find an installed model.** `resolve_weights_path` consults
  only `METASCIENCE_PANEL_DETECTOR_ONNX`, which is unset on this machine, so
  `auto` resolved to `gutter` for all of the embargoed 2026-09 corpus — **103,243
  panels, zero typed** — while BOTH exported models sat in the directory the
  docs tell the operator to use. The low-texture routing gate and the
  `chart_template` demotion were structurally inert, and the only symptom was a
  review queue that was ~90% charts. `image_forensics/model_store.py` now
  discovers a model (env var or flag → `panel_detector.onnx` → a lone `.onnx`)
  and **refuses by name** when several are present with no canonical one: the
  4-class and 5-class exports are different classifiers, and picking one
  silently would stamp runs with a model nobody chose. It sits outside
  `retain.FINGERPRINT_FILES` because finding a path changes no answer; callers
  pass what it finds as the explicit path, so the resolved mode and the weights
  sha256 remain the stamp flags.
- **A run now records why it typed or didn't**: `sweep.json` carries
  `panel_detector_resolution`, and the image scorecard carries `panel_typing`,
  a tri-state that raises a NAMED ALARM for "the stamp says learned and no
  panel carries a type". Previously the reason was one log line nobody kept.
- **The per-class measurement that `panel_detector_weights.md` said was owed.**
  `evaluate_figure` keeps `(annotated, predicted, iou, confidence, min_side)`
  per matched box; `typing_report` gives the confusion matrix, per-class
  precision/recall/F1, the chart-vs-image binary, `P(gt=Blots | pred=Graphs)`
  and a confidence curve. On panels600 (own test split, 2,124 typed boxes) the
  5-class export types `Graphs` at **P 865/867 = 0.998, R 0.989**, with
  `P(pred chart | annotated image)` = **2/1,249 = 0.0016** and **0 of 36 blots
  typed `Graphs`**. Graphs precision is FLAT in confidence (0.998 at every τ
  from 0.4 to 0.8), so the errors are confident ones and a confidence threshold
  was NOT added.
- **Off-split, on data the model has never seen** (`panel-benchmark
  --composites`): 993 real BioFors panels in our layouts — **zero chart/image
  confusions in either direction, 0 of 256 blots typed `Graphs`**, clean in all
  five layout families. The drawn charts make chart PRECISION weak evidence
  there; the blot direction is the strong half.
- **The 5-class export is canonical**, decided on a rule fixed before the run.
  The rule tied (two image-typed-chart errors each); it broke on blots typed
  `Graphs` (0/36 vs 1/36) and on the 4-class having nowhere to put 213 `Body
  Imaging` annotations, which land in `Microscopy` and take its precision 0.969
  → 0.804. Its lower raw 5-way agreement (0.874 vs 0.955) is the missing class
  behaving correctly and being scored as disagreement — the binary is what the
  gates ask.
- **What is still NOT established, and the docs now say so:** the blot side.
  Only **36 of 804** annotated blots reach the type call on panels600, because
  the 100 px side gate removes 93.9% of them (median side 26 px) first. That is
  a figure-scale problem, not a classification one, and `composites` cannot
  measure it (one panel there is under the gate).
- **Human review decisions are frozen and joinable.** `image-reviews-export`
  writes each standing decision beside the member uids, parent streams and
  sweep stamp it was recorded against; `image-benchmark --reviews-from` joins on
  CONTENT, never on `IMGDUP-n` (an index that re-points on every detector
  change). MEASURED: 1,980 standing decisions, 1,980 joined, 0 unjoinable — and
  the first precision this corpus has ever had, **1/1,980 overall, with
  `transformed_match` 0/1,857 against `near_duplicate_phash` 1/123**. Parent-key
  matches are counted and never scored: the 1,980 labelled groups reduce to 923
  parent sets, and scoring by parent key would attach Dan's verdicts to 1,842
  groups he never opened.
- **An embargoed corpus can finish reconciling** (v1.57.0's fix) and
  `python -m <pkg>.cli` is no longer a silent no-op — it exited 0 doing nothing
  and cost three benchmark runs, the same trap already recorded for
  `fetchpdf_grey.cli`.

## [1.57.0] — a typed chart pair is context, filter-wide review, and an embargoed corpus can finish reconciling (2026-09-12)

- **`chart_template`: a tier-4 match with ONE panel typed `Graphs` is demoted
  to context.** Dan hand-reviewed all 2,031 candidates of the embargoed 2026-09 corpus:
  ~90% were charts, graphs and graphics, none was a real duplication, and his
  ruling was that chart duplications are rare enough that a lower detection
  threshold for them costs little. So the rule is deliberately aggressive --
  one typed chart is enough, because a chart aligned against anything is
  aligning on axes, legends and plot furniture. A DEMOTION, not a withholding:
  the group stays in the record and out of `n_duplicate_groups`, so a
  duplicated graph is still detected and still findable. This overrules the
  policy sentence in `docs/datasets/rsiid.md`, which is now marked superseded
  rather than left to contradict it.
  **Inert under the default gutter splitter**, which writes no `panel_type` at
  all — pinned by its own test, because that inertness is why this corpus had
  to be reviewed by hand. Owed: `Graphs` per-class precision on panels600, and
  then the decision about defaulting the learned typer for sweeps.
- **Filter-wide review decisions** (`review_filter`, `POST /api/images/bulk`,
  and a reason selector in the queue). The per-page action covered the 50
  loaded rows; measured on this run, ~1,944 candidates were reviewed by hand
  and **58 decisions persisted**. Each decision saves against its own run
  through the durable outbox. It refuses rather than labelling a partial set
  (above `BULK_REVIEW_MAX`, or when `expected_total` no longer matches), and
  **skips any item that already carries a decision** — a "these are all charts"
  sweep must not overwrite a `true_issue` recorded by hand. The reason
  (`chart_or_graph`, `channel_overlay`, `caption_disclosed_zoom`) rides on the
  event as `bulk_reason` beside the generic `false_positive` decision.
- **An embargoed corpus can finish its analysis run.** `image-screen`
  finalization calls `history_publication.refresh`, the embargo raised, and the
  whole run died at its last step — after every model call was paid for and
  every judgment written, leaving the reconciliation scope pending. The embargo
  refuses publication, not analysis: `reconcile_paper`/`reconcile_project` now
  record a NAMED refusal in the report and the progress stream and finish. The
  guard itself is unchanged and still hard at the publication boundary.
- **Verified on the corpus**: with the v1.55.1 gate fix, one item screened
  grok-as-screen and grok-as-confirm returned `validated: true` (first attempt
  failed on image delivery, the bounded retry succeeded). Before the fix every
  Grok launch died at the init event, 62 of 62.

## [1.56.0] — the pair-screen validator stops enforcing rules no prompt states (2026-09-12)

Luna validated **52 of 142** screens on the embargoed 2026-09 corpus (36.6%). The
failures were measured against the saved judgments, not guessed: the ledger
keeps every answer dict, so the rules could be rescored offline at zero cost
(`metascience-observatory-image-analysis/scripts/rescore_screen_rules.py`).
Three rules did most of the damage, and each was a rule the validator enforced
and no prompt stated.

- **The channel and relationship enums were never one vocabulary.**
  `channel_assessment` answers "is a pseudocolour merge the explanation?";
  `relationship_assessment` answers "which relationship holds?". They overlap
  in two tokens, and equality was required on both. 22 screens were refused for
  saying "not a merge" (channel `distinct_claims`) beside "not actually the same
  field" (relationship `not_matching`) — 19 of them exactly that pair, every one
  with a proposed *innocuous* decision. `CHANNEL_BINDS` now frees the token
  whose two meanings diverge and **leaves `same_field_merge` binding**, because
  there the two meanings coincide: a match called a disclosed merge in one field
  and overview/detail in the other is still two readings of one pair and still
  does not clear it.
- **A printed label that is not a bare subletter is a label, not an absence.**
  `normalise_subletter` returns None for `ii`, `2a`, `A*01:01`, `R444C`, `A₂`,
  and the `subfigure_raw` check compared the model's answer against that None —
  demanding it report NO LABEL for a panel it could plainly see labelled. The
  `subpanels` branch already carried the right fallback; the two branches now
  share one `expected_label`, which is the drift that produced this. 17 of 21
  measured label mismatches were this shape; `(a)` → `a` is still required.
- **Rescored: 36.6% → 52.1% validated, +22 screens, zero model calls.** What
  still fails is dominated by the quote rules (43) and by delivery/extraction
  (24, including 7 screens whose answer was empty — those already take the retry
  path), plus the 33 `innocuous` + `distinct_claims` refusals below.
- **`innocuous` + relationship `distinct_claims` stays refused** — it is the
  ISSUE relationship, so clearing a pair the screen itself called distinct
  claims is self-contradictory. But all 33 refusals had
  `benign_explanation_status: supported`, i.e. the model had already concluded
  the reuse was legitimate and then labelled it with the issue token, because
  `image_relationship_screening.md` asked one enum to answer both "what do A and
  B claim to represent?" and "what is the benign explanation?". The prompt now
  separates those, the enum field names only the relationship that holds, and
  the error message names what to write instead. **Prompt-side, so unmeasurable
  without model calls — no claim is made for it here.**
- `image_screening.md` states the label rule; `image_channel_screening.md`
  states that the two vocabularies need not match token-for-token and what
  `not_applicable` is for.

Pair-screen prompt and validator both changed, so v6 stamps do not compare
across this boundary.

## [1.55.1] — the init-event MCP gate stops aborting launches that asked for no server (2026-09-12)

**Every Grok image escalation on the embargoed 2026-09 corpus failed — 62 of 62 — and
the error blamed the wrong thing.** Commit `01a4de6b` (the standalone image
package extraction) made image screening pass `forensic_mcp=False`, so the Grok
config was written with an empty `[mcp]` table; the init-event gate still
*required* `forensic_metascience` in `mcp_servers` and killed the child before
its first turn. Codex was exempt only because its stream lists no servers at all
and returns early, which is the sole reason Luna screened at all. **Claude was
broken the same way and silently** — `--mcp-config {}` with
`--strict-mcp-config` declares nothing either.

- `Invocation.forensic_mcp` records whether a launch actually asked for the
  server, stamped by the builder rather than inferred from argv: the absence of
  a flag cannot distinguish "not asked for" from "asked for and lost". For
  Claude the stamp is the AND of the caller's intent and what the MCP config
  actually declares, because the launch — not the intent — is what the gate sees.
- When it is False, `mcp_discovery_from_init` **inverts** the contract instead of
  disabling it: `mcp_servers` must be empty, and any server present, foreign or
  ours, is still a hard abort. Image screening's guarantee is isolation, not
  presence; demanding presence is what aborted the run.
- The "no forensic_metascience server" message no longer asserts a folder-trust
  or cwd cause it cannot distinguish from a config written without the server.
  That misdirection sent an investigation after the wrong thing for 62 papers.
- `tests/test_image_mcp_gate.py` (image package) pins both directions on both
  backends, plus the regression guard that a *forensic* launch with an empty
  list still aborts. The gap was that no test ever ran the image builder through
  the gate.

## [Unreleased] -- human review decisions as a negative set

- `image_forensics/review_negatives.py` + `image-benchmark --reviews-from`:
  the frozen workbench decisions (`review_fixture_*.jsonl`) are scored as
  NEGATIVES by durable pair identity -- parent stream + crop rectangle, with
  gutter `-segN` crops recomputed from the retained parent PNG -- so they
  survive the splitter change that renames every crop uid. Two match modes
  (`exact` IoU >= 0.5; `contained`, the reviewer saw a superset), and every
  labelled pair lands in one named outcome. MEASURED on a scratch copy of the
  581 reviewed embargoed-corpus papers (`docs/datasets/reviews.md`; the corpus is
  embargoed, so counts only): the native gutter arm re-finds 1,944 of 1,954
  labelled false-positive pairs; the shipped learned defaults still fire on
  371 (81.0% suppressed; 89.0% in exact mode), keep the one confirmed
  positive, and the Graphs gate is the largest suppressor (722 pairs).
  Authorship note: the module, wiring and tests first reached the branch
  inside a peer's commit (a42c605d) that staged the whole tree.
- `workbench/image_cleanup.disk_plan` preserves `review_fixture_*.jsonl`; it
  listed every non-pubpeer .jsonl under `.image_track` for deletion. The
  `ai_screening.json` / `furniture.json` question is filed in
  `docs/DESIGN_DECISIONS.md`.

## [1.55.0] — the low-texture routing refuses detector-typed charts, and unsplit figures fall back to the gutters (2026-09-12)

MINOR: a detector answer change (three fingerprinted files), so every earlier
sweep reads `stale:fingerprint`. Image package 0.8.0.

- `image_analysis`: a low-texture panel the learned detector typed `Graphs`
  is no longer routed to the keypoint tier; it is withheld from the
  perceptual tiers under its own name, `low_texture_chart_panel`, and the
  result's `low_texture_keypoints` block counts `n_chart_panels_withheld`
  beside `n_panels_routed`. Measured basis (Masliah scratch subset,
  2026-09-12, `docs/datasets/rsiid.md`): every counted low-texture keypoint
  group drawn was a copied chart legend or shared plot template, and 44 of
  the 100 panels involved were typed Graphs. Gutter mode and untyped panels
  are unchanged; the routing flag off is unchanged.
- `panels._segment_one`: a figure the detector saw several boxes in but
  that stays ONE panel (refused split, below the montage gate, boxes too
  small) now carries the MAJORITY class of its detections
  (`detection["type_source"] = "majority_of_detections"`) instead of no
  class -- 28 of those 100 panels were whole chart figures left untyped.
  A split parent still keeps `panel_type=None`.
- `panels._segment_one`: a figure the detector saw >= 2 boxes in but did
  not split (every box under the 100-px gate on a small render, a refused
  split, one big box among small ones) is cut by the gutter splitter
  instead; crops carry `segmenter="gutter"` and are typed from the detector
  boxes inside them (a crop is a chart only when every box in it is one),
  the parent keeps its majority class, `detection.fallback` says why, and
  the `panel_detector` summary counts `n_gutter_fallbacks` /
  `n_gutter_fallback_crops`. Measured basis: a 778x327 PMC render with 34
  boxes all under the gate stayed one panel and, as `pmc_render`, was
  withheld by provenance while the gutter splitter had compared its strips.
- All three files are in `retain.FINGERPRINT_FILES`, so every earlier sweep
  reads `stale:fingerprint`. MEASURED (`docs/datasets/rsiid.md`): RSIID
  40/family with the gate is 80/440 identical per family to ungated, 0/200
  false positives, 782 typed-chart panels withheld (indicative: a peer
  commit landed mid-run). Masliah scratch subset, shipped defaults: gate
  alone 14/43 papers, 4/30 figures, fire 26.4% unchanged, counted
  low-texture groups 6 -> 1; gate + fallback 18/43, 5/30, fire 29.5%,
  fallback on 35 figures in 20 papers, transformed tier 51 groups on 27
  papers (format alarm, 20.9% vs the 20% line; the one figure-level gain
  is the alleged figure but the drawn pair is a chart template the match
  control already ranks `lookalike`), p50 6.2 s. The gutter 2x2's
  "plain + low-texture 21/43" is chart templates landing on alleged
  figures at figure granularity, not recall -- diffed paper by paper in
  the doc.

## [1.54.1] — correction: the Masliah gain is the low-texture lever, not an interaction (2026-09-12)

PATCH, docs only. The 1.54.0 entry below concluded from three cells that the
+8 papers came from RootSIFT + G2NN acting on the panels the low-texture
routing admits. The fourth cell, measured minutes later on the same subset,
same gutter segmentation, same plain baseline, says otherwise:
plain + `low_texture_keypoints` = 21 of 43 papers, 7 of 30 figures, 28.7%
transformed_match fire rate (135 groups), the SAME three papers gained and
the same one lost as `rootsift_g2nn` + low-texture (22 / 7 / 31.8%, 165
groups). So on real papers the descriptor mode adds one paper and three
points of fire rate on top of the routing lever, and the +7 belongs to
`low_texture_keypoints` under gutter segmentation. The concurrent session's
13 of 43 for the same lever was under LEARNED segmentation, a different
panel population, which is why the two numbers disagree. The BioFors and
pair-level results in 1.54.0 stand. The plain + low-texture sweep's last
~35 s overlapped commit aa36e11 (the Graphs gate), which cannot act under
gutter segmentation because gutter crops carry no panel type, so the cell is
not contaminated.

## [1.54.0] — third keypoint mode `rootsift_g2nn`, and the clean 2x2 on real papers (2026-09-12)

MINOR: a new opt-in matcher configuration. Defaults unchanged (`plain`).
Image package 0.6.0 -> 0.7.0.

- `keypoint_mode` gains `rootsift_g2nn`: RootSIFT descriptors + G2NN
  selection on the RAW gray, no equalisation. Child parser, both CLI verbs and
  `dataset-run` accept it; `heq_rootsift_g2nn` stays available and is
  documented as harmful on assembled figures.
- The Masliah-subset comparison in 1.53.0 was confounded (the plain arm ran
  before `low_texture_keypoints` became a default, the mode arms after). Clean
  re-measurement, 203 papers / 129 ran, gutter segmentation, every flag
  explicit, one plain scorecard as baseline, PubPeer paper-level hits of 43
  examined positives / figure-level of 30 / `transformed_match` fire rate:
  plain 14 / 5 / 17.1%; `rootsift_g2nn` 14 / 5 / 14.7% (gained 0, lost 0);
  `heq_rootsift_g2nn` 9 / 3 / 11.6% (lost 2 -- equalisation confirmed as the
  loss); `rootsift_g2nn` + `low_texture_keypoints` 22 / 7 / 31.8% (gained 3,
  lost 1, FORMAT ALARM, 140 of 165 groups tagged `low_texture_pair`). The
  concurrent session's learned + plain + low-texture sweep on the same subset
  gives 13 / 4 / 26.4%, so the low-texture lever alone adds nothing and the
  descriptors alone add nothing: the +8 papers are the INTERACTION -- RootSIFT +
  G2NN finding pairs among the blot-like panels the routing lets in, which is
  the same population BioFors measured (blot recall at 1% FPR 0.12 -> 0.31
  without equalisation). The fire-rate cost is charts entering through the
  same routing; the chart gate on that block is the next measurement.
- BioFors EDD for `rootsift_g2nn` (raw inlier AUC / recall at 1% FPR /
  full-gate found of positives at FP of 3,000 negatives): blot 0.79 / 0.31 /
  5 of 523 at 0; microscopy 0.93 / 0.65 / 182 of 395 at 4. CLAHE (clip 2,
  8x8) was measured and sat between plain and global equalisation on both sets.
- Eight-way factor grid on the real pairs plain matched: RootSIFT + G2NN kept
  or raised inliers on every pair (64 -> 80, 60 -> 77, 64 -> 80, 51 -> 59);
  global equalisation collapsed the candidate matches (108 -> 12 good).

## [1.53.0] — keypoint_mode default back to plain (2026-09-11)

- The real-paper set overrules the synthetic ones: on the 203-paper Masliah
  scratch subset `heq_rootsift_g2nn` LOST paper-level recall 14 -> 7 of 43
  and figure-level 5 -> 2 of 30 while gaining 66 -> 93 of 440 on RSIID and
  0.12 -> 0.51 blot recall on BioFors. **That sweep-level comparison is
  CONFOUNDED**: the plain arm ran before 44f8050 (low-texture routing off)
  and the mode arm after it (routing on), so it carries two levers; a clean
  pair is being re-measured. The PAIR-level diagnosis stands on its own
  (measured directly on the lost panels): `cv2.equalizeHist` doubles the
  keypoint count on composite JPEG figures and the true correspondences lose
  their nearest-neighbour margin, while RootSIFT + G2NN WITHOUT equalisation
  raised inliers on every pair walked. `keypoint_mode` defaults to `plain`
  again (opt-in flag kept); `panel_detector auto`, `low_texture_keypoints`
  and segmentation-on stay pending their own clean real-paper column.
  Image package 0.6.0.
- Real-paper column for the shipped defaults (Masliah scratch subset, sweep
  `2026-09-11_E_defaults_v153`, `docs/datasets/rsiid.md`): paper-level 13 of
  43 and figure-level 4 of 30, identical bucket-for-bucket to the learned arm
  without low-texture routing (gutter: 14 and 5); fire rate 26.4% vs 24.0%;
  per-paper cost unchanged (p50 7.0 s vs 7.5 s). Of the 50 groups tagged
  `low_texture_pair`, 44 land in the suppressed context classes and 6 count,
  and every one drawn is a copied chart legend or shared plot template --
  the low-texture panels on real papers are charts, not blots. Next lever
  named in the doc: do not route detector-typed `Graphs` (and attach the
  majority class to unsplit figures so the untyped half can be gated too).

## [1.52.0] — recall-first defaults for the image track (2026-09-11)

- Dan's policy: bias toward recall, suppress only the obvious classes
  deterministically. Defaults change accordingly; every one is a stamp flag,
  so earlier sweeps read `stale:flags` rather than silently comparable:
  `segment_montages` on in `analyze`/`pipeline.run` (was off on the paid
  path); `panel_detector` `auto` (learned when a model is configured, else
  gutter, said in the log; the resolved value is stamped, never "auto");
  `keypoint_mode` `heq_rootsift_g2nn`; `low_texture_keypoints` on. Measured
  on RSIID (40 per family, `docs/datasets/rsiid.md`): learned segmentation
  localizes both duplicated panels in 343/440 vs 24/440; pairs found
  66 -> 80 (low-texture) and 66 -> 93 (keypoint mode) of 440; zero pair-tier
  false positives on 200 negatives in every arm. Per-case cost 1.4 s -> ~5 s.
- `sweep.DEFAULT_JOBS` capped at 6: each child now holds the learned
  detector (~1.3 GB) and the platform's memory guard killed 19-child runs.
- Image package 0.5.0.

## [1.51.0] — opt-in tier-4 keypoint mode (2026-09-11)

MINOR: a new matcher configuration can change which `transformed_match`
groups a paper produces. Off by default; `plain` is byte-identical to 1.50.0.
Image package 0.3.0 -> 0.4.0.

- `analyze_paper_images(keypoint_mode=)`, `--keypoint-mode` on `image-analysis`
  and `image-sweep`, threaded through `run_track`, the child argv, `pipeline.run`
  and the sweep flags; `keypoint_mode` is a STAMP flag (`retain.STAMP_FLAGS`)
  and appends `_kp-<mode>` to the default sweep id, so two sweeps differing
  only in matcher never share a directory or a stamp.
- `heq_rootsift_g2nn` re-implements three textbook steps in front of the
  UNCHANGED similarity RANSAC and the eight Acuna gates: `cv2.equalizeHist` on
  the gray panel before SIFT, RootSIFT descriptors (L1-normalise then square
  root; Arandjelović & Zisserman, CVPR 2012) and G2NN match selection (walk the
  20 nearest neighbours while consecutive distance ratios stay under 0.75, then
  one-to-one by best distance; Amerini et al., IEEE TIFS 2011). ORB-only builds
  run plain and say so in `caveats`.
- MEASURED on BioFors EDD test pairs (every positive plus 3,000 random negatives
  per class, the same split used for the TruFor and Cicconet surveys). Raw
  inlier count as the score, recall at 1% FPR: blot 0.12 -> 0.51 (AUC 0.74 ->
  0.88), microscopy 0.61 -> 0.88 (AUC 0.93 -> 0.96). Through the full
  eight-gate matcher at `_MIN_INLIERS = 30`: blot 4 -> 28 of 523 positives at 0
  false positives on 3,000 negatives; microscopy 152 -> 210 of 395 at 2 -> 6
  false positives. Equalisation carried most of the blot gain.
- Surveyed from the ELIS suite's AGPL-3.0 `provenance-analysis` service. No
  code was copied. Its CBIR candidate search, recursive expansion and networkx
  provenance graph duplicate our exhaustive cross-paper sweep; its
  `findFundamentalMat` USAC_MAGSAC verification was measured in place of our
  `estimateAffinePartial2D` RANSAC and lost (blot AUC 0.73 vs 0.88), so it is
  not offered. Same day, two sibling repos were measured and declined
  outright: TruFor (CVPR 2023 splice localiser; AUC 0.47-0.55 on BioFors
  spliced blots, 11% fire rate on Masliah panels that outlines montage layout)
  and teddykoker's Cicconet-2018 siamese embedding (below pHash and SIFT at
  every usable FPR; 34-98% FPR at its own threshold).
- NOT yet measured, and what gates a default change: `transformed_match` fire
  rate on the Masliah PubPeer scorecard and pair recall on the composites set
  with the mode on. The low-texture blot exclusion is untouched; equalisation
  is the lever that could let that channel in, and that is a separate decision.
- Tests: `tests/test_keypoint_mode_wiring.py` pins the flag end to end and the
  matcher under both modes, including a 12%-contrast copy that plain SIFT
  cannot clear and the new mode matches.

## Unreleased — segmentation-sensitive evaluation sets (2026-09-11)

- Recall-first policy (Dan, 2026-09-11): `sibling_phash` groups are tagged, not
  withheld; new opt-in `--low-texture-keypoints` (stamp flag) lets blot-like
  panels into the keypoint tier only, tagged `low_texture_pair` -- RSIID pairs
  found 66 -> 80 of 440 with zero new pair-tier false positives; `image-dataset-run`
  gains `--low-texture-keypoints` and `--keypoint-mode` for A/B runs.
- Add the two panel-box ground truths we lacked, both stored on the data disk
  through `dataset_fetch`: `panels600` (the ELIS panel-extractor's 600-figure
  test set with boxes in five classes) and generated `composites` (BioFors
  panels pasted into figures with known boxes, a known duplicate pair, true
  negatives and one-panel controls, six layout families).
- `metascience image-panel-benchmark` scores the gutter splitter and the learned
  detector against real boxes, by class and by size band; `image-dataset-compose`
  builds the composites; `image-dataset-run` gains `--panel-detector` /
  `--panel-detector-onnx` and scores localization against known boxes;
  `image-benchmark-compare A B` diffs two PubPeer scorecards, refusing different
  labels and marking truncated miss lists as undetermined rather than inventing
  gained papers.
- Measured (docs/datasets/panels600.md): on boxes above the 100-px minimum side
  the learned detector recovers 95.3% and the gutter splitter 22.6%; 53.6% of
  annotated boxes on these small figures (93.9% of Blots) fall under that gate
  and neither splitter can return them. The gate, not the model, bounds recall
  on small figures.
- RSIID test set (Zenodo 15095089, 12,927 cases, CC BY 4.0) fetched by hand,
  MD5-verified, extracted on the data disk; the fetcher gains 7z extraction and
  the provisional adapter is replaced by one validated against the release.
  Compound figures score through the known-boxes path. Measured on 40 cases per
  family (docs/datasets/rsiid.md): both duplicated panels localized in 343 of
  440 inter-panel positives with the learned detector against 24 of 440 with
  gutters; the pair then found in 66 of 440 against 6 of 440; zero pair-tier
  false positives on 360 negatives for both. After splitting, matching is the
  bottleneck: 145 localized positive crops were excluded as low-texture blots.

## [1.50.0] — 2026-09-11

- **Strip-sliced figures can be pasted back together (`--reassemble-tiles`,
  opt-in).** Surveying the ELIS `pdf-image-extraction` tool (SILA; Cardenuto,
  UNICAMP; AGPL-3.0) against our harvest found ONE technique we lacked: it
  reassembles a figure the PDF producer sliced into edge-adjacent strips,
  each strip its own xref. We already DETECTED that shape (`tile_member`)
  and withheld every strip; nothing was rebuilt. On every other axis
  (placement geometry, same-xref reuse, dedup, manifests, timeouts) the
  existing harvest is stronger, so nothing else was taken and no code was
  copied -- the technique is re-implemented (`panels._reassemble_tiles`).
  MEASURED 2026-09-11 over 1,086 corpus PDFs: sliced groups in 51 papers;
  17 are 1980s-90s Masliah page scans (reassembly would yield a scanned
  page, never a panel) and about ten are modern, figure-level slicings --
  Springer 1998, Wiley, Elsevier 2019, MDPI 2023-25. `10.1007--s007020070015`
  (three phase-contrast micrograph figures in 38/38/53 strips of 390x21
  and 797x10 px) harvested as **133 panels, 129 `tiny`, 0 eligible**: the
  strips fell below the tiny gate BEFORE `_classify_tiles` ran, so the
  figures were invisible and the paper read `all_panels_withheld`. With
  the flag it yields three `tile_composite` panels (390x798, 390x798,
  797x530 px) whose pixels are the figures, opened and checked by eye.
  What licenses a paste is the PIXELS, not adjacency: a seam-continuity
  ratio (`_TILE_SEAM_MAX_RATIO`, measured 0.15-0.75 on true slices vs
  1.08 on a stack of distinct blot strips and 1.5-5 on panel grids),
  decided on the median over seams and recorded on every group whether
  or not it is reassembled. Refusals are named and counted
  (`tile_groups_refused` by reason; the MDPI shape -- every strip placed
  twice, one copy clipped -- is `partially_visible_member`, phase 2); a
  group spanning the page width is `tile_composite_full_page` and no
  pixel is touched. NO COVERAGE LOSS: a member's eligibility changes only
  when a composite replaces it. The composite is a new acquisition
  channel OUTSIDE `ORIGINAL_BYTES` -- perceptual tiers only, like a
  `crop_segment`; with `--segment-montages` it is split like any montage.
  `reassemble_tiles` joins `STAMP_FLAGS`; `panels.py`, `image_analysis.py`
  and `image_track.py` changed, so the detector fingerprint moves for
  everyone and every retained sweep reads `stale:detector` -- that is a
  fact, not an instruction to re-run. The detector result carries a
  `tile_reassembly` block (`mode: off` when not asked) so "not
  reassembled" never reads as "nothing to reassemble". Follow-ups the same
  survey measured and did NOT change: 197 of 394 soft-masked large images
  carry an all-opaque mask yet are withheld as `visibility_unresolved`;
  `content_sha256` is not proven to be the raw stream for Flate/CCITT/
  JBIG2/CMYK-JPEG (fetchpdf's `extract_images.py` already checks
  `xref_stream_raw`); discontinuous flush groups stay withheld as today.
  MINOR: a new channel changes which panels are compared. Image package
  0.3.0.

## [1.49.0] — 2026-09-11

- Add an optional LEARNED panel detector to the image package
  (`image_forensics/panel_detector.py`): the ELIS panel-extractor YOLOv5x6
  model (Cardenuto, Moreira, Rocha 2024; 5 classes, mAP@0.5 0.95) run as an
  operator-supplied ONNX file with onnxruntime and our own letterbox / NMS /
  merge -- no GPL code enters the package. `--panel-detector {gutter,learned}`
  on `image-sweep`, `analyze` and the `image_track` child; default `gutter`,
  so nothing changes unless asked. Learned mode without a model REFUSES the
  paper (never silently splits on gutters); the model's sha256 and the
  detector file join the sweep stamp, which marks every earlier sweep stale.
  Crops and typed whole panels carry `panel_type` / `panel_type_confidence` /
  `segmenter`; overlapping crops of one parent are never compared with each
  other; the scorecard gains recall by DETECTED kind. Measured 2026-09-11 on
  40 Masliah montages: splits 33 the gutter splitter split 23 of; 0.35 s per
  figure. Provenance, licence and every measurement:
  `metascience-observatory-image-analysis/docs/panel_detector_weights.md`.
  Compared on a 203-paper Masliah subset (docs/panel_detector_weights.md,
  Phase 3): learned mode does NOT beat the gutter baseline on PubPeer recall
  (10-13 vs 14 of 43 papers) and its first cut tripped the fire-rate alarm
  via pHash on tight sibling crops (47 of 53 groups), so learned crops of one
  parent now skip the pHash tier and use a 1600-pair keypoint budget; the
  default stays `gutter`. No consumer changes an answer from a type yet.
  MINOR: a new detector with new record fields.

## [1.48.0] — 2026-09-11

- Pair image screening v6 repairs relocated supplementary images and next-page
  captions, preserves source-scoped typography, and reads multi-panel crops.
- Add compact context briefs, explicit benign-relationship assessment, colored
  channel comparisons, repairable category errors, and bounded fallback retries.
- Separate failed/unresolved screening from scientific clearance in the workbench;
  preserve cached navigation and bound targeted screening to selected owners.
- Add frozen nonpublishing context/model comparison with raw transcript rescoring.
  Model defaults remain gated on independently checked positive references.

## Unreleased — workbench performance (2026-09-11)

- Replace whole-cache interactive projection rebuilds with indexed project/run
  reads and durable revisions; isolate read, detail, source, media, and thumbnail
  workers. Cache thumbnail PNGs outside shared folders while revalidating sources.
- Render item details independently of queue loading, share decoded comparison
  images with PDF overlays, defer diagnostics/search indexing, and bound detail
  caches with request cancellation. Status polling uses 30 seconds normally and
  5 seconds for pending writes, plus immediate focus/review refresh.
- Isolate production/development builds and ports. Remove hidden legacy image
  filters, add filter reset, remove the queue banner, and show version beside kind.
- Replace queue page buttons with infinite scrolling; arrow keys select rows and
  Enter opens them. Preserve loaded rows on errors and position on back navigation.

## [1.47.3] — 2026-09-11

- Run the local test stack concurrently, calibrate pytest workers by measured
  elapsed time on each machine, and limit native thread pools within each worker.
  Explicit worker/thread settings remain available; tests retain file grouping.

## [1.47.2] — 2026-09-11

- Prioritize queued review writes before routine synchronization and refresh pending
  feedback every 500 ms, with offline backoff and acknowledgment-safe UI updates.

## [1.47.1] — 2026-09-11

- Show image adjudicator-dropdown counts for the entire selected run before
  filtering and pagination, including missing and legacy judgments.

## [1.47.0] — 2026-09-10

- Add optional, versioned image content-support diagnostics with saved-transform
  support, independent masked fitting, scale-aware furniture exclusion, and
  montage-cell views. Original candidates, detector thresholds, review ranking,
  production AI screening inputs and publication eligibility are unchanged.
- Display verified diagnostic overlays on selected workbench items, distinguish
  bounding-box area from pixel agreement, and show the saved disposition clearly.
- Add frozen, non-publishing paired shadow evaluation with per-positive regression
  reporting. New evidence is never adopted by production screening automatically.

## [1.46.0] — 2026-09-10

- Pair screening v5 explicitly assesses channel/merge relationships. Aligned
  grayscale-to-RGB component measurements and derived channel attachments inform
  review without automatically clearing color changes. Clearances require
  observed candidate context and a scoped caption; issues with component matches
  require distinct-claims evidence. Missing/ambiguous evidence stays unresolved.
- Preserve the clone v1 contract. Pair screening input stamps include the new
  measurement code; older pair decisions cannot bypass the revised policy.
- Qualify the shared-grain ranking explanation: a channel and its merge can
  legitimately share pixel-scale grain. Keep archived rankings and detector
  answers intact. Regression coverage includes the reported Figure 2 example.

## [1.45.1] — 2026-09-10

- Image screening finalization reconciles only affected papers, with a durable
  pending scope for interrupted runs. It batches local publication refresh,
  builds the compatibility feed once without rendering media, and leaves full
  report import and project-index regeneration to explicit maintenance.
- Log finalization progress/timing and shared-sync outcomes. An empty explicit
  run selection no longer uploads the entire archive. Scientific screening
  contracts and saved evidence are unchanged.

## [1.45.0] — 2026-09-10

- Give intra-panel clone candidates their own evidence and screening contract:
  two localized regions within one panel are A and B, while the overview and
  full figure remain context. Clone validation no longer demands an unrelated
  independent-panel caption and never accepts `source_alias`.
- Exclude repeated annotation overlays only when their common extreme-tone
  pixels drive the match and the remaining photographic content falls below
  the correlation floor. Preserve pair-v4 screening stamps, immutable history,
  and mixed-policy publication through incremental projection updates.

## [1.44.1] — 2026-09-10

- Project shared image eligibility from saved database judgments, independent
  of local files. Preserve publication revocations when importing older runs.
- Separate foreground detail connections and workers from synchronization and
  source conversion; render hash-verified archived XML and monitor known local
  paths without recursive scans or network access.
- Support an explicit image-result reset with run-identity tombstones and
  reimport guards. Masliah image results were cleared at the user's request;
  original sources and non-image analyses were preserved.

## [1.43.2] — 2026-09-10

- Add explicit retirement of superseded image-run payloads, with verified newer
  replacements, preserved human reviews, immutable scientific headers, and cache
  invalidation. Tiny markers prevent archive synchronization from restoring the
  removed payloads. Original local archives remain intact.

## [1.43.1] — 2026-09-10

- Workbench navigation reads a private SQLite cache through a persistent Python
  service. Neon change synchronization, paginated findings/candidates, separate
  source preparation, verified local artifact mappings and a durable review
  outbox replace normal navigation's CLI and folder-index hot paths.
- Review conflicts remain visible; historical selections and evidence hashes are
  preserved. See [workbench storage](docs/workbench_storage.md) for migration,
  verification, and known import exceptions. Scientific adjudication is unchanged.

## [1.43.0] — 2026-09-10

Treat an identified main PDF as the gold-standard image source and exclude
alternate PMC/publisher renders from duplication candidates. Scope captions to
their source documents, reconcile retained alternate-source matches with a
renumbering-tolerant full-figure registration, and skip deterministic clears
and terminal source-identity blockers during paid screening. Add a local-first,
all-indexed-project repair command and keep cleared aliases in the audit view.

## [1.42.0] — 2026-09-10

Add standalone paper-level copy-paste detection, process-parallel batch execution,
Grok adjudication, version-checked local dataset imports and issue-level benchmarks.
Expose reader coverage and uncached formulas, preserve every candidate and cell,
and index exact adjacent sequences. Cross-file comparisons require unambiguous
column identities. Preserve detector evidence, AI decisions and all source files
separately in portable runs and the workbench. Scoring thresholds remain unchanged.

## [1.41.0] — 2026-09-10

Preserve rendered figure parents and crop identities in the panel index, and
include their keypoint coverage in the eligibility counter. Render-only matches
no longer incorrectly take the zero-coverage refusal path. Archive panel source
PDFs and display archived PDF references in the image viewer. Existing frozen
runs retain their original version and evidence.

## [1.40.1] — 2026-09-09

Recognize fetchpdf's DOI-named image-extraction directories and PMC figure
directories as paper internals. They no longer make corpus discovery skip the
containing paper or enumerate its extracted images as separate papers. Verified
against the batch2 corpus and top-level/nested discovery regression fixtures.

## [1.40.0] — 2026-09-09

Prevent PDF resource and alternate-delivery artifacts from becoming image
matches in future runs. Count renderer-verified occurrences across nested
rectangular clips, canonicalize aliases across pages, and compare only visible
source crops when a PDF hides part of an image. Unsupported visibility remains
an explicit coverage gap. Preserve source parents and diagnostics in the review
index; invalidate detector and cross-paper feature fingerprints.

Deduplicate verified same-paper PDF deliveries using every page's image content,
placements, masks, scientific text and graphics. Record hashes, correspondence
tolerances and the narrow Nature packaging profile. Different scientific labels,
unmatched pages or unresolved compositing prevent automatic equivalence. Existing
archives, human decisions and published results are unchanged.

## [1.39.1] — 2026-09-09

Codex usage windows are identified by their reported duration, including a
weekly primary window with no session gauge. The 97% weekly stop remains active;
a 96% weekly reading no longer causes an indefinite five-hour pause. Prefer the
main Codex bucket when multiple model buckets are returned. Added a frozen,
resumable prompt comparison that holds evidence and model settings fixed.

## [1.39.0] — 2026-09-09

Image confirmation now defaults to Grok 4.6. Grok image-read receipts are verified
from actual image payloads, and lost-prime caption quotation normalization requires
a matching visual reading with document and attachment provenance. Numbered
manuscript captions are joined across lines and pages, and separate caption
pages are delivered as visual context. Attachment validation checks the source
document, figure and repeated placement.

- Preserve image identity and all source placements in a shared, versioned
  evidence packet. Recover crop geometry through the PDF affine transform,
  retain parent boxes, separate main/SI captions, preserve prime labels and
  record unresolved label readings explicitly.
- Supply original panels, marked source pages, full figures and localized
  matches to image screening and both adjudication paths. Verify delivery of
  context images as well as crops; preserve complete screening rationale and
  packet references in the final adjudicator's docket.
- Invalidate screens when source documents, geometry, captions, labels or the
  evidence builder change. Keep detector answers and prior judgments intact.
  Add a replay tool for three saved identity failures and regression tests for
  source collisions, multiple placements, image delivery and rotated geometry.

## [1.38.1] — 2026-09-09

- Add downloadable image-dataset benchmarks with pinned acquisition receipts,
  BioFors/WIFS annotation adapters, per-case deterministic detector execution,
  reproducible sampling, compression/resize challenges, and retained Markdown
  scorecards. Missing datasets and unsupported edit mechanisms remain explicit.
- Document dataset provenance and license evidence. No production detector,
  severity policy, or prompt behavior changes in this benchmark addition.

## [1.38.0] — 2026-09-09

- Preserve execution, paper/component run, and item identities in an immutable
  `.analysis_runs` archive. Image extraction uses isolated workspaces; screening
  and adjudication produce linked revisions. Analyst copy/paste calls retain
  full results and input evidence without adding a mandatory pipeline stage.
- Add Version / run selection to image, copy/paste, and paper review. Saved
  candidates remain browsable independently of current publication policy;
  historical media and human decisions remain scoped to their owning run.
- Add execution, component item, artifact, and item-to-paper database records,
  plus a separate current-publication projection. Import and sync preserve
  historical IDs, report missing evidence, and reject changed sealed content.
- Add `copy-paste`, `history-import`, `history-import-copy`, `history-db-migrate`,
  and `history-sync`; standalone copy/paste supports portable `--run-dir` output.

See [run history](docs/analysis_history.md) for storage, migration, and usage.

## [1.37.0] — Luna/Terra image review (2026-09-09)

- Default mandatory image screening to Codex CLI Luna, escalating uncertain or
  invalid responses to Codex CLI Terra. CLI, standalone module, per-paper pipeline,
  and non-publishing evaluation share the route. Explicit overrides remain available.
- Evaluation resume and summaries distinguish the escalation route, so historical
  Sonnet results cannot be reused or mixed into a Terra evaluation.
- Existing judgments remain historical records; this change does not rerun a corpus.

## [1.36.1] — Live screening feed refresh (2026-09-09)

- Serialize feed builds with screening ledger commits so an active review batch
  does not cause repeated rebuild failures. Revalidate cached findings against
  changed AI decisions immediately; discover new findings in the background.
- Preserve evidence freshness checks and immediate removal of revoked findings.

## [1.36.0] — Independent image pipeline (2026-09-09)

- Full runs enable the independent image pipeline by default alongside the tool
  and science analysts. Detection and mandatory AI screening share one module
  entry point; only screened findings enter the shared adjudicator.
- Single-paper and batch runners support `--no-image-forensics`. Existing
  detector settings, screening policy, standalone commands, and artifacts stay
  compatible. Image analysis remains excluded from analyst tools.
- Record and render completed, incomplete, failed, and disabled image execution;
  cancel and await background work on early exits and release screening leases.


## [1.35.1] — Workbench responsiveness and write safety (2026-09-09)

- Run Python asynchronously with bounded concurrency, timeouts and read deduplication.
  Browsing reads the index snapshot; explicit refresh scans it.
- Validate displayed image evidence per paper; discover additional items in a
  background refresh. Human decisions no longer invalidate unrelated evidence.
- Keep image navigation within the app; lazy-load queue thumbnails and render
  visible PDF pages with cancellation, bounded canvases and document reuse.
- Enforce image-item path containment and existence before writes; serialize
  review and index updates. Preserve nested paper paths and refuse corrupt reviews.
- Correct suffix byte ranges and revalidate repaired media; reset spreadsheet
  selection when its source changes.

## [Unreleased]

- **The `src/copy_paste_detector` symlink is gone.** It pointed at
  `copy_paste_detector/src/copy_paste_detector` and existed only so an
  editable install made before 2026-09-08 (whose `.pth` lists `src/` alone)
  could still import the detector; it read as a second copy of the package,
  and on a checkout without symlink support it became a text file and the
  import failed silently. A fresh `pip install -e .` writes both roots to
  the `.pth` (hatchling `add_to_path` per `packages` entry, verified), so
  **re-run it after pulling** or `metascience raw-duplication-detect` raises
  `ModuleNotFoundError`. Out-of-venv runs now need
  `PYTHONPATH=src:copy_paste_detector/src` (README, CLAUDE.md, the example
  and verification docstrings, and `test_version.py`'s subprocess are
  updated). When the root IS missing, the bare project folder shadows the
  package as an empty namespace and the stock error is "cannot import
  name ... (unknown location)"; the two compatibility shims
  (`tools/raw_duplication.py`, `highlight_render.py`) now raise an
  ImportError that says which root is absent and how to add it
  (`tests/test_detector_import_guard.py`). PATCH: no output changes.

- Future videos end with the blink comparison; the checkerboard segment has
  been removed from both the pipeline and standalone renderer.

- **Video files carry the paper's DOI.** `image-render-videos` wrote
  `group01_transformed_match.mp4`, which names nothing once the file leaves
  its directory (Dan, 2026-09-08). New renders are
  `<doi-slug>_groupNN_<kind>.mp4` -- the slug is `paper_ids.doi_dirname`
  (lowercase, `/` -> `--`, the directory convention) with any character a
  filesystem or URL objects to replaced by `_` (`review_media.video_slug`).
  Readers accept BOTH spellings (`video_paths`): the ten videos already on
  `image_discovery_2026-09` stay attached and are not re-rendered, `video_todo`
  counts a legacy file as present, and a `--repair-existing` pass writes the
  named file and deletes the bare one it replaces. `webapp_index` finds the
  group number at a `_` boundary instead of the start of the name, so the
  workbench's manifest join survives the prefix. Exhibit PNGs are unchanged.

- **Mirrored video matches now visibly turn over after rotation and scaling.**
  The moving image lands on the complete recorded affine, including reflection,
  and the transformation caption identifies the mirror. Video title cards
  recover missing citations before rendering and fit long references without
  cutting off the title or footer.
- **`image-render-videos --repair-existing`** replaces legacy clips and clips
  whose citation changed, validates encoded replacements before swapping them
  in, and preserves render provenance across manifest rebuilds. Revisioned
  video URLs prevent the workbench from replaying a cached, outdated clip.

## [1.35.0] — 2026-09-08

- Reconcile PDF, PMC and XML-linked publisher representations of one figure.
  Full-figure registration, distributed content agreement, and crop-coordinate
  agreement are required; different-region reuse remains reviewable. Verified
  extraction artifacts carry `source_identity` evidence and are excluded from
  finding counts without changing IDs or deleting model/reviewer history.
- Adjudication exhibits are matched by panel identities, so a filtered subset
  cannot attach another finding's image. Malformed quote responses get at most
  one format retry; semantic refusals are not retried.
- Different source files no longer imply different figures. Recover PDF
  captions merged into text blocks after bare panel letters. Adjudication
  distinguishes procedural-illustration resizing from optical magnification;
  explicit rotation claims contradicted by measured geometry require review.
- Automatic comparison videos are limited to rotation (at least 3 degrees) and
  flips. Scale-only matches retain static comparisons; archived videos remain
  on disk. Existing feeds are refreshed by the resumable source-identity repair.
- `python -m metascience_agent.image_forensics.repair_source_identity PROJECT`
  audits saved findings. `--apply` archives originals and repairs verified
  artifacts; `--readjudicate --workers 4` also rechecks affected contextual
  cases with the previous model set. Model errors never count as clearing votes.

## [1.34.0] — 2026-09-08

- **Videos keep the panels' colour.** The animator loaded both panels
  greyscale and composed every act from them, so a stained section played
  in black and white while the paper is not. Matching, masks and the
  difference map stay on grey (the detector's input, so the printed numbers
  do not move); every frame a viewer sees is composed from the colour
  originals, and the render pass hands the video the colour panels it
  already loaded for the exhibit. The discovery corpus' 90 videos were
  re-rendered; the greyscale ones sit in
  `.image_track/videos_grayscale_2026-09-08/` until someone deletes them.

MINOR: the triage order and the exhibit captions changed; the detector did
not. `detector_fingerprint()` is **unchanged** — no paper is re-swept, no
group is re-adjudicated, `duplication_evidence`, `kind` and the fire rate
are exactly what they were.

- **Every duplication match now has a control.** `match_stats` recorded how
  well two panels agree once one is warped onto the other and nothing about
  how well they agree without the warp — the confound `pubpeer_figure` had
  been stating in prose ("r is inflated when both panels share a layout …
  r = 0.82 between two 4x2 blocks of entirely different micrographs").
  `image_forensics/match_control.py` measures it: the largest CONNECTED
  region agreeing at local NCC > 0.80 as a share of the overlap
  (`agree_share`), and — INSIDE that region — the aligned Pearson r beside
  the same pixels of the two panels unaligned (`lift_in_blob`). The gate
  is `agree_share ≥ 0.20 and lift_in_blob ≥ 0.25`; whole-panel `overlap_r`
  / `control_r` / `lift` / `agree_frac` are reported beside it for the
  reader. MEASURED on 90 random same-parent groups of
  `image_discovery_2026-09`, on the detector's own segments: **11 pass**,
  every one a `transformed_match` (`chart_furniture` 0 of 7,
  `shared_plot_template` 0 of 5, `same_field_independent_capture` 0 of 14).
  `10.3390--ijms13078514` IMGDUP-3, the eye-verified duplication the
  renderer had refused, passes at share 0.46 / lift +0.85;
  `10.1186--s12941-022-00531-5` IMGDUP-3, a `chart_furniture` pair at
  aligned r 0.93, fails at share 0.04. Three designs were measured and
  rejected on the way: whole-overlap correlation read the real case at
  r 0.09 (its source segment is an entire montage row); a share-only gate
  passed a synthetic grid over two DIFFERENT fields at share 0.95 with lift
  +0.00; and an inlier-box region would read the wrong pixels on every
  mirrored match, because `inlier_box_b` is in the flipped frame.
- **It lives in the review manifest, not in `image_duplication_findings.json`.**
  Computed inside `render_review_media`, which every write path already
  calls (`retain`, `adjudicate`, `agent`, the video pass), on the panels it
  already decodes. `adjudicate.combine` rebuilds the findings file from the
  pristine copy on every pass, so a block written there post hoc would have
  been deleted by the next adjudication. Each block carries `code_sha` and
  `measured_at`; a re-render re-measures when the code moved and carries
  the block forward otherwise. `metascience image-rebuild-exhibits` is the
  backfill: free, idempotent, leaves the sweep stamp alone.
- **The gate annotates and re-ranks; it never removes a box.** The inlier
  box is a true statement about keypoint geometry. `triage_rank` flags a
  MEASURED failure `lookalike` and sorts it after every unflagged group of
  its tier — a demotion, so a group nobody has measured yet ranks exactly
  as before; `score` is untouched. Exhibits print the control sentence
  under the reading note; `summary_figure`'s footer says in all three
  states what its box does and does not establish. The manifest carries
  `exhibit_gate: passed | failed | not_measured`.
- **Exhibits draw from the detector's recorded affine.** `estimate_match`
  re-derived the geometry at `nfeatures=1000` against the detector's 2000
  and refused `10.3390--ijms13078514` IMGDUP-3 (aligned r 0.81, above its
  own 0.5 floor) on a keypoint count, so the real finding shipped as
  `group01_unverified.png`. The fallback now runs at 2000 and is reached
  only when no affine was recorded.
- **`exhibit_verified` means "a box was drawn from verified geometry".** It
  defaulted `True` and was only ever flipped inside the refusal branch, so
  every bail path (missing PNG, single-panel group) said verified with no
  exhibit.
- **The manifest ↔ feed join is fixed.** `group_index` numbers STANDING
  groups (it is the artifact filename's number); `image_review` numbers
  `IMGDUP-N` over ALL groups. On a paper whose first group had been
  cleared, the cleared group was handed the real finding's exhibit and the
  real finding showed none. Entries now carry `findings_index` and the feed
  joins on it; `video_todo` numbers from the same `_standing_groups` as the
  writer instead of hunting for filenames never written. Filenames are
  unchanged, so nothing on disk is orphaned.
- Not in this release, deliberately: the adjudicator prompt does not yet
  see the control (its own MINOR, with a before/after count), and
  cross-paper matches are unmeasured — that sweep matches without pixels.

## [1.33.0] — 2026-09-08

MINOR: a published count changed meaning.

- **The project table's "Image findings" column now counts what the
  adjudicator left suspicious**, not everything still standing. The old
  number was `n_duplicate_groups` — and only `explained` clears a group,
  so every `insufficient_evidence` verdict stayed in it: measured on the
  fully-adjudicated discovery corpus, 834 groups on 180 papers where only
  344 on 128 were `unexplained` (Dan: "it seems wrong right now"). The
  scanner (`webapp_index._evidence_group_counts`) now reads verdicts:
  the column = standing groups that are `unexplained` OR never judged
  (an unadjudicated group must count — "nobody looked" rendered as 0 is
  absence read as evidence, the review queue's own default lens);
  standing `insufficient_evidence` is the NEW `n_image_undecided`,
  shown as a dim `+N?` suffix and named in the cell tooltip, because
  silently excluded it would read as cleared, which it is not. The
  `n_duplicate_groups` scalar survives only as the fallback for a file
  with no groups list. Side effect, deliberate: papers whose only
  standing groups are undecided leave `paperHasFindings`'s prev/next
  navigation ring, consistent with the queue. Re-run
  `metascience webapp-index` for the new fields.

## [1.32.0] — 2026-09-08

MINOR: pipeline videos are full productions, and they cannot vanish.

- **`metascience image-render-videos`**: renders the animation for every
  standing rotation/zoom/flip group that lacks one, corpus-wide, free,
  idempotent (Dan: "for ones with rotations, please make sure videos have
  been created with title card etc" — the adjudication passes re-render
  manifests with `render_videos=False`, so the discovery corpus had 107
  eligible groups and ZERO videos). Defers papers with no adjudication
  stamp by default: an in-flight judgement may clear the group and will
  rewrite the manifest.
- **The title card now reaches pipeline videos.** `title_slide` was only
  callable from the standalone animator's CLI flags; `review_media.
  title_card_args` builds the card from the paper's own `metadata.json`
  (authors capped at 12 + et al., journal_normalized preferred), artwork
  via `METASCIENCE_TITLE_LOGO` / `METASCIENCE_TITLE_BRAND_MARK` or the
  sibling website checkout, and `_render_video` renders it first, with
  `main()`'s own `UI = height/720` scaling.
- **Real references fixed the card's layout**: a four-line title pushed
  the footer off the slide and a long journal name ran under the woodcut
  (`mixed()` never wrapped). Titles elide at three lines, the journal
  wraps onto its own italic line when the assembled reference cannot fit,
  and the generated-by footer anchors to the bottom of the slide.
- **A rendered video can no longer vanish from the manifest.** Every
  rewrite with `render_videos=False` NULLED `video_mp4` while the .mp4
  sat orphaned on disk; an existing video for a group that wants one is
  now re-attached, never re-rendered and never dropped.

## [1.31.0] — 2026-09-08

MINOR: cross-paper matches can finally be adjudicated after the sweep.

- **`metascience image-adjudicate-cross`** (`image_corpus.
  readjudicate_cross_matches`): reads every paper's
  `cross_paper_matches.json` back into the sweep's match shape (mirror
  rows deduplicated on the sorted uid pair; page/pt/figure labels
  recovered harvest-first from `panels.json`) and runs a
  **screen-then-confirm ladder** — the screen model (default haiku)
  judges every pending pair; the confirm model (default sonnet) re-judges
  only the pairs the screen would clear or left undecided; a match is
  cleared only when every model that voted said `explained`
  (`adjudicate.combine`'s require-all rule, evaluated lazily — a screen
  `unexplained` is final because downgrade-only means standing is the
  conservative outcome). Per-model records ride beside the combined one
  (`adjudications`), the per-paper files are rewritten as a whole, and
  every failure keeps the match standing and named. Until now
  `adjudicate_matches` was reachable only from a full `image-corpus`
  sweep, so a corpus swept without the paid pass (all 49 discovery-corpus
  cross items) had no route to a verdict short of recomputing ~10.9M
  pair comparisons.
- **`write_cross_paper_matches` stamped every real sweep
  `adjudicated: false`** — it read a top-level `adjudicated` key that
  `sweep()` never writes (its key is `adjudication`), so matches without
  a verdict carried the misleading "--no-adjudicate" absent-reason even
  when the paid pass ran; the tests passed because the fixture injected
  the key itself. Now falls back to `bool(result["adjudication"])`.

## [1.30.0] — 2026-09-08

MINOR: a new artifact (the one-image summary) and new review-surface verbs.

- **One PubPeer-ready summary PNG per image item** (Dan: "all in a single
  image ... not two separate images with text below").
  `review_media.summary_figure` renders both panels, the red/green inlier
  boxes (the comparator's own colours) and the identifying text — detector
  sentence on top, a colour-swatched `A · Figure N` label under each panel,
  paper dir + DOI lines in the footer — into one self-contained image. It
  draws `within:` and `cross:` items alike (cross-paper pairs never had a
  composite), and an intra-panel clone as one panel with source red / copy
  green. An item with no verified fit renders unboxed and says so on the
  image. New verb `metascience image-summary-figure <corpus> --item <id>`,
  cached under `<corpus>/.image_track/summary/` and invalidated by a newer
  panel PNG; served by the workbench at `/api/images/summary` behind a
  "summary PNG" link on the item page; `discovery_review_folder.py` writes
  it as `00_summary.png` beside the raw panels.
- **Download the paper from the viewer**: a "download PDF" link on the image
  item page's PDF strip and a ⤓ button in the findings viewer's zoom group,
  both via `/api/media`'s existing `?download=1` attachment path.
- **Show in folder**: `/api/reveal` opens the paper's directory in the OS
  file browser (`explorer /select,` on Windows, `open -R` on macOS,
  `xdg-open` on Linux, which has no select verb), through the same path
  boundary as `/api/media`; buttons on both viewer surfaces.

## [1.29.2] — 2026-09-08

PATCH: image review surface, from Dan's first session with it.

- **B's inlier box was never drawn.** Every pair carries `inlier_box_b`,
  but the comparator drew A's box only and showed B as a plain image in
  side-by-side. B now has its own canvas with its box (green) in its own
  frame, and in overlay and blink modes B's box is carried through the
  inverse transform into A's frame, where it must land on A's red box --
  and on `10.1186--1476-4598-9-282` IMGDUP-1 (a 292 px translation) it does.
- **Hovering a queue thumbnail shows a large version** beside the cursor:
  the exhibit when one was rendered, else both panels.
- The comparator measures its toolbar instead of assuming one line, so a
  long status sentence no longer pushes the canvas past its box.

## [1.29.1] — 2026-09-08

PATCH: layout only, on the image review item page (Dan, first use).

- Explanation and decisions on the LEFT, the comparator and PDF on the
  RIGHT, previous/next at the right end of the header -- the paper page's
  reading order.
- The comparator FITS its box by default (width and height, both columns
  in side-by-side) instead of filling the column width, which on a wide
  screen put the pair past the fold; `-` / `=` zoom, `0` refits.

## [1.29.0] — 2026-09-08

MINOR: two new CLI verbs and a new review surface. No detector or prompt
changed, so retained sweeps stay valid; the bump is for the verbs and for
`image-benchmark`'s scorecard gaining a key.

- **A separate review system for image findings** (`webapp/app/images/`,
  `/images/<project>` and `/images/<project>/<item>`). The unit of work is
  an ITEM -- one pair of panels, `within:<paper>:IMGDUP-N` or
  `cross:<A>:<B>:<hash>` -- never a paper: the paper page's image issues
  showed one paper at a time and could not rank across a corpus of 338
  standing groups. `image_review.build_items` is the feed
  (`metascience image-review-items <corpus>`, cached under
  `<corpus>/.image_track/image_review_items.json`; `--summary` prints the
  counts), joining every paper's retained findings, adjudication, exhibit,
  captions (verbatim, via `figure_context.resolve_captions`),
  `cross_paper_matches.json` and the human decisions. `write_decision`
  (`metascience image-review-write`) writes `review.json` beside the paper
  -- BOTH papers for a pair -- plus the corpus ledger
  `.image_track/image_review.jsonl`, and patches the cache in place.
  Ranking is `image_forensics/triage_rank.py`, the rule that separated real
  from scaffold on Masliah and the discovery corpus (+2 partial coverage,
  +2 real rotation or flip, +1 spans figures, +1 shared grain, +1 clone;
  unexplained above insufficient-evidence above cleared), shared with
  `examples/discovery_review_folder.py` so the queue and the offline folders
  cannot disagree.
- **The PDF opens at the panel, with its caption in view.** Each item
  carries one `pdf_bbox` target per placement and the item page mounts the
  workbench's `PdfPane` per paper (two for a cross-paper pair); `a` and
  `shift+b` jump between the panels. MEASURED: all 90 cross-paper targets
  on the discovery corpus were page-only (the corpus index records no box),
  so the pane opened the 2012 paper at the top of page 5 and the reviewer
  had to find Figure 3; `fill_bboxes_from_pdf` now recovers the rectangle
  from PyMuPDF by the xref in the panel uid -- verified identical to the
  harvest's own boxes on the Nature Medicine pair -- and stamps
  `bbox_source` so a recovered box is never mistaken for a measured one. A
  PMC-render panel has no page and the pane says so instead of jumping.
- **A comparator that survives mirrored and rotated pairs.** B is drawn
  through the detector's affine into A's frame on a canvas (side by side,
  blink with space to hold, overlay with an opacity slider, inlier boxes);
  the animator had refused exactly those pairs (0 ratio-test matches on
  `nm.2772` and `nl4017072`), and the Figure 1 / Figure 6 pair now lines up
  on screen. A guessed alignment (no affine recorded) says so in words.
- **`image-benchmark` gains a `cross_paper_review` block** from the ledger:
  a decision tally over pairs, explicitly not a recall figure, because
  PubPeer has no cross-paper denominator.
- **The bridge picks the console script's interpreter** (`webapp/lib/
  python.ts`): it used to try only `METASCIENCE_PYTHON` and one venv path,
  then fall through to the system python. A shebang is accepted only when
  it names a python, and a `#!/bin/sh` shim is followed one `exec` hop --
  the first version accepted `/bin/sh` and every bridge call ran
  `sh -m metascience_agent.cli`.
- The new routes resolve the project through the CACHED index. Awaiting
  the rescanning loader, as the project page does, re-ran the Python
  scanner over every project and cost 4 s per queue open and per decision.

## [1.28.0] — 2026-09-05

MINOR: a new detector tier and an adjudication-prompt change. Two image
reviews across this boundary are not comparable, and every retained sweep's
stamp is now stale by design (`copy_move.py` joined `FINGERPRINT_FILES`).

- **The intra-panel clone tier is wired, opt-in** (`--copy-move` on
  `image-sweep` and `image-analysis`; `analyze_paper_images(copy_move=)`).
  Every other tier compares DISTINCT panels, so a region pasted from
  elsewhere in the SAME panel -- the canonical within-blot manipulation, 88
  of 236 alleged figures in the PubPeer ground truth -- was invisible to all
  of them. `copy_move.detect_copy_move` had been exact on synthetic ground
  truth and deliberately unwired through four measured calibration passes
  (its docstring is the record; the last reached PubPeer 18/50, other 1/40).
  Tier 5 emits `intra_panel_clone`: ONE panel, two boxed regions,
  `pair_scope: regions_within_one_panel`. Default OFF, and when off the
  result carries a `tiers_not_run` entry naming it -- "no clone found" and
  "clones were not looked for" must never arrive in the same shape.
  Threaded end to end and ASSERTED (`tests/test_copy_move_wiring.py`): the
  flag changes the answer (the planted paste is recovered at exactly
  (330, 0); the clean membrane does not fire), the stamp (`copy_move` in
  `STAMP_FLAGS`) and the child's argv -- because the `rendered_regions` flag
  had once been accepted and silently dropped. Every consumer survives a
  one-panel group: the findings rows, the sibling-clique gate, the review
  manifest (the exhibit is the detector's red/green overlay, drawn without
  the animator) and the coloured-box summary figure (the overlay joins the
  row as a second column so the |A-B| view shows exactly where the boxes
  sit). The adjudicator sees the overlay path and is told red = source,
  green = copy; `same_condition_in_both_figures` and `overview_and_detail`
  are registered as contradictions of this kind (one figure; a pure
  translation). The sweep summary's per-tier line now includes it, which is
  where its adjudicated fire rate gets measured before any default changes.
- **`examples/build_discovery_corpus.py`: a fetch list of papers with an
  elevated prior of image problems where nobody has looked.** Seeds are
  Retraction Watch papers retracted for image reasons whose authors are in
  the long tail (1-2 such retractions: 27,806 names, against 215 with 10+ --
  the famous ones are the combed ones); the corpus is everything ELSE those
  authors published, 2010+. Authors are resolved from the retracted DOI's
  OpenAlex authorships, never from a name search. Hard exclusions, each
  recorded in `MANIFEST.json`: any Retraction Watch DOI, OpenAlex
  `is_retracted`, NLM's retraction mark, and any PubPeer thread about images
  (attached figure, a reuse word, or a figure reference beside a visual-
  sameness phrase -- bare "identical" excluded a 10,000-character statistics
  critique on the first pass). A PubPeer lookup that was REFUSED lands in
  `pubpeer_unknown` and is never fetched as clean; 41% of batches were
  refused at 1.5 s spacing on the first full run, so the default is 3 s
  with one slower retry. Two conflation guards, because OpenAlex author
  records for common names are two people: topic domain (2,370 physical-
  sciences works under "biologists" on the first run) and co-authorship
  connectivity to the seed paper -- adaptive, strict only where the record
  shows off-domain work, since applied flat it zeroed a PI whose 2007 lab
  had turned over and a postdoc who moved. Meeting-abstract leaks
  (supplement issues, `iv123`/`S123` pages, no PMID, venue "PubMed") are
  closed with the signal that caught each. PubPeer is asked only about a
  preliminary shortlist, not all ~14,000 survivors.

- **docling stays unwired as a figure-region source, measured rather than
  assumed** (`examples/measure_figure_regions.py`, new; numbers dated in
  `extraction/regions_docling.py`). The question was whether the layout model
  finds figures the caption-anchored route cannot, which is the only thing
  that would justify ~8 s/paper against 0.28 s. On 60 papers with a text
  layer and 313 published figures the caption route found 278 (recall 0.888)
  and docling 252 (0.805, label agreement 0.897). On 19 papers the image
  track had REFUSED -- the set that would justify a second instrument -- both
  routes found essentially the same: 20 and 21 of 58, and they returned zero
  on the SAME LWW/Ovid papers. Where both found a figure they agree on where
  it is (median bbox IoU 0.98, and 0.879 on the hard set). docling is not a
  second instrument pointed at what the first one misses; it is the same
  instrument, slower. The decision rule was fixed in the script's docstring
  before the run and is recorded as NOT MET -- and could not strictly be
  evaluated at all, because no paper in either sample had both an empty text
  layer and a publisher XML to score against.
- **A layout adapter that reported "no figures" when OUR toolchain was
  broken.** Found while running the above: in a plain process on Python 3.13
  (no `distutils`) the layout model's torch-dynamo compile step fails and
  `figure_regions` returns SUCCESS with ZERO regions. Four tests were failing
  exactly that way; the adapter now sets `TORCHDYNAMO_DISABLE` itself, as
  `docling_tables` already did. docling had also moved to 2.119.0, which the
  adapter refused as untested -- correctly; it is now re-verified against the
  smoke paper (page 4 of `10.1007--s004010051012` maps to top-left
  `[46.9, 49.2, 548.7, 387.9]`, identical to the recorded figure) and
  `DOCLING_PIN` became `DOCLING_VERIFIED`, a list of versions whose facts
  were actually re-checked, each dated.

- **Elsevier high-resolution figures: 383 fetched, and the honest finding is
  that the captions were never the problem.** An Elsevier full-text XML
  carries the label and caption in `<ce:figure>` and a full-resolution
  rendering in `<xocs:attachment>`, joined on the locator; no code read
  either. `image_forensics/publisher_figures.py` reads both and
  `metascience image-fetch-publisher-figures` fetches them.
  MEASURED over the Masliah corpus: 93 papers carry an Elsevier full text,
  58 have `IMAGE-HIGH-RES` attachments, and the fetch took **383 figures,
  180 MB, median width 1,644 px (max 7,500), zero failures and zero
  entitlement denials.** The `<xocs:ucs-locator>` in the XML is a signed S3
  URL that answers 403; the same file is public on the ScienceDirect CDN
  under its attachment id, which is what the module requests -- both are
  recorded in the manifest so a reader can tell which was tried.
  **What it does NOT add is captions.** Of the 379 figure captions the fetch
  brought back, all 379 were already available to the adjudicator straight
  from the same XML, which v1.17.0's resolver reads first. The fetch's value
  is therefore pixels -- a 1,644 px rendering against a downsampled embedded
  stream -- and whether that changes a verdict is the deferred
  "high-resolution supersedes embedded" experiment, not something this
  release claims. The captions are wired into the resolver regardless, for
  the papers whose XML is absent but whose manifest is not.

- **`rendered_region`: the whole-figure crops now have a consumer, and it
  finds nothing on this corpus. Default OFF, and the measurement says why.**
  `extraction/figures.py` renders each figure's page region at 150 dpi with
  its label and caption, the track already runs it for the figure-label
  join, and 3,255 high-confidence crops sat on the Masliah corpus read by
  nobody -- while 625 figures had no harvested panel at all and 5,252 panels
  were withheld as `tile_member`, one photograph sliced into strips with no
  reassembly. `panels.harvest_rendered_regions` turns those crops into
  panels, gap-filling only (a figure whose embedded panels survived the
  texture gate gets none) and keypoint-tier only (a whole-figure crop's
  perceptual hash measures the caption band and margins, not the content).
  MEASURED over 738 papers with a figure map: 2,632 figures are already
  covered, 549 renders are withheld as low texture (bar charts, which is the
  gate working), 127 crops are not confident enough, and **38 papers gain 79
  compared renders**.
  Swept, those 38 first produced **66 groups across 8 papers, 65 of them
  between figures on ONE page** -- and reading them showed why:
  `10.1007--bf00688209` gives five figures on page 4 the identical bbox
  `[0, 0, 597, 785]`, the whole sheet, so their "crops" are five copies of
  one page and 42 groups were a page matched against itself. Two exact
  guards, both tested: a region shared by two or more figures yields no
  render at all (`crop_not_figure_specific` -- the region names the page,
  not the figure), and two renders whose regions overlap on one page never
  match (`_render_contains_placement`, which previously only refused a
  render against a panel inside it).
  After the guards: **115 renders compared, 4 groups, all of them already
  classified `chart_furniture` and suppressed as context, and ZERO
  evidence-bearing groups.** So on this corpus the channel adds no findings.
  It ships gated and off, with `extraction/figures.py` in the detector
  fingerprint and `rendered_regions` in the stamp, because a corpus of
  strip-sliced photographic figures is a different question from a corpus of
  bar charts -- and the next person to ask it should not have to rebuild it.

## [1.27.0] — 2026-09-04

**The serial sweep → editorial pipeline is deleted.** ~7,100 lines from `src/`
and `examples/`, ~4,700 from `tests/`. `agent.py` 7,487 → 5,634;
`report_render.py` 2,634 → 784.

Gone: the `two_stage_legacy` mode and its body, `write_review_outputs`,
`_findings_only_result`, `_build_editorial_prompt`, `_findings_by_stage`,
`_run_stamp`, `_write_raw_duplication_highlights`, `stage1_system_prompt` /
`stage2_system_prompt`, `stage1_sweep.md` / `stage2_editorial.md`,
`report_render.render_report` and 31 helpers, 15 dead module constants, the v1
`findings.schema.json` / `report.schema.json`, and the `--legacy-two-stage`
flag on `analyze` and `eval`.

**Everything that READS v1 output still works** — `bundle.py`,
`webapp_index.py`, `migrate_v2.py`, `runs.py`, `agreement`, `replay`,
`repair-register`, `anatomy`, `tripwire`. Deleting a writer is not deleting a
reader, and ~39 archived runs plus 22 tracked bundles depend on that.

**Why it was safe now, and not before.** The grok measurement of 2026-09-02
(parallel ≥ legacy recall on all three fixtures, 0–1 false positives); every
legacy-only capability ported or dropped with its reason recorded (census
v1.23.0, sandbox guards v1.23.1, severity reconciliation v1.24.0/1.25.1,
machine refusals + supplement record v1.25.0, `source` v1.26.0, highlight
workbook dropped); the four prerequisites in v1.26.1; and the analyst-loss
root cause found in v1.26.0, which is what most needed the legacy sweep prompt
as a control.

**The test work was the risky half, and it was risky in one specific way.**
`test_prompt_contract.py` parametrised its cross-document rules over a dict
keyed by the two legacy prompt filenames, so deleting them would have SHRUNK
the parametrisation and passed. Rules are now anchored on the live prompts —
which fixed a gap that already existed: `tool_expert.md` carries the anecdote
those rules police and was in no case at all, passing by luck rather than
enforcement.

Re-pointed rather than deleted, because the rule survives in the live prompt's
own words: the R cross-check gate on `impossible` (`adjudication.md` §6 — "if
the R engine cannot run, SAY SO … an unavailable cross-check is never a
disagreement"), the spot-check-not-a-second-sweep rule (§6), verdict
calibration (§7), the measured-provenance rules (`tool_expert.md`, identical
phrasing), and every `handoff` wiring needle. **A first pass reported the R
gate as MISSING** — that was a grep for the legacy WORDING, and reading its
absence as the rule's absence is the error `LESSONS.md` names first.

Superseded rather than ported: the figure-limitation prompt rule. v2 computes
it — `channels.image_forensics` is a tri-state that `report_v2` renders
structurally — which is stronger than asking a model to remember, and is
pinned in `test_report_v2.py`.

`test_every_check_can_be_named` was nearly lost and is now stronger: its
`_enum()` read the schema FILE, which ships the literal placeholder
`__TECHNIQUE_ENUM_INJECTED_AT_LOAD__`, so it reported every real tool as
unnameable. It reads the loaded schema now, and identity wins over the v1
paraphrase map.

**Two gaps this made visible, recorded not fixed.** v2 has no `plain` field
and no `headline` — the plain-language translation for non-statisticians is a
v1-report feature the v2 document never carried, so it has not been produced
since v1.0.0. And v2's `coverage_summary` is an OPEN object
(`additionalProperties: true`, no declared keys) where v1's was closed, so the
census writes into a block with no schema discipline.

## [1.26.1] — 2026-09-04

**The four legacy-deletion prerequisites. No deletion yet, no behaviour change.**

Each was a live coupling that would have broken working code, or silently
mis-reported, the moment the legacy body was removed.

- **(a)** `SEVERITY_VALUES` / `VERDICT_VALUES` were built at import by reading
  the two V1 schema files the deletion removes, and
  `evaluation/deterministic.py` reads both on the LIVE eval path — so deleting
  the schemas would have broken current-pipeline evaluation with an error
  pointing at a file nobody thought was load-bearing. Now sourced from
  `tools/severity.py` and `verdicts.py`, verified byte-identical.
- **(b)** `_provenance()`'s default `prompt_blob` hashed the legacy stage
  prompts, and `cli.py`'s version verb calls it bare — so `metascience
  --verbose` reported the fingerprint of prompts the live pipeline does not
  send. Default is now the parallel trio. **`_run_stamp` passes the legacy blob
  explicitly**, because both its callers are in the legacy body: a run labelled
  with the wrong prompt hash is worse than one labelled with none, since it
  makes two incomparable runs look comparable.
- **(c)** `handoff.reachability` read `agent.STAGE1_TOOLS`/`STAGE2_TOOLS`; it
  now asks `registry.stage_tools` for the three roles — the source those
  aliases were derived from. Verified identical first: both unions cover 60
  tools and strand nothing. Counts are reported under role names, with the old
  keys kept as aliases.
- **(d)** Four `_reads` needles pointed into the legacy body or at
  `stage2_editorial.md`. `_reads` returns False for a missing file OR a vanished
  name — silently — so the audit that exists to catch a stranded hand-off would
  have reported OUR OWN CLEANUP as an unwired pipeline. All four now name the
  live pipeline's equivalents.

`tests/test_handoff_reachability_roles.py` adds the guard that makes the
deletion safe: **every `_reads` needle in the module must resolve**, so a
needle aimed at deleted code fails loudly instead of degrading to "not wired".

The repo's own guards caught two of my mistakes here, both right:
`test_ruff_errors.py` on an import left unused by (c), and my first version of
the no-legacy-import assertion, which scanned prose and fired on its own
explanatory comment.

## [1.26.0] — 2026-09-04

**The analyst loss is partly ours, and this recovers it for free.**

The paid A/B authorised to isolate why grok "loses an analyst" produced its
answer on the first arm. Running the tool-expert contract and fence on
`airforce` — the configuration whose archived run made **0 tool calls in 7.4
seconds** — the stage instead made **87 tool calls over 1,030 s** and returned
one `impossible` verdict. Its 61,300-char result BEGAN with a real document,
broke off at char 4,904 into `Extra. Extra. Extra…` repeated, and then
re-emitted a COMPLETE 18-finding document (34 register rows, 8 unchecked)
filling the rest of the stream.

`_extract_json` returned `failed` and discarded all of it. Every tier it had
reads from the START of the stream: `json.loads` on the whole string dies on
the abandoned prefix, and the fenced-block tier finds nothing because grok
emits bare JSON. The run then paid for a `_repair_json` retry — which in the
archive came back empty. So a stage that had done the work was recorded as
having produced nothing.

**`_salvage_documents` is a fourth, free, deterministic tier**, tried after the
cheap ones and before anything paid. It scans for every COMPLETE object that
carries a document marker and returns the RICHEST — not the last, because grok
emits empty skeleton placeholders throughout a run and "last" would happily
return one emitted after the real document. Nothing is ever synthesised: a
truncated document is skipped, not repaired. Verified on the live stream: 18
findings, 34 register rows, 8 unchecked recovered; and every cheap tier still
wins where it can, with a genuinely empty stage still `failed`.

A salvaged run **says so** — `output_parse_path: "salvaged_object"` in
`run_meta`, plus a limitation, because "we recovered it" is not "it ran
cleanly".

This reframes the failure taxonomy. Failure A (degenerate mid-document) is
largely an EXTRACTION defect on our side and the model recovers on its own.
Failure B (airforce's archived 238-char, zero-call stage) is real and
unaffected — salvage correctly refuses it. The archived streams are slimmed, so
this could not be validated retroactively; it rests on the fresh unslimmed arm.

**`source` now has a producer.** `sourcing.annotate_v2` is wired into the
parallel writer. It was declared in `findings.v2.schema.json` AND listed in
`prompts._NOT_PRODUCER_WRITTEN` — the contract said the pipeline writes it —
and nothing did: 0 of 80 archived parallel findings carried it. Measured now:
18/25, 10/17, 2/3 and 2/4 joinable findings trace to a passage. `_has_real_tool`
replaces `_candidate_tools` truthiness so v2 judgement techniques
(`not_computational`, `internal_contradiction`, `factual_claim`) land in
`manual` instead of being reported as failed joins — 14/4/5/8 per run. Now
registered in `obligations.py`, whose exclusion note is retired.

**Built and deleted rather than shipped:** a narrowing of the sourcing pool to
`tool_verdict.tool`. The theory was sound — v2 findings carry no `inputs`, so
the scalar route cannot fire — but measured across all four archived runs it
changed NOTHING: not one extra join, not one differing quote. `_source_for`'s
empty-`wanted` branch already handles it. Shipping it would have been inert
machinery carrying a plausible story.

**A fourth serialise-then-mutate defect, this one mine.**
`severity_reconcile.annotate_v2` sat BELOW the `findings.v2.json` write from
v1.24.0, so the `severity_source` blocks it writes onto findings never reached
disk — only the `run_meta` summary did, which is why every test passed. Both
annotators now sit immediately above the write, and the new tests read the FILE
rather than the in-memory dict, which is the only way this class of bug is
visible.

## [1.25.1] — 2026-09-04

**The reconciler re-derived a join the document already carried.** A defect in
v1.24.0, found by a second reader checking `findings_v2.py` against the port
rather than reading the port alone.

`severity_reconcile.reconcile_finding_v2` established the tool's verdict with
`_tool_severity`, which matches a finding's `inputs` scalars against the
ledger — and **v2 findings do not carry `inputs`**. Meanwhile
`findings_v2.tool_verdict_for` had already written that verdict onto the very
same findings at `parallel.py:477`, 1,300 lines before `annotate_v2` runs at
:1836. So the port re-derived, weakly, an answer sitting on its own input.

`_v2_tool_severity` now prefers the annotator's `tool_verdict` and keeps the
ledger join as a fallback, so this is a superset of v1.24.0's behaviour.
`joined_by` records which route fired, per finding and as two summary counts —
a run where `n_joined_by_ledger` dominates means the annotator has stopped
writing `tool_verdict`, which is visible here rather than as a quiet drop in
`n_compared`.

**What this did and did not change, measured on the four archived parallel
runs.** `n_compared` (1/1/1/0) and `n_diverged` (1/1/0/0) are UNCHANGED, and
the v1.24.0 report of them stands. What moved is two findings, on apple_cider
and wound_healing, from `n_unjoined` — "we could not join this" — to
`n_not_on_ladder`, where the tool had returned `consistent` or `indeterminate`.
Those verdicts have no rung on the 1–9 ladder and must never be diffed against
an integer, so they were never comparable; filing them as a failed join
overstated our own failure, which is the mirror of understating it and just as
misleading. Of the 8 apple_cider findings carrying a `tool_verdict`, 7 are
`consistent`/`indeterminate` and 1 is `suspicious` — so 1 comparison is the
correct number, not a shortfall.

Consuming the shared join also drops `computed.severity` as a source: that is
the MODEL's transcription of a tool result, and comparing the adjudicator
against a number the model typed is comparing the model with itself.

**`severity_source` is now declared in `findings.v2.schema.json`.** v1.24.0
wrote it into a `findings/items` block that is `additionalProperties: false`,
where it was undeclared — illegal by contract, and green only because nothing
validates the WRITTEN document. It is declared beside `tool_verdict` and added
to `prompts._NOT_PRODUCER_WRITTEN`, so no producer is offered the slot: a
producer able to write its own `severity_source` could assert agreement with a
tool that never ran.

**Recorded, not fixed: `source` has a contract and no producer.** It is
declared in the v2 schema ("Set by the pipeline, not the model", five
subfields) and listed in `_NOT_PRODUCER_WRITTEN` — so the design already says
the pipeline writes it — and nothing on the parallel path does. 0 of 80
findings across the four archived parallel runs carry it, against every legacy
run that does, and `sourcing.annotate` lives only in the legacy writer the
deletion removes. `obligations.py`'s stated reason for excluding it ("NOT in
`findings.v2.schema.json` at all") is now false and is corrected in place. This
is the `sandbox_audit.json` case again, and a fourth port-or-lose item the plan
had missed.

## [1.25.0] — 2026-09-03

MINOR: the dispatcher's refusals and the supplement record reach the parallel
document. With v1.23.1 and v1.24.0 this completes the enrichment port; the
highlight workbook is dropped deliberately and the reason is in the spec.

- **What the DISPATCHER declined now reaches `unchecked`.**
  `dispatch.check_table` writes a per-(cell, check) `not_run` record with a
  reader-grade reason precisely so coverage does not depend on the model
  remembering what it skipped, and on the parallel path nothing consumed it:
  a run that submitted three tables and had every cell inside them refused
  still read as "checked", because checked meant attempted. The machine's
  refusals merge into `unchecked`, which until now held the PRODUCERS' own
  account alone — the model's declaration and the dispatcher's refusals are
  the same kind of fact — deduped on `(location, reason)`.

  Read from **raw messages, not the ledger**, and deliberately: `check_table`
  is a bulk tool whose ledger result is capped at 4,000 chars, so refusals
  read from there would be cut off on exactly the tables big enough to
  matter. The census reads the ledger for the mirror-image reason (there the
  archive's *messages* are the truncated copy). Each reads whichever source
  keeps the payload it needs.

- **`run_meta` names the supplements again.** No archived parallel run
  records a supplement at all. `supplied_supplement_paths` in particular
  cannot be recovered by re-listing the paper directory later, since a
  `--supplement` may live anywhere on disk, so a run whose record omits it is
  not reproducible from its own metadata. It matters more since v1.23.0: the
  census counts supplements toward its denominator, so which ones were
  readable is now part of a published coverage figure.

- **DROPPED, deliberately: the highlight workbook.**
  `_write_raw_duplication_highlights` goes with the legacy writer. v2 findings
  carry `technique` but not `inputs`, so the detector's arguments have no
  source in a v2 finding, and **no archived parallel run has ever produced a
  `raw_duplication` finding** — the port would ship dormant. Recorded in
  `docs/specs/pipeline.md` so the absence is a decision and not an oversight.
  The workbench link degrades to absent, not to a wrong answer.

The refusal merge was written after `findings.v2.json` is serialised on its
first cut, so it reached the in-memory document and never the file — the same
serialise-then-mutate hazard that cost `run_meta.sandbox` 21 archived runs.
Its test caught it before the commit.

## [1.24.0] — 2026-09-03

MINOR: severity reconciliation runs on the parallel pipeline, onto the 1-9
ladder. `run_meta.severity_reconciliation` is written by every run, so the
viewer's "Did the write-up keep the tool's verdict?" section stops vanishing.

**The v2 question is not the v1 question, and porting it unchanged would have
produced a guard nobody reads.** In v1 the editorial stage had no mandate to
re-grade, so ANY departure from the tool's verdict was suspicious on its face.
In v2 an adjudicator exists whose entire job is assigning the final rung, so a
departure is the design working. Flagging every one would fire on nearly every
finding. The v2 check is narrower: a departure from the tool's verdict **that
the adjudication does not explain**.

- **The ladder trap.** `severity9.FIVE_TO_NINE` covers only the three
  accusatory values (`suspicious` 3, `highly_suspicious` 4, `impossible` 5);
  `indeterminate` and `consistent` map to non-problem outcomes with a null
  severity and have NO rung. They land in an explicit `n_not_on_ladder`
  bucket. Treating them as 0 and diffing against a real rung would
  manufacture a divergence out of a category error, and the interesting case
  there -- the tool said fine and a finding was filed anyway -- is a different
  question `_unbacked_findings` already owns.
- **Manual is not a broken join.** `_candidate_tools` falls back to the
  technique's own name, which was fair in v1 where every technique named a
  tool. v2 techniques include `not_computational`, `internal_contradiction`
  and `factual_claim` -- findings with no tool verdict BY DEFINITION -- so the
  fallback filed them as failed joins and **overstated our own failure**,
  which misleads exactly as much as understating it. `_has_real_tool` asks the
  registry instead. Measured on apple_cider: `n_unjoined` 32 -> 18, with 14
  correctly reclassified as manual.
- Every divergence is listed with its marker, explained or not. A list
  carrying only the unexplained ones beside an `n_diverged` counting all of
  them makes a reader do subtraction to learn what they are not being shown.

**MEASURED on the four archived parallel runs**, and the numbers are the
honest ones rather than flattering ones:

| run | findings | compared | diverged | unjoined | manual | not on ladder |
|---|---|---|---|---|---|---|
| apple_cider | 39 | 1 | 1 | 18 | 14 | 6 |
| wound_healing | 8 | 1 | 0 | 2 | 5 | 0 |
| cerebrolysin_flow | 21 | 1 | 1 | 9 | 4 | 7 |
| airforce | 12 | 0 | 0 | 3 | 8 | 1 |

Both divergences found were EXPLAINED -- the adjudicator departed from the
tool and said why, which is the system working.

**The join is weaker on v2 than on v1 and this release does not fix that.** On
the same three papers the legacy runs compared 12, 10 and 32; these compare 0,
1 and 1. v2 findings record the inputs the producer reasoned about, which do
not always match the arguments of the call that produced the verdict. Loosening
the match was rejected: a false join produces a false accusation about our own
model, which is the wrong direction to be wrong in. The weakness is REPORTED
rather than hidden -- every finding lands in exactly one named bucket and the
buckets sum to the finding count, which `tests/test_severity_reconcile_v2.py`
pins per run. A reader can tell a quiet run from a broken join, which is the
property this module's first version lacked.

## [1.23.1] — 2026-09-03

PATCH: the guard audit reaches every agent. v1.23.0's predecessor ported half
of the sandbox audit and said it had ported all of it.

`sandbox_audit.json` gained a `guards` block per stage on the legacy path
years ago; v1.22.0's parallel port called `_sandbox_audit` and stopped there.
`bundle._guards_by_stage` reads `sandbox_audit.stages.<stage>.guards`, and its
docstring asserts "`_guard_audit` runs on every stage of every run" -- **false
for every parallel run between v1.22.0 and this fix**. The viewer's guard pane
was empty and nothing said why, which is the failure mode that audit exists to
prevent, committed by the commit that claimed to fix it.

This is the more consequential half. A guard is a precondition without which a
check INVERTS rather than degrades: at most 0.31% of numeric cells in a real
corpus are GRIM-eligible at all, so a defaulted `data_type` is the single
likeliest cause of a false accusation, and this block is the only thing that
counts how often one is supplied.

MEASURED on the archived `wound_healing` tool-agent ledger once attached:
**51 guarded calls, 92 guard slots, 46 supplied** -- half the guards defaulted
on a run whose audit reported nothing at all.

## [1.23.0] — 2026-09-03

MINOR: the coverage census runs on the parallel pipeline. Every run now
carries an independent denominator, so "we checked N" has something to be
divided by.

`docs/specs/pipeline.md` has said since the v2 cutover that the enrichment
block -- "checkable census, completeness, statistics register, undelivered
files" -- "attaches to the ADJUDICATED object". It ran only on the retiring
legacy path. The census reads the paper's own tables with no model involved,
which is the whole of its value: it is the one number in the document that no
model produced. It is written to `findings.v2.json -> coverage_summary`,
declared in the schema, and stripped from the producer subset so the model
cannot write it.

**Six blocks ported**, and seven deliberately not. Ported: `checkable`,
`completeness`, `computation_audit`, `statistics_register` validation (the
floor tripwire, which had exactly one call site and it was the legacy writer),
`text_integrity`, `extraction` (the record `analyze_paper_parallel` was
discarding). `stage1_reconciliation` is NOT ported -- its inputs do not exist
in v2 and `adjudication.docket.n_not_adjudicated` answers the same question.
Six more were already answered in v2 (`coverage`, `checks_tally`,
`run_meta.exhaustive_checks`, `run_meta.delivery`).

**Two defects found by porting it, both fixed here:**

- **The census read the wrong source.** Its counters walked stage `messages`,
  and `_slim_messages` empties large `tool_result` payloads before they are
  persisted. MEASURED on the archived `wound_healing` run: the three
  `check_table` results are **0 chars** in `messages.tool_agent.json` and
  25,519 / 21,809 / 9,774 chars, untruncated, in `toolcalls.tool_agent.json`.
  A census computed from an archived run therefore reported nothing checked,
  and that was first diagnosed as the census being broken on v2 rather than as
  a probe reading an emptied file. `agent._tool_events` now accepts either
  source, prefers the ledger for the canonical tool name, and falls back to
  the message whenever the ledger's copy was truncated.
- **The prose reported one of three populations.** `render` compared
  `n_checked` (the `check_table` path) against `n_consumable` and never
  mentioned the batch rows or per-value calls sitting in the same summary. On
  `apple_cider` it printed "0 of 168 checkable cells were checked (0%)" beside
  **47 per-value calls and 39 findings**. Those counters were added in August
  precisely because a report once printed "**NOTHING IN THE TABLES WAS
  CHECKED**"; the counters landed and the sentence did not, so the denial
  moved from bold text into a percentage. It now names all three and says why
  they cannot be summed.

A census that cannot be built writes a NAMED absence rather than vanishing: a
paper with no surveyable table gets `no_cells_examined` and a note saying it
is "not a count of zero checkable cells". `n_runnable` and `never_submitted`
are carried across unrendered with their `predictor_disagrees` payload, by
decision: they are blocked on a per-cell sample size the census cannot resolve
(`missing_inputs: {"n": 29}` on airforce) and **7 of 15 archived runs report
more cells checked than were runnable**. Fixing that predictor is a separate
project.

**The viewer.** Twelve accessors bottomed out in
`report_obj.coverage_summary`, which no parallel run writes, and **nine failed
silently** -- five whole Coverage sections and three Overview bullets vanished
with no trace. All three places that DEFINE `cs` now fall back to
`D.coverage_summary`, which reaches every accessor. The "computed only on the
legacy analysis path" note was true when written and would have become a lie
the moment this landed, so `census_is_a_legacy_capability` now reads the
census's presence and not just the schema version.

Verified by building a real bundle from the `wound_healing` run: 124 cells, 57
consumable, 19 checked, 33% coverage in the payload, the legacy note stood
down, and the page's JS parses.

Two of the repo's own ratchets fired and both were right.
`test_v1_residue_ratchet` counts reads of structures only the legacy path
produces; `coverage_summary` has left that set because it was PORTED, and the
bound falls 25 -> 20. `test_census_note_is_true` guarded the claim that the
census is legacy-only, which this release inverts; it now guards the new fact
and the note's honesty. Separately, the new test that drives the real writer
was caught deleting three archived `analysis_code` scripts -- the writer MOVES
that directory -- and now copies the paper first.

Full suite: 9,609 passed, 158 skipped, 0 failed. lint-inert steady at 47.

## [1.22.0] — 2026-09-03

MINOR: the parallel pipeline writes `sandbox_audit.json`. Every run now says
mechanically whether anything ran outside the validated tool surface.

`docs/specs/pipeline.md:530` has listed it among a parallel run's outputs
since the v2 cutover ("per-stage union, as today"), and `README.md:296` calls
it "**read this one** ... a silently un-sandboxed run is otherwise
indistinguishable from a validated one". It was never written. MEASURED
2026-09-03: none of the four archived parallel runs has one, all three legacy
runs do, and `obligations.PARALLEL_TOLERATED` had come to excuse the absence
as a *"legacy-path artifact; present when a run came through agent.py"* — a
missing spec requirement wearing the clothes of a design decision. It is a
REQUIRED artifact now, and that exemption is gone.

- **The verdict wording has one source.** `compose_sandbox_audit` and
  `sandbox_run_meta` were lifted out of the legacy writer and are called by
  both. Duplicating the block would have let the two writers drift in what a
  breach is CALLED, which is the part a reader acts on.
- **Each agent is scored against its own ledger and its own findings**, joined
  by `producer`. The union rule was measured wrong on the legacy archive: 29
  top-level unbacked findings fell to 6 once each stage was scored against the
  tools it could actually call, so 23 of 29 were artefacts. The adjudicator is
  audited for breaches (a `Bash` call is a breach wherever it happens) but is
  answerable for no unbacked findings, because it does not derive them.
- **A run with no ledger writes the file anyway**, at `level: "not_measured"`
  with every count `null` rather than `0`. Omitting it would make "we could
  not look" indistinguishable from "we looked and it was clean", on the one
  artifact whose whole job is telling those apart; and `0` would assert there
  were no breaches when there was no measurement.
- `run_meta.sandbox` is set BEFORE `run_meta.json` is serialised. On the
  legacy path that block ran after the write, so the key reached the in-memory
  dict and never the file: 0 of 21 archived `run_meta.json` carry it, 17 of
  them beside a `sandbox_audit.json` whose verdict begins BREACH.

The audit returns `clean` on all four archived parallel runs. That is the
right answer for those runs and also exactly what a broken guard returns, so
`tests/test_sandbox_audit_v2.py` drives all five verdicts from known
positives: a `Bash` call is `severe`, an off-surface tool is `surface`, a
finding whose technique no call backs is `unbacked`, an undeclared forensic
tool is `off_allowlist` and not a breach, and a declared call backing its own
finding is `clean`. Two of those tests failed first on wrong INPUTS of mine —
`grim_test` is neither a tool name (`grim_check`) nor a technique (`grim`) —
which is the check working.

Full suite: 9,572 passed, 152 skipped, 0 failed. lint-inert steady at 47.

## [1.21.0] — 2026-09-03

MINOR: ad-hoc code and web text are no longer recorded as validated forensic
evidence. `_unbacked_findings` reads that flag, so the same paper may now
produce a different sandbox verdict.

`docs/specs/pipeline.md:334-338` has required the `agent_code` and `web`
ledger surfaces since the v2 cutover, with `validated` False for both --
"web text and ad-hoc code are never validated evidence, even though
`run_python_script` rides the forensic MCP server". They were never
implemented. **MEASURED 2026-09-03: all six `run_python_script` calls across
the four archived parallel runs were filed `surface: forensic_mcp,
validated: True`**, so a finding resting on a script the model wrote itself
was indistinguishable from one resting on a tool we wrote and test. That is
precisely the distinction the sandbox audit exists to draw.

- `run_python_script` is now `agent_code`; `WebSearch` / `WebFetch` (and
  grok's `web_search` / `web_fetch` spellings) are now `web`. Both are
  `validated: False`. Off-list forensic calls stay `validated: True` — being
  called by the wrong stage does not make our own arithmetic wrong, and that
  breach is reported through `surface`, unchanged.
- **What counts as WORK is now asked per producer**, which is a different
  question from what counts as evidence. The science-error analyst reasons
  through sandboxed scripts and the literature, so `agent_code` and `web`
  count as its work; the tool expert's whole job is the validated toolkit, so
  only `forensic_mcp` counts for it. Without this the `no_forensic_calls`
  refusal added in 1.18.0 would have refused a science agent that had done
  everything asked of it, purely because its tool moved surfaces.
- The ledger recovery digest (1.18.0) carries `agent_code` rows too: for the
  science agent its scripts and their stdout ARE the work being recovered.

One existing test changed meaning rather than breaking: a grok "Web search:"
display string is still not filed as a list breach — the invariant that test
was written for — but its surface is now `web` rather than `builtin_allowed`.

Full suite: 9,559 passed, 152 skipped, 0 failed.

## [1.20.0] — 2026-09-03

MINOR: the parallel writer emits two audits it never had, and a register that
was written by one path and read on another now reaches the viewer.

Four of the seven gaps the 2026-09-02 audit found between
`write_parallel_outputs` and the legacy `write_review_outputs`. Each was
measured against the four archived parallel runs before being closed.

- **`report.md` is scrubbed at write time**, as the legacy writer has always
  done. `bundle.py` scrubs its own copy on the way out, so the emailed
  artifact was never at risk; the forwarded `forensic_review/report.md` was.
  Measured: 0 home-paths or session ids across the four archived runs, so
  this closes a guarantee rather than a wound.
- **`run_meta.delivery`** is set from the tool agent's ledger, so a tool
  result that overflowed and never reached the model is stated. The viewer
  renders that section only when the key is present, so its absence was
  silent: a starved run read as an incurious one.
- **`handoff.audit` reads both ledger layouts.** It looked only for
  `toolcalls.stage1.json`, which no parallel run writes, so on every current
  run it kept the pre-flight sentence "no review directory given ... Pass -r
  <run> to check it" when one HAD been passed, and left `ready` True on an
  unmeasured leg. Verified against both archived layouts: the parallel run now
  answers "every tool call returned a usable payload".
- **`source_coverage.json`** is written per agent. Operator-facing by the
  standing decision; the bundle still recounts inline so the two cannot drift.
- **The statistics register reaches the viewer.** The parallel pipeline writes
  it at the TOP LEVEL of `findings.v2.json`; the viewer read
  `coverage_summary.statistics_register`, a key no parallel run has, so the
  block rendered empty on every current run. **Measured: 25 rows on
  apple_cider and 28 on cerebrolysin_flow, written and rendered nowhere.**
  Verified by building a real bundle: 28 rows now reach the payload and the
  viewer reads them.

Two things the repo's own guards caught while this was being written, both
recorded because they are the pattern rather than the incident: `unregistered()`
would have flagged `source_coverage.json` as an unannounced output on a real
run (the pipeline tests drive the writer with fakes that produce neither it
nor `report.pdf`, so the conservation test was never asked) — now registered,
with a test that asks directly; and `lint-inert` refused the first cut of the
two new audits over swallowed exceptions, so both now record their failure,
`delivery` as an explicit `ok: null` with the reason and the tally as a named
`source_coverage.error.txt`.

## [1.19.0] — 2026-09-03

MINOR: `mode="single_stage"` is removed. A caller passing it now gets a
`ValueError` naming the two modes that remain.

It was the original one-shot markdown report, and it had **no tests at all**
(`grep single_stage tests/` returned nothing) while `docs/specs/pipeline.md`
recorded it as "untouched, forever out of scope". Untested and permanent is
the worst of both: every prompt edit, severity change and guard since v1.0.0
had to keep working for a path nobody ran and nothing checked.

- `agent.py` loses the branch, `SINGLE_STAGE_PROMPT` and `_build_legacy_prompt`
  (87 lines).
- `analyze --single-stage` is gone. `--two-stage` survives as a deprecated
  no-op beside `--parallel`, so existing scripts keep working; the two-analyst
  review is the only non-legacy pipeline, so neither flag can select anything
  else. `--legacy-two-stage` is unaffected.
- `examples/batch_analyze.py` drops it from `--mode`; the GUI launcher drops
  the option it offered.

This is the first step of the legacy retirement. `two_stage_legacy` STAYS: the
audit found that removing it would also remove seven behaviours the parallel
writer never implemented — `sandbox_audit.json` among them, which
`docs/specs/pipeline.md:530` requires and `README.md` calls "read this one" —
and would delete ~37 tests that guard live code through legacy entry points.

## [1.18.0] — 2026-09-03

MINOR: a producer stage that made no forensic calls now REFUSES instead of
filing an empty document, and the bounded retry recovers from its own ledger
instead of re-running the stage. The same paper may now produce different
findings.

_(Bookkeeping: the commit carrying this change is titled "v1.17.0". That
number was taken by the image-adjudicator release landed the same evening;
this work is 1.18.0. The bump script asserted on the version it expected to
find, failed closed, and the commit went in without it — which is the failure
mode CHANGELOG's "bump in the same commit" rule exists to prevent, arriving
by a route the rule does not cover.)_

**The measurement.** Diagnosed from the archived transcripts of 1.15.0's six
grok runs; no paid runs. All three grok parallel runs lost an analyst, while
the legacy sweep completed cleanly on the same three papers (91 / 105 / 66
tool calls, zero limitations). **Correction to an earlier claim in this
file:** it is 3 of 3 *grok* runs, not 4 of 4 across both backends —
apple_cider (claude) had an empty FIRST attempt whose retry SUCCEEDED, and its
final document carries 33 tool-expert findings. Backend matters: on claude the
document arrives through a dedicated structured-output channel (that run's
tool-agent transcript holds ONE text emission of 2 output tokens beside 33
findings in `result.structured_output`); on grok the document is assistant
text, composed for real only in the final turn.

- **The retry recovers instead of re-deriving.** On `wound_healing` the tool
  expert made 90 calls, began writing its report, degenerated into
  `n.n.n.n.n…` mid-document and recovered by filing ONE finding. Its ledger
  held **78 forensic results — 1 `highly_suspicious`, 13 `suspicious`, 12
  `indeterminate`, 48 `consistent`** — and the bounded retry re-ran the whole
  stage from scratch, came back empty, and discarded all of them. The
  `truncated_docket` detector fired correctly; the RESPONSE was wrong. With
  forensic calls on the ledger the retry is now a document-only turn: the
  producer's own calls and results as the prompt, no forensic tools, one turn,
  composing from the ledger rather than from the 238K-token transcript it
  degenerated under. An EMPTY ledger still re-runs the full stage — there is
  nothing to recover from.
- **A stage that never called a tool is a named refusal.** On `airforce` the
  tool expert took one turn, 36,169 input tokens, **184 output tokens, zero
  tool calls**, `end_turn` in 7.4 s: a schema-valid EMPTY document, and the
  retry did the same. Downstream that is indistinguishable from a paper with
  nothing wrong. The stage now carries `error_subtype: "no_forensic_calls"`,
  contributes nothing to the merge, and states that the silence is ours. It is
  deliberately absent from `_CUT_OFF_SUBTYPES`, so no predicate mistakes it
  for a budget or timeout cut.
- **Falsified, so nobody re-runs it:** the v2 producer schema is not more
  permissive than v1 (both reject the empty skeleton) and not more complex (v1
  is larger — 35,745 vs 34,508 bytes, same depth, a 69-value technique enum
  against 57). Neither path caps `max_turns`. The user prompts are
  byte-identical; `_build_sweep_prompt` is shared. **Not yet isolated:** why
  grok composes a 69,294-char / 42-finding document for the legacy sweep and
  degenerates for the tool expert on the same paper. The remaining difference
  is the system prompt (89,792 bytes assembled against 76,482). That needs a
  paid A/B and is not a prerequisite for either fix above.

## [1.17.0] — 2026-09-02

MINOR: the image adjudicator's prompt, schema and guards all changed, so the
same paper may now produce different verdicts.

**MEASURED after the change**, same corpus, same sweep, same 760 judged
groups, codex:gpt-5.6-luna re-judging all 200 fired papers:

| | before | after |
|---|---|---|
| explanations naming a caption | 129 of 760 | **174 of 760** |
| explanations naming Methods / a protocol | 12 of 760 | **137 of 760** |
| clears with no quote | 188 of 465 (40%) | **166 of 434 — every one a pixel category** |
| text-category clears resting on nothing | 188 | **0** |
| PubPeer positives fully cleared (false-clear candidates) | 15 of 37 | **12 of 37** |
| paper-level recall after adjudication | 22 of 69 (31.9%) | **25 of 69 (36.2%)** |
| in-scope paper-level | 15 of 38 (39.5%) | **16 of 38 (42.1%)** |
| in-scope figure-level | 10 of 38 (26.3%) | **11 of 38 (28.9%)** |
| figure-level recall after adjudication | 15 of 68 (22.1%) | 14 of 68 (20.6%) |

Where the surviving text-category clears now rest: the Methods 90, a
figure's own caption 190, a citing sentence 9, elsewhere in the paper 27.
Twenty groups were demoted, none of them for a reason that blames the paper
for our own gap.

- **An image clear must rest on text about THIS figure.** The prompt has
  always told the adjudicator to read both captions first, and nothing
  checked that it had. MEASURED 2026-09-02 (Masliah, 198 papers, 760 groups,
  codex:gpt-5.6-luna): 129 of 760 explanations mentioned a caption, 12 the
  Methods, and **188 of 465 clears (40%) quoted nothing at all** -- including
  29 of the 51 clears on the 15 PubPeer positives the pass cleared outright.
  Three changes. The schema now REQUIRES `figures_reported`, one entry per
  figure in the group naming what it reports and where that was read, so the
  caption-first step is an output rather than a hope. `_apply_image_adjudication`
  takes the `figure_context` the prompt was built from and enforces, DOWNGRADE
  ONLY: the six categories that are claims about what the paper says
  (`same_condition_in_both_figures`, `same_field_different_channel`,
  `stated_representative_image`, `overview_and_detail`, `paired_design`,
  `shared_template_backdrop`) must quote the paper, and the quote must land in
  the caption of an involved figure, a sentence citing it, or the Methods; the
  four a reader can SEE (`chart_furniture`, `plot_template`,
  `publisher_furniture`, `producer_tiling`) keep their exemption;
  `same_condition_in_both_figures` needs two distinct figures and a caption
  quote; and a byte stream placed twice cannot be cleared as two channels, two
  timepoints or a crop of itself. Where we could read no caption and locate no
  Methods, the demotion sentence names that as OUR gap, not the paper's.
- **The per-group haystack is normalised, and checked independently.**
  `build_haystack`'s contract is that its texts are already normalised --
  `classify` normalises only the quote. A raw haystack fails every lookup, and
  a failed lookup DEMOTES, so the guard would have demoted every honest clear
  (LESSONS #4). It is also classified independently of the paper-wide pass: a
  paper whose body text could not be loaded still has captions from its XML.
- **The judge is shown the figure as printed** -- the caption-anchored crop or
  the publisher render, by absolute path -- so a caption's "(F, left)" can be
  paired with our `xref117-seg8`. 3,255 such crops were already on disk and no
  consumer read them.
- **A whole-figure PMC render was invisible to the judge.** The prompt and
  `review_media._panel_png` composed `panels/<pid>.png`, but the harvest
  writes `panels/pmc/pmc_<file>.png` and names it only in
  `panel_index.json`; 11 XML-only groups came back `insufficient_evidence`
  saying the images could not be opened. Both now resolve through the index.
- **The cross-paper writer never passed a figure map**, so 0 of 13,232
  placements in the corpus' `panels.json` carried a figure label while the
  sweep's index had 76%. `describe_paper` now loads `figures/figures.json`
  (or extracts one) and `FEATURE_VERSION` is 3 so the stale files are rewritten.
- **The scorecard reads all of it**: `text_basis` (category x where the quote
  was located), `demotions`, and `figures_reported_source`, rendered as two
  tables. A verdict written before this release reads `not recorded`, never
  zero.

- **Masliah image benchmark, corpus-wide, after the stale-pristine repair**
  (`eval/runs/image_masliah/scorecard.md`, 2026-09-02): 907 papers, 734
  examined, 200 fired and every one adjudicated by codex:gpt-5.6-luna
  alone. Pre-adjudication figure-level recall 23/68 (33.8%), paper-level
  37/69 (53.6%); after adjudication 15/68 (22.1%) and 22/69 (31.9%); in
  scope 10/38 and 15/38. Fire rate 114/734 = 15.5% after suppression, no
  tier above the 20% alarm (transformed_match was 23.8% before). Codex
  cleared 465 of 765 groups (60.8%) and fully cleared 15 of the 37 fired
  PubPeer positives, 8 of them figure-level hits; three of those were read
  beside their exhibits and none is a plain false clear (label-grid
  matches and a near-blank hash pair), but its clearing rate is roughly
  three times the require-all pair's measured earlier, so a codex-only
  verdict is reported as such and never as the pair's. Attribution sums to
  69: hit 15, examined_no_fire 23, out of scope 27, wrong figure 3, not
  harvested 1. Precision is still null: no human label is scoped to this
  run.

- **A clear must cite an exhibit that exists.** The guard demoting an image
  group "adjudicated unseen" tested only that the model's `images_read`
  list was non-empty -- a model-written string, not a fact about the disk.
  MEASURED 2026-09-02 over 1,190 entries from a codex/Luna pass: 29 named
  files that do not exist (a space inserted into a directory name, a path
  component dropped), every one the basename of a real exhibit, and one
  clear rested on nothing else. `image_forensics/exhibit_paths.
  resolve_images_read` accepts an entry as given, relative to the paper
  directory, or by basename under the directories an exhibit can live in;
  the verdict record carries `images_verified` / `images_unresolved`; a
  clear resting on nothing that exists is demoted with its own sentence.
  Both appliers (within-paper `_apply_image_adjudication`, cross-paper
  `apply_cross_paper_adjudication`) and all three callers pass their paper
  directories; without one the old non-empty test stands.

- **`--backend codex` is now usage-guarded.** It used to be reported
  `usage_guard: unsupported_for_backend` and ran straight into its 5-hour
  window. `usage_guard.probe_codex_usage` speaks `codex app-server`'s stdio
  JSON-RPC (`initialize`, `initialized`, `account/rateLimits/read` -- the
  call the codex TUI's own status line makes) and returns the 5-hour and
  weekly `usedPercent`; `probe_usage` dispatches on the backend, so the
  gates, thresholds (`METASCIENCE_USAGE_THRESHOLD` 90 / weekly 97),
  pause/stop behaviour and fail-open contract are the Claude ones,
  unchanged. Grok stays `UNSUPPORTED`. `python -m metascience_agent.usage_guard
  codex` prints the gauges; measured 2026-09-02 mid-run: 5h 33%, week 27%.

- **A pristine copy dies with the run that made it, and the writer is not the
  detector.** Found by reading the final Masliah scorecard, not the code:
  figure-level recall printed as 1 of 33 with most positives attributed
  `not_run_this_sweep`, after a sweep that had examined 734 papers. The
  adjudicator keeps a pristine copy of the detector's unjudged answer so a
  re-judgement starts from the detector rather than a thinned list; nothing
  invalidated that copy when the detector changed, so after the 1.16.0
  fingerprint change re-ran 907 papers, the next adjudication judged the
  OLD copies and wrote them back over the fresh answer on 176 papers, each
  stamped with the superseded fingerprint and therefore dropped from
  scoring. Two guards, both tested against the shape that failed:
  `retain_paper` (the single writer) deletes the pristine on every new
  answer or refusal, and `pristine_result` validates both the pristine and
  the live file against the STATUS file's stamp -- the status file is
  rebuilt from the child on every run and is the authority on which run
  produced the current answer. A stale pristine is discarded and rebuilt; a
  stale live file raises `StaleAnswer`, which the corpus driver records as
  `stale_answer_needs_resweep` instead of judging the wrong run. And
  `retain.py` leaves `FINGERPRINT_FILES`: a change to how an answer is
  packaged does not change the answer, and including the writer turned a
  one-line fix into a 907-paper re-run plus a 200-paper re-adjudication.
  Consumers tolerate a missing field in an older file instead.

## [1.16.1] — 2026-09-02

PATCH. Two things the full suite caught after 1.16.0 was pushed (9,351
passed, 2 failed, 1 error): `ruff --fix` had removed three `progress`
aliases from `cli.py` that `tests/test_progress_callback.py` imports FROM
`cli` -- restored with a `noqa` saying why -- and `report.pdf`, newly
written by the parallel writer, was not in `obligations.PARALLEL_ARTIFACTS`,
so the conservation test flagged it as an unannounced output. Registered as
optional (a machine without a renderer still produces a review; the reason
travels in `run_meta.pdf_error`).

## [1.16.0] — 2026-09-02

Audit follow-ups. MINOR for one reason: the legacy stage-2 prompt's measured
verdict-band claim changed (below), and a prompt claim that governs
interpretation is a MINOR by the rule at the top of this file. Everything
else here is PATCH-grade.

- **A stage cut off by the clock now says so.** `run_meta.stages.*.
  truncated_by_timeout` was written by `_stage_meta` and read by nothing
  while its sibling `truncated_by_budget` was rendered; the parallel path
  reported such a stage as "produced no parseable findings JSON" -- measured
  live on this release's cerebrolysin_flow grok run, whose science agent
  stalled. The viewer's stage table, the image channel in the workbench
  index, and the report's limitations now name the timeout; the render
  contract in `tests/test_output_is_read.py` pins it.
- **A missing report.pdf carries its reason, and the default pipeline
  writes one.** `report_render.last_pdf_error()` had held the reason since
  defect #163 with no caller; `run_meta.pdf_error` now records it and the
  viewer prints it. Separately, `analyze --pdf` (default on) reached nothing
  on the parallel path: only the legacy writer rendered a PDF, while the
  README listed `report.pdf` among every run's outputs. `write_parallel_outputs`
  renders it, best-effort, before run_meta.json.
- **The hand-off audit no longer says "ok" over tables it could not read.**
  `prepass.paper_tables` returns a list subclass carrying `.problems`; the
  one caller that wanted them wrapped the result in `list(...)`, which
  dropped the attribute, so the audit's `tbl_problems` was always empty.
  ruff reported it as an unused local; the unused local was the symptom.
- **Legacy runs record `mode_requested`.** Their run_meta said `"mode":
  "two_stage"` -- the deprecated alias name for the PARALLEL pipeline --
  beside a scorecard saying `two_stage_legacy`.
- **`stage2_editorial.md` re-measured**: the middle verdict band in 28 of
  38 archived reports (was 48 of 57 on 2026-08-22; the 22 that left were
  the `funder_demo_2026-08-10` reviews, all middle-band, and the three grok
  legacy eval runs above joined, two of them middle-band). The test that
  pins this claim is green again.
- **ruff error class pinned at zero** for `src/` (`tests/test_ruff_errors.py`):
  53 unused imports / placeholder-less f-strings removed, the dead locals
  deleted by hand, bundle.py's deliberate locator re-exports marked. Four
  stage-record keys the audit found written and read by nobody
  (`current_tool`, `mcp_discovery`, `usage_guard`, `backend_default_model`)
  are declared operator-only with reasons.
- Docstrings: `agent.py` no longer describes the serial pipeline as the
  default; `tool_reference.md` lists the four tools it omitted; four
  citations of local scratch memos say they are untracked.
- NOT done, deliberately (plan §A12): converting the ten consequential
  `except: return {}` sites in bundle.py / webapp_index.py / jats.py to
  recorded problems. Each needs a renderer and a rebuilt, executed bundle
  to verify (LESSONS.md, entry 6); `tests/test_inertness.py` keeps
  `MAX_CERTAIN` as the ratchet.

- **MEASURED: legacy serial vs parallel, on grok-4.6, at v1.15.0, six runs
  (2026-09-02, 12:47-15:50 UTC).** Weighted recall / false positives /
  verdict match / analysis cost:

  | fixture | legacy serial | parallel (this release) | parallel v1.3.0 (2026-08-22) |
  |---|---|---|---|
  | airforce | 0.375 / 0 / **no** (`unresolved`) / $0.74 | 0.375 / 0 / yes / $0.37 | 0.375 / 0 / yes / $0.70 |
  | wound_healing | 0.333 / 0 / no / $0.57 | 0.556 / 0 / no / $1.15 | 0.556 / 0 / no / $0.82 |
  | cerebrolysin_flow | 0.231 / 0 / yes / $0.59 | 0.538 / **1** / yes / $0.57 | 0.846 / 0 / yes / $0.77 |

  The parallel pipeline recalls at least as much on every fixture (equal on
  airforce, +0.22 and +0.31 on the others) and gets the airforce verdict
  right where the legacy body softens it. Two caveats, both read off the
  run records rather than the scorecards: the cerebrolysin_flow parallel
  run's science agent STALLED (`error_stalled`, `truncated_by_timeout`), so
  its 0.538 against v1.3.0's 0.846 is a truncated run, not a pipeline
  regression -- and the report described it as "produced no parseable
  findings JSON", the wording the timeout fix below replaces. Its one false
  positive is the tool expert modelling a Wei-Lachin combined CI as
  independent Wald averaging of the component intervals. On every parallel
  run the tool expert's first attempt returned no tool calls and the
  bounded retry did the work (23 min on airforce). The cerebrolysin_flow
  legacy judge returned EMPTY `judge_notes`, the defect CLAUDE.md records
  for the v1.11.1 apple_cider run. Legacy runs live in
  `eval/runs/<paper>/forensic_review_legacy/` + `scorecard_legacy.json`.
  Whether the legacy body is deleted is Dan's call on these numbers.

- **Two more modules that skipped for months and failed the first time they
  ran.** The corpus consolidation made their fixture paper resolvable;
  the full suite then showed 10 failures that had never been seen.
  `test_repair_log.py` (9): its fixture copied the paper but never
  materialised `markdown/body.md`, the derived file every test edits -- the
  pipeline writes it in `ensure_paper_extracted`; the fixture now does the
  same. `test_run_horizon.py` (1): it looked for the newest run schema under
  `test_pdfs/` only, which holds 39 v1 runs, and read the fixture's age as a
  pipeline drift; it now reads both archives (the four v2 runs are in
  `eval/runs/`). Full suite after these: 9,368 passed, 152 skipped, 1 known
  red (the prompt claim above).

- **Docs re-measured.** CLAUDE.md: test count 9,494 (was "~8,375"); the
  two MCP-withheld tools named correctly (they are the CLI-only pair, not the
  R tools); `CLI_ONLY` pointed at `registry.py` where it lives; the lapsed
  "for one release" promise replaced by the eval gate; `single_stage` marked
  untested. README: the three `batch`/`usage` commands on the moved corpus
  path; the preflight sample (was "54 tools, stage1 52"); the mermaid tool
  count (56, was 54); the test count (was "~6,240"); an extras table
  (`images`, `pdf`, `db`, `html` were undocumented and `html` pins one
  machine's path); a section for the image-track verbs. Six docs with no
  date now open with their git dates and a status line. The GUI launcher's
  placeholder path named another machine; `eval/reference_set.json` roots
  updated.
- **Repo hygiene.** `scratchpad/` (392 tracked files, 102 MB, 44 MB of
  non-LFS binaries, read by nothing -- nine tests EXCLUDE it from archive
  walks) is untracked and ignored; the files stay on disk. The two
  `cerebrolysin_run*` corpora get the same LFS `.gitattributes` as their
  siblings (their 148 PDFs/PNGs are plain blobs today; history is not
  rewritten). Stray empty `panels/` and `figures/` at the root removed. ruff:
  `N818` off (eight public exception names), `F811` off for `tests/` (pytest
  fixture shadowing, 83 of 84 hits).
- **KNOWN RED, scheduled:** `test_prompt_claims_are_dated.py::
  TestTheVerdictClaimStaysCurrent` -- `stage2_editorial.md` says the middle
  band in 48 of 57 archived reports; with `funder_demo_2026-08-10` gone the
  archive says 26 of 35. The prompt is read by the legacy eval runs in
  flight, so the refresh lands when they finish (a prompt-claim change is
  MINOR by the rule above).

- **Grok runs died before spend under grok 1.0.13: "folder untrusted".** The
  sandbox ROOT was in `~/.grok/trusted_folders.toml` exactly as the backend
  writes it, but grok's trust grant now covers only subdirectories "of the
  same repository", and the sandbox root is not a git repository, so no
  per-run `run-<uuid>/` was covered and `grok mcp doctor` refused to start
  the project-scoped MCP server. Measured on the first six eval runs of this
  release, all `MCPUnavailable` within seconds. `GROK_FOLDER_TRUST=0` now
  rides in the sandbox subprocess env -- the run AND the doctor probe, so the
  probe vouches for the run it precedes -- and the same run dir reports
  handshake OK, 17 tools discovered. Under grok 1.0.5 (the v1.3.0 runs)
  trust cascaded and none of this was needed; the root entry is kept for
  versions where it still does.

- **Three test guards had silently stopped guarding.** `test_tripwire.py`'s
  archive replay globbed a fixed depth from the working directory and matched
  0 of the 22 archived runs after the corpus consolidation, so it skipped
  green; it now resolves two depths from the repo root and a sibling test
  asserts the archive is FOUND whenever `test_pdfs/` exists.
  `test_bundle.py`'s shared-walker check named its fixture without the
  `test_pdfs/` prefix and skipped with the fixture present.
  `test_corpus_invariants.py` pinned one machine's WSL path, so its six
  ratchets skipped everywhere else; it now resolves `METASCIENCE_PAPERS_ROOT`,
  then the sibling papers checkout -- and on this machine the six ran for the
  first time and held. Also: `funder_demo_2026-08-10` dropped from
  `test_sweep_false_positives.CORPORA`; a vacuous trailing `assert True`
  retired in `test_output_is_read.py`; a re-import removed in `test_glyphs.py`.

## [1.15.0] — 2026-09-02

MINOR: three new CLI verbs, a new `db-push` kind, a changed scoring join, and
an eval flag. Two reviews across this boundary are not directly comparable.

- **`metascience eval --legacy-two-stage`** runs the retiring serial pipeline
  (`mode="two_stage_legacy"`) into `eval/runs/<paper>/forensic_review_legacy/`
  and `scorecard_legacy.json`, BESIDE the parallel run, never over it. Every
  scorecard now records `pipeline_version`, `mode`, `backend` and `model`.
  Measured before this existed: `baselines/` holds corpus-state snapshots, not
  eval data; the only serial-mode recall anywhere is apple_cider's git history
  (0.545 on 2026-07-17, 0.091 on 2026-08-09, both claude, pre-v1.0); and
  airforce / wound_healing / cerebrolysin_flow each have exactly ONE archived
  run -- **v1.3.0, parallel, grok-4.6, 2026-08-22: recall 0.375 / 0.556 /
  0.846, 0 false positives each, verdict match yes / no / yes** -- so the
  legacy body's deletion (promised "for one release" at v1.0.0) was gated on a
  comparison nothing could produce. Those three numbers are recorded here
  because the grok re-run at this version overwrites them in place.
- **Corpus consolidation.** The four papers that lived at a top-level
  `high_value_pdfs_to_run_on/` join the canonical
  `test_pdfs/high_value_pdfs_to_run_on/` (which already held 8; 12 paper
  directories in total now). The retired
  `.pdf4llm_checkpoint.json` is dropped with them. `funder_demo_2026-08-10/`
  (47 files, the 2026-08-10 blinded demo) is removed; the four measured rows
  in `docs/VALUE_REGISTER_MEASUREMENTS.md` that walked it are now history.
- **The image track lives in `image_forensics/`, runs over a corpus on its
  own, and is scored against PubPeer.** Nine modules moved from `tools/`,
  `extraction/` and the package root (pure rename first, so history follows);
  the old paths are `sys.modules` aliases, not copies, because ~20 tests patch
  attributes on the old module objects. Importing the detector FIRST -- what
  the child process does -- was a circular import that 1,322 targeted tests
  could not see; `tests/test_image_forensics_package.py` imports each module
  in a fresh interpreter and runs the child by both paths.
  - `metascience image-sweep CORPUS`: one child subprocess per paper through
    `agent._run_forensic_track` (a hung or crashing PDF costs one paper, killed
    as a process group), an append-only manifest, and a per-paper STAMP --
    sweep id, detector fingerprint, flags, the furniture set as it applied to
    this paper, inputs digest -- so a re-run skips exactly the papers whose
    answer could not have changed and prints why each other paper is not
    done. Corpus furniture is a second pass that re-runs only the papers it
    touches. Every paper keeps `panels/image_track_status.json`; fired papers
    keep `image_duplication_findings.json`, a review manifest, and a
    findings-v2 document in `forensic_review_image/` (`db-push` kind
    `image_track`). Segmentation is ON here; `analyze` stays off. No
    adjudicator option: the verb never spends. Replaces
    `examples/run_image_track_on.py` and `calibrate_image_dup.py`.
  - `metascience image-labels CORPUS` (network) and `metascience
    image-benchmark CORPUS --labels ...` (files only): a dated scorecard
    (`scorecard.json`, dated copy, `scorecard.md`) with figure-level recall as
    the PRIMARY number, both denominators (examined positives, ALL positives)
    beside every rate, one attribution bucket per positive summing to the
    positives (`no_pdf`, `refused:<subtype>`,
    `alleged_figure_panels_excluded:<reason>`, `examined_fired_wrong_figure`,
    `hit`, ...), per-figure KIND (blot / micrograph / graph; heuristic or
    human sidecar, source counted), and a precision block from workbench
    labels joined by the SAME `IMGDUP-N` numbering `_findings_rows` uses --
    the old scorer numbered context groups too and joined human labels to
    the wrong group. `--sweep-id` compares stamp EQUIVALENCE (fingerprint +
    flags), not the run name. Replaces `examples/score_against_pubpeer.py`
    and `pubpeer_ground_truth.py`.
  - Found by reading the first real sweep's output: the exhibit renderer
    printed `wrote <png>` to stdout ahead of the JSON envelope, so a paper
    that ran was filed as `track_output_invalid`. Under `--json` the child
    now sends every print to stderr; a test spawns the real child on a firing
    paper and asserts the first byte is `{`.
  - `webapp_index.run_kind()` is the one derivation of what produced a v2
    document (`db_push` copies it into `runs.kind`): the numeric channel no
    longer reports the numeric pipeline as `ran` on an image-only review
    directory, and `corpus_stats` no longer lets a newer image-only run
    displace a full review as the paper's current document.
  - MEASURED on the 38 PubPeer positives with a PDF (2026-09-01): 562 panels
    excluded as `low_texture_blot_channel_uncalibrated` against 1,342 eligible;
    Masliah's allegations are mostly blots, so that exclusion is the recall
    ceiling the benchmark exists to move. 31 of 69 positives have no PDF on
    disk; 19 of the 21 checked have a PMCID.
  - **Baseline scorecard** (`eval/runs/image_masliah/`, sweep
    `2026-09-02_baseline_seg`, 907 paper dirs, 560 ran, 347 refused, 0
    failed, 449 s at 12 jobs): figure-level recall 11 of 37 examined
    positives with a named figure = 29.7% (21.2% of all 52); paper-level 26
    of 51 = 51.0% (37.7% of all 69); fire rate 155 of 560 = 27.7%,
    `transformed_match` 23.8% -- FORMAT ALARM. Determinism: 40 papers at 1
    job vs 12, 0 differing rows.
  - **`analyze --segment-montages`** (default OFF, gated on the alarm) reaches
    the child through `_run_image_track(segment_montages=)` and is recorded
    on the stage record. Production runs had never segmented.
  - **v2 image rows carry `inputs.spans_figures`** and say "across figures"
    in the title -- the one measured prior (63% vs 36%), as data for ordering,
    never a gate. The v1 row contract is unchanged.
  - **PMC figure renders for papers with no PDF.** `metascience
    image-fetch-pmc-figures` (network, serial, delayed, never from the sweep)
    resolves each JATS `<graphic>` to PMC's blob CDN via the article page --
    the `/bin/<file>` scheme is 404 on PMC and 520 on Europe PMC, the OA web
    service endpoint is gone (2026-09-02) -- into `pmc_figures/` with a
    manifest whose refusals are named. `panels.harvest_pmc_figures` reads them
    as channel `pmc_render` (NOT original bytes: perceptual and keypoint tiers
    only; segmented under `--segment-montages`); `analyze_paper_images` takes
    `pdf_path=None`; `run_track` falls back to the renders instead of
    `no_pdf`. Found by the channel's first test: tiers 3 and 4 skipped every
    byte-identical pair as "tier 2's" while tier 2 refuses non-original
    channels, so two identical renders were compared by nobody; the skip now
    requires original bytes on both sides.
  - **MEASURED after the fetch** (same sweep id, resume re-ran only the
    papers whose inputs changed): renders fetched for 16 of the 18 no-PDF
    positives (PMC lists no figures for the other 2), all 16 ran, 10 fired,
    0 retain errors; the previously examined population is unchanged at 155
    of 560. Figure-level recall 16 of 50 examined positives with a named
    figure = 32.0% (was 11 of 37 = 29.7%), and of ALL 52: 30.8% (was 21.2%);
    paper-level 36 of 67 = 53.7% (was 26 of 51), of ALL 69: 52.2% (was
    37.7%). `refused:no_pdf` 18 -> 2. Both scorecards are kept under
    time-stamped names -- the first post-fetch run overwrote the baseline's
    dated copy because the name carried only the date.
  - **`metascience image-adjudicate`** -- the paid pass that suppresses false
    positives on a retained sweep, isolated from the text pipeline.
    Downgrade-only (a model may release a group from the severity ladder and
    nothing else); judges the detector's PRISTINE answer, kept beside the
    live file, so every model sees the same groups and a re-run never judges
    an already-thinned list; several `backend:model` judges with a group
    cleared only when EVERY one clears it; the pass recorded on the status
    file and one row per paper in the sweep's `adjudication.jsonl`.
    `image-sweep --adjudicate` chains it, and the sweep itself still never
    spends.
  - **Codex can adjudicate images**, on two measured fixes. `view_image` is
    disabled on every forensic invocation, so `build_invocation(vision=True)`
    re-enables it for that stage alone (a clear made without opening an image
    is demoted to `insufficient_evidence` in code, so without this a codex
    adjudicator could only ever refuse). And `codex_strict_schema` did not
    give a bare `const` or `enum` the `type` OpenAI's strict validator
    requires: the stage died with exit 1 and an EMPTY stderr, the 400 buried
    in codex's own stdout stream. Four shipped schemas carry such a node.
    `_run_stage` now keeps a five-line tail of the child's raw stdout and
    puts it in the StageError when stderr is empty. `gpt-5.6-luna` is a real
    codex model here; plain `luna` is refused for ChatGPT accounts.
  - **The ground truth records the MECHANISM of each allegation.** A visual
    review of the sleuths' own annotated PubPeer images records, per figure,
    a kind and one of `cross_panel_within_paper` / `intra_panel_clone` /
    `cross_paper` / `other_integrity`. MEASURED over 45 reviewed positives
    (144 figures): 70 / 53 / 8 / 13 -- only about half of what PubPeer
    flags is reachable by a detector comparing pairs of distinct panels, and
    blots are overwhelmingly intra-panel while micrographs are
    overwhelmingly cross-panel. `image-benchmark --image-review` merges it;
    the scorecard gains `recall.figure_level_in_scope` /
    `paper_level_in_scope` and a `scope` block, and an out-of-scope positive
    is attributed `out_of_scope:<mechanism>` rather than counted as a
    detector miss. `detectable_by_panel_pairs` is DERIVED from the
    mechanism, never trusted from the reviewer.
  - **Coverage, via the sibling `fetchpdf`**: run over the 202 Masliah
    papers the sweep refused for `no_pdf`, it recovered 178 (70 PDF, 104
    XML, 4 HTML); the 70 PDFs moved into the corpus and the resumed sweep
    examined 66 of them, 12 firing.
  - **The furniture set persists at corpus level and only grows**
    (`<corpus>/.image_track/furniture.json`). After one furniture pass the
    re-run papers' indexes no longer list the withheld streams, so a
    re-screen of the indexes found 0 streams where the previous pass had
    ended with 22; a journal mark does not stop being one when we stop
    indexing it.

## [1.14.0] - 2026-09-01

- **The 1–9 ladder has no ceiling.** `PIPELINE_MAX = 8`,
  `ADJUDICATOR_MAX_DEFAULT = 7`, `ADJUDICATOR_MAX_MANIPULATION = 8`, the
  manipulation 8-gate (`_manipulation_evidence_ok`) and the analyst
  evidence-CLASS ceilings (`PROVISIONAL_CAP`: absolute 5 / probabilistic 4 /
  descriptive 2 / not_computational 5 / no_tool_exists 3 /
  tool_existed_unused 3) are gone. Every role — tool expert, science-error
  analyst, adjudicator — may write any rung 1–9. Dan's call, 2026-09-01: the
  layered ceilings had become too complicated to reason about.
  - **What remains** bounds the CHANNEL and the MOVEMENT, not the level:
    `AGENT_CODE_CAP = 4`, `FAST_SCREEN_CAP = 4`, `MODEL_KNOWLEDGE_CAP = 3`,
    `MODEL_READING_CAP = 3` (tool technique, no call cited),
    `QUARANTINE_CAP = 3`; the adjudicator's +2 upgrade limit with its
    `merged_pattern` exemption; `ACCUSATORY_MIN = 3`.
  - **Behavioural consequence:** with the gate gone, a `manipulation`
    upgrade is +2-bound like `consequence_reassessed`, so a provisional 5
    asking for 8 now lands on 7 (it used to reach 8 through the gate). 9 is
    reachable from a provisional ≥ 7, from any provisional via
    `merged_pattern`, or directly from an analyst whose channel carries no
    cap. `n_nine_clamped` is removed from the adjudication summary and
    schema.
  - **Prompts:** the composition rules (`_COMPOSITION_RULES`, section 4 of
    `adjudication.md`), "9 is never yours to assign", "past the caps",
    "move at most one level" and "levels 6–7 belong to the adjudicator" are
    stripped. The ladder, its per-rung boundary tests and the one question
    are the whole instruction. Sentences describing channel caps that still
    bind (model-knowledge ≤ 3) stay.
  - `clamp_provisional` drops its `evidence_class`/`technique` parameters;
    an unknown technique is no longer clamped to 2 or reported by it (the
    schema enum rejects it upstream). `LADDER_VERSION` 2 → 3;
    `severity_ladder.json` / `constants.gen.ts` regenerated.
  - Tests: `test_manipulation_gate_evidence.py` deleted (its clear-quote
    class moved into `test_adjudicate.py`); new known-positives pin that 9
    survives every path that has no cap and that each channel cap still
    fires from 9.

- **The workbench says whether anyone has opened a paper.** A `Viewed?` column
  on the project table, fed by `views.json` written beside the paper whenever
  a review page is opened — by anyone, named or not. FOUR states, because a
  yes/no would fuse facts that are not the same: `yes` (a view is on file),
  `yes*` (no view on file, but a human recorded a decision, so the paper was
  demonstrably open — MEASURED 2026-08-22: 60 papers across the corpora,
  every one of which the column would otherwise have called un-opened), `no`
  (**nothing recorded** — view tracking is younger than the corpus, and a
  bundle or PDF opened outside the workbench cannot report back), and `?`
  (the record exists and could not be read).
  - **Deliberately NOT in `review.json`.** Opening a paper is not judging it.
    `review_state` answers `reviewed: True` because that file EXISTS, and
    `sort_papers` ranks the work queue off that answer — so a view written
    there would have silently demoted every merely-opened paper. Pinned by
    `test_a_view_does_not_reorder_the_work_queue` and
    `test_a_view_lives_outside_the_decision_file`.
  - **Recorded from the browser, never from the server render.**
    `stats/page.tsx` links into review pages with `next/link`, which
    prefetches on viewport entry and renders the server component; recording
    there would have marked two hundred papers viewed by scrolling a page.
  - `webapp/lib/python.ts` gains `pyModuleJson`: the ping runs
    `python -m metascience_agent.views_io` (22 ms) rather than the whole CLI
    (407 ms, MEASURED), because `pyJson` is `spawnSync` and blocks the Node
    event loop on a path that fires on every paper open.

## [1.13.1] — 2026-09-01

PATCH: display only; no change to what a run finds or how it is judged.

- **A silent codex stage is now visibly alive.** Codex reasons between tool
  calls without emitting any event the status line reacted to — MEASURED on
  the verified apple_cider run: a healthy stage went 6.5 minutes with no
  mapped event (`flag_round_n · 11:50` → `csf_test · 18:16`) while a
  redirected log printed nothing at all, and Dan read a working run as hung.
  `_run_stage` now emits a progress snapshot on every codex stream event; a
  `reasoning` item resets the label to "thinking". Claude/Grok emission is
  unchanged.
- **Codex's permanently-zero token counters are dropped from the line, not
  printed.** Codex reports usage only in the final `turn.completed`, so the
  live counters read `0 in / 0 out` for the whole run — the exact
  broken-counter look `render_stage_line`'s docstring warns about. Codex
  snapshots stamp `live_tokens: False` and the renderer omits the segment
  (the `kind: "track"` argument); claude/grok keep their real counters.
- A finished track's frozen line (`text track : clean · 0:01`) was already
  correct — a stopped clock on a kept line is deliberate — and is unchanged.

## [1.13.0] — 2026-09-01

MINOR: a third LLM backend, `--backend codex` (OpenAI Codex CLI). A backend is
a change to what produces the findings, so two reviews across this boundary
are not comparable. Everything below was measured against codex-cli 0.147.0
with gpt-5.6-sol on 2026-09-01; free probes (`codex debug prompt-input`,
strict-config field enumeration, schema-file rejection) first, then paid
canary runs for the behaviors only a spend can show.

- **`--backend codex` on analyze / batch / eval / adjudicate / preflight**,
  default model `gpt-5.6-sol`, efforts pass through to
  `model_reasoning_effort`. `METASCIENCE_LLM_CLI=codex` works everywhere the
  flag does.
- **System prompt travels as `AGENTS.md`** in a per-run sandbox dir
  (`~/.cache/metascience/codex-sandbox`, `METASCIENCE_CODEX_SANDBOX_ROOT`),
  with `project_doc_max_bytes` raised past the 32 KiB default that would have
  silently truncated the tool-expert prompt (108 KB canary delivered intact).
- **MCP via `-c mcp_servers.*` overrides under `--ignore-user-config`** —
  auth stays in `CODEX_HOME`; the user's config.toml is never loaded and
  never written (structurally cleaner than Grok, which must seed a trust
  entry). `enabled_tools` narrows discovery to the stage allowlist (derived
  from the registry), and the `METASCIENCE_MCP_STAGE` env fence stays the
  enforced layer. `default_tools_approval_mode="approve"` is load-bearing:
  without it every MCP call fails under `approval_policy="never"` — and the
  measured failure mode was the model FABRICATING the tool's verdict in its
  final JSON, not reporting the error.
- **The no-internet analysts pin the web tool's `allowed_domains` to an
  unresolvable sentinel.** `tools.web_search=false` does NOT detach the web
  tool on catalog models (the fetch succeeded anyway, measured); the
  sentinel allowlist is what actually blocked it, and the read-only sandbox
  denies the shell's DNS. The internet delta for the science agent is exactly
  one `-c` value.
- **A stateful stream normalizer** maps `codex exec --json` events
  (`thread.started`, `item.*`, `turn.completed`) onto the Claude stream-json
  shapes, so the tool-verdict ledger, live status line and `_extract_json`
  work unchanged; forensic calls become `mcp__forensic_metascience__<tool>`
  (the exact string the model sees), foreign servers stay their own names and
  land UNVALIDATED. Claude and Grok paths are byte-identical to before.
- **Degraded surfaces are recorded, not faked**: no cost figure exists in a
  codex stream (stage cost stays 0.0), there is no `--max-turns` (the stamp
  `max_turns_unsupported` reaches the stage payload — wall-clock and the
  stall watchdog are the only brakes), no usage probe (the guard reports
  UNSUPPORTED), and the codex `sandbox_weaker` sentence says what the
  read-only shell could do that the prompt forbids. The `apps` feature is
  force-disabled: without `--disable apps` the model saw ~130 foreign
  `mcp__codex_apps__*` tools even under `--ignore-user-config`.
- Golden fixture `tests/data/codex_exec_stream.jsonl` is a real captured
  stream with an MCP round-trip; `tests/test_codex_backend.py` pins the
  normalizer, the argv, the isolation flags, budget refusal, liveness
  probing, and the end-to-end `_run_stage` path.

## [1.12.0] — 2026-08-22

MINOR: cells that no check could reach are now reached. The same paper can
produce different findings, so two reviews across this boundary are not
comparable.

Every figure below is over the 12-paper `high_value_pdfs_to_run_on` corpus with
schema-6 caches. **The value count is held constant at 10,313 throughout** --
that is the control separating "named" from "invented": nothing here creates a
value, it only lets an existing one be read.

### A spreadsheet's first row is its caption, not its header

`10.1038--s41537-025-00576-3`'s supplementary `.xlsx` puts `eTable 1.
Proportion of ...` in row 0 with the rest of the row empty, so the caption
became the column labels and the real header -- `ICD-10 code | Diagnosis |
Cases (n) | Prevalence (%)` -- was read as data.

    unlabelled columns        2,983 (100%)  ->  0
    typed `n_percent`                     0  ->  1,479
    with an applicable tool               0  ->  1,479

Those 1,479 now dispatch to `grim_percentage` and `check_count_percent`. The
recovered `AIC`/`BIC`/`Entropy` columns are the latent-class fit indices
justifying that paper's four-class solution.

The rule is structural because openpyxl reports no merged ranges on these
sheets: one value in row 0 of a wide sheet, followed by a row of labels. It
fails closed -- if the row below reads as measurements the caption is not
promoted, because a header that swallows a data row deletes a measurement from
every check.

### A header row that repeats itself is a span

Docling propagates a spanning cell across every column it covers, then reports
`n_header_rows: 1` -- so the row naming those columns stays in the body. On
`...51752` supplementary_2 Table 3, four columns all read `Mothers of Girls`.

    pdf-supplement ambiguous columns   971 (50.9%)  ->  212 (11.1%)

Ambiguity split by the TABLE's source, which is what located it: article 7.5%,
docx-supp 7.8%, xlsx-supp 0%, pdf-supp 50.9%. Splitting by PAPER said "nearly
all of it is in papers with publisher XML", which was true and pointed away
from the cause.

Two brakes, and the second was added after the first proved too weak: the
candidate row must not read as measurements, AND not one of its cells may look
like a number. `_reads_as_measurements` judges on balance, and on a table where
docling had glued a header to its data (14 of 19 cells text) it waved through a
row still holding `226150662 7250065 ...`. Eleven values would have left the
body silently.

### `p-v` is `p-value` with the end cut off

Making that inner level visible exposed columns docling truncates.
`role_from_column` now accepts a prefix of the one word `value` -- `p-v`,
`p-va`, `p-val` -- while `p-w`, `p-t`, `pop` and `prev` still match nothing.
The [0,1] bound is unchanged and still decides.

    role `p`   1,031  ->  1,199

### Reporting, not gating

- `values.ambiguous_columns(register)` -- how many values sit under a column
  label another column of the same table shares. Corpus-wide 1,169 -> 410.
  It reports and does not suppress: gating there would trade a possible false
  accusation for a certain false all-clear.
- `n_cells_with_no_value` was two facts in one number. Split: **279 markers**
  (the paper writing `NA`), **769 labels**, **790 measurements we lost** to
  extractor-glued rows. Nothing is recovered -- a glued cell cannot say which
  column each number belongs to -- but the size of the loss is now visible
  instead of hidden inside a count that reads as ordinary.
- `prepass` names any PDF whose cached extraction predates the current schema,
  so a cheap cache-only read cannot return pre-fix numbers that look current.
- `metascience corpus-state` snapshots the register and diffs two snapshots,
  for telling an improvement from a regression across a merge. It renders no
  verdict: more ambiguous columns can mean a worse reader OR one that stopped
  skipping tables, and a tool that judged would invite tuning until it was
  green.

## [1.11.1] — 2026-08-22

Audit pass. No output semantics change: one guard restored to the behaviour it
was always meant to have, one latent `NameError` removed, and the rest is
deletion and de-duplication.

### Two defects, both found by `pyflakes` in seconds

- **The schema rejection never left the function that captured it.**
  `schema_errors` is declared in `_run_stage` and assigned inside the nested
  `_read_stdout`, which was missing it from its `nonlocal` list — so Python
  bound a fresh local, the outer list stayed `[]`, and `_stage_payload` emitted
  an empty one on every run. The adjudicator retry that was supposed to quote
  the CLI's rejection back at the model has **never once quoted it**, silently
  falling through to its generic paragraph. That paragraph was enough to
  recover 2 of 2 adjudicators in the v1.9.0 run, which is exactly why nothing
  noticed: the feature appeared to work while half of it was dead. Shipped in
  v1.9.0, in the commit whose message claims it fixes this.
  - The old tests could not have caught it — they exercised the formatter with
    a hand-built dict, proving the formatter worked and saying nothing about
    whether anything filled the field. The new ones go through `_run_stage`
    with the real MMWR rejection.
- **`undefined name 'json'`** in `fetch_metadata_from_title`'s OpenCitations
  block. An except clause's exception tuple is evaluated only when something
  raises, so a malformed response raised `NameError` *while evaluating the
  handler*; the outer `except Exception` then logged it as an OpenCitations
  error and abandoned the lookup instead of setting `oc_data = None` and
  carrying on. Both `json.JSONDecodeError` and requests' own subclass
  `ValueError`, so the name was redundant as well as undefined.

### Trimming the last two rounds

Of 607 added source lines, 207 were prose inside string literals and 181
comments, leaving 171 lines of actual code — but four things still had to go.

- **`ONE_SIDED_UNDER_SURVEY` was dead**, in a module whose docstring cites the
  lesson against dead code.
- **The `prior_attempt` plumbing was redundant.** Six assignment sites across
  three return paths, duplicating a record `record_spend` was already keeping.
  It was missing only the four token fields; adding those makes the ledger
  sufficient and `_add_ledger_only_attempts` derives the rows in one loop.
  Strictly more correct: it also covers the legacy `stage2_editorial` path and
  the tool agent's internal retry, neither of which `prior_attempt` ever saw.
  It **sums by label**, because `tool_agent_retry` can be emitted twice in one
  run and keying by name would let one overwrite the other — an undercount
  presented as a decomposition.
- `_usage_totals` trades eight per-field `try/except`s for one guard that
  returns UNKNOWN rather than a partial total: it runs inside the return
  statement of a finished paper, so it must not crash, but a silently short sum
  would look like a measurement.
- `n_markers` and six `_ALIASES` entries, neither acted on by anything.

Kept deliberately: the seven identical three-line tool guards. A decorator
would save 14 statements and hide the refusal at exactly the point CLAUDE.md
wants it visible — the same argument that keeps `data_type` inside `grim_test`.

### Verified unchanged

All three archived replays give identical answers: the detector fires on 2 of
18 paper directories, the six s12889 rows all return `consistent` with race and
BMI `indeterminate`, and the coverage rebuild recovers 18/27/21 tools.

## [1.11.0] — 2026-08-22

Second audit of the same ten `biomedical_did_not_replicate` papers, re-run at
v1.9.0 — a controlled before/after. Every v1.9.0 fix landed: both adjudicator
schema-gate deaths recovered on the retry (10/10 parsed, against 2 terminal
plus one 71-minute hang), MMWR's loaded text went 6,891 → 13,947 characters,
the two Elsevier abstract findings went from `unverified` to `verbatim` and
were upgraded once confirmable, and the alz duplication false positive is
`consistent` at p=0.9998 with `n_accusatory: 0` on all ten. MINOR because the
sampling guard changes which severities are reachable.

### The false positive this run exposed

- **Six accusations against an NHANES paper for using survey weights
  correctly.** `10.1186--s12889-025-24026-y`: six of the twenty
  severity-bearing tool-expert findings, two at severity 3, were p-values and
  intervals from a design-based analysis recomputed as a simple random sample.
  The paper's Methods named the design *and* the software. Solving for the
  survey degrees of freedom that reproduce each printed p from its own printed
  interval gives 7.8, 6.9, 4.7, 8.8, 38.6 and 37.3 — every row lands on a
  plausible df, and the tell is that the z-based check cleared Model 3 and
  accused Models 1–2 off one table. The BMI t-test needed a design effect of
  only 1.62; NHANES design effects of 1.5–3 are routine.
  - **The check was not broken, it was one-sided.** Fewer df means fatter
    tails, so the same interval half-width implies a less significant p,
    monotonically — the normal-approximation answer is the *infimum* of p. A
    printed p above it is reachable at some df and says nothing; a printed p
    below it is reachable at no df and stands. All six sat in the
    no-information direction.
  - Hence two tiers rather than a severity cap. `check_estimate_ci` keeps the
    check and narrows the question. The recompute-from-printed-means family
    (`recalc_independent_t`, `recalc_within_subjects_t`, `recalc_anova`,
    `recalc_chi_squared`, `recalc_stat_to_p`, `rivets_independent_t`,
    `rivets_anova`) refuses, like GRIM on non-integer data — the direction
    argument does not transfer there, and the race row proves it: printed
    p=0.003 against an unweighted chi-square of 0.117 is the "anomalous"
    direction and is *still* a false positive, because NHANES oversamples
    minorities and weighting moves the composition of the sample.
  - Counting checks on printed integers are deliberately untouched: whether
    one *particular* percentage was weighted is a per-cell fact a paper-level
    flag cannot know.
  - The guard lives in the tools, not in `ToolSpec.call`, because `cli.py`
    calls these functions directly and the CLI is the surface a human uses to
    reproduce an accusation. Prevention is a per-paper prompt paragraph
    quoting the paper's own sentence — the pipeline already knew this rule and
    applied it unevenly, refusing GRIM on weighted percentages on MMWR
    unprompted in both runs and not here.
  - The detector is 14 markers naming the design concept, the software, or an
    NHANES variable; bare "weight", "stratified" and "survey" are absent
    because each is ordinary in this corpus. Fires on exactly the two survey
    papers out of 18 paper directories.

### The pipeline's account of itself

- **A lost docket is not a paper with nothing checked.** Three of ten papers
  filed `coverage: {"tools_run": []}` after 47, 70 and 78 forensic tool calls,
  with the retry empty too. Not truncation — the final message on s13550 is
  3,726 characters of complete JSON with three findings and stub metadata; the
  model worked for 19 turns and filed a highlights document.
  `coverage.tools_run` is rebuilt from the tool-call ledger (18, 27 and 21
  tools recovered on replay), stamped `tools_run_source: "ledger"`, with
  `stats_found` never invented. The v1.9.0 honesty warning keyed on
  `tools_run` being empty and so would have switched itself off the moment the
  recovery landed; it now keys on the source too.
- **The producer retry re-sent a byte-identical prompt** and lost 3 of 3. It
  now names the failure, with different sentences for the two signatures: a
  schema-gate error is quoted verbatim, while a truncated docket parsed and is
  told what was missing instead.
- **$1.82 of $11.57 was spent and absent from the stage table**, because
  `_retry_if_empty` discarded one attempt including its cost. Both attempts
  now reach `stages_meta`, named for which one was discarded.
- **The usage table printed "output tokens: 0"** for a run that produced about
  1.3 million; the "input tokens 41,261,824" beside it was cache-read alone,
  and the runtime rows never printed. `analyze_paper_parallel` returned no
  token or wall-clock keys at all.

### Still open, deliberately

`check_sd_range`'s exhaustive sweep remains 0 checks on 113 enumerated targets,
unchanged across both runs. The bind at `prepass.py:762` is guarded by a
comment protecting exactly what a fuzzy matcher would break, and the tool can
return `impossible`; it needs its own change with its own measurement.

## [1.10.0] — 2026-08-22

MINOR: the agents are told where the paper is, a stage that stops answering is
now cut off, and a corrupt markdown channel is refused by name. **The same
paper may produce different findings** — mostly because the adjudicator can now
reach the paper at all. Measured while diagnosing a worker that hung for 70
minutes on the biomedical batch.

- **The adjudicator could not find the paper, and nothing told it where.**
  `grep -c "/home/dan" prompt.adjudicator.md` returned **0** on every paper of
  the 2026-08-22 batch: `build_docket` took no paths. From grok's own session
  logs for that batch —

      role           sessions  tool calls  failed        reached MCP
      tool_expert          18       1,487  3    ( 0%)    1,238 (83%)
      science_error        15         498  8    ( 2%)      295 (59%)
      ADJUDICATOR          13       1,038  680  (66%)      145 (14%)

  — every adjudicator failure the same shape, `read_file` on `<cwd>/body.md`,
  `<cwd>/paper/body.md`, `<cwd>/paper.md`, names it guessed. `_resolve_paper_sources`
  already stated the rule it broke: "every path the model can read is one this
  function put in the prompt... a supplement that is not merged here is a
  supplement that does not exist as far as the review is concerned."
  `build_docket(sources=…)` now opens the docket with `## Where the paper is`,
  absolute paths, built from the same `src` record the analyst prompts use so
  the three stages cannot be told different things about one paper.
- **NEW `extraction/markdown_out.py` — `<paper>/markdown/body.md`.** MEASURED
  over 1,293 paper directories: **980 (76%) had no markdown this repo could
  read**. `fetchpdf --to-markdown` writes `<stem>_from_xml.md` (418) and
  `_from_html.md` (37), which appeared nowhere in this repo's source.
  Generated from `paper_text_with_source`, so it inherits the `[Table N: …]`
  placeholder rule, and materialised in `ensure_paper_extracted` before any
  agent starts.
- **And it is NOT read back.** The folder is written FOR AGENTS; making it an
  input would reintroduce a staleness class that cannot be closed — it
  invalidates on the source FILES changing, not on the extractor changing, and
  the extractor moved twice in two days (dc4306f, d5d8604) with the XML
  untouched both times. A fresh resolve costs 4.4 ms/paper, so there was
  nothing to weigh against it.
- **fetchpdf's markdown is refused by name.** Of the 418 papers holding both an
  XML and a `_from_xml.md`, **152 (36%) declare fewer tables than the XML
  holds** — nearly all `tables: 0`, one Lancet paper with 7. The rows are not
  dropped but dissolved into the prose undelimited:
  `2-AG at post-injury5.111.870.232.730.007` is B=5.11, SE=1.87, β=0.23,
  t=2.73, p=0.007 — while the front matter certifies
  `tables_not_machine_readable: 0`. One adjudicator in that batch had already
  read one. Named in `jats.py` and in all three prompts.
- **A stall timeout, separate from the duration cap.** One number cannot answer
  both "how long may a legitimate stage take" and "how long before we call it
  dead", and raising the first to be safe raises the deadline for a DEAD stage
  too. `10.1016--j.ynstr.2021.100304`'s adjudicator completed a batch of tool
  calls at 17:51:33 and never wrote again; the process stayed alive and silent
  for ~53 minutes until killed by hand, because `--timeout 60000` was the only
  clock. `METASCIENCE_STAGE_STALL_SECONDS` (default 600) takes the EXISTING
  truncation path, so the paper lands PARTIAL with both analysts' findings
  intact. Stamped `error_stalled`, not `error_timeout`: a budget decision and
  a backend fault need different responses.
  - `_stage_hit_timeout` and `_retryable_empty_forensic_dump` now key on
    `_CUT_OFF_SUBTYPES` rather than the one literal. A new subtype half the
    predicates knew about would have been the guard-that-stops-guarding
    failure; its own test caught it.

Not changed in fetchpdf, deliberately: `--to-markdown` is already opt-in
(`action="store_true"`, default off), and `fulltext_scan._SCANNABLE` reads
those files for its citation signal, so suppressing generation would degrade a
feature that depends on it. The bug there is the flattener, and it is theirs to
fix; this repo refuses the output either way, because 418 files are already on
disk and a corpus can be fetched with any version.

## [1.9.0] — 2026-08-22

Post-run audit of a 10-paper grok-4.6 batch on
`biomedical_did_not_replicate`. The findings themselves held up — 211 of 239
quotes verbatim-verified, cross-stream merge/dedup correct, and no blatant
false positive in any published report. Everything below is harness plumbing
the run exposed. MINOR because `adjudication.md` and the duplication chance
model both change interpretation: the same paper may now produce different
findings.

### Nothing was published that should not have been

- **The adjudicator emitted a placeholder on turn 1 and died, on 2 of 10
  papers.** `num_turns: 1`, ~7 s, zero tool calls, rejected by the schema's
  200-character floor on `summary` — the model wrote a stub intending to
  fill it in on a later turn, and there is no later turn: the schema gate
  closes the conversation. $1.15 of completed analyst work shipped
  unadjudicated for $0.018 of adjudicator time. `adjudication.md` now states
  the turn contract, bans placeholder text by name, and restates the
  200-character floor as four things the summary must CONTAIN. `_run_stage`
  carries the CLI's own `errors` list as `schema_errors`, and the
  adjudicator gets one bounded retry that QUOTES the rejection — narrowed to
  the schema gate, never a budget stop (money is the constraint) and never a
  timeout (the retry inherits the same wall clock).
- **A dying batch orphaned its child and deleted the sandbox under it.**
  `_run_stage`'s `finally` ran `inv.cleanup()` — `shutil.rmtree` — without
  killing the child. When the parent was killed mid-flight the grok CLI was
  reparented to init and kept streaming for 15 minutes against a `(deleted)`
  cwd, holding its own MCP grandchild. One paper lost both finished analyst
  stages with no `forensic_review*/`, no cost row and no failure row: no
  record it had been attempted. The timeout path already did the right thing;
  the cancellation path did not.
- **A lost tool docket was published as a clean coverage record.**
  `10.1186--s12889-025-24026-y`: 76 forensic calls, a docket that serialized
  with `tools_run: []`, an empty retry, and then a report saying three
  different things about one quantity — "Twenty-six table checks were
  consistent" in the adjudicator's summary, "Checks recorded as passing: 0"
  in Limitations, "tools run: none recorded" in Coverage — plus "Nothing was
  recorded as uncheckable". Pass ROWS and ledger CHECKS were never the same
  measurement; both are now printed, each named for its source, and only when
  they disagree. Both sections now lead with the reason they are empty.

### What the model was allowed to read

- **A fifth of an MMWR report was never loaded.** `10.15585--mmwr.mm6923e2`:
  34 KB of publisher XML yielded 6,891 characters, because that report's
  entire Methods and Results are eleven `<p>` children of `<body>` sitting
  outside any `<sec>`, and the walk recognised sections and containers and
  nothing else. Now 13,947 characters. The heading is "Body text (no section
  heading in the XML)" — calling it Methods because that is what it looks
  like would put a fabricated `location` in a finding.
- **Every Elsevier abstract was dropped, and the format scored as derived.**
  `<ce:abstract-sec>` is Elsevier's name for a structured abstract's section
  and the recursion did not know it, so `10.1016--j.jpsychires.2018.04.010`
  loaded starting at "## Introduction" — and both of that paper's
  abstract-vs-Results findings shipped `quote_verified: "unverified"`,
  because the sentences they quote were not in the text we had loaded.
  Separately, `<full-text-retrieval-response>` carries none of the JATS
  markers `_PUBLISHER_XML` looks for (its ISSN is `<prism:issn>`), so it
  scored `unknown`, which every caller reads as `derived`. Measured over the
  ten papers: +7,056 / +2,256 / +1,827 / +1,420 / +1,286 / +555 / +334
  characters, three unchanged, and no sentence emitted twice.

### False positives

- **Six ties on a column where half the SEs are 0.01 is not six
  coincidences.** The harness sweep called `10.1002--alz.13600`
  `highly_suspicious` at a coincidence probability of 2e-39 over six
  (beta, SE) pairs shared between Table 3 and Supplementary Table 5 — which
  is the same models re-fitted by sex. Ten of Table 3's twenty
  beta-plus-minus-SE cells have SE exactly 0.01. The span model priced the
  MODE of a column as rare. Marginals are now FLOORED by the value's actual
  frequency, leaving the match's own two occurrences OUT of the estimate
  (counting them is circular, and four existing pins caught that draft,
  including the Gino four-pair affect regression). The chance gate runs at
  every k rather than only k=1, and `_drop_to` makes it provably
  one-directional. alz is now `consistent` at p=0.98; all 212 pre-existing
  duplication tests pass unchanged.
- **A display string was filed as an undeclared tool.** `"Web search:"` —
  trailing colon included, 7 calls — scored `surface: "UNVALIDATED"` and was
  invisible to `_WEB_TOOLS`, the set deciding what the adjudicator is told
  the agent actually visited. `tool_short` is canonical across backends now;
  `tool` keeps the raw name. Denied tools are deliberately not aliased.
- **A bare URL is not a finding title.** Three mmwr `pass` rows were titled
  with nothing but a link, under techniques like `check_summation_batch` for
  a Wikipedia page. The row is kept and the link moves to `notes`; a title
  that quotes a URL inside a sentence is untouched.

### Also

- The batch plan table says when `--timeout` is large enough that the runaway
  guard is off in practice. The hung adjudicator in this run had a 16.7-hour
  leash from `--timeout 60000` while its siblings finished in 6–10 minutes.

## [1.8.0] — 2026-08-22

MINOR: a severity cap that binds where none did, and a chi-squared guard that
recognises a test it used to accuse. **The same paper may now produce different
findings.** Measured while auditing the v1.7.0 `grok_second_run` batch.

- **Arithmetic the model asserted rather than performed could ship at level 4.**
  `10.1037--0022-3514.94.2.94.2.196` came back `does_not_reconcile` carrying two
  severity-4 recomputation findings, and one is a FALSE POSITIVE: `Study 4
  postattack F(1, 142) = 14.06` was called twice the F from the means, but the
  paper states a "2 x 2 x (time) mixed-design ANOVA" in the same paragraph, so
  that F is a simple effect whose error term is the model's. Reaching 14.06
  needs MS_error 1.219 and the within-subjects error term at r = 0.47 gives
  1.234 — an ordinary pre/post correlation reproduces the printed F exactly.
  (Its sibling, Study 3 `t(103) = 7.23, p = .008`, IS real and survives on its
  own: t = 7.23 at df 103 implies p ≈ 1e-10, and 7.23 = √52.14, the time main
  effect printed two sentences later.)

  It reached 4 through the CLAMP, not the tool — `recalc_anova` returned
  `suspicious` on those very numbers. The finding carries
  `computed_by: model_reading`, `inputs: null`, `computed: null` and no
  tool_verdict, and `_COMPUTED_BY_CAPS` held `agent_code: 4` and
  `model_knowledge: 3` with **no entry at all** for the weakest of the three.
  `MODEL_READING_CAP = 3`, GATED on the technique naming a registered tool:
  `not_computational` and `internal_contradiction` have no arithmetic to cite
  and reading the page is their honest channel, and three legitimate level-4
  findings in these two runs are exactly that. Replayed over both archived runs
  (339 findings): **exactly 2 severities move**, both on the target paper, both
  `recalc_*`. The cap rewards CITATION rather than a guess about which findings
  are correct — the route back to 4 is to cite the tool call.
- **A tool-technique row with no `inputs` cannot be joined to its own
  evidence.** `tool_verdict_for` matches on scalar inputs, so those rows lose
  the tool verdict even when the tool ran and agreed. Rows carrying `inputs`
  fell from 85% (v1.5.1) to 56% (v1.7.0) and tool_verdict from 54% to 44%, and
  nothing counted it. Now a `validate_producer_constraints` problem record
  (12 of 339 rows, 4%). Recorded, not rejected — the cap above is the answer.
- **McNemar is a different statistic and the table looks the same.** A paired
  2x2 uses `(b-c)^2/(b+c)` on the discordant cells, not a chi-squared of
  independence. MEASURED on `10.1111--j.2044-835x.2011.02046.x`:
  `recalc_chi_squared` answered "matches NEITHER convention" and returned
  `suspicious` on a McNemar table. McNemar (both continuity conventions, since
  R's `mcnemar.test` corrects by default) is now computed on every 2x2 and
  entered into the same matching, so a statistic only it explains comes back
  consistent — no reliance on the caller declaring the design. `paired=true`
  additionally makes it the headline test.
- **The system prompt is archived with the run.** `prompt.{label}.md` is the
  USER turn — 504 bytes for the tool agent — so the rulebook, the ladder, the
  CLI map and every guard sentence appeared in no artefact and no transcript. A
  finished review could not be audited for what instructed it, and
  `prompt_sha256` had nothing to compare against. `system_prompt.{label}.md` is
  now written per role, captured where the command is built rather than rebuilt
  by the writer.

WITHDRAWN after review: a design-aware guard on the recomputation family. Its
discriminator — statistic and p agree with each other but disagree with the
means → downgrade — is the exact signature of fabricated summary statistics,
the highest-value signal this toolkit has. And a `design` parameter has no good
default: unlike the GRIM-U fix the precondition is not checkable in code, since
in both Study 3 and Study 4 the printed df is exactly n−2.

## [1.7.0] — 2026-08-22

MINOR: a new tool, a severity cap that now refuses two cases it used to
accuse, prompt edits that change interpretation, and a statcheck text channel
that reads statistics it used to lose. **The same paper may now produce
different findings**, in both directions. Two reviews across this boundary are
not comparable. Everything below was measured on a 9-paper grok-4.6 psychology
batch run on 2026-08-22.

- **`checks_tally` counted nothing, and the adjudicator believed it.** It
  bucketed findings on the retired v1 lowercase severity ladder while
  findings-v2 carries `outcome` (`pass|problem|undecided`) and an INTEGER
  severity — and the tally runs BEFORE adjudication, when even that is still
  `provisional_severity`. Every finding fell into `"unknown"`. All 9 papers
  reported `checks_total: 0` against a real 124 pass / 61 problem / 28
  undecided. `parallel.py` hands the dict to
  `adjudicate.build_docket(tally=...)`, so the adjudicator was told on every
  paper that nothing had passed and nothing was flagged — the denominator its
  verdict rubric needs. Every report also printed "Checks recorded as passing:
  0" above ~30 passing checks. Archived v1 runs still tally as before, and a
  finding neither vocabulary recognises is counted `unclassified` rather than
  binned as a pass.
- **A truncated docket is a third retry signature.**
  `10.1177--0956797614564191`'s tool agent made 56 calls, then its structured
  output degenerated mid-array (backticks where quotes belonged) and closed
  the findings list after ONE row with
  `"coverage":{"stats_found":0,"tools_run":[]}`. 55 of 56 tool results were
  discarded — including a statcheck run that had already found two real
  inconsistencies. `is_error` false, `output_parse_path` "json_schema",
  `limitations` EMPTY. `_retry_if_empty` could not see it because one surviving
  finding satisfied the not-empty test. Forensic calls on the ledger beside no
  tools in the coverage is now a retry, and the contradiction is stated as a
  limitation even when the retry is skipped or fails.
- **statcheck was reading damaged text.** Two artefacts join the HTML-entity
  and capital-`P` repairs: docling renders `<` as `\` in some PDFs (15
  occurrences of `p \ .001` and ZERO of `p <` on `10.1007--s10803-013-1829-4`;
  repairing them takes that paper 26 → 37 statistics), and runs of horizontal
  whitespace defeat the regex outright (`F(2,  33)  =  5.76, p  =  .008`
  extracts nothing; the Bargh 1996 scan yielded 0 of 4).
- **`statcheck` is one tool again.** `python_statcheck(pdf_path)` was a second
  implementation wearing the same name, with none of the normalisations and
  none of the `correct_at_printed_precision` filter. It reported
  `errors_found: 25` where the text path reports 1 on the same paper, emitted a
  mangled `t(28 ) = 2.86, p < .0` and flagged it, and found 1 statistic where
  our own extraction yields 13. It now reads the PDF through
  `extraction/pdf.py` and delegates, keeping statcheck's own reader as the
  fallback. Measured after: 37/1, 4/1, 13/0.
- **NEW TOOL `effect_size_from_f`.** Partial eta-squared —
  `(F*df1)/(F*df1 + df2)` — and Cohen's f, reconciled against the F beside
  them. Nothing in the registry did this, so a real mismatch (`F(2, 54) =
  51.81, eta_p^2 = .83` against a true .657) had to be filed under
  `no_tool_exists`, while another paper hand-rolled four such checks through
  `check_ratio` using `F/(F + df2)` — the `df1 = 1` special case. Refuses
  without `df1`; refuses `eta_squared`, `generalized_eta_squared`,
  `omega_squared` and model `r_squared` BY NAME, since each needs a total sum
  of squares the paper does not print. Interval-to-interval, capped at
  `suspicious`.
- **SEVERITY CAP: GRIM-U now refuses two cases it used to accuse.** A p printed
  beside a normal-approximation Z is a function of the ROUNDED Z, not of U
  (`reported_z`, checked rather than taken on the label — a Z that does not
  explain the p buys no acquittal); and a tie-prone outcome moves every
  achievable p off the untied lattice (`ties_possible`, granularity branch
  only — below-floor still returns `impossible`). Two severity-2 findings
  against an honest paper came from this, whose own notes conceded statcheck
  reproduced each p from the printed Z.
- **The R cross-check must be asked the same question.**
  `r_grim_ground_truth(mean=28, n=41)` answers "can 41 integers average 28?"
  (yes) where `grim_percentage` asks "is 28% a possible k/41?" (no). The
  engines "disagreed" because they were asked different things, and the easier
  answer read as exoneration. `percentage=true` converts to the proportion at
  the same precision `grim_test_percentage` uses; every verdict carries
  `asked_as`. Both ranking prompts now state the machine's actual R
  availability and forbid the "pending"/"awaiting" wording in either branch —
  two findings shipped at severity 2 and 3 carrying it.
- **A publisher shop front no longer outranks the article.**
  `paper_text_with_source` returned the SAGE landing page (13,838 chars, zero
  statcheck-eligible statistics) over a 41,510-char PDF, because HTML ranks
  above the PDF for its table structure — true of a real full text and exactly
  backwards for a purchase page. Gated on the PDF being 1.5x longer, so a
  false positive costs nothing.
- **The value register never parsed a printed test.** `prose_values` had no
  `nhst` branch, so `t(28) = 2.10` and `F(2, 54) = 51.81` reached the register
  as one `unknown` row with `value: None` — 116 such spans across the batch.
  And `applicable_tools` was hard-coded `[]` for every body group, which is
  this module's word for "considered and declined", so a register that had
  never looked was reporting a decision (`74 / 74` on one paper). `df2` is its
  own role: F(2, 54) and F(54, 2) are different tests.
- **RULEBOOK rule 17.** A finding whose own `notes` explain the value away does
  not publish above severity 1. Three did, at severity 2.

## [1.6.0] — 2026-08-22

MINOR: XML extraction now yields figure captions and structured abstracts it
used to drop, so **the analysts read text on every XML paper that they could
not see before**. Two reviews across this boundary are not comparable. No
severity cap, threshold or prompt changed.

- **Figure captions get the document-wide sweep tables already had.**
  `_paragraphs` emitted a figure only when `<fig>` was a DIRECT CHILD of the
  section it was called on, and publishers overwhelmingly park floats
  elsewhere. MEASURED over 120 papers with XML: of 550 `<fig>` elements only
  234 have a `<sec>` parent — 219 sit under `<floats>`, 71 under
  `<floats-group>`, the rest under `<p>`, `<fig-group>`, `<body>` or `<app>`.
  More captions were lost than kept. Captions are prose and carry no grid, so
  the reason `_collect` skips `<fig>` beside `<table-wrap>` — a flattened
  table loses its column alignment — never applied to the caption itself.
  A figure a section already claimed is not repeated by the sweep.
- **A structured abstract is no longer dropped entirely.** JATS nests that
  prose in `<sec>` children, `_paragraphs` read only direct children, so
  `add()` saw an empty section and discarded it. MEASURED: 114 of 195 papers
  with an `<abstract>` have no direct `<p>` in it. The abstract is where a
  paper's headline claim usually lives.
- **Every `<abstract>` is kept, labelled by `abstract-type`.** Taking `[0]`
  published whichever sibling came first; a JAMA Network Open article ships
  `key-points`, `teaser` and the abstract proper.
- **The workbench renders captions rather than skipping them.**
  `_paragraphs_html` dropped `[Figure ...]` blocks alongside `[Table ...]`.
  A table placeholder is skipped because the real grid is spliced in below it;
  a figure has no second rendering, so dropping it there put the caption
  nowhere and left a caption-quoting finding unhighlightable however well it
  was anchored.

Anchor coverage over the whole eligible population — 92 papers with a PDF, an
XML and findings; 369 unique candidate quotes — combining this with the
table-cell matcher:

| | before | after |
|---|---|---|
| `exact` | 247 (66.9%) | **300 (81.3%)** |
| `section` | 25 (6.8%) | 26 (7.0%) |
| `none` | 97 (26.3%) | **43 (11.7%)** |

Issues with no XML anchor: 58 → 29 of 260.

## [1.5.2] — 2026-08-22

PATCH: two runs can now share one paper directory. No finding, severity, or
report output moves; an archived review has the same shape it always had.

- **`analysis_code/` is scoped to the run.** `run_python_script` chose its
  sequence number by COUNTING the scripts already on disk, with no
  reservation, and `write_parallel_outputs` then `shutil.move`d the whole
  directory into the finishing run's archive. Two analyses of one paper — a
  cross-backend comparison, or a re-run started before the first finished —
  therefore (a) both wrote `007_<label>.py` and the second silently replaced
  the first's code, (b) shared one `007_<label>.d` sandbox workdir, and (c)
  the first to finish carried the other's scripts off into its own review.
  The persisted script is the audit artefact behind every
  `reproduction_kind: "script"` finding, so that was a finding citing another
  run's code. Now the pipeline mints a `run_slug` once per run and hands it to
  the MCP server on the same env channel as `METASCIENCE_PAPER_DIR` — a
  channel the model cannot write — and scripts land under
  `analysis_code/<run_slug>/`. The archive FLATTENS the slug, so a finished
  review still reads `analysis_code/007_x.py`, which is also what
  `script_path` reports. Unset (legacy, hand-driven callers) keeps the flat
  layout unchanged.
- **One atomic writer, `atomicio`, replaces four fixed-name temp files.**
  `docling_tables` already wrote tmp+rename with a PID suffix, carrying the
  comment that explains why: "two processes extracting the same paper at once
  left a half-written cache". `metadata.json`, `webapp/data/index.json` and
  `review.json` all wrote tmp+rename with a FIXED temp name, which fixes
  nothing — two writers open the same `foo.json.tmp`, interleave, and rename a
  truncated file over the real one. A torn `index.json` is the worst of the
  three: every later refresh then gives up with "unreadable index" and the
  workbench table silently stops updating. The discriminator is PID **and** a
  uuid, because `batch --workers N` runs papers concurrently inside one
  process, where a PID distinguishes nothing.
- **The OCR scratch file is unique.** `supplements_read` rendered each page to
  a deterministic `.<stem>.ocr-p<N>.png` beside the supplement and unlinked it
  in a `finally`; two runs OCR-ing the same file read each other's page image,
  or lost it mid-read. This became reachable rather than theoretical when an
  OCR engine turned out to be installed (see the CLAUDE.md correction below).
- **`examples/batch_analyze.py` uses the versioned output name.** Commit
  4ec9bb3 introduced `forensic_review_<model>_v<version>` so "the two entry
  points cannot drift apart again", but changed `cli.py` and `agent.py` only;
  the script's own argparse default stayed the bare `forensic_review`, so
  running it directly put every model and every pipeline version in one folder
  and two backends overwrote each other. `metascience batch` passes an
  explicit `subdir_name` and is unaffected.
- **CLAUDE.md no longer asserts that no OCR engine is installed.** It is
  machine-specific; `engine_status()` and `metascience preflight` answer for
  the machine you are on. Measured 2026-08-22: pytesseract and
  PyMuPDF-Tesseract both available here.

Not fixed, and now documented in the function that has it:
`webapp_index.refresh_index_paper` is a read-modify-write with no
compare-and-swap, so two runs finishing together can lose one another's edits
to OTHER papers' rows. Each run's own row survives — `scan_paper` re-reads the
directory — and the write is atomic, so the file is never torn.

## [1.5.1] — 2026-08-22

PATCH: reader-side only; no finding, severity, or run output moves.

- **The HTML bundle understands findings-v2 runs.** Since v1.0.0 every run
  writes `findings.v2.json` + per-agent ledgers, and `bundle.collect()` read
  only the legacy filenames — so a bundle of any current run built
  "successfully" as a HOLLOW viewer: report prose and paper panes, zero
  finding cards, zero tool-call ledger, and the archive did not even copy
  the findings document. Now: a v2 adapter (`_v2_container`) feeds the same
  payload; the findings page renders v2 natively — the adjudicator's
  verdict/paper-severity header, headline first, S1–S9 chips colored from
  `severity9.as_json()` (the ladder's single source; the legacy 5-enum
  words are never minted from a 1–9 level — an S5 is not "impossible"),
  discarded/merged rows retained at the bottom with their rationale; the
  three agent ledgers appear in the calls pane; and the v2 files
  (findings.v2.json, adjudication.json, toolcalls/messages/prompts) ship in
  `analysis/`. A hollow bundle now RAISES instead of shipping
  (`build_bundle` compares the doc's finding count against the payload).
  Verified end-to-end against the 2023 rematch run: 1.3 MB viewer, CD3
  headline first, all three ledgers, node-rendered section test in
  `tests/test_bundle.py::TestV2Bundle`.

## [1.5.0] — 2026-08-22

MINOR. The fixable-error pass: every error the four-paper FP audit and its
follow-up analysis surfaced, fixed in one sweep. `recalc_f_to_p`'s semantics
and two docket-visible fields move, so reviews cross a MINOR boundary.

- **The spend ledger is context-local** (`agent._SPEND` → ContextVar).
  MEASURED: in a 4-worker batch the module-global ledger cross-contaminated
  every paper — the first finisher reported total_cost_usd $2.11 while its
  own stages summed to $0.86, and the published "7×" old-vs-new cost
  comparison was really ~2× ($0.34 → ~$0.69/paper on grok). Per-paper
  totals from any PRE-1.5.0 concurrent batch are untrustworthy; their
  `stages.*.cost_usd` figures are correct. `tests/test_spend_ledger.py`
  reproduces both halves of the contamination.
- **`recalc_f_to_p` runs without a df2 the paper never printed.** df2 is
  optional; omitted, the reported p is checked for attainability over EVERY
  df2 (grid + the df2→∞ chi-square limit, printed-F interval propagated),
  and the tool accuses only when no denominator df explains it — capped at
  suspicious. The measured Sholl FP (F(3, assumed 20)=6.951 vs p=0.0001,
  reconciled exactly by df2→∞) is now `consistent` when df2 is omitted.
  df1=1 keeps the one-tailed indeterminate wrinkle.
- **Unsourced `web_lookup` rows carry `ledger_web_context`** — the URLs and
  queries the stage's ledger shows were actually visited (cap 10), rendered
  in the adjudicator docket under the `web_unbacked` sentence. The row's
  own `web_sources` is never fabricated; it stays the model's attestation.
- **The "known 6" standing test failures are zero.** One was a real bug:
  `_assert_forensic_tools_ran` relabeled an ERRORED stage (empty ledger
  because the call failed) as a "plumbing failure", crashing the
  both-stages-failed → partial-report contract; errored stages now bypass
  the gate. The other five were stale pins re-pinned at what matters: the
  help-into-schema seam we own (`mcp_server._to_json_schema`, not a removed
  SDK private), the `bundle` command's Windows path (the analyze print was
  removed deliberately), the Invocation call shape, the both-readings
  guard's direction (threshold reading may only clear, never accuse), and
  the cli-compat detector's mechanism rather than the environment's class
  hierarchy.
- **A stub main PDF is known BEFORE the spend.** `probe_main_pdf_stub`
  (shared by the workbench scanner, a yellow pre-spend warning in
  `metascience analyze`, and a named run limitation) flags a ≤2-page PDF
  beside a full-text XML; the report now says its figure checks were blind
  instead of the fact living only in a workbench cell.
- GRIM-U's in-code `test_type` refusal was verified already shipped;
  CLAUDE.md's stale "porting it is the remaining work" claim corrected.
- Decision recorded from the same analysis: the science-error analyst is
  NOT merged into the adjudicator. It produced 29/45 kept findings and 2 of
  4 headlines in the rematch at ~$0.36/paper true cost, its audit FP count
  equals the tool expert's (one each), and the adjudicator cannot originate
  findings without bypassing every pre-adjudication annotator.

## [1.4.0] — 2026-08-22

MINOR. Two sources: the four-paper v0.7.0-vs-v1.3.0 rematch on Grok (the
per-finding false-positive audit of all 45 kept findings measured a 4.4% FP
rate and two systemic gaps), and the severity-ladder v2 rewrite. Prompt rules,
severity caps and the ladder's rung meanings all move, so reviews across this
boundary are not comparable.

From the FP audit and the rematch's failure diagnosis:

- **Transcript salvage for Grok schema failures** (`parallel._doc_for`).
  MEASURED: the neulet science agent did 22 tool calls and 13 web searches,
  narrated its findings, then emitted an empty findings shell beside another
  tool call and errored at `error_max_structured_output_retries` — $0.32 of
  real work lost with the findings sitting in the transcript. The repair pass
  now runs over the final assistant texts (thinking blocks excluded) when the
  stage's own output is empty or unparseable.
- **The empty-report retry also covers the errored-at-schema-gate variant**:
  a stage that died at the structured-output gate (after salvage fails) gets
  the same one bounded, billed retry. A timeout is explicitly NOT retried by
  this guard.
- **Grok final-turn discipline** (`grok_mcp_route.md`, "## Last action"): the
  final message must be ONLY the findings JSON, no tool call beside it, with
  the measured neulet failure quoted. Pinned for all three grok-routed
  producers.
- **The unsourced-lookup guard** — the inverted `web_unbacked` shape.
  MEASURED: all ten `basis: web_lookup` rows across the four runs carried
  `web_sources: []` beside ledgers full of real web calls; one sat at S4.
  Such a row is now flagged (`web_unbacked: "no_recorded_source"`, its own
  docket sentence) and severity-clamped as model knowledge (cap 3) unless a
  joined tool verdict provides the evidence. Prompt states the rule.
- **Degrees of freedom are an assumed bound** (rulebook rule 4;
  `recalc_f_to_p` description). MEASURED FP: F(3, df₂)=6.951 flagged against
  a reported p=0.0001 using an assumed df₂=20, but at df₂→∞ the same F gives
  p=1.14e-4 — which prints as 0.0001. The paper never stated df₂. The model
  must check attainability at the large-df limit before accusing.
- **Row coherence is an adjudication requirement** (`adjudication.md`): a
  row whose title and description describe different defects — the audit
  found a kept S3 titled as a timing contradiction whose description analyzed
  an unrelated ANOVA and found it consistent — is malformed and must be
  discarded as `insufficient_evidence`, not kept.
- **Stitched-quote pressure at the source** (`science_error.md`): the
  producer is told the verifier publishes the stitched flag and the finding
  weakens; one quote record = one contiguous span. The claims register now
  names the abstract and the acknowledgements as register sources (both
  dropped-finding classes in the rematch were prose contradictions).
- **Stub-PDF visibility** (`webapp_index._sources`): a ≤2-page PDF beside a
  full-text XML is recorded as `pdf_suspect_stub` with `main_pdf_pages`, and
  the workbench PDF column shows "stub?" instead of "yes". MEASURED:
  `10.1016--j.neuroscience.2024.05.006` holds a 1.9 MB ONE-page ScienceDirect
  preview (size is not the tell; the page count is), and its review ran
  figure-blind while the table said `pdf: yes`. Page count is probed only
  when an XML proves full text exists (fitz, ~0.4 ms; absent fitz the count
  is `None` — unknown, never a claim).

Also in this release (committed earlier on this branch):

- **The 1-9 severity ladder is rewritten for classification, and the ladder
  now ships as data to both of its audiences** (`severity9.LADDER_VERSION`
  1 → 2; MINOR when this is released — rung meanings changed, so two reviews
  across it are not comparable). The correction outcome is now the rung's
  LABEL, not its TEST: rungs 2/3/4 used to be discriminated by journal notice
  names (erratum / correction / corrigendum), which differ by publisher and so
  gave a classifier an unstable thing to reason from. Each rung gains
  `boundaries` — escalate/de-escalate tests keyed on the paper (does a reported
  result change; must something be re-run rather than re-reported; does an
  abstract-level claim fall; can the surviving results still be bounded) —
  which are rendered into every agent prompt. Two rungs were repaired: **3/4**
  was near-vacuous ("a small miscalculation in a supplementary analysis" vs
  "a mistake in data processing for a specific analysis"), and **6** was keyed
  on investigation status, which the pipeline cannot know, making it
  unassignable; it now records unbounded scope. Slugs, labels, correction
  outcomes and every cap are unchanged, so no stored finding or DB row moves.
- Each rung also gains `web_summary`, and `as_json()` now exports the rung
  prose it used to drop. `metascience gen-webapp-constants` writes **two**
  artifacts from that one payload — `webapp/lib/constants.gen.ts` (typed, for
  the Next.js app) and the new checked-in `docs/severity_ladder.json` (for
  anything that should not have to parse TypeScript to read the ladder) —
  each byte-compared in `tests/test_webapp_constants.py`. Prompts read
  `finding_rubric` + `boundaries`; a public ladder page reads
  `label`/`correction_outcome`/`web_summary`/`colors`. One record, two field
  sets: a hand-written website copy would be the `tool_reference.md` failure.
- `docs/errorlevels.md` is now explicitly the narrative appendix — it explains
  why the axis switches from consequence to culpability at 7, why 6 records
  unbounded scope, and why 9 merges two rungs, none of which was written down.
  **Its worked cases are recalibrated**: they sat 1–2 rungs high and several
  contradicted their own rung (two "major error affecting conclusions" cases
  whose own summaries said the conclusions were unchanged; a "localized flaw"
  case whose corrigendum reassigned the cause of the title claim). The bias
  tracked venue — every mid-ladder example was Science or Nature. The cases
  stay OUT of every prompt for that reason.

- Merged `main` (Greg's stacked-headers extraction campaign: spanning/stacked
  table headers in JATS and .docx, the value register, tripwire, numerals/
  glyph handling, censored values, document-decided decimal separators).
  The docling cache schema is now **6**: both branches had independently
  stamped 5 with different fixes, so an on-disk 5 cannot prove which one it
  carries and is refused as stale. His prompt/annotator work still targets
  the retiring legacy pipeline files; the port into the parallel prompts is
  the next entry's work.
- A finished `analyze` is written back into the workbench index. The
  project table was still showing `—` for Findings on papers whose
  review was already on disk, because the table reads a snapshot and
  analyze never updated it.
- `--ignore-weekly-limit` (`METASCIENCE_USAGE_IGNORE_WEEKLY=1`) skips the
  weekly usage STOP so extra Claude Code usage credits can be spent; the
  `/usage` weekly % does not include them. Session-window pausing still
  runs. `--no-usage-guard` is now on `metascience analyze` and
  `metascience batch` as well as the example batch script, and a spent
  week names both flags in the error instead of only WEEK_WAIT.

- `metascience analyze` end-of-run terminal output is verdict, finding
  counts by severity, and runtime. The report, paths, cost, and viewer
  location are not printed; they are still written to disk.

- The workbench no longer has a "Fetch missing metadata" button. Papers
  missing a title or an author are refilled in the background from the
  DOI cascade; volume/issue gaps are not a refetch. A failed lookup is
  not retried for a day.
- Workbench findings can have several locate *targets* (two sides of a
  contradiction, the same quote in XML and in the PDF, tool-emitted
  spreadsheet cells). Clicking a finding card jumps to the highlighted
  region. **Highlight 1** / **Highlight 2** buttons appear only when a
  finding has two distinct places to compare (the same quote in PDF and
  XML is one highlight, not two). Both sides paint in the same severity
  colour. Locate is deterministic (`fold_rendering` so an XML-copied
  quote can still hit the PDF). No second model, no invented page.
  Optional `passages[]` on editorial findings so new runs name the two
  quotes explicitly.
- Image duplication cards in the workbench now show where the matched
  panels sit (`Figure 2 on p. 5 and p. 17`) from recorded placements,
  with **Open p. N** jumping the PDF to each page. Pages already lived
  on the harvest; the card just did not print them. No invented page 1.
- Workbench numeric labels split `correct` into `correct_minor` and
  `correct_significant`. A stored `correct` is still readable. Finding
  checkboxes sit in three columns.
- **`metascience analyze` shows one live status line per concurrent
  channel, stacked, instead of one line for all of them** (PATCH: display
  only; no finding, schema or cost figure moves). The parallel pipeline
  runs a tool agent and a science agent at once and both emit progress
  snapshots, but the CLI stored the newest one in a single cell, so they
  overwrote each other and the operator watched one line flicker between
  two unrelated stages. Snapshots already carried `stage`, and
  `LiveBatchStatus` (used by `batch_analyze`) was already a multi-slot
  Rich Live block, so this is a wiring change: slots keyed by stage,
  seeded in display order because the two analysts race under
  `asyncio.gather`. The image and text tracks get a line too, a HEARTBEAT
  rather than a stream -- `_run_forensic_track` reads its child with
  `communicate()` and so genuinely knows nothing between launch and exit;
  it emits `running`, then the terminal state BY NAME (`clean`,
  `3 finding row(s)`, `engine_missing`, `track_timeout`), because "did not
  run" and "ran and found nothing" are different facts. Track lines carry
  no token counters: `0 in / 0 out` reads as a broken counter, not as
  "this channel has no such number". A finished line **stops its clock**
  (`done`, stamped in a `finally` so a DEAD agent stops counting too) --
  the lines are kept on screen now, and one whose elapsed keeps climbing
  reads as still working. Non-TTY is unchanged: one plain line per 15 s,
  never carriage returns. `batch_analyze`'s behaviour is byte-identical
  (`transient` and `show_key` default to what it already did).

## [1.3.0] — 2026-08-21

MINOR. Calibration round 2, from reading the passing gate run's ledgers:
the same paper may now produce different findings.

- The v1.2.0 apple_cider run's two remaining misses were both NEVER-RAN,
  not ran-and-cleared: zero `sprite_reconstruct` and zero
  `check_effect_plausibility` calls in 41. The tool expert's procedure
  gains two CLOSING SWEEPS that must run (or be recorded in `unchecked`)
  before output: SPRITE on every bounded mean/SD/n/range variable, and
  effect plausibility on the headline effect(s).
- `check_effect_plausibility` joins the SCIENCE_AGENT surface (15 → 16
  tools): implausibly large effects need field norms — that analyst's
  beat — and once the tool left the old sweep's habit loop neither
  analyst ran it. Registry snapshot updated deliberately (one entry).
- Eval on Grok works end to end: the harness drops the default budget for
  a backend that cannot cap spend, and the model default resolves per
  backend (forwarding the claude alias made the grok CLI exit with
  "unknown model id" before spending a cent).
- A physical duplicate of a paper is one paper: `iter_paper_dirs` dedupes
  copies by name, keeping the one whose newest run is newest (the DB's
  current-run ordering), so file stats and the database pick the SAME
  copy — masliah's drift check now agrees at 566 papers with v2.

## [1.2.0] — 2026-08-21

MINOR. The apple-cider calibration pass: every defect the failed v1.0.0
eval gate exposed, fixed at its source. The same paper may now produce
different findings.

- **`bayesian_table1_dispersion` cannot print reassurance over its own
  evidence.** On the measured failure it computed per-row baseline p-values
  of 0.93/0.99/0.99, diluted them across eight unremarkable biochemical
  rows (whole-table csf similarity_p 0.19, τ̂ CI [0.20, 2.82]), and printed
  "consistent with random allocation". An upper-tail Simes test on 1−p
  (0.057 on that data) now withholds the all-clear when a concentrated
  uniform cluster hides in the table — verdict `indeterminate`, the extreme
  rows named, `csf_test` on the coherent subgroup named as the next
  instrument; never an escalation. The clean-table wording is now "does not
  distinguish", never "is consistent with random allocation" (rulebook
  rule 1 in code). Regression tests use the live run's exact table.
- **The per-role MCP fence is real.** The tool expert had executed
  `run_python_script` three times — `--allowedTools` is an auto-approve
  list under bypassPermissions, not a fence, and the stdio server
  registered every tool for every caller. The pipeline now stamps each
  agent's role into the server's environment and the server registers ONLY
  that role's tools; a call for an off-role tool that slips through is a
  named `off_role_tool` refusal, not an execution.
- **Prompt calibration:** `csf_test` is mandatory on any multi-arm baseline
  table and runs on the coherent variable block, with the bayesian screen's
  pass explicitly never clearance; SPRITE runs on every bounded variable
  with printed mean/SD/n/range even when granularity checks pass; the
  promises-versus-delivery (data-availability) check has an owner — the
  science-error analyst — after falling between the two agents' beats.
- **The apple-cider `must_not_say` nets catch the phrasings that slipped
  through**: "baseline dispersion … consistent", "consistent with
  randomisation" (both spellings), "baseline similarity … consistent".

## [1.1.0] — 2026-08-21

MINOR. The stacked-headers merge follow-through: the same paper may now
produce different findings.

- **Greg's 14 unmerged tip commits land** (censored values as bounds,
  spanning header labels to every covered column, .docx span markup, the
  stale-cache report, ambiguous-column reporting, reference categories as
  values).
- **His prompt fixes are ported into the live parallel prompts** — they had
  only reached the retiring legacy files: work each table to completion in
  row order (denominators must not be conditioned on suspicion); a tool's
  verdict is the DEFAULT, not a floor; table-cell quotes as the paper's own
  pipe-markdown, never tool JSON (measured: 107/120 located vs 0/82);
  `variable_id` on granularity checks; where schema and prose disagree THE
  SCHEMA WINS; contradiction anchors carry roles and locate independently;
  the adjudicator may run a stricter check on a finding's own inputs, names
  a failed producer channel, and sees the verdict-band distribution.
- **The roles rule is 16 now**: the rulebook gained its own rule 15 (a
  near-miss percentage is usually a denominator) on Greg's branch while the
  roles preamble appended a different rule 15; two rules, one number.
- **Quote verification actually runs on parallel output** — the annotator
  takes a result-shaped dict, the parallel pipeline handed it the bare doc,
  and every run since the cutover shipped quotes unverified behind a
  swallowed exception (found via the failed apple_cider eval gate).
- **The value register and the exhaustive harness prepass run on parallel
  output too** (both previously legacy-writer-only): value_register.json in
  every parallel archive, and the deterministic duplication/sd_range sweeps
  feed the adjudicator's tally and run_meta.

## [1.0.0] — 2026-08-21

MAJOR: the output schema changed. `findings.json` is now findings-v2
(`schema_version: "2.0"`) and the review directory layout carries per-agent
files — anything parsing the old shapes must re-read the format
(`docs/specs/findings_v2.md`). No review produced before this release is
directly comparable with one produced after it.

- **The pipeline is two parallel analysts plus an adjudicator.**
  `mode="parallel"` (now the default; `two_stage` is a deprecated alias for
  it, recorded as `mode_requested`) runs a *tool expert* (numbers, tables,
  supplements; forensic MCP tools; no internet, no code) and a
  *science-error analyst* (methodology, contradictions, CONSORT/patient-flow
  arithmetic via the new `check_flow_arithmetic` tool, factual entity
  checks; internet on; sandboxed network-off `run_python_script`)
  concurrently, then an adjudicator that dedupes, merges, verifies quotes,
  and assigns each finding's FINAL severity under code-enforced clamps.
  The retiring serial pipeline remains reachable for one release as
  `mode="two_stage_legacy"`.
- **Severity is a single 1–9 ladder** (`errorlevels.md`, one source of truth
  in `severity9.py`, generated into the webapp). The 5-value tool enum
  survives underneath as the evidence verdict (`tool_verdict`);
  `impossible` is a standalone pipeline-derived flag no model can set; 9 is
  never machine-assigned.
- Findings carry content-hash `finding_id`s, persisted PDF/XML anchors
  (word-alignment bridge for XML-analyzed papers), `computed_by`
  provenance, and per-producer five-state channel blocks.
- `metascience migrate-v2` converts legacy runs one-way (549/549 real-corpus
  docs validate); review verdicts survive by reference and orphans are
  reported, never dropped.
- Neon Postgres lands as the findings database (`db/schema.sql`,
  `metascience db-push` with replace-within-run semantics and an auto-push
  hook; best-effort — an unreachable DB never fails a paid run).
- New verbs: `flow-check`, `corpus-stats`, `findings-query`,
  `draft-pubpeer`/`draft-letter`, `gen-webapp-constants`, `migrate-v2`,
  `db-push`, `anchor-findings`, `metadata-enrich`.
- Eval fixtures are relabeled to integer 1–9 severity intervals, and a
  CONSORT regression fixture (`cerebrolysin_flow`) pins the science
  agent's flow coverage.
- `tool_verdict` joins learn nested stage headcounts: `check_flow_arithmetic`'s
  only discriminating argument is the nested `stages` list, so the scalar
  join saw nothing, every flow call matched, and the unanimity rule refused —
  the science agent's flagship tool could never join its own verdict
  (measured on the 2026-08-21 cerebrolysin run, where the abstract-vs-Results
  flow contradiction lost its validated `impossible`). Headcounts now join;
  a non-empty key set matching no call still refuses rather than guesses.
- `computed_by` is ledger-grounded: a finding citing a `run_python_script`
  script by its persisted path or label is `agent_code` even when the model
  cites it loosely (the live run stamped every script-backed row
  `model_reading`); a joined registry-tool verdict outranks the script.
  The science prompt now tells the agent to cite `analysis_code/<file>.py`
  in `reproduction`.
- Neon is wired live. `db_push.resolve_db_url` accepts
  `$METASCIENCE_DB_URL`, `$NEON_DB_URL`, or the repo's gitignored `.env`
  (the CLI and the webapp's spawned Python run without the shell profile,
  so an env-only lookup left the auto-push hook permanently silent while
  the URL sat in `.env`); the run-completion auto-push fires whenever a
  URL resolves. `findings-query` answers from the database by default when
  a URL resolves (`--files` forces the offline scan); the two modes were
  drift-checked live: 60/60 identical rows on cerebrolysin_papers. The
  test suite pins itself offline (an autouse guard blanks every URL
  channel) so unit tests can never push fixtures into the live store.
- Parallel run_meta records the release number (`version`) -- the live run
  pushed `runs.pipeline_version` NULL because only the legacy `_run_stamp`
  recorded it -- and its `prompt_sha256` now fingerprints the parallel
  prompt trio (tool_expert + science_error + adjudication) instead of the
  legacy stage prompts, which a science_error.md edit never moved.
- The judge scores fixture rows with `allow_undecided`: a matched real
  finding with no severity is an allowed landing, distinct from matching
  nothing.

## [0.9.0] — 2026-08-20

MINOR. Eight forensic-correctness fixes. The same paper may now produce
different findings: a wall-clock timeout keeps a truncated stage instead
of discarding the stream; GRIM-U refuses the wrong test in code; a
row-pair match expected under column frequencies is no longer a finding;
a conventional alpha that only accuses as an exact p is indeterminate.

- A stage that hits the wall-clock cap returns a truncated stage
  (`error_timeout`) instead of discarding the stream. MCP tools time out
  after 60 s (`METASCIENCE_MCP_TOOL_TIMEOUT`) rather than hanging the
  stage. An editorial-only timeout is disclosed separately from a
  truncated sweep.
- GRIM-U refuses in code when `test_type` is not Mann-Whitney / Wilcoxon
  rank-sum (same misapplication shape as GRIM/DEBIT `data_type`).
- Workbench image-finding counts prefer `n_duplicate_groups` and ignore
  leftover `review_manifest.json` / furniture rows.
- Raw-duplication row pairs gain a chance gate (clearing only): a
  two-shared-column match that is expected under column frequencies is
  not a finding. Unique high-precision copies still fire.
- The image-forensics coverage note no longer claims supplements were
  checked when `include_supplements` is off.
- Article-PDF docling is skipped when JATS XML is the primary text; SI
  PDFs are still extracted.
- Conventional-alpha dual-read (`p=0.05` as exact vs bound) extends to
  GRIM-U and independent t, matching the within-subjects t guard.
- `detect_copy_move` stays unwired; a ratchet test forbids registering it.

## [0.8.0] — 2026-08-20

MINOR. A Grok sweep that dumps empty findings JSON without calling a
forensic tool is retried once, and the Grok-only system prompt now says
how to reach those tools (`search_tool` then `use_tool`). The refuse
after a second empty dump is unchanged: that run still must not publish
as a clean paper.

MEASURED 2026-08-20 on `10.18332--tid--209827`: Grok 4.6 / high emitted
the empty findings skeleton on turn 1 (0 tool calls, 173 output tokens,
MCP live, 56 tools advertised) while sibling papers in the same batch
made 165–282 tool events. The diagnostic now records `result` /
`structured_output` / `stop_reason` / init `tools`, writes
`messages.stage1.json`, bills the refuse to `batch_costs.jsonl`, and
does not print a traceback.

- Stage 1 no longer forbids "load additional tools" in the shared
  prompt (that sentence fought Grok's only route to the forensic
  server). Claude's prompt still does not mention `search_tool`.
- Grok sandbox env now also sets `GROK_CLAUDE_SKILLS_ENABLED=false` and
  `GROK_CURSOR_SKILLS_ENABLED=false`.

## [0.7.0] — 2026-08-19

MINOR. A new LLM engine: the same paper may now produce different findings
depending on `--backend claude` (default) vs `--backend grok`. `run_meta.json`
gains `llm_backend`, `backend_binary_version`, and on Grok a
`sandbox_limitation` sentence.

### Selectable Grok CLI backend

`metascience analyze <paper> --backend grok` (or `METASCIENCE_LLM_CLI=grok`)
runs the two-stage pipeline on the `grok` CLI. Claude argv is unchanged,
including the space-joined `--disallowedTools` quirk.

Grok has no `--mcp-config`, no `--max-budget-usd`, and no `/usage` probe.
Forensic tools arrive as `use_tool` with a double-wrapped `OkayOutput`. A
naive port would produce a sweep that checked nothing and still read as a
clean paper. This release:

- writes a per-run sandbox under one trusted root
  (`~/.cache/metascience/grok-sandbox/`), never a fresh `mkdtemp`
- fails closed if `grok mcp doctor` is unhealthy, if the init event has no
  `forensic_metascience` server, or if stage 1 recorded zero *on-list*
  forensic calls (CLI-only image/text MCP wrappers do not count)
- does not register `analyze_paper_images` or `detect_tortured_phrases` on
  the MCP server. Those stay CLI-only: the deterministic tracks call the
  Python functions in child processes. Serving them over MCP is how a
  Grok sweep invoked them mid-run and dumped empty findings.
- refuses `--budget-usd` on Grok rather than stamping a fake
  `truncated_by_budget: False`
- records `usage_guard: unsupported_for_backend` rather than reusing the
  fail-open `(None, None)` that already means "the probe broke"
- names the weaker sandbox (`search_tool` cannot be denied) in Provenance

The eval judge, which previously omitted the required `prompt` argument to
`_run_stage` and put ~70 KB on argv, follows the run's backend and now
delivers the prompt the same way as every other stage.

## [0.6.0] — 2026-08-19

MINOR. The same paper may now produce different image findings: chrome-only
keypoint matches and four-plus identical streams are demoted to context.

### Chrome-only matches are no longer evidence

`content_match_ratio` / `n_inliers_masked` were recorded on every
transformed match and read by nothing (CHANGELOG 0.5.0). A match that
does not survive chrome-masking at the same inlier floor (`_MIN_INLIERS`,
30) is now `chart_furniture`, not `transformed_match`. Demote, never drop.

MEASURED 2026-08-19 on 105 workbench-labelled false-positive
`transformed_match` groups in Masliah: the masked-inlier floor demotes 44
of them. A ratio cut was weaker (21 at 0.30) and is kept as a diagnostic
only. A duplicated texture with no chrome still stays evidence.

### Four identical streams are a repeated element

The "placed ≥4 times" gate was tier-1 only. Nature reporting-summary and
SI PDFs re-embed the same icon per page, so it exploded as
`identical_stream` (122 groups on `10.1016--j.xgen.2023.100316`, 63 on
`10.1038--s41586-020-2681-2`). Two copies of a photograph stay evidence.

### Workbench can see PubPeer

The project table carries a PubPeer column and sorts image-integrity
papers first. Schema 1.0 `findings.IMGDUP-*` labels promote to
`image:IMGDUP-*` (`false_positive` → `false_positive_other`), so the 113
Masliah image FPs stop looking like unreviewed arithmetic.

`score_against_pubpeer.py` reports fire rate, soft figure agreement
(`Figure 1C` ~ `Figure 1`), and survival of human-labelled FPs
(`--reviews`).

- Bare `pytest` / `python -m pytest` now default to the same parallel
  workers as `metascience-test` when pytest-xdist is installed
  (`tests/conftest.py`). `addopts` still does not hardcode `-n`, so a
  machine without the plugin keeps working serially instead of crashing.
- `analyze_paper` now fetches bibliographic metadata (`metadata.json`)
  before the sweep. A failed DOI lookup cannot fail the run.
- Workbench findings name the file they were computed from (paper-relative
  POSIX path, resolved by basename if the papers root moved). Clicking a
  finding about an xlsx/csv opens that sheet; an SI PDF opens that PDF.
  Old reviews with no `inputs.path` stay file-less — we do not invent a
  location from the prose. New sweeps stamp `artefacts` onto
  `findings.json`.

## [0.5.2] — 2026-08-19

PATCH. Workbench coverage and review-pane fixes. No change to what the
agent finds.

- A completed sweep with zero findings shows `0`, not `—`. A paper with
  no run stores `n_findings: null` rather than `0`.
- The home "Image track" column names `ran_result_discarded` instead of
  counting only retained results.
- `text_channel` counts `findings_rows` / `result.matches`, not a
  top-level `matches` key the current artifact does not have.
- `figures_channel` sees `figures/` beside the paper even with no review
  directory.
- A cached metadata `error` is not retried on every paper open. Opening
  a paper no longer blocks the review pane on Crossref.
- XML locators with `section_index` 0 now scroll.
- Settings reject a missing papers root before writing `settings.json`.
- Review labels queue so a decision and a PubPeer tick cannot clobber
  each other. The PDF pane updates overlays without re-rendering pages.

## [0.5.1] — 2026-08-19

PATCH. No change to what the agent finds. New rapid-review workbench
(Next.js) over the existing scanner: project table, two-pane reviewer,
`review.json` 1.1 labels, PDF.js highlights gated on locator confidence,
XML article view when there is no PDF.

### What is not a finding

The editorial stage already writes `consequence` and `rank`. The workbench
list is ordered by `sort_findings` (severity, then consequence) plus two
tie-breaks the report does not need: a `field_norm` / unbacked editorial
finding sorts after a sweep-backed one of the same severity, and an image
group the adjudicator already explained sorts last. `report.md` order is
unchanged.

## [0.5.0] — 2026-08-17

MINOR. The same paper may now produce different findings: the image-duplication
tier records a new discriminator, and the image adjudicator's verdict policy
changed. Nothing acts on the discriminator yet — the threshold is deliberately
not chosen until the corpus distribution has been seen.

### The chrome mask — attacking the cause instead of scoring the symptom

Segmenting montages raised recall on the Masliah corpus from **17.8% to 62.5%**
(PubPeer image-integrity papers that were examined) and simultaneously made
`transformed_match` fire on **27.6% of papers**, tripping the format alarm.

Root cause: **SIFT is attracted to exactly the chrome.** Its highest-contrast
corners in a figure panel are tick marks, axis corners, legend boxes, glyph
edges, panel letters, scale bars and instrument footers. Two panels built from
one template share hundreds of pixel-identical keypoints that satisfy a rigid
transform trivially. The match is real; the evidence is made of the wrong
pixels. That also explains why the grain residual runs BACKWARDS as a
discriminator (0.802 median on unflagged papers vs 0.705 on PubPeer-flagged
ones): identical rendered text is identical pixels.

- **New `tools/chrome_mask.py`** withholds chrome from `detectAndCompute` via
  three signals — saturated paint (reusing `_OVERLAY_SAT_MIN`, not a second
  copy of it), extreme-intensity bands, and glyph/solid-bar components.
- **New `match_stats` keys `n_inliers_masked` and `content_match_ratio`**,
  recorded on every match. **No severity or kind reads them yet.**

MEASURED 2026-08-17, inliers unmasked → masked: the TEM instrument-overlay
cluster (`10.21608--mjfmct.2023.217551.1065`, the corpus's largest FP cluster)
67–118 → **0** across 12 groups; plot-template cliques 31, 58, 73 → **0**; and
the two real duplications in `10.1007--s004010051012` Fig. 3 kept 158 and 66
inliers (ratio 0.564 and 0.458), well clear of `_MIN_INLIERS` (30).

**Known cost, recorded before it is discovered the hard way:** a chart is chrome
almost everywhere, so chart-vs-chart matching becomes near-impossible under the
mask. A genuinely re-used bar chart would go near-invisible to the masked pass.
This is why the mask is a second opinion and not a replacement, and why the
eventual action must be a demotion to `chart_furniture` rather than a drop.

Three post-hoc gates were tested against the corpus and **rejected**: clique
degree (69% vs 63%), `same_registration` (38% vs 59%) and the near-identity
transform (4% vs 5%, and it zeroed a PubPeer-flagged paper for nothing).

### The adjudicator was refusing where it had already answered

On cerebrolysin the image adjudicator returned `insufficient_evidence` **46
times out of 95 groups** while having *already* diagnosed the cause correctly —
"panels show different cell fields but share the identical microscope
capture-software footer/scale bar". The schema always permitted an empty
`evidence_quote` and `_apply_image_adjudication` never demoted for one; the
prompt's "needs BOTH a measurement AND a quote" framing is what pushed those to
refusals. `image_adjudication.md` now states that a reason you can SEE is a
reason, and reserves `insufficient_evidence` for "I could not see" rather than
"I could not cite". A paper does not describe its own scale bar.

### Colour: the same pixels cannot be two colours

Dan reviewed `10.1523--jneurosci.0775-16.2016`, called all ten groups false,
and named the cause by eye: "one is green, one is pink showing tubulin or ngf
expression levels". A green Figure 2 grid and a blue/red Figure 8 grid share
the same four column headers, so the headers and frames align at grain 0.94 —
and no geometric statistic separates that, because the structures genuinely do
align. The chrome mask does not reach it either: `content_match_ratio` 0.595 at
14% kept, because the header text is INSIDE the segment rather than at its
frame.

Mean unit BGR direction over chromatic pixels; above 30° apart, demote to
`same_field_independent_capture`. 41–47° across that paper's green-against-other
pairs, 7 groups demoted (not 10 — two are `near_duplicate_phash`, which is
tier 3 and never reaches this code).

**The abstention is the design, not a rail on it.** 34 of 193 Masliah review
groups are near-grey, and both of the project's strongest true positives are
among them — `10.1007--s004010051012` Fig. 3 is a brown immunostain at
saturation 0.00. Reading "no colour" as "the colours agree" would clear the
finding this project was built on.

**Not a general furniture test.** Two segments of one figure share their headers
AND their colourway, so colour is blind to them by construction. It separates
cross-figure channel pairs; a 2° angle means "these panels are the same colour",
never "this is a duplication".

Also rejected on measurement, and recorded so they are not retried blind: a
cross-figure clique-density rule (flagged papers score *higher* — 0.50 against
0.37 — so any moderate cut is harmful, and the only safe cut demotes 3 papers
on 0-of-9 evidence).

### The adjudicator was never told to compare the two captions

Dan: it "needs to be able to read figure captions to understand when two
figures show same condition / same thing, and its inoculous". The prompt listed
captions as an input and several categories cited one, but nothing said to read
the two captions AGAINST EACH OTHER. The catalogue was one-directional — it
named what makes a shared panel damning ("presented as different conditions")
and never what makes one ordinary, so on a cross-figure match the cheapest
correct answer was `unexplained`.

Adds an explicit first step (state what condition each figure reports, then ask
whether they are the same) and a new `same_condition_in_both_figures` category,
guarded so it cannot become a skeleton key: it does not survive an undisclosed
rotation or magnification, it may not be inferred from similar wording, and it
does not apply when the captions differ.

### Calibration output stopped throwing away what it computed

`calibrate_image_dup.py` kept 3 of the ~15 statistics per match. Every
calibration question asked on 2026-08-17 was blocked by the absent 12 and
needed `run_track` re-run over labelled papers to answer what a finished sweep
had already computed. It now carries the whole `match_stats` dict; the three
original keys stay for readers written against the old shape.


## [0.4.0] — 2026-08-17

MINOR, and it is a **breaking output-schema change** — under the table above
that reads MAJOR, but this project is pre-1.0, where the convention is that
MINOR carries breaking changes. Anything switching on the string
`report.json:verdict` must be updated; nothing else in the format moved.

### Changed
- **The verdict vocabulary is now the one `verdicts.py` defines**, everywhere.
  `trustworthy | questionable | untrustworthy` → `reconciles | unresolved |
  does_not_reconcile`. The rename landed on 2026-08-11 in `verdicts.py` and in
  the viewer, and reached nothing else: **no module under `src/` imported that
  module**, `report.schema.json` still enumerated the retired words, and
  `report_render` printed `report["verdict"]` raw. So `analysis/report.md` and
  `viewer.html` **in one bundle printed different verdict words for the same
  run**, and the surface printing the retired, accusatory word was `report.md`
  — the file `bundle._FILE_BLURBS` calls "The review itself -- what you would
  read", i.e. the one people forward.

  Every surface now reads through `verdicts.canonical`: the markdown renderer,
  the CLI's colour map (which held its own copy of the retired words), the eval
  scorer, and the viewer, which reads the definitions and the old-to-new map
  from the payload (`facts.verdict_vocab`) instead of a JS literal. The JS
  comment had already claimed this was so, naming a payload key that did not
  exist — which is how a third renderer ended up with no copy at all.

  An archived report is rendered in the current words **with a note saying it
  was recorded in the earlier ones**; a word in neither vocabulary is printed
  exactly as recorded, never coerced into one of the three, for the reason
  `canonical` returns `None` rather than guessing.

- **`reconciles` no longer requires the absence of `suspicious` findings.**
  That rung is defined as a question rather than a determination, so a paper
  whose arithmetic reconciles may carry open questions — but a `reconciles`
  verdict carrying them must say so in the same breath. Only a surviving
  `impossible` / `highly_suspicious`, or claims lost to multiplicity
  correction, keep a paper off the top rung. `prompts/stage2_editorial.md` §4
  and the schema description carry the full rubric. **The same paper may now
  receive a different verdict**, which is the MINOR rule doing its job.

- `verdicts.MEANING["unresolved"]` now states that the middle rung is not a
  finding of misconduct and not a negative result. It was the one definition
  without that sentence, and it is the word a reader is likeliest to read as
  "probably fraudulent".

- Eval fixtures move to `verdict_expected: does_not_reconcile`, and
  `deterministic.check_verdict` compares through `canonical` so
  `--skip-analysis` still scores the 34 archived reports written in the old
  words. Two `None`s do not compare equal: an unparseable verdict scored
  against an unparseable expectation is not a pass.

### Added
- `tests/test_verdict_vocabulary.py` — the end-to-end property the defect
  broke: whatever a report records, `report.md` and the viewer say the same
  thing about it, neither prints the retired word as the verdict, and no module
  outside `verdicts.py` keeps its own map of the old words.

## [0.3.0] — 2026-08-17

MINOR: a new tool, a new technique enum value, and a prompt change that
governs interpretation — the same paper may now produce different findings.

### Added
- **Tortured-phrases detector**, a deterministic text-forensics track that
  runs concurrent with the stage-1 sweep (`text_track.py`, mirroring the
  image track's containment contract) and injects QUARANTINED
  `tortured_phrases` findings into stage 2. Dictionary matching in the
  Problematic Paper Screener tradition: tortured phrases ("counterfeit
  consciousness" for "artificial intelligence"), LLM boilerplate ("as an AI
  language model"), and tortured acronym expansions, from a versioned,
  sha-stamped fingerprint dictionary (`data/tortured_phrases/`, seed set
  pending Zenodo/PPS ingestion). Severity keys on DISTINCT guarded
  fingerprints (k), is pre-registered (k=1 indeterminate, k=2 suspicious,
  k≥3 highly_suspicious; first-person LLM disclaimer highly_suspicious),
  caps at `highly_suspicious` in code, and ships fully quarantined until the
  calibration gates in `tools/tortured_phrases.py` pass.
- `detect_tortured_phrases` (CLI-only by design), `metascience
  tortured-phrases`, `analyze --text-forensics/--no-text-forensics`
  (default ON — free and local), `run_meta.stages.text_forensics`, the
  `text_forensics.json` artifact, and the `tortured_phrases` technique enum
  value.
- Report limitation notes `TORTURED_PHRASES_NOTE` /
  `TORTURED_PHRASES_SCOPE_NOTE` — the blanket "no language screen" note
  narrows, never disappears, when the track ran.
- Rulebook rule 14 (how stage 2 may treat quarantined `tortured_phrases`
  rows) and a stage-1 paragraph on eyeballed mangled terminology.
- `extraction.jats.paper_text_with_source` — `paper_text` plus WHICH source
  in the fallback chain supplied the text (provenance for the track's
  status block).

### Changed
- `agent.py`'s image-track client was factored into a shared
  `_run_forensic_track` / `_validate_track_output` pair; behavior of the
  image track is unchanged (its tests run unmodified).

## [0.2.0] — 2026-08-17

MINOR: the report's contents changed, and one of the changes removes information
a reader may have been relying on.

### Added
- Reports now carry **when they were run and what produced them**. A stamp line
  under the title (`Analysed 2026-08-17 14:32 UTC · pipeline v0.2.0 (g1a2b3c)`)
  puts both on page 1 of the PDF, and a closing **Provenance** section records
  the prompt hash, the registry hash, the models that ran, and the effort
  setting. Previously a report stated neither, and a reader holding one could
  not say what had produced it.
- `version.py`: `__version__`, `git_state()` and `pipeline_version()` — the
  single source of truth, read by `pyproject.toml` via hatchling.
- This changelog, and the bump rules above.
- `metascience version --verbose`, which prints the full composite plus the
  prompt and registry hashes.

### Changed
- A run that recorded no timestamp (anything produced before `_run_stamp`
  existed) falls back to the mtime of `run_meta.json` **and says on the page
  that it is a file timestamp, not a run date** — the two diverge the moment a
  directory is copied or synced.

### Removed
- The per-finding and headline **Reproduce:** lines in `report.md` /
  `report.pdf`. The `reproduction` command is unchanged in `findings.json`,
  `run_meta.json` and the HTML viewer, which is now the only surface that offers
  a reader a runnable command — and the only one that has ever refused to print
  one that does not run.

## [0.1.0]

Everything before the version number meant anything. Reports produced under
`0.1.0` carry no stamp at all; the number was hardcoded, never bumped, and
declared in two files that were free to disagree. Treat `0.1.0` as "unversioned"
rather than as a release.
