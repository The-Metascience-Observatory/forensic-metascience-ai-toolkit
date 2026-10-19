"""Run the forensic checks on the account's own premises.

WHAT THIS IS. The account was built so that "the set of valid checks is a
function of the scaffold's composition and nothing else" (schema.py), and
`applicability.census` already computes that function as a READ-ONLY
enumeration. It calls nothing. This module is the wire: it takes the same
premise lookups, translates them into the registry's parameter names, and calls
`registry.BY_NAME[tool].call(args)` in process. Zero paid model calls -- every
input is already on disk.

WHY IT GOES THROUGH THE REGISTRY AND NEVER ROUND THE SIDE. `ToolSpec.call` is
where GATE 0 (a number sent as a string), GATE 1 (non-finite input), GATE 2
(measured or OCR'd provenance), GATE 3 (missing printed precision) and GATE 4
(the declared variable) live. Calling the underlying function directly would
reimplement five gates, badly, and this repo has already paid for that class of
omission once (see `registry.py`'s opening note). The verdict a tool returns is
COPIED VERBATIM and never re-severitied: the dispatch rule.

`variable_id` IS DELIBERATELY NOT PASSED. GATE 4 would reconcile it against the
anatomy's `declared` store, which the scaffold never populates, so every call
would come back `not_declared`. The id is recorded on the bridge's own record
instead, which is where a reader looks for it anyway. (Translating scaffold
variables into `anatomy.Variable` to reuse `forensic_kwargs` was considered and
rejected: two vocabularies, two translations, two chances to drift.)

THREE LAYERS, PURE UNTIL THE LAST.
  1. `candidates(account, text)` -- one Candidate per (family, primary value),
     carrying every input value id, the variable and the coordinate. Structural
     only: it says WHAT could be checked, never whether it may be.
  2. `translate(cand)` -- one pure function per family (`to_grim_kwargs`,
     `to_count_percent_kwargs`, `to_sd_or_se_kwargs`, `to_grimmer_kwargs`,
     `to_sprite_kwargs`). Each returns kwargs plus the premises they rest on, or
     a `Refusal` naming EVERY missing premise and the value or variable it was
     missing from. Nothing defaults, infers from a label, or reads position.
  3. `run(out_dir)` -- calls the registry and writes `checks.json` / `checks.md`.

EVERY PREMISE IS A LOOKUP, AND WAVE 7b IS WHY. The admission decision -- is this
value printed, is its variable id corroborated, is this cell a description or a
model output, is its literal readable, is the step of 1 established, may this
bound be passed -- is made ONCE by `scaffold/premises.py` and stamped on the
account before the first candidate is formed. `_provenance`, `_binding`,
`_descriptive`, `_granularity`, `_bounds` and `_literal` below are thin readers
of that stamp; none of them decides anything. The bridge had reinvented five of
those judgements weakly, two adversarial rounds found the same five places
again, and a heuristic tightened is a heuristic still.

THE LITERAL IS READ TWICE, ON PURPOSE. `bind.read_literal` produces the
account's `numeric` and `decimals`; `premises.read_plain` (aliased here as
`_read_plain`) re-derives both from `printed` under a STRICTER grammar of its
own, and the two are compared on every record AND PRINTED when they disagree.
This is the one place in this package where a second implementation of one rule
is wanted rather than tolerated: the whole point of the check is that a number
was read correctly, and a check that inherits the reader it is checking proves
nothing. The strict grammar admits exactly `plain` and `percent`; every other
form -- a word (`Twenty-six`), a qualifier (`approximately 84,000`), a range
(`6-9`), and any comma-bearing literal, because a thousands separator and a
decimal comma are undecidable PER VALUE -- is refused rather than guessed.

A REFUSAL IS THE PRODUCT, NOT A FAILURE. `refused` is a docket: every candidate
that did not run, with a closed reason code and the ids it was missing from.
Most of it can only be discharged by a structural adjudication or a re-read, and
the bridge never fills any of it.
"""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .. import registry as _registry
from . import applicability as _app
from . import codestamp as _codestamp
from . import premises as _premises
from . import reconstruct as _reconstruct  # the one reader of the `n (pct%)` cell
from . import schema as _schema
from . import structure as _structure

SCHEMA_VERSION = "scaffold_checks/1"

# --------------------------------------------------------------------------
# The families, and the census's stale tool names corrected in place
# --------------------------------------------------------------------------

#: (bridge family, registry tool, the census family it refines).
#:
#: The census names a family and a TOOL, and five of its seven names were stale:
#: `grim_test` is registered as `grim_check`, `grimmer_test / sprite` as
#: `grimmer_check` / `sprite_reconstruct`, `sd_range` as `check_sd_range`,
#: `stat_to_p` as `recalc_stat_to_p`, and `check_bounds` /
#: `check_claim_vs_result` name no registry tool at all. Corrected in
#: `applicability.FAMILIES` rather than restated here, so there is one list.
FAMILIES: tuple[tuple[str, str, str], ...] = (
    ("count_percent", "check_count_percent", "count_percent"),
    ("grim", "grim_check", "grim"),
    ("sd_or_se", "check_sd_or_se", "sd_or_se_plausibility"),
    ("grimmer", "grimmer_check", "grimmer_or_sprite"),
    ("sprite", "sprite_reconstruct", "grimmer_or_sprite"),
)

FAMILY_NAMES: tuple[str, ...] = tuple(f for f, _, _ in FAMILIES)
TOOL_OF: dict[str, str] = {f: t for f, t, _ in FAMILIES}
CENSUS_FAMILY_OF: dict[str, str] = {f: c for f, _, c in FAMILIES}

#: Census families the bridge does not wire, and why. Stated here so that a
#: census-bindable coordinate the bridge never runs still carries a reason.
UNWIRED: dict[str, str] = {
    "range_within_bounds": "no_registry_tool",
    "claim_vs_result": "no_registry_tool",
    "statistic_to_p": "family_not_wired",
}

#: REGISTRY TOOLS WHOSE POPULATION THIS ACCOUNT CAN FORM AND WHICH ARE STILL NOT
#: CALLED, each with the premise that blocks it. It is NOT `UNWIRED` above:
#: `UNWIRED` is keyed by CENSUS family and answers "this coordinate was bindable
#: and nothing ran on it", and the census enumerates no regression family at all,
#: so a coefficient table is bindable by nobody and appeared in no total. The
#: registry holds 62 tools and this bridge calls 5, and the 57 that stay silent
#: were, until now, silent in the docket too -- an absence with no
#: representation, which is the one thing this package is not allowed to leave
#: (`premises` exists so that a missing premise is DECLARED rather than
#: defaulted; the same rule binds a missing CHECK).
#:
#: THE POPULATION IS COUNTED FROM THE ACCOUNT, NEVER ASSERTED HERE
#: (`unwired_population`), because a number written into a comment is falsified
#: by the next reading of the next paper and nothing fails when it is.
#:
#: `check_regression` IS THE ONE WORTH READING, and the measurement is on the
#: only real account this repo holds (ajcp.70049, 2026-09-13). It is the tool
#: for exactly the population `to_sd_or_se_kwargs` already identifies and
#: refuses -- 24 `dispersion_of_coefficient` refusals on that account -- and it
#: needs NO n, which is the premise that blocks all 127 candidates there. So it
#: looks like the whole of the coverage answer, and it is not wired for three
#: measured reasons, any one of them sufficient:
#:
#:   1. NO df, AND THE VERDICT TURNS ON IT. `check_regression` returns
#:      `indeterminate` on every row without a df. Supply one and rows begin to
#:      flag -- and WHICH rows flag depends on which df was supplied: replayed
#:      over this account's own population at df = infinity and again at
#:      df = n - k, the two flag sets did not name a single row in common. So
#:      every accusation such a wiring produced would be an accusation the
#:      other df disowns, and the paper prints neither. Choosing one is
#:      CLAUDE.md 8d invariant 1's prohibited move exactly: a derived boundary
#:      may narrow a premise, never supply one.
#:
#:      THE COUNTS ARE DELIBERATELY NOT WRITTEN DOWN HERE, and the reason is
#:      worth more than the counts were. An earlier version of this comment, and
#:      of the reader-facing `why` below, asserted four of them: "at df =
#:      infinity this tool flags 3 of 63 coefficient rows ON THE WORKING ACCOUNT
#:      and at df = n - k it flags 6, four of them different rows". Every one of
#:      those numbers is REPRODUCIBLE -- on the hand-retyped fixture in
#:      `test_scaffold_checks_round29`, which holds 63 rows because it retypes
#:      Tables 2, 3 and 4. THE ACCOUNT DOES NOT HOLD 63. It types Table 4's
#:      dispersions `dispersion_unstated` and its estimates `other`, not
#:      `coefficient`, so `unwired_population` forms 42 rows and not 63, and
#:      `checks.md` was printing 42 and 63 in ONE TABLE ROW. The sentence was not
#:      false arithmetic; it was a fixture measurement wearing the account's
#:      name, which is the harder version to catch and the reason the rule two
#:      paragraphs above is absolute rather than a preference. (It is also a
#:      fourth instability in its own right: a wiring keyed on
#:      `statistic == "coefficient"` would not reach Table 4 at all.)
#:      Keep the shape, drop the count: `unwired_population` counts the
#:      population at render time, and a replay re-measures the flag sets on
#:      whatever account is actually in front of you -- replayed that way, the
#:      two df choices overlap in NO row at all.
#:   2. THE SE PREMISE IS UNSTABLE INSIDE ONE ACCOUNT. Tables 2, 3 and 4 of that
#:      paper carry a BYTE-IDENTICAL column band (`Coefficient | M (SD)`) and the
#:      reading typed their parentheticals `se`, `sd` and `dispersion_unstated`
#:      respectively -- and the paper's own header and footnote call all three
#:      SD. A wiring keyed on `statistic == "se"` therefore draws its population
#:      from a coin flip: keyed on `se` it flags Table 2's `-4.51 (1.50) < .001`,
#:      keyed on `sd` it flags Table 3's `8.57 (3.03) .01` instead -- and
#:      `8.57 (3.03)` is the cell CLAUDE.md 8f records as having already
#:      produced one false `impossible` on this honest paper.
#:   3. THE DIRECTIONAL GATE IS AN ARGUMENT WE WOULD BE CHOOSING, AND THE
#:      OBVIOUS CHOICE IS THE WRONG ONE. An earlier version of this comment said
#:      `check_regression` "is not directional"; that is FALSE about the tool.
#:      It delegates its p comparison to `ttest._p_matches`, which is directional
#:      by DEFAULT and has been since 2026-08-12 for this exact reason:
#:      `p_is_threshold=None` and `True` both enforce the interval only in the
#:      over-claim direction, and only `False` -- "the paper printed an exact
#:      value" -- tests both sides. So conservative reporting is flagged by ONE
#:      ARGUMENT VALUE WE CONTROL, not by the tool.
#:
#:      That makes it a hazard rather than a defect, and the hazard is real,
#:      because the natural wiring walks straight into it: reading the argument
#:      off the printed literal, `p_is_threshold = printed.startswith("<")`,
#:      supplies `False` for every plain `.01` in the table -- and `.01` is the
#:      commonest printed p on this account. Replayed both ways over the same
#:      population and the same df, that wiring flags strictly more rows than
#:      passing `None`, and the extra rows are papers reporting a p LARGER than
#:      their own B/SE implies. `_p_matches` own docstring already names the
#:      safe choice: pass `None` unless the paper's exactness has been checked.
#:      This reason therefore does not block a wiring; it fixes one of its
#:      arguments, and reasons 1 and 2 are the ones that block.
#:
#: WHAT WOULD HAVE TO EXIST FIRST, in the order it would remove a reason: a df
#: on the value (`schema.STATISTICS` already admits `df`, so this is a reading
#: gap and not a schema one) or a stated df-free rule for a THRESHOLD claim,
#: since the t tail is monotone decreasing in df and the normal is its infimum,
#: so `p_normal > c` refutes `p < c` at every df; and a corroborated SE premise
#: that does not rest on one reading of one column label. The directional gate
#: is not on that list: it already exists, and the wiring must pass
#: `p_is_threshold=None` rather than derive `False` from a printed literal.
NOT_WIRED_TOOLS: dict[str, dict[str, str]] = {
    "check_regression": {
        "population": "a coefficient and its dispersion printed in one table cell, "
                      "with a p in the cell beside it",
        "blocked_on": "df_not_captured",
        # NO COUNT IN THIS STRING, and it is a reader-facing string, so the rule
        # is enforced (`test_scaffold_checks_round30`). The claim it used to
        # carry a count for is the stronger half anyway: not "how many rows
        # flag" but that the flag SET turns on a df the paper never printed, so
        # the two defensible df choices accuse different rows.
        "why": "the account carries no df for a table cell, and the verdict turns on "
               "it: without a df every row returns `indeterminate`, and supplying one "
               "makes the flagged set a function of WHICH df was supplied -- replayed "
               "at df = infinity and at df = n - k, the two sets name different rows. "
               "The paper prints neither, so every such flag would rest on a df we "
               "invented. The SE premise is unstable too: byte-identical "
               "`Coefficient | M (SD)` bands in one paper were typed `se`, `sd` and "
               "`dispersion_unstated`, so which cells a wiring even reaches depends on "
               "one reading of one column label",
    },
    "recalc_stat_to_p": {
        "population": "a comparison printing a test statistic, its df and its p",
        "blocked_on": "family_not_wired",
        "why": "the census already reports this family's own blocker per account "
               "(`statistic_to_p` in `census_vs_bridge`), and the population column "
               "beside this one is the count: where it reads zero, no comparison in "
               "the account printed a test statistic at all and wiring the tool would "
               "add no call. The premise is the paper's, not the bridge's",
    },
}

# --------------------------------------------------------------------------
# The closed refusal vocabulary
# --------------------------------------------------------------------------

#: The premise slots, IN THE ORDER a refusal reports them. A candidate collects
#: EVERY missing premise (`reasons`); `reason` is the first one in this order.
#: Reporting only the first would hide that `var:service_area_population` fails
#: GRIM for two independent reasons -- no per-subject step AND a literal with a
#: thousands separator -- and a reader supplying one of them would find the
#: check still refused.
#:
#: APPLICABILITY AND PARTNER ARE TWO SLOTS, NOT ONE, and the split is the whole
#: reason the order is defensible for every family at once. "This dispersion
#: sits beside a regression coefficient" says the FAMILY DOES NOT APPLY here,
#: and it outranks every premise; "the paper prints no count beside this
#: percentage" says the family applies and one input is absent, which is a
#: weaker statement than "we do not know what this percentage is a percentage
#: OF". So an applicability failure is reported first and a missing partner
#: last, and a percentage at a group with no resolvable n reports `no_group_n`
#: rather than the missing count.
#:
#: `error` LEADS THE ORDER and is not a premise at all. A candidate whose
#: evaluation raised did not fail to find a premise -- it fell over, and that
#: outranks every statement about what the paper prints. It is first so that a
#: reader is never told "no count is printed beside this percentage" about a
#: candidate that in fact divided by zero.
PREMISE_ORDER: tuple[str, ...] = (
    "error", "family", "provenance", "binding", "applicability", "variable", "kind",
    "granularity", "literal", "bounds", "n", "partner",
)

