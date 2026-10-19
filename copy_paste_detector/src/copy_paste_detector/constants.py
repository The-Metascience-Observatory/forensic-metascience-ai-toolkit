"""Thresholds and recognition patterns; preserved from the original detector."""

from __future__ import annotations

import re

from .severity import (
    CONSISTENT,
    HIGHLY_SUSPICIOUS,
    INDETERMINATE,
    SUSPICIOUS,
)

# ---------------------------------------------------------------------------
# Tunables. Pinned by tests/test_raw_duplication.py; derived from this corpus,
# not copied from anyone else's.
# ---------------------------------------------------------------------------

#: Coverage caps. NEVER silent: exceeding one adds a caveat naming what was
#: dropped, because a truncated sweep that reads as complete is the failure
#: mode this repo's invariants exist to prevent.
_MAX_SHEETS = 8

_MAX_ROWS = 5000

_MAX_COLS = 100

#: A value seeds a row-pair candidate only with >= this many significant
#: digits of information (post-discount). Below that, coincidences dominate.
_SEED_MIN_DIGITS = 3

#: ... and only when it occurs in <= this many rows of its column. A value
#: present everywhere is ambient (a category code, a plate number), not a seed.
_MAX_SEED_OCCURRENCES = 100

#: A standalone repeated value is reportable only at >= this many digits.
_VALUE_MIN_DIGITS = 4

#: Row pairs must share at least this many distinct value-carrying columns.
_MIN_SHARED_COLS = 2

#: Vertical runs must be at least this long (3, stricter than the minimum
#: conceivable 2: two-value runs recur constantly in blocked designs).
_MIN_RUN = 3

#: Comparison budget; exceeding it truncates LOUDLY (caveat).
_MAX_ROW_PAIRS = 5000

#: Integers in this range are calendar years; they carry ~no information.
_YEAR_RANGE = (1880, 2100)

#: Repeating-fraction denominators worth testing (thirds, sevenths, ninths...).
_FRACTION_DENOMS = (3, 6, 7, 9, 11, 13, 17, 19, 21, 23)

#: Terminating-decimal denominators (halves/quarters/eighths).
_TERMINATING_DENOMS = (2, 4, 8)

#: Derived-form detection needs at least this many printed decimals — short
#: decimals match some fraction by accident.
_DERIVED_MIN_DECIMALS = 4

#: Exact-rational reconstruction bound: a long decimal that IS p/q for q up
#: to this (a percentage of n=29, a ratio of two counts) carries only its
#: numerator's information. Matched at the float/canonicalization noise
#: floor, so honest 4-6 dp MEASUREMENTS never trip it.
_RATIONAL_MAX_DENOM = 999

#: Score ladders (score = information-weighted, size-normalized; see
#: `_size_norm`). Rows and sequences share a ladder; standalone values have
#: their own (they are weaker evidence at the same score).
_LINE_HS, _LINE_S, _LINE_IND = 5.0, 2.5, 1.2

_VALUE_HS, _VALUE_S, _VALUE_IND = 5.0, 2.6, 2.0

#: `data_context` values. Pooled data duplicates rows by construction.
_CONTEXTS = ("raw_participant_level", "pooled_or_meta_analysis", "unknown")

#: A column is treated as an index/ID run when this fraction of its consecutive
#: differences share one value (1.0 = perfect arithmetic progression).
_ARITH_RUN_FRACTION = 0.9

#: Diversity guard (see the repeated-value detector). A column holding at most
#: this many distinct values is categorical enough that the uniform-digit model
#: behind the Poisson gate does not apply to it. Set well above Likert/condition
#: widths but far below any real measurement column.
_CATEGORICAL_MAX_DISTINCT = 40

#: ...and the value must recur at least this many times PER distinct value
#: before the model is treated as falsified. A 6-value column over 2,600 rows
#: is ~440x; a genuine pair of copy-pasted measurements is nowhere near.
_CATEGORICAL_COUNT_RATIO = 4

#: Instrument telemetry may seed a row pair only at this precision or above.
#: A click count of 1.0 or a browser build shared by two respondents is the
#: platform repeating itself; a page-submit time agreeing to the millisecond
#: is not. Set above any plausible count/version and at the precision
#: Qualtrics writes its timers (3 decimals).
_TELEMETRY_SEED_DIGITS = 5

#: The same test by RATIO, for wide columns the absolute cap cannot reach. A
#: designed parameter (an experimental tax on a fixed grid: ~117 levels, each
#: recurring ~135 times) is drawn from a menu, so every value recurs by
#: design -- but 117 is far above _CATEGORICAL_MAX_DISTINCT. What marks it is
#: the recurrence rate, not the level count. Deliberately conservative: this
#: suppresses evidence, so it must not reach a column of real measurements.
_LOW_DIVERSITY_RATIO = 0.025

_LOW_DIVERSITY_MIN_ROWS = 400

