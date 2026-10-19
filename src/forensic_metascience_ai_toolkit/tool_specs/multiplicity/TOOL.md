---
family: multiplicity
implementation:
- forensic_metascience_ai_toolkit.anatomy
tools:
  multiplicity_report:
    evidence: descriptive
    consumes_table_cells: false
    purpose: Reports the family-wise error rate and four correction thresholds for a declared family.
    assumptions:
    - Everything is conditional on the DECLARED family; the same p-values give different answers under different families.
    - FWER-if-independent is an upper bound when outcomes are correlated; survivor counts are a bound across four methods.
    - Undisclosed analytic flexibility means the true comparison count can exceed the reported one, so this is a floor.
---
# `multiplicity` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## multiplicity_report

<!-- description:multiplicity_report -->
Multiple-comparisons arithmetic for a FAMILY of tests: family-wise error rate, four correction thresholds (Bonferroni, Holm, Benjamini-Hochberg, Benjamini-Yekutieli), and -- the number that matters -- how many results significant uncorrected FAIL to survive correction (`n_claims_lost_to_correction`). Use whenever a paper reports several tests with no stated correction. This is DETERMINISTIC ARITHMETIC, not a judgement about the authors: uncorrected testing is ordinary in most literatures, and the output is a statement about what the numbers imply, not an accusation. HOW MANY RESULTS SURVIVE IS A BOUND, NOT ONE NUMBER: `n_surviving_floor` and `n_surviving_ceiling` span the four methods, because the answer depends on whether the family needs family-wise control (Bonferroni, Holm) or false-discovery-rate control (Benjamini-Hochberg; Benjamini-Yekutieli once the outcomes are correlated, which is the normal case when several measures come from the same subjects). Report the interval, not one convenient method. `n_claims_lost_to_correction` is read off Benjamini-Hochberg, the most permissive, so it is the SMALLEST loss these corrections support. WHAT COUNTS AS A FAMILY IS YOUR CALL and the tool cannot make it -- `family_label` is MANDATORY and has no default; omit it and the tool REFUSES rather than pooling the paper. Run it once per family rather than lumping every test in the paper together. Tests the authors already corrected are excluded automatically. Tests whose p is reported as a threshold ('p < .05') are dropped rather than coerced, and counted in the output. FWER assumes independence and is therefore an UPPER bound; correlated outcomes inflate it. Undisclosed analytic flexibility means the true comparison count can exceed the reported one, so this is a FLOOR on the multiplicity problem. Parameters: tests (list of {p_value, correction_applied, id, test_type, location, p_is_threshold}), family_label (str, REQUIRED), alpha (default 0.05)
<!-- /description:multiplicity_report -->

## Guidance

The tools agent's procedure for these tools (its step 3, assembled into `tool_expert.md` in the order the numbers give). Sent to the model as part of the system prompt; edit it here.

<!-- guidance:24 -->
   - `multiplicity_report` — a FAMILY of tests reported with no stated
     correction. Run it once per family and name the family; `family_label` is
     mandatory and the tool refuses without it. What counts as a family:
     - Post-hoc tests inside a significant omnibus ARE one family — the six
       pairwise contrasts following a significant ANOVA F, the cells of one
       interaction probe.
     - Several outcomes measured on the SAME subjects for the same hypothesis
       ARE one family. Quote the Benjamini-Yekutieli count for these: BH's
       guarantee assumes a dependence structure correlated outcomes need not
       have.
     - Separate studies are usually NOT one family, and neither are tests
       answering unrelated questions. Pooling them inflates m and manufactures
       a result that survives nothing.
     - A single planned confirmatory test needs NO correction. Do not run this
       on one hypothesis tested once.
     Report the surviving-claims interval (`n_surviving_floor` to
     `n_surviving_ceiling`), not one method's count, and say which method you
     are quoting.
<!-- /guidance:24 -->