#: reason code -> (premise slot, what it means). CLOSED: every refusal the
#: bridge emits is one of these, and `tests/test_scaffold_checks.py` fails on a
#: code that is not.
#:
#: HALF OF IT IS `premises.REASONS`, MERGED HERE RATHER THAN RESTATED. The
#: premise-shaped codes belong to the module that makes the judgement -- after
#: wave 7b the bridge adds no premise judgement of its own, so it may not own
#: the words for one either -- and the merge keeps ONE closed vocabulary for a
#: refusal to draw on. The codes below are the bridge's own: they are about
#: pairing, wiring and arithmetic the bridge does, not about what the paper
#: prints.
BRIDGE_REASONS: dict[str, tuple[str, str]] = {
    # error -- the candidate did not survive its own evaluation
    "check_raised": ("error", "evaluating this candidate raised; the exception type and "
                              "message are in the detail, and no other candidate was "
                              "affected"),
    "value_malformed": ("error", "the value could not be read as a value at all (no id, or "
                                 "a location or coordinate that is not an object); it was "
                                 "skipped and no other candidate was affected"),
    "duplicate_variable_id": ("error", "two or more VARIABLES in this account carry this id, so "
                                       "it does not name one record; the variable table is "
                                       "last-write-wins in both readers of it, and a value bound "
                                       "to the id was adjudicated against the other variable's "
                                       "kind, bounds and granularity -- the value-id defect one "
                                       "table over (`premises.variables_by_id`)"),
    "duplicate_value_id": ("error", "two or more values in this account carry this id, so the "
                                    "id does not name one record; `_Index.by_id` is "
                                    "last-write-wins, and the candidate formed from one value "
                                    "would have been translated from the other's number "
                                    "(`premises.duplicate_ids`)"),
    # family
    "no_registry_tool": ("family", "no registry tool takes this family's premises"),
    "family_not_wired": ("family", "the tool exists; this wave does not wire it"),
    "unknown_family": ("family", "the caller asked for a family this bridge does not "
                                 "define; it is refused BY NAME rather than raising, "
                                 "because `families=('typo',)` used to leave the run with "
                                 "no checks, no refusals and no docket at all -- a "
                                 "caller's error taking the paper's whole sidecar with it"),
    "no_bridge_candidate": ("family", "the census binds this coordinate and the "
                                      "bridge formed no candidate at it"),
    # applicability -- this family does not apply to this value at all
    "dispersion_of_coefficient": ("applicability", "the dispersion sits beside a "
                                                   "regression coefficient, so it is a "
                                                   "model standard error and not a "
                                                   "descriptive dispersion"),
    "no_paired_mean": ("applicability", "no mean sits at this dispersion's own cell"),
    "no_paired_sd": ("applicability", "no SD sits at this mean's own cell (a SEM is not one)"),
    # partner -- the family applies and the second input is absent
    "count_not_printed": ("partner", "the paper prints no count beside this percentage"),
    "ambiguous_pairing": ("partner", "two or more values could be the partner"),
    # variable
    "no_variable": ("variable", "the value is bound to no declared variable"),
    # kind
    "kind_not_integer": ("kind", "the variable's kind is not integer-valued, and this "
                                 "family is defined only for integer observations"),
    "percentage_is_a_proportion": ("kind", "the variable's kind is `proportion` -- a "
                                           "fraction of one -- and `check_count_percent` "
                                           "takes a percentage of a hundred"),
    "percentage_scale_not_established": ("kind", "the printed literal is between 0 and 1 "
                                                 "exclusive, carries no `%`, and sits on a "
                                                 "variable whose kind is not a percentage "
                                                 "kind, so a proportion and a percentage "
                                                 "are the same digits here"),
    "percentage_base_is_not_subjects": ("kind", "the variable's kind says this percentage is "
                                                "taken over observations, time or a reference "
                                                "value (`premises.NON_SUBJECT_PERCENTAGE_KINDS`), "
                                                "and the only denominator the account carries "
                                                "at a coordinate is a count of SUBJECTS, which "
                                                "is not its base"),
    # n
    "no_group_n": ("n", "no n value sits at this value's own (study, group)"),
    "ambiguous_n": ("n", "the n rows at this coordinate are not one plain integer"),
    "n_not_printed": ("n", "every n row at this coordinate fails the provenance gate every "
                           "other input meets -- not a table cell the paper printed, nor "
                           "prose whose own number sits inside its verified quote"),
    "n_binding_not_corroborated": ("n", "every n row at this coordinate rests on a variable "
                                        "id the name join contradicts or could not check "
                                        "(`id_check`)"),
    "n_disagrees_with_structure": ("n", "the n in the values disagrees with the n "
                                        "parsed from the declared group's own label"),
    "declared_n_not_comparable": ("n", "the declared group n is not an exact integer, so it "
                                       "cannot be shown to agree with the printed n; a "
                                       "truncating comparison would pass 30.4 against 30"),
    "n_not_positive": ("n", "the denominator printed at this coordinate is zero or negative, "
                            "so it is not a denominator at all; refused before any tool "
                            "divides by it (wave 7b)"),
    "another_denominator_fits": ("n", "the paper's own count and percentage are reproduced "
                                      "exactly at an integer denominator that is not the n "
                                      "bound here (`premises.other_bases_that_fit`), so the "
                                      "disagreement is explained by the base rather than by "
                                      "the arithmetic; a percentage over a different base (row "
                                      "versus column, a subgroup, 'of those with complete "
                                      "data') is the commonest convention in a clinical table "
                                      "and this check cannot tell the two apart"),
    "denominator_contradicted_by_the_sentence": ("n", "the value's own sentence states the "
                                                      "population it is reported over "
                                                      "(`premises.population_sizes`), and it is "
                                                      "LARGER than the n bound here, so the two "
                                                      "cannot both be this statistic's "
                                                      "denominator -- a cluster trial's `n = 6` "
                                                      "clinics beside `The 240 patients ... "
                                                      "attended a mean of 3.4 visits`"),
    "n_not_corroborated": ("n", "one n row stands alone at this coordinate: the structure "
                                "declares no n for the group, the group's own label prints "
                                "none, no second row of the paper agrees with it, and the "
                                "row's own quote does not print `n = <that integer>`. A "
                                "lone integer may be a count of EVENTS rather than of "
                                "subjects, and nothing here can tell the two apart"),
    "study_n_over_several_arms": ("n", "the only n is a study-level figure the sentence says "
                                       "applies to every group, and the study declares more "
                                       "than one group; applying the whole study's n to one "
                                       "arm is a guess about how the arms divide it"),
    "count_at_this_coordinate_may_be_its_n": ("n", "integers printed as shares of a base sit at "
                                                   "this coordinate -- `38 (59%)` -- and a cell "
                                                   "of that form types `count`, so none of them "
                                                   "was ever a candidate denominator. That is "
                                                   "right about the cell and silent about the "
                                                   "study: a retention row is the same "
                                                   "arithmetic as a category row, and its "
                                                   "integer IS the population the other "
                                                   "statistics here were computed over. The "
                                                   "structure could not bind ANY of these counts "
                                                   "to a declared variable or level, so the "
                                                   "account cannot say that they are categories "
                                                   "rather than stages, and the n left standing "
                                                   "may be the stale one"),
    "phase_n_over_several_phases": ("n", "the account states an n at some PHASE of this group, "
                                         "and this value either sits at a phase that has none "
                                         "or sits at NO PHASE AT ALL -- so the group's "
                                         "denominator varies by wave and the only n available "
                                         "here cannot be shown to be this one's; a baseline's n "
                                         "is not a follow-up's, and choosing which wave an "
                                         "unbound n belongs to (or which wave an unbound VALUE "
                                         "belongs to) is the guess this layer exists to remove"),
    "analysed_n_stated_for_another_stage": ("n", "the value sits at a named phase, the only n "
                                                 "available carries no phase of its own, and the "
                                                 "paper's text states a DIFFERENT number of "
                                                 "subjects analysed at a stage of the study "
                                                 "(`premises.analysed_counts`) -- `Twenty-four "
                                                 "nurses attended the twelve-week visit` beside "
                                                 "an enrolled `n = 28`, with no `n = 24` "
                                                 "notation for the reading to key on. The "
                                                 "unbound n cannot be shown to be this wave's, "
                                                 "and the paper's own number for this wave is "
                                                 "not in the account"),
    "analysis_unit_is_not_the_subject_count": ("n", "the paper states the number of ANALYSIS "
                                                    "UNITS its design yields and it is not the n "
                                                    "bound here (`premises."
                                                    "analysis_unit_statement`) -- 28 nurses "
                                                    "recorded on three nights each, `giving 84 "
                                                    "nurse-nights of actigraphy` -- so a mean "
                                                    "over those units has a denominator this "
                                                    "account does not carry, and the group's "
                                                    "count of SUBJECTS is not it"),
    "subgroup_stated_in_the_sentence": ("n", "the value's own sentence names a SMALLER "
                                             "population than the n bound here and prints its "
                                             "size (`premises.population_sizes`) -- `The 21 "
                                             "children who ate a school lunch had a mean score "
                                             "of 11.90` beside a group n of 34 -- so the "
                                             "statistic is over the subgroup and not over the "
                                             "group; the subgroup's own size is NOT taken as "
                                             "the denominator, because reading one from a "
                                             "sentence would supply a premise rather than "
                                             "narrow one (CLAUDE.md 8d, invariant 1)"),
    "n_too_large_for_sprite": ("n", "SPRITE's search is linear in n and the account's n is "
                                    "above the measured ceiling, so the call would stall "
                                    "the run rather than refuse it"),
    "n_too_large_for_grimmer": ("n", "GRIMMER searches the attainable variances and the "
                                     "account's n is above the measured ceiling "
                                     "(`checks.GRIMMER_MAX_N`), so the call would stall the "
                                     "run rather than refuse it -- the per-candidate "
                                     "try/except catches exceptions, not seconds. It was "
                                     "wired with no ceiling at all while SPRITE had two"),
    "sprite_search_too_large": ("n", "SPRITE walks the SCALE, so the cost is driven by the "
                                     "stated range and not by n alone; this variable's range "
                                     "times its n is above the measured ceiling, and the call "
                                     "would stall the run rather than refuse it (the "
                                     "per-candidate try/except catches exceptions, not "
                                     "seconds)"),
    # THE GAP THAT BECAME REACHABLE. A per-row n is still nowhere in the schema,
    # and where the PAPER ITSELF says so -- `Sample sizes vary from 44 to 48
    # across measures owing to missing responses` -- the group's n is not this
    # row's denominator and the paper has not printed one that is. Round 4
    # measured the cost of binding it anyway: an honest mean of 46 whole-point
    # scores, adjudicated at n = 48, returned GRIM, GRIMMER and SPRITE
    # `impossible`.
    "per_row_n_not_captured": ("n", "the paper says that the number of subjects behind this "
                                    "row is not the group's -- read from this value's own "
                                    "table caption, its table's footnote or the served text "
                                    "by `premises._N_VARIES`, or, under "
                                    "`--adjudicate-varying-n`, judged by a model on a "
                                    "passage this pipeline supplied. Either way the group's "
                                    "n is not this row's denominator, and a per-row n is "
                                    "nowhere in the schema, so the one that is cannot be "
                                    "recovered. The paper's own words are in the detail"),
    # PREMISES THE SCAFFOLD DOES NOT CAPTURE AT ALL. Declared so the vocabulary
    # NAMES the gap rather than leaving it as an absence; none of the three is
    # reachable in wave 7, because no candidate gets far enough to want them.
    # THE ACCOUNT'S OWN VERDICT ON ITSELF, WHICH NOTHING HERE USED TO READ.
    # `bind.assemble` runs `schema.validate_account` and writes the result to
    # `account["integrity_problems"]`; before wave 7 only the RENDERER read it,
    # so the bridge went on to adjudicate values the account had already
    # declared broken. A value naming a group the structure never declared is
    # the documented route to a false accusation -- no n at its own coordinate,
    # fall through to the study-level n, inherit the whole cohort's denominator.
    # It is the bridge's own code rather than a premise code because it is a
    # fact about the ACCOUNT, not about what the paper printed.
    "account_integrity_problem": ("binding", "the account's own referential-integrity "
                                             "record (`integrity_problems`, written by "
                                             "`schema.validate_account`) names this value: "
                                             "one of the ids it sits at does not exist, or "
                                             "its statistic is outside the vocabulary. A "
                                             "check resting on an id that names nothing "
                                             "rests on a coordinate the account cannot "
                                             "resolve"),
    "items_not_captured": ("granularity", "a composite's item count is nowhere in the "
                                          "schema (only indirectly, as a step != 1)"),
    "df_not_captured": ("literal", "a tidy table cell carries no df, so a regression p "
                                   "cannot be recomputed from it"),
    "plausible_sd_max_not_captured": ("bounds", "the schema has no plausibility ceiling "
                                                "for a variable other than its bounds"),
}


#: THE ONE CLOSED VOCABULARY, half of it owned by `premises`. Every refusal the
#: bridge emits is one of these; the two halves may not overlap, which
#: `tests/test_scaffold_premises.py` asserts.
REASONS: dict[str, tuple[str, str]] = {**_premises.REASONS, **BRIDGE_REASONS}


def reason_rank(reason: str) -> int:
    slot = REASONS.get(reason, ("n", ""))[0]
    return PREMISE_ORDER.index(slot) if slot in PREMISE_ORDER else len(PREMISE_ORDER)


# --------------------------------------------------------------------------
# The vocabularies, and the strict literal grammar -- ONE definition each
# --------------------------------------------------------------------------
#
# EVERY NAME BELOW IS AN ALIAS, NOT A COPY. Each of these was defined here AND
# somewhere else in the package, and this module's own history is the argument:
# `CORROBORATED` existed twice under `scaffold/` and `prepass.reports_model_output`
# was hand-copied into an eleventh place. `tests/test_scaffold_premises.py`
# ratchets it -- under `scaffold/`, only `premises.py` may assign one of these
# names to a literal collection.

_read_plain = _premises.read_plain
_is_plain_integer = _premises.is_plain_integer
_exact_int = _premises.exact_int
CORROBORATED = _premises.CORROBORATED
UNCORROBORATED = _premises.UNCORROBORATED
PROVENANCE_OF = _premises.PROVENANCE_OF
BOUND_SOURCE_OF = _premises.BOUND_SOURCE_OF
ASSUMED_BOUND_SOURCE = _premises.ASSUMED_BOUND_SOURCE
NECESSARY_BOUNDS = _premises.NECESSARY_BOUNDS
PERCENTAGE_KINDS = _premises.PERCENTAGE_KINDS
_DISCRETENESS = _premises.DISCRETENESS

#: The largest n `sprite_reconstruct` is handed. MEASURED (round 2's own probe,
#: 2026-09-08): one call at n = 5,000 costs 1.9 s, at n = 50,000 it costs 110 s,
#: and at n = 5,000,000 it does not return. The per-candidate try/except catches
#: exceptions, not runtime, so one mis-read denominator stalls a whole run
#: without ever raising. A named refusal above the ceiling is the honest form of
#: the same fact, and SPRITE's reconstruction is not informative at that n
#: anyway.
SPRITE_MAX_N = 5000

#: AND n IS NOT THE AXIS THE COST IS ON. The ceiling above was justified as
#: "SPRITE's search is linear in n", and it is not: the search walks the SCALE,
#: so an honest paper that states a wide integer range passes the n ceiling at
#: any n and stalls the run anyway. MEASURED at 7fe89f2, one call each
#: (mean/SD centred on the scale, `discreteness_source: stated`):
#:
#:     n = 4999, span      6 -> 1.1 s      n =  200, span      6 ->  0.03 s
#:     n = 5000, span     10 -> 4.2 s      n =   40, span    100 ->  0.90 s
#:     n =  100, span    100 -> 2.5 s      n =  300, span    100 ->  8.5 s
#:     n = 4999, span     20 -> 24.5 s     n = 1000, span     50 -> 13.7 s
#:     n =  200, span  1,000 -> 10.7 s     n =  200, span 30,000 -> 10.8 s
#:
#: Round 3's honest case is the last shape: an accelerometer study, n = 200,
#: with the paper's own stated range of 0 to 30,000 steps -- 11 s of `evaluate`
#: for ONE value, far under the n ceiling. So the guard keys on the SEARCH
#: rather than on n: a Likert-width scale is cheap at every admitted n, and
#: anything wider is bounded by `n * span`. The envelope below holds every
#: measured call at or under ~4 s.
#:
#: WIDE SCALES ALSO STOP BEING INFORMATIVE: every call above that took more than
#: 8 s came back `indeterminate`, because the search fails rather than succeeds
#: slowly. The refusal costs a verdict that was not going to be one.
SPRITE_NARROW_SPAN = 10
SPRITE_MAX_SEARCH = 10_000

#: The largest n `grimmer_check` is handed, and it exists for the reason
#: `SPRITE_MAX_N` does: the per-candidate try/except catches exceptions, not
#: seconds. MEASURED at 0850ff9, one call each (mean 5.39, SD 1.83, 2 dp,
#: `data_type: count`):
#:
#:     n =    10,000 -> 0.01 s      n =   200,000 -> 3.2 s (end to end)
#:     n =   100,000 -> 0.81 s      n = 1,000,000 -> did not return in 20 s
#:
#: GRIM is not bounded and does not need to be: the same sweep returns in 0.00 s
#: at n = 10,000,000, because its test is arithmetic rather than a search.
#: GRIMMER's is a search over the attainable variances, and the working corpus
#: contains a 315,661-patient paper -- one such cell would stall a run without
#: ever raising. The refusal costs a verdict that was not going to be one: every
#: call above 100,000 came back `consistent`, because at that n almost every
#: printed SD is attainable.
GRIMMER_MAX_N = 100_000


# --------------------------------------------------------------------------
# The premise translations -- scaffold field -> registry parameter
# --------------------------------------------------------------------------

#: `variable.kind` -> the registry's `data_type`. `ordinal` is the one
#: conditional entry: an ordinal variable is integer-valued only when the paper
#: fixes its step, so it is resolved in `_data_type` and not here.
KIND_TO_DATA_TYPE: dict[str, str] = {
    "count": "count",
    "integer_score": "integer",
    "binary": "binary",
    "continuous": "continuous", "duration": "continuous", "mass": "continuous",
    "concentration": "continuous", "temperature": "continuous", "rate": "continuous",
    "proportion": "proportion",
    "percentage_of_observations": "proportion", "percentage_of_time": "proportion",
    "percentage_of_subjects": "proportion", "percentage_of_reference": "proportion",
    "categorical": "nominal",
    "other": "unknown",
}

#: The canonical data types every granularity family is defined for.
INTEGER_DATA_TYPES = frozenset({"integer", "likert", "count"})

#: `value.statistic` -> `check_sd_or_se`'s `reported_as`.
REPORTED_AS_OF: dict[str, str] = {"sd": "SD", "sem": "SE", "se": "SE",
                                  "dispersion_unstated": "unknown"}


def _data_type(var: dict, step_is_one: bool) -> str:
    kind = str((var or {}).get("kind") or "")
    if kind == "ordinal":
        # An ordinal variable is integer-valued only where the paper's own
        # definition fixes the step; otherwise its spacing is unknown and
        # calling it `integer` would supply a premise rather than narrow one.
        return "integer" if step_is_one else "unknown"
    return KIND_TO_DATA_TYPE.get(kind, "unknown")


# --------------------------------------------------------------------------
# Candidates
# --------------------------------------------------------------------------


