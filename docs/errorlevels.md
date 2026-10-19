# Error levels (1-9)

> Written 2026-08-21, last revised 2026-09-01. The ladder itself is `severity9.py`; `docs/severity_ladder.json` is generated from it and checked by tests -- this file is the prose.

The severity ladder used by this toolkit: nine rungs answering one question
about a single finding.

> If this one finding were confirmed, and it were the only problem in the
> paper, what would the journal **have to** do about it?

**This file is the narrative source. It is not what the code reads.**
`src/metascience_agent/severity9.py` holds the machine-readable ladder --
rung text, boundary tests, caps and colours -- and generates
`webapp/lib/constants.gen.ts` and `docs/severity_ladder.json`. Changing a
rung's meaning means editing `severity9.py` and bumping its `LADDER_VERSION`;
two reviews across such a change are not comparable. This document exists to
explain *why* the ladder is shaped the way it is, and to work real cases
against it.

## Two axes, not one

The 1-9 ladder is a **correction-outcome ranking**. It is not the same thing
as the tool-layer verdict (`impossible | highly_suspicious | suspicious |
indeterminate | consistent`), which is an **epistemic** statement about a
number. A finding carries both, and neither is derivable from the other.

A GRIM-impossible digit in a descriptive table row is arithmetically
`impossible` and a **Level 2-3** consequence. Impossibility is a fact, not a
rung.

## The outcome is the label, not the test

Each rung is *named* for what a journal would do. But do not classify by
guessing the notice type: "erratum", "correction" and "corrigendum" mean
different things at different publishers -- Nature issues "Author
Correction" where Science issues "Erratum" -- so the notice name is an
unstable thing to reason from.

Classify on the **paper** instead. Each boundary is a question with an answer
you can look up:

| seam | the question |
|---|---|
| 1 → 2 | Does a reader carry away a wrong **fact**? |
| 2 → 3 | Does a reported **result** change? |
| 3 → 4 | Must something be **re-run or re-derived**, or only re-reported? |
| 4 → 5 | Does a claim **in the abstract** change? |
| 5 → 6 | Can you still **bound** which results survive? |
| 6 → 7 | Is the outcome **settled**? |
| 7 → 8 | Is there **positive evidence of intent**? |
| 8 → 9 | Does it span **multiple papers**, or cause **external harm**? |

The 3/4 seam is the one that does the most work: a transcription error and a
methods error look alike on the page and are not remotely alike in what they
mean.

## The ladder

| n | slug | label | what the journal does |
|---|---|---|---|
| 1 | `trivial` | Trivial error | no formal correction |
| 2 | `minor` | Minor error | erratum if needed |
| 3 | `notable` | Notable error | localized correction |
| 4 | `local_flaw` | Localized methodological flaw | corrigendum |
| 5 | `conclusions_affected` | Major error affecting conclusions | corrigendum or partial retraction |
| 6 | `unreliable` | Severe error -- results unreliable | expression of concern |
| 7 | `fatal_error` | Fatal error invalidating main findings | retraction (honest error) |
| 8 | `misconduct` | Serious misconduct | retraction (misconduct) |
| 9 | `extreme_misconduct` | Malicious or extreme misconduct | retraction, sanctions |

Per-rung criteria and boundary tests are in `severity9.py`; they are rendered
into every agent prompt at assembly time so the text cannot drift from this
table.

## Four things about the shape of the ladder

**Levels 1 and 2 are one band.** Both leave the findings unchanged; the only
difference is whether the journal bothers to publish a notice. The code
already treats them as one (`ACCUSATORY_MIN = 3` -- levels 1-2 are
record-keeping, not accusations). Use 2 when unsure. They stay separate rungs
because collapsing them would renumber everything below, invalidating stored
findings for no analytic gain.

**The axis switches at 7.** Levels 1-7 rank by consequence. But 7, 8 and 9 all
resolve to "retract", so the outcome axis saturates there and the
discriminator above 7 becomes **culpability and scale**, not harm. This means
the ordering is not monotone in damage: the arsenic-life paper (7, honest)
misled a field for fifteen years, while a plagiarized paragraph plus a few
invented data points (8) may mislead nobody. Level 8 is not "worse than 7";
it is a different kind of thing that also ends in retraction.

**Level 6 records unbounded scope, not a journal's procedural state.** It is
tempting to define 6 as "under investigation" -- but whether an institution
has opened a review is not a property of the paper, and this pipeline cannot
know it. Define 6 by what you can and cannot say: at 5 you can name which
claim falls and which stand; at 6 you cannot. Cases sit at 6 temporarily and
leave it in both directions once the scope is established.

**Level 9 merges two rungs deliberately.** Broad systematic fraud and fraud
with public consequences were originally separate; they are merged because
9 is reached rarely enough that splitting them would buy resolution nobody
uses. (Until v1.14.0 the pipeline could not assign 9 at all; it now can,
through the same rubric as every other rung.)

## Worked cases

Placements below are argued from the boundary tests, not from where the
journal filed the notice.

**Level 2 -- a wrong fact nothing depends on**
- Walton *et al.*, Science 2023. Labeling error in a supplementary table;
  re-running the preregistered analyses changed nothing. `10.1126/science.ads9718`
- Gould *et al.*, Science 2022. A mistaken table entry; the spectral fits and
  magnetism claims stood. `10.1126/science.adf5804`
- Liu *et al.*, Science 2023. A mislabeled ribosome-profiling dataset
  description; analyses unchanged. `10.1126/science.ado9025`

