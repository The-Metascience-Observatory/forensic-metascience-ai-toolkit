"""The human verification gate, and what it does and does not license.

Two error classes, treated differently:

  MEASUREMENT error -- reading a value off correctly-identified marks. Bounded,
  computable from pixel geometry. A human gate does NOT reduce it.

  EXTRACTION error -- wrong figure, caption paired with the panel above rather
  than below, a three-panel figure treated as one, chart type misread. Not 4%
  errors; WRONG-OBJECT errors, and unbounded. A human gate near-eliminates them.

So verification does not relax the exact-arithmetic refusal, and these tests pin
that it does not. What it licenses is the coverage claim: "this outcome appears
only in Figure 3" currently depends on OUR extractor having enumerated
correctly, and if we missed a supplementary table that is a coverage accusation
against the paper which is actually our bug.
"""
import pytest

from forensic_metascience_ai_toolkit import registry as R
from metascience_observatory_image_analysis.extraction.figures import (
    AI_PROPOSED,
    HUMAN_VERIFIED,
    UNVERIFIED,
    load_annotations,
    to_annotation_project,
)


def _project(n=3, manual=(), panels=0):
    figs = []
    for i in range(1, n + 1):
        figs.append({
            "id": f"fig{i}", "label": f"Figure {i}", "pageNum": i,
            "caption": f"Figure {i}. Outcome by group (error bars = SEM).",
            "captionSource": "manual" if i in manual else "textlayer",
            "subfigures": [
                {"label": f"Figure {i}{c}", "caption": "panel", "captionSource": "manual"}
                for c in "ab"[:panels]
            ],
        })
    return {"schemaVersion": 2, "figures": figs}


class TestVerificationStatus:
    def test_untouched_is_not_confirmed(self):
        """'Not contradicted' is not 'confirmed'.

        Rounding one up to the other is how a rubber-stamped pass launders
        extraction error into apparent human confirmation -- worse than no gate,
        because the provenance record would then be false.
        """
        out = load_annotations(_project(3))
        assert out["verification"] == AI_PROPOSED
        assert out["n_human_verified"] == 0
        assert all(f["verification"] == AI_PROPOSED for f in out["figures"])

    def test_partial_verification_is_not_rounded_up(self):
        out = load_annotations(_project(3, manual=(1,)))
        assert out["n_human_verified"] == 1
        assert out["verification"] == AI_PROPOSED, "1 of 3 is not a verified pass"

    def test_full_verification(self):
        out = load_annotations(_project(3, manual=(1, 2, 3)))
        assert out["verification"] == HUMAN_VERIFIED
        assert out["n_human_verified"] == 3

    def test_empty_is_unverified_not_verified(self):
        assert load_annotations({"figures": []})["verification"] == UNVERIFIED

    def test_a_corrected_subfigure_verifies_its_parent(self):
        """Splitting a multi-panel figure IS the correction."""
        proj = _project(1)
        proj["figures"][0]["subfigures"] = [
            {"label": "Figure 1a", "caption": "A", "captionSource": "manual"}]
        out = load_annotations(proj)
        assert out["figures"][0]["verification"] == HUMAN_VERIFIED
        assert out["n_subfigures"] == 1


class TestRoundTrip:
    def test_emits_the_schema_the_tool_loads(self):
        proj = to_annotation_project({
            "paper_id": "10.1/x",
            "figures": [{"label": "Figure 1", "page": 3, "caption": "c",
                         "bbox": (10.0, 20.0, 110.0, 220.0)}],
        })
        assert proj["schemaVersion"] == 2
        f = proj["figures"][0]
        assert f["bounds"] == {"x": 10.0, "y": 20.0, "width": 100.0, "height": 200.0}
        assert f["subfigures"] == []

    def test_round_trips_without_loss(self):
        out = load_annotations(to_annotation_project({
            "paper_id": "p",
            "figures": [{"label": "Figure 1", "page": 1, "caption": "x", "bbox": None}],
        }))
        assert out["n_figures"] == 1

    def test_error_bar_meaning_survives_the_round_trip(self):
        out = load_annotations(_project(1))
        assert out["figures"][0]["error_bar_meaning"] == "SEM"


class TestVerificationDoesNotRelaxTheRefusal:
    """The tempting wrong conclusion, pinned shut.

    A human confirming WHICH FIGURE a crop came from does not make a bar height
    into a number the authors asserted, and does not change its sigma. Even
    human-verified vector extraction reaches only ~0.1% of axis range -- sigma
    ~0.006 against GRIM's 0.005 window, which is a ~40% false-positive rate, not
    an acceptable one.
    """

    @pytest.mark.parametrize("name", [s.name for s in R.SPECS if s.is_exact_check()])
    def test_exact_checks_refuse_regardless_of_verification(self, name):
        spec = R.BY_NAME[name]
        param = sorted(spec.exact_params())[0]
        out = spec.call({param: 1.0, "uncertainty": {param: 0.006},
                         "provenance": "measured_vector"})
        assert out["severity"] == "indeterminate"
        assert out["applicable"] is False

    def test_a_numeral_read_off_a_verified_figure_is_still_printed(self):
        """The channel the gate DOES open.

        A human transcribing `n = 32` from a panel is not measuring, they are
        reading. That is a printed value, tier 0, and no check refuses it. The
        split the gate implements is as-printed vs MEASURED, not text vs figure,
        so `printed_figure` has to reach the same verdict `printed_text` does --
        anything less trades a false accusation for a false all-clear.

        `decimals` is supplied because it became a no-default guard on
        2026-08-07 (the old default of 2 read "5.9" as "5.90" and returned a
        false `impossible` on 41.1% of GRIM rows). That refusal is a DIFFERENT
        gate -- unknown printed precision -- and leaving it to fire here would
        have hidden whether the figure gate still passes a printed value.
        """
        printed = {"mean": 5.51, "n": 30, "data_type": "likert", "decimals": 2,
                   "discreteness_source": "stated"}
        out = R.BY_NAME["grim_check"].call({**printed, "provenance": "printed_figure"})
        assert out["severity"] == "impossible"
        assert out["applicable"] is True

    def test_printed_in_a_figure_and_printed_in_the_text_agree(self):
        """The gate keys on MEASURED, so where a printed numeral sits is not a
        severity input. Pinned separately because an over-broad refusal would
        leave the test above passing on `printed_text` alone."""
        printed = {"mean": 5.51, "n": 30, "data_type": "likert", "decimals": 2,
                   "discreteness_source": "stated"}
        verdicts = {p: R.BY_NAME["grim_check"].call({**printed, "provenance": p})["severity"]
                    for p in ("printed_text", "printed_table", "printed_figure")}
        assert set(verdicts.values()) == {"impossible"}, verdicts


class TestDefaultOff:
    def test_analyze_defaults_to_no_figures(self):
        """An unverified figure pass can make a report WORSE, so it is opt-in."""
        src = (R.__file__.rsplit("/", 1)[0] + "/cli.py")
        text = open(src, encoding="utf-8").read()
        assert '"--figures/--no-figures"' in text
        assert "figures: bool = typer.Option(False" in text