@dataclass(frozen=True, kw_only=True)
class Coord:
    """WHERE A VALUE SITS: study, group, phase. The only key this file indexes by.

    IT EXISTS BECAUSE THE ARITY WAS THE DEFECT. `_Index` built eight dictionaries
    over one value population, every key a hand-written tuple literal, and the
    axes of two keys written months apart drifted: `n_at` was
    `(study_id, group_id)` while `_coord_var`, ten lines away in the SAME class,
    was already reading the phase. So a two-wave study's BASELINE n became the
    denominator of every follow-up statistic of the same group -- 34 children at
    baseline, 29 re-interviewed at twelve weeks, and the follow-up mean
    adjudicated at 34 came back `impossible` (fixed at `bfc3a4b`). That is this
    project's recurring shape: two sides written at different times, one moved.

    THE ENFORCEMENT IS THE CONSTRUCTOR, AND IT IS RUNTIME, NOT STATIC. The three
    fields are keyword-only and have NO defaults, so `Coord(study_id=s,
    group_id=g)` raises `TypeError` at the construction site rather than
    silently keying at two axes. Dropping an axis is therefore something you
    have to WRITE (`phase_id=None`), which is a visible decision in a diff, not
    an omission. Python enforces none of this before the line runs -- there is
    no type checker in CI -- so what this buys is a loud immediate failure and a
    reviewable signature, not proof.

    AND THE SHORTER KEYS ARE NAMED RATHER THAN LITERAL. `phases_with_n` really
    is keyed one axis shorter than `n_at` -- it holds the phases a (study,
    group) has an n AT, so keying it by phase would be vacuous -- and
    `group_key()` says so in its name. The defect was never "some keys are
    short"; it was that nothing distinguished a short key that was meant from a
    short key that was forgotten.
    """

    study_id: Any
    group_id: Any
    phase_id: Any

    @classmethod
    def of(cls, value: dict) -> "Coord":
        """The coordinate of one VALUE record."""
        return cls.from_mapping(value.get("coordinate") or {})

    @classmethod
    def from_mapping(cls, m: dict) -> "Coord":
        """The coordinate carried by any mapping with the three axis keys -- a
        value's `coordinate`, a `Candidate.coordinate`, or a census row, all of
        which spell the axes the same way and were all keying by hand."""
        return cls(study_id=m.get("study_id"), group_id=m.get("group_id"),
                   phase_id=m.get("phase_id"))

    def key(self) -> tuple:
        """The full three-axis dict key. The ONLY way to index by coordinate."""
        return (self.study_id, self.group_id, self.phase_id)

    def group_key(self) -> tuple:
        """The (study, group) key, for the one index whose PAYLOAD is the phase."""
        return (self.study_id, self.group_id)

    def var_key(self, variable_id: Any) -> tuple:
        """This coordinate plus a variable -- what `by_coord_var` and the
        census-against-bridge reconciliation both key by, and they must agree."""
        return (self.study_id, self.group_id, self.phase_id, variable_id)

    def at_phase(self, phase_id: Any) -> "Coord":
        return Coord(study_id=self.study_id, group_id=self.group_id, phase_id=phase_id)

    def at_group(self, group_id: Any) -> "Coord":
        return Coord(study_id=self.study_id, group_id=group_id, phase_id=self.phase_id)


@dataclass(frozen=True)
class Candidate:
    """One (family, primary value) the bridge could try. Structural only."""

    family: str
    tool: str
    primary_value_id: str
    value_ids: dict[str, str]         # role -> value id
    variable_id: str | None
    coordinate: dict[str, Any]
    #: Roles where two or more values could be the partner. A role is NEVER
    #: filled by choosing between them -- the pairing is a premise, and choosing
    #: is the guess this layer exists to remove -- so it lands here instead and
    #: the translator refuses `ambiguous_pairing`.
    ambiguous_roles: tuple[str, ...] = ()

    @property
    def check_id(self) -> str:
        return f"chk:{self.family}:{self.primary_value_id}"


@dataclass
class Refusal:
    """Why a candidate did not run. Names every missing premise, and the value
    or variable id it was missing from."""

    reasons: list[dict] = field(default_factory=list)

    def add(self, reason: str, where: str | None = None, detail: str = "") -> None:
        self.reasons.append({"reason": reason, "where": where,
                             "premise": REASONS[reason][0], "detail": detail})

    def sort(self) -> None:
        self.reasons.sort(key=lambda r: reason_rank(r["reason"]))

    def __bool__(self) -> bool:
        return bool(self.reasons)

    @property
    def reason(self) -> str:
        return self.reasons[0]["reason"] if self.reasons else ""


