# SPOT (Son et al. 2025) -- full read, and what it means for this toolkit

**Status:** analysis, 2026-08-18. Supersedes the preliminary pass of 2026-08-13
that produced the docstring in `src/forensic_metascience_ai_toolkit/evaluation/agreement.py`.
**Author:** drafted by Claude at Greg's direction. Every number below is traced
to a source; claims the paper makes and claims I derived are labelled separately
and never mixed inside a sentence.

## Sources actually read

| what | where |
|---|---|
| the paper (arXiv:2505.11855v1, 17 May 2025, 40pp) | Greg's local Zotero copy (not in this repository) |
| annotations (91 rows x 6 cols, CC-BY-4.0) | local copy of the `SPOT-MetaData` dataset's `data/train-00000-of-00001.parquet` (not in this repository) |
| code + archived PDFs + parsed content | `https://github.com/guijinSON/SPOT` (tree read via API 2026-08-18) |
| parsed papers | `https://huggingface.co/datasets/amphora/SPOT` |
| model generations + judge decisions | `https://huggingface.co/datasets/amphora/spot-results` |

Verification of the existing docstring first, since it is already load-bearing
in this repo. **All three of its claims check out.** Table 2 of the paper gives
o3 at precision **6.1% (sd 1.3)**, recall **21.1% (sd 4.4)**, pass@1 **18.4%**,
pass@4 **37.8%**; o3 is the best model on every one of those columns. "Across
eight independent runs, models rarely rediscover the same errors" is verbatim
from the abstract. One correction to make before quoting it in public: **21.1%
is not the highest recall in the paper.** Table 3 reports o3 at 34.6% recall on
the 48-instance figure-independent subset with figures supplied, and 25.7% on
the same subset with figures stripped. "21.1% at best" is right for the headline
full-corpus multimodal setting and wrong as a global maximum.

---

# Part 1 -- the section for the blog post

## 1. What SPOT verifies, and on what corpus

SPOT is **83 published manuscripts carrying 91 errors, drawn from 47 paper
sources across 28 venues and 10 fields** (paper, Table 1 and Appendix E). The
authors describe it as a multimodal error-detection benchmark: mean 12,888
tokens and 17.5 images per manuscript, range 1,207-46,441 tokens and 0-80
figures.

The construction is a five-stage funnel (paper, Section 2.1), and the funnel is
the whole story:

1. **Seed.** WithdrarXiv (14,000 retracted arXiv papers with withdrawal
   comments) plus a PubPeer crawl.
