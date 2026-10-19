"""Red-team regressions for detect_raw_duplication (audit 2026-08-09).

Every test in TestHonestDataMustNotBeAccused reproduces an HONEST dataset
that the pre-audit implementation accused (suspicious or worse) or crashed
on. The fix direction is always REFUSAL: indeterminate or consistent, never
an accusatory severity built on our own assumption or defect.

TestSensitivityPins documents what the fixes deliberately did NOT weaken,
plus the two disclosed sensitivity reductions (block-structure cap,
matched-design cap) so any future recalibration is a visible choice.
"""

from __future__ import annotations

import csv
import math
import random

from copy_paste_detector import detect_raw_duplication
from copy_paste_detector.scoring import _info_digits

ORDER = ["highly_suspicious", "suspicious", "indeterminate", "consistent"]


def _write_csv(path, rows):
    with path.open("w", newline="") as fh:
        csv.writer(fh).writerows(rows)
    return str(path)


def _not_accusatory(res):
    assert ORDER.index(res["severity"]) >= ORDER.index("indeterminate"), (
        f"honest data was accused: {res['severity']}; "
        f"groups={[(g['kind'], g['severity']) for g in res['duplicate_groups'][:5]]}"
    )


class TestInfoDigitsRational:
    def test_exact_small_denominator_rational_scored_as_numerator(self):
        # 7/29 as a percentage: full-float export of a derived column.
        assert _info_digits(7 / 29 * 100) <= 2
        assert _info_digits(13 / 41 * 1000) <= 3

    def test_irrational_full_precision_keeps_its_digits(self):
        # pi is NOT within float noise of any p/q with q <= 999.
        assert _info_digits(math.pi) >= 10

    def test_short_honest_measurements_untouched(self):
        assert _info_digits(413.762) == 6


class TestHonestDataMustNotBeAccused:
    def test_derived_percentage_odd_denominator(self, tmp_path):
        # Event counts out of n=29 with the software-exported full-precision
        # percentage. Two subgroups happening to share k=7 is ordinary; the
        # pct match is arithmetic necessity, not duplication. Pre-audit:
        # suspicious (row_pair on events+pct, adjusted 3.67).
        ks = [3, 7, 12, 5, 9, 7, 14, 2, 11, 6, 8, 10]
        rows = [["subgroup", "events", "pct"]]
        for i, k in enumerate(ks, 1):
            rows.append([i, k, k / 29 * 100])
        _not_accusatory(detect_raw_duplication(_write_csv(tmp_path / "p.csv", rows)))

    def test_two_derived_columns_never_highly_suspicious(self, tmp_path):
        # Same, plus a rate-per-1000 column derived from the SAME count.
        # Pre-audit: highly_suspicious -- the worst possible false accusation,
        # produced entirely by our hardcoded fraction-denominator list.
        ks = [3, 7, 12, 5, 9, 7, 14, 2, 11, 6, 8, 10]
        rows = [["subgroup", "events", "pct", "rate_per_1000"]]
        for i, k in enumerate(ks, 1):
            rows.append([i, k, k / 29 * 100, k / 29 * 1000])
        _not_accusatory(detect_raw_duplication(_write_csv(tmp_path / "p3.csv", rows)))

    def test_site_covariate_blocks(self, tmp_path):
        # Ecology design: 4 sites x 10 individuals; 5-dp GPS, rainfall,
        # elevation, temperature identical within site BY DESIGN. Pre-audit:
        # suspicious row pairs despite the per-value covariate discount.
        rng = random.Random(42)
        rows = [["id", "site", "lat", "lon", "rainfall_mm", "elev_m", "temp_c", "mass_g"]]
        sites = [
            (45.12345, -71.23456, 123.4567, 312.5, 18.34),
            (45.98761, -71.87652, 98.7654, 287.5, 17.92),
            (46.54327, -72.12348, 156.7891, 401.0, 16.55),
            (44.87659, -70.98761, 111.2233, 350.5, 19.01),
        ]
        i = 0
        for s, (lat, lon, rain, elev, t) in enumerate(sites, 1):
            for _ in range(10):
                i += 1
                rows.append([i, s, lat, lon, rain, elev, t, round(rng.uniform(1, 9), 3)])
        res = detect_raw_duplication(_write_csv(tmp_path / "eco.csv", rows))
        _not_accusatory(res)
        pairs = [g for g in res["duplicate_groups"] if g["kind"] == "row_pair"]
        assert pairs, "covariate blocks should still be VISIBLE (as refusals)"
        # every pair refused; at least one was actively lowered by the cap
        assert all(ORDER.index(g["severity"]) >= ORDER.index("indeterminate") for g in pairs)
        assert any(g.get("column_mass_capped") for g in pairs)

    def test_low_cardinality_sequences_are_chance(self, tmp_path):
        # Two 1-dp body-temperature columns: ~25-value support, so 3-4 long
        # matching runs occur by pigeonhole. Pre-audit: suspicious in 6 of 50
        # seeds (this seed among them). The sequence chance gate must absorb
        # them the way the Poisson gate absorbs repeated values.
        for seed in (13, 16, 0):
            rng = random.Random(seed)
            rows = [["id", "temp_day1", "temp_day2"]]
            for i in range(1, 101):
                rows.append([i, round(rng.gauss(37.0, 0.4), 1), round(rng.gauss(37.0, 0.4), 1)])
            res = detect_raw_duplication(_write_csv(tmp_path / f"t{seed}.csv", rows))
            _not_accusatory(res)

    def test_matched_pair_design_capped_with_named_caveat(self, tmp_path):
        # 25 case-control pairs matched on age/bmi/sbp/baseline score: every
        # pair duplicates its matching covariates BY DESIGN. Pre-audit:
        # suspicious with 25 row-pair groups.
        rng = random.Random(21)
        rows = [["pair", "case", "age", "bmi", "sbp", "baseline_score", "outcome"]]
        for p in range(1, 26):
            age = rng.randint(35, 75)
            bmi = round(rng.uniform(19, 34), 1)
            sbp = rng.randint(100, 165)
            base = round(rng.uniform(10, 99), 2)
            for case in (1, 0):
                rows.append([p, case, age, bmi, sbp, base, round(rng.uniform(0.1, 9.9), 2)])
        res = detect_raw_duplication(_write_csv(tmp_path / "m.csv", rows))
        _not_accusatory(res)
        assert any("matched" in c for c in res["caveats"])
        assert any(g.get("design_structure_capped") for g in res["duplicate_groups"])