class _Index:
    """Every lookup the translators make, computed once.

    THE ACCOUNT IT INDEXES IS ALREADY STAMPED. `evaluate` runs
    `premises.stamp` first, so every value here carries `premise` and every n
    row carries `n_premise`; this class reads them and derives nothing of its
    own about a value's admissibility. That is the wave-7b rule in one sentence:
    the bridge adds no premise judgement after the stamp.
    """

    def __init__(self, account: dict, text: str = ""):
        # EVERY VALUE THIS INDEX HOLDS IS STAMPED, whoever called. `evaluate`
        # stamps first, so this is a no-op on the live path; it exists because
        # `candidates` and `translate` are exported, and a premise reader handed
        # an unstamped value would read `None` and admit it -- a fail-open of
        # exactly the kind the stamp exists to remove. Stamping returns a COPY,
        # so nothing is written back into the caller's account either way.
        account = _premises.stamped(account, text)
        self.account = account
        self.text = text or ""
        raw = list(account.get("values") or [])
        #: A value that cannot be read AS a value is one skip, never the run.
        #: `location` arriving as the string `"table_cell"`, and a value with no
        #: `id`, each took the whole sidecar with them, because the index and
        #: the census are built OUTSIDE the per-candidate try/except.
        self.malformed: list[dict] = []
        self.values: list[dict] = []
        for i, v in enumerate(raw):
            why = _premises.well_formed(v)
            if why is None:
                self.values.append(v)
            else:
                self.malformed.append({"index": i, "why": why,
                                       "id": (v.get("id") if isinstance(v, dict) else None)})
        self.by_id = {v["id"]: v for v in self.values}
        #: The ids more than one value carries. `by_id` above is last-write-wins,
        #: so an id two values share names ONE of them and every candidate formed
        #: from the other is translated from the wrong record. Refused by name
        #: rather than resolved: choosing which value an id means is exactly the
        #: guess this layer exists to remove.
        self.duplicate_ids = _premises.duplicate_ids(self.values)
        #: THE ACCOUNT'S OWN VERDICT ON ITSELF, READ AT LAST. `bind.assemble`
        #: writes `schema.validate_account`'s problems to
        #: `account["integrity_problems"]` and nothing between there and the
        #: renderer read them, so the bridge adjudicated values the account had
        #: already declared unbindable. Only the ids the problems NAME are
        #: withdrawn -- a dangling group on one value says nothing about the
        #: rest of the paper -- and an absent or empty list, which is the
        #: ordinary case, makes this a no-op. It can only ever REMOVE a check.
        self.integrity_problems: dict[str, list[str]] = defaultdict(list)
        for problem in account.get("integrity_problems") or []:
            for vid in _schema.values_with_problems([problem]):
                self.integrity_problems[vid].append(str(problem))
        #: THE VARIABLE TABLE, HELD TO THE RULE THE VALUE TABLE IS HELD TO. It
        #: was `{v["id"]: v for ...}` -- last-write-wins over a field that may
        #: arrive as a list or a dict -- so a variable id that is not a scalar
        #: raised `TypeError: unhashable type` out of the index (before the
        #: per-candidate try/except: no sidecar at all), and two variables
        #: sharing one id silently adjudicated a value against the OTHER one's
        #: kind, bounds and granularity. Both are `premises`' judgement now, and
        #: a duplicated id is refused BY NAME rather than resolved.
        readable = _premises.readable_variables(account)
        self.malformed_variables: list[dict] = [
            {"index": i, "why": _premises.well_formed_variable(v),
             "id": (v.get("id") if isinstance(v, dict) else None)}
            for i, v in enumerate(account.get("variables") or [])
            if _premises.well_formed_variable(v) is not None]
        self.duplicate_variable_ids = _premises.duplicate_ids(readable)
        self.variables = _premises.variables_by_id(readable)
        # THE SAME TOLERANCE THE VALUES GET. A study or a group that is not an
        # object is a malformed account, and reading one used to raise out of
        # the index -- which is built before the per-candidate try/except and so
        # took the whole sidecar with it. A coordinate whose group cannot be
        # read simply has no declared n, which is a refusal and not a crash.
        self.groups: dict[tuple, dict] = {}
        self.groups_of_study: dict[Any, list[dict]] = defaultdict(list)
        for st in account.get("studies") or []:
            # A study or a group id that is not a scalar cannot be part of an
            # index key, and building one raised `TypeError: unhashable type`
            # out of the index -- which is built BEFORE the per-candidate
            # try/except, so it took the whole sidecar with it. The same rule
            # the values are held to (`premises.well_formed`), applied to the
            # structure: a group we cannot key is a group with no declared n,
            # which is a refusal and not a crash.
            if not isinstance(st, dict) or not _premises.is_scalar(st.get("id")):
                continue
            for g in st.get("groups") or []:
                if not isinstance(g, dict) or not _premises.is_scalar(g.get("id")):
                    continue
                self.groups[(st.get("id"), g.get("id"))] = g
                self.groups_of_study[st.get("id")].append(g)
        #: Every id a declared variable gives one of its LEVELS. A count bound to
        #: one of these is, in the structure's own vocabulary, the size of a
        #: subset picked out by a PROPERTY -- which is the fact `group_n`'s last
        #: gate needs and which a bare `variable_id` does not carry.
        #:
        #: AN id THAT IS NOT THERE IS NOT AN id. A declared level with no `id`
        #: would put `None` in this set, and a value with no `level_id` would
        #: then test as BOUND -- licensing the very demotion the gate exists to
        #: question, on the least identified row in the table.
        self.level_ids: frozenset = frozenset(
            lv.get("id") for var in self.variables.values()
            for lv in (var.get("levels") or [])
            if isinstance(lv, dict) and _premises.is_scalar(lv.get("id")) and lv.get("id"))
        self.by_cell: dict[tuple, list[dict]] = defaultdict(list)
        self.by_coord_var: dict[tuple, list[dict]] = defaultdict(list)
        self.n_at: dict[tuple, list[dict]] = defaultdict(list)
        #: THE COUNTS THAT ARE NOT CANDIDATE DENOMINATORS, kept because each one
        #: might have been. A cell printed `38 (59%)` types `count` -- by the
        #: reconstruction prompt's own instruction, and failing that by
        #: `reconstruct._retype` -- so it never reaches `n_at`. The integer is a
        #: population size all the same: 38 coalitions ran a programme, and 28 of
        #: 30 participants were analysed. See `group_n`'s last gate.
        self.shares_at: dict[tuple, list[dict]] = defaultdict(list)
        #: The phases at which this (study, group) has an n OF ITS OWN. A
        #: phase-less n stands for a group whose n the paper states once; it may
        #: not stand for one wave of a group whose n the paper states PER WAVE --
        #: see `group_n`.
        self.phases_with_n: dict[tuple, set] = defaultdict(set)
        for v in self.values:
            loc = v.get("location") or {}
            coord = Coord.of(v)
            if loc.get("kind") == "table_cell":
                self.by_cell[(loc.get("table_id"), loc.get("row"), loc.get("col"))].append(v)
            else:
                self.by_coord_var[self._coord_var(v)].append(v)
            if v.get("statistic") == "count" and _reconstruct.is_count_of_a_share(
                    v.get("quote"), v.get("printed")):
                self.shares_at[coord.group_key()].append(v)
            if v.get("statistic") == "n" and coord.phase_id is not None:
                self.phases_with_n[coord.group_key()].add(coord.phase_id)
            if v.get("statistic") == "n":
                # THE PHASE IS PART OF THE COORDINATE EVERYWHERE ELSE IN THIS
                # FILE (`_coord_var`, `_census_vs_bridge`) AND WAS NOT PART OF
                # THIS KEY. So a two-wave study's baseline n was the denominator
                # of every follow-up statistic of the same group: 34 children at
                # baseline, 29 re-interviewed at twelve weeks with the paper
                # saying so in the sentence the follow-up mean sits in, and the
                # follow-up mean adjudicated at 34 came back `impossible`.
                #
                # THE KEY IS NOW A `Coord`, which cannot be built without saying
                # what its phase is: the omission above is no longer something
                # you can write by leaving an axis out of a tuple literal.
                self.n_at[coord.key()].append(v)
        #: The largest number of subjects THIS PAPER prints, and the ceiling on
        #: what may count as an ALTERNATIVE percentage base
        #: (`premises.other_bases_that_fit`). An integer above it is arithmetic
        #: rather than a denominator this paper could have used, and admitting
        #: one excused a hundredfold error: `26 (0.867%)` in a paper of thirty
        #: people, "explained" by the denominators 2,996 to 3,000.
        #:
        #: IT USED TO BE THE ACCOUNT'S CEILING, NOT THE PAPER'S -- the largest
        #: value held as a `statistic: n` under the STRICT literal grammar. A
        #: paper that spells its total out (`Thirty-four children were sampled`)
        #: or groups it by thousands (`1,204 patients`) put its own denominator
        #: ABOVE its own ceiling, so the guard stopped naming the base on exactly
        #: the papers whose base is hardest to see, and a by-school table whose
        #: caption states `% of all children surveyed` was called `suspicious`.
        #: Both forms are read now: the account's n values through
        #: `premises.printed_integer`, and the served text through
        #: `premises.printed_subject_counts`. A ceiling can only ever NAME more
        #: alternatives, and naming one only ever REFUSES a check.
        #:
        #: WAVE 7D: THE SERVED TEXT IS NOT THE ONLY PLACE A PAPER PRINTS ITS
        #: ELIGIBLE COHORT OR ITS FULL ROLL -- a flow table's own footnote or
        #: caption is exactly where a clinical paper's "of the 1,240 eligible
        #: patients" sentence sits, and it is not always echoed in prose. Table
        #: furniture is now scanned too (`premises.document_furniture_text`),
        #: which is regex-only and document-wide like `printed_subject_counts`
        #: itself -- a looser ceiling still only ever NAMES more alternatives.
        self.max_printed_n = _premises.paper_max_n(
            self.values, self.text + " " + _premises.document_furniture_text(self.account))
        #: THE FOURTH DOCUMENT-LEVEL STATEMENT: HOW MANY UNITS WERE ANALYSED.
        #: Read once per paper, exactly as `max_printed_n` is, because both are
        #: properties of the PAPER and a per-value reader would let two rows of
        #: one table disagree about what the paper says. `analysed_counts` is
        #: what the text says reached a STAGE (`Twenty-four nurses attended the
        #: twelve-week visit`); `analysis_units` is what it says the design
        #: YIELDS when the unit is not a person (`giving 84 nurse-nights`).
        #: Neither supplies a denominator -- both only ever withdraw one.
        self.analysed_counts = _premises.analysed_counts(self.text)
        self.analysis_units = _premises.analysis_unit_statement(self.text)
        self._haystack: "_premises.Haystack | None" = None

    @property
    def haystack(self) -> "_premises.Haystack":
        """One paper, prepared once. Only the fallback path uses it -- an
        unstamped account handed straight to `translate` -- because `evaluate`
        stamps first and every verification is then a lookup."""
        if self._haystack is None:
            self._haystack = _premises.Haystack(self.text)
        return self._haystack

    @staticmethod
    def _coord_var(v: dict) -> tuple:
        return Coord.of(v).var_key(v.get("variable_id"))

    def partners(self, v: dict) -> list[dict]:
        """The other values printed in the same place as `v` -- the same table
        cell, or the same (study, group, phase, variable) for prose."""
        loc = v.get("location") or {}
        if loc.get("kind") == "table_cell":
            pool = self.by_cell[(loc.get("table_id"), loc.get("row"), loc.get("col"))]
        else:
            pool = self.by_coord_var[self._coord_var(v)]
        return [w for w in pool if w["id"] != v["id"]]

    #: A LOOKUP, NOT A SECOND OPINION. The corroboration judgement -- what,
    #: besides one row, says this integer is the number of SUBJECTS -- is
    #: `premises.n_corroboration`, and this name exists so the call site reads
    #: the same as it did before the judgement moved.
    _corroboration = staticmethod(_premises.n_corroboration)

    def group_n(self, v: dict) -> tuple[int | None, str | None, dict]:
        """`(n, refusal reason, premise record)` for the value `v`.

        RESOLVED BY KEY AND NEVER BY PROXIMITY: the n rows at EXACTLY this
        value's (study, group), and -- only when the group has none of its own --
        a study-level n that the sentence says applies to every group. Every
        such row must be a plain integer and they must all say the same thing;
        anything else is `ambiguous_n`, because choosing between two printed
        denominators is exactly the guess this layer exists to remove.

        EVERY GATE HERE IS A LOOKUP OF `value.n_premise`, which `premises`
        computed: provenance (a denominator read off a FIGURE reached an exact
        GRIM call stamped `printed_table`), binding (an n row the name join
        CONTRADICTS supplied every denominator in a run), `statistic_disputed`
        (the one input the disputed-kind gate never covered), and POSITIVITY (a
        printed `-30` reached SPRITE and came back `suspicious`).

        AND A STUDY-LEVEL n IS NOT AN ARM'S n WHERE THERE ARE ARMS. `n = 30` for
        a study with an intervention and a control arm says nothing about how
        the 30 divide, and applying it to each arm in turn is a guess with two
        chances to accuse.
        """
        at = Coord.of(v)
        sid, gid, pid = at.study_id, at.group_id, at.phase_id
        rows = list(self.n_at.get(at.key()) or [])
        source = "printed"
        from_study = False
        from_phaseless = False
        # A PHASE-LESS n IS THE GROUP'S ONE n, OR IT IS NOBODY'S WAVE. Where the
        # value sits at a named phase and no n does, the only n available is one
        # the reading never bound to a wave. That is the ordinary honest shape --
        # a single-arm trial states `n = 48` once and reports the outcome at
        # baseline and week 12 -- so it is admitted. It is NOT admitted where the
        # paper states an n PER WAVE and this wave is not one of them: there the
        # account's own rows say the denominator varies by phase, and taking the
        # unbound one is the same guess `study_n_over_several_arms` refuses
        # across arms.
        #
        # AND THE GUARD IS TWO-SIDED, WHICH IT WAS NOT. It fired only for a value
        # AT a phase, so a value bound to NO phase inherited the phase-less
        # enrolled n even where the account's own rows state an n per wave --
        # which is the ordinary shape of a prose results sentence, because the
        # TABLE rows carry phases (the table has a wave column) and the sentence
        # in Results does not. Measured on one run: the follow-up mean `7.08`
        # (= 170/24 exactly, at no phase) came back GRIM, GRIMMER and SPRITE
        # `impossible` at the enrolled 28, while the wave-1 mean BESIDE IT --
        # honest at 28 -- was correctly refused by the one-sided guard. The
        # guard was protecting the right value and letting the wrong one
        # through: the less the reading recorded, the more the bridge accused.
        # WHOSE n ROWS THIS VALUE WOULD ACTUALLY DRAW ON. Both wave guards were
        # keyed on the GROUP, and a single-arm paper states its enrolled n ONCE,
        # as a sentence about the STUDY (`Twenty-eight patients were enrolled
        # (n = 28)`) -- which the reading records with no group and
        # `applies_to_all_groups`, filed under `(study, None)` and invisible to
        # `phases_with_n[(study, group)]`. So the SAME paper with the SAME
        # sentences was protected when the n sat on the group and accused when it
        # sat on the study, and the study-level form is the one a single-arm
        # paper produces. The guard asks the question of whichever rows would be
        # used: the group's where the group has any, the study's otherwise.
        #
        # AND ITS KEY IS GENUINELY ONE AXIS SHORTER, WHICH IS WHY IT SAYS SO.
        # `phases_with_n` holds the phases a (study, group) has an n AT -- the
        # phase is the PAYLOAD -- so keying it by phase would be vacuous. The
        # two arities in the line below are `n_at` (three axes) and
        # `phases_with_n` (two), and both are now named by the method rather
        # than written as a tuple literal, so the short one reads as a decision
        # instead of as a dropped axis.
        owner = (at.group_key() if (self.n_at.get(at.key())
                                    or self.n_at.get(at.at_phase(None).key())
                                    or self.phases_with_n.get(at.group_key()))
                 else at.at_group(None).group_key())
        per_wave = self.phases_with_n.get(owner) or set()
        if per_wave and (pid is None or not rows):
            rec_p = {"source": "printed", "study_id": sid, "group_id": gid,
                     "phase_id": pid, "value_ids": [], "printed": [],
                     "value_carries_no_phase": pid is None,
                     "phases_with_their_own_n": sorted(str(p) for p in per_wave)}
            return None, "phase_n_over_several_phases", rec_p
        if not rows and pid is not None:
            rows = list(self.n_at.get(at.at_phase(None).key()) or [])
        if not rows and gid is not None:
            pool = list(self.n_at.get(at.at_group(None).key()) or [])
            if pid is not None:
                pool += list(self.n_at.get(at.at_group(None).at_phase(None).key()) or [])
            rows = [r for r in pool if r.get("applies_to_all_groups")]
            source, from_study = "study_applies_to_all_groups", True
        elif gid is None:
            rows = [r for r in rows if r.get("applies_to_all_groups")]
            source = "study_applies_to_all_groups"
        # A PROPERTY OF THE ROWS, NOT OF THE BRANCH THAT FOUND THEM. The
        # retention join below runs where the value sits at a named wave and the
        # only n available carries none -- and it was gated on the GROUP's
        # phase-less fallback having fired, so the same fact arriving through the
        # STUDY-level branch (which sets `from_study`) reached the join gate as
        # False and the guard withdrew nothing. Identical paper, identical
        # sentences: refused with the n at the group, GRIM `impossible` with it
        # at the study.
        from_phaseless = bool(rows) and pid is not None and all(
            ((r.get("coordinate") or {}).get("phase_id")) is None for r in rows)
        rec: dict[str, Any] = {"source": source, "study_id": sid, "group_id": gid,
                               "phase_id": pid,
                               "n_row_carries_no_phase": from_phaseless,
                               "value_ids": [r.get("id") for r in rows],
                               "printed": sorted({str(r.get("printed")) for r in rows})}
        if not rows:
            return None, "no_group_n", rec
        # AND A DENOMINATOR'S OWN ROW HAS TO NAME ONE VALUE TOO. The n rows come
        # from `n_at` rather than from `by_id`, so a duplicated id does not
        # silently substitute one for the other here -- but the row a reader is
        # sent to look at would be one of two, which is the same defect one step
        # further down.
        dup = sorted({str(r.get("id")) for r in rows if r.get("id") in self.duplicate_ids})
        if dup:
            rec["duplicate_value_ids"] = dup
            return None, "duplicate_value_id", rec
        if from_study:
            arms = self.groups_of_study.get(sid) or []
            declared_ids = {g.get("id") for g in arms}
            # THE GUARD COUNTED DECLARED GROUPS, AND AN UNDECLARED ONE IS A
            # GROUP TOO. A value whose coordinate names a group the structure
            # never declared fell through to the study-level n and the guard saw
            # ONE arm, so it did not fire: round 3's completers (32 of the 40
            # enrolled) inherited the whole cohort's 40 and produced
            # `check_count_percent` `suspicious` and GRIM `impossible` on an
            # honest paper. A study-level figure is an arm's n only where that
            # arm is the study's ONLY arm -- which cannot be shown for a group
            # the study does not list at all.
            if len(arms) > 1 or (gid is not None and gid not in declared_ids):
                rec["groups_in_study"] = sorted(str(g.get("id")) for g in arms)
                rec["group_is_declared"] = gid in declared_ids
                return None, "study_n_over_several_arms", rec
        # `n_premise.usable` IS THE GATE, and the branch below only says WHICH
        # of its parts failed, for the docket. Asking the four questions again
        # here would be a second derivation of one fact -- the defect this whole
        # wave removes -- and the two could then disagree.
        kept, dropped = [], []
        for r in rows:
            np = r.get("n_premise") or {}
            if np.get("usable"):
                kept.append(r)
                continue
            vid = r.get("id")
            if np.get("provenance") is None:
                dropped.append({"value_id": vid, "why": "provenance"})
            elif np.get("binding") in ("contradicted", "unchecked"):
                dropped.append({"value_id": vid, "why": "binding",
                                "id_check": r.get("id_check")})
            elif np.get("disputed"):
                dropped.append({"value_id": vid, "why": "statistic_disputed"})
            elif np.get("integer") is None:
                dropped.append({"value_id": vid, "why": "not_an_integer",
                                "printed": r.get("printed")})
            else:
                dropped.append({"value_id": vid, "why": "not_positive",
                                "printed": r.get("printed")})
        if dropped:
            rec["rows_not_used"] = dropped
        # AN UNREADABLE n ROW IS NOT A ROW TO DROP, IT IS AN AMBIGUITY. Every
        # other failed premise removes one row and leaves the rest usable; a row
        # whose literal cannot be read is different, because what it says is
        # unknown rather than unusable. `30` beside `30.5` is two denominators
        # and choosing the readable one is the guess this layer exists to
        # remove -- so the coordinate is ambiguous, which is what it was before
        # the drop loop existed.
        if any(d["why"] == "not_an_integer" for d in dropped):
            return None, "ambiguous_n", rec
        if not kept:
            rec["value_ids"] = []
            why = {d["why"] for d in dropped}
            return None, ("n_not_printed" if "provenance" in why else
                          "n_not_positive" if "not_positive" in why else
                          "n_binding_not_corroborated"), rec
        rows = kept
        rec["value_ids"] = [r.get("id") for r in rows]
        rec["printed"] = sorted({str(r.get("printed")) for r in rows})
        ints = {(r.get("n_premise") or {}).get("integer") for r in rows}
        if None in ints or len(ints) != 1:
            return None, "ambiguous_n", rec
        n = ints.pop()
        rec["n"] = n
        g = self.groups.get((sid, gid)) or {}
        declared = g.get("n")
        if declared is not None:
            rec["declared_group_n"] = declared
            rec["declared_group_n_source"] = g.get("n_source")
            # COMPARED EXACTLY, NEVER TRUNCATED. `int(declared) != int(n)` let a
            # declared 30.4 agree with a printed 30, and raised `ValueError` on
            # a hand-edited `"thirty"` -- taking the whole run's `checks.json`
            # with it. A declared n that is not an exact integer cannot be shown
            # to agree with anything, so it refuses.
            exact = _exact_int(declared)
            if exact is None:
                return None, "declared_n_not_comparable", rec
            if exact != n:
                return None, "n_disagrees_with_structure", rec
        # THE VALUE'S OWN SENTENCE MAY STATE ITS OWN DENOMINATOR, AND THE UNIT
        # IS NEVER OTHERWISE ASKED. `group_n` resolves an n by KEY and asks four
        # corroboration questions, none of which is "does this n count the same
        # THING". A cluster trial prints both numbers honestly -- `six clinics
        # (n = 6)` for the arm, and `The 240 patients of the intervention
        # clinics attended a mean of 3.4 visits` for the statistic -- and 3.4 at
        # n = 6 is GRIM `impossible` on a `count` whose discreteness the kind
        # makes necessary.
        #
        # THE POPULATION THE SENTENCE STATES IS READ IN BOTH DIRECTIONS NOW, and
        # the reason it was read in one is that the two errors look different
        # from here. A population LARGER than the n bound cannot be a subgroup of
        # it, so the two cannot both be this statistic's denominator. A SMALLER
        # one was left alone because "a smaller integer in the same sentence may
        # be anything a paper counts -- items, weeks, sites".
        #
        # IT MAY BE, AND THE COMMONEST THING IT IS IS A SUBGROUP -- which is
        # exactly the direction that manufactures a granularity failure, because
        # the true denominator is always smaller than the group's. `The 21
        # children who ate a school lunch had a mean score of 11.90` is an
        # ordinary results sentence, its 21 scores are real, and the mean
        # adjudicated at the group's 34 is `impossible`.
        #
        # THE SUBGROUP'S OWN SIZE IS NOT TAKEN AS THE DENOMINATOR. Reading one
        # out of a sentence would SUPPLY a premise, and a derived boundary may
        # only narrow one (CLAUDE.md 8d, invariant 1); a wrong pick here is a
        # false accusation rather than a lost check. So both directions refuse,
        # under their own reason, and the sentence is in the docket.
        stated = [k for k in (_premise_of(v).get("denominator_stated_in_quote") or [])
                  if isinstance(k, int)]
        larger = [k for k in stated if k > n]
        smaller = [k for k in stated if k < n]
        if larger:
            rec["denominator_stated_in_quote"] = larger
            return None, "denominator_contradicted_by_the_sentence", rec
        if smaller:
            rec["denominator_stated_in_quote"] = smaller
            return None, "subgroup_stated_in_the_sentence", rec
        # AND THE PAPER MAY SAY THAT THIS ROW'S n IS NOT THE GROUP'S. Item-level
        # missingness is the commonest honest reason a real paper fails GRIM, and
        # papers announce it -- `Sample sizes vary from 44 to 48 across measures`
        # in the table's own footnote, or the same sentence in Methods. The
        # stamp is `premises.varying_n_statement`, read from the value's own
        # caption and from the served text; where the paper states the variation
        # it does not state the number, so no denominator survives and the
        # gap `per_row_n_not_captured` already named becomes reachable.
        varies = _premise_of(v).get("analysis_n_varies")
        if varies:
            rec["analysis_n_varies"] = varies
            return None, "per_row_n_not_captured", rec
        # AND THE PAPER MAY STATE, IN A SENTENCE OF ITS OWN, HOW MANY UNITS IT
        # ANALYSED HERE -- the fourth document-level statement, and the one the
        # stamp had no reader for. Two shapes, both read once per paper by
        # `premises` and both able only to WITHDRAW the n:
        #
        #   * a RETENTION count, where this value sits at a named phase, the only
        #     n available carries none, and the retention sentence names THE SAME
        #     STAGE as the value's own (`Twenty-four nurses attended the
        #     twelve-week visit` beside `At the twelve-week visit the mean index
        #     score was 7.08`, with no `n = 24` for the reading to key on).
        #     TWICE SCOPED, and both scopes are load-bearing: without the phase
        #     path it would fire on tables, and without the STAGE JOIN it would
        #     withdraw the baseline mean of every study that reports dropout --
        #     the honest case, where the enrolled n IS that wave's denominator.
        #   * an ANALYSIS-UNIT yield, where the paper's own unit is not a person
        #     (`giving 84 nurse-nights of actigraphy`). That one governs every
        #     coordinate, because the account carries no per-value unit of
        #     analysis to narrow it with.
        if from_phaseless:
            here = set(_premise_of(v).get("stages_named_in_quote") or [])
            elsewhere = [s for s in self.analysed_counts
                         if s.get("n") != n and here & set(s.get("stages") or [])]
            if elsewhere:
                rec["stages_named_in_quote"] = sorted(here)
                rec["analysed_counts_stated"] = elsewhere[:3]
                return None, "analysed_n_stated_for_another_stage", rec
        if self.analysis_units and self.analysis_units.get("n") != n:
            rec["analysis_unit_statement"] = self.analysis_units
            return None, "analysis_unit_is_not_the_subject_count", rec
        corroborated = self._corroboration(rows, n, g)
        rec["corroborated_by"] = corroborated
        if not corroborated:
            # THE VOCABULARY'S OWN WORD FOR WHAT THIS MIGHT BE. A lone integer
            # nothing else in the paper agrees with may be a count of EVENTS
            # rather than of subjects, and `source` says so rather than leaving
            # the reader to infer it from the refusal alone.
            rec["source"] = "event_count_row"
            return None, "n_not_corroborated", rec
        # AND THE LAST GATE: WAS THIS n THE ONLY CANDIDATE, OR THE LAST ONE
        # STANDING? A cell printed `38 (59%)` is typed `count` and so is not a
        # candidate denominator at all -- by the reconstruction prompt's own
        # instruction, and failing that by `reconstruct._retype`. That typing is
        # right about the CELL and says nothing about the STUDY: 38 is the number
        # of coalitions running a programme AND it is the size of a population.
        # Where such a row is the group's size at a later stage -- `Analysed
        # (n, %) | 28 (93.3%)` beside `Enrolled | 30` -- the integer removed from
        # the pool is the very denominator every statistic here was computed on,
        # and what remains is unanimous and stale. Measured on the demonstrating
        # fixture: GRIM and SPRITE `impossible` on a mean attainable from 28.
        #
        # A RETENTION ROW AND A CATEGORY ROW ARE THE SAME ARITHMETIC. Both print
        # an integer beside a percentage that reproduces against a base standing
        # at the same coordinate, and the implied base -- count / percentage --
        # is the resolved n in both. Nothing in the cell separates them. What
        # separates them is a RELATION the account does not carry: 28 of 30 is
        # the same subjects at a later stage, 38 of 64 is a partition by a
        # property.
        #
        # SO THE GATE ASKS THE STRUCTURE, WHICH IS WHERE PROPERTIES LIVE. A count
        # bound to a declared variable or to one of its levels IS a category
        # count in the account's own vocabulary. Where at least one share at this
        # coordinate is bound, the shares here are a characteristics block and
        # the n they are shares OF is this coordinate's; where none is, the
        # account cannot say what any of these integers counts, and one of them
        # may be the population itself.
        #
        # IT ONLY EVER WITHDRAWS, and it cannot supply or raise anything. What it
        # costs is a coordinate whose share-shaped counts the structure failed to
        # bind -- an account too weak to say what its own table holds, which is
        # not an account that should be accusing anyone.
        #
        # WHAT IT DOES NOT CLOSE, and the residue is the commoner shape: a flow
        # table that ALSO carries a bound category row is licensed by that row
        # and still resolves the stale n. The premise that would close it is a
        # STAGE on the flow rows, where `phase_n_over_several_phases` and
        # `analysed_n_stated_for_another_stage` -- both of which exist -- already
        # refuse. Pinned in `tests/test_count_under_percentage.py`.
        shares = self.shares_at.get(at.group_key()) or []
        if shares:
            bound = [w.get("id") for w in shares
                     if w.get("level_id") in self.level_ids
                     or w.get("variable_id") in self.variables]
            rec["counts_printed_as_shares_here"] = [
                {"value_id": w.get("id"), "printed": w.get("printed"),
                 # WHO TOOK THIS ROW OUT OF THE POOL. `statistic_as_read` is
                 # written only where `reconstruct._retype` overruled the model,
                 # so a true here says the demotion was ours and a false says the
                 # model typed the cell `count` itself. The channel runs through
                 # both, and a reader of the record should not have to guess
                 # which one they are looking at.
                 "read_as_an_n_and_retyped": w.get("statistic_as_read") == "n"}
                for w in shares[:12]]
            rec["counts_bound_to_a_declared_category"] = bound[:12]
            if not bound:
                return None, "count_at_this_coordinate_may_be_its_n", rec
        return n, None, rec


