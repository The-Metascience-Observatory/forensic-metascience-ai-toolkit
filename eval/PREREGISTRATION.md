# Pre-registration: measuring the FMT tool panel against the labelled corpus

**Status:** committed BEFORE any scored run. Version 1, 2026-08-09.
**Corpus:** `eval/ground_truth/` -- `manifest.csv` (78 papers) and `papers/`.
**Analyst:** Greg Fitzgerald. **Repo:** `agent_for_forensic_metascience`, branch `review/romano-followups`.

Everything in this file was written from the manifest's *structure* only. No paper has been
scored, and no run output has been joined to the label column. Every count below is
reproduced by the script in Appendix A, which reads only columns that describe eligibility
(`can_validate_tools`, `cannot_validate_tools`, `expected_statistical_signature`) -- never a
tool's actual output, because no tool has been run.

The point of writing this down first is narrow and specific: with 8 tools, 5 severity levels,
3 plausible units of analysis and a free hand over exclusions, the same run supports a
sensitivity anywhere from roughly 40% to roughly 90%. Choosing after seeing the numbers is
not fraud, it is the ordinary way an honest person gets a flattering answer. The choices are
therefore made here.

---

## 1. What is being measured, and what is not

The FMT panel is being measured as an **accusation instrument**: given a paper, does it raise
an accusatory finding, and is that accusation right?

It is **not** being measured as a fraud detector. No statistical-consistency tool detects
fraud; they detect numbers that cannot have arisen the way the paper says they did, which has
many innocent causes (transcription error, ambiguous reporting convention, our own extraction
failure). Heathers' framing is the operative one -- the output modifies trust, it does not
establish misconduct -- and the endpoints below are worded accordingly.

**The cardinal rule governs the endpoint hierarchy.** A false accusation against an honest
paper is the worst output this system can produce. A missed flaw is second worst. A visible
refusal (`indeterminate`) is tolerated and is *not* scored as either error. Specificity is
therefore the primary endpoint and sensitivity the secondary, and no amount of sensitivity
rescues a failed specificity result (§7).

---

## 2. Unit of analysis

**Primary unit: the (paper, tool) cell.** Not the paper. The manifest declares, per paper,
which tools have a documented ground-truth signature and which cannot be validated at all, so
the truth value lives at the cell.

Each of the 78 x 8 = 624 cells is assigned to exactly one of four states, entirely from the
manifest, before running:

| State | Definition | n |
|---|---|---|
| **FIRE-EXPECTED** | tool named in `expected_statistical_signature`, and not in `cannot_validate_tools` | **60** |
| **NULL-EXPECTED** | paper's `expected_statistical_signature` is exactly `none`, tool not vetoed | **408** |
| **UNDETERMINED** | fraud paper, tool NOT named in its expected signature, not vetoed | **146** |
| **VETOED** | tool listed in `cannot_validate_tools` (no usable text) | **10** |

UNDETERMINED is the honest category and it is large. On a fraudulent paper, a tool with no
documented signature has no known truth value: a hit might be a real detection of an
undocumented flaw or a false positive, and nothing in the record distinguishes them.
**UNDETERMINED cells are reported separately and are never counted as hits or as false
positives.** Folding them into either direction is the single easiest way to manufacture a
good number here, and it is prohibited.

**Independence.** The 30 fraud papers are **16 misconduct cases**, not 30 (Sato 8, Anderson 4,
Skau 2, Fujii 2, Potti 2, Rutherford 2, and 10 singletons). Papers within a case share
authors, methods and often the same fabricated data-generating process, so they are not
independent observations. The 48 controls are 47 distinct first authors and are treated as 48
clusters. **Every interval in this study is a cluster bootstrap resampling CASES, never
papers.** The effective sample size on the positive side is 14 cases, and the write-up must
lead with that number, not with 60 cells.

---

## 3. Population and pre-declared exclusions

All 78 papers are in the analysis population. Exclusions operate at the cell level via the
state assignment in §2 and are fully determined by the manifest. No paper is excluded after
the fact for any reason other than the two logged below.

Two exclusions are permitted post hoc, and both must be recorded in §11 with the paper, the
reason and the timestamp:

1. **Harness crash.** A run that terminates without producing output may be re-run once. Both
   attempts are retained.
2. **Blinding failure.** A paper whose scrubbed materials still contain a label marker at
   verification (§5) is excluded from the scored set and reported as a blinding failure, not
   as a tool result.

Nothing else. In particular, "the extraction was poor on this one" is **not** grounds for
exclusion -- poor extraction is part of what is being measured, and dropping the papers we
handle badly is how a pipeline's accuracy gets overstated.

