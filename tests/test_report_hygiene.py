"""The review written to disk must not carry the operator's machine.

`scrub` existed, and was applied to `<review>_bundle/analysis/report.md` -- the
COPY the bundler makes. The file the pipeline writes,
`forensic_review/report.md`, was written raw.

That is the wrong one to leave unscrubbed. `bundle._FILE_BLURBS` describes it
as "The review itself -- what you would read", it is the artifact a person
attaches to an email, and archived reports on this checkout contain
`/mnt/c/Users/gregs/...` inside a reproduction-failure message printed directly
under an `IMPOSSIBLE` heading. A forensic review is a document about someone
else's work that may end up in front of that person, an editor, or a journal's
research-integrity office. The operator's home directory is not evidence about
the paper.
"""
import json
from pathlib import Path

import pytest

from forensic_metascience_ai_toolkit import bundle, scrub
LEAKS = [
    "/home/gsfitzgerald/.venvs/metascience-agent/bin/python",
    "/mnt/c/Users/gregs/agent_for_forensic_metascience/x.pdf",
    "C:\\Users\\gregs\\corpus\\paper.pdf",
    "/Users/dan/Dropbox/papers/10.1234--demo.pdf",
    "session 5758fef6-f008-43da-a4cb-5c95bd162970 ended",
]


class TestTheFunctionItself:
    @pytest.mark.parametrize("text", LEAKS)
    def test_no_home_path_or_session_id_survives(self, text):
        out = scrub.scrub(text)
        for token in ("gsfitzgerald", "gregs", "/Users/dan",
                      "5758fef6-f008-43da-a4cb-5c95bd162970"):
            assert token not in out, out

    def test_a_shared_data_url_is_not_a_home_directory(self):
        """`https://osf.io/home/xyz` has `/home/` in it and is the PAPER's
        data link -- the single most valuable string in a review of a paper
        that shared its data. The lookbehind exists for this."""
        url = "https://osf.io/home/abc123"
        assert scrub.scrub(f"data at {url}") == f"data at {url}"

    def test_the_path_stays_runnable(self):
        """Collapsed to `<home>` rather than deleted, so a reproduction command
        still reads as a path after the reader substitutes their checkout."""
        assert scrub.scrub("/home/dan/x/y.pdf") == "<home>/x/y.pdf"

    def test_the_bundle_re_export_is_the_same_function(self):
        """Two implementations of a redaction rule is two failure modes."""
        assert bundle.scrub is scrub.scrub