def _n_detail(n_rec: dict) -> str:
    """What a reader is told when the denominator refuses.

    NAMES THE ROWS THAT WERE NOT USED, not just the numbers that were printed.
    `n rows ['30']` beside `n_not_printed` reads as a contradiction -- a 30 IS
    printed -- and the fact that matters is WHICH row was dropped and under
    which gate, because that is the row a person has to go and look at.
    """
    out = f"n rows {n_rec.get('printed')}"
    # WHICH ARMS THE STUDY-LEVEL n WOULD HAVE BEEN SPREAD OVER. Named, because
    # "the study n is not this arm's n" is a sentence a reader can only act on
    # if they know which arms the study declares.
    arms = n_rec.get("groups_in_study") or []
    if arms:
        out += "; the study declares " + ", ".join(str(a) for a in arms)
        if n_rec.get("group_is_declared") is False:
            out += f", and not {n_rec.get('group_id')}"
    # WHICH WAVES THE PAPER GIVES AN n OF ITS OWN. Named for the same reason the
    # arms are: "the group's n is not this wave's" is a sentence a reader can act
    # on only if they know which waves the paper does state one for.
    waves = n_rec.get("phases_with_their_own_n") or []
    if waves:
        out += ("; the paper states an n at " + ", ".join(str(w) for w in waves)
                + (" and this value names no phase at all"
                   if n_rec.get("value_carries_no_phase")
                   else f" and not at {n_rec.get('phase_id')}"))
    dup = n_rec.get("duplicate_value_ids") or []
    if dup:
        out += ("; more than one value carries the id "
                + ", ".join(str(d) for d in dup))
    # THE RIVALS THAT WERE NEVER CANDIDATES. A coordinate whose denominator is
    # unanimous only because every competing integer was typed `count` reads,
    # from here, exactly like one that printed a single n and nothing else. This
    # is the refusal's sentence; the same fact rides on the RECORD, where it is
    # carried by checks that RUN as well -- which is the case it matters in,
    # because there the verdict is not withheld.
    shares = n_rec.get("counts_printed_as_shares_here") or []
    if shares:
        ours = [s for s in shares if s.get("read_as_an_n_and_retyped")]
        out += ("; " + ", ".join(str(s.get("printed")) for s in shares)
                + " are printed here as shares of a base and so are not "
                  "candidate denominators"
                + (f" ({len(ours)} of them read as an n and retyped)" if ours else "")
                + ("; none is bound to a declared variable or level"
                   if not (n_rec.get("counts_bound_to_a_declared_category") or [])
                   else ""))
    stated = n_rec.get("denominator_stated_in_quote") or []
    if stated:
        out += ("; the value's own sentence reports over "
                + ", ".join(str(k) for k in stated))
    varies = n_rec.get("analysis_n_varies")
    if varies:
        out += f"; the paper states {str(varies)[:120]!r}"
    # THE PAPER'S OWN WORDS BEHIND THE TWO NEW REFUSALS, for the reason round 5
    # gave for putting them behind the others: a docket that names the code and
    # not the sentence reads as an assertion about nothing in particular, and a
    # reader cannot go and check it.
    for row in n_rec.get("analysed_counts_stated") or []:
        out += (f"; the paper states {str(row.get('quote'))[:120]!r}, and this "
                f"value's own sentence is about "
                + ", ".join(n_rec.get("stages_named_in_quote") or ["no stage"]))
    unit = n_rec.get("analysis_unit_statement")
    if unit:
        out += (f"; the paper states {str(unit.get('quote'))[:120]!r}, so its "
                f"analysis unit is {unit.get('n')} {unit.get('unit')}")
    dropped = n_rec.get("rows_not_used") or []
    if dropped:
        out += "; not used: " + ", ".join(
            f"{d['value_id']} ({d['why']}"
            + (f" `{d['id_check']}`" if d.get("id_check") else "") + ")"
            for d in dropped)
    return out


def _fill(ids: dict[str, str], ambiguous: list[str], role: str,
          pool: list[dict], statistic: str) -> None:
    """Bind `role` to the one value of `statistic` printed in the same place, or
    record the role as ambiguous. Never chooses between two."""
    hits = [w for w in pool if w.get("statistic") == statistic]
    if len(hits) == 1:
        ids[role] = hits[0]["id"]
    elif len(hits) > 1:
        ambiguous.append(role)


def candidates(account: dict, text: str = "", families: tuple[str, ...] | None = None
               ) -> tuple[list[Candidate], _Index]:
    """One Candidate per (family, primary value). Structural, not eligible.

    The PRIMARY VALUE is the one the tool's verdict is about: the percentage for
    `check_count_percent`, the mean for GRIM/GRIMMER/SPRITE, the dispersion for
    `check_sd_or_se`. The unit deliberately differs from the census's, which
    counts COORDINATES -- one coordinate can hold several count/percent pairs,
    and one dispersion can sit at a coordinate whose mean belongs to another
    column.
    """
    idx = _Index(account, text)
    # `None` MEANS EVERY FAMILY; AN EMPTY SELECTION MEANS NONE. `families or
    # FAMILY_NAMES` read an empty tuple as "all of them", so a caller who asked
    # for nothing -- or, after `evaluate` drops the names this bridge does not
    # define, for nothing that exists -- got the whole run instead.
    want = set(FAMILY_NAMES if families is None else families)
    out: list[Candidate] = []
    for v in idx.values:
        stat = v.get("statistic")
        vid = v.get("variable_id")
        coord = dict(v.get("coordinate") or {})
        if stat == "percentage" and "count_percent" in want:
            ids, amb = {"percentage": v["id"]}, []
            _fill(ids, amb, "count", idx.partners(v), "count")
            out.append(Candidate("count_percent", TOOL_OF["count_percent"], v["id"],
                                 ids, vid, coord, tuple(amb)))
        if stat == "mean":
            if "grim" in want:
                out.append(Candidate("grim", TOOL_OF["grim"], v["id"],
                                     {"mean": v["id"]}, vid, coord))
            for fam in ("grimmer", "sprite"):
                if fam not in want:
                    continue
                ids, amb = {"mean": v["id"]}, []
                _fill(ids, amb, "sd", idx.partners(v), "sd")
                out.append(Candidate(fam, TOOL_OF[fam], v["id"], ids, vid, coord, tuple(amb)))
        if stat in ("sd", "se", "sem", "dispersion_unstated") and "sd_or_se" in want:
            ids, amb = {"dispersion": v["id"]}, []
            _fill(ids, amb, "mean", idx.partners(v), "mean")
            _fill(ids, amb, "coefficient", idx.partners(v), "coefficient")
            out.append(Candidate("sd_or_se", TOOL_OF["sd_or_se"], v["id"], ids, vid, coord,
                                 tuple(amb)))
    out.sort(key=lambda c: (c.family, c.primary_value_id))
    return out, idx


# --------------------------------------------------------------------------
# Shared premise checks
# --------------------------------------------------------------------------


def _premise_of(v: dict) -> dict:
    """The stamp `premises.stamp` wrote on this value.

    NEVER RE-DERIVED. `evaluate` stamps the account before the first candidate
    is formed, so an absent stamp here is a programming error rather than a
    value to be judged some other way -- and judging it some other way is
    exactly the defect wave 7b exists to remove.
    """
    return v.get("premise") or {}


def _reasons_from_premise(v: dict, ref: Refusal, *, wanted: tuple[str, ...],
                          needs_variable: bool = True) -> None:
    """Copy the premise's own refusals onto this candidate's docket.

    `wanted` names the premise slots this family reads, because they differ:
    `check_count_percent` reads no variable premise, so a model-only binding is
    no worse there than a corroborated one, and the D2 reason is filtered out
    for it alone.
    """
    for row in _premise_of(v).get("reasons") or []:
        code = row["reason"]
        if code not in wanted:
            continue
        if code == "binding_model_only" and not needs_variable:
            continue
        ref.add(code, v["id"], row.get("detail", ""))


#: The premise slots each shared check copies. Named so a reader can see that a
#: family's gates are a SELECTION from one stamp rather than a rule of its own.
_PROVENANCE_REASONS = ("provenance_not_printed",)
_BINDING_REASONS = ("binding_model_only", "binding_not_corroborated")
_APPLICABILITY_REASONS = ("reports_model_output", "percentage_is_weighted",
                          "statistic_kind_disputed", "value_withdrawn_by_a_correction",
                          "value_attributed_to_another_study")
_LITERAL_REASONS = ("printed_not_plain_numeral", "percent_sign_on_a_non_percentage")
#: READ BY THE THREE FAMILIES WHOSE ARITHMETIC IS THE MEAN'S, AND BY NO OTHER.
#: It is deliberately not in `_APPLICABILITY_REASONS`, which every family copies:
#: `check_sd_or_se` reads the mean only as a WITNESS that the dispersion beside it
#: is descriptive, and a weighted mean is still that witness. Refusing it there
#: would take a value out of a family for a reason that is not about that family.
_ESTIMATOR_REASONS = ("mean_is_not_a_simple_average",)
#: READ BY THE THREE FAMILIES WHOSE ARITHMETIC IS `mean * n`, AND BY NO OTHER.
#: See `_units` for why `check_sd_or_se` is not one of them.
_UNITS_REASONS = ("printed_in_another_unit",)


def _provenance(v: dict, ref: Refusal) -> str | None:
    """The registry `provenance` for a value, read off its premise."""
    _reasons_from_premise(v, ref, wanted=_PROVENANCE_REASONS)
    return _premise_of(v).get("provenance")


def _binding(v: dict, ref: Refusal, needs_variable: bool) -> None:
    """The `id_check` gate, read off the premise.

    `model_only` (`id_check: null`) keeps its own reason (D2): it refuses the
    families that read a variable premise and not `check_count_percent`, which
    reads none. Everything else is admitted only by exact membership in
    `premises.CORROBORATED`.
    """
    _reasons_from_premise(v, ref, wanted=_BINDING_REASONS, needs_variable=needs_variable)


def _variable(cand: Candidate, idx: _Index, ref: Refusal) -> dict | None:
    var = idx.variables.get(cand.variable_id) if cand.variable_id else None
    if var is None:
        ref.add("no_variable", cand.primary_value_id)
    return var


def _descriptive(v: dict, idx: _Index, ref: Refusal) -> dict:
    """The applicability gate every descriptive family shares: is this cell a
    DESCRIPTIVE statistic of a measured variable at all?

    BOTH ANSWERS ARE READ OFF THE STAMP. `premises.model_output_reason` asks
    `prepass.reports_model_output` first and then three structural questions the
    string rule cannot answer (a whole header that IS an estimate symbol, a
    neighbour the reading typed as an estimate, the paper's own `B = ... SE =
    ...` notation in a prose sentence with no column at all);
    `premises.value_premise` reads `statistic_disputed`, which
    `reconstruct.kind_consistency` sets when the same column header and printed
    form was read as a different KIND elsewhere in the same paper.

    ONE SELECTION, FIVE FAMILIES. `check_count_percent` had NO applicability
    gate at all until wave 7b: a count/percent pair read out of a `Coefficient
    (SE)` column, under a caption that says `Associations between ...`, ran and
    could accuse.
    """
    _reasons_from_premise(v, ref, wanted=_APPLICABILITY_REASONS)
    pre = _premise_of(v)
    desc = dict(pre.get("descriptive") or {})
    desc["statistic_disputed"] = bool(pre.get("disputed"))
    return desc


def _estimator(v: dict, ref: Refusal) -> None:
    """The premise GRIM, GRIMMER and SPRITE share and nothing else does: that this
    printed mean is an integer total divided by the n bound here.

    READ OFF THE STAMP, from the SAME four places the weighted-percentage guard
    reads -- the column band, the table's caption, the value's own sentence, and a
    sentence of the paper's governing its means. `premises.weighted_percentage_reason`
    read all four and then returned early unless the value was a percentage, so a
    survey-weighted mean, a Rubin-pooled mean, an ANCOVA least-squares mean, a
    trimmed mean and a two-stage mean of school means were each adjudicated
    `impossible` on integer data that produces them exactly.

    THE RECORD IS ALREADY IN `app_rec`: `_descriptive` copies the whole
    `descriptive` block, which carries `mean_is_not_a_simple_average` beside the
    other two. This function only moves the REFUSAL onto the docket, for the
    families that read this premise.
    """
    _reasons_from_premise(v, ref, wanted=_ESTIMATOR_REASONS)


def _units(v: dict, ref: Refusal) -> None:
    """The premise GRIM, GRIMMER and SPRITE share with the granularity stamp:
    that the step established for this variable is the step of the number as
    PRINTED.

    READ OFF THE STAMP (`premises.units_of`), which compares `value.units`
    against `variable.units` -- two schema fields nothing in this package had
    ever read. A quantity recorded in whole minutes and printed in hours moves in
    sixtieths, and `mean * n` is a claim about the unit printed: 11,369 whole
    minutes over 28 nurses is `6.77` h and returned GRIM, GRIMMER and SPRITE
    `impossible`, with the identical account in minutes `consistent`.

    `check_sd_or_se` DOES NOT READ IT, and the reason is that the mismatch says
    nothing about the premise that family uses. Its ceiling is the variable's
    RANGE, whose own unit the schema does not record, so a unit mismatch is not
    evidence about it either way -- and both directions are already closed: a
    dispersion printed in a COARSER unit only ever falls further under the
    ceiling (the tool accuses on an SD too LARGE, never too small), and one
    printed in a FINER unit drags its own paired mean outside the stated bound,
    which `bounds_verification` already withdraws as
    `bound_contradicted_by_printed_values`. Refusing it there would remove an
    honest check for a reason that is not about that check.
    """
    _reasons_from_premise(v, ref, wanted=_UNITS_REASONS)


def _granularity(var: dict, idx: _Index, ref: Refusal) -> tuple[bool, dict]:
    """`(the step of 1 is established, the verification record)`, both read off
    `variable.granularity.verification`.

    D3: GRIM runs only where the step of 1 is established by the PAPER or by the
    KIND. A `suspicious` resting on our own reading of the word "count" is the
    softer form of the accusation this project exists to avoid -- and so,
    exactly, is one resting on a sentence of the paper's that says nothing about
    granularity, or on a twelve-character fragment of a sentence about a
    different variable.
    """
    rec = ((var.get("granularity") or {}).get("verification")
           or _premises.granularity_verification(var, idx.haystack,
                                                 list(idx.variables.values()), []))
    for row in rec.get("reasons") or []:
        ref.add(row["reason"], var.get("id"), row.get("detail", ""))
    return bool(rec.get("establishes_step_of_one")), rec


def _bounds(var: dict, idx: _Index, ref: Refusal, *, need_both: bool,
            need_any: bool) -> tuple[float | None, float | None, str, dict]:
    """`(lower, upper, bound_source, verification record)`, read off
    `variable.bounds.verification`.

    A bound is passed ONLY where the kind makes it necessary or the paper states
    it in a located sentence about THIS variable. `not_stated`, and every source
    outside the allowlist, passes nothing and declares `assumed`, so an invented
    bound can never reach a range verdict.

    `need_both` / `need_any` say what this FAMILY needs, not what the variable
    has: a family that reads no bound at all still refuses when a DECLARED bound
    fails its evidence test, because a bound the account asserts and cannot
    support is a fact about the account rather than about this call.
    """
    rec = ((var.get("bounds") or {}).get("verification")
           or _premises.bounds_verification(var, idx.haystack,
                                            list(idx.variables.values()), []))
    for row in rec.get("reasons") or []:
        code = row["reason"]
        if code == "bounds_not_stated" and not (need_both or need_any):
            continue
        ref.add(code, var.get("id"), row.get("detail", ""))
    declared = {row["reason"] for row in rec.get("reasons") or []}
    if need_both and "bounds_not_stated" not in declared:
        if rec.get("lower_passed") is None:
            ref.add("lower_bound_not_stated", var.get("id"))
        if rec.get("upper_passed") is None:
            ref.add("upper_bound_not_stated", var.get("id"))
    return (rec.get("lower_passed"), rec.get("upper_passed"),
            rec.get("bound_source", ASSUMED_BOUND_SOURCE), rec)


def _literal(v: dict, ref: Refusal) -> dict | None:
    """The bridge's own reading of one printed literal, read off the premise.

    THE `%` SIGN IS NOT REQUIRED AND NOT FORBIDDEN ON A PERCENTAGE. `85.94%` and
    `73.0` are both percentages: which of the two a paper prints is a typographic
    choice of the column header's, and the account's `statistic` is what says the
    cell is a percentage. IT IS FORBIDDEN ON ANYTHING ELSE -- a value typed
    `mean` and printed `86.75%` had the sign stripped and entered GRIM as a mean
    of 86.75 whole-number ratings on a 1-7 scale.
    """
    _reasons_from_premise(v, ref, wanted=_LITERAL_REASONS)
    pre = _premise_of(v)
    if not pre:
        got = _read_plain(v.get("printed"))
        if got is None:
            ref.add("printed_not_plain_numeral", v["id"], repr(str(v.get("printed"))[:40]))
        return got
    return pre.get("literal") if not any(
        r["reason"] in _LITERAL_REASONS for r in pre.get("reasons") or []) else None


def _cross_check(v: dict, got: dict) -> dict:
    """What the account said about this literal, beside what the bridge read."""
    return {"value_id": v["id"], "printed": v.get("printed"),
            "bridge_value": got["value"], "bridge_decimals": got["decimals"],
            "account_numeric": v.get("numeric"), "account_decimals": v.get("decimals"),
            "account_printed_form": v.get("printed_form"),
            "agrees": (v.get("numeric") == got["value"]
                       and v.get("decimals") == got["decimals"])}


def _jsonable(obj: Any) -> Any:
    """A tool result as plain JSON types.

    SPRITE's reconstruction comes back holding numpy scalars, which `json.dumps`
    refuses. Converting with `default=str` would write the number as the STRING
    `"3"` and a reader could not tell that from a value the paper printed as
    text, so the scalars are unwrapped instead. Duck-typed on `.item()` /
    `.tolist()` rather than importing numpy, which this module has no other
    reason to need.
    """
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if hasattr(obj, "tolist"):
        return _jsonable(obj.tolist())
    if hasattr(obj, "item"):
        try:
            return _jsonable(obj.item())
        except (ValueError, TypeError):
            pass
    return str(obj)


