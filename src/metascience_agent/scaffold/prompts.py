"""The three pass prompts, and the residual prompt. Text only; no I/O.

THE ORDER IS THE METHOD. Greg (2026-09-04): a person "would read the paper to get
a high-level understanding of the background, studies, results, and claims, and
then list all the variables and their characteristics, and then extract all the
relevant information (e.g. numbers) in terms of the variables and the
higher-level structure of the paper." Each pass sees the whole paper and the
JSON of the passes before it, and is asked ONLY for its own layer.

Every prompt repeats the two rules that matter more than any other instruction:
quotes are verbatim, and NOT STATED IS AN ANSWER. Measured claims are kept out of
these prompts on purpose -- a number in a prompt goes stale and then steers
(`tests/test_prompt_claims_are_dated.py`).
"""

from __future__ import annotations

import json

PREAMBLE = """\
You are the EXTRACTION component of a forensic metascience toolkit. Your only
job is a complete, structured description of what THIS paper contains. You
render no verdicts, run no checks, and flag no problems -- other components do
that, and they can only do it correctly if your description is complete and
faithful. A human who knows the paper will read your output and check it
against the PDF line by line.

Four rules govern everything you write:

1. VERBATIM QUOTES. Every `quote` field is a contiguous span copied from the
   text below, character for character. Quotes are verified automatically; a
   quote the paper did not print is recorded as such and discredits the row it
   sits on. Never paraphrase inside a quote field.

2. NOT STATED IS AN ANSWER. When the paper does not give a value -- an n, a
   unit, a bound, a test name, whether a dispersion is SD or SEM -- write null
   and, where the schema offers it, `not_stated`. A plausible fill is a defect.
   A range the paper prints (`n = 6-9`) is recorded AS A RANGE, never resolved.

3. COMPLETENESS OVER BREVITY. Efficiency is not a consideration. Every
   experiment, every variable, every reported number belongs in the output.
   Split rather than lump: two panels with different groups are two studies.

4. READABLE IDS. Ids are short slugs a person can read (`study:cfc_dose_response`,
   `grp:igf2_30`, `phase:test_24h`, `var:pct_freezing`). Use them consistently
   across passes; the JSON of earlier passes is given to you so you can.

The text below was converted from the PDF and then REPAIRED: characters the
publisher drew from symbol fonts (so that the text layer read `m` for `µ`, `o`
for `<`, `¼` for `=`, `1` for `°`, `-` for `×`) have been restored from the
rendered glyphs, and each repair is logged. The schedule-legend pictogram that
marks the injection time in figure legends is rendered `(injection)`. Figure
artwork is not in the text; only captions are. Tables are inlined as pipe
tables and are ALSO given to you as cell lists where a pass needs them.
"""


#: THE VOCABULARY IS CLOSED, and this is the one wording of it -- served to
#: every pass that SELECTS from the structure (pass 3, the table-only pass, the
#: residual pass and the table reading in `reconstruct.py`) and to none that
#: BUILDS it. `structure.close_vocabulary` enforces it whatever the model
#: writes; the instruction exists so that the model's own honest answer (null,
#: with the words it read) is the one it reaches for.
CLOSED_VOCABULARY = """\
THE VOCABULARY IS CLOSED. Every `study_id`, `group_id`, `phase_id`,
`variable_id` and `level_id` you write must be one of the ids given to you
above, copied exactly. You may not coin one: the paper was decomposed once, and
an id you compose names nothing. Where none of the declared ids fits, write null
and put what you read in the words beside it -- that is a complete answer and
the right one. An id that is not in the lists above is discarded on arrival,
counted as unbound, and the row keeps only the words; so a null with the paper's
own wording tells the next reader more than a plausible id does.
"""


def _fence(label: str, body: str) -> str:
    return f"\n\n===== {label} =====\n{body}\n===== END {label} =====\n"


