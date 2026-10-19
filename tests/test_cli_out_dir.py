"""The analyze output folder names its experiment: model AND pipeline
version. A same-model same-version folder already on disk (any date) is a
duplicate experiment, surfaced to the operator BEFORE any spend."""

from pathlib import Path

from forensic_metascience_ai_toolkit.cli import _analyze_out_dir
from forensic_metascience_ai_toolkit.version import __version__


class TestAnalyzeOutDir:
    def test_the_name_is_model_and_version_no_date(self, tmp_path):
        """The default going forward (Dan, 2026-08-22): the folder names its
        EXPERIMENT; when it ran lives in run_meta.analysed_at."""
        out, same = _analyze_out_dir(tmp_path, None, "grok-4.6")
        assert out.parent == tmp_path
        assert out.name == f"forensic_review_grok-4-6_v{__version__}"
        assert same == []

    def test_the_exact_name_existing_is_a_twin(self, tmp_path):
        (tmp_path / f"forensic_review_opus_v{__version__}").mkdir()
        _, same = _analyze_out_dir(tmp_path, None, "opus")
        assert [d.name for d in same] == [
            f"forensic_review_opus_v{__version__}"]

    def test_a_dated_variant_of_the_same_experiment_is_a_twin_too(self, tmp_path):
        (tmp_path / f"forensic_review_opus_v{__version__}_01_01_2026").mkdir()
        _, same = _analyze_out_dir(tmp_path, None, "opus")
        assert [d.name for d in same] == [
            f"forensic_review_opus_v{__version__}_01_01_2026"]

    def test_other_versions_and_models_are_not_twins(self, tmp_path):
        (tmp_path / "forensic_review_opus_v0.9.0_08_20_2026").mkdir()
        (tmp_path / f"forensic_review_sonnet_v{__version__}_08_20_2026").mkdir()
        _, same = _analyze_out_dir(tmp_path, None, "opus")
        assert same == [], (
            "a different version or model is a different experiment")

    def test_explicit_output_bypasses_the_check(self, tmp_path):
        (tmp_path / f"forensic_review_opus_v{__version__}_08_20_2026").mkdir()
        out, same = _analyze_out_dir(tmp_path, tmp_path / "here", "opus")
        assert out == tmp_path / "here" and same == []

    def test_a_pdf_paper_gets_the_stem_prefix(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        pdf = tmp_path / "paper.pdf"
        pdf.write_text("x")
        out, same = _analyze_out_dir(pdf, None, "opus")
        assert out.name == f"paper_forensic_review_opus_v{__version__}"
        Path(out.name).mkdir()
        _, same2 = _analyze_out_dir(pdf, None, "opus")
        assert len(same2) == 1

    def test_a_pdf_paper_is_reviewed_beside_the_pdf_not_in_cwd(self, tmp_path,
                                                                monkeypatch):
        elsewhere = tmp_path / "shell"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        pdf = tmp_path / "papers" / "paper.pdf"
        pdf.parent.mkdir()
        pdf.write_text("x")
        out, same = _analyze_out_dir(pdf, None, "opus")
        assert out == pdf.parent / f"paper_forensic_review_opus_v{__version__}"
        assert same == []
        out.mkdir()
        _, same2 = _analyze_out_dir(pdf, None, "opus")
        assert same2 == [out]

    def test_batch_shares_the_same_default_name(self):
        from forensic_metascience_ai_toolkit.cli import _versioned_review_dirname
        assert _versioned_review_dirname("grok-4.6") == \
            f"forensic_review_grok-4-6_v{__version__}"