class TestDegenerateInputsRefuse:
    def test_infinite_cell_does_not_crash(self, tmp_path):
        # A 400-digit cell parses to float('inf'); pre-audit this raised
        # OverflowError out of _canon -- our defect surfacing mid-analysis.
        rows = [["a", "b"], ["9" * 400, 1.23], [2.34, 4.56], [3.45, 5.67]]
        res = detect_raw_duplication(_write_csv(tmp_path / "inf.csv", rows))
        assert res["severity"] in ORDER
        assert res.get("error") is None

    def test_single_data_row_refuses(self, tmp_path):
        # One row compared against nothing must not report "consistent"
        # (a clean bill from zero comparisons); it must refuse.
        rows = [["a", "b"], [1.234, 5.678]]
        res = detect_raw_duplication(_write_csv(tmp_path / "one.csv", rows))
        assert res["severity"] == "indeterminate"
        assert "one" in res["error"]

    def test_all_columns_excluded_refuses(self, tmp_path):
        # 30 identical rows: every column is constant, so everything is
        # excluded and NOTHING was compared. Pre-audit: "consistent".
        rows = [["a", "b"]] + [[1.2345, 6.789]] * 30
        res = detect_raw_duplication(_write_csv(tmp_path / "ident.csv", rows))
        assert res["severity"] == "indeterminate"
        assert "excluded" in res["error"]

    def test_exclude_columns_accepts_bare_string(self, tmp_path):
        # Pre-audit a bare string iterated as characters and the exclusion
        # the caller EXPLICITLY declared was silently dropped.
        rng = random.Random(5)
        rows = [["id", "site", "rainfall_mm", "mass_g"]]
        for i in range(1, 41):
            rows.append(
                [
                    i,
                    1 if i <= 20 else 2,
                    123.4567 if i <= 20 else 88.1234,
                    round(rng.uniform(1, 9), 3),
                ]
            )
        res = detect_raw_duplication(
            _write_csv(tmp_path / "wx.csv", rows), exclude_columns="rainfall_mm"
        )
        assert any("shared-by-design" in c for c in res["excluded_columns"])
        assert res["severity"] == "consistent"


class TestSensitivityPins:
    def test_planted_pair_is_not_block_capped(self, tmp_path):
        # A single copied row keeps count-2 values everywhere: neither the
        # block-structure cap nor the matched-design cap may touch it.
        rng = random.Random(7)
        rows = [["id", "group", "weight_kg", "cortisol_nmol"]]
        for i in range(1, 61):
            rows.append(
                [i, (i % 3) + 1, round(rng.uniform(52, 96), 2), round(rng.uniform(180, 620), 3)]
            )
        rows[47] = [47, rows[12][1], rows[12][2], rows[12][3]]
        res = detect_raw_duplication(_write_csv(tmp_path / "d.csv", rows))
        assert res["severity"] in ("suspicious", "highly_suspicious")
        pairs = [g for g in res["duplicate_groups"] if g["kind"] == "row_pair"]
        assert pairs and not pairs[0]["column_mass_capped"]
        assert not pairs[0].get("design_structure_capped")

    def test_contiguous_block_duplication_still_highly_suspicious(self, tmp_path):
        # Wholesale contiguous duplication of a 50-row block: the row pairs
        # are design-capped (the matched-design shape), but the 50-long
        # column sequences keep it at highly_suspicious. Pinned so the
        # strongest genuine signal is never silently lost.
        rng = random.Random(9)
        base = [[round(rng.uniform(10, 99), 4) for _ in range(6)] for _ in range(50)]
        rows = [["a", "b", "c", "d", "e", "f"]] + base + [r[:] for r in base]
        res = detect_raw_duplication(_write_csv(tmp_path / "w.csv", rows))
        assert res["severity"] == "highly_suspicious"
        assert any(
            g["kind"] == "column_sequence" and g["severity"] == "highly_suspicious"
            for g in res["duplicate_groups"]
        )

    def test_sequence_gate_reports_its_chance_number(self, tmp_path):
        # Reported sequences must carry the chance expectation they beat,
        # so the editorial stage can audit the null, mirroring
        # chance_expected_repeats on repeated values.
        rng = random.Random(7)
        rows = [["id", "group", "weight_kg", "cortisol_nmol"]]
        for i in range(1, 61):
            rows.append(
                [i, (i % 3) + 1, round(rng.uniform(52, 96), 2), round(rng.uniform(180, 620), 3)]
            )
        for k in range(5):
            rows[20 + k][2] = rows[40 + k][3]
        res = detect_raw_duplication(_write_csv(tmp_path / "s.csv", rows))
        seqs = [g for g in res["duplicate_groups"] if g["kind"] == "column_sequence"]
        assert seqs and all("chance_expected_runs" in g for g in seqs)
        assert res["severity"] == "highly_suspicious"