**Level 3 -- a reported result changes, the work is sound**
- Gore *et al.*, Nature 2005. Labels for two morpholino conditions swapped in
  a figure and a supplementary table. What the panels *report* changed; the
  experiments did not. `10.1038/nature11788`
- Bushdid *et al.*, Science 2014. Reporting details tied to the original
  calculations were corrected; the headline claim was untouched by the
  notice. `10.1126/science.ado6457`

**Level 4 -- one part of the work had to be redone**
- Worobey *et al.*, Science 2022. The distance data feeding the mapping
  analyses were wrong, so the analyses were re-run -- past the 3/4 seam. The
  interpretation of market centrality held, so it stops short of 5.
  `10.1126/science.adp1133`
- Phillips *et al.*, Science 2019. A data-preparation bug dropped
  zero-abundance sites; reanalysis lowered predicted global means and shifted
  geographic patterns, while the environmental drivers and overall
  interpretation remained. **This is the 4/5 seam in one case**: the method
  was wrong and had to be re-run (→ 4), but no abstract-level claim fell
  (→ not 5). `10.1126/science.abd9834`

**Level 5 -- a main claim does not survive**
- Eisenbarth *et al.*, Nature 2012. The corrigendum reported that a *Dock8*
  mutation, not the knockout, explained the dendritic-cell migration
  phenotype -- reassigning the cause of the effect the title claim rests on.
  Other findings stood, which is what holds this at 5 rather than 7.
  `10.1038/nature16074`

**Level 6 -- scope not yet boundable**
- Flore *et al.*, Nature 1998 (EoC 2025, institutional review under way).
  `10.1038/s41586-025-09239-w`
- Lu *et al.*, Nature 2004 (EoC 2023, image-integrity issues and an
  institutional report). `10.1038/s41586-023-06944-2`
- Vaitiekėnas *et al.*, Science 2018 (EoC 2021). `10.1126/science.abl5286`

These sit at 6 because at the time of the notice nobody could say which
results survived. Note that two of them cite image integrity: if intent is
later established they move to 8, and if the concerns are resolved they move
down. The rung records the state of knowledge, and it is expected to change.

**Level 7 -- honest, and fatal**
- Wolfe-Simon *et al.*, Science 2010 ("arsenic life"). Retracted 2025 after
  follow-up work found no arsenate in GFAJ-1 DNA and explained the growth by
  trace phosphate. No misconduct was alleged; the conclusions simply did not
  hold. `10.1126/science.adu5488`
- Lombardi *et al.*, Science 2009 (XMRV in chronic fatigue syndrome).
  Multi-laboratory blinded studies detected nothing; XMRV was shown to be a
  recombinant arising during cell-line passage, i.e. laboratory
  contamination. `10.1126/science.334.6063.1636-a`
- Lee *et al.*, Science 2009 (XA21). Strain mislabeling and assay problems
  invalidated the main claim; intent was not established, which is what keeps
  it at 7. `10.1126/science.342.6155.191-a`

**Level 8 -- evidenced misconduct, confined to one paper**
- LaCour & Green, Science 2014 ("When contact changes minds"). Irregularities
  and no verifiable raw data. `10.1126/science.aac6638`
- Shu *et al.*, PNAS 2012 (signing at the beginning). Data-integrity
  problems. `10.1073/pnas.2115397118`
- Chen, Journal of Vibration and Control 2009. A fabricated peer-review ring.
  `10.1177/1077546309349849`
- Dunoyer *et al.*, The Plant Cell 2004. Image manipulation and duplication
  across several figures -- **several figures of one paper is still 8**;
  multiple papers would make it 9. `10.1105/tpc.15.00407`
- Neurology 2017 partial retraction. An author removed and a figure replaced
  after misconduct findings. The *outcome* was partial, the *cause* was
  misconduct: classify on the cause. `10.1212/WNL.0000000000003650`

**Level 9 -- systematic, or harmful outside the literature**
- Schön *et al.*, Nature 2001. Fabricated and duplicated data across a body
  of work. `10.1038/nature01464`
- Hwang *et al.*, Science 2005. Fabricated patient-specific stem-cell data;
  national investigation. `10.1126/science.1124926`
- Wakefield *et al.*, The Lancet 1998. Ethics breaches and data
  misrepresentation; sustained public-health harm.
  `10.1016/S0140-6736(10)60175-4`
- Macchiarini *et al.*, The Lancet 2011. Ethics violations and
  misrepresented outcomes in patients who died.
  `10.1016/S0140-6736(18)31558-7`
- Mehra *et al.*, The Lancet 2020 (Surgisphere). Unverifiable third-party
  data; the paper halted WHO trial arms before retraction.
  `10.1016/S0140-6736(20)31324-6`

## A calibration warning

An earlier draft of this file placed most of these cases one to two rungs
higher, and several examples contradicted the criteria of the rung they were
filed under -- two "major error affecting conclusions" cases whose own
summaries stated the conclusions were unchanged. The cause looks like venue:
every mid-ladder example is from Science or Nature, and a Science erratum
*feels* weighty even when it is a typo fix.

Two consequences. First, when placing a case, argue from the boundary
questions and ignore the masthead. Second, **these cases are deliberately not
included in any agent prompt.** They would import the same bias, and a model
that half-remembers a famous case will confabulate the rest. The agents get
the criteria and the boundary tests; the cases are here, for people.
