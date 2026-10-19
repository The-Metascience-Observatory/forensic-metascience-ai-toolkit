---
family: r_wrappers
implementation:
- forensic_metascience_ai_toolkit.tools.r_wrappers
tools:
  r_grim_ground_truth:
    evidence: descriptive
    consumes_table_cells: true
    purpose: Cross-checks our GRIM against R's canonical scrutiny package.
    assumptions:
    - Reports R's verdict. A disagreement between engines means OUR tooling is wrong; it is never evidence about the paper.
  r_sprite_ground_truth:
    evidence: descriptive
    consumes_table_cells: true
    purpose: Cross-checks our SPRITE against R's canonical rsprite2 package.
    assumptions:
    - Reports rsprite2's result. A disagreement is a bug in our tooling and the finding must not be reported.
  statcheck:
    evidence: probabilistic
    consumes_table_cells: false
    purpose: Extracts APA-style results and recomputes their p-values for internal consistency.
    assumptions:
    - Each p is recomputed assuming a two-tailed, unadjusted test.
    - Only APA-formatted results are extracted; everything else is invisible to it.
    - A p correct at its own printed precision is not an error.
    - Inconsistencies are near-universal in honest work and must never support a misconduct verdict alone.
---
# `r_wrappers` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## r_grim_ground_truth

<!-- description:r_grim_ground_truth -->
Run GRIM via R's canonical `scrutiny` package. Use to CROSS-CHECK a grim_check result before reporting an anomaly. Disagreement between engines means our tooling is wrong, not the paper. ASK IT THE SAME QUESTION YOU ASKED THE PYTHON TOOL, or it is not a cross-check. Checking a `grim_percentage` finding? Pass percentage=true and the SAME percentage you gave grim_percentage -- not the number divided by 100, and not the percentage as a `mean`. MEASURED: a 28% share at n=41 that grim_percentage calls impossible comes back `consistent` if you pass it as mean=28, because R is then correctly answering "can 41 integers average 28?" (they can: 28*41 = 1148). The share question -- is 28% a possible k/41? -- is no: 11/41 = 26.83, 12/41 = 29.27. A cross-check that quietly answers an easier question reads as exoneration. The reply carries `asked_as` so you can see which question was answered; quote it in `notes`. Parameters: mean (the mean, or the percentage if percentage=true), n, items (default 1), decimals (default 2, the printed precision), percentage (bool, default false)
<!-- /description:r_grim_ground_truth -->

## r_sprite_ground_truth

<!-- description:r_sprite_ground_truth -->
Run SPRITE via R's canonical `rsprite2` package. Use this to CROSS-CHECK a sprite_reconstruct result before reporting it -- especially any 'no solution' claim. If the two engines disagree, that is a bug in our tooling, NOT evidence about the paper, and the finding must not be reported. Returns infeasible=true when rsprite2 PROVES no such sample exists. Parameters: mean, sd, n, scale_min, scale_max, num_samples, decimals (reported precision)
<!-- /description:r_sprite_ground_truth -->

## statcheck

<!-- description:statcheck -->
Run statcheck to extract and verify NHST statistical tests (t-tests, F-tests, correlations, chi-squared, z). Recalculates each p-value from the statistic and its degrees of freedom. Provide EITHER pdf_path OR text, not both. PASS pdf_path, OR THE WHOLE EXTRACTED TEXT -- never a paragraph you picked out. This tool only sees the characters you hand it, so a hand-chosen snippet makes the coverage number a fact about your paste and not about the paper, and a statistic you did not paste is reported as absent rather than as unchecked. IT NEEDS FULL APA FORM: the statistic, its df in parentheses, and the p together -- "F(2, 33) = 5.76, p = .008". A paper that prints F and p with NO df (common in some journals) yields zero here, which is a fact about the FORMAT, not the paper; use recalc_f_to_p / recalc_stat_to_p on those instead, which sweep the unstated df. READ THE RESULT CAREFULLY: `errors_flagged_upstream` counts raw statcheck flags, `errors_explained_by_rounding` are p-values correct at their own printed precision and are NOT errors, and `errors_found` is what is left. Only `decision_errors` (a p on the wrong side of its own alpha) change a conclusion; plain inconsistencies are near-universal in honest work. Parameters: pdf_path (str, optional), text (str, optional - raw text/markdown to check)
<!-- /description:statcheck -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:09 -->
   - `statcheck` — run once over the body text for APA-style statistics.
<!-- /guidance:09 -->