def _sourcing(v: dict) -> dict:
    """The trace the registry stamps on every result."""
    loc = v.get("location") or {}
    if loc.get("kind") == "table_cell":
        where = f"{loc.get('table_id')} row {loc.get('row')} col {loc.get('col')}"
    elif loc.get("offset") is not None:
        where = f"{loc.get('kind')}@{loc.get('offset')}"
    else:
        where = str(loc.get("kind") or "")
    return {"source_quote": str(v.get("quote") or "") or None, "source_locator": where}


# --------------------------------------------------------------------------
# The per-family translations
# --------------------------------------------------------------------------


def to_count_percent_kwargs(cand: Candidate, idx: _Index) -> tuple[dict, dict] | Refusal:
    """`check_count_percent` -- the only family here that reads no variable
    SCALE, which is why a model-only binding is admitted for it.

    IT HAD NO APPLICABILITY GATE AT ALL, and it is the family whose verdict is
    the cheapest to reach: a count, a percentage and an n, and arithmetic. A
    count/percent pair read out of a `Coefficient (SE)` column, under a caption
    reading `Associations between mood and falls`, ran and could accuse; a cell
    the account itself marks `statistic_disputed` -- the same header read as
    another kind elsewhere in the paper -- ran too, on both the percentage and
    the count. The other four families had read both facts since wave 7.
    """
    ref = Refusal()
    pv = idx.by_id[cand.value_ids["percentage"]]
    prov = _provenance(pv, ref)
    _binding(pv, ref, needs_variable=False)
    app_rec = _descriptive(pv, idx, ref)
    pct = _literal(pv, ref)
    # THE TOOL'S PARAMETER IS A PERCENTAGE, SO THE VALUE HAS TO BE ONE.
    # `check_count_percent` compares `count / n * 100` against `percentage`, and
    # a `proportion` -- a fraction of ONE -- fails that comparison by a factor of
    # a hundred on a paper that did nothing wrong.
    #
    # THE GATE IS EVIDENCE, NOT VOCABULARY, and it is narrow on purpose. This
    # module's own rule is that "the `%` sign is not required and not
    # forbidden" -- `73.0` under a `n (%)` band is a percentage -- so demanding
    # a percentage KIND would refuse 109 honest cells on
    # jamanetworkopen.37679 alone, where the variable is `Age` (categorical)
    # and the column is the percentage in each band. What actually cannot be
    # told apart is a number in (0, 1): `0.73` is `0.73%` and `73%` in the same
    # digits. Above 1, no proportion reading exists; at 0 both readings agree.
    #
    # AND THE KIND CANNOT EXEMPT IT. The gate used to be skipped whenever the
    # variable's kind was a percentage kind, which made the ONE ambiguous case
    # turn on the ONE premise this family does not check: a variable id bound by
    # the model alone. `0.867` on a variable the reading typed
    # `percentage_of_subjects` was compared against `26 / 30 * 100` and came
    # back `suspicious` on an honest paper. A printed `%`, which is the paper's
    # own mark, still settles it.
    kind = str((idx.variables.get(cand.variable_id) or {}).get("kind") or "")
    if kind == "proportion":
        ref.add("percentage_is_a_proportion", pv["id"],
                f"printed {str(pv.get('printed'))[:20]!r} on a `proportion` variable")
    elif pct is not None and not pct["is_percent"] and 0 < abs(pct["value"]) <= 1:
        ref.add("percentage_scale_not_established", pv["id"],
                f"printed {str(pv.get('printed'))[:20]!r} and variable kind "
                f"`{kind or 'none'}`")
    # AND THE DENOMINATOR THIS FAMILY DIVIDES BY IS A COUNT OF SUBJECTS. A
    # percentage OF OBSERVATIONS, OF TIME, or OF A REFERENCE VALUE is a
    # percentage of something the account carries no denominator for, so the
    # group's n is not its base by the reading's own words. Round 3's case:
    # `31 attended at least ten of the twelve scheduled sessions, and attendance
    # averaged 82.5% of scheduled sessions` -- two honest, unrelated quantities
    # paired because they share (study, group, phase, variable), and 31/40
    # compared against a percentage of SESSIONS.
    if kind in _premises.NON_SUBJECT_PERCENTAGE_KINDS:
        ref.add("percentage_base_is_not_subjects", pv["id"],
                f"the reading types this variable `{kind}`, and the only denominator at "
                "this coordinate is a count of subjects")
    n, n_reason, n_rec = idx.group_n(pv)
    if n_reason:
        ref.add(n_reason, pv["id"], _n_detail(n_rec))
    cv = None
    cid = cand.value_ids.get("count")
    if "count" in cand.ambiguous_roles:
        ref.add("ambiguous_pairing", pv["id"], "two or more counts are printed here")
    elif cid is None:
        ref.add("count_not_printed", pv["id"])
    else:
        cv = idx.by_id[cid]
        _provenance(cv, ref)
        _binding(cv, ref, needs_variable=False)
        _descriptive(cv, idx, ref)
        if _is_plain_integer(cv.get("printed")) is None:
            ref.add("printed_not_plain_numeral", cv["id"],
                    repr(str(cv.get("printed"))[:40]))
    # THE BASE IS A PREMISE, AND THE PAPER'S OWN TWO NUMBERS ARE THE EVIDENCE
    # ABOUT IT. See `premises.other_bases_that_fit`: the check runs where `n`
    # reproduces the printed percentage, and where NO integer denominator does
    # (which is what an arithmetic error looks like). It refuses where the
    # paper's own count and percentage are reproduced exactly at some OTHER
    # integer -- there the accusation rests entirely on our having chosen this
    # n, and a percentage over a different base is the commonest convention in a
    # clinical table.
    alternatives: list[int] = []
    if not ref and n is not None and pct is not None and cv is not None:
        printed_count = _is_plain_integer(cv.get("printed"))
        if not _premises.base_fits(printed_count, pct["value"], pct["decimals"], n):
            alternatives = _premises.other_bases_that_fit(
                printed_count, pct["value"], pct["decimals"], n, idx.max_printed_n)
            if alternatives:
                ref.add("another_denominator_fits", pv["id"],
                        f"{printed_count}/{n} does not give {pv.get('printed')}, and "
                        + ", ".join(str(m) for m in alternatives)
                        + (" does" if len(alternatives) == 1 else " do"))
    if ref:
        ref.sort()
        return ref
    args = {"count": _is_plain_integer(cv.get("printed")), "percentage": pct["value"],
            "n": n, "decimals": pct["decimals"], **_sourcing(pv)}
    premises = {
        "provenance": {"value": prov, "value_id": pv["id"]},
        "applicability": app_rec,
        "n": n_rec,
        "scale": {"printed_percent_sign": pct["is_percent"], "variable_kind": kind},
        "literals": [_cross_check(pv, pct),
                     _cross_check(cv, _read_plain(cv.get("printed")))],
        "binding": {"percentage": pv.get("id_check"), "count": cv.get("id_check")},
    }
    return args, premises


def to_grim_kwargs(cand: Candidate, idx: _Index) -> tuple[dict, dict] | Refusal:
    """`grim_check`. A one-sided or absent bound is passed as `None` on the side
    the paper does not state (D1-A): the granularity branch is bound-free, so an
    absent bound removes an accusation path and adds none."""
    ref = Refusal()
    mv = idx.by_id[cand.value_ids["mean"]]
    prov = _provenance(mv, ref)
    _binding(mv, ref, needs_variable=True)
    app_rec = _descriptive(mv, idx, ref)
    _estimator(mv, ref)
    _units(mv, ref)
    var = _variable(cand, idx, ref)
    dt, gran_rec, bound_rec = "unknown", {}, {}
    if var is not None:
        step_ok, gran_rec = _granularity(var, idx, ref)
        dt = _data_type(var, step_ok)
        if dt not in INTEGER_DATA_TYPES:
            ref.add("kind_not_integer", var["id"], f"kind `{var.get('kind')}` -> {dt}")
        _, _, _, bound_rec = _bounds(var, idx, ref, need_both=False, need_any=False)
    lit = _literal(mv, ref)
    n, n_reason, n_rec = idx.group_n(mv)
    if n_reason:
        ref.add(n_reason, mv["id"], _n_detail(n_rec))
    if ref:
        ref.sort()
        return ref
    args = {"mean": lit["value"], "n": n,
            "scale_min": bound_rec["lower_passed"], "scale_max": bound_rec["upper_passed"],
            "decimals": lit["decimals"], "data_type": dt,
            "bound_source": bound_rec["bound_source"],
            "discreteness_source": gran_rec["discreteness_source"],
            "provenance": prov, **_sourcing(mv)}
    premises = {"provenance": {"value": prov, "value_id": mv["id"]},
                "applicability": app_rec,
                "bounds": bound_rec, "discreteness": gran_rec, "n": n_rec,
                "literals": [_cross_check(mv, lit)],
                "binding": {"mean": mv.get("id_check")}}
    return args, premises


def _mean_sd_premises(cand: Candidate, idx: _Index, ref: Refusal):
    """The premises GRIMMER and SPRITE share, resolved once."""
    mv = idx.by_id[cand.value_ids["mean"]]
    prov = _provenance(mv, ref)
    _binding(mv, ref, needs_variable=True)
    app_rec = _descriptive(mv, idx, ref)
    _estimator(mv, ref)
    _units(mv, ref)
    sv = idx.by_id[cand.value_ids["sd"]] if cand.value_ids.get("sd") else None
    if "sd" in cand.ambiguous_roles:
        ref.add("ambiguous_pairing", mv["id"], "two or more SDs sit at this cell")
    elif sv is None:
        ref.add("no_paired_sd", mv["id"])
    else:
        _provenance(sv, ref)
        _binding(sv, ref, needs_variable=True)
        _descriptive(sv, idx, ref)
        # THE SD IS HELD TO THE UNIT RULE TOO. GRIMMER and SPRITE reconstruct a
        # sample from BOTH numbers, so a dispersion printed in a unit other than
        # the variable's is the same defect one input further along.
        _units(sv, ref)
    var = _variable(cand, idx, ref)
    dt, gran_rec, bound_rec = "unknown", {}, {}
    if var is not None:
        step_ok, gran_rec = _granularity(var, idx, ref)
        dt = _data_type(var, step_ok)
        if dt not in INTEGER_DATA_TYPES:
            ref.add("kind_not_integer", var["id"], f"kind `{var.get('kind')}` -> {dt}")
        _, _, _, bound_rec = _bounds(var, idx, ref, need_both=True, need_any=True)
    lit_m = _literal(mv, ref)
    lit_s = _literal(sv, ref) if sv is not None else None
    n, n_reason, n_rec = idx.group_n(mv)
    if n_reason:
        ref.add(n_reason, mv["id"], _n_detail(n_rec))
    return mv, sv, prov, dt, gran_rec, bound_rec, lit_m, lit_s, n, n_rec, app_rec


def to_grimmer_kwargs(cand: Candidate, idx: _Index) -> tuple[dict, dict] | Refusal:
    """`grimmer_check`. Its ToolSpec exposes no `bound_source` parameter (the
    function accepts one), so through the registry it runs at `assumed` and a
    range failure caps at `suspicious`. Recorded, not worked around.

    AND A CEILING ON n, WHICH IS A RUNTIME FACT RATHER THAN A PREMISE -- the same
    fact SPRITE has had since round 2, on the family that was wired without it.
    See `GRIMMER_MAX_N` for the measurements.
    """
    ref = Refusal()
    mv, sv, prov, dt, gran, bnd, lm, ls, n, n_rec, app = _mean_sd_premises(cand, idx, ref)
    if n is not None and n > GRIMMER_MAX_N:
        ref.add("n_too_large_for_grimmer", mv["id"],
                f"n = {n} is above the measured ceiling of {GRIMMER_MAX_N}")
    if ref:
        ref.sort()
        return ref
    args = {"mean": lm["value"], "sd": ls["value"], "n": n,
            "scale_min": bnd["lower_passed"], "scale_max": bnd["upper_passed"],
            "decimals": lm["decimals"], "decimals_sd": ls["decimals"], "data_type": dt,
            "discreteness_source": gran["discreteness_source"],
            "provenance": prov, **_sourcing(mv)}
    premises = {"provenance": {"value": prov, "value_id": mv["id"]},
                "applicability": app,
                "bounds": {**bnd, "bound_source_not_exposed_by_toolspec": True},
                "discreteness": gran, "n": n_rec,
                "literals": [_cross_check(mv, lm), _cross_check(sv, ls)],
                "binding": {"mean": mv.get("id_check"), "sd": sv.get("id_check")}}
    return args, premises


def to_sprite_kwargs(cand: Candidate, idx: _Index) -> tuple[dict, dict] | Refusal:
    """`sprite_reconstruct`. Same premises as GRIMMER, same missing
    `bound_source`, and the seed is left at the registry's declared default so
    the search is reproducible from the ledger.

    AND A CEILING ON n, WHICH IS A RUNTIME FACT RATHER THAN A PREMISE. The
    search is linear in n: one call at n = 5,000 costs 1.9 s and at n = 50,000
    costs 110 s, so a single mis-read denominator stalls the run instead of
    failing it -- and the per-candidate try/except catches exceptions, not
    seconds. Refused by name above `SPRITE_MAX_N`, which is a statement about
    this tool and not about the paper.
    """
    ref = Refusal()
    mv, sv, prov, dt, gran, bnd, lm, ls, n, n_rec, app = _mean_sd_premises(cand, idx, ref)
    if n is not None and n > SPRITE_MAX_N:
        ref.add("n_too_large_for_sprite", mv["id"],
                f"n = {n} is above the measured ceiling of {SPRITE_MAX_N}")
    span = _sprite_span(bnd)
    if n is not None and span is not None and span > SPRITE_NARROW_SPAN \
            and n * span > SPRITE_MAX_SEARCH:
        ref.add("sprite_search_too_large", mv["id"],
                f"the stated scale spans {span:g} and n = {n}, so the search is "
                f"{n * span:g} wide against the measured ceiling of {SPRITE_MAX_SEARCH} "
                f"(a span at or under {SPRITE_NARROW_SPAN} is admitted at any n)")
    if ref:
        ref.sort()
        return ref
    args = {"mean": lm["value"], "sd": ls["value"], "n": n,
            "scale_min": bnd["lower_passed"], "scale_max": bnd["upper_passed"],
            "decimals_mean": lm["decimals"], "decimals_sd": ls["decimals"],
            "data_type": dt, "discreteness_source": gran["discreteness_source"],
            "provenance": prov, **_sourcing(mv)}
    premises = {"provenance": {"value": prov, "value_id": mv["id"]},
                "applicability": app,
                "bounds": {**bnd, "bound_source_not_exposed_by_toolspec": True},
                "discreteness": gran, "n": n_rec,
                "literals": [_cross_check(mv, lm), _cross_check(sv, ls)],
                "binding": {"mean": mv.get("id_check"), "sd": sv.get("id_check")}}
    return args, premises


def _sprite_span(bound_rec: dict) -> float | None:
    """The width of the scale SPRITE would search, or None where either side is
    absent. `to_sprite_kwargs` reaches here only with both bounds passed
    (`need_both=True`), so None means a shape this guard cannot measure and must
    not refuse on."""
    lo, hi = (bound_rec or {}).get("lower_passed"), (bound_rec or {}).get("upper_passed")
    try:
        span = float(hi) - float(lo)
    except (TypeError, ValueError):
        return None
    return span if span >= 0 else None


def to_sd_or_se_kwargs(cand: Candidate, idx: _Index) -> tuple[dict, dict] | Refusal:
    """`check_sd_or_se`. The pairing is the family's applicability question: a
    dispersion beside a regression COEFFICIENT is a model standard error, not a
    descriptive dispersion, and adjudicating it against a variable's scale is a
    category error."""
    ref = Refusal()
    dv = idx.by_id[cand.value_ids["dispersion"]]
    prov = _provenance(dv, ref)
    _binding(dv, ref, needs_variable=True)
    # THE PAIRING IS ASKED FIRST, because it is the most specific thing that can
    # be said about this candidate. A dispersion beside a value the reading
    # itself typed `coefficient` is a model standard error by the account's own
    # words; `reports_model_output` says the same thing from the column band and
    # is recorded too, but the reader is owed the sharper sentence first.
    beside_coefficient = bool(cand.value_ids.get("coefficient")
                              or "coefficient" in cand.ambiguous_roles)
    if beside_coefficient:
        # AND THE READER IS TOLD WHICH TOOL *WOULD* TAKE IT. Saying only "wrong
        # family" leaves a coefficient table looking like a thing nothing can
        # check, when `check_regression` is written, registered, and takes
        # exactly this pair -- it is the premise and not the tool that is
        # missing, and those are different facts. `NOT_WIRED_TOOLS` carries the
        # measurement; the count for this account is in `tools_not_wired`.
        ref.add("dispersion_of_coefficient", dv["id"],
                f"beside `{cand.value_ids.get('coefficient') or 'a coefficient'}`; "
                f"`check_regression` takes this pair and is not wired "
                f"({NOT_WIRED_TOOLS['check_regression']['blocked_on']})")
    app_rec = _descriptive(dv, idx, ref)
    if beside_coefficient:
        pass
    elif cand.ambiguous_roles:
        ref.add("ambiguous_pairing", dv["id"],
                f"two or more values could be the {cand.ambiguous_roles[0]}")
    elif not cand.value_ids.get("mean"):
        ref.add("no_paired_mean", dv["id"])
    else:
        # THE MEAN IS THE WITNESS, so it is held to EVERY rule the inputs are.
        # Its number never enters the arithmetic, but the claim "this is a
        # DESCRIPTIVE dispersion" rests entirely on it, and a witness we cannot
        # show the paper printed cannot establish that. Provenance was being
        # asked and binding and the literal were not, so a mean the name join
        # CONTRADICTS, and a mean printed `Twenty-six`, `84,299` or
        # `approximately 3.5`, each licensed the adjudication of a real
        # dispersion against a real scale -- on a witness the same account
        # refuses to use for anything else.
        wv = idx.by_id[cand.value_ids["mean"]]
        _provenance(wv, ref)
        _binding(wv, ref, needs_variable=True)
        _literal(wv, ref)
        _descriptive(wv, idx, ref)
    lit = _literal(dv, ref)
    var = _variable(cand, idx, ref)
    bound_rec: dict = {}
    if var is not None:
        _, _, _, bound_rec = _bounds(var, idx, ref, need_both=False, need_any=True)
    n, n_reason, n_rec = idx.group_n(dv)
    if n_reason:
        ref.add(n_reason, dv["id"], _n_detail(n_rec))
    if ref:
        ref.sort()
        return ref
    args = {"reported_value": lit["value"], "n": n,
            "reported_as": REPORTED_AS_OF.get(str(dv.get("statistic")), "unknown"),
            # NEVER FILLED. The scaffold records no plausibility ceiling for a
            # variable other than its bounds, and inventing one is the exact
            # move `check_sd_or_se`'s own `bound_source` argument exists to stop.
            "plausible_sd_max": None,
            "variable_range_min": bound_rec["lower_passed"],
            "variable_range_max": bound_rec["upper_passed"],
            "decimals": lit["decimals"], "bound_source": bound_rec["bound_source"],
            **_sourcing(dv)}
    premises = {"provenance": {"value": prov, "value_id": dv["id"]},
                "applicability": app_rec,
                "bounds": bound_rec, "n": n_rec,
                "literals": [_cross_check(dv, lit)],
                "pairing": {"mean": cand.value_ids.get("mean")},
                "binding": {"dispersion": dv.get("id_check"),
                            "mean": (idx.by_id[cand.value_ids["mean"]].get("id_check")
                                     if cand.value_ids.get("mean") else None)}}
    return args, premises


