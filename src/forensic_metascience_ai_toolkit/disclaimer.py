"""The standing caveat attached to every piece of output this toolkit produces.

Kept in one module because the disclaimer has to be identical everywhere it
appears -- markdown report, PDF, findings JSON, and the stage-2 prompt. A
disclaimer that says something slightly different in each place reads as
boilerplate, and boilerplate is skipped.

The wording is deliberately quantitative. "This may contain errors" is ignorable;
"half of the clean control papers in our own corpus contain a statcheck
inconsistency" tells the reader what base rate to actually apply.
"""

# One line. Goes directly under the report title, into the PDF header, and into
# findings.json. Must survive being read in isolation.
#
# "Arithmetic consistency check" understated what this does and will understate
# it much further as citation and duplication checks land. The claim to avoid is
# not breadth but CERTAINTY: the reason a reader must not treat this as a
# finding of misconduct is that any individual flag is more likely to be our
# extraction error than the authors' wrongdoing, and that is true of a
# duplicated table value exactly as it is of a mis-rounded mean.
DISCLAIMER_SHORT = (
    "This is an automated check of a paper's reported numbers and its internal "
    "record -- not a finding of misconduct. It is NOT adequate for definitive "
    "detection of wrongdoing or fraud."
)

# The full statement. Rendered as a closing section, and given to stage 2 so the
# narrative is written in a register consistent with it.
#
# `{TESTED_ON}` IS FILLED FROM `scope.py`, NOT TYPED. This paragraph carried the
# corpus size as a literal and said "at least 37 runs over 19 papers" while
# `scope.ARCHIVE_RUNS` said 35 -- the toolkit overstating its own testing, in the
# paragraph whose entire job is to bound what it has been tested on, and in a
# document that tells readers to distrust unverified numbers. `scope.py`'s own
# comment records correcting that figure twice already, which is what a literal
# in a second file guarantees.
_DISCLAIMER_LONG_TEMPLATE = """\
**What this document is.** An automated check of a paper against itself: whether
the numbers it reports are mutually consistent, whether any dataset could have
produced them, whether its statistics follow from the values printed beside
them, and whether its own record -- tables, references, supplementary material
-- holds together. Where it says a value is "impossible", it means the reported
figures contradict one another arithmetically.

**What this document is not.** It is not a finding of fraud, misconduct, error,
or bad faith, and it is not adequate for definitive detection of any of those.
An inconsistency has many ordinary causes, and the innocent ones are far more
common than the guilty ones: typographical error, rounding or transcription
slips, a mislabelled sample size, values copied from a superseded analysis, or
-- most often -- a mistake by this tool in reading the number off the page.

**The base rates that matter here.** In our own ground-truth corpus, half of the
clean control papers contain at least one statcheck inconsistency. Reporting
errors are near-universal in honest work. Separately, nearly all of this
pipeline's failure lives in getting numbers off a PDF, not in the arithmetic:
the arithmetic is exact and the extraction is not. Any individual flag in this
report is therefore much more likely to be our extraction error than the
authors' misconduct.

**Anything marked `indeterminate` is a refusal, not a negative result.** It means
a precondition could not be verified and the tool declined to judge. It is not
evidence of a problem, and it is not evidence of the absence of one.

**What it has been tested on.** {TESTED_ON} Almost all of them are
primary biomedical or psychology research and most are human randomised
trials. No qualitative, bench-science, -omics, or non-biomedical paper has ever
been through it, and no claim here about its accuracy transfers to one. It is
**not designed for narrative reviews** -- their numbers belong to the papers
they cite, so a flag would land on the wrong authors -- and auditing a
**meta-analysis or systematic review** is a separate undertaking with different
tools, which this is not. The full breakdown is in "What this has been tested
on", below.
"""


def _tested_on() -> str:
    """The corpus sentence, from the module that counts the corpus."""
    from .scope import tested_on_sentence
    return tested_on_sentence().split(", almost all")[0].rstrip(".") + "."


DISCLAIMER_LONG = _DISCLAIMER_LONG_TEMPLATE.replace(
    "{TESTED_ON}", _tested_on())


# What a reader should actually DO with a finding. Separated from the disclaimer
# proper because it is instruction rather than caveat.
ACTION_NOTE = """\
**Before treating anything here as a problem:** verify the number by hand against
the published paper, since the most likely explanation is that this tool misread
it. If it holds up, the appropriate next step is to contact the corresponding
author and ask -- most discrepancies are resolved by a correction or an
explanation. Requesting the raw data is the only thing that can actually settle
the question. Public allegations are not an appropriate use of this output.
"""


def banner_markdown() -> str:
    """The short caveat as a markdown blockquote, for placement under a title."""
    return f"> {DISCLAIMER_SHORT}"


def closing_section_markdown() -> list[str]:
    """The full disclaimer, the action note, and the scope statement.

    The scope section lives in `scope.py` and is appended here rather than
    duplicated, for the reason this module exists at all: a caveat that says
    something slightly different in each place reads as boilerplate.
    """
    from .scope import scope_markdown

    out: list[str] = ["## How to read this", ""]
    out.append(DISCLAIMER_LONG.strip())
    out.append("")
    out.append(ACTION_NOTE.strip())
    out.append("")
    out.extend(scope_markdown())
    return out