#: Diffuse-evidence cap. Copy-paste is local; findings smeared across this
#: fraction of a file's included columns say more about the tool's grasp of
#: the file than about the data. Only applied to files wide enough for the
#: fraction to mean anything.
_DIFFUSE_COLUMN_FRACTION = 0.6

_DIFFUSE_MIN_COLUMNS = 8

#: A finding at or above this adjusted score is exempt from the diffuse cap:
#: the ladder's own `highly_suspicious` line, not a second threshold invented
#: beside it. Measured on the corpus, the separation is wide and the boundary
#: belongs in the gap rather than inside either group -- a file's diffuse
#: background of shared Likert 1s tops out at 1.37, while participant rows
#: copied into it score 5.1-13.7. An earlier 1.5x value (7.5) cut through the
#: MIDDLE of that cluster, passing a planted duplicate at 8.05 and demoting
#: its twin at 7.44, which is an arbitrary line dressed as a principled one.
#: Doubt about a file's overall shape is not grounds to demote a finding the
#: ladder already calls highly suspicious; that is how the real one gets hidden.
_DIFFUSE_EXEMPT_SCORE = _LINE_HS

_HAS_ALPHA = re.compile(r"[A-Za-z]")

#: A comma is a thousands separator ONLY in this shape. Anything else carrying
#: a comma is a LIST, not a number: Qualtrics stores task-order permutations as
#: "1,2,4,3", which has no letters and so passes _HAS_ALPHA. Stripping commas
#: unconditionally turned that ordering into the integer 1243 -- four digits of
#: fabricated precision from a 4-item permutation. Measured on one corpus file:
#: 10 of 208 columns became numeric this way and produced 48% of its findings.
_THOUSANDS = re.compile(r"^[+-]?\d{1,3}(,\d{3})+(\.\d+)?$")

#: Columns the SURVEY PLATFORM wrote, not the participant. Two respondents on
#: one Chrome build, or who both took 3.7s on a page, is the instrument
#: repeating itself. This is name-based screening, which this module otherwise
#: avoids (value shape is more honest than headers) -- justified here because
#: the alternative is worse: these columns supplied 52% of one corpus file's
#: findings, and no value-shape test distinguishes a click count from a
#: measurement. Screening only ever EXCLUDES; it never raises suspicion, and
#: every exclusion is named in `excluded_columns` so a reader can override it.
#: SPLIT 2026-08-18. These names LOCATE a telemetry candidate; whether the
#: column really was written by a survey platform is judged separately, because
#: half the old list is ordinary clinical vocabulary. "Sleep duration (h)",
#: "Symptom Duration (days)" and "Exercise duration min" were all screened as
#: instrument telemetry and barred from seeding a duplicate pair -- and in a
#: duration-heavy clinical dataset those are the highest-information columns
#: there are.
#:
#: PLATFORM: names a survey platform emits and a researcher does not. No
#: clinical variable is called "Distribution Channel" or "Page Submit". A match
#: here is decisive on its own.
_TELEMETRY_PLATFORM = (
    "page submit",
    "first click",
    "last click",
    "click count",
    "user agent",
    "useragent",
    "operating system",
    "screen resolution",
    "response id",
    "distribution channel",
    "user language",
    "ip address",
    "recorded date",
    "browser",
)

#: AMBIGUOUS: real English words that name real measurements. A match here is a
#: candidate, not a verdict -- it counts only when the file ALSO carries a
#: PLATFORM column, i.e. when the file demonstrably IS a platform export. That
#: is the judge: not the shape of one header, but whether the export it sits in
#: is one a platform wrote.
_TELEMETRY_AMBIGUOUS = (
    "timer",
    "duration",
    "version",
    "progress",
    "finished",
    "start date",
    "end date",
    "latitude",
    "longitude",
)

_TELEMETRY_PATTERNS = _TELEMETRY_PLATFORM + _TELEMETRY_AMBIGUOUS

#: Geographic and administrative CODES. Digits that identify a PLACE, not a
#: measurement of one: a ZIP is a label that happens to be written in numerals.
#: No value-shape test can catch these -- 29681 has five significant digits and
#: looks exactly like a high-precision measurement, which is the whole problem.
#: Measured on `study1b_data.csv` (PNAS 2217551120, 1,818 respondents across 565
#: distinct ZIPs): the `zip` column alone produced 469 of the file's 471
#: repeated-value groups and drove the verdict to `suspicious`. Two people
#: living in the same town is not duplicated data.
#:
#: Screening only ever EXCLUDES, exactly as for telemetry, and names itself in
#: `excluded_columns` so a reader can override it. Matching is on whole tokens,
#: not substrings, because "zip" inside "zipf_rank" or "fips" inside "fipsize"
#: would silently drop a real measurement -- an exclusion that hides a finding
#: is as bad as a false one.
#: `tract` WAS IN THIS SET ON ITS OWN AND HAD TO COME OUT. Measured 2026-08-18:
#: a column headed `corticospinal tract FA` or `tract volume mm3` matched it and
#: was dropped from every comparison. This repository's own corpus is 309
#: NEUROSCIENCE papers, where white-matter tract measurements are among the most
#: commonly tabulated numbers there are -- so the exclusion built to stop two
#: neighbours sharing a postcode was silently removing the measurements most
#: likely to carry fabricated data. `census_tract` stays; the bare token cannot.
_GEOCODE_NAMES = frozenset(
    {
        "zip",
        "zipcode",
        "zip_code",
        "postcode",
        "postal",
        "postal_code",
        "fips",
        "fips_code",
        "geoid",
        "msa",
        "cbsa",
        "census_tract",
        "county_code",
        "state_code",
        "country_code",
        "area_code",
        "block_group",
    }
)