### Three fraud papers where a clean report is the CORRECT answer

The manifest already encodes this and the scoring must honour it:

- **Potti / Salter 2008 and Potti / Garman 2008** -- genomic papers containing no parseable
  test statistics, no mean+/-SD pairs and no GRIM-eligible means. The input preconditions for
  the panel are unsatisfiable. *Any* non-empty GRIM/SPRITE/statcheck output is a hallucinated
  extraction. These are the extraction-hallucination canaries and they sit in NULL-EXPECTED.
- **Shu / Gino / Ariely 2012** -- every documented signature is file-level or raw-data level;
  none is a summary-statistic signature. A clean report is correct and is evidence that the
  summary-statistic layer needs a file-forensic layer beside it.

A run that "catches" all three has failed, and the report must say so in those words.

### One paper that is not a fraud

**Sugira Muryango / Siboyintore 2025** is contested: the retraction is driven by an
authorship and data-permission dispute, the corresponding author concedes a sample-size error
and maintains the conclusions. It is labelled **misreporting**, never fraud, in every output.
It remains a legitimate positive control for an N-consistency check (means reported against
N=247 were computed on n=44) and keeps its FIRE-EXPECTED cell for that check only.

### Circularity

The 8 Sato/Iwamoto papers were identified *by* baseline-similarity analysis (Bolland et al.,
Neurology 2016;87:2391-2402). Scoring baseline-similarity against them measures nothing.
Their `cannot_validate_tools` already excludes it; they remain valid for GRIM/SPRITE/statcheck,
which are anchored independently by the Kurume University finding and the forged-authorship
determinations. **After this exclusion the corpus contains exactly one FIRE-EXPECTED cell for
baseline-similarity**, so that tool's sensitivity is not estimable here and no sensitivity
figure for it will be reported.

### What this corpus cannot measure, stated in advance

FIRE-EXPECTED cells by tool: grim 16, duplication 11, sprite 10, grimmer 10, statcheck 9,
digit_preference 3, baseline_similarity 1, **debit 0**.

**DEBIT has no positive control in this corpus at all.** Its sensitivity is unmeasurable here
and will be reported as such -- not as a missing value, not omitted from the table, but as an
explicit "not estimable, n=0". The same applies to baseline_similarity (n=1) and
digit_preference (n=3), whose intervals will be too wide to support any claim.

### Correction, 2026-08-10: digit_preference is not merely under-powered, it does not exist

Found while building the runner, and recorded here rather than quietly amended.

**This toolkit implements no digit-preference check.** There is no terminal-digit, no Benford,
no digit-frequency tool anywhere in the registry. I built the tool vocabulary above from the
manifest's `can_validate_tools` column without verifying that each named technique was
something we had actually written, so the cell counts include 78 cells for a check that cannot
run in principle.

The arithmetic above is unaffected -- those cells were already going to be recorded as
unevaluated -- but the *reason* differs, and the difference matters to a reader. An
unevaluated cell invites the question "why did you not run it"; an unimplemented one has a
different answer. The runner now records them as **unscoreable, not unevaluated**, in those
words.

