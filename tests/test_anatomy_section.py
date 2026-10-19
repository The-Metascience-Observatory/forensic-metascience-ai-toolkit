"""The statistical anatomy must reach the report.

Every production report printed "_No variables were declared._" while the
findings.json beside it held a complete anatomy -- 24 typed variables, 68 tests,
4 hypotheses. The renderer looked for `anatomy` on the EDITORIAL object, and the
sweep puts it on the FINDINGS object. Same defect as the paper metadata: stage 1
captures it, nothing carries it across.

Laying tests out against typed variables is what makes a variable/test mismatch
visible without any statistical work by the reader -- a linear regression whose
outcome is typed `count` is apparent from two adjacent columns.
"""
import pytest

ANATOMY = {
    "studies": [
        {"id": "s1", "label": "Coalition-level analysis", "design": "secondary_analysis",
         "n": 64, "unit_of_analysis": "coalition", "clustered": True},
    ],
    "variables": [
        {"id": "n_ebp", "name": "Number of EBPs", "role": "primary_outcome",
         "measurement_level": "ratio", "discreteness": "discrete", "family": "count",
         "lower_bound": 0, "upper_bound": 9, "confidence": "high"},
        {"id": "comm", "name": "Engaging communication", "role": "predictor",
         "measurement_level": "ordinal", "discreteness": "continuous",
         "family": "likert_composite", "lower_bound": 1, "upper_bound": 4,
         "confidence": "high"},
        {"id": "age", "name": "Age", "role": "covariate", "measurement_level": "ratio",
         "discreteness": "continuous", "family": "continuous", "confidence": "high"},
    ],
    "tests": [
        {"id": "t1", "test_type": "linear_regression", "location": "Table 2",
         "n": 64, "outcome_var": "n_ebp", "predictor_vars": ["comm", "age"],
         "correction_applied": "none", "assumption_checks_reported": []},
        {"id": "t2", "test_type": "mixed_model", "location": "Table 4",
         "n": 101, "outcome_var": "age", "predictor_vars": ["comm"],
         "correction_applied": "bonferroni",
         "assumption_checks_reported": ["ICC of 0.10 reported"]},
    ],
}


def _obj():
    return {
        "headline": {"severity": "suspicious", "statement": "Something."},
        "verdict": "unresolved", "confidence": "high", "findings": [],
        "not_checked": [], "limitations": [],
        "coverage_summary": {"stats_found": 2, "stats_checked": 2},
    }