def pass1_prompt(paper_text: str) -> str:
    task = """\
PASS 1 -- COMPREHENSION. Read the whole paper once, as a careful reader would,
and describe what it contains at the level of studies, results and claims.
Do not type variables or extract table numbers yet; that comes later.

What to produce, in the schema you are given:

- `paper`: bibliographic identity as printed.
- `background`: the problem, the prior findings the paper builds on (each with
  its citation as printed), the gap, and each stated aim with its quote.
- `subjects`: who or what the units are. For animals: species, strain, sex,
  age, supplier, housing. For people or organizations: `population`,
  `unit_of_analysis` (what one n counts), `setting`, `recruitment`,
  `eligibility`. Every field as printed, null where not printed; and whether a
  TOTAL n is stated anywhere.
- `statistical_analysis`: the Statistical Analysis paragraph verbatim; every
  test family it names; whether the main text says which test was used for
  which experiment; `alpha_declared` ONLY if the paper declares a threshold in
  words (a caption legend `*P<0.05` is a legend, not a declaration -- record it
  under `significance_legend` with its quote); where the paper says its detailed
  statistics live, if elsewhere.
- `procedures`: one entry per Methods subsection that describes a task,
  measurement or preparation, with a two-sentence summary and whether the
  paper says scoring was blind.
- `phases`: occasions the WHOLE paper is organized by -- survey waves,
  visits, follow-up years -- each with id, label and when. Leave empty when
  every occasion belongs to one study.
- `studies`: ONE PER EXPERIMENT. An experiment is a set of groups compared on
  an outcome under one design -- usually one figure panel, or a group of panels
  sharing the same animals and groups, or one table. For each: id, label, aim,
  the Results subsection heading, where it is reported (figure + panel letters,
  table, supplement), design type and a description of the comparison
  structure in words, the sample size as PRINTED (per group when the paper
  gives it; as a range under `n_range_printed` when the paper gives only a
  range across groups; null when it gives neither), every group with id, label,
  description and its printed n, every phase (test occasion / timepoint /
  trial) that is the study's OWN -- leave the study's phases empty when its
  occasions are the paper-level `phases` -- the outcomes measured in words, the manipulations in words, the
  Results sentences stating what was found (verbatim), the sentences stating
  what the authors take it to mean (verbatim), and the procedure ids used.
- `claims`: every claim sentence in the title, abstract, results-section
  conclusions and discussion, verbatim, with location, kind, the studies it
  rests on, and three flags: hedged, generalizes beyond the sample, causal.
- `supplements_referenced`: every supplementary item the paper points to and
  what it says is there.

Be exhaustive. A safety or control experiment is a study. A dose-response
panel is a study. A western-blot quantification is a study.
"""
    return PREAMBLE + "\n" + task + _fence("PAPER TEXT", paper_text)


def pass2_prompt(paper_text: str, pass1: dict) -> str:
    task = """\
PASS 2 -- VARIABLES AND THEIR CHARACTERISTICS. You now know the studies. List
EVERY variable the paper manipulates, measures, derives, or fixes as a design
setting, and type each one from what the paper itself says.

For each variable:
- `role`: manipulated_factor (the experimenter set its levels), time (a
  within-subject axis: test occasions, timepoints, trials, blocks),
  measured_outcome, derived_outcome (computed by a stated formula from other
  measurements), design_parameter (a fixed setting: shock intensity, session
  length, injection volume, chamber size), covariate, blocking,
  population_descriptor (age, sex, weight of the sample as a whole).
- `kind`: what kind of number ONE subject's value is. A percentage is not one
  kind: `percentage_of_observations` when it is k out of a fixed number K of
  discrete observations (freezing scored every 10 s over a 3-min session is k
  of 18); `percentage_of_time` when it is a continuous time ratio;
  `percentage_of_subjects` when it is a count of animals over the group n;
  `percentage_of_reference` when values are normalised to a reference group
  (100% = control). `integer_score` for a defined integer scale. `count` for a
  tally. `continuous` for a measured quantity.
- `units` AS PRINTED, with `units_source: not_stated` when the paper prints a
  number with no unit (a table column headed `Temp` states no unit even when
  the values are obviously degrees).
- `bounds`: `stated` when the paper prints the bound (quote the numeral);
  `definitional` when it follows from the paper's own definition (a percentage
  is 0-100; a score the Methods define from 0 to 15); `not_stated` otherwise.
  Never supply a bound from general knowledge.
- `granularity.per_subject_step`: the smallest step ONE subject's value can
  take when the paper's definition fixes it (1 for an integer score; 100/K for
  a percentage of K observations; 100/5 = 20 for percent correct over 5
  trials). null when continuous or when K is not derivable from the text; say
  which in `basis`.
- `derivation` and `derived_from` for computed variables, in the paper's words.
- `levels` for factors and time axes: every level, in order, with its numeric
  value and unit when it has one (doses; timepoints). The vehicle/control
  condition is a level.
- `studies_using`: the study ids from pass 1.
- `quote`: the sentence that establishes the typing.

Then bind the structure:
- `group_coordinates`: for every group of every study, the level of each
  manipulated factor it received. Every group in pass 1 must appear.
- `phase_coordinates`: for every phase of every study, which time variable
  and level it is.
- `procedure_parameters`: every fixed numeric setting in Methods (durations,
  intensities, volumes, concentrations, dimensions, dilutions, coordinates,
  doses of anaesthetics), AS PRINTED, with units and quote.
- `outcome_bindings`: for every study, its outcome variable ids.
- `population_descriptors`: age, sex, weight, strain descriptors with values.

Use the pass-1 study, group, phase and procedure ids exactly.
"""
    return (PREAMBLE + "\n" + task
            + _fence("PASS 1 OUTPUT (comprehension)", json.dumps(pass1, indent=1, ensure_ascii=False))
            + _fence("PAPER TEXT", paper_text))


