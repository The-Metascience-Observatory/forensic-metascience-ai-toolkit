"""A derived artifact carries the code that computed it, and a stale one says so.

THE DEFECT THIS PINS (D47, 2026-09-07). Two `account.headline.json` files on
disk were written by an older `coverage.py` than the one in the same tree: ajcp
read `65 of 162` on the artifact and `120 of 162` at HEAD, and the supplement
`0 placed` on the artifact and `4` at HEAD. Nothing on either file said which
code had produced it, so a day of diagnosis went into residuals the code had
already stopped producing. The stamp is what lets such a file FAIL.

The property is not "the numbers are right". It is that a headline this code
cannot vouch for is rendered as a REASON and never as a share.
"""

from __future__ import annotations

import copy
import json

import pytest

from metascience_agent.scaffold import bind, codestamp, coverage, render

from .test_scaffold_coverage import TEXT, account


@pytest.fixture()
def acct():
    return account()


FOREIGN = {"code_commit": "0" * 40, "modules": {}, "sha256": "deadbeefdeadbeef"}


class TestTheStampItself:

    def test_it_names_the_commit_and_the_modules_that_compute_the_numbers(self):
        s = codestamp.stamp()
        assert set(s) == {"code_commit", "modules", "sha256"}
        assert set(s["modules"]) == set(codestamp.MODULES)
        # Every named module must exist: a stamp over a file that is not there
        # would be a hash of None and would compare equal for the wrong reason.
        assert all(v for v in s["modules"].values()), s["modules"]

    def test_the_stamp_is_the_same_object_twice_in_one_process(self):
        assert codestamp.stamp() is codestamp.stamp()

    def test_no_subprocess_is_launched_to_read_the_commit(self, monkeypatch):
        """`coverage.headline` is specified model-free and its own test makes
        `subprocess.run` raise. A stamp that shelled out to `git` would break
        that guarantee for a fact that is sitting in a file."""
        import subprocess

        def _boom(*a, **k):
            raise AssertionError("the code stamp ran a subprocess")

        monkeypatch.setattr(subprocess, "run", _boom)
        monkeypatch.setattr(subprocess, "Popen", _boom)
        codestamp.stamp.cache_clear()
        try:
            assert codestamp.stamp()["sha256"]
        finally:
            codestamp.stamp.cache_clear()

    def test_an_absent_or_foreign_stamp_is_not_current(self):
        assert codestamp.is_current(codestamp.stamp())
        assert not codestamp.is_current(FOREIGN)
        assert not codestamp.is_current(None)
        assert not codestamp.is_current({})
        assert not codestamp.is_current("da685a4")


class TestTheArtifactsCarryIt:

    def test_the_headline_block_carries_the_stamp(self, acct):
        assert coverage.headline(acct, TEXT)["code"] == codestamp.stamp()

    def test_the_account_carries_the_stamp(self):
        import inspect
        src = inspect.getsource(bind.assemble)
        assert 'account["code"] = _codestamp.stamp()' in src

    def test_the_stamp_does_not_break_the_byte_for_byte_recomputation(self, acct):
        first = coverage.headline(acct, TEXT)
        again = coverage.headline(json.loads(json.dumps(acct)), TEXT)
        assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)


class TestAForeignStampRendersAsStaleNeverAsANumber:

    def test_render_lines_refuses_to_print_a_foreign_blocks_numbers(self, acct):
        block = coverage.headline(acct, TEXT)
        assert f"{block['table_cells_placed']['placed']} of " in "\n".join(
            coverage.render_lines(block))
        block["code"] = FOREIGN
        md = "\n".join(coverage.render_lines(block))
        assert "**STALE.**" in md
        assert "deadbeefdeadbeef" in md
        for forbidden in (f"{block['table_cells_placed']['placed']} of "
                          f"{block['table_cells_placed']['cells']}",
                          f"{block['statistic_sentences']['covered']} of "
                          f"{block['statistic_sentences']['statistic_sentences']}",
                          "| tier | n |"):
            assert forbidden not in md, forbidden

    def test_a_block_with_no_stamp_at_all_is_stale_too(self, acct):
        """An artifact written before the stamp existed cannot be vouched for
        either, and that is the honest answer -- not a shrug."""
        block = coverage.headline(acct, TEXT)
        del block["code"]
        md = "\n".join(coverage.render_lines(block))
        assert "**STALE.**" in md and "no code stamp" in md

    def test_an_account_with_a_stale_stored_headline_renders_stale_not_its_numbers(self, acct):
        stored = coverage.headline(acct, TEXT)
        stored["statistic_sentences"]["covered"] = 999
        stored["code"] = FOREIGN
        acct["headline"] = stored
        # No text: H2 cannot be recomputed, so the stored block is the only
        # source there is -- and it is not one this code may print.
        md = "\n".join(coverage.render_lines(coverage.for_rendering(acct)))
        # The figure, not a bare "999": the stale note names the current git
        # sha, which can contain that digit run as hex (this tree: 906087c7a999).
        assert "999 of" not in md
        assert "was computed by code this tree does not contain" in md

    def test_a_current_stored_headline_is_used_where_it_cannot_be_recomputed(self, acct):
        acct["headline"] = coverage.headline(acct, TEXT)
        md = "\n".join(coverage.render_lines(coverage.for_rendering(acct)))
        assert "H2. Statistic-bearing sentences covered: 1 of 3" in md

    def test_render_recomputes_h1_and_h3_rather_than_reading_them_off_the_account(self, acct):
        """H1 and H3 are functions of the account alone. A stored block that
        disagrees with the account must lose, whatever its stamp says."""
        acct["headline"] = coverage.headline(acct, TEXT)
        acct["headline"]["table_cells_placed"]["placed"] = 999
        acct["headline"]["declared_variables"]["with_any_value"] = 999
        md = "\n".join(coverage.render_lines(coverage.for_rendering(acct, TEXT)))
        assert "999 of" not in md
        assert "H1. Table cells placed: 1 of 5" in md
        assert "H3. Declared variables with values: 2 of 3" in md

    def test_the_renderer_goes_through_for_rendering_and_not_the_stored_block(self):
        """The measures are worthless if the renderer reads them off the file."""
        import inspect
        src = inspect.getsource(render.render)
        assert "_coverage.render_lines(_coverage.for_rendering(account, text))" in src
        assert 'account.get("headline")' not in src

    def test_the_stale_block_is_not_a_zero(self, acct):
        block = coverage.headline(acct, TEXT)
        block["code"] = FOREIGN
        md = "\n".join(coverage.render_lines(block))
        assert "0 of 0" not in md and "(0.0)" not in md
