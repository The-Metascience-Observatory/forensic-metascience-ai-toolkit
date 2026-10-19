"""Find informative repeated values not covered by stronger matches."""

from __future__ import annotations

import math
from collections import Counter, defaultdict

from scipy import stats

from .constants import (
    _CATEGORICAL_COUNT_RATIO,
    _CATEGORICAL_MAX_DISTINCT,
    _TIERS,
    _VALUE_MIN_DIGITS,
)
from .readers import (
    _cell_ref,
)
from .scoring import (
    _sig_digits,
    _value_severity,
)
from .screening import (
    _column_name,
)
from .severity import (
    CONSISTENT,
    INDETERMINATE,
    SUSPICIOUS,
)


def _find_repeated_values(
    *,
    col_index,
    corroborating,
    diversity,
    duplicate_groups,
    identity_of,
    info,
    norm,
    occurrences,
    reported_cells,
    segments,
):
    """Append weaker value matches while respecting cells claimed by earlier stages."""
    # ---- 3. repeated individual values ------------------------------------
    # Weakest signal; only values whose every occurrence is NOT already part
    # of a reported row pair / sequence are reported (cross-detector dedup).
    #
    # Chance gate: on a large sheet, same-precision collisions are CERTAIN
    # (birthday effect: 75k two-decimal cells produce thousands of repeated
    # 5-digit values). Model each d-digit mantissa bin as Poisson with rate
    # N_d / (9*10^(d-1)); a repeat count the model expects somewhere in the
    # file is not evidence against anyone.
    digit_class: Counter = Counter()
    for v, count in occurrences.items():
        digit_class[_sig_digits(v)] += count

    def comparison_scopes():
        for v, count in occurrences.items():
            if count < 2:
                continue
            locs = [loc for ident in col_index for loc in col_index[ident].get(v, ())]
            by_file, by_identity = defaultdict(list), defaultdict(list)
            for loc in locs:
                s, _, c = loc
                by_file[(segments[s].source or {}).get("file", "single")].append(loc)
                by_identity[identity_of[(s, c)]].append(loc)
            if len(by_file) <= 1:
                yield v, count, locs
                continue
            # Preserve within-file scatter; cross-file equality requires a
            # shared, unique header including units. Never merge unlike columns.
            for scope in by_file.values():
                if len(scope) > 1:
                    yield v, len(scope), scope
            for scope in by_identity.values():
                if len({(segments[s].source or {}).get("file") for s, _, _ in scope}) > 1:
                    yield v, len(scope), scope

    for v, count, locs in comparison_scopes():
        # The same-row guard, which the sequence detector already applies:
        # one measurement written into several columns of ONE row is one fact,
        # not a duplicate. A corpus file records each participant's tax rate as
        # Tax / Tax_Final / Tax_Orig -- identical in 4,000 of 4,000 rows, and
        # every one of those was reported as a duplicated high-precision value.
        # Copy-paste means the value crossed a ROW boundary.
        if len({(s, r) for s, r, _ in locs}) < 2:
            continue
        # ...and a repeated TELEMETRY value is not a finding on its own: a
        # shared browser build or click count is the instrument, not the
        # participant. It can still corroborate a row pair above.
        if all(corroborating.get((s, c)) for s, _, c in locs):
            continue
        d = max((info(s, c, v) for s, _, c in locs), default=0)
        if d < _VALUE_MIN_DIGITS:
            continue
        if all((s, r, c) in reported_cells for s, r, c in locs):
            continue
        low_diversity_capped = False
        d_raw = _sig_digits(v)
        bins = 9.0 * 10.0 ** (d_raw - 1)
        lam = digit_class[d_raw] / bins
        expected_repeats = bins * float(stats.poisson.sf(count - 1, lam))
        if expected_repeats > 0.5:
            continue  # a repeat this common is expected under chance
        score = ((d - 1) ** 1.3) * math.log2(count)
        adjusted = score / norm
        sev = _value_severity(adjusted)
        if expected_repeats > 0.05:
            if _TIERS.index(sev) < _TIERS.index(INDETERMINATE):
                sev = INDETERMINATE
        # A value massed in ONE column is the shared-covariate shape (site
        # rainfall, species constant), not scattered copy-paste. Suspicion
        # from sheer repetition is capped there; the agent should exclude the
        # column if it is a covariate, and only a scatter across columns or
        # sheets keeps the full ladder.
        idents_of_v = {identity_of[(s, c)] for s, _, c in locs}
        single_column_mass = len(idents_of_v) == 1 and count >= 4
        if single_column_mass:
            cap = INDETERMINATE if count >= 8 else SUSPICIOUS
            if _TIERS.index(sev) < _TIERS.index(cap):
                sev = cap
        # THE DIVERSITY GUARD. The Poisson gate above rejects repeats that are
        # too COMMON to mean anything, but it is monotone the wrong way at the
        # other end: expected_repeats collapses to 0.0 in the far tail, so a
        # 4-digit value seen twice is rejected while the SAME value seen 2,639
        # times sails through and scores higher (score grows with log2(count)).
        #
        # That reading is only valid if the column really draws from ~9x10^(d-1)
        # equally likely values. Massive repetition is the strongest possible
        # evidence that it does not -- a condition code, not a measurement. So
        # when the count dwarfs the model's prediction AND the source columns
        # carry few distinct values, the model is falsified, not the data.
        # Cap instead of accusing. Values scattered across many DISTINCT
        # columns keep the full ladder; those are the copy-paste shape.
        div = min((diversity.get((s, c), 10**9) for s, _, c in locs), default=10**9)
        if div <= _CATEGORICAL_MAX_DISTINCT and count >= max(8, _CATEGORICAL_COUNT_RATIO * div):
            if _TIERS.index(sev) < _TIERS.index(INDETERMINATE):
                sev = INDETERMINATE
                low_diversity_capped = True
        if sev == CONSISTENT:
            continue
        duplicate_groups.append(
            {
                "kind": "repeated_value",
                "value": v,
                "occurrences_in_file": count,
                "n_columns": len(idents_of_v),
                "single_column_repeat": single_column_mass,
                "significant_digits": d,
                "chance_expected_repeats": round(expected_repeats, 4),
                "low_diversity_column": low_diversity_capped,
                "columns": sorted({_column_name(segments[s], c) for s, _, c in locs}),
                "cells": [_cell_ref(segments[s], r, c) for s, r, c in locs],
                "adjusted_score": round(adjusted, 2),
                "severity": sev,
            }
        )