def pass3_prompt(paper_text: str, pass1: dict, pass2: dict, tables: list[dict],
                 figures: list[dict]) -> str:
    cells_view = []
    read_elsewhere = []
    for t in tables:
        # A TABLE WITH A VERIFIED READING IS NOT RE-READ HERE. Its values,
        # variables, levels and groups are already entries (reconstruct.py);
        # listing its cells again bought a second, divergent reading and, on a
        # paper with twelve tables, an output past the 64,000-token cap.
        if (t.get("reconstruction") or {}).get("status") == "verified":
            read_elsewhere.append({"table_id": t["id"], "label": t["label"], "caption": t.get("caption"),
                                   "n_cells": t.get("n_cells"), "note": "already read as entries; give NO "
                                   "table_reading and list NO comparison from it"})
            continue
        cells_view.append({
            "table_id": t["id"], "label": t["label"], "caption": t.get("caption"),
            "sections": t.get("sections"), "footnotes": t.get("footnotes"),
            "header_rows": t.get("header_rows"),
            "col_labels": t["col_labels"], "row_labels": t["row_labels"],
            "cells": [{"row_label": c.get("row_label"), "col_label": c.get("col_label"),
                       "raw": c.get("raw")} for c in t["cells"]],
        })
    figs_view = [{"id": f["id"], "label": f["label"], "panels": f["panels"],
                  "caption": f["caption"]} for f in figures]
    task = """\
PASS 3 -- VALUES, IN TERMS OF THE STRUCTURE. You now have the studies and the
typed variables. Locate every reported number at its coordinate.

A. TABLE READINGS. For each table in the cells list, do NOT transcribe the
numbers -- they are already extracted. Give the READING: for every distinct
`col_label` (copied exactly), which study, group and phase that column is; for
every distinct `row_label` (copied exactly), which variable it is and what
statistic form its cells take (`mean_pm_sem`, `mean_pm_sd`, `mean_pm_unstated`
when the table prints `x (±y)` and NOWHERE says whether y is SEM or SD,
`percentage_of_subjects`, `count`, ...). Say whether the table or its
caption/footnotes state the n behind each column, and where the paper states
what the ± means for THIS table, if it does. A row label whose variable you
cannot identify gets `variable_id: null` and a note -- do not force one.

B. PROSE VALUES. Every number printed in the abstract, Methods, Results,
Discussion, figure captions and table captions that is a reported value or a
design setting: sample sizes (as printed, ranges kept as ranges, with
`applies_to_all_groups` true when the caption gives one n for a whole panel),
doses, timepoints, durations, thresholds, chance levels, percentages,
concentrations, dimensions, ages. For each: the variable it belongs to (null if
none fits), the statistic, the value EXACTLY as printed, its coordinate (study,
group, phase -- null where the sentence does not fix one), its quote, and where
it sits. Every numeral in the paper's analytic text will afterwards be checked
against this list, and anything you did not account for will be shown to you
again. Be exhaustive here; a number listed twice is cheap, a number missed is
not.

C. COMPARISONS. Every statistical comparison the RESULTS TEXT or a figure caption
REPORTS WITH EVIDENCE: each sentence or starred caption contrast that says
something was significantly different, not different, or a trend, AND carries
a printed test statistic, an exact p, or a threshold (a star, `p < .05`). A
table's statistics are NOT comparisons here: a table already read as entries is
listed below by id only, and an unread table's cells belong in its
`table_reading`, not in this list. A
sentence in the Abstract or Discussion that restates a result without one is a
CLAIM (pass 1 already holds it) -- do not list it here. For each: study,
outcome variable, what is compared with what (group ids, phase ids, words),
the test the paper names FOR THIS comparison (null when Methods lists tests
without saying which applies -- do not guess from the design), the statistic,
df and p AS PRINTED (null when not printed in the main text), the p threshold
when the result is given only as a star or `P<0.05`, the verbal significance,
the direction FROM THE CLOSED SET (first/second by the order of the contrast's
ids; positive/negative for an association; the paper's words go in
`direction_words`), the kind of place it is reported (`reported_in_kind`) and
its label, the quote, and where the paper says the full statistics are.

D. FIGURE PANELS. For each figure panel the captions describe: study, y-axis
variable, groups drawn, phases drawn, the n the caption gives for that panel as
printed, what the error bars are said to be, and the caption fragment. The
bar heights themselves are NOT in the text and must not be estimated.

Use the pass-1 and pass-2 ids exactly.
"""
    return (PREAMBLE + "\n" + task + "\n" + CLOSED_VOCABULARY
            + _fence("TABLES (cells, exact labels)", json.dumps(cells_view, indent=1, ensure_ascii=False))
            + _fence("TABLES ALREADY READ AS ENTRIES (no table_reading, no comparisons from these)",
                     json.dumps(read_elsewhere, indent=1, ensure_ascii=False))
            + _fence("FIGURES DETECTED", json.dumps(figs_view, indent=1, ensure_ascii=False))
            + _fence("PASS 1 OUTPUT (comprehension)", json.dumps(pass1, indent=1, ensure_ascii=False))
            + _fence("PASS 2 OUTPUT (variables)", json.dumps(pass2, indent=1, ensure_ascii=False))
            + _fence("PAPER TEXT", paper_text))


