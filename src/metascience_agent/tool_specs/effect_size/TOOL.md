---
family: effect_size
implementation:
- metascience_agent.tools.effect_size
tools:
  check_effect_plausibility:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Places an effect size against cited field benchmarks; flags unusual, never impossible.
    assumptions:
    - Benchmarks carry a provenance label. Only social_psychology's percentiles trace to a published table (Lovakov & Agadullina 2021, Table 1); the rest are uncited estimates and say so in the result. psychology_general was WITHDRAWN 2026-08-16 -- its median came from an OSC 2015 correlation (r = .40) used as a Cohen's d, which is d ~ 0.87, so it flagged ordinary effects as large; naming it now returns a diagnosis rather than a comparison.
    - Field benchmarks are distributions of PUBLISHED effects, themselves inflated by publication bias.
    - Dispersion inputs must be SDs; an SEM read as an SD inflates d by sqrt(n).
    - d from group statistics assumes independent groups and pooled-SD standardisation.
    - An effect can be improbable but never impossible, so this caps at `suspicious`.
  paired_d_interval:
    evidence: descriptive
    consumes_table_cells: true
    purpose: Reports the attainable range of a within-subjects d_av when the correlation is unreported; never accuses.
    assumptions:
    - d_av = d_z * sqrt(2*(1-r)). The direction inverts easily and effectcheck 0.7.7 has it backwards; verified here against a 200,000-pair simulation with known r.
    - The r grid is a RANGE, not a prior. It says what is attainable and deliberately does not weight the interior, because weighting it would be the assumption this tool exists to refuse.
    - 'Returns d_rm (Lakens 2013 eq. 8), NOT d_av. They coincide only when the pre and post SDs are equal. MEASURED 2026-08-27, 300,000 pairs per cell: error against true d_av is 0.2% at equal SDs, 29.3% at sd2/sd1=2, 44.5% at 3. A card here asserted the inverse for one day.'
    - d_av additionally needs the SD RATIO, which this tool neither takes nor can infer from d_z and r. When the paper printed both SDs, `recalc_within_subjects_t` recovers r and the ratio is visible -- prefer that.
    - '`recalc_within_subjects_t` RECOVERS r when both SDs are printed and is strictly better; this is the fallback for when they are not.'
    - 'Descriptive by class: a wide interval is a fact about the reporting, not about the work, so it caps at `indeterminate` and can never accuse.'
---
# `effect_size` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_effect_plausibility

<!-- description:check_effect_plausibility -->
Compute an effect size and report it WITH A 95% CONFIDENCE INTERVAL. Takes the six group statistics (or a d directly) and returns Cohen's d, Hedges' g and an estimated CI. Reporting the value IS the deliverable. An effect far outside the usual range is informative and is NOT evidence of misconduct, and severity is capped at `suspicious` because an effect size can be improbable but never arithmetically impossible. `field` is OPTIONAL and usually omitted -- magnitude is REPORTED, not judged, because whether an effect is unrealistically large is a judgement for the reader with the paper's effects laid out as a set. PASS `reported_d` ALONGSIDE the group statistics to check INTERNAL CONSISTENCY instead: does the effect size the paper printed match the one its own means, SDs and ns imply? That needs no comparison class and is what catches a mistyped effect size. Supplying `field` additionally places the value against field benchmarks, which are mostly uncited estimates and say so. THIS IS THE CHECK THAT WORKS ON FIGURE-DERIVED DATA: gross implausibility survives digitization error (verified -- the verdict is unchanged across the full +/-37% dispersion error range), so a paper reporting its outcome ONLY as a bar chart becomes checkable here even though GRIM/GRIMMER/SPRITE cannot touch it. Pass provenance='figure_pixels' when the inputs were read off a chart. Before treating a large effect as a finding, rule out the three ordinary causes: dispersion reported as SEM and read as SD (inflates d by sqrt(n)), a waitlist rather than active comparator, and a units mismatch. Parameters: d (optional), field, mean1, sd1, n1, mean2, sd2, n2, design, provenance
<!-- /description:check_effect_plausibility -->

## paired_d_interval

<!-- description:paired_d_interval -->
What a WITHIN-SUBJECTS effect size could be, when the pre-post correlation is not reported. A paired design reports d_z -- the difference over the SD OF THE DIFFERENCES -- and a reader comparing it against a between-subjects literature wants a raw-SD effect size. This returns d_rm (Lakens 2013 eq. 8): d_rm = d_z * sqrt(2*(1-r)). It is NOT d_av, which also needs the SD ratio this tool does not take -- they differ by up to 44% at unequal SDs. Papers reporting d_z almost never report r. USE `recalc_within_subjects_t` FIRST: when the pre and post SDs are both printed it RECOVERS r, which is strictly better than this. Use this only when they are not, and then quote the INTERVAL rather than a point -- picking r = 0.5 silently is an unstated assumption doing the work of a measurement. Note the direction, which is easy to invert: d_rm SHRINKS as r rises, because a high correlation makes the paired test efficient, so d_z is large while the raw-SD effect is not. Returns d_rm_low, d_rm_high, the value at each r on the grid, and the high/low ratio -- typically over 4x, which is how much the paper left unsaid. DESCRIPTIVE: it reports a property of what was printed and can never accuse. A wide interval is a fact about the reporting, not about the work. Parameters: dz (or t with n), r (optional, if the paper reports it)
<!-- /description:paired_d_interval -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:19 -->
   - `check_effect_plausibility` — Cohen's d, Hedges' g and a 95% CI from the six
     group statistics. `field` is OPTIONAL and usually omitted: the value and its
     interval are the deliverable, and a reader with the paper's effects laid out
     as a set judges magnitude better than a benchmark table can. Pass
     `reported_d` to check the paper's printed effect size against the one its
     own means, SDs and ns imply. An effect far outside the usual range is NOT
     evidence of misconduct and is capped at `suspicious`. Rule out first:
     dispersion reported as SEM and read as SD (inflates d by sqrt(n)), a
     waitlist rather than active comparator, and a units mismatch.
<!-- /guidance:19 -->
