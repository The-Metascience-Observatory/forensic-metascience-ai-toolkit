---
family: se_sd
implementation:
- forensic_metascience_ai_toolkit.tools.se_sd
tools:
  check_sd_or_se:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Adjudicates whether a reported dispersion value is an SD or a mislabelled SE.
    assumptions:
    - SD and SE are linked by SE = SD/sqrt(n); n must be the cell's true denominator.
    - A 'neither reading fits' verdict rests ENTIRELY on the plausibility ceiling implied by the variable's range.
    - A ceiling from an ASSUMED bound caps at `suspicious`; only a stated bound licenses `highly_suspicious`.
    - Under the SE reading the rounding interval stretches by sqrt(n).
    - 'BASE RATE: mislabelling SE as SD is the norm, not an outlier. Olsen (2002) found 35 of 88 studies (40%) reporting the SEM where they said SD. Heathers (2025): ''usually an honest mistake of statistical ignorance, not anything that implies a problem with research integrity.'' Report it as a reporting defect; it moves what the numbers MEAN, not what the authors did.'
---
# `se_sd` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_sd_or_se

<!-- description:check_sd_or_se -->
SD/SE confusion check: when a paper reports a dispersion value but you suspect it may have confused SD and SE (linked by SE = SD/sqrt(n)), this returns both interpretations and adjudicates them against a plausibility ceiling. Provide either plausible_sd_max or variable_range (preferred when known). reported_as is one of 'SD', 'SE', or 'unknown'. Parameters: reported_value (float), n (int), reported_as (str, default 'unknown'), plausible_sd_max (float, optional), variable_range_min (float, optional, supply with _max), variable_range_max (float, optional). PASS `decimals` -- the PRINTED precision of reported_value. The value asserts a rounding interval, and under the SE reading that interval is stretched by sqrt(n), so at n = 100 a value printed to one decimal carries plus or minus 0.5 of implied SD. Without it the ceiling gets a flat 1% margin, which is a guess and is the wrong size in both directions. ALSO pass bound_source: 'stated' if the PAPER gives the range/ceiling, 'logically_necessary' if it follows from the quantity itself (a proportion is in [0,1]), or 'assumed' (default) if YOU supplied it -- a 'neither reading fits' verdict rests ENTIRELY on that ceiling, so against an assumed bound it caps at 'suspicious'; only a hard bound licenses 'highly_suspicious' (rulebook rule 4, same as grim_check).
<!-- /description:check_sd_or_se -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:10 -->
   - `check_sd_or_se` — dispersion plausibility.
<!-- /guidance:10 -->