#: Cells per pass-3 call. One call over twelve tables (about 900 cells) overflowed
#: the 64,000-token output cap on jamanetworkopen.37679; a batch this size is
#: well inside it, and a table read alone is read once, not against eleven others.
PASS3_CELL_BUDGET = 250


def pass3_batches(tables: list[dict], budget: int = PASS3_CELL_BUDGET) -> tuple[list[dict], list[list[dict]]]:
    """(tables the main pass-3 call reads, batches of tables for separate
    table-only calls). Verified tables go nowhere: they are already entries.
    The main call keeps unread tables up to `budget` cells; the rest are
    batched, each batch within `budget`, a single oversized table alone."""
    unread = [t for t in tables if (t.get("reconstruction") or {}).get("status") != "verified"]
    main: list[dict] = []
    used = 0
    rest: list[dict] = []
    for t in unread:
        n = int(t.get("n_cells") or len(t.get("cells") or []))
        if not rest and used + n <= budget:
            main.append(t); used += n
        else:
            rest.append(t)
    batches: list[list[dict]] = []
    cur: list[dict] = []; cur_n = 0
    for t in rest:
        n = int(t.get("n_cells") or len(t.get("cells") or []))
        if cur and cur_n + n > budget:
            batches.append(cur); cur, cur_n = [], 0
        cur.append(t); cur_n += n
    if cur:
        batches.append(cur)
    return main, batches


def dedupe_readings(readings: list[dict]) -> list[dict]:
    """One table_reading per table id, the first kept, order preserved."""
    seen: set = set()
    out: list[dict] = []
    for r in readings or []:
        tid = r.get("table_id")
        if tid in seen:
            continue
        seen.add(tid)
        out.append(r)
    return out


def pass3_tables_prompt(pass1: dict, pass2: dict, tables: list[dict]) -> str:
    """Pass 3 for a batch of unread tables only: the table_readings, nothing
    else. Same schema as pass 3; prose_values, comparisons and figure_panels
    are expected empty and are ignored on merge."""
    cells_view = [{
        "table_id": t["id"], "label": t["label"], "caption": t.get("caption"),
        "sections": t.get("sections"), "footnotes": t.get("footnotes"),
        "header_rows": t.get("header_rows"),
        "col_labels": t["col_labels"], "row_labels": t["row_labels"],
        "cells": [{"row_label": c.get("row_label"), "col_label": c.get("col_label"),
                   "raw": c.get("raw")} for c in t["cells"]],
    } for t in tables]
    task = """\
PASS 3 (TABLES ONLY). You have the studies and the typed variables. For EACH table
below give its `table_reading`: which study, group and phase each column is
(`column_map`, labels copied EXACTLY), which variable and statistic form each
row is (`row_map`, labels copied EXACTLY; null variable when none fits, with a
note). Leave `prose_values`, `comparisons` and `figure_panels` EMPTY: this call
is the tables and nothing else. Use the pass-1 and pass-2 ids exactly.
"""
    return (PREAMBLE + "\n" + task + "\n" + CLOSED_VOCABULARY
            + _fence("TABLES (cells, exact labels)", json.dumps(cells_view, indent=1, ensure_ascii=False))
            + _fence("PASS 1 OUTPUT (comprehension)", json.dumps(pass1, indent=1, ensure_ascii=False))
            + _fence("PASS 2 OUTPUT (variables)", json.dumps(pass2, indent=1, ensure_ascii=False)))


