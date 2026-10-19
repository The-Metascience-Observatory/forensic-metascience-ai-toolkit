"""Identify columns and exclude or cap values repeated by design."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Optional

import numpy as np

from .constants import (
    _AGGREGATE_RE,
    _ARITH_RUN_FRACTION,
    _CATEGORICAL_MAX_DISTINCT,
    _DERIVED_MIN_DECIMALS,
    _FD_MAX_COLS,
    _FD_MAX_ROWS,
    _FD_MIN_COEF,
    _FD_RESIDUAL_TOL,
    _GEOCODE_NAMES,
    _IDENTIFIER_RE,
    _LONG_FORMAT_MIN_BLOCKS,
    _LONG_FORMAT_MIN_REPEATED,
    _LONG_FORMAT_MIN_VARYING,
    _LOW_DIVERSITY_MIN_ROWS,
    _LOW_DIVERSITY_RATIO,
    _NAME_TOKENS,
    _STATS_OUTPUT_RE,
    _TELEMETRY_AMBIGUOUS,
    _TELEMETRY_PLATFORM,
)
from .readers import (
    _col_letter,
    _Segment,
)
from .scoring import (
    _canon,
    _derived_source_digits,
    _num_decimals,
)


def _normalise_header(name: str) -> str:
    """Lowercase, with `_`, `-` and camelCase boundaries read as spaces.

    Qualtrics writes `StartDate` and `ResponseId`; researchers write
    `start_date`; the patterns are spelled with spaces and matched neither.
    Splitting camelCase is not cosmetic -- without it `ResponseId` fails the
    platform test, so an export that IS a Qualtrics file is not recognised as
    one and its ambiguous columns are judged with no context at all.
    """
    txt = str(name or "").replace("_", " ").replace("-", " ")
    txt = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", txt)
    return " ".join(txt.split()).lower()


def _telemetry_name_candidate(name: str) -> str | None:
    """`"platform"`, `"ambiguous"`, or None. The NAME only; see `_is_telemetry`.

    Word-bounded: the old substring test read "progress" out of
    "disease_progression_score" and demoted a clinical outcome.
    """
    low = _normalise_header(name)
    for pat in _TELEMETRY_PLATFORM:
        if re.search(r"(?<![a-z0-9])" + re.escape(pat) + r"s?(?![a-z0-9])", low):
            return "platform"
    for pat in _TELEMETRY_AMBIGUOUS:
        if re.search(r"(?<![a-z0-9])" + re.escape(pat) + r"s?(?![a-z0-9])", low):
            return "ambiguous"
    return None


def _looks_like_platform_export(names: "list[str] | tuple[str, ...]") -> bool:
    """Does this file carry a column only a survey platform would write?"""
    return any(_telemetry_name_candidate(n) == "platform" for n in names or ())


def _is_telemetry(name: str, all_names: "list[str] | tuple[str, ...] | None" = None) -> bool:
    """Was this column written by the survey platform rather than the participant?

    `all_names` is the file's other headers, and it is what turns a guess into
    a judgment. Omitted, only the unambiguous platform names count -- the safe
    reading, since demoting a column removes its values from the evidence base
    for a finding.
    """
    kind = _telemetry_name_candidate(name)
    if kind == "platform":
        return True
    if kind == "ambiguous" and all_names is not None:
        return _looks_like_platform_export(all_names)
    return False


def _geocode_name_candidate(name: str) -> bool:
    """The NAME suggests a place code. It does not settle it -- see `_is_geocode`.

    Renamed from `_is_geocode` 2026-08-18 to stop the name being read as a
    verdict, which is what it had become.
    """
    low = name.strip().lower()
    if low in _GEOCODE_NAMES:
        return True
    tokens = [t for t in _NAME_TOKENS.split(low) if t]
    if not tokens:
        return False
    # `zip`, `ZIP Code`, `respondent zip` -> yes. `zipf_rank` -> no.
    if any(t in _GEOCODE_NAMES for t in tokens):
        return True
    return "_".join(tokens) in _GEOCODE_NAMES


def _values_look_like_codes(values: "list[float]") -> bool:
    """Do the VALUES corroborate the name? A code has no fractional part.

    A ZIP, a FIPS, a GEOID, a census tract number: every one of them is an
    integer label. A measurement is not -- fractional anisotropy is 0.42, a
    volume in cm3 is 12.7, a rate is 0.031. So a single non-integral value is
    decisive evidence AGAINST the name, and it is the cheapest possible check
    because this function already holds the column.

    Refuses to judge an empty column: nothing observed is not evidence of a
    code, and returning True there would restore the silent exclusion by a
    different route.
    """
    if not values:
        return False
    return all(float(v) == int(v) for v in values)


def _is_geocode(name: str, values: "list[float] | None" = None) -> bool:
    """A place code rather than a measurement -- NAME LOCATES, VALUES JUDGE.

    THE NAME ALONE WAS THE VERDICT UNTIL 2026-08-18, AND THAT WAS THE DEFECT.
    Greg, 2026-08-18, on a survey of pattern-made semantic judgments: "I do not
    see why this kind of rudimentary application of regex is being used at all."
    This was the worst of the three high-severity cases, because unlike the
    others it does not merely mislabel -- it REMOVES a column from every
    comparison in the duplication check, so the evidence never reaches the
    reader in any form.

    The name is now a screen that raises a candidate; the column's own values
    decide it. `corticospinal tract FA` no longer matches by name at all, and
    even if it did, its decimals would refuse the exclusion.

    `values=None` preserves the old name-only behaviour for callers that have no
    column to hand, and there are none in this module -- it exists so a future
    caller has to pass the evidence or knowingly opt out of it.
    """
    if not _geocode_name_candidate(name):
        return False
    if values is None:
        return True
    return _values_look_like_codes(values)


def _column_name(seg: _Segment, col: int) -> str:
    if col < len(seg.col_names) and seg.col_names[col]:
        return seg.col_names[col]
    return f"(column {_col_letter(col)})"


def _column_identity(seg: _Segment, seg_idx: int, col: int) -> str:
    """Key under which columns are compared across segments: the header name
    when the file provides one, else a per-segment positional identity."""
    if col < len(seg.col_names) and seg.col_names[col]:
        name = seg.col_names[col].strip().lower()
        if sum(n.strip().lower() == name for n in seg.col_names) == 1:
            return name
        return f"#{seg_idx}:{col}:{name}"
    return f"#{seg_idx}:{col}"


def _has_identifier_column(names: "list[str]") -> bool:
    """Does this table name a unit of observation, one row each?"""
    return any(_IDENTIFIER_RE.search(_normalise_header(n)) for n in names)


def _group_columns(group: dict) -> set:
    """Every column a finding implicates, by display name where known.

    Each kind names its columns differently -- `columns` on repeated_value,
    `column_a`/`column_b` on column_sequence, only cell refs on row_pair --
    so both the rollup and the diffuse-evidence cap go through here.
    """
    names = set(group.get("columns") or ())
    for k in ("column_a", "column_b"):
        if group.get(k):
            names.add(group[k])
    if not names:
        for k in ("cells", "cells_a", "cells_b"):
            for ref in group.get(k) or ():
                if isinstance(ref, dict) and ref.get("col") is not None:
                    names.add(_col_letter(ref["col"]))
    return names


def _infer_context(segments: list[_Segment]) -> str:
    """What this file actually looks like, read off its headers.

    `data_context` is caller-supplied, and a caller that mislabels a
    regression table as participant data gets it scanned as raw data: a
    corpus sweep put six `tab_s*_model_results.xlsx` files (headers
    `Term, Beta, SE, Tvalue, PValue, R_Squared`, four rows each) through the
    full ladder. An R-squared is identical across the rows of one model BY
    CONSTRUCTION, so those repeats are structure, not evidence.

    Returns "statistical_output", "aggregate", or "" (looks like raw data).
    Advisory only -- it caps, it never accuses.
    """
    for seg in segments:
        names = [n for n in seg.col_names if n and n.strip()]
        if len(names) < 3:
            continue
        stats_hits = sum(1 for n in names if _STATS_OUTPUT_RE.match(n))
        if stats_hits >= 3 or (stats_hits >= 2 and stats_hits >= len(names) / 2):
            return "statistical_output"
        # Header text is NORMALISED first. `\b` does not fire on `_`, so
        # `Total Score` matched and `total_score` did not -- the rule was
        # keying on formatting rather than on meaning.
        agg_hits = sum(1 for n in names if _AGGREGATE_RE.search(_normalise_header(n)))
        if (
            agg_hits >= 2
            and agg_hits >= len(names) / 2
            and len(seg.rows) <= 200
            and not _has_identifier_column(names)
        ):
            return "aggregate"
    return ""


def _detect_long_format(seg: "_Segment") -> Optional[dict]:
    """Recognise repeated-measures LONG FORMAT, where each subject owns k rows.

    In long format a participant's invariant attributes are written once per
    row they occupy, so a 550-subject x 3-condition file contains three exact
    copies of every attribute column. That is the reshape, not duplicated data
    -- but it presents to `column_sequence` as a perfect 550-long repeat and
    earned `highly_suspicious` on `study1a_data.csv` (PNAS 2217551120), whose
    1,650 rows are 550 respondents seen under `badge`/`poster`/`test`.

    Reporting that as duplication is the failure mode this module is most
    careful about elsewhere: an accusation manufactured from the SHAPE of an
    honest file. So the shape is detected once, named, and the columns that
    repeat BY CONSTRUCTION are excluded -- the ones that vary are still
    compared, because a reshape is no reason to stop looking.

    Returns None unless the file is confidently long format. The test is
    deliberately strict: an exact integer period, at least three blocks, a
    substantial repeated set AND a substantial varying set.
    """
    n_rows = len(seg.rows)
    if n_rows < _LONG_FORMAT_MIN_BLOCKS * 2:
        return None

    cols: dict[int, list] = defaultdict(list)
    for _, numbers in seg.rows:
        for c, v in numbers.items():
            cols[c].append(v)
    # Only columns present on EVERY row can testify about the period; a ragged
    # column says nothing about block structure. A CONSTANT column cannot
    # testify either -- it repeats across any partition whatsoever, so counting
    # it as support finds "long format" in any file carrying a few constants.
    # Measured on `study5_data.csv`, whose only three repeating columns are
    # `Progress`=100, `Finished`=1 and a constant flag: a 3x264 split was
    # declared structural on evidence that would fit 2x396 and 4x198 equally.
    full = {c: vals for c, vals in cols.items() if len(vals) == n_rows and len(set(vals)) > 1}
    if len(full) < 4:
        return None

    for n_blocks in range(_LONG_FORMAT_MIN_BLOCKS, 13):
        if n_rows % n_blocks:
            continue
        period = n_rows // n_blocks
        if period < 5:
            continue
        repeated, varying = [], []
        for c, vals in full.items():
            blocks = [vals[i * period : (i + 1) * period] for i in range(n_blocks)]
            if all(b == blocks[0] for b in blocks[1:]):
                repeated.append(c)
            else:
                varying.append(c)
        if len(repeated) >= _LONG_FORMAT_MIN_REPEATED and len(varying) >= _LONG_FORMAT_MIN_VARYING:
            return {
                "n_blocks": n_blocks,
                "period": period,
                "repeated_columns": sorted(repeated),
                "varying_columns": sorted(varying),
            }
    return None


def _screen_columns(
    segments: list[_Segment],
    exclude_columns: Optional[list],
) -> tuple[
    dict[tuple[int, int], str],
    dict[tuple[int, int], bool],
    list[str],
    dict[tuple[int, int], int],
    dict[tuple[int, int], bool],
]:
    """Decide, per (segment, column): excluded reason ('' = included) and
    whether the column's information is capped as a transform column.

    Exclusions (never compared at all):
      - caller-named shared-by-design columns (IDs, coordinates, site-level
        covariates) — the agent knows what a column MEANS; code does not;
      - constant columns (one repeated value is design, not evidence);
      - arithmetic runs (row counters / IDs — consecutive differences share
        one dominant value);
      - instrument telemetry (browser build, click timings) — the survey
        platform wrote these, not the participant, and they collide by nature;
      - mixed text/number columns, where only a minority of cells parse.
    Transform cap (compared, but each value scored as ~1 digit): a column
    where sampled values are systematically derived (fractions / sqrt / ln) —
    their apparent precision is an artifact of the transform.

    Also returns each surviving column's DISTINCT-VALUE COUNT, which the
    repeated-value detector needs to tell a categorical code apart from a
    measurement (see the diversity guard in detect_raw_duplication).
    """
    excluded_norm = {str(c).strip().lower() for c in (exclude_columns or [])}
    excluded: dict[tuple[int, int], str] = {}
    capped: dict[tuple[int, int], bool] = {}
    notes: list[str] = []
    diversity: dict[tuple[int, int], int] = {}
    #: Columns that may support a row pair but never seed one. See the
    #: telemetry branch below for why the distinction has to exist.
    corroborating: dict[tuple[int, int], bool] = {}

    for s_idx, seg in enumerate(segments):
        cols: dict[int, list[float]] = defaultdict(list)
        for _, numbers in seg.rows:
            for c, v in numbers.items():
                cols[c].append(v)
        # Whole-sheet shape, decided once: which columns repeat BY CONSTRUCTION
        # because each subject owns several rows. Named in `notes` so a reader
        # sees the reshape was recognised rather than silently tolerated.
        long_fmt = _detect_long_format(seg)
        long_repeated = set(long_fmt["repeated_columns"]) if long_fmt else set()
        if long_fmt:
            notes.append(
                f"'{seg.label}': long format detected — {long_fmt['n_blocks']} "
                f"blocks of {long_fmt['period']} rows (repeated measures). "
                f"{len(long_repeated)} subject-level column(s) repeat once per "
                "block by construction and were excluded; the "
                f"{len(long_fmt['varying_columns'])} varying column(s) were "
                "still compared."
            )
        # Every header in THIS file, so the telemetry screen can ask whether it
        # is looking at a survey-platform export before it trusts an ambiguous
        # name like "duration".
        seg_names = [_column_name(seg, ci) for ci in cols]
        seg_is_platform_export = _looks_like_platform_export(seg_names)
        for c, values in cols.items():
            key = (s_idx, c)
            name = _column_name(seg, c)
            if name.strip().lower() in excluded_norm or name.strip().lower() in {
                x.strip().lower() for x in seg.exclude_columns
            }:
                excluded[key] = "excluded by caller (shared-by-design)"
                continue
            if c in long_repeated:
                excluded[key] = (
                    f"repeats once per block in long format "
                    f"({long_fmt['n_blocks']} x {long_fmt['period']} rows)"
                )
                continue
            if _geocode_name_candidate(name):
                # EXCLUDED outright when confirmed, unlike telemetry. A
                # page-submit time is a real measurement of a real event and can
                # corroborate a copied row; a ZIP is a categorical label whose
                # digits carry no measurement precision at all, so it can
                # neither seed nor support a pair.
                #
                # BUT THE NAME NO LONGER DECIDES ALONE. The values must agree,
                # and a single fractional value refuses the exclusion. A kept
                # candidate is ANNOUNCED rather than silently kept, so a reader
                # can see the screen fired and was overruled by the evidence.
                if _values_look_like_codes(values):
                    excluded[key] = (
                        "geographic/administrative code (not a measurement) -- "
                        "name matched and every value is integral"
                    )
                    continue
                notes.append(
                    f"'{name}' matches the geographic-code screen by NAME but "
                    "its values are not all integral, so it was KEPT and "
                    "compared. A place code has no fractional part; a "
                    "measurement does."
                )
            _tel = _telemetry_name_candidate(name)
            if _tel == "ambiguous" and not seg_is_platform_export:
                # ANNOUNCED, not silently kept -- the same device as the
                # geographic screen. The reader sees that the name matched and
                # that the file overruled it.
                notes.append(
                    f"'{name}' matches the telemetry screen by NAME, but this "
                    "file carries no column a survey platform would have "
                    "written, so it was KEPT and may seed a pair. "
                    '"Duration" in a clinical file is a measurement.'
                )
            if _is_telemetry(name, seg_names):
                # CORROBORATING ONLY, NOT EXCLUDED. Two respondents on one
                # Chrome build is the instrument repeating itself -- but two
                # sharing a page-submit time of 226.971s are not, and those
                # millisecond floats are the most identifying numbers in a
                # Qualtrics export. Excluding them outright cost real
                # sensitivity: three participant rows copied into a corpus
                # file went from detectable to invisible, because 22 of the
                # high-information cells the duplicate shared were timers.
                # So these columns may CORROBORATE a pair seeded elsewhere,
                # and may never seed or stand alone.
                corroborating[key] = True
                continue
            # A numeric MINORITY in a text column is a parsing artifact: the
            # column means something the tool cannot read, and the few cells
            # that happen to parse are not measurements. Checked BEFORE the
            # constant/arithmetic screens, which would otherwise claim the
            # column for the wrong reason and hide why it was really dropped.
            n_text = seg.n_text.get(c, 0)
            if n_text and len(values) < n_text / 2:
                excluded[key] = "mixed text/number column (numeric minority)"
                continue
            if len(values) >= 3 and len(set(values)) == 1:
                excluded[key] = "constant column"
                continue
            n_distinct = len(set(values))
            # Fold the ratio test into the same signal the detectors consume:
            # a column whose values each recur dozens of times is a designed
            # parameter regardless of how many distinct levels it has.
            if len(values) >= _LOW_DIVERSITY_MIN_ROWS and n_distinct <= _LOW_DIVERSITY_RATIO * len(
                values
            ):
                n_distinct = min(n_distinct, _CATEGORICAL_MAX_DISTINCT)
            diversity[key] = n_distinct
            if len(values) >= 5:
                diffs = [b - a for a, b in zip(values, values[1:])]
                counts = Counter(_canon(d) for d in diffs)
                top, top_n = counts.most_common(1)[0]
                if top != 0 and top_n / len(diffs) >= _ARITH_RUN_FRACTION:
                    excluded[key] = "arithmetic run (index/ID column)"
                    continue
            sample = values[:10]
            derived_hits = sum(
                1
                for v in sample
                if _num_decimals(v) >= _DERIVED_MIN_DECIMALS
                and _derived_source_digits(v) is not None
            )
            if derived_hits >= max(2, len(sample) // 3):
                capped[key] = True
                notes.append(
                    f"column '{name}' in '{seg.label}' looks transformed "
                    "(fraction/sqrt/log); its precision was discounted"
                )
        # A column COMPUTED FROM two others is not independent evidence: a
        # chance tie on the inputs forces a tie in the output, and the scorer
        # would count one coincidence as two or three high-information
        # matches. Discounted on the same footing as a transform column.
        derived_cols, unfittable = _linearly_derived(cols, len(seg.rows))
        if unfittable:  # pragma: no cover - needs a singular float design
            notes.append(
                f"'{seg.label}': {len(unfittable)} column triple(s) could not "
                "be tested for a linear derivation (the least-squares design "
                "would not decompose); they are neither confirmed nor cleared"
            )
        for c_dep, (src_a, src_b) in derived_cols.items():
            k = (s_idx, c_dep)
            if k in excluded or capped.get(k):
                continue
            capped[k] = True
            notes.append(
                f"column '{_column_name(seg, c_dep)}' in '{seg.label}' is a "
                f"deterministic function of '{_column_name(seg, src_a)}' and "
                f"'{_column_name(seg, src_b)}'; its precision was discounted "
                "so one coincidence in the inputs is not counted twice"
            )

    return excluded, capped, notes, diversity, corroborating


def _linearly_derived(cols: dict, n_rows: int) -> dict:
    """Columns computed from two OTHERS by an exact linear formula.

    WHY. `_screen_columns` already discounts a column whose own values look
    transformed (fraction / sqrt / log). It has no notion of "column C is
    computed FROM columns A and B", and that is the shape that inflates
    row-pair evidence several-fold.

    MEASURED, on the CARS workbook: `QALY - SG` is exactly
    0.125*(`SG - V2`) + 0.125*(`SG - V7`) across all 193 rows, and the ORD and
    Bpost triples are the same shape. So the nine numeric columns are six
    inputs and three outputs. Any chance tie on a (V2, V7) input pair FORCES a
    17-significant-digit tie in the derived column, which the scorer reads as
    a third independent high-information match. One coincidence, counted three
    times.

    WHY LINEAR AND NOT MERELY FUNCTIONAL. The first attempt asked only whether
    C was a deterministic function of (A, B). That is very nearly vacuous: on
    low-cardinality data almost every column is "determined" by some pair, and
    the test capped 15 of this file's columns, dropping the whole finding to
    `consistent`. Requiring an EXACT linear fit -- residuals at floating-point
    noise across every row -- is the property a formula column actually has,
    and a coincidental dependency does not.

    Returns ({column_index: (source_a, source_b)}, unfittable), where
    `unfittable` lists (target, a, b) triples whose design would not decompose
    -- reported rather than dropped, so "no derived column found" cannot be
    confused with "the fit never ran".
    """
    idxs = [c for c, v in cols.items() if len(v) == n_rows]
    if len(idxs) < 3 or len(idxs) > _FD_MAX_COLS or n_rows < 12:
        return {}, []
    rows = min(n_rows, _FD_MAX_ROWS)
    data = {c: np.asarray(cols[c][:rows], dtype=float) for c in idxs}
    if any(not np.all(np.isfinite(v)) for v in data.values()):
        idxs = [c for c in idxs if np.all(np.isfinite(data[c]))]
        if len(idxs) < 3:
            return {}, []

    out: dict[int, tuple] = {}
    notes_unfittable: list[tuple] = []
    ones = np.ones(rows)
    for c in idxs:
        y = data[c]
        scale = float(np.max(np.abs(y))) or 1.0
        if float(np.ptp(y)) == 0.0:  # constant: nothing to explain
            continue
        # A 3-parameter fit through <= 3 distinct points is exact by
        # construction, so a binary or 3-level column is "linearly derived"
        # from anything. MEASURED: `Treatment Group` (values 1 and 2) came out
        # as a function of `Treatment cost` (values 2104.2 and 207.9) -- true,
        # degenerate, and not a formula. Demand the fit be over-determined.
        if len(set(y.tolist())) < 4:
            continue
        found = None
        others = [x for x in idxs if x != c]
        for i, a in enumerate(others):
            for b in others[i + 1 :]:
                if len({(p, q) for p, q in zip(data[a].tolist(), data[b].tolist())}) < 6:
                    continue
                A = np.column_stack([data[a], data[b], ones])
                try:
                    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
                except np.linalg.LinAlgError:
                    # A design that will not decompose cannot establish a
                    # derivation; recorded so "no derived column found" is not
                    # confused with "the fit never ran".
                    notes_unfittable.append((c, a, b))
                    continue
                if abs(coef[0]) < _FD_MIN_COEF or abs(coef[1]) < _FD_MIN_COEF:
                    continue
                resid = float(np.max(np.abs(A @ coef - y)))
                if resid / scale < _FD_RESIDUAL_TOL:
                    found = (a, b)
                    break
            if found:
                break
        if found:
            out[c] = found
    return out, notes_unfittable
