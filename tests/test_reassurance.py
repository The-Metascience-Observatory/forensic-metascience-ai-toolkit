"""Reassurance language is flagged by the pipeline, not only by the eval."""

from forensic_metascience_ai_toolkit import reassurance
from tests.test_parallel_pipeline import fakes, paper  # noqa: F401


def test_the_measured_phrase_and_the_fixture_phrases_are_caught():
    rows = [{"slug": "a", "title": "Table 1 baseline", "description":
             "The baseline dispersion is consistent with randomisation."},
            {"slug": "b", "title": "x", "description": "The patient flow reconciles."},
            {"slug": "c", "title": "GRIM", "description": "Mean 3.53 is impossible for n=30."}]
    hits = reassurance.scan(rows, {"summary": "Overall the results are sound."})
    assert [(h["slug"], h["field"]) for h in hits] == [
        ("a", "description"), ("b", "description"), ("adjudication.summary", "summary")]
    assert all(h["code"] == "reassurance_language" for h in hits)


def test_an_accusation_is_not_reassurance():
    rows = [{"slug": "x", "title": "Baseline too similar", "description":
             "Table 1 p-values of 0.93-0.99 are far more similar than randomization produces."}]
    assert reassurance.scan(rows) == []


def test_every_fixture_pattern_is_covered():
    """The eval's per-fixture must_not_say nets live here too, generalised."""
    import pathlib
    import re
    import yaml
    root = pathlib.Path(__file__).resolve().parents[1] / "benchmarks" / "paper_reviews" / "fixtures"
    samples = {
        "statistics (are|were|appear)[^.]*\\bconsistent\\b and (verifiable|reproducible)":
            "the statistics are all consistent and verifiable",
        "results (are|appear) (sound|trustworthy)": "results appear trustworthy",
        "no (significant|notable) (anomalies|inconsistencies) (were )?found":
            "no notable anomalies were found",
        "baseline (characteristics|values|comparisons|dispersion|similarity)[^.]*\\bconsistent\\b":
            "baseline values are consistent",
        "no suspicious uniformity": "no suspicious uniformity",
        "groups (were|are) well[- ]balanced": "groups were well balanced",
        "consistent with random (allocation|assignment)": "consistent with random allocation",
        "consistent with randomi[sz]ation": "consistent with randomisation",
        "(animal|patient) flow[^.\\n]{0,60}(reconciles|consistent|accounted for)\\b":
            "animal flow reconciles",
    }
    # Fixture-specific false ACCUSATIONS, not reassurance; the eval keeps them.
    accusations = {"apple_cider.yaml"}
    for f in root.glob("*.yaml"):
        for pat in yaml.safe_load(f.read_text()).get("must_not_say") or []:
            if f.name in accusations and "impossible" in pat:
                continue
            text = samples[pat]
            assert re.search(pat, text, re.I)
            assert reassurance.scan([{"slug": "s", "description": text}]), (f.name, pat)


def test_a_discarded_row_is_not_flagged():
    row = {"slug": "d", "description": "consistent with randomisation",
           "adjudication": {"action": "discarded"}}
    assert reassurance.scan([row]) == []


def test_the_pipeline_records_it(paper, fakes):  # noqa: F811
    """Wired, not just written: the flag reaches findings.v2 and the report."""
    from tests.test_parallel_pipeline import _doc, _row, _stage, run
    fakes["tool"] = _stage(_doc([_row(
        "t1", description="Table 1 baseline dispersion is consistent with "
                          "randomisation, with the numbers inline")]))
    res = run(paper)
    probs = [p for p in res["findings_v2"]["producer_constraint_problems"]
             if p.get("code") == "reassurance_language"]
    assert [p["slug"] for p in probs] == ["t1"]
    assert any("reassurance" in l for l in res["limitations"])
