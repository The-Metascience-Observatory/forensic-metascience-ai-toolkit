"""A progress bar is optional; an ETA in a log is not noise.

Two rules, both about not making things worse. A run that is otherwise fine
must not fail because `tqdm` is absent -- this package's hard dependencies are
the ones whose absence makes output WRONG, and a progress bar's absence makes
it quieter. And a bar written to a redirected stdout is thousands of
carriage-return lines in a log file, which is how every sweep in `examples/`
is actually run.
"""

from __future__ import annotations

import io

from forensic_metascience_ai_toolkit.progress import Progress, _fmt


class TestItNeverBreaksTheRunItIsWatching:
    def test_it_works_without_tqdm(self, monkeypatch):
        import builtins
        real = builtins.__import__

        def no_tqdm(name, *a, **k):
            if name == "tqdm":
                raise ImportError("tqdm is not installed")
            return real(name, *a, **k)

        monkeypatch.setattr(builtins, "__import__", no_tqdm)
        stream = io.StringIO()
        stream.isatty = lambda: True                 # ask for the bar anyway
        assert list(Progress(range(5), stream=stream)) == [0, 1, 2, 3, 4]

    def test_an_unsized_iterable_still_iterates(self):
        stream = io.StringIO()
        got = list(Progress((x for x in range(4)), stream=stream))
        assert got == [0, 1, 2, 3]

    def test_an_exception_mid_iteration_still_closes(self):
        stream = io.StringIO()
        bar = Progress(range(10), stream=stream)
        try:
            for i in bar:
                if i == 3:
                    raise RuntimeError("boom")
        except RuntimeError:
            pass
        assert bar._bar is None


class TestALogGetsALineNotABar:
    def test_a_non_tty_stream_never_starts_a_bar(self):
        stream = io.StringIO()                       # isatty() is False
        bar = Progress(range(3), stream=stream)
        list(bar)
        assert bar._bar is None
        assert "eta" in stream.getvalue()

    def test_the_line_reports_progress_elapsed_and_an_eta(self):
        stream = io.StringIO()
        bar = Progress(range(3), desc="sweep", stream=stream, every_s=0)
        list(bar)
        text = stream.getvalue()
        assert "sweep" in text and "3/3" in text and "eta" in text

    def test_the_label_says_what_it_is_working_on(self):
        """What a stalled run is stuck on is the thing you actually need."""
        stream = io.StringIO()
        bar = Progress(range(2), stream=stream, every_s=0)
        it = iter(bar)
        next(it)
        bar.note("10.1007--s12035-017-0742-9")
        next(it)
        assert "10.1007--s12035-017-0742-9" in stream.getvalue()


class TestTheDurationsAreReadable:
    def test_it_formats_the_ranges_a_sweep_actually_takes(self):
        assert _fmt(45) == "45s"
        assert _fmt(750) == "12m 30s"
        assert _fmt(3840) == "1h 04m"

    def test_an_impossible_duration_says_so_rather_than_lying(self):
        assert _fmt(-1) == "?"
        assert _fmt(float("nan")) == "?"

    def test_the_summary_reports_throughput(self):
        stream = io.StringIO()
        bar = Progress(range(3), stream=stream)
        list(bar)
        assert "3 item(s)" in bar.summary() and "/min" in bar.summary()

    def test_an_empty_run_summarises_without_dividing_by_zero(self):
        assert Progress([], stream=io.StringIO()).summary() == \
            "nothing processed"


class TestAdvanceDrivesTheBarFromOutside:
    """`advance()` exists because a process pool cannot use `__iter__`.

    The iterator owns dispatch AND counting, which is right for a serial pass
    and impossible for a pool: results arrive out of order, and the loop that
    consumes them is not the loop that defines the work.
    """

    def test_it_counts_without_iterating(self):
        import io
        from forensic_metascience_ai_toolkit.progress import Progress
        buf = io.StringIO()
        with Progress(range(5), desc="sweep", every_s=0.0, stream=buf) as bar:
            for i in range(5):
                bar.advance(f"paper{i}")
        assert bar.n == 5

    def test_the_label_follows_the_completed_item(self):
        import io
        from forensic_metascience_ai_toolkit.progress import Progress
        buf = io.StringIO()
        with Progress(range(2), desc="sweep", every_s=0.0, stream=buf) as bar:
            bar.advance("10.1234--abc")
        assert "10.1234--abc" in buf.getvalue()

    def test_n_may_exceed_nothing_and_totals_stay_sane(self):
        """A pool reports completions, so `n` must track them even when the
        caller never touches `items`."""
        import io
        from forensic_metascience_ai_toolkit.progress import Progress
        buf = io.StringIO()
        with Progress([], total=3, desc="sweep", every_s=0.0, stream=buf) as bar:
            bar.advance("a", n=3)
        assert bar.n == 3
