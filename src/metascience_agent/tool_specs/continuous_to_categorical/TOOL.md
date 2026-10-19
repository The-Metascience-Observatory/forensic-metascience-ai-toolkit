---
family: continuous_to_categorical
implementation:
- metascience_agent.tools.continuous_to_categorical
tools:
  check_proportion_from_normal:
    evidence: probabilistic
    consumes_table_cells: true
    purpose: Tests a categorical proportion against the reported continuous mean and SD.
    assumptions:
    - The headline test assumes the RAW variable is normal; skew explains a mismatch innocently, so it caps at `suspicious`.
    - '`highly_suspicious` needs a distribution-free violation -- Cantelli''s bound, which holds for EVERY distribution.'
    - Independent observations (binomial sampling of the count at the threshold).
    - The proportion and the mean/SD/n must describe the same sample.
---
# `continuous_to_categorical` tools

The frontmatter holds each tool's integrity card: its evidence class, purpose and assumptions (`registry.TOOL_INTEGRITY`). Each block below is the tool's MCP description, the text the model is shown, exactly as sent. Parameters and guards are in `spec.py`.

## check_proportion_from_normal

<!-- description:check_proportion_from_normal -->
Continuous→categorical plausibility (Heathers §'continuous to categorical transforms'): given a normal-assumed (mean, sd, n) and a reported categorical proportion at a threshold, test whether the proportion is consistent with the continuous distribution via a binomial test. Direction is 'below' (P(X<threshold)) or 'above' (P(X>threshold)). Parameters: reported_proportion (0..1), mean, sd, n, threshold, direction (default 'below'), num_simulations (default 10000), seed (default 0)
<!-- /description:check_proportion_from_normal -->