#: Splits a header into tokens so whole-token matching survives the usual
#: naming styles (`ZIP Code`, `zip_code`, `zip.code`, `zipCode`).
_NAME_TOKENS = re.compile(r"[^a-z0-9]+")

#: Severity ladder, most severe first (index comparisons: lower = worse).
_TIERS = [HIGHLY_SUSPICIOUS, SUSPICIOUS, INDETERMINATE, CONSISTENT]

#: Headers that mark a file as MODEL OUTPUT rather than participant data.
_STATS_OUTPUT_RE = re.compile(
    r"^\s*(beta|se|std\.?\s*err\w*|t.?value|p.?value|r.?squared|estimate|"
    r"ci.?(lower|upper)|conf\.?\s*(low|high)|z.?value|odds.?ratio)\s*$",
    re.I,
)

#: ...and as an AGGREGATE/summary table. A LOCATOR ONLY: "Mean RT",
#: "Total Score" and "Percent Correct" are per-participant columns, and a
#: 120-row participant-level supplement with headers
#: `ID, Mean RT, Total Score, Percent Correct` was declared an aggregate table
#: -- 3 of 4 headers matched and the row count was under the ceiling -- which
#: caps every duplication finding in it at `indeterminate`. What the words name
#: is a statistic; what makes a table an aggregate is one row per GROUP.
#: `_IDENTIFIER_RE` below is what asks that question.
_AGGREGATE_RE = re.compile(
    r"(^|\b)(%\s*of|percent|number of|count|frequency|mean|median|total)\b", re.I
)

#: A column that identifies the UNIT OF OBSERVATION. Its presence means one row
#: per person (or animal, or sample), which is what participant-level data is,
#: and it settles the question the header words cannot.
#:
#: Deliberately narrow. A bare `No.`, `Index` or `Row` is NOT accepted, because
#: aggregate tables carry row numbers too and the cap is the conservative
#: setting -- losing it wrongly lets a finding keep a severity it has not
#: earned, which is the direction that ends in a false accusation.
_IDENTIFIER_RE = re.compile(
    r"^(?:id|ids|uid|pid|sid|subj|subject|participant|patient)$|"
    r"\b(?:subject|participant|patient|respondent|case|record|sample|animal|"
    r"mouse|rat|donor|student|subj|ppt)\s*(?:id|no|number|code)\b|"
    r"\b(?:id|uid)\b",
    re.I,
)

#: A long-format block must repeat at least this many times before the shape is
#: called structural. Two blocks is also what a file duplicated ONCE looks like,
#: which is the thing this module exists to catch; three or more with the same
#: period is a reshape.
_LONG_FORMAT_MIN_BLOCKS = 3

#: How many columns must be IDENTICAL across every block. A COUNT, not a
#: fraction: a first attempt required 30% and missed the case it was written
#: for. `study1a_data.csv` repeats 2 of 10 numeric columns (20%) because most
#: of its columns are per-condition outcomes, which is what long format is FOR
#: -- the richer the design, the smaller the invariant share, so a fraction
#: gets stricter exactly as the evidence gets stronger. Two columns repeating
#: identically across three 550-row blocks is already a 1650-cell coincidence.
_LONG_FORMAT_MIN_REPEATED = 2

#: ...and at least this many must VARY. A file where everything repeats is not
#: long format, it is a duplicated file, and it must stay detectable.
_LONG_FORMAT_MIN_VARYING = 1

#: Bounds on the derived-column search below: it is O(k^3 * rows), so cap the
#: columns considered and sample the rows.
_FD_MAX_COLS = 16

_FD_MAX_ROWS = 400

#: Relative residual below which C = aA + bB + c is treated as EXACT. A
#: spreadsheet formula reproduces to floating-point noise; a real-world
#: correlation, however tight, does not.
_FD_RESIDUAL_TOL = 1e-9

#: Both source coefficients must matter. Otherwise a two-source "derivation"
#: is really a single-source scaling, which the transform detector owns.
_FD_MIN_COEF = 1e-12
