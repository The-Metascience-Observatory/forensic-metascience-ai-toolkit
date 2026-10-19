"""
STALT Check (Smaller Than A Lowest Threshold)

Check whether a p-value reported only as a threshold is consistent with the
recomputed exact p-value.

DIRECTION OF THE CHECK. "p < .001" claims exactly one thing: the p-value is
below .001. A recomputed p of 1e-15 SATISFIES that claim -- thresholds are
style-mandated FLOORS (APA style requires "p < .001" for ANY p below .001,
and journals routinely forbid printing smaller exact values), so a true p far
below the threshold is correct reporting, not a finding. The earlier version
keyed severity on how many orders of magnitude the true p sat BELOW the
threshold: every large test statistic correctly reported as "p < .001" came
back `highly_suspicious` (measured: stalt_check(1e-15, '<0.001') ->
highly_suspicious, and t(198) = 9.0 gives p = 1.9e-16, whose only
style-compliant rendering IS 'p < .001'), while the actual violation -- a
recomputed p ABOVE the printed bound, stalt_check(0.04, '<0.001') -- came
back `consistent`: a false all-clear on the one thing the printed claim rules
out. The check is now one-sided in the direction the claim actually has.
"""

import math

from .rounding import EPSILON


def stalt_check(
    calculated_p: float,
    reported_threshold: str = "<0.05",
) -> dict:
    """
    Check a recomputed p-value against the threshold it was reported as.

    A reported threshold "p < T" is an upper-bound CLAIM, so the check is
    one-sided:

    * calculated_p <= T: `consistent`, however far below T. "< .001" is a
      style floor; any large t/F legitimately produces p = 1e-15, and that is
      correctly reported as "< .001".
    * calculated_p > T: the printed claim is contradicted. Severity scales
      with the overshoot: within a factor of 2 a one-tailed p read as
      two-tailed would explain it on its own (`indeterminate`); beyond that
      `suspicious`; beyond 10x `highly_suspicious`.

    Every parseable form ("<0.05", "p < 0.001", "≤0.05", "=0.05", "0.05") is
    treated as the same upper-bound claim: the parameter is declared BY THE
    CALLER to be how the p was thresholded in print. Checking an exact printed
    p-value against a recomputation is the recalc tools' (`_p_matches`) job,
    not this tool's.

    Args:
        calculated_p: The recomputed exact p-value
        reported_threshold: How the p-value was reported (e.g., "<0.05", "<0.001")

    Returns:
        Dictionary with STALT analysis
    """
    # Parse the threshold: accept forms like "<0.05", "p < 0.001", "≤0.05",
    # "=0.05", "0.05".
    cleaned = (
        reported_threshold.strip()
        .lower()
        .lstrip("p")
        .strip()
        .lstrip("<≤=")
        .strip()
    )
    try:
        threshold_value = float(cleaned)
    except ValueError:
        return {
            "error": f"Could not parse threshold: {reported_threshold!r}",
            "severity": "indeterminate",
        }
    if not (0 < threshold_value <= 1):
        return {
            "error": f"Threshold must be in (0, 1] (got {threshold_value})",
            "severity": "indeterminate",
        }
    if isinstance(calculated_p, bool) or not isinstance(calculated_p, (int, float)):
        # A bool, a string or a None here is a JSON/parsing artefact of OURS,
        # never a recomputed p. `True` coerces to 1.0 and previously sailed
        # through to `highly_suspicious`; a string raised. Both now decline.
        return {
            "error": (
                f"calculated_p must be a number (got {calculated_p!r})"
            ),
            "severity": "indeterminate",
        }
    if not math.isfinite(calculated_p) or calculated_p < 0 or calculated_p > 1:
        # A NaN here is OUR extraction/recomputation failing, never the
        # author's arithmetic. The registry's non-finite gate already refuses
        # it on the MCP path; this keeps a direct call from judging it either
        # (it previously fell through to `highly_suspicious`).
        return {
            "error": (
                f"calculated_p must be a finite value in [0, 1] (got {calculated_p})"
            ),
            "severity": "indeterminate",
        }

    # Informational: how far below the threshold the true p sits. Kept for the
    # CLI and the explanation; it no longer drives severity, because sitting
    # far below a "<" bound is exactly what a large test statistic produces
    # and the printed claim remains true.
    if calculated_p > 0:
        orders_smaller = -math.log10(calculated_p) - (-math.log10(threshold_value))
    else:
        orders_smaller = float("inf")

    bound_satisfied = bool(calculated_p <= threshold_value + EPSILON)

    if bound_satisfied:
        severity = "consistent"
        excess_ratio = None
        if orders_smaller > 3:
            explanation = (
                f"Actual p = {calculated_p:.2e} satisfies the reported bound "
                f"'{reported_threshold}'. It lies ~{orders_smaller:.0f} orders of "
                "magnitude below the threshold, which is what a large test "
                "statistic produces and what style rules require reporting as a "
                "floor (APA mandates 'p < .001' for ANY p below .001). Correct "
                "reporting, not a finding."
            )
        else:
            explanation = (
                f"P-value {calculated_p:.4f} is consistent with "
                f"'{reported_threshold}'."
            )
    else:
        excess_ratio = calculated_p / threshold_value
        if excess_ratio > 10:
            severity = "highly_suspicious"
            explanation = (
                f"The reported claim '{reported_threshold}' is contradicted: the "
                f"recomputed p = {calculated_p:.4g} is {excess_ratio:.1f}x ABOVE "
                f"the claimed bound {threshold_value}. No tail convention "
                "(a factor of 2 at most) or plausible input rounding explains an "
                "overshoot this large; the printed significance claim is not "
                "supported by the recomputed value."
            )
        elif excess_ratio > 2:
            severity = "suspicious"
            explanation = (
                f"The recomputed p = {calculated_p:.4g} is {excess_ratio:.1f}x "
                f"above the reported bound '{reported_threshold}'. A one-tailed p "
                "read as two-tailed explains at most a factor of 2, so this "
                "exceeds reporting-convention slack -- but verify the test "
                "variant and the inputs the p was recomputed from before "
                "treating it as more."
            )
        else:
            severity = "indeterminate"
            explanation = (
                f"The recomputed p = {calculated_p:.4g} exceeds the reported "
                f"bound '{reported_threshold}', but only by a factor of "
                f"{excess_ratio:.2f}. A one-tailed p reported against a "
                "two-tailed recomputation, or rounding in the inputs the p was "
                "recomputed from, explains an overshoot this size, so no "
                "judgement is made. Confirm the tail convention and exact "
                "inputs, then re-run."
            )

    return {
        "calculated_p": calculated_p,
        "reported_threshold": reported_threshold,
        "threshold_value": threshold_value,
        "bound_satisfied": bound_satisfied,
        "excess_ratio": excess_ratio,
        "orders_of_magnitude_smaller": orders_smaller,
        "severity": severity,
        "explanation": explanation,
        "methodology": (
            f"STALT check: a reported '{reported_threshold}' claims only that "
            f"p < {threshold_value}. Compared recomputed p = {calculated_p:.2e} "
            "against that bound, one-sided: any p at or below the bound is "
            "consistent however small (a threshold is a style-mandated floor); "
            "only a p above the bound contradicts the claim. Distance below "
            f"the bound: {orders_smaller:.1f} orders of magnitude "
            "(informational only)."
        ),
    }
