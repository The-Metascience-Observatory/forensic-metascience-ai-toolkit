---
family: grimu
implementation:
- forensic_metascience_ai_toolkit.tools.grimu
tools:
  grimu_check:
    evidence: absolute
    consumes_table_cells: true
    purpose: Checks a Mann-Whitney p against the finite set achievable at these group sizes.
    assumptions:
    - The p must genuinely come from a Mann-Whitney U / Wilcoxon rank-sum test at these group sizes.
    - The achievable set spans the normal approximation with and without continuity correction, plus the exact permutation p.
    - 'KNOWN LIMITATION: the TIE-CORRECTED variance that scipy and R use on tied data is NOT in that set, so a correctly reported p from tied data can fall below the modelled floor. Treat an `impossible` verdict on data with heavy ties as unproven until checked against the R implementation.'
    - Pass one_sided for one-tailed reports. `decimals` is read from the printed literal; from a bare float it falls back to that float's shortest round-tripping decimal form, which is a LOWER bound on the printed precision, so the interval can only widen. A float carrying float-noise precision is refused rather than guessed at.
  grimu_coexistence:
    evidence: absolute
    consumes_table_cells: true
    purpose: Flags near-identical Mann-Whitney p-values that cannot all arise at these group sizes.
    assumptions:
    - All the p-values must come from Mann-Whitney tests on the SAME group sizes.
    - Pass one_sided if the paper reports one-tailed tests; forcing the two-sided set manufactures accusations.
    - 'Same tie-correction limitation as grimu_check: heavy ties can put an honest p outside the modelled set.'
---
# `grimu` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## grimu_check

<!-- description:grimu_check -->
GRIM-U: check whether a p-value from a Mann-Whitney U / Wilcoxon rank-sum test is achievable given the group sizes. The U statistic is (half-)integer in [0, n1*n2], so only a finite set of p-values is possible. ONLY apply to p-values a paper attributes to a Mann-Whitney/Wilcoxon test with known group sizes n1, n2 — NEVER to t-test/ANOVA/chi-squared/regression p-values. Best at 3 decimals and small groups (per-group n <~15). Verdicts: impossible = below the U=0 floor; suspicious = between achievable granular values; consistent = some achievable U reproduces it. reported_p accepts a number or a string like '<0.001'. test_type must be mann_whitney or wilcoxon (default mann_whitney); a t / F / chi-squared / ANOVA p is REFUSED as indeterminate, not scored. TWO MORE PRECONDITIONS, AND YOU MUST SUPPLY THEM. (1) If the paper prints a normal-approximation Z beside the p -- 'Z = 1.219, p = .223', which is how SPSS reports Mann-Whitney -- PASS IT as reported_z. That p is a function of the ROUNDED Z, not of U, so the U lattice does not constrain it and the check refuses. (2) If the outcome is a small-integer or ordinal scale, ranks TIE, the tie-corrected sdU is smaller than the untied one, and every achievable p moves: pass ties_possible=true and the granularity branch refuses (the below-floor branch still runs, since ties cannot push U below 0). Skipping either produced two published severity-2 findings against an honest paper. Parameters: n1 (int), n2 (int), reported_p (number or str), decimals (int, inferred if omitted), continuity_correction ('none'|'cc'|'both', default 'both'), method ('normal'|'exact'|'both', default 'normal'), one_sided (bool, default false), test_type (str, default 'mann_whitney'), reported_z (float, the printed Z if there is one), p_source ('u_statistic'|'normal_z'|'unspecified'), ties_possible (bool)
<!-- /description:grimu_check -->

## grimu_coexistence

<!-- description:grimu_coexistence -->
GRIM-U co-existence: given several p-values from Mann-Whitney/Wilcoxon tests on the SAME group sizes n1, n2, flag minimally-differing p-values that cannot both arise from achievable U's (e.g. 0.171 vs 0.172 at n=8v8 — one maps to a U, the other falls in a gap). Same applicability rule as grimu_check (rank-sum tests only). PASS `one_sided` if the paper reports one-sided tests -- the achievable p-value set differs, and forcing a one-sided table onto the two-sided set manufactures accusations. The two preconditions grimu_check names apply here too and void this heuristic the same way: pass ties_possible=true for a small-integer or ordinal outcome, and p_source="normal_z" when the paper printed Z values rather than U. Parameters: n1 (int), n2 (int), p_values (list of numbers/strings), decimals (int, optional), continuity_correction (str, default 'both'), method (str, default 'normal'), one_sided (bool, default false), test_type (str, default 'mann_whitney'), p_source (str), ties_possible (bool)
<!-- /description:grimu_coexistence -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:23 -->
   - `grimu_check` / `grimu_coexistence` — p-values from a **Mann-Whitney U /
     Wilcoxon rank-sum test with known group sizes n1, n2 ONLY**. Do NOT apply
     to t-test, ANOVA, χ², or regression p-values — the granularity argument is
     specific to rank-sum tests (this is the top false-accusation risk; the
     tool can't see the test type, so you must gate it). Use only when the paper
     attributes the p to Mann-Whitney/Wilcoxon (methods text, table footnote, or
     a reported "U="/"W="). Best on p at 3 decimals from small groups (per-group
     n ≲ 15); above that granularity vanishes and it returns `consistent`. When
     two or more non-significant p-values share the same n and differ minimally
     (e.g. 0.171 vs 0.172), run `grimu_coexistence`. **Pass `reported_z` when
     the paper prints a Z beside the p** (`Z = 1.219, p = .223` — SPSS's
     Mann-Whitney output): that p is the rounded Z's, not U's, and the check
     refuses. **Pass `ties_possible=true` for a small-integer or ordinal
     outcome**: ranks tie, the tie correction shrinks sdU, and the untied
     lattice stops describing the achievable p's. Both apply to
     `grimu_coexistence` too.
<!-- /guidance:23 -->