def residual_prompt(residual: list[dict], values_index: list[dict], structure: dict,
                    iteration: int = 1) -> str:
    task = f"""\
PASS 3b, ITERATION {iteration} -- PLACING THE NUMERALS NOT YET PLACED.

You hold the scaffold of this paper: its studies, groups, phases, variables and
the values already located (indexed below). Below that is every numeral in the
paper's text, outside the reference list, that the passes so far have NOT
placed, in reading order, each with the whole sentence it sits in, its section
and its page. These are not noise: most are real values the paper printed --
sample sizes, doses, timepoints, durations, settings, percentages, thresholds
-- that were presented badly the first time. Your task per numeral is only to
say where it belongs. Read the rows in order, as sentences.

For each numeral give ONE disposition:

- `value` -- a reported value or design setting. Name an existing `val:` id
  from the index when the index already holds this number for this place;
  otherwise DEFINE the value in `new_values` (full row: variable id or null,
  statistic, `printed` EXACTLY as the numeral is printed, coordinate -- study,
  group, phase, null where the sentence does not fix one -- the verbatim
  sentence as quote, location) and name its id here. A range such as `6-9` is
  two numerals and ONE value with statistic `n_range`.
- `duplicate_of_value` -- the same number printed again for a value in the
  index (name it).
- `design_parameter` / `sample_size` -- only when it IS such a value and the
  sentence genuinely fixes no coordinate at all; prefer `value` with a new row.
- `axis_tick`, `citation_year`, `citation_page`, `figure_or_table_ref`
  (`Figure 1a`, `Table 1`, `Supplementary Figure S2`), `panel_or_item_label`
  (`Test 1`, `E4`, `A1`, `Trials 1-5` as labels), `coordinate_label`,
  `section_or_list_number`, `date_or_id` (grant numbers, DOIs, dates, catalog
  numbers, postal codes, phone numbers, page ranges), `affiliation`,
  `unit_or_catalog`, `textual_count` (a number that is part of the procedure's
  description rather than a setting: `three arms`, `two objects`).
- `ambiguous` -- the value plausibly belongs to TWO OR MORE coordinates in the
  scaffold and the paper does not settle which. List every candidate in
  `candidates` (study, group, phase, variable, statistic, and why each is
  plausible) and say in `distinguisher` what would settle it. "This 24 is
  either the n at the 24-hour timepoint or the hours themselves; the sentence
  does not say" is a complete and useful answer -- a person adjudicates it in
  seconds. Ambiguity is a property of the paper as often as of the reader.
- `unaccounted` -- UNPLACED: no coordinate in the scaffold fits, and say why in
  `note` (only in a figure; inside a reference; an equipment specification the
  scaffold does not model; a referent the paper never states).

Placement is a matching problem over the finite set of coordinates the
scaffold defines -- not "what is this number?" but "which of these known
places does it belong to?". An unplaced numeral is strictly better than a
wrongly placed one; a wrongly placed one is the worst outcome. Do not skip an
id. Do not invent a coordinate the sentence does not fix.
"""
    return (PREAMBLE + "\n" + task + "\n" + CLOSED_VOCABULARY
            + _fence("NUMERALS NOT YET PLACED (reading order)", json.dumps(residual, indent=1, ensure_ascii=False))
            + _fence("VALUES INDEX (id, printed, variable, statistic, coordinate)",
                     json.dumps(values_index, indent=1, ensure_ascii=False))
            + _fence("STRUCTURE (study, group, phase, variable ids)",
                     json.dumps(structure, indent=1, ensure_ascii=False)))
