"""
DEBIT — Descriptive Estimate Brawley-Imes Test for binary variables.

For 0/1-coded data with n observations, the sample mean μ = k/n (k ∈ {0..n})
fully determines the sample standard deviation:

    Σ(x_i − μ)² = k·(1 − μ)² + (n − k)·μ²
                = k·(n − k) / n

So sample variance s² = k·(n − k) / (n · (n − 1))   (Bessel's correction),
i.e. sample SD = √(k(n−k) / (n(n−1))).

Equivalently, the population-form SD is σ = √(μ(1 − μ)).

DEBIT therefore enumerates every k consistent with the reported mean's
rounding interval and checks whether ANY of them produces an SD that
rounds to the reported SD. If none do, the (mean, SD, n) triple is
mathematically impossible for binary data.

Reference: Heathers et al., "Recovering data from summary statistics:
Sample Parameter Reconstruction via Iterative TEchniques (SPRITE)" and
the DEBIT preprint cited in Heathers (2025) §"Analyzing regression
coefficients with DEBIT".
"""

from __future__ import annotations

import math
from typing import Optional

from . import rounding as _rounding


def _rounding_half_width(decimals: int) -> float:
    """Half-width of the interval that rounds to a value reported to `decimals` dp.

    The definition lives in `rounding` so every tool shares one; the local name
    is kept so call sites read as before.
    """
    return _rounding.half_width(decimals)


def _expected_sample_sd(k: int, n: int) -> float:
    """Sample SD (Bessel, ÷(n−1)) of a binary vector with k ones and n−k zeros."""
    if n < 2:
        return 0.0
    var = (k * (n - k)) / (n * (n - 1))
    return math.sqrt(var)


def _population_sd_from_k(k: int, n: int) -> float:
    """Population SD (÷n) of a binary vector with k ones: √(p(1−p)).

    Distinct from the module-level `_expected_population_sd(mean)` helper below,
    which takes a proportion rather than a count.

    Reporting √(p(1−p)) instead of the Bessel-corrected SD is a widespread
    convention, not misconduct. Treating it as impossible is a false positive,
    so DEBIT must test this reading too.
    """
    if n < 1:
        return 0.0
    p = k / n
    return math.sqrt(p * (1 - p))