TRANSLATORS = {
    "count_percent": to_count_percent_kwargs,
    "grim": to_grim_kwargs,
    "sd_or_se": to_sd_or_se_kwargs,
    "grimmer": to_grimmer_kwargs,
    "sprite": to_sprite_kwargs,
}


def translate(cand: Candidate, idx: _Index) -> tuple[dict, dict] | Refusal:
    """The family's own translation, unless an input's id does not name one value.

    THE ID GATE IS HERE AND NOT IN A FAMILY, because every translator resolves
    every input through `idx.by_id` -- which is last-write-wins -- so a duplicated
    id is wrong for all five in the same way and in the same place. Measured on an
    honest paper: an abstract's 1-decimal mean and a table's 3-decimal SD minted
    the same id, GRIM was handed the SD as its mean, and `impossible` came back
    while `n_candidates == n_run + n_refused` balanced exactly.
    """
    # AND THE ACCOUNT'S OWN INTEGRITY RECORD IS ASKED BEFORE ANY OF IT. It is
    # the same shape of gate as the two below -- an input whose id does not name
    # one resolvable record -- and it is asked first because a coordinate that
    # names nothing is a weaker footing than a coordinate that names two things.
    named = sorted({vid for vid in cand.value_ids.values() if vid in idx.integrity_problems})
    if named:
        ref = Refusal()
        for vid in named:
            ref.add("account_integrity_problem", vid, "; ".join(idx.integrity_problems[vid]))
        return ref
    dupes = sorted({vid for vid in cand.value_ids.values() if vid in idx.duplicate_ids})
    if dupes:
        ref = Refusal()
        for vid in dupes:
            ref.add("duplicate_value_id", vid,
                    f"{sum(1 for v in idx.values if v.get('id') == vid)} values carry the id "
                    f"{vid!r}, so it names no one record")
        return ref
    # AND THE VARIABLE'S ID IS THE SAME GATE ONE TABLE OVER. It is asked here for
    # the same reason: every translator resolves the variable through
    # `idx.variables`, `check_count_percent` included (it reads the `kind`), so a
    # duplicated variable id is wrong for all five in the same way and in the
    # same place.
    if cand.variable_id and cand.variable_id in idx.duplicate_variable_ids:
        ref = Refusal()
        ref.add("duplicate_variable_id", cand.variable_id,
                f"{sum(1 for v in _premises.readable_variables(idx.account) if v.get('id') == cand.variable_id)}"
                f" variables carry the id {cand.variable_id!r}, so it names no one record")
        return ref
    return TRANSLATORS[cand.family](cand, idx)


# --------------------------------------------------------------------------
# Run and record
# --------------------------------------------------------------------------


def _with_nearby_denominators(n_rec: dict | None, args: dict) -> dict:
    """The denominators near this one that WOULD have fitted, on any record that
    did not come back `consistent`.

    A PER-ROW n IS THE PREMISE THE SCAFFOLD DOES NOT CAPTURE. The n the bridge
    binds is the group's, and missing data on one outcome shrinks the analysed n
    below it -- which is the direction that manufactures a GRIM failure. So
    every non-consistent record carries the window, as a QUESTION for the
    authors and never as a rescue: `nearby_denominators` documents that 70-80%
    of GENUINE failures at n = 20-50 also fit somewhere in n +/- 2, so "it works
    at a nearby n" is what almost every failure looks like, honest or not. The
    severity is untouched.
    """
    rec = dict(n_rec or {})
    mean, n = args.get("mean"), args.get("n")
    dp = args.get("decimals", args.get("decimals_mean"))
    if mean is None or n is None or dp is None:
        return rec
    from ..tools.grim import nearby_denominators
    rec["n_that_would_fit"] = nearby_denominators(float(mean), int(n), int(dp))
    rec["n_that_would_fit_note"] = (
        "A QUESTION, NOT A RESCUE. The n bound here is the group's; the n analysed "
        "for one outcome is often smaller. Ask which n this row was analysed at. "
        "It does not weaken the verdict: 70-80% of genuine GRIM failures at "
        "n = 20-50 also fit somewhere in n +/- 2.")
    return rec


def _n_roles(n_rec: dict | None) -> dict[str, str]:
    """The denominator's own value ids, as `value_ids` roles.

    `n` for the one row that supplied it; `n_2`, `n_3` ... when the paper prints
    the same integer in more than one place and every one of them agreed (two
    that disagree are `ambiguous_n` and nothing runs).
    """
    ids = list((n_rec or {}).get("value_ids") or [])
    if not ids or (n_rec or {}).get("n") is None:
        return {}
    return {("n" if i == 0 else f"n_{i + 1}"): vid for i, vid in enumerate(ids)}


def _census_vs_bridge(account: dict, cands: list[Candidate],
                      outcome: dict[str, dict]) -> dict:
    """Per census family: what it called bindable, what the bridge did with it.

    THE TWO UNITS DIFFER AND THE COMPARISON HAS TO SAY SO. The census counts
    COORDINATES; the bridge counts VALUES. A coordinate holding three
    count/percent pairs is one census row and three bridge calls, and a
    coordinate whose census premise is present can still hold a value the bridge
    refuses. So this maps each census-bindable coordinate onto the bridge
    candidates that sit at it, and gives every one that did not run a reason.
    """
    cen = _app.census(account)
    by_coord: dict[tuple, list[Candidate]] = defaultdict(list)
    # BOTH SIDES OF THIS JOIN KEY BY HAND, AND THEY MUST AGREE. The candidate's
    # key is built here and the census row's thirty lines down, from two
    # differently-shaped mappings that happen to spell the axes the same way --
    # which is the arrangement `Coord` exists to remove. Neither literal
    # survives.
    for c in cands:
        by_coord[Coord.from_mapping(c.coordinate).var_key(c.variable_id)].append(c)
    out: dict[str, Any] = {}
    roll: dict[str, int] = defaultdict(int)
    n_bindable = 0
    for fam in cen["families"]:
        name = fam["family"]
        bridge_families = [f for f, _, c in FAMILIES if c == name]
        rows: list[dict] = []
        n_run = 0
        for b in fam["bindable"]:
            n_bindable += 1
            if "variable_id" not in b:      # a comparison- or claim-level family
                key = None
            else:
                key = Coord.from_mapping(b).var_key(b.get("variable_id"))
            here = [c for c in by_coord.get(key, []) if c.family in bridge_families]
            ran = [c for c in here if outcome[c.check_id]["ran"]]
            if ran:
                n_run += 1
                continue
            if not bridge_families:
                reason, all_reasons = UNWIRED.get(name, "family_not_wired"), []
            elif not here:
                reason, all_reasons = "no_bridge_candidate", []
            else:
                all_reasons = sorted({outcome[c.check_id]["reason"] for c in here},
                                     key=reason_rank)
                # THE COORDINATE'S REASON IS THE LAST PREMISE STANDING, not the
                # first. Several values can sit at one coordinate -- a table mean
                # and a prose mean of the same variable -- and the reader's
                # question is "what is the one thing between this coordinate and
                # a check?", which is answered by the candidate that got
                # FURTHEST. The first-missing rule would have answered with a
                # premise missing from a different value.
                reason = all_reasons[-1]
            rows.append({**b, "reason": reason, "reasons": all_reasons})
            roll[reason] += 1
        out[name] = {
            "census_tools": fam["tools"],
            "census_bindable": fam["n_bindable"],
            "bridge_families": bridge_families,
            "bridge_calls": sum(1 for c in cands
                                if c.family in bridge_families and outcome[c.check_id]["ran"]),
            "coordinates_run": n_run,
            "coordinates_not_run": len(rows),
            "not_run_by_reason": dict(sorted(
                {r["reason"]: sum(1 for x in rows if x["reason"] == r["reason"])
                 for r in rows}.items())),
            "not_run": rows,
        }
    out["_totals"] = {
        "census_bindable_coordinates": n_bindable,
        "bridge_calls": sum(1 for c in cands if outcome[c.check_id]["ran"]),
        "coordinates_not_run_by_reason": dict(sorted(roll.items())),
    }
    return out


def unwired_population(idx: "_Index") -> list[dict]:
    """One record per `NOT_WIRED_TOOLS` entry, with its population COUNTED from
    this account.

    THE COUNT IS THE POINT. Naming an unwired tool in a comment says nothing
    about whether it would have anything to do here, and this repo has been
    wrong in both directions on that in one session: `check_regression` looked
    like a coverage answer and its population is real (24 cells the sd_or_se
    translator already refuses by name), while `recalc_stat_to_p` was reported
    as 64 waiting p-values and its population on the same account is ZERO,
    because the paper prints B, SE and p and never a test statistic. A number
    computed from the account cannot make that mistake twice.

    IT COUNTS WHAT THE TOOL WOULD CONSUME, NOT WHAT IT WOULD VERDICT. Every one
    of these is still blocked on the premise named in `NOT_WIRED_TOOLS`, so the
    count is the size of a REFUSAL and never a promise of checks.
    """
    p_at: dict[tuple, list[dict]] = defaultdict(list)
    for v in idx.values:
        loc = v.get("location") or {}
        if loc.get("kind") == "table_cell" and v.get("statistic") == "p_value":
            p_at[(loc.get("table_id"), loc.get("row"), loc.get("col"))].append(v)
    regression = 0
    for v in idx.values:
        loc = v.get("location") or {}
        if loc.get("kind") != "table_cell":
            continue
        if v.get("statistic") not in ("sd", "se", "sem", "dispersion_unstated"):
            continue
        cell = idx.by_cell[(loc.get("table_id"), loc.get("row"), loc.get("col"))]
        if not [w for w in cell if w.get("statistic") == "coefficient"]:
            continue
        # THE p IS NOT IN THE SAME CELL, which is why `idx.partners` cannot see
        # it and why no existing candidate reaches it: a regression table prints
        # `B (SE)` in one column and its p in the NEXT one. Counted at col + 1
        # rather than searched for, so a cell with no p beside it is not counted.
        row, col = loc.get("row"), loc.get("col")
        if isinstance(col, int) and p_at.get((loc.get("table_id"), row, col + 1)):
            regression += 1
    stat_to_p = sum(1 for c in (idx.account.get("comparisons") or [])
                    if isinstance(c, dict) and c.get("statistic_printed")
                    and c.get("df_printed") and c.get("p_printed"))
    counted = {"check_regression": regression, "recalc_stat_to_p": stat_to_p}
    return [{"tool": name, "population_in_this_account": counted.get(name, 0), **rec}
            for name, rec in sorted(NOT_WIRED_TOOLS.items())]


def _unwired_safely(idx: "_Index") -> list[dict]:
    """`unwired_population`, held to the rule every other whole-account reader
    here is held to: IT MAY NOT TAKE THE RUN WITH IT.

    It is called from `evaluate`'s return expression, outside the per-candidate
    try/except, so a malformed coordinate in one cell would cost the paper its
    entire sidecar -- no checks, no refusal docket, nothing. That is the exact
    defect `_census_safely` exists for, and this is a strictly less important
    reader than the census, so it gets the same treatment: a counting failure is
    reported as a count we could not take, never as a paper with no checks."""
    try:
        return unwired_population(idx)
    except Exception as exc:  # noqa: BLE001
        return [{"tool": name, "population_in_this_account": None,
                 "error": f"{type(exc).__name__}: {exc}", **rec}
                for name, rec in sorted(NOT_WIRED_TOOLS.items())]


def _census_safely(account: dict, idx: "_Index", cands: list[Candidate],
                   outcome: dict[str, dict]) -> dict:
    """The census-against-bridge reconciliation, and never the run.

    IT IS A SIDECAR OF A SIDECAR. `applicability.census` reads the same values
    the bridge does and can raise on one the bridge has already skipped, so it
    is given the WELL-FORMED values and wrapped: a reconciliation that cannot be
    computed is a missing table, not a lost `checks.json`. `_totals` is always
    present because the renderer prints it.
    """
    try:
        return _census_vs_bridge({**account, "values": idx.values}, cands, outcome)
    except Exception as exc:  # noqa: BLE001
        return {"_totals": {"census_bindable_coordinates": 0,
                            "bridge_calls": sum(1 for c in cands
                                                if outcome.get(c.check_id, {}).get("ran")),
                            "coordinates_not_run_by_reason": {}},
                "error": f"{type(exc).__name__}: {exc}"}