Heathers 2025 also gives no source for digit preference: it is not in the book, and its
inclusion rule ("if I had direct evidence that a test had been used more than once to publicly
criticize a paper") explains the absence. Anyone implementing it later needs a citation from
elsewhere.

---

## 4. The decision rule

A cell **accuses** when the panel returns, for that tool on that paper, at least one finding
with severity in **{`impossible`, `highly_suspicious`}**.

`suspicious`, `indeterminate` and `consistent` are not accusations. This is fixed now because
the severity threshold is the most tempting free parameter in the study: dropping to
`suspicious`+ raises sensitivity and lowers specificity, and choosing between them after
seeing both is exactly the move this document exists to prevent.

A **secondary** analysis at the `suspicious`+ threshold will be reported alongside, labelled
secondary, with both numbers always shown together so neither can be quoted alone.

Paper-level roll-up, for the secondary paper-level endpoints: a paper accuses if any eligible
cell accuses.

---

## 5. Blinding

This corpus is **not currently blind**, and running it as-is would measure reading
comprehension rather than forensic capability. Established before writing this: all 15 fraud
papers that have XML carry an explicit retraction marker inside the document
(`This article has been retracted`, `is-retracted`, `retraction-forward`), and 14 of 30 fraud
titles contain the literal string "RETRACTED". The frauds are also the canon -- Reuben, Fujii,
Stapel, Wansink, Sato -- which a frontier model recognises by name.

Conditions that must ALL hold before a scored run:

1. **Scrubbing.** Materials pass a blinding pass that removes retraction markers, retraction
   notices, cross-references to retraction articles, and label-bearing title fragments.
2. **Verification, not assertion.** The blinding pass emits a per-paper report of what it
   removed and a residual scan; a paper with any residual marker is excluded per §3.2. The
   verification is a test in the suite, not a manual check.
3. **Filenames and paths.** DOIs, titles and directory names are replaced by opaque ids in
   everything the model sees, including tool results and error messages.
4. **No manifest columns reach the model.** `label`, `retraction_status`,
   `retraction_reason`, `how_established`, `expected_statistical_signature` and `notes` are
   analyst-side only.

**Irreducible leakage.** Author identity and canonical status cannot be scrubbed without
destroying the document. The write-up must state that any model-mediated result on this
corpus carries an unknown upward bias from recognition, and must not present a blinded
measurement as if recognition had been eliminated. This is the strongest argument for running
the **offline tool panel** (no model in the loop) as the primary measurement: it cannot
recognise anything.

**Declarations must also be blind.** The panel needs human-written per-table variable
declarations (variable type, scale bounds, N). These are an input the analyst controls, and
writing them with knowledge of the label would leak the answer into the input. Procedure:
declarations are written from a shuffled, de-identified list, time-boxed, committed and
hashed before any tool is run, and the hash recorded in §11. If a declaration is later
corrected, the correction is logged with its reason and the run is re-scored both ways.

---

## 6. Freeze, then join

The mechanism that makes "no peeking" checkable:

1. Run the panel over the blinded corpus. Write raw per-cell output to
   `eval/runs/<run-id>/cells.jsonl`.
2. Commit it. Record the git SHA and the SHA-256 of `cells.jsonl` in §11.
3. **Only then** join to the label column and compute the endpoints.

Any analysis choice made after step 3 is exploratory by definition and is labelled so.

---

## 7. Endpoints

**E1 (PRIMARY) -- false-accusation rate.** Proportion of NULL-EXPECTED cells (n=408) that
accuse. Reported with a cluster-bootstrap 95% CI over cases, and at the paper level over the
51 papers whose expected signature is `none`.

**E2 (SECONDARY) -- sensitivity.** Proportion of FIRE-EXPECTED cells (n=60, 14 cases) that
accuse. Cluster-bootstrap 95% CI over the 14 cases. Reported per tool only where n >= 9
(grim, duplication, sprite, grimmer, statcheck); the other three are reported as not
estimable.

**E3 (SECONDARY) -- the canaries.** Number of accusatory findings on Potti x2 and Shu, where
the correct count is zero and any hit is a hallucinated extraction.

**E4 (DESCRIPTIVE) -- coverage.** Proportion of eligible cells the panel could evaluate at all
(as opposed to refusing for missing inputs). A high refusal rate is not a failure -- a visible
refusal is the tolerated outcome -- but it bounds what every other number means, and the
existing statcheck pass over this corpus (only 9 of 78 papers contained any APA-format
statistic) says to expect it to bind hard.

**E5 (DESCRIPTIVE) -- the undetermined cells.** Accusation rate among the 146 UNDETERMINED
cells, reported alone, with the explicit statement that it is uninterpretable as either
sensitivity or specificity.

### Zero counts

A zero numerator is **never** reported as "100% specificity" or "0% false positives". It is
reported as a point estimate of 0 with a one-sided 95% Clopper-Pearson upper bound, at the
case level. For 48 control clusters that bound is about 6%; for the smaller per-tool strata it
will be far worse, and the bound is what gets quoted.

### What this corpus can resolve, computed before the run

The resolution limits below come from the cluster counts alone and are known now, without
running anything. They are the honest ceiling on what any result can claim.

| Endpoint | Clusters | Best possible claim |
|---|---|---|
| E1 false-accusation rate, all tools | 50 | a perfectly clean run bounds it at **5.8%**, not zero |
| E1 per tool | 50 | same 5.8% |
| E2 sensitivity, all tools | 14 | a perfect score establishes only **> 80.7%** |
| E2 grim | 7 | **> 65.2%** at best; 16 cells |
| E2 grimmer | 8 | **> 68.8%** at best; 10 cells |
| E2 sprite | 6 | **> 60.7%** at best; 10 cells |
| E2 statcheck | 6 | **> 60.7%** at best; 9 cells |
| E2 debit, baseline_similarity, digit_preference | 0-3 | **not estimable** |

Read the second column before the third. This corpus cannot demonstrate that the panel is
safe below about a 6% false-accusation rate, and it cannot demonstrate that any single tool
exceeds roughly two-thirds sensitivity. Those are properties of 78 papers and 16 misconduct
cases, not of the tools, and no analysis choice improves them. If a tighter claim is needed,
the corpus has to grow -- and it has to grow in *cases*, not papers, so eight more Sato papers
would buy nothing.

### No hypothesis tests

This is an estimation study. No p-values, no "significant" anything, no null-hypothesis test
comparing fraud to control rates. Consequently no multiplicity correction is applied, and the
absence of one is not an oversight -- it is a consequence of not testing. Intervals are
descriptive.

---

## 8. What would count as a failure

Declared now, so that a bad result cannot be re-narrated as a mixed one.

- **The panel is not deployable as an accusation instrument if the E1 upper 95% bound exceeds
  20%** at the cell level, regardless of E2. One accusation in five against honest work is
  disqualifying, and a good sensitivity alongside it makes the instrument more dangerous, not
  less.
- **The extraction layer is unfit if E3 > 0**, because a hit on Potti or Shu is our own
  fabrication reported in the grammar of a claim about the paper -- the house failure pattern.
- **The corpus, not the tool, is the finding if E4 < 0.25.** If fewer than a quarter of
  eligible cells can be evaluated, the study measures document parsing and should be reported
  as a parsing result with the forensic endpoints suppressed.
- **A null E2 is publishable and will be published.** If the panel misses most documented
  signatures, that is the answer, and it is more useful to the field than another paper
  asserting that these tools work. The existing statcheck pass already points this way: it
  flagged 3 of 6 testable controls against 1 of 3 testable frauds -- the contrast inverted, on
  the only 9 papers it could test at all.

---

## 9. Analysis code

`src/forensic_metascience_ai_toolkit/evaluation/corpus.py`, committed together with this file and before any
run. It takes `cells.jsonl` plus `manifest.csv` and emits every number in §7 with no free
parameters left to choose:

```
python -m forensic_metascience_ai_toolkit.evaluation.corpus eval/runs/<run-id>/cells.jsonl --secondary
```

`verdict()` evaluates the §8 failure conditions mechanically, so a failing run reports itself
as failing rather than waiting to be characterised by whoever writes it up.

Tested in `tests/test_corpus_scoring.py` (28 assertions) against hand-counted toy corpora and
against the real manifest's structure. Three of those tests exist to stop specific ways of
cheating:

- UNDETERMINED cells are proven not to leak into either headline, by accusing on every one of
  them and asserting both headline numerators stay at zero.
- A clean sweep over a small corpus is proven to FAIL the deployability check, so a tiny
  no-findings run cannot be quoted as a pass.
- The cluster bootstrap is proven to resample cases, not cells: eight hits in one case beside
  one miss in another must yield an interval reaching zero, which cell-level resampling
  cannot produce.

The real-manifest assertions (60/408/146/10 cells, 16 cases, debit's zero positive controls)
mean that a silent change to the corpus fails the suite instead of quietly running a
different study under this protocol.

---

## 10. Exploratory work

Anything not in §7 is exploratory: per-journal patterns, per-year patterns, severity
distributions, error taxonomies, case studies of individual disagreements. All valuable, all
labelled EXPLORATORY in the write-up, none used to support a headline claim.

---

## 11. Run record and deviations

To be filled in at run time. Empty is the correct state of this section right now.

| Field | Value |
|---|---|
| Declarations committed (SHA-256) | *pending* |
| Blinding verification passed | *pending* |
| Run id | *pending* |
| `cells.jsonl` SHA-256 | *pending* |
| Git SHA at freeze | *pending* |
| Date of label join | *pending* |

**Deviations from this pre-registration:** none yet. Each gets a dated entry naming what
changed, why, and whether it was decided before or after the label join.

---

## Appendix A -- reproducing the cell counts

```python
import csv, collections, re
rows = list(csv.DictReader(open('eval/ground_truth/manifest.csv')))
def toks(s):
    return set(t.strip() for t in s.replace('|', ',').split(',')
               if t.strip() and t.strip() != 'none')

state = collections.Counter()
for r in rows:
    cv, nv = toks(r['can_validate_tools']), toks(r['cannot_validate_tools'])
    es = toks(r['expected_statistical_signature'])
    expects_none = r['expected_statistical_signature'].strip() == 'none'
    for t in cv | nv:
        if t in nv:            state['VETOED'] += 1
        elif t in es:          state['FIRE'] += 1
        elif expects_none:     state['NULL'] += 1
        else:                  state['UNDETERMINED'] += 1
# FIRE 60, NULL 408, UNDETERMINED 146, VETOED 10, total 624
```

Case clustering uses the bracketed case name at the start of `notes`
(`[Sato (Kurume finding; ...)]` -> `Sato`), giving 16 fraud cases.