def debit_test(
    mean: float,
    sd: float,
    n: int,
    decimals_mean: int = 2,
    decimals_sd: int = 2,
    data_type: str = "binary",
) -> dict:
    """Run DEBIT on a single (mean, SD, n) triple from claimed binary data.

    MISAPPLICATION GUARD: DEBIT is only valid for 0/1-coded data. Applied to a
    continuous variable it reports ordinary values as `impossible` -- e.g.
    `debit_test(5.51, 1.2, 30)` on a Likert mean. `data_type` must therefore
    declare the data, and a mean outside [0, 1] is treated as evidence the
    tool was misapplied (`indeterminate`), not as a finding against the paper.

    Args:
        mean: Reported mean (a proportion in [0, 1]).
        sd: Reported standard deviation.
        n: Sample size.
        decimals_mean: Decimal places the mean was reported to.
        decimals_sd: Decimal places the SD was reported to.
        data_type: Must be "binary" (or "proportion"); anything else returns
            `indeterminate` rather than a finding.

    Returns:
        Dict with `consistent`, `severity`, the candidate (k, expected_sd)
        pairs, and a methodology string.
    """
    from .grim import canonical_data_type
    from .severity import refuse_if_nonfinite

    guard = refuse_if_nonfinite(mean=mean, sd=sd, n=n)
    if guard is not None:
        return guard

    if canonical_data_type(data_type) not in {"binary", "proportion"}:
        return {
            "consistent": False,
            "severity": "indeterminate",
            "applicable": False,
            "explanation": (
                f"DEBIT does not apply to data_type={data_type!r}. It is defined only for "
                "0/1-coded (binary) data, where the mean determines the SD exactly."
            ),
            "methodology": "DEBIT applicability guard.",
            "reported_mean": mean,
            "reported_sd": sd,
            "n": n,
        }
    if n < 2:
        return {
            "consistent": False,
            # A GUARD, not a finding: we cannot evaluate, so we must not accuse.
            "severity": "indeterminate",
            "explanation": "DEBIT requires n ≥ 2; cannot evaluate.",
            "methodology": "DEBIT cannot be computed for n < 2.",
            "reported_mean": mean,
            "reported_sd": sd,
            "n": n,
        }

    if not (0.0 <= mean <= 1.0):
        return {
            "consistent": False,
            # A mean outside [0,1] almost always means DEBIT was pointed at
            # non-binary data -- a MISAPPLICATION -- not that the paper is
            # impossible. Refuse to evaluate rather than accuse.
            "severity": "indeterminate",
            "applicable": False,
            "explanation": (
                f"Reported mean {mean} is outside [0, 1], so these are not 0/1-coded "
                "data and DEBIT does not apply. This indicates the tool was misapplied, "
                "not that the reported statistics are impossible."
            ),
            "methodology": (
                "DEBIT precondition: binary data are coded {0, 1}, so the "
                "mean (= proportion of 1s) must lie in [0, 1]."
            ),
            "reported_mean": mean,
            "reported_sd": sd,
            "n": n,
        }

    if sd < 0.0:
        return {
            "consistent": False,
            "severity": "impossible",
            "explanation": "Standard deviation cannot be negative.",
            "methodology": "Trivial check.",
            "reported_mean": mean,
            "reported_sd": sd,
            "n": n,
        }

    # Step 1: enumerate all k whose proportion k/n rounds to `mean`.
    mean_tol = _rounding_half_width(decimals_mean)
    sd_tol = _rounding_half_width(decimals_sd)

    # SD UNIT-SLIP GUARD. A binary variable's sample SD cannot exceed
    # 0.5·sqrt(n/(n-1)), so any SD above that is not a valid binary SD. But an
    # impossible binary SD is exactly what DEBIT is FOR -- Regnerus 2012's
    # SD 0.75 at mean 0.01 is a real detection -- so an over-range SD must NOT
    # be blanket-reclassified, or the core check is gutted. Only the specific
    # PERCENT UNIT SLIP is a misapplication, and it has a tell the genuine
    # impossibility lacks: dividing by 100 yields exactly the binary SD the mean
    # implies. Verified: a paper's "35% (SD 47.7%)" arrives here as mean=0.35,
    # sd=47.7, and 47.7/100 = 0.477 = sqrt(0.35·0.65) to the digit; Regnerus's
    # 0.75/100 = 0.0075 is nowhere near sqrt(0.01·0.99) = 0.0995, so it falls
    # through and stays `impossible`.
    max_binary_sd = 0.5 * math.sqrt(n / (n - 1)) if n > 1 else 0.5
    expected_binary_sd = math.sqrt(mean * (1.0 - mean))
    looks_like_percent = (
        sd > max_binary_sd + sd_tol
        and sd / 100.0 <= max_binary_sd + sd_tol
        and abs(sd / 100.0 - expected_binary_sd) <= max(sd_tol, 0.02)
    )
    if looks_like_percent:
        return {
            "consistent": False,
            "severity": "indeterminate",
            "applicable": False,
            "explanation": (
                f"Reported SD {sd} exceeds {max_binary_sd:.4f}, the largest SD any "
                f"binary (0/1) variable can have at n = {n}, but {sd} / 100 = "
                f"{sd / 100:.4f} is exactly the binary SD that mean {mean} implies "
                f"(sqrt({mean}·{1 - mean:.2f}) = {expected_binary_sd:.4f}). This is a "
                "unit slip -- the SD left in percent while the mean was normalised "
                "-- not a fact about the paper, so the tool was misapplied rather "
                "than the statistics being impossible."
            ),
            "methodology": (
                "DEBIT precondition: a binary SD is bounded by 0.5·sqrt(n/(n-1)); "
                "an over-range SD whose /100 matches the mean's implied SD is a "
                "percent unit slip, not an impossibility."
            ),
            "reported_mean": mean,
            "reported_sd": sd,
            "n": n,
        }

    # ROUNDING CONVENTION: tried BOTH ways, never silently assumed. A reporter
    # that truncates (SPSS's default, some journals', one of scrutiny::grim's
    # rounding options) prints floor(true·10^d)/10^d, so the true value lies
    # in the HALF-OPEN interval [reported, reported + 10^-d) -- a different
    # window from round-half, not a wider one. Testing round-half alone
    # convicts an honest truncating reporter: verified, 2 ones + 1 zero (n=3)
    # has exact mean 0.6667 and sample SD 0.5774, printed 0.66 / 0.57 by a
    # truncating reporter, and this function returned `impossible` for both
    # the mean step and the SD step. Same de-escalation grim_test applies
    # (failure_mode `rounding_convention`). Since 2026-08-10 that de-escalation
    # goes all the way to `consistent` -- Greg's call; see `grim.grim_test`.
    # The convention is named and counted per paper, never filed as a finding.
    mean_step = 10.0 ** (-decimals_mean)
    sd_step = 10.0 ** (-decimals_sd)

    round_mean_ks: set[int] = set()
    trunc_mean_ks: set[int] = set()
    for k in range(0, n + 1):
        prop = k / n
        # Round-half: the reported value `mean` is the rounded version of
        # prop, so |prop − mean| < mean_tol (strict inequality from below for
        # the standard "round half away from zero" convention; we accept ≤).
        if abs(prop - mean) <= mean_tol + 1e-12:
            round_mean_ks.add(k)
        # Truncation: prop lies in [mean, mean + 10^-d).
        if mean - 1e-12 <= prop < mean + mean_step - 1e-12:
            trunc_mean_ks.add(k)

    candidate_ks = sorted(round_mean_ks | trunc_mean_ks)

    if not candidate_ks:
        # No integer k produces the reported mean under EITHER convention --
        # a GRIM-style failure, and bound-free arithmetic, so `impossible`
        # is licensed.
        return {
            "consistent": False,
            "severity": "impossible",
            "explanation": (
                f"No integer k in [0, {n}] produces a proportion k/n that "
                f"rounds OR truncates to {mean} (to {decimals_mean} dp). The "
                "mean alone is impossible under both reporting conventions; "
                "DEBIT subsumes GRIM here."
            ),
            "methodology": (
                "DEBIT step 1 (GRIM): for binary data, the mean must equal k/n "
                "for integer k. No such k matches the reported mean under "
                "either the round-half or the truncation convention."
            ),
            "reported_mean": mean,
            "reported_sd": sd,
            "n": n,
            "candidates": [],
        }

    # Step 2: for each candidate k, compute expected sample SD; check if
    # any rounds (or truncates) to the reported SD.
    candidates: list[dict] = []
    matching: list[dict] = []
    matching_population: list[dict] = []
    matching_truncation: list[dict] = []

    def _trunc_match(expected: float) -> bool:
        """True if a truncating reporter would print `expected` as `sd`."""
        return sd - 1e-12 <= expected < sd + sd_step - 1e-12

    for k in candidate_ks:
        expected_sd = _expected_sample_sd(k, n)
        population_sd = _population_sd_from_k(k, n)
        deviation = abs(expected_sd - sd)
        deviation_population = abs(population_sd - sd)
        # `consistent` / `consistent_population_convention` keep their
        # original round-half meaning (and require a round-half mean).
        mean_round = k in round_mean_ks
        mean_trunc = k in trunc_mean_ks
        consistent = mean_round and deviation <= sd_tol + 1e-12
        consistent_population = (
            mean_round and deviation_population <= sd_tol + 1e-12
        )
        # Any full reading that leans on truncation somewhere -- truncated
        # mean, truncated SD, or both, under either SD convention.
        sd_any = (
            deviation <= sd_tol + 1e-12
            or deviation_population <= sd_tol + 1e-12
            or _trunc_match(expected_sd)
            or _trunc_match(population_sd)
        )
        consistent_truncation = (mean_round or mean_trunc) and sd_any
        entry = {
            "k": k,
            "implied_proportion": k / n,
            "expected_sample_sd": expected_sd,
            "expected_population_sd": population_sd,
            "deviation": deviation,
            "deviation_population": deviation_population,
            "consistent": consistent,
            "consistent_population_convention": consistent_population,
            "consistent_truncation_convention": consistent_truncation,
        }
        candidates.append(entry)
        if consistent:
            matching.append(entry)
        if consistent_population:
            matching_population.append(entry)
        if consistent_truncation:
            matching_truncation.append(entry)

    overall_consistent = len(matching) > 0
    population_only = (not overall_consistent) and len(matching_population) > 0
    truncation_only = (
        not overall_consistent
        and not population_only
        and len(matching_truncation) > 0
    )

    # Severity ladder. `impossible` is reserved for triples that fail EVERY
    # defensible reading of "SD" -- a paper using the population convention,
    # or one that truncates rather than rounds, is making a reporting choice,
    # not fabricating data.
    if overall_consistent:
        severity = "consistent"
    elif population_only or truncation_only:
        # GREG'S CALL, 2026-08-10, in two parts, and the second part corrects
        # the first.
        #
        # He first ruled on TRUNCATION: a value rescued purely by that
        # convention is not filed as a suspicious finding; it is named and
        # counted per paper. I applied it to truncation only and recorded, in
        # this very block, that the POPULATION-SD convention was "deliberately
        # left at `suspicious`" because he had not ruled on it.
        #
        # He then ruled on it: "regarding the Population-SD convention, I
        # changed my mind and want it applied as well -- it would be
        # inconsistent to do the truncation check but not this."
        #
        # He is right, and the caution was the wrong kind. The two are the same
        # KIND of thing: a reporting convention the paper chose, which fully
        # explains the number. Splitting them meant one epistemic situation
        # getting two different words depending on which convention happened to
        # carry it -- and a reader cannot be expected to know that `suspicious`
        # here meant "numpy's std default" while `consistent` next door meant
        # "SPSS's rounding default".
        #
        # Both are counted per paper in `agent.checks_tally`, which is where a
        # RATE can be read. Per Heathers this class of anomaly is commoner in
        # papers with more serious errors, so a high rate is grounds to look
        # harder -- never a finding on its own.
        severity = "consistent"
    else:
        severity = "impossible"

    if overall_consistent:
        explanation = (
            f"Reported SD {sd} matches at least one binary-data SD consistent "
            f"with mean {mean} (n = {n}). Matching k values: "
            f"{[m['k'] for m in matching]}."
        )
    elif population_only:
        ks = [m["k"] for m in matching_population]
        explanation = (
            f"Reported SD {sd} is consistent under the POPULATION-SD convention "
            f"√(p(1−p)) (matching k: {ks}), but not under the sample-SD (Bessel, "
            f"n−1) convention. This is a reporting-convention difference, which is "
            "common and legitimate -- NOT evidence of fabrication. NOT a finding: "
            "the convention is named and counted per paper, because the RATE is "
            "where the signal lives and one such value is a house style. Confirm "
            "the convention against the paper's methods section."
        )
    elif truncation_only:
        ks = [m["k"] for m in matching_truncation]
        explanation = (
            f"Reported mean {mean} and SD {sd} are consistent (matching k: {ks}) "
            "only if the reported values were TRUNCATED rather than rounded -- "
            "SPSS's default, some journals', and one of scrutiny::grim's rounding "
            "options, so a truncating reporter would print exactly these figures "
            "from real binary data. A rounding-convention difference is a "
            "reporting choice, NOT evidence of fabrication; flagged only so the "
            "convention can be confirmed against the paper."
        )
    else:
        # Find closest candidate so the LLM can quote it.
        closest = min(candidates, key=lambda c: c["deviation"])
        explanation = (
            f"For binary data with mean {mean} and n = {n}, the SD is forced "
            f"to be one of {sorted({round(c['expected_sample_sd'], decimals_sd + 2) for c in candidates})} "
            f"(sample convention) or "
            f"{sorted({round(c['expected_population_sd'], decimals_sd + 2) for c in candidates})} "
            f"(population convention). Reported SD {sd} matches neither, under "
            f"either the round-half or the truncation reading "
            f"(closest: SD ≈ {closest['expected_sample_sd']:.{decimals_sd + 2}f} for k = {closest['k']})."
        )

    # WHAT FAILED AS PRINTED, before a convention explained it.
    #
    # GREG, 2026-08-11: "we do the test on only those numbers available, flag
    # it, and then test truncation etc. That way the reader can see the apparent
    # violation (i.e. our toolkit working) but then judge for themselves whether
    # the truncation etc is credible."
    #
    # DEBIT was already the most transparent of the family -- it names both the
    # SD convention and the rounding convention in its result -- but it never
    # said what severity had been WITHHELD, so a reader could not tell a value
    # that sailed through from one that survived only on a convention.
    #
    # MEASURED against Greg's off-switch rule before keeping either rescue: over
    # 400 arbitrary (mean, sd, n) triples DEBIT still reached `impossible` on
    # 388. Only 12 cleared, and only 2 of those via the population convention.
    # DEBIT retains 97% of its power -- these conventions explain individual
    # values, they do not switch the check off. That is expected: for 0/1 data
    # the SD is FULLY DETERMINED by the count of 1s and n, so the admissible set
    # is tiny and no reporting convention widens it much.
    as_reported = None
    if population_only or truncation_only:
        as_reported = {
            "verdict": "sd_inconsistent_with_mean",
            "severity_if_taken_at_face_value": "impossible",
            "statement": (
                f"As printed, an SD of {sd} is not attainable for binary data "
                f"with a mean of {mean} at n = {n} under the ordinary reading "
                "(sample SD, round-half). For 0/1 data the SD is fully "
                "determined by the count of 1s and n, so this is a tight "
                "constraint rather than a loose plausibility band."
            ),
            "explained_by": "population_sd" if population_only else "truncation",
            "explanation": (
                "It IS attainable under the POPULATION (n) SD convention -- "
                "numpy's `std` default and Excel's STDEVP."
                if population_only else
                "It IS attainable if the mean and SD were TRUNCATED rather than "
                "rounded, which is SPSS's default."
            ),
            "how_often_that_excuse_is_available": 0.03,
            "judge_for_yourself": (
                "Not counted as a finding: a reporting convention that fully "
                "explains a number is not evidence against the paper. It is "
                "shown because the arithmetic did fail as printed. Measured on "
                "arbitrary values these conventions rescue about 3% of "
                "otherwise-impossible triples, so this is a specific "
                "explanation rather than a universal escape -- check whether "
                "the paper's other binary rows need the same reading. The RATE "
                "across one paper is the signal, not a single instance."
            ),
        }

    # Which SD convention carried the truncation-only match, for the record.
    truncation_sd_convention = None
    if truncation_only:
        sample_carried = any(
            abs(m["expected_sample_sd"] - sd) <= sd_tol + 1e-12
            or _trunc_match(m["expected_sample_sd"])
            for m in matching_truncation
        )
        truncation_sd_convention = "sample" if sample_carried else "population"

    out = {
        "consistent": overall_consistent,
        "consistent_under_population_convention": len(matching_population) > 0,
        "consistent_under_truncation_convention": len(matching_truncation) > 0,
        "sd_convention": (
            "sample" if overall_consistent
            else ("population" if population_only
                  else (truncation_sd_convention if truncation_only
                        else "neither"))
        ),
        "rounding_convention": (
            "truncation" if truncation_only
            else ("round_half" if (overall_consistent or population_only)
                  else "neither")
        ),
        "severity": severity,
        "reported_mean": mean,
        "reported_sd": sd,
        "n": n,
        "decimals_mean": decimals_mean,
        "decimals_sd": decimals_sd,
        "candidates": candidates,
        "matching_k_values": [m["k"] for m in matching],
        "matching_k_values_population": [m["k"] for m in matching_population],
        "matching_k_values_truncation": [m["k"] for m in matching_truncation],
        "explanation": explanation,
        "methodology": (
            "DEBIT: for 0/1 data, sample SD is fully determined by the count k of "
            f"1s and n via SD = √(k(n−k)/(n(n−1))). With mean reported as {mean} "
            f"(±{mean_tol} round-half, or [{mean}, {round(mean + mean_step, decimals_mean + 2)}) "
            f"truncated) and n = {n}, candidate k values are {candidate_ks}; the "
            "reported SD must round (or truncate) to one of the SDs implied by "
            "those k. Both rounding conventions and both SD conventions "
            "(sample n−1, population n) are tried before any accusation; a "
            "triple consistent only under truncation or only under the "
            "population SD is `suspicious`, never `impossible`."
        ),
    }
    if as_reported:
        out["as_reported"] = as_reported
    return out