def evaluate(account: dict, text: str = "", families: tuple[str, ...] | None = None
             ) -> dict:
    """Everything `run` writes, computed from an account in memory. Pure apart
    from the in-process tool calls, which read nothing but their arguments.

    THE ACCOUNT IS STAMPED FIRST, ON A COPY, AND ALWAYS. `bind.assemble` already
    stamps what it writes to disk, but this function is handed hand-built
    accounts (every adversarial fixture), model-authored ones, and accounts a
    test has edited AFTER assembly -- and a stamp computed before an edit is a
    fact about the account as it was. Recomputing is the only reading that
    cannot be stale, and the copy is what keeps the bridge's other contract:
    nothing here writes back into the account it was given.
    """
    account = _premises.stamp(account, text)
    records: list[dict] = []
    refused: list[dict] = []
    outcome: dict[str, dict] = {}
    # A FAMILY NAME THIS BRIDGE DOES NOT DEFINE IS A REFUSAL, NOT AN EXCEPTION.
    # `evaluate(acc, text, families=("no_such_family",))` raised `KeyError` out
    # of the by-family roll-up -- outside every per-candidate try/except -- so
    # the run produced no checks, no refusals and no docket. It is a caller's
    # error rather than anything the paper did, and the isolation rule that
    # covers a malformed value covers it too: one named skip, never the run.
    unknown = tuple(str(f) for f in (families or ()) if f not in TOOL_OF)
    if unknown:
        families = tuple(f for f in families if f in TOOL_OF)
    for name in unknown:
        blew = Refusal()
        blew.add("unknown_family", None,
                 f"`{name}` is not one of " + ", ".join(FAMILY_NAMES))
        refused.append({"check_id": f"chk:family:{name}", "family": None, "tool": None,
                        "coordinate": {}, "variable_id": None, "value_ids": {},
                        "reason": "unknown_family", "reasons": blew.reasons})
    # THE INDEX AND THE CENSUS ARE INSIDE THE ISOLATION TOO. They were not: a
    # `location` that arrived as the string `"table_cell"`, and a value with no
    # `id`, each raised in `candidates()` -- which runs BEFORE the per-candidate
    # try/except -- and took the whole sidecar with them. A malformed value is
    # now one named skip in the docket.
    cands, idx = candidates(account, text, families)
    for skip in idx.malformed:
        vid = skip.get("id") or f"value[{skip['index']}]"
        blew = Refusal()
        blew.add("value_malformed", vid, skip["why"])
        refused.append({"check_id": f"chk:value:{vid}", "family": None, "tool": None,
                        "coordinate": {}, "variable_id": None, "value_ids": {},
                        "reason": "value_malformed", "reasons": blew.reasons})
    for cand in cands:
        # ONE CANDIDATE CANNOT TAKE THE RUN WITH IT. A printed `0` reaching a
        # division and a hand-edited group n of `"thirty"` each raised out of
        # the loop, so NOTHING was written -- no `checks.json`, no refusal
        # docket, no record of the 126 candidates that had nothing wrong with
        # them. A candidate that falls over is a refusal naming the exception,
        # which is a fact about that candidate and about nothing else.
        try:
            got = translate(cand, idx)
            if isinstance(got, Refusal):
                row = {"check_id": cand.check_id, "family": cand.family, "tool": cand.tool,
                       "coordinate": cand.coordinate, "variable_id": cand.variable_id,
                       "value_ids": cand.value_ids, "reason": got.reason,
                       "reasons": got.reasons}
                refused.append(row)
                outcome[cand.check_id] = {"ran": False, "reason": got.reason}
                continue
            args, premises = got
            result = _jsonable(_registry.BY_NAME[cand.tool].call(dict(args)))
        except Exception as exc:  # noqa: BLE001
            blew = Refusal()
            blew.add("check_raised", cand.primary_value_id,
                     f"{type(exc).__name__}: {exc}")
            refused.append({"check_id": cand.check_id, "family": cand.family,
                            "tool": cand.tool, "coordinate": cand.coordinate,
                            "variable_id": cand.variable_id,
                            "value_ids": cand.value_ids, "reason": "check_raised",
                            "reasons": blew.reasons})
            outcome[cand.check_id] = {"ran": False, "reason": "check_raised"}
            continue
        severity = result.get("severity") if isinstance(result, dict) else None
        if severity != "consistent":
            premises = {**premises, "n": _with_nearby_denominators(premises.get("n"), args)}
        records.append({
            "check_id": cand.check_id, "tool": cand.tool, "family": cand.family,
            "coordinate": cand.coordinate, "variable_id": cand.variable_id,
            # EVERY INPUT, THE DENOMINATOR INCLUDED. `value_ids` is defined as
            # "the value ids of every input (mean, sd, n, count, percentage)"
            # and the n was the one input that never appeared in it, so an
            # invariant asserted over `value_ids` could not see the row that
            # supplied the denominator of every call in the run.
            "value_ids": {**cand.value_ids, **_n_roles(premises.get("n"))},
            "args": args, "premises": premises,
            # COPIED VERBATIM. The bridge never re-severities a tool result --
            # the dispatch rule, and the one thing that keeps a reader's ladder
            # the tool's own.
            "result": result, "severity": severity,
        })
        outcome[cand.check_id] = {"ran": True, "reason": ""}
    by_family: dict[str, dict] = {}
    for fam in (FAMILY_NAMES if families is None else families):
        ran = [r for r in records if r["family"] == fam]
        ref = [r for r in refused if r["family"] == fam]
        by_family[fam] = {
            "tool": TOOL_OF[fam], "candidates": len(ran) + len(ref), "run": len(ran),
            "refused": len(ref),
            "by_severity": dict(sorted(
                {s: sum(1 for r in ran if r["severity"] == s)
                 for s in {r["severity"] for r in ran}}.items(), key=lambda kv: str(kv[0]))),
            "refused_by_reason": dict(sorted(
                {r["reason"]: sum(1 for x in ref if x["reason"] == r["reason"])
                 for r in ref}.items())),
        }
    return {
        "schema_version": SCHEMA_VERSION,
        # A MALFORMED VALUE IS A CANDIDATE TOO, and so is a family name this
        # bridge does not define, so that `n_run + n_refused == n_candidates`
        # stays a conservation law rather than a coincidence: a skip that
        # appeared in the docket and in no total would be exactly the silent
        # loss the docket exists to prevent.
        "n_candidates": len(cands) + len(idx.malformed) + len(unknown),
        "n_run": len(records), "n_refused": len(refused),
        "n_values_malformed": len(idx.malformed),
        # A MALFORMED VARIABLE IS NOT A CANDIDATE, AND IT IS NOT NOTHING EITHER.
        # It is not added to `n_candidates` -- the values that named it still
        # form candidates and refuse `no_variable` -- but a variable we passed
        # over must be distinguishable from one that is not there, so it is
        # counted here and named in `variables_malformed`.
        "n_variables_malformed": len(idx.malformed_variables),
        "variables_malformed": idx.malformed_variables,
        "by_family": by_family,
        "by_severity": dict(sorted(
            {s: sum(1 for r in records if r["severity"] == s)
             for s in {r["severity"] for r in records}}.items(), key=lambda kv: str(kv[0]))),
        "refused_by_reason": dict(sorted(
            {r["reason"]: sum(1 for x in refused if x["reason"] == r["reason"])
             for r in refused}.items())),
        "checks": records,
        "refused": refused,
        "census_vs_bridge": _census_safely(account, idx, cands, outcome),
        # THE CHECKS THIS BRIDGE DOES NOT MAKE, AND HOW MANY THERE WOULD BE.
        # Every other total here counts something the bridge considered; this
        # one counts what it never looked at, which is the only number that
        # could have said "the registry holds 62 tools and 5 are called" without
        # a session going and counting by hand.
        "tools_not_wired": _unwired_safely(idx),
        "reason_vocabulary": {k: {"premise": v[0], "means": v[1]}
                              for k, v in sorted(REASONS.items())},
    }


def run(out_dir: str | Path, families: tuple[str, ...] | None = None) -> dict:
    """Read the account and the structure off disk, check, and write the sidecar.

    THE SIDECAR IS THE WHOLE OUTPUT. Nothing is written back into
    `account.json`: the account is the paper's own description and a verdict is
    not part of it, so a reader can delete every check and lose nothing that was
    extracted.
    """
    out = Path(out_dir)
    raw = (out / "account.json").read_bytes()
    account = json.loads(raw.decode("utf-8"))
    body = out / "body.repaired.md"
    text = body.read_text(encoding="utf-8") if body.is_file() else ""
    # THE PRESENCE IS READ BEFORE THE FILE IS PARSED, because `structure.load`
    # raises on a `structure.json` that is not JSON while `structure.presence`
    # answers `empty` for it -- and a truncated write is exactly how a structure
    # file ends up unreadable. A named refusal is the honest form of the same
    # fact; a traceback out of `run` writes no `checks.json` and says nothing.
    present = _structure.presence(out)
    struct = _structure.load(out) if present == "present" else None

    # THE VERSION STAMP IS CHECKED BEFORE ANYTHING RUNS. An account assembled
    # from one vocabulary and a structure holding another cannot both be right
    # about a variable's bounds, and a check that read the wrong one would be a
    # verdict about a paper nobody described.
    #
    # AND IT IS A PRESENCE TEST, NOT ONLY A DISAGREEMENT TEST. `require` is on
    # wherever there is a structure to be right or wrong about -- one on disk,
    # or an account that names one -- so an absent, empty or null stamp refuses
    # by name instead of passing as agreement. A structureless account (no
    # `structure.json`, no stamp claimed) is a different thing and still runs:
    # it names no structure, so there is none to have mixed.
    expected = _structure.content_sha256(struct) if struct else None
    stamps = {"account.json (provenance)":
              (account.get("provenance") or {}).get("structure_sha256"),
              "account.json (structure block)":
              (account.get("structure") or {}).get("sha256")}
    claims_one = bool((account.get("provenance") or {}).get("structure_sha256")
                      or account.get("structure"))
    # AN EMPTY `structure.json` IS A THIRD STATE AND IT WAS BEING READ AS THE
    # FIRST. `structure.presence` was added to distinguish "no file" from "a file
    # with nothing in it", and the gate below still keyed on `expected`, which is
    # None for BOTH -- so a directory holding `{}` beside an account claiming
    # `deadbeef...` ran every check, and the only correction was that
    # `checks.json` stopped printing the fabricated sha256 as the structure it
    # had verified against. A stamp naming a structure that is not on disk is an
    # unproven premise whichever way the file is empty, so `require` is on for
    # `empty` exactly as it is for a structure that IS there.
    if present == "empty":
        raise _structure.StructureMismatch(
            "`structure.json` is present and holds no structure, so nothing on disk "
            "hashes to the stamp these artifacts carry"
            + ("; " + ", ".join(f"{k} -> {str(v)[:12]}" for k, v in sorted(stamps.items()) if v)
               if claims_one else "; and no artifact names one either"))
    _structure.refuse_mixed_versions(stamps, expected, require=bool(expected) or claims_one)

    got = evaluate(account, text, families)
    got = {
        **got,
        "paper": {"doi": (account.get("paper") or {}).get("doi"),
                  "title": (account.get("paper") or {}).get("title")},
        "structure_version": (struct or {}).get("version"),
        "structure_status": (struct or {}).get("status"),
        # THE ARTIFACT NAMES WHAT IT VERIFIED AGAINST, AND NOTHING ELSE. It used
        # to fall back to the account's own stamp, so a run with an EMPTY
        # `structure.json` beside an account claiming `deadbeef...` printed
        # `deadbeef...` as the structure it had checked -- a sha256 nothing on
        # disk was ever hashed to. Absent is now `null`, which is the honest
        # answer, and `structure_present` says which of the three states the
        # directory was in.
        "structure_sha256": expected,
        "structure_present": present,
        "account_sha256": hashlib.sha256(raw).hexdigest(),
        "code": _codestamp.stamp(),
    }
    (out / "checks.json").write_text(
        json.dumps(got, indent=1, ensure_ascii=False, sort_keys=False), encoding="utf-8")
    (out / "checks.md").write_text(render_markdown(got), encoding="utf-8")
    return got


# --------------------------------------------------------------------------
# The reader's view
# --------------------------------------------------------------------------


def _short(v: Any, n: int = 60) -> str:
    s = " ".join(str(v if v is not None else "").split())
    return (s[: n - 1] + "…") if len(s) > n else s


def _denominator(record: dict) -> str:
    """The n a check used, and where the bridge got it.

    A DENOMINATOR WITHOUT ITS PROVENANCE IS HALF A FACT. The same 64 can be the
    group's own printed n, a study-level figure the sentence says applies to
    every group, or the number parsed out of the declared group's label; a
    reader checking a percentage against the paper needs to know which.
    """
    rec = record.get("premises", {}).get("n") or {}
    n = rec.get("n")
    if n is None:
        return "--"
    where = rec.get("source") or "?"
    declared = rec.get("declared_group_n")
    if declared is not None:
        where += f", agreeing with the group label's {declared} " \
                 f"({rec.get('declared_group_n_source')})"
    return f"{n} ({where})"


def render_markdown(checks: dict) -> str:
    """The checks as a reader sees them: what ran, what it said, what did not
    run and which premise was missing."""
    L: list[str] = []
    L.append(f"{checks['n_candidates']} candidate check(s) on this account's own premises; "
             f"**{checks['n_run']} ran**, {checks['n_refused']} refused for a named missing "
             "premise. Every call went through the tool registry, so every registry gate "
             "(coercion, non-finite input, measured provenance, missing printed precision) "
             "applied; every verdict below is the tool's own word, copied and never "
             "re-severitied.")
    L.append("")
    L.append("| family | tool | candidates | run | verdicts | refused (first missing premise) |")
    L.append("|---|---|---:|---:|---|---|")
    for fam, d in checks["by_family"].items():
        verdicts = ", ".join(f"{k}: {v}" for k, v in d["by_severity"].items()) or "--"
        refused = ", ".join(f"{k}: {v}" for k, v in
                            sorted(d["refused_by_reason"].items(), key=lambda kv: -kv[1])) or "--"
        L.append(f"| {fam} | `{d['tool']}` | {d['candidates']} | {d['run']} | "
                 f"{verdicts} | {refused} |")
    L.append("")
    # WHAT IS NOT CHECKED AT ALL, printed beside what is. The table above is a
    # complete account of the five families the bridge wires and says nothing
    # about the other fifty-seven tools in the registry, so a reader could take
    # "0 ran" for "nothing here is checkable" when the truer sentence is
    # narrower: one premise is missing, and the tool that needs it exists.
    not_wired = [r for r in (checks.get("tools_not_wired") or [])
                 if r.get("population_in_this_account")]
    if not_wired:
        L.append("### Checks this bridge does not make")
        L.append("")
        L.append("Registry tools whose inputs this account DOES carry, and the premise that "
                 "stops each being wired. The counts are this account's, computed from it; "
                 "every one is the size of a refusal and not a promise of checks.")
        L.append("")
        L.append("| tool | population here | blocked on | why |")
        L.append("|---|---:|---|---|")
        for r in not_wired:
            L.append(f"| `{r['tool']}` | {r['population_in_this_account']} | "
                     f"`{r['blocked_on']}` | {r['why']} |")
        L.append("")
    if checks["checks"]:
        L.append("### What ran")
        L.append("")
        L.append("| check | tool | variable | inputs | denominator | verdict |")
        L.append("|---|---|---|---|---|---|")
        for r in checks["checks"]:
            args = {k: v for k, v in r["args"].items()
                    if k not in ("source_quote", "source_locator")}
            L.append(f"| `{r['check_id']}` | `{r['tool']}` | "
                     f"`{r['variable_id'] or '--'}` | {_short(args, 100)} | "
                     f"{_denominator(r)} | "
                     f"**{r['severity']}** {_short(r['result'].get('failure_mode') or '', 30)} |")
        L.append("")
        # THE QUESTION A NON-CONSISTENT RECORD RAISES, printed rather than left
        # in the JSON. The n bound here is the GROUP's; the n analysed for one
        # outcome is routinely smaller, and that is the direction that
        # manufactures a granularity failure.
        asks = [r for r in checks["checks"]
                if (r["premises"].get("n") or {}).get("n_that_would_fit")]
        if asks:
            L.append("Denominators near the one used that would have fitted -- "
                     "a question for the authors, never a rescue:")
            L.append("")
            for r in asks:
                n_rec = r["premises"]["n"]
                L.append(f"- `{r['check_id']}`: n = {n_rec.get('n')} was used; "
                         f"{r['args'].get('mean')} is consistent at n = "
                         + ", ".join(str(x) for x in n_rec["n_that_would_fit"]) + ". "
                         + str(n_rec.get("n_that_would_fit_note") or ""))
            L.append("")
        # THE TWO READINGS OF ONE LITERAL, WHERE THEY DISAGREE. The account's
        # `numeric`/`decimals` and the bridge's strict grammar are deliberately
        # two implementations of one rule ("a check that inherits the reader it
        # is checking proves nothing"), and the comparison was computed on every
        # record and shown on none: a cell the account read as 35.0 and the
        # bridge as 3.5 produced a verdict, and `checks.md` said nothing at all.
        # A disagreement does not decide which reading is right, and it is the
        # reader's business either way.
        rows = [(r, lit) for r in checks["checks"]
                for lit in (r["premises"].get("literals") or [])
                if isinstance(lit, dict) and lit.get("agrees") is False]
        if rows:
            L.append("The account and the bridge disagree about how to read these printed "
                     "literals (`agrees: false`). The verdict above used the bridge's "
                     "reading; the disagreement is not resolved here, and either reading "
                     "being wrong would change the call:")
            L.append("")
            L.append("| check | value | printed | bridge_value | account_numeric |")
            L.append("|---|---|---|---|---|")
            for r, lit in rows:
                L.append(f"| `{r['check_id']}` | `{lit.get('value_id')}` | "
                         f"`{_short(lit.get('printed'), 20)}` | "
                         f"{lit.get('bridge_value')} ({lit.get('bridge_decimals')} dp) | "
                         f"{lit.get('account_numeric')} ({lit.get('account_decimals')} dp) |")
            L.append("")
    if checks.get("n_values_malformed"):
        L.append(f"{checks['n_values_malformed']} value(s) could not be read as values at "
                 "all and were skipped; they are in the docket below under "
                 "`value_malformed`.")
        L.append("")
    if checks.get("n_variables_malformed"):
        L.append(f"{checks['n_variables_malformed']} variable(s) could not be read as "
                 "variables at all (an `id` that cannot be part of an index key) and were "
                 "skipped; every value bound to one of them refuses `no_variable`: "
                 + "; ".join(f"`{v.get('id')}` ({v.get('why')})"
                             for v in (checks.get("variables_malformed") or [])[:5]))
        L.append("")
    L.append("### The docket: candidates that did not run")
    L.append("")
    if not checks["refused"]:
        L.append("None.")
    else:
        L.append("A refusal is a statement about what the paper does not print, or about "
                 "what this account does not yet carry -- never about the paper's honesty. "
                 "Only a structural adjudication or a re-read can discharge one; the bridge "
                 "never fills any of it.")
        L.append("")
        # ONE WORKED EXAMPLE PER REASON, AND IT IS THE HALF A READER CAN ACT ON.
        # The table said what the reason MEANS -- the closed vocabulary's own
        # sentence, identical on every paper -- and never what THIS paper said to
        # earn it. So `mean_is_not_a_simple_average` read as an assertion about
        # nothing in particular, when the detail behind it is the paper's own
        # words ("the value's own sentence says 'survey-weighted mean'") and the
        # candidate they were read from. Capped at one example per reason so the
        # docket stays a summary: a run refusing 111 candidates prints 111 rows
        # nobody reads.
        example: dict[str, tuple[str, str]] = {}
        for row in checks["refused"]:
            for r in row.get("reasons") or []:
                if r["reason"] not in example and r.get("detail"):
                    example[r["reason"]] = (str(row.get("check_id") or ""),
                                            str(r.get("detail") or ""))
        L.append("| reason | n | means | for example |")
        L.append("|---|---:|---|---|")
        for reason, n in sorted(checks["refused_by_reason"].items(), key=lambda kv: -kv[1]):
            cid, detail = example.get(reason, ("", ""))
            shown = f"`{cid}`: {_short(detail, 140)}" if detail else "--"
            L.append(f"| `{reason}` | {n} | {REASONS.get(reason, ('', '?'))[1]} | {shown} |")
        L.append("")
    tot = checks["census_vs_bridge"]["_totals"]
    L.append("### Census against bridge")
    L.append("")
    L.append(f"The read-only census (section 15) binds "
             f"{tot['census_bindable_coordinates']} coordinate(s); the bridge made "
             f"{tot['bridge_calls']} call(s). The units differ on purpose -- the census "
             "counts coordinates, the bridge counts values, and one coordinate can hold "
             "several count/percent pairs.")
    L.append("")
    L.append("| census family | bindable | coordinates run | not run, by reason |")
    L.append("|---|---:|---:|---|")
    for name, d in checks["census_vs_bridge"].items():
        if name.startswith("_"):
            continue
        nr = ", ".join(f"`{k}`: {v}" for k, v in d["not_run_by_reason"].items()) or "--"
        L.append(f"| {name} | {d['census_bindable']} | {d['coordinates_run']} | {nr} |")
    L.append("")
    return "\n".join(L)
