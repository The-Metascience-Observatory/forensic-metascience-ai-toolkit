"""Every `paper_text` caller must reckon with the empty string.

`jats.paper_text` returns "" for FOUR different reasons -- no body.md, no
parseable XML, no HTML, and a PDF whose text layer could not be read -- and every
caller receives the same empty string with nothing to distinguish them. That is
the defect recorded as #177, and its underlying cause is that
`extraction.pdf.extract_text` returns a bare `str`: the explanation goes to
stderr as a warning, invisible to any programmatic caller.

THE API CHANGE WAS CONSIDERED AND DECLINED, 2026-08-18, and this file is what
replaced it. The call-site survey found ONE real caller of `extract_text` in
`src` and that most `paper_text` consumers already fail closed, several carrying
comments about the incident that taught them to. Re-plumbing the return type
would have churned thirteen call sites to re-derive a property twelve of them
already had.

BUT ONE CALLER WAS LIVE, which is why a guard is still needed. `agent.py:1897`
passed the possibly-empty text into `artefacts.preregistration`, which returned
`status: "not_mentioned"` -- a claim ABOUT THE PAPER manufactured from our
failure to read it. (Tracing it also turned up a second, unrelated defect: an
explicit denial was being reported as `preregistered`. Both fixed in 9c8b144.)

So the risk is not the existing callers. It is the NEXT one. This is a ratchet:
the set of call sites is pinned, and adding one fails the test until whoever
added it records how their caller behaves when the paper could not be read.
"""
from tests.source_paths import canonical
import re
from pathlib import Path

import pytest

SRC = Path("src/metascience_agent")

#: Every call site, and HOW it survives an empty return. Adding a caller means
#: adding a line here, which is the point -- the line is cheap and the thinking
#: it forces is not.
KNOWN_CALLERS: dict[str, str] = {
    "register_view.py": (
        "means UNKNOWN and says so on the page. `build` passes the source label "
        "through to `render`, which prints 'no source could be read -- which is "
        "UNKNOWN, not an absence of text' when it is None. The inspector's whole "
        "job is making our own gaps visible, so an empty read is rendered as a "
        "gap rather than as a paper with nothing in it."),
    "agent.py": (
        "two sites. 3444 checks `if txt:` and records 'the paper's own text "
        "came back empty' as a problem. 1897 feeds artefacts.preregistration, "
        "which since 9c8b144 returns `unknown_no_text` rather than a verdict."),
    "artefacts.py": (
        "find_in_paper hedges in its own note; the empty case is discussed in a "
        "comment at the call site."),
    "bundle.py": (
        "display only -- acronyms, body HTML and artefact links. An empty body "
        "renders an empty pane, which is visibly empty to a reader rather than "
        "silently asserting anything about the paper."),
    "glyphs.py": (
        "scan_paper fails closed: no text returns `clean: False, "
        "text_available: False` with a note that corruption is UNKNOWN."),
    "parallel.py": (
        "feeds the adjudicator docket's inline paper-text excerpt; an empty "
        "read degrades to no excerpt while the adjudicator keeps `Read` "
        "access to the paper dir, so an unreadable paper costs convenience, "
        "never asserts an absence."),
    "prepass.py": (
        "_repair_proven_glyphs fails closed and distinguishes the two cases: "
        "unreadable text records that WE could not read the paper, "
        "read-but-unproven records that the PAPER does not establish the "
        "mapping. Either way no cell is rewritten, so an empty read can only "
        "leave damage in place, never invent a repair."),
    "quotes.py": (
        "adds the text to a verification haystack. An empty haystack makes "
        "quotes UNVERIFIABLE rather than verified, so the failure direction is "
        "safe by construction."),
    "tripwire.py": (
        "the xml_present_but_no_text condition FIRES on this exact case; it is "
        "the caller that exists to catch it."),
}

#: NOT `_paper_text`. `evaluation/corpus_run.py` defines a same-named private
#: helper that concatenates .md/.txt/.xml out of a blinded directory and never
#: touches `jats.paper_text` at all. It was listed here on a first pass and the
#: stale-entry check below caught it -- a registry naming a caller that is not
#: one is the same defect as one missing a caller that is. The word boundary
#: keeps them apart: `_` is a word character, so `\bpaper_text` does not match
#: inside `_paper_text`.
_CALL = re.compile(r"\bpaper_text\s*\(")


def _call_sites() -> dict[str, list[int]]:
    found: dict[str, list[int]] = {}
    for path in sorted(SRC.rglob("*.py")):
        rel = path.relative_to(SRC).as_posix()
        for i, line in enumerate(canonical(path).read_text(encoding="utf-8").splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#") or "def paper_text" in line:
                continue
            if _CALL.search(line):
                found.setdefault(rel, []).append(i)
    return found


class TestTheCallerSetIsPinned:
    def test_no_unregistered_caller(self):
        """A new call site must state how it handles an unreadable paper."""
        extra = sorted(set(_call_sites()) - set(KNOWN_CALLERS))
        assert not extra, (
            f"new paper_text caller(s) {extra}: `paper_text` returns '' for a "
            "paper we COULD NOT READ as well as for one with nothing in it. "
            "Decide which your caller means, then add it to KNOWN_CALLERS with "
            "one line saying so.")

    def test_no_stale_entry(self):
        """A registry naming callers that no longer exist stops being read."""
        gone = sorted(set(KNOWN_CALLERS) - set(_call_sites()))
        assert not gone, f"KNOWN_CALLERS lists absent call sites: {gone}"

    def test_every_entry_says_something(self):
        for name, why in KNOWN_CALLERS.items():
            assert len(why) > 30, f"{name}: state HOW it handles the empty case"


class TestTheTwoFailClosedCallersStillDo:
    """Spot-checks, because the registry above is prose and prose drifts."""

    def test_glyph_scan_reports_unknown_rather_than_clean(self, tmp_path):
        from metascience_agent.glyphs import scan_paper
        d = tmp_path / "paper"; d.mkdir()
        r = scan_paper(d)
        assert r["clean"] is False and r["text_available"] is False

    def test_supplement_audit_is_three_valued(self, tmp_path):
        from metascience_agent.supplements import audit
        d = tmp_path / "paper"; d.mkdir()
        assert audit(d)["missing"] is None

    def test_preregistration_does_not_claim_not_mentioned(self):
        """The caller that was actually live. #177's concrete harm."""
        from metascience_agent.artefacts import preregistration
        assert preregistration("")["status"] == "unknown_no_text"