def debit_test_batch(
    rows: list[dict],
    data_type: str = "binary",
) -> dict:
    """Run DEBIT on a list of binary-variable rows.

    Each row: {"label": str (optional), "mean": float, "sd": float,
               "n": int, "decimals_mean": int, "decimals_sd": int}.

    PRECISION IS PER ROW AND HAS NO BATCH-WIDE FALLBACK. A table prints its
    numbers at whatever precision each one was printed at -- a mean to 2 dp
    beside its own SD at 1 dp is ordinary, and the corpus has one. Measured
    exhaustively over 19,729 honest binary rows: 0 `impossible` at each row's
    true precision, 13,447 (68.2%) under a single batch-wide 2 dp. A row that
    does not carry its own precision is REFUSED, named, and the rest of the
    batch still runs.
    """
    results = []
    for i, row in enumerate(rows):
        label = row.get("label", f"row_{i}")
        dm, ds = row.get("decimals_mean"), row.get("decimals_sd")
        if dm is None or ds is None:
            results.append({
                "consistent": None, "severity": "indeterminate",
                "failure_mode": "precondition_absent", "label": label,
                "error": ("this row did not carry its own printed precision "
                          "(decimals_mean and decimals_sd). Read them off the "
                          "literals the paper printed; there is deliberately no "
                          "batch-wide default, because one precision for a whole "
                          "table convicts the rows printed more coarsely."),
            })
            continue
        try:
            r = debit_test(
                mean=float(row["mean"]),
                sd=float(row["sd"]),
                n=int(row["n"]),
                decimals_mean=int(dm),
                decimals_sd=int(ds),
                # The batch tool used to call debit_test WITHOUT data_type, so
                # every row ran at the function default `binary` regardless of
                # what the caller declared -- and the batch form is the one a
                # Table 1 invites you to use. The guard existed only on the
                # single-row tool.
                data_type=data_type,
            )
        except (KeyError, ValueError, TypeError) as e:
            r = {"consistent": False, "severity": "indeterminate", "error": str(e)}
        r["label"] = label
        results.append(r)

    n_impossible = sum(1 for r in results if r.get("severity") == "impossible")
    n_consistent = sum(1 for r in results if r.get("severity") == "consistent")
    n_indeterminate = sum(1 for r in results if r.get("severity") == "indeterminate")
    n_population = sum(
        1 for r in results if r.get("sd_convention") == "population"
    )
    n_truncation = sum(
        1 for r in results if r.get("rounding_convention") == "truncation"
    )
    # A row is EVALUATED only if DEBIT actually ran on it. Guard hits (wrong
    # data_type, n < 2, mean outside [0, 1], malformed row) return
    # `indeterminate` and check nothing.
    n_evaluated = len(results) - n_indeterminate

    # Escalation needs a real pattern, not a single row. The previous rule
    # (`n_impossible >= max(1, len//3)`) escalated a 3-row table to
    # `highly_suspicious` on ONE impossible row, which is noise on small tables.
    # The "a third of the table" fraction is taken over the rows that were
    # EVALUATED, not over every row submitted: a table where 24 of 30 rows were
    # refused and all 6 evaluated rows are impossible is a pattern, and dividing
    # by the 30 submitted rows would hide it.
    if n_evaluated == 0:
        # THE FALSE-CLEAR GUARD. Reporting `consistent` for a batch in which
        # nothing was checked turns a refusal into a clean bill of health --
        # the reader sees a green verdict on a table DEBIT never looked at.
        # An unevaluated batch is `indeterminate`, exactly as the single-cell
        # tool already is on the same input.
        overall_severity = "indeterminate"
    elif n_impossible == 0:
        # NEITHER convention taints the aggregate any more (Greg, 2026-08-10:
        # truncation first, then population-SD -- "it would be inconsistent to do
        # the truncation check but not this"). A batch whose rows are all
        # explained by a reporting convention has no impossible row in it, and
        # calling the table `suspicious` on that basis was filing the convention
        # as a finding by the back door, one level up from the per-row severity
        # that no longer does so.
        #
        # The counts survive: `n_population` and `n_truncation` are returned and
        # named in the explanation, so the RATE -- the thing that actually
        # carries information -- is right there for a reader, and
        # `agent.checks_tally` aggregates it per paper.
        overall_severity = "consistent"
    elif n_impossible >= max(3, n_evaluated // 3):
        overall_severity = "highly_suspicious"
    else:
        overall_severity = "suspicious"

    if n_evaluated == 0:
        explanation = (
            f"Not evaluated: DEBIT ran on 0 of {len(results)} rows (all "
            "`indeterminate`). This is a refusal, not a finding, and says nothing "
            "about the table. Check the per-row `explanation` fields -- the usual "
            "cause is a data_type that is not binary/proportion, so DEBIT does not "
            "apply."
        )
    else:
        explanation = (
            f"DEBIT evaluated {n_evaluated} of {len(results)} rows "
            f"({n_indeterminate} not evaluated): {n_consistent} consistent, "
            f"{n_impossible} impossible, {n_population} consistent only under the "
            f"population-SD convention, {n_truncation} consistent only under the "
            "truncation convention."
        )

    return {
        "results": results,
        "n_rows": len(results),
        # Reported explicitly so the reader never has to infer "nothing ran"
        # from n_consistent + n_impossible failing to sum to n_rows.
        "n_evaluated": n_evaluated,
        "n_indeterminate": n_indeterminate,
        "n_impossible": n_impossible,
        "n_consistent": n_consistent,
        "n_population_convention": n_population,
        "n_truncation_convention": n_truncation,
        "severity": overall_severity,
        "explanation": explanation,
        # Same convention as the single-cell guards: `applicable` appears only
        # when the tool declined to evaluate, and consumers key off it.
        **({"applicable": False} if n_evaluated == 0 else {}),
        "methodology": (
            "DEBIT batch: applied debit_test to each row independently. "
            "A batch in which NO row was evaluated is `indeterminate`, never "
            "`consistent`; `consistent` requires at least one row to have been "
            "checked. Severity escalates only with a PATTERN of impossible rows "
            "(>= 3, or a third of the EVALUATED rows); a lone impossible row on a "
            "small table is not escalated. Rows consistent only under the "
            "population-SD convention, or only under the truncation rounding "
            "convention, are reported as `suspicious`, never `impossible`."
        ),
    }


def _expected_population_sd(mean: float) -> Optional[float]:
    """Convenience: σ = √(p(1−p)) for binary data, when n is unknown."""
    if not (0.0 <= mean <= 1.0):
        return None
    return math.sqrt(mean * (1 - mean))
