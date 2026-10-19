"""pass@K across DIFFERENT papers is arithmetic that answers nothing.

FOUND 2026-08-18 while looking at something else. Pointing `find_runs` at
`funder_demo_2026-08-10/reviews` -- a directory holding reviews of THREE
different papers -- produced:

    pass@1 bracketed 26%-41%
    note: "ONE RUN SURFACES BETWEEN 26% AND 41% of what the pipeline is capable
           of finding on this paper"

There was no "this paper". Every cluster appeared in exactly one run because no
two runs had seen the same text, which is precisely the shape a genuinely poor
reliability result takes -- so the number looked plausible, cited a method, and
meant nothing.

The caller error was mine. The silence was the module's, and that is what these
tests fix: a metric defined over repeated runs of one paper must refuse a set
that is not that, rather than computing something.

`measurable: False` rather than an exception, deliberately, and matching the
convention used by `supplements.audit` and `tripwire`: a question that could not
be asked is a third state, never a pass and never a failure.
"""
import json

import pytest

from metascience_agent.evaluation.agreement import from_review_dirs


def _run(tmp, name, paper_id, findings):
    d = tmp / name
    d.mkdir(parents=True)
    (d / "findings.json").write_text(json.dumps({"findings": findings}),
                                     encoding="utf-8")
    if paper_id is not None:
        (d / "run_meta.json").write_text(json.dumps({"paper_id": paper_id}),
                                         encoding="utf-8")
    return d


F1 = [{"id": "1", "severity": "suspicious", "location": "Table 1, age row",
       "technique": "grim"}]
F2 = [{"id": "2", "severity": "suspicious", "location": "Table 2, BMI row",
       "technique": "grimmer"}]


class TestAMixedSetIsRefused:
    def test_two_papers_are_not_measurable(self, tmp_path):
        dirs = [_run(tmp_path, "a", "10.1/x", F1),
                _run(tmp_path, "b", "10.2/y", F2)]
        r = from_review_dirs([str(d) for d in dirs])
        assert r["measurable"] is False
        assert r["pass_at_1_bracket"] is None

    def test_the_note_names_the_papers(self, tmp_path):
        """An operator has to be able to see WHICH set they handed over."""
        dirs = [_run(tmp_path, "a", "10.1/x", F1),
                _run(tmp_path, "b", "10.2/y", F2)]
        note = from_review_dirs([str(d) for d in dirs])["note"]
        assert "DIFFERENT papers" in note
        assert "10.1/x" in note and "10.2/y" in note

    def test_no_pass_at_k_figure_is_offered_at_all(self, tmp_path):
        """Not a low number with a caveat -- no number. A caveat beside a
        plausible figure is how the figure gets quoted."""
        dirs = [_run(tmp_path, "a", "10.1/x", F1),
                _run(tmp_path, "b", "10.2/y", F2)]
        r = from_review_dirs([str(d) for d in dirs])
        assert "all_findings" not in r and "accusations" not in r


class TestRepeatedRunsOfOnePaperStillWork:
    def test_same_paper_is_measurable(self, tmp_path):
        dirs = [_run(tmp_path, "r1", "10.1/x", F1),
                _run(tmp_path, "r2", "10.1/x", F1)]
        r = from_review_dirs([str(d) for d in dirs])
        assert r["measurable"] is True
        assert r["paper_id"] == "10.1/x"
        assert r["pass_at_1_bracket"] is not None

    def test_a_finding_in_both_runs_reads_as_agreement(self, tmp_path):
        dirs = [_run(tmp_path, "r1", "10.1/x", F1),
                _run(tmp_path, "r2", "10.1/x", F1)]
        r = from_review_dirs([str(d) for d in dirs])
        assert r["all_findings"]["in_every_run"] == 1


class TestUnlabelledRunsSaySo:
    def test_missing_paper_ids_are_flagged_not_assumed(self, tmp_path):
        """Older artefacts record no paper_id. Comparing them may be fine, and
        the point is that nothing has CHECKED -- so the note says so rather than
        the result implying a verification that did not happen."""
        dirs = [_run(tmp_path, "r1", None, F1),
                _run(tmp_path, "r2", None, F1)]
        r = from_review_dirs([str(d) for d in dirs])
        assert r["measurable"] is True
        assert "unverified" in r["note"]
