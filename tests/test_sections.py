"""Greg, 2026-08-18: "identify those sections and don't include them in the
analysis of the extractable values." These pin the direction the rule must fail
in, which is the whole difficulty."""

from metascience_agent import sections as S

PAPER = """# Body

## Accepted Manuscript

G. Ladurner 1 , P. Kalvach 2 , H. Moessler 3

## A B S T R A C T

We enrolled 146 patients and mortality fell by 43%.

## Results

The effect was 2.5 (SD 0.3).

## Acknowledgements

Grant 12345 funded this.

## Funding

Award 999 from AKP.

## References

1. Smith 1997
"""


class TestWhatCountsAsFurniture:
    def test_publisher_furniture_is_front_matter(self):
        secs = S.map_sections(PAPER)
        kinds = {s["name"]: s["kind"] for s in secs}
        assert kinds["accepted manuscript"] == S.FRONT_MATTER
        assert kinds["body"] == S.FRONT_MATTER

    def test_a_letter_spaced_heading_is_still_read(self):
        """13 of 119 corpus papers print `## A B S T R A C T`."""
        secs = {s["name"]: s["kind"] for s in S.map_sections(PAPER)}
        assert "abstract" in secs and secs["abstract"] == S.ANALYTIC

    def test_back_matter_runs_until_the_argument_resumes(self):
        """`Acknowledgements` is routinely followed by `Funding` and then
        `References`; treating each sub-heading as a fresh start would let the
        middle of the back matter read as analytic."""
        kinds = {s["name"]: s["kind"] for s in S.map_sections(PAPER)}
        assert kinds["acknowledgements"] == S.BACK_MATTER
        assert kinds["funding"] == S.BACK_MATTER
        assert kinds["references"] == S.BACK_MATTER


class TestItFailsTowardKeepingThings:
    """A surplus number costs the model one glance. A missing one costs a check
    that would have run, and nothing downstream can tell it is absent."""

    def test_a_title_heading_holding_the_abstract_stays_analytic(self):
        """THE REGRESSION THIS FILE EXISTS FOR. An earlier rule classed
        everything before the first analytic heading as front matter -- but a
        paper's title is itself a heading and the section under it holds the
        abstract. Measured over 40 corpus papers, that rule put 36 numerals
        already typed `statistic` inside an excluded span, including "reduced
        A-beta burden by 43%" and "death of 60% of the animals"."""
        text = ("# Body\n\n## The neuroprotective effects of cerebrolysin\n\n"
                "Treatment reduced burden by 43% in the young group.\n\n"
                "## Introduction\n\nPrior work...\n")
        secs = S.map_sections(text)
        title = next(s for s in secs if s["name"].startswith("the neuroprotective"))
        assert title["kind"] == S.ANALYTIC
        off = text.index("43%")
        assert S.kind_at(secs, off) == S.ANALYTIC

    def test_a_paper_with_no_headings_excludes_nothing(self):
        """Greg, 2026-08-19: "some of the docling extractions lack the clear
        headers you'd want in a markdown file." So the no-heading case is real,
        and it must cost nothing."""
        secs = S.map_sections("plain text, 45 patients, no headings at all")
        assert [s["kind"] for s in secs] == [S.ANALYTIC]

    def test_an_unrecognised_heading_is_analytic(self):
        secs = S.map_sections("## Weird Bespoke Heading\n\nvalue 4.2\n")
        assert all(s["kind"] == S.ANALYTIC for s in secs if s["name"])

    def test_empty_text_is_no_sections_not_a_crash(self):
        assert S.map_sections("") == []

    def test_an_unknown_offset_reads_analytic(self):
        assert S.kind_at(S.map_sections(PAPER), 10**9) == S.ANALYTIC
