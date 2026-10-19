# Checks we chose not to implement

*Draft section for the whitepaper. Written 2026-08-18; decision confirmed by
Greg the same day. Placed here rather than in the shared outline because the
whitepaper is a collaboration and its structure is Dan's call -- this is ready
to drop in.*

A toolkit is defined as much by the checks it declines as by the ones it runs.
Every check we ship can produce an accusation against an honest paper, and a
check whose signal is weaker than its failure mode is a liability however
respectable its provenance. This section records one we removed deliberately,
with the reasoning, so that a reader can disagree with us on the merits rather
than wonder whether we had thought about it.

## The hidden tiny p

James Heathers' forensic-metascience toolkit includes a signal we will call
STALT: a reported p-value stated as a threshold (`p < .05`) whose recomputed
value turns out to lie orders of magnitude below that threshold (say, 1e-15).
The intuition is that an author who computed a p of 1e-15 and wrote `p < .05`
has chosen to obscure something, and the gap between the two is evidence of
that choice.

We implemented it, ran it, and then removed it as an accusation-grade signal.

### Why we removed it

**The printed statement is true.** If the true p is 1e-15, then `p < .05` is a
correct statement about the data. A forensic instrument that raises
accusation-grade severity against a true statement has made a category error,
and no amount of surrounding context repairs it. Our governing constraint is
that a false accusation against an honest paper is the worst output the system
can produce; a check that fires on correct reporting violates it by
construction.

**The convention it flags is the one the field mandates.** APA style requires
p-values below .001 to be reported as `p < .001` rather than as an exact figure.
A great many journals impose the same floor. So the signal fires most reliably
on authors who are following their journal's house style, and least reliably on
anyone with something to hide, who is under no obligation to use a threshold at
all.

**The magnitude of the gap is not evidence of intent.** A very large test
statistic produces a very small p as a matter of arithmetic. An F of 400 on
reasonable degrees of freedom yields a p far below any threshold anyone would
print. The gap therefore measures effect size and sample size at least as much
as it measures disclosure behaviour, and the tool cannot separate those.

**The test statistic already falsifies the p-value where it matters.** This is
the decisive point, and it is what makes the check redundant rather than merely
noisy. Where a reported p is actually *wrong*, the paper almost always supplies
enough to prove it: the test statistic and its degrees of freedom recompute the
p directly. That is what statcheck does, and it is a far stronger instrument --
it produces a determinate contradiction rather than an inference about why an
author chose a notation. A check that adds suspicion where a recomputation
already gives certainty is adding noise to a channel that was already clear.

### What we kept

The reversal is narrower than "we deleted the check". The tool still fires, and
fires hard, in the direction where the paper is *wrong* rather than merely
terse: a recomputed p that lies **above** its claimed bound is flagged, graded
by how far it overshoots. `p < .05` with a true p of .09 is a false statement
about the data, and that is a finding.

The hidden-tiny-p observation itself is not discarded either. It survives in the
explanatory text attached to the result, where a human reader can weigh it, and
it is available as context to the agents that run the check: `stalt_check` is
callable by the tools agent and by the adjudicator, which assigns each finding's
final severity (it is not on the scientific proofreading agent's list). What it no longer does is
drive severity. The distinction we are drawing is between something worth
mentioning to a reader and something worth accusing an author of, and we think
that line is where most of the difficulty in this field actually sits.

### The cost, stated plainly

If the hidden-tiny-p signal has real diagnostic value that we have
underweighted, we have removed a detector and our sensitivity is lower for it.
We accept that trade because the failure mode we avoided is the one we consider
unrecoverable, and because the alternative instrument -- recomputing the p from
the test statistic -- is strictly better where the paper gives us the means. But
it is a judgement call about a published technique, not a bug fix, and a reader
who weighs the two failure modes differently would be entitled to restore it.
