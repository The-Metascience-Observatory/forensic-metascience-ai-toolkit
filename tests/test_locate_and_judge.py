"""Patterns LOCATE; evidence JUDGES.

Greg, 2026-08-18, after a survey found 23 places where a regex decides what a
paper MEANS: "do the locate-and-judge refactor for the three high severity ones.
(the _is_geocode error is particularly bad)"

The shared defect is a pattern issuing a TERMINAL verdict on a semantic question
-- one where negation, attribution or scope changes the answer and the pattern
cannot see them. The shared fix is to demote the pattern to a screen and require
evidence the code already holds.
"""
import pytest


class TestSupplementDenialIsNotACitation:
    """`gate()` returns proceed=False and refuses a PAID run. VERIFIED
    2026-08-18: "No supplementary material is provided for this article."
    matched as a REFERENCE TO supplementary material, so the paper was judged to
    depend on a supplement we do not hold -- a hard refusal, exit 2, for stating
    it has none."""

    def _audit(self, tmp_path, body):
        from forensic_metascience_ai_toolkit.supplements import audit
        (tmp_path / "body.md").write_text(body, encoding="utf-8")
        return audit(tmp_path)

    def test_a_denial_no_longer_blocks_the_run(self, tmp_path):
        a = self._audit(tmp_path, "No supplementary material is provided for this article.")
        assert a["missing"] is False
        assert len(a["mentions_denied"]) == 1

    def test_a_genuine_citation_still_blocks(self, tmp_path):
        a = self._audit(tmp_path, "Full results are given in Supplementary Table 3.")
        assert a["missing"] is True
        assert len(a["mentions_cited"]) == 1

    def test_a_citation_beside_a_denial_still_blocks(self, tmp_path):
        """The dangerous direction. A real dependency must not be waved through
        because another clause happens to contain a negation."""
        a = self._audit(
            tmp_path,
            "Results are in Supplementary Table 3. No supplementary code is provided.")
        assert a["missing"] is True

    def test_the_clause_boundary_is_what_makes_that_work(self, tmp_path):
        """A plain distance window reached across the semicolon and classified
        the citation as a denial -- which would have let the gate proceed on a
        paper that really does depend on a supplement."""
        from forensic_metascience_ai_toolkit.supplements import classify_mentions
        r = classify_mentions(
            "See Supplementary Table 1; no supplementary code is provided.")
        assert len(r["cited"]) == 1, "the citation must survive its neighbour"

    def test_the_evidence_travels_with_the_verdict(self, tmp_path):
        """`missing` on its own is the thing that could not be checked."""
        a = self._audit(tmp_path, "No supplementary material is provided for this article.")
        ctx = a["mentions_denied"][0]["context"]
        assert "No supplementary material" in ctx

    def test_an_unrecognised_negation_fails_CONSERVATIVELY(self, tmp_path):
        """`_DENIAL_NEAR` does NOT enumerate every negation -- that approach
        already failed tonight on artefacts.preregistration. What matters is the
        direction it fails in: an unrecognised negation leaves the mention read
        as a citation and the gate refuses, which is a blocked run rather than
        findings written against authors whose supplement we never saw."""
        a = self._audit(
            tmp_path,
            "Scarcely any supplementary tables accompany this report.")
        assert a["missing"] is True


class TestLocatorNumbersDiscriminate:
    """`_disambiguate_by_locator` decides which passage a finding's numbers were
    read from, and the answer renders in the viewer as a bold "Numbers read
    from". Word overlap alone chose the WRONG ROW.

    VERIFIED 2026-08-18: finding at "Table 3, control group, week 4", candidates
    "Table 3, control group, week 12" (wrong) and "Table 3, wk 4 control" (the
    true producer). The wrong one won 4-3, because `control`, `group` and `week`
    are boilerplate shared by every row of that table while the one token that
    identifies the ROW -- the 4 -- counted no more than the word "the" would.
    """

    def _pick(self, location, cands):
        from forensic_metascience_ai_toolkit.sourcing import _disambiguate_by_locator
        r = _disambiguate_by_locator(
            {"location": location},
            [{"source_locator": loc, "tool": tag} for loc, tag in cands])
        return (r or {}).get("tool")

    def test_the_reported_misattribution_is_fixed(self):
        assert self._pick("Table 3, control group, week 4", [
            ("Table 3, control group, week 12", "WRONG_ROW"),
            ("Table 3, wk 4 control", "TRUE"),
        ]) == "TRUE"

    def test_a_contradicting_number_disqualifies_rather_than_outscores(self):
        """Even with overwhelming word overlap, `week 12` cannot be the producer
        of a finding about `week 4`."""
        assert self._pick("Table 3, control group, week 4", [
            ("Table 3, control group, week 12", "WRONG_ROW"),
        ]) is None

    def test_when_every_candidate_contradicts_it_refuses(self):
        """No attribution beats a confident wrong one."""
        assert self._pick("Table 2, week 4", [
            ("Table 2, week 12", "A"), ("Table 2, week 24", "B"),
        ]) is None

    def test_an_unambiguous_match_still_resolves(self):
        assert self._pick("Table 1, age row", [("Table 1, age", "ONLY")]) == "ONLY"

    def test_a_finding_with_no_numbers_is_unaffected(self):
        """The rule only fires when the finding names numbers to contradict."""
        assert self._pick("Baseline characteristics table, sex distribution", [
            ("Baseline characteristics sex", "P"),
        ]) == "P"