2. **Automated filter.** Two GPT-4o passes -- keep comments that pinpoint a
   specific section/figure/equation/table, drop anything needing an external
   artifact (another paper's images, an external dataset, code) -- leaving 1,855
   WithdrarXiv and 25,378 PubPeer candidates. Then a post-2024 publication
   filter to dodge contamination, leaving **58 WithdrarXiv + 215 PubPeer = 273**.
3. **Author confirmation.** Keep only PubPeer threads where the original author
   explicitly acknowledged the mistake, and arXiv self-retractions.
4. **Human sanity check.** Two mutually exclusive annotator groups; the error
   must be self-contained, identifiable, and author-acknowledged; the archived
   PDF must still show it.
5. **Normalization.** See Section 3 below -- this is the important one.

**273 candidates in, 83 papers out.** The ground truth is therefore not "errors
in published papers". It is the intersection of four filters: somebody noticed
the error, they posted it publicly (PubPeer) or the authors withdrew (arXiv),
**the authors publicly admitted it**, and the error is self-contained enough to
be pinned to one location without external data. That is a narrow and unusual
tail of the error population, and the paper is explicit about it -- Appendix A
concedes that "the complexity of scientific manuscripts means some true errors
may be unannotated".

The composition matters as much as the size:

| error category | n | severity |
|---|---|---|
| Equation / proof | 37 | retractions concentrated here |
| Figure duplication | 27 | |
| Data inconsistency (all subtypes) | 18 | |
| Statistical reporting | **4** | |
| Reagent identity | 3 | |
| Experiment setup | 2 | |
| **total** | **91** | 59 errata, 32 retractions |

Fields: Mathematics 22, Computer Science 13, Biology 13, Multidisciplinary 11,
Chemistry 8, Physics 8, Materials Science 6, Medicine 5, Environmental Science
3, Engineering 2. **Psychology and the social sciences contribute zero.**
Seventy-six papers carry one error, six carry two, one carries three.

Two disclosures in the paper deserve to travel with any citation of that table.
First, the category taxonomy was derived inductively after annotation, not set
in advance. Second -- and this is the one people will miss -- **the distribution
was deliberately rebalanced**: "figure-duplication instances initially
overwhelmed the dataset, so we filtered based on severity and paper category to
prevent a single type from dominating" (Section 2.2). The category proportions
are therefore a curatorial choice, not an estimate of anything in the world.

Severity is likewise a proxy: erratum versus retraction is **the form of the
publisher's response**, not an assessment of scientific consequence.

**Inferred, not stated:** the 2.5% yield from 273 candidates to 83 papers, and
the observation that the four filters compose into a strong selection effect,
are mine. The paper reports the funnel counts without characterising the
selection.

## 2. Metrics and denominators -- how SPOT treats false positives

The scoring rule (paper, Section 2.3) is short enough to quote in full effect:

> A predicted error is counted as a true positive (TP) only when the model's
> reported location matches a benchmark annotation and an LLM confirms they
> indicate the same error. All other predictions, including those at
> non-annotated locations or those matching an annotated location but with a
> different description, are considered false positives (FP) [...] We treat the
> error annotations included in SPOT as exhaustive.

Precision = TP/(TP+FP), recall = TP/(TP+FN), both computed over the 91
annotations and every error the model emitted across the 83 papers, averaged
over eight independent runs.

**The answer to the question we actually care about: no, SPOT does not and
cannot penalise a model for flagging a correct paper, because SPOT contains no
correct papers.** Every one of the 83 manuscripts is known to carry at least one
author-acknowledged error. There is no honest-paper arm, no negative control,
and consequently no specificity figure anywhere in the paper. What SPOT's
precision measures is a different and narrower thing: given a paper that is
already known to be flawed, what fraction of the model's flags land on the flaw
the curators annotated.

That number is small. **6.1% for the best model.** Ninety-four percent of what
o3 emitted was scored as a false positive.

**Inferred, not stated:** with 91 annotations, recall 21.1% implies about 19 true
positives per run, and precision 6.1% then implies about 296 false positives per
run across 83 papers -- roughly **3.6 false flags per paper per run** from the
best model available. The paper does not report raw counts; this is arithmetic
from Table 2 and should be quoted as approximate.

Three caveats on that 6.1%, all of which we should state rather than let a
reader assume:

- **The exhaustiveness assumption inflates FP.** A model that finds a genuine
  error the curators never annotated is scored as wrong. The authors defend this
  ("through case studies later in this paper, we notice such cases are highly
  unlikely") and their expert review found exactly one instance: Gemini-2.5-Pro
  spotting a BET surface area reported as `1606 cm2 g-1` where the unit should
  be `m2 g-1`, a factor of 10,000 (Section 4.2). So 6.1% is a **floor** on
  precision, not an estimate -- but the case studies are strong evidence that
  the floor is close to the truth, because the expert reviewers judged nearly
  every other unannotated flag to be a genuine model error.
- **The judge is unvalidated.** GPT-4.1 decides whether a predicted description
  denotes the same error as an annotation. The judge prompt (Appendix F.2)
  contradicts itself -- "A match occurs only when both `location` and
  `description` are identical" followed by "the location may be slightly
  differently named, but the description must match overall". No
  human-agreement figure for the judge is reported. This is the same weak point
  our own `agreement.py` note identifies in our matching rules, and neither
  project has solved it.
- **The "calibration" result is not what it appears to be.** The abstract says
  "confidence estimates are uniformly low" and Section 3.2 says it compares
  pass@4 against the model's "self-estimated confidence". But the generation
  prompt asks for `has_error` and a list of `{location, description}` and
  nothing else -- verified in Appendix F.2 and in `prompts.py` in the repo, both
  of which show no confidence field. Appendix C then defines Confidence as
  `1 - C(n-c, K)/C(n, K)` aggregated over annotations, where `c` is the number
  of the 8 runs in which the error was detected. **That is the pass@K estimator,
  computed from detection frequency.** Section 3.2's own supporting sentence
  confirms the reading: "we observe only two cases (both from o3) of full
  confidence" is a statement about errors found in all 8 runs.
  **Inferred, not stated:** Figure 4's calibration plot is therefore
  detection-frequency against detection-frequency, and the abstract's confidence
  claim restates low recall rather than establishing miscalibration. I could not
  find a reading of Appendix C that makes it a model self-report. Treat this as
  a likely wording error in the paper, and do not cite SPOT for a calibration
  finding.

## 3. Extraction -- the question that decides comparability

**Answer: curated, cleaned, and human-audited. Found in the paper, Section 2.1,
Stage 5 (Normalization).** Not inferred, not from the repo -- stated outright,
and stated as a deliberate design choice:

> While prior benchmarks in manuscript error detection and AI-assisted science
> have relied on raw PDFs or text-only inputs, this approach offloads document
> understanding to OCR and parsing modules rather than the LLM itself, thereby
> conflating upstream parser failures with downstream model errors.

Their pipeline: LlamaParse converts each PDF to Markdown and captures
"high-fidelity screenshots of every figure, table, and equation"; each page's
OCR text plus roughly eight images (full page, isolated equations, isolated
paragraphs) goes to GPT-4.1 for correction; and then --

> Finally, we conduct a manual audit of all processed pages to ensure that every
> flagged error remains visible and accurately represented in the OCR output.

That last sentence is the one that settles comparability. **A human verified,
for every instance, that the ground-truth error survived extraction.** By
construction, SPOT's extraction stage has zero misses on the quantity being
scored.

The paper also supplies our best available evidence that this matters, in
Appendix D.1. Their first pipeline pass, before the GPT-4.1 refinement stage,
introduced OCR errors such as dropped complex conjugations inside an integral.
Both o3 and Gemini-2.5-Pro **reacted to different OCR errors and reported them
as mathematical mistakes in the paper.** After refinement, o3's verdict on the
same manuscript flipped to "no errors". So the same model, on the same paper,
went from confidently accusing to finding nothing, purely on a change in
extraction quality. That is their observation, in their appendix, about their
own pipeline.

Set against our own measurements on the same axis:

| | measured here |
|---|---|
| numeric recall, PDF vs publisher-XML ground truth, previous extractor | **60.4%** (`docs/archive/ACQUISITION_STAGE_SPEC.md`) |
| same, current extractor | **95.8%** |
| papers whose extraction corrupts *digits* | **5 of 141 = 3.5%** (`docs/archive/ZOTERO_GENERALISATION_PHASE1.md`) |
| corpus papers with no publisher XML at all | **308 of 315 = 97.8%** |

The consequence for any head-to-head comparison: **SPOT's numbers are an upper
bound on what a real pipeline achieves, and the gap is not small.** Their 21.1%
recall is recall given that the error was guaranteed legible. Ours has to
survive a 4.2% miss rate on numbers and a 3.5% rate of documents where a digit
can arrive at a check as a value the paper never printed. Neither project can
quote the other's figures without this adjustment, and SPOT is the party that
chose to make the measurement cleaner rather than more realistic. They say why,
and their reason is defensible for their purpose -- they wanted to score models,
not parsers. It is simply not our purpose.

## 4. Where SPOT is ahead, and what we do that it does not

Not flattery in either direction.

**SPOT is straightforwardly better than us on five things.**

1. **Ground-truth provenance.** Their positives are author-acknowledged. Ours
   are analyst-established from retraction notices, institutional findings and
   published forensic analyses. Author acknowledgement is a cleaner label.
2. **Breadth.** Ten fields, 28 venues, 47 sources. Our labelled corpus is 78
   papers concentrated in the canonical misconduct cases (`eval/PREREGISTRATION.md`).
3. **Volume of measurement.** Thirteen models, eight independent runs each,
   bootstrap intervals, plus three ablations -- context length (segment versus
   full paper), modality (figures in versus stripped), and test-time scaling
   (o4-mini reasoning effort low/med/high). Roughly $5,000 of API spend
   (Appendix, NeurIPS checklist item 8). Our reliability evidence is 3 runs on
   1 paper.
4. **Multimodality.** Figures are actually supplied, and 27 of 91 errors are
   figure duplication. We were figure-blind when this was written. (2026-10-16:
   the statistical analysts still do not see figures unless `--figures` is
   passed; image-duplication detection now exists as an optional, separately
   distributed image analysis package, not part of this repository.) Their result that GPT-4.1 beats o3
   44.4% to 0.0% on figure duplication at pass@4, while o3 beats everything on
   equations at 62.6%, is a finding we could not have produced.
5. **It is published, citable, and released** -- data, prompts, harness, and
   per-run generations.

**What we do that SPOT does not do at all.**

1. **Honest-paper controls, as the primary endpoint.** SPOT has zero correct
   papers and reports no specificity. Our pre-registration
   (`eval/PREREGISTRATION.md`) fixes the unit of analysis as the (paper, tool)
   cell, assigns all 624 cells from the manifest before running, and yields
   **408 NULL-EXPECTED cells** where any accusation is a false positive, against
   60 FIRE-EXPECTED cells. The cardinal rule is written into the endpoint
   hierarchy: specificity is primary, sensitivity secondary, and no amount of
   sensitivity rescues a failed specificity result. SPOT cannot state a
   false-accusation rate for an honest paper, and neither can anyone using it.
2. **Deterministic checks with recomputable warrants.** SPOT's system under test
   is a model emitting prose. Ours is statcheck / GRIM / GRIMMER / SPRITE /
   duplication -- checks whose ground truth is computable, so a finding carries
   the arithmetic that produced it and a reader can refute it without trusting
   us.
3. **A refusal channel.** Our `indeterminate` verdict is scored as neither a hit
   nor a false positive. SPOT's schema is `has_error: true|false` with no way to
   say "the input does not support a judgement", which forces every uncertain
   case into an assertion.
4. **Extraction inside the measurement.** We measure numeric recall and glyph
   corruption as pipeline properties and forbid dropping papers we extract badly
   ("the extraction was poor on this one is not grounds for exclusion",
   `eval/PREREGISTRATION.md` Section 3). SPOT audits the error into visibility
   and reports on what remains.
5. **Pre-registration.** Severity threshold, exclusions, unit of analysis and
   clustering fixed before any scored run, with cluster bootstrap over 16
   misconduct cases rather than 30 papers. SPOT's exhaustiveness convention was
   necessarily settled after seeing model output.
6. **Synthetic controls.** `src/forensic_metascience_ai_toolkit/simulation.py` generates
   negative controls correct by construction and positive controls with a
   single injected flaw, deterministic and free of API calls.

**And the finding that decides whether SPOT is a benchmark for us at all: it
contains essentially none of the errors our toolkit checks.** Scanning all 91
annotation texts for the vocabulary of statistical forensics returns zero
mentions of p-value, standard deviation, sample size, t-test, ANOVA,
chi-square, or confidence interval; the six hits for "mean" are all the English
word "meaning". The four Statistical reporting rows are an incorrect angle
calculation, a comparison of non-comparable baselines, possibly-wrong metric
calculations, and negative values reported for pharmacokinetic parameters
(AUC, elimination rates, LOQ) in a table. Only the last is something our panel
could plausibly reach, and only via a plausibility bound rather than a
consistency test. **There is not one statcheck-eligible, GRIM-eligible or
SPRITE-eligible error in SPOT.**

So Greg's instinct on 2026-08-13 was right, and it is stronger than "not exactly
what we're doing". SPOT is a benchmark for **long-context multimodal reading
comprehension applied to error-spotting**: 70% of its errors are broken proofs
and duplicated images. We are building an **accusation instrument constrained by
arithmetic**, whose worst outcome is a false accusation and whose primary
evidence must be a specificity figure on honest papers. The two projects share a
motivating question and almost no measurement surface. The one place they meet
squarely is reliability across runs, and there both teams found the same thing
independently.

---

# Part 2 -- internal note: what to take, and what to leave

## Adopt

**A1. Their PDFs plus their audited markdown is a ready-made extraction
experiment, and it is the most valuable thing in the release.** The GitHub repo
ships `data/<doi>/` for **91 instances**: the archived pre-correction manuscript
PDF (`<doi>_err1.pdf`, also `_err2`/`_err3` where a paper carries several errors;
arXiv entries carry the withdrawn version, e.g. `2402.14546v1.pdf`), a
`metadata.json`, and extracted figure images -- 1,469 images, ~84 MB of metadata,
PDFs at a median 2.6 MB (spot-checked: `10.1002_btm2.10667_err1.pdf` is the full
14-page research article, not a correction notice).

`metadata.json` schema:

```
{"doi": "<doi with / replaced by _>",
 "content": [ {"type": "text",      "text": "<LlamaParse markdown, GPT-4.1-refined>"},
              {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
              ... ]}
```

-- i.e. an OpenAI-format interleaved message list. Because that markdown was
**human-audited for fidelity at the error location**, it is a rare thing: a
near-ground-truth rendering of 91 real papers, paired with the source PDF.
Proposed experiment, cheap and directly serving the acquisition argument: run
our Stage 0 on their PDFs (2026-10-16: the Stage 0 acquisition agent was never
built -- see `docs/archive/ACQUISITION_STAGE_SPEC.md`; today the equivalent is
the docling extraction path, `extraction/docling_tables.py`), diff the numeric content against their audited
markdown, and report what the curation buys in numeric recall. That converts our
"their numbers are an upper bound" claim from an argument into a measurement,
on their corpus rather than ours.

**A2. The prompt pair, as a documented baseline.** Generation prompt and
LLM-judge prompt are verbatim in Appendix F.2 and in `prompts.py`. Worth reading
against our prompts (now `src/forensic_metascience_ai_toolkit/modules/*/prompt.md` and the
shared `src/forensic_metascience_ai_toolkit/core/prompts/`) -- note in particular that their
generation prompt explicitly scopes out presentational, rhetorical, stylistic and
citation issues, which is the same boundary our scope module enforces, reached
independently.

**A3. `annotation/retracted_machine_filtered_final.csv`** in the repo is the
pre-filter candidate pool behind the benchmark. Not inspected in detail here;
likely a useful seed list if we ever want more retraction-anchored positives.

**A4. Cite them for the extraction argument.** Appendix D.1 -- pre-refinement OCR
errors caused both o3 and Gemini to report phantom mathematical errors, and o3's
verdict flipped to "no errors" after the extraction improved -- is an
independent team demonstrating our thesis on their own pipeline. It is a better
citation for us than anything else in the paper.

## Do not adopt

**D1. The corpus, as a benchmark for this toolkit.** Zero statcheck/GRIM/SPRITE
positives (Part 1, Section 4). Running our panel on SPOT would measure nothing.

**D2. The exhaustive-annotations convention.** Fine for their purpose; fatal for
ours. It scores a genuine unannotated finding as a false accusation, which
inverts the exact quantity we are trying to protect.

**D3. Their "confidence"/calibration construct.** See Part 1, Section 2. Do not
cite SPOT for calibration.

**D4. A pass@K-only reliability story.** Their pass@K is well specified and we
already borrowed it, but note the structural difference: SPOT's `G_i` is a fixed
ground-truth set, so matching is annotation-to-prediction. Ours is
prediction-to-prediction across runs with no ground truth, which is why our
strict/loose bracket is 34%-64% and theirs is a point estimate. Task #154 (the
adjudicator) is still the fix; SPOT does not supply one, and their own judge is
unvalidated. *(2026-10-16: an adjudicator now exists, `modules/adjudicator`,
but it merges and grades the two analysts' findings within ONE run. Cross-run
matching is still `evaluation/agreement.py` (`metascience agreement`), which
reads `findings.v2.json` and still reports the strict/loose string-rule
bracket; its own docstring calls those rules a placeholder. No validated
cross-run rediscovery judge exists, so this item is still open.)*

## Not resolved, flagged for Greg

- **Licensing.** The code repo has **no LICENSE file** (GitHub API, 2026-08-18:
  `license: None`), so the harness and prompts are all-rights-reserved by
  default -- fine to read and cite, not obviously fine to vendor. `SPOT-MetaData`
  is CC-BY-4.0. Separately, Appendix E says 21 of the 83 manuscripts are
  paywalled and "we do not redistribute them directly", yet the GitHub `data/`
  tree contains 91 full manuscript PDFs. I have not established that any of those
  91 is one of the 21. Worth checking before we mirror or redistribute anything
  from that tree; reading it in place is not at issue.
- **Text-only subset composition.** The paper states the figure-independent
  subset is 48 instances. **Inferred:** 91 - 27 figure-duplication - 16
  figure-dependent data-inconsistency = 48, which implies the subset is 37
  equation/proof, 4 statistical reporting, 3 reagent identity, 2 experiment
  setup, 2 data inconsistency. Arithmetic is consistent but the composition is
  not printed in the paper. Under that reading, **11 of 91 SPOT errors are
  text-based and non-mathematical.**
- **A likely typo worth not propagating.** Section 2.1 Stage 3 reads "we do not
  include any error with explicit acknowledgment from the original authors",
  which contradicts the entire stage and the sentence before it. Read as
  "without".
